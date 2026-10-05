from collections import Counter

import evaluar
from app.clasificacion.simulado import ClasificadorSimulado
from app.dominio import Categoria


def test_dataset_tiene_entre_30_y_50_consultas_y_todas_las_categorias():
    datos = evaluar.cargar_dataset()
    assert 30 <= len(datos) <= 50
    assert set(Counter(d["categoria"] for d in datos)) == {c.value for c in Categoria}
    assert len({d["id"] for d in datos}) == len(datos)


def test_evaluar_calcula_metricas():
    datos = evaluar.cargar_dataset()
    resultado = evaluar.evaluar(ClasificadorSimulado(), datos)
    assert resultado.total == len(datos)
    assert 0 < resultado.exactitud_categoria <= 1
    por_cat = resultado.por_categoria()
    assert sum(m["reales"] for m in por_cat.values()) == len(datos)


def test_main_respeta_el_umbral(tmp_path, capsys):
    salida = tmp_path / "r.json"
    assert evaluar.main(["--simulado", "--limite", "10", "--salida", str(salida)]) == 0
    assert salida.exists()
    assert evaluar.main(["--simulado", "--umbral", "1.01"]) == 1
    assert "Exactitud categoría" in capsys.readouterr().out
