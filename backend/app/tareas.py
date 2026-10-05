"""Tareas que ejecuta el worker de RQ."""

import logging
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.clasificacion.base import Clasificador
from app.clasificacion.esquema import ConsultaEntrada, ErrorClasificacion, UsoRegistro
from app.clasificacion.fabrica import obtener_clasificador
from app.config import obtener_configuracion
from app.db import SesionLocal
from app.dominio import EstadoConsulta
from app.modelos import Consulta, UsoLLM
from app.reglas_negocio import aplicar_reglas

log = logging.getLogger(__name__)


def _registrar_uso(sesion: Session, consulta_id: int, uso: UsoRegistro, error: str | None = None) -> None:
    sesion.add(
        UsoLLM(
            consulta_id=consulta_id,
            modelo=uso.modelo,
            tokens_entrada=uso.tokens_entrada,
            tokens_salida=uso.tokens_salida,
            costo_usd=uso.costo_usd or Decimal("0"),
            duracion_ms=uso.duracion_ms,
            intentos=uso.intentos,
            exito=error is None,
            error=error,
        )
    )


def procesar_en_sesion(sesion: Session, consulta_id: int, clasificador: Clasificador) -> Consulta | None:
    """Clasifica una consulta y aplica las reglas de negocio. Devuelve la consulta actualizada."""
    consulta = sesion.get(Consulta, consulta_id)
    if consulta is None:
        log.warning("La consulta %s no existe (¿se borró?)", consulta_id)
        return None
    if consulta.estado == EstadoConsulta.APROBADA:
        log.info("La consulta %s ya está aprobada; no se reprocesa", consulta_id)
        return consulta

    consulta.estado = EstadoConsulta.EN_PROCESO
    consulta.intentos += 1
    sesion.commit()

    entrada = ConsultaEntrada(
        asunto=consulta.asunto,
        cuerpo=consulta.cuerpo,
        remitente_nombre=consulta.remitente_nombre,
        canal=consulta.canal,
    )
    try:
        salida = clasificador.clasificar(entrada)
    except ErrorClasificacion as error:
        log.error("Falló la clasificación de la consulta %s: %s", consulta_id, error)
        if error.uso:
            _registrar_uso(sesion, consulta_id, error.uso, error=str(error))
        consulta.estado = EstadoConsulta.ERROR
        consulta.error_detalle = str(error)
        sesion.commit()
        return consulta

    r = salida.resultado
    asignacion = aplicar_reglas(r, f"{consulta.asunto} {consulta.cuerpo}", consulta.recibida_en)

    consulta.categoria = r.categoria.value
    consulta.categoria_modelo = r.categoria.value
    consulta.urgencia_modelo = r.urgencia.value
    consulta.urgencia = asignacion.urgencia.value
    consulta.sentimiento = r.sentimiento.value
    consulta.resumen = r.resumen
    consulta.datos_extraidos = r.datos_extraidos.model_dump()
    consulta.borrador_respuesta = r.borrador_respuesta
    consulta.confianza = Decimal(str(round(r.confianza, 3)))
    consulta.clasificador = salida.clasificador
    consulta.area_asignada = asignacion.area
    consulta.sla_vence_en = asignacion.sla_vence_en
    consulta.reglas_aplicadas = asignacion.reglas_aplicadas
    consulta.estado = EstadoConsulta.CLASIFICADA
    consulta.error_detalle = None
    consulta.revisada_en = None
    consulta.clasificada_en = datetime.now(UTC)
    if salida.uso:
        _registrar_uso(sesion, consulta_id, salida.uso)
    sesion.commit()
    return consulta


def procesar_consulta(consulta_id: int) -> str:
    """Punto de entrada que llama RQ (recibe solo el id, los datos se leen de la base)."""
    clasificador = obtener_clasificador(obtener_configuracion())
    with SesionLocal() as sesion:
        consulta = procesar_en_sesion(sesion, consulta_id, clasificador)
        return consulta.estado if consulta else "inexistente"
