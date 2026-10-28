"""
Bateria de Pruebas Unitarias y de Integracion — Tarea 27.
Traductor de ensamblador CacaoCore-64 a Enigma-64.

Valida el ciclo completo de procesamiento:
  1. Compilacion de CacaoScript (.cac) a ensamblador CacaoCore-64 (.asm)
  2. Traduccion de CacaoCore-64 a Enigma-64 mediante reglas LEX
  3. Ejecucion en el emulador de Enigma-64 y verificacion de resultados:
     - Euclides: MCD(48, 18) = 6
     - Factorial: 5! = 120
     - Fibonacci: [0, 1, 1, 2, 3, 5, 8]
  4. Soporte y emision por MMIO (Controlador de Pantalla 0xFF001000 / 0xFF001010)
"""

from __future__ import annotations

import unittest
from pathlib import Path

from enigma64.cpu import CPU
from enigma64.memoria import RAMMemory
from enigma64.perifericos import (
    BASE_PANTALLA,
    OFFSET_DATA,
    ControladorPantalla,
    Perifericos,
)
from enigma64.registros import BancoRegistros
from spl.traductor import traducir_texto
from spl.traductor.mmio_soporte import (
    ejecutar_en_enigma_mmio,
    generar_emision_ascii_mmio,
    inyectar_salida_mmio,
)
from tools.compilar_algoritmos_cacao import (
    buscar_cacaocore_src,
    compilar_archivo_cacao,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
SRC_DIR = BASE_DIR / "spl" / "traductor" / "cacaocore_src"
EJEMPLOS_DIR = BASE_DIR / "spl" / "traductor" / "ejemplos"


class TestCompilacionCacaoScript(unittest.TestCase):
    """Pruebas de la etapa de alto nivel y compilacion de CacaoScript."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.cacao_src = buscar_cacaocore_src()
        except FileNotFoundError:
            cls.cacao_src = None

    def test_existencia_archivos_fuente_cac(self) -> None:
        self.assertTrue((SRC_DIR / "euclides.cac").is_file(), "Falta euclides.cac")
        self.assertTrue((SRC_DIR / "factorial.cac").is_file(), "Falta factorial.cac")
        self.assertTrue((SRC_DIR / "fibonacci.cac").is_file(), "Falta fibonacci.cac")

    def test_compilacion_euclides_produce_asm_valido(self) -> None:
        if self.cacao_src is None:
            self.skipTest("CacaoCore-64 src no disponible en entorno de pruebas")
        lineas = compilar_archivo_cacao(SRC_DIR / "euclides.cac", self.cacao_src)
        self.assertIn(".data", lineas)
        self.assertIn(".text", lineas)
        self.assertTrue(any("MOVD" in l for l in lineas))
        self.assertTrue(any("HLT" in l for l in lineas))

    def test_compilacion_factorial_produce_asm_valido(self) -> None:
        if self.cacao_src is None:
            self.skipTest("CacaoCore-64 src no disponible en entorno de pruebas")
        lineas = compilar_archivo_cacao(SRC_DIR / "factorial.cac", self.cacao_src)
        self.assertIn(".data", lineas)
        self.assertIn(".text", lineas)
        self.assertTrue(any("MUL" in l for l in lineas))
        self.assertTrue(any("HLT" in l for l in lineas))

    def test_compilacion_fibonacci_produce_asm_valido(self) -> None:
        if self.cacao_src is None:
            self.skipTest("CacaoCore-64 src no disponible en entorno de pruebas")
        lineas = compilar_archivo_cacao(SRC_DIR / "fibonacci.cac", self.cacao_src)
        self.assertIn(".data", lineas)
        self.assertIn(".text", lineas)
        self.assertTrue(any("ADD" in l for l in lineas))
        self.assertTrue(any("HLT" in l for l in lineas))


class TestTraduccionCacaoCoreAEnigma(unittest.TestCase):
    """Pruebas de la etapa de traduccion LEX CacaoCore -> Enigma-64."""

    def test_traduccion_cacao_euclides_sin_errores(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_euclides.asm"
        self.assertTrue(ruta_asm.is_file(), "Debe existir cacao_euclides.asm")
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        self.assertTrue(res.ok, f"Errores en traduccion: {res.errores}")
        self.assertIn("a", res.variables)
        self.assertIn("b", res.variables)
        self.assertGreaterEqual(res.variables["a"], 0x00201000)

    def test_traduccion_cacao_factorial_sin_errores(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_factorial.asm"
        self.assertTrue(ruta_asm.is_file(), "Debe existir cacao_factorial.asm")
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        self.assertTrue(res.ok, f"Errores en traduccion: {res.errores}")
        self.assertIn("n", res.variables)
        self.assertIn("fact", res.variables)
        self.assertGreaterEqual(res.variables["fact"], 0x00201000)

    def test_traduccion_cacao_fibonacci_sin_errores(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_fibonacci.asm"
        self.assertTrue(ruta_asm.is_file(), "Debe existir cacao_fibonacci.asm")
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        self.assertTrue(res.ok, f"Errores en traduccion: {res.errores}")
        self.assertIn("fib", res.variables)
        self.assertIn("res", res.variables)
        self.assertGreaterEqual(res.variables["res"], 0x00201000)


class TestEjecucionEnigma64ValoresOficiales(unittest.TestCase):
    """Ejecucion real en Enigma-64 y contraste con los resultados de la Tarea 10."""

    def test_euclides_mcd_48_18_es_6(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_euclides.asm"
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        cpu, banco, ram, perifs = ejecutar_en_enigma_mmio(res.codigo)

        addr_a = res.variables["a"]
        mcd, _ = ram.mem_read(addr_a, 8)
        self.assertEqual(mcd, 6, "MCD(48, 18) debe ser 6")

    def test_factorial_5_es_120(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_factorial.asm"
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        cpu, banco, ram, perifs = ejecutar_en_enigma_mmio(res.codigo)

        addr_fact = res.variables["fact"]
        factorial, _ = ram.mem_read(addr_fact, 8)
        self.assertEqual(factorial, 120, "5! debe ser 120")

    def test_fibonacci_7_terminos(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_fibonacci.asm"
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        cpu, banco, ram, perifs = ejecutar_en_enigma_mmio(res.codigo)

        nombres = ["fib", "fib1", "fib2", "fib3", "fib4", "fib5", "fib6"]
        valores = [ram.mem_read(res.variables[nom], 8)[0] for nom in nombres]
        self.assertEqual(valores, [0, 1, 1, 2, 3, 5, 8], "Fibonacci debe ser [0, 1, 1, 2, 3, 5, 8]")

        val_res, _ = ram.mem_read(res.variables["res"], 8)
        self.assertEqual(val_res, 8, "El termino final res debe ser 8")


class TestSoporteSalidaMMIO(unittest.TestCase):
    """Pruebas del puente de salida MMIO (Base 0xFF001000 / Registro DATA 0xFF001010)."""

    def test_emision_mmio_euclides_muestra_6_en_pantalla(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_euclides.asm"
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        codigo_mmio = inyectar_salida_mmio(res.codigo, res.variables, ["a"])

        perifs = Perifericos()
        cpu, banco, ram, perifs = ejecutar_en_enigma_mmio(codigo_mmio, perifericos=perifs)

        lineas = perifs.controlador_pantalla.obtener_lineas()
        self.assertEqual(lineas[0], "6", "La linea 0 de la terminal CRT debe mostrar '6'")
        self.assertGreater(perifs.controlador_pantalla.count, 0)

    def test_emision_mmio_factorial_muestra_120_en_pantalla(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_factorial.asm"
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        codigo_mmio = inyectar_salida_mmio(res.codigo, res.variables, ["fact"])

        perifs = Perifericos()
        cpu, banco, ram, perifs = ejecutar_en_enigma_mmio(codigo_mmio, perifericos=perifs)

        lineas = perifs.controlador_pantalla.obtener_lineas()
        self.assertEqual(lineas[0], "120", "La linea 0 de la terminal CRT debe mostrar '120'")

    def test_emision_mmio_fibonacci_muestra_8_en_pantalla(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_fibonacci.asm"
        res = traducir_texto(ruta_asm.read_text(encoding="utf-8"))
        codigo_mmio = inyectar_salida_mmio(res.codigo, res.variables, ["res"])

        perifs = Perifericos()
        cpu, banco, ram, perifs = ejecutar_en_enigma_mmio(codigo_mmio, perifericos=perifs)

        lineas = perifs.controlador_pantalla.obtener_lineas()
        self.assertEqual(lineas[0], "8", "La linea 0 de la terminal CRT debe mostrar '8'")
