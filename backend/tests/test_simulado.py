import pytest

from app.clasificacion.esquema import ConsultaEntrada
from app.clasificacion.simulado import ClasificadorSimulado, extraer_datos, normalizar
from app.dominio import Categoria, Sentimiento, Urgencia

clasificador = ClasificadorSimulado()


def clasificar(asunto: str, cuerpo: str, nombre: str | None = None):
    return clasificador.clasificar(ConsultaEntrada(asunto=asunto, cuerpo=cuerpo, remitente_nombre=nombre)).resultado


@pytest.mark.parametrize(
    ("asunto", "cuerpo", "esperada"),
    [
        ("Pedido demorado", "Mi paquete no llegó y el seguimiento no cambia", Categoria.ENVIO),
        ("Licuadora", "La licuadora llegó rota y no funciona", Categoria.PRODUCTO_DEFECTUOSO),
        ("Cambio", "Quiero devolver el termo, me arrepentí", Categoria.DEVOLUCION),
        ("Cobro", "Me cobraron dos veces en la tarjeta, necesito la factura", Categoria.FACTURACION),
        ("Consulta", "¿Tienen stock de la cafetera? ¿Cuánto sale?", Categoria.CONSULTA_PRODUCTO),
        ("Acceso", "No puedo entrar, olvidé la contraseña", Categoria.CUENTA),
        ("Hola", "Les escribo para saludarlos", Categoria.OTRO),
    ],
)
def test_categoria_por_palabras_clave(asunto, cuerpo, esperada):
    assert clasificar(asunto, cuerpo).categoria == esperada


def test_es_determinista():
    a = clasificar("Pedido", "No me llegó el pedido 123456, estoy enojado")
    b = clasificar("Pedido", "No me llegó el pedido 123456, estoy enojado")
    assert a == b


def test_urgencia_critica_si_hay_mencion_legal():
    r = clasificar("Reclamo", "Si no me responden hago la denuncia en Defensa del Consumidor")
    assert r.urgencia == Urgencia.CRITICA


def test_urgencia_baja_en_consulta_general():
    r = clasificar("Consulta", "Quisiera saber el precio de la pava eléctrica")
    assert r.urgencia == Urgencia.BAJA


def test_sentimiento_negativo_y_positivo():
    assert clasificar("Mal", "Pésimo servicio, estoy indignado").sentimiento == Sentimiento.NEGATIVO
    assert clasificar("Gracias", "Excelente atención, muchas gracias").sentimiento == Sentimiento.POSITIVO


def test_extrae_datos_del_texto():
    datos = extraer_datos("Pedido 104233: pagué $ 45.999,50 con Mercado Pago el 12/08 por la pava eléctrica")
    assert datos.numero_pedido == "PED-104233"
    assert datos.monto == 45999.50
    assert datos.medio_pago == "Mercado Pago"
    assert datos.fecha_mencionada == "12/08"
    assert datos.producto == "pava electrica"


def test_extrae_pedido_con_prefijo_ped():
    assert extraer_datos("Mi compra PED-105012 vino mal").numero_pedido == "PED-105012"


def test_sin_datos_devuelve_nulls():
    datos = extraer_datos("Hola, ¿cómo están?")
    assert datos.model_dump() == {
        "numero_pedido": None,
        "producto": None,
        "monto": None,
        "medio_pago": None,
        "fecha_mencionada": None,
    }


def test_borrador_saluda_por_nombre_y_firma():
    r = clasificar("Pedido", "No llegó el pedido 104233", nombre="Marcela Ríos")
    assert r.borrador_respuesta.startswith("Hola Marcela,")
    assert "PED-104233" in r.borrador_respuesta
    assert "Bazar La Esquina" in r.borrador_respuesta


def test_normalizar_saca_tildes_y_mayusculas():
    assert normalizar("ENVÍO   Demorádo") == "envio demorado"


def test_resumen_saltea_el_saludo():
    r = clasificar("Cafetera rota", "Hola, buen día.\n\nMe llegó la cafetera con la jarra rota. Quiero el cambio.")
    assert r.resumen == "Cafetera rota: Me llegó la cafetera con la jarra rota."
