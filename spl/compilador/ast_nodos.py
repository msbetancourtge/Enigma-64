"""
Jerarquía de nodos del Árbol de Sintaxis Abstracta (AST) del Compilador SPL.
Fase 2: Análisis Sintáctico (Taller 02, Literal e).

Responsabilidad: Integrante 2
- Nodos de todas las construcciones de la gramática E-BNF
  (spl/compilador/gramatica_spl.ebnf): programa, TDA, typedef, variables
  escalares/1D/2D, funciones, sentencias y expresiones.
- Atributos comunes de posición (linea, columna) y anotaciones que llena el
  analizador semántico (tipo_inferido, simbolo).
- Recorrido genérico (hijos, recorrer), patrón visitante y volcado en texto.

Convenciones:
- Todos los nodos son @dataclass. Los atributos de posición y de anotación son
  solo de palabra clave y no participan en la igualdad (==), de modo que dos
  árboles con la misma estructura son iguales aunque vengan de líneas distintas.
- Las dimensiones de arreglos y matrices se guardan como lista de expresiones,
  una por dimensión: v[N] -> [N], m[F][C] -> [F, C]. Una dimensión vacía
  ('int v[] = {...}' o el parámetro 'int m[][4]') se guarda como None.
- El parser no evalúa expresiones constantes: N, F y C quedan como nodos y el
  analizador semántico las reduce y valida (N > 0, F, C > 0).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Iterator, List, Optional, Union


# ---------------------------------------------------------------------------
# 1. Nodo base
# ---------------------------------------------------------------------------

# Campos del nodo base que no forman parte de la estructura del árbol
CAMPOS_ANOTACION = ("linea", "columna", "tipo_inferido", "simbolo")


@dataclass(kw_only=True)
class NodoAST:
    """
    Raíz de la jerarquía de nodos.

    :ivar linea: línea (base 1) del primer token de la construcción.
    :ivar columna: columna (base 1) del primer token de la construcción.
    :ivar tipo_inferido: tipo resuelto por el analizador semántico
                         ('int', 'float', 'bool', 'char', 'void', 'struct X'...).
    :ivar simbolo: entrada de la tabla de símbolos semántica asociada al nodo.
    """

    linea: int = field(default=0, compare=False)
    columna: int = field(default=0, compare=False)
    tipo_inferido: Optional[str] = field(default=None, compare=False)
    simbolo: Any = field(default=None, compare=False, repr=False)

    def hijos(self) -> Iterator["NodoAST"]:
        """Itera los nodos hijos directos en el orden de declaración de los campos."""
        for f in fields(self):
            if f.name in CAMPOS_ANOTACION:
                continue
            valor = getattr(self, f.name)
            if isinstance(valor, NodoAST):
                yield valor
            elif isinstance(valor, list):
                for elemento in valor:
                    if isinstance(elemento, NodoAST):
                        yield elemento

    def recorrer(self) -> Iterator["NodoAST"]:
        """Recorrido en preorden de todo el subárbol (incluye al propio nodo)."""
        yield self
        for hijo in self.hijos():
            yield from hijo.recorrer()


# ---------------------------------------------------------------------------
# 2. Tipos
# ---------------------------------------------------------------------------

TIPOS_PRIMITIVOS = ("int", "float", "bool", "char", "void")

# Categorías de EspecificadorTipo
CATEGORIA_PRIMITIVO = "primitivo"   # int, float, bool, char, void
CATEGORIA_STRUCT = "struct"         # struct Nombre
CATEGORIA_TDA = "tda"               # tda Nombre
CATEGORIA_ALIAS = "alias"           # nombre declarado con typedef (token TIPO_ID)


@dataclass
class EspecificadorTipo(NodoAST):
    """
    EspecificadorTipo ::= 'const'? TipoBase

    :ivar nombre: 'int', 'float', ... para primitivos; el nombre del TDA para
                  struct/tda; el nombre del alias para typedef.
    :ivar categoria: una de 'primitivo', 'struct', 'tda', 'alias'.
    :ivar es_const: True si lleva el calificador 'const'.
    """

    nombre: str
    categoria: str = CATEGORIA_PRIMITIVO
    es_const: bool = False

    @property
    def es_primitivo(self) -> bool:
        return self.categoria == CATEGORIA_PRIMITIVO

    @property
    def es_compuesto(self) -> bool:
        """True para struct y tda (el layout lo calcula el analizador semántico)."""
        return self.categoria in (CATEGORIA_STRUCT, CATEGORIA_TDA)

    def __str__(self) -> str:
        base = self.nombre
        if self.es_compuesto:
            base = f"{self.categoria} {self.nombre}"
        return f"const {base}" if self.es_const else base


# Una dimensión es una expresión o None (dimensión abierta '[]')
Dimension = Optional["Expresion"]


# ---------------------------------------------------------------------------
# 3. Programa y declaraciones externas (Integrante 2)
# ---------------------------------------------------------------------------

@dataclass
class ProgramaAST(NodoAST):
    """Programa ::= DeclaracionExterna*"""

    declaraciones: List["DeclaracionExterna"] = field(default_factory=list)

    def funciones(self) -> List["DefinicionFuncion"]:
        return [d for d in self.declaraciones if isinstance(d, DefinicionFuncion)]

    def tdas(self) -> List["DefinicionTDA"]:
        return [d for d in self.declaraciones if isinstance(d, DefinicionTDA)]

    def variables_globales(self) -> List["DeclaracionVariable"]:
        return [d for d in self.declaraciones if isinstance(d, DeclaracionVariable)]

    def typedefs(self) -> List["DefinicionTypedef"]:
        return [d for d in self.declaraciones if isinstance(d, DefinicionTypedef)]


@dataclass
class CampoTDA(NodoAST):
    """CampoTDA ::= EspecificadorTipo ID Dimensiones ';'"""

    tipo: EspecificadorTipo
    nombre: str
    dimensiones: List["Expresion"] = field(default_factory=list)

    @property
    def es_arreglo(self) -> bool:
        return len(self.dimensiones) == 1

    @property
    def es_matriz(self) -> bool:
        return len(self.dimensiones) == 2


@dataclass
class DefinicionTDA(NodoAST):
    """
    DefinicionTDA ::= ( 'struct' | 'tda' ) ID '{' CampoTDA+ '}' ';'

    :ivar clase: 'struct' o 'tda' (sinónimos; se conserva la palabra usada).
    """

    clase: str
    nombre: str
    campos: List[CampoTDA] = field(default_factory=list)

    def campo(self, nombre: str) -> Optional[CampoTDA]:
        for c in self.campos:
            if c.nombre == nombre:
                return c
        return None


@dataclass
class DefinicionTypedef(NodoAST):
    """DefinicionTypedef ::= 'typedef' EspecificadorTipo ID Dimensiones ';'"""

    tipo: EspecificadorTipo
    nombre: str
    dimensiones: List["Expresion"] = field(default_factory=list)


@dataclass
class ListaInicializadores(NodoAST):
    """'{' Inicializador ( ',' Inicializador )* ','? '}'  (anidable para matrices)"""

    elementos: List["Inicializador"] = field(default_factory=list)


@dataclass
class Declarador(NodoAST):
    """
    Declarador ::= ID DimensionesAbiertas ( '=' Inicializador )?

    Escalar: dimensiones == []. Vector: 1 dimensión. Matriz: 2 dimensiones.
    """

    nombre: str
    dimensiones: List[Dimension] = field(default_factory=list)
    inicializador: Optional["Inicializador"] = None

    @property
    def es_escalar(self) -> bool:
        return not self.dimensiones

    @property
    def es_arreglo(self) -> bool:
        return len(self.dimensiones) == 1

    @property
    def es_matriz(self) -> bool:
        return len(self.dimensiones) == 2


@dataclass
class DeclaracionVariable(NodoAST):
    """DeclaracionVariable ::= EspecificadorTipo Declarador ( ',' Declarador )* ';'"""

    tipo: EspecificadorTipo
    declaradores: List[Declarador] = field(default_factory=list)

    @property
    def nombres(self) -> List[str]:
        return [d.nombre for d in self.declaradores]


@dataclass
class Parametro(NodoAST):
    """
    Parametro ::= EspecificadorTipo ID? DimensionesAbiertas

    El nombre es opcional solo en prototipos: 'int f(int, float);'.
    """

    tipo: EspecificadorTipo
    nombre: Optional[str] = None
    dimensiones: List[Dimension] = field(default_factory=list)


@dataclass
class DefinicionFuncion(NodoAST):
    """
    DeclaracionFuncion ::= 'function'? EspecificadorTipo ID '(' Parametros? ')' ( Bloque | ';' )

    :ivar cuerpo: Bloque de la definición, o None si es un prototipo.
    :ivar con_function: True si se escribió la palabra opcional 'function'.

    La lista de parámetros '(void)' se normaliza a [] en el parser.
    """

    tipo_retorno: EspecificadorTipo
    nombre: str
    parametros: List[Parametro] = field(default_factory=list)
    cuerpo: Optional["Bloque"] = None
    con_function: bool = False

    @property
    def es_prototipo(self) -> bool:
        return self.cuerpo is None

    @property
    def aridad(self) -> int:
        return len(self.parametros)


# ---------------------------------------------------------------------------
# 4. Sentencias (las produce la Parte 2 del parser, Integrante 3)
# ---------------------------------------------------------------------------

@dataclass
class Bloque(NodoAST):
    """Bloque ::= '{' ElementoBloque* '}'"""

    elementos: List["ElementoBloque"] = field(default_factory=list)


@dataclass
class SentenciaVacia(NodoAST):
    """Sentencia ::= ';'"""


@dataclass
class SentenciaExpresion(NodoAST):
    """SentenciaSimple ::= Expresion   (p. ej. una llamada: f(x);)"""

    expresion: "Expresion"


@dataclass
class Asignacion(NodoAST):
    """
    SentenciaSimple ::= Expresion OpAsignacion Expresion

    :ivar operador: '=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<=', '>>='
    """

    destino: "Expresion"
    operador: str
    valor: "Expresion"


@dataclass
class IncrementoDecremento(NodoAST):
    """SentenciaSimple ::= Expresion ( '++' | '--' )"""

    destino: "Expresion"
    operador: str


@dataclass
class SentenciaIf(NodoAST):
    """SentenciaIf ::= 'if' '(' Expresion ')' 'then'? Sentencia ( 'else' Sentencia )?"""

    condicion: "Expresion"
    entonces: "Sentencia"
    sino: Optional["Sentencia"] = None
    con_then: bool = False


@dataclass
class ClausulaCase(NodoAST):
    """ClausulaCase ::= 'case' ConstanteCase ':' ElementoBloque*"""

    valor: "Expresion"
    cuerpo: List["ElementoBloque"] = field(default_factory=list)


@dataclass
class ClausulaDefault(NodoAST):
    """'default' ':' ElementoBloque*"""

    cuerpo: List["ElementoBloque"] = field(default_factory=list)


@dataclass
class SentenciaSwitch(NodoAST):
    """SentenciaSwitch ::= 'switch' '(' Expresion ')' '{' ClausulaCase* ( 'default' ':' ... )? '}'"""

    expresion: "Expresion"
    casos: List[ClausulaCase] = field(default_factory=list)
    defecto: Optional[ClausulaDefault] = None


@dataclass
class SentenciaWhile(NodoAST):
    """SentenciaWhile ::= 'while' '(' Expresion ')' Sentencia"""

    condicion: "Expresion"
    cuerpo: "Sentencia"


@dataclass
class SentenciaDoWhile(NodoAST):
    """SentenciaDoWhile ::= 'do' Sentencia 'while' '(' Expresion ')' ';'"""

    cuerpo: "Sentencia"
    condicion: "Expresion"


@dataclass
class SentenciaFor(NodoAST):
    """
    SentenciaFor ::= 'for' '(' ForInicial ';' Expresion? ';' SentenciaSimple? ')' Sentencia

    :ivar inicial: DeclaracionVariable ('int i = 0'), sentencia simple o None.
    """

    inicial: Optional["ElementoBloque"]
    condicion: Optional["Expresion"]
    paso: Optional["Sentencia"]
    cuerpo: "Sentencia"


@dataclass
class SentenciaReturn(NodoAST):
    """SentenciaReturn ::= 'return' Expresion? ';'"""

    valor: Optional["Expresion"] = None


@dataclass
class SentenciaBreak(NodoAST):
    """SentenciaBreak ::= 'break' ';'"""


@dataclass
class SentenciaContinue(NodoAST):
    """SentenciaContinue ::= 'continue' ';'"""


# ---------------------------------------------------------------------------
# 5. Expresiones
# ---------------------------------------------------------------------------

@dataclass
class ExpresionBinaria(NodoAST):
    """
    Operadores binarios de los niveles ExprOr .. ExprMultiplicativa.

    :ivar operador: lexema del operador ('+', '-', '*', '/', '%', '==', '!=',
                    '<', '<=', '>', '>=', '&&', '||', '&', '|', '^', '<<', '>>').
    """

    operador: str
    izquierda: "Expresion"
    derecha: "Expresion"


@dataclass
class ExpresionUnaria(NodoAST):
    """ExprUnaria ::= ( '+' | '-' | '!' | '~' ) ExprUnaria"""

    operador: str
    operando: "Expresion"


@dataclass
class Sizeof(NodoAST):
    """
    'sizeof' '(' ( EspecificadorTipo | Expresion ) ')'

    El analizador semántico lo reduce a una constante entera en bytes.
    """

    objetivo: Union[EspecificadorTipo, "Expresion"]


@dataclass
class AccesoIndice(NodoAST):
    """ExprPostfija '[' Expresion ']'   (m[i][j] = AccesoIndice(AccesoIndice(m, i), j))"""

    base: "Expresion"
    indice: "Expresion"


@dataclass
class AccesoCampo(NodoAST):
    """
    ExprPostfija '.' ID   (o '->' ID con por_puntero=True)

    Dir(s.campo) = Base(s) + offset(campo), con el offset relativo a la base
    de la instancia que calcula el analizador semántico.
    """

    base: "Expresion"
    campo: str
    por_puntero: bool = False


@dataclass
class LlamadaFuncion(NodoAST):
    """ExprPostfija '(' ( Expresion ( ',' Expresion )* )? ')'"""

    funcion: "Expresion"
    argumentos: List["Expresion"] = field(default_factory=list)

    @property
    def nombre(self) -> Optional[str]:
        """Nombre de la función llamada si el llamado es un identificador simple."""
        return self.funcion.nombre if isinstance(self.funcion, Identificador) else None


@dataclass
class Identificador(NodoAST):
    """ExprPrimaria ::= ID   (simbolo_idx apunta a la entrada de tablaID)"""

    nombre: str
    simbolo_idx: Optional[int] = field(default=None, compare=False)


@dataclass
class LiteralEntero(NodoAST):
    """
    ENTERO_DEC | ENTERO_HEX | ENTERO_BIN

    :ivar valor: valor con signo de 64 bits. Un patrón hexadecimal o binario
                 mayor que INT64_MAX se interpreta en complemento a dos
                 (0xFFFFFFFFFFFFFFFF -> -1), igual que en el registro.
    :ivar lexema: texto original del literal.
    :ivar simbolo_idx: índice de la entrada en tablaNum.
    """

    valor: int
    lexema: str = ""
    simbolo_idx: Optional[int] = field(default=None, compare=False)


@dataclass
class LiteralFlotante(NodoAST):
    """
    FLOTANTE (IEEE 754 binary64)

    El generador obtiene el patrón de 64 bits desde tablaNum con simbolo_idx
    (atributo patron_ieee754_hex).
    """

    valor: float
    lexema: str = ""
    simbolo_idx: Optional[int] = field(default=None, compare=False)


@dataclass
class LiteralCadena(NodoAST):
    """STRING (valor sin comillas y con los escapes resueltos)"""

    valor: str
    lexema: str = ""
    simbolo_idx: Optional[int] = field(default=None, compare=False)


@dataclass
class LiteralCaracter(NodoAST):
    """CHAR_LITERAL (valor: el carácter con el escape resuelto)"""

    valor: str
    lexema: str = ""


@dataclass
class LiteralBooleano(NodoAST):
    """'true' | 'false'"""

    valor: bool


@dataclass
class CoercionTipo(NodoAST):
    """
    Conversión implícita insertada por el analizador semántico (nunca por el
    parser). Ejemplo: CoercionTipo('int', 'float', e) -> CALL FCONV_INT_A_FLOAT.
    """

    origen: str
    destino: str
    expresion: "Expresion"


# ---------------------------------------------------------------------------
# 6. Alias de tipos para anotaciones
# ---------------------------------------------------------------------------

Expresion = Union[
    ExpresionBinaria, ExpresionUnaria, Sizeof, AccesoIndice, AccesoCampo,
    LlamadaFuncion, Identificador, LiteralEntero, LiteralFlotante,
    LiteralCadena, LiteralCaracter, LiteralBooleano, CoercionTipo,
]
Inicializador = Union[Expresion, ListaInicializadores]
Sentencia = Union[
    Bloque, SentenciaVacia, SentenciaExpresion, Asignacion, IncrementoDecremento,
    SentenciaIf, SentenciaSwitch, SentenciaWhile, SentenciaDoWhile, SentenciaFor,
    SentenciaReturn, SentenciaBreak, SentenciaContinue,
]
ElementoBloque = Union[DeclaracionVariable, Sentencia]
DeclaracionExterna = Union[DefinicionTDA, DefinicionTypedef, DefinicionFuncion, DeclaracionVariable]

NODOS_EXPRESION = (
    ExpresionBinaria, ExpresionUnaria, Sizeof, AccesoIndice, AccesoCampo,
    LlamadaFuncion, Identificador, LiteralEntero, LiteralFlotante,
    LiteralCadena, LiteralCaracter, LiteralBooleano, CoercionTipo,
)


def es_expresion(nodo: Any) -> bool:
    return isinstance(nodo, NODOS_EXPRESION)


# ---------------------------------------------------------------------------
# 7. Patrón visitante
# ---------------------------------------------------------------------------

class VisitanteAST:
    """
    Despacha visitar(nodo) al método visitar_<NombreClase>(nodo).

    Si la subclase no define el método, se usa visitar_generico, que visita
    los hijos en orden. El analizador semántico y el generador de código
    heredan de esta clase.
    """

    def visitar(self, nodo: Optional[NodoAST]) -> Any:
        if nodo is None:
            return None
        metodo = getattr(self, f"visitar_{type(nodo).__name__}", self.visitar_generico)
        return metodo(nodo)

    def visitar_generico(self, nodo: NodoAST) -> Any:
        for hijo in nodo.hijos():
            self.visitar(hijo)
        return None


# ---------------------------------------------------------------------------
# 8. Volcado del árbol en texto
# ---------------------------------------------------------------------------

def _resumen(nodo: NodoAST) -> str:
    """Nombre de la clase con sus atributos escalares (sin hijos ni anotaciones)."""
    if isinstance(nodo, EspecificadorTipo):
        texto = f"EspecificadorTipo '{nodo}'"
    else:
        partes = []
        for f in fields(nodo):
            if f.name in CAMPOS_ANOTACION or f.name == "simbolo_idx":
                continue
            valor = getattr(nodo, f.name)
            if isinstance(valor, (NodoAST, list)) or valor is None:
                continue
            if isinstance(valor, bool) and not valor:
                continue
            partes.append(f"{f.name}={valor!r}")
        texto = type(nodo).__name__
        if partes:
            texto += "(" + ", ".join(partes) + ")"
    if nodo.tipo_inferido:
        texto += f" : {nodo.tipo_inferido}"
    if nodo.linea:
        texto += f"  @{nodo.linea}:{nodo.columna}"
    return texto


def _hijos_etiquetados(nodo: NodoAST):
    """Pares (etiqueta, hijo) incluyendo las dimensiones abiertas (None)."""
    for f in fields(nodo):
        if f.name in CAMPOS_ANOTACION:
            continue
        valor = getattr(nodo, f.name)
        if isinstance(valor, NodoAST):
            yield f.name, valor
        elif isinstance(valor, list):
            for i, elemento in enumerate(valor):
                if isinstance(elemento, NodoAST) or (elemento is None and f.name == "dimensiones"):
                    yield f"{f.name}[{i}]", elemento


def formatear_ast(nodo: NodoAST) -> str:
    """
    Devuelve el árbol en texto con guías de rama, por ejemplo:

        ProgramaAST
        └─ declaraciones[0]: DefinicionTDA(clase='struct', nombre='Punto')  @1:1
           └─ campos[0]: CampoTDA(nombre='x')  @1:16
              └─ tipo: EspecificadorTipo 'float'  @1:16
    """
    lineas = [_resumen(nodo)]

    def rec(actual: NodoAST, prefijo: str) -> None:
        hijos = list(_hijos_etiquetados(actual))
        for i, (etiqueta, hijo) in enumerate(hijos):
            ultimo = i == len(hijos) - 1
            rama = "└─ " if ultimo else "├─ "
            texto = "[] (dimension abierta)" if hijo is None else _resumen(hijo)
            lineas.append(f"{prefijo}{rama}{etiqueta}: {texto}")
            if hijo is not None:
                rec(hijo, prefijo + ("   " if ultimo else "│  "))

    rec(nodo, "")
    return "\n".join(lineas)
