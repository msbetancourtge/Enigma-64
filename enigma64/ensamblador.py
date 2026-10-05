"""
Ensamblador de dos pasadas para la arquitectura Enigma-64 (Noctua Systems).

Soporta mnemónicos oficiales, registros R0..R7 (incluyendo alias RV, SP, BP),
etiquetas de salto, saltos condicionales relativos (JZ, JNZ, etc.), saltos
absolutos (JMP, CALL), literales en decimal y hexadecimal (0x...), y cálculo
automático de direcciones y offsets relativos Big-Endian.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .registros import CODIGO_POR_NOMBRE


class ErrorEnsamblador(Exception):
    """Error durante el análisis sintáctico o ensamblado de Enigma-64."""


REGISTROS_VALIDOS: Dict[str, int] = {
    **CODIGO_POR_NOMBRE,
    "R0": 0, "R1": 1, "R2": 2, "R3": 3,
    "R4": 4, "R5": 5, "R6": 6, "R7": 7,
    "RV": 5, "SP": 6, "BP": 7,
}


def _parse_int(val_str: str) -> int:
    val_str = val_str.strip()
    if val_str.startswith("0x") or val_str.startswith("0X"):
        return int(val_str, 16)
    if val_str.startswith("-0x") or val_str.startswith("-0X"):
        return -int(val_str[1:], 16)
    return int(val_str, 10)


def _parse_reg(reg_str: str) -> int:
    nombre = reg_str.strip().upper()
    if nombre not in REGISTROS_VALIDOS:
        raise ErrorEnsamblador(f"Registro desconocido o no válido: '{reg_str}'")
    return REGISTROS_VALIDOS[nombre]


def ensamblar(codigo_asm: str, direccion_base: int = 0x00200000) -> bytes:
    """
    Ensambla una cadena de código fuente en ensamblador de Enigma-64
    y devuelve los bytes binarios correspondientes.
    """
    lineas = codigo_asm.splitlines()

    # Primera pasada: Recolectar etiquetas y calcular longitudes de instrucciones
    simbolos: Dict[str, int] = {}
    instrucciones_limpias: List[Tuple[int, str, List[str], str]] = []
    pc = direccion_base

    for num_linea, linea_orig in enumerate(lineas, 1):
        # Remover comentarios (# o ;)
        linea = re.split(r"[#;]", linea_orig)[0].strip()
        if not linea:
            continue

        # Detectar etiqueta inicial
        while ":" in linea:
            etiqueta, resto = linea.split(":", 1)
            etiqueta = etiqueta.strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", etiqueta):
                raise ErrorEnsamblador(
                    f"Nombre de etiqueta inválido '{etiqueta}' en línea {num_linea}"
                )
            if etiqueta in simbolos:
                raise ErrorEnsamblador(
                    f"Etiqueta duplicada '{etiqueta}' en línea {num_linea}"
                )
            simbolos[etiqueta] = pc
            linea = resto.strip()

        if not linea:
            continue

        # Separar mnemónico de operandos
        partes = linea.split(None, 1)
        mnemonico = partes[0].upper()
        ops_str = partes[1] if len(partes) > 1 else ""

        # Separar operandos por coma respetando corchetes [...]
        ops: List[str] = []
        if ops_str:
            tokens = []
            actual = []
            en_corchete = False
            for ch in ops_str:
                if ch == "[":
                    en_corchete = True
                    actual.append(ch)
                elif ch == "]":
                    en_corchete = False
                    actual.append(ch)
                elif ch == "," and not en_corchete:
                    tokens.append("".join(actual).strip())
                    actual = []
                else:
                    actual.append(ch)
            if actual:
                tokens.append("".join(actual).strip())
            ops = tokens

        # Determinar longitud de la instrucción
        longitud = _calcular_longitud(mnemonico, ops, num_linea)
        instrucciones_limpias.append((pc, mnemonico, ops, linea_orig))
        pc += longitud

    # Segunda pasada: Generar código máquina
    salida = bytearray()
    for pc_inst, mnemonico, ops, linea_orig in instrucciones_limpias:
        bytes_inst = _ensamblar_instruccion(
            pc_inst, mnemonico, ops, simbolos, direccion_base
        )
        salida.extend(bytes_inst)

    return bytes(salida)


def _calcular_longitud(mnemonico: str, ops: List[str], num_linea: int) -> int:
    if mnemonico in ("HLT", "RET", "LEAVE", "EI", "DI", "IRET"):
        return 1
    if mnemonico in ("INC", "DEC", "NOT", "PUSH", "POP", "CALLR", "JMPR"):
        return 2
    if mnemonico in ("ADD", "SUB", "MUL", "DIV", "AND", "OR", "XOR", "CMP"):
        return 3
    if mnemonico in (
        "JZ", "JNZ", "JC", "JNC", "JN", "JP", "JV", "JNV"
    ):
        return 3
    if mnemonico in ("ADDI", "SUBI", "SHL", "SHR", "ASR", "LOAD", "STORE", "LDB", "STB", "ENTER"):
        return 4
    if mnemonico in ("JMP", "CALL"):
        return 5
    raise ErrorEnsamblador(f"Mnemónico desconocido: '{mnemonico}' en línea {num_linea}")


def _ensamblar_instruccion(
    pc_inst: int,
    mnemonico: str,
    ops: List[str],
    simbolos: Dict[str, int],
    direccion_base: int,
) -> bytes:
    # Formato NONE (1 byte)
    if mnemonico == "HLT":
        return bytes([0x00])
    if mnemonico == "RET":
        return bytes([0x4C])
    if mnemonico == "LEAVE":
        return bytes([0x50])
    if mnemonico == "EI":
        return bytes([0x51])
    if mnemonico == "DI":
        return bytes([0x52])
    if mnemonico == "IRET":
        return bytes([0x53])

    # Formato UNARY (2 bytes): opcode, (rd << 4)
    if mnemonico in ("INC", "DEC", "NOT"):
        opcodes = {"INC": 0x16, "DEC": 0x17, "NOT": 0x23}
        rd = _parse_reg(ops[0])
        return bytes([opcodes[mnemonico], (rd << 4)])

    # Formato REGISTER (2 bytes): opcode, (rd << 4)
    if mnemonico in ("PUSH", "POP", "CALLR", "JMPR"):
        opcodes = {"PUSH": 0x4D, "POP": 0x4E, "CALLR": 0x4B, "JMPR": 0x49}
        rd = _parse_reg(ops[0])
        return bytes([opcodes[mnemonico], (rd << 4)])

    # Formato RR (3 bytes): opcode, (rd << 4) | rs1, (rs2 << 4)
    if mnemonico in ("ADD", "SUB", "MUL", "DIV", "AND", "OR", "XOR"):
        opcodes = {
            "ADD": 0x10, "SUB": 0x11, "MUL": 0x12, "DIV": 0x13,
            "AND": 0x20, "OR": 0x21, "XOR": 0x22,
        }
        rd = _parse_reg(ops[0])
        rs1 = _parse_reg(ops[1])
        rs2 = _parse_reg(ops[2])
        return bytes([opcodes[mnemonico], (rd << 4) | rs1, (rs2 << 4)])

    if mnemonico == "CMP":
        # CMP rs1, rs2 -> opcode 0x27, (0 << 4) | rs1, (rs2 << 4)
        rs1 = _parse_reg(ops[0])
        rs2 = _parse_reg(ops[1])
        return bytes([0x27, rs1 & 0x0F, (rs2 << 4)])

    # Formato RELATIVE (3 bytes): opcode, rel16 (signed, big endian)
    # pc_siguiente = pc_inst + 3
    # offset = destino - pc_siguiente
    if mnemonico in ("JZ", "JNZ", "JC", "JNC", "JN", "JP", "JV", "JNV"):
        opcodes = {
            "JZ": 0x41, "JNZ": 0x42, "JC": 0x43, "JNC": 0x44,
            "JN": 0x45, "JP": 0x46, "JV": 0x47, "JNV": 0x48,
        }
        destino_str = ops[0].strip()
        if destino_str in simbolos:
            destino = simbolos[destino_str]
        else:
            destino = _parse_int(destino_str)
        pc_siguiente = pc_inst + 3
        offset = destino - pc_siguiente
        if not (-32768 <= offset <= 32767):
            raise ErrorEnsamblador(
                f"Salto relativo fuera de rango 16-bit ({offset}) en {mnemonico} a {destino_str}"
            )
        offset_u16 = offset & 0xFFFF
        return bytes([opcodes[mnemonico], (offset_u16 >> 8) & 0xFF, offset_u16 & 0xFF])

    # Formato IMM (4 bytes): opcode, (rd << 4) | rs1, imm16 (big endian)
    if mnemonico in ("ADDI", "SUBI", "SHL", "SHR", "ASR"):
        opcodes = {
            "ADDI": 0x14, "SUBI": 0x15, "SHL": 0x24, "SHR": 0x25, "ASR": 0x26
        }
        rd = _parse_reg(ops[0])
        rs1 = _parse_reg(ops[1])
        imm_str = ops[2].strip()
        imm = simbolos[imm_str] if imm_str in simbolos else _parse_int(imm_str)
        imm_u16 = imm & 0xFFFF
        return bytes([
            opcodes[mnemonico],
            (rd << 4) | rs1,
            (imm_u16 >> 8) & 0xFF,
            imm_u16 & 0xFF,
        ])

    # Formato MEMORY (4 bytes): opcode, (rd << 4) | rs1, offset16
    # Sintaxis esperada: LOAD Rd, [Rs1 + offset] o STORE Rd, [Rs1 + offset]
    # También soporta [Rs1 - offset] o [Rs1] (offset=0)
    if mnemonico in ("LOAD", "STORE", "LDB", "STB"):
        opcodes = {"LOAD": 0x30, "STORE": 0x31, "LDB": 0x32, "STB": 0x33}
        rd = _parse_reg(ops[0])
        mem_str = ops[1].strip()
        if not (mem_str.startswith("[") and mem_str.endswith("]")):
            raise ErrorEnsamblador(f"Sintaxis de memoria inválida: '{mem_str}'")
        interior = mem_str[1:-1].strip()
        rs1, offset = _parse_mem_interior(interior, simbolos)
        offset_u16 = offset & 0xFFFF
        return bytes([
            opcodes[mnemonico],
            (rd << 4) | rs1,
            (offset_u16 >> 8) & 0xFF,
            offset_u16 & 0xFF,
        ])

    # Formato ENTER (4 bytes): 0x4F, 0x00, imm16
    if mnemonico == "ENTER":
        imm_str = ops[0].strip()
        imm = _parse_int(imm_str)
        imm_u16 = imm & 0xFFFF
        return bytes([0x4F, 0x00, (imm_u16 >> 8) & 0xFF, imm_u16 & 0xFF])

    # Formato ABSOLUTE (5 bytes): opcode, addr32 (4 bytes big endian)
    if mnemonico in ("JMP", "CALL"):
        opcodes = {"JMP": 0x40, "CALL": 0x4A}
        target_str = ops[0].strip()
        if target_str in simbolos:
            addr = simbolos[target_str]
        else:
            addr = _parse_int(target_str)
        addr_u32 = addr & 0xFFFFFFFF
        return bytes([
            opcodes[mnemonico],
            (addr_u32 >> 24) & 0xFF,
            (addr_u32 >> 16) & 0xFF,
            (addr_u32 >> 8) & 0xFF,
            addr_u32 & 0xFF,
        ])

    raise ErrorEnsamblador(f"Instrucción no implementada en el ensamblador: {mnemonico}")


def _parse_mem_interior(interior: str, simbolos: Dict[str, int]) -> Tuple[int, int]:
    # Formatos posibles: R1, R1 + 8, R1 - 8, R1 + 0x10
    if "+" in interior:
        base_part, off_part = interior.split("+", 1)
        rs1 = _parse_reg(base_part)
        off_str = off_part.strip()
        off = simbolos[off_str] if off_str in simbolos else _parse_int(off_str)
        return rs1, off
    elif "-" in interior:
        base_part, off_part = interior.split("-", 1)
        rs1 = _parse_reg(base_part)
        off_str = off_part.strip()
        off = -(simbolos[off_str] if off_str in simbolos else _parse_int(off_str))
        return rs1, off
    else:
        rs1 = _parse_reg(interior)
        return rs1, 0
