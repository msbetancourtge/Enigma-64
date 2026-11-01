"""
Lectura y escritura del modulo objeto en texto (.tobj) - Enigma-64 (Noctua Systems).

leer_objeto_texto recorre los tokens de ObjetoLexer (lexer.py) linea por linea,
como el motor del preprocesador recorre los de su lexer, y arma el mismo
ModuloObjeto que produce la lectura de un .obj binario. escribir_objeto_texto
hace el camino inverso, de modo que ambas representaciones se convierten una
en la otra sin perder informacion.

Gramatica de cada linea (los nombres de seccion y de simbolo se resuelven al
final, asi el orden de los bloques es libre):

    [MODULO]  nombre
    [ENTRADA] seccion [+ offset]
    [SECCION] nombre BITS  permisos ALIN n { byte* }
    [SECCION] nombre VACIA permisos ALIN n TAM n
    [SIMBOLOS]        y debajo, una fila por simbolo:
        nombre (LOCAL | GLOBAL) tipo (seccion | *ABS*) valor
        nombre IMPORTADO tipo
    [REUBICACIONES]   y debajo, una fila por marca:
        seccion offset tipo simbolo [(+ | -) sumando]

Los errores lexicos y los de estructura se acumulan con su linea y columna y se
informan juntos en un solo ObjetoInvalido; la coherencia del modulo resultante
la comprueba ModuloObjeto.validar, igual que para un .obj binario.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .lexer import ESCAPES, NOMBRE, PALABRAS_RESERVADAS, PERMISOS, ErrorLexico, ObjetoLexer
from .objeto import (
    NOMBRE_LIGADURA,
    NOMBRE_REUBICACION,
    NOMBRE_TIPO_SECCION,
    NOMBRE_TIPO_SIMBOLO,
    PERM_EJECUCION,
    PERM_ESCRITURA,
    PERM_LECTURA,
    SECCION_ABSOLUTA,
    SECCION_BITS,
    SECCION_INDEFINIDA,
    SECCION_VACIA,
    MarcaReubicacion,
    ModuloObjeto,
    ObjetoInvalido,
    SeccionObjeto,
    SimboloObjeto,
    texto_permisos,
)

_ENTEROS = ('ENTERO_HEX', 'ENTERO_DEC')

# Nombre -> codigo de cada tabla del formato
_TIPO_SECCION = {nombre: codigo for codigo, nombre in NOMBRE_TIPO_SECCION.items()}
_LIGADURA = {nombre: codigo for codigo, nombre in NOMBRE_LIGADURA.items()}
_TIPO_SIMBOLO = {nombre: codigo for codigo, nombre in NOMBRE_TIPO_SIMBOLO.items()}
_TIPO_REUBICACION = {nombre: codigo for codigo, nombre in NOMBRE_REUBICACION.items()}

# Ningun caracter de control fuera de los escapes cabe en un nombre de texto
_ESCAPE_DE = {caracter: '\\' + letra for letra, caracter in ESCAPES.items()}


@dataclass(frozen=True)
class ErrorSintactico:
    linea: int
    columna: int
    lexema: str
    mensaje: str

    def __str__(self):
        sufijo = f": '{self.lexema}'" if self.lexema else ''
        return (f"ERROR SINTACTICO (linea {self.linea}, columna {self.columna}): "
                f"{self.mensaje}{sufijo}")


ErrorTexto = Union[ErrorLexico, ErrorSintactico]


class _FilaInvalida(Exception):
    def __init__(self, error: ErrorSintactico) -> None:
        super().__init__(str(error))
        self.error = error


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


class _Fila:
    """Tokens de una linea logica (un bloque { } cuenta como parte de su linea)."""

    def __init__(self, tokens: Sequence) -> None:
        self.tokens = tokens
        self.pos = 0

    @property
    def lineas(self) -> range:
        return range(self.tokens[0].lineno, self.tokens[-1].lineno + 1)

    def _fallar(self, tok, mensaje: str):
        raise _FilaInvalida(ErrorSintactico(tok.lineno, tok.columna, tok.value, mensaje))

    def esperar(self, tipos: Union[str, Tuple[str, ...]], que: str, valor: Optional[str] = None):
        tipos = (tipos,) if isinstance(tipos, str) else tipos
        if self.pos >= len(self.tokens):
            ultimo = self.tokens[-1]
            raise _FilaInvalida(ErrorSintactico(
                ultimo.lineno, ultimo.columna + len(ultimo.value), '', f'falta {que}'
            ))
        tok = self.tokens[self.pos]
        if tok.type not in tipos or (valor is not None and tok.value != valor):
            self._fallar(tok, f'se esperaba {que}')
        self.pos += 1
        return tok

    def opcional(self, tipos: Union[str, Tuple[str, ...]], valor: Optional[str] = None):
        tipos = (tipos,) if isinstance(tipos, str) else tipos
        if self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            if tok.type in tipos and (valor is None or tok.value == valor):
                self.pos += 1
                return tok
        return None

    def terminar(self) -> None:
        if self.pos < len(self.tokens):
            self._fallar(self.tokens[self.pos], 'sobra texto al final de la linea')


def _filas(tokens: Sequence) -> List[_Fila]:
    filas, actual = [], []
    for tok in tokens:
        if tok.type == 'FIN_LINEA':
            if actual:
                filas.append(_Fila(actual))
            actual = []
        else:
            actual.append(tok)
    if actual:
        filas.append(_Fila(actual))
    return filas


class _Lector:
    """Arma un ModuloObjeto a partir de las filas; los nombres se resuelven al final."""

    def __init__(self) -> None:
        self.errores: List[ErrorSintactico] = []
        self.tabla: Optional[str] = None
        self.nombre = None
        self.entrada = None
        self.secciones: List[Tuple[SeccionObjeto, object]] = []
        self.simbolos: List[tuple] = []
        self.marcas: List[tuple] = []

    def leer(self, filas: Sequence[_Fila], lineas_con_error_lexico: set) -> None:
        for fila in filas:
            try:
                self._fila(fila)
            except _FilaInvalida as exc:
                # Si el lexer ya informo un error en la fila, el sintactico es su eco
                if not lineas_con_error_lexico.intersection(fila.lineas):
                    self.errores.append(exc.error)

    def _fila(self, fila: _Fila) -> None:
        encabezado = fila.opcional('ENCABEZADO')
        if encabezado is None:
            if self.tabla == 'SIMBOLOS':
                self._simbolo(fila)
            elif self.tabla == 'REUBICACIONES':
                self._marca(fila)
            else:
                fila._fallar(fila.tokens[0], 'fila fuera de una tabla (falta [SIMBOLOS] o '
                                             '[REUBICACIONES] antes de ella)')
            return

        nombre = encabezado.value[1:-1]
        self.tabla = nombre if nombre in ('SIMBOLOS', 'REUBICACIONES') else None
        if nombre == 'MODULO':
            if self.nombre is not None:
                fila._fallar(encabezado, '[MODULO] repetido')
            self.nombre = fila.esperar('NOMBRE', 'el nombre del modulo').nombre
        elif nombre == 'ENTRADA':
            if self.entrada is not None:
                fila._fallar(encabezado, '[ENTRADA] repetida')
            seccion = fila.esperar('NOMBRE', 'la seccion del punto de entrada')
            offset = 0
            if fila.opcional('MAS'):
                offset = fila.esperar(_ENTEROS, 'el offset del punto de entrada').entero
            self.entrada = (seccion, offset)
        elif nombre == 'SECCION':
            self._seccion(fila)
        fila.terminar()

    def _seccion(self, fila: _Fila) -> None:
        nombre = fila.esperar('NOMBRE', 'el nombre de la seccion')
        tipo = _TIPO_SECCION[fila.esperar('TIPO_SECCION', 'el tipo de seccion (BITS o VACIA)').value]
        permisos = _permisos(fila.esperar('PERMISOS', 'el campo de permisos (por ejemplo R-X o RW-)').value)
        fila.esperar('ATRIBUTO', 'ALIN', 'ALIN')
        alineacion = fila.esperar(_ENTEROS, 'la alineacion').entero
        if tipo == SECCION_VACIA:
            fila.esperar('ATRIBUTO', 'TAM (una seccion VACIA declara su tamano)', 'TAM')
            tamano = fila.esperar(_ENTEROS, 'el tamano de la seccion').entero
            seccion = SeccionObjeto(nombre.nombre, b'', permisos, alineacion, tipo, tamano)
        else:
            fila.esperar('LLAVE_IZQ', "'{' con el contenido de la seccion BITS")
            contenido = bytearray()
            while (byte := fila.opcional('BYTE')) is not None:
                contenido.append(byte.entero)
            fila.esperar('LLAVE_DER', "'}'")
            seccion = SeccionObjeto(nombre.nombre, bytes(contenido), permisos, alineacion, tipo)
        self.secciones.append((seccion, nombre))

    def _simbolo(self, fila: _Fila) -> None:
        nombre = fila.esperar('NOMBRE', 'el nombre del simbolo')
        ligadura = fila.esperar('LIGADURA', 'la ligadura (LOCAL, GLOBAL o IMPORTADO)').value
        tipo = _TIPO_SIMBOLO[fila.esperar('TIPO_SIMBOLO', 'el tipo (SIN_TIPO, FUNCION o DATO)').value]
        if ligadura == 'IMPORTADO':
            seccion, valor = None, 0
        else:
            seccion = fila.esperar(('NOMBRE', 'SECCION_ABSOLUTA'), 'la seccion o *ABS*')
            valor = fila.esperar(_ENTEROS, 'el valor del simbolo').entero
        fila.terminar()
        self.simbolos.append((nombre, ligadura, tipo, seccion, valor))

    def _marca(self, fila: _Fila) -> None:
        seccion = fila.esperar('NOMBRE', 'la seccion de la marca')
        offset = fila.esperar(_ENTEROS, 'el offset del campo').entero
        tipo = _TIPO_REUBICACION[
            fila.esperar('TIPO_REUBICACION', 'el tipo de marca (ABS64, ABS32, REL16, HI16 o LO16)').value
        ]
        simbolo = fila.esperar('NOMBRE', 'el simbolo de la marca')
        sumando = 0
        signo = fila.opcional(('MAS', 'MENOS'))
        valor = fila.opcional(_ENTEROS) if signo is None else fila.esperar(_ENTEROS, 'el sumando')
        if valor is not None:
            sumando = -valor.entero if signo is not None and signo.type == 'MENOS' else valor.entero
        fila.terminar()
        self.marcas.append((seccion, offset, tipo, simbolo, sumando))

    # -- resolucion de nombres ------------------------------------------------

    def _no_declarado(self, tok, que: str) -> None:
        self.errores.append(ErrorSintactico(tok.lineno, tok.columna, tok.value, que))

    def modulo(self) -> Optional[ModuloObjeto]:
        indice_seccion: Dict[str, int] = {}
        for indice, (seccion, _) in enumerate(self.secciones):
            indice_seccion.setdefault(seccion.nombre, indice)
        indice_simbolo: Dict[str, int] = {}
        for indice, (nombre, *_resto) in enumerate(self.simbolos):
            indice_simbolo.setdefault(nombre.nombre, indice)

        simbolos = []
        for nombre, ligadura, tipo, seccion, valor in self.simbolos:
            if ligadura == 'IMPORTADO':
                simbolos.append(SimboloObjeto.importado(nombre.nombre, tipo))
                continue
            if seccion.type == 'SECCION_ABSOLUTA':
                indice = SECCION_ABSOLUTA
            elif seccion.nombre in indice_seccion:
                indice = indice_seccion[seccion.nombre]
            else:
                self._no_declarado(seccion, 'seccion no declarada con [SECCION]')
                continue
            simbolos.append(SimboloObjeto(nombre.nombre, indice, valor, _LIGADURA[ligadura], tipo))

        marcas = []
        for seccion, offset, tipo, simbolo, sumando in self.marcas:
            if seccion.nombre not in indice_seccion:
                self._no_declarado(seccion, 'seccion no declarada con [SECCION]')
            elif simbolo.nombre not in indice_simbolo:
                self._no_declarado(simbolo, 'simbolo no declarado en [SIMBOLOS]')
            else:
                marcas.append(MarcaReubicacion(
                    indice_seccion[seccion.nombre], offset, tipo,
                    indice_simbolo[simbolo.nombre], sumando,
                ))

        entrada = None
        if self.entrada is not None:
            seccion, offset = self.entrada
            if seccion.nombre in indice_seccion:
                entrada = (indice_seccion[seccion.nombre], offset)
            else:
                self._no_declarado(seccion, 'seccion no declarada con [SECCION]')

        if self.errores:
            return None
        return ModuloObjeto(
            nombre=self.nombre or '',
            secciones=[seccion for seccion, _ in self.secciones],
            simbolos=simbolos,
            reubicaciones=marcas,
            entrada=entrada,
        )


def analizar_texto(texto: str) -> Tuple[Optional[ModuloObjeto], List[ErrorTexto]]:
    """
    Analiza un modulo objeto en texto. Devuelve (modulo, errores): el modulo es
    None si hubo errores lexicos o sintacticos, y en ese caso la lista los trae
    todos, ordenados por linea y columna. No llama a validar().
    """
    tokens, errores_lexicos = ObjetoLexer().tokenizar(texto)
    lector = _Lector()
    lector.leer(_filas(tokens), {e.linea for e in errores_lexicos})
    errores: List[ErrorTexto] = sorted(
        [*errores_lexicos, *lector.errores], key=lambda e: (e.linea, e.columna)
    )
    if errores:
        return None, errores
    modulo = lector.modulo()
    return modulo, sorted(lector.errores, key=lambda e: (e.linea, e.columna))


def leer_objeto_texto(texto: str) -> ModuloObjeto:
    """
    Analiza un modulo objeto en texto (.tobj) y devuelve el modulo validado.

    :raises ObjetoInvalido: Con todos los errores lexicos y sintacticos en el
        mensaje (y en el atributo errores), o con el primer problema de coherencia.
    """
    modulo, errores = analizar_texto(texto)
    if errores:
        exc = ObjetoInvalido(
            f"Modulo objeto en texto con {len(errores)} error(es):\n"
            + "\n".join(f"  {error}" for error in errores)
        )
        exc.errores = errores
        raise exc
    modulo.validar()
    return modulo


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------


def _permisos(texto: str) -> int:
    return (
        (PERM_LECTURA if texto[0] == 'R' else 0)
        | (PERM_ESCRITURA if texto[1] == 'W' else 0)
        | (PERM_EJECUCION if texto[2] == 'X' else 0)
    )


def _nombre(texto: str) -> str:
    """El nombre tal cual si el lexer lo leeria como NOMBRE; si no, entre comillas."""
    if (re.fullmatch(NOMBRE, texto) and texto not in PALABRAS_RESERVADAS
            and not re.fullmatch(PERMISOS, texto)):
        return texto
    partes = []
    for caracter in texto:
        if caracter in _ESCAPE_DE:
            partes.append(_ESCAPE_DE[caracter])
        elif ord(caracter) < 0x20 or ord(caracter) == 0x7F:
            raise ObjetoInvalido(
                f"El nombre {texto!r} tiene un caracter de control que el formato de "
                f"texto no representa"
            )
        else:
            partes.append(caracter)
    return '"' + ''.join(partes) + '"'


def _columnas(filas: Sequence[Sequence[str]], sangria: str = '') -> List[str]:
    if not filas:
        return []
    anchos = [max(len(fila[i]) for fila in filas if i < len(fila))
              for i in range(max(len(fila) for fila in filas))]
    return [
        (sangria + '  '.join(celda.ljust(anchos[i]) for i, celda in enumerate(fila))).rstrip()
        for fila in filas
    ]


def escribir_objeto_texto(modulo: ModuloObjeto, bytes_por_linea: int = 16) -> str:
    """Escribe el modulo en formato de texto .tobj (valida antes de escribir)."""
    modulo.validar()
    lineas = [
        '; Modulo objeto reubicable de Enigma-64 en formato de texto (.tobj)',
        f'[MODULO] {_nombre(modulo.nombre)}',
    ]
    if modulo.entrada is not None:
        indice, offset = modulo.entrada
        lineas.append(f'[ENTRADA] {_nombre(modulo.secciones[indice].nombre)} + 0x{offset:04X}')

    for sec in modulo.secciones:
        cabecera = (f'[SECCION] {_nombre(sec.nombre)} {NOMBRE_TIPO_SECCION[sec.tipo]} '
                    f'{texto_permisos(sec.permisos)} ALIN {sec.alineacion}')
        lineas.append('')
        if sec.tipo == SECCION_BITS:
            lineas.append(cabecera + ' {')
            for inicio in range(0, len(sec.contenido), bytes_por_linea):
                fragmento = sec.contenido[inicio:inicio + bytes_por_linea]
                lineas.append('    ' + ' '.join(f'{b:02X}' for b in fragmento))
            lineas.append('}')
        else:
            lineas.append(cabecera + f' TAM {sec.tamano}')

    lineas += ['', '[SIMBOLOS]']
    filas = [('; nombre', 'ligadura', 'tipo', 'seccion', 'valor')]
    for sim in modulo.simbolos:
        tipo = NOMBRE_TIPO_SIMBOLO[sim.tipo]
        if sim.seccion == SECCION_INDEFINIDA:
            filas.append((_nombre(sim.nombre), 'IMPORTADO', tipo))
        else:
            seccion = ('*ABS*' if sim.seccion == SECCION_ABSOLUTA
                       else _nombre(modulo.secciones[sim.seccion].nombre))
            filas.append((_nombre(sim.nombre), NOMBRE_LIGADURA[sim.ligadura], tipo,
                          seccion, f'0x{sim.valor:04X}'))
    lineas += _columnas(filas)

    lineas += ['', '[REUBICACIONES]']
    filas = [('; seccion', 'offset', 'tipo', 'simbolo', 'sumando')]
    for marca in modulo.reubicaciones:
        filas.append((
            _nombre(modulo.secciones[marca.seccion].nombre), f'0x{marca.offset:04X}',
            NOMBRE_REUBICACION[marca.tipo], _nombre(modulo.simbolos[marca.simbolo].nombre),
            f'{marca.sumando:+d}',
        ))
    lineas += _columnas(filas)
    return '\n'.join(lineas) + '\n'
