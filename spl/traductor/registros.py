"""
Traductor CacaoCore-64 -> Enigma-64: banco de registros (Integrante 2).

CacaoCore-64 tiene 16 registros de 64 bits (R0-R12 de proposito general,
R13 = SP, R14 = LR y R15 = ACC). Enigma-64 solo tiene R0..R7, y R0 esta
cableado a cero. Este modulo decide donde vive cada registro de CacaoCore
dentro de Enigma-64:

  * en un registro fisico de Enigma-64 (registro "residente"), o
  * en una ranura de 8 bytes del area de derrame (spill), en memoria de
    usuario, direccionada con BP: [R7 + 8*ranura].

Roles fijos de los registros de Enigma-64 dentro del codigo traducido:

  R0  constante 0. Nunca recibe un registro de CacaoCore; se usa como
      operando cero (NEG -> SUB Rx, R0, Rx; CMPZ -> CMP R0, Rx; MOV -> ADD).
  R1  residente 1 \
  R2  residente 2  > los registros de CacaoCore mas usados del programa
  R3  residente 3 /
  R4  TMP1: temporal de datos (operando 1 derramado, resultados intermedios)
  R5  TMP2: temporal de direcciones (Integrante 1) y del segundo operando
  R6  SP de Enigma-64. Recibe R13 (SP) de CacaoCore: PUSH/POP/CALL/RET
      de ambas maquinas usan la misma pila.
  R7  BP: base del area de derrame. Si el programa no necesita derrames,
      R7 queda libre y se usa como cuarto residente.

Las rutinas emitir_load / emitir_store son el punto de enlace con el trabajo
del Integrante 1 (memoria): por defecto emiten LOAD/STORE relativos a BP, y se
pueden reemplazar al construir la TablaRegistros.

Autor: Integrante 2 Tomas Garzon - Registros & ALU (Tarea 27)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

# ---------------------------------------------------------------------------
# Registros de CacaoCore-64
# ---------------------------------------------------------------------------

NUM_REGISTROS_CACAO = 16
SP_CACAO = 13
LR_CACAO = 14
ACC = 15

# Alias que aceptan las funciones publicas. El lexer de CacaoCore solo
# reconoce R0..R15; los alias son una comodidad para el resto del grupo
# (el lexer del Integrante 1 tambien produce SP, LR, ACC y ACM).
ALIAS_CACAO: Dict[str, int] = {"SP": SP_CACAO, "LR": LR_CACAO, "ACC": ACC, "ACM": ACC}

_RE_REGISTRO = re.compile(r"[Rr](\d+)")


class RegistroInvalido(ValueError):
    """El nombre no corresponde a ningun registro R0..R15 de CacaoCore."""


class RegistroDerramado(LookupError):
    """Se pidio el registro fisico de un registro que vive en memoria."""


def numero_registro(registro: Union[int, str]) -> int:
    """
    Normaliza un registro de CacaoCore a su numero 0..15.

    Acepta 3, "R3", "r3" y los alias SP, LR, ACC y ACM.
    """
    if isinstance(registro, int):
        numero = registro
    else:
        nombre = registro.strip()
        if nombre.upper() in ALIAS_CACAO:
            return ALIAS_CACAO[nombre.upper()]
        coincidencia = _RE_REGISTRO.fullmatch(nombre)
        if not coincidencia:
            raise RegistroInvalido(f"registro de CacaoCore invalido: {registro!r}")
        numero = int(coincidencia.group(1))
    if not 0 <= numero < NUM_REGISTROS_CACAO:
        raise RegistroInvalido(f"registro de CacaoCore fuera de rango: R{numero}")
    return numero


def nombre_cacao(numero: int) -> str:
    """Nombre legible de un registro de CacaoCore: R0..R12, R13(SP)..."""
    extra = {SP_CACAO: " (SP)", LR_CACAO: " (LR)", ACC: " (ACC)"}.get(numero, "")
    return f"R{numero}{extra}"


# ---------------------------------------------------------------------------
# Registros de Enigma-64 con rol fijo
# ---------------------------------------------------------------------------

REG_CERO = "R0"
TMP1 = "R4"
TMP2 = "R5"
REG_SP = "R6"
REG_BASE = "R7"
RESIDENTES: Tuple[str, ...] = ("R1", "R2", "R3")

TAM_PALABRA = 8
BASE_DERRAME = 0x00300000  # area de usuario, lejos de .text (0x00200000) y .data (0x00201000)

EmisorMemoria = Callable[[str, int], List[str]]


def operando_base(desplazamiento: int, base: str = REG_BASE) -> str:
    """Operando de memoria en la sintaxis del ensamblador de Enigma-64."""
    if desplazamiento == 0:
        return f"[{base}]"
    signo = "+" if desplazamiento > 0 else "-"
    return f"[{base} {signo} {abs(desplazamiento)}]"


def emitir_load(registro: str, ranura: int) -> List[str]:
    """Carga en `registro` la ranura de derrame indicada (LOAD de Integrante 1)."""
    return [f"LOAD {registro}, {operando_base(ranura * TAM_PALABRA)}"]


def emitir_store(registro: str, ranura: int) -> List[str]:
    """Guarda `registro` en la ranura de derrame indicada (STORE de Integrante 1)."""
    return [f"STORE {registro}, {operando_base(ranura * TAM_PALABRA)}"]


# ---------------------------------------------------------------------------
# Tabla de asignacion
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ubicacion:
    """Donde vive un registro de CacaoCore dentro de Enigma-64."""

    registro: Optional[str] = None  # registro fisico si es residente
    ranura: Optional[int] = None  # indice en el area de derrame si no lo es

    @property
    def residente(self) -> bool:
        return self.registro is not None

    @property
    def desplazamiento(self) -> int:
        if self.ranura is None:
            raise RegistroDerramado("la ubicacion es un registro, no una ranura")
        return self.ranura * TAM_PALABRA

    def __str__(self) -> str:
        if self.residente:
            return self.registro
        return f"derrame {operando_base(self.desplazamiento)}"


class TablaRegistros:
    """
    Asignacion de los 16 registros de CacaoCore a Enigma-64.

    Se construye con `desde_uso` (a partir de lo que usa el programa) o con
    `por_defecto` (tabla estatica, util cuando no se ha analizado un programa).
    Un registro que aparezca sin haber sido asignado recibe una ranura nueva.
    """

    def __init__(
        self,
        residentes: Mapping[int, str],
        derramados: Sequence[int] = (),
        base_derrame: int = BASE_DERRAME,
        emitir_load: EmisorMemoria = emitir_load,
        emitir_store: EmisorMemoria = emitir_store,
    ) -> None:
        self._ubicaciones: Dict[int, Ubicacion] = {SP_CACAO: Ubicacion(registro=REG_SP)}
        for numero, registro in residentes.items():
            self._ubicaciones[numero_registro(numero)] = Ubicacion(registro=registro)
        self._siguiente_ranura = 0
        for numero in derramados:
            self._nueva_ranura(numero_registro(numero))
        self.base_derrame = base_derrame
        self._emitir_load = emitir_load
        self._emitir_store = emitir_store

        fisicos = [u.registro for u in self._ubicaciones.values() if u.residente]
        if len(fisicos) != len(set(fisicos)):
            raise ValueError(f"dos registros de CacaoCore comparten registro fisico: {fisicos}")
        if REG_CERO in fisicos or TMP1 in fisicos or TMP2 in fisicos:
            raise ValueError("R0, TMP1 y TMP2 no pueden recibir registros de CacaoCore")
        if self.hay_derrames and REG_BASE in fisicos:
            raise ValueError("R7 es la base del area de derrame y no puede ser residente")

    # -- construccion --------------------------------------------------------

    @classmethod
    def desde_uso(cls, pesos: Mapping[int, float], **opciones) -> "TablaRegistros":
        """
        Asigna registros fisicos a los registros de CacaoCore mas usados.

        `pesos` asocia cada registro usado con su frecuencia de uso (el
        traductor pondera mas los usos dentro de bucles). Si caben todos en
        R1, R2, R3 y R7, no hay derrames; si no, R7 pasa a ser la base del area
        de derrame y solo los tres primeros quedan en registros.
        """
        candidatos = sorted(
            (numero_registro(n) for n in pesos if numero_registro(n) != SP_CACAO),
            key=lambda n: (-pesos[n], n),
        )
        disponibles = RESIDENTES + (REG_BASE,)
        if len(candidatos) <= len(disponibles):
            return cls(dict(zip(candidatos, disponibles)), (), **opciones)
        corte = len(RESIDENTES)
        return cls(
            dict(zip(candidatos[:corte], RESIDENTES)), candidatos[corte:], **opciones
        )

    @classmethod
    def por_defecto(cls, **opciones) -> "TablaRegistros":
        """
        Tabla estatica: R0->R1, R1->R2, R2->R3, R13->R6 y el resto derramado
        en orden (R3 en la ranura 0, R4 en la 1, ...).
        """
        residentes = {0: "R1", 1: "R2", 2: "R3"}
        derramados = [n for n in range(NUM_REGISTROS_CACAO) if n not in residentes and n != SP_CACAO]
        return cls(residentes, derramados, **opciones)

    def _nueva_ranura(self, numero: int) -> Ubicacion:
        ubicacion = Ubicacion(ranura=self._siguiente_ranura)
        self._siguiente_ranura += 1
        self._ubicaciones[numero] = ubicacion
        return ubicacion

    # -- consultas -----------------------------------------------------------

    @property
    def hay_derrames(self) -> bool:
        return any(not u.residente for u in self._ubicaciones.values())

    def ubicacion(self, registro: Union[int, str]) -> Ubicacion:
        numero = numero_registro(registro)
        if numero not in self._ubicaciones:
            return self._nueva_ranura(numero)
        return self._ubicaciones[numero]

    def es_residente(self, registro: Union[int, str]) -> bool:
        return self.ubicacion(registro).residente

    def mapear_registro(self, registro: Union[int, str], temporal: Optional[str] = None) -> str:
        """
        Registro fisico de Enigma-64 que corresponde a un registro de CacaoCore.

        Para un registro derramado devuelve `temporal` (el llamador debe cargarlo
        y guardarlo con `leer`/`escribir`), o lanza RegistroDerramado si no se dio.
        """
        ubicacion = self.ubicacion(registro)
        if ubicacion.residente:
            return ubicacion.registro
        if temporal is None:
            raise RegistroDerramado(
                f"R{numero_registro(registro)} esta derramado en {ubicacion}; indique un temporal"
            )
        return temporal

    def filas(self) -> List[Tuple[str, str]]:
        """Tabla legible (registro CacaoCore, ubicacion Enigma-64) para informes."""
        return [
            (nombre_cacao(n), str(self._ubicaciones[n])) for n in sorted(self._ubicaciones)
        ]

    # -- generacion de codigo ------------------------------------------------

    def emitir_load(self, registro: str, ranura: int) -> List[str]:
        return self._emitir_load(registro, ranura)

    def emitir_store(self, registro: str, ranura: int) -> List[str]:
        return self._emitir_store(registro, ranura)

    def leer(self, registro: Union[int, str], temporal: str) -> Tuple[str, List[str]]:
        """
        Prepara la lectura de un registro de CacaoCore.

        Devuelve (registro fisico con el valor, instrucciones previas). Si el
        registro esta derramado, las instrucciones lo cargan en `temporal`.
        """
        ubicacion = self.ubicacion(registro)
        if ubicacion.residente:
            return ubicacion.registro, []
        return temporal, self.emitir_load(temporal, ubicacion.ranura)

    def escribir(self, registro: Union[int, str], temporal: str) -> Tuple[str, List[str]]:
        """
        Prepara la escritura de un registro de CacaoCore.

        Devuelve (registro fisico donde calcular, instrucciones posteriores).
        Si el registro esta derramado, se calcula en `temporal` y las
        instrucciones posteriores lo guardan en su ranura.
        """
        ubicacion = self.ubicacion(registro)
        if ubicacion.residente:
            return ubicacion.registro, []
        return temporal, self.emitir_store(temporal, ubicacion.ranura)

    def prologo(self, generar_direccion: Optional[Callable[[str, int], List[str]]] = None) -> List[str]:
        """
        Instrucciones de arranque: apuntar BP (R7) al area de derrame.

        `generar_direccion(reg, direccion)` debe devolver la secuencia que
        carga una direccion de 32 bits; el traductor pasa la del Integrante 1
        (ADDI + SHL + ADDI). Sin derrames no se emite nada.
        """
        if not self.hay_derrames:
            return []
        if generar_direccion is None:
            from .alu import cargar_constante as generar_direccion
        return list(generar_direccion(REG_BASE, self.base_derrame))

    def leer_valor(self, registro: Union[int, str], banco, ram) -> int:
        """
        Valor actual de un registro de CacaoCore en una maquina Enigma-64
        (BancoRegistros + RAMMemory) que ejecuto el codigo traducido.
        """
        ubicacion = self.ubicacion(registro)
        if ubicacion.residente:
            return banco.leer_nombre(ubicacion.registro)
        valor, _estado = ram.mem_read(self.base_derrame + ubicacion.desplazamiento, 8)
        return valor or 0


# ---------------------------------------------------------------------------
# API de modulo (tabla estatica) para reutilizar desde otros modulos
# ---------------------------------------------------------------------------

_TABLA_POR_DEFECTO = TablaRegistros.por_defecto()


def mapear_registro(registro: Union[int, str], temporal: Optional[str] = None) -> str:
    """
    mapear_registro(n) con la tabla estatica por defecto.

    El traductor completo usa una tabla calculada para cada programa
    (TablaRegistros.desde_uso); esta funcion sirve a quien solo necesite la
    convencion fija, por ejemplo las pruebas del Integrante 1.
    """
    return _TABLA_POR_DEFECTO.mapear_registro(registro, temporal)


def registros_de(operandos: Iterable) -> List[int]:
    """Numeros de los registros que aparecen en una lista de operandos (alu.Operando)."""
    return [op.registro for op in operandos if op.registro is not None]


__all__ = [
    "ACC", "LR_CACAO", "SP_CACAO", "REG_CERO", "TMP1", "TMP2", "REG_SP", "REG_BASE",
    "RESIDENTES", "BASE_DERRAME", "TAM_PALABRA", "RegistroInvalido", "RegistroDerramado",
    "Ubicacion", "TablaRegistros", "numero_registro", "nombre_cacao", "mapear_registro",
    "emitir_load", "emitir_store", "operando_base", "registros_de",
]
