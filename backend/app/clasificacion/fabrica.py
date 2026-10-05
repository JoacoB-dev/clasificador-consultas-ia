"""Elige qué clasificador usar según la configuración."""

from app.clasificacion.base import Clasificador
from app.clasificacion.simulado import ClasificadorSimulado
from app.config import Configuracion


def obtener_clasificador(config: Configuracion) -> Clasificador:
    """Con ANTHROPIC_API_KEY usa Claude; sin clave (o forzado) usa el simulado por reglas."""
    if config.usa_llm_real:
        # Import diferido: el simulado no necesita cargar el SDK
        from app.clasificacion.claude import ClasificadorClaude

        return ClasificadorClaude(config)
    return ClasificadorSimulado()
