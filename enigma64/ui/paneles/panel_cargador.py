"""
Panel del cargador y del manipulador de bits (Integrante 4).

Permite depositar un programa en la region de usuario respetando el mapa de
memoria: el cargador rechaza cualquier intento de invadir los vectores, el
firmware o la pila, y la interfaz muestra ese rechazo con su motivo exacto.

Incluye tambien el manipulador bit a bit, con el byte representado como ocho
celdas pulsables.

Arranque suelto:  python -m enigma64.ui.paneles.panel_cargador

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from ..core.bus import Evento
from ..core.formato import (
    ValorInvalido, hex32, parsear_direccion, tamano_legible,
)
from ..core.tema import MARGEN, PALETA, mono, sans
from ..core.widgets import TextoMono, TiraBits
from ..servicios.mapa_memoria import nombre_region
from .base import PanelBase


class PanelCargador(PanelBase):
    """Carga de programas y manipulacion bit a bit de la memoria."""

    NOMBRE = "cargador"
    TITULO = "Cargador y manipulador de bits"
    SUBTITULO = "Integrante 4  ·  enigma64.cargador"
    ACENTO = PALETA["ambar"]
    CLAVE_SERVICIO = "cargador"
    TAMANO_SUELTO = (860, 780)

    def construir(self) -> None:
        self._construir_origen()
        self.separador()
        self._construir_destino()
        self._construir_resultado()
        self.separador()
        self._construir_bits()

    # -- construccion -------------------------------------------------------

    def _construir_origen(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")

        columna = tk.Frame(fila, bg=PALETA["elevado"])
        columna.pack(side="left", fill="x", expand=True)
        self.rotulo(columna, "Archivo del programa (.e64 / .bin / .txt)").pack(anchor="w")
        self.ruta = tk.StringVar()
        ttk.Entry(columna, textvariable=self.ruta, font=mono(10)).pack(fill="x")

        ttk.Button(fila, text="Examinar…", command=self.examinar).pack(
            side="left", padx=(10, 0), pady=(14, 0))
        ttk.Button(fila, text="Cargar archivo", style="Primario.TButton",
                   command=self.cargar_archivo).pack(side="left", padx=(6, 0),
                                                     pady=(14, 0))

        self.rotulo(self.cuerpo,
                    "O pegar un volcado en texto (hexadecimal, binario o decimal)").pack(
                        anchor="w", pady=(MARGEN, 4))
        self.volcado = TextoMono(self.cuerpo, alto=5, ancho=70, editable=True, tam=10)
        self.volcado.pack(fill="x")

    def _construir_destino(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")

        columna_destino = tk.Frame(fila, bg=PALETA["elevado"])
        columna_destino.pack(side="left")
        self.rotulo(columna_destino, "Direccion destino").pack(anchor="w")
        self.destino = tk.StringVar(value=hex32(self.servicio.DIRECCION_USUARIO))
        ttk.Entry(columna_destino, textvariable=self.destino, width=18,
                  font=mono(10)).pack(anchor="w")

        columna_entrada = tk.Frame(fila, bg=PALETA["elevado"])
        columna_entrada.pack(side="left", padx=(12, 0))
        self.rotulo(columna_entrada, "Punto de entrada (opcional)").pack(anchor="w")
        self.punto_entrada = tk.StringVar()
        ttk.Entry(columna_entrada, textvariable=self.punto_entrada, width=18,
                  font=mono(10)).pack(anchor="w")

        self.configurar_cpu = tk.BooleanVar(value=True)
        ttk.Checkbutton(fila, text="Inicializar contexto de CPU",
                        variable=self.configurar_cpu).pack(side="left",
                                                           padx=(14, 0), pady=(14, 0))

        ttk.Button(fila, text="Cargar volcado", style="Primario.TButton",
                   command=self.cargar_texto).pack(side="right", pady=(14, 0))

    def _construir_resultado(self) -> None:
        marco = tk.Frame(self.cuerpo, bg=PALETA["borde"])
        marco.pack(fill="x", pady=(MARGEN, 0))
        self.caja_resultado = tk.Frame(marco, bg=PALETA["abismo"])
        self.caja_resultado.pack(fill="x", padx=1, pady=1)

        self.titulo_resultado = tk.Label(
            self.caja_resultado, text="SIN CARGA TODAVIA", bg=PALETA["abismo"],
            fg=PALETA["texto_debil"], font=sans(9, True), anchor="w")
        self.titulo_resultado.pack(fill="x", padx=12, pady=(10, 4))

        self.detalle_resultado = tk.Label(
            self.caja_resultado,
            text="Elige un archivo o pega un volcado y pulsa Cargar.",
            bg=PALETA["abismo"], fg=PALETA["texto_tenue"], font=mono(9),
            anchor="w", justify="left", wraplength=760)
        self.detalle_resultado.pack(fill="x", padx=12, pady=(0, 10))

    def _construir_bits(self) -> None:
        self.rotulo(self.cuerpo,
                    "Manipulador de bits  ·  pulsa un bit para conmutarlo").pack(
                        anchor="w")

        fila = self.fila()
        fila.pack(fill="x", pady=(8, 0))

        columna = tk.Frame(fila, bg=PALETA["elevado"])
        columna.pack(side="left")
        self.rotulo(columna, "Direccion del byte").pack(anchor="w")
        self.direccion_bit = tk.StringVar(value=hex32(self.servicio.DIRECCION_USUARIO))
        entrada = ttk.Entry(columna, textvariable=self.direccion_bit, width=18,
                            font=mono(10))
        entrada.pack(anchor="w")
        entrada.bind("<Return>", lambda _e: self.refrescar_bits())

        ttk.Button(fila, text="Leer byte", command=self.refrescar_bits).pack(
            side="left", padx=(10, 0), pady=(14, 0))

        self.tira = TiraBits(fila, al_pulsar=self.conmutar_bit)
        self.tira.pack(side="left", padx=(20, 0), pady=(8, 0))

        self.valor_byte = tk.Label(fila, text="—", bg=PALETA["elevado"],
                                   fg=PALETA["cian"], font=mono(11, True))
        self.valor_byte.pack(side="left", padx=(16, 0), pady=(14, 0))

    # -- acciones -----------------------------------------------------------

    def examinar(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona un ejecutable de Enigma-64",
            filetypes=[("Ejecutables Enigma-64", "*.e64"),
                       ("Binario plano", "*.bin"),
                       ("Volcado en texto", "*.txt"),
                       ("Todos los archivos", "*.*")])
        if ruta:
            self.ruta.set(ruta)

    def _destino_y_entrada(self):
        """Lee los dos campos de direccion; devuelve None si alguno es invalido."""
        try:
            destino = parsear_direccion(self.destino.get())
        except ValorInvalido as exc:
            self._fallo("DIRECCION INVALIDA", str(exc))
            return None

        texto_entrada = self.punto_entrada.get().strip()
        if not texto_entrada:
            return destino, None
        try:
            return destino, parsear_direccion(texto_entrada)
        except ValorInvalido as exc:
            self._fallo("PUNTO DE ENTRADA INVALIDO", str(exc))
            return None

    def cargar_archivo(self) -> None:
        ruta = self.ruta.get().strip()
        if not ruta:
            self._fallo("FALTA EL ARCHIVO", "Escribe una ruta o pulsa Examinar.")
            return
        campos = self._destino_y_entrada()
        if campos is None:
            return
        self._intentar(lambda: self.servicio.cargar_archivo(
            ruta, campos[0], self.configurar_cpu.get()))

    def cargar_texto(self) -> None:
        texto = self.volcado.obtener().strip()
        if not texto:
            self._fallo("VOLCADO VACIO", "Pega los bytes del programa en el area de texto.")
            return
        campos = self._destino_y_entrada()
        if campos is None:
            return
        destino, entrada = campos
        self._intentar(lambda: self.servicio.cargar_texto(
            texto, destino, entrada, self.configurar_cpu.get()))

    def _intentar(self, operacion) -> None:
        """
        Ejecuta una carga y traduce cualquier excepcion del cargador a un
        mensaje legible. Las violaciones del mapa de memoria son resultados
        esperados, no fallos de la interfaz.
        """
        try:
            informe = operacion()
        except FileNotFoundError as exc:
            self._fallo("ARCHIVO NO ENCONTRADO", str(exc))
        except Exception as exc:
            self._fallo(f"CARGA RECHAZADA · {type(exc).__name__}", str(exc))
            self.publicar(Evento.CARGA_RECHAZADA, motivo=str(exc),
                          tipo=type(exc).__name__)
        else:
            self._exito(informe)

    def conmutar_bit(self, indice: int) -> None:
        try:
            direccion = parsear_direccion(self.direccion_bit.get())
        except ValorInvalido as exc:
            self._fallo("DIRECCION INVALIDA", str(exc))
            return
        try:
            nuevo = self.servicio.conmutar_bit(direccion, indice)
        except Exception as exc:
            self._fallo(f"BIT NO CONMUTADO · {type(exc).__name__}", str(exc))
            return

        self.refrescar_bits()
        self.trazar(f"bit {indice} de {hex32(direccion)} = {nuevo}", "dato")
        self.publicar(Evento.BIT_MODIFICADO, direccion=direccion, bit=indice,
                      valor=nuevo)

    def refrescar_bits(self) -> None:
        try:
            direccion = parsear_direccion(self.direccion_bit.get())
        except ValorInvalido as exc:
            self._fallo("DIRECCION INVALIDA", str(exc))
            return
        try:
            bits = self.servicio.byte_en_bits(direccion)
        except Exception as exc:
            self._fallo(f"LECTURA FALLIDA · {type(exc).__name__}", str(exc))
            return

        valor = int(bits, 2)
        self.tira.fijar_byte(valor)
        caracter = chr(valor) if 0x20 <= valor <= 0x7E else "·"
        self.valor_byte.configure(text=f"0x{valor:02X}  ·  '{caracter}'  ·  {bits}")

    # -- pintado ------------------------------------------------------------

    def _exito(self, informe: dict) -> None:
        self.caja_resultado.master.configure(bg=PALETA["ok"])
        self.titulo_resultado.configure(text="CARGA ACEPTADA", fg=PALETA["ok"])

        base, fin = informe["direccion_base"], informe["direccion_final"]
        lineas = [
            f"{tamano_legible(informe['tamano_total'])}"
            f"  ·  {hex32(base)} → {hex32(fin)}"
            f"  ·  region: {nombre_region(base)}",
            f"codigo {informe['tamano_codigo']} B  ·  datos {informe['tamano_datos']} B"
            f"  ·  {'reubicable' if informe['reubicable'] else 'absoluto'}",
            f"entry point {informe['entry_point_hex']}",
        ]
        if self.configurar_cpu.get():
            lineas.append("PC ← entry point   SP ← 0x00000000EFFFFFFF   R5 ← entry point")
        self.detalle_resultado.configure(text="\n".join(lineas), fg=PALETA["texto_tenue"])

        self.direccion_bit.set(hex32(base))
        self.refrescar_bits()

        self.trazar(f"{informe['tamano_total']} bytes en {hex32(base)}", "exito")
        self.publicar(Evento.PROGRAMA_CARGADO, **informe)
        # Quien muestre memoria querra mirar ahi; se lo pido por el bus.
        self.publicar(Evento.IR_A_DIRECCION, direccion=base)

    def _fallo(self, titulo: str, detalle: str) -> None:
        self.caja_resultado.master.configure(bg=PALETA["fallo"])
        self.titulo_resultado.configure(text=titulo, fg=PALETA["fallo"])
        self.detalle_resultado.configure(text=detalle, fg=PALETA["texto_tenue"])
        self.trazar(f"{titulo}: {detalle}", "error")

    # -- demostracion suelta ------------------------------------------------

    def preparar_demo(self) -> None:
        """Deja un programa de ejemplo listo para cargar con un solo clic."""
        if not self.servicio.disponible:
            return
        self.volcado.fijar(
            "; Suma dos registros y termina (Tarea 9)\n"
            "10 12 30   ; ADD R1, R2, R3\n"
            "16 10      ; INC R1\n"
            "00         ; HLT\n"
        )
        self.refrescar_bits()


if __name__ == "__main__":
    PanelCargador.ejecutar_suelto()
