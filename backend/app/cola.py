"""Cola de trabajos en Redis usando RQ.

Por qué RQ y no Celery o arq: el procesamiento es una sola tarea sincrónica
(clasificar una consulta), RQ solo necesita Redis, no tiene configuración extra
y el worker se levanta con un comando. Celery sería demasiado para esto y arq
obliga a que todo sea async (el SDK y SQLAlchemy los usamos sincrónicos).
"""

import logging
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue

from app.config import obtener_configuracion

log = logging.getLogger(__name__)

TAREA_PROCESAR = "app.tareas.procesar_consulta"


@lru_cache
def conexion_redis() -> Redis:
    return Redis.from_url(obtener_configuracion().redis_url)


class ColaConsultas:
    """Envoltorio chico sobre la cola de RQ (en los tests se reemplaza por uno falso)."""

    def __init__(self, cola: Queue):
        self.cola = cola

    def encolar(self, consulta_id: int) -> bool:
        """Encola el procesamiento. Devuelve False si Redis no está disponible:
        la consulta queda 'pendiente' y se puede reencolar más tarde."""
        try:
            self.cola.enqueue(TAREA_PROCESAR, consulta_id, job_timeout=180, result_ttl=3600)
            return True
        except RedisError as error:
            log.error("No se pudo encolar la consulta %s: %s", consulta_id, error)
            return False


def obtener_cola() -> ColaConsultas:
    config = obtener_configuracion()
    return ColaConsultas(Queue(config.nombre_cola, connection=conexion_redis()))
