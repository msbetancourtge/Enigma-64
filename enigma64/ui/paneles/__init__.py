"""
Paneles de la interfaz. Uno por modulo, todos independientes entre si.

Importante: este paquete reexporta las clases por comodidad de la ventana
principal, pero NINGUN modulo de panel importa a otro. Cada uno se puede
arrancar por separado:

    python -m enigma64.ui.paneles.panel_memoria
    python -m enigma64.ui.paneles.panel_registros
    python -m enigma64.ui.paneles.panel_alu
    python -m enigma64.ui.paneles.panel_fpu
    python -m enigma64.ui.paneles.panel_cargador
    python -m enigma64.ui.paneles.panel_cpu
    python -m enigma64.ui.paneles.panel_mmio
    python -m enigma64.ui.paneles.panel_algoritmos
    python -m enigma64.ui.paneles.panel_mapa
    python -m enigma64.ui.paneles.panel_consola
"""

from .base import PanelBase
from .panel_algoritmos import PanelAlgoritmos
from .panel_alu import PanelALU
from .panel_cargador import PanelCargador
from .panel_consola import PanelConsola
from .panel_cpu import PanelCPU
from .panel_fpu import PanelFPU
from .panel_mapa import PanelMapa
from .panel_memoria import PanelMemoria
from .panel_mmio import PanelMMIO
from .panel_registros import PanelRegistros

#: Todos los paneles, en el orden en que se presentan en la documentacion.
PANELES = (PanelMemoria, PanelRegistros, PanelALU, PanelFPU, PanelCargador,
           PanelCPU, PanelMMIO, PanelAlgoritmos, PanelMapa, PanelConsola)

__all__ = ["PanelBase", "PanelALU", "PanelAlgoritmos", "PanelCargador",
           "PanelConsola", "PanelCPU", "PanelFPU", "PanelMapa", "PanelMemoria", "PanelMMIO",
           "PanelRegistros", "PANELES"]
