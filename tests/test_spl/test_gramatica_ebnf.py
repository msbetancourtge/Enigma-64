"""
Pruebas de verificación de la Gramática Libre de Contexto E-BNF (spl/compilador/gramatica_spl.ebnf).
"""

import re
from pathlib import Path

RUTA_EBNF = Path(__file__).resolve().parent.parent.parent / "spl" / "compilador" / "gramatica_spl.ebnf"


def test_archivo_ebnf_existe_y_no_vacio():
    assert RUTA_EBNF.exists(), f"El archivo {RUTA_EBNF} no existe"
    contenido = RUTA_EBNF.read_text(encoding="utf-8")
    assert len(contenido.strip()) > 100, "El archivo E-BNF está vacío o es demasiado corto"


def parsear_reglas_ebnf(contenido: str):
    """
    Parsea reglas E-BNF W3C separadas en sintácticas y léxicas mediante <?TOKENS?>.
    Retorna (reglas_sintacticas, reglas_lexicas, no_terminales_definidos, tokens_definidos).
    """
    # Eliminar comentarios /* ... */
    sin_comentarios = re.sub(r'/\*.*?\*/', '', contenido, flags=re.DOTALL)

    partes = sin_comentarios.split("<?TOKENS?>")
    assert len(partes) == 2, "La gramática debe contener exactamente una directiva <?TOKENS?>"

    parte_sintactica = partes[0]
    parte_lexica = partes[1]

    def extraer_reglas(texto: str) -> dict[str, str]:
        reglas = {}
        # Coincidencia con Nombre ::= Cuerpo (hasta siguiente Nombre ::= o fin de bloque)
        patron = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*::=\s*(.*?)(?=^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*::=|\Z)', re.MULTILINE | re.DOTALL)
        for m in patron.finditer(texto):
            nombre = m.group(1).strip()
            cuerpo = m.group(2).strip()
            reglas[nombre] = cuerpo
        return reglas

    reglas_sint = extraer_reglas(parte_sintactica)
    reglas_lex = extraer_reglas(parte_lexica)

    return reglas_sint, reglas_lex


def test_directiva_tokens_presente():
    contenido = RUTA_EBNF.read_text(encoding="utf-8")
    assert "<?TOKENS?>" in contenido, "Falta la directiva <?TOKENS?> exigida por Bottlecaps RR-UI"


def test_cero_no_terminales_indefinidos():
    """
    Verifica que todo símbolo no-terminal referenciado en el cuerpo de una producción
    esté debidamente definido en la sección sintáctica o léxica (0 undefined non-terminals).
    """
    contenido = RUTA_EBNF.read_text(encoding="utf-8")
    reglas_sint, reglas_lex = parsear_reglas_ebnf(contenido)

    simbolos_definidos = set(reglas_sint.keys()) | set(reglas_lex.keys())

    # Palabras clave y literales textuales están entrecomillados simple o doblemente: '...', "..."
    # Buscar identificadores en los cuerpos de las reglas sintácticas que no estén entrecomillados
    simbolos_referenciados = set()

    for nombre_regla, cuerpo in reglas_sint.items():
        # Remover cadenas literales '...' y "..."
        cuerpo_sin_strings = re.sub(r"'(?:\\.|[^'])*'", ' ', cuerpo)
        cuerpo_sin_strings = re.sub(r'"(?:\\.|[^"])*"', ' ', cuerpo_sin_strings)
        
        # Encontrar todas las palabras identificadoras
        tokens_encontrados = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', cuerpo_sin_strings)
        for tok in tokens_encontrados:
            simbolos_referenciados.add(tok)

    indefinidos = simbolos_referenciados - simbolos_definidos
    assert not indefinidos, f"Se encontraron no terminales indefinidos en la gramática: {indefinidos}"


def test_producciones_sintacticas_principales():
    """Verifica que las producciones clave del compilador SPL estén presentes."""
    contenido = RUTA_EBNF.read_text(encoding="utf-8")
    reglas_sint, _ = parsear_reglas_ebnf(contenido)

    producciones_requeridas = [
        "Programa",
        "DeclaracionExterna",
        "DefinicionTDA",
        "CampoTDA",
        "DefinicionTypedef",
        "EspecificadorTipo",
        "TipoBase",
        "DimensionesOpt",
        "DeclaracionVariable",
        "Inicializador",
        "ListaInicializadores",
        "DefinicionFuncion",
        "ListaParametrosOpt",
        "Parametro",
        "DimensionesParamOpt",
        "Bloque",
        "ElementoBloque",
        "Sentencia",
        "SentenciaAsignacionOExpr",
        "SentenciaIf",
        "SentenciaSwitch",
        "ClausulaCase",
        "ClausulaDefaultOpt",
        "SentenciaWhile",
        "SentenciaDoWhile",
        "SentenciaFor",
        "ForInicial",
        "AccionForOpt",
        "SentenciaReturn",
        "SentenciaBreak",
        "SentenciaContinue",
    ]

    for prod in producciones_requeridas:
        assert prod in reglas_sint, f"Falta la producción sintáctica obligatoria: {prod}"


def test_estratificacion_9_niveles_expresiones():
    """
    Verifica que la jerarquía estratificada de expresiones contenga exactamente
    los 9 niveles de precedencia sin ambigüedad gramatical:
    1. OrLogico
    2. AndLogico
    3. Igualdad (==, !=)
    4. Relacional (<, <=, >, >=)
    5. Aditiva (+, -)
    6. Multiplicativa (*, /, %)
    7. Unaria (+, -, !, sizeof)
    8. Postfija ([], ., ->, ())
    9. Primaria (ID, LiteralConstante, parentizada)
    """
    contenido = RUTA_EBNF.read_text(encoding="utf-8")
    reglas_sint, _ = parsear_reglas_ebnf(contenido)

    niveles = [
        "Expresion",
        "ExprOrLogico",
        "ExprAndLogico",
        "ExprIgualdad",
        "ExprRelacional",
        "ExprAditiva",
        "ExprMultiplicativa",
        "ExprUnaria",
        "ExprPostfija",
        "ExprPrimaria",
        "LiteralConstante",
    ]

    for niv in niveles:
        assert niv in reglas_sint, f"Falta el nivel estratificado de expresión: {niv}"

    # Verificar que sizeof esté presente en ExprUnaria
    assert "sizeof" in reglas_sint["ExprUnaria"]
    # Verificar que '.' y '->' estén en ExprPostfija
    assert "'.' ID" in reglas_sint["ExprPostfija"]
    assert "'->' ID" in reglas_sint["ExprPostfija"]


def test_reglas_lexicas_obligatorias():
    """Verifica que todos los tokens formales exigidos estén en la sección <?TOKENS?>."""
    contenido = RUTA_EBNF.read_text(encoding="utf-8")
    _, reglas_lex = parsear_reglas_ebnf(contenido)

    tokens_requeridos = [
        "ID",
        "ENTERO_DEC",
        "ENTERO_HEX",
        "ENTERO_BIN",
        "FLOTANTE",
        "STRING",
        "CHAR_LITERAL",
    ]

    for tok in tokens_requeridos:
        assert tok in reglas_lex, f"Falta la regla léxica formal obligatoria: {tok}"


def test_soporte_tda_struct_y_tda():
    """Verifica que tanto 'struct' como 'tda' estén soportados en DefinicionTDA y TipoBase."""
    contenido = RUTA_EBNF.read_text(encoding="utf-8")
    reglas_sint, _ = parsear_reglas_ebnf(contenido)

    assert "'struct'" in reglas_sint["DefinicionTDA"] and "'tda'" in reglas_sint["DefinicionTDA"]
    assert "'struct'" in reglas_sint["TipoBase"] and "'tda'" in reglas_sint["TipoBase"]


def test_soporte_then_y_function_opcionales():
    """Verifica que 'then' en if y 'function' en funciones sean opcionales (con '?')."""
    contenido = RUTA_EBNF.read_text(encoding="utf-8")
    reglas_sint, _ = parsear_reglas_ebnf(contenido)

    assert "'then'?" in reglas_sint["SentenciaIf"], "then debe ser opcional ('then'?)"
    assert "'function'?" in reglas_sint["DefinicionFuncion"], "function debe ser opcional ('function'?)"
