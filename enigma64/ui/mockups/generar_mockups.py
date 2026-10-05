"""
Generador de los bocetos (mockups) de la interfaz de Enigma-64.

Los bocetos no se dibujan a mano en una herramienta externa: se generan desde
la MISMA paleta que usa la aplicacion (`enigma64.ui.core.tema`). Asi el boceto
y la implementacion no se pueden separar, y si la marca cambia de color basta
con volver a ejecutar:

    python -m enigma64.ui.mockups.generar_mockups

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import pathlib
from typing import List, Optional, Sequence

from ..core.tema import COMPUTADOR, EMPRESA, LEMA, PALETA

P = PALETA
MONO = "JetBrains Mono, DejaVu Sans Mono, Consolas, monospace"
SANS = "Inter, Segoe UI, DejaVu Sans, sans-serif"

AQUI = pathlib.Path(__file__).parent


# ---------------------------------------------------------------------------
# Constructor de SVG
# ---------------------------------------------------------------------------


class Lienzo:
    """Acumulador de elementos SVG con las primitivas del sistema de diseno."""

    def __init__(self, ancho: int, alto: int, titulo: str) -> None:
        self.ancho, self.alto, self.titulo = ancho, alto, titulo
        self.partes: List[str] = []
        self.rect(0, 0, ancho, alto, P["abismo"])

    # -- primitivas ---------------------------------------------------------

    def rect(self, x, y, w, h, relleno, trazo=None, radio=0, ancho_trazo=1, opacidad=None):
        atributos = f'x="{x}" y="{y}" width="{w}" height="{h}" fill="{relleno}"'
        if radio:
            atributos += f' rx="{radio}"'
        if trazo:
            atributos += f' stroke="{trazo}" stroke-width="{ancho_trazo}"'
        if opacidad is not None:
            atributos += f' opacity="{opacidad}"'
        self.partes.append(f"  <rect {atributos}/>")

    def texto(self, x, y, contenido, color=None, tam=12, familia=SANS,
              negrita=False, ancla="start", opacidad=None):
        atributos = (f'x="{x}" y="{y}" fill="{color or P["texto"]}" '
                     f'font-family="{familia}" font-size="{tam}"')
        if negrita:
            atributos += ' font-weight="600"'
        if ancla != "start":
            atributos += f' text-anchor="{ancla}"'
        if opacidad is not None:
            atributos += f' opacity="{opacidad}"'
        self.partes.append(f"  <text {atributos}>{_escapar(contenido)}</text>")

    def linea(self, x1, y1, x2, y2, color=None, ancho=1, opacidad=None):
        atributos = (f'x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                     f'stroke="{color or P["borde_sutil"]}" stroke-width="{ancho}"')
        if opacidad is not None:
            atributos += f' opacity="{opacidad}"'
        self.partes.append(f"  <line {atributos}/>")

    def circulo(self, cx, cy, r, relleno, trazo=None, ancho_trazo=1, opacidad=None):
        atributos = f'cx="{cx}" cy="{cy}" r="{r}" fill="{relleno}"'
        if trazo:
            atributos += f' stroke="{trazo}" stroke-width="{ancho_trazo}"'
        if opacidad is not None:
            atributos += f' opacity="{opacidad}"'
        self.partes.append(f"  <circle {atributos}/>")

    def poligono(self, puntos: Sequence[float], relleno="none", trazo=None, ancho_trazo=1):
        coords = " ".join(f"{puntos[i]},{puntos[i + 1]}" for i in range(0, len(puntos), 2))
        atributos = f'points="{coords}" fill="{relleno}"'
        if trazo:
            atributos += f' stroke="{trazo}" stroke-width="{ancho_trazo}"'
        self.partes.append(f"  <polygon {atributos}/>")

    # -- componentes del sistema de diseno ---------------------------------

    def tarjeta(self, x, y, w, h, titulo, subtitulo="", acento=None) -> float:
        """Dibuja una tarjeta y devuelve la Y donde empieza su cuerpo."""
        acento = acento or P["ambar"]
        self.rect(x, y, w, h, P["elevado"], P["borde"], radio=8)
        if not titulo:
            return y + 14
        self.rect(x + 14, y + 14, 3, 16, acento, radio=1.5)
        self.texto(x + 25, y + 27, titulo, P["texto"], 12.5, SANS, True)
        if subtitulo:
            self.texto(x + 25, y + 41, subtitulo, P["texto_tenue"], 9.5)
            self.linea(x + 14, y + 52, x + w - 14, y + 52)
            return y + 68
        self.linea(x + 14, y + 40, x + w - 14, y + 40)
        return y + 56

    def led(self, x, y, etiqueta, color, encendido=False):
        if encendido:
            self.circulo(x + 6, y, 8, color, opacidad=0.26)
            self.circulo(x + 6, y, 5, color)
            self.texto(x + 18, y + 4, etiqueta, color, 9.5, MONO, True)
        else:
            self.circulo(x + 6, y, 5, color, P["borde"], opacidad=0.18)
            self.texto(x + 18, y + 4, etiqueta, P["texto_debil"], 9.5, MONO, True)

    def insignia(self, x, y, w, texto, color, h=21):
        self.rect(x, y, w, h, color, radio=h / 2, opacidad=0.16)
        self.rect(x, y, w, h, "none", color, radio=h / 2, opacidad=0.45)
        self.texto(x + w / 2, y + h / 2 + 3.5, texto, color, 9.5, MONO, True, "middle")

    def campo(self, x, y, w, etiqueta, valor, h=28, color_valor=None):
        self.texto(x, y - 5, etiqueta.upper(), P["texto_debil"], 8, SANS, True)
        self.rect(x, y, w, h, P["abismo"], P["borde"], radio=4)
        self.texto(x + 9, y + h / 2 + 4, valor, color_valor or P["cian"], 11, MONO)

    def boton(self, x, y, w, texto, primario=False, h=30):
        relleno = P["ambar_oscuro"] if primario else P["elevado_alto"]
        color = P["texto"] if primario else P["texto_tenue"]
        self.rect(x, y, w, h, relleno, P["borde"], radio=5)
        self.texto(x + w / 2, y + h / 2 + 4, texto, color, 10, SANS, True, "middle")

    def marca(self, x, y, lado=44):
        """El isotipo de la lechuza, el mismo que dibuja `widgets.MarcaNoctua`."""
        import math
        c = lado / 2
        r = lado * 0.46
        for escala, color, grosor in ((1.0, P["ambar"], 2), (0.72, P["ambar_oscuro"], 1)):
            puntos = []
            for i in range(6):
                a = -math.pi / 2 + i * math.pi / 3
                puntos += [x + c + r * escala * math.cos(a), y + c + r * escala * math.sin(a)]
            self.poligono(puntos, "none", color, grosor)
        ojo, sep, alto = lado * 0.115, lado * 0.155, y + c - lado * 0.045
        for dx in (-sep, sep):
            self.circulo(x + c + dx, alto, ojo, P["ambar"])
            self.circulo(x + c + dx, alto, ojo * 0.42, P["abismo"])
        self.poligono([x + c, alto + lado * 0.085,
                       x + c - lado * 0.052, alto + lado * 0.185,
                       x + c + lado * 0.052, alto + lado * 0.185], P["cian"])

    def barra_superior(self, alto=76, chips: Optional[Sequence] = None):
        self.rect(0, 0, self.ancho, alto, P["abismo"])
        self.linea(0, alto, self.ancho, alto, P["borde"])
        self.marca(20, (alto - 44) / 2)
        self.texto(76, 34, COMPUTADOR, P["texto"], 21, SANS, True)
        self.texto(77, 50, EMPRESA, P["ambar"], 9.5, SANS, True)
        self.texto(77, 63, LEMA, P["texto_debil"], 8.5)
        if chips:
            x = self.ancho - 20
            for etiqueta, color in reversed(list(chips)):
                w = 9 + len(etiqueta) * 6.4
                x -= w + 8
                self.insignia(x, (alto - 21) / 2, w, etiqueta, color)

    def volcado_hex(self, x, y, base, filas, ancho_total, resaltar=None):
        """Maqueta del volcado hexadecimal de 16 bytes por linea."""
        x_hex, x_ascii = x + 80, x + ancho_total - 98
        self.rect(x, y, ancho_total, filas * 17 + 24, P["abismo"], P["borde"], radio=5)
        self.texto(x + 11, y + 17, "DIRECCION", P["texto_debil"], 8, MONO, True)
        self.texto(x_hex, y + 17, "00 01 02 03  04 05 06 07  08 09 0A 0B  0C 0D 0E 0F",
                   P["texto_debil"], 8, MONO, True)
        self.texto(x_ascii, y + 17, "ASCII", P["texto_debil"], 8, MONO, True)
        self.linea(x + 10, y + 23, x + ancho_total - 10, y + 23)
        contenidos = [
            ("45 4E 49 47  00 00 00 01  00 00 00 00  00 20 00 00", "ENIG........ ..."),
            ("00 00 00 00  00 20 00 00  00 00 00 20  00 00 00 00", "..... ..... ...."),
            ("10 12 00 14  23 30 00 11  41 00 1A 4C  00 00 00 00", "....#0..A..L...."),
            ("00 00 00 00  00 00 00 00  00 00 00 00  00 00 00 00", "................"),
        ]
        for fila in range(filas):
            fy = y + 40 + fila * 17
            hexa, ascii_ = contenidos[fila % len(contenidos)]
            if resaltar is not None and fila == resaltar:
                self.rect(x + 6, fy - 11, ancho_total - 12, 16, P["seleccion"], radio=3)
            vivo = fila < 3
            self.texto(x + 11, fy, f"0x{base + fila * 16:08X}", P["ambar"], 9, MONO)
            self.texto(x_hex, fy, hexa,
                       P["cian"] if vivo else P["texto_debil"], 9, MONO)
            self.texto(x_ascii, fy, ascii_,
                       P["texto_tenue"] if vivo else P["texto_debil"], 9, MONO)

    # -- salida -------------------------------------------------------------

    def guardar(self, nombre: str) -> pathlib.Path:
        ruta = AQUI / nombre
        cuerpo = "\n".join(self.partes)
        ruta.write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.ancho}" '
            f'height="{self.alto}" viewBox="0 0 {self.ancho} {self.alto}">\n'
            f"  <title>{_escapar(self.titulo)}</title>\n{cuerpo}\n</svg>\n",
            encoding="utf-8",
        )
        return ruta


def _escapar(texto: str) -> str:
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# Boceto 1: ventana completa
# ---------------------------------------------------------------------------


def shell_completo() -> pathlib.Path:
    """
    Ventana completa, dimensionada para 1366x768 (el portatil mas pequeno del
    grupo). Cuaderno de modulos a la izquierda, columna de contexto a la
    derecha: solo se ve un modulo a la vez, tal y como pidio el profesor.
    """
    L = Lienzo(1366, 740, "Enigma-64 - Ventana completa")
    L.barra_superior(alto=62, chips=[("MEMORIA", P["ok"]), ("REGISTROS", P["ok"]),
                                     ("ALU", P["ok"]), ("CARGADOR", P["ok"])])

    arriba, margen = 74, 12
    alto_util = 740 - arriba - 34
    ancho_contexto = 450
    ancho_cuaderno = 1366 - ancho_contexto - margen * 3
    x_ctx = margen * 2 + ancho_cuaderno

    # -- cuaderno de modulos -----------------------------------------------
    pestanas = [("Memoria RAM", True), ("Registros", False), ("ALU", False),
                ("Cargador", False)]
    x = margen
    for etiqueta, activa in pestanas:
        w = 24 + len(etiqueta) * 7
        L.rect(x, arriba, w, 28, P["elevado"] if activa else P["noche"],
               P["borde"], radio=5)
        L.texto(x + w / 2, arriba + 18, etiqueta,
                P["ambar"] if activa else P["texto_tenue"], 10, SANS, True, "middle")
        x += w + 3

    cuerpo = arriba + 28
    alto_cuerpo = alto_util - 28
    y = L.tarjeta(margen, cuerpo, ancho_cuaderno, alto_cuerpo, "Memoria RAM y buses",
                  "Integrante 1  ·  enigma64.memoria", P["cian"])

    L.campo(margen + 16, y + 12, 190, "Direccion", "0x00200000")
    L.campo(margen + 218, y + 12, 100, "Tamano", "8")
    L.campo(margen + 330, y + 12, 200, "Valor a escribir", "0x454E494700000001")

    L.boton(margen + 16, y + 56, 86, "Leer")
    L.boton(margen + 110, y + 56, 86, "Escribir", True)
    L.boton(margen + 204, y + 56, 124, "Ir a la direccion")
    L.boton(margen + 336, y + 56, 110, "Reiniciar RAM")
    L.rect(margen + 458, y + 60, 15, 15, P["abismo"], P["ambar"], radio=3)
    L.texto(margen + 464, y + 72, "✓", P["ambar"], 10, MONO, True)
    L.texto(margen + 481, y + 72, "Verificar alineacion natural", P["texto_tenue"], 9)

    L.linea(margen + 16, y + 98, margen + ancho_cuaderno - 16, y + 98)
    L.texto(margen + 16, y + 118, "SENAL DEL BUS DE CONTROL", P["texto_debil"], 8,
            SANS, True)
    for i, (senal, color, on) in enumerate([
            ("READY", P["ok"], True), ("MISALIGNED", P["alerta"], False),
            ("MMIO", P["violeta"], False), ("ADDR_FAULT", P["fallo"], False)]):
        L.led(margen + 16 + i * 180, y + 140, senal, color, on)

    L.volcado_hex(margen + 16, y + 164, 0x00200000, 16, ancho_cuaderno - 32,
                  resaltar=0)

    yb = y + 164 + 16 * 17 + 24 + 18
    for i, (etiqueta, valor) in enumerate([
            ("Paginas asignadas", "3"), ("Memoria reservada", "12 KiB"),
            ("Tamano de pagina", "4 KiB"), ("Region actual", "Programas y datos")]):
        L.texto(margen + 16 + i * 210, yb, etiqueta.upper(), P["texto_debil"], 8,
                SANS, True)
        L.texto(margen + 16 + i * 210, yb + 18, valor, P["cian"], 11, MONO, True)

    # -- columna de contexto: mapa + traza ---------------------------------
    alto_mapa = int(alto_util * 0.63)
    my = L.tarjeta(x_ctx, arriba, ancho_contexto, alto_mapa, "Mapa de memoria",
                   "4 GiB fisicos  ·  Tarea 9", P["violeta"])
    regiones = [("Vectores", "0x00000000", P["fallo"], 16),
                ("Monitor + Cargador", "0x00001000", P["ambar"], 20),
                ("Trabajo del cargador", "0x00100000", P["ambar_oscuro"], 16),
                ("Tablas del sistema", "0x00120000", P["ambar_oscuro"], 16),
                ("Programas y datos", "0x00200000", P["ok"], 56),
                ("Pila", "0xC0000000", P["cian"], 30),
                ("Buffers de I/O y DMA", "0xF0000000", P["cian_oscuro"], 20),
                ("I/O mapeada", "0xFF000000", P["violeta"], 20)]
    yr = my + 4
    caja_usuario = None
    for nombre, inicio_dir, color, alto in regiones:
        if nombre == "Programas y datos":
            caja_usuario = (yr, alto)
        L.rect(x_ctx + 16, yr, 9, alto, color, radio=2)
        L.texto(x_ctx + 34, yr + alto / 2 + 3, nombre, P["texto"], 9)
        L.texto(x_ctx + ancho_contexto - 18, yr + alto / 2 + 3, inicio_dir, color,
                9, MONO, ancla="end")
        yr += alto + 4
    if caja_usuario:
        y_u, alto_u = caja_usuario
        L.rect(x_ctx + 12, y_u - 3, ancho_contexto - 24, alto_u + 6, "none",
               P["ok"], radio=4, opacidad=0.55)

    L.linea(x_ctx + 16, yr + 8, x_ctx + ancho_contexto - 16, yr + 8)
    L.texto(x_ctx + 16, yr + 28, "ULTIMO ACCESO OBSERVADO EN EL BUS",
            P["texto_debil"], 8, SANS, True)
    L.rect(x_ctx + 16, yr + 38, ancho_contexto - 32, 50, P["abismo"], P["borde"],
           radio=5)
    L.texto(x_ctx + 28, yr + 58, "0x00200000", P["ambar"], 11, MONO, True)
    L.texto(x_ctx + 28, yr + 76, "Programas y datos · R/W/X · READY",
            P["texto_tenue"], 9, MONO)

    y_traza = arriba + alto_mapa + margen
    ty = L.tarjeta(x_ctx, y_traza, ancho_contexto, arriba + alto_util - y_traza,
                   "Traza del bus de eventos", "Integrante 5  ·  core.bus",
                   P["texto_tenue"])
    L.rect(x_ctx + 16, ty + 8, ancho_contexto - 32,
           arriba + alto_util - ty - 20, P["abismo"], P["borde"], radio=5)
    traza = [("12:04:01", "cargador", "224 B → 0x00200000", P["ok"]),
             ("12:04:01", "registros", "PC ← 0x00200000", P["cian"]),
             ("12:04:07", "memoria", "READY 8B @0x00200000", P["texto_tenue"]),
             ("12:04:11", "alu", "ADD → 0x…7D [Z=0 N=0]", P["texto_tenue"]),
             ("12:04:15", "memoria", "MISALIGNED 4B", P["alerta"])]
    for i, (hora, origen, texto, color) in enumerate(traza):
        fy = ty + 28 + i * 16
        L.texto(x_ctx + 26, fy, hora, P["texto_debil"], 8, MONO)
        L.texto(x_ctx + 76, fy, origen, P["ambar"], 8, MONO)
        L.texto(x_ctx + 146, fy, texto, color, 8, MONO)

    # -- barra de estado ----------------------------------------------------
    L.linea(0, 740 - 26, 1366, 740 - 26, P["borde"])
    L.texto(14, 740 - 9, "conda: Enigma-64  ·  Python 3.11  ·  tkinter/ttk",
            P["texto_debil"], 8, MONO)
    L.texto(1366 - 14, 740 - 9, "4/4 modulos conectados", P["ok"], 8, MONO, ancla="end")
    return L.guardar("00_shell_completo.svg")


# ---------------------------------------------------------------------------
# Bocetos de los paneles sueltos
# ---------------------------------------------------------------------------


def _ventana_suelta(L: Lienzo, titulo: str, comando: str) -> float:
    """
    Marco de una ventana con un solo panel dentro. Es como se ve un modulo
    cuando se arranca por separado, que es el requisito del profesor.
    """
    L.rect(0, 0, L.ancho, 58, P["abismo"])
    L.linea(0, 58, L.ancho, 58, P["borde"])
    L.marca(16, 7, 36)
    L.texto(62, 26, titulo, P["texto"], 14, SANS, True)
    L.texto(62, 43, comando, P["ambar"], 9, MONO)
    L.insignia(L.ancho - 158, 19, 142, "MODULO INDEPENDIENTE", P["ok"])
    return 58


def panel_memoria() -> pathlib.Path:
    L = Lienzo(760, 660, "Enigma-64 - Panel de memoria RAM")
    top = _ventana_suelta(L, "Memoria RAM y buses",
                          "python -m enigma64.ui.paneles.panel_memoria")
    y = L.tarjeta(14, top + 14, 732, 660 - top - 28, "Memoria RAM y buses",
                  "Integrante 1  ·  enigma64.memoria", P["cian"])

    L.campo(30, y + 12, 210, "Direccion", "0x00200000")
    L.campo(254, y + 12, 110, "Tamano de acceso", "8 bytes")
    L.campo(378, y + 12, 200, "Valor a escribir", "0x454E494700000001")
    L.boton(592, y + 12, 138, "Ir a la direccion")

    L.boton(30, y + 62, 100, "Leer")
    L.boton(138, y + 62, 100, "Escribir", True)
    L.boton(246, y + 62, 100, "Reiniciar")
    L.rect(360, y + 66, 15, 15, P["abismo"], P["ambar"], radio=3)
    L.texto(366, y + 78, "✓", P["ambar"], 10, MONO, True)
    L.texto(383, y + 78, "Verificar alineacion natural", P["texto_tenue"], 9.5)

    L.linea(30, y + 104, 730, y + 104)
    L.texto(30, y + 126, "SENAL DEL BUS DE CONTROL", P["texto_debil"], 8, SANS, True)
    for i, (senal, color, on) in enumerate([
            ("READY", P["ok"], True), ("MISALIGNED", P["alerta"], False),
            ("MMIO", P["violeta"], False), ("ADDR_FAULT", P["fallo"], False)]):
        L.led(30 + i * 176, y + 148, senal, color, on)

    L.volcado_hex(30, y + 172, 0x00200000, 14, 700, resaltar=0)

    yb = y + 172 + 14 * 17 + 24 + 20
    for i, (etiqueta, valor) in enumerate([
            ("Paginas asignadas", "3"), ("Memoria reservada", "12 KiB"),
            ("Tamano de pagina", "4 KiB"), ("Region actual", "Programas y datos")]):
        L.texto(30 + i * 178, yb, etiqueta.upper(), P["texto_debil"], 8, SANS, True)
        L.texto(30 + i * 178, yb + 18, valor, P["cian"], 12, MONO, True)
    return L.guardar("01_panel_memoria.svg")


def panel_registros() -> pathlib.Path:
    L = Lienzo(660, 600, "Enigma-64 - Panel del banco de registros")
    top = _ventana_suelta(L, "Banco de registros",
                          "python -m enigma64.ui.paneles.panel_registros")
    y = L.tarjeta(14, top + 14, 632, 600 - top - 28, "Banco de registros",
                  "Integrante 2  ·  enigma64.registros", P["ok"])

    L.texto(30, y + 8, "REG", P["texto_debil"], 8.5, MONO, True)
    L.texto(104, y + 8, "COD", P["texto_debil"], 8.5, MONO, True)
    L.texto(158, y + 8, "HEXADECIMAL", P["texto_debil"], 8.5, MONO, True)
    L.texto(616, y + 8, "DECIMAL CON SIGNO", P["texto_debil"], 8.5, MONO, True, "end")
    L.linea(28, y + 16, 618, y + 16)

    filas = [("R0", "0x0", "0x0000000000000000", "0", "cableado a cero"),
             ("R1", "0x1", "0x0000000000000078", "120", ""),
             ("R2", "0x2", "0x0000000000000005", "5", ""),
             ("R3", "0x3", "0x0000000000000000", "0", ""),
             ("R4", "0x4", "0x0000000000000000", "0", ""),
             ("R5 (RV)", "0x5", "0x0000000000200000", "2097152", ""),
             ("R6 (SP)", "0x6", "0x00000000EFFFFFFF", "4026531839", ""),
             ("R7 (BP)", "0x7", "0x0000000000000000", "0", ""),
             ("PC", "0x8", "0x0000000000200000", "2097152", ""),
             ("SR", "0x9", "0x0000000000000041", "65", "")]
    for i, (nombre, cod, hexa, dec, nota) in enumerate(filas):
        fy = y + 36 + i * 21
        if nombre == "R1":
            L.rect(26, fy - 14, 594, 20, P["ambar"], radio=3, opacidad=0.14)
        tenue = hexa.endswith("0000000000000000")
        L.texto(30, fy, nombre, P["texto"] if not tenue else P["texto_tenue"], 10, MONO)
        L.texto(104, fy, cod, P["texto_debil"], 10, MONO)
        L.texto(158, fy, hexa, P["texto_debil"] if tenue else P["cian"], 10, MONO)
        L.texto(616, fy, dec, P["texto_debil"] if tenue else P["texto_tenue"], 10,
                MONO, ancla="end")
        if nota:
            L.texto(330, fy, nota, P["texto_debil"], 8.5)

    yf = y + 36 + len(filas) * 21 + 6
    L.linea(28, yf, 618, yf)
    L.texto(30, yf + 24, "BANDERAS DEL SR  (pulsa para conmutar)",
            P["texto_debil"], 8, SANS, True)
    for i, (b, nombre, on) in enumerate([
            ("Z", "Zero", False), ("N", "Negative", False), ("C", "Carry", False),
            ("V", "oVerflow", False), ("M", "Misaligned", False),
            ("I", "Interrupt", False), ("S", "Supervisor", True)]):
        bx = 30 + i * 84
        L.led(bx, yf + 48, b, P["ambar"] if on else P["ok"], on)
        L.texto(bx, yf + 66, nombre, P["texto_debil"], 7.5)

    L.campo(30, yf + 96, 150, "Registro", "R1")
    L.campo(194, yf + 96, 220, "Nuevo valor", "0x78")
    L.boton(428, yf + 96, 92, "Escribir", True)
    L.boton(528, yf + 96, 90, "RESET")
    return L.guardar("02_panel_registros.svg")


def panel_alu() -> pathlib.Path:
    L = Lienzo(660, 560, "Enigma-64 - Panel de la ALU")
    top = _ventana_suelta(L, "Unidad aritmetico-logica",
                          "python -m enigma64.ui.paneles.panel_alu")
    y = L.tarjeta(14, top + 14, 632, 560 - top - 28, "Unidad aritmetico-logica",
                  "Integrante 2  ·  enigma64.alu", P["ambar"])

    L.texto(30, y + 6, "OPERACION", P["texto_debil"], 8, SANS, True)
    familias = [("Aritmeticas", ["ADD", "SUB", "MUL", "DIV", "ADDI", "SUBI", "INC", "DEC"]),
                ("Logicas", ["AND", "OR", "XOR", "NOT"]),
                ("Desplazamientos", ["SHL", "SHR", "ASR"]),
                ("Comparacion", ["CMP"])]
    fy = y + 22
    for familia, ops in familias:
        L.texto(30, fy + 10, familia, P["texto_debil"], 8.5)
        x = 140
        for op in ops:
            activo = op == "ADD"
            w = 46
            L.rect(x, fy, w, 20, P["ambar"] if activo else P["abismo"],
                   P["ambar"] if activo else P["borde"], radio=4,
                   opacidad=1 if activo else None)
            L.texto(x + w / 2, fy + 14, op, P["abismo"] if activo else P["texto_tenue"],
                    9, MONO, True, "middle")
            x += w + 6
        fy += 27

    L.linea(28, fy + 6, 618, fy + 6)
    L.campo(30, fy + 32, 270, "Latch A", "0x0000000000000078")
    L.campo(318, fy + 32, 270, "Latch B", "0x0000000000000005")
    L.boton(30, fy + 78, 120, "Ejecutar", True)
    L.rect(164, fy + 82, 15, 15, P["abismo"], P["ambar"], radio=3)
    L.texto(170, fy + 94, "✓", P["ambar"], 10, MONO, True)
    L.texto(187, fy + 94, "Volcar banderas al registro SR", P["texto_tenue"], 9.5)

    L.rect(30, fy + 118, 558, 74, P["abismo"], P["borde"], radio=6)
    L.texto(44, fy + 142, "Z", P["texto_debil"], 10, MONO, True)
    L.texto(66, fy + 143, "0x000000000000007D", P["cian"], 15, MONO, True)
    L.texto(44, fy + 164, "125 con signo   ·   escribe el registro destino",
            P["texto_tenue"], 9.5, MONO)
    L.texto(44, fy + 180, "0000…0000 0111 1101", P["texto_debil"], 9, MONO)

    L.texto(30, fy + 216, "BANDERAS PRODUCIDAS  ·  afectadas por ADD: Z N C V",
            P["texto_debil"], 8, SANS, True)
    for i, (b, on) in enumerate([("Z", False), ("N", False), ("C", False), ("V", False)]):
        L.led(30 + i * 90, fy + 238, b, P["ok"], on)
    return L.guardar("03_panel_alu.svg")


def panel_cargador() -> pathlib.Path:
    L = Lienzo(760, 700, "Enigma-64 - Panel del cargador")
    top = _ventana_suelta(L, "Cargador y manipulador de bits",
                          "python -m enigma64.ui.paneles.panel_cargador")
    y = L.tarjeta(14, top + 14, 732, 400, "Cargador",
                  "Integrante 4  ·  enigma64.cargador", P["ambar"])

    L.campo(30, y + 12, 520, "Archivo del programa (.e64 / .bin / .txt)",
            "programas/factorial.e64")
    L.boton(564, y + 12, 166, "Examinar…")
    L.texto(30, y + 66, "O PEGAR UN VOLCADO EN TEXTO", P["texto_debil"], 8, SANS, True)
    L.rect(30, y + 76, 700, 58, P["abismo"], P["borde"], radio=5)
    L.texto(42, y + 96, "10 12 00  14 23 30  00 11 41  00 1A 4C", P["cian"], 10, MONO)
    L.texto(42, y + 114, "0x00 0x00 0x00 0x00", P["cian"], 10, MONO)

    L.campo(30, y + 162, 210, "Direccion destino", "0x00200000")
    L.campo(254, y + 162, 210, "Punto de entrada", "0x00200000")
    L.rect(478, y + 166, 15, 15, P["abismo"], P["ambar"], radio=3)
    L.texto(484, y + 178, "✓", P["ambar"], 10, MONO, True)
    L.texto(501, y + 178, "Inicializar contexto de CPU", P["texto_tenue"], 9.5)
    L.boton(478, y + 196, 252, "Cargar en memoria", True)

    L.rect(30, y + 240, 700, 84, P["abismo"], P["ok"], radio=6, opacidad=None)
    L.texto(44, y + 264, "CARGA ACEPTADA", P["ok"], 9, SANS, True)
    L.texto(44, y + 284, "224 bytes  ·  0x00200000 → 0x002000DF  ·  region: Programas y datos",
            P["texto_tenue"], 9.5, MONO)
    L.texto(44, y + 302, "PC ← 0x00200000   SP ← 0x00000000EFFFFFFF   R5 ← 0x00200000",
            P["cian"], 9.5, MONO)

    y2 = L.tarjeta(14, top + 428, 732, 700 - top - 442, "Manipulador de bits",
                   "Lectura, escritura y conmutacion bit a bit", P["cian"])
    L.campo(30, y2 + 12, 210, "Direccion del byte", "0x00200003")
    L.texto(254, y2 + 4, "BYTE ACTUAL  ·  pulsa un bit para conmutarlo",
            P["texto_debil"], 8, SANS, True)

    bits = [0, 1, 0, 0, 0, 1, 1, 1]
    for i, bit in enumerate(bits):
        bx = 254 + i * 30
        L.rect(bx, y2 + 14, 26, 26, P["cian"] if bit else P["abismo"],
               P["cian"] if bit else P["borde"], radio=4)
        L.texto(bx + 13, y2 + 31, str(bit), P["abismo"] if bit else P["texto_debil"],
                11, MONO, True, "middle")
        L.texto(bx + 13, y2 + 52, str(7 - i), P["texto_debil"], 7.5, MONO, ancla="middle")
    L.texto(504, y2 + 31, "0x47  ·  'G'", P["cian"], 11, MONO, True)
    return L.guardar("04_panel_cargador.svg")


def panel_mapa() -> pathlib.Path:
    L = Lienzo(560, 780, "Enigma-64 - Mapa de memoria")
    top = _ventana_suelta(L, "Mapa de memoria",
                          "python -m enigma64.ui.paneles.panel_mapa")
    y = L.tarjeta(14, top + 14, 532, 780 - top - 28, "Mapa de memoria",
                  "4 GiB fisicos implementados  ·  Tarea 9", P["violeta"])

    regiones = [("Vectores", "0x00000000", "0x00000FFF", "R / X", P["fallo"], 22),
                ("Monitor + Enlazador-Cargador", "0x00001000", "0x000FFFFF", "R / X",
                 P["ambar"], 30),
                ("Trabajo del cargador", "0x00100000", "0x0011FFFF", "R/W admin",
                 P["ambar_oscuro"], 22),
                ("Tablas del sistema", "0x00120000", "0x001FFFFF", "R/W admin",
                 P["ambar_oscuro"], 22),
                ("Programas y datos", "0x00200000", "0xBFFFFFFF", "R / W / X",
                 P["ok"], 96),
                ("Pila", "0xC0000000", "0xEFFFFFFF", "R/W no ejecutable", P["cian"], 48),
                ("Buffers de I/O y DMA", "0xF0000000", "0xFEFFFFFF", "R/W no cacheable",
                 P["cian_oscuro"], 30),
                ("I/O mapeada", "0xFF000000", "0xFFFFFFFF", "R/W admin", P["violeta"], 30)]
    yr = y + 6
    for nombre, ini, fin, permisos, color, alto in regiones:
        L.rect(30, yr, 10, alto, color, radio=2)
        L.texto(50, yr + alto / 2 - 2, nombre, P["texto"], 10)
        L.texto(50, yr + alto / 2 + 11, permisos, P["texto_debil"], 8)
        L.texto(530, yr + alto / 2 - 2, ini, color, 9.5, MONO, ancla="end")
        L.texto(530, yr + alto / 2 + 11, fin, P["texto_debil"], 9, MONO, ancla="end")
        yr += alto + 5

    L.linea(28, yr + 10, 532, yr + 10)
    L.texto(30, yr + 32, "CONTROLADORES MAPEADOS EN MEMORIA  (4 KiB cada uno)",
            P["texto_debil"], 8, SANS, True)
    for i, (base, nombre) in enumerate([
            ("0xFF000000", "Entrada (teclado)"), ("0xFF001000", "Salida (pantalla)"),
            ("0xFF002000", "Memoria secundaria (disco)"),
            ("0xFF003000", "Interfaz de red"), ("0xFF004000", "Temporizador / reloj")]):
        ly = yr + 52 + i * 17
        L.texto(30, ly, base, P["violeta"], 9.5, MONO)
        L.texto(120, ly, nombre, P["texto_tenue"], 9.5)
    L.texto(30, yr + 156, "+0x00 CTRL   +0x08 STATUS   +0x10 DATA   +0x18 ADDR   +0x20 COUNT",
            P["texto_debil"], 8.5, MONO)
    return L.guardar("05_panel_mapa.svg")


def panel_cpu() -> pathlib.Path:
    """La FSM multiciclo. Se dibuja el estado ENCENDIDO, el que se vera cuando
    se fusione la rama del Integrante 3."""
    L = Lienzo(880, 620, "Enigma-64 - Unidad de Control")
    top = _ventana_suelta(L, "Unidad de Control (FSM)",
                          "python -m enigma64.ui.paneles.panel_cpu")
    y = L.tarjeta(14, top + 14, 852, 620 - top - 28, "Unidad de Control (FSM)",
                  "Integrante 3  ·  enigma64.cpu", P["violeta"])

    L.boton(30, y + 10, 128, "Paso (una fase)")
    L.boton(166, y + 10, 158, "Instruccion completa", True)
    L.boton(332, y + 10, 140, "Ejecutar hasta HLT")
    L.boton(480, y + 10, 84, "RESET")
    L.insignia(736, y + 15, 112, "EJECUTANDO", P["ok"])

    for i, (etiqueta, valor) in enumerate([("Ciclos de reloj", "48"),
                                           ("Instrucciones completadas", "11")]):
        L.texto(30 + i * 210, y + 68, etiqueta.upper(), P["texto_debil"], 8, SANS, True)
        L.texto(30 + i * 210, y + 88, valor, P["cian"], 14, MONO, True)

    L.linea(28, y + 108, 852, y + 108)
    L.texto(30, y + 130, "MAQUINA DE ESTADOS MULTICICLO", P["texto_debil"], 8, SANS, True)
    fases = ["FETCH", "DECODE", "EXECUTE", "MEMORY", "WRITE-BACK"]
    x = 30
    for i, fase in enumerate(fases):
        activa = fase == "EXECUTE"
        w = 148
        L.rect(x, y + 142, w, 32, P["violeta"] if activa else P["abismo"],
               P["violeta"] if activa else P["borde"], radio=5,
               opacidad=None if activa else None)
        L.texto(x + w / 2, y + 162, fase, P["abismo"] if activa else P["texto_debil"],
                9.5, MONO, True, "middle")
        x += w
        if i < len(fases) - 1:
            L.texto(x + 6, y + 162, "→", P["texto_debil"], 10, MONO, ancla="middle")
            x += 14
    L.texto(30, y + 196,
            "La ALU opera sobre A y B; el resultado queda en Z y se calculan las banderas.",
            P["texto_tenue"], 9)

    L.linea(28, y + 214, 852, y + 214)
    L.texto(30, y + 236, "REGISTROS MICROARQUITECTONICOS  ·  RUTA INTERNA DE DATOS",
            P["texto_debil"], 8, SANS, True)
    micro = [("MAR", "0x0000000000200014"), ("MDR", "0x1222000142FFF631"),
             ("IR",  "0x0000000000122320"), ("A",   "0x0000000000000078"),
             ("B",   "0x0000000000000005"), ("Z",   "0x000000000000007D")]
    for i, (nombre, valor) in enumerate(micro):
        fila, columna = divmod(i, 2)
        mx, my = 30 + columna * 420, y + 262 + fila * 24
        L.texto(mx, my, nombre, P["texto_tenue"], 10, MONO, True)
        L.texto(mx + 52, my, valor, P["cian"], 10, MONO)

    L.texto(30, y + 350, "BUFFER DE PREBUSQUEDA  ·  16 BYTES", P["texto_debil"], 8,
            SANS, True)
    L.texto(30, y + 372, "12 33 20 15 22 00 01 42 FF F6 31 31 00 08 00 00",
            P["cian"], 10, MONO)
    return L.guardar("07_panel_cpu.svg")


def panel_mmio() -> pathlib.Path:
    L = Lienzo(880, 640, "Enigma-64 - I/O mapeada en memoria")
    top = _ventana_suelta(L, "I/O mapeada en memoria",
                          "python -m enigma64.ui.paneles.panel_mmio")
    y = L.tarjeta(14, top + 14, 852, 640 - top - 28, "I/O mapeada en memoria",
                  "0xFF000000 – 0xFFFFFFFF  ·  Tarea 9", P["violeta"])

    L.rect(30, y + 8, 822, 46, P["elevado_alto"], P["alerta"], radio=6)
    L.texto(42, y + 26, "BANCO PROVISIONAL", P["alerta"], 8.5, SANS, True)
    L.texto(42, y + 43,
            "La RAM enruta 0xFF...... al bus de perifericos sin almacenar nada. "
            "Se reemplaza en cuanto exista enigma64/perifericos.py.",
            P["texto_tenue"], 9)

    L.texto(30, y + 80, "CONTROLADORES  ·  UNA PAGINA DE 4 KiB CADA UNO",
            P["texto_debil"], 8, SANS, True)
    controladores = [("Entrada (teclado)", "0xFF000000", P["cian"], False),
                     ("Salida (pantalla)", "0xFF001000", P["ok"], False),
                     ("Memoria secundaria (disco)", "0xFF002000", P["ambar"], True),
                     ("Interfaz de red", "0xFF003000", P["violeta"], False),
                     ("Temporizador / reloj", "0xFF004000", P["alerta"], False)]
    cy = y + 92
    for nombre, base, color, activo in controladores:
        if activo:
            L.rect(28, cy, 826, 30, color, radio=5, opacidad=0.12)
            L.rect(28, cy, 826, 30, "none", color, radio=5)
        L.rect(34, cy + 5, 4, 20, color, radio=2)
        L.texto(50, cy + 19, nombre, P["texto"], 10)
        L.texto(844, cy + 19, base, color, 10, MONO, ancla="end")
        cy += 33

    L.linea(28, cy + 8, 852, cy + 8)
    L.texto(30, cy + 30, "REGISTROS  ·  MEMORIA SECUNDARIA (DISCO)",
            P["texto_debil"], 8, SANS, True)
    for i, (nombre, columna) in enumerate([("REGISTRO", 30), ("DIRECCION", 150),
                                           ("VALOR (64 BITS)", 270),
                                           ("", 470)]):
        if nombre:
            L.texto(columna, cy + 50, nombre, P["texto_debil"], 8, MONO, True)
    registros = [("CTRL", "0xFF002000", "0x0000000000000001", "Comando que se ordena al controlador."),
                 ("STATUS", "0xFF002008", "0x0000000000000001", "Estado devuelto: listo, ocupado, error."),
                 ("DATA", "0xFF002010", "0x0000000000000000", "Dato transferido en la operacion."),
                 ("ADDR", "0xFF002018", "0x000000000000002A", "Direccion de RAM o bloque implicado."),
                 ("COUNT", "0xFF002020", "0x0000000000000001", "Cantidad de unidades a transferir.")]
    for i, (nombre, direccion, valor, nota) in enumerate(registros):
        ry = cy + 72 + i * 28
        L.texto(30, ry + 14, nombre, P["texto"], 10, MONO, True)
        L.texto(150, ry + 14, direccion, P["ambar"], 9.5, MONO)
        L.rect(270, ry, 186, 22, P["abismo"], P["borde"], radio=4)
        L.texto(280, ry + 15, valor, P["cian"], 9.5, MONO)
        L.texto(470, ry + 14, nota, P["texto_debil"], 8.5)
    return L.guardar("08_panel_mmio.svg")


def panel_algoritmos() -> pathlib.Path:
    L = Lienzo(920, 745, "Enigma-64 - Algoritmos de verificacion")
    top = _ventana_suelta(L, "Algoritmos de verificacion",
                          "python -m enigma64.ui.paneles.panel_algoritmos")
    y = L.tarjeta(14, top + 14, 892, 745 - top - 28, "Algoritmos de verificacion",
                  "Tarea 9  ·  factorial, Euclides y Fibonacci", P["ok"])

    x = 30
    for nombre, activo in [("Factorial de N", True), ("Algoritmo de Euclides", False),
                           ("Sucesion de Fibonacci", False)]:
        w = 20 + len(nombre) * 7
        L.rect(x, y + 8, w, 26, P["ok"] if activo else P["abismo"],
               P["ok"] if activo else P["borde"], radio=5)
        L.texto(x + w / 2, y + 25, nombre, P["abismo"] if activo else P["texto_tenue"],
                9.5, MONO, True, "middle")
        x += w + 6

    L.texto(30, y + 56, "Calcula N! por multiplicaciones sucesivas con un bucle decremental.",
            P["texto_tenue"], 9)
    for i, (etiqueta, valor) in enumerate([("Direccion de carga", "0x00200000"),
                                           ("Variables en RAM", "0x00201000"),
                                           ("Tamano del programa", "41 bytes"),
                                           ("Resultado esperado", "5! = 120")]):
        L.texto(30 + i * 215, y + 82, etiqueta.upper(), P["texto_debil"], 8, SANS, True)
        L.texto(30 + i * 215, y + 100, valor, P["cian"], 10.5, MONO, True)

    L.texto(30, y + 128, "PSEUDOCODIGO Y TRADUCCION MANUAL A LENGUAJE DE MAQUINA",
            P["texto_debil"], 8, SANS, True)
    L.rect(30, y + 138, 832, 300, P["abismo"], P["borde"], radio=6)

    ly = y + 158
    for linea in ["; Pseudocodigo",
                  ";   N = Mem[0x00201000]",
                  ";   factorial = 1",
                  ";   mientras N > 0: factorial *= N ; N -= 1",
                  ";   Mem[0x00201008] = factorial"]:
        L.texto(42, ly, linea, P["texto_tenue"] if linea.startswith(";  ") else P["texto_debil"],
                9, MONO)
        ly += 15

    ly += 10
    L.texto(42, ly, "DIRECCION    ENSAMBLADOR                CODIGO MAQUINA (BIG-ENDIAN)",
            P["texto_debil"], 8.5, MONO, True)
    ly += 17
    listado = [("0x00200000", "ADDI  R1, R0, 0x0020", "14 10 00 20", "R1 = 0x0020"),
               ("0x00200004", "SHL   R1, R1, 16", "24 11 00 10", "R1 = 0x00200000"),
               ("0x00200008", "ADDI  R1, R1, 0x1000", "14 11 10 00", "base de datos"),
               ("0x0020000C", "LOAD  R2, [R1 + 0]", "30 21 00 00", "R2 = N"),
               ("0x00200010", "ADDI  R3, R0, 1", "14 30 00 01", "factorial = 1"),
               ("0x00200014", "CMP   R2, R0", "27 02 00", "compara N con 0"),
               ("0x00200017", "JZ    FIN_FACT", "41 00 0A", "si N == 0 (+10B)"),
               ("0x0020001A", "MUL   R3, R3, R2", "12 33 20", "factorial *= N"),
               ("0x0020001D", "SUBI  R2, R2, 1", "15 22 00 01", "N = N - 1"),
               ("0x00200021", "JNZ   LOOP_FACT", "42 FF F6", "repetir (-10B)"),
               ("0x00200024", "STORE R3, [R1 + 8]", "31 31 00 08", "guarda el resultado"),
               ("0x00200028", "HLT", "00", "detener ejecucion")]
    for direccion, mnemonico, maquina, comentario in listado:
        L.texto(42, ly, direccion, P["ambar"], 9, MONO)
        L.texto(140, ly, mnemonico, P["texto"], 9, MONO)
        L.texto(330, ly, maquina, P["cian"], 9, MONO)
        L.texto(440, ly, "; " + comentario, P["texto_debil"], 9, MONO)
        ly += 14

    L.boton(30, y + 452, 130, "Cargar en RAM", True)
    L.boton(168, y + 452, 142, "Verificar resultado")
    L.boton(318, y + 452, 92, "Ejecutar")
    L.texto(420, y + 472, "Ejecutar necesita la Unidad de Control (Integrante 3)",
            P["texto_debil"], 8.5)

    L.rect(30, y + 496, 832, 70, P["abismo"], P["ok"], radio=6)
    L.texto(44, y + 518, "PROGRAMA CARGADO", P["ok"], 9, SANS, True)
    L.texto(44, y + 536, "41 bytes  ·  0x00200000 → 0x00200028  ·  entry point 0x00200000",
            P["texto_tenue"], 9, MONO)
    L.texto(44, y + 552, "N = 5 sembrado en 0x00201000  ·  PC y R5 en el entry point",
            P["cian"], 9, MONO)
    return L.guardar("09_panel_algoritmos.svg")


def panel_fpu() -> pathlib.Path:
    L = Lienzo(900, 640, "Enigma-64 - Panel de la FPU")
    top = _ventana_suelta(L, "Unidad de punto flotante",
                          "python -m enigma64.ui.paneles.panel_fpu")
    y = L.tarjeta(14, top + 14, 872, 640 - top - 28, "Unidad de punto flotante",
                  "IEEE 754 doble precision  ·  enigma64.fpu", P["cian"])

    # Selector de operacion: en ambar apagado, la rutina que aun no se entrego.
    L.texto(30, y + 6, "OPERACION", P["texto_debil"], 8, SANS, True)
    familias = [("Aritmeticas", ["FADD", "FSUB", "FMUL", "FDIV", "FSQRT"]),
                ("Comparacion", ["FCMP"]),
                ("Conversiones", ["I2F", "F2I"])]
    fy = y + 20
    for familia, ops in familias:
        L.texto(30, fy + 14, familia, P["texto_debil"], 8.5)
        x = 140
        for op in ops:
            activo = op == "FADD"
            color = P["alerta"] if op == "FSQRT" else P["texto_tenue"]
            L.rect(x, fy, 52, 20, P["ambar"] if activo else P["abismo"],
                   P["ambar"] if activo else P["borde"], radio=4)
            L.texto(x + 26, fy + 14, op, P["abismo"] if activo else color,
                    9, MONO, True, "middle")
            x += 58
        fy += 25

    # Calculadora reactiva: no hay boton de ejecutar.
    L.linea(28, fy + 6, 870, fy + 6)
    L.campo(30, fy + 32, 410, "Operando A  ·  decimal o patron 0x", "0.1")
    L.campo(458, fy + 32, 410, "Operando B  ·  decimal o patron 0x", "0.2")
    L.texto(30, fy + 74, "0x3FB999999999999A  ·  normal", P["texto_debil"], 8.5, MONO)
    L.texto(458, fy + 74, "0x3FC999999999999A  ·  normal", P["texto_debil"], 8.5, MONO)

    L.rect(30, fy + 88, 838, 70, P["abismo"], P["borde"], radio=6)
    L.texto(44, fy + 114, "0.1  +  0.2  =", P["texto_debil"], 10, MONO, True)
    L.texto(160, fy + 115, "0.3", P["cian"], 15, MONO, True)
    L.insignia(672, fy + 98, 182, "COINCIDE CON IEEE 754", P["ok"])
    L.texto(44, fy + 134, "0x3FD3333333333334   ·   595 ciclos de reloj   ·   VEC_FADD",
            P["texto_tenue"], 9.5, MONO)
    L.texto(44, fy + 150, "IEEE 754 del anfitrion: 0.30000000000000004",
            P["texto_debil"], 9.5, MONO)

    condiciones = [("CERO", P["ok"], False), ("NEGATIVO", P["violeta"], False),
                   ("SUBNORMAL", P["alerta"], False), ("INFINITO", P["alerta"], False),
                   ("NaN", P["fallo"], False), ("INEXACTO", P["cian"], True)]
    for i, (nombre, color, encendido) in enumerate(condiciones):
        L.led(30 + i * 112, fy + 180, nombre, color, encendido)

    # Visor IEEE 754: 1 + 11 + 52 celdas, mas el bit implicito sin almacenar.
    vy = fy + 206
    L.texto(30, vy, "VISOR IEEE 754", P["texto_debil"], 8, SANS, True)
    x = 140
    for texto, activo in (("Operando A", True), ("Operando B", False),
                          ("Resultado", False)):
        L.rect(x, vy - 13, 84, 20, P["cian"] if activo else P["abismo"],
               P["cian"] if activo else P["borde"], radio=4)
        L.texto(x + 42, vy + 1, texto, P["abismo"] if activo else P["texto_tenue"],
                8.5, SANS, True, "middle")
        x += 90

    patron = 0x3FB999999999999A
    celda, cy = 12.3, vy + 34
    x = 30.0
    for nombre, alto, bajo, color in (("S", 63, 63, P["violeta"]),
                                      ("EXPONENTE  ·  11 bits", 62, 52, P["ambar"]),
                                      ("MANTISA  ·  52 bits", 51, 0, P["cian"])):
        if bajo == 0:
            L.rect(x, cy, celda - 1, 26, P["elevado"], P["texto_tenue"])
            L.texto(x + celda / 2, cy + 17, "1", P["texto"], 8, MONO, True, "middle")
            L.texto(x + celda / 2, cy + 50, "bit implicito", P["texto_tenue"], 7,
                    SANS, False, "middle")
            x += celda + 8
        L.texto(x, cy - 6, nombre, color, 8, SANS, True)
        L.texto(x + celda / 2, cy + 38, str(alto), P["texto_debil"], 7, MONO,
                False, "middle")
        for indice in range(alto, bajo - 1, -1):
            encendido = (patron >> indice) & 1
            L.rect(x, cy, celda - 1, 26, color if encendido else P["abismo"],
                   color if encendido else P["borde"])
            L.texto(x + celda / 2, cy + 17, str(encendido),
                    P["abismo"] if encendido else P["texto_debil"], 8, MONO, True,
                    "middle")
            x += celda
        if bajo != alto:
            L.texto(x - celda / 2, cy + 38, str(bajo), P["texto_debil"], 7, MONO,
                    False, "middle")
        x += 8

    dy = cy + 70
    for i, (rotulo, color, valor) in enumerate((
            ("Signo", P["violeta"], "0   →  positivo"),
            ("Exponente", P["ambar"], "0x3FB = 1019   →  1019 - 1023 = -4"),
            ("Mantisa", P["cian"], "0x999999999999A   →  con el bit implicito 1:  "
                                   "0x1999999999999A"),
            ("Valor", P["texto"], "+1.6 x 2^-4  =  0.1   (normal)"))):
        L.texto(30, dy + i * 16, rotulo, color, 8.5, SANS, True)
        L.texto(140, dy + i * 16, valor, P["texto_tenue"], 9.5, MONO)

    ry = dy + 80
    L.texto(30, ry, "RUTINAS DE LA BIBLIOTECA", P["texto_debil"], 8, SANS, True)
    x = 30
    for texto, conectada in (("FADD", True), ("FSUB", True), ("FMUL", True),
                             ("FDIV", True), ("FSQRT", False), ("FCMP", True),
                             ("I2F", True), ("F2I", True), ("ORACULO", False),
                             ("CONSTANTE DE BRUN", False),
                             ("BATERIA DE PRUEBAS", False)):
        w = 16 + len(texto) * 8
        L.insignia(x, ry + 10, w, texto, P["ok"] if conectada else P["alerta"], 20)
        x += w + 4
    return L.guardar("10_panel_fpu.svg")


def sistema_diseno() -> pathlib.Path:
    L = Lienzo(1000, 660, "Enigma-64 - Sistema de diseno Noctua")
    L.rect(0, 0, 1000, 92, P["abismo"])
    L.linea(0, 92, 1000, 92, P["borde"])
    L.marca(24, 24, 44)
    L.texto(82, 42, "Sistema de diseno Noctua", P["texto"], 19, SANS, True)
    L.texto(83, 62, "enigma64/ui/core/tema.py  ·  fuente unica de color y tipografia",
            P["texto_tenue"], 9.5, MONO)

    L.texto(30, 128, "PALETA", P["ambar"], 9, SANS, True)
    muestras = [("abismo", "fondo de la aplicacion"), ("noche", "superficie base"),
                ("elevado", "tarjetas"), ("borde", "trazos"),
                ("texto", "texto principal"), ("texto_tenue", "texto secundario"),
                ("ambar", "marca Noctua"), ("cian", "datos y direcciones"),
                ("violeta", "espacio MMIO"), ("ok", "READY"),
                ("alerta", "MISALIGNED"), ("fallo", "ADDR_FAULT")]
    for i, (clave, uso) in enumerate(muestras):
        col, fila = i % 4, i // 4
        x, yy = 30 + col * 240, 146 + fila * 70
        L.rect(x, yy, 54, 54, P[clave], P["borde"], radio=8)
        L.texto(x + 66, yy + 20, clave, P["texto"], 10.5, MONO, True)
        L.texto(x + 66, yy + 35, P[clave].upper(), P["texto_tenue"], 9, MONO)
        L.texto(x + 66, yy + 49, uso, P["texto_debil"], 8.5)

    L.linea(28, 372, 972, 372)
    L.texto(30, 398, "TIPOGRAFIA", P["ambar"], 9, SANS, True)
    L.texto(30, 424, "Inter / Segoe UI / DejaVu Sans", P["texto"], 13, SANS, True)
    L.texto(30, 442, "titulos, botones y textos de ayuda", P["texto_debil"], 9)
    L.texto(30, 470, "JetBrains Mono / DejaVu Sans Mono", P["texto"], 13, MONO, True)
    L.texto(30, 488, "0x00200000  ·  45 4E 49 47  ·  01000111", P["cian"], 11, MONO)
    L.texto(30, 504, "todo valor hexadecimal, binario o decimal", P["texto_debil"], 9)

    L.texto(430, 398, "COMPONENTES", P["ambar"], 9, SANS, True)
    L.boton(430, 414, 120, "Secundario")
    L.boton(562, 414, 120, "Primario", True)
    L.insignia(694, 418, 126, "READY", P["ok"])
    L.insignia(834, 418, 138, "ADDR_FAULT", P["fallo"])
    for i, (b, color, on) in enumerate([("Z", P["ok"], True), ("N", P["ok"], False),
                                        ("C", P["ok"], False), ("V", P["ok"], False)]):
        L.led(430 + i * 66, 470, b, color, on)
    L.campo(694, 466, 278, "Campo de valor", "0x0000000000000078")

    L.linea(28, 534, 972, 534)
    L.texto(30, 560, "PRINCIPIO DE AISLAMIENTO", P["ambar"], 9, SANS, True)
    L.texto(30, 584,
            "Ningun panel importa a otro panel. Se comunican publicando eventos "
            "en el bus (enigma64/ui/core/bus.py),",
            P["texto_tenue"], 10)
    L.texto(30, 602,
            "igual que los modulos reales se comunican por el bus de control. "
            "Por eso cada panel arranca solo.",
            P["texto_tenue"], 10)
    L.texto(30, 628, "python -m enigma64.ui.paneles.panel_memoria", P["cian"], 10, MONO)
    return L.guardar("06_sistema_diseno.svg")


def generar_todo() -> List[pathlib.Path]:
    return [shell_completo(), panel_memoria(), panel_registros(), panel_alu(),
            panel_cargador(), panel_mapa(), sistema_diseno(), panel_cpu(),
            panel_mmio(), panel_algoritmos(), panel_fpu()]


if __name__ == "__main__":
    for ruta in generar_todo():
        print(f"  generado  {ruta.name}")
