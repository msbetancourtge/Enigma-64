"""
Suite de pruebas unitarias para la subrutina FSQRT y el Algoritmo de Newton-Raphson.

Verifica la funcionalidad del Integrante 6 ejecutada directamente sobre la CPU
oficial y la FPU emulada de Enigma-64:
  1. Cuadrados perfectos y enteros (0, 1, 4, 9, 16, 25, 49, 64, 81, 100, 144, 10000).
  2. Valores fraccionarios y decimales (0.25, 0.0625, 0.5, 2.0, 3.0, 10.0).
  3. Constantes matemáticas (pi, e).
  4. Escalas y magnitudes extremas (1e50, 1e150, 1e-50, 1e-150).
  5. Números subnormales de IEEE 754.
  6. Casos especiales: +0.0, -0.0, negativos produciendo NaN, +inf, -inf, qNaN y sNaN.
  7. Invocación mediante la tabla canónica FPU_VECTORES (VEC_FSQRT).
  8. Validación bit a bit de cada resultado contra el Oráculo IEEE 754.

Referencia: Ricardo Peña, 'De Euclides a JAVA' (pág. 26).
"""

from __future__ import annotations

import math
import struct
import unittest

from enigma64.fpu import (
    EmuladorFPUEnigma64,
    float_a_ieee64,
    ieee64_a_float,
    VECTOR_FSQRT,
)
from enigma64.oraculo_ieee754 import (
    CANONICAL_NAN,
    NEG_INFINITY,
    NEG_ZERO,
    POS_INFINITY,
    POS_ZERO,
    OraculoIEEE754,
    bits_a_float,
    float_a_bits,
    generar_catalogo_casos_prueba,
)


class TestFPURaizCuadrada(unittest.TestCase):
    """Pruebas unitarias de la subrutina FSQRT ejecutada en Enigma-64."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fpu = EmuladorFPUEnigma64()

    # -------------------------------------------------------------------------
    # 1. Pruebas de Cuadrados Perfectos y Enteros
    # -------------------------------------------------------------------------

    def test_fsqrt_cuadrados_perfectos(self) -> None:
        """FSQRT debe calcular la raíz cuadrada exacta de enteros cuadrados perfectos."""
        casos = [
            (1.0, 1.0),
            (4.0, 2.0),
            (9.0, 3.0),
            (16.0, 4.0),
            (25.0, 5.0),
            (49.0, 7.0),
            (64.0, 8.0),
            (81.0, 9.0),
            (100.0, 10.0),
            (144.0, 12.0),
            (10000.0, 100.0),
            (float(2**20), float(2**10)),
            (float(2**40), float(2**20)),
        ]
        for val_in, esperado in casos:
            res_flt = self.fpu.raiz_cuadrada(val_in)
            self.assertEqual(res_flt, esperado, f"Fallo en sqrt({val_in})")
            res_bits = self.fpu.raiz_cuadrada_bits(val_in)
            esp_bits = float_a_ieee64(esperado)
            self.assertEqual(res_bits, esp_bits, f"Diferencia de bits en sqrt({val_in})")

    # -------------------------------------------------------------------------
    # 2. Pruebas de Fraccionarios, Decimales e Irracionales
    # -------------------------------------------------------------------------

    def test_fsqrt_fraccionarios(self) -> None:
        """FSQRT debe calcular raíces exactas de valores fraccionarios."""
        casos = [
            (0.25, 0.5),
            (0.0625, 0.25),
        ]
        for val_in, esperado in casos:
            res_flt = self.fpu.raiz_cuadrada(val_in)
            self.assertEqual(res_flt, esperado)
            self.assertEqual(self.fpu.raiz_cuadrada_bits(val_in), float_a_ieee64(esperado))

    def test_fsqrt_irracionales_y_constantes(self) -> None:
        """FSQRT debe converger con precisión óptima en irracionales (sqrt(2), sqrt(3), pi)."""
        casos = [2.0, 3.0, 5.0, 10.0, 0.5, math.pi, math.e]
        for val_in in casos:
            res_bits = self.fpu.raiz_cuadrada_bits(val_in)
            esp_bits = OraculoIEEE754.fsqrt_bits(float_a_bits(val_in))
            valido, explicacion = OraculoIEEE754.validar_fsqrt(
                float_a_bits(val_in), res_bits, max_ulps=1
            )
            self.assertTrue(valido, f"Fallo en {val_in}: {explicacion}")

    # -------------------------------------------------------------------------
    # 3. Pruebas de Magnitudes Extremas
    # -------------------------------------------------------------------------

    def test_fsqrt_magnitudes_extremas(self) -> None:
        """FSQRT no debe desbordarse ni perder precisión con números gigantes o diminutos."""
        casos = [1e50, 1e100, 1e150, 1e-50, 1e-100, 1e-150]
        for val_in in casos:
            res_bits = self.fpu.raiz_cuadrada_bits(val_in)
            valido, explicacion = OraculoIEEE754.validar_fsqrt(
                float_a_bits(val_in), res_bits, max_ulps=1
            )
            self.assertTrue(valido, f"Fallo en escala {val_in}: {explicacion}")

    # -------------------------------------------------------------------------
    # 4. Pruebas de Números Subnormales
    # -------------------------------------------------------------------------

    def test_fsqrt_subnormales(self) -> None:
        """FSQRT debe normalizar y calcular correctamente la raíz de números subnormales."""
        subnormal_min = 0x0000_0000_0000_0001
        subnormal_mid = 0x0000_8000_0000_0000

        for u64_in in (subnormal_min, subnormal_mid):
            res_bits = self.fpu.raiz_cuadrada_bits(u64_in)
            valido, explicacion = OraculoIEEE754.validar_fsqrt(u64_in, res_bits, max_ulps=1)
            self.assertTrue(valido, f"Fallo en subnormal 0x{u64_in:016X}: {explicacion}")

    # -------------------------------------------------------------------------
    # 5. Pruebas de Casos Especiales IEEE 754
    # -------------------------------------------------------------------------

    def test_fsqrt_ceros_con_signo(self) -> None:
        """FSQRT debe preservar estrictamente el signo de +0.0 y -0.0."""
        # +0.0
        bits_pos = self.fpu.raiz_cuadrada_bits(0.0)
        self.assertEqual(bits_pos, POS_ZERO)

        # -0.0
        bits_neg = self.fpu.raiz_cuadrada_bits(-0.0)
        self.assertEqual(bits_neg, NEG_ZERO)

    def test_fsqrt_negativos_producen_nan(self) -> None:
        """La raíz de cualquier número negativo debe producir NaN canónico."""
        negativos = [-1.0, -4.0, -0.25, -100.0, -1e50]
        for neg in negativos:
            res_bits = self.fpu.raiz_cuadrada_bits(neg)
            self.assertEqual(
                res_bits,
                CANONICAL_NAN,
                f"sqrt({neg}) debió retornar NaN canónico pero retornó 0x{res_bits:016X}",
            )

    def test_fsqrt_infinitos(self) -> None:
        """FSQRT(+inf) = +inf y FSQRT(-inf) = NaN."""
        # +inf
        res_pos_inf = self.fpu.raiz_cuadrada_bits(math.inf)
        self.assertEqual(res_pos_inf, POS_INFINITY)

        # -inf
        res_neg_inf = self.fpu.raiz_cuadrada_bits(-math.inf)
        self.assertEqual(res_neg_inf, CANONICAL_NAN)

    def test_fsqrt_nans(self) -> None:
        """FSQRT(NaN) debe propagar NaN silenciado activando el bit 51."""
        # qNaN
        qnan = 0x7FF8_0000_0000_0123
        self.assertEqual(self.fpu.raiz_cuadrada_bits(qnan), qnan)

        # sNaN debe silenciarse (activar bit 51)
        snan = 0x7FF0_0000_0000_0123
        esperado_qnan = snan | 0x0008_0000_0000_0000
        self.assertEqual(self.fpu.raiz_cuadrada_bits(snan), esperado_qnan)

    # -------------------------------------------------------------------------
    # 6. Pruebas de la Tabla de Vectores (VEC_FSQRT)
    # -------------------------------------------------------------------------

    def test_fsqrt_vector_fpu(self) -> None:
        """FSQRT debe ser invocable mediante el punto de entrada VEC_FSQRT."""
        res_bits = self.fpu.ejecutar_vector("VEC_FSQRT", 16.0)
        self.assertEqual(res_bits, float_a_ieee64(4.0))

        res_bits_25 = self.fpu.ejecutar_vector("VEC_FSQRT", 25.0)
        self.assertEqual(res_bits_25, float_a_ieee64(5.0))

        res_bits_cero = self.fpu.ejecutar_vector("VEC_FSQRT", 0.0)
        self.assertEqual(res_bits_cero, POS_ZERO)

    # -------------------------------------------------------------------------
    # 7. Validación Sistemática Contra el Catálogo del Oráculo
    # -------------------------------------------------------------------------

    def test_fsqrt_contra_catalogo_completo(self) -> None:
        """Comprueba exhaustivamente todos los casos del catálogo del oráculo."""
        catalogo = generar_catalogo_casos_prueba()
        for caso in catalogo:
            u_in = caso["entrada_bits"]
            nombre = caso["nombre"]
            obtenido_bits = self.fpu.raiz_cuadrada_bits(u_in)
            valido, explicacion = OraculoIEEE754.validar_fsqrt(u_in, obtenido_bits, max_ulps=1)
            self.assertTrue(
                valido,
                f"Fallo en caso '{nombre}' (0x{u_in:016X}): {explicacion}",
            )


if __name__ == "__main__":
    unittest.main()
