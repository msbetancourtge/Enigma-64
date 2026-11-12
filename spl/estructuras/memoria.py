"""
Precarga e Inspeccion Directa de Estructuras de Datos sobre RAMMemory.

Tarea 29 - Integrante 4 (Cargador, Directivas, Cabeceras y Enlace):
  - Inyeccion alineada (8 bytes, Big-Endian) de descriptores en BASE_CABECERAS,
    cabeceras inline [base - 16 .. base) y elementos de vectores y matrices en
    RAMMemory, validando fronteras de usuario con CargadorEnigma.validar_limites().
  - Lectura tipada (int con signo, uint de 64 bits o float IEEE 754 binary64) de
    vectores 1D, matrices 2D Row-Major y descriptores de 32 bytes desde RAM.
"""

from __future__ import annotations

import struct
from typing import Dict, Iterable, List, Optional, Sequence, Union

from enigma64.cargador import USER_MEM_START, CargadorEnigma
from enigma64.memoria import STATUS_READY, RAMMemory
from enigma64.registros import MASK64

from .descriptores import (
    BASE_CABECERAS,
    BASE_MATRICES,
    BASE_VECTORES,
    PALABRA_BYTES,
    DescriptorMatriz,
    DescriptorVector,
    ErrorEstructuraDatos,
    EstructuraDescriptor,
    MapaEstructurasRAM,
    ValorElemento,
    desnormalizar_entero_64,
    desnormalizar_float_64,
    direccion_descriptor,
    validar_alineacion_8,
)


def _escribir_bloque_alineado_ram(
    ram: RAMMemory,
    direccion_inicio: int,
    datos_be: bytes,
    cargador: Optional[CargadorEnigma] = None,
) -> int:
    if not datos_be:
        return 0
    validar_alineacion_8(direccion_inicio, "bloque RAM")
    if len(datos_be) % PALABRA_BYTES != 0:
        raise ErrorEstructuraDatos(
            f"El bloque de datos ({len(datos_be)} bytes) no es multiplo de 8 bytes."
        )
    validador = cargador if cargador is not None else CargadorEnigma(ram=ram)
    validador.validar_limites(direccion_inicio, len(datos_be))

    for offset in range(0, len(datos_be), PALABRA_BYTES):
        (palabra,) = struct.unpack(">Q", datos_be[offset : offset + PALABRA_BYTES])
        _, status = ram.mem_write(
            direccion_inicio + offset, palabra, size_bytes=PALABRA_BYTES, check_alignment=True
        )
        if status != STATUS_READY:
            raise ErrorEstructuraDatos(
                f"Fallo al escribir palabra de 64 bits en 0x{direccion_inicio + offset:08X}: {status}"
            )
    return len(datos_be)


def precargar_estructuras_en_ram(
    ram: RAMMemory,
    estructuras: Union[MapaEstructurasRAM, Iterable[EstructuraDescriptor]],
    cargador: Optional[CargadorEnigma] = None,
) -> int:
    """
    Escribe en RAMMemory todas las cabeceras, descriptores y elementos de las estructuras
    dadas, validando no solapamiento, fronteras de usuario y alineacion de 8 bytes.
    Retorna el total de bytes escritos.
    """
    mapa = (
        estructuras
        if isinstance(estructuras, MapaEstructurasRAM)
        else MapaEstructurasRAM(estructuras)
    )
    total_bytes = 0
    for _, dir_seg, bytes_seg in mapa.todos_los_segmentos():
        total_bytes += _escribir_bloque_alineado_ram(ram, dir_seg, bytes_seg, cargador=cargador)
    return total_bytes


def precargar_vector_en_ram(
    ram: RAMMemory,
    elementos: Sequence[ValorElemento],
    direccion_base: int = BASE_VECTORES,
    nombre: str = "vec",
    slot_cabecera: Optional[int] = 0,
    incluir_cabecera_inline: bool = True,
    cargador: Optional[CargadorEnigma] = None,
) -> DescriptorVector:
    """Construye e inyecta un vector 1D en RAMMemory y retorna su DescriptorVector."""
    desc = DescriptorVector(
        nombre=nombre,
        elementos=elementos,
        direccion_base=direccion_base,
        slot_cabecera=slot_cabecera,
        incluir_cabecera_inline=incluir_cabecera_inline,
    )
    precargar_estructuras_en_ram(ram, [desc], cargador=cargador)
    return desc


def precargar_matriz_en_ram(
    ram: RAMMemory,
    filas_2d: Sequence[Sequence[ValorElemento]],
    direccion_base: int = BASE_MATRICES,
    nombre: str = "mat",
    slot_cabecera: Optional[int] = 1,
    incluir_cabecera_inline: bool = True,
    cargador: Optional[CargadorEnigma] = None,
) -> DescriptorMatriz:
    """Construye e inyecta una matriz 2D (Row-Major) en RAMMemory y retorna su DescriptorMatriz."""
    desc = DescriptorMatriz.desde_filas(
        nombre=nombre,
        filas_2d=filas_2d,
        direccion_base=direccion_base,
        slot_cabecera=slot_cabecera,
        incluir_cabecera_inline=incluir_cabecera_inline,
    )
    precargar_estructuras_en_ram(ram, [desc], cargador=cargador)
    return desc


def _leer_palabra_ram(ram: RAMMemory, direccion: int) -> int:
    validar_alineacion_8(direccion, "lectura RAM")
    palabra, status = ram.mem_read(direccion, size_bytes=PALABRA_BYTES, check_alignment=True)
    if status != STATUS_READY or palabra is None:
        raise ErrorEstructuraDatos(
            f"Fallo al leer palabra de 64 bits en 0x{direccion:08X}: {status}"
        )
    return palabra & MASK64


def leer_descriptor_de_ram(
    ram: RAMMemory,
    slot_o_direccion: int,
    base_cabeceras: int = BASE_CABECERAS,
) -> Dict[str, int]:
    """
    Lee un descriptor de 32 bytes desde BASE_CABECERAS (pasando el numero de slot < 0x10000
    o la direccion fisica directa >= USER_MEM_START).
    """
    dir_desc = (
        slot_o_direccion
        if slot_o_direccion >= USER_MEM_START
        else direccion_descriptor(slot_o_direccion, base_cabeceras)
    )
    tipo = _leer_palabra_ram(ram, dir_desc + 0)
    base = _leer_palabra_ram(ram, dir_desc + 8)
    filas = _leer_palabra_ram(ram, dir_desc + 16)
    cols = _leer_palabra_ram(ram, dir_desc + 24)
    return {
        "direccion_descriptor": dir_desc,
        "tipo": tipo,
        "direccion_base": base,
        "filas": filas,
        "longitud": filas,
        "columnas": cols,
    }


def leer_vector_de_ram(
    ram: RAMMemory,
    direccion_base: int = BASE_VECTORES,
    longitud: Optional[int] = None,
    modo: str = "int",
) -> List[Union[int, float]]:
    """
    Extrae un vector de 64 bits desde RAMMemory. Si longitud es None, lee [direccion_base - 8].
    Modos soportados: 'int' (entero con signo), 'uint' (64 bits sin signo), 'float' (IEEE 754).
    """
    validar_alineacion_8(direccion_base, "direccion_base vector")
    n = _leer_palabra_ram(ram, direccion_base - 8) if longitud is None else longitud
    if n < 0:
        raise ErrorEstructuraDatos(f"Longitud invalida al leer vector: {n}")

    salida: List[Union[int, float]] = []
    for i in range(n):
        raw = _leer_palabra_ram(ram, direccion_base + (i << 3))
        if modo == "int":
            salida.append(desnormalizar_entero_64(raw, con_signo=True))
        elif modo == "uint":
            salida.append(raw)
        elif modo == "float":
            salida.append(desnormalizar_float_64(raw))
        else:
            raise ErrorEstructuraDatos(f"Modo de lectura desconocido: {modo!r}")
    return salida


def leer_matriz_de_ram(
    ram: RAMMemory,
    direccion_base: int = BASE_MATRICES,
    filas: Optional[int] = None,
    columnas: Optional[int] = None,
    modo: str = "int",
) -> List[List[Union[int, float]]]:
    """
    Extrae una matriz 2D almacenada en orden Row-Major desde RAMMemory.
    Si filas o columnas son None, los lee de la cabecera inline [base - 16] y [base - 8].
    """
    validar_alineacion_8(direccion_base, "direccion_base matriz")
    f = _leer_palabra_ram(ram, direccion_base - 16) if filas is None else filas
    c = _leer_palabra_ram(ram, direccion_base - 8) if columnas is None else columnas

    plana = leer_vector_de_ram(ram, direccion_base=direccion_base, longitud=f * c, modo=modo)
    if c == 0:
        return [[] for _ in range(f)]
    return [plana[i * c : (i + 1) * c] for i in range(f)]
