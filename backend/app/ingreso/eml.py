"""Lectura de archivos .eml (mails exportados) para convertirlos en consultas.

No hay conexión a un servidor de correo real: se simula el canal mail importando
archivos .eml o JSON. Conectarlo a IMAP sería el siguiente paso.
"""

import html
import re
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime

from pydantic import ValidationError

from app.dominio import Canal
from app.esquemas import ConsultaImportada


class ErrorEml(ValueError):
    pass


def _html_a_texto(contenido: str) -> str:
    sin_estilos = re.sub(r"(?is)<(script|style).*?</\1>", " ", contenido)
    con_saltos = re.sub(r"(?i)<br\s*/?>|</p>", "\n", sin_estilos)
    sin_tags = re.sub(r"<[^>]+>", " ", con_saltos)
    return re.sub(r"[ \t]+", " ", html.unescape(sin_tags)).strip()


def leer_eml(contenido: bytes) -> ConsultaImportada:
    """Convierte los bytes de un .eml en una consulta importable. Lanza ErrorEml si no sirve."""
    if not contenido:
        raise ErrorEml("El archivo está vacío")
    mensaje = BytesParser(policy=policy.default).parsebytes(contenido)

    nombre, email = parseaddr(str(mensaje.get("From", "")))
    if not email or "@" not in email:
        raise ErrorEml("El mail no tiene remitente (From) válido")

    parte = mensaje.get_body(preferencelist=("plain", "html"))
    if parte is None:
        raise ErrorEml("El mail no tiene cuerpo de texto")
    cuerpo = parte.get_content()
    if parte.get_content_subtype() == "html":
        cuerpo = _html_a_texto(cuerpo)
    cuerpo = cuerpo.strip()

    recibida_en = None
    if fecha := mensaje.get("Date"):
        try:
            recibida_en = parsedate_to_datetime(str(fecha))
        except (TypeError, ValueError):
            recibida_en = None

    try:
        return ConsultaImportada(
            canal=Canal.EMAIL,
            nombre=nombre or None,
            email=email,
            asunto=str(mensaje.get("Subject", "")).strip() or "(sin asunto)",
            cuerpo=cuerpo,
            id_externo=str(mensaje.get("Message-ID", "")).strip() or None,
            recibida_en=recibida_en,
        )
    except ValidationError as error:
        campos = ", ".join(str(e["loc"][0]) for e in error.errors())
        raise ErrorEml(f"Datos inválidos en el mail: {campos}") from error
