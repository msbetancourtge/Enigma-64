"""
Modulos objeto de ejemplo para el Enlazador de Enigma-64.

Construyen a mano lo que emitiria el backend del ensamblador para un programa
de dos modulos, usando los cinco tipos de marca de reubicacion. Los campos
reubicables quedan en cero: el enlazador escribe en ellos S + A.

  principal.obj  (.text 57 B, .data 32 B, .bss 16 B; entrada en main)
    +0x00 main:   ADDI R1, R0, %hi(valores)  HI16  en +0x02 -> valores (local)
    +0x04         SHL  R1, R1, 16
    +0x08         ADDI R1, R1, %lo(valores)  LO16  en +0x0A -> valores (local)
    +0x0C         LOAD R2, [R1 + 0]          R2 = a
    +0x10         LOAD R3, [R1 + 8]          R3 = b
    +0x14         CALL sumar                 ABS32 en +0x15 -> sumar (importado)
    +0x19         CMP  R5, R0
    +0x1C         JZ   error                 REL16 en +0x1D -> error (importado)
    +0x1F         STORE R5, [R1 + 16]        resultado = a + b
    +0x23         LOAD R4, [R1 + 24]         R4 = puntero (ABS64 en .data+0x18 -> copia)
    +0x27         STORE R5, [R4 + 0]         copia = a + b
    +0x2B         JMP  fin                   ABS32 en +0x2C -> fin (local)
    +0x30 trampa: ADDI R5, R0, 0x0BAD        solo se ejecuta si JMP quedo mal reubicado
    +0x34         STORE R5, [R1 + 16]
    +0x38 fin:    HLT

  libmat.obj  (.text 13 B)
    +0x00 sumar:  ADD  R5, R2, R3            exportado
    +0x03         RET
    +0x04 error:  ADDI R5, R0, 0x00EE        exportado; usa el R1 que dejo main
    +0x08         STORE R5, [R1 + 16]
    +0x0C         HLT

Generar los archivos:  python -m enigma64.enlazador.ejemplos [directorio]
"""

from __future__ import annotations

import os
import struct
import sys
from typing import List

from .objeto import (
    REUB_ABS32,
    REUB_ABS64,
    REUB_HI16,
    REUB_LO16,
    REUB_REL16,
    SIMBOLO_DATO,
    SIMBOLO_FUNCION,
    MarcaReubicacion,
    ModuloObjeto,
    SeccionObjeto,
    SimboloObjeto,
)

# Valores de entrada del programa de ejemplo: resultado esperado a + b = 42
VALOR_A: int = 30
VALOR_B: int = 12
# Lo que escribe la rutina error de libmat cuando a + b == 0
CODIGO_ERROR: int = 0x00EE

CODIGO_PRINCIPAL: bytes = bytes([
    # +0x00 main: ADDI R1, R0, %hi(valores)
    0x14, 0x10, 0x00, 0x00,
    # +0x04 SHL R1, R1, 16
    0x24, 0x11, 0x00, 0x10,
    # +0x08 ADDI R1, R1, %lo(valores)
    0x14, 0x11, 0x00, 0x00,
    # +0x0C LOAD R2, [R1 + 0]
    0x30, 0x21, 0x00, 0x00,
    # +0x10 LOAD R3, [R1 + 8]
    0x30, 0x31, 0x00, 0x08,
    # +0x14 CALL sumar
    0x4A, 0x00, 0x00, 0x00, 0x00,
    # +0x19 CMP R5, R0
    0x27, 0x05, 0x00,
    # +0x1C JZ error
    0x41, 0x00, 0x00,
    # +0x1F STORE R5, [R1 + 16]
    0x31, 0x51, 0x00, 0x10,
    # +0x23 LOAD R4, [R1 + 24]
    0x30, 0x41, 0x00, 0x18,
    # +0x27 STORE R5, [R4 + 0]
    0x31, 0x54, 0x00, 0x00,
    # +0x2B JMP fin
    0x40, 0x00, 0x00, 0x00, 0x00,
    # +0x30 trampa: ADDI R5, R0, 0x0BAD
    0x14, 0x50, 0x0B, 0xAD,
    # +0x34 STORE R5, [R1 + 16]
    0x31, 0x51, 0x00, 0x10,
    # +0x38 fin: HLT
    0x00,
])

# valores[0] = a, valores[1] = b, resultado, puntero (-> copia)
DATOS_PRINCIPAL: bytes = struct.pack(">QQQQ", VALOR_A, VALOR_B, 0, 0)

CODIGO_LIBMAT: bytes = bytes([
    # +0x00 sumar: ADD R5, R2, R3
    0x10, 0x52, 0x30,
    # +0x03 RET
    0x4C,
    # +0x04 error: ADDI R5, R0, 0x00EE
    0x14, 0x50, 0x00, 0xEE,
    # +0x08 STORE R5, [R1 + 16]
    0x31, 0x51, 0x00, 0x10,
    # +0x0C HLT
    0x00,
])


def construir_modulo_principal() -> ModuloObjeto:
    """Modulo con codigo, datos y reserva que importa sumar y error de libmat."""
    texto, datos, bss = 0, 1, 2
    simbolos = [
        SimboloObjeto.exportado("main", texto, 0x00, SIMBOLO_FUNCION),
        SimboloObjeto.local("trampa", texto, 0x30, SIMBOLO_FUNCION),
        SimboloObjeto.local("fin", texto, 0x38),
        SimboloObjeto.local("valores", datos, 0x00, SIMBOLO_DATO),
        SimboloObjeto.exportado("resultado", datos, 0x10, SIMBOLO_DATO),
        SimboloObjeto.local("puntero", datos, 0x18, SIMBOLO_DATO),
        SimboloObjeto.exportado("copia", bss, 0x00, SIMBOLO_DATO),
        SimboloObjeto.importado("sumar", SIMBOLO_FUNCION),
        SimboloObjeto.importado("error", SIMBOLO_FUNCION),
    ]
    indice = {simbolo.nombre: i for i, simbolo in enumerate(simbolos)}
    return ModuloObjeto(
        nombre="principal",
        secciones=[
            SeccionObjeto.texto(CODIGO_PRINCIPAL),
            SeccionObjeto.datos(DATOS_PRINCIPAL),
            SeccionObjeto.reserva(16),
        ],
        simbolos=simbolos,
        reubicaciones=[
            MarcaReubicacion(texto, 0x02, REUB_HI16, indice["valores"]),
            MarcaReubicacion(texto, 0x0A, REUB_LO16, indice["valores"]),
            MarcaReubicacion(texto, 0x15, REUB_ABS32, indice["sumar"]),
            MarcaReubicacion(texto, 0x1D, REUB_REL16, indice["error"]),
            MarcaReubicacion(texto, 0x2C, REUB_ABS32, indice["fin"]),
            MarcaReubicacion(datos, 0x18, REUB_ABS64, indice["copia"]),
        ],
        entrada=(texto, 0x00),
    )


def construir_modulo_libmat() -> ModuloObjeto:
    """Biblioteca sin dependencias que exporta sumar y error."""
    return ModuloObjeto(
        nombre="libmat",
        secciones=[SeccionObjeto.texto(CODIGO_LIBMAT)],
        simbolos=[
            SimboloObjeto.exportado("sumar", 0, 0x00, SIMBOLO_FUNCION),
            SimboloObjeto.exportado("error", 0, 0x04, SIMBOLO_FUNCION),
        ],
    )


def exportar_ejemplos(directorio: str) -> List[str]:
    """Escribe principal.obj y libmat.obj en el directorio y devuelve las rutas."""
    os.makedirs(directorio, exist_ok=True)
    rutas = []
    for modulo in (construir_modulo_principal(), construir_modulo_libmat()):
        ruta = os.path.join(directorio, f"{modulo.nombre}.obj")
        modulo.guardar(ruta)
        rutas.append(ruta)
    return rutas


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join("programas", "objetos")
    for ruta in exportar_ejemplos(destino):
        print(f"{ruta} ({os.path.getsize(ruta)} bytes)")
