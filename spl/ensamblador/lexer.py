"""
Lexer del Ensamblador SPL de Enigma-64 usando PLY (Python Lex-Yacc).

Reconoce mnemonicos, registros, directivas, etiquetas, literales numericos
(decimal, hexadecimal, binario y punto flotante), separadores y operadores.
Ignora comentarios ';' y espacios, lleva el conteo de lineas y reporta los
errores lexicos con su linea y columna sin detener el analisis.
"""

import re
from dataclasses import dataclass

import ply.lex as lex
from ply.lex import TOKEN


# Vocabulario del ensamblador

# Las 41 instrucciones del ISA (tabla _INSTRUCTIONS de enigma64/cpu.py)
MNEMONICOS = frozenset({
    # Control
    'HLT',
    # Aritmetica entera
    'ADD', 'SUB', 'MUL', 'DIV', 'ADDI', 'SUBI', 'INC', 'DEC',
    # Logica, corrimientos y comparacion
    'AND', 'OR', 'XOR', 'NOT', 'SHL', 'SHR', 'ASR', 'CMP',
    # Memoria
    'LOAD', 'STORE', 'LDB', 'STB',
    # Saltos
    'JMP', 'JZ', 'JNZ', 'JC', 'JNC', 'JN', 'JP', 'JV', 'JNV', 'JMPR',
    # Subrutinas y pila
    'CALL', 'CALLR', 'RET', 'PUSH', 'POP', 'ENTER', 'LEAVE',
    # Interrupciones
    'EI', 'DI', 'IRET',
})

# Registros codificados en 4 bits (enigma64/registros.py) y alias por rol
REGISTROS = frozenset({
    'R0', 'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'PC', 'SR',
    'RV', 'SP', 'BP',
})

DIRECTIVAS = frozenset({'.data', '.text', '.org', '.word', '.byte'})

# Categorias tras las cuales un '-' es el operador resta y no el signo de un
# literal: en [BP-8] el '-' resta, en ADDI R1, R0, -8 el '-' es signo.
_OPERANDOS = frozenset({
    'REGISTRO', 'ETIQUETA_REF', 'ENTERO_DEC', 'ENTERO_HEX', 'ENTERO_BIN',
    'FLOTANTE', 'CORCHETE_DER', 'PARENTESIS_DER',
})

_MIN_64 = -(1 << 63)          # menor entero con signo de 64 bits
_MAX_64 = (1 << 64) - 1       # mayor entero sin signo de 64 bits


# Definiciones regulares

DIGITO = r'[0-9]'
HEX = r'[0-9a-fA-F]'
BIN = r'[01]'
LETRA = r'[a-zA-Z_]'
ID = LETRA + r'(?:' + LETRA + r'|' + DIGITO + r')*'
REGISTRO = r'(?i:' + '|'.join(sorted(REGISTROS)) + r')'
REGISTRO_INVALIDO = r'[rR]' + DIGITO + r'+'
SIGNO = r'-?'
FIN_NUM = r'(?![\w.])'        # un literal no puede ir pegado a letras, digitos o '.'
EXPONENTE = r'[eE][+-]?' + DIGITO + r'+'

ENTERO_HEX = SIGNO + r'0[xX]' + HEX + r'+' + FIN_NUM
ENTERO_BIN = SIGNO + r'0[bB]' + BIN + r'+' + FIN_NUM
FLOTANTE = (SIGNO + r'(?:' + DIGITO + r'+\.' + DIGITO + r'+(?:' + EXPONENTE + r')?'
            + r'|' + DIGITO + r'+' + EXPONENTE + r')' + FIN_NUM)
ENTERO_DEC = SIGNO + DIGITO + r'+' + FIN_NUM
NUMERO_MAL = SIGNO + DIGITO + r'[\w.]*'
DEF_ETIQUETA = ID + r'(?=[ \t]*:)'
DIRECTIVA = r'\.' + ID
COMENTARIO = r';[^\n]*'


@dataclass(frozen=True)
class ErrorLexico:
    linea: int
    columna: int
    lexema: str
    mensaje: str

    def __str__(self):
        return (f"ERROR LEXICO (linea {self.linea}, columna {self.columna}): "
                f"{self.mensaje}: '{self.lexema}'")


class EnsambladorLexer:
    """
    Tokenizador del lenguaje ensamblador de Enigma-64.

    Las reglas de funcion se prueban en el orden en que estan escritas, por eso
    los literales mas especificos van antes que los generales y la definicion
    de etiqueta va antes que el identificador.
    """

    tokens = (
        'MNEMONICO',
        'REGISTRO',
        'DIRECTIVA',
        'ETIQUETA_DEF',
        'ETIQUETA_REF',
        'ENTERO_DEC',
        'ENTERO_HEX',
        'ENTERO_BIN',
        'FLOTANTE',
        'COMA',
        'DOS_PUNTOS',
        'CORCHETE_IZQ',
        'CORCHETE_DER',
        'PARENTESIS_IZQ',
        'PARENTESIS_DER',
        'INMEDIATO',
        'MAS',
        'MENOS',
    )

    t_ignore = ' \t\r'

    # Comentarios y saltos de linea (no producen token)

    @TOKEN(COMENTARIO)
    def t_COMENTARIO(self, t):
        self.comentarios += 1

    def t_NUEVA_LINEA(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)
        self._ultimo_tipo = None

    # Literales numericos

    @TOKEN(ENTERO_HEX)
    def t_ENTERO_HEX(self, t):
        return self._literal_entero(t, 16)

    @TOKEN(ENTERO_BIN)
    def t_ENTERO_BIN(self, t):
        return self._literal_entero(t, 2)

    @TOKEN(FLOTANTE)
    def t_FLOTANTE(self, t):
        return self._separar_signo(t)

    @TOKEN(ENTERO_DEC)
    def t_ENTERO_DEC(self, t):
        return self._literal_entero(t, 10)

    # Digitos pegados a letras o puntos: 0b102, 0xG1, 12abc, 3., 1.2.3
    @TOKEN(NUMERO_MAL)
    def t_NUMERO_MAL(self, t):
        if self._separar_signo(t).type == 'MENOS':
            return t
        self._reportar(t, 'literal numerico mal formado')

    # Directivas, etiquetas, mnemonicos y registros

    @TOKEN(DIRECTIVA)
    def t_DIRECTIVA(self, t):
        if t.value.lower() not in DIRECTIVAS:
            self._reportar(t, 'directiva desconocida')
            return None
        return t

    @TOKEN(DEF_ETIQUETA)
    def t_ETIQUETA_DEF(self, t):
        tipo = self._clasificar_palabra(t)
        if tipo is None:
            return None
        if tipo != 'ETIQUETA_REF':
            self._reportar(t, 'palabra reservada usada como etiqueta')
            return None
        return t

    # Una sola regla para palabras: la palabra completa se busca en las tablas
    # de reservadas, asi 'ADDR' queda como etiqueta y no como ADD seguido de R.
    @TOKEN(ID)
    def t_ID(self, t):
        tipo = self._clasificar_palabra(t)
        if tipo is None:
            return None
        t.type = tipo
        return t

    # Separadores y operadores

    t_COMA = r','
    t_DOS_PUNTOS = r':'
    t_CORCHETE_IZQ = r'\['
    t_CORCHETE_DER = r'\]'
    t_PARENTESIS_IZQ = r'\('
    t_PARENTESIS_DER = r'\)'
    t_INMEDIATO = r'\#'
    t_MAS = r'\+'
    t_MENOS = r'-'

    def t_error(self, t):
        t.value = t.value[0]
        self._reportar(t, 'caracter no valido')
        t.lexer.skip(1)

    # Utilidades de las reglas

    def _separar_signo(self, t):
        """Si el '-' sigue a un operando es una resta: emite MENOS y deja el numero para el siguiente token."""
        if t.value.startswith('-') and self._ultimo_tipo in _OPERANDOS:
            t.type = 'MENOS'
            t.value = '-'
            t.lexer.lexpos = t.lexpos + 1
        return t

    def _clasificar_palabra(self, t):
        """Categoria de una palabra sin distinguir mayusculas; None si es un registro inexistente."""
        if t.value.upper() in MNEMONICOS:
            return 'MNEMONICO'
        if re.fullmatch(REGISTRO, t.value):
            return 'REGISTRO'
        if re.fullmatch(REGISTRO_INVALIDO, t.value):
            self._reportar(t, 'registro inexistente (solo R0..R7)')
            return None
        return 'ETIQUETA_REF'

    def _literal_entero(self, t, base):
        t = self._separar_signo(t)
        if t.type == 'MENOS':
            return t
        digitos = t.value.lstrip('-')
        valor = int(digitos if base == 10 else digitos[2:], base)
        if t.value.startswith('-'):
            valor = -valor
        if not _MIN_64 <= valor <= _MAX_64:
            self._reportar(t, 'literal fuera del rango de 64 bits')
            return None
        return t

    def _columna(self, lexpos):
        return lexpos - self.lexer.lexdata.rfind('\n', 0, lexpos)

    def _reportar(self, t, mensaje):
        error = ErrorLexico(t.lexer.lineno, self._columna(t.lexpos), t.value, mensaje)
        self.errores.append(error)
        if self.al_error:
            self.al_error(error)

    # API publica

    def __init__(self, al_error=None):
        """al_error: funcion opcional que recibe cada ErrorLexico en cuanto ocurre."""
        self.al_error = al_error
        self.lexer = lex.lex(object=self, optimize=0, debug=False)
        self.input('')

    def input(self, texto: str):
        self.errores = []
        self.comentarios = 0
        self._ultimo_tipo = None
        self.lexer.lineno = 1
        self.lexer.input(texto)

    def token(self):
        tok = self.lexer.token()
        if tok is not None:
            tok.columna = self._columna(tok.lexpos)
            self._ultimo_tipo = tok.type
        return tok

    def __iter__(self):
        return iter(self.token, None)

    def tokenizar(self, texto: str):
        """Devuelve (lista de tokens, lista de ErrorLexico) del texto completo."""
        self.input(texto)
        return list(self), list(self.errores)
