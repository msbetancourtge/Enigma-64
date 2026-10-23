"""
Analisis de Modulos Objeto Reubicables (.obj) - Enigma-64 (Noctua Systems).

Primera mitad del modulo Enlazador-Cargador (region "Monitor + Enlazador-Cargador",
0x00001000 - 0x000FFFFF, Tarea 9). El Cargador ubica en memoria programas ya
resueltos; la especificacion deja al Enlazador la lectura de los modulos objeto
que produce un ensamblado por separado. Este modulo se encarga de esa lectura:

  1. Reconoce la cabecera del archivo y la tabla de encabezados de seccion
     (.text, .data, .bss o secciones propias): tipo, permisos R/W/X,
     alineacion, tamano y posicion del contenido dentro del archivo.
  2. Extrae la tabla de exportaciones (simbolos GLOBAL definidos en el modulo)
     y la tabla de importaciones (simbolos que debe definir otro modulo).
  3. Interpreta las marcas de reubicacion: que bytes de que seccion se parchan
     en memoria, con que formula y contra que simbolo.
  4. Valida cada campo y rechaza con ObjetoInvalido cualquier indice,
     desplazamiento, tamano o nombre incoherente antes de que llegue a la RAM.
  5. Serializa modulos construidos en memoria: es el formato que debe emitir
     el backend del ensamblador SPL.

Disposicion del archivo (Big-Endian, igual que la maquina y el formato .e64):

    +-----------------------------------+ 0
    | Cabecera                   52 B   |
    +-----------------------------------+ off_secciones
    | Encabezados de seccion     20 B c/u
    +-----------------------------------+
    | Contenido de secciones BITS       |  (.bss no ocupa bytes en el archivo)
    +-----------------------------------+ off_simbolos
    | Tabla de simbolos          12 B c/u
    +-----------------------------------+ off_reubicaciones
    | Marcas de reubicacion      16 B c/u
    +-----------------------------------+ off_cadenas
    | Tabla de cadenas (UTF-8 + NUL)    |
    +-----------------------------------+

Tipos de marca (S = direccion final del simbolo, A = sumando de la marca,
P = direccion final del primer byte del campo parchado):

    ABS64  8 B  S + A                   palabra de datos que guarda una direccion
    ABS32  4 B  S + A                   destino de JMP / CALL (bytes 1 a 4)
    REL16  2 B  S + A - (P + 2)         desplazamiento de JZ, JNZ, ... (bytes 1 y 2)
    HI16   2 B  (S + A + 0x8000) >> 16  inmediato del ADDI que precede a SHL 16
    LO16   2 B  (S + A) & 0xFFFF        inmediato de ADDI o desplazamiento de LOAD/STORE

HI16 es la parte alta *ajustada*: la CPU extiende el signo de los inmediatos de
16 bits, asi que un LO16 >= 0x8000 resta 0x10000 y la parte alta lo compensa.
Con eso la secuencia del equipo ADDI Rx,R0,hi / SHL Rx,Rx,16 / ADDI Rx,Rx,lo
construye la direccion exacta.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from ..cargador import MAGIC_OBJETO, ErrorCargador, FormatoInvalido

# ---------------------------------------------------------------------------
# Constantes del formato .obj
# ---------------------------------------------------------------------------

VERSION_OBJETO: int = 1
MAQUINA_ENIGMA64: int = 0xE064

# Cabecera: magia, version, maquina, banderas, seccion_entrada, offset_entrada,
# nombre_modulo y las parejas (cantidad, offset) de cada tabla + tabla de cadenas.
FORMATO_CABECERA_OBJ: str = ">4sHHHHIIIIIIIIII"
TAM_CABECERA_OBJ: int = struct.calcsize(FORMATO_CABECERA_OBJ)  # 52 bytes

# Encabezado de seccion: nombre, tipo, permisos, alineacion, tamano, offset
FORMATO_SECCION: str = ">IHHIII"
TAM_SECCION: int = struct.calcsize(FORMATO_SECCION)  # 20 bytes

# Simbolo: nombre, seccion, ligadura, tipo, valor
FORMATO_SIMBOLO: str = ">IHBBI"
TAM_SIMBOLO: int = struct.calcsize(FORMATO_SIMBOLO)  # 12 bytes

# Marca de reubicacion: seccion, tipo, reservado, offset, simbolo, sumando
FORMATO_REUBICACION: str = ">HBBIIi"
TAM_REUBICACION: int = struct.calcsize(FORMATO_REUBICACION)  # 16 bytes

# Bandera de cabecera: el modulo declara el punto de entrada del programa
FLAG_OBJ_ENTRADA: int = 0x0001
_FLAGS_OBJ_CONOCIDOS: int = FLAG_OBJ_ENTRADA

# Tipos de seccion
SECCION_BITS: int = 1   # contenido presente en el archivo (.text, .data)
SECCION_VACIA: int = 2  # solo reserva memoria inicializada en cero (.bss)

# Permisos: los mismos de la columna "Permisos" del mapa de memoria (Tarea 9)
PERM_LECTURA: int = 0x1
PERM_ESCRITURA: int = 0x2
PERM_EJECUCION: int = 0x4
_PERMISOS_CONOCIDOS: int = PERM_LECTURA | PERM_ESCRITURA | PERM_EJECUCION

# Una seccion no puede pedir una alineacion mayor que una pagina de RAM
ALINEACION_MAXIMA: int = 4096

# Clase de una seccion: decide el orden en que el enlazador las ubica
CLASE_CODIGO: int = 0   # BITS ejecutable
CLASE_DATOS: int = 1    # BITS no ejecutable
CLASE_RESERVA: int = 2  # VACIA

# Indices de seccion reservados en la tabla de simbolos
SECCION_ABSOLUTA: int = 0xFFFE    # constante: su valor no se reubica
SECCION_INDEFINIDA: int = 0xFFFF  # importado: lo define otro modulo

LIGADURA_LOCAL: int = 0
LIGADURA_GLOBAL: int = 1

SIMBOLO_SIN_TIPO: int = 0
SIMBOLO_FUNCION: int = 1
SIMBOLO_DATO: int = 2

REUB_ABS64: int = 1
REUB_ABS32: int = 2
REUB_REL16: int = 3
REUB_HI16: int = 4
REUB_LO16: int = 5

ANCHO_REUBICACION: Dict[int, int] = {
    REUB_ABS64: 8,
    REUB_ABS32: 4,
    REUB_REL16: 2,
    REUB_HI16: 2,
    REUB_LO16: 2,
}

NOMBRE_TIPO_SECCION: Dict[int, str] = {SECCION_BITS: "BITS", SECCION_VACIA: "VACIA"}
NOMBRE_CLASE: Dict[int, str] = {
    CLASE_CODIGO: "CODIGO",
    CLASE_DATOS: "DATOS",
    CLASE_RESERVA: "RESERVA",
}
NOMBRE_LIGADURA: Dict[int, str] = {LIGADURA_LOCAL: "LOCAL", LIGADURA_GLOBAL: "GLOBAL"}
NOMBRE_TIPO_SIMBOLO: Dict[int, str] = {
    SIMBOLO_SIN_TIPO: "SIN_TIPO",
    SIMBOLO_FUNCION: "FUNCION",
    SIMBOLO_DATO: "DATO",
}
NOMBRE_REUBICACION: Dict[int, str] = {
    REUB_ABS64: "ABS64",
    REUB_ABS32: "ABS32",
    REUB_REL16: "REL16",
    REUB_HI16: "HI16",
    REUB_LO16: "LO16",
}

_MAX_U32: int = 0xFFFFFFFF
_MIN_I32: int = -(1 << 31)
_MAX_I32: int = (1 << 31) - 1


# ---------------------------------------------------------------------------
# Jerarquia de Excepciones del Enlazador
# ---------------------------------------------------------------------------


class ErrorEnlazador(ErrorCargador):
    """Excepcion base del Enlazador: analisis de objetos, resolucion y reubicacion."""


class ObjetoInvalido(ErrorEnlazador, FormatoInvalido):
    """El modulo objeto esta mal formado o sus tablas son incoherentes."""


def texto_permisos(permisos: int) -> str:
    """Permisos en la notacion del mapa de memoria: 'R-X', 'RW-', ..."""
    return (
        ("R" if permisos & PERM_LECTURA else "-")
        + ("W" if permisos & PERM_ESCRITURA else "-")
        + ("X" if permisos & PERM_EJECUCION else "-")
    )


# ---------------------------------------------------------------------------
# 1. Modelo de un Modulo Objeto
# ---------------------------------------------------------------------------


@dataclass
class SeccionObjeto:
    """
    Seccion de un modulo: codigo (.text), datos (.data) o reserva en cero (.bss).

    Las secciones BITS llevan su contenido; las VACIA solo declaran cuantos bytes
    ocupan en memoria (tamano_reservado) y no aportan bytes al archivo.
    """

    nombre: str
    contenido: bytes = b""
    permisos: int = PERM_LECTURA
    alineacion: int = 1
    tipo: int = SECCION_BITS
    tamano_reservado: int = 0
    # Solo cuando la seccion proviene de un archivo analizado
    offset_archivo: Optional[int] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        self.contenido = bytes(self.contenido)

    @classmethod
    def texto(cls, codigo: Union[bytes, bytearray], nombre: str = ".text") -> SeccionObjeto:
        """Seccion de codigo ejecutable (R-X, alineacion 1: instrucciones de 1 a 5 bytes)."""
        return cls(nombre, codigo, PERM_LECTURA | PERM_EJECUCION, 1)

    @classmethod
    def datos(
        cls,
        contenido: Union[bytes, bytearray],
        nombre: str = ".data",
        alineacion: int = 8,
    ) -> SeccionObjeto:
        """Seccion de datos inicializados (RW-, alineada a palabra para LOAD/STORE)."""
        return cls(nombre, contenido, PERM_LECTURA | PERM_ESCRITURA, alineacion)

    @classmethod
    def reserva(cls, tamano: int, nombre: str = ".bss", alineacion: int = 8) -> SeccionObjeto:
        """Seccion de datos sin inicializar: el enlazador la llena de ceros."""
        return cls(
            nombre, b"", PERM_LECTURA | PERM_ESCRITURA, alineacion, SECCION_VACIA, tamano
        )

    @property
    def tamano(self) -> int:
        """Bytes que ocupa la seccion en memoria."""
        return len(self.contenido) if self.tipo == SECCION_BITS else self.tamano_reservado

    @property
    def clase(self) -> int:
        if self.tipo == SECCION_VACIA:
            return CLASE_RESERVA
        return CLASE_CODIGO if self.permisos & PERM_EJECUCION else CLASE_DATOS


@dataclass(frozen=True)
class SimboloObjeto:
    """
    Entrada de la tabla de simbolos.

    seccion es el indice de la seccion que lo define, SECCION_INDEFINIDA si lo
    importa (lo define otro modulo) o SECCION_ABSOLUTA si es una constante.
    valor es el offset dentro de su seccion, o el valor de la constante.
    """

    nombre: str
    seccion: int
    valor: int = 0
    ligadura: int = LIGADURA_LOCAL
    tipo: int = SIMBOLO_SIN_TIPO

    @classmethod
    def local(cls, nombre: str, seccion: int, valor: int, tipo: int = SIMBOLO_SIN_TIPO) -> SimboloObjeto:
        return cls(nombre, seccion, valor, LIGADURA_LOCAL, tipo)

    @classmethod
    def exportado(cls, nombre: str, seccion: int, valor: int, tipo: int = SIMBOLO_SIN_TIPO) -> SimboloObjeto:
        return cls(nombre, seccion, valor, LIGADURA_GLOBAL, tipo)

    @classmethod
    def importado(cls, nombre: str, tipo: int = SIMBOLO_SIN_TIPO) -> SimboloObjeto:
        return cls(nombre, SECCION_INDEFINIDA, 0, LIGADURA_GLOBAL, tipo)

    @property
    def es_importacion(self) -> bool:
        return self.seccion == SECCION_INDEFINIDA

    @property
    def es_exportacion(self) -> bool:
        return self.ligadura == LIGADURA_GLOBAL and self.seccion != SECCION_INDEFINIDA

    @property
    def es_absoluto(self) -> bool:
        return self.seccion == SECCION_ABSOLUTA


@dataclass(frozen=True)
class MarcaReubicacion:
    """
    Marca de reubicacion: el campo de `ancho` bytes que empieza en `offset`
    dentro de la seccion `seccion` debe recibir la direccion del simbolo de
    indice `simbolo` (mas `sumando`) segun la formula del `tipo`.
    """

    seccion: int
    offset: int
    tipo: int
    simbolo: int
    sumando: int = 0

    @property
    def ancho(self) -> int:
        return ANCHO_REUBICACION.get(self.tipo, 0)

    @property
    def nombre_tipo(self) -> str:
        return NOMBRE_REUBICACION.get(self.tipo, f"0x{self.tipo:02X}")


@dataclass(frozen=True)
class CabeceraObjeto:
    """Campos de la cabecera tal como se leyeron del archivo."""

    version: int
    maquina: int
    banderas: int
    seccion_entrada: int
    offset_entrada: int
    num_secciones: int
    off_secciones: int
    num_simbolos: int
    off_simbolos: int
    num_reubicaciones: int
    off_reubicaciones: int
    tam_cadenas: int
    off_cadenas: int
    tamano_archivo: int


@dataclass
class ModuloObjeto:
    """
    Modulo objeto reubicable: secciones, simbolos y marcas de reubicacion.

    entrada = (indice de seccion, offset) cuando el modulo declara el punto de
    entrada del programa. cabecera solo existe si el modulo se leyo de un archivo.
    """

    nombre: str
    secciones: List[SeccionObjeto] = field(default_factory=list)
    simbolos: List[SimboloObjeto] = field(default_factory=list)
    reubicaciones: List[MarcaReubicacion] = field(default_factory=list)
    entrada: Optional[Tuple[int, int]] = None
    cabecera: Optional[CabeceraObjeto] = field(default=None, compare=False)

    # -- consultas ----------------------------------------------------------

    def indice_seccion(self, nombre: str) -> int:
        for indice, seccion in enumerate(self.secciones):
            if seccion.nombre == nombre:
                return indice
        raise KeyError(f"El modulo '{self.nombre}' no tiene la seccion '{nombre}'")

    def seccion(self, nombre: str) -> SeccionObjeto:
        return self.secciones[self.indice_seccion(nombre)]

    def indice_simbolo(self, nombre: str) -> int:
        for indice, simbolo in enumerate(self.simbolos):
            if simbolo.nombre == nombre:
                return indice
        raise KeyError(f"El modulo '{self.nombre}' no tiene el simbolo '{nombre}'")

    @property
    def exportaciones(self) -> List[SimboloObjeto]:
        """Tabla de exportaciones: simbolos GLOBAL definidos en este modulo."""
        return [s for s in self.simbolos if s.es_exportacion]

    @property
    def importaciones(self) -> List[SimboloObjeto]:
        """Tabla de importaciones: simbolos que debe definir otro modulo."""
        return [s for s in self.simbolos if s.es_importacion]

    @property
    def locales(self) -> List[SimboloObjeto]:
        """Simbolos visibles solo dentro del modulo (etiquetas internas)."""
        return [s for s in self.simbolos if s.ligadura == LIGADURA_LOCAL]

    def referencias(self, nombre_simbolo: str) -> List[MarcaReubicacion]:
        """Marcas de reubicacion que usan el simbolo indicado."""
        indice = self.indice_simbolo(nombre_simbolo)
        return [m for m in self.reubicaciones if m.simbolo == indice]

    def marcas_de_seccion(self, nombre_seccion: str) -> List[MarcaReubicacion]:
        """Marcas de reubicacion de una seccion, ordenadas por offset."""
        indice = self.indice_seccion(nombre_seccion)
        return sorted(
            (m for m in self.reubicaciones if m.seccion == indice), key=lambda m: m.offset
        )

    # -- validacion ---------------------------------------------------------

    def validar(self) -> None:
        """
        Comprueba la coherencia interna del modulo. La usan el analizador (tras
        leer el archivo) y el serializador (antes de escribirlo), asi ningun
        modulo incoherente entra ni sale del enlazador.

        :raises ObjetoInvalido: Con el primer problema encontrado.
        """
        _exigir_nombre(self.nombre, "nombre del modulo", permitir_vacio=True)
        self._validar_secciones()
        self._validar_simbolos()
        self._validar_reubicaciones()
        self._validar_entrada()

    def _validar_secciones(self) -> None:
        if len(self.secciones) >= SECCION_ABSOLUTA:
            raise ObjetoInvalido(
                f"Demasiadas secciones ({len(self.secciones)}): los indices "
                f"0x{SECCION_ABSOLUTA:04X} y 0x{SECCION_INDEFINIDA:04X} estan reservados"
            )
        vistos = set()
        for indice, sec in enumerate(self.secciones):
            contexto = f"Seccion {indice}"
            _exigir_nombre(sec.nombre, contexto)
            if sec.nombre in vistos:
                raise ObjetoInvalido(f"Seccion duplicada: '{sec.nombre}'")
            vistos.add(sec.nombre)
            contexto = f"Seccion '{sec.nombre}'"
            if sec.tipo not in NOMBRE_TIPO_SECCION:
                raise ObjetoInvalido(f"{contexto}: tipo desconocido ({sec.tipo})")
            if sec.permisos & ~_PERMISOS_CONOCIDOS:
                raise ObjetoInvalido(
                    f"{contexto}: permisos desconocidos (0x{sec.permisos:04X})"
                )
            if (
                sec.alineacion <= 0
                or sec.alineacion & (sec.alineacion - 1)
                or sec.alineacion > ALINEACION_MAXIMA
            ):
                raise ObjetoInvalido(
                    f"{contexto}: la alineacion debe ser una potencia de 2 entre 1 y "
                    f"{ALINEACION_MAXIMA} (se recibio {sec.alineacion})"
                )
            if sec.tipo == SECCION_BITS and sec.tamano_reservado:
                raise ObjetoInvalido(
                    f"{contexto}: tamano_reservado solo aplica a secciones VACIA"
                )
            if sec.tipo == SECCION_VACIA and sec.contenido:
                raise ObjetoInvalido(f"{contexto}: una seccion VACIA no lleva contenido")
            if not 0 <= sec.tamano <= _MAX_U32:
                raise ObjetoInvalido(
                    f"{contexto}: tamano fuera del rango de 32 bits ({sec.tamano})"
                )

    def _validar_simbolos(self) -> None:
        vistos = set()
        for indice, sim in enumerate(self.simbolos):
            _exigir_nombre(sim.nombre, f"Simbolo {indice}")
            if sim.nombre in vistos:
                raise ObjetoInvalido(f"Simbolo duplicado en el modulo: '{sim.nombre}'")
            vistos.add(sim.nombre)
            contexto = f"Simbolo '{sim.nombre}'"
            if sim.ligadura not in NOMBRE_LIGADURA:
                raise ObjetoInvalido(f"{contexto}: ligadura desconocida ({sim.ligadura})")
            if sim.tipo not in NOMBRE_TIPO_SIMBOLO:
                raise ObjetoInvalido(f"{contexto}: tipo desconocido ({sim.tipo})")
            if not 0 <= sim.valor <= _MAX_U32:
                raise ObjetoInvalido(f"{contexto}: valor fuera del rango de 32 bits")
            if sim.seccion == SECCION_INDEFINIDA:
                if sim.ligadura != LIGADURA_GLOBAL:
                    raise ObjetoInvalido(
                        f"{contexto}: un simbolo importado (indefinido) debe ser GLOBAL"
                    )
            elif sim.seccion == SECCION_ABSOLUTA:
                continue
            elif not 0 <= sim.seccion < len(self.secciones):
                raise ObjetoInvalido(
                    f"{contexto}: apunta a la seccion {sim.seccion}, que no existe"
                )
            elif sim.valor > self.secciones[sim.seccion].tamano:
                seccion = self.secciones[sim.seccion]
                raise ObjetoInvalido(
                    f"{contexto}: offset 0x{sim.valor:X} fuera de '{seccion.nombre}' "
                    f"({seccion.tamano} bytes)"
                )

    def _validar_reubicaciones(self) -> None:
        for indice, marca in enumerate(self.reubicaciones):
            contexto = f"Marca de reubicacion {indice}"
            if not 0 <= marca.seccion < len(self.secciones):
                raise ObjetoInvalido(
                    f"{contexto}: apunta a la seccion {marca.seccion}, que no existe"
                )
            seccion = self.secciones[marca.seccion]
            if seccion.tipo != SECCION_BITS:
                raise ObjetoInvalido(
                    f"{contexto}: la seccion VACIA '{seccion.nombre}' no tiene bytes que parchar"
                )
            if marca.tipo not in ANCHO_REUBICACION:
                raise ObjetoInvalido(f"{contexto}: tipo de reubicacion desconocido ({marca.tipo})")
            if marca.offset < 0 or marca.offset + marca.ancho > seccion.tamano:
                raise ObjetoInvalido(
                    f"{contexto}: el campo {marca.nombre_tipo} de {marca.ancho} bytes en "
                    f"0x{marca.offset:X} excede '{seccion.nombre}' ({seccion.tamano} bytes)"
                )
            if not 0 <= marca.simbolo < len(self.simbolos):
                raise ObjetoInvalido(
                    f"{contexto}: apunta al simbolo {marca.simbolo}, que no existe"
                )
            if not _MIN_I32 <= marca.sumando <= _MAX_I32:
                raise ObjetoInvalido(f"{contexto}: sumando fuera del rango de 32 bits")

        # Dos marcas que parchan los mismos bytes delatan un objeto corrupto
        ordenadas = sorted(self.reubicaciones, key=lambda m: (m.seccion, m.offset))
        for previa, actual in zip(ordenadas, ordenadas[1:]):
            if previa.seccion == actual.seccion and previa.offset + previa.ancho > actual.offset:
                nombre = self.secciones[actual.seccion].nombre
                raise ObjetoInvalido(
                    f"Marcas de reubicacion solapadas en '{nombre}': "
                    f"{previa.nombre_tipo} en 0x{previa.offset:X} y "
                    f"{actual.nombre_tipo} en 0x{actual.offset:X}"
                )

    def _validar_entrada(self) -> None:
        if self.entrada is None:
            return
        indice, offset = self.entrada
        if not 0 <= indice < len(self.secciones):
            raise ObjetoInvalido(
                f"Punto de entrada en la seccion {indice}, que no existe"
            )
        seccion = self.secciones[indice]
        if not seccion.permisos & PERM_EJECUCION:
            raise ObjetoInvalido(
                f"Punto de entrada en la seccion no ejecutable '{seccion.nombre}'"
            )
        if not 0 <= offset < seccion.tamano:
            raise ObjetoInvalido(
                f"Punto de entrada 0x{offset:X} fuera de '{seccion.nombre}' "
                f"({seccion.tamano} bytes)"
            )

    # -- serializacion ------------------------------------------------------

    def serializar(self) -> bytes:
        """Escribe el modulo en formato .obj (valida antes de escribir)."""
        self.validar()

        cadenas = _TablaCadenas()
        nombre_modulo = cadenas.agregar(self.nombre)

        off_secciones = TAM_CABECERA_OBJ
        off_contenido = off_secciones + len(self.secciones) * TAM_SECCION
        encabezados = bytearray()
        contenidos = bytearray()
        for sec in self.secciones:
            if sec.tipo == SECCION_BITS:
                offset = off_contenido + len(contenidos)
                contenidos.extend(sec.contenido)
            else:
                offset = 0
            encabezados.extend(
                struct.pack(
                    FORMATO_SECCION,
                    cadenas.agregar(sec.nombre),
                    sec.tipo,
                    sec.permisos,
                    sec.alineacion,
                    sec.tamano,
                    offset,
                )
            )

        off_simbolos = off_contenido + len(contenidos)
        tabla_simbolos = b"".join(
            struct.pack(
                FORMATO_SIMBOLO,
                cadenas.agregar(sim.nombre),
                sim.seccion,
                sim.ligadura,
                sim.tipo,
                sim.valor,
            )
            for sim in self.simbolos
        )

        off_reubicaciones = off_simbolos + len(tabla_simbolos)
        tabla_reubicaciones = b"".join(
            struct.pack(
                FORMATO_REUBICACION,
                marca.seccion,
                marca.tipo,
                0,
                marca.offset,
                marca.simbolo,
                marca.sumando,
            )
            for marca in self.reubicaciones
        )

        off_cadenas = off_reubicaciones + len(tabla_reubicaciones)
        if self.entrada is not None:
            banderas = FLAG_OBJ_ENTRADA
            seccion_entrada, offset_entrada = self.entrada
        else:
            banderas, seccion_entrada, offset_entrada = 0, SECCION_INDEFINIDA, 0

        cabecera = struct.pack(
            FORMATO_CABECERA_OBJ,
            MAGIC_OBJETO,
            VERSION_OBJETO,
            MAQUINA_ENIGMA64,
            banderas,
            seccion_entrada,
            offset_entrada,
            nombre_modulo,
            len(self.secciones),
            off_secciones,
            len(self.simbolos),
            off_simbolos,
            len(self.reubicaciones),
            off_reubicaciones,
            len(cadenas.datos),
            off_cadenas,
        )
        return (
            cabecera
            + bytes(encabezados)
            + bytes(contenidos)
            + tabla_simbolos
            + tabla_reubicaciones
            + bytes(cadenas.datos)
        )

    def guardar(self, ruta: Union[str, os.PathLike]) -> None:
        """Escribe el modulo en disco como archivo .obj."""
        with open(ruta, "wb") as f:
            f.write(self.serializar())

    @classmethod
    def deserializar(cls, contenido: Union[bytes, bytearray]) -> ModuloObjeto:
        """
        Analiza un archivo .obj completo: cabecera, encabezados de seccion,
        tabla de simbolos, marcas de reubicacion y tabla de cadenas.

        :raises ObjetoInvalido: Si algun campo esta fuera de rango o es incoherente.
        """
        datos = bytes(contenido)
        total = len(datos)
        if total < TAM_CABECERA_OBJ:
            raise ObjetoInvalido(
                f"El archivo tiene {total} bytes y la cabecera .obj ocupa {TAM_CABECERA_OBJ}"
            )

        (
            magia,
            version,
            maquina,
            banderas,
            seccion_entrada,
            offset_entrada,
            nombre_modulo,
            num_secciones,
            off_secciones,
            num_simbolos,
            off_simbolos,
            num_reubicaciones,
            off_reubicaciones,
            tam_cadenas,
            off_cadenas,
        ) = struct.unpack_from(FORMATO_CABECERA_OBJ, datos, 0)

        if magia != MAGIC_OBJETO:
            raise ObjetoInvalido(
                f"Firma magica invalida: esperada {MAGIC_OBJETO!r}, obtenida {magia!r}"
            )
        if version != VERSION_OBJETO:
            raise ObjetoInvalido(
                f"Version de formato no soportada: {version} (se admite {VERSION_OBJETO})"
            )
        if maquina != MAQUINA_ENIGMA64:
            raise ObjetoInvalido(
                f"El objeto es para la maquina 0x{maquina:04X}, no para Enigma-64 "
                f"(0x{MAQUINA_ENIGMA64:04X})"
            )
        if banderas & ~_FLAGS_OBJ_CONOCIDOS:
            raise ObjetoInvalido(f"Banderas de cabecera desconocidas: 0x{banderas:04X}")

        _exigir_region("la tabla de encabezados de seccion", off_secciones,
                       num_secciones * TAM_SECCION, total)
        _exigir_region("la tabla de simbolos", off_simbolos, num_simbolos * TAM_SIMBOLO, total)
        _exigir_region("la tabla de reubicacion", off_reubicaciones,
                       num_reubicaciones * TAM_REUBICACION, total)
        _exigir_region("la tabla de cadenas", off_cadenas, tam_cadenas, total)
        cadenas = datos[off_cadenas : off_cadenas + tam_cadenas]

        secciones: List[SeccionObjeto] = []
        for indice in range(num_secciones):
            nombre, tipo, permisos, alineacion, tamano, offset = struct.unpack_from(
                FORMATO_SECCION, datos, off_secciones + indice * TAM_SECCION
            )
            nombre_seccion = _leer_cadena(cadenas, nombre, f"Seccion {indice}")
            if tipo == SECCION_BITS:
                _exigir_region(f"el contenido de la seccion '{nombre_seccion}'", offset,
                               tamano, total)
                secciones.append(SeccionObjeto(
                    nombre_seccion, datos[offset : offset + tamano], permisos,
                    alineacion, tipo, 0, offset,
                ))
            elif tipo == SECCION_VACIA:
                if offset != 0:
                    raise ObjetoInvalido(
                        f"La seccion VACIA '{nombre_seccion}' no puede tener contenido "
                        f"en el archivo (offset 0x{offset:X})"
                    )
                secciones.append(SeccionObjeto(
                    nombre_seccion, b"", permisos, alineacion, tipo, tamano, None,
                ))
            else:
                raise ObjetoInvalido(f"Seccion '{nombre_seccion}': tipo desconocido ({tipo})")

        simbolos: List[SimboloObjeto] = []
        for indice in range(num_simbolos):
            nombre, seccion, ligadura, tipo, valor = struct.unpack_from(
                FORMATO_SIMBOLO, datos, off_simbolos + indice * TAM_SIMBOLO
            )
            simbolos.append(SimboloObjeto(
                _leer_cadena(cadenas, nombre, f"Simbolo {indice}"),
                seccion, valor, ligadura, tipo,
            ))

        reubicaciones: List[MarcaReubicacion] = []
        for indice in range(num_reubicaciones):
            seccion, tipo, reservado, offset, simbolo, sumando = struct.unpack_from(
                FORMATO_REUBICACION, datos, off_reubicaciones + indice * TAM_REUBICACION
            )
            if reservado != 0:
                raise ObjetoInvalido(
                    f"Marca de reubicacion {indice}: el byte reservado debe valer 0 "
                    f"(vale {reservado})"
                )
            reubicaciones.append(MarcaReubicacion(seccion, offset, tipo, simbolo, sumando))

        modulo = cls(
            nombre=_leer_cadena(cadenas, nombre_modulo, "Nombre del modulo"),
            secciones=secciones,
            simbolos=simbolos,
            reubicaciones=reubicaciones,
            entrada=(
                (seccion_entrada, offset_entrada) if banderas & FLAG_OBJ_ENTRADA else None
            ),
            cabecera=CabeceraObjeto(
                version, maquina, banderas, seccion_entrada, offset_entrada,
                num_secciones, off_secciones, num_simbolos, off_simbolos,
                num_reubicaciones, off_reubicaciones, tam_cadenas, off_cadenas, total,
            ),
        )
        modulo.validar()
        return modulo

    @classmethod
    def desde_archivo(cls, ruta: Union[str, os.PathLike]) -> ModuloObjeto:
        """Analiza un .obj del disco; si no trae nombre se usa el del archivo."""
        with open(ruta, "rb") as f:
            modulo = cls.deserializar(f.read())
        if not modulo.nombre:
            modulo.nombre = os.path.splitext(os.path.basename(os.fspath(ruta)))[0]
        return modulo

    # -- informe ------------------------------------------------------------

    def nombre_seccion_de(self, simbolo: SimboloObjeto) -> str:
        if simbolo.es_importacion:
            return "*IND*"
        if simbolo.es_absoluto:
            return "*ABS*"
        return self.secciones[simbolo.seccion].nombre

    def informe(self) -> str:
        """Volcado legible del analisis (al estilo de objdump -h -t -r)."""
        lineas = [f"Modulo objeto '{self.nombre}'"]
        if self.cabecera is not None:
            c = self.cabecera
            lineas.append(
                f"  Formato EOBJ v{c.version}, maquina 0x{c.maquina:04X} (Enigma-64), "
                f"{c.tamano_archivo} bytes"
            )
        lineas.append(
            f"  Secciones: {len(self.secciones)}  Simbolos: {len(self.simbolos)}  "
            f"Marcas de reubicacion: {len(self.reubicaciones)}"
        )
        if self.entrada is None:
            lineas.append("  Punto de entrada: no declarado")
        else:
            indice, offset = self.entrada
            lineas.append(
                f"  Punto de entrada: {self.secciones[indice].nombre}+0x{offset:04X}"
            )

        lineas += ["", "Encabezados de seccion"]
        lineas += _formatear_tabla(
            ("Idx", "Nombre", "Tipo", "Clase", "Perm", "Alin", "Tamano", "Offset"),
            [
                (
                    str(i), s.nombre, NOMBRE_TIPO_SECCION[s.tipo], NOMBRE_CLASE[s.clase],
                    texto_permisos(s.permisos), str(s.alineacion), str(s.tamano),
                    "-" if s.offset_archivo is None else f"0x{s.offset_archivo:04X}",
                )
                for i, s in enumerate(self.secciones)
            ],
        )

        lineas += ["", f"Tabla de exportaciones ({len(self.exportaciones)})"]
        lineas += _formatear_tabla(
            ("Simbolo", "Seccion", "Valor", "Tipo"),
            [
                (s.nombre, self.nombre_seccion_de(s), f"0x{s.valor:08X}",
                 NOMBRE_TIPO_SIMBOLO[s.tipo])
                for s in self.exportaciones
            ],
        )

        lineas += ["", f"Tabla de importaciones ({len(self.importaciones)})"]
        lineas += _formatear_tabla(
            ("Simbolo", "Tipo", "Referencias"),
            [
                (
                    s.nombre, NOMBRE_TIPO_SIMBOLO[s.tipo],
                    ", ".join(
                        f"{self.secciones[m.seccion].nombre}+0x{m.offset:04X} {m.nombre_tipo}"
                        for m in self.referencias(s.nombre)
                    ) or "(sin referencias)",
                )
                for s in self.importaciones
            ],
        )

        lineas += ["", f"Simbolos locales ({len(self.locales)})"]
        lineas += _formatear_tabla(
            ("Simbolo", "Seccion", "Valor", "Tipo"),
            [
                (s.nombre, self.nombre_seccion_de(s), f"0x{s.valor:08X}",
                 NOMBRE_TIPO_SIMBOLO[s.tipo])
                for s in self.locales
            ],
        )

        lineas += ["", f"Marcas de reubicacion ({len(self.reubicaciones)})"]
        lineas += _formatear_tabla(
            ("Seccion", "Offset", "Tipo", "Ancho", "Simbolo", "Origen", "Sumando"),
            [
                (
                    self.secciones[m.seccion].nombre, f"0x{m.offset:04X}", m.nombre_tipo,
                    str(m.ancho), self.simbolos[m.simbolo].nombre,
                    _origen(self.simbolos[m.simbolo]), f"{m.sumando:+d}",
                )
                for m in sorted(self.reubicaciones, key=lambda m: (m.seccion, m.offset))
            ],
        )
        return "\n".join(lineas)


FuenteObjeto = Union[ModuloObjeto, bytes, bytearray, str, os.PathLike]


def analizar_objeto(fuente: FuenteObjeto) -> ModuloObjeto:
    """
    Punto de entrada del analisis: acepta un ModuloObjeto ya construido, los
    bytes de un .obj o la ruta del archivo, y devuelve el modulo validado.
    """
    if isinstance(fuente, ModuloObjeto):
        fuente.validar()
        return fuente
    if isinstance(fuente, (bytes, bytearray)):
        return ModuloObjeto.deserializar(fuente)
    return ModuloObjeto.desde_archivo(fuente)


# ---------------------------------------------------------------------------
# 2. Utilidades internas del analizador
# ---------------------------------------------------------------------------


class _TablaCadenas:
    """Tabla de cadenas UTF-8 terminadas en NUL; el offset 0 es la cadena vacia."""

    def __init__(self) -> None:
        self.datos = bytearray(b"\x00")
        self._offsets: Dict[str, int] = {"": 0}

    def agregar(self, texto: str) -> int:
        if texto not in self._offsets:
            self._offsets[texto] = len(self.datos)
            self.datos.extend(texto.encode("utf-8") + b"\x00")
        return self._offsets[texto]


def _exigir_nombre(nombre: str, contexto: str, permitir_vacio: bool = False) -> None:
    if not nombre and not permitir_vacio:
        raise ObjetoInvalido(f"{contexto}: el nombre esta vacio")
    if "\x00" in nombre:
        raise ObjetoInvalido(f"{contexto}: el nombre {nombre!r} contiene un byte NUL")


def _exigir_region(descripcion: str, offset: int, tamano: int, total: int) -> None:
    """descripcion lleva su articulo ('la tabla ...', 'el contenido ...')."""
    if offset + tamano > total:
        raise ObjetoInvalido(
            f"{descripcion[:1].upper()}{descripcion[1:]} (offset 0x{offset:X}, {tamano} bytes) "
            f"excede el archivo de {total} bytes"
        )


def _leer_cadena(cadenas: bytes, offset: int, contexto: str) -> str:
    if offset >= len(cadenas):
        raise ObjetoInvalido(
            f"{contexto}: el nombre apunta fuera de la tabla de cadenas "
            f"(offset {offset}, tamano {len(cadenas)})"
        )
    fin = cadenas.find(b"\x00", offset)
    if fin < 0:
        raise ObjetoInvalido(f"{contexto}: nombre sin terminador NUL en la tabla de cadenas")
    try:
        return cadenas[offset:fin].decode("utf-8")
    except UnicodeDecodeError:
        raise ObjetoInvalido(f"{contexto}: el nombre no es UTF-8 valido") from None


def _origen(simbolo: SimboloObjeto) -> str:
    if simbolo.es_importacion:
        return "IMPORTADO"
    return NOMBRE_LIGADURA[simbolo.ligadura]


def _formatear_tabla(encabezados: Sequence[str], filas: Sequence[Sequence[str]]) -> List[str]:
    """Tabla de texto con columnas alineadas a la izquierda."""
    if not filas:
        return ["  (vacia)"]
    anchos = [max(len(celda) for celda in columna) for columna in zip(encabezados, *filas)]

    def linea(celdas: Sequence[str]) -> str:
        return ("  " + "  ".join(c.ljust(a) for c, a in zip(celdas, anchos))).rstrip()

    return [linea(encabezados)] + [linea(fila) for fila in filas]
