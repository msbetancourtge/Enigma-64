"""
Enlazador del modulo Enlazador-Cargador de Enigma-64 (Noctua Systems).

  * objeto: analisis de modulos objeto reubicables (.obj): cabecera, encabezados
    de seccion, tablas de exportacion e importacion y marcas de reubicacion.
  * enlace: asignacion de direcciones, tabla global de simbolos, resolucion de
    importaciones y aplicacion de las marcas sobre la imagen de memoria.

    from enigma64.enlazador import EnlazadorEnigma, analizar_objeto

    modulo = analizar_objeto("principal.obj")
    print(modulo.informe())

    resultado = EnlazadorEnigma(["principal.obj", "libmat.obj"]).enlazar(0x00200000)
    cargador.cargar_binario(resultado.binario)

Linea de comandos:  python -m enigma64.enlazador modulo.obj [...] [-o salida.e64]
"""

from .enlace import (
    LIMITE_HI16,
    DesbordamientoReubicacion,
    EnlazadorEnigma,
    ResultadoEnlace,
    SimboloDuplicado,
    SimboloNoDefinido,
    UbicacionSeccion,
    calcular_parche,
)
from .objeto import (
    ALINEACION_MAXIMA,
    ANCHO_REUBICACION,
    CLASE_CODIGO,
    CLASE_DATOS,
    CLASE_RESERVA,
    FLAG_OBJ_ENTRADA,
    LIGADURA_GLOBAL,
    LIGADURA_LOCAL,
    MAQUINA_ENIGMA64,
    NOMBRE_REUBICACION,
    PERM_EJECUCION,
    PERM_ESCRITURA,
    PERM_LECTURA,
    REUB_ABS32,
    REUB_ABS64,
    REUB_HI16,
    REUB_LO16,
    REUB_REL16,
    SECCION_ABSOLUTA,
    SECCION_BITS,
    SECCION_INDEFINIDA,
    SECCION_VACIA,
    SIMBOLO_DATO,
    SIMBOLO_FUNCION,
    SIMBOLO_SIN_TIPO,
    TAM_CABECERA_OBJ,
    TAM_REUBICACION,
    TAM_SECCION,
    TAM_SIMBOLO,
    VERSION_OBJETO,
    CabeceraObjeto,
    ErrorEnlazador,
    MarcaReubicacion,
    ModuloObjeto,
    ObjetoInvalido,
    SeccionObjeto,
    SimboloObjeto,
    analizar_objeto,
    texto_permisos,
)

__all__ = [
    # Analisis de modulos objeto (.obj)
    "ModuloObjeto",
    "SeccionObjeto",
    "SimboloObjeto",
    "MarcaReubicacion",
    "CabeceraObjeto",
    "analizar_objeto",
    "texto_permisos",
    # Enlace
    "EnlazadorEnigma",
    "ResultadoEnlace",
    "UbicacionSeccion",
    "calcular_parche",
    "LIMITE_HI16",
    # Excepciones
    "ErrorEnlazador",
    "ObjetoInvalido",
    "SimboloNoDefinido",
    "SimboloDuplicado",
    "DesbordamientoReubicacion",
    # Constantes del formato
    "VERSION_OBJETO",
    "MAQUINA_ENIGMA64",
    "FLAG_OBJ_ENTRADA",
    "TAM_CABECERA_OBJ",
    "TAM_SECCION",
    "TAM_SIMBOLO",
    "TAM_REUBICACION",
    "SECCION_BITS",
    "SECCION_VACIA",
    "SECCION_ABSOLUTA",
    "SECCION_INDEFINIDA",
    "CLASE_CODIGO",
    "CLASE_DATOS",
    "CLASE_RESERVA",
    "PERM_LECTURA",
    "PERM_ESCRITURA",
    "PERM_EJECUCION",
    "ALINEACION_MAXIMA",
    "LIGADURA_LOCAL",
    "LIGADURA_GLOBAL",
    "SIMBOLO_SIN_TIPO",
    "SIMBOLO_FUNCION",
    "SIMBOLO_DATO",
    "REUB_ABS64",
    "REUB_ABS32",
    "REUB_REL16",
    "REUB_HI16",
    "REUB_LO16",
    "ANCHO_REUBICACION",
    "NOMBRE_REUBICACION",
]
