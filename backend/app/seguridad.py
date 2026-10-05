"""Hash de contraseñas (bcrypt) y tokens JWT para el panel."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import obtener_configuracion
from app.db import obtener_sesion
from app.dominio import Rol
from app.modelos import Usuario

_bearer = HTTPBearer(auto_error=False)


def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, hash_guardado: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("utf-8"))
    except ValueError:
        return False


def crear_token(usuario: Usuario) -> str:
    config = obtener_configuracion()
    ahora = datetime.now(UTC)
    payload = {
        "sub": str(usuario.id),
        "rol": usuario.rol,
        "iat": ahora,
        "exp": ahora + timedelta(minutes=config.jwt_minutos_expiracion),
    }
    return jwt.encode(payload, config.jwt_secreto, algorithm=config.jwt_algoritmo)


def _no_autorizado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detalle, headers={"WWW-Authenticate": "Bearer"}
    )


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    sesion: Session = Depends(obtener_sesion),
) -> Usuario:
    if credenciales is None:
        raise _no_autorizado("Falta el token de acceso")
    config = obtener_configuracion()
    try:
        payload = jwt.decode(credenciales.credentials, config.jwt_secreto, algorithms=[config.jwt_algoritmo])
        usuario_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _no_autorizado("Token inválido o vencido") from None
    usuario = sesion.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise _no_autorizado("Usuario inexistente o inactivo")
    return usuario


def requiere_supervisor(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    if usuario.rol != Rol.SUPERVISOR:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol supervisor")
    return usuario
