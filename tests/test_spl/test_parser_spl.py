"""
Pruebas del analizador sintáctico del SPL (spl/compilador/parser.py) y de los
nodos del AST (spl/compilador/ast_nodos.py).

Integrante 2 - Taller 02, Literal e (Parser Parte 1): Programa, DefinicionTDA
(struct/tda), DefinicionTypedef, DeclaracionVariable (escalares, 1D y 2D) y
DeclaracionFuncion (definiciones y prototipos).
"""

from __future__ import annotations

from pathlib import Path

import pytest

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
    LiteralCaracter,
    LiteralEntero,
    LiteralFlotante,
    LlamadaFuncion,
    NodoAST,
    Parametro,
    ProgramaAST,
    SentenciaReturn,
    Sizeof,
    VisitanteAST,
    formatear_ast,
)
from spl.compilador.parser import TOKENS_ADICIONALES, CompiladorParser, ErrorSintactico
from spl.compilador.tablas import GestorTablasSimbolos

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLOS = RAIZ / "spl" / "compilador" / "ejemplos"


@pytest.fixture(scope="module")
def parser() -> CompiladorParser:
    return CompiladorParser()


def analizar_ok(parser: CompiladorParser, texto: str) -> ProgramaAST:
    """Analiza y exige que no haya errores léxicos ni sintácticos."""
    ast, errores = parser.analizar(texto)
    assert errores == [], [str(e) for e in errores]
    assert parser.errores_lexicos == [], [str(e) for e in parser.errores_lexicos]
    return ast


def unica(parser: CompiladorParser, texto: str):
    """Devuelve la única declaración externa del programa."""
    ast = analizar_ok(parser, texto)
    assert len(ast.declaraciones) == 1
    return ast.declaraciones[0]


def entero(valor: int) -> LiteralEntero:
    return LiteralEntero(valor=valor, lexema=str(valor))


def tipo(nombre: str, categoria: str = CATEGORIA_PRIMITIVO, es_const: bool = False) -> EspecificadorTipo:
    return EspecificadorTipo(nombre=nombre, categoria=categoria, es_const=es_const)


# ---------------------------------------------------------------------------
# 1. Construcción de la tabla LALR(1)
# ---------------------------------------------------------------------------

class TestConstruccion:
    def test_cero_conflictos_reduce_reduce(self, parser):
        assert parser.conflictos_reduce_reduce == 0

    def test_cero_conflictos_shift_reduce(self, parser):
        assert parser.conflictos_shift_reduce == 0

    def test_sin_errores_de_gramatica(self, parser):
        assert parser.registro.errores == []

    def test_tokens_incluyen_los_del_lexer_y_los_adicionales(self, parser):
        from spl.compilador.lexer import CompiladorLexer
        assert set(CompiladorLexer.tokens) <= set(parser.tokens)
        assert set(TOKENS_ADICIONALES) <= set(parser.tokens)
        assert len(parser.tokens) == len(set(parser.tokens))

    def test_no_escribe_archivos_de_tablas(self):
        carpeta = RAIZ / "spl" / "compilador"
        CompiladorParser()
        assert not (carpeta / "parsetab.py").exists()
        assert not (carpeta / "parser.out").exists()

    def test_parser_reutilizable(self, parser):
        a1 = analizar_ok(parser, "int a;")
        a2 = analizar_ok(parser, "float b; float c;")
        assert a1.declaraciones[0].nombres == ["a"]
        assert [d.nombres for d in a2.declaraciones] == [["b"], ["c"]]


# ---------------------------------------------------------------------------
# 2. Programa
# ---------------------------------------------------------------------------

class TestPrograma:
    def test_programa_vacio(self, parser):
        ast = analizar_ok(parser, "")
        assert ast == ProgramaAST(declaraciones=[])

    def test_programa_solo_comentarios(self, parser):
        ast = analizar_ok(parser, "// nada\n/* tampoco */\n")
        assert ast.declaraciones == []

    def test_orden_de_las_declaraciones_externas(self, parser):
        ast = analizar_ok(parser, """
            struct P { int x; };
            typedef float Real;
            int g;
            int f() { return 0; }
        """)
        assert [type(d) for d in ast.declaraciones] == [
            DefinicionTDA, DefinicionTypedef, DeclaracionVariable, DefinicionFuncion,
        ]

    def test_filtros_del_programa(self, parser):
        ast = analizar_ok(parser, """
            struct P { int x; };
            tda Q { int y; };
            typedef int E;
            int a; float b;
            void f(); int g() { return 1; }
        """)
        assert [t.nombre for t in ast.tdas()] == ["P", "Q"]
        assert [t.nombre for t in ast.typedefs()] == ["E"]
        assert [v.nombres[0] for v in ast.variables_globales()] == ["a", "b"]
        assert [f.nombre for f in ast.funciones()] == ["f", "g"]


# ---------------------------------------------------------------------------
# 3. Especificador de tipo
# ---------------------------------------------------------------------------

class TestEspecificadorTipo:
    @pytest.mark.parametrize("palabra", ["int", "float", "bool", "char"])
    def test_tipos_primitivos(self, parser, palabra):
        decl = unica(parser, f"{palabra} x;")
        assert decl.tipo == tipo(palabra)
        assert decl.tipo.es_primitivo

    def test_const(self, parser):
        decl = unica(parser, "const int N = 10;")
        assert decl.tipo == tipo("int", es_const=True)
        assert str(decl.tipo) == "const int"

    @pytest.mark.parametrize("clase", ["struct", "tda"])
    def test_tipo_compuesto(self, parser, clase):
        decl = unica(parser, f"{clase} Punto p;")
        assert decl.tipo == tipo("Punto", clase)
        assert decl.tipo.es_compuesto
        assert str(decl.tipo) == f"{clase} Punto"

    def test_const_tipo_compuesto(self, parser):
        decl = unica(parser, "const struct Punto origen;")
        assert decl.tipo == tipo("Punto", CATEGORIA_STRUCT, es_const=True)

    def test_palabras_reservadas_sin_distinguir_mayusculas(self, parser):
        # El lexer de la Fase 1 compara las palabras reservadas en minúsculas.
        decl = unica(parser, "INT x;")
        assert decl.tipo == tipo("int")


# ---------------------------------------------------------------------------
# 4. DefinicionTDA (struct / tda)
# ---------------------------------------------------------------------------

class TestDefinicionTDA:
    def test_struct_con_campos_escalares(self, parser):
        tda = unica(parser, "struct Vector3D { float x; float y; float z; int id; };")
        assert tda == DefinicionTDA(
            clase="struct",
            nombre="Vector3D",
            campos=[
                CampoTDA(tipo=tipo("float"), nombre="x"),
                CampoTDA(tipo=tipo("float"), nombre="y"),
                CampoTDA(tipo=tipo("float"), nombre="z"),
                CampoTDA(tipo=tipo("int"), nombre="id"),
            ],
        )

    def test_palabra_tda_es_sinonimo_de_struct(self, parser):
        tda = unica(parser, "tda Registro { int id; };")
        assert tda.clase == "tda"
        assert tda.nombre == "Registro"

    def test_campos_vector_y_matriz(self, parser):
        tda = unica(parser, """
            tda MatrizTransformacion {
                float datos[4][4];
                int historial[8];
                bool normalizada;
            };
        """)
        datos, historial, normalizada = tda.campos
        assert datos.dimensiones == [entero(4), entero(4)] and datos.es_matriz
        assert historial.dimensiones == [entero(8)] and historial.es_arreglo
        assert normalizada.dimensiones == []

    def test_campo_de_tipo_compuesto(self, parser):
        tda = unica(parser, "struct Linea { struct Punto a; tda Punto b; };")
        assert tda.campos[0].tipo == tipo("Punto", CATEGORIA_STRUCT)
        assert tda.campos[1].tipo == tipo("Punto", CATEGORIA_TDA)

    def test_dimension_de_campo_con_expresion(self, parser):
        tda = unica(parser, "struct B { int celdas[N * 2]; };")
        dim = tda.campos[0].dimensiones[0]
        assert dim == ExpresionBinaria("*", Identificador("N"), entero(2))

    def test_buscar_campo(self, parser):
        tda = unica(parser, "struct P { int x; float y; };")
        assert tda.campo("y").tipo == tipo("float")
        assert tda.campo("z") is None

    def test_tda_sin_campos_es_error(self, parser):
        _, errores = parser.analizar("struct Vacio { };")
        assert len(errores) == 1
        assert errores[0].lexema == "}"

    def test_tda_sin_punto_y_coma_final_es_error(self, parser):
        _, errores = parser.analizar("struct P { int x; }\nint y;")
        assert errores and errores[0].linea == 2

    def test_campo_con_dimension_vacia_es_error(self, parser):
        # Las dimensiones de un campo fijan el layout: no pueden quedar abiertas.
        _, errores = parser.analizar("struct P { int v[]; };")
        assert len(errores) == 1
        assert errores[0].lexema == "]"

    def test_campo_con_inicializador_es_error(self, parser):
        _, errores = parser.analizar("struct P { int x = 1; };")
        assert errores and errores[0].lexema == "="


# ---------------------------------------------------------------------------
# 5. DefinicionTypedef y alias (TIPO_ID)
# ---------------------------------------------------------------------------

class TestTypedef:
    def test_typedef_simple(self, parser):
        td = unica(parser, "typedef float Real;")
        assert td == DefinicionTypedef(tipo=tipo("float"), nombre="Real")

    def test_typedef_de_vector_y_matriz(self, parser):
        ast = analizar_ok(parser, "typedef int Vec8[8]; typedef float M3[3][3];")
        assert ast.declaraciones[0].dimensiones == [entero(8)]
        assert ast.declaraciones[1].dimensiones == [entero(3), entero(3)]

    def test_typedef_de_struct(self, parser):
        td = unica(parser, "typedef struct Punto P2D;")
        assert td.tipo == tipo("Punto", CATEGORIA_STRUCT)

    def test_alias_en_variable_global_y_local(self, parser):
        ast = analizar_ok(parser, """
            typedef int Entero;
            Entero contador = 0;
            void f() { Entero local; local = contador; }
        """)
        glob = ast.declaraciones[1]
        assert glob.tipo == tipo("Entero", CATEGORIA_ALIAS)
        local = ast.declaraciones[2].cuerpo.elementos[0]
        assert isinstance(local, DeclaracionVariable)
        assert local.tipo == tipo("Entero", CATEGORIA_ALIAS)

    def test_alias_en_campo_parametro_y_retorno(self, parser):
        ast = analizar_ok(parser, """
            typedef float Real;
            struct Sensor { Real lectura; };
            Real escalar(Real x, const Real k) { return x * k; }
        """)
        assert ast.declaraciones[1].campos[0].tipo.categoria == CATEGORIA_ALIAS
        funcion = ast.declaraciones[2]
        assert funcion.tipo_retorno == tipo("Real", CATEGORIA_ALIAS)
        assert funcion.parametros[1].tipo == tipo("Real", CATEGORIA_ALIAS, es_const=True)

    def test_alias_en_sizeof(self, parser):
        ast = analizar_ok(parser, "typedef int E; int t = sizeof(E);")
        init = ast.declaraciones[1].declaradores[0].inicializador
        assert init == Sizeof(tipo("E", CATEGORIA_ALIAS))

    def test_alias_disponible_inmediatamente(self, parser):
        # El alias debe estar registrado antes de leer la declaración siguiente.
        ast = analizar_ok(parser, "typedef int A;A x;")
        assert ast.declaraciones[1].tipo.categoria == CATEGORIA_ALIAS

    def test_identificador_no_declarado_como_alias_sigue_siendo_id(self, parser):
        _, errores = parser.analizar("Desconocido x;")
        assert errores  # 'Desconocido' es ID, no puede iniciar una declaración

    def test_nombres_tipo_se_reinician_entre_analisis(self, parser):
        analizar_ok(parser, "typedef int Temporal;")
        assert parser.nombres_tipo == {"Temporal"}
        _, errores = parser.analizar("Temporal x;")
        assert errores
        assert parser.nombres_tipo == set()

    def test_typedef_sin_nombre_es_error(self, parser):
        _, errores = parser.analizar("typedef int;")
        assert errores


# ---------------------------------------------------------------------------
# 6. DeclaracionVariable: escalares, vectores 1D y matrices 2D
# ---------------------------------------------------------------------------

class TestDeclaracionVariable:
    def test_escalar_sin_inicializar(self, parser):
        decl = unica(parser, "int x;")
        assert decl == DeclaracionVariable(tipo=tipo("int"), declaradores=[Declarador(nombre="x")])
        assert decl.declaradores[0].es_escalar

    def test_escalar_inicializado(self, parser):
        decl = unica(parser, "float pi = 3.14159;")
        init = decl.declaradores[0].inicializador
        assert isinstance(init, LiteralFlotante)
        assert init.valor == pytest.approx(3.14159)
        assert init.lexema == "3.14159"

    def test_varios_declaradores(self, parser):
        decl = unica(parser, "int a, b = 2, v[3], m[2][2];")
        assert decl.nombres == ["a", "b", "v", "m"]
        a, b, v, m = decl.declaradores
        assert a.inicializador is None
        assert b.inicializador == entero(2)
        assert v.es_arreglo and v.dimensiones == [entero(3)]
        assert m.es_matriz and m.dimensiones == [entero(2), entero(2)]

    def test_vector_1d(self, parser):
        decl = unica(parser, "int datos[8];")
        assert decl.declaradores[0].dimensiones == [entero(8)]

    def test_matriz_2d(self, parser):
        decl = unica(parser, "int buffer_pixeles[64][64];")
        assert decl.declaradores[0].dimensiones == [entero(64), entero(64)]

    def test_dimension_con_identificador(self, parser):
        decl = unica(parser, "struct Vector3D lista_puntos[MAX_PUNTOS];")
        assert decl.declaradores[0].dimensiones == [Identificador("MAX_PUNTOS")]

    def test_vector_con_lista_de_inicializadores(self, parser):
        decl = unica(parser, "int datos[8] = {42, 15, 8, 99, 23, 4, 16, 50};")
        init = decl.declaradores[0].inicializador
        assert isinstance(init, ListaInicializadores)
        assert [e.valor for e in init.elementos] == [42, 15, 8, 99, 23, 4, 16, 50]

    def test_matriz_con_listas_anidadas(self, parser):
        decl = unica(parser, "int A[2][2] = {{2, 3}, {1, 4}};")
        init = decl.declaradores[0].inicializador
        assert init == ListaInicializadores([
            ListaInicializadores([entero(2), entero(3)]),
            ListaInicializadores([entero(1), entero(4)]),
        ])

    def test_coma_final_en_inicializador(self, parser):
        decl = unica(parser, "int v[] = {1, 2, 3,};")
        assert len(decl.declaradores[0].inicializador.elementos) == 3

    def test_dimension_abierta_con_inicializador(self, parser):
        decl = unica(parser, "int v[] = {1, 2};")
        assert decl.declaradores[0].dimensiones == [None]

    def test_matriz_con_primera_dimension_abierta(self, parser):
        decl = unica(parser, "int m[][3] = {{1,2,3}};")
        assert decl.declaradores[0].dimensiones == [None, entero(3)]

    def test_inicializador_con_expresion(self, parser):
        decl = unica(parser, "int x = -(a + 1) * 2;")
        init = decl.declaradores[0].inicializador
        assert init == ExpresionBinaria(
            "*",
            ExpresionUnaria("-", ExpresionBinaria("+", Identificador("a"), entero(1))),
            entero(2),
        )

    def test_inicializador_hexadecimal_y_binario(self, parser):
        ast = analizar_ok(parser, "int h = 0xFF; int b = 0b1010; int m = 0xFFFFFFFFFFFFFFFF;")
        valores = [d.declaradores[0].inicializador.valor for d in ast.declaraciones]
        assert valores == [255, 10, -1]  # el patrón de 64 bits se lee en complemento a dos

    def test_inicializador_caracter(self, parser):
        decl = unica(parser, "char salto = '\\n';")
        assert decl.declaradores[0].inicializador == LiteralCaracter(valor="\n", lexema="'\\n'")

    def test_inicializador_booleano_con_tokens_del_literal_b(self, parser):
        # Simula el ajuste léxico del Literal b (TRUE_LIT / FALSE_LIT).
        from spl.compilador import parser as modulo

        class LexerConBooleanos(modulo.CompiladorLexer):
            def token(self):
                tok = super().token()
                if tok is not None and tok.type == "ID" and tok.value in ("true", "false"):
                    tok.type = "TRUE_LIT" if tok.value == "true" else "FALSE_LIT"
                return tok

        original = modulo.CompiladorLexer
        modulo.CompiladorLexer = LexerConBooleanos
        try:
            ast = analizar_ok(parser, "bool a = true; bool b = false;")
        finally:
            modulo.CompiladorLexer = original
        valores = [d.declaradores[0].inicializador for d in ast.declaraciones]
        assert valores == [LiteralBooleano(True), LiteralBooleano(False)]

    def test_falta_punto_y_coma(self, parser):
        _, errores = parser.analizar("int x\nint y;")
        assert len(errores) == 1
        assert (errores[0].linea, errores[0].lexema) == (2, "int")

    def test_falta_nombre(self, parser):
        _, errores = parser.analizar("int = 3;")
        assert errores and errores[0].lexema == "="

    def test_lista_de_inicializadores_vacia_es_error(self, parser):
        _, errores = parser.analizar("int v[2] = {};")
        assert errores


# ---------------------------------------------------------------------------
# 7. DeclaracionFuncion: definiciones y prototipos
# ---------------------------------------------------------------------------

class TestDeclaracionFuncion:
    def test_funcion_con_palabra_function(self, parser):
        f = unica(parser, "function int mcd(int a, int b) { return a; }")
        assert f.con_function
        assert f.nombre == "mcd"
        assert f.tipo_retorno == tipo("int")
        assert f.parametros == [Parametro(tipo("int"), "a"), Parametro(tipo("int"), "b")]
        assert f.aridad == 2
        assert not f.es_prototipo
        assert f.cuerpo == Bloque([SentenciaReturn(Identificador("a"))])

    def test_funcion_estilo_c(self, parser):
        f = unica(parser, "float area(float r) { return 3.14 * r * r; }")
        assert not f.con_function
        assert f.tipo_retorno == tipo("float")

    def test_funcion_sin_parametros(self, parser):
        f = unica(parser, "void inicializar() { }")
        assert f.parametros == []
        assert f.cuerpo == Bloque([])

    def test_parametros_void_se_normalizan(self, parser):
        f = unica(parser, "int main(void) { return 0; }")
        assert f.parametros == []

    def test_parametro_void_con_nombre_no_se_normaliza(self, parser):
        # 'void x' no es la lista vacía; el analizador semántico lo rechaza.
        f = unica(parser, "int f(void x) { return 0; }")
        assert f.parametros == [Parametro(tipo("void"), "x")]

    def test_parametros_arreglo_y_matriz(self, parser):
        f = unica(parser, "function float promedio(float notas[10], int m[][4], int n) { return 0.0; }")
        notas, m, n = f.parametros
        assert notas.dimensiones == [entero(10)]
        assert m.dimensiones == [None, entero(4)]
        assert n.dimensiones == []

    def test_parametro_tda(self, parser):
        f = unica(parser, "float leer(tda RegistroSensor s) { return s.lectura; }")
        assert f.parametros[0].tipo == tipo("RegistroSensor", CATEGORIA_TDA)
        ret = f.cuerpo.elementos[0]
        assert ret.valor == AccesoCampo(Identificador("s"), "lectura")

    def test_retorno_tda(self, parser):
        f = unica(parser, "struct Punto origen() { struct Punto p; return p; }")
        assert f.tipo_retorno == tipo("Punto", CATEGORIA_STRUCT)

    def test_prototipo(self, parser):
        f = unica(parser, "int mcd(int a, int b);")
        assert f.es_prototipo
        assert f.cuerpo is None
        assert f.aridad == 2

    def test_prototipo_con_function(self, parser):
        f = unica(parser, "function void reset();")
        assert f.es_prototipo and f.con_function

    def test_prototipo_con_parametros_sin_nombre(self, parser):
        f = unica(parser, "float mezclar(int, float, int[]);")
        assert [p.nombre for p in f.parametros] == [None, None, None]
        assert f.parametros[2].dimensiones == [None]

    def test_cuerpo_con_locales_y_sentencias(self, parser):
        f = unica(parser, """
            function int suma(int v[], int n) {
                int total = 0;
                int datos[4] = {1, 2, 3, 4};
                total = total + v[0] + datos[n - 1];
                registrar(total, 2.5);
                return total;
            }
        """)
        e = f.cuerpo.elementos
        assert isinstance(e[0], DeclaracionVariable) and e[0].nombres == ["total"]
        assert isinstance(e[1], DeclaracionVariable) and e[1].declaradores[0].es_arreglo
        assert isinstance(e[2], Asignacion)
        assert e[2].valor.derecha == AccesoIndice(
            Identificador("datos"), ExpresionBinaria("-", Identificador("n"), entero(1)),
        )
        llamada = e[3].expresion
        assert isinstance(llamada, LlamadaFuncion)
        assert llamada.nombre == "registrar" and len(llamada.argumentos) == 2
        assert isinstance(e[4], SentenciaReturn)

    def test_varias_funciones(self, parser):
        ast = analizar_ok(parser, """
            int mcd(int a, int b);
            int main() { return mcd(1071, 462); }
            int mcd(int a, int b) { return a; }
        """)
        assert [(f.nombre, f.es_prototipo) for f in ast.funciones()] == [
            ("mcd", True), ("main", False), ("mcd", False),
        ]

    def test_funcion_anidada_es_error(self, parser):
        _, errores = parser.analizar("void f() { void g() { } }")
        assert errores

    def test_falta_parentesis_de_cierre(self, parser):
        _, errores = parser.analizar("int f(int a { return a; }")
        assert errores and errores[0].lexema == "{"

    def test_parametros_sin_coma(self, parser):
        _, errores = parser.analizar("int f(int a int b);")
        assert errores and errores[0].lexema == "int"

    def test_function_sin_tipo_es_error(self, parser):
        _, errores = parser.analizar("function f() { }")
        assert errores


# ---------------------------------------------------------------------------
# 8. Posiciones (línea y columna) de los nodos
# ---------------------------------------------------------------------------

class TestPosiciones:
    def test_posicion_de_tda_y_campos(self, parser):
        tda = unica(parser, "\n  struct P {\n    int x;\n  };")
        assert (tda.linea, tda.columna) == (2, 3)
        assert (tda.campos[0].linea, tda.campos[0].columna) == (3, 5)

    def test_posicion_de_declarador(self, parser):
        decl = unica(parser, "int a, bb;")
        assert [(d.linea, d.columna) for d in decl.declaradores] == [(1, 5), (1, 8)]

    def test_posicion_de_const(self, parser):
        decl = unica(parser, "  const int N = 1;")
        assert (decl.linea, decl.columna) == (1, 3)

    def test_posicion_de_funcion_con_y_sin_function(self, parser):
        ast = analizar_ok(parser, "function int f() { }\n   int g() { }")
        f, g = ast.declaraciones
        assert (f.linea, f.columna) == (1, 1)
        assert (g.linea, g.columna) == (2, 4)

    def test_posicion_ignorada_en_igualdad(self, parser):
        a = unica(parser, "int x;")
        b = unica(parser, "\n\n     int x;")
        assert a == b
        assert a.linea != b.linea


# ---------------------------------------------------------------------------
# 9. Enlace con las tablas de símbolos de la Fase 1
# ---------------------------------------------------------------------------

class TestTablas:
    def test_literal_flotante_enlazado_a_tabla_num(self, parser):
        tablas = GestorTablasSimbolos()
        ast, _ = parser.analizar("float r = 25.0;", tablas=tablas)
        lit = ast.declaraciones[0].declaradores[0].inicializador
        entrada = tablas.tabla_num.obtener(lit.simbolo_idx)
        assert entrada.patron_ieee754_hex.upper().endswith("4039000000000000")

    def test_identificadores_registrados_en_tabla_id(self, parser):
        parser.analizar("int alfa; int beta = alfa;")
        nombres = {e.lexema for e in parser.tablas.tabla_id.entradas}
        assert {"alfa", "beta"} <= nombres

    def test_identificador_conserva_indice_de_tabla(self, parser):
        ast, _ = parser.analizar("int alfa; int beta = alfa;")
        ident = ast.declaraciones[1].declaradores[0].inicializador
        assert ident.simbolo_idx == parser.tablas.tabla_id.buscar("alfa")

    def test_errores_lexicos_quedan_disponibles(self, parser):
        _, errores = parser.analizar("int precio@descuento = 1;")
        assert parser.errores_lexicos
        assert errores  # el ID partido produce además un error sintáctico


# ---------------------------------------------------------------------------
# 10. Recuperación de errores en declaraciones
# ---------------------------------------------------------------------------

class TestRecuperacion:
    def test_continua_despues_de_una_declaracion_erronea(self, parser):
        ast, errores = parser.analizar("int x = ;\nint y = 2;\nfloat z;")
        assert len(errores) == 1
        assert errores[0].linea == 1
        assert [d.nombres for d in ast.declaraciones] == [["y"], ["z"]]

    def test_recupera_campo_erroneo_de_tda(self, parser):
        ast, errores = parser.analizar("struct P { int ; float z; int w; };")
        assert len(errores) == 1
        assert [c.nombre for c in ast.declaraciones[0].campos] == ["z", "w"]

    def test_conserva_declaraciones_si_el_archivo_termina_antes(self, parser):
        ast, errores = parser.analizar("int a;\nstruct P { int x;")
        assert errores[-1].lexema == "<EOF>"
        assert [type(d) for d in ast.declaraciones] == [DeclaracionVariable]

    def test_callback_de_errores(self):
        recibidos = []
        p = CompiladorParser(al_error=recibidos.append)
        p.analizar("int = 1;")
        assert len(recibidos) == 1 and isinstance(recibidos[0], ErrorSintactico)

    def test_formato_del_error(self):
        err = ErrorSintactico(linea=3, columna=7, lexema="=", mensaje="token inesperado ASIGNAR")
        assert str(err) == "ERROR SINTACTICO (linea 3, columna 7): token inesperado ASIGNAR: '='"


# ---------------------------------------------------------------------------
# 11. Nodos del AST: recorrido, visitante y volcado
# ---------------------------------------------------------------------------

class TestNodosAST:
    def test_todos_los_nodos_heredan_de_nodo_ast(self):
        import inspect
        from spl.compilador import ast_nodos
        clases = [c for _, c in inspect.getmembers(ast_nodos, inspect.isclass)
                  if c.__module__ == ast_nodos.__name__ and c is not ast_nodos.VisitanteAST]
        assert len(clases) >= 35
        for clase in clases:
            assert issubclass(clase, NodoAST), clase

    def test_anotaciones_semanticas_disponibles(self):
        nodo = Identificador("x")
        assert nodo.tipo_inferido is None and nodo.simbolo is None
        nodo.tipo_inferido = "int"
        assert nodo == Identificador("x")  # las anotaciones no cambian la igualdad

    def test_hijos_y_recorrido(self, parser):
        ast = analizar_ok(parser, "int v[2] = {1, 2};")
        tipos = [type(n).__name__ for n in ast.recorrer()]
        assert tipos == [
            "ProgramaAST", "DeclaracionVariable", "EspecificadorTipo", "Declarador",
            "LiteralEntero", "ListaInicializadores", "LiteralEntero", "LiteralEntero",
        ]

    def test_visitante_despacha_por_clase(self, parser):
        ast = analizar_ok(parser, """
            struct P { int x; };
            int a, b;
            int f(int n) { int c; return n; }
        """)

        class Contador(VisitanteAST):
            def __init__(self):
                self.declaradores = []

            def visitar_Declarador(self, nodo):
                self.declaradores.append(nodo.nombre)

        contador = Contador()
        contador.visitar(ast)
        assert contador.declaradores == ["a", "b", "c"]

    def test_formatear_ast(self, parser):
        ast = analizar_ok(parser, "struct P { float x[2]; };\nint v[] = {1};")
        texto = formatear_ast(ast)
        assert texto.splitlines()[0].startswith("ProgramaAST")
        assert "DefinicionTDA(clase='struct', nombre='P')  @1:1" in texto
        assert "tipo: EspecificadorTipo 'float'" in texto
        assert "dimensiones[0]: [] (dimension abierta)" in texto
        assert "└─ " in texto


# ---------------------------------------------------------------------------
# 12. Programas de ejemplo del repositorio
# ---------------------------------------------------------------------------

class TestEjemplos:
    def test_escenario1_tda_matrices(self, parser):
        texto = (EJEMPLOS / "escenario1_tda_matrices.spl").read_text(encoding="utf-8")
        ast = analizar_ok(parser, texto)
        assert [type(d).__name__ for d in ast.declaraciones] == [
            "DefinicionTDA", "DefinicionTDA", "DeclaracionVariable", "DeclaracionVariable",
            "DeclaracionVariable", "DeclaracionVariable", "DefinicionFuncion",
        ]
        matriz = ast.declaraciones[1]
        assert matriz.clase == "tda" and matriz.campos[0].es_matriz
        funcion = ast.declaraciones[-1]
        assert funcion.nombre == "inicializar_sistema" and funcion.con_function
        assert len(funcion.cuerpo.elementos) == 7

    def test_declaraciones_del_programa5_del_taller(self, parser):
        ast = analizar_ok(parser, """
            tda RegistroSensor {
                int id;
                int modo;
                float lectura;
                float escala;
                float resultado;
            };
            tda RegistroSensor sensores[2];
            function float procesar(tda RegistroSensor s);
        """)
        registro = ast.declaraciones[0]
        assert [c.nombre for c in registro.campos] == ["id", "modo", "lectura", "escala", "resultado"]
        assert ast.declaraciones[1].declaradores[0].dimensiones == [entero(2)]
        assert ast.declaraciones[2].es_prototipo
