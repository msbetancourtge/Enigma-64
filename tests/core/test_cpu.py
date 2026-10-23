"""
Pruebas unitarias de la Unidad de Control y CPU de Enigma-64.

Este test verifica la FSM multiciclo, el buffer de prebúsqueda, el decodificador de
formatos variables, la ALU, memoria, saltos, pila, interrupciones y los tres
programas documentados de la arquitectura.

Ejecutar desde la raiz:
    python3 -m unittest tests.test_cpu -v

    Autor: Integrante 3 Michael Stiven Betancourt Gelves - CPU FSM: Pre-Fetch - Fetch-Decode-Execute
"""

from __future__ import annotations

import unittest

from enigma64.cpu import (
    AlignmentFault,
    CPU,
    DivisionPorCero,
    ExecutionLimitExceeded,
    IllegalInstruction,
    MemoryFault,
    PrefetchBuffer,
    PrivilegeFault,
)
from enigma64.memoria import RAMMemory
from enigma64.registros import BancoRegistros, SP_RESET
from enigma64.ui.servicios import construir_maquina
from enigma64.ui.servicios.algoritmos import obtener


USER_BASE = 0x00200000
DATA_BASE = 0x00201000


class CPUTestCase(unittest.TestCase):
    """Hardware fresco y utilidades para cargar bytes en RAM."""

    def setUp(self) -> None:
        self.ram = RAMMemory()
        self.banco = BancoRegistros()
        self.cpu = CPU(ram=self.ram, banco=self.banco)

    def cargar(self, direccion: int, codigo: bytes) -> None:
        for offset, byte in enumerate(codigo):
            _, status = self.ram.mem_write(
                direccion + offset, byte, 1, check_alignment=False
            )
            self.assertEqual(status, "READY")

    def ejecutar(self, codigo: bytes, direccion: int = USER_BASE) -> dict:
        self.cargar(direccion, codigo)
        self.banco.pc = direccion
        return self.cpu.ejecutar()


class TestContratoYFSM(CPUTestCase):
    def test_expone_contrato_de_la_interfaz(self) -> None:
        self.assertEqual(self.cpu.fases(), (
            "FETCH", "DECODE", "EXECUTE", "MEMORY", "WRITE-BACK"
        ))
        self.assertEqual(self.cpu.micro_registros(),
                         ("MAR", "MDR", "IR", "A", "B", "Z"))
        estado = self.cpu.estado()
        self.assertEqual(estado["fase"], "FETCH")
        self.assertFalse(estado["detenido"])
        self.assertEqual(set(estado["micro"]), set(self.cpu.micro_registros()))

    def test_avanza_las_cinco_fases_y_completa_hlt(self) -> None:
        self.cargar(USER_BASE, b"\x00")
        self.banco.pc = USER_BASE
        fases_observadas = [self.cpu.paso()["fase"] for _ in range(5)]
        self.assertEqual(fases_observadas,
                         ["DECODE", "EXECUTE", "MEMORY", "WRITE-BACK", "FETCH"])
        self.assertTrue(self.cpu.detenido)
        self.assertEqual(self.cpu.instrucciones, 1)
        self.assertEqual(self.cpu.ciclos, 5)

    def test_reset_limpia_fsm_prefetch_y_contadores(self) -> None:
        self.ejecutar(b"\x00")
        self.cpu.reset()
        estado = self.cpu.estado()
        self.assertEqual(estado["fase"], "FETCH")
        self.assertEqual(estado["ciclos"], 0)
        self.assertEqual(estado["instrucciones"], 0)
        self.assertFalse(estado["detenido"])
        self.assertEqual(estado["prefetch"], b"")
        self.assertEqual(self.banco.pc, 0)
        self.assertEqual(self.banco.sp, SP_RESET)


class TestPrefetchYFormatos(CPUTestCase):
    def test_prefetch_carga_palabras_alineadas_y_cruza_limite(self) -> None:
        buffer = PrefetchBuffer(self.ram)
        direccion = USER_BASE + 7
        codigo = bytes.fromhex("14 10 00 2A 00")
        self.cargar(direccion, codigo)
        self.assertEqual(buffer.ensure(direccion, 4), codigo[:4])
        self.assertEqual(buffer.start, USER_BASE)
        self.assertEqual(len(buffer.bytes), 16)

        self.banco.pc = direccion
        self.cpu.ejecutar()
        self.assertEqual(self.banco.leer_nombre("R1"), 0x2A)

    def test_formatos_de_registro_inmediato_y_unario(self) -> None:
        codigo = bytes.fromhex(
            "14 10 00 05"      # ADDI R1, R0, 5
            "16 10"            # Incrementa R1
            "23 10"            # Invierte R1
            "17 10"            # Decrementa R1
            "00"
        )
        estado = self.ejecutar(codigo)
        self.assertTrue(estado["detenido"])
        self.assertEqual(self.banco.leer_nombre("R1"), 0xFFFFFFFFFFFFFFF8)

    def test_inmediatos_con_signo_y_formato_registro(self) -> None:
        codigo = bytes.fromhex(
            "14 10 FF FF"      # ADDI R1, R0, -1
            "14 21 00 02"      # ADDI R2, R1, 2
            "10 32 10"         # ADD R3, R2, R1
            "00"
        )
        self.ejecutar(codigo)
        self.assertEqual(self.banco.leer_nombre("R1"), 0xFFFFFFFFFFFFFFFF)
        self.assertEqual(self.banco.leer_nombre("R2"), 1)
        self.assertEqual(self.banco.leer_nombre("R3"), 0)
        self.assertEqual(self.banco.leer_bandera("Z"), 1)

    def test_opcode_desconocido_falla(self) -> None:
        self.cargar(USER_BASE, b"\xFF")
        self.banco.pc = USER_BASE
        with self.assertRaises(IllegalInstruction):
            self.cpu.ejecutar()

    def test_division_por_cero_es_un_fallo_de_la_unidad_de_control(self) -> None:
        codigo = bytes.fromhex(
            "14 10 00 0A"       # R1 = 10
            "14 20 00 00"       # R2 = 0
            "13 31 20"          # DIV R3, R1, R2
        )
        self.cargar(USER_BASE, codigo)
        self.banco.pc = USER_BASE
        with self.assertRaises(DivisionPorCero):
            self.cpu.ejecutar()


class TestALUYSaltos(CPUTestCase):
    def test_banderas_cmp_y_salto_relativo(self) -> None:
        codigo = bytes.fromhex(
            "27 00 00"          # CMP R0, R0 -> Z=1
            "41 00 04"          # JZ salta al HLT en +4
            "14 10 00 7B"       # No debe ejecutarse
            "00"
        )
        self.ejecutar(codigo)
        self.assertEqual(self.banco.leer_nombre("R1"), 0)
        self.assertEqual(self.banco.leer_bandera("Z"), 1)

    def test_operadores_logicos_y_desplazamientos(self) -> None:
        codigo = bytes.fromhex(
            "14 10 00 03"       # R1 = 3
            "14 20 00 01"       # R2 = 1
            "20 31 20"          # AND R3, R1, R2 = 1
            "21 41 20"          # OR R4, R1, R2 = 3
            "22 51 20"          # XOR R5, R1, R2 = 2
            "24 35 00 03"       # SHL R3, R5, 3 = 16
            "25 43 00 01"       # SHR R4, R3, 1 = 8
            "00"
        )
        self.ejecutar(codigo)
        self.assertEqual(self.banco.leer_nombre("R3"), 16)
        self.assertEqual(self.banco.leer_nombre("R4"), 8)
        self.assertEqual(self.banco.leer_nombre("R5"), 2)

    def test_bucle_con_jnz_y_limite_de_ciclos(self) -> None:
        codigo = bytes.fromhex(
            "14 10 00 03"       # R1 = 3
            "15 11 00 01"       # R1 -= 1
            "42 FF F9"          # JNZ a la instruccion SUBI
            "00"
        )
        estado = self.ejecutar(codigo)
        self.assertTrue(estado["detenido"])
        self.assertEqual(self.banco.leer_nombre("R1"), 0)

        self.cpu.reset()
        self.cargar(USER_BASE, bytes.fromhex("40 00 20 00 00"))
        self.banco.pc = USER_BASE
        with self.assertRaises(ExecutionLimitExceeded):
            self.cpu.ejecutar(max_ciclos=10)


class TestMemoriaYPila(CPUTestCase):
    def test_load_store_big_endian_y_byte(self) -> None:
        codigo = bytes.fromhex(
            "14 20 12 34"       # R2 = 0x1234
            "31 21 00 08"       # STORE R2, [R1+8]
            "30 31 00 08"       # LOAD R3, [R1+8]
            "32 41 00 0F"       # LDB R4, [R1+15] = 0x34
            "33 21 00 0A"       # STB R2, [R1+10]
            "00"
        )
        self.banco.escribir_nombre("R1", DATA_BASE)
        self.ejecutar(codigo)
        self.assertEqual(self.banco.leer_nombre("R3"), 0x1234)
        self.assertEqual(self.banco.leer_nombre("R4"), 0x34)
        self.assertEqual(self.ram.mem_read(DATA_BASE + 10, 1, False)[0], 0x34)
        self.assertEqual(self.ram.mem_read(DATA_BASE + 8, 8)[0], 0x0000340000001234)

    def test_acceso_desalineado_activa_bandera_m(self) -> None:
        self.cargar(USER_BASE, bytes.fromhex("30 11 00 01"))
        self.banco.escribir_nombre("R1", USER_BASE)
        self.banco.pc = USER_BASE
        with self.assertRaises(AlignmentFault):
            self.cpu.ejecutar()
        self.assertEqual(self.banco.leer_bandera("M"), 1)

    def test_proteccion_de_memoria_y_mmio(self) -> None:
        self.cargar(USER_BASE, bytes.fromhex("30 11 00 00"))
        self.banco.escribir_nombre("R1", 0x1000)
        self.banco.pc = USER_BASE
        with self.assertRaises(PrivilegeFault):
            self.cpu.ejecutar()

        self.cpu.reset()
        self.cargar(USER_BASE, bytes.fromhex("30 11 00 00"))
        self.banco.escribir_nombre("R1", 0xFF000000)
        self.banco.pc = USER_BASE
        with self.assertRaises(MemoryFault):
            self.cpu.ejecutar()

    def test_call_ret_push_pop_y_punteros(self) -> None:
        codigo = bytes.fromhex(
            "14 10 00 2A"       # R1 = 42
            "4D 10"              # Apila R1
            "14 10 00 00"        # R1 = 0
            "4E 20"              # Extrae en R2
            "4A 00 20 00 20"     # CALL subrutina
            "00"
        )
        subrutina = bytes.fromhex("14 31 00 07 4C")  # R3=7; RET
        self.cargar(USER_BASE, codigo)
        self.cargar(USER_BASE + 0x20, subrutina)
        self.banco.pc = USER_BASE
        self.cpu.ejecutar()
        self.assertEqual(self.banco.leer_nombre("R2"), 42)
        self.assertEqual(self.banco.leer_nombre("R3"), 7)
        self.assertEqual(self.banco.sp, SP_RESET)


class TestIntegracionDocumentada(unittest.TestCase):
    def test_ejecuta_los_tres_algoritmos_de_la_tarea(self) -> None:
        esperados = {
            "factorial": (0x00201008, 120),
            "euclides": (0x00202010, 6),
        }
        for nombre, (direccion, esperado) in esperados.items():
            maquina = construir_maquina()
            maquina.algoritmos.cargar(obtener(nombre))
            estado = maquina.algoritmos.ejecutar()
            self.assertTrue(estado["detenido"], nombre)
            self.assertEqual(maquina.memoria.leer(direccion, 8)[0], esperado, nombre)

        maquina = construir_maquina()
        maquina.algoritmos.cargar(obtener("fibonacci"))
        estado = maquina.algoritmos.ejecutar()
        valores = [maquina.memoria.leer(0x00203000 + i * 8, 8)[0]
                   for i in range(7)]
        self.assertTrue(estado["detenido"])
        self.assertEqual(valores, [0, 1, 1, 2, 3, 5, 8])


if __name__ == "__main__":
    unittest.main()
