"""
Vista binaria pura (0 y 1) del Enlazador - Enigma-64 (Noctua Systems).

Mejoras 2 y 3 de la retroalimentacion del Taller 01 (Taller 02):

  * Cada instruccion y cada palabra se imprimen como cadenas de 0 y 1 agrupadas
    segun el formato real de 1 a 5 bytes de Enigma-64, con el desglose de sus
    campos (Opcode, Rd, Rs1, Rs2, Imm16, Off16, Rel16, Addr32):

      [.text+0x0000 | 4 B] 00010100 01010000 00000000 00101010 -> ADDI R5, R0, 42
          (Opcode:00010100 | Rd:0101 Rs1:0000 | Imm16:0000000000101010)

  * Toda direccion dice respecto de que base se mide:
      - modulo objeto (.obj / .tobj): offset relativo al inicio de su seccion
        (.text+0x0018, .data+0x0010, .bss+0x0000);
      - imagen enlazada (.e64): direccion absoluta y su offset relativo a la
        base real de la seccion donde quedo ([Dir 0x00200018 (.text+0x0018) | 4 B]);
      - saltos REL16: desplazamiento relativo al PC de la instruccion siguiente
        (inicio + 3, que es P + 2 con P = primer byte del campo).

Los opcodes, formatos y longitudes salen de la tabla del ISA de la CPU
(enigma64.cpu._INSTRUCTIONS) y los nombres de registro de enigma64.registros,
asi que el desglose es el mismo que decodifica el hardware emulado.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from enigma64.cpu import _INSTRUCTIONS as INSTRUCCIONES_ISA
from enigma64.registros import NOMBRE_POR_CODIGO
from .objeto import (
    NOMBRE_TIPO_SECCION,
    PERM_EJECUCION,
    REUB_ABS32,
    REUB_ABS64,
    REUB_HI16,
    REUB_LO16,
    REUB_REL16,
    SECCION_BITS,
    MarcaReubicacion,
    ModuloObjeto,
    SeccionObjeto,
    _formatear_tabla,
    texto_permisos,
)

# Formula de cada tipo de marca (S = simbolo, A = sumando, P = primer byte del campo)
FORMULA_REUBICACION = {
    REUB_ABS64: "S + A",
    REUB_ABS32: "S + A",
    REUB_REL16: "S + A - (P + 2)",
    REUB_HI16: "(S + A + 0x8000) >> 16",
    REUB_LO16: "(S + A) & 0xFFFF",
}

# Bytes por linea en las secciones de datos: una palabra de 64 bits
BYTES_POR_PALABRA = 8

# Una reserva o un relleno de mas bytes que esto se resume en una sola linea
MAX_BYTES_EXPLICITOS = 16


# ---------------------------------------------------------------------------
# 1. Bits y campos de una instruccion
# ---------------------------------------------------------------------------


def bits(datos: bytes) -> str:
    """Bytes como grupos de 8 bits separados por espacios: '00010100 01010000'."""
    return " ".join(f"{b:08b}" for b in datos)


def _registro(codigo: int) -> str:
    return NOMBRE_POR_CODIGO.get(codigo, f"R?{codigo:X}")


def _con_signo_16(valor: int) -> int:
    return valor - 0x10000 if valor & 0x8000 else valor


@dataclass(frozen=True)
class InstruccionDecodificada:
    """Instruccion leida de una seccion de codigo (offset relativo al inicio de la seccion)."""

    offset: int
    crudo: bytes
    mnemonico: str
    formato: str

    @property
    def longitud(self) -> int:
        return len(self.crudo)

    @property
    def campos(self) -> List[List[Tuple[str, str]]]:
        """
        Campos agrupados por byte (o por par de bytes en los campos de 16 y 32
        bits), en el orden en que la CPU los decodifica.
        """
        r = self.crudo
        opcode = [("Opcode", f"{r[0]:08b}")]
        if self.formato == "none":
            return [opcode]
        if self.formato in ("unary", "register"):
            return [opcode, [("Rd", f"{r[1] >> 4:04b}"), ("Relleno", f"{r[1] & 0xF:04b}")]]
        if self.formato == "rr":
            # CMP no escribe registro: el ensamblador deja en cero el nibble de Rd
            destino = "Relleno" if self.mnemonico == "CMP" else "Rd"
            return [
                opcode,
                [(destino, f"{r[1] >> 4:04b}"), ("Rs1", f"{r[1] & 0xF:04b}")],
                [("Rs2", f"{r[2] >> 4:04b}"), ("Relleno", f"{r[2] & 0xF:04b}")],
            ]
        if self.formato in ("imm", "memory"):
            nombre = "Imm16" if self.formato == "imm" else "Off16"
            return [
                opcode,
                [("Rd", f"{r[1] >> 4:04b}"), ("Rs1", f"{r[1] & 0xF:04b}")],
                [(nombre, f"{int.from_bytes(r[2:4], 'big'):016b}")],
            ]
        if self.formato == "relative":
            return [opcode, [("Rel16", f"{int.from_bytes(r[1:3], 'big'):016b}")]]
        if self.formato == "enter":
            return [opcode, [("Relleno", f"{r[1]:08b}")],
                    [("Imm16", f"{int.from_bytes(r[2:4], 'big'):016b}")]]
        # absolute
        return [opcode, [("Addr32", f"{int.from_bytes(r[1:5], 'big'):032b}")]]

    def texto_campos(self) -> str:
        """'Opcode:00010100 | Rd:0101 Rs1:0000 | Imm16:0000000000101010'"""
        return " | ".join(" ".join(f"{n}:{v}" for n, v in grupo) for grupo in self.campos)

    @property
    def desplazamiento_relativo(self) -> Optional[int]:
        """Rel16 con signo de un salto relativo (None si no es salto relativo)."""
        if self.formato != "relative":
            return None
        return _con_signo_16(int.from_bytes(self.crudo[1:3], "big"))

    def ensamblador(self) -> str:
        """Instruccion en la sintaxis del ensamblador del equipo."""
        r, m, f = self.crudo, self.mnemonico, self.formato
        if f == "none":
            return m
        if f in ("unary", "register"):
            return f"{m} {_registro(r[1] >> 4)}"
        if f == "rr":
            if m == "CMP":
                return f"CMP {_registro(r[1] & 0xF)}, {_registro(r[2] >> 4)}"
            return f"{m} {_registro(r[1] >> 4)}, {_registro(r[1] & 0xF)}, {_registro(r[2] >> 4)}"
        if f == "imm":
            inmediato = _con_signo_16(int.from_bytes(r[2:4], "big"))
            return f"{m} {_registro(r[1] >> 4)}, {_registro(r[1] & 0xF)}, {inmediato}"
        if f == "memory":
            desplazamiento = _con_signo_16(int.from_bytes(r[2:4], "big"))
            signo = "-" if desplazamiento < 0 else "+"
            return (f"{m} {_registro(r[1] >> 4)}, "
                    f"[{_registro(r[1] & 0xF)} {signo} {abs(desplazamiento)}]")
        if f == "relative":
            return f"{m} {self.desplazamiento_relativo:+d}"
        if f == "enter":
            return f"{m} {_con_signo_16(int.from_bytes(r[2:4], 'big'))}"
        return f"{m} 0x{int.from_bytes(r[1:5], 'big'):08X}"


def decodificar(codigo: bytes, offset: int) -> Optional[InstruccionDecodificada]:
    """
    Decodifica la instruccion que empieza en codigo[offset]. Devuelve None si el
    opcode no pertenece al ISA o si la instruccion queda cortada por el final.
    """
    entrada = INSTRUCCIONES_ISA.get(codigo[offset])
    if entrada is None:
        return None
    mnemonico, formato, longitud = entrada
    if offset + longitud > len(codigo):
        return None
    return InstruccionDecodificada(offset, bytes(codigo[offset:offset + longitud]), mnemonico, formato)


def _lineas_de_codigo(codigo: bytes):
    """(offset, longitud, InstruccionDecodificada o None) recorriendo la seccion."""
    offset = 0
    while offset < len(codigo):
        instruccion = decodificar(codigo, offset)
        if instruccion is None:
            yield offset, 1, None
            offset += 1
        else:
            yield offset, instruccion.longitud, instruccion
            offset += instruccion.longitud


def _lineas_de_datos(datos: bytes):
    """(offset, longitud) de cada palabra de 64 bits (la ultima puede ser parcial)."""
    for offset in range(0, len(datos), BYTES_POR_PALABRA):
        yield offset, min(BYTES_POR_PALABRA, len(datos) - offset)


def _texto_palabra(crudo: bytes) -> str:
    valor = int.from_bytes(crudo, "big")
    if len(crudo) == BYTES_POR_PALABRA:
        con_signo = valor - (1 << 64) if valor >> 63 else valor
        return f"palabra 0x{valor:016X} = {con_signo}"
    return f"{len(crudo)} bytes 0x{valor:0{2 * len(crudo)}X}"


def _resumen_ceros(cantidad: int) -> str:
    if cantidad <= MAX_BYTES_EXPLICITOS:
        return bits(bytes(cantidad))
    return f"00000000 x {cantidad}"


# ---------------------------------------------------------------------------
# 2. Modulo objeto reubicable (.obj / .tobj): offsets relativos a cada seccion
# ---------------------------------------------------------------------------


def _marcas_en(marcas: Sequence[MarcaReubicacion], inicio: int, longitud: int):
    """Marcas cuyo campo se cruza con los bytes [inicio, inicio + longitud)."""
    return [m for m in marcas if m.offset < inicio + longitud and inicio < m.offset + m.ancho]


def _nota_marca_objeto(modulo: ModuloObjeto, marca: MarcaReubicacion, seccion: SeccionObjeto) -> str:
    simbolo = modulo.simbolos[marca.simbolo].nombre
    fin = marca.offset + marca.ancho - 1
    return (
        f"      ^ {marca.nombre_tipo} {simbolo}{marca.sumando:+d}: campo {seccion.nombre}+0x{marca.offset:04X}"
        f"..0x{fin:04X} (relativo al inicio de {seccion.nombre}); al enlazar recibe "
        f"{FORMULA_REUBICACION.get(marca.tipo, '?')}"
    )


def _destino_relativo_objeto(seccion: SeccionObjeto, instruccion: InstruccionDecodificada) -> str:
    siguiente = instruccion.offset + instruccion.longitud
    destino = siguiente + instruccion.desplazamiento_relativo
    return (f" ; destino {seccion.nombre}+0x{destino:04X} = PC siguiente "
            f"{seccion.nombre}+0x{siguiente:04X} {instruccion.desplazamiento_relativo:+d} B "
            f"(relativo al PC de la instruccion siguiente)")


def formatear_modulo_bits(modulo: ModuloObjeto) -> str:
    """
    Volcado bit a bit del contenido de un modulo objeto reubicable: cada
    instruccion de las secciones de codigo con sus campos, cada palabra de las
    de datos, la extension de las reservas (.bss) y la tabla de reubicacion.
    Todas las posiciones son offsets relativos al inicio de su seccion.
    """
    lineas = [
        f"Volcado binario del modulo objeto '{modulo.nombre}' "
        f"(offsets relativos al inicio de cada seccion)"
    ]
    for indice, seccion in enumerate(modulo.secciones):
        marcas = sorted((m for m in modulo.reubicaciones if m.seccion == indice),
                        key=lambda m: m.offset)
        lineas += ["", (
            f"Seccion {seccion.nombre} ({NOMBRE_TIPO_SECCION[seccion.tipo]}, "
            f"{texto_permisos(seccion.permisos)}, alineacion {seccion.alineacion}, "
            f"{seccion.tamano} bytes)"
        )]
        if seccion.tipo != SECCION_BITS:
            if seccion.tamano:
                lineas.append(
                    f"  [{seccion.nombre}+0x0000 | {seccion.tamano} B] {_resumen_ceros(seccion.tamano)} -> "
                    f"reserva sin bytes en el archivo: el enlazador la llena con ceros "
                    f"({seccion.nombre}+0x0000 a {seccion.nombre}+0x{seccion.tamano - 1:04X})"
                )
            else:
                lineas.append("  (reserva vacia)")
            continue
        if not seccion.contenido:
            lineas.append("  (seccion vacia)")
            continue
        es_codigo = bool(seccion.permisos & PERM_EJECUCION)
        for offset, longitud, instruccion in (
            _lineas_de_codigo(seccion.contenido) if es_codigo
            else ((o, n, None) for o, n in _lineas_de_datos(seccion.contenido))
        ):
            crudo = seccion.contenido[offset:offset + longitud]
            prefijo = f"  [{seccion.nombre}+0x{offset:04X} | {longitud} B] {bits(crudo)} -> "
            propias = _marcas_en(marcas, offset, longitud)
            if instruccion is not None:
                texto = f"{instruccion.ensamblador()} ({instruccion.texto_campos()})"
                if instruccion.formato == "relative":
                    if any(m.tipo == REUB_REL16 for m in propias):
                        texto += " ; destino pendiente: lo fija la marca REL16 al enlazar"
                    else:
                        texto += _destino_relativo_objeto(seccion, instruccion)
            elif es_codigo:
                texto = f"byte sin instruccion valida (0x{crudo[0]:02X})"
            else:
                texto = _texto_palabra(crudo)
            lineas.append(prefijo + texto)
            lineas += [_nota_marca_objeto(modulo, m, seccion) for m in propias]

    lineas += ["", f"Tabla de reubicacion ({len(modulo.reubicaciones)}): "
                   f"offsets relativos al inicio de la seccion que se parcha"]
    filas = []
    for m in sorted(modulo.reubicaciones, key=lambda m: (m.seccion, m.offset)):
        seccion = modulo.secciones[m.seccion]
        filas.append((
            seccion.nombre, f"0x{m.offset:04X}", m.nombre_tipo, str(m.ancho),
            modulo.simbolos[m.simbolo].nombre, f"{m.sumando:+d}",
            FORMULA_REUBICACION.get(m.tipo, "?"),
            bits(seccion.contenido[m.offset:m.offset + m.ancho]),
        ))
    lineas += _formatear_tabla(
        ("Seccion", "Offset", "Tipo", "Ancho", "Simbolo", "Sumando", "Formula", "Bits del campo"),
        filas,
    )
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# 3. Imagen enlazada (.e64): direccion absoluta + offset relativo a su seccion
# ---------------------------------------------------------------------------


def _nota_marca_enlace(aplicada) -> str:
    texto = (
        f"      ^ {aplicada.nombre_tipo} {aplicada.simbolo}{aplicada.sumando:+d}: S = 0x{aplicada.direccion_simbolo:08X}, "
        f"campo P = 0x{aplicada.direccion_campo:08X} ({aplicada.seccion}+0x{aplicada.offset:04X} de "
        f"'{aplicada.modulo}', relativo a la base de la seccion 0x{aplicada.base_seccion:08X}); "
        f"escrito {bits(aplicada.valor)}"
    )
    if aplicada.tipo == REUB_REL16:
        texto += f" = {aplicada.desplazamiento:+d} B relativo al PC siguiente 0x{aplicada.pc_siguiente:08X}"
    return texto


def formatear_enlace_bits(resultado) -> str:
    """
    Volcado bit a bit del ejecutable enlazado (ResultadoEnlace). Cada linea da
    la direccion absoluta y su offset relativo a la base real de la seccion;
    los rellenos de alineacion se muestran aparte y cada campo parchado indica
    el simbolo, la base de la seccion y el valor escrito.
    """
    base = resultado.direccion_base
    imagen = bytes(resultado.binario.bytes_completos())
    lineas = [
        f"Volcado binario del ejecutable enlazado: base de carga 0x{base:08X}, "
        f"{len(imagen)} bytes, entrada 0x{resultado.entry_point:08X}",
        "(cada direccion absoluta va con su offset relativo a la base de su seccion)",
    ]
    cursor = base
    for ubicacion in sorted(resultado.mapa, key=lambda u: (u.direccion, u.tamano)):
        if ubicacion.direccion > cursor:
            hueco = ubicacion.direccion - cursor
            lineas += ["", f"Relleno de alineacion ({hueco} bytes)",
                       f"  [Dir 0x{cursor:08X} | {hueco} B] {_resumen_ceros(hueco)} -> "
                       f"relleno (no pertenece a ninguna seccion)"]
        nombre = ubicacion.seccion
        lineas += ["", (
            f"{nombre} de '{ubicacion.modulo}' ({NOMBRE_TIPO_SECCION[ubicacion.tipo]}, "
            f"{texto_permisos(ubicacion.permisos)}, {ubicacion.tamano} bytes): base de la seccion "
            f"0x{ubicacion.direccion:08X} = base de carga + 0x{ubicacion.direccion - base:04X}"
        )]
        cursor = max(cursor, ubicacion.direccion + ubicacion.tamano)
        if not ubicacion.tamano:
            lineas.append("  (seccion vacia)")
            continue
        inicio = ubicacion.direccion - base
        contenido = imagen[inicio:inicio + ubicacion.tamano]
        if ubicacion.tipo != SECCION_BITS:
            lineas.append(
                f"  [Dir 0x{ubicacion.direccion:08X} ({nombre}+0x0000) | {ubicacion.tamano} B] "
                f"{_resumen_ceros(ubicacion.tamano)} -> reserva en cero"
            )
            continue
        aplicadas = [a for a in resultado.detalle_reubicaciones
                     if a.modulo == ubicacion.modulo and a.seccion == nombre]
        es_codigo = bool(ubicacion.permisos & PERM_EJECUCION)
        for offset, longitud, instruccion in (
            _lineas_de_codigo(contenido) if es_codigo
            else ((o, n, None) for o, n in _lineas_de_datos(contenido))
        ):
            direccion = ubicacion.direccion + offset
            crudo = contenido[offset:offset + longitud]
            prefijo = f"  [Dir 0x{direccion:08X} ({nombre}+0x{offset:04X}) | {longitud} B] {bits(crudo)} -> "
            if instruccion is not None:
                texto = f"{instruccion.ensamblador()} ({instruccion.texto_campos()})"
                if instruccion.formato == "relative":
                    siguiente = direccion + longitud
                    destino = siguiente + instruccion.desplazamiento_relativo
                    texto += (f" ; destino 0x{destino:08X} = PC siguiente 0x{siguiente:08X} "
                              f"{instruccion.desplazamiento_relativo:+d} B")
            elif es_codigo:
                texto = f"byte sin instruccion valida (0x{crudo[0]:02X})"
            else:
                texto = _texto_palabra(crudo)
            lineas.append(prefijo + texto)
            lineas += [
                _nota_marca_enlace(a) for a in aplicadas
                if a.offset < offset + longitud and offset < a.offset + a.ancho
            ]
    return "\n".join(lineas)
