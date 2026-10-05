from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.dependencias import cola_consultas
from app.cola import ColaConsultas
from app.db import obtener_sesion
from app.dominio import Canal, Categoria, EstadoConsulta, Urgencia
from app.esquemas import (
    ActualizarConsulta,
    AprobarConsulta,
    ConsultaDetalle,
    ConsultaFormulario,
    ConsultaImportada,
    ConsultaResumen,
    IngresoSalida,
    PaginaConsultas,
)
from app.modelos import Consulta, Usuario
from app.seguridad import requiere_supervisor, usuario_actual
from app.servicios import ErrorNegocio, actualizar_consulta, aprobar_consulta, crear_consulta

router = APIRouter(prefix="/api/consultas", tags=["consultas"])


def _sla_vencido(c: Consulta, ahora: datetime) -> bool:
    return bool(c.sla_vence_en and c.estado != EstadoConsulta.APROBADA and c.sla_vence_en < ahora)


def _resumen(c: Consulta, ahora: datetime) -> ConsultaResumen:
    r = ConsultaResumen.model_validate(c)
    r.sla_vencido = _sla_vencido(c, ahora)
    r.corregida = bool(c.categoria_modelo and c.categoria != c.categoria_modelo)
    return r


def _detalle(c: Consulta) -> ConsultaDetalle:
    ahora = datetime.now(UTC)
    d = ConsultaDetalle.model_validate(c)
    d.sla_vencido = _sla_vencido(c, ahora)
    d.corregida = bool(c.categoria_modelo and c.categoria != c.categoria_modelo)
    return d


def _obtener(sesion: Session, consulta_id: int) -> Consulta:
    consulta = sesion.scalar(
        select(Consulta).options(selectinload(Consulta.correcciones)).where(Consulta.id == consulta_id)
    )
    if consulta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta no encontrada")
    return consulta


@router.post("/formulario", response_model=IngresoSalida, status_code=status.HTTP_201_CREATED)
def recibir_formulario(
    datos: ConsultaFormulario,
    sesion: Session = Depends(obtener_sesion),
    cola: ColaConsultas = Depends(cola_consultas),
) -> IngresoSalida:
    """Endpoint público que usa el formulario de contacto de la web."""
    importada = ConsultaImportada(
        canal=Canal.FORMULARIO, nombre=datos.nombre, email=datos.email, asunto=datos.asunto, cuerpo=datos.mensaje
    )
    return crear_consulta(sesion, importada, cola)


@router.get("", response_model=PaginaConsultas)
def listar(
    estado: EstadoConsulta | None = None,
    categoria: Categoria | None = None,
    urgencia: Urgencia | None = None,
    area: str | None = Query(default=None, max_length=60),
    canal: Canal | None = None,
    q: str | None = Query(default=None, max_length=100, description="Busca en asunto, cuerpo y remitente"),
    sla_vencido: bool | None = None,
    pagina: int = Query(default=1, ge=1),
    tamanio: int = Query(default=20, ge=1, le=100),
    sesion: Session = Depends(obtener_sesion),
    _: Usuario = Depends(usuario_actual),
) -> PaginaConsultas:
    ahora = datetime.now(UTC)
    filtros = []
    if estado:
        filtros.append(Consulta.estado == estado.value)
    if categoria:
        filtros.append(Consulta.categoria == categoria.value)
    if urgencia:
        filtros.append(Consulta.urgencia == urgencia.value)
    if area:
        filtros.append(Consulta.area_asignada == area)
    if canal:
        filtros.append(Consulta.canal == canal.value)
    if q:
        patron = f"%{q}%"
        filtros.append(
            or_(
                Consulta.asunto.ilike(patron),
                Consulta.cuerpo.ilike(patron),
                Consulta.remitente_email.ilike(patron),
                Consulta.remitente_nombre.ilike(patron),
            )
        )
    if sla_vencido is True:
        filtros += [Consulta.sla_vence_en < ahora, Consulta.estado != EstadoConsulta.APROBADA.value]
    elif sla_vencido is False:
        filtros.append(or_(Consulta.sla_vence_en.is_(None), Consulta.sla_vence_en >= ahora))

    total = sesion.scalar(select(func.count(Consulta.id)).where(*filtros)) or 0
    # Primero lo abierto que vence antes; las aprobadas al final y las sin SLA por fecha de llegada
    ya_aprobada = case((Consulta.estado == EstadoConsulta.APROBADA.value, 1), else_=0)
    filas = sesion.scalars(
        select(Consulta)
        .where(*filtros)
        .order_by(ya_aprobada, Consulta.sla_vence_en.asc().nulls_last(), Consulta.recibida_en.desc())
        .offset((pagina - 1) * tamanio)
        .limit(tamanio)
    ).all()
    return PaginaConsultas(items=[_resumen(c, ahora) for c in filas], total=total, pagina=pagina, tamanio=tamanio)


@router.get("/{consulta_id}", response_model=ConsultaDetalle)
def detalle(
    consulta_id: int, sesion: Session = Depends(obtener_sesion), _: Usuario = Depends(usuario_actual)
) -> ConsultaDetalle:
    return _detalle(_obtener(sesion, consulta_id))


@router.patch("/{consulta_id}", response_model=ConsultaDetalle)
def actualizar(
    consulta_id: int,
    datos: ActualizarConsulta,
    sesion: Session = Depends(obtener_sesion),
    usuario: Usuario = Depends(usuario_actual),
) -> ConsultaDetalle:
    consulta = _obtener(sesion, consulta_id)
    try:
        consulta = actualizar_consulta(
            sesion, consulta, usuario, datos.borrador_respuesta, datos.categoria, datos.urgencia
        )
    except ErrorNegocio as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _detalle(_obtener(sesion, consulta.id))


@router.post("/{consulta_id}/aprobar", response_model=ConsultaDetalle)
def aprobar(
    consulta_id: int,
    datos: AprobarConsulta,
    sesion: Session = Depends(obtener_sesion),
    usuario: Usuario = Depends(usuario_actual),
) -> ConsultaDetalle:
    consulta = _obtener(sesion, consulta_id)
    try:
        aprobar_consulta(sesion, consulta, usuario, datos.respuesta_final)
    except ErrorNegocio as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _detalle(_obtener(sesion, consulta_id))


@router.post("/{consulta_id}/reprocesar", response_model=IngresoSalida)
def reprocesar(
    consulta_id: int,
    sesion: Session = Depends(obtener_sesion),
    cola: ColaConsultas = Depends(cola_consultas),
    _: Usuario = Depends(usuario_actual),
) -> IngresoSalida:
    """Vuelve a mandar la consulta al worker (por ejemplo, si quedó en error)."""
    consulta = _obtener(sesion, consulta_id)
    if consulta.estado == EstadoConsulta.APROBADA:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La consulta ya fue aprobada")
    if consulta.estado == EstadoConsulta.EN_PROCESO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La consulta se está procesando")
    consulta.estado = EstadoConsulta.PENDIENTE.value
    sesion.commit()
    return IngresoSalida(id=consulta.id, estado=consulta.estado, encolada=cola.encolar(consulta.id))


@router.post("/reencolar-pendientes", response_model=list[IngresoSalida])
def reencolar_pendientes(
    sesion: Session = Depends(obtener_sesion),
    cola: ColaConsultas = Depends(cola_consultas),
    _: Usuario = Depends(requiere_supervisor),
) -> list[IngresoSalida]:
    """Para cuando Redis estuvo caído: vuelve a encolar todo lo que quedó pendiente."""
    pendientes = sesion.scalars(select(Consulta).where(Consulta.estado == EstadoConsulta.PENDIENTE.value)).all()
    return [IngresoSalida(id=c.id, estado=c.estado, encolada=cola.encolar(c.id)) for c in pendientes]
