"""
Panel del banco de registros (Integrante 2).

Pinta los diez registros arquitectonicos (R0..R7, PC, SR) con su nibble de
codificacion, su valor en hexadecimal y su lectura en complemento a 2, mas las
siete banderas del SR. Se refresca solo: se suscribe al banco y repinta cuando
cualquier otra parte del sistema escribe un registro.

Arranque suelto:  python -m enigma64.ui.paneles.panel_registros

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.bus import Evento
from ..core.formato import ValorInvalido, decimal_agrupado, parsear_entero
from ..core.tema import MARGEN, PALETA, mono, sans
from ..core.widgets import Led
from .base import PanelBase

#: Descripcion larga de cada bandera, tomada de la Tarea 9.
NOMBRE_BANDERA = {
    "Z": "Zero", "N": "Negative", "C": "Carry", "V": "oVerflow",
    "M": "Misaligned", "I": "Interrupt", "S": "Supervisor",
}


class PanelRegistros(PanelBase):
    """Vista en vivo y editor del banco de registros."""

    NOMBRE = "registros"
    TITULO = "Banco de registros"
    SUBTITULO = "Integrante 2  ·  enigma64.registros"
    ACENTO = PALETA["ok"]
    CLAVE_SERVICIO = "registros"
    TAMANO_SUELTO = (760, 660)

    def construir(self) -> None:
        self._valores_previos = {}
        self._filas = {}
        self._leds = {}

        self._construir_tabla()
        self.separador()
        self._construir_banderas()
        self.separador()
        self._construir_edicion()

        # El banco avisa a quien se suscriba; asi el panel se entera de los
        # cambios que hace el cargador o la ALU sin conocerlos.
        self.servicio.suscribir(self.refrescar)
        self.refrescar()

    # -- construccion -------------------------------------------------------

    def _construir_tabla(self) -> None:
        tabla = self.fila()
        tabla.pack(fill="x")
        for columna, peso in ((0, 0), (1, 0), (2, 1), (3, 0)):
            tabla.columnconfigure(columna, weight=peso)

        encabezados = (("Reg", "w"), ("Cod", "w"), ("Hexadecimal", "w"),
                       ("Decimal con signo", "e"))
        for columna, (texto, anclaje) in enumerate(encabezados):
            tk.Label(tabla, text=texto.upper(), bg=PALETA["elevado"],
                     fg=PALETA["texto_debil"], font=mono(8, True)).grid(
                         row=0, column=columna, sticky=anclaje, pady=(0, 4))

        tk.Frame(tabla, bg=PALETA["borde_sutil"], height=1).grid(
            row=1, column=0, columnspan=4, sticky="ew", pady=(0, 4))

        for indice, nombre in enumerate(self.servicio.nombres()):
            fila = indice + 2
            alias = self.servicio.alias(nombre)
            etiqueta = f"{nombre} ({alias})" if alias else nombre

            celda_nombre = tk.Label(tabla, text=etiqueta, bg=PALETA["elevado"],
                                    fg=PALETA["texto_tenue"], font=mono(10))
            celda_nombre.grid(row=fila, column=0, sticky="w", padx=(0, 16))

            celda_codigo = tk.Label(tabla, text="", bg=PALETA["elevado"],
                                    fg=PALETA["texto_debil"], font=mono(10))
            celda_codigo.grid(row=fila, column=1, sticky="w", padx=(0, 16))

            celda_hex = tk.Label(tabla, text="", bg=PALETA["elevado"],
                                 fg=PALETA["cian"], font=mono(10))
            celda_hex.grid(row=fila, column=2, sticky="w")

            celda_dec = tk.Label(tabla, text="", bg=PALETA["elevado"],
                                 fg=PALETA["texto_tenue"], font=mono(10))
            celda_dec.grid(row=fila, column=3, sticky="e")

            if self.servicio.es_solo_lectura(nombre):
                celda_nombre.configure(fg=PALETA["texto_debil"])

            self._filas[nombre] = (celda_nombre, celda_codigo, celda_hex, celda_dec)

    def _construir_banderas(self) -> None:
        self.rotulo(self.cuerpo,
                    "Banderas del SR  ·  pulsa una para conmutarla").pack(anchor="w")

        fila = self.fila()
        fila.pack(anchor="w", pady=(8, 0))
        for bandera in self.servicio.banderas():
            columna = tk.Frame(fila, bg=PALETA["elevado"])
            columna.pack(side="left", padx=(0, 18))

            led = Led(columna, bandera, color=PALETA["ok"])
            led.pack(anchor="w")
            tk.Label(columna, text=NOMBRE_BANDERA.get(bandera, ""),
                     bg=PALETA["elevado"], fg=PALETA["texto_debil"],
                     font=sans(7)).pack(anchor="w")

            # El diodo y su etiqueta reaccionan al clic.
            for objetivo in (led, led.lienzo, led.etiqueta):
                objetivo.bind("<Button-1>",
                              lambda _e, b=bandera: self.conmutar_bandera(b))
                objetivo.configure(cursor="hand2")
            self._leds[bandera] = led

    def _construir_edicion(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")

        columna_reg = tk.Frame(fila, bg=PALETA["elevado"])
        columna_reg.pack(side="left")
        self.rotulo(columna_reg, "Registro").pack(anchor="w")
        self.registro = tk.StringVar(value="R1")
        ttk.Combobox(columna_reg, textvariable=self.registro, width=8,
                     state="readonly", font=mono(10),
                     values=list(self.servicio.nombres())).pack(anchor="w")

        columna_valor = tk.Frame(fila, bg=PALETA["elevado"])
        columna_valor.pack(side="left", padx=(12, 0), fill="x", expand=True)
        self.rotulo(columna_valor, "Nuevo valor").pack(anchor="w")
        self.valor = tk.StringVar(value="0x0")
        ttk.Entry(columna_valor, textvariable=self.valor,
                  font=mono(10)).pack(anchor="w", fill="x")

        ttk.Button(fila, text="Escribir", style="Primario.TButton",
                   command=self.escribir).pack(side="left", padx=(12, 0))
        ttk.Button(fila, text="RESET", style="Peligro.TButton",
                   command=self.reiniciar).pack(side="left", padx=6)

        self.mensaje = tk.Label(self.cuerpo, text="", bg=PALETA["elevado"],
                                fg=PALETA["texto_tenue"], font=mono(9), anchor="w")
        self.mensaje.pack(fill="x", pady=(MARGEN, 0))

    # -- acciones -----------------------------------------------------------

    def escribir(self) -> None:
        nombre = self.registro.get()
        try:
            valor = parsear_entero(self.valor.get())
        except ValorInvalido as exc:
            self._informar(str(exc), "error")
            return

        self.servicio.escribir_nombre(nombre, valor)

        if self.servicio.es_solo_lectura(nombre):
            # No es un error: el hardware descarta la escritura a R0.
            self._informar("R0 esta cableado a cero: la escritura se ignoro.", "aviso")
        else:
            self._informar(f"{nombre} ← {self.servicio.leer_nombre(nombre):#018x}",
                           "exito")
        self.publicar(Evento.REGISTROS_CAMBIADOS, registro=nombre, valor=valor)

    def conmutar_bandera(self, bandera: str) -> None:
        nuevo = self.servicio.alternar_bandera(bandera)
        self._informar(f"Bandera {bandera} ({NOMBRE_BANDERA.get(bandera, '')}) = {nuevo}",
                       "info")
        self.publicar(Evento.REGISTROS_CAMBIADOS, bandera=bandera, valor=nuevo)

    def reiniciar(self) -> None:
        self.servicio.reiniciar()
        self._informar("Estado de RESET: PC = 0x0, SP = 0x…EFFFFFFF.", "aviso")
        self.publicar(Evento.REGISTROS_REINICIADOS)

    # -- pintado ------------------------------------------------------------

    def refrescar(self) -> None:
        """Repinta la tabla. La llama el banco tras cada cambio de estado."""
        datos = self.servicio.instantanea()

        for nombre, (_celda_nombre, celda_codigo, celda_hex, celda_dec) in self._filas.items():
            info = datos["registros"].get(nombre)
            if info is None:
                continue
            valor = info["valor"]
            celda_codigo.configure(text=f"0x{info['codigo']:X}")
            celda_hex.configure(
                text=info["hex"],
                fg=PALETA["texto_debil"] if valor == 0 else PALETA["cian"])
            celda_dec.configure(
                text=decimal_agrupado(info["con_signo"]),
                fg=PALETA["texto_debil"] if valor == 0 else PALETA["texto_tenue"])

            # Un cambio desde el ultimo repintado se resalta en ambar.
            if self._valores_previos.get(nombre, valor) != valor:
                celda_hex.configure(fg=PALETA["ambar"])
            self._valores_previos[nombre] = valor

        for bandera, led in self._leds.items():
            activa = bool(datos["banderas"].get(bandera, 0))
            led.fijar(activa, PALETA["ambar"] if bandera in ("S", "I") else PALETA["ok"])

    def _informar(self, texto: str, severidad: str = "info") -> None:
        colores = {"info": PALETA["texto_tenue"], "exito": PALETA["ok"],
                   "aviso": PALETA["alerta"], "error": PALETA["fallo"]}
        self.mensaje.configure(text=texto, fg=colores.get(severidad, PALETA["texto_tenue"]))
        self.trazar(texto, severidad)

    # -- demostracion suelta ------------------------------------------------

    def preparar_demo(self) -> None:
        if not self.servicio.disponible:
            return
        self.servicio.escribir_nombre("R1", 120)
        self.servicio.escribir_nombre("R2", 5)
        self.servicio.escribir_nombre("PC", 0x00200000)
        self._informar("Registros de demostracion cargados.", "info")


if __name__ == "__main__":
    PanelRegistros.ejecutar_suelto()
