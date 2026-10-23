"""
Pruebas unitarias del modulo Registros & ALU del Enigma-64.

Ejecutar:  python3 -m unittest test_registros_alu -v
       o:  python3 test_registros_alu.py
"""

import unittest

from enigma64 import (
    ALU,
    BancoRegistros,
    DivisionPorCero,
    OperacionInvalida,
    RegistroInvalido,
    SP_RESET,
    a_con_signo,
)
from enigma64.registros import (
    COD_PC,
    COD_R0,
    COD_R1,
    COD_R2,
    COD_R3,
    COD_R6,
    COD_SR,
)

MASK64 = 0xFFFFFFFFFFFFFFFF
INT64_MIN = 0x8000000000000000
INT64_MAX = 0x7FFFFFFFFFFFFFFF
MENOS_UNO = MASK64


class PruebasBancoRegistros(unittest.TestCase):
    def setUp(self):
        self.banco = BancoRegistros()

    def test_r0_cableado_a_cero(self):
        self.banco.escribir(COD_R0, 0xDEADBEEF)
        self.assertEqual(self.banco.leer(COD_R0), 0)

    def test_valores_de_reset(self):
        self.assertEqual(self.banco.sp, SP_RESET)
        self.assertEqual(self.banco.pc, 0)
        self.assertEqual(self.banco.sp, 0x00000000EFFFFFFF)

    def test_enmascarado_a_64_bits(self):
        self.banco.escribir(COD_R1, 1 << 70)
        self.assertEqual(self.banco.leer(COD_R1), 0)
        self.banco.escribir(COD_R1, -1)
        self.assertEqual(self.banco.leer(COD_R1), MASK64)

    def test_registros_reservados_rechazados(self):
        with self.assertRaises(RegistroInvalido):
            self.banco.leer(0xA)
        with self.assertRaises(RegistroInvalido):
            self.banco.escribir(0xF, 1)

    def test_pc_avanza_por_longitud_variable(self):
        self.banco.pc = 0x00200000
        self.banco.avanzar_pc(4)   # formato 3 (4 bytes)
        self.banco.avanzar_pc(3)   # formato 1 (3 bytes)
        self.banco.avanzar_pc(1)   # HLT
        self.assertEqual(self.banco.pc, 0x00200008)

    def test_banderas_individuales(self):
        self.banco.escribir_bandera("S", 1)
        self.assertTrue(self.banco.en_supervisor)
        self.banco.escribir_bandera("S", 0)
        self.assertFalse(self.banco.en_supervisor)

    def test_posiciones_de_bits_del_sr(self):
        self.banco.sr = 0
        for nombre, bit in (("Z", 0), ("N", 1), ("C", 2), ("V", 3),
                            ("M", 4), ("I", 5), ("S", 6)):
            self.banco.sr = 1 << bit
            self.assertEqual(self.banco.leer_bandera(nombre), 1, nombre)

    def test_aplicar_banderas_respeta_las_afectadas(self):
        self.banco.sr = 0
        self.banco.escribir_bandera("C", 1)
        # MUL solo afecta Z y N: C debe sobrevivir intacta
        self.banco.aplicar_banderas({"Z": 1, "N": 0, "C": 0},
                                    afectadas=frozenset({"Z", "N"}))
        self.assertEqual(self.banco.leer_bandera("Z"), 1)
        self.assertEqual(self.banco.leer_bandera("C"), 1)

    def test_observador_para_la_gui(self):
        llamadas = []
        self.banco.suscribir(lambda b: llamadas.append(b.leer(COD_R1)))
        self.banco.escribir(COD_R1, 0x42)
        self.assertEqual(llamadas[-1], 0x42)

    def test_snapshot_tiene_todo_lo_que_pinta_la_gui(self):
        snap = self.banco.snapshot()
        self.assertEqual(len(snap["registros"]), 10)
        self.assertEqual(snap["registros"]["R6"]["alias"], "SP")
        self.assertEqual(snap["registros"]["R6"]["hex"], "0x00000000EFFFFFFF")
        self.assertIn("S", snap["banderas"])


class PruebasAritmetica(unittest.TestCase):
    def setUp(self):
        self.alu = ALU()

    def test_suma_simple(self):
        r = self.alu.ejecutar("ADD", 5, 3)
        self.assertEqual(r.valor, 8)
        self.assertEqual(r.banderas["Z"], 0)
        self.assertEqual(r.banderas["C"], 0)
        self.assertEqual(r.banderas["V"], 0)

    def test_suma_con_acarreo_sin_signo(self):
        r = self.alu.ejecutar("ADD", MASK64, 1)
        self.assertEqual(r.valor, 0)
        self.assertEqual(r.banderas["C"], 1)
        self.assertEqual(r.banderas["Z"], 1)
        self.assertEqual(r.banderas["V"], 0)  # -1 + 1 = 0, sin desbordar

    def test_suma_con_desbordamiento_con_signo(self):
        r = self.alu.ejecutar("ADD", INT64_MAX, 1)
        self.assertEqual(r.valor, INT64_MIN)
        self.assertEqual(r.banderas["V"], 1)
        self.assertEqual(r.banderas["N"], 1)
        self.assertEqual(r.banderas["C"], 0)

    def test_resta_con_prestamo(self):
        r = self.alu.ejecutar("SUB", 3, 5)
        self.assertEqual(a_con_signo(r.valor), -2)
        self.assertEqual(r.banderas["C"], 1)  # convencion "prestamo"
        self.assertEqual(r.banderas["N"], 1)

    def test_resta_sin_prestamo(self):
        r = self.alu.ejecutar("SUB", 5, 3)
        self.assertEqual(r.valor, 2)
        self.assertEqual(r.banderas["C"], 0)

    def test_resta_da_cero(self):
        r = self.alu.ejecutar("SUB", 6, 6)
        self.assertEqual(r.banderas["Z"], 1)
        self.assertEqual(r.banderas["N"], 0)

    def test_resta_con_desbordamiento_con_signo(self):
        r = self.alu.ejecutar("SUB", INT64_MIN, 1)
        self.assertEqual(r.banderas["V"], 1)

    def test_multiplicacion_guarda_64_bits_bajos(self):
        r = self.alu.ejecutar("MUL", 1 << 40, 1 << 40)
        self.assertEqual(r.valor, 0)
        self.assertEqual(r.banderas["Z"], 1)
        self.assertNotIn("C", r.afectadas)
        self.assertNotIn("V", r.afectadas)

    def test_multiplicacion_del_factorial(self):
        # Trazado del Algoritmo 1: 120 * 1 = 120
        r = self.alu.ejecutar("MUL", 120, 1)
        self.assertEqual(r.valor, 0x78)

    def test_division_trunca_hacia_cero(self):
        r = self.alu.ejecutar("DIV", MENOS_UNO - 6, 2)  # -7 / 2
        self.assertEqual(a_con_signo(r.valor), -3)      # NO -4

    def test_division_positiva(self):
        r = self.alu.ejecutar("DIV", 48, 18)
        self.assertEqual(r.valor, 2)

    def test_division_por_cero(self):
        with self.assertRaises(DivisionPorCero):
            self.alu.ejecutar("DIV", 10, 0)

    def test_inc_y_dec(self):
        r = self.alu.ejecutar("INC", 41)
        self.assertEqual(r.valor, 42)
        r = self.alu.ejecutar("DEC", 1)
        self.assertEqual(r.valor, 0)
        self.assertEqual(r.banderas["Z"], 1)
        self.assertNotIn("C", r.afectadas)  # INC/DEC no afectan C


class PruebasLogicaYDesplazamientos(unittest.TestCase):
    def setUp(self):
        self.alu = ALU()

    def test_operaciones_logicas(self):
        self.assertEqual(self.alu.ejecutar("AND", 0b1100, 0b1010).valor, 0b1000)
        self.assertEqual(self.alu.ejecutar("OR", 0b1100, 0b1010).valor, 0b1110)
        self.assertEqual(self.alu.ejecutar("XOR", 0b1100, 0b1010).valor, 0b0110)
        self.assertEqual(self.alu.ejecutar("NOT", 0).valor, MASK64)

    def test_logicas_no_tocan_c_ni_v(self):
        r = self.alu.ejecutar("AND", 0xFF, 0x0F)
        self.assertEqual(r.afectadas, frozenset({"Z", "N"}))

    def test_shl_construye_0x00200000(self):
        # Patron que usan los tres algoritmos: ADDI 0x20 + SHL 16
        r = self.alu.ejecutar("SHL", 0x0020, 16)
        self.assertEqual(r.valor, 0x00200000)

    def test_shl_construye_0xc0000000(self):
        # Validacion 2 del Cargador: ADDI 3 + SHL 30
        r = self.alu.ejecutar("SHL", 3, 30)
        self.assertEqual(r.valor, 0xC0000000)

    def test_shl_acarreo_es_el_ultimo_bit_expulsado(self):
        r = self.alu.ejecutar("SHL", 1 << 63, 1)
        self.assertEqual(r.valor, 0)
        self.assertEqual(r.banderas["C"], 1)

    def test_shr_rellena_con_ceros(self):
        r = self.alu.ejecutar("SHR", MASK64, 60)
        self.assertEqual(r.valor, 0xF)
        self.assertEqual(r.banderas["N"], 0)

    def test_asr_preserva_el_signo(self):
        r = self.alu.ejecutar("ASR", MENOS_UNO, 32)  # -1 >> 32
        self.assertEqual(r.valor, MASK64)
        self.assertEqual(r.banderas["N"], 1)

    def test_asr_vs_shr_en_negativo(self):
        negativo = 0xFFFFFFFFFFFFFFF0  # -16
        self.assertEqual(a_con_signo(self.alu.ejecutar("ASR", negativo, 1).valor), -8)
        self.assertNotEqual(self.alu.ejecutar("SHR", negativo, 1).valor, MASK64 - 7)

    def test_desplazamiento_de_cero_no_toca_c(self):
        r = self.alu.ejecutar("SHL", 0xFF, 0)
        self.assertEqual(r.valor, 0xFF)
        self.assertNotIn("C", r.afectadas)

    def test_desplazamiento_mayor_o_igual_a_64(self):
        self.assertEqual(self.alu.ejecutar("SHL", MASK64, 64).valor, 0)
        self.assertEqual(self.alu.ejecutar("SHL", MASK64, 100).valor, 0)
        self.assertEqual(self.alu.ejecutar("ASR", MENOS_UNO, 100).valor, MASK64)


class PruebasCMP(unittest.TestCase):
    def setUp(self):
        self.alu = ALU()
        self.banco = BancoRegistros()

    def test_cmp_no_escribe_destino(self):
        r = self.alu.ejecutar("CMP", 12, 18)
        self.assertFalse(r.escribe_destino)

    def test_cmp_del_algoritmo_de_euclides(self):
        # Paso 3 del trazado: CMP R2=12, R3=18 -> Z=0, N=1 (salta por JN)
        r = self.alu.ejecutar("CMP", 12, 18)
        self.assertEqual(r.banderas["Z"], 0)
        self.assertEqual(r.banderas["N"], 1)
        # Paso 5: CMP 6, 6 -> Z=1 (salta por JZ)
        r = self.alu.ejecutar("CMP", 6, 6)
        self.assertEqual(r.banderas["Z"], 1)
        self.assertEqual(r.banderas["N"], 0)

    def test_operacion_desconocida(self):
        with self.assertRaises(OperacionInvalida):
            self.alu.ejecutar("NAND", 1, 2)


class PruebasIntegracion(unittest.TestCase):
    """Reproduce el bucle del factorial usando solo registros y ALU."""

    def test_trazado_del_factorial(self):
        banco = BancoRegistros()
        alu = ALU()

        banco.escribir(COD_R2, 5)   # N = 5
        banco.escribir(COD_R3, 1)   # factorial = 1

        # CMP R2, R0
        r = alu.ejecutar("CMP", banco.leer(COD_R2), banco.leer(COD_R0))
        banco.aplicar_banderas(r.banderas, r.afectadas)
        self.assertEqual(banco.leer_bandera("Z"), 0)  # no salta por JZ

        iteraciones = 0
        while True:
            # MUL R3, R3, R2
            r = alu.ejecutar("MUL", banco.leer(COD_R3), banco.leer(COD_R2))
            banco.aplicar_banderas(r.banderas, r.afectadas)
            banco.escribir(COD_R3, r.valor)

            # SUBI R2, R2, 1
            r = alu.ejecutar("SUBI", banco.leer(COD_R2), 1)
            banco.aplicar_banderas(r.banderas, r.afectadas)
            banco.escribir(COD_R2, r.valor)

            iteraciones += 1
            if banco.leer_bandera("Z") == 1:  # JNZ no bifurca
                break

        self.assertEqual(iteraciones, 5)
        self.assertEqual(banco.leer(COD_R3), 0x78)  # 120

    def test_trazado_de_euclides(self):
        banco = BancoRegistros()
        alu = ALU()
        banco.escribir(COD_R2, 48)
        banco.escribir(COD_R3, 18)

        for _ in range(100):
            r = alu.ejecutar("CMP", banco.leer(COD_R2), banco.leer(COD_R3))
            banco.aplicar_banderas(r.banderas, r.afectadas)
            if banco.leer_bandera("Z"):
                break
            if banco.leer_bandera("N"):  # A < B
                r = alu.ejecutar("SUB", banco.leer(COD_R3), banco.leer(COD_R2))
                banco.escribir(COD_R3, r.valor)
            else:
                r = alu.ejecutar("SUB", banco.leer(COD_R2), banco.leer(COD_R3))
                banco.escribir(COD_R2, r.valor)

        self.assertEqual(banco.leer(COD_R2), 6)  # MCD(48, 18)


if __name__ == "__main__":
    unittest.main(verbosity=2)
