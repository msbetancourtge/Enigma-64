"""
Pruebas del módulo de periféricos y controlador de pantalla MMIO (Integrante 6).

Verifica el comportamiento del hardware emulado:
  * Controlador de pantalla (0xFF001000): registros, buffer de texto, caracteres,
    saltos de línea, scroll y comandos CTRL (CLEAR, RESET).
  * Gestor general de perifericos: enrutamiento de los 5 controladores de la Tarea 9.

Autor: Integrante 6 - Visor/Editor RAM & MMIO
"""

from __future__ import annotations

import unittest

from enigma64.perifericos import (
    BASE_DISCO, BASE_PANTALLA, BASE_RED, BASE_TECLADO, BASE_TEMPORIZADOR,
    CMD_CLEAR, CMD_NEWLINE, CMD_RESET, CMD_SCROLL_UP,
    OFFSET_ADDR, OFFSET_COUNT, OFFSET_CTRL, OFFSET_DATA, OFFSET_STATUS,
    STATUS_READY, ControladorPantalla, Perifericos,
)


class TestControladorPantalla(unittest.TestCase):
    """Pruebas del controlador básico de pantalla MMIO."""

    def setUp(self) -> None:
        self.pantalla = ControladorPantalla(filas=10, columnas=20)

    def test_estado_inicial(self) -> None:
        self.assertEqual(self.pantalla.status, STATUS_READY)
        self.assertEqual(self.pantalla.cursor_fila, 0)
        self.assertEqual(self.pantalla.cursor_col, 0)
        self.assertEqual(self.pantalla.addr, 0)
        self.assertEqual(self.pantalla.count, 0)
        self.assertEqual(self.pantalla.ctrl, 0)

    def test_escritura_caracteres_simples(self) -> None:
        self.pantalla.escribir_registro(OFFSET_DATA, ord("H"))
        self.pantalla.escribir_registro(OFFSET_DATA, ord("O"))
        self.pantalla.escribir_registro(OFFSET_DATA, ord("L"))
        self.pantalla.escribir_registro(OFFSET_DATA, ord("A"))

        self.assertEqual(self.pantalla.count, 4)
        self.assertEqual(self.pantalla.cursor_col, 4)
        self.assertEqual(self.pantalla.cursor_fila, 0)
        self.assertEqual(self.pantalla.addr, 4)
        self.assertEqual(self.pantalla.obtener_lineas()[0], "HOLA")

    def test_salto_de_linea_y_retorno(self) -> None:
        self.pantalla.escribir_cadena("ABC\nDEF")
        lineas = self.pantalla.obtener_lineas()
        self.assertEqual(lineas[0], "ABC")
        self.assertEqual(lineas[1], "DEF")
        self.assertEqual(self.pantalla.cursor_fila, 1)
        self.assertEqual(self.pantalla.cursor_col, 3)

    def test_backspace(self) -> None:
        self.pantalla.escribir_cadena("HOLA\b\b Mundo")
        lineas = self.pantalla.obtener_lineas()
        self.assertEqual(lineas[0], "HO Mundo")

    def test_tabulador(self) -> None:
        self.pantalla.escribir_cadena("A\tB")
        lineas = self.pantalla.obtener_lineas()
        self.assertEqual(lineas[0], "A   B")

    def test_scroll_vertical_al_llenar_filas(self) -> None:
        # La pantalla tiene 10 filas; escribimos 12 lineas
        for i in range(12):
            self.pantalla.escribir_cadena(f"Linea {i}\n")

        lineas = self.pantalla.obtener_lineas()
        # Con 10 filas y 12 lineas con salto final (\n), se producen 3 desplazamientos
        self.assertIn("Linea 3", lineas[0])
        self.assertIn("Linea 11", lineas[8])

    def test_comando_clear(self) -> None:
        self.pantalla.escribir_cadena("Texto de prueba")
        self.pantalla.escribir_registro(OFFSET_CTRL, CMD_CLEAR)

        self.assertEqual(self.pantalla.cursor_fila, 0)
        self.assertEqual(self.pantalla.cursor_col, 0)
        self.assertEqual(self.pantalla.addr, 0)
        self.assertEqual(self.pantalla.obtener_texto().strip(), "")

    def test_comando_reset(self) -> None:
        self.pantalla.escribir_cadena("Datos")
        self.pantalla.escribir_registro(OFFSET_CTRL, CMD_RESET)

        self.assertEqual(self.pantalla.count, 0)
        self.assertEqual(self.pantalla.status, STATUS_READY)
        self.assertEqual(self.pantalla.obtener_texto().strip(), "")

    def test_mover_cursor_mediante_addr(self) -> None:
        # Colocar cursor en fila 2, col 5 -> 2 * 20 + 5 = 45
        self.pantalla.escribir_registro(OFFSET_ADDR, 45)
        self.assertEqual(self.pantalla.cursor_fila, 2)
        self.assertEqual(self.pantalla.cursor_col, 5)

        self.pantalla.escribir_cadena("XY")
        lineas = self.pantalla.obtener_lineas()
        self.assertEqual(lineas[2], "     XY")

    def test_notificacion_a_escuchadores(self) -> None:
        notificado = []
        def al_cambiar():
            notificado.append(True)

        self.pantalla.suscribir(al_cambiar)
        self.pantalla.escribir_registro(OFFSET_DATA, ord("Z"))
        self.assertTrue(len(notificado) > 0)

        self.pantalla.desuscribir(al_cambiar)
        prev_len = len(notificado)
        self.pantalla.escribir_registro(OFFSET_DATA, ord("W"))
        self.assertEqual(len(notificado), prev_len)


class TestSubsistemaPerifericos(unittest.TestCase):
    """Pruebas del gestor de perifericos MMIO completo."""

    def setUp(self) -> None:
        self.mmio = Perifericos()

    def test_no_es_provisional(self) -> None:
        self.assertFalse(self.mmio.es_provisional)

    def test_enrutamiento_pantalla(self) -> None:
        # Escribir en DATA de pantalla
        self.mmio.escribir(BASE_PANTALLA, OFFSET_DATA, ord("E"))
        self.mmio.escribir(BASE_PANTALLA, OFFSET_DATA, ord("6"))
        self.mmio.escribir(BASE_PANTALLA, OFFSET_DATA, ord("4"))

        self.assertEqual(self.mmio.leer(BASE_PANTALLA, OFFSET_COUNT), 3)
        self.assertEqual(self.mmio.controlador_pantalla.obtener_lineas()[0], "E64")

    def test_enrutamiento_disco(self) -> None:
        self.mmio.escribir(BASE_DISCO, OFFSET_ADDR, 0x1234)
        self.mmio.escribir(BASE_DISCO, OFFSET_COUNT, 8)
        self.assertEqual(self.mmio.leer(BASE_DISCO, OFFSET_ADDR), 0x1234)
        self.assertEqual(self.mmio.leer(BASE_DISCO, OFFSET_COUNT), 8)

    def test_enrutamiento_red_mac_inicial(self) -> None:
        self.assertEqual(self.mmio.leer(BASE_RED, OFFSET_DATA), 0x4E4F43545541)

    def test_reiniciar_todos_los_controladores(self) -> None:
        self.mmio.escribir(BASE_PANTALLA, OFFSET_DATA, ord("A"))
        self.mmio.escribir(BASE_DISCO, OFFSET_ADDR, 0x99)
        self.mmio.reiniciar()

        self.assertEqual(self.mmio.leer(BASE_PANTALLA, OFFSET_COUNT), 0)
        self.assertEqual(self.mmio.leer(BASE_DISCO, OFFSET_ADDR), 0)
        self.assertEqual(self.mmio.leer(BASE_PANTALLA, OFFSET_STATUS), STATUS_READY)

    def test_instantanea(self) -> None:
        snap = self.mmio.instantanea(BASE_PANTALLA)
        self.assertEqual(set(snap.keys()), {0x00, 0x08, 0x10, 0x18, 0x20})
        self.assertEqual(snap[OFFSET_STATUS], STATUS_READY)


if __name__ == "__main__":
    unittest.main()
