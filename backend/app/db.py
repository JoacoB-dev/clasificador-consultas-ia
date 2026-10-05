"""Motor de SQLAlchemy y sesión por request."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import obtener_configuracion


class Base(DeclarativeBase):
    pass


_config = obtener_configuracion()
engine = create_engine(_config.database_url, pool_pre_ping=True)
SesionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def obtener_sesion() -> Iterator[Session]:
    """Dependencia de FastAPI: abre una sesión y la cierra al terminar el request."""
    sesion = SesionLocal()
    try:
        yield sesion
    finally:
        sesion.close()
