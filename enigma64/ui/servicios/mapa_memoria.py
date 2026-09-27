"""
Mapa de memoria de Enigma-64, transcrito de la Tarea 9.

Es dato puro, sin dependencias: el panel del mapa funciona aunque ningun
modulo de hardware este disponible.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..core.tema import PALETA

#: Regiones del espacio fisico de 4 GiB, en el orden del documento.
REGIONES: List[Dict[str, Any]] = [
    {"nombre": "Vectores", "inicio": 0x00000000, "fin": 0x00000FFF,
     "permisos": "R / X", "color": PALETA["fallo"],
     "nota": "0x00000000 es el vector de reset: el PC arranca aqui."},
    {"nombre": "Monitor + Enlazador-Cargador", "inicio": 0x00001000, "fin": 0x000FFFFF,
     "permisos": "R / X", "color": PALETA["ambar"],
     "nota": "Firmware del cargador en 0x00001000."},
    {"nombre": "Trabajo del cargador", "inicio": 0x00100000, "fin": 0x0011FFFF,
     "permisos": "R / W (admin)", "color": PALETA["ambar_oscuro"],
     "nota": "Area de trabajo del cargador, solo en modo supervisor."},
    {"nombre": "Tablas del sistema", "inicio": 0x00120000, "fin": 0x001FFFFF,
     "permisos": "R / W (admin)", "color": PALETA["ambar_oscuro"],
     "nota": "Estructuras internas del monitor."},
    {"nombre": "Programas y datos", "inicio": 0x00200000, "fin": 0xBFFFFFFF,
     "permisos": "R / W / X", "color": PALETA["ok"],
     "nota": "Unica region donde el cargador acepta depositar un programa."},
    {"nombre": "Pila", "inicio": 0xC0000000, "fin": 0xEFFFFFFF,
     "permisos": "R / W (no ejecutable)", "color": PALETA["cian"],
     "nota": "SP arranca en 0xEFFFFFFF y crece hacia abajo."},
    {"nombre": "Buffers de I/O y DMA", "inicio": 0xF0000000, "fin": 0xFEFFFFFF,
     "permisos": "R / W (no cacheable)", "color": PALETA["cian_oscuro"],
     "nota": "Paquetes de red y transferencias por DMA."},
    {"nombre": "I/O mapeada", "inicio": 0xFF000000, "fin": 0xFFFFFFFF,
     "permisos": "R / W (admin)", "color": PALETA["violeta"],
     "nota": "A[31:24] == 0xFF activa el bus de perifericos en vez de la RAM."},
]

#: Controladores mapeados en memoria, una pagina de 4 KiB cada uno.
CONTROLADORES: List[Dict[str, Any]] = [
    {"base": 0xFF000000, "nombre": "Entrada (teclado)"},
    {"base": 0xFF001000, "nombre": "Salida (pantalla)"},
    {"base": 0xFF002000, "nombre": "Memoria secundaria (disco)"},
    {"base": 0xFF003000, "nombre": "Interfaz de red"},
    {"base": 0xFF004000, "nombre": "Temporizador / reloj"},
]

#: Desplazamientos fijos dentro de la pagina de cada controlador.
REGISTROS_MMIO = ("CTRL +0x00", "STATUS +0x08", "DATA +0x10", "ADDR +0x18", "COUNT +0x20")

LIMITE_FISICO = 0x100000000  # 4 GiB


def region_de(direccion: int) -> Optional[Dict[str, Any]]:
    """Devuelve la region que contiene la direccion, o None si no esta mapeada."""
    for region in REGIONES:
        if region["inicio"] <= direccion <= region["fin"]:
            return region
    return None


def nombre_region(direccion: int) -> str:
    region = region_de(direccion)
    return region["nombre"] if region else "No mapeado"
