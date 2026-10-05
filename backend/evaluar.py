"""Mide la precisión del clasificador activo contra el set de evaluación etiquetado.

Uso:
    python evaluar.py                  # usa Claude si hay ANTHROPIC_API_KEY, si no el simulado
    python evaluar.py --simulado       # fuerza el clasificador por reglas
    python evaluar.py --limite 10      # solo las primeras 10 (para probar barato)
    python evaluar.py --umbral 0.7     # termina con código 1 si la exactitud queda por debajo
    python evaluar.py --salida resultado.json

No toca la base de datos: lee el JSON, clasifica y compara.
"""

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from app.clasificacion.base import Clasificador
from app.clasificacion.esquema import ConsultaEntrada, ErrorClasificacion
from app.clasificacion.fabrica import obtener_clasificador
from app.clasificacion.simulado import ClasificadorSimulado
from app.config import obtener_configuracion
from app.dominio import Categoria

RUTA_DATASET = Path(__file__).parent / "evaluacion" / "consultas_etiquetadas.json"


@dataclass
class Resultado:
    total: int = 0
    errores: int = 0
    aciertos_categoria: int = 0
    aciertos_urgencia: int = 0
    pares_categoria: list[tuple[str, str]] = field(default_factory=list)  # (esperada, predicha)
    fallos: list[dict] = field(default_factory=list)
    tokens_entrada: int = 0
    tokens_salida: int = 0
    costo_usd: Decimal = Decimal("0")

    @property
    def evaluadas(self) -> int:
        return self.total - self.errores

    @property
    def exactitud_categoria(self) -> float:
        return self.aciertos_categoria / self.evaluadas if self.evaluadas else 0.0

    @property
    def exactitud_urgencia(self) -> float:
        return self.aciertos_urgencia / self.evaluadas if self.evaluadas else 0.0

    def por_categoria(self) -> dict[str, dict[str, float | int | None]]:
        predichas = Counter(p for _, p in self.pares_categoria)
        reales = Counter(e for e, _ in self.pares_categoria)
        correctas = Counter(e for e, p in self.pares_categoria if e == p)
        salida = {}
        for cat in Categoria:
            c = cat.value
            salida[c] = {
                "reales": reales[c],
                "predichas": predichas[c],
                "correctas": correctas[c],
                "precision": round(correctas[c] / predichas[c], 3) if predichas[c] else None,
                "recall": round(correctas[c] / reales[c], 3) if reales[c] else None,
            }
        return salida


def cargar_dataset(ruta: Path = RUTA_DATASET) -> list[dict]:
    with ruta.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)
    for item in datos:
        Categoria(item["categoria"])  # valida que las etiquetas existan
    return datos


def evaluar(clasificador: Clasificador, dataset: list[dict]) -> Resultado:
    resultado = Resultado()
    for item in dataset:
        resultado.total += 1
        entrada = ConsultaEntrada(asunto=item["asunto"], cuerpo=item["cuerpo"], remitente_nombre=item.get("nombre"))
        try:
            salida = clasificador.clasificar(entrada)
        except ErrorClasificacion as error:
            resultado.errores += 1
            resultado.fallos.append({"id": item["id"], "error": str(error)})
            continue
        r = salida.resultado
        if salida.uso:
            resultado.tokens_entrada += salida.uso.tokens_entrada
            resultado.tokens_salida += salida.uso.tokens_salida
            resultado.costo_usd += salida.uso.costo_usd
        resultado.pares_categoria.append((item["categoria"], r.categoria.value))
        if r.categoria.value == item["categoria"]:
            resultado.aciertos_categoria += 1
        else:
            resultado.fallos.append(
                {
                    "id": item["id"],
                    "asunto": item["asunto"],
                    "esperada": item["categoria"],
                    "predicha": r.categoria.value,
                }
            )
        if r.urgencia.value == item.get("urgencia"):
            resultado.aciertos_urgencia += 1
    return resultado


def imprimir(resultado: Resultado, nombre: str) -> None:
    print(f"\nClasificador: {nombre}")
    print(f"Consultas: {resultado.total} (errores: {resultado.errores})")
    print(f"Exactitud categoría: {resultado.exactitud_categoria:.1%}")
    print(f"Exactitud urgencia:  {resultado.exactitud_urgencia:.1%}")
    if resultado.tokens_entrada or resultado.tokens_salida:
        print(
            f"Tokens: {resultado.tokens_entrada} entrada / {resultado.tokens_salida} salida "
            f"- costo estimado USD {resultado.costo_usd:.4f}"
        )
    print(f"\n{'categoría':<22}{'reales':>7}{'pred.':>7}{'ok':>5}{'precisión':>11}{'recall':>8}")
    for cat, m in resultado.por_categoria().items():
        precision = f"{m['precision']:.0%}" if m["precision"] is not None else "-"
        recall = f"{m['recall']:.0%}" if m["recall"] is not None else "-"
        print(f"{cat:<22}{m['reales']:>7}{m['predichas']:>7}{m['correctas']:>5}{precision:>11}{recall:>8}")
    if resultado.fallos:
        print("\nErrores de categoría:")
        for f in resultado.fallos:
            if "error" in f:
                print(f"  #{f['id']}: ERROR {f['error']}")
            else:
                print(f"  #{f['id']} '{f['asunto']}': esperada {f['esperada']}, predijo {f['predicha']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--simulado", action="store_true", help="Forzar el clasificador simulado por reglas")
    parser.add_argument("--limite", type=int, default=None, help="Evaluar solo las primeras N consultas")
    parser.add_argument("--umbral", type=float, default=None, help="Exactitud mínima de categoría (0 a 1)")
    parser.add_argument("--salida", type=Path, default=None, help="Guardar el resultado en un JSON")
    args = parser.parse_args(argv)

    clasificador = ClasificadorSimulado() if args.simulado else obtener_clasificador(obtener_configuracion())
    dataset = cargar_dataset()[: args.limite]
    resultado = evaluar(clasificador, dataset)
    imprimir(resultado, clasificador.nombre)

    if args.salida:
        args.salida.write_text(
            json.dumps(
                {
                    "clasificador": clasificador.nombre,
                    "total": resultado.total,
                    "errores": resultado.errores,
                    "exactitud_categoria": round(resultado.exactitud_categoria, 4),
                    "exactitud_urgencia": round(resultado.exactitud_urgencia, 4),
                    "por_categoria": resultado.por_categoria(),
                    "fallos": resultado.fallos,
                    "tokens_entrada": resultado.tokens_entrada,
                    "tokens_salida": resultado.tokens_salida,
                    "costo_usd": float(resultado.costo_usd),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    if args.umbral is not None and resultado.exactitud_categoria < args.umbral:
        print(f"\nLa exactitud quedó por debajo del umbral {args.umbral:.0%}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
