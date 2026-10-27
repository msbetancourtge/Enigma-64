"""
Suite de pruebas unitarias para el módulo FPU de Enigma-64.

Verifica directamente sobre la CPU oficial de Enigma-64:
  1. FPU_DESEMPAQUETAR: Descomposición de signo, exponente y mantisa de 53 bits con bit implícito.
  2. FPU_EMPAQUETAR: Reconstrucción idéntica bit a bit al estándar IEEE 754 de 64 bits.
  3. FADD: Suma con alineación de mantisas, evaluación de diferencia de exponentes y renormalización.
  4. FSUB: Resta con alineación, cambio de signo, cancelación total y catastrófica.
"""

from __future__ import annotations

import unittest

from enigma64.fpu import (
    EmuladorFPUEnigma64,
    float_a_ieee64,
    ieee64_a_float,
    compilar_fpu,
)


class TestFPUEnigma64(unittest.TestCase):
    """Pruebas unitarias de las subrutinas de bajo nivel de la FPU de Enigma-64."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fpu = EmuladorFPUEnigma64()

    def test_compilacion_modulo(self) -> None:
        """Verifica que el código ensamblador de la FPU ensamble correctamente."""
        binario = compilar_fpu(0x00200000)
        self.assertGreater(len(binario), 0)
        self.assertIsInstance(binario, bytes)

    def test_desempaquetar_uno(self) -> None:
        """1.0: Signo=0, Exponente=1023 (0x3FF), Mantisa=0x0010000000000000 (bit 52 implícito)."""
        signo, exp, mantisa = self.fpu.desempaquetar(1.0)
        self.assertEqual(signo, 0)
        self.assertEqual(exp, 1023)
        self.assertEqual(mantisa, 1 << 52)

    def test_desempaquetar_negativo(self) -> None:
        """-2.5: Signo=1, Exponente=1024 (0x400), Mantisa=(1.01)_2 * 2^52."""
        signo, exp, mantisa = self.fpu.desempaquetar(-2.5)
        self.assertEqual(signo, 1)
        self.assertEqual(exp, 1024)
        # 1.25 * 2^52 = 0x0014000000000000
        esperado_mantisa = (1 << 52) | (1 << 50)
        self.assertEqual(mantisa, esperado_mantisa)

    def test_desempaquetar_cero(self) -> None:
        """0.0: Signo=0, Exponente=0, Mantisa=0 (sin bit implícito)."""
        signo, exp, mantisa = self.fpu.desempaquetar(0.0)
        self.assertEqual(signo, 0)
        self.assertEqual(exp, 0)
        self.assertEqual(mantisa, 0)

    def test_empaquetar_canonica(self) -> None:
        """Comprueba que FPU_EMPAQUETAR reconstruye el patrón IEEE 754 exacto."""
        # 1.0: S=0, E=1023, M=1<<52
        u64 = self.fpu.empaquetar(0, 1023, 1 << 52)
        self.assertEqual(u64, float_a_ieee64(1.0))
        self.assertEqual(ieee64_a_float(u64), 1.0)

        # -2.5: S=1, E=1024, M=(1<<52) | (1<<50)
        u64_neg = self.fpu.empaquetar(1, 1024, (1 << 52) | (1 << 50))
        self.assertEqual(u64_neg, float_a_ieee64(-2.5))
        self.assertEqual(ieee64_a_float(u64_neg), -2.5)

    def test_empaquetar_cero(self) -> None:
        """0.0 empaquetado debe retornar 0."""
        u64 = self.fpu.empaquetar(0, 0, 0)
        self.assertEqual(u64, 0)

    def test_inversa_desempaquetar_empaquetar(self) -> None:
        """EMPAQUETAR(DESEMPAQUETAR(x)) == x para un conjunto variado de números."""
        valores = [1.0, -1.0, 2.0, 0.5, 3.141592653589793, 1024.5, -42.125]
        for val in valores:
            s, e, m = self.fpu.desempaquetar(val)
            rec = self.fpu.empaquetar(s, e, m)
            self.assertEqual(rec, float_a_ieee64(val), f"Fallo al reconstruir {val}")

    def test_fadd_exponentes_iguales(self) -> None:
        """FADD: Suma de números con exponentes iguales."""
        # 1.0 + 1.0 = 2.0
        self.assertEqual(self.fpu.sumar(1.0, 1.0), 2.0)
        # 1.5 + 2.5 = 4.0
        self.assertEqual(self.fpu.sumar(1.5, 2.5), 4.0)

    def test_fadd_alineacion_exponentes(self) -> None:
        """FADD: Suma con alineación por corrimiento de mantisas (Delta E > 0)."""
        # Delta E = 1: 1.0 + 0.5 = 1.5
        self.assertEqual(self.fpu.sumar(1.0, 0.5), 1.5)
        # Delta E = 2: 1.0 + 0.25 = 1.25
        self.assertEqual(self.fpu.sumar(1.0, 0.25), 1.25)
        # Delta E = 11: 1024.0 + 0.5 = 1024.5
        self.assertEqual(self.fpu.sumar(1024.0, 0.5), 1024.5)
        # Orden inverso: B > A (el intercambio swap garantiza E_A >= E_B)
        self.assertEqual(self.fpu.sumar(0.25, 1.0), 1.25)

    def test_fadd_con_ceros(self) -> None:
        """FADD: Identidad aditiva con cero."""
        self.assertEqual(self.fpu.sumar(7.5, 0.0), 7.5)
        self.assertEqual(self.fpu.sumar(0.0, 7.5), 7.5)

    def test_fadd_numeros_negativos(self) -> None:
        """FADD: Suma de números negativos (signos iguales)."""
        self.assertEqual(self.fpu.sumar(-2.5, -1.5), -4.0)

    def test_fadd_signos_opuestos(self) -> None:
        """FADD: Suma de números con signos opuestos (ejecuta resta interna de mantisas)."""
        self.assertEqual(self.fpu.sumar(100.0, -40.0), 60.0)
        self.assertEqual(self.fpu.sumar(-40.0, 100.0), 60.0)

    def test_fadd_subdesbordamiento_delta_e(self) -> None:
        """FADD: Si Delta E > 54, el término menor se desprecia por completo."""
        self.assertEqual(self.fpu.sumar(1.0, 1e-18), 1.0)

    def test_fsub_resta_basica(self) -> None:
        """FSUB: Resta directa entre números positivos."""
        self.assertEqual(self.fpu.restar(5.0, 3.0), 2.0)
        self.assertEqual(self.fpu.restar(10.5, 0.5), 10.0)

    def test_fsub_resultado_negativo(self) -> None:
        """FSUB: Resta donde el sustraendo es mayor que el minuendo (cambio de signo)."""
        self.assertEqual(self.fpu.restar(3.0, 5.0), -2.0)

    def test_fsub_cancelacion_cero(self) -> None:
        """FSUB: A - A = 0.0."""
        self.assertEqual(self.fpu.restar(1.0, 1.0), 0.0)
        self.assertEqual(self.fpu.restar(12345.678, 12345.678), 0.0)

    def test_fsub_con_ceros(self) -> None:
        """FSUB: Operaciones con cero."""
        self.assertEqual(self.fpu.restar(5.0, 0.0), 5.0)
        self.assertEqual(self.fpu.restar(0.0, 5.0), -5.0)

    def test_fsub_numeros_negativos(self) -> None:
        """FSUB: Resta con números negativos."""
        # (-5.0) - (-3.0) = -2.0
        self.assertEqual(self.fpu.restar(-5.0, -3.0), -2.0)

    def test_fsub_cancelacion_catastrofica(self) -> None:
        """FSUB: Resta de operandos muy cercanos requiere corrimiento múltiple a la izquierda."""
        delta = 1.0 / (1 << 20)  # 2^-20
        a = 1.0 + delta
        b = 1.0
        resultado = self.fpu.restar(a, b)
        self.assertAlmostEqual(resultado, delta, places=12)


if __name__ == "__main__":
    unittest.main()
