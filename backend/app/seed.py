"""Carga datos de demo: usuarios, consultas de ejemplo ya clasificadas y algunas revisadas.

Uso: python -m app.seed            (idempotente: no duplica si ya hay datos)
     python -m app.seed --encolar  (manda las consultas a la cola en vez de clasificarlas acá)

Las consultas se clasifican con el clasificador activo (Claude si hay clave, si no el simulado).
"""

import argparse
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.clasificacion.fabrica import obtener_clasificador
from app.cola import obtener_cola
from app.config import obtener_configuracion
from app.db import SesionLocal
from app.dominio import Categoria, EstadoConsulta, Rol
from app.esquemas import ConsultaImportada
from app.modelos import Consulta, Usuario
from app.seguridad import hashear_password
from app.servicios import actualizar_consulta, aprobar_consulta
from app.tareas import procesar_en_sesion

log = logging.getLogger("seed")
RUTA_DEMO = Path(__file__).resolve().parent.parent / "ejemplos" / "consultas_demo.json"
PASSWORD_DEMO = "demo1234"
USUARIOS_DEMO = [
    ("supervisor@demo.local", "Sabrina Supervisora", Rol.SUPERVISOR),
    ("operador@demo.local", "Omar Operador", Rol.OPERADOR),
]
# Cuántas de las consultas demo quedan revisadas por un humano (para que haya métricas)
REVISADAS = 9
APROBADAS = 6


def crear_usuarios(sesion: Session) -> dict[str, Usuario]:
    usuarios = {}
    for email, nombre, rol in USUARIOS_DEMO:
        usuario = sesion.scalar(select(Usuario).where(Usuario.email == email))
        if usuario is None:
            usuario = Usuario(email=email, nombre=nombre, rol=rol.value, hash_password=hashear_password(PASSWORD_DEMO))
            sesion.add(usuario)
            log.info("Usuario creado: %s (%s)", email, rol.value)
        usuarios[rol.value] = usuario
    sesion.commit()
    return usuarios


def crear_consultas(sesion: Session, usuarios: dict[str, Usuario], encolar: bool) -> None:
    if sesion.scalar(select(func.count(Consulta.id))):
        log.info("Ya hay consultas cargadas; no se agregan las de demo")
        return
    items = json.loads(RUTA_DEMO.read_text(encoding="utf-8"))
    ahora = datetime.now(UTC)
    clasificador = None if encolar else obtener_clasificador(obtener_configuracion())
    cola = obtener_cola() if encolar else None

    for i, item in enumerate(items):
        datos = ConsultaImportada.model_validate(item)
        # Repartimos las fechas en los últimos 3 días para que haya SLA vencidos y al día
        consulta = Consulta(
            canal=datos.canal.value,
            remitente_nombre=datos.nombre,
            remitente_email=str(datos.email),
            asunto=datos.asunto,
            cuerpo=datos.cuerpo,
            estado=EstadoConsulta.PENDIENTE.value,
            recibida_en=ahora - timedelta(hours=5 * (len(items) - i)),
        )
        sesion.add(consulta)
        sesion.commit()
        if cola:
            cola.encolar(consulta.id)
            continue
        procesar_en_sesion(sesion, consulta.id, clasificador)

        # Simulamos la revisión humana: corrige la categoría si el modelo le erró y aprueba algunas
        if i < REVISADAS and consulta.estado == EstadoConsulta.CLASIFICADA:
            revisor = usuarios[Rol.SUPERVISOR.value] if i % 2 else usuarios[Rol.OPERADOR.value]
            etiqueta = Categoria(item["etiqueta"])
            if consulta.categoria != etiqueta.value:
                actualizar_consulta(sesion, consulta, revisor, None, etiqueta, None)
            else:
                consulta.revisada_en = ahora
                sesion.commit()
            if i < APROBADAS:
                aprobar_consulta(sesion, consulta, revisor, None)
    log.info("Se cargaron %s consultas de demo", len(items))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Carga datos de demo")
    parser.add_argument("--encolar", action="store_true", help="Encolar en Redis en vez de clasificar acá")
    args = parser.parse_args()
    with SesionLocal() as sesion:
        usuarios = crear_usuarios(sesion)
        crear_consultas(sesion, usuarios, args.encolar)


if __name__ == "__main__":
    main()
