"""
Pruebas del traductor CacaoCore-64 -> Enigma-64: control de flujo, saltos,
pila y subrutinas (Integrante 3).

Ademas de probar cada regla LEX, cada programa se traduce, se ensambla con el
ensamblador de Enigma-64, se ejecuta en el emulador y su estado final se
compara con un modelo de la semantica de CacaoCore-64 (j_condicional,
jn_condicional, j_comparacion, call_m, ret, push y pop de
src/processor/microinstructions_mixin.py).
"""

from __future__ import annotations

import pytest

from enigma64.ensamblador import ensamblar
from enigma64.registros import SP_RESET
from spl.traductor.alu import modifica_banderas
from spl.traductor.control import MNEMONICOS_CONTROL, NO_CACAO, SALTOS, TraductorControl, lee_lr
from spl.traductor.registros import ACC, LR_CACAO, SP_CACAO, TablaRegistros
from spl.traductor.traductor import (
    BASE_CODIGO,
    TraductorCacaoEnigma,
    ejecutar_en_enigma,
    traducir_texto,
)

MASK64 = (1 << 64) - 1


def s64(valor: int) -> int:
    valor &= MASK64
    return valor - (1 << 64) if valor >> 63 else valor


# ---------------------------------------------------------------------------
# Modelo de referencia de CacaoCore-64
# ---------------------------------------------------------------------------

# Condicion de cada salto en CacaoCore (Z y S = N); jc/jnc/jo/jno no se modelan
SALTO_TOMADO = {
    "jmp": lambda z, n: True,
    "jz": lambda z, n: z, "je": lambda z, n: z,
    "jnz": lambda z, n: not z, "jne": lambda z, n: not z,
    "js": lambda z, n: n, "jns": lambda z, n: not n,
    "jl": lambda z, n: n and not z, "jg": lambda z, n: not n and not z,
    "jge": lambda z, n: not n or z, "jle": lambda z, n: n or z,
}


class ModeloCacao:
    """
    Interprete minimo de CacaoCore-64 para los programas de estas pruebas.

    Una direccion de retorno se modela como ("retorno", indice): su valor
    numerico es distinto en cada maquina, pero se mueve igual por registros y
    pila.
    """

    def __init__(self, fuente: str, direcciones: dict[str, int]) -> None:
        self.programa = TraductorCacaoEnigma().analizar(fuente)
        self.r: list = [0] * 16
        self.mem = {direcciones[n]: s64(bits) for n, (bits, _) in self.programa.variables.items()}
        self.dir = direcciones
        self.z = self.n = 0
        self.pila: list = []

    def _valor(self, op):
        if op.tipo == "reg":
            return self.r[op.valor]
        if op.tipo == "imm":
            return op.valor
        return self.mem[self.dir[op.valor]]

    def _banderas(self, valor: int) -> None:
        self.z, self.n = int(valor == 0), int(valor < 0)

    def ejecutar(self, limite: int = 200_000) -> "ModeloCacao":
        instrucciones, etiquetas = self.programa.instrucciones, self.programa.etiquetas
        pc = 0
        for _ in range(limite):
            if pc >= len(instrucciones):
                return self
            ins = instrucciones[pc]
            pc += 1
            m, ops = ins.mnemonico, ins.operandos
            if m == "hlt":
                return self
            if m in SALTO_TOMADO:
                if SALTO_TOMADO[m](self.z, self.n):
                    pc = etiquetas[ops[0].valor]
            elif m == "call":  # call_m: LR = PC; push(LR); jmp
                self.r[LR_CACAO] = ("retorno", pc)
                self.pila.append(self.r[LR_CACAO])
                pc = etiquetas[ops[0].valor]
            elif m == "ret":  # ret: pop(LR); PC = LR
                self.r[LR_CACAO] = self.pila.pop()
                pc = self.r[LR_CACAO][1]
            elif m == "push":
                self.pila.append(self.r[ops[0].valor])
            elif m == "pop":
                self.r[ops[0].valor] = self.pila.pop()
            elif m.startswith("mov"):
                if ops[0].tipo == "reg":
                    self.r[ops[0].valor] = self._valor(ops[1])
                else:
                    self.mem[self.dir[ops[0].valor]] = self._valor(ops[1])
            elif m in ("add", "sub", "mul"):
                a, b = self.r[ops[0].valor], self._valor(ops[1])
                resultado = s64({"add": a + b, "sub": a - b, "mul": a * b}[m])
                self.r[ops[0].valor] = self.r[ACC] = resultado
                self._banderas(resultado)
            elif m == "cmp":
                self._banderas(s64(self.r[ops[0].valor] - self._valor(ops[1])))
            else:
                raise AssertionError(f"el modelo no conoce {m}")
        raise AssertionError("el modelo no termino")


def ejecutar_y_comparar(fuente: str):
    """Traduce, ejecuta en Enigma-64 y compara contra el modelo. Devuelve (resultado, modelo, banco, ram)."""
    resultado = traducir_texto(fuente)
    assert resultado.errores == [], resultado.errores
    modelo = ModeloCacao(fuente, resultado.variables).ejecutar()
    _cpu, banco, ram = ejecutar_en_enigma(resultado.codigo)
    usados = {int(cacao.split()[0][1:]) for cacao, _ in resultado.tabla.filas()}
    for registro in sorted(usados - {SP_CACAO, LR_CACAO, ACC}):
        esperado = modelo.r[registro]
        if isinstance(esperado, tuple):  # direccion de retorno: distinta en cada maquina
            continue
        obtenido = s64(resultado.tabla.leer_valor(registro, banco, ram))
        assert obtenido == esperado, (
            f"R{registro}: Enigma-64={obtenido} modelo={esperado}\n{resultado.codigo}"
        )
    for nombre, direccion in resultado.variables.items():
        valor, _ = ram.mem_read(direccion, 8)
        assert s64(valor or 0) == modelo.mem[direccion], f"variable {nombre}"
    # La pila de Enigma-64 queda con tantas palabras como la de CacaoCore
    assert SP_RESET - banco.sp == 8 * len(modelo.pila)
    return resultado, modelo, banco, ram


def leer_variable(resultado, ram, nombre: str) -> int:
    valor, _ = ram.mem_read(resultado.variables[nombre], 8)
    return s64(valor or 0)


# ---------------------------------------------------------------------------
# Reglas LEX de control.py
# ---------------------------------------------------------------------------


class TestReglasControl:
    @pytest.fixture
    def control(self):
        # Tabla por defecto: R0->R1, R1->R2, R2->R3, R13->R6; R3.. derramados (R9 en [R7 + 48])
        return TraductorControl(TablaRegistros.por_defecto(), etiquetas={"LOOP", "FIN", "F"})

    @pytest.mark.parametrize("cacao,enigma", [
        ("LOOP:", ["LOOP:"]),
        ("LOOP :", ["LOOP:"]),
        ("JMP LOOP", ["JMP LOOP"]),
        ("jmp LOOP", ["JMP LOOP"]),
        ("JMP\tLOOP   ; comentario", ["JMP LOOP"]),
        ("JZ FIN", ["JZ FIN"]),
        ("JE FIN", ["JZ FIN"]),
        ("JNZ FIN", ["JNZ FIN"]),
        ("JNE FIN", ["JNZ FIN"]),
        ("JC FIN", ["JC FIN"]),
        ("JNC FIN", ["JNC FIN"]),
        ("JS FIN", ["JN FIN"]),
        ("JNS FIN", ["JP FIN", "JZ FIN"]),
        ("JO FIN", ["JV FIN"]),
        ("JNO FIN", ["JNV FIN"]),
        ("JL FIN", ["JN FIN"]),
        ("JG FIN", ["JP FIN"]),
        ("JGE FIN", ["JP FIN", "JZ FIN"]),
        ("jle FIN", ["JN FIN", "JZ FIN"]),
        ("CALL F", ["CALL F"]),
        ("RET", ["RET"]),
        ("ret", ["RET"]),
        ("HLT", ["HLT"]),
        ("PUSH R0", ["PUSH R1"]),
        ("pop r2", ["POP R3"]),
        ("PUSH R13", ["PUSH R6"]),
        ("POP R13", ["POP R6"]),
        ("PUSH R9", ["LOAD R4, [R7 + 48]", "PUSH R4"]),
        ("POP R9", ["POP R4", "STORE R4, [R7 + 48]"]),
    ])
    def test_traduccion(self, control, cacao, enigma):
        assert control.traducir(cacao, linea=3) == enigma
        assert control.errores == []

    def test_call_y_ret_con_lr_observable(self):
        control = TraductorControl(TablaRegistros({0: "R1", 14: "R2"}), {"F"}, lr_observable=True)
        assert control.traducir("CALL F") == [
            "CALL _lr_ida_0", "JMP _lr_vuelta_0",
            "_lr_ida_0:", "POP R2", "PUSH R2", "JMP F",
            "_lr_vuelta_0:",
        ]
        assert control.traducir("CALL F")[0] == "CALL _lr_ida_1"  # etiquetas unicas
        assert control.traducir("RET") == ["POP R2", "JMPR R2"]
        assert control.errores == []

    def test_call_y_ret_con_lr_derramado(self):
        # Tabla por defecto: R14 vive en la ranura 10 ([R7 + 80])
        control = TraductorControl(TablaRegistros.por_defecto(), {"F"}, lr_observable=True)
        assert control.traducir("CALL F") == [
            "CALL _lr_ida_0", "JMP _lr_vuelta_0",
            "_lr_ida_0:", "POP R4", "STORE R4, [R7 + 80]", "PUSH R4", "JMP F",
            "_lr_vuelta_0:",
        ]
        assert control.traducir("RET") == ["POP R4", "STORE R4, [R7 + 80]", "JMPR R4"]

    @pytest.mark.parametrize("cacao,fragmento", [
        ("JMP NOEXISTE", "etiqueta no definida 'NOEXISTE'"),
        ("CALL NOEXISTE", "etiqueta no definida 'NOEXISTE'"),
        ("jmp externa", "etiqueta no definida 'externa'"),
        ("JMP 0x00001010", "salto a direccion absoluta no soportado"),
        ("CALL 0x10", "salto a direccion absoluta no soportado"),
        ("JZ R1", "modo de direccionamiento no soportado para JZ"),
        ("JMP [a]", "modo de direccionamiento no soportado para JMP"),
        ("JMP", "modo de direccionamiento no soportado para JMP"),
        ("PUSH 5", "modo de direccionamiento no soportado para PUSH"),
        ("POP [a]", "modo de direccionamiento no soportado para POP"),
        ("RET R1", "modo de direccionamiento no soportado para RET"),
        ("HLT 0", "modo de direccionamiento no soportado para HLT"),
        ("PUSH R16", "registro invalido 'R16'"),
        ("JMP R16", "registro invalido 'R16'"),
        ("Jmp FIN", "mezcla mayusculas y minusculas"),
        ("loop:", "etiqueta invalida"),
        ("JU FIN", "sin equivalente en Enigma-64"),
        ("JNU 0x10", "sin equivalente en Enigma-64"),
    ])
    def test_errores_con_linea(self, control, cacao, fragmento):
        codigo = control.traducir(cacao, linea=42)
        assert len(control.errores) == 1
        assert control.errores[0][0] == 42 and fragmento in control.errores[0][1]
        assert all(linea.startswith(";") for linea in codigo)  # no se emite codigo ejecutable

    @pytest.mark.parametrize("mnemonico", sorted(NO_CACAO))
    def test_instrucciones_que_cacaocore_no_tiene(self, control, mnemonico):
        operando = {"jmpr": " R1", "callr": " R2", "enter": " 16", "leave": ""}.get(mnemonico, " FIN")
        codigo = control.traducir(f"{mnemonico.upper()}{operando}", linea=8)
        assert len(control.errores) == 1 and control.errores[0][0] == 8
        assert f"'{mnemonico.upper()}' no es una instruccion de CacaoCore-64" in control.errores[0][1]
        assert all(linea.startswith(";") for linea in codigo)

    def test_etiqueta_e_instruccion_en_la_misma_linea(self, control):
        """CacaoCore exige la etiqueta sola en su linea (LABEL COLON NEWLINE en asm_parser.py)."""
        assert control.traducir("LOOP: HLT", linea=5) == [
            "; ERROR: la etiqueta debe ir sola en su linea, como en CacaoCore-64: 'LOOP: HLT'"
        ]
        assert control.errores == [(5, "la etiqueta debe ir sola en su linea, como en CacaoCore-64: 'LOOP: HLT'")]

    @pytest.mark.parametrize("lr_observable", [False, True])
    @pytest.mark.parametrize("tabla", [TablaRegistros.por_defecto(), TablaRegistros({0: "R1", 14: "R2"})])
    def test_el_control_nunca_modifica_banderas(self, tabla, lr_observable):
        """Ninguna traduccion de control escribe banderas: no hace falta PUSH SR / POP SR."""
        control = TraductorControl(tabla, {"F"}, lr_observable)
        textos = ["F:", "RET", "HLT"] + [f"{m.upper()} F" for m in SALTOS]
        textos += [f"{m} R{n}" for m in ("PUSH", "POP") for n in range(16)]
        for texto in textos:
            codigo = control.traducir(texto)
            assert codigo and not any(modifica_banderas(c) for c in codigo), texto
        assert control.errores == []


def test_el_driver_envia_a_control_py_todos_sus_mnemonicos():
    fuente = ".text\n" + "\n".join(f"    {m.upper()} X" for m in sorted(MNEMONICOS_CONTROL)) + "\nX:\n"
    programa = TraductorCacaoEnigma().analizar(fuente)
    assert {ins.clase for ins in programa.instrucciones} == {"control"}


@pytest.mark.parametrize("cuerpo,observable", [
    ("MOVD R1, 5", False),
    ("POP R14", False),
    ("MOVD R1, R14", True),
    ("PUSH R14", True),
    ("CMP R14, R1", True),
])
def test_lee_lr(cuerpo, observable):
    programa = TraductorCacaoEnigma().analizar(f".text\n    {cuerpo}\n    HLT\n")
    assert lee_lr(programa.instrucciones) is observable


def test_errores_del_programa_completo_reportan_linea():
    fuente = (".text\n    JMP NOEXISTE\n    JMP 0x00001010\n    JU FIN\n    JN FIN\n"
              "    ENTER 16\n    PUSH 5\n    Jmp FIN\nFIN:\n    HLT\n")
    resultado = traducir_texto(fuente)
    assert [linea for linea, _ in resultado.errores] == [2, 3, 4, 5, 6, 7, 8]
    assert "FIN:" in resultado.codigo.splitlines()
    assert any(linea.split(";")[0].strip() == "HLT" for linea in resultado.codigo.splitlines())


# ---------------------------------------------------------------------------
# Saltos condicionales en el emulador
# ---------------------------------------------------------------------------

_VERDAD = {
    "jz": lambda x, y: x == y, "je": lambda x, y: x == y,
    "jnz": lambda x, y: x != y, "jne": lambda x, y: x != y,
    "jl": lambda x, y: x < y, "jg": lambda x, y: x > y,
    "jge": lambda x, y: x >= y, "jle": lambda x, y: x <= y,
    "js": lambda x, y: x - y < 0, "jns": lambda x, y: x - y >= 0,
}


@pytest.mark.parametrize("salto", sorted(_VERDAD))
@pytest.mark.parametrize("x,y", [(5, 5), (3, 9), (9, 3), (-4, 2), (2, -4), (0, 0), (-9, -2), (-2, -9)])
def test_saltos_condicionales(salto, x, y):
    fuente = f""".data
    r: 0
.text
    MOVD R0, {x}
    MOVD R1, {y}
    CMP R0, R1
    {salto.upper()} SI
    MOVD R2, 100
    JMP FIN
SI:
    MOVD R2, 200
FIN:
    MOVD [r], R2
    HLT
"""
    resultado, _modelo, _banco, ram = ejecutar_y_comparar(fuente)
    assert leer_variable(resultado, ram, "r") == (200 if _VERDAD[salto](x, y) else 100)


@pytest.mark.parametrize("salto", ["JZ", "JNZ", "JG", "JL", "JGE", "JLE", "JS", "JNS"])
@pytest.mark.parametrize("x,y", [(5, 5), (3, 9), (9, 3)])
def test_banderas_sobreviven_a_pila_y_subrutinas(salto, x, y):
    """CMP; PUSH; CALL; POP; Jcc con registros derramados: las banderas llegan intactas."""
    fuente = f""".data
    r: 0
.text
    MOVD R0, {x}
    MOVD R1, {y}
    MOVD R3, 3
    MOVD R4, 4
    MOVD R5, 5
    MOVD R6, 6
    MOVD R7, 7
    MOVD R8, 8
    MOVD R9, 9
    CMP R0, R1
    PUSH R9
    CALL NADA
    POP R8
    {salto} SI
    MOVD R2, 100
    JMP FIN
SI:
    MOVD R2, 200
FIN:
    MOVD [r], R2
    HLT
NADA:
    PUSH R7
    POP R6
    RET
"""
    resultado, modelo, _banco, ram = ejecutar_y_comparar(fuente)
    assert resultado.tabla.hay_derrames
    assert "PUSH SR" not in resultado.codigo  # el control no necesita proteger las banderas
    assert leer_variable(resultado, ram, "r") == (200 if _VERDAD[salto.lower()](x, y) else 100)
    assert modelo.r[8] == 9 and modelo.r[6] == 7


# ---------------------------------------------------------------------------
# Subrutinas y pila
# ---------------------------------------------------------------------------

FACTORIAL = """.data
    res: 0
.text
    MOVD R0, {n}
    CALL FACT
    MOVD [res], R1
    HLT
FACT:
    CMP R0, 1
    JG RECURSE
    MOVD R1, 1
    RET
RECURSE:
    PUSH R0
    SUB R0, 1
    CALL FACT
    POP R0
    MUL R1, R0
    RET
"""

FIBONACCI = """.data
    res: 0
.text
    MOVD R0, {n}
    CALL FIB
    MOVD [res], R1
    HLT
FIB:
    CMP R0, 2
    JL BASE
    PUSH R0
    SUB R0, 1
    CALL FIB
    POP R0
    PUSH R1
    PUSH R0
    SUB R0, 2
    CALL FIB
    POP R0
    POP R2
    ADD R1, R2
    RET
BASE:
    MOVD R1, R0
    RET
"""


@pytest.mark.parametrize("n,esperado", [(0, 1), (1, 1), (2, 2), (5, 120), (6, 720), (10, 3628800)])
def test_factorial_recursivo(n, esperado):
    resultado, _modelo, _banco, ram = ejecutar_y_comparar(FACTORIAL.format(n=n))
    assert leer_variable(resultado, ram, "res") == esperado


@pytest.mark.parametrize("n,esperado", [(0, 0), (1, 1), (2, 1), (7, 13), (10, 55)])
def test_fibonacci_recursivo(n, esperado):
    resultado, _modelo, _banco, ram = ejecutar_y_comparar(FIBONACCI.format(n=n))
    assert leer_variable(resultado, ram, "res") == esperado


# Forma exacta que emite el compilador de CacaoCore (generador_codigo.py:
# p_expr_call_args, p_func_def, p_deliver_val) para
#     func a (b : int, c : int) { let banana : int  set banana = b + c  deliver banana }
#     let res : int   set res = a(X, Y)
# El llamado saca la direccion de retorno con POP, saca los argumentos y la
# vuelve a meter con PUSH antes del cuerpo.
FUNCION_COMPILADA = """.data
b : 0
c : 0
banana : 0
btemp : 0
ctemp : 0
res : 0
.text
MOVD R0, {x}
PUSH R0
MOVD R0, {y}
PUSH R0
CALL A
MOVD R0, R1
MOVD [res], R0
HLT
A:
POP R2
MOVD R0 , [c]
MOVD [ctemp], R0
POP R0
MOVD [c], R0
MOVD R0 , [b]
MOVD [btemp], R0
POP R0
MOVD [b], R0
PUSH R2
MOVD [banana], 0
MOVD R0, [b]
ADD R0, [c]
MOVD [banana], R0
MOVD R1, [banana]
RET
MOVD R0, [ctemp]
MOVD [c], R0
MOVD R0, [btemp]
MOVD [b], R0
RET
"""


@pytest.mark.parametrize("x,y", [(2, 3), (40, -2), (0, 0)])
def test_protocolo_de_llamada_del_compilador_de_cacaocore(x, y):
    resultado, _modelo, _banco, ram = ejecutar_y_comparar(FUNCION_COMPILADA.format(x=x, y=y))
    assert leer_variable(resultado, ram, "res") == x + y
    assert not lee_lr(TraductorCacaoEnigma().analizar(FUNCION_COMPILADA).instrucciones)
    assert "JMPR" not in resultado.codigo  # sin LR observable, CALL y RET van directos


# Subrutinas VEC_SUM y VEC_MAX copiadas de src/Libraries/lib_vectores.asm de
# CacaoCore-64 (mnemonicos en minuscula, jge/jle/jmp y ret)
VECTORES = """.data
    v0: 7
    v1: -3
    v2: 12
    v3: 5
    v4: 9
    suma: 0
    maximo: 0
.text
    LEA R0, [v0]
    MOVD R1, 5
    CALL VEC_SUM
    MOVD [suma], R5
    CALL VEC_MAX
    MOVD [maximo], R5
    HLT
VEC_SUM:
    movd r5, 0
    movd r2, 0
    movd r4, r0
LOOP_SUM:
    cmp r2, r1
    jge END_SUM
    movd r3, [r4]
    add r5, r3
    add r4, 8
    add r2, 1
    jmp LOOP_SUM
END_SUM:
    ret
VEC_MAX:
    movd r5, [r0]
    movd r2, 1
    movd r4, r0
    add r4, 8
LOOP_MAX:
    cmp r2, r1
    jge END_MAX
    movd r3, [r4]
    cmp r3, r5
    jle NO_UPDATE_MAX
    movd r5, r3
NO_UPDATE_MAX:
    add r4, 8
    add r2, 1
    jmp LOOP_MAX
END_MAX:
    ret
"""


def test_subrutinas_de_lib_vectores():
    resultado = traducir_texto(VECTORES)
    assert resultado.errores == []
    _cpu, banco, ram = ejecutar_en_enigma(resultado.codigo)
    assert leer_variable(resultado, ram, "suma") == 7 - 3 + 12 + 5 + 9
    assert leer_variable(resultado, ram, "maximo") == 12
    assert banco.sp == SP_RESET


# ---------------------------------------------------------------------------
# LR (R14) observable
# ---------------------------------------------------------------------------

# F devuelve el control con la direccion que dejo CALL en LR: solo funciona si
# CALL escribe LR igual que call_m de CacaoCore.
RETORNO_POR_LR = """.data
    r: 0
.text
    MOVD R1, 0
    CALL F
    MOVD R1, 1
    MOVD [r], R1
    HLT
F:
    MOVD R2, R14
    POP R3
    PUSH R2
    RET
"""


def _direccion_valida_de_codigo(codigo: str, valor: int) -> bool:
    return BASE_CODIGO <= valor < BASE_CODIGO + len(ensamblar(codigo))


def test_call_escribe_lr_con_la_direccion_de_retorno():
    resultado, modelo, banco, ram = ejecutar_y_comparar(RETORNO_POR_LR)
    assert "JMPR" in resultado.codigo
    assert leer_variable(resultado, ram, "r") == 1
    lr, r2, r3 = (resultado.tabla.leer_valor(n, banco, ram) for n in (LR_CACAO, 2, 3))
    assert lr == r2 == r3 and _direccion_valida_de_codigo(resultado.codigo, lr)
    assert modelo.r[LR_CACAO] == modelo.r[2] == modelo.r[3]


def test_llamadas_anidadas_y_lr_restaurado():
    fuente = """.data
    r: 0
.text
    CALL F
    MOVD [r], R1
    HLT
F:
    MOVD R5, R14
    CALL G
    MOVD R6, R14
    MOVD R14, R5
    MOVD R1, 7
    RET
G:
    RET
"""
    resultado, modelo, banco, ram = ejecutar_y_comparar(fuente)
    assert leer_variable(resultado, ram, "r") == 7
    r5, r6 = (resultado.tabla.leer_valor(n, banco, ram) for n in (5, 6))
    assert r5 != r6 and all(_direccion_valida_de_codigo(resultado.codigo, v) for v in (r5, r6))
    assert modelo.r[5] != modelo.r[6]


def test_lr_derramado():
    """Con muchos registros en uso, LR vive en una ranura de derrame."""
    cuerpo = "\n".join(f"    MOVD R{n}, {n}\n    ADD R{n}, R{n}" for n in (0, 4, 5, 6, 7, 8, 9))
    fuente = RETORNO_POR_LR.replace("    MOVD R1, 0\n", f"    MOVD R1, 0\n{cuerpo}\n")
    resultado, _modelo, _banco, ram = ejecutar_y_comparar(fuente)
    assert not resultado.tabla.es_residente(LR_CACAO)
    assert leer_variable(resultado, ram, "r") == 1


def test_etiquetas_generadas_no_chocan_con_las_del_programa():
    fuente = RETORNO_POR_LR.replace("F:", "_LR_IDA_0:\nF:")
    resultado, _modelo, _banco, ram = ejecutar_y_comparar(fuente)
    assert "_LR_IDA_0:" in resultado.codigo and "_lr_ida_0:" in resultado.codigo
    assert leer_variable(resultado, ram, "r") == 1
