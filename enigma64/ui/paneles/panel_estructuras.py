"""
Panel visual de Estructuras de Datos (Tarea 29).

Muestra en vivo los vectores (celdas indexadas V[0 .. N-1]) y las matrices
(cuadricula F x C) que viven en la RAM mientras corre un algoritmo de la
libreria `estructuras.inc`. Se usa en tres pasos, numerados en pantalla:

    1. DATOS DE ENTRADA   el usuario escribe un vector o una matriz y se
                          guarda en RAM con su descriptor y su cabecera.
    2. PROGRAMA           elige un algoritmo (merge sort, ...) y lo carga.
    3. EJECUCION          paso a paso, animado o de corrido; las celdas que
                          se leen o escriben se iluminan, y al final se ven
                          la entrada y la salida lado a lado.

El panel solo habla con su servicio (`servicios/estructuras.py`) y con el
bus de eventos; no importa ni la libreria del grupo ni el hardware.

Arranque suelto:  python -m enigma64.ui.paneles.panel_estructuras

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import pathlib
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Dict, List, Optional, Tuple

from ..core.bus import Evento
from ..core.formato import hex32, hex64
from ..core.tema import MARGEN, PALETA, mono, sans
from ..core.visores import COLOR_CAMBIADA, COLOR_ESCRITA, COLOR_LEIDA, visor_para
from .base import PanelBase

#: Registros que importan para seguir la libreria (ABI de estructuras.inc).
REGISTROS_ABI = (
    ("R1", "base"), ("R2", "i / lo"), ("R3", "j / hi / valor"),
    ("R4", "aux"), ("R5", "retorno"), ("SP", "pila"),
)

#: Velocidades del modo animado: instrucciones por fotograma.
VELOCIDADES = (("Lenta", 1), ("Media", 8), ("Rapida", 40), ("Turbo", 200))

#: Ejemplos con los que se rellena el formulario de entrada.
EJEMPLO_VECTOR = "38, 27, 43, 3, 9, 82, 10, -4"
EJEMPLO_MATRIZ = "1 2 3\n4 5 6"

#: Milisegundos entre fotogramas al animar.
RETARDO_MS = 60


class PanelEstructuras(PanelBase):
    """Vectores y matrices de la Tarea 29, vistos en vivo durante la ejecucion."""

    NOMBRE = "estructuras"
    TITULO = "Estructuras de Datos · Vectores y Matrices"
    SUBTITULO = "Tarea 29  ·  libreria estructuras.inc vista en vivo sobre la RAM"
    ACENTO = PALETA["ok"]
    CLAVE_SERVICIO = "estructuras"
    TAMANO_SUELTO = (1220, 860)
    DESPLAZABLE_SUELTO = True

    # =======================================================================
    # Construccion
    # =======================================================================

    def construir(self) -> None:
        self._programas = {p["nombre"]: p for p in self.servicio.programas()}
        self.programa: Optional[dict] = None
        self.formato = tk.StringVar(value="decimal")
        self.tipo_entrada = tk.StringVar(value="vector")
        self.velocidad = tk.StringVar(value=VELOCIDADES[1][0])
        self._animando = False
        self._tarea: Optional[str] = None
        self._anteriores: Dict[str, List[List[int]]] = {}
        self._visores: Dict[str, object] = {}
        self._seleccion: Optional[Tuple[str, int, int]] = None

        self._construir_programa()
        self._construir_cuerpo()
        self._construir_ejecucion()

        self.bus.suscribir(Evento.MEMORIA_REINICIADA, self._al_cambiar_desde_fuera)
        self.bus.suscribir(Evento.CPU_AVANZO, self._al_cambiar_desde_fuera)
        self.bus.suscribir(Evento.PROGRAMA_CARGADO, self._al_cambiar_desde_fuera)
        self.bind("<Destroy>", lambda _e: self.pausar(), add="+")
        self._refrescar_entradas()
        self.refrescar()

    def preparar_demo(self) -> None:
        if not getattr(self.servicio, "disponible", False) or not self._programas:
            return
        primero = next(iter(self._programas))
        self.selector.set(primero)
        self.elegir_programa(primero)

    # -- paso 2: programa (va arriba porque define el contexto) --------------

    def _construir_programa(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")
        self._paso(fila, "2", "Programa").pack(side="left", padx=(0, 8))
        self.selector = ttk.Combobox(fila, values=list(self._programas), state="readonly",
                                     width=30)
        self.selector.pack(side="left")
        self.selector.bind("<<ComboboxSelected>>",
                           lambda _e: self.elegir_programa(self.selector.get()))
        ttk.Button(fila, text="Abrir .asm...", command=self.examinar).pack(side="left", padx=6)
        ttk.Button(fila, text="Compilar y cargar", style="Primario.TButton",
                   command=self.compilar_y_cargar).pack(side="left")
        self.estado_programa = tk.Label(fila, text="", bg=PALETA["elevado"],
                                        fg=PALETA["texto_debil"], font=mono(8), anchor="w")
        self.estado_programa.pack(side="left", fill="x", expand=True, padx=(10, 0))

        self.descripcion = tk.Label(self.cuerpo, text="", bg=PALETA["elevado"],
                                    fg=PALETA["texto_tenue"], font=sans(9), anchor="w",
                                    justify="left", wraplength=1100)
        self.descripcion.pack(fill="x", pady=(4, 0))

    # -- cuerpo: entrada a la izquierda, estructuras a la derecha ------------

    def _construir_cuerpo(self) -> None:
        marco = self.fila()
        marco.pack(fill="both", expand=True, pady=(MARGEN, 0))
        marco.columnconfigure(0, weight=0, minsize=320)
        marco.columnconfigure(1, weight=1)
        marco.rowconfigure(0, weight=1)

        izquierda = tk.Frame(marco, bg=PALETA["elevado"])
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, MARGEN))
        self._construir_entrada(izquierda)

        derecha = tk.Frame(marco, bg=PALETA["elevado"])
        derecha.grid(row=0, column=1, sticky="nsew")
        self._construir_estructuras(derecha)

    def _construir_entrada(self, maestro: tk.Frame) -> None:
        self._paso(maestro, "1", "Datos de entrada").pack(anchor="w")
        tk.Label(maestro, text="Escribe tus datos; se guardan en la RAM con su\n"
                               "descriptor y cabecera, listos para el programa.",
                 bg=PALETA["elevado"], fg=PALETA["texto_debil"], font=sans(8),
                 justify="left").pack(anchor="w", pady=(2, 6))

        tipos = self.fila(maestro)
        tipos.pack(fill="x")
        for valor, texto in (("vector", "Vector"), ("matriz", "Matriz")):
            tk.Radiobutton(tipos, text=texto, value=valor, variable=self.tipo_entrada,
                           command=self._al_cambiar_tipo, bg=PALETA["elevado"],
                           fg=PALETA["texto"], selectcolor=PALETA["abismo"],
                           activebackground=PALETA["elevado"],
                           activeforeground=PALETA["ambar"], font=sans(9),
                           highlightthickness=0).pack(side="left", padx=(0, 10))

        campos = self.fila(maestro)
        campos.pack(fill="x", pady=(6, 0))
        campos.columnconfigure(1, weight=1)
        self.rotulo(campos, "Nombre").grid(row=0, column=0, sticky="w")
        self.campo_nombre = ttk.Entry(campos, width=12)
        self.campo_nombre.grid(row=0, column=1, sticky="ew", pady=2)
        self.campo_nombre.insert(0, "V")
        self.rotulo(campos, "Base").grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.campo_base = ttk.Entry(campos, width=12)
        self.campo_base.grid(row=1, column=1, sticky="ew", pady=2)
        self.campo_base.insert(0, "auto")

        self.ayuda_valores = self.rotulo(maestro, "")
        self.ayuda_valores.pack(anchor="w", pady=(6, 2))
        borde = tk.Frame(maestro, bg=PALETA["borde"])
        borde.pack(fill="x")
        self.campo_valores = tk.Text(borde, height=4, width=34, font=mono(10),
                                     bg=PALETA["abismo"], fg=PALETA["cian"],
                                     insertbackground=PALETA["ambar"], relief="flat",
                                     highlightthickness=0, padx=6, pady=4, wrap="word")
        self.campo_valores.pack(fill="x", padx=1, pady=1)
        self.campo_valores.bind("<Control-Return>", lambda _e: (self.escribir_entrada(), "break")[1])

        botones = self.fila(maestro)
        botones.pack(fill="x", pady=(6, 0))
        ttk.Button(botones, text="Escribir en RAM", style="Primario.TButton",
                   command=self.escribir_entrada).pack(side="left")
        ttk.Button(botones, text="Ejemplo", command=self.rellenar_ejemplo).pack(side="left",
                                                                              padx=6)
        self.mensaje_entrada = tk.Label(maestro, text="", bg=PALETA["elevado"],
                                        fg=PALETA["texto_debil"], font=sans(8),
                                        anchor="w", justify="left", wraplength=300)
        self.mensaje_entrada.pack(fill="x", pady=(4, 0))

        self.separador(maestro)
        self.rotulo(maestro, "Tus estructuras en RAM").pack(anchor="w")
        borde_lista = tk.Frame(maestro, bg=PALETA["borde"])
        borde_lista.pack(fill="x", pady=(4, 0))
        self.lista_entradas = tk.Listbox(borde_lista, height=5, font=mono(9),
                                         bg=PALETA["abismo"], fg=PALETA["texto"],
                                         selectbackground=PALETA["seleccion"],
                                         highlightthickness=0, relief="flat",
                                         activestyle="none")
        self.lista_entradas.pack(fill="x", padx=1, pady=1)
        acciones = self.fila(maestro)
        acciones.pack(fill="x", pady=(6, 0))
        ttk.Button(acciones, text="Quitar", command=self.quitar_entrada).pack(side="left")
        ttk.Button(acciones, text="Detectar en RAM",
                   command=self.detectar).pack(side="left", padx=6)

        self.separador(maestro)
        self.rotulo(maestro, "Celda seleccionada").pack(anchor="w")
        self.detalle_celda = tk.Label(maestro, text="Pulsa una celda para ver su\n"
                                                    "direccion y su valor en bruto.",
                                      bg=PALETA["elevado"], fg=PALETA["texto_tenue"],
                                      font=mono(9), anchor="w", justify="left")
        self.detalle_celda.pack(fill="x", pady=(2, 0))

        self._al_cambiar_tipo()

    def _construir_estructuras(self, maestro: tk.Frame) -> None:
        cabecera = self.fila(maestro)
        cabecera.pack(fill="x")
        self._paso(cabecera, "◉", "Estructuras en memoria").pack(side="left")

        formatos = self.fila(cabecera)
        formatos.pack(side="right")
        for valor, texto in (("decimal", "Dec"), ("hex", "Hex"), ("float", "Float")):
            tk.Radiobutton(formatos, text=texto, value=valor, variable=self.formato,
                           command=self.refrescar, indicatoron=False, width=6,
                           bg=PALETA["elevado_alto"], fg=PALETA["texto"],
                           selectcolor=PALETA["ambar_oscuro"], relief="flat",
                           activebackground=PALETA["seleccion"], font=sans(8, True),
                           highlightthickness=0, bd=0).pack(side="left", padx=1)

        leyenda = self.fila(maestro)
        leyenda.pack(fill="x", pady=(4, 6))
        for color, texto, relleno in ((COLOR_ESCRITA, "escrita ahora", True),
                                      (COLOR_LEIDA, "leida ahora", False),
                                      (COLOR_CAMBIADA, "distinta de la entrada", None)):
            muestra = tk.Canvas(leyenda, width=16, height=12, bg=PALETA["elevado"],
                                highlightthickness=0)
            if relleno is None:
                muestra.create_text(8, 6, text="7", fill=color, font=mono(8, True))
            else:
                muestra.create_rectangle(1, 1, 15, 11, outline=color, width=2,
                                         fill=color if relleno else PALETA["abismo"])
            muestra.pack(side="left")
            tk.Label(leyenda, text=texto, bg=PALETA["elevado"], fg=PALETA["texto_debil"],
                     font=sans(8)).pack(side="left", padx=(3, 12))

        self.contenedor = tk.Frame(maestro, bg=PALETA["elevado"])
        self.contenedor.pack(fill="both", expand=True)
        self.aviso_vacio = tk.Label(
            self.contenedor, bg=PALETA["elevado"], fg=PALETA["texto_debil"], font=sans(9),
            justify="left",
            text="Aun no hay estructuras que mostrar.\n\n"
                 "  · Escribe un vector o una matriz en «1 · Datos de entrada», o\n"
                 "  · elige un programa en «2 · Programa» y pulsa Compilar y cargar.")

    # -- paso 3: ejecucion ----------------------------------------------------

    def _construir_ejecucion(self) -> None:
        self.separador()
        fila = self.fila()
        fila.pack(fill="x")
        self._paso(fila, "3", "Ejecucion").pack(side="left", padx=(0, 10))

        self.boton_paso = ttk.Button(fila, text="Paso", command=lambda: self.avanzar(1))
        self.boton_paso.pack(side="left")
        self.boton_paso10 = ttk.Button(fila, text="×10", width=4,
                                       command=lambda: self.avanzar(10))
        self.boton_paso10.pack(side="left", padx=(4, 0))
        self.boton_animar = ttk.Button(fila, text="▶ Animar", style="Primario.TButton",
                                       command=self.alternar_animacion)
        self.boton_animar.pack(side="left", padx=6)
        ttk.Combobox(fila, textvariable=self.velocidad, state="readonly", width=8,
                     values=[n for n, _v in VELOCIDADES]).pack(side="left")
        self.boton_fin = ttk.Button(fila, text="Ejecutar hasta HLT", command=self.ejecutar_todo)
        self.boton_fin.pack(side="left", padx=6)
        ttk.Button(fila, text="Reiniciar", style="Peligro.TButton",
                   command=self.recargar).pack(side="left")
        self._botones_ejecucion = (self.boton_paso, self.boton_paso10, self.boton_animar,
                                   self.boton_fin)

        estado = self.fila()
        estado.pack(fill="x", pady=(MARGEN, 0))
        self._datos: Dict[str, tk.Label] = {}
        for clave, etiqueta in (("pc", "PC"), ("subrutina", "Subrutina"),
                                ("instruccion", "Instruccion"),
                                ("instrucciones", "Instrucciones"), ("estado", "Estado")):
            columna = tk.Frame(estado, bg=PALETA["elevado"])
            columna.pack(side="left", padx=(0, 22))
            self.rotulo(columna, etiqueta).pack(anchor="w")
            valor = self.texto_dato(columna, "—", tam=10, negrita=True)
            valor.pack(anchor="w")
            self._datos[clave] = valor

        registros = self.fila()
        registros.pack(fill="x", pady=(MARGEN, 0))
        self._registros: Dict[str, tk.Label] = {}
        for nombre, rol in REGISTROS_ABI:
            columna = tk.Frame(registros, bg=PALETA["elevado"])
            columna.pack(side="left", padx=(0, 18))
            self.rotulo(columna, f"{nombre} · {rol}").pack(anchor="w")
            valor = self.texto_dato(columna, "—", tam=9)
            valor.pack(anchor="w")
            self._registros[nombre] = valor

        marco = tk.Frame(self.cuerpo, bg=PALETA["borde"])
        marco.pack(fill="x", pady=(MARGEN, 0))
        caja = tk.Frame(marco, bg=PALETA["abismo"])
        caja.pack(fill="x", padx=1, pady=1)
        tk.Label(caja, text="PANTALLA MMIO  ·  0xFF001010", bg=PALETA["abismo"],
                 fg=PALETA["violeta"], font=sans(8, True)).pack(anchor="w", padx=10,
                                                                pady=(6, 0))
        self.pantalla = tk.Label(caja, text="(el programa aun no ha escrito nada)",
                                 bg=PALETA["abismo"], fg=PALETA["texto_tenue"],
                                 font=mono(10), anchor="w", justify="left", wraplength=1100)
        self.pantalla.pack(fill="x", padx=10, pady=(2, 8))

        if not self.servicio.puede_ejecutar:
            for boton in self._botones_ejecucion:
                boton.state(["disabled"])
            tk.Label(fila, text="Ejecutar necesita la Unidad de Control (Integrante 3)",
                     bg=PALETA["elevado"], fg=PALETA["texto_debil"],
                     font=sans(8)).pack(side="left", padx=(10, 0))
        else:
            self._habilitar_ejecucion(False)

    def _paso(self, maestro, numero: str, texto: str) -> tk.Frame:
        """Rotulo numerado de cada paso del flujo: '1 · DATOS DE ENTRADA'."""
        caja = tk.Frame(maestro, bg=PALETA["elevado"])
        tk.Label(caja, text=f" {numero} ", bg=PALETA["ambar"], fg=PALETA["abismo"],
                 font=sans(9, True)).pack(side="left")
        tk.Label(caja, text=texto.upper(), bg=PALETA["elevado"], fg=PALETA["texto"],
                 font=sans(9, True)).pack(side="left", padx=(6, 0))
        return caja

    # =======================================================================
    # Paso 1: datos de entrada
    # =======================================================================

    def _al_cambiar_tipo(self) -> None:
        if self.tipo_entrada.get() == "vector":
            self.ayuda_valores.configure(text="VALORES  ·  separados por coma o espacio")
            if self.campo_nombre.get() in ("", "A", "M"):
                self._fijar_campo(self.campo_nombre, "V")
        else:
            self.ayuda_valores.configure(text="FILAS  ·  una por linea o separadas por ';'")
            if self.campo_nombre.get() in ("", "V"):
                self._fijar_campo(self.campo_nombre, "A")

    @staticmethod
    def _fijar_campo(campo: ttk.Entry, texto: str) -> None:
        campo.delete(0, "end")
        campo.insert(0, texto)

    def rellenar_ejemplo(self) -> None:
        ejemplo = EJEMPLO_VECTOR if self.tipo_entrada.get() == "vector" else EJEMPLO_MATRIZ
        self.campo_valores.delete("1.0", "end")
        self.campo_valores.insert("1.0", ejemplo)

    def _leer_base(self) -> Optional[int]:
        texto = self.campo_base.get().strip().lower()
        if texto in ("", "auto"):
            return None
        try:
            return int(texto.replace("_", ""), 0)
        except ValueError:
            raise ValueError(f"la base '{texto}' no es una direccion (usa 0x00220000 o auto)")

    def escribir_entrada(self) -> Optional[dict]:
        """Valida lo escrito, lo guarda en RAM y lo dibuja."""
        texto = self.campo_valores.get("1.0", "end").strip()
        nombre = self.campo_nombre.get().strip()
        try:
            base = self._leer_base()
            if self.tipo_entrada.get() == "vector":
                entrada = self.servicio.definir_vector(
                    nombre, self.servicio.parsear_vector(texto), base=base)
                forma = f"{entrada['longitud']} elementos"
            else:
                entrada = self.servicio.definir_matriz(
                    nombre, self.servicio.parsear_matriz(texto), base=base)
                forma = f"{entrada['filas']} x {entrada['columnas']}"
        except Exception as exc:
            self._mensaje(f"✗ {exc}", PALETA["fallo"])
            self.trazar(f"entrada rechazada: {exc}", "error")
            return None

        self._mensaje(f"✓ {entrada['nombre']} ({forma}) escrito en {hex32(entrada['base'])}, "
                      f"descriptor en la ranura {entrada['ranura']}.", PALETA["ok"])
        self._anteriores.pop(entrada["nombre"], None)
        self._refrescar_entradas()
        self.refrescar()
        self.publicar(Evento.ESTRUCTURA_DEFINIDA, nombre=entrada["nombre"],
                      tipo=entrada["tipo"], direccion=entrada["base"])
        self.publicar(Evento.IR_A_DIRECCION, direccion=entrada["base"])
        self.trazar(f"estructura {entrada['nombre']} escrita en {hex32(entrada['base'])}",
                    "exito")
        return entrada

    def quitar_entrada(self) -> None:
        seleccion = self.lista_entradas.curselection()
        if not seleccion:
            self._mensaje("Selecciona en la lista la estructura que quieres quitar.",
                          PALETA["texto_debil"])
            return
        nombre = self.lista_entradas.get(seleccion[0]).split()[0]
        self.servicio.quitar(nombre)
        self._anteriores.pop(nombre, None)
        self._refrescar_entradas()
        self.refrescar()
        self._mensaje(f"{nombre} ya no se observa (sus datos siguen en RAM hasta "
                      "el proximo Reiniciar).", PALETA["texto_debil"])

    def detectar(self) -> None:
        try:
            encontradas = self.servicio.detectar()
        except Exception as exc:
            self._mensaje(f"✗ {exc}", PALETA["fallo"])
            return
        self.refrescar()
        if encontradas:
            nombres = ", ".join(e["nombre"] for e in encontradas)
            self._mensaje(f"✓ {len(encontradas)} descriptor(es) en 0x00210000: {nombres}",
                          PALETA["ok"])
        else:
            self._mensaje("No hay descriptores validos en la tabla de cabeceras.",
                          PALETA["texto_debil"])

    def _refrescar_entradas(self) -> None:
        self.lista_entradas.delete(0, "end")
        for e in self.servicio.entradas_publicas():
            forma = (f"[{e['longitud']}]" if e["tipo"] == "vector"
                     else f"[{e['filas']}x{e['columnas']}]")
            self.lista_entradas.insert("end", f"{e['nombre']:<8} {forma:<8} {hex32(e['base'])}")

    def _mensaje(self, texto: str, color: str) -> None:
        self.mensaje_entrada.configure(text=texto, fg=color)

    # =======================================================================
    # Paso 2: programa
    # =======================================================================

    def elegir_programa(self, nombre: str) -> None:
        programa = self._programas.get(nombre)
        if programa is None:
            return
        self.programa = programa
        self.descripcion.configure(text=programa["descripcion"])
        self.servicio.observar_programa(programa)
        self.estado_programa.configure(text=programa["ruta"], fg=PALETA["texto_debil"])
        self.refrescar()

    def examinar(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Programa en ensamblador que use estructuras.inc",
            filetypes=[("Ensamblador Enigma-64", "*.asm"), ("Todos los archivos", "*.*")])
        if not ruta:
            return
        self.programa = {"clave": pathlib.Path(ruta).stem, "nombre": pathlib.Path(ruta).name,
                         "ruta": ruta, "observables": [],
                         "descripcion": "Programa externo: pulsa «Detectar en RAM» tras "
                                        "ejecutarlo para ver sus descriptores."}
        self.selector.set("")
        self.descripcion.configure(text=self.programa["descripcion"])
        self.estado_programa.configure(text=ruta, fg=PALETA["texto_debil"])

    def compilar_y_cargar(self) -> bool:
        """Preprocesa, ensambla, empaqueta el .e64 y lo deja listo en RAM."""
        self.pausar()
        if self.programa is None:
            self.estado_programa.configure(text="✗ elige primero un programa",
                                           fg=PALETA["fallo"])
            return False
        try:
            fuente = self.servicio.leer_archivo(self.programa["ruta"])
        except Exception as exc:
            self.estado_programa.configure(text=f"✗ {exc}", fg=PALETA["fallo"])
            return False
        resultado = self.servicio.compilar(fuente, ruta=self.programa["ruta"])
        if not resultado["ok"]:
            self.estado_programa.configure(text=f"✗ {resultado['error']}", fg=PALETA["fallo"])
            self.trazar(f"compilacion fallida: {resultado['error']}", "error")
            self._habilitar_ejecucion(False)
            return False
        return self.recargar(resultado)

    def recargar(self, resultado: Optional[dict] = None) -> bool:
        """Vuelve a cargar el programa compilado con los datos de entrada actuales."""
        self.pausar()
        try:
            informe = self.servicio.cargar()
        except Exception as exc:
            self.estado_programa.configure(text=f"✗ {exc}", fg=PALETA["fallo"])
            self.trazar(f"carga rechazada: {exc}", "error")
            return False
        self._anteriores.clear()
        texto = (f"✓ {informe['tamano_codigo']} bytes en {hex32(informe['direccion_base'])}"
                 f"  ·  {informe['estructuras_escritas']} entrada(s) del usuario en RAM")
        if resultado is not None:
            texto += f"  ·  {resultado['lineas']} lineas tras el preprocesador"
        self.estado_programa.configure(text=texto, fg=PALETA["ok"])
        self.pantalla.configure(text="(el programa aun no ha escrito nada)",
                                fg=PALETA["texto_tenue"])
        self._habilitar_ejecucion(True)
        self.refrescar()
        self.publicar(Evento.PROGRAMA_CARGADO, **informe)
        self.trazar(f"programa {self.programa['nombre'] if self.programa else ''} cargado",
                    "exito")
        return True

    # =======================================================================
    # Paso 3: ejecucion
    # =======================================================================

    def avanzar(self, instrucciones: int = 1) -> Optional[dict]:
        try:
            estado = self.servicio.avanzar(instrucciones)
        except Exception as exc:
            self.pausar()
            self._pintar_error(exc)
            return None
        self.refrescar(estado)
        if estado["detenido"]:
            self._al_terminar(estado)
        return estado

    def alternar_animacion(self) -> None:
        if self._animando:
            self.pausar()
        else:
            self._animando = True
            self.boton_animar.configure(text="❚❚ Pausa")
            self._fotograma()

    def pausar(self) -> None:
        self._animando = False
        if self._tarea is not None:
            try:
                self.after_cancel(self._tarea)
            except Exception:
                pass
            self._tarea = None
        try:
            self.boton_animar.configure(text="▶ Animar")
        except Exception:  # el panel se esta destruyendo
            pass

    def _fotograma(self) -> None:
        self._tarea = None
        if not self._animando:
            return
        paso = dict(VELOCIDADES).get(self.velocidad.get(), 8)
        estado = self.avanzar(paso)
        if estado is None or estado["detenido"]:
            self.pausar()
            return
        self._tarea = self.after(RETARDO_MS, self._fotograma)

    def ejecutar_todo(self) -> Optional[dict]:
        self.pausar()
        try:
            estado = self.servicio.ejecutar_hasta_fin()
        except Exception as exc:
            self._pintar_error(exc)
            return None
        self.refrescar(estado)
        self._al_terminar(estado)
        return estado

    def _al_terminar(self, estado: dict) -> None:
        self._habilitar_ejecucion(False)
        self.publicar(Evento.CPU_AVANZO, fase="FETCH", ciclos=estado["ciclos"],
                      instrucciones=estado["instrucciones"], detenido=estado["detenido"])
        self.publicar(Evento.ESTRUCTURAS_ACTUALIZADAS, terminado=True,
                      instrucciones=estado["instrucciones"])
        if estado.get("agotado"):
            self.trazar("se agoto el presupuesto de instrucciones sin llegar a HLT", "aviso")
        else:
            self.trazar(f"programa terminado en HLT tras {estado['instrucciones']} "
                        "instrucciones", "exito")

    def _pintar_error(self, exc: Exception) -> None:
        self._datos["estado"].configure(text=f"FALLO · {type(exc).__name__}",
                                        fg=PALETA["fallo"])
        self.pantalla.configure(text=str(exc), fg=PALETA["fallo"])
        self.trazar(f"la ejecucion se detuvo: {exc}", "error")
        self._habilitar_ejecucion(False)

    def _habilitar_ejecucion(self, activo: bool) -> None:
        if not self.servicio.puede_ejecutar:
            return
        for boton in self._botones_ejecucion:
            boton.state(["!disabled"] if activo else ["disabled"])

    # =======================================================================
    # Dibujo de las estructuras
    # =======================================================================

    def _al_cambiar_desde_fuera(self, mensaje) -> None:
        """Otra pestana movio la CPU o la RAM: se vuelve a leer todo."""
        if mensaje.get("origen") == self.NOMBRE:
            return
        try:
            self.refrescar()
        except Exception:  # pragma: no cover - el panel puede estar destruyendose
            pass

    def refrescar(self, estado: Optional[dict] = None) -> None:
        """Relee de la RAM todas las estructuras observadas y las redibuja."""
        try:
            fotos = self.servicio.instantaneas()
        except Exception as exc:
            self._pintar_error(exc)
            return
        formato = self.formato.get()
        accesos = (estado or {}).get("accesos", [])

        nombres = [f["nombre"] for f in fotos]
        for nombre in list(self._visores):
            if nombre not in nombres:
                self._visores.pop(nombre)["marco"].destroy()
        if fotos:
            self.aviso_vacio.pack_forget()
        else:
            self.aviso_vacio.pack(anchor="w", pady=10)

        for foto in fotos:
            entrada = self._visores.get(foto["nombre"])
            if entrada is None or entrada["tipo"] != foto["tipo"]:
                if entrada is not None:
                    entrada["marco"].destroy()
                entrada = self._crear_visor(foto)
                self._visores[foto["nombre"]] = entrada
            self._pintar_foto(entrada, foto, formato, accesos,
                              lambda p, f=formato: self.servicio.formatear(p, f))
            self._anteriores[foto["nombre"]] = foto["palabras"]

        if estado is None and self.servicio.puede_ejecutar:
            estado = self.servicio.estado()
        if estado is not None:
            self._pintar_estado(estado)

    def _crear_visor(self, foto: dict) -> dict:
        marco = tk.Frame(self.contenedor, bg=PALETA["elevado"])
        marco.pack(fill="x", pady=(0, MARGEN))
        titulo = tk.Label(marco, bg=PALETA["elevado"], fg=PALETA["texto"], font=sans(9, True),
                          anchor="w")
        titulo.pack(fill="x")
        nombre = foto["nombre"]
        visor = visor_para(foto["tipo"], marco,
                           al_pulsar=lambda i, j, n=nombre: self.seleccionar_celda(n, i, j))
        visor.pack(fill="x" if foto["tipo"] == "vector" else "none", anchor="w", pady=(2, 0))
        comparacion = tk.Label(marco, bg=PALETA["elevado"], fg=PALETA["texto_debil"],
                               font=mono(8), anchor="w", justify="left", wraplength=820)
        comparacion.pack(fill="x")
        return {"tipo": foto["tipo"], "marco": marco, "titulo": titulo, "visor": visor,
                "comparacion": comparacion}

    def _pintar_foto(self, entrada: dict, foto: dict, formato: str, accesos: list,
                     formatear) -> None:
        filas, cols, base = foto["filas"], foto["columnas"], foto["base"]
        forma = (f"N = {cols}" if foto["tipo"] == "vector" else f"{filas} x {cols}")
        origen = {"usuario": "tu entrada", "programa": "del programa",
                  "descriptor": "detectada en la tabla de descriptores"}.get(foto["origen"],
                                                                             foto["origen"])
        nota = f"  ·  ⚠ {foto['nota']}" if foto["nota"] else ""
        entrada["titulo"].configure(
            text=f"{foto['nombre']}   {foto['tipo']} {forma}   ·   base {hex32(base)}   ·   "
                 f"zona {foto['zona'] or '—'}   ·   {origen}{nota}")

        escritas, leidas = set(), set()
        total = filas * cols
        for acceso in accesos:
            desplazamiento = acceso["direccion"] - base
            if desplazamiento < 0 or desplazamiento % 8 or desplazamiento // 8 >= total:
                continue
            indice = desplazamiento // 8
            celda = (indice // cols, indice % cols) if cols else (0, 0)
            (escritas if acceso["tipo"] == "escritura" else leidas).add(celda)

        cambiadas = set()
        iniciales = foto["iniciales"]
        if iniciales is not None:
            cambiadas = {(i, j) for i in range(filas) for j in range(cols)
                         if foto["palabras"][i][j] != iniciales[i][j]}
        entrada["visor"].fijar(foto["palabras"], formatear, formato,
                               escritas=escritas, leidas=leidas, cambiadas=cambiadas)

        if iniciales is not None and cambiadas:
            def lista(filas_2d):
                textos = ["[" + ", ".join(formatear(p) for p in fila) + "]" for fila in filas_2d]
                return textos[0] if foto["tipo"] == "vector" else " ".join(textos)
            entrada["comparacion"].configure(
                text=f"entrada  {lista(iniciales)}\nsalida   {lista(foto['palabras'])}",
                fg=PALETA["texto_tenue"])
        else:
            entrada["comparacion"].configure(text="")

    def seleccionar_celda(self, nombre: str, fila: int, columna: int) -> None:
        """Detalle de una celda y aviso al volcado de memoria para que salte alli."""
        try:
            foto = self.servicio.instantanea(nombre, {})
            palabra = foto["palabras"][fila][columna]
            direccion = self.servicio.direccion_de(nombre, fila, columna)
        except Exception:
            return
        indice = f"[{columna}]" if foto["tipo"] == "vector" else f"[{fila}][{columna}]"
        formula = (f"B + ({columna} << 3)" if foto["tipo"] == "vector"
                   else f"B + (({fila}*{foto['columnas']} + {columna}) << 3)")
        self.detalle_celda.configure(
            text=f"{nombre}{indice}  @ {hex32(direccion)}\n"
                 f"  = {formula}\n"
                 f"dec   {self.servicio.formatear(palabra, 'decimal')}\n"
                 f"hex   {hex64(palabra)}\n"
                 f"float {self.servicio.formatear(palabra, 'float')}",
            fg=PALETA["cian"])
        self._seleccion = (nombre, fila, columna)
        self.publicar(Evento.IR_A_DIRECCION, direccion=direccion)

    def _pintar_estado(self, estado: dict) -> None:
        self._datos["pc"].configure(text=hex32(estado["pc"]))
        self._datos["subrutina"].configure(text=estado["etiqueta"] or "—")
        self._datos["instruccion"].configure(text=estado["mnemonico"] or "—")
        self._datos["instrucciones"].configure(text=str(estado["instrucciones"]))
        if estado.get("agotado"):
            texto, color = "SIN HLT", PALETA["alerta"]
        elif estado["detenido"]:
            texto, color = "HLT", PALETA["ok"]
        else:
            texto, color = "EN CURSO", PALETA["cian"]
        self._datos["estado"].configure(text=texto, fg=color)
        for nombre, etiqueta in self._registros.items():
            valor = estado["registros"].get(nombre)
            if valor is None:
                etiqueta.configure(text="—")
                continue
            con_signo = valor - (1 << 64) if valor >> 63 else valor
            texto = hex32(valor) if abs(con_signo) > 0xFFFF else str(con_signo)
            etiqueta.configure(text=texto)

        salida = self.servicio.salida_mmio()
        if salida:
            self.pantalla.configure(text=salida, fg=PALETA["texto"])


if __name__ == "__main__":
    PanelEstructuras.ejecutar_suelto()
