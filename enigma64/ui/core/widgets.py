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
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .formato import ascii_imprimible, bin8, hex32, hex64
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
# Visor de campos IEEE 754
# ---------------------------------------------------------------------------


class VisorIEEE754(tk.Canvas):
    """
    Los 64 bits de un flotante de doble precision, separados en sus campos:
    el bit 63 de signo, los 11 de exponente y los 52 de mantisa. Entre el
    exponente y la mantisa se dibuja, con trazo discontinuo, el bit implicito:
    forma parte del numero pero no se almacena.

    Las 64 celdas almacenadas son pulsables; el bit implicito no, porque no
    existe en la palabra. El ancho de las celdas se ajusta al del panel.
    """

    ALTO = 76
    #: (nombre, bit mas alto, bit mas bajo, clave de color en la paleta)
    CAMPOS = (
        ("SIGNO", 63, 63, "violeta"),
        ("EXPONENTE", 62, 52, "ambar"),
        ("MANTISA", 51, 0, "cian"),
    )
    _SEPARACION = 8
    _CELDA_MIN = 9.0
    _CELDA_MAX = 16.0

    def __init__(self, maestro, al_pulsar: Optional[Callable[[int], None]] = None,
                 fondo: Optional[str] = None, ancho: int = 760) -> None:
        fondo = fondo or PALETA["elevado"]
        super().__init__(maestro, width=ancho, height=self.ALTO, bg=fondo,
                         highlightthickness=0)
        self.fondo = fondo
        self.al_pulsar = al_pulsar
        self.patron = 0
        self.implicito = 0
        self.editable = True
        self._indices: Dict[int, int] = {}
        self._ancho_dibujado = 0

        self.bind("<Configure>", self._al_redimensionar)
        self.bind("<Button-1>", self._al_hacer_clic)
        self._dibujar(ancho)

    # -- estado -------------------------------------------------------------

    def fijar(self, patron: int, implicito: Optional[int] = None,
              editable: bool = True) -> None:
        """Muestra un patron. Sin `implicito` se deduce del exponente."""
        self.patron = patron & 0xFFFFFFFFFFFFFFFF
        if implicito is None:
            implicito = 0 if (self.patron >> 52) & 0x7FF == 0 else 1
        self.implicito = implicito & 1
        self.editable = editable
        self._dibujar(self._ancho_dibujado)

    def pulsar(self, indice: int) -> None:
        """Lo mismo que hacer clic sobre la celda del bit `indice`."""
        if self.editable and self.al_pulsar is not None and 0 <= indice <= 63:
            self.al_pulsar(indice)

    # -- dibujo -------------------------------------------------------------

    def _al_redimensionar(self, evento) -> None:
        if abs(evento.width - self._ancho_dibujado) > 1:
            self._dibujar(evento.width)

    def _dibujar(self, ancho: int) -> None:
        self.delete("all")
        self._indices.clear()
        self._ancho_dibujado = ancho

        # 64 celdas almacenadas + 1 implicita, con tres separaciones entre grupos.
        celda = (ancho - 2 - 3 * self._SEPARACION) / 65.0
        celda = max(self._CELDA_MIN, min(self._CELDA_MAX, celda))
        tam_bit = 9 if celda >= 13 else (8 if celda >= 11 else 7)
        y0, y1 = 20, 46

        x = 1.0
        for nombre, alto, bajo, clave_color in self.CAMPOS:
            color = PALETA[clave_color]
            if nombre == "MANTISA":
                x = self._dibujar_implicito(x, celda, y0, y1, tam_bit)
            inicio = x
            for indice in range(alto, bajo - 1, -1):
                encendido = bool((self.patron >> indice) & 1)
                forma = self.create_rectangle(
                    x + 0.5, y0, x + celda - 0.5, y1,
                    fill=color if encendido else PALETA["abismo"],
                    outline=color if encendido else mezclar(PALETA["borde"], color, 0.35))
                texto = self.create_text(
                    x + celda / 2, (y0 + y1) / 2, text="1" if encendido else "0",
                    fill=PALETA["abismo"] if encendido else mezclar(self.fondo, color, 0.6),
                    font=mono(tam_bit, True))
                self._indices[forma] = indice
                self._indices[texto] = indice
                x += celda
            fin = x

            bits = alto - bajo + 1
            # El signo ocupa una sola celda: su nombre entero pisaria al del
            # exponente, asi que se abrevia a la S de la notacion habitual.
            rotulo = "S" if bits == 1 else f"{nombre}  ·  {bits} bits"
            self.create_text(inicio, 8, text=rotulo, anchor="w", fill=color,
                             font=sans(8, True))
            self.create_text(inicio + celda / 2, y1 + 10, text=str(alto),
                             fill=PALETA["texto_debil"], font=mono(7))
            if bits > 1:
                self.create_text(fin - celda / 2, y1 + 10, text=str(bajo),
                                 fill=PALETA["texto_debil"], font=mono(7))
            x += self._SEPARACION

        if not self.editable:
            self.create_text(1, self.ALTO - 6, anchor="w", fill=PALETA["texto_debil"],
                             font=sans(7), text="solo lectura")

    def _dibujar_implicito(self, x: float, celda: float, y0: float, y1: float,
                           tam_bit: int) -> float:
        """Celda fantasma del bit que la norma da por sabido."""
        color = PALETA["texto_tenue"]
        self.create_rectangle(x + 0.5, y0, x + celda - 0.5, y1, fill=self.fondo,
                              outline=color, dash=(2, 2))
        self.create_text(x + celda / 2, (y0 + y1) / 2, text=str(self.implicito),
                         fill=PALETA["texto"] if self.implicito else color,
                         font=mono(tam_bit, True))
        # Va una linea mas abajo que los indices para no pisar el 52 y el 51.
        self.create_line(x + celda / 2, y1 + 2, x + celda / 2, y1 + 14, fill=color,
                         dash=(2, 2))
        self.create_text(x + celda / 2, y1 + 21, text="bit implicito", fill=color,
                         font=sans(7))
        return x + celda + self._SEPARACION

    def _al_hacer_clic(self, evento) -> None:
        for item in self.find_overlapping(evento.x, evento.y, evento.x, evento.y):
            if item in self._indices:
                self.pulsar(self._indices[item])
                return


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


# ---------------------------------------------------------------------------
# Grilla visual interactiva de memoria (8 Bancos de 64 bits - Tarea 9)
# ---------------------------------------------------------------------------


class GrillaBytesInteractiva(tk.Frame):
    """
    Cuadrícula visual interactiva para inspeccionar y seleccionar bytes en la RAM.

    Organizada según la microarquitectura de la Tarea 9:
      * Cada fila es una palabra de 64 bits (8 bytes).
      * Cada columna corresponde a uno de los 8 bancos físicos de memoria (Bancos 0 a 7,
        seleccionados por A[2:0]).
      * Cada celda de byte es interactiva: clic la selecciona, resalta su ubicación
        física e invoca `al_seleccionar(direccion, valor_byte, banco)`.
    """

    ANCHO_DIR = 100
    ANCHO_BANCO = 38
    ANCHO_ASCII = 100
    ALTO_FILA = 22
    ALTO_CABECERA = 26

    def __init__(self, maestro, filas_visibles: int = 16,
                 al_seleccionar: Optional[Callable[[int, int, int], None]] = None,
                 fondo: Optional[str] = None) -> None:
        self.fondo = fondo or PALETA["abismo"]
        super().__init__(maestro, bg=self.fondo)
        self.filas_visibles = filas_visibles
        self.al_seleccionar = al_seleccionar

        self.base_direccion: int = 0x00200000
        self.direccion_seleccionada: Optional[int] = None
        self._datos_filas: List[List[int]] = [[0] * 8 for _ in range(self.filas_visibles)]
        self._celdas_items: Dict[Tuple[int, int], Tuple[int, int]] = {}  # (fila, col) -> (rect_id, text_id)
        self._items_a_coords: Dict[int, Tuple[int, int]] = {}             # item_id -> (fila, col)

        ancho_total = self.ANCHO_DIR + (self.ANCHO_BANCO * 8) + self.ANCHO_ASCII + 16
        alto_total = self.ALTO_CABECERA + (self.ALTO_FILA * self.filas_visibles) + 8

        self.lienzo = tk.Canvas(self, width=ancho_total, height=alto_total,
                                bg=self.fondo, highlightthickness=0, cursor="hand2")
        self.lienzo.pack(fill="both", expand=True)

        self.lienzo.bind("<Button-1>", self._al_hacer_clic)
        self._dibujar_estructura_inicial()

    def _dibujar_estructura_inicial(self) -> None:
        self.lienzo.delete("all")
        self._celdas_items.clear()
        self._items_a_coords.clear()

        # Fondo de cabecera
        x_fin = self.ANCHO_DIR + (self.ANCHO_BANCO * 8) + self.ANCHO_ASCII + 8
        self.lienzo.create_rectangle(0, 0, x_fin, self.ALTO_CABECERA,
                                     fill=PALETA["elevado"], outline="")

        # Titulo columna direccion
        self.lienzo.create_text(8, self.ALTO_CABECERA / 2, text="PALABRA 64b",
                                fill=PALETA["texto_debil"], font=mono(8, True), anchor="w")

        # Titulos de los 8 bancos físicos
        for banco in range(8):
            x_centro = self.ANCHO_DIR + banco * self.ANCHO_BANCO + self.ANCHO_BANCO / 2
            self.lienzo.create_text(x_centro, self.ALTO_CABECERA / 2 - 4,
                                     text=f"B{banco}",
                                     fill=PALETA["ambar"], font=mono(8, True), anchor="center")
            self.lienzo.create_text(x_centro, self.ALTO_CABECERA / 2 + 6,
                                     text=f"+{banco}",
                                     fill=PALETA["texto_debil"], font=mono(7), anchor="center")

        # Titulo ASCII
        x_ascii = self.ANCHO_DIR + 8 * self.ANCHO_BANCO + 10
        self.lienzo.create_text(x_ascii, self.ALTO_CABECERA / 2, text="ASCII (64b)",
                                fill=PALETA["texto_debil"], font=mono(8, True), anchor="w")

        # Linea divisoria horizontal
        self.lienzo.create_line(0, self.ALTO_CABECERA, x_fin, self.ALTO_CABECERA,
                                fill=PALETA["borde"], width=1)

        # Crear celdas de las filas
        for fila in range(self.filas_visibles):
            y0 = self.ALTO_CABECERA + fila * self.ALTO_FILA + 2
            y1 = y0 + self.ALTO_FILA - 2
            y_centro = (y0 + y1) / 2

            # Etiqueta de direccion de la palabra
            self.lienzo.create_text(8, y_centro, text=f"{hex32(self.base_direccion + fila * 8)}",
                                    fill=PALETA["ambar"], font=mono(8), anchor="w",
                                    tags=(f"dir_{fila}",))

            # 8 Celdas de bytes
            for col in range(8):
                x0 = self.ANCHO_DIR + col * self.ANCHO_BANCO + 1
                x1 = x0 + self.ANCHO_BANCO - 2

                rect = rect_redondeado(self.lienzo, x0, y0, x1, y1, radio=3,
                                       fill=PALETA["abismo"], outline=PALETA["borde"])
                txt = self.lienzo.create_text((x0 + x1) / 2, y_centro, text="00",
                                              fill=PALETA["texto_debil"], font=mono(9, True))

                self._celdas_items[(fila, col)] = (rect, txt)
                self._items_a_coords[rect] = (fila, col)
                self._items_a_coords[txt] = (fila, col)

            # Texto ASCII de la palabra
            self.lienzo.create_text(x_ascii, y_centro, text="........",
                                    fill=PALETA["texto_debil"], font=mono(8), anchor="w",
                                    tags=(f"ascii_{fila}",))

    def fijar_datos(self, base_direccion: int, bytes_datos: List[List[int]]) -> None:
        """Actualiza todas las celdas con la matriz de bytes recibida (filas x 8 bytes)."""
        self.base_direccion = base_direccion
        self._datos_filas = bytes_datos

        for fila in range(min(len(bytes_datos), self.filas_visibles)):
            dir_palabra = base_direccion + fila * 8
            self.lienzo.itemconfigure(f"dir_{fila}", text=hex32(dir_palabra))

            bytes_fila = bytes_datos[fila]
            for col in range(8):
                byte_val = bytes_fila[col] if col < len(bytes_fila) else 0
                rect, txt = self._celdas_items[(fila, col)]

                direccion_celda = dir_palabra + col
                es_seleccionada = (self.direccion_seleccionada == direccion_celda)

                # Coloreado según contenido y seleccion
                if es_seleccionada:
                    fill_color = mezclar(PALETA["elevado"], PALETA["ambar"], 0.4)
                    outline_color = PALETA["ambar"]
                    text_color = PALETA["texto"]
                elif byte_val != 0:
                    fill_color = mezclar(PALETA["abismo"], PALETA["cian"], 0.18)
                    outline_color = PALETA["borde"]
                    text_color = PALETA["cian"]
                else:
                    fill_color = PALETA["abismo"]
                    outline_color = PALETA["borde"]
                    text_color = PALETA["texto_debil"]

                self.lienzo.itemconfigure(rect, fill=fill_color, outline=outline_color)
                self.lienzo.itemconfigure(txt, text=f"{byte_val:02X}", fill=text_color)

            cadena_ascii = "".join(ascii_imprimible(b) for b in bytes_fila)
            self.lienzo.itemconfigure(f"ascii_{fila}", text=cadena_ascii,
                                      fill=PALETA["texto_tenue"] if any(bytes_fila) else PALETA["texto_debil"])

    def seleccionar_direccion(self, direccion: int) -> None:
        """Marca visualmente la celda de la dirección indicada."""
        self.direccion_seleccionada = direccion
        self.fijar_datos(self.base_direccion, self._datos_filas)

    def _al_hacer_clic(self, evento) -> None:
        elementos = self.lienzo.find_overlapping(evento.x, evento.y, evento.x, evento.y)
        for item in elementos:
            if item in self._items_a_coords:
                fila, col = self._items_a_coords[item]
                direccion = self.base_direccion + fila * 8 + col
                self.direccion_seleccionada = direccion
                self.fijar_datos(self.base_direccion, self._datos_filas)

                byte_val = self._datos_filas[fila][col] if fila < len(self._datos_filas) else 0
                if self.al_seleccionar:
                    self.al_seleccionar(direccion, byte_val, col)
                return


# ---------------------------------------------------------------------------
# Inspector y Editor de Bits de un Byte en Vivo
# ---------------------------------------------------------------------------


class InspectorBitsByte(Tarjeta):
    """
    Inspector visual interactivo para visualizar y conmutar en vivo los 8 bits
    de un byte seleccionado de la memoria RAM.
    """

    def __init__(self, maestro, al_conmutar_bit: Optional[Callable[[int, int], None]] = None,
                 al_guardar_byte: Optional[Callable[[int, int], None]] = None,
                 **kwargs) -> None:
        super().__init__(maestro, titulo="INSPECTOR Y EDITOR DE BITS",
                         subtitulo="Modificación interactiva a nivel de bit y byte en vivo",
                         acento=PALETA["ambar"], **kwargs)
        self.al_conmutar_bit = al_conmutar_bit
        self.al_guardar_byte = al_guardar_byte

        self.direccion_actual: int = 0x00200000
        self.valor_byte_actual: int = 0
        self.banco_actual: int = 0

        self._construir_interfaz()

    def _construir_interfaz(self) -> None:
        # Fila 1: Datos de localizacion
        fila_loc = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        fila_loc.pack(fill="x", pady=(0, 6))

        self.lbl_direccion = tk.Label(fila_loc, text="Dirección: 0x00200000",
                                      bg=PALETA["elevado"], fg=PALETA["ambar"],
                                      font=mono(10, True))
        self.lbl_direccion.pack(side="left")

        self.lbl_banco = tk.Label(fila_loc, text="· Banco: B0 (bits [7:0])",
                                  bg=PALETA["elevado"], fg=PALETA["cian"],
                                  font=mono(9))
        self.lbl_banco.pack(side="left", padx=(10, 0))

        self.lbl_region = tk.Label(fila_loc, text="· Región: Programas y datos",
                                   bg=PALETA["elevado"], fg=PALETA["texto_tenue"],
                                   font=sans(9))
        self.lbl_region.pack(side="left", padx=(10, 0))

        # Fila 2: Tira interactiva de 8 bits
        fila_bits = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        fila_bits.pack(fill="x", pady=(4, 6))

        tk.Label(fila_bits, text="Bits (b7..b0 - clic para conmutar):",
                 bg=PALETA["elevado"], fg=PALETA["texto_debil"], font=sans(8)).pack(anchor="w")

        self.tira_bits = TiraBits(fila_bits, al_pulsar=self._on_click_bit, fondo=PALETA["elevado"])
        self.tira_bits.pack(anchor="w", pady=(2, 0))

        # Fila 3: Desglose y edicion rapida
        fila_edit = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        fila_edit.pack(fill="x", pady=(6, 0))

        # Hex
        col_hex = tk.Frame(fila_edit, bg=PALETA["elevado"])
        col_hex.pack(side="left", padx=(0, 10))
        tk.Label(col_hex, text="Hexadecimal", bg=PALETA["elevado"],
                 fg=PALETA["texto_debil"], font=sans(8)).pack(anchor="w")
        self.var_hex = tk.StringVar(value="0x00")
        self.ent_hex = ttk.Entry(col_hex, textvariable=self.var_hex, width=8, font=mono(10))
        self.ent_hex.pack(anchor="w")
        self.ent_hex.bind("<Return>", lambda _e: self._guardar_desde_campos())

        # Decimal
        col_dec = tk.Frame(fila_edit, bg=PALETA["elevado"])
        col_dec.pack(side="left", padx=(0, 10))
        tk.Label(col_dec, text="Decimal", bg=PALETA["elevado"],
                 fg=PALETA["texto_debil"], font=sans(8)).pack(anchor="w")
        self.var_dec = tk.StringVar(value="0")
        self.ent_dec = ttk.Entry(col_dec, textvariable=self.var_dec, width=6, font=mono(10))
        self.ent_dec.pack(anchor="w")
        self.ent_dec.bind("<Return>", lambda _e: self._guardar_desde_campos())

        # Binario
        col_bin = tk.Frame(fila_edit, bg=PALETA["elevado"])
        col_bin.pack(side="left", padx=(0, 10))
        tk.Label(col_bin, text="Binario", bg=PALETA["elevado"],
                 fg=PALETA["texto_debil"], font=sans(8)).pack(anchor="w")
        self.lbl_bin = tk.Label(col_bin, text="0b00000000", bg=PALETA["elevado"],
                                fg=PALETA["cian"], font=mono(10))
        self.lbl_bin.pack(anchor="w", pady=2)

        # Carácter ASCII
        col_ascii = tk.Frame(fila_edit, bg=PALETA["elevado"])
        col_ascii.pack(side="left", padx=(0, 12))
        tk.Label(col_ascii, text="ASCII", bg=PALETA["elevado"],
                 fg=PALETA["texto_debil"], font=sans(8)).pack(anchor="w")
        self.lbl_ascii = tk.Label(col_ascii, text="' ' (0x00)", bg=PALETA["elevado"],
                                  fg=PALETA["texto"], font=mono(10))
        self.lbl_ascii.pack(anchor="w", pady=2)

        # Botones de accion rapida
        ttk.Button(fila_edit, text="Aplicar", style="Primario.TButton",
                   command=self._guardar_desde_campos).pack(side="left", padx=(6, 4), pady=(12, 0))
        ttk.Button(fila_edit, text="NOT (~)",
                   command=self._invertir_byte).pack(side="left", padx=2, pady=(12, 0))
        ttk.Button(fila_edit, text="0x00",
                   command=lambda: self._fijar_valor_directo(0x00)).pack(side="left", padx=2, pady=(12, 0))
        ttk.Button(fila_edit, text="0xFF",
                   command=lambda: self._fijar_valor_directo(0xFF)).pack(side="left", padx=2, pady=(12, 0))

        # Mensaje de estado
        self.lbl_estado = tk.Label(self.cuerpo, text="Selecciona un byte para inspeccionar sus bits.",
                                   bg=PALETA["elevado"], fg=PALETA["texto_tenue"], font=mono(8), anchor="w")
        self.lbl_estado.pack(fill="x", pady=(6, 0))

    def actualizar_byte(self, direccion: int, valor: int, region: str = "") -> None:
        """Carga un nuevo byte en el inspector."""
        self.direccion_actual = direccion
        self.valor_byte_actual = valor & 0xFF
        self.banco_actual = direccion & 0x07

        self.lbl_direccion.configure(text=f"Dirección: {hex32(direccion)}")
        self.lbl_banco.configure(text=f"· Banco B{self.banco_actual} (bits [{self.banco_actual*8+7}:{self.banco_actual*8}])")
        if region:
            self.lbl_region.configure(text=f"· Región: {region}")

        self.tira_bits.fijar_byte(self.valor_byte_actual)
        self.var_hex.set(f"0x{self.valor_byte_actual:02X}")
        self.var_dec.set(str(self.valor_byte_actual))
        self.lbl_bin.configure(text=f"0b{bin8(self.valor_byte_actual)}")

        caracter = ascii_imprimible(self.valor_byte_actual)
        self.lbl_ascii.configure(text=f"'{caracter}'")
        self.lbl_estado.configure(text=f"Byte en {hex32(direccion)} = 0x{self.valor_byte_actual:02X} ({self.valor_byte_actual})",
                                  fg=PALETA["texto_tenue"])

    def _on_click_bit(self, bit_index: int) -> None:
        nuevo_valor = self.valor_byte_actual ^ (1 << bit_index)
        self.valor_byte_actual = nuevo_valor
        self.actualizar_byte(self.direccion_actual, nuevo_valor)
        bit_val = (nuevo_valor >> bit_index) & 1
        self.lbl_estado.configure(text=f"Bit {bit_index} conmutado a {bit_val} en {hex32(self.direccion_actual)}",
                                  fg=PALETA["ok"])

        if self.al_conmutar_bit:
            self.al_conmutar_bit(self.direccion_actual, bit_index)

    def _guardar_desde_campos(self) -> None:
        texto = self.var_hex.get().strip()
        try:
            if texto.startswith("0x") or texto.startswith("0X"):
                valor = int(texto, 16)
            elif texto.startswith("0b") or texto.startswith("0B"):
                valor = int(texto, 2)
            else:
                # Intentar como decimal
                valor = int(self.var_dec.get().strip(), 10)
        except Exception:
            try:
                valor = int(self.var_dec.get().strip(), 10)
            except Exception:
                self.lbl_estado.configure(text="Valor inválido.", fg=PALETA["fallo"])
                return

        valor = valor & 0xFF
        self.valor_byte_actual = valor
        self.actualizar_byte(self.direccion_actual, valor)
        self.lbl_estado.configure(text=f"Byte guardado: 0x{valor:02X} en {hex32(self.direccion_actual)}",
                                  fg=PALETA["ok"])

        if self.al_guardar_byte:
            self.al_guardar_byte(self.direccion_actual, valor)

    def _invertir_byte(self) -> None:
        self._fijar_valor_directo((~self.valor_byte_actual) & 0xFF)

    def _fijar_valor_directo(self, valor: int) -> None:
        self.valor_byte_actual = valor & 0xFF
        self.actualizar_byte(self.direccion_actual, self.valor_byte_actual)
        if self.al_guardar_byte:
            self.al_guardar_byte(self.direccion_actual, self.valor_byte_actual)


# ---------------------------------------------------------------------------
# Monitor de Pantalla MMIO (Salida 0xFF001000 - Tarea 9)
# ---------------------------------------------------------------------------


class MonitorPantallaCRT(Tarjeta):
    """
    Monitor / Terminal CRT emulado para el Controlador de Pantalla MMIO (0xFF001000).

    Muestra en tiempo real los caracteres emitidos en DATA y los comandos de CTRL,
    con controles interactivos para pruebas y demostración.
    """

    def __init__(self, maestro, al_emitir_data: Optional[Callable[[int], None]] = None,
                 al_emitir_ctrl: Optional[Callable[[int], None]] = None,
                 **kwargs) -> None:
        super().__init__(maestro, titulo="TERMINAL DE SALIDA CRT · MMIO",
                         subtitulo="Salida de pantalla (Base 0xFF001000)  ·  Controlador de pantalla emulado",
                         acento=PALETA["ok"], **kwargs)
        self.al_emitir_data = al_emitir_data
        self.al_emitir_ctrl = al_emitir_ctrl

        self._construir_pantalla()

    def _construir_pantalla(self) -> None:
        # Pantalla estilo fósforo verde CRT
        marco_crt = tk.Frame(self.cuerpo, bg=PALETA["borde"], padx=1, pady=1)
        marco_crt.pack(fill="both", expand=True, pady=(0, 6))

        self.pantalla_texto = tk.Text(marco_crt, width=70, height=12,
                                      bg="#070A0F", fg=PALETA["ok"],
                                      insertbackground=PALETA["ok"],
                                      font=mono(9), wrap="none",
                                      relief="flat", padx=8, pady=8)
        self.pantalla_texto.pack(fill="both", expand=True)
        self.pantalla_texto.configure(state="disabled")

        # Barra de estado de la pantalla
        barra_info = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        barra_info.pack(fill="x", pady=(0, 6))

        self.lbl_cursor = tk.Label(barra_info, text="Cursor: Ln 0, Col 0  ·  ADDR: 0x00000000",
                                   bg=PALETA["elevado"], fg=PALETA["cian"], font=mono(8))
        self.lbl_cursor.pack(side="left")

        self.lbl_count = tk.Label(barra_info, text="· Caracteres emitidos: 0",
                                  bg=PALETA["elevado"], fg=PALETA["texto_debil"], font=mono(8))
        self.lbl_count.pack(side="left", padx=(10, 0))

        self.lbl_status = tk.Label(barra_info, text="STATUS: 1 (READY)",
                                   bg=PALETA["elevado"], fg=PALETA["ok"], font=mono(8, True))
        self.lbl_status.pack(side="right")

        # Barra de controles interactivos
        controles = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        controles.pack(fill="x")

        tk.Label(controles, text="Emitir a DATA (ASCII):",
                 bg=PALETA["elevado"], fg=PALETA["texto_debil"], font=sans(8)).pack(side="left")

        self.var_texto = tk.StringVar(value="Hola Enigma-64!")
        self.ent_texto = ttk.Entry(controles, textvariable=self.var_texto, width=22, font=mono(9))
        self.ent_texto.pack(side="left", padx=(4, 6))
        self.ent_texto.bind("<Return>", lambda _e: self.enviar_cadena())

        ttk.Button(controles, text="Enviar", style="Primario.TButton",
                   command=self.enviar_cadena).pack(side="left", padx=2)
        ttk.Button(controles, text="Nueva línea (\\n)",
                   command=self.enviar_salto).pack(side="left", padx=2)
        ttk.Button(controles, text="Limpiar (CTRL=1)",
                   command=self.limpiar_pantalla).pack(side="left", padx=2)
        ttk.Button(controles, text="Demo Saludo",
                   command=self.demo_saludo).pack(side="left", padx=2)

    def fijar_contenido(self, lineas: List[str], cursor_fila: int = 0,
                        cursor_col: int = 0, count: int = 0, status: int = 1) -> None:
        """Actualiza el texto desplegado en la pantalla CRT emulada."""
        self.pantalla_texto.configure(state="normal")
        self.pantalla_texto.delete("1.0", "end")

        for f, linea in enumerate(lineas):
            if f == cursor_fila:
                # Mostrar el cursor interactivo en la línea actual
                col = min(cursor_col, len(linea))
                linea_con_cursor = linea[:col] + "█" + linea[col:]
                self.pantalla_texto.insert("end", linea_con_cursor + "\n")
            else:
                self.pantalla_texto.insert("end", linea + "\n")

        self.pantalla_texto.configure(state="disabled")

        addr = cursor_fila * 80 + cursor_col
        self.lbl_cursor.configure(text=f"Cursor: Ln {cursor_fila}, Col {cursor_col}  ·  ADDR: 0x{addr:08X}")
        self.lbl_count.configure(text=f"· Caracteres emitidos: {count}")
        self.lbl_status.configure(text=f"STATUS: {status} (READY)" if status == 1 else f"STATUS: {status}")

    def enviar_cadena(self) -> None:
        texto = self.var_texto.get()
        if not texto:
            return
        if self.al_emitir_data:
            for char in texto:
                self.al_emitir_data(ord(char))
        self.var_texto.set("")

    def enviar_salto(self) -> None:
        if self.al_emitir_data:
            self.al_emitir_data(10)  # \n

    def limpiar_pantalla(self) -> None:
        if self.al_emitir_ctrl:
            self.al_emitir_ctrl(1)  # CMD_CLEAR

    def demo_saludo(self) -> None:
        saludo = "Enigma-64 [Noctua Systems]\nControlador MMIO activo (0xFF001000)\n"
        if self.al_emitir_data:
            for char in saludo:
                self.al_emitir_data(ord(char))

