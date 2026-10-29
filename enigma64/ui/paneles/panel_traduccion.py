"""
Panel del traductor CacaoCore-64 -> Enigma-64 (Tarea 27).

Se carga un .asm de CacaoCore (de los ejemplos del traductor o de disco), se
traduce con las reglas ply.lex del grupo y se ven los dos programas lado a
lado. Al pulsar una linea de un lado se resaltan las lineas que le
corresponden en el otro. Desde aqui el programa traducido se envia al
Cargador/RAM, se ejecuta y, para los tres algoritmos clasicos, se contrasta
con los resultados oficiales de la Tarea 10.

El panel solo habla con su servicio (`servicios/traduccion.py`); no importa ni
el traductor ni el hardware.

Arranque suelto:  python -m enigma64.ui.paneles.panel_traduccion

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import pathlib
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Optional

from ..core.bus import Evento
from ..core.formato import hex32
from ..core.tema import MARGEN, PALETA, mono, sans
from ..core.widgets import TextoMono
from .base import PanelBase


class PanelTraduccion(PanelBase):
    """Traduccion LEX de CacaoCore-64 a Enigma-64, carga y ejecucion."""

    NOMBRE = "traduccion"
    TITULO = "Traductor CacaoCore-64 → Enigma-64"
    SUBTITULO = "Tarea 27  ·  traduccion con ply.lex, carga y ejecucion"
    ACENTO = PALETA["cian"]
    CLAVE_SERVICIO = "traduccion"
    TAMANO_SUELTO = (1180, 800)
    DESPLAZABLE_SUELTO = True

    def construir(self) -> None:
        self.traduccion: Optional[dict] = None
        self.clave: Optional[str] = None
        self._ejemplos = {e["nombre"]: e for e in self.servicio.ejemplos()}

        self._construir_fuente()
        self._construir_editores()
        self._construir_datos()
        self._construir_acciones()
        self._construir_resultado()

    def preparar_demo(self) -> None:
        if not getattr(self.servicio, "disponible", False) or not self._ejemplos:
            return
        primero = next(iter(self._ejemplos))
        self.selector.set(primero)
        self.abrir_ejemplo(primero)

    # -- construccion -------------------------------------------------------

    def _construir_fuente(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")
        self.rotulo(fila, "Programa CacaoCore").pack(side="left", padx=(0, 8))
        self.selector = ttk.Combobox(fila, values=list(self._ejemplos), state="readonly",
                                     width=26)
        self.selector.pack(side="left")
        self.selector.bind("<<ComboboxSelected>>",
                           lambda _e: self.abrir_ejemplo(self.selector.get()))
        ttk.Button(fila, text="Abrir .asm...", command=self.examinar).pack(side="left", padx=6)
        self.origen = tk.Label(fila, text="", bg=PALETA["elevado"],
                               fg=PALETA["texto_debil"], font=mono(8), anchor="w")
        self.origen.pack(side="left", fill="x", expand=True, padx=(6, 0))

    def _construir_editores(self) -> None:
        marco = self.fila()
        marco.pack(fill="both", expand=True, pady=(MARGEN, 0))
        marco.columnconfigure(0, weight=2, uniform="lados")
        marco.columnconfigure(1, weight=3, uniform="lados")
        marco.rowconfigure(1, weight=1)

        self.rotulo(marco, "CacaoCore-64 (editable)").grid(row=0, column=0, sticky="w",
                                                           pady=(0, 4))
        self.rotulo(marco, "Enigma-64 traducido por LEX").grid(row=0, column=1, sticky="w",
                                                               padx=(8, 0), pady=(0, 4))
        self.cacao = TextoMono(marco, alto=24, ancho=34, editable=True, tam=9)
        self.cacao.grid(row=1, column=0, sticky="nsew")
        self.enigma = TextoMono(marco, alto=24, ancho=52, tam=9)
        self.enigma.grid(row=1, column=1, sticky="nsew", padx=(8, 0))

        for lado in (self.cacao, self.enigma):
            lado.configurar_etiqueta("foco", background=PALETA["seleccion"])
        self.cacao.configurar_etiqueta("error", foreground=PALETA["fallo"])
        self.enigma.configurar_etiqueta("comentario", foreground=PALETA["texto_debil"])
        self.enigma.configurar_etiqueta("etiqueta", foreground=PALETA["ambar"])

        self.cacao.texto.bind("<ButtonRelease-1>", self._al_pulsar_cacao, add="+")
        self.enigma.texto.bind("<ButtonRelease-1>", self._al_pulsar_enigma, add="+")

    def _construir_datos(self) -> None:
        datos = self.fila()
        datos.pack(fill="x", pady=(MARGEN, 0))
        self._datos = {}
        for clave, etiqueta in (("lineas", "Lineas CacaoCore"),
                                ("instrucciones", "Lineas Enigma-64"),
                                ("bytes", "Codigo maquina"),
                                ("variables", "Variables .data"),
                                ("avisos", "Avisos / errores")):
            columna = tk.Frame(datos, bg=PALETA["elevado"])
            columna.pack(side="left", padx=(0, 22))
            self.rotulo(columna, etiqueta).pack(anchor="w")
            valor = self.texto_dato(columna, "—", tam=10, negrita=True)
            valor.pack(anchor="w")
            self._datos[clave] = valor

    def _construir_acciones(self) -> None:
        fila = self.fila()
        fila.pack(fill="x", pady=(MARGEN, 0))
        ttk.Button(fila, text="Traducir", style="Primario.TButton",
                   command=self.traducir).pack(side="left")
        self.boton_enviar = ttk.Button(fila, text="Enviar al Cargador / RAM",
                                       command=self.enviar)
        self.boton_enviar.pack(side="left", padx=6)
        self.boton_ejecutar = ttk.Button(fila, text="Ejecutar", command=self.ejecutar)
        self.boton_ejecutar.pack(side="left")
        ttk.Button(fila, text="Guardar .asm Enigma...",
                   command=self.guardar).pack(side="left", padx=6)
        self.boton_enviar.state(["disabled"])
        self.boton_ejecutar.state(["disabled"])
        if not self.servicio.puede_ejecutar:
            tk.Label(fila, text="Ejecutar necesita la Unidad de Control (Integrante 3)",
                     bg=PALETA["elevado"], fg=PALETA["texto_debil"],
                     font=sans(8)).pack(side="left", padx=(10, 0))

    def _construir_resultado(self) -> None:
        marco = tk.Frame(self.cuerpo, bg=PALETA["borde"])
        marco.pack(fill="x", pady=(MARGEN, 0))
        self.caja = tk.Frame(marco, bg=PALETA["abismo"])
        self.caja.pack(fill="x", padx=1, pady=1)

        self.titulo_resultado = tk.Label(self.caja, text="SIN TRADUCIR",
                                         bg=PALETA["abismo"], fg=PALETA["texto_debil"],
                                         font=sans(9, True), anchor="w")
        self.titulo_resultado.pack(fill="x", padx=12, pady=(10, 4))
        self.detalle_resultado = tk.Label(
            self.caja, text="Elige un programa de CacaoCore y pulsa Traducir.",
            bg=PALETA["abismo"], fg=PALETA["texto_tenue"], font=mono(9),
            anchor="w", justify="left", wraplength=1000)
        self.detalle_resultado.pack(fill="x", padx=12, pady=(0, 10))

    # -- fuente -------------------------------------------------------------

    def abrir_ejemplo(self, nombre: str) -> None:
        ejemplo = self._ejemplos.get(nombre)
        if ejemplo is not None:
            self.abrir_ruta(ejemplo["ruta"])

    def examinar(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona un programa en ensamblador de CacaoCore-64",
            filetypes=[("Ensamblador CacaoCore-64", "*.asm"),
                       ("Todos los archivos", "*.*")])
        if ruta:
            self.abrir_ruta(ruta)

    def abrir_ruta(self, ruta: str) -> None:
        try:
            fuente = self.servicio.leer_archivo(ruta)
        except Exception as exc:
            self._fallo(f"NO SE PUDO LEER · {type(exc).__name__}", str(exc))
            return
        self.clave = pathlib.Path(ruta).stem
        self.origen.configure(text=ruta)
        self.cacao.fijar(fuente)
        self.traducir()

    # -- acciones -----------------------------------------------------------

    def traducir(self) -> None:
        fuente = self.cacao.obtener()
        try:
            self.traduccion = self.servicio.traducir(fuente)
        except Exception as exc:
            self.traduccion = None
            self._habilitar(False)
            self._fallo(f"TRADUCCION FALLIDA · {type(exc).__name__}", str(exc))
            return

        t = self.traduccion
        self._pintar_enigma(t["codigo"])
        self._marcar_errores(t["errores"])
        self._pintar_datos(fuente, t)
        self._habilitar(t["ok"])

        mensajes = [f"L{linea}: {texto}" for linea, texto in t["errores"]]
        if t["error_ensamblado"]:
            mensajes.append(f"ensamblador: {t['error_ensamblado']}")
        avisos = [f"aviso L{linea}: {texto}" for linea, texto in t["avisos"]]

        if t["ok"]:
            self._exito("TRADUCCION CORRECTA", "\n".join([
                f"{len(t['binario'])} bytes de codigo maquina en {hex32(t['base_codigo'])}"
                f"  ·  datos en {hex32(t['base_datos'])}",
                *avisos[:4],
            ]))
        else:
            self._fallo("LA TRADUCCION TIENE ERRORES", "\n".join(mensajes[:6] + avisos[:2]))
        self.publicar(Evento.TRADUCCION_REALIZADA, ok=t["ok"], clave=self.clave,
                      errores=len(t["errores"]), avisos=len(t["avisos"]))

    def enviar(self) -> None:
        if not self.traduccion or not self.traduccion["ok"]:
            self._fallo("NADA QUE CARGAR", "Traduce primero un programa sin errores.")
            return
        try:
            informe = self.servicio.enviar_a_ram(self.traduccion)
        except Exception as exc:
            self._fallo(f"CARGA RECHAZADA · {type(exc).__name__}", str(exc))
            self.publicar(Evento.CARGA_RECHAZADA, motivo=str(exc))
            return

        self._exito("PROGRAMA TRADUCIDO EN RAM", "\n".join([
            f"{informe['tamano_total']} bytes  ·  {hex32(informe['direccion_base'])} → "
            f"{hex32(informe['direccion_final'])}",
            f"entry point {informe['entry_point_hex']}  ·  "
            f"{informe['bytes_datos']} bytes de .data sembrados en "
            f"{hex32(self.traduccion['base_datos'])}",
        ]))
        self.publicar(Evento.PROGRAMA_CARGADO, **informe)
        self.publicar(Evento.IR_A_DIRECCION, direccion=informe["direccion_base"])

    def ejecutar(self) -> None:
        if not self.traduccion or not self.traduccion["ok"]:
            return
        try:
            estado = self.servicio.ejecutar()
            variables = self.servicio.leer_variables(self.traduccion)
            veredicto = self.servicio.verificar(self.clave, self.traduccion)
        except Exception as exc:
            self._fallo(f"NO SE PUDO EJECUTAR · {type(exc).__name__}", str(exc))
            return

        lineas = [
            f"{estado['ciclos']} ciclos  ·  {estado['instrucciones']} instrucciones  ·  "
            f"{'detenido en HLT' if estado['detenido'] else 'sin HLT'}",
            "  ".join(f"{nombre} = {'—' if valor is None else valor}"
                      for nombre, _d, valor in variables),
        ]
        self.publicar(Evento.CPU_AVANZO, fase=estado["fase"], ciclos=estado["ciclos"],
                      instrucciones=estado["instrucciones"], detenido=estado["detenido"])
        # Pide al volcado de memoria que se refresque sobre la zona de datos.
        self.publicar(Evento.IR_A_DIRECCION, direccion=self.traduccion["base_datos"])

        if veredicto is None:
            self._exito("EJECUCION TERMINADA", "\n".join(lineas))
            return
        self.publicar(Evento.TRADUCCION_VERIFICADA, clave=self.clave, ok=veredicto["ok"])
        if veredicto["ok"]:
            self._exito(f"VERIFICADO · {veredicto['etiqueta']}", "\n".join(lineas))
        else:
            esperado = ", ".join(f"{n} = {v}" for n, v in veredicto["esperado"].items())
            self._fallo(f"NO COINCIDE · {veredicto['etiqueta']}",
                        "\n".join(lineas + [f"esperado  {esperado}"]))

    def guardar(self) -> None:
        if not self.traduccion:
            self._fallo("NADA QUE GUARDAR", "Traduce primero un programa.")
            return
        sugerido = f"{self.clave or 'programa'}_enigma.asm"
        ruta = filedialog.asksaveasfilename(
            title="Guardar el ensamblador de Enigma-64", initialfile=sugerido,
            defaultextension=".asm",
            filetypes=[("Ensamblador Enigma-64", "*.asm"), ("Todos los archivos", "*.*")])
        if not ruta:
            return
        try:
            pathlib.Path(ruta).write_text(self.traduccion["codigo"], encoding="utf-8")
        except Exception as exc:
            self._fallo(f"NO SE PUDO GUARDAR · {type(exc).__name__}", str(exc))
            return
        self.trazar(f"traduccion guardada en {ruta}", "exito")

    # -- correspondencia lado a lado ----------------------------------------

    def _al_pulsar_cacao(self, _evento=None) -> None:
        self.resaltar_desde_cacao(int(self.cacao.texto.index("insert").split(".")[0]))

    def _al_pulsar_enigma(self, _evento=None) -> None:
        linea = int(self.enigma.texto.index("insert").split(".")[0])
        if self.traduccion and linea in self.traduccion["correspondencia"]:
            self.resaltar_desde_cacao(self.traduccion["correspondencia"][linea])

    def resaltar_desde_cacao(self, linea_cacao: int) -> list:
        """Resalta una linea de CacaoCore y todas las de Enigma-64 que genero."""
        for lado in (self.cacao, self.enigma):
            lado.texto.tag_remove("foco", "1.0", "end")
        if not self.traduccion:
            return []
        destino = sorted(n for n, origen in self.traduccion["correspondencia"].items()
                         if origen == linea_cacao)
        if not destino:
            return []
        self.cacao.texto.tag_add("foco", f"{linea_cacao}.0", f"{linea_cacao}.end+1c")
        for numero in destino:
            self.enigma.texto.tag_add("foco", f"{numero}.0", f"{numero}.end+1c")
        self.enigma.texto.see(f"{destino[0]}.0")
        self.cacao.texto.see(f"{linea_cacao}.0")
        return destino

    # -- pintado ------------------------------------------------------------

    def _pintar_enigma(self, codigo: str) -> None:
        self.enigma.limpiar()
        for linea in codigo.splitlines():
            instruccion, separador, comentario = linea.partition(";")
            if not instruccion.strip():
                self.enigma.anexar(linea + "\n", "comentario", autodesplazar=False)
                continue
            etiqueta = "etiqueta" if instruccion.rstrip().endswith(":") else None
            self.enigma.anexar(instruccion, etiqueta, autodesplazar=False)
            if separador:
                self.enigma.anexar(separador + comentario, "comentario", autodesplazar=False)
            self.enigma.anexar("\n", autodesplazar=False)

    def _marcar_errores(self, errores) -> None:
        self.cacao.texto.tag_remove("error", "1.0", "end")
        for linea, _texto in errores:
            if linea > 0:
                self.cacao.texto.tag_add("error", f"{linea}.0", f"{linea}.end")

    def _pintar_datos(self, fuente: str, t: dict) -> None:
        self._datos["lineas"].configure(text=str(len(fuente.splitlines())))
        self._datos["instrucciones"].configure(text=str(len(t["codigo"].splitlines())))
        self._datos["bytes"].configure(
            text=f"{len(t['binario'])} bytes" if t["binario"] is not None else "—")
        self._datos["variables"].configure(text=str(len(t["variables"])))
        self._datos["avisos"].configure(
            text=f"{len(t['avisos'])} / {len(t['errores'])}",
            fg=PALETA["fallo"] if t["errores"] else PALETA["cian"])

    def _habilitar(self, ok: bool) -> None:
        self.boton_enviar.state(["!disabled"] if ok else ["disabled"])
        puede = ok and self.servicio.puede_ejecutar
        self.boton_ejecutar.state(["!disabled"] if puede else ["disabled"])

    def _exito(self, titulo: str, detalle: str) -> None:
        self.caja.master.configure(bg=PALETA["ok"])
        self.titulo_resultado.configure(text=titulo, fg=PALETA["ok"])
        self.detalle_resultado.configure(text=detalle, fg=PALETA["texto_tenue"])
        self.trazar(titulo.lower(), "exito")

    def _fallo(self, titulo: str, detalle: str) -> None:
        self.caja.master.configure(bg=PALETA["fallo"])
        self.titulo_resultado.configure(text=titulo, fg=PALETA["fallo"])
        self.detalle_resultado.configure(text=detalle, fg=PALETA["texto_tenue"])
        self.trazar(f"{titulo}: {detalle}", "error")


if __name__ == "__main__":
    PanelTraduccion.ejecutar_suelto()
