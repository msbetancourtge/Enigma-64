"""
Modulo de Perifericos y Controladores MMIO - Enigma-64.

Implementa los controladores del espacio de entrada/salida mapeada en memoria (MMIO)
en el rango 0xFF000000 - 0xFFFFFFFF (Bits 31-24 == 0xFF) de acuerdo con la Tarea 9:
  * Cada controlador ocupa una pagina fisica de 4 KiB (0x1000 bytes).
  * Los registros van en desplazamientos fijos de 8 bytes (+0x00 CTRL, +0x08 STATUS,
    +0x10 DATA, +0x18 ADDR, +0x20 COUNT).
  * Controlador básico de pantalla (Salida, base 0xFF001000):
      - Buffer de texto de terminal/pantalla emulada.
      - Manejo de caracteres ASCII, saltos de línea (\\n), retornos (\\r), backspace (\\b).
      - Cursor de texto (fila, columna) y dirección lineal (ADDR).
      - Conteo de caracteres emitidos (COUNT).
      - Comandos de control (CTRL): limpiar pantalla, resetear cursor, etc.
      - Notificaciones a escuchadores/UI en tiempo real.
  * Dispositivos mapeados:
      - 0xFF000000: Entrada (teclado)
      - 0xFF001000: Salida (pantalla)
      - 0xFF002000: Memoria secundaria (disco)
      - 0xFF003000: Interfaz de red
      - 0xFF004000: Temporizador / reloj de tiempo real

Autor: Integrante 6 - Visor/Editor RAM & MMIO
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

# Constantes del mapa MMIO (Tarea 9)
BASE_MMIO: int = 0xFF000000
TAMANO_PAGINA: int = 0x1000  # 4 KiB
ANCHO_REGISTRO: int = 8

# Direcciones base de los cinco controladores
BASE_TECLADO: int = 0xFF000000
BASE_PANTALLA: int = 0xFF001000
BASE_DISCO: int = 0xFF002000
BASE_RED: int = 0xFF003000
BASE_TEMPORIZADOR: int = 0xFF004000

# Desplazamientos estandar de registros
OFFSET_CTRL: int = 0x00
OFFSET_STATUS: int = 0x08
OFFSET_DATA: int = 0x10
OFFSET_ADDR: int = 0x18
OFFSET_COUNT: int = 0x20

# Comandos del registro CTRL para el Controlador de Pantalla
CMD_NOP: int = 0x00
CMD_CLEAR: int = 0x01       # Limpia el buffer de pantalla y resetea cursor a 0
CMD_RESET: int = 0x02       # Reinicia el controlador de pantalla
CMD_NEWLINE: int = 0x03     # Inserta salto de linea
CMD_SCROLL_UP: int = 0x04   # Desplaza lineas hacia arriba

# Estados devueltos en STATUS
STATUS_ERROR: int = 0
STATUS_READY: int = 1
STATUS_BUSY: int = 2


class ControladorPantalla:
    """
    Controlador básico de pantalla MMIO (Base 0xFF001000).

    Maneja un buffer de texto emulado con soporte de cursor bidimensional
    y lineal, control de caracteres ASCII estándar, scroll vertical y
    comandos de control.
    """

    def __init__(self, filas: int = 25, columnas: int = 80) -> None:
        self.filas: int = filas
        self.columnas: int = columnas
        self._listeners: List[Callable[[], None]] = []

        # Registros de hardware (64 bits cada uno)
        self.ctrl: int = CMD_NOP
        self.status: int = STATUS_READY
        self.data: int = 0
        self.addr: int = 0
        self.count: int = 0

        # Buffer de caracteres: matriz de caracteres [fila][columna]
        self.buffer: List[List[str]] = [[" " for _ in range(self.columnas)] for _ in range(self.filas)]
        self.cursor_fila: int = 0
        self.cursor_col: int = 0

    def suscribir(self, callback: Callable[[], None]) -> None:
        """Registra un callback que se invoca ante cambios en la pantalla."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def desuscribir(self, callback: Callable[[], None]) -> None:
        """Elimina un callback registrado."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notificar(self) -> None:
        """Notifica a todos los escuchadores registrados."""
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                pass

    def reiniciar(self) -> None:
        """Devuelve el controlador de pantalla a su estado inicial de encendido."""
        self.ctrl = CMD_NOP
        self.status = STATUS_READY
        self.data = 0
        self.addr = 0
        self.count = 0
        self.cursor_fila = 0
        self.cursor_col = 0
        self.buffer = [[" " for _ in range(self.columnas)] for _ in range(self.filas)]
        self._notificar()

    def limpiar(self) -> None:
        """Borra todo el contenido de la pantalla y regresa el cursor a (0, 0)."""
        self.buffer = [[" " for _ in range(self.columnas)] for _ in range(self.filas)]
        self.cursor_fila = 0
        self.cursor_col = 0
        self.addr = 0
        self._notificar()

    def leer_registro(self, desplazamiento: int) -> int:
        """Lee uno de los registros del controlador según su desplazamiento."""
        if desplazamiento == OFFSET_CTRL:
            return self.ctrl
        elif desplazamiento == OFFSET_STATUS:
            return self.status
        elif desplazamiento == OFFSET_DATA:
            return self.data
        elif desplazamiento == OFFSET_ADDR:
            return self.addr
        elif desplazamiento == OFFSET_COUNT:
            return self.count
        return 0

    def escribir_registro(self, desplazamiento: int, valor: int) -> None:
        """Escribe en uno de los registros del controlador."""
        valor_64 = valor & 0xFFFFFFFFFFFFFFFF

        if desplazamiento == OFFSET_CTRL:
            self.ctrl = valor_64
            self._procesar_comando(int(valor_64 & 0xFF))
        elif desplazamiento == OFFSET_STATUS:
            self.status = valor_64
        elif desplazamiento == OFFSET_DATA:
            self.data = valor_64
            self._emitir_byte(int(valor_64 & 0xFF))
        elif desplazamiento == OFFSET_ADDR:
            self.addr = valor_64
            # Permite mover el cursor programaticamente
            pos = int(valor_64 % (self.filas * self.columnas))
            self.cursor_fila = pos // self.columnas
            self.cursor_col = pos % self.columnas
            self._notificar()
        elif desplazamiento == OFFSET_COUNT:
            self.count = valor_64

    def _procesar_comando(self, comando: int) -> None:
        """Ejecuta un comando recibido en el registro CTRL."""
        if comando == CMD_CLEAR:
            self.limpiar()
        elif comando == CMD_RESET:
            self.reiniciar()
        elif comando == CMD_NEWLINE:
            self._avanzar_linea()
            self._notificar()
        elif comando == CMD_SCROLL_UP:
            self._scroll_arriba()
            self._notificar()

    def _emitir_byte(self, byte_val: int) -> None:
        """Procesa un byte escrito en el registro DATA y lo imprime en el buffer."""
        self.count = (self.count + 1) & 0xFFFFFFFFFFFFFFFF

        if byte_val == 10:  # \\n (Line Feed / Nueva linea)
            self._avanzar_linea()
        elif byte_val == 13:  # \\r (Carriage Return)
            self.cursor_col = 0
        elif byte_val == 8:  # \\b (Backspace)
            if self.cursor_col > 0:
                self.cursor_col -= 1
                self.buffer[self.cursor_fila][self.cursor_col] = " "
        elif byte_val == 9:  # \\t (Tabulador - avanza a multiplo de 4)
            siguiente = ((self.cursor_col // 4) + 1) * 4
            while self.cursor_col < siguiente and self.cursor_col < self.columnas:
                self.buffer[self.cursor_fila][self.cursor_col] = " "
                self.cursor_col += 1
            if self.cursor_col >= self.columnas:
                self._avanzar_linea()
        elif 32 <= byte_val <= 126 or byte_val >= 160:  # Caracter imprimible
            char = chr(byte_val)
            self.buffer[self.cursor_fila][self.cursor_col] = char
            self.cursor_col += 1
            if self.cursor_col >= self.columnas:
                self._avanzar_linea()
        else:
            # Caracter no imprimible: colocar espacio o avanzar
            self.buffer[self.cursor_fila][self.cursor_col] = "·"
            self.cursor_col += 1
            if self.cursor_col >= self.columnas:
                self._avanzar_linea()

        self.addr = self.cursor_fila * self.columnas + self.cursor_col
        self._notificar()

    def _avanzar_linea(self) -> None:
        """Mueve el cursor a la siguiente fila al inicio; si excede las filas, hace scroll."""
        self.cursor_col = 0
        if self.cursor_fila < self.filas - 1:
            self.cursor_fila += 1
        else:
            self._scroll_arriba()

    def _scroll_arriba(self) -> None:
        """Desplaza todas las filas hacia arriba y crea una nueva linea vacia abajo."""
        for f in range(self.filas - 1):
            self.buffer[f] = list(self.buffer[f + 1])
        self.buffer[self.filas - 1] = [" " for _ in range(self.columnas)]

    def escribir_cadena(self, texto: str) -> None:
        """Escribe una cadena completa en la pantalla emitiendo sus bytes secuencialmente."""
        for char in texto:
            byte_val = ord(char)
            self.data = byte_val
            self._emitir_byte(byte_val)

    def obtener_lineas(self) -> List[str]:
        """Devuelve las lineas actuales de la pantalla recortando espacios al final."""
        return ["".join(fila).rstrip() for fila in self.buffer]

    def obtener_texto(self) -> str:
        """Devuelve el contenido completo de la pantalla como una cadena multilineal."""
        return "\n".join(self.obtener_lineas())

    def obtener_estado(self) -> Dict[str, Any]:
        """Devuelve un resumen del estado del controlador de pantalla."""
        return {
            "filas": self.filas,
            "columnas": self.columnas,
            "cursor_fila": self.cursor_fila,
            "cursor_col": self.cursor_col,
            "cursor_lineal": self.addr,
            "caracteres_emitidos": self.count,
            "status": self.status,
            "ctrl": self.ctrl,
        }


class ControladorGenerico:
    """Controlador generico MMIO para dispositivos con registros estandar."""

    def __init__(self, base: int, clave: str, mac: int = 0) -> None:
        self.base: int = base
        self.clave: str = clave
        self.registros: Dict[int, int] = {
            OFFSET_CTRL: 0,
            OFFSET_STATUS: STATUS_READY,
            OFFSET_DATA: mac if mac else 0,
            OFFSET_ADDR: 0,
            OFFSET_COUNT: 0,
        }

    def reiniciar(self) -> None:
        self.registros[OFFSET_CTRL] = 0
        self.registros[OFFSET_STATUS] = STATUS_READY
        self.registros[OFFSET_ADDR] = 0
        self.registros[OFFSET_COUNT] = 0

    def leer(self, desplazamiento: int) -> int:
        return self.registros.get(desplazamiento, 0)

    def escribir(self, desplazamiento: int, valor: int) -> None:
        self.registros[desplazamiento] = valor & 0xFFFFFFFFFFFFFFFF


class Perifericos:
    """
    Gestor del subsistema de E/S Mapeada en Memoria (MMIO) - Enigma-64.

    Controla el espacio 0xFF000000 - 0xFFFFFFFF integrando el Controlador de Pantalla
    y los demas controladores de la arquitectura.
    """

    es_provisional: bool = False

    def __init__(self) -> None:
        self.pantalla = ControladorPantalla()
        self.teclado = ControladorGenerico(BASE_TECLADO, "teclado")
        self.disco = ControladorGenerico(BASE_DISCO, "disco")
        self.red = ControladorGenerico(BASE_RED, "red", mac=0x4E4F43545541)  # "NOCTUA"
        self.temporizador = ControladorGenerico(BASE_TEMPORIZADOR, "temporizador")

        self._mapa_controladores: Dict[int, Any] = {
            BASE_TECLADO: self.teclado,
            BASE_PANTALLA: self.pantalla,
            BASE_DISCO: self.disco,
            BASE_RED: self.red,
            BASE_TEMPORIZADOR: self.temporizador,
        }

    def reiniciar(self) -> None:
        """Reinicia todos los controladores al estado de encendido."""
        self.teclado.reiniciar()
        self.pantalla.reiniciar()
        self.disco.reiniciar()
        self.red.reiniciar()
        self.temporizador.reiniciar()

    def leer(self, base: int, desplazamiento: int) -> int:
        """Lee el registro indicado del controlador correspondiente."""
        ctrl = self._mapa_controladores.get(base)
        if ctrl is None:
            return 0
        if isinstance(ctrl, ControladorPantalla):
            return ctrl.leer_registro(desplazamiento)
        return ctrl.leer(desplazamiento)

    def escribir(self, base: int, desplazamiento: int, valor: int) -> None:
        """Escribe en el registro indicado del controlador correspondiente."""
        ctrl = self._mapa_controladores.get(base)
        if ctrl is None:
            return
        if isinstance(ctrl, ControladorPantalla):
            ctrl.escribir_registro(desplazamiento, valor)
        else:
            ctrl.escribir(desplazamiento, valor)

    def instantanea(self, base: int) -> Dict[int, int]:
        """Devuelve un diccionario con los cinco registros del controlador."""
        return {
            despl: self.leer(base, despl)
            for despl in (OFFSET_CTRL, OFFSET_STATUS, OFFSET_DATA, OFFSET_ADDR, OFFSET_COUNT)
        }

    @property
    def controlador_pantalla(self) -> ControladorPantalla:
        return self.pantalla


# Alias para compatibilidad con busquedas por pato en adaptadores
ControladoresMMIO = Perifericos
BancoMMIO = Perifericos
MMIO = Perifericos
