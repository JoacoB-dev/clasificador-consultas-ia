from datetime import UTC, datetime, timedelta

import pytest

from app.clasificacion.esquema import DatosExtraidos, ResultadoClasificacion
from app.dominio import Categoria, Sentimiento, Urgencia
from app.reglas_negocio import AREA_ESCALADO, aplicar_reglas

RECIBIDA = datetime(2026, 10, 1, 10, 0, tzinfo=UTC)
SIN_DATOS = DatosExtraidos(numero_pedido=None, producto=None, monto=None, medio_pago=None, fecha_mencionada=None)


def resultado(categoria=Categoria.ENVIO, urgencia=Urgencia.MEDIA, sentimiento=Sentimiento.NEUTRO, datos=SIN_DATOS):
    return ResultadoClasificacion(
        categoria=categoria,
        urgencia=urgencia,
        sentimiento=sentimiento,
        resumen="r",
        datos_extraidos=datos,
        borrador_respuesta="b",
        confianza=0.9,
    )


@pytest.mark.parametrize(
    ("categoria", "area"),
    [
        (Categoria.ENVIO, "Logística"),
        (Categoria.PRODUCTO_DEFECTUOSO, "Postventa"),
        (Categoria.DEVOLUCION, "Postventa"),
        (Categoria.FACTURACION, "Administración"),
        (Categoria.CONSULTA_PRODUCTO, "Ventas"),
        (Categoria.CUENTA, "Atención al cliente"),
        (Categoria.OTRO, "Atención al cliente"),
    ],
)
def test_area_por_categoria(categoria, area):
    assert aplicar_reglas(resultado(categoria=categoria), "texto", RECIBIDA).area == area


@pytest.mark.parametrize(("urgencia", "horas"), [("critica", 4), ("alta", 8), ("media", 24), ("baja", 72)])
def test_sla_segun_urgencia(urgencia, horas):
    a = aplicar_reglas(resultado(urgencia=Urgencia(urgencia)), "texto", RECIBIDA)
    assert a.sla_vence_en == RECIBIDA + timedelta(hours=horas)


def test_mencion_legal_escala_a_supervision():
    a = aplicar_reglas(resultado(urgencia=Urgencia.BAJA), "voy a ir a Defensa del Consumidor", RECIBIDA)
    assert a.area == AREA_ESCALADO
    assert a.urgencia == Urgencia.CRITICA
    assert any("Supervisión" in r for r in a.reglas_aplicadas)


def test_sentimiento_negativo_sube_urgencia_baja():
    a = aplicar_reglas(resultado(urgencia=Urgencia.BAJA, sentimiento=Sentimiento.NEGATIVO), "texto", RECIBIDA)
    assert a.urgencia == Urgencia.MEDIA


def test_facturacion_con_monto_alto_es_al_menos_alta():
    datos = SIN_DATOS.model_copy(update={"monto": 650_000.0})
    a = aplicar_reglas(resultado(categoria=Categoria.FACTURACION, datos=datos), "texto", RECIBIDA)
    assert a.urgencia == Urgencia.ALTA
    # Si ya era crítica, no baja
    a = aplicar_reglas(
        resultado(categoria=Categoria.FACTURACION, urgencia=Urgencia.CRITICA, datos=datos), "texto", RECIBIDA
    )
    assert a.urgencia == Urgencia.CRITICA


def test_monto_alto_no_afecta_otras_categorias():
    datos = SIN_DATOS.model_copy(update={"monto": 900_000.0})
    assert aplicar_reglas(resultado(datos=datos), "texto", RECIBIDA).urgencia == Urgencia.MEDIA
