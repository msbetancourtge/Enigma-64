"""
Traductor CacaoCore-64 -> Enigma-64: control de flujo, saltos, pila y
subrutinas (Integrante 3).

Reglas LEX (ply.lex) que reconocen cada forma de las instrucciones de control
de CacaoCore-64 y cuyas acciones emiten su equivalente en Enigma-64:

    etiquetas              LABEL:
    salto incondicional    JMP
    saltos condicionales   JZ JNZ JE JNE JC JNC JS JNS JO JNO JL JG JGE JLE
    pila y subrutinas      PUSH POP CALL RET
    parada                 HLT

Instrucciones de Enigma-64 que se emiten (enigma64/ensamblador.py y cpu.py):
    JMP etiqueta                  absoluto, 32 bits
    JZ JNZ JC JNC JN JP JV JNV    relativos al PC, 16 bits con signo
                                  (JP salta si N = 0 y Z = 0)
    JMPR Rd                       PC = Rd
    CALL etiqueta                 push(PC siguiente); PC = etiqueta
    RET                           PC = pop()
    PUSH Rd / POP Rd              SP -= 8; [SP] = Rd  /  Rd = [SP]; SP += 8
    HLT

Semantica de origen, tomada del emulador de CacaoCore
(src/processor/microinstructions_mixin.py, instruction_map.py y
src/assembler/asm_parser.py):
  * Una etiqueta es un identificador en MAYUSCULA seguido de ':' en su propia
    linea y vale la direccion de la instruccion siguiente. Un destino que no es
    una etiqueta del programa queda como funcion externa (@func) del enlazador.
  * JZ JNZ JC JNC JS JNS JO JNO miran una sola bandera (la S de CacaoCore es
    la N de Enigma-64 y la O es la V). JL JG JGE JLE JE JNE (j_comparacion)
    solo miran N y Z.
  * CALL hace LR (R14) = direccion de retorno, push(LR) y PC = destino.
    RET hace pop() -> LR y PC = LR.
  * PUSH escribe en [SP] y luego resta 8; POP suma 8 y luego lee. El orden
    LIFO es el mismo de Enigma-64 y R13 (SP) vive en R6, asi que las dos pilas
    son una sola: el protocolo de llamadas del compilador de CacaoCore (el
    llamado saca la direccion de retorno con POP, saca los argumentos y la
    vuelve a meter con PUSH) funciona sin cambios.
  * Ninguna de estas instrucciones modifica banderas, y su traduccion tampoco:
    solo usa saltos, PUSH, POP y los LOAD/STORE de los derrames.

LR (R14) solo se reproduce si el programa lo lee en algun momento, con el
mismo criterio que el ACC del Integrante 2. En ese caso:

    CALL F  ->      CALL _lr_ida_n      ; empuja la direccion de retorno A
                    JMP _lr_vuelta_n    ; A: aqui vuelve RET
                _lr_ida_n:
                    POP lr              ; LR = A
                    PUSH lr
                    JMP F
                _lr_vuelta_n:
    RET     ->      POP lr              ; LR = direccion de retorno
                    JMPR lr

Las etiquetas generadas llevan minusculas, asi que no chocan con las de
CacaoCore, que siempre van en MAYUSCULA.

No se emiten ENTER ni LEAVE: CacaoCore-64 no tiene marcos de pila (su
compilador pasa los argumentos por la pila y los copia a variables globales) y
ENTER/LEAVE reescriben BP (R7), que es la base del area de derrame. Las
instrucciones de control de Enigma-64 que CacaoCore-64 no tiene (JN JP JV JNV
JMPR CALLR ENTER LEAVE), y JA, que no existe en ninguna de las dos maquinas,
se reconocen para reportar el error con la forma correcta de CacaoCore.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Control de flujo, saltos, pila y subrutinas (Tarea 27)
"""

from __future__ import annotations

import re
from typing import Dict, FrozenSet, Iterable, List, Optional, Tuple

import ply.lex as lex
from ply.lex import TOKEN

from .alu import (
    ETIQUETA,
    FIN,
    MEMORIA,
    REGISTRO,
    VARIABLE,
    Operando,
    _ESP,
    _ESP1,
    _mnemonicos,
    dividir_instruccion,
)
from .registros import LR_CACAO, TMP1, TablaRegistros

# ---------------------------------------------------------------------------
# Tablas de traduccion
# ---------------------------------------------------------------------------

# Saltos de CacaoCore -> saltos de Enigma-64 (se salta si alguno se cumple).
# JG/JL/JGE/JLE de CacaoCore solo miran N y Z (j_comparacion), y Z = 1
# implica N = 0, de modo que:
#   JG  (N=0 y Z=0) = JP          JL  (N=1 y Z=0) = JN
#   JGE (N=0 o Z=1) = JP o JZ     JLE (N=1 o Z=1) = JN o JZ
SALTOS: Dict[str, Tuple[str, ...]] = {
    "jmp": ("JMP",), "call": ("CALL",),
    "jz": ("JZ",), "jnz": ("JNZ",), "je": ("JZ",), "jne": ("JNZ",), "jc": ("JC",), "jnc": ("JNC",),
    "js": ("JN",), "jns": ("JP", "JZ"), "jo": ("JV",), "jno": ("JNV",),
    "jl": ("JN",), "jg": ("JP",), "jge": ("JP", "JZ"), "jle": ("JN", "JZ"),
}
SALTOS_CONDICIONALES = frozenset(SALTOS) - {"jmp", "call"}
SALTOS_FPU = ("ju", "jnu")  # bandera U (no ordenado) de la FPU de CacaoCore

# Instrucciones de control que CacaoCore-64 no tiene, con la forma correcta
NO_CACAO: Dict[str, str] = {
    "jn": "es el salto de Enigma-64 por N = 1; en CacaoCore-64 se escribe JS (o JL tras un CMP)",
    "jp": "es el salto de Enigma-64 por N = 0 y Z = 0; en CacaoCore-64 se escribe JG",
    "jv": "es el salto de Enigma-64 por V = 1; en CacaoCore-64 se escribe JO",
    "jnv": "es el salto de Enigma-64 por V = 0; en CacaoCore-64 se escribe JNO",
    "ja": "no existe ni en CacaoCore-64 ni en Enigma-64; para 'mayor que' use JG (se traduce a JP)",
    "jmpr": "CacaoCore-64 no tiene saltos a registro",
    "callr": "CacaoCore-64 no tiene llamadas a registro",
    "enter": "CacaoCore-64 no tiene marcos de pila; los argumentos se pasan con PUSH/POP",
    "leave": "CacaoCore-64 no tiene marcos de pila; los argumentos se pasan con PUSH/POP",
}

# Mnemonicos que traduce este modulo
MNEMONICOS_CONTROL: FrozenSet[str] = (
    frozenset(SALTOS) | frozenset(SALTOS_FPU) | {"ret", "push", "pop", "hlt"} | frozenset(NO_CACAO)
)

# Forma valida de cada instruccion, para los mensajes de error
_FORMAS: Dict[str, str] = {
    **{m: f"{m.upper()} ETIQUETA" for m in SALTOS},
    **{m: f"{m.upper()} ETIQUETA" for m in SALTOS_FPU},
    "push": "PUSH Rx", "pop": "POP Rx", "ret": "RET", "hlt": "HLT",
}


def lee_lr(instrucciones: Iterable) -> bool:
    """True si alguna instruccion lee R14 (LR): solo entonces CALL y RET deben escribirlo."""
    return any(LR_CACAO in ins.efectos.lee for ins in instrucciones)


# ---------------------------------------------------------------------------
# Reglas LEX y acciones de traduccion
# ---------------------------------------------------------------------------

# Destino de un salto: etiqueta (o nombre externo en minuscula), nunca un registro
DESTINO = rf"(?![Rr]\d+(?![A-Za-z0-9_]))(?:{ETIQUETA}|{VARIABLE})(?![A-Za-z0-9_])"

_M_JMP = _mnemonicos("jmp")
_M_CONDICIONALES = _mnemonicos(*SALTOS_CONDICIONALES)
_M_SALTOS = _mnemonicos(*SALTOS)
_M_FPU = _mnemonicos(*SALTOS_FPU)
_M_CALL = _mnemonicos("call")
_M_RET = _mnemonicos("ret")
_M_PILA = _mnemonicos("push", "pop")
_M_HLT = _mnemonicos("hlt")
_M_NO_CACAO = _mnemonicos(*NO_CACAO)


class TraductorControl:
    """
    Analizador LEX de las instrucciones de control de CacaoCore-64.

    Cada regla reconoce una forma y su accion emite el codigo Enigma-64. Se
    usa una linea a la vez, como TraductorALU:

        control = TraductorControl(tabla, etiquetas={"LOOP", "FIN"})
        control.traducir("JGE LOOP", linea=12)   # ['JP LOOP', 'JZ LOOP']
        control.traducir("LOOP:")                # ['LOOP:']

    `tabla` es la TablaRegistros del programa (registros.py); `etiquetas`, las
    que define el programa (None: no se comprueban). Si `lr_observable` es
    True, CALL y RET tambien escriben LR (R14); lo calcula `lee_lr`.
    """

    tokens = (
        "ETIQUETA", "SALTO_INCONDICIONAL", "SALTO_CONDICIONAL", "SALTO_ABSOLUTO",
        "SALTO_FPU", "LLAMADA", "RETORNO", "PILA", "PARADA", "NO_CACAO",
    )

    t_ignore = " \t\r"

    def __init__(
        self,
        tabla: TablaRegistros,
        etiquetas: Optional[Iterable[str]] = None,
        lr_observable: bool = False,
    ) -> None:
        self.tabla = tabla
        self.etiquetas = set(etiquetas) if etiquetas is not None else None
        self.lr_observable = lr_observable
        self.errores: List[Tuple[int, str]] = []
        self._codigo: List[str] = []
        self._linea = 0
        self._llamadas = 0
        self.lexer = lex.lex(object=self, reflags=0)

    # -- punto de entrada ----------------------------------------------------

    def traducir(self, texto: str, linea: int = 0) -> List[str]:
        """
        Traduce una etiqueta o instruccion de control. Los errores quedan en
        self.errores. Toda regla termina en fin de linea o comentario, asi que
        cada linea produce un solo token.
        """
        self._codigo, self._linea = [], linea
        self.lexer.input(texto)
        for _token in iter(self.lexer.token, None):
            pass
        return self._codigo

    # -- reglas --------------------------------------------------------------
    # Etiquetas

    @TOKEN(rf"{ETIQUETA}{_ESP}:{FIN}")
    def t_ETIQUETA(self, t):
        self._emitir(f"{t.value.split(':', 1)[0].strip()}:")
        return t

    # JMP

    @TOKEN(rf"{_M_JMP}{_ESP1}{DESTINO}{FIN}")
    def t_SALTO_INCONDICIONAL(self, t):
        self._saltar(*dividir_instruccion(t.value))
        return t

    # JZ JNZ JE JNE JC JNC JS JNS JO JNO JL JG JGE JLE

    @TOKEN(rf"{_M_CONDICIONALES}{_ESP1}{DESTINO}{FIN}")
    def t_SALTO_CONDICIONAL(self, t):
        self._saltar(*dividir_instruccion(t.value))
        return t

    # Saltos y llamadas a una direccion absoluta (0x...)

    @TOKEN(rf"{_M_SALTOS}{_ESP1}{MEMORIA}{FIN}")
    def t_SALTO_ABSOLUTO(self, t):
        self._error(
            "salto a direccion absoluta no soportado (el codigo de CacaoCore-64 y el de "
            f"Enigma-64 estan en direcciones distintas; use una etiqueta): '{t.value.strip()}'"
        )
        return t

    # JU JNU

    @TOKEN(rf"{_M_FPU}{_ESP1}(?:{DESTINO}|{MEMORIA}){FIN}")
    def t_SALTO_FPU(self, t):
        self._error(
            f"instruccion sin equivalente en Enigma-64: '{t.value.strip()}' (JU/JNU leen la "
            "bandera U de la FPU de CacaoCore-64, que Enigma-64 no tiene)"
        )
        return t

    # CALL y RET

    @TOKEN(rf"{_M_CALL}{_ESP1}{DESTINO}{FIN}")
    def t_LLAMADA(self, t):
        _, (destino,) = dividir_instruccion(t.value)
        if self._definida(destino.valor):
            self._llamar(destino.valor)
        return t

    @TOKEN(rf"{_M_RET}{FIN}")
    def t_RETORNO(self, t):
        self._retornar()
        return t

    # PUSH y POP

    @TOKEN(rf"{_M_PILA}{_ESP1}{REGISTRO}{FIN}")
    def t_PILA(self, t):
        mnemonico, (registro,) = dividir_instruccion(t.value)
        if mnemonico == "push":
            fisico, previas = self.tabla.leer(registro.valor, TMP1)
            self._emitir(*previas, f"PUSH {fisico}")
        else:
            fisico, posteriores = self.tabla.escribir(registro.valor, TMP1)
            self._emitir(f"POP {fisico}", *posteriores)
        return t

    # HLT

    @TOKEN(rf"{_M_HLT}{FIN}")
    def t_PARADA(self, t):
        self._emitir("HLT")
        return t

    # Instrucciones de control que CacaoCore-64 no tiene

    @TOKEN(rf"{_M_NO_CACAO}(?:{_ESP1}[^;\#\n]*?)?{FIN}")
    def t_NO_CACAO(self, t):
        mnemonico = t.value.split(None, 1)[0]
        self._error(
            f"'{mnemonico.upper()}' no es una instruccion de CacaoCore-64: "
            f"{NO_CACAO[mnemonico.lower()]}: '{t.value.strip()}'"
        )
        return t

    def t_COMENTARIO(self, t):
        r"[;\#][^\n]*"

    def t_error(self, t):
        resto = re.split(r"[;#]", t.value, maxsplit=1)[0].strip()
        self._error(self._diagnosticar(resto))
        t.lexer.skip(len(t.value))

    def _diagnosticar(self, texto: str) -> str:
        invalido = re.search(r"(?<![A-Za-z0-9_])[Rr](\d+)(?![A-Za-z0-9_])", texto)
        if invalido and int(invalido.group(1)) > 15:
            return f"registro invalido '{invalido.group(0)}' (CacaoCore tiene R0..R15): '{texto}'"
        etiqueta = re.match(r"([A-Za-z_][A-Za-z0-9_]*)[ \t]*:", texto)
        if etiqueta:
            if not re.fullmatch(ETIQUETA, etiqueta.group(1)):
                return f"etiqueta invalida (CacaoCore-64 solo admite etiquetas en MAYUSCULA): '{texto}'"
            return f"la etiqueta debe ir sola en su linea, como en CacaoCore-64: '{texto}'"
        palabra = texto.split(None, 1)[0] if texto else ""
        if palabra.lower() in MNEMONICOS_CONTROL:
            if palabra not in (palabra.lower(), palabra.upper()):
                return f"mnemonico '{palabra}' mezcla mayusculas y minusculas: '{texto}'"
            forma = _FORMAS.get(palabra.lower())
            if forma:
                return f"modo de direccionamiento no soportado para {palabra.upper()} (forma: {forma}): '{texto}'"
        return f"instruccion desconocida: '{texto}'"

    # -- utilidades de emision ----------------------------------------------

    def _emitir(self, *instrucciones: str) -> None:
        self._codigo.extend(instrucciones)

    def _error(self, mensaje: str) -> None:
        self.errores.append((self._linea, mensaje))
        self._emitir(f"; ERROR: {mensaje}")

    def _definida(self, destino: str) -> bool:
        """True si `destino` es una etiqueta del programa; si no, reporta el error."""
        if self.etiquetas is None or destino in self.etiquetas:
            return True
        self._error(
            f"etiqueta no definida '{destino}' (CacaoCore la dejaria como funcion externa "
            "@func del enlazador; el traductor no enlaza modulos)"
        )
        return False

    # -- acciones ------------------------------------------------------------

    def _saltar(self, mnemonico: str, operandos: List[Operando]) -> None:
        """JMP y saltos condicionales: uno o dos saltos de Enigma-64 al mismo destino."""
        (destino,) = operandos
        if self._definida(destino.valor):
            self._emitir(*(f"{salto} {destino.valor}" for salto in SALTOS[mnemonico]))

    def _llamar(self, destino: str) -> None:
        """CALL F (call_m): push(retorno) y salto; si LR es observable, LR = retorno."""
        if not self.lr_observable:
            self._emitir(f"CALL {destino}")
            return
        ida, vuelta = f"_lr_ida_{self._llamadas}", f"_lr_vuelta_{self._llamadas}"
        self._llamadas += 1
        lr, posteriores = self.tabla.escribir(LR_CACAO, TMP1)
        self._emitir(
            f"CALL {ida}", f"JMP {vuelta}",
            f"{ida}:", f"POP {lr}", *posteriores, f"PUSH {lr}", f"JMP {destino}",
            f"{vuelta}:",
        )

    def _retornar(self) -> None:
        """RET (ret): LR = pop() y PC = LR."""
        if not self.lr_observable:
            self._emitir("RET")
            return
        lr, posteriores = self.tabla.escribir(LR_CACAO, TMP1)
        self._emitir(f"POP {lr}", *posteriores, f"JMPR {lr}")


__all__ = [
    "TraductorControl", "SALTOS", "SALTOS_CONDICIONALES", "SALTOS_FPU", "NO_CACAO",
    "MNEMONICOS_CONTROL", "DESTINO", "lee_lr",
]
