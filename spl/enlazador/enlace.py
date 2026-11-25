"""
Enlazador de Modulos Objeto - Enigma-64 (Noctua Systems).

Segunda mitad del modulo Enlazador-Cargador. Recibe modulos objeto ya analizados
(spl.enlazador.objeto) y sigue el esquema clasico del cargador-enlazador de
dos pasadas:

  Pasada 1 - Asignacion: ubica cada seccion en el espacio de usuario respetando
  su alineacion (primero el codigo, luego los datos y al final las reservas
  .bss) y construye la tabla global de simbolos (ESTAB) con las exportaciones.

  Pasada 2 - Enlace y reubicacion: resuelve cada importacion contra la ESTAB y
  aplica las marcas de reubicacion sobre la imagen de memoria, verificando que
  el valor quepa en el campo de la instruccion.

El resultado es un BinarioEnigma absoluto que CargadorEnigma deposita en la RAM
con sus validaciones de frontera de siempre (enlazar_y_cargar).

El mapa de enlace dice respecto de que base se mide cada direccion (la base de
carga para las secciones, la base de la seccion para los simbolos y los campos
parchados, y el PC de la instruccion siguiente para REL16) y trae el mapa de
direcciones reubicadas; formatear_binario_bits() da la imagen en 0 y 1.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from enigma64.cargador import (
    MAX_PHYSICAL_ADDR,
    USER_MEM_START,
    BinarioEnigma,
    CargadorEnigma,
    DireccionInvalida,
)
from enigma64.registros import MASK64
from .binario import FORMULA_REUBICACION, bits, formatear_enlace_bits
from .objeto import (
    ANCHO_REUBICACION,
    NOMBRE_REUBICACION,
    PERM_EJECUCION,
    REUB_ABS32,
    REUB_ABS64,
    REUB_HI16,
    REUB_LO16,
    REUB_REL16,
    SECCION_BITS,
    ErrorEnlazador,
    FuenteObjeto,
    ModuloObjeto,
    SimboloObjeto,
    _formatear_tabla,
    analizar_objeto,
    texto_permisos,
)

# Primera direccion que la secuencia ADDI/SHL 16/ADDI ya no puede construir:
# ADDI extiende el signo de su inmediato, asi que la parte alta ajustada debe
# quedar en 0x0000-0x7FFF.
LIMITE_HI16: int = 0x7FFF8000


# ---------------------------------------------------------------------------
# Excepciones del enlace
# ---------------------------------------------------------------------------


class SimboloNoDefinido(ErrorEnlazador):
    """Una importacion (o el punto de entrada pedido) no la exporta ningun modulo."""

    def __init__(self, mensaje: str, faltantes: Optional[Dict[str, List[str]]] = None) -> None:
        super().__init__(mensaje)
        # simbolo -> modulos que lo importan
        self.faltantes: Dict[str, List[str]] = dict(faltantes or {})


class SimboloDuplicado(ErrorEnlazador):
    """Dos modulos exportan el mismo simbolo global."""


class DesbordamientoReubicacion(ErrorEnlazador):
    """El valor reubicado no cabe en el campo que indica la marca."""


# ---------------------------------------------------------------------------
# 1. Formulas de reubicacion
# ---------------------------------------------------------------------------


def calcular_parche(tipo: int, direccion_simbolo: int, sumando: int, direccion_campo: int) -> bytes:
    """
    Calcula los bytes (Big-Endian) que una marca de reubicacion escribe en memoria.

    :param tipo: REUB_ABS64, REUB_ABS32, REUB_REL16, REUB_HI16 o REUB_LO16.
    :param direccion_simbolo: S, direccion final del simbolo referenciado.
    :param sumando: A, sumando de la marca.
    :param direccion_campo: P, direccion final del primer byte del campo.
    :raises DesbordamientoReubicacion: Si el resultado no cabe en el campo.
    """
    objetivo = direccion_simbolo + sumando
    if tipo == REUB_ABS64:
        _exigir_rango(objetivo, 0, MASK64, "ABS64", "la direccion")
        return objetivo.to_bytes(8, "big")
    if tipo == REUB_ABS32:
        _exigir_rango(objetivo, 0, MAX_PHYSICAL_ADDR, "ABS32", "la direccion")
        return objetivo.to_bytes(4, "big")
    if tipo == REUB_REL16:
        # El desplazamiento se mide desde la instruccion siguiente, que empieza
        # justo despues del campo de 2 bytes (formato relativo de 3 bytes).
        desplazamiento = objetivo - (direccion_campo + 2)
        _exigir_rango(desplazamiento, -0x8000, 0x7FFF, "REL16", "el desplazamiento")
        return (desplazamiento & 0xFFFF).to_bytes(2, "big")
    if tipo == REUB_HI16:
        _exigir_rango(objetivo, 0, LIMITE_HI16 - 1, "HI16", "la direccion")
        return (((objetivo + 0x8000) >> 16) & 0xFFFF).to_bytes(2, "big")
    if tipo == REUB_LO16:
        _exigir_rango(objetivo, 0, MAX_PHYSICAL_ADDR, "LO16", "la direccion")
        return (objetivo & 0xFFFF).to_bytes(2, "big")
    raise ErrorEnlazador(f"Tipo de marca de reubicacion desconocido: {tipo}")


def _exigir_rango(valor: int, minimo: int, maximo: int, tipo: str, que: str) -> None:
    if not minimo <= valor <= maximo:
        raise DesbordamientoReubicacion(
            f"{que} {valor:#x} no cabe en un campo {tipo} "
            f"(rango {minimo:#x} a {maximo:#x})"
        )


# ---------------------------------------------------------------------------
# 2. Resultado del enlace
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class UbicacionSeccion:
    """Donde quedo una seccion de un modulo dentro de la imagen enlazada."""

    modulo: str
    seccion: str
    direccion: int
    tamano: int
    permisos: int
    tipo: int


@dataclass(frozen=True)
class ReubicacionAplicada:
    """
    Una marca ya resuelta: que campo se parcho, contra que simbolo y con que
    bytes. offset es relativo al inicio de la seccion que se parcha, cuya
    direccion final es base_seccion; P = base_seccion + offset.
    """

    modulo: str
    seccion: str
    base_seccion: int
    offset: int
    tipo: int
    simbolo: str
    direccion_simbolo: int
    sumando: int
    valor: bytes

    @property
    def direccion_campo(self) -> int:
        """P: direccion final del primer byte del campo parchado."""
        return self.base_seccion + self.offset

    @property
    def ancho(self) -> int:
        return ANCHO_REUBICACION[self.tipo]

    @property
    def nombre_tipo(self) -> str:
        return NOMBRE_REUBICACION[self.tipo]

    @property
    def pc_siguiente(self) -> int:
        """Base de un REL16: PC de la instruccion siguiente (P + 2 = inicio + 3)."""
        return self.direccion_campo + 2

    @property
    def desplazamiento(self) -> int:
        """Valor con signo escrito en un campo REL16."""
        valor = int.from_bytes(self.valor, "big")
        return valor - 0x10000 if valor & 0x8000 else valor


@dataclass
class ResultadoEnlace:
    """Ejecutable absoluto, mapa de secciones y tabla global de simbolos (ESTAB)."""

    binario: BinarioEnigma
    mapa: List[UbicacionSeccion]
    simbolos: Dict[str, int]
    origen_simbolos: Dict[str, str]
    reubicaciones_aplicadas: int
    # Mapa de direcciones reubicadas, en el orden en que se aplicaron
    detalle_reubicaciones: List[ReubicacionAplicada] = field(default_factory=list)
    # Seccion donde quedo cada simbolo de la ESTAB (None: constante absoluta)
    ubicacion_simbolos: Dict[str, Optional[UbicacionSeccion]] = field(default_factory=dict)

    @property
    def direccion_base(self) -> int:
        return self.binario.direccion_base

    @property
    def entry_point(self) -> int:
        return self.binario.entry_point

    @property
    def tamano_total(self) -> int:
        return self.binario.tamano_total

    def _relativo_simbolo(self, nombre: str, direccion: int) -> str:
        ubicacion = self.ubicacion_simbolos.get(nombre)
        if ubicacion is None:
            return "constante absoluta (no se reubica)" if nombre in self.ubicacion_simbolos else "-"
        return (f"{ubicacion.seccion} de {ubicacion.modulo} (0x{ubicacion.direccion:08X}) "
                f"+ 0x{direccion - ubicacion.direccion:04X}")

    def informe(self) -> str:
        """Mapa de enlace legible (al estilo de ld -Map)."""
        lineas = [
            f"Mapa de enlace: base 0x{self.direccion_base:08X}, {self.tamano_total} bytes, "
            f"entrada 0x{self.entry_point:08X}",
        ]
        lineas += _formatear_tabla(
            ("Direccion", "Tamano", "Perm", "Seccion", "Modulo", "Relativa a la base de carga"),
            [
                (f"0x{u.direccion:08X}", str(u.tamano), texto_permisos(u.permisos),
                 u.seccion, u.modulo, f"0x{self.direccion_base:08X} + 0x{u.direccion - self.direccion_base:04X}")
                for u in self.mapa
            ],
        )
        lineas += ["", f"Tabla global de simbolos (ESTAB): {len(self.simbolos)}"]
        lineas += _formatear_tabla(
            ("Direccion", "Simbolo", "Modulo", "Relativa a la base de su seccion"),
            [
                (f"0x{direccion:08X}", nombre, self.origen_simbolos[nombre],
                 self._relativo_simbolo(nombre, direccion))
                for nombre, direccion in sorted(
                    self.simbolos.items(), key=lambda par: (par[1], par[0])
                )
            ],
        )
        lineas += ["", f"Marcas de reubicacion aplicadas: {self.reubicaciones_aplicadas}"]
        if self.detalle_reubicaciones:
            lineas += ["", "Mapa de direcciones reubicadas (P = campo parchado, S = simbolo, A = sumando)"]
            lineas += _formatear_tabla(
                ("P", "Campo relativo a su seccion", "Tipo", "Simbolo", "S", "A", "Formula",
                 "Escrito", "Base del valor"),
                [
                    (
                        f"0x{a.direccion_campo:08X}",
                        f"{a.seccion} de {a.modulo} (0x{a.base_seccion:08X}) + 0x{a.offset:04X}",
                        a.nombre_tipo, a.simbolo, f"0x{a.direccion_simbolo:08X}", f"{a.sumando:+d}",
                        FORMULA_REUBICACION[a.tipo], bits(a.valor),
                        (f"{a.desplazamiento:+d} B desde el PC siguiente 0x{a.pc_siguiente:08X}"
                         if a.tipo == REUB_REL16 else "absoluta"),
                    )
                    for a in self.detalle_reubicaciones
                ],
            )
        return "\n".join(lineas)

    def formatear_binario_bits(self) -> str:
        """Imagen enlazada en 0 y 1 por instruccion y por palabra (ver binario.py)."""
        return formatear_enlace_bits(self)


# ---------------------------------------------------------------------------
# 3. Motor del Enlazador (EnlazadorEnigma)
# ---------------------------------------------------------------------------


class EnlazadorEnigma:
    """
    Enlazador de modulos objeto de Enigma-64.

    Uso:
        enlazador = EnlazadorEnigma(["principal.obj", "libmat.obj"])
        resultado = enlazador.enlazar(direccion_base=0x00200000)
        cargador.cargar_binario(resultado.binario)

    o en un solo paso, enlazando directamente en la direccion de carga:
        enlazador.enlazar_y_cargar(cargador, direccion_destino=0x00200000)
    """

    def __init__(self, modulos: Optional[Sequence[FuenteObjeto]] = None) -> None:
        self.modulos: List[ModuloObjeto] = []
        for fuente in modulos or ():
            self.agregar(fuente)

    def agregar(self, fuente: FuenteObjeto) -> ModuloObjeto:
        """Analiza y agrega un modulo (ModuloObjeto, bytes de un .obj o ruta)."""
        modulo = analizar_objeto(fuente)
        self.modulos.append(modulo)
        return modulo

    def enlazar(
        self,
        direccion_base: int = USER_MEM_START,
        entrada: Optional[str] = None,
    ) -> ResultadoEnlace:
        """
        Enlaza los modulos agregados para ejecutarse a partir de direccion_base.

        :param direccion_base: Direccion fisica donde empezara la imagen.
        :param entrada: Simbolo exportado que sera el punto de entrada. Si se omite
            se usa el que declare un modulo o, si ninguno lo hace, el inicio del codigo.
        :raises SimboloNoDefinido: Si queda alguna importacion sin resolver.
        :raises SimboloDuplicado: Si dos modulos exportan el mismo simbolo.
        :raises DesbordamientoReubicacion: Si un valor no cabe en su campo.
        :raises DireccionInvalida: Si la imagen sale de los 4 GiB fisicos.
        """
        if not self.modulos:
            raise ErrorEnlazador("No hay modulos objeto que enlazar")
        for modulo in self.modulos:
            modulo.validar()
        if not 0 <= direccion_base <= MAX_PHYSICAL_ADDR:
            raise DireccionInvalida(
                f"Direccion base fuera de los 4 GiB fisicos: 0x{direccion_base:X}"
            )

        # Pasada 1: asignacion de direcciones y tabla global de simbolos
        mapa, direcciones, fin = self._asignar_direcciones(direccion_base)
        if fin - 1 > MAX_PHYSICAL_ADDR:
            raise DireccionInvalida(
                f"La imagen enlazada termina en 0x{fin - 1:X}, fuera de los 4 GiB fisicos"
            )
        estab, origen, secciones_estab = self._construir_estab(direcciones)
        self._verificar_importaciones(estab)

        # Pasada 2: imagen de memoria y reubicacion
        imagen = bytearray(fin - direccion_base)  # las reservas .bss quedan en cero
        for (i, j), direccion in direcciones.items():
            seccion = self.modulos[i].secciones[j]
            if seccion.tipo == SECCION_BITS:
                inicio = direccion - direccion_base
                imagen[inicio : inicio + seccion.tamano] = seccion.contenido
        detalle = self._reubicar(imagen, direccion_base, direcciones, estab)

        entry_point = self._punto_de_entrada(entrada, estab, direcciones, mapa, direccion_base)

        # El codigo va hasta la primera seccion que no es codigo; el resto son datos
        corte = next(
            (u.direccion for u in mapa if not _es_codigo(u.tipo, u.permisos)), fin
        ) - direccion_base
        binario = BinarioEnigma(
            codigo=imagen[:corte],
            datos=imagen[corte:],
            direccion_base=direccion_base,
            entry_point=entry_point,
            reubicable=False,
            tabla_simbolos=estab,
        )
        # _asignar_direcciones llena 'direcciones' y 'mapa' en el mismo orden
        por_indice = dict(zip(direcciones, mapa))
        ubicacion_simbolos = {
            nombre: (None if indices is None else por_indice[indices])
            for nombre, indices in secciones_estab.items()
        }
        return ResultadoEnlace(
            binario, mapa, estab, origen, len(detalle), detalle, ubicacion_simbolos
        )

    def enlazar_y_cargar(
        self,
        cargador: CargadorEnigma,
        direccion_destino: int = USER_MEM_START,
        entrada: Optional[str] = None,
        configurar_cpu: bool = True,
    ) -> Dict[str, Any]:
        """
        Cargador-enlazador: enlaza en la direccion de carga y deposita la imagen en
        RAM con CargadorEnigma, que aplica las fronteras del mapa de memoria.

        :return: Los metadatos de cargar_binario mas los del enlace.
        """
        resultado = self.enlazar(direccion_destino, entrada)
        metadatos = cargador.cargar_binario(resultado.binario, configurar_cpu=configurar_cpu)
        metadatos.update(
            {
                "modulos": [modulo.nombre for modulo in self.modulos],
                "simbolos": dict(resultado.simbolos),
                "mapa": list(resultado.mapa),
                "reubicaciones_aplicadas": resultado.reubicaciones_aplicadas,
            }
        )
        return metadatos

    # -- pasada 1 -----------------------------------------------------------

    def _asignar_direcciones(
        self, direccion_base: int
    ) -> Tuple[List[UbicacionSeccion], Dict[Tuple[int, int], int], int]:
        """
        Ordena las secciones por clase (codigo, datos, reservas); dentro de cada
        clase agrupa las del mismo nombre en orden de aparicion y respeta el
        orden de los modulos. Devuelve el mapa, la direccion de cada seccion
        (modulo, seccion) y la primera direccion libre tras la imagen.
        """
        orden_nombres: Dict[str, int] = {}
        pendientes = []
        for i, modulo in enumerate(self.modulos):
            for j, seccion in enumerate(modulo.secciones):
                orden = orden_nombres.setdefault(seccion.nombre, len(orden_nombres))
                pendientes.append((seccion.clase, orden, i, j))
        pendientes.sort()

        mapa: List[UbicacionSeccion] = []
        direcciones: Dict[Tuple[int, int], int] = {}
        cursor = direccion_base
        for _clase, _orden, i, j in pendientes:
            modulo = self.modulos[i]
            seccion = modulo.secciones[j]
            direccion = _alinear(cursor, seccion.alineacion)
            direcciones[(i, j)] = direccion
            mapa.append(UbicacionSeccion(
                modulo.nombre, seccion.nombre, direccion, seccion.tamano,
                seccion.permisos, seccion.tipo,
            ))
            cursor = direccion + seccion.tamano
        return mapa, direcciones, cursor

    def _construir_estab(
        self, direcciones: Dict[Tuple[int, int], int]
    ) -> Tuple[Dict[str, int], Dict[str, str], Dict[str, Optional[Tuple[int, int]]]]:
        """
        ESTAB, modulo que exporta cada simbolo y la seccion que lo define como
        (indice de modulo, indice de seccion); None para una constante absoluta.
        """
        estab: Dict[str, int] = {}
        origen: Dict[str, str] = {}
        secciones: Dict[str, Optional[Tuple[int, int]]] = {}
        for i, modulo in enumerate(self.modulos):
            for simbolo in modulo.exportaciones:
                if simbolo.nombre in estab:
                    raise SimboloDuplicado(
                        f"El simbolo global '{simbolo.nombre}' lo exportan "
                        f"'{origen[simbolo.nombre]}' y '{modulo.nombre}'"
                    )
                estab[simbolo.nombre] = _direccion_definida(i, simbolo, direcciones)
                origen[simbolo.nombre] = modulo.nombre
                secciones[simbolo.nombre] = None if simbolo.es_absoluto else (i, simbolo.seccion)
        return estab, origen, secciones

    def _verificar_importaciones(self, estab: Dict[str, int]) -> None:
        faltantes: Dict[str, List[str]] = {}
        for modulo in self.modulos:
            for simbolo in modulo.importaciones:
                if simbolo.nombre not in estab:
                    faltantes.setdefault(simbolo.nombre, []).append(modulo.nombre)
        if faltantes:
            detalle = "; ".join(
                f"'{nombre}' (importado por {', '.join(modulos)})"
                for nombre, modulos in sorted(faltantes.items())
            )
            raise SimboloNoDefinido(f"Importaciones sin resolver: {detalle}", faltantes)

    # -- pasada 2 -----------------------------------------------------------

    def _reubicar(
        self,
        imagen: bytearray,
        direccion_base: int,
        direcciones: Dict[Tuple[int, int], int],
        estab: Dict[str, int],
    ) -> List[ReubicacionAplicada]:
        aplicadas: List[ReubicacionAplicada] = []
        for i, modulo in enumerate(self.modulos):
            for marca in modulo.reubicaciones:
                simbolo = modulo.simbolos[marca.simbolo]
                if simbolo.es_importacion:
                    direccion_simbolo = estab[simbolo.nombre]
                else:
                    direccion_simbolo = _direccion_definida(i, simbolo, direcciones)
                direccion_campo = direcciones[(i, marca.seccion)] + marca.offset
                try:
                    parche = calcular_parche(
                        marca.tipo, direccion_simbolo, marca.sumando, direccion_campo
                    )
                except DesbordamientoReubicacion as exc:
                    seccion = modulo.secciones[marca.seccion]
                    raise DesbordamientoReubicacion(
                        f"Modulo '{modulo.nombre}', {marca.nombre_tipo} en "
                        f"{seccion.nombre}+0x{marca.offset:X} contra '{simbolo.nombre}': {exc}"
                    ) from None
                inicio = direccion_campo - direccion_base
                imagen[inicio : inicio + marca.ancho] = parche
                aplicadas.append(ReubicacionAplicada(
                    modulo=modulo.nombre,
                    seccion=modulo.secciones[marca.seccion].nombre,
                    base_seccion=direcciones[(i, marca.seccion)],
                    offset=marca.offset,
                    tipo=marca.tipo,
                    simbolo=simbolo.nombre,
                    direccion_simbolo=direccion_simbolo,
                    sumando=marca.sumando,
                    valor=parche,
                ))
        return aplicadas

    def _punto_de_entrada(
        self,
        entrada: Optional[str],
        estab: Dict[str, int],
        direcciones: Dict[Tuple[int, int], int],
        mapa: List[UbicacionSeccion],
        direccion_base: int,
    ) -> int:
        if entrada is not None:
            if entrada not in estab:
                raise SimboloNoDefinido(
                    f"El punto de entrada '{entrada}' no lo exporta ningun modulo",
                    {entrada: ["(punto de entrada)"]},
                )
            return estab[entrada]

        declarados = [(i, m) for i, m in enumerate(self.modulos) if m.entrada is not None]
        if len(declarados) > 1:
            nombres = ", ".join(f"'{m.nombre}'" for _, m in declarados)
            raise ErrorEnlazador(
                f"Varios modulos declaran punto de entrada ({nombres}); "
                f"indique cual usar con 'entrada'"
            )
        if declarados:
            i, modulo = declarados[0]
            seccion, offset = modulo.entrada
            return direcciones[(i, seccion)] + offset

        # Sin declaracion: el programa arranca en la primera seccion de codigo
        for ubicacion in mapa:
            if _es_codigo(ubicacion.tipo, ubicacion.permisos) and ubicacion.tamano:
                return ubicacion.direccion
        return direccion_base


def _alinear(direccion: int, alineacion: int) -> int:
    return (direccion + alineacion - 1) & ~(alineacion - 1)


def _es_codigo(tipo: int, permisos: int) -> bool:
    return tipo == SECCION_BITS and bool(permisos & PERM_EJECUCION)


def _direccion_definida(
    indice_modulo: int,
    simbolo: SimboloObjeto,
    direcciones: Dict[Tuple[int, int], int],
) -> int:
    if simbolo.es_absoluto:
        return simbolo.valor
    return direcciones[(indice_modulo, simbolo.seccion)] + simbolo.valor
