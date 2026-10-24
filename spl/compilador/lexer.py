"""
Lexer del Compilador SPL (Simple Programming Language) para Enigma-64.
Fase 1: Análisis Léxico con PLY (Python Lex-Yacc).

Responsabilidad: Integrante 4
- Diseño del vocabulario y categorías base del lenguaje de alto nivel.
- Especificación formal de palabras reservadas (control de flujo, iteración, funciones).
- Tipos primitivos (int de 64 bits, float IEEE 754 de 64 bits, char, void, bool, const).
- Tipos de Datos Abstractos (TDA / struct, typedef, sizeof).
- Delimitadores estructurales para arreglos unidimensionales y matrices multidimensionales.
- Identificadores (ID) con desambiguación y deduplicación mediante GestorTablasSimbolos.
- Soporte base extensible para operadores y literales (Integrante 5 y 6).

Responsabilidad: Integrante 5
- Expresiones regulares de operadores aritméticos (+, -, *, /, %), lógicos
  (&&, ||, !) y relacionales (==, !=, <, <=, >, >=) con subcódigo propio.
- Literales enteros en base 10 y base 16 (0x...) acotados a 64 bits.
- Literales flotantes en punto fijo (3.14, .5, 5.) y notación científica
  (1e10, 2.5E-3), acotados al rango de IEEE 754 binary64.
- Cadenas de texto con secuencias de escape validadas (\\n, \\t, \\r, \\0,
  \\\\, \\", \\') y detección de cadenas sin cerrar.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

import ply.lex as lex
from ply.lex import TOKEN

from spl.compilador.tablas import GestorTablasSimbolos


# ---------------------------------------------------------------------------
# 1. Tabla Maestra de Códigos de Categoría y Subcódigos (SPL Enigma-64)
# ---------------------------------------------------------------------------

# Códigos numéricos de categoría según el estándar del proyecto
CAT_PALABRA_RESERVADA: int = 100     # KW (if, else, while, etc.)
CAT_TIPO_PRIMITIVO: int = 110        # TYPE (int, float, char, void, bool)
CAT_TIPO_ABSTRACTO: int = 120        # TDA / STRUCT (struct, tda, typedef, sizeof)
CAT_IDENTIFICADOR: int = 150         # ID (variables, funciones, tipos)
CAT_CONSTANTE_NUMERICA: int = 160    # NUMBER (enteros 64-bit y flotantes IEEE 754)
CAT_CADENA_LITERAL: int = 170        # STRING ("...")
CAT_OPERADOR_RELACIONAL: int = 200   # RELOP (==, !=, <, <=, >, >=)
CAT_OPERADOR_ARITMETICO: int = 210   # ARITH (+, -, *, /, %)
CAT_OPERADOR_LOGICO: int = 220       # LOGOP (&&, ||, !)
CAT_OPERADOR_ASIGNACION: int = 230   # ASSIGN (=)
CAT_DELIMITADOR: int = 240           # DELIM ([, ], {, }, (, ), ;, ,, :, ., ->)

# Diccionario unificado de palabras reservadas del lenguaje de alto nivel
# Mapea el lexema exacto (en minúsculas) al nombre canónico del token.
PALABRAS_RESERVADAS_CONTROL: Dict[str, str] = {
    # Estructuras de selección
    "if": "IF",
    "then": "THEN",
    "else": "ELSE",
    "switch": "SWITCH",
    "case": "CASE",
    "default": "DEFAULT",
    # Estructuras de iteración
    "while": "WHILE",
    "do": "DO",
    "for": "FOR",
    "continue": "CONTINUE",
    # Secuencia y subrutinas
    "function": "FUNCTION",
    "return": "RETURN",
    "break": "BREAK",
}

PALABRAS_RESERVADAS_TIPOS: Dict[str, str] = {
    # Tipos primitivos alineados a la arquitectura de 64 bits de Enigma-64
    "int": "INT_TYPE",        # Entero con signo de 64 bits (complemento a dos)
    "float": "FLOAT_TYPE",    # Punto flotante de 64 bits (IEEE 754 Binary64)
    "void": "VOID_TYPE",      # Tipo nulo / retorno de procedimientos
    "char": "CHAR_TYPE",      # Carácter de 8 bits / byte direccionable
    "bool": "BOOL_TYPE",      # Tipo booleano (1 = verdadero, 0 = falso)
    "const": "CONST",         # Calificador de inmutabilidad
}

PALABRAS_RESERVADAS_TDA: Dict[str, str] = {
    # Tipos de Datos Abstractos y agregados
    "struct": "STRUCT",       # Declaración de estructura compuesta
    "tda": "TDA",             # Sinónimo explícito de Tipo de Dato Abstracto
    "typedef": "TYPEDEF",     # Alias de tipos
    "sizeof": "SIZEOF",       # Tamaño en bytes del tipo o variable
}

# Diccionario maestro de palabras reservadas
PALABRAS_RESERVADAS: Dict[str, str] = {
    **PALABRAS_RESERVADAS_CONTROL,
    **PALABRAS_RESERVADAS_TIPOS,
    **PALABRAS_RESERVADAS_TDA,
}

# Subcódigos ordinales para representación canónica en yylval
SUBCODIGOS_CONTROL: Dict[str, int] = {
    "IF": 1, "THEN": 2, "ELSE": 3, "SWITCH": 4, "CASE": 5, "DEFAULT": 6,
    "WHILE": 7, "DO": 8, "FOR": 9, "CONTINUE": 10,
    "FUNCTION": 11, "RETURN": 12, "BREAK": 13,
}

SUBCODIGOS_TIPOS: Dict[str, int] = {
    "INT_TYPE": 1, "FLOAT_TYPE": 2, "VOID_TYPE": 3,
    "CHAR_TYPE": 4, "BOOL_TYPE": 5, "CONST": 6,
}

SUBCODIGOS_TDA: Dict[str, int] = {
    "STRUCT": 1, "TDA": 2, "TYPEDEF": 3, "SIZEOF": 4,
}

# Operadores (Integrante 5): lexema exacto -> nombre canónico del token
OPERADORES_RELACIONALES: Dict[str, str] = {
    "==": "IGUAL", "!=": "DISTINTO",
    "<": "MENOR", "<=": "MENOR_IGUAL",
    ">": "MAYOR", ">=": "MAYOR_IGUAL",
}

OPERADORES_ARITMETICOS: Dict[str, str] = {
    "+": "MAS", "-": "MENOS", "*": "POR", "/": "DIV", "%": "MOD",
}

OPERADORES_LOGICOS: Dict[str, str] = {
    "&&": "AND_LOGICO", "||": "OR_LOGICO", "!": "NOT_LOGICO",
}

OPERADORES: Dict[str, str] = {
    **OPERADORES_RELACIONALES,
    **OPERADORES_ARITMETICOS,
    **OPERADORES_LOGICOS,
}

# Subcódigos de operadores (atributo del token, al estilo RELOP de FLEX)
SUBCODIGOS_RELACIONALES: Dict[str, int] = {
    "IGUAL": 1, "DISTINTO": 2, "MENOR": 3,
    "MENOR_IGUAL": 4, "MAYOR": 5, "MAYOR_IGUAL": 6,
}

SUBCODIGOS_ARITMETICOS: Dict[str, int] = {
    "MAS": 1, "MENOS": 2, "POR": 3, "DIV": 4, "MOD": 5,
}

SUBCODIGOS_LOGICOS: Dict[str, int] = {
    "AND_LOGICO": 1, "OR_LOGICO": 2, "NOT_LOGICO": 3,
}

# Subcódigos de literales numéricos (alineados con TipoNumero de tablas.py)
SUB_NUM_ENTERO_DEC: int = 1
SUB_NUM_ENTERO_HEX: int = 2
SUB_NUM_ENTERO_BIN: int = 3
SUB_NUM_REAL_DECIMAL: int = 4
SUB_NUM_REAL_CIENTIFICO: int = 5

# Subcódigos de literales de texto
SUB_CADENA: int = 1
SUB_CARACTER: int = 2

# Límites de representación de Enigma-64
ENTERO_DEC_MAXIMO: int = 2**63 - 1        # INT64_MAX (el signo es el operador unario '-')
ENTERO_PATRON_MAXIMO: int = 2**64 - 1     # 0xFFFFFFFFFFFFFFFF (patrón de 64 bits)

# Secuencias de escape admitidas (las mismas que resuelve desescapar_cadena)
ESCAPES_VALIDOS: str = "ntr0\\\"'"


def obtener_categoria_y_subcodigo(tipo_token: str) -> Tuple[int, int]:
    """Retorna la tupla (codigo_categoria, subcodigo) para un token formal."""
    if tipo_token in SUBCODIGOS_CONTROL:
        return CAT_PALABRA_RESERVADA, SUBCODIGOS_CONTROL[tipo_token]
    if tipo_token in SUBCODIGOS_TIPOS:
        return CAT_TIPO_PRIMITIVO, SUBCODIGOS_TIPOS[tipo_token]
    if tipo_token in SUBCODIGOS_TDA:
        return CAT_TIPO_ABSTRACTO, SUBCODIGOS_TDA[tipo_token]
    if tipo_token == "ID":
        return CAT_IDENTIFICADOR, 1
    if tipo_token == "ENTERO_DEC":
        return CAT_CONSTANTE_NUMERICA, SUB_NUM_ENTERO_DEC
    if tipo_token == "ENTERO_HEX":
        return CAT_CONSTANTE_NUMERICA, SUB_NUM_ENTERO_HEX
    if tipo_token == "ENTERO_BIN":
        return CAT_CONSTANTE_NUMERICA, SUB_NUM_ENTERO_BIN
    if tipo_token == "FLOTANTE":
        return CAT_CONSTANTE_NUMERICA, SUB_NUM_REAL_DECIMAL
    if tipo_token == "NUMBER":
        return CAT_CONSTANTE_NUMERICA, 1
    if tipo_token == "STRING":
        return CAT_CADENA_LITERAL, SUB_CADENA
    if tipo_token == "CHAR_LITERAL":
        return CAT_CADENA_LITERAL, SUB_CARACTER
    if tipo_token in SUBCODIGOS_RELACIONALES:
        return CAT_OPERADOR_RELACIONAL, SUBCODIGOS_RELACIONALES[tipo_token]
    if tipo_token in SUBCODIGOS_ARITMETICOS:
        return CAT_OPERADOR_ARITMETICO, SUBCODIGOS_ARITMETICOS[tipo_token]
    if tipo_token in SUBCODIGOS_LOGICOS:
        return CAT_OPERADOR_LOGICO, SUBCODIGOS_LOGICOS[tipo_token]
    if tipo_token == "ASIGNAR":
        return CAT_OPERADOR_ASIGNACION, 1
    return CAT_DELIMITADOR, 1


# ---------------------------------------------------------------------------
# 2. Definiciones Regulares Formales
# ---------------------------------------------------------------------------

DIGITO = r"[0-9]"
HEX = r"[0-9a-fA-F]"
BIN = r"[01]"
LETRA = r"[a-zA-Z_]"
FIN_NUM = r"(?![\w.])"
EXPONENTE = r"[eE][+-]?" + DIGITO + r"+"

# Expresiones para identificadores y literales
PATRON_ID = LETRA + r"(?:" + LETRA + r"|" + DIGITO + r")*"
PATRON_ENTERO_HEX = r"0[xX]" + HEX + r"+" + FIN_NUM
PATRON_ENTERO_BIN = r"0[bB]" + BIN + r"+" + FIN_NUM
# Mantisa en punto fijo: 3.14, 5. o .5 (al menos un dígito a algún lado del punto)
MANTISA = r"(?:" + DIGITO + r"+\." + DIGITO + r"*|\." + DIGITO + r"+)"
PATRON_FLOTANTE = (
    r"(?:" + MANTISA + r"(?:" + EXPONENTE + r")?"
    r"|" + DIGITO + r"+" + EXPONENTE + r")" + FIN_NUM
)
PATRON_ENTERO_DEC = DIGITO + r"+" + FIN_NUM
# Exponente con signo pero sin dígitos: 1e+, 2.5E-
PATRON_EXPONENTE_INCOMPLETO = (
    r"(?:" + MANTISA + r"|" + DIGITO + r"+)[eE][+-](?!" + DIGITO + r")"
)

# Cadenas y caracteres: el escape válido se especifica en la regla aceptora y
# las variantes con escapes desconocidos o sin cierre se capturan aparte.
ESCAPE = r"\\[ntr0\\\"']"
ESCAPE_CUALQUIERA = r"\\[^\n\r]"
PATRON_CADENA = r'"(?:[^"\\\n\r]|' + ESCAPE + r')*"'
PATRON_CADENA_ESCAPE_INVALIDO = r'"(?:[^"\\\n\r]|' + ESCAPE_CUALQUIERA + r')*"'
PATRON_CADENA_SIN_CERRAR = r'"(?:[^"\\\n\r]|' + ESCAPE_CUALQUIERA + r')*\\?'
PATRON_CARACTER = r"'(?:[^'\\\n\r]|" + ESCAPE + r")'"
PATRON_CARACTER_MAL = r"'(?:[^'\\\n\r]|" + ESCAPE_CUALQUIERA + r")*'?"

PATRON_NUMERO_MAL = r"(?:" + DIGITO + r"|\." + DIGITO + r")[\w.]*"
# '&' o '|' aislados (no forman '&&' ni '||')
PATRON_OPERADOR_INCOMPLETO = r"&(?!&)|\|(?!\|)"


def _primer_escape_invalido(lexema: str) -> str:
    """Devuelve la primera secuencia de escape no admitida de una cadena."""
    i = 1
    while i < len(lexema) - 1:
        if lexema[i] == "\\":
            if lexema[i + 1] not in ESCAPES_VALIDOS:
                return lexema[i:i + 2]
            i += 2
        else:
            i += 1
    return ""


def _mantisa_no_nula(lexema: str) -> bool:
    """Indica si la mantisa de un literal flotante tiene algún dígito distinto de cero."""
    mantisa = re.split(r"[eE]", lexema, maxsplit=1)[0]
    return any(c in "123456789" for c in mantisa)


# ---------------------------------------------------------------------------
# 3. Estructuras de Datos de Errores y Tokens
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ErrorLexico:
    """Representa un error léxico reportado por el compilador."""
    linea: int
    columna: int
    lexema: str
    mensaje: str

    def __str__(self) -> str:
        return (
            f"ERROR LEXICO (linea {self.linea}, columna {self.columna}): "
            f"{self.mensaje}: '{self.lexema}'"
        )


# ---------------------------------------------------------------------------
# 4. Analizador Léxico del Compilador (CompiladorLexer)
# ---------------------------------------------------------------------------

class CompiladorLexer:
    """
    Tokenizador del lenguaje de alto nivel para Enigma-64.

    Implementa el vocabulario base (Integrante 4), la integración con las
    tablas de símbolos y literales (Integrante 6) y los operadores/literales
    extensibles (Integrante 5).
    """

    # Categorías base de palabras reservadas e identificadores (Integrante 4)
    TOKENS_BASE = (
        "ID",
        # Control de flujo y selección
        "IF", "THEN", "ELSE", "SWITCH", "CASE", "DEFAULT",
        # Iteración
        "WHILE", "DO", "FOR", "CONTINUE",
        # Funciones y secuencia
        "FUNCTION", "RETURN", "BREAK",
        # Tipos primitivos
        "INT_TYPE", "FLOAT_TYPE", "VOID_TYPE", "CHAR_TYPE", "BOOL_TYPE", "CONST",
        # Tipos de Datos Abstractos
        "STRUCT", "TDA", "TYPEDEF", "SIZEOF",
        # Delimitadores de arreglos, matrices, bloques y expresiones
        "CORCHETE_IZQ",     # [ para arr[i] y matrix[r][c]
        "CORCHETE_DER",     # ]
        "LLAVE_IZQ",        # { para bloques imperativos y cuerpos de TDA
        "LLAVE_DER",        # }
        "PARENTESIS_IZQ",   # ( para funciones y expresiones
        "PARENTESIS_DER",   # )
        "PUNTO_Y_COMA",     # ; fin de sentencia
        "COMA",             # , separador de argumentos, campos y dimensiones
        "DOS_PUNTOS",       # : en switch/case y etiquetas
        "PUNTO",            # . acceso a campos de struct/TDA (ej. p.x)
        "FLECHA",           # -> acceso a campos de TDA por puntero (ej. p->x)
        "ASIGNAR",          # = operador de asignación
    )

    # Operadores y literales (Integrante 5 y 6)
    TOKENS_OPERADORES_LITERALES = (
        # Operadores relacionales
        "IGUAL",            # ==
        "DISTINTO",         # !=
        "MENOR_IGUAL",      # <=
        "MAYOR_IGUAL",      # >=
        "MENOR",            # <
        "MAYOR",            # >
        # Operadores aritméticos
        "MAS",              # +
        "MENOS",            # -
        "POR",              # *
        "DIV",              # /
        "MOD",              # %
        # Operadores lógicos
        "AND_LOGICO",       # &&
        "OR_LOGICO",        # ||
        "NOT_LOGICO",       # !
        # Literales
        "ENTERO_HEX",
        "ENTERO_BIN",
        "FLOTANTE",
        "ENTERO_DEC",
        "STRING",
        "CHAR_LITERAL",
    )

    tokens = TOKENS_BASE + TOKENS_OPERADORES_LITERALES

    # Caracteres ignorados: espacios en blanco, tabulaciones y retorno de carro
    t_ignore = " \t\r"

    # -----------------------------------------------------------------------
    # Reglas para Comentarios y Saltos de Línea
    # -----------------------------------------------------------------------

    def t_COMENTARIO_LINEA(self, t):
        r"//[^\n]*"
        self.comentarios += 1

    def t_COMENTARIO_BLOQUE(self, t):
        r"/\*[\s\S]*?\*/"
        self.comentarios += 1
        # Contar saltos de línea dentro del bloque de comentario
        t.lexer.lineno += t.value.count("\n")

    def t_NUEVA_LINEA(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    # -----------------------------------------------------------------------
    # Operadores Multicarácter y Delimitadores Compuestos
    # (Deben preceder a los operadores simples de 1 carácter)
    # -----------------------------------------------------------------------

    t_FLECHA = r"->"
    t_IGUAL = r"=="
    t_DISTINTO = r"!="
    t_MENOR_IGUAL = r"<="
    t_MAYOR_IGUAL = r">="
    t_AND_LOGICO = r"&&"
    t_OR_LOGICO = r"\|\|"

    # -----------------------------------------------------------------------
    # Delimitadores Estructurales (Arreglos, Matrices, Bloques y Puntuación)
    # -----------------------------------------------------------------------

    t_CORCHETE_IZQ = r"\["
    t_CORCHETE_DER = r"\]"
    t_LLAVE_IZQ = r"\{"
    t_LLAVE_DER = r"\}"
    t_PARENTESIS_IZQ = r"\("
    t_PARENTESIS_DER = r"\)"
    t_PUNTO_Y_COMA = r";"
    t_COMA = r","
    t_DOS_PUNTOS = r":"
    t_PUNTO = r"\."
    t_ASIGNAR = r"="

    # Operadores simples
    t_MAS = r"\+"
    t_MENOS = r"-"
    t_POR = r"\*"
    t_DIV = r"/"
    t_MOD = r"%"
    t_MENOR = r"<"
    t_MAYOR = r">"
    t_NOT_LOGICO = r"!"

    # -----------------------------------------------------------------------
    # Literales Numéricos y Cadenas (Integración con GestorTablasSimbolos)
    # -----------------------------------------------------------------------

    @TOKEN(PATRON_CADENA)
    def t_STRING(self, t):
        if self.tablas is not None:
            t.simbolo_idx = self.tablas.install_string(t.value)
        else:
            t.simbolo_idx = None
        t.categoria_codigo = CAT_CADENA_LITERAL
        t.subcodigo = SUB_CADENA
        return t

    @TOKEN(PATRON_CADENA_ESCAPE_INVALIDO)
    def t_CADENA_ESCAPE_INVALIDO(self, t):
        escape = _primer_escape_invalido(t.value)
        self._reportar(t, f"secuencia de escape no valida '{escape}' en cadena")

    @TOKEN(PATRON_CADENA_SIN_CERRAR)
    def t_CADENA_SIN_CERRAR(self, t):
        self._reportar(t, "cadena de texto sin cerrar antes del fin de linea")

    @TOKEN(PATRON_CARACTER)
    def t_CHAR_LITERAL(self, t):
        t.categoria_codigo = CAT_CADENA_LITERAL
        t.subcodigo = SUB_CARACTER
        return t

    @TOKEN(PATRON_CARACTER_MAL)
    def t_CARACTER_MAL(self, t):
        self._reportar(t, "literal de caracter mal formado")

    @TOKEN(PATRON_ENTERO_HEX)
    def t_ENTERO_HEX(self, t):
        if int(t.value, 16) > ENTERO_PATRON_MAXIMO:
            self._reportar(t, "literal hexadecimal excede los 64 bits de Enigma-64")
            return None
        return self._instalar_numero(t, SUB_NUM_ENTERO_HEX)

    @TOKEN(PATRON_ENTERO_BIN)
    def t_ENTERO_BIN(self, t):
        if int(t.value[2:], 2) > ENTERO_PATRON_MAXIMO:
            self._reportar(t, "literal binario excede los 64 bits de Enigma-64")
            return None
        return self._instalar_numero(t, SUB_NUM_ENTERO_BIN)

    @TOKEN(PATRON_FLOTANTE)
    def t_FLOTANTE(self, t):
        valor = float(t.value)
        if math.isinf(valor):
            self._reportar(t, "literal flotante desborda el rango de IEEE 754 binary64")
            return None
        if valor == 0.0 and _mantisa_no_nula(t.value):
            self._reportar(t, "literal flotante subdesborda a cero en IEEE 754 binary64")
            return None
        es_cientifico = "e" in t.value.lower()
        return self._instalar_numero(
            t, SUB_NUM_REAL_CIENTIFICO if es_cientifico else SUB_NUM_REAL_DECIMAL
        )

    @TOKEN(PATRON_ENTERO_DEC)
    def t_ENTERO_DEC(self, t):
        if int(t.value) > ENTERO_DEC_MAXIMO:
            self._reportar(t, "literal entero excede el rango de 64 bits con signo")
            return None
        return self._instalar_numero(t, SUB_NUM_ENTERO_DEC)

    @TOKEN(PATRON_EXPONENTE_INCOMPLETO)
    def t_EXPONENTE_INCOMPLETO(self, t):
        self._reportar(t, "exponente sin digitos en literal flotante")

    @TOKEN(PATRON_NUMERO_MAL)
    def t_NUMERO_MAL(self, t):
        self._reportar(t, "literal numerico mal formado")

    # -----------------------------------------------------------------------
    # Identificadores y Palabras Reservadas (Núcleo Integrante 4)
    # -----------------------------------------------------------------------

    @TOKEN(PATRON_ID)
    def t_ID(self, t):
        """
        Regla unificada para identificadores y palabras reservadas.
        Aplica coincidencia contra PALABRAS_RESERVADAS:
          - Si coincide: muta el tipo al token formal de la palabra clave.
          - Si no coincide: se clasifica como 'ID' y se registra en tablaID.
        """
        val_lower = t.value.lower()
        if val_lower in PALABRAS_RESERVADAS:
            t.type = PALABRAS_RESERVADAS[val_lower]
            cat, sub = obtener_categoria_y_subcodigo(t.type)
            t.categoria_codigo = cat
            t.subcodigo = sub
            t.simbolo_idx = None
        else:
            t.type = "ID"
            t.categoria_codigo = CAT_IDENTIFICADOR
            t.subcodigo = 1
            if self.tablas is not None:
                t.simbolo_idx = self.tablas.install_id(t.value)
            else:
                t.simbolo_idx = None
        return t

    @TOKEN(PATRON_OPERADOR_INCOMPLETO)
    def t_OPERADOR_INCOMPLETO(self, t):
        self._reportar(t, "operador logico incompleto (se esperaba '&&' o '||')")

    # -----------------------------------------------------------------------
    # Manejo de Errores Léxicos
    # -----------------------------------------------------------------------

    def t_error(self, t):
        caracter = t.value[0]
        t.value = caracter
        self._reportar(t, "caracter no valido en lenguaje SPL")
        t.lexer.skip(1)

    # -----------------------------------------------------------------------
    # Métodos Auxiliares Internos
    # -----------------------------------------------------------------------

    def _columna(self, lexpos: int) -> int:
        """Calcula la columna (base 1) a partir de la posición absoluta."""
        ultima_nl = self.lexer.lexdata.rfind("\n", 0, lexpos)
        return lexpos - ultima_nl

    def _instalar_numero(self, t, subcodigo: int):
        """Registra el literal numérico en tablaNum y fija su categoría."""
        if self.tablas is not None:
            t.simbolo_idx = self.tablas.install_num(t.value)
        else:
            t.simbolo_idx = None
        t.categoria_codigo = CAT_CONSTANTE_NUMERICA
        t.subcodigo = subcodigo
        return t

    def _reportar(self, t, mensaje: str) -> None:
        """Registra un error léxico conservando posición y llamando al callback."""
        col = self._columna(t.lexpos)
        error = ErrorLexico(
            linea=t.lexer.lineno,
            columna=col,
            lexema=t.value,
            mensaje=mensaje,
        )
        self.errores.append(error)
        if self.al_error:
            self.al_error(error)

    # -----------------------------------------------------------------------
    # API Pública del Lexer
    # -----------------------------------------------------------------------

    def __init__(
        self,
        al_error: Optional[Callable[[ErrorLexico], None]] = None,
        tablas: Optional[GestorTablasSimbolos] = None,
    ) -> None:
        """
        Inicializa el analizador léxico del compilador.

        :param al_error: Función callback opcional que recibe cada ErrorLexico.
        :param tablas: Instancia compartida de GestorTablasSimbolos. Si no se
                       especifica, se instancia una nueva automáticamente.
        """
        self.al_error = al_error
        self.tablas = tablas if tablas is not None else GestorTablasSimbolos()
        self.errores: List[ErrorLexico] = []
        self.comentarios: int = 0
        self.lexer = lex.lex(object=self, optimize=0, debug=False)
        self.input("")

    def input(self, texto: str) -> None:
        """Carga una nueva cadena de texto para iniciar el análisis léxico."""
        self.errores = []
        self.comentarios = 0
        self.lexer.lineno = 1
        self.lexer.input(texto)

    def token(self) -> Optional[Any]:
        """Obtiene el siguiente token del flujo léxico."""
        tok = self.lexer.token()
        if tok is not None:
            tok.columna = self._columna(tok.lexpos)
            if not hasattr(tok, "categoria_codigo"):
                cat, sub = obtener_categoria_y_subcodigo(tok.type)
                tok.categoria_codigo = cat
                tok.subcodigo = sub
            if not hasattr(tok, "simbolo_idx"):
                tok.simbolo_idx = None
        return tok

    def __iter__(self):
        """Permite iterar directamente sobre el analizador léxico."""
        return iter(self.token, None)

    def tokenizar(self, texto: str) -> Tuple[List[Any], List[ErrorLexico]]:
        """
        Tokeniza un texto completo de una sola vez.

        :param texto: Código fuente SPL a procesar.
        :return: Tupla con (lista_tokens, lista_errores).
        """
        self.input(texto)
        return list(self), list(self.errores)
