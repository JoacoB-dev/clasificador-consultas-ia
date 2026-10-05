"""Configuración leída de variables de entorno (o de un archivo .env)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Base de datos y cola
    database_url: str = "postgresql+psycopg://consultas:consultas@localhost:54322/consultas_dev"
    redis_url: str = "redis://localhost:63792/0"
    nombre_cola: str = "consultas"

    # Seguridad (JWT para el panel)
    jwt_secreto: str = "cambiar-este-secreto-en-produccion"
    jwt_algoritmo: str = "HS256"
    jwt_minutos_expiracion: int = 8 * 60

    # CORS para el panel en desarrollo (Vite en 5174)
    cors_origenes: list[str] = ["http://localhost:5174", "http://127.0.0.1:5174"]

    # LLM: si no hay ANTHROPIC_API_KEY se usa el clasificador simulado (reglas)
    anthropic_api_key: str | None = None
    llm_modelo: str = "claude-sonnet-5-5"
    llm_timeout_segundos: float = 30.0
    llm_max_reintentos: int = 3
    llm_backoff_base_segundos: float = 1.0
    llm_max_tokens: int = 4000
    # Esfuerzo de razonamiento: para clasificar alcanza con "low"
    llm_esfuerzo: str = "low"
    # Fallback del lado del servidor si el modelo rechaza la consulta
    llm_fallback_servidor: bool = True
    # Forzar el simulado aunque haya clave (útil para demos y tests)
    forzar_clasificador_simulado: bool = False

    # Límites de entrada
    max_largo_cuerpo: int = Field(default=8000, description="Caracteres máximos del cuerpo de una consulta")

    @property
    def usa_llm_real(self) -> bool:
        return bool(self.anthropic_api_key) and not self.forzar_clasificador_simulado


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
