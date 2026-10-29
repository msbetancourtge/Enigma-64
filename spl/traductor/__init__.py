"""
Paquete traductor de ensamblador CacaoCore-64 a Enigma-64.

  memoria.py      accesos a memoria, direccionamiento y alineacion (Integrante 1)
  registros.py    asignacion de registros y derrames (Integrante 2)
  alu.py          operaciones de la ALU (Integrante 2)
  control.py      etiquetas, saltos, pila, subrutinas y HLT (Integrante 3)
  directivas.py   secciones, directivas, literales y enlace con cargador (Integrante 4)
  traductor.py    driver integrador: lee .asm de CacaoCore y escribe el de Enigma-64
  mmio_soporte.py soporte de salida por MMIO (Base 0xFF001000 / Registro DATA 0xFF001010) (Integrante 6)
"""

from .alu import TraductorALU, cargar_constante
from .control import TraductorControl
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
from .verificacion import (
    ARCHIVOS_ALGORITMOS_CACAO,
    RESULTADOS_OFICIALES_TAREA10,
    ReporteVerificacionTraductor,
    ResultadoVerificacionAlgoritmo,
    construir_definiciones_programas_tarea27,
    ejecutar_algoritmo_nativo_tarea10,
    ejecutar_pipeline_verificacion_cacao,
    verificar_algoritmo_cacao,
)

__all__ = [
    "TraductorMemoria",
    "LexerMemoriaCacao",
    "TablaRegistros",
    "mapear_registro",
    "emitir_load",
    "emitir_store",
    "TraductorALU",
    "cargar_constante",
    "TraductorControl",
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
    "ARCHIVOS_ALGORITMOS_CACAO",
    "RESULTADOS_OFICIALES_TAREA10",
    "ResultadoVerificacionAlgoritmo",
    "ReporteVerificacionTraductor",
    "verificar_algoritmo_cacao",
    "ejecutar_pipeline_verificacion_cacao",
    "ejecutar_algoritmo_nativo_tarea10",
    "construir_definiciones_programas_tarea27",
]
