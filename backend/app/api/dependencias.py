"""Dependencias compartidas (la cola se puede reemplazar en los tests)."""

from app.cola import ColaConsultas, obtener_cola


def cola_consultas() -> ColaConsultas:
    return obtener_cola()
