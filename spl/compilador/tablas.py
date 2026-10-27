"""
Tablas de Símbolos y Tablas de Literales para el Compilador SPL (Enigma-64).
Responsabilidad: Integrante 6 (Tabla de Símbolos & Tablas de Literales).

Implementa:
- Tabla de Identificadores (tablaID): InstallID() con deduplicación y mapeo base 1.
- Tabla de Constantes Numéricas (tablaNum): InstallNum() con soporte para enteros
  de 64 bits y flotantes IEEE 754 de 64 bits (binary64).
- Tabla de Cadenas Literales (tablaString): InstallString() con algoritmo de
  des-escape y deduplicación sobre texto limpio.
- Consultas (lookup) y volcado tabular estructurado.
"""

from __future__ import annotations
import re
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any


class TipoNumero(Enum):
    """Tipos numéricos soportados por el computador Enigma-64."""
    ENTERO_DECIMAL = "ENTERO_DECIMAL"
    ENTERO_HEX = "ENTERO_HEX"
    ENTERO_BIN = "ENTERO_BIN"
    REAL_DECIMAL = "REAL_DECIMAL"
    REAL_CIENTIFICO = "REAL_CIENTIFICO"


@dataclass
class EntradaID:
    """Entrada en la tabla de identificadores."""
    indice: int
    lexema: str


@dataclass
class EntradaNum:
    """
    Entrada en la tabla de constantes numéricas.
    Preserva el formato de origen, el valor entero de 64 bits y el valor float IEEE 754 de 64 bits.
    """
    indice: int
    lexema: str
    tipo: TipoNumero
    valor_int: int
    valor_uint: int
    valor_float: float
    patron_ieee754_hex: str


@dataclass
class EntradaString:
    """Entrada en la tabla de cadenas literales."""
    indice: int
    texto: str
    longitud: int


def desescapar_cadena(origen: str) -> str:
    """
    Algoritmo determinista de des-comillado y resolución de secuencias de escape.
    Equivalente a la especificación en C del Literal d de la Tarea 26.
    """
    if not origen or len(origen) < 2 or origen[0] != '"' or origen[-1] != '"':
        return ""

    contenido = origen[1:-1]
    res: List[str] = []
    i = 0
    n = len(contenido)

    while i < n:
        char = contenido[i]
        if char == '\\' and i + 1 < n:
            i += 1
            sig = contenido[i]
            if sig == '"':
                res.append('"')
            elif sig == '\\':
                res.append('\\')
            elif sig == 'n':
                res.append('\n')
            elif sig == 't':
                res.append('\t')
            elif sig == 'r':
                res.append('\r')
            elif sig == '0':
                res.append('\0')
            else:
                res.append(sig)
        else:
            res.append(char)
        i += 1

    return "".join(res)


class TablaID:
    """
    Gestor de la Tabla de Identificadores (tablaID - Categoría 150).
    """

    def __init__(self, capacidad_maxima: int = 1024):
        self.capacidad_maxima = capacidad_maxima
        self._entradas: List[EntradaID] = []
        self._indice_por_lexema: Dict[str, int] = {}

    def install(self, lexema: str) -> int:
        """
        Búsqueda e inserción sin duplicados (InstallID).
        Retorna el índice 1-based asignado a yylval.
        """
        if not lexema:
            raise ValueError("El lexema del identificador no puede estar vacio")

        if lexema in self._indice_por_lexema:
            return self._indice_por_lexema[lexema]

        if len(self._entradas) >= self.capacidad_maxima:
            raise OverflowError(f"Tabla de Identificadores llena (Capacidad: {self.capacidad_maxima})")

        nuevo_indice = len(self._entradas) + 1
        entrada = EntradaID(indice=nuevo_indice, lexema=lexema)
        self._entradas.append(entrada)
        self._indice_por_lexema[lexema] = nuevo_indice
        return nuevo_indice

    def buscar(self, lexema: str) -> Optional[int]:
        """Consulta el índice de un identificador sin insertar."""
        return self._indice_por_lexema.get(lexema)

    def obtener(self, indice: int) -> Optional[EntradaID]:
        """Obtiene la entrada dada su posición 1-based."""
        if 1 <= indice <= len(self._entradas):
            return self._entradas[indice - 1]
        return None

    @property
    def total(self) -> int:
        return len(self._entradas)

    @property
    def entradas(self) -> List[EntradaID]:
        return list(self._entradas)

    def limpiar(self) -> None:
        self._entradas.clear()
        self._indice_por_lexema.clear()


class TablaNum:
    """
    Gestor de la Tabla de Constantes Numéricas (tablaNum - Categoría 160).
    Soporta enteros de 64 bits y punto flotante IEEE 754 de 64 bits (binary64).
    """

    def __init__(self, capacidad_maxima: int = 1024):
        self.capacidad_maxima = capacidad_maxima
        self._entradas: List[EntradaNum] = []
        self._indice_por_lexema: Dict[str, int] = {}

    def _convertir(self, lexema: str) -> tuple[TipoNumero, int, int, float, str]:
        lex = lexema.strip()

        # Hexadecimal 0x... / 0X...
        if lex.startswith(("0x", "0X")):
            tipo = TipoNumero.ENTERO_HEX
            val_u = int(lex, 16) & 0xFFFFFFFFFFFFFFFF
            val_i = struct.unpack('q', struct.pack('Q', val_u))[0]
            val_f = float(val_u)

        # Binario 0b... / 0B...
        elif lex.startswith(("0b", "0B")):
            tipo = TipoNumero.ENTERO_BIN
            val_u = int(lex, 2) & 0xFFFFFFFFFFFFFFFF
            val_i = struct.unpack('q', struct.pack('Q', val_u))[0]
            val_f = float(val_u)

        # Coma flotante / Notación científica
        elif '.' in lex or 'e' in lex.lower():
            if 'e' in lex.lower():
                tipo = TipoNumero.REAL_CIENTIFICO
            else:
                tipo = TipoNumero.REAL_DECIMAL
            val_f = float(lex)
            val_i = int(val_f)
            val_u = val_i & 0xFFFFFFFFFFFFFFFF

        # Entero decimal estándar
        else:
            tipo = TipoNumero.ENTERO_DECIMAL
            val_i = int(lex)
            val_u = struct.unpack('Q', struct.pack('q', val_i))[0] if -2**63 <= val_i < 2**63 else (val_i & 0xFFFFFFFFFFFFFFFF)
            val_f = float(val_i)

        # Patrón exacto IEEE 754 binary64 de 64 bits
        packed_ieee = struct.pack('>d', val_f)
        hex_ieee = packed_ieee.hex().upper()

        return tipo, val_i, val_u, val_f, hex_ieee

    def install(self, lexema: str) -> int:
        """
        Búsqueda e inserción de constantes numéricas (InstallNum).
        Retorna el índice 1-based asignado a yylval.
        """
        lex = lexema.strip()
        if not lex:
            raise ValueError("El lexema numérico no puede estar vacio")

        if lex in self._indice_por_lexema:
            return self._indice_por_lexema[lex]

        if len(self._entradas) >= self.capacidad_maxima:
            raise OverflowError(f"Tabla de Constantes Numéricas llena (Capacidad: {self.capacidad_maxima})")

        tipo, val_i, val_u, val_f, hex_ieee = self._convertir(lex)

        nuevo_indice = len(self._entradas) + 1
        entrada = EntradaNum(
            indice=nuevo_indice,
            lexema=lex,
            tipo=tipo,
            valor_int=val_i,
            valor_uint=val_u,
            valor_float=val_f,
            patron_ieee754_hex=hex_ieee,
        )
        self._entradas.append(entrada)
        self._indice_por_lexema[lex] = nuevo_indice
        return nuevo_indice

    def buscar(self, lexema: str) -> Optional[int]:
        return self._indice_por_lexema.get(lexema.strip())

    def obtener(self, indice: int) -> Optional[EntradaNum]:
        if 1 <= indice <= len(self._entradas):
            return self._entradas[indice - 1]
        return None

    @property
    def total(self) -> int:
        return len(self._entradas)

    @property
    def entradas(self) -> List[EntradaNum]:
        return list(self._entradas)

    def limpiar(self) -> None:
        self._entradas.clear()
        self._indice_por_lexema.clear()


class TablaString:
    """
    Gestor de la Tabla de Cadenas Literales (tablaString - Categoría 170).
    Deduplica sobre el contenido limpio des-escapado.
    """

    def __init__(self, capacidad_maxima: int = 1024):
        self.capacidad_maxima = capacidad_maxima
        self._entradas: List[EntradaString] = []
        self._indice_por_texto: Dict[str, int] = {}

    def install(self, lexema: str) -> int:
        """
        Procesamiento y registro de cadenas literales (InstallString).
        Deduplica sobre el texto limpio y normalizado.
        """
        texto_limpio = desescapar_cadena(lexema)

        if texto_limpio in self._indice_por_texto:
            return self._indice_por_texto[texto_limpio]

        if len(self._entradas) >= self.capacidad_maxima:
            raise OverflowError(f"Tabla de Cadenas Literales llena (Capacidad: {self.capacidad_maxima})")

        nuevo_indice = len(self._entradas) + 1
        entrada = EntradaString(
            indice=nuevo_indice,
            texto=texto_limpio,
            longitud=len(texto_limpio),
        )
        self._entradas.append(entrada)
        self._indice_por_texto[texto_limpio] = nuevo_indice
        return nuevo_indice

    def buscar(self, texto_limpio: str) -> Optional[int]:
        return self._indice_por_texto.get(texto_limpio)

    def obtener(self, indice: int) -> Optional[EntradaString]:
        if 1 <= indice <= len(self._entradas):
            return self._entradas[indice - 1]
        return None

    @property
    def total(self) -> int:
        return len(self._entradas)

    @property
    def entradas(self) -> List[EntradaString]:
        return list(self._entradas)

    def limpiar(self) -> None:
        self._entradas.clear()
        self._indice_por_texto.clear()


class GestorTablasSimbolos:
    """
    Orquestador unificado de las tablas de símbolos del Compilador SPL.
    Expone la API canónica requerida por la arquitectura de Enigma-64.
    """

    def __init__(self, capacidad_maxima: int = 1024):
        self.tabla_id = TablaID(capacidad_maxima)
        self.tabla_num = TablaNum(capacidad_maxima)
        self.tabla_string = TablaString(capacidad_maxima)

    def install_id(self, lexema: str) -> int:
        """InstallID() canónico."""
        return self.tabla_id.install(lexema)

    def install_num(self, lexema: str) -> int:
        """InstallNum() canónico."""
        return self.tabla_num.install(lexema)

    def install_string(self, lexema: str) -> int:
        """InstallString() canónico."""
        return self.tabla_string.install(lexema)

    def limpiar(self) -> None:
        self.tabla_id.limpiar()
        self.tabla_num.limpiar()
        self.tabla_string.limpiar()

    def generar_volcado_texto(self) -> str:
        """Genera el reporte tabular alineado para consola o reportes."""
        lineas = []
        lineas.append("========================================================================================")
        lineas.append("                 ESTADO FINAL DE LAS TABLAS DE SIMBOLOS (ENIGMA-64)                     ")
        lineas.append("========================================================================================")

        # 1. Tabla ID
        lineas.append("\n* Tabla de Identificadores (tablaID, Categoria 150):")
        lineas.append("+--------+------------------------------------------------+")
        lineas.append("| Indice | Lexema                                         |")
        lineas.append("+--------+------------------------------------------------+")
        if self.tabla_id.total == 0:
            lineas.append("| (vacia)                                                 |")
        else:
            for e in self.tabla_id.entradas:
                lineas.append(f"| {e.indice:<6} | {e.lexema:<46} |")
        lineas.append("+--------+------------------------------------------------+")
        lineas.append(f"Total de identificadores registrados: {self.tabla_id.total}")

        # 2. Tabla Num
        lineas.append("\n* Tabla de Constantes Numericas (tablaNum, Categoria 160):")
        lineas.append("+--------+----------------+---------------------+---------------------+----------------------+")
        lineas.append("| Indice | Lexema Literal | Formato Enigma-64   | Valor Entero 64-bit | Real IEEE 754 (64b)  |")
        lineas.append("+--------+----------------+---------------------+---------------------+----------------------+")
        if self.tabla_num.total == 0:
            lineas.append("| (vacia)                                                                                    |")
        else:
            for en in self.tabla_num.entradas:
                lineas.append(f"| {en.indice:<6} | {en.lexema:<14} | {en.tipo.value:<19} | {en.valor_int:<19} | {en.valor_float:<20.10g} |")
        lineas.append("+--------+----------------+---------------------+---------------------+----------------------+")
        lineas.append(f"Total de constantes numericas registradas: {self.tabla_num.total}")

        # 3. Tabla String
        lineas.append("\n* Tabla de Cadenas de Texto (tablaString, Categoria 170):")
        lineas.append("+--------+------------------------------------------------+----------+")
        lineas.append("| Indice | Texto limpio (des-escapado)                    | Longitud |")
        lineas.append("+--------+------------------------------------------------+----------+")
        if self.tabla_string.total == 0:
            lineas.append("| (vacia)                                                            |")
        else:
            for es in self.tabla_string.entradas:
                texto_vis = es.texto.replace("\n", "\\n").replace("\t", "\\t")
                lineas.append(f"| {es.indice:<6} | {texto_vis:<46} | {es.longitud:<8} |")
        lineas.append("+--------+------------------------------------------------+----------+")
        lineas.append(f"Total de cadenas de texto registradas: {self.tabla_string.total}")
        lineas.append("========================================================================================\n")

        return "\n".join(lineas)
