"""
Enigma-64 - Noctua Systems
Arquitectura y emulacion de computador Von Neumann de 64 bits.

Subsistemas principales:
  * Memoria RAM y Buses (RAMMemory)
  * Banco de Registros y ALU (ALU, BancoRegistros)
  * Unidad de Control y FSM (CPU, PrefetchBuffer, FASES_FSM)
  * Cargador y Manipulador de Bits (CargadorEnigma, BinarioEnigma)
  * Interfaz Grafica Modular (enigma64.ui)
  * Perifericos y MMIO (Perifericos, ControladorPantalla)
  * Programas Oficiales y Algoritmos de Prueba (PROGRAMAS_OFICIALES)

API publica del emulador:

    from enigma64 import ALU, BancoRegistros, RAMMemory, CPU, CargadorEnigma

    banco = BancoRegistros()
    alu = ALU()
    ram = RAMMemory()
    cargador = CargadorEnigma(ram=ram, banco=banco)
    cpu = CPU(ram=ram, banco=banco)
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
from .cpu import (
    CPU,
    CPUError,
    PrefetchBuffer,
    DecodedInstruction,
    DivisionPorCero as DivisionPorCeroCPU,
    IllegalInstruction,
    MemoryFault,
    AlignmentFault,
    PrivilegeFault,
    ExecutionLimitExceeded,
    FASES_FSM,
    MICRO_REGISTROS,
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
from .programas import (
    BYTES_CARGADOR_FIRMWARE,
    BYTES_EUCLIDES,
    BYTES_FACTORIAL,
    BYTES_FIBONACCI,
    PROGRAMA_EUCLIDES,
    PROGRAMA_FACTORIAL,
    PROGRAMA_FIBONACCI,
    PROGRAMAS_OFICIALES,
    DefinicionPrograma,
    exportar_archivos_programas,
    inicializar_escenario_prueba,
)


__all__ = [
    # Memoria RAM & Buses
    "RAMMemory",
    "InvalidAccessSizeError",
    "STATUS_READY",
    "STATUS_ADDR_FAULT",
    "STATUS_MMIO",
    "STATUS_MISALIGNED",
    "PAGE_SIZE",
    "VALID_SIZES",
    "MMIO_BASE",
    # Banco de Registros & ALU
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
    # Cargador & Manipulador de Bits
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
    # CPU & Unidad de Control FSM
    "CPU",
    "CPUError",
    "PrefetchBuffer",
    "DecodedInstruction",
    "FASES_FSM",
    "MICRO_REGISTROS",
    # Perifericos & MMIO
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
    # Programas Oficiales & Algoritmos de Prueba
    "BYTES_FACTORIAL",
    "BYTES_EUCLIDES",
    "BYTES_FIBONACCI",
    "BYTES_CARGADOR_FIRMWARE",
    "PROGRAMAS_OFICIALES",
    "PROGRAMA_FACTORIAL",
    "PROGRAMA_EUCLIDES",
    "PROGRAMA_FIBONACCI",
    "DefinicionPrograma",
    "exportar_archivos_programas",
    "inicializar_escenario_prueba",
]


