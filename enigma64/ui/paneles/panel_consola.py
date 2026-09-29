"""
Panel de traza del bus de eventos (Integrante 5).

Se suscribe a TODO lo que circula por el bus y lo escribe con marca de tiempo,
origen y severidad. Es la prueba visible de que los paneles no se hablan entre
si: aqui se ve cada mensaje que un modulo publica y que otro recoge.

Arranque suelto:  python -m enigma64.ui.paneles.panel_consola

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from ..core.bus import Evento
from ..core.tema import COLOR_POR_SEVERIDAD, MARGEN, PALETA, mono
from ..core.widgets import TextoMono
from .base import PanelBase

#: Cuantos eventos se conservan antes de recortar el principio.
LIMITE_LINEAS = 400


class PanelConsola(PanelBase):
    """Registro cronologico de los eventos del bus."""

    NOMBRE = "consola"
    TITULO = "Traza del bus de eventos"
    SUBTITULO = "Integrante 5  ·  enigma64.ui.core.bus"
    ACENTO = PALETA["texto_tenue"]
    CLAVE_SERVICIO = ""
    TAMANO_SUELTO = (820, 520)

    def construir(self) -> None:
        self._lineas = 0
        self._construir_controles()

        self.registro = TextoMono(self.cuerpo, alto=12, ancho=34, tam=8)
        self.registro.pack(fill="both", expand=True)
        for severidad, color in COLOR_POR_SEVERIDAD.items():
            self.registro.configurar_etiqueta(severidad, foreground=color)
        self.registro.configurar_etiqueta("hora", foreground=PALETA["texto_debil"])
        self.registro.configurar_etiqueta("origen", foreground=PALETA["ambar"])

        self.bus.suscribir_todo(self._al_llegar_evento)
        self.anotar("Traza iniciada. Escuchando el bus de eventos.", "info", "ui")

    def _construir_controles(self) -> None:
        fila = self.fila()
        fila.pack(fill="x", pady=(0, MARGEN))

        self.autodesplazar = tk.BooleanVar(value=True)
        ttk.Checkbutton(fila, text="Seguir el final",
                        variable=self.autodesplazar).pack(side="left")

        self.contador = tk.Label(fila, text="0 eventos", bg=PALETA["elevado"],
                                 fg=PALETA["texto_debil"], font=mono(9))
        self.contador.pack(side="left", padx=(14, 0))

        ttk.Button(fila, text="Limpiar", command=self.limpiar).pack(side="right")

    # -- entrada de eventos -------------------------------------------------

    def _al_llegar_evento(self, mensaje) -> None:
        """Traduce cualquier mensaje del bus a una linea legible."""
        origen = mensaje.get("origen", "bus")

        if mensaje.evento == Evento.TRAZA:
            self.anotar(mensaje.get("texto", ""), mensaje.get("severidad", "info"),
                        origen)
            return

        # Los demas eventos se resumen mostrando sus datos, sin el origen.
        datos = {c: v for c, v in mensaje.datos.items() if c != "origen"}
        resumen = "  ".join(f"{c}={_breve(v)}" for c, v in datos.items())
        self.anotar(f"{mensaje.evento}  {resumen}".rstrip(), "dato", origen)

    def anotar(self, texto: str, severidad: str = "info", origen: str = "ui") -> None:
        seguir = self.autodesplazar.get()
        self.registro.anexar(time.strftime("%H:%M:%S") + "  ", "hora",
                             autodesplazar=False)
        self.registro.anexar(f"{origen:<10}", "origen", autodesplazar=False)
        self.registro.anexar(texto + "\n", severidad, autodesplazar=seguir)

        self._lineas += 1
        if self._lineas > LIMITE_LINEAS:
            self._recortar()
        self.contador.configure(text=f"{self._lineas} eventos")

    def _recortar(self) -> None:
        """Descarta la primera mitad para que la traza no crezca sin limite."""
        sobrantes = self._lineas - LIMITE_LINEAS // 2
        self.registro.texto.configure(state="normal")
        self.registro.texto.delete("1.0", f"{sobrantes + 1}.0")
        self.registro.texto.configure(state="disabled")
        self._lineas -= sobrantes

    def limpiar(self) -> None:
        self.registro.limpiar()
        self._lineas = 0
        self.contador.configure(text="0 eventos")


def _breve(valor, limite: int = 34) -> str:
    """Los enteros que parecen direcciones se muestran en hexadecimal."""
    if isinstance(valor, bool) or valor is None:
        return str(valor)
    if isinstance(valor, int):
        return f"0x{valor:X}" if valor > 255 else str(valor)
    texto = str(valor)
    return texto if len(texto) <= limite else texto[:limite - 1] + "…"


if __name__ == "__main__":
    PanelConsola.ejecutar_suelto()
