"""
Banco de registros del computador Enigma-64 (Noctua Systems).

Implementa los registros arquitectonicos definidos en la Tarea 9:
    R0..R7, PC, SR  (codificados en 4 bits, 0x0..0x9)

Reglas de la arquitectura implementadas aqui:
  * R0 es parte de los registros de proposito general pero se usa para proveer
    de forma cableada el 0 de reset, halt y referencia; toda escritura se descarta.
  * Todos los registros son de 64 bits; cualquier valor se enmascara a 64 bits.
  * SR contiene las banderas Z, N, C, V, M, I, S en los bits 0..6.
  * SP (R6) arranca en 0x00000000EFFFFFFF (tope de la region de Pila).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constantes de ancho de palabra
# ---------------------------------------------------------------------------

BITS = 64
MASK64 = 0xFFFFFFFFFFFFFFFF
BIT63 = 0x8000000000000000
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1


def a_con_signo(valor: int) -> int:
    """Interpreta un patron de 64 bits como entero en complemento a 2."""
    valor &= MASK64
    return valor - (1 << BITS) if valor & BIT63 else valor


def a_sin_signo(valor: int) -> int:
    """Convierte cualquier entero de Python al patron de 64 bits equivalente."""
    return valor & MASK64


def hex64(valor: int) -> str:
    """Formatea un valor de 64 bits como en la documentacion: 0x0000000000000078."""
    return f"0x{valor & MASK64:016X}"


# ---------------------------------------------------------------------------
# Codificacion de registros (nibble de 4 bits, seccion "Codificacion de los
# Registros" de la Tarea 9)
# ---------------------------------------------------------------------------

COD_R0 = 0x0
COD_R1 = 0x1
COD_R2 = 0x2
COD_R3 = 0x3
COD_R4 = 0x4
COD_R5 = 0x5  # RV - valor de retorno
COD_R6 = 0x6  # SP - stack pointer
COD_R7 = 0x7  # BP - base pointer
COD_PC = 0x8
COD_SR = 0x9

NOMBRE_POR_CODIGO: Dict[int, str] = {
    COD_R0: "R0",
    COD_R1: "R1",
    COD_R2: "R2",
    COD_R3: "R3",
    COD_R4: "R4",
    COD_R5: "R5",
    COD_R6: "R6",
    COD_R7: "R7",
    COD_PC: "PC",
    COD_SR: "SR",
}

CODIGO_POR_NOMBRE: Dict[str, int] = {n: c for c, n in NOMBRE_POR_CODIGO.items()}

# Alias por rol, para que el codigo del resto del grupo se lea mejor
CODIGO_POR_NOMBRE.update({"RV": COD_R5, "SP": COD_R6, "BP": COD_R7})

ALIAS_ROL: Dict[int, str] = {COD_R5: "RV", COD_R6: "SP", COD_R7: "BP"}

# Codigos 0xA..0xF: reservados para extensiones futuras del ISA
CODIGOS_RESERVADOS = frozenset(range(0xA, 0x10))


# ---------------------------------------------------------------------------
# Banderas del registro SR
# ---------------------------------------------------------------------------

BIT_Z = 0  # Zero
BIT_N = 1  # Negative  (bit 63 del resultado)
BIT_C = 2  # Carry     (acarreo / prestamo sin signo)
BIT_V = 3  # oVerflow  (desbordamiento con signo)
BIT_M = 4  # Misaligned
BIT_I = 5  # Interrupt enable
BIT_S = 6  # Supervisor (1 = admin/kernel, 0 = usuario)

BIT_DE_BANDERA: Dict[str, int] = {
    "Z": BIT_Z,
    "N": BIT_N,
    "C": BIT_C,
    "V": BIT_V,
    "M": BIT_M,
    "I": BIT_I,
    "S": BIT_S,
}

ORDEN_BANDERAS = ("Z", "N", "C", "V", "M", "I", "S")

# ---------------------------------------------------------------------------
# Valores de reset (tabla "Estado de Reset" de la Tarea 9)
# ---------------------------------------------------------------------------

SP_RESET = 0x00000000EFFFFFFF  # tope de la region de Pila
PC_RESET = 0x0000000000000000  # vector de reset

# Valor de reset de SR segun la especificacion: 0x...0001 (Z = 1).
# Se provee tambien SR_RESET_SUPERVISOR (0x40, S = 1) para arranque en modo supervisor:
SR_RESET_SEGUN_DOCUMENTO = 0x0000000000000001  # Z = 1
SR_RESET_SUPERVISOR = 0x0000000000000040       # S = 1

SR_RESET = SR_RESET_SEGUN_DOCUMENTO


class RegistroInvalido(Exception):
    """Se intento leer o escribir un codigo de registro no definido."""


# ---------------------------------------------------------------------------
# Banco de registros
# ---------------------------------------------------------------------------


class BancoRegistros:
    """
    Banco de registros de 64 bits del Enigma-64.

    Uso tipico desde la CPU:

        banco = BancoRegistros()
        a = banco.leer(COD_R1)
        banco.escribir(COD_R3, resultado)
        banco.aplicar_banderas({"Z": 1, "N": 0}, afectadas={"Z", "N"})

    Uso tipico desde la GUI:

        banco.suscribir(self.refrescar_panel)
        datos = banco.snapshot()
    """

    def __init__(self, sr_reset: int = SR_RESET) -> None:
        self._sr_reset = sr_reset & MASK64
        self._reg: List[int] = [0] * 16
        self._oyentes: List[Callable[["BancoRegistros"], None]] = []
        self.reset()

    # -- ciclo de vida ------------------------------------------------------

    def reset(self) -> None:
        """Estado de encendido/RESET de la maquina."""
        self._reg = [0] * 16
        self._reg[COD_R6] = SP_RESET
        self._reg[COD_PC] = PC_RESET
        self._reg[COD_SR] = self._sr_reset
        self._notificar()

    # -- acceso por codigo (lo que usa el decodificador de instrucciones) ---

    def _validar(self, codigo: int) -> int:
        if not isinstance(codigo, int) or not (0 <= codigo <= 0xF):
            raise RegistroInvalido(f"codigo de registro fuera de rango: {codigo!r}")
        if codigo in CODIGOS_RESERVADOS:
            raise RegistroInvalido(
                f"registro 0x{codigo:X} esta reservado para extensiones futuras"
            )
        return codigo

    def leer(self, codigo: int) -> int:
        """Lee el registro indicado por su nibble de codificacion."""
        codigo = self._validar(codigo)
        return self._reg[codigo]

    def escribir(self, codigo: int, valor: int, *, notificar: bool = True) -> None:
        """
        Escribe el registro indicado por su nibble.

        R0 es un registro de proposito general que provee de forma cableada el 0 de reset
        o de halt: la escritura se descarta silenciosamente, tal como en el hardware.
        No es un error, simplemente no tiene efecto.
        """
        codigo = self._validar(codigo)
        if codigo == COD_R0:
            return
        self._reg[codigo] = valor & MASK64
        if notificar:
            self._notificar()

    # -- acceso por nombre (comodo para tests y para la GUI) ----------------

    def leer_nombre(self, nombre: str) -> int:
        try:
            return self.leer(CODIGO_POR_NOMBRE[nombre.upper()])
        except KeyError:
            raise RegistroInvalido(f"no existe el registro {nombre!r}") from None

    def escribir_nombre(self, nombre: str, valor: int) -> None:
        try:
            self.escribir(CODIGO_POR_NOMBRE[nombre.upper()], valor)
        except KeyError:
            raise RegistroInvalido(f"no existe el registro {nombre!r}") from None

    # -- atajos para los registros con rol fijo -----------------------------

    @property
    def pc(self) -> int:
        return self._reg[COD_PC]

    @pc.setter
    def pc(self, valor: int) -> None:
        self.escribir(COD_PC, valor)

    @property
    def sp(self) -> int:
        return self._reg[COD_R6]

    @sp.setter
    def sp(self, valor: int) -> None:
        self.escribir(COD_R6, valor)

    @property
    def bp(self) -> int:
        return self._reg[COD_R7]

    @bp.setter
    def bp(self, valor: int) -> None:
        self.escribir(COD_R7, valor)

    @property
    def sr(self) -> int:
        return self._reg[COD_SR]

    @sr.setter
    def sr(self, valor: int) -> None:
        self.escribir(COD_SR, valor)

    def avanzar_pc(self, bytes_instruccion: int) -> int:
        """
        Autoincrementa el PC segun la longitud en bytes de la instruccion
        actual (formatos de longitud variable). Devuelve el PC nuevo.
        """
        self.escribir(COD_PC, (self._reg[COD_PC] + bytes_instruccion) & MASK64)
        return self._reg[COD_PC]

    # -- banderas -----------------------------------------------------------

    def leer_bandera(self, nombre: str) -> int:
        try:
            bit = BIT_DE_BANDERA[nombre.upper()]
        except KeyError:
            raise RegistroInvalido(f"no existe la bandera {nombre!r}") from None
        return (self._reg[COD_SR] >> bit) & 1

    def escribir_bandera(self, nombre: str, valor: int, *, notificar: bool = True) -> None:
        try:
            bit = BIT_DE_BANDERA[nombre.upper()]
        except KeyError:
            raise RegistroInvalido(f"no existe la bandera {nombre!r}") from None
        if valor:
            self._reg[COD_SR] |= 1 << bit
        else:
            self._reg[COD_SR] &= ~(1 << bit) & MASK64
        if notificar:
            self._notificar()

    def aplicar_banderas(
        self,
        banderas: Dict[str, int],
        afectadas: Optional[frozenset] = None,
    ) -> None:
        """
        Vuelca al SR unicamente las banderas que la instruccion afecta.

        `banderas` es el diccionario que devuelve la ALU. `afectadas` limita
        cuales se escriben; si es None se escriben todas las presentes.
        Esto es lo que permite que, por ejemplo, MUL actualice Z y N sin tocar
        C ni V, tal como especifica la tabla del ISA.
        """
        permitidas = afectadas if afectadas is not None else set(banderas)
        for nombre, valor in banderas.items():
            if nombre in permitidas:
                self.escribir_bandera(nombre, valor, notificar=False)
        self._notificar()

    @property
    def en_supervisor(self) -> bool:
        """True si la CPU corre en modo admin/kernel (bit S del SR)."""
        return bool(self.leer_bandera("S"))

    @property
    def interrupciones_habilitadas(self) -> bool:
        return bool(self.leer_bandera("I"))

    # -- observadores para la GUI ------------------------------------------

    def suscribir(self, callback: Callable[["BancoRegistros"], None]) -> None:
        """Registra una funcion que se llama tras cada cambio de estado."""
        self._oyentes.append(callback)

    def desuscribir(self, callback: Callable[["BancoRegistros"], None]) -> None:
        if callback in self._oyentes:
            self._oyentes.remove(callback)

    def _notificar(self) -> None:
        for cb in list(self._oyentes):
            cb(self)

    # -- volcado de estado --------------------------------------------------

    def snapshot(self) -> Dict[str, object]:
        """
        Estado completo en un diccionario, listo para pintar en la GUI o para
        guardarlo en un log de trazado.
        """
        registros = {}
        for codigo, nombre in NOMBRE_POR_CODIGO.items():
            valor = self._reg[codigo]
            registros[nombre] = {
                "codigo": codigo,
                "alias": ALIAS_ROL.get(codigo),
                "valor": valor,
                "hex": hex64(valor),
                "con_signo": a_con_signo(valor),
            }
        return {
            "registros": registros,
            "banderas": {b: self.leer_bandera(b) for b in ORDEN_BANDERAS},
        }

    def __str__(self) -> str:
        filas = []
        for codigo, nombre in NOMBRE_POR_CODIGO.items():
            alias = ALIAS_ROL.get(codigo)
            etiqueta = f"{nombre} ({alias})" if alias else nombre
            filas.append(f"  {etiqueta:<9} {hex64(self._reg[codigo])}")
        banderas = "  ".join(
            f"{b}={self.leer_bandera(b)}" for b in ORDEN_BANDERAS
        )
        return "Banco de registros Enigma-64\n" + "\n".join(filas) + f"\n  [{banderas}]"

    __repr__ = __str__
