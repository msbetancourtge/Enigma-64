"""
Bus de eventos de la interfaz de Enigma-64.

Requisito del curso: los modulos no se mezclan. Ningun panel importa a otro
panel ni guarda una referencia a el. Cuando un panel necesita contarle algo al
resto, publica un evento en este bus y se olvida; quien este interesado se
suscribe. El resultado es que cada panel se puede arrancar solo, sin bus y sin
companeros, y sigue funcionando.

Funciona como el bus de control de la maquina real: un emisor, varios
receptores, y nadie conoce a nadie.

    bus = BusEventos()
    bus.suscribir(Evento.MEMORIA_ESCRITA, self._al_escribir)
    bus.publicar(Evento.MEMORIA_ESCRITA, direccion=0x200000, valor=1)

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import traceback
from typing import Any, Callable, Dict, List

Oyente = Callable[["Mensaje"], None]


class Evento:
    """
    Catalogo de eventos. Son cadenas para que un panel pueda publicar sin
    importar nada de otro panel; la constante existe solo para evitar erratas.
    """

    # Memoria RAM y buses (Integrante 1)
    MEMORIA_LEIDA = "memoria.leida"
    MEMORIA_ESCRITA = "memoria.escrita"
    MEMORIA_REINICIADA = "memoria.reiniciada"
    BUS_SENAL = "bus.senal"

    # Banco de registros y ALU (Integrante 2)
    REGISTROS_CAMBIADOS = "registros.cambiados"
    REGISTROS_REINICIADOS = "registros.reiniciados"
    ALU_EJECUTADA = "alu.ejecutada"

    # Cargador (Integrante 4)
    PROGRAMA_CARGADO = "cargador.programa_cargado"
    CARGA_RECHAZADA = "cargador.carga_rechazada"
    BIT_MODIFICADO = "cargador.bit_modificado"

    # Navegacion y traza (Integrante 5)
    IR_A_DIRECCION = "ui.ir_a_direccion"
    TRAZA = "ui.traza"

    @classmethod
    def todos(cls) -> List[str]:
        return sorted(
            valor for nombre, valor in vars(cls).items()
            if not nombre.startswith("_") and isinstance(valor, str)
        )


class Mensaje:
    """Lo que recibe un oyente: el nombre del evento y sus datos."""

    __slots__ = ("evento", "datos")

    def __init__(self, evento: str, datos: Dict[str, Any]) -> None:
        self.evento = evento
        self.datos = datos

    def get(self, clave: str, por_defecto: Any = None) -> Any:
        return self.datos.get(clave, por_defecto)

    def __repr__(self) -> str:  # pragma: no cover - ayuda de depuracion
        return f"Mensaje({self.evento!r}, {self.datos!r})"


#: Comodin: suscribirse a esto recibe absolutamente todos los eventos.
TODOS = "*"


class BusEventos:
    """
    Publicador/suscriptor sincrono y sin dependencias.

    Es deliberadamente tolerante a fallos: si un oyente lanza una excepcion, se
    registra y se sigue notificando al resto. Un panel roto no puede tumbar a
    los demas, que es justamente lo que pide el requisito de aislamiento.
    """

    def __init__(self) -> None:
        self._oyentes: Dict[str, List[Oyente]] = {}
        self._historial: List[Mensaje] = []
        self._limite_historial = 500
        self.errores: List[str] = []

    # -- suscripcion --------------------------------------------------------

    def suscribir(self, evento: str, oyente: Oyente) -> Oyente:
        """Registra un oyente. Devuelve el mismo oyente para poder desuscribirlo."""
        self._oyentes.setdefault(evento, []).append(oyente)
        return oyente

    def suscribir_todo(self, oyente: Oyente) -> Oyente:
        """Escucha cualquier evento. Lo usa el panel de traza."""
        return self.suscribir(TODOS, oyente)

    def desuscribir(self, evento: str, oyente: Oyente) -> None:
        cola = self._oyentes.get(evento)
        if cola and oyente in cola:
            cola.remove(oyente)

    # -- publicacion --------------------------------------------------------

    def publicar(self, evento: str, **datos: Any) -> Mensaje:
        """Entrega el evento a sus oyentes y a los suscritos al comodin."""
        mensaje = Mensaje(evento, datos)

        self._historial.append(mensaje)
        if len(self._historial) > self._limite_historial:
            del self._historial[: len(self._historial) - self._limite_historial]

        for oyente in list(self._oyentes.get(evento, ())) + list(self._oyentes.get(TODOS, ())):
            try:
                oyente(mensaje)
            except Exception:
                self.errores.append(
                    f"oyente de {evento!r} fallo:\n{traceback.format_exc()}"
                )
        return mensaje

    def traza(self, texto: str, severidad: str = "info", origen: str = "ui") -> Mensaje:
        """Atajo para mandar una linea a la consola de traza."""
        return self.publicar(Evento.TRAZA, texto=texto, severidad=severidad, origen=origen)

    # -- inspeccion ---------------------------------------------------------

    @property
    def historial(self) -> List[Mensaje]:
        return list(self._historial)

    def limpiar_historial(self) -> None:
        self._historial.clear()

    def cuenta_oyentes(self, evento: str) -> int:
        return len(self._oyentes.get(evento, ()))


class BusNulo(BusEventos):
    """
    Bus que no lleva a ninguna parte.

    Es lo que recibe un panel cuando se arranca suelto con
    ``python -m enigma64.ui.paneles.panel_memoria``: el panel publica
    exactamente igual que dentro de la ventana completa, pero nadie escucha.
    Asi el codigo del panel no necesita ni un solo ``if bus is not None``.
    """

    def publicar(self, evento: str, **datos: Any) -> Mensaje:
        return Mensaje(evento, datos)
