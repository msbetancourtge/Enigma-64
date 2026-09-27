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

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .puertos import ServicioBase

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

from .mapa_memoria import REGIONES


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
