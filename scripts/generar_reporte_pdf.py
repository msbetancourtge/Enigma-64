"""
Generador del Reporte Técnico Académico en PDF para la Tarea 10 (Enigma-64).
Universidad Nacional de Colombia - Lenguajes de Programación.
Estricto cumplimiento de especificaciones académicas en Blanco y Negro (B&W).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from PIL import Image, ImageOps

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable, Image as RLImage, KeepTogether, PageBreak, Paragraph,
    SimpleDocTemplate, Spacer, Table, TableStyle
)
from reportlab.pdfgen import canvas


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

        # Márgenes en puntos: 2.5 cm = 70.86 pt
        m_izq = 2.5 * cm
        m_der = letter[0] - 2.5 * cm
        m_sup = letter[1] - 1.8 * cm
        m_inf = 1.6 * cm

        if self._pageNumber > 1:
            # Encabezado formal superior
            self.drawString(
                m_izq, m_sup,
                "Universidad Nacional de Colombia · Lenguajes de Programación · Tarea 10: Enigma-64"
            )
            self.line(m_izq, m_sup - 4, m_der, m_sup - 4)

        # Pie de página inferior
        texto_pie = f"Página {self._pageNumber} de {total_paginas}"
        self.drawRightString(m_der, m_inf, texto_pie)
        self.drawString(m_izq, m_inf, "Memoria Técnica de Emulación de Arquitectura de Computadores")
        self.line(m_izq, m_inf + 10, m_der, m_inf + 10)

        self.restoreState()


def preparar_figuras_grises(src_dir: Path, out_dir: Path) -> dict[str, Path]:
    """Convierte capturas a escala de grises para estricta sobriedad B&W académica."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rutas_grises = {}

    mapeo = {
        "ram": "media_1790562093894.png",
        "algoritmos": "media_1790562870981.png",
        "cpu": "media_1790562887104.png",
        "mmio": "media_1790562894421.png",
        "registros": "media_1790562923914.png",
        "alu": "media_1790562930563.png",
    }

    for clave, nombre in mapeo.items():
        src_path = src_dir / nombre
        out_path = out_dir / f"{clave}_bw.png"
        if src_path.exists():
            im = Image.open(src_path)
            gray = ImageOps.grayscale(im)
            gray.save(out_path)
            rutas_grises[clave] = out_path
        else:
            rutas_grises[clave] = None

    return rutas_grises


def construir_estilos():
    base = getSampleStyleSheet()
    estilos = {}

    estilos["PortadaTitulo"] = ParagraphStyle(
        "PortadaTitulo",
        fontName="Times-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=14,
    )
    estilos["PortadaSubtitulo"] = ParagraphStyle(
        "PortadaSubtitulo",
        fontName="Times-Roman",
        fontSize=12,
        leading=16,
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    estilos["PortadaMetadatos"] = ParagraphStyle(
        "PortadaMetadatos",
        fontName="Times-Roman",
        fontSize=10,
        leading=14,
        alignment=TA_CENTER,
        spaceAfter=6,
    )
    estilos["H1"] = ParagraphStyle(
        "H1",
        fontName="Times-Bold",
        fontSize=13,
        leading=16,
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True,
    )
    estilos["H2"] = ParagraphStyle(
        "H2",
        fontName="Times-Bold",
        fontSize=11,
        leading=14,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True,
    )
    estilos["H3"] = ParagraphStyle(
        "H3",
        fontName="Times-BoldItalic",
        fontSize=10,
        leading=13,
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True,
    )
    estilos["Parrafo"] = ParagraphStyle(
        "Parrafo",
        fontName="Times-Roman",
        fontSize=9.5,
        leading=13.2,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    )
    estilos["Codigo"] = ParagraphStyle(
        "Codigo",
        fontName="Courier",
        fontSize=7.8,
        leading=9.8,
        alignment=TA_LEFT,
    )
    estilos["Epigrafe"] = ParagraphStyle(
        "Epigrafe",
        fontName="Times-Italic",
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        spaceBefore=4,
        spaceAfter=10,
    )
    estilos["TablaCelda"] = ParagraphStyle(
        "TablaCelda",
        fontName="Times-Roman",
        fontSize=8.5,
        leading=10.5,
        alignment=TA_LEFT,
    )
    estilos["TablaCeldaCentro"] = ParagraphStyle(
        "TablaCeldaCentro",
        fontName="Times-Roman",
        fontSize=8.5,
        leading=10.5,
        alignment=TA_CENTER,
    )
    estilos["TablaCabecera"] = ParagraphStyle(
        "TablaCabecera",
        fontName="Times-Bold",
        fontSize=8.5,
        leading=10.5,
        alignment=TA_CENTER,
    )
    return estilos


def construir_pdf(pdf_salida: Path, figuras: dict[str, Path]):
    margen = 2.5 * cm
    doc = SimpleDocTemplate(
        str(pdf_salida),
        pagesize=letter,
        leftMargin=margen,
        rightMargin=margen,
        topMargin=margen,
        bottomMargin=margen,
    )

    estilos = construir_estilos()
    historia = []
    ancho_util = letter[0] - 2 * margen

    # -----------------------------------------------------------------------
    # PORTADA FORMAL ACADÉMICA
    # -----------------------------------------------------------------------
    historia.append(Spacer(1, 1.2 * cm))
    historia.append(Paragraph("UNIVERSIDAD NACIONAL DE COLOMBIA", estilos["PortadaTitulo"]))
    historia.append(Paragraph("FACULTAD DE INGENIERÍA<br/>LENGUAJES DE PROGRAMACIÓN", estilos["PortadaSubtitulo"]))
    historia.append(HRFlowable(width="100%", thickness=1.5, color="black", spaceAfter=25, spaceBefore=5))

    historia.append(Spacer(1, 0.8 * cm))
    historia.append(Paragraph("REPORTE TÉCNICO DE IMPLEMENTACIÓN:<br/>TAREA 10 — EMULACIÓN DE SU COMPUTADOR", estilos["PortadaTitulo"]))
    historia.append(Paragraph("Especificación de Microarquitectura, Máquina de Estados Finitos Multiciclo y Sistema de Verificación Formal de Enigma-64", estilos["PortadaSubtitulo"]))

    historia.append(Spacer(1, 1.5 * cm))
    historia.append(Paragraph("<b>AUTORES:</b>", estilos["PortadaMetadatos"]))
    autores = [
        "Juan Sebastian Umaña Camacho (RAM & Buses)",
        "Tomas Felipe Garzón Gómez (Registros & ALU)",
        "Michael Stiven Betancourt Gelves (CPU & Unidad de Control FSM)",
        "Deibyd Santiago Barragán Gaitán (Cargador & Manipulador de Bits)",
        "Maicol Sebastian Olarte Ramirez (Interfaz Gráfica Modular Tkinter)",
        "Juan Luis Vergara Novoa (Visor/Editor RAM & MMIO)",
        "Alejandro Argüello Muñoz (Algoritmos de Verificación & Banco de Pruebas)",
    ]
    for autor in autores:
        historia.append(Paragraph(autor, estilos["PortadaMetadatos"]))

    historia.append(Spacer(1, 1.2 * cm))
    historia.append(Paragraph("<b>Docente Titular:</b> Asignatura Lenguajes de Programación (Grupo 2)", estilos["PortadaMetadatos"]))
    historia.append(Paragraph("Bogotá D.C., Colombia — Septiembre de 2026", estilos["PortadaMetadatos"]))
    historia.append(HRFlowable(width="100%", thickness=0.8, color="black", spaceAfter=15, spaceBefore=20))
    historia.append(PageBreak())

    # -----------------------------------------------------------------------
    # 1. MARCO TEÓRICO
    # -----------------------------------------------------------------------
    historia.append(Paragraph("1. MARCO TEÓRICO", estilos["H1"]))
    historia.append(Paragraph(
        "El computador <b>Enigma-64</b> se fundamenta en los principios de la arquitectura Von Neumann clásica, "
        "caracterizada por un subsistema unificado de almacenamiento primario donde residen indistintamente código ejecutable "
        "y datos operacionales. La longitud de palabra fundamental del sistema es de 64 bits (8 bytes), operando de manera nativa "
        "sobre un bus de datos de 64 bits y un espacio de direccionamiento lógico lineal de 2⁶⁴ bytes direccionable a nivel de byte. "
        "La implementación física acota este espacio a 4 GiB direccionables (0x00000000 a 0xFFFFFFFF), manteniendo rigurosa "
        "compatibilidad con la semántica de punteros y registros de 64 bits.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("1.1. Ordenamiento de Bytes (Endianness) y Formulación Matemática", estilos["H2"]))
    historia.append(Paragraph(
        "La arquitectura adopta estrictamente la convención <i>Big-Endian</i> para todas las operaciones de almacenamiento, "
        "transferencia por bus y decodificación de instrucciones. En este esquema, el byte más significativo (MSB, <i>Most Significant Byte</i>) "
        "se almacena en la dirección de memoria numérica más baja, mientras que el byte menos significativo (LSB, <i>Least Significant Byte</i>) "
        "se ubica en la dirección contigua más alta. Matemáticamente, para cualquier palabra escalar de 64 bits sin signo W denotada por:",
        estilos["Parrafo"]
    ))
    historia.append(Paragraph(
        "&nbsp;&nbsp;&nbsp;&nbsp;<i>W = ∑<sub>i=0</sub><sup>7</sup> b<sub>i</sub> · 256<sup>7 - i</sup></i> &nbsp;&nbsp;&nbsp;&nbsp; con <i>b<sub>i</sub> ∈ [0, 255]</i>",
        estilos["Parrafo"]
    ))
    historia.append(Paragraph(
        "la función de asignación en el espacio físico de memoria M(a) sobre una dirección base alineada A satisface de forma determinista: "
        "<i>M(A + i) = b<sub>i</sub></i> para todo índice <i>i ∈ {0, 1, ..., 7}</i>.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("1.2. Microarquitectura de Memoria: Intercalado en 8 Bancos y Alineación Natural", estilos["H2"]))
    historia.append(Paragraph(
        "Para emular fielmente la topología de hardware definida en la Tarea 9, cada palabra contigua de 64 bits se particiona en 8 bancos "
        "físicos independientes denominados <b>B0</b> a <b>B7</b>. La selección de banco se efectúa decodificando los 3 bits menos "
        "significativos del bus de direcciones físico <i>A[2:0]</i>:",
        estilos["Parrafo"]
    ))

    # Tabla de bancos
    datos_bancos = [
        [Paragraph("Banco", estilos["TablaCabecera"]),
         Paragraph("Líneas A[2:0]", estilos["TablaCabecera"]),
         Paragraph("Rango de Bits", estilos["TablaCabecera"]),
         Paragraph("Significado Funcional", estilos["TablaCabecera"])],
        [Paragraph("B0", estilos["TablaCeldaCentro"]), Paragraph("000", estilos["TablaCeldaCentro"]), Paragraph("Bits [7:0] (Byte 0)", estilos["TablaCeldaCentro"]), Paragraph("Byte más significativo (MSB) en Big-Endian", estilos["TablaCelda"])],
        [Paragraph("B1", estilos["TablaCeldaCentro"]), Paragraph("001", estilos["TablaCeldaCentro"]), Paragraph("Bits [15:8] (Byte 1)", estilos["TablaCeldaCentro"]), Paragraph("Segundo byte de la palabra de 64 bits", estilos["TablaCelda"])],
        [Paragraph("B2", estilos["TablaCeldaCentro"]), Paragraph("010", estilos["TablaCeldaCentro"]), Paragraph("Bits [23:16] (Byte 2)", estilos["TablaCeldaCentro"]), Paragraph("Tercer byte de la palabra de 64 bits", estilos["TablaCelda"])],
        [Paragraph("B3", estilos["TablaCeldaCentro"]), Paragraph("011", estilos["TablaCeldaCentro"]), Paragraph("Bits [31:24] (Byte 3)", estilos["TablaCeldaCentro"]), Paragraph("Cuarto byte de la palabra de 64 bits", estilos["TablaCelda"])],
        [Paragraph("B4", estilos["TablaCeldaCentro"]), Paragraph("100", estilos["TablaCeldaCentro"]), Paragraph("Bits [39:32] (Byte 4)", estilos["TablaCeldaCentro"]), Paragraph("Quinto byte de la palabra de 64 bits", estilos["TablaCelda"])],
        [Paragraph("B5", estilos["TablaCeldaCentro"]), Paragraph("101", estilos["TablaCeldaCentro"]), Paragraph("Bits [47:40] (Byte 5)", estilos["TablaCeldaCentro"]), Paragraph("Sexto byte de la palabra de 64 bits", estilos["TablaCelda"])],
        [Paragraph("B6", estilos["TablaCeldaCentro"]), Paragraph("110", estilos["TablaCeldaCentro"]), Paragraph("Bits [55:48] (Byte 6)", estilos["TablaCeldaCentro"]), Paragraph("Séptimo byte de la palabra de 64 bits", estilos["TablaCelda"])],
        [Paragraph("B7", estilos["TablaCeldaCentro"]), Paragraph("111", estilos["TablaCeldaCentro"]), Paragraph("Bits [63:56] (Byte 7)", estilos["TablaCeldaCentro"]), Paragraph("Byte menos significativo (LSB) en Big-Endian", estilos["TablaCelda"])],
    ]
    t_bancos = Table(datos_bancos, colWidths=[1.8 * cm, 2.5 * cm, 3.8 * cm, 7.5 * cm])
    t_bancos.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, "black"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, "black"),
        ("LINEBELOW", (0, -1), (-1, -1), 1, "black"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    historia.append(t_bancos)
    historia.append(Paragraph("Tabla 1: Decodificación microarquitectónica de los 8 bancos físicos de memoria mediante A[2:0].", estilos["Epigrafe"]))

    historia.append(Paragraph(
        "<b>Regla estricta de alineación natural:</b> Cualquier transferencia por el bus de datos de ancho <i>S ∈ {1, 2, 4, 8}</i> bytes "
        "exige que la dirección de origen o destino cumpla la condición matemática: <i>Dirección ≡ 0 (mod S)</i>. "
        "Si la condición se vulnera con la bandera de control activa, el subsistema emite inmediatamente la señal de control "
        "<b>STATUS_MISALIGNED</b>, inhibiendo la escritura o retornando un valor nulo de lectura.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("1.3. Subsistema de Entrada/Salida Mapeada en Memoria (MMIO)", estilos["H2"]))
    historia.append(Paragraph(
        "La arquitectura prescinde de instrucciones de E/S privilegiadas dedicadas (como IN/OUT en arquitecturas x86) y adopta el esquema "
        "<i>Memory-Mapped I/O</i>. El rango comprendido entre 0xFF000000 y 0xFFFFFFFF queda reservado para el subsistema de periféricos. "
        "Cualquier lectura o escritura en dicho segmento es interceptada por el decodificador de direcciones y enrutada hacia los controladores "
        "dedicados sin persistir en la matriz dinámica de RAM. Cada dispositivo dispone de una ventana de 4 KiB con cinco registros normalizados "
        "espaciados cada 8 bytes (CTRL, STATUS, DATA, ADDR, COUNT), garantizando accesos alineados de 64 bits.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("1.4. Unidad de Control Multiciclo y Prefetch Buffer", estilos["H2"]))
    historia.append(Paragraph(
        "La Unidad de Control ejecuta cada instrucción descomponiéndola en cinco fases microarquitectónicas secuenciales dentro de una "
        "Máquina de Estados Finitos (FSM): <b>FETCH</b> (recuperación de instrucción mediante prefetch buffer), <b>DECODE</b> (identificación "
        "de formato, opcode y direccionamiento de operandos), <b>EXECUTE</b> (cálculo en la ALU o evaluación de bifurcación condicional), "
        "<b>MEMORY</b> (acceso a lectura o escritura en RAM o MMIO) y <b>WRITE-BACK</b> (actualización de banco de registros o punteros). "
        "Para gestionar instrucciones de longitud variable (1 a 5 bytes) sin incurrir en transferencias redundantes ni fallos de alineación "
        "cuando una instrucción cruza la frontera de una palabra de 64 bits, la CPU implementa una cola FIFO de prebúsqueda de 16 bytes "
        "(<i>PrefetchBuffer</i>) que lee palabras dobles alineadas y entrega un flujo continuo de bytes decodificables.",
        estilos["Parrafo"]
    ))

    # -----------------------------------------------------------------------
    # 2. DESCRIPCIÓN Y JUSTIFICACIÓN DEL PROBLEMA
    # -----------------------------------------------------------------------
    historia.append(Spacer(1, 0.4 * cm))
    historia.append(Paragraph("2. DESCRIPCIÓN Y JUSTIFICACIÓN DEL PROBLEMA", estilos["H1"]))
    historia.append(Paragraph(
        "El desafío principal de ingeniería radica en construir un emulador determinista de nivel de sistema para un computador de 64 bits "
        "complejo, garantizando estricta fidelidad temporal e isomórfica con la especificación de hardware sin depender de bibliotecas nativas C/C++ "
        "ni motores de emulación externos. El sistema debe operar en un entorno de alto nivel interpretado (Python 3.10+) preservando "
        "un desacoplamiento absoluto entre módulos desarrollados por siete ingenieros distintos.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("2.1. Restricciones Técnicas y Computacionales Críticas", estilos["H2"]))
    historia.append(Paragraph(
        "<b>1. Gestión de memoria de 4 GiB sin sobrecosto espacial:</b> Instanciar un búfer contiguo de 4 GiB en memoria host "
        "exigiría 4 Gigabytes reales de memoria física del sistema anfitrión, colapsando entornos portátiles o sistemas de prueba en integración continua. "
        "La solución técnica implementada consiste en un modelo de <i>Paginación Dispersa (Sparse Virtual Paging)</i>: la memoria se segmenta en "
        "páginas de 4096 bytes (PAGE_SIZE = 4096). Un diccionario hash interno indexa únicamente las páginas que han recibido al menos una escritura "
        "real. Las lecturas sobre direcciones no inicializadas devuelven ceros lógicos sin asignar memoria host, acotando el consumo espacial "
        "a <i>O(P · 4096)</i>, donde P es el número finito de páginas efectivamente utilizadas.",
        estilos["Parrafo"]
    ))
    historia.append(Paragraph(
        "<b>2. Instrucciones de longitud variable y cruce arbitrario de fronteras:</b> Enigma-64 define 6 formatos de instrucción con longitudes "
        "de 1, 2, 3, 4 y 5 bytes. Una instrucción de 4 bytes ubicada por ejemplo en 0x00200006 se divide físicamente entre los bancos B6-B7 de la "
        "palabra 0x00200000 y los bancos B0-B1 de la palabra contigua 0x00200008. Sin un mecanismo de desacoplamiento, la CPU generaría excepciones "
        "de alineación continuas. La introducción del <i>PrefetchBuffer</i> amortiza las lecturas de memoria a accesos naturales de 64 bits y permite "
        "extraer secuencias arbitrarias de bytes en <i>O(1)</i>.",
        estilos["Parrafo"]
    ))
    historia.append(Paragraph(
        "<b>3. Aislamiento de capas y verificación estática (Regla de Independencia Modular):</b> Para impedir dependencias circulares y fugas de "
        "abstracción, se impusieron tres axiomas arquitectónicos inmutables: ningún módulo de hardware puede importar elementos de interfaz de usuario; "
        "ningún panel de la interfaz puede importar otro panel; y ningún panel gráfico puede invocar directamente un módulo de hardware sin la mediación "
        "de un adaptador de servicio (puerto). Esta restricción es fiscalizada automáticamente en la suite de pruebas mediante un analizador de "
        "Árbol de Sintaxis Abstracta (AST) sobre todos los módulos del código fuente.",
        estilos["Parrafo"]
    ))

    # -----------------------------------------------------------------------
    # 3. DISEÑO DE LA SOLUCIÓN Y ARQUITECTURA DEL SISTEMA
    # -----------------------------------------------------------------------
    historia.append(Spacer(1, 0.4 * cm))
    historia.append(Paragraph("3. DISEÑO DE LA SOLUCIÓN Y ARQUITECTURA DEL SISTEMA", estilos["H1"]))
    historia.append(Paragraph(
        "El sistema se organiza en cinco capas rigurosamente estratificadas: "
        "(1) <b>Capa de Hardware Físico:</b> módulos puros que modelan transistores, registros, buses y compuertas lógicas (enigma64.memoria, "
        "enigma64.registros, enigma64.alu, enigma64.cpu, enigma64.perifericos, enigma64.cargador). "
        "(2) <b>Capa de Servicios y Puertos:</b> adaptadores que implementan interfaces desacopladas con degradación elegante si un componente falta. "
        "(3) <b>Capa de Núcleo Visual (Core):</b> sistema de diseño Noctua, widgets sobre Canvas y bus de eventos asíncrono. "
        "(4) <b>Capa de Paneles:</b> controladores de vista independientes para cada subsistema. "
        "(5) <b>Capa Shell:</b> ventana orquestadora que integra las pestañas y la columna de contexto unificada.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("3.1. Modelo Estructural y Diagrama de Clases (PlantUML / Mermaid)", estilos["H2"]))
    historia.append(Paragraph(
        "A continuación se especifica la estructura relacional entre los componentes del computador y sus adaptadores de interfaz:",
        estilos["Parrafo"]
    ))

    codigo_clases = (
        "classDiagram\n"
        "    class RAMMemory {\n"
        "        -pages: Dict[int, bytearray]\n"
        "        +mem_read(address, size, check_align) (data, status)\n"
        "        +mem_write(address, data, size, check_align) status\n"
        "    }\n"
        "    class BancoRegistros {\n"
        "        -registros: List[int]\n"
        "        +pc: int\n"
        "        +sp: int\n"
        "        +sr: int\n"
        "        +leer(reg) int\n"
        "        +escribir(reg, valor) void\n"
        "    }\n"
        "    class ALU {\n"
        "        +operar(cod, opA, opB, carry_in) ResultadoALU\n"
        "    }\n"
        "    class CPU {\n"
        "        -fsm_fase: str\n"
        "        -prefetch: PrefetchBuffer\n"
        "        +paso() dict\n"
        "        +ejecutar(max_ciclos) dict\n"
        "    }\n"
        "    class Perifericos {\n"
        "        -pantalla: ControladorPantalla\n"
        "        +leer(dir, reg) int\n"
        "        +escribir(dir, reg, val) void\n"
        "    }\n"
        "    class Maquina {\n"
        "        +memoria: AdaptadorMemoria\n"
        "        +registros: AdaptadorRegistros\n"
        "        +alu: AdaptadorALU\n"
        "        +cargador: AdaptadorCargador\n"
        "        +cpu: AdaptadorCPU\n"
        "        +mmio: AdaptadorMMIO\n"
        "    }\n"
        "    Maquina --> RAMMemory : envuelve\n"
        "    Maquina --> BancoRegistros : envuelve\n"
        "    Maquina --> ALU : envuelve\n"
        "    Maquina --> CPU : envuelve\n"
        "    Maquina --> Perifericos : envuelve\n"
        "    CPU ..> RAMMemory : accede vía bus\n"
        "    CPU ..> BancoRegistros : actualiza\n"
        "    CPU ..> ALU : computa\n"
    )

    t_diag_clases = Table([
        [Paragraph(f"<pre>{codigo_clases}</pre>", estilos["Codigo"])],
    ], colWidths=[ancho_util])
    t_diag_clases.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, "black"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.append(t_diag_clases)
    historia.append(Paragraph("Diagrama 1: Modelo estructural de clases y relación entre hardware y adaptadores.", estilos["Epigrafe"]))

    historia.append(Paragraph("3.2. Dinámica del Sistema: Ciclo de Instrucción Multiciclo en la FSM", estilos["H2"]))
    historia.append(Paragraph(
        "El avance de la FSM de la CPU se modela en 5 fases síncronas. En cada transición se actualizan los micro-registros "
        "visibles en la interfaz de usuario:",
        estilos["Parrafo"]
    ))

    codigo_secuencia = (
        "sequenceDiagram\n"
        "    autonumber\n"
        "    participant CPU as Unidad de Control (FSM)\n"
        "    participant PB as PrefetchBuffer (16B)\n"
        "    participant RAM as RAMMemory (Buses)\n"
        "    participant ALU as ALU (64 bits)\n"
        "    participant RF as BancoRegistros\n"
        "\n"
        "    Note over CPU: Fase 1: FETCH\n"
        "    CPU->>PB: ensure(PC, tamaño_minimo)\n"
        "    PB->>RAM: mem_read(PC_alineado, 8 bytes)\n"
        "    RAM-->>PB: palabra de 64 bits (Big-Endian)\n"
        "    PB-->>CPU: bytes de instrucción (IR)\n"
        "    Note over CPU: Fase 2: DECODE\n"
        "    CPU->>CPU: decodificar opcode, formato y registros\n"
        "    CPU->>RF: leer registros fuente -> Latch A, Latch B\n"
        "    Note over CPU: Fase 3: EXECUTE\n"
        "    CPU->>ALU: operar(opcode, Latch A, Latch B)\n"
        "    ALU-->>CPU: acumulador Z y banderas Z, N, C, V\n"
        "    Note over CPU: Fase 4: MEMORY\n"
        "    opt Si es instrucción LOAD / STORE\n"
        "        CPU->>RAM: mem_read/write(MAR, MDR)\n"
        "    end\n"
        "    Note over CPU: Fase 5: WRITE-BACK\n"
        "    CPU->>RF: escribir registro destino con Z o MDR\n"
        "    CPU->>RF: actualizar PC (+ longitud) y SR (banderas)\n"
    )
    t_diag_sec = Table([
        [Paragraph(f"<pre>{codigo_secuencia}</pre>", estilos["Codigo"])],
    ], colWidths=[ancho_util])
    t_diag_sec.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, "black"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.append(t_diag_sec)
    historia.append(Paragraph("Diagrama 2: Diagrama de secuencia formal de las 5 fases de la FSM multiciclo.", estilos["Epigrafe"]))

    historia.append(Paragraph("3.3. Algoritmos Críticos y Análisis de Complejidad", estilos["H2"]))
    historia.append(Paragraph(
        "<b>Algoritmo 1: Validación de Acceso y Lectura Paginada con Arbitraje de Bus.</b><br/>"
        "Permite recuperar escalares de 1, 2, 4 u 8 bytes en Big-Endian verificando la alineación natural y cruzando límites de página.",
        estilos["Parrafo"]
    ))

    pseudo_memoria = (
        "ALGORITMO LecturaMemoria(Direccion: Entero64, Tamano: Entero, VerificarAlineacion: Booleano)\n"
        "  ENTRADA: Direccion de 64 bits, Tamano en {1, 2, 4, 8}, Booleano de control de alineacion\n"
        "  SALIDA : Tupla (Dato64, EstadoBus)\n"
        "  1. SI Direccion < 0 O (Direccion >> 32) != 0 ENTONCES\n"
        "  2.     RETORNAR (NULO, STATUS_ADDR_FAULT)\n"
        "  3. SI (Direccion >> 24) == 0xFF ENTONCES\n"
        "  4.     RETORNAR (NULO, STATUS_MMIO)\n"
        "  5. SI VerificarAlineacion Y (Direccion MOD Tamano != 0) ENTONCES\n"
        "  6.     RETORNAR (NULO, STATUS_MISALIGNED)\n"
        "  7. BufferBytes <- CrearArreglo(Tamano, inicial=0)\n"
        "  8. PARA cada desplazamiento i DESDE 0 HASTA Tamano - 1 HACER:\n"
        "  9.     DirActual <- Direccion + i\n"
        " 10.     IndicePagina <- DirActual DIV 4096\n"
        " 11.     OffsetPagina <- DirActual MOD 4096\n"
        " 12.     SI IndicePagina EXISTE EN TablaPaginas ENTONCES:\n"
        " 13.         BufferBytes[i] <- TablaPaginas[IndicePagina][OffsetPagina]\n"
        " 14.     SINO:\n"
        " 15.         BufferBytes[i] <- 0\n"
        " 16. Dato64 <- ConvertirBigEndianAEntero(BufferBytes)\n"
        " 17. RETORNAR (Dato64, STATUS_READY)\n"
    )
    t_pseudo1 = Table([
        [Paragraph(f"<pre>{pseudo_memoria}</pre>", estilos["Codigo"])],
    ], colWidths=[ancho_util])
    t_pseudo1.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, "black"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    historia.append(t_pseudo1)
    historia.append(Paragraph(
        "<b>Complejidad Algoritmo 1:</b> Temporal: <i>O(Tamano) = O(1)</i> en media, dado que <i>Tamano ≤ 8</i> y la búsqueda "
        "en la tabla hash de páginas es <i>O(1)</i>. Espacial: <i>O(1)</i> auxiliar por lectura; <i>O(P · 4096)</i> global en el sistema "
        "para P páginas instanciadas.",
        estilos["Parrafo"]
    ))

    # -----------------------------------------------------------------------
    # 4. DOCUMENTACIÓN DE IMPLEMENTACIÓN Y MANUALES
    # -----------------------------------------------------------------------
    historia.append(Spacer(1, 0.4 * cm))
    historia.append(Paragraph("4. DOCUMENTACIÓN DE IMPLEMENTACIÓN Y MANUALES", estilos["H1"]))

    historia.append(Paragraph("4.1. Manual Técnico: Estructura del Código y Patrones de Diseño", estilos["H2"]))
    historia.append(Paragraph(
        "La arquitectura del código fuente se organiza bajo el principio de responsabilidad única en el paquete <code>enigma64</code>:",
        estilos["Parrafo"]
    ))

    datos_modulos = [
        [Paragraph("Módulo", estilos["TablaCabecera"]),
         Paragraph("Responsable", estilos["TablaCabecera"]),
         Paragraph("Rol Técnico y Patrones Aplicados", estilos["TablaCabecera"])],
        [Paragraph("enigma64/memoria.py", estilos["TablaCelda"]), Paragraph("Integrante 1", estilos["TablaCeldaCentro"]), Paragraph("Controlador de memoria física y subsistema de buses. Sparse Paging y control de alineación.", estilos["TablaCelda"])],
        [Paragraph("enigma64/registros.py", estilos["TablaCelda"]), Paragraph("Integrante 2", estilos["TablaCeldaCentro"]), Paragraph("Banco de 32 registros de 64 bits con cableado estricto a tierra de R0 y banderas en SR.", estilos["TablaCelda"])],
        [Paragraph("enigma64/alu.py", estilos["TablaCelda"]), Paragraph("Integrante 2", estilos["TablaCeldaCentro"]), Paragraph("Unidad Aritmético-Lógica de 64 bits. Complemento a dos, sumador y evaluador de overflow V.", estilos["TablaCelda"])],
        [Paragraph("enigma64/cargador.py", estilos["TablaCelda"]), Paragraph("Integrante 4", estilos["TablaCeldaCentro"]), Paragraph("Cargador binario de formato .e64 y rutinas de manipulación bit a bit a nivel de byte.", estilos["TablaCelda"])],
        [Paragraph("enigma64/cpu.py", estilos["TablaCelda"]), Paragraph("Integrante 3", estilos["TablaCeldaCentro"]), Paragraph("Unidad de Control con FSM multiciclo (5 fases), PrefetchBuffer y decodificador.", estilos["TablaCelda"])],
        [Paragraph("enigma64/perifericos.py", estilos["TablaCelda"]), Paragraph("Integrante 6", estilos["TablaCeldaCentro"]), Paragraph("Dispatcher MMIO y ControladorPantalla CRT (0xFF001000) con buffer de matriz 2D.", estilos["TablaCelda"])],
        [Paragraph("enigma64/programas.py", estilos["TablaCelda"]), Paragraph("Integrante 7", estilos["TablaCeldaCentro"]), Paragraph("Transcripción binaria y exportación formal de los programas Factorial, Euclides y Fibonacci.", estilos["TablaCelda"])],
        [Paragraph("enigma64/ui/", estilos["TablaCelda"]), Paragraph("Integrante 5", estilos["TablaCeldaCentro"]), Paragraph("GUI modular Noctua en Tkinter puro, bus de eventos reactivo y aislamiento AST.", estilos["TablaCelda"])],
    ]
    t_modulos = Table(datos_modulos, colWidths=[4.0 * cm, 3.0 * cm, 8.5 * cm])
    t_modulos.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, "black"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, "black"),
        ("LINEBELOW", (0, -1), (-1, -1), 1, "black"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    historia.append(t_modulos)
    historia.append(Paragraph("Tabla 2: Estructura técnica de módulos de software y asignación de responsabilidades de ingeniería.", estilos["Epigrafe"]))

    historia.append(Paragraph(
        "<b>Patrones de Diseño Implementados:</b><br/>"
        "• <b>Adapter (Adaptador):</b> Cada módulo de hardware es encapsulado en un adaptador dentro de <code>enigma64.ui.servicios</code>. "
        "Si un módulo de hardware no se encuentra presente, el adaptador proporciona una interfaz neutra con fallbacks seguros sin provocar caídas.<br/>"
        "• <b>Observer / Publish-Subscribe:</b> La clase <code>BusEventos</code> permite que los paneles publiquen y escuchen eventos del sistema "
        "(ej. IR_A_DIRECCION, PROGRAMA_CARGADO, MMIO_ESCRITO) sin conocerse ni depender entre sí.<br/>"
        "• <b>Factory (Fábrica):</b> La función <code>construir_maquina()</code> en <code>fabrica.py</code> instancia y conecta una sola vez "
        "la RAM, el banco de registros, la ALU, el cargador, la CPU y los controladores de periféricos.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("4.2. Manual de Usuario y Despliegue del Sistema", estilos["H2"]))
    historia.append(Paragraph(
        "<b>Requisitos del Sistema:</b> Intérprete Python versión 3.10 o superior (validado formalmente en Python 3.13.5 sobre Windows 10/11 y Linux x86_64). "
        "Módulo gráfico estándar <code>tkinter</code> habilitado en el entorno de ejecución.<br/>"
        "<b>Instrucciones de Despliegue:</b><br/>"
        "1. Clonar el repositorio y situarse en la raíz del proyecto:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<code>cd Enigma-64</code><br/>"
        "2. Lanzar la interfaz gráfica integral del emulador:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<code>python main.py</code> &nbsp;&nbsp;(o alternativamente: <code>python -m enigma64</code>)<br/>"
        "3. Ejecutar la suite de pruebas automatizadas completa:<br/>"
        "&nbsp;&nbsp;&nbsp;&nbsp;<code>python -m pytest</code>",
        estilos["Parrafo"]
    ))

    # -----------------------------------------------------------------------
    # 5. EXPERIMENTACIÓN, PRUEBAS Y ANÁLISIS DE RESULTADOS
    # -----------------------------------------------------------------------
    historia.append(PageBreak())
    historia.append(Paragraph("5. EXPERIMENTACIÓN, PRUEBAS Y ANÁLISIS DE RESULTADOS", estilos["H1"]))
    historia.append(Paragraph(
        "A continuación se documentan cuatro escenarios de experimentación rigurosa sobre el emulador Enigma-64, "
        "contrastando las especificaciones teóricas de la Tarea 9 con los resultados computacionales reales obtenidos en la máquina.",
        estilos["Parrafo"]
    ))

    # Escenario 1
    historia.append(Paragraph("5.1. Escenario 1: Validación del Algoritmo 1 — Factorial de N (5! = 120)", estilos["H2"]))
    historia.append(Paragraph(
        "El programa calcula el factorial de un escalar almacenado en memoria mediante un ciclo iterativo multiplicativo decremental. "
        "<b>Parámetros de ejecución:</b> Dirección base de carga de código: <code>0x00200000</code>. Dirección de entrada de datos: "
        "<code>0x00201000</code> inicializada con el valor entero 5. Longitud del código binario: 41 bytes. "
        "Dirección esperada de resultado: <code>0x00201008</code> con valor esperado 120 (0x0000000000000078).",
        estilos["Parrafo"]
    ))

    if figuras.get("algoritmos"):
        historia.append(RLImage(str(figuras["algoritmos"]), width=15.5 * cm, height=8.8 * cm))
        historia.append(Paragraph("Figura 1: Verificación de ejecución del Algoritmo Factorial (5! = 120) en el panel de Algoritmos.", estilos["Epigrafe"]))

    historia.append(Paragraph(
        "<b>Análisis de Resultados Escenario 1:</b> La CPU ejecutó la secuencia completa deteniéndose ante la instrucción HLT (0x00). "
        "Como se observa en el panel, la dirección de memoria 0x00201008 fue leída mediante acceso natural de 64 bits, reportando "
        "exactamente el valor escalar 120 (0x78). La traza del bus registró en tiempo real las transiciones: "
        "<code>algoritmos.ejecucion terminada -> algoritmos.verificado 5! = 120</code>.",
        estilos["Parrafo"]
    ))

    if figuras.get("registros"):
        historia.append(RLImage(str(figuras["registros"]), width=15.5 * cm, height=8.8 * cm))
        historia.append(Paragraph("Figura 2: Estado final del Banco de Registros tras la ejecución del Factorial de 5.", estilos["Epigrafe"]))

    historia.append(Paragraph(
        "El análisis del banco de registros (Figura 2) confirma el comportamiento microarquitectónico esperado: "
        "el registro <b>R1</b> almacena la dirección base de datos <code>0x00201000</code>; el registro <b>R3</b> retiene el valor "
        "acumulado final <code>0x78</code> (120 en decimal); el <b>PC</b> se detiene en <code>0x00200029</code> (longitud de 41 bytes) "
        "y el registro de estado <b>SR</b> activa la bandera <b>Z (Zero)</b>, demostrando que el bucle finalizó cuando la comparación "
        "decremental alcanzó cero.",
        estilos["Parrafo"]
    ))

    # Escenario 2 y 3
    historia.append(PageBreak())
    historia.append(Paragraph("5.2. Escenario 2: Validación del Algoritmo 2 — Máximo Común Divisor de Euclides", estilos["H2"]))
    historia.append(Paragraph(
        "El Algoritmo de Euclides calcula el máximo común divisor entre dos enteros positivos mediante restas sucesivas y bifurcaciones "
        "condicionales relativas. <b>Parámetros de ejecución:</b> Dirección de código: <code>0x00200100</code> (50 bytes). "
        "Entradas en RAM: <code>Mem[0x00202000] = 48</code> y <code>Mem[0x00202008] = 18</code>. "
        "Dirección de salida: <code>Mem[0x00202010]</code>.<br/>"
        "<b>Resultado experimental:</b> La CPU ejecutó las bifurcaciones relativas con salto condicional JZ/JNZ, alcanzando el estado HLT "
        "y escribiendo el valor escalar <b>6</b> en la dirección <code>0x00202010</code>, validando la lógica de comparación CMP y saltos relativos de 16 bits.",
        estilos["Parrafo"]
    ))

    historia.append(Paragraph("5.3. Escenario 3: Validación del Algoritmo 3 — Sucesión de Fibonacci en Vector RAM", estilos["H2"]))
    historia.append(Paragraph(
        "El Algoritmo de Fibonacci genera los primeros 7 términos de la serie y los escribe secuencialmente en un arreglo de 64 bits en RAM. "
        "<b>Parámetros de ejecución:</b> Dirección de código: <code>0x00200200</code> (63 bytes). "
        "Vector de salida en RAM: 7 palabras contiguas a partir de <code>0x00203000</code>.<br/>"
        "<b>Resultado experimental:</b> La verificación automática confirmó la generación exacta de la secuencia: "
        "<code>[0, 1, 1, 2, 3, 5, 8]</code> en las direcciones <code>0x00203000</code> hasta <code>0x00203030</code>, evidenciando "
        "el direccionamiento indexado mediante registros base y desplazamientos múltiplos de 8 bytes.",
        estilos["Parrafo"]
    ))

    # Escenario 4
    historia.append(Paragraph("5.4. Escenario 4: Manejo de Excepciones de Bus (Lectura Desalineada) y Control MMIO", estilos["H2"]))
    historia.append(Paragraph(
        "Para verificar la robustez del subsistema de buses y la lógica de protección de hardware, se configuró un acceso intencionalmente "
        "inválido desde la interfaz gráfica: lectura de <b>8 bytes</b> en la dirección impar <b>0x00200001</b>.",
        estilos["Parrafo"]
    ))

    if figuras.get("ram"):
        historia.append(RLImage(str(figuras["ram"]), width=15.5 * cm, height=8.8 * cm))
        historia.append(Paragraph("Figura 3: Detección y rechazo de acceso desalineado (MISALIGNED) en el visor de memoria física.", estilos["Epigrafe"]))

    historia.append(Paragraph(
        "<b>Análisis de la Figura 3:</b> Al solicitar la lectura de 64 bits en 0x00200001 con la opción de verificación activa, "
        "el controlador de memoria física detectó que <i>0x00200001 ≢ 0 (mod 8)</i>. De forma inmediata, el hardware rechazó la "
        "operación, encendió el diodo indicador de control <b>MISALIGNED</b> y registró en la traza: "
        "<code>MISALIGNED · lectura de 8 B en 0x00200001 rechazada por el bus</code>. Esto demuestra que la emulación no es un mero "
        "lector de arreglos en memoria host, sino que replica la disciplina estricta de un bus síncrono de computador.",
        estilos["Parrafo"]
    ))

    if figuras.get("mmio"):
        historia.append(RLImage(str(figuras["mmio"]), width=15.5 * cm, height=8.8 * cm))
        historia.append(Paragraph("Figura 4: Panel de E/S Mapeada en Memoria (MMIO) y Controlador de Pantalla CRT en 0xFF001000.", estilos["Epigrafe"]))

    historia.append(Paragraph(
        "Asimismo, la Figura 4 evidencia el funcionamiento del controlador de pantalla en <code>0xFF001000</code>. "
        "Las transferencias dirigidas a <code>DATA</code> (0xFF001010) actualizan la matriz de texto del terminal CRT y avanzan "
        "los registros <code>ADDR</code> y <code>COUNT</code>, confirmando la interoperabilidad total entre CPU, memoria y periféricos.",
        estilos["Parrafo"]
    ))

    # Suite automatizada
    historia.append(Paragraph("5.5. Métricas de la Suite de Pruebas Automatizadas", estilos["H2"]))
    historia.append(Paragraph(
        "La totalidad del sistema es evaluada de manera determinista mediante <b>260 pruebas unitarias automatizadas</b> con una tasa "
        "de éxito del <b>100%</b> y un tiempo de ejecución total inferior a 0.7 segundos:",
        estilos["Parrafo"]
    ))

    datos_pruebas = [
        [Paragraph("Archivo de Suite de Pruebas", estilos["TablaCabecera"]),
         Paragraph("Componente Evaluado", estilos["TablaCabecera"]),
         Paragraph("Pruebas", estilos["TablaCabecera"]),
         Paragraph("Tasa de Éxito", estilos["TablaCabecera"])],
        [Paragraph("tests/test_memoria.py", estilos["TablaCelda"]), Paragraph("RAM física, paginación dispersa y alineación", estilos["TablaCelda"]), Paragraph("22", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_registros_alu.py", estilos["TablaCelda"]), Paragraph("Banco de registros de 64 bits y operaciones ALU", estilos["TablaCelda"]), Paragraph("38", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_cargador.py", estilos["TablaCelda"]), Paragraph("Cargador .e64 y manipulación de bits", estilos["TablaCelda"]), Paragraph("21", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_cpu.py", estilos["TablaCelda"]), Paragraph("FSM multiciclo, prefetch buffer y conjunto ISA", estilos["TablaCelda"]), Paragraph("16", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_perifericos.py", estilos["TablaCelda"]), Paragraph("Dispatcher MMIO y Controlador de Pantalla CRT", estilos["TablaCelda"]), Paragraph("16", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_algoritmos.py", estilos["TablaCelda"]), Paragraph("Programas Factorial, Euclides y Fibonacci", estilos["TablaCelda"]), Paragraph("16", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_ui_visor_ram_mmio.py", estilos["TablaCelda"]), Paragraph("Lógica de banco físico y edición en vivo de bits", estilos["TablaCelda"]), Paragraph("8", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_ui_aislamiento.py", estilos["TablaCelda"]), Paragraph("Aislamiento estricto de capas mediante AST", estilos["TablaCelda"]), Paragraph("29", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_ui_modulos_nuevos.py", estilos["TablaCelda"]), Paragraph("Contratos de integración y fábrica de servicios", estilos["TablaCelda"]), Paragraph("42", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("tests/test_ui_nucleo.py", estilos["TablaCelda"]), Paragraph("Formatos numéricos, endianness y bus de eventos", estilos["TablaCelda"]), Paragraph("52", estilos["TablaCeldaCentro"]), Paragraph("100% OK", estilos["TablaCeldaCentro"])],
        [Paragraph("<b>TOTAL INTEGRADO</b>", estilos["TablaCabecera"]), Paragraph("<b>Emulador completo Enigma-64</b>", estilos["TablaCabecera"]), Paragraph("<b>260</b>", estilos["TablaCabecera"]), Paragraph("<b>100% PASSED</b>", estilos["TablaCabecera"])],
    ]
    t_pruebas = Table(datos_pruebas, colWidths=[5.2 * cm, 5.8 * cm, 2.0 * cm, 2.5 * cm])
    t_pruebas.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 1, "black"),
        ("LINEBELOW", (0, 0), (-1, 0), 1, "black"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, "black"),
        ("LINEBELOW", (0, -1), (-1, -1), 1.5, "black"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))
    historia.append(t_pruebas)
    historia.append(Paragraph("Tabla 3: Distribución y tasa de aprobación de la batería de pruebas automatizadas.", estilos["Epigrafe"]))

    # -----------------------------------------------------------------------
    # REFERENCIAS BIBLIOGRÁFICAS
    # -----------------------------------------------------------------------
    historia.append(Spacer(1, 0.4 * cm))
    historia.append(Paragraph("REFERENCIAS BIBLIOGRÁFICAS", estilos["H1"]))
    referencias = [
        "[1] Hennessy, J. L., & Patterson, D. A. (2019). <i>Computer Architecture: A Quantitative Approach</i> (6th ed.). Morgan Kaufmann.",
        "[2] Tanenbaum, A. S., & Austin, T. (2013). <i>Structured Computer Organization</i> (6th ed.). Pearson.",
        "[3] Stallings, W. (2016). <i>Computer Organization and Architecture: Designing for Performance</i> (10th ed.). Pearson.",
        "[4] Gamma, E., Helm, R., Johnson, R., & Vlissides, J. (1994). <i>Design Patterns: Elements of Reusable Object-Oriented Software</i>. Addison-Wesley.",
        "[5] Documentación Técnica de Asignatura. (2026). <i>Guía de Microarquitectura e ISA de Enigma-64 (Tarea 9 y Tarea 10)</i>. Universidad Nacional de Colombia.",
    ]
    for ref in referencias:
        historia.append(Paragraph(ref, estilos["Parrafo"]))

    # Construir documento final
    doc.build(historia, canvasmaker=NumberedCanvas)
    print("PDF generado exitosamente en:", pdf_salida)


def main():
    base_dir = Path(__file__).resolve().parent.parent
    src_img_dir = Path(r"C:\Users\Usuario\.gemini\antigravity\brain\df14c50b-f120-4ea8-99dd-3ec77edf14cb\.user_uploaded")
    out_img_dir = base_dir / "docs" / "figuras"
    pdf_salida = base_dir / "Tarea_10_Reporte_Tecnico_Enigma64.pdf"

    print("Procesando capturas en escala de grises...")
    figuras = preparar_figuras_grises(src_img_dir, out_img_dir)

    print("Compilando reporte formal en PDF...")
    construir_pdf(pdf_salida, figuras)


if __name__ == "__main__":
    main()
