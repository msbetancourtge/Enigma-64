"""
Panel de los tres algoritmos de verificacion (Tarea 9).

Factorial, Euclides y Fibonacci, con su pseudocodigo, su listado en
ensamblador y el codigo maquina traducido a mano en el documento. Desde aqui
se siembran los datos de entrada, se carga el programa en su direccion base y
se comprueba el resultado leyendo la RAM.

Ejecutarlos de verdad necesita la Unidad de Control (Integrante 3). Mientras
no este, cargar y verificar siguen sirviendo: el volcado de memoria permite
revisar byte a byte que la traduccion manual del documento es correcta.

Arranque suelto:  python -m enigma64.ui.paneles.panel_algoritmos

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.bus import Evento
from ..core.formato import hex32, hex64
from ..core.tema import MARGEN, PALETA, mono, sans
from ..core.widgets import TextoMono
from .base import PanelBase


class PanelAlgoritmos(PanelBase):
    """Carga y verificacion de los algoritmos de la Tarea 9."""

    NOMBRE = "algoritmos"
    TITULO = "Algoritmos de verificacion"
    SUBTITULO = "Tarea 9  ·  factorial, Euclides y Fibonacci"
    ACENTO = PALETA["ok"]
    CLAVE_SERVICIO = "algoritmos"
    TAMANO_SUELTO = (920, 760)

    def construir(self) -> None:
        self._botones = {}
        self.algoritmo = self.servicio.catalogo()[0]

        self._construir_selector()
        self._construir_resumen()
        self._construir_listado()
        self._construir_acciones()
        self._construir_resultado()

        self.elegir(self.algoritmo["clave"])

    # -- construccion -------------------------------------------------------

    def _construir_selector(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")
        for algoritmo in self.servicio.catalogo():
            boton = tk.Label(fila, text=algoritmo["nombre"], bg=PALETA["abismo"],
                             fg=PALETA["texto_tenue"], font=mono(9, True),
                             padx=13, pady=5, cursor="hand2", highlightthickness=1,
                             highlightbackground=PALETA["borde"])
            boton.pack(side="left", padx=(0, 5))
            boton.bind("<Button-1>",
                       lambda _e, c=algoritmo["clave"]: self.elegir(c))
            self._botones[algoritmo["clave"]] = boton

    def _construir_resumen(self) -> None:
        self.resumen = tk.Label(self.cuerpo, text="", bg=PALETA["elevado"],
                                fg=PALETA["texto_tenue"], font=sans(9), anchor="w",
                                wraplength=840, justify="left")
        self.resumen.pack(fill="x", pady=(MARGEN, 0))

        datos = self.fila()
        datos.pack(fill="x", pady=(8, 0))
        self._datos = {}
        for clave, etiqueta in (("base", "Direccion de carga"),
                                ("datos", "Variables en RAM"),
                                ("tamano", "Tamano del programa"),
                                ("esperado", "Resultado esperado")):
            columna = tk.Frame(datos, bg=PALETA["elevado"])
            columna.pack(side="left", padx=(0, 24))
            self.rotulo(columna, etiqueta).pack(anchor="w")
            valor = self.texto_dato(columna, "—", tam=10, negrita=True)
            valor.pack(anchor="w")
            self._datos[clave] = valor

    def _construir_listado(self) -> None:
        self.rotulo(self.cuerpo,
                    "Pseudocodigo y traduccion manual a lenguaje de maquina").pack(
                        anchor="w", pady=(MARGEN, 6))
        self.listado = TextoMono(self.cuerpo, alto=18, ancho=88, tam=9)
        self.listado.pack(fill="both", expand=True)
        self.listado.configurar_etiqueta("pseudo", foreground=PALETA["texto_tenue"])
        self.listado.configurar_etiqueta("cabecera", foreground=PALETA["texto_debil"])
        self.listado.configurar_etiqueta("direccion", foreground=PALETA["ambar"])
        self.listado.configurar_etiqueta("mnemonico", foreground=PALETA["texto"])
        self.listado.configurar_etiqueta("maquina", foreground=PALETA["cian"])
        self.listado.configurar_etiqueta("comentario", foreground=PALETA["texto_debil"])

    def _construir_acciones(self) -> None:
        fila = self.fila()
        fila.pack(fill="x", pady=(MARGEN, 0))
        ttk.Button(fila, text="Cargar en RAM", style="Primario.TButton",
                   command=self.cargar).pack(side="left")
        ttk.Button(fila, text="Verificar resultado",
                   command=self.verificar).pack(side="left", padx=6)
        self.boton_ejecutar = ttk.Button(fila, text="Ejecutar", command=self.ejecutar)
        self.boton_ejecutar.pack(side="left")
        if not self.servicio.puede_ejecutar:
            self.boton_ejecutar.state(["disabled"])
            tk.Label(fila, text="Ejecutar necesita la Unidad de Control (Integrante 3)",
                     bg=PALETA["elevado"], fg=PALETA["texto_debil"],
                     font=sans(8)).pack(side="left", padx=(10, 0))

    def _construir_resultado(self) -> None:
        marco = tk.Frame(self.cuerpo, bg=PALETA["borde"])
        marco.pack(fill="x", pady=(MARGEN, 0))
        self.caja = tk.Frame(marco, bg=PALETA["abismo"])
        self.caja.pack(fill="x", padx=1, pady=1)

        self.titulo_resultado = tk.Label(self.caja, text="SIN EJECUTAR",
                                         bg=PALETA["abismo"], fg=PALETA["texto_debil"],
                                         font=sans(9, True), anchor="w")
        self.titulo_resultado.pack(fill="x", padx=12, pady=(10, 4))
        self.detalle_resultado = tk.Label(
            self.caja, text="Carga el programa y comprueba el resultado en RAM.",
            bg=PALETA["abismo"], fg=PALETA["texto_tenue"], font=mono(9),
            anchor="w", justify="left", wraplength=840)
        self.detalle_resultado.pack(fill="x", padx=12, pady=(0, 10))

    # -- seleccion ----------------------------------------------------------

    def elegir(self, clave: str) -> None:
        self.algoritmo = self.servicio.obtener(clave)
        for otra, boton in self._botones.items():
            activo = otra == clave
            boton.configure(
                bg=PALETA["ok"] if activo else PALETA["abismo"],
                fg=PALETA["abismo"] if activo else PALETA["texto_tenue"],
                highlightbackground=PALETA["ok"] if activo else PALETA["borde"])

        self.resumen.configure(text=self.algoritmo["resumen"])
        resultado = self.algoritmo["resultado"]
        self._datos["base"].configure(text=hex32(self.algoritmo["base"]))
        self._datos["datos"].configure(text=hex32(self.algoritmo["datos"]))
        self._datos["tamano"].configure(
            text=f"{len(self.servicio.codigo_maquina(self.algoritmo))} bytes")
        self._datos["esperado"].configure(text=resultado["etiqueta"])

        self._pintar_listado()
        self._neutral()

    def _pintar_listado(self) -> None:
        self.listado.limpiar()
        self.listado.anexar("; Pseudocodigo\n", "cabecera", autodesplazar=False)
        for linea in self.algoritmo["pseudocodigo"].splitlines():
            self.listado.anexar(f";   {linea}\n", "pseudo", autodesplazar=False)

        self.listado.anexar(
            "\nDIRECCION    ENSAMBLADOR                CODIGO MAQUINA (BIG-ENDIAN)\n",
            "cabecera", autodesplazar=False)

        for direccion, mnemonico, octetos, comentario in self.algoritmo["listado"]:
            self.listado.anexar(f"{hex32(direccion)}   ", "direccion", autodesplazar=False)
            self.listado.anexar(f"{mnemonico:<26}", "mnemonico", autodesplazar=False)
            maquina = " ".join(f"{b:02X}" for b in octetos)
            self.listado.anexar(f"{maquina:<17}", "maquina", autodesplazar=False)
            self.listado.anexar(f"; {comentario}\n", "comentario", autodesplazar=False)

    # -- acciones -----------------------------------------------------------

    def cargar(self) -> None:
        try:
            informe = self.servicio.cargar(self.algoritmo)
        except Exception as exc:
            self._fallo(f"CARGA RECHAZADA · {type(exc).__name__}", str(exc))
            return

        entradas = ", ".join(
            f"{etiqueta} = {valor}"
            for etiqueta, (_d, valor, _a) in zip(self.algoritmo["etiquetas_entrada"],
                                                 self.algoritmo["entradas"])
        ) or "sin datos de entrada"

        self._exito("PROGRAMA CARGADO", "\n".join([
            f"{informe['tamano_total']} bytes  ·  {hex32(informe['direccion_base'])} → "
            f"{hex32(informe['direccion_final'])}",
            f"entry point {informe['entry_point_hex']}  ·  {entradas}",
            "PC y R5 apuntan al entry point; SP en 0x00000000EFFFFFFF.",
        ]))
        self.publicar(Evento.ALGORITMO_CARGADO, clave=self.algoritmo["clave"], **informe)
        self.publicar(Evento.IR_A_DIRECCION, direccion=informe["direccion_base"])

    def verificar(self) -> None:
        try:
            veredicto = self.servicio.verificar(self.algoritmo)
        except Exception as exc:
            self._fallo(f"NO SE PUDO VERIFICAR · {type(exc).__name__}", str(exc))
            return

        if veredicto["es_secuencia"]:
            obtenido = ", ".join("—" if v is None else str(v) for v in veredicto["obtenido"])
            esperado = ", ".join(str(v) for v in veredicto["esperado"])
            detalle = (f"desde {hex32(veredicto['direccion'])} en palabras de 8 bytes\n"
                       f"esperado  [{esperado}]\nobtenido  [{obtenido}]")
        else:
            detalle = (f"Mem[{hex32(veredicto['direccion'])}]\n"
                       f"esperado  {veredicto['esperado']}  ({hex64(veredicto['esperado'])})\n"
                       f"obtenido  {veredicto['obtenido']}  "
                       f"({hex64(veredicto['obtenido'] or 0)})")

        if veredicto["ok"]:
            self._exito(f"VERIFICADO · {veredicto['etiqueta']}", detalle)
        else:
            self._pendiente("RESULTADO AUN NO ESCRITO", detalle + (
                "\nEl programa esta en RAM pero nadie lo ha ejecutado: falta la "
                "Unidad de Control (Integrante 3)."
                if not self.servicio.puede_ejecutar else ""))
        self.publicar(Evento.ALGORITMO_VERIFICADO, clave=self.algoritmo["clave"],
                      ok=veredicto["ok"])

    def ejecutar(self) -> None:
        try:
            estado = self.servicio.ejecutar()
        except Exception as exc:
            self._fallo(f"NO SE PUDO EJECUTAR · {type(exc).__name__}", str(exc))
            return
        self._exito("EJECUCION TERMINADA",
                    f"{estado['ciclos']} ciclos  ·  {estado['instrucciones']} instrucciones"
                    f"  ·  {'detenido en HLT' if estado['detenido'] else 'sin HLT'}")
        self.verificar()

    # -- pintado ------------------------------------------------------------

    def _neutral(self) -> None:
        self.caja.master.configure(bg=PALETA["borde"])
        self.titulo_resultado.configure(text="SIN EJECUTAR", fg=PALETA["texto_debil"])
        self.detalle_resultado.configure(
            text="Carga el programa y comprueba el resultado en RAM.",
            fg=PALETA["texto_tenue"])

    def _exito(self, titulo: str, detalle: str) -> None:
        self.caja.master.configure(bg=PALETA["ok"])
        self.titulo_resultado.configure(text=titulo, fg=PALETA["ok"])
        self.detalle_resultado.configure(text=detalle, fg=PALETA["texto_tenue"])
        self.trazar(titulo.lower(), "exito")

    def _pendiente(self, titulo: str, detalle: str) -> None:
        self.caja.master.configure(bg=PALETA["alerta"])
        self.titulo_resultado.configure(text=titulo, fg=PALETA["alerta"])
        self.detalle_resultado.configure(text=detalle, fg=PALETA["texto_tenue"])
        self.trazar(titulo.lower(), "aviso")

    def _fallo(self, titulo: str, detalle: str) -> None:
        self.caja.master.configure(bg=PALETA["fallo"])
        self.titulo_resultado.configure(text=titulo, fg=PALETA["fallo"])
        self.detalle_resultado.configure(text=detalle, fg=PALETA["texto_tenue"])
        self.trazar(f"{titulo}: {detalle}", "error")


if __name__ == "__main__":
    PanelAlgoritmos.ejecutar_suelto()
