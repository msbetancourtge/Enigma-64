"""
Visores de estructuras de datos: un vector como celdas indexadas V[0 .. N-1]
y una matriz como cuadricula F x C.

Son widgets genericos del sistema de diseno: no saben nada de la RAM ni de
la CPU. Reciben una "foto" (palabras crudas de 64 bits por filas) y la dibujan
marcando tres cosas, que son las que hacen falta para seguir un algoritmo:

    escrita ahora     fondo ambar      la instruccion que acaba de correr la escribio
    leida ahora       borde cian       la instruccion que acaba de correr la leyo
    cambiada          texto ambar      ya no vale lo que valia al cargar el programa

Al pulsar una celda se llama a `al_pulsar(fila, columna)`.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .tema import PALETA, mono, sans
from .widgets import mezclar

Celda = Tuple[int, int]
Formateador = Callable[[int], str]

#: Ancho de celda segun el formato: el hexadecimal de 64 bits no cabe en 64 px.
ANCHO_CELDA = {"decimal": 74, "hex": 140, "float": 84}
ALTO_CELDA = 34
ALTO_INDICE = 16
MARGEN_IZQ_MATRIZ = 34

#: Colores de la leyenda, compartidos con el panel.
COLOR_ESCRITA = PALETA["ambar"]
COLOR_LEIDA = PALETA["cian"]
COLOR_CAMBIADA = PALETA["ambar"]


def _recortar(texto: str, ancho_px: int) -> str:
    """Corta el texto para que quepa en la celda (aprox. 7 px por caracter)."""
    maximo = max(3, ancho_px // 7)
    return texto if len(texto) <= maximo else texto[:maximo - 1] + "…"


class _VisorBase(tk.Canvas):
    """Parte comun: estado, colores y deteccion de pulsaciones."""

    def __init__(self, maestro, al_pulsar: Optional[Callable[[int, int], None]] = None,
                 fondo: Optional[str] = None) -> None:
        super().__init__(maestro, bg=fondo or PALETA["elevado"], highlightthickness=0,
                         height=ALTO_CELDA + ALTO_INDICE + 6)
        self.al_pulsar = al_pulsar
        self.palabras: List[List[int]] = []
        self.formato = "decimal"
        self.formatear: Formateador = str
        self.escritas: Set[Celda] = set()
        self.leidas: Set[Celda] = set()
        self.cambiadas: Set[Celda] = set()
        self.seleccion: Optional[Celda] = None
        self._cajas: Dict[Celda, Tuple[int, int, int, int]] = {}
        self.bind("<Button-1>", self._al_click)
        self.bind("<Configure>", lambda _e: self.dibujar())

    def fijar(self, palabras: Sequence[Sequence[int]], formatear: Formateador,
              formato: str = "decimal", escritas: Iterable[Celda] = (),
              leidas: Iterable[Celda] = (), cambiadas: Iterable[Celda] = ()) -> None:
        self.palabras = [list(f) for f in palabras]
        self.formatear = formatear
        self.formato = formato
        self.escritas = set(escritas)
        self.leidas = set(leidas)
        self.cambiadas = set(cambiadas)
        self.dibujar()

    def seleccionar(self, celda: Optional[Celda]) -> None:
        self.seleccion = celda
        self.dibujar()

    @property
    def ancho_celda(self) -> int:
        return ANCHO_CELDA.get(self.formato, 74)

    def _celda(self, x0: int, y0: int, celda: Celda, palabra: int) -> None:
        ancho = self.ancho_celda
        x1, y1 = x0 + ancho - 4, y0 + ALTO_CELDA
        relleno = PALETA["abismo"]
        borde = PALETA["borde"]
        grosor = 1
        texto_color = PALETA["cian"]
        if celda in self.cambiadas:
            texto_color = COLOR_CAMBIADA
        if celda in self.escritas:
            relleno = mezclar(PALETA["abismo"], COLOR_ESCRITA, 0.45)
            borde, grosor, texto_color = COLOR_ESCRITA, 2, PALETA["texto"]
        if celda in self.leidas:
            borde, grosor = COLOR_LEIDA, 2
        if celda == self.seleccion:
            relleno = PALETA["seleccion"]
            borde, grosor = PALETA["texto"], 2
        self.create_rectangle(x0, y0, x1, y1, fill=relleno, outline=borde, width=grosor)
        self.create_text((x0 + x1) // 2, (y0 + y1) // 2, fill=texto_color, font=mono(9, True),
                         text=_recortar(self.formatear(palabra), ancho - 8))
        self._cajas[celda] = (x0, y0, x1, y1)

    def _al_click(self, evento) -> None:
        for celda, (x0, y0, x1, y1) in self._cajas.items():
            if x0 <= evento.x <= x1 and y0 <= evento.y <= y1:
                self.seleccion = celda
                self.dibujar()
                if self.al_pulsar is not None:
                    self.al_pulsar(*celda)
                return

    def _vacio(self, texto: str) -> None:
        self.configure(height=ALTO_CELDA)
        self.create_text(8, ALTO_CELDA // 2, anchor="w", text=texto,
                         fill=PALETA["texto_debil"], font=sans(9))

    def dibujar(self) -> None:  # pragma: no cover - cada subclase
        raise NotImplementedError


class VisorVector(_VisorBase):
    """
    Celdas indexadas V[0 .. N-1]. Si no caben en una linea se parten en
    varias, cada celda con su indice encima.
    """

    def dibujar(self) -> None:
        self.delete("all")
        self._cajas.clear()
        fila = self.palabras[0] if self.palabras else []
        if not fila:
            self._vacio("vector vacio (N = 0)")
            return
        ancho = self.ancho_celda
        disponible = max(self.winfo_width(), ancho * 4)
        por_linea = max(1, (disponible - 8) // ancho)
        alto_linea = ALTO_INDICE + ALTO_CELDA + 6
        lineas = (len(fila) + por_linea - 1) // por_linea
        self.configure(height=lineas * alto_linea + 2)
        for i, palabra in enumerate(fila):
            x0 = 4 + (i % por_linea) * ancho
            y0 = (i // por_linea) * alto_linea
            self.create_text(x0 + (ancho - 4) // 2, y0 + ALTO_INDICE // 2 + 1, text=f"[{i}]",
                             fill=PALETA["texto_debil"], font=mono(8))
            self._celda(x0, y0 + ALTO_INDICE, (0, i), palabra)


class VisorMatriz(_VisorBase):
    """Cuadricula F x C con los indices de fila a la izquierda y de columna arriba."""

    def dibujar(self) -> None:
        self.delete("all")
        self._cajas.clear()
        if not self.palabras or not self.palabras[0]:
            self._vacio("matriz vacia (F x C = 0)")
            return
        ancho = self.ancho_celda
        filas, columnas = len(self.palabras), len(self.palabras[0])
        self.configure(height=ALTO_INDICE + filas * (ALTO_CELDA + 4) + 4,
                       width=MARGEN_IZQ_MATRIZ + columnas * ancho + 8)
        for j in range(columnas):
            x = MARGEN_IZQ_MATRIZ + j * ancho + (ancho - 4) // 2
            self.create_text(x, ALTO_INDICE // 2 + 1, text=f"[{j}]",
                             fill=PALETA["texto_debil"], font=mono(8))
        for i, fila in enumerate(self.palabras):
            y0 = ALTO_INDICE + i * (ALTO_CELDA + 4)
            self.create_text(MARGEN_IZQ_MATRIZ - 6, y0 + ALTO_CELDA // 2, anchor="e",
                             text=f"[{i}]", fill=PALETA["texto_debil"], font=mono(8))
            for j, palabra in enumerate(fila):
                self._celda(MARGEN_IZQ_MATRIZ + j * ancho, y0, (i, j), palabra)


def visor_para(tipo: str, maestro, **kwargs) -> _VisorBase:
    """Fabrica: el visor que corresponde a 'vector' o 'matriz'."""
    return (VisorMatriz if tipo == "matriz" else VisorVector)(maestro, **kwargs)
