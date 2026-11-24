"""
Paquete Preprocesador del SPL de Enigma-64.
"""

from spl.preprocesador.motor import (
    preprocesar_archivo,
    preprocesar_texto,
    exportar_archivo_pre,
    PreprocesadorError,
    ResultadoPreprocesamiento,
    MacroDef,
)

__all__ = [
    "preprocesar_archivo",
    "preprocesar_texto",
    "exportar_archivo_pre",
    "PreprocesadorError",
    "ResultadoPreprocesamiento",
    "MacroDef",
]
