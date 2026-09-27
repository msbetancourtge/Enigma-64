"""
Panel del modulo de Memoria RAM y buses (Integrante 1).

Muestra el subsistema de memoria tal y como lo describe la Tarea 9: acceso de
1, 2, 4 u 8 bytes en Big-Endian, control de alineacion natural, enrutamiento
hacia MMIO y las senales del bus de control.

Arranque suelto:  python -m enigma64.ui.paneles.panel_memoria

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.bus import Evento
from ..core.formato import (
    ValorInvalido, ascii_imprimible, hex32, hex_ancho, parsear_direccion,
    parsear_entero, tamano_legible,
)
from ..core.tema import COLOR_POR_ESTADO, MARGEN, PALETA, mono
from ..core.widgets import CampoValor, TableroLeds, TextoMono
from ..servicios.mapa_memoria import nombre_region
from .base import PanelBase

#: Bytes por linea del volcado hexadecimal.
POR_LINEA = 16
#: Lineas visibles del volcado.
LINEAS = 16


class PanelMemoria(PanelBase):
    """Lectura, escritura y volcado de la memoria fisica."""

    NOMBRE = "memoria"
    TITULO = "Memoria RAM y buses"
    SUBTITULO = "Integrante 1  ·  enigma64.memoria"
    ACENTO = PALETA["cian"]
    CLAVE_SERVICIO = "memoria"
    TAMANO_SUELTO = (900, 720)

    def construir(self) -> None:
        self.base_volcado = 0x00200000
        self._construir_controles()
        self.separador()
        self._construir_bus()
        self._construir_volcado()
        self._construir_estadisticas()

        # Quien quiera llevarme a una direccion lo pide por el bus; no me
        # llama directamente ningun otro panel.
        self.bus.suscribir(Evento.IR_A_DIRECCION, self._al_pedir_direccion)

        self.refrescar_volcado()

    # -- construccion -------------------------------------------------------

    def _construir_controles(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")

        self.campo_direccion = CampoValor(fila, "Direccion", "0x00200000", ancho=20)
        self.campo_direccion.pack(side="left")

        columna_tam = tk.Frame(fila, bg=PALETA["elevado"])
        columna_tam.pack(side="left", padx=(12, 0))
        self.rotulo(columna_tam, "Tamano de acceso").pack(anchor="w")
        self.tamano = tk.StringVar(value="8")
        combo = ttk.Combobox(columna_tam, textvariable=self.tamano, width=6,
                             state="readonly", font=mono(10),
                             values=[str(t) for t in self.servicio.tamanos_validos()])
        combo.pack(anchor="w")

        self.campo_valor = CampoValor(fila, "Valor a escribir", "0x0000000000000000",
                                      ancho=22)
        self.campo_valor.pack(side="left", padx=(12, 0))

        botones = self.fila()
        botones.pack(fill="x", pady=(MARGEN, 0))
        ttk.Button(botones, text="Leer", command=self.leer).pack(side="left")
        ttk.Button(botones, text="Escribir", style="Primario.TButton",
                   command=self.escribir).pack(side="left", padx=6)
        ttk.Button(botones, text="Ir a la direccion",
                   command=self.ir_a_direccion).pack(side="left", padx=(6, 0))
        ttk.Button(botones, text="Reiniciar RAM", style="Peligro.TButton",
                   command=self.reiniciar).pack(side="left", padx=6)

        self.verificar_alineacion = tk.BooleanVar(value=True)
        ttk.Checkbutton(botones, text="Verificar alineacion natural",
                        variable=self.verificar_alineacion).pack(side="left", padx=(14, 0))

    def _construir_bus(self) -> None:
        self.rotulo(self.cuerpo, "Senal del bus de control").pack(anchor="w")
        self.leds = TableroLeds(self.cuerpo, self.servicio.senales(), COLOR_POR_ESTADO)
        self.leds.pack(anchor="w", pady=(6, 0))

        self.mensaje = tk.Label(self.cuerpo, text="", bg=PALETA["elevado"],
                                fg=PALETA["texto_tenue"], font=mono(9), anchor="w")
        self.mensaje.pack(fill="x", pady=(8, 0))

    def _construir_volcado(self) -> None:
        encabezado = self.fila()
        encabezado.pack(fill="x", pady=(MARGEN, 4))
        self.rotulo(encabezado, "Volcado hexadecimal  ·  Big-Endian").pack(side="left")

        ttk.Button(encabezado, text="▲ Pagina", width=10,
                   command=lambda: self.desplazar(-POR_LINEA * LINEAS)).pack(side="right")
        ttk.Button(encabezado, text="▼ Pagina", width=10,
                   command=lambda: self.desplazar(POR_LINEA * LINEAS)).pack(
                       side="right", padx=4)

        self.volcado = TextoMono(self.cuerpo, alto=LINEAS + 1, ancho=78, tam=9)
        self.volcado.pack(fill="both", expand=True)
        self.volcado.configurar_etiqueta("cabecera", foreground=PALETA["texto_debil"])
        self.volcado.configurar_etiqueta("direccion", foreground=PALETA["ambar"])
        self.volcado.configurar_etiqueta("datos", foreground=PALETA["cian"])
        self.volcado.configurar_etiqueta("vacio", foreground=PALETA["texto_debil"])
        self.volcado.configurar_etiqueta("ascii", foreground=PALETA["texto_tenue"])

    def _construir_estadisticas(self) -> None:
        fila = self.fila()
        fila.pack(fill="x", pady=(MARGEN, 0))
        self.estadisticas = {}
        for clave, etiqueta in (("paginas", "Paginas asignadas"),
                                ("bytes", "Memoria reservada"),
                                ("tamano_pagina", "Tamano de pagina"),
                                ("region", "Region actual")):
            columna = tk.Frame(fila, bg=PALETA["elevado"])
            columna.pack(side="left", padx=(0, 26))
            self.rotulo(columna, etiqueta).pack(anchor="w")
            valor = self.texto_dato(columna, "—", tam=11, negrita=True)
            valor.pack(anchor="w")
            self.estadisticas[clave] = valor

    # -- acciones -----------------------------------------------------------

    def _leer_campos(self):
        """Devuelve (direccion, tamano) o None si el usuario escribio algo raro."""
        try:
            direccion = parsear_direccion(self.campo_direccion.texto)
        except ValorInvalido as exc:
            self._informar(str(exc), "error")
            return None
        return direccion, int(self.tamano.get())

    def leer(self) -> None:
        campos = self._leer_campos()
        if campos is None:
            return
        direccion, tamano = campos

        dato, estado = self.servicio.leer(direccion, tamano,
                                          self.verificar_alineacion.get())
        self.leds.marcar(estado)

        if dato is None:
            self._informar(f"{estado}  ·  lectura de {tamano} B en {hex32(direccion)} "
                           f"rechazada por el bus", "error")
        else:
            self.campo_valor.texto = hex_ancho(dato, tamano)
            self._informar(f"{estado}  ·  {hex32(direccion)} → {hex_ancho(dato, tamano)}"
                           f"  ({tamano} B)", "exito")

        self.publicar(Evento.MEMORIA_LEIDA, direccion=direccion, tamano=tamano,
                      valor=dato, estado=estado)
        self.publicar(Evento.BUS_SENAL, estado=estado, direccion=direccion)
        self.base_volcado = direccion - (direccion % POR_LINEA)
        self.refrescar_volcado()

    def escribir(self) -> None:
        campos = self._leer_campos()
        if campos is None:
            return
        direccion, tamano = campos

        try:
            valor = parsear_entero(self.campo_valor.texto)
        except ValorInvalido as exc:
            self._informar(str(exc), "error")
            return

        _, estado = self.servicio.escribir(direccion, valor, tamano,
                                           self.verificar_alineacion.get())
        self.leds.marcar(estado)

        if estado != "READY":
            self._informar(f"{estado}  ·  escritura de {tamano} B en "
                           f"{hex32(direccion)} rechazada por el bus", "error")
        else:
            self._informar(f"{estado}  ·  {hex_ancho(valor, tamano)} → "
                           f"{hex32(direccion)}  ({tamano} B)", "exito")

        self.publicar(Evento.MEMORIA_ESCRITA, direccion=direccion, tamano=tamano,
                      valor=valor, estado=estado)
        self.publicar(Evento.BUS_SENAL, estado=estado, direccion=direccion)
        self.base_volcado = direccion - (direccion % POR_LINEA)
        self.refrescar_volcado()

    def ir_a_direccion(self) -> None:
        try:
            direccion = parsear_direccion(self.campo_direccion.texto)
        except ValorInvalido as exc:
            self._informar(str(exc), "error")
            return
        self.base_volcado = direccion - (direccion % POR_LINEA)
        self.refrescar_volcado()
        self._informar(f"Volcado situado en {hex32(self.base_volcado)}", "info")

    def desplazar(self, delta: int) -> None:
        self.base_volcado = max(0, self.base_volcado + delta)
        self.refrescar_volcado()

    def reiniciar(self) -> None:
        self.servicio.reiniciar()
        self.leds.marcar(None)
        self._informar("RAM reiniciada: se liberaron todas las paginas.", "aviso")
        self.publicar(Evento.MEMORIA_REINICIADA)
        self.refrescar_volcado()

    # -- pintado ------------------------------------------------------------

    def refrescar_volcado(self) -> None:
        """Vuelve a dibujar las 16 lineas del volcado desde `base_volcado`."""
        self.volcado.limpiar()
        cabecera = ("DIRECCION    " + " ".join(f"{i:02X}" for i in range(POR_LINEA))
                    + "   ASCII\n")
        self.volcado.anexar(cabecera, "cabecera")

        for linea in range(LINEAS):
            inicio = self.base_volcado + linea * POR_LINEA
            bytes_linea = [self.servicio.leer_byte(inicio + i) for i in range(POR_LINEA)]
            vivo = any(bytes_linea)

            self.volcado.anexar(f"{hex32(inicio)}  ", "direccion", autodesplazar=False)
            self.volcado.anexar(" ".join(f"{b:02X}" for b in bytes_linea),
                                "datos" if vivo else "vacio", autodesplazar=False)
            self.volcado.anexar("  " + "".join(ascii_imprimible(b) for b in bytes_linea)
                                + "\n", "ascii" if vivo else "vacio",
                                autodesplazar=False)

        self._refrescar_estadisticas()

    def _refrescar_estadisticas(self) -> None:
        datos = self.servicio.estadisticas()
        self.estadisticas["paginas"].configure(text=str(datos["paginas"]))
        self.estadisticas["bytes"].configure(text=tamano_legible(datos["bytes"]))
        self.estadisticas["tamano_pagina"].configure(
            text=tamano_legible(datos["tamano_pagina"]))
        region = nombre_region(self.base_volcado)
        self.estadisticas["region"].configure(
            text=region,
            fg=PALETA["fallo"] if region == "No mapeado" else PALETA["cian"])

    def _informar(self, texto: str, severidad: str = "info") -> None:
        colores = {"info": PALETA["texto_tenue"], "exito": PALETA["ok"],
                   "aviso": PALETA["alerta"], "error": PALETA["fallo"]}
        self.mensaje.configure(text=texto, fg=colores.get(severidad, PALETA["texto_tenue"]))
        self.trazar(texto, severidad)

    # -- reaccion a eventos ajenos -----------------------------------------

    def _al_pedir_direccion(self, mensaje) -> None:
        """Otro panel pidio ver una direccion; nadie me llamo directamente."""
        direccion = mensaje.get("direccion")
        if direccion is None:
            return
        self.campo_direccion.texto = hex32(direccion)
        self.base_volcado = direccion - (direccion % POR_LINEA)
        self.refrescar_volcado()

    # -- demostracion suelta ------------------------------------------------

    def preparar_demo(self) -> None:
        """Siembra la cabecera de un .e64 para que el volcado no salga vacio."""
        if not self.servicio.disponible:
            return
        for desplazamiento, byte in enumerate(b"ENIG\x00\x00\x00\x01"):
            self.servicio.escribir(0x00200000 + desplazamiento, byte, 1,
                                   verificar_alineacion=False)
        self.refrescar_volcado()
        self._informar("Datos de demostracion escritos en 0x00200000.", "info")


if __name__ == "__main__":
    PanelMemoria.ejecutar_suelto()
