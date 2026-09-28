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
from .cargador import (
    FIRMWARE_LOADER_ADDR,
    LOADER_WORKSPACE_END,
    LOADER_WORKSPACE_START,
    MAGIC_ENIGMA,
    STACK_START,
    USER_MEM_END,
    USER_MEM_START,
    BinarioEnigma,
    CargadorEnigma,
    DireccionInvalida,
    ErrorCargador,
    FormatoInvalido,
    ViolacionProteccionMemoria,
    byte_a_cadena_bits,
    conmutar_bit,
    emular_subrutina_cargador,
    escribir_bit,
    escribir_byte_directo,
    leer_bit,
    leer_byte_directo,
    parsear_texto_a_bytes,
)
from .perifericos import (
    BASE_DISCO,
    BASE_MMIO as MMIO_PERIFERICOS_BASE,
    BASE_PANTALLA,
    BASE_RED,
    BASE_TECLADO,
    BASE_TEMPORIZADOR,
    CMD_CLEAR,
    CMD_NEWLINE,
    CMD_RESET,
    CMD_SCROLL_UP,
    ControladorPantalla,
    ControladoresMMIO,
    Perifericos,
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
    # Integrante 4 - Cargador & Manipulador de Bits
    "CargadorEnigma",
    "BinarioEnigma",
    "ErrorCargador",
    "DireccionInvalida",
    "ViolacionProteccionMemoria",
    "FormatoInvalido",
    "leer_bit",
    "escribir_bit",
    "conmutar_bit",
    "byte_a_cadena_bits",
    "escribir_byte_directo",
    "leer_byte_directo",
    "parsear_texto_a_bytes",
    "emular_subrutina_cargador",
    "USER_MEM_START",
    "USER_MEM_END",
    "STACK_START",
    "FIRMWARE_LOADER_ADDR",
    "LOADER_WORKSPACE_START",
    "LOADER_WORKSPACE_END",
    "MAGIC_ENIGMA",
    # Integrante 6 - Visor/Editor RAM & MMIO
    "ControladorPantalla",
    "Perifericos",
    "ControladoresMMIO",
    "BASE_PANTALLA",
    "BASE_TECLADO",
    "BASE_DISCO",
    "BASE_RED",
    "BASE_TEMPORIZADOR",
    "CMD_CLEAR",
    "CMD_RESET",
    "CMD_NEWLINE",
    "CMD_SCROLL_UP",
]

