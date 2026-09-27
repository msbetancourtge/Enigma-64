"""
Espacio de I/O mapeada en memoria (0xFF000000 - 0xFFFFFFFF).

La Tarea 9 da a cada controlador una pagina de 4 KiB y coloca sus registros en
desplazamientos fijos de 8 bytes. Aqui vive esa tabla y, mientras el modulo de
perifericos no exista, un banco de registros provisional para que el
visor/editor sea demostrable desde ya.

IMPORTANTE - el banco provisional es un andamio, no hardware:
    `RAMMemory` enruta cualquier direccion 0xFF...... hacia el bus de
    perifericos y devuelve la senal MMIO sin guardar nada, que es justo lo que
    debe hacer. Alguien tiene que sostener el valor de esos registros, y
    todavia no hay un `enigma64.perifericos` que lo haga. `BancoMMIOProvisional`
    cubre ese hueco.

    Cuando el modulo real aparezca, `AdaptadorMMIO` lo prefiere solo y este
    banco deja de usarse; no hay que tocar el panel.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.tema import PALETA

#: Base del espacio de perifericos: A[31:24] == 0xFF.
BASE_MMIO: int = 0xFF000000
#: Cada controlador recibe una pagina de 4 KiB.
TAMANO_PAGINA: int = 0x1000
#: Los registros van en desplazamientos fijos de 8 bytes.
ANCHO_REGISTRO: int = 8


#: Controladores mapeados, en el orden del documento.
CONTROLADORES: List[Dict[str, Any]] = [
    {"clave": "teclado", "base": 0xFF000000, "nombre": "Entrada (teclado)",
     "color": PALETA["cian"],
     "nota": "El programa sondea STATUS y lee el caracter en DATA."},
    {"clave": "pantalla", "base": 0xFF001000, "nombre": "Salida (pantalla)",
     "color": PALETA["ok"],
     "nota": "Escribir en DATA emite un caracter; CTRL controla el volcado."},
    {"clave": "disco", "base": 0xFF002000, "nombre": "Memoria secundaria (disco)",
     "color": PALETA["ambar"],
     "nota": "LBA de 28 bits en ADDR, bloques en COUNT, comando en CTRL."},
    {"clave": "red", "base": 0xFF003000, "nombre": "Interfaz de red",
     "color": PALETA["violeta"],
     "nota": "Los campos se especializan: MAC de 48 bits, punteros de TX y RX."},
    {"clave": "temporizador", "base": 0xFF004000, "nombre": "Temporizador / reloj",
     "color": PALETA["alerta"],
     "nota": "Genera la interrupcion periodica que atiende la FSM tras Write-Back."},
]


#: Registros genericos: (desplazamiento, nombre, descripcion).
REGISTROS: List[Tuple[int, str, str]] = [
    (0x00, "CTRL", "Comando que se ordena al controlador."),
    (0x08, "STATUS", "Estado devuelto: listo, ocupado, error."),
    (0x10, "DATA", "Dato transferido en la operacion."),
    (0x18, "ADDR", "Direccion de RAM o bloque implicado."),
    (0x20, "COUNT", "Cantidad de unidades a transferir."),
]

#: La interfaz de red especializa los mismos desplazamientos (Tarea 9).
NOMBRES_RED: Dict[int, Tuple[str, str]] = {
    0x00: ("NET_CTRL", "Inicia transmision o recepcion."),
    0x08: ("NET_STATUS", "Listo, error o paquete disponible."),
    0x10: ("NET_MAC", "Direccion fisica de 48 bits."),
    0x18: ("NET_TX_ADDR", "Puntero al paquete a enviar (region de buffers)."),
    0x20: ("NET_TX_LEN", "Longitud del paquete a enviar."),
}


def controlador_de(direccion: int) -> Optional[Dict[str, Any]]:
    """Devuelve el controlador cuya pagina contiene la direccion."""
    for controlador in CONTROLADORES:
        if controlador["base"] <= direccion < controlador["base"] + TAMANO_PAGINA:
            return controlador
    return None


def registros_de(clave: str) -> List[Tuple[int, str, str]]:
    """Registros de un controlador, con los nombres especializados si los tiene."""
    if clave != "red":
        return list(REGISTROS)
    return [(desplazamiento, *NOMBRES_RED[desplazamiento])
            if desplazamiento in NOMBRES_RED else (desplazamiento, nombre, descripcion)
            for desplazamiento, nombre, descripcion in REGISTROS]


def descomponer(direccion: int) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
    """
    Parte una direccion MMIO en (controlador, desplazamiento, nombre de registro).

    El nombre es None si la direccion cae dentro de la pagina pero no sobre un
    registro definido.
    """
    controlador = controlador_de(direccion)
    if controlador is None:
        return None, 0, None
    desplazamiento = direccion - controlador["base"]
    for despl, nombre, _descripcion in registros_de(controlador["clave"]):
        if despl == desplazamiento:
            return controlador, desplazamiento, nombre
    return controlador, desplazamiento, None


class BancoMMIOProvisional:
    """
    Sostiene el valor de los registros de los controladores.

    Provisional: lo reemplaza `enigma64.perifericos` en cuanto exista. Guarda
    palabras de 64 bits indexadas por (base del controlador, desplazamiento).
    """

    #: Marca para que la interfaz pueda avisar de que esto no es el modulo real.
    es_provisional = True

    def __init__(self) -> None:
        self._registros: Dict[Tuple[int, int], int] = {}
        self.reiniciar()

    def reiniciar(self) -> None:
        """Estado de encendido de los controladores."""
        self._registros.clear()
        # STATUS = 1 (listo) en todos, que es el estado razonable tras el RESET.
        for controlador in CONTROLADORES:
            self._registros[(controlador["base"], 0x08)] = 1
        # La interfaz de red arranca con una MAC de laboratorio.
        self._registros[(0xFF003000, 0x10)] = 0x4E4F43545541  # "NOCTUA" en ASCII

    def leer(self, base: int, desplazamiento: int) -> int:
        return self._registros.get((base, desplazamiento), 0)

    def escribir(self, base: int, desplazamiento: int, valor: int) -> None:
        self._registros[(base, desplazamiento)] = valor & 0xFFFFFFFFFFFFFFFF

    def instantanea(self, base: int) -> Dict[int, int]:
        """Todos los registros de un controlador, por desplazamiento."""
        return {despl: self.leer(base, despl)
                for despl, _nombre, _descripcion in REGISTROS}
