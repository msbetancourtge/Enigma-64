"""
Paquete traductor de ensamblador CacaoCore-64 a Enigma-64.

  memoria.py      accesos a memoria, direccionamiento y alineacion (Integrante 1)
  registros.py    asignacion de registros y derrames (Integrante 2)
  alu.py          operaciones de la ALU (Integrante 2)
  directivas.py   secciones, directivas, literales y enlace con cargador (Integrante 4)
  traductor.py    driver integrador: lee .asm de CacaoCore y escribe el de Enigma-64
  mmio_soporte.py soporte de salida por MMIO (Base 0xFF001000 / Registro DATA 0xFF001010) (Integrante 6)
"""

from .alu import TraductorALU, cargar_constante
from .directivas import (
    LexerDirectivasCacao,
    MapaSeccionDatos,
    ProcesadorDirectivasCacao,
    VariableDato,
    cargar_y_ejecutar_con_cargador,
    construir_binario_enigma,
    exportar_ejecutable_e64,
    normalizar_literal_cacao,
    precargar_datos_en_ram,
)
from .memoria import LexerMemoriaCacao, TraductorMemoria
from .mmio_soporte import (
    PUERTO_SALIDA_PANTALLA,
    ejecutar_en_enigma_mmio,
    generar_emision_ascii_mmio,
    inyectar_salida_mmio,
)
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
    "LexerDirectivasCacao",
    "ProcesadorDirectivasCacao",
    "VariableDato",
    "MapaSeccionDatos",
    "normalizar_literal_cacao",
    "precargar_datos_en_ram",
    "construir_binario_enigma",
    "exportar_ejecutable_e64",
    "cargar_y_ejecutar_con_cargador",
    "TraductorCacaoEnigma",
    "traducir_texto",
    "ejecutar_en_enigma",
    "PUERTO_SALIDA_PANTALLA",
    "generar_emision_ascii_mmio",
    "inyectar_salida_mmio",
    "ejecutar_en_enigma_mmio",
]
