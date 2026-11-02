"""
Pruebas de la libreria de vectores spl/include/vec.asm (Integrante 2).

Cada programa pasa por el preprocesador (#include), el ensamblador de
Enigma-64 y la CPU real, y se revisa la RAM y los registros al llegar a HLT.
"""

import random
from pathlib import Path

import pytest

from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory
from enigma64.registros import BancoRegistros
from spl.ensamblador import EnsambladorLexer
from spl.ensamblador.literales import literal_a_bits
from spl.preprocesador import preprocesar_archivo, preprocesar_texto


RAIZ = Path(__file__).resolve().parents[2]
VEC_ASM = RAIZ / "spl" / "include" / "vec.asm"
PRUEBA_VEC = RAIZ / "spl" / "ejemplos" / "prueba_vec.asm"
ESQUELETO = RAIZ / "spl" / "ejemplos" / "esqueleto_merge_sort.asm"

BASE_CODIGO = 0x00200000
V = 0x00220000          # BASE_VECTORES
W = 0x00220100
RES = 0x002E0000        # BASE_BUFFERS
PILA = 0x00400000
MASK64 = (1 << 64) - 1
MENOS_2_5 = 0xC004000000000000


def ejecutar(fuente_asm):
    """Ensambla texto ya preprocesado, lo ejecuta hasta HLT y devuelve (cpu, banco, ram)."""
    binario = ensamblar(fuente_asm, direccion_base=BASE_CODIGO)
    ram, banco = RAMMemory(), BancoRegistros()
    for i, byte in enumerate(binario):
        ram.mem_write(BASE_CODIGO + i, byte, 1, check_alignment=False)
    banco.pc = BASE_CODIGO
    cpu = CPU(ram=ram, banco=banco)
    cpu.ejecutar(max_ciclos=2_000_000)
    return cpu, banco, ram


def palabra(ram, direccion):
    return ram.mem_read(direccion, 8)[0]


def palabras(ram, base, n):
    return [palabra(ram, base + 8 * k) for k in range(n)]


def cargar(registro, valor):
    """ADDI/SHL que dejan una constante de hasta 32 bits en el registro."""
    alto, bajo = valor >> 16, valor & 0xFFFF
    lineas = [f"ADDI {registro}, R0, {alto}", f"SHL {registro}, {registro}, 16"]
    if bajo:
        lineas += [f"ADDI {registro}, {registro}, {bajo}" if bajo < 0x8000 else
                   f"ADDI {registro}, {registro}, {bajo - 0x10000}"]
    return "\n".join(lineas)


def programa(cuerpo):
    """Programa con la libreria incluida, pila alineada y R1..R4 con valores testigo."""
    texto = "\n".join([
        '#include "vec.asm"',
        cargar("SP", PILA),
        cuerpo,
        "HLT",
    ])
    return preprocesar_texto(texto).texto


# 1. Inclusion con el preprocesador

class TestInclusion:
    def test_include_desde_spl_include(self):
        texto = preprocesar_texto('#include "vec.asm"\nHLT\n').texto
        for rutina in ("VEC_ADDR:", "VEC_GET:", "VEC_SET:", "VEC_SWAP:", "VEC_COPY:", "VEC_LEN:"):
            assert f"\n{rutina}" in texto

    def test_inclusion_doble_no_duplica_etiquetas(self):
        texto = preprocesar_texto('#include "vec.asm"\n#include <vec.asm>\nHLT\n').texto
        assert texto.count("JMP VEC_FIN_LIBRERIA") == 1
        ensamblar(texto)  # una etiqueta duplicada lanzaria ErrorEnsamblador

    def test_lexer_del_ensamblador_sin_errores(self):
        _, errores = EnsambladorLexer().tokenizar(preprocesar_texto('#include "vec.asm"\n').texto)
        assert errores == []

    def test_incluida_al_inicio_no_se_ejecuta_por_caida(self):
        _, banco, _ = ejecutar(programa("ADDI R1, R0, 7"))
        assert banco.leer(1) == 7
        assert banco.sp == PILA

    def test_incluida_al_final_tambien_sirve(self):
        texto = preprocesar_texto(
            cargar("SP", PILA) + "\n" + cargar("R1", V) + "\nADDI R2, R0, 2\nCALL VEC_ADDR\nHLT\n"
            '#include "vec.asm"\n'
        ).texto
        _, banco, _ = ejecutar(texto)
        assert banco.leer(5) == V + 16


# 2. Programa de prueba entregado (spl/ejemplos/prueba_vec.asm)

@pytest.fixture(scope="module")
def estado():
    return ejecutar(preprocesar_archivo(str(PRUEBA_VEC)).texto)


class TestProgramaDePrueba:
    def test_vector_v(self, estado):
        _, _, ram = estado
        assert palabras(ram, V - 8, 7) == [6, 50, 20, 30, 40, 40, MENOS_2_5]

    def test_vector_w(self, estado):
        _, _, ram = estado
        assert palabras(ram, W, 6) == [50, 20, 30, 40, 10, MENOS_2_5]

    def test_resultados(self, estado):
        _, _, ram = estado
        assert palabras(ram, RES, 6) == [V + 24, 30, MENOS_2_5, 6, V, 4]

    def test_registros_finales(self, estado):
        _, banco, _ = estado
        assert [banco.leer(r) for r in (1, 2, 3, 4)] == [V, V + 8, 4, RES]
        assert banco.sp == PILA


# 3. Cada subrutina y la convencion de llamada

TESTIGOS = {1: V, 2: 3, 3: 1, 4: 0x1234}          # base, i, j o valor, R4 ajeno
TESTIGOS_COPY = {1: V, 2: V + 24, 3: 2, 4: 0x1234}  # destino, origen, n, R4 ajeno


def preparar_testigos(testigos=TESTIGOS):
    return "\n".join([cargar(f"R{r}", valor) if valor > 0x7FFF else f"ADDI R{r}, R0, {valor}"
                      for r, valor in testigos.items()])


def llenar_v(ram, valores, base=V):
    for k, valor in enumerate(valores):
        ram.mem_write(base + 8 * k, valor & MASK64, 8)


def ejecutar_con_datos(cuerpo, datos, base=V):
    """Como ejecutar(), pero precarga datos en la RAM antes de correr."""
    binario = ensamblar(programa(cuerpo), direccion_base=BASE_CODIGO)
    ram, banco = RAMMemory(), BancoRegistros()
    for i, byte in enumerate(binario):
        ram.mem_write(BASE_CODIGO + i, byte, 1, check_alignment=False)
    llenar_v(ram, datos, base)
    banco.pc = BASE_CODIGO
    cpu = CPU(ram=ram, banco=banco)
    cpu.ejecutar(max_ciclos=2_000_000)
    return cpu, banco, ram


DATOS = [11, 22, 33, 44, 55, 66]


class TestSubrutinas:
    def test_vec_addr_usa_shl_y_add(self):
        cuerpo = [linea.split(";")[0].split() for linea in VEC_ASM.read_text(encoding="utf-8")
                  .split("VEC_ADDR:\n", 1)[1].split("RET", 1)[0].splitlines()]
        assert [partes[0] for partes in cuerpo if partes] == ["SHL", "ADD"]

    @pytest.mark.parametrize("i", [0, 1, 5, 1000])
    def test_vec_addr(self, i):
        _, banco, _ = ejecutar(programa(cargar("R1", V) + f"\nADDI R2, R0, {i}\nCALL VEC_ADDR"))
        assert banco.leer(5) == V + (i << 3)

    @pytest.mark.parametrize("i", range(6))
    def test_vec_get(self, i):
        _, banco, _ = ejecutar_con_datos(preparar_testigos() + f"\nADDI R2, R0, {i}\nCALL VEC_GET", DATOS)
        assert banco.leer(5) == DATOS[i]

    def test_vec_set(self):
        _, _, ram = ejecutar_con_datos(preparar_testigos() + "\nCALL VEC_SET", DATOS)
        assert palabras(ram, V, 6) == [11, 22, 33, 1, 55, 66]   # v[3] = 1

    def test_vec_swap(self):
        _, _, ram = ejecutar_con_datos(preparar_testigos() + "\nCALL VEC_SWAP", DATOS)
        assert palabras(ram, V, 6) == [11, 44, 33, 22, 55, 66]   # v[3] <-> v[1]

    def test_vec_swap_mismo_indice(self):
        _, _, ram = ejecutar_con_datos(preparar_testigos() + "\nADDI R3, R0, 3\nCALL VEC_SWAP", DATOS)
        assert palabras(ram, V, 6) == DATOS

    def test_vec_len(self):
        _, banco, _ = ejecutar_con_datos(preparar_testigos() + "\nCALL VEC_LEN", [6] + DATOS, base=V - 8)
        assert banco.leer(5) == 6

    @pytest.mark.parametrize("llamada", ["VEC_ADDR", "VEC_GET", "VEC_SET", "VEC_SWAP", "VEC_COPY", "VEC_LEN"])
    def test_preserva_r1_a_r4_y_sp(self, llamada):
        testigos = TESTIGOS_COPY if llamada == "VEC_COPY" else TESTIGOS
        cuerpo = preparar_testigos(testigos) + "\nADDI R7, R0, 0x77\n" + f"CALL {llamada}"
        _, banco, _ = ejecutar_con_datos(cuerpo, [6] + DATOS + [0] * 8, base=V - 8)
        assert {r: banco.leer(r) for r in testigos} == testigos
        assert banco.sp == PILA
        assert banco.bp == 0x77


# 4. VEC_COPY: semantica de memmove, con y sin solape

def copiar_en_python(memoria, destino, origen, n):
    if n > 0:
        memoria[destino:destino + n] = memoria[origen:origen + n]


class TestVecCopy:
    @pytest.mark.parametrize("destino, origen, n", [
        (0, 10, 5),    # sin solape, hacia adelante
        (10, 0, 5),    # sin solape, hacia atras
        (1, 0, 6),     # solape, destino > origen
        (0, 1, 6),     # solape, destino < origen
        (3, 3, 4),     # misma zona
        (2, 0, 0),     # n = 0
        (2, 0, -3),    # n negativo
        (0, 7, 1),
    ])
    def test_casos(self, destino, origen, n):
        inicial = [100 + k for k in range(16)]
        cuerpo = "\n".join([cargar("R1", V + 8 * destino), cargar("R2", V + 8 * origen),
                            f"ADDI R3, R0, {n}", "CALL VEC_COPY"])
        _, banco, ram = ejecutar_con_datos(cuerpo, inicial)
        esperado = list(inicial)
        copiar_en_python(esperado, destino, origen, n)
        assert palabras(ram, V, 16) == esperado
        assert banco.leer(3) == n & MASK64

    def test_aleatorio_contra_memmove(self):
        azar = random.Random(64)
        for _ in range(25):
            destino, origen = azar.randrange(0, 20), azar.randrange(0, 20)
            n = azar.randrange(0, 20 - max(destino, origen) + 1)
            inicial = [azar.getrandbits(64) for _ in range(20)]
            cuerpo = "\n".join([cargar("R1", V + 8 * destino), cargar("R2", V + 8 * origen),
                                f"ADDI R3, R0, {n}", "CALL VEC_COPY"])
            _, _, ram = ejecutar_con_datos(cuerpo, inicial)
            esperado = list(inicial)
            copiar_en_python(esperado, destino, origen, n)
            assert palabras(ram, V, 20) == esperado, (destino, origen, n)


# 5. Datos double IEEE-754: las primitivas mueven los 64 bits sin tocarlos

class TestDobles:
    LITERALES = ["3.14159265358979323846", "1e-07", "-0.0", "-2.5", "0.0",
                 "4.9406564584124654e-324", "1.7976931348623157e308"]

    def test_swap_y_copy_conservan_los_bits(self):
        bits = [literal_a_bits(t) for t in self.LITERALES]
        cuerpo = "\n".join([
            cargar("R1", V), "ADDI R2, R0, 0", "ADDI R3, R0, 6", "CALL VEC_SWAP",
            cargar("R1", W), cargar("R2", V), "ADDI R3, R0, 7", "CALL VEC_COPY",
        ])
        _, _, ram = ejecutar_con_datos(cuerpo, bits)
        intercambiado = [bits[6]] + bits[1:6] + [bits[0]]
        assert palabras(ram, V, 7) == intercambiado
        assert palabras(ram, W, 7) == intercambiado


# 6. Esqueleto de merge sort: ensambla con la libreria

def test_esqueleto_merge_sort_ensambla():
    texto = preprocesar_archivo(str(ESQUELETO)).texto
    assert EnsambladorLexer().tokenizar(texto)[1] == []
    assert len(ensamblar(texto)) > 0
