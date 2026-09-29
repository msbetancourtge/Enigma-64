"""Nucleo de la interfaz: sistema de diseno, bus de eventos y widgets."""

from .bus import BusEventos, BusNulo, Evento, Mensaje
from .tema import COMPUTADOR, EMPRESA, LEMA, PALETA, aplicar_tema, mono, sans

__all__ = [
    "BusEventos", "BusNulo", "Evento", "Mensaje",
    "COMPUTADOR", "EMPRESA", "LEMA", "PALETA", "aplicar_tema", "mono", "sans",
]
