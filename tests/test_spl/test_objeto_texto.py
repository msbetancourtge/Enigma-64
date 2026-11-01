"""
Suite de Pruebas del modulo objeto en texto (.tobj) - Enigma-64.

Verifica:
  1. Vocabulario del analizador lexico (lex.py): encabezados, palabras
     reservadas, permisos, nombres, cadenas, enteros, bytes y separadores.
  2. Estado exclusivo 'contenido' entre '{' y '}' y su regla de fin de archivo.
  3. Errores lexicos con linea y columna, y recuperacion tras cada uno.
  4. Lectura: los .tobj de ejemplo equivalen a los modulos armados en memoria.
  5. Errores de estructura y de nombres no declarados, todos en una ejecucion.
  6. Escritura: texto -> modulo -> binario -> modulo -> texto sin perdidas.
  7. Integracion con el enlazador, el cargador, la linea de comandos y el SPL.
  8. Cifras del escenario complementario 6 del informe del Taller 01.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

import contextlib
import io
import os
import struct
import subprocess
import sys
import tempfile
import unittest

from enigma64 import CPU, BancoRegistros, CargadorEnigma, RAMMemory
from spl.enlazador import (
    REUB_ABS32,
    REUB_ABS64,
    REUB_HI16,
    REUB_LO16,
    REUB_REL16,
    SECCION_ABSOLUTA,
    SIMBOLO_DATO,
    SIMBOLO_FUNCION,
    EnlazadorEnigma,
    MarcaReubicacion,
    ModuloObjeto,
    ObjetoInvalido,
    SeccionObjeto,
    SimboloNoDefinido,
    SimboloObjeto,
    analizar_objeto,
)
from spl.enlazador.__main__ import main as cli_enlazador
from spl.enlazador.ejemplos import (
    CODIGO_LIBMAT,
    CODIGO_PRINCIPAL,
    DATOS_PRINCIPAL,
    DIR_OBJETOS,
    RUTA_LIBMAT,
    RUTA_PRINCIPAL,
    VALOR_A,
    VALOR_B,
    construir_modulo_libmat,
    construir_modulo_principal,
)
from spl.enlazador.lexer import (
    ENCABEZADOS,
    PALABRAS_RESERVADAS,
    ErrorLexico,
    ObjetoLexer,
)
from spl.enlazador.objeto import (
    NOMBRE_LIGADURA,
    NOMBRE_REUBICACION,
    NOMBRE_TIPO_SECCION,
    NOMBRE_TIPO_SIMBOLO,
)
from spl.enlazador.texto import (
    ErrorSintactico,
    analizar_texto,
    escribir_objeto_texto,
    leer_objeto_texto,
)
from enigma64.ensamblador import ensamblar
from enigma64.fpu import CODIGO_FPU_ASM

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tipos(texto: str):
    tokens, _ = ObjetoLexer().tokenizar(texto)
    return [t.type for t in tokens]


def _principal_en_memoria() -> ModuloObjeto:
    """El modulo principal tal como lo armaba ejemplos.py antes del formato de texto."""
    texto, datos, bss = 0, 1, 2
    simbolos = [
        SimboloObjeto.exportado("main", texto, 0x00, SIMBOLO_FUNCION),
        SimboloObjeto.local("trampa", texto, 0x30, SIMBOLO_FUNCION),
        SimboloObjeto.local("fin", texto, 0x38),
        SimboloObjeto.local("valores", datos, 0x00, SIMBOLO_DATO),
        SimboloObjeto.exportado("resultado", datos, 0x10, SIMBOLO_DATO),
        SimboloObjeto.local("puntero", datos, 0x18, SIMBOLO_DATO),
        SimboloObjeto.exportado("copia", bss, 0x00, SIMBOLO_DATO),
        SimboloObjeto.importado("sumar", SIMBOLO_FUNCION),
        SimboloObjeto.importado("error", SIMBOLO_FUNCION),
    ]
    indice = {simbolo.nombre: i for i, simbolo in enumerate(simbolos)}
    return ModuloObjeto(
        nombre="principal",
        secciones=[
            SeccionObjeto.texto(CODIGO_PRINCIPAL),
            SeccionObjeto.datos(DATOS_PRINCIPAL),
            SeccionObjeto.reserva(16),
        ],
        simbolos=simbolos,
        reubicaciones=[
            MarcaReubicacion(texto, 0x02, REUB_HI16, indice["valores"]),
            MarcaReubicacion(texto, 0x0A, REUB_LO16, indice["valores"]),
            MarcaReubicacion(texto, 0x15, REUB_ABS32, indice["sumar"]),
            MarcaReubicacion(texto, 0x1D, REUB_REL16, indice["error"]),
            MarcaReubicacion(texto, 0x2C, REUB_ABS32, indice["fin"]),
            MarcaReubicacion(datos, 0x18, REUB_ABS64, indice["copia"]),
        ],
        entrada=(texto, 0x00),
    )


def _libmat_en_memoria() -> ModuloObjeto:
    return ModuloObjeto(
        nombre="libmat",
        secciones=[SeccionObjeto.texto(CODIGO_LIBMAT)],
        simbolos=[
            SimboloObjeto.exportado("sumar", 0, 0x00, SIMBOLO_FUNCION),
            SimboloObjeto.exportado("error", 0, 0x04, SIMBOLO_FUNCION),
        ],
    )


# Programa autocontenido: duplica el dato de .data y lo guarda en 'doble'
FUENTE_DUPLICADOR = """
inicio: ADDI  R1, R0, 0
        SHL   R1, R1, 16
        ADDI  R1, R1, 0
        LOAD  R2, [R1 + 0]
        ADD   R2, R2, R2
        STORE R2, [R1 + 8]
        HLT
"""

TOBJ_DUPLICADOR = """\
; duplicador.tobj: doble = 2 * dato
[MODULO] duplicador
[ENTRADA] .text
[SECCION] .text BITS R-X ALIN 1 {
    14 10 00 00     ; ADDI  R1, R0, %hi(dato)
    24 11 00 10     ; SHL   R1, R1, 16
    14 11 00 00     ; ADDI  R1, R1, %lo(dato)
    30 21 00 00     ; LOAD  R2, [R1 + 0]
    10 22 20        ; ADD   R2, R2, R2
    31 21 00 08     ; STORE R2, [R1 + 8]
    00              ; HLT
}
[SECCION] .data BITS RW- ALIN 8 {
    00 00 00 00 00 00 00 15     ; dato = 21
    00 00 00 00 00 00 00 00     ; doble
}
[SIMBOLOS]
inicio  GLOBAL  FUNCION  .text  0x0000
dato    LOCAL   DATO     .data  0x0000
doble   GLOBAL  DATO     .data  0x0008
[REUBICACIONES]
.text  0x0002  HI16  dato
.text  0x000A  LO16  dato
"""


def _modulo_variado() -> ModuloObjeto:
    """Ejercita lo que los ejemplos no usan: *ABS*, nombres con comillas, sumandos con signo."""
    return ModuloObjeto(
        nombre="mod variado",
        secciones=[
            SeccionObjeto.texto(bytes(range(40)), nombre="DATO"),
            SeccionObjeto("vacia", b"", 0x4 | 0x1, 1),
            SeccionObjeto.datos(b"\x00" * 16, nombre=".rodata.tabla", alineacion=16),
            SeccionObjeto.reserva(4096, alineacion=4096),
        ],
        simbolos=[
            SimboloObjeto.exportado("RWX", 0, 0x10, SIMBOLO_FUNCION),
            SimboloObjeto.exportado("LIMITE", SECCION_ABSOLUTA, 0xFFFFFFFF),
            SimboloObjeto.local('con "comillas" y \\', 2, 8, SIMBOLO_DATO),
            SimboloObjeto.local("1empieza_con_digito", 0, 0),
            SimboloObjeto.importado("tab\tnueva\nlinea"),
        ],
        reubicaciones=[
            MarcaReubicacion(0, 0, REUB_ABS32, 4, -8),
            MarcaReubicacion(0, 4, REUB_REL16, 0, 0x7FFFFFFF),
            MarcaReubicacion(2, 0, REUB_ABS64, 2, -(1 << 31)),
        ],
        entrada=(0, 0x27),
    )


# ---------------------------------------------------------------------------
# 1. Vocabulario del analizador lexico
# ---------------------------------------------------------------------------


class TestVocabularioLexer(unittest.TestCase):
    """Cada categoria lexica se reconoce con su lexema, linea y columna."""

    def test_palabras_reservadas_salen_de_las_tablas_del_formato(self) -> None:
        esperadas = {
            *NOMBRE_TIPO_SECCION.values(), *NOMBRE_LIGADURA.values(), "IMPORTADO",
            *NOMBRE_TIPO_SIMBOLO.values(), *NOMBRE_REUBICACION.values(), "ALIN", "TAM",
        }
        self.assertEqual(set(PALABRAS_RESERVADAS), esperadas)
        self.assertEqual(ENCABEZADOS, {"MODULO", "ENTRADA", "SECCION", "SIMBOLOS", "REUBICACIONES"})

    def test_tupla_de_tokens_para_yacc(self) -> None:
        self.assertEqual(len(ObjetoLexer.tokens), 17)
        self.assertEqual(len(set(ObjetoLexer.tokens)), 17)
        self.assertTrue(set(PALABRAS_RESERVADAS.values()) <= set(ObjetoLexer.tokens))

    def test_encabezados(self) -> None:
        for nombre in sorted(ENCABEZADOS):
            with self.subTest(encabezado=nombre):
                tokens, errores = ObjetoLexer().tokenizar(f"[{nombre}]")
                self.assertEqual([(t.type, t.value) for t in tokens], [("ENCABEZADO", f"[{nombre}]")])
                self.assertEqual(errores, [])

    def test_palabras_reservadas_y_nombres(self) -> None:
        casos = {
            "BITS": "TIPO_SECCION", "VACIA": "TIPO_SECCION",
            "LOCAL": "LIGADURA", "GLOBAL": "LIGADURA", "IMPORTADO": "LIGADURA",
            "SIN_TIPO": "TIPO_SIMBOLO", "FUNCION": "TIPO_SIMBOLO", "DATO": "TIPO_SIMBOLO",
            "ABS64": "TIPO_REUBICACION", "ABS32": "TIPO_REUBICACION",
            "REL16": "TIPO_REUBICACION", "HI16": "TIPO_REUBICACION", "LO16": "TIPO_REUBICACION",
            "ALIN": "ATRIBUTO", "TAM": "ATRIBUTO",
            # La palabra completa decide: un prefijo o el uso de minusculas da un nombre
            "DATOS": "NOMBRE", "dato": "NOMBRE", "ALINEAR": "NOMBRE",
            ".text": "NOMBRE", "main": "NOMBRE", "_x1": "NOMBRE", "lib.sumar": "NOMBRE",
            "*ABS*": "SECCION_ABSOLUTA",
        }
        for lexema, tipo in casos.items():
            with self.subTest(lexema=lexema):
                self.assertEqual(_tipos(lexema), [tipo])

    def test_permisos(self) -> None:
        for lexema in ("R-X", "RW-", "RWX", "---", "R--", "-W-", "--X"):
            with self.subTest(lexema=lexema):
                self.assertEqual(_tipos(lexema), ["PERMISOS"])
        self.assertEqual(_tipos("RWXY"), ["NOMBRE"])
        self.assertEqual(_tipos("-8"), ["MENOS", "ENTERO_DEC"])
        self.assertEqual(_tipos("+0x10"), ["MAS", "ENTERO_HEX"])

    def test_nombres_conservan_su_texto(self) -> None:
        tokens, _ = ObjetoLexer().tokenizar('.text "DATO" "a\\"b\\\\c\\nd\\te" ""')
        self.assertEqual([t.type for t in tokens], ["NOMBRE"] * 4)
        self.assertEqual([t.nombre for t in tokens], [".text", "DATO", 'a"b\\c\nd\te', ""])

    def test_enteros(self) -> None:
        tokens, errores = ObjetoLexer().tokenizar("0x1F 0X1f 42 0 0xFFFFFFFF 4294967295")
        self.assertEqual(errores, [])
        self.assertEqual(
            [(t.type, t.entero) for t in tokens],
            [("ENTERO_HEX", 31), ("ENTERO_HEX", 31), ("ENTERO_DEC", 42), ("ENTERO_DEC", 0),
             ("ENTERO_HEX", 0xFFFFFFFF), ("ENTERO_DEC", 0xFFFFFFFF)],
        )

    def test_comentarios_saltos_de_linea_y_posiciones(self) -> None:
        lexer = ObjetoLexer()
        tokens, errores = lexer.tokenizar("; cabecera\r\n\r\n[MODULO]  m ; nombre\n\n  [SIMBOLOS]")
        self.assertEqual(errores, [])
        self.assertEqual(lexer.comentarios, 2)
        self.assertEqual(
            [(t.type, t.lineno, t.columna) for t in tokens],
            # El comentario llega hasta el '\r'; el '\n' queda en la columna 12
            [("FIN_LINEA", 1, 12), ("FIN_LINEA", 2, 2), ("ENCABEZADO", 3, 1),
             ("NOMBRE", 3, 11), ("FIN_LINEA", 3, 21), ("ENCABEZADO", 5, 3)],
        )

    def test_fila_de_reubicacion(self) -> None:
        self.assertEqual(
            _tipos(".text 0x0002 HI16 valores -8 ; campo\n"),
            ["NOMBRE", "ENTERO_HEX", "TIPO_REUBICACION", "NOMBRE", "MENOS", "ENTERO_DEC",
             "FIN_LINEA"],
        )


# ---------------------------------------------------------------------------
# 2. Estado exclusivo 'contenido'
# ---------------------------------------------------------------------------


class TestEstadoContenido(unittest.TestCase):
    """Entre '{' y '}' solo hay bytes; fuera, los mismos digitos son enteros."""

    def test_digitos_son_bytes_dentro_y_enteros_fuera(self) -> None:
        tokens, errores = ObjetoLexer().tokenizar("16 { 16 ee 0A } 16")
        self.assertEqual(errores, [])
        self.assertEqual(
            [(t.type, getattr(t, "entero", None)) for t in tokens],
            [("ENTERO_DEC", 16), ("LLAVE_IZQ", None), ("BYTE", 0x16), ("BYTE", 0xEE),
             ("BYTE", 0x0A), ("LLAVE_DER", None), ("ENTERO_DEC", 16)],
        )

    def test_saltos_y_comentarios_dentro_no_son_tokens(self) -> None:
        lexer = ObjetoLexer()
        tokens, errores = lexer.tokenizar("{\n  01 02   ; primero\n\n  03 ; tercero\n}\n")
        self.assertEqual(errores, [])
        self.assertEqual([t.type for t in tokens],
                         ["LLAVE_IZQ", "BYTE", "BYTE", "BYTE", "LLAVE_DER", "FIN_LINEA"])
        self.assertEqual([t.lineno for t in tokens], [1, 2, 2, 4, 5, 5])
        self.assertEqual(lexer.comentarios, 2)

    def test_las_palabras_del_formato_no_valen_dentro(self) -> None:
        tokens, errores = ObjetoLexer().tokenizar("{ 01 ALIN 0x10 02 }")
        self.assertEqual([t.type for t in tokens], ["LLAVE_IZQ", "BYTE", "BYTE", "LLAVE_DER"])
        self.assertEqual([e.lexema for e in errores], ["ALIN", "0x10"])

    def test_llave_sin_cerrar_se_informa_en_su_posicion(self) -> None:
        tokens, errores = ObjetoLexer().tokenizar("[SECCION] .t BITS R-X ALIN 1 {\n 01 02\n")
        self.assertEqual(len(errores), 1)
        self.assertEqual((errores[0].linea, errores[0].columna, errores[0].lexema), (1, 30, "{"))
        self.assertIn("sin cerrar", errores[0].mensaje)
        # La regla de fin de archivo cierra el bloque con una '}' vacia
        self.assertEqual((tokens[-1].type, tokens[-1].value), ("LLAVE_DER", ""))

    def test_el_lexer_se_reinicia_en_cada_entrada(self) -> None:
        lexer = ObjetoLexer()
        lexer.tokenizar("{ 01")
        tokens, errores = lexer.tokenizar("16")
        self.assertEqual(([t.type for t in tokens], errores), (["ENTERO_DEC"], []))


# ---------------------------------------------------------------------------
# 3. Errores lexicos
# ---------------------------------------------------------------------------


class TestErroresLexicos(unittest.TestCase):
    """Cada error lleva linea, columna, lexema y mensaje; el analisis continua."""

    def test_errores_detectados(self) -> None:
        casos = {
            "@": ("caracter no valido", "@"),
            "0x1G": ("literal numerico mal formado", "0x1G"),
            "12ab": ("literal numerico mal formado", "12ab"),
            "0x10.5": ("literal numerico mal formado", "0x10.5"),
            "0x100000000": ("excede los 32 bits", "0x100000000"),
            "4294967296": ("excede los 32 bits", "4294967296"),
            "[RARO]": ("encabezado desconocido", "[RARO]"),
            "[seccion]": ("encabezado desconocido", "[seccion]"),
            '"abc\\q"': ("secuencia de escape no valida '\\q'", '"abc\\q"'),
            '"abierta': ("cadena sin cerrar", '"abierta'),
            "{ 1 }": ("byte mal formado", "1"),
            "{ ABC }": ("byte mal formado", "ABC"),
            "{ 0x14 }": ("byte mal formado", "0x14"),
            "{ @ }": ("caracter no valido en el contenido", "@"),
        }
        for texto, (mensaje, lexema) in casos.items():
            with self.subTest(texto=texto):
                _, errores = ObjetoLexer().tokenizar(texto)
                self.assertEqual(len(errores), 1)
                self.assertIn(mensaje, errores[0].mensaje)
                self.assertEqual(errores[0].lexema, lexema)
                self.assertIsInstance(errores[0], ErrorLexico)

    def test_recuperacion_tras_cada_error(self) -> None:
        texto = "main @ GLOBAL 0x1G FUNCION\n.text # 0x10\n"
        avisados = []
        tokens, errores = ObjetoLexer(al_error=avisados.append).tokenizar(texto)
        self.assertEqual(
            [t.type for t in tokens],
            ["NOMBRE", "LIGADURA", "TIPO_SIMBOLO", "FIN_LINEA", "NOMBRE", "ENTERO_HEX",
             "FIN_LINEA"],
        )
        self.assertEqual([(e.linea, e.columna, e.lexema) for e in errores],
                         [(1, 6, "@"), (1, 15, "0x1G"), (2, 7, "#")])
        self.assertEqual(avisados, errores)
        self.assertEqual(str(errores[0]),
                         "ERROR LEXICO (linea 1, columna 6): caracter no valido: '@'")


# ---------------------------------------------------------------------------
# 4. Lectura del texto
# ---------------------------------------------------------------------------


class TestLecturaDelTexto(unittest.TestCase):
    """El texto produce exactamente el ModuloObjeto que describe."""

    def test_ejemplos_equivalen_a_los_modulos_en_memoria(self) -> None:
        self.assertEqual(construir_modulo_principal(), _principal_en_memoria())
        self.assertEqual(construir_modulo_libmat(), _libmat_en_memoria())
        self.assertEqual(construir_modulo_principal().serializar(),
                         _principal_en_memoria().serializar())
        self.assertEqual(construir_modulo_libmat().serializar(), _libmat_en_memoria().serializar())

    def test_bytes_de_los_ejemplos(self) -> None:
        principal = construir_modulo_principal()
        self.assertEqual(principal.seccion(".text").contenido, CODIGO_PRINCIPAL)
        self.assertEqual(principal.seccion(".data").contenido, DATOS_PRINCIPAL)
        self.assertEqual(struct.unpack(">QQ", DATOS_PRINCIPAL[:16]), (VALOR_A, VALOR_B))
        self.assertEqual(construir_modulo_libmat().seccion(".text").contenido, CODIGO_LIBMAT)

    def test_el_codigo_del_duplicador_coincide_con_el_ensamblador_oficial(self) -> None:
        modulo = leer_objeto_texto(TOBJ_DUPLICADOR)
        self.assertEqual(modulo.seccion(".text").contenido,
                         ensamblar(FUENTE_DUPLICADOR, direccion_base=0))
        self.assertEqual(modulo.entrada, (0, 0))
        self.assertEqual([m.sumando for m in modulo.reubicaciones], [0, 0])

    def test_el_orden_de_los_bloques_es_libre(self) -> None:
        # Las tablas pueden ir antes de las secciones que nombran; solo el orden
        # de las secciones entre si fija sus indices
        cabecera, modulo, entrada, texto, datos, simbolos, marcas = TOBJ_DUPLICADOR.split("\n[")
        reordenado = "\n[".join(
            [cabecera, marcas.rstrip("\n"), simbolos, texto, datos, entrada, modulo]
        )
        self.assertEqual(leer_objeto_texto(reordenado), leer_objeto_texto(TOBJ_DUPLICADOR))

    def test_campos_opcionales(self) -> None:
        modulo = leer_objeto_texto(
            "[SECCION] .t BITS R-X ALIN 1 { }\n"
            "[SECCION] .u BITS R-X ALIN 1 { 00 00 00 00 00 00 00 00 00 00 }\n"
            "[ENTRADA] .u + 4\n"
            "[SIMBOLOS]\n"
            "k LOCAL SIN_TIPO *ABS* 0x10\n"
            "x IMPORTADO DATO\n"
            "[REUBICACIONES]\n"
            ".u 0 ABS32 x - 8\n"
            ".u 4 ABS32 x 3\n"
        )
        self.assertEqual(modulo.nombre, "")
        self.assertEqual(modulo.secciones[0].contenido, b"")
        self.assertEqual(modulo.entrada, (1, 4))
        self.assertEqual(modulo.simbolos[0], SimboloObjeto.local("k", SECCION_ABSOLUTA, 0x10))
        self.assertTrue(modulo.simbolos[1].es_importacion)
        self.assertEqual([m.sumando for m in modulo.reubicaciones], [-8, 3])

    def test_desde_archivo_usa_el_nombre_del_archivo_si_falta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "anonimo.tobj")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(TOBJ_DUPLICADOR.replace("[MODULO] duplicador\n", ""))
            self.assertEqual(analizar_objeto(ruta).nombre, "anonimo")


# ---------------------------------------------------------------------------
# 5. Errores de estructura
# ---------------------------------------------------------------------------


class TestErroresDeEstructura(unittest.TestCase):
    """Cada fila mal formada se informa con su posicion y no detiene la lectura."""

    SECCION = "[SECCION] .t BITS R-X ALIN 1 { 00 00 00 00 }\n"

    def _errores(self, texto: str):
        modulo, errores = analizar_texto(texto)
        self.assertIsNone(modulo)
        return errores

    def test_filas_mal_formadas(self) -> None:
        casos = {
            "main GLOBAL FUNCION .t 0x0\n": "fila fuera de una tabla",
            "[MODULO] a\n[MODULO] b\n": "[MODULO] repetido",
            "[ENTRADA] .t\n[ENTRADA] .t\n": "[ENTRADA] repetida",
            "[MODULO]\n": "falta el nombre del modulo",
            "[MODULO] DATO\n": "se esperaba el nombre del modulo",
            "[MODULO] a b\n": "sobra texto al final de la linea",
            "[ENTRADA] .t + \n": "falta el offset del punto de entrada",
            "[SECCION] .t bits R-X ALIN 1 { }\n": "se esperaba el tipo de seccion",
            "[SECCION] .t BITS ALIN 1 { }\n": "se esperaba el campo de permisos",
            "[SECCION] .t BITS R-X 1 { }\n": "se esperaba ALIN",
            "[SECCION] .t BITS R-X ALIN 1\n": "falta '{' con el contenido",
            "[SECCION] .t BITS R-X ALIN 1 TAM 4 { }\n": "se esperaba '{' con el contenido",
            "[SECCION] .b VACIA RW- ALIN 8\n": "falta TAM",
            "[SECCION] .b VACIA RW- ALIN 8 TAM 4 { 00 }\n": "sobra texto",
            "[SIMBOLOS] x\n": "sobra texto",
            "[SIMBOLOS]\nmain GLOBAL\n": "falta el tipo",
            "[SIMBOLOS]\nmain FUNCION GLOBAL .t 0\n": "se esperaba la ligadura",
            "[SIMBOLOS]\nmain GLOBAL FUNCION .t\n": "falta el valor del simbolo",
            "[SIMBOLOS]\nx IMPORTADO FUNCION .t 0\n": "sobra texto",
            "[REUBICACIONES]\n.t 0 ABS32\n": "falta el simbolo de la marca",
            "[REUBICACIONES]\n.t 0 ABS16 x\n": "se esperaba el tipo de marca",
            "[REUBICACIONES]\n.t 0 ABS32 x +\n": "falta el sumando",
        }
        for texto, mensaje in casos.items():
            with self.subTest(texto=texto):
                errores = self._errores(self.SECCION + texto)
                self.assertEqual(len(errores), 1, errores)
                self.assertIsInstance(errores[0], ErrorSintactico)
                self.assertIn(mensaje, errores[0].mensaje)
                self.assertGreaterEqual(errores[0].linea, 2)

    def test_todos_los_errores_en_una_ejecucion(self) -> None:
        texto = (
            "[MODULO]\n"                       # 1
            "[SECCION] .t BITS R-X ALIN 1 { 00 }\n"
            "[SIMBOLOS]\n"
            "a GLOBAL\n"                       # 4
            "b LOCAL FUNCION .t 0\n"
            "c @ LOCAL FUNCION .t 0\n"         # 6: error lexico, sin eco sintactico
            "[REUBICACIONES]\n"
            ".t 0 HI16\n"                      # 8
        )
        with self.assertRaises(ObjetoInvalido) as ctx:
            leer_objeto_texto(texto)
        errores = ctx.exception.errores
        self.assertEqual([(type(e), e.linea) for e in errores],
                         [(ErrorSintactico, 1), (ErrorSintactico, 4), (ErrorLexico, 6),
                          (ErrorSintactico, 8)])
        self.assertIn("4 error(es)", str(ctx.exception))
        self.assertIn("ERROR SINTACTICO (linea 4, columna 9): falta el tipo", str(ctx.exception))

    def test_nombres_no_declarados(self) -> None:
        errores = self._errores(
            self.SECCION
            + "[ENTRADA] .x\n"
            "[SIMBOLOS]\n"
            "a LOCAL FUNCION .y 0\n"
            "[REUBICACIONES]\n"
            ".z 0 ABS32 a\n"
            ".t 0 ABS32 nadie\n"
        )
        self.assertEqual(
            [(e.linea, e.lexema, e.mensaje) for e in errores],
            [(2, ".x", "seccion no declarada con [SECCION]"),
             (4, ".y", "seccion no declarada con [SECCION]"),
             (6, ".z", "seccion no declarada con [SECCION]"),
             (7, "nadie", "simbolo no declarado en [SIMBOLOS]")],
        )

    def test_la_coherencia_se_valida_como_en_el_binario(self) -> None:
        casos = {
            "offset fuera de la seccion": "[SIMBOLOS]\na LOCAL FUNCION .t 0x99\n",
            "simbolo duplicado": "[SIMBOLOS]\na LOCAL FUNCION .t 0\na LOCAL DATO .t 1\n",
            "campo fuera de la seccion": "[SIMBOLOS]\na LOCAL FUNCION .t 0\n"
                                         "[REUBICACIONES]\n.t 2 ABS32 a\n",
            "sumando de 33 bits": "[SIMBOLOS]\na LOCAL FUNCION .t 0\n"
                                  "[REUBICACIONES]\n.t 0 ABS32 a + 0x80000000\n",
            "entrada fuera": "[ENTRADA] .t + 4\n",
        }
        for descripcion, texto in casos.items():
            with self.subTest(caso=descripcion):
                self.assertEqual(analizar_texto(self.SECCION + texto)[1], [])
                with self.assertRaises(ObjetoInvalido):
                    leer_objeto_texto(self.SECCION + texto)
        with self.assertRaises(ObjetoInvalido):
            leer_objeto_texto("[SECCION] .t BITS R-X ALIN 3 { 00 }\n")


# ---------------------------------------------------------------------------
# 6. Escritura y conversion entre representaciones
# ---------------------------------------------------------------------------


class TestEscritura(unittest.TestCase):
    """Texto y binario se convierten uno en otro sin perder informacion."""

    def _modulos(self):
        fpu = ensamblar(CODIGO_FPU_ASM, direccion_base=0)
        return [
            construir_modulo_principal(),
            construir_modulo_libmat(),
            leer_objeto_texto(TOBJ_DUPLICADOR),
            _modulo_variado(),
            ModuloObjeto("fpu", [SeccionObjeto.texto(fpu)],
                         [SimboloObjeto.exportado("inicio", 0, 0, SIMBOLO_FUNCION)]),
        ]

    def test_ida_y_vuelta(self) -> None:
        for modulo in self._modulos():
            with self.subTest(modulo=modulo.nombre):
                texto = escribir_objeto_texto(modulo)
                leido = leer_objeto_texto(texto)
                self.assertEqual(leido, modulo)
                desde_binario = ModuloObjeto.deserializar(modulo.serializar())
                self.assertEqual(desde_binario.a_texto(), texto)
                self.assertEqual(leido.serializar(), modulo.serializar())

    def test_nombres_que_necesitan_comillas(self) -> None:
        texto = _modulo_variado().a_texto()
        for fragmento in ('[MODULO] "mod variado"', '[SECCION] "DATO" BITS', '"RWX"',
                          '"con \\"comillas\\" y \\\\"', '"1empieza_con_digito"',
                          '"tab\\tnueva\\nlinea"', "*ABS*", "-8", "-2147483648",
                          "[ENTRADA] \"DATO\" + 0x0027", "TAM 4096"):
            with self.subTest(fragmento=fragmento):
                self.assertIn(fragmento, texto)
        self.assertIn('[MODULO] ""', ModuloObjeto("", [SeccionObjeto.texto(b"\x00")]).a_texto())

    def test_formato_de_salida(self) -> None:
        self.assertEqual(
            construir_modulo_libmat().a_texto(),
            "; Modulo objeto reubicable de Enigma-64 en formato de texto (.tobj)\n"
            "[MODULO] libmat\n"
            "\n"
            "[SECCION] .text BITS R-X ALIN 1 {\n"
            "    10 52 30 4C 14 50 00 EE 31 51 00 10 00\n"
            "}\n"
            "\n"
            "[SIMBOLOS]\n"
            "; nombre  ligadura  tipo     seccion  valor\n"
            "sumar     GLOBAL    FUNCION  .text    0x0000\n"
            "error     GLOBAL    FUNCION  .text    0x0004\n"
            "\n"
            "[REUBICACIONES]\n"
            "; seccion  offset  tipo  simbolo  sumando\n",
        )

    def test_lo_que_no_se_puede_escribir(self) -> None:
        texto = SeccionObjeto.texto(b"\x00")
        with self.assertRaises(ObjetoInvalido):
            ModuloObjeto("m", [texto], [SimboloObjeto.local("a\x01b", 0, 0)]).a_texto()
        with self.assertRaises(ObjetoInvalido):
            ModuloObjeto("m", [texto, SeccionObjeto.texto(b"\x00")]).a_texto()

    def test_guardar_texto_y_leer_archivo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "variado.TOBJ")
            _modulo_variado().guardar_texto(ruta)
            self.assertEqual(analizar_objeto(ruta), _modulo_variado())


# ---------------------------------------------------------------------------
# 7. Integracion
# ---------------------------------------------------------------------------


def _leer64(ram: RAMMemory, direccion: int) -> int:
    valor, _ = ram.mem_read(direccion, size_bytes=8)
    return valor


class TestIntegracion(unittest.TestCase):
    """El .tobj entra por los mismos caminos que el .obj binario."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _ruta(self, nombre: str, contenido: str) -> str:
        ruta = os.path.join(self.dir, nombre)
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(contenido)
        return ruta

    def test_enlace_mixto_de_texto_y_binario(self) -> None:
        libmat_obj = os.path.join(self.dir, "libmat.obj")
        construir_modulo_libmat().guardar(libmat_obj)
        ram, banco = RAMMemory(), BancoRegistros()
        meta = EnlazadorEnigma([RUTA_PRINCIPAL, libmat_obj]).enlazar_y_cargar(
            CargadorEnigma(ram=ram, banco=banco), 0x00300000
        )
        cpu = CPU(ram=ram, banco=banco)
        cpu.ejecutar(max_ciclos=10_000)
        self.assertEqual(meta["modulos"], ["principal", "libmat"])
        self.assertEqual(_leer64(ram, meta["simbolos"]["resultado"]), VALOR_A + VALOR_B)
        self.assertEqual(cpu.instrucciones, 15)

    def test_el_cargador_enlaza_y_carga_un_tobj(self) -> None:
        ruta = self._ruta("duplicador.tobj", TOBJ_DUPLICADOR)
        ram, banco = RAMMemory(), BancoRegistros()
        meta = CargadorEnigma(ram=ram, banco=banco).cargar_archivo(ruta, direccion_destino=0x00250000)
        self.assertEqual(banco.pc, 0x00250000)
        CPU(ram=ram, banco=banco).ejecutar(max_ciclos=10_000)
        self.assertEqual(_leer64(ram, meta["simbolos"]["doble"]), 42)

    def test_el_cargador_rechaza_un_tobj_con_importaciones(self) -> None:
        cargador = CargadorEnigma(ram=RAMMemory(), banco=BancoRegistros())
        with self.assertRaises(SimboloNoDefinido):
            cargador.cargar_archivo(RUTA_PRINCIPAL)

    def test_tobj_que_no_es_utf8(self) -> None:
        ruta = os.path.join(self.dir, "binario.tobj")
        with open(ruta, "wb") as f:
            f.write(b"[MODULO] \xff\n")
        with self.assertRaises(ObjetoInvalido):
            analizar_objeto(ruta)

    def _cli(self, *argumentos):
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = cli_enlazador(list(argumentos))
        return codigo, salida.getvalue(), errores.getvalue()

    def test_cli_tokens_y_enlace(self) -> None:
        e64 = os.path.join(self.dir, "demo.e64")
        codigo, salida, _ = self._cli(RUTA_PRINCIPAL, RUTA_LIBMAT, "--tokens", "-o", e64)
        self.assertEqual(codigo, 0)
        self.assertIn("<8, ENCABEZADO, [MODULO]>", salida)
        self.assertIn("<11, PERMISOS, R-X>", salida)
        self.assertIn("<52, TIPO_REUBICACION, HI16>", salida)
        self.assertRegex(salida, r"BYTE\s+89\n")
        self.assertRegex(salida, r"Errores lexicos\s+0\n")
        self.assertIn("Tabla de importaciones (2)", salida)
        self.assertTrue(os.path.getsize(e64) > 0)

    def test_cli_tokens_ignora_los_obj_binarios(self) -> None:
        libmat_obj = os.path.join(self.dir, "libmat.obj")
        construir_modulo_libmat().guardar(libmat_obj)
        codigo, salida, _ = self._cli(libmat_obj, "--tokens")
        self.assertEqual(codigo, 0)
        self.assertNotIn("Tokens de", salida)

    def test_cli_errores_devuelven_codigo_1(self) -> None:
        ruta = self._ruta("malo.tobj", "[MODULO] m\n[SECCION] .t BITS R-X ALIN 1 { 1 }\n")
        codigo, salida, errores = self._cli(ruta, "--tokens")
        self.assertEqual(codigo, 1)
        self.assertIn("ERROR LEXICO (linea 2, columna 32): byte mal formado", salida)
        self.assertIn("ObjetoInvalido", errores)
        self.assertIn("ERROR LEXICO (linea 2, columna 32)", errores)

    def test_orquestador_spl_acepta_tobj(self) -> None:
        from spl.__main__ import main as cli_spl

        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = cli_spl(["--obj", RUTA_PRINCIPAL, RUTA_LIBMAT, "--sin-tablas"])
        self.assertEqual(codigo, 0)
        self.assertIn("Módulos .obj enlazados   : 2 (principal, libmat)", salida.getvalue())
        self.assertIn("Registro retorno R5 (RV) : 42", salida.getvalue())

    def test_el_emulador_no_depende_de_ply(self) -> None:
        resultado = subprocess.run(
            [sys.executable, "-c",
             "import sys, enigma64; print('ply' in sys.modules)"],
            cwd=RAIZ, capture_output=True, text=True, check=True,
        )
        self.assertEqual(resultado.stdout.strip(), "False")


# ---------------------------------------------------------------------------
# 8. Escenario complementario 6 del informe
# ---------------------------------------------------------------------------


class TestEscenarioDelInforme(unittest.TestCase):
    """Las tablas del escenario 6 del informe salen de estos archivos."""

    def _tokenizar(self, ruta: str):
        with open(ruta, encoding="utf-8") as f:
            lexer = ObjetoLexer()
            tokens, errores = lexer.tokenizar(f.read())
        conteo = {}
        for tok in tokens:
            conteo[tok.type] = conteo.get(tok.type, 0) + 1
        return len(tokens), conteo, lexer.comentarios, errores

    def test_tokens_de_los_modulos_de_ejemplo(self) -> None:
        total, conteo, comentarios, errores = self._tokenizar(RUTA_PRINCIPAL)
        self.assertEqual((total, conteo["BYTE"], conteo["NOMBRE"], comentarios, errores),
                         (228, 89, 33, 33, []))
        total, conteo, comentarios, errores = self._tokenizar(RUTA_LIBMAT)
        self.assertEqual((total, conteo["BYTE"], conteo["NOMBRE"], comentarios, errores),
                         (43, 13, 6, 9, []))

    def test_errores_del_modulo_mal_formado(self) -> None:
        ruta = os.path.join(DIR_OBJETOS, "errores.tobj")
        total, _, comentarios, errores = self._tokenizar(ruta)
        self.assertEqual((total, comentarios, len(errores)), (87, 6, 7))
        with self.assertRaises(ObjetoInvalido) as ctx:
            analizar_objeto(ruta)
        self.assertEqual(
            [(type(e).__name__, e.linea, e.columna, e.lexema) for e in ctx.exception.errores],
            [("ErrorLexico", 11, 5, "0G"), ("ErrorLexico", 13, 33, "@"),
             ("ErrorLexico", 19, 33, "0x1G"), ("ErrorLexico", 20, 1, '"x\\q"'),
             ("ErrorSintactico", 21, 21, ""), ("ErrorLexico", 23, 1, "[TABLAS]"),
             ("ErrorLexico", 25, 31, "0x100000000"), ("ErrorSintactico", 26, 17, "HI32"),
             ("ErrorLexico", 28, 33, "{")],
        )


if __name__ == "__main__":
    unittest.main()
