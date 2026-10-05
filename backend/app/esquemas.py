"""Esquemas Pydantic de entrada y salida de la API."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.config import obtener_configuracion
from app.dominio import Canal, Categoria, EstadoConsulta, Rol, Urgencia

_MAX_CUERPO = obtener_configuracion().max_largo_cuerpo


# Validación de mail simple a propósito: email-validator rechaza dominios reservados
# como .local o .example, que justamente usamos en la demo.
EmailSimple = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]


def _limpiar(texto: str) -> str:
    return texto.strip()


# ---------- Autenticación ----------


class LoginEntrada(BaseModel):
    email: EmailSimple
    password: str = Field(min_length=1, max_length=200)


class UsuarioSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nombre: str
    rol: Rol


class TokenSalida(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioSalida


# ---------- Ingreso de consultas ----------


class ConsultaFormulario(BaseModel):
    """Lo que manda el formulario web público."""

    nombre: str | None = Field(default=None, max_length=150)
    email: EmailSimple
    asunto: str = Field(min_length=3, max_length=300)
    mensaje: str = Field(min_length=10, max_length=_MAX_CUERPO)

    @field_validator("asunto", "mensaje", "nombre", mode="before")
    @classmethod
    def _sacar_espacios(cls, valor: Any) -> Any:
        return _limpiar(valor) if isinstance(valor, str) else valor


class ConsultaImportada(BaseModel):
    """Formato de importación JSON (simula consultas que llegan por mail u otra integración)."""

    canal: Canal = Canal.EMAIL
    nombre: str | None = Field(default=None, max_length=150)
    email: EmailSimple
    asunto: str = Field(min_length=1, max_length=300)
    cuerpo: str = Field(min_length=1, max_length=_MAX_CUERPO)
    id_externo: str | None = Field(default=None, max_length=300)
    recibida_en: datetime | None = None


class IngresoSalida(BaseModel):
    id: int
    estado: EstadoConsulta
    encolada: bool
    duplicada: bool = False


class ResultadoImportacion(BaseModel):
    creadas: list[IngresoSalida]
    duplicadas: int
    errores: list[str]


# ---------- Bandeja y detalle ----------


class ConsultaResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    canal: str
    remitente_nombre: str | None
    remitente_email: str
    asunto: str
    recibida_en: datetime
    estado: str
    categoria: str | None
    urgencia: str | None
    sentimiento: str | None
    resumen: str | None
    area_asignada: str | None
    sla_vence_en: datetime | None
    sla_vencido: bool = False
    corregida: bool = False


class CorreccionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campo: str
    valor_anterior: str | None
    valor_nuevo: str
    usuario_id: int
    creada_en: datetime


class ConsultaDetalle(ConsultaResumen):
    cuerpo: str
    datos_extraidos: dict[str, Any] | None
    borrador_respuesta: str | None
    respuesta_final: str | None
    confianza: float | None
    categoria_modelo: str | None
    urgencia_modelo: str | None
    clasificador: str | None
    reglas_aplicadas: list[str] | None
    intentos: int
    error_detalle: str | None
    clasificada_en: datetime | None
    revisada_en: datetime | None
    aprobada_en: datetime | None
    aprobada_por_id: int | None
    correcciones: list[CorreccionSalida] = []


class PaginaConsultas(BaseModel):
    items: list[ConsultaResumen]
    total: int
    pagina: int
    tamanio: int


class ActualizarConsulta(BaseModel):
    """Edición desde el panel: borrador y/o corrección de categoría o urgencia."""

    borrador_respuesta: str | None = Field(default=None, min_length=1, max_length=5000)
    categoria: Categoria | None = None
    urgencia: Urgencia | None = None


class AprobarConsulta(BaseModel):
    respuesta_final: str | None = Field(default=None, min_length=1, max_length=5000)


# ---------- Métricas ----------


class PrecisionCategoria(BaseModel):
    categoria: str
    predichas: int  # veces que el modelo dijo esta categoría
    correctas: int  # de esas, cuántas confirmó el humano
    reales: int  # cuántas terminaron siendo de esta categoría
    precision: float | None
    recall: float | None


class CeldaMatriz(BaseModel):
    modelo: str
    real: str
    cantidad: int


class MetricasPrecision(BaseModel):
    total_revisadas: int
    correctas: int
    exactitud: float | None
    por_categoria: list[PrecisionCategoria]
    matriz_confusion: list[CeldaMatriz]
    clasificador: str | None = None


class UsoPorModelo(BaseModel):
    modelo: str
    llamadas: int
    fallidas: int
    tokens_entrada: int
    tokens_salida: int
    costo_usd: float
    duracion_promedio_ms: float


class MetricasUso(BaseModel):
    llamadas: int
    tokens_entrada: int
    tokens_salida: int
    costo_total_usd: float
    costo_promedio_usd: float | None
    por_modelo: list[UsoPorModelo]


class ResumenBandeja(BaseModel):
    por_estado: dict[str, int]
    por_area: dict[str, int]
    sla_vencidas: int
    clasificador_activo: str
