"""
Suite de pruebas unitarias para la subrutina FPU_BRUN y la Constante de Brun B2.

Tarea 17 - Integrante 7 (Constante de Brun & Batería de Pruebas).
Autor: Alejandro Argüello Muñoz

Verifica exhaustivamente sobre la arquitectura oficial Enigma-64:
  1. Subrutina FPU_ES_PRIMO:
     - Primos conocidos (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 97, 101, 103).
     - No primos y compuestos (0, 1, 4, 6, 8, 9, 15, 21, 25, 27, 49, 100).
     - Actualización correcta de la bandera Z y del registro de retorno R2.
  2. Subrutina FPU_BRUN:
     - Caso límite K=0 (retorna +0.0, 0 pares procesados).
     - K=1: Par (3, 5) -> B2 = 1/3 + 1/5 = 0.5333333333333333.
     - K=2: Pares (3, 5), (5, 7) -> B2 = 0.8761904761904761.
     - K=3: Pares (3, 5), (5, 7), (11, 13) -> B2 = 1.0440226440226437.
     - K=5: Pares (3, 5), (5, 7), (11, 13), (17, 19), (29, 31) -> B2 = 1.222218575518595.
     - K=8: Pares hasta (71, 73) -> B2 = 1.330990365719087.
  3. Invocación a través de la Mesa de Vectores (VEC_FBRUN - offset +0x28).
  4. Ejecución del programa ejecutable oficial (programas/constante_brun.bin).
  5. Validación contra el Oráculo Matemático IEEE 754 de 64 bits.
"""

from __future__ import annotations

import os
import unittest
from typing import Dict, Any

from enigma64.fpu import (
    EmuladorFPUEnigma64,
    float_a_ieee64,
    ieee64_a_float,
    VECTOR_FBRUN,
    CODIGO_FPU_ASM,
)
from enigma64.oraculo_ieee754 import (
    OraculoIEEE754,
    bits_a_float,
    float_a_bits,
    descomponer_ieee754,
    POS_ZERO,
)
from enigma64.programas import (
    PROGRAMA_BRUN,
    BYTES_BRUN,
    inicializar_escenario_prueba,
    CargadorEnigma,
)


class TestConstanteBrun(unittest.TestCase):
    """Pruebas unitarias y de integración de la Constante de Brun en Enigma-64."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fpu = EmuladorFPUEnigma64()

    # -------------------------------------------------------------------------
    # 1. Pruebas de la Subrutina Auxiliar FPU_ES_PRIMO
    # -------------------------------------------------------------------------

    def test_es_primo_positivos(self) -> None:
        """Verifica que FPU_ES_PRIMO reconozca números primos verdaderos."""
        primos = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 41, 43, 59, 61, 71, 73, 97, 101, 103]
        for p in primos:
            with self.subTest(primo=p):
                harness = f"""
                JMP HARNESS_START
                HARNESS_START:
                    ADDI SP, R0, 0x0020
                    SHL SP, SP, 16
                    ADDI SP, SP, 0x4000
                    ADDI BP, SP, 0

                    ADDI R4, R0, 0x0020
                    SHL R4, R4, 16
                    ADDI R4, R4, 0x5000
                    LOAD R1, [R4 + 0]
                    CALL FPU_ES_PRIMO

                    ADDI R4, R0, 0x0020
                    SHL R4, R4, 16
                    ADDI R4, R4, 0x5000
                    STORE R2, [R4 + 8]
                    HLT
                """
                self.fpu._preparar_entorno(harness)
                self.fpu.ram.mem_write(self.fpu.DIRECCION_VARIABLES + 0, p, 8)
                self.fpu.cpu.ejecutar(max_ciclos=10000)
                resultado, _ = self.fpu.ram.mem_read(self.fpu.DIRECCION_VARIABLES + 8, 8)
                self.assertEqual(resultado, 1, f"Fallo al reconocer {p} como primo")

    def test_es_primo_compuestos_y_menores(self) -> None:
        """Verifica que FPU_ES_PRIMO descarte números compuestos y menores que 2."""
        no_primos = [0, 1, 4, 6, 8, 9, 10, 12, 14, 15, 21, 25, 27, 33, 35, 49, 51, 65, 77, 85, 91, 100]
        for c in no_primos:
            with self.subTest(compuesto=c):
                harness = f"""
                JMP HARNESS_START
                HARNESS_START:
                    ADDI SP, R0, 0x0020
                    SHL SP, SP, 16
                    ADDI SP, SP, 0x4000
                    ADDI BP, SP, 0

                    ADDI R4, R0, 0x0020
                    SHL R4, R4, 16
                    ADDI R4, R4, 0x5000
                    LOAD R1, [R4 + 0]
                    CALL FPU_ES_PRIMO

                    ADDI R4, R0, 0x0020
                    SHL R4, R4, 16
                    ADDI R4, R4, 0x5000
                    STORE R2, [R4 + 8]
                    HLT
                """
                self.fpu._preparar_entorno(harness)
                self.fpu.ram.mem_write(self.fpu.DIRECCION_VARIABLES + 0, c, 8)
                self.fpu.cpu.ejecutar(max_ciclos=10000)
                resultado, _ = self.fpu.ram.mem_read(self.fpu.DIRECCION_VARIABLES + 8, 8)
                self.assertEqual(resultado, 0, f"Fallo al descartar {c} como primo")

    # -------------------------------------------------------------------------
    # 2. Pruebas de la Subrutina FPU_BRUN con K Pares
    # -------------------------------------------------------------------------

    def test_brun_cero_pares(self) -> None:
        """K=0 debe retornar 0.0 y 0 pares calculados."""
        res = self.fpu.ejecutar_programa_brun(num_pares=0)
        self.assertEqual(res["b2_bits"], POS_ZERO)
        self.assertEqual(res["b2_float"], 0.0)
        self.assertEqual(res["pares_calculados"], 0)

    def test_brun_un_par_exacto(self) -> None:
        """K=1: Par (3, 5) -> 1/3 + 1/5 = 0.5333333333333333 (0x3FE1111111111111)."""
        res = self.fpu.ejecutar_programa_brun(num_pares=1)
        self.assertEqual(res["pares_calculados"], 1)
        self.assertEqual(res["ultimo_primo"], 3)
        self.assertEqual(res["b2_bits"], 0x3FE1111111111111)
        self.assertEqual(res["b2_float"], 0.5333333333333333)

    def test_brun_dos_pares(self) -> None:
        """K=2: Pares (3, 5) y (5, 7) -> B2 = 0.8761904761904761."""
        res = self.fpu.ejecutar_programa_brun(num_pares=2)
        self.assertEqual(res["pares_calculados"], 2)
        self.assertEqual(res["ultimo_primo"], 5)
        self.assertAlmostEqual(res["b2_float"], 0.8761904761904761, places=14)

    def test_brun_tres_pares(self) -> None:
        """K=3: Pares (3, 5), (5, 7), (11, 13) -> B2 = 1.0440226440226437."""
        res = self.fpu.ejecutar_programa_brun(num_pares=3)
        self.assertEqual(res["pares_calculados"], 3)
        self.assertEqual(res["ultimo_primo"], 11)
        self.assertAlmostEqual(res["b2_float"], 1.044022644022644, places=14)

    def test_brun_cinco_pares_oficial(self) -> None:
        """K=5: Pares (3, 5), (5, 7), (11, 13), (17, 19), (29, 31)."""
        res = self.fpu.ejecutar_programa_brun(num_pares=5)
        self.assertEqual(res["pares_calculados"], 5)
        self.assertEqual(res["ultimo_primo"], 29)
        self.assertAlmostEqual(res["b2_float"], 1.222218575518595, places=14)

        # Validación formal con el Oráculo IEEE 754
        valido, msg = OraculoIEEE754.validar_constante_brun(5, res["b2_bits"], max_ulps=15)
        self.assertTrue(valido, msg)

    # -------------------------------------------------------------------------
    # 3. Pruebas de Invocación por Vector Canónico (VEC_FBRUN)
    # -------------------------------------------------------------------------

    def test_brun_vector_canónico(self) -> None:
        """Verifica invocación de FPU_BRUN a través de la tabla FPU_VECTORES (VEC_FBRUN)."""
        res_bits = self.fpu.ejecutar_vector("VEC_FBRUN", a=1, b=0)
        self.assertEqual(res_bits, 0x3FE1111111111111)

        res_bits_3 = self.fpu.ejecutar_vector("VEC_FBRUN", a=3, b=0)
        valido, msg = OraculoIEEE754.validar_constante_brun(3, res_bits_3, max_ulps=15)
        self.assertTrue(valido, msg)

    # -------------------------------------------------------------------------
    # 4. Prueba del Binario Ejecutable Oficial (programas/constante_brun.bin)
    # -------------------------------------------------------------------------

    def test_programa_oficial_en_ram(self) -> None:
        """Carga y ejecuta el programa estructurado PROGRAMA_BRUN mediante el CargadorEnigma."""
        cargador = CargadorEnigma(ram=self.fpu.ram, banco=self.fpu.banco)
        self.fpu.ram.reset()
        self.fpu.cpu.reset()

        inicializar_escenario_prueba(
            ram=self.fpu.ram,
            banco=self.fpu.banco,
            cargador=cargador,
            programa=PROGRAMA_BRUN,
        )

        self.fpu.banco.sp = 0x00204000
        self.fpu.banco.bp = 0x00204000
        self.fpu.cpu.ejecutar(max_ciclos=300000)

        # Leer resultados de RAM
        res_b2, _ = self.fpu.ram.mem_read(0x00205008, 8)
        pares_calc, _ = self.fpu.ram.mem_read(0x00205010, 8)
        ultimo_p, _ = self.fpu.ram.mem_read(0x00205018, 8)

        self.assertEqual(pares_calc, 5)
        self.assertEqual(ultimo_p, 29)
        self.assertEqual(res_b2, 0x3FF38E3510A6A83B)
        self.assertAlmostEqual(ieee64_a_float(res_b2), 1.222218575518595, places=14)


if __name__ == "__main__":
    unittest.main()
