import pytest

pytestmark = pytest.mark.integracion


def test_login_ok_devuelve_token_y_usuario(cliente, usuarios):
    r = cliente.post("/api/auth/login", json={"email": "Operador@Demo.local", "password": "demo1234"})
    assert r.status_code == 200
    assert r.json()["usuario"]["rol"] == "operador"


def test_login_con_password_incorrecta(cliente, usuarios):
    r = cliente.post("/api/auth/login", json={"email": "operador@demo.local", "password": "otra"})
    assert r.status_code == 401


def test_yo_requiere_token(cliente, usuarios, auth_supervisor):
    assert cliente.get("/api/auth/yo").status_code == 401
    assert cliente.get("/api/auth/yo", headers={"Authorization": "Bearer basura"}).status_code == 401
    r = cliente.get("/api/auth/yo", headers=auth_supervisor)
    assert r.json()["email"] == "supervisor@demo.local"


def test_operador_no_ve_metricas_de_supervisor(cliente, auth_operador, auth_supervisor):
    assert cliente.get("/api/metricas/precision", headers=auth_operador).status_code == 403
    assert cliente.get("/api/metricas/uso-llm", headers=auth_operador).status_code == 403
    assert cliente.get("/api/metricas/precision", headers=auth_supervisor).status_code == 200
