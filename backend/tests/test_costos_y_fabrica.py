from decimal import Decimal

from app.clasificacion.claude import ClasificadorClaude
from app.clasificacion.costos import estimar_costo
from app.clasificacion.fabrica import obtener_clasificador
from app.clasificacion.simulado import ClasificadorSimulado
from app.config import Configuracion


def test_costo_sonnet():
    # 1.000 tokens de entrada a $2/M + 500 de salida a $10/M = 0,002 + 0,005
    assert estimar_costo("claude-sonnet-5-5", 1000, 500) == Decimal("0.007000")


def test_costo_modelo_desconocido_usa_el_precio_mas_alto():
    assert estimar_costo("modelo-x", 1_000_000, 0) == Decimal("4.000000")


def test_sin_clave_usa_el_simulado():
    assert isinstance(obtener_clasificador(Configuracion(anthropic_api_key=None)), ClasificadorSimulado)


def test_con_clave_usa_claude_con_el_modelo_configurado():
    c = obtener_clasificador(Configuracion(anthropic_api_key="sk-ant-prueba", llm_modelo="claude-haiku-4-5"))
    assert isinstance(c, ClasificadorClaude)
    assert c.nombre == "claude:claude-haiku-4-5"


def test_forzar_simulado_aunque_haya_clave():
    config = Configuracion(anthropic_api_key="sk-ant-prueba", forzar_clasificador_simulado=True)
    assert isinstance(obtener_clasificador(config), ClasificadorSimulado)
