"""
Traductor CacaoCore-64 -> Enigma-64 (driver minimo para integrar).

Lee un .asm de CacaoCore-64 y escribe el .asm equivalente de Enigma-64:

    python -m spl.traductor entrada.asm -o salida.asm [--verificar] [--ejecutar]

Etapas:
  1. Un lexer de lineas (ply.lex) separa secciones, datos, etiquetas e
     instrucciones.
  2. Analisis: registros usados (ponderados por bucles), si el ACC de
     CacaoCore se lee alguna vez y, para cada instruccion, si las banderas
     siguen vivas despues de ella.
  3. Emision: cada instruccion se envia al modulo que la traduce
       ALU y transferencias registro/inmediato -> alu.py      (Integrante 2)
       accesos a memoria y LEA                 -> memoria.py  (Integrante 1)
       saltos, pila, HLT                       -> este archivo (soporte minimo)
     y cada linea emitida lleva como comentario la instruccion original.

Los saltos, la seccion .data y la pila se resuelven aqui solo lo necesario
para que el programa traducido corra en el emulador; el grupo puede
reemplazarlos al integrar.

Autor: Integrante 2 Tomas Garzon - Registros & ALU (Tarea 27)
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import ply.lex as lex

from .alu import (
    MNEMONICOS_ALU,
    MNEMONICOS_TRANSFERENCIA,
    Efectos,
    Operando,
    TraductorALU,
    cargar_constante,
    dividir_instruccion,
    efectos_alu,
    modifica_banderas,
)
from .directivas import (
    ProcesadorDirectivasCacao,
    construir_binario_enigma,
    exportar_ejecutable_e64,
    normalizar_literal_cacao,
    precargar_datos_en_ram,
)
from .memoria import TraductorMemoria
from .registros import (
    ACC,
    BASE_DERRAME,
    REG_CERO,
    TMP1,
    TMP2,
    RegistroInvalido,
    TablaRegistros,
    nombre_cacao,
)

BASE_CODIGO = 0x00200000
BASE_DATOS = 0x00201000

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
SIN_OPERANDOS = {"hlt": "HLT", "ret": "RET", "ei": "EI", "di": "DI", "iret": "IRET", "nop": None}
CONTROL = frozenset(SALTOS) | frozenset(SIN_OPERANDOS) | {"push", "pop", "intr", "ju", "jnu", "sext"}


# ---------------------------------------------------------------------------
# Lexer de lineas
# ---------------------------------------------------------------------------


class LexerPrograma:
    """Divide un programa de CacaoCore en secciones, datos, etiquetas e instrucciones."""

    tokens = ("SECCION", "DATO", "ETIQUETA", "INSTRUCCION")
    t_ignore = " \t\r"

    def __init__(self) -> None:
        self.errores: List[Tuple[int, str]] = []
        self.lexer = lex.lex(object=self, reflags=0)

    def t_COMENTARIO(self, t):
        r"[;\#][^\n]*"

    def t_NUEVA_LINEA(self, t):
        r"\n+"
        t.lexer.lineno += len(t.value)

    def t_SECCION(self, t):
        r"\.(?:data|DATA|text|TEXT)(?![A-Za-z0-9_])|\[(?:DATA|data|CODE|code)\]"
        return t

    def t_DATO(self, t):
        r"[a-z_][a-z0-9_]*[ \t]*:[ \t]*(?:[+-]?0[xX][0-9a-fA-F]+|[+-]?0[bB][01]+|[+-]?\d+\.\d+(?:[eE][+-]?\d+)?|[+-]?\d+|'(?:\\.|[^'\\])+'|\"[^\"\n]*\")"
        return t

    def t_ETIQUETA(self, t):
        r"[A-Z_][A-Z0-9_]*[ \t]*:"
        t.value = t.value[:-1].strip()
        return t

    def t_INSTRUCCION(self, t):
        r"[A-Za-z][A-Za-z0-9_]*(?:[ \t]+[^\n;\#]*)?"
        t.value = t.value.strip()
        return t

    def t_error(self, t):
        resto = t.value.split("\n", 1)[0]
        self.errores.append((t.lexer.lineno, f"texto no reconocido: '{resto.strip()}'"))
        t.lexer.skip(len(resto))

    def tokenizar(self, fuente: str) -> List[lex.LexToken]:
        self.lexer.lineno = 1
        self.lexer.input(fuente)
        return list(iter(self.lexer.token, None))


# ---------------------------------------------------------------------------
# Representacion del programa
# ---------------------------------------------------------------------------


@dataclass
class Instruccion:
    linea: int
    texto: str
    mnemonico: str
    operandos: List[Operando]
    clase: str  # alu | memoria | control | desconocida
    efectos: Efectos


@dataclass
class Programa:
    elementos: List[Tuple[str, object]] = field(default_factory=list)  # (tipo, dato) en orden
    instrucciones: List[Instruccion] = field(default_factory=list)
    etiquetas: Dict[str, int] = field(default_factory=dict)  # etiqueta -> indice de instruccion
    variables: Dict[str, Tuple[int, str]] = field(default_factory=dict)  # nombre -> (bits, texto)
    errores: List[Tuple[int, str]] = field(default_factory=list)


@dataclass
class ResultadoTraduccion:
    codigo: str
    tabla: TablaRegistros
    variables: Dict[str, int]  # variable -> direccion en Enigma-64
    acc_observable: bool
    errores: List[Tuple[int, str]]
    avisos: List[Tuple[int, str]]

    @property
    def ok(self) -> bool:
        return not self.errores


def _valor_dato(texto: str) -> int:
    """Patron de 64 bits de un dato de .data (entero, flotante IEEE 754, caracter, hex o bin)."""
    bits, _ = normalizar_literal_cacao(texto)
    return bits


def _efectos_memoria(mnemonico: str, operandos: List[Operando]) -> Efectos:
    """Efectos de las instrucciones de memoria (las traduce el Integrante 1)."""
    bases = {op.valor for op in operandos if op.tipo == "ind"}
    datos = [op.valor for op in operandos if op.tipo == "reg"]
    if mnemonico == "lea":  # lea_rm: ACC = direccion; Rx = ACC
        return Efectos(frozenset(bases), frozenset(datos or [ACC]), acc_implicito=bool(datos))
    if len(operandos) == 1:  # LOADx [m] / STOREx [m] usan el ACC
        es_carga = not mnemonico.startswith("store")
        return Efectos(frozenset(bases | (set() if es_carga else {ACC})),
                       frozenset({ACC} if es_carga else ()))
    if operandos and operandos[0].tipo == "reg":  # carga: Rx = [m]
        return Efectos(frozenset(bases), frozenset(datos[:1]))
    return Efectos(frozenset(bases | set(datos)))  # almacenamiento: [m] = Rx | imm


def _efectos_control(mnemonico: str, operandos: List[Operando]) -> Efectos:
    registros = [op.valor for op in operandos if op.tipo == "reg"]
    if mnemonico == "push":
        return Efectos(lee=frozenset(registros))
    if mnemonico == "pop":
        return Efectos(escribe=frozenset(registros))
    return Efectos(lee_banderas=mnemonico in SALTOS_CONDICIONALES or mnemonico in ("ju", "jnu"))


def _clasificar(mnemonico: str, operandos: List[Operando]) -> str:
    if mnemonico == "lea":
        return "memoria"
    if mnemonico in MNEMONICOS_TRANSFERENCIA:
        return "memoria" if any(op.es_memoria for op in operandos) else "alu"
    if mnemonico in MNEMONICOS_ALU:
        return "alu"
    if mnemonico in CONTROL:
        return "control"
    return "desconocida"


# ---------------------------------------------------------------------------
# Traductor
# ---------------------------------------------------------------------------


class TraductorCacaoEnigma:
    """
    Traductor completo de un programa CacaoCore-64 a ensamblador Enigma-64.

    `sincronizar_acc`: None (automatico) mantiene el efecto lateral "ACC =
    resultado" de la ALU de CacaoCore solo si el programa lee el ACC en algun
    momento; True lo mantiene siempre; False nunca.
    """

    def __init__(
        self,
        base_datos: int = BASE_DATOS,
        base_derrame: int = BASE_DERRAME,
        sincronizar_acc: Optional[bool] = None,
    ) -> None:
        self.base_datos = base_datos
        self.base_derrame = base_derrame
        self.sincronizar_acc = sincronizar_acc

    # -- etapa 1: lectura ----------------------------------------------------

    def analizar(self, fuente: str) -> Programa:
        programa = Programa()
        lexer = LexerPrograma()
        en_datos = False
        for token in lexer.tokenizar(fuente):
            if token.type == "SECCION":
                en_datos = token.value.lower() == ".data"
                programa.elementos.append(("seccion", token.value))
            elif token.type == "DATO":
                nombre, valor = (p.strip() for p in token.value.split(":", 1))
                if not en_datos:
                    programa.errores.append((token.lineno, f"dato '{nombre}' fuera de .data"))
                programa.variables[nombre] = (_valor_dato(valor), valor)
                programa.elementos.append(("dato", (nombre, valor)))
            elif token.type == "ETIQUETA":
                if token.value in programa.etiquetas:
                    programa.errores.append((token.lineno, f"etiqueta duplicada '{token.value}'"))
                programa.etiquetas[token.value] = len(programa.instrucciones)
                programa.elementos.append(("etiqueta", token.value))
            else:
                instruccion = self._leer_instruccion(token.value, token.lineno, programa)
                if instruccion is not None:
                    programa.elementos.append(("instruccion", len(programa.instrucciones)))
                    programa.instrucciones.append(instruccion)
        programa.errores.extend(lexer.errores)
        return programa

    def _leer_instruccion(self, texto: str, linea: int, programa: Programa) -> Optional[Instruccion]:
        try:
            mnemonico, operandos = dividir_instruccion(texto)
        except RegistroInvalido as exc:
            programa.errores.append((linea, f"{exc}: '{texto}'"))
            return None
        clase = _clasificar(mnemonico, operandos)
        if clase == "alu":
            efectos = efectos_alu(mnemonico, operandos)
        elif clase == "memoria":
            efectos = _efectos_memoria(mnemonico, operandos)
        else:
            efectos = _efectos_control(mnemonico, operandos)
        return Instruccion(linea, texto, mnemonico, operandos, clase, efectos)

    # -- etapa 2: analisis ---------------------------------------------------

    @staticmethod
    def _acc_observable(programa: Programa) -> bool:
        return any(ACC in ins.efectos.lee for ins in programa.instrucciones)

    @staticmethod
    def _pesos(programa: Programa, acc_observable: bool) -> Dict[int, float]:
        """Usos de cada registro; un uso dentro de un bucle vale 10 veces mas por nivel."""
        instrucciones = programa.instrucciones
        profundidad = [0] * len(instrucciones)
        for j, ins in enumerate(instrucciones):
            if ins.mnemonico in SALTOS and ins.operandos and ins.operandos[0].tipo == "etiqueta":
                inicio = programa.etiquetas.get(ins.operandos[0].valor)
                if inicio is not None and inicio <= j:  # salto hacia atras: bucle
                    for k in range(inicio, j + 1):
                        profundidad[k] += 1
        pesos: Dict[int, float] = {}
        for ins, nivel in zip(instrucciones, profundidad):
            peso = 10 ** min(nivel, 3)
            usados = set(ins.efectos.lee | ins.efectos.escribe)
            usados |= {op.registro for op in ins.operandos if op.registro is not None}
            if ins.efectos.acc_implicito and acc_observable:
                usados.add(ACC)
            for registro in usados:
                pesos[registro] = pesos.get(registro, 0) + peso
        return pesos

    @staticmethod
    def _banderas_vivas(programa: Programa) -> List[bool]:
        """
        vivas[i] es True si, despues de la instruccion i, algun camino lee las
        banderas antes de que otra instruccion las escriba. CALL, RET e IRET se
        tratan de forma conservadora (banderas vivas). INTR es transparente: su
        rutina guarda el FR en la pila y lo restaura con IRET.
        """
        instrucciones = programa.instrucciones

        def leidas_desde(inicio: int) -> bool:
            pendientes, vistos = [inicio], set()
            while pendientes:
                j = pendientes.pop()
                if j in vistos or j >= len(instrucciones):
                    continue
                vistos.add(j)
                ins = instrucciones[j]
                if ins.efectos.lee_banderas or ins.mnemonico in ("call", "ret", "iret"):
                    return True
                if ins.efectos.banderas or ins.mnemonico == "hlt":
                    continue
                if ins.mnemonico == "jmp":
                    destino = programa.etiquetas.get(ins.operandos[0].valor) if ins.operandos else None
                    if destino is None:
                        return True
                    pendientes.append(destino)
                else:
                    pendientes.append(j + 1)
            return False

        return [leidas_desde(i + 1) for i in range(len(instrucciones))]

    # -- etapa 3: emision ----------------------------------------------------

    def traducir(self, fuente: str) -> ResultadoTraduccion:
        programa = self.analizar(fuente)
        errores = list(programa.errores)
        avisos: List[Tuple[int, str]] = []

        acc_observable = (
            self._acc_observable(programa) if self.sincronizar_acc is None else self.sincronizar_acc
        )
        tabla = TablaRegistros.desde_uso(
            self._pesos(programa, acc_observable), base_derrame=self.base_derrame
        )
        memoria = TraductorMemoria(
            reg_temporal=TMP2, base_datos=self.base_datos, reg_temporal_valor=TMP1, reg_acm=TMP1
        )
        for nombre in programa.variables:
            memoria.registrar_variable(nombre)
        alu = TraductorALU(tabla, memoria, acc_observable, set(programa.variables))
        vivas = self._banderas_vivas(programa)

        salida = self._encabezado(tabla, acc_observable)
        salida += self._anotar(tabla.prologo(memoria.generar_secuencia_direccion),
                               f"[prologo] BP = area de derrame 0x{self.base_derrame:08X}")
        for nombre, (bits, texto) in programa.variables.items():
            direccion = memoria.obtener_direccion_variable(nombre)
            carga = [] if bits == 0 else cargar_constante(TMP1, bits)
            fuente_dato = REG_CERO if bits == 0 else TMP1
            secuencia = carga + memoria.generar_secuencia_direccion(TMP2, direccion)
            secuencia.append(f"STORE {fuente_dato}, [{TMP2}]")
            salida += self._anotar(secuencia, f"[datos] {nombre}: {texto} -> 0x{direccion:08X}")

        for tipo, dato in programa.elementos:
            if tipo == "etiqueta":
                salida.append(f"{dato}:")
            elif tipo == "seccion":
                salida.append(f"; {dato}")
            elif tipo == "instruccion":
                ins = programa.instrucciones[dato]
                codigo = self._traducir_instruccion(ins, vivas[dato], tabla, memoria, alu,
                                                    programa, acc_observable, errores, avisos)
                salida += self._anotar(codigo, f"L{ins.linea}: {ins.texto}")

        errores += alu.errores
        avisos += alu.avisos
        if not any(ins.mnemonico == "hlt" for ins in programa.instrucciones):
            avisos.append((0, "el programa no tiene HLT"))
        return ResultadoTraduccion(
            codigo="\n".join(salida) + "\n",
            tabla=tabla,
            variables={n: memoria.obtener_direccion_variable(n) for n in programa.variables},
            acc_observable=acc_observable,
            errores=sorted(errores),
            avisos=sorted(avisos),
        )

    def _traducir_instruccion(self, ins, vivas, tabla, memoria, alu, programa, acc_observable,
                              errores, avisos) -> List[str]:
        if ins.clase == "alu":
            codigo = alu.traducir(ins.texto, ins.linea, vivas)
        elif ins.clase == "memoria":
            codigo = self._memoria(ins, tabla, memoria, acc_observable, errores)
        elif ins.clase == "control":
            codigo = self._control(ins, tabla, programa, errores, avisos)
        else:
            errores.append((ins.linea, f"instruccion desconocida: '{ins.texto}'"))
            return ["; ERROR: instruccion desconocida"]
        # Una instruccion de CacaoCore que no toca banderas no puede cambiarlas
        # en Enigma-64 si alguien las va a leer despues: se guardan con la pila.
        if not ins.efectos.banderas and vivas and any(modifica_banderas(c) for c in codigo):
            codigo = ["PUSH SR"] + codigo + ["POP SR"]
        return codigo

    @staticmethod
    def _memoria(ins, tabla, memoria, acc_observable, errores) -> List[str]:
        """
        Traduce con el TraductorMemoria del Integrante 1. Antes se reescriben
        los registros de CacaoCore por su registro fisico de Enigma-64 (TMP1
        para el dato derramado, TMP2 para la base derramada) y se agregan las
        cargas/guardados de las ranuras de derrame.
        """
        previas: List[str] = []
        posteriores: List[str] = []
        nuevos: List[str] = []
        fisico_dato = None
        for op in ins.operandos:
            if op.tipo in ("reg", "ind"):
                temporal = TMP1 if op.tipo == "reg" else TMP2
                ubicacion = tabla.ubicacion(op.valor)
                fisico = ubicacion.registro if ubicacion.residente else temporal
                if not ubicacion.residente:
                    if op.tipo == "ind" or op.valor in ins.efectos.lee:
                        previas += tabla.emitir_load(temporal, ubicacion.ranura)
                    if op.tipo == "reg" and op.valor in ins.efectos.escribe:
                        posteriores += tabla.emitir_store(temporal, ubicacion.ranura)
                if op.tipo == "reg":
                    fisico_dato = fisico
                nuevos.append(fisico if op.tipo == "reg" else f"[{fisico}]")
            else:
                nuevos.append(op.texto)

        # Formas de un operando: el dato implicito es el ACC
        ubicacion_acc = tabla.ubicacion(ACC)
        memoria.reg_acm = ubicacion_acc.registro if ubicacion_acc.residente else TMP1
        if len(ins.operandos) == 1 and not ubicacion_acc.residente:
            if ACC in ins.efectos.lee:
                previas += tabla.emitir_load(TMP1, ubicacion_acc.ranura)
            if ACC in ins.efectos.escribe:
                posteriores += tabla.emitir_store(TMP1, ubicacion_acc.ranura)

        texto = f"{ins.mnemonico.upper()} {', '.join(nuevos)}"
        traducidas = [linea.strip() for linea in memoria.traducir_linea(texto)]
        if traducidas == [texto]:
            errores.append((ins.linea, f"modo de direccionamiento no soportado: '{ins.texto}'"))
            return ["; ERROR: modo no soportado"]

        # LEA Rx, [m] tambien deja la direccion en ACC (lea_rm)
        if ins.efectos.acc_implicito and acc_observable and fisico_dato is not None:
            if ubicacion_acc.residente:
                if ubicacion_acc.registro != fisico_dato:
                    posteriores.append(f"ADD {ubicacion_acc.registro}, {fisico_dato}, {REG_CERO}")
            else:
                posteriores += tabla.emitir_store(fisico_dato, ubicacion_acc.ranura)
        return previas + traducidas + posteriores

    @staticmethod
    def _control(ins, tabla, programa, errores, avisos) -> List[str]:
        mnemonico, operandos = ins.mnemonico, ins.operandos
        if mnemonico in SALTOS:
            if len(operandos) != 1 or operandos[0].tipo != "etiqueta":
                errores.append((ins.linea, f"salto sin etiqueta (no se admiten direcciones absolutas): '{ins.texto}'"))
                return ["; ERROR: destino de salto no soportado"]
            destino = operandos[0].valor
            if destino not in programa.etiquetas:
                errores.append((ins.linea, f"etiqueta no definida '{destino}'"))
                return ["; ERROR: etiqueta no definida"]
            return [f"{salto} {destino}" for salto in SALTOS[mnemonico]]
        if mnemonico in SIN_OPERANDOS:
            enigma = SIN_OPERANDOS[mnemonico]
            return [enigma] if enigma else []
        if mnemonico in ("push", "pop") and len(operandos) == 1 and operandos[0].tipo == "reg":
            registro = operandos[0].valor
            if mnemonico == "push":
                fisico, previas = tabla.leer(registro, TMP1)
                return previas + [f"PUSH {fisico}"]
            fisico, posteriores = tabla.escribir(registro, TMP1)
            return [f"POP {fisico}"] + posteriores
        if mnemonico == "intr":
            avisos.append((ins.linea, f"'{ins.texto}': Enigma-64 no tiene interrupcion de "
                                      "software para E/S; se omite (el dato queda en memoria)"))
            return []
        errores.append((ins.linea, f"instruccion sin equivalente en Enigma-64: '{ins.texto}'"))
        return ["; ERROR: sin equivalente"]

    # -- formato -------------------------------------------------------------

    @staticmethod
    def _anotar(codigo: List[str], origen: str) -> List[str]:
        """Cada instruccion emitida lleva el comentario con la instruccion de CacaoCore."""
        if not codigo:
            return [f"    {'':<26}; {origen}  (sin codigo en Enigma-64)"]
        return [
            f"    {linea}" if linea.startswith(";") else f"    {linea:<26}; {origen}"
            for linea in codigo
        ]

    def _encabezado(self, tabla: TablaRegistros, acc_observable: bool) -> List[str]:
        lineas = [
            "; Traduccion automatica CacaoCore-64 -> Enigma-64",
            f"; Temporales: TMP1={TMP1}  TMP2={TMP2}   Pila: R6   Datos: 0x{self.base_datos:08X}",
            f"; ACC sincronizado: {'si' if acc_observable else 'no (el programa nunca lee R15)'}",
            "; Asignacion de registros:",
        ]
        lineas += [f";   {cacao:<10} -> {enigma}" for cacao, enigma in tabla.filas()]
        return lineas


# ---------------------------------------------------------------------------
# Utilidades: traducir archivos y ejecutar en el emulador
# ---------------------------------------------------------------------------


def traducir_texto(fuente: str, **opciones) -> ResultadoTraduccion:
    return TraductorCacaoEnigma(**opciones).traducir(fuente)


def ejecutar_en_enigma(codigo_enigma: str, max_ciclos: int = 1_000_000,
                       base_datos: int = BASE_DATOS,
                       usar_cargador: bool = False):
    """Ensambla, carga en 0x00200000 y ejecuta hasta HLT. Devuelve (cpu, banco, ram)."""
    from enigma64.cargador import CargadorEnigma
    from enigma64.cpu import CPU
    from enigma64.ensamblador import ensamblar
    from enigma64.memoria import RAMMemory
    from enigma64.registros import BancoRegistros

    binario = ensamblar(codigo_enigma, direccion_base=BASE_CODIGO)
    if BASE_CODIGO + len(binario) > base_datos:
        raise ValueError(
            f"el codigo ({len(binario)} bytes) se solapa con .data en 0x{base_datos:08X}"
        )
    ram, banco = RAMMemory(), BancoRegistros()
    if usar_cargador:
        from enigma64.cargador import BinarioEnigma
        obj_bin = BinarioEnigma(codigo=binario, direccion_base=BASE_CODIGO)
        cpu = CPU(ram=ram, banco=banco)
        cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)
        cargador.cargar_binario(obj_bin, direccion_destino=BASE_CODIGO, configurar_cpu=True)
    else:
        for i, byte in enumerate(binario):
            ram.mem_write(BASE_CODIGO + i, byte, 1, check_alignment=False)
        banco.pc = BASE_CODIGO
        cpu = CPU(ram=ram, banco=banco)
    cpu.ejecutar(max_ciclos=max_ciclos)
    return cpu, banco, ram


def _a_con_signo(valor: int) -> int:
    return valor - (1 << 64) if valor >> 63 else valor


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Traductor CacaoCore-64 -> Enigma-64")
    parser.add_argument("entrada", help="programa .asm de CacaoCore-64")
    parser.add_argument("-o", "--salida", help="archivo .asm de Enigma-64 (por defecto, stdout)")
    parser.add_argument("--exportar-e64", help="ruta para guardar ejecutable estructurado .e64")
    parser.add_argument("--cargador", action="store_true", help="usar CargadorEnigma para la ejecucion")
    parser.add_argument("--verificar", action="store_true", help="ensamblar la salida con el ensamblador de Enigma-64")
    parser.add_argument("--ejecutar", action="store_true", help="ejecutar la salida en el emulador y mostrar el estado")
    args = parser.parse_args(argv)

    with open(args.entrada, encoding="utf-8") as archivo:
        resultado = traducir_texto(archivo.read())
    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as archivo:
            archivo.write(resultado.codigo)
    else:
        print(resultado.codigo)

    for linea, mensaje in resultado.avisos:
        print(f"aviso (linea {linea}): {mensaje}", file=sys.stderr)
    for linea, mensaje in resultado.errores:
        print(f"error (linea {linea}): {mensaje}", file=sys.stderr)

    if args.exportar_e64:
        proc_datos = ProcesadorDirectivasCacao()
        mapa_datos = proc_datos.procesar(resultado.codigo)
        exportar_ejecutable_e64(resultado.codigo, mapa_datos, args.exportar_e64)
        print(f"ejecutable .e64 exportado: {args.exportar_e64}", file=sys.stderr)

    if args.verificar or args.ejecutar:
        from enigma64.ensamblador import ensamblar

        binario = ensamblar(resultado.codigo)
        print(f"ensamblado correcto: {len(binario)} bytes", file=sys.stderr)
    if args.ejecutar:
        cpu, banco, ram = ejecutar_en_enigma(resultado.codigo, usar_cargador=args.cargador)
        print(f"HLT tras {cpu.instrucciones} instrucciones ({cpu.ciclos} ciclos)", file=sys.stderr)
        for nombre, direccion in resultado.variables.items():
            valor, _ = ram.mem_read(direccion, 8)
            print(f"  [{nombre}] @0x{direccion:08X} = {_a_con_signo(valor or 0)}", file=sys.stderr)
        for cacao, _ in resultado.tabla.filas():
            numero = int(cacao.split()[0][1:])
            valor = resultado.tabla.leer_valor(numero, banco, ram)
            print(f"  {cacao:<10} = {_a_con_signo(valor)}", file=sys.stderr)
    return 1 if resultado.errores else 0


if __name__ == "__main__":
    sys.exit(main())
