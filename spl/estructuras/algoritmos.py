"""
Ejecutores de Alto Nivel para los 3 Problemas Computacionales de la Libreria de Estructuras.

Tarea 29 - Integrante 7 (Algoritmos 2 y 3 & Suite de Tests):
  - Problema 1 (Vectores 1D): Merge Sort recursivo (spl/ejemplos/merge_sort.asm).
  - Problema 2A (Vectores 1D): Producto Punto dot(A, B) (spl/ejemplos/producto_punto.asm).
  - Problema 2B (Vectores 1D): Busqueda Binaria O(log N) (spl/ejemplos/busqueda_binaria.asm).
  - Problema 3A (Matrices 2D): Multiplicacion de Matrices C = A * B (spl/ejemplos/multiplicacion_matrices.asm).
  - Problema 3B (Matrices 2D): Multiplicacion Matriz por Vector y = A * x (spl/ejemplos/multiplicacion_matrices.asm).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from .cargador import (
    ResultadoEjecucionEstructuras,
    cargar_y_ejecutar_estructuras,
)
from .descriptores import (
    BASE_BUFFERS,
    BASE_MATRICES,
    BASE_VECTORES,
    DescriptorMatriz,
    DescriptorVector,
    ErrorEstructuraDatos,
    desnormalizar_entero_64,
)
from .memoria import leer_matriz_de_ram, leer_vector_de_ram

RUTA_EJEMPLOS_DEFAULT: Path = Path(__file__).resolve().parents[1] / "ejemplos"
RUTA_ASM_MERGE_SORT: Path = RUTA_EJEMPLOS_DEFAULT / "merge_sort.asm"
RUTA_ASM_PRODUCTO_PUNTO: Path = RUTA_EJEMPLOS_DEFAULT / "producto_punto.asm"
RUTA_ASM_BUSQUEDA_BINARIA: Path = RUTA_EJEMPLOS_DEFAULT / "busqueda_binaria.asm"
RUTA_ASM_MULTIPLICACION_MATRICES: Path = RUTA_EJEMPLOS_DEFAULT / "multiplicacion_matrices.asm"

BASE_VEC_A: int = BASE_VECTORES            # 0x00220000
BASE_VEC_B: int = BASE_VECTORES + 0x100    # 0x00220100
BASE_VEC_RES: int = BASE_BUFFERS           # 0x002E0000

BASE_MAT_A: int = BASE_MATRICES            # 0x00260000
BASE_MAT_B: int = BASE_MATRICES + 0x200    # 0x00260200
BASE_MAT_C: int = BASE_MATRICES + 0x400    # 0x00260400


def ejecutar_merge_sort(
    elementos: Optional[Sequence[int]] = None,
    max_ciclos: int = 200_000,
) -> Tuple[List[int], ResultadoEjecucionEstructuras]:
    """
    Compila y ejecuta el Problema 1 (merge_sort.asm) sobre la CPU Enigma-64.
    Si elementos es None, ejecuta el vector autonomo por defecto de 8 elementos.
    Retorna (vector_ordenado, ResultadoEjecucionEstructuras).
    """
    estructuras = None
    if elementos is not None:
        estructuras = [
            DescriptorVector(
                nombre="vec_entrada",
                elementos=list(elementos),
                direccion_base=BASE_VECTORES,
                slot_cabecera=0,
            )
        ]
    ejecucion = cargar_y_ejecutar_estructuras(
        fuente_o_ruta=RUTA_ASM_MERGE_SORT,
        es_archivo=True,
        estructuras=estructuras,
        max_ciclos=max_ciclos,
    )
    ordenado = [int(v) for v in leer_vector_de_ram(ejecucion.ram, BASE_VECTORES, modo="int")]
    return ordenado, ejecucion


def ejecutar_producto_punto(
    vec_a: Optional[Sequence[int]] = None,
    vec_b: Optional[Sequence[int]] = None,
    max_ciclos: int = 100_000,
) -> Tuple[int, ResultadoEjecucionEstructuras]:
    """
    Compila y ejecuta el Problema 2A (producto_punto.asm) sobre la CPU Enigma-64.
    Si vec_a y vec_b son None, ejecuta los vectores autonomos por defecto.
    Retorna (producto_punto, ResultadoEjecucionEstructuras).
    """
    estructuras = None
    if vec_a is not None or vec_b is not None:
        if vec_a is None or vec_b is None:
            raise ErrorEstructuraDatos("Debe proporcionar tanto vec_a como vec_b, o ninguno.")
        if len(vec_a) != len(vec_b):
            raise ErrorEstructuraDatos(
                f"Los vectores para producto punto deben tener igual longitud: "
                f"{len(vec_a)} != {len(vec_b)}."
            )
        estructuras = [
            DescriptorVector(
                nombre="vec_a",
                elementos=list(vec_a),
                direccion_base=BASE_VEC_A,
                slot_cabecera=0,
            ),
            DescriptorVector(
                nombre="vec_b",
                elementos=list(vec_b),
                direccion_base=BASE_VEC_B,
                slot_cabecera=1,
            ),
        ]

    ejecucion = cargar_y_ejecutar_estructuras(
        fuente_o_ruta=RUTA_ASM_PRODUCTO_PUNTO,
        es_archivo=True,
        estructuras=estructuras,
        max_ciclos=max_ciclos,
    )
    res_vec = leer_vector_de_ram(ejecucion.ram, BASE_VEC_RES, longitud=1, modo="int")
    valor_r5 = desnormalizar_entero_64(ejecucion.banco.leer(5), con_signo=True)
    assert int(res_vec[0]) == valor_r5
    return valor_r5, ejecucion


def ejecutar_busqueda_binaria(
    vector_ordenado: Optional[Sequence[int]] = None,
    consultas: Optional[Sequence[int]] = None,
    max_ciclos: int = 100_000,
) -> Tuple[List[int], ResultadoEjecucionEstructuras]:
    """
    Compila y ejecuta el Problema 2B (busqueda_binaria.asm) sobre la CPU Enigma-64.
    Si vector_ordenado y consultas son None, ejecuta los datos autonomos por defecto.
    Retorna (lista_de_indices_encontrados, ResultadoEjecucionEstructuras).
    """
    estructuras = None
    if vector_ordenado is not None or consultas is not None:
        if vector_ordenado is None or consultas is None:
            raise ErrorEstructuraDatos(
                "Debe proporcionar tanto vector_ordenado como consultas, o ninguno."
            )
        estructuras = [
            DescriptorVector(
                nombre="vec_v",
                elementos=list(vector_ordenado),
                direccion_base=BASE_VEC_A,
                slot_cabecera=0,
            ),
            DescriptorVector(
                nombre="vec_q",
                elementos=list(consultas),
                direccion_base=BASE_VEC_B,
                slot_cabecera=1,
            ),
        ]

    ejecucion = cargar_y_ejecutar_estructuras(
        fuente_o_ruta=RUTA_ASM_BUSQUEDA_BINARIA,
        es_archivo=True,
        estructuras=estructuras,
        max_ciclos=max_ciclos,
    )
    indices = [int(v) for v in leer_vector_de_ram(ejecucion.ram, BASE_VEC_RES, modo="int")]
    return indices, ejecucion


def ejecutar_multiplicacion_matrices(
    matriz_a: Optional[Sequence[Sequence[int]]] = None,
    matriz_b: Optional[Sequence[Sequence[int]]] = None,
    vector_x: Optional[Sequence[int]] = None,
    max_ciclos: int = 300_000,
) -> Tuple[List[List[int]], Optional[List[int]], ResultadoEjecucionEstructuras]:
    """
    Compila y ejecuta el Problema 3 (multiplicacion_matrices.asm) sobre la CPU Enigma-64.
    Calcula C = A * B en 0x00260400 y, si se suministra vector_x (o en modo autonomo),
    calcula tambien y = A * x en 0x00220100.
    Retorna (matriz_c, vector_y_opcional, ResultadoEjecucionEstructuras).
    """
    estructuras = None
    if matriz_a is not None or matriz_b is not None:
        if matriz_a is None or matriz_b is None:
            raise ErrorEstructuraDatos("Debe proporcionar tanto matriz_a como matriz_b, o ninguna.")
        desc_a = DescriptorMatriz.desde_filas(
            nombre="mat_a",
            filas_2d=matriz_a,
            direccion_base=BASE_MAT_A,
            slot_cabecera=0,
        )
        desc_b = DescriptorMatriz.desde_filas(
            nombre="mat_b",
            filas_2d=matriz_b,
            direccion_base=BASE_MAT_B,
            slot_cabecera=1,
        )
        if desc_a.columnas != desc_b.filas:
            raise ErrorEstructuraDatos(
                f"Dimensiones incompatibles para A * B: A es {desc_a.filas}x{desc_a.columnas} "
                f"y B es {desc_b.filas}x{desc_b.columnas}."
            )
        estructuras = [desc_a, desc_b]
        if vector_x is not None:
            if len(vector_x) != desc_a.columnas:
                raise ErrorEstructuraDatos(
                    f"Dimensiones incompatibles para A * x: A tiene {desc_a.columnas} columnas "
                    f"y x tiene longitud {len(vector_x)}."
                )
            estructuras.append(
                DescriptorVector(
                    nombre="vec_x",
                    elementos=list(vector_x),
                    direccion_base=BASE_VEC_A,
                    slot_cabecera=3,
                )
            )

    ejecucion = cargar_y_ejecutar_estructuras(
        fuente_o_ruta=RUTA_ASM_MULTIPLICACION_MATRICES,
        es_archivo=True,
        estructuras=estructuras,
        max_ciclos=max_ciclos,
    )
    mat_c_raw = leer_matriz_de_ram(ejecucion.ram, BASE_MAT_C, modo="int")
    mat_c = [[int(val) for val in fila] for fila in mat_c_raw]

    vec_y: Optional[List[int]] = None
    if estructuras is None or vector_x is not None:
        vec_y = [int(v) for v in leer_vector_de_ram(ejecucion.ram, BASE_VEC_B, modo="int")]

    return mat_c, vec_y, ejecucion


def ejecutar_matriz_por_vector(
    matriz_a: Sequence[Sequence[int]],
    vector_x: Sequence[int],
    max_ciclos: int = 200_000,
) -> Tuple[List[int], ResultadoEjecucionEstructuras]:
    """
    Compila y ejecuta multiplicacion_matrices.asm precargando unicamente la matriz A y el
    vector x para obtener y = A * x en 0x00220100.
    """
    desc_a = DescriptorMatriz.desde_filas(
        nombre="mat_a",
        filas_2d=matriz_a,
        direccion_base=BASE_MAT_A,
        slot_cabecera=0,
    )
    if len(vector_x) != desc_a.columnas:
        raise ErrorEstructuraDatos(
            f"Dimensiones incompatibles para A * x: A tiene {desc_a.columnas} columnas "
            f"y x tiene longitud {len(vector_x)}."
        )
    desc_x = DescriptorVector(
        nombre="vec_x",
        elementos=list(vector_x),
        direccion_base=BASE_VEC_A,
        slot_cabecera=3,
    )
    ejecucion = cargar_y_ejecutar_estructuras(
        fuente_o_ruta=RUTA_ASM_MULTIPLICACION_MATRICES,
        es_archivo=True,
        estructuras=[desc_a, desc_x],
        max_ciclos=max_ciclos,
    )
    vec_y = [int(v) for v in leer_vector_de_ram(ejecucion.ram, BASE_VEC_B, modo="int")]
    return vec_y, ejecucion
