"""
Pruebas de la correccion del ValueError con literales decimales largos.
Cubren el conversor (spl/ensamblador/literales.py) y sus dos usuarios: el
lexer del ensamblador y el traductor CacaoCore -> Enigma-64.
"""

import math
import struct

import pytest

from spl.ensamblador import EnsambladorLexer
from spl.ensamblador.literales import (
    LiteralInvalido,
    entero_decimal_64,
    literal_a_bits,
    literal_a_bytes,
    literal_a_double,
)
from spl.traductor.alu import parsear_operando
from spl.traductor.traductor import traducir_texto


MUCHAS_CIFRAS = "3.14159265358979323846264338327950288419716939937510"
MILES_DE_CIFRAS = "0." + "3" * 5000          # mas que el limite de 4300 de int()
ENTERO_ENORME = "9" * 5000


def nombre_corto(valor):
    """Id legible en la salida de pytest: los literales de miles de cifras se resumen."""
    texto = str(valor)
    return texto if len(texto) <= 32 else f"{texto[:12]}...({len(texto)}_caracteres)"


def bits(valor):
    return struct.unpack(">Q", struct.pack(">d", valor))[0]


# 1. Conversor

class TestConversor:
    @pytest.mark.parametrize("texto, esperado", [
        (MUCHAS_CIFRAS, math.pi),
        ("3.14159265358979323846", math.pi),
        (MILES_DE_CIFRAS, 1 / 3),
        ("1" + "0" * 300 + ".0", 1e300),
        ("1e-07", 1e-07),
        ("6.02E+23", 6.02e23),
        ("2.5e-324", 5e-324),                  # redondea al menor subnormal
        ("4.9406564584124654e-324", 5e-324),
        ("2.2250738585072014e-308", 2.2250738585072014e-308),  # menor normal
        ("1.7976931348623157e308", 1.7976931348623157e308),    # mayor double
        ("-2.5", -2.5),
        ("-0.1", -0.1),
        ("+7.25", 7.25),
        (".5", 0.5),
        ("5.", 5.0),
        ("0.0", 0.0),
    ], ids=nombre_corto)
    def test_valor_redondeado_a_double(self, texto, esperado):
        assert literal_a_double(texto) == esperado

    def test_menos_cero_conserva_el_signo(self):
        assert literal_a_bits("-0.0") == 0x8000000000000000
        assert literal_a_bits("0.0") == 0

    def test_subdesbordamiento_da_cero(self):
        assert literal_a_double("1e-400") == 0.0
        assert literal_a_bits("-1e-400") == 0x8000000000000000

    def test_redondeo_al_par_en_el_empate(self):
        # 2**53 + 1 esta justo entre dos doubles: gana el de mantisa par (2**53)
        assert literal_a_double("9007199254740993.0") == 2.0 ** 53
        assert literal_a_double("9007199254740993.0000000000000000000001") == 2.0 ** 53 + 2

    @pytest.mark.parametrize("texto", ["1e400", "-1e309", "1" * 400 + ".0"], ids=nombre_corto)
    def test_desborde_es_error_y_no_infinito(self, texto):
        with pytest.raises(LiteralInvalido, match="rango de double"):
            literal_a_double(texto)

    @pytest.mark.parametrize("texto", ["", ".", "1.2.3", "1e", "e5", "--1.0", "nan", "inf", "1_000.5", "0x1p3"], ids=nombre_corto)
    def test_mal_formado(self, texto):
        with pytest.raises(LiteralInvalido):
            literal_a_double(texto)

    def test_literal_invalido_sigue_siendo_value_error(self):
        assert issubclass(LiteralInvalido, ValueError)

    def test_bytes_big_endian_por_defecto(self):
        assert literal_a_bytes("-2.5") == bytes.fromhex("C004000000000000")
        assert literal_a_bytes("-2.5") == struct.pack(">d", -2.5)

    def test_bytes_little_endian_a_pedido(self):
        assert literal_a_bytes("-2.5", orden="little") == struct.pack("<d", -2.5)
        with pytest.raises(ValueError):
            literal_a_bytes("1.0", orden="medio")

    def test_bits_coinciden_con_struct(self):
        for texto in (MUCHAS_CIFRAS, "1e-07", "-123.456e-7", "0.0"):
            assert literal_a_bits(texto) == bits(float(texto))

    @pytest.mark.parametrize("texto, esperado", [
        ("0", 0), ("-1", -1), ("+42", 42),
        ("18446744073709551615", (1 << 64) - 1),
        ("-9223372036854775808", -(1 << 63)),
        ("000000000000000000000000000007", 7),   # ceros a la izquierda no cuentan
    ], ids=nombre_corto)
    def test_entero_64(self, texto, esperado):
        assert entero_decimal_64(texto) == esperado

    @pytest.mark.parametrize("texto", ["18446744073709551616", "-9223372036854775809", ENTERO_ENORME], ids=nombre_corto)
    def test_entero_fuera_de_rango_sin_value_error_de_int(self, texto):
        with pytest.raises(LiteralInvalido, match="rango de 64 bits"):
            entero_decimal_64(texto)

    def test_mensaje_no_repite_miles_de_cifras(self):
        with pytest.raises(LiteralInvalido) as info:
            entero_decimal_64(ENTERO_ENORME)
        assert len(str(info.value)) < 120


# 2. Lexer del ensamblador

class TestLexerEnsamblador:
    def tokenizar(self, codigo):
        return EnsambladorLexer().tokenizar(codigo)

    @pytest.mark.parametrize("texto", [MUCHAS_CIFRAS, MILES_DE_CIFRAS, "1e-07", "-2.5", "0.0", "2.5E+10"], ids=nombre_corto)
    def test_flotante_lleva_sus_bits_ieee(self, texto):
        toks, errores = self.tokenizar(f".word {texto}")
        assert errores == []
        assert toks[1].type == "FLOTANTE"
        assert toks[1].value == texto
        assert toks[1].bits == literal_a_bits(texto)

    def test_flotante_fuera_de_rango_es_error_lexico(self):
        toks, errores = self.tokenizar(".word 1e400\nHLT")
        assert [t.type for t in toks] == ["DIRECTIVA", "MNEMONICO"]
        assert errores[0].mensaje == "literal fuera del rango de double"

    def test_entero_de_miles_de_cifras_es_error_lexico(self):
        toks, errores = self.tokenizar(f"ADDI R1, R0, {ENTERO_ENORME}\nHLT")
        assert errores[0].mensaje == "literal fuera del rango de 64 bits"
        assert errores[0].linea == 1
        assert toks[-1].type == "MNEMONICO"           # el analisis continua

    def test_resta_con_flotante_no_cambia(self):
        toks, errores = self.tokenizar("[BP-1.5]")
        assert [t.type for t in toks] == ["CORCHETE_IZQ", "REGISTRO", "MENOS", "FLOTANTE", "CORCHETE_DER"]
        assert toks[3].bits == literal_a_bits("1.5")


# 3. Traductor CacaoCore -> Enigma-64

class TestTraductor:
    @pytest.mark.parametrize("texto, esperado", [
        (MUCHAS_CIFRAS, math.pi), ("1e-07", 1e-07), ("-2.5E3", -2500.0), ("0.0", 0.0),
    ], ids=nombre_corto)
    def test_operando_flotante(self, texto, esperado):
        op = parsear_operando(texto)
        assert (op.tipo, op.valor) == ("float", esperado)

    def test_operando_entero_enorme_es_literal_invalido(self):
        with pytest.raises(LiteralInvalido):
            parsear_operando(ENTERO_ENORME)

    @pytest.mark.parametrize("linea", [f"mov R1, {ENTERO_ENORME}", f"add R1, {ENTERO_ENORME}"], ids=nombre_corto)
    def test_traduccion_reporta_error_en_vez_de_lanzar(self, linea):
        resultado = traducir_texto(f"{linea}\nhalt\n")
        assert any("rango de 64 bits" in mensaje for _, mensaje in resultado.errores)

    def test_inmediato_valido_sigue_funcionando(self):
        resultado = traducir_texto("mov R1, 1234567\nhalt\n")
        assert not any("rango" in mensaje for _, mensaje in resultado.errores)
