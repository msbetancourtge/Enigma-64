"""
SPL — Sistema de Procesamiento del Lenguaje para el computador Enigma-64 (Noctua Systems).

Integra los 4 subsistemas del Taller #01:
  1. Preprocesador (spl.preprocesador)
  2. Analizador Léxico del Compilador & Tablas de Símbolos (spl.compilador)
  3. Analizador Léxico del Ensamblador (spl.ensamblador)
  4. Orquestador del Pipeline & Enlazador-Cargador (spl.pipeline / enigma64.enlazador)
"""

from spl.pipeline import (
    EtapaCompiladorResult,
    EtapaEnlazadorCargadorResult,
    EtapaEnsambladorResult,
    EtapaPreprocesadorResult,
    OrquestadorSPL,
    ResultadoPipelineSPL,
    verificar_modulo_c_tablas,
)

__all__ = [
    "OrquestadorSPL",
    "ResultadoPipelineSPL",
    "EtapaPreprocesadorResult",
    "EtapaCompiladorResult",
    "EtapaEnsambladorResult",
    "EtapaEnlazadorCargadorResult",
    "verificar_modulo_c_tablas",
]
