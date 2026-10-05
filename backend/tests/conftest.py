"""Fixtures compartidas.

Los tests unitarios no tocan la base. Los de integración (marcados `integracion`)
usan PostgreSQL y Redis reales: por defecto la base `consultas_test` y la DB 15 de Redis.
"""

import os

# Hay que definir el entorno ANTES de importar la app (la configuración se cachea)
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://consultas:consultas@localhost:54322/consultas_test"
)
os.environ["REDIS_URL"] = os.environ.get("TEST_REDIS_URL", "redis://localhost:63792/15")
os.environ["ANTHROPIC_API_KEY"] = ""  # los tests nunca llaman a la API real
os.environ["NOMBRE_COLA"] = "consultas-test"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.api.dependencias import cola_consultas  # noqa: E402
from app.db import SesionLocal, engine  # noqa: E402
from app.dominio import Rol  # noqa: E402
from app.main import app  # noqa: E402
from app.modelos import Usuario  # noqa: E402
from app.seguridad import hashear_password  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ColaFalsa:
    """Reemplaza a Redis en los tests de API: solo anota qué se encoló."""

    def __init__(self, disponible: bool = True):
        self.encoladas: list[int] = []
        self.disponible = disponible

    def encolar(self, consulta_id: int) -> bool:
        if not self.disponible:
            return False
        self.encoladas.append(consulta_id)
        return True


@pytest.fixture(scope="session")
def base_migrada():
    """Recrea el esquema de la base de test corriendo las migraciones de Alembic."""
    with engine.begin() as conexion:
        conexion.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
    configuracion = Config(os.path.join(RAIZ, "alembic.ini"))
    configuracion.set_main_option("script_location", os.path.join(RAIZ, "alembic"))
    command.upgrade(configuracion, "head")
    yield


@pytest.fixture
def sesion(base_migrada):
    with engine.begin() as conexion:
        conexion.execute(text("TRUNCATE usos_llm, correcciones, consultas, usuarios RESTART IDENTITY CASCADE"))
    with SesionLocal() as s:
        yield s


@pytest.fixture
def usuarios(sesion):
    creados = {}
    for email, nombre, rol in [
        ("supervisor@demo.local", "Sabrina Supervisora", Rol.SUPERVISOR),
        ("operador@demo.local", "Omar Operador", Rol.OPERADOR),
    ]:
        u = Usuario(email=email, nombre=nombre, rol=rol.value, hash_password=hashear_password("demo1234"))
        sesion.add(u)
        creados[rol.value] = u
    sesion.commit()
    return creados


@pytest.fixture
def cola():
    return ColaFalsa()


@pytest.fixture
def cliente(sesion, cola):
    app.dependency_overrides[cola_consultas] = lambda: cola
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _token(cliente: TestClient, email: str) -> dict[str, str]:
    r = cliente.post("/api/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth_operador(cliente, usuarios):
    return _token(cliente, "operador@demo.local")


@pytest.fixture
def auth_supervisor(cliente, usuarios):
    return _token(cliente, "supervisor@demo.local")
