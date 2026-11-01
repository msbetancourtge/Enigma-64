"""
Analizador lexico del modulo objeto en texto (.tobj) - Enigma-64 (Noctua Systems).

El Enlazador-Cargador acepta cada modulo objeto en dos representaciones
equivalentes: la binaria (.obj, ver objeto.py) y la de texto (.tobj), que es la
que escribe una persona o el backend del ensamblador SPL. La de texto se analiza
con lex.py (PLY), la alternativa a FLEX que admite el enunciado:

    ; principal.tobj
    [MODULO] principal
    [ENTRADA] .text + 0x0000
    [SECCION] .text BITS R-X ALIN 1 {
        14 10 00 00                 ; ADDI R1, R0, %hi(valores)
    }
    [SECCION] .bss VACIA RW- ALIN 8 TAM 16
    [SIMBOLOS]
    main     GLOBAL     FUNCION  .text  0x0000
    sumar    IMPORTADO  FUNCION
    [REUBICACIONES]
    .text  0x0002  HI16  valores  +0

Como un %x de FLEX, el contenido de una seccion se reconoce en el estado
exclusivo 'contenido': entre '{' y '}' solo hay bytes de dos digitos
hexadecimales y comentarios, asi '16' es un byte y no el entero 16. Fuera de ese
estado el salto de linea es un token (FIN_LINEA) porque cada fila de una tabla
ocupa una linea. Un '{' sin cerrar se detecta con la regla de fin de archivo del
estado (el <<EOF>> de FLEX).

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

from __future__ import annotations

from dataclasses import dataclass

import ply.lex as lex
from ply.lex import TOKEN

from .objeto import (
    NOMBRE_LIGADURA,
    NOMBRE_REUBICACION,
    NOMBRE_TIPO_SECCION,
    NOMBRE_TIPO_SIMBOLO,
)

# ---------------------------------------------------------------------------
# Vocabulario del modulo objeto en texto
# ---------------------------------------------------------------------------

ENCABEZADOS = frozenset({'MODULO', 'ENTRADA', 'SECCION', 'SIMBOLOS', 'REUBICACIONES'})

# Palabras reservadas -> categoria. Salen de las mismas tablas que usa el formato
# binario, asi ambas representaciones nombran igual cada tipo.
PALABRAS_RESERVADAS = {
    **{nombre: 'TIPO_SECCION' for nombre in NOMBRE_TIPO_SECCION.values()},
    **{nombre: 'LIGADURA' for nombre in NOMBRE_LIGADURA.values()},
    'IMPORTADO': 'LIGADURA',
    **{nombre: 'TIPO_SIMBOLO' for nombre in NOMBRE_TIPO_SIMBOLO.values()},
    **{nombre: 'TIPO_REUBICACION' for nombre in NOMBRE_REUBICACION.values()},
    'ALIN': 'ATRIBUTO',
    'TAM': 'ATRIBUTO',
}

# Escapes admitidos dentro de un nombre entre comillas
ESCAPES = {'\\': '\\', '"': '"', 'n': '\n', 't': '\t'}

# Todos los campos numericos del formato .obj caben en 32 bits
_MAX_U32 = 0xFFFFFFFF

# ---------------------------------------------------------------------------
# Definiciones regulares
# ---------------------------------------------------------------------------

DIGITO = r'[0-9]'
HEX = r'[0-9a-fA-F]'
LETRA = r'[a-zA-Z_.]'
NOMBRE = LETRA + r'(?:' + LETRA + r'|' + DIGITO + r')*'
FIN_NUM = r'(?![\w.])'        # un literal no puede ir pegado a letras, digitos o '.'

ENCABEZADO = r'\[[a-zA-Z_]+\]'
PERMISOS = r'[R-][W-][X-](?![\w.-])'
ENTERO_HEX = r'0[xX]' + HEX + r'+' + FIN_NUM
ENTERO_DEC = DIGITO + r'+' + FIN_NUM
NUMERO_MAL = DIGITO + r'[\w.]*'
CADENA = r'"(?:[^"\\\n]|\\.)*"'
CADENA_ABIERTA = r'"(?:[^"\\\n]|\\.)*\\?'
COMENTARIO = r';[^\n]*'
BYTE = HEX + r'{2}(?!\w)'
BYTE_MAL = r'\w+'


@dataclass(frozen=True)
class ErrorLexico:
    linea: int
    columna: int
    lexema: str
    mensaje: str

    def __str__(self):
        return (f"ERROR LEXICO (linea {self.linea}, columna {self.columna}): "
                f"{self.mensaje}: '{self.lexema}'")


class ObjetoLexer:
    """
    Tokenizador del modulo objeto en texto de Enigma-64.

    Las reglas de funcion se prueban en el orden en que estan escritas: los
    permisos van antes que los nombres (RWX no es un simbolo) y cada regla de
    error va despues de la regla valida que extiende.
    """

    tokens = (
        'ENCABEZADO',
        'TIPO_SECCION',
        'PERMISOS',
        'ATRIBUTO',
        'LIGADURA',
        'TIPO_SIMBOLO',
        'TIPO_REUBICACION',
        'SECCION_ABSOLUTA',
        'NOMBRE',
        'ENTERO_HEX',
        'ENTERO_DEC',
        'BYTE',
        'MAS',
        'MENOS',
        'LLAVE_IZQ',
        'LLAVE_DER',
        'FIN_LINEA',
    )

    states = (
        ('contenido', 'exclusive'),
    )

    t_ignore = ' \t\r'
    t_contenido_ignore = ' \t\r'

    # Estado INITIAL: encabezados y filas de las tablas

    @TOKEN(COMENTARIO)
    def t_COMENTARIO(self, t):
        self.comentarios += 1

    def t_FIN_LINEA(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)
        return t

    @TOKEN(ENCABEZADO)
    def t_ENCABEZADO(self, t):
        if t.value[1:-1] not in ENCABEZADOS:
            self._reportar(t, 'encabezado desconocido')
            return None
        return t

    @TOKEN(PERMISOS)
    def t_PERMISOS(self, t):
        return t

    @TOKEN(ENTERO_HEX)
    def t_ENTERO_HEX(self, t):
        return self._literal_entero(t, 16)

    @TOKEN(ENTERO_DEC)
    def t_ENTERO_DEC(self, t):
        return self._literal_entero(t, 10)

    # Digitos pegados a letras o puntos: 0x1G, 12ab, 0x10.5
    @TOKEN(NUMERO_MAL)
    def t_NUMERO_MAL(self, t):
        self._reportar(t, 'literal numerico mal formado')

    # Nombre entre comillas: para nombres que coinciden con una palabra reservada
    # o que no tienen forma de identificador ("DATO", "mi seccion")
    @TOKEN(CADENA)
    def t_CADENA(self, t):
        texto = []
        i = 1
        while i < len(t.value) - 1:
            if t.value[i] == '\\':
                if t.value[i + 1] not in ESCAPES:
                    self._reportar(t, f"secuencia de escape no valida '\\{t.value[i + 1]}'")
                    return None
                texto.append(ESCAPES[t.value[i + 1]])
                i += 2
            else:
                texto.append(t.value[i])
                i += 1
        t.type = 'NOMBRE'
        t.nombre = ''.join(texto)
        return t

    @TOKEN(CADENA_ABIERTA)
    def t_CADENA_ABIERTA(self, t):
        self._reportar(t, 'cadena sin cerrar antes del fin de linea')

    # Una sola regla para palabras: la palabra completa se busca en la tabla de
    # reservadas, asi 'DATOS' es un nombre y 'DATO' un tipo de simbolo.
    @TOKEN(NOMBRE)
    def t_NOMBRE(self, t):
        t.type = PALABRAS_RESERVADAS.get(t.value, 'NOMBRE')
        if t.type == 'NOMBRE':
            t.nombre = t.value
        return t

    def t_LLAVE_IZQ(self, t):
        r'\{'
        self._apertura = (t.lexer.lineno, t.lexpos)
        t.lexer.begin('contenido')
        return t

    t_SECCION_ABSOLUTA = r'\*ABS\*'
    t_MAS = r'\+'
    t_MENOS = r'-'

    def t_error(self, t):
        t.value = t.value[0]
        self._reportar(t, 'caracter no valido')
        t.lexer.skip(1)

    # Estado 'contenido': bytes de una seccion BITS entre '{' y '}'

    @TOKEN(COMENTARIO)
    def t_contenido_COMENTARIO(self, t):
        self.comentarios += 1

    def t_contenido_SALTO(self, t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    @TOKEN(BYTE)
    def t_contenido_BYTE(self, t):
        t.entero = int(t.value, 16)
        return t

    @TOKEN(BYTE_MAL)
    def t_contenido_BYTE_MAL(self, t):
        self._reportar(t, 'byte mal formado (se esperan dos digitos hexadecimales)')

    def t_contenido_LLAVE_DER(self, t):
        r'\}'
        t.lexer.begin('INITIAL')
        return t

    def t_contenido_error(self, t):
        t.value = t.value[0]
        self._reportar(t, 'caracter no valido en el contenido de la seccion')
        t.lexer.skip(1)

    def t_contenido_eof(self, t):
        # Se informa en la posicion de la '{' y se cierra el bloque con una '}'
        # vacia para que el analizador no repita el error
        linea, lexpos = self._apertura
        self._registrar(ErrorLexico(linea, self._columna(lexpos), '{',
                                    "contenido de seccion sin cerrar (falta '}')"))
        t.lexer.begin('INITIAL')
        t.type = 'LLAVE_DER'
        t.value = ''
        return t

    # Utilidades de las reglas

    def _literal_entero(self, t, base):
        t.entero = int(t.value if base == 10 else t.value[2:], base)
        if t.entero > _MAX_U32:
            self._reportar(t, 'literal excede los 32 bits de los campos del formato .obj')
            return None
        return t

    def _columna(self, lexpos):
        return lexpos - self.lexer.lexdata.rfind('\n', 0, lexpos)

    def _reportar(self, t, mensaje):
        self._registrar(ErrorLexico(t.lexer.lineno, self._columna(t.lexpos), t.value, mensaje))

    def _registrar(self, error):
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
        self._apertura = (1, 0)
        self.lexer.lineno = 1
        self.lexer.begin('INITIAL')
        self.lexer.input(texto)

    def token(self):
        tok = self.lexer.token()
        if tok is not None:
            tok.columna = self._columna(tok.lexpos)
        return tok

    def __iter__(self):
        return iter(self.token, None)

    def tokenizar(self, texto: str):
        """Devuelve (lista de tokens, lista de ErrorLexico) del texto completo."""
        self.input(texto)
        return list(self), list(self.errores)
