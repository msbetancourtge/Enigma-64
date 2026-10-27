"""
Motor del Preprocesador SPL (Enigma-64).
Coordina el lexer, gestiona macros, resuelve includes recursivos,
evalua directivas condicionales y construye el mapa de lineas de salida.
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass, field
from typing import Any

from spl.preprocesador.lexer import PreprocesadorLexer


class PreprocesadorError(Exception):
    """
    Excepcion lanzada ante errores del preprocesador.
    Formato: archivo:linea: error: mensaje
    """
    def __init__(self, archivo: str, linea: int, mensaje: str):
        self.archivo = archivo
        self.linea = linea
        self.mensaje = mensaje
        super().__init__(f"{archivo}:{linea}: error: {mensaje}")


@dataclass
class ResultadoPreprocesamiento:
    """
    Resultado del preprocesamiento:
    - texto: codigo preprocesado final
    - macros: diccionario de macros activas al finalizar
    - mapa_lineas: lista de tuplas (archivo_origen, linea_origen) por cada linea de salida
    """
    texto: str
    macros: dict[str, str] = field(default_factory=dict)
    mapa_lineas: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class _SimpleToken:
    """Token liviano interno para manipulacion y emision."""
    type: str
    value: str
    lineno: int = 1
    lexpos: int = 0


class _CondFrame:
    """Representa un marco de contexto condicional (#ifdef / #ifndef)."""
    def __init__(self, tipo: str, activo: bool, cumplido: bool, linea: int, archivo: str):
        self.tipo = tipo
        self.activo = activo
        self.cumplido = cumplido
        self.tiene_else = False
        self.linea = linea
        self.archivo = archivo


class Preprocesador:
    """
    Motor del preprocesador.
    Mantiene estado de macros, includes, guardas #pragma once y directivas condicionales.
    """

    def __init__(
        self,
        dirs_inclusion: list[str] | None = None,
        definiciones: dict[str, Any] | None = None,
        limite_profundidad: int = 50,
    ):
        self.dirs_inclusion = list(dirs_inclusion or [])
        self.macros: dict[str, str] = {}
        if definiciones:
            for k, v in definiciones.items():
                self.macros[str(k)] = str(v) if v is not None else "1"

        self.limite_profundidad = limite_profundidad
        self.pragma_once_archivos: set[str] = set()
        self.include_stack_paths: list[str] = []
        self.include_stack_display: list[str] = []
        self.cond_stack: list[_CondFrame] = []

    def esta_activo(self) -> bool:
        """Indica si el bloque condicional actual esta emitiendo codigo."""
        return all(frame.activo for frame in self.cond_stack)

    def resolver_ruta_include(
        self,
        nombre_header: str,
        es_sistema: bool,
        dir_archivo_actual: str | None,
    ) -> str | None:
        """
        Resuelve la ruta absoluta de un archivo incluido.
        - Si es "...": busca primero en el directorio del archivo actual, luego en dirs_inclusion y spl/include/.
        - Si es <...>: busca en dirs_inclusion y en spl/include/.
        """
        candidatos = []

        if not es_sistema:
            if dir_archivo_actual and os.path.isdir(dir_archivo_actual):
                candidatos.append(os.path.join(dir_archivo_actual, nombre_header))
            else:
                candidatos.append(os.path.join(os.getcwd(), nombre_header))

        for d in self.dirs_inclusion:
            candidatos.append(os.path.join(d, nombre_header))

        # Directorio de inclusion por defecto: spl/include/
        motor_dir = os.path.dirname(os.path.abspath(__file__))
        repo_root = os.path.dirname(os.path.dirname(motor_dir))
        spl_inc = os.path.join(repo_root, "spl", "include")
        candidatos.append(os.path.join(spl_inc, nombre_header))
        candidatos.append(os.path.join("spl", "include", nombre_header))

        for c in candidatos:
            if os.path.isfile(c):
                return os.path.abspath(c)

        return None

    def expandir_macro(self, nombre: str, expanding: set[str] | None = None) -> str:
        """
        Expande una macro recursivamente evitando bucles infinitos.
        """
        if expanding is None:
            expanding = set()

        if nombre in expanding:
            return nombre

        val = self.macros.get(nombre, nombre)
        if not val:
            return ""

        nuevo_expanding = expanding | {nombre}
        sub_lexer = PreprocesadorLexer()
        sub_lexer.input(val)
        partes = []

        while True:
            tok = sub_lexer.token()
            if not tok:
                break
            if tok.type == 'IDENTIFIER' and tok.value in self.macros and tok.value not in nuevo_expanding:
                partes.append(self.expandir_macro(tok.value, nuevo_expanding))
            else:
                partes.append(tok.value)

        return "".join(partes)

    def expandir_linea_tokens(self, tokens_linea: list[Any]) -> str:
        """
        Reemplaza identificadores con sus valores de macro en una lista de tokens.
        No toca cadenas, caracteres ni numeros.
        """
        resultado = []
        for tok in tokens_linea:
            if tok.type == 'IDENTIFIER' and tok.value in self.macros:
                resultado.append(self.expandir_macro(tok.value))
            else:
                resultado.append(tok.value)
        return "".join(resultado)

    def procesar_archivo(self, ruta: str, display_name: str | None = None) -> tuple[list[str], list[tuple[str, int]]]:
        """Procesa un archivo dado su ruta en disco."""
        ruta_abs = os.path.abspath(ruta)
        nombre_display = display_name or ruta

        if not os.path.isfile(ruta_abs):
            raise PreprocesadorError(nombre_display, 1, f"archivo no encontrado: {nombre_display}")

        canon_path = os.path.realpath(ruta_abs)
        if canon_path in self.pragma_once_archivos:
            return [], []

        try:
            with open(ruta_abs, "r", encoding="utf-8") as f:
                contenido = f.read()
        except UnicodeDecodeError:
            with open(ruta_abs, "r", encoding="latin-1") as f:
                contenido = f.read()

        dir_actual = os.path.dirname(ruta_abs)
        return self.procesar_fuente(
            contenido,
            archivo=nombre_display,
            canon_path=canon_path,
            dir_actual=dir_actual,
        )

    def procesar_fuente(
        self,
        fuente: str,
        archivo: str = "<stdin>",
        canon_path: str | None = None,
        dir_actual: str | None = None,
    ) -> tuple[list[str], list[tuple[str, int]]]:
        """
        Procesa el texto fuente de un archivo o entrada estandar.
        Devuelve (lineas_salida, mapa_lineas).
        """
        real_path = canon_path or (os.path.realpath(archivo) if archivo != "<stdin>" and os.path.exists(archivo) else None)
        directorio_origen = dir_actual or (os.path.dirname(os.path.abspath(archivo)) if archivo != "<stdin>" and os.path.exists(archivo) else None)

        if real_path:
            if real_path in self.include_stack_paths:
                idx = self.include_stack_paths.index(real_path)
                ciclo_display = self.include_stack_display[idx:] + [archivo]
                cadena_ciclo = " -> ".join(ciclo_display)
                raise PreprocesadorError(archivo, 1, f"ciclo de inclusion detectado: {cadena_ciclo}")

            if len(self.include_stack_paths) >= self.limite_profundidad:
                raise PreprocesadorError(
                    archivo, 1, f"limite de profundidad de inclusion excedido ({self.limite_profundidad})"
                )

            self.include_stack_paths.append(real_path)
            self.include_stack_display.append(archivo)

        try:
            return self._ejecutar_lexico(fuente, archivo, real_path, directorio_origen)
        finally:
            if real_path:
                self.include_stack_paths.pop()
                self.include_stack_display.pop()

    def _ejecutar_lexico(
        self,
        fuente: str,
        archivo: str,
        real_path: str | None,
        dir_actual: str | None,
    ) -> tuple[list[str], list[tuple[str, int]]]:
        lex_inst = PreprocesadorLexer()
        lex_inst.input(fuente)

        lineas_salida: list[str] = []
        mapa_lineas: list[tuple[str, int]] = []

        tokens_linea_actual: list[Any] = []
        linea_origen_actual: int = 1

        while True:
            tok = lex_inst.token()
            if not tok:
                break

            # Directiva
            if tok.type == 'DIRECTIVE_START':
                # Si habia tokens acumulados en la linea antes de la directiva, emitirlos
                if tokens_linea_actual and self.esta_activo():
                    linea_proc = self.expandir_linea_tokens(tokens_linea_actual)
                    lineas_salida.append(linea_proc)
                    mapa_lineas.append((archivo, linea_origen_actual))
                    tokens_linea_actual = []

                dir_start_line = tok.lineno
                dir_tokens: list[Any] = []
                while True:
                    dt = lex_inst.token()
                    if not dt or dt.type == 'DIR_END':
                        break
                    dir_tokens.append(dt)

                # Ejecutar directiva
                inc_lineas, inc_mapa = self._ejecutar_directiva(
                    dir_tokens,
                    dir_start_line,
                    archivo,
                    real_path,
                    dir_actual,
                )
                if inc_lineas:
                    lineas_salida.extend(inc_lineas)
                    mapa_lineas.extend(inc_mapa)

                linea_origen_actual = lex_inst.lexer.lineno
                continue

            # Salto de linea
            if tok.type == 'NEWLINE':
                if self.esta_activo():
                    linea_proc = self.expandir_linea_tokens(tokens_linea_actual)
                    lineas_salida.append(linea_proc)
                    mapa_lineas.append((archivo, linea_origen_actual))
                tokens_linea_actual = []
                linea_origen_actual = lex_inst.lexer.lineno
                continue

            # Comentario con saltos de linea (multi-linea)
            if tok.type == 'COMMENT' and '\n' in tok.value:
                nl_partes = tok.value.split('\n')
                if self.esta_activo():
                    # La primera parte termina la linea actual
                    tokens_linea_actual.append(_SimpleToken(type='WHITESPACE', value=nl_partes[0], lineno=tok.lineno, lexpos=tok.lexpos))
                    linea_proc = self.expandir_linea_tokens(tokens_linea_actual)
                    lineas_salida.append(linea_proc)
                    mapa_lineas.append((archivo, linea_origen_actual))
                    tokens_linea_actual = []

                    # Lineas intermedias vacias generadas por el comentario
                    curr_l = linea_origen_actual + 1
                    for p in nl_partes[1:-1]:
                        lineas_salida.append(p)
                        mapa_lineas.append((archivo, curr_l))
                        curr_l += 1

                    # La ultima parte continua en la linea actual
                    tokens_linea_actual.append(_SimpleToken(type='WHITESPACE', value=nl_partes[-1], lineno=tok.lineno, lexpos=tok.lexpos))
                    linea_origen_actual = tok.lineno
                else:
                    tokens_linea_actual = []
                    linea_origen_actual = tok.lineno
                continue

            # Token de codigo normal
            if not tokens_linea_actual:
                linea_origen_actual = tok.lineno
            tokens_linea_actual.append(tok)

        # Verificar comentario de bloque no cerrado
        if lex_inst.lexer.current_state() == 'blockcomment':
            raise PreprocesadorError(archivo, lex_inst.lexer.comment_start_line, "comentario de bloque no cerrado")

        # Emitir ultima linea si no termino con newline
        if tokens_linea_actual and self.esta_activo():
            linea_proc = self.expandir_linea_tokens(tokens_linea_actual)
            lineas_salida.append(linea_proc)
            mapa_lineas.append((archivo, linea_origen_actual))

        return lineas_salida, mapa_lineas

    def _ejecutar_directiva(
        self,
        tokens: list[Any],
        linea: int,
        archivo: str,
        real_path: str | None,
        dir_actual: str | None,
    ) -> tuple[list[str], list[tuple[str, int]]]:
        """
        Ejecuta una directiva preprocesada a partir de sus tokens.
        """
        # Filtrar espacios iniciales
        idx = 0
        while idx < len(tokens) and tokens[idx].type in ('DIR_WHITESPACE', 'WHITESPACE', 'DIR_CONTINUE'):
            idx += 1

        if idx >= len(tokens):
            # Directiva nula (# solo)
            return [], []

        primer_tok = tokens[idx]
        idx += 1

        tipo = primer_tok.type
        val = primer_tok.value

        # Condicionales: #ifdef, #ifndef, #else, #endif
        # Deben procesarse incluso si el bloque actual es inactivo para rastrear anidamiento.
        if tipo == 'DIR_IFDEF' or val == 'ifdef':
            macro_nombre = self._obtener_identificador_arg(tokens, idx, linea, archivo, "ifdef")
            padre_activo = self.esta_activo()
            condicion = (macro_nombre in self.macros)
            activo = padre_activo and condicion
            self.cond_stack.append(_CondFrame('ifdef', activo, condicion, linea, archivo))
            return [], []

        if tipo == 'DIR_IFNDEF' or val == 'ifndef':
            macro_nombre = self._obtener_identificador_arg(tokens, idx, linea, archivo, "ifndef")
            padre_activo = self.esta_activo()
            condicion = (macro_nombre not in self.macros)
            activo = padre_activo and condicion
            self.cond_stack.append(_CondFrame('ifndef', activo, condicion, linea, archivo))
            return [], []

        if tipo == 'DIR_ELSE' or val == 'else':
            if not self.cond_stack:
                raise PreprocesadorError(archivo, linea, "#else sin directiva condicional previa")
            frame = self.cond_stack[-1]
            if frame.tiene_else:
                raise PreprocesadorError(archivo, linea, "#else duplicado para el mismo bloque condicional")
            frame.tiene_else = True
            padre_activo = all(f.activo for f in self.cond_stack[:-1])
            frame.activo = padre_activo and (not frame.cumplido)
            frame.cumplido = True
            return [], []

        if tipo == 'DIR_ENDIF' or val == 'endif':
            if not self.cond_stack:
                raise PreprocesadorError(archivo, linea, "#endif sin directiva condicional previa")
            self.cond_stack.pop()
            return [], []

        # Si el contexto condicional actual es inactivo, ignorar las demas directivas
        if not self.esta_activo():
            return [], []

        # Directivas activas
        if tipo == 'DIR_DEFINE' or val == 'define':
            # Obtener nombre de macro
            while idx < len(tokens) and tokens[idx].type in ('DIR_WHITESPACE', 'WHITESPACE', 'DIR_CONTINUE'):
                idx += 1
            if idx >= len(tokens) or tokens[idx].type not in ('DIR_IDENTIFIER', 'IDENTIFIER'):
                raise PreprocesadorError(archivo, linea, "se esperaba un nombre de macro en #define")

            macro_nombre = tokens[idx].value
            idx += 1

            # Resto de tokens es el valor del macro
            val_tokens = []
            while idx < len(tokens):
                t = tokens[idx]
                if t.type == 'DIR_CONTINUE':
                    val_tokens.append(' ')
                elif t.type in ('DIR_LINE_COMMENT', 'COMMENT'):
                    val_tokens.append(' ')
                elif t.type in ('DIR_WHITESPACE', 'WHITESPACE'):
                    val_tokens.append(' ')
                else:
                    val_tokens.append(t.value)
                idx += 1

            raw_valor = "".join(val_tokens).strip()
            macro_valor = self._normalizar_espacios_macro(raw_valor)
            self.macros[macro_nombre] = macro_valor
            return [], []

        if tipo == 'DIR_UNDEF' or val == 'undef':
            macro_nombre = self._obtener_identificador_arg(tokens, idx, linea, archivo, "undef")
            self.macros.pop(macro_nombre, None)
            return [], []

        if tipo == 'DIR_PRAGMA' or val == 'pragma':
            while idx < len(tokens) and tokens[idx].type in ('DIR_WHITESPACE', 'WHITESPACE', 'DIR_CONTINUE'):
                idx += 1
            if idx < len(tokens) and tokens[idx].value == 'once':
                if real_path:
                    self.pragma_once_archivos.add(real_path)
            return [], []

        if tipo == 'DIR_INCLUDE' or val == 'include':
            while idx < len(tokens) and tokens[idx].type in ('DIR_WHITESPACE', 'WHITESPACE', 'DIR_CONTINUE'):
                idx += 1
            if idx >= len(tokens):
                raise PreprocesadorError(archivo, linea, "sintaxis invalida en #include; se esperaba \"...\" o <...>")

            header_tok = tokens[idx]
            header_str = header_tok.value.strip()

            es_sistema = False
            if (header_tok.type == 'DIR_HEADER_SYS' or header_str.startswith('<')) and header_str.endswith('>'):
                es_sistema = True
                nombre_archivo = header_str[1:-1]
            elif (header_tok.type == 'DIR_HEADER_LOCAL' or header_str.startswith('"')) and header_str.endswith('"'):
                es_sistema = False
                nombre_archivo = header_str[1:-1]
            else:
                raise PreprocesadorError(archivo, linea, f"sintaxis invalida en #include '{header_str}'")

            ruta_resuelta = self.resolver_ruta_include(nombre_archivo, es_sistema, dir_actual)
            if not ruta_resuelta:
                raise PreprocesadorError(archivo, linea, f"archivo no encontrado: {nombre_archivo}")

            return self.procesar_archivo(ruta_resuelta, display_name=nombre_archivo)

        # Directiva desconocida
        nombre_desconocido = val
        raise PreprocesadorError(archivo, linea, f"directiva desconocida '#{nombre_desconocido}'")

    def _normalizar_espacios_macro(self, valor: str) -> str:
        """Normaliza multiples espacios consecutivos fuera de cadenas."""
        if not valor:
            return ""
        if '"' not in valor and "'" not in valor:
            return re.sub(r'[ \t]+', ' ', valor)
        sub_lexer = PreprocesadorLexer()
        sub_lexer.input(valor)
        partes = []
        while True:
            t = sub_lexer.token()
            if not t:
                break
            if t.type == 'WHITESPACE':
                partes.append(' ')
            else:
                partes.append(t.value)
        return "".join(partes)

    def _obtener_identificador_arg(
        self,
        tokens: list[Any],
        idx: int,
        linea: int,
        archivo: str,
        nombre_dir: str,
    ) -> str:
        while idx < len(tokens) and tokens[idx].type in ('DIR_WHITESPACE', 'WHITESPACE', 'DIR_CONTINUE'):
            idx += 1
        if idx >= len(tokens) or tokens[idx].type not in ('DIR_IDENTIFIER', 'IDENTIFIER'):
            raise PreprocesadorError(archivo, linea, f"se esperaba un identificador en #{nombre_dir}")
        return tokens[idx].value


def preprocesar_archivo(
    ruta: str,
    dirs_inclusion: list[str] | None = None,
    definiciones: dict[str, Any] | None = None,
) -> ResultadoPreprocesamiento:
    """
    API principal para preprocesar un archivo en disco.
    """
    pre = Preprocesador(dirs_inclusion=dirs_inclusion, definiciones=definiciones)
    lineas, mapa = pre.procesar_archivo(ruta)

    if pre.cond_stack:
        frame = pre.cond_stack[-1]
        raise PreprocesadorError(frame.archivo, frame.linea, f"directiva condicional #{frame.tipo} sin cerrar (#endif faltante)")

    texto_final = "\n".join(lineas)
    return ResultadoPreprocesamiento(
        texto=texto_final,
        macros=pre.macros,
        mapa_lineas=mapa,
    )


def preprocesar_texto(
    texto: str,
    dirs_inclusion_o_nombre: list[str] | str | None = None,
    definiciones: dict[str, Any] | None = None,
    nombre_archivo: str = "<stdin>",
    dirs_inclusion: list[str] | None = None,
) -> ResultadoPreprocesamiento:
    """
    API principal para preprocesar codigo directamente desde una cadena de texto.
    Soporta firmas:
      - preprocesar_texto(texto)
      - preprocesar_texto(texto, dirs_inclusion=[], definiciones={})
      - preprocesar_texto(texto, nombre_archivo="...", dirs_inclusion=[], definiciones={})
    """
    if isinstance(dirs_inclusion_o_nombre, str):
        archivo = dirs_inclusion_o_nombre
        dirs = dirs_inclusion
    elif isinstance(dirs_inclusion_o_nombre, list):
        dirs = dirs_inclusion_o_nombre
        archivo = nombre_archivo
    else:
        dirs = dirs_inclusion
        archivo = nombre_archivo

    pre = Preprocesador(dirs_inclusion=dirs, definiciones=definiciones)
    lineas, mapa = pre.procesar_fuente(texto, archivo=archivo)

    if pre.cond_stack:
        frame = pre.cond_stack[-1]
        raise PreprocesadorError(frame.archivo, frame.linea, f"directiva condicional #{frame.tipo} sin cerrar (#endif faltante)")

    texto_final = "\n".join(lineas)
    return ResultadoPreprocesamiento(
        texto=texto_final,
        macros=pre.macros,
        mapa_lineas=mapa,
    )
