"""Genera docs/reportes/Tarea_29_Reporte_Tecnico_Enigma64.pdf (ReportLab)."""
import json
import math
import sys

from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String, Circle, Polygon
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    CondPageBreak, KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate,
    Spacer, Table, TableStyle,
)

SALIDA, METRICAS = sys.argv[1], sys.argv[2]
#: Resultado de `python -m pytest tests -q`, p. ej. "1786 pruebas pasan y 1 se omite".
SUITE = sys.argv[3] if len(sys.argv) > 3 else "todas las pruebas pasan"
M = json.load(open(METRICAS))

NEGRO = colors.black
AZUL = NEGRO                       # trazos y titulos: negro
AZUL_CLARO = colors.white          # cajas: blanco con borde negro
VERDE_CLARO = colors.HexColor("#e6e6e6")   # tonos de gris para distinguir capas
NARANJA_CLARO = colors.HexColor("#f4f4f4")
GRIS = colors.HexColor("#444444")
GRIS_CLARO = colors.HexColor("#f4f4f4")
SERIE = NEGRO

ss = getSampleStyleSheet()
CUERPO = ParagraphStyle("c", parent=ss["Normal"], fontName="Times-Roman", fontSize=10.6,
                        leading=13.6, alignment=TA_JUSTIFY, spaceAfter=5)
H1 = ParagraphStyle("h1", parent=CUERPO, fontName="Times-Bold", fontSize=15, leading=18,
                    textColor=NEGRO, spaceBefore=12, spaceAfter=6, alignment=0)
H2 = ParagraphStyle("h2", parent=H1, fontSize=12, leading=15, spaceBefore=8, spaceAfter=3)
PEQ = ParagraphStyle("p", parent=CUERPO, fontSize=9.2, leading=11.4, alignment=0, spaceAfter=0)
PIE = ParagraphStyle("pie", parent=CUERPO, fontName="Times-Italic", fontSize=9.5, leading=11.5,
                     alignment=TA_CENTER, textColor=NEGRO, spaceBefore=2, spaceAfter=8)
CODIGO = ParagraphStyle("cod", fontName="Courier", fontSize=8.2, leading=9.8,
                        leftIndent=10, spaceBefore=3, spaceAfter=8)
VINETA = ParagraphStyle("v", parent=CUERPO, leftIndent=14, bulletIndent=4, spaceAfter=2)

historia = []


def p(texto, estilo=CUERPO):
    historia.append(Paragraph(texto, estilo))


PAGINAS = {}      # titulo de seccion -> pagina (se llena en la primera pasada)


def h1(t, clave=None):
    historia.append(CondPageBreak(4 * cm))
    par = Paragraph(t, H1)
    par._clave = clave or t
    historia.append(par)


def h2(t):
    historia.append(CondPageBreak(3 * cm))
    p(t, H2)


def vinetas(items, numeradas=False):
    for i, t in enumerate(items, 1):
        historia.append(Paragraph(t, VINETA, bulletText=f"{i}." if numeradas else "•"))
    historia.append(Spacer(1, 4))


def codigo(t):
    historia.append(Preformatted(t.strip("\n"), CODIGO))


def tabla(filas, anchos, cabecera=True, fuente=9.2):
    est = ParagraphStyle("t", parent=PEQ, fontSize=fuente, leading=fuente + 2.2)
    estb = ParagraphStyle("tb", parent=est, fontName="Times-Bold", textColor=NEGRO)
    datos = [[Paragraph(str(c), estb if (cabecera and i == 0) else est) for c in fila]
             for i, fila in enumerate(filas)]
    t = Table(datos, colWidths=[a * cm for a in anchos], repeatRows=1 if cabecera else 0)
    estilo = [("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("LINEABOVE", (0, 0), (-1, 0), 1.0, NEGRO),
              ("LINEBELOW", (0, -1), (-1, -1), 1.0, NEGRO),
              ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
              ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5)]
    if cabecera:
        estilo.append(("LINEBELOW", (0, 0), (-1, 0), 0.6, NEGRO))
    t.setStyle(TableStyle(estilo))
    historia.append(t)
    historia.append(Spacer(1, 7))


def figura(dibujo, pie):
    historia.append(KeepTogether([dibujo, Paragraph(pie, PIE)]))


# ---------------------------------------------------------------------------
# utilidades de dibujo
# ---------------------------------------------------------------------------

def caja(d, x, y, w, h, texto, relleno=AZUL_CLARO, tam=7.4, negrita_primera=True):
    d.add(Rect(x, y, w, h, fillColor=relleno, strokeColor=AZUL, strokeWidth=0.7, rx=4, ry=4))
    lineas = texto.split("\n")
    total = len(lineas) * (tam + 2)
    yy = y + h / 2 + total / 2 - tam
    for i, l in enumerate(lineas):
        d.add(String(x + w / 2, yy, l, fontName="Times-Bold" if (i == 0 and negrita_primera)
                     else "Times-Roman", fontSize=tam, textAnchor="middle", fillColor=colors.black))
        yy -= tam + 2


def flecha(d, x1, y1, x2, y2, color=GRIS, discontinua=False):
    ln = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=0.9)
    if discontinua:
        ln.strokeDashArray = [3, 2]
    d.add(ln)
    ang = math.atan2(y2 - y1, x2 - x1)
    a = 5
    d.add(Polygon([x2, y2, x2 - a * math.cos(ang - 0.4), y2 - a * math.sin(ang - 0.4),
                   x2 - a * math.cos(ang + 0.4), y2 - a * math.sin(ang + 0.4)],
                  fillColor=color, strokeColor=color))


def texto(d, x, y, t, tam=7, ancla="start", color=colors.black, negrita=False):
    d.add(String(x, y, t, fontName="Times-Bold" if negrita else "Times-Roman", fontSize=tam,
                 textAnchor=ancla, fillColor=color))


ANCHO = 17.2 * cm


def diagrama_bloques():
    d = Drawing(ANCHO, 250)
    # programa del usuario
    caja(d, 5, 200, 120, 42, "Programa del usuario\n.asm\n#include \"estructuras.inc\"",
         NARANJA_CLARO)
    # libreria
    d.add(Rect(150, 120, 170, 125, fillColor=colors.white, strokeColor=AZUL, strokeDashArray=[3, 2]))
    texto(d, 235, 236, "Librería spl/include/ (ensamblador)", 7.2, "middle", AZUL, True)
    caja(d, 158, 204, 154, 24, "estructuras.inc  (archivo maestro)", AZUL_CLARO, 7)
    caja(d, 158, 176, 74, 22, "layout_datos.inc\nmapa + macros", AZUL_CLARO, 6.4)
    caja(d, 238, 176, 74, 22, "vec.asm\nVEC_* (1D)", AZUL_CLARO, 6.4)
    caja(d, 158, 128, 74, 40, "cabeceras.asm\nVEC_INIT MAT_INIT\nDESC_*", AZUL_CLARO, 6.4)
    caja(d, 238, 128, 74, 40, "mat.asm\nMAT_* (2D)\nENTER / LEAVE", AZUL_CLARO, 6.4)
    # pipeline
    caja(d, 345, 205, 95, 34, "Preprocesador SPL\n(ply.lex) #include,\n#define, #ifdef", VERDE_CLARO, 6.6)
    caja(d, 345, 155, 95, 34, "Ensamblador\nEnigma-64\ncódigo máquina", VERDE_CLARO, 6.6)
    caja(d, 345, 105, 95, 34, "BinarioEnigma\n.e64 (Integrante 4)", VERDE_CLARO, 6.6)
    caja(d, 345, 55, 95, 34, "CargadorEnigma\nPC = 0x00200000", VERDE_CLARO, 6.6)
    caja(d, 345, 5, 95, 34, "CPU multiciclo\nRAM + MMIO", VERDE_CLARO, 6.6)
    flecha(d, 125, 221, 158, 216)
    flecha(d, 312, 216, 345, 222)
    for y in (205, 155, 105, 55):
        flecha(d, 392, y, 392, y - 16)
    # spl.estructuras
    caja(d, 150, 55, 170, 50, "spl.estructuras (Python)\ndescriptores · memoria · cargador\nalgoritmos (ejecutores)",
         colors.HexColor("#ececec"), 6.8)
    flecha(d, 320, 80, 345, 72, discontinua=True)
    caja(d, 5, 55, 120, 50, "GUI Noctua\npestaña Estructuras\nAdaptadorEstructuras", NARANJA_CLARO, 6.8)
    flecha(d, 125, 80, 150, 80, discontinua=True)
    caja(d, 5, 5, 120, 34, "Pruebas pytest\n273 casos de la Tarea 29", colors.white, 6.8)
    flecha(d, 125, 22, 345, 22, discontinua=True)
    caja(d, 450, 105, 40, 85, "", colors.white)
    texto(d, 470, 175, "Datos", 6.6, "middle", negrita=True)
    texto(d, 470, 160, "0x0021…", 5.8, "middle")
    texto(d, 470, 150, "0x0022…", 5.8, "middle")
    texto(d, 470, 140, "0x0026…", 5.8, "middle")
    texto(d, 470, 130, "0x002E…", 5.8, "middle")
    flecha(d, 440, 22, 470, 105, discontinua=True)
    return d


def diagrama_mapa():
    d = Drawing(ANCHO, 175)
    zonas = [
        ("0x00200000", "Código del programa + librería", "≤ 64 KiB", colors.HexColor("#f4f4f4")),
        ("0x00210000", "Zona 1: descriptores (32 B por ranura)", "64 KiB", NARANJA_CLARO),
        ("0x00220000", "Zona 2: vectores  V1 · V2 = +DESP_VECTOR_2", "256 KiB", AZUL_CLARO),
        ("0x00260000", "Zona 3: matrices row-major  M1 · M2 · M3", "512 KiB", VERDE_CLARO),
        ("0x002E0000", "Zona 4: buffers (AUX del merge, resultados)", "128 KiB", colors.HexColor("#ececec")),
        ("0x00400000", "Pila (SP alineado, crece hacia abajo)", "", colors.white),
    ]
    y = 150
    for dir_, nombre, tam, color in zonas:
        d.add(Rect(95, y, 230, 22, fillColor=color, strokeColor=AZUL, strokeWidth=0.6))
        texto(d, 90, y + 8, dir_, 7, "end", negrita=True)
        texto(d, 102, y + 8, nombre, 7)
        texto(d, 332, y + 8, tam, 6.6, color=GRIS)
        y -= 26
    # detalle de un vector
    x0, y0 = 392, 120
    texto(d, x0, 160, "Vector V de N elementos", 7.2, negrita=True)
    celdas = [("base-16", "1"), ("base-8", "N"), ("base+0", "V[0]"), ("base+8", "V[1]"), ("…", "…"),
              ("base+8(N-1)", "V[N-1]")]
    yy = 148
    for i, (et, val) in enumerate(celdas):
        color = NARANJA_CLARO if i < 2 else AZUL_CLARO
        d.add(Rect(x0 + 52, yy - 4, 50, 13, fillColor=color, strokeColor=AZUL, strokeWidth=0.5))
        texto(d, x0 + 48, yy, et, 6.2, "end", GRIS)
        texto(d, x0 + 77, yy, val, 6.6, "middle")
        yy -= 13
    texto(d, x0, 60, "Matriz F x C:  [base-16] = F, [base-8] = C", 6.6)
    texto(d, x0, 50, "Dir(M[i][j]) = base + ((i·C + j) << 3)", 6.6, negrita=True)
    texto(d, x0, 40, "Dir(V[i])    = base + (i << 3)", 6.6, negrita=True)
    texto(d, x0, 26, "Descriptor k en 0x00210000 + 32k:", 6.6)
    texto(d, x0, 16, "[tipo, base, filas, columnas]", 6.6)
    return d


def diagrama_clases():
    d = Drawing(ANCHO, 210)

    def clase(x, y, w, titulo, lineas, relleno=AZUL_CLARO):
        h = 14 + 9.2 * len(lineas)
        d.add(Rect(x, y, w, h, fillColor=colors.white, strokeColor=AZUL, strokeWidth=0.7))
        d.add(Rect(x, y + h - 14, w, 14, fillColor=relleno, strokeColor=AZUL, strokeWidth=0.7))
        texto(d, x + w / 2, y + h - 10, titulo, 7, "middle", negrita=True)
        yy = y + h - 23
        for l in lineas:
            texto(d, x + 4, yy, l, 6.2)
            yy -= 9.2
        return h

    clase(5, 120, 150, "DescriptorVector / DescriptorMatriz",
          ["nombre, elementos, direccion_base", "slot_cabecera, filas, columnas",
           "+ segmentos_memoria()", "+ desde_filas(filas_2d)  (matriz)", "normalizar_palabra_64()"])
    clase(5, 40, 150, "MapaEstructurasRAM",
          ["estructuras: list[Descriptor]", "+ validar_solapamientos()",
           "+ precargar(ram)", "ErrorEstructuraDatos"])
    clase(178, 130, 150, "cargador.py",
          ["compilar_a_binario_e64(fuente)", "  -> ResultadoCompilacionEstructuras",
           "cargar_y_ejecutar_estructuras()", "  -> ResultadoEjecucionEstructuras",
           "exportar_estructuras_e64()"])
    clase(178, 40, 150, "algoritmos.py",
          ["ejecutar_merge_sort(v)", "ejecutar_producto_punto(a, b)",
           "ejecutar_busqueda_binaria(v, q)", "ejecutar_multiplicacion_matrices()",
           "ejecutar_matriz_por_vector()", "DESP_VECTOR_2 / DESP_MATRIZ_2|3"])
    clase(352, 112, 150, "AdaptadorEstructuras (GUI)",
          ["entradas, observadas, programa_activo", "+ programas()  + definir_vector()",
           "+ definir_matriz() + observar_programa()", "+ compilar() + cargar()",
           "+ avanzar(n) + ejecutar_hasta_fin()", "+ instantaneas() + detectar()",
           "+ salida_mmio()"], NARANJA_CLARO)
    clase(352, 30, 150, "PanelEstructuras (Tkinter)",
          ["VisorVector: celdas V[0..N-1]", "VisorMatriz: cuadrícula F x C",
           "publica estructuras.* en el bus", "no importa hardware (aislamiento)"],
          NARANJA_CLARO)
    flecha(d, 80, 120, 80, 92)
    flecha(d, 178, 160, 155, 160)
    flecha(d, 253, 110, 253, 130)
    flecha(d, 352, 160, 328, 160, discontinua=True)
    flecha(d, 427, 82, 427, 112, discontinua=True)
    flecha(d, 178, 70, 155, 70)
    return d


def diagrama_flujo_merge():
    d = Drawing(ANCHO, 200)
    pasos = [
        ("PRINCIPAL: SP = 0x00400000; ¿cabecera [V-16] ≠ 0? (datos precargados)", AZUL_CLARO),
        ("No: crea V demo de 8 con VEC_INIT + VEC_SET    Sí: usa los datos del usuario", NARANJA_CLARO),
        ("N = VEC_LEN(V);  MERGE_SORT(V, lo = 0, hi = N, aux = BASE_BUFFERS)", AZUL_CLARO),
        ("MERGE_SORT: si hi - lo ≤ 1 → RET;  mid = (lo + hi) >> 1 (ASR)", AZUL_CLARO),
        ("CALL MERGE_SORT(lo, mid);  CALL MERGE_SORT(mid, hi)   (recursión en la pila)", AZUL_CLARO),
        ("MERGE: mezcla con VEC_GET/VEC_SET en AUX y VEC_COPY de vuelta a V", VERDE_CLARO),
        ("EMITIR_VECTOR_MMIO: dígitos ASCII → pantalla 0xFF001010;  HLT", colors.HexColor("#ececec")),
    ]
    y = 175
    for i, (t, c) in enumerate(pasos):
        caja(d, 40, y, 410, 21, t, c, 7, negrita_primera=False)
        if i:
            flecha(d, 245, y + 47 - 26 + 5, 245, y + 21)
        y -= 28
    return d


def grafica_merge():
    datos = M["merge"]
    d = Drawing(ANCHO, 175)
    x0, y0, w, h = 45, 30, 280, 125
    xs = [r["n"] for r in datos]
    ys = [r["ins"] for r in datos]
    xmax, ymax = 256, 140000
    sx = lambda n: x0 + w * n / xmax
    sy = lambda v: y0 + h * v / ymax
    for v in range(0, ymax + 1, 35000):
        d.add(Line(x0, sy(v), x0 + w, sy(v), strokeColor=colors.HexColor("#d0d0d0"), strokeWidth=0.5))
        texto(d, x0 - 4, sy(v) - 2.5, f"{v // 1000}k" if v else "0", 6.4, "end", GRIS)
    for n in (0, 64, 128, 192, 256):
        texto(d, sx(n), y0 - 11, str(n), 6.4, "middle", GRIS)
    d.add(Line(x0, y0, x0 + w, y0, strokeColor=GRIS, strokeWidth=0.7))
    # referencia c·N log2 N con c ajustado al mayor N
    c = datos[-1]["ins"] / (256 * 8)
    ref = [(n, c * n * math.log2(n)) for n in range(2, 257, 2)]
    pl = PolyLine([v for n, y in ref for v in (sx(n), sy(y))], strokeColor=GRIS, strokeWidth=1)
    pl.strokeDashArray = [3, 2]
    d.add(pl)
    d.add(PolyLine([v for n, y in zip(xs, ys) for v in (sx(n), sy(y))], strokeColor=SERIE,
                   strokeWidth=2))
    for n, y in zip(xs, ys):
        d.add(Circle(sx(n), sy(y), 3.2, fillColor=SERIE, strokeColor=colors.white, strokeWidth=1.5))
    texto(d, sx(256) - 4, sy(ys[-1]) + 8, f"{ys[-1]:,}".replace(",", "."), 6.6, "end")
    texto(d, x0 + w / 2, 4, "N (elementos)", 7, "middle", GRIS)
    texto(d, x0, y0 + h + 10, "Instrucciones ejecutadas", 7, "start", GRIS)
    # leyenda
    lx = 345
    d.add(Line(lx, 130, lx + 18, 130, strokeColor=SERIE, strokeWidth=2))
    texto(d, lx + 24, 127.5, "merge_sort.asm medido en la CPU", 7)
    ln = Line(lx, 114, lx + 18, 114, strokeColor=GRIS, strokeWidth=1)
    ln.strokeDashArray = [3, 2]
    d.add(ln)
    texto(d, lx + 24, 111.5, f"referencia {c:.1f} · N log2 N", 7)
    texto(d, lx, 85, "Instrucciones / (N log2 N):", 7, negrita=True)
    yy = 73
    for r in datos:
        texto(d, lx, yy, f"N = {r['n']:>3}:  {r['ins'] / (r['n'] * math.log2(r['n'])):.1f}", 6.8)
        yy -= 10
    return d


# ---------------------------------------------------------------------------
# encabezado y pie
# ---------------------------------------------------------------------------

class Doc(SimpleDocTemplate):
    def afterFlowable(self, f):
        clave = getattr(f, "_clave", None)
        if clave:
            PAGINAS[clave] = self.page


def marco(canv, doc):
    canv.saveState()
    if doc.page > 1:
        canv.setFont("Times-Roman", 9)
        canv.setFillColor(NEGRO)
        canv.drawString(2.2 * cm, letter[1] - 1.3 * cm,
                        "Universidad Nacional de Colombia · Lenguajes de Programación · "
                        "Tarea # 29: Librería de estructuras de datos para Enigma-64")
        canv.setStrokeColor(NEGRO)
        canv.setLineWidth(0.5)
        canv.line(2.2 * cm, letter[1] - 1.45 * cm, letter[0] - 2.2 * cm, letter[1] - 1.45 * cm)
    canv.setStrokeColor(NEGRO)
    canv.setLineWidth(0.5)
    canv.line(2.2 * cm, 1.55 * cm, letter[0] - 2.2 * cm, 1.55 * cm)
    canv.setFont("Times-Roman", 9.5)
    canv.setFillColor(NEGRO)
    canv.drawRightString(letter[0] - 2.2 * cm, 1.2 * cm, f"Página {doc.page} de {TOTAL}")
    canv.restoreState()


# ---------------------------------------------------------------------------
# contenido
# ---------------------------------------------------------------------------

def portada():
    t = ParagraphStyle("port", parent=CUERPO, alignment=TA_CENTER, fontSize=12, leading=17)
    tg = ParagraphStyle("portg", parent=t, fontName="Times-Bold", fontSize=16, leading=22,
                        textColor=NEGRO)
    historia.append(Spacer(1, 0.6 * cm))
    for l in ("UNIVERSIDAD NACIONAL DE COLOMBIA", "FACULTAD DE INGENIERÍA",
              "DEPARTAMENTO DE INGENIERÍA DE SISTEMAS E INDUSTRIAL", "LENGUAJES DE PROGRAMACIÓN"):
        p(f"<b>{l}</b>", t)
    historia.append(Spacer(1, 0.4 * cm))
    historia.append(Table([[""]], colWidths=[ANCHO], style=[("LINEABOVE", (0, 0), (-1, 0), 0.8, NEGRO)]))
    historia.append(Spacer(1, 2.4 * cm))
    p("TAREA # 29 — LIBRERÍA BÁSICA DE ESTRUCTURAS DE DATOS (LISTAS Y MATRICES) "
      "PARA LA MÁQUINA DE LA TAREA # 10 (ENIGMA-64)", tg)
    historia.append(Spacer(1, 1.6 * cm))
    p("<b>AUTORES:</b>", t)
    for n in ("Juan Sebastian Umaña Camacho", "Tomas Felipe Garzón Gómez",
              "Michael Stiven Betancourt Gelves", "Juan Luis Vergara Novoa",
              "Maicol Sebastian Olarte Ramirez", "Deibyd Santiago Barragán Gaitán",
              "Alejandro Argüello Muñoz"):
        p(n, t)
    historia.append(Spacer(1, 1.4 * cm))
    p("Docente: Jorge Eduardo Ortiz Triviño", t)
    p("Bogotá D.C., Colombia — Noviembre de 2026", t)
    historia.append(Spacer(1, 0.8 * cm))
    historia.append(Table([[""]], colWidths=[ANCHO], style=[("LINEABOVE", (0, 0), (-1, 0), 0.8, NEGRO)]))
    historia.append(PageBreak())


def contenido():
    p("CONTENIDO", H1)
    secciones = [
        ("—", "Enunciado y equipo de trabajo", "ENUNCIADO"),
        ("1", "Marco teórico", "1. MARCO TEÓRICO"),
        ("2", "Descripción y justificación del problema", "2. DESCRIPCIÓN Y JUSTIFICACIÓN DEL PROBLEMA"),
        ("3", "Diseño de la solución (bloques, mapa de memoria, clases y flujo)", "3. DISEÑO DE LA SOLUCIÓN"),
        ("4", "La librería: módulos, API y convención de llamada",
         "4. LA LIBRERÍA: MÓDULOS, API Y CONVENCIÓN DE LLAMADA"),
        ("5", "Los tres problemas computacionales", "5. LOS TRES PROBLEMAS COMPUTACIONALES"),
        ("6", "Manual técnico", "6. MANUAL TÉCNICO"),
        ("7", "Manual de usuario (línea de comandos y GUI Noctua)", "7. MANUAL DE USUARIO"),
        ("8", "Experimentación y análisis de resultados", "8. EXPERIMENTACIÓN Y ANÁLISIS DE RESULTADOS"),
        ("9", "Limitaciones conocidas", "9. LIMITACIONES CONOCIDAS"),
        ("10", "Conclusiones", "10. CONCLUSIONES"),
        ("—", "Referencias", "REFERENCIAS"),
        ("A", "Anexo: inventario del código fuente", "A. ANEXO: INVENTARIO DEL CÓDIGO FUENTE"),
    ]
    tabla([["Sección", "Título", ""]] + [[n, t, str(PAGINAS.get(c, ""))] for n, t, c in secciones],
          [2, 14, 1.2])
    p("<b>Correspondencia con los entregables de una tarea automatizada.</b> La tarea se entrega "
      "en un único archivo; la tabla indica dónde está cada entregable mínimo exigido:")
    tabla([["Entregable exigido", "Ubicación en este documento"],
           ["a. Marco teórico", "Sección 1"],
           ["b. Descripción y justificación del problema", "Sección 2"],
           ["c. Diseño de la aplicación (diagramas de bloques, de flujo y UML)",
            "Secciones 3 y 5 (Diagramas 1 a 5)"],
           ["d. Código fuente completo y versiones de las librerías",
            "Sección 6.2 (versiones) y Anexo A; el código acompaña la entrega en spl/include/, "
            "spl/estructuras/, spl/ejemplos/ y enigma64/ui/"],
           ["e. Manual de usuario y manual técnico", "Secciones 6 y 7"],
           ["f. Experimentación y análisis de al menos 3 escenarios",
            "Sección 8 (merge sort, producto punto / búsqueda binaria, matrices)"],
           ["Información de todos los autores", "Portada y tabla de roles del equipo"]], [8, 9.2])

    h1("ENUNCIADO")
    p("1. Análisis, diseño e implementación de una pequeña librería de gestión de estructuras de "
      "datos básicas: listas (vectores) y matrices. La librería debe ser importada o incluida por el "
      "programador en sus aplicaciones para que sea añadida y gestionada por el preprocesador del "
      "sistema de procesamiento del lenguaje.")
    p("2. Pruebe su funcionamiento con el algoritmo de las mezclas utilizado para ordenar datos "
      "almacenados en una lista. Seleccione otros dos problemas computacionales que empleen vectores "
      "y matrices.")
    p("Datos de la tarea: inicio el 30 de octubre de 2026, entrega el 13 de noviembre de 2026; "
      "categoría automatizada, obligatoria, clase 15; grupo de Taller-Proyecto de 7 estudiantes.")
    h2("Equipo de trabajo y roles")
    p("El grupo es el mismo de las Tareas # 09, # 10, # 27 y del Taller # 01. Cada integrante conservó "
      "el subsistema de Enigma-64 del que era responsable y construyó la parte de la librería que lo toca:")
    tabla([["Int.", "Nombre", "Módulo", "Responsabilidad en la Tarea 29"],
           ["1", "Juan Sebastian Umaña Camacho", "layout_datos.inc, preprocesador",
            "#include \"estructuras.inc\", macros parametrizadas VEC_DIR / MAT_DIR y mapa de memoria "
            "de datos alineado a 8 bytes."],
           ["2", "Tomas Felipe Garzón Gómez", "vec.asm",
            "Primitivas 1D: VEC_ADDR, VEC_GET, VEC_SET, VEC_SWAP, VEC_COPY, VEC_LEN; convención "
            "R1–R4 / R5."],
           ["3", "Michael Stiven Betancourt Gelves", "mat.asm",
            "Primitivas 2D: MAT_ADDR, MAT_GET, MAT_SET, MAT_CLEAR y marcos de pila "
            "(PUSH/POP, ENTER/LEAVE, CALL/RET)."],
           ["4", "Juan Luis Vergara Novoa", "estructuras.inc, cabeceras.asm, spl.estructuras",
            "Archivo maestro, descriptores y cabeceras, normalización a 64 bits y puente "
            "Preprocesador → Ensamblador → .e64 → CargadorEnigma."],
           ["5", "Maicol Sebastian Olarte Ramirez", "enigma64/ui/",
            "Pestaña Estructuras de la GUI Noctua: VisorVector, VisorMatriz y AdaptadorEstructuras; "
            "integración de los tres problemas."],
           ["6", "Deibyd Santiago Barragán Gaitán", "merge_sort.asm",
            "Algoritmo de las mezclas con vector auxiliar y salida por la pantalla MMIO "
            "(0xFF001010)."],
           ["7", "Alejandro Argüello Muñoz", "producto_punto, busqueda_binaria, "
            "multiplicacion_matrices, tests",
            "Problemas 2 y 3 y la suite automatizada tests/test_libreria_estructuras.py."]],
          [0.9, 3.6, 4.2, 8.5], fuente=7.8)


def marco_teorico():
    h1("1. MARCO TEÓRICO")
    h2("1.1 Tipos abstractos de datos lineales: listas y matrices")
    p("Un <i>tipo abstracto de datos</i> (TAD) separa la especificación de un tipo (sus operaciones y "
      "propiedades) de su representación. La lista es la secuencia finita V = (v<sub>0</sub>, …, "
      "v<sub>N-1</sub>) con las operaciones obtener, asignar, intercambiar, copiar y longitud; la matriz "
      "M de F × C es una función de los pares (i, j), 0 ≤ i &lt; F, 0 ≤ j &lt; C, en los valores. "
      "Cuando la representación es <i>contigua</i> y los elementos tienen tamaño fijo w, el acceso es de "
      "tiempo constante porque la dirección se calcula: Dir(v<sub>i</sub>) = B + i·w [1]. En Enigma-64 "
      "cada elemento es una palabra de 64 bits (w = 8), de modo que la multiplicación se reduce a un "
      "desplazamiento: <b>Dir(V[i]) = B + (i &lt;&lt; 3)</b>.")
    p("Una matriz se aplana a un vector con un <i>orden de almacenamiento</i>. En orden por filas "
      "(row-major, el de C y Pascal) la fila i ocupa C palabras consecutivas que empiezan en B + i·C·w, "
      "de donde <b>Dir(M[i][j]) = B + ((i·C + j) &lt;&lt; 3)</b>. El orden por filas tiene una "
      "consecuencia útil: cada fila es en sí misma un vector, así que las primitivas de listas operan "
      "sobre filas sin conversión. La fórmula necesita C, el <i>vector de información</i> o dope vector "
      "de la matriz; por eso la librería guarda una cabecera con las dimensiones junto a los datos.")
    h2("1.2 Preprocesador, inclusión de archivos y macros")
    p("El preprocesador es la primera fase del sistema de procesamiento del lenguaje: transforma el "
      "texto antes del ensamblado. La directiva <font face='Courier'>#include</font> sustituye la línea "
      "por el contenido del archivo, lo que permite distribuir una librería como fuente y que el "
      "programador la «importe» con una sola línea; <font face='Courier'>#define</font> declara macros "
      "objeto y macros parametrizadas (VEC_DIR(base, i)), y <font face='Courier'>#ifdef / #ifndef / "
      "#pragma once</font> evitan la doble inclusión y permiten activar módulos opcionales "
      "(INCLUIR_MATRICES) [2]. El preprocesador del SPL de Enigma-64 se construyó con ply.lex en el "
      "Taller # 01: reconoce las directivas con un analizador léxico de estados y resuelve las "
      "inclusiones recursivas con detección de ciclos y búsqueda primero junto al archivo y luego en "
      "<font face='Courier'>spl/include/</font>.")
    h2("1.3 Subrutinas, convención de llamada y marcos de pila")
    p("Una librería en ensamblador solo es reutilizable si todas sus rutinas respetan el mismo "
      "<i>contrato binario</i> (ABI): dónde van los argumentos, dónde el resultado y qué registros "
      "conserva la rutina llamada (callee-saved) frente a los que puede destruir (caller-saved). Las "
      "rutinas que llaman a otras guardan sus temporales con PUSH y abren un <i>registro de activación</i> "
      "con ENTER t (apila BP, BP = SP, reserva t bytes de variables locales); LEAVE y RET lo deshacen en "
      "orden inverso. La cadena de BP guardados (enlace dinámico) permite recorrer la pila y es lo que "
      "hace posible la recursión del algoritmo de las mezclas [3].")
    h2("1.4 Los algoritmos de prueba")
    p("<b>Ordenamiento por mezclas (merge sort).</b> Algoritmo de divide y vencerás de von Neumann "
      "(1945): divide la lista en dos mitades, las ordena recursivamente y las <i>mezcla</i> en tiempo "
      "lineal con un vector auxiliar. Su costo cumple T(N) = 2T(N/2) + Θ(N), es decir Θ(N log N) en todos "
      "los casos, y es estable [1, 4]. <b>Producto punto.</b> a·b = Σ a<sub>k</sub>b<sub>k</sub>, Θ(N), "
      "recorrido secuencial de dos vectores. <b>Búsqueda binaria.</b> Sobre un vector ordenado compara con "
      "el elemento central y descarta la mitad: Θ(log N) comparaciones. <b>Producto de matrices.</b> "
      "C = A·B con c<sub>ij</sub> = Σ<sub>k</sub> a<sub>ik</sub>b<sub>kj</sub>, Θ(F·K·C) con el "
      "algoritmo de tres bucles; y su caso particular matriz por vector, y = A·x, Θ(F·K). Juntos ejercitan "
      "todas las operaciones de la librería: acceso aleatorio, escritura, copia, recursión, y acceso 2D.")


def descripcion():
    h1("2. DESCRIPCIÓN Y JUSTIFICACIÓN DEL PROBLEMA")
    h2("2.1 Descripción")
    p("Enigma-64 (Tareas # 09 y # 10) es una máquina Von Neumann multiciclo de 64 bits con 8 registros "
      "(R0 = 0, R6 = SP, R7 = BP), inmediatos de 16 bits con signo, memoria big-endian de 4 GiB con "
      "palabras alineadas a 8 bytes (un acceso desalineado produce STATUS_MISALIGNED) y la zona de sistema "
      "por debajo de 0x00200000 protegida. Su ensamblador no tiene tipos ni directivas de datos: un "
      "programador que necesite una lista o una matriz debe calcular direcciones a mano, decidir dónde "
      "guarda la longitud y repetir ese código en cada programa. El problema es ofrecerle una librería "
      "que resuelva eso una sola vez y que se incorpore a cualquier programa con "
      "<font face='Courier'>#include \"estructuras.inc\"</font>, gestionada por el preprocesador del SPL.")
    p("Los requisitos que se derivan del enunciado y de la máquina son: (R1) inclusión por el "
      "preprocesador, sin pasos manuales; (R2) acceso en O(1) a V[i] y M[i][j]; (R3) metadatos "
      "(longitud, filas, columnas) en memoria, legibles en tiempo de ejecución; (R4) alineación a 8 bytes "
      "y respeto del mapa de memoria de la Tarea # 09; (R5) una convención de llamada única que permita "
      "anidar y recursar; (R6) modularidad: cada módulo se puede incluir y probar solo; (R7) "
      "demostración con el merge sort y otros dos problemas sobre vectores y matrices.")
    h2("2.2 Justificación")
    p("Había tres caminos. (i) <b>Solo macros</b>: VEC_DIR y MAT_DIR resuelven la dirección en el texto, "
      "pero el preprocesador de una línea por macro no puede emitir secuencias de instrucciones, y los "
      "índices que viven en registros no se pueden calcular en tiempo de preprocesamiento. (ii) "
      "<b>Extender el ensamblador</b> con instrucciones o directivas de estructuras: rompe la "
      "compatibilidad con la máquina de la Tarea # 10, que no debe cambiar. (iii) <b>Librería de "
      "subrutinas en ensamblador incluida por el preprocesador</b>, el camino elegido: las macros quedan "
      "para constantes y direcciones conocidas al escribir el programa y las subrutinas para todo lo "
      "dinámico. Ventajas: el código es ensamblador de Enigma-64 estándar que corre a velocidad nativa; "
      "cada archivo es un módulo con guardas de inclusión; la convención R1–R4 / R5 hace que las rutinas "
      "se compongan; y el lado Python (spl.estructuras) reutiliza el mismo formato de descriptores para "
      "precargar datos, leer resultados, probar y visualizar en la GUI.")


def diseno():
    h1("3. DISEÑO DE LA SOLUCIÓN")
    h2("3.1 Arquitectura general (diagrama de bloques)")
    p("El Diagrama 1 muestra cómo se organiza la solución en capas independientes: a la izquierda los "
      "clientes (el programa del usuario, la GUI y las pruebas), en el centro la librería en ensamblador "
      "(recuadro punteado) y el paquete Python que conecta ambos mundos, y a la derecha, en gris, el "
      "sistema de procesamiento del lenguaje y la máquina de la Tarea # 10.")
    figura(diagrama_bloques(), "Diagrama 1: Arquitectura de la librería y su integración con el SPL y "
           "con Enigma-64. Flecha continua: inclusión o flujo de datos; discontinua: uso.")
    h2("3.2 Diseño modular")
    p("La modularidad es la decisión central del diseño. Cada archivo de "
      "<font face='Courier'>spl/include/</font> es un módulo con una sola responsabilidad, una guarda "
      "<font face='Courier'>#pragma once</font> + <font face='Courier'>#ifndef</font> y un "
      "<font face='Courier'>JMP</font> inicial que salta su cuerpo, de modo que puede incluirse al inicio "
      "o al final del programa sin ejecutarse por caída. El programador elige el grano: "
      "<font face='Courier'>#include \"vec.asm\"</font> solo trae listas; "
      "<font face='Courier'>#include \"estructuras.inc\"</font> trae listas y cabeceras; y "
      "<font face='Courier'>#define INCLUIR_MATRICES</font> antes de ese include añade "
      "<font face='Courier'>mat.asm</font>. Las dependencias forman un árbol sin ciclos: "
      "mat.asm → cabeceras.asm; estructuras.inc → layout_datos.inc, vec.asm, cabeceras.asm [, mat.asm].")
    tabla([["Módulo", "Responsabilidad", "Depende de"],
           ["layout_datos.inc", "Mapa de las 4 zonas de datos, DESP_VECTOR_2 / DESP_MATRIZ_2 / "
            "DESP_MATRIZ_3 y macros VEC_DIR, MAT_DIR", "—"],
           ["vec.asm", "Primitivas 1D (hojas, sin pila salvo VEC_SWAP / VEC_COPY)", "—"],
           ["cabeceras.asm", "Cabecera inline y tabla de descriptores (tipo, base, filas, cols)", "—"],
           ["mat.asm", "Primitivas 2D (no hoja, con marcos ENTER/LEAVE)", "cabeceras.asm"],
           ["estructuras.inc", "Punto único de inclusión, constantes del ABI y DESC_DIR(slot)",
            "los anteriores"],
           ["spl/estructuras/*.py", "Descriptores, precarga/lectura en RAM, compilación a .e64, "
            "ejecutores", "preprocesador, ensamblador, cargador"],
           ["enigma64/ui/…/estructuras.py", "Adaptador y pestaña de la GUI", "spl.estructuras"]],
          [4, 9.2, 4])
    p("Los algoritmos de prueba (MERGE_SORT, VEC_DOT, VEC_BIN_SEARCH, MAT_MUL, MAT_VEC_MUL) viven en sus "
      "programas de <font face='Courier'>spl/ejemplos/</font> y no en la librería: son "
      "<i>aplicaciones</i> de la librería, como pide el enunciado, y la librería se mantiene pequeña y "
      "básica. Durante la integración se eliminaron los desplazamientos codificados a mano (256, 512, "
      "1024 bytes) de los programas 2 y 3 y se reemplazaron por las macros DESP_* del mapa de memoria, "
      "que ahora es la única fuente de verdad para Python, ensamblador y GUI (Sección 8.6).")
    h2("3.3 Mapa de memoria y representación")
    figura(diagrama_mapa(), "Diagrama 2: Zonas de datos de layout_datos.inc (izquierda) y representación "
           "de un vector con su cabecera inline (derecha).")
    p("Cada estructura tiene un <b>modelo dual de metadatos</b>: una cabecera <i>inline</i> de dos palabras "
      "justo antes de los datos (lo que leen VEC_LEN, MAT_ROWS y MAT_COLS en O(1)) y, opcionalmente, un "
      "<i>descriptor</i> de 32 bytes en la tabla de la Zona 1 (lo que permite a la GUI y a las pruebas "
      "descubrir qué estructuras construyó un programa). Todas las bases son múltiplos de 8; la Zona 1 "
      "empieza en 0x00210000 para no pisar los programas demo de la Tarea # 10 (0x00201000–0x00205020).")
    h2("3.4 Diagrama de clases del lado Python (UML)")
    figura(diagrama_clases(), "Diagrama 3: Clases y módulos de spl.estructuras (izquierda y centro) y de "
           "la GUI (derecha). Flecha continua: uso directo; discontinua: el adaptador usa el puente.")
    p("<font face='Courier'>MapaEstructurasRAM</font> valida antes de escribir que ningún segmento "
      "(cabecera inline, datos, descriptor) se solape con otro ni salga de su zona, y lanza "
      "<font face='Courier'>ErrorEstructuraDatos</font> con las direcciones exactas del conflicto. "
      "<font face='Courier'>cargar_y_ejecutar_estructuras</font> encadena preprocesador, ensamblador, "
      "empaquetado .e64, CargadorEnigma, precarga de las estructuras y ejecución en la CPU.")


def libreria():
    h1("4. LA LIBRERÍA: MÓDULOS, API Y CONVENCIÓN DE LLAMADA")
    h2("4.1 Convención de llamada (ABI)")
    tabla([["Elemento", "Regla"],
           ["Argumentos", "R1, R2, R3, R4 en ese orden (del 5.º en adelante, por pila)"],
           ["Retorno", "R5 (alias RV)"],
           ["Preservados (callee-saved)", "R1–R4, R6 = SP, R7 = BP"],
           ["Destruidos (caller-saved)", "R5 y banderas Z, N, C, V"],
           ["Pila", "Crece hacia direcciones menores; SP alineado a 8 (0x00400000) antes de la primera "
            "llamada; cada rutina deja SP como lo encontró"],
           ["Límites", "Las primitivas no validan índices (como en C): 0 ≤ i &lt; N es responsabilidad "
            "del llamador; los datos son 64 bits crudos, válidos para enteros y double IEEE-754"]],
          [4.5, 12.7])
    h2("4.2 Interfaz de programación")
    tabla([["Rutina", "Entradas", "Salida / efecto", "Módulo"],
           ["VEC_ADDR", "R1 = base, R2 = i", "R5 = base + (i &lt;&lt; 3)", "vec.asm"],
           ["VEC_GET / VEC_SET", "R1, R2 = i (, R3 = valor)", "R5 = V[i] / V[i] = R3", "vec.asm"],
           ["VEC_SWAP", "R1, R2 = i, R3 = j", "intercambia V[i] y V[j] (correcto con i = j)", "vec.asm"],
           ["VEC_COPY", "R1 = dest, R2 = orig, R3 = n", "copia n palabras, semántica memmove", "vec.asm"],
           ["VEC_LEN", "R1 = base", "R5 = N (de [base − 8])", "vec.asm"],
           ["VEC_INIT / MAT_INIT", "R1 = base, R2 = N | F (, R3 = C)", "escribe la cabecera inline",
            "cabeceras.asm"],
           ["MAT_ROWS / MAT_COLS", "R1 = base", "R5 = F / C", "cabeceras.asm"],
           ["DESC_VEC_INIT / DESC_MAT_INIT", "R1 = ranura, R2 = base, R3 (, R4)",
            "descriptor en 0x00210000 + 32·ranura y cabecera inline", "cabeceras.asm"],
           ["DESC_ADDR, DESC_GET_*", "R1 = ranura", "R5 = dirección / tipo / base / filas / cols",
            "cabeceras.asm"],
           ["MAT_ADDR", "R1 = base, R2 = i, R3 = j", "R5 = base + ((i·C + j) &lt;&lt; 3)", "mat.asm"],
           ["MAT_GET / MAT_SET", "R1, R2 = i, R3 = j (, R4 = valor)", "R5 = M[i][j] / M[i][j] = R4",
            "mat.asm"],
           ["MAT_CLEAR", "R1 = base", "pone a 0 las F·C palabras; R5 = F·C", "mat.asm"]],
          [4.1, 4.4, 6.3, 2.4], fuente=7.8)
    h2("4.3 Ejemplo de uso mínimo")
    p("El siguiente programa completo crea V = [7, 3] y los intercambia; todo lo que no es "
      "<font face='Courier'>PRINCIPAL</font> lo aporta la librería:")
    codigo("""
#include "estructuras.inc"          ; el preprocesador trae layout, vec y cabeceras
PRINCIPAL:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000 (alineado)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16             ; R1 = BASE_VECTORES
        ADDI R2, R0, 2
        CALL VEC_INIT               ; cabecera: N = 2
        ADDI R2, R0, 0
        ADDI R3, R0, 7
        CALL VEC_SET                ; V[0] = 7
        ADDI R2, R0, 1
        ADDI R3, R0, 3
        CALL VEC_SET                ; V[1] = 3
        ADDI R2, R0, 0
        ADDI R3, R0, 1
        CALL VEC_SWAP               ; V = [3, 7]
        HLT
""")
    p("MAT_GET muestra la gestión de pila de una rutina no hoja: abre un marco con "
      "<font face='Courier'>ENTER 0</font>, llama a MAT_ADDR (segundo nivel), lee y deshace el marco. "
      "Durante esa llamada la pila contiene, de arriba abajo, el retorno a MAT_GET, el BP del llamador y "
      "el retorno al llamador; las pruebas del Integrante 3 inspeccionan esos marcos en la CPU real y "
      "ejecutan 300 niveles de recursión.")
    codigo("""
MAT_ADDR:   LOAD R5, [R1 - 8]       ; C de la cabecera
            MUL  R5, R2, R5         ; i * C
            ADD  R5, R5, R3         ; i * C + j
            SHL  R5, R5, 3          ; * 8 bytes
            ADD  R5, R1, R5         ; base + ...
            RET
MAT_GET:    ENTER 0                 ; marco: apila BP, BP = SP
            CALL MAT_ADDR           ; nivel 2
            LOAD R5, [R5]
            LEAVE
            RET
""")


def problemas():
    h1("5. LOS TRES PROBLEMAS COMPUTACIONALES")
    p("Los cuatro programas siguen el mismo patrón: incluyen la librería, ponen SP en 0x00400000, "
      "comprueban si la cabecera de su primera estructura ya tiene datos (precargados desde Python o desde "
      "la GUI) y, si no, construyen unos datos de demostración; al terminar dejan los resultados en RAM, "
      "en R5 y, en el merge sort, en la pantalla MMIO. Así cada programa es autónomo y a la vez "
      "parametrizable.")
    h2("5.1 Problema 1: algoritmo de las mezclas (merge_sort.asm, Integrante 6)")
    figura(diagrama_flujo_merge(), "Diagrama 4: Flujo de merge_sort.asm. Cada caja usa rutinas de la "
           "librería: VEC_INIT, VEC_SET, VEC_LEN, VEC_GET, VEC_COPY.")
    p("MERGE_SORT(V, lo, hi, aux) ordena el intervalo semiabierto [lo, hi). El punto medio se calcula con "
      "ASR para no desbordar; R1 (base), R2 (lo), R4 (aux) se preservan por la ABI, de modo que las dos "
      "llamadas recursivas no necesitan restaurarlos. MERGE copia [lo, hi) a AUX con VEC_COPY y mezcla de "
      "vuelta sobre V eligiendo el menor con VEC_GET (≤ para que el orden sea estable). "
      "EMITIR_VECTOR_MMIO convierte cada entero con signo a dígitos ASCII y los escribe en el registro DATA "
      "de la pantalla (0xFF001010).")
    h2("5.2 Problema 2: vectores — producto punto y búsqueda binaria (Integrante 7)")
    p("<b>producto_punto.asm</b> lee A y B (A en BASE_VECTORES, B en BASE_VECTORES + DESP_VECTOR_2), "
      "acumula A[k]·B[k] con VEC_GET y MUL en VEC_DOT y deja el resultado en el vector DOT de longitud 1 "
      "en BASE_BUFFERS y en R5. <b>busqueda_binaria.asm</b> recibe un vector ordenado V y un vector de "
      "consultas Q; para cada Q[k] VEC_BIN_SEARCH reduce [lo, hi] con mid = (lo + hi) &gt;&gt; 1 y deja el "
      "índice (o −1) en R[k] (BASE_BUFFERS). Los dos problemas cubren el recorrido secuencial Θ(N) y el "
      "acceso aleatorio Θ(log N) sobre listas.")
    h2("5.3 Problema 3: matrices — C = A × B y y = A × x (Integrante 7)")
    p("<b>multiplicacion_matrices.asm</b> se incluye con <font face='Courier'>#define "
      "INCLUIR_MATRICES</font>. MAT_MUL lee las dimensiones con MAT_ROWS / MAT_COLS, crea C (FA × CB) con "
      "DESC_MAT_INIT en BASE_MATRICES + DESP_MATRIZ_3, la limpia con MAT_CLEAR y ejecuta el triple bucle "
      "con MAT_GET y MAT_SET; sus nueve variables locales viven en un marco <font face='Courier'>ENTER "
      "72</font> ([BP − 8] … [BP − 72]). Si hay un vector x en BASE_VECTORES, MAT_VEC_MUL calcula también "
      "y = A·x mezclando primitivas 2D (MAT_GET) y 1D (VEC_GET, VEC_SET), lo que demuestra que ambos "
      "módulos se componen.")
    codigo("""
MM_BODY_K:  LOAD R1, [BP - 8]       ; base_A
            LOAD R2, [BP - 56]      ; i
            ADD  R3, R4, R0         ; k
            CALL MAT_GET            ; R5 = A[i][k]
            PUSH R5
            LOAD R1, [BP - 16]      ; base_B
            ADD  R2, R4, R0         ; k
            LOAD R3, [BP - 64]      ; j
            CALL MAT_GET            ; R5 = B[k][j]
            POP  R3
            MUL  R5, R3, R5         ; acc += A[i][k] * B[k][j]
""")


def manual_tecnico():
    h1("6. MANUAL TÉCNICO")
    h2("6.1 Estructura del paquete")
    tabla([["Archivo", "Contenido"],
           ["spl/include/estructuras.inc", "Archivo maestro: constantes del ABI, DESC_DIR(slot), includes"],
           ["spl/include/layout_datos.inc", "Zonas de datos, DESP_*, macros VEC_DIR y MAT_DIR"],
           ["spl/include/vec.asm · cabeceras.asm · mat.asm", "Primitivas 1D, cabeceras/descriptores, primitivas 2D"],
           ["spl/estructuras/descriptores.py", "DescriptorVector, DescriptorMatriz, MapaEstructurasRAM, "
            "normalización a 64 bits"],
           ["spl/estructuras/memoria.py", "Precarga y lectura de vectores, matrices y descriptores en RAMMemory"],
           ["spl/estructuras/cargador.py", "compilar_a_binario_e64, cargar_y_ejecutar_estructuras, .e64"],
           ["spl/estructuras/algoritmos.py", "Ejecutores de los tres problemas y constantes DESP_*"],
           ["spl/ejemplos/*.asm", "merge_sort, producto_punto, busqueda_binaria, "
            "multiplicacion_matrices y las pruebas prueba_vec, prueba_mat, prueba_cabeceras_cargador"],
           ["enigma64/ui/servicios/estructuras.py", "AdaptadorEstructuras: librería + cargador + RAM + CPU + MMIO"],
           ["enigma64/ui/paneles/panel_estructuras.py · core/visores.py", "Pestaña Tkinter, VisorVector y VisorMatriz"]],
          [6.6, 10.6], fuente=7.8)
    h2("6.2 Requisitos y versiones")
    p("El emulador y la GUI usan solo la biblioteca estándar de Python (incluido tkinter). Las "
      "dependencias externas están en requirements.txt y environment.yml:")
    tabla([["Componente", "Versión probada", "Requerida", "Uso"],
           ["Python", "3.14.4", "≥ 3.10", "Lenguaje de implementación"],
           ["PLY (ply.lex)", "3.11", "≥ 3.11", "Preprocesador y analizadores léxicos del SPL"],
           ["pytest", "9.2.0", "≥ 8.0", "Suite de pruebas"],
           ["Tk / tkinter", "8.6", "8.6", "GUI Noctua (solo para la interfaz)"]], [4.2, 3, 2.6, 7.4])
    codigo("""
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # o: conda env create -f environment.yml
""")
    h2("6.3 API de programación (Python)")
    codigo("""
from spl.estructuras import (ejecutar_merge_sort, ejecutar_producto_punto,
    ejecutar_busqueda_binaria, ejecutar_multiplicacion_matrices, cargar_y_ejecutar_estructuras,
    DescriptorVector, BASE_VECTORES)

ordenado, ej = ejecutar_merge_sort([45, -12, 89, 0])    # corre merge_sort.asm en la CPU
print(ordenado, ej.salida_mmio)                         # [-12, 0, 45, 89] '-12 0 45 89'
dot, _ = ejecutar_producto_punto([1, 2, 3], [4, 5, 6])  # 32
C, y, _ = ejecutar_multiplicacion_matrices([[1, 2], [3, 4]], [[5, 6], [7, 8]], vector_x=[1, 1])

# Programa propio con datos precargados:
v = DescriptorVector(nombre="V", elementos=[5, 1, 4], direccion_base=BASE_VECTORES, slot_cabecera=0)
ej = cargar_y_ejecutar_estructuras("mi_programa.asm", es_archivo=True, estructuras=[v])
""")
    h2("6.4 Cómo extender la librería")
    vinetas([
        "Para una primitiva nueva, añadirla al módulo que le corresponde (1D en vec.asm, 2D en mat.asm), "
        "respetar la ABI de la Sección 4.1 y no escribir nombres de macros en los comentarios (el "
        "preprocesador también expande dentro de los comentarios con ';').",
        "Para un módulo nuevo, crear el archivo en spl/include/ con #pragma once, guarda #ifndef y "
        "JMP inicial, e incluirlo desde estructuras.inc (opcionalmente bajo un #ifdef como INCLUIR_MATRICES).",
        "Para una tercera o cuarta estructura en un programa, usar las bases BASE_* + DESP_* de "
        "layout_datos.inc; la prueba test_layout_capacidad.py comprueba que Python y ensamblador coinciden.",
        "Un programa nuevo en spl/ejemplos/ que haga #include \"estructuras.inc\" aparece solo en el "
        "catálogo de la GUI; para que sus estructuras se dibujen solas basta registrarlas en "
        "OBSERVABLES_CONOCIDOS (o pulsar «Detectar en RAM»).",
    ])
    h2("6.5 Pruebas")
    codigo("""
python -m pytest tests -q                                   # suite completa del proyecto
python -m pytest tests/test_libreria_estructuras.py tests/test_spl/test_vec_lib.py \\
       tests/test_spl/test_mat_lib.py tests/ui/test_ui_estructuras.py -q
""")


def manual_usuario():
    h1("7. MANUAL DE USUARIO")
    h2("7.1 Línea de comandos")
    codigo("""
# Preprocesar + ensamblar + empaquetar un programa que usa la libreria
python -m spl.estructuras spl/ejemplos/merge_sort.asm -o merge_sort.e64
# ... y ejecutarlo en el emulador (muestra registros, estructuras y salida MMIO)
python -m spl.estructuras spl/ejemplos/merge_sort.asm --ejecutar
# Solo el preprocesador, para ver la libreria expandida
python -m spl.preprocesador spl/ejemplos/producto_punto.asm
""")
    h2("7.2 Interfaz gráfica: pestaña Estructuras")
    p("Se abre con <font face='Courier'>python -m enigma64.ui</font> (pestaña <b>Estructuras</b>, que comparte "
      "RAM, registros, CPU y MMIO con las demás pestañas) o, de forma aislada, con "
      "<font face='Courier'>python -m enigma64.ui.paneles.panel_estructuras</font>. La pantalla tiene tres "
      "zonas: a la izquierda los datos de entrada, arriba el programa y sus controles de ejecución, y en el "
      "centro los visores de vectores (celdas indexadas V[0..N−1]) y matrices (cuadrícula F × C).")
    vinetas([
        "<b>Elegir el programa</b> en el selector (merge sort encabeza la lista; luego producto punto, "
        "búsqueda binaria, multiplicación de matrices y las pruebas de la librería) o «Abrir .asm…». "
        "La descripción indica qué estructuras lee el programa, por ejemplo «A (vector en 0x00220000), "
        "B (vector en 0x00221000)».",
        "<b>Escribir los datos</b> (opcional): tipo Vector o Matriz, nombre (A, B, V, Q, x…), base "
        "«auto» y valores (<font face='Courier'>45, -12, 89</font> para vectores; una fila por línea o "
        "separadas por «;» para matrices; se aceptan decimal, 0x…, 0b… y reales). «Escribir en RAM» la "
        "guarda con su cabecera y descriptor. Con base «auto», un nombre que el programa espera cae justo "
        "donde el programa lo lee; si se escribió antes de elegir el programa, se recoloca al elegirlo.",
        "<b>Compilar y cargar</b>: preprocesa (resuelve el #include), ensambla, empaqueta el .e64, lo carga "
        "con CargadorEnigma en 0x00200000, pone SP = 0x00400000 y reescribe los datos de entrada.",
        "<b>Ejecutar</b>: «Paso» avanza una instrucción e ilumina la celda leída (cian) o escrita (ámbar); "
        "«Animar» corre a la velocidad elegida y se puede pausar; «Hasta el final» corre hasta HLT. "
        "La barra muestra PC, la subrutina actual (p. ej. MERGE o MAT_GET), R1–R5, SP y BP.",
        "<b>Leer resultados</b>: cada visor muestra el valor final y, debajo, el valor al cargar (entrada vs. "
        "salida); el formato puede ser decimal, hexadecimal o double. Pulsar una celda muestra su dirección "
        "(Dir = B + ((i·C + j) &lt;&lt; 3)) y salta a ella en la pestaña Memoria. La salida de la pantalla "
        "MMIO aparece al pie.",
        "<b>Detectar en RAM</b> recorre la tabla de descriptores y dibuja cualquier estructura que un "
        "programa propio haya creado con DESC_VEC_INIT / DESC_MAT_INIT.",
    ], numeradas=True)
    p("Los errores (valores no numéricos, filas de distinta longitud, una base que se solapa con otra "
      "estructura, un programa que no ensambla) se muestran en rojo junto al control que los produjo y no "
      "detienen la interfaz.")


def experimentacion():
    h1("8. EXPERIMENTACIÓN Y ANÁLISIS DE RESULTADOS")
    h2("8.1 Metodología")
    p("Cada escenario se ejecuta sin intervención manual con el puente del Integrante 4: (1) el "
      "preprocesador resuelve <font face='Courier'>#include \"estructuras.inc\"</font>; (2) el "
      "ensamblador de la Tarea # 10 genera el código; (3) se empaqueta el .e64 y CargadorEnigma lo carga "
      "en 0x00200000; (4) se precargan los datos con sus descriptores; (5) la CPU multiciclo ejecuta hasta "
      "HLT; (6) se leen las estructuras de la RAM y se comparan con un oráculo en Python. Los datos son "
      "aleatorios con semilla fija (2026). Las cifras se obtuvieron el 11 de noviembre de 2026 con Python "
      "3.14.4 y PLY 3.11; cada instrucción tarda 5 ciclos (FETCH, DECODE, EXECUTE, MEMORY, WRITE-BACK).")
    h2("8.2 Escenario 1: algoritmo de las mezclas")
    dm = M["demo_merge"]
    p(f"<b>Datos de demostración.</b> Entrada V = [45, −12, 89, 0, 23, −5, 77, 10]. Salida en RAM "
      f"{dm['r']} y en la pantalla MMIO «{dm['mmio'].strip()}». Resultado: correcto.")
    filas = [["N", "Instrucciones", "Ciclos", "Instr. / (N log2 N)", "Resultado"]]
    for r in M["merge"]:
        filas.append([r["n"], f"{r['ins']:,}".replace(",", "."), f"{r['cic']:,}".replace(",", "."),
                      f"{r['ins'] / (r['n'] * math.log2(r['n'])):.1f}", "ordenado ✓" if r["ok"] else "✗"])
    tabla(filas, [2, 3.5, 3.5, 4, 4.2])
    figura(grafica_merge(), "Diagrama 5: Instrucciones ejecutadas por merge_sort.asm frente a N, con la "
           "curva c·N log2 N ajustada al punto N = 256.")
    p("El cociente instrucciones / (N log2 N) baja de 86,8 a 64,4 y se estabiliza: el término lineal de "
      "la inicialización y de la salida MMIO pesa cada vez menos y el crecimiento observado es el "
      "Θ(N log N) que predice la teoría. Duplicar N de 128 a 256 multiplica las instrucciones por 2,20 "
      "(el modelo N log N predice 2,29). El costo constante por elemento y nivel (~64 instrucciones) "
      "proviene de que cada acceso pasa por VEC_GET / VEC_SET (CALL + 3 instrucciones + RET): es el precio "
      "explícito de la modularidad, que se cuantifica en 8.5.")
    h2("8.3 Escenario 2: producto punto y búsqueda binaria")
    p(f"<b>Demostración.</b> A = [3, −4, 7, 2, −5], B = [6, 5, 2, −3, −4]: dot(A, B) = "
      f"{M['demo_dot']} (esperado 26). Búsqueda en V = [−20, −5, 0, 7, 15, 23, 42, 88] de Q = [23, −20, "
      f"88, 19]: R = {M['demo_bin']} (esperado [5, 0, 7, −1]).")
    filas = [["N", "Producto punto: instr.", "Instr. / N", "Búsqueda (4 consultas): instr.",
              "Resultado"]]
    for a, b in zip(M["dot"], M["bin"]):
        filas.append([a["n"], f"{a['ins']:,}".replace(",", "."), f"{a['ins'] / a['n']:.1f}",
                      f"{b['ins']:,}".replace(",", "."), "✓" if a["ok"] and b["ok"] else "✗"])
    tabla(filas, [1.6, 4.2, 2.6, 5, 3.8])
    p("El producto punto crece linealmente (~24 instrucciones por elemento a partir de N = 32). La "
      "búsqueda binaria pasa de 572 a 1.032 instrucciones cuando N crece 32 veces: cada duplicación de N "
      "añade una iteración por consulta (~23 instrucciones × 4 consultas ≈ 92, exactamente la diferencia "
      "entre 128 y 256), la firma de Θ(log N).")
    h2("8.4 Escenario 3: multiplicación de matrices y matriz por vector")
    dm = M["demo_mat"]
    p(f"<b>Demostración.</b> A = [[1, 2, 3], [4, −1, 2]], B = [[2, 1], [0, −3], [4, 5]], x = [2, −1, 3]: "
      f"C = {dm['C']} y y = {dm['y']}, ambos iguales al cálculo a mano.")
    filas = [["n (n × n)", "C = A·B: instr.", "Instr. / n³", "y = A·x: instr.", "Resultado"]]
    mv = {r["n"]: r for r in M["matvec"]}
    for r in M["mat"]:
        v = mv.get(r["n"])
        filas.append([r["n"], f"{r['ins']:,}".replace(",", "."), f"{r['ins'] / r['n'] ** 3:.1f}",
                      f"{v['ins']:,}".replace(",", ".") if v else "—",
                      "✓" if r["ok"] and (v is None or v["ok"]) else "✗"])
    tabla(filas, [2.2, 3.8, 2.8, 3.8, 4.6])
    p("El cociente instrucciones / n³ tiende a ~43, lo que confirma el costo Θ(n³) del producto (de 8 a 16 "
      "el trabajo se multiplica por 7,6 ≈ 2³). El producto matriz por vector crece como n² (de 8 a 16: "
      "× 3,7). Con el mapa original (B a 512 bytes de A) un producto 8 × 8 era rechazado por solapamiento; "
      "con DESP_MATRIZ_2 = 0x3000 caben matrices de 32 × 32, el máximo que dibuja la GUI.")
    h2("8.5 Suite de regresión")
    tabla([["Archivo de pruebas", "Casos", "Qué verifica"],
           ["test_preprocesador_estructuras.py", "31", "#include, guardas, macros VEC_DIR / MAT_DIR, layout"],
           ["test_vec_lib.py", "41", "VEC_* en la CPU real: direcciones, solapes de VEC_COPY, preservación"],
           ["test_mat_lib.py", "74", "MAT_*, contenido de cada marco de pila, recursión de 300 niveles"],
           ["test_estructuras_cargador.py", "18", "descriptores, normalización 64 bits, .e64 y CargadorEnigma"],
           ["test_merge_sort.py", "20", "merge sort: casos borde, estrés de recursión, métricas N log N"],
           ["test_libreria_estructuras.py", "38", "los tres problemas extremo a extremo"],
           ["test_layout_capacidad.py", "8", "DESP_* iguales en Python y ensamblador; vectores de 300, 8 × 8"],
           ["tests/ui/test_ui_estructuras.py", "43", "servicio y pestaña de la GUI con los tres problemas"],
           ["Total Tarea 29", "273", ""]], [5.8, 1.5, 9.9])
    p("La suite completa del proyecto (incluidas las Tareas # 10, # 17, # 27 y el Taller # 01) se ejecutó "
      "tras integrar las ramas de los siete integrantes: <b>" + SUITE + "</b>, lo que confirma que la "
      "librería no alteró la máquina ni las herramientas previas.")
    h2("8.6 Análisis de resultados")
    p("<b>Corrección.</b> En los tres escenarios los resultados coinciden con el oráculo para todos los "
      "tamaños probados, incluidos negativos, duplicados, vectores de un elemento y consultas ausentes. "
      "<b>Costo de la modularidad.</b> En el merge sort una lectura de V[i] cuesta 5 instrucciones vía "
      "VEC_GET (CALL, SHL, ADD, LOAD, RET) frente a 3 en línea; en el producto de matrices MAT_GET añade "
      "además el marco ENTER/LEAVE y la llamada anidada a MAT_ADDR (12 instrucciones por acceso, contando la llamada). Ese factor "
      "constante (≈ 1,7–3×) no cambia el orden de complejidad, como muestran las tablas, y compra "
      "legibilidad, reutilización y que cada rutina se pruebe de forma aislada. Las macros VEC_DIR / MAT_DIR "
      "quedan disponibles para el programador que quiera el acceso en línea cuando el índice es constante. "
      "<b>Integración.</b> La revisión de la integración detectó que los programas 2 y 3 colocaban la "
      "segunda estructura a 256 / 512 bytes de la primera: un vector de 31 elementos o una matriz 8 × 8 "
      "producían un solapamiento (detectado por MapaEstructurasRAM, nunca corrupción silenciosa). Se "
      "centralizaron los desplazamientos en layout_datos.inc y se añadió la prueba de consistencia; la GUI "
      "toma las mismas constantes.")


def cierre():
    h1("9. LIMITACIONES CONOCIDAS")
    vinetas([
        "Las primitivas no comprueban límites (como los arreglos de C): un índice fuera de rango lee o "
        "escribe memoria vecina. La validación se hace en el lado Python y en la GUI antes de escribir.",
        "Los elementos son palabras de 64 bits; la librería mueve bits crudos y el cálculo con double "
        "depende del programa (la FPU de la Tarea # 17), no de la librería.",
        "La capacidad por estructura la fija el mapa: 510 elementos para el primer vector de un programa "
        "con dos vectores y 1.534 palabras para cada matriz; los programas de prueba usan bases fijas.",
        "Las estructuras son estáticas: no hay asignación dinámica (malloc) ni redimensionamiento.",
        "Un preprocesador de una línea por macro no puede emitir secuencias de instrucciones, por eso la "
        "gestión de pila vive en subrutinas y no en macros.",
    ])
    h1("10. CONCLUSIONES")
    vinetas([
        "Se construyó una librería de listas y matrices para Enigma-64 que se incorpora con una sola línea "
        "(<font face='Courier'>#include \"estructuras.inc\"</font>) y que gestiona el preprocesador del SPL, "
        "como pide el enunciado, sin modificar la máquina de la Tarea # 10.",
        "El diseño modular (layout, vec, cabeceras, mat; guardas de inclusión; ABI única) permitió que siete "
        "personas desarrollaran y probaran su parte por separado y que todo se integrara sin conflictos.",
        "El algoritmo de las mezclas, el producto punto, la búsqueda binaria y el producto de matrices "
        "corren en la CPU emulada con resultados correctos y con los órdenes de crecimiento predichos: "
        "Θ(N log N), Θ(N), Θ(log N) y Θ(n³).",
        "La pestaña Estructuras de la GUI hace visible el funcionamiento: los datos que escribe el usuario, "
        "las celdas que cada instrucción lee o escribe y el resultado final frente a la entrada.",
        "273 pruebas automatizadas específicas de la tarea, sobre la CPU real, sostienen la corrección y "
        "protegen el contrato de la librería ante cambios futuros.",
    ])
    h1("REFERENCIAS")
    for r in [
        "[1] T. H. Cormen, C. E. Leiserson, R. L. Rivest y C. Stein, <i>Introduction to Algorithms</i>, 4.ª ed. "
        "MIT Press, 2022.",
        "[2] A. V. Aho, M. S. Lam, R. Sethi y J. D. Ullman, <i>Compiladores: principios, técnicas y "
        "herramientas</i>, 2.ª ed. Pearson, 2008.",
        "[3] D. A. Patterson y J. L. Hennessy, <i>Computer Organization and Design: The Hardware/Software "
        "Interface</i>, 6.ª ed. Morgan Kaufmann, 2020.",
        "[4] D. E. Knuth, <i>The Art of Computer Programming, Vol. 3: Sorting and Searching</i>, 2.ª ed. "
        "Addison-Wesley, 1998.",
        "[5] D. Beazley, <i>PLY (Python Lex-Yacc) 3.11</i>, documentación, https://www.dabeaz.com/ply/.",
        "[6] Grupo Enigma-64, <i>Tareas # 09, # 10, # 17, # 27 y Taller # 01</i>, Universidad Nacional de "
        "Colombia, 2026.",
    ]:
        p(r, ParagraphStyle("ref", parent=CUERPO, fontSize=8.8, leading=11.5, alignment=0))
    h1("A. ANEXO: INVENTARIO DEL CÓDIGO FUENTE")
    tabla([["Archivo", "Líneas", "Autor"],
           ["spl/include/estructuras.inc", "67", "Integrante 4"],
           ["spl/include/layout_datos.inc", "84", "Integrantes 1 y 5"],
           ["spl/include/vec.asm", "151", "Integrante 2"],
           ["spl/include/cabeceras.asm", "155", "Integrante 4"],
           ["spl/include/mat.asm", "139", "Integrante 3"],
           ["spl/estructuras/ (descriptores, memoria, cargador, __main__, __init__)", "1.344", "Integrante 4"],
           ["spl/estructuras/algoritmos.py", "267", "Integrante 7"],
           ["spl/ejemplos/merge_sort.asm", "362", "Integrante 6"],
           ["spl/ejemplos/producto_punto.asm · busqueda_binaria.asm", "414", "Integrante 7"],
           ["spl/ejemplos/multiplicacion_matrices.asm", "419", "Integrante 7"],
           ["spl/ejemplos/prueba_vec.asm · prueba_mat.asm · prueba_cabeceras_cargador.asm", "356",
            "Integrantes 2, 3 y 4"],
           ["enigma64/ui/servicios/estructuras.py", "896", "Integrante 5"],
           ["enigma64/ui/paneles/panel_estructuras.py · core/visores.py", "931", "Integrante 5"],
           ["tests/ (8 archivos de la Tarea 29)", "2.933", "Todos"],
           ["docs/integrantes/informe_integrante*_{vec,mat,estructuras_*,merge_sort_mmio}.md", "—",
            "Informes individuales"]], [11.2, 2, 4])


def construir(total):
    global TOTAL, historia
    TOTAL = total
    historia = []
    portada(); contenido(); marco_teorico(); descripcion(); diseno(); libreria(); problemas()
    manual_tecnico(); manual_usuario(); experimentacion(); cierre()
    doc = Doc(SALIDA, pagesize=letter, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
              topMargin=2 * cm, bottomMargin=1.9 * cm, title="Tarea 29 - Librería de estructuras de datos",
              author="Grupo Enigma-64")
    doc.build(historia, onFirstPage=marco, onLaterPages=marco)
    return doc.page


TOTAL = "?"
n = construir("?")
construir(n)
print("paginas:", n)
