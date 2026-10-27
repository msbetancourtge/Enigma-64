"""
Paquete traductor de ensamblador CacaoCore-64 a Enigma-64.

  memoria.py    accesos a memoria y direcciones (Integrante 1)
  registros.py  asignacion de registros y derrames (Integrante 2)
  alu.py        operaciones de la ALU (Integrante 2)
  traductor.py  driver: lee un .asm de CacaoCore y escribe el de Enigma-64
"""

from .alu import TraductorALU, cargar_constante
from .memoria import LexerMemoriaCacao, TraductorMemoria
from .registros import TablaRegistros, emitir_load, emitir_store, mapear_registro
from .traductor import TraductorCacaoEnigma, ejecutar_en_enigma, traducir_texto

__all__ = [
    "TraductorMemoria",
    "LexerMemoriaCacao",
    "TablaRegistros",
    "mapear_registro",
    "emitir_load",
    "emitir_store",
    "TraductorALU",
    "cargar_constante",
    "TraductorCacaoEnigma",
    "traducir_texto",
    "ejecutar_en_enigma",
]
