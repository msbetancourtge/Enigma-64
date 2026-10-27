"""
Suite de pruebas unitarias y de integración para el analizador léxico del Compilador SPL.
Fase 1: Vocabulario, Palabras Reservadas, Categorías Base y TDA (Integrante 4).
"""

import sys
import subprocess
from pathlib import Path
import pytest

from spl.compilador.lexer import (
    CompiladorLexer,
    ErrorLexico,
    PALABRAS_RESERVADAS,
    PALABRAS_RESERVADAS_CONTROL,
    PALABRAS_RESERVADAS_TIPOS,
    PALABRAS_RESERVADAS_TDA,
    CAT_PALABRA_RESERVADA,
    CAT_TIPO_PRIMITIVO,
    CAT_TIPO_ABSTRACTO,
    CAT_IDENTIFICADOR,
    CAT_DELIMITADOR,
)
from spl.compilador.tablas import GestorTablasSimbolos


@pytest.fixture
def lexer():
    """Instancia limpia de CompiladorLexer para cada prueba."""
    return CompiladorLexer()


# ===========================================================================
# 1. Pruebas de Palabras Reservadas y Categorías
# ===========================================================================

def test_palabras_reservadas_control(lexer):
    """Verifica el reconocimiento exacto de todas las palabras clave de control."""
    codigo = "if then else switch case default while do for continue function return break"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    tipos = [t.type for t in tokens]
    esperados = [
        "IF", "THEN", "ELSE", "SWITCH", "CASE", "DEFAULT",
        "WHILE", "DO", "FOR", "CONTINUE", "FUNCTION", "RETURN", "BREAK",
    ]
    assert tipos == esperados
    for t in tokens:
        assert t.categoria_codigo == CAT_PALABRA_RESERVADA


def test_palabras_reservadas_tipos_primitivos(lexer):
    """Verifica el reconocimiento de los tipos primitivos alineados a Enigma-64."""
    codigo = "int float void char bool const"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    tipos = [t.type for t in tokens]
    esperados = ["INT_TYPE", "FLOAT_TYPE", "VOID_TYPE", "CHAR_TYPE", "BOOL_TYPE", "CONST"]
    assert tipos == esperados
    for t in tokens:
        assert t.categoria_codigo == CAT_TIPO_PRIMITIVO


def test_palabras_reservadas_tda_y_estructuras(lexer):
    """Verifica el reconocimiento de constructos para Tipos de Datos Abstractos."""
    codigo = "struct tda typedef sizeof"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    tipos = [t.type for t in tokens]
    esperados = ["STRUCT", "TDA", "TYPEDEF", "SIZEOF"]
    assert tipos == esperados
    for t in tokens:
        assert t.categoria_codigo == CAT_TIPO_ABSTRACTO


def test_insensibilidad_controlada_mayusculas(lexer):
    """Verifica que las palabras reservadas se reconozcan en minúsculas y mayúsculas."""
    codigo = "IF if If WHILE while While STRUCT struct Struct"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    tipos = [t.type for t in tokens]
    esperados = [
        "IF", "IF", "IF",
        "WHILE", "WHILE", "WHILE",
        "STRUCT", "STRUCT", "STRUCT",
    ]
    assert tipos == esperados


# ===========================================================================
# 2. Pruebas de Desambiguación de Identificadores (ID vs Keywords)
# ===========================================================================

def test_desambiguacion_identificadores_con_prefijos(lexer):
    """
    Verifica que identificadores que comienzan o contienen palabras clave
    no sean fragmentados ni confundidos con palabras reservadas.
    """
    codigo = "if_condicion while_contador float_suma struct_nodo int_val format"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    assert len(tokens) == 6
    for t in tokens:
        assert t.type == "ID"
        assert t.categoria_codigo == CAT_IDENTIFICADOR


def test_desambiguacion_identificadores_con_sufijos(lexer):
    """Verifica identificadores que terminan en palabras clave."""
    codigo = "my_if total_while calcular_float es_const"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    assert len(tokens) == 4
    for t in tokens:
        assert t.type == "ID"
        assert t.categoria_codigo == CAT_IDENTIFICADOR


# ===========================================================================
# 3. Pruebas de Arreglos, Matrices y Tipos de Datos Abstractos (TDA)
# ===========================================================================

def test_declaracion_arreglo_unidimensional(lexer):
    """Verifica el reconocimiento de arreglos unidimensionales (vector[10])."""
    codigo = "int vector[10];"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    tipos = [t.type for t in tokens]
    assert tipos == ["INT_TYPE", "ID", "CORCHETE_IZQ", "ENTERO_DEC", "CORCHETE_DER", "PUNTO_Y_COMA"]
    assert tokens[2].categoria_codigo == CAT_DELIMITADOR
    assert tokens[4].categoria_codigo == CAT_DELIMITADOR


def test_declaracion_matriz_multidimensional(lexer):
    """Verifica el reconocimiento de matrices multidimensionales (matriz[4][8][2])."""
    codigo = "float matriz[4][8][2];"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    tipos = [t.type for t in tokens]
    assert tipos == [
        "FLOAT_TYPE", "ID",
        "CORCHETE_IZQ", "ENTERO_DEC", "CORCHETE_DER",
        "CORCHETE_IZQ", "ENTERO_DEC", "CORCHETE_DER",
        "CORCHETE_IZQ", "ENTERO_DEC", "CORCHETE_DER",
        "PUNTO_Y_COMA",
    ]


def test_definicion_tda_struct_y_acceso_campos(lexer):
    """Verifica la definición de un struct/TDA y el acceso a campos con '.' y '->'."""
    codigo = """
    struct Punto {
        float x;
        float y;
    };
    p.x = 10.5;
    ptr->y = 20.0;
    """
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    tipos = [t.type for t in tokens]
    assert "STRUCT" in tipos
    assert "LLAVE_IZQ" in tipos
    assert "LLAVE_DER" in tipos
    assert "PUNTO" in tipos
    assert "FLECHA" in tipos


# ===========================================================================
# 4. Integración con GestorTablasSimbolos (Deduplicación en tablaID)
# ===========================================================================

def test_integracion_tabla_simbolos_deduplicacion(lexer):
    """
    Verifica que los identificadores se instalen en tablaID sin duplicados
    y que reciban el mismo índice correlativo base 1.
    """
    codigo = "contador = contador + 1; limite = contador * 2;"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    # Identificadores: contador (3 veces), limite (1 vez)
    tokens_id = [t for t in tokens if t.type == "ID"]
    assert len(tokens_id) == 4

    # Los tres 'contador' deben compartir el mismo símbolo 1
    assert tokens_id[0].value == "contador"
    assert tokens_id[0].simbolo_idx == 1
    assert tokens_id[1].value == "contador"
    assert tokens_id[1].simbolo_idx == 1
    assert tokens_id[3].value == "contador"
    assert tokens_id[3].simbolo_idx == 1

    # 'limite' debe ser el símbolo 2
    assert tokens_id[2].value == "limite"
    assert tokens_id[2].simbolo_idx == 2

    # La tabla de símbolos debe tener exactamente 2 entradas registradas
    assert lexer.tablas.tabla_id.total == 2


def test_palabras_reservadas_no_contaminan_tabla_id(lexer):
    """Verifica que las palabras reservadas NO se registren en la tabla de identificadores."""
    codigo = "if else while for struct int float return"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    # No debe haber ningún ID
    assert all(t.type != "ID" for t in tokens)
    # La tabla de identificadores debe permanecer vacía
    assert lexer.tablas.tabla_id.total == 0


# ===========================================================================
# 5. Pruebas de Comentarios, Líneas, Columnas y Errores
# ===========================================================================

def test_comentarios_linea_y_bloque(lexer):
    """Verifica que los comentarios de línea y bloque se ignoren y cuenten."""
    codigo = """
    // Comentario inicial de una linea
    int x = 5;
    /* Comentario de bloque
       que abarca multiples lineas */
    float y = 3.14;
    """
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    assert lexer.comentarios == 2
    tipos = [t.type for t in tokens]
    assert "INT_TYPE" in tipos
    assert "FLOAT_TYPE" in tipos


def test_conteo_exacto_de_lineas_y_columnas(lexer):
    """Verifica el cálculo de líneas y columnas para cada token."""
    codigo = "int x;\nfloat y;\n   int z;"
    tokens, errores = lexer.tokenizar(codigo)

    assert not errores
    # Línea 1: int x;
    assert tokens[0].type == "INT_TYPE" and tokens[0].lineno == 1 and tokens[0].columna == 1
    assert tokens[1].type == "ID" and tokens[1].lineno == 1 and tokens[1].columna == 5
    # Línea 2: float y;
    assert tokens[3].type == "FLOAT_TYPE" and tokens[3].lineno == 2 and tokens[3].columna == 1
    # Línea 3:    int z; (con 3 espacios)
    assert tokens[6].type == "INT_TYPE" and tokens[6].lineno == 3 and tokens[6].columna == 4


def test_reporte_y_recuperacion_ante_errores_lexicos(lexer):
    """
    Verifica que ante caracteres inválidos se reporte ErrorLexico con línea y columna,
    y que el lexer continúe analizando el resto del texto.
    """
    codigo = "int @val = $50;"
    tokens, errores = lexer.tokenizar(codigo)

    assert len(errores) == 2
    assert errores[0].lexema == "@"
    assert errores[0].linea == 1
    assert errores[0].columna == 5
    assert errores[1].lexema == "$"
    assert errores[1].linea == 1
    assert errores[1].columna == 12

    # Se debieron recuperar los tokens válidos
    tipos = [t.type for t in tokens]
    assert "INT_TYPE" in tipos
    assert "ID" in tipos
    assert "ASIGNAR" in tipos
    assert "ENTERO_DEC" in tipos
    assert "PUNTO_Y_COMA" in tipos


# ===========================================================================
# 6. Validación de Escenarios de Ejemplo Oficiales
# ===========================================================================

def test_escenario_1_ejemplo_tda_matrices(lexer):
    """Valida el escenario formal 1 (TDAs, vectores y matrices)."""
    ruta_ejemplo = Path(__file__).parent.parent.parent / "spl" / "compilador" / "ejemplos" / "escenario1_tda_matrices.spl"
    with open(ruta_ejemplo, encoding="utf-8") as f:
        texto = f.read()

    tokens, errores = lexer.tokenizar(texto)
    assert not errores
    assert len(tokens) > 100
    assert lexer.tablas.tabla_id.total == 16


def test_escenario_2_ejemplo_control_funciones(lexer):
    """Valida el escenario formal 2 (control de flujo, iteración y desambiguación)."""
    ruta_ejemplo = Path(__file__).parent.parent.parent / "spl" / "compilador" / "ejemplos" / "escenario2_control_funciones.spl"
    with open(ruta_ejemplo, encoding="utf-8") as f:
        texto = f.read()

    tokens, errores = lexer.tokenizar(texto)
    assert not errores
    assert len(tokens) > 150
    assert lexer.tablas.tabla_id.total == 16


def test_escenario_3_ejemplo_errores_recuperacion(lexer):
    """Valida el escenario formal 3 (detección de 7 errores y recuperación)."""
    ruta_ejemplo = Path(__file__).parent.parent.parent / "spl" / "compilador" / "ejemplos" / "escenario3_errores_recuperacion.spl"
    with open(ruta_ejemplo, encoding="utf-8") as f:
        texto = f.read()

    tokens, errores = lexer.tokenizar(texto)
    assert len(errores) == 7
    # Verifica que a pesar de los errores, fin_del_programa se tokenizó
    nombres_id = [t.value for t in tokens if t.type == "ID"]
    assert "fin_del_programa" in nombres_id


# ===========================================================================
# 7. Prueba del CLI (python -m spl.compilador)
# ===========================================================================

def test_cli_compilador():
    """Verifica la ejecución del CLI mediante subprocess con salida formateada."""
    ruta_ejemplo = Path(__file__).parent.parent.parent / "spl" / "compilador" / "ejemplos" / "escenario1_tda_matrices.spl"
    cmd = [sys.executable, "-m", "spl.compilador", str(ruta_ejemplo)]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=str(Path(__file__).parent.parent.parent))

    assert res.returncode == 0
    assert "SECUENCIA DE TOKENS SPL" in res.stdout
    assert "ESTADO FINAL DE LAS TABLAS DE SIMBOLOS" in res.stdout
    assert "RESUMEN DEL ANALISIS LEXICO DEL COMPILADOR" in res.stdout
