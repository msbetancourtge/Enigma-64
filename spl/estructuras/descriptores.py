"""
Descriptores y Constructores de Cabeceras de Listas (1D) y Matrices (2D) en Memoria.

Tarea 29 - Integrante 4 (Cargador, Directivas, Cabeceras y Enlace):
  1. Constantes arquitectonicas sincronizadas con spl/include/layout_datos.inc y
     spl/include/estructuras.inc (Zonas 1 a 4 en >= 0x00210000).
  2. Normalizacion universal de elementos (enteros con/sin signo y punto flotante
     IEEE 754 binary64) a palabras crudas de 64 bits Big-Endian, exigiendo
     alineacion natural estricta a multiplos de 8 bytes (addr % 8 == 0).
  3. Constructores de cabeceras y descriptores en memoria:
     - DescriptorVector: lista 1D contigua Dir(V[i]) = B + (i * 8), cabecera
       inline [B - 16] = 1, [B - 8] = N y descriptor de 32 bytes en BASE_CABECERAS.
     - DescriptorMatriz: matriz 2D Row-Major Dir(M[i][j]) = B + ((i * C + j) * 8),
       cabecera inline [B - 16] = F, [B - 8] = C y descriptor de 32 bytes.
     - MapaEstructurasRAM: registro de estructuras con deteccion de colisiones y
       solapamientos de segmentos en RAM.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from enigma64.cargador import USER_MEM_START, CargadorEnigma
from enigma64.registros import MASK64
from spl.ensamblador.literales import (
    LiteralInvalido,
    entero_decimal_64,
    literal_a_bits,
)

# ---------------------------------------------------------------------------
# Constantes Arquitectonicas (sincronizadas con layout_datos.inc y estructuras.inc)
# ---------------------------------------------------------------------------

BASE_CODIGO: int = USER_MEM_START        # 0x00200000
MIN_DATOS_ESTRUCTURAS: int = 0x00201000  # Frontera inferior de datos de usuario

BASE_CABECERAS: int = 0x00210000
TAM_CABECERAS: int = 0x00010000
LIMITE_CABECERAS: int = 0x00220000

BASE_VECTORES: int = 0x00220000
TAM_VECTORES: int = 0x00040000
LIMITE_VECTORES: int = 0x00260000

BASE_MATRICES: int = 0x00260000
TAM_MATRICES: int = 0x00080000
LIMITE_MATRICES: int = 0x002E0000

BASE_BUFFERS: int = 0x002E0000
TAM_BUFFERS: int = 0x00020000
LIMITE_BUFFERS: int = 0x00300000

PILA_ESTRUCTURAS: int = 0x00400000       # Puntero de pila alineado a 8 bytes

PALABRA_BYTES: int = 8
DESC_TAM_BYTES: int = 32                 # 4 palabras de 64 bits por descriptor
TIPO_VECTOR: int = 1
TIPO_MATRIZ: int = 2

INT64_MIN: int = -(1 << 63)
INT64_MAX: int = (1 << 63) - 1
UINT64_MAX: int = (1 << 64) - 1

ValorElemento = Union[int, float, str]
EstructuraDescriptor = Union["DescriptorVector", "DescriptorMatriz"]


class ErrorEstructuraDatos(ValueError):
    """Error de alineacion, dimension, rango o solapamiento en estructuras de datos."""


# ---------------------------------------------------------------------------
# 1. Normalizacion de Palabras de 64 Bits y Validacion de Alineacion
# ---------------------------------------------------------------------------


def validar_alineacion_8(direccion: int, contexto: str = "direccion") -> None:
    """Exige que una direccion o desplazamiento sea multiplo exacto de 8 bytes."""
    if direccion % PALABRA_BYTES != 0:
        raise ErrorEstructuraDatos(
            f"Desalineacion detectada en {contexto}: 0x{direccion:08X} no es multiplo de 8 bytes "
            f"(provocaria STATUS_MISALIGNED en Enigma-64)."
        )


def normalizar_palabra_64(valor: ValorElemento) -> int:
    """
    Convierte un entero (con o sin signo), float IEEE 754 binary64 o literal en texto
    a su patron crudo sin signo de 64 bits [0, 2^64 - 1].
    """
    if isinstance(valor, bool):
        return 1 if valor else 0

    if isinstance(valor, int):
        if valor < INT64_MIN or valor > UINT64_MAX:
            raise ErrorEstructuraDatos(
                f"Entero fuera del rango de 64 bits [{INT64_MIN}, {UINT64_MAX}]: {valor}"
            )
        return valor & MASK64

    if isinstance(valor, float):
        if math.isnan(valor) or math.isinf(valor):
            raise ErrorEstructuraDatos(
                f"Flotante no finito no admitido en normalizacion de estructura: {valor!r}"
            )
        return struct.unpack(">Q", struct.pack(">d", valor))[0]

    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            raise ErrorEstructuraDatos("Literal vacio en elemento de estructura")
        low = texto.lower()
        try:
            if low.startswith(("-0x", "+0x", "0x")):
                entero = int(texto, 16)
                return normalizar_palabra_64(entero)
            if low.startswith(("-0b", "+0b", "0b")):
                entero = int(texto, 2)
                return normalizar_palabra_64(entero)
            if "." in texto or "e" in low:
                return literal_a_bits(texto)
            entero = entero_decimal_64(texto)
            return entero & MASK64
        except (ValueError, LiteralInvalido) as exc:
            raise ErrorEstructuraDatos(
                f"Literal invalido o fuera de rango de 64 bits: {valor!r}"
            ) from exc

    raise ErrorEstructuraDatos(f"Tipo de elemento no soportado: {type(valor).__name__}")


def desnormalizar_entero_64(palabra: int, con_signo: bool = True) -> int:
    """Convierte un patron crudo de 64 bits a entero Python con o sin signo."""
    raw = palabra & MASK64
    if con_signo and raw >= (1 << 63):
        return raw - (1 << 64)
    return raw


def desnormalizar_float_64(palabra: int) -> float:
    """Interpreta un patron crudo de 64 bits como double IEEE 754 Big-Endian."""
    return struct.unpack(">d", struct.pack(">Q", palabra & MASK64))[0]


def direccion_descriptor(slot: int, base_cabeceras: int = BASE_CABECERAS) -> int:
    """Calcula y valida la direccion de un descriptor de 32 bytes en BASE_CABECERAS."""
    if slot < 0:
        raise ErrorEstructuraDatos(f"El indice de slot de cabecera no puede ser negativo: {slot}")
    validar_alineacion_8(base_cabeceras, "base_cabeceras")
    direccion = base_cabeceras + (slot * DESC_TAM_BYTES)
    if base_cabeceras == BASE_CABECERAS and direccion + DESC_TAM_BYTES > LIMITE_CABECERAS:
        raise ErrorEstructuraDatos(
            f"El descriptor en slot {slot} (0x{direccion:08X}) excede LIMITE_CABECERAS "
            f"(0x{LIMITE_CABECERAS:08X})."
        )
    return direccion


# ---------------------------------------------------------------------------
# 2. Constructores / Descriptores de Listas (Vectores 1D) y Matrices (2D)
# ---------------------------------------------------------------------------


@dataclass
class DescriptorVector:
    """
    Descriptor formal de una lista / vector 1D en la memoria lineal de Enigma-64.

    Gestiona simultaneamente:
      - Datos contiguos en [direccion_base + 8*i] para 0 <= i < longitud.
      - Cabecera inline opcional en [direccion_base - 16] = 1 y [direccion_base - 8] = N
        (compatible con VEC_LEN de vec.asm y con el modo externo de merge_sort.asm).
      - Descriptor de 32 bytes en BASE_CABECERAS + slot * 32 (opcional si slot_cabecera=None).
    """

    nombre: str
    elementos: Sequence[ValorElemento] = field(default_factory=list)
    direccion_base: int = BASE_VECTORES
    longitud: Optional[int] = None
    slot_cabecera: Optional[int] = 0
    incluir_cabecera_inline: bool = True
    base_cabeceras: int = BASE_CABECERAS
    palabras_datos: List[int] = field(init=False)

    def __post_init__(self) -> None:
        if not self.nombre or not self.nombre.strip():
            raise ErrorEstructuraDatos("El nombre del vector no puede estar vacio.")
        validar_alineacion_8(self.direccion_base, f"vector '{self.nombre}'")

        convertidos = [normalizar_palabra_64(v) for v in self.elementos]
        if self.longitud is None:
            self.longitud = len(convertidos)
        elif self.longitud < 0:
            raise ErrorEstructuraDatos(
                f"La longitud del vector '{self.nombre}' no puede ser negativa: {self.longitud}"
            )
        elif self.longitud < len(convertidos):
            raise ErrorEstructuraDatos(
                f"longitud={self.longitud} es menor que la cantidad de elementos iniciales "
                f"({len(convertidos)}) en '{self.nombre}'."
            )
        elif self.longitud > len(convertidos):
            convertidos.extend([0] * (self.longitud - len(convertidos)))

        self.palabras_datos = convertidos

        cargador_validador = CargadorEnigma()
        if self.incluir_cabecera_inline:
            cargador_validador.validar_limites(self.direccion_base - 16, 16)
        cargador_validador.validar_limites(
            self.direccion_base, max(self.tamano_datos_bytes, PALABRA_BYTES)
        )
        if self.slot_cabecera is not None:
            dir_desc = direccion_descriptor(self.slot_cabecera, self.base_cabeceras)
            cargador_validador.validar_limites(dir_desc, DESC_TAM_BYTES)

    @property
    def tipo_estructura(self) -> int:
        return TIPO_VECTOR

    @property
    def tamano_datos_bytes(self) -> int:
        assert self.longitud is not None
        return self.longitud * PALABRA_BYTES

    @property
    def dir_descriptor(self) -> Optional[int]:
        if self.slot_cabecera is None:
            return None
        return direccion_descriptor(self.slot_cabecera, self.base_cabeceras)

    def direccion_elemento(self, indice: int) -> int:
        """Retorna Dir(V[i]) = B + (i * 8) validando el rango [0, longitud)."""
        assert self.longitud is not None
        if not (0 <= indice < self.longitud):
            raise ErrorEstructuraDatos(
                f"Indice {indice} fuera de rango [0, {self.longitud}) en vector '{self.nombre}'."
            )
        return self.direccion_base + (indice << 3)

    def palabras_descriptor(self) -> Tuple[int, int, int, int]:
        """Retorna las 4 palabras de 64 bits del descriptor: (tipo, base, N, 1)."""
        assert self.longitud is not None
        return (TIPO_VECTOR, self.direccion_base, self.longitud, 1)

    def bytes_descriptor_big_endian(self) -> bytes:
        tipo, base, n, stride = self.palabras_descriptor()
        return struct.pack(">4Q", tipo, base & MASK64, n & MASK64, stride)

    def bytes_cabecera_inline_big_endian(self) -> bytes:
        """Empaqueta [flag_inicializado = 1, longitud = N] para [base - 16 .. base)."""
        assert self.longitud is not None
        return struct.pack(">2Q", 1, self.longitud & MASK64)

    def bytes_datos_big_endian(self) -> bytes:
        if not self.palabras_datos:
            return b""
        return b"".join(struct.pack(">Q", w & MASK64) for w in self.palabras_datos)

    def segmentos_memoria(self) -> List[Tuple[str, int, bytes]]:
        """Devuelve todos los bloques (etiqueta, direccion_inicio, bytes_be) a escribir en RAM."""
        segmentos: List[Tuple[str, int, bytes]] = []
        if self.dir_descriptor is not None:
            segmentos.append(
                (f"{self.nombre}.descriptor", self.dir_descriptor, self.bytes_descriptor_big_endian())
            )
        if self.incluir_cabecera_inline:
            segmentos.append(
                (
                    f"{self.nombre}.cabecera_inline",
                    self.direccion_base - 16,
                    self.bytes_cabecera_inline_big_endian(),
                )
            )
        datos = self.bytes_datos_big_endian()
        if datos:
            segmentos.append((f"{self.nombre}.datos", self.direccion_base, datos))
        return segmentos


@dataclass
class DescriptorMatriz:
    """
    Descriptor formal de una matriz 2D almacenada en orden por filas (Row-Major):
      Dir(M[i][j]) = B + ((i * C + j) * 8)

    Gestiona simultaneamente:
      - F * C palabras contiguas de 64 bits en [direccion_base + (i * C + j) * 8].
      - Cabecera inline opcional en [direccion_base - 16] = F y [direccion_base - 8] = C
        (compatible con MAT_ROWS y MAT_COLS de cabeceras.asm).
      - Descriptor de 32 bytes en BASE_CABECERAS + slot * 32: (2, base, F, C).
    """

    nombre: str
    filas: int
    columnas: int
    elementos_lineales: Sequence[ValorElemento] = field(default_factory=list)
    direccion_base: int = BASE_MATRICES
    slot_cabecera: Optional[int] = 1
    incluir_cabecera_inline: bool = True
    base_cabeceras: int = BASE_CABECERAS
    palabras_datos: List[int] = field(init=False)

    def __post_init__(self) -> None:
        if not self.nombre or not self.nombre.strip():
            raise ErrorEstructuraDatos("El nombre de la matriz no puede estar vacio.")
        if self.filas < 0 or self.columnas < 0:
            raise ErrorEstructuraDatos(
                f"Dimensiones invalidas en matriz '{self.nombre}': ({self.filas}, {self.columnas})."
            )
        validar_alineacion_8(self.direccion_base, f"matriz '{self.nombre}'")

        total = self.filas * self.columnas
        convertidos = [normalizar_palabra_64(v) for v in self.elementos_lineales]
        if not convertidos and total > 0:
            convertidos = [0] * total
        elif len(convertidos) != total:
            raise ErrorEstructuraDatos(
                f"La matriz '{self.nombre}' de {self.filas}x{self.columnas} requiere {total} "
                f"elementos, pero se recibieron {len(convertidos)}."
            )

        self.palabras_datos = convertidos

        cargador_validador = CargadorEnigma()
        if self.incluir_cabecera_inline:
            cargador_validador.validar_limites(self.direccion_base - 16, 16)
        cargador_validador.validar_limites(
            self.direccion_base, max(self.tamano_datos_bytes, PALABRA_BYTES)
        )
        if self.slot_cabecera is not None:
            dir_desc = direccion_descriptor(self.slot_cabecera, self.base_cabeceras)
            cargador_validador.validar_limites(dir_desc, DESC_TAM_BYTES)

    @classmethod
    def desde_filas(
        cls,
        nombre: str,
        filas_2d: Sequence[Sequence[ValorElemento]],
        direccion_base: int = BASE_MATRICES,
        slot_cabecera: Optional[int] = 1,
        incluir_cabecera_inline: bool = True,
        base_cabeceras: int = BASE_CABECERAS,
    ) -> "DescriptorMatriz":
        """Construye un DescriptorMatriz a partir de una lista anidada de filas [[...], [...]]."""
        num_filas = len(filas_2d)
        if num_filas == 0:
            return cls(
                nombre=nombre,
                filas=0,
                columnas=0,
                elementos_lineales=[],
                direccion_base=direccion_base,
                slot_cabecera=slot_cabecera,
                incluir_cabecera_inline=incluir_cabecera_inline,
                base_cabeceras=base_cabeceras,
            )
        num_cols = len(filas_2d[0])
        planos: List[ValorElemento] = []
        for idx_f, fila in enumerate(filas_2d):
            if len(fila) != num_cols:
                raise ErrorEstructuraDatos(
                    f"Matriz irregular en '{nombre}': fila 0 tiene {num_cols} columnas, "
                    f"pero fila {idx_f} tiene {len(fila)}."
                )
            planos.extend(fila)
        return cls(
            nombre=nombre,
            filas=num_filas,
            columnas=num_cols,
            elementos_lineales=planos,
            direccion_base=direccion_base,
            slot_cabecera=slot_cabecera,
            incluir_cabecera_inline=incluir_cabecera_inline,
            base_cabeceras=base_cabeceras,
        )

    @classmethod
    def vacia(
        cls,
        nombre: str,
        filas: int,
        columnas: int,
        valor_inicial: ValorElemento = 0,
        direccion_base: int = BASE_MATRICES,
        slot_cabecera: Optional[int] = 1,
        incluir_cabecera_inline: bool = True,
        base_cabeceras: int = BASE_CABECERAS,
    ) -> "DescriptorMatriz":
        """Construye una matriz F x C inicializada uniformemente con valor_inicial."""
        if filas < 0 or columnas < 0:
            raise ErrorEstructuraDatos(
                f"Dimensiones invalidas en matriz '{nombre}': ({filas}, {columnas})."
            )
        elem = [valor_inicial] * (filas * columnas)
        return cls(
            nombre=nombre,
            filas=filas,
            columnas=columnas,
            elementos_lineales=elem,
            direccion_base=direccion_base,
            slot_cabecera=slot_cabecera,
            incluir_cabecera_inline=incluir_cabecera_inline,
            base_cabeceras=base_cabeceras,
        )

    @property
    def tipo_estructura(self) -> int:
        return TIPO_MATRIZ

    @property
    def total_elementos(self) -> int:
        return self.filas * self.columnas

    @property
    def tamano_datos_bytes(self) -> int:
        return self.total_elementos * PALABRA_BYTES

    @property
    def dir_descriptor(self) -> Optional[int]:
        if self.slot_cabecera is None:
            return None
        return direccion_descriptor(self.slot_cabecera, self.base_cabeceras)

    def direccion_elemento(self, fila: int, col: int) -> int:
        """Retorna Dir(M[i][j]) = B + ((i * C + j) * 8) en orden Row-Major."""
        if not (0 <= fila < self.filas) or not (0 <= col < self.columnas):
            raise ErrorEstructuraDatos(
                f"Indices ({fila}, {col}) fuera de rango ({self.filas}, {self.columnas}) "
                f"en matriz '{self.nombre}'."
            )
        return self.direccion_base + (((fila * self.columnas) + col) << 3)

    def obtener_palabra(self, fila: int, col: int) -> int:
        if not (0 <= fila < self.filas) or not (0 <= col < self.columnas):
            raise ErrorEstructuraDatos(
                f"Indices ({fila}, {col}) fuera de rango ({self.filas}, {self.columnas})."
            )
        return self.palabras_datos[fila * self.columnas + col]

    def palabras_descriptor(self) -> Tuple[int, int, int, int]:
        """Retorna las 4 palabras de 64 bits del descriptor: (2, base, F, C)."""
        return (TIPO_MATRIZ, self.direccion_base, self.filas, self.columnas)

    def bytes_descriptor_big_endian(self) -> bytes:
        tipo, base, f, c = self.palabras_descriptor()
        return struct.pack(">4Q", tipo, base & MASK64, f & MASK64, c & MASK64)

    def bytes_cabecera_inline_big_endian(self) -> bytes:
        """Empaqueta [filas = F, columnas = C] para [base - 16 .. base)."""
        return struct.pack(">2Q", self.filas & MASK64, self.columnas & MASK64)

    def bytes_datos_big_endian(self) -> bytes:
        if not self.palabras_datos:
            return b""
        return b"".join(struct.pack(">Q", w & MASK64) for w in self.palabras_datos)

    def segmentos_memoria(self) -> List[Tuple[str, int, bytes]]:
        segmentos: List[Tuple[str, int, bytes]] = []
        if self.dir_descriptor is not None:
            segmentos.append(
                (f"{self.nombre}.descriptor", self.dir_descriptor, self.bytes_descriptor_big_endian())
            )
        if self.incluir_cabecera_inline:
            segmentos.append(
                (
                    f"{self.nombre}.cabecera_inline",
                    self.direccion_base - 16,
                    self.bytes_cabecera_inline_big_endian(),
                )
            )
        datos = self.bytes_datos_big_endian()
        if datos:
            segmentos.append((f"{self.nombre}.datos", self.direccion_base, datos))
        return segmentos


class MapaEstructurasRAM:
    """
    Registro validado de listas y matrices para una aplicacion de Enigma-64.
    Detecta colisiones de nombres y solapamientos fisicos entre cabeceras y datos.
    """

    def __init__(self, estructuras: Optional[Iterable[EstructuraDescriptor]] = None) -> None:
        self._estructuras: Dict[str, EstructuraDescriptor] = {}
        if estructuras is not None:
            for est in estructuras:
                self.registrar(est)

    @property
    def estructuras(self) -> Dict[str, EstructuraDescriptor]:
        return dict(self._estructuras)

    def registrar(self, estructura: EstructuraDescriptor) -> None:
        if estructura.nombre in self._estructuras:
            raise ErrorEstructuraDatos(
                f"Ya existe una estructura registrada con el nombre '{estructura.nombre}'."
            )
        nuevos_seg = estructura.segmentos_memoria()
        existentes_seg = self.todos_los_segmentos()

        for et_nuevo, ini_n, bytes_n in nuevos_seg:
            fin_n = ini_n + len(bytes_n)
            for et_ex, ini_e, bytes_e in existentes_seg:
                fin_e = ini_e + len(bytes_e)
                if max(ini_n, ini_e) < min(fin_n, fin_e):
                    raise ErrorEstructuraDatos(
                        f"Solapamiento de memoria entre '{et_nuevo}' "
                        f"[0x{ini_n:08X}, 0x{fin_n:08X}) y '{et_ex}' "
                        f"[0x{ini_e:08X}, 0x{fin_e:08X})."
                    )
        self._estructuras[estructura.nombre] = estructura

    def todos_los_segmentos(self) -> List[Tuple[str, int, bytes]]:
        segs: List[Tuple[str, int, bytes]] = []
        for est in self._estructuras.values():
            segs.extend(est.segmentos_memoria())
        return sorted(segs, key=lambda item: item[1])

    def tabla_simbolos(self) -> Dict[str, int]:
        simbolos: Dict[str, int] = {}
        for nombre, est in self._estructuras.items():
            simbolos[nombre] = est.direccion_base
            if est.dir_descriptor is not None:
                simbolos[f"{nombre}_desc"] = est.dir_descriptor
        return simbolos
