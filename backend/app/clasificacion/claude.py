"""Clasificador real usando la Claude API con el SDK oficial `anthropic`.

- Salida estructurada: se pasa el JSON Schema de `ResultadoClasificacion` en
  `output_config.format`, y además se valida la respuesta con Pydantic.
- Reintentos propios con backoff exponencial + jitter (el reintento del SDK se
  desactiva para no reintentar dos veces). También se reintenta si el JSON no valida.
- Timeout por request configurable.
- Se suman los tokens de todos los intentos y se estima el costo.
"""

import logging
import random
import time
from collections.abc import Callable
from typing import Any

import anthropic
from pydantic import ValidationError

from app.clasificacion.costos import estimar_costo
from app.clasificacion.esquema import (
    ConsultaEntrada,
    ErrorClasificacion,
    ResultadoClasificacion,
    SalidaClasificador,
    UsoRegistro,
)
from app.clasificacion.prompts import PROMPT_SISTEMA, armar_mensaje_usuario
from app.config import Configuracion

log = logging.getLogger(__name__)

# Beta del fallback del lado del servidor: si el modelo rechaza la consulta por
# políticas de seguridad, la API la reintenta con otro modelo dentro de la misma llamada.
BETA_FALLBACK = "server-side-fallback-2026-07-01"

# Códigos HTTP que vale la pena reintentar
ESTADOS_REINTENTABLES = {408, 409, 429, 500, 502, 503, 504, 529}


def _es_reintentable(error: Exception) -> bool:
    if isinstance(error, anthropic.APIConnectionError):  # incluye APITimeoutError
        return True
    if isinstance(error, anthropic.APIStatusError):
        return error.status_code in ESTADOS_REINTENTABLES or error.status_code >= 500
    return False


class ClasificadorClaude:
    def __init__(
        self,
        config: Configuracion,
        cliente: Any | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self.modelo = config.llm_modelo
        self.nombre = f"claude:{self.modelo}"
        self._dormir = dormir
        self._schema = anthropic.transform_schema(ResultadoClasificacion)
        # max_retries=0: los reintentos los maneja esta clase (con su propio log y conteo)
        self.cliente = cliente or anthropic.Anthropic(
            api_key=config.anthropic_api_key,
            timeout=config.llm_timeout_segundos,
            max_retries=0,
        )

    def _parametros(self, consulta: ConsultaEntrada) -> dict[str, Any]:
        parametros: dict[str, Any] = {
            "model": self.modelo,
            "max_tokens": self.config.llm_max_tokens,
            "system": PROMPT_SISTEMA,
            "messages": [{"role": "user", "content": armar_mensaje_usuario(consulta)}],
            "output_config": {
                "effort": self.config.llm_esfuerzo,
                "format": {"type": "json_schema", "schema": self._schema},
            },
        }
        if self.config.llm_fallback_servidor:
            parametros["betas"] = [BETA_FALLBACK]
            parametros["fallbacks"] = "default"
        return parametros

    def _espera(self, intento: int) -> float:
        base = self.config.llm_backoff_base_segundos * (2 ** (intento - 1))
        return min(base + random.uniform(0, base / 2), 30.0)

    def clasificar(self, consulta: ConsultaEntrada) -> SalidaClasificador:
        uso = UsoRegistro(modelo=self.modelo, intentos=0)
        inicio = time.monotonic()
        ultimo_error = "sin intentos"
        parametros = self._parametros(consulta)

        for intento in range(1, self.config.llm_max_reintentos + 1):
            uso.intentos = intento
            try:
                respuesta = self.cliente.beta.messages.create(**parametros)
            except anthropic.APIError as error:
                ultimo_error = f"{type(error).__name__}: {error}"
                if not _es_reintentable(error):
                    raise self._fallar(ultimo_error, uso, inicio, reintentable=False) from error
                log.warning("Intento %s/%s falló (%s)", intento, self.config.llm_max_reintentos, ultimo_error)
            else:
                self._sumar_uso(uso, respuesta)
                if respuesta.stop_reason == "refusal":
                    raise self._fallar("El modelo rechazó la consulta (refusal)", uso, inicio, reintentable=False)
                if respuesta.stop_reason == "max_tokens":
                    raise self._fallar("La respuesta se cortó por max_tokens", uso, inicio, reintentable=False)
                texto = next((b.text for b in respuesta.content if b.type == "text"), "")
                try:
                    resultado = ResultadoClasificacion.model_validate_json(texto)
                except ValidationError as error:
                    ultimo_error = f"JSON inválido: {error.error_count()} errores de validación"
                    log.warning("Intento %s: %s", intento, ultimo_error)
                else:
                    uso.duracion_ms = int((time.monotonic() - inicio) * 1000)
                    uso.costo_usd = estimar_costo(uso.modelo, uso.tokens_entrada, uso.tokens_salida)
                    return SalidaClasificador(resultado=resultado, clasificador=self.nombre, uso=uso)

            if intento < self.config.llm_max_reintentos:
                self._dormir(self._espera(intento))

        raise self._fallar(f"Se agotaron los reintentos. Último error: {ultimo_error}", uso, inicio)

    def _sumar_uso(self, uso: UsoRegistro, respuesta: Any) -> None:
        uso.tokens_entrada += respuesta.usage.input_tokens or 0
        uso.tokens_salida += respuesta.usage.output_tokens or 0
        # Con fallback la respuesta puede venir de otro modelo: el costo se calcula con ese
        if getattr(respuesta, "model", None):
            uso.modelo = respuesta.model

    def _fallar(self, mensaje: str, uso: UsoRegistro, inicio: float, reintentable: bool = True) -> ErrorClasificacion:
        uso.duracion_ms = int((time.monotonic() - inicio) * 1000)
        uso.costo_usd = estimar_costo(uso.modelo, uso.tokens_entrada, uso.tokens_salida)
        return ErrorClasificacion(mensaje, uso=uso, reintentable=reintentable)
