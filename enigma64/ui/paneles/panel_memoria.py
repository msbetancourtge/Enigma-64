"""
Panel del modulo de Memoria RAM y buses (Integrantes 1 y 6).

Muestra el subsistema de memoria tal y como lo describe la Tarea 9:
  * Acceso de 1, 2, 4 u 8 bytes en Big-Endian con control de alineacion natural.
  * Senales del bus de control (READY, MISALIGNED, MMIO, ADDR_FAULT).
  * Grilla visual interactiva con los 8 bancos fisicos de memoria de 64 bits (Tarea 9).
  * Inspector y editor de bits en vivo para conmutar bits (0 <-> 1) y modificar bytes.
  * Volcado hexadecimal clasico de 16 columnas con vista ASCII.
  * Botones de salto rapido a regiones del mapa de memoria de la Tarea 9.

Arranque suelto:  python -m enigma64.ui.paneles.panel_memoria

Autores: Integrante 5 (Shell base) & Integrante 6 (Grilla interactiva y editor de bits)
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from ..core.bus import Evento
from ..core.formato import (
    ValorInvalido, ascii_imprimible, hex32, hex_ancho, parsear_direccion,
    parsear_entero, tamano_legible,
)
from ..core.tema import COLOR_POR_ESTADO, MARGEN, MARGEN_CHICO, PALETA, mono, sans
from ..core.widgets import (
    CampoValor, GrillaBytesInteractiva, InspectorBitsByte, TableroLeds,
    TextoMono,
)
from ..servicios.mapa_memoria import nombre_region
from .base import PanelBase

#: Bytes por linea del volcado hexadecimal.
POR_LINEA = 16
#: Lineas visibles del volcado.
LINEAS = 16
#: Palabras de 64 bits en la grilla interactiva (8 bytes por fila).
FILAS_GRILLA = 16


class PanelMemoria(PanelBase):
    """Lectura, escritura, grilla interactiva y volcado de la memoria fisica."""

    NOMBRE = "memoria"
    TITULO = "Memoria RAM y buses"
    SUBTITULO = "Integrantes 1 & 6  ·  Visor/Editor interactivo y 8 bancos RAM"
    ACENTO = PALETA["cian"]
    CLAVE_SERVICIO = "memoria"
    TAMANO_SUELTO = (960, 1080)

    def construir(self) -> None:
        self.base_volcado: int = 0x00200000
        self.direccion_seleccionada: int = 0x00200000
        self.modo_vista: tk.StringVar = tk.StringVar(value="grilla")

        self._construir_controles()
        self.separador()
        self._construir_bus()
        self._construir_atajos_regiones()
        self._construir_area_visual()
        self._construir_estadisticas()

        # Suscripción a eventos del bus
        self.bus.suscribir(Evento.IR_A_DIRECCION, self._al_pedir_direccion)
        self.bus.suscribir(Evento.PROGRAMA_CARGADO, lambda _m: self.refrescar_volcado())
        self.bus.suscribir(Evento.MEMORIA_REINICIADA, lambda _m: self.refrescar_volcado())

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
        self.mensaje.pack(fill="x", pady=(6, 0))

    def _construir_atajos_regiones(self) -> None:
        """Barra de accesos directos a las regiones clave del mapa de memoria (Tarea 9)."""
        fila = self.fila()
        fila.pack(fill="x", pady=(4, 6))

        tk.Label(fila, text="Saltar a región:", bg=PALETA["elevado"],
                 fg=PALETA["texto_debil"], font=sans(8)).pack(side="left", padx=(0, 6))

        regiones = [
            ("0x00000000", "Vectores"),
            ("0x00001000", "Monitor"),
            ("0x00200000", "Programas"),
            ("0x00201000", "Datos"),
            ("0xEFFFFFF0", "Pila"),
            ("0xFF001000", "MMIO"),
        ]
        for addr, nombre in regiones:
            btn = ttk.Button(fila, text=nombre,
                             command=lambda a=addr: self._saltar_a(a))
            btn.pack(side="left", padx=2)

    def _saltar_a(self, dir_texto: str) -> None:
        self.campo_direccion.texto = dir_texto
        self.ir_a_direccion()

    def _construir_area_visual(self) -> None:
        """Construye el área visual dual: Grilla interactiva y Volcado clásico."""
        encabezado = self.fila()
        encabezado.pack(fill="x", pady=(MARGEN_CHICO, 4))

        self.lbl_titulo_visor = self.rotulo(encabezado, "Visor de Memoria RAM")
        self.lbl_titulo_visor.pack(side="left")

        # Selector de vista (Grilla interactiva vs Volcado clásico)
        marco_modo = tk.Frame(encabezado, bg=PALETA["elevado"])
        marco_modo.pack(side="left", padx=(16, 0))

        rb_grilla = ttk.Radiobutton(marco_modo, text="Grilla Interactiva (8 Bancos)",
                                    variable=self.modo_vista, value="grilla",
                                    command=self._cambiar_modo_vista)
        rb_grilla.pack(side="left", padx=4)

        rb_volcado = ttk.Radiobutton(marco_modo, text="Volcado Clásico (16 B)",
                                     variable=self.modo_vista, value="volcado",
                                     command=self._cambiar_modo_vista)
        rb_volcado.pack(side="left", padx=4)

        # Botones de desplazamiento
        ttk.Button(encabezado, text="▼ Pagina", width=9,
                   command=lambda: self.desplazar(POR_LINEA * LINEAS)).pack(side="right")
        ttk.Button(encabezado, text="▲ Pagina", width=9,
                   command=lambda: self.desplazar(-POR_LINEA * LINEAS)).pack(
                       side="right", padx=4)

        # Contenedor para la Grilla Interactiva
        self.contenedor_grilla = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        self.contenedor_grilla.pack(fill="both", expand=True)

        self.grilla_bytes = GrillaBytesInteractiva(
            self.contenedor_grilla, filas_visibles=FILAS_GRILLA,
            al_seleccionar=self._al_seleccionar_celda_grilla,
            fondo=PALETA["abismo"],
        )
        self.grilla_bytes.pack(fill="both", expand=True, pady=(2, 6))

        # Inspector de bits interactivo desplegado debajo de la grilla
        self.inspector_bits = InspectorBitsByte(
            self.contenedor_grilla,
            al_conmutar_bit=self._al_conmutar_bit_inspector,
            al_guardar_byte=self._al_guardar_byte_inspector,
        )
        self.inspector_bits.pack(fill="x", pady=(2, 4))

        # Contenedor para el Volcado Clásico (oculto por defecto)
        self.contenedor_volcado = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        self.volcado = TextoMono(self.contenedor_volcado, alto=LINEAS + 1, ancho=78, tam=9)
        self.volcado.pack(fill="both", expand=True)
        self.volcado.configurar_etiqueta("cabecera", foreground=PALETA["texto_debil"])
        self.volcado.configurar_etiqueta("direccion", foreground=PALETA["ambar"])
        self.volcado.configurar_etiqueta("datos", foreground=PALETA["cian"])
        self.volcado.configurar_etiqueta("vacio", foreground=PALETA["texto_debil"])
        self.volcado.configurar_etiqueta("ascii", foreground=PALETA["texto_tenue"])

    def _cambiar_modo_vista(self) -> None:
        modo = self.modo_vista.get()
        if modo == "grilla":
            self.contenedor_volcado.pack_forget()
            self.contenedor_grilla.pack(fill="both", expand=True)
            self.lbl_titulo_visor.configure(
                text="Grilla Interactiva  ·  8 Bancos físicos de 64 bits (Tarea 9)")
        else:
            self.contenedor_grilla.pack_forget()
            self.contenedor_volcado.pack(fill="both", expand=True)
            self.lbl_titulo_visor.configure(text="Volcado hexadecimal  ·  Big-Endian (16 B)")
        self.refrescar_volcado()

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
        self.direccion_seleccionada = direccion
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
        self.direccion_seleccionada = direccion
        self.refrescar_volcado()

    def ir_a_direccion(self) -> None:
        try:
            direccion = parsear_direccion(self.campo_direccion.texto)
        except ValorInvalido as exc:
            self._informar(str(exc), "error")
            return
        self.base_volcado = direccion - (direccion % POR_LINEA)
        self.direccion_seleccionada = direccion
        self.refrescar_volcado()
        self._informar(f"Visor situado en {hex32(self.base_volcado)}", "info")

    def desplazar(self, delta: int) -> None:
        self.base_volcado = max(0, self.base_volcado + delta)
        self.refrescar_volcado()

    def reiniciar(self) -> None:
        self.servicio.reiniciar()
        self.leds.marcar(None)
        self._informar("RAM reiniciada: se liberaron todas las paginas.", "aviso")
        self.publicar(Evento.MEMORIA_REINICIADA)
        self.refrescar_volcado()

    # -- interaccion de grilla e inspector ----------------------------------

    def _al_seleccionar_celda_grilla(self, direccion: int, valor: int, banco: int) -> None:
        """Callback al hacer clic en una celda de la grilla interactiva."""
        self.direccion_seleccionada = direccion
        self.campo_direccion.texto = hex32(direccion)
        region = nombre_region(direccion)
        self.inspector_bits.actualizar_byte(direccion, valor, region)
        self._informar(f"Byte seleccionado: {hex32(direccion)} = 0x{valor:02X} (Banco {banco})", "info")

    def _al_conmutar_bit_inspector(self, direccion: int, bit_index: int) -> None:
        """Callback al pulsar un bit en el inspector: lo conmuta en RAM en vivo."""
        nuevo_bit = self.servicio.conmutar_bit(direccion, bit_index)
        nuevo_byte = self.servicio.leer_byte(direccion)
        self._informar(f"Bit {bit_index} conmutado a {nuevo_bit} en {hex32(direccion)} (byte: 0x{nuevo_byte:02X})", "exito")
        self.publicar(Evento.MEMORIA_ESCRITA, direccion=direccion, tamano=1, valor=nuevo_byte, estado="READY")
        self.publicar(Evento.BUS_SENAL, estado="READY", direccion=direccion)
        self.refrescar_volcado()

    def _al_guardar_byte_inspector(self, direccion: int, valor: int) -> None:
        """Callback al guardar un byte modificado desde el inspector."""
        self.servicio.escribir_byte(direccion, valor)
        self._informar(f"Byte escrito en {hex32(direccion)}: 0x{valor:02X} ({valor})", "exito")
        self.publicar(Evento.MEMORIA_ESCRITA, direccion=direccion, tamano=1, valor=valor, estado="READY")
        self.publicar(Evento.BUS_SENAL, estado="READY", direccion=direccion)
        self.refrescar_volcado()

    # -- pintado ------------------------------------------------------------

    def refrescar_volcado(self) -> None:
        """Actualiza la grilla interactiva y el volcado clásico."""
        # 1. Actualizar Grilla Interactiva (16 filas de 8 bytes = palabras de 64b)
        datos_grilla = []
        for fila in range(FILAS_GRILLA):
            base_palabra = self.base_volcado + fila * 8
            fila_bytes = [self.servicio.leer_byte(base_palabra + b) for b in range(8)]
            datos_grilla.append(fila_bytes)
        self.grilla_bytes.fijar_datos(self.base_volcado, datos_grilla)
        self.grilla_bytes.seleccionar_direccion(self.direccion_seleccionada)

        # Actualizar inspector de bits con la dirección seleccionada
        val_sel = self.servicio.leer_byte(self.direccion_seleccionada)
        self.inspector_bits.actualizar_byte(self.direccion_seleccionada, val_sel,
                                           nombre_region(self.direccion_seleccionada))

        # 2. Actualizar Volcado clásico de 16 columnas
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
        self.direccion_seleccionada = direccion
        self.refrescar_volcado()

    # -- demostracion suelta ------------------------------------------------

    def preparar_demo(self) -> None:
        """Siembra la cabecera de un .e64 para que el visor no salga vacio."""
        if not self.servicio.disponible:
            return
        for desplazamiento, byte in enumerate(b"ENIG\x00\x00\x00\x01"):
            self.servicio.escribir(0x00200000 + desplazamiento, byte, 1,
                                   verificar_alineacion=False)
        self.refrescar_volcado()
        self._informar("Datos de demostracion escritos en 0x00200000.", "info")


if __name__ == "__main__":
    PanelMemoria.ejecutar_suelto()
