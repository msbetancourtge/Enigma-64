"""
Enigma-64 - Noctua Systems
Modulos integrados:
  * Integrante 1: RAM & Buses (RAMMemory)
  * Integrante 2: Banco de registros y ALU (ALU, BancoRegistros)

Contrato publico para consumir integrantes:

    from enigma64 import ALU, BancoRegistros, RAMMemory

    banco = BancoRegistros()
    alu = ALU()
    ram = RAMMemory()

    # Acceso a memoria desde FSM
    dato, estado = ram.mem_read(banco.pc, size_bytes=4)
"""

from .alu import (
    ALU,
    CARRY_EN_RESTA,
    DivisionPorCero,
    OperacionInvalida,
    ResultadoALU,
    TABLA_OPERACIONES,
)
from .memoria import (
    MMIO_BASE,
    PAGE_SIZE,
    STATUS_ADDR_FAULT,
    STATUS_MISALIGNED,
    STATUS_MMIO,
    STATUS_READY,
    VALID_SIZES,
    InvalidAccessSizeError,
    RAMMemory,
)
from .registros import (
    BITS,
    BIT63,
    BIT_DE_BANDERA,
    CODIGO_POR_NOMBRE,
    MASK64,
    NOMBRE_POR_CODIGO,
    ORDEN_BANDERAS,
    PC_RESET,
    SP_RESET,
    SR_RESET,
    SR_RESET_SUPERVISOR,
    BancoRegistros,
    RegistroInvalido,
    a_con_signo,
    a_sin_signo,
    hex64,
)

__all__ = [
    # Integrante 1 - RAM & Buses
    "RAMMemory",
    "InvalidAccessSizeError",
    "STATUS_READY",
    "STATUS_ADDR_FAULT",
    "STATUS_MMIO",
    "STATUS_MISALIGNED",
    "PAGE_SIZE",
    "VALID_SIZES",
    "MMIO_BASE",
    # Integrante 2 - ALU & Registros
    "ALU",
    "BancoRegistros",
    "ResultadoALU",
    "DivisionPorCero",
    "OperacionInvalida",
    "RegistroInvalido",
    "TABLA_OPERACIONES",
    "CARRY_EN_RESTA",
    "NOMBRE_POR_CODIGO",
    "CODIGO_POR_NOMBRE",
    "BIT_DE_BANDERA",
    "ORDEN_BANDERAS",
    "MASK64",
    "BIT63",
    "BITS",
    "SP_RESET",
    "PC_RESET",
    "SR_RESET",
    "SR_RESET_SUPERVISOR",
    "a_con_signo",
    "a_sin_signo",
    "hex64",
]
