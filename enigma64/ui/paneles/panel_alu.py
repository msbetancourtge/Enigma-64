"""
Panel de la Unidad Aritmetico-Logica (Integrante 2).

Reproduce la fase EXECUTE de la maquina de estados: se cargan los latches A y
B, se elige una operacion del repertorio del ISA y se observa el registro Z de
salida junto a las banderas que esa instruccion afecta segun la Tarea 9.

Arranque suelto:  python -m enigma64.ui.paneles.panel_alu

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.bus import Evento
from ..core.formato import (
    ValorInvalido, bin64_agrupado, decimal_agrupado, parsear_entero,
)
from ..core.tema import MARGEN, PALETA, mono, sans
from ..core.widgets import Led, TextoMono
from .base import PanelBase


class PanelALU(PanelBase):
    """Banco de pruebas de la ALU de 64 bits."""

    NOMBRE = "alu"
    TITULO = "Unidad aritmetico-logica"
    SUBTITULO = "Integrante 2  ·  enigma64.alu"
    ACENTO = PALETA["ambar"]
    CLAVE_SERVICIO = "alu"
    TAMANO_SUELTO = (780, 680)

    def construir(self) -> None:
        self.operacion = tk.StringVar(value="ADD")
        self._botones_op = {}
        self._leds = {}

        self._construir_operaciones()
        self.separador()
        self._construir_latches()
        self._construir_resultado()
        self._construir_historial()

        self._resaltar_operacion()

    # -- construccion -------------------------------------------------------

    def _construir_operaciones(self) -> None:
        self.rotulo(self.cuerpo, "Operacion").pack(anchor="w", pady=(0, 6))

        for familia, operaciones in self.servicio.operaciones_por_familia().items():
            if not operaciones:
                continue
            fila = self.fila()
            fila.pack(fill="x", pady=1)
            tk.Label(fila, text=familia, bg=PALETA["elevado"],
                     fg=PALETA["texto_debil"], font=sans(8), width=15,
                     anchor="w").pack(side="left")

            for operacion in operaciones:
                boton = tk.Label(fila, text=operacion, bg=PALETA["abismo"],
                                 fg=PALETA["texto_tenue"], font=mono(9, True),
                                 padx=9, pady=3, cursor="hand2",
                                 highlightthickness=1,
                                 highlightbackground=PALETA["borde"])
                boton.pack(side="left", padx=2)
                boton.bind("<Button-1>",
                           lambda _e, op=operacion: self.elegir_operacion(op))
                self._botones_op[operacion] = boton

    def _construir_latches(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")

        columna_a = tk.Frame(fila, bg=PALETA["elevado"])
        columna_a.pack(side="left", fill="x", expand=True)
        self.rotulo(columna_a, "Latch A").pack(anchor="w")
        self.latch_a = tk.StringVar(value="0x78")
        ttk.Entry(columna_a, textvariable=self.latch_a,
                  font=mono(10)).pack(fill="x")

        self.columna_b = tk.Frame(fila, bg=PALETA["elevado"])
        self.columna_b.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.rotulo_b = self.rotulo(self.columna_b, "Latch B")
        self.rotulo_b.pack(anchor="w")
        self.latch_b = tk.StringVar(value="0x5")
        self.entrada_b = ttk.Entry(self.columna_b, textvariable=self.latch_b,
                                   font=mono(10))
        self.entrada_b.pack(fill="x")

        acciones = self.fila()
        acciones.pack(fill="x", pady=(MARGEN, 0))
        ttk.Button(acciones, text="Ejecutar", style="Primario.TButton",
                   command=self.ejecutar).pack(side="left")
        self.volcar_sr = tk.BooleanVar(value=False)
        ttk.Checkbutton(acciones, text="Volcar banderas al registro SR",
                        variable=self.volcar_sr).pack(side="left", padx=(12, 0))
        ttk.Button(acciones, text="Intercambiar A/B",
                   command=self.intercambiar).pack(side="right")

    def _construir_resultado(self) -> None:
        marco = tk.Frame(self.cuerpo, bg=PALETA["borde"])
        marco.pack(fill="x", pady=(MARGEN, 0))
        interior = tk.Frame(marco, bg=PALETA["abismo"])
        interior.pack(fill="x", padx=1, pady=1)

        linea = tk.Frame(interior, bg=PALETA["abismo"])
        linea.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(linea, text="Z", bg=PALETA["abismo"], fg=PALETA["texto_debil"],
                 font=mono(10, True)).pack(side="left", padx=(0, 10))
        self.salida_hex = tk.Label(linea, text="—", bg=PALETA["abismo"],
                                   fg=PALETA["cian"], font=mono(15, True))
        self.salida_hex.pack(side="left")

        self.salida_dec = tk.Label(interior, text="", bg=PALETA["abismo"],
                                   fg=PALETA["texto_tenue"], font=mono(9), anchor="w")
        self.salida_dec.pack(fill="x", padx=12, pady=(4, 0))
        self.salida_bin = tk.Label(interior, text="", bg=PALETA["abismo"],
                                   fg=PALETA["texto_debil"], font=mono(8), anchor="w")
        self.salida_bin.pack(fill="x", padx=12, pady=(0, 10))

        self.rotulo_banderas = self.rotulo(self.cuerpo, "Banderas producidas")
        self.rotulo_banderas.pack(anchor="w", pady=(MARGEN, 6))

        fila_leds = self.fila()
        fila_leds.pack(anchor="w")
        for bandera in ("Z", "N", "C", "V"):
            led = Led(fila_leds, bandera, color=PALETA["ok"])
            led.pack(side="left", padx=(0, 22))
            self._leds[bandera] = led

    def _construir_historial(self) -> None:
        self.rotulo(self.cuerpo, "Historial de ejecucion").pack(anchor="w",
                                                                pady=(MARGEN, 6))
        self.historial = TextoMono(self.cuerpo, alto=6, ancho=64, tam=9)
        self.historial.pack(fill="both", expand=True)
        self.historial.configurar_etiqueta("ok", foreground=PALETA["texto_tenue"])
        self.historial.configurar_etiqueta("error", foreground=PALETA["fallo"])

    # -- acciones -----------------------------------------------------------

    def elegir_operacion(self, operacion: str) -> None:
        self.operacion.set(operacion)
        self._resaltar_operacion()

    def intercambiar(self) -> None:
        a, b = self.latch_a.get(), self.latch_b.get()
        self.latch_a.set(b)
        self.latch_b.set(a)

    def ejecutar(self) -> None:
        operacion = self.operacion.get()
        unaria = self.servicio.es_unaria(operacion)

        try:
            a = parsear_entero(self.latch_a.get())
            b = 0 if unaria else parsear_entero(self.latch_b.get())
        except ValorInvalido as exc:
            self.historial.anexar(f"  {exc}\n", "error")
            self.trazar(str(exc), "error")
            return

        try:
            resultado = self.servicio.ejecutar(operacion, a, b, self.volcar_sr.get())
        except Exception as exc:
            # DivisionPorCero y OperacionInvalida llegan aqui: son parte del
            # comportamiento esperado de la ALU, no un fallo de la interfaz.
            texto = f"{operacion}: {type(exc).__name__}: {exc}"
            self.historial.anexar(f"  {texto}\n", "error")
            self.trazar(texto, "error")
            return

        self._pintar_resultado(resultado)
        self.publicar(Evento.ALU_EJECUTADA, **resultado)

    # -- pintado ------------------------------------------------------------

    def _resaltar_operacion(self) -> None:
        activa = self.operacion.get()
        for operacion, boton in self._botones_op.items():
            encendido = operacion == activa
            boton.configure(
                bg=PALETA["ambar"] if encendido else PALETA["abismo"],
                fg=PALETA["abismo"] if encendido else PALETA["texto_tenue"],
                highlightbackground=PALETA["ambar"] if encendido else PALETA["borde"])

        # Las operaciones unarias (NOT, INC, DEC) ignoran el segundo operando.
        unaria = self.servicio.es_unaria(activa)
        self.entrada_b.configure(state="disabled" if unaria else "normal")
        self.rotulo_b.configure(
            text="LATCH B (NO USADO)" if unaria else "LATCH B",
            fg=PALETA["texto_debil"])

        afectadas = self.servicio.banderas_afectadas(activa)
        self.rotulo_banderas.configure(
            text=f"BANDERAS PRODUCIDAS  ·  {activa} AFECTA: {' '.join(afectadas) or '—'}")

    def _pintar_resultado(self, resultado: dict) -> None:
        self.salida_hex.configure(text=resultado["hex"])
        detalle = f"{decimal_agrupado(resultado['con_signo'])} con signo"
        if not resultado["escribe_destino"]:
            detalle += "   ·   CMP no escribe el registro destino"
        if resultado["volcado_sr"]:
            detalle += "   ·   banderas volcadas al SR"
        self.salida_dec.configure(text=detalle)
        self.salida_bin.configure(text=bin64_agrupado(resultado["valor"]))

        banderas = resultado["banderas"]
        for bandera, led in self._leds.items():
            led.fijar(bool(banderas.get(bandera, 0)))

        activas = " ".join(f"{b}={banderas[b]}" for b in ("Z", "N", "C", "V")
                           if b in banderas)
        self.historial.anexar(
            f"  {resultado['operacion']:<5} → {resultado['hex']}  [{activas}]\n", "ok")
        self.trazar(f"{resultado['operacion']} → {resultado['hex']}  [{activas}]", "dato")

    # -- demostracion suelta ------------------------------------------------

    def preparar_demo(self) -> None:
        if self.servicio.disponible:
            self.ejecutar()


if __name__ == "__main__":
    PanelALU.ejecutar_suelto()
