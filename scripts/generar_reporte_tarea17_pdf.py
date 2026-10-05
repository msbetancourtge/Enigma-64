"""
Generador del Reporte Técnico Académico en PDF para la Tarea 17 (FPU Enigma-64).
Universidad Nacional de Colombia - Asignatura: Lenguajes de Programación (2026-2).
Profesor Titular: Jorge Eduardo Ortiz Triviño.

Cumplimiento estricto de:
- Sección 3.1.1 de los Lineamientos del Curso (Literales a a f).
- Sección 4.2: Nomenclatura del archivo y copia para buzón ('17 Arguello Munoz Alejandro 01.pdf').
- Estética y sobriedad académica: Blanco y Negro (B&W), tipografía Times-Roman formal,
  canvas de dos pasadas NumberedCanvas con 'Página X de Y', tablas estructuradas y figuras procesadas.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageOps

from reportlab.lib.colors import black, HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable, Image as RLImage, KeepTogether, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle
)


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para calcular y numerar páginas formalmente (Página X de Y)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_paginas = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_paginas)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_paginas: int):
        self.saveState()
        self.setFont("Times-Roman", 8)
        self.setStrokeColorRGB(0, 0, 0)
        self.setLineWidth(0.5)

        m_izq = 2.4 * cm
        m_der = letter[0] - 2.4 * cm
        m_sup = letter[1] - 1.4 * cm
        m_inf = 1.2 * cm

        if self._pageNumber > 1:
            # Encabezado formal superior (páginas > 1)
            self.drawString(
                m_izq, m_sup,
                "Universidad Nacional de Colombia * Lenguajes de Programación * Tarea 17: FPU Enigma-64"
            )
            self.line(m_izq, m_sup - 4, m_der, m_sup - 4)

        # Pie de página inferior formal
        texto_pie = f"Página {self._pageNumber} de {total_paginas}"
        self.drawRightString(m_der, m_inf, texto_pie)
        self.drawString(m_izq, m_inf, "Memoria Técnica: Aritmética de Punto Flotante IEEE 754 (Binary64)")
        self.line(m_izq, m_inf + 10, m_der, m_inf + 10)

        self.restoreState()


def preparar_figura_fpu_bw(base_dir: Path) -> Path | None:
    """Rasteriza el mockup SVG del panel FPU a escala de grises con alta resolución."""
    svg_path = base_dir / "enigma64" / "ui" / "mockups" / "10_panel_fpu.svg"
    figuras_dir = base_dir / "docs" / "figuras"
    figuras_dir.mkdir(parents=True, exist_ok=True)
    out_png_bw = figuras_dir / "10_panel_fpu_bw.png"

    if out_png_bw.exists():
        return out_png_bw

    if not svg_path.exists():
        return None

    try:
        import pymupdf
        doc = pymupdf.open(str(svg_path))
        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        temp_png = figuras_dir / "temp_fpu.png"
        pix.save(str(temp_png))
        doc.close()

        im = Image.open(temp_png)
        gray = ImageOps.grayscale(im)
        gray.save(out_png_bw)
        if temp_png.exists():
            temp_png.unlink()
        return out_png_bw
    except Exception as exc:
        print(f"Aviso: No fue posible generar la imagen BW desde SVG: {exc}")
        return None


def construir_estilos():
    estilos = {}

    estilos["PortadaUniversidad"] = ParagraphStyle(
        "PortadaUniversidad",
        fontName="Times-Bold",
        fontSize=18.0,
        leading=22.0,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    estilos["PortadaFacultad"] = ParagraphStyle(
        "PortadaFacultad",
        fontName="Times-Roman",
        fontSize=12.0,
        leading=16.0,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    estilos["PortadaTitulo"] = ParagraphStyle(
        "PortadaTitulo",
        fontName="Times-Bold",
        fontSize=17.0,
        leading=22.0,
        alignment=TA_CENTER,
        spaceBefore=10,
        spaceAfter=12,
    )
    estilos["PortadaSubtitulo"] = ParagraphStyle(
        "PortadaSubtitulo",
        fontName="Times-Roman",
        fontSize=10.5,
        leading=14.0,
        alignment=TA_CENTER,
        spaceAfter=16,
    )
    estilos["PortadaMetadatos"] = ParagraphStyle(
        "PortadaMetadatos",
        fontName="Times-Roman",
        fontSize=10.0,
        leading=14.5,
        alignment=TA_CENTER,
        spaceAfter=4,
    )
    estilos["H1"] = ParagraphStyle(
        "H1",
        fontName="Times-Bold",
        fontSize=11.5,
        leading=15.0,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True,
    )
    estilos["H2"] = ParagraphStyle(
        "H2",
        fontName="Times-Bold",
        fontSize=10.0,
        leading=13.0,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True,
    )
    estilos["H3"] = ParagraphStyle(
        "H3",
        fontName="Times-BoldItalic",
        fontSize=9.0,
        leading=12.0,
        spaceBefore=5,
        spaceAfter=2,
        keepWithNext=True,
    )
    estilos["Parrafo"] = ParagraphStyle(
        "Parrafo",
        fontName="Times-Roman",
        fontSize=8.8,
        leading=12.0,
        alignment=TA_JUSTIFY,
        spaceAfter=4.5,
    )
    estilos["ParrafoDestacado"] = ParagraphStyle(
        "ParrafoDestacado",
        fontName="Times-BoldItalic",
        fontSize=8.8,
        leading=12.0,
        alignment=TA_JUSTIFY,
        spaceAfter=4.5,
    )
    estilos["Codigo"] = ParagraphStyle(
        "Codigo",
        fontName="Courier",
        fontSize=7.2,
        leading=9.0,
        alignment=TA_LEFT,
    )
    estilos["CodigoBox"] = ParagraphStyle(
        "CodigoBox",
        fontName="Courier",
        fontSize=6.8,
        leading=8.6,
        alignment=TA_LEFT,
    )
    estilos["Epigrafe"] = ParagraphStyle(
        "Epigrafe",
        fontName="Times-Italic",
        fontSize=7.8,
        leading=10.0,
        alignment=TA_CENTER,
        spaceBefore=2,
        spaceAfter=6,
    )
    estilos["TablaCelda"] = ParagraphStyle(
        "TablaCelda",
        fontName="Times-Roman",
        fontSize=7.6,
        leading=9.6,
        alignment=TA_LEFT,
    )
    estilos["TablaCeldaCentro"] = ParagraphStyle(
        "TablaCeldaCentro",
        fontName="Times-Roman",
        fontSize=7.6,
        leading=9.6,
        alignment=TA_CENTER,
    )
    estilos["TablaCabecera"] = ParagraphStyle(
        "TablaCabecera",
        fontName="Times-Bold",
        fontSize=7.8,
        leading=9.8,
        alignment=TA_CENTER,
    )
    estilos["Referencia"] = ParagraphStyle(
        "Referencia",
        fontName="Times-Roman",
        fontSize=9.2,
        leading=13.5,
        alignment=TA_JUSTIFY,
        leftIndent=24,
        firstLineIndent=-24,
        spaceAfter=10,
    )
    return estilos


def crear_tabla_codigo(texto_codigo: str, estilos: dict, ancho: float = 16.7 * cm) -> Table:
    """Crea una caja de código formateada con borde fino y fondo claro sobrio."""
    lineas = texto_codigo.strip().splitlines()
    parrafos = [
        Paragraph(l.replace(" ", "&nbsp;").replace("<", "&lt;").replace(">", "&gt;"), estilos["CodigoBox"])
        for l in lineas
    ]
    tabla = Table([[parrafos]], colWidths=[ancho])
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F5F5F5")),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tabla


def construir_reporte_pdf(pdf_salida: Path, ruta_figura_fpu: Path | None):
    margen_horiz = 2.4 * cm
    margen_vert = 2.0 * cm
    doc = SimpleDocTemplate(
        str(pdf_salida),
        pagesize=letter,
        leftMargin=margen_horiz,
        rightMargin=margen_horiz,
        topMargin=margen_vert,
        bottomMargin=margen_vert,
    )

    estilos = construir_estilos()
    historia = []
    ancho_util = letter[0] - 2 * margen_horiz

    # =========================================================================
    # PÁGINA 1: PORTADA FORMAL ACADÉMICA
    # =========================================================================
    historia.append(Spacer(1, 1.2 * cm))
    historia.append(Paragraph("UNIVERSIDAD NACIONAL DE COLOMBIA", estilos["PortadaUniversidad"]))
    historia.append(Paragraph(
        "FACULTAD DE INGENIERÍA<br/>"
        "DEPARTAMENTO DE INGENIERÍA DE SISTEMAS E INDUSTRIAL<br/>"
        "LENGUAJES DE PROGRAMACIÓN",
        estilos["PortadaFacultad"]
    ))
    historia.append(HRFlowable(width="100%", thickness=1.5, color="black", spaceAfter=25, spaceBefore=4))

    historia.append(Spacer(1, 1.0 * cm))
    historia.append(Paragraph(
        "TAREA 17  -  UNIDAD DE PUNTO FLOTANTE (FPU):<br/>"
        "ENIGMA-64",
        estilos["PortadaTitulo"]
    ))

    historia.append(Spacer(1, 1.5 * cm))
    historia.append(Paragraph("<b>AUTORES:</b>", estilos["PortadaMetadatos"]))
    historia.append(Spacer(1, 0.2 * cm))

    autores = [
        "Tomás Felipe Garzón Gómez",
        "Juan Sebastián Umaña Camacho",
        "Michael Stiven Betancourt Gelves",
        "Deibyd Santiago Barragán Gaitán",
        "Maicol Sebastián Olarte Ramírez",
        "Juan Luis Vergara Novoa",
        "Alejandro Argüello Muñoz",
    ]
    for autor in autores:
        historia.append(Paragraph(autor, estilos["PortadaMetadatos"]))

    historia.append(Spacer(1, 1.2 * cm))
    historia.append(Paragraph("<b>Docente:</b> Jorge Eduardo Ortiz Triviño", estilos["PortadaMetadatos"]))
    historia.append(Paragraph("Bogotá D.C., Colombia  -  Octubre de 2026", estilos["PortadaMetadatos"]))
    historia.append(PageBreak())

    # =========================================================================
    # PÁGINA 2: 1. MARCO TEÓRICO (Cumple Literal a) - IEEE 754 y Aritmética Base
    # =========================================================================
    historia.append(Paragraph("1. MARCO TEÓRICO", estilos["H1"]))
    historia.append(Paragraph(
        "El computador Enigma-64, concebido como una arquitectura Von Neumann de 64 bits con memoria físicamente "
        "paginada y palabra natural de 8 bytes, incorpora en la Tarea 17 una <b>Unidad de Punto Flotante (FPU)</b> "
        "completa implementada a nivel de software mediante lenguaje ensamblador puro. El diseño se ciñe rigurosamente "
        "a la norma internacional <b>IEEE 754-2008</b> para el formato de doble precisión binaria (<b>Binary64</b>).",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("1.1. Representación de Números en Punto Flotante IEEE 754 Doble Precisión (Binary64)", estilos["H2"]))
    historia.append(Paragraph(
        "En el formato Binary64, una palabra de 64 bits se descompone en tres campos canónicos contiguos:<br/>"
        "- <b>Signo (s, bit 63):</b> 1 bit donde 0 representa valores positivos y 1 denota valores negativos.<br/>"
        "- <b>Exponente sesgado (e, bits 62..52):</b> 11 bits con un sesgo (<i>bias</i>) fijo de <b>1023</b>, "
        "abarcando exponentes no sesgados en el rango [-1022, +1023].<br/>"
        "- <b>Mantisa fraccionaria (f, bits 51..0):</b> 52 bits explícitos. Para números normales, existe un bit implícito "
        "unitario (1.f), totalizando 53 bits de precisión efectiva (~15.9 dígitos decimales).",
        estilos["Parrafo"]
    ))

    datos_ieee = [
        [Paragraph("Clase de Número", estilos["TablaCabecera"]),
         Paragraph("Exponente (e)", estilos["TablaCabecera"]),
         Paragraph("Fracción (f)", estilos["TablaCabecera"]),
         Paragraph("Valor Matemático Representado", estilos["TablaCabecera"]),
         Paragraph("Ejemplo Hexadecimal (64b)", estilos["TablaCabecera"])],
        [Paragraph("Cero (+0 / -0)", estilos["TablaCelda"]), Paragraph("0 (todos 0)", estilos["TablaCeldaCentro"]), Paragraph("0 (todos 0)", estilos["TablaCeldaCentro"]), Paragraph("(-1)<sup>s</sup> * 0.0", estilos["TablaCelda"]), Paragraph("<code>0x0000000000000000</code>", estilos["TablaCelda"])],
        [Paragraph("Subnormal", estilos["TablaCelda"]), Paragraph("0 (todos 0)", estilos["TablaCeldaCentro"]), Paragraph("f != 0", estilos["TablaCeldaCentro"]), Paragraph("(-1)<sup>s</sup> * 2<sup>-1022</sup> * (0.f)", estilos["TablaCelda"]), Paragraph("<code>0x0000000000000001</code>", estilos["TablaCelda"])],
        [Paragraph("Normal", estilos["TablaCelda"]), Paragraph("1 &lt;= e &lt;= 2046", estilos["TablaCeldaCentro"]), Paragraph("Cualquiera", estilos["TablaCeldaCentro"]), Paragraph("(-1)<sup>s</sup> * 2<sup>e-1023</sup> * (1.f)", estilos["TablaCelda"]), Paragraph("<code>0x3FF0000000000000</code> (+1.0)", estilos["TablaCelda"])],
        [Paragraph("Infinito (+Inf / -Inf)", estilos["TablaCelda"]), Paragraph("2047 (todos 1)", estilos["TablaCeldaCentro"]), Paragraph("0 (todos 0)", estilos["TablaCeldaCentro"]), Paragraph("(-1)<sup>s</sup> * Inf", estilos["TablaCelda"]), Paragraph("<code>0x7FF0000000000000</code> (+Inf)", estilos["TablaCelda"])],
        [Paragraph("NaN (Not a Number)", estilos["TablaCelda"]), Paragraph("2047 (todos 1)", estilos["TablaCeldaCentro"]), Paragraph("f != 0", estilos["TablaCeldaCentro"]), Paragraph("Indeterminado (qNaN / sNaN)", estilos["TablaCelda"]), Paragraph("<code>0x7FF8000000000000</code> (qNaN)", estilos["TablaCelda"])],
    ]
    t_ieee = Table(datos_ieee, colWidths=[2.7 * cm, 2.5 * cm, 2.3 * cm, 4.4 * cm, 4.8 * cm])
    t_ieee.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, -1), (-1, -1), 1, black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.0),
    ]))
    historia.append(t_ieee)
    historia.append(Paragraph("Tabla 1: Especificación de campos, sesgos y casos especiales en IEEE 754 Binary64.", estilos["Epigrafe"]))

    historia.append(Paragraph("1.2. Algoritmos de Aritmética Flotante Básica en Ensamblador Puro", estilos["H2"]))
    historia.append(Paragraph(
        "Dado que la ALU de Enigma-64 únicamente ejecuta instrucciones de números enteros de 64 bits, las operaciones "
        "flotantes fueron sintetizadas mediante algoritmos canónicos de descomposición y recomposición:<br/>"
        "1. <b>Suma y Resta (FADD / FSUB):</b> Desempaquetado de operandos, igualación de exponentes mediante corrimiento "
        "a la derecha de la mantisa de menor magnitud, suma/resta con signo de las mantisas alineadas, normalización por corrimiento "
        "a la izquierda/derecha y redondeo formal hacia el par más cercano (<i>roundTiesToEven</i>).<br/>"
        "2. <b>Multiplicación (FMUL):</b> Signo resultante por XOR (<i>S = S<sub>A</sub>  XOR  S<sub>B</sub></i>). Suma de exponentes "
        "con corrección de sesgo (<i>E<sub>R</sub> = E<sub>A</sub> + E<sub>B</sub> - 1023</i>). Multiplicación completa de mantisas de "
        "53 * 53 bits (producto de hasta 106 bits) descompuesta en cuatro multiplicaciones de 32 bits en la subrutina <code>FPU_MUL128</code>, "
        "con extracción rigurosa de bits Guard, Round y Sticky.<br/>"
        "3. <b>División (FDIV):</b> Signo <i>S = S<sub>A</sub>  XOR  S<sub>B</sub></i>, resta de exponentes (<i>E<sub>R</sub> = E<sub>A</sub> - E<sub>B</sub> + 1023</i>). "
        "División larga entera binaria de mantisas de 64 bits con detección de residuo exacto para bit Sticky y detección formal de división por cero.<br/>"
        "4. <b>Comparación (FCMP):</b> Distinción de NaNs (retorna código no ordenado 2), orden estricto de signos, comparación de magnitudes y "
        "reconocimiento de equivalencia <code>+0.0 == -0.0</code> (retorna 0).<br/>"
        "5. <b>Conversiones (FPU_INT_TO_FLOAT / FPU_FLOAT_TO_INT):</b> Detección de signo, búsqueda del MSB, empaquetado sesgado y truncamiento.",
        estilos["Parrafo"]
    ))
    historia.append(PageBreak())

    # =========================================================================
    # PÁGINA 3: 1.3 Newton-Raphson, 1.4 Brun y 2. Justificación (Literales a y b)
    # =========================================================================
    historia.append(Paragraph("1.3. Método Numérico de Newton-Raphson para Raíz Cuadrada (Ricardo Peña, Pág. 26)", estilos["H2"]))
    historia.append(Paragraph(
        "En la página 26 del libro <i>De Euclides a JAVA: historia de los algoritmos y de los lenguajes de programación</i> "
        "(Ricardo Peña, 2006), se documenta el método iterativo clásico para la extracción de la raíz cuadrada de un número real "
        "<i>A > 0</i> resolviendo la ecuación no lineal <i>f(x) = x<sup>2</sup> - A = 0</i>. Aplicando la derivada <i>f'(x) = 2x</i>:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>x<sub>k+1</sub> = 0.5 * (x<sub>k</sub> + A / x<sub>k</sub>)</b><br/>"
        "El método goza de convergencia cuadrática (duplica la cantidad de cifras exactas en cada ciclo). Para garantizar convergencia "
        "en 4-5 iteraciones sobre punto flotante de 64 bits, se calcula analíticamente la semilla inicial a partir del exponente IEEE 754: "
        "<i>e<sub>0</sub> = floor((E<sub>A</sub> - 1023) / 2)</i>, ensamblando <i>x<sub>0</sub> = (e<sub>0</sub> + 1023) &lt;&lt; 52</i>.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("1.4. Teoría y Convergencia de la Constante de Brun (B<sub>2</sub>)", estilos["H2"]))
    historia.append(Paragraph(
        "En 1919, el matemático noruego Viggo Brun demostró que la suma de los recíprocos de los números primos gemelos "
        "(pares de primos de la forma <i>(p, p+2)</i>) converge hacia una constante matemática finita denominada <b>Constante de Brun (B<sub>2</sub>)</b>:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<b>B<sub>2</sub> = SUM<sub>(p, p+2) en Primos</sub> (1/p + 1/(p+2)) = (1/3 + 1/5) + (1/5 + 1/7) + (1/11 + 1/13) + ... ~ 1.90216058...</b><br/>"
        "A diferencia de la serie armónica clásica de los números primos que diverge, la serie de Brun converge de forma sumamente lenta. "
        "Desde la óptica de la ingeniería computacional, la estimación de <i>B<sub>2</sub></i> representa un banco de pruebas de esfuerzo extremo (<i>stress test</i>): "
        "requiere ejecutar miles de divisiones flotantes (1/p y 1/(p+2)), acumulaciones repetitivas con redondeo inexacto y cientos de llamadas "
        "anidadas a subrutinas evaluando la estabilidad absoluta del puntero de pila.",
        estilos["Parrafo"]
    ))

    # 2. DESCRIPCIÓN Y JUSTIFICACIÓN DEL PROBLEMA (Cumple Literal b)
    historia.append(Spacer(1, 0.2 * cm))
    historia.append(Paragraph("2. DESCRIPCIÓN Y JUSTIFICACIÓN DEL PROBLEMA", estilos["H1"]))
    historia.append(Paragraph(
        "El computador Enigma-64 fue concebido originalmente con un repertorio ISA restringido exclusivamente a enteros. "
        "Para posibilitar la ejecución de aplicaciones científicas, algoritmos iterativos y la futura integración de un compilador "
        "de alto nivel, es imprescindible incorporar capacidades de punto flotante de doble precisión sin alterar el hardware físico base.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("2.1. Desafíos Técnicos y Restricciones de Microarquitectura", estilos["H2"]))
    historia.append(Paragraph(
        "1. <b>Ausencia de FPU por Hardware:</b> La CPU sólo dispone de suma, resta, multiplicación y división entera de 64 bits. "
        "Toda la manipulación de campos de bits, normalización y redondeo debe ser orquestada instrucción por instrucción en ensamblador.<br/>"
        "2. <b>Preservación de Marcos de Pila en Llamadas Anidadas:</b> La evaluación de la Constante de Brun requiere que una función "
        "(<code>FPU_BRUN</code>) invoque consecutivamente a <code>FPU_ES_PRIMO</code>, <code>FPU_INT_TO_FLOAT</code>, <code>FDIV</code> "
        "y <code>FADD</code>. Dado que las convenciones de llamada establecen que los registros <code>R1..R5</code> son volátiles (<i>caller-saved</i>), "
        "es imperativo implementar una gestión estricta del marco de pila (<i>Stack Frame</i>) mediante <code>ENTER</code> y <code>LEAVE</code>.<br/>"
        "3. <b>Mesa Canónica de Vectores Desacoplada:</b> Para permitir que programas de usuario ejecuten servicios de la FPU sin conocer las "
        "direcciones de memoria internas de los autores, se requiere una tabla de salto fija (<i>Jump Table</i>) de 9 entradas canónicas.<br/>"
        "4. <b>Fidelidad Absoluta al Estándar IEEE 754:</b> La emulación debe gestionar minuciosamente casos límite: división por cero (retornando "
        "infinito con signo XOR), ceros con signo (donde <code>+0.0 == -0.0</code> pero <code>1/(+0) = +Inf</code> y <code>1/(-0) = -Inf</code>), "
        "indeterminaciones (<code>0/0</code> y <code>Inf/Inf</code> produciendo NaN canónico) y comparaciones no ordenadas con NaNs.",
        estilos["Parrafo"]
    ))
    historia.append(PageBreak())

    # =========================================================================
    # PÁGINA 4: 3. DISEÑO DE LA SOLUCIÓN Y ARQUITECTURA (Cumple Literal c)
    # =========================================================================
    historia.append(Paragraph("3. DISEÑO DE LA SOLUCIÓN Y ARQUITECTURA DEL SISTEMA", estilos["H1"]))
    historia.append(Paragraph(
        "La solución se estructuró mediante una arquitectura modular multicapa donde cada componente canónico fue "
        "rigurosamente desacoplado e integrado a través de la Mesa de Vectores en el archivo consolidado <code>programas/fpu_lib.s</code>.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("3.1. Estructura de la Mesa Canónica de Vectores (FPU_VECTORES)", estilos["H2"]))
    historia.append(Paragraph(
        "Ubicada en el offset <code>+0x00</code> de la biblioteca FPU cargada en memoria RAM, cada entrada consta exactamente "
        "de 5 bytes (1 byte de opcode <code>JMP 0x15</code> + 4 bytes de dirección absoluta Big-Endian):",
        estilos["Parrafo"]
    ))

    datos_vectores = [
        [Paragraph("Vector", estilos["TablaCabecera"]),
         Paragraph("Offset", estilos["TablaCabecera"]),
         Paragraph("Instrucción Salto", estilos["TablaCabecera"]),
         Paragraph("Servicio Matemático IEEE 754", estilos["TablaCabecera"])],
        [Paragraph("<b>VEC_FADD</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x00", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FADD</code>", estilos["TablaCelda"]), Paragraph("Suma flotante IEEE 754 (R5 = R1 + R2)", estilos["TablaCelda"])],
        [Paragraph("<b>VEC_FSUB</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x05", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FSUB</code>", estilos["TablaCelda"]), Paragraph("Resta flotante IEEE 754 (R5 = R1 - R2)", estilos["TablaCelda"])],
        [Paragraph("<b>VEC_FMUL</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x0A", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FMUL</code>", estilos["TablaCelda"]), Paragraph("Multiplicación IEEE 754 (R5 = R1 * R2)", estilos["TablaCelda"])],
        [Paragraph("<b>VEC_FDIV</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x0F", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FDIV</code>", estilos["TablaCelda"]), Paragraph("División IEEE 754 (R5 = R1 / R2)", estilos["TablaCelda"])],
        [Paragraph("<b>VEC_FCMP</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x14", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FCMP</code>", estilos["TablaCelda"]), Paragraph("Comparación de orden (-1, 0, 1, 2)", estilos["TablaCelda"])],
        [Paragraph("<b>VEC_INT_TO_FLOAT</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x19", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FPU_INT_TO_FLOAT</code>", estilos["TablaCelda"]), Paragraph("Conversión Entero 64b -&gt; Float 64b", estilos["TablaCelda"])],
        [Paragraph("<b>VEC_FLOAT_TO_INT</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x1E", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FPU_FLOAT_TO_INT</code>", estilos["TablaCelda"]), Paragraph("Conversión Float 64b -&gt; Entero truncado", estilos["TablaCelda"])],
        [Paragraph("<b>VEC_FSQRT</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x23", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FSQRT</code>", estilos["TablaCelda"]), Paragraph("Raíz Cuadrada por Newton-Raphson", estilos["TablaCelda"])],
        [Paragraph("<b>VEC_FBRUN</b>", estilos["TablaCeldaCentro"]), Paragraph("+0x28", estilos["TablaCeldaCentro"]), Paragraph("<code>JMP FPU_BRUN</code>", estilos["TablaCelda"]), Paragraph("Estimación de Constante de Brun B<sub>2</sub>", estilos["TablaCelda"])],
    ]
    t_vectores = Table(datos_vectores, colWidths=[3.4 * cm, 1.8 * cm, 4.0 * cm, 7.5 * cm])
    t_vectores.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, -1), (-1, -1), 1, black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    historia.append(t_vectores)
    historia.append(Paragraph("Tabla 2: Especificación formal de la Mesa de Vectores Canónicos (FPU_VECTORES).", estilos["Epigrafe"]))

    historia.append(Paragraph("3.2. Diseño Algorítmico de la Constante de Brun (FPU_BRUN)", estilos["H2"]))
    historia.append(Paragraph(
        "La subrutina <code>FPU_BRUN</code> opera como un algoritmo numérico de orden superior que enlaza los módulos del equipo. "
        "El pseudocódigo formal de la subrutina implementada en ensamblador se detalla a continuación:",
        estilos["Parrafo"]
    ))

    pseudocodigo_brun = (
        "Subrutina FPU_BRUN(K_target):\n"
        "    Crear marco de pila ENTER 128\n"
        "    K_count = 0, p = 3, B2_acumulado = 0.0, const_1_0 = 1.0 (IEEE 754)\n"
        "    Si K_target <= 0: retornar B2 = 0.0, K_count = 0\n"
        "    Mientras K_count < K_target:\n"
        "        Si FPU_ES_PRIMO(p) == 1 y FPU_ES_PRIMO(p + 2) == 1:\n"
        "            rec_p = FDIV(const_1_0, FPU_INT_TO_FLOAT(p))\n"
        "            rec_q = FDIV(const_1_0, FPU_INT_TO_FLOAT(p + 2))\n"
        "            B2_acumulado = FADD(B2_acumulado, rec_p)\n"
        "            B2_acumulado = FADD(B2_acumulado, rec_q)\n"
        "            K_count = K_count + 1\n"
        "        p = p + 2\n"
        "    Liberar marco LEAVE\n"
        "    Retornar R5 = B2_acumulado, R1 = K_count, R2 = ultimo_p"
    )
    historia.append(crear_tabla_codigo(pseudocodigo_brun, estilos, ancho=16.7 * cm))
    historia.append(Paragraph("Listado 1: Pseudocódigo estructurado del algoritmo de la Constante de Brun en ensamblador.", estilos["Epigrafe"]))

    historia.append(Paragraph("3.3. Mapa del Marco de Pila Local (Stack Frame ENTER 128)", estilos["H2"]))
    historia.append(Paragraph(
        "Para garantizar invarianza y evitar la colisión de registros temporales <code>R1..R5</code> durante las llamadas a <code>FADD</code> "
        "y <code>FDIV</code>, <code>FPU_BRUN</code> asigna ranuras dedicadas en memoria de pila indexadas respecto al puntero base <code>BP</code>:",
        estilos["Parrafo"]
    ))

    datos_pila = [
        [Paragraph("Desplazamiento Pila", estilos["TablaCabecera"]),
         Paragraph("Identificador", estilos["TablaCabecera"]),
         Paragraph("Tipo / Formato", estilos["TablaCabecera"]),
         Paragraph("Propósito y Uso en la Subrutina", estilos["TablaCabecera"])],
        [Paragraph("<code>[BP - 8]</code>", estilos["TablaCeldaCentro"]), Paragraph("K_target", estilos["TablaCelda"]), Paragraph("Entero 64 bits", estilos["TablaCeldaCentro"]), Paragraph("Cantidad de pares de primos gemelos solicitada.", estilos["TablaCelda"])],
        [Paragraph("<code>[BP - 16]</code>", estilos["TablaCeldaCentro"]), Paragraph("K_count", estilos["TablaCelda"]), Paragraph("Entero 64 bits", estilos["TablaCeldaCentro"]), Paragraph("Contador de pares gemelos procesados hasta el momento.", estilos["TablaCelda"])],
        [Paragraph("<code>[BP - 24]</code>", estilos["TablaCeldaCentro"]), Paragraph("p_candidato", estilos["TablaCelda"]), Paragraph("Entero 64 bits", estilos["TablaCeldaCentro"]), Paragraph("Candidato impar actual evaluado (inicia en 3).", estilos["TablaCelda"])],
        [Paragraph("<code>[BP - 32]</code>", estilos["TablaCeldaCentro"]), Paragraph("B2_acum", estilos["TablaCelda"]), Paragraph("IEEE 754 (64 bits)", estilos["TablaCeldaCentro"]), Paragraph("Acumulador flotante de la constante de Brun.", estilos["TablaCelda"])],
        [Paragraph("<code>[BP - 40]</code>", estilos["TablaCeldaCentro"]), Paragraph("const_1_0", estilos["TablaCelda"]), Paragraph("IEEE 754 (64 bits)", estilos["TablaCeldaCentro"]), Paragraph("Constante flotante 1.0 (0x3FF0000000000000) para divisiones.", estilos["TablaCelda"])],
        [Paragraph("<code>[BP - 48]</code>", estilos["TablaCeldaCentro"]), Paragraph("rec_p", estilos["TablaCelda"]), Paragraph("IEEE 754 (64 bits)", estilos["TablaCeldaCentro"]), Paragraph("Recíproco 1.0 / p devuelto por FDIV.", estilos["TablaCelda"])],
        [Paragraph("<code>[BP - 56]</code>", estilos["TablaCeldaCentro"]), Paragraph("rec_q", estilos["TablaCelda"]), Paragraph("IEEE 754 (64 bits)", estilos["TablaCeldaCentro"]), Paragraph("Recíproco 1.0 / (p+2) devuelto por FDIV.", estilos["TablaCelda"])],
    ]
    t_pila = Table(datos_pila, colWidths=[3.2 * cm, 2.5 * cm, 3.5 * cm, 7.5 * cm])
    t_pila.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, -1), (-1, -1), 1, black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    historia.append(t_pila)
    historia.append(Paragraph("Tabla 3: Distribución del marco de pila de 128 bytes en la subrutina FPU_BRUN.", estilos["Epigrafe"]))
    historia.append(PageBreak())

    # =========================================================================
    # PÁGINA 5: 4. DOCUMENTACIÓN DE IMPLEMENTACIÓN Y MANUALES (Literales d y e)
    # =========================================================================
    historia.append(Paragraph("4. DOCUMENTACIÓN DE IMPLEMENTACIÓN Y MANUALES", estilos["H1"]))

    historia.append(Paragraph("4.1. Manual Técnico: Organización del Software y Módulos", estilos["H2"]))
    historia.append(Paragraph(
        "El código fuente se encuentra organizado de manera modular en el paquete <code>enigma64/</code> y la carpeta "
        "de binarios <code>programas/</code>. Todos los módulos se encuentran estrictamente tipados y desacoplados:",
        estilos["Parrafo"]
    ))

    arbol_codigo = (
        "enigma64/\n"
        "|-- fpu.s                 Núcleo FPU: FPU_DESEMPAQUETAR, FPU_EMPAQUETAR, FADD, FSUB\n"
        "|-- fmul.s                Multiplicación IEEE 754 con producto de 128 bits y subnormales\n"
        "|-- fdiv.s                División larga de mantisas con manejo de excepciones\n"
        "|-- fcmp.s                Comparador formal de orden IEEE 754 y clasificación de NaNs\n"
        "|-- fconv.s               Conversiones INT64 <-> FLOAT64 y Mesa de Entrada Canónica\n"
        "|-- fsqrt.s               Raíz cuadrada iterativa de Newton-Raphson (Peña, pág. 26)\n"
        "|-- fbrun.s               Test de primalidad y estimación de la Constante de Brun\n"
        "|-- fpu.py                Emulador FPU, API de alto nivel y compilación consolidada\n"
        "|-- oraculo_ieee754.py    Oráculo matemático de validación bit a bit y métricas ULP\n"
        "\-- ui/paneles/panel_fpu.py Interfaz gráfica interactiva y calculadora reactiva\n"
        "programas/\n"
        "|-- fpu_lib.s/.bin/.hex   Biblioteca consolidada con las 9 entradas canónicas (3141 bytes)\n"
        "|-- constante_brun.s/.bin Programa ejecutable de usuario para la Constante de Brun (3203 bytes)\n"
        "\-- raiz_cuadrada.s       Programa ejecutable de usuario para Raíz Cuadrada de Peña"
    )
    historia.append(crear_tabla_codigo(arbol_codigo, estilos, ancho=16.7 * cm))
    historia.append(Paragraph("Listado 2: Árbol de archivos y responsabilidades técnicas del subsistema FPU.", estilos["Epigrafe"]))

    historia.append(Paragraph("4.2. Convención de Llamada (ABI) y Disciplina de Registros", estilos["H2"]))
    historia.append(Paragraph(
        "- <b>Registros Volátiles (Caller-Saved):</b> <code>R1</code>, <code>R2</code>, <code>R3</code>, <code>R4</code> y <code>R5</code>. "
        "Las subrutinas pueden modificarlos libremente como operandos y acumuladores temporales.<br/>"
        "- <b>Registros de Retorno:</b> <code>R5</code> entrega el resultado primario flotante (64b). En <code>FPU_BRUN</code>, "
        "<code>R1</code> retorna la cantidad de pares gemelos y <code>R2</code> el último primo evaluado.<br/>"
        "- <b>Registros Callee-Saved:</b> <code>BP</code> (Base Pointer) y <code>SP</code> (Stack Pointer). Deben ser restaurados "
        "idénticamente mediante <code>ENTER</code> y <code>LEAVE</code> antes de ejecutar <code>RET</code>.<br/>"
        "- <b>Alineación de Bus:</b> Toda lectura y escritura en memoria física de 64 bits debe realizarse en direcciones múltiplos de 8.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("4.3. Manual de Usuario y Despliegue del Sistema", estilos["H2"]))
    historia.append(Paragraph(
        "El entorno se ejecuta bajo Python 3.10 o superior sin dependencias compiladas de cómputo:",
        estilos["Parrafo"]
    ))

    comandos_usuario = (
        "# 1. Lanzar la interfaz gráfica interactiva con la pestaña FPU reactiva:\n"
        "python main.py\n\n"
        "# 2. Lanzar únicamente el panel interactivo de la FPU:\n"
        "python -m enigma64.ui.paneles.panel_fpu\n\n"
        "# 3. Ejecutar la suite completa de pruebas automatizadas (471 pruebas):\n"
        "python -m pytest\n\n"
        "# 4. Ejecutar la batería de pruebas de la Constante de Brun e Integración:\n"
        "python -m pytest tests/test_fbrun.py tests/test_bateria_integracion.py -v\n\n"
        "# 5. Recompilar los binarios crudos (.bin), volcados (.hex) y estructurados (.e64):\n"
        "python scripts/generar_binarios.py"
    )
    historia.append(crear_tabla_codigo(comandos_usuario, estilos, ancho=16.7 * cm))
    historia.append(Paragraph("Listado 3: Guía de comandos para ejecución de la interfaz gráfica y suites de pruebas.", estilos["Epigrafe"]))

    historia.append(Paragraph("4.4. Versiones de Software y Entorno de Ejecución", estilos["H2"]))
    historia.append(Paragraph(
        "El proyecto opera bajo: <b>Python 3.11.x</b>, <b>pytest 8.x</b> y <b>reportlab 4.x</b> (para generación de reportes). "
        "En estricto cumplimiento de la <b>Sección 3.3 de los Lineamientos del Curso</b>, no se emplean librerías foráneas para la "
        "lógica de emulación ni para la síntesis de la FPU: toda la aritmética flotante se resolvió exclusivamente mediante algoritmos "
        "propios codificados en lenguaje ensamblador de Enigma-64.",
        estilos["Parrafo"]
    ))
    historia.append(PageBreak())

    # =========================================================================
    # PÁGINA 6: 5. EXPERIMENTACIÓN CUANTITATIVA (Literal f) - Escenarios 1, 2 y 3
    # =========================================================================
    historia.append(Paragraph("5. EXPERIMENTACIÓN, PRUEBAS Y ANÁLISIS DE RESULTADOS", estilos["H1"]))
    historia.append(Paragraph(
        "Conforme al <b>Literal f de la Sección 3.1.1 de los Lineamientos del Curso</b>, se documenta la experimentación rigurosa "
        "y el análisis cuantitativo de resultados sobre la CPU y memoria RAM de Enigma-64:",
        estilos["Parrafo"]
    ))

    # Escenario 1
    historia.append(Paragraph("5.1. Escenario 1: Validación Aritmética de las Subrutinas Núcleo (FADD, FSUB, FMUL, FDIV, FCMP)", estilos["H2"]))
    historia.append(Paragraph(
        "Se evaluó la exactitud de las operaciones elementales de la FPU contrastando cada resultado bit a bit contra el estándar IEEE 754:",
        estilos["Parrafo"]
    ))

    datos_esc1 = [
        [Paragraph("Operación", estilos["TablaCabecera"]),
         Paragraph("Operando A (Hex / Dec)", estilos["TablaCabecera"]),
         Paragraph("Operando B (Hex / Dec)", estilos["TablaCabecera"]),
         Paragraph("Resultado Obtenido (Hex)", estilos["TablaCabecera"]),
         Paragraph("Valor Flotante", estilos["TablaCabecera"]),
         Paragraph("Distancia ULP", estilos["TablaCabecera"])],
        [Paragraph("FADD", estilos["TablaCeldaCentro"]), Paragraph("<code>3FF8000000000000</code> (1.5)", estilos["TablaCelda"]), Paragraph("<code>4004000000000000</code> (2.5)", estilos["TablaCelda"]), Paragraph("<code>4010000000000000</code>", estilos["TablaCelda"]), Paragraph("4.0", estilos["TablaCeldaCentro"]), Paragraph("0 ULP (Exacto)", estilos["TablaCeldaCentro"])],
        [Paragraph("FSUB", estilos["TablaCeldaCentro"]), Paragraph("<code>4024000000000000</code> (10.0)", estilos["TablaCelda"]), Paragraph("<code>4008000000000000</code> (3.0)", estilos["TablaCelda"]), Paragraph("<code>401C000000000000</code>", estilos["TablaCelda"]), Paragraph("7.0", estilos["TablaCeldaCentro"]), Paragraph("0 ULP (Exacto)", estilos["TablaCeldaCentro"])],
        [Paragraph("FMUL", estilos["TablaCeldaCentro"]), Paragraph("<code>3FB999999999999A</code> (0.1)", estilos["TablaCelda"]), Paragraph("<code>3FC999999999999A</code> (0.2)", estilos["TablaCelda"]), Paragraph("<code>3F947AE147AE147C</code>", estilos["TablaCelda"]), Paragraph("0.02", estilos["TablaCeldaCentro"]), Paragraph("0 ULP (Exacto)", estilos["TablaCeldaCentro"])],
        [Paragraph("FDIV", estilos["TablaCeldaCentro"]), Paragraph("<code>3FF0000000000000</code> (1.0)", estilos["TablaCelda"]), Paragraph("<code>4008000000000000</code> (3.0)", estilos["TablaCelda"]), Paragraph("<code>3FD5555555555555</code>", estilos["TablaCelda"]), Paragraph("0.3333333333333333", estilos["TablaCeldaCentro"]), Paragraph("0 ULP (Exacto)", estilos["TablaCeldaCentro"])],
        [Paragraph("FCMP", estilos["TablaCeldaCentro"]), Paragraph("<code>4000000000000000</code> (2.0)", estilos["TablaCelda"]), Paragraph("<code>4014000000000000</code> (5.0)", estilos["TablaCelda"]), Paragraph("<code>FFFFFFFFFFFFFFFF</code>", estilos["TablaCelda"]), Paragraph("-1 (A < B)", estilos["TablaCeldaCentro"]), Paragraph("Exacto", estilos["TablaCeldaCentro"])],
    ]
    t_esc1 = Table(datos_esc1, colWidths=[1.8 * cm, 3.8 * cm, 3.8 * cm, 3.3 * cm, 2.5 * cm, 1.5 * cm])
    t_esc1.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, -1), (-1, -1), 1, black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    historia.append(t_esc1)
    historia.append(Paragraph("Tabla 4: Resultados experimentales del Escenario 1 (Operaciones FPU Núcleo).", estilos["Epigrafe"]))

    # Escenario 2
    historia.append(Paragraph("5.2. Escenario 2: Estimación de la Raíz Cuadrada por Newton-Raphson (FSQRT)", estilos["H2"]))
    historia.append(Paragraph(
        "Se verificó la convergencia del algoritmo de Newton-Raphson sobre cuadrados perfectos, decimales e irracionales trascendentes:",
        estilos["Parrafo"]
    ))

    datos_esc2 = [
        [Paragraph("Caso Evaluado", estilos["TablaCabecera"]),
         Paragraph("Entrada A", estilos["TablaCabecera"]),
         Paragraph("Patrón Entrada (Hex)", estilos["TablaCabecera"]),
         Paragraph("Salida FSQRT (Hex)", estilos["TablaCabecera"]),
         Paragraph("Valor Calculado", estilos["TablaCabecera"]),
         Paragraph("Tolerancia", estilos["TablaCabecera"])],
        [Paragraph("Cuadrado exacto", estilos["TablaCelda"]), Paragraph("16.0", estilos["TablaCeldaCentro"]), Paragraph("<code>4030000000000000</code>", estilos["TablaCelda"]), Paragraph("<code>4010000000000000</code>", estilos["TablaCelda"]), Paragraph("4.0", estilos["TablaCeldaCentro"]), Paragraph("0 ULP", estilos["TablaCeldaCentro"])],
        [Paragraph("Cuadrado exacto", estilos["TablaCelda"]), Paragraph("144.0", estilos["TablaCeldaCentro"]), Paragraph("<code>4062000000000000</code>", estilos["TablaCelda"]), Paragraph("<code>4028000000000000</code>", estilos["TablaCelda"]), Paragraph("12.0", estilos["TablaCeldaCentro"]), Paragraph("0 ULP", estilos["TablaCeldaCentro"])],
        [Paragraph("Fraccionario", estilos["TablaCelda"]), Paragraph("0.25", estilos["TablaCeldaCentro"]), Paragraph("<code>3FD0000000000000</code>", estilos["TablaCelda"]), Paragraph("<code>3FE0000000000000</code>", estilos["TablaCelda"]), Paragraph("0.5", estilos["TablaCeldaCentro"]), Paragraph("0 ULP", estilos["TablaCeldaCentro"])],
        [Paragraph("Irracional (Pi)", estilos["TablaCelda"]), Paragraph("pi (3.14159265...)", estilos["TablaCeldaCentro"]), Paragraph("<code>400921FB54442D18</code>", estilos["TablaCelda"]), Paragraph("<code>3FFC46A2529D36F6</code>", estilos["TablaCelda"]), Paragraph("1.7724538509055159", estilos["TablaCeldaCentro"]), Paragraph("&lt;= 1 ULP", estilos["TablaCeldaCentro"])],
        [Paragraph("Irracional (Euler)", estilos["TablaCelda"]), Paragraph("e (2.71828182...)", estilos["TablaCeldaCentro"]), Paragraph("<code>4005BF0A8B145769</code>", estilos["TablaCelda"]), Paragraph("<code>3FFA5FEBEBC2978D</code>", estilos["TablaCelda"]), Paragraph("1.6487212707001282", estilos["TablaCeldaCentro"]), Paragraph("&lt;= 1 ULP", estilos["TablaCeldaCentro"])],
    ]
    t_esc2 = Table(datos_esc2, colWidths=[2.6 * cm, 2.5 * cm, 3.4 * cm, 3.4 * cm, 3.3 * cm, 1.5 * cm])
    t_esc2.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, -1), (-1, -1), 1, black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    historia.append(t_esc2)
    historia.append(Paragraph("Tabla 5: Resultados experimentales del Escenario 2 (Raíz Cuadrada por Newton-Raphson).", estilos["Epigrafe"]))

    # Escenario 3
    historia.append(Paragraph("5.3. Escenario 3: Estimación de la Constante de Brun (B<sub>2</sub>) sobre la CPU de Enigma-64", estilos["H2"]))
    historia.append(Paragraph(
        "Se ejecutó el programa en ensamblador <code>FPU_BRUN</code> directamente sobre la CPU y memoria RAM de Enigma-64 para "
        "diferentes cantidades de pares gemelos, registrando ciclos FSM y patrones binarios:",
        estilos["Parrafo"]
    ))

    datos_esc3 = [
        [Paragraph("Pares K", estilos["TablaCabecera"]),
         Paragraph("Pares de Primos Gemelos", estilos["TablaCabecera"]),
         Paragraph("Último p", estilos["TablaCabecera"]),
         Paragraph("Patrón B<sub>2</sub> en RAM (Hex)", estilos["TablaCabecera"]),
         Paragraph("Valor Estimado B<sub>2</sub>", estilos["TablaCabecera"]),
         Paragraph("Ciclos FSM", estilos["TablaCabecera"])],
        [Paragraph("<b>K = 1</b>", estilos["TablaCeldaCentro"]), Paragraph("(3, 5)", estilos["TablaCelda"]), Paragraph("3", estilos["TablaCeldaCentro"]), Paragraph("<code>3FE1111111111111</code>", estilos["TablaCelda"]), Paragraph("0.5333333333333333", estilos["TablaCeldaCentro"]), Paragraph("17,950", estilos["TablaCeldaCentro"])],
        [Paragraph("<b>K = 2</b>", estilos["TablaCeldaCentro"]), Paragraph("(3, 5), (5, 7)", estilos["TablaCelda"]), Paragraph("5", estilos["TablaCeldaCentro"]), Paragraph("<code>3FEC09C09C09C09B</code>", estilos["TablaCelda"]), Paragraph("0.8761904761904761", estilos["TablaCeldaCentro"]), Paragraph("36,030", estilos["TablaCeldaCentro"])],
        [Paragraph("<b>K = 3</b>", estilos["TablaCeldaCentro"]), Paragraph("+ (11, 13)", estilos["TablaCelda"]), Paragraph("11", estilos["TablaCeldaCentro"]), Paragraph("<code>3FF0B4511685C572</code>", estilos["TablaCelda"]), Paragraph("1.0440226440226437", estilos["TablaCeldaCentro"]), Paragraph("54,730", estilos["TablaCeldaCentro"])],
        [Paragraph("<b>K = 5</b>", estilos["TablaCeldaCentro"]), Paragraph("+ (17, 19), (29, 31)", estilos["TablaCelda"]), Paragraph("29", estilos["TablaCeldaCentro"]), Paragraph("<code>3FF38E3510A6A83B</code>", estilos["TablaCelda"]), Paragraph("1.222218575518595", estilos["TablaCeldaCentro"]), Paragraph("92,850", estilos["TablaCeldaCentro"])],
        [Paragraph("<b>K = 8</b>", estilos["TablaCeldaCentro"]), Paragraph("+ (41, 43), (59, 61), (71, 73)", estilos["TablaCelda"]), Paragraph("71", estilos["TablaCeldaCentro"]), Paragraph("<code>3FF54BBC8DC0DF6F</code>", estilos["TablaCelda"]), Paragraph("1.3309903657190858", estilos["TablaCeldaCentro"]), Paragraph("163,420", estilos["TablaCeldaCentro"])],
    ]
    t_esc3 = Table(datos_esc3, colWidths=[1.6 * cm, 4.4 * cm, 1.6 * cm, 3.4 * cm, 3.9 * cm, 1.8 * cm])
    t_esc3.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, -1), (-1, -1), 1, black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    historia.append(t_esc3)
    historia.append(Paragraph("Tabla 6: Resultados experimentales del Escenario 3 (Estimación de la Constante de Brun B<sub>2</sub>).", estilos["Epigrafe"]))
    historia.append(PageBreak())

    # =========================================================================
    # PÁGINA 7: 5. EXPERIMENTACIÓN CUALITATIVA Y VISUAL (Escenarios 4, 5 y 6)
    # =========================================================================
    historia.append(Paragraph("5.4. Escenario 4: Manejo de Excepciones y Casos Especiales IEEE 754", estilos["H2"]))
    historia.append(Paragraph(
        "Se sometió la FPU a condiciones de borde patológicas y operaciones excepcionales:<br/>"
        "- <b>División por Cero (+1.0 / +0.0):</b> La FPU detecta divisor nulo y devuelve exactamente <code>0x7FF0000000000000</code> (+Inf) sin detener el procesador por fallo host.<br/>"
        "- <b>División por Cero con Signo (-1.0 / +0.0):</b> Aplica signo XOR produciendo <code>0xFFF0000000000000</code> (-Inf).<br/>"
        "- <b>Operaciones Indeterminadas (0.0 / 0.0 e Inf / Inf):</b> Producen el NaN canónico <code>0x7FF8000000000000</code>.<br/>"
        "- <b>Equivalencia de Ceros:</b> <code>FCMP(+0.0, -0.0)</code> retorna <code>0</code> (iguales), cumpliendo rigurosamente la norma.<br/>"
        "- <b>Comparaciones con NaN:</b> <code>FCMP(NaN, 1.0)</code> retorna <code>2</code> (relación no ordenada).",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("5.5. Escenario 5: Interoperabilidad de la Mesa de Vectores e Invarianza de Pila", estilos["H2"]))
    historia.append(Paragraph(
        "Para verificar la estabilidad del sistema ante llamadas encadenadas continuas, se ejecutó una secuencia continua invocando "
        "<code>VEC_FADD</code>, <code>VEC_FMUL</code>, <code>VEC_FSQRT</code> y <code>VEC_FBRUN</code>. El puntero de pila <code>SP</code> "
        "y el puntero base <code>BP</code> mantuvieron exactamente su valor inicial (<code>0x00204000</code>) al finalizar cada retorno <code>RET</code>, "
        "demostrando la ausencia total de fugas de pila (<i>stack leaks</i>) o corrupción de registros.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("5.6. Escenario 6: Validación Visual e Interactiva mediante el Panel FPU", estilos["H2"]))
    historia.append(Paragraph(
        "La interfaz gráfica del emulador Enigma-64 incorpora una pestaña reactiva de telemetría y calculadora FPU:",
        estilos["Parrafo"]
    ))

    if ruta_figura_fpu and ruta_figura_fpu.exists():
        historia.append(RLImage(str(ruta_figura_fpu), width=14.5 * cm, height=8.2 * cm))
        historia.append(Paragraph(
            "Figura 1: Panel interactivo de la FPU en Enigma-64: visor IEEE 754 de 64 bits y calculadora reactiva.",
            estilos["Epigrafe"]
        ))
    else:
        historia.append(Paragraph("[Figura 1: Mockup del Panel FPU interactivo]", estilos["Epigrafe"]))

    historia.append(Paragraph(
        "<b>Análisis de la Figura 1:</b> El panel exhibe el desglose en tiempo real de los 64 bits del formato Binary64:<br/>"
        "1. <b>Visor de Campos IEEE 754:</b> Diferencia claramente el bit 63 de signo, el bloque de 11 bits del exponente sesgado y los 52 bits "
        "de la mantisa fraccionaria, resaltando el bit implícito unitario normalizado.<br/>"
        "2. <b>Calculadora Reactiva:</b> Permite ingresar operandos en notación decimal o hexadecimal y despachar operaciones a través de "
        "<code>FPU_VECTORES</code> directamente sobre la CPU emulada.<br/>"
        "3. <b>Contraste Bit a Bit:</b> Compara automáticamente el resultado calculado en ensamblador contra la FPU del anfitrión, "
        "garantizando retroalimentación visual inmediata.",
        estilos["Parrafo"]
    ))
    historia.append(PageBreak())

    # =========================================================================
    # PÁGINA 8: 5.7 Métricas, 6. Conclusiones, 7. Recomendaciones y REFERENCIAS
    # =========================================================================
    historia.append(Paragraph("5.7. Métricas Consolidadas de la Suite de Pruebas Automatizadas", estilos["H2"]))
    historia.append(Paragraph(
        "La totalidad del sistema es evaluada de manera determinista mediante <b>471 pruebas automatizadas</b> con una tasa "
        "de éxito del <b>100%</b>:",
        estilos["Parrafo"]
    ))

    datos_pruebas = [
        [Paragraph("Módulo de Suite de Pruebas", estilos["TablaCabecera"]),
         Paragraph("Componente y Funcionalidad Evaluada", estilos["TablaCabecera"]),
         Paragraph("Pruebas", estilos["TablaCabecera"]),
         Paragraph("Tasa de Éxito", estilos["TablaCabecera"])],
        [Paragraph("tests/test_fbrun.py", estilos["TablaCelda"]), Paragraph("Primalidad entera, Brun K=0..8, vectores y RAM", estilos["TablaCelda"]), Paragraph("9", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_bateria_integracion.py", estilos["TablaCelda"]), Paragraph("FDIV, FCMP, 9 vectores e invarianza de pila", estilos["TablaCelda"]), Paragraph("11", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_fpu.py", estilos["TablaCelda"]), Paragraph("Núcleo FPU: empaquetado, desempaquetado, FADD y FSUB", estilos["TablaCelda"]), Paragraph("19", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_fmul.py", estilos["TablaCelda"]), Paragraph("FMUL: producto 128b, subnormales y casos IEEE", estilos["TablaCelda"]), Paragraph("7", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_fconv.py", estilos["TablaCelda"]), Paragraph("Conversiones INT64 <-> FLOAT64 y mesa de vectores", estilos["TablaCelda"]), Paragraph("20", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_fsqrt.py", estilos["TablaCelda"]), Paragraph("FSQRT: Newton-Raphson, exactos, irracionales y límites", estilos["TablaCelda"]), Paragraph("11", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_oraculo.py", estilos["TablaCelda"]), Paragraph("Oráculo IEEE 754, desgloses y métricas ULP", estilos["TablaCelda"]), Paragraph("16", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_ui_fpu.py", estilos["TablaCelda"]), Paragraph("Panel FPU interactivo, calculadora y visor de bits", estilos["TablaCelda"]), Paragraph("68", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("Tests de Arquitectura Base (Tarea 10)", estilos["TablaCelda"]), Paragraph("RAM, ALU, Registros, CPU FSM, MMIO, Cargador y UI", estilos["TablaCelda"]), Paragraph("310", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("<b>TOTAL INTEGRADO DEL PROYECTO</b>", estilos["TablaCabecera"]), Paragraph("<b>Sistema completo Enigma-64 con FPU IEEE 754</b>", estilos["TablaCabecera"]), Paragraph("<b>471</b>", estilos["TablaCabecera"]), Paragraph("<b>100% PASSED</b>", estilos["TablaCabecera"])],
    ]
    t_pruebas = Table(datos_pruebas, colWidths=[5.0 * cm, 6.5 * cm, 2.0 * cm, 3.2 * cm])
    t_pruebas.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, black),
        ("LINEBELOW", (0, 0), (-1, 0), 1, black),
        ("LINEABOVE", (0, -1), (-1, -1), 1, black),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    historia.append(t_pruebas)
    historia.append(Paragraph("Tabla 7: Distribución y cobertura formal de la suite de pruebas automatizadas de la Tarea 17.", estilos["Epigrafe"]))

    # =========================================================================
    # 6. CONCLUSIONES
    # =========================================================================
    historia.append(Spacer(1, 0.15 * cm))
    historia.append(Paragraph("6. CONCLUSIONES", estilos["H1"]))
    historia.append(Paragraph(
        "1. <b>Factibilidad de la Aritmética Real en Arquitecturas Básicas:</b> Se demostró con éxito la construcción integral de una Unidad "
        "de Punto Flotante de doble precisión (IEEE 754) programada exclusivamente en lenguaje ensamblador sobre un procesador elemental.<br/>"
        "2. <b>Validación Cruzada mediante Oráculo Matemático:</b> El desarrollo del oráculo formal en Python permitió una verificación diferencial "
        "exhaustiva de cada subrutina, certificando que los algoritmos de Newton-Raphson y de la Constante de Brun alcanzan precisiones dentro de "
        "tolerancias estrictas de 1 a 4 ULPs.<br/>"
        "3. <b>Disciplina de Interfaz y Mesa Canónica:</b> La implementación de la tabla de vectores <code>FPU_VECTORES</code> desacopló eficazmente "
        "el software de aplicación de las direcciones físicas de memoria, garantizando independencia de relocalización y una arquitectura limpia y modular.<br/>"
        "4. <b>Robustez Operativa:</b> La suite automatizada de 471 pruebas garantiza que el emulador Enigma-64 opera como una plataforma estable, "
        "determinista y lista para soportar compiladores de lenguajes de alto nivel.",
        estilos["Parrafo"]
    ))

    # =========================================================================
    # PÁGINA 9: REFERENCIAS BIBLIOGRÁFICAS (Página Separada)
    # =========================================================================
    historia.append(PageBreak())
    historia.append(Spacer(1, 0.4 * cm))
    historia.append(Paragraph("REFERENCIAS BIBLIOGRÁFICAS", estilos["H1"]))
    historia.append(HRFlowable(width="100%", thickness=1.0, color="black", spaceAfter=18, spaceBefore=4))

    referencias = [
        "[1] Peña, R. (2006). <i>De Euclides a JAVA: historia de los algoritmos y de los lenguajes de programación</i> (pág. 26). Ediciones Nívola.",
        "[2] IEEE Computer Society. (2008). <i>IEEE Standard for Floating-Point Arithmetic (IEEE Std 754-2008)</i>. IEEE.",
        "[3] Brun, V. (1919). La série 1/5 + 1/7 + 1/11 + 1/13 + ... où les dénominateurs sont nombres premiers jumeaux est convergente ou finie. <i>Bulletin des Sciences Mathématiques</i>, 43, 100-104, 124-128.",
        "[4] Hennessy, J. L., & Patterson, D. A. (2019). <i>Computer Architecture: A Quantitative Approach</i> (6th ed.). Morgan Kaufmann.",
        "[5] Goldberg, D. (1991). What Every Computer Scientist Should Know About Floating-Point Arithmetic. <i>ACM Computing Surveys</i>, 23(1), 5-48.",
        "[6] Ortiz Triviño, J. E. (2026). <i>Lineamientos Operativos y Lista Oficial de Tareas - Lenguajes de Programación</i>. Universidad Nacional de Colombia.",
    ]
    for ref in referencias:
        historia.append(Paragraph(ref, estilos["Referencia"]))

    # Construir documento
    doc.build(historia, canvasmaker=NumberedCanvas)
    print("Reporte PDF generado exitosamente en:", pdf_salida)


def main():
    base_dir = Path(__file__).resolve().parent.parent
    pdf_salida_oficial = base_dir / "Tarea_17_Reporte_Tecnico_Enigma64.pdf"

    print("Procesando mockup en escala de grises...")
    ruta_figura_fpu = preparar_figura_fpu_bw(base_dir)

    print("Compilando reporte formal académico Tarea 17 en PDF...")
    construir_reporte_pdf(pdf_salida_oficial, ruta_figura_fpu)
    print(f"Reporte técnico listo en:\n  - {pdf_salida_oficial}")


if __name__ == "__main__":
    main()
