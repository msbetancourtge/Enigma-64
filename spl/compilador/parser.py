"""
Analizador sintáctico LALR(1) del Compilador SPL para Enigma-64 (ply.yacc).
Fase 2: Análisis Sintáctico (Taller 02, Literales a y e).

Contrato de entrada y salida (Matriz de Modularidad, etapa 3):
- Entrada: flujo de tokens List[LexToken] emitido por CompiladorLexer sobre el
  texto preprocesado (.pre).
- Salida: ProgramaAST (spl/compilador/ast_nodos.py) + List[ErrorSintactico].

Las producciones siguen la gramática E-BNF de spl/compilador/gramatica_spl.ebnf.
Las repeticiones E-BNF (X*, X+) se expresan con recursión por la izquierda, que
es la forma que no agota la pila en un analizador LR.

Organización por responsables:
- Parte 1, Integrante 2 (_ProduccionesDeclaraciones): Programa, DefinicionTDA
  (struct/tda), DefinicionTypedef, EspecificadorTipo, DeclaracionVariable
  (escalares, 1D y 2D con inicializadores) y DeclaracionFuncion
  (definiciones y prototipos).
- Parte 2, Integrante 3 (_ProduccionesSentenciasExpresiones): Bloque, sentencias,
  control de flujo, niveles de expresión y p_error. Esta parte contiene por
  ahora una base mínima (bloques, asignación, return y expresiones con los
  operadores que reconoce el lexer) para que la Parte 1 se pueda construir y
  probar; el Integrante 3 la completa.

Nombres de tipo declarados con typedef (token TIPO_ID): la gramática distingue
TIPO_ID de ID para que 'Alias x;' (declaración) y 'x = 1;' (sentencia) no
generen conflictos. El parser registra el alias en una acción intermedia, justo
después de leer su nombre, y el flujo de tokens reclasifica como TIPO_ID cada
ID que coincida con un alias registrado.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Set, Tuple

import ply.yacc as yacc

from spl.compilador.ast_nodos import (
    CATEGORIA_ALIAS,
    CATEGORIA_PRIMITIVO,
    AccesoCampo,
    AccesoIndice,
    Asignacion,
    Bloque,
    CampoTDA,
    Declarador,
    DeclaracionVariable,
    DefinicionFuncion,
    DefinicionTDA,
    DefinicionTypedef,
    EspecificadorTipo,
    ExpresionBinaria,
    ExpresionUnaria,
    Identificador,
    ListaInicializadores,
    LiteralBooleano,
    LiteralCadena,
    LiteralCaracter,
    LiteralEntero,
    LiteralFlotante,
    LlamadaFuncion,
    Parametro,
    ProgramaAST,
    SentenciaExpresion,
    SentenciaReturn,
    SentenciaVacia,
    Sizeof,
)
from spl.compilador.lexer import CompiladorLexer, ErrorLexico
from spl.compilador.tablas import GestorTablasSimbolos, desescapar_cadena


# ---------------------------------------------------------------------------
# 1. Errores sintácticos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ErrorSintactico:
    """Error reportado por el analizador sintáctico."""

    linea: int
    columna: int
    lexema: str
    mensaje: str

    def __str__(self) -> str:
        return (
            f"ERROR SINTACTICO (linea {self.linea}, columna {self.columna}): "
            f"{self.mensaje}: '{self.lexema}'"
        )


# Tokens que la gramática usa y que el lexer de la Fase 1 todavía no emite.
# TRUE_LIT y FALSE_LIT los agrega el ajuste léxico del Literal b; TIPO_ID lo
# produce el propio parser al reclasificar los alias de typedef.
TOKENS_ADICIONALES = ("TRUE_LIT", "FALSE_LIT", "TIPO_ID")

TIPOS_PRIMITIVOS_TOKEN = {
    "INT_TYPE": "int",
    "FLOAT_TYPE": "float",
    "BOOL_TYPE": "bool",
    "CHAR_TYPE": "char",
    "VOID_TYPE": "void",
}

INT64_MIN = -(2**63)
INT64_MAX = 2**63 - 1


def _pos(p, i: int) -> dict:
    """Posición (linea, columna) del terminal en la posición i de la producción."""
    tok = p.slice[i]
    return {"linea": getattr(tok, "lineno", 0), "columna": getattr(tok, "columna", 0)}


def _pos_nodo(nodo) -> dict:
    """Posición heredada de un nodo ya construido."""
    return {"linea": nodo.linea, "columna": nodo.columna}


def _a_int64(valor: int) -> int:
    """Interpreta un patrón de 64 bits en complemento a dos."""
    valor &= 2**64 - 1
    return valor - 2**64 if valor > INT64_MAX else valor


# ---------------------------------------------------------------------------
# 2. Flujo de tokens con reclasificación de alias (typedef)
# ---------------------------------------------------------------------------

class _FlujoTokens:
    """Adaptador entre CompiladorLexer y ply.yacc que emite TIPO_ID para los alias."""

    def __init__(self, lexer: CompiladorLexer, nombres_tipo: Set[str]) -> None:
        self.lexer = lexer
        self.nombres_tipo = nombres_tipo
        self.ultima_linea = 1

    def input(self, texto: str) -> None:
        self.lexer.input(texto)

    def token(self):
        tok = self.lexer.token()
        if tok is not None:
            self.ultima_linea = tok.lineno
            if tok.type == "ID" and tok.value in self.nombres_tipo:
                tok.type = "TIPO_ID"
        return tok


class _RegistroPLY:
    """Logger para ply.yacc que guarda los avisos en vez de imprimirlos."""

    def __init__(self) -> None:
        self.avisos: List[str] = []
        self.errores: List[str] = []

    def debug(self, msg, *args, **kwargs):
        pass

    info = debug

    def warning(self, msg, *args, **kwargs):
        self.avisos.append(msg % args)

    def error(self, msg, *args, **kwargs):
        self.errores.append(msg % args)

    critical = error

    def contar(self, patron: str) -> int:
        """Suma los conflictos reportados con el patrón dado (shift/reduce o reduce/reduce)."""
        total = 0
        for aviso in self.avisos:
            m = re.match(r"^(\d+) " + patron + r" conflicts?$", aviso)
            if m:
                total += int(m.group(1))
        return total


# ---------------------------------------------------------------------------
# 3. Parte 1 (Integrante 2): Programa, TDA, typedef, variables y funciones
# ---------------------------------------------------------------------------

class _ProduccionesDeclaraciones:
    """Producciones de declaraciones. Cada p_* construye el nodo del AST correspondiente."""

    # --- Programa -----------------------------------------------------------

    def p_programa(self, p):
        """programa : lista_declaraciones_externas"""
        p[0] = ProgramaAST(declaraciones=p[1], linea=1, columna=1)

    def p_lista_declaraciones_externas(self, p):
        """lista_declaraciones_externas : lista_declaraciones_externas declaracion_externa
                                        | vacio"""
        if len(p) == 2:
            # Se guarda la referencia para conservar las declaraciones ya
            # reconocidas si el archivo termina en medio de una declaración.
            p[0] = self._declaraciones = []
        else:
            p[0] = p[1]
            if p[2] is not None:  # None = declaración descartada tras un error
                p[0].append(p[2])

    def p_declaracion_externa(self, p):
        """declaracion_externa : definicion_tda
                               | definicion_typedef
                               | definicion_funcion
                               | declaracion_variable"""
        p[0] = p[1]

    def p_declaracion_externa_error(self, p):
        """declaracion_externa : error PUNTO_Y_COMA"""
        # Recuperación en modo pánico: se descartan los tokens hasta el ';'
        # que cierra la declaración defectuosa y el análisis continúa.
        p[0] = None

    # --- Especificador de tipo ------------------------------------------------

    def p_especificador_tipo(self, p):
        """especificador_tipo : tipo_base
                              | CONST tipo_base"""
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = p[2]
            p[0].es_const = True
            pos = _pos(p, 1)  # la construcción empieza en 'const'
            p[0].linea, p[0].columna = pos["linea"], pos["columna"]

    def p_tipo_base_primitivo(self, p):
        """tipo_base : INT_TYPE
                     | FLOAT_TYPE
                     | BOOL_TYPE
                     | CHAR_TYPE
                     | VOID_TYPE"""
        nombre = TIPOS_PRIMITIVOS_TOKEN[p.slice[1].type]
        p[0] = EspecificadorTipo(nombre=nombre, categoria=CATEGORIA_PRIMITIVO, **_pos(p, 1))

    def p_tipo_base_compuesto(self, p):
        """tipo_base : clase_tda ID"""
        clase, pos = p[1]
        p[0] = EspecificadorTipo(nombre=p[2], categoria=clase, **pos)

    def p_tipo_base_alias(self, p):
        """tipo_base : TIPO_ID"""
        p[0] = EspecificadorTipo(nombre=p[1], categoria=CATEGORIA_ALIAS, **_pos(p, 1))

    def p_clase_tda(self, p):
        """clase_tda : STRUCT
                     | TDA"""
        # Se devuelve la palabra usada ('struct' o 'tda') junto con su posición.
        p[0] = (p.slice[1].type.lower(), _pos(p, 1))

    # --- DefinicionTDA ------------------------------------------------------

    def p_definicion_tda(self, p):
        """definicion_tda : clase_tda ID LLAVE_IZQ lista_campos LLAVE_DER PUNTO_Y_COMA"""
        clase, pos = p[1]
        p[0] = DefinicionTDA(clase=clase, nombre=p[2], campos=p[4], **pos)

    def p_lista_campos(self, p):
        """lista_campos : lista_campos campo_tda
                        | campo_tda"""
        if len(p) == 2:
            p[0] = [p[1]] if p[1] is not None else []
        else:
            p[0] = p[1]
            if p[2] is not None:
                p[0].append(p[2])

    def p_campo_tda(self, p):
        """campo_tda : especificador_tipo ID dimensiones PUNTO_Y_COMA"""
        p[0] = CampoTDA(tipo=p[1], nombre=p[2], dimensiones=p[3], **_pos_nodo(p[1]))

    def p_campo_tda_error(self, p):
        """campo_tda : error PUNTO_Y_COMA"""
        p[0] = None

    # --- DefinicionTypedef ----------------------------------------------------

    def p_definicion_typedef(self, p):
        """definicion_typedef : TYPEDEF especificador_tipo ID registrar_alias dimensiones PUNTO_Y_COMA"""
        p[0] = DefinicionTypedef(tipo=p[2], nombre=p[3], dimensiones=p[5], **_pos(p, 1))

    def p_registrar_alias(self, p):
        """registrar_alias : vacio"""
        # Acción intermedia: p[-1] es el ID recién leído. Registrarlo aquí, y
        # no al reducir la definición completa, garantiza que el siguiente
        # uso del alias ya salga del flujo de tokens como TIPO_ID.
        self._nombres_tipo.add(p[-1])

    # --- Dimensiones ----------------------------------------------------------

    def p_dimensiones(self, p):
        """dimensiones : dimensiones CORCHETE_IZQ expresion CORCHETE_DER
                       | vacio"""
        # Dimensiones obligatorias (campos de TDA y typedef): [N], [F][C]
        if len(p) == 2:
            p[0] = []
        else:
            p[0] = p[1] + [p[3]]

    def p_dimensiones_abiertas(self, p):
        """dimensiones_abiertas : dimensiones_abiertas CORCHETE_IZQ expresion CORCHETE_DER
                                | dimensiones_abiertas CORCHETE_IZQ CORCHETE_DER
                                | vacio"""
        # Variables y parámetros admiten una dimensión vacía: v[] = {...}, m[][4]
        if len(p) == 2:
            p[0] = []
        elif len(p) == 4:
            p[0] = p[1] + [None]
        else:
            p[0] = p[1] + [p[3]]

    # --- DeclaracionVariable --------------------------------------------------

    def p_declaracion_variable(self, p):
        """declaracion_variable : especificador_tipo lista_declaradores PUNTO_Y_COMA"""
        p[0] = DeclaracionVariable(tipo=p[1], declaradores=p[2], **_pos_nodo(p[1]))

    def p_lista_declaradores(self, p):
        """lista_declaradores : lista_declaradores COMA declarador
                              | declarador"""
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[3]]

    def p_declarador(self, p):
        """declarador : ID dimensiones_abiertas
                      | ID dimensiones_abiertas ASIGNAR inicializador"""
        inicializador = p[4] if len(p) == 5 else None
        p[0] = Declarador(nombre=p[1], dimensiones=p[2], inicializador=inicializador, **_pos(p, 1))

    def p_inicializador_expresion(self, p):
        """inicializador : expresion"""
        p[0] = p[1]

    def p_inicializador_lista(self, p):
        """inicializador : LLAVE_IZQ lista_inicializadores LLAVE_DER
                         | LLAVE_IZQ lista_inicializadores COMA LLAVE_DER"""
        p[0] = ListaInicializadores(elementos=p[2], **_pos(p, 1))

    def p_lista_inicializadores(self, p):
        """lista_inicializadores : lista_inicializadores COMA inicializador
                                 | inicializador"""
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[3]]

    # --- DeclaracionFuncion ---------------------------------------------------

    def p_definicion_funcion(self, p):
        """definicion_funcion : encabezado_funcion bloque
                              | encabezado_funcion PUNTO_Y_COMA"""
        funcion = p[1]
        funcion.cuerpo = p[2] if isinstance(p[2], Bloque) else None
        p[0] = funcion

    def p_encabezado_funcion(self, p):
        """encabezado_funcion : FUNCTION especificador_tipo ID PARENTESIS_IZQ parametros_opt PARENTESIS_DER
                              | especificador_tipo ID PARENTESIS_IZQ parametros_opt PARENTESIS_DER"""
        if p.slice[1].type == "FUNCTION":
            tipo, nombre, params, pos, con_function = p[2], p[3], p[5], _pos(p, 1), True
        else:
            tipo, nombre, params, pos, con_function = p[1], p[2], p[4], _pos_nodo(p[1]), False
        p[0] = DefinicionFuncion(
            tipo_retorno=tipo,
            nombre=nombre,
            parametros=self._normalizar_void(params),
            con_function=con_function,
            **pos,
        )

    @staticmethod
    def _normalizar_void(params: List[Parametro]) -> List[Parametro]:
        """'f(void)' equivale a una función sin parámetros."""
        if len(params) == 1:
            unico = params[0]
            if (unico.tipo.nombre == "void" and unico.tipo.es_primitivo
                    and not unico.tipo.es_const and unico.nombre is None
                    and not unico.dimensiones):
                return []
        return params

    def p_parametros_opt(self, p):
        """parametros_opt : lista_parametros
                          | vacio"""
        p[0] = p[1] if p[1] is not None else []

    def p_lista_parametros(self, p):
        """lista_parametros : lista_parametros COMA parametro
                            | parametro"""
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[3]]

    def p_parametro(self, p):
        """parametro : especificador_tipo ID dimensiones_abiertas
                     | especificador_tipo dimensiones_abiertas"""
        if len(p) == 4:
            p[0] = Parametro(tipo=p[1], nombre=p[2], dimensiones=p[3], **_pos_nodo(p[1]))
        else:
            p[0] = Parametro(tipo=p[1], nombre=None, dimensiones=p[2], **_pos_nodo(p[1]))

    # --- Producción vacía -----------------------------------------------------

    def p_vacio(self, p):
        """vacio :"""
        p[0] = None


# ---------------------------------------------------------------------------
# 4. Parte 2 (Integrante 3): bloques, sentencias y expresiones
#    BASE MÍNIMA PROVISIONAL: el Integrante 3 agrega el control de flujo
#    (if/switch/while/do/for/break/continue), los niveles de bits, la
#    asignación compuesta y la recuperación de errores por sentencia.
# ---------------------------------------------------------------------------

class _ProduccionesSentenciasExpresiones:

    # --- Bloques y sentencias -------------------------------------------------

    def p_bloque(self, p):
        """bloque : LLAVE_IZQ elementos_bloque LLAVE_DER"""
        p[0] = Bloque(elementos=p[2], **_pos(p, 1))

    def p_elementos_bloque(self, p):
        """elementos_bloque : elementos_bloque elemento_bloque
                            | vacio"""
        if len(p) == 2:
            p[0] = []
        else:
            p[0] = p[1] + [p[2]]

    def p_elemento_bloque(self, p):
        """elemento_bloque : declaracion_variable
                           | sentencia"""
        p[0] = p[1]

    def p_sentencia_bloque(self, p):
        """sentencia : bloque"""
        p[0] = p[1]

    def p_sentencia_vacia(self, p):
        """sentencia : PUNTO_Y_COMA"""
        p[0] = SentenciaVacia(**_pos(p, 1))

    def p_sentencia_simple(self, p):
        """sentencia : sentencia_simple PUNTO_Y_COMA"""
        p[0] = p[1]

    def p_sentencia_simple_expresion(self, p):
        """sentencia_simple : expresion"""
        p[0] = SentenciaExpresion(expresion=p[1], **_pos_nodo(p[1]))

    def p_sentencia_simple_asignacion(self, p):
        """sentencia_simple : expresion ASIGNAR expresion"""
        p[0] = Asignacion(destino=p[1], operador="=", valor=p[3], **_pos_nodo(p[1]))

    def p_sentencia_return(self, p):
        """sentencia : RETURN PUNTO_Y_COMA
                     | RETURN expresion PUNTO_Y_COMA"""
        valor = p[2] if len(p) == 4 else None
        p[0] = SentenciaReturn(valor=valor, **_pos(p, 1))

    # --- Expresiones (estratificadas, asociatividad izquierda) ----------------

    def p_expresion(self, p):
        """expresion : expr_or"""
        p[0] = p[1]

    def p_expr_binaria(self, p):
        """expr_or : expr_or OR_LOGICO expr_and
           expr_and : expr_and AND_LOGICO expr_igualdad
           expr_igualdad : expr_igualdad IGUAL expr_relacional
                         | expr_igualdad DISTINTO expr_relacional
           expr_relacional : expr_relacional MENOR expr_aditiva
                           | expr_relacional MENOR_IGUAL expr_aditiva
                           | expr_relacional MAYOR expr_aditiva
                           | expr_relacional MAYOR_IGUAL expr_aditiva
           expr_aditiva : expr_aditiva MAS expr_multiplicativa
                        | expr_aditiva MENOS expr_multiplicativa
           expr_multiplicativa : expr_multiplicativa POR expr_unaria
                               | expr_multiplicativa DIV expr_unaria
                               | expr_multiplicativa MOD expr_unaria"""
        p[0] = ExpresionBinaria(operador=p[2], izquierda=p[1], derecha=p[3], **_pos_nodo(p[1]))

    def p_expr_nivel(self, p):
        """expr_or : expr_and
           expr_and : expr_igualdad
           expr_igualdad : expr_relacional
           expr_relacional : expr_aditiva
           expr_aditiva : expr_multiplicativa
           expr_multiplicativa : expr_unaria
           expr_unaria : expr_postfija
           expr_postfija : expr_primaria"""
        p[0] = p[1]

    def p_expr_unaria(self, p):
        """expr_unaria : MAS expr_unaria
                       | MENOS expr_unaria
                       | NOT_LOGICO expr_unaria"""
        p[0] = ExpresionUnaria(operador=p[1], operando=p[2], **_pos(p, 1))

    def p_expr_sizeof(self, p):
        """expr_unaria : SIZEOF PARENTESIS_IZQ especificador_tipo PARENTESIS_DER
                       | SIZEOF PARENTESIS_IZQ expresion PARENTESIS_DER"""
        p[0] = Sizeof(objetivo=p[3], **_pos(p, 1))

    def p_expr_postfija_indice(self, p):
        """expr_postfija : expr_postfija CORCHETE_IZQ expresion CORCHETE_DER"""
        p[0] = AccesoIndice(base=p[1], indice=p[3], **_pos_nodo(p[1]))

    def p_expr_postfija_campo(self, p):
        """expr_postfija : expr_postfija PUNTO ID
                         | expr_postfija FLECHA ID"""
        p[0] = AccesoCampo(base=p[1], campo=p[3], por_puntero=p[2] == "->", **_pos_nodo(p[1]))

    def p_expr_postfija_llamada(self, p):
        """expr_postfija : expr_postfija PARENTESIS_IZQ argumentos_opt PARENTESIS_DER"""
        p[0] = LlamadaFuncion(funcion=p[1], argumentos=p[3], **_pos_nodo(p[1]))

    def p_argumentos_opt(self, p):
        """argumentos_opt : lista_argumentos
                          | vacio"""
        p[0] = p[1] if p[1] is not None else []

    def p_lista_argumentos(self, p):
        """lista_argumentos : lista_argumentos COMA expresion
                            | expresion"""
        if len(p) == 2:
            p[0] = [p[1]]
        else:
            p[0] = p[1] + [p[3]]

    def p_expr_primaria_id(self, p):
        """expr_primaria : ID"""
        p[0] = Identificador(nombre=p[1], simbolo_idx=p.slice[1].simbolo_idx, **_pos(p, 1))

    def p_expr_primaria_parentesis(self, p):
        """expr_primaria : PARENTESIS_IZQ expresion PARENTESIS_DER"""
        p[0] = p[2]

    def p_expr_primaria_literal(self, p):
        """expr_primaria : literal"""
        p[0] = p[1]

    # --- Literales -----------------------------------------------------------

    def p_literal_entero(self, p):
        """literal : ENTERO_DEC
                   | ENTERO_HEX
                   | ENTERO_BIN"""
        tok = p.slice[1]
        lexema = tok.value
        if tok.type == "ENTERO_HEX":
            valor = _a_int64(int(lexema, 16))
        elif tok.type == "ENTERO_BIN":
            valor = _a_int64(int(lexema[2:], 2))
        else:
            valor = int(lexema)
        p[0] = LiteralEntero(valor=valor, lexema=lexema, simbolo_idx=tok.simbolo_idx, **_pos(p, 1))

    def p_literal_flotante(self, p):
        """literal : FLOTANTE"""
        tok = p.slice[1]
        p[0] = LiteralFlotante(valor=float(tok.value), lexema=tok.value,
                               simbolo_idx=tok.simbolo_idx, **_pos(p, 1))

    def p_literal_cadena(self, p):
        """literal : STRING"""
        tok = p.slice[1]
        p[0] = LiteralCadena(valor=desescapar_cadena(tok.value), lexema=tok.value,
                             simbolo_idx=tok.simbolo_idx, **_pos(p, 1))

    def p_literal_caracter(self, p):
        """literal : CHAR_LITERAL"""
        lexema = p[1]
        valor = desescapar_cadena('"' + lexema[1:-1] + '"')
        p[0] = LiteralCaracter(valor=valor, lexema=lexema, **_pos(p, 1))

    def p_literal_booleano(self, p):
        """literal : TRUE_LIT
                   | FALSE_LIT"""
        p[0] = LiteralBooleano(valor=p.slice[1].type == "TRUE_LIT", **_pos(p, 1))

    # --- Errores ---------------------------------------------------------------

    def p_error(self, tok):
        if tok is None:
            error = ErrorSintactico(
                linea=self._flujo.ultima_linea,
                columna=0,
                lexema="<EOF>",
                mensaje="fin de archivo inesperado (falta cerrar una declaracion o un bloque)",
            )
        else:
            error = ErrorSintactico(
                linea=tok.lineno,
                columna=getattr(tok, "columna", 0),
                lexema=str(tok.value),
                mensaje=f"token inesperado {tok.type}",
            )
        self.errores.append(error)
        if self.al_error:
            self.al_error(error)


# ---------------------------------------------------------------------------
# 5. Fachada del analizador sintáctico
# ---------------------------------------------------------------------------

class CompiladorParser(_ProduccionesDeclaraciones, _ProduccionesSentenciasExpresiones):
    """
    Analizador sintáctico LALR(1) del SPL.

    Uso:
        parser = CompiladorParser()
        ast, errores = parser.analizar(texto_pre)

    Tras analizar quedan disponibles parser.tablas (GestorTablasSimbolos que
    llenó el lexer), parser.errores_lexicos y parser.nombres_tipo (alias de typedef).
    """

    tokens = CompiladorLexer.tokens + tuple(
        t for t in TOKENS_ADICIONALES if t not in CompiladorLexer.tokens
    )
    start = "programa"

    def __init__(self, al_error: Optional[Callable[[ErrorSintactico], None]] = None) -> None:
        """
        Construye las tablas LALR(1) en memoria (no escribe parsetab.py ni parser.out).

        :param al_error: callback opcional que recibe cada ErrorSintactico.
        """
        self.al_error = al_error
        self.errores: List[ErrorSintactico] = []
        self.errores_lexicos: List[ErrorLexico] = []
        self.tablas: Optional[GestorTablasSimbolos] = None
        self._nombres_tipo: Set[str] = set()
        self._declaraciones: List[Any] = []
        self._flujo: Optional[_FlujoTokens] = None

        self.registro = _RegistroPLY()
        self._parser = yacc.yacc(
            module=self,
            start=self.start,
            debug=True,                    # necesario para que PLY cuente conflictos
            debuglog=yacc.NullLogger(),    # sin archivo parser.out
            errorlog=self.registro,
            write_tables=False,            # sin archivo parsetab.py
        )
        self.conflictos_shift_reduce = self.registro.contar("shift/reduce")
        self.conflictos_reduce_reduce = self.registro.contar("reduce/reduce")

    @property
    def nombres_tipo(self) -> Set[str]:
        return set(self._nombres_tipo)

    def analizar(
        self,
        texto: str,
        tablas: Optional[GestorTablasSimbolos] = None,
        al_error_lexico: Optional[Callable[[ErrorLexico], None]] = None,
    ) -> Tuple[ProgramaAST, List[ErrorSintactico]]:
        """
        Analiza un texto SPL ya preprocesado.

        :param texto: contenido del archivo .pre (o código sin directivas).
        :param tablas: GestorTablasSimbolos compartido; si se omite se crea uno nuevo.
        :param al_error_lexico: callback opcional para los errores léxicos.
        :return: (ProgramaAST, lista de errores sintácticos). El AST se devuelve
                 aunque haya errores: contiene las declaraciones reconocidas y
                 omite las que se descartaron durante la recuperación.
        """
        self.errores = []
        self._declaraciones = []
        self._nombres_tipo = set()
        self.tablas = tablas if tablas is not None else GestorTablasSimbolos()
        lexer = CompiladorLexer(al_error=al_error_lexico, tablas=self.tablas)
        self._flujo = _FlujoTokens(lexer, self._nombres_tipo)
        self._flujo.input(texto)

        ast = self._parser.parse(lexer=self._flujo)
        if ast is None:
            # Error irrecuperable al final del archivo: PLY aborta sin valor,
            # pero las declaraciones completas anteriores siguen siendo válidas.
            ast = ProgramaAST(declaraciones=self._declaraciones, linea=1, columna=1)
        self.errores_lexicos = list(lexer.errores)
        return ast, list(self.errores)

    # Alias con el nombre habitual de PLY
    def parse(self, texto: str) -> ProgramaAST:
        return self.analizar(texto)[0]


# ---------------------------------------------------------------------------
# 6. CLI de depuración: python -m spl.compilador.parser archivo.spl
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    import argparse

    from spl.compilador.ast_nodos import formatear_ast
    from spl.preprocesador.motor import PreprocesadorError, preprocesar_archivo

    ap = argparse.ArgumentParser(
        prog="python -m spl.compilador.parser",
        description="Analizador sintáctico del SPL: imprime el AST de un programa",
    )
    ap.add_argument("entrada", help="archivo .spl (se preprocesa) o .pre")
    args = ap.parse_args(argv)

    try:
        if args.entrada.endswith(".pre"):
            with open(args.entrada, encoding="utf-8") as f:
                texto = f.read()
        else:
            texto = preprocesar_archivo(args.entrada).texto
    except (OSError, PreprocesadorError) as exc:
        sys.stderr.write(f"No se pudo leer '{args.entrada}': {exc}\n")
        return 2

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = CompiladorParser()
    ast, errores = parser.analizar(texto)
    print(formatear_ast(ast))
    for err in parser.errores_lexicos:
        print(err)
    for err in errores:
        print(err)
    print(f"\n{len(parser.errores_lexicos)} errores lexicos, {len(errores)} errores sintacticos")
    return 1 if errores or parser.errores_lexicos else 0


if __name__ == "__main__":
    sys.exit(main())
