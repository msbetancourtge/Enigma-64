"""
Pruebas del Algoritmo de Ordenamiento por Mezclas (Merge Sort) & MMIO.
Tarea 29: Integrante 6 (Algoritmo 1 & MMIO).

Verifica:
  1. Inclusión de la librería maestro (#include "estructuras.inc").
  2. Preprocesamiento y resolución de macros del layout de memoria.
  3. Ensamblado correcto de la estructura base del programa.
"""

from pathlib import Path
import pytest

from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory
from enigma64.registros import BancoRegistros
from spl.preprocesador import preprocesar_archivo, preprocesar_texto


RAIZ = Path(__file__).resolve().parents[2]
MERGE_SORT_ASM = RAIZ / "spl" / "ejemplos" / "merge_sort.asm"
ESTRUCTURAS_INC = RAIZ / "spl" / "include" / "estructuras.inc"

BASE_CODIGO = 0x00200000


def test_archivo_estructuras_inc_existe():
    """Comprueba que exista el archivo maestro estructuras.inc."""
    assert ESTRUCTURAS_INC.exists(), "Debe existir spl/include/estructuras.inc"


def test_preprocesamiento_merge_sort():
    """Comprueba que merge_sort.asm resuelva #include 'estructuras.inc' sin errores."""
    res = preprocesar_archivo(str(MERGE_SORT_ASM))
    assert res.texto, "El código preprocesado no debe estar vacío"
    assert "VEC_ADDR:" in res.texto
    assert "VEC_GET:" in res.texto
    assert "VEC_SET:" in res.texto
    assert "VEC_COPY:" in res.texto
    assert "BASE_VECTORES" in res.macros or "0x00220000" in res.texto


def test_ensamblado_merge_sort():
    """Comprueba que el código preprocesado de merge_sort.asm se ensamble correctamente."""
    res = preprocesar_archivo(str(MERGE_SORT_ASM))
    binario = ensamblar(res.texto, direccion_base=BASE_CODIGO)
    assert len(binario) > 0, "El binario generado debe contener bytes de código"
