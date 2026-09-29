"""
Suite de Pruebas Unitarias del Cargador y Manipulador de Bits - Enigma-64.

Verifica:
  1. Manipulacion atomica de bits y bytes en la RAM (Punto 2 de Tarea 10).
  2. Validacion estricta de fronteras de memoria (area de usuario, proteccion
     de vectores/ROM y prevencion de colisiones con la Pila).
  3. Formatos de ejecutable: binario crudo (.bin), estructurado (.e64) y texto (hex/bin).
  4. Sincronizacion del contexto de hardware (PC, SP, SR, R0, R5).
  5. Emulacion de la subrutina de firmware de carga en 0x00001000 (Tarea 9).

Autor: Integrante 4 - Cargador & Manipulador de Bits
"""

import os
import struct
import tempfile
import unittest

from enigma64 import (
    MAGIC_ENIGMA,
    SP_RESET,
    SR_RESET,
    STACK_START,
    USER_MEM_START,
    BancoRegistros,
    BinarioEnigma,
    CargadorEnigma,
    DireccionInvalida,
    ErrorCargador,
    FormatoInvalido,
    RAMMemory,
    ViolacionProteccionMemoria,
    byte_a_cadena_bits,
    conmutar_bit,
    emular_subrutina_cargador,
    escribir_bit,
    escribir_byte_directo,
    leer_bit,
    leer_byte_directo,
    parsear_texto_a_bytes,
)


class TestManipulacionBits(unittest.TestCase):
    """Pruebas de la API de manipulacion directa de bits y bytes en RAM."""

    def setUp(self) -> None:
        self.ram = RAMMemory()
        self.addr = 0x00200000  # Primera direccion valida del area de usuario

    def test_leer_bit_posiciones(self) -> None:
        # Escribir 0b10100101 = 165 (0xA5)
        # Bits: b7=1, b6=0, b5=1, b4=0, b3=0, b2=1, b1=0, b0=1
        escribir_byte_directo(self.ram, self.addr, 0b10100101)

        esperados = [1, 0, 1, 0, 0, 1, 0, 1]  # bit 0 a bit 7
        for bit_idx, exp in enumerate(esperados):
            self.assertEqual(
                leer_bit(self.ram, self.addr, bit_idx),
                exp,
                f"Fallo en bit_idx={bit_idx}",
            )

    def test_escribir_bit_aislado(self) -> None:
        # Inicialmente el byte esta en 0
        self.assertEqual(leer_byte_directo(self.ram, self.addr), 0)

        # Encender el bit 3 (2^3 = 8)
        escribir_bit(self.ram, self.addr, bit_index=3, valor=1)
        self.assertEqual(leer_byte_directo(self.ram, self.addr), 0b00001000)
        self.assertEqual(leer_bit(self.ram, self.addr, 3), 1)

        # Encender el bit 7 (2^7 = 128) sin tocar bit 3
        escribir_bit(self.ram, self.addr, bit_index=7, valor=1)
        self.assertEqual(leer_byte_directo(self.ram, self.addr), 0b10001000)
        self.assertEqual(leer_bit(self.ram, self.addr, 3), 1)
        self.assertEqual(leer_bit(self.ram, self.addr, 7), 1)

        # Apagar el bit 3
        escribir_bit(self.ram, self.addr, bit_index=3, valor=0)
        self.assertEqual(leer_byte_directo(self.ram, self.addr), 0b10000000)
        self.assertEqual(leer_bit(self.ram, self.addr, 3), 0)
        self.assertEqual(leer_bit(self.ram, self.addr, 7), 1)

    def test_no_altera_bytes_adyacentes(self) -> None:
        # Colocar valores centinela en bytes contiguos
        escribir_byte_directo(self.ram, self.addr - 1, 0xAA)
        escribir_byte_directo(self.ram, self.addr, 0x00)
        escribir_byte_directo(self.ram, self.addr + 1, 0x55)

        # Modificar un bit en el byte central
        escribir_bit(self.ram, self.addr, bit_index=4, valor=1)

        # Verificar que los bytes contiguos siguen intactos
        self.assertEqual(leer_byte_directo(self.ram, self.addr - 1), 0xAA)
        self.assertEqual(leer_byte_directo(self.ram, self.addr + 1), 0x55)
        self.assertEqual(leer_byte_directo(self.ram, self.addr), 0x10)

    def test_conmutar_bit(self) -> None:
        escribir_byte_directo(self.ram, self.addr, 0b00000000)

        # 0 -> 1
        nuevo = conmutar_bit(self.ram, self.addr, bit_index=5)
        self.assertEqual(nuevo, 1)
        self.assertEqual(leer_byte_directo(self.ram, self.addr), 0b00100000)

        # 1 -> 0
        nuevo2 = conmutar_bit(self.ram, self.addr, bit_index=5)
        self.assertEqual(nuevo2, 0)
        self.assertEqual(leer_byte_directo(self.ram, self.addr), 0b00000000)

    def test_byte_a_cadena_bits(self) -> None:
        escribir_byte_directo(self.ram, self.addr, 0b11001010)
        cadena = byte_a_cadena_bits(self.ram, self.addr)
        self.assertEqual(cadena, "11001010")

        escribir_byte_directo(self.ram, self.addr, 0x00)
        self.assertEqual(byte_a_cadena_bits(self.ram, self.addr), "00000000")

        escribir_byte_directo(self.ram, self.addr, 0xFF)
        self.assertEqual(byte_a_cadena_bits(self.ram, self.addr), "11111111")

    def test_argumentos_invalidos(self) -> None:
        with self.assertRaises(ValueError):
            leer_bit(self.ram, self.addr, -1)
        with self.assertRaises(ValueError):
            leer_bit(self.ram, self.addr, 8)
        with self.assertRaises(ValueError):
            escribir_bit(self.ram, self.addr, 0, valor=2)
        with self.assertRaises(ValueError):
            conmutar_bit(self.ram, self.addr, 10)


class TestValidacionLimitesYMemoria(unittest.TestCase):
    """Pruebas de las reglas y fronteras de memoria arquitectonicas."""

    def setUp(self) -> None:
        self.ram = RAMMemory()
        self.banco = BancoRegistros()
        self.cargador = CargadorEnigma(ram=self.ram, banco=self.banco)

    def test_carga_en_area_usuario_permitida(self) -> None:
        # Carga en el borde inferior permitido: 0x00200000
        res = self.cargador.cargar_bytes(b"\x01\x02\x03\x04", direccion_destino=0x00200000)
        self.assertEqual(res["direccion_base"], 0x00200000)
        self.assertEqual(res["tamano_total"], 4)

        # Carga dentro del area de usuario
        res2 = self.cargador.cargar_bytes(b"\xAA\xBB", direccion_destino=0x00500000)
        self.assertEqual(res2["direccion_base"], 0x00500000)

    def test_rechazo_vectores_y_sistema(self) -> None:
        # Carga en vector 0x00000000
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(b"\x00", direccion_destino=0x00000000)

        # Carga en tabla de interrupciones 0x00000500
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(b"\x00", direccion_destino=0x00000500)

        # Carga en firmware de monitor 0x00001000
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(b"\x00", direccion_destino=0x00001000)

        # Carga en area de trabajo del cargador 0x00100000
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(b"\x00", direccion_destino=0x00100000)

        # Justo antes del area de usuario (0x001FFFFF)
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(b"\x00", direccion_destino=0x001FFFFF)

    def test_rechazo_colision_con_pila(self) -> None:
        # STACK_START = 0xC0000000
        # Cargar exactamente en 0xC0000000 debe fallar
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(b"\x00", direccion_destino=STACK_START)

        # Carga que inicia antes pero cuyo final invade la pila
        with self.assertRaises(ViolacionProteccionMemoria):
            self.cargador.cargar_bytes(b"\x00\x00", direccion_destino=STACK_START - 1)

    def test_rechazo_direcciones_fuera_de_4gib_o_negativas(self) -> None:
        # Direccion mayor a 4 GiB
        with self.assertRaises(DireccionInvalida):
            self.cargador.cargar_bytes(b"\x00", direccion_destino=0x100000000)

        # Direccion negativa
        with self.assertRaises(DireccionInvalida):
            self.cargador.cargar_bytes(b"\x00", direccion_destino=-1)

    def test_tamano_vacio_falla(self) -> None:
        with self.assertRaises(ErrorCargador):
            self.cargador.validar_limites(USER_MEM_START, 0)


class TestCargaFormatos(unittest.TestCase):
    """Pruebas de compatibilidad con binarios planos, estructurados y texto."""

    def setUp(self) -> None:
        self.ram = RAMMemory()
        self.banco = BancoRegistros()
        self.cargador = CargadorEnigma(ram=self.ram, banco=self.banco)

    def test_cargar_bytes_crudos_plano(self) -> None:
        opcodes = bytes([0x10, 0x20, 0x30, 0x40, 0x50, 0x00])  # Simula instrucciones
        meta = self.cargador.cargar_bytes(opcodes, direccion_destino=0x00200000)

        self.assertEqual(meta["tamano_total"], 6)
        # Comprobar que en la RAM estan exactamente los bytes
        for i, byte_esperado in enumerate(opcodes):
            self.assertEqual(
                leer_byte_directo(self.ram, 0x00200000 + i), byte_esperado
            )

    def test_serializacion_deserializacion_e64(self) -> None:
        codigo = bytes([0x01, 0x02, 0x03, 0x04])
        datos = bytes([0xAA, 0xBB])
        tabla_reloc = [0x00000002]
        tabla_simb = {"main": 0x00200000, "data_var": 0x00200004}

        binario_orig = BinarioEnigma(
            codigo=codigo,
            datos=datos,
            direccion_base=0x00200000,
            entry_point=0x00200000,
            reubicable=True,
            tabla_reubicacion=tabla_reloc,
            tabla_simbolos=tabla_simb,
        )

        serializado = binario_orig.serializar_e64()
        self.assertTrue(serializado.startswith(MAGIC_ENIGMA))

        # Deserializar y comprobar fidelidad
        binario_rec = BinarioEnigma.deserializar_e64(serializado)
        self.assertEqual(binario_rec.codigo, codigo)
        self.assertEqual(binario_rec.datos, datos)
        self.assertEqual(binario_rec.direccion_base, 0x00200000)
        self.assertEqual(binario_rec.entry_point, 0x00200000)
        self.assertTrue(binario_rec.reubicable)
        self.assertEqual(binario_rec.tabla_reubicacion, tabla_reloc)
        self.assertEqual(binario_rec.tabla_simbolos, tabla_simb)

    def test_cargar_binario_e64_en_ram(self) -> None:
        codigo = bytes([0xDE, 0xAD, 0xBE, 0xEF])
        binario = BinarioEnigma(codigo=codigo, direccion_base=0x00201000)
        meta = self.cargador.cargar_binario(binario)

        self.assertEqual(meta["direccion_base"], 0x00201000)
        self.assertEqual(leer_byte_directo(self.ram, 0x00201000), 0xDE)
        self.assertEqual(leer_byte_directo(self.ram, 0x00201001), 0xAD)
        self.assertEqual(leer_byte_directo(self.ram, 0x00201002), 0xBE)
        self.assertEqual(leer_byte_directo(self.ram, 0x00201003), 0xEF)

    def test_reubicacion_dinamica_binario(self) -> None:
        # Crear un binario reubicable que tiene una direccion de 64 bits en el offset 0
        # Direccion original: 0x00200010. Si se carga en 0x00300000 (delta +0x00100000),
        # debe quedar parchada a 0x00300010.
        dir_original = 0x00200010
        codigo = bytearray(struct.pack(">Q", dir_original))
        binario = BinarioEnigma(
            codigo=codigo,
            direccion_base=0x00200000,
            entry_point=0x00200000,
            reubicable=True,
            tabla_reubicacion=[0],  # El offset 0 requiere relocalizacion
        )

        # Cargar desplazado a 0x00300000
        self.cargador.cargar_binario(binario, direccion_destino=0x00300000)

        # Leer la palabra de 64 bits reubicada desde la RAM
        val_reubicado, _ = self.ram.mem_read(0x00300000, size_bytes=8)
        self.assertEqual(val_reubicado, 0x00300010)

    def test_parsear_y_cargar_texto(self) -> None:
        texto = """
        # Programa de prueba en texto
        0x12, 0x34   // dos primeros bytes
        0b00001111   ; byte binario (15)
        AA BB        # tokens hex sin prefijo
        255          # byte decimal
        """
        parsed = parsear_texto_a_bytes(texto)
        self.assertEqual(
            bytes(parsed), bytes([0x12, 0x34, 0x0F, 0xAA, 0xBB, 0xFF])
        )

        # Cargar texto en RAM
        meta = self.cargador.cargar_texto(texto, direccion_destino=0x00205000)
        self.assertEqual(meta["tamano_total"], 6)
        self.assertEqual(leer_byte_directo(self.ram, 0x00205000), 0x12)
        self.assertEqual(leer_byte_directo(self.ram, 0x00205002), 0x0F)
        self.assertEqual(leer_byte_directo(self.ram, 0x00205005), 0xFF)

    def test_cargar_desde_archivos_en_disco(self) -> None:
        # 1. Probar archivo .bin
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f_bin:
            f_bin.write(b"\x01\x02\x03\x04")
            ruta_bin = f_bin.name

        try:
            res_bin = self.cargador.cargar_archivo(ruta_bin, direccion_destino=0x00208000)
            self.assertEqual(res_bin["tamano_total"], 4)
            self.assertEqual(leer_byte_directo(self.ram, 0x00208000), 0x01)
        finally:
            os.remove(ruta_bin)

        # 2. Probar archivo .e64 estructurado
        bin_e64 = BinarioEnigma(codigo=b"\xCA\xFE", direccion_base=0x00209000)
        with tempfile.NamedTemporaryFile(suffix=".e64", delete=False) as f_e64:
            f_e64.write(bin_e64.serializar_e64())
            ruta_e64 = f_e64.name

        try:
            res_e64 = self.cargador.cargar_archivo(ruta_e64)
            self.assertEqual(res_e64["direccion_base"], 0x00209000)
            self.assertEqual(leer_byte_directo(self.ram, 0x00209000), 0xCA)
            self.assertEqual(leer_byte_directo(self.ram, 0x00209001), 0xFE)
        finally:
            os.remove(ruta_e64)


class TestContextoHardware(unittest.TestCase):
    """Pruebas de la inicializacion del entorno de ejecucion tras la carga."""

    def setUp(self) -> None:
        self.ram = RAMMemory()
        self.banco = BancoRegistros()
        self.cargador = CargadorEnigma(ram=self.ram, banco=self.banco)

    def test_sincronizacion_registros(self) -> None:
        entry_point = 0x00200100
        self.cargador.cargar_bytes(
            b"\x00\x00\x00\x00",
            direccion_destino=0x00200100,
            entry_point=entry_point,
        )

        # Comprobar estado de registros segun diseno Enigma-64
        self.assertEqual(self.banco.pc, entry_point)
        self.assertEqual(self.banco.sp, SP_RESET)  # 0x00000000EFFFFFFF
        self.assertEqual(self.banco.sr, SR_RESET)
        self.assertEqual(self.banco.leer_nombre("R0"), 0)
        self.assertEqual(self.banco.leer_nombre("R5"), entry_point)

    def test_detencion_y_reanudacion_cpu(self) -> None:
        class FakeCPU:
            def __init__(self, banco):
                self.banco = banco
                self.detenido = False

        cpu = FakeCPU(self.banco)
        cargador_cpu = CargadorEnigma(ram=self.ram, cpu=cpu)
        cargador_cpu.cargar_bytes(b"\x12\x34", direccion_destino=0x00200000)

        # La CPU debe reanudarse al finalizar la carga
        self.assertFalse(cpu.detenido)
        self.assertEqual(cpu.banco.pc, 0x00200000)


class TestSubrutinaFirmware(unittest.TestCase):
    """Pruebas de la emulacion de la subrutina de firmware en 0x00001000 (Tarea 9)."""

    def setUp(self) -> None:
        self.ram = RAMMemory()
        self.banco = BancoRegistros()

    def test_emulacion_firmware_transferencia(self) -> None:
        # Preparar un buffer de origen (ej. buffer DMA de disco en 0x00300000)
        src_addr = 0x00300000
        dst_addr = 0x00200000
        tamano = 8

        datos_prueba = bytes([10, 20, 30, 40, 50, 60, 70, 80])
        for i, val in enumerate(datos_prueba):
            escribir_byte_directo(self.ram, src_addr + i, val)

        # Cargar los registros segun el protocolo arquitectonico de la Tarea 9:
        # R1 = origen, R2 = destino, R3 = tamano
        self.banco.escribir_nombre("R1", src_addr)
        self.banco.escribir_nombre("R2", dst_addr)
        self.banco.escribir_nombre("R3", tamano)

        # Ejecutar emulacion de subrutina firmware
        entry_point = emular_subrutina_cargador(self.ram, self.banco)

        # 1. Comprobar que los datos fueron copiados a dst_addr
        for i, val_esperado in enumerate(datos_prueba):
            self.assertEqual(
                leer_byte_directo(self.ram, dst_addr + i), val_esperado
            )

        # 2. Comprobar que R5 contiene la direccion de entrada para el salto JMPR R5
        self.assertEqual(entry_point, dst_addr)
        self.assertEqual(self.banco.leer_nombre("R5"), dst_addr)

    def test_firmware_rechaza_destino_fuera_de_usuario(self) -> None:
        # Si R2 apunta a vectores (< 0x00200000) o a pila (>= 0xC0000000), debe fallar
        self.banco.escribir_nombre("R1", 0x00300000)
        self.banco.escribir_nombre("R2", 0x00000500)  # Destino invalido
        self.banco.escribir_nombre("R3", 16)

        with self.assertRaises(ViolacionProteccionMemoria):
            emular_subrutina_cargador(self.ram, self.banco)


if __name__ == "__main__":
    unittest.main()
