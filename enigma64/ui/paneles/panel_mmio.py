"""
Visor y editor de la I/O mapeada en memoria (MMIO) y Terminal CRT (Integrante 6).

La Tarea 9 asigna una pagina de 4 KiB a cada controlador y coloca sus
registros en desplazamientos fijos de 8 bytes. Este panel permite inspeccionar
y escribir esos registros directamente, e incluye la pantalla emulada interactiva
para el Controlador de Pantalla (Base 0xFF001000).

Recuerda la regla de enrutamiento: cuando A[31:24] == 0xFF la unidad de
memoria bloquea la RAM y activa el Chip Select del bus de perifericos, por eso
estos registros no aparecen en el volcado del panel de memoria.

Arranque suelto:  python -m enigma64.ui.paneles.panel_mmio

Autores: Integrante 5 (Shell base) & Integrante 6 (Terminal CRT y controlador de pantalla)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.bus import Evento
from ..core.formato import ValorInvalido, hex32, hex64, parsear_entero
from ..core.tema import MARGEN, MARGEN_CHICO, PALETA, mono, sans
from ..core.widgets import MonitorPantallaCRT, mezclar
from .base import PanelBase


class PanelMMIO(PanelBase):
    """Inspeccion y edicion de registros MMIO y Monitor de Pantalla CRT."""

    NOMBRE = "mmio"
    TITULO = "I/O mapeada en memoria"
    SUBTITULO = "Integrante 6  ·  Visor/Editor MMIO y Terminal CRT (0xFF001000)"
    ACENTO = PALETA["violeta"]
    CLAVE_SERVICIO = "mmio"
    TAMANO_SUELTO = (960, 1050)

    def construir(self) -> None:
        self._filas_controlador = {}
        self._campos = {}
        self.seleccionado = self.servicio.controladores()[0]

        self._construir_aviso()
        self._construir_lista()
        self.separador()
        self._construir_registros()
        self.separador()
        self._construir_terminal_pantalla()

        self.bus.suscribir(Evento.MMIO_ESCRITO, lambda _m: self.refrescar())
        self.seleccionar(self.seleccionado["clave"])

    # -- construccion -------------------------------------------------------

    def _construir_aviso(self) -> None:
        advertencia = getattr(self.servicio, "advertencia", "")
        if not advertencia:
            return
        marco = tk.Frame(self.cuerpo, bg=mezclar(PALETA["elevado"], PALETA["alerta"], 0.14),
                         highlightthickness=1, highlightbackground=PALETA["alerta"])
        marco.pack(fill="x", pady=(0, MARGEN))
        tk.Label(marco, text="BANCO PROVISIONAL", bg=marco["bg"],
                 fg=PALETA["alerta"], font=sans(8, True), anchor="w").pack(
                     fill="x", padx=11, pady=(8, 0))
        tk.Label(marco, text=advertencia, bg=marco["bg"], fg=PALETA["texto_tenue"],
                 font=sans(9), anchor="w", wraplength=780, justify="left").pack(
                     fill="x", padx=11, pady=(2, 9))

    def _construir_lista(self) -> None:
        self.rotulo(self.cuerpo, "Controladores  ·  una pagina de 4 KiB cada uno").pack(
            anchor="w")

        lista = self.fila()
        lista.pack(fill="x", pady=(8, 0))

        for controlador in self.servicio.controladores():
            fila = tk.Frame(lista, bg=PALETA["elevado"], cursor="hand2",
                            highlightthickness=1, highlightbackground=PALETA["elevado"])
            fila.pack(fill="x", pady=1)

            barra = tk.Frame(fila, bg=controlador["color"], width=4, height=30)
            barra.pack(side="left", fill="y", padx=(2, 10))
            barra.pack_propagate(False)

            columna = tk.Frame(fila, bg=PALETA["elevado"])
            columna.pack(side="left", fill="x", expand=True, pady=4)
            titulo = tk.Label(columna, text=controlador["nombre"], bg=PALETA["elevado"],
                              fg=PALETA["texto"], font=sans(10), anchor="w")
            titulo.pack(fill="x")
            nota = tk.Label(columna, text=controlador["nota"], bg=PALETA["elevado"],
                            fg=PALETA["texto_debil"], font=sans(8), anchor="w")
            nota.pack(fill="x")

            base = tk.Label(fila, text=hex32(controlador["base"]), bg=PALETA["elevado"],
                            fg=controlador["color"], font=mono(10), anchor="e")
            base.pack(side="right", padx=(0, 8))

            for objetivo in (fila, columna, titulo, nota, base, barra):
                objetivo.bind("<Button-1>",
                              lambda _e, c=controlador["clave"]: self.seleccionar(c))
            self._filas_controlador[controlador["clave"]] = (fila, columna, titulo, nota)

    def _construir_registros(self) -> None:
        self.titulo_registros = self.rotulo(self.cuerpo, "Registros")
        self.titulo_registros.pack(anchor="w")

        self.rejilla = self.fila()
        self.rejilla.pack(fill="x", pady=(8, 0))
        self.rejilla.columnconfigure(3, weight=1)

        for columna, texto in enumerate(("Registro", "Direccion", "Valor (64 bits)", "")):
            if not texto:
                continue
            tk.Label(self.rejilla, text=texto.upper(), bg=PALETA["elevado"],
                     fg=PALETA["texto_debil"], font=mono(8, True), anchor="w").grid(
                         row=0, column=columna, sticky="w", pady=(0, 5), padx=(0, 12))

        acciones = self.fila()
        acciones.pack(fill="x", pady=(MARGEN, 0))
        ttk.Button(acciones, text="Releer", command=self.refrescar).pack(side="left")
        ttk.Button(acciones, text="Escribir valores", style="Primario.TButton",
                   command=self.escribir).pack(side="left", padx=6)
        ttk.Button(acciones, text="Reiniciar controladores", style="Peligro.TButton",
                   command=self.reiniciar).pack(side="left")

        self.mensaje = tk.Label(self.cuerpo, text="", bg=PALETA["elevado"],
                                fg=PALETA["texto_tenue"], font=mono(9), anchor="w",
                                wraplength=800, justify="left")
        self.mensaje.pack(fill="x", pady=(MARGEN, 0))

    def _construir_terminal_pantalla(self) -> None:
        """Construye el monitor / terminal CRT de salida emulada para la pantalla."""
        self.terminal_crt = MonitorPantallaCRT(
            self.cuerpo,
            al_emitir_data=self._al_emitir_data_pantalla,
            al_emitir_ctrl=self._al_emitir_ctrl_pantalla,
        )
        self.terminal_crt.pack(fill="both", expand=True, pady=(MARGEN_CHICO, 0))

    # -- seleccion ----------------------------------------------------------

    def seleccionar(self, clave: str) -> None:
        """Cambia el controlador mostrado y repinta su tabla de registros."""
        for controlador in self.servicio.controladores():
            if controlador["clave"] == clave:
                self.seleccionado = controlador
                break

        for otra_clave, (fila, columna, titulo, nota) in self._filas_controlador.items():
            activa = otra_clave == clave
            color = self.seleccionado["color"] if activa else PALETA["elevado"]
            fondo = (mezclar(PALETA["elevado"], self.seleccionado["color"], 0.12)
                     if activa else PALETA["elevado"])
            fila.configure(highlightbackground=color, bg=fondo)
            for objetivo in (columna, titulo, nota):
                objetivo.configure(bg=fondo)

        self._construir_filas_registro()
        self.refrescar()

    def _construir_filas_registro(self) -> None:
        """Rehace la tabla: la interfaz de red renombra los mismos desplazamientos."""
        for hijo in self.rejilla.winfo_children():
            if int(hijo.grid_info().get("row", 0)) > 0:
                hijo.destroy()
        self._campos.clear()

        registros = self.servicio.registros(self.seleccionado["clave"])
        for indice, (desplazamiento, nombre, descripcion) in enumerate(registros, start=1):
            direccion = self.seleccionado["base"] + desplazamiento

            tk.Label(self.rejilla, text=nombre, bg=PALETA["elevado"],
                     fg=PALETA["texto"], font=mono(10, True), anchor="w").grid(
                         row=indice, column=0, sticky="w", pady=3, padx=(0, 12))
            tk.Label(self.rejilla, text=hex32(direccion), bg=PALETA["elevado"],
                     fg=self.seleccionado["color"], font=mono(9), anchor="w").grid(
                         row=indice, column=1, sticky="w", padx=(0, 12))

            variable = tk.StringVar(value=hex64(0))
            ttk.Entry(self.rejilla, textvariable=variable, width=20,
                      font=mono(10)).grid(row=indice, column=2, sticky="w", padx=(0, 12))

            tk.Label(self.rejilla, text=descripcion, bg=PALETA["elevado"],
                     fg=PALETA["texto_debil"], font=sans(8), anchor="w").grid(
                         row=indice, column=3, sticky="w")

            self._campos[desplazamiento] = variable

        self.titulo_registros.configure(
            text=f"REGISTROS  ·  {self.seleccionado['nombre'].upper()}")

    # -- acciones -----------------------------------------------------------

    def refrescar(self) -> None:
        base = self.seleccionado["base"]
        for desplazamiento, variable in self._campos.items():
            variable.set(hex64(self.servicio.leer(base, desplazamiento)))

        # Actualizar monitor CRT si el controlador de pantalla está presente
        ctrl_pantalla = getattr(self.servicio, "controlador_pantalla", None)
        if ctrl_pantalla is not None:
            self.terminal_crt.fijar_contenido(
                lineas=ctrl_pantalla.obtener_lineas(),
                cursor_fila=ctrl_pantalla.cursor_fila,
                cursor_col=ctrl_pantalla.cursor_col,
                count=ctrl_pantalla.count,
                status=ctrl_pantalla.status,
            )

    def escribir(self) -> None:
        base = self.seleccionado["base"]
        escritos = []
        for desplazamiento, variable in self._campos.items():
            try:
                valor = parsear_entero(variable.get())
            except ValorInvalido as exc:
                self._informar(f"{hex32(base + desplazamiento)}: {exc}", "error")
                return
            if valor != self.servicio.leer(base, desplazamiento):
                self.servicio.escribir(base, desplazamiento, valor)
                escritos.append((base + desplazamiento, valor))

        self.refrescar()
        if not escritos:
            self._informar("No habia ningun valor modificado.", "info")
            return

        detalle = ", ".join(f"{hex32(d)} ← {hex64(v)}" for d, v in escritos)
        self._informar(f"{len(escritos)} registro(s) escrito(s): {detalle}", "exito")
        for direccion, valor in escritos:
            self.publicar(Evento.MMIO_ESCRITO, direccion=direccion, valor=valor,
                          controlador=self.seleccionado["clave"])
        # El mapa resalta la region de perifericos al ver la senal.
        self.publicar(Evento.BUS_SENAL, estado="MMIO", direccion=escritos[0][0])

    def reiniciar(self) -> None:
        self.servicio.reiniciar()
        self.refrescar()
        self._informar("Controladores en estado de encendido: STATUS = 1 (listo).",
                       "aviso")

    def _al_emitir_data_pantalla(self, byte_val: int) -> None:
        base_pantalla = 0xFF001000
        self.servicio.escribir(base_pantalla, 0x10, byte_val)
        self.publicar(Evento.MMIO_ESCRITO, direccion=base_pantalla + 0x10, valor=byte_val,
                      controlador="pantalla")
        self.publicar(Evento.BUS_SENAL, estado="MMIO", direccion=base_pantalla + 0x10)
        self.refrescar()

    def _al_emitir_ctrl_pantalla(self, cmd_val: int) -> None:
        base_pantalla = 0xFF001000
        self.servicio.escribir(base_pantalla, 0x00, cmd_val)
        self.publicar(Evento.MMIO_ESCRITO, direccion=base_pantalla, valor=cmd_val,
                      controlador="pantalla")
        self.publicar(Evento.BUS_SENAL, estado="MMIO", direccion=base_pantalla)
        self.refrescar()

    def _informar(self, texto: str, severidad: str = "info") -> None:
        colores = {"info": PALETA["texto_tenue"], "exito": PALETA["ok"],
                   "aviso": PALETA["alerta"], "error": PALETA["fallo"]}
        self.mensaje.configure(text=texto, fg=colores.get(severidad, PALETA["texto_tenue"]))
        self.trazar(texto, severidad)

    # -- demostracion suelta ------------------------------------------------

    def preparar_demo(self) -> None:
        if not self.servicio.disponible:
            return
        self.seleccionar("pantalla")
        self.terminal_crt.demo_saludo()
        self._informar("Demostración activa: mensaje emitido a la terminal CRT (0xFF001000).",
                       "info")


if __name__ == "__main__":
    PanelMMIO.ejecutar_suelto()
