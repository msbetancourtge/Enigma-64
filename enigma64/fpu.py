"""
Módulo FPU (Unidad de Punto Flotante) para Enigma-64 (Noctua Systems).

Implementa la aritmética de punto flotante de doble precisión (IEEE 754 - 64 bits)
en código ensamblador propio de la arquitectura:
  * FPU_DESEMPAQUETAR: Extrae signo, exponente (11 bits) y mantisa (52 bits + implícito).
  * FPU_EMPAQUETAR: Ensambla signo, exponente y mantisa al formato canónico IEEE 754.
  * FADD: Suma de flotantes con alineación por corrimiento de mantisas y renormalización.
  * FSUB: Resta de flotantes mediante inversión del signo del sustraendo y FADD.
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

# Carga del código fuente ensamblador oficial
_RUTA_FPU_S = os.path.join(os.path.dirname(__file__), "fpu.s")

with open(_RUTA_FPU_S, "r", encoding="utf-8") as _f:
    CODIGO_FPU_ASM: str = _f.read()


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

    def _ejecutar_binario_fpu(
        self, a: float | int, b: float | int, subrutina: str
    ) -> float:
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
        return ieee64_a_float(res_u64 or 0)
