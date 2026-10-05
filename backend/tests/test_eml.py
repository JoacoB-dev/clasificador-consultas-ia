from pathlib import Path

import pytest

from app.ingreso.eml import ErrorEml, leer_eml

EJEMPLOS = Path(__file__).resolve().parent.parent / "ejemplos" / "emails"


def test_lee_mail_de_texto_plano():
    c = leer_eml((EJEMPLOS / "01_cafetera_rota.eml").read_bytes())
    assert c.email == "laura.gomez@ejemplo.com"
    assert c.nombre == "Laura Gómez"
    assert c.asunto == "Cafetera con la jarra rota"
    assert "pedido 105200" in c.cuerpo
    assert c.id_externo == "<demo-0001@ejemplo.com>"
    assert c.recibida_en is not None and c.recibida_en.year == 2026


def test_lee_mail_html_con_asunto_codificado():
    c = leer_eml((EJEMPLOS / "02_pedido_sin_llegar.eml").read_bytes())
    assert c.asunto == "¿Dónde está mi pedido?"
    assert "<b>" not in c.cuerpo and "termo" in c.cuerpo


def test_mail_sin_remitente_falla():
    with pytest.raises(ErrorEml, match="remitente"):
        leer_eml(b"Subject: hola\n\ncuerpo")


def test_archivo_vacio_falla():
    with pytest.raises(ErrorEml):
        leer_eml(b"")
