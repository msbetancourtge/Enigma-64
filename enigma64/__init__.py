"""
Enigma-64 - Noctua Systems
Modulo del Integrante 2: Banco de registros y ALU.

Contrato publico para consumir integrantes:

    from enigma64 import ALU, BancoRegistros

    banco = BancoRegistros()
    alu = ALU()

    # fase EXECUTE de la FSM
    res = alu.ejecutar("ADD", banco.leer(0x3), banco.leer(0x2))
    banco.aplicar_banderas(res.banderas, res.afectadas)

    # fase WRITE-BACK
    if res.escribe_destino:
        banco.escribir(0x5, res.valor)
"""

from .alu import (
    ALU,
    CARRY_EN_RESTA,
    DivisionPorCero,
    OperacionInvalida,
    ResultadoALU,
    TABLA_OPERACIONES,
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
