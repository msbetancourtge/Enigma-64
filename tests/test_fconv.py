"""
Suite de pruebas unitarias para Conversiones FPU y Mesa de Vectores (Enigma-64).

Verifica sobre la CPU oficial de Enigma-64:
  1. FPU_INT_TO_FLOAT (alias INT64_TO_FLOAT64):
     - Cero, positivos y negativos.
     - Potencias de dos (2^1 .. 2^62).
     - Casos límites: INT64_MAX (2^63 - 1) e INT64_MIN (-2^63).
     - Comparación bit a bit contra el oráculo IEEE 754 de Python.
     - Redondeo al par más cercano (roundTiesToEven) para enteros > 53 bits.
  2. FPU_FLOAT_TO_INT (alias FLOAT64_TO_INT64):
     - Truncamiento hacia cero (|x| < 1.0 da 0).
     - Enteros positivos y negativos con parte decimal.
     - Casos especiales (0.0, -0.0, Inf, NaN).
     - Identidad inversa int -> float -> int en el rango [-2^53, 2^53].
  3. FPU_VECTORES (Mesa de Entrada de la Biblioteca):
     - Invocación de VEC_FADD, VEC_FSUB, VEC_FMUL.
     - Invocación de VEC_INT_TO_FLOAT y VEC_FLOAT_TO_INT.
    - Verificación de VEC_FDIV y VEC_FCMP, incluidos casos especiales.

Autor: Integrante 4 (Deibyd Santiago Barragán Gaitán / Juan Luis Vergara Novoa)
"""

from __future__ import annotations

import math
import struct
import unittest

from enigma64.fpu import (
    EmuladorFPUEnigma64,
    float_a_ieee64,
    ieee64_a_float,
)


class TestFPUConversiones(unittest.TestCase):
    """Pruebas unitarias de las subrutinas de conversión INT <-> FLOAT en Enigma-64."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fpu = EmuladorFPUEnigma64()

    # -------------------------------------------------------------------------
    # Pruebas INT64 -> FLOAT64 (FPU_INT_TO_FLOAT)
    # -------------------------------------------------------------------------

    def test_int_to_float_cero(self) -> None:
        """El entero 0 debe convertirse a 0.0 (todos los bits en cero)."""
        bits = self.fpu.int_to_float_bits(0)
        self.assertEqual(bits, 0x0000000000000000)
        self.assertEqual(self.fpu.int_to_float(0), 0.0)

    def test_int_to_float_enteros_positivos(self) -> None:
        """Verifica enteros positivos pequeños y medianos contra el oráculo."""
        casos = [1, 2, 3, 5, 10, 42, 100, 255, 1000, 65535, 123456789]
        for n in casos:
            with self.subTest(n=n):
                bits_obtenidos = self.fpu.int_to_float_bits(n)
                bits_esperados = float_a_ieee64(float(n))
                self.assertEqual(
                    bits_obtenidos,
                    bits_esperados,
                    f"Fallo para n={n}: esperado 0x{bits_esperados:016X}, "
                    f"obtenido 0x{bits_obtenidos:016X}",
                )
                self.assertEqual(self.fpu.int_to_float(n), float(n))

    def test_int_to_float_enteros_negativos(self) -> None:
        """Verifica enteros negativos pequeños y medianos contra el oráculo."""
        casos = [-1, -2, -3, -5, -10, -42, -100, -255, -1000, -65535, -123456789]
        for n in casos:
            with self.subTest(n=n):
                bits_obtenidos = self.fpu.int_to_float_bits(n)
                bits_esperados = float_a_ieee64(float(n))
                self.assertEqual(
                    bits_obtenidos,
                    bits_esperados,
                    f"Fallo para n={n}: esperado 0x{bits_esperados:016X}, "
                    f"obtenido 0x{bits_obtenidos:016X}",
                )
                self.assertEqual(self.fpu.int_to_float(n), float(n))

    def test_int_to_float_potencias_de_dos(self) -> None:
        """Verifica potencias de dos exactas tanto positivas como negativas."""
        for p in [1, 2, 8, 16, 24, 32, 40, 50, 52, 60, 62]:
            val_pos = 1 << p
            val_neg = -(1 << p)
            with self.subTest(potencia=p, signo="+"):
                self.assertEqual(
                    self.fpu.int_to_float_bits(val_pos),
                    float_a_ieee64(float(val_pos)),
                )
            with self.subTest(potencia=p, signo="-"):
                self.assertEqual(
                    self.fpu.int_to_float_bits(val_neg),
                    float_a_ieee64(float(val_neg)),
                )

    def test_int_to_float_casos_extremos_64_bits(self) -> None:
        """Verifica los valores extremos de un entero con signo de 64 bits."""
        # INT64_MAX: 2^63 - 1 = 9223372036854775807
        int64_max = (1 << 63) - 1
        self.assertEqual(
            self.fpu.int_to_float_bits(int64_max),
            float_a_ieee64(float(int64_max)),
        )

        # INT64_MIN: -2^63 = -9223372036854775808 (caso límite de complemento a 2)
        int64_min = -(1 << 63)
        self.assertEqual(
            self.fpu.int_to_float_bits(int64_min),
            float_a_ieee64(float(int64_min)),
        )
        self.assertEqual(self.fpu.int_to_float(int64_min), float(int64_min))

    def test_int_to_float_redondeo_al_par(self) -> None:
        """Verifica el redondeo al par más cercano para enteros mayores a 53 bits."""
        base_53 = 1 << 53  # 9007199254740992 (límite de precisión exacta)
        # 2^53 + 1 es un empate (bit 0 = 1). LSB de mantisa es 0 (par) -> redondea hacia abajo
        # 2^53 + 2 es exacto
        # 2^53 + 3 es impar con LSB 1 -> redondea hacia arriba
        casos = [
            base_53 + 0,
            base_53 + 1,
            base_53 + 2,
            base_53 + 3,
            base_53 + 4,
            -(base_53 + 1),
            -(base_53 + 3),
        ]
        for n in casos:
            with self.subTest(n=n):
                self.assertEqual(
                    self.fpu.int_to_float_bits(n),
                    float_a_ieee64(float(n)),
                )

    # -------------------------------------------------------------------------
    # Pruebas FLOAT64 -> INT64 (FPU_FLOAT_TO_INT)
    # -------------------------------------------------------------------------

    def test_float_to_int_ceros(self) -> None:
        """+0.0 y -0.0 deben convertirse al entero 0."""
        self.assertEqual(self.fpu.float_to_int(0.0), 0)
        self.assertEqual(self.fpu.float_to_int(-0.0), 0)

    def test_float_to_int_magnitud_menor_a_uno(self) -> None:
        """Cualquier flotante con |x| < 1.0 debe truncarse a 0."""
        casos = [0.1, 0.25, 0.5, 0.75, 0.999999, -0.1, -0.5, -0.75, -0.999999]
        for x in casos:
            with self.subTest(x=x):
                self.assertEqual(self.fpu.float_to_int(x), 0)

    def test_float_to_int_enteros_exactos(self) -> None:
        """Flotantes con valor entero exacto se recuperan íntegramente."""
        casos = [1.0, 2.0, 5.0, 10.0, 42.0, 100.0, 1000.0, -1.0, -5.0, -42.0, -100.0]
        for x in casos:
            with self.subTest(x=x):
                self.assertEqual(self.fpu.float_to_int(x), int(x))

    def test_float_to_int_truncamiento_hacia_cero(self) -> None:
        """La parte decimal debe descartarse truncando hacia cero."""
        casos = [
            (1.2, 1),
            (1.9, 1),
            (5.75, 5),
            (42.9999, 42),
            (1234.5678, 1234),
            (-1.2, -1),
            (-1.9, -1),
            (-5.75, -5),
            (-42.9999, -42),
            (-1234.5678, -1234),
        ]
        for x, esperado in casos:
            with self.subTest(x=x):
                self.assertEqual(self.fpu.float_to_int(x), esperado)

    def test_float_to_int_enteros_grandes(self) -> None:
        """Verifica conversiones con exponentes grandes (e > 52)."""
        casos = [
            1 << 30,
            1 << 40,
            1 << 50,
            1 << 52,
            1 << 60,
            -(1 << 30),
            -(1 << 40),
            -(1 << 50),
            -(1 << 52),
            -(1 << 60),
        ]
        for n in casos:
            with self.subTest(n=n):
                self.assertEqual(self.fpu.float_to_int(float(n)), n)

    def test_float_to_int_casos_especiales(self) -> None:
        """Infinito y NaN deben retornar 0 de forma segura sin colapsar."""
        pos_inf = float("inf")
        neg_inf = float("-inf")
        nan_val = float("nan")

        self.assertEqual(self.fpu.float_to_int(pos_inf), 0)
        self.assertEqual(self.fpu.float_to_int(neg_inf), 0)
        self.assertEqual(self.fpu.float_to_int(nan_val), 0)

    def test_inversa_int_float_int(self) -> None:
        """Para todo entero n dentro del rango exacto [-2^53, 2^53], int_to_float y float_to_int son inversas."""
        muestras = [
            0, 1, -1, 7, -7, 13, -13, 42, -42, 127, -128,
            256, 1024, -2048, 1000000, -1000000,
            (1 << 30) - 1, -(1 << 30) + 1,
            (1 << 52) - 1, -(1 << 52) + 1,
        ]
        for n in muestras:
            with self.subTest(n=n):
                flotante = self.fpu.int_to_float(n)
                recuperado = self.fpu.float_to_int(flotante)
                self.assertEqual(recuperado, n)


class TestFPUMesaDeVectores(unittest.TestCase):
    """Pruebas de la Mesa de Entrada / Tabla Canónica de Vectores de la FPU."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fpu = EmuladorFPUEnigma64()

    def test_vector_fadd(self) -> None:
        """El vector 0 (VEC_FADD) debe ejecutar FADD correctamente."""
        res_bits = self.fpu.ejecutar_vector("VEC_FADD", 10.5, 20.25)
        self.assertEqual(ieee64_a_float(res_bits), 30.75)

    def test_vector_fsub(self) -> None:
        """El vector 1 (VEC_FSUB) debe ejecutar FSUB correctamente."""
        res_bits = self.fpu.ejecutar_vector("VEC_FSUB", 50.0, 18.5)
        self.assertEqual(ieee64_a_float(res_bits), 31.5)

    def test_vector_fmul(self) -> None:
        """El vector 2 (VEC_FMUL) debe ejecutar FMUL correctamente."""
        res_bits = self.fpu.ejecutar_vector("VEC_FMUL", 3.0, 7.5)
        self.assertEqual(ieee64_a_float(res_bits), 22.5)

    def test_vector_int_to_float(self) -> None:
        """El vector 5 (VEC_INT_TO_FLOAT) debe ejecutar la conversión entera a float."""
        res_bits = self.fpu.ejecutar_vector("VEC_INT_TO_FLOAT", 12345, 0)
        self.assertEqual(ieee64_a_float(res_bits), 12345.0)

    def test_vector_float_to_int(self) -> None:
        """El vector 6 (VEC_FLOAT_TO_INT) debe ejecutar la conversión float a entero."""
        res_bits = self.fpu.ejecutar_vector("VEC_FLOAT_TO_INT", 9876.54, 0)
        self.assertEqual(res_bits, 9876)

    def test_vector_fdiv(self) -> None:
        """El vector 3 (VEC_FDIV) debe ejecutar division IEEE-754."""
        res_fdiv = self.fpu.ejecutar_vector("VEC_FDIV", 1.0, 2.0)
        self.assertEqual(ieee64_a_float(res_fdiv), 0.5)

        res_fdiv_zero = self.fpu.ejecutar_vector("VEC_FDIV", 0.0, 0.0)
        self.assertTrue(math.isnan(ieee64_a_float(res_fdiv_zero)))

    def test_vector_fcmp(self) -> None:
        """El vector 4 (VEC_FCMP) debe comparar valores binary64."""
        res_fcmp = self.fpu.ejecutar_vector("VEC_FCMP", 1.0, 2.0)
        self.assertEqual(res_fcmp, (1 << 64) - 1)

        res_fcmp_nan = self.fpu.ejecutar_vector("VEC_FCMP", float("nan"), 1.0)
        self.assertEqual(res_fcmp_nan, 2)


if __name__ == "__main__":
    unittest.main()
