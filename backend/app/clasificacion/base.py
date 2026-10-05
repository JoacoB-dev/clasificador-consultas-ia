"""Interfaz común de los clasificadores."""

from typing import Protocol

from app.clasificacion.esquema import ConsultaEntrada, SalidaClasificador


class Clasificador(Protocol):
    nombre: str

    def clasificar(self, consulta: ConsultaEntrada) -> SalidaClasificador: ...
