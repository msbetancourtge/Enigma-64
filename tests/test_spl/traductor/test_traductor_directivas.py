"""
Pruebas Unitarias y de Integración — Directivas, Secciones, Literales y Cargador.
Tarea 27: Traductor de ensamblador CacaoCore-64 a Enigma-64 (Integrante 4).

Cubre:
  1. Analizador léxico PLY (LexerDirectivasCacao) para directivas y secciones.
  2. Normalización de literales a 64 bits (hex, dec, bin, float IEEE 754, char, str).
  3. Reubicación y alineación a 8 bytes en espacio de usuario (>= 0x00201000).
  4. Conversión Little-Endian (CacaoCore) -> Big-Endian (Enigma-64).
  5. Enlace con CargadorEnigma, precarga en RAM y exportación .e64.
  6. Ejecución E2E de los algoritmos clásicos con CargadorEnigma.
"""

from __future__ import annotations

import os
import struct
import tempfile
import unittest
from pathlib import Path

from enigma64.cargador import (
    MAGIC_ENIGMA,
    USER_MEM_START,
    BinarioEnigma,
    CargadorEnigma,
    ViolacionProteccionMemoria,
)
from enigma64.cpu import CPU
from enigma64.memoria import RAMMemory
from enigma64.registros import BancoRegistros, MASK64
from spl.traductor.directivas import (
    BASE_CODIGO,
    BASE_DATOS,
    LexerDirectivasCacao,
    MapaSeccionDatos,
    ProcesadorDirectivasCacao,
    VariableDato,
    cargar_y_ejecutar_con_cargador,
    construir_binario_enigma,
    exportar_ejecutable_e64,
    normalizar_literal_cacao,
    precargar_datos_en_ram,
)
from spl.traductor.traductor import TraductorCacaoEnigma, traducir_texto

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
EJEMPLOS_DIR = BASE_DIR / "spl" / "traductor" / "ejemplos"


class TestLexerDirectivasCacao(unittest.TestCase):
    """Pruebas del analizador léxico PLY para secciones y directivas."""

    def setUp(self) -> None:
        self.lexer = LexerDirectivasCacao()

    def test_reconocimiento_secciones_estandar(self) -> None:
        fuente = ".data\n.text\n.DATA\n.TEXT\n.bss\n.rodata"
        tokens = self.lexer.tokenizar(fuente)
        tipos = [t.type for t in tokens]
        self.assertEqual(tipos, [
            "SECCION_DATA", "SECCION_TEXT",
            "SECCION_DATA", "SECCION_TEXT",
            "SECCION_OTRA", "SECCION_OTRA"
        ])

    def test_reconocimiento_secciones_objeto_cacao(self) -> None:
        fuente = "[DATA]\n[CODE]\n[MODULE]\n[SYMBOLS]\n[EXTERNAL]"
        tokens = self.lexer.tokenizar(fuente)
        tipos = [t.type for t in tokens]
        self.assertEqual(tipos, [
            "SECCION_DATA", "SECCION_TEXT",
            "SECCION_OTRA", "SECCION_OTRA", "SECCION_OTRA"
        ])

    def test_reconocimiento_directivas_de_tamano(self) -> None:
        fuente = ".word 10\n.quad 20\n.byte 30\n.ascii \"hola\"\n.space 64"
        tokens = self.lexer.tokenizar(fuente)
        directivas = [t.value for t in tokens if t.type == "DIRECTIVA_DATO"]
        self.assertEqual(directivas, [".word", ".quad", ".byte", ".ascii", ".space"])

    def test_filtrado_de_comentarios(self) -> None:
        fuente = """
        # Comentario tipo CacaoCore
        .data ; Comentario tipo Enigma
        n: 5 # Valor inicial
        """
        tokens = self.lexer.tokenizar(fuente)
        tipos = [t.type for t in tokens]
        self.assertNotIn("COMENTARIO", tipos)
        self.assertIn("SECCION_DATA", tipos)
        self.assertIn("IDENTIFICADOR", tipos)
        self.assertIn("LITERAL_DEC", tipos)


class TestNormalizacionLiterales(unittest.TestCase):
    """Pruebas de la normalización universal de constantes a patrones de 64 bits."""

    def test_enteros_decimales(self) -> None:
        bits, tipo = normalizar_literal_cacao("48")
        self.assertEqual(tipo, "decimal")
        self.assertEqual(bits, 48)

        bits, tipo = normalizar_literal_cacao("0")
        self.assertEqual(tipo, "decimal")
        self.assertEqual(bits, 0)

        # Entero negativo en complemento a dos
        bits, tipo = normalizar_literal_cacao("-1")
        self.assertEqual(tipo, "decimal")
        self.assertEqual(bits, 0xFFFFFFFFFFFFFFFF)

        bits, tipo = normalizar_literal_cacao("-120")
        self.assertEqual(tipo, "decimal")
        self.assertEqual(bits, (-120) & MASK64)

    def test_hexadecimales(self) -> None:
        bits, tipo = normalizar_literal_cacao("0x00000177")
        self.assertEqual(tipo, "hexadecimal")
        self.assertEqual(bits, 0x177)

        bits, tipo = normalizar_literal_cacao("0xFF")
        self.assertEqual(tipo, "hexadecimal")
        self.assertEqual(bits, 255)

        bits, tipo = normalizar_literal_cacao("-0x10")
        self.assertEqual(tipo, "hexadecimal")
        self.assertEqual(bits, (-16) & MASK64)

    def test_binarios(self) -> None:
        bits, tipo = normalizar_literal_cacao("0b1010")
        self.assertEqual(tipo, "binario")
        self.assertEqual(bits, 10)

        bits, tipo = normalizar_literal_cacao("-0b11")
        self.assertEqual(tipo, "binario")
        self.assertEqual(bits, (-3) & MASK64)

    def test_flotantes_ieee754(self) -> None:
        bits, tipo = normalizar_literal_cacao("3.141592653589793")
        self.assertEqual(tipo, "flotante")
        (flt_reconstruido,) = struct.unpack(">d", struct.pack(">Q", bits))
        self.assertAlmostEqual(flt_reconstruido, 3.141592653589793, places=10)

        bits_neg, _ = normalizar_literal_cacao("-0.5")
        (flt_neg,) = struct.unpack(">d", struct.pack(">Q", bits_neg))
        self.assertEqual(flt_neg, -0.5)

    def test_caracteres_y_escapes(self) -> None:
        bits, tipo = normalizar_literal_cacao("'h'")
        self.assertEqual(tipo, "caracter")
        self.assertEqual(bits, ord("h"))

        bits, tipo = normalizar_literal_cacao(r"'\n'")
        self.assertEqual(tipo, "caracter")
        self.assertEqual(bits, 10)

        bits, tipo = normalizar_literal_cacao(r"'\0'")
        self.assertEqual(tipo, "caracter")
        self.assertEqual(bits, 0)

        bits, tipo = normalizar_literal_cacao(r"'\t'")
        self.assertEqual(tipo, "caracter")
        self.assertEqual(bits, 9)

    def test_cadenas(self) -> None:
        bits, tipo = normalizar_literal_cacao('"HOLA"')
        self.assertEqual(tipo, "cadena")
        self.assertEqual(bits, ord("H"))


class TestProcesadorDirectivasCacao(unittest.TestCase):
    """Pruebas del procesamiento de la sección de datos y asignación de memoria."""

    def test_extraccion_datos_alineados(self) -> None:
        fuente = """
        .data
            a : 48
            b : 18
            nombre : 'X'
            factor : 3.5
            hexval : 0x00FF
        .text
            HLT
        """
        proc = ProcesadorDirectivasCacao(base_datos=0x00201000)
        mapa = proc.procesar(fuente)
        self.assertTrue(mapa.ok)
        self.assertEqual(mapa.total_variables, 5)

        # Verificación de alineación a 8 bytes
        self.assertEqual(mapa.obtener_direccion("a"), 0x00201000)
        self.assertEqual(mapa.obtener_direccion("b"), 0x00201008)
        self.assertEqual(mapa.obtener_direccion("nombre"), 0x00201010)
        self.assertEqual(mapa.obtener_direccion("factor"), 0x00201018)
        self.assertEqual(mapa.obtener_direccion("hexval"), 0x00201020)

        for var in mapa.variables.values():
            self.assertEqual(var.direccion_enigma % 8, 0, "Debe ser múltiplo de 8")

    def test_inversion_endianness(self) -> None:
        fuente = ".data\nval: 0x12345678\n.text\nHLT"
        proc = ProcesadorDirectivasCacao(base_datos=0x00201000)
        mapa = proc.procesar(fuente)
        var = mapa.variables["val"]

        # Enigma-64 (Big-Endian): el byte más significativo va primero
        self.assertEqual(var.bytes_big_endian, bytes([0x00, 0x00, 0x00, 0x00, 0x12, 0x34, 0x56, 0x78]))
        # CacaoCore (Little-Endian): el byte menos significativo va primero
        self.assertEqual(var.bytes_little_endian, bytes([0x78, 0x56, 0x34, 0x12, 0x00, 0x00, 0x00, 0x00]))

    def test_arreglos_separados_por_comas(self) -> None:
        fuente = """
        .data
            arr: 10, 20, 30
        .text
            HLT
        """
        proc = ProcesadorDirectivasCacao(base_datos=0x00201000)
        mapa = proc.procesar(fuente)
        self.assertTrue(mapa.ok)
        var = mapa.variables["arr"]
        self.assertEqual(var.valor_bits, 10)
        self.assertEqual(var.elementos_extra, [20, 30])
        self.assertEqual(mapa.tamano_total_bytes, 24)  # 3 palabras * 8 bytes


class TestEnlaceCargadorEnigma(unittest.TestCase):
    """Pruebas de la precarga en RAM y enlace con CargadorEnigma."""

    def test_precargar_datos_en_ram(self) -> None:
        fuente = """
        .data
            x: 100
            y: 200
        .text
            HLT
        """
        proc = ProcesadorDirectivasCacao(base_datos=0x00201000)
        mapa = proc.procesar(fuente)
        ram = RAMMemory()

        bytes_escritos = precargar_datos_en_ram(ram, mapa)
        self.assertEqual(bytes_escritos, 16)

        # Leer directamente de RAM y contrastar
        val_x, st_x = ram.mem_read(0x00201000, 8)
        val_y, st_y = ram.mem_read(0x00201008, 8)
        self.assertIn(st_x, (0, "READY"))
        self.assertIn(st_y, (0, "READY"))
        self.assertEqual(val_x, 100)
        self.assertEqual(val_y, 200)

    def test_rechazo_bajo_frontera_de_usuario(self) -> None:
        fuente = ".data\nx: 10\n.text\nHLT"
        # Dirección prohibida bajo 0x00200000
        proc = ProcesadorDirectivasCacao(base_datos=0x00100000)
        mapa = proc.procesar(fuente)
        ram = RAMMemory()

        with self.assertRaises(ViolacionProteccionMemoria):
            precargar_datos_en_ram(ram, mapa)

    def test_construir_y_exportar_binario_e64(self) -> None:
        fuente = """
        .data
            num: 42
        .text
            ADDI R1, R0, 7
            HLT
        """
        res = traducir_texto(fuente)
        proc = ProcesadorDirectivasCacao()
        mapa = proc.procesar(fuente)

        binario = construir_binario_enigma(res.codigo, mapa)
        self.assertEqual(binario.serializar_e64()[:4], MAGIC_ENIGMA)
        self.assertEqual(binario.entry_point, BASE_CODIGO)
        self.assertIn("num", binario.tabla_simbolos)
        self.assertEqual(binario.tabla_simbolos["num"], 0x00201000)

        # Exportar y verificar deserialización
        with tempfile.NamedTemporaryFile(suffix=".e64", delete=False) as tf:
            ruta_tmp = tf.name

        try:
            exportar_ejecutable_e64(res.codigo, mapa, ruta_tmp)
            with open(ruta_tmp, "rb") as f:
                contenido = f.read()
            self.assertEqual(contenido[:4], MAGIC_ENIGMA)
            bin_reconstruido = BinarioEnigma.deserializar_e64(contenido)
            self.assertEqual(bin_reconstruido.entry_point, BASE_CODIGO)
            self.assertIn("num", bin_reconstruido.tabla_simbolos)
        finally:
            if os.path.exists(ruta_tmp):
                os.remove(ruta_tmp)


class TestEjecucionAlgoritmosConCargador(unittest.TestCase):
    """Ejecución de los tres algoritmos clásicos empleando formalmente CargadorEnigma."""

    def test_cargador_euclides(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_euclides.asm"
        self.assertTrue(ruta_asm.is_file())
        fuente = ruta_asm.read_text(encoding="utf-8")

        cpu, banco, ram, cargador, info = cargar_y_ejecutar_con_cargador(fuente)
        self.assertEqual(cpu.fase, "FETCH")
        self.assertTrue(cpu.detenido)

        # Leer resultado del MCD de Mem[a] (0x00201000)
        val_mcd, _ = ram.mem_read(0x00201000, 8)
        self.assertEqual(val_mcd, 6, "MCD(48, 18) debe ser 6")

    def test_cargador_factorial(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_factorial.asm"
        self.assertTrue(ruta_asm.is_file())
        fuente = ruta_asm.read_text(encoding="utf-8")

        cpu, banco, ram, cargador, info = cargar_y_ejecutar_con_cargador(fuente)
        self.assertTrue(cpu.detenido)

        # Leer resultado de 5! en Mem[fact] (0x00201008)
        val_fact, _ = ram.mem_read(0x00201008, 8)
        self.assertEqual(val_fact, 120, "Factorial de 5 debe ser 120")

    def test_cargador_fibonacci(self) -> None:
        ruta_asm = EJEMPLOS_DIR / "cacao_fibonacci.asm"
        self.assertTrue(ruta_asm.is_file())
        fuente = ruta_asm.read_text(encoding="utf-8")

        cpu, banco, ram, cargador, info = cargar_y_ejecutar_con_cargador(fuente)
        self.assertTrue(cpu.detenido)

        # Leer el séptimo término de Fibonacci en Mem[res] (0x00201040)
        val_fib7, _ = ram.mem_read(0x00201040, 8)
        self.assertEqual(val_fib7, 8, "Fibonacci(6) debe ser 8")


if __name__ == "__main__":
    unittest.main()
