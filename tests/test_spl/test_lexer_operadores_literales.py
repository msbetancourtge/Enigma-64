"""
Suite de pruebas del analizador léxico del Compilador SPL.
Fase 1: Operadores aritméticos, lógicos y relacionales, literales numéricos
(enteros base 10 / base 16, flotantes en punto fijo y notación científica) y
cadenas de texto con secuencias de escape (Integrante 5).
"""

import struct
import sys
import subprocess
from pathlib import Path

import pytest

from spl.compilador.lexer import (
    CompiladorLexer,
    OPERADORES,
    OPERADORES_RELACIONALES,
    OPERADORES_ARITMETICOS,
    OPERADORES_LOGICOS,
    SUBCODIGOS_RELACIONALES,
    SUBCODIGOS_ARITMETICOS,
    SUBCODIGOS_LOGICOS,
    SUB_NUM_ENTERO_DEC,
    SUB_NUM_ENTERO_HEX,
    SUB_NUM_REAL_DECIMAL,
    SUB_NUM_REAL_CIENTIFICO,
    SUB_CADENA,
    SUB_CARACTER,
    CAT_OPERADOR_RELACIONAL,
    CAT_OPERADOR_ARITMETICO,
    CAT_OPERADOR_LOGICO,
    CAT_OPERADOR_ASIGNACION,
    CAT_CONSTANTE_NUMERICA,
    CAT_CADENA_LITERAL,
    obtener_categoria_y_subcodigo,
)
from spl.compilador.tablas import TipoNumero

RAIZ = Path(__file__).parent.parent.parent
EJEMPLOS = RAIZ / "spl" / "compilador" / "ejemplos"


@pytest.fixture
def lexer():
    """Instancia limpia de CompiladorLexer para cada prueba."""
    return CompiladorLexer()


def _tipos(tokens):
    return [t.type for t in tokens]


# ===========================================================================
# 1. Operadores aritméticos, relacionales y lógicos
# ===========================================================================

@pytest.mark.parametrize("lexema,tipo", sorted(OPERADORES_ARITMETICOS.items()))
def test_operadores_aritmeticos(lexer, lexema, tipo):
    tokens, errores = lexer.tokenizar(f"a {lexema} b")
    assert not errores
    assert _tipos(tokens) == ["ID", tipo, "ID"]
    assert tokens[1].value == lexema
    assert tokens[1].categoria_codigo == CAT_OPERADOR_ARITMETICO
    assert tokens[1].subcodigo == SUBCODIGOS_ARITMETICOS[tipo]


@pytest.mark.parametrize("lexema,tipo", sorted(OPERADORES_RELACIONALES.items()))
def test_operadores_relacionales(lexer, lexema, tipo):
    tokens, errores = lexer.tokenizar(f"a {lexema} b")
    assert not errores
    assert _tipos(tokens) == ["ID", tipo, "ID"]
    assert tokens[1].categoria_codigo == CAT_OPERADOR_RELACIONAL
    assert tokens[1].subcodigo == SUBCODIGOS_RELACIONALES[tipo]


@pytest.mark.parametrize("lexema,tipo", sorted(OPERADORES_LOGICOS.items()))
def test_operadores_logicos(lexer, lexema, tipo):
    tokens, errores = lexer.tokenizar(f"a {lexema} b")
    assert not errores
    assert _tipos(tokens) == ["ID", tipo, "ID"]
    assert tokens[1].categoria_codigo == CAT_OPERADOR_LOGICO
    assert tokens[1].subcodigo == SUBCODIGOS_LOGICOS[tipo]


def test_subcodigos_de_operadores_son_unicos_por_categoria():
    for subcodigos in (SUBCODIGOS_RELACIONALES, SUBCODIGOS_ARITMETICOS, SUBCODIGOS_LOGICOS):
        assert len(set(subcodigos.values())) == len(subcodigos)
    assert set(OPERADORES.values()) == (
        set(SUBCODIGOS_RELACIONALES) | set(SUBCODIGOS_ARITMETICOS) | set(SUBCODIGOS_LOGICOS)
    )
    for tipo, sub in SUBCODIGOS_RELACIONALES.items():
        assert obtener_categoria_y_subcodigo(tipo) == (CAT_OPERADOR_RELACIONAL, sub)


def test_maximal_munch_sin_espacios(lexer):
    """Los operadores de dos caracteres tienen prioridad sobre los de uno."""
    tokens, errores = lexer.tokenizar("a<=b>=c==d!=e&&f||!g<h>i=j")
    assert not errores
    assert _tipos(tokens) == [
        "ID", "MENOR_IGUAL", "ID", "MAYOR_IGUAL", "ID", "IGUAL", "ID",
        "DISTINTO", "ID", "AND_LOGICO", "ID", "OR_LOGICO", "NOT_LOGICO", "ID",
        "MENOR", "ID", "MAYOR", "ID", "ASIGNAR", "ID",
    ]


def test_asignacion_frente_a_igualdad(lexer):
    tokens, errores = lexer.tokenizar("x = y == z")
    assert not errores
    assert _tipos(tokens) == ["ID", "ASIGNAR", "ID", "IGUAL", "ID"]
    assert tokens[1].categoria_codigo == CAT_OPERADOR_ASIGNACION


def test_negacion_y_distinto(lexer):
    tokens, errores = lexer.tokenizar("!!a != !b")
    assert not errores
    assert _tipos(tokens) == ["NOT_LOGICO", "NOT_LOGICO", "ID", "DISTINTO", "NOT_LOGICO", "ID"]


def test_division_frente_a_comentarios(lexer):
    tokens, errores = lexer.tokenizar("a / b // comentario\nc /* bloque */ / d")
    assert not errores
    assert _tipos(tokens) == ["ID", "DIV", "ID", "ID", "DIV", "ID"]
    assert lexer.comentarios == 2


def test_resta_y_flecha(lexer):
    tokens, errores = lexer.tokenizar("a-b p->x a - -1")
    assert not errores
    assert _tipos(tokens) == ["ID", "MENOS", "ID", "ID", "FLECHA", "ID", "ID", "MENOS", "MENOS", "ENTERO_DEC"]


@pytest.mark.parametrize("codigo,lexema", [("a & b", "&"), ("a | b", "|"), ("a &&& b", "&")])
def test_operador_logico_incompleto(lexer, codigo, lexema):
    tokens, errores = lexer.tokenizar(codigo)
    assert len(errores) == 1
    assert errores[0].lexema == lexema
    assert "operador logico incompleto" in errores[0].mensaje
    assert _tipos(tokens)[0] == "ID" and _tipos(tokens)[-1] == "ID"


# ===========================================================================
# 2. Literales enteros (base 10 y base 16)
# ===========================================================================

@pytest.mark.parametrize("lexema,valor", [
    ("0", 0), ("7", 7), ("42", 42), ("1000", 1000),
    ("9223372036854775807", 2**63 - 1),
])
def test_entero_decimal(lexer, lexema, valor):
    tokens, errores = lexer.tokenizar(lexema)
    assert not errores
    assert _tipos(tokens) == ["ENTERO_DEC"]
    tok = tokens[0]
    assert tok.categoria_codigo == CAT_CONSTANTE_NUMERICA
    assert tok.subcodigo == SUB_NUM_ENTERO_DEC
    entrada = lexer.tablas.tabla_num.obtener(tok.simbolo_idx)
    assert entrada.tipo == TipoNumero.ENTERO_DECIMAL
    assert entrada.valor_int == valor


@pytest.mark.parametrize("lexema,valor_uint", [
    ("0x0", 0), ("0xFF", 255), ("0Xff", 255), ("0xDeadBeef", 0xDEADBEEF),
    ("0x7FFFFFFFFFFFFFFF", 2**63 - 1), ("0xFFFFFFFFFFFFFFFF", 2**64 - 1),
    ("0x0000000000000000001", 1),
])
def test_entero_hexadecimal(lexer, lexema, valor_uint):
    tokens, errores = lexer.tokenizar(lexema)
    assert not errores
    assert _tipos(tokens) == ["ENTERO_HEX"]
    assert tokens[0].subcodigo == SUB_NUM_ENTERO_HEX
    entrada = lexer.tablas.tabla_num.obtener(tokens[0].simbolo_idx)
    assert entrada.tipo == TipoNumero.ENTERO_HEX
    assert entrada.valor_uint == valor_uint


def test_hex_de_64_bits_se_reinterpreta_en_complemento_a_dos(lexer):
    tokens, _ = lexer.tokenizar("0xFFFFFFFFFFFFFFFF")
    assert lexer.tablas.tabla_num.obtener(tokens[0].simbolo_idx).valor_int == -1


def test_entero_negativo_es_operador_unario(lexer):
    tokens, errores = lexer.tokenizar("-15")
    assert not errores
    assert _tipos(tokens) == ["MENOS", "ENTERO_DEC"]


@pytest.mark.parametrize("lexema", ["9223372036854775808", "99999999999999999999999"])
def test_entero_decimal_fuera_de_rango(lexer, lexema):
    tokens, errores = lexer.tokenizar(lexema)
    assert tokens == []
    assert len(errores) == 1
    assert "64 bits" in errores[0].mensaje
    assert lexer.tablas.tabla_num.total == 0


def test_entero_hex_fuera_de_rango(lexer):
    tokens, errores = lexer.tokenizar("0x10000000000000000")
    assert tokens == []
    assert len(errores) == 1
    assert "hexadecimal excede" in errores[0].mensaje


@pytest.mark.parametrize("lexema", ["0xZZ1", "0xFFG1", "12abc", "0x", "45xyz"])
def test_enteros_mal_formados(lexer, lexema):
    tokens, errores = lexer.tokenizar(lexema)
    assert tokens == []
    assert len(errores) == 1
    assert errores[0].lexema == lexema


# ===========================================================================
# 3. Literales flotantes (punto fijo y notación científica)
# ===========================================================================

@pytest.mark.parametrize("lexema,valor", [
    ("3.14", 3.14), ("0.0", 0.0), ("100.0", 100.0),
    (".5", 0.5), ("5.", 5.0), ("0.000001", 1e-6),
])
def test_flotante_punto_fijo(lexer, lexema, valor):
    tokens, errores = lexer.tokenizar(lexema)
    assert not errores
    assert _tipos(tokens) == ["FLOTANTE"]
    assert tokens[0].subcodigo == SUB_NUM_REAL_DECIMAL
    entrada = lexer.tablas.tabla_num.obtener(tokens[0].simbolo_idx)
    assert entrada.tipo == TipoNumero.REAL_DECIMAL
    assert entrada.valor_float == valor


@pytest.mark.parametrize("lexema,valor", [
    ("1e10", 1e10), ("1E10", 1e10), ("2.5e-3", 2.5e-3), ("2.5E+3", 2.5e3),
    (".5e2", 50.0), ("5.e3", 5000.0), ("6.022e23", 6.022e23),
    ("1.7976931348623157e308", 1.7976931348623157e308),
    ("4.9e-324", 5e-324), ("0e0", 0.0),
])
def test_flotante_notacion_cientifica(lexer, lexema, valor):
    tokens, errores = lexer.tokenizar(lexema)
    assert not errores
    assert _tipos(tokens) == ["FLOTANTE"]
    assert tokens[0].subcodigo == SUB_NUM_REAL_CIENTIFICO
    entrada = lexer.tablas.tabla_num.obtener(tokens[0].simbolo_idx)
    assert entrada.tipo == TipoNumero.REAL_CIENTIFICO
    assert entrada.valor_float == valor


def test_flotante_patron_ieee754(lexer):
    tokens, _ = lexer.tokenizar("10.5")
    entrada = lexer.tablas.tabla_num.obtener(tokens[0].simbolo_idx)
    assert entrada.patron_ieee754_hex == struct.pack(">d", 10.5).hex().upper()
    assert entrada.patron_ieee754_hex == "4025000000000000"


def test_flotante_en_expresion_y_acceso_a_campo(lexer):
    tokens, errores = lexer.tokenizar("p.x = .5 * v[2].y + 5.;")
    assert not errores
    assert _tipos(tokens) == [
        "ID", "PUNTO", "ID", "ASIGNAR", "FLOTANTE", "POR",
        "ID", "CORCHETE_IZQ", "ENTERO_DEC", "CORCHETE_DER", "PUNTO", "ID",
        "MAS", "FLOTANTE", "PUNTO_Y_COMA",
    ]


def test_flotante_desbordado(lexer):
    tokens, errores = lexer.tokenizar("1e309")
    assert tokens == []
    assert len(errores) == 1
    assert "desborda" in errores[0].mensaje


def test_flotante_subdesbordado(lexer):
    tokens, errores = lexer.tokenizar("1e-400")
    assert tokens == []
    assert len(errores) == 1
    assert "subdesborda" in errores[0].mensaje


@pytest.mark.parametrize("lexema", ["1e+", "2.5E-", ".5e+"])
def test_exponente_sin_digitos(lexer, lexema):
    tokens, errores = lexer.tokenizar(lexema + " ;")
    assert _tipos(tokens) == ["PUNTO_Y_COMA"]
    assert len(errores) == 1
    assert errores[0].lexema == lexema
    assert "exponente" in errores[0].mensaje


@pytest.mark.parametrize("lexema", ["1e", "1.2.3", "3.14abc", ".5x", "1..2"])
def test_flotantes_mal_formados(lexer, lexema):
    tokens, errores = lexer.tokenizar(lexema)
    assert tokens == []
    assert len(errores) == 1
    assert errores[0].lexema == lexema


def test_literales_numericos_se_deduplican(lexer):
    tokens, errores = lexer.tokenizar("1.5 + 1.5 + 0xFF + 0xFF + 7 + 7")
    assert not errores
    nums = [t for t in tokens if t.categoria_codigo == CAT_CONSTANTE_NUMERICA]
    assert [t.simbolo_idx for t in nums] == [1, 1, 2, 2, 3, 3]
    assert lexer.tablas.tabla_num.total == 3


# ===========================================================================
# 4. Cadenas de texto y caracteres con secuencias de escape
# ===========================================================================

@pytest.mark.parametrize("fuente,texto", [
    (r'"hola"', "hola"),
    (r'""', ""),
    (r'"linea\n"', "linea\n"),
    (r'"a\tb"', "a\tb"),
    (r'"cr\r"', "cr\r"),
    (r'"nulo\0"', "nulo\0"),
    (r'"barra \\ fin"', "barra \\ fin"),
    (r'"dice \"hola\""', 'dice "hola"'),
    (r'"apostrofo \'"', "apostrofo '"),
    (r'"C:\\Enigma64\\log.txt"', "C:\\Enigma64\\log.txt"),
])
def test_cadenas_con_escapes(lexer, fuente, texto):
    tokens, errores = lexer.tokenizar(fuente)
    assert not errores
    assert _tipos(tokens) == ["STRING"]
    assert tokens[0].categoria_codigo == CAT_CADENA_LITERAL
    assert tokens[0].subcodigo == SUB_CADENA
    entrada = lexer.tablas.tabla_string.obtener(tokens[0].simbolo_idx)
    assert entrada.texto == texto
    assert entrada.longitud == len(texto)


def test_cadena_no_interpreta_operadores_ni_comentarios(lexer):
    tokens, errores = lexer.tokenizar('"a + b // no es comentario /* ni esto */"')
    assert not errores
    assert _tipos(tokens) == ["STRING"]
    assert lexer.comentarios == 0


def test_cadenas_se_deduplican_por_texto_limpio(lexer):
    tokens, errores = lexer.tokenizar('"x\\ty" "x\\ty" "otra"')
    assert not errores
    assert [t.simbolo_idx for t in tokens] == [1, 1, 2]
    assert lexer.tablas.tabla_string.total == 2


@pytest.mark.parametrize("fuente,escape", [(r'"mal \q"', r"\q"), (r'"ok \n luego \x41"', r"\x")])
def test_cadena_con_escape_invalido(lexer, fuente, escape):
    tokens, errores = lexer.tokenizar(fuente + " ;")
    assert _tipos(tokens) == ["PUNTO_Y_COMA"]
    assert len(errores) == 1
    assert f"'{escape}'" in errores[0].mensaje
    assert errores[0].lexema == fuente
    assert lexer.tablas.tabla_string.total == 0


def test_cadena_sin_cerrar_se_recupera_en_la_linea_siguiente(lexer):
    tokens, errores = lexer.tokenizar('s = "sin cierre;\nint x = 1;')
    assert len(errores) == 1
    assert errores[0].linea == 1
    assert errores[0].lexema == '"sin cierre;'
    assert "sin cerrar" in errores[0].mensaje
    assert _tipos(tokens) == ["ID", "ASIGNAR", "INT_TYPE", "ID", "ASIGNAR", "ENTERO_DEC", "PUNTO_Y_COMA"]
    assert tokens[2].lineno == 2


def test_cadena_sin_cerrar_terminada_en_barra(lexer):
    tokens, errores = lexer.tokenizar('"abc\\\nx')
    assert len(errores) == 1
    assert errores[0].lexema == '"abc\\'
    assert _tipos(tokens) == ["ID"]


@pytest.mark.parametrize("fuente", ["'a'", "'\\n'", "'\\t'", "'\\''", "'\\\\'", "'\"'"])
def test_literales_de_caracter(lexer, fuente):
    tokens, errores = lexer.tokenizar(fuente)
    assert not errores
    assert _tipos(tokens) == ["CHAR_LITERAL"]
    assert tokens[0].subcodigo == SUB_CARACTER


@pytest.mark.parametrize("fuente", ["'ab'", "''", "'\\q'", "'a"])
def test_literales_de_caracter_mal_formados(lexer, fuente):
    tokens, errores = lexer.tokenizar(fuente)
    assert tokens == []
    assert len(errores) == 1
    assert "caracter mal formado" in errores[0].mensaje


# ===========================================================================
# 5. Escenarios de ejemplo y CLI
# ===========================================================================

def test_escenario_4_operadores_literales(lexer):
    texto = (EJEMPLOS / "escenario4_operadores_literales.spl").read_text(encoding="utf-8")
    tokens, errores = lexer.tokenizar(texto)
    assert not errores
    tipos = set(_tipos(tokens))
    assert set(OPERADORES.values()) <= tipos
    assert {"ENTERO_DEC", "ENTERO_HEX", "FLOTANTE", "STRING", "CHAR_LITERAL"} <= tipos
    assert lexer.tablas.tabla_num.total == 11
    assert lexer.tablas.tabla_string.total == 2
    assert lexer.tablas.tabla_string.buscar('Ruta: "C:\\Enigma64\\salida.log"') == 2


def test_escenario_5_errores_literales(lexer):
    texto = (EJEMPLOS / "escenario5_errores_literales.spl").read_text(encoding="utf-8")
    tokens, errores = lexer.tokenizar(texto)
    assert len(errores) == 9
    assert [e.linea for e in errores] == [9, 10, 13, 14, 17, 20, 23, 23, 26]
    assert "fin_de_literales" in [t.value for t in tokens if t.type == "ID"]


def test_cli_escenario_operadores_literales():
    ruta = EJEMPLOS / "escenario4_operadores_literales.spl"
    res = subprocess.run(
        [sys.executable, "-m", "spl.compilador", str(ruta)],
        capture_output=True, text=True, cwd=str(RAIZ),
    )
    assert res.returncode == 0
    assert "AND_LOGICO" in res.stdout
    assert "REAL_CIENTIFICO" in res.stdout


def test_cli_escenario_errores_literales():
    ruta = EJEMPLOS / "escenario5_errores_literales.spl"
    res = subprocess.run(
        [sys.executable, "-m", "spl.compilador", str(ruta), "--sin-tablas"],
        capture_output=True, text=True, cwd=str(RAIZ),
    )
    assert res.returncode == 1
    assert res.stdout.count("ERROR LEXICO") == 9
