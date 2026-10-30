"""
Traductor de instrucciones de acceso a memoria de CacaoCore-64 a Enigma-64.

Este módulo implementa el análisis léxico con PLY (ply.lex) de las instrucciones
de memoria de la arquitectura CacaoCore-64 y su traducción correspondiente a las
instrucciones LOAD, STORE, LDB y STB de Enigma-64.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

# Asegurar compatibilidad en entornos donde __file__ no está en sys.modules[__name__]
if hasattr(sys, "modules") and __name__ in sys.modules:
    mod = sys.modules[__name__]
    if not hasattr(mod, "__file__"):
        mod.__file__ = __file__ if "__file__" in globals() else "memoria.py"

import ply.lex as lex


# Clases de soporte para operandos analizados

@dataclass
class OperandoRegistro:
    nombre: str


@dataclass
class OperandoInmediato:
    valor: int


@dataclass
class OperandoMemoria:
    tipo: str  # 'puntero', 'puntero_offset', 'variable', 'direccion'
    registro_base: Optional[str] = None
    offset: int = 0
    nombre_var: Optional[str] = None
    direccion_inmediata: Optional[int] = None


# Analizador Léxico PLY para Memoria CacaoCore

class LexerMemoriaCacao:
    """
    Analizador léxico PLY para instrucciones de ensamblador CacaoCore-64
    enfocado en patrones de acceso a memoria.
    """

    tokens = (
        "MNEMONICO_BYTE",
        "MNEMONICO_PALABRA",
        "MNEMONICO_LEA",
        "REGISTRO",
        "HEXADECIMAL",
        "DECIMAL",
        "ID",
        "COMA",
        "DOS_PUNTOS",
        "CORCHETE_IZQ",
        "CORCHETE_DER",
        "MAS",
        "MENOS",
    )

    t_COMA = r","
    t_DOS_PUNTOS = r":"
    t_CORCHETE_IZQ = r"\["
    t_CORCHETE_DER = r"\]"
    t_MAS = r"\+"
    t_MENOS = r"-"
    t_ignore = " \t\r"

    def t_COMENTARIO(self, t):
        r"(\#|\;)[^\n]*"
        pass

    def t_HEXADECIMAL(self, t):
        r"0[xX][0-9a-fA-F]+"
        t.value = int(t.value, 16)
        return t

    def t_DECIMAL(self, t):
        r"\d+"
        t.value = int(t.value, 10)
        return t

    def t_PALABRA(self, t):
        r"[a-zA-Z_.][a-zA-Z0-9_.]*"
        val_lower = t.value.lower()
        if val_lower in {"movb", "loadb", "storeb"}:
            t.type = "MNEMONICO_BYTE"
            t.value = val_lower
        elif val_lower in {
            "movd", "loadd", "stored",
            "movw", "loadw", "storew",
            "movh", "loadh", "storeh",
        }:
            t.type = "MNEMONICO_PALABRA"
            t.value = val_lower
        elif val_lower == "lea":
            t.type = "MNEMONICO_LEA"
            t.value = val_lower
        elif re.fullmatch(r"r(1[0-5]|[0-9])|sp|lr|acc|acm", val_lower):
            t.type = "REGISTRO"
            t.value = t.value.upper()
        else:
            t.type = "ID"
        return t

    def t_error(self, t):
        t.lexer.skip(1)

    def __init__(self):
        self.lexer = lex.lex(object=self, optimize=0, debug=False)

    def tokenizar(self, texto: str) -> List[lex.LexToken]:
        """Tokeniza la cadena de entrada y retorna la lista de tokens."""
        self.lexer.input(texto)
        tokens = []
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            tokens.append(tok)
        return tokens


# Traductor de Memoria

class TraductorMemoria:
    """
    Traduce instrucciones de acceso a memoria de CacaoCore-64 a ensamblador
    Enigma-64 (LOAD, STORE, LDB, STB).
    """

    def __init__(
        self,
        reg_temporal: str = "R7",
        base_datos: int = 0x00201000,
        reg_temporal_valor: str = "R6",
        reg_acm: str = "R5",
        mapeo_registros: Optional[Dict[str, str]] = None,
        tabla_variables: Optional[Dict[str, int]] = None,
        alinear_palabra: bool = True,
    ):
        """
        :param reg_temporal: Registro Enigma-64 usado para construir direcciones.
        :param base_datos: Dirección base en memoria para datos de usuario (>= 0x00200000).
        :param reg_temporal_valor: Registro temporal secundario para almacenar inmediatos.
        :param reg_acm: Registro Enigma-64 mapeado al acumulador (ACM) de CacaoCore.
        :param mapeo_registros: Diccionario opcional para mapear registros CacaoCore -> Enigma.
        :param tabla_variables: Diccionario opcional variable -> offset relativo a base_datos.
        :param alinear_palabra: Si True, ajusta offsets/direcciones de palabra a múltiplos de 8.
        """
        self.reg_temporal = reg_temporal.upper()
        self.base_datos = base_datos
        self.reg_temporal_valor = reg_temporal_valor.upper()
        self.reg_acm = reg_acm.upper()
        self.mapeo_registros = {k.upper(): v.upper() for k, v in mapeo_registros.items()} if mapeo_registros else {}
        self.tabla_variables = dict(tabla_variables) if tabla_variables else {}
        self.alinear_palabra = alinear_palabra

        self.lexer = LexerMemoriaCacao()
        self._proximo_offset_var = len(self.tabla_variables) * 8

    # Gestión de registros y variables

    def mapear_registro(self, reg: str) -> str:
        """Traduce un nombre de registro CacaoCore a un registro válido en Enigma-64."""
        r = reg.strip().upper()
        if r in self.mapeo_registros:
            return self.mapeo_registros[r]

        # Mapeos por convención por defecto
        if r in {"SP", "R13"}:
            return "R6"
        if r in {"LR", "R14"}:
            return "R5"
        if r in {"ACC", "ACM", "R15"}:
            return self.reg_acm

        # Registros arquitectónicos directos R0..R7
        if re.fullmatch(r"R[0-7]", r):
            return r

        # Registros extendidos de CacaoCore (R8..R12) mapeados a registros de trabajo
        mapeo_defecto = {
            "R8": "R1",
            "R9": "R2",
            "R10": "R3",
            "R11": "R4",
            "R12": "R5",
        }
        return mapeo_defecto.get(r, r)

    def registrar_variable(self, nombre: str, offset: Optional[int] = None) -> int:
        """Registra una variable en la tabla de datos asignándole un desplazamiento alineado."""
        if nombre in self.tabla_variables:
            return self.tabla_variables[nombre]
        if offset is not None:
            self.tabla_variables[nombre] = offset
            self._proximo_offset_var = max(self._proximo_offset_var, offset + 8)
            return offset
        nuevo_offset = self._proximo_offset_var
        self.tabla_variables[nombre] = nuevo_offset
        self._proximo_offset_var += 8
        return nuevo_offset

    def obtener_direccion_variable(self, nombre: str) -> int:
        """Retorna la dirección absoluta en RAM de una variable."""
        offset = self.registrar_variable(nombre)
        return self.base_datos + offset

    # Mapeo y alineación de memoria

    def mapear_direccion(self, direccion: int, alinear: bool = True) -> int:
        """
        Lleva una dirección al rango de usuario (>= 0x00200000) y opcionalmente
        la alinea a múltiplo de 8 bytes.
        """
        if direccion >= 0x00200000:
            dir_final = direccion
        elif direccion >= 0x00040000:
            # Segmento de datos estáticos de CacaoCore (0x00040000 - 0x0007FFFF)
            offset = direccion - 0x00040000
            dir_final = self.base_datos + offset
        else:
            # Dirección absoluta/offset directo
            dir_final = self.base_datos + direccion

        if alinear:
            dir_final = dir_final & ~0x7

        return dir_final

    def ajustar_offset(self, offset: int, alinear: bool = True) -> int:
        """
        Ajusta un offset numérico a un múltiplo de 8 bytes para evitar
        STATUS_MISALIGNED en accesos de 64 bits.
        """
        if alinear:
            return (offset // 8) * 8
        return offset

    def generar_secuencia_direccion(self, reg_destino: str, direccion: int) -> List[str]:
        """
        Genera la secuencia canónica Enigma-64:
            ADDI Rx, R0, HI16
            SHL  Rx, Rx, 16
            ADDI Rx, Rx, LO16
        donde HI16 = ((direccion + 0x8000) >> 16) & 0xFFFF para compensar
        la extensión de signo que efectúa la CPU sobre inmediatos de 16 bits.
        """
        reg = self.mapear_registro(reg_destino)
        hi16 = ((direccion + 0x8000) >> 16) & 0xFFFF
        lo16 = direccion & 0xFFFF
        return [
            f"ADDI {reg}, R0, 0x{hi16:04X}",
            f"SHL {reg}, {reg}, 16",
            f"ADDI {reg}, {reg}, 0x{lo16:04X}",
        ]

    # Análisis sintáctico auxiliar de operandos

    def _parsear_operando(
        self, toks: Sequence[lex.LexToken]
    ) -> Optional[Union[OperandoRegistro, OperandoMemoria, OperandoInmediato]]:
        if not toks:
            return None

        # Registro simple: R1, r4, sp
        if len(toks) == 1 and toks[0].type == "REGISTRO":
            return OperandoRegistro(nombre=toks[0].value)

        # Dirección hexadecimal directa sin corchetes: 0x00000177 (en CacaoCore es token MEMORY)
        if len(toks) == 1 and toks[0].type == "HEXADECIMAL":
            return OperandoMemoria(tipo="direccion", direccion_inmediata=toks[0].value)

        # Inmediato numérico decimal con signo opcional: 756, -8
        if len(toks) == 1 and toks[0].type == "DECIMAL":
            return OperandoInmediato(valor=toks[0].value)
        if len(toks) == 2 and toks[0].type in ("MAS", "MENOS") and toks[1].type in ("DECIMAL", "HEXADECIMAL"):
            signo = 1 if toks[0].type == "MAS" else -1
            return OperandoInmediato(valor=signo * toks[1].value)

        # Operando entre corchetes [...]
        if toks[0].type == "CORCHETE_IZQ" and toks[-1].type == "CORCHETE_DER":
            interior = toks[1:-1]
            if not interior:
                return None
            # [R4]
            if len(interior) == 1 and interior[0].type == "REGISTRO":
                return OperandoMemoria(tipo="puntero", registro_base=interior[0].value, offset=0)
            # [R4 + 8] o [R4 - 8]
            if (
                len(interior) == 3
                and interior[0].type == "REGISTRO"
                and interior[1].type in ("MAS", "MENOS")
                and interior[2].type in ("DECIMAL", "HEXADECIMAL")
            ):
                signo = 1 if interior[1].type == "MAS" else -1
                return OperandoMemoria(
                    tipo="puntero_offset",
                    registro_base=interior[0].value,
                    offset=signo * interior[2].value,
                )
            # [temp] o [a]
            if len(interior) == 1 and interior[0].type == "ID":
                return OperandoMemoria(tipo="variable", nombre_var=interior[0].value)
            # [0x00000177] o [100]
            if len(interior) == 1 and interior[0].type in ("HEXADECIMAL", "DECIMAL"):
                return OperandoMemoria(tipo="direccion", direccion_inmediata=interior[0].value)

        # Dirección hexadecimal sin corchetes: 0x00000177
        if len(toks) == 1 and toks[0].type == "HEXADECIMAL":
            return OperandoMemoria(tipo="direccion", direccion_inmediata=toks[0].value)

        # Identificador directo (para LEA o variables sin corchetes)
        if len(toks) == 1 and toks[0].type == "ID":
            return OperandoMemoria(tipo="variable", nombre_var=toks[0].value)

        return None

    # Verificación de instrucción de memoria

    def es_instruccion_memoria(self, linea: str) -> bool:
        """Determina si la línea contiene una instrucción de acceso a memoria de CacaoCore."""
        toks = self.lexer.tokenizar(linea)
        if not toks:
            return False

        # Ignorar etiqueta inicial si existe
        if len(toks) >= 2 and toks[0].type == "ID" and toks[1].type == "DOS_PUNTOS":
            toks = toks[2:]

        if not toks:
            return False

        primer_tipo = toks[0].type
        if primer_tipo == "MNEMONICO_LEA":
            return True

        if primer_tipo not in ("MNEMONICO_BYTE", "MNEMONICO_PALABRA"):
            return False

        # Dividir operandos por coma
        ops_toks = self._separar_operandos_por_coma(toks[1:])
        op1 = self._parsear_operando(ops_toks[0]) if len(ops_toks) >= 1 else None
        op2 = self._parsear_operando(ops_toks[1]) if len(ops_toks) >= 2 else None

        # Si al menos un operando es memoria, es una instrucción de memoria
        if isinstance(op1, OperandoMemoria) or isinstance(op2, OperandoMemoria):
            return True

        # Operaciones unarias (implican acumulador ACM como operando de registro)
        if len(ops_toks) == 1 and isinstance(op1, OperandoMemoria):
            return True

        return False

    def _separar_operandos_por_coma(
        self, toks: Sequence[lex.LexToken]
    ) -> List[List[lex.LexToken]]:
        """Divide una secuencia de tokens en operandos separados por COMA fuera de corchetes."""
        grupos: List[List[lex.LexToken]] = []
        actual: List[lex.LexToken] = []
        nivel_corchetes = 0

        for tok in toks:
            if tok.type == "CORCHETE_IZQ":
                nivel_corchetes += 1
                actual.append(tok)
            elif tok.type == "CORCHETE_DER":
                nivel_corchetes = max(0, nivel_corchetes - 1)
                actual.append(tok)
            elif tok.type == "COMA" and nivel_corchetes == 0:
                if actual:
                    grupos.append(actual)
                    actual = []
            else:
                actual.append(tok)

        if actual:
            grupos.append(actual)
        return grupos

    # Traducción de una línea

    def traducir_linea(self, linea: str) -> List[str]:
        """
        Traduce una línea de ensamblador CacaoCore a una lista de instrucciones
        en ensamblador Enigma-64. Si la línea no es una instrucción de memoria,
        se devuelve como está.
        """
        # Preservar indentación original
        indentacion_match = re.match(r"^([ \t]*)", linea)
        indentacion = indentacion_match.group(1) if indentacion_match else ""

        linea_limpia = linea.strip()
        if not linea_limpia or linea_limpia.startswith(("#", ";")):
            return [linea]

        toks = self.lexer.tokenizar(linea_limpia)
        if not toks:
            return [linea]

        # Extraer etiqueta si existe
        etiqueta: Optional[str] = None
        if len(toks) >= 2 and toks[0].type == "ID" and toks[1].type == "DOS_PUNTOS":
            etiqueta = toks[0].value
            toks = toks[2:]

        if not toks:
            return [f"{indentacion}{etiqueta}:"] if etiqueta else [linea]

        # Si es declaración de variable en .data (ej: "temp: 0")
        if (
            etiqueta
            and len(toks) in (1, 2)
            and (toks[-1].type in ("DECIMAL", "HEXADECIMAL"))
        ):
            self.registrar_variable(etiqueta)
            return [linea]

        # Verificar si es mnemónico de memoria
        mnem_tok = toks[0]
        if mnem_tok.type not in ("MNEMONICO_BYTE", "MNEMONICO_PALABRA", "MNEMONICO_LEA"):
            return [linea]

        ops_toks = self._separar_operandos_por_coma(toks[1:])
        op1 = self._parsear_operando(ops_toks[0]) if len(ops_toks) >= 1 else None
        op2 = self._parsear_operando(ops_toks[1]) if len(ops_toks) >= 2 else None

        # Si ni op1 ni op2 son memoria, y no es LEA, no es acceso a memoria
        if (
            mnem_tok.type != "MNEMONICO_LEA"
            and not isinstance(op1, OperandoMemoria)
            and not isinstance(op2, OperandoMemoria)
        ):
            return [linea]

        es_byte = mnem_tok.type == "MNEMONICO_BYTE"
        alinear = (not es_byte) and self.alinear_palabra
        mnemonico_str = mnem_tok.value.lower()

        instrucciones: List[str] = []

        # Caso 1: LEA (Load Effective Address)
        if mnem_tok.type == "MNEMONICO_LEA":
            reg_dest = self.mapear_registro(op1.nombre) if isinstance(op1, OperandoRegistro) else self.reg_acm
            mem_op = op2 if op2 is not None else op1

            if isinstance(mem_op, OperandoMemoria):
                if mem_op.tipo == "variable":
                    dir_final = self.obtener_direccion_variable(mem_op.nombre_var or "")
                    instrucciones.extend(self.generar_secuencia_direccion(reg_dest, dir_final))
                elif mem_op.tipo == "direccion":
                    dir_final = self.mapear_direccion(mem_op.direccion_inmediata or 0, alinear=alinear)
                    instrucciones.extend(self.generar_secuencia_direccion(reg_dest, dir_final))
                elif mem_op.tipo == "puntero":
                    reg_b = self.mapear_registro(mem_op.registro_base or "R0")
                    instrucciones.append(f"ADDI {reg_dest}, {reg_b}, 0")
                elif mem_op.tipo == "puntero_offset":
                    reg_b = self.mapear_registro(mem_op.registro_base or "R0")
                    off_ajustado = self.ajustar_offset(mem_op.offset, alinear=alinear)
                    instrucciones.append(f"ADDI {reg_dest}, {reg_b}, {off_ajustado}")
            else:
                return [linea]

        # Caso 2: Carga en Registro desde Memoria (LOAD / LDB)
        elif isinstance(op1, OperandoRegistro) and isinstance(op2, OperandoMemoria):
            reg_dest = self.mapear_registro(op1.nombre)
            inst_cmd = "LDB" if es_byte else "LOAD"

            if op2.tipo == "puntero":
                reg_b = self.mapear_registro(op2.registro_base or "R0")
                instrucciones.append(f"{inst_cmd} {reg_dest}, [{reg_b}]")
            elif op2.tipo == "puntero_offset":
                reg_b = self.mapear_registro(op2.registro_base or "R0")
                off_ajustado = self.ajustar_offset(op2.offset, alinear=alinear)
                if off_ajustado == 0:
                    instrucciones.append(f"{inst_cmd} {reg_dest}, [{reg_b}]")
                elif off_ajustado > 0:
                    instrucciones.append(f"{inst_cmd} {reg_dest}, [{reg_b} + {off_ajustado}]")
                else:
                    instrucciones.append(f"{inst_cmd} {reg_dest}, [{reg_b} - {abs(off_ajustado)}]")
            elif op2.tipo == "variable":
                dir_final = self.obtener_direccion_variable(op2.nombre_var or "")
                instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                instrucciones.append(f"{inst_cmd} {reg_dest}, [{self.reg_temporal}]")
            elif op2.tipo == "direccion":
                dir_final = self.mapear_direccion(op2.direccion_inmediata or 0, alinear=alinear)
                instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                instrucciones.append(f"{inst_cmd} {reg_dest}, [{self.reg_temporal}]")


        # Caso 3: Almacenamiento en Memoria desde Registro (STORE / STB)
        elif isinstance(op1, OperandoMemoria) and isinstance(op2, OperandoRegistro):
            reg_src = self.mapear_registro(op2.nombre)
            inst_cmd = "STB" if es_byte else "STORE"

            if op1.tipo == "puntero":
                reg_b = self.mapear_registro(op1.registro_base or "R0")
                instrucciones.append(f"{inst_cmd} {reg_src}, [{reg_b}]")
            elif op1.tipo == "puntero_offset":
                reg_b = self.mapear_registro(op1.registro_base or "R0")
                off_ajustado = self.ajustar_offset(op1.offset, alinear=alinear)
                if off_ajustado == 0:
                    instrucciones.append(f"{inst_cmd} {reg_src}, [{reg_b}]")
                elif off_ajustado > 0:
                    instrucciones.append(f"{inst_cmd} {reg_src}, [{reg_b} + {off_ajustado}]")
                else:
                    instrucciones.append(f"{inst_cmd} {reg_src}, [{reg_b} - {abs(off_ajustado)}]")
            elif op1.tipo == "variable":
                dir_final = self.obtener_direccion_variable(op1.nombre_var or "")
                instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                instrucciones.append(f"{inst_cmd} {reg_src}, [{self.reg_temporal}]")
            elif op1.tipo == "direccion":
                dir_final = self.mapear_direccion(op1.direccion_inmediata or 0, alinear=alinear)
                instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                instrucciones.append(f"{inst_cmd} {reg_src}, [{self.reg_temporal}]")

        # Caso 4: Almacenamiento de Inmediato en Memoria (MOVD/STORED 0x..., num)
        elif isinstance(op1, OperandoMemoria) and isinstance(op2, OperandoInmediato):
            inst_cmd = "STB" if es_byte else "STORE"

            # Cargar dirección en reg_temporal
            if op1.tipo == "variable":
                dir_final = self.obtener_direccion_variable(op1.nombre_var or "")
                instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                reg_base_store = self.reg_temporal
                off_store = 0
            elif op1.tipo == "direccion":
                dir_final = self.mapear_direccion(op1.direccion_inmediata or 0, alinear=alinear)
                instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                reg_base_store = self.reg_temporal
                off_store = 0
            elif op1.tipo == "puntero":
                reg_base_store = self.mapear_registro(op1.registro_base or "R0")
                off_store = 0
            elif op1.tipo == "puntero_offset":
                reg_base_store = self.mapear_registro(op1.registro_base or "R0")
                off_store = self.ajustar_offset(op1.offset, alinear=alinear)
            else:
                return [linea]

            # Cargar el valor inmediato en reg_temporal_valor
            valor = op2.valor
            if -32768 <= valor <= 32767:
                instrucciones.append(f"ADDI {self.reg_temporal_valor}, R0, {valor}")
            else:
                instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal_valor, valor))

            # Emitir instrucción de almacenamiento
            if off_store == 0:
                instrucciones.append(f"{inst_cmd} {self.reg_temporal_valor}, [{reg_base_store}]")
            elif off_store > 0:
                instrucciones.append(f"{inst_cmd} {self.reg_temporal_valor}, [{reg_base_store} + {off_store}]")
            else:
                instrucciones.append(f"{inst_cmd} {self.reg_temporal_valor}, [{reg_base_store} - {abs(off_store)}]")

        # Caso 5: Instrucciones de un solo operando (acumulador implícito)
        elif isinstance(op1, OperandoMemoria) and op2 is None:
            es_load = mnemonico_str.startswith("load") or mnemonico_str.startswith("mov")
            inst_cmd = ("LDB" if es_byte else "LOAD") if es_load else ("STB" if es_byte else "STORE")
            reg_acm = self.reg_acm

            if es_load:
                # Carga en acumulador
                if op1.tipo == "variable":
                    dir_final = self.obtener_direccion_variable(op1.nombre_var or "")
                    instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                    instrucciones.append(f"{inst_cmd} {reg_acm}, [{self.reg_temporal}]")
                elif op1.tipo == "direccion":
                    dir_final = self.mapear_direccion(op1.direccion_inmediata or 0, alinear=alinear)
                    instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                    instrucciones.append(f"{inst_cmd} {reg_acm}, [{self.reg_temporal}]")
                elif op1.tipo == "puntero":
                    reg_b = self.mapear_registro(op1.registro_base or "R0")
                    instrucciones.append(f"{inst_cmd} {reg_acm}, [{reg_b}]")
                elif op1.tipo == "puntero_offset":
                    reg_b = self.mapear_registro(op1.registro_base or "R0")
                    off_ajustado = self.ajustar_offset(op1.offset, alinear=alinear)
                    if off_ajustado == 0:
                        instrucciones.append(f"{inst_cmd} {reg_acm}, [{reg_b}]")
                    else:
                        instrucciones.append(f"{inst_cmd} {reg_acm}, [{reg_b} + {off_ajustado}]")
            else:
                # Almacenamiento desde acumulador
                if op1.tipo == "variable":
                    dir_final = self.obtener_direccion_variable(op1.nombre_var or "")
                    instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                    instrucciones.append(f"{inst_cmd} {reg_acm}, [{self.reg_temporal}]")
                elif op1.tipo == "direccion":
                    dir_final = self.mapear_direccion(op1.direccion_inmediata or 0, alinear=alinear)
                    instrucciones.extend(self.generar_secuencia_direccion(self.reg_temporal, dir_final))
                    instrucciones.append(f"{inst_cmd} {reg_acm}, [{self.reg_temporal}]")
                elif op1.tipo == "puntero":
                    reg_b = self.mapear_registro(op1.registro_base or "R0")
                    instrucciones.append(f"{inst_cmd} {reg_acm}, [{reg_b}]")
                elif op1.tipo == "puntero_offset":
                    reg_b = self.mapear_registro(op1.registro_base or "R0")
                    off_ajustado = self.ajustar_offset(op1.offset, alinear=alinear)
                    if off_ajustado == 0:
                        instrucciones.append(f"{inst_cmd} {reg_acm}, [{reg_b}]")
                    else:
                        instrucciones.append(f"{inst_cmd} {reg_acm}, [{reg_b} + {off_ajustado}]")
        else:
            return [linea]

        if not instrucciones:
            return [linea]

        # Adjuntar etiqueta en la primera instrucción generada si existía
        if etiqueta:
            instrucciones[0] = f"{etiqueta}: {instrucciones[0]}"

        # Aplicar indentación original
        if indentacion:
            return [f"{indentacion}{inst}" for inst in instrucciones]
        return instrucciones

    # Traducción de un programa completo

    def traducir_programa(self, texto: str) -> str:
        """
        Traduce un programa ensamblador CacaoCore-64 completo a ensamblador
        Enigma-64, sustituyendo las instrucciones de memoria por sus secuencias
        equivalentes y preservando directivas, etiquetas y demás instrucciones.
        """
        lineas_resultado: List[str] = []

        # Primera pasada: registrar variables declaradas en .data
        en_seccion_data = False
        for linea in texto.splitlines():
            linea_limpia = re.split(r"[#;]", linea)[0].strip()
            if not linea_limpia:
                continue
            if linea_limpia.lower() in (".data", "section .data"):
                en_seccion_data = True
                continue
            if linea_limpia.lower() in (".text", "section .text"):
                en_seccion_data = False
                continue
            if en_seccion_data and ":" in linea_limpia:
                nombre_var = linea_limpia.split(":", 1)[0].strip()
                if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", nombre_var):
                    self.registrar_variable(nombre_var)

        # Segunda pasada: traducción línea a línea
        for linea in texto.splitlines():
            lineas_traducidas = self.traducir_linea(linea)
            lineas_resultado.extend(lineas_traducidas)

        return "\n".join(lineas_resultado)
