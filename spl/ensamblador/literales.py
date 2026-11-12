"""
Conversion robusta de literales numericos del SPL de Enigma-64.

Corrige el ValueError con numeros de muchas cifras. Las causas eran dos:
  * int() sobre el texto de un entero decimal: desde Python 3.11, int() se
    niega a convertir cadenas de mas de 4300 digitos (proteccion contra DoS)
    y lanza ValueError. Un entero de 64 bits tiene a lo sumo 20 digitos, asi
    que se mide la longitud ANTES de convertir.
  * Una expresion regular de flotantes sin exponente: 1e-07 (lo que produce
    str() de un float pequeno) no se reconocia como flotante.

Un literal decimal se convierte con float(texto). CPython redondea
correctamente (al par mas cercano) cualquier cantidad de cifras, sin pasar
por int() y sin limite de digitos. No se usa Decimal: mezclarlo con float
introduce un doble redondeo innecesario.

Autor: Integrante 2 Tomas Garzon - Registros, ALU y Primitivas 1D
"""

from __future__ import annotations

import math
import re
import struct

# [+-] parte entera y/o fraccionaria, exponente opcional: 3.14, -2.5, .5, 5., 1e-07, 6.02E+23
LITERAL_DECIMAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")
LITERAL_ENTERO = re.compile(r"[+-]?\d+")

MIN_64 = -(1 << 63)        # menor entero con signo de 64 bits
MAX_64 = (1 << 64) - 1     # mayor entero sin signo de 64 bits
_MAX_DIGITOS_64 = len(str(MAX_64))  # 20


class LiteralInvalido(ValueError):
    """El texto no es un literal valido o no cabe en 64 bits."""


def literal_a_double(texto: str) -> float:
    """Valor double IEEE-754 (redondeo al par mas cercano) de un literal decimal."""
    t = texto.strip()
    if not LITERAL_DECIMAL.fullmatch(t):
        raise LiteralInvalido(f"literal decimal mal formado: '{t}'")
    valor = float(t)  # nunca int(): sin limite de digitos
    if math.isinf(valor):
        raise LiteralInvalido(f"literal fuera del rango de double: '{_recortar(t)}'")
    return valor  # un literal demasiado pequeno da subnormal o +-0.0, como dicta IEEE-754


def literal_a_bytes(texto: str, orden: str = "big") -> bytes:
    """
    Los 8 bytes del double. Por defecto big-endian ('>d'): la RAM de Enigma-64
    lee las palabras en big-endian (enigma64/memoria.py). orden='little' da '<d'.
    """
    if orden not in ("big", "little"):
        raise ValueError(f"orden debe ser 'big' o 'little', no {orden!r}")
    return struct.pack(">d" if orden == "big" else "<d", literal_a_double(texto))


def literal_a_bits(texto: str) -> int:
    """Patron de 64 bits del double, listo para STORE o para cargar en un registro."""
    return int.from_bytes(literal_a_bytes(texto, "big"), "big")


def entero_decimal_64(texto: str) -> int:
    """Entero decimal en [-2^63, 2^64 - 1]; rechaza los que no caben sin llamar a int()."""
    t = texto.strip()
    if not LITERAL_ENTERO.fullmatch(t):
        raise LiteralInvalido(f"literal entero mal formado: '{_recortar(t)}'")
    if len(t.lstrip("+-").lstrip("0")) > _MAX_DIGITOS_64:
        raise LiteralInvalido(f"literal fuera del rango de 64 bits: '{_recortar(t)}'")
    valor = int(t, 10)
    if not MIN_64 <= valor <= MAX_64:
        raise LiteralInvalido(f"literal fuera del rango de 64 bits: '{_recortar(t)}'")
    return valor


def _recortar(texto: str, maximo: int = 40) -> str:
    """Los mensajes de error no repiten literales de miles de cifras."""
    if len(texto) <= maximo:
        return texto
    return f"{texto[:maximo // 2]}...{texto[-8:]} ({len(texto)} caracteres)"


__all__ = [
    "LiteralInvalido", "LITERAL_DECIMAL", "LITERAL_ENTERO", "MIN_64", "MAX_64",
    "literal_a_double", "literal_a_bytes", "literal_a_bits", "entero_decimal_64",
]
