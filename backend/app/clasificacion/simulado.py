"""Clasificador simulado y determinista basado en palabras clave.

Se usa cuando no hay ANTHROPIC_API_KEY: permite correr la demo, el worker y los tests
sin gastar ni depender de la red. No pretende ser bueno: es una línea de base contra
la cual comparar al LLM con `evaluar.py`.
"""

import re
import unicodedata

from app.clasificacion.esquema import (
    ConsultaEntrada,
    DatosExtraidos,
    ResultadoClasificacion,
    SalidaClasificador,
)
from app.dominio import Categoria, Sentimiento, Urgencia

# Palabras clave por categoría con su peso. Se buscan sobre el texto normalizado
# (minúsculas y sin tildes). Las frases más específicas pesan más.
PALABRAS_CATEGORIA: dict[Categoria, dict[str, int]] = {
    Categoria.ENVIO: {
        "envio": 2,
        "no llego": 3,
        "no me llego": 3,
        "todavia no llego": 3,
        "seguimiento": 2,
        "correo": 1,
        "andreani": 2,
        "demora": 2,
        "despacho": 2,
        "despacharon": 2,
        "repartidor": 2,
        "cuando llega": 3,
        "cuando me llega": 3,
        "tracking": 2,
        "entrega": 1,
        "domicilio": 1,
        "paquete": 2,
        "sucursal": 1,
        "direccion de entrega": 2,
    },
    Categoria.PRODUCTO_DEFECTUOSO: {
        "roto": 3,
        "rota": 3,
        "no funciona": 3,
        "no anda": 3,
        "dejo de andar": 3,
        "defectuoso": 3,
        "fallado": 3,
        "fallada": 3,
        "rajado": 3,
        "rajada": 3,
        "quemo": 2,
        "no prende": 3,
        "golpeado": 2,
        "abollado": 2,
        "falla": 2,
        "garantia": 2,
        "pierde agua": 3,
        "se corta": 2,
        "hace ruido": 2,
        "se calienta": 2,
    },
    Categoria.DEVOLUCION: {
        "devolver": 3,
        "devolucion": 3,
        "cambio": 2,
        "cambiar": 2,
        "arrepentimiento": 3,
        "me arrepenti": 3,
        "no me gusto": 2,
        "otro talle": 2,
        "otro color": 2,
        "talle": 1,
        "retiren": 1,
        "no lo quiero": 2,
        "boton de arrepentimiento": 4,
    },
    Categoria.FACTURACION: {
        "factura": 3,
        "facturacion": 3,
        "cobro": 2,
        "cobraron": 3,
        "me cobraron": 3,
        "doble": 1,
        "dos veces": 2,
        "cuit": 2,
        "reintegro": 2,
        "resumen de la tarjeta": 3,
        "cuotas": 1,
        "pago": 1,
        "debito": 1,
        "nota de credito": 3,
        "comprobante": 2,
        "iva": 2,
        "transferencia": 1,
        "reembolso": 2,
    },
    Categoria.CONSULTA_PRODUCTO: {
        "stock": 3,
        "tienen": 1,
        "precio": 2,
        "cuanto sale": 3,
        "cuanto cuesta": 3,
        "medidas": 2,
        "viene en": 2,
        "sirve para": 2,
        "es compatible": 2,
        "caracteristicas": 2,
        "capacidad": 1,
        "consulta": 1,
        "quisiera saber": 1,
        "material": 1,
        "colores": 1,
        "hacen envios": 2,
        "por mayor": 2,
        "voltaje": 2,
        "lavavajillas": 1,
    },
    Categoria.CUENTA: {
        "contrasena": 3,
        "clave": 2,
        "no puedo entrar": 3,
        "no puedo ingresar": 3,
        "iniciar sesion": 3,
        "mi cuenta": 2,
        "usuario": 1,
        "cambiar el mail": 3,
        "cambiar mi mail": 3,
        "dar de baja": 2,
        "datos personales": 2,
        "newsletter": 2,
        "bloqueada": 2,
        "codigo de verificacion": 3,
    },
}

PALABRAS_CRITICAS = ["defensa del consumidor", "denuncia", "abogado", "carta documento", "estafa", "estafadores"]
PALABRAS_ALTA = [
    "urgente",
    "urgencia",
    "hoy mismo",
    "ya mismo",
    "inaceptable",
    "vergüenza",
    "verguenza",
    "nadie me responde",
    "nadie responde",
    "tercera vez",
    "otra vez",
    "hace dos semanas",
    "hace 15 dias",
    "hace un mes",
    "regalo",
    "cumpleanos",
    "me cobraron dos veces",
    "doble",
]
PALABRAS_BAJA = ["consulta", "quisiera saber", "cuando puedan", "sin apuro", "curiosidad", "gracias de antemano"]

PALABRAS_NEGATIVAS = [
    "enojado",
    "enojada",
    "molesto",
    "molesta",
    "indignado",
    "indignada",
    "pesimo",
    "pesima",
    "horrible",
    "vergüenza",
    "verguenza",
    "inaceptable",
    "decepcion",
    "decepcionado",
    "decepcionada",
    "estafa",
    "nunca mas",
    "harto",
    "harta",
    "mal servicio",
    "una burla",
    "falta de respeto",
    "denuncia",
    "no funciona",
    "roto",
    "rota",
    "nadie me responde",
    "nadie responde",
]
PALABRAS_POSITIVAS = [
    "gracias",
    "excelente",
    "genial",
    "buenisimo",
    "muy bueno",
    "contento",
    "contenta",
    "encantado",
    "encantada",
    "felicitaciones",
    "impecable",
    "recomiendo",
    "joya",
]

PRODUCTOS_CATALOGO = [
    "pava electrica",
    "cafetera",
    "licuadora",
    "batidora",
    "tostadora",
    "juego de ollas",
    "sarten",
    "termo",
    "mate",
    "vaso termico",
    "set de cuchillos",
    "microondas",
    "freidora de aire",
    "aspiradora",
    "ventilador",
    "estufa",
    "plancha",
    "vajilla",
    "juego de sabanas",
    "almohada",
]

PLANTILLAS_RESPUESTA: dict[Categoria, str] = {
    Categoria.ENVIO: (
        "Gracias por escribirnos y disculpá la demora. Ya le pedimos al área de Logística que revise "
        "el estado del envío{pedido}. En cuanto tengamos la novedad del correo te avisamos por este medio."
    ),
    Categoria.PRODUCTO_DEFECTUOSO: (
        "Lamentamos mucho que el producto{producto} haya llegado con un problema. Para gestionar el cambio "
        "por garantía, ¿nos podrías mandar una foto del producto y del embalaje{pedido_pregunta}? "
        "Postventa lo revisa y te contacta para coordinar."
    ),
    Categoria.DEVOLUCION: (
        "Recibimos tu pedido de cambio/devolución{pedido}. Tenés 10 días corridos desde que lo recibiste "
        "para ejercer el derecho de arrepentimiento. Te vamos a enviar las instrucciones para el retiro."
    ),
    Categoria.FACTURACION: (
        "Gracias por avisarnos. Derivamos tu consulta a Administración para que revise el cobro{pedido}. "
        "Si corresponde un reintegro te lo confirmamos por este medio con el detalle."
    ),
    Categoria.CONSULTA_PRODUCTO: (
        "¡Gracias por tu consulta! Te pasamos la información{producto} a la brevedad. "
        "También podés ver stock y precios actualizados en la tienda online."
    ),
    Categoria.CUENTA: (
        "Gracias por escribirnos. Para ayudarte con tu cuenta, probá primero la opción "
        '"Olvidé mi contraseña". Si no te llega el mail, respondenos y lo revisamos manualmente.'
    ),
    Categoria.OTRO: (
        "Gracias por escribirnos. Recibimos tu mensaje y lo derivamos al área correspondiente. "
        "Te respondemos a la brevedad."
    ),
}

RE_PEDIDO = re.compile(r"\b(?:ped|pedido|orden|compra)\s*(?:n(?:ro|°|º|umero)?\.?\s*)?[-#:]?\s*(\d{5,8})\b")
RE_MONTO = re.compile(r"\$\s?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?")
RE_FECHA = re.compile(r"\b(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\b")
MEDIOS_PAGO = {
    "mercado pago": "Mercado Pago",
    "tarjeta de credito": "tarjeta de crédito",
    "tarjeta de debito": "tarjeta de débito",
    "transferencia": "transferencia",
    "efectivo": "efectivo",
    "visa": "tarjeta Visa",
    "mastercard": "tarjeta Mastercard",
}


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para que 'Envío' y 'envio' cuenten igual."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_tildes.lower())


def _contar(texto: str, palabras: list[str]) -> int:
    return sum(1 for p in palabras if normalizar(p) in texto)


def extraer_datos(texto_original: str) -> DatosExtraidos:
    texto = normalizar(texto_original)
    pedido = None
    if m := RE_PEDIDO.search(texto):
        pedido = f"PED-{m.group(1)}"

    monto = None
    if m := RE_MONTO.search(texto_original):
        entero = m.group(1).replace(".", "")
        decimales = m.group(2) or "0"
        monto = float(f"{entero}.{decimales}")

    producto = next((p for p in PRODUCTOS_CATALOGO if p in texto), None)
    medio = next((v for k, v in MEDIOS_PAGO.items() if k in texto), None)
    fecha = m.group(1) if (m := RE_FECHA.search(texto_original)) else None
    return DatosExtraidos(
        numero_pedido=pedido, producto=producto, monto=monto, medio_pago=medio, fecha_mencionada=fecha
    )


def _elegir_categoria(texto: str) -> tuple[Categoria, float]:
    puntajes = {
        cat: sum(peso for palabra, peso in palabras.items() if palabra in texto)
        for cat, palabras in PALABRAS_CATEGORIA.items()
    }
    # Ordenamos por puntaje y, a igualdad, por el orden de la enum (determinista)
    orden = list(Categoria)
    mejor, puntaje = max(puntajes.items(), key=lambda kv: (kv[1], -orden.index(kv[0])))
    if puntaje == 0:
        return Categoria.OTRO, 0.3
    total = sum(puntajes.values())
    return mejor, round(min(0.95, 0.4 + 0.5 * puntaje / total), 2)


def _elegir_urgencia(texto: str, categoria: Categoria, sentimiento: Sentimiento) -> Urgencia:
    if _contar(texto, PALABRAS_CRITICAS):
        return Urgencia.CRITICA
    if _contar(texto, PALABRAS_ALTA):
        return Urgencia.ALTA
    if categoria in (Categoria.CONSULTA_PRODUCTO, Categoria.OTRO) or _contar(texto, PALABRAS_BAJA):
        return Urgencia.BAJA if sentimiento != Sentimiento.NEGATIVO else Urgencia.MEDIA
    return Urgencia.MEDIA


def _elegir_sentimiento(texto: str) -> Sentimiento:
    negativas = _contar(texto, PALABRAS_NEGATIVAS) + texto.count("!!")
    positivas = _contar(texto, PALABRAS_POSITIVAS)
    if negativas > positivas:
        return Sentimiento.NEGATIVO
    if positivas > negativas and positivas >= 2:
        return Sentimiento.POSITIVO
    return Sentimiento.NEUTRO


RE_SALUDO = re.compile(r"^(hola|buen(os|as)? (dia|dias|tardes|noches)|buenas|que tal|estimad[oa]s?)\b[\s,.!]*", re.I)


def _resumir(asunto: str, cuerpo: str) -> str:
    """Asunto + la primera oración con contenido (salteando saludos como 'Hola, buen día.')."""
    oraciones = [o.strip() for o in re.split(r"(?<=[.!?])\s+|\n+", cuerpo.strip()) if o.strip()]
    primera = next(
        (o for o in oraciones if len(RE_SALUDO.sub("", normalizar(o)).strip(" ,.!")) > 12),
        oraciones[0] if oraciones else "",
    )
    resumen = f"{asunto.strip()}: {primera}" if asunto.strip() else primera
    return resumen if len(resumen) <= 280 else resumen[:277] + "..."


def _borrador(categoria: Categoria, nombre: str | None, datos: DatosExtraidos) -> str:
    saludo = f"Hola {nombre.split()[0]}," if nombre and nombre.strip() else "Hola,"
    cuerpo = PLANTILLAS_RESPUESTA[categoria].format(
        pedido=f" del pedido {datos.numero_pedido}" if datos.numero_pedido else "",
        pedido_pregunta=f" (pedido {datos.numero_pedido})" if datos.numero_pedido else " y el número de pedido",
        producto=f" ({datos.producto})" if datos.producto else "",
    )
    return f"{saludo}\n\n{cuerpo}\n\nSaludos,\nEquipo de Atención - Bazar La Esquina"


class ClasificadorSimulado:
    nombre = "simulado-reglas"

    def clasificar(self, consulta: ConsultaEntrada) -> SalidaClasificador:
        texto = normalizar(f"{consulta.asunto} {consulta.cuerpo}")
        categoria, confianza = _elegir_categoria(texto)
        sentimiento = _elegir_sentimiento(texto)
        urgencia = _elegir_urgencia(texto, categoria, sentimiento)
        datos = extraer_datos(f"{consulta.asunto} {consulta.cuerpo}")
        resultado = ResultadoClasificacion(
            categoria=categoria,
            urgencia=urgencia,
            sentimiento=sentimiento,
            resumen=_resumir(consulta.asunto, consulta.cuerpo),
            datos_extraidos=datos,
            borrador_respuesta=_borrador(categoria, consulta.remitente_nombre, datos),
            confianza=confianza,
        )
        return SalidaClasificador(resultado=resultado, clasificador=self.nombre)
