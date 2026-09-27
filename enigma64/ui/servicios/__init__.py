"""Capa de servicios: contratos y adaptadores hacia los modulos del equipo."""

from .adaptadores import (
    AdaptadorALU, AdaptadorCPU, AdaptadorCargador, AdaptadorMemoria,
    AdaptadorMMIO, AdaptadorRegistros,
)
from .fabrica import Maquina, construir_maquina
from .puertos import (
    FASES_FSM, MICRO_REGISTROS, PuertoALU, PuertoCPU, PuertoCargador,
    PuertoMMIO, PuertoMemoria, PuertoRegistros, ServicioBase,
    ServicioNoDisponible,
)

__all__ = [
    "AdaptadorALU", "AdaptadorCPU", "AdaptadorCargador", "AdaptadorMemoria",
    "AdaptadorMMIO", "AdaptadorRegistros",
    "Maquina", "construir_maquina",
    "FASES_FSM", "MICRO_REGISTROS",
    "PuertoALU", "PuertoCPU", "PuertoCargador", "PuertoMMIO", "PuertoMemoria",
    "PuertoRegistros", "ServicioBase", "ServicioNoDisponible",
]
