"""
Puertos: el contrato entre la interfaz y los modulos de hardware del equipo.

Cada panel habla con su modulo a traves de uno de estos servicios y nunca
importa directamente `enigma64.memoria`, `enigma64.registros` ni
`enigma64.cargador`. Gracias a eso:

  * El panel se puede arrancar solo aunque el modulo del companero todavia no
    exista o cambie de firma: basta con ajustar el adaptador.
  * Los modulos de los companeros no se tocan nunca. El adaptador se adapta a
    ellos, no al reves.

Cada servicio expone ademas `disponible` y `motivo`, para que el panel pueda
mostrar honestamente que el modulo no se pudo cargar en vez de reventar.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple, runtime_checkable


class ServicioNoDisponible(RuntimeError):
    """Se pidio una operacion a un modulo que no se pudo cargar."""


class ServicioBase:
    """Parte comun a todos los servicios: saber si el modulo esta o no esta."""

    nombre: str = "servicio"
    modulo: str = ""

    def __init__(self, disponible: bool = True, motivo: str = "") -> None:
        self.disponible = disponible
        self.motivo = motivo

    def exigir(self) -> None:
        if not self.disponible:
            raise ServicioNoDisponible(
                f"El modulo '{self.modulo or self.nombre}' no esta disponible: {self.motivo}"
            )


@runtime_checkable
class PuertoMemoria(Protocol):
    """Lo que la interfaz necesita del subsistema de RAM y buses."""

    disponible: bool
    motivo: str

    def leer(self, direccion: int, tamano: int, verificar_alineacion: bool = True
             ) -> Tuple[Optional[int], str]: ...

    def escribir(self, direccion: int, valor: int, tamano: int,
                 verificar_alineacion: bool = True) -> Tuple[Optional[int], str]: ...

    def leer_byte(self, direccion: int) -> int: ...

    def reiniciar(self) -> None: ...

    def estadisticas(self) -> Dict[str, Any]: ...

    def senales(self) -> Sequence[str]: ...

    def tamanos_validos(self) -> Sequence[int]: ...


@runtime_checkable
class PuertoRegistros(Protocol):
    """Lo que la interfaz necesita del banco de registros."""

    disponible: bool
    motivo: str

    def instantanea(self) -> Dict[str, Any]: ...

    def escribir_nombre(self, nombre: str, valor: int) -> None: ...

    def leer_nombre(self, nombre: str) -> int: ...

    def alternar_bandera(self, bandera: str) -> int: ...

    def reiniciar(self) -> None: ...

    def suscribir(self, callback) -> None: ...

    def nombres(self) -> Sequence[str]: ...

    def banderas(self) -> Sequence[str]: ...


@runtime_checkable
class PuertoALU(Protocol):
    """Lo que la interfaz necesita de la unidad aritmetico-logica."""

    disponible: bool
    motivo: str

    def operaciones(self) -> Sequence[str]: ...

    def es_unaria(self, operacion: str) -> bool: ...

    def ejecutar(self, operacion: str, a: int, b: int, volcar_sr: bool = False
                 ) -> Dict[str, Any]: ...


@runtime_checkable
class PuertoCargador(Protocol):
    """Lo que la interfaz necesita del cargador y del manipulador de bits."""

    disponible: bool
    motivo: str

    def cargar_archivo(self, ruta: str, destino: Optional[int],
                       configurar_cpu: bool) -> Dict[str, Any]: ...

    def cargar_texto(self, texto: str, destino: int, punto_entrada: Optional[int],
                     configurar_cpu: bool) -> Dict[str, Any]: ...

    def leer_bit(self, direccion: int, indice: int) -> int: ...

    def escribir_bit(self, direccion: int, indice: int, valor: int) -> None: ...

    def conmutar_bit(self, direccion: int, indice: int) -> int: ...

    def byte_en_bits(self, direccion: int) -> str: ...

    def regiones(self) -> List[Dict[str, Any]]: ...
