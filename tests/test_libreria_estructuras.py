"""
Suite de Pruebas de Extremo a Extremo de la Libreria de Estructuras de Datos (Tarea 29).

Integrante 7 (Algoritmos 2 y 3 & Suite de Tests):
Valida en conjunto el trabajo de los 7 integrantes sobre la CPU y RAMMemory de Enigma-64:
  - Integrante 1: Preprocesador (#include, #define, #ifdef/#ifndef, macros parametrizadas).
  - Integrante 2: Primitivas de vectores 1D (vec.asm: VEC_ADDR, VEC_GET, VEC_SET, VEC_SWAP, VEC_COPY, VEC_LEN).
  - Integrante 3: Primitivas de matrices 2D Row-Major (mat.asm: MAT_ADDR, MAT_GET, MAT_SET, MAT_CLEAR).
  - Integrante 4: Descriptores, cabeceras, normalizacion de 64 bits y cargador .e64 (cabeceras.asm, spl.estructuras).
  - Integrante 5: Stack frames (PUSH, POP, ENTER, LEAVE) y convencion de llamadas recursivas/anidadas.
  - Integrante 6: Problema 1 - Merge Sort recursivo y emision MMIO (merge_sort.asm).
  - Integrante 7: Problema 2 (Producto Punto y Busqueda Binaria en Vector) y
                  Problema 3 (Multiplicacion de Matrices A x B y Matriz por Vector A * x).
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pytest

from enigma64.cargador import CargadorEnigma
from enigma64.cpu import CPU
from enigma64.memoria import RAMMemory
from enigma64.perifericos import Perifericos
from enigma64.registros import BancoRegistros
from spl.estructuras import (
    BASE_BUFFERS,
    BASE_CABECERAS,
    BASE_MAT_A,
    BASE_MAT_B,
    BASE_MAT_C,
    BASE_MATRICES,
    BASE_VEC_A,
    BASE_VEC_B,
    BASE_VEC_RES,
    BASE_VECTORES,
    PILA_ESTRUCTURAS,
    RUTA_ASM_BUSQUEDA_BINARIA,
    RUTA_ASM_MERGE_SORT,
    RUTA_ASM_MULTIPLICACION_MATRICES,
    RUTA_ASM_PRODUCTO_PUNTO,
    TIPO_MATRIZ,
    TIPO_VECTOR,
    DescriptorMatriz,
    DescriptorVector,
    ErrorEstructuraDatos,
    cargar_y_ejecutar_estructuras,
    compilar_a_binario_e64,
    desnormalizar_entero_64,
    ejecutar_busqueda_binaria,
    ejecutar_matriz_por_vector,
    ejecutar_merge_sort,
    ejecutar_multiplicacion_matrices,
    ejecutar_producto_punto,
    exportar_estructuras_e64,
    leer_descriptor_de_ram,
    leer_matriz_de_ram,
    leer_vector_de_ram,
)
from spl.preprocesador import preprocesar_texto

RUTA_INCLUDE = Path(__file__).resolve().parents[1] / "spl" / "include"
RUTA_EJEMPLOS = Path(__file__).resolve().parents[1] / "spl" / "ejemplos"


# ==============================================================================
# 1. Preprocesador, Cabecera Maestra (estructuras.inc) y Macros de Direccionamiento
# ==============================================================================


class TestCabeceraMaestraYMacros:
    """Valida la inclusion modular de estructuras.inc y la expansion de macros."""

    def test_inclusion_solo_vectores_omite_mat_asm(self) -> None:
        codigo = '#include "estructuras.inc"\nHLT\n'
        expandido = preprocesar_texto(codigo, dirs_inclusion=[str(RUTA_INCLUDE)]).texto

        assert "VEC_ADDR:" in expandido
        assert "VEC_GET:" in expandido
        assert "DESC_VEC_INIT:" in expandido
        assert "MAT_ADDR:" not in expandido

    def test_inclusion_con_incluir_matrices_activa_mat_asm(self) -> None:
        codigo = '#define INCLUIR_MATRICES\n#include "estructuras.inc"\nHLT\n'
        expandido = preprocesar_texto(codigo, dirs_inclusion=[str(RUTA_INCLUDE)]).texto

        assert "VEC_ADDR:" in expandido
        assert "MAT_ADDR:" in expandido
        assert "MAT_GET:" in expandido
        assert "MAT_SET:" in expandido
        assert "MAT_CLEAR:" in expandido

    def test_macros_parametrizadas_vec_dir_y_mat_dir(self) -> None:
        codigo = (
            '#include "estructuras.inc"\n'
            "; Calculo estatico:\n"
            "ADDI R1, R0, VEC_DIR(0, 5)\n"
            "ADDI R2, R0, MAT_DIR(0, 4, 2, 3)\n"
            "HLT\n"
        )
        expandido = preprocesar_texto(codigo, dirs_inclusion=[str(RUTA_INCLUDE)]).texto
        assert "0 + (5 << 3)" in expandido
        assert "0 + ((2 * 4 + 3) << 3)" in expandido


# ==============================================================================
# 2. Primitivas de Vectores 1D (vec.asm + cabeceras.asm) en CPU y RAMMemory
# ==============================================================================


class TestPrimitivasVectoresCPU:
    """Valida las subrutinas de vec.asm y cabeceras.asm ejecutadas en la CPU Enigma-64."""

    def test_vec_init_set_get_swap_copy_len(self) -> None:
        codigo_asm = """
#include "estructuras.inc"

        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16

        ; Inicializar descriptor y vector en 0x00220000 (slot 0, N = 4)
        ADDI R1, R0, 0
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16
        ADDI R3, R0, 4
        CALL DESC_VEC_INIT

        ADD  R1, R2, R0             ; R1 = 0x00220000
        ADDI R2, R0, 0
        ADDI R3, R0, 100
        CALL VEC_SET
        ADDI R2, R0, 1
        ADDI R3, R0, -200
        CALL VEC_SET
        ADDI R2, R0, 2
        ADDI R3, R0, 300
        CALL VEC_SET
        ADDI R2, R0, 3
        ADDI R3, R0, 400
        CALL VEC_SET

        ; Intercambiar v[0] y v[3] -> [400, -200, 300, 100]
        ADDI R2, R0, 0
        ADDI R3, R0, 3
        CALL VEC_SWAP

        ; Copiar los 4 elementos a 0x002E0000 con VEC_COPY
        ADDI R1, R0, 0x002E
        SHL  R1, R1, 16             ; destino = 0x002E0000
        ADDI R2, R0, 4
        CALL VEC_INIT
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16             ; origen = 0x00220000
        ADDI R3, R0, 4
        CALL VEC_COPY

        ; Leer v[1] del vector copiado en R5
        ADDI R2, R0, 1
        CALL VEC_GET
        HLT
"""
        res = cargar_y_ejecutar_estructuras(codigo_asm, es_archivo=False)
        assert res.cpu.detenido is True
        assert res.banco.leer(6) == PILA_ESTRUCTURAS
        assert desnormalizar_entero_64(res.banco.leer(5)) == -200

        vec_original = leer_vector_de_ram(res.ram, BASE_VECTORES, modo="int")
        vec_copia = leer_vector_de_ram(res.ram, BASE_BUFFERS, modo="int")
        assert vec_original == [400, -200, 300, 100]
        assert vec_copia == [400, -200, 300, 100]

        desc = leer_descriptor_de_ram(res.ram, 0)
        assert desc["tipo"] == TIPO_VECTOR
        assert desc["direccion_base"] == BASE_VECTORES
        assert desc["longitud"] == 4


# ==============================================================================
# 3. Primitivas de Matrices 2D Row-Major (mat.asm + cabeceras.asm) en CPU y RAMMemory
# ==============================================================================


class TestPrimitivasMatricesCPU:
    """Valida las subrutinas de mat.asm y prueba_mat.asm sobre CPU y RAMMemory."""

    def test_ejemplo_prueba_mat_asm_completo(self) -> None:
        ruta_prueba = RUTA_EJEMPLOS / "prueba_mat.asm"
        res = cargar_y_ejecutar_estructuras(ruta_prueba, es_archivo=True)

        assert res.cpu.detenido is True
        assert res.banco.leer(5) == 6  # MAT_CLEAR sobre matriz 2x3 retorna F*C = 6
        assert res.banco.leer(6) == PILA_ESTRUCTURAS

        # Verificar los resultados guardados por prueba_mat.asm en 0x002E0000
        resultados = leer_vector_de_ram(res.ram, BASE_BUFFERS, longitud=9, modo="int")
        assert resultados[0] == 0x00260048  # MAT_ADDR(M, 2, 1)
        assert resultados[1] == 12          # MAT_GET(M, 1, 2)
        assert resultados[2] == 23          # MAT_GET(M, 2, 3)
        assert resultados[3] == 138         # SUMAR_MATRIZ(M)
        assert resultados[4] == 0x00260000  # R1 preservado
        assert resultados[5] == 3           # R3 preservado
        assert resultados[7] == 13          # VEC_GET sobre fila 1
        assert resultados[8] == 6           # MAT_CLEAR(N)

    def test_direccionamiento_row_major_y_descriptores_2d(self) -> None:
        codigo_asm = """
#define INCLUIR_MATRICES
#include "estructuras.inc"

        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16

        ; Crear matriz 3x3 en 0x00260000 con descriptor en slot 1
        ADDI R1, R0, 1
        ADDI R2, R0, 0x0026
        SHL  R2, R2, 16
        ADDI R3, R0, 3
        ADDI R4, R0, 3
        CALL DESC_MAT_INIT

        ADD  R1, R2, R0
        CALL MAT_CLEAR

        ; Escribir diagonal principal: M[0][0]=11, M[1][1]=-22, M[2][2]=33
        ADDI R2, R0, 0
        ADDI R3, R0, 0
        ADDI R4, R0, 11
        CALL MAT_SET

        ADDI R2, R0, 1
        ADDI R3, R0, 1
        ADDI R4, R0, -22
        CALL MAT_SET

        ADDI R2, R0, 2
        ADDI R3, R0, 2
        ADDI R4, R0, 33
        CALL MAT_SET

        ; Leer M[1][1] en R5
        ADDI R2, R0, 1
        ADDI R3, R0, 1
        CALL MAT_GET
        HLT
"""
        res = cargar_y_ejecutar_estructuras(codigo_asm, es_archivo=False)
        assert desnormalizar_entero_64(res.banco.leer(5)) == -22

        matriz = leer_matriz_de_ram(res.ram, BASE_MATRICES, modo="int")
        assert matriz == [
            [11, 0, 0],
            [0, -22, 0],
            [0, 0, 33],
        ]
        desc = leer_descriptor_de_ram(res.ram, 1)
        assert desc["tipo"] == TIPO_MATRIZ
        assert desc["filas"] == 3
        assert desc["columnas"] == 3


# ==============================================================================
# 4. Problema Computacional 1: Merge Sort en Vector (merge_sort.asm)
# ==============================================================================


class TestProblema1MergeSort:
    """Valida el Problema 1 (Merge Sort recursivo + salida MMIO) en CPU y RAMMemory."""

    def test_merge_sort_modo_autonomo_y_mmio(self) -> None:
        ordenado, res = ejecutar_merge_sort()
        assert res.cpu.detenido is True
        assert ordenado == [-12, -5, 0, 10, 23, 45, 77, 89]
        assert res.salida_mmio.strip() == "-12 -5 0 10 23 45 77 89"

    @pytest.mark.parametrize(
        "entrada",
        [
            [100, 50, 25, 0, -25, -50, -100],
            [5, 5, 1, 3, 3, -2, -2, 0],
            [42],
            [-999, 1000, -1, 0, 1, -1000, 999],
            [1, 2, 3, 4, 5, 6],
        ],
    )
    def test_merge_sort_con_vectores_precargados(self, entrada: List[int]) -> None:
        ordenado, res = ejecutar_merge_sort(entrada)
        assert res.cpu.detenido is True
        assert ordenado == sorted(entrada)


# ==============================================================================
# 5. Problema Computacional 2: Producto Punto y Busqueda Binaria en Vector
# ==============================================================================


class TestProblema2Vectores:
    """Valida el Problema 2 (Producto Punto y Busqueda Binaria) en CPU y RAMMemory."""

    def test_producto_punto_modo_autonomo(self) -> None:
        # A = [3, -4, 7, 2, -5], B = [6, 5, 2, -3, -4] -> 18 - 20 + 14 - 6 + 20 = 26
        valor, res = ejecutar_producto_punto()
        assert res.cpu.detenido is True
        assert res.banco.leer(6) == PILA_ESTRUCTURAS
        assert valor == 26

        desc_res = leer_descriptor_de_ram(res.ram, 2)
        assert desc_res["tipo"] == TIPO_VECTOR
        assert desc_res["direccion_base"] == BASE_VEC_RES
        assert desc_res["longitud"] == 1

    @pytest.mark.parametrize(
        ("vec_a", "vec_b", "esperado"),
        [
            ([1, 2, 3, 4], [5, 6, 7, 8], 70),
            ([2, -3, 1], [3, 2, 0], 0),  # Vectores ortogonales
            ([-10, -20, -30], [1, -2, 3], -60),
            ([15], [-7], -105),
            ([0, 0, 0, 0], [99, -88, 77, -66], 0),
            ([10, 20, 30, 40, 50, 60], [6, 5, 4, 3, 2, 1], 560),
        ],
    )
    def test_producto_punto_parametrico(
        self, vec_a: List[int], vec_b: List[int], esperado: int
    ) -> None:
        valor, res = ejecutar_producto_punto(vec_a, vec_b)
        assert res.cpu.detenido is True
        assert valor == esperado
        assert sum(a * b for a, b in zip(vec_a, vec_b)) == valor

    def test_producto_punto_rechaza_longitudes_distintas(self) -> None:
        with pytest.raises(ErrorEstructuraDatos, match="igual longitud"):
            ejecutar_producto_punto([1, 2, 3], [1, 2])

    def test_busqueda_binaria_modo_autonomo(self) -> None:
        # V = [-20, -5, 0, 7, 15, 23, 42, 88], Q = [23, -20, 88, 19] -> [5, 0, 7, -1]
        indices, res = ejecutar_busqueda_binaria()
        assert res.cpu.detenido is True
        assert res.banco.leer(6) == PILA_ESTRUCTURAS
        assert indices == [5, 0, 7, -1]
        assert desnormalizar_entero_64(res.banco.leer(5)) == 5

    def test_busqueda_binaria_todos_los_elementos_y_ausentes(self) -> None:
        vector = [-150, -40, -1, 0, 8, 19, 34, 100, 512]
        consultas_presentes = list(vector)
        indices_presentes, _ = ejecutar_busqueda_binaria(vector, consultas_presentes)
        assert indices_presentes == list(range(len(vector)))

        consultas_ausentes = [-200, -50, -2, 1, 20, 99, 600]
        indices_ausentes, res_aus = ejecutar_busqueda_binaria(vector, consultas_ausentes)
        assert indices_ausentes == [-1] * len(consultas_ausentes)
        assert desnormalizar_entero_64(res_aus.banco.leer(5)) == -1

    def test_busqueda_binaria_vector_unitario(self) -> None:
        indices, _ = ejecutar_busqueda_binaria([42], [42, -42, 0])
        assert indices == [0, -1, -1]


# ==============================================================================
# 6. Problema Computacional 3: Multiplicacion de Matrices (A x B) y Matriz por Vector
# ==============================================================================


def _matmul_ref(a: List[List[int]], b: List[List[int]]) -> List[List[int]]:
    filas_a, k = len(a), len(a[0])
    cols_b = len(b[0])
    return [[sum(a[i][p] * b[p][j] for p in range(k)) for j in range(cols_b)] for i in range(filas_a)]


def _matvec_ref(a: List[List[int]], x: List[int]) -> List[int]:
    return [sum(fila[k] * x[k] for k in range(len(x))) for fila in a]


class TestProblema3Matrices:
    """Valida el Problema 3 (Multiplicacion de Matrices y Matriz por Vector) en CPU y RAMMemory."""

    def test_multiplicacion_matrices_modo_autonomo(self) -> None:
        mat_c, vec_y, res = ejecutar_multiplicacion_matrices()
        assert res.cpu.detenido is True
        assert res.banco.leer(6) == PILA_ESTRUCTURAS
        assert mat_c == [
            [14, 10],
            [16, 17],
        ]
        assert vec_y == [9, 15]
        assert desnormalizar_entero_64(res.banco.leer(5)) == 14

        desc_c = leer_descriptor_de_ram(res.ram, 2)
        assert desc_c["tipo"] == TIPO_MATRIZ
        assert desc_c["direccion_base"] == BASE_MAT_C
        assert desc_c["filas"] == 2
        assert desc_c["columnas"] == 2

    @pytest.mark.parametrize(
        ("mat_a", "mat_b"),
        [
            # Cuadradas 2x2
            (
                [[3, -2], [5, 4]],
                [[-1, 6], [7, -3]],
            ),
            # Cuadradas 3x3 con identidad
            (
                [[9, -4, 2], [0, 11, -7], [5, 3, 8]],
                [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            ),
            # Cuadradas 3x3 generales
            (
                [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
                [[9, 8, 7], [6, 5, 4], [3, 2, 1]],
            ),
            # Rectangulares 3x4 por 4x2
            (
                [[2, -1, 0, 3], [4, 2, -2, 1], [-3, 0, 5, -1]],
                [[1, 2], [-3, 4], [2, -1], [0, 5]],
            ),
            # Producto fila (1x4) por columna (4x1) -> escalar 1x1
            (
                [[4, -3, 2, -1]],
                [[5], [6], [7], [8]],
            ),
            # Multiplicacion por matriz nula
            (
                [[12, -34], [56, -78]],
                [[0, 0], [0, 0]],
            ),
        ],
    )
    def test_multiplicacion_matrices_parametrica(
        self, mat_a: List[List[int]], mat_b: List[List[int]]
    ) -> None:
        esperado = _matmul_ref(mat_a, mat_b)
        mat_c, vec_y, res = ejecutar_multiplicacion_matrices(mat_a, mat_b)
        assert res.cpu.detenido is True
        assert mat_c == esperado
        assert vec_y is None
        assert desnormalizar_entero_64(res.banco.leer(5)) == esperado[0][0]

    @pytest.mark.parametrize(
        ("mat_a", "vec_x"),
        [
            ([[1, 2, 3], [4, -1, 2]], [2, -1, 3]),
            ([[5, 0, -2], [-3, 4, 1], [2, 2, 2]], [10, -5, 3]),
            ([[7, -8, 9, -10]], [1, 2, 3, 4]),
        ],
    )
    def test_multiplicacion_matriz_por_vector_independiente(
        self, mat_a: List[List[int]], vec_x: List[int]
    ) -> None:
        esperado = _matvec_ref(mat_a, vec_x)
        vec_y, res = ejecutar_matriz_por_vector(mat_a, vec_x)
        assert res.cpu.detenido is True
        assert vec_y == esperado
        assert desnormalizar_entero_64(res.banco.leer(5)) == esperado[0]

    def test_multiplicacion_matrices_rechaza_dimensiones_incompatibles(self) -> None:
        with pytest.raises(ErrorEstructuraDatos, match="Dimensiones incompatibles"):
            ejecutar_multiplicacion_matrices([[1, 2, 3]], [[1, 2], [3, 4]])


# ==============================================================================
# 7. Empaquetado a Binario (.e64) y Carga Mediante CargadorEnigma
# ==============================================================================


class TestEmpaquetadoBinarioE64:
    """Verifica que los 3 problemas computacionales se exportan y cargan como .e64."""

    @pytest.mark.parametrize(
        "ruta_asm",
        [
            RUTA_ASM_MERGE_SORT,
            RUTA_ASM_PRODUCTO_PUNTO,
            RUTA_ASM_BUSQUEDA_BINARIA,
            RUTA_ASM_MULTIPLICACION_MATRICES,
        ],
    )
    def test_exportar_y_ejecutar_binario_e64_de_los_problemas(
        self, tmp_path: Path, ruta_asm: Path
    ) -> None:
        ruta_e64 = tmp_path / f"{ruta_asm.stem}.e64"
        binario = exportar_estructuras_e64(ruta_asm, ruta_e64, es_archivo=True)
        assert ruta_e64.exists()
        assert len(binario.codigo) > 0

        ram = RAMMemory()
        banco = BancoRegistros()
        perifericos = Perifericos()
        cpu = CPU(ram=ram, banco=banco, perifericos=perifericos)
        cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)
        info = cargador.cargar_archivo(str(ruta_e64), configurar_cpu=True)
        banco.sp = PILA_ESTRUCTURAS
        assert info["entry_point"] == 0x00200000

        res_ejec = cpu.ejecutar(max_ciclos=200_000)
        assert cpu.detenido is True
        assert res_ejec["ciclos"] > 0
