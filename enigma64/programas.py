"""
Definicion y Generacion de Algoritmos Clasicos - Enigma-64 (Noctua Systems).

Implementa las responsabilidades del Integrante 7 (Tarea 10):
  1. Definicion binaria exacta (Big-Endian) de los tres algoritmos disenados
     y verificados manualmente en la Tarea 9:
       - Algoritmo 1: Calculo del Factorial (N!).
       - Algoritmo 2: Algoritmo de Euclides (Maximo Comun Divisor - MCD).
       - Algoritmo 3: Generacion de la Sucesion de Fibonacci en RAM.
       - Extra: Firmware del Cargador (ubicado en 0x00001000).
  2. Generacion automatizada de archivos binarios crudos (.bin), volcados
     hexadecimales legibles (.hex/.txt) y binarios estructurados (.e64).
  3. Metadatos de ejecucion (direcciones base, puntos de entrada, direcciones
     de entrada de datos, direcciones de resultados esperados y valores testigo).

Autor: Integrante 7 - Algoritmos & Tests (Alejandro Arguello Munoz)
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .cargador import (
    BinarioEnigma,
    CargadorEnigma,
    USER_MEM_START,
    escribir_byte_directo,
    leer_byte_directo,
)
from .memoria import RAMMemory, STATUS_READY
from .registros import BancoRegistros, MASK64


# ===========================================================================
# 1. Definicion de Bytes de los 3 Algoritmos de la Tarea 9
# ===========================================================================

# ---------------------------------------------------------------------------
# Algoritmo 1: Factorial (N!) - 41 bytes
# Direccion base: 0x00200000
# Variables RAM : 0x00201000 (Entrada N=5, 64-bit), 0x00201008 (Salida fact, 64-bit)
# ---------------------------------------------------------------------------
BYTES_FACTORIAL: bytes = bytes([
    # 0x00200000: ADDI R1, R0, 0x0020 (R1 = 0x0020)
    0x14, 0x10, 0x00, 0x20,
    # 0x00200004: SHL R1, R1, 16      (R1 = 0x00200000)
    0x24, 0x11, 0x00, 0x10,
    # 0x00200008: ADDI R1, R1, 0x1000 (R1 = 0x00201000)
    0x14, 0x11, 0x10, 0x00,
    # 0x0020000C: LOAD R2, [R1 + 0]   (R2 = N desde Mem[0x00201000])
    0x30, 0x21, 0x00, 0x00,
    # 0x00200010: ADDI R3, R0, 1      (R3 = factorial = 1)
    0x14, 0x30, 0x00, 0x01,
    # 0x00200014: CMP R2, R0          (Compara N con 0, actualiza Z)
    0x27, 0x02, 0x00,
    # 0x00200017: JZ FIN_FACT         (Salto relativo +10 bytes -> 0x00200024)
    0x41, 0x00, 0x0A,
    # 0x0020001A: MUL R3, R3, R2      (LOOP_FACT: factorial = factorial * N)
    0x12, 0x33, 0x20,
    # 0x0020001D: SUBI R2, R2, 1      (N = N - 1, actualiza Z)
    0x15, 0x22, 0x00, 0x01,
    # 0x00200021: JNZ LOOP_FACT       (Salto relativo -10 bytes -> 0x0020001A)
    0x42, 0xFF, 0xF6,
    # 0x00200024: STORE R3, [R1 + 8]  (FIN_FACT: Mem[0x00201008] = factorial final)
    0x31, 0x31, 0x00, 0x08,
    # 0x00200028: HLT                 (Detener procesador)
    0x00,
])

# ---------------------------------------------------------------------------
# Algoritmo 2: Euclides (MCD) - 50 bytes
# Direccion base: 0x00200100
# Variables RAM : 0x00202000 (A=48, 64-bit), 0x00202008 (B=18, 64-bit),
#                 0x00202010 (MCD resultante, 64-bit)
# ---------------------------------------------------------------------------
BYTES_EUCLIDES: bytes = bytes([
    # 0x00200100: ADDI R1, R0, 0x0020 (R1 = 0x0020)
    0x14, 0x10, 0x00, 0x20,
    # 0x00200104: SHL R1, R1, 16      (R1 = 0x00200000)
    0x24, 0x11, 0x00, 0x10,
    # 0x00200108: ADDI R1, R1, 0x2000 (R1 = 0x00202000)
    0x14, 0x11, 0x20, 0x00,
    # 0x0020010C: LOAD R2, [R1 + 0]   (R2 = A)
    0x30, 0x21, 0x00, 0x00,
    # 0x00200110: LOAD R3, [R1 + 8]   (R3 = B)
    0x30, 0x31, 0x00, 0x08,
    # 0x00200114: CMP R2, R3          (LOOP_EUCLIDES: Evalua R2 - R3)
    0x27, 0x02, 0x30,
    # 0x00200117: JZ FIN_EUCLIDES     (Salto relativo +19 bytes -> 0x0020012D)
    0x41, 0x00, 0x13,
    # 0x0020011A: JN B_ES_MAYOR       (Salto relativo +8 bytes -> 0x00200125)
    0x45, 0x00, 0x08,
    # 0x0020011D: SUB R2, R2, R3      (Caso A > B: A = A - B)
    0x11, 0x22, 0x30,
    # 0x00200120: JMP 0x00200114      (Salto incondicional absoluto F5 a LOOP_EUCLIDES)
    0x40, 0x00, 0x20, 0x01, 0x14,
    # 0x00200125: SUB R3, R3, R2      (B_ES_MAYOR: B = B - A)
    0x11, 0x33, 0x20,
    # 0x00200128: JMP 0x00200114      (Salto incondicional absoluto F5 a LOOP_EUCLIDES)
    0x40, 0x00, 0x20, 0x01, 0x14,
    # 0x0020012D: STORE R2, [R1 + 16] (FIN_EUCLIDES: Mem[0x00202010] = MCD)
    0x31, 0x21, 0x00, 0x10,
    # 0x00200131: HLT                 (Detener procesador)
    0x00,
])

# ---------------------------------------------------------------------------
# Algoritmo 3: Fibonacci en RAM - 63 bytes
# Direccion base: 0x00200200
# Almacenamiento: 0x00203000 en adelante (7 terminos de 64-bit = 56 bytes)
# ---------------------------------------------------------------------------
BYTES_FIBONACCI: bytes = bytes([
    # 0x00200200: ADDI R1, R0, 0x0020 (R1 = 0x0020)
    0x14, 0x10, 0x00, 0x20,
    # 0x00200204: SHL R1, R1, 16      (R1 = 0x00200000)
    0x24, 0x11, 0x00, 0x10,
    # 0x00200208: ADDI R1, R1, 0x3000 (R1 = 0x00203000 - Base del arreglo)
    0x14, 0x11, 0x30, 0x00,
    # 0x0020020C: ADDI R2, R0, 0      (R2 = F0 = 0)
    0x14, 0x20, 0x00, 0x00,
    # 0x00200210: ADDI R3, R0, 1      (R3 = F1 = 1)
    0x14, 0x30, 0x00, 0x01,
    # 0x00200214: STORE R2, [R1 + 0]  (Mem[0x00203000] = F0 = 0)
    0x31, 0x21, 0x00, 0x00,
    # 0x00200218: STORE R3, [R1 + 8]  (Mem[0x00203008] = F1 = 1)
    0x31, 0x31, 0x00, 0x08,
    # 0x0020021C: ADDI R1, R1, 16     (ptr = ptr + 16 -> apunta a 0x00203010)
    0x14, 0x11, 0x00, 0x10,
    # 0x00200220: ADDI R4, R0, 5      (R4 = 5 terminos restantes)
    0x14, 0x40, 0x00, 0x05,
    # 0x00200224: ADD R5, R3, R2      (LOOP_FIBONACCI: F_sig = F1 + F0)
    0x10, 0x53, 0x20,
    # 0x00200227: STORE R5, [R1 + 0]  (Mem[ptr] = F_sig)
    0x31, 0x51, 0x00, 0x00,
    # 0x0020022B: ADDI R2, R3, 0      (F0 = F1)
    0x14, 0x23, 0x00, 0x00,
    # 0x0020022F: ADDI R3, R5, 0      (F1 = F_sig)
    0x14, 0x35, 0x00, 0x00,
    # 0x00200233: ADDI R1, R1, 8      (ptr = ptr + 8 -> siguiente celda)
    0x14, 0x11, 0x00, 0x08,
    # 0x00200237: SUBI R4, R4, 1      (contador = contador - 1, actualiza Z)
    0x15, 0x44, 0x00, 0x01,
    # 0x0020023B: JNZ LOOP_FIBONACCI  (Salto relativo -26 bytes -> 0x00200224)
    0x42, 0xFF, 0xE6,
    # 0x0020023E: HLT                 (Fin del programa)
    0x00,
])

# ---------------------------------------------------------------------------
# Extra: Firmware del Cargador residente en 0x00001000 - 69 bytes
# ---------------------------------------------------------------------------
BYTES_CARGADOR_FIRMWARE: bytes = bytes([
    # 0x00001000: ADDI R4, R0, 0x0020
    0x14, 0x40, 0x00, 0x20,
    # 0x00001004: SHL R4, R4, 16
    0x24, 0x44, 0x00, 0x10,
    # 0x00001008: CMP R2, R4
    0x27, 0x02, 0x40,
    # 0x0000100B: JN CARGADOR_ERROR (offset +0x36 = 54)
    0x45, 0x00, 0x36,
    # 0x0000100E: ADD R5, R2, R3
    0x10, 0x52, 0x30,
    # 0x00001011: ADDI R4, R0, 3
    0x14, 0x40, 0x00, 0x03,
    # 0x00001015: SHL R4, R4, 30
    0x24, 0x44, 0x00, 0x1E,
    # 0x00001019: CMP R5, R4
    0x27, 0x05, 0x40,
    # 0x0000101C: JP CARGADOR_ERROR (offset +0x25 = 37)
    0x46, 0x00, 0x25,
    # 0x0000101F: ADDI R5, R2, 0
    0x14, 0x52, 0x00, 0x00,
    # 0x00001023: CMP R3, R0 (CARGADOR_COPIA)
    0x27, 0x03, 0x00,
    # 0x00001026: JZ CARGADOR_FIN (offset +0x19 = 25)
    0x41, 0x00, 0x19,
    # 0x00001029: LDB R4, [R1+0]
    0x32, 0x41, 0x00, 0x00,
    # 0x0000102D: STB R4, [R2+0]
    0x33, 0x42, 0x00, 0x00,
    # 0x00001031: ADDI R1, R1, 1
    0x14, 0x11, 0x00, 0x01,
    # 0x00001035: ADDI R2, R2, 1
    0x14, 0x22, 0x00, 0x01,
    # 0x00001039: SUBI R3, R3, 1
    0x15, 0x33, 0x00, 0x01,
    # 0x0000103D: JMP CARGADOR_COPIA (absoluto 0x00001023)
    0x40, 0x00, 0x00, 0x10, 0x23,
    # 0x00001042: JMPR R5 (CARGADOR_FIN)
    0x49, 0x50,
    # 0x00001044: HLT (CARGADOR_ERROR)
    0x00,
])


# ===========================================================================
# 2. Metadatos Estructurados de Cada Programa
# ===========================================================================

@dataclass(frozen=True)
class DefinicionPrograma:
    nombre: str
    descripcion: str
    bytes_codigo: bytes
    direccion_base: int
    entry_point: int
    entradas_ram: Dict[int, int] = field(default_factory=dict)
    salidas_esperadas_ram: Dict[int, int] = field(default_factory=dict)
    lineas_ensamblador: List[str] = field(default_factory=list)

    @property
    def tamano_bytes(self) -> int:
        return len(self.bytes_codigo)

    def volcado_hexadecimal(self, bytes_por_linea: int = 16) -> str:
        """Retorna representacion hexadecimal limpia formateada."""
        lineas = []
        for i in range(0, len(self.bytes_codigo), bytes_por_linea):
            chunk = self.bytes_codigo[i : i + bytes_por_linea]
            hex_part = " ".join(f"{b:02X}" for b in chunk)
            lineas.append(hex_part)
        return "\n".join(lineas)


PROGRAMA_FACTORIAL = DefinicionPrograma(
    nombre="factorial",
    descripcion="Calculo de Factorial N! (N=5 -> 120)",
    bytes_codigo=BYTES_FACTORIAL,
    direccion_base=0x00200000,
    entry_point=0x00200000,
    entradas_ram={
        0x00201000: 5,  # N = 5
    },
    salidas_esperadas_ram={
        0x00201008: 120,  # 5! = 120 (0x0000000000000078)
    },
    lineas_ensamblador=[
        "ADDI R1, R0, 0x0020",
        "SHL R1, R1, 16",
        "ADDI R1, R1, 0x1000",
        "LOAD R2, [R1 + 0]",
        "ADDI R3, R0, 1",
        "CMP R2, R0",
        "JZ FIN_FACT",
        "LOOP_FACT:",
        "MUL R3, R3, R2",
        "SUBI R2, R2, 1",
        "JNZ LOOP_FACT",
        "FIN_FACT:",
        "STORE R3, [R1 + 8]",
        "HLT",
    ],
)

PROGRAMA_EUCLIDES = DefinicionPrograma(
    nombre="euclides",
    descripcion="Algoritmo de Euclides para MCD (A=48, B=18 -> MCD=6)",
    bytes_codigo=BYTES_EUCLIDES,
    direccion_base=0x00200100,
    entry_point=0x00200100,
    entradas_ram={
        0x00202000: 48,  # A = 48 (0x30)
        0x00202008: 18,  # B = 18 (0x12)
    },
    salidas_esperadas_ram={
        0x00202010: 6,  # MCD(48, 18) = 6
    },
    lineas_ensamblador=[
        "ADDI R1, R0, 0x0020",
        "SHL R1, R1, 16",
        "ADDI R1, R1, 0x2000",
        "LOAD R2, [R1 + 0]",
        "LOAD R3, [R1 + 8]",
        "LOOP_EUCLIDES:",
        "CMP R2, R3",
        "JZ FIN_EUCLIDES",
        "JN B_ES_MAYOR",
        "SUB R2, R2, R3",
        "JMP 0x00200114",
        "B_ES_MAYOR:",
        "SUB R3, R3, R2",
        "JMP 0x00200114",
        "FIN_EUCLIDES:",
        "STORE R2, [R1 + 16]",
        "HLT",
    ],
)

PROGRAMA_FIBONACCI = DefinicionPrograma(
    nombre="fibonacci",
    descripcion="Sucesion de Fibonacci en RAM (7 terminos: 0, 1, 1, 2, 3, 5, 8)",
    bytes_codigo=BYTES_FIBONACCI,
    direccion_base=0x00200200,
    entry_point=0x00200200,
    entradas_ram={},
    salidas_esperadas_ram={
        0x00203000: 0,  # F0
        0x00203008: 1,  # F1
        0x00203010: 1,  # F2
        0x00203018: 2,  # F3
        0x00203020: 3,  # F4
        0x00203028: 5,  # F5
        0x00203030: 8,  # F6
    },
    lineas_ensamblador=[
        "ADDI R1, R0, 0x0020",
        "SHL R1, R1, 16",
        "ADDI R1, R1, 0x3000",
        "ADDI R2, R0, 0",
        "ADDI R3, R0, 1",
        "STORE R2, [R1 + 0]",
        "STORE R3, [R1 + 8]",
        "ADDI R1, R1, 16",
        "ADDI R4, R0, 5",
        "LOOP_FIBONACCI:",
        "ADD R5, R3, R2",
        "STORE R5, [R1 + 0]",
        "ADDI R2, R3, 0",
        "ADDI R3, R5, 0",
        "ADDI R1, R1, 8",
        "SUBI R4, R4, 1",
        "JNZ LOOP_FIBONACCI",
        "HLT",
    ],
)

PROGRAMAS_OFICIALES: Dict[str, DefinicionPrograma] = {
    "factorial": PROGRAMA_FACTORIAL,
    "euclides": PROGRAMA_EUCLIDES,
    "fibonacci": PROGRAMA_FIBONACCI,
}


# ===========================================================================
# 3. Utilidades de Exportacion y Carga en Disco
# ===========================================================================

def exportar_archivos_programas(directorio_salida: str) -> List[str]:
    """
    Exporta en el directorio indicado los archivos binarios (.bin),
    volcados hexadecimales (.hex) y ejecutables estructurados (.e64).
    Retorna la lista de rutas absolutas de los archivos creados.
    """
    os.makedirs(directorio_salida, exist_ok=True)
    rutas_generadas: List[str] = []

    for clave, prog in PROGRAMAS_OFICIALES.items():
        # 1. Archivo .bin crudo
        ruta_bin = os.path.join(directorio_salida, f"{clave}.bin")
        with open(ruta_bin, "wb") as f:
            f.write(prog.bytes_codigo)
        rutas_generadas.append(ruta_bin)

        # 2. Archivo .hex legible
        ruta_hex = os.path.join(directorio_salida, f"{clave}.hex")
        with open(ruta_hex, "w", encoding="utf-8") as f:
            f.write(f"# Enigma-64 - {prog.nombre.upper()}\n")
            f.write(f"# Direccion Base: 0x{prog.direccion_base:08X}\n")
            f.write(f"# Tamano: {prog.tamano_bytes} bytes\n\n")
            f.write(prog.volcado_hexadecimal() + "\n")
        rutas_generadas.append(ruta_hex)

        # 3. Archivo estructurado .e64
        binario_e64 = BinarioEnigma.desde_crudo(
            prog.bytes_codigo,
            direccion_base=prog.direccion_base,
            entry_point=prog.entry_point,
        )
        ruta_e64 = os.path.join(directorio_salida, f"{clave}.e64")
        with open(ruta_e64, "wb") as f:
            f.write(binario_e64.serializar_e64())
        rutas_generadas.append(ruta_e64)

    # Tambien exportamos el firmware del cargador
    ruta_fw = os.path.join(directorio_salida, "cargador_firmware.bin")
    with open(ruta_fw, "wb") as f:
        f.write(BYTES_CARGADOR_FIRMWARE)
    rutas_generadas.append(ruta_fw)

    return rutas_generadas


def inicializar_escenario_prueba(
    ram: RAMMemory,
    banco: BancoRegistros,
    cargador: CargadorEnigma,
    programa: DefinicionPrograma,
) -> Dict[str, Any]:
    """
    Carga un programa en memoria RAM e inicializa todas sus variables de entrada.
    Deja la maquina lista para ejecucion.
    """
    # 1. Cargar binario en RAM y apuntar PC al entry point
    info_carga = cargador.cargar_bytes(
        programa.bytes_codigo,
        direccion_destino=programa.direccion_base,
        entry_point=programa.entry_point,
        configurar_cpu=True,
    )

    # 2. Escribir palabras de 64 bits para las entradas del algoritmo (Big-Endian)
    for direccion, valor in programa.entradas_ram.items():
        _, status = ram.mem_write(
            direccion, valor & MASK64, size_bytes=8, check_alignment=True
        )
        if status != STATUS_READY:
            raise RuntimeError(
                f"Fallo al escribir entrada en 0x{direccion:08X}: estado={status}"
            )

    return info_carga
