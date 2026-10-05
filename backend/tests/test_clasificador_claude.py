"""Tests del clasificador con Claude usando un cliente falso (no hay clave real ni red)."""

import json
from decimal import Decimal
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from app.clasificacion.claude import BETA_FALLBACK, ClasificadorClaude
from app.clasificacion.esquema import ConsultaEntrada, ErrorClasificacion
from app.config import Configuracion
from app.dominio import Categoria

PEDIDO = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

JSON_VALIDO = {
    "categoria": "envio",
    "urgencia": "alta",
    "sentimiento": "negativo",
    "resumen": "El pedido PED-104233 no llegó.",
    "datos_extraidos": {
        "numero_pedido": "PED-104233",
        "producto": "pava eléctrica",
        "monto": None,
        "medio_pago": None,
        "fecha_mencionada": "12/08",
    },
    "borrador_respuesta": "Hola Marcela, ya lo estamos revisando.",
    "confianza": 0.92,
}


def respuesta(texto: str, stop_reason="end_turn", entrada=1200, salida=300, modelo="claude-sonnet-5-5"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=texto)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=entrada, output_tokens=salida),
        model=modelo,
    )


class ClienteFalso:
    """Imita `client.beta.messages.create`: devuelve (o lanza) lo que se le cargue, en orden."""

    def __init__(self, *salidas):
        self.salidas = list(salidas)
        self.llamadas: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.llamadas.append(kwargs)
        salida = self.salidas.pop(0)
        if isinstance(salida, Exception):
            raise salida
        return salida


def config(**cambios) -> Configuracion:
    base = {"anthropic_api_key": "sk-ant-prueba", "llm_max_reintentos": 3}
    return Configuracion(**(base | cambios))


def armar(cliente, **cambios):
    esperas: list[float] = []
    clasificador = ClasificadorClaude(config(**cambios), cliente=cliente, dormir=esperas.append)
    return clasificador, esperas


ENTRADA = ConsultaEntrada(asunto="Pedido sin novedades", cuerpo="No llegó el pedido 104233", remitente_nombre="Marcela")


def test_clasifica_y_registra_tokens_y_costo():
    cliente = ClienteFalso(respuesta(json.dumps(JSON_VALIDO)))
    clasificador, esperas = armar(cliente)

    salida = clasificador.clasificar(ENTRADA)

    assert salida.resultado.categoria == Categoria.ENVIO
    assert salida.resultado.datos_extraidos.numero_pedido == "PED-104233"
    assert salida.clasificador == "claude:claude-sonnet-5-5"
    assert salida.uso.tokens_entrada == 1200 and salida.uso.tokens_salida == 300
    assert salida.uso.costo_usd == Decimal("0.005400")  # 1200*2/1M + 300*10/1M
    assert salida.uso.intentos == 1
    assert esperas == []


def test_envia_salida_estructurada_modelo_y_fallback():
    cliente = ClienteFalso(respuesta(json.dumps(JSON_VALIDO)))
    clasificador, _ = armar(cliente, llm_modelo="claude-sonnet-5-5")
    clasificador.clasificar(ENTRADA)

    params = cliente.llamadas[0]
    assert params["model"] == "claude-sonnet-5-5"
    formato = params["output_config"]["format"]
    assert formato["type"] == "json_schema"
    assert set(formato["schema"]["required"]) >= {"categoria", "urgencia", "datos_extraidos", "borrador_respuesta"}
    assert params["betas"] == [BETA_FALLBACK] and params["fallbacks"] == "default"
    # El texto del cliente va delimitado para que no se tome como instrucciones
    assert "<consulta>" in params["messages"][0]["content"]


def test_sin_fallback_no_manda_beta():
    cliente = ClienteFalso(respuesta(json.dumps(JSON_VALIDO)))
    clasificador, _ = armar(cliente, llm_fallback_servidor=False)
    clasificador.clasificar(ENTRADA)
    assert "betas" not in cliente.llamadas[0] and "fallbacks" not in cliente.llamadas[0]


def test_reintenta_con_backoff_ante_rate_limit_y_timeout():
    cliente = ClienteFalso(
        anthropic.RateLimitError("rate", response=httpx2.Response(429, request=PEDIDO), body=None),
        anthropic.APITimeoutError(request=PEDIDO),
        respuesta(json.dumps(JSON_VALIDO)),
    )
    clasificador, esperas = armar(cliente, llm_backoff_base_segundos=1.0)

    salida = clasificador.clasificar(ENTRADA)

    assert salida.uso.intentos == 3
    assert len(esperas) == 2
    assert 1.0 <= esperas[0] <= 1.5 and 2.0 <= esperas[1] <= 3.0  # exponencial con jitter


def test_reintenta_si_el_json_no_valida_y_suma_tokens():
    malo = dict(JSON_VALIDO, categoria="inventada")
    cliente = ClienteFalso(respuesta(json.dumps(malo)), respuesta(json.dumps(JSON_VALIDO)))
    clasificador, _ = armar(cliente)

    salida = clasificador.clasificar(ENTRADA)

    assert salida.uso.intentos == 2
    assert salida.uso.tokens_entrada == 2400  # se pagan los dos intentos


def test_agota_reintentos_y_lanza_error_con_uso():
    errores = [anthropic.InternalServerError("caído", response=httpx2.Response(500, request=PEDIDO), body=None)] * 3
    clasificador, esperas = armar(ClienteFalso(*errores))

    with pytest.raises(ErrorClasificacion) as info:
        clasificador.clasificar(ENTRADA)

    assert "reintentos" in str(info.value)
    assert info.value.uso.intentos == 3
    assert len(esperas) == 2


def test_error_400_no_se_reintenta():
    cliente = ClienteFalso(anthropic.BadRequestError("mal", response=httpx2.Response(400, request=PEDIDO), body=None))
    clasificador, esperas = armar(cliente)

    with pytest.raises(ErrorClasificacion) as info:
        clasificador.clasificar(ENTRADA)

    assert info.value.reintentable is False
    assert len(cliente.llamadas) == 1 and esperas == []


def test_refusal_no_se_reintenta():
    clasificador, _ = armar(ClienteFalso(respuesta("", stop_reason="refusal")))
    with pytest.raises(ErrorClasificacion, match="refusal"):
        clasificador.clasificar(ENTRADA)


def test_si_responde_otro_modelo_por_fallback_el_costo_usa_ese_modelo():
    cliente = ClienteFalso(respuesta(json.dumps(JSON_VALIDO), entrada=1_000_000, salida=0, modelo="claude-opus-5-5"))
    clasificador, _ = armar(cliente)
    salida = clasificador.clasificar(ENTRADA)
    assert salida.uso.modelo == "claude-opus-5-5"
    assert salida.uso.costo_usd == Decimal("4.000000")
