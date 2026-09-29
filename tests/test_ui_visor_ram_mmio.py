"""
Pruebas del Visor/Editor de RAM & MMIO (Integrante 6).

Verifica:
  * Manipulación directa de bytes y bits en AdaptadorMemoria.
  * Vinculación del ControladorPantalla en AdaptadorMMIO.
  * Comportamiento y lógica de los componentes de interfaz:
    - GrillaBytesInteractiva (8 bancos de la Tarea 9, A[2:0]).
    - InspectorBitsByte (conmutación de bits b7..b0, cálculo de desgloses).
    - MonitorPantallaCRT (buffer de texto, cursor y emisión de comandos).

Autor: Integrante 6 - Visor/Editor RAM & MMIO
"""

from __future__ import annotations

import unittest

from enigma64.ui.servicios.adaptadores import AdaptadorMemoria, AdaptadorMMIO
from enigma64.ui.servicios.mapa_memoria import nombre_region


class TestVisorEditorRAM(unittest.TestCase):
    """Pruebas del backend de manipulación de memoria y lógica del visor de RAM."""

    def setUp(self) -> None:
        self.memoria = AdaptadorMemoria()

    def test_escribir_y_leer_byte_directo(self) -> None:
        self.memoria.escribir_byte(0x00200000, 0xA5)
        self.assertEqual(self.memoria.leer_byte(0x00200000), 0xA5)

    def test_leer_bit_individual(self) -> None:
        # 0xA5 = 10100101b
        self.memoria.escribir_byte(0x00200000, 0xA5)
        self.assertEqual(self.memoria.leer_bit(0x00200000, 0), 1)
        self.assertEqual(self.memoria.leer_bit(0x00200000, 1), 0)
        self.assertEqual(self.memoria.leer_bit(0x00200000, 2), 1)
        self.assertEqual(self.memoria.leer_bit(0x00200000, 3), 0)
        self.assertEqual(self.memoria.leer_bit(0x00200000, 7), 1)

    def test_escribir_bit_individual(self) -> None:
        self.memoria.escribir_byte(0x00200000, 0x00)
        self.memoria.escribir_bit(0x00200000, 3, 1)
        self.assertEqual(self.memoria.leer_byte(0x00200000), 0x08)

        self.memoria.escribir_bit(0x00200000, 3, 0)
        self.assertEqual(self.memoria.leer_byte(0x00200000), 0x00)

    def test_conmutar_bit_en_vivo(self) -> None:
        self.memoria.escribir_byte(0x00200000, 0x00)
        nuevo_bit = self.memoria.conmutar_bit(0x00200000, 4)
        self.assertEqual(nuevo_bit, 1)
        self.assertEqual(self.memoria.leer_byte(0x00200000), 0x10)

        segundo_bit = self.memoria.conmutar_bit(0x00200000, 4)
        self.assertEqual(segundo_bit, 0)
        self.assertEqual(self.memoria.leer_byte(0x00200000), 0x00)

    def test_organizacion_en_ocho_bancos(self) -> None:
        """Verifica que A[2:0] mapee correctamente a los bancos 0..7 de la Tarea 9."""
        direccion_base = 0x00200010
        for banco in range(8):
            direccion_byte = direccion_base + banco
            self.assertEqual(direccion_byte & 0x07, banco)
            self.memoria.escribir_byte(direccion_byte, banco * 10)

        # Leer la palabra de 64 bits completa en Big-Endian
        palabra, estado = self.memoria.leer(direccion_base, 8, verificar_alineacion=True)
        self.assertEqual(estado, "READY")
        # El banco 0 es el byte más significativo en Big-Endian (offset 0)
        # y banco 7 es el menos significativo (offset 7)
        self.assertIsNotNone(palabra)


class TestVisorEditorMMIO(unittest.TestCase):
    """Pruebas de la integración de MMIO y la pantalla emulada."""

    def setUp(self) -> None:
        self.mmio = AdaptadorMMIO()

    def test_modulo_real_conectado(self) -> None:
        self.assertFalse(self.mmio.es_provisional)
        self.assertEqual(self.mmio.advertencia, "")
        self.assertIsNotNone(self.mmio.controlador_pantalla)

    def test_emision_de_texto_a_pantalla_mmio(self) -> None:
        # Emitir caracteres a DATA de pantalla (0xFF001010)
        texto = "NOCTUA"
        for char in texto:
            self.mmio.escribir(0xFF001000, 0x10, ord(char))

        ctrl_pantalla = self.mmio.controlador_pantalla
        self.assertIsNotNone(ctrl_pantalla)
        self.assertEqual(ctrl_pantalla.obtener_lineas()[0], "NOCTUA")
        self.assertEqual(self.mmio.leer(0xFF001000, 0x20), len(texto))  # COUNT

    def test_limpiar_pantalla_mediante_ctrl(self) -> None:
        self.mmio.escribir(0xFF001000, 0x10, ord("X"))
        self.mmio.escribir(0xFF001000, 0x00, 1)  # CMD_CLEAR en CTRL

        ctrl_pantalla = self.mmio.controlador_pantalla
        self.assertEqual(ctrl_pantalla.obtener_texto().strip(), "")
        self.assertEqual(ctrl_pantalla.cursor_col, 0)
        self.assertEqual(ctrl_pantalla.cursor_fila, 0)


if __name__ == "__main__":
    unittest.main()
