"""
Suite de pruebas unitarias para FMUL (fmul.s) de Enigma-64.

Cada caso se ejecuta sobre la CPU oficial y se compara bit a bit contra el
oráculo de Python: los float de Python son binary64 con redondeo al par más
cercano, así que struct + "*" reproduce el resultado IEEE 754 exacto.

Autor: Integrante 2 Tomas Garzon - FMUL
"""

from __future__ import annotations

import math
import random
import unittest

from enigma64.fpu import (
    EmuladorFPUEnigma64,
    float_a_ieee64,
    ieee64_a_float,
)

POS_INF = 0x7FF0000000000000
NEG_INF = 0xFFF0000000000000
NAN_CANONICO = 0x7FF8000000000000


def oraculo_fmul(a: int, b: int) -> int:
    """Resultado IEEE 754 de referencia para A * B, como patrón de 64 bits."""
    return float_a_ieee64(ieee64_a_float(a) * ieee64_a_float(b))


def es_nan(u64: int) -> bool:
    return math.isnan(ieee64_a_float(u64))


# (descripción, A, B, resultado esperado). Los valores esperados coinciden con
# oraculo_fmul salvo en NaN, donde IEEE 754 no fija signo ni carga útil.
CASOS_TABLA = [
    ("normal x normal: 1.5 x 2.5",              0x3FF8000000000000, 0x4004000000000000, 0x400E000000000000),
    ("signos: -3.0 x 4.0",                      0xC008000000000000, 0x4010000000000000, 0xC028000000000000),
    ("signos: -2.0 x -0.5",                     0xC000000000000000, 0xBFE0000000000000, 0x3FF0000000000000),
    ("identidad: 1.0 x pi",                     0x3FF0000000000000, 0x400921FB54442D18, 0x400921FB54442D18),
    ("potencias de 2: 2^10 x 2^-3",             0x4090000000000000, 0x3FC0000000000000, 0x4060000000000000),
    ("normalizacion P >= 2: 1.75 x 1.75",       0x3FFC000000000000, 0x3FFC000000000000, 0x4008800000000000),
    ("redondeo inexacto: 0.1 x 0.2",            0x3FB999999999999A, 0x3FC999999999999A, 0x3F947AE147AE147C),
    ("cero: +0 x 5.0",                          0x0000000000000000, 0x4014000000000000, 0x0000000000000000),
    ("cero con signo: -0 x 5.0",                0x8000000000000000, 0x4014000000000000, 0x8000000000000000),
    ("Inf x finito: +Inf x -2.0",               POS_INF,            0xC000000000000000, NEG_INF),
    ("Inf x Inf: -Inf x -Inf",                  NEG_INF,            NEG_INF,            POS_INF),
    ("invalida: 0 x Inf",                       0x0000000000000000, POS_INF,            NAN_CANONICO),
    ("NaN x 1.0 se propaga",                    0x7FF8000000000123, 0x3FF0000000000000, 0x7FF8000000000123),
    ("sNaN se silencia",                        0x7FF0000000000001, 0x3FF0000000000000, 0x7FF8000000000001),
    ("overflow: MAX x 2.0",                     0x7FEFFFFFFFFFFFFF, 0x4000000000000000, POS_INF),
    ("overflow negativo: 1e200 x -1e200",       0x6974E718D7D7625A, 0xE974E718D7D7625A, NEG_INF),
    ("underflow a subnormal: 2^-1022 x 0.5",    0x0010000000000000, 0x3FE0000000000000, 0x0008000000000000),
    ("underflow a cero: 1e-200 x 1e-200",       0x16687E92154EF7AC, 0x16687E92154EF7AC, 0x0000000000000000),
    ("subnormal x normal: 2^-1074 x 2^60",      0x0000000000000001, 0x43B0000000000000, 0x0090000000000000),
    ("empate al par, sube: (1+2^-52) x 1.5",    0x3FF0000000000001, 0x3FF8000000000000, 0x3FF8000000000002),
    ("empate al par, baja: (1+3*2^-52) x 1.5",  0x3FF0000000000003, 0x3FF8000000000000, 0x3FF8000000000004),
    ("empate subnormal: 2^-1074 x 0.5",         0x0000000000000001, 0x3FE0000000000000, 0x0000000000000000),
    ("empate subnormal: 3*2^-1074 x 0.5",       0x0000000000000003, 0x3FE0000000000000, 0x0000000000000002),
    ("redondeo al menor normal",                0x000FFFFFFFFFFFFF, 0x3FF0000000000001, 0x0010000000000000),
]


class TestFMULEnigma64(unittest.TestCase):
    """Pruebas de FMUL y de su auxiliar FPU_MUL128 sobre la CPU de Enigma-64."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fpu = EmuladorFPUEnigma64()

    def test_tabla_casos(self) -> None:
        """Tabla de casos con entradas y salidas en hexadecimal."""
        for descripcion, a, b, esperado in CASOS_TABLA:
            with self.subTest(descripcion):
                obtenido = self.fpu.multiplicar_bits(a, b)
                self.assertEqual(
                    obtenido, esperado,
                    f"{a:016X} * {b:016X}: {obtenido:016X} != {esperado:016X}",
                )

    def test_tabla_concuerda_con_oraculo(self) -> None:
        """Los valores esperados de la tabla salen del oráculo IEEE 754."""
        for descripcion, a, b, esperado in CASOS_TABLA:
            with self.subTest(descripcion):
                referencia = oraculo_fmul(a, b)
                if es_nan(referencia):
                    self.assertTrue(es_nan(esperado))
                else:
                    self.assertEqual(esperado, referencia)

    def test_multiplicar_flotantes(self) -> None:
        """La interfaz con float de Python devuelve el producto exacto."""
        self.assertEqual(self.fpu.multiplicar(6.0, 7.0), 42.0)
        self.assertEqual(self.fpu.multiplicar(-0.75, 8.0), -6.0)
        self.assertEqual(self.fpu.multiplicar(0.1, 3.0), 0.1 * 3.0)

    def test_conmutatividad(self) -> None:
        """A * B == B * A para operandos no NaN."""
        pares = [(1.1, 2.2), (-3.5, 1e-300), (1e300, 1e-10), (5e-324, 7.0)]
        for a, b in pares:
            with self.subTest(a=a, b=b):
                self.assertEqual(
                    self.fpu.multiplicar_bits(a, b), self.fpu.multiplicar_bits(b, a)
                )

    def test_aleatorio_contra_oraculo(self) -> None:
        """Comparación diferencial con semilla fija sobre todo el rango binary64."""
        rnd = random.Random(2026)
        for _ in range(300):
            tipo = rnd.randrange(4)
            if tipo == 0:
                a, b = rnd.getrandbits(64), rnd.getrandbits(64)
            elif tipo == 1:
                a = float_a_ieee64(rnd.uniform(-4.0, 4.0))
                b = float_a_ieee64(rnd.uniform(-4.0, 4.0))
            elif tipo == 2:
                # Región de subdesbordamiento gradual
                a = float_a_ieee64(rnd.uniform(1.0, 2.0) * 2.0 ** rnd.randint(-1080, -500))
                b = float_a_ieee64(rnd.uniform(1.0, 2.0) * 2.0 ** rnd.randint(-560, 0))
            else:
                # Operando subnormal por operando grande
                a = rnd.getrandbits(52) | (rnd.getrandbits(1) << 63)
                b = float_a_ieee64(rnd.uniform(1.0, 2.0) * 2.0 ** rnd.randint(900, 1023))
            obtenido = self.fpu.multiplicar_bits(a, b)
            referencia = oraculo_fmul(a, b)
            if es_nan(referencia):
                self.assertTrue(es_nan(obtenido), f"{a:016X} * {b:016X}")
            else:
                self.assertEqual(
                    obtenido, referencia,
                    f"{a:016X} * {b:016X}: {obtenido:016X} != {referencia:016X}",
                )

    def test_ciclos_peor_caso(self) -> None:
        """Subnormal x subnormal (peor caso de bucles) termina holgadamente."""
        self.assertEqual(self.fpu.multiplicar_bits(1, 1), 0)
        self.assertLess(self.fpu.cpu.ciclos, 10000)

    def test_mul128(self) -> None:
        """FPU_MUL128 entrega el producto de 128 bits exacto en R5:R4."""
        pares = [
            (0, 0),
            (1, 1),
            (0xFFFFFFFFFFFFFFFF, 0xFFFFFFFFFFFFFFFF),
            (0x001FFFFFFFFFFFFF, 0x001FFFFFFFFFFFFF),
            (0x123456789ABCDEF0, 0x0FEDCBA987654321),
        ]
        for x, y in pares:
            with self.subTest(x=hex(x), y=hex(y)):
                hi, lo = self._ejecutar_mul128(x, y)
                self.assertEqual((hi << 64) | lo, x * y)

    def _ejecutar_mul128(self, x: int, y: int) -> tuple[int, int]:
        harness = """
        JMP HARNESS_START
        HARNESS_START:
            ADDI SP, R0, 0x0020
            SHL SP, SP, 16
            ADDI SP, SP, 0x4000
            ADDI BP, SP, 0

            ADDI R3, R0, 0x0020
            SHL R3, R3, 16
            ADDI R3, R3, 0x5000
            LOAD R1, [R3 + 0]
            LOAD R2, [R3 + 8]
            CALL FPU_MUL128

            ADDI R3, R0, 0x0020
            SHL R3, R3, 16
            ADDI R3, R3, 0x5000
            STORE R5, [R3 + 16]
            STORE R4, [R3 + 24]
            HLT
        """
        fpu = self.fpu
        fpu._preparar_entorno(harness)
        fpu.ram.mem_write(fpu.DIRECCION_VARIABLES + 0, x, 8)
        fpu.ram.mem_write(fpu.DIRECCION_VARIABLES + 8, y, 8)
        fpu.cpu.ejecutar(max_ciclos=50000)
        hi, _ = fpu.ram.mem_read(fpu.DIRECCION_VARIABLES + 16, 8)
        lo, _ = fpu.ram.mem_read(fpu.DIRECCION_VARIABLES + 24, 8)
        return hi or 0, lo or 0


if __name__ == "__main__":
    unittest.main()
