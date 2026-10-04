"""
Módulo FPU (Unidad de Punto Flotante) para Enigma-64 (Noctua Systems).

Implementa la aritmética de punto flotante de doble precisión (IEEE 754 - 64 bits)
en código ensamblador propio de la arquitectura:
  * FPU_DESEMPAQUETAR: Extrae signo, exponente (11 bits) y mantisa (52 bits + implícito).
  * FPU_EMPAQUETAR: Ensambla signo, exponente y mantisa al formato canónico IEEE 754.
  * FADD: Suma de flotantes con alineación por corrimiento de mantisas y renormalización.
  * FSUB: Resta de flotantes mediante inversión del signo del sustraendo y FADD.
  * FMUL: Multiplicación con producto de 106 bits, redondeo al par más cercano,
    subnormales y casos especiales (fmul.s).
"""

from __future__ import annotations

import os
import struct
from typing import Tuple

from .cpu import CPU
from .ensamblador import ensamblar
from .memoria import RAMMemory
from .registros import BancoRegistros, MASK64

# Constantes IEEE 754 Doble Precisión (binary64)
BIAS: int = 1023
EXP_MASK: int = 0x7FF
FRAC_MASK: int = 0x000FFFFFFFFFFFFF
IMPLICIT_BIT: int = 0x0010000000000000
SIGN_BIT: int = 0x8000000000000000

# Carga del código fuente ensamblador oficial.
# fpu.s (núcleo + FADD/FSUB), fmul.s (FMUL) y fconv.s (Conversiones y Vectores)
# se ensamblan conjuntamente como una sola unidad modular de biblioteca.
_RUTA_FPU_S = os.path.join(os.path.dirname(__file__), "fpu.s")
_RUTA_FMUL_S = os.path.join(os.path.dirname(__file__), "fmul.s")
_RUTA_FCONV_S = os.path.join(os.path.dirname(__file__), "fconv.s")

with open(_RUTA_FPU_S, "r", encoding="utf-8") as _f:
    _CODIGO_NUCLEO_ASM: str = _f.read()

with open(_RUTA_FMUL_S, "r", encoding="utf-8") as _f:
    _CODIGO_FMUL_ASM: str = _f.read()

with open(_RUTA_FCONV_S, "r", encoding="utf-8") as _f:
    _CODIGO_FCONV_ASM: str = _f.read()

CODIGO_FPU_ASM: str = f"{_CODIGO_NUCLEO_ASM}\n{_CODIGO_FMUL_ASM}\n{_CODIGO_FCONV_ASM}"

# Desplazamientos fijos de la Tabla de Vectores de la FPU (5 bytes por JMP)
VECTOR_FADD: int = 0x00
VECTOR_FSUB: int = 0x05
VECTOR_FMUL: int = 0x0A
VECTOR_FDIV: int = 0x0F
VECTOR_FCMP: int = 0x14
VECTOR_INT_TO_FLOAT: int = 0x19
VECTOR_FLOAT_TO_INT: int = 0x1E



def compilar_fpu(direccion_base: int = 0x00200000) -> bytes:
    """Ensambla el módulo oficial de la FPU a la dirección base especificada."""
    return ensamblar(CODIGO_FPU_ASM, direccion_base=direccion_base)


BYTES_FPU_MODULO: bytes = compilar_fpu(0x00200000)


def float_a_ieee64(val: float) -> int:
    """Convierte un flotante estándar de Python a su entero sin signo de 64 bits IEEE 754."""
    return struct.unpack(">Q", struct.pack(">d", float(val)))[0]


def ieee64_a_float(val: int) -> float:
    """Convierte un entero de 64 bits en formato IEEE 754 al flotante de Python correspondiente."""
    return struct.unpack(">d", struct.pack(">Q", val & MASK64))[0]


class EmuladorFPUEnigma64:
    """
    Controlador y ejecutor de pruebas para las subrutinas de la FPU
    directamente sobre el procesador y memoria física de Enigma-64.
    """

    DIRECCION_BASE_CODIGO = 0x00200000
    DIRECCION_SP_INICIAL = 0x00204000
    DIRECCION_VARIABLES = 0x00205000

    def __init__(self) -> None:
        self.ram = RAMMemory()
        self.banco = BancoRegistros()
        self.cpu = CPU(ram=self.ram, banco=self.banco)

    def _preparar_entorno(self, codigo_harness: str) -> None:
        """Ensambla y carga en memoria el código de la FPU junto con el harness de llamada."""
        codigo_completo = f"{codigo_harness}\n{CODIGO_FPU_ASM}"
        binario = ensamblar(codigo_completo, direccion_base=self.DIRECCION_BASE_CODIGO)
        self.ram.reset()
        for i, b in enumerate(binario):
            self.ram.mem_write(
                self.DIRECCION_BASE_CODIGO + i, b, 1, check_alignment=False
            )
        self.cpu.reset()
        self.cpu.banco.sp = self.DIRECCION_SP_INICIAL
        self.cpu.banco.bp = self.DIRECCION_SP_INICIAL
        self.cpu.banco.pc = self.DIRECCION_BASE_CODIGO

    def desempaquetar(self, val: float | int) -> Tuple[int, int, int]:
        """
        Ejecuta FPU_DESEMPAQUETAR sobre el procesador Enigma-64.
        Devuelve (signo, exponente, mantisa).
        """
        u64 = float_a_ieee64(val) if isinstance(val, float) else (val & MASK64)
        harness = f"""
        JMP HARNESS_START
        HARNESS_START:
            ADDI SP, R0, 0x0020
            SHL SP, SP, 16
            ADDI SP, SP, 0x4000
            ADDI BP, SP, 0
            
            ADDI R1, R0, 0x0020
            SHL R1, R1, 16
            ADDI R1, R1, 0x5000
            LOAD R1, [R1 + 0]
            CALL FPU_DESEMPAQUETAR
            
            ADDI R5, R0, 0x0020
            SHL R5, R5, 16
            ADDI R5, R5, 0x5000
            STORE R2, [R5 + 8]
            STORE R3, [R5 + 16]
            STORE R4, [R5 + 24]
            HLT
        """
        self._preparar_entorno(harness)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 0, u64, 8)
        self.cpu.ejecutar(max_ciclos=50000)

        signo, _ = self.ram.mem_read(self.DIRECCION_VARIABLES + 8, 8)
        exponente, _ = self.ram.mem_read(self.DIRECCION_VARIABLES + 16, 8)
        mantisa, _ = self.ram.mem_read(self.DIRECCION_VARIABLES + 24, 8)
        return signo or 0, exponente or 0, mantisa or 0

    def empaquetar(self, signo: int, exponente: int, mantisa: int) -> int:
        """
        Ejecuta FPU_EMPAQUETAR sobre el procesador Enigma-64.
        Devuelve el entero de 64 bits en formato IEEE 754.
        """
        harness = f"""
        JMP HARNESS_START
        HARNESS_START:
            ADDI SP, R0, 0x0020
            SHL SP, SP, 16
            ADDI SP, SP, 0x4000
            ADDI BP, SP, 0
            
            ADDI R1, R0, 0x0020
            SHL R1, R1, 16
            ADDI R1, R1, 0x5000
            LOAD R2, [R1 + 0]
            LOAD R3, [R1 + 8]
            LOAD R4, [R1 + 16]
            CALL FPU_EMPAQUETAR
            
            ADDI R1, R0, 0x0020
            SHL R1, R1, 16
            ADDI R1, R1, 0x5000
            STORE R5, [R1 + 24]
            HLT
        """
        self._preparar_entorno(harness)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 0, signo, 8)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 8, exponente, 8)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 16, mantisa, 8)
        self.cpu.ejecutar(max_ciclos=50000)

        resultado, _ = self.ram.mem_read(self.DIRECCION_VARIABLES + 24, 8)
        return resultado or 0

    def sumar(self, a: float | int, b: float | int) -> float:
        """Ejecuta FADD en Enigma-64 y devuelve el flotante resultante."""
        return self._ejecutar_binario_fpu(a, b, subrutina="FADD")

    def restar(self, a: float | int, b: float | int) -> float:
        """Ejecuta FSUB en Enigma-64 y devuelve el flotante resultante."""
        return self._ejecutar_binario_fpu(a, b, subrutina="FSUB")

    def multiplicar(self, a: float | int, b: float | int) -> float:
        """Ejecuta FMUL en Enigma-64 y devuelve el flotante resultante."""
        return self._ejecutar_binario_fpu(a, b, subrutina="FMUL")

    def multiplicar_bits(self, a: float | int, b: float | int) -> int:
        """Ejecuta FMUL en Enigma-64 y devuelve el patrón IEEE 754 de 64 bits."""
        return self._ejecutar_binario_fpu_u64(a, b, subrutina="FMUL")

    def _ejecutar_binario_fpu(
        self, a: float | int, b: float | int, subrutina: str
    ) -> float:
        return ieee64_a_float(self._ejecutar_binario_fpu_u64(a, b, subrutina))

    def _ejecutar_binario_fpu_u64(
        self, a: float | int, b: float | int, subrutina: str
    ) -> int:
        u64_a = float_a_ieee64(a) if isinstance(a, float) else (a & MASK64)
        u64_b = float_a_ieee64(b) if isinstance(b, float) else (b & MASK64)

        harness = f"""
        JMP HARNESS_START
        HARNESS_START:
            ADDI SP, R0, 0x0020
            SHL SP, SP, 16
            ADDI SP, SP, 0x4000
            ADDI BP, SP, 0
            
            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            LOAD R1, [R4 + 0]
            LOAD R2, [R4 + 8]
            CALL {subrutina}
            
            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            STORE R5, [R4 + 16]
            HLT
        """
        self._preparar_entorno(harness)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 0, u64_a, 8)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 8, u64_b, 8)
        self.cpu.ejecutar(max_ciclos=50000)

        res_u64, _ = self.ram.mem_read(self.DIRECCION_VARIABLES + 16, 8)
        return res_u64 or 0

    def int_to_float(self, val: int) -> float:
        """Convierte un entero con signo a flotante IEEE 754 ejecutando FPU_INT_TO_FLOAT."""
        return ieee64_a_float(self.int_to_float_bits(val))

    def int_to_float_bits(self, val: int) -> int:
        """Convierte un entero con signo a patrón IEEE 754 de 64 bits ejecutando FPU_INT_TO_FLOAT."""
        u64_in = val & MASK64
        harness = f"""
        JMP HARNESS_START
        HARNESS_START:
            ADDI SP, R0, 0x0020
            SHL SP, SP, 16
            ADDI SP, SP, 0x4000
            ADDI BP, SP, 0

            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            LOAD R1, [R4 + 0]
            CALL FPU_INT_TO_FLOAT

            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            STORE R5, [R4 + 8]
            HLT
        """
        self._preparar_entorno(harness)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 0, u64_in, 8)
        self.cpu.ejecutar(max_ciclos=50000)

        res_u64, _ = self.ram.mem_read(self.DIRECCION_VARIABLES + 8, 8)
        return res_u64 or 0

    def float_to_int(self, val: float | int) -> int:
        """Convierte un flotante IEEE 754 a entero de 64 bits con signo ejecutando FPU_FLOAT_TO_INT."""
        u64_in = float_a_ieee64(val) if isinstance(val, float) else (val & MASK64)
        harness = f"""
        JMP HARNESS_START
        HARNESS_START:
            ADDI SP, R0, 0x0020
            SHL SP, SP, 16
            ADDI SP, SP, 0x4000
            ADDI BP, SP, 0

            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            LOAD R1, [R4 + 0]
            CALL FPU_FLOAT_TO_INT

            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            STORE R5, [R4 + 8]
            HLT
        """
        self._preparar_entorno(harness)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 0, u64_in, 8)
        self.cpu.ejecutar(max_ciclos=50000)

        res_u64, _ = self.ram.mem_read(self.DIRECCION_VARIABLES + 8, 8)
        val_u64 = res_u64 or 0
        return val_u64 - (1 << 64) if val_u64 & SIGN_BIT else val_u64

    def ejecutar_vector(self, vector_label: str, a: float | int, b: float | int = 0) -> int:
        """
        Ejecuta una subrutina invocándola a través de su punto de entrada en la tabla
        canónica FPU_VECTORES (p. ej. VEC_FADD, VEC_INT_TO_FLOAT).
        """
        u64_a = float_a_ieee64(a) if isinstance(a, float) else (a & MASK64)
        u64_b = float_a_ieee64(b) if isinstance(b, float) else (b & MASK64)
        harness = f"""
        JMP HARNESS_START
        HARNESS_START:
            ADDI SP, R0, 0x0020
            SHL SP, SP, 16
            ADDI SP, SP, 0x4000
            ADDI BP, SP, 0

            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            LOAD R1, [R4 + 0]
            LOAD R2, [R4 + 8]
            CALL {vector_label}

            ADDI R4, R0, 0x0020
            SHL R4, R4, 16
            ADDI R4, R4, 0x5000
            STORE R5, [R4 + 16]
            HLT
        """
        self._preparar_entorno(harness)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 0, u64_a, 8)
        self.ram.mem_write(self.DIRECCION_VARIABLES + 8, u64_b, 8)
        self.cpu.ejecutar(max_ciclos=50000)

        res_u64, _ = self.ram.mem_read(self.DIRECCION_VARIABLES + 16, 8)
        return res_u64 or 0

