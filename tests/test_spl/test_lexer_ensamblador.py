"""
Suite de pruebas para el analizador lexico del Ensamblador SPL de Enigma-64.
Verifica categorias, insensibilidad a mayusculas, conflicto reservada/etiqueta,
signo de literales, conteo de lineas, recuperacion de errores y CLI.
"""

import sys
import subprocess
from pathlib import Path

import pytest

from spl.ensamblador import EnsambladorLexer, MNEMONICOS, REGISTROS


RAIZ = Path(__file__).resolve().parents[2]
PRUEBA_ASM = RAIZ / "spl" / "ensamblador" / "ejemplos" / "prueba.asm"


def tokenizar(codigo):
    toks, errores = EnsambladorLexer().tokenizar(codigo)
    return [(t.type, t.value) for t in toks], errores


def tipos(codigo):
    return [tipo for tipo, _ in tokenizar(codigo)[0]]


# 1. Vocabulario

class TestVocabulario:
    def test_isa_completo(self):
        from enigma64.cpu import _INSTRUCTIONS
        assert MNEMONICOS == {nombre for nombre, _, _ in _INSTRUCTIONS.values()}

    @pytest.mark.parametrize("mnemonico", sorted(MNEMONICOS))
    def test_cada_mnemonico(self, mnemonico):
        assert tokenizar(mnemonico)[0] == [("MNEMONICO", mnemonico)]

    @pytest.mark.parametrize("registro", sorted(REGISTROS))
    def test_cada_registro(self, registro):
        assert tokenizar(registro)[0] == [("REGISTRO", registro)]

    @pytest.mark.parametrize("directiva", [".data", ".text", ".org", ".word", ".byte"])
    def test_cada_directiva(self, directiva):
        assert tokenizar(directiva)[0] == [("DIRECTIVA", directiva)]

    def test_insensible_a_mayusculas(self):
        assert tipos("addi Sp, r0, 1\nJmP x\n.DATA") == [
            "MNEMONICO", "REGISTRO", "COMA", "REGISTRO", "COMA", "ENTERO_DEC",
            "MNEMONICO", "ETIQUETA_REF", "DIRECTIVA",
        ]


# 2. Etiquetas y palabras reservadas

class TestEtiquetas:
    def test_definicion_y_uso(self):
        assert tokenizar("loop: JMP loop")[0] == [
            ("ETIQUETA_DEF", "loop"), ("DOS_PUNTOS", ":"),
            ("MNEMONICO", "JMP"), ("ETIQUETA_REF", "loop"),
        ]

    def test_definicion_con_espacio_antes_de_dos_puntos(self):
        assert tipos("fin :") == ["ETIQUETA_DEF", "DOS_PUNTOS"]

    @pytest.mark.parametrize("palabra", ["ADDR", "HLTX", "R1X", "SPACE", "PCB", "LOADER", "R0_"])
    def test_prefijo_reservado_es_etiqueta(self, palabra):
        assert tokenizar(palabra)[0] == [("ETIQUETA_REF", palabra)]

    def test_reservada_como_etiqueta_es_error(self):
        toks, errores = tokenizar("LOAD: HLT")
        assert toks == [("DOS_PUNTOS", ":"), ("MNEMONICO", "HLT")]
        assert errores[0].mensaje == "palabra reservada usada como etiqueta"

    @pytest.mark.parametrize("registro", ["R8", "r9", "R10"])
    def test_registro_inexistente(self, registro):
        toks, errores = tokenizar(registro)
        assert toks == []
        assert errores[0].lexema == registro


# 3. Literales numericos

class TestLiterales:
    @pytest.mark.parametrize("lexema, tipo", [
        ("0", "ENTERO_DEC"), ("42", "ENTERO_DEC"), ("-7", "ENTERO_DEC"),
        ("0x1F", "ENTERO_HEX"), ("0XffFF", "ENTERO_HEX"), ("-0x10", "ENTERO_HEX"),
        ("0b1010", "ENTERO_BIN"), ("-0B1", "ENTERO_BIN"),
        ("3.14", "FLOTANTE"), ("-2.5e-3", "FLOTANTE"), ("6E2", "FLOTANTE"), ("1.0e+10", "FLOTANTE"),
    ])
    def test_literal_valido(self, lexema, tipo):
        assert tokenizar(lexema) == ([(tipo, lexema)], [])

    @pytest.mark.parametrize("lexema", ["0b102", "0x", "0xG1", "12abc", "3.", "1.2.3"])
    def test_literal_mal_formado(self, lexema):
        toks, errores = tokenizar(lexema)
        assert toks == []
        assert errores[0].mensaje == "literal numerico mal formado"

    def test_limites_de_64_bits(self):
        assert tokenizar("0xFFFFFFFFFFFFFFFF")[1] == []
        assert tokenizar("-9223372036854775808")[1] == []
        assert tokenizar("0x1FFFFFFFFFFFFFFFF")[1][0].mensaje == "literal fuera del rango de 64 bits"
        assert tokenizar("-9223372036854775809")[1][0].mensaje == "literal fuera del rango de 64 bits"

    def test_menos_tras_operando_es_resta(self):
        assert tokenizar("[BP-8]")[0] == [
            ("CORCHETE_IZQ", "["), ("REGISTRO", "BP"), ("MENOS", "-"),
            ("ENTERO_DEC", "8"), ("CORCHETE_DER", "]"),
        ]

    def test_menos_tras_coma_es_signo(self):
        assert tokenizar("SUBI R1, R1, -1")[0][-1] == ("ENTERO_DEC", "-1")

    def test_menos_con_espacio_es_operador(self):
        assert tipos("[BP - 8]") == ["CORCHETE_IZQ", "REGISTRO", "MENOS", "ENTERO_DEC", "CORCHETE_DER"]

    def test_signo_al_inicio_de_linea_nueva(self):
        assert tokenizar("PUSH R1\n-5")[0][-1] == ("ENTERO_DEC", "-5")


# 4. Separadores, comentarios, espacios y lineas

class TestSeparadoresYLineas:
    def test_separadores(self):
        assert tipos(", : [ ] ( ) # + -") == [
            "COMA", "DOS_PUNTOS", "CORCHETE_IZQ", "CORCHETE_DER",
            "PARENTESIS_IZQ", "PARENTESIS_DER", "INMEDIATO", "MAS", "MENOS",
        ]

    def test_comentarios_se_ignoran(self):
        lexer = EnsambladorLexer()
        toks, _ = lexer.tokenizar("; cabecera\nHLT ; fin, [x] @$\n;")
        assert [t.value for t in toks] == ["HLT"]
        assert lexer.comentarios == 3

    def test_conteo_de_lineas_y_columnas(self):
        toks, _ = EnsambladorLexer().tokenizar("\n\n  HLT\r\n\n\tRET")
        assert [(t.value, t.lineno, t.columna) for t in toks] == [("HLT", 3, 3), ("RET", 5, 2)]

    def test_lexer_reutilizable(self):
        lexer = EnsambladorLexer()
        lexer.tokenizar("@\n@")
        toks, errores = lexer.tokenizar("HLT")
        assert errores == [] and toks[0].lineno == 1 and lexer.comentarios == 0


# 5. Recuperacion de errores

class TestErrores:
    def test_continua_tras_error(self):
        toks, errores = tokenizar("MOV R1, @R2\nJMP $fin\n.float 1.5")
        assert [(e.linea, e.columna, e.lexema) for e in errores] == [
            (1, 9, "@"), (2, 5, "$"), (3, 1, ".float"),
        ]
        assert ("REGISTRO", "R2") in toks and ("ETIQUETA_REF", "fin") in toks
        assert toks[-1] == ("FLOTANTE", "1.5")

    def test_callback_al_error(self):
        vistos = []
        EnsambladorLexer(al_error=vistos.append).tokenizar("HLT ?")
        assert len(vistos) == 1 and vistos[0].lexema == "?"

    @pytest.mark.parametrize("archivo", sorted(
        list((RAIZ / "enigma64" / "asm").glob("*.s")) + list((RAIZ / "programas").glob("*.s"))
    ), ids=lambda p: p.name)
    def test_programas_oficiales_sin_errores(self, archivo):
        toks, errores = EnsambladorLexer().tokenizar(archivo.read_text(encoding="utf-8"))
        assert errores == [] and toks


# 6. CLI

class TestCLI:
    def ejecutar(self, *args, entrada=None):
        return subprocess.run(
            [sys.executable, "-m", "spl.ensamblador", *args],
            input=entrada, capture_output=True, text=True, encoding="utf-8", cwd=RAIZ,
        )

    def test_archivo_de_prueba(self):
        res = self.ejecutar(str(PRUEBA_ASM))
        esperado = (PRUEBA_ASM.parent / "prueba_salida_esperada.txt").read_text(encoding="utf-8")
        assert res.returncode == 1
        assert res.stdout == esperado

    def test_stdin_sin_errores(self):
        res = self.ejecutar(entrada="start: HLT\n")
        assert res.returncode == 0
        assert res.stdout.startswith("<1, ETIQUETA_DEF, start>\n<1, DOS_PUNTOS, :>\n<1, MNEMONICO, HLT>\n")
        assert "Errores lexicos              0" in res.stdout

    def test_archivo_inexistente(self):
        res = self.ejecutar("no_existe.asm")
        assert res.returncode == 2 and "no se pudo leer" in res.stderr
