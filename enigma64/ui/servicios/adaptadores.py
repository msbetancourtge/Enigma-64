"""
Adaptadores hacia los modulos de hardware escritos por el equipo.

Cada adaptador envuelve el modulo de un companero y lo expone con la forma que
espera la interfaz. Toda la asimetria entre lo que un panel quiere y lo que el
modulo ofrece se resuelve aqui, en un unico sitio, de manera que:

  * los modulos de `enigma64/` no se modifican nunca;
  * si un modulo cambia de firma, solo hay que tocar su adaptador;
  * si un modulo no se puede importar, el adaptador queda marcado como no
    disponible y el panel lo informa en pantalla en vez de caerse.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import math
import pathlib
import re
from fractions import Fraction
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .puertos import (
    FASES_FSM, MICRO_REGISTROS, ServicioBase, ServicioNoDisponible,
)

# ---------------------------------------------------------------------------
# Importacion defensiva de los modulos del equipo
# ---------------------------------------------------------------------------

try:
    from ...memoria import (  # type: ignore
        PAGE_SIZE, STATUS_ADDR_FAULT, STATUS_MISALIGNED, STATUS_MMIO,
        STATUS_READY, VALID_SIZES, RAMMemory,
    )
    _FALLO_MEMORIA = ""
except Exception as exc:  # pragma: no cover - solo si falta el modulo
    RAMMemory = None  # type: ignore
    PAGE_SIZE, VALID_SIZES = 4096, frozenset({1, 2, 4, 8})
    STATUS_READY, STATUS_ADDR_FAULT = "READY", "ADDR_FAULT"
    STATUS_MMIO, STATUS_MISALIGNED = "MMIO", "MISALIGNED"
    _FALLO_MEMORIA = f"{type(exc).__name__}: {exc}"

try:
    from ...registros import (  # type: ignore
        ALIAS_ROL, NOMBRE_POR_CODIGO, ORDEN_BANDERAS, BancoRegistros,
    )
    _FALLO_REGISTROS = ""
except Exception as exc:  # pragma: no cover
    BancoRegistros = None  # type: ignore
    NOMBRE_POR_CODIGO, ALIAS_ROL = {}, {}
    ORDEN_BANDERAS = ("Z", "N", "C", "V", "M", "I", "S")
    _FALLO_REGISTROS = f"{type(exc).__name__}: {exc}"

try:
    from ...alu import ALU, OPERACIONES_UNARIAS, TABLA_OPERACIONES  # type: ignore
    _FALLO_ALU = ""
except Exception as exc:  # pragma: no cover
    ALU = None  # type: ignore
    TABLA_OPERACIONES, OPERACIONES_UNARIAS = {}, frozenset()
    _FALLO_ALU = f"{type(exc).__name__}: {exc}"

try:
    from ...cargador import (  # type: ignore
        USER_MEM_START, byte_a_cadena_bits, conmutar_bit, escribir_bit,
        leer_bit, CargadorEnigma,
    )
    _FALLO_CARGADOR = ""
except Exception as exc:  # pragma: no cover
    CargadorEnigma = None  # type: ignore
    USER_MEM_START = 0x00200000
    _FALLO_CARGADOR = f"{type(exc).__name__}: {exc}"

try:
    from ...fpu import CODIGO_FPU_ASM, EmuladorFPUEnigma64  # type: ignore
    _FALLO_FPU = ""
except Exception as exc:  # pragma: no cover
    EmuladorFPUEnigma64 = None  # type: ignore
    CODIGO_FPU_ASM = ""
    _FALLO_FPU = f"{type(exc).__name__}: {exc}"

from .mapa_memoria import REGIONES
from ..core.formato import (
    MASCARA_64, bits_a_flotante, campos_ieee754, clasificar_ieee754, con_signo,
    flotante_a_bits, hex64, texto_flotante,
)
from .algoritmos import (
    CATALOGO as CATALOGO_ALGORITMOS,
    codigo_maquina as codigo_maquina_algoritmo,
    obtener as obtener_algoritmo,
)
from .mmio import (
    CONTROLADORES as CONTROLADORES_MMIO,
    BancoMMIOProvisional,
    descomponer as descomponer_mmio,
    registros_de as registros_mmio,
)


# ---------------------------------------------------------------------------
# Memoria RAM y buses (Integrante 1)
# ---------------------------------------------------------------------------


class AdaptadorMemoria(ServicioBase):
    """Envuelve `enigma64.memoria.RAMMemory`."""

    nombre = "Memoria RAM y buses"
    modulo = "enigma64.memoria"

    SENALES = (STATUS_READY, STATUS_MISALIGNED, STATUS_MMIO, STATUS_ADDR_FAULT)

    def __init__(self, ram: Optional[Any] = None) -> None:
        if ram is None and RAMMemory is not None:
            ram = RAMMemory()
        super().__init__(disponible=ram is not None, motivo=_FALLO_MEMORIA)
        self.ram = ram

    def leer(self, direccion: int, tamano: int, verificar_alineacion: bool = True
             ) -> Tuple[Optional[int], str]:
        self.exigir()
        return self.ram.mem_read(direccion, tamano, check_alignment=verificar_alineacion)

    def escribir(self, direccion: int, valor: int, tamano: int,
                 verificar_alineacion: bool = True) -> Tuple[Optional[int], str]:
        self.exigir()
        return self.ram.mem_write(direccion, valor, tamano,
                                  check_alignment=verificar_alineacion)

    def leer_byte(self, direccion: int) -> int:
        """Lectura de un byte para el volcado hexadecimal; nunca lanza."""
        if not self.disponible:
            return 0
        dato, estado = self.ram.mem_read(direccion, 1, check_alignment=False)
        return dato if estado == STATUS_READY and dato is not None else 0

    def escribir_byte(self, direccion: int, valor: int) -> Tuple[Optional[int], str]:
        """Escribe un byte directamente sin verificacion de alineacion."""
        self.exigir()
        return self.ram.mem_write(direccion, valor & 0xFF, 1, check_alignment=False)

    def leer_bit(self, direccion: int, bit_index: int) -> int:
        """Lee el valor (0 o 1) del bit indicado dentro del byte."""
        b = self.leer_byte(direccion)
        return (b >> bit_index) & 1

    def escribir_bit(self, direccion: int, bit_index: int, valor: int) -> int:
        """Escribe 0 o 1 en el bit indicado de la direccion y devuelve el nuevo byte."""
        b = self.leer_byte(direccion)
        if valor:
            b |= (1 << bit_index)
        else:
            b &= ~(1 << bit_index)
        self.escribir_byte(direccion, b)
        return b

    def conmutar_bit(self, direccion: int, bit_index: int) -> int:
        """Invierte el bit indicado en la memoria y devuelve el nuevo estado del bit."""
        b = self.leer_byte(direccion)
        b ^= (1 << bit_index)
        self.escribir_byte(direccion, b)
        return (b >> bit_index) & 1

    def reiniciar(self) -> None:
        self.exigir()
        self.ram.reset()

    def estadisticas(self) -> Dict[str, Any]:
        if not self.disponible:
            return {"paginas": 0, "bytes": 0, "tamano_pagina": PAGE_SIZE}
        return {
            "paginas": len(self.ram.pages),
            "bytes": self.ram.allocated_bytes,
            "tamano_pagina": self.ram.page_size,
            "bloques": self.ram.allocated_blocks,
        }

    def senales(self) -> Sequence[str]:
        return self.SENALES

    def tamanos_validos(self) -> Sequence[int]:
        return sorted(VALID_SIZES)


# ---------------------------------------------------------------------------
# Banco de registros (Integrante 2)
# ---------------------------------------------------------------------------


class AdaptadorRegistros(ServicioBase):
    """Envuelve `enigma64.registros.BancoRegistros`."""

    nombre = "Banco de registros"
    modulo = "enigma64.registros"

    def __init__(self, banco: Optional[Any] = None) -> None:
        if banco is None and BancoRegistros is not None:
            banco = BancoRegistros()
        super().__init__(disponible=banco is not None, motivo=_FALLO_REGISTROS)
        self.banco = banco

    def instantanea(self) -> Dict[str, Any]:
        if not self.disponible:
            return {"registros": {}, "banderas": {}}
        return self.banco.snapshot()

    def escribir_nombre(self, nombre: str, valor: int) -> None:
        self.exigir()
        self.banco.escribir_nombre(nombre, valor)

    def leer_nombre(self, nombre: str) -> int:
        self.exigir()
        return self.banco.leer_nombre(nombre)

    def alternar_bandera(self, bandera: str) -> int:
        """Invierte una bandera del SR y devuelve su nuevo valor."""
        self.exigir()
        nuevo = 0 if self.banco.leer_bandera(bandera) else 1
        self.banco.escribir_bandera(bandera, nuevo)
        return nuevo

    def reiniciar(self) -> None:
        self.exigir()
        self.banco.reset()

    def suscribir(self, callback: Callable[[], None]) -> None:
        """
        El banco notifica pasandose a si mismo; la interfaz no necesita ese
        argumento, asi que se descarta aqui y no en cada panel.
        """
        if self.disponible:
            self.banco.suscribir(lambda _banco: callback())

    def nombres(self) -> Sequence[str]:
        return tuple(NOMBRE_POR_CODIGO.values())

    def alias(self, nombre: str) -> Optional[str]:
        for codigo, nom in NOMBRE_POR_CODIGO.items():
            if nom == nombre:
                return ALIAS_ROL.get(codigo)
        return None

    def banderas(self) -> Sequence[str]:
        return tuple(ORDEN_BANDERAS)

    def es_solo_lectura(self, nombre: str) -> bool:
        """R0 esta cableado a cero: la interfaz lo muestra como no editable."""
        return nombre.upper() == "R0"


# ---------------------------------------------------------------------------
# ALU (Integrante 2)
# ---------------------------------------------------------------------------


class AdaptadorALU(ServicioBase):
    """Envuelve `enigma64.alu.ALU`."""

    nombre = "Unidad aritmetico-logica"
    modulo = "enigma64.alu"

    #: Agrupacion de la tabla del ISA, para ordenar el selector de la interfaz.
    FAMILIAS = {
        "Aritmeticas": ("ADD", "SUB", "MUL", "DIV", "ADDI", "SUBI", "INC", "DEC"),
        "Logicas": ("AND", "OR", "XOR", "NOT"),
        "Desplazamientos": ("SHL", "SHR", "ASR"),
        "Comparacion": ("CMP",),
    }

    def __init__(self, alu: Optional[Any] = None,
                 registros: Optional[AdaptadorRegistros] = None) -> None:
        if alu is None and ALU is not None:
            alu = ALU()
        super().__init__(disponible=alu is not None, motivo=_FALLO_ALU)
        self.alu = alu
        self.registros = registros

    def operaciones(self) -> Sequence[str]:
        return tuple(sorted(TABLA_OPERACIONES))

    def operaciones_por_familia(self) -> Dict[str, Sequence[str]]:
        soportadas = set(self.operaciones())
        return {
            familia: tuple(op for op in ops if op in soportadas)
            for familia, ops in self.FAMILIAS.items()
        }

    def es_unaria(self, operacion: str) -> bool:
        return operacion.upper() in OPERACIONES_UNARIAS

    def banderas_afectadas(self, operacion: str) -> Sequence[str]:
        entrada = TABLA_OPERACIONES.get(operacion.upper())
        return tuple(sorted(entrada[1])) if entrada else ()

    def ejecutar(self, operacion: str, a: int, b: int = 0,
                 volcar_sr: bool = False) -> Dict[str, Any]:
        """
        Ejecuta una operacion y devuelve el resultado ya normalizado.

        Si `volcar_sr` esta activo y hay un banco conectado, las banderas se
        escriben en el SR igual que haria la fase EXECUTE de la maquina de
        estados.
        """
        self.exigir()
        puede_volcar = (
            volcar_sr and self.registros is not None and self.registros.disponible
        )
        if puede_volcar:
            resultado = self.alu.ejecutar_y_volcar(operacion, a, b, self.registros.banco)
        else:
            resultado = self.alu.ejecutar(operacion, a, b)

        return {
            "operacion": operacion.upper(),
            "valor": resultado.valor,
            "hex": resultado.hex,
            "con_signo": resultado.con_signo,
            "banderas": dict(resultado.banderas),
            "afectadas": tuple(sorted(resultado.afectadas)),
            "escribe_destino": resultado.escribe_destino,
            "volcado_sr": puede_volcar,
        }


# ---------------------------------------------------------------------------
# Cargador y manipulacion de bits (Integrante 4)
# ---------------------------------------------------------------------------


class AdaptadorCargador(ServicioBase):
    """Envuelve `enigma64.cargador.CargadorEnigma` y sus utilidades de bits."""

    nombre = "Cargador y manipulador de bits"
    modulo = "enigma64.cargador"

    DIRECCION_USUARIO = USER_MEM_START

    def __init__(self, cargador: Optional[Any] = None,
                 memoria: Optional[AdaptadorMemoria] = None,
                 registros: Optional[AdaptadorRegistros] = None) -> None:
        self.memoria = memoria
        self.registros = registros
        if cargador is None and CargadorEnigma is not None:
            cargador = CargadorEnigma(
                ram=memoria.ram if memoria is not None else None,
                banco=registros.banco if registros is not None else None,
            )
        super().__init__(disponible=cargador is not None, motivo=_FALLO_CARGADOR)
        self.cargador = cargador

    # -- carga de programas -------------------------------------------------

    def cargar_archivo(self, ruta: str, destino: Optional[int] = None,
                       configurar_cpu: bool = True) -> Dict[str, Any]:
        self.exigir()
        return self.cargador.cargar_archivo(ruta, direccion_destino=destino,
                                            configurar_cpu=configurar_cpu)

    def cargar_texto(self, texto: str, destino: int = USER_MEM_START,
                     punto_entrada: Optional[int] = None,
                     configurar_cpu: bool = True) -> Dict[str, Any]:
        self.exigir()
        return self.cargador.cargar_texto(texto, direccion_destino=destino,
                                          entry_point=punto_entrada,
                                          configurar_cpu=configurar_cpu)

    def cargar_bytes(self, datos: bytes, destino: int = USER_MEM_START,
                     punto_entrada: Optional[int] = None,
                     configurar_cpu: bool = True) -> Dict[str, Any]:
        self.exigir()
        return self.cargador.cargar_bytes(datos, direccion_destino=destino,
                                          entry_point=punto_entrada,
                                          configurar_cpu=configurar_cpu)

    def validar_limites(self, destino: int, tamano: int) -> None:
        """Lanza la excepcion del cargador si el rango invade region protegida."""
        self.exigir()
        self.cargador.validar_limites(destino, tamano)

    # -- manipulacion bit a bit --------------------------------------------

    def _ram(self):
        if self.memoria is None or not self.memoria.disponible:
            raise RuntimeError("El manipulador de bits necesita el modulo de memoria.")
        return self.memoria.ram

    def leer_bit(self, direccion: int, indice: int) -> int:
        self.exigir()
        return leer_bit(self._ram(), direccion, indice)

    def escribir_bit(self, direccion: int, indice: int, valor: int) -> None:
        self.exigir()
        escribir_bit(self._ram(), direccion, indice, valor)

    def conmutar_bit(self, direccion: int, indice: int) -> int:
        self.exigir()
        return conmutar_bit(self._ram(), direccion, indice)

    def byte_en_bits(self, direccion: int) -> str:
        self.exigir()
        return byte_a_cadena_bits(self._ram(), direccion)

    # -- mapa ---------------------------------------------------------------

    def regiones(self) -> List[Dict[str, Any]]:
        return list(REGIONES)


# ---------------------------------------------------------------------------
# Unidad de Control / CPU (Integrante 3) - modulo pendiente
# ---------------------------------------------------------------------------

#: Nombres de clase que se prueban al buscar la CPU dentro de `enigma64.cpu`.
_CLASES_CPU = ("CPU", "UnidadControl", "UnidadDeControl", "ControlUnit", "Procesador")

#: Equivalencias aceptadas para cada operacion del contrato.
_ALIAS_CPU = {
    "paso": ("paso", "step", "ciclo", "tick", "paso_fase"),
    "paso_instruccion": ("paso_instruccion", "step_instruction", "instruccion",
                         "siguiente_instruccion", "step_over"),
    "ejecutar": ("ejecutar", "run", "correr", "ejecutar_todo"),
    "reiniciar": ("reiniciar", "reset", "reinicializar"),
    "estado": ("estado", "state", "snapshot", "instantanea"),
}

try:
    from ... import cpu as _modulo_cpu  # type: ignore
    _FALLO_CPU = ""
except Exception as exc:
    _modulo_cpu = None  # type: ignore
    _FALLO_CPU = (
        f"{type(exc).__name__}: {exc}. El modulo enigma64/cpu.py todavia no "
        f"existe; lo escribe el Integrante 3."
    )


class AdaptadorCPU(ServicioBase):
    """
    Envuelve la Unidad de Control cuando exista `enigma64/cpu.py`.

    Se escribio antes que el modulo a proposito: asi el Integrante 3 tiene un
    contrato contra el que programar (`puertos.PuertoCPU`) y la interfaz ya
    esta lista para recibirlo. Hasta entonces queda no disponible y el panel
    lo explica en pantalla.

    El enganche es por pato: se buscan varios nombres de clase y, para cada
    operacion, varios nombres de metodo. Si el Integrante 3 escribe `step()`
    en vez de `paso()`, sigue funcionando.
    """

    nombre = "Unidad de Control (FSM)"
    modulo = "enigma64.cpu"

    FASES = FASES_FSM
    MICRO = MICRO_REGISTROS

    def __init__(self, cpu: Optional[Any] = None,
                 memoria: Optional["AdaptadorMemoria"] = None,
                 registros: Optional["AdaptadorRegistros"] = None) -> None:
        self.memoria = memoria
        self.registros = registros

        if cpu is None and _modulo_cpu is not None:
            cpu = self._instanciar()

        motivo = _FALLO_CPU
        if cpu is None and not motivo:
            motivo = (
                f"enigma64/cpu.py existe pero no expone ninguna clase conocida "
                f"({', '.join(_CLASES_CPU)}). Ver puertos.PuertoCPU."
            )
        super().__init__(disponible=cpu is not None, motivo=motivo)
        self.cpu = cpu

    def _instanciar(self) -> Optional[Any]:
        """Busca la clase de la CPU y la construye con el hardware conectado."""
        for nombre_clase in _CLASES_CPU:
            clase = getattr(_modulo_cpu, nombre_clase, None)
            if clase is None:
                continue
            ram = self.memoria.ram if self.memoria is not None else None
            banco = self.registros.banco if self.registros is not None else None
            # Se prueban las firmas mas probables, de la mas completa a la mas simple.
            for intento in (
                lambda: clase(ram=ram, banco=banco),
                lambda: clase(ram, banco),
                lambda: clase(ram),
                lambda: clase(),
            ):
                try:
                    return intento()
                except TypeError:
                    continue
        return None

    def _metodo(self, operacion: str):
        """Resuelve el metodo real detras de un nombre del contrato."""
        for alias in _ALIAS_CPU[operacion]:
            metodo = getattr(self.cpu, alias, None)
            if callable(metodo):
                return metodo
        return None

    # -- contrato -----------------------------------------------------------

    def fases(self) -> Sequence[str]:
        return self.FASES

    def micro_registros(self) -> Sequence[str]:
        return self.MICRO

    def _invocar(self, operacion: str, *args) -> Dict[str, Any]:
        self.exigir()
        metodo = self._metodo(operacion)
        if metodo is None:
            raise ServicioNoDisponible(
                f"La CPU no implementa '{operacion}'. Nombres aceptados: "
                f"{', '.join(_ALIAS_CPU[operacion])}."
            )
        metodo(*args)
        return self.estado()

    def paso(self) -> Dict[str, Any]:
        return self._invocar("paso")

    def paso_instruccion(self) -> Dict[str, Any]:
        return self._invocar("paso_instruccion")

    def ejecutar(self, max_ciclos: int = 100000) -> Dict[str, Any]:
        return self._invocar("ejecutar", max_ciclos)

    def reiniciar(self) -> None:
        if not self.disponible:
            return
        metodo = self._metodo("reiniciar")
        if metodo is not None:
            metodo()

    def estado(self) -> Dict[str, Any]:
        """
        Estado normalizado de la FSM. Rellena lo que falte con valores neutros
        para que el panel nunca tenga que comprobar si una clave existe.
        """
        crudo: Dict[str, Any] = {}
        if self.disponible:
            metodo = self._metodo("estado")
            if metodo is not None:
                try:
                    crudo = dict(metodo() or {})
                except Exception as exc:  # pragma: no cover - CPU de terceros
                    crudo = {"error": f"{type(exc).__name__}: {exc}"}

        micro = dict(crudo.get("micro") or {})
        return {
            "fase": crudo.get("fase") or self.FASES[0],
            "ciclos": int(crudo.get("ciclos") or 0),
            "instrucciones": int(crudo.get("instrucciones") or 0),
            "detenido": bool(crudo.get("detenido", False)),
            "micro": {nombre: int(micro.get(nombre) or 0) for nombre in self.MICRO},
            "mnemonico": crudo.get("mnemonico") or "",
            "prefetch": crudo.get("prefetch") or b"",
            "error": crudo.get("error", ""),
        }


# ---------------------------------------------------------------------------
# Perifericos mapeados en memoria
# ---------------------------------------------------------------------------

try:
    from ... import perifericos as _modulo_perifericos  # type: ignore
except Exception:
    _modulo_perifericos = None  # type: ignore


class AdaptadorMMIO(ServicioBase):
    """
    Envuelve el espacio de I/O mapeada.

    Prefiere `enigma64.perifericos` si alguien lo escribe; mientras tanto usa
    el banco provisional de `servicios/mmio.py`, de modo que el visor/editor ya
    se puede usar y demostrar. `es_provisional` dice cual de los dos esta
    detras, para que el panel lo advierta con honestidad.
    """

    nombre = "I/O mapeada en memoria"
    modulo = "enigma64.perifericos"

    def __init__(self, banco: Optional[Any] = None,
                 memoria: Optional["AdaptadorMemoria"] = None) -> None:
        self.memoria = memoria
        self.es_provisional = False

        if banco is None and _modulo_perifericos is not None:
            for nombre_clase in ("Perifericos", "ControladoresMMIO", "BancoMMIO", "MMIO"):
                clase = getattr(_modulo_perifericos, nombre_clase, None)
                if clase is not None:
                    try:
                        banco = clase()
                        break
                    except TypeError:
                        continue

        if banco is None or getattr(banco, "es_provisional", False):
            if banco is None:
                banco = BancoMMIOProvisional()
            self.es_provisional = True

        super().__init__(disponible=True, motivo="")
        self.banco = banco

    @property
    def controlador_pantalla(self) -> Optional[Any]:
        """Devuelve el controlador de pantalla si el modulo de hardware lo expone."""
        if hasattr(self.banco, "controlador_pantalla"):
            return self.banco.controlador_pantalla
        if hasattr(self.banco, "pantalla"):
            return self.banco.pantalla
        return None

    # -- contrato -----------------------------------------------------------

    def controladores(self) -> List[Dict[str, Any]]:
        return list(CONTROLADORES_MMIO)

    def registros(self, clave: str) -> List[Tuple[int, str, str]]:
        return registros_mmio(clave)

    def leer(self, base: int, desplazamiento: int) -> int:
        return self.banco.leer(base, desplazamiento)

    def escribir(self, base: int, desplazamiento: int, valor: int) -> None:
        self.banco.escribir(base, desplazamiento, valor)

    def reiniciar(self) -> None:
        self.banco.reiniciar()

    def descomponer(self, direccion: int):
        """Parte una direccion MMIO en (controlador, desplazamiento, registro)."""
        return descomponer_mmio(direccion)

    @property
    def advertencia(self) -> str:
        """Texto que el panel muestra si detras hay un andamio y no hardware."""
        if not self.es_provisional:
            return ""
        return ("Banco de registros provisional: la RAM enruta 0xFF...... al bus "
                "de perifericos sin almacenar nada. Se reemplaza solo en cuanto "
                "exista enigma64/perifericos.py.")


# ---------------------------------------------------------------------------
# Algoritmos de verificacion (Tarea 9)
# ---------------------------------------------------------------------------


class AdaptadorAlgoritmos(ServicioBase):
    """
    Servicio compuesto para los tres algoritmos de verificacion.

    Sembrar los datos, cargar el codigo y comprobar el resultado toca a la RAM,
    al cargador y (cuando exista) a la CPU. En vez de dar tres servicios al
    panel y romper la regla de "un panel, un servicio", la composicion se hace
    aqui y el panel sigue recibiendo uno solo.
    """

    nombre = "Algoritmos de verificacion"
    modulo = "enigma64.ui.servicios.algoritmos"

    def __init__(self, memoria: Optional["AdaptadorMemoria"] = None,
                 cargador: Optional["AdaptadorCargador"] = None,
                 registros: Optional["AdaptadorRegistros"] = None,
                 cpu: Optional["AdaptadorCPU"] = None) -> None:
        self.memoria = memoria
        self.cargador = cargador
        self.registros = registros
        self.cpu = cpu

        faltan = [
            nombre for nombre, servicio in (("memoria", memoria), ("cargador", cargador))
            if servicio is None or not servicio.disponible
        ]
        super().__init__(
            disponible=not faltan,
            motivo=f"faltan los modulos: {', '.join(faltan)}" if faltan else "",
        )

    # -- catalogo -----------------------------------------------------------

    def catalogo(self) -> List[Dict[str, Any]]:
        return list(CATALOGO_ALGORITMOS)

    def obtener(self, clave: str) -> Optional[Dict[str, Any]]:
        return obtener_algoritmo(clave)

    def codigo_maquina(self, algoritmo: Dict[str, Any]) -> bytes:
        return codigo_maquina_algoritmo(algoritmo)

    # -- preparacion --------------------------------------------------------

    def sembrar_datos(self, algoritmo: Dict[str, Any]) -> List[Tuple[int, int]]:
        """
        Escribe en RAM los valores de entrada del algoritmo.

        Devuelve la lista de (direccion, valor) sembrados, para que el panel
        pueda mostrarlos sin volver a leer la memoria.
        """
        self.exigir()
        sembrados = []
        for direccion, valor, ancho in algoritmo["entradas"]:
            _, estado = self.memoria.escribir(direccion, valor, ancho)
            if estado != STATUS_READY:
                raise RuntimeError(
                    f"No se pudo sembrar {hex64(valor)} en 0x{direccion:08X}: {estado}")
            sembrados.append((direccion, valor))
        return sembrados

    def cargar(self, algoritmo: Dict[str, Any]) -> Dict[str, Any]:
        """Siembra los datos y deposita el codigo maquina en su direccion base."""
        self.exigir()
        self.sembrar_datos(algoritmo)
        return self.cargador.cargar_bytes(
            self.codigo_maquina(algoritmo),
            destino=algoritmo["base"],
            punto_entrada=algoritmo["base"],
            configurar_cpu=True,
        )

    # -- verificacion -------------------------------------------------------

    def verificar(self, algoritmo: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lee el resultado del algoritmo en RAM y lo compara con lo que dice el
        documento. Fibonacci compara la secuencia entera, no un solo valor.
        """
        self.exigir()
        esperado = algoritmo["resultado"]
        secuencia = esperado.get("secuencia")

        if secuencia is not None:
            obtenidos = []
            for indice in range(len(secuencia)):
                direccion = esperado["direccion"] + indice * esperado["tamano"]
                valor, estado = self.memoria.leer(direccion, esperado["tamano"])
                obtenidos.append(valor if estado == STATUS_READY else None)
            return {
                "ok": obtenidos == list(secuencia),
                "obtenido": obtenidos,
                "esperado": list(secuencia),
                "direccion": esperado["direccion"],
                "etiqueta": esperado["etiqueta"],
                "es_secuencia": True,
            }

        valor, estado = self.memoria.leer(esperado["direccion"], esperado["tamano"])
        return {
            "ok": estado == STATUS_READY and valor == esperado["esperado"],
            "obtenido": valor,
            "esperado": esperado["esperado"],
            "direccion": esperado["direccion"],
            "etiqueta": esperado["etiqueta"],
            "estado_bus": estado,
            "es_secuencia": False,
        }

    # -- ejecucion ----------------------------------------------------------

    @property
    def puede_ejecutar(self) -> bool:
        """La ejecucion real necesita la Unidad de Control del Integrante 3."""
        return self.cpu is not None and self.cpu.disponible

    def ejecutar(self, max_ciclos: int = 100000) -> Dict[str, Any]:
        if not self.puede_ejecutar:
            raise ServicioNoDisponible(
                "Ejecutar un algoritmo necesita la Unidad de Control "
                "(enigma64/cpu.py, Integrante 3). Mientras tanto se puede "
                "cargar el programa y revisarlo en el volcado de memoria."
            )
        return self.cpu.ejecutar(max_ciclos)


# ---------------------------------------------------------------------------
# Unidad de punto flotante (biblioteca FPU en ensamblador de Enigma-64)
# ---------------------------------------------------------------------------

#: Raiz del repositorio, para detectar las entregas que aun estan en camino.
_RAIZ_REPOSITORIO = pathlib.Path(__file__).resolve().parents[3]


class AdaptadorFPU(ServicioBase):
    """
    Envuelve `enigma64.fpu.EmuladorFPUEnigma64`.

    La FPU del equipo no es aritmetica de Python: son subrutinas en
    ensamblador de Enigma-64 que corren sobre la CPU del proyecto. El emulador
    de la FPU trae su propia RAM y su propia CPU, asi que una operacion de
    punto flotante nunca pisa la memoria ni los registros de la maquina
    compartida.

    Cada operacion entra por la tabla de vectores canonica (`VEC_FADD`, ...),
    que es el punto de enlace que publico el Integrante 4.

    El catalogo incluye tambien las rutinas que todavia no se entregaron. Una
    rutina queda conectada sola en cuanto su etiqueta aparece en el
    ensamblador de la biblioteca; hasta entonces el panel la muestra como
    pendiente y solo ensena el valor de referencia.
    """

    nombre = "Unidad de punto flotante"
    modulo = "enigma64.fpu"

    #: Presupuesto de ciclos por llamada; el mismo que usa el emulador del equipo.
    MAX_CICLOS = 50000

    #: clave -> descripcion. `etiquetas` son los puntos de entrada candidatos,
    #: del preferido al menos preferido.
    CATALOGO: Dict[str, Dict[str, Any]] = {
        "FADD": {
            "simbolo": "+", "familia": "Aritmeticas", "unaria": False,
            "entrada": "flotante", "salida": "flotante",
            "etiquetas": ("VEC_FADD", "FADD"), "autor": "Integrante 1",
            "descripcion": "Suma con alineacion de mantisas y renormalizacion",
        },
        "FSUB": {
            "simbolo": "-", "familia": "Aritmeticas", "unaria": False,
            "entrada": "flotante", "salida": "flotante",
            "etiquetas": ("VEC_FSUB", "FSUB"), "autor": "Integrante 1",
            "descripcion": "Resta: A + (-B)",
        },
        "FMUL": {
            "simbolo": "x", "familia": "Aritmeticas", "unaria": False,
            "entrada": "flotante", "salida": "flotante",
            "etiquetas": ("VEC_FMUL", "FMUL"), "autor": "Integrante 2",
            "descripcion": "Producto de 106 bits con redondeo al par",
        },
        "FDIV": {
            "simbolo": "/", "familia": "Aritmeticas", "unaria": False,
            "entrada": "flotante", "salida": "flotante",
            "etiquetas": ("VEC_FDIV", "FDIV"), "autor": "Integrante 3",
            "descripcion": "Division larga de mantisas con guarda y pegajoso",
        },
        "FSQRT": {
            "simbolo": "sqrt", "familia": "Aritmeticas", "unaria": True,
            "entrada": "flotante", "salida": "flotante",
            "etiquetas": ("VEC_FSQRT", "FSQRT", "FPU_FSQRT", "FPU_SQRT",
                          "FPU_RAIZ", "FRAIZ"),
            "autor": "Integrante 6",
            "descripcion": "Raiz cuadrada",
        },
        "FCMP": {
            "simbolo": "?", "familia": "Comparacion", "unaria": False,
            "entrada": "flotante", "salida": "orden",
            "etiquetas": ("VEC_FCMP", "FCMP"), "autor": "Integrante 3",
            "descripcion": "Comparacion quieta: -1, 0, 1 o 2 (sin orden)",
        },
        "I2F": {
            "simbolo": "int->float", "familia": "Conversiones", "unaria": True,
            "entrada": "entero", "salida": "flotante",
            "etiquetas": ("VEC_INT_TO_FLOAT", "FPU_INT_TO_FLOAT"),
            "autor": "Integrante 4",
            "descripcion": "Entero de 64 bits con signo a binary64",
        },
        "F2I": {
            "simbolo": "float->int", "familia": "Conversiones", "unaria": True,
            "entrada": "flotante", "salida": "entero",
            "etiquetas": ("VEC_FLOAT_TO_INT", "FPU_FLOAT_TO_INT"),
            "autor": "Integrante 4",
            "descripcion": "binary64 a entero de 64 bits, truncando hacia cero",
        },
    }

    FAMILIAS = ("Aritmeticas", "Comparacion", "Conversiones")

    #: Lo que significa cada codigo que FCMP deja en R5.
    ORDEN_FCMP = {
        MASCARA_64: "A < B", 0: "A = B", 1: "A > B", 2: "sin orden (NaN)",
    }

    #: Entregas que no son una rutina de la biblioteca: se detectan por los
    #: archivos que traen. (clave, titulo, autor, patrones de archivo)
    ENTREGAS = (
        ("oraculo", "Oraculo", "Integrante 6",
         ("enigma64/*oracul*.py", "tests/*oracul*.py")),
        ("brun", "Constante de Brun", "Integrante 7",
         ("programas/*brun*", "enigma64/*brun*")),
        ("bateria", "Bateria de pruebas", "Integrante 7",
         ("tests/*brun*.py", "tests/*bateria*.py")),
    )

    def __init__(self, emulador: Optional[Any] = None,
                 codigo_asm: Optional[str] = None,
                 raiz: Optional[pathlib.Path] = None) -> None:
        if emulador is None and EmuladorFPUEnigma64 is not None:
            emulador = EmuladorFPUEnigma64()
        super().__init__(disponible=emulador is not None, motivo=_FALLO_FPU)
        self.emulador = emulador
        self.raiz = raiz if raiz is not None else _RAIZ_REPOSITORIO
        codigo = CODIGO_FPU_ASM if codigo_asm is None else codigo_asm
        self._etiquetas_asm = set(
            re.findall(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*:", codigo, re.MULTILINE)
        )

    # -- catalogo -----------------------------------------------------------

    def operaciones(self) -> Sequence[str]:
        return tuple(self.CATALOGO)

    def operaciones_por_familia(self) -> Dict[str, Sequence[str]]:
        return {
            familia: tuple(clave for clave, datos in self.CATALOGO.items()
                           if datos["familia"] == familia)
            for familia in self.FAMILIAS
        }

    def descripcion(self, operacion: str) -> Dict[str, Any]:
        clave = operacion.upper()
        if clave not in self.CATALOGO:
            raise ValueError(f"operacion de la FPU desconocida: {operacion!r}")
        datos = dict(self.CATALOGO[clave])
        datos["clave"] = clave
        datos["punto_entrada"] = self.punto_entrada(clave)
        datos["conectada"] = datos["punto_entrada"] is not None
        return datos

    def punto_entrada(self, operacion: str) -> Optional[str]:
        """Etiqueta por la que se llama a la rutina, o None si aun no existe."""
        for etiqueta in self.CATALOGO[operacion.upper()]["etiquetas"]:
            if etiqueta in self._etiquetas_asm:
                return etiqueta
        return None

    def esta_conectada(self, operacion: str) -> bool:
        return self.disponible and self.punto_entrada(operacion) is not None

    def es_unaria(self, operacion: str) -> bool:
        return bool(self.CATALOGO[operacion.upper()]["unaria"])

    def hoja_de_ruta(self) -> List[Dict[str, Any]]:
        """
        Estado de cada pieza de la FPU: las rutinas de la biblioteca y las
        entregas que la acompanan. Es lo que pinta el panel para que se vea de
        un vistazo que esta conectado y que falta.
        """
        piezas = [
            {
                "clave": clave, "titulo": clave, "autor": datos["autor"],
                "conectada": self.esta_conectada(clave),
            }
            for clave, datos in self.CATALOGO.items()
        ]
        for clave, titulo, autor, patrones in self.ENTREGAS:
            piezas.append({
                "clave": clave, "titulo": titulo, "autor": autor,
                "conectada": self._hay_archivos(patrones) or (
                    clave == "brun" and any("BRUN" in e.upper()
                                            for e in self._etiquetas_asm)),
            })
        return piezas

    def _hay_archivos(self, patrones: Sequence[str]) -> bool:
        try:
            return any(any(self.raiz.glob(patron)) for patron in patrones)
        except OSError:  # pragma: no cover - disco no accesible
            return False

    # -- descomposicion IEEE 754 --------------------------------------------

    def descomponer(self, patron: int) -> Dict[str, Any]:
        """
        Separa un patron binary64 en sus campos ejecutando FPU_DESEMPAQUETAR
        en la CPU de Enigma-64. La mantisa que devuelve la rutina ya trae el
        bit implicito en la posicion 52.
        """
        self.exigir()
        patron &= MASCARA_64
        signo, exponente, mantisa = self.emulador.desempaquetar(patron)
        campos = campos_ieee754(patron)
        clase = clasificar_ieee754(patron)
        # En ceros y subnormales el exponente efectivo es 1 - sesgo, no 0 - sesgo.
        exponente_real = None
        if clase in ("normal", "subnormal"):
            exponente_real = (exponente if exponente else 1) - 1023
        return {
            "patron": patron,
            "hex": hex64(patron),
            "signo": signo,
            "exponente": exponente,
            "mantisa": mantisa,
            "fraccion": campos["fraccion"],
            "implicito": (mantisa >> 52) & 1,
            "exponente_real": exponente_real,
            "clase": clase,
            "texto": texto_flotante(patron),
            "ciclos": self._ciclos(),
        }

    # -- ejecucion ----------------------------------------------------------

    def ejecutar(self, operacion: str, a: int, b: int = 0) -> Dict[str, Any]:
        """
        Ejecuta una rutina de la FPU sobre patrones de 64 bits.

        `a` y `b` son siempre patrones crudos: un binary64 para las entradas
        flotantes y un entero en complemento a 2 para INT -> FLOAT.

        El resultado trae ademas el valor de referencia calculado con la
        aritmetica IEEE 754 del anfitrion, para poder contrastar la rutina.
        Si la rutina aun no se entrego, `conectada` es False, `resultado` es
        None y solo viaja la referencia.
        """
        self.exigir()
        datos = self.descripcion(operacion)
        clave = datos["clave"]
        a &= MASCARA_64
        b = 0 if datos["unaria"] else b & MASCARA_64

        referencia = self._referencia(clave, a, b)
        salida: Dict[str, Any] = {
            "operacion": clave,
            "simbolo": datos["simbolo"],
            "autor": datos["autor"],
            "unaria": datos["unaria"],
            "tipo_entrada": datos["entrada"],
            "tipo_salida": datos["salida"],
            "a": a,
            "b": b,
            "conectada": datos["conectada"],
            "punto_entrada": datos["punto_entrada"],
            "resultado": None,
            "hex": "",
            "texto": "",
            "ciclos": 0,
            "referencia": referencia,
            "texto_referencia": (
                "" if referencia is None
                else self._texto_salida(datos["salida"], referencia)),
            "coincide": None,
            "inexacto": None,
        }
        if not datos["conectada"]:
            return salida

        resultado = self.emulador.ejecutar_vector(datos["punto_entrada"], a, b)
        if not self._se_detuvo():
            raise RuntimeError(
                f"{clave} no termino en {self.MAX_CICLOS} ciclos de reloj")
        resultado &= MASCARA_64

        salida.update({
            "resultado": resultado,
            "hex": hex64(resultado),
            "texto": self._texto_salida(datos["salida"], resultado),
            "ciclos": self._ciclos(),
            "coincide": self._coinciden(datos["salida"], resultado, referencia),
            "inexacto": self._es_inexacto(clave, a, b, resultado),
        })
        return salida

    # -- lectura del emulador -----------------------------------------------

    def _ciclos(self) -> int:
        return int(getattr(getattr(self.emulador, "cpu", None), "ciclos", 0) or 0)

    def _se_detuvo(self) -> bool:
        return bool(getattr(getattr(self.emulador, "cpu", None), "detenido", True))

    # -- referencia del anfitrion -------------------------------------------

    def _texto_salida(self, tipo: str, patron: int) -> str:
        if tipo == "flotante":
            return texto_flotante(patron)
        if tipo == "entero":
            return str(con_signo(patron))
        return self.ORDEN_FCMP.get(patron, f"codigo {con_signo(patron)}")

    @staticmethod
    def _coinciden(tipo: str, resultado: int, referencia: Optional[int]
                   ) -> Optional[bool]:
        if referencia is None:
            return None
        if tipo == "flotante" and clasificar_ieee754(referencia) == "NaN":
            # Cualquier NaN es una respuesta valida: la carga util es libre.
            return clasificar_ieee754(resultado) == "NaN"
        return resultado == referencia

    @staticmethod
    def _referencia(clave: str, a: int, b: int) -> Optional[int]:
        """
        Lo que dice la aritmetica IEEE 754 del anfitrion. Devuelve None cuando
        el estandar no fija un unico resultado (FLOAT -> INT fuera de rango).
        """
        if clave == "I2F":
            return flotante_a_bits(float(con_signo(a)))

        x, y = bits_a_flotante(a), bits_a_flotante(b)

        if clave == "F2I":
            if math.isnan(x) or math.isinf(x):
                return None
            entero = math.trunc(x)
            if not -(1 << 63) <= entero < (1 << 63):
                return None
            return entero & MASCARA_64

        if clave == "FCMP":
            if math.isnan(x) or math.isnan(y):
                return 2
            return MASCARA_64 if x < y else (1 if x > y else 0)

        if clave == "FADD":
            valor = x + y
        elif clave == "FSUB":
            valor = x - y
        elif clave == "FMUL":
            valor = x * y
        elif clave == "FDIV":
            if y == 0.0 and not math.isnan(x) and not math.isnan(y):
                # Python lanza ZeroDivisionError; IEEE 754 responde infinito
                # con el signo XOR de los operandos, o NaN si es 0/0.
                negativo = (a ^ b) >> 63
                valor = math.nan if x == 0.0 else (-math.inf if negativo else math.inf)
            else:
                valor = x / y
        elif clave == "FSQRT":
            if math.isnan(x) or x == 0.0:
                valor = x                       # sqrt(-0) = -0
            elif x < 0.0:
                valor = math.nan
            else:
                valor = math.sqrt(x)
        else:  # pragma: no cover - el catalogo y esta funcion van a la par
            return None
        return flotante_a_bits(valor)

    @staticmethod
    def _es_inexacto(clave: str, a: int, b: int, resultado: int) -> Optional[bool]:
        """
        True si el resultado tuvo que redondearse. Se decide con aritmetica
        racional exacta; None cuando la pregunta no aplica (NaN, infinitos,
        comparaciones).
        """
        if clave in ("FCMP",):
            return None
        if clave == "F2I":
            x = bits_a_flotante(a)
            if math.isnan(x) or math.isinf(x):
                return None
            return Fraction(x) != con_signo(resultado)

        r = bits_a_flotante(resultado)
        if math.isnan(r) or math.isinf(r):
            return None
        if clave == "I2F":
            return Fraction(r) != con_signo(a)

        x, y = bits_a_flotante(a), bits_a_flotante(b)
        if any(math.isnan(v) or math.isinf(v) for v in (x, y)):
            return None
        fx, fy, fr = Fraction(x), Fraction(y), Fraction(r)
        if clave == "FADD":
            return fx + fy != fr
        if clave == "FSUB":
            return fx - fy != fr
        if clave == "FMUL":
            return fx * fy != fr
        if clave == "FDIV":
            return None if fy == 0 else fx / fy != fr
        if clave == "FSQRT":
            return None if fx < 0 else fr * fr != fx
        return None  # pragma: no cover
