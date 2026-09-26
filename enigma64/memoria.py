"""
Modulo de Memoria RAM y Buses - Enigma-64.

Implementa el subsistema de memoria fisica y control de buses:
  * Espacio de memoria fisica de 4 GiB direccionable a nivel de byte.
  * Paginacion por software mediante diccionario disperso (Sparse Memory, 4 KiB/bloque).
  * Formato de ordenamiento de bytes Big-Endian.
  * Decodificacion de direcciones de 64 bits con validacion de bits superiores (A[63:32] == 0).
  * Deteccion y enrutamiento hacia el espacio MMIO (0xFF000000 - 0xFFFFFFFF).
  * Control estricto de alineacion natural para accesos a datos.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Optional, Tuple

# Constantes del bus de memoria y limites de direccionamiento

PAGE_SIZE: int = 4096  # Bloques de 4 KiB
VALID_SIZES: FrozenSet[int] = frozenset({1, 2, 4, 8})

# Rango base para perifericos mapeados en memoria (MMIO)
MMIO_BASE: int = 0xFF000000

# Señales de estado del bus de control
STATUS_READY: str = "READY"
STATUS_ADDR_FAULT: str = "ADDR_FAULT"
STATUS_MMIO: str = "MMIO"
STATUS_MISALIGNED: str = "MISALIGNED"


class InvalidAccessSizeError(ValueError):
    """Lanzada cuando se solicita un tamaño de acceso no soportado por el bus."""


class RAMMemory:
    """
    Controlador de Memoria RAM fisica y buses.

    No reserva 4 GiB reales en memoria, utiliza paginacion dispersa
    (Sparse Memory) con bloques de 4 KiB bajo demanda dentro de un diccionario.
    """

    STATUS_READY: str = STATUS_READY
    STATUS_ADDR_FAULT: str = STATUS_ADDR_FAULT
    STATUS_MMIO: str = STATUS_MMIO
    STATUS_MISALIGNED: str = STATUS_MISALIGNED
    VALID_SIZES: FrozenSet[int] = VALID_SIZES

    def __init__(self, page_size: int = PAGE_SIZE) -> None:
        """
        Inicializa el subsistema de memoria con soporte de paginacion.

        :param page_size: Tamaño de pagina en bytes (por defecto 4 KiB). Debe ser potencia de 2.
        """
        if page_size <= 0 or (page_size & (page_size - 1)) != 0:
            raise ValueError("Page size must be a positive power of 2.")

        self.page_size: int = page_size
        # Diccionario de paginas: clave = page_index, valor = bytearray de tamaño page_size
        self.pages: Dict[int, bytearray] = {}

    def reset(self) -> None:
        """Vacia el diccionario de paginas liberando toda la memoria reservada."""
        self.pages.clear()

    @property
    def allocated_blocks(self) -> List[int]:
        """Lista ordenada de los indices de bloques actualmente presentes en memoria."""
        return sorted(self.pages.keys())

    @property
    def allocated_bytes(self) -> int:
        """Cantidad total de bytes reales ocupados por las paginas instanciadas."""
        return len(self.pages) * self.page_size

    def _validate_address(self, address: int, size_bytes: int, check_alignment: bool) -> Optional[str]:
        """
        Valida la direccion entrante en el bus segun las reglas arquitectonicas.

        1. Rango logico de 64 bits: A[63:32] debe ser 0x00000000.
        2. Deteccion de MMIO: A[31:24] == 0xFF.
        3. Control de alineacion: address % size_bytes == 0.

        :return: Señal de estado de error/enrutamiento o None si procede hacia la RAM.
        """
        # 1. Validacion de rango de 64 bits y bits superiores A[63:32]
        if address < 0 or (address >> 32) != 0:
            return STATUS_ADDR_FAULT

        # 2. Deteccion de rango MMIO en A[31:24]
        start_segment = (address >> 24) & 0xFF
        end_address = address + size_bytes - 1
        end_segment = (end_address >> 24) & 0xFF

        if start_segment == 0xFF or end_segment == 0xFF:
            return STATUS_MMIO

        # 3. Control de alineacion natural
        if check_alignment and (address % size_bytes != 0):
            return STATUS_MISALIGNED

        return None

    def mem_read(
        self, address: int, size_bytes: int, check_alignment: bool = True
    ) -> Tuple[Optional[int], str]:
        """
        Lee una palabra de 1, 2, 4 u 8 bytes en formato Big-Endian desde la memoria.

        Si se accede a una pagina que aun no ha sido escrita, retorna ceros
        sin instanciar la pagina en el diccionario.

        :param address: Direccion de memoria de 64 bits.
        :param size_bytes: Ancho de acceso en bytes (1, 2, 4 u 8).
        :param check_alignment: Habilita el control estricto de alineacion (True por defecto).
        :return: Tupla (data, status). data contiene el entero leido o None si la operacion aborta.
        """
        if size_bytes not in VALID_SIZES:
            raise InvalidAccessSizeError(
                f"Unsupported access size: {size_bytes}. Allowed sizes: {sorted(VALID_SIZES)}"
            )

        status = self._validate_address(address, size_bytes, check_alignment)
        if status is not None:
            return None, status

        # Lectura byte a byte soportando cruce continuo entre limites de bloques
        raw_bytes = bytearray(size_bytes)
        for offset_idx in range(size_bytes):
            current_addr = address + offset_idx
            page_index = current_addr // self.page_size
            page_offset = current_addr % self.page_size

            page = self.pages.get(page_index)
            if page is not None:
                raw_bytes[offset_idx] = page[page_offset]
            else:
                raw_bytes[offset_idx] = 0

        data = int.from_bytes(raw_bytes, byteorder="big", signed=False)
        return data, STATUS_READY

    def mem_write(
        self, address: int, data: int, size_bytes: int, check_alignment: bool = True
    ) -> Tuple[Optional[int], str]:
        """
        Escribe una palabra de 1, 2, 4 u 8 bytes en memoria en formato Big-Endian.

        Instancia la pagina bajo demanda en el diccionario si aun no existe.

        :param address: Direccion de memoria de 64 bits.
        :param data: Valor entero a escribir.
        :param size_bytes: Ancho de acceso en bytes (1, 2, 4 u 8).
        :param check_alignment: Habilita el control estricto de alineacion (True por defecto).
        :return: Tupla (None, status).
        """
        if size_bytes not in VALID_SIZES:
            raise InvalidAccessSizeError(
                f"Unsupported access size: {size_bytes}. Allowed sizes: {sorted(VALID_SIZES)}"
            )

        status = self._validate_address(address, size_bytes, check_alignment)
        if status is not None:
            return None, status

        mask = (1 << (size_bytes * 8)) - 1
        data_bytes = (data & mask).to_bytes(size_bytes, byteorder="big", signed=False)

        # Escritura byte a byte instanciando bloques bajo demanda
        for offset_idx in range(size_bytes):
            current_addr = address + offset_idx
            page_index = current_addr // self.page_size
            page_offset = current_addr % self.page_size

            if page_index not in self.pages:
                self.pages[page_index] = bytearray(self.page_size)

            self.pages[page_index][page_offset] = data_bytes[offset_idx]

        return None, STATUS_READY
