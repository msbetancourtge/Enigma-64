"""
Panel de la Unidad de Control (Integrante 3).

Visualiza la maquina de estados multiciclo descrita en la Tarea 9:
FETCH, DECODE, EXECUTE, MEMORY y WRITE-BACK, con los registros
microarquitectonicos de la ruta interna de datos (MAR, MDR, IR, A, B y Z) y el
buffer de prebusqueda que compensa las instrucciones de longitud variable.

El modulo `enigma64/cpu.py` todavia no existe. Este panel se escribio antes a
proposito: mientras falte, muestra en pantalla el contrato que debe cumplir, y
el dia que se fusione la rama del Integrante 3 se enciende solo.

Arranque suelto:  python -m enigma64.ui.paneles.panel_cpu

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.bus import Evento
from ..core.formato import hex64
from ..core.tema import MARGEN, PALETA, mono, sans
from ..core.widgets import Insignia, TextoMono, mezclar
from .base import PanelBase

#: Que hace cada fase, resumido del documento.
DESCRIPCION_FASE = {
    "FETCH": "PC → MAR; la memoria entrega la palabra al MDR y el opcode pasa al IR.",
    "DECODE": "El PLA desglosa el IR, comprueba privilegios y carga los latches A y B.",
    "EXECUTE": "La ALU opera sobre A y B; el resultado queda en Z y se calculan las banderas.",
    "MEMORY": "Solo en LOAD/STORE: Z pasa al MAR y se comprueba la alineacion.",
    "WRITE-BACK": "El resultado vuelve al banco de registros; se atienden DMA e interrupciones.",
}


class PanelCPU(PanelBase):
    """Vista en vivo de la maquina de estados de la Unidad de Control."""

    NOMBRE = "cpu"
    TITULO = "Unidad de Control (FSM)"
    SUBTITULO = "Integrante 3  ·  enigma64.cpu"
    ACENTO = PALETA["violeta"]
    CLAVE_SERVICIO = "cpu"
    TAMANO_SUELTO = (880, 700)

    def construir(self) -> None:
        self._cajas_fase = {}
        self._celdas_micro = {}

        self._construir_controles()
        self.separador()
        self._construir_fases()
        self.separador()
        self._construir_micro()
        self._construir_prefetch()

        self.refrescar()

    # -- construccion -------------------------------------------------------

    def _construir_controles(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")

        ttk.Button(fila, text="Paso (una fase)",
                   command=lambda: self._avanzar("paso")).pack(side="left")
        ttk.Button(fila, text="Instruccion completa", style="Primario.TButton",
                   command=lambda: self._avanzar("paso_instruccion")).pack(
                       side="left", padx=6)
        ttk.Button(fila, text="Ejecutar hasta HLT",
                   command=lambda: self._avanzar("ejecutar")).pack(side="left")
        ttk.Button(fila, text="RESET", style="Peligro.TButton",
                   command=self.reiniciar).pack(side="left", padx=6)

        self.insignia = Insignia(fila, ancho=112, alto=22)
        self.insignia.pack(side="right", pady=2)

        contadores = self.fila()
        contadores.pack(fill="x", pady=(MARGEN, 0))
        self._contadores = {}
        for clave, etiqueta in (("ciclos", "Ciclos de reloj"),
                                ("instrucciones", "Instrucciones completadas")):
            columna = tk.Frame(contadores, bg=PALETA["elevado"])
            columna.pack(side="left", padx=(0, 30))
            self.rotulo(columna, etiqueta).pack(anchor="w")
            valor = self.texto_dato(columna, "0", tam=13, negrita=True)
            valor.pack(anchor="w")
            self._contadores[clave] = valor

        self.mensaje = tk.Label(self.cuerpo, text="", bg=PALETA["elevado"],
                                fg=PALETA["texto_tenue"], font=mono(9), anchor="w",
                                wraplength=760, justify="left")
        self.mensaje.pack(fill="x", pady=(MARGEN, 0))

    def _construir_fases(self) -> None:
        self.rotulo(self.cuerpo, "Maquina de estados multiciclo").pack(anchor="w")

        tira = self.fila()
        tira.pack(fill="x", pady=(8, 0))
        fases = self.servicio.fases()
        for indice, fase in enumerate(fases):
            caja = tk.Label(tira, text=fase, bg=PALETA["abismo"],
                            fg=PALETA["texto_debil"], font=mono(9, True),
                            padx=10, pady=7, highlightthickness=1,
                            highlightbackground=PALETA["borde"])
            caja.pack(side="left", fill="x", expand=True)
            self._cajas_fase[fase] = caja
            if indice < len(fases) - 1:
                tk.Label(tira, text="→", bg=PALETA["elevado"],
                         fg=PALETA["texto_debil"], font=mono(10)).pack(side="left", padx=2)

        self.detalle_fase = tk.Label(self.cuerpo, text="", bg=PALETA["elevado"],
                                     fg=PALETA["texto_tenue"], font=sans(9),
                                     anchor="w", wraplength=760, justify="left")
        self.detalle_fase.pack(fill="x", pady=(9, 0))

    def _construir_micro(self) -> None:
        self.rotulo(self.cuerpo,
                    "Registros microarquitectonicos  ·  ruta interna de datos").pack(
                        anchor="w")

        rejilla = self.fila()
        rejilla.pack(fill="x", pady=(8, 0))
        rejilla.columnconfigure(1, weight=1)
        rejilla.columnconfigure(3, weight=1)

        for indice, nombre in enumerate(self.servicio.micro_registros()):
            fila, columna = divmod(indice, 2)
            tk.Label(rejilla, text=nombre, bg=PALETA["elevado"],
                     fg=PALETA["texto_tenue"], font=mono(10, True), width=5,
                     anchor="w").grid(row=fila, column=columna * 2, sticky="w",
                                      pady=2, padx=(0, 8))
            celda = tk.Label(rejilla, text=hex64(0), bg=PALETA["elevado"],
                             fg=PALETA["texto_debil"], font=mono(10), anchor="w")
            celda.grid(row=fila, column=columna * 2 + 1, sticky="w", padx=(0, 26))
            self._celdas_micro[nombre] = celda

    def _construir_prefetch(self) -> None:
        self.rotulo(self.cuerpo,
                    "Buffer de prebusqueda  ·  16 bytes").pack(anchor="w",
                                                               pady=(MARGEN, 6))
        self.prefetch = self.texto_dato(self.cuerpo, "—", color=PALETA["texto_debil"],
                                        tam=10)
        self.prefetch.pack(anchor="w")

    # -- acciones -----------------------------------------------------------

    def _avanzar(self, operacion: str) -> None:
        try:
            estado = getattr(self.servicio, operacion)()
        except Exception as exc:
            self._informar(f"{type(exc).__name__}: {exc}", "error")
            return
        self.refrescar(estado)
        self.publicar(Evento.CPU_AVANZO, fase=estado["fase"], ciclos=estado["ciclos"],
                      instrucciones=estado["instrucciones"],
                      detenido=estado["detenido"])

    def reiniciar(self) -> None:
        self.servicio.reiniciar()
        self.refrescar()
        self._informar("RESET de la Unidad de Control.", "aviso")
        self.publicar(Evento.CPU_REINICIADA)

    # -- pintado ------------------------------------------------------------

    def refrescar(self, estado=None) -> None:
        estado = estado if estado is not None else self.servicio.estado()

        fase_activa = estado["fase"]
        for fase, caja in self._cajas_fase.items():
            activa = fase == fase_activa
            caja.configure(
                bg=mezclar(PALETA["abismo"], PALETA["violeta"], 0.55) if activa
                else PALETA["abismo"],
                fg=PALETA["texto"] if activa else PALETA["texto_debil"],
                highlightbackground=PALETA["violeta"] if activa else PALETA["borde"])
        self.detalle_fase.configure(text=DESCRIPCION_FASE.get(fase_activa, ""))

        self._contadores["ciclos"].configure(text=f"{estado['ciclos']:,}".replace(",", " "))
        self._contadores["instrucciones"].configure(
            text=f"{estado['instrucciones']:,}".replace(",", " "))

        for nombre, celda in self._celdas_micro.items():
            valor = estado["micro"].get(nombre, 0)
            celda.configure(text=hex64(valor),
                            fg=PALETA["texto_debil"] if valor == 0 else PALETA["cian"])

        octetos = estado.get("prefetch") or b""
        self.prefetch.configure(
            text=" ".join(f"{b:02X}" for b in octetos) if octetos else "vacio",
            fg=PALETA["cian"] if octetos else PALETA["texto_debil"])

        if estado["detenido"]:
            self.insignia.fijar("HLT", PALETA["alerta"])
        elif estado["instrucciones"] or estado["ciclos"]:
            self.insignia.fijar("EJECUTANDO", PALETA["ok"])
        else:
            self.insignia.fijar("EN RESET", PALETA["texto_tenue"])

        if estado.get("error"):
            self._informar(estado["error"], "error")
        elif estado.get("mnemonico"):
            self._informar(f"Instruccion en curso: {estado['mnemonico']}", "info")

    def _informar(self, texto: str, severidad: str = "info") -> None:
        colores = {"info": PALETA["texto_tenue"], "exito": PALETA["ok"],
                   "aviso": PALETA["alerta"], "error": PALETA["fallo"]}
        self.mensaje.configure(text=texto, fg=colores.get(severidad, PALETA["texto_tenue"]))
        self.trazar(texto, severidad)

    # -- mientras el modulo no exista --------------------------------------

    def _construir_sin_modulo(self) -> None:
        """
        En vez del aviso generico, este panel imprime el contrato que espera.
        Es lo que el Integrante 3 necesita leer para saber contra que programar.
        """
        motivo = getattr(self.servicio, "motivo", "") or "modulo no encontrado"

        tk.Label(self.cuerpo, text="MODULO PENDIENTE", bg=PALETA["elevado"],
                 fg=PALETA["alerta"], font=sans(11, True)).pack(anchor="w")
        tk.Label(self.cuerpo, text=motivo, bg=PALETA["elevado"],
                 fg=PALETA["texto_debil"], font=mono(9), anchor="w",
                 wraplength=780, justify="left").pack(fill="x", pady=(6, 0))
        tk.Label(self.cuerpo,
                 text="El panel se enciende solo en cuanto la rama del Integrante 3 "
                      "se fusione. Este es el contrato que debe cumplir:",
                 bg=PALETA["elevado"], fg=PALETA["texto_tenue"], font=sans(9),
                 anchor="w", wraplength=780, justify="left").pack(fill="x",
                                                                  pady=(10, 8))

        contrato = TextoMono(self.cuerpo, alto=17, ancho=74, tam=9)
        contrato.pack(fill="both", expand=True)
        contrato.configurar_etiqueta("clave", foreground=PALETA["violeta"])
        contrato.configurar_etiqueta("nota", foreground=PALETA["texto_debil"])
        contrato.fijar(
            "# enigma64/cpu.py\n"
            "class CPU:\n"
            "    def __init__(self, ram, banco): ...\n\n"
            "    def paso(self) -> dict:\n"
            "        '''Avanza UNA fase de la FSM.'''\n\n"
            "    def paso_instruccion(self) -> dict:\n"
            "        '''Completa la instruccion actual.'''\n\n"
            "    def ejecutar(self, max_ciclos: int = 100000) -> dict:\n"
            "        '''Corre hasta HLT o hasta agotar los ciclos.'''\n\n"
            "    def reiniciar(self) -> None: ...\n\n"
            "    def estado(self) -> dict:\n"
            "        return {\n"
            "            'fase': 'FETCH',        # FETCH DECODE EXECUTE MEMORY WRITE-BACK\n"
            "            'ciclos': 0, 'instrucciones': 0, 'detenido': False,\n"
            "            'micro': {'MAR': 0, 'MDR': 0, 'IR': 0,\n"
            "                      'A': 0, 'B': 0, 'Z': 0},\n"
            "            'mnemonico': '', 'prefetch': b'',   # ambos opcionales\n"
            "        }\n"
        )
        tk.Label(self.cuerpo,
                 text="Tambien valen los nombres en ingles (step, run, reset, state) "
                      "y las clases UnidadControl, ControlUnit o Procesador: el "
                      "adaptador engancha por pato. Contrato completo en "
                      "enigma64/ui/servicios/puertos.py → PuertoCPU.",
                 bg=PALETA["elevado"], fg=PALETA["texto_debil"], font=sans(8),
                 anchor="w", wraplength=780, justify="left").pack(fill="x",
                                                                  pady=(8, 0))


if __name__ == "__main__":
    PanelCPU.ejecutar_suelto()
