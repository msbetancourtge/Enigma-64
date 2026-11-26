"""
Analizador Semántico y Tabla de Símbolos Jerárquica del Compilador SPL (Enigma-64).
Fase 2: Análisis Semántico (Taller 02, Literales d y e).

Responsabilidad: Integrante 4 (Juan Luis Vergara Novoa)
Contrato de entrada y salida (Matriz de Modularidad, etapa 4):
- Entrada: ProgramaAST (spl/compilador/ast_nodos.py) + GestorTablasSimbolos (opcional).
- Transformación:
    1. Construcción de la pila de ámbitos (global -> función -> bloque / for).
    2. Resolución de tipos primitivos, alias (typedef) y Tipos de Datos Abstractos
       (struct / tda) con cálculo de layouts y offsets alineados a 8 bytes.
    3. Asignación de memoria lógica relativa:
       - Globales: desplazamiento positivo relativo a BASE_DATOS_GLOBAL (0x00201000).
       - Locales: desplazamiento negativo [BP - k] relativo a R7/BP (para ENTER).
       - Parámetros: argumentos 1..4 en R1..R4; 5.º en adelante en [BP + 16 + 8*(i-4)].
       - Campos de TDA: offset positivo relativo a Base(instancia).
       - Matrices 2D: cabecera [Base - 16] = F y [Base - 8] = C (formato mat.asm).
    4. Verificación estricta de tipos, lvalues, const, aridad, prototipos, return,
       case duplicados y contextos de break/continue.
    5. Coerción automática int -> float IEEE 754 binary64 mediante inserción explícita
       de nodos CoercionTipo('int', 'float', expr) en el AST (rechazo de float -> int).
- Salida: ResultadoSemantico(ast anotado, TablaSimbolosSemantica, List[ErrorSemantico]).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from spl.compilador.ast_nodos import (
    CATEGORIA_ALIAS,
    CATEGORIA_PRIMITIVO,
    CATEGORIA_STRUCT,
    CATEGORIA_TDA,
    AccesoCampo,
    AccesoIndice,
    Asignacion,
    Bloque,
    CampoTDA,
    ClausulaCase,
    ClausulaDefault,
    CoercionTipo,
    DeclaracionVariable,
    Declarador,
    DefinicionFuncion,
    DefinicionTDA,
    DefinicionTypedef,
    EspecificadorTipo,
    Expresion,
    ExpresionBinaria,
    ExpresionUnaria,
    Identificador,
    IncrementoDecremento,
    ListaInicializadores,
    LiteralBooleano,
    LiteralCadena,
    LiteralCaracter,
    LiteralEntero,
    LiteralFlotante,
    LlamadaFuncion,
    NodoAST,
    Parametro,
    ProgramaAST,
    SentenciaBreak,
    SentenciaContinue,
    SentenciaDoWhile,
    SentenciaExpresion,
    SentenciaFor,
    SentenciaIf,
    SentenciaReturn,
    SentenciaSwitch,
    SentenciaVacia,
    SentenciaWhile,
    Sizeof,
    VisitanteAST,
)
from spl.compilador.tablas import GestorTablasSimbolos

# ---------------------------------------------------------------------------
# Constantes arquitectónicas de memoria para Enigma-64
# ---------------------------------------------------------------------------

BASE_DATOS_GLOBAL: int = 0x00201000
TAMANO_PALABRA: int = 8
TAMANO_CABECERA_MATRIZ: int = 16  # [Base - 16] = F, [Base - 8] = C

TIPOS_ENTEROS = frozenset({"int", "char", "bool"})
TIPOS_NUMERICOS = frozenset({"int", "float", "char", "bool"})

OPERADORES_ARITMETICOS_BIN = frozenset({"+", "-", "*", "/"})
OPERADORES_ENTEROS_ESTRICTOS = frozenset({"%", "&", "|", "^", "<<", ">>"})
OPERADORES_RELACIONALES_BIN = frozenset({"<", "<=", ">", ">="})
OPERADORES_IGUALDAD_BIN = frozenset({"==", "!="})
OPERADORES_LOGICOS_BIN = frozenset({"&&", "||"})

MAPA_ASIGNACION_COMPUESTA: Dict[str, str] = {
    "+=": "+",
    "-=": "-",
    "*=": "*",
    "/=": "/",
    "%=": "%",
    "&=": "&",
    "|=": "|",
    "^=": "^",
    "<<=": "<<",
    ">>=": ">>",
}


# ---------------------------------------------------------------------------
# 1. Errores semánticos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ErrorSemantico:
    """Representa un error detectado durante el análisis semántico."""

    linea: int
    columna: int
    mensaje: str
    simbolo: str = ""

    def __str__(self) -> str:
        sufijo = f" ('{self.simbolo}')" if self.simbolo and self.simbolo not in self.mensaje else ""
        return f"ERROR SEMANTICO (linea {self.linea}, columna {self.columna}): {self.mensaje}{sufijo}"


# ---------------------------------------------------------------------------
# 2. Modelo de tipos, descriptores de TDA, símbolos y ámbitos
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TipoResuelto:
    """
    Representación canónica de un tipo ya resuelto (sin alias typedef pendientes).

    :ivar base: 'int', 'float', 'bool', 'char', 'void', 'string', o el nombre del TDA.
    :ivar dimensiones: tupla de dimensiones (vacía = escalar, 1 elem = vector 1D,
                       2 elems = matriz 2D; None indica dimensión abierta en parámetros).
    :ivar es_const: True si el símbolo o tipo tiene calificador const.
    :ivar clase_tda: 'struct' o 'tda' si base es un TDA; None para primitivos/string.
    """

    base: str
    dimensiones: Tuple[Optional[int], ...] = ()
    es_const: bool = False
    clase_tda: Optional[str] = None

    @property
    def es_tda(self) -> bool:
        return self.clase_tda is not None

    @property
    def es_primitivo(self) -> bool:
        return not self.es_tda and self.base != "string"

    @property
    def es_escalar(self) -> bool:
        return len(self.dimensiones) == 0

    @property
    def es_arreglo(self) -> bool:
        return len(self.dimensiones) == 1

    @property
    def es_matriz(self) -> bool:
        return len(self.dimensiones) == 2

    @property
    def es_void(self) -> bool:
        return self.base == "void" and self.es_escalar and not self.es_tda

    @property
    def es_entero(self) -> bool:
        return not self.es_tda and self.es_escalar and self.base in TIPOS_ENTEROS

    @property
    def es_flotante(self) -> bool:
        return not self.es_tda and self.es_escalar and self.base == "float"

    @property
    def es_numerico(self) -> bool:
        return not self.es_tda and self.es_escalar and self.base in TIPOS_NUMERICOS

    @property
    def es_string(self) -> bool:
        return not self.es_tda and self.base == "string" and self.es_escalar

    def sin_const(self) -> "TipoResuelto":
        if not self.es_const:
            return self
        return TipoResuelto(
            base=self.base,
            dimensiones=self.dimensiones,
            es_const=False,
            clase_tda=self.clase_tda,
        )

    def con_const(self, es_const: bool = True) -> "TipoResuelto":
        return TipoResuelto(
            base=self.base,
            dimensiones=self.dimensiones,
            es_const=es_const,
            clase_tda=self.clase_tda,
        )

    def tamano_elemento(self, tipos_tda: Dict[str, "DescriptorTipoTDA"]) -> int:
        if self.es_tda:
            desc = tipos_tda.get(self.base)
            return desc.tamano_bytes if desc is not None else TAMANO_PALABRA
        if self.base == "void":
            return 0
        return TAMANO_PALABRA

    def tamano_bytes(self, tipos_tda: Dict[str, "DescriptorTipoTDA"]) -> int:
        """
        Tamaño en bytes alineado a 8 bytes según el layout oficial de Enigma-64:
        - Escalar primitivo: 8 B
        - TDA escalar: tam(TDA)
        - Vector T[N]: N * tam(T)
        - Matriz T[F][C]: 16 + F * C * tam(T)  (incluye cabecera [B-16]=F, [B-8]=C)
        - Parámetro con dimensión abierta (None): 8 B (puntero/referencia)
        """
        tam_elem = self.tamano_elemento(tipos_tda)
        if not self.dimensiones:
            return tam_elem
        if any(d is None for d in self.dimensiones):
            return TAMANO_PALABRA
        if len(self.dimensiones) == 1:
            return int(self.dimensiones[0]) * tam_elem
        filas, cols = int(self.dimensiones[0]), int(self.dimensiones[1])
        return TAMANO_CABECERA_MATRIZ + (filas * cols * tam_elem)

    def mismo_tipo(self, otro: "TipoResuelto", ignorar_const: bool = True) -> bool:
        """Compara igualdad estructural (struct X y tda X son sinónimos)."""
        if not ignorar_const and self.es_const != otro.es_const:
            return False
        return (
            self.base == otro.base
            and self.es_tda == otro.es_tda
            and self.dimensiones == otro.dimensiones
        )

    def __str__(self) -> str:
        nombre_base = f"{self.clase_tda} {self.base}" if self.es_tda else self.base
        dims = "".join(f"[{'' if d is None else d}]" for d in self.dimensiones)
        return f"{nombre_base}{dims}"


TIPO_INT = TipoResuelto("int")
TIPO_FLOAT = TipoResuelto("float")
TIPO_BOOL = TipoResuelto("bool")
TIPO_CHAR = TipoResuelto("char")
TIPO_VOID = TipoResuelto("void")
TIPO_STRING = TipoResuelto("string")
TIPO_ERROR = TipoResuelto("<error>")


@dataclass
class DescriptorCampo:
    """Describe un campo de un Tipo de Dato Abstracto y su offset relativo a la instancia."""

    nombre: str
    tipo: TipoResuelto
    offset: int
    tamano_bytes: int
    offset_cabecera: Optional[int] = None


@dataclass
class DescriptorTipoTDA:
    """Layout completo en memoria de una estructura struct/tda (alineado a 8 bytes)."""

    nombre: str
    clase: str = CATEGORIA_STRUCT
    campos: List[DescriptorCampo] = field(default_factory=list)
    tamano_bytes: int = 0
    completo: bool = False
    _mapa_campos: Dict[str, DescriptorCampo] = field(default_factory=dict, repr=False)

    def agregar_campo(self, campo: DescriptorCampo) -> None:
        self.campos.append(campo)
        self._mapa_campos[campo.nombre] = campo

    def obtener_campo(self, nombre: str) -> Optional[DescriptorCampo]:
        return self._mapa_campos.get(nombre)

    def offset(self, nombre: str) -> int:
        campo = self._mapa_campos.get(nombre)
        if campo is None:
            raise KeyError(f"El TDA '{self.nombre}' no posee el campo '{nombre}'")
        return campo.offset


@dataclass
class DescriptorAlias:
    """Alias definido mediante typedef."""

    nombre: str
    tipo: TipoResuelto


@dataclass
class SimboloVariable:
    """
    Entrada semántica de una variable (global, local o parámetro) con trazabilidad
    explícita de ubicación y base de direccionamiento relativo.
    """

    nombre: str
    tipo: TipoResuelto
    es_const: bool
    ubicacion: str          # 'global' | 'local' | 'parametro'
    desplazamiento: int     # offset respecto a base_relativa (o índice 0..3 en R1..R4)
    base_relativa: str      # '0x00201000' | 'R7/BP' | 'R1..R4'
    tamano_bytes: int
    offset_cabecera: Optional[int] = None
    por_referencia: bool = False
    valor_constante: Optional[Any] = None
    linea: int = 0
    columna: int = 0

    @property
    def direccion_absoluta(self) -> Optional[int]:
        if self.ubicacion == "global":
            return BASE_DATOS_GLOBAL + self.desplazamiento
        return None

    def referencia_relativa(self) -> str:
        if self.ubicacion == "global":
            return (
                f"0x{BASE_DATOS_GLOBAL + self.desplazamiento:08X} "
                f"(base 0x{BASE_DATOS_GLOBAL:08X} + {self.desplazamiento})"
            )
        if self.ubicacion == "local":
            signo = "-" if self.desplazamiento < 0 else "+"
            return f"[BP {signo} {abs(self.desplazamiento)}] (relativo a R7/BP)"
        if self.base_relativa == "R1..R4":
            return f"R{self.desplazamiento + 1} (parametro #{self.desplazamiento + 1})"
        return f"[BP + {self.desplazamiento}] (relativo a R7/BP)"


@dataclass
class FirmaFuncion:
    """Firma y metadatos de marco de activación de una función SPL."""

    nombre: str
    retorno: TipoResuelto
    parametros: List[Tuple[Optional[str], TipoResuelto]] = field(default_factory=list)
    definida: bool = False
    es_intrinseca: bool = False
    tam_locales: int = 0
    simbolos_parametros: List[SimboloVariable] = field(default_factory=list)
    simbolos_locales: List[SimboloVariable] = field(default_factory=list)
    linea: int = 0
    columna: int = 0

    @property
    def aridad(self) -> int:
        return len(self.parametros)


class TablaAmbitos:
    """Pila de ámbitos léxicos (global -> función -> bloques anidados)."""

    def __init__(self) -> None:
        self.pila: List[Dict[str, SimboloVariable]] = [{}]

    @property
    def profundidad(self) -> int:
        return len(self.pila)

    @property
    def es_global(self) -> bool:
        return len(self.pila) == 1

    def abrir(self) -> None:
        self.pila.append({})

    def cerrar(self) -> Dict[str, SimboloVariable]:
        if len(self.pila) <= 1:
            raise RuntimeError("No se puede cerrar el ambito global")
        return self.pila.pop()

    def insertar(self, simbolo: SimboloVariable) -> None:
        self.pila[-1][simbolo.nombre] = simbolo

    def buscar_local(self, nombre: str) -> Optional[SimboloVariable]:
        return self.pila[-1].get(nombre)

    def buscar(self, nombre: str) -> Optional[SimboloVariable]:
        for ambito in reversed(self.pila):
            if nombre in ambito:
                return ambito[nombre]
        return None


@dataclass
class TablaSimbolosSemantica:
    """Contenedor unificado de tipos TDA, alias, funciones y ámbitos del programa."""

    tipos: Dict[str, DescriptorTipoTDA] = field(default_factory=dict)
    alias: Dict[str, DescriptorAlias] = field(default_factory=dict)
    funciones: Dict[str, FirmaFuncion] = field(default_factory=dict)
    ambitos: TablaAmbitos = field(default_factory=TablaAmbitos)
    globales_ordenados: List[SimboloVariable] = field(default_factory=list)
    tamano_datos_globales: int = 0

    def generar_informe(self) -> str:
        """Genera un volcado legible de TDAs, globales y funciones con offsets relativos."""
        lineas = [
            "========================================================================================",
            "                  TABLA DE SIMBOLOS SEMANTICA Y LAYOUTS (ENIGMA-64)                     ",
            "========================================================================================",
        ]
        lineas.append("\n* Tipos de Datos Abstractos (TDA / struct):")
        if not self.tipos:
            lineas.append("  (ninguno)")
        else:
            for tda in self.tipos.values():
                lineas.append(f"  - {tda.clase} {tda.nombre} (tamano = {tda.tamano_bytes} bytes):")
                for c in tda.campos:
                    cab = f", cabecera=+{c.offset_cabecera}" if c.offset_cabecera is not None else ""
                    lineas.append(
                        f"      +{c.offset:<4} {c.nombre:<22} : {str(c.tipo):<20} ({c.tamano_bytes} B{cab})"
                    )

        lineas.append(
            f"\n* Variables Globales (.data relativo a 0x{BASE_DATOS_GLOBAL:08X}, "
            f"total = {self.tamano_datos_globales} bytes):"
        )
        if not self.globales_ordenados:
            lineas.append("  (ninguna)")
        else:
            for g in self.globales_ordenados:
                const_txt = "const " if g.es_const else ""
                lineas.append(
                    f"  - {g.nombre:<22} : {const_txt}{str(g.tipo):<18} -> {g.referencia_relativa()} ({g.tamano_bytes} B)"
                )

        lineas.append("\n* Funciones definidas:")
        funcs_usuario = [f for f in self.funciones.values() if not f.es_intrinseca]
        if not funcs_usuario:
            lineas.append("  (ninguna)")
        else:
            for fn in funcs_usuario:
                params = ", ".join(f"{t} {n or '_'}" for n, t in fn.parametros)
                estado = "definida" if fn.definida else "solo prototipo"
                lineas.append(
                    f"  - {fn.retorno} {fn.nombre}({params}) [{estado}, ENTER {fn.tam_locales}]"
                )
                for loc in fn.simbolos_locales:
                    lineas.append(
                        f"      local {loc.nombre:<18} : {str(loc.tipo):<16} -> {loc.referencia_relativa()}"
                    )
        lineas.append("========================================================================================")
        return "\n".join(lineas)


@dataclass
class ResultadoSemantico:
    """Salida formal del módulo Analizador Semántico (etapa 4 de la Matriz de Modularidad)."""

    ast: ProgramaAST
    tabla: TablaSimbolosSemantica
    errores: List[ErrorSemantico] = field(default_factory=list)

    @property
    def exito(self) -> bool:
        return len(self.errores) == 0


# ---------------------------------------------------------------------------
# 3. Analizador Semántico (VisitanteAST)
# ---------------------------------------------------------------------------

class AnalizadorSemantico(VisitanteAST):
    """
    Recorre el AST construido por CompiladorParser, valida reglas de ámbitos,
    tipos, TDA, arreglos/matrices, control de flujo y funciones, inserta nodos
    CoercionTipo('int', 'float') para aritmética IEEE 754 y anota cada nodo con
    tipo_inferido y simbolo.
    """

    def __init__(
        self,
        tablas_lexicas: Optional[GestorTablasSimbolos] = None,
        exigir_main: bool = True,
    ) -> None:
        self.tablas_lexicas = tablas_lexicas
        self.exigir_main = exigir_main
        self.tabla = TablaSimbolosSemantica()
        self.errores: List[ErrorSemantico] = []

        # Estado contextual durante el recorrido
        self._funcion_actual: Optional[FirmaFuncion] = None
        self._offset_local_actual: int = 0
        self._tiene_return_en_funcion: bool = False
        self._profundidad_bucle: int = 0
        self._profundidad_switch: int = 0

    def analizar(self, programa: ProgramaAST) -> ResultadoSemantico:
        """Ejecuta el análisis semántico completo sobre un ProgramaAST."""
        self.tabla = TablaSimbolosSemantica()
        self.errores = []
        self._funcion_actual = None
        self._offset_local_actual = 0
        self._tiene_return_en_funcion = False
        self._profundidad_bucle = 0
        self._profundidad_switch = 0

        self._registrar_intrinsecas()
        self.visitar(programa)
        return ResultadoSemantico(
            ast=programa,
            tabla=self.tabla,
            errores=list(self.errores),
        )

    # --- Helpers de reporte y entorno ----------------------------------------

    def _registrar_intrinsecas(self) -> None:
        """Registra funciones intrínsecas estándar de E/S MMIO y FPU del entorno SPL."""
        intrinsecas = [
            FirmaFuncion("string_log", TIPO_VOID, [("mensaje", TIPO_STRING)], definida=True, es_intrinseca=True),
            FirmaFuncion("print_int", TIPO_VOID, [("valor", TIPO_INT)], definida=True, es_intrinseca=True),
            FirmaFuncion("print_float", TIPO_VOID, [("valor", TIPO_FLOAT)], definida=True, es_intrinseca=True),
            FirmaFuncion("sqrt_f", TIPO_FLOAT, [("x", TIPO_FLOAT)], definida=True, es_intrinseca=True),
        ]
        for firma in intrinsecas:
            self.tabla.funciones[firma.nombre] = firma

    def _reportar(self, nodo: NodoAST, mensaje: str, simbolo: str = "") -> None:
        self.errores.append(
            ErrorSemantico(
                linea=getattr(nodo, "linea", 0),
                columna=getattr(nodo, "columna", 0),
                mensaje=mensaje,
                simbolo=simbolo,
            )
        )

    @staticmethod
    def _anotar(nodo: NodoAST, tipo: TipoResuelto, simbolo: Any = None) -> TipoResuelto:
        nodo.tipo_inferido = str(tipo)
        if simbolo is not None:
            nodo.simbolo = simbolo
        return tipo

    @staticmethod
    def _coercer_a_float(expr: Expresion) -> CoercionTipo:
        return CoercionTipo(
            origen="int",
            destino="float",
            expresion=expr,
            linea=expr.linea,
            columna=expr.columna,
            tipo_inferido="float",
        )

    def _compatibilidad_asignacion(
        self,
        origen: TipoResuelto,
        destino: TipoResuelto,
        expr: Expresion,
        nodo_error: NodoAST,
        contexto: str = "asignacion",
    ) -> Tuple[Expresion, bool]:
        """
        Verifica si 'origen' puede asignarse a 'destino'.
        Si origen es entero y destino es float, devuelve (CoercionTipo, True).
        Si origen es float y destino es entero, reporta error (sin truncamiento silencioso).
        """
        if origen == TIPO_ERROR or destino == TIPO_ERROR:
            return expr, False

        if origen.es_void or destino.es_void:
            self._reportar(
                nodo_error,
                f"tipo 'void' no es valido en {contexto} (se encontro '{origen}' para '{destino}')",
            )
            return expr, False

        # Cadenas hacia string o char[]
        if destino.es_string and (origen.es_string or (origen.base == "char" and origen.es_arreglo)):
            return expr, True

        # Exactamente el mismo tipo (escalares, TDA por copia o arreglos compatibles)
        if origen.mismo_tipo(destino, ignorar_const=True):
            return expr, True

        # Escalares enteros compatibles (int, char, bool comparten palabra de 64 bits)
        if origen.es_entero and destino.es_entero:
            return expr, True

        # Coerción automática int/char/bool -> float IEEE 754
        if origen.es_entero and destino.es_flotante:
            return self._coercer_a_float(expr), True

        # Prohibición explícita de truncamiento implícito float -> int
        if origen.es_flotante and destino.es_entero:
            self._reportar(
                nodo_error,
                f"no se puede convertir implicitamente 'float' a '{destino}' en {contexto}",
            )
            return expr, False

        self._reportar(
            nodo_error,
            f"tipos incompatibles en {contexto}: no se puede asignar '{origen}' a '{destino}'",
        )
        return expr, False

    def _compatibilidad_parametro(
        self,
        arg_tipo: TipoResuelto,
        param_tipo: TipoResuelto,
        arg_expr: Expresion,
        nodo_error: NodoAST,
        indice_param: int,
        nombre_fn: str,
    ) -> Expresion:
        """Verifica compatibilidad de un argumento frente al tipo del parámetro."""
        if arg_tipo == TIPO_ERROR or param_tipo == TIPO_ERROR:
            return arg_expr

        # Arreglos y matrices (pasados por referencia: la 1.ª dim puede ser abierta)
        if param_tipo.dimensiones:
            if not arg_tipo.dimensiones:
                self._reportar(
                    nodo_error,
                    f"argumento #{indice_param} de '{nombre_fn}': se esperaba '{param_tipo}' y se recibio '{arg_tipo}'",
                )
                return arg_expr
            if arg_tipo.base != param_tipo.base or arg_tipo.es_tda != param_tipo.es_tda:
                self._reportar(
                    nodo_error,
                    f"argumento #{indice_param} de '{nombre_fn}': tipo base incompatible '{arg_tipo}' para '{param_tipo}'",
                )
                return arg_expr
            if len(arg_tipo.dimensiones) != len(param_tipo.dimensiones):
                self._reportar(
                    nodo_error,
                    f"argumento #{indice_param} de '{nombre_fn}': numero de dimensiones incompatible '{arg_tipo}' para '{param_tipo}'",
                )
                return arg_expr
            for dim_arg, dim_par in zip(arg_tipo.dimensiones, param_tipo.dimensiones):
                if dim_par is not None and dim_arg is not None and dim_arg != dim_par:
                    self._reportar(
                        nodo_error,
                        f"argumento #{indice_param} de '{nombre_fn}': dimension incompatible '{arg_tipo}' para '{param_tipo}'",
                    )
                    return arg_expr
            return arg_expr

        expr_res, _ = self._compatibilidad_asignacion(
            arg_tipo,
            param_tipo,
            arg_expr,
            nodo_error,
            contexto=f"argumento #{indice_param} de '{nombre_fn}'",
        )
        return expr_res

    def _resolver_especificador_tipo(
        self,
        esp: EspecificadorTipo,
        dimensiones_extra: Sequence[Optional[int]] = (),
        permitir_void: bool = False,
    ) -> TipoResuelto:
        """Resuelve un EspecificadorTipo (primitivo, struct/tda o alias typedef) y compone dimensiones."""
        es_const = esp.es_const

        if esp.categoria == CATEGORIA_PRIMITIVO:
            if esp.nombre == "void" and not permitir_void:
                self._reportar(esp, "el tipo 'void' solo es valido como retorno de funcion")
                return TIPO_ERROR
            base_tipo = TipoResuelto(base=esp.nombre, dimensiones=(), es_const=es_const)
        elif esp.categoria in (CATEGORIA_STRUCT, CATEGORIA_TDA):
            desc = self.tabla.tipos.get(esp.nombre)
            if desc is None:
                self._reportar(esp, f"TDA no declarado: '{esp.nombre}'", simbolo=esp.nombre)
                return TIPO_ERROR
            base_tipo = TipoResuelto(
                base=desc.nombre,
                dimensiones=(),
                es_const=es_const,
                clase_tda=desc.clase,
            )
            esp.simbolo = desc
        elif esp.categoria == CATEGORIA_ALIAS:
            alias = self.tabla.alias.get(esp.nombre)
            if alias is None:
                self._reportar(esp, f"alias typedef no declarado: '{esp.nombre}'", simbolo=esp.nombre)
                return TIPO_ERROR
            if alias.tipo.es_void and not permitir_void:
                self._reportar(esp, f"el alias '{esp.nombre}' resuelve a 'void' y no es valido aqui")
                return TIPO_ERROR
            base_tipo = TipoResuelto(
                base=alias.tipo.base,
                dimensiones=alias.tipo.dimensiones,
                es_const=es_const or alias.tipo.es_const,
                clase_tda=alias.tipo.clase_tda,
            )
            esp.simbolo = alias
        else:
            self._reportar(esp, f"categoria de tipo desconocida: '{esp.categoria}'")
            return TIPO_ERROR

        # Regla 4.3 del diseño: las dimensiones del alias van a la DERECHA de las del declarador.
        # Ej: typedef int Vec[4]; Vec m[3]; -> int[3][4]
        dims_finales = tuple(dimensiones_extra) + base_tipo.dimensiones
        if len(dims_finales) > 2:
            self._reportar(
                esp,
                f"solo se admiten vectores 1D y matrices 2D (se obtuvieron {len(dims_finales)} dimensiones)",
            )
            dims_finales = dims_finales[:2]

        resuelto = TipoResuelto(
            base=base_tipo.base,
            dimensiones=dims_finales,
            es_const=base_tipo.es_const,
            clase_tda=base_tipo.clase_tda,
        )
        esp.tipo_inferido = str(resuelto)
        return resuelto

    def _evaluar_constante_entera(self, expr: Optional[Expresion]) -> Optional[int]:
        """Evalúa una expresión constante entera en tiempo de compilación (para dimensiones, case, const)."""
        if expr is None:
            return None
        if isinstance(expr, LiteralEntero):
            self._anotar(expr, TIPO_INT)
            return expr.valor
        if isinstance(expr, LiteralBooleano):
            self._anotar(expr, TIPO_BOOL)
            return 1 if expr.valor else 0
        if isinstance(expr, LiteralCaracter):
            self._anotar(expr, TIPO_CHAR)
            return ord(expr.valor[0]) if expr.valor else 0
        if isinstance(expr, Identificador):
            sim = self.tabla.ambitos.buscar(expr.nombre)
            if sim is not None and sim.es_const and sim.tipo.es_entero and sim.valor_constante is not None:
                self._anotar(expr, sim.tipo, sim)
                return int(sim.valor_constante)
            return None
        if isinstance(expr, Sizeof):
            self.visitar_Sizeof(expr)
            return expr.simbolo if isinstance(expr.simbolo, int) else None
        if isinstance(expr, ExpresionUnaria):
            val = self._evaluar_constante_entera(expr.operando)
            if val is None:
                return None
            if expr.operador == "+":
                return +val
            if expr.operador == "-":
                return -val
            if expr.operador == "~":
                return ~val
            if expr.operador == "!":
                return 0 if val else 1
            return None
        if isinstance(expr, ExpresionBinaria):
            izq = self._evaluar_constante_entera(expr.izquierda)
            der = self._evaluar_constante_entera(expr.derecha)
            if izq is None or der is None:
                return None
            op = expr.operador
            if op == "+":
                return izq + der
            if op == "-":
                return izq - der
            if op == "*":
                return izq * der
            if op == "/" and der != 0:
                return int(izq / der)
            if op == "%" and der != 0:
                return izq % der
            if op == "&":
                return izq & der
            if op == "|":
                return izq | der
            if op == "^":
                return izq ^ der
            if op == "<<" and der >= 0:
                return izq << der
            if op == ">>" and der >= 0:
                return izq >> der
        return None

    def _evaluar_dimensiones(
        self,
        dimensiones: Sequence[Optional[Expresion]],
        nodo_ref: NodoAST,
        permitir_abierta_primera: bool = False,
        permitir_abiertas_todas: bool = False,
    ) -> Tuple[Optional[int], ...]:
        """Evalúa una lista de expresiones de dimensión y exige enteros constantes > 0."""
        resultado: List[Optional[int]] = []
        for idx, dim_expr in enumerate(dimensiones):
            if dim_expr is None:
                if permitir_abiertas_todas or (permitir_abierta_primera and idx == 0):
                    resultado.append(None)
                else:
                    self._reportar(
                        nodo_ref,
                        f"dimension #{idx + 1} abierta '[]' no permitida en esta declaracion",
                    )
                    resultado.append(1)
                continue
            valor = self._evaluar_constante_entera(dim_expr)
            if valor is None:
                self._reportar(
                    dim_expr,
                    f"la dimension #{idx + 1} debe ser una expresion constante entera",
                )
                resultado.append(1)
            elif valor <= 0:
                self._reportar(
                    dim_expr,
                    f"la dimension #{idx + 1} debe ser estrictamente positiva (se obtuvo {valor})",
                )
                resultado.append(1)
            else:
                resultado.append(valor)
        return tuple(resultado)

    def _es_lvalue(self, expr: Expresion) -> bool:
        if isinstance(expr, Identificador):
            return True
        if isinstance(expr, AccesoIndice):
            return self._es_lvalue(expr.base)
        if isinstance(expr, AccesoCampo):
            return self._es_lvalue(expr.base)
        return False

    def _simbolo_raiz_lvalue(self, expr: Expresion) -> Optional[SimboloVariable]:
        actual: Any = expr
        while isinstance(actual, (AccesoIndice, AccesoCampo)):
            actual = actual.base
        if isinstance(actual, Identificador) and isinstance(actual.simbolo, SimboloVariable):
            return actual.simbolo
        return None

    # --- Visitantes: Programa y Declaraciones Externas -----------------------

    def visitar_ProgramaAST(self, nodo: ProgramaAST) -> TipoResuelto:
        for decl in nodo.declaraciones:
            self.visitar(decl)

        # Verificar que todo prototipo de usuario tenga su definición
        for nombre, firma in self.tabla.funciones.items():
            if not firma.es_intrinseca and not firma.definida:
                self.errores.append(
                    ErrorSemantico(
                        linea=firma.linea,
                        columna=firma.columna,
                        mensaje=f"funcion declarada como prototipo y nunca definida: '{nombre}'",
                        simbolo=nombre,
                    )
                )

        # Verificar existencia de main sin parámetros (punto de entrada 0x00200000)
        if self.exigir_main:
            firma_main = self.tabla.funciones.get("main")
            if firma_main is None or not firma_main.definida:
                self._reportar(
                    nodo,
                    "el programa debe definir la funcion de entrada 'main()' sin parametros",
                    simbolo="main",
                )
            elif firma_main.aridad != 0:
                self.errores.append(
                    ErrorSemantico(
                        linea=firma_main.linea,
                        columna=firma_main.columna,
                        mensaje="la funcion 'main' no debe recibir parametros",
                        simbolo="main",
                    )
                )

        return self._anotar(nodo, TIPO_VOID)

    def visitar_DefinicionTDA(self, nodo: DefinicionTDA) -> TipoResuelto:
        if nodo.nombre in self.tabla.tipos or nodo.nombre in self.tabla.alias:
            self._reportar(nodo, f"TDA redefinido: '{nodo.nombre}'", simbolo=nodo.nombre)
            return TIPO_ERROR

        # Registrar antes de analizar campos para detectar recursión por valor
        descriptor = DescriptorTipoTDA(nombre=nodo.nombre, clase=nodo.clase, completo=False)
        self.tabla.tipos[nodo.nombre] = descriptor

        offset_acum = 0
        nombres_vistos: set[str] = set()

        for campo in nodo.campos:
            if campo.nombre in nombres_vistos:
                self._reportar(
                    campo,
                    f"campo duplicado '{campo.nombre}' en TDA '{nodo.nombre}'",
                    simbolo=campo.nombre,
                )
                continue
            nombres_vistos.add(campo.nombre)

            dims = self._evaluar_dimensiones(campo.dimensiones, campo, permitir_abierta_primera=False)
            tipo_campo = self._resolver_especificador_tipo(
                campo.tipo, dimensiones_extra=dims, permitir_void=False
            )
            if tipo_campo == TIPO_ERROR:
                continue

            # Detección de recursión directa o mutua por valor
            if tipo_campo.es_tda:
                tda_ref = self.tabla.tipos.get(tipo_campo.base)
                if tda_ref is not None and not tda_ref.completo:
                    self._reportar(
                        campo,
                        f"TDA recursivo por valor no permitido: campo '{campo.nombre}' de tipo '{tipo_campo.base}'",
                        simbolo=campo.nombre,
                    )
                    continue

            tam_campo = tipo_campo.tamano_bytes(self.tabla.tipos)
            if tipo_campo.es_matriz:
                offset_cab = offset_acum
                offset_dato = offset_acum + TAMANO_CABECERA_MATRIZ
            else:
                offset_cab = None
                offset_dato = offset_acum

            desc_campo = DescriptorCampo(
                nombre=campo.nombre,
                tipo=tipo_campo,
                offset=offset_dato,
                tamano_bytes=tam_campo,
                offset_cabecera=offset_cab,
            )
            descriptor.agregar_campo(desc_campo)
            self._anotar(campo, tipo_campo, desc_campo)
            offset_acum += tam_campo

        descriptor.tamano_bytes = offset_acum
        descriptor.completo = True
        tipo_tda = TipoResuelto(base=descriptor.nombre, clase_tda=descriptor.clase)
        return self._anotar(nodo, tipo_tda, descriptor)

    def visitar_DefinicionTypedef(self, nodo: DefinicionTypedef) -> TipoResuelto:
        if nodo.nombre in self.tabla.tipos or nodo.nombre in self.tabla.alias:
            self._reportar(nodo, f"alias typedef redefinido: '{nodo.nombre}'", simbolo=nodo.nombre)
            return TIPO_ERROR

        dims = self._evaluar_dimensiones(nodo.dimensiones, nodo, permitir_abierta_primera=False)
        tipo_res = self._resolver_especificador_tipo(
            nodo.tipo, dimensiones_extra=dims, permitir_void=False
        )
        if tipo_res == TIPO_ERROR:
            return TIPO_ERROR

        alias = DescriptorAlias(nombre=nodo.nombre, tipo=tipo_res)
        self.tabla.alias[nodo.nombre] = alias
        return self._anotar(nodo, tipo_res, alias)

    def visitar_DeclaracionVariable(self, nodo: DeclaracionVariable) -> TipoResuelto:
        tipo_base_preliminar = self._resolver_especificador_tipo(
            nodo.tipo, dimensiones_extra=(), permitir_void=False
        )
        if tipo_base_preliminar == TIPO_ERROR:
            return TIPO_ERROR

        for decl in nodo.declaradores:
            self._analizar_declarador(nodo.tipo, decl)

        return self._anotar(nodo, tipo_base_preliminar)

    def _analizar_declarador(self, esp_tipo: EspecificadorTipo, decl: Declarador) -> Optional[SimboloVariable]:
        # 1. Verificar redeclaración en el ámbito actual y colisión global con funciones
        if self.tabla.ambitos.buscar_local(decl.nombre) is not None:
            self._reportar(decl, f"variable redeclarada en el mismo ambito: '{decl.nombre}'", simbolo=decl.nombre)
            return None
        if self.tabla.ambitos.es_global and decl.nombre in self.tabla.funciones:
            self._reportar(
                decl,
                f"el nombre '{decl.nombre}' ya esta en uso por una funcion global",
                simbolo=decl.nombre,
            )
            return None

        # 2. Evaluar dimensiones (la 1.ª puede ser abierta solo si trae ListaInicializadores)
        tiene_lista = isinstance(decl.inicializador, ListaInicializadores)
        dims = self._evaluar_dimensiones(
            decl.dimensiones,
            decl,
            permitir_abierta_primera=tiene_lista,
        )
        tipo_var = self._resolver_especificador_tipo(esp_tipo, dimensiones_extra=dims, permitir_void=False)
        if tipo_var == TIPO_ERROR:
            return None

        # 3. Verificar const sin inicializador
        if tipo_var.es_const and decl.inicializador is None:
            self._reportar(
                decl,
                f"la constante '{decl.nombre}' debe tener un inicializador",
                simbolo=decl.nombre,
            )

        # 4. Validar inicializador e inferir dimensión abierta si aplica
        valor_constante: Optional[Any] = None
        if decl.inicializador is not None:
            tipo_var, valor_constante = self._validar_inicializador(tipo_var, decl)

        # Si quedó alguna dimensión abierta sin resolver (error previo), normalizar a 1 para layout
        if any(d is None for d in tipo_var.dimensiones):
            dims_seguras = tuple(1 if d is None else d for d in tipo_var.dimensiones)
            tipo_var = TipoResuelto(
                base=tipo_var.base,
                dimensiones=dims_seguras,
                es_const=tipo_var.es_const,
                clase_tda=tipo_var.clase_tda,
            )

        # 5. Calcular ubicación y desplazamiento alineado a 8 bytes
        tam = tipo_var.tamano_bytes(self.tabla.tipos)
        if self.tabla.ambitos.es_global:
            ubicacion = "global"
            base_relativa = f"0x{BASE_DATOS_GLOBAL:08X}"
            if tipo_var.es_matriz:
                offset_cab = self.tabla.tamano_datos_globales
                desplazamiento = offset_cab + TAMANO_CABECERA_MATRIZ
            else:
                offset_cab = None
                desplazamiento = self.tabla.tamano_datos_globales
            self.tabla.tamano_datos_globales += tam
        else:
            ubicacion = "local"
            base_relativa = "R7/BP"
            bloque_inicio = -(self._offset_local_actual + tam)
            if tipo_var.es_matriz:
                offset_cab = bloque_inicio
                desplazamiento = bloque_inicio + TAMANO_CABECERA_MATRIZ
            else:
                offset_cab = None
                desplazamiento = bloque_inicio
            self._offset_local_actual += tam

        simbolo = SimboloVariable(
            nombre=decl.nombre,
            tipo=tipo_var,
            es_const=tipo_var.es_const,
            ubicacion=ubicacion,
            desplazamiento=desplazamiento,
            base_relativa=base_relativa,
            tamano_bytes=tam,
            offset_cabecera=offset_cab,
            por_referencia=False,
            valor_constante=valor_constante,
            linea=decl.linea,
            columna=decl.columna,
        )
        self.tabla.ambitos.insertar(simbolo)
        if ubicacion == "global":
            self.tabla.globales_ordenados.append(simbolo)
        elif self._funcion_actual is not None:
            self._funcion_actual.simbolos_locales.append(simbolo)

        self._anotar(decl, tipo_var, simbolo)
        return simbolo

    def _validar_inicializador(
        self,
        tipo_var: TipoResuelto,
        decl: Declarador,
    ) -> Tuple[TipoResuelto, Optional[Any]]:
        """Valida inicializadores escalares, 1D y 2D; infiere 1.ª dimensión abierta y coerciones."""
        init = decl.inicializador
        assert init is not None

        # Escalar
        if tipo_var.es_escalar:
            if isinstance(init, ListaInicializadores):
                self._reportar(
                    init,
                    f"no se puede usar una lista de inicializadores para la variable escalar '{decl.nombre}'",
                )
                return tipo_var, None
            tipo_expr = self._analizar_expresion(init)
            nueva_expr, ok = self._compatibilidad_asignacion(
                tipo_expr,
                tipo_var,
                init,
                decl,
                contexto=f"inicializacion de '{decl.nombre}'",
            )
            decl.inicializador = nueva_expr
            val_const = None
            if ok and tipo_var.es_const and tipo_var.es_entero:
                val_const = self._evaluar_constante_entera(init)
            return tipo_var, val_const

        # Vector 1D
        if tipo_var.es_arreglo:
            # Permite char s[N] = "hola";
            if tipo_var.base == "char" and isinstance(init, LiteralCadena):
                self._anotar(init, TIPO_STRING)
                tam_cad = len(init.valor) + 1
                dim0 = tipo_var.dimensiones[0]
                if dim0 is None:
                    tipo_var = TipoResuelto(
                        base=tipo_var.base,
                        dimensiones=(tam_cad,),
                        es_const=tipo_var.es_const,
                        clase_tda=tipo_var.clase_tda,
                    )
                elif tam_cad > dim0:
                    self._reportar(
                        init,
                        f"la cadena literal excede el tamano del arreglo '{decl.nombre}[{dim0}]'",
                    )
                return tipo_var, None

            if not isinstance(init, ListaInicializadores):
                self._reportar(
                    init,
                    f"el arreglo '{decl.nombre}' debe inicializarse con una lista '{{...}}'",
                )
                return tipo_var, None

            n_elems = len(init.elementos)
            dim0 = tipo_var.dimensiones[0]
            if dim0 is None:
                tipo_var = TipoResuelto(
                    base=tipo_var.base,
                    dimensiones=(n_elems,),
                    es_const=tipo_var.es_const,
                    clase_tda=tipo_var.clase_tda,
                )
            elif n_elems > dim0:
                self._reportar(
                    init,
                    f"demasiados elementos ({n_elems}) para el arreglo '{decl.nombre}[{dim0}]'",
                )

            tipo_elem = TipoResuelto(base=tipo_var.base, clase_tda=tipo_var.clase_tda)
            for idx, elem in enumerate(init.elementos):
                if isinstance(elem, ListaInicializadores):
                    self._reportar(elem, f"no se esperaba sublista en elemento #{idx} del vector '{decl.nombre}'")
                    continue
                t_e = self._analizar_expresion(elem)
                nuevo_e, _ = self._compatibilidad_asignacion(
                    t_e, tipo_elem, elem, elem, contexto=f"elemento [{idx}] de '{decl.nombre}'"
                )
                init.elementos[idx] = nuevo_e
            self._anotar(init, tipo_var)
            return tipo_var, None

        # Matriz 2D
        if not isinstance(init, ListaInicializadores):
            self._reportar(
                init,
                f"la matriz '{decl.nombre}' debe inicializarse con listas anidadas '{{{{...}}}}'",
            )
            return tipo_var, None

        filas_init = len(init.elementos)
        dim_f, dim_c = tipo_var.dimensiones
        if dim_f is None:
            tipo_var = TipoResuelto(
                base=tipo_var.base,
                dimensiones=(filas_init, dim_c),
                es_const=tipo_var.es_const,
                clase_tda=tipo_var.clase_tda,
            )
            dim_f = filas_init
        elif filas_init > dim_f:
            self._reportar(
                init,
                f"demasiadas filas ({filas_init}) para la matriz '{decl.nombre}[{dim_f}][{dim_c}]'",
            )

        tipo_elem = TipoResuelto(base=tipo_var.base, clase_tda=tipo_var.clase_tda)
        for i, fila in enumerate(init.elementos):
            if not isinstance(fila, ListaInicializadores):
                self._reportar(fila, f"la fila {i} de la matriz '{decl.nombre}' debe ser una lista '{{...}}'")
                continue
            if dim_c is not None and len(fila.elementos) > dim_c:
                self._reportar(
                    fila,
                    f"demasiados elementos ({len(fila.elementos)}) en fila {i} de '{decl.nombre}' (max {dim_c})",
                )
            for j, elem in enumerate(fila.elementos):
                if isinstance(elem, ListaInicializadores):
                    self._reportar(elem, f"anidamiento excesivo en elemento [{i}][{j}] de '{decl.nombre}'")
                    continue
                t_e = self._analizar_expresion(elem)
                nuevo_e, _ = self._compatibilidad_asignacion(
                    t_e, tipo_elem, elem, elem, contexto=f"elemento [{i}][{j}] de '{decl.nombre}'"
                )
                fila.elementos[j] = nuevo_e
            self._anotar(fila, TipoResuelto(base=tipo_var.base, dimensiones=(dim_c,), clase_tda=tipo_var.clase_tda))

        self._anotar(init, tipo_var)
        return tipo_var, None

    def visitar_DefinicionFuncion(self, nodo: DefinicionFuncion) -> TipoResuelto:
        # 1. Resolver tipo de retorno (void permitido)
        tipo_ret = self._resolver_especificador_tipo(
            nodo.tipo_retorno, dimensiones_extra=(), permitir_void=True
        )

        # 2. Verificar que no colisione con una variable global
        if self.tabla.ambitos.pila[0].get(nodo.nombre) is not None:
            self._reportar(
                nodo,
                f"el nombre de funcion '{nodo.nombre}' colisiona con una variable global",
                simbolo=nodo.nombre,
            )

        # 3. Resolver tipos de parámetros
        params_resueltos: List[Tuple[Optional[str], TipoResuelto]] = []
        nombres_params: set[str] = set()
        for param in nodo.parametros:
            if not nodo.es_prototipo and param.nombre is None:
                self._reportar(param, f"todo parametro en la definicion de '{nodo.nombre}' debe tener nombre")
            if param.nombre is not None:
                if param.nombre in nombres_params:
                    self._reportar(
                        param,
                        f"parametro duplicado '{param.nombre}' en la funcion '{nodo.nombre}'",
                        simbolo=param.nombre,
                    )
                nombres_params.add(param.nombre)

            # En parámetros, la 1.ª dimensión (y en matrices incluso la 2.ª) puede ser abierta
            dims_p = self._evaluar_dimensiones(
                param.dimensiones,
                param,
                permitir_abierta_primera=True,
                permitir_abiertas_todas=True,
            )
            tipo_p = self._resolver_especificador_tipo(
                param.tipo, dimensiones_extra=dims_p, permitir_void=False
            )
            params_resueltos.append((param.nombre, tipo_p))
            self._anotar(param, tipo_p)

        # 4. Registrar o contrastar contra prototipo/definición previa
        previa = self.tabla.funciones.get(nodo.nombre)
        if previa is not None:
            if previa.definida and not nodo.es_prototipo:
                self._reportar(nodo, f"funcion redefinida: '{nodo.nombre}'", simbolo=nodo.nombre)
                return TIPO_ERROR
            # Comprobar coincidencia de firma
            firma_ok = (
                previa.retorno.mismo_tipo(tipo_ret, ignorar_const=True)
                and previa.aridad == len(params_resueltos)
                and all(
                    t_prev.mismo_tipo(t_act, ignorar_const=True)
                    for (_, t_prev), (_, t_act) in zip(previa.parametros, params_resueltos)
                )
            )
            if not firma_ok:
                self._reportar(
                    nodo,
                    f"declaracion de '{nodo.nombre}' incompatible con su prototipo previo",
                    simbolo=nodo.nombre,
                )
                return TIPO_ERROR
            firma = previa
            if not nodo.es_prototipo:
                firma.parametros = params_resueltos
                firma.definida = True
                firma.linea = nodo.linea
                firma.columna = nodo.columna
        else:
            firma = FirmaFuncion(
                nombre=nodo.nombre,
                retorno=tipo_ret,
                parametros=params_resueltos,
                definida=not nodo.es_prototipo,
                linea=nodo.linea,
                columna=nodo.columna,
            )
            self.tabla.funciones[nodo.nombre] = firma

        self._anotar(nodo, tipo_ret, firma)

        # Si es solo prototipo, termina aquí
        if nodo.es_prototipo or nodo.cuerpo is None:
            return tipo_ret

        # 5. Analizar cuerpo de la función en su propio ámbito
        funcion_previa = self._funcion_actual
        offset_previo = self._offset_local_actual
        return_previo = self._tiene_return_en_funcion

        self._funcion_actual = firma
        self._offset_local_actual = 0
        self._tiene_return_en_funcion = False
        self.tabla.ambitos.abrir()

        try:
            for idx, (param_nodo, (p_nombre, p_tipo)) in enumerate(zip(nodo.parametros, params_resueltos)):
                if p_nombre is None:
                    continue
                es_ref = bool(p_tipo.dimensiones) or p_tipo.es_tda
                if idx < 4:
                    base_rel = "R1..R4"
                    despl = idx  # 0->R1, 1->R2, 2->R3, 3->R4
                else:
                    base_rel = "R7/BP"
                    despl = 16 + 8 * (idx - 4)  # [BP + 16], [BP + 24], ...
                sim_p = SimboloVariable(
                    nombre=p_nombre,
                    tipo=p_tipo,
                    es_const=p_tipo.es_const,
                    ubicacion="parametro",
                    desplazamiento=despl,
                    base_relativa=base_rel,
                    tamano_bytes=TAMANO_PALABRA,
                    por_referencia=es_ref,
                    linea=param_nodo.linea,
                    columna=param_nodo.columna,
                )
                self.tabla.ambitos.insertar(sim_p)
                firma.simbolos_parametros.append(sim_p)
                self._anotar(param_nodo, p_tipo, sim_p)

            # Recorrer directamente los elementos del bloque de la función (sin abrir doble ámbito)
            for elem in nodo.cuerpo.elementos:
                self.visitar(elem)
            self._anotar(nodo.cuerpo, TIPO_VOID)

            firma.tam_locales = self._offset_local_actual

            if not tipo_ret.es_void and tipo_ret != TIPO_ERROR and not self._tiene_return_en_funcion:
                self._reportar(
                    nodo,
                    f"la funcion '{nodo.nombre}' de tipo '{tipo_ret}' debe retornar un valor",
                    simbolo=nodo.nombre,
                )
        finally:
            self.tabla.ambitos.cerrar()
            self._funcion_actual = funcion_previa
            self._offset_local_actual = offset_previo
            self._tiene_return_en_funcion = return_previo

        return tipo_ret

    # --- Visitantes: Bloques y Control de Flujo ------------------------------

    def visitar_Bloque(self, nodo: Bloque) -> TipoResuelto:
        self.tabla.ambitos.abrir()
        try:
            for elem in nodo.elementos:
                self.visitar(elem)
        finally:
            self.tabla.ambitos.cerrar()
        return self._anotar(nodo, TIPO_VOID)

    def visitar_SentenciaVacia(self, nodo: SentenciaVacia) -> TipoResuelto:
        return self._anotar(nodo, TIPO_VOID)

    def visitar_SentenciaExpresion(self, nodo: SentenciaExpresion) -> TipoResuelto:
        tipo = self._analizar_expresion(nodo.expresion)
        return self._anotar(nodo, tipo)

    def visitar_Asignacion(self, nodo: Asignacion) -> TipoResuelto:
        tipo_dest = self._analizar_expresion(nodo.destino)
        tipo_val = self._analizar_expresion(nodo.valor)

        if not self._es_lvalue(nodo.destino):
            self._reportar(nodo, "el lado izquierdo de la asignacion no es un lvalue modificable")
            return self._anotar(nodo, TIPO_ERROR)

        raiz = self._simbolo_raiz_lvalue(nodo.destino)
        if raiz is not None and raiz.es_const:
            self._reportar(
                nodo,
                f"no se puede modificar la constante '{raiz.nombre}'",
                simbolo=raiz.nombre,
            )
            return self._anotar(nodo, TIPO_ERROR)

        if tipo_dest.dimensiones:
            self._reportar(
                nodo,
                f"no se permite asignar directamente a un arreglo o matriz completo ('{tipo_dest}')",
            )
            return self._anotar(nodo, TIPO_ERROR)

        if nodo.operador == "=":
            nuevo_val, _ = self._compatibilidad_asignacion(
                tipo_val, tipo_dest, nodo.valor, nodo, contexto="asignacion"
            )
            nodo.valor = nuevo_val
            return self._anotar(nodo, tipo_dest)

        # Asignación compuesta: +=, -=, *=, /=, %=, &=, |=, ^=, <<=, >>=
        op_base = MAPA_ASIGNACION_COMPUESTA[nodo.operador]
        if tipo_dest.es_tda:
            self._reportar(
                nodo,
                f"el operador compuesto '{nodo.operador}' no aplica a TDA '{tipo_dest}'",
            )
            return self._anotar(nodo, TIPO_ERROR)

        if op_base in OPERADORES_ENTEROS_ESTRICTOS:
            if not (tipo_dest.es_entero and tipo_val.es_entero):
                self._reportar(
                    nodo,
                    f"el operador '{nodo.operador}' exige operandos enteros (se encontro '{tipo_dest}' y '{tipo_val}')",
                )
                return self._anotar(nodo, TIPO_ERROR)
            return self._anotar(nodo, tipo_dest)

        # +=, -=, *=, /=
        if not (tipo_dest.es_numerico and tipo_val.es_numerico):
            self._reportar(
                nodo,
                f"el operador '{nodo.operador}' exige operandos numericos (se encontro '{tipo_dest}' y '{tipo_val}')",
            )
            return self._anotar(nodo, TIPO_ERROR)

        if tipo_dest.es_flotante and tipo_val.es_entero:
            nodo.valor = self._coercer_a_float(nodo.valor)
        elif tipo_dest.es_entero and tipo_val.es_flotante:
            self._reportar(
                nodo,
                f"no se puede aplicar '{nodo.operador}' con 'float' sobre destino entero '{tipo_dest}'",
            )
            return self._anotar(nodo, TIPO_ERROR)

        return self._anotar(nodo, tipo_dest)

    def visitar_IncrementoDecremento(self, nodo: IncrementoDecremento) -> TipoResuelto:
        tipo_dest = self._analizar_expresion(nodo.destino)
        if not self._es_lvalue(nodo.destino):
            self._reportar(nodo, f"el operando de '{nodo.operador}' debe ser un lvalue modificable")
            return self._anotar(nodo, TIPO_ERROR)

        raiz = self._simbolo_raiz_lvalue(nodo.destino)
        if raiz is not None and raiz.es_const:
            self._reportar(
                nodo,
                f"no se puede aplicar '{nodo.operador}' a la constante '{raiz.nombre}'",
                simbolo=raiz.nombre,
            )
            return self._anotar(nodo, TIPO_ERROR)

        if not tipo_dest.es_numerico:
            self._reportar(
                nodo,
                f"el operador '{nodo.operador}' requiere un operando numerico (se encontro '{tipo_dest}')",
            )
            return self._anotar(nodo, TIPO_ERROR)

        return self._anotar(nodo, tipo_dest)

    def _verificar_condicion(self, expr: Expresion, nombre_estructura: str) -> None:
        tipo = self._analizar_expresion(expr)
        if tipo != TIPO_ERROR and not tipo.es_numerico:
            self._reportar(
                expr,
                f"la condicion de '{nombre_estructura}' debe ser booleana o numerica (se encontro '{tipo}')",
            )

    def visitar_SentenciaIf(self, nodo: SentenciaIf) -> TipoResuelto:
        self._verificar_condicion(nodo.condicion, "if")
        self.visitar(nodo.entonces)
        if nodo.sino is not None:
            self.visitar(nodo.sino)
        return self._anotar(nodo, TIPO_VOID)

    def visitar_SentenciaSwitch(self, nodo: SentenciaSwitch) -> TipoResuelto:
        tipo_sel = self._analizar_expresion(nodo.expresion)
        if tipo_sel != TIPO_ERROR and not tipo_sel.es_entero:
            self._reportar(
                nodo.expresion,
                f"la expresion de 'switch' debe ser entera, char o bool (se encontro '{tipo_sel}')",
            )

        self._profundidad_switch += 1
        valores_vistos: set[int] = set()
        try:
            for caso in nodo.casos:
                val = self._evaluar_constante_entera(caso.valor)
                if val is None:
                    self._reportar(caso.valor, "la etiqueta de 'case' debe ser una constante entera")
                elif val in valores_vistos:
                    self._reportar(caso, f"etiqueta 'case' duplicada con valor {val}")
                else:
                    valores_vistos.add(val)
                caso.simbolo = val
                self._anotar(caso, TIPO_INT)
                self.tabla.ambitos.abrir()
                try:
                    for elem in caso.cuerpo:
                        self.visitar(elem)
                finally:
                    self.tabla.ambitos.cerrar()

            if nodo.defecto is not None:
                self._anotar(nodo.defecto, TIPO_VOID)
                self.tabla.ambitos.abrir()
                try:
                    for elem in nodo.defecto.cuerpo:
                        self.visitar(elem)
                finally:
                    self.tabla.ambitos.cerrar()
        finally:
            self._profundidad_switch -= 1

        return self._anotar(nodo, TIPO_VOID)

    def visitar_SentenciaWhile(self, nodo: SentenciaWhile) -> TipoResuelto:
        self._verificar_condicion(nodo.condicion, "while")
        self._profundidad_bucle += 1
        try:
            self.visitar(nodo.cuerpo)
        finally:
            self._profundidad_bucle -= 1
        return self._anotar(nodo, TIPO_VOID)

    def visitar_SentenciaDoWhile(self, nodo: SentenciaDoWhile) -> TipoResuelto:
        self._profundidad_bucle += 1
        try:
            self.visitar(nodo.cuerpo)
        finally:
            self._profundidad_bucle -= 1
        self._verificar_condicion(nodo.condicion, "do-while")
        return self._anotar(nodo, TIPO_VOID)

    def visitar_SentenciaFor(self, nodo: SentenciaFor) -> TipoResuelto:
        self.tabla.ambitos.abrir()
        self._profundidad_bucle += 1
        try:
            if nodo.inicial is not None:
                self.visitar(nodo.inicial)
            if nodo.condicion is not None:
                self._verificar_condicion(nodo.condicion, "for")
            if nodo.paso is not None:
                self.visitar(nodo.paso)
            self.visitar(nodo.cuerpo)
        finally:
            self._profundidad_bucle -= 1
            self.tabla.ambitos.cerrar()
        return self._anotar(nodo, TIPO_VOID)

    def visitar_SentenciaReturn(self, nodo: SentenciaReturn) -> TipoResuelto:
        if self._funcion_actual is None:
            self._reportar(nodo, "'return' fuera de una funcion")
            return self._anotar(nodo, TIPO_ERROR)

        esperado = self._funcion_actual.retorno
        if nodo.valor is None:
            if not esperado.es_void:
                self._reportar(
                    nodo,
                    f"la funcion '{self._funcion_actual.nombre}' espera retornar '{esperado}', no vacio",
                )
            self._tiene_return_en_funcion = True
            return self._anotar(nodo, TIPO_VOID)

        tipo_val = self._analizar_expresion(nodo.valor)
        if esperado.es_void:
            self._reportar(
                nodo,
                f"la funcion void '{self._funcion_actual.nombre}' no puede retornar un valor",
            )
            return self._anotar(nodo, TIPO_ERROR)

        nuevo_val, _ = self._compatibilidad_asignacion(
            tipo_val,
            esperado,
            nodo.valor,
            nodo,
            contexto=f"return de '{self._funcion_actual.nombre}'",
        )
        nodo.valor = nuevo_val
        self._tiene_return_en_funcion = True
        return self._anotar(nodo, esperado)

    def visitar_SentenciaBreak(self, nodo: SentenciaBreak) -> TipoResuelto:
        if self._profundidad_bucle == 0 and self._profundidad_switch == 0:
            self._reportar(nodo, "'break' solo puede aparecer dentro de un bucle o 'switch'")
        return self._anotar(nodo, TIPO_VOID)

    def visitar_SentenciaContinue(self, nodo: SentenciaContinue) -> TipoResuelto:
        if self._profundidad_bucle == 0:
            self._reportar(nodo, "'continue' solo puede aparecer dentro de un bucle")
        return self._anotar(nodo, TIPO_VOID)

    # --- Visitantes: Expresiones (13 niveles) y Coerción IEEE 754 ------------

    def _analizar_expresion(self, expr: Expresion) -> TipoResuelto:
        res = self.visitar(expr)
        return res if isinstance(res, TipoResuelto) else TIPO_ERROR

    def visitar_ExpresionBinaria(self, nodo: ExpresionBinaria) -> TipoResuelto:
        t_izq = self._analizar_expresion(nodo.izquierda)
        t_der = self._analizar_expresion(nodo.derecha)
        if t_izq == TIPO_ERROR or t_der == TIPO_ERROR:
            return self._anotar(nodo, TIPO_ERROR)

        op = nodo.operador

        # 1. Aritméticos (+, -, *, /): soportan int y float IEEE 754 con coerción automática
        if op in OPERADORES_ARITMETICOS_BIN:
            if not (t_izq.es_numerico and t_der.es_numerico):
                self._reportar(
                    nodo,
                    f"el operador '{op}' requiere operandos numericos (se encontro '{t_izq}' y '{t_der}')",
                )
                return self._anotar(nodo, TIPO_ERROR)
            if t_izq.es_flotante or t_der.es_flotante:
                if t_izq.es_entero:
                    nodo.izquierda = self._coercer_a_float(nodo.izquierda)
                if t_der.es_entero:
                    nodo.derecha = self._coercer_a_float(nodo.derecha)
                return self._anotar(nodo, TIPO_FLOAT)
            return self._anotar(nodo, TIPO_INT)

        # 2. Enteros estrictos (%, &, |, ^, <<, >>)
        if op in OPERADORES_ENTEROS_ESTRICTOS:
            if not (t_izq.es_entero and t_der.es_entero):
                self._reportar(
                    nodo,
                    f"el operador '{op}' solo admite operandos enteros (se encontro '{t_izq}' y '{t_der}')",
                )
                return self._anotar(nodo, TIPO_ERROR)
            return self._anotar(nodo, TIPO_INT)

        # 3. Relacionales (<, <=, >, >=) e Igualdad (==, !=)
        if op in OPERADORES_RELACIONALES_BIN or op in OPERADORES_IGUALDAD_BIN:
            if not (t_izq.es_numerico and t_der.es_numerico):
                self._reportar(
                    nodo,
                    f"el operador '{op}' requiere operandos numericos/booleanos (se encontro '{t_izq}' y '{t_der}')",
                )
                return self._anotar(nodo, TIPO_ERROR)
            if t_izq.es_flotante or t_der.es_flotante:
                if t_izq.es_entero:
                    nodo.izquierda = self._coercer_a_float(nodo.izquierda)
                if t_der.es_entero:
                    nodo.derecha = self._coercer_a_float(nodo.derecha)
            return self._anotar(nodo, TIPO_BOOL)

        # 4. Lógicos (&&, ||)
        if op in OPERADORES_LOGICOS_BIN:
            if not (t_izq.es_numerico and t_der.es_numerico):
                self._reportar(
                    nodo,
                    f"el operador logico '{op}' requiere operandos escalares (se encontro '{t_izq}' y '{t_der}')",
                )
                return self._anotar(nodo, TIPO_ERROR)
            return self._anotar(nodo, TIPO_BOOL)

        self._reportar(nodo, f"operador binario no soportado: '{op}'")
        return self._anotar(nodo, TIPO_ERROR)

    def visitar_ExpresionUnaria(self, nodo: ExpresionUnaria) -> TipoResuelto:
        t_op = self._analizar_expresion(nodo.operando)
        if t_op == TIPO_ERROR:
            return self._anotar(nodo, TIPO_ERROR)

        op = nodo.operador
        if op in ("+", "-"):
            if not t_op.es_numerico:
                self._reportar(
                    nodo,
                    f"el operador unario '{op}' requiere un operando numerico (se encontro '{t_op}')",
                )
                return self._anotar(nodo, TIPO_ERROR)
            return self._anotar(nodo, TIPO_FLOAT if t_op.es_flotante else TIPO_INT)

        if op == "!":
            if not t_op.es_numerico:
                self._reportar(
                    nodo,
                    f"el operador '!' requiere un operando booleano o numerico (se encontro '{t_op}')",
                )
                return self._anotar(nodo, TIPO_ERROR)
            return self._anotar(nodo, TIPO_BOOL)

        if op == "~":
            if not t_op.es_entero:
                self._reportar(
                    nodo,
                    f"el operador bit a bit '~' requiere un operando entero (se encontro '{t_op}')",
                )
                return self._anotar(nodo, TIPO_ERROR)
            return self._anotar(nodo, TIPO_INT)

        self._reportar(nodo, f"operador unario no soportado: '{op}'")
        return self._anotar(nodo, TIPO_ERROR)

    def visitar_Sizeof(self, nodo: Sizeof) -> TipoResuelto:
        if isinstance(nodo.objetivo, EspecificadorTipo):
            tipo_obj = self._resolver_especificador_tipo(nodo.objetivo, permitir_void=False)
        else:
            tipo_obj = self._analizar_expresion(nodo.objetivo)

        if tipo_obj == TIPO_ERROR:
            return self._anotar(nodo, TIPO_INT, 0)

        tam = tipo_obj.tamano_bytes(self.tabla.tipos)
        return self._anotar(nodo, TIPO_INT, tam)

    def visitar_AccesoIndice(self, nodo: AccesoIndice) -> TipoResuelto:
        t_base = self._analizar_expresion(nodo.base)
        t_idx = self._analizar_expresion(nodo.indice)

        if t_idx != TIPO_ERROR and not t_idx.es_entero:
            self._reportar(
                nodo.indice,
                f"el indice de un arreglo o matriz debe ser entero (se encontro '{t_idx}')",
            )

        if t_base == TIPO_ERROR:
            return self._anotar(nodo, TIPO_ERROR)

        if not t_base.dimensiones:
            self._reportar(
                nodo,
                f"no se puede indexar un valor de tipo '{t_base}' que no es arreglo ni matriz",
            )
            return self._anotar(nodo, TIPO_ERROR)

        tipo_res = TipoResuelto(
            base=t_base.base,
            dimensiones=t_base.dimensiones[1:],
            es_const=t_base.es_const,
            clase_tda=t_base.clase_tda,
        )
        return self._anotar(nodo, tipo_res, nodo.base.simbolo)

    def visitar_AccesoCampo(self, nodo: AccesoCampo) -> TipoResuelto:
        t_base = self._analizar_expresion(nodo.base)
        if t_base == TIPO_ERROR:
            return self._anotar(nodo, TIPO_ERROR)

        if not t_base.es_tda or not t_base.es_escalar:
            self._reportar(
                nodo,
                f"el acceso al campo '.{nodo.campo}' requiere una instancia de TDA (se encontro '{t_base}')",
                simbolo=nodo.campo,
            )
            return self._anotar(nodo, TIPO_ERROR)

        desc_tda = self.tabla.tipos.get(t_base.base)
        if desc_tda is None:
            self._reportar(nodo, f"TDA no definido: '{t_base.base}'", simbolo=t_base.base)
            return self._anotar(nodo, TIPO_ERROR)

        desc_campo = desc_tda.obtener_campo(nodo.campo)
        if desc_campo is None:
            self._reportar(
                nodo,
                f"el TDA '{desc_tda.nombre}' no tiene un campo llamado '{nodo.campo}'",
                simbolo=nodo.campo,
            )
            return self._anotar(nodo, TIPO_ERROR)

        tipo_campo = desc_campo.tipo.con_const(desc_campo.tipo.es_const or t_base.es_const)
        return self._anotar(nodo, tipo_campo, desc_campo)

    def visitar_LlamadaFuncion(self, nodo: LlamadaFuncion) -> TipoResuelto:
        nombre_fn = nodo.nombre
        if nombre_fn is None:
            self._reportar(nodo, "la expresion invocada no es un nombre de funcion valido")
            return self._anotar(nodo, TIPO_ERROR)

        firma = self.tabla.funciones.get(nombre_fn)
        if firma is None:
            self._reportar(nodo, f"funcion no declarada: '{nombre_fn}'", simbolo=nombre_fn)
            for arg in nodo.argumentos:
                self._analizar_expresion(arg)
            return self._anotar(nodo, TIPO_ERROR)

        if len(nodo.argumentos) != firma.aridad:
            self._reportar(
                nodo,
                f"la funcion '{nombre_fn}' espera {firma.aridad} argumento(s), se recibieron {len(nodo.argumentos)}",
                simbolo=nombre_fn,
            )
            for arg in nodo.argumentos:
                self._analizar_expresion(arg)
            return self._anotar(nodo, firma.retorno, firma)

        for idx, (arg, (_, param_tipo)) in enumerate(zip(nodo.argumentos, firma.parametros), start=1):
            arg_tipo = self._analizar_expresion(arg)
            nodo.argumentos[idx - 1] = self._compatibilidad_parametro(
                arg_tipo, param_tipo, arg, arg, idx, nombre_fn
            )

        if isinstance(nodo.funcion, Identificador):
            self._anotar(nodo.funcion, firma.retorno, firma)

        return self._anotar(nodo, firma.retorno, firma)

    def visitar_Identificador(self, nodo: Identificador) -> TipoResuelto:
        sim = self.tabla.ambitos.buscar(nodo.nombre)
        if sim is None:
            self._reportar(nodo, f"variable no declarada: '{nodo.nombre}'", simbolo=nodo.nombre)
            return self._anotar(nodo, TIPO_ERROR)
        return self._anotar(nodo, sim.tipo, sim)

    def visitar_LiteralEntero(self, nodo: LiteralEntero) -> TipoResuelto:
        return self._anotar(nodo, TIPO_INT)

    def visitar_LiteralFlotante(self, nodo: LiteralFlotante) -> TipoResuelto:
        return self._anotar(nodo, TIPO_FLOAT)

    def visitar_LiteralCadena(self, nodo: LiteralCadena) -> TipoResuelto:
        return self._anotar(nodo, TIPO_STRING)

    def visitar_LiteralCaracter(self, nodo: LiteralCaracter) -> TipoResuelto:
        return self._anotar(nodo, TIPO_CHAR)

    def visitar_LiteralBooleano(self, nodo: LiteralBooleano) -> TipoResuelto:
        return self._anotar(nodo, TIPO_BOOL)

    def visitar_CoercionTipo(self, nodo: CoercionTipo) -> TipoResuelto:
        self._analizar_expresion(nodo.expresion)
        tipo_dest = TIPO_FLOAT if nodo.destino == "float" else TIPO_INT
        return self._anotar(nodo, tipo_dest)
