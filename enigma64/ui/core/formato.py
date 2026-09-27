"""
Conversiones de texto a numero y de numero a texto para la interfaz.

La interfaz de Enigma-64 muestra valores de 64 bits constantemente, y el
usuario los escribe en la base que le resulte comoda. Todo el parseo y el
formateo vive aqui para que los paneles no repitan la misma logica.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

MASCARA_64 = 0xFFFFFFFFFFFFFFFF
BIT_63 = 0x8000000000000000


class ValorInvalido(ValueError):
    """El texto escrito por el usuario no representa un numero valido."""


def parsear_entero(texto: str) -> int:
    """
    Interpreta el texto de un campo de entrada como entero.

    Acepta las bases con las que se trabaja en la documentacion de Enigma-64:

        0x1F00 / 1F00h / $1F00   -> hexadecimal
        0b1011 / 1011b           -> binario
        0o17   / 17o             -> octal
        -42    / 1_000           -> decimal (se permite el guion bajo)

    Un texto sin prefijo se lee como decimal, salvo que contenga digitos
    hexadecimales, en cuyo caso se avisa al usuario en vez de adivinar.
    """
    if texto is None:
        raise ValorInvalido("no se recibio ningun valor")

    limpio = texto.strip().replace("_", "").replace(" ", "")
    if not limpio:
        raise ValorInvalido("el campo esta vacio")

    signo = 1
    if limpio[0] in "+-":
        signo = -1 if limpio[0] == "-" else 1
        limpio = limpio[1:]
        if not limpio:
            raise ValorInvalido("falta el numero despues del signo")

    bases = (("0x", 16), ("0b", 2), ("0o", 8))
    for prefijo, base in bases:
        if limpio.lower().startswith(prefijo):
            return signo * _convertir(limpio[2:], base, texto)

    if limpio[0] == "$":
        return signo * _convertir(limpio[1:], 16, texto)

    sufijos = (("h", 16), ("b", 2), ("o", 8))
    for sufijo, base in sufijos:
        if len(limpio) > 1 and limpio[-1].lower() == sufijo:
            cuerpo = limpio[:-1]
            # "1011b" es binario, pero "0b" ya se trato arriba; "b" suelto no.
            if all(c in "0123456789abcdefABCDEF" for c in cuerpo):
                return signo * _convertir(cuerpo, base, texto)

    return signo * _convertir(limpio, 10, texto)


def _convertir(cuerpo: str, base: int, original: str) -> int:
    if not cuerpo:
        raise ValorInvalido(f"{original!r} no contiene digitos")
    try:
        return int(cuerpo, base)
    except ValueError:
        nombre = {2: "binario", 8: "octal", 10: "decimal", 16: "hexadecimal"}[base]
        raise ValorInvalido(f"{original!r} no es un numero {nombre} valido") from None


def parsear_direccion(texto: str) -> int:
    """
    Igual que :func:`parsear_entero` pero para direcciones: sin prefijo se
    asume hexadecimal, que es como estan escritas todas las direcciones del
    mapa de memoria en la documentacion (0x00200000, 0xFF001000, ...).
    """
    limpio = (texto or "").strip().replace("_", "").replace(" ", "")
    if not limpio:
        raise ValorInvalido("el campo de direccion esta vacio")

    if limpio[0] == "-":
        raise ValorInvalido("una direccion no puede ser negativa")
    if limpio[0] == "+":
        limpio = limpio[1:]
        if not limpio:
            raise ValorInvalido("el campo de direccion esta vacio")

    lleva_prefijo = limpio.lower().startswith(("0x", "0b", "0o")) or limpio[0] == "$"
    if not lleva_prefijo:
        # Sin prefijo se lee en hexadecimal: asi estan escritas todas las
        # direcciones del mapa de memoria (200000 == 0x00200000).
        return parsear_entero("0x" + limpio)
    return parsear_entero(limpio)


def hex64(valor: int) -> str:
    """0x0000000000200000 - el formato que usa la documentacion de la Tarea 9."""
    return f"0x{valor & MASCARA_64:016X}"


def hex32(valor: int) -> str:
    """0x00200000 - direcciones dentro de los 4 GiB fisicos implementados."""
    return f"0x{valor & 0xFFFFFFFF:08X}"


def hex_ancho(valor: int, bytes_: int) -> str:
    """Hexadecimal ajustado al ancho de acceso del bus (1, 2, 4 u 8 bytes)."""
    return f"0x{valor & ((1 << (bytes_ * 8)) - 1):0{bytes_ * 2}X}"


def bin8(valor: int) -> str:
    """Un byte como ocho bits, con el bit 7 a la izquierda."""
    return format(valor & 0xFF, "08b")


def bin64_agrupado(valor: int) -> str:
    """64 bits en grupos de 8, legibles de un vistazo."""
    crudo = format(valor & MASCARA_64, "064b")
    return " ".join(crudo[i:i + 8] for i in range(0, 64, 8))


def con_signo(valor: int) -> int:
    """Lee un patron de 64 bits como entero en complemento a 2."""
    valor &= MASCARA_64
    return valor - (1 << 64) if valor & BIT_63 else valor


def decimal_agrupado(valor: int) -> str:
    """Decimal con separador de miles, para cifras largas."""
    return f"{valor:,}".replace(",", " ")


def ascii_imprimible(byte: int) -> str:
    """Representacion ASCII de un byte para el volcado hexadecimal."""
    return chr(byte) if 0x20 <= byte <= 0x7E else "."


def tamano_legible(bytes_: int) -> str:
    """Convierte una cantidad de bytes a KiB/MiB/GiB."""
    unidades = ("B", "KiB", "MiB", "GiB", "TiB")
    valor = float(bytes_)
    for unidad in unidades:
        if valor < 1024 or unidad == unidades[-1]:
            entero = valor == int(valor)
            return f"{int(valor)} {unidad}" if entero else f"{valor:.1f} {unidad}"
        valor /= 1024
    return f"{bytes_} B"  # pragma: no cover - inalcanzable
