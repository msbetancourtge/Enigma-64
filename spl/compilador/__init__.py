"""
Módulo del Compilador SPL (Simple Programming Language) para Enigma-64.

Exporta:
- Analizador léxico base, vocabulario y categorías del compilador (Integrante 4).
- Tablas de símbolos, literales y des-escape determinista (Integrante 6).
"""

from spl.compilador.tablas import (
    TipoNumero,
    EntradaID,
    EntradaNum,
    EntradaString,
    TablaID,
    TablaNum,
    TablaString,
    GestorTablasSimbolos,
    desescapar_cadena,
)

from spl.compilador.lexer import (
    CompiladorLexer,
    ErrorLexico,
    PALABRAS_RESERVADAS,
    PALABRAS_RESERVADAS_CONTROL,
    PALABRAS_RESERVADAS_TIPOS,
    PALABRAS_RESERVADAS_TDA,
    SUBCODIGOS_CONTROL,
    SUBCODIGOS_TIPOS,
    SUBCODIGOS_TDA,
    CAT_PALABRA_RESERVADA,
    CAT_TIPO_PRIMITIVO,
    CAT_TIPO_ABSTRACTO,
    CAT_IDENTIFICADOR,
    CAT_CONSTANTE_NUMERICA,
    CAT_CADENA_LITERAL,
    CAT_OPERADOR_RELACIONAL,
    CAT_OPERADOR_ARITMETICO,
    CAT_OPERADOR_LOGICO,
    CAT_OPERADOR_ASIGNACION,
    CAT_DELIMITADOR,
    obtener_categoria_y_subcodigo,
)

__all__ = [
    # Tablas de Símbolos & Literales (Integrante 6)
    "TipoNumero",
    "EntradaID",
    "EntradaNum",
    "EntradaString",
    "TablaID",
    "TablaNum",
    "TablaString",
    "GestorTablasSimbolos",
    "desescapar_cadena",
    # Analizador Léxico & Vocabulario (Integrante 4)
    "CompiladorLexer",
    "ErrorLexico",
    "PALABRAS_RESERVADAS",
    "PALABRAS_RESERVADAS_CONTROL",
    "PALABRAS_RESERVADAS_TIPOS",
    "PALABRAS_RESERVADAS_TDA",
    "SUBCODIGOS_CONTROL",
    "SUBCODIGOS_TIPOS",
    "SUBCODIGOS_TDA",
    "CAT_PALABRA_RESERVADA",
    "CAT_TIPO_PRIMITIVO",
    "CAT_TIPO_ABSTRACTO",
    "CAT_IDENTIFICADOR",
    "CAT_CONSTANTE_NUMERICA",
    "CAT_CADENA_LITERAL",
    "CAT_OPERADOR_RELACIONAL",
    "CAT_OPERADOR_ARITMETICO",
    "CAT_OPERADOR_LOGICO",
    "CAT_OPERADOR_ASIGNACION",
    "CAT_DELIMITADOR",
    "obtener_categoria_y_subcodigo",
]
