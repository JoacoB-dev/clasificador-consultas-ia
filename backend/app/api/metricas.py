from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import obtener_configuracion
from app.db import obtener_sesion
from app.dominio import EstadoConsulta
from app.esquemas import MetricasPrecision, MetricasUso, ResumenBandeja
from app.modelos import Consulta, Usuario
from app.seguridad import requiere_supervisor, usuario_actual
from app.servicios import calcular_precision, calcular_uso

router = APIRouter(prefix="/api/metricas", tags=["métricas"])


def nombre_clasificador_activo() -> str:
    config = obtener_configuracion()
    return f"claude:{config.llm_modelo}" if config.usa_llm_real else "simulado-reglas"


@router.get("/resumen", response_model=ResumenBandeja)
def resumen(sesion: Session = Depends(obtener_sesion), _: Usuario = Depends(usuario_actual)) -> ResumenBandeja:
    por_estado = dict(sesion.execute(select(Consulta.estado, func.count()).group_by(Consulta.estado)).all())
    por_area = dict(
        sesion.execute(
            select(Consulta.area_asignada, func.count())
            .where(Consulta.area_asignada.is_not(None), Consulta.estado != EstadoConsulta.APROBADA.value)
            .group_by(Consulta.area_asignada)
        ).all()
    )
    vencidas = sesion.scalar(
        select(func.count()).where(
            Consulta.sla_vence_en < datetime.now(UTC), Consulta.estado != EstadoConsulta.APROBADA.value
        )
    )
    return ResumenBandeja(
        por_estado=por_estado,
        por_area=por_area,
        sla_vencidas=vencidas or 0,
        clasificador_activo=nombre_clasificador_activo(),
    )


@router.get("/precision", response_model=MetricasPrecision)
def precision(
    clasificador: str | None = Query(default=None, max_length=80, description="Filtra por clasificador"),
    sesion: Session = Depends(obtener_sesion),
    _: Usuario = Depends(requiere_supervisor),
) -> MetricasPrecision:
    return calcular_precision(sesion, clasificador)


@router.get("/uso-llm", response_model=MetricasUso)
def uso_llm(sesion: Session = Depends(obtener_sesion), _: Usuario = Depends(requiere_supervisor)) -> MetricasUso:
    return calcular_uso(sesion)
