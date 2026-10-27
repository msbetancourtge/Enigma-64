"""
Suite de pruebas unitarias para el Oráculo de Validación IEEE 754 (Enigma-64).

Verifica la funcionalidad del Integrante 6:
  1. Desglose y análisis de precisión de campos IEEE 754 (binary64).
  2. Clasificación de clases: normales, subnormales, ceros con signo, infinitos y NaNs.
  3. Conversión exacta y composición de campos.
  4. Cálculo de distancias en ULPs (Units in the Last Place).
  5. Simulador del método de Newton-Raphson (Ricardo Peña, pág. 26).
  6. Oráculo canónico de referencia de raíz cuadrada y validación.
  7. Catálogo completo de casos de prueba.
"""

from __future__ import annotations

import math
import struct
import unittest

from enigma64.oraculo_ieee754 import (
    CANONICAL_NAN,
    NEG_INFINITY,
    NEG_ZERO,
    POS_INFINITY,
    POS_ZERO,
    ClaseIEEE754,
    DesgloseIEEE754,
    OraculoIEEE754,
    PasoNewtonRaphson,
    ResultadoNewtonRaphson,
    bits_a_float,
    componer_ieee754,
    descomponer_ieee754,
    float_a_bits,
    generar_catalogo_casos_prueba,
    simular_newton_raphson,
)


class TestOraculoIEEE754(unittest.TestCase):
    """Batería de pruebas exhaustivas para el módulo del oráculo IEEE 754."""

    # -------------------------------------------------------------------------
    # 1. Pruebas de Conversiones y Campos Básicos
    # -------------------------------------------------------------------------

    def test_conversiones_bidireccionales(self) -> None:
        """float_a_bits y bits_a_float deben ser inversas exactas."""
        valores = [
            0.0, -0.0, 1.0, -1.0, 2.0, 0.5, 0.25,
            math.pi, math.e, 1e100, 1e-100,
            float(2**53), float(2**62),
        ]
        for v in valores:
            bits = float_a_bits(v)
            recuperado = bits_a_float(bits)
            self.assertEqual(bits, float_a_bits(recuperado))
            if not math.isnan(v):
                self.assertEqual(v, recuperado)

    def test_componer_ieee754(self) -> None:
        """componer_ieee754 debe ensamblar correctamente S, E y Fracción."""
        # 1.0 -> S=0, E=1023 (0x3FF), Frac=0 -> 0x3FF0000000000000
        bits_uno = componer_ieee754(0, 1023, 0)
        self.assertEqual(bits_uno, 0x3FF0000000000000)
        self.assertEqual(bits_a_float(bits_uno), 1.0)

        # -2.0 -> S=1, E=1024 (0x400), Frac=0 -> 0xC000000000000000
        bits_menos_dos = componer_ieee754(1, 1024, 0)
        self.assertEqual(bits_menos_dos, 0xC000000000000000)
        self.assertEqual(bits_a_float(bits_menos_dos), -2.0)

    # -------------------------------------------------------------------------
    # 2. Pruebas de Desglose y Clasificación de Clases
    # -------------------------------------------------------------------------

    def test_descomponer_normales(self) -> None:
        """Verifica la descomposición de números normales positivos y negativos."""
        # 1.0
        d = descomponer_ieee754(1.0)
        self.assertEqual(d.signo, 0)
        self.assertEqual(d.exponente, 1023)
        self.assertEqual(d.exponente_real, 0)
        self.assertEqual(d.fraccion, 0)
        self.assertEqual(d.bit_implicito, 1)
        self.assertEqual(d.mantisa_efectiva, 0x0010_0000_0000_0000)
        self.assertEqual(d.clase, ClaseIEEE754.NORMAL_POSITIVO)
        self.assertFalse(d.es_nan)
        self.assertFalse(d.es_inf)
        self.assertFalse(d.es_cero)
        self.assertFalse(d.es_subnormal)

        # -4.0
        d_neg = descomponer_ieee754(-4.0)
        self.assertEqual(d_neg.signo, 1)
        self.assertEqual(d_neg.exponente, 1025)
        self.assertEqual(d_neg.exponente_real, 2)
        self.assertEqual(d_neg.clase, ClaseIEEE754.NORMAL_NEGATIVO)
        self.assertTrue(d_neg.es_negativo)

    def test_descomponer_ceros_con_signo(self) -> None:
        """Verifica la diferenciación de +0.0 y -0.0."""
        d_pos = descomponer_ieee754(0.0)
        self.assertEqual(d_pos.clase, ClaseIEEE754.CERO_POSITIVO)
        self.assertEqual(d_pos.signo, 0)
        self.assertTrue(d_pos.es_cero)
        self.assertEqual(d_pos.bits, POS_ZERO)

        d_neg = descomponer_ieee754(-0.0)
        self.assertEqual(d_neg.clase, ClaseIEEE754.CERO_NEGATIVO)
        self.assertEqual(d_neg.signo, 1)
        self.assertTrue(d_neg.es_cero)
        self.assertEqual(d_neg.bits, NEG_ZERO)

    def test_descomponer_subnormales(self) -> None:
        """Verifica el reconocimiento y análisis de números subnormales."""
        # Mínimo subnormal positivo: 2^-1074 -> bits = 1
        d_sub = descomponer_ieee754(1)
        self.assertEqual(d_sub.clase, ClaseIEEE754.SUBNORMAL_POSITIVO)
        self.assertTrue(d_sub.es_subnormal)
        self.assertEqual(d_sub.exponente, 0)
        self.assertEqual(d_sub.exponente_real, -1022)
        self.assertEqual(d_sub.bit_implicito, 0)
        self.assertEqual(d_sub.fraccion, 1)

    def test_descomponer_infinitos(self) -> None:
        """Verifica la clasificación de +infinito y -infinito."""
        d_inf = descomponer_ieee754(math.inf)
        self.assertEqual(d_inf.clase, ClaseIEEE754.INFINITO_POSITIVO)
        self.assertTrue(d_inf.es_inf)
        self.assertEqual(d_inf.bits, POS_INFINITY)

        d_ninf = descomponer_ieee754(-math.inf)
        self.assertEqual(d_ninf.clase, ClaseIEEE754.INFINITO_NEGATIVO)
        self.assertTrue(d_ninf.es_inf)
        self.assertEqual(d_ninf.bits, NEG_INFINITY)

    def test_descomponer_nans(self) -> None:
        """Verifica el reconocimiento de qNaN y sNaN."""
        # qNaN estándar
        d_qnan = descomponer_ieee754(CANONICAL_NAN)
        self.assertEqual(d_qnan.clase, ClaseIEEE754.QNAN)
        self.assertTrue(d_qnan.es_nan)

        # sNaN: exponente 0x7FF, fraccion no nula pero bit 51 en cero
        snan_bits = 0x7FF0_0000_0000_0001
        d_snan = descomponer_ieee754(snan_bits)
        self.assertEqual(d_snan.clase, ClaseIEEE754.SNAN)
        self.assertTrue(d_snan.es_nan)

    # -------------------------------------------------------------------------
    # 3. Pruebas del Simulador de Newton-Raphson (Ricardo Peña, pág. 26)
    # -------------------------------------------------------------------------

    def test_simulador_cuadrados_perfectos(self) -> None:
        """Verifica la convergencia exacta en enteros cuadrados perfectos."""
        cuadrados = [1.0, 4.0, 9.0, 16.0, 25.0, 49.0, 64.0, 81.0, 100.0, 144.0, 10000.0]
        for val in cuadrados:
            res = simular_newton_raphson(val)
            self.assertTrue(res.convergido)
            self.assertAlmostEqual(res.raiz_estimada, math.sqrt(val), places=14)
            # En cuadrados perfectos debe converger a distancia 0 o a lo sumo 1 ULP
            dist = abs(res.raiz_estimada_bits - res.raiz_exacta_bits)
            self.assertLessEqual(dist, 1)
            # El número de iteraciones debe ser pequeño (convergencia rápida)
            self.assertLessEqual(res.total_iteraciones, 20)

    def test_simulador_fraccionarios_e_irracionales(self) -> None:
        """Verifica la convergencia en valores fraccionarios y con raíz irracional."""
        valores = [0.25, 0.0625, 2.0, 3.0, 0.5, 10.0, math.pi, math.e]
        for val in valores:
            res = simular_newton_raphson(val)
            self.assertTrue(res.convergido)
            self.assertAlmostEqual(res.raiz_estimada, math.sqrt(val), places=14)
            dist = abs(res.raiz_estimada_bits - res.raiz_exacta_bits)
            self.assertLessEqual(dist, 1)

    def test_simulador_historial_y_metricas(self) -> None:
        """Verifica que el historial paso a paso registre todas las métricas."""
        res = simular_newton_raphson(16.0)
        self.assertGreater(len(res.iteraciones), 0)
        for paso in res.iteraciones:
            self.assertIsInstance(paso, PasoNewtonRaphson)
            self.assertGreater(paso.iteracion, 0)
            self.assertGreater(paso.x_k, 0.0)
            self.assertGreater(paso.cociente, 0.0)
            self.assertGreater(paso.x_sig, 0.0)
            # El error debe disminuir monotónicamente en las primeras iteraciones
            self.assertGreaterEqual(paso.diff_absoluta, 0.0)

    def test_simulador_casos_especiales(self) -> None:
        """Verifica el manejo de ceros, negativos, infinitos y NaNs."""
        # +0.0
        res_cero = simular_newton_raphson(0.0)
        self.assertEqual(res_cero.raiz_estimada_bits, POS_ZERO)
        self.assertEqual(res_cero.caso_especial, "Cero con signo")

        # -0.0
        res_ncero = simular_newton_raphson(-0.0)
        self.assertEqual(res_ncero.raiz_estimada_bits, NEG_ZERO)
        self.assertEqual(res_ncero.caso_especial, "Cero con signo")

        # Negativo
        res_neg = simular_newton_raphson(-4.0)
        self.assertEqual(res_neg.raiz_estimada_bits, CANONICAL_NAN)
        self.assertEqual(res_neg.caso_especial, "Negativo")

        # +Infinito
        res_inf = simular_newton_raphson(math.inf)
        self.assertEqual(res_inf.raiz_estimada_bits, POS_INFINITY)
        self.assertEqual(res_inf.caso_especial, "+Infinito")

        # NaN
        res_nan = simular_newton_raphson(float("nan"))
        self.assertEqual(res_nan.caso_especial, "NaN")
        self.assertTrue(math.isnan(res_nan.raiz_estimada))

    def test_estrategias_semilla_newton(self) -> None:
        """Verifica que las distintas estrategias de semilla inicial converjan."""
        for est in ("peña", "uno", "exponente"):
            res = simular_newton_raphson(25.0, estrategia_semilla=est)
            self.assertTrue(res.convergido)
            self.assertAlmostEqual(res.raiz_estimada, 5.0, places=14)

    # -------------------------------------------------------------------------
    # 4. Pruebas del Oráculo Canónico y Distancias ULP
    # -------------------------------------------------------------------------

    def test_oraculo_fsqrt_float_y_bits(self) -> None:
        """Verifica que el oráculo calcule patrones de 64 bits precisos."""
        # Normal
        self.assertEqual(OraculoIEEE754.fsqrt_float(4.0), 2.0)
        self.assertEqual(OraculoIEEE754.fsqrt_bits(float_a_bits(4.0)), float_a_bits(2.0))

        # Cero con signo
        self.assertEqual(OraculoIEEE754.fsqrt_bits(POS_ZERO), POS_ZERO)
        self.assertEqual(OraculoIEEE754.fsqrt_bits(NEG_ZERO), NEG_ZERO)

        # Negativo -> NaN canónico
        self.assertEqual(OraculoIEEE754.fsqrt_bits(float_a_bits(-1.0)), CANONICAL_NAN)

        # +Infinito
        self.assertEqual(OraculoIEEE754.fsqrt_bits(POS_INFINITY), POS_INFINITY)

    def test_distancia_ulps(self) -> None:
        """Verifica el cálculo de distancias en ULPs."""
        bits_1 = float_a_bits(1.0)
        bits_1_mas_ulp = bits_1 + 1
        self.assertEqual(OraculoIEEE754.distancia_ulps(bits_1, bits_1), 0)
        self.assertEqual(OraculoIEEE754.distancia_ulps(bits_1, bits_1_mas_ulp), 1)

        # Ceros tienen distancia 0
        self.assertEqual(OraculoIEEE754.distancia_ulps(POS_ZERO, NEG_ZERO), 0)

    def test_validar_fsqrt(self) -> None:
        """Verifica el validador de resultados frente al oráculo."""
        bits_4 = float_a_bits(4.0)
        bits_2 = float_a_bits(2.0)
        valido, msg = OraculoIEEE754.validar_fsqrt(bits_4, bits_2)
        self.assertTrue(valido)
        self.assertIn("Correcto", msg)

        # Discrepancia intencional
        bits_falso = float_a_bits(3.0)
        invalido, msg_inv = OraculoIEEE754.validar_fsqrt(bits_4, bits_falso)
        self.assertFalse(invalido)
        self.assertIn("Discrepancia", msg_inv)

        # Caso negativo
        valido_neg, _ = OraculoIEEE754.validar_fsqrt(float_a_bits(-4.0), CANONICAL_NAN)
        self.assertTrue(valido_neg)

    # -------------------------------------------------------------------------
    # 5. Pruebas del Catálogo de Casos de Prueba
    # -------------------------------------------------------------------------

    def test_catalogo_casos_prueba(self) -> None:
        """El catálogo de casos de prueba debe contener todas las categorías requeridas."""
        catalogo = generar_catalogo_casos_prueba()
        self.assertGreater(len(catalogo), 20)

        categorias = {c["categoria"] for c in catalogo}
        self.assertIn("exactos", categorias)
        self.assertIn("ceros", categorias)
        self.assertIn("fraccionarios", categorias)
        self.assertIn("irracionales", categorias)
        self.assertIn("constantes", categorias)
        self.assertIn("escalas", categorias)
        self.assertIn("subnormales", categorias)
        self.assertIn("especiales", categorias)

        for caso in catalogo:
            self.assertIn("nombre", caso)
            self.assertIn("entrada_bits", caso)
            self.assertIn("esperado_bits", caso)
            self.assertIn("hex_entrada", caso)
            self.assertIn("hex_esperado", caso)


if __name__ == "__main__":
    unittest.main()
