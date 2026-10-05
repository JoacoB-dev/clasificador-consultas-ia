"""Costo estimado por llamada, según precios públicos por millón de tokens (USD).

Son valores de referencia para estimar; el costo real sale de la consola de Anthropic.
"""

from decimal import Decimal

# (entrada, salida) en USD por millón de tokens
PRECIOS_POR_MILLON: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-5-5": (Decimal("2.00"), Decimal("10.00")),
    "claude-opus-5-5": (Decimal("4.00"), Decimal("20.00")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
}
# Si el modelo no está en la tabla usamos el precio más caro conocido (mejor sobreestimar)
PRECIO_DESCONOCIDO = (Decimal("4.00"), Decimal("20.00"))


def estimar_costo(modelo: str, tokens_entrada: int, tokens_salida: int) -> Decimal:
    entrada, salida = PRECIOS_POR_MILLON.get(modelo, PRECIO_DESCONOCIDO)
    costo = (Decimal(tokens_entrada) * entrada + Decimal(tokens_salida) * salida) / Decimal(1_000_000)
    return costo.quantize(Decimal("0.000001"))
