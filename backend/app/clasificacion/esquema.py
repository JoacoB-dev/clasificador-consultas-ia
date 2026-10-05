"""Esquema de salida estructurada que tiene que devolver cualquier clasificador.

El mismo modelo Pydantic se usa para:
- generar el JSON Schema que se le pasa a Claude (salida estructurada), y
- validar la respuesta antes de guardarla (si no valida, se reintenta).
"""

from dataclasses import dataclass
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.dominio import Categoria, Sentimiento, Urgencia


class DatosExtraidos(BaseModel):
    """Todos los campos son obligatorios pero aceptan null (así lo pide la salida estructurada estricta)."""

    model_config = ConfigDict(extra="forbid")

    numero_pedido: str | None = Field(description="Número de pedido en formato PED-123456 si aparece en el texto")
    producto: str | None = Field(description="Producto mencionado, tal como lo nombra el cliente")
    monto: float | None = Field(description="Monto en pesos mencionado (número, sin símbolo)")
    medio_pago: str | None = Field(description="Medio de pago mencionado (tarjeta, transferencia, etc.)")
    fecha_mencionada: str | None = Field(description="Fecha relevante mencionada, tal cual aparece")


class ResultadoClasificacion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    categoria: Categoria
    urgencia: Urgencia
    sentimiento: Sentimiento
    resumen: str = Field(min_length=1, max_length=400, description="Resumen de una o dos oraciones")
    datos_extraidos: DatosExtraidos
    borrador_respuesta: str = Field(min_length=1, max_length=3000, description="Borrador de respuesta al cliente")
    confianza: float = Field(ge=0, le=1, description="Confianza en la categoría elegida, entre 0 y 1")


@dataclass
class UsoRegistro:
    """Tokens y costo de una clasificación (vacío para el simulado)."""

    modelo: str
    tokens_entrada: int = 0
    tokens_salida: int = 0
    costo_usd: Decimal = Decimal("0")
    duracion_ms: int = 0
    intentos: int = 1


@dataclass
class SalidaClasificador:
    resultado: ResultadoClasificacion
    clasificador: str  # ej. "simulado-reglas" o "claude:claude-sonnet-5-5"
    uso: UsoRegistro | None = None


@dataclass
class ConsultaEntrada:
    """Lo mínimo que necesita un clasificador para trabajar."""

    asunto: str
    cuerpo: str
    remitente_nombre: str | None = None
    canal: str = "formulario"


class ErrorClasificacion(Exception):
    """La clasificación falló definitivamente (después de los reintentos)."""

    def __init__(self, mensaje: str, uso: UsoRegistro | None = None, reintentable: bool = True):
        super().__init__(mensaje)
        self.uso = uso
        self.reintentable = reintentable
