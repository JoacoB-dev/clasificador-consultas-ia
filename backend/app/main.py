"""Aplicación FastAPI."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import auth, consultas, ingreso, metricas
from app.cola import conexion_redis
from app.config import obtener_configuracion
from app.db import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

config = obtener_configuracion()
app = FastAPI(
    title="Clasificador de consultas con IA",
    description="Proyecto de portfolio: clasifica consultas de clientes con un LLM y las deja para revisión humana.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origenes,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(consultas.router)
app.include_router(ingreso.router)
app.include_router(metricas.router)


@app.get("/api/salud", tags=["salud"])
def salud() -> dict:
    """Estado de la base, de Redis y qué clasificador está activo."""
    estado = {"api": "ok", "clasificador": metricas.nombre_clasificador_activo()}
    try:
        with engine.connect() as conexion:
            conexion.execute(text("select 1"))
        estado["base"] = "ok"
    except SQLAlchemyError:
        estado["base"] = "error"
    try:
        conexion_redis().ping()
        estado["redis"] = "ok"
    except RedisError:
        estado["redis"] = "error"
    return estado
