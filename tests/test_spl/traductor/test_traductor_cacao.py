"""
Suite de Pruebas y Pipeline de Verificacion — Tarea 27 (Integrante 7).

Implementa las responsabilidades del Integrante 7 (Algoritmos & Tests):
  1. Paso de los 3 archivos .asm de CacaoCore-64 (cacao_euclides.asm,
     cacao_factorial.asm, cacao_fibonacci.asm) por el traductor LEX.
  2. Ensamblado a codigo de maquina Big-Endian, empaquetado .e64 con
     CargadorEnigma y ejecucion real en la CPU y RAMMemory de Enigma-64.
  3. Contraste automatizado directo contra los programas y resultados
     oficiales de la Tarea 10 (enigma64/programas.py):
       - Factorial: 5! = 120
       - Euclides : MCD(48, 18) = 6
       - Fibonacci: [0, 1, 1, 2, 3, 5, 8]
  4. Pruebas parametricas de equivalencia funcional entre los programas
     CacaoCore traducidos y los binarios nativos de la Tarea 10.

Autor: Integrante 7 - Algoritmos & Tests (Alejandro Arguello Munoz)
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from enigma64.cargador import MAGIC_ENIGMA, BinarioEnigma, CargadorEnigma
from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory, STATUS_READY
from enigma64.programas import inicializar_escenario_prueba, obtener_programas_tarea27
from enigma64.registros import BancoRegistros
from spl.traductor import (
    ARCHIVOS_ALGORITMOS_CACAO,
    RESULTADOS_OFICIALES_TAREA10,
    ProcesadorDirectivasCacao,
    TraductorCacaoEnigma,
    cargar_y_ejecutar_con_cargador,
    ejecutar_algoritmo_nativo_tarea10,
    ejecutar_en_enigma,
    ejecutar_pipeline_verificacion_cacao,
    exportar_ejecutable_e64,
    traducir_texto,
    verificar_algoritmo_cacao,
)


class TestPipelineTraduccionLexTresAlgoritmos(unittest.TestCase):
    """Verifica el paso de los 3 .asm de CacaoCore por el traductor LEX completo."""

    def test_existencia_tres_archivos_asm_cacao(self) -> None:
        for nombre in ("euclides", "factorial", "fibonacci"):
            self.assertIn(nombre, ARCHIVOS_ALGORITMOS_CACAO)
            ruta = ARCHIVOS_ALGORITMOS_CACAO[nombre]
            self.assertTrue(ruta.is_file(), f"No existe el archivo {ruta}")

    def test_traduccion_lex_euclides_alineacion_y_codigo(self) -> None:
        fuente = ARCHIVOS_ALGORITMOS_CACAO["euclides"].read_text(encoding="utf-8")
        res = traducir_texto(fuente)
        self.assertTrue(res.ok, f"Errores LEX en Euclides: {res.errores}")
        self.assertIn("a", res.variables)
        self.assertIn("b", res.variables)
        for var, addr in res.variables.items():
            self.assertGreaterEqual(addr, 0x00201000)
            self.assertEqual(addr % 8, 0, f"Variable {var} desalineada: 0x{addr:08X}")
        self.assertIn("HLT", res.codigo)

    def test_traduccion_lex_factorial_alineacion_y_codigo(self) -> None:
        fuente = ARCHIVOS_ALGORITMOS_CACAO["factorial"].read_text(encoding="utf-8")
        res = traducir_texto(fuente)
        self.assertTrue(res.ok, f"Errores LEX en Factorial: {res.errores}")
        self.assertIn("n", res.variables)
        self.assertIn("fact", res.variables)
        for var, addr in res.variables.items():
            self.assertGreaterEqual(addr, 0x00201000)
            self.assertEqual(addr % 8, 0, f"Variable {var} desalineada: 0x{addr:08X}")
        self.assertIn("MUL", res.codigo)
        self.assertIn("HLT", res.codigo)

    def test_traduccion_lex_fibonacci_alineacion_y_codigo(self) -> None:
        fuente = ARCHIVOS_ALGORITMOS_CACAO["fibonacci"].read_text(encoding="utf-8")
        res = traducir_texto(fuente)
        self.assertTrue(res.ok, f"Errores LEX en Fibonacci: {res.errores}")
        for clave in ("fib", "fib1", "fib2", "fib3", "fib4", "fib5", "fib6", "i", "res"):
            self.assertIn(clave, res.variables)
            addr = res.variables[clave]
            self.assertGreaterEqual(addr, 0x00201000)
            self.assertEqual(addr % 8, 0, f"Variable {clave} desalineada: 0x{addr:08X}")
        self.assertIn("HLT", res.codigo)


class TestContrasteOficialContraTarea10(unittest.TestCase):
    """
    Ejecuta en paralelo los 3 algoritmos traducidos desde CacaoCore-64 y los
    binarios oficiales de la Tarea 10 sobre la CPU y RAMMemory de Enigma-64,
    contrastando que produzcan exactamente los mismos resultados.
    """

    def test_contraste_factorial_5_es_120(self) -> None:
        verif = verificar_algoritmo_cacao("factorial", usar_cargador=True)
        self.assertTrue(verif.ok)
        self.assertTrue(verif.detenido_hlt_traducido)
        self.assertTrue(verif.detenido_hlt_nativo)
        self.assertEqual(verif.resultado_traducido, 120)
        self.assertEqual(verif.resultado_nativo_tarea10, 120)
        self.assertTrue(verif.coincide_con_tarea10)
        self.assertEqual(verif.salida_mmio_lineas[0], "120")

    def test_contraste_euclides_mcd_48_18_es_6(self) -> None:
        verif = verificar_algoritmo_cacao("euclides", usar_cargador=True)
        self.assertTrue(verif.ok)
        self.assertTrue(verif.detenido_hlt_traducido)
        self.assertTrue(verif.detenido_hlt_nativo)
        self.assertEqual(verif.resultado_traducido, 6)
        self.assertEqual(verif.resultado_nativo_tarea10, 6)
        self.assertTrue(verif.coincide_con_tarea10)
        self.assertEqual(verif.salida_mmio_lineas[0], "6")

    def test_contraste_fibonacci_7_terminos_oficiales(self) -> None:
        esperado = [0, 1, 1, 2, 3, 5, 8]
        verif = verificar_algoritmo_cacao("fibonacci", usar_cargador=True)
        self.assertTrue(verif.ok)
        self.assertTrue(verif.detenido_hlt_traducido)
        self.assertTrue(verif.detenido_hlt_nativo)
        self.assertEqual(verif.resultado_traducido, esperado)
        self.assertEqual(verif.resultado_nativo_tarea10, esperado)
        self.assertTrue(verif.coincide_con_tarea10)
        self.assertEqual(verif.salida_mmio_lineas[0], "8")

    def test_pipeline_verificacion_consolidado_tres_algoritmos(self) -> None:
        reporte = ejecutar_pipeline_verificacion_cacao(usar_cargador=True, verificar_mmio=True)
        self.assertTrue(reporte.exito_total)
        self.assertEqual(set(reporte.algoritmos.keys()), {"euclides", "factorial", "fibonacci"})
        self.assertGreater(reporte.total_instrucciones_traducidas, 0)
        self.assertGreater(reporte.total_ciclos_traducidos, 0)
        for clave, esperado in RESULTADOS_OFICIALES_TAREA10.items():
            self.assertEqual(reporte.algoritmos[clave].resultado_traducido, esperado)
            self.assertEqual(reporte.algoritmos[clave].resultado_nativo_tarea10, esperado)


class TestCargaEstructuradaE64YEjecucionCPU(unittest.TestCase):
    """
    Valida la generacion del archivo estructurado .e64 (cabecera b'ENIG'),
    carga mediante CargadorEnigma y ejecucion real en CPU + RAMMemory.
    """

    def test_exportacion_y_carga_e64_tres_algoritmos(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            for nombre, ruta in ARCHIVOS_ALGORITMOS_CACAO.items():
                with self.subTest(algoritmo=nombre):
                    fuente = ruta.read_text(encoding="utf-8")
                    res = traducir_texto(fuente)
                    self.assertTrue(res.ok)

                    proc = ProcesadorDirectivasCacao()
                    mapa = proc.procesar(fuente)
                    ruta_e64 = os.path.join(tmpdir, f"cacao_{nombre}.e64")
                    bin_e64 = exportar_ejecutable_e64(res.codigo, mapa, ruta_e64)

                    self.assertTrue(os.path.isfile(ruta_e64))
                    raw = Path(ruta_e64).read_bytes()
                    self.assertTrue(raw.startswith(MAGIC_ENIGMA))
                    self.assertEqual(bin_e64.entry_point, 0x00200000)

                    # Deserializar, cargar en RAM limpia y ejecutar en CPU
                    bin_leido = BinarioEnigma.deserializar_e64(raw)
                    ram = RAMMemory()
                    banco = BancoRegistros()
                    cpu = CPU(ram=ram, banco=banco)
                    cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)
                    cargador.cargar_binario(bin_leido, direccion_destino=0x00200000, configurar_cpu=True)
                    cpu.ejecutar(max_ciclos=500_000)
                    self.assertTrue(cpu.detenido)

    def test_integracion_programas_tarea27_en_enigma64_programas(self) -> None:
        progs_t27 = obtener_programas_tarea27()
        self.assertEqual(set(progs_t27.keys()), {"cacao_euclides", "cacao_factorial", "cacao_fibonacci"})

        for clave, prog in progs_t27.items():
            with self.subTest(programa=clave):
                ram = RAMMemory()
                banco = BancoRegistros()
                cpu = CPU(ram=ram, banco=banco)
                cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)

                inicializar_escenario_prueba(ram, banco, cargador, prog)
                cpu.ejecutar(max_ciclos=500_000)
                self.assertTrue(cpu.detenido)

                for dir_esperada, val_esperado in prog.salidas_esperadas_ram.items():
                    val_real, st = ram.mem_read(dir_esperada, size_bytes=8, check_alignment=True)
                    self.assertEqual(st, STATUS_READY)
                    self.assertEqual(val_real, val_esperado)


class TestEquivalenciaParametricaContraTarea10(unittest.TestCase):
    """
    Pruebas parametricas que verifican que para distintas entradas, el codigo
    de CacaoCore traducido por LEX produce exactamente el mismo resultado en
    RAM que el binario nativo oficial de la Tarea 10.
    """

    def test_factorial_parametrico_contra_tarea10(self) -> None:
        casos = [
            (0, 1),
            (1, 1),
            (3, 6),
            (4, 24),
            (5, 120),
            (6, 720),
            (7, 5040),
        ]
        for n_val, esperado in casos:
            with self.subTest(n=n_val):
                verif = verificar_algoritmo_cacao(
                    "factorial",
                    usar_cargador=True,
                    overrides_cacao={"n": n_val},
                    overrides_nativo_ram={0x00201000: n_val},
                    verificar_mmio=False,
                )
                self.assertTrue(verif.ok)
                self.assertEqual(verif.resultado_traducido, esperado)
                self.assertEqual(verif.resultado_nativo_tarea10, esperado)
                self.assertTrue(verif.coincide_con_tarea10)

    def test_euclides_parametrico_contra_tarea10(self) -> None:
        casos = [
            (48, 18, 6),
            (35, 14, 7),
            (100, 25, 25),
            (17, 13, 1),
            (270, 192, 6),
            (42, 42, 42),
        ]
        for a_val, b_val, esperado in casos:
            with self.subTest(a=a_val, b=b_val):
                verif = verificar_algoritmo_cacao(
                    "euclides",
                    usar_cargador=True,
                    overrides_cacao={"a": a_val, "b": b_val},
                    overrides_nativo_ram={0x00202000: a_val, 0x00202008: b_val},
                    verificar_mmio=False,
                )
                self.assertTrue(verif.ok)
                self.assertEqual(verif.resultado_traducido, esperado)
                self.assertEqual(verif.resultado_nativo_tarea10, esperado)
                self.assertTrue(verif.coincide_con_tarea10)


if __name__ == "__main__":
    unittest.main()
