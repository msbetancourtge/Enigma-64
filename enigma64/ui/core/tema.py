"""
Sistema de diseno de Noctua Systems para el emulador Enigma-64.

Este modulo es la unica fuente de verdad visual de la interfaz: paleta,
tipografias, metricas y estilos ttk. Ningun panel define colores por su
cuenta, de modo que cambiar la identidad de la marca se hace aqui y se
propaga a toda la aplicacion.

Identidad:
  Noctua es la lechuza: vigilancia nocturna. De ahi el fondo de noche
  profunda, el ambar de los ojos como color de marca y el cian de los datos
  en transito por los buses.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

from tkinter import font as tkfont, ttk
from typing import Dict, Iterable, Sequence, Tuple

# ---------------------------------------------------------------------------
# Identidad de marca
# ---------------------------------------------------------------------------

EMPRESA = "NOCTUA SYSTEMS"
COMPUTADOR = "ENIGMA-64"
LEMA = "Arquitectura Von Neumann  ·  Palabra de 64 bits  ·  Big-Endian"


# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------

PALETA: Dict[str, str] = {
    # Superficies, de la mas profunda a la mas elevada
    "abismo": "#0B0E14",
    "noche": "#11151F",
    "elevado": "#171E2B",
    "elevado_alto": "#1E2636",
    "seleccion": "#22314A",
    # Trazos
    "borde": "#263041",
    "borde_sutil": "#1B2231",
    # Texto
    "texto": "#E6ECF5",
    "texto_tenue": "#8494AC",
    "texto_debil": "#5A6880",
    # Acentos
    "ambar": "#F2B138",        # marca Noctua (ojos de la lechuza)
    "ambar_oscuro": "#8A6520",
    "cian": "#3FC9D6",         # datos y direcciones en los buses
    "cian_oscuro": "#1E5C63",
    "violeta": "#A98BF5",      # espacio de perifericos (MMIO)
    # Semantica
    "ok": "#4FD07A",
    "alerta": "#FFB454",
    "fallo": "#FF5C6C",
}

#: Color con el que se pinta cada senal del bus de control de la RAM.
COLOR_POR_ESTADO: Dict[str, str] = {
    "READY": PALETA["ok"],
    "MISALIGNED": PALETA["alerta"],
    "MMIO": PALETA["violeta"],
    "ADDR_FAULT": PALETA["fallo"],
}

#: Color por severidad de los mensajes que viajan en el bus de eventos.
COLOR_POR_SEVERIDAD: Dict[str, str] = {
    "info": PALETA["texto_tenue"],
    "dato": PALETA["cian"],
    "exito": PALETA["ok"],
    "aviso": PALETA["alerta"],
    "error": PALETA["fallo"],
}


# ---------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------

MARGEN = 10
MARGEN_CHICO = 6
RADIO_TARJETA = 8


# ---------------------------------------------------------------------------
# Tipografias
# ---------------------------------------------------------------------------

_CANDIDATAS_MONO: Sequence[str] = (
    "JetBrains Mono",
    "Cascadia Mono",
    "Fira Mono",
    "Ubuntu Mono",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "Consolas",
    "Courier New",
)

_CANDIDATAS_SANS: Sequence[str] = (
    "Inter",
    "Segoe UI",
    "Ubuntu",
    "Cantarell",
    "DejaVu Sans",
    "Liberation Sans",
    "Helvetica",
)

_FAMILIAS: Dict[str, str] = {}


def _primera_disponible(candidatas: Iterable[str], instaladas: set, respaldo: str) -> str:
    for nombre in candidatas:
        if nombre in instaladas:
            return nombre
    return respaldo


def _resolver_familias() -> None:
    """Elige la mejor tipografia instalada. Requiere que exista una raiz Tk."""
    if _FAMILIAS:
        return
    try:
        instaladas = set(tkfont.families())
    except Exception:  # pragma: no cover - solo si Tk no esta inicializado
        instaladas = set()
    _FAMILIAS["mono"] = _primera_disponible(_CANDIDATAS_MONO, instaladas, "Courier")
    _FAMILIAS["sans"] = _primera_disponible(_CANDIDATAS_SANS, instaladas, "Helvetica")


def mono(tam: int = 10, negrita: bool = False) -> Tuple[str, int, str]:
    """Tipografia monoespaciada, para todo lo que sea hexadecimal o binario."""
    _resolver_familias()
    # Tk exige un tamano entero; redondear aqui evita un TclError por sorpresa.
    return (_FAMILIAS["mono"], round(tam), "bold" if negrita else "normal")


def sans(tam: int = 10, negrita: bool = False) -> Tuple[str, int, str]:
    """Tipografia de interfaz, para titulos, botones y textos de ayuda."""
    _resolver_familias()
    # Tk exige un tamano entero; redondear aqui evita un TclError por sorpresa.
    return (_FAMILIAS["sans"], round(tam), "bold" if negrita else "normal")


# ---------------------------------------------------------------------------
# Estilos ttk
# ---------------------------------------------------------------------------

_APLICADO = {"si": False}


def aplicar_tema(raiz) -> ttk.Style:
    """
    Instala el tema Noctua sobre la raiz Tk indicada.

    Es idempotente: los estilos ttk son globales al interprete, asi que
    llamarlo desde varias ventanas (por ejemplo al abrir un panel suelto) no
    duplica trabajo ni rompe nada.
    """
    _resolver_familias()
    estilo = ttk.Style(raiz)

    try:
        raiz.configure(background=PALETA["abismo"])
    except Exception:  # pragma: no cover - raices no configurables
        pass

    if _APLICADO["si"]:
        return estilo

    # 'clam' es el unico tema incorporado que permite recolorear casi todo.
    estilo.theme_use("clam")

    p = PALETA

    estilo.configure(".", background=p["noche"], foreground=p["texto"],
                     fieldbackground=p["elevado"], bordercolor=p["borde"],
                     lightcolor=p["borde"], darkcolor=p["borde"],
                     font=sans(10))

    # -- contenedores -------------------------------------------------------
    estilo.configure("TFrame", background=p["noche"])
    estilo.configure("Abismo.TFrame", background=p["abismo"])
    estilo.configure("Tarjeta.TFrame", background=p["elevado"])
    estilo.configure("TarjetaAlta.TFrame", background=p["elevado_alto"])
    estilo.configure("Separador.TFrame", background=p["borde"])

    # -- textos -------------------------------------------------------------
    estilo.configure("TLabel", background=p["noche"], foreground=p["texto"])
    estilo.configure("Tarjeta.TLabel", background=p["elevado"], foreground=p["texto"])
    estilo.configure("Tenue.TLabel", background=p["elevado"], foreground=p["texto_tenue"],
                     font=sans(9))
    estilo.configure("TenueNoche.TLabel", background=p["noche"], foreground=p["texto_tenue"],
                     font=sans(9))
    estilo.configure("Titulo.TLabel", background=p["elevado"], foreground=p["texto"],
                     font=sans(11, True))
    estilo.configure("Seccion.TLabel", background=p["elevado"], foreground=p["ambar"],
                     font=sans(9, True))
    estilo.configure("Dato.TLabel", background=p["elevado"], foreground=p["cian"],
                     font=mono(10))
    estilo.configure("DatoFuerte.TLabel", background=p["elevado"], foreground=p["cian"],
                     font=mono(11, True))
    estilo.configure("Cabecera.TLabel", background=p["elevado"], foreground=p["texto_debil"],
                     font=mono(9, True))
    estilo.configure("Marca.TLabel", background=p["abismo"], foreground=p["texto"],
                     font=sans(20, True))
    estilo.configure("MarcaTenue.TLabel", background=p["abismo"], foreground=p["texto_tenue"],
                     font=sans(9))

    # -- controles ----------------------------------------------------------
    estilo.configure("TButton", background=p["elevado_alto"], foreground=p["texto"],
                     bordercolor=p["borde"], focuscolor=p["ambar"],
                     padding=(10, 5), font=sans(9, True), relief="flat")
    estilo.map("TButton",
               background=[("pressed", p["seleccion"]), ("active", p["borde"])],
               foreground=[("disabled", p["texto_debil"])])

    estilo.configure("Primario.TButton", background=p["ambar_oscuro"], foreground=p["texto"])
    estilo.map("Primario.TButton",
               background=[("pressed", p["ambar_oscuro"]), ("active", p["ambar"])],
               foreground=[("active", p["abismo"])])

    estilo.configure("Peligro.TButton", background=p["elevado_alto"], foreground=p["fallo"])
    estilo.map("Peligro.TButton", background=[("active", p["fallo"])],
               foreground=[("active", p["abismo"])])

    estilo.configure("TEntry", fieldbackground=p["abismo"], foreground=p["cian"],
                     insertcolor=p["ambar"], bordercolor=p["borde"],
                     padding=4, font=mono(10))
    estilo.map("TEntry", bordercolor=[("focus", p["ambar"])])

    estilo.configure("TCombobox", fieldbackground=p["abismo"], background=p["elevado_alto"],
                     foreground=p["cian"], arrowcolor=p["texto_tenue"],
                     bordercolor=p["borde"], padding=3, font=mono(10))
    estilo.map("TCombobox", fieldbackground=[("readonly", p["abismo"])],
               bordercolor=[("focus", p["ambar"])])

    estilo.configure("TCheckbutton", background=p["elevado"], foreground=p["texto_tenue"],
                     focuscolor=p["elevado"], font=sans(9))
    estilo.map("TCheckbutton",
               background=[("active", p["elevado"])],
               foreground=[("active", p["texto"])],
               indicatorcolor=[("selected", p["ambar"]), ("!selected", p["borde"])])

    estilo.configure("TRadiobutton", background=p["elevado"], foreground=p["texto_tenue"],
                     focuscolor=p["elevado"], font=sans(9))
    estilo.map("TRadiobutton",
               background=[("active", p["elevado"])],
               foreground=[("active", p["texto"])],
               indicatorcolor=[("selected", p["ambar"]), ("!selected", p["borde"])])

    # -- barras de desplazamiento ------------------------------------------
    estilo.configure("TScrollbar", background=p["elevado_alto"], troughcolor=p["abismo"],
                     bordercolor=p["abismo"], arrowcolor=p["texto_debil"], relief="flat")
    estilo.map("TScrollbar", background=[("active", p["borde"])])

    # -- pestanas -----------------------------------------------------------
    estilo.configure("TNotebook", background=p["abismo"], bordercolor=p["borde"],
                     tabmargins=(2, 4, 2, 0))
    estilo.configure("TNotebook.Tab", background=p["noche"], foreground=p["texto_tenue"],
                     padding=(14, 6), font=sans(9, True), bordercolor=p["borde"])
    estilo.map("TNotebook.Tab",
               background=[("selected", p["elevado"])],
               foreground=[("selected", p["ambar"])])

    _APLICADO["si"] = True
    return estilo
