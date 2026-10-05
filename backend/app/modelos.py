"""Modelos ORM (SQLAlchemy 2, estilo tipado)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# JSONB en Postgres (JSON genérico en otros motores)
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(120))
    hash_password: Mapped[str] = mapped_column(String(200))
    rol: Mapped[str] = mapped_column(String(20))
    activo: Mapped[bool] = mapped_column(default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Consulta(Base):
    __tablename__ = "consultas"

    id: Mapped[int] = mapped_column(primary_key=True)
    canal: Mapped[str] = mapped_column(String(20))
    # Message-ID del mail original: evita importar dos veces el mismo correo
    id_externo: Mapped[str | None] = mapped_column(String(300), unique=True)
    remitente_nombre: Mapped[str | None] = mapped_column(String(150))
    remitente_email: Mapped[str] = mapped_column(String(200))
    asunto: Mapped[str] = mapped_column(String(300))
    cuerpo: Mapped[str] = mapped_column(Text)
    recibida_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    estado: Mapped[str] = mapped_column(String(20), index=True, default="pendiente")

    # Resultado de la clasificación (lo que quedó vigente, corregido o no)
    categoria: Mapped[str | None] = mapped_column(String(40), index=True)
    urgencia: Mapped[str | None] = mapped_column(String(20), index=True)
    sentimiento: Mapped[str | None] = mapped_column(String(20))
    resumen: Mapped[str | None] = mapped_column(Text)
    datos_extraidos: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    borrador_respuesta: Mapped[str | None] = mapped_column(Text)
    confianza: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))

    # Lo que dijo el modelo originalmente (para medir precisión)
    categoria_modelo: Mapped[str | None] = mapped_column(String(40))
    urgencia_modelo: Mapped[str | None] = mapped_column(String(20))
    clasificador: Mapped[str | None] = mapped_column(String(80))

    # Reglas de negocio
    area_asignada: Mapped[str | None] = mapped_column(String(60), index=True)
    sla_vence_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reglas_aplicadas: Mapped[list[str] | None] = mapped_column(JSONType)

    # Revisión humana
    respuesta_final: Mapped[str | None] = mapped_column(Text)
    revisada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aprobada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aprobada_por_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    # Procesamiento
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    error_detalle: Mapped[str | None] = mapped_column(Text)
    clasificada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    correcciones: Mapped[list["Correccion"]] = relationship(
        back_populates="consulta", order_by="Correccion.creada_en", cascade="all, delete-orphan"
    )
    aprobada_por: Mapped[Usuario | None] = relationship()


class Correccion(Base):
    """Cada vez que un humano corrige un campo que puso el modelo queda registrado acá."""

    __tablename__ = "correcciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    consulta_id: Mapped[int] = mapped_column(ForeignKey("consultas.id", ondelete="CASCADE"), index=True)
    campo: Mapped[str] = mapped_column(String(30))
    valor_anterior: Mapped[str | None] = mapped_column(String(60))
    valor_nuevo: Mapped[str] = mapped_column(String(60))
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    creada_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    consulta: Mapped[Consulta] = relationship(back_populates="correcciones")
    usuario: Mapped[Usuario] = relationship()


class UsoLLM(Base):
    """Registro de cada llamada al LLM: tokens, costo estimado y duración."""

    __tablename__ = "usos_llm"

    id: Mapped[int] = mapped_column(primary_key=True)
    consulta_id: Mapped[int | None] = mapped_column(ForeignKey("consultas.id", ondelete="SET NULL"), index=True)
    modelo: Mapped[str] = mapped_column(String(80))
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0)
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0)
    costo_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    duracion_ms: Mapped[int] = mapped_column(Integer, default=0)
    intentos: Mapped[int] = mapped_column(Integer, default=1)
    exito: Mapped[bool] = mapped_column(default=True)
    error: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
