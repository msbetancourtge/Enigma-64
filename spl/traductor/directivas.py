"""
Directivas, Secciones, Literales y Enlace con CargadorEnigma (Tarea 27).

Implementa las responsabilidades del Integrante 4:
  1. Analizador léxico con PLY (ply.lex) para reconocer secciones (.data, .text,
     [DATA], [CODE], [MODULE]), directivas de reserva y datos (.word, .byte,
     .ascii, etc.) y comentarios (# y ;).
  2. Normalización formal de constantes y literales a palabras de 64 bits:
     - Enteros decimales con y sin signo (complemento a dos de 64 bits).
     - Hexadecimales (0x...) y binarios (0b...).
     - Punto flotante de doble precisión IEEE 754 (binary64).
     - Caracteres simples ('h'), secuencias de escape ('\\n', '\\t', '\\0') y cadenas.
  3. Reubicación y alineación de variables estáticas a partir de 0x00201000 con
     garantía estricta de alineación a múltiplos de 8 bytes (evita STATUS_MISALIGNED).
  4. Enlace directo con CargadorEnigma (enigma64.cargador):
     - Precarga en memoria RAM en orden Big-Endian.
     - Construcción y serialización de ejecutables estructurados (.e64, b'ENIG').
     - Ejecución asistida por CargadorEnigma con reinicio de prefetch y FSM.

Autor: Integrante 4 - Juan Luis Vergara Novoa (Cargador, Directivas y Bits)
"""

from __future__ import annotations

import re
import struct
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

# Asegurar compatibilidad en entornos donde __file__ no está en sys.modules[__name__]
if hasattr(sys, "modules") and __name__ in sys.modules:
    mod = sys.modules[__name__]
    if not hasattr(mod, "__file__"):
        mod.__file__ = __file__ if "__file__" in globals() else "directivas.py"

import ply.lex as lex

from enigma64.cargador import (
    MAGIC_ENIGMA,
    USER_MEM_START,
    BinarioEnigma,
    CargadorEnigma,
    ViolacionProteccionMemoria,
    escribir_byte_directo,
    leer_byte_directo,
)
from enigma64.memoria import RAMMemory
from enigma64.registros import BancoRegistros, MASK64


# =============================================================================
# Constantes de Arquitectura y Mapeo
# =============================================================================

BASE_CODIGO: int = 0x00200000
BASE_DATOS: int = 0x00201000
TAMANO_PALABRA: int = 8  # 64 bits = 8 bytes
ALINEACION_PALABRA: int = 8


# =============================================================================
# Modelos de Datos para Variables y Secciones
# =============================================================================


@dataclass
class VariableDato:
    """Representa una variable estática declarada en la sección .data de CacaoCore."""

    nombre: str
    tipo_literal: str  # 'decimal' | 'hexadecimal' | 'binario' | 'flotante' | 'caracter' | 'cadena' | 'directiva'
    texto_original: str
    valor_bits: int  # Patrón de 64 bits sin signo (0..0xFFFFFFFFFFFFFFFF)
    direccion_enigma: int = 0  # Asignada durante la reubicación (>= BASE_DATOS)
    elementos_extra: List[int] = field(default_factory=list)  # Para directivas con múltiples elementos

    @property
    def bytes_big_endian(self) -> bytes:
        """Representación en 8 bytes Big-Endian (nativa de Enigma-64)."""
        return struct.pack(">Q", self.valor_bits & MASK64)

    @property
    def bytes_little_endian(self) -> bytes:
        """Representación en 8 bytes Little-Endian (origen CacaoCore-64)."""
        return struct.pack("<Q", self.valor_bits & MASK64)

    @property
    def valor_con_signo(self) -> int:
        """Interpreta el patrón de 64 bits como entero con signo en complemento a dos."""
        b = self.valor_bits & MASK64
        return b - (1 << 64) if b >> 63 else b

    @property
    def valor_flotante(self) -> float:
        """Interpreta el patrón de 64 bits como float IEEE 754 de doble precisión."""
        return struct.unpack(">d", struct.pack(">Q", self.valor_bits & MASK64))[0]


@dataclass
class MapaSeccionDatos:
    """Mapa consolidado de la sección de datos reubicada para Enigma-64."""

    variables: Dict[str, VariableDato] = field(default_factory=dict)
    base_datos: int = BASE_DATOS
    errores: List[Tuple[int, str]] = field(default_factory=list)
    avisos: List[Tuple[int, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errores

    @property
    def total_variables(self) -> int:
        return len(self.variables)

    @property
    def tamano_total_bytes(self) -> int:
        """Calcula el tamaño total en bytes ocupado por todas las variables (múltiplos de 8)."""
        total = 0
        for var in self.variables.values():
            total += 8 * (1 + len(var.elementos_extra))
        return total

    def obtener_direccion(self, nombre: str) -> Optional[int]:
        var = self.variables.get(nombre)
        return var.direccion_enigma if var is not None else None

    def volcar_bytes_big_endian(self) -> bytes:
        """Concatena los bytes de todas las variables en orden de declaración (Big-Endian)."""
        partes: List[bytes] = []
        for var in self.variables.values():
            partes.append(var.bytes_big_endian)
            for extra in var.elementos_extra:
                partes.append(struct.pack(">Q", extra & MASK64))
        return b"".join(partes)

    def volcar_bytes_little_endian(self) -> bytes:
        """Concatena los bytes originales en Little-Endian (útil para auditoría CacaoCore)."""
        partes: List[bytes] = []
        for var in self.variables.values():
            partes.append(var.bytes_little_endian)
            for extra in var.elementos_extra:
                partes.append(struct.pack("<Q", extra & MASK64))
        return b"".join(partes)


# =============================================================================
# Normalizador de Literales CacaoCore -> Enigma-64 (64 bits)
# =============================================================================


def _desescapar_caracter(texto: str) -> int:
    """Convierte una representación literal de carácter en su valor ordinal ASCII."""
    t = texto[1:-1] if len(texto) >= 2 and texto[0] == "'" and texto[-1] == "'" else texto
    if not t:
        return 0
    if t.startswith("\\"):
        escapes = {
            "\\n": 10,
            "\\r": 13,
            "\\t": 9,
            "\\0": 0,
            "\\'": 39,
            '\\"': 34,
            "\\\\": 92,
        }
        if t in escapes:
            return escapes[t]
        if len(t) >= 2 and t[1] in ("x", "X"):
            try:
                return int(t[2:], 16) & 0xFF
            except ValueError:
                pass
        return ord(t[-1])
    return ord(t[0])


def normalizar_literal_cacao(texto: str) -> Tuple[int, str]:
    """
    Normaliza cualquier literal sintáctico de CacaoCore a un patrón de 64 bits sin signo.

    Retorna:
      (valor_bits_64, tipo_detectado)

    Tipos soportados:
      - 'caracter':    'h', '\\n', '\\0'
      - 'hexadecimal': 0x00000177, -0x10, +0xFF
      - 'binario':     0b1010, -0b11
      - 'flotante':    3.14159, -0.5, 1.0e-4 (empaquetado IEEE 754 double precision)
      - 'decimal':     48, -120, +5 (complemento a dos de 64 bits)
    """
    t = texto.strip()

    # 1. Caracteres entre comillas simples
    if t.startswith("'") and t.endswith("'") and len(t) >= 2:
        return _desescapar_caracter(t), "caracter"

    # 2. Cadenas entre comillas dobles (toma ordinal del primer carácter o 0 si vacía)
    if t.startswith('"') and t.endswith('"') and len(t) >= 2:
        contenido = t[1:-1]
        val = ord(contenido[0]) if contenido else 0
        return val, "cadena"

    # 3. Hexadecimal (con o sin signo)
    if re.fullmatch(r"[+-]?0[xX][0-9a-fA-F]+", t):
        val = int(t, 16)
        return val & MASK64, "hexadecimal"

    # 4. Binario (con o sin signo)
    if re.fullmatch(r"[+-]?0[bB][01]+", t):
        val = int(t, 2)
        return val & MASK64, "binario"

    # 5. Flotante con punto decimal o notación científica
    if ("." in t or "e" in t.lower()) and re.fullmatch(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", t):
        try:
            val_f = float(t)
            (bits,) = struct.unpack(">Q", struct.pack(">d", val_f))
            return bits, "flotante"
        except (ValueError, OverflowError):
            pass

    # 6. Entero decimal
    try:
        val_i = int(t, 10)
        return val_i & MASK64, "decimal"
    except ValueError:
        pass

    # Si no se pudo clasificar, devuelve 0 y 'desconocido'
    return 0, "desconocido"


# =============================================================================
# Analizador Léxico PLY de Directivas y Secciones (LexerDirectivasCacao)
# =============================================================================


class LexerDirectivasCacao:
    """
    Analizador léxico PLY para extraer secciones, directivas, comentarios y datos
    en ensamblador CacaoCore-64.
    """

    tokens = (
        "SECCION_DATA",
        "SECCION_TEXT",
        "SECCION_OTRA",
        "DIRECTIVA_DATO",
        "LITERAL_HEX",
        "LITERAL_BIN",
        "LITERAL_FLOAT",
        "LITERAL_DEC",
        "LITERAL_CHAR",
        "LITERAL_STR",
        "IDENTIFICADOR",
        "DOS_PUNTOS",
        "COMA",
    )

    t_DOS_PUNTOS = r":"
    t_COMA = r","
    t_ignore = " \t\r"

    def t_COMENTARIO(self, t):
        r"[;#][^\n]*"
        pass

    def t_NUEVA_LINEA(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    def t_SECCION_DATA(self, t):
        r"\.(?:data|DATA)\b|\[(?:DATA|data)\]"
        t.value = ".data"
        return t

    def t_SECCION_TEXT(self, t):
        r"\.(?:text|TEXT)\b|\[(?:CODE|code)\]"
        t.value = ".text"
        return t

    def t_SECCION_OTRA(self, t):
        r"\.(?:bss|BSS|rodata|RODATA)\b|\[(?:MODULE|SYMBOLS|EXTERNAL|module|symbols|external)\]"
        t.value = t.value.lower()
        return t

    def t_DIRECTIVA_DATO(self, t):
        r"\.(?:word|WORD|quad|QUAD|dword|DWORD|half|HALF|byte|BYTE|ascii|ASCII|asciz|ASCIZ|string|STRING|space|SPACE|align|ALIGN)\b"
        t.value = t.value.lower()
        return t

    def t_LITERAL_HEX(self, t):
        r"[+-]?0[xX][0-9a-fA-F]+"
        return t

    def t_LITERAL_BIN(self, t):
        r"[+-]?0[bB][01]+"
        return t

    def t_LITERAL_FLOAT(self, t):
        r"[+-]?\d+\.\d+(?:[eE][+-]?\d+)?"
        return t

    def t_LITERAL_DEC(self, t):
        r"[+-]?\d+"
        return t

    def t_LITERAL_CHAR(self, t):
        r"'(?:\\.|[^'\\])+'"
        return t

    def t_LITERAL_STR(self, t):
        r'"(?:\\.|[^"\\])*"'
        return t

    def t_IDENTIFICADOR(self, t):
        r"[a-zA-Z_][a-zA-Z0-9_]*"
        return t

    def t_error(self, t):
        self.errores.append((t.lexer.lineno, f"Carácter no reconocido: '{t.value[0]}'"))
        t.lexer.skip(1)

    def __init__(self) -> None:
        self.errores: List[Tuple[int, str]] = []
        self.lexer = lex.lex(object=self, reflags=0)

    def tokenizar(self, fuente: str) -> List[lex.LexToken]:
        self.lexer.lineno = 1
        self.errores.clear()
        self.lexer.input(fuente)
        return list(iter(self.lexer.token, None))


# =============================================================================
# Procesador de Secciones de Datos y Reubicador
# =============================================================================


class ProcesadorDirectivasCacao:
    """
    Procesa un programa ensamblador CacaoCore-64, extrae la sección de datos (.data / [DATA]),
    normaliza cada literal a 64 bits y reubica las direcciones de memoria hacia Enigma-64
    a partir de base_datos (0x00201000 por defecto) con alineación a 8 bytes.
    """

    def __init__(self, base_datos: int = BASE_DATOS) -> None:
        self.base_datos = base_datos

    def procesar(self, fuente: str) -> MapaSeccionDatos:
        mapa = MapaSeccionDatos(base_datos=self.base_datos)
        lexer = LexerDirectivasCacao()
        tokens = lexer.tokenizar(fuente)
        mapa.errores.extend(lexer.errores)

        en_datos = False
        i = 0
        n = len(tokens)
        dir_actual = self.base_datos

        while i < n:
            tok = tokens[i]

            if tok.type in ("SECCION_DATA", "SECCION_TEXT", "SECCION_OTRA"):
                en_datos = tok.type == "SECCION_DATA"
                i += 1
                continue

            if en_datos and tok.type == "IDENTIFICADOR":
                nombre_var = tok.value
                linea = tok.lineno

                # Caso 1: nombre_var : valor
                if i + 2 < n and tokens[i + 1].type == "DOS_PUNTOS":
                    i_val = i + 2
                    tok_val = tokens[i_val]
                    bits, tipo_lit = normalizar_literal_cacao(str(tok_val.value))

                    extras: List[int] = []
                    i_next = i_val + 1
                    while i_next + 1 < n and tokens[i_next].type == "COMA":
                        tok_extra = tokens[i_next + 1]
                        extra_bits, _ = normalizar_literal_cacao(str(tok_extra.value))
                        extras.append(extra_bits)
                        i_next += 2

                    if nombre_var in mapa.variables:
                        mapa.avisos.append(
                            (linea, f"Variable '{nombre_var}' redefinida; se sobrescribe dirección.")
                        )

                    var = VariableDato(
                        nombre=nombre_var,
                        tipo_literal=tipo_lit,
                        texto_original=str(tok_val.value),
                        valor_bits=bits,
                        direccion_enigma=dir_actual,
                        elementos_extra=extras,
                    )
                    mapa.variables[nombre_var] = var

                    dir_actual += 8 * (1 + len(extras))
                    i = i_next
                    continue

                # Caso 2: nombre_var DIRECTIVA_DATO valores
                if i + 2 < n and tokens[i + 1].type == "DIRECTIVA_DATO":
                    directiva = tokens[i + 1].value
                    tok_val = tokens[i + 2]
                    bits, tipo_lit = normalizar_literal_cacao(str(tok_val.value))

                    extras = []
                    i_next = i + 3
                    while i_next + 1 < n and tokens[i_next].type == "COMA":
                        tok_extra = tokens[i_next + 1]
                        extra_bits, _ = normalizar_literal_cacao(str(tok_extra.value))
                        extras.append(extra_bits)
                        i_next += 2

                    var = VariableDato(
                        nombre=nombre_var,
                        tipo_literal="directiva",
                        texto_original=f"{directiva} {tok_val.value}",
                        valor_bits=bits,
                        direccion_enigma=dir_actual,
                        elementos_extra=extras,
                    )
                    mapa.variables[nombre_var] = var
                    dir_actual += 8 * (1 + len(extras))
                    i = i_next
                    continue

            # Si encontramos datos fuera de sección de datos
            if not en_datos and tok.type == "IDENTIFICADOR" and i + 1 < n and tokens[i + 1].type == "DOS_PUNTOS":
                if i + 2 < n and tokens[i + 2].type in (
                    "LITERAL_HEX", "LITERAL_BIN", "LITERAL_FLOAT", "LITERAL_DEC", "LITERAL_CHAR"
                ):
                    mapa.errores.append(
                        (tok.lineno, f"Dato '{tok.value}' declarado fuera de la sección .data")
                    )

            i += 1

        return mapa


# =============================================================================
# Enlace Directo con CargadorEnigma (enigma64.cargador)
# =============================================================================


def precargar_datos_en_ram(
    ram: RAMMemory,
    mapa_datos: MapaSeccionDatos,
    cargador: Optional[CargadorEnigma] = None,
) -> int:
    """
    Escribe directamente en la memoria RAM de Enigma-64 los valores iniciales
    de las variables declaradas en la sección .data, en orden Big-Endian y
    en direcciones alineadas a 8 bytes a partir de mapa_datos.base_datos.

    Retorna la cantidad total de bytes escritos en RAM.
    """
    bytes_totales = 0
    base = mapa_datos.base_datos

    if cargador is not None:
        cargador.validar_limites(base, max(mapa_datos.tamano_total_bytes, 8))
    else:
        if base < USER_MEM_START:
            raise ViolacionProteccionMemoria(
                f"Frontera inválida: la dirección de datos 0x{base:08X} está por debajo de "
                f"la zona de usuario (0x{USER_MEM_START:08X})"
            )

    for var in mapa_datos.variables.values():
        dir_var = var.direccion_enigma
        for offset, byte in enumerate(var.bytes_big_endian):
            ram.mem_write(dir_var + offset, byte, 1, check_alignment=False)
            bytes_totales += 1

        for idx_extra, extra_val in enumerate(var.elementos_extra):
            dir_extra = dir_var + 8 * (idx_extra + 1)
            extra_bytes = struct.pack(">Q", extra_val & MASK64)
            for offset, byte in enumerate(extra_bytes):
                ram.mem_write(dir_extra + offset, byte, 1, check_alignment=False)
                bytes_totales += 1

    return bytes_totales


def construir_binario_enigma(
    codigo_o_binario: Union[str, bytes],
    mapa_datos: MapaSeccionDatos,
    direccion_codigo: int = BASE_CODIGO,
    entry_point: int = BASE_CODIGO,
) -> BinarioEnigma:
    """
    Construye una instancia oficial de BinarioEnigma a partir del código traducido
    y el mapa de variables, poblando la tabla de símbolos y metadatos de cabecera.
    """
    from enigma64.ensamblador import ensamblar

    if isinstance(codigo_o_binario, str):
        cuerpo_codigo = ensamblar(codigo_o_binario, direccion_base=direccion_codigo)
    else:
        cuerpo_codigo = bytearray(codigo_o_binario)

    cuerpo_datos = bytearray(mapa_datos.volcar_bytes_big_endian())

    tabla_simbolos: Dict[str, int] = {
        nombre: var.direccion_enigma for nombre, var in mapa_datos.variables.items()
    }
    tabla_simbolos["_start"] = entry_point

    binario = BinarioEnigma(
        codigo=cuerpo_codigo,
        datos=cuerpo_datos,
        direccion_base=direccion_codigo,
        entry_point=entry_point,
        reubicable=False,
        tabla_reubicacion=[],
        tabla_simbolos=tabla_simbolos,
    )
    return binario


def exportar_ejecutable_e64(
    codigo_o_binario: Union[str, bytes],
    mapa_datos: MapaSeccionDatos,
    ruta_archivo: str,
    direccion_codigo: int = BASE_CODIGO,
    entry_point: int = BASE_CODIGO,
) -> BinarioEnigma:
    """
    Genera y guarda en disco un ejecutable estructurado .e64 compatible con CargadorEnigma.
    """
    binario = construir_binario_enigma(
        codigo_o_binario,
        mapa_datos=mapa_datos,
        direccion_codigo=direccion_codigo,
        entry_point=entry_point,
    )
    bytes_e64 = binario.serializar_e64()
    with open(ruta_archivo, "wb") as f:
        f.write(bytes_e64)
    return binario


def cargar_y_ejecutar_con_cargador(
    fuente_cacao: str,
    max_ciclos: int = 1_000_000,
    base_datos: int = BASE_DATOS,
    usar_precarga_directa_ram: bool = False,
) -> Tuple[Any, BancoRegistros, RAMMemory, CargadorEnigma, Dict[str, Any]]:
    """
    Traduce un programa de CacaoCore-64 y lo ejecuta en el emulador de Enigma-64
    empleando formalmente la clase CargadorEnigma (enigma64.cargador).

    Retorna:
      (cpu, banco, ram, cargador, info_carga)
    """
    from enigma64.cpu import CPU
    from spl.traductor.traductor import TraductorCacaoEnigma

    # 1. Procesar directivas y sección .data de forma robusta
    proc_datos = ProcesadorDirectivasCacao(base_datos=base_datos)
    mapa_datos = proc_datos.procesar(fuente_cacao)

    # 2. Traducir instrucciones con el pipeline completo
    traductor = TraductorCacaoEnigma(base_datos=base_datos)
    resultado = traductor.traducir(fuente_cacao)
    if not resultado.ok:
        raise ValueError(f"Errores en la traducción de CacaoCore: {resultado.errores}")

    # 3. Construir hardware emulado
    ram = RAMMemory()
    banco = BancoRegistros()
    cpu = CPU(ram=ram, banco=banco)
    cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)

    # 4. Construir binario oficial Enigma-64
    binario = construir_binario_enigma(
        codigo_o_binario=resultado.codigo,
        mapa_datos=mapa_datos,
        direccion_codigo=BASE_CODIGO,
        entry_point=BASE_CODIGO,
    )

    # 5. Cargar en RAM utilizando CargadorEnigma
    info_carga = cargador.cargar_binario(
        binario,
        direccion_destino=BASE_CODIGO,
        configurar_cpu=True,
    )

    # 6. Si se solicita precarga directa de datos en RAM
    if usar_precarga_directa_ram:
        precargar_datos_en_ram(ram, mapa_datos, cargador=cargador)

    # 7. Ejecutar CPU
    cpu.ejecutar(max_ciclos=max_ciclos)

    return cpu, banco, ram, cargador, info_carga
