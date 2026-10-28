"""
Soporte de Salida MMIO (0xFF001000) para Enigma-64 (Tarea 27).

Permite conectar los programas traducidos desde CacaoCore-64 con el
subsistema de perifericos mapeados en memoria (MMIO) de Enigma-64:
  * Controlador de pantalla CRT (Salida, Base 0xFF001000)
  * Registro de emision de datos (OFFSET_DATA = 0x10 -> 0xFF001010)
  * Formateo y emision de enteros en caracteres ASCII legibles
  * Ejecucion integrada con emulacion de hardware y perifericos
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory
from enigma64.perifericos import (
    BASE_PANTALLA,
    OFFSET_DATA,
    ControladorPantalla,
    Perifericos,
)
from enigma64.registros import BancoRegistros
from spl.traductor.alu import cargar_constante
from spl.traductor.traductor import BASE_CODIGO, BASE_DATOS

PUERTO_SALIDA_PANTALLA: int = BASE_PANTALLA + OFFSET_DATA  # 0xFF001010


def generar_emision_ascii_mmio(
    reg_valor: str = "R1",
    etiqueta_prefijo: str = "MMIO_OUT",
) -> List[str]:
    """
    Genera la secuencia de instrucciones Enigma-64 para convertir un entero
    positivo de 64 bits en reg_valor a caracteres ASCII y emitirlos al registro
    DATA del Controlador de Pantalla MMIO (0xFF001010), cerrando con salto de linea.

    Utiliza R5 para la direccion MMIO, R2 como divisor (10), R3 y R4 como temporales,
    y R7 como contador de digitos en pila.
    """
    lineas = [
        f"; --- Inicio Emision MMIO (Base 0xFF001000, DATA 0xFF001010) ---",
    ]
    lineas.extend(cargar_constante("R5", PUERTO_SALIDA_PANTALLA))

    lbl_cero = f"{etiqueta_prefijo}_ES_CERO"
    lbl_conv = f"{etiqueta_prefijo}_CONVERTIR"
    lbl_div = f"{etiqueta_prefijo}_LOOP_DIV"
    lbl_emit = f"{etiqueta_prefijo}_LOOP_EMIT"
    lbl_fin = f"{etiqueta_prefijo}_FIN"

    lineas.extend([
        f"CMP {reg_valor}, R0",
        f"JZ {lbl_cero}",
        f"JMP {lbl_conv}",
        f"{lbl_cero}:",
        f"ADDI R4, R0, 48",       # '0'
        f"STORE R4, [R5 + 0]",     # Emite '0' a MMIO
        f"JMP {lbl_fin}",
        f"{lbl_conv}:",
        f"ADDI R2, R0, 10",       # Base 10
        f"ADDI R7, R0, 0",        # Contador de digitos
        f"{lbl_div}:",
        f"CMP {reg_valor}, R0",
        f"JZ {lbl_emit}",
        f"DIV R4, {reg_valor}, R2",  # R4 = cociente
        f"MUL R3, R4, R2",          # R3 = cociente * 10
        f"SUB R3, {reg_valor}, R3",  # R3 = residuo (digito actual)
        f"ADDI R3, R3, 48",         # Convertir a ASCII ('0'..'9')
        f"PUSH R3",                 # Guardar digito en pila
        f"ADDI R7, R7, 1",          # Incrementar contador
        f"ADDI {reg_valor}, R4, 0",  # reg_valor = cociente
        f"JMP {lbl_div}",
        f"{lbl_emit}:",
        f"CMP R7, R0",
        f"JZ {lbl_fin}",
        f"POP R4",
        f"STORE R4, [R5 + 0]",     # Emite digito a MMIO
        f"SUBI R7, R7, 1",
        f"JMP {lbl_emit}",
        f"{lbl_fin}:",
        f"ADDI R4, R0, 10",       # Salto de linea '\n'
        f"STORE R4, [R5 + 0]",     # Emite '\n'
        f"; --- Fin Emision MMIO ---",
    ])
    return lineas


def inyectar_salida_mmio(
    codigo_enigma: str,
    variables: Dict[str, int],
    variables_a_imprimir: List[str],
) -> str:
    """
    Inserta la rutina de emision MMIO antes de la instruccion HLT para
    las variables indicadas.
    """
    lineas = codigo_enigma.splitlines()
    lineas_resultado: List[str] = []

    for linea in lineas:
        if linea.split(";")[0].strip() == "HLT":
            for idx, var in enumerate(variables_a_imprimir):
                if var in variables:
                    addr = variables[var]
                    lineas_resultado.append(f"; Cargar variable '{var}' (0x{addr:08X}) para salida MMIO")
                    lineas_resultado.extend(cargar_constante("R5", addr))
                    lineas_resultado.append("LOAD R1, [R5 + 0]")
                    lineas_resultado.extend(generar_emision_ascii_mmio("R1", f"MMIO_{var.upper()}_{idx}"))
            lineas_resultado.append("HLT")
        else:
            lineas_resultado.append(linea)

    return "\n".join(lineas_resultado)


def ejecutar_en_enigma_mmio(
    codigo_enigma: str,
    max_ciclos: int = 1_000_000,
    base_datos: int = BASE_DATOS,
    perifericos: Optional[Perifericos] = None,
) -> Tuple[CPU, BancoRegistros, RAMMemory, Perifericos]:
    """
    Ensambla, carga en 0x00200000, conecta el subsistema de perifericos MMIO
    y ejecuta hasta HLT. Devuelve (cpu, banco, ram, perifericos).
    """
    binario = ensamblar(codigo_enigma, direccion_base=BASE_CODIGO)
    if BASE_CODIGO + len(binario) > base_datos:
        raise ValueError(
            f"El codigo ({len(binario)} bytes) se solapa con .data en 0x{base_datos:08X}"
        )
    ram = RAMMemory()
    banco = BancoRegistros()
    if perifericos is None:
        perifericos = Perifericos()

    for i, byte in enumerate(binario):
        ram.mem_write(BASE_CODIGO + i, byte, 1, check_alignment=False)

    banco.pc = BASE_CODIGO
    banco.sp = 0xEFFFFFF0

    cpu = CPU(ram=ram, banco=banco, perifericos=perifericos)
    cpu.ejecutar(max_ciclos=max_ciclos)
    return cpu, banco, ram, perifericos
