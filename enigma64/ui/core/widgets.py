"""
Componentes visuales reutilizables del sistema de diseno Noctua.

tkinter trae controles muy planos, asi que aqui se construyen sobre Canvas las
piezas que le dan identidad propia a Enigma-64: la tarjeta con franja de
acento, los diodos del bus de control, las insignias de estado, la tira de bits
y la marca de la lechuza.

Ningun panel dibuja nada a mano: todos componen estas piezas.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Sequence

from .tema import MARGEN, MARGEN_CHICO, PALETA, mono, sans


# ---------------------------------------------------------------------------
# Utilidades de color y dibujo
# ---------------------------------------------------------------------------


def mezclar(color_a: str, color_b: str, proporcion: float) -> str:
    """
    Mezcla dos colores hexadecimales. `proporcion` 0.0 devuelve `color_a` y
    1.0 devuelve `color_b`. Se usa para apagar los diodos sin inventar colores
    nuevos fuera de la paleta.
    """
    proporcion = max(0.0, min(1.0, proporcion))
    a = tuple(int(color_a[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(color_b[i:i + 2], 16) for i in (1, 3, 5))
    m = tuple(round(x + (y - x) * proporcion) for x, y in zip(a, b))
    return "#{:02X}{:02X}{:02X}".format(*m)


def rect_redondeado(lienzo: tk.Canvas, x0: float, y0: float, x1: float, y1: float,
                    radio: float = 6, **opciones) -> int:
    """Rectangulo de esquinas redondeadas; tkinter no trae uno."""
    radio = min(radio, abs(x1 - x0) / 2, abs(y1 - y0) / 2)
    puntos = [
        x0 + radio, y0, x1 - radio, y0, x1, y0, x1, y0 + radio,
        x1, y1 - radio, x1, y1, x1 - radio, y1, x0 + radio, y1,
        x0, y1, x0, y1 - radio, x0, y0 + radio, x0, y0,
    ]
    return lienzo.create_polygon(puntos, smooth=True, **opciones)


# ---------------------------------------------------------------------------
# Tarjeta
# ---------------------------------------------------------------------------


class Tarjeta(tk.Frame):
    """
    Contenedor con borde, franja de acento y titulo.

    Los widgets hijos se agregan a ``tarjeta.cuerpo``, nunca a la tarjeta.
    """

    def __init__(self, maestro, titulo: str = "", subtitulo: str = "",
                 acento: Optional[str] = None, **kwargs) -> None:
        super().__init__(maestro, bg=PALETA["borde"], **kwargs)
        self.acento = acento or PALETA["ambar"]

        interior = tk.Frame(self, bg=PALETA["elevado"])
        interior.pack(fill="both", expand=True, padx=1, pady=1)

        if titulo:
            cabecera = tk.Frame(interior, bg=PALETA["elevado"])
            cabecera.pack(fill="x", padx=MARGEN, pady=(MARGEN_CHICO + 2, 0))

            franja = tk.Canvas(cabecera, width=3, height=16,
                               bg=PALETA["elevado"], highlightthickness=0)
            franja.create_rectangle(0, 0, 3, 16, fill=self.acento, outline="")
            franja.pack(side="left", padx=(0, 8))

            columna = tk.Frame(cabecera, bg=PALETA["elevado"])
            columna.pack(side="left", fill="x", expand=True)
            ttk.Label(columna, text=titulo, style="Titulo.TLabel").pack(anchor="w")
            if subtitulo:
                ttk.Label(columna, text=subtitulo, style="Tenue.TLabel").pack(anchor="w")

            self.zona_cabecera = tk.Frame(cabecera, bg=PALETA["elevado"])
            self.zona_cabecera.pack(side="right")

            tk.Frame(interior, bg=PALETA["borde_sutil"], height=1).pack(
                fill="x", padx=MARGEN, pady=(MARGEN_CHICO, 0))
        else:
            self.zona_cabecera = tk.Frame(interior, bg=PALETA["elevado"])

        self.cuerpo = tk.Frame(interior, bg=PALETA["elevado"])
        self.cuerpo.pack(fill="both", expand=True, padx=MARGEN, pady=MARGEN)


# ---------------------------------------------------------------------------
# Diodos del bus de control
# ---------------------------------------------------------------------------


class Led(tk.Frame):
    """
    Diodo con etiqueta. Encendido brilla en su color; apagado queda como una
    brasa apenas visible sobre la superficie de la tarjeta.
    """

    def __init__(self, maestro, texto: str, color: Optional[str] = None,
                 diametro: int = 11, fondo: Optional[str] = None) -> None:
        self.fondo = fondo or PALETA["elevado"]
        super().__init__(maestro, bg=self.fondo)
        self.color = color or PALETA["ok"]
        self.diametro = diametro

        lado = diametro + 6
        self.lienzo = tk.Canvas(self, width=lado, height=lado, bg=self.fondo,
                                highlightthickness=0)
        self.lienzo.pack(side="left")
        m = 3
        self._halo = self.lienzo.create_oval(m - 2, m - 2, m + diametro + 2, m + diametro + 2,
                                             fill=self.fondo, outline="")
        self._nucleo = self.lienzo.create_oval(m, m, m + diametro, m + diametro,
                                               fill=self.fondo, outline="")

        self.etiqueta = tk.Label(self, text=texto, bg=self.fondo,
                                 fg=PALETA["texto_debil"], font=mono(9, True))
        self.etiqueta.pack(side="left", padx=(5, 0))

        self.apagar()

    def encender(self, color: Optional[str] = None) -> None:
        self.color = color or self.color
        self.lienzo.itemconfigure(self._halo, fill=mezclar(self.fondo, self.color, 0.28))
        self.lienzo.itemconfigure(self._nucleo, fill=self.color,
                                  outline=mezclar(self.color, "#FFFFFF", 0.35))
        self.etiqueta.configure(fg=self.color)

    def apagar(self) -> None:
        self.lienzo.itemconfigure(self._halo, fill=self.fondo)
        self.lienzo.itemconfigure(self._nucleo,
                                  fill=mezclar(self.fondo, self.color, 0.16),
                                  outline=PALETA["borde"])
        self.etiqueta.configure(fg=PALETA["texto_debil"])

    def fijar(self, encendido: bool, color: Optional[str] = None) -> None:
        self.encender(color) if encendido else self.apagar()


class TableroLeds(tk.Frame):
    """Fila de diodos donde a lo sumo uno esta encendido (senal del bus)."""

    def __init__(self, maestro, senales: Sequence[str], colores: dict,
                 fondo: Optional[str] = None) -> None:
        fondo = fondo or PALETA["elevado"]
        super().__init__(maestro, bg=fondo)
        self.leds = {}
        for senal in senales:
            led = Led(self, senal, color=colores.get(senal, PALETA["ok"]), fondo=fondo)
            led.pack(side="left", padx=(0, 14))
            self.leds[senal] = led

    def marcar(self, senal_activa: Optional[str]) -> None:
        for senal, led in self.leds.items():
            led.fijar(senal == senal_activa)


# ---------------------------------------------------------------------------
# Insignia de estado
# ---------------------------------------------------------------------------


class Insignia(tk.Canvas):
    """Pastilla de color con texto: estados cortos como READY o CONECTADO."""

    def __init__(self, maestro, texto: str = "", color: Optional[str] = None,
                 ancho: int = 118, alto: int = 22, fondo: Optional[str] = None) -> None:
        fondo = fondo or PALETA["elevado"]
        super().__init__(maestro, width=ancho, height=alto, bg=fondo,
                         highlightthickness=0)
        self.fondo = fondo
        self._ancho, self._alto = ancho, alto
        self._forma = rect_redondeado(self, 1, 1, ancho - 1, alto - 1, radio=alto / 2,
                                      fill=fondo, outline=PALETA["borde"])
        self._texto = self.create_text(ancho / 2, alto / 2, text=texto,
                                       fill=PALETA["texto_tenue"], font=mono(9, True))
        if texto:
            self.fijar(texto, color or PALETA["texto_tenue"])

    def fijar(self, texto: str, color: str) -> None:
        self.itemconfigure(self._texto, text=texto, fill=color)
        self.itemconfigure(self._forma, fill=mezclar(self.fondo, color, 0.16),
                           outline=mezclar(self.fondo, color, 0.45))


# ---------------------------------------------------------------------------
# Campos de entrada
# ---------------------------------------------------------------------------


class CampoValor(tk.Frame):
    """Etiqueta encima, campo de texto monoespaciado debajo."""

    def __init__(self, maestro, etiqueta: str, valor: str = "", ancho: int = 18,
                 ayuda: str = "", fondo: Optional[str] = None) -> None:
        fondo = fondo or PALETA["elevado"]
        super().__init__(maestro, bg=fondo)
        tk.Label(self, text=etiqueta.upper(), bg=fondo, fg=PALETA["texto_debil"],
                 font=sans(8, True)).pack(anchor="w")
        self.variable = tk.StringVar(value=valor)
        self.entrada = ttk.Entry(self, textvariable=self.variable, width=ancho,
                                 font=mono(10))
        self.entrada.pack(anchor="w", fill="x")
        if ayuda:
            tk.Label(self, text=ayuda, bg=fondo, fg=PALETA["texto_debil"],
                     font=sans(8)).pack(anchor="w")

    @property
    def texto(self) -> str:
        return self.variable.get()

    @texto.setter
    def texto(self, valor: str) -> None:
        self.variable.set(valor)


# ---------------------------------------------------------------------------
# Texto monoespaciado con barra de desplazamiento
# ---------------------------------------------------------------------------


class TextoMono(tk.Frame):
    """Area de texto oscura y monoespaciada, con barra de desplazamiento."""

    def __init__(self, maestro, alto: int = 12, ancho: int = 60,
                 editable: bool = False, tam: int = 10) -> None:
        super().__init__(maestro, bg=PALETA["borde"])
        interior = tk.Frame(self, bg=PALETA["abismo"])
        interior.pack(fill="both", expand=True, padx=1, pady=1)

        self.texto = tk.Text(
            interior, height=alto, width=ancho, font=mono(tam),
            bg=PALETA["abismo"], fg=PALETA["texto"], insertbackground=PALETA["ambar"],
            selectbackground=PALETA["seleccion"], selectforeground=PALETA["texto"],
            relief="flat", borderwidth=0, highlightthickness=0,
            padx=8, pady=6, wrap="none",
        )
        self.texto.pack(side="left", fill="both", expand=True)

        barra = ttk.Scrollbar(interior, orient="vertical", command=self.texto.yview)
        barra.pack(side="right", fill="y")
        self.texto.configure(yscrollcommand=barra.set)

        self.editable = editable
        if not editable:
            self.texto.configure(state="disabled")

    def _con_escritura(self, accion: Callable[[], None]) -> None:
        if not self.editable:
            self.texto.configure(state="normal")
        accion()
        if not self.editable:
            self.texto.configure(state="disabled")

    def fijar(self, contenido: str) -> None:
        def accion() -> None:
            self.texto.delete("1.0", "end")
            self.texto.insert("1.0", contenido)
        self._con_escritura(accion)

    def anexar(self, contenido: str, etiqueta: Optional[str] = None,
               autodesplazar: bool = True) -> None:
        def accion() -> None:
            self.texto.insert("end", contenido, etiqueta or ())
            if autodesplazar:
                self.texto.see("end")
        self._con_escritura(accion)

    def limpiar(self) -> None:
        self._con_escritura(lambda: self.texto.delete("1.0", "end"))

    def obtener(self) -> str:
        return self.texto.get("1.0", "end-1c")

    def configurar_etiqueta(self, nombre: str, **opciones) -> None:
        self.texto.tag_configure(nombre, **opciones)


# ---------------------------------------------------------------------------
# Tira de bits
# ---------------------------------------------------------------------------


class TiraBits(tk.Canvas):
    """
    Los ocho bits de un byte como celdas pulsables, con el bit 7 a la
    izquierda igual que en la documentacion. Pulsar una celda invoca el
    callback con el indice del bit.
    """

    CELDA = 26
    ALTO = 34

    def __init__(self, maestro, al_pulsar: Optional[Callable[[int], None]] = None,
                 fondo: Optional[str] = None) -> None:
        fondo = fondo or PALETA["elevado"]
        super().__init__(maestro, width=self.CELDA * 8 + 2, height=self.ALTO,
                         bg=fondo, highlightthickness=0)
        self.fondo = fondo
        self.al_pulsar = al_pulsar
        self._celdas = {}
        self._textos = {}
        self._indices = {}

        for posicion in range(8):
            indice = 7 - posicion  # el bit 7 va primero por ser el mas significativo
            x0 = posicion * self.CELDA + 1
            forma = rect_redondeado(self, x0 + 1, 1, x0 + self.CELDA - 2, 23, radio=4,
                                    fill=PALETA["abismo"], outline=PALETA["borde"])
            texto = self.create_text(x0 + self.CELDA / 2 - 0.5, 12, text="0",
                                     fill=PALETA["texto_debil"], font=mono(10, True))
            self.create_text(x0 + self.CELDA / 2 - 0.5, 30, text=str(indice),
                             fill=PALETA["texto_debil"], font=mono(7))
            self._celdas[indice] = forma
            self._textos[indice] = texto
            self._indices[forma] = indice
            self._indices[texto] = indice

        self.bind("<Button-1>", self._al_hacer_clic)

    def _al_hacer_clic(self, evento) -> None:
        if self.al_pulsar is None:
            return
        for item in self.find_overlapping(evento.x, evento.y, evento.x, evento.y):
            if item in self._indices:
                self.al_pulsar(self._indices[item])
                return

    def fijar_byte(self, valor: int) -> None:
        for indice in range(8):
            encendido = bool((valor >> indice) & 1)
            self.itemconfigure(self._textos[indice],
                               text="1" if encendido else "0",
                               fill=PALETA["abismo"] if encendido else PALETA["texto_debil"])
            self.itemconfigure(self._celdas[indice],
                               fill=PALETA["cian"] if encendido else PALETA["abismo"],
                               outline=PALETA["cian"] if encendido else PALETA["borde"])


# ---------------------------------------------------------------------------
# Marca
# ---------------------------------------------------------------------------


class MarcaNoctua(tk.Canvas):
    """
    Isotipo de Noctua Systems: un hexagono de circuito con los dos ojos de la
    lechuza. Se dibuja con vectores para no depender de archivos de imagen,
    de modo que cualquier modulo suelto puede mostrarlo sin recursos externos.
    """

    def __init__(self, maestro, lado: int = 46, fondo: Optional[str] = None) -> None:
        fondo = fondo or PALETA["abismo"]
        super().__init__(maestro, width=lado, height=lado, bg=fondo,
                         highlightthickness=0)
        c = lado / 2
        r = lado * 0.46

        # Hexagono exterior
        puntos = []
        for i in range(6):
            angulo = -math.pi / 2 + i * math.pi / 3
            puntos += [c + r * math.cos(angulo), c + r * math.sin(angulo)]
        self.create_polygon(puntos, fill="", outline=PALETA["ambar"], width=2)

        # Hexagono interior, mas tenue: la "placa"
        puntos_int = []
        for i in range(6):
            angulo = -math.pi / 2 + i * math.pi / 3
            puntos_int += [c + r * 0.72 * math.cos(angulo), c + r * 0.72 * math.sin(angulo)]
        self.create_polygon(puntos_int, fill="", outline=PALETA["ambar_oscuro"], width=1)

        # Ojos de la lechuza
        ojo = lado * 0.115
        sep = lado * 0.155
        alto_ojo = c - lado * 0.045
        for dx in (-sep, sep):
            self.create_oval(c + dx - ojo, alto_ojo - ojo, c + dx + ojo, alto_ojo + ojo,
                             fill=PALETA["ambar"], outline="")
            pupila = ojo * 0.42
            self.create_oval(c + dx - pupila, alto_ojo - pupila,
                             c + dx + pupila, alto_ojo + pupila,
                             fill=PALETA["abismo"], outline="")

        # Pico
        self.create_polygon(
            c, alto_ojo + lado * 0.085,
            c - lado * 0.052, alto_ojo + lado * 0.185,
            c + lado * 0.052, alto_ojo + lado * 0.185,
            fill=PALETA["cian"], outline="",
        )


# ---------------------------------------------------------------------------
# Contenedor con desplazamiento
# ---------------------------------------------------------------------------


class MarcoDesplazable(tk.Frame):
    """
    Marco que se desplaza verticalmente cuando su contenido no cabe.

    Enigma-64 tiene que poder demostrarse en el portatil de cualquier
    integrante, y no todos tienen la misma resolucion. En vez de recortar
    paneles, se envuelven aqui: si caben se ven enteros, y si no, la rueda del
    raton llega al resto.

    Los hijos se agregan a ``marco.interior``.
    """

    def __init__(self, maestro, fondo: Optional[str] = None, **kwargs) -> None:
        fondo = fondo or PALETA["abismo"]
        super().__init__(maestro, bg=fondo, **kwargs)

        self.lienzo = tk.Canvas(self, bg=fondo, highlightthickness=0, bd=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        self.lienzo.configure(yscrollcommand=self._al_desplazar)

        self.lienzo.pack(side="left", fill="both", expand=True)
        # La barra solo aparece cuando hace falta (la gestiona _al_desplazar).
        self._barra_visible = False

        self.interior = tk.Frame(self.lienzo, bg=fondo)
        self._ventana = self.lienzo.create_window((0, 0), window=self.interior,
                                                  anchor="nw")

        self.interior.bind("<Configure>", self._al_cambiar_interior)
        self.lienzo.bind("<Configure>", self._al_cambiar_lienzo)
        self.bind("<Enter>", lambda _e: self._enlazar_rueda(True))
        self.bind("<Leave>", lambda _e: self._enlazar_rueda(False))

    # -- ajuste de tamano ---------------------------------------------------

    def _al_cambiar_interior(self, _evento=None) -> None:
        self.lienzo.configure(scrollregion=self.lienzo.bbox("all"))

    def _al_cambiar_lienzo(self, evento) -> None:
        # El contenido siempre ocupa todo el ancho disponible; solo se
        # desplaza en vertical.
        self.lienzo.itemconfigure(self._ventana, width=evento.width)

    def _al_desplazar(self, inicio: str, fin: str) -> None:
        """Muestra la barra solo si el contenido desborda."""
        necesita = not (float(inicio) <= 0.0 and float(fin) >= 1.0)
        if necesita and not self._barra_visible:
            self.barra.pack(side="right", fill="y")
            self._barra_visible = True
        elif not necesita and self._barra_visible:
            self.barra.pack_forget()
            self._barra_visible = False
        self.barra.set(inicio, fin)

    # -- rueda del raton ----------------------------------------------------

    def _enlazar_rueda(self, activar: bool) -> None:
        if activar:
            self.lienzo.bind_all("<Button-4>", self._rueda)
            self.lienzo.bind_all("<Button-5>", self._rueda)
            self.lienzo.bind_all("<MouseWheel>", self._rueda)
        else:
            self.lienzo.unbind_all("<Button-4>")
            self.lienzo.unbind_all("<Button-5>")
            self.lienzo.unbind_all("<MouseWheel>")

    def _rueda(self, evento) -> None:
        if not self._barra_visible:
            return
        if evento.num == 4:
            paso = -1
        elif evento.num == 5:
            paso = 1
        else:                                   # Windows y macOS
            paso = -1 if evento.delta > 0 else 1
        self.lienzo.yview_scroll(paso, "units")
