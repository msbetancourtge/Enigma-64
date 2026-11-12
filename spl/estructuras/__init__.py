"""
Subpaquete de Estructuras de Datos (Listas y Matrices) y Enlace con CargadorEnigma.

Tarea 29 - Integrante 4 (Cargador, Directivas, Cabeceras y Enlace):
  * descriptores.py : constructores de cabeceras y descriptores en memoria
                      (DescriptorVector, DescriptorMatriz, MapaEstructurasRAM) y
                      normalizacion universal a palabras de 64 bits Big-Endian.
  * memoria.py      : precarga e inspeccion directa de vectores, matrices y
                      descriptores de 32 bytes sobre RAMMemory.
  * cargador.py     : puente Preprocesador -> Ensamblador -> BinarioEnigma (.e64)
                      -> CargadorEnigma -> CPU.

Linea de comandos:
    python -m spl.estructuras spl/ejemplos/merge_sort.asm [-o salida.e64] [--ejecutar]
"""

from .algoritmos import (
    BASE_MAT_A,
    BASE_MAT_B,
    BASE_MAT_C,
    BASE_VEC_A,
    BASE_VEC_B,
    BASE_VEC_RES,
    RUTA_ASM_BUSQUEDA_BINARIA,
    RUTA_ASM_MERGE_SORT,
    RUTA_ASM_MULTIPLICACION_MATRICES,
    RUTA_ASM_PRODUCTO_PUNTO,
    ejecutar_busqueda_binaria,
    ejecutar_matriz_por_vector,
    ejecutar_merge_sort,
    ejecutar_multiplicacion_matrices,
    ejecutar_producto_punto,
)
from .cargador import (
    ResultadoCompilacionEstructuras,
    ResultadoEjecucionEstructuras,
    cargar_y_ejecutar_estructuras,
    compilar_a_binario_e64,
    exportar_estructuras_e64,
)
from .descriptores import (
    BASE_BUFFERS,
    BASE_CABECERAS,
    BASE_CODIGO,
    BASE_MATRICES,
    BASE_VECTORES,
    DESC_TAM_BYTES,
    INT64_MAX,
    INT64_MIN,
    LIMITE_BUFFERS,
    LIMITE_CABECERAS,
    LIMITE_MATRICES,
    LIMITE_VECTORES,
    MIN_DATOS_ESTRUCTURAS,
    PALABRA_BYTES,
    PILA_ESTRUCTURAS,
    TAM_BUFFERS,
    TAM_CABECERAS,
    TAM_MATRICES,
    TAM_VECTORES,
    TIPO_MATRIZ,
    TIPO_VECTOR,
    UINT64_MAX,
    DescriptorMatriz,
    DescriptorVector,
    ErrorEstructuraDatos,
    EstructuraDescriptor,
    MapaEstructurasRAM,
    ValorElemento,
    desnormalizar_entero_64,
    desnormalizar_float_64,
    direccion_descriptor,
    normalizar_palabra_64,
    validar_alineacion_8,
)
from .memoria import (
    leer_descriptor_de_ram,
    leer_matriz_de_ram,
    leer_vector_de_ram,
    precargar_estructuras_en_ram,
    precargar_matriz_en_ram,
    precargar_vector_en_ram,
)

__all__ = [
    # Constantes del mapa de memoria y descriptores
    "BASE_CODIGO",
    "MIN_DATOS_ESTRUCTURAS",
    "BASE_CABECERAS",
    "TAM_CABECERAS",
    "LIMITE_CABECERAS",
    "BASE_VECTORES",
    "TAM_VECTORES",
    "LIMITE_VECTORES",
    "BASE_MATRICES",
    "TAM_MATRICES",
    "LIMITE_MATRICES",
    "BASE_BUFFERS",
    "TAM_BUFFERS",
    "LIMITE_BUFFERS",
    "PILA_ESTRUCTURAS",
    "PALABRA_BYTES",
    "DESC_TAM_BYTES",
    "TIPO_VECTOR",
    "TIPO_MATRIZ",
    "INT64_MIN",
    "INT64_MAX",
    "UINT64_MAX",
    # Normalizacion y validacion
    "ValorElemento",
    "EstructuraDescriptor",
    "ErrorEstructuraDatos",
    "validar_alineacion_8",
    "normalizar_palabra_64",
    "desnormalizar_entero_64",
    "desnormalizar_float_64",
    "direccion_descriptor",
    # Constructores y descriptores
    "DescriptorVector",
    "DescriptorMatriz",
    "MapaEstructurasRAM",
    # Precarga y lectura en RAMMemory
    "precargar_estructuras_en_ram",
    "precargar_vector_en_ram",
    "precargar_matriz_en_ram",
    "leer_descriptor_de_ram",
    "leer_vector_de_ram",
    "leer_matriz_de_ram",
    # Puente Preprocesador -> Ensamblador -> CargadorEnigma (.e64)
    "ResultadoCompilacionEstructuras",
    "ResultadoEjecucionEstructuras",
    "compilar_a_binario_e64",
    "exportar_estructuras_e64",
    "cargar_y_ejecutar_estructuras",
    # Ejecutores de los 3 Problemas Computacionales (Integrante 7)
    "RUTA_ASM_MERGE_SORT",
    "RUTA_ASM_PRODUCTO_PUNTO",
    "RUTA_ASM_BUSQUEDA_BINARIA",
    "RUTA_ASM_MULTIPLICACION_MATRICES",
    "BASE_VEC_A",
    "BASE_VEC_B",
    "BASE_VEC_RES",
    "BASE_MAT_A",
    "BASE_MAT_B",
    "BASE_MAT_C",
    "ejecutar_merge_sort",
    "ejecutar_producto_punto",
    "ejecutar_busqueda_binaria",
    "ejecutar_multiplicacion_matrices",
    "ejecutar_matriz_por_vector",
]
