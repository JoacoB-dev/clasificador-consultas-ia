"""Flujo completo contra PostgreSQL real: ingreso -> worker -> revisión -> métricas."""

from pathlib import Path

import pytest

from app.clasificacion.simulado import ClasificadorSimulado
from app.modelos import Consulta, Correccion, UsoLLM
from app.tareas import procesar_en_sesion

pytestmark = pytest.mark.integracion

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos" / "emails"
FORMULARIO = {
    "nombre": "Marcela Ríos",
    "email": "marcela@ejemplo.com",
    "asunto": "Pedido sin novedades",
    "mensaje": "Hola, el pedido 104233 todavía no llegó y el seguimiento no cambia.",
}


def crear_y_procesar(cliente, sesion, **cambios) -> int:
    r = cliente.post("/api/consultas/formulario", json=FORMULARIO | cambios)
    assert r.status_code == 201, r.text
    consulta_id = r.json()["id"]
    procesar_en_sesion(sesion, consulta_id, ClasificadorSimulado())
    return consulta_id


def test_formulario_publico_guarda_y_encola(cliente, sesion, cola):
    r = cliente.post("/api/consultas/formulario", json=FORMULARIO)
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["estado"] == "pendiente" and cuerpo["encolada"] is True
    assert cola.encoladas == [cuerpo["id"]]
    assert sesion.get(Consulta, cuerpo["id"]).canal == "formulario"


@pytest.mark.parametrize(
    "cambio",
    [{"email": "no-es-un-mail"}, {"mensaje": "corto"}, {"asunto": ""}, {"mensaje": "x" * 9000}],
)
def test_formulario_valida_datos(cliente, cambio):
    assert cliente.post("/api/consultas/formulario", json=FORMULARIO | cambio).status_code == 422


def test_si_redis_no_esta_la_consulta_queda_pendiente(cliente, cola):
    cola.disponible = False
    r = cliente.post("/api/consultas/formulario", json=FORMULARIO)
    assert r.status_code == 201 and r.json()["encolada"] is False


def test_worker_clasifica_y_aplica_reglas(cliente, sesion, auth_operador):
    consulta_id = crear_y_procesar(cliente, sesion)
    r = cliente.get(f"/api/consultas/{consulta_id}", headers=auth_operador)
    d = r.json()
    assert d["estado"] == "clasificada"
    assert d["categoria"] == d["categoria_modelo"] == "envio"
    assert d["area_asignada"] == "Logística"
    assert d["datos_extraidos"]["numero_pedido"] == "PED-104233"
    assert d["sla_vence_en"] is not None
    assert d["clasificador"] == "simulado-reglas"
    assert any("SLA" in regla for regla in d["reglas_aplicadas"])


def test_bandeja_con_filtros_y_busqueda(cliente, sesion, auth_operador):
    crear_y_procesar(cliente, sesion)
    crear_y_procesar(cliente, sesion, asunto="Factura A", mensaje="Necesito la factura A del pedido 104620, CUIT 30.")
    cliente.post("/api/consultas/formulario", json=FORMULARIO | {"asunto": "Sin procesar"})

    todas = cliente.get("/api/consultas", headers=auth_operador).json()
    assert todas["total"] == 3

    r = cliente.get("/api/consultas", params={"categoria": "facturacion"}, headers=auth_operador).json()
    assert [c["asunto"] for c in r["items"]] == ["Factura A"]
    assert r["items"][0]["area_asignada"] == "Administración"

    assert cliente.get("/api/consultas", params={"estado": "pendiente"}, headers=auth_operador).json()["total"] == 1
    assert cliente.get("/api/consultas", params={"q": "cuit"}, headers=auth_operador).json()["total"] == 1
    assert cliente.get("/api/consultas", params={"area": "Logística"}, headers=auth_operador).json()["total"] == 1
    assert cliente.get("/api/consultas", params={"tamanio": 1}, headers=auth_operador).json()["items"].__len__() == 1
    assert cliente.get("/api/consultas", params={"categoria": "inventada"}, headers=auth_operador).status_code == 422
    assert cliente.get("/api/consultas").status_code == 401


def test_detalle_inexistente_da_404(cliente, auth_operador):
    assert cliente.get("/api/consultas/999", headers=auth_operador).status_code == 404


def test_corregir_categoria_guarda_correccion_y_reasigna_area(cliente, sesion, auth_operador, usuarios):
    consulta_id = crear_y_procesar(cliente, sesion)
    r = cliente.patch(
        f"/api/consultas/{consulta_id}",
        json={"categoria": "producto_defectuoso", "urgencia": "alta", "borrador_respuesta": "Hola, nuevo texto."},
        headers=auth_operador,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["categoria"] == "producto_defectuoso" and d["categoria_modelo"] == "envio"
    assert d["area_asignada"] == "Postventa"
    assert d["urgencia"] == "alta"
    assert d["borrador_respuesta"] == "Hola, nuevo texto."
    assert d["corregida"] is True and d["revisada_en"] is not None
    campos = sorted(c["campo"] for c in d["correcciones"])
    assert campos == ["categoria", "urgencia"]
    correccion = sesion.query(Correccion).filter_by(campo="categoria").one()
    assert correccion.valor_anterior == "envio" and correccion.usuario_id == usuarios["operador"].id


def test_no_se_edita_una_consulta_pendiente(cliente, auth_operador):
    consulta_id = cliente.post("/api/consultas/formulario", json=FORMULARIO).json()["id"]
    r = cliente.patch(f"/api/consultas/{consulta_id}", json={"categoria": "otro"}, headers=auth_operador)
    assert r.status_code == 409


def test_aprobar_y_no_aprobar_dos_veces(cliente, sesion, auth_operador, usuarios):
    consulta_id = crear_y_procesar(cliente, sesion)
    r = cliente.post(f"/api/consultas/{consulta_id}/aprobar", json={}, headers=auth_operador)
    assert r.status_code == 200
    d = r.json()
    assert d["estado"] == "aprobada"
    assert d["respuesta_final"] == d["borrador_respuesta"]
    assert d["aprobada_por_id"] == usuarios["operador"].id
    assert cliente.post(f"/api/consultas/{consulta_id}/aprobar", json={}, headers=auth_operador).status_code == 409
    assert (
        cliente.patch(f"/api/consultas/{consulta_id}", json={"urgencia": "baja"}, headers=auth_operador).status_code
        == 409
    )


def test_aprobar_con_texto_editado(cliente, sesion, auth_operador):
    consulta_id = crear_y_procesar(cliente, sesion)
    r = cliente.post(
        f"/api/consultas/{consulta_id}/aprobar", json={"respuesta_final": "Texto final revisado"}, headers=auth_operador
    )
    assert r.json()["respuesta_final"] == "Texto final revisado"


def test_reprocesar_vuelve_a_encolar(cliente, sesion, cola, auth_operador):
    consulta_id = crear_y_procesar(cliente, sesion)
    r = cliente.post(f"/api/consultas/{consulta_id}/reprocesar", headers=auth_operador)
    assert r.status_code == 200 and r.json()["estado"] == "pendiente"
    assert cola.encoladas.count(consulta_id) == 2


def test_reencolar_pendientes_solo_supervisor(cliente, cola, auth_operador, auth_supervisor):
    cola.disponible = False
    cliente.post("/api/consultas/formulario", json=FORMULARIO)
    cola.disponible = True
    assert cliente.post("/api/consultas/reencolar-pendientes", headers=auth_operador).status_code == 403
    r = cliente.post("/api/consultas/reencolar-pendientes", headers=auth_supervisor)
    assert len(r.json()) == 1 and r.json()[0]["encolada"] is True


def test_metrica_de_precision_por_categoria(cliente, sesion, auth_operador, auth_supervisor):
    # Tres consultas que el simulado clasifica como 'envio'
    ids = [crear_y_procesar(cliente, sesion) for _ in range(3)]
    # Una se aprueba tal cual (acierto), otra se corrige (error), la tercera queda sin revisar
    cliente.post(f"/api/consultas/{ids[0]}/aprobar", json={}, headers=auth_operador)
    cliente.patch(f"/api/consultas/{ids[1]}", json={"categoria": "devolucion"}, headers=auth_operador)

    m = cliente.get("/api/metricas/precision", headers=auth_supervisor).json()
    assert m["total_revisadas"] == 2 and m["correctas"] == 1 and m["exactitud"] == 0.5
    envio = next(c for c in m["por_categoria"] if c["categoria"] == "envio")
    assert envio == {
        "categoria": "envio",
        "predichas": 2,
        "correctas": 1,
        "reales": 1,
        "precision": 0.5,
        "recall": 1.0,
    }
    devolucion = next(c for c in m["por_categoria"] if c["categoria"] == "devolucion")
    assert devolucion["recall"] == 0.0 and devolucion["precision"] is None
    assert {"modelo": "envio", "real": "devolucion", "cantidad": 1} in m["matriz_confusion"]

    filtrada = cliente.get(
        "/api/metricas/precision", params={"clasificador": "claude:x"}, headers=auth_supervisor
    ).json()
    assert filtrada["total_revisadas"] == 0 and filtrada["exactitud"] is None


def test_metrica_de_uso_llm(cliente, sesion, auth_supervisor):
    sesion.add_all(
        [
            UsoLLM(
                modelo="claude-sonnet-5-5", tokens_entrada=1000, tokens_salida=200, costo_usd=0.004, duracion_ms=900
            ),
            UsoLLM(modelo="claude-sonnet-5-5", tokens_entrada=500, tokens_salida=0, costo_usd=0.001, exito=False),
        ]
    )
    sesion.commit()
    m = cliente.get("/api/metricas/uso-llm", headers=auth_supervisor).json()
    assert m["llamadas"] == 2 and m["tokens_entrada"] == 1500
    assert m["costo_total_usd"] == pytest.approx(0.005)
    assert m["por_modelo"][0]["fallidas"] == 1


def test_resumen_de_bandeja(cliente, sesion, auth_operador):
    crear_y_procesar(cliente, sesion)
    r = cliente.get("/api/metricas/resumen", headers=auth_operador).json()
    assert r["por_estado"] == {"clasificada": 1}
    assert r["clasificador_activo"] == "simulado-reglas"


def test_importar_json_no_duplica_por_id_externo(cliente, cola, auth_operador):
    lote = [
        {"email": "a@ejemplo.com", "asunto": "Hola", "cuerpo": "No llegó mi pedido", "id_externo": "<x1@ejemplo.com>"},
        {"email": "b@ejemplo.com", "asunto": "Chau", "cuerpo": "Quiero la factura", "canal": "formulario"},
    ]
    r = cliente.post("/api/ingreso/json", json=lote, headers=auth_operador).json()
    assert len(r["creadas"]) == 2 and r["duplicadas"] == 0
    r = cliente.post("/api/ingreso/json", json=lote[:1], headers=auth_operador).json()
    assert r["creadas"] == [] and r["duplicadas"] == 1
    assert len(cola.encoladas) == 2


def test_importar_json_invalido_da_422(cliente, auth_operador):
    r = cliente.post("/api/ingreso/json", json=[{"email": "x", "asunto": "a", "cuerpo": "b"}], headers=auth_operador)
    assert r.status_code == 422


def test_importar_eml(cliente, auth_operador):
    archivos = [("archivos", (p.name, p.read_bytes(), "message/rfc822")) for p in sorted(EJEMPLOS.glob("*.eml"))]
    archivos.append(("archivos", ("roto.eml", b"esto no es un mail", "message/rfc822")))
    r = cliente.post("/api/ingreso/eml", files=archivos, headers=auth_operador)
    assert r.status_code == 200
    cuerpo = r.json()
    assert len(cuerpo["creadas"]) == 3
    assert len(cuerpo["errores"]) == 1 and "roto.eml" in cuerpo["errores"][0]
