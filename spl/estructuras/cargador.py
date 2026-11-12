"""
Puente Preprocesador -> Ensamblador -> BinarioEnigma (.e64) -> CargadorEnigma.

Tarea 29 - Integrante 4 (Cargador, Directivas, Cabeceras y Enlace):
  Conecta el preprocesador del SPL (que gestiona #include "estructuras.inc" y
  macros #define) con el ensamblador de dos pasadas de Enigma-64, empaqueta el
  ejecutable estructurado .e64 (firma 'ENIG') y lo deposita en memoria RAM a
  traves de CargadorEnigma con SP alineado a 8 bytes (0x00400000).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

from enigma64.cargador import BinarioEnigma, CargadorEnigma
from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory
from enigma64.perifericos import Perifericos
from enigma64.registros import BancoRegistros
from spl.preprocesador import (
    ResultadoPreprocesamiento,
    preprocesar_archivo,
    preprocesar_texto,
)

from .descriptores import (
    BASE_CODIGO,
    BASE_MATRICES,
    BASE_VECTORES,
    PILA_ESTRUCTURAS,
    ErrorEstructuraDatos,
    EstructuraDescriptor,
    MapaEstructurasRAM,
    validar_alineacion_8,
)
from .memoria import (
    leer_descriptor_de_ram,
    leer_matriz_de_ram,
    leer_vector_de_ram,
    precargar_estructuras_en_ram,
)


def _recolectar_etiquetas_asm(codigo_asm: str, direccion_base: int) -> Dict[str, int]:
    """Recolecta las direcciones de etiquetas del codigo ensamblador expandido para ESTAB."""
    from enigma64.ensamblador import _calcular_longitud

    simbolos: Dict[str, int] = {}
    pc = direccion_base
    for num_linea, linea_orig in enumerate(codigo_asm.splitlines(), 1):
        linea = re.split(r"[#;]", linea_orig)[0].strip()
        if not linea:
            continue
        while ":" in linea:
            etiqueta, resto = linea.split(":", 1)
            etiqueta = etiqueta.strip()
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", etiqueta) and etiqueta not in simbolos:
                simbolos[etiqueta] = pc
            linea = resto.strip()
        if not linea:
            continue
        partes = linea.split(None, 1)
        mnemonico = partes[0].upper()
        ops_str = partes[1] if len(partes) > 1 else ""
        ops: List[str] = []
        if ops_str:
            actual: List[str] = []
            en_corchete = False
            for ch in ops_str:
                if ch == "[":
                    en_corchete = True
                    actual.append(ch)
                elif ch == "]":
                    en_corchete = False
                    actual.append(ch)
                elif ch == "," and not en_corchete:
                    ops.append("".join(actual).strip())
                    actual = []
                else:
                    actual.append(ch)
            if actual:
                ops.append("".join(actual).strip())
        pc += _calcular_longitud(mnemonico, ops, num_linea)
    return simbolos


@dataclass
class ResultadoCompilacionEstructuras:
    """Artefactos producidos por el pipeline Preprocesador -> Ensamblador -> BinarioEnigma."""

    preprocesamiento: ResultadoPreprocesamiento
    codigo_maquina: bytes
    binario_e64: BinarioEnigma
    mapa_estructuras: MapaEstructurasRAM


@dataclass
class ResultadoEjecucionEstructuras:
    """Estado resultante tras cargar con CargadorEnigma y ejecutar en CPU."""

    cpu: CPU
    banco: BancoRegistros
    ram: RAMMemory
    perifericos: Perifericos
    cargador: CargadorEnigma
    binario_e64: BinarioEnigma
    info_carga: Dict[str, Any]
    mapa_estructuras: MapaEstructurasRAM
    texto_preprocesado: str

    @property
    def salida_mmio(self) -> str:
        return self.perifericos.pantalla.obtener_texto()

    def leer_vector(
        self,
        direccion_base: int = BASE_VECTORES,
        longitud: Optional[int] = None,
        modo: str = "int",
    ) -> List[Union[int, float]]:
        return leer_vector_de_ram(
            self.ram, direccion_base=direccion_base, longitud=longitud, modo=modo
        )

    def leer_matriz(
        self,
        direccion_base: int = BASE_MATRICES,
        filas: Optional[int] = None,
        columnas: Optional[int] = None,
        modo: str = "int",
    ) -> List[List[Union[int, float]]]:
        return leer_matriz_de_ram(
            self.ram,
            direccion_base=direccion_base,
            filas=filas,
            columnas=columnas,
            modo=modo,
        )

    def leer_descriptor(self, slot_o_direccion: int) -> Dict[str, int]:
        return leer_descriptor_de_ram(self.ram, slot_o_direccion)


def compilar_a_binario_e64(
    fuente_o_ruta: Union[str, Path],
    *,
    es_archivo: Optional[bool] = None,
    estructuras: Optional[Union[MapaEstructurasRAM, Iterable[EstructuraDescriptor]]] = None,
    dirs_inclusion: Optional[Sequence[str]] = None,
    definiciones: Optional[Dict[str, str]] = None,
    direccion_codigo: int = BASE_CODIGO,
    entry_point: Optional[int] = None,
    incluir_datos_en_imagen: bool = False,
) -> ResultadoCompilacionEstructuras:
    """
    Ejecuta el pipeline:
      1. Preprocesador SPL (resuelve #include "estructuras.inc" y macros #define).
      2. Ensamblador de dos pasadas de Enigma-64 (enigma64.ensamblador.ensamblar).
      3. Construccion de BinarioEnigma (.e64) con firma 'ENIG' y tabla de simbolos.

    Si incluir_datos_en_imagen=True, empaqueta las estructuras registradas dentro del
    segmento .data del ejecutable .e64 para que incluso una carga autonoma mediante
    CargadorEnigma.cargar_archivo() restaure tanto el codigo como los vectores/matrices.
    """
    validar_alineacion_8(direccion_codigo, "direccion_codigo")
    ep = entry_point if entry_point is not None else direccion_codigo

    es_ruta = (
        isinstance(fuente_o_ruta, Path)
        if es_archivo is None
        else es_archivo
    )
    if es_archivo is None and isinstance(fuente_o_ruta, str) and "\n" not in fuente_o_ruta:
        posible = Path(fuente_o_ruta)
        if posible.is_file():
            es_ruta = True

    if es_ruta:
        res_prep = preprocesar_archivo(
            str(fuente_o_ruta),
            dirs_inclusion=list(dirs_inclusion) if dirs_inclusion else None,
            definiciones=definiciones,
        )
    else:
        res_prep = preprocesar_texto(
            str(fuente_o_ruta),
            dirs_inclusion=list(dirs_inclusion) if dirs_inclusion else None,
            definiciones=definiciones,
        )

    codigo_bytes = ensamblar(res_prep.texto, direccion_base=direccion_codigo)
    etiquetas_asm = _recolectar_etiquetas_asm(res_prep.texto, direccion_base=direccion_codigo)

    mapa = (
        estructuras
        if isinstance(estructuras, MapaEstructurasRAM)
        else MapaEstructurasRAM(estructuras)
    )

    fin_codigo = direccion_codigo + len(codigo_bytes)
    segmentos = mapa.todos_los_segmentos()
    for et_seg, ini_seg, _ in segmentos:
        if ini_seg < fin_codigo:
            raise ErrorEstructuraDatos(
                f"El codigo ensamblado [0x{direccion_codigo:08X}, 0x{fin_codigo:08X}) "
                f"colisiona con el segmento '{et_seg}' en 0x{ini_seg:08X}."
            )

    datos_imagen = bytearray()
    if incluir_datos_en_imagen and segmentos:
        max_fin = max(ini + len(b) for _, ini, b in segmentos)
        datos_imagen = bytearray(max_fin - fin_codigo)
        for _, ini_seg, bytes_seg in segmentos:
            despl = ini_seg - fin_codigo
            datos_imagen[despl : despl + len(bytes_seg)] = bytes_seg

    tabla_simbolos: Dict[str, int] = {"_start": ep}
    tabla_simbolos.update(etiquetas_asm)
    tabla_simbolos.update(mapa.tabla_simbolos())

    binario = BinarioEnigma(
        codigo=codigo_bytes,
        datos=datos_imagen,
        direccion_base=direccion_codigo,
        entry_point=ep,
        reubicable=False,
        tabla_reubicacion=[],
        tabla_simbolos=tabla_simbolos,
    )

    return ResultadoCompilacionEstructuras(
        preprocesamiento=res_prep,
        codigo_maquina=codigo_bytes,
        binario_e64=binario,
        mapa_estructuras=mapa,
    )


def exportar_estructuras_e64(
    fuente_o_ruta: Union[str, Path],
    ruta_salida_e64: Union[str, Path],
    *,
    es_archivo: Optional[bool] = None,
    estructuras: Optional[Union[MapaEstructurasRAM, Iterable[EstructuraDescriptor]]] = None,
    dirs_inclusion: Optional[Sequence[str]] = None,
    definiciones: Optional[Dict[str, str]] = None,
    direccion_codigo: int = BASE_CODIGO,
    entry_point: Optional[int] = None,
    incluir_datos_en_imagen: bool = True,
) -> BinarioEnigma:
    """
    Compila un programa con #include "estructuras.inc" y escribe en disco un archivo
    ejecutable estructurado .e64 directamente cargable por CargadorEnigma.
    """
    comp = compilar_a_binario_e64(
        fuente_o_ruta,
        es_archivo=es_archivo,
        estructuras=estructuras,
        dirs_inclusion=dirs_inclusion,
        definiciones=definiciones,
        direccion_codigo=direccion_codigo,
        entry_point=entry_point,
        incluir_datos_en_imagen=incluir_datos_en_imagen,
    )
    ruta_out = Path(ruta_salida_e64)
    ruta_out.parent.mkdir(parents=True, exist_ok=True)
    ruta_out.write_bytes(comp.binario_e64.serializar_e64())
    return comp.binario_e64


def cargar_y_ejecutar_estructuras(
    fuente_o_ruta: Union[str, Path],
    *,
    es_archivo: Optional[bool] = None,
    estructuras: Optional[Union[MapaEstructurasRAM, Iterable[EstructuraDescriptor]]] = None,
    dirs_inclusion: Optional[Sequence[str]] = None,
    definiciones: Optional[Dict[str, str]] = None,
    direccion_codigo: int = BASE_CODIGO,
    entry_point: Optional[int] = None,
    sp_inicial: int = PILA_ESTRUCTURAS,
    max_ciclos: int = 4_000_000,
    ejecutar: bool = True,
    perifericos: Optional[Perifericos] = None,
) -> ResultadoEjecucionEstructuras:
    """
    Conecta de extremo a extremo el pipeline de la Tarea 29:
      Preprocesador -> Ensamblador -> BinarioEnigma -> CargadorEnigma -> RAM/CPU.

    Garantiza:
      - Validacion formal de fronteras de memoria mediante CargadorEnigma.cargar_binario().
      - Alineacion estricta del puntero de pila SP a multiplo de 8 bytes (0x00400000).
      - Precarga alineada de cabeceras, descriptores, vectores y matrices en RAMMemory.
    """
    validar_alineacion_8(sp_inicial, "sp_inicial")

    comp = compilar_a_binario_e64(
        fuente_o_ruta,
        es_archivo=es_archivo,
        estructuras=estructuras,
        dirs_inclusion=dirs_inclusion,
        definiciones=definiciones,
        direccion_codigo=direccion_codigo,
        entry_point=entry_point,
        incluir_datos_en_imagen=False,
    )

    ram = RAMMemory()
    banco = BancoRegistros()
    perif = perifericos if perifericos is not None else Perifericos()
    cpu = CPU(ram=ram, banco=banco, perifericos=perif)
    cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)

    info_carga = cargador.cargar_binario(
        comp.binario_e64,
        direccion_destino=direccion_codigo,
        configurar_cpu=True,
    )

    # Sobreescribir SP_RESET (0xEFFFFFFF, impar) con un SP alineado a 8 bytes
    banco.sp = sp_inicial

    if comp.mapa_estructuras.estructuras:
        precargar_estructuras_en_ram(ram, comp.mapa_estructuras, cargador=cargador)

    if ejecutar:
        cpu.ejecutar(max_ciclos=max_ciclos)

    return ResultadoEjecucionEstructuras(
        cpu=cpu,
        banco=banco,
        ram=ram,
        perifericos=perif,
        cargador=cargador,
        binario_e64=comp.binario_e64,
        info_carga=info_carga,
        mapa_estructuras=comp.mapa_estructuras,
        texto_preprocesado=comp.preprocesamiento.texto,
    )
