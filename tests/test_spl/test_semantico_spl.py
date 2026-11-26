"""
Suite de pruebas unitarias e integrales del Analizador Semántico del Compilador SPL.
Fase 2: Análisis Semántico (Taller 02, Literales b, d y e - Integrante 4).

Cubre:
1. Integración real Lexer (ajustado Literal b) -> Parser (Int. 2 y 3) -> Semántico (Int. 4).
2. Ámbitos léxicos, redeclaración, ocultamiento (shadowing) y colisión global función/variable.
3. Tipos de Datos Abstractos (struct / tda): offsets relativos alineados a 8 B, matrices dentro
   de TDA (MatrizTransformacion = 168 B, RegistroSensor = 40 B), TDA anidados y recursión por valor.
4. Alias typedef: expansión, composición de dimensiones a la derecha y límite de 2 dimensiones.
5. Variables escalares, vectores 1D y matrices 2D: dimensiones constantes, inferencia de
   dimensión abierta, const inmutable, offsets globales (base 0x00201000) y locales ([BP - k]).
6. Funciones, prototipos, main(), parámetros por valor/referencia, return y ENTER tam_locales.
7. Control de flujo: if/then/else, switch (constantes negativas y duplicadas), while, do-while,
   for con ámbito propio, break y continue dentro/fuera de contexto.
8. Expresiones de 13 niveles, operadores de bits/asignación compuesta/++/--, coerción automática
   int -> float IEEE 754 (CoercionTipo), rechazo float -> int, lvalue y sizeof.
9. Escenarios integrales reales del Taller 01 y los 5 algoritmos tipo Taller 02 (Euclides,
   Newton-Raphson IEEE 754, vectores/búsqueda, matrices 2D y TDA con switch-case).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spl.compilador import (
    BASE_DATOS_GLOBAL,
    AnalizadorSemantico,
    CompiladorParser,
    DescriptorCampo,
    DescriptorTipoTDA,
    ErrorSemantico,
    FirmaFuncion,
    ResultadoSemantico,
    SimboloVariable,
)
from spl.compilador.ast_nodos import (
    AccesoCampo,
    Asignacion,
    CoercionTipo,
    DeclaracionVariable,
    DefinicionFuncion,
    DefinicionTDA,
    ExpresionBinaria,
    ListaInicializadores,
    LlamadaFuncion,
    SentenciaReturn,
    Sizeof,
)
from spl.preprocesador.motor import preprocesar_archivo

RAIZ = Path(__file__).resolve().parents[2]
EJEMPLOS_COMP = RAIZ / "spl" / "compilador" / "ejemplos"
EJEMPLOS_PIPE = RAIZ / "spl" / "ejemplos"


def analizar(codigo: str, *, exigir_main: bool = False) -> ResultadoSemantico:
    """Helper que pasa el código por Lexer + Parser reales y luego por AnalizadorSemantico."""
    parser = CompiladorParser()
    ast, err_sint = parser.analizar(codigo)
    assert not parser.errores_lexicos, f"Errores lexicos inesperados: {parser.errores_lexicos}"
    assert not err_sint, f"Errores sintacticos inesperados: {err_sint}"
    sem = AnalizadorSemantico(tablas_lexicas=parser.tablas, exigir_main=exigir_main)
    return sem.analizar(ast)


# ===========================================================================
# 1. Programa, main y prototipos
# ===========================================================================

class TestProgramaYPrototipos:
    def test_exige_main_por_defecto(self):
        res = analizar("int x = 1;", exigir_main=True)
        assert not res.exito
        assert any("main" in e.mensaje for e in res.errores)

    def test_main_con_parametros_es_error(self):
        res = analizar("int main(int argc) { return 0; }", exigir_main=True)
        assert not res.exito
        assert any("main" in e.mensaje and "parametros" in e.mensaje for e in res.errores)

    def test_main_valido_sin_parametros(self):
        res = analizar("function int main() { return 0; }", exigir_main=True)
        assert res.exito
        assert "main" in res.tabla.funciones
        assert res.tabla.funciones["main"].definida is True

    def test_prototipo_sin_definicion_es_error(self):
        res = analizar("int sumar(int, int); int main() { return 0; }", exigir_main=True)
        assert not res.exito
        assert any("nunca definida" in e.mensaje for e in res.errores)

    def test_prototipo_y_definicion_compatibles(self):
        codigo = """
        int mcd(int, int);
        int main() { return mcd(48, 18); }
        int mcd(int a, int b) {
            while (b != 0) {
                int r = a % b;
                a = b;
                b = r;
            }
            return a;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores

    def test_prototipo_incompatible_con_definicion(self):
        codigo = """
        int f(int a);
        float f(int a) { return 1.0; }
        """
        res = analizar(codigo)
        assert not res.exito
        assert any("incompatible" in e.mensaje for e in res.errores)

    def test_funcion_redefinida_es_error(self):
        codigo = """
        int f() { return 1; }
        int f() { return 2; }
        """
        res = analizar(codigo)
        assert not res.exito
        assert any("redefinida" in e.mensaje for e in res.errores)

    def test_colision_variable_global_y_funcion(self):
        res1 = analizar("int x = 1; int x() { return 0; }")
        assert not res1.exito
        assert any("colisiona" in e.mensaje for e in res1.errores)

        res2 = analizar("int x() { return 0; } int x = 1;")
        assert not res2.exito
        assert any("funcion global" in e.mensaje for e in res2.errores)


# ===========================================================================
# 2. Tipos de Datos Abstractos (struct / tda) y Layouts a 8 bytes
# ===========================================================================

class TestTiposDatosAbstractos:
    def test_layout_registro_sensor_40_bytes(self):
        """Valida el layout exacto del TDA del Programa 5 del taller (40 bytes)."""
        codigo = """
        tda RegistroSensor {
            int id;
            int modo;
            float lectura;
            float escala;
            float resultado;
        };
        """
        res = analizar(codigo)
        assert res.exito
        desc = res.tabla.tipos["RegistroSensor"]
        assert isinstance(desc, DescriptorTipoTDA)
        assert desc.tamano_bytes == 40
        assert desc.offset("id") == 0
        assert desc.offset("modo") == 8
        assert desc.offset("lectura") == 16
        assert desc.offset("escala") == 24
        assert desc.offset("resultado") == 32
        assert all(c.offset % 8 == 0 for c in desc.campos)

    def test_layout_matriz_transformacion_168_bytes(self):
        """Valida el layout con matriz embebida (cabecera +0/+8, datos +16, resto desde +144)."""
        codigo = """
        tda MatrizTransformacion {
            float datos[4][4];
            int filas;
            int columnas;
            bool normalizada;
        };
        """
        res = analizar(codigo)
        assert res.exito
        desc = res.tabla.tipos["MatrizTransformacion"]
        assert desc.tamano_bytes == 168
        campo_datos = desc.obtener_campo("datos")
        assert campo_datos is not None
        assert campo_datos.offset_cabecera == 0
        assert campo_datos.offset == 16
        assert campo_datos.tamano_bytes == 144
        assert desc.offset("filas") == 144
        assert desc.offset("columnas") == 152
        assert desc.offset("normalizada") == 160

    def test_struct_y_tda_son_sinonimos(self):
        codigo = """
        struct Punto { float x; float y; };
        int main() {
            tda Punto p;
            struct Punto q;
            p.x = 1.0;
            p.y = 2.5;
            q = p;
            return 0;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores

    def test_tda_anidado_suma_tamanos(self):
        codigo = """
        struct Vec2 { float x; float y; };
        tda Rect { struct Vec2 origen; struct Vec2 tam; int id; };
        """
        res = analizar(codigo)
        assert res.exito
        rect = res.tabla.tipos["Rect"]
        assert rect.tamano_bytes == 40
        assert rect.offset("origen") == 0
        assert rect.offset("tam") == 16
        assert rect.offset("id") == 32

    def test_tda_redefinido_es_error(self):
        res = analizar("struct A { int x; }; tda A { float y; };")
        assert not res.exito
        assert any("redefinido" in e.mensaje for e in res.errores)

    def test_tda_recursivo_por_valor_es_error(self):
        res = analizar("struct Nodo { int val; struct Nodo sig; };")
        assert not res.exito
        assert any("recursivo" in e.mensaje for e in res.errores)

    def test_tda_campo_duplicado_y_campo_void(self):
        res = analizar("struct Mal { int x; float x; void v; };")
        assert not res.exito
        assert any("duplicado" in e.mensaje for e in res.errores)
        assert any("void" in e.mensaje for e in res.errores)

    def test_tda_no_declarado_y_campo_inexistente(self):
        res = analizar("""
        struct P { int x; };
        int main() {
            struct NoExiste a;
            struct P p;
            p.z = 1;
            return 0;
        }
        """)
        assert not res.exito
        assert any("TDA no declarado" in e.mensaje for e in res.errores)
        assert any("no tiene un campo llamado 'z'" in e.mensaje for e in res.errores)

    def test_acceso_campo_anota_descriptor_con_offset(self):
        codigo = """
        struct P { int a; float b; };
        int main() {
            struct P p;
            p.b = 3.5;
            return 0;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito
        accesos = [n for n in res.ast.recorrer() if isinstance(n, AccesoCampo)]
        assert len(accesos) == 1
        assert accesos[0].tipo_inferido == "float"
        assert isinstance(accesos[0].simbolo, DescriptorCampo)
        assert accesos[0].simbolo.offset == 8


# ===========================================================================
# 3. Alias typedef y composición de dimensiones
# ===========================================================================

class TestTypedef:
    def test_typedef_simple_y_compuesto(self):
        codigo = """
        typedef float Real;
        typedef int Vec4[4];
        int main() {
            Real r = 2;
            Vec4 m[3];
            m[2][3] = 99;
            return m[2][3];
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        fn_main = res.tabla.funciones["main"]
        sim_m = next(s for s in fn_main.simbolos_locales if s.nombre == "m")
        assert sim_m.tipo.dimensiones == (3, 4)
        assert sim_m.tamano_bytes == 16 + 3 * 4 * 8

    def test_typedef_mas_de_dos_dimensiones_es_error(self):
        codigo = """
        typedef int Mat[2][2];
        Mat cubo[2];
        """
        res = analizar(codigo)
        assert not res.exito
        assert any("vectores 1D y matrices 2D" in e.mensaje for e in res.errores)

    def test_typedef_colision_con_tda_y_redefinicion_ast(self):
        # Colisión entre nombre de TDA y alias typedef
        res = analizar("struct Punto { int x; }; typedef int Punto;")
        assert not res.exito
        assert any("redefinido" in e.mensaje for e in res.errores)

        # Redefinición directa en AST (en texto plano el parser ya rechaza el 2.º TIPO_ID)
        from spl.compilador.ast_nodos import DefinicionTypedef, EspecificadorTipo, ProgramaAST
        ast = ProgramaAST(declaraciones=[
            DefinicionTypedef(tipo=EspecificadorTipo("int"), nombre="Entero", linea=1, columna=1),
            DefinicionTypedef(tipo=EspecificadorTipo("float"), nombre="Entero", linea=2, columna=1),
        ])
        res2 = AnalizadorSemantico(exigir_main=False).analizar(ast)
        assert not res2.exito
        assert any("redefinido" in e.mensaje for e in res2.errores)


# ===========================================================================
# 4. Variables, Ámbitos, Const, Arreglos 1D, Matrices 2D y Offsets Relativos
# ===========================================================================

class TestVariablesAmbitosYMemoria:
    def test_offsets_globales_relativos_a_0x00201000(self):
        codigo = """
        int a = 1;
        float b = 2.0;
        int v[4];
        int m[2][3];
        """
        res = analizar(codigo)
        assert res.exito
        glob = {s.nombre: s for s in res.tabla.globales_ordenados}
        assert glob["a"].ubicacion == "global"
        assert glob["a"].base_relativa == f"0x{BASE_DATOS_GLOBAL:08X}"
        assert glob["a"].desplazamiento == 0
        assert glob["a"].direccion_absoluta == BASE_DATOS_GLOBAL
        assert glob["b"].desplazamiento == 8
        assert glob["v"].desplazamiento == 16
        assert glob["v"].tamano_bytes == 32
        # Matriz empieza en offset 48 (cabecera en 48 y 56, datos en 64)
        assert glob["m"].offset_cabecera == 48
        assert glob["m"].desplazamiento == 64
        assert glob["m"].tamano_bytes == 16 + 2 * 3 * 8
        assert res.tabla.tamano_datos_globales == 48 + 64
        assert res.tabla.tamano_datos_globales % 8 == 0

    def test_offsets_locales_relativos_a_bp_y_tam_locales(self):
        """Verifica [BP - 64] para vector datos[8] y ENTER tam_locales."""
        codigo = """
        int main() {
            int datos[8] = {42, 15, 8, 99, 23, 4, 16, 50};
            int i = 0;
            return datos[i];
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        fn_main = res.tabla.funciones["main"]
        locs = {s.nombre: s for s in fn_main.simbolos_locales}
        assert locs["datos"].ubicacion == "local"
        assert locs["datos"].base_relativa == "R7/BP"
        assert locs["datos"].desplazamiento == -64
        assert locs["i"].desplazamiento == -72
        assert fn_main.tam_locales == 72

    def test_dimension_abierta_inferida_en_1d_y_2d(self):
        codigo = """
        int v[] = {10, 20, 30};
        int m[][2] = {{1, 2}, {3, 4}, {5, 6}};
        """
        res = analizar(codigo)
        assert res.exito, res.errores
        glob = {s.nombre: s for s in res.tabla.globales_ordenados}
        assert glob["v"].tipo.dimensiones == (3,)
        assert glob["m"].tipo.dimensiones == (3, 2)

    def test_dimension_abierta_sin_inicializador_es_error(self):
        res = analizar("int v[];")
        assert not res.exito
        assert any("abierta" in e.mensaje for e in res.errores)

    def test_dimension_no_constante_o_no_positiva_es_error(self):
        res = analizar("int n = 5; int a[n]; int b[0]; int c[-3];")
        assert not res.exito
        assert len(res.errores) >= 3

    def test_const_global_en_dimension_y_prohibicion_de_modificar(self):
        codigo = """
        const int N = 4;
        int v[N];
        int main() {
            N = 5;
            return v[0];
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert not res.exito
        assert any("constante 'N'" in e.mensaje for e in res.errores)

    def test_const_sin_inicializador_es_error(self):
        res = analizar("const int K;")
        assert not res.exito
        assert any("inicializador" in e.mensaje for e in res.errores)

    def test_redeclaracion_mismo_ambito_y_shadowing_valido(self):
        codigo_ok = """
        int x = 1;
        int main() {
            int x = 2;
            {
                float x = 3.5;
                x += 1;
            }
            return x;
        }
        """
        assert analizar(codigo_ok, exigir_main=True).exito

        codigo_mal = "int main() { int a = 1; int a = 2; return a; }"
        res_mal = analizar(codigo_mal, exigir_main=True)
        assert not res_mal.exito
        assert any("redeclarada" in e.mensaje for e in res_mal.errores)

    def test_variable_no_declarada_y_exceso_inicializadores(self):
        res = analizar("""
        int main() {
            int v[2] = {1, 2, 3};
            return no_existe + v[0];
        }
        """)
        assert not res.exito
        assert any("demasiados elementos" in e.mensaje for e in res.errores)
        assert any("no declarada" in e.mensaje for e in res.errores)


# ===========================================================================
# 5. Coerción Automática IEEE 754 (int -> float) y Reglas de Tipos
# ===========================================================================

class TestTiposYCoercionIEEE754:
    def test_coercion_int_a_float_en_expresion_binaria(self):
        codigo = """
        int main() {
            int n = 5;
            float r = n + 2.5;
            return 0;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        binarias = [n for n in res.ast.recorrer() if isinstance(n, ExpresionBinaria)]
        assert len(binarias) == 1
        assert binarias[0].tipo_inferido == "float"
        assert isinstance(binarias[0].izquierda, CoercionTipo)
        assert binarias[0].izquierda.origen == "int"
        assert binarias[0].izquierda.destino == "float"

    def test_coercion_en_inicializacion_asignacion_argumento_y_return(self):
        codigo = """
        float doble(float x) {
            float y = 2;
            y += 1;
            if (y > 2) {
                return 3;
            }
            return x * y;
        }
        int main() {
            float r = doble(10);
            return 0;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        coerciones = [n for n in res.ast.recorrer() if isinstance(n, CoercionTipo)]
        # 2 -> float, 1 -> float (en +=), 2 -> float (en y > 2), 3 -> float (en return), 10 -> float (en doble(10))
        assert len(coerciones) == 5
        assert all(c.origen == "int" and c.destino == "float" and c.tipo_inferido == "float" for c in coerciones)

    def test_float_a_int_implicito_es_error(self):
        codigo = """
        int main() {
            int a = 3.14;
            int b = 1;
            b = 2.5;
            b += 0.5;
            return a;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert not res.exito
        assert len(res.errores) >= 3

    def test_modulo_y_operadores_bit_sobre_float_son_error(self):
        codigo = """
        int main() {
            float x = 5.0;
            int a = x % 2;
            int b = x & 1;
            int c = x << 1;
            int d = ~x;
            return a + b + c + d;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert not res.exito
        assert len(res.errores) >= 4

    def test_operadores_de_13_niveles_validos(self):
        codigo = """
        int main() {
            int a = 12, b = 5;
            int r = ((a << 2) | (b & 3) ^ (~a)) >> 1;
            bool ok = (a >= b) && (r != 0) || !(a == 0);
            a++;
            b--;
            a += 3;
            a &= 0xFF;
            a <<= 1;
            return ok ? 0 : 0;
        }
        """
        # Nota: SPL no tiene operador ternario '?:'; usamos if/else
        codigo = """
        int main() {
            int a = 12, b = 5;
            int r = (((a << 2) | (b & 3)) ^ (~a)) >> 1;
            bool ok = (a >= b) && (r != 0) || !(a == 0);
            a++;
            b--;
            a += 3;
            a &= 0xFF;
            a <<= 1;
            if (ok) return r;
            return 0;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores

    def test_sizeof_tipo_y_expresion_y_tda(self):
        codigo = """
        tda Par { int a; float b; };
        int main() {
            int s1 = sizeof(int);
            int s2 = sizeof(struct Par);
            int m[2][3];
            int s3 = sizeof(m);
            return s1 + s2 + s3;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        sizeofs = [n for n in res.ast.recorrer() if isinstance(n, Sizeof)]
        assert [s.simbolo for s in sizeofs] == [8, 16, 16 + 2 * 3 * 8]
        assert all(s.tipo_inferido == "int" for s in sizeofs)

    def test_lvalue_invalido_y_asignacion_arreglo_completo(self):
        codigo = """
        int f() { return 1; }
        int main() {
            int a[2], b[2];
            5 = 3;
            f() = 2;
            a = b;
            (1 + 2)++;
            return 0;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert not res.exito
        assert len(res.errores) >= 4

    def test_indice_no_entero_e_indexacion_escalar(self):
        codigo = """
        int main() {
            int v[4];
            int x = 1;
            int a = v[1.5];
            int b = x[0];
            return a + b;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert not res.exito
        assert any("indice" in e.mensaje for e in res.errores)
        assert any("no se puede indexar" in e.mensaje for e in res.errores)


# ===========================================================================
# 6. Control de Flujo, Switch, Break/Continue y Funciones
# ===========================================================================

class TestControlDeFlujoYFunciones:
    def test_switch_casos_validos_con_negativo_y_duplicados(self):
        codigo_ok = """
        int main() {
            int op = -1;
            int r = 0;
            switch (op) {
                case -1: r = 10; break;
                case 0: r = 20; break;
                case 1: r = 30; break;
                default: r = 40; break;
            }
            return r;
        }
        """
        assert analizar(codigo_ok, exigir_main=True).exito

        codigo_dup = """
        int main() {
            int x = 1;
            switch (x) {
                case 1: break;
                case 1: break;
            }
            return 0;
        }
        """
        res_dup = analizar(codigo_dup, exigir_main=True)
        assert not res_dup.exito
        assert any("duplicada" in e.mensaje for e in res_dup.errores)

    def test_switch_con_float_es_error(self):
        res = analizar("int main() { float x = 1.0; switch (x) { case 1: break; } return 0; }")
        assert not res.exito
        assert any("switch" in e.mensaje for e in res.errores)

    def test_break_y_continue_fuera_de_contexto(self):
        res = analizar("""
        int main() {
            break;
            continue;
            switch (1) {
                case 1:
                    continue;
                    break;
            }
            return 0;
        }
        """)
        assert not res.exito
        assert len(res.errores) == 3

    def test_for_ambito_propio_y_do_while(self):
        codigo = """
        int main() {
            int suma = 0;
            for (int i = 0; i < 5; i++) {
                if (i == 2) continue;
                suma += i;
            }
            int i = 100;
            do {
                i--;
            } while (i > 95);
            return suma + i;
        }
        """
        assert analizar(codigo, exigir_main=True).exito

    def test_return_faltante_y_return_en_void(self):
        res = analizar("""
        int sin_return() { int x = 1; }
        void con_valor() { return 5; }
        int main() { return 0; }
        """)
        assert not res.exito
        assert any("debe retornar un valor" in e.mensaje for e in res.errores)
        assert any("void" in e.mensaje and "retornar" in e.mensaje for e in res.errores)

    def test_parametros_por_referencia_y_mas_de_4_parametros(self):
        codigo = """
        struct S { int k; };
        int procesar(int a, int b, int c, int d, int e, int v[], int m[][2], struct S s) {
            return a + b + c + d + e + v[0] + m[0][1] + s.k;
        }
        int main() {
            int vec[3] = {1, 2, 3};
            int mat[2][2] = {{1, 2}, {3, 4}};
            struct S obj;
            obj.k = 9;
            return procesar(1, 2, 3, 4, 5, vec, mat, obj);
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        fn = res.tabla.funciones["procesar"]
        params = {p.nombre: p for p in fn.simbolos_parametros}
        assert params["a"].base_relativa == "R1..R4" and params["a"].desplazamiento == 0
        assert params["d"].base_relativa == "R1..R4" and params["d"].desplazamiento == 3
        assert params["e"].base_relativa == "R7/BP" and params["e"].desplazamiento == 16
        assert params["v"].por_referencia is True
        assert params["m"].por_referencia is True
        assert params["s"].por_referencia is True

    def test_llamada_aridad_y_dimension_matriz_invalida(self):
        codigo = """
        int f(int m[][4]) { return m[0][0]; }
        int main() {
            int mala[2][3];
            int x = f(mala);
            int y = f();
            return x + y;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert not res.exito
        assert any("dimension incompatible" in e.mensaje for e in res.errores)
        assert any("espera 1 argumento" in e.mensaje for e in res.errores)


# ===========================================================================
# 7. Integración con los Ejemplos del Taller 1 y los 5 Programas del Taller 2
# ===========================================================================

class TestIntegracionEscenariosReales:
    @pytest.mark.parametrize("ruta", [
        EJEMPLOS_COMP / "escenario1_tda_matrices.spl",
        EJEMPLOS_COMP / "escenario2_control_funciones.spl",
        EJEMPLOS_COMP / "escenario4_operadores_literales.spl",
        EJEMPLOS_PIPE / "escenario1_aritmetica_tda.spl",
        EJEMPLOS_PIPE / "escenario2_punto_flotante_switch.spl",
    ])
    def test_escenarios_taller01_pasan_analisis_semantico(self, ruta):
        texto_pre = preprocesar_archivo(str(ruta)).texto
        res = analizar(texto_pre, exigir_main=False)
        assert res.exito, f"{ruta.name} reporto errores: {res.errores}"

    def test_programa1_euclides_completo(self):
        codigo = """
        int resultado_global = 0;

        function int mcd(int a, int b) {
            while (b != 0) {
                int r = a % b;
                a = b;
                b = r;
            }
            return a;
        }

        function int main() {
            int g1 = mcd(1071, 462);
            int g2 = mcd(48, 18);
            if (g1 > g2) then {
                resultado_global = g1;
            } else {
                resultado_global = g2;
            }
            return resultado_global;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        informe = res.tabla.generar_informe()
        assert "resultado_global" in informe
        assert "0x00201000" in informe
        assert "mcd" in informe

    def test_programa2_newton_ieee754_completo(self):
        codigo = """
        float raiz_newton(float s, int max_iter) {
            float x = s / 2;
            for (int i = 0; i < max_iter; i++) {
                float siguiente = 0.5 * (x + s / x);
                float diff = siguiente - x;
                if (diff < 0.0) diff = -diff;
                x = siguiente;
                if (diff < 1.0e-9) break;
            }
            return x;
        }

        int main() {
            float r = raiz_newton(25, 10);
            print_float(r);
            return 0;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        # Coerciones: 2 -> float (en s / 2) y 25 -> float (en raiz_newton(25, 10))
        coerciones = [n for n in res.ast.recorrer() if isinstance(n, CoercionTipo)]
        assert len(coerciones) == 2

    def test_programa5_tda_registro_sensor_y_switch(self):
        codigo = """
        tda RegistroSensor {
            int id;
            int modo;
            float lectura;
            float escala;
            float resultado;
        };

        int main() {
            tda RegistroSensor sensores[2];
            sensores[0].id = 1;
            sensores[0].modo = 1;
            sensores[0].lectura = 12.5;
            sensores[0].escala = 2.0;

            sensores[1].id = 2;
            sensores[1].modo = 2;
            sensores[1].lectura = 10.0;
            sensores[1].escala = 5.5;

            float total = 0.0;
            for (int i = 0; i < 2; i++) {
                switch (sensores[i].modo) {
                    case 1:
                        sensores[i].resultado = sensores[i].lectura * sensores[i].escala;
                        break;
                    case 2:
                        sensores[i].resultado = sensores[i].lectura + sensores[i].escala;
                        break;
                    default:
                        sensores[i].resultado = 0.0;
                        break;
                }
                total += sensores[i].resultado;
            }
            print_float(total);
            return 0;
        }
        """
        res = analizar(codigo, exigir_main=True)
        assert res.exito, res.errores
        desc = res.tabla.tipos["RegistroSensor"]
        assert desc.tamano_bytes == 40
        fn_main = res.tabla.funciones["main"]
        sim_sensores = next(s for s in fn_main.simbolos_locales if s.nombre == "sensores")
        assert sim_sensores.tamano_bytes == 80
        assert sim_sensores.desplazamiento == -80
