"""Integración con Redis real: se encola con RQ y un worker en modo burst procesa la consulta."""

import json
from types import SimpleNamespace

import pytest
from redis import Redis
from rq import Queue, SimpleWorker

from app.clasificacion.claude import ClasificadorClaude
from app.cola import ColaConsultas
from app.config import Configuracion, obtener_configuracion
from app.dominio import EstadoConsulta
from app.modelos import Consulta, UsoLLM
from app.tareas import procesar_en_sesion

pytestmark = pytest.mark.integracion


@pytest.fixture
def redis_real():
    conexion = Redis.from_url(obtener_configuracion().redis_url)
    conexion.flushdb()
    yield conexion
    conexion.flushdb()


def nueva_consulta(sesion, cuerpo="Mi paquete no llegó, pedido 104233") -> Consulta:
    c = Consulta(canal="email", remitente_email="x@ejemplo.com", asunto="Pedido", cuerpo=cuerpo, estado="pendiente")
    sesion.add(c)
    sesion.commit()
    return c


def test_encolar_y_procesar_con_worker_rq(sesion, redis_real):
    consulta = nueva_consulta(sesion)
    cola = Queue(obtener_configuracion().nombre_cola, connection=redis_real)

    assert ColaConsultas(cola).encolar(consulta.id) is True
    assert cola.count == 1

    SimpleWorker([cola], connection=redis_real).work(burst=True)

    sesion.expire_all()
    procesada = sesion.get(Consulta, consulta.id)
    assert procesada.estado == EstadoConsulta.CLASIFICADA
    assert procesada.categoria == "envio"
    assert procesada.intentos == 1


def test_encolar_con_redis_caido_devuelve_false():
    caido = Redis(host="localhost", port=1, socket_connect_timeout=0.2)
    assert ColaConsultas(Queue("x", connection=caido)).encolar(1) is False


class _ClienteFalso:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **_: self.respuestas.pop(0)))


def _respuesta(texto, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=800, output_tokens=250),
        model="claude-sonnet-5-5",
    )


def test_procesar_con_claude_mockeado_guarda_uso(sesion):
    consulta = nueva_consulta(sesion, cuerpo="Voy a hacer la denuncia en Defensa del Consumidor")
    datos = {
        "categoria": "envio",
        "urgencia": "alta",
        "sentimiento": "negativo",
        "resumen": "Amenaza con denuncia por demora.",
        "datos_extraidos": {
            "numero_pedido": None,
            "producto": None,
            "monto": None,
            "medio_pago": None,
            "fecha_mencionada": None,
        },
        "borrador_respuesta": "Hola, lo revisamos ya.",
        "confianza": 0.8,
    }
    clasificador = ClasificadorClaude(
        Configuracion(anthropic_api_key="sk-ant-prueba"), cliente=_ClienteFalso([_respuesta(json.dumps(datos))])
    )

    procesar_en_sesion(sesion, consulta.id, clasificador)

    assert consulta.estado == EstadoConsulta.CLASIFICADA
    assert consulta.urgencia_modelo == "alta" and consulta.urgencia == "critica"  # regla legal
    assert consulta.area_asignada == "Supervisión"
    uso = sesion.query(UsoLLM).one()
    assert (uso.tokens_entrada, uso.tokens_salida, uso.exito) == (800, 250, True)
    assert float(uso.costo_usd) == pytest.approx(0.0041)


def test_si_falla_el_llm_queda_en_error_y_registra_el_intento(sesion):
    consulta = nueva_consulta(sesion)
    clasificador = ClasificadorClaude(
        Configuracion(anthropic_api_key="sk-ant-prueba"),
        cliente=_ClienteFalso([_respuesta("", stop_reason="refusal")]),
    )

    procesar_en_sesion(sesion, consulta.id, clasificador)

    assert consulta.estado == EstadoConsulta.ERROR
    assert "refusal" in consulta.error_detalle
    uso = sesion.query(UsoLLM).one()
    assert uso.exito is False and uso.tokens_entrada == 800


def test_no_reprocesa_una_consulta_aprobada(sesion):
    consulta = nueva_consulta(sesion)
    consulta.estado = EstadoConsulta.APROBADA.value
    sesion.commit()
    procesar_en_sesion(sesion, consulta.id, None)  # no debería ni llamar al clasificador
    assert consulta.intentos == 0


def test_consulta_inexistente_no_rompe(sesion):
    assert procesar_en_sesion(sesion, 12345, None) is None
