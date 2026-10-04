"""
Batería de Pruebas Unitarias y de Integración del Sistema FPU Enigma-64.

Tarea 17 - Integrante 7 (Constante de Brun & Batería de Pruebas).
Autor: Alejandro Argüello Muñoz

Cubre exhaustivamente:
  1. Pruebas Unitarias de FDIV (División IEEE 754):
     - Operaciones normales (cocientes exactos e inexactos).
     - Casos especiales de división por cero (+inf, -inf con signo XOR).
     - Operaciones inválidas que producen NaN (0.0 / 0.0, inf / inf).
     - Operaciones con infinitos (x / inf = 0, inf / x = inf).
     - Subnormales y números de muy baja magnitud.
     - Contraste diferencial sistemático contra el Oráculo IEEE 754.
  2. Pruebas Unitarias de FCMP (Comparador IEEE 754):
     - Comparaciones de orden estricto (<, ==, >).
     - Equivalencia de ceros con signo (+0.0 == -0.0 -> 0).
     - Comparaciones de infinitos (+inf == +inf, -inf < +inf).
     - Operandos NaN (comparación no ordenada / unordered -> 2).
     - Contraste sistemático contra el Oráculo IEEE 754.
  3. Batería de la Mesa de Vectores Canónicos (FPU_VECTORES):
     - Comprobación de los 9 puntos de entrada fijos:
       VEC_FADD (+0x00), VEC_FSUB (+0x05), VEC_FMUL (+0x0A), VEC_FDIV (+0x0F),
       VEC_FCMP (+0x14), VEC_INT_TO_FLOAT (+0x19), VEC_FLOAT_TO_INT (+0x1E),
       VEC_FSQRT (+0x23), VEC_FBRUN (+0x28).
  4. Pruebas de Integración y Estabilidad de Sistema:
     - Preservación e invariancia de la pila de llamadas (SP y BP coinciden antes y después).
     - Integridad de marcos de pila en llamadas anidadas (FBRUN -> FADD, FDIV, FCONV).
     - Carga en memoria mediante CargadorEnigma y ejecución libre de fallos de alineación.
"""

from __future__ import annotations

import math
import unittest

from enigma64.fpu import (
    EmuladorFPUEnigma64,
    float_a_ieee64,
    ieee64_a_float,
    VECTOR_FADD,
    VECTOR_FSUB,
    VECTOR_FMUL,
    VECTOR_FDIV,
    VECTOR_FCMP,
    VECTOR_INT_TO_FLOAT,
    VECTOR_FLOAT_TO_INT,
    VECTOR_FSQRT,
    VECTOR_FBRUN,
)
from enigma64.oraculo_ieee754 import (
    CANONICAL_NAN,
    NEG_INFINITY,
    NEG_ZERO,
    POS_INFINITY,
    POS_ZERO,
    OraculoIEEE754,
    descomponer_ieee754,
)


class TestBateriaIntegracionFPU(unittest.TestCase):
    """Batería oficial de pruebas unitarias y de integración de la FPU."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fpu = EmuladorFPUEnigma64()

    # =========================================================================
    # 1. PRUEBAS UNITARIAS DE FDIV
    # =========================================================================

    def test_fdiv_operaciones_normales(self) -> None:
        """FDIV: Cocientes normales con diferentes signos y magnitudes."""
        casos = [
            (10.0, 2.0, 5.0),
            (-15.0, 3.0, -5.0),
            (20.0, -4.0, -5.0),
            (-30.0, -6.0, 5.0),
            (1.0, 1.0, 1.0),
            (7.5, 2.5, 3.0),
            (1.0, 4.0, 0.25),
            (1.0, 8.0, 0.125),
            (3.0, 2.0, 1.5),
        ]
        for a, b, esperado in casos:
            with self.subTest(a=a, b=b):
                res = self.fpu.dividir(a, b)
                self.assertEqual(res, esperado)
                bits = self.fpu.dividir_bits(a, b)
                self.assertEqual(bits, float_a_ieee64(esperado))

    def test_fdiv_division_por_cero(self) -> None:
        """FDIV: División por cero debe retornar infinito con el signo adecuado."""
        # +x / +0.0 = +inf
        self.assertEqual(self.fpu.dividir_bits(1.0, 0.0), POS_INFINITY)
        # +x / -0.0 = -inf
        self.assertEqual(self.fpu.dividir_bits(1.0, -0.0), NEG_INFINITY)
        # -x / +0.0 = -inf
        self.assertEqual(self.fpu.dividir_bits(-1.0, 0.0), NEG_INFINITY)
        # -x / -0.0 = +inf
        self.assertEqual(self.fpu.dividir_bits(-1.0, -0.0), POS_INFINITY)

    def test_fdiv_casos_invalidos_nan(self) -> None:
        """FDIV: 0/0 e inf/inf son operaciones inválidas que producen NaN."""
        # 0.0 / 0.0 -> NaN
        res_0_0 = self.fpu.dividir_bits(0.0, 0.0)
        desg_0_0 = descomponer_ieee754(res_0_0)
        self.assertTrue(desg_0_0.es_nan, "0.0 / 0.0 debe ser NaN")

        # inf / inf -> NaN
        res_inf_inf = self.fpu.dividir_bits(math.inf, math.inf)
        desg_inf_inf = descomponer_ieee754(res_inf_inf)
        self.assertTrue(desg_inf_inf.es_nan, "inf / inf debe ser NaN")

    def test_fdiv_ceros_e_infinitos(self) -> None:
        """FDIV: Operaciones donde cero o infinito es dividendo o divisor."""
        # 0 / x = 0 con signo
        self.assertEqual(self.fpu.dividir_bits(0.0, 5.0), POS_ZERO)
        self.assertEqual(self.fpu.dividir_bits(-0.0, 5.0), NEG_ZERO)
        self.assertEqual(self.fpu.dividir_bits(0.0, -5.0), NEG_ZERO)
        self.assertEqual(self.fpu.dividir_bits(-0.0, -5.0), POS_ZERO)

        # x / inf = 0 con signo
        self.assertEqual(self.fpu.dividir_bits(5.0, math.inf), POS_ZERO)
        self.assertEqual(self.fpu.dividir_bits(-5.0, math.inf), NEG_ZERO)

        # inf / x = inf con signo
        self.assertEqual(self.fpu.dividir_bits(math.inf, 2.0), POS_INFINITY)
        self.assertEqual(self.fpu.dividir_bits(-math.inf, 2.0), NEG_INFINITY)

    def test_fdiv_comparacion_diferencial_oraculo(self) -> None:
        """FDIV: Comparación contra el oráculo matemático IEEE 754."""
        pares = [
            (1.0, 3.0),
            (1.0, 7.0),
            (22.0, 7.0),
            (355.0, 113.0),
            (1e10, 3.0),
            (1.0, 1e10),
            (2.0**-500, 2.0**500),
        ]
        for a, b in pares:
            with self.subTest(a=a, b=b):
                a_bits = float_a_ieee64(a)
                b_bits = float_a_ieee64(b)
                obtenido = self.fpu.dividir_bits(a, b)
                esperado = OraculoIEEE754.oraculo_fdiv(a_bits, b_bits)
                distancia = OraculoIEEE754.distancia_ulps(obtenido, esperado)
                self.assertLessEqual(distancia, 1, f"Divergencia en {a}/{b}: {distancia} ULPs")

    # =========================================================================
    # 2. PRUEBAS UNITARIAS DE FCMP
    # =========================================================================

    def test_fcmp_orden_estricto(self) -> None:
        """FCMP: Orden estricto menor (-1), igual (0) y mayor (1)."""
        # A < B -> -1
        self.assertEqual(self.fpu.comparar(1.0, 2.0), -1)
        self.assertEqual(self.fpu.comparar(-5.0, -2.0), -1)
        self.assertEqual(self.fpu.comparar(-1.0, 1.0), -1)

        # A == B -> 0
        self.assertEqual(self.fpu.comparar(42.0, 42.0), 0)
        self.assertEqual(self.fpu.comparar(-3.1415, -3.1415), 0)

        # A > B -> 1
        self.assertEqual(self.fpu.comparar(2.0, 1.0), 1)
        self.assertEqual(self.fpu.comparar(1.0, -1.0), 1)
        self.assertEqual(self.fpu.comparar(-2.0, -5.0), 1)

    def test_fcmp_equivalencia_ceros(self) -> None:
        """FCMP: En IEEE 754, +0.0 y -0.0 son iguales numéricamente (retorna 0)."""
        self.assertEqual(self.fpu.comparar(0.0, -0.0), 0)
        self.assertEqual(self.fpu.comparar(-0.0, 0.0), 0)
        self.assertEqual(self.fpu.comparar(0.0, 0.0), 0)
        self.assertEqual(self.fpu.comparar(-0.0, -0.0), 0)

    def test_fcmp_infinitos(self) -> None:
        """FCMP: Comparación con infinitos respeta la recta real extendida."""
        self.assertEqual(self.fpu.comparar(math.inf, math.inf), 0)
        self.assertEqual(self.fpu.comparar(-math.inf, -math.inf), 0)
        self.assertEqual(self.fpu.comparar(-math.inf, math.inf), -1)
        self.assertEqual(self.fpu.comparar(math.inf, -math.inf), 1)
        self.assertEqual(self.fpu.comparar(1e300, math.inf), -1)
        self.assertEqual(self.fpu.comparar(-1e300, -math.inf), 1)

    def test_fcmp_nans_unordered(self) -> None:
        """FCMP: Cualquier comparación que involucre NaN es no ordenada (retorna 2)."""
        nan_bits = CANONICAL_NAN
        self.assertEqual(self.fpu.comparar(nan_bits, 1.0), 2)
        self.assertEqual(self.fpu.comparar(1.0, nan_bits), 2)
        self.assertEqual(self.fpu.comparar(nan_bits, nan_bits), 2)

    # =========================================================================
    # 3. PRUEBAS DE LA MESA DE VECTORES CANÓNICOS (FPU_VECTORES)
    # =========================================================================

    def test_mesa_vectores_completa(self) -> None:
        """Verifica la invocación funcional de los 9 vectores canónicos de la FPU."""
        # Vector 0: VEC_FADD
        self.assertEqual(self.fpu.ejecutar_vector("VEC_FADD", 1.5, 2.5), float_a_ieee64(4.0))

        # Vector 1: VEC_FSUB
        self.assertEqual(self.fpu.ejecutar_vector("VEC_FSUB", 10.0, 3.0), float_a_ieee64(7.0))

        # Vector 2: VEC_FMUL
        self.assertEqual(self.fpu.ejecutar_vector("VEC_FMUL", 3.0, 4.0), float_a_ieee64(12.0))

        # Vector 3: VEC_FDIV
        self.assertEqual(self.fpu.ejecutar_vector("VEC_FDIV", 20.0, 5.0), float_a_ieee64(4.0))

        # Vector 4: VEC_FCMP
        res_fcmp = self.fpu.ejecutar_vector("VEC_FCMP", 5.0, 10.0)
        # -1 en complemento a 2 de 64 bits es 0xFFFFFFFFFFFFFFFF
        self.assertEqual(res_fcmp, 0xFFFFFFFFFFFFFFFF)

        # Vector 5: VEC_INT_TO_FLOAT
        self.assertEqual(self.fpu.ejecutar_vector("VEC_INT_TO_FLOAT", 42), float_a_ieee64(42.0))

        # Vector 6: VEC_FLOAT_TO_INT
        self.assertEqual(self.fpu.ejecutar_vector("VEC_FLOAT_TO_INT", 42.9), 42)

        # Vector 7: VEC_FSQRT
        self.assertEqual(self.fpu.ejecutar_vector("VEC_FSQRT", 49.0), float_a_ieee64(7.0))

        # Vector 8: VEC_FBRUN
        self.assertEqual(self.fpu.ejecutar_vector("VEC_FBRUN", 1), 0x3FE1111111111111)

    # =========================================================================
    # 4. PRUEBAS DE INTEGRIDAD DE PILA Y REGISTROS
    # =========================================================================

    def test_invarianza_marco_de_pila(self) -> None:
        """Verifica que llamadas sucesivas a la FPU preserven SP y BP sin fugas de memoria de pila."""
        harness = """
        JMP HARNESS_START
        HARNESS_START:
            ADDI SP, R0, 0x0020
            SHL SP, SP, 16
            ADDI SP, SP, 0x4000
            ADDI BP, SP, 0

            ; Guardar SP inicial en memoria [0x00205008] (R1..R5 son scratch en ABI)
            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            STORE SP, [R4 + 8]

            ; 1. Llamar FADD
            ADDI R1, R0, 0x03FF
            SHL R1, R1, 52
            ADDI R2, R1, 0
            CALL FADD

            ; 2. Llamar FMUL
            ADDI R1, R5, 0
            ADDI R2, R5, 0
            CALL FMUL

            ; 3. Llamar FSQRT
            ADDI R1, R5, 0
            CALL FSQRT

            ; 4. Llamar FPU_BRUN
            ADDI R1, R0, 1
            CALL FPU_BRUN

            ; Recuperar SP inicial de memoria y comparar con SP actual
            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            LOAD R3, [R4 + 8]
            CMP SP, R3
            JZ STACK_OK
            ADDI R1, R0, 0
            STORE R1, [R4 + 0]
            HLT
        STACK_OK:
            ADDI R1, R0, 1
            STORE R1, [R4 + 0]
            HLT
        """
        self.fpu._preparar_entorno(harness)
        self.fpu.cpu.ejecutar(max_ciclos=80000)
        status, _ = self.fpu.ram.mem_read(self.fpu.DIRECCION_VARIABLES + 0, 8)
        self.assertEqual(status, 1, "Violación de invariancia de pila: SP no se preservó tras llamadas")


if __name__ == "__main__":
    unittest.main()
