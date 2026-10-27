"""
Batería de Pruebas Unitarias para las Tablas de Símbolos y Literales (SPL Enigma-64).
Responsabilidad: Integrante 6 (Tabla de Símbolos & Tablas de Literales).
"""

import pytest
import math
from spl.compilador.tablas import (
    TipoNumero,
    TablaID,
    TablaNum,
    TablaString,
    GestorTablasSimbolos,
    desescapar_cadena,
)


class TestDesescaparCadena:
    """Pruebas del algoritmo de des-escape determinista (Literal d)."""

    def test_cadena_simple(self):
        assert desescapar_cadena('"Hola mundo"') == "Hola mundo"

    def test_comillas_escapadas(self):
        assert desescapar_cadena(r'"Dijo: \"Hola\""') == 'Dijo: "Hola"'

    def test_barras_invertidas(self):
        assert desescapar_cadena(r'"C:\\Archivos\\flex"') == "C:\\Archivos\\flex"

    def test_secuencias_caracteres_control(self):
        assert desescapar_cadena(r'"Linea 1\nLinea 2\tTab"') == "Linea 1\nLinea 2\tTab"

    def test_cadena_vacia(self):
        assert desescapar_cadena('""') == ""

    def test_cadena_invalida_sin_comillas(self):
        assert desescapar_cadena("sin_comillas") == ""
        assert desescapar_cadena('"incompleta') == ""


class TestTablaID:
    """Pruebas de la Tabla de Identificadores (tablaID - Categoría 150)."""

    def test_insercion_e_indexacion_base_1(self):
        tabla = TablaID()
        idx1 = tabla.install("contador")
        idx2 = tabla.install("_temp")
        idx3 = tabla.install("val_max")

        assert idx1 == 1
        assert idx2 == 2
        assert idx3 == 3
        assert tabla.total == 3

    def test_deduplicacion_estricta(self):
        tabla = TablaID()
        idx1 = tabla.install("alpha")
        idx2 = tabla.install("beta")
        idx1_dup = tabla.install("alpha")
        idx2_dup = tabla.install("beta")

        assert idx1_dup == 1
        assert idx2_dup == 2
        assert tabla.total == 2

    def test_busqueda_y_obtencion(self):
        tabla = TablaID()
        tabla.install("registro_r0")
        assert tabla.buscar("registro_r0") == 1
        assert tabla.buscar("inexistente") is None

        entrada = tabla.obtener(1)
        assert entrada is not None
        assert entrada.lexema == "registro_r0"
        assert tabla.obtener(99) is None

    def test_desbordamiento_capacidad(self):
        tabla = TablaID(capacidad_maxima=2)
        tabla.install("v1")
        tabla.install("v2")
        with pytest.raises(OverflowError):
            tabla.install("v3")


class TestTablaNum:
    """Pruebas de la Tabla de Constantes Numéricas (tablaNum - Categoría 160)."""

    def test_enteros_decimales(self):
        tabla = TablaNum()
        idx = tabla.install("42")
        assert idx == 1
        e = tabla.obtener(1)
        assert e.tipo == TipoNumero.ENTERO_DECIMAL
        assert e.valor_int == 42
        assert e.valor_float == 42.0

    def test_enteros_hexadecimales_64bits(self):
        tabla = TablaNum()
        # Dirección MMIO típica de Enigma-64
        idx = tabla.install("0xFF000000")
        assert idx == 1
        e = tabla.obtener(1)
        assert e.tipo == TipoNumero.ENTERO_HEX
        assert e.valor_uint == 0xFF000000

    def test_enteros_binarios(self):
        tabla = TablaNum()
        idx = tabla.install("0b1010")
        assert idx == 1
        e = tabla.obtener(1)
        assert e.tipo == TipoNumero.ENTERO_BIN
        assert e.valor_int == 10

    def test_reales_decimales_y_cientificos_ieee754(self):
        tabla = TablaNum()
        idx_dec = tabla.install("25.5")
        idx_exp1 = tabla.install("1.5E3")
        idx_exp2 = tabla.install("0.05e-2")

        e_dec = tabla.obtener(idx_dec)
        e_exp1 = tabla.obtener(idx_exp1)
        e_exp2 = tabla.obtener(idx_exp2)

        assert e_dec.tipo == TipoNumero.REAL_DECIMAL
        assert math.isclose(e_dec.valor_float, 25.5)

        assert e_exp1.tipo == TipoNumero.REAL_CIENTIFICO
        assert math.isclose(e_exp1.valor_float, 1500.0)

        assert e_exp2.tipo == TipoNumero.REAL_CIENTIFICO
        assert math.isclose(e_exp2.valor_float, 0.0005)

        # Verificación del empaquetado binario IEEE 754 de 64 bits (hexadecimal)
        assert len(e_exp1.patron_ieee754_hex) == 16  # 64 bits = 8 bytes = 16 dígitos hex

    def test_deduplicacion_numerica(self):
        tabla = TablaNum()
        i1 = tabla.install("100")
        i2 = tabla.install("1.5E3")
        i1_dup = tabla.install("100")
        i2_dup = tabla.install("1.5E3")

        assert i1_dup == 1
        assert i2_dup == 2
        assert tabla.total == 2


class TestTablaString:
    """Pruebas de la Tabla de Cadenas Literales (tablaString - Categoría 170)."""

    def test_insercion_desescapada(self):
        tabla = TablaString()
        idx = tabla.install(r'"Mensaje: \"OK\"\n"')
        assert idx == 1
        e = tabla.obtener(1)
        assert e.texto == 'Mensaje: "OK"\n'
        assert e.longitud == len('Mensaje: "OK"\n')

    def test_cadena_vacia(self):
        tabla = TablaString()
        idx = tabla.install('""')
        assert idx == 1
        e = tabla.obtener(1)
        assert e.texto == ""
        assert e.longitud == 0

    def test_deduplicacion_sobre_texto_limpio(self):
        tabla = TablaString()
        i1 = tabla.install('"Texto"')
        i2 = tabla.install(r'"Otro \"texto\""')
        i1_dup = tabla.install('"Texto"')

        assert i1 == 1
        assert i2 == 2
        assert i1_dup == 1
        assert tabla.total == 2


class TestGestorTablasSimbolos:
    """Pruebas de integración del gestor global unificado."""

    def test_flujo_completo_compilador(self):
        gestor = GestorTablasSimbolos()

        id_x = gestor.install_id("x")
        num_10 = gestor.install_num("10")
        num_pi = gestor.install_num("3.14159")
        str_msg = gestor.install_string(r'"Salida: \t"')

        # Repeticiones
        assert gestor.install_id("x") == id_x
        assert gestor.install_num("10") == num_10

        volcado = gestor.generar_volcado_texto()
        assert "Tabla de Identificadores" in volcado
        assert "x" in volcado
        assert "3.14159" in volcado
        assert "Salida: \\t" in volcado

        # Limpiar
        gestor.limpiar()
        assert gestor.tabla_id.total == 0
        assert gestor.tabla_num.total == 0
        assert gestor.tabla_string.total == 0
