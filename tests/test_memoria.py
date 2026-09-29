"""
Suite de pruebas unitarias para el módulo de Memoria RAM y Buses - Enigma-64.

Verifica:
  * Paginación por software bajo demanda (Sparse Memory, 4 GiB de espacio lógico).
  * Formato de ordenamiento de bytes Big-Endian para transferencias de 1, 2, 4 y 8 bytes.
  * Acceso continuo a memoria cruzando límites físicos de páginas.
  * Control estricto de alineación natural de direcciones (MISALIGNED).
  * Detección y enrutamiento de direcciones MMIO (A[31:24] == 0xFF -> MMIO).
  * Decodificación de direcciones físicas rechazando valores > 4 GiB (A[63:32] != 0 -> ADDR_FAULT).
  * Manejo de excepciones para anchos de acceso inválidos y parámetros de configuración.

Ejecutar:  python -m unittest tests/test_memoria.py -v
       o:  python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest

from enigma64 import (
    PAGE_SIZE,
    STATUS_ADDR_FAULT,
    STATUS_MISALIGNED,
    STATUS_MMIO,
    STATUS_READY,
    InvalidAccessSizeError,
    RAMMemory,
)


class TestRAMPaging(unittest.TestCase):
    """Pruebas de la paginacion por software bajo demanda (Sparse Memory)."""

    def setUp(self) -> None:
        self.ram = RAMMemory(page_size=4096)

    def test_unallocated_block_read_returns_zeros_without_allocating_page(self) -> None:
        # Lectura de 8 bytes en una pagina nueva
        val, status = self.ram.mem_read(0x00040000, size_bytes=8)
        self.assertEqual(status, STATUS_READY)
        self.assertEqual(val, 0)
        self.assertEqual(len(self.ram.pages), 0, "No debe instanciar paginas en lecturas de ceros")
        self.assertNotIn(0x00040000 // PAGE_SIZE, self.ram.pages)

    def test_write_allocates_page_on_demand(self) -> None:
        addr = 0x00020000
        page_idx = addr // PAGE_SIZE

        self.assertNotIn(page_idx, self.ram.pages)
        _, status = self.ram.mem_write(addr, 0x11223344, size_bytes=4)
        self.assertEqual(status, STATUS_READY)

        self.assertIn(page_idx, self.ram.pages)
        self.assertEqual(len(self.ram.pages), 1)

        val, read_status = self.ram.mem_read(addr, size_bytes=4)
        self.assertEqual(read_status, STATUS_READY)
        self.assertEqual(val, 0x11223344)

    def test_multiple_writes_same_page_do_not_duplicate_blocks(self) -> None:
        self.ram.mem_write(0x00001000, 0xAA, size_bytes=1)
        self.ram.mem_write(0x00001004, 0xBB, size_bytes=1)
        self.ram.mem_write(0x00001008, 0xCC, size_bytes=1)
        self.assertEqual(len(self.ram.pages), 1)
        self.assertEqual(self.ram.allocated_blocks, [1])

    def test_reset_clears_all_pages(self) -> None:
        self.ram.mem_write(0x00001000, 0x1234, size_bytes=2)
        self.ram.mem_write(0x00005000, 0x5678, size_bytes=2)
        self.assertEqual(len(self.ram.pages), 2)

        self.ram.reset()
        self.assertEqual(len(self.ram.pages), 0)
        self.assertEqual(self.ram.allocated_bytes, 0)

        # Tras el reset, una lectura vuelve a entregar ceros limpios
        val, status = self.ram.mem_read(0x00001000, size_bytes=2)
        self.assertEqual(status, STATUS_READY)
        self.assertEqual(val, 0)


class TestBigEndianAndBlockCrossing(unittest.TestCase):
    """Pruebas del formato Big-Endian y el cruce continuo entre limites de paginas."""

    def setUp(self) -> None:
        self.ram = RAMMemory(page_size=4096)

    def test_single_byte_access(self) -> None:
        addr = 0x00000100
        _, status_w = self.ram.mem_write(addr, 0xAB, size_bytes=1)
        self.assertEqual(status_w, STATUS_READY)

        val, status_r = self.ram.mem_read(addr, size_bytes=1)
        self.assertEqual(status_r, STATUS_READY)
        self.assertEqual(val, 0xAB)

    def test_two_byte_access_big_endian(self) -> None:
        addr = 0x00000200
        # En Big-Endian: byte mas significativo primero en memoria
        self.ram.mem_write(addr, 0x1234, size_bytes=2)
        val, status = self.ram.mem_read(addr, size_bytes=2)
        self.assertEqual(status, STATUS_READY)
        self.assertEqual(val, 0x1234)

        # Verificacion directa de bytes fisicos en la pagina
        page_idx = addr // PAGE_SIZE
        offset = addr % PAGE_SIZE
        self.assertEqual(self.ram.pages[page_idx][offset], 0x12)
        self.assertEqual(self.ram.pages[page_idx][offset + 1], 0x34)

    def test_four_byte_access_big_endian(self) -> None:
        addr = 0x00000400
        test_val = 0xA1B2C3D4
        self.ram.mem_write(addr, test_val, size_bytes=4)
        val, status = self.ram.mem_read(addr, size_bytes=4)
        self.assertEqual(status, STATUS_READY)
        self.assertEqual(val, test_val)

        page_idx = addr // PAGE_SIZE
        offset = addr % PAGE_SIZE
        self.assertEqual(
            list(self.ram.pages[page_idx][offset : offset + 4]),
            [0xA1, 0xB2, 0xC3, 0xD4],
        )

    def test_eight_byte_access_big_endian(self) -> None:
        addr = 0x00000800
        test_val = 0x0123456789ABCDEF
        self.ram.mem_write(addr, test_val, size_bytes=8)
        val, status = self.ram.mem_read(addr, size_bytes=8)
        self.assertEqual(status, STATUS_READY)
        self.assertEqual(val, test_val)

        page_idx = addr // PAGE_SIZE
        offset = addr % PAGE_SIZE
        self.assertEqual(
            list(self.ram.pages[page_idx][offset : offset + 8]),
            [0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF],
        )

    def test_write_and_read_crossing_page_boundary(self) -> None:
        # Pagina 0: 0x0000 - 0x0FFF (0 - 4095)
        # Pagina 1: 0x1000 - 0x1FFF (4096 - 8191)
        # Direccion 0x0FFE: escribimos 4 bytes (2 en pag 0 y 2 en pag 1)
        cross_addr = 0x00000FFE
        cross_val = 0xDEADBEEF

        _, write_status = self.ram.mem_write(cross_addr, cross_val, size_bytes=4, check_alignment=False)
        self.assertEqual(write_status, STATUS_READY)

        read_val, read_status = self.ram.mem_read(cross_addr, size_bytes=4, check_alignment=False)
        self.assertEqual(read_status, STATUS_READY)
        self.assertEqual(read_val, cross_val)

        # Confirmar que ambas paginas fueron instanciadas y tienen los fragmentos esperados
        self.assertIn(0, self.ram.pages)
        self.assertIn(1, self.ram.pages)
        self.assertEqual(self.ram.pages[0][4094:4096], bytearray([0xDE, 0xAD]))
        self.assertEqual(self.ram.pages[1][0:2], bytearray([0xBE, 0xEF]))

    def test_eight_byte_crossing_page_boundary(self) -> None:
        # Escribimos 8 bytes en 0x0FFC (4 bytes en pag 0 y 4 bytes en pag 1)
        cross_addr = 0x00000FFC
        cross_val = 0x0102030405060708

        _, write_status = self.ram.mem_write(cross_addr, cross_val, size_bytes=8, check_alignment=False)
        self.assertEqual(write_status, STATUS_READY)

        read_val, read_status = self.ram.mem_read(cross_addr, size_bytes=8, check_alignment=False)
        self.assertEqual(read_status, STATUS_READY)
        self.assertEqual(read_val, cross_val)

        self.assertEqual(self.ram.pages[0][4092:4096], bytearray([0x01, 0x02, 0x03, 0x04]))
        self.assertEqual(self.ram.pages[1][0:4], bytearray([0x05, 0x06, 0x07, 0x08]))


class TestAlignmentControl(unittest.TestCase):
    """Pruebas del control de alineacion natural en el bus de datos."""

    def setUp(self) -> None:
        self.ram = RAMMemory()

    def test_misaligned_two_byte_access(self) -> None:
        for addr in (0x00000001, 0x00000003, 0x00000007):
            data_out, status = self.ram.mem_write(addr, 0x1234, size_bytes=2)
            self.assertEqual(status, STATUS_MISALIGNED)
            self.assertIsNone(data_out)

            data_out, status = self.ram.mem_read(addr, size_bytes=2)
            self.assertEqual(status, STATUS_MISALIGNED)
            self.assertIsNone(data_out)

    def test_misaligned_four_byte_access(self) -> None:
        for addr in (0x00000001, 0x00000002, 0x00000003, 0x00000006):
            data_out, status = self.ram.mem_write(addr, 0x12345678, size_bytes=4)
            self.assertEqual(status, STATUS_MISALIGNED)
            self.assertIsNone(data_out)

            data_out, status = self.ram.mem_read(addr, size_bytes=4)
            self.assertEqual(status, STATUS_MISALIGNED)
            self.assertIsNone(data_out)

    def test_misaligned_eight_byte_access(self) -> None:
        for addr in (0x00000002, 0x00000004, 0x00000006, 0x0000000C):
            data_out, status = self.ram.mem_write(addr, 0x123456789ABCDEF0, size_bytes=8)
            self.assertEqual(status, STATUS_MISALIGNED)
            self.assertIsNone(data_out)

            data_out, status = self.ram.mem_read(addr, size_bytes=8)
            self.assertEqual(status, STATUS_MISALIGNED)
            self.assertIsNone(data_out)

    def test_aligned_accesses_succeed(self) -> None:
        _, s1 = self.ram.mem_write(0x00000003, 0xFF, size_bytes=1)
        self.assertEqual(s1, STATUS_READY)

        _, s2 = self.ram.mem_write(0x00000006, 0xFFFF, size_bytes=2)
        self.assertEqual(s2, STATUS_READY)

        _, s4 = self.ram.mem_write(0x0000000C, 0xFFFFFFFF, size_bytes=4)
        self.assertEqual(s4, STATUS_READY)

        _, s8 = self.ram.mem_write(0x00000018, 0xFFFFFFFFFFFFFFFF, size_bytes=8)
        self.assertEqual(s8, STATUS_READY)

    def test_disabling_alignment_check_allows_misaligned_access(self) -> None:
        _, status_w = self.ram.mem_write(0x00000001, 0xCAFEBABE, size_bytes=4, check_alignment=False)
        self.assertEqual(status_w, STATUS_READY)

        val, status_r = self.ram.mem_read(0x00000001, size_bytes=4, check_alignment=False)
        self.assertEqual(status_r, STATUS_READY)
        self.assertEqual(val, 0xCAFEBABE)


class TestMMIORouting(unittest.TestCase):
    """Pruebas del enrutamiento a espacio MMIO (A[31:24] == 0xFF)."""

    def setUp(self) -> None:
        self.ram = RAMMemory()

    def test_mmio_detection_on_read_and_write(self) -> None:
        mmio_addresses = [
            0x00000000FF000000,
            0x00000000FF000010,
            0x00000000FF000080,
            0x00000000FFFFFFFF,
        ]
        for addr in mmio_addresses:
            data_r, status_r = self.ram.mem_read(addr, size_bytes=4, check_alignment=False)
            self.assertEqual(status_r, STATUS_MMIO, f"Fallo al detectar MMIO en {hex(addr)}")
            self.assertIsNone(data_r)

            data_w, status_w = self.ram.mem_write(addr, 0x1234, size_bytes=2, check_alignment=False)
            self.assertEqual(status_w, STATUS_MMIO, f"Fallo al detectar MMIO en {hex(addr)}")
            self.assertIsNone(data_w)

        self.assertEqual(len(self.ram.pages), 0, "No debe tocar la RAM para accesos MMIO")

    def test_address_immediately_before_mmio_accesses_ram(self) -> None:
        addr_ram = 0xFEFFFFF8  # Ultima posicion alineada antes de 0xFF000000
        _, status_w = self.ram.mem_write(addr_ram, 0x1122334455667788, size_bytes=8)
        self.assertEqual(status_w, STATUS_READY)

        val, status_r = self.ram.mem_read(addr_ram, size_bytes=8)
        self.assertEqual(status_r, STATUS_READY)
        self.assertEqual(val, 0x1122334455667788)

    def test_transfer_invading_mmio_returns_mmio(self) -> None:
        # Direccion 0xFEFFFFFE con tamano 4 bytes invade hacia 0xFF000000
        invading_addr = 0xFEFFFFFE
        _, status_w = self.ram.mem_write(invading_addr, 0x12345678, size_bytes=4, check_alignment=False)
        self.assertEqual(status_w, STATUS_MMIO)

        data, status_r = self.ram.mem_read(invading_addr, size_bytes=4, check_alignment=False)
        self.assertEqual(status_r, STATUS_MMIO)
        self.assertIsNone(data)


class Test64BitAddressValidation(unittest.TestCase):
    """Pruebas de validacion de direcciones logicas superiores a 4 GiB (A[63:32] != 0)."""

    def setUp(self) -> None:
        self.ram = RAMMemory()

    def test_addresses_above_4_gib_return_address_fault(self) -> None:
        invalid_addresses = [
            0x0000000100000000,
            0x0000000200000000,
            0x000000008000000000000000,
            0x8000000000000000,
            0xFFFFFFFFFFFFFFFF,
        ]
        for addr in invalid_addresses:
            data_r, status_r = self.ram.mem_read(addr, size_bytes=8)
            self.assertEqual(status_r, STATUS_ADDR_FAULT, f"Fallo al rechazar {hex(addr)}")
            self.assertIsNone(data_r)

            data_w, status_w = self.ram.mem_write(addr, 0x1234, size_bytes=4)
            self.assertEqual(status_w, STATUS_ADDR_FAULT, f"Fallo al rechazar {hex(addr)}")
            self.assertIsNone(data_w)

        self.assertEqual(len(self.ram.pages), 0)

    def test_negative_addresses_return_address_fault(self) -> None:
        data_r, status_r = self.ram.mem_read(-1, size_bytes=4)
        self.assertEqual(status_r, STATUS_ADDR_FAULT)
        self.assertIsNone(data_r)

        data_w, status_w = self.ram.mem_write(-8, 0x12, size_bytes=1)
        self.assertEqual(status_w, STATUS_ADDR_FAULT)
        self.assertIsNone(data_w)


class TestExceptionsAndConfiguration(unittest.TestCase):
    """Pruebas de excepciones por parametros de configuracion o accesos anomalos."""

    def setUp(self) -> None:
        self.ram = RAMMemory()

    def test_unsupported_access_sizes_raise_exception(self) -> None:
        invalid_sizes = [0, 3, 5, 6, 7, 16, -1]
        for size in invalid_sizes:
            with self.assertRaises(InvalidAccessSizeError):
                self.ram.mem_read(0x00001000, size_bytes=size)

            with self.assertRaises(InvalidAccessSizeError):
                self.ram.mem_write(0x00001000, 0x12, size_bytes=size)

    def test_invalid_page_size_in_constructor(self) -> None:
        for invalid_page_size in [0, -4096, 1000, 3000, 5000]:
            with self.assertRaises(ValueError):
                RAMMemory(page_size=invalid_page_size)


if __name__ == "__main__":
    unittest.main(verbosity=2)
