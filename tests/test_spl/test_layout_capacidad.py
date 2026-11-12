"""
Capacidad del layout de estructuras (Tarea 29).

Los programas de los Algoritmos 2 y 3 colocan varias estructuras en la misma
zona usando los desplazamientos DESP_* de layout_datos.inc. Estas pruebas
comprueban que el ensamblador y el lado Python usan los mismos valores y que
caben las estructuras grandes que permite la interfaz (vectores de cientos de
elementos y matrices de 8 x 8 en adelante).
"""

from __future__ import annotations

import random
import re
from pathlib import Path

import pytest

from spl.estructuras import (
    BASE_MAT_B, BASE_MAT_C, BASE_MATRICES, BASE_VEC_B, BASE_VECTORES,
    ejecutar_busqueda_binaria, ejecutar_multiplicacion_matrices, ejecutar_producto_punto,
)
from spl.estructuras.algoritmos import DESP_MATRIZ_2, DESP_MATRIZ_3, DESP_VECTOR_2

LAYOUT = Path(__file__).resolve().parents[2] / "spl" / "include" / "layout_datos.inc"
EJEMPLOS = LAYOUT.parents[1] / "ejemplos"


def _macro(nombre: str) -> int:
    m = re.search(rf"^#define\s+{nombre}\s+(\S+)", LAYOUT.read_text(), re.MULTILINE)
    assert m, nombre
    return int(m.group(1), 0)


def test_python_y_layout_datos_usan_los_mismos_desplazamientos():
    assert _macro("DESP_VECTOR_2") == DESP_VECTOR_2 == BASE_VEC_B - BASE_VECTORES
    assert _macro("DESP_MATRIZ_2") == DESP_MATRIZ_2 == BASE_MAT_B - BASE_MATRICES
    assert _macro("DESP_MATRIZ_3") == DESP_MATRIZ_3 == BASE_MAT_C - BASE_MATRICES


def test_los_desplazamientos_caben_en_el_inmediato_de_addi():
    for valor in (DESP_VECTOR_2, DESP_MATRIZ_2, DESP_MATRIZ_3):
        assert 0 < valor <= 0x7FFF and valor % 8 == 0


@pytest.mark.parametrize("programa", ["producto_punto", "busqueda_binaria",
                                      "multiplicacion_matrices"])
def test_los_programas_no_codifican_desplazamientos_a_mano(programa):
    fuente = (EJEMPLOS / f"{programa}.asm").read_text()
    assert not re.search(r"ADDI\s+R\d,\s*R\d,\s*(256|512|1024)\b", fuente)
    assert "DESP_" in fuente


def test_producto_punto_de_200_elementos():
    rnd = random.Random(29)
    a = [rnd.randint(-50, 50) for _ in range(200)]
    b = [rnd.randint(-50, 50) for _ in range(200)]
    valor, _ = ejecutar_producto_punto(a, b, max_ciclos=5_000_000)
    assert valor == sum(x * y for x, y in zip(a, b))


def test_busqueda_binaria_sobre_300_elementos():
    v = list(range(-300, 300, 2))
    q = [-300, 0, 298, 1, 999]
    indices, _ = ejecutar_busqueda_binaria(v, q, max_ciclos=2_000_000)
    assert indices == [v.index(x) if x in v else -1 for x in q]


def test_multiplicacion_de_matrices_8x8_ya_no_solapa():
    rnd = random.Random(8)
    a = [[rnd.randint(-5, 5) for _ in range(8)] for _ in range(8)]
    b = [[rnd.randint(-5, 5) for _ in range(8)] for _ in range(8)]
    c, _, _ = ejecutar_multiplicacion_matrices(a, b, max_ciclos=20_000_000)
    assert c == [[sum(a[i][k] * b[k][j] for k in range(8)) for j in range(8)] for i in range(8)]
