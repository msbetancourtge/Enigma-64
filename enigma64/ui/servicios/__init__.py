"""Capa de servicios: contratos y adaptadores hacia los modulos del equipo."""

from .adaptadores import (
    AdaptadorALU, AdaptadorCargador, AdaptadorMemoria, AdaptadorRegistros,
)
from .fabrica import Maquina, construir_maquina
from .puertos import (
    PuertoALU, PuertoCargador, PuertoMemoria, PuertoRegistros,
    ServicioBase, ServicioNoDisponible,
)

__all__ = [
    "AdaptadorALU", "AdaptadorCargador", "AdaptadorMemoria", "AdaptadorRegistros",
    "Maquina", "construir_maquina",
    "PuertoALU", "PuertoCargador", "PuertoMemoria", "PuertoRegistros",
    "ServicioBase", "ServicioNoDisponible",
]
