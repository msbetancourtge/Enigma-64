"""
Base comun de todos los paneles de Enigma-64.

Aqui vive la regla que pidio el profesor: cada modulo tiene que poder
funcionar por separado. `PanelBase.ejecutar_suelto()` levanta una ventana con
un unico panel dentro, con su propio hardware recien construido y un bus que
no va a ninguna parte. El panel no se entera de la diferencia: el mismo codigo
sirve dentro de la ventana completa y fuera de ella.

Un panel NUNCA importa a otro panel. Si necesita avisar de algo, lo publica en
el bus; si necesita datos del hardware, se los pide a su servicio.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk

from typing import Optional

from ..core.bus import BusEventos, BusNulo
from ..core.tema import COMPUTADOR, EMPRESA, MARGEN, PALETA, aplicar_tema, mono, sans
from ..core.widgets import Insignia, MarcaNoctua, MarcoDesplazable, Tarjeta


class PanelBase(tk.Frame):
    """
    Un panel es una tarjeta autocontenida asociada a un modulo del equipo.

    Las subclases definen los metadatos de clase y implementan `construir()`.
    """

    #: Identificador corto, usado como origen en los eventos del bus.
    NOMBRE = "panel"
    #: Titulo visible de la tarjeta.
    TITULO = "Panel"
    #: Linea de contexto: de quien es el modulo y como se llama.
    SUBTITULO = ""
    #: Color de la franja de acento; None usa el ambar de la marca.
    ACENTO: Optional[str] = None
    #: Clave del servicio que necesita dentro de `Maquina`; "" si no necesita ninguno.
    CLAVE_SERVICIO = ""
    #: Tamano minimo razonable cuando se abre suelto.
    TAMANO_SUELTO = (820, 640)
    #: True para los paneles mas altos que un portatil de 768 lineas: al
    #: abrirse sueltos van dentro de un marco desplazable en vez de recortarse.
    DESPLAZABLE_SUELTO = False

    def __init__(self, maestro, servicio=None, bus: Optional[BusEventos] = None,
                 **kwargs) -> None:
        super().__init__(maestro, bg=PALETA["noche"], **kwargs)
        self.servicio = servicio
        self.bus = bus if bus is not None else BusNulo()

        self.tarjeta = Tarjeta(self, self.TITULO, self.SUBTITULO, self.ACENTO)
        self.tarjeta.pack(fill="both", expand=True)
        self.cuerpo = self.tarjeta.cuerpo

        if self.CLAVE_SERVICIO and (servicio is None or not servicio.disponible):
            self._construir_sin_modulo()
        else:
            self.construir()

    # -- a implementar por cada panel ---------------------------------------

    def construir(self) -> None:
        raise NotImplementedError

    def preparar_demo(self) -> None:
        """
        Estado inicial para cuando el panel se abre suelto. Opcional: sirve
        para que la demostracion del modulo no arranque con todo en ceros.
        """

    # -- ayudas de maquetado ------------------------------------------------

    def fila(self, maestro=None) -> tk.Frame:
        """Contenedor horizontal con el fondo de la tarjeta."""
        return tk.Frame(maestro or self.cuerpo, bg=PALETA["elevado"])

    def rotulo(self, maestro, texto: str, tam: int = 8) -> tk.Label:
        """Rotulo corto en mayusculas, el que va encima de cada campo."""
        return tk.Label(maestro, text=texto.upper(), bg=PALETA["elevado"],
                        fg=PALETA["texto_debil"], font=sans(tam, True))

    def texto_dato(self, maestro, texto: str = "", color: Optional[str] = None,
                   tam: int = 10, negrita: bool = False) -> tk.Label:
        """Valor monoespaciado: hexadecimal, binario o decimal."""
        return tk.Label(maestro, text=texto, bg=PALETA["elevado"],
                        fg=color or PALETA["cian"], font=mono(tam, negrita))

    def separador(self, maestro=None) -> tk.Frame:
        linea = tk.Frame(maestro or self.cuerpo, bg=PALETA["borde_sutil"], height=1)
        linea.pack(fill="x", pady=MARGEN)
        return linea

    # -- comunicacion -------------------------------------------------------

    def publicar(self, evento: str, **datos):
        """Publica en el bus anotando de que panel salio el evento."""
        datos.setdefault("origen", self.NOMBRE)
        return self.bus.publicar(evento, **datos)

    def trazar(self, texto: str, severidad: str = "info"):
        return self.bus.traza(texto, severidad=severidad, origen=self.NOMBRE)

    # -- estado degradado ---------------------------------------------------

    def _construir_sin_modulo(self) -> None:
        """
        El modulo del companero no se pudo importar. En vez de reventar, el
        panel lo dice con claridad y sigue en pie.
        """
        motivo = getattr(self.servicio, "motivo", "") or "modulo no encontrado"
        caja = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        caja.pack(fill="both", expand=True, pady=20)

        tk.Label(caja, text="MODULO NO DISPONIBLE", bg=PALETA["elevado"],
                 fg=PALETA["alerta"], font=sans(11, True)).pack()
        tk.Label(caja, text=f"No se pudo cargar {self.CLAVE_SERVICIO}.",
                 bg=PALETA["elevado"], fg=PALETA["texto_tenue"],
                 font=sans(9)).pack(pady=(8, 2))
        tk.Label(caja, text=motivo, bg=PALETA["elevado"], fg=PALETA["texto_debil"],
                 font=mono(9), wraplength=420, justify="center").pack()
        tk.Label(caja, text="El resto de la interfaz sigue funcionando.",
                 bg=PALETA["elevado"], fg=PALETA["texto_debil"],
                 font=sans(9)).pack(pady=(10, 0))

    # -- arranque suelto ----------------------------------------------------

    @classmethod
    def ejecutar_suelto(cls) -> None:
        """
        Abre una ventana que contiene solo este panel.

        Construye su propia maquina, de modo que no comparte memoria ni
        registros con ninguna otra ventana. Es la forma de demostrar el modulo
        de manera aislada.
        """
        from ..servicios import construir_maquina  # import local: evita ciclos

        raiz = tk.Tk()
        aplicar_tema(raiz)
        raiz.title(f"{COMPUTADOR} · {cls.TITULO} · {EMPRESA}")
        ancho, alto = cls.TAMANO_SUELTO
        if cls.DESPLAZABLE_SUELTO:
            ancho = min(ancho, raiz.winfo_screenwidth() - 40)
            alto = min(alto, raiz.winfo_screenheight() - 90)
        raiz.geometry(f"{ancho}x{alto}")
        raiz.minsize(min(ancho, 640), min(alto, 480))
        raiz.configure(bg=PALETA["abismo"])

        maquina = construir_maquina()
        servicio = getattr(maquina, cls.CLAVE_SERVICIO) if cls.CLAVE_SERVICIO else None

        _barra_suelta(raiz, cls)

        maestro = raiz
        if cls.DESPLAZABLE_SUELTO:
            marco = MarcoDesplazable(raiz)
            marco.pack(fill="both", expand=True, padx=12, pady=(0, 12))
            maestro = marco.interior

        panel = cls(maestro, servicio=servicio, bus=BusNulo())
        if cls.DESPLAZABLE_SUELTO:
            panel.pack(fill="both", expand=True)
        else:
            panel.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        panel.preparar_demo()

        raiz.mainloop()


def _barra_suelta(raiz: tk.Tk, cls) -> None:
    """Cabecera de marca para las ventanas de un solo panel."""
    barra = tk.Frame(raiz, bg=PALETA["abismo"])
    barra.pack(fill="x", padx=12, pady=(10, 8))

    MarcaNoctua(barra, lado=36, fondo=PALETA["abismo"]).pack(side="left")

    columna = tk.Frame(barra, bg=PALETA["abismo"])
    columna.pack(side="left", padx=10)
    tk.Label(columna, text=cls.TITULO, bg=PALETA["abismo"], fg=PALETA["texto"],
             font=sans(13, True)).pack(anchor="w")
    modulo = cls.__module__.replace("enigma64.ui.paneles.", "")
    tk.Label(columna, text=f"python -m enigma64.ui.paneles.{modulo}",
             bg=PALETA["abismo"], fg=PALETA["ambar"], font=mono(9)).pack(anchor="w")

    insignia = Insignia(barra, ancho=150, fondo=PALETA["abismo"])
    insignia.fijar("MODULO INDEPENDIENTE", PALETA["ok"])
    insignia.pack(side="right")

    tk.Frame(raiz, bg=PALETA["borde"], height=1).pack(fill="x")
    tk.Frame(raiz, bg=PALETA["abismo"], height=10).pack(fill="x")
