"""
Ventana principal de Enigma-64.

La ventana no contiene logica de ningun modulo: crea UNA maquina, UN bus, e
instancia los paneles pasandole a cada uno su servicio. Los paneles no se
conocen entre si; cuando uno tiene que reaccionar a otro lo hace por el bus.

Distribucion, pensada para que quepa en un portatil de 1366x768:

    izquierda   cuaderno con una pestana por modulo (memoria, registros,
                ALU, FPU, cargador). Solo se ve un modulo a la vez, que es
                exactamente como pidio el profesor que se demostraran.
    derecha     columna de contexto: el mapa de memoria y la traza del bus,
                visibles siempre para poder seguir lo que hace el modulo
                que este abierto.

Todo panel va dentro de un marco desplazable, asi que ninguna resolucion
recorta contenido.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.bus import BusEventos, Evento
from ..core.tema import (
    COMPUTADOR, EMPRESA, LEMA, MARGEN, PALETA, aplicar_tema, mono, sans,
)
from ..core.widgets import Insignia, MarcaNoctua, MarcoDesplazable
from ..paneles.panel_algoritmos import PanelAlgoritmos
from ..paneles.panel_alu import PanelALU
from ..paneles.panel_cargador import PanelCargador
from ..paneles.panel_consola import PanelConsola
from ..paneles.panel_cpu import PanelCPU
from ..paneles.panel_fpu import PanelFPU
from ..paneles.panel_mapa import PanelMapa
from ..paneles.panel_memoria import PanelMemoria
from ..paneles.panel_mmio import PanelMMIO
from ..paneles.panel_registros import PanelRegistros
from ..servicios import construir_maquina

#: Paneles que ocupan una pestana del cuaderno, en orden de presentacion.
PESTANAS = (
    (PanelMemoria, "memoria", "Memoria RAM"),
    (PanelRegistros, "registros", "Registros"),
    (PanelALU, "alu", "ALU"),
    (PanelFPU, "fpu", "FPU"),
    (PanelCargador, "cargador", "Cargador"),
    (PanelCPU, "cpu", "Unidad de Control"),
    (PanelMMIO, "mmio", "I/O mapeada"),
    (PanelAlgoritmos, "algoritmos", "Algoritmos"),
)

#: Ancho reservado a la columna de contexto de la derecha.
ANCHO_CONTEXTO = 450


class VentanaEnigma(tk.Tk):
    """Ventana completa del emulador."""

    def __init__(self) -> None:
        super().__init__()
        aplicar_tema(self)

        self.title(f"{COMPUTADOR}  ·  {EMPRESA}")
        self.configure(bg=PALETA["abismo"])
        self._ajustar_a_la_pantalla()

        self.maquina = construir_maquina()
        self.bus = BusEventos()
        self.paneles = {}

        self._construir_barra_superior()
        self._construir_cuerpo()
        self._construir_barra_estado()

        self.bus.suscribir_todo(self._al_pasar_evento)
        self.bus.traza(
            f"{self.maquina.modulos_disponibles} de {self.maquina.total_modulos} "
            "modulos conectados.", "exito", "shell")

    # -- geometria ----------------------------------------------------------

    def _ajustar_a_la_pantalla(self) -> None:
        """
        Toma casi toda la pantalla sin pasarse de ella. En monitores pequenos
        esto evita que la ventana nazca mas grande que el escritorio.
        """
        ancho_pantalla = self.winfo_screenwidth()
        alto_pantalla = self.winfo_screenheight()
        ancho = min(1500, ancho_pantalla - 40)
        alto = min(940, alto_pantalla - 80)
        x = max(0, (ancho_pantalla - ancho) // 2)
        y = max(0, (alto_pantalla - alto) // 3)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.minsize(min(1024, ancho), min(640, alto))

    # -- barra superior -----------------------------------------------------

    def _construir_barra_superior(self) -> None:
        barra = tk.Frame(self, bg=PALETA["abismo"])
        barra.pack(fill="x", padx=MARGEN + 2, pady=(8, 6))

        MarcaNoctua(barra, lado=40, fondo=PALETA["abismo"]).pack(side="left")

        columna = tk.Frame(barra, bg=PALETA["abismo"])
        columna.pack(side="left", padx=10)
        tk.Label(columna, text=COMPUTADOR, bg=PALETA["abismo"], fg=PALETA["texto"],
                 font=sans(16, True)).pack(anchor="w")
        tk.Label(columna, text=f"{EMPRESA}   ·   {LEMA}", bg=PALETA["abismo"],
                 fg=PALETA["ambar"], font=sans(8)).pack(anchor="w")

        ttk.Button(barra, text="RESET de la maquina", style="Peligro.TButton",
                   command=self.reiniciar_maquina).pack(side="right", padx=(10, 0))

        # Una insignia por modulo: se ve de un vistazo que hay conectado.
        chips = tk.Frame(barra, bg=PALETA["abismo"])
        chips.pack(side="right")
        for informe in self.maquina.informe():
            etiqueta = informe["clave"].upper()
            insignia = Insignia(chips, ancho=10 + len(etiqueta) * 8, alto=20,
                                fondo=PALETA["abismo"])
            insignia.fijar(etiqueta,
                           PALETA["ok"] if informe["disponible"] else PALETA["fallo"])
            insignia.pack(side="left", padx=3)

        tk.Frame(self, bg=PALETA["borde"], height=1).pack(fill="x")

    # -- cuerpo -------------------------------------------------------------

    def _construir_cuerpo(self) -> None:
        cuerpo = tk.Frame(self, bg=PALETA["abismo"])
        cuerpo.pack(fill="both", expand=True, padx=MARGEN, pady=MARGEN)
        cuerpo.rowconfigure(0, weight=1)
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.columnconfigure(1, weight=0, minsize=ANCHO_CONTEXTO)

        self._construir_cuaderno(cuerpo)
        self._construir_contexto(cuerpo)

    def _construir_cuaderno(self, maestro: tk.Frame) -> None:
        self.cuaderno = ttk.Notebook(maestro)
        self.cuaderno.grid(row=0, column=0, sticky="nsew", padx=(0, MARGEN // 2))

        for clase, clave, etiqueta in PESTANAS:
            marco = MarcoDesplazable(self.cuaderno)
            self.cuaderno.add(marco, text=etiqueta)
            self._montar(clase, marco.interior, getattr(self.maquina, clave))

    def _construir_contexto(self, maestro: tk.Frame) -> None:
        columna = tk.Frame(maestro, bg=PALETA["abismo"], width=ANCHO_CONTEXTO)
        columna.grid(row=0, column=1, sticky="nsew", padx=(MARGEN // 2, 0))
        columna.grid_propagate(False)
        columna.rowconfigure(0, weight=3)
        columna.rowconfigure(1, weight=2)
        columna.columnconfigure(0, weight=1)

        marco_mapa = MarcoDesplazable(columna)
        marco_mapa.grid(row=0, column=0, sticky="nsew", pady=(0, MARGEN))
        self._montar(PanelMapa, marco_mapa.interior, None)

        marco_traza = tk.Frame(columna, bg=PALETA["abismo"])
        marco_traza.grid(row=1, column=0, sticky="nsew")
        self._montar(PanelConsola, marco_traza, None)

    def _montar(self, clase, maestro, servicio) -> None:
        """Instancia un panel dandole SOLO el servicio que le corresponde."""
        panel = clase(maestro, servicio=servicio, bus=self.bus)
        panel.pack(fill="both", expand=True)
        self.paneles[clase.NOMBRE] = panel
        panel.preparar_demo()

    # -- barra de estado ----------------------------------------------------

    def _construir_barra_estado(self) -> None:
        tk.Frame(self, bg=PALETA["borde"], height=1).pack(fill="x")
        barra = tk.Frame(self, bg=PALETA["abismo"])
        barra.pack(fill="x", padx=MARGEN + 2, pady=5)

        self.estado = tk.Label(barra, text="Listo.", bg=PALETA["abismo"],
                               fg=PALETA["texto_debil"], font=mono(9), anchor="w")
        self.estado.pack(side="left", fill="x", expand=True)

        completo = self.maquina.modulos_disponibles == self.maquina.total_modulos
        tk.Label(barra,
                 text=f"{self.maquina.modulos_disponibles}/"
                      f"{self.maquina.total_modulos} modulos conectados",
                 bg=PALETA["abismo"],
                 fg=PALETA["ok"] if completo else PALETA["alerta"],
                 font=mono(9)).pack(side="right")

    def _al_pasar_evento(self, mensaje) -> None:
        """La barra de estado repite la ultima traza que circulo por el bus."""
        if mensaje.evento == Evento.TRAZA:
            self.estado.configure(text=mensaje.get("texto", ""))

    # -- acciones globales --------------------------------------------------

    def reiniciar_maquina(self) -> None:
        """RESET general: vacia la RAM y devuelve los registros a su estado inicial."""
        self.maquina.reiniciar()
        self.bus.publicar(Evento.MEMORIA_REINICIADA, origen="shell")
        self.bus.publicar(Evento.REGISTROS_REINICIADOS, origen="shell")
        self.bus.traza("RESET de la maquina completo.", "aviso", "shell")

        panel_memoria = self.paneles.get("memoria")
        if panel_memoria is not None and hasattr(panel_memoria, "refrescar_volcado"):
            panel_memoria.refrescar_volcado()


def main() -> None:
    """Punto de entrada de la interfaz completa."""
    VentanaEnigma().mainloop()


if __name__ == "__main__":
    main()
