"""Reglas de negocio que se aplican DESPUÉS de la clasificación.

El modelo propone; estas reglas (deterministas y fáciles de auditar) deciden el área
y el vencimiento del SLA. Así una decisión de negocio no depende del humor del LLM.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.clasificacion.esquema import ResultadoClasificacion
from app.clasificacion.simulado import normalizar
from app.dominio import ORDEN_URGENCIA, Categoria, Sentimiento, Urgencia

AREA_POR_CATEGORIA: dict[Categoria, str] = {
    Categoria.ENVIO: "Logística",
    Categoria.PRODUCTO_DEFECTUOSO: "Postventa",
    Categoria.DEVOLUCION: "Postventa",
    Categoria.FACTURACION: "Administración",
    Categoria.CONSULTA_PRODUCTO: "Ventas",
    Categoria.CUENTA: "Atención al cliente",
    Categoria.OTRO: "Atención al cliente",
}
AREA_ESCALADO = "Supervisión"

HORAS_SLA: dict[Urgencia, int] = {
    Urgencia.CRITICA: 4,
    Urgencia.ALTA: 8,
    Urgencia.MEDIA: 24,
    Urgencia.BAJA: 72,
}

PALABRAS_LEGALES = ["defensa del consumidor", "denuncia", "abogado", "carta documento"]
MONTO_ALTO = 500_000  # pesos


@dataclass
class Asignacion:
    area: str
    urgencia: Urgencia
    sla_vence_en: datetime
    reglas_aplicadas: list[str]


def _maxima(a: Urgencia, b: Urgencia) -> Urgencia:
    return max(a, b, key=ORDEN_URGENCIA.index)


def aplicar_reglas(resultado: ResultadoClasificacion, texto: str, recibida_en: datetime) -> Asignacion:
    reglas: list[str] = []
    urgencia = resultado.urgencia
    area = AREA_POR_CATEGORIA[resultado.categoria]
    reglas.append(f"Área por categoría '{resultado.categoria.value}': {area}")

    texto_norm = normalizar(texto)
    if any(p in texto_norm for p in PALABRAS_LEGALES):
        urgencia = Urgencia.CRITICA
        area = AREA_ESCALADO
        reglas.append("Mención legal (denuncia / Defensa del Consumidor): escala a Supervisión con urgencia crítica")

    if resultado.sentimiento == Sentimiento.NEGATIVO and urgencia == Urgencia.BAJA:
        urgencia = Urgencia.MEDIA
        reglas.append("Cliente con sentimiento negativo: la urgencia baja sube a media")

    monto = resultado.datos_extraidos.monto
    if resultado.categoria == Categoria.FACTURACION and monto is not None and monto >= MONTO_ALTO:
        nueva = _maxima(urgencia, Urgencia.ALTA)
        if nueva != urgencia:
            urgencia = nueva
            reglas.append(f"Facturación con monto ≥ ${MONTO_ALTO:,}".replace(",", ".") + ": urgencia al menos alta")

    horas = HORAS_SLA[urgencia]
    reglas.append(f"SLA por urgencia '{urgencia.value}': {horas} h")
    return Asignacion(
        area=area,
        urgencia=urgencia,
        sla_vence_en=recibida_en + timedelta(hours=horas),
        reglas_aplicadas=reglas,
    )
