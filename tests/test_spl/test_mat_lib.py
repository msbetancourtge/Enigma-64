"""
Pruebas de la libreria de matrices spl/include/mat.asm (Integrante 3).

Cada programa pasa por el puente de la Tarea 29 (preprocesador con #include,
ensamblador, BinarioEnigma .e64 y CargadorEnigma) y se ejecuta en la CPU real.
Se revisan la RAM, los registros y la pila al llegar a HLT y tambien en medio
de una llamada anidada, deteniendo la CPU a la entrada de MAT_ADDR.
"""

import itertools
from pathlib import Path

import pytest

from enigma64.ensamblador import ensamblar
from spl.ensamblador import EnsambladorLexer
from spl.ensamblador.literales import literal_a_bits
from spl.estructuras import (
    BASE_BUFFERS,
    BASE_MATRICES,
    PILA_ESTRUCTURAS,
    TIPO_MATRIZ,
    DescriptorMatriz,
    cargar_y_ejecutar_estructuras,
)
from spl.preprocesador import preprocesar_archivo, preprocesar_texto


RAIZ = Path(__file__).resolve().parents[2]
MAT_ASM = RAIZ / "spl" / "include" / "mat.asm"
PRUEBA_MAT = RAIZ / "spl" / "ejemplos" / "prueba_mat.asm"

M = BASE_MATRICES       # 0x00260000
N = M + 0x100           # segunda matriz de prueba_mat.asm
RES = BASE_BUFFERS      # 0x002E0000
PILA = PILA_ESTRUCTURAS  # 0x00400000
BP_TESTIGO = 0x7777     # BP del llamador: las rutinas deben devolverlo intacto
MASK64 = (1 << 64) - 1
MENOS_2_5 = 0xC004000000000000

INCLUIR_MAT = '#include "mat.asm"'
INCLUIR_TODO = '#define INCLUIR_MATRICES\n#include "estructuras.inc"'

# Bytes desde la etiqueta hasta la instruccion que sigue a la primera llamada
# anidada: es la direccion de retorno que esa llamada deja en la pila.
RETORNO_EN_MAT_GET = len(ensamblar("ENTER 0\nCALL 0"))
RETORNO_EN_MAT_CLEAR = len(ensamblar("PUSH R1\nPUSH R2\nENTER 0\nCALL 0"))


def palabra(ram, direccion):
    return ram.mem_read(direccion, 8)[0]


def palabras(ram, base, n):
    return [palabra(ram, base + 8 * k) for k in range(n)]


def escribir(ram, base, valores):
    for k, valor in enumerate(valores):
        ram.mem_write(base + 8 * k, valor & MASK64, 8)


def cargar(registro, valor):
    """ADDI/SHL que dejan una constante de hasta 32 bits en el registro."""
    alto, bajo = valor >> 16, valor & 0xFFFF
    lineas = [f"ADDI {registro}, R0, {alto}", f"SHL {registro}, {registro}, 16"]
    if bajo:
        lineas += [f"ADDI {registro}, {registro}, {bajo}" if bajo < 0x8000 else
                   f"ADDI {registro}, {registro}, {bajo - 0x10000}"]
    return "\n".join(lineas)


def fuente(cuerpo, incluir=INCLUIR_MAT):
    """Programa con la libreria incluida y un BP testigo (SP lo alinea el puente)."""
    return "\n".join([incluir, f"ADDI BP, R0, {BP_TESTIGO}", cuerpo, "HLT"])


def preparar(cuerpo, datos=None, estructuras=None, incluir=INCLUIR_MAT):
    """Compila y carga sin ejecutar; datos = {direccion: [palabras]} se precargan en RAM."""
    res = cargar_y_ejecutar_estructuras(
        fuente(cuerpo, incluir), es_archivo=False, estructuras=estructuras, ejecutar=False
    )
    for base, valores in (datos or {}).items():
        escribir(res.ram, base, valores)
    return res


def ejecutar(cuerpo, datos=None, estructuras=None, incluir=INCLUIR_MAT):
    res = preparar(cuerpo, datos, estructuras, incluir)
    res.cpu.ejecutar(max_ciclos=4_000_000)
    return res


def matriz(filas, cols, elementos=None, base=M):
    """Cabecera inline (F, C) seguida de los F * C elementos, lista para precargar."""
    elementos = list(elementos) if elementos is not None else [0] * (filas * cols)
    return {base - 16: [filas, cols] + elementos}


def argumentos(r1=M, r2=0, r3=0, r4=0):
    return "\n".join([cargar("R1", r1), f"ADDI R2, R0, {r2}", f"ADDI R3, R0, {r3}",
                      cargar("R4", r4) if r4 > 0x7FFF else f"ADDI R4, R0, {r4}"])


def correr_hasta(res, etiqueta, condicion=lambda res: True, max_instrucciones=100_000):
    """Ejecuta instruccion a instruccion hasta entrar en la etiqueta (y cumplir la condicion)."""
    destino = res.binario_e64.tabla_simbolos[etiqueta]
    for _ in range(max_instrucciones):
        if res.banco.pc == destino and condicion(res):
            return
        assert not res.cpu.detenido, f"la CPU llego a HLT sin entrar en {etiqueta}"
        res.cpu.paso_instruccion()
    raise AssertionError(f"no se llego a {etiqueta} en {max_instrucciones} instrucciones")


DATOS = [100 + k for k in range(12)]   # matriz 3 x 4 de prueba


# 1. Inclusion con el preprocesador

class TestInclusion:
    def test_include_desde_spl_include_trae_la_api_completa(self):
        texto = preprocesar_texto(INCLUIR_MAT + "\nHLT\n").texto
        for rutina in ("MAT_ADDR", "MAT_GET", "MAT_SET", "MAT_CLEAR",   # mat.asm
                       "MAT_INIT", "MAT_ROWS", "MAT_COLS"):            # cabeceras.asm
            assert f"\n{rutina}:" in texto

    def test_inclusion_doble_no_duplica_etiquetas(self):
        texto = preprocesar_texto(
            '#include "mat.asm"\n#include <mat.asm>\n' + INCLUIR_TODO +
            '\n#include "cabeceras.asm"\nHLT\n'
        ).texto
        assert texto.count("JMP MAT_FIN_LIBRERIA") == 1
        assert texto.count("JMP CAB_FIN_LIBRERIA") == 1
        assert texto.count("JMP VEC_FIN_LIBRERIA") == 1
        ensamblar(texto)  # una etiqueta duplicada lanzaria ErrorEnsamblador

    @pytest.mark.parametrize("codigo, definiciones", [
        (INCLUIR_TODO, None),
        ('#include "estructuras.inc"', {"INCLUIR_MATRICES": "1"}),
    ])
    def test_gancho_incluir_matrices_de_estructuras_inc(self, codigo, definiciones):
        texto = preprocesar_texto(codigo + "\nHLT\n", definiciones=definiciones).texto
        assert "\nMAT_ADDR:" in texto and "\nVEC_ADDR:" in texto
        assert len(ensamblar(texto)) > 0

    def test_sin_el_gancho_estructuras_inc_no_trae_matrices(self):
        texto = preprocesar_texto('#include "estructuras.inc"\nHLT\n').texto
        assert "MAT_ADDR" not in texto

    def test_lexer_del_ensamblador_sin_errores(self):
        for codigo in (INCLUIR_MAT, INCLUIR_TODO):
            _, errores = EnsambladorLexer().tokenizar(preprocesar_texto(codigo + "\n").texto)
            assert errores == []

    def test_incluida_al_inicio_no_se_ejecuta_por_caida(self):
        res = ejecutar("ADDI R1, R0, 7")
        assert res.banco.leer(1) == 7
        assert res.banco.sp == PILA
        assert res.banco.bp == BP_TESTIGO

    def test_incluida_al_final_tambien_sirve(self):
        codigo = "\n".join([argumentos(M, 2, 1), "CALL MAT_ADDR", "HLT", INCLUIR_MAT])
        res = cargar_y_ejecutar_estructuras(codigo, es_archivo=False, ejecutar=False)
        escribir(res.ram, M - 8, [4])   # C = 4
        res.cpu.ejecutar(max_ciclos=100_000)
        assert res.banco.leer(5) == M + ((2 * 4 + 1) << 3)


# 2. Programa de prueba entregado (spl/ejemplos/prueba_mat.asm)

@pytest.fixture(scope="module")
def estado():
    return cargar_y_ejecutar_estructuras(str(PRUEBA_MAT), es_archivo=True)


class TestProgramaDePrueba:
    def test_matriz_m(self, estado):
        assert palabras(estado.ram, M - 16, 2) == [3, 4]
        assert estado.leer_matriz(M, 3, 4, modo="uint") == [
            [0, 1, 2, MENOS_2_5],
            [10, 11, 12, 13],
            [20, 21, 22, 23],
        ]

    def test_matriz_n_borrada_sin_tocar_el_centinela(self, estado):
        assert palabras(estado.ram, N - 16, 2 + 6 + 1) == [2, 3, 0, 0, 0, 0, 0, 0, 12]

    def test_resultados(self, estado):
        assert palabras(estado.ram, RES, 9) == [
            M + 72, 12, 23, 138, M, 3, MENOS_2_5, 13, 6
        ]

    def test_registros_finales_y_pila_balanceada(self, estado):
        assert [estado.banco.leer(r) for r in (1, 2, 3, 4)] == [N, 2, 3, RES]
        assert estado.banco.sp == PILA
        assert estado.banco.bp == PILA

    def test_preprocesado_desde_archivo_ensambla(self):
        texto = preprocesar_archivo(str(PRUEBA_MAT)).texto
        assert EnsambladorLexer().tokenizar(texto)[1] == []
        assert len(ensamblar(texto)) > 0


# 3. MAT_ADDR: base + ((i * C + j) << 3)

def cuerpo_rutina(nombre):
    """Mnemonicos de la rutina, desde su etiqueta hasta el primer RET."""
    texto = MAT_ASM.read_text(encoding="utf-8").split(f"\n{nombre}:\n", 1)[1].split("RET", 1)[0]
    lineas = [linea.split(";")[0].split() for linea in texto.splitlines()]
    return [partes[0] for partes in lineas if partes]


class TestMatAddr:
    def test_usa_mul_add_y_shl(self):
        assert cuerpo_rutina("MAT_ADDR") == ["LOAD", "MUL", "ADD", "SHL", "ADD"]

    @pytest.mark.parametrize("cols, i, j", [
        (4, 0, 0), (4, 2, 1), (4, 2, 3), (4, 1, 0),
        (7, 0, 6),          # una sola fila
        (1, 6, 0),          # una sola columna
        (1000, 99, 999),    # desplazamiento de mas de 16 bits
        (3, 1, 2),
    ])
    def test_direccion(self, cols, i, j):
        res = ejecutar(argumentos(M, i, j) + "\nCALL MAT_ADDR", datos={M - 8: [cols]})
        assert res.banco.leer(5) == M + ((i * cols + j) << 3)

    @pytest.mark.parametrize("cols, i, j", [(4, 2, 1), (5, 3, 4), (1, 9, 0), (12, 0, 11)])
    def test_coincide_con_la_macro_del_layout(self, cols, i, j):
        linea = preprocesar_texto(
            f'#include "layout_datos.inc"\nx = MAT_DIR({M:#x}, {cols}, {i}, {j});\n'
        ).texto.strip().splitlines()[-1]
        en_compilacion = eval(linea.split("=", 1)[1].rstrip(";"))
        res = ejecutar(argumentos(M, i, j) + "\nCALL MAT_ADDR", datos={M - 8: [cols]})
        assert res.banco.leer(5) == en_compilacion

    @pytest.mark.parametrize("j", range(6))
    def test_una_fila_es_un_vector(self, j):
        cuerpo = "\n".join([argumentos(M, 0, j), "CALL MAT_ADDR", "ADD R4, R5, R0",
                            "ADD R2, R3, R0", "CALL VEC_ADDR"])
        res = ejecutar(cuerpo, datos=matriz(1, 6), incluir=INCLUIR_TODO)
        assert res.banco.leer(4) == res.banco.leer(5) == M + (j << 3)


# 4. MAT_GET y MAT_SET

class TestMatGetSet:
    @pytest.mark.parametrize("i, j", list(itertools.product(range(3), range(4))))
    def test_mat_get(self, i, j):
        res = ejecutar(argumentos(M, i, j) + "\nCALL MAT_GET", datos=matriz(3, 4, DATOS))
        assert res.banco.leer(5) == DATOS[i * 4 + j]

    @pytest.mark.parametrize("i, j", [(0, 0), (1, 2), (2, 3), (2, 0)])
    def test_mat_set_solo_cambia_su_celda(self, i, j):
        res = ejecutar(argumentos(M, i, j, 0x1234) + "\nCALL MAT_SET",
                       datos={**matriz(3, 4, DATOS), M + 96: [0xCAFE]})
        esperado = list(DATOS)
        esperado[i * 4 + j] = 0x1234
        assert palabras(res.ram, M - 16, 2 + 12 + 1) == [3, 4] + esperado + [0xCAFE]

    def test_set_y_get_conservan_los_bits_de_double(self):
        literales = ["3.14159265358979323846", "1e-07", "-0.0", "-2.5", "0.0",
                     "4.9406564584124654e-324"]
        bits = [literal_a_bits(t) for t in literales]
        b = M + 0x200
        lineas = []
        for k in range(len(bits)):                  # B[i][j] = A[i][j] con GET y SET
            i, j = divmod(k, 3)
            lineas += [f"ADDI R2, R0, {i}", f"ADDI R3, R0, {j}", cargar("R1", M),
                       "CALL MAT_GET", "ADD R4, R5, R0", cargar("R1", b), "CALL MAT_SET"]
        res = ejecutar("\n".join(lineas), datos={**matriz(2, 3, bits), **matriz(2, 3, base=b)})
        assert palabras(res.ram, b, 6) == bits


# 5. MAT_CLEAR

class TestMatClear:
    @pytest.mark.parametrize("filas, cols", [(1, 1), (3, 4), (1, 7), (5, 1), (16, 16), (0, 4), (4, 0)])
    def test_borra_exactamente_f_por_c_palabras(self, filas, cols):
        total = filas * cols
        datos = {M - 24: [0xBEEF, filas, cols] + [MENOS_2_5 + k for k in range(total)] + [0xCAFE]}
        res = ejecutar(argumentos(M) + "\nCALL MAT_CLEAR", datos=datos)
        assert palabras(res.ram, M - 24, 3 + total + 1) == [0xBEEF, filas, cols] + [0] * total + [0xCAFE]
        assert res.banco.leer(5) == total

    def test_dimensiones_negativas_no_escriben(self):
        res = ejecutar(argumentos(M) + "\nCALL MAT_CLEAR", datos=matriz(-1, 3, [5, 6, 7]))
        assert palabras(res.ram, M, 3) == [5, 6, 7]
        assert res.banco.leer(5) == 0

    def test_tras_clear_los_doubles_son_mas_cero(self):
        res = ejecutar(argumentos(M) + "\nCALL MAT_CLEAR",
                       datos=matriz(2, 2, [literal_a_bits("-2.5")] * 4))
        assert res.leer_matriz(M, 2, 2, modo="float") == [[0.0, 0.0], [0.0, 0.0]]
        assert palabras(res.ram, M, 4) == [literal_a_bits("0.0")] * 4


# 6. Convencion de llamada y gestion de la pila (R6 = SP, R7 = BP)

RUTINAS = ["MAT_ADDR", "MAT_GET", "MAT_SET", "MAT_CLEAR"]


class TestConvencionDeLlamada:
    @pytest.mark.parametrize("llamada", RUTINAS)
    def test_preserva_r1_a_r4_sp_y_bp(self, llamada):
        testigos = {1: M, 2: 2, 3: 1, 4: 0x1234}
        res = ejecutar(argumentos(*testigos.values()) + f"\nCALL {llamada}",
                       datos=matriz(3, 4, DATOS))
        assert {r: res.banco.leer(r) for r in testigos} == testigos
        assert res.banco.sp == PILA
        assert res.banco.bp == BP_TESTIGO

    @pytest.mark.parametrize("llamada, palabras_de_pila", [
        ("MAT_ADDR", 1),    # retorno
        ("MAT_GET", 3),     # retorno, BP del llamador, retorno a MAT_GET
        ("MAT_SET", 3),
        ("MAT_CLEAR", 5),   # retorno, R1, R2, BP del llamador, retorno a MAT_CLEAR
    ])
    def test_profundidad_maxima_de_pila(self, llamada, palabras_de_pila):
        res = preparar(argumentos(M, 2, 1, 9) + f"\nCALL {llamada}", datos=matriz(3, 4, DATOS))
        minimo = res.banco.sp
        while not res.cpu.detenido:
            res.cpu.paso_instruccion()
            minimo = min(minimo, res.banco.sp)
        assert PILA - minimo == 8 * palabras_de_pila
        assert res.banco.sp == PILA

    @pytest.mark.parametrize("llamada", ["MAT_GET", "MAT_SET"])
    def test_marco_durante_la_llamada_anidada_a_mat_addr(self, llamada):
        res = preparar(argumentos(M, 2, 1, 9) + f"\nCALL {llamada}\nTRAS_LLAMADA:",
                       datos=matriz(3, 4, DATOS))
        simbolos = res.binario_e64.tabla_simbolos
        correr_hasta(res, "MAT_ADDR")
        sp, bp, ram = res.banco.sp, res.banco.bp, res.ram
        assert palabra(ram, sp) == simbolos[llamada] + RETORNO_EN_MAT_GET   # nivel 2
        assert bp == sp + 8                                                   # ENTER 0
        assert palabra(ram, bp) == BP_TESTIGO                                 # enlace dinamico
        assert palabra(ram, bp + 8) == simbolos["TRAS_LLAMADA"]               # nivel 1
        assert bp + 16 == PILA

    def test_marco_de_mat_clear_durante_la_llamada_anidada(self):
        res = preparar(argumentos(M, 2, 1, 9) + "\nCALL MAT_CLEAR\nTRAS_LLAMADA:",
                       datos=matriz(3, 4, DATOS))
        simbolos = res.binario_e64.tabla_simbolos
        correr_hasta(res, "MAT_ROWS")
        sp, bp, ram = res.banco.sp, res.banco.bp, res.ram
        assert palabra(ram, sp) == simbolos["MAT_CLEAR"] + RETORNO_EN_MAT_CLEAR
        assert palabras(ram, bp, 4) == [BP_TESTIGO, 2, M, simbolos["TRAS_LLAMADA"]]

    def test_cadena_de_marcos_en_tres_niveles(self):
        """INICIO -> SUMAR_MATRIZ -> MAT_GET -> MAT_ADDR en prueba_mat.asm."""
        res = cargar_y_ejecutar_estructuras(str(PRUEBA_MAT), es_archivo=True, ejecutar=False)
        simbolos = res.binario_e64.tabla_simbolos
        en_sumar = range(simbolos["SUMAR_MATRIZ"], simbolos["SM_FIN"])
        correr_hasta(res, "MAT_ADDR", lambda r: palabra(r.ram, r.banco.bp + 8) in en_sumar)
        ram = res.ram
        assert palabra(ram, res.banco.sp) == simbolos["MAT_GET"] + RETORNO_EN_MAT_GET
        marcos, bp = [], res.banco.bp
        while bp != PILA:                    # sigue el enlace dinamico [BP] hasta INICIO
            marcos.append(bp)
            bp = palabra(ram, bp)
        assert len(marcos) == 2
        bp_get, bp_sumar = marcos
        # Marco de MAT_GET (ENTER 0 sin PUSH previos): retorno en [BP + 8]
        assert palabra(ram, bp_get + 8) in en_sumar
        # Marco de SUMAR_MATRIZ (PUSH R2, R3, R4 y ENTER 16): R4, R3, R2 guardados
        # encima de BP, retorno en [BP + 32] y locales F, C debajo de BP
        assert palabras(ram, bp_sumar + 8, 4) == [RES, 3, 2, simbolos["TRAS_SUMAR"]]
        assert palabras(ram, bp_sumar - 16, 2) == [4, 3]

    def test_recursion_profunda_con_marcos(self):
        """Suma recursiva de la columna 0: 300 marcos anidados que llaman a MAT_GET."""
        filas = [[7 * k - 1000, k] for k in range(300)]
        rutina = """
            ADD  R2, R0, R0
            CALL SUMA_COL
            HLT
        SUMA_COL:                           ; R5 = suma de M[k][0] para k >= R2
            PUSH R2
            PUSH R3
            ENTER 8                         ; [BP - 8] = M[i][0]
            CALL MAT_ROWS
            CMP  R2, R5
            JZ   SC_BASE
            ADD  R3, R0, R0
            CALL MAT_GET
            STORE R5, [BP - 8]
            INC  R2
            CALL SUMA_COL
            LOAD R3, [BP - 8]
            ADD  R5, R5, R3
            JMP  SC_FIN
        SC_BASE:
            ADD  R5, R0, R0
        SC_FIN:
            LEAVE
            POP  R3
            POP  R2
            RET
        """
        desc = DescriptorMatriz.desde_filas("T", filas, direccion_base=M, slot_cabecera=None)
        res = ejecutar(cargar("R1", M) + rutina, estructuras=[desc])
        assert res.banco.leer(5) == sum(f[0] for f in filas) & MASK64
        assert res.banco.sp == PILA
        assert res.banco.bp == BP_TESTIGO


# 7. Integracion con cabeceras.asm, descriptores Python y vec.asm

class TestIntegracionEstructuras:
    def test_matriz_precargada_con_descriptor_python(self):
        desc = DescriptorMatriz.desde_filas("A", [[1, 2, 3], [4, 5, 6]], direccion_base=M)
        cuerpo = argumentos(M, 1, 2, 77) + "\nCALL MAT_SET\nADDI R2, R0, 0\nCALL MAT_GET"
        res = ejecutar(cuerpo, estructuras=[desc])
        assert res.banco.leer(5) == 3                       # M[0][2]
        assert res.leer_matriz(M, 2, 3) == [[1, 2, 3], [4, 5, 77]]

    def test_desc_mat_init_y_mat_clear(self):
        cuerpo = "\n".join([
            "ADDI R1, R0, 1", cargar("R2", N), "ADDI R3, R0, 2", "ADDI R4, R0, 3",
            "CALL DESC_MAT_INIT",                           # descriptor slot 1 y cabecera
            cargar("R1", N), "CALL MAT_CLEAR",
        ])
        res = ejecutar(cuerpo, datos={N: list(range(1, 8))}, incluir=INCLUIR_TODO)
        assert res.banco.leer(5) == 6
        assert palabras(res.ram, N, 7) == [0] * 6 + [7]
        descriptor = res.leer_descriptor(1)
        assert (descriptor["tipo"], descriptor["direccion_base"]) == (TIPO_MATRIZ, N)

    def test_vec_swap_sobre_una_fila(self):
        cuerpo = "\n".join([argumentos(M, 1, 0), "CALL MAT_ADDR",   # R5 = &M[1][0]
                            "ADD R1, R5, R0", "ADDI R2, R0, 0", "ADDI R3, R0, 3",
                            "CALL VEC_SWAP"])
        res = ejecutar(cuerpo, datos=matriz(3, 4, DATOS), incluir=INCLUIR_TODO)
        esperado = [DATOS[0:4], [DATOS[7], DATOS[5], DATOS[6], DATOS[4]], DATOS[8:12]]
        assert res.leer_matriz(M, 3, 4) == esperado
