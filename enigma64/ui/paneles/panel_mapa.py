"""
Panel del mapa de memoria (Integrante 5).

Dibuja las ocho regiones del espacio fisico de 4 GiB con sus permisos, tal y
como estan definidas en la Tarea 9, y resalta la region donde cayo el ultimo
acceso. No depende de ningun modulo de hardware: es dato puro, asi que este
panel funciona siempre, incluso si todo lo demas falla.

Arranque suelto:  python -m enigma64.ui.paneles.panel_mapa

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk

from ..core.bus import Evento
from ..core.formato import hex32, tamano_legible
from ..core.tema import MARGEN, PALETA, mono, sans
from ..core.widgets import mezclar
from ..servicios.mapa_memoria import (
    CONTROLADORES, REGIONES, REGISTROS_MMIO, region_de,
)
from .base import PanelBase


class PanelMapa(PanelBase):
    """Referencia visual del mapa de memoria arquitectonico."""

    NOMBRE = "mapa"
    TITULO = "Mapa de memoria"
    SUBTITULO = "4 GiB fisicos implementados  ·  Tarea 9"
    ACENTO = PALETA["violeta"]
    CLAVE_SERVICIO = ""          # no necesita ningun modulo del equipo
    TAMANO_SUELTO = (680, 920)

    def construir(self) -> None:
        self._marcos = {}
        self._construir_regiones()
        self.separador()
        self._construir_perifericos()
        self._construir_detalle()

        # Se entera de los accesos escuchando el bus, sin conocer al panel
        # de memoria ni al del cargador.
        self.bus.suscribir(Evento.BUS_SENAL, self._al_acceder)
        self.bus.suscribir(Evento.PROGRAMA_CARGADO, self._al_cargar)

    # -- construccion -------------------------------------------------------

    def _construir_regiones(self) -> None:
        for region in REGIONES:
            marco = tk.Frame(self.cuerpo, bg=PALETA["elevado"],
                             highlightthickness=1,
                             highlightbackground=PALETA["elevado"])
            marco.pack(fill="x", pady=1)

            barra = tk.Frame(marco, bg=region["color"], width=10)
            barra.pack(side="left", fill="y", padx=(2, 10), pady=2)
            barra.pack_propagate(False)

            columna = tk.Frame(marco, bg=PALETA["elevado"])
            columna.pack(side="left", fill="x", expand=True, pady=3)
            tk.Label(columna, text=region["nombre"], bg=PALETA["elevado"],
                     fg=PALETA["texto"], font=sans(10), anchor="w").pack(fill="x")
            tk.Label(columna, text=region["permisos"], bg=PALETA["elevado"],
                     fg=PALETA["texto_debil"], font=sans(8), anchor="w").pack(fill="x")

            derecha = tk.Frame(marco, bg=PALETA["elevado"])
            derecha.pack(side="right", pady=3, padx=(0, 4))
            tk.Label(derecha, text=hex32(region["inicio"]), bg=PALETA["elevado"],
                     fg=region["color"], font=mono(9), anchor="e").pack(fill="x")
            tk.Label(derecha, text=hex32(region["fin"]), bg=PALETA["elevado"],
                     fg=PALETA["texto_debil"], font=mono(9), anchor="e").pack(fill="x")

            # Una barra mas alta para las regiones grandes da sensacion de escala.
            extension = region["fin"] - region["inicio"] + 1
            barra.configure(height=max(26, min(70, int(extension / 0x02000000) + 26)))
            self._marcos[region["nombre"]] = marco

    def _construir_perifericos(self) -> None:
        self.rotulo(self.cuerpo,
                    "Controladores mapeados en memoria  ·  4 KiB cada uno").pack(
                        anchor="w")
        rejilla = self.fila()
        rejilla.pack(fill="x", pady=(6, 0))
        for indice, controlador in enumerate(CONTROLADORES):
            fila = tk.Frame(rejilla, bg=PALETA["elevado"])
            fila.pack(fill="x")
            tk.Label(fila, text=hex32(controlador["base"]), bg=PALETA["elevado"],
                     fg=PALETA["violeta"], font=mono(9), width=12,
                     anchor="w").pack(side="left")
            tk.Label(fila, text=controlador["nombre"], bg=PALETA["elevado"],
                     fg=PALETA["texto_tenue"], font=sans(9),
                     anchor="w").pack(side="left")

        # Los cinco registros no caben en una sola linea en la columna lateral.
        mitad = (len(REGISTROS_MMIO) + 1) // 2
        for grupo in (REGISTROS_MMIO[:mitad], REGISTROS_MMIO[mitad:]):
            tk.Label(self.cuerpo, text="  ".join(grupo), bg=PALETA["elevado"],
                     fg=PALETA["texto_debil"], font=mono(8), anchor="w").pack(
                         fill="x", pady=(6, 0))

    def _construir_detalle(self) -> None:
        self.rotulo(self.cuerpo, "Ultimo acceso observado en el bus").pack(
            anchor="w", pady=(MARGEN, 6))

        marco = tk.Frame(self.cuerpo, bg=PALETA["borde"])
        marco.pack(fill="x")
        interior = tk.Frame(marco, bg=PALETA["abismo"])
        interior.pack(fill="x", padx=1, pady=1)

        self.detalle_direccion = tk.Label(interior, text="—", bg=PALETA["abismo"],
                                          fg=PALETA["ambar"], font=mono(11, True),
                                          anchor="w")
        self.detalle_direccion.pack(fill="x", padx=12, pady=(10, 2))
        self.detalle_region = tk.Label(interior, text="Sin accesos todavia.",
                                       bg=PALETA["abismo"], fg=PALETA["texto_tenue"],
                                       font=mono(9), anchor="w", justify="left",
                                       wraplength=360)
        self.detalle_region.pack(fill="x", padx=12, pady=(0, 10))

    # -- reaccion a eventos -------------------------------------------------

    def _al_acceder(self, mensaje) -> None:
        direccion = mensaje.get("direccion")
        if direccion is not None:
            self.resaltar(direccion, mensaje.get("estado", ""))

    def _al_cargar(self, mensaje) -> None:
        direccion = mensaje.get("direccion_base")
        if direccion is not None:
            self.resaltar(direccion, "PROGRAMA CARGADO")

    def resaltar(self, direccion: int, estado: str = "") -> None:
        """Marca la region que contiene la direccion indicada."""
        region = region_de(direccion)

        for nombre, marco in self._marcos.items():
            activa = region is not None and nombre == region["nombre"]
            marco.configure(
                highlightbackground=region["color"] if activa else PALETA["elevado"],
                bg=mezclar(PALETA["elevado"], region["color"], 0.12) if activa
                else PALETA["elevado"])

        self.detalle_direccion.configure(text=hex32(direccion))
        if region is None:
            self.detalle_region.configure(
                text="No mapeado  ·  A[63:32] != 0 levanta FALLO_DIR en el bus.",
                fg=PALETA["fallo"])
        else:
            extension = region["fin"] - region["inicio"] + 1
            self.detalle_region.configure(
                text=f"{region['nombre']}  ·  {region['permisos']}"
                     f"  ·  {tamano_legible(extension)}"
                     + (f"  ·  {estado}" if estado else "")
                     + f"\n{region['nota']}",
                fg=PALETA["texto_tenue"])

    # -- demostracion suelta ------------------------------------------------

    def preparar_demo(self) -> None:
        self.resaltar(0x00200000, "READY")


if __name__ == "__main__":
    PanelMapa.ejecutar_suelto()
