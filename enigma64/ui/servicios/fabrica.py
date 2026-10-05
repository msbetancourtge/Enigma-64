"""
Fabrica de servicios: arma el hardware una sola vez y lo reparte.

Hay dos formas de usar la interfaz y las dos pasan por aqui:

  * Ventana completa: se crea UNA maquina y todos los paneles reciben
    adaptadores que apuntan a la misma RAM y al mismo banco de registros, por
    eso lo que carga el cargador se ve en el volcado de memoria.

  * Panel suelto (`python -m enigma64.ui.paneles.panel_alu`): el panel llama a
    `construir_maquina()` por su cuenta y obtiene un hardware propio y recien
    reiniciado. No comparte nada con nadie, que es justo lo que permite
    demostrar el modulo por separado.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

from typing import Dict, List

from .adaptadores import (
    AdaptadorALU, AdaptadorAlgoritmos, AdaptadorCPU, AdaptadorCargador,
    AdaptadorFPU, AdaptadorMemoria, AdaptadorMMIO, AdaptadorRegistros,
)


class Maquina:
    """
    Conjunto coherente de servicios: una RAM, un banco, una ALU y un cargador
    ya conectados entre si.
    """

    def __init__(self) -> None:
        self.memoria = AdaptadorMemoria()
        self.registros = AdaptadorRegistros()
        self.alu = AdaptadorALU(registros=self.registros)
        self.cargador = AdaptadorCargador(memoria=self.memoria, registros=self.registros)
        self.cpu = AdaptadorCPU(memoria=self.memoria, registros=self.registros)
        self.mmio = AdaptadorMMIO(memoria=self.memoria)
        # La FPU corre sobre un procesador propio: no recibe ni la RAM ni el
        # banco compartidos, asi que sus calculos no alteran la maquina.
        self.fpu = AdaptadorFPU()
        # Servicio compuesto: no es un modulo del equipo, por eso no sale en
        # el informe de modulos de la barra superior.
        self.algoritmos = AdaptadorAlgoritmos(
            memoria=self.memoria, cargador=self.cargador,
            registros=self.registros, cpu=self.cpu,
        )

    # -- diagnostico --------------------------------------------------------

    @property
    def servicios(self) -> Dict[str, object]:
        return {
            "memoria": self.memoria,
            "registros": self.registros,
            "alu": self.alu,
            "cargador": self.cargador,
            "cpu": self.cpu,
            "mmio": self.mmio,
            "fpu": self.fpu,
        }

    def informe(self) -> List[Dict[str, object]]:
        """Estado de carga de cada modulo, para pintarlo en la barra superior."""
        return [
            {
                "clave": clave,
                "nombre": servicio.nombre,
                "modulo": servicio.modulo,
                "disponible": servicio.disponible,
                "motivo": servicio.motivo,
            }
            for clave, servicio in self.servicios.items()
        ]

    @property
    def modulos_disponibles(self) -> int:
        return sum(1 for s in self.servicios.values() if s.disponible)

    @property
    def total_modulos(self) -> int:
        return len(self.servicios)

    def reiniciar(self) -> None:
        """RESET de la maquina: vacia la RAM y devuelve los registros a su estado inicial."""
        if self.memoria.disponible:
            self.memoria.reiniciar()
        if self.registros.disponible:
            self.registros.reiniciar()
        if self.cpu.disponible:
            self.cpu.reiniciar()
        self.mmio.reiniciar()


def construir_maquina() -> Maquina:
    """Crea un juego completo de servicios independiente de cualquier otro."""
    return Maquina()
