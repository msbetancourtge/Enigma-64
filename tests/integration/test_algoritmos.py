"""
Suite de Pruebas Unitarias y de Integracion de Algoritmos - Enigma-64.

Implementa las responsabilidades del Integrante 7 (Tarea 10):
  1. Validacion de integridad binaria de los 3 programas de la Tarea 9
     (Factorial, Euclides y Fibonacci) contra la tabla de codificacion Big-Endian.
  2. Pruebas de carga en memoria RAM mediante el CargadorEnigma (.bin, .hex, .e64).
  3. Validacion de aislamiento de memoria y proteccion de vectores y pila.
  4. Simulacion y ejecucion completa paso a paso / continuo de los 3 algoritmos.
  5. Verificacion exacta de los resultados almacenados en celdas de RAM:
       - Factorial: Mem[0x00201008] == 120 (5!).
       - Euclides: Mem[0x00202010] == 6 (MCD(48, 18)).
       - Fibonacci: Mem[0x00203000..0x00203030] == [0, 1, 1, 2, 3, 5, 8].
  6. Casos adicionales con entradas variables (ej. Factorial(0)=1, MCD(35, 14)=7).
  7. Gancho de integracion con el futuro modulo CPU del Integrante 3.

Autor: Integrante 7 - Algoritmos & Tests (Alejandro Arguello Munoz)
"""

import os
import struct
import tempfile
import unittest
from typing import Optional, Tuple

from enigma64 import (
    ALU,
    BYTES_CARGADOR_FIRMWARE,
    BYTES_EUCLIDES,
    BYTES_FACTORIAL,
    BYTES_FIBONACCI,
    MASK64,
    PROGRAMA_EUCLIDES,
    PROGRAMA_FACTORIAL,
    PROGRAMA_FIBONACCI,
    PROGRAMAS_OFICIALES,
    STATUS_READY,
    USER_MEM_START,
    BancoRegistros,
    CargadorEnigma,
    RAMMemory,
    ViolacionProteccionMemoria,
    exportar_archivos_programas,
    inicializar_escenario_prueba,
    leer_byte_directo,
)


# ===========================================================================
# Runner / Despachador de Instrucciones de Prueba
# Permite ejecutar los 3 algoritmos usando la ALU y BancoRegistros existentes
# mientras el Integrante 3 entrega el modulo CPU oficial.
# ===========================================================================

class RunnerInstruccionesPrueba:
    """
    Emulador de ejecucion multiciclo minimo para validar los programas de la Tarea 9
    sobre la RAMMemory, ALU y BancoRegistros ya implementados.
    """

    def __init__(self, ram: RAMMemory, banco: BancoRegistros, alu: ALU):
        self.ram = ram
        self.banco = banco
        self.alu = alu
        self.ciclos_ejecutados = 0
        self.detenido = False

    def paso(self) -> bool:
        """
        Ejecuta una unica instruccion en la direccion actual de PC.
        Retorna True si la ejecucion debe continuar, False si se alcanzo HLT.
        """
        if self.detenido:
            return False

        pc_actual = self.banco.pc
        # Leer Opcode (Byte 0)
        byte_op, st = self.ram.mem_read(pc_actual, size_bytes=1, check_alignment=False)
        if st != STATUS_READY or byte_op is None:
            raise RuntimeError(f"Fallo al leer opcode en PC=0x{pc_actual:08X} (estado={st})")

        self.ciclos_ejecutados += 1

        # 0x00: HLT
        if byte_op == 0x00:
            self.detenido = True
            return False

        # Formato 1 (3 Bytes): ALU reg-a-reg (Op: 1B, Rd:Rs1: 1B, Rs2:0: 1B)
        # Opcodes: ADD=0x10, SUB=0x11, MUL=0x12, CMP=0x27
        if byte_op in (0x10, 0x11, 0x12, 0x27):
            map_op = {0x10: "ADD", 0x11: "SUB", 0x12: "MUL", 0x27: "CMP"}
            b1, _ = self.ram.mem_read(pc_actual + 1, size_bytes=1, check_alignment=False)
            b2, _ = self.ram.mem_read(pc_actual + 2, size_bytes=1, check_alignment=False)
            rd_code = (b1 >> 4) & 0x0F
            rs1_code = b1 & 0x0F
            rs2_code = (b2 >> 4) & 0x0F

            v_rs1 = self.banco.leer(rs1_code)
            v_rs2 = self.banco.leer(rs2_code)
            res = self.alu.ejecutar(map_op[byte_op], v_rs1, v_rs2)

            # Actualizar banderas de SR
            self.banco.aplicar_banderas(res.banderas, res.afectadas)

            # Si no es CMP (0x27), escribir resultado en Rd
            if byte_op != 0x27:
                self.banco.escribir(rd_code, res.valor)

            self.banco.pc = pc_actual + 3
            return True

        # Formato 3 (4 Bytes): Inmediato / Memoria (Op: 1B, Rd:Rs1: 1B, Imm16: 2B)
        # Opcodes: ADDI=0x14, SUBI=0x15, SHL=0x24, LOAD=0x30, STORE=0x31
        if byte_op in (0x14, 0x15, 0x24, 0x30, 0x31):
            b1, _ = self.ram.mem_read(pc_actual + 1, size_bytes=1, check_alignment=False)
            # Imm16 en Big-Endian con signo para aritmetica y memoria
            raw_imm, _ = self.ram.mem_read(pc_actual + 2, size_bytes=2, check_alignment=False)
            imm16_unsigned = raw_imm & 0xFFFF
            imm16_signed = struct.unpack(">h", struct.pack(">H", imm16_unsigned))[0]

            r_dest_code = (b1 >> 4) & 0x0F
            r_src_code = b1 & 0x0F

            if byte_op == 0x14:  # ADDI: Rd <- Rs1 + SignExtend(Imm16)
                v_rs1 = self.banco.leer(r_src_code)
                res = self.alu.ejecutar("ADDI", v_rs1, imm16_signed & MASK64)
                self.banco.aplicar_banderas(res.banderas, res.afectadas)
                self.banco.escribir(r_dest_code, res.valor)

            elif byte_op == 0x15:  # SUBI: Rd <- Rs1 - SignExtend(Imm16)
                v_rs1 = self.banco.leer(r_src_code)
                res = self.alu.ejecutar("SUBI", v_rs1, imm16_signed & MASK64)
                self.banco.aplicar_banderas(res.banderas, res.afectadas)
                self.banco.escribir(r_dest_code, res.valor)

            elif byte_op == 0x24:  # SHL: Rd <- Rs1 << Imm16
                v_rs1 = self.banco.leer(r_src_code)
                res = self.alu.ejecutar("SHL", v_rs1, imm16_unsigned)
                self.banco.aplicar_banderas(res.banderas, res.afectadas)
                self.banco.escribir(r_dest_code, res.valor)

            elif byte_op == 0x30:  # LOAD: Rd <- Memoria[Rb + Offset16] (64-bit)
                base = self.banco.leer(r_src_code)
                dir_efectiva = (base + imm16_signed) & 0xFFFFFFFF
                palabra, st_load = self.ram.mem_read(dir_efectiva, size_bytes=8, check_alignment=True)
                if st_load != STATUS_READY or palabra is None:
                    raise RuntimeError(f"Fallo LOAD en 0x{dir_efectiva:08X} (estado={st_load})")
                self.banco.escribir(r_dest_code, palabra)

            elif byte_op == 0x31:  # STORE: Memoria[Rb + Offset16] <- Rs (64-bit)
                base = self.banco.leer(r_src_code)
                dir_efectiva = (base + imm16_signed) & 0xFFFFFFFF
                v_rs = self.banco.leer(r_dest_code)
                _, st_store = self.ram.mem_write(dir_efectiva, v_rs, size_bytes=8, check_alignment=True)
                if st_store != STATUS_READY:
                    raise RuntimeError(f"Fallo STORE en 0x{dir_efectiva:08X} (estado={st_store})")

            self.banco.pc = pc_actual + 4
            return True

        # Formato 4 (3 Bytes): Salto Relativo (Op: 1B, Offset16 con signo: 2B)
        # Opcodes: JZ=0x41, JNZ=0x42, JN=0x45
        if byte_op in (0x41, 0x42, 0x45):
            raw_off, _ = self.ram.mem_read(pc_actual + 1, size_bytes=2, check_alignment=False)
            offset_signed = struct.unpack(">h", struct.pack(">H", raw_off & 0xFFFF))[0]
            pc_siguiente = pc_actual + 3

            condicion_cumplida = False
            if byte_op == 0x41:  # JZ: Salta si SR.Z == 1
                condicion_cumplida = (self.banco.leer_bandera("Z") == 1)
            elif byte_op == 0x42:  # JNZ: Salta si SR.Z == 0
                condicion_cumplida = (self.banco.leer_bandera("Z") == 0)
            elif byte_op == 0x45:  # JN: Salta si SR.N == 1
                condicion_cumplida = (self.banco.leer_bandera("N") == 1)

            if condicion_cumplida:
                self.banco.pc = (pc_siguiente + offset_signed) & 0xFFFFFFFF
            else:
                self.banco.pc = pc_siguiente
            return True

        # Formato 5 (5 Bytes): Salto Absoluto (Op: 1B, Addr32: 4B)
        # Opcode: JMP=0x40
        if byte_op == 0x40:
            addr32, _ = self.ram.mem_read(pc_actual + 1, size_bytes=4, check_alignment=False)
            self.banco.pc = addr32 & 0xFFFFFFFF
            return True

        raise NotImplementedError(f"Opcode 0x{byte_op:02X} no implementado en runner de prueba")

    def ejecutar_hasta_fin(self, max_instrucciones: int = 10000) -> int:
        """Ejecuta en modo continuo hasta alcanzar HLT o el limite de seguridad."""
        pasos = 0
        while not self.detenido and pasos < max_instrucciones:
            if not self.paso():
                break
            pasos += 1
        if pasos >= max_instrucciones and not self.detenido:
            raise TimeoutError(f"El programa excedio {max_instrucciones} instrucciones sin detenerse.")
        return pasos


# ===========================================================================
# 1. Pruebas de Integridad Binaria de los Algoritmos (Tarea 9)
# ===========================================================================

class TestIntegridadBinariaAlgoritmos(unittest.TestCase):
    """Verifica que las secuencias de bytes coincidan con el diseno formal."""

    def test_tamano_bytes_algoritmo1_factorial(self) -> None:
        # En Tarea 9 (Pags. 30-32): Factorial consta de 41 bytes (0x29)
        self.assertEqual(len(BYTES_FACTORIAL), 41)
        self.assertEqual(BYTES_FACTORIAL[0], 0x14)  # ADDI inicial
        self.assertEqual(BYTES_FACTORIAL[-1], 0x00)  # HLT final

    def test_tamano_bytes_algoritmo2_euclides(self) -> None:
        # En Tarea 9 (Pags. 34-36): Euclides consta de 50 bytes (0x32)
        self.assertEqual(len(BYTES_EUCLIDES), 50)
        self.assertEqual(BYTES_EUCLIDES[0], 0x14)  # ADDI inicial
        self.assertEqual(BYTES_EUCLIDES[-1], 0x00)  # HLT final

    def test_tamano_bytes_algoritmo3_fibonacci(self) -> None:
        # En Tarea 9 (Pags. 38-41): Fibonacci consta de 63 bytes (0x3F)
        self.assertEqual(len(BYTES_FIBONACCI), 63)
        self.assertEqual(BYTES_FIBONACCI[0], 0x14)  # ADDI inicial
        self.assertEqual(BYTES_FIBONACCI[-1], 0x00)  # HLT final

    def test_tamano_bytes_cargador_firmware(self) -> None:
        # En Tarea 9 (Pags. 26-27): Firmware del cargador consta de 69 bytes
        self.assertEqual(len(BYTES_CARGADOR_FIRMWARE), 69)
        self.assertEqual(BYTES_CARGADOR_FIRMWARE[0], 0x14)
        self.assertEqual(BYTES_CARGADOR_FIRMWARE[-1], 0x00)

    def test_exportacion_archivos_en_disco(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            rutas = exportar_archivos_programas(tmpdir)
            self.assertEqual(len(rutas), 10)
            for nombre in ("factorial.bin", "euclides.bin", "fibonacci.bin"):
                p = os.path.join(tmpdir, nombre)
                self.assertTrue(os.path.isfile(p))
                self.assertGreater(os.path.getsize(p), 0)


# ===========================================================================
# 2. Pruebas de Carga en Memoria RAM con CargadorEnigma
# ===========================================================================

class TestCargaAlgoritmosEnRAM(unittest.TestCase):
    """Verifica que el Cargador ubique los binarios en las direcciones correctas."""

    def setUp(self) -> None:
        self.ram = RAMMemory()
        self.banco = BancoRegistros()
        self.cargador = CargadorEnigma(ram=self.ram, banco=self.banco)

    def test_carga_bytes_factorial_posicion_correcta(self) -> None:
        res = self.cargador.cargar_bytes(
            BYTES_FACTORIAL,
            direccion_destino=PROGRAMA_FACTORIAL.direccion_base,
            configurar_cpu=True,
        )
        self.assertEqual(res["direccion_base"], 0x00200000)
        self.assertEqual(res["tamano_total"], 41)
        self.assertEqual(self.banco.pc, 0x00200000)

        # Verificar los primeros 4 bytes en RAM: 14 10 00 20
        d0 = leer_byte_directo(self.ram, 0x00200000)
        d1 = leer_byte_directo(self.ram, 0x00200001)
        d2 = leer_byte_directo(self.ram, 0x00200002)
        d3 = leer_byte_directo(self.ram, 0x00200003)
        self.assertEqual([d0, d1, d2, d3], [0x14, 0x10, 0x00, 0x20])

        # Verificar el ultimo byte (HLT = 0x00 en 0x00200028)
        self.assertEqual(leer_byte_directo(self.ram, 0x00200028), 0x00)

    def test_carga_bytes_euclides_posicion_correcta(self) -> None:
        res = self.cargador.cargar_bytes(
            BYTES_EUCLIDES,
            direccion_destino=PROGRAMA_EUCLIDES.direccion_base,
            configurar_cpu=True,
        )
        self.assertEqual(res["direccion_base"], 0x00200100)
        self.assertEqual(res["tamano_total"], 50)
        self.assertEqual(self.banco.pc, 0x00200100)
        self.assertEqual(leer_byte_directo(self.ram, 0x00200131), 0x00)

    def test_carga_bytes_fibonacci_posicion_correcta(self) -> None:
        res = self.cargador.cargar_bytes(
            BYTES_FIBONACCI,
            direccion_destino=PROGRAMA_FIBONACCI.direccion_base,
            configurar_cpu=True,
        )
        self.assertEqual(res["direccion_base"], 0x00200200)
        self.assertEqual(res["tamano_total"], 63)
        self.assertEqual(self.banco.pc, 0x00200200)
        self.assertEqual(leer_byte_directo(self.ram, 0x0020023E), 0x00)

    def test_proteccion_memoria_direccion_invalida(self) -> None:
        # Intento de cargar en zona de vectores (0x00000500) debe fallar
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(BYTES_FACTORIAL, direccion_destino=0x00000500)

        # Intento de invadir la Pila (0xC5000000) debe fallar
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(BYTES_FACTORIAL, direccion_destino=0xC5000000)


# ===========================================================================
# 3. Pruebas de Ejecucion y Validacion Matematica en Memoria RAM
# ===========================================================================

class TestValidacionResultadosAlgoritmos(unittest.TestCase):
    """
    Ejecuta cada algoritmo cargado en RAM y valida que el resultado en memoria
    coincida de manera exacta con lo especificado en la Tarea 9.
    """

    def setUp(self) -> None:
        self.ram = RAMMemory()
        self.banco = BancoRegistros()
        self.alu = ALU()
        self.cargador = CargadorEnigma(ram=self.ram, banco=self.banco)
        self.runner = RunnerInstruccionesPrueba(self.ram, self.banco, self.alu)

    def test_ejecucion_algoritmo1_factorial_5(self) -> None:
        """
        Escenario 1: Factorial de 5
        Entrada : Mem[0x00201000] = 5
        Salida  : Mem[0x00201008] = 120 (0x78)
        """
        # 1. Cargar programa e inicializar entrada
        inicializar_escenario_prueba(self.ram, self.banco, self.cargador, PROGRAMA_FACTORIAL)

        # Verificar que la entrada fue inyectada en RAM
        val_n, _ = self.ram.mem_read(0x00201000, size_bytes=8)
        self.assertEqual(val_n, 5)

        # 2. Ejecutar programa
        pasos = self.runner.ejecutar_hasta_fin()
        self.assertTrue(self.runner.detenido)
        self.assertGreater(pasos, 0)

        # 3. Validar resultado en RAM
        val_resultado, st = self.ram.mem_read(0x00201008, size_bytes=8)
        self.assertEqual(st, STATUS_READY)
        self.assertEqual(
            val_resultado,
            120,
            f"Esperado factorial 5! = 120, obtenido: {val_resultado}",
        )

    def test_ejecucion_algoritmo1_factorial_cero(self) -> None:
        """
        Escenario 1b: Factorial de 0 (Caso borde)
        Entrada : Mem[0x00201000] = 0
        Salida  : Mem[0x00201008] = 1
        """
        inicializar_escenario_prueba(self.ram, self.banco, self.cargador, PROGRAMA_FACTORIAL)
        # Sobreescribir entrada N = 0
        self.ram.mem_write(0x00201000, 0, size_bytes=8)

        self.runner.ejecutar_hasta_fin()
        self.assertTrue(self.runner.detenido)

        val_resultado, _ = self.ram.mem_read(0x00201008, size_bytes=8)
        self.assertEqual(val_resultado, 1, "0! debe ser igual a 1")

    def test_ejecucion_algoritmo2_euclides_mcd_48_18(self) -> None:
        """
        Escenario 2: Maximo Comun Divisor de 48 y 18
        Entradas: Mem[0x00202000] = 48, Mem[0x00202008] = 18
        Salida  : Mem[0x00202010] = 6 (MCD)
        """
        inicializar_escenario_prueba(self.ram, self.banco, self.cargador, PROGRAMA_EUCLIDES)

        # Verificar entradas
        a, _ = self.ram.mem_read(0x00202000, size_bytes=8)
        b, _ = self.ram.mem_read(0x00202008, size_bytes=8)
        self.assertEqual(a, 48)
        self.assertEqual(b, 18)

        pasos = self.runner.ejecutar_hasta_fin()
        self.assertTrue(self.runner.detenido)
        self.assertGreater(pasos, 0)

        # Validar salida esperada
        mcd, st = self.ram.mem_read(0x00202010, size_bytes=8)
        self.assertEqual(st, STATUS_READY)
        self.assertEqual(mcd, 6, f"Esperado MCD(48, 18) = 6, obtenido: {mcd}")

    def test_ejecucion_algoritmo2_euclides_mcd_caso_arbitrario(self) -> None:
        """
        Escenario 2b: MCD(35, 14) = 7
        """
        inicializar_escenario_prueba(self.ram, self.banco, self.cargador, PROGRAMA_EUCLIDES)
        self.ram.mem_write(0x00202000, 35, size_bytes=8)
        self.ram.mem_write(0x00202008, 14, size_bytes=8)

        self.runner.ejecutar_hasta_fin()
        mcd, _ = self.ram.mem_read(0x00202010, size_bytes=8)
        self.assertEqual(mcd, 7, f"Esperado MCD(35, 14) = 7, obtenido: {mcd}")

    def test_ejecucion_algoritmo3_fibonacci_7_terminos(self) -> None:
        """
        Escenario 3: Generacion de 7 terminos de Fibonacci en memoria RAM
        Secuencia esperada: [0, 1, 1, 2, 3, 5, 8]
        Direccion base del arreglo: 0x00203000
        """
        inicializar_escenario_prueba(self.ram, self.banco, self.cargador, PROGRAMA_FIBONACCI)

        pasos = self.runner.ejecutar_hasta_fin()
        self.assertTrue(self.runner.detenido)
        self.assertGreater(pasos, 0)

        # Verificar los 7 terminos consecutivos en RAM (palabras de 64 bits = 8 bytes c/u)
        terminos_obtenidos = []
        for i in range(7):
            dir_termino = 0x00203000 + (i * 8)
            val, st = self.ram.mem_read(dir_termino, size_bytes=8)
            self.assertEqual(st, STATUS_READY)
            terminos_obtenidos.append(val)

        esperados = [0, 1, 1, 2, 3, 5, 8]
        self.assertEqual(
            terminos_obtenidos,
            esperados,
            f"Esperado Fibonacci {esperados}, obtenido: {terminos_obtenidos}",
        )

    def test_ejecucion_paso_a_paso_factorial(self) -> None:
        """Verifica que el modo paso a paso avance la instruccion y modifique el PC."""
        inicializar_escenario_prueba(self.ram, self.banco, self.cargador, PROGRAMA_FACTORIAL)

        pc_inicial = self.banco.pc
        self.assertEqual(pc_inicial, 0x00200000)

        # Paso 1: ADDI R1, R0, 0x0020 (4 bytes)
        continuar = self.runner.paso()
        self.assertTrue(continuar)
        self.assertEqual(self.banco.pc, 0x00200004)
        self.assertEqual(self.banco.leer_nombre("R1"), 0x0020)

        # Paso 2: SHL R1, R1, 16 (4 bytes)
        continuar = self.runner.paso()
        self.assertTrue(continuar)
        self.assertEqual(self.banco.pc, 0x00200008)
        self.assertEqual(self.banco.leer_nombre("R1"), 0x00200000)


# ===========================================================================
# 4. Gancho para la futura CPU oficial del Integrante 3
# ===========================================================================

class TestIntegracionCPUOficial(unittest.TestCase):
    """
    Verifica la ejecucion sobre la clase CPU oficial cuando el Integrante 3
    la integre en enigma64.cpu.
    """

    def test_ejecucion_con_cpu_oficial(self) -> None:
        try:
            from enigma64.cpu import CPU  # type: ignore
        except ImportError:
            raise unittest.SkipTest(
                "Modulo CPU oficial (Integrante 3) aun no disponible en repositorio. "
                "La suite se valido exitosamente con el runner de pruebas."
            )

        ram = RAMMemory()
        banco = BancoRegistros()
        cargador = CargadorEnigma(ram=ram, banco=banco)
        cpu = CPU(ram=ram, banco=banco)

        inicializar_escenario_prueba(ram, banco, cargador, PROGRAMA_FACTORIAL)
        cpu.ejecutar()
        val, _ = ram.mem_read(0x00201008, size_bytes=8)
        self.assertEqual(val, 120)


if __name__ == "__main__":
    unittest.main()
