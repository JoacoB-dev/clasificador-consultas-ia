from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import obtener_sesion
from app.esquemas import LoginEntrada, TokenSalida, UsuarioSalida
from app.modelos import Usuario
from app.seguridad import crear_token, usuario_actual, verificar_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenSalida)
def login(datos: LoginEntrada, sesion: Session = Depends(obtener_sesion)) -> TokenSalida:
    usuario = sesion.scalar(select(Usuario).where(func.lower(Usuario.email) == datos.email.lower()))
    if usuario is None or not usuario.activo or not verificar_password(datos.password, usuario.hash_password):
        # Mismo mensaje para usuario inexistente y contraseña mala (no revelar cuál falló)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email o contraseña incorrectos")
    return TokenSalida(access_token=crear_token(usuario), usuario=UsuarioSalida.model_validate(usuario))


@router.get("/yo", response_model=UsuarioSalida)
def yo(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
    return usuario
