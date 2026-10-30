"""
Pruebas del traductor CacaoCore-64 -> Enigma-64: registros y ALU (Integrante 2).

Ademas de pruebas unitarias, cada programa se traduce, se ensambla con el
ensamblador de Enigma-64, se ejecuta en el emulador y su estado final se
compara con un modelo de referencia de la semantica de CacaoCore-64, registro
por registro (incluidos los derramados a memoria).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from enigma64.ensamblador import ensamblar
from spl.traductor.alu import TraductorALU, cargar_constante, parsear_operando
from spl.traductor.memoria import TraductorMemoria
from spl.traductor.registros import (
    ACC,
    REG_BASE,
    TMP1,
    TMP2,
    RegistroDerramado,
    RegistroInvalido,
    TablaRegistros,
    mapear_registro,
    numero_registro,
)
from spl.traductor.traductor import (
    TraductorCacaoEnigma,
    ejecutar_en_enigma,
    traducir_texto,
)

EJEMPLOS = Path(__file__).resolve().parents[3] / "spl" / "traductor" / "ejemplos"
MASK64 = (1 << 64) - 1


def s64(valor: int) -> int:
    valor &= MASK64
    return valor - (1 << 64) if valor >> 63 else valor


# ---------------------------------------------------------------------------
# Modelo de referencia de CacaoCore-64 (semantica documentada)
# ---------------------------------------------------------------------------


class OperandoNoValido(Exception):
    """El programa aleatorio cae en un caso fuera del modelo (p. ej. DIV negativa)."""


class ModeloCacao:
    """Interprete minimo de CacaoCore-64 con las reglas que sigue el traductor."""

    def __init__(self, fuente: str, direcciones: dict[str, int]) -> None:
        self.programa = TraductorCacaoEnigma().analizar(fuente)
        self.r = [0] * 16
        self.mem = {direcciones[n]: s64(bits) for n, (bits, _) in self.programa.variables.items()}
        self.dir = direcciones
        self.z = self.n = 0
        self.pila: list[int] = []

    def _banderas(self, valor: int) -> None:
        self.z, self.n = int(valor == 0), int(valor < 0)

    def _direccion(self, op) -> int:
        return self.dir[op.valor] if op.tipo == "var" else self.r[op.valor]

    def _valor(self, op) -> int:
        if op.tipo == "reg":
            return self.r[op.valor]
        if op.tipo == "imm":
            return op.valor
        return self.mem.get(self._direccion(op), 0)

    def _division(self, a: int, b: int) -> int:
        if a <= 0 or b <= 0:
            raise OperandoNoValido("division con operandos no positivos")
        return a // b

    def ejecutar(self, limite: int = 100_000) -> "ModeloCacao":
        ins_list, etiquetas = self.programa.instrucciones, self.programa.etiquetas
        pc = 0
        for _ in range(limite):
            if pc >= len(ins_list):
                return self
            ins = ins_list[pc]
            pc += 1
            m, ops = ins.mnemonico, ins.operandos
            r = self.r
            if m == "hlt":
                return self
            if m in ("jmp", "jz", "jnz", "jg", "jl", "jge", "jle", "js", "jns"):
                salta = {
                    "jmp": True, "jz": self.z, "jnz": not self.z,
                    "jg": not self.n and not self.z, "jl": self.n and not self.z,
                    "jge": not self.n or self.z, "jle": self.n or self.z,
                    "js": self.n, "jns": not self.n,
                }[m]
                if salta:
                    pc = etiquetas[ops[0].valor]
            elif m in ("nop", "intr"):
                pass
            elif m == "push":
                self.pila.append(r[ops[0].valor])
            elif m == "pop":
                r[ops[0].valor] = self.pila.pop()
            elif m in ("add", "sub", "mul", "and", "or", "xor", "div"):
                destino, fuente = (ACC, ops[0]) if len(ops) == 1 else (ops[0].valor, ops[1])
                a, b = r[destino], self._valor(fuente)
                if m == "div":
                    q = self._division(a, b)
                    r[ACC] = q
                    if len(ops) == 2 and fuente.tipo == "reg":
                        r[fuente.valor] = a - q * b
                    r[destino] = r[ACC]
                    self._banderas(q)
                    continue
                res = s64({"add": a + b, "sub": a - b, "mul": a * b,
                           "and": a & b, "or": a | b, "xor": a ^ b}[m])
                r[destino] = r[ACC] = res
                self._banderas(res)
            elif m in ("cmp", "test"):
                a, b = (r[ACC], self._valor(ops[0])) if len(ops) == 1 else (r[ops[0].valor], self._valor(ops[1]))
                self._banderas(s64(a - b) if m == "cmp" else s64(a & b))
            elif m == "cmpz":
                self._banderas(s64(0 - self._valor(ops[0])))
            elif m in ("inc", "dec", "neg", "not"):
                v = self._valor(ops[0])
                res = s64({"inc": v + 1, "dec": v - 1, "neg": -v, "not": ~v}[m])
                if ops[0].tipo == "reg":
                    r[ops[0].valor] = res
                else:
                    self.mem[self._direccion(ops[0])] = res
                r[ACC] = res
                self._banderas(res)
            elif m in ("shl", "shr"):
                x, k = (ACC, ops[0].valor) if len(ops) == 1 else (ops[0].valor, ops[1].valor)
                res = s64(r[x] << k) if m == "shl" else r[x] >> k
                r[x] = r[ACC] = res
                self._banderas(res)
            elif m in ("rol", "ror"):
                x, k = (ACC, ops[0].valor) if len(ops) == 1 else (ops[0].valor, ops[1].valor)
                k %= 64
                v = r[x] & MASK64
                rot = ((v << k) | (v >> (64 - k))) if m == "rol" else ((v >> k) | (v << (64 - k)))
                r[x] = s64(rot)
            elif m == "swap":
                x, y = (ops[0].valor, ACC) if len(ops) == 1 else (ops[0].valor, ops[1].valor)
                r[x], r[y] = r[y], r[x]
            elif m == "lea":
                x = ops[0].valor if len(ops) == 2 else ACC
                r[x] = r[ACC] = self._direccion(ops[-1])
            elif m.startswith(("mov", "load", "store")):
                if len(ops) == 1:
                    if m.startswith("store") and ops[0].tipo == "reg":
                        r[ops[0].valor] = r[ACC]
                    elif m.startswith("store"):
                        self.mem[self._direccion(ops[0])] = r[ACC]
                    else:
                        r[ACC] = self._valor(ops[0])
                elif ops[0].tipo == "reg":
                    r[ops[0].valor] = self._valor(ops[1])
                else:
                    self.mem[self._direccion(ops[0])] = self._valor(ops[1])
            else:
                raise AssertionError(f"el modelo no conoce {m}")
        raise AssertionError("el modelo no termino")


def ejecutar_y_comparar(fuente: str, sincronizar_acc=None, max_ciclos: int = 2_000_000):
    """Traduce, ejecuta en Enigma-64 y compara contra el modelo. Devuelve (resultado, modelo, ram)."""
    resultado = traducir_texto(fuente, sincronizar_acc=sincronizar_acc)
    assert resultado.errores == [], resultado.errores
    modelo = ModeloCacao(fuente, resultado.variables).ejecutar()
    _cpu, banco, ram = ejecutar_en_enigma(resultado.codigo, max_ciclos=max_ciclos)
    for registro in range(16):
        if registro == 13 or (registro == ACC and not resultado.acc_observable):
            continue
        obtenido = s64(resultado.tabla.leer_valor(registro, banco, ram))
        assert obtenido == modelo.r[registro], (
            f"R{registro}: Enigma-64={obtenido} modelo={modelo.r[registro]}\n{resultado.codigo}"
        )
    for direccion, esperado in modelo.mem.items():
        valor, _ = ram.mem_read(direccion, 8)
        assert s64(valor or 0) == esperado, f"memoria 0x{direccion:08X}"
    return resultado, modelo, ram


def leer_variable(resultado, ram, nombre: str) -> int:
    valor, _ = ram.mem_read(resultado.variables[nombre], 8)
    return s64(valor or 0)


# ---------------------------------------------------------------------------
# registros.py
# ---------------------------------------------------------------------------


class TestRegistros:
    @pytest.mark.parametrize("nombre,numero", [
        ("R0", 0), ("r7", 7), ("R12", 12), ("R15", 15), (3, 3),
        ("SP", 13), ("lr", 14), ("ACC", 15), ("ACM", 15),
    ])
    def test_numero_registro(self, nombre, numero):
        assert numero_registro(nombre) == numero

    @pytest.mark.parametrize("nombre", ["R16", "R99", "X1", "", 16, -1])
    def test_registro_invalido(self, nombre):
        with pytest.raises(RegistroInvalido):
            numero_registro(nombre)

    def test_tabla_por_defecto(self):
        tabla = TablaRegistros.por_defecto()
        assert [tabla.mapear_registro(n) for n in (0, 1, 2, 13)] == ["R1", "R2", "R3", "R6"]
        assert mapear_registro("R13") == "R6"
        assert tabla.ubicacion(3).ranura == 0
        assert tabla.mapear_registro(9, temporal=TMP1) == TMP1
        with pytest.raises(RegistroDerramado):
            mapear_registro(9)

    def test_r0_de_cacao_nunca_va_a_r0_de_enigma(self):
        tabla = TablaRegistros.desde_uso({0: 100, 1: 1})
        assert tabla.mapear_registro(0) != "R0"

    def test_sin_derrames_r7_es_residente(self):
        tabla = TablaRegistros.desde_uso({0: 5, 1: 4, 2: 3, 3: 2})
        assert not tabla.hay_derrames
        assert tabla.mapear_registro(3) == REG_BASE
        assert tabla.prologo() == []

    def test_con_derrames_los_mas_usados_son_residentes(self):
        tabla = TablaRegistros.desde_uso({0: 1, 4: 50, 7: 40, 9: 30, 12: 20, 15: 10})
        assert [tabla.mapear_registro(n) for n in (4, 7, 9)] == ["R1", "R2", "R3"]
        assert tabla.hay_derrames
        assert not tabla.es_residente(12) and not tabla.es_residente(0)
        assert tabla.prologo()  # inicializa BP

    def test_leer_y_escribir_derramado(self):
        tabla = TablaRegistros.por_defecto()
        assert tabla.leer(5, TMP1) == (TMP1, ["LOAD R4, [R7 + 16]"])
        assert tabla.escribir(5, TMP2) == (TMP2, ["STORE R5, [R7 + 16]"])
        assert tabla.leer(0, TMP1) == ("R1", [])

    def test_emisores_reemplazables(self):
        """El Integrante 1 puede inyectar su propia rutina de LOAD/STORE."""
        tabla = TablaRegistros({0: "R1"}, [5], emitir_load=lambda r, s: [f"MI_LOAD {r} {s}"])
        assert tabla.leer(5, TMP1) == (TMP1, ["MI_LOAD R4 0"])

    def test_tabla_rechaza_registros_reservados(self):
        with pytest.raises(ValueError):
            TablaRegistros({0: "R4"})


# ---------------------------------------------------------------------------
# alu.py: constantes, operandos y reglas LEX
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("valor", [
    0, 1, -1, 32767, -32768, 32768, -32769, 987654, 123456, 0x7FFFFFFF, -(1 << 31),
    (1 << 63) - 1, -(1 << 63), 0x0123456789ABCDEF, -0x0123456789ABCDEF,
])
def test_cargar_constante_en_el_emulador(valor):
    codigo = "\n".join(cargar_constante("R1", valor) + ["HLT"])
    _cpu, banco, _ram = ejecutar_en_enigma(codigo)
    assert s64(banco.leer_nombre("R1")) == valor


@pytest.mark.parametrize("texto,tipo,valor", [
    ("R3", "reg", 3), ("r15", "reg", 15), ("-25", "imm", -25), ("+7", "imm", 7),
    ("0x00000177", "mem", 0x177), ("[a]", "var", "a"), ("[R4]", "ind", 4),
    ("[0x10]", "mem", 0x10), ("LOOP", "etiqueta", "LOOP"), ("3.5", "float", 3.5),
])
def test_parsear_operando(texto, tipo, valor):
    op = parsear_operando(texto)
    assert (op.tipo, op.valor) == (tipo, valor)


def test_parsear_operando_registro_invalido():
    with pytest.raises(RegistroInvalido):
        parsear_operando("R16")


class TestReglasALU:
    @pytest.fixture
    def alu(self):
        return TraductorALU(TablaRegistros.por_defecto(), TraductorMemoria(reg_temporal=TMP2, reg_temporal_valor=TMP1),
                            acc_observable=False)

    @pytest.mark.parametrize("cacao,enigma", [
        ("ADD R0, R1", ["ADD R1, R1, R2"]),
        ("add r0, r1", ["ADD R1, R1, R2"]),
        ("SUB R0, 5", ["SUBI R1, R1, 5"]),
        ("ADD R0, -40000", ["ADDI R5, R0, -1", "SHL R5, R5, 16", "ADDI R5, R5, 25536", "ADD R1, R1, R5"]),
        ("MUL R0, 8", ["ADDI R5, R0, 8", "MUL R1, R1, R5"]),
        ("CMP R1, 0", ["CMP R2, R0"]),
        ("CMPZ R1", ["CMP R0, R2"]),
        ("NEG R1", ["SUB R2, R0, R2"]),
        ("INC R0", ["INC R1"]),
        ("NOT R2", ["NOT R3"]),
        ("TEST R0, R1", ["AND R4, R1, R2"]),
        ("SHR R0, 3", ["ASR R1, R1, 3"]),
        ("ROL R0, 8", ["SHR R5, R1, 56", "SHL R1, R1, 8", "OR R1, R1, R5"]),
        ("ROR R0, 8", ["SHL R5, R1, 56", "SHR R1, R1, 8", "OR R1, R1, R5"]),
        ("SWAP R0, R1", ["PUSH R1", "PUSH R2", "POP R1", "POP R2"]),
        ("ADD R0, [R1]", ["LOAD R5, [R2]", "ADD R1, R1, R5"]),
        ("INC R5", ["LOAD R4, [R7 + 16]", "INC R4", "STORE R4, [R7 + 16]"]),
        ("ADD R5, R6", ["LOAD R4, [R7 + 16]", "LOAD R5, [R7 + 24]", "ADD R4, R4, R5", "STORE R4, [R7 + 16]"]),
        ("MOVD R0, R1", ["ADD R1, R2, R0"]),
        ("MOVD R5, R0", ["STORE R1, [R7 + 16]"]),
        ("MOVH R5, 0", ["STORE R0, [R7 + 16]"]),
        ("ADD R15", ["LOAD R4, [R7 + 88]", "LOAD R5, [R7 + 88]", "ADD R4, R4, R5", "STORE R4, [R7 + 88]"]),
    ])
    def test_traduccion(self, alu, cacao, enigma):
        assert alu.traducir(cacao, banderas_vivas=False) == enigma
        assert alu.errores == []

    def test_mov_con_banderas_vivas_no_las_toca(self, alu):
        assert alu.traducir("MOVD R0, R1", banderas_vivas=True) == ["PUSH R2", "POP R1"]

    def test_div_registro_calcula_residuo(self, alu):
        assert alu.traducir("DIV R0, R1", banderas_vivas=False) == [
            "DIV R4, R1, R2", "MUL R5, R4, R2", "SUB R2, R1, R5", "ADD R1, R4, R0",
        ]

    def test_flotante_solo_aviso(self, alu):
        assert alu.traducir("FPADD R1, R2") == ["; [FPU sin traducir] FPADD R1, R2"]
        assert alu.errores == [] and len(alu.avisos) == 1

    @pytest.mark.parametrize("cacao,fragmento", [
        ("ADD R16, R1", "registro invalido"),
        ("SHL R1, R2", "modo de direccionamiento no soportado para SHL"),
        ("NEG 5", "modo de direccionamiento no soportado para NEG"),
        ("Add R1, R2", "mezcla mayusculas"),
    ])
    def test_errores_con_linea(self, alu, cacao, fragmento):
        assert alu.traducir(cacao, linea=42) == []
        assert alu.errores[0][0] == 42 and fragmento in alu.errores[0][1]


# ---------------------------------------------------------------------------
# traductor.py: programas reales de CacaoCore en el emulador
# ---------------------------------------------------------------------------


def _correr_ejemplo(nombre: str):
    resultado = traducir_texto((EJEMPLOS / nombre).read_text(encoding="utf-8"))
    assert resultado.errores == []
    ensamblar(resultado.codigo)
    _cpu, _banco, ram = ejecutar_en_enigma(resultado.codigo)
    return resultado, ram


def test_euclides_ejemplo():
    resultado, ram = _correr_ejemplo("euclides.asm")
    assert leer_variable(resultado, ram, "temp") == math.gcd(987654, 123456) == 6


@pytest.mark.parametrize("a,b", [(48, 18), (18, 48), (17, 5), (1071, 462), (7, 7), (1, 999), (2**40, 6**10)])
def test_euclides_contra_modelo(a, b):
    fuente = (EJEMPLOS / "euclides.asm").read_text(encoding="utf-8")
    fuente = fuente.replace("a: 987654", f"a: {a}").replace("b: 123456", f"b: {b}")
    resultado, _modelo, ram = ejecutar_y_comparar(fuente)
    assert leer_variable(resultado, ram, "temp") == math.gcd(a, b)


def test_euclides_por_restas_con_direcciones_hex():
    resultado, ram = _correr_ejemplo("euclides_resta.asm")
    assert leer_variable(resultado, ram, "temp") == math.gcd(756, 924)


def test_burbuja():
    resultado, ram = _correr_ejemplo("burbuja.asm")
    assert [leer_variable(resultado, ram, f"a{i}") for i in range(1, 6)] == [1, 3, 4, 5, 8]


def test_maximo():
    resultado, ram = _correr_ejemplo("maximo.asm")
    assert leer_variable(resultado, ram, "temp") == 10


def test_maximo_hex():
    resultado, ram = _correr_ejemplo("maximo_hex.asm")
    direccion = TraductorMemoria(base_datos=0x00201000).mapear_direccion(0x00040030)
    assert s64(ram.mem_read(direccion, 8)[0]) == 10


def test_cada_linea_lleva_la_instruccion_original():
    resultado, _ram = _correr_ejemplo("euclides.asm")
    for linea in resultado.codigo.splitlines():
        if linea.startswith("    ") and not linea.strip().startswith(";"):
            assert "; L" in linea or "; [" in linea, linea


def test_prueba_alu_completa():
    """spl/traductor/ejemplos/prueba_alu.asm usa todas las formas ALU de CacaoCore."""
    fuente = (EJEMPLOS / "prueba_alu.asm").read_text(encoding="utf-8")
    resultado, modelo, ram = ejecutar_y_comparar(fuente)
    assert resultado.acc_observable and resultado.tabla.hay_derrames
    mnemonicos = {ins.mnemonico for ins in modelo.programa.instrucciones}
    assert {"add", "sub", "mul", "div", "and", "or", "xor", "inc", "dec", "neg", "not",
            "cmp", "cmpz", "test", "shl", "shr", "rol", "ror", "swap"} <= mnemonicos
    assert leer_variable(resultado, ram, "fallos") == 0


def test_errores_reportan_linea_y_la_traduccion_continua():
    fuente = ".text\n    MOVD R1, 5\n    ADD R16, R1\n    FOO R1\n    SHL R1, R2\n    INC R1\n    HLT\n"
    resultado = traducir_texto(fuente)
    assert [linea for linea, _ in resultado.errores] == [3, 4, 5]
    assert "INC" in resultado.codigo and "HLT" in resultado.codigo


# ---------------------------------------------------------------------------
# Banderas: una instruccion que en CacaoCore no las toca no puede cambiarlas
# ---------------------------------------------------------------------------

_NEUTRAS = ["MOVD R9, R0", "MOVD R1, 40000", "MOVD R10, 7", "SWAP R0, R9", "ROL R1, 5",
            "LEA R11, [a]", "MOVD R12, [a]", "MOVD [a], R1", "STORED R2", "LOADD R3, 9"]


@pytest.mark.parametrize("salto", ["JZ", "JNZ", "JG", "JL", "JGE", "JLE", "JS", "JNS"])
@pytest.mark.parametrize("x,y", [(5, 5), (3, 9), (9, 3), (-4, 2)])
def test_banderas_sobreviven_a_instrucciones_neutras(salto, x, y):
    neutras = "\n".join(f"    {i}" for i in _NEUTRAS)
    fuente = f""".data
    a: 77
.text
    MOVD R0, {x}
    MOVD R1, {y}
    MOVD R2, 1
    MOVD R4, 2
    MOVD R5, 3
    MOVD R15, 4
    CMP R0, R1
{neutras}
    {salto} SI
    MOVD R8, 100
    HLT
SI:
    MOVD R8, 200
    HLT
"""
    resultado, modelo, _ram = ejecutar_y_comparar(fuente)
    assert "PUSH SR" in resultado.codigo
    assert modelo.r[8] in (100, 200)


# ---------------------------------------------------------------------------
# Programas aleatorios contra el modelo (presion de registros y derrames)
# ---------------------------------------------------------------------------

_REGS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15]


def _programa_aleatorio(rng: random.Random) -> str:
    reg = lambda: f"R{rng.choice(_REGS)}"  # noqa: E731
    imm = lambda: str(rng.choice([0, 1, -1, 7, 255, -300, 40000, -70000, rng.randint(-99, 99)]))  # noqa: E731
    var = lambda: f"[v{rng.randint(0, 3)}]"  # noqa: E731
    plantillas = [
        lambda: f"{rng.choice(['ADD', 'SUB', 'MUL', 'AND', 'OR', 'XOR'])} {reg()}, {reg()}",
        lambda: f"{rng.choice(['ADD', 'SUB', 'MUL', 'AND', 'OR', 'XOR'])} {reg()}, {imm()}",
        lambda: f"{rng.choice(['ADD', 'SUB', 'AND', 'OR', 'XOR'])} {reg()}, {var()}",
        lambda: f"{rng.choice(['ADD', 'SUB', 'XOR', 'OR'])} {rng.choice([reg(), imm(), var()])}",
        lambda: f"{rng.choice(['INC', 'DEC', 'NEG', 'NOT'])} {rng.choice([reg(), var()])}",
        lambda: f"{rng.choice(['SHL', 'SHR'])} {reg()}, {rng.randint(1, 63)}",
        lambda: f"{rng.choice(['ROL', 'ROR'])} {reg()}, {rng.randint(0, 70)}",
        lambda: f"{rng.choice(['SHL', 'SHR', 'ROL', 'ROR'])} {rng.randint(1, 63)}",
        lambda: f"SWAP {reg()}, {reg()}",
        lambda: f"SWAP {reg()}",
        lambda: f"MOVD {reg()}, {rng.choice([reg(), imm(), var()])}",
        lambda: f"MOVD {var()}, {rng.choice([reg(), imm()])}",
        lambda: f"STORED {reg()}" if rng.random() < 0.5 else f"LOADD {imm()}",
        lambda: f"DIV {reg()}, {rng.choice([reg(), str(rng.randint(1, 9))])}",
        lambda: f"PUSH {reg()}\n    POP {reg()}",
        lambda: (lambda p: f"LEA {p}, {var()}\n    {rng.choice(['ADD', 'XOR', 'CMP'])} {reg()}, [{p}]")(reg()),
    ]
    lineas = [".data"] + [f"    v{i}: {rng.randint(-50, 50)}" for i in range(4)] + [".text"]
    lineas += [f"    MOVD R{n}, {rng.randint(1, 60)}" for n in _REGS]
    for k in range(rng.randint(10, 30)):
        lineas.append("    " + rng.choice(plantillas)())
        if rng.random() < 0.25:  # sonda de banderas
            lineas.append(f"    {rng.choice(['CMP', 'TEST'])} {reg()}, {rng.choice([reg(), imm()])}")
            lineas.append("    " + rng.choice(["MOVD R3, R4", "SWAP R1, R2", "ROL R5, 9", "MOVD R6, 12345", f"LEA R7, {var()}"]))
            lineas.append(f"    {rng.choice(['JZ', 'JNZ', 'JG', 'JL', 'JGE', 'JLE'])} S{k}")
            lineas.append("    INC R8")
            lineas.append(f"S{k}:")
    lineas.append("    HLT")
    return "\n".join(lineas) + "\n"


@pytest.mark.parametrize("semilla", range(60))
@pytest.mark.parametrize("sincronizar_acc", [True, None])
def test_programas_aleatorios_contra_modelo(semilla, sincronizar_acc):
    rng = random.Random(semilla)
    for _ in range(20):
        fuente = _programa_aleatorio(rng)
        try:
            ModeloCacao(fuente, traducir_texto(fuente).variables).ejecutar()
        except OperandoNoValido:
            continue  # DIV con operandos que el modelo no cubre: se genera otro
        ejecutar_y_comparar(fuente, sincronizar_acc=sincronizar_acc)
        return
    pytest.skip("no se genero un programa valido")
