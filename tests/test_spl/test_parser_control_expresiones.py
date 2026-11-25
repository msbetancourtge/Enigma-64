"""
Pruebas de la Parte 2 del analizador sintáctico del SPL (spl/compilador/parser.py).

Integrante 3 - Taller 02, Literal e (Parser Parte 2): Bloque, sentencias simples
(asignación simple y compuesta, ++ y --), control de flujo (if/then/else,
switch/case/default, while, do-while, for, return, break y continue), los 13
niveles de expresión de la gramática E-BNF, recuperación de errores por
sentencia y por bloque, y p_error con los tokens esperados.

Los operadores de bits, la asignación compuesta y ++/-- usan tokens que el
lexer de la Fase 1 todavía no emite (OPERADORES_ADICIONALES). Para probarlos,
LexerConOperadores agrega a CompiladorLexer una regla por cada lexema del
contrato, con el mismo nombre de token que espera el parser.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from spl.compilador import parser as modulo_parser
from spl.compilador.ast_nodos import (
    AccesoCampo,
    AccesoIndice,
    Asignacion,
    Bloque,
    ClausulaCase,
    ClausulaDefault,
    Declarador,
    DeclaracionVariable,
    EspecificadorTipo,
    ExpresionBinaria,
    ExpresionUnaria,
    Identificador,
    IncrementoDecremento,
    LiteralBooleano,
    LiteralCaracter,
    LiteralEntero,
    LiteralFlotante,
    LlamadaFuncion,
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
    formatear_ast,
)
from spl.compilador.lexer import OPERADORES, CompiladorLexer
from spl.compilador.parser import (
    MAX_TOKENS_ESPERADOS,
    OPERADORES_ADICIONALES,
    TOKENS_ADICIONALES,
    CompiladorParser,
    ErrorSintactico,
)
from spl.preprocesador.motor import preprocesar_archivo

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLOS_COMPILADOR = RAIZ / "spl" / "compilador" / "ejemplos"
EJEMPLOS_PIPELINE = RAIZ / "spl" / "ejemplos"


# ---------------------------------------------------------------------------
# Lexer de prueba con los operadores del contrato OPERADORES_ADICIONALES
# ---------------------------------------------------------------------------

def _construir_lexer_con_operadores():
    """
    Subclase de CompiladorLexer con una regla de cadena por cada operador del
    contrato. PLY ordena las reglas de cadena por la longitud de la expresión
    y desempata por nombre; como re.escape('&') ya mide lo mismo que '&&', cada
    regla lleva una búsqueda negativa con los caracteres que formarían un
    operador más largo ('&' no coincide en '&&' ni en '&='), y el orden de PLY
    deja de importar. La regla t_OPERADOR_INCOMPLETO del lexer base (que
    reporta '&' y '|' sueltos como error) se reemplaza por una que nunca coincide.
    """
    nuevos = tuple(t for t in OPERADORES_ADICIONALES.values() if t not in CompiladorLexer.tokens)
    atributos = {"tokens": CompiladorLexer.tokens + nuevos}
    todos = set(OPERADORES) | set(OPERADORES_ADICIONALES) | {"->"}
    for lexema, token in OPERADORES_ADICIONALES.items():
        siguientes = sorted({o[len(lexema)] for o in todos
                             if len(o) > len(lexema) and o.startswith(lexema)})
        patron = re.escape(lexema)
        if siguientes:
            patron += "(?![" + "".join(re.escape(c) for c in siguientes) + "])"
        atributos[f"t_{token}"] = patron

    def t_OPERADOR_INCOMPLETO(self, t):
        r"(?!)"

    atributos["t_OPERADOR_INCOMPLETO"] = t_OPERADOR_INCOMPLETO
    return type("LexerConOperadores", (CompiladorLexer,), atributos)


LexerConOperadores = _construir_lexer_con_operadores()


@pytest.fixture(scope="module")
def parser() -> CompiladorParser:
    return CompiladorParser()


@pytest.fixture
def con_operadores(monkeypatch):
    """El parser crea su lexer con LexerConOperadores durante la prueba."""
    monkeypatch.setattr(modulo_parser, "CompiladorLexer", LexerConOperadores)


def analizar_ok(parser: CompiladorParser, texto: str):
    ast, errores = parser.analizar(texto)
    assert errores == [], [str(e) for e in errores]
    assert parser.errores_lexicos == [], [str(e) for e in parser.errores_lexicos]
    return ast


def cuerpo(parser: CompiladorParser, sentencias: str) -> list:
    """Elementos del bloque de 'void f() { <sentencias> }'."""
    ast = analizar_ok(parser, "void f() {\n" + sentencias + "\n}")
    return ast.declaraciones[0].cuerpo.elementos


def unica(parser: CompiladorParser, sentencia: str):
    elementos = cuerpo(parser, sentencia)
    assert len(elementos) == 1, elementos
    return elementos[0]


def expr(parser: CompiladorParser, texto: str):
    """Expresión de la sentencia 'x = <texto>;'."""
    asignacion = unica(parser, f"x = {texto};")
    assert isinstance(asignacion, Asignacion)
    return asignacion.valor


def I(nombre: str) -> Identificador:
    return Identificador(nombre)


def E(valor: int, lexema: str = None) -> LiteralEntero:
    return LiteralEntero(valor=valor, lexema=str(valor) if lexema is None else lexema)


def B(operador: str, izquierda, derecha) -> ExpresionBinaria:
    return ExpresionBinaria(operador, izquierda, derecha)


def asignar(destino: str, valor, operador: str = "=") -> Asignacion:
    return Asignacion(I(destino), operador, valor)


# ---------------------------------------------------------------------------
# 1. Construcción de la tabla LALR(1)
# ---------------------------------------------------------------------------

class TestConstruccion:
    def test_cero_conflictos(self, parser):
        assert parser.conflictos_shift_reduce == 0
        assert parser.conflictos_reduce_reduce == 0
        assert parser.registro.errores == []

    def test_todos_los_tokens_se_usan(self, parser):
        # PLY avisa "Token 'X' defined, but not used" por cada token sin regla
        assert parser.registro.avisos == []

    def test_operadores_adicionales_en_los_tokens_del_parser(self, parser):
        assert set(OPERADORES_ADICIONALES.values()) <= set(TOKENS_ADICIONALES)
        assert set(TOKENS_ADICIONALES) <= set(parser.tokens)
        assert len(parser.tokens) == len(set(parser.tokens))

    def test_contrato_de_operadores_cubre_la_gramatica_ebnf(self):
        ebnf = (RAIZ / "spl" / "compilador" / "gramatica_spl.ebnf").read_text(encoding="utf-8")
        for lexema in OPERADORES_ADICIONALES:
            assert f"'{lexema}'" in ebnf, lexema

    def test_el_unico_conflicto_resuelto_por_precedencia_es_el_else_colgante(self):
        # Sin la tabla de precedencia y sin %prec, PLY cuenta exactamente un
        # conflicto shift/reduce: el del else colgante.
        class SinPrecedencia(CompiladorParser):
            precedence = ()

            def p_sentencia_if(self, p):
                """sentencia_if : IF PARENTESIS_IZQ expresion PARENTESIS_DER then_opt sentencia
                                | IF PARENTESIS_IZQ expresion PARENTESIS_DER then_opt sentencia ELSE sentencia"""
                CompiladorParser.p_sentencia_if(self, p)

        sin = SinPrecedencia()
        assert (sin.conflictos_shift_reduce, sin.conflictos_reduce_reduce) == (1, 0)
        # PLY resuelve ese conflicto desplazando, igual que la tabla de precedencia
        ast, errores = sin.analizar("void f() { if (a) if (b) x = 1; else x = 2; }")
        assert errores == []
        externo = ast.declaraciones[0].cuerpo.elementos[0]
        assert externo.sino is None and externo.entonces.sino is not None


# ---------------------------------------------------------------------------
# 2. Bloques
# ---------------------------------------------------------------------------

class TestBloques:
    def test_bloque_vacio(self, parser):
        assert cuerpo(parser, "") == []

    def test_bloques_anidados(self, parser):
        externo = unica(parser, "{ { } { x = 1; } }")
        assert isinstance(externo, Bloque)
        assert externo.elementos == [Bloque([]), Bloque([asignar("x", E(1))])]

    def test_declaraciones_y_sentencias_intercaladas(self, parser):
        elementos = cuerpo(parser, "int a = 1; a = 2; float b; b = a;")
        assert [type(e) for e in elementos] == [
            DeclaracionVariable, Asignacion, DeclaracionVariable, Asignacion,
        ]

    def test_sentencia_vacia(self, parser):
        assert cuerpo(parser, ";;") == [SentenciaVacia(), SentenciaVacia()]

    def test_posicion_del_bloque(self, parser):
        b = unica(parser, "  { }")
        assert (b.linea, b.columna) == (2, 3)


# ---------------------------------------------------------------------------
# 3. Sentencias simples: expresión, asignación, ++ y --
# ---------------------------------------------------------------------------

class TestSentenciasSimples:
    def test_llamada_como_sentencia(self, parser):
        s = unica(parser, "registrar(1, x);")
        assert s == SentenciaExpresion(LlamadaFuncion(I("registrar"), [E(1), I("x")]))

    def test_asignacion_simple(self, parser):
        assert unica(parser, "x = y;") == asignar("x", I("y"))

    def test_destinos_indexados_y_campos(self, parser):
        s = unica(parser, "m[i][j].campo = 0;")
        assert s.destino == AccesoCampo(AccesoIndice(AccesoIndice(I("m"), I("i")), I("j")), "campo")

    def test_asignacion_no_es_expresion(self, parser):
        # La asignación es sentencia (SentenciaSimple), no operador de expresión
        _, errores = parser.analizar("void f() { x = y = 1; }")
        assert errores

    @pytest.mark.parametrize("lexema", [
        "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
    ])
    def test_asignacion_compuesta(self, parser, con_operadores, lexema):
        s = unica(parser, f"total {lexema} 3;")
        assert s == asignar("total", E(3), lexema)

    @pytest.mark.parametrize("lexema", ["++", "--"])
    def test_incremento_y_decremento(self, parser, con_operadores, lexema):
        s = unica(parser, f"v[i]{lexema};")
        assert s == IncrementoDecremento(AccesoIndice(I("v"), I("i")), lexema)

    def test_incremento_solo_como_sentencia(self, parser, con_operadores):
        _, errores = parser.analizar("void f() { x = i++; }")
        assert errores

    def test_posiciones(self, parser):
        s = unica(parser, "   x = 1;")
        assert (s.linea, s.columna) == (2, 4)


# ---------------------------------------------------------------------------
# 4. Selección: if / then / else
# ---------------------------------------------------------------------------

class TestIf:
    def test_if_sin_else(self, parser):
        s = unica(parser, "if (x) y = 1;")
        assert s == SentenciaIf(I("x"), asignar("y", E(1)))
        assert s.sino is None and not s.con_then

    def test_if_con_else_y_bloques(self, parser):
        s = unica(parser, "if (x < 0) { y = 1; } else { y = 2; }")
        assert s.condicion == B("<", I("x"), E(0))
        assert s.entonces == Bloque([asignar("y", E(1))])
        assert s.sino == Bloque([asignar("y", E(2))])

    def test_then_opcional(self, parser):
        con = unica(parser, "if (x) then y = 1; else y = 2;")
        sin = unica(parser, "if (x) y = 1; else y = 2;")
        assert con.con_then and not sin.con_then
        assert con == SentenciaIf(I("x"), asignar("y", E(1)), asignar("y", E(2)), con_then=True)
        assert sin == SentenciaIf(I("x"), asignar("y", E(1)), asignar("y", E(2)))

    def test_else_colgante_se_asocia_al_if_mas_cercano(self, parser):
        s = unica(parser, "if (a) if (b) x = 1; else x = 2;")
        assert s.sino is None
        assert s.entonces == SentenciaIf(I("b"), asignar("x", E(1)), asignar("x", E(2)))

    def test_else_colgante_a_traves_de_un_while(self, parser):
        s = unica(parser, "if (a) while (b) if (c) x = 1; else x = 2;")
        assert s.sino is None
        assert s.entonces.cuerpo.sino == asignar("x", E(2))

    def test_else_if_encadenado(self, parser):
        s = unica(parser, "if (a) x = 1; else if (b) x = 2; else x = 3;")
        assert s.sino == SentenciaIf(I("b"), asignar("x", E(2)), asignar("x", E(3)))

    def test_else_sin_if_es_error(self, parser):
        _, errores = parser.analizar("void f() { else x = 1; }")
        assert errores and errores[0].lexema == "else"

    def test_condicion_sin_parentesis_es_error(self, parser):
        _, errores = parser.analizar("void f() { if x y = 1; }")
        assert errores and errores[0].lexema == "x"

    def test_posicion(self, parser):
        s = unica(parser, "  if (x) ;")
        assert (s.linea, s.columna) == (2, 3)


# ---------------------------------------------------------------------------
# 5. Selección múltiple: switch / case / default
# ---------------------------------------------------------------------------

class TestSwitch:
    def test_casos_y_default(self, parser):
        s = unica(parser, """
            switch (op) {
                case 1: x = 10; break;
                case 2: x = 20; break;
                default: x = 0;
            }
        """)
        assert isinstance(s, SentenciaSwitch) and s.expresion == I("op")
        assert s.casos == [
            ClausulaCase(E(1), [asignar("x", E(10)), SentenciaBreak()]),
            ClausulaCase(E(2), [asignar("x", E(20)), SentenciaBreak()]),
        ]
        assert s.defecto == ClausulaDefault([asignar("x", E(0))])

    def test_switch_vacio_y_solo_default(self, parser):
        assert unica(parser, "switch (x) { }") == SentenciaSwitch(I("x"), [], None)
        s = unica(parser, "switch (x) { default: ; }")
        assert s.casos == [] and s.defecto == ClausulaDefault([SentenciaVacia()])

    def test_casos_sin_cuerpo_comparten_el_siguiente(self, parser):
        s = unica(parser, "switch (c) { case 1: case 2: x = 1; }")
        assert [c.cuerpo for c in s.casos] == [[], [asignar("x", E(1))]]

    def test_constantes_case_admitidas(self, parser):
        s = unica(parser, "switch (c) { case 0x1F: case 0b101: case -3: case 'a': }")
        assert [c.valor for c in s.casos] == [
            E(31, "0x1F"),
            E(5, "0b101"),
            ExpresionUnaria("-", E(3)),
            LiteralCaracter("a", "'a'"),
        ]

    def test_case_booleano_con_tokens_del_literal_b(self, parser, monkeypatch):
        class LexerConBooleanos(CompiladorLexer):
            def token(self):
                tok = super().token()
                if tok is not None and tok.type == "ID" and tok.value in ("true", "false"):
                    tok.type = "TRUE_LIT" if tok.value == "true" else "FALSE_LIT"
                return tok

        monkeypatch.setattr(modulo_parser, "CompiladorLexer", LexerConBooleanos)
        s = unica(parser, "switch (b) { case true: x = 1; case false: x = 0; }")
        assert [c.valor for c in s.casos] == [LiteralBooleano(True), LiteralBooleano(False)]

    def test_declaraciones_dentro_de_un_case(self, parser):
        s = unica(parser, "switch (c) { case 1: int t = 2; x = t; break; }")
        assert [type(e) for e in s.casos[0].cuerpo] == [DeclaracionVariable, Asignacion, SentenciaBreak]

    @pytest.mark.parametrize("etiqueta", ["1.5", '"uno"', "x", "a + 1"])
    def test_case_no_constante_es_error(self, parser, etiqueta):
        _, errores = parser.analizar(f"void f() {{ switch (c) {{ case {etiqueta}: ; }} }}")
        assert errores

    def test_default_antes_de_un_case_es_error(self, parser):
        _, errores = parser.analizar("void f() { switch (c) { default: ; case 1: ; } }")
        assert errores and errores[0].lexema == "case"

    def test_posiciones(self, parser):
        s = unica(parser, "switch (c) {\n case 1: ;\n default: ;\n}")
        assert (s.casos[0].linea, s.casos[0].columna) == (3, 2)
        assert (s.defecto.linea, s.defecto.columna) == (4, 2)


# ---------------------------------------------------------------------------
# 6. Iteración: while, do-while y for
# ---------------------------------------------------------------------------

class TestIteracion:
    def test_while(self, parser):
        s = unica(parser, "while (b != 0) { b = b - 1; }")
        assert s == SentenciaWhile(B("!=", I("b"), E(0)),
                                   Bloque([asignar("b", B("-", I("b"), E(1)))]))

    def test_while_con_cuerpo_simple(self, parser):
        assert unica(parser, "while (x) ;") == SentenciaWhile(I("x"), SentenciaVacia())

    def test_do_while(self, parser):
        s = unica(parser, "do x = x - 1; while (x > 0);")
        assert s == SentenciaDoWhile(asignar("x", B("-", I("x"), E(1))), B(">", I("x"), E(0)))

    def test_do_while_sin_punto_y_coma_es_error(self, parser):
        _, errores = parser.analizar("void f() { do { } while (x) }")
        assert errores and errores[0].lexema == "}"

    def test_for_con_declaracion(self, parser):
        s = unica(parser, "for (int i = 0; i < 5; i = i + 1) suma = suma + i;")
        assert s.inicial == DeclaracionVariable(
            EspecificadorTipo("int"), [Declarador("i", [], E(0))]
        )
        assert s.condicion == B("<", I("i"), E(5))
        assert s.paso == asignar("i", B("+", I("i"), E(1)))
        assert s.cuerpo == asignar("suma", B("+", I("suma"), I("i")))

    def test_for_con_declaracion_sin_inicializar(self, parser):
        s = unica(parser, "for (float x; x < 1.0; ) ;")
        assert s.inicial.declaradores == [Declarador("x")]
        assert s.condicion == B("<", I("x"), LiteralFlotante(1.0, "1.0"))
        assert s.paso is None

    def test_for_con_asignacion_inicial(self, parser):
        s = unica(parser, "for (i = 0; ; ) { }")
        assert s.inicial == asignar("i", E(0))
        assert s.condicion is None and s.paso is None

    def test_for_infinito(self, parser):
        assert unica(parser, "for (;;) ;") == SentenciaFor(None, None, None, SentenciaVacia())

    def test_for_con_paso_compuesto(self, parser, con_operadores):
        s = unica(parser, "for (int i = 0; i < n; i++) total += i;")
        assert s.paso == IncrementoDecremento(I("i"), "++")
        assert s.cuerpo == asignar("total", I("i"), "+=")

    def test_for_con_tipo_alias_y_tda(self, parser):
        ast = analizar_ok(parser, """
            typedef int Indice;
            void f() {
                for (Indice k = 0; k < 2; k = k + 1) ;
                for (const int j = 1; j; ) ;
            }
        """)
        primero, segundo = ast.declaraciones[1].cuerpo.elementos
        assert primero.inicial.tipo.nombre == "Indice"
        assert segundo.inicial.tipo.es_const

    def test_for_con_varios_declaradores_es_error(self, parser):
        _, errores = parser.analizar("void f() { for (int i = 0, j = 1; ; ) ; }")
        assert errores

    def test_posicion_del_declarador_del_for(self, parser):
        s = unica(parser, "for (int i = 0; ; ) ;")
        assert (s.inicial.declaradores[0].linea, s.inicial.declaradores[0].columna) == (2, 10)


# ---------------------------------------------------------------------------
# 7. Saltos: return, break y continue
# ---------------------------------------------------------------------------

class TestSaltos:
    def test_return_con_y_sin_valor(self, parser):
        assert cuerpo(parser, "return; return a + 1;") == [
            SentenciaReturn(), SentenciaReturn(B("+", I("a"), E(1))),
        ]

    def test_break_y_continue(self, parser):
        elementos = cuerpo(parser, "while (1) { break; continue; }")
        assert elementos[0].cuerpo.elementos == [SentenciaBreak(), SentenciaContinue()]

    def test_break_sin_punto_y_coma_es_error(self, parser):
        _, errores = parser.analizar("void f() { while (1) { break } }")
        assert errores and errores[0].lexema == "}"

    def test_posiciones(self, parser):
        b, c = cuerpo(parser, " break;\n  continue;")
        assert (b.linea, b.columna, c.linea, c.columna) == (2, 2, 3, 3)


# ---------------------------------------------------------------------------
# 8. Expresiones: 13 niveles de precedencia y asociatividad izquierda
# ---------------------------------------------------------------------------

# Un operador representativo por nivel binario, de menor a mayor precedencia
NIVELES_BINARIOS = [
    ("expr_or", "||"),
    ("expr_and", "&&"),
    ("expr_bit_or", "|"),
    ("expr_bit_xor", "^"),
    ("expr_bit_and", "&"),
    ("expr_igualdad", "=="),
    ("expr_relacional", "<"),
    ("expr_shift", "<<"),
    ("expr_aditiva", "+"),
    ("expr_multiplicativa", "*"),
]

OPERADORES_BINARIOS = [
    "||", "&&", "|", "^", "&", "==", "!=", "<", "<=", ">", ">=",
    "<<", ">>", "+", "-", "*", "/", "%",
]


class TestExpresiones:
    @pytest.mark.parametrize("i", range(len(NIVELES_BINARIOS) - 1))
    def test_cada_nivel_liga_mas_que_el_anterior(self, parser, con_operadores, i):
        bajo, alto = NIVELES_BINARIOS[i][1], NIVELES_BINARIOS[i + 1][1]
        # a BAJO b ALTO c  ==  a BAJO (b ALTO c)
        assert expr(parser, f"a {bajo} b {alto} c") == B(bajo, I("a"), B(alto, I("b"), I("c")))
        # a ALTO b BAJO c  ==  (a ALTO b) BAJO c
        assert expr(parser, f"a {alto} b {bajo} c") == B(bajo, B(alto, I("a"), I("b")), I("c"))

    @pytest.mark.parametrize("op", OPERADORES_BINARIOS)
    def test_asociatividad_izquierda(self, parser, con_operadores, op):
        assert expr(parser, f"a {op} b {op} c") == B(op, B(op, I("a"), I("b")), I("c"))

    def test_mismo_nivel_se_agrupa_por_la_izquierda(self, parser, con_operadores):
        assert expr(parser, "a - b + c") == B("+", B("-", I("a"), I("b")), I("c"))
        assert expr(parser, "a < b >= c") == B(">=", B("<", I("a"), I("b")), I("c"))
        assert expr(parser, "a >> b << c") == B("<<", B(">>", I("a"), I("b")), I("c"))

    def test_parentesis_cambian_la_agrupacion(self, parser):
        assert expr(parser, "(a + b) * c") == B("*", B("+", I("a"), I("b")), I("c"))

    def test_unarios_anidados_y_sobre_postfijos(self, parser, con_operadores):
        assert expr(parser, "- -x") == ExpresionUnaria("-", ExpresionUnaria("-", I("x")))
        assert expr(parser, "!~v[0]") == ExpresionUnaria(
            "!", ExpresionUnaria("~", AccesoIndice(I("v"), E(0)))
        )
        # El unario liga más que el multiplicativo: -a * b == (-a) * b
        assert expr(parser, "-a * b") == B("*", ExpresionUnaria("-", I("a")), I("b"))

    def test_sizeof_de_tipo_y_de_expresion(self, parser):
        assert expr(parser, "sizeof(int) + sizeof(v)") == B(
            "+", Sizeof(EspecificadorTipo("int")), Sizeof(I("v"))
        )

    def test_cadena_de_postfijos(self, parser):
        assert expr(parser, "f(a)[1].c") == AccesoCampo(
            AccesoIndice(LlamadaFuncion(I("f"), [I("a")]), E(1)), "c"
        )

    def test_flecha(self, parser):
        assert expr(parser, "p->x") == AccesoCampo(I("p"), "x", por_puntero=True)

    def test_comparacion_de_igualdad_y_logica_estilo_c(self, parser, con_operadores):
        # Como en C: '&' liga menos que '==' y '<' menos que '<<'
        assert expr(parser, "a & b == c") == B("&", I("a"), B("==", I("b"), I("c")))
        assert expr(parser, "a < b << 1") == B("<", I("a"), B("<<", I("b"), E(1)))

    def test_trece_niveles_en_una_expresion(self, parser, con_operadores):
        e = expr(parser, "a || b && c | d ^ e & f == g < h << i + j * -k[0]")
        esperado = B("||", I("a"), B("&&", I("b"), B("|", I("c"), B("^", I("d"), B(
            "&", I("e"), B("==", I("f"), B("<", I("g"), B("<<", I("h"), B(
                "+", I("i"), B("*", I("j"), ExpresionUnaria("-", AccesoIndice(I("k"), E(0))))
            ))))
        )))))
        assert e == esperado

    def test_posicion_de_la_binaria_es_la_del_operando_izquierdo(self, parser):
        e = expr(parser, "aa + 1")
        assert (e.linea, e.columna) == (2, 5)


# ---------------------------------------------------------------------------
# 9. Recuperación de errores por sentencia y por bloque
# ---------------------------------------------------------------------------

class TestRecuperacion:
    def test_descarta_la_sentencia_y_continua(self, parser):
        ast, errores = parser.analizar("void f() {\n x = ;\n y = 2;\n}")
        assert len(errores) == 1 and errores[0].linea == 2
        assert ast.declaraciones[0].cuerpo.elementos == [asignar("y", E(2))]

    def test_falta_punto_y_coma_antes_de_cierre_de_bloque(self, parser):
        ast, errores = parser.analizar("void f() { a = 1; b = 2 }\nint g;")
        assert len(errores) == 1 and errores[0].lexema == "}"
        funcion, variable = ast.declaraciones
        assert funcion.cuerpo.elementos == [asignar("a", E(1))]
        assert variable.nombres == ["g"]

    def test_varios_errores_en_una_funcion(self, parser):
        ast, errores = parser.analizar("void f() {\n a = ;\n b = 1;\n c = = 2;\n d = 3;\n}")
        assert [e.linea for e in errores] == [2, 4]
        assert ast.declaraciones[0].cuerpo.elementos == [asignar("b", E(1)), asignar("d", E(3))]

    def test_cuerpo_descartado_queda_como_sentencia_vacia(self, parser):
        ast, errores = parser.analizar("void f() { while (x) y = ; z = 1; }")
        assert len(errores) == 1
        bucle, siguiente = ast.declaraciones[0].cuerpo.elementos
        assert bucle == SentenciaWhile(I("x"), SentenciaVacia())
        assert siguiente == asignar("z", E(1))

    def test_error_dentro_de_un_case(self, parser):
        ast, errores = parser.analizar("void f() { switch (c) { case 1: x = ; y = 1; break; } }")
        assert len(errores) == 1
        caso = ast.declaraciones[0].cuerpo.elementos[0].casos[0]
        assert caso.cuerpo == [asignar("y", E(1)), SentenciaBreak()]

    def test_las_funciones_siguientes_se_conservan(self, parser):
        ast, errores = parser.analizar("int f() { return 1 }\nint g() { return 2; }")
        assert len(errores) == 1
        assert [f.nombre for f in ast.funciones()] == ["f", "g"]
        assert ast.funciones()[1].cuerpo.elementos == [SentenciaReturn(E(2))]

    def test_bloque_sin_cerrar_al_final_del_archivo(self, parser):
        ast, errores = parser.analizar("int a;\nvoid f() { x = 1;")
        assert errores[-1].lexema == "<EOF>"
        assert ast.declaraciones[0].nombres == ["a"]


# ---------------------------------------------------------------------------
# 10. Mensajes de p_error
# ---------------------------------------------------------------------------

class TestMensajes:
    def mensaje(self, parser, texto: str) -> str:
        _, errores = parser.analizar(texto)
        assert errores
        return errores[0].mensaje

    def test_falta_punto_y_coma(self, parser):
        assert self.mensaje(parser, "void f() { x = 1 }") == "token inesperado LLAVE_DER; se esperaba ';'"

    def test_no_lista_busquedas_de_otro_contexto(self, parser):
        # La fila LALR(1) del estado también trae ')' (paso de un for): no se lista
        assert "')'" not in self.mensaje(parser, "void f() { x = 1 }")

    def test_constante_de_case(self, parser):
        assert self.mensaje(parser, "void f() { switch (c) { case y: ; } }") == (
            "token inesperado ID; se esperaba '-', 'false', 'true', caracter o entero"
        )

    def test_parametros(self, parser):
        assert self.mensaje(parser, "int f(int a { }") == (
            "token inesperado LLAVE_IZQ; se esperaba ')', ',' o '['"
        )

    def test_omite_la_lista_si_hay_demasiadas_opciones(self, parser):
        # Tras 'x =' cabe cualquier inicio de expresión
        assert self.mensaje(parser, "void f() { x = ; }") == "token inesperado PUNTO_Y_COMA"
        assert MAX_TOKENS_ESPERADOS == 6

    def test_fin_de_archivo(self, parser):
        _, errores = parser.analizar("void f() {")
        assert errores[-1].lexema == "<EOF>"
        assert errores[-1].mensaje.startswith("fin de archivo inesperado")

    def test_formato_y_callback(self):
        recibidos = []
        p = CompiladorParser(al_error=recibidos.append)
        p.analizar("void f() {\n  return 1\n}")
        assert len(recibidos) == 1 and isinstance(recibidos[0], ErrorSintactico)
        assert str(recibidos[0]) == (
            "ERROR SINTACTICO (linea 3, columna 1): token inesperado LLAVE_DER; "
            "se esperaba ';': '}'"
        )


# ---------------------------------------------------------------------------
# 11. Programas completos
# ---------------------------------------------------------------------------

class TestProgramas:
    def test_escenario2_control_funciones(self, parser):
        texto = (EJEMPLOS_COMPILADOR / "escenario2_control_funciones.spl").read_text(encoding="utf-8")
        ast = analizar_ok(parser, texto)
        promedio, despachar = ast.funciones()
        tipos = [type(e).__name__ for e in promedio.cuerpo.elementos]
        assert tipos == [
            "DeclaracionVariable", "DeclaracionVariable", "SentenciaWhile",
            "SentenciaDoWhile", "SentenciaFor", "SentenciaReturn",
        ]
        do_while = promedio.cuerpo.elementos[3]
        assert do_while.cuerpo.elementos[0].entonces == Bloque([SentenciaBreak()])
        selector, condicional = despachar.cuerpo.elementos
        assert [c.valor for c in selector.casos] == [E(1), E(2)]
        assert selector.defecto.cuerpo == [SentenciaReturn()]
        assert condicional.con_then and condicional.sino is not None

    @pytest.mark.parametrize("archivo", [
        "escenario1_aritmetica_tda.spl",
        "escenario2_punto_flotante_switch.spl",
    ])
    def test_escenarios_del_pipeline_tras_preprocesar(self, parser, archivo):
        texto = preprocesar_archivo(str(EJEMPLOS_PIPELINE / archivo)).texto
        ast = analizar_ok(parser, texto)
        assert ast.funciones()

    def test_programa_1_euclides(self, parser):
        ast = analizar_ok(parser, """
            int resultado;
            function int mcd(int a, int b) {
                while (b != 0) {
                    int r = a % b;
                    a = b;
                    b = r;
                }
                return a;
            }
            function int main() {
                int m = mcd(1071, 462);
                if (m == 21) then {
                    resultado = m;
                } else {
                    resultado = -1;
                }
                return mcd(48, 18);
            }
        """)
        mcd = ast.funciones()[0]
        bucle = mcd.cuerpo.elementos[0]
        assert bucle.condicion == B("!=", I("b"), E(0))
        assert bucle.cuerpo.elementos[0].declaradores[0].inicializador == B("%", I("a"), I("b"))

    def test_programa_5_tda_switch_float(self, parser):
        ast = analizar_ok(parser, """
            tda RegistroSensor { int id; int modo; float lectura; float escala; float resultado; };
            tda RegistroSensor sensores[2];
            function float procesar(tda RegistroSensor s) {
                switch (s.modo) {
                    case 1: s.resultado = s.lectura * s.escala; break;
                    case 2: s.resultado = s.lectura + s.escala; break;
                    default: s.resultado = 0.0;
                }
                return s.resultado;
            }
        """)
        selector = ast.funciones()[0].cuerpo.elementos[0]
        assert selector.expresion == AccesoCampo(I("s"), "modo")
        assert selector.casos[0].cuerpo[0].valor == B(
            "*", AccesoCampo(I("s"), "lectura"), AccesoCampo(I("s"), "escala")
        )

    def test_volcado_del_arbol(self, parser):
        ast = analizar_ok(parser, "void f() { if (x) then y = 1; else ; }")
        texto = formatear_ast(ast)
        assert "SentenciaIf(con_then=True)" in texto
        assert "sino: SentenciaVacia" in texto
