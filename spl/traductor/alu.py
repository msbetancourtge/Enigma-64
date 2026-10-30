"""
Traductor CacaoCore-64 -> Enigma-64: operaciones de la ALU (Integrante 2).

Reglas LEX (ply.lex) que reconocen cada forma de las instrucciones ALU de
CacaoCore-64 y cuyas acciones emiten la secuencia equivalente con las 16
operaciones de la ALU de Enigma-64:

    ADD SUB MUL DIV ADDI SUBI INC DEC AND OR XOR NOT SHL SHR ASR CMP

Sintaxis de Enigma-64 (enigma64/ensamblador.py):
    OP Rd, Rs1, Rs2       ADD SUB MUL DIV AND OR XOR       (tres operandos)
    OPI Rd, Rs1, imm16    ADDI SUBI SHL SHR ASR            (imm con signo)
    OP Rd                 INC DEC NOT                      (Rd = op Rd)
    CMP Rs1, Rs2          solo banderas

Semantica de origen, tomada del emulador de CacaoCore
(src/processor/microinstructions_mixin.py y alu.py):
  * La ALU de CacaoCore es de acumulador: toda operacion aritmetico-logica
    deja el resultado en ACC (R15) y, en las formas de dos operandos, lo copia
    al destino. ADD R1, R2 deja R1 = ACC = R1 + R2.
  * DIV Rx, Ry deja el cociente en Rx (y en ACC) y el RESIDUO en Ry. El
    algoritmo de Euclides de CacaoCore depende de esto.
  * CMPZ Rx compara 0 contra Rx (banderas de 0 - Rx).
  * SHR es aritmetico (desplaza el valor con signo), por eso se traduce a ASR.
  * MOV, SWAP, ROL y ROR no modifican banderas.

Registros de trabajo: TMP1 (R4) para el primer operando o resultado
derramado, TMP2 (R5) para el segundo operando, inmediatos y direcciones.

Autor: Integrante 2 Tomas Garzon - Registros & ALU (Tarea 27)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, FrozenSet, List, Optional, Sequence, Set, Tuple

import ply.lex as lex
from ply.lex import TOKEN

from .registros import (
    ACC,
    REG_CERO,
    TMP1,
    TMP2,
    RegistroInvalido,
    TablaRegistros,
    numero_registro,
)

# ---------------------------------------------------------------------------
# Seccion de definiciones LEX. Las expresiones son las de
# src/assembler/asm_lexer.py de CacaoCore (REGISTER, NUMBER, MEMORY, VAR),
# con anclas de fin de token para que una regla no reconozca un prefijo.
# ---------------------------------------------------------------------------

_ESP = r"[ \t]*"
_ESP1 = r"[ \t]+"
_COMA = _ESP + "," + _ESP

REGISTRO = r"[Rr](?:1[0-5]|[0-9])(?![A-Za-z0-9_])"  # (R|r)(1[0-5]|[0-9])
NUMERO = r"[+-]?\d+(?![\d.xX])"  # [+-]?\d+ (no flotante, no hexadecimal)
FLOTANTE = r"[+-]?\d+\.\d+"  # [+-]?(\d+\.\d+)
MEMORIA = r"0x[0-9A-Fa-f]+"  # 0x... : direccion de memoria directa
VARIABLE = r"[a-z_][a-z0-9_]*"  # identificador en minuscula: variable de .data
ETIQUETA = r"[A-Z_][A-Z0-9_]*"  # identificador en MAYUSCULA: etiqueta
DIRECTO = rf"(?:{MEMORIA}|\[{_ESP}(?:{VARIABLE}|{MEMORIA}){_ESP}\])"  # 0x10, [a], [0x10]
INDIRECTO = rf"\[{_ESP}{REGISTRO}{_ESP}\]"  # [R3]
FIN = r"(?=[ \t]*(?:[;\#]|$))"  # fin de instruccion: comentario o fin de linea


def _mnemonicos(*nombres: str) -> str:
    """CacaoCore acepta un mnemonico todo en minuscula o todo en MAYUSCULA."""
    variantes = sorted({v for n in nombres for v in (n.lower(), n.upper())}, key=len, reverse=True)
    return "(?:" + "|".join(variantes) + r")(?![A-Za-z0-9_])"


OPS_BINARIAS = ("add", "sub", "mul", "div", "and", "or", "xor")
OPS_COMPARACION = ("cmp", "test")
OPS_UNARIAS = ("inc", "dec", "neg", "not", "cmpz")
OPS_DESPLAZAMIENTO = ("shl", "shr", "rol", "ror")
OPS_FLOTANTE = ("fpadd", "fpsub", "fpmul", "fpdiv", "fpneg", "fpcmp", "fpsqrt", "fptof", "fptoi")
MOVS = ("movb", "movh", "movw", "movd")
LOADS = ("loadb", "loadh", "loadw", "loadd")
STORES = ("storeb", "storeh", "storew", "stored")

# Mnemonicos que siempre traduce este modulo
MNEMONICOS_ALU: FrozenSet[str] = frozenset(
    OPS_BINARIAS + OPS_COMPARACION + OPS_UNARIAS + OPS_DESPLAZAMIENTO + ("swap",) + OPS_FLOTANTE
)
# Transferencias: este modulo traduce sus formas registro/inmediato; las
# formas con memoria son del Integrante 1 (spl/traductor/memoria.py).
MNEMONICOS_TRANSFERENCIA: FrozenSet[str] = frozenset(MOVS + LOADS + STORES)

# Instrucciones de Enigma-64 que escriben banderas en el SR
ENIGMA_MODIFICAN_BANDERAS: FrozenSet[str] = frozenset(
    {"ADD", "SUB", "MUL", "DIV", "ADDI", "SUBI", "INC", "DEC",
     "AND", "OR", "XOR", "NOT", "SHL", "SHR", "ASR", "CMP"}
)

_INT16_MIN, _INT16_MAX = -0x8000, 0x7FFF
_MASK64 = (1 << 64) - 1


def modifica_banderas(instruccion: str) -> bool:
    """True si la instruccion Enigma-64 (texto) escribe banderas."""
    partes = instruccion.split(None, 1)
    return bool(partes) and partes[0].upper() in ENIGMA_MODIFICAN_BANDERAS


def _con_signo64(valor: int) -> int:
    valor &= _MASK64
    return valor - (1 << 64) if valor >> 63 else valor


def cargar_constante(registro: str, valor: int) -> List[str]:
    """
    Carga una constante de 64 bits en `registro` usando solo ADDI y SHL.

    El inmediato de ADDI es de 16 bits con extension de signo, asi que el
    valor se parte en trozos de 16 bits de arriba hacia abajo:
        hi = (v + 0x8000) >> 16,  lo = v - (hi << 16)  con lo en [-32768, 32767]
    Para direcciones de 32 bits coincide con la secuencia ADDI + SHL + ADDI
    del Integrante 1; aqui se generaliza a cualquier constante de 64 bits.
    """
    valor = _con_signo64(valor)
    if _INT16_MIN <= valor <= _INT16_MAX:
        return [f"ADDI {registro}, {REG_CERO}, {valor}"]
    alto = (valor + 0x8000) >> 16
    bajo = valor - (alto << 16)
    secuencia = cargar_constante(registro, alto) + [f"SHL {registro}, {registro}, 16"]
    if bajo:
        secuencia.append(f"ADDI {registro}, {registro}, {bajo}")
    return secuencia


# ---------------------------------------------------------------------------
# Operandos
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Operando:
    """Operando de CacaoCore ya clasificado."""

    tipo: str  # reg | imm | mem (hex directa) | var ([a]) | ind ([Rx]) | etiqueta | float | texto
    valor: object
    texto: str

    @property
    def registro(self) -> Optional[int]:
        """Registro de CacaoCore que aparece en el operando (Rx o [Rx])."""
        return self.valor if self.tipo in ("reg", "ind") else None

    @property
    def es_memoria(self) -> bool:
        return self.tipo in ("mem", "var", "ind")


def parsear_operando(texto: str) -> Operando:
    """Clasifica un operando con las mismas expresiones que el lexer de CacaoCore."""
    t = texto.strip()
    if re.fullmatch(REGISTRO, t):
        return Operando("reg", numero_registro(t), t)
    if re.fullmatch(r"[Rr]\d+", t):
        raise RegistroInvalido(f"registro invalido '{t}' (CacaoCore tiene R0..R15)")
    if re.fullmatch(NUMERO, t):
        return Operando("imm", int(t), t)
    if re.fullmatch(FLOTANTE, t):
        return Operando("float", float(t), t)
    if re.fullmatch(MEMORIA, t):
        return Operando("mem", int(t, 16), t)
    interior = re.fullmatch(r"\[\s*(.*?)\s*\]", t)
    if interior:
        dentro = interior.group(1)
        if re.fullmatch(REGISTRO, dentro):
            return Operando("ind", numero_registro(dentro), t)
        if re.fullmatch(r"[Rr]\d+", dentro):
            raise RegistroInvalido(f"registro invalido '{dentro}' (CacaoCore tiene R0..R15)")
        if re.fullmatch(VARIABLE, dentro):
            return Operando("var", dentro, t)
        if re.fullmatch(MEMORIA, dentro):
            return Operando("mem", int(dentro, 16), t)
    if re.fullmatch(ETIQUETA, t) or re.fullmatch(VARIABLE, t):
        return Operando("etiqueta", t, t)
    return Operando("texto", t, t)


def separar_operandos(texto: str) -> List[str]:
    """Separa operandos por comas que no esten dentro de corchetes."""
    partes, actual, nivel = [], [], 0
    for caracter in texto:
        if caracter == "[":
            nivel += 1
        elif caracter == "]":
            nivel = max(0, nivel - 1)
        if caracter == "," and nivel == 0:
            partes.append("".join(actual).strip())
            actual = []
        else:
            actual.append(caracter)
    if "".join(actual).strip():
        partes.append("".join(actual).strip())
    return partes


def dividir_instruccion(texto: str) -> Tuple[str, List[Operando]]:
    """'ADD R1, [a]' -> ('add', [Operando reg, Operando var])."""
    texto = re.split(r"[;#]", texto, maxsplit=1)[0].strip()
    partes = texto.split(None, 1)
    mnemonico = partes[0].lower() if partes else ""
    operandos = [parsear_operando(o) for o in separar_operandos(partes[1])] if len(partes) > 1 else []
    return mnemonico, operandos


# ---------------------------------------------------------------------------
# Efectos de cada instruccion ALU (para el analisis previo del traductor)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Efectos:
    """Que registros lee y escribe una instruccion de CacaoCore y si toca banderas."""

    lee: FrozenSet[int] = frozenset()
    escribe: FrozenSet[int] = frozenset()
    acc_implicito: bool = False  # ademas deja el resultado en ACC (ALU de acumulador)
    banderas: bool = False  # escribe banderas
    lee_banderas: bool = False


def _regs(operandos: Sequence[Operando]) -> Set[int]:
    return {op.registro for op in operandos if op.registro is not None}


def efectos_alu(mnemonico: str, operandos: Sequence[Operando]) -> Efectos:
    """Efectos de una instruccion ALU o de transferencia registro/inmediato."""
    ops = list(operandos)
    if not ops and mnemonico not in OPS_FLOTANTE:
        return Efectos()
    destino = ops[0].registro if ops and ops[0].tipo == "reg" else None

    if mnemonico in OPS_BINARIAS or mnemonico in OPS_COMPARACION:
        escribe = mnemonico in OPS_BINARIAS
        if len(ops) == 1:  # forma de acumulador: ACC = ACC op x
            return Efectos(frozenset({ACC} | _regs(ops)), frozenset({ACC} if escribe else ()), False, True)
        escritos = {destino} if escribe else set()
        if mnemonico == "div" and ops[1].tipo == "reg":
            escritos.add(ops[1].valor)  # residuo
        return Efectos(frozenset(_regs(ops)), frozenset(escritos), escribe, True)
    if mnemonico in OPS_UNARIAS:
        if mnemonico == "cmpz":
            return Efectos(frozenset(_regs(ops)), frozenset(), False, True)
        escritos = frozenset({destino}) if destino is not None else frozenset()
        return Efectos(frozenset(_regs(ops)), escritos, True, True)
    if mnemonico in OPS_DESPLAZAMIENTO:
        objetivo = destino if destino is not None else ACC
        es_shift = mnemonico in ("shl", "shr")
        return Efectos(frozenset({objetivo}), frozenset({objetivo}), es_shift and objetivo != ACC, es_shift)
    if mnemonico == "swap":
        par = frozenset(_regs(ops) | ({ACC} if len(ops) == 1 else set()))
        return Efectos(par, par)
    if mnemonico in MOVS:
        return Efectos(frozenset(_regs(ops[1:])), frozenset({destino}) if destino is not None else frozenset())
    if mnemonico in LOADS:
        return Efectos(frozenset(), frozenset({destino if len(ops) == 2 else ACC}))
    if mnemonico in STORES:
        return Efectos(frozenset({ACC}), frozenset({destino}) if destino is not None else frozenset())
    return Efectos()  # punto flotante: no se traduce


# ---------------------------------------------------------------------------
# Reglas LEX y acciones de traduccion
# ---------------------------------------------------------------------------

_M_DOS = _mnemonicos(*(OPS_BINARIAS + OPS_COMPARACION))
_M_UNARIAS = _mnemonicos(*OPS_UNARIAS)
_M_DESP = _mnemonicos(*OPS_DESPLAZAMIENTO)
_M_SWAP = _mnemonicos("swap")
_M_MOVS = _mnemonicos(*MOVS)
_M_MOVS_LOADS = _mnemonicos(*(MOVS + LOADS))
_M_LOADS = _mnemonicos(*LOADS)
_M_STORES = _mnemonicos(*STORES)
_M_FLOTANTE = _mnemonicos(*OPS_FLOTANTE)


class TraductorALU:
    """
    Analizador LEX de las instrucciones ALU de CacaoCore-64.

    Cada regla reconoce una forma (modo de direccionamiento) y su accion emite
    el codigo Enigma-64. Se usa una linea a la vez:

        alu = TraductorALU(tabla, memoria)
        codigo = alu.traducir("DIV R3, R2", linea=17, banderas_vivas=False)

    `tabla` es la TablaRegistros del programa; `memoria` es el TraductorMemoria
    del Integrante 1, del que se reutilizan las rutinas de direcciones.
    `banderas_vivas` indica si alguna instruccion posterior lee las banderas
    antes de que se vuelvan a escribir (lo calcula traductor.py).
    """

    tokens = (
        "OP_RR", "OP_RI", "OP_RM", "OP_RN", "OP_R", "OP_I", "OP_M",
        "UNARIA_R", "UNARIA_M", "DESP_I", "DESP_RI", "SWAP_R", "SWAP_RR",
        "MOV_RR", "MOV_RI", "LOAD_I", "STORE_R", "FLOTANTE",
    )

    t_ignore = " \t\r"

    def __init__(
        self,
        tabla: TablaRegistros,
        memoria,
        acc_observable: bool = True,
        variables: Optional[Set[str]] = None,
    ) -> None:
        self.tabla = tabla
        self.memoria = memoria
        self.acc_observable = acc_observable
        self.variables = variables
        self.errores: List[Tuple[int, str]] = []
        self.avisos: List[Tuple[int, str]] = []
        self._codigo: List[str] = []
        self._pendientes: List[str] = []
        self._linea = 0
        self._banderas_vivas = True
        self.lexer = lex.lex(object=self, reflags=0)

    # -- punto de entrada ----------------------------------------------------

    def traducir(self, texto: str, linea: int = 0, banderas_vivas: bool = True) -> List[str]:
        """Traduce una instruccion ALU de CacaoCore. Los errores quedan en self.errores."""
        self._codigo, self._pendientes = [], []
        self._linea, self._banderas_vivas = linea, banderas_vivas
        self.lexer.input(texto)
        reconocidas = 0
        try:
            for _token in iter(self.lexer.token, None):
                reconocidas += 1
        except RegistroInvalido as exc:
            self._error(str(exc))
            return []
        if reconocidas > 1:
            self._error(f"mas de una instruccion en la linea: '{texto.strip()}'")
        return self._codigo

    # -- reglas --------------------------------------------------------------
    # Formas de ADD SUB MUL DIV AND OR XOR CMP TEST

    @TOKEN(rf"{_M_DOS}{_ESP1}{REGISTRO}{_COMA}{REGISTRO}{FIN}")
    def t_OP_RR(self, t):
        self._dos_operandos(*dividir_instruccion(t.value))
        return t

    @TOKEN(rf"{_M_DOS}{_ESP1}{REGISTRO}{_COMA}{NUMERO}{FIN}")
    def t_OP_RI(self, t):
        self._dos_operandos(*dividir_instruccion(t.value))
        return t

    @TOKEN(rf"{_M_DOS}{_ESP1}{REGISTRO}{_COMA}{DIRECTO}{FIN}")
    def t_OP_RM(self, t):
        self._dos_operandos(*dividir_instruccion(t.value))
        return t

    @TOKEN(rf"{_M_DOS}{_ESP1}{REGISTRO}{_COMA}{INDIRECTO}{FIN}")
    def t_OP_RN(self, t):
        self._dos_operandos(*dividir_instruccion(t.value))
        return t

    @TOKEN(rf"{_M_DOS}{_ESP1}{REGISTRO}{FIN}")
    def t_OP_R(self, t):
        self._forma_acumulador(*dividir_instruccion(t.value))
        return t

    @TOKEN(rf"{_M_DOS}{_ESP1}{NUMERO}{FIN}")
    def t_OP_I(self, t):
        self._forma_acumulador(*dividir_instruccion(t.value))
        return t

    @TOKEN(rf"{_M_DOS}{_ESP1}{DIRECTO}{FIN}")
    def t_OP_M(self, t):
        self._forma_acumulador(*dividir_instruccion(t.value))
        return t

    # INC DEC NEG NOT CMPZ

    @TOKEN(rf"{_M_UNARIAS}{_ESP1}{REGISTRO}{FIN}")
    def t_UNARIA_R(self, t):
        mnemonico, (op,) = dividir_instruccion(t.value)
        self._unaria_registro(mnemonico, op.valor)
        return t

    @TOKEN(rf"{_M_UNARIAS}{_ESP1}{DIRECTO}{FIN}")
    def t_UNARIA_M(self, t):
        mnemonico, (op,) = dividir_instruccion(t.value)
        self._unaria_memoria(mnemonico, op)
        return t

    # SHL SHR ROL ROR

    @TOKEN(rf"{_M_DESP}{_ESP1}{NUMERO}{FIN}")
    def t_DESP_I(self, t):
        mnemonico, (n,) = dividir_instruccion(t.value)
        self._desplazamiento(mnemonico, ACC, n.valor)
        return t

    @TOKEN(rf"{_M_DESP}{_ESP1}{REGISTRO}{_COMA}{NUMERO}{FIN}")
    def t_DESP_RI(self, t):
        mnemonico, (x, n) = dividir_instruccion(t.value)
        self._desplazamiento(mnemonico, x.valor, n.valor)
        return t

    # SWAP

    @TOKEN(rf"{_M_SWAP}{_ESP1}{REGISTRO}{FIN}")
    def t_SWAP_R(self, t):
        _, (x,) = dividir_instruccion(t.value)
        self._intercambiar(x.valor, ACC)
        return t

    @TOKEN(rf"{_M_SWAP}{_ESP1}{REGISTRO}{_COMA}{REGISTRO}{FIN}")
    def t_SWAP_RR(self, t):
        _, (x, y) = dividir_instruccion(t.value)
        self._intercambiar(x.valor, y.valor)
        return t

    # Transferencias registro/inmediato (las de memoria son del Integrante 1)

    @TOKEN(rf"{_M_MOVS}{_ESP1}{REGISTRO}{_COMA}{REGISTRO}{FIN}")
    def t_MOV_RR(self, t):
        _, (x, y) = dividir_instruccion(t.value)
        self._mover(x.valor, y.valor)
        return t

    @TOKEN(rf"{_M_MOVS_LOADS}{_ESP1}{REGISTRO}{_COMA}{NUMERO}{FIN}")
    def t_MOV_RI(self, t):
        _, (x, n) = dividir_instruccion(t.value)
        self._cargar_inmediato(x.valor, n.valor)
        return t

    @TOKEN(rf"{_M_LOADS}{_ESP1}{NUMERO}{FIN}")
    def t_LOAD_I(self, t):
        _, (n,) = dividir_instruccion(t.value)
        self._cargar_inmediato(ACC, n.valor)
        return t

    @TOKEN(rf"{_M_STORES}{_ESP1}{REGISTRO}{FIN}")
    def t_STORE_R(self, t):
        _, (x,) = dividir_instruccion(t.value)
        self._mover(x.valor, ACC)
        return t

    # Punto flotante: fuera del alcance de esta parte

    @TOKEN(rf"{_M_FLOTANTE}(?:{_ESP1}[^;\#\n]*?)?{FIN}")
    def t_FLOTANTE(self, t):
        self._aviso(
            f"'{t.value.strip()}' es de punto flotante (FPU): no se traduce, queda comentada"
        )
        self._emitir(f"; [FPU sin traducir] {t.value.strip()}")
        return t

    def t_COMENTARIO(self, t):
        r"[;\#][^\n]*"

    def t_error(self, t):
        resto = re.split(r"[;#]", t.value, maxsplit=1)[0].strip()
        self._error(self._diagnosticar(resto))
        t.lexer.skip(len(t.value))

    def _diagnosticar(self, texto: str) -> str:
        invalido = re.search(r"(?<![A-Za-z0-9_])[Rr](\d+)(?![A-Za-z0-9_])", texto)
        if invalido and int(invalido.group(1)) > 15:
            return f"registro invalido '{invalido.group(0)}' (CacaoCore tiene R0..R15): '{texto}'"
        palabra = texto.split(None, 1)[0] if texto else ""
        if palabra.lower() in MNEMONICOS_ALU | MNEMONICOS_TRANSFERENCIA:
            if palabra not in (palabra.lower(), palabra.upper()):
                return f"mnemonico '{palabra}' mezcla mayusculas y minusculas: '{texto}'"
            return f"modo de direccionamiento no soportado para {palabra.upper()}: '{texto}'"
        return f"instruccion desconocida: '{texto}'"

    # -- utilidades de emision ----------------------------------------------

    def _emitir(self, *instrucciones: str) -> None:
        self._codigo.extend(instrucciones)

    def _error(self, mensaje: str) -> None:
        self.errores.append((self._linea, mensaje))

    def _aviso(self, mensaje: str) -> None:
        self.avisos.append((self._linea, mensaje))

    def _leer(self, registro: int, temporal: str) -> str:
        """Registro fisico con el valor de un registro de CacaoCore (carga si esta derramado)."""
        fisico, previas = self.tabla.leer(registro, temporal)
        self._emitir(*previas)
        return fisico

    def _destino(self, registro: int, temporal: str) -> str:
        """Registro fisico donde calcular; el STORE del derrame queda pendiente."""
        fisico, posteriores = self.tabla.escribir(registro, temporal)
        self._pendientes.extend(posteriores)
        return fisico

    def _confirmar(self) -> None:
        self._emitir(*self._pendientes)
        self._pendientes = []

    def _direccion(self, op: Operando, temporal: str) -> str:
        """Operando de memoria de Enigma-64 ([Rx]) para un operando de memoria de CacaoCore."""
        if op.tipo == "ind":
            return f"[{self._leer(op.valor, temporal)}]"
        if op.tipo == "var":
            if self.variables is not None and op.valor not in self.variables:
                self._aviso(f"la variable '{op.valor}' no esta declarada en .data")
            direccion = self.memoria.obtener_direccion_variable(op.valor)
        else:
            direccion = self.memoria.mapear_direccion(op.valor, alinear=True)
        self._emitir(*self.memoria.generar_secuencia_direccion(temporal, direccion))
        return f"[{temporal}]"

    def _valor(self, op: Operando, temporal: str) -> str:
        """Registro fisico que contiene el valor de un operando fuente."""
        if op.tipo == "reg":
            return self._leer(op.valor, temporal)
        if op.tipo == "imm":
            if op.valor == 0:
                return REG_CERO
            self._emitir(*cargar_constante(temporal, op.valor))
            return temporal
        referencia = self._direccion(op, temporal)
        self._emitir(f"LOAD {temporal}, {referencia}")
        return temporal

    def _copiar(self, destino: str, origen: str) -> None:
        """destino = origen entre registros fisicos, sin tocar banderas si estan vivas."""
        if destino == origen:
            return
        if self._banderas_vivas:
            self._emitir(f"PUSH {origen}", f"POP {destino}")
        else:
            self._emitir(f"ADD {destino}, {origen}, {REG_CERO}")

    def _escribir_valor(self, registro: int, origen: str) -> None:
        """Registro de CacaoCore = registro fisico `origen`."""
        ubicacion = self.tabla.ubicacion(registro)
        if ubicacion.residente:
            if ubicacion.registro != origen:
                self._emitir(f"ADD {ubicacion.registro}, {origen}, {REG_CERO}")
        else:
            self._emitir(*self.tabla.emitir_store(origen, ubicacion.ranura))

    def _operar(
        self,
        emitir_op: Callable[[str], None],
        destino: str,
        fuentes: Sequence[str],
        escribe_acc: bool,
    ) -> None:
        """
        Emite una operacion cuyo resultado va a `destino` y, como en la ALU de
        acumulador de CacaoCore, tambien a ACC.

        Si ACC vive en un registro que no es fuente, la operacion se calcula
        dos veces (primero en ACC, luego en el destino) para que las banderas
        finales sean exactamente las de la operacion. Si ACC esta derramado se
        guarda con STORE, que no toca banderas.
        """
        acc = self.tabla.ubicacion(ACC) if (escribe_acc and self.acc_observable) else None
        if acc is None or acc.registro == destino:
            emitir_op(destino)
        elif acc.residente and acc.registro not in fuentes:
            emitir_op(acc.registro)
            emitir_op(destino)
        else:
            emitir_op(destino)
            self._escribir_valor(ACC, destino)

    # -- acciones ------------------------------------------------------------

    def _dos_operandos(self, mnemonico: str, operandos: List[Operando]) -> None:
        x, y = operandos
        if mnemonico == "div":
            self._dividir(x.valor, y)
        elif mnemonico in OPS_COMPARACION:
            self._comparar(mnemonico, self._leer(x.valor, TMP1), y)
        else:
            self._binaria(mnemonico, x.valor, y)

    def _forma_acumulador(self, mnemonico: str, operandos: List[Operando]) -> None:
        """ADD Rx / ADD imm / ADD [m]  ->  ACC = ACC op operando."""
        (y,) = operandos
        if mnemonico == "div":
            self._dividir(ACC, y, con_residuo=False)  # div_a descarta el residuo
        elif mnemonico in OPS_COMPARACION:
            self._comparar(mnemonico, self._leer(ACC, TMP1), y)
        else:
            self._binaria(mnemonico, ACC, y)

    def _binaria(self, mnemonico: str, x: int, y: Operando) -> None:
        """X = X op Y para ADD SUB MUL AND OR XOR (y ACC = resultado)."""
        xs = self._leer(x, TMP1)
        if y.tipo == "imm" and mnemonico in ("add", "sub") and _INT16_MIN <= y.valor <= _INT16_MAX:
            instruccion = "ADDI" if mnemonico == "add" else "SUBI"
            fuentes = (xs,)

            def emitir_op(destino: str) -> None:
                self._emitir(f"{instruccion} {destino}, {xs}, {y.valor}")
        else:
            ys = self._valor(y, TMP2)
            fuentes = (xs, ys)

            def emitir_op(destino: str) -> None:
                self._emitir(f"{mnemonico.upper()} {destino}, {xs}, {ys}")

        destino = self._destino(x, TMP1)
        self._operar(emitir_op, destino, fuentes, escribe_acc=x != ACC)
        self._confirmar()

    def _dividir(self, x: int, y: Operando, con_residuo: bool = True) -> None:
        """
        DIV X, Y de CacaoCore: X = ACC = X / Y; si Y es registro, Y = X mod Y.

        Enigma-64 solo tiene cociente, asi que el residuo se calcula como
        r = x - (x / y) * y. Al final TMP1 = cociente y TMP2 = residuo, y las
        escrituras se hacen en el orden de div_ra: ACC = q, Y = r, X = ACC.
        """
        if y.tipo != "reg" or not con_residuo:
            xs = self._leer(x, TMP1)
            ys = self._valor(y, TMP2)
            destino = self._destino(x, TMP1)
            self._operar(
                lambda d: self._emitir(f"DIV {d}, {xs}, {ys}"), destino, (xs, ys), escribe_acc=x != ACC
            )
            self._confirmar()
            return

        xs = self._leer(x, TMP1)
        ys = self._leer(y.valor, TMP2)
        self._emitir(f"DIV {TMP1}, {xs}, {ys}", f"MUL {TMP2}, {TMP1}, {ys}")
        ubicacion_x, ubicacion_y = self.tabla.ubicacion(x), self.tabla.ubicacion(y.valor)
        # Si Y vive en un registro distinto de X, el residuo se escribe ahi directamente
        residuo = ubicacion_y.registro if ubicacion_y.residente and x != y.valor else TMP2
        if ubicacion_x.residente:
            self._emitir(f"SUB {residuo}, {ubicacion_x.registro}, {TMP2}")
        elif residuo != TMP2:
            # y ya no hace falta: su registro recibe x desde la ranura y luego r
            self._emitir(*self.tabla.emitir_load(residuo, ubicacion_x.ranura))
            self._emitir(f"SUB {residuo}, {residuo}, {TMP2}")
        else:
            # x se perdio en TMP1; se recarga de su ranura guardando q en la pila
            self._emitir(f"PUSH {TMP1}", *self.tabla.emitir_load(TMP1, ubicacion_x.ranura))
            self._emitir(f"SUB {TMP2}, {TMP1}, {TMP2}", f"POP {TMP1}")

        valor_acc = residuo if y.valor == ACC else TMP1
        self._escribir_valor(y.valor, residuo)
        self._escribir_valor(x, valor_acc)
        if self.acc_observable and ACC not in (x, y.valor):
            self._escribir_valor(ACC, valor_acc)
        if self._banderas_vivas and not self._ultima_bandera_es(TMP1):
            # Banderas de DIV en CacaoCore: Z y N del cociente, C = V = 0
            self._emitir(f"ADD {TMP1}, {TMP1}, {REG_CERO}")

    def _ultima_bandera_es(self, origen: str) -> bool:
        """True si la ultima instruccion que escribio banderas fue ADD _, origen, R0."""
        for instruccion in reversed(self._codigo):
            if modifica_banderas(instruccion):
                return bool(re.fullmatch(rf"ADD R\d, {origen}, {REG_CERO}", instruccion))
        return False

    def _comparar(self, mnemonico: str, xs: str, y: Operando) -> None:
        """CMP: banderas de x - y. TEST: banderas de x AND y en un temporal."""
        ys = self._valor(y, TMP2)
        if mnemonico == "cmp":
            self._emitir(f"CMP {xs}, {ys}")
        else:
            self._emitir(f"AND {TMP1}, {xs}, {ys}")

    def _unaria_registro(self, mnemonico: str, x: int) -> None:
        if mnemonico == "cmpz":
            self._emitir(f"CMP {REG_CERO}, {self._leer(x, TMP1)}")
            return
        xs = self._leer(x, TMP1)
        destino = self._destino(x, TMP1)
        self._operar(self._emisor_unaria(mnemonico, xs), destino, (xs,), escribe_acc=x != ACC)
        self._confirmar()

    def _unaria_memoria(self, mnemonico: str, op: Operando) -> None:
        """INC/DEC/NEG/NOT [m]: [m] = op [m] y ACC = resultado. CMPZ [m]: solo banderas."""
        referencia = self._direccion(op, TMP2)
        self._emitir(f"LOAD {TMP1}, {referencia}")
        if mnemonico == "cmpz":
            self._emitir(f"CMP {REG_CERO}, {TMP1}")
            return
        self._operar(self._emisor_unaria(mnemonico, TMP1), TMP1, (TMP1,), escribe_acc=True)
        self._emitir(f"STORE {TMP1}, {referencia}")

    def _emisor_unaria(self, mnemonico: str, origen: str) -> Callable[[str], None]:
        def emitir_op(destino: str) -> None:
            if mnemonico == "neg":
                self._emitir(f"SUB {destino}, {REG_CERO}, {origen}")  # R0 = 0
            elif destino == origen:
                self._emitir(f"{mnemonico.upper()} {destino}")
            elif mnemonico == "inc":
                self._emitir(f"ADDI {destino}, {origen}, 1")
            elif mnemonico == "dec":
                self._emitir(f"SUBI {destino}, {origen}, 1")
            else:  # not
                self._emitir(f"ADD {destino}, {origen}, {REG_CERO}", f"NOT {destino}")

        return emitir_op

    def _desplazamiento(self, mnemonico: str, x: int, n: int) -> None:
        if n < 0:
            self._error(f"desplazamiento negativo ({n}) en {mnemonico.upper()}")
            return
        xs = self._leer(x, TMP1)
        destino = self._destino(x, TMP1)
        if mnemonico in ("shl", "shr"):
            # SHR de CacaoCore desplaza el valor con signo: es ASR en Enigma-64
            instruccion = "SHL" if mnemonico == "shl" else "ASR"
            self._operar(
                lambda d: self._emitir(f"{instruccion} {d}, {xs}, {n}"), destino, (xs,), escribe_acc=x != ACC
            )
        else:
            # Rotacion de 64 bits con desplazamientos logicos y OR
            k = n % 64
            if k:
                hacia, desde = ("SHL", "SHR") if mnemonico == "rol" else ("SHR", "SHL")
                self._emitir(
                    f"{desde} {TMP2}, {xs}, {64 - k}",
                    f"{hacia} {destino}, {xs}, {k}",
                    f"OR {destino}, {destino}, {TMP2}",
                )
            elif destino != xs:
                self._emitir(f"ADD {destino}, {xs}, {REG_CERO}")
        self._confirmar()

    def _intercambiar(self, x: int, y: int) -> None:
        """SWAP con la pila: no usa temporales extra, no toca banderas y sirve si x == y."""
        if x == y:
            return
        xs = self._leer(x, TMP1)
        ys = self._leer(y, TMP2)
        destino_x = self._destino(x, TMP1)
        destino_y = self._destino(y, TMP2)
        self._emitir(f"PUSH {xs}", f"PUSH {ys}", f"POP {destino_x}", f"POP {destino_y}")
        self._confirmar()

    def _mover(self, x: int, y: int) -> None:
        """MOV X, Y (y STORE X = ACC): copia sin efecto en ACC ni en banderas."""
        if x == y:
            return
        destino, origen = self.tabla.ubicacion(x), self.tabla.ubicacion(y)
        if destino.residente and origen.residente:
            self._copiar(destino.registro, origen.registro)
        elif destino.residente:
            self._emitir(*self.tabla.emitir_load(destino.registro, origen.ranura))
        elif origen.residente:
            self._emitir(*self.tabla.emitir_store(origen.registro, destino.ranura))
        else:
            self._emitir(*self.tabla.emitir_load(TMP1, origen.ranura))
            self._emitir(*self.tabla.emitir_store(TMP1, destino.ranura))

    def _cargar_inmediato(self, x: int, valor: int) -> None:
        """MOV X, imm / LOAD X, imm / LOAD imm (X = ACC)."""
        ubicacion = self.tabla.ubicacion(x)
        if ubicacion.residente:
            if valor == 0:
                self._copiar(ubicacion.registro, REG_CERO)
            else:
                self._emitir(*cargar_constante(ubicacion.registro, valor))
        elif valor == 0:
            self._emitir(*self.tabla.emitir_store(REG_CERO, ubicacion.ranura))
        else:
            self._emitir(*cargar_constante(TMP1, valor))
            self._emitir(*self.tabla.emitir_store(TMP1, ubicacion.ranura))


__all__ = [
    "TraductorALU", "Operando", "Efectos", "efectos_alu", "parsear_operando",
    "separar_operandos", "dividir_instruccion", "cargar_constante", "modifica_banderas",
    "MNEMONICOS_ALU", "MNEMONICOS_TRANSFERENCIA", "MOVS", "LOADS", "STORES",
    "ENIGMA_MODIFICAN_BANDERAS",
]
