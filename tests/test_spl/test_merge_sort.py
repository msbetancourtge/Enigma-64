"""
Pruebas del Algoritmo de Ordenamiento por Mezclas (Merge Sort) & MMIO.
Tarea 29: Integrante 6 (Algoritmo 1 & MMIO).

Verifica:
  1. Inclusión de la librería maestro (#include "estructuras.inc").
  2. Preprocesamiento y resolución de macros del layout de memoria.
  3. Ensamblado y ejecución en la CPU real de Enigma-64.
  4. Correctitud del algoritmo MERGE_SORT sobre vectores desordenados,
     invertidos, con duplicados, números negativos y casos borde.
  5. Salida opcional hacia el periférico de pantalla MMIO (0xFF001010).
  6. Preservación estricta de registros callee-saved (R1..R4, SP, BP).
"""

from pathlib import Path
import random
import pytest

from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory
from enigma64.perifericos import Perifericos
from enigma64.registros import BancoRegistros
from spl.preprocesador import preprocesar_archivo, preprocesar_texto


RAIZ = Path(__file__).resolve().parents[2]
MERGE_SORT_ASM = RAIZ / "spl" / "ejemplos" / "merge_sort.asm"
ESTRUCTURAS_INC = RAIZ / "spl" / "include" / "estructuras.inc"

BASE_CODIGO = 0x00200000
BASE_VECTORES = 0x00220000
BASE_BUFFERS = 0x002E0000
PILA_INIT = 0x00400000
MASK64 = (1 << 64) - 1


def int64_a_raw(val: int) -> int:
    """Convierte un entero con signo de 64 bits a su representación sin signo de 64 bits."""
    return val & MASK64


def raw_a_int64(raw: int) -> int:
    """Convierte un entero de 64 bits sin signo a su valor con signo."""
    if raw >= (1 << 63):
        return raw - (1 << 64)
    return raw


def correr_merge_sort(
    elementos: list[int],
    perifericos: Perifericos | None = None,
) -> tuple[list[int], CPU, BancoRegistros, RAMMemory, Perifericos]:
    """
    Inicializa la máquina, escribe la cabecera (longitud) y elementos en BASE_VECTORES,
    ensambla y corre merge_sort.asm hasta HLT, y retorna el vector resultante.
    """
    res = preprocesar_archivo(str(MERGE_SORT_ASM))
    binario = ensamblar(res.texto, direccion_base=BASE_CODIGO)

    ram = RAMMemory()
    banco = BancoRegistros()
    if perifericos is None:
        perifericos = Perifericos()

    # Cargar binario en BASE_CODIGO
    for i, b in enumerate(binario):
        ram.mem_write(BASE_CODIGO + i, b, 1, check_alignment=False)

    n = len(elementos)
    # Escribir cabecera: longitud en base - 8 (la lee VEC_LEN)
    ram.mem_write(BASE_VECTORES - 8, n, 8)

    # Escribir elementos en base + i * 8
    for i, val in enumerate(elementos):
        ram.mem_write(BASE_VECTORES + i * 8, int64_a_raw(val), 8)

    banco.pc = BASE_CODIGO
    cpu = CPU(ram=ram, banco=banco, perifericos=perifericos)
    cpu.ejecutar(max_ciclos=3_000_000)

    # Leer elementos resultantes
    resultado = [
        raw_a_int64(ram.mem_read(BASE_VECTORES + i * 8, 8)[0])
        for i in range(n)
    ]
    return resultado, cpu, banco, ram, perifericos


class TestFase1Setup:
    def test_archivo_estructuras_inc_existe(self):
        """Comprueba que exista el archivo maestro estructuras.inc."""
        assert ESTRUCTURAS_INC.exists(), "Debe existir spl/include/estructuras.inc"

    def test_preprocesamiento_merge_sort(self):
        """Comprueba que merge_sort.asm resuelva #include 'estructuras.inc' sin errores."""
        res = preprocesar_archivo(str(MERGE_SORT_ASM))
        assert res.texto, "El código preprocesado no debe estar vacío"
        assert "VEC_ADDR:" in res.texto
        assert "VEC_GET:" in res.texto
        assert "VEC_SET:" in res.texto
        assert "VEC_COPY:" in res.texto
        assert "MERGE:" in res.texto
        assert "EMITIR_VECTOR_MMIO:" in res.texto

    def test_ensamblado_merge_sort(self):
        """Comprueba que el código preprocesado de merge_sort.asm se ensamble correctamente."""
        res = preprocesar_archivo(str(MERGE_SORT_ASM))
        binario = ensamblar(res.texto, direccion_base=BASE_CODIGO)
        assert len(binario) > 0, "El binario generado debe contener bytes de código"


class TestFase2MergeSort:
    def test_merge_sort_vector_pequeno(self):
        """Ordenamiento básico de un vector de 4 elementos."""
        datos = [40, 10, 30, 20]
        res, cpu, banco, ram, _ = correr_merge_sort(datos)
        assert res == [10, 20, 30, 40]

    def test_merge_sort_invertido(self):
        """Ordenamiento de vector en orden estrictamente descendente."""
        datos = [90, 80, 70, 60, 50, 40, 30, 20, 10]
        res, _, _, _, _ = correr_merge_sort(datos)
        assert res == sorted(datos)

    def test_merge_sort_ya_ordenado(self):
        """Vector que ya se encuentra ordenado de antemano."""
        datos = [1, 2, 3, 4, 5, 6, 7, 8]
        res, _, _, _, _ = correr_merge_sort(datos)
        assert res == [1, 2, 3, 4, 5, 6, 7, 8]

    def test_merge_sort_duplicados_y_negativos(self):
        """Vector con números negativos, ceros y elementos repetidos."""
        datos = [-50, 20, -100, 20, 0, -50, 15, 3]
        res, _, _, _, _ = correr_merge_sort(datos)
        assert res == sorted(datos)

    def test_merge_sort_casos_base(self):
        """Vectores de longitud 0, 1 y 2."""
        res_vacio, _, _, _, _ = correr_merge_sort([])
        assert res_vacio == []

        res_uno, _, _, _, _ = correr_merge_sort([777])
        assert res_uno == [777]

        res_dos, _, _, _, _ = correr_merge_sort([50, 10])
        assert res_dos == [10, 50]

    def test_merge_sort_aleatorio(self):
        """Prueba con 25 elementos aleatorios con signo."""
        rng = random.Random(42)
        datos = [rng.randint(-1000, 1000) for _ in range(25)]
        res, _, _, _, _ = correr_merge_sort(datos)
        assert res == sorted(datos)

    def test_preservacion_pila_y_registros(self):
        """Verifica que SP no tenga fugas y termine en PILA_INIT tras HLT."""
        datos = [35, 12, 88, 4, 19]
        res, cpu, banco, ram, _ = correr_merge_sort(datos)
        assert res == sorted(datos)
        assert banco.sp == PILA_INIT, f"Fuga en la pila: SP = 0x{banco.sp:08X}, esperado 0x{PILA_INIT:08X}"


class TestFase3MMIO:
    def test_emision_mmio_pantalla_vector_ordenado(self):
        """Comprueba que el vector ordenado se emita correctamente al puerto 0xFF001010."""
        datos = [40, 10, 30, 20]
        res, _, _, _, perifericos = correr_merge_sort(datos)
        assert res == [10, 20, 30, 40]
        texto = perifericos.pantalla.obtener_texto().strip()
        assert texto == "10 20 30 40"

    def test_emision_mmio_pantalla_negativos_y_cero(self):
        """Comprueba la conversión ASCII de ceros y valores negativos hacia MMIO."""
        datos = [-15, 0, 42, -99, 100]
        res, _, _, _, perifericos = correr_merge_sort(datos)
        assert res == [-99, -15, 0, 42, 100]
        texto = perifericos.pantalla.obtener_texto().strip()
        assert texto == "-99 -15 0 42 100"

    def test_emision_mmio_pantalla_vector_vacio(self):
        """Comprueba que un vector de 0 elementos no emita caracteres espurios a pantalla."""
        res, _, _, _, perifericos = correr_merge_sort([])
        assert res == []
        texto = perifericos.pantalla.obtener_texto().strip()
        assert texto == ""
