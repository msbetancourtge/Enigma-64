"""
Suite de pruebas exhaustiva para el Preprocesador del SPL de Enigma-64.
Verifica macros, comentarios, directivas condicionales, includes,
deteccion de ciclos, mapa de lineas y CLI.
"""

import sys
import subprocess
import pytest

from spl.preprocesador import (
    preprocesar_archivo,
    preprocesar_texto,
    PreprocesadorError,
)


# 1. Pruebas de Macros (#define, #undef)

class TestMacros:
    def test_define_constante_simple(self):
        codigo = (
            "#define MAX 100\n"
            "int a = MAX;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int a = 100;"
        assert res.macros["MAX"] == "100"

    def test_define_alias_tipo(self):
        codigo = (
            "#define ENTERO int\n"
            "ENTERO a = 42;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int a = 42;"
        assert res.macros["ENTERO"] == "int"

    def test_define_vacio(self):
        codigo = (
            "#define VACIO\n"
            "int VACIO x = 10;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int  x = 10;"
        assert res.macros["VACIO"] == ""

    def test_sustituye_solo_identificadores_completos(self):
        codigo = (
            "#define MAX 100\n"
            "int MAXIMO = MAX;\n"
            "int SUB_MAX = 50;\n"
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "int MAXIMO = 100;"
        assert lineas[1] == "int SUB_MAX = 50;"

    def test_no_sustituye_dentro_de_cadenas_y_caracteres(self):
        codigo = (
            '#define MAX 100\n'
            '#define MSG "hola"\n'
            'char *s = "MAX no cambia MSG";\n'
            'char c = \'M\';\n'
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == 'char *s = "MAX no cambia MSG";'
        assert lineas[1] == "char c = 'M';"

    def test_no_sustituye_dentro_de_numeros(self):
        codigo = (
            "#define FF 99\n"
            "#define e 2.71\n"
            "#define b 0\n"
            "int x = 0xFF;\n"
            "float y = 1e5;\n"
            "int bin = 0b101;\n"
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "int x = 0xFF;"
        assert lineas[1] == "float y = 1e5;"
        assert lineas[2] == "int bin = 0b101;"

    def test_macro_usa_otras_macros_cadena(self):
        codigo = (
            "#define A B\n"
            "#define B C\n"
            "#define C 42\n"
            "int valor = A;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int valor = 42;"

    def test_evita_bucles_infinitos_ciclo_mutuo(self):
        codigo = (
            "#define A B\n"
            "#define B A\n"
            "int x = A;\n"
            "int y = B;\n"
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "int x = A;"
        assert lineas[1] == "int y = B;"

    def test_evita_bucles_infinitos_autoreferencia(self):
        codigo = (
            "#define X X\n"
            "int x = X;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int x = X;"

    def test_continuacion_de_linea_con_barra(self):
        codigo = (
            "#define SUMA \\\n"
            "    a + \\\n"
            "    b\n"
            "int r = SUMA;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int r = a + b;"
        assert res.macros["SUMA"] == "a + b"

    def test_undef(self):
        codigo = (
            "#define FOO 10\n"
            "int a = FOO;\n"
            "#undef FOO\n"
            "int b = FOO;\n"
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "int a = 10;"
        assert lineas[1] == "int b = FOO;"
        assert "FOO" not in res.macros

    def test_undef_inexistente_no_falla(self):
        codigo = (
            "#undef NO_EXISTE\n"
            "int a = 1;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int a = 1;"

    def test_redefinicion_de_macro(self):
        codigo = (
            "#define X 10\n"
            "int a = X;\n"
            "#define X 20\n"
            "int b = X;\n"
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "int a = 10;"
        assert lineas[1] == "int b = 20;"
        assert res.macros["X"] == "20"

    def test_directiva_con_espacios_antes_y_despues_de_hash(self):
        codigo = "   #   define   ESPACIADO   999  \nint val = ESPACIADO;\n"
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int val = 999;"
        assert res.macros["ESPACIADO"] == "999"

    def test_macro_con_comentarios_internos(self):
        codigo = "#define VALOR /* comentario */ 123 // comentario fin\nint x = VALOR;\n"
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int x = 123;"

    def test_error_directiva_desconocida(self):
        codigo = "#directiva_inexistente arg1\nint x = 1;\n"
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo, nombre_archivo="test.c")
        assert "test.c:1: error: directiva desconocida '#directiva_inexistente'" in str(exc_info.value)


# 2. Pruebas de Comentarios

class TestComentarios:
    def test_comentario_linea_simple(self):
        codigo = "int a = 10; // Este es un comentario\nint b = 20;\n"
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0].strip() == "int a = 10;"
        assert lineas[1].strip() == "int b = 20;"

    def test_comentario_bloque_en_una_linea(self):
        codigo = "int a = /* comentario */ 10;\n"
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int a =   10;"

    def test_comentario_bloque_multilinea_conserva_saltos_de_linea(self):
        codigo = (
            "int a = 1;\n"
            "/* inicio comentario\n"
            "   segunda linea\n"
            "   fin comentario */\n"
            "int b = 2;\n"
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.splitlines()
        # Verificamos que 'int b = 2;' permanezca en la linea 5 (conservando lineas)
        assert "int a = 1;" in lineas[0]
        assert "int b = 2;" in lineas[4]
        # Y mapa_lineas mapea correctamente a la linea original 5
        assert res.mapa_lineas[4] == ("<stdin>", 5)

    def test_comentarios_dentro_de_cadenas_no_se_tocan(self):
        codigo = (
            'char *c1 = "// esto no es comentario";\n'
            'char *c2 = "/* esto tampoco */";\n'
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == 'char *c1 = "// esto no es comentario";'
        assert lineas[1] == 'char *c2 = "/* esto tampoco */";'

    def test_error_comentario_bloque_no_cerrado(self):
        codigo = "int a = 1;\n/* comentario que nunca se cierra"
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo, nombre_archivo="prueba.c")
        err_msg = str(exc_info.value)
        assert "prueba.c:2: error:" in err_msg
        assert "comentario de bloque no cerrado" in err_msg

    def test_no_toca_comentarios_punto_y_coma_en_archivos_s(self):
        codigo_s = (
            "; Subrutina de prueba Enigma-64\n"
            "FPU_TEST:\n"
            "    SHR R2, R1, 63 ; Extraer signo\n"
            "    RET\n"
        )
        res = preprocesar_texto(codigo_s, nombre_archivo="fpu_test.s")
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "; Subrutina de prueba Enigma-64"
        assert "; Extraer signo" in lineas[2]


# 3. Pruebas de Directivas Condicionales (#ifdef, #ifndef, #else, #endif)

class TestCondicionales:
    def test_ifdef_cuando_esta_definido(self):
        codigo = (
            "#define ACTIVADO\n"
            "#ifdef ACTIVADO\n"
            "int x = 1;\n"
            "#else\n"
            "int x = 2;\n"
            "#endif\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int x = 1;"

    def test_ifdef_cuando_no_esta_definido(self):
        codigo = (
            "#ifdef DESACTIVADO\n"
            "int x = 1;\n"
            "#else\n"
            "int x = 2;\n"
            "#endif\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int x = 2;"

    def test_ifndef_cuando_no_esta_definido(self):
        codigo = (
            "#ifndef REG_BASE\n"
            "#define REG_BASE 0x1000\n"
            "#endif\n"
            "int base = REG_BASE;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int base = 0x1000;"
        assert res.macros["REG_BASE"] == "0x1000"

    def test_condicionales_anidados(self):
        codigo = (
            "#define NIVEL1\n"
            "#define NIVEL2\n"
            "#ifdef NIVEL1\n"
            "    #ifdef NIVEL2\n"
            "    int anidado = 100;\n"
            "    #else\n"
            "    int anidado = 50;\n"
            "    #endif\n"
            "#endif\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int anidado = 100;"

    def test_directivas_dentro_de_rama_inactiva_no_se_ejecutan(self):
        codigo = (
            "#ifdef NO_DEFINIDO\n"
            "#define FALSO_VALOR 999\n"
            "#include <archivo_que_no_existe_y_fallaria.h>\n"
            "#endif\n"
            "int limpio = 1;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int limpio = 1;"
        assert "FALSO_VALOR" not in res.macros

    def test_error_else_sin_ifdef(self):
        codigo = "int a = 1;\n#else\nint b = 2;\n"
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo, nombre_archivo="error.c")
        assert "error.c:2: error:" in str(exc_info.value)
        assert "#else sin directiva condicional previa" in str(exc_info.value)

    def test_error_endif_sin_ifdef(self):
        codigo = "int a = 1;\n#endif\n"
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo, nombre_archivo="error.c")
        assert "error.c:2: error:" in str(exc_info.value)
        assert "#endif sin directiva condicional previa" in str(exc_info.value)

    def test_error_condicional_sin_cerrar(self):
        codigo = (
            "int a = 1;\n"
            "#ifdef PENDIENTE\n"
            "int b = 2;\n"
        )
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo, nombre_archivo="abierto.c")
        assert "abierto.c:2: error:" in str(exc_info.value)
        assert "sin cerrar" in str(exc_info.value)


# 4. Pruebas de Includes y #pragma once

class TestIncludes:
    def test_include_local_en_misma_carpeta(self, tmp_path):
        h_file = tmp_path / "mi_header.h"
        h_file.write_text("#define VAL 42\nint x = VAL;\n", encoding="utf-8")

        main_file = tmp_path / "main.c"
        main_file.write_text('#include "mi_header.h"\nint y = VAL * 2;\n', encoding="utf-8")

        res = preprocesar_archivo(str(main_file))
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "int x = 42;"
        assert lineas[1] == "int y = 42 * 2;"
        assert res.macros["VAL"] == "42"

    def test_include_con_ruta_I(self, tmp_path):
        inc_dir = tmp_path / "lib_include"
        inc_dir.mkdir()
        h_file = inc_dir / "modulo.h"
        h_file.write_text("#define MODULO_VERSION 1\n", encoding="utf-8")

        main_file = tmp_path / "src" / "main.c"
        main_file.parent.mkdir()
        main_file.write_text('<modulo.h>\n#include <modulo.h>\nint v = MODULO_VERSION;\n', encoding="utf-8")
        # Correccion de sintaxis: solo el include
        main_file.write_text('#include <modulo.h>\nint v = MODULO_VERSION;\n', encoding="utf-8")

        res = preprocesar_archivo(str(main_file), dirs_inclusion=[str(inc_dir)])
        assert res.texto.strip() == "int v = 1;"

    def test_include_sistema_spl_include_por_defecto(self):
        # Debe encontrar spl/include/enigma64.h
        codigo = (
            "#include <enigma64.h>\n"
            "int bits = TAM_PALABRA;\n"
            "ENTERO limite = RAM_LIMIT;\n"
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "int bits = 64;"
        assert lineas[1] == "int limite = 0xFFFFFFFF;"

    def test_pragma_once_evita_doble_inclusion(self, tmp_path):
        h_file = tmp_path / "guardado.h"
        h_file.write_text(
            "#pragma once\n"
            "int variable_unica = 1;\n",
            encoding="utf-8",
        )

        main_file = tmp_path / "main.c"
        main_file.write_text(
            '#include "guardado.h"\n'
            '#include "guardado.h"\n',
            encoding="utf-8",
        )

        res = preprocesar_archivo(str(main_file))
        assert res.texto.strip() == "int variable_unica = 1;"

    def test_include_anidado(self, tmp_path):
        h3 = tmp_path / "c.h"
        h3.write_text("#define C_VAL 3\n", encoding="utf-8")

        h2 = tmp_path / "b.h"
        h2.write_text('#include "c.h"\n#define B_VAL 2\n', encoding="utf-8")

        h1 = tmp_path / "a.h"
        h1.write_text('#include "b.h"\n#define A_VAL 1\n', encoding="utf-8")

        main_file = tmp_path / "main.c"
        main_file.write_text('#include "a.h"\nint total = A_VAL + B_VAL + C_VAL;\n', encoding="utf-8")

        res = preprocesar_archivo(str(main_file))
        assert res.texto.strip() == "int total = 1 + 2 + 3;"

    def test_deteccion_de_ciclos_include(self, tmp_path):
        h_a = tmp_path / "a.h"
        h_b = tmp_path / "b.h"

        h_a.write_text('#include "b.h"\n', encoding="utf-8")
        h_b.write_text('#include "a.h"\n', encoding="utf-8")

        main_file = tmp_path / "main.c"
        main_file.write_text('#include "a.h"\n', encoding="utf-8")

        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_archivo(str(main_file))

        err_msg = str(exc_info.value)
        assert ": error:" in err_msg
        assert "ciclo de inclusion detectado:" in err_msg
        assert "a.h -> b.h -> a.h" in err_msg

    def test_error_archivo_no_encontrado(self):
        codigo = '#include "archivo_fantasma_12345.h"\n'
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo, nombre_archivo="origen.c")
        err_msg = str(exc_info.value)
        assert "origen.c:1: error:" in err_msg
        assert "archivo no encontrado: archivo_fantasma_12345.h" in err_msg

    def test_error_limite_profundidad_inclusion(self, tmp_path):
        from spl.preprocesador.motor import Preprocesador

        # Creamos una cadena de archivos h0 -> h1 -> h2 ... -> h5
        for i in range(5):
            (tmp_path / f"h{i}.h").write_text(f'#include "h{i+1}.h"\n', encoding="utf-8")
        (tmp_path / "h5.h").write_text("int base = 0;\n", encoding="utf-8")

        main_file = tmp_path / "main.c"
        main_file.write_text('#include "h0.h"\n', encoding="utf-8")

        # Motor con limite de profundidad 3
        pre = Preprocesador(limite_profundidad=3)
        with pytest.raises(PreprocesadorError) as exc_info:
            pre.procesar_archivo(str(main_file))
        assert "limite de profundidad de inclusion excedido (3)" in str(exc_info.value)


# 5. Pruebas de Mapa de Líneas (mapa_lineas)

class TestMapaLineas:
    def test_mapa_lineas_archivo_simple(self):
        codigo = (
            "#define MAX 10\n"
            "int a = MAX;\n"
            "int b = 20;\n"
        )
        res = preprocesar_texto(codigo, nombre_archivo="prueba.spl")
        lineas = res.texto.splitlines()
        assert len(lineas) == 2
        assert len(res.mapa_lineas) == 2
        assert res.mapa_lineas[0] == ("prueba.spl", 2)
        assert res.mapa_lineas[1] == ("prueba.spl", 3)

    def test_mapa_lineas_con_include(self, tmp_path):
        h_file = tmp_path / "header.h"
        h_file.write_text("int x = 1;\nint y = 2;\n", encoding="utf-8")

        main_file = tmp_path / "main.spl"
        main_file.write_text('#include "header.h"\nint z = 3;\n', encoding="utf-8")

        res = preprocesar_archivo(str(main_file))
        assert len(res.mapa_lineas) == 3
        # Las dos primeras lineas vienen de header.h
        assert res.mapa_lineas[0] == ("header.h", 1)
        assert res.mapa_lineas[1] == ("header.h", 2)
        # La tercera linea viene de main.spl linea 2
        assert res.mapa_lineas[2] == (str(main_file), 2)


# 6. Pruebas de CLI (python -m spl.preprocesador)

class TestCLI:
    def test_cli_salida_stdout(self, tmp_path):
        entrada = tmp_path / "in.c"
        entrada.write_text("#define VALOR 555\nint k = VALOR;\n", encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, "-m", "spl.preprocesador", str(entrada)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == "int k = 555;"

    def test_cli_opcion_o_salida(self, tmp_path):
        entrada = tmp_path / "in.c"
        entrada.write_text("#define MAX 99\nint x = MAX;\n", encoding="utf-8")
        salida = tmp_path / "out.c"

        proc = subprocess.run(
            [sys.executable, "-m", "spl.preprocesador", str(entrada), "-o", str(salida)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert salida.exists()
        assert salida.read_text(encoding="utf-8").strip() == "int x = 99;"

    def test_cli_opciones_D_e_I(self, tmp_path):
        inc_dir = tmp_path / "inc"
        inc_dir.mkdir()
        (inc_dir / "config.h").write_text("#define PUERTO 8080\n", encoding="utf-8")

        entrada = tmp_path / "main.c"
        entrada.write_text(
            '#include <config.h>\n'
            'int p = PUERTO;\n'
            'int n = NIVEL;\n',
            encoding="utf-8",
        )

        proc = subprocess.run(
            [
                sys.executable, "-m", "spl.preprocesador",
                str(entrada),
                "-I", str(inc_dir),
                "-D", "NIVEL=3",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert "int p = 8080;" in proc.stdout
        assert "int n = 3;" in proc.stdout

    def test_cli_define_sin_valor_asigna_uno(self, tmp_path):
        entrada = tmp_path / "main.c"
        entrada.write_text(
            '#ifdef DEBUG\n'
            'int modo = 1;\n'
            '#else\n'
            'int modo = 0;\n'
            '#endif\n',
            encoding="utf-8",
        )

        proc = subprocess.run(
            [
                sys.executable, "-m", "spl.preprocesador",
                str(entrada),
                "-D", "DEBUG",
            ],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == "int modo = 1;"

    def test_cli_error_retorna_codigo_no_cero_y_stderr(self, tmp_path):
        entrada = tmp_path / "error.c"
        entrada.write_text('#include "inexistente.h"\n', encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, "-m", "spl.preprocesador", str(entrada)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        assert "error: archivo no encontrado: inexistente.h" in proc.stderr
