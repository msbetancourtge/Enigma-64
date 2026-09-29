"""
Unidad de Control y CPU de Enigma-64.

Implementa la ruta de datos multiciclo descrita en la especificacion:
FETCH -> DECODE -> EXECUTE -> MEMORY -> WRITE-BACK.

La CPU usa el banco de registros, la RAM y la ALU existentes. Las instrucciones
son byte-addressable, big-endian y de longitud variable (1 a 5 bytes). El
buffer de prebusqueda mantiene hasta 16 bytes para que una instruccion pueda
cruzar limites de palabra de 64 bits.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - CPU FSM: Pre-Fetch - Fetch-Decode-Execute
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .alu import ALU, DivisionPorCero as DivisionPorCeroALU, ResultadoALU
from .memoria import (
    STATUS_ADDR_FAULT,
    STATUS_MISALIGNED,
    STATUS_MMIO,
    STATUS_READY,
    RAMMemory,
)
from .registros import BancoRegistros, MASK64

FASES_FSM: Tuple[str, ...] = ("FETCH", "DECODE", "EXECUTE", "MEMORY", "WRITE-BACK")
MICRO_REGISTROS: Tuple[str, ...] = ("MAR", "MDR", "IR", "A", "B", "Z")
PREFETCH_SIZE = 16

_INSTRUCTIONS: Dict[int, Tuple[str, str, int]] = {
    0x00: ("HLT", "none", 1),
    0x10: ("ADD", "rr", 3),
    0x11: ("SUB", "rr", 3),
    0x12: ("MUL", "rr", 3),
    0x13: ("DIV", "rr", 3),
    0x14: ("ADDI", "imm", 4),
    0x15: ("SUBI", "imm", 4),
    0x16: ("INC", "unary", 2),
    0x17: ("DEC", "unary", 2),
    0x20: ("AND", "rr", 3),
    0x21: ("OR", "rr", 3),
    0x22: ("XOR", "rr", 3),
    0x23: ("NOT", "unary", 2),
    0x24: ("SHL", "imm", 4),
    0x25: ("SHR", "imm", 4),
    0x26: ("ASR", "imm", 4),
    0x27: ("CMP", "rr", 3),
    0x30: ("LOAD", "memory", 4),
    0x31: ("STORE", "memory", 4),
    0x32: ("LDB", "memory", 4),
    0x33: ("STB", "memory", 4),
    0x40: ("JMP", "absolute", 5),
    0x41: ("JZ", "relative", 3),
    0x42: ("JNZ", "relative", 3),
    0x43: ("JC", "relative", 3),
    0x44: ("JNC", "relative", 3),
    0x45: ("JN", "relative", 3),
    0x46: ("JP", "relative", 3),
    0x47: ("JV", "relative", 3),
    0x48: ("JNV", "relative", 3),
    0x49: ("JMPR", "register", 2),
    0x4A: ("CALL", "absolute", 5),
    0x4B: ("CALLR", "register", 2),
    0x4C: ("RET", "none", 1),
    0x4D: ("PUSH", "register", 2),
    0x4E: ("POP", "register", 2),
    0x4F: ("ENTER", "enter", 4),
    0x50: ("LEAVE", "none", 1),
    0x51: ("EI", "none", 1),
    0x52: ("DI", "none", 1),
    0x53: ("IRET", "none", 1),
}

_ALU_MNEMONICS = frozenset({
    "ADD", "SUB", "MUL", "DIV", "ADDI", "SUBI", "INC", "DEC",
    "AND", "OR", "XOR", "NOT", "SHL", "SHR", "ASR", "CMP",
})
_MEMORY_MNEMONICS = frozenset({"LOAD", "STORE", "LDB", "STB"})


class CPUError(RuntimeError):
    """Error base para fallos durante la ejecucion de la CPU."""


class DivisionPorCero(CPUError):
    """La unidad de control intento dividir entre cero."""


class IllegalInstruction(CPUError):
    """El opcode o la codificacion del registro no pertenece al ISA."""


class MemoryFault(CPUError):
    """La RAM rechazo el acceso o falta un dispositivo MMIO."""


class AlignmentFault(MemoryFault):
    """Se solicito un acceso natural en una direccion desalineada."""


class PrivilegeFault(MemoryFault):
    """El codigo de usuario intento acceder a una region protegida."""


class ExecutionLimitExceeded(CPUError):
    """La ejecucion no se detuvo antes de agotar el limite de ciclos."""


@dataclass(frozen=True)
class DecodedInstruction:
    """Instruccion y operandos decodificados para el ciclo actual de la FSM."""

    opcode: int
    mnemonic: str
    formato: str
    length: int
    address: int
    raw: bytes
    rd: Optional[int] = None
    rs1: Optional[int] = None
    rs2: Optional[int] = None
    immediate: Optional[int] = None
    offset: Optional[int] = None


class PrefetchBuffer:
    """Buffer de instrucciones de 16 bytes alimentado por lecturas alineadas."""

    def __init__(self, ram: RAMMemory, capacity: int = PREFETCH_SIZE) -> None:
        if capacity < 8:
            raise ValueError("The prefetch buffer must hold at least one word.")
        self.ram = ram
        self.capacity = capacity
        self.start: Optional[int] = None
        self.data = bytearray()

    def reset(self) -> None:
        self.start = None
        self.data.clear()

    def _load_window(self, address: int) -> None:
        aligned = address & ~0x7
        raw = bytearray()
        for offset in range(0, self.capacity, 8):
            word, status = self.ram.mem_read(aligned + offset, 8, check_alignment=True)
            if status != STATUS_READY or word is None:
                raise MemoryFault(
                    f"No se pudo prebucar 0x{aligned + offset:08X}: {status}"
                )
            raw.extend(word.to_bytes(8, "big"))
        self.start = aligned
        self.data = raw[: self.capacity]

    def ensure(self, address: int, count: int = 1) -> bytes:
        if count < 0 or count > self.capacity:
            raise ValueError("Invalid prefetch request size.")
        if (
            self.start is None
            or address < self.start
            or address + count > self.start + len(self.data)
        ):
            self._load_window(address)
        offset = address - self.start
        return bytes(self.data[offset : offset + count])

    def consume(self, count: int) -> None:
        if count < 0 or count > len(self.data):
            raise ValueError("Cannot consume more bytes than buffered.")
        if self.start is not None:
            self.start += count
        del self.data[:count]

    @property
    def bytes(self) -> bytes:
        return bytes(self.data)


class CPU:
    """Procesador Enigma-64 y unidad de control multiciclo."""

    def __init__(
        self,
        ram: Optional[RAMMemory] = None,
        banco: Optional[BancoRegistros] = None,
        alu: Optional[ALU] = None,
    ) -> None:
        self.ram = ram if ram is not None else RAMMemory()
        self.banco = banco if banco is not None else BancoRegistros()
        self.alu = alu if alu is not None else ALU()
        self.prefetch = PrefetchBuffer(self.ram)
        self.micro: Dict[str, int] = {nombre: 0 for nombre in MICRO_REGISTROS}
        self.fase = "FETCH"
        self.ciclos = 0
        self.instrucciones = 0
        self.detenido = False
        self._actual: Optional[DecodedInstruction] = None
        self._resultado_alu: Optional[ResultadoALU] = None
        self._resultado_memoria: Optional[int] = None
        self._destino: Optional[int] = None
        self._pc_siguiente = 0
        self._mensaje = ""
        self._halt_pending = False

    def reset(self) -> None:
        self.banco.reset()
        self.prefetch.reset()
        for nombre in MICRO_REGISTROS:
            self.micro[nombre] = 0
        self.fase = "FETCH"
        self.ciclos = 0
        self.instrucciones = 0
        self.detenido = False
        self._actual = None
        self._resultado_alu = None
        self._resultado_memoria = None
        self._destino = None
        self._pc_siguiente = 0
        self._mensaje = ""
        self._halt_pending = False

    reiniciar = reset

    def estado(self) -> Dict[str, object]:
        return {
            "fase": self.fase,
            "ciclos": self.ciclos,
            "instrucciones": self.instrucciones,
            "detenido": self.detenido,
            "micro": dict(self.micro),
            "mnemonico": self._actual.mnemonic if self._actual else "",
            "prefetch": self.prefetch.bytes,
            "prefetch_inicio": self.prefetch.start,
            "mensaje": self._mensaje,
        }

    snapshot = estado
    state = estado
    fases = staticmethod(lambda: FASES_FSM)
    micro_registros = staticmethod(lambda: MICRO_REGISTROS)

    @staticmethod
    def _sign_extend(value: int, bits: int) -> int:
        sign = 1 << (bits - 1)
        return value - (1 << bits) if value & sign else value

    def _read_prefetch(self, address: int, count: int) -> bytes:
        try:
            return self.prefetch.ensure(address, count)
        except MemoryFault:
            raise

    def _decode(self, address: int) -> DecodedInstruction:
        opcode = self._read_prefetch(address, 1)[0]
        try:
            mnemonic, formato, length = _INSTRUCTIONS[opcode]
        except KeyError:
            raise IllegalInstruction(f"Opcode desconocido: 0x{opcode:02X}") from None
        raw = self._read_prefetch(address, length)
        first = raw[1] if length > 1 else 0
        instruction = DecodedInstruction(
            opcode=opcode,
            mnemonic=mnemonic,
            formato=formato,
            length=length,
            address=address,
            raw=raw,
        )
        if formato == "rr":
            instruction = DecodedInstruction(
                **{**instruction.__dict__, "rd": first >> 4, "rs1": first & 0xF,
                   "rs2": raw[2] >> 4}
            )
        elif formato == "unary":
            instruction = DecodedInstruction(**{**instruction.__dict__, "rd": first >> 4})
        elif formato in ("imm", "memory"):
            value = int.from_bytes(raw[2:4], "big")
            instruction = DecodedInstruction(
                **{**instruction.__dict__, "rd": first >> 4, "rs1": first & 0xF,
                   "immediate": self._sign_extend(value, 16)}
            )
        elif formato == "relative":
            value = int.from_bytes(raw[1:3], "big")
            instruction = DecodedInstruction(
                **{**instruction.__dict__, "offset": self._sign_extend(value, 16)}
            )
        elif formato == "absolute":
            instruction = DecodedInstruction(
                **{**instruction.__dict__, "immediate": int.from_bytes(raw[1:5], "big")}
            )
        elif formato == "register":
            instruction = DecodedInstruction(**{**instruction.__dict__, "rd": first >> 4})
        elif formato == "enter":
            instruction = DecodedInstruction(
                **{**instruction.__dict__, "immediate": self._sign_extend(
                    int.from_bytes(raw[2:4], "big"), 16
                )}
            )
        return instruction

    def _write_micro(self, nombre: str, valor: int) -> None:
        self.micro[nombre] = valor & MASK64

    def _fase_fetch(self) -> None:
        pc = self.banco.pc
        self._write_micro("MAR", pc)
        aligned = pc & ~0x7
        word, status = self.ram.mem_read(aligned, 8, check_alignment=True)
        if status != STATUS_READY or word is None:
            raise MemoryFault(f"FETCH en 0x{pc:08X} fallo: {status}")
        self._write_micro("MDR", word)
        self._read_prefetch(pc, 1)
        self._write_micro("IR", int.from_bytes(self._read_prefetch(pc, 8), "big"))
        self.fase = "DECODE"

    def _fase_decode(self) -> None:
        actual = self._decode(self.banco.pc)
        self._actual = actual
        self._pc_siguiente = (actual.address + actual.length) & MASK64
        self.banco.pc = self._pc_siguiente
        self.prefetch.consume(actual.length)
        self._destino = actual.rd
        if actual.formato == "unary":
            operando_a = self.banco.leer(actual.rd or 0)
        else:
            operando_a = self.banco.leer(actual.rs1) if actual.rs1 is not None else 0
        self._write_micro("A", operando_a)
        self._write_micro("B", self.banco.leer(actual.rs2) if actual.rs2 is not None else 0)
        self.fase = "EXECUTE"

    def _fase_execute(self) -> None:
        assert self._actual is not None
        op = self._actual.mnemonic
        self._resultado_alu = None
        self._resultado_memoria = None
        if op in _ALU_MNEMONICS:
            a = self.micro["A"]
            b = self.micro["B"]
            if op in {"ADDI", "SUBI", "SHL", "SHR", "ASR"}:
                b = self._actual.immediate or 0
            try:
                self._resultado_alu = self.alu.ejecutar(op, a, b)
            except DivisionPorCeroALU as exc:
                raise DivisionPorCero("DIV recibio un divisor igual a cero") from exc
            self.banco.aplicar_banderas(
                self._resultado_alu.banderas, self._resultado_alu.afectadas
            )
            self._write_micro("Z", self._resultado_alu.valor)
        elif op in _MEMORY_MNEMONICS:
            base = self.banco.leer(self._actual.rs1 or 0)
            self._write_micro("Z", base + (self._actual.immediate or 0))
        elif op == "JMP":
            self.banco.pc = self._actual.immediate or 0
        elif op in {"JZ", "JNZ", "JC", "JNC", "JN", "JP", "JV", "JNV"}:
            flag = {
                "JZ": self.banco.leer_bandera("Z") == 1,
                "JNZ": self.banco.leer_bandera("Z") == 0,
                "JC": self.banco.leer_bandera("C") == 1,
                "JNC": self.banco.leer_bandera("C") == 0,
                "JN": self.banco.leer_bandera("N") == 1,
                "JP": self.banco.leer_bandera("N") == 0 and self.banco.leer_bandera("Z") == 0,
                "JV": self.banco.leer_bandera("V") == 1,
                "JNV": self.banco.leer_bandera("V") == 0,
            }[op]
            if flag:
                self.banco.pc = self._pc_siguiente + (self._actual.offset or 0)
        elif op == "JMPR":
            self.banco.pc = self.banco.leer(self._actual.rd or 0)
        elif op in {"EI", "DI"}:
            self.banco.escribir_bandera("I", 1 if op == "EI" else 0)
        elif op == "HLT":
            self._halt_pending = True
        self.fase = "MEMORY"

    def _memory_access(self, address: int, size: int, write: Optional[int] = None,
                       alignment: bool = True) -> Optional[int]:
        if address < 0x00200000 and not self.banco.en_supervisor:
            raise PrivilegeFault(f"Acceso de usuario a 0x{address:08X}")
        if write is None:
            value, status = self.ram.mem_read(address, size, check_alignment=alignment)
        else:
            value, status = self.ram.mem_write(address, write, size, check_alignment=alignment)
        if status == STATUS_MISALIGNED:
            self.banco.escribir_bandera("M", 1)
            raise AlignmentFault(f"Acceso desalineado en 0x{address:08X}")
        if status == STATUS_ADDR_FAULT:
            raise MemoryFault(f"Direccion fuera de rango: 0x{address:X}")
        if status == STATUS_MMIO:
            raise MemoryFault(f"MMIO no conectado: 0x{address:08X}")
        if status != STATUS_READY:
            raise MemoryFault(f"Fallo de memoria en 0x{address:08X}: {status}")
        return value

    def _push(self, value: int) -> None:
        self.banco.sp = self.banco.sp - 8
        self._memory_access(self.banco.sp, 8, value, alignment=False)

    def _pop(self) -> int:
        value = self._memory_access(self.banco.sp, 8, alignment=False)
        self.banco.sp = self.banco.sp + 8
        return value or 0

    def _fase_memory(self) -> None:
        assert self._actual is not None
        op = self._actual.mnemonic
        address = self.micro["Z"]
        if op == "LOAD":
            self._resultado_memoria = self._memory_access(address, 8)
        elif op == "STORE":
            self._memory_access(address, 8, self.micro["A"] if self._actual.rd is None else self.banco.leer(self._actual.rd))
        elif op == "LDB":
            self._resultado_memoria = self._memory_access(address, 1)
        elif op == "STB":
            self._memory_access(address, 1, self.banco.leer(self._actual.rd or 0))
        elif op == "CALL":
            self._push(self.banco.pc)
            self.banco.pc = self._actual.immediate or 0
        elif op == "CALLR":
            self._push(self.banco.pc)
            self.banco.pc = self.banco.leer(self._actual.rd or 0)
        elif op == "RET":
            self.banco.pc = self._pop()
        elif op == "PUSH":
            self._push(self.banco.leer(self._actual.rd or 0))
        elif op == "POP":
            self._resultado_memoria = self._pop()
        elif op == "ENTER":
            self._push(self.banco.bp)
            self.banco.bp = self.banco.sp
            self.banco.sp = self.banco.sp - (self._actual.immediate or 0)
        elif op == "LEAVE":
            self.banco.sp = self.banco.bp
            self.banco.bp = self._pop()
        elif op == "IRET":
            self.banco.pc = self._pop()
            self.banco.sr = self._pop()
        self.fase = "WRITE-BACK"

    def _fase_write_back(self) -> None:
        assert self._actual is not None
        op = self._actual.mnemonic
        if self._resultado_alu is not None and self._resultado_alu.escribe_destino:
            self.banco.escribir(self._destino or 0, self._resultado_alu.valor)
        elif op in {"LOAD", "LDB", "POP"}:
            self.banco.escribir(self._destino or 0, self._resultado_memoria or 0)
        self.instrucciones += 1
        self._actual = None
        self._resultado_alu = None
        self._resultado_memoria = None
        self.fase = "FETCH"
        if self._halt_pending:
            self.detenido = True
            self._halt_pending = False
            self._mensaje = "HLT"

    def paso(self) -> Dict[str, object]:
        """Avanza una fase de la FSM y devuelve el estado resultante."""
        if self.detenido and self.fase == "FETCH":
            return self.estado()
        fases = {
            "FETCH": self._fase_fetch,
            "DECODE": self._fase_decode,
            "EXECUTE": self._fase_execute,
            "MEMORY": self._fase_memory,
            "WRITE-BACK": self._fase_write_back,
        }
        fases[self.fase]()
        self.ciclos += 1
        return self.estado()

    step = paso
    ciclo = paso
    tick = paso

    def paso_instruccion(self) -> Dict[str, object]:
        """Completa la instruccion actual, incluyendo sus cinco fases."""
        if self.detenido:
            return self.estado()
        ciclos = 0
        while not self.detenido or self.fase != "FETCH":
            self.paso()
            ciclos += 1
            if self.fase == "FETCH" and (self._actual is None):
                break
            if ciclos > len(FASES_FSM) + 1:
                break
        return self.estado()

    step_instruction = paso_instruccion

    def ejecutar(self, max_ciclos: int = 100000) -> Dict[str, object]:
        """Ejecuta hasta HLT, respetando un presupuesto de ciclos."""
        if max_ciclos <= 0:
            raise ValueError("max_ciclos debe ser positivo")
        consumidos = 0
        while not self.detenido:
            if consumidos >= max_ciclos:
                raise ExecutionLimitExceeded(
                    f"La CPU no se detuvo en {max_ciclos} ciclos."
                )
            self.paso()
            consumidos += 1
        return self.estado()

    run = ejecutar
    correr = ejecutar
    ejecutar_todo = ejecutar


UnidadControl = CPU
UnidadDeControl = CPU
ControlUnit = CPU
Procesador = CPU

__all__ = [
    "CPU", "UnidadControl", "UnidadDeControl", "ControlUnit", "Procesador",
    "PrefetchBuffer", "DecodedInstruction", "FASES_FSM", "MICRO_REGISTROS",
    "CPUError", "IllegalInstruction", "MemoryFault", "AlignmentFault",
    "PrivilegeFault", "ExecutionLimitExceeded", "DivisionPorCero",
]
