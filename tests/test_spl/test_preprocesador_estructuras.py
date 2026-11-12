"""
Cubre:
1. Inclusión (#include): rutas relativas, desde spl/include/, anidados,
   protección contra doble inclusión (#pragma once e include guards) y
   errores claros (archivo no encontrado, inclusión circular).
2. Macros parametrizadas (#define NOMBRE(a, b) cuerpo): sustitución de parámetros,
   macros de acceso VEC_DIR y MAT_DIR, expresiones en argumentos, anidamiento y
   manejo de errores de aridad.
3. Layout de memoria (layout_datos.inc): direcciones base en >= 0x00201000,
   alineación estricta de 8 bytes (STATUS_READY en RAMMemory), zonas disjuntas
   sin solapamiento y preservación de memoria de programas demo oficiales.
"""

import pytest

from spl.preprocesador import (
    preprocesar_archivo,
    preprocesar_texto,
    PreprocesadorError,
)
from enigma64.memoria import RAMMemory, STATUS_READY


# ==============================================================================
# 1. Pruebas de #include
# ==============================================================================

class TestIncludeEstructuras:
    def test_include_layout_datos_comillas_desde_spl_include(self):
        """Verifica que #include "layout_datos.inc" se resuelva desde spl/include/."""
        codigo = (
            '#include "layout_datos.inc"\n'
            'int base_vec = BASE_VECTORES;\n'
            'int base_mat = BASE_MATRICES;\n'
        )
        res = preprocesar_texto(codigo)
        lineas = [l for l in res.texto.strip().splitlines() if l.strip()]
        assert "int base_vec = 0x00220000;" in lineas
        assert "int base_mat = 0x00260000;" in lineas
        assert "BASE_CABECERAS" in res.macros
        assert "BASE_VECTORES" in res.macros
        assert "BASE_MATRICES" in res.macros
        assert "BASE_BUFFERS" in res.macros

    def test_include_layout_datos_angulares_desde_spl_include(self):
        """Verifica que #include <layout_datos.inc> se resuelva como cabecera de sistema."""
        codigo = (
            '#include <layout_datos.inc>\n'
            'int base_cab = BASE_CABECERAS;\n'
            'int base_buf = BASE_BUFFERS;\n'
        )
        res = preprocesar_texto(codigo)
        lineas = [l for l in res.texto.strip().splitlines() if l.strip()]
        assert "int base_cab = 0x00210000;" in lineas
        assert "int base_buf = 0x002E0000;" in lineas

    def test_include_ruta_relativa_misma_carpeta(self, tmp_path):
        """Verifica inclusión local con ruta relativa en el mismo directorio."""
        inc = tmp_path / "auxiliar.inc"
        inc.write_text("#define FACTOR_ESCALA 8\n", encoding="utf-8")

        main = tmp_path / "programa.spl"
        main.write_text(
            '#include "auxiliar.inc"\n'
            'int tam = 10 * FACTOR_ESCALA;\n',
            encoding="utf-8",
        )
        res = preprocesar_archivo(str(main))
        assert "int tam = 10 * 8;" in res.texto

    def test_include_ruta_relativa_subdirectorio(self, tmp_path):
        """Verifica inclusión con ruta relativa hacia subdirectorios."""
        subdir = tmp_path / "includes_custom"
        subdir.mkdir()
        (subdir / "tipos.inc").write_text("#define WORD 8\n", encoding="utf-8")

        main = tmp_path / "main.spl"
        main.write_text(
            '#include "includes_custom/tipos.inc"\n'
            'int w = WORD;\n',
            encoding="utf-8",
        )
        res = preprocesar_archivo(str(main))
        assert "int w = 8;" in res.texto

    def test_include_anidado_resuelve_correctamente(self, tmp_path):
        """Verifica inclusión en cadena anidada: main -> capa1.inc -> layout_datos.inc."""
        capa1 = tmp_path / "capa1.inc"
        capa1.write_text(
            '#include "layout_datos.inc"\n'
            '#define VEC_INICIAL BASE_VECTORES\n',
            encoding="utf-8",
        )

        main = tmp_path / "main.spl"
        main.write_text(
            '#include "capa1.inc"\n'
            'int ptr = VEC_INICIAL;\n',
            encoding="utf-8",
        )
        res = preprocesar_archivo(str(main))
        assert "int ptr = 0x00220000;" in res.texto

    def test_doble_inclusion_layout_datos_protegida(self):
        """Verifica que incluir layout_datos.inc dos veces no duplique contenido (#pragma once / guardas)."""
        codigo = (
            '#include "layout_datos.inc"\n'
            '#include "layout_datos.inc"\n'
            'int total = BASE_VECTORES;\n'
        )
        res = preprocesar_texto(codigo)
        lineas = [l for l in res.texto.strip().splitlines() if "int total" in l]
        assert len(lineas) == 1
        assert lineas[0] == "int total = 0x00220000;"

    def test_doble_inclusion_include_guards_personalizadas(self, tmp_path):
        """Verifica que la protección por guardas clásicas (#ifndef/#define/#endif) funcione sin duplicar."""
        header = tmp_path / "guardas.inc"
        header.write_text(
            "#ifndef GUARDAS_INC\n"
            "#define GUARDAS_INC\n"
            "int inicializado_una_vez = 1;\n"
            "#endif\n",
            encoding="utf-8",
        )

        main = tmp_path / "main.spl"
        main.write_text(
            '#include "guardas.inc"\n'
            '#include "guardas.inc"\n',
            encoding="utf-8",
        )
        res = preprocesar_archivo(str(main))
        lineas = [l for l in res.texto.strip().splitlines() if "inicializado_una_vez" in l]
        assert len(lineas) == 1
        assert lineas[0] == "int inicializado_una_vez = 1;"

    def test_error_archivo_no_encontrado(self):
        """Verifica error claro cuando se intenta incluir un archivo que no existe."""
        codigo = '#include "archivo_que_no_existe_xyz.inc"\n'
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo)
        mensaje = str(exc_info.value)
        assert ": error:" in mensaje
        assert "archivo no encontrado" in mensaje
        assert "archivo_que_no_existe_xyz.inc" in mensaje

    def test_error_inclusion_circular(self, tmp_path):
        """Verifica detección de ciclo de inclusión y reporte del camino circular."""
        f_a = tmp_path / "circ_a.inc"
        f_b = tmp_path / "circ_b.inc"

        f_a.write_text('#include "circ_b.inc"\n', encoding="utf-8")
        f_b.write_text('#include "circ_a.inc"\n', encoding="utf-8")

        main = tmp_path / "main.spl"
        main.write_text('#include "circ_a.inc"\n', encoding="utf-8")

        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_archivo(str(main))

        mensaje = str(exc_info.value)
        assert ": error:" in mensaje
        assert "ciclo de inclusion detectado" in mensaje
        assert "circ_a.inc -> circ_b.inc -> circ_a.inc" in mensaje

    def test_simulacion_include_estructuras_inc(self, tmp_path):
        """
        Simula la interacción con la futura librería del Integrante 4:
        un archivo estructuras.inc que incluye layout_datos.inc y exporta rutinas.
        """
        estructuras_mock = tmp_path / "estructuras.inc"
        estructuras_mock.write_text(
            '#pragma once\n'
            '#include "layout_datos.inc"\n'
            '#define ESTRUCTURAS_LIB_VERSION 1\n'
            'int base_vec_global = BASE_VECTORES;\n',
            encoding="utf-8",
        )

        main = tmp_path / "consumidor.spl"
        main.write_text(
            '#include "estructuras.inc"\n'
            'int v = ESTRUCTURAS_LIB_VERSION;\n'
            'int dir_el = VEC_DIR(BASE_VECTORES, 2);\n',
            encoding="utf-8",
        )

        res = preprocesar_archivo(str(main))
        assert "int base_vec_global = 0x00220000;" in res.texto
        assert "int v = 1;" in res.texto
        assert "int dir_el = 0x00220000 + (2 << 3);" in res.texto


# ==============================================================================
# 2. Pruebas de Macros Parametrizadas
# ==============================================================================

class TestMacrosParametrizadas:
    def test_macro_parametrizada_un_parametro(self):
        """Prueba una macro clásica con un único argumento: CUADRADO(x)."""
        codigo = (
            "#define CUADRADO(x) ((x) * (x))\n"
            "int c = CUADRADO(5);\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int c = ((5) * (5));"

    def test_macro_parametrizada_multiples_parametros(self):
        """Prueba una macro con múltiples argumentos y operadores aritméticos."""
        codigo = (
            "#define CALC(a, b, c) ((a) * (b) + (c))\n"
            "int res = CALC(2, 3, 4);\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int res = ((2) * (3) + (4));"

    def test_macro_vec_dir_definicion_y_expansion(self):
        """Verifica la macro requerida VEC_DIR(base, i) = base + (i << 3)."""
        codigo = (
            "#define VEC_DIR(base, i) base + (i << 3)\n"
            "int dir = VEC_DIR(0x00220000, 4);\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int dir = 0x00220000 + (4 << 3);"

    def test_macro_vec_dir_con_registros_ensamblador(self):
        """Verifica el uso de VEC_DIR en sintaxis de ensamblador Enigma-64."""
        codigo = (
            '#include "layout_datos.inc"\n'
            "LOAD R2, [VEC_DIR(R1, R3)]\n"
        )
        res = preprocesar_texto(codigo)
        assert "LOAD R2, [R1 + (R3 << 3)]" in res.texto

    def test_macro_mat_dir_definicion_y_expansion(self):
        """Verifica la macro requerida MAT_DIR(base, cols, i, j) = base + ((i * cols + j) << 3)."""
        codigo = (
            "#define MAT_DIR(base, cols, i, j) base + ((i * cols + j) << 3)\n"
            "int celda = MAT_DIR(0x00260000, 10, 2, 5);\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int celda = 0x00260000 + ((2 * 10 + 5) << 3);"

    def test_macro_mat_dir_con_registros_ensamblador(self):
        """Verifica el uso de MAT_DIR en sintaxis de ensamblador Enigma-64."""
        codigo = (
            '#include "layout_datos.inc"\n'
            "STORE R4, [MAT_DIR(R1, 8, R2, R3)]\n"
        )
        res = preprocesar_texto(codigo)
        assert "STORE R4, [R1 + ((R2 * 8 + R3) << 3)]" in res.texto

    def test_macro_con_expresiones_complejas_en_argumentos(self):
        """Verifica que los argumentos conteniendo paréntesis u operadores no rompan la expansión."""
        codigo = (
            '#include "layout_datos.inc"\n'
            "int a = VEC_DIR(R1 + 16, (R2 * 2));\n"
            "int b = MAT_DIR(R1, (COLS + 1), i + 1, (j << 1));\n"
        )
        res = preprocesar_texto(codigo, definiciones={"COLS": "4"})
        lineas = [l for l in res.texto.strip().splitlines() if l.strip()]
        assert "int a = R1 + 16 + ((R2 * 2) << 3);" in lineas
        assert "int b = R1 + ((i + 1 * (4 + 1) + (j << 1)) << 3);" in lineas

    def test_macros_parametrizadas_anidadas(self):
        """Verifica llamadas anidadas: una macro como argumento de otra."""
        codigo = (
            "#define SUM(x, y) ((x) + (y))\n"
            "#define VEC_DIR(base, i) base + (i << 3)\n"
            "int pos = VEC_DIR(R1, SUM(2, 3));\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int pos = R1 + (((2) + (3)) << 3);"

    def test_macro_parametrizada_sin_parentesis_no_se_expande(self):
        """
        Conforme a la norma C, el identificador de una macro parametrizada que aparezca
        sin paréntesis '(' de invocación no debe ser reemplazado.
        """
        codigo = (
            "#define VEC_DIR(base, i) base + (i << 3)\n"
            "int VEC_DIR = 100;\n"
            "int test = VEC_DIR;\n"
        )
        res = preprocesar_texto(codigo)
        lineas = res.texto.strip().splitlines()
        assert lineas[0] == "int VEC_DIR = 100;"
        assert lineas[1] == "int test = VEC_DIR;"

    def test_macro_con_espacio_despues_de_nombre_es_objeto(self):
        """
        En C, '#define FOO (a, b)' con espacio antes de '(' es una macro objeto
        cuyo valor es '(a, b)', no una macro función con parámetros.
        """
        codigo = (
            "#define OBJETO (a, b)\n"
            "int tupla = OBJETO;\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int tupla = (a, b);"
        assert not getattr(res.macros["OBJETO"], "es_parametrizada", False)

    def test_error_aridad_insuficiente(self):
        """Verifica que invocar una macro con menos argumentos de los esperados lance error."""
        codigo = (
            "#define VEC_DIR(base, i) base + (i << 3)\n"
            "int p = VEC_DIR(R1);\n"
        )
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo)
        mensaje = str(exc_info.value)
        assert "macro 'VEC_DIR' esperaba 2 argumentos, pero recibio 1" in mensaje

    def test_error_aridad_sobrante(self):
        """Verifica que invocar una macro con más argumentos de los esperados lance error."""
        codigo = (
            "#define VEC_DIR(base, i) base + (i << 3)\n"
            "int p = VEC_DIR(R1, R2, R3);\n"
        )
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo)
        mensaje = str(exc_info.value)
        assert "macro 'VEC_DIR' esperaba 2 argumentos, pero recibio 3" in mensaje

    def test_error_parametro_duplicado_en_define(self):
        """Verifica error si se define una macro con parámetros duplicados."""
        codigo = "#define MALO(x, x) (x + x)\n"
        with pytest.raises(PreprocesadorError) as exc_info:
            preprocesar_texto(codigo)
        assert "parametro duplicado 'x' en #define" in str(exc_info.value)

    def test_undef_macro_parametrizada(self):
        """Verifica que #undef desactive la macro parametrizada."""
        codigo = (
            "#define VEC_DIR(base, i) base + (i << 3)\n"
            "#undef VEC_DIR\n"
            "int x = VEC_DIR(R1, 2);\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int x = VEC_DIR(R1, 2);"
        assert "VEC_DIR" not in res.macros

    def test_ifdef_con_macro_parametrizada(self):
        """Verifica que #ifdef y #ifndef reconozcan macros parametrizadas como definidas."""
        codigo = (
            "#define VEC_DIR(base, i) base + (i << 3)\n"
            "#ifdef VEC_DIR\n"
            "int vec_activo = 1;\n"
            "#else\n"
            "int vec_activo = 0;\n"
            "#endif\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.strip() == "int vec_activo = 1;"


# ==============================================================================
# 3. Pruebas de Layout de Memoria (layout_datos.inc)
# ==============================================================================

class TestLayoutMemoria:
    @pytest.fixture(autouse=True)
    def cargar_layout(self):
        """Preprocesa layout_datos.inc para extraer las constantes evaluadas."""
        codigo = '#include "layout_datos.inc"\n'
        res = preprocesar_texto(codigo)
        self.macros = res.macros

        # Extraer direcciones base como enteros
        self.base_cab = int(self.macros["BASE_CABECERAS"], 0)
        self.tam_cab = int(self.macros["TAM_CABECERAS"], 0)
        self.lim_cab = int(self.macros["LIMITE_CABECERAS"], 0)

        self.base_vec = int(self.macros["BASE_VECTORES"], 0)
        self.tam_vec = int(self.macros["TAM_VECTORES"], 0)
        self.lim_vec = int(self.macros["LIMITE_VECTORES"], 0)

        self.base_mat = int(self.macros["BASE_MATRICES"], 0)
        self.tam_mat = int(self.macros["TAM_MATRICES"], 0)
        self.lim_mat = int(self.macros["LIMITE_MATRICES"], 0)

        self.base_buf = int(self.macros["BASE_BUFFERS"], 0)
        self.tam_buf = int(self.macros["TAM_BUFFERS"], 0)
        self.lim_buf = int(self.macros["LIMITE_BUFFERS"], 0)

    def test_direcciones_base_mayores_o_iguales_a_0x00201000(self):
        """Garantiza que toda la región de datos de estructuras esté en >= 0x00201000."""
        min_datos = 0x00201000
        assert self.base_cab >= min_datos, f"Cabeceras (0x{self.base_cab:08X}) < 0x00201000"
        assert self.base_vec >= min_datos, f"Vectores (0x{self.base_vec:08X}) < 0x00201000"
        assert self.base_mat >= min_datos, f"Matrices (0x{self.base_mat:08X}) < 0x00201000"
        assert self.base_buf >= min_datos, f"Buffers (0x{self.base_buf:08X}) < 0x00201000"

    def test_alineacion_estricta_multiplo_de_8(self):
        """Garantiza que todas las direcciones base y límites sean múltiplos exactos de 8 bytes."""
        for nombre, direccion in [
            ("BASE_CABECERAS", self.base_cab),
            ("TAM_CABECERAS", self.tam_cab),
            ("LIMITE_CABECERAS", self.lim_cab),
            ("BASE_VECTORES", self.base_vec),
            ("TAM_VECTORES", self.tam_vec),
            ("LIMITE_VECTORES", self.lim_vec),
            ("BASE_MATRICES", self.base_mat),
            ("TAM_MATRICES", self.tam_mat),
            ("LIMITE_MATRICES", self.lim_mat),
            ("BASE_BUFFERS", self.base_buf),
            ("TAM_BUFFERS", self.tam_buf),
            ("LIMITE_BUFFERS", self.lim_buf),
        ]:
            assert direccion % 8 == 0, f"{nombre} (0x{direccion:08X}) no es múltiplo de 8"

    def test_zonas_disjuntas_sin_solapamiento(self):
        """Verifica que las 4 zonas del mapa de memoria sean mutuamente excluyentes."""
        zonas = [
            ("Cabeceras", self.base_cab, self.base_cab + self.tam_cab),
            ("Vectores", self.base_vec, self.base_vec + self.tam_vec),
            ("Matrices", self.base_mat, self.base_mat + self.tam_mat),
            ("Buffers", self.base_buf, self.base_buf + self.tam_buf),
        ]

        # Verificar coherencia interna base + tam <= limite
        assert self.base_cab + self.tam_cab <= self.lim_cab
        assert self.base_vec + self.tam_vec <= self.lim_vec
        assert self.base_mat + self.tam_mat <= self.lim_mat
        assert self.base_buf + self.tam_buf <= self.lim_buf

        # Verificar no solapamiento por pares
        for i in range(len(zonas)):
            nom_i, ini_i, fin_i = zonas[i]
            for j in range(i + 1, len(zonas)):
                nom_j, ini_j, fin_j = zonas[j]
                solapamiento = max(0, min(fin_i, fin_j) - max(ini_i, ini_j))
                assert solapamiento == 0, (
                    f"Solapamiento detectado entre {nom_i} [0x{ini_i:08X}, 0x{fin_i:08X}) "
                    f"y {nom_j} [0x{ini_j:08X}, 0x{fin_j:08X})"
                )

    def test_no_pisa_programas_demo_oficiales(self):
        """
        Garantiza que la región de estructuras no solape con las áreas de datos
        ni con la memoria utilizada por los programas demo en programas/:
          - Factorial:  Código 0x00200000, Datos 0x00201000 - 0x00201008
          - Euclides:   Código 0x00200100, Datos 0x00202000 - 0x00202010
          - Fibonacci:  Código 0x00200200, Datos 0x00203000 - 0x00203038
          - Brun:       Pila SP 0x00204000, Datos 0x00205000 - 0x00205020
        """
        direcciones_criticas_demos = [
            # Factorial
            (0x00200000, 41, "Factorial (Código)"),
            (0x00201000, 16, "Factorial (Datos N y resultado)"),
            # Euclides
            (0x00200100, 50, "Euclides (Código)"),
            (0x00202000, 24, "Euclides (Datos A, B y MCD)"),
            # Fibonacci
            (0x00200200, 63, "Fibonacci (Código)"),
            (0x00203000, 56, "Fibonacci (Arreglo F0-F6)"),
            # Brun
            (0x00204000, 0,  "Brun (Pila descendente SP)"),
            (0x00205000, 32, "Brun (Variables de entrada y salida)"),
        ]

        inicio_region_estructuras = min(self.base_cab, self.base_vec, self.base_mat, self.base_buf)
        fin_region_estructuras = max(self.lim_cab, self.lim_vec, self.lim_mat, self.lim_buf)

        for dir_demo, tam, nombre_demo in direcciones_criticas_demos:
            fin_demo = dir_demo + max(tam, 8)
            solapamiento = max(0, min(fin_demo, fin_region_estructuras) - max(dir_demo, inicio_region_estructuras))
            assert solapamiento == 0, (
                f"Conflicto con programa demo '{nombre_demo}': "
                f"[0x{dir_demo:08X}, 0x{fin_demo:08X}) solapa con estructuras "
                f"[0x{inicio_region_estructuras:08X}, 0x{fin_region_estructuras:08X})"
            )

    def test_alineacion_memoria_enigma_status_ready(self):
        """
        Valida contra el subsistema de hardware real de Enigma-64 (RAMMemory)
        que los accesos de palabra de 64 bits (8 bytes) en las direcciones base
        retornen STATUS_READY ('READY') sin generar bandera de desalineación MISALIGNED.
        """
        ram = RAMMemory()
        test_data = 0x0123456789ABCDEF

        for nombre_base, dir_base in [
            ("BASE_CABECERAS", self.base_cab),
            ("BASE_VECTORES", self.base_vec),
            ("BASE_MATRICES", self.base_mat),
            ("BASE_BUFFERS", self.base_buf),
        ]:
            # Escritura de 64 bits (8 bytes) con control de alineación
            _, estado = ram.mem_write(dir_base, test_data, size_bytes=8, check_alignment=True)
            assert estado == STATUS_READY, (
                f"Fallo de alineacion al escribir en {nombre_base} (0x{dir_base:08X}): {estado}"
            )

            # Lectura de 64 bits (8 bytes) con control de alineación
            leido, estado_lectura = ram.mem_read(dir_base, size_bytes=8, check_alignment=True)
            assert estado_lectura == STATUS_READY, (
                f"Fallo de alineacion al leer en {nombre_base} (0x{dir_base:08X}): {estado_lectura}"
            )
            assert leido == test_data, f"Dato corrupto en {nombre_base}: leido {leido} != esperado {test_data}"

    def test_acceso_desalineado_falla_como_esperado(self):
        """
        Verificación complementaria: confirma que RAMMemory rechaza accesos desalineados
        (por ejemplo, dirección impar o no múltiplo de 8) devolviendo MISALIGNED.
        """
        ram = RAMMemory()
        direccion_desalineada = self.base_vec + 3  # Offset impar
        _, estado = ram.mem_write(direccion_desalineada, 0x5555, size_bytes=8, check_alignment=True)
        assert estado == "MISALIGNED", f"Se esperaba MISALIGNED pero se obtuvo {estado}"
