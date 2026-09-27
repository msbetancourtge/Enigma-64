"""
Modulo del Cargador y Manipulador de Bits - Enigma-64 (Noctua Systems).

Implementa las responsabilidades del Integrante 4 (Tarea 10):
  1. Manipulador directo de memoria a nivel de bits y bytes sobre la RAM (Punto 2).
  2. Modelo de ejecutable BinarioEnigma con soporte para binarios planos (.bin),
     binarios estructurados Big-Endian (.e64) y volcados de texto hexadecimal.
  3. Motor del Cargador (CargadorEnigma) con validacion estricta de fronteras de memoria,
     prevencion de colisiones con vectores/pila e inicializacion de registros.
  4. Emulacion de la subrutina de firmware del cargador residente en 0x00001000 (Tarea 9).
  5. Base desacoplada y extensible preparada para el futuro enlazador (relocacion y simbolos).

Autor: Integrante 4 - Cargador & Manipulador de Bits
"""

from __future__ import annotations

import os
import re
import struct
from typing import Any, Dict, List, Optional, Tuple, Union

from .memoria import (
    MMIO_BASE,
    STATUS_ADDR_FAULT,
    STATUS_MISALIGNED,
    STATUS_MMIO,
    STATUS_READY,
    RAMMemory,
)
from .registros import (
    BITS,
    MASK64,
    PC_RESET,
    SP_RESET,
    SR_RESET,
    BancoRegistros,
    hex64,
)

# ---------------------------------------------------------------------------
# Mapa de Memoria Arquitectonico de Enigma-64 (Definido en Tarea 9)
# ---------------------------------------------------------------------------

VECTORES_SISTEMA_START: int = 0x00000000
VECTORES_SISTEMA_END: int = 0x00000FFF

FIRMWARE_LOADER_ADDR: int = 0x00001000

# Area de trabajo del cargador: reservada para tablas de reubicacion y simbolos
LOADER_WORKSPACE_START: int = 0x00100000
LOADER_WORKSPACE_END: int = 0x0011FFFF

# Area de Programas y Datos de Usuario (unica zona valida para carga de ejecutables)
USER_MEM_START: int = 0x00200000
USER_MEM_END: int = 0xBFFFFFFF

# Region de Pila (Stack Pointer arranca en SP_RESET = 0xEFFFFFFF y crece hacia abajo)
STACK_START: int = 0xC0000000
STACK_TOP_RESET: int = 0xEFFFFFFF

# Limite fisico de 4 GiB direccionables (A[63:32] == 0)
MAX_PHYSICAL_ADDR: int = 0xFFFFFFFF

# Cabecera magica para ejecutables estructurados Enigma-64 (Big-Endian)
MAGIC_ENIGMA: bytes = b"ENIG"  # 0x454E4947

# Formato struct de cabecera Enigma-64 (32 bytes, Big-Endian):
# Magic (4s) + Flags/Version (I) + Entry_Point (I) + Target_Address (I)
# + Code_Size (I) + Data_Size (I) + Reloc_Count (I) + Symbol_Count (I)
HEADER_FORMAT_E64: str = ">4s7I"
HEADER_SIZE_E64: int = struct.calcsize(HEADER_FORMAT_E64)  # 32 bytes


# ---------------------------------------------------------------------------
# Jerarquia de Excepciones del Cargador
# ---------------------------------------------------------------------------


class ErrorCargador(Exception):
    """Excepcion base para errores del modulo Cargador."""


class DireccionInvalida(ErrorCargador):
    """La direccion excede los 4 GiB fisicos (A[63:32] != 0) o es negativa."""


class ViolacionProteccionMemoria(ErrorCargador):
    """Intento de cargar codigo o datos fuera del area permitida de usuario."""


class FormatoInvalido(ErrorCargador):
    """Error al parsear o deserializar el archivo binario o de texto."""


# ---------------------------------------------------------------------------
# 1. Manipulador Directo de Memoria a Nivel de Bit y Byte (Tarea 10 - Punto 2)
# ---------------------------------------------------------------------------


def leer_bit(ram: RAMMemory, direccion: int, bit_index: int) -> int:
    """
    Lee un bit individual (0 a 7) en la direccion especificada de la RAM.

    Convencion de bits:
      bit 0 = LSB (menos significativo, 2^0)
      bit 7 = MSB (mas significativo, 2^7)

    :param ram: Instancia del subsistema de memoria RAMMemory.
    :param direccion: Direccion fisica de 64 bits en RAM.
    :param bit_index: Indice del bit (0 a 7).
    :return: 0 o 1 segun el estado del bit.
    :raises ValueError: Si bit_index esta fuera de [0, 7].
    :raises DireccionInvalida: Si la direccion no es valida en la RAM.
    """
    if not (0 <= bit_index <= 7):
        raise ValueError(f"bit_index debe estar entre 0 y 7, se recibio: {bit_index}")

    dato, status = ram.mem_read(direccion, size_bytes=1, check_alignment=False)
    if status != STATUS_READY:
        raise DireccionInvalida(
            f"Fallo al leer direccion 0x{direccion:08X} en RAM. Senal de bus: {status}"
        )

    byte_val = dato if dato is not None else 0
    return (byte_val >> bit_index) & 1


def escribir_bit(ram: RAMMemory, direccion: int, bit_index: int, valor: int) -> None:
    """
    Modifica atomicamente un unico bit en la direccion dada de la RAM sin alterar
    los 7 bits vecinos del byte.

    :param ram: Instancia de RAMMemory.
    :param direccion: Direccion fisica de 64 bits en RAM.
    :param bit_index: Indice del bit (0 a 7).
    :param valor: Nuevo valor para el bit (0 o 1).
    :raises ValueError: Si bit_index no esta en [0, 7] o valor no esta en (0, 1).
    :raises DireccionInvalida: Si la direccion es rechazada por el bus de memoria.
    """
    if not (0 <= bit_index <= 7):
        raise ValueError(f"bit_index debe estar entre 0 y 7, se recibio: {bit_index}")
    if valor not in (0, 1):
        raise ValueError(f"valor del bit debe ser 0 o 1, se recibio: {valor}")

    dato_actual, status = ram.mem_read(direccion, size_bytes=1, check_alignment=False)
    if status != STATUS_READY:
        raise DireccionInvalida(
            f"Fallo al acceder a la direccion 0x{direccion:08X} en RAM. Senal: {status}"
        )

    byte_actual = dato_actual if dato_actual is not None else 0

    if valor == 1:
        nuevo_byte = byte_actual | (1 << bit_index)
    else:
        nuevo_byte = byte_actual & ~(1 << bit_index)

    _, status_w = ram.mem_write(
        direccion, nuevo_byte, size_bytes=1, check_alignment=False
    )
    if status_w != STATUS_READY:
        raise DireccionInvalida(
            f"Fallo al escribir en direccion 0x{direccion:08X}. Senal: {status_w}"
        )


def conmutar_bit(ram: RAMMemory, direccion: int, bit_index: int) -> int:
    """
    Invierte el estado del bit (0 -> 1, 1 -> 0) mediante la operacion logica XOR.

    :param ram: Instancia de RAMMemory.
    :param direccion: Direccion fisica en RAM.
    :param bit_index: Indice del bit (0 a 7).
    :return: El nuevo valor del bit (0 o 1).
    """
    if not (0 <= bit_index <= 7):
        raise ValueError(f"bit_index debe estar entre 0 y 7, se recibio: {bit_index}")

    dato_actual, status = ram.mem_read(direccion, size_bytes=1, check_alignment=False)
    if status != STATUS_READY:
        raise DireccionInvalida(
            f"Fallo al acceder a la direccion 0x{direccion:08X} en RAM. Senal: {status}"
        )

    byte_actual = dato_actual if dato_actual is not None else 0
    nuevo_byte = byte_actual ^ (1 << bit_index)

    _, status_w = ram.mem_write(
        direccion, nuevo_byte, size_bytes=1, check_alignment=False
    )
    if status_w != STATUS_READY:
        raise DireccionInvalida(
            f"Fallo al escribir en direccion 0x{direccion:08X}. Senal: {status_w}"
        )

    return (nuevo_byte >> bit_index) & 1


def byte_a_cadena_bits(ram: RAMMemory, direccion: int) -> str:
    """
    Devuelve la representacion en cadena de 8 bits (ej. '10110001') del byte en RAM.
    Formato desde MSB (bit 7) a LSB (bit 0), ideal para el panel interactivo de la GUI.
    """
    dato, status = ram.mem_read(direccion, size_bytes=1, check_alignment=False)
    if status != STATUS_READY:
        raise DireccionInvalida(
            f"Fallo al leer direccion 0x{direccion:08X}. Senal: {status}"
        )
    byte_val = dato if dato is not None else 0
    return f"{byte_val & 0xFF:08b}"


def escribir_byte_directo(ram: RAMMemory, direccion: int, valor: int) -> None:
    """Escribe un byte directamente en la memoria RAM fisica."""
    _, status = ram.mem_write(
        direccion, valor & 0xFF, size_bytes=1, check_alignment=False
    )
    if status != STATUS_READY:
        raise DireccionInvalida(
            f"Fallo al escribir byte en 0x{direccion:08X}. Senal: {status}"
        )


def leer_byte_directo(ram: RAMMemory, direccion: int) -> int:
    """Lee un byte directamente desde la memoria RAM fisica."""
    dato, status = ram.mem_read(direccion, size_bytes=1, check_alignment=False)
    if status != STATUS_READY:
        raise DireccionInvalida(
            f"Fallo al leer byte en 0x{direccion:08X}. Senal: {status}"
        )
    return dato if dato is not None else 0


# ---------------------------------------------------------------------------
# 2. Modelo de Ejecutable (BinarioEnigma) - Soporte Dual y Futuro Enlazador
# ---------------------------------------------------------------------------


class BinarioEnigma:
    """
    Representa un programa ejecutable para Enigma-64.

    Soporta:
      - Binario plano crudo (.bin): simple volcado de bytes (Tarea 10).
      - Binario estructurado (.e64): cabecera Big-Endian de 32 bytes con
        secciones de codigo (.text), datos (.data), tabla de reubicacion y simbolos.
    """

    FLAG_ABSOLUTO: int = 0x00000000
    FLAG_REUBICABLE: int = 0x00000001

    def __init__(
        self,
        codigo: Union[bytes, bytearray],
        datos: Optional[Union[bytes, bytearray]] = None,
        direccion_base: int = USER_MEM_START,
        entry_point: Optional[int] = None,
        reubicable: bool = False,
        tabla_reubicacion: Optional[List[int]] = None,
        tabla_simbolos: Optional[Dict[str, int]] = None,
    ) -> None:
        self.codigo: bytearray = bytearray(codigo)
        self.datos: bytearray = bytearray(datos) if datos is not None else bytearray()
        self.direccion_base: int = direccion_base
        self.entry_point: int = (
            entry_point if entry_point is not None else direccion_base
        )
        self.reubicable: bool = reubicable
        self.tabla_reubicacion: List[int] = (
            list(tabla_reubicacion) if tabla_reubicacion is not None else []
        )
        self.tabla_simbolos: Dict[str, int] = (
            dict(tabla_simbolos) if tabla_simbolos is not None else {}
        )

    @property
    def tamano_codigo(self) -> int:
        return len(self.codigo)

    @property
    def tamano_datos(self) -> int:
        return len(self.datos)

    @property
    def tamano_total(self) -> int:
        return self.tamano_codigo + self.tamano_datos

    def bytes_completos(self) -> bytearray:
        """Devuelve el cuerpo contiguo de codigo seguido de datos estaticos."""
        return self.codigo + self.datos

    def serializar_e64(self) -> bytes:
        """
        Serializa el ejecutable en formato estructurado .e64 con cabecera Big-Endian
        y tablas de reubicacion / simbolos para el futuro enlazador.
        """
        flags = self.FLAG_REUBICABLE if self.reubicable else self.FLAG_ABSOLUTO
        reloc_count = len(self.tabla_reubicacion)
        symbol_count = len(self.tabla_simbolos)

        cabecera = struct.pack(
            HEADER_FORMAT_E64,
            MAGIC_ENIGMA,
            flags,
            self.entry_point & 0xFFFFFFFF,
            self.direccion_base & 0xFFFFFFFF,
            self.tamano_codigo,
            self.tamano_datos,
            reloc_count,
            symbol_count,
        )

        cuerpo = bytearray(cabecera)
        cuerpo.extend(self.codigo)
        cuerpo.extend(self.datos)

        # Seccion de reubicacion: cada offset como entero de 32 bits Big-Endian
        for offset in self.tabla_reubicacion:
            cuerpo.extend(struct.pack(">I", offset & 0xFFFFFFFF))

        # Seccion de simbolos: longitud nombre (1B) + nombre utf-8 + offset (4B)
        for nombre, direccion in self.tabla_simbolos.items():
            nombre_bytes = nombre.encode("utf-8")[:255]
            cuerpo.append(len(nombre_bytes))
            cuerpo.extend(nombre_bytes)
            cuerpo.extend(struct.pack(">I", direccion & 0xFFFFFFFF))

        return bytes(cuerpo)

    @classmethod
    def deserializar_e64(cls, contenido: bytes) -> BinarioEnigma:
        """
        Deserializa un flujo de bytes con cabecera .e64 de Enigma-64.
        """
        if len(contenido) < HEADER_SIZE_E64:
            raise FormatoInvalido(
                f"El archivo es demasiado corto ({len(contenido)} bytes) para ser un binario .e64"
            )

        (
            magic,
            flags,
            entry_point,
            direccion_base,
            code_size,
            data_size,
            reloc_count,
            symbol_count,
        ) = struct.unpack(HEADER_FORMAT_E64, contenido[:HEADER_SIZE_E64])

        if magic != MAGIC_ENIGMA:
            raise FormatoInvalido(
                f"Firma magica invalida: esperada {MAGIC_ENIGMA!r}, obtenida {magic!r}"
            )

        offset_actual = HEADER_SIZE_E64
        if len(contenido) < offset_actual + code_size + data_size:
            raise FormatoInvalido(
                "El archivo esta truncado: los segmentos de codigo y datos exceden el archivo."
            )

        codigo = contenido[offset_actual : offset_actual + code_size]
        offset_actual += code_size

        datos = contenido[offset_actual : offset_actual + data_size]
        offset_actual += data_size

        # Leer tabla de reubicacion
        tabla_reubicacion: List[int] = []
        for _ in range(reloc_count):
            if offset_actual + 4 > len(contenido):
                break
            (reloc_offset,) = struct.unpack(
                ">I", contenido[offset_actual : offset_actual + 4]
            )
            tabla_reubicacion.append(reloc_offset)
            offset_actual += 4

        # Leer tabla de simbolos
        tabla_simbolos: Dict[str, int] = {}
        for _ in range(symbol_count):
            if offset_actual >= len(contenido):
                break
            nombre_len = contenido[offset_actual]
            offset_actual += 1
            if offset_actual + nombre_len + 4 > len(contenido):
                break
            nombre = contenido[offset_actual : offset_actual + nombre_len].decode(
                "utf-8", errors="replace"
            )
            offset_actual += nombre_len
            (sym_val,) = struct.unpack(
                ">I", contenido[offset_actual : offset_actual + 4]
            )
            offset_actual += 4
            tabla_simbolos[nombre] = sym_val

        return cls(
            codigo=codigo,
            datos=datos,
            direccion_base=direccion_base,
            entry_point=entry_point,
            reubicable=bool(flags & cls.FLAG_REUBICABLE),
            tabla_reubicacion=tabla_reubicacion,
            tabla_simbolos=tabla_simbolos,
        )

    @classmethod
    def desde_crudo(
        cls,
        datos: Union[bytes, bytearray],
        direccion_base: int = USER_MEM_START,
        entry_point: Optional[int] = None,
    ) -> BinarioEnigma:
        """Crea una instancia a partir de un flujo plano de opcodes (.bin crudo)."""
        return cls(
            codigo=datos,
            datos=b"",
            direccion_base=direccion_base,
            entry_point=entry_point,
            reubicable=False,
        )


# ---------------------------------------------------------------------------
# 3. Parser de Volcados en Texto (Hex / Bin / Dec)
# ---------------------------------------------------------------------------


def parsear_texto_a_bytes(contenido: str) -> bytearray:
    """
    Parsea volcados de memoria escritos en texto (hexadecimal, binario o decimal).
    Ignora comentarios (prefijados con #, // o ;) y espacios en blanco.

    Ejemplos soportados:
      "0x12 0x34 0xAB 0xCD"
      "12 34 AB CD # comentario"
      "0b10110001 0b00001111"
      "120, 255, 0, 18"
    """
    buffer = bytearray()
    lineas = contenido.splitlines()

    for linea in lineas:
        # Remover comentarios
        linea_limpia = re.sub(r"(#|//|;).*$", "", linea).strip()
        if not linea_limpia:
            continue

        # Dividir por espacios, comas o tabulaciones
        tokens = re.split(r"[\s,]+", linea_limpia)
        for token in tokens:
            token = token.strip()
            if not token:
                continue

            try:
                if token.startswith(("0x", "0X")):
                    val = int(token, 16)
                elif token.startswith(("0b", "0B")):
                    val = int(token, 2)
                elif re.fullmatch(r"[0-9a-fA-F]{2}", token):
                    val = int(token, 16)
                elif token.isdigit():
                    val = int(token, 10)
                else:
                    raise ValueError(f"Token no reconocido: {token}")

                if not (0 <= val <= 255):
                    raise ValueError(f"Valor fuera de rango de byte (0-255): {val}")

                buffer.append(val)
            except ValueError as e:
                raise FormatoInvalido(
                    f"Error parseando linea '{linea}': {e}"
                ) from None

    if not buffer:
        raise FormatoInvalido("El texto no contiene bytes validos para cargar")

    return buffer


# ---------------------------------------------------------------------------
# 4. Motor Principal del Cargador (CargadorEnigma)
# ---------------------------------------------------------------------------


class CargadorEnigma:
    """
    Cargador del emulador Enigma-64.

    Responsabilidades:
      - Validar el mapa de memoria arquitectonico (0x00200000 a 0xBFFFFFFF).
      - Rechazar invasiones a vectores (< 0x00200000) o colisiones con la Pila (>= 0xC0000000).
      - Inyectar el codigo y datos secuencialmente en la memoria fisica (RAMMemory).
      - Inicializar el contexto del procesador (BancoRegistros): PC, SP, SR, R0, R5.
      - Soportar binarios planos, binarios estructurados .e64 y texto.
    """

    def __init__(
        self,
        ram: Optional[RAMMemory] = None,
        banco: Optional[BancoRegistros] = None,
        cpu: Optional[Any] = None,
    ) -> None:
        self.ram: Optional[RAMMemory] = ram
        self.banco: Optional[BancoRegistros] = banco
        self.cpu: Optional[Any] = cpu
        self.ultima_direccion_cargada: int = 0
        self.ultimo_entry_point: int = 0
        self.ultimo_tamano_cargado: int = 0

    def conectar_hardware(
        self,
        ram: Optional[RAMMemory] = None,
        banco: Optional[BancoRegistros] = None,
        cpu: Optional[Any] = None,
    ) -> None:
        """Conecta o actualiza los componentes de hardware vinculados al cargador."""
        if ram is not None:
            self.ram = ram
        if banco is not None:
            self.banco = banco
        if cpu is not None:
            self.cpu = cpu

    def validar_limites(self, direccion_base: int, tamano: int) -> None:
        """
        Valida que el rango de carga [direccion_base, direccion_base + tamano - 1]
        sea legal segun el mapa de memoria unificado de Enigma-64.

        Reglas:
          1. 64 bits: A[63:32] == 0 (direccion_base y direccion final < 4 GiB).
          2. No direccion negativa.
          3. Limite inferior: direccion_base >= USER_MEM_START (0x00200000).
          4. Limite superior: (direccion_base + tamano) <= STACK_START (0xC0000000).
        """
        if direccion_base < 0 or (direccion_base >> 32) != 0:
            raise DireccionInvalida(
                f"Direccion base fuera de los 4 GiB fisicos: 0x{direccion_base:016X}"
            )

        if tamano <= 0:
            raise ErrorCargador(f"El tamano de los datos a cargar debe ser positivo: {tamano}")

        direccion_final = direccion_base + tamano - 1
        if (direccion_final >> 32) != 0:
            raise DireccionInvalida(
                f"La imagen excede el limite de 4 GiB fisicos en direccion final: 0x{direccion_final:016X}"
            )

        # Validar proteccion de vectores, sistema y area de cargador (< 0x00200000)
        if direccion_base < USER_MEM_START:
            raise ViolacionProteccionMemoria(
                f"Carga rechazada: La direccion base 0x{direccion_base:08X} invade el area "
                f"protegida del sistema (vectores en 0x00000000 o firmware en 0x00001000). "
                f"El espacio de usuario inicia en 0x{USER_MEM_START:08X}."
            )

        # Validar colision con la region de Pila (Stack)
        if direccion_base + tamano > STACK_START:
            raise ViolacionProteccionMemoria(
                f"Carga rechazada: El programa (0x{direccion_base:08X} + {tamano} bytes = "
                f"0x{direccion_base + tamano:08X}) invade la region de Pila/Stack "
                f"(inicia en 0x{STACK_START:08X})."
            )

    def _copiar_a_ram(self, datos: Union[bytes, bytearray], direccion_base: int) -> None:
        """Copia secuencialmente una secuencia de bytes en la RAM física."""
        if self.ram is None:
            raise ErrorCargador("No se ha conectado una instancia de RAMMemory al cargador.")

        for i, byte in enumerate(datos):
            dir_actual = direccion_base + i
            _, status = self.ram.mem_write(
                dir_actual, byte, size_bytes=1, check_alignment=False
            )
            if status != STATUS_READY:
                raise ErrorCargador(
                    f"Fallo al inyectar byte en 0x{dir_actual:08X}. Senal de bus: {status}"
                )

    def inicializar_contexto_hardware(self, entry_point: int) -> None:
        """
        Sincroniza el entorno de registros para iniciar la ejecucion del programa:
          - PC = entry_point
          - SP (R6) = SP_RESET (0x00000000EFFFFFFF)
          - SR = SR_RESET
          - R0 = 0 (cableado a cero)
          - R5 (RV) = entry_point (convencion de retorno del cargador)
        """
        # Si se conecto el BancoRegistros directamente
        if self.banco is not None:
            self.banco.pc = entry_point
            self.banco.sp = SP_RESET
            self.banco.sr = SR_RESET
            self.banco.escribir_nombre("R0", 0)
            self.banco.escribir_nombre("R5", entry_point)

        # Si se paso la CPU y esta expone su banco o registros
        if self.cpu is not None:
            if hasattr(self.cpu, "banco"):
                self.cpu.banco.pc = entry_point
                self.cpu.banco.sp = SP_RESET
                self.cpu.banco.sr = SR_RESET
                self.cpu.banco.escribir_nombre("R0", 0)
                self.cpu.banco.escribir_nombre("R5", entry_point)
            elif hasattr(self.cpu, "pc"):
                self.cpu.pc = entry_point

    def cargar_binario(
        self,
        binario: BinarioEnigma,
        direccion_destino: Optional[int] = None,
        configurar_cpu: bool = True,
    ) -> Dict[str, Any]:
        """
        Carga un objeto BinarioEnigma en la memoria RAM fisica.

        :param binario: Objeto BinarioEnigma con codigo, datos y metadatos.
        :param direccion_destino: Direccion opcional para sobreescribir direccion_base.
        :param configurar_cpu: Si True, inicializa registros de CPU/Banco tras la carga.
        :return: Diccionario con metadatos de la carga.
        """
        dir_base = (
            direccion_destino
            if direccion_destino is not None
            else binario.direccion_base
        )
        tamano = binario.tamano_total

        # 1. Detencion preventiva de la CPU
        if self.cpu is not None and hasattr(self.cpu, "detenido"):
            self.cpu.detenido = True

        # 2. Validacion estricta de fronteras
        self.validar_limites(dir_base, tamano)

        # 3. Reubicacion si el ejecutable es reubicable y cambio de direccion base
        cuerpo = binario.bytes_completos()
        entry_point = binario.entry_point

        if binario.reubicable and dir_base != binario.direccion_base:
            delta = dir_base - binario.direccion_base
            entry_point = (binario.entry_point + delta) & MASK64
            # Aplicar reubicacion de direcciones absolutas registradas en la tabla
            for offset_reloc in binario.tabla_reubicacion:
                if offset_reloc + 8 <= len(cuerpo):
                    (dir_antigua,) = struct.unpack(
                        ">Q", cuerpo[offset_reloc : offset_reloc + 8]
                    )
                    dir_nueva = (dir_antigua + delta) & MASK64
                    cuerpo[offset_reloc : offset_reloc + 8] = struct.pack(
                        ">Q", dir_nueva
                    )

        # 4. Volcado secuencial en memoria RAM
        self._copiar_a_ram(cuerpo, dir_base)

        # 5. Inicializacion de contexto de hardware
        if configurar_cpu:
            self.inicializar_contexto_hardware(entry_point)

        # 6. Reanudacion de CPU
        if self.cpu is not None and hasattr(self.cpu, "detenido"):
            self.cpu.detenido = False

        self.ultima_direccion_cargada = dir_base + tamano - 1
        self.ultimo_entry_point = entry_point
        self.ultimo_tamano_cargado = tamano

        return {
            "direccion_base": dir_base,
            "direccion_final": self.ultima_direccion_cargada,
            "tamano_total": tamano,
            "tamano_codigo": binario.tamano_codigo,
            "tamano_datos": binario.tamano_datos,
            "entry_point": entry_point,
            "entry_point_hex": hex64(entry_point),
            "reubicable": binario.reubicable,
        }

    def cargar_bytes(
        self,
        datos: Union[bytes, bytearray],
        direccion_destino: int = USER_MEM_START,
        entry_point: Optional[int] = None,
        configurar_cpu: bool = True,
    ) -> Dict[str, Any]:
        """
        Carga un flujo crudo de bytes (.bin plano) en la RAM.
        Metodo directo consumido para los algoritmos de prueba de la Tarea 10.
        """
        ep = entry_point if entry_point is not None else direccion_destino
        binario = BinarioEnigma.desde_crudo(
            datos, direccion_base=direccion_destino, entry_point=ep
        )
        return self.cargar_binario(
            binario, direccion_destino=direccion_destino, configurar_cpu=configurar_cpu
        )

    def cargar_texto(
        self,
        texto: str,
        direccion_destino: int = USER_MEM_START,
        entry_point: Optional[int] = None,
        configurar_cpu: bool = True,
    ) -> Dict[str, Any]:
        """Parsea una cadena con volcado en texto (hex/bin/dec) y la carga en RAM."""
        bytes_datos = parsear_texto_a_bytes(texto)
        return self.cargar_bytes(
            bytes_datos,
            direccion_destino=direccion_destino,
            entry_point=entry_point,
            configurar_cpu=configurar_cpu,
        )

    def cargar_archivo(
        self,
        ruta_archivo: str,
        direccion_destino: Optional[int] = None,
        configurar_cpu: bool = True,
    ) -> Dict[str, Any]:
        """
        Lee un archivo desde el host y lo carga en la memoria RAM.
        Detecta automaticamente:
          - Formato estructurado .e64 (cabecera 'ENIG').
          - Archivo de texto .txt (volcado legible hex/bin).
          - Binario plano .bin o cualquier otro archivo binario crudo.
        """
        if not os.path.isfile(ruta_archivo):
            raise FileNotFoundError(f"Archivo no encontrado: {ruta_archivo}")

        with open(ruta_archivo, "rb") as f:
            contenido = f.read()

        if len(contenido) >= 4 and contenido[:4] == MAGIC_ENIGMA:
            binario = BinarioEnigma.deserializar_e64(contenido)
            return self.cargar_binario(
                binario,
                direccion_destino=direccion_destino,
                configurar_cpu=configurar_cpu,
            )

        # Si termina en .txt o es texto legible
        if ruta_archivo.lower().endswith(".txt"):
            try:
                texto = contenido.decode("utf-8")
                return self.cargar_texto(
                    texto,
                    direccion_destino=direccion_destino or USER_MEM_START,
                    configurar_cpu=configurar_cpu,
                )
            except UnicodeDecodeError:
                pass

        # Por defecto tratar como binario plano crudo (.bin)
        dir_base = (
            direccion_destino if direccion_destino is not None else USER_MEM_START
        )
        return self.cargar_bytes(
            contenido,
            direccion_destino=dir_base,
            configurar_cpu=configurar_cpu,
        )


# ---------------------------------------------------------------------------
# 5. Emulacion de la Subrutina de Firmware del Cargador (Tarea 9)
# ---------------------------------------------------------------------------


def emular_subrutina_cargador(
    ram: RAMMemory,
    banco: BancoRegistros,
    cargador: Optional[CargadorEnigma] = None,
) -> int:
    """
    Emula la subrutina del cargador residente teoricamente en 0x00001000 (Tarea 9).

    Protocolo arquitectonico de llamada (registros de entrada):
      - R1: Direccion origen en RAM (ej. buffer DMA de disco/red).
      - R2: Direccion base destino en RAM (debe pertenecer a espacio de usuario).
      - R3: Longitud en bytes a transferir.

    Protocolo de salida y efectos:
      - Transfiere R3 bytes de [R1, R1 + R3 - 1] hacia [R2, R2 + R3 - 1].
      - R5: Queda cargado con la direccion de entrada del programa (R2) para
        que la instruccion siguiente pueda ejecutar un salto 'JMPR R5'.
      - Retorna el valor cargado en R5.
    """
    origen = banco.leer_nombre("R1")
    destino = banco.leer_nombre("R2")
    longitud = banco.leer_nombre("R3")

    c = cargador if cargador is not None else CargadorEnigma(ram=ram, banco=banco)
    c.validar_limites(destino, longitud)

    # Copia secuencial desde el buffer de origen hacia el area de destino
    for offset in range(longitud):
        dir_src = origen + offset
        dir_dst = destino + offset

        dato, status_r = ram.mem_read(dir_src, size_bytes=1, check_alignment=False)
        if status_r != STATUS_READY:
            raise DireccionInvalida(
                f"Fallo al leer direccion origen 0x{dir_src:08X} en firmware loader. Senal: {status_r}"
            )

        val = dato if dato is not None else 0
        _, status_w = ram.mem_write(
            dir_dst, val, size_bytes=1, check_alignment=False
        )
        if status_w != STATUS_READY:
            raise DireccionInvalida(
                f"Fallo al escribir direccion destino 0x{dir_dst:08X} en firmware loader. Senal: {status_w}"
            )

    # El punto de entrada por defecto es la direccion base de destino
    entry_point = destino
    banco.escribir_nombre("R5", entry_point)
    return entry_point
