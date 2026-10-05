"""Lógica de aplicación compartida entre los routers (crear, corregir, aprobar, métricas)."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cola import ColaConsultas
from app.dominio import Categoria, EstadoConsulta, Urgencia
from app.esquemas import (
    CeldaMatriz,
    ConsultaImportada,
    IngresoSalida,
    MetricasPrecision,
    MetricasUso,
    PrecisionCategoria,
    UsoPorModelo,
)
from app.modelos import Consulta, Correccion, UsoLLM, Usuario
from app.reglas_negocio import AREA_ESCALADO, AREA_POR_CATEGORIA, HORAS_SLA


class ErrorNegocio(Exception):
    """Operación inválida para el estado actual (se traduce a 409)."""


def crear_consulta(sesion: Session, datos: ConsultaImportada, cola: ColaConsultas) -> IngresoSalida:
    """Guarda la consulta y la encola. Si el mail ya se importó (mismo Message-ID) no la duplica."""
    if datos.id_externo:
        existente = sesion.scalar(select(Consulta).where(Consulta.id_externo == datos.id_externo))
        if existente:
            return IngresoSalida(id=existente.id, estado=existente.estado, encolada=False, duplicada=True)

    consulta = Consulta(
        canal=datos.canal.value,
        id_externo=datos.id_externo,
        remitente_nombre=datos.nombre,
        remitente_email=str(datos.email),
        asunto=datos.asunto,
        cuerpo=datos.cuerpo,
        estado=EstadoConsulta.PENDIENTE.value,
    )
    if datos.recibida_en:
        consulta.recibida_en = datos.recibida_en
    sesion.add(consulta)
    sesion.commit()
    encolada = cola.encolar(consulta.id)
    return IngresoSalida(id=consulta.id, estado=consulta.estado, encolada=encolada)


def _registrar_correccion(sesion: Session, consulta: Consulta, campo: str, nuevo: str, usuario: Usuario) -> None:
    sesion.add(
        Correccion(
            consulta_id=consulta.id,
            campo=campo,
            valor_anterior=getattr(consulta, campo),
            valor_nuevo=nuevo,
            usuario_id=usuario.id,
        )
    )


def actualizar_consulta(
    sesion: Session,
    consulta: Consulta,
    usuario: Usuario,
    borrador: str | None,
    categoria: Categoria | None,
    urgencia: Urgencia | None,
) -> Consulta:
    if consulta.estado not in (EstadoConsulta.CLASIFICADA, EstadoConsulta.APROBADA):
        raise ErrorNegocio("Solo se pueden editar consultas ya clasificadas")
    if consulta.estado == EstadoConsulta.APROBADA:
        raise ErrorNegocio("La consulta ya fue aprobada; no se puede modificar")

    ahora = datetime.now(UTC)
    reglas = list(consulta.reglas_aplicadas or [])

    if borrador is not None:
        consulta.borrador_respuesta = borrador

    if categoria is not None and categoria.value != consulta.categoria:
        _registrar_correccion(sesion, consulta, "categoria", categoria.value, usuario)
        consulta.categoria = categoria.value
        # Si fue escalada a Supervisión se mantiene ahí; si no, el área sigue a la categoría
        if consulta.area_asignada != AREA_ESCALADO:
            consulta.area_asignada = AREA_POR_CATEGORIA[categoria]
        reglas.append(f"Corrección manual de categoría a '{categoria.value}' por {usuario.nombre}")
        consulta.revisada_en = ahora

    if urgencia is not None and urgencia.value != consulta.urgencia:
        _registrar_correccion(sesion, consulta, "urgencia", urgencia.value, usuario)
        consulta.urgencia = urgencia.value
        consulta.sla_vence_en = consulta.recibida_en + timedelta(hours=HORAS_SLA[urgencia])
        reglas.append(f"Corrección manual de urgencia a '{urgencia.value}': SLA {HORAS_SLA[urgencia]} h")

    consulta.reglas_aplicadas = reglas
    sesion.commit()
    sesion.refresh(consulta)
    return consulta


def aprobar_consulta(sesion: Session, consulta: Consulta, usuario: Usuario, respuesta: str | None) -> Consulta:
    if consulta.estado != EstadoConsulta.CLASIFICADA:
        raise ErrorNegocio(f"No se puede aprobar una consulta en estado '{consulta.estado}'")
    texto = respuesta or consulta.borrador_respuesta
    if not texto:
        raise ErrorNegocio("No hay respuesta para aprobar")
    ahora = datetime.now(UTC)
    consulta.respuesta_final = texto
    consulta.borrador_respuesta = texto
    consulta.estado = EstadoConsulta.APROBADA.value
    consulta.aprobada_en = ahora
    consulta.aprobada_por_id = usuario.id
    # Aprobar implica que el humano validó la categoría (corregida o no)
    consulta.revisada_en = consulta.revisada_en or ahora
    sesion.commit()
    sesion.refresh(consulta)
    return consulta


def calcular_precision(sesion: Session, clasificador: str | None = None) -> MetricasPrecision:
    """Precisión del modelo por categoría usando las consultas revisadas por humanos.

    precision(C) = de las que el modelo dijo C, cuántas eran C.
    recall(C)    = de las que eran C, cuántas detectó el modelo.
    """
    consulta_sql = select(Consulta.categoria_modelo, Consulta.categoria).where(
        Consulta.revisada_en.is_not(None), Consulta.categoria_modelo.is_not(None)
    )
    if clasificador:
        consulta_sql = consulta_sql.where(Consulta.clasificador == clasificador)
    pares = [(m, r) for m, r in sesion.execute(consulta_sql).all()]

    matriz = Counter(pares)
    predichas = Counter(m for m, _ in pares)
    reales = Counter(r for _, r in pares)
    correctas_total = sum(c for (m, r), c in matriz.items() if m == r)

    por_categoria = []
    for cat in Categoria:
        c = cat.value
        ok = matriz.get((c, c), 0)
        por_categoria.append(
            PrecisionCategoria(
                categoria=c,
                predichas=predichas[c],
                correctas=ok,
                reales=reales[c],
                precision=round(ok / predichas[c], 3) if predichas[c] else None,
                recall=round(ok / reales[c], 3) if reales[c] else None,
            )
        )
    return MetricasPrecision(
        total_revisadas=len(pares),
        correctas=correctas_total,
        exactitud=round(correctas_total / len(pares), 3) if pares else None,
        por_categoria=por_categoria,
        matriz_confusion=[CeldaMatriz(modelo=m, real=r, cantidad=c) for (m, r), c in sorted(matriz.items())],
        clasificador=clasificador,
    )


def calcular_uso(sesion: Session) -> MetricasUso:
    filas = sesion.execute(
        select(
            UsoLLM.modelo,
            func.count(UsoLLM.id),
            func.count(UsoLLM.id).filter(UsoLLM.exito.is_(False)),
            func.coalesce(func.sum(UsoLLM.tokens_entrada), 0),
            func.coalesce(func.sum(UsoLLM.tokens_salida), 0),
            func.coalesce(func.sum(UsoLLM.costo_usd), 0),
            func.coalesce(func.avg(UsoLLM.duracion_ms), 0),
        ).group_by(UsoLLM.modelo)
    ).all()
    por_modelo = [
        UsoPorModelo(
            modelo=modelo,
            llamadas=llamadas,
            fallidas=fallidas,
            tokens_entrada=int(te),
            tokens_salida=int(ts),
            costo_usd=float(costo),
            duracion_promedio_ms=round(float(dur), 1),
        )
        for modelo, llamadas, fallidas, te, ts, costo, dur in filas
    ]
    llamadas = sum(m.llamadas for m in por_modelo)
    costo_total = round(sum(m.costo_usd for m in por_modelo), 6)
    return MetricasUso(
        llamadas=llamadas,
        tokens_entrada=sum(m.tokens_entrada for m in por_modelo),
        tokens_salida=sum(m.tokens_salida for m in por_modelo),
        costo_total_usd=costo_total,
        costo_promedio_usd=round(costo_total / llamadas, 6) if llamadas else None,
        por_modelo=por_modelo,
    )
