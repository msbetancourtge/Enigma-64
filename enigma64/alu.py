"""
Unidad Aritmetico-Logica (ALU) de 64 bits del Enigma-64.

La ALU es PURA: recibe dos operandos de 64 bits y devuelve el resultado junto
con las banderas calculadas, sin tocar el banco de registros. Quien decide si
esas banderas se vuelcan al SR es la Unidad de Control (Integrante 3), llamando
a BancoRegistros.aplicar_banderas(). Esto hace que la ALU sea trivial de probar
y que el Write-Back quede donde corresponde: en la FSM.

Operaciones cubiertas (seccion "Repertorio de Microinstrucciones Base"):
  Aritmeticas   : ADD SUB MUL DIV ADDI SUBI INC DEC
  Logicas       : AND OR XOR NOT
  Desplazamiento: SHL SHR ASR
  Comparacion   : CMP

Autor: Integrante 2 Tomas Garzon - Registros & ALU
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, FrozenSet, Tuple

from .registros import (
    BIT63,
    BITS,
    INT64_MIN,
    MASK64,
    a_con_signo,
    a_sin_signo,
    hex64,
)

# ---------------------------------------------------------------------------
# Convencion de la bandera C en la resta
# ---------------------------------------------------------------------------
# Hay dos escuelas y hay que elegir UNA y documentarla:
#   "prestamo"    (estilo x86): C = 1 cuando A < B sin signo, es decir, hubo
#                 prestamo. Es la mas intuitiva de leer en un trazado manual.
#   "no_prestamo" (estilo ARM): C = 1 cuando NO hubo prestamo.
# El grupo usa el trazado manual en la documentacion, asi que se adopta
# "prestamo". Cambiar esta constante invierte C en SUB, SUBI, DEC y CMP.
CARRY_EN_RESTA = "prestamo"


class DivisionPorCero(Exception):
    """DIV con divisor 0. La Unidad de Control debe convertirlo en excepcion."""


@dataclass(frozen=True)
class ResultadoALU:
    """Salida de la ALU: el valor de 64 bits mas las banderas calculadas."""

    valor: int
    banderas: Dict[str, int] = field(default_factory=dict)
    afectadas: FrozenSet[str] = frozenset()
    escribe_destino: bool = True  # CMP es la unica que no escribe Rd

    @property
    def hex(self) -> str:
        return hex64(self.valor)

    @property
    def con_signo(self) -> int:
        return a_con_signo(self.valor)

    def __str__(self) -> str:
        activas = " ".join(
            f"{b}={self.banderas[b]}" for b in ("Z", "N", "C", "V") if b in self.banderas
        )
        return f"{self.hex} [{activas}]"


# ---------------------------------------------------------------------------
# Auxiliares de banderas
# ---------------------------------------------------------------------------


def _signo(valor: int) -> int:
    return 1 if valor & BIT63 else 0


def _zn(resultado: int) -> Dict[str, int]:
    """Banderas Z y N, que dependen solo del resultado."""
    return {"Z": 1 if resultado == 0 else 0, "N": _signo(resultado)}


# ---------------------------------------------------------------------------
# Primitivas
# ---------------------------------------------------------------------------


def _suma(a: int, b: int) -> Tuple[int, Dict[str, int]]:
    crudo = a + b
    resultado = crudo & MASK64
    sa, sb, sr = _signo(a), _signo(b), _signo(resultado)
    banderas = _zn(resultado)
    banderas["C"] = 1 if crudo > MASK64 else 0
    # Desbordamiento con signo: dos operandos del mismo signo dan un resultado
    # de signo contrario.
    banderas["V"] = 1 if (sa == sb and sr != sa) else 0
    return resultado, banderas


def _resta(a: int, b: int) -> Tuple[int, Dict[str, int]]:
    resultado = (a - b) & MASK64
    sa, sb, sr = _signo(a), _signo(b), _signo(resultado)
    banderas = _zn(resultado)
    hubo_prestamo = 1 if a < b else 0
    banderas["C"] = hubo_prestamo if CARRY_EN_RESTA == "prestamo" else 1 - hubo_prestamo
    # Desbordamiento con signo: operandos de distinto signo y el resultado
    # toma el signo del sustraendo.
    banderas["V"] = 1 if (sa != sb and sr != sa) else 0
    return resultado, banderas


def _multiplicacion(a: int, b: int) -> Tuple[int, Dict[str, int]]:
    # Se conservan los 64 bits menos significativos. Ese patron de bits es el
    # mismo tanto si los operandos se interpretan con signo como sin signo.
    resultado = (a * b) & MASK64
    return resultado, _zn(resultado)


def _division(a: int, b: int) -> Tuple[int, Dict[str, int]]:
    sa, sb = a_con_signo(a), a_con_signo(b)
    if sb == 0:
        raise DivisionPorCero("DIV con divisor cero")
    # Division entera truncada hacia cero (convencion de hardware). Ojo: el
    # operador // de Python trunca hacia -infinito, que NO es lo mismo:
    #   -7 // 2 == -4   pero el hardware entrega -3.
    magnitud = abs(sa) // abs(sb)
    cociente = -magnitud if (sa < 0) != (sb < 0) else magnitud
    # Caso limite: INT64_MIN / -1 desborda el rango; se envuelve a INT64_MIN.
    resultado = a_sin_signo(cociente)
    return resultado, _zn(resultado)


def _and(a: int, b: int) -> Tuple[int, Dict[str, int]]:
    resultado = a & b
    return resultado, _zn(resultado)


def _or(a: int, b: int) -> Tuple[int, Dict[str, int]]:
    resultado = a | b
    return resultado, _zn(resultado)


def _xor(a: int, b: int) -> Tuple[int, Dict[str, int]]:
    resultado = a ^ b
    return resultado, _zn(resultado)


def _not(a: int, _b: int = 0) -> Tuple[int, Dict[str, int]]:
    resultado = (~a) & MASK64
    return resultado, _zn(resultado)


def _shl(a: int, n: int) -> Tuple[int, Dict[str, int]]:
    """
    Desplazamiento logico a la izquierda. C recibe el ultimo bit expulsado.
    El inmediato es de 16 bits, asi que hay que definir que pasa con n >= 64.
    """
    if n == 0:
        banderas = _zn(a)
        banderas["C"] = None  # C no se modifica cuando el desplazamiento es 0
        return a, banderas
    if n >= BITS:
        c = (a & 1) if n == BITS else 0
        return 0, {**_zn(0), "C": c}
    resultado = (a << n) & MASK64
    c = (a >> (BITS - n)) & 1
    return resultado, {**_zn(resultado), "C": c}


def _shr(a: int, n: int) -> Tuple[int, Dict[str, int]]:
    """Desplazamiento logico a la derecha: rellena con ceros."""
    if n == 0:
        banderas = _zn(a)
        banderas["C"] = None
        return a, banderas
    if n >= BITS:
        c = _signo(a) if n == BITS else 0
        return 0, {**_zn(0), "C": c}
    resultado = a >> n
    c = (a >> (n - 1)) & 1
    return resultado, {**_zn(resultado), "C": c}


def _asr(a: int, n: int) -> Tuple[int, Dict[str, int]]:
    """Desplazamiento aritmetico a la derecha: preserva el bit de signo."""
    sa = a_con_signo(a)
    if n == 0:
        banderas = _zn(a)
        banderas["C"] = None
        return a, banderas
    if n >= BITS:
        resultado = MASK64 if sa < 0 else 0
        return resultado, {**_zn(resultado), "C": _signo(a)}
    # El operador >> de Python sobre enteros negativos ya es aritmetico.
    resultado = a_sin_signo(sa >> n)
    c = (a >> (n - 1)) & 1
    return resultado, {**_zn(resultado), "C": c}


# ---------------------------------------------------------------------------
# Tabla de operaciones: mnemonico -> (primitiva, banderas afectadas, escribe Rd)
# Las banderas afectadas salen literalmente de la columna "Banderas" de las
# tablas del ISA en la Tarea 9.
# ---------------------------------------------------------------------------

Primitiva = Callable[[int, int], Tuple[int, Dict[str, int]]]

TABLA_OPERACIONES: Dict[str, Tuple[Primitiva, FrozenSet[str], bool]] = {
    # Aritmeticas
    "ADD":  (_suma,           frozenset({"Z", "N", "C", "V"}), True),
    "SUB":  (_resta,          frozenset({"Z", "N", "C", "V"}), True),
    "MUL":  (_multiplicacion, frozenset({"Z", "N"}),           True),
    "DIV":  (_division,       frozenset({"Z", "N"}),           True),
    "ADDI": (_suma,           frozenset({"Z", "N", "C", "V"}), True),
    "SUBI": (_resta,          frozenset({"Z", "N", "C", "V"}), True),
    "INC":  (_suma,           frozenset({"Z", "N", "V"}),      True),
    "DEC":  (_resta,          frozenset({"Z", "N", "V"}),      True),
    # Logicas
    "AND":  (_and,            frozenset({"Z", "N"}),           True),
    "OR":   (_or,             frozenset({"Z", "N"}),           True),
    "XOR":  (_xor,            frozenset({"Z", "N"}),           True),
    "NOT":  (_not,            frozenset({"Z", "N"}),           True),
    # Desplazamientos
    "SHL":  (_shl,            frozenset({"Z", "N", "C"}),      True),
    "SHR":  (_shr,            frozenset({"Z", "N", "C"}),      True),
    "ASR":  (_asr,            frozenset({"Z", "N", "C"}),      True),
    # Comparacion: resta completa pero sin escribir el destino
    "CMP":  (_resta,          frozenset({"Z", "N", "C", "V"}), False),
}

# Operaciones que ignoran el segundo operando (formato de 2 bytes)
OPERACIONES_UNARIAS = frozenset({"NOT", "INC", "DEC"})


class OperacionInvalida(Exception):
    """La Unidad de Control pidio una operacion que la ALU no implementa."""


class ALU:
    """
    ALU de 64 bits. Sin estado propio: una sola instancia sirve para todo el
    emulador, y `ultima_operacion` queda disponible solo para depuracion y
    para que la GUI pueda mostrar que hizo el ultimo ciclo EXECUTE.
    """

    def __init__(self) -> None:
        self.ultima_operacion: str = ""
        self.ultimo_resultado: ResultadoALU | None = None

    def ejecutar(self, operacion: str, a: int, b: int = 0) -> ResultadoALU:
        """
        Ejecuta una operacion de la ALU.

        `a` y `b` son los latches A y B descritos en la Tarea 9. Se enmascaran
        a 64 bits antes de operar, asi que es seguro pasarles enteros de Python
        de cualquier tamano o negativos.

        Para INC y DEC se ignora `b` y se usa 1 internamente.
        """
        op = operacion.upper()
        try:
            primitiva, afectadas, escribe = TABLA_OPERACIONES[op]
        except KeyError:
            raise OperacionInvalida(f"la ALU no implementa {operacion!r}") from None

        a = a_sin_signo(a)
        if op in ("INC", "DEC"):
            b = 1
        elif op == "NOT":
            b = 0
        else:
            b = a_sin_signo(b)

        valor, banderas = primitiva(a, b)

        # Un valor None significa "esta bandera no se modifica en este caso"
        # (unico caso real: desplazamiento de 0 posiciones y la bandera C).
        afectadas_reales = frozenset(
            nombre for nombre in afectadas if banderas.get(nombre) is not None
        )
        banderas = {k: v for k, v in banderas.items() if v is not None}

        resultado = ResultadoALU(
            valor=valor,
            banderas=banderas,
            afectadas=afectadas_reales,
            escribe_destino=escribe,
        )
        self.ultima_operacion = op
        self.ultimo_resultado = resultado
        return resultado

    # -- conveniencia para la Unidad de Control -----------------------------

    def ejecutar_y_volcar(self, operacion: str, a: int, b: int, banco) -> ResultadoALU:
        """
        Ejecuta y vuelca de una vez las banderas al SR del banco recibido.
        Atajo para la fase EXECUTE de la FSM; no escribe el registro destino,
        eso corresponde a la fase WRITE-BACK.
        """
        resultado = self.ejecutar(operacion, a, b)
        banco.aplicar_banderas(resultado.banderas, resultado.afectadas)
        return resultado

    @staticmethod
    def operaciones_soportadas() -> Tuple[str, ...]:
        return tuple(sorted(TABLA_OPERACIONES))
