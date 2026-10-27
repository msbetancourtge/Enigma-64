"""
Lexer del Preprocesador SPL usando PLY (Python Lex-Yacc).
Maneja estados para comentarios de bloque y directivas.
"""

import sys
import re
import ply.lex as lex

# Asegurar compatibilidad en entornos donde __file__ no está en sys.modules[__name__]
if hasattr(sys, "modules") and __name__ in sys.modules:
    mod = sys.modules[__name__]
    if not hasattr(mod, "__file__"):
        mod.__file__ = __file__


class PreprocesadorLexer:
    """
    Lexer con estados léxicos exclusivos para comentarios de bloque y líneas de directiva.
    """

    tokens = (
        # Directivas
        'DIRECTIVE_START',
        'DIR_DEFINE',
        'DIR_UNDEF',
        'DIR_INCLUDE',
        'DIR_IFDEF',
        'DIR_IFNDEF',
        'DIR_ELSE',
        'DIR_ENDIF',
        'DIR_PRAGMA',
        'DIR_HEADER_SYS',
        'DIR_HEADER_LOCAL',
        'DIR_IDENTIFIER',
        'DIR_NUMBER',
        'DIR_STRING',
        'DIR_CHAR',
        'DIR_WHITESPACE',
        'DIR_CONTINUE',
        'DIR_END',
        'DIR_OTHER',

        # Código normal
        'STRING',
        'CHAR',
        'NUMBER',
        'IDENTIFIER',
        'WHITESPACE',
        'COMMENT',
        'NEWLINE',
        'LINE_CONTINUATION',
        'OTHER',
    )

    states = (
        ('directive', 'exclusive'),
        ('blockcomment', 'exclusive'),
    )

    # Estado: INITIAL (Código normal)

    # Directivas al inicio de línea (posiblemente precedidas de espacios/tabulaciones)
    def t_DIRECTIVE_START(self, t):
        r'^[ \t]*\#'
        t.lexer.begin('directive')
        t.lexer.directive_tokens = []
        t.lexer.directive_start_line = t.lexer.lineno
        return t

    # Inicio de comentario de bloque
    def t_BLOCKCOMMENT_START(self, t):
        r'/\*'
        t.lexer.comment_prev_state = 'INITIAL'
        t.lexer.comment_start_line = t.lexer.lineno
        t.lexer.comment_newlines = 0
        t.lexer.begin('blockcomment')

    # Comentario de una sola línea //
    def t_LINE_COMMENT(self, t):
        r'//[^\r\n]*'
        t.type = 'COMMENT'
        t.value = ' '
        return t

    # Cadenas literales (sin sustitución dentro de cadenas)
    def t_STRING(self, t):
        r'\"([^\"\\\r\n]|\\.)*\"'
        return t

    # Caracteres literales (sin sustitución dentro de caracteres)
    def t_CHAR(self, t):
        r'\'([^\'\\\r\n]|\\.)*\''
        return t

    # Números (hexadecimal, binario, punto flotante, notación científica, enteros)
    def t_NUMBER(self, t):
        r'0[xX][0-9a-fA-F]+[uUlL]*|0[bB][01]+[uUlL]*|[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?[uUlL]*|\.[0-9]+([eE][+-]?[0-9]+)?[uUlL]*'
        return t

    # Continuación de línea en código normal
    def t_LINE_CONTINUATION(self, t):
        r'\\([ \t]*\r?\n)'
        t.lexer.lineno += 1
        t.value = ' '
        return t

    # Identificadores
    def t_IDENTIFIER(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_]*'
        return t

    # Espacios y tabulaciones en código normal
    def t_WHITESPACE(self, t):
        r'[ \t]+'
        return t

    # Salto de línea
    def t_NEWLINE(self, t):
        r'\r?\n'
        t.lexer.lineno += 1
        return t

    # Cualquier otro carácter (operadores, puntuación, ; de assembler, etc.)
    def t_OTHER(self, t):
        r'[^\r\n]'
        return t

    def t_error(self, t):
        t.lexer.skip(1)

    # Estado: blockcomment (Comentarios de bloque /* ... */)

    def t_blockcomment_END(self, t):
        r'\*/'
        prev = getattr(t.lexer, 'comment_prev_state', 'INITIAL')
        t.lexer.begin(prev)
        t.type = 'COMMENT'
        # Conservar los saltos de línea para no desalinear números de línea
        t.value = ' ' + ('\n' * t.lexer.comment_newlines)
        return t

    def t_blockcomment_NEWLINE(self, t):
        r'\r?\n'
        t.lexer.lineno += 1
        t.lexer.comment_newlines += 1

    def t_blockcomment_CONTENT(self, t):
        r'[^\r\n*]+|\*'
        pass

    def t_blockcomment_error(self, t):
        t.lexer.skip(1)

    # Estado: directive (Líneas de directiva)

    # Inicio de comentario de bloque dentro de directiva
    def t_directive_BLOCKCOMMENT_START(self, t):
        r'/\*'
        t.lexer.comment_prev_state = 'directive'
        t.lexer.comment_start_line = t.lexer.lineno
        t.lexer.comment_newlines = 0
        t.lexer.begin('blockcomment')

    # Comentario de una línea dentro de directiva
    def t_directive_LINE_COMMENT(self, t):
        r'//[^\r\n]*'
        t.type = 'DIR_WHITESPACE'
        t.value = ' '
        return t

    # Continuación de línea con \ dentro de directiva
    def t_directive_CONTINUE(self, t):
        r'\\([ \t]*\r?\n)'
        t.lexer.lineno += 1
        t.type = 'DIR_CONTINUE'
        t.value = ' '
        return t

    # Palabras clave de directivas
    def t_directive_KEYWORDS(self, t):
        r'\b(define|undef|include|ifdef|ifndef|else|endif|pragma)\b'
        name = t.value
        token_map = {
            'define': 'DIR_DEFINE',
            'undef': 'DIR_UNDEF',
            'include': 'DIR_INCLUDE',
            'ifdef': 'DIR_IFDEF',
            'ifndef': 'DIR_IFNDEF',
            'else': 'DIR_ELSE',
            'endif': 'DIR_ENDIF',
            'pragma': 'DIR_PRAGMA',
        }
        t.type = token_map[name]
        return t

    # Header de sistema <archivo> en directivas
    def t_directive_HEADER_SYS(self, t):
        r'<[^>\r\n]+>'
        t.type = 'DIR_HEADER_SYS'
        return t

    # Header local "archivo" o cadenas en directivas
    def t_directive_STRING_OR_HEADER(self, t):
        r'\"([^\"\\\r\n]|\\.)*\"'
        t.type = 'DIR_HEADER_LOCAL'
        return t

    def t_directive_CHAR(self, t):
        r'\'([^\'\\\r\n]|\\.)*\''
        t.type = 'DIR_CHAR'
        return t

    def t_directive_NUMBER(self, t):
        r'0[xX][0-9a-fA-F]+[uUlL]*|0[bB][01]+[uUlL]*|[0-9]+(\.[0-9]+)?([eE][+-]?[0-9]+)?[uUlL]*|\.[0-9]+([eE][+-]?[0-9]+)?[uUlL]*'
        t.type = 'DIR_NUMBER'
        return t

    def t_directive_IDENTIFIER(self, t):
        r'[a-zA-Z_][a-zA-Z0-9_]*'
        t.type = 'DIR_IDENTIFIER'
        return t

    def t_directive_WHITESPACE(self, t):
        r'[ \t]+'
        t.type = 'DIR_WHITESPACE'
        return t

    # Fin de directiva: salto de línea sin escapar
    def t_directive_DIR_END(self, t):
        r'\r?\n'
        t.lexer.lineno += 1
        t.lexer.begin('INITIAL')
        t.type = 'DIR_END'
        return t

    def t_directive_OTHER(self, t):
        r'[^\r\n]'
        t.type = 'DIR_OTHER'
        return t

    def t_directive_error(self, t):
        t.lexer.skip(1)

    def __init__(self):
        self.lexer = lex.lex(
            object=self,
            reflags=re.MULTILINE,
            optimize=0,
            debug=False,
        )

    def input(self, texto: str):
        self.lexer.lineno = 1
        self.lexer.comment_start_line = 1
        self.lexer.comment_newlines = 0
        self.lexer.comment_prev_state = 'INITIAL'
        self.lexer.begin('INITIAL')
        self.lexer.input(texto)

    def token(self):
        return self.lexer.token()
