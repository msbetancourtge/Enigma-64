"""
Panel de la Unidad de Punto Flotante.

Tiene dos piezas que trabajan juntas:

  * una calculadora reactiva: basta con escribir los operandos o cambiar de
    operacion para que la rutina de la FPU se ejecute de nuevo;
  * un visor IEEE 754 que desglosa cualquiera de los tres valores en el bit 63
    de signo, los 11 bits de exponente, los 52 de mantisa y el bit implicito.

Las cuentas no las hace Python: cada operacion entra por la tabla de vectores
de la biblioteca en ensamblador del equipo y corre sobre la CPU de Enigma-64.
Al lado se ensena lo que responde la aritmetica IEEE 754 del anfitrion, para
que se vea si la rutina coincide con la norma.

Arranque suelto:  python -m enigma64.ui.paneles.panel_fpu

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..core.bus import Evento
from ..core.formato import (
    MASCARA_64, ValorInvalido, clasificar_ieee754, con_signo, hex64,
    parsear_entero, parsear_ieee754, texto_flotante,
)
from ..core.tema import MARGEN, MARGEN_CHICO, PALETA, mono, sans
from ..core.widgets import Insignia, Led, TextoMono, VisorIEEE754
from .base import PanelBase


class PanelFPU(PanelBase):
    """Calculadora reactiva y visor de campos de la FPU de 64 bits."""

    NOMBRE = "fpu"
    TITULO = "Unidad de punto flotante"
    SUBTITULO = "IEEE 754 doble precision  ·  enigma64.fpu"
    ACENTO = PALETA["cian"]
    CLAVE_SERVICIO = "fpu"
    TAMANO_SUELTO = (900, 850)
    DESPLAZABLE_SUELTO = True

    #: Espera tras la ultima tecla antes de volver a ejecutar la rutina.
    RETARDO_MS = 140

    #: Casos que vale la pena ensenar: (rotulo, operacion, A, B).
    CASOS = (
        ("10.5 + 20.2", "FADD", "10.5", "20.2"),
        ("0.1 + 0.2", "FADD", "0.1", "0.2"),
        ("1 / 3", "FDIV", "1", "3"),
        ("1 / 0", "FDIV", "1", "0"),
        ("0 / 0", "FDIV", "0", "0"),
        ("max x 2", "FMUL", "1.7976931348623157e308", "2"),
        ("subnormal", "FDIV", "0x0010000000000000", "4"),
        ("-0 ? +0", "FCMP", "-0.0", "0.0"),
        ("NaN ? 1", "FCMP", "nan", "1"),
    )

    #: Diodos de condicion del resultado, en orden de presentacion.
    CONDICIONES = (
        ("CERO", "ok"), ("NEGATIVO", "violeta"), ("SUBNORMAL", "alerta"),
        ("INFINITO", "alerta"), ("NaN", "fallo"), ("INEXACTO", "cian"),
    )

    VISTAS = (("A", "Operando A"), ("B", "Operando B"), ("R", "Resultado"))

    def construir(self) -> None:
        self.operacion = tk.StringVar(value="FADD")
        self.operando_a = tk.StringVar(value="10.5")
        self.operando_b = tk.StringVar(value="20.2")
        self.vista = tk.StringVar(value="R")

        self._botones_op = {}
        self._botones_vista = {}
        self._leds = {}
        self._pendiente = None
        self._silenciado = False
        self._ultimo_registrado = None
        #: Ultimo calculo valido; None mientras haya un error de entrada.
        self.resultado = None
        #: Patrones de 64 bits vigentes de cada vista del visor.
        self._patrones = {"A": None, "B": None, "R": None}

        self._construir_operaciones()
        self.separador()
        self._construir_operandos()
        self._construir_resultado()
        self._construir_visor()
        self._construir_hoja_de_ruta()
        self._construir_historial()

        self.operando_a.trace_add("write", self._al_escribir)
        self.operando_b.trace_add("write", self._al_escribir)
        self._resaltar_operacion()

    # -- construccion -------------------------------------------------------

    def _construir_operaciones(self) -> None:
        self.rotulo(self.cuerpo, "Operacion").pack(anchor="w", pady=(0, 6))

        for familia, operaciones in self.servicio.operaciones_por_familia().items():
            if not operaciones:
                continue
            fila = self.fila()
            fila.pack(fill="x", pady=1)
            tk.Label(fila, text=familia, bg=PALETA["elevado"],
                     fg=PALETA["texto_debil"], font=sans(8), width=15,
                     anchor="w").pack(side="left")

            for operacion in operaciones:
                boton = tk.Label(fila, text=operacion, bg=PALETA["abismo"],
                                 fg=PALETA["texto_tenue"], font=mono(9, True),
                                 padx=9, pady=3, cursor="hand2",
                                 highlightthickness=1,
                                 highlightbackground=PALETA["borde"])
                boton.pack(side="left", padx=2)
                boton.bind("<Button-1>",
                           lambda _e, op=operacion: self.elegir_operacion(op))
                self._botones_op[operacion] = boton

        self.detalle_operacion = tk.Label(
            self.cuerpo, text="", bg=PALETA["elevado"], fg=PALETA["texto_debil"],
            font=sans(8), anchor="w")
        self.detalle_operacion.pack(fill="x", pady=(6, 0))

    def _construir_operandos(self) -> None:
        fila = self.fila()
        fila.pack(fill="x")

        columna_a = tk.Frame(fila, bg=PALETA["elevado"])
        columna_a.pack(side="left", fill="x", expand=True)
        self.rotulo_a = self.rotulo(columna_a, "Operando A")
        self.rotulo_a.pack(anchor="w")
        self.entrada_a = ttk.Entry(columna_a, textvariable=self.operando_a,
                                   font=mono(10))
        self.entrada_a.pack(fill="x")
        self.lectura_a = self.texto_dato(columna_a, "", PALETA["texto_debil"], 8)
        self.lectura_a.pack(anchor="w", pady=(2, 0))

        columna_b = tk.Frame(fila, bg=PALETA["elevado"])
        columna_b.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.rotulo_b = self.rotulo(columna_b, "Operando B")
        self.rotulo_b.pack(anchor="w")
        self.entrada_b = ttk.Entry(columna_b, textvariable=self.operando_b,
                                   font=mono(10))
        self.entrada_b.pack(fill="x")
        self.lectura_b = self.texto_dato(columna_b, "", PALETA["texto_debil"], 8)
        self.lectura_b.pack(anchor="w", pady=(2, 0))

        casos = self.fila()
        casos.pack(fill="x", pady=(MARGEN_CHICO, 0))
        tk.Label(casos, text="Casos", bg=PALETA["elevado"],
                 fg=PALETA["texto_debil"], font=sans(8), width=15,
                 anchor="w").pack(side="left")
        for rotulo, operacion, a, b in self.CASOS:
            boton = tk.Label(casos, text=rotulo, bg=PALETA["elevado_alto"],
                             fg=PALETA["texto_tenue"], font=mono(8), padx=6, pady=2,
                             cursor="hand2")
            boton.pack(side="left", padx=2)
            boton.bind("<Button-1>", lambda _e, op=operacion, x=a, y=b:
                       self.cargar_caso(op, x, y))
        ttk.Button(casos, text="Intercambiar A/B",
                   command=self.intercambiar).pack(side="right")

    def _construir_resultado(self) -> None:
        marco = tk.Frame(self.cuerpo, bg=PALETA["borde"])
        marco.pack(fill="x", pady=(MARGEN, 0))
        interior = tk.Frame(marco, bg=PALETA["abismo"])
        interior.pack(fill="x", padx=1, pady=1)

        linea = tk.Frame(interior, bg=PALETA["abismo"])
        linea.pack(fill="x", padx=12, pady=(10, 0))
        self.expresion = tk.Label(linea, text="", bg=PALETA["abismo"],
                                  fg=PALETA["texto_debil"], font=mono(10, True))
        self.expresion.pack(side="left", padx=(0, 10))
        self.salida_valor = tk.Label(linea, text="—", bg=PALETA["abismo"],
                                     fg=PALETA["cian"], font=mono(15, True))
        self.salida_valor.pack(side="left")
        self.insignia = Insignia(linea, ancho=196, fondo=PALETA["abismo"])
        self.insignia.pack(side="right")

        self.salida_hex = tk.Label(interior, text="", bg=PALETA["abismo"],
                                   fg=PALETA["texto_tenue"], font=mono(9), anchor="w")
        self.salida_hex.pack(fill="x", padx=12, pady=(4, 0))
        self.salida_referencia = tk.Label(
            interior, text="", bg=PALETA["abismo"], fg=PALETA["texto_debil"],
            font=mono(9), anchor="w")
        self.salida_referencia.pack(fill="x", padx=12, pady=(0, 10))

        fila_leds = self.fila()
        fila_leds.pack(anchor="w", pady=(MARGEN, 0))
        for nombre, color in self.CONDICIONES:
            led = Led(fila_leds, nombre, color=PALETA[color])
            led.pack(side="left", padx=(0, 18))
            self._leds[nombre] = led

    def _construir_visor(self) -> None:
        cabecera = self.fila()
        cabecera.pack(fill="x", pady=(MARGEN, 6))
        self.rotulo(cabecera, "Visor IEEE 754").pack(side="left", padx=(0, 12))
        for clave, texto in self.VISTAS:
            boton = tk.Label(cabecera, text=texto, bg=PALETA["abismo"],
                             fg=PALETA["texto_tenue"], font=sans(8, True),
                             padx=9, pady=3, cursor="hand2", highlightthickness=1,
                             highlightbackground=PALETA["borde"])
            boton.pack(side="left", padx=2)
            boton.bind("<Button-1>", lambda _e, v=clave: self.elegir_vista(v))
            self._botones_vista[clave] = boton
        self.pista_visor = tk.Label(cabecera, text="", bg=PALETA["elevado"],
                                    fg=PALETA["texto_debil"], font=sans(8))
        self.pista_visor.pack(side="right")

        self.visor = VisorIEEE754(self.cuerpo, al_pulsar=self._al_pulsar_bit)
        self.visor.pack(fill="x")

        desglose = tk.Frame(self.cuerpo, bg=PALETA["elevado"])
        desglose.pack(fill="x", pady=(2, 0))
        self._campos = {}
        for fila, (clave, rotulo, color) in enumerate((
                ("signo", "Signo", "violeta"),
                ("exponente", "Exponente", "ambar"),
                ("mantisa", "Mantisa", "cian"),
                ("valor", "Valor", "texto"))):
            tk.Label(desglose, text=rotulo, bg=PALETA["elevado"], fg=PALETA[color],
                     font=sans(8, True), width=15, anchor="w").grid(
                         row=fila, column=0, sticky="w")
            campo = tk.Label(desglose, text="", bg=PALETA["elevado"],
                             fg=PALETA["texto_tenue"], font=mono(9), anchor="w")
            campo.grid(row=fila, column=1, sticky="w")
            self._campos[clave] = campo

    def _construir_hoja_de_ruta(self) -> None:
        self.rotulo(self.cuerpo, "Rutinas de la biblioteca").pack(
            anchor="w", pady=(MARGEN, 6))
        fila = self.fila()
        fila.pack(fill="x")
        self._insignias_ruta = {}
        for pieza in self.servicio.hoja_de_ruta():
            texto = pieza["titulo"].upper()
            insignia = Insignia(fila, ancho=16 + len(texto) * 8, alto=20)
            insignia.fijar(texto,
                           PALETA["ok"] if pieza["conectada"] else PALETA["alerta"])
            insignia.pack(side="left", padx=(0, 4))
            self._insignias_ruta[pieza["clave"]] = insignia

        pendientes = [f"{p['titulo']} ({p['autor']})"
                      for p in self.servicio.hoja_de_ruta() if not p["conectada"]]
        self.nota_ruta = tk.Label(
            self.cuerpo, bg=PALETA["elevado"], fg=PALETA["texto_debil"],
            font=sans(8), anchor="w", justify="left", wraplength=760,
            text=("En verde lo conectado. Pendiente: " + ", ".join(pendientes) + "."
                  if pendientes else "Toda la biblioteca esta conectada."))
        self.nota_ruta.pack(fill="x", pady=(4, 0))

    def _construir_historial(self) -> None:
        self.rotulo(self.cuerpo, "Historial de ejecucion").pack(anchor="w",
                                                                pady=(MARGEN, 6))
        self.historial = TextoMono(self.cuerpo, alto=4, ancho=64, tam=9)
        self.historial.pack(fill="both", expand=True)
        self.historial.configurar_etiqueta("ok", foreground=PALETA["texto_tenue"])
        self.historial.configurar_etiqueta("aviso", foreground=PALETA["alerta"])
        self.historial.configurar_etiqueta("error", foreground=PALETA["fallo"])

    # -- acciones -----------------------------------------------------------

    def elegir_operacion(self, operacion: str) -> None:
        self.operacion.set(operacion)
        self._resaltar_operacion()
        self.recalcular()

    def elegir_vista(self, vista: str) -> None:
        if vista in self._vistas_disponibles():
            self.vista.set(vista)
        self._pintar_visor()

    def intercambiar(self) -> None:
        a, b = self.operando_a.get(), self.operando_b.get()
        self._fijar_operandos(b, a)
        self.recalcular()

    def cargar_caso(self, operacion: str, a: str, b: str) -> None:
        self._fijar_operandos(a, b)
        self.elegir_operacion(operacion)

    def recalcular(self) -> None:
        """Vuelve a ejecutar la rutina con lo que haya escrito en los campos."""
        self._cancelar_pendiente()
        operacion = self.operacion.get()
        datos = self.servicio.descripcion(operacion)

        try:
            a = self._leer_operando(self.operando_a.get(), datos["entrada"], "A")
            b = 0 if datos["unaria"] else self._leer_operando(
                self.operando_b.get(), "flotante", "B")
        except ValorInvalido as exc:
            self._pintar_error(str(exc))
            return

        try:
            resultado = self.servicio.ejecutar(operacion, a, b)
        except Exception as exc:
            # La rutina es codigo del equipo corriendo en la CPU emulada: si
            # falla, el panel lo cuenta y sigue en pie.
            self._pintar_error(f"{operacion}: {type(exc).__name__}: {exc}")
            self.trazar(f"{operacion}: {type(exc).__name__}: {exc}", "error")
            return

        self.resultado = resultado
        self._pintar_resultado(resultado)
        self._registrar(resultado)

    # -- reactividad --------------------------------------------------------

    def _al_escribir(self, *_args) -> None:
        if self._silenciado:
            return
        self._cancelar_pendiente()
        self._pendiente = self.after(self.RETARDO_MS, self.recalcular)

    def _cancelar_pendiente(self) -> None:
        if self._pendiente is not None:
            try:
                self.after_cancel(self._pendiente)
            except tk.TclError:  # pragma: no cover - la ventana ya no existe
                pass
            self._pendiente = None

    def _fijar_operandos(self, a: str, b: str) -> None:
        """Cambia los dos campos sin disparar dos recalculos intermedios."""
        self._silenciado = True
        try:
            self.operando_a.set(a)
            self.operando_b.set(b)
        finally:
            self._silenciado = False

    def _leer_operando(self, texto: str, tipo: str, nombre: str) -> int:
        try:
            if tipo == "entero":
                valor = parsear_entero(texto)
                if not -(1 << 63) <= valor <= MASCARA_64:
                    raise ValorInvalido(f"{texto.strip()!r} no cabe en 64 bits")
                return valor & MASCARA_64
            return parsear_ieee754(texto)
        except ValorInvalido as exc:
            raise ValorInvalido(f"Operando {nombre}: {exc}") from None

    def _al_pulsar_bit(self, indice: int) -> None:
        """Conmutar un bit del visor reescribe el operando que se esta viendo."""
        vista = self.vista.get()
        patron = self._patrones.get(vista)
        if vista not in ("A", "B") or patron is None:
            return
        nuevo = patron ^ (1 << indice)
        variable = self.operando_a if vista == "A" else self.operando_b
        escrito_en_hex = variable.get().strip().lower().startswith("0x")
        if escrito_en_hex or clasificar_ieee754(nuevo) == "NaN":
            variable.set(hex64(nuevo))      # un NaN solo se identifica por su patron
        else:
            variable.set(texto_flotante(nuevo))
        self.recalcular()

    # -- pintado ------------------------------------------------------------

    def _resaltar_operacion(self) -> None:
        activa = self.operacion.get()
        for operacion, boton in self._botones_op.items():
            encendido = operacion == activa
            conectada = self.servicio.esta_conectada(operacion)
            apagado = PALETA["texto_tenue"] if conectada else PALETA["alerta"]
            boton.configure(
                bg=PALETA["ambar"] if encendido else PALETA["abismo"],
                fg=PALETA["abismo"] if encendido else apagado,
                highlightbackground=PALETA["ambar"] if encendido else PALETA["borde"])

        datos = self.servicio.descripcion(activa)
        estado = (f"entra por {datos['punto_entrada']}" if datos["conectada"]
                  else "rutina pendiente de entrega")
        self.detalle_operacion.configure(
            text=f"{activa}  ·  {datos['descripcion']}  ·  {datos['autor']}  ·  {estado}",
            fg=PALETA["texto_debil"] if datos["conectada"] else PALETA["alerta"])

        self.rotulo_a.configure(
            text="OPERANDO A  ·  ENTERO CON SIGNO" if datos["entrada"] == "entero"
            else "OPERANDO A  ·  DECIMAL O PATRON 0x")
        self.entrada_b.configure(state="disabled" if datos["unaria"] else "normal")
        self.rotulo_b.configure(
            text="OPERANDO B (NO USADO)" if datos["unaria"]
            else "OPERANDO B  ·  DECIMAL O PATRON 0x")

    def _vistas_disponibles(self) -> tuple:
        """Solo se puede desglosar lo que de verdad es un flotante."""
        if self.resultado is None:
            return ()
        vistas = []
        if self.resultado["tipo_entrada"] == "flotante":
            vistas.append("A")
        if not self.resultado["unaria"]:
            vistas.append("B")
        if (self.resultado["tipo_salida"] == "flotante"
                and self.resultado["resultado"] is not None):
            vistas.append("R")
        return tuple(vistas)

    def _pintar_resultado(self, resultado: dict) -> None:
        operacion = resultado["operacion"]
        texto_a = (str(con_signo(resultado["a"]))
                   if resultado["tipo_entrada"] == "entero"
                   else texto_flotante(resultado["a"]))
        if resultado["unaria"]:
            self.expresion.configure(text=f"{resultado['simbolo']}({texto_a})  =")
        else:
            self.expresion.configure(
                text=f"{texto_a}  {resultado['simbolo']}  "
                     f"{texto_flotante(resultado['b'])}  =")

        self.lectura_a.configure(text=self._lectura(resultado["a"],
                                                    resultado["tipo_entrada"]))
        self.lectura_b.configure(
            text="" if resultado["unaria"] else self._lectura(resultado["b"], "flotante"))

        referencia = resultado["texto_referencia"]
        if not resultado["conectada"]:
            self.salida_valor.configure(text="—", fg=PALETA["texto_debil"])
            self.salida_hex.configure(
                text=f"{operacion} todavia no esta en la biblioteca "
                     f"({resultado['autor']}).")
            self.salida_referencia.configure(
                text=f"IEEE 754 del anfitrion: {referencia}   "
                     f"{hex64(resultado['referencia'])}" if referencia else "")
            self.insignia.fijar("RUTINA PENDIENTE", PALETA["alerta"])
        else:
            self.salida_valor.configure(text=resultado["texto"], fg=PALETA["cian"])
            self.salida_hex.configure(
                text=f"{resultado['hex']}   ·   {resultado['ciclos']} ciclos de reloj"
                     f"   ·   {resultado['punto_entrada']}")
            if resultado["coincide"] is None:
                self.salida_referencia.configure(
                    text="IEEE 754 no fija un resultado unico para este caso.")
                self.insignia.fijar("SIN REFERENCIA", PALETA["texto_tenue"])
            elif resultado["coincide"]:
                self.salida_referencia.configure(
                    text=f"IEEE 754 del anfitrion: {referencia}")
                self.insignia.fijar("COINCIDE CON IEEE 754", PALETA["ok"])
            else:
                self.salida_referencia.configure(
                    text=f"IEEE 754 del anfitrion: {referencia}   "
                         f"{hex64(resultado['referencia'])}")
                self.insignia.fijar("DIFIERE DE IEEE 754", PALETA["alerta"])

        self._pintar_condiciones(resultado)
        self._patrones = {
            "A": resultado["a"] if resultado["tipo_entrada"] == "flotante" else None,
            "B": None if resultado["unaria"] else resultado["b"],
            "R": (resultado["resultado"]
                  if resultado["tipo_salida"] == "flotante" else None),
        }
        disponibles = self._vistas_disponibles()
        if self.vista.get() not in disponibles and disponibles:
            self.vista.set("R" if "R" in disponibles else disponibles[0])
        self._pintar_visor()

    def _pintar_condiciones(self, resultado: dict) -> None:
        patron = resultado["resultado"]
        tipo = resultado["tipo_salida"]
        estado = dict.fromkeys(self._leds, False)
        if patron is not None and tipo == "flotante":
            clase = clasificar_ieee754(patron)
            estado.update({
                "CERO": clase == "cero",
                "NEGATIVO": bool(patron >> 63) and clase != "NaN",
                "SUBNORMAL": clase == "subnormal",
                "INFINITO": clase == "infinito",
                "NaN": clase == "NaN",
            })
        elif patron is not None and tipo == "entero":
            estado.update({"CERO": patron == 0, "NEGATIVO": bool(patron >> 63)})
        estado["INEXACTO"] = bool(resultado["inexacto"])
        for nombre, led in self._leds.items():
            led.fijar(estado[nombre])

    def _pintar_visor(self) -> None:
        disponibles = self._vistas_disponibles()
        activa = self.vista.get()
        for clave, boton in self._botones_vista.items():
            encendido = clave == activa and clave in disponibles
            boton.configure(
                bg=PALETA["cian"] if encendido else PALETA["abismo"],
                fg=(PALETA["abismo"] if encendido else
                    PALETA["texto_tenue"] if clave in disponibles
                    else PALETA["borde"]),
                highlightbackground=PALETA["cian"] if encendido else PALETA["borde"])

        patron = self._patrones.get(activa) if activa in disponibles else None
        if patron is None:
            self.visor.fijar(0, editable=False)
            self.pista_visor.configure(text="no hay un flotante que desglosar")
            for campo in self._campos.values():
                campo.configure(text="—")
            return

        try:
            d = self.servicio.descomponer(patron)
        except Exception as exc:
            self.pista_visor.configure(text=f"FPU_DESEMPAQUETAR fallo: {exc}")
            return

        editable = activa in ("A", "B")
        self.visor.fijar(patron, implicito=d["implicito"], editable=editable)
        self.pista_visor.configure(
            text=f"FPU_DESEMPAQUETAR  ·  {d['ciclos']} ciclos"
                 + ("  ·  pulsa un bit para conmutarlo" if editable else ""))

        self._campos["signo"].configure(
            text=f"{d['signo']}   →  {'negativo' if d['signo'] else 'positivo'}")
        if d["exponente_real"] is None:
            detalle = "todo unos: infinito o NaN" if d["exponente"] else "cero"
        elif d["exponente"] == 0:
            detalle = "subnormal: exponente efectivo 1 - 1023 = -1022"
        else:
            detalle = f"{d['exponente']} - 1023 = {d['exponente_real']}"
        self._campos["exponente"].configure(
            text=f"0x{d['exponente']:03X} = {d['exponente']}   →  {detalle}")
        self._campos["mantisa"].configure(
            text=f"0x{d['fraccion']:013X}   →  con el bit implicito "
                 f"{d['implicito']}:  0x{d['mantisa']:014X}")
        self._campos["valor"].configure(text=self._formula(d))

    @staticmethod
    def _formula(d: dict) -> str:
        """(-1)^s x 1.f x 2^e, o el nombre de la clase si no es un numero finito."""
        if d["exponente_real"] is None:
            return f"{d['texto']}   ({d['clase']})"
        significando = d["mantisa"] / float(1 << 52)
        signo = "-" if d["signo"] else "+"
        return (f"{signo}{significando!r} x 2^{d['exponente_real']}  =  {d['texto']}"
                f"   ({d['clase']})")

    @staticmethod
    def _lectura(patron: int, tipo: str) -> str:
        if tipo == "entero":
            return f"{hex64(patron)}  ·  entero {con_signo(patron)}"
        return f"{hex64(patron)}  ·  {clasificar_ieee754(patron)}"

    def _pintar_error(self, texto: str) -> None:
        self.resultado = None
        self._patrones = {"A": None, "B": None, "R": None}
        self.expresion.configure(text="")
        self.salida_valor.configure(text="—", fg=PALETA["texto_debil"])
        self.salida_hex.configure(text=texto)
        self.salida_referencia.configure(text="")
        self.insignia.fijar("ENTRADA NO VALIDA", PALETA["fallo"])
        self.lectura_a.configure(text="")
        self.lectura_b.configure(text="")
        for led in self._leds.values():
            led.apagar()
        self._pintar_visor()

    def _registrar(self, resultado: dict) -> None:
        """Anota el calculo y lo publica, una sola vez por combinacion nueva."""
        clave = (resultado["operacion"], resultado["a"], resultado["b"])
        if clave == self._ultimo_registrado:
            return
        self._ultimo_registrado = clave

        expresion = self.expresion.cget("text")
        if not resultado["conectada"]:
            linea = f"{expresion} (pendiente; referencia {resultado['texto_referencia']})"
            etiqueta, severidad = "aviso", "aviso"
        else:
            linea = (f"{expresion} {resultado['texto']}  [{resultado['hex']}]  "
                     f"{resultado['ciclos']} ciclos")
            if resultado["coincide"] is False:
                linea += f"  DIFIERE (IEEE: {resultado['texto_referencia']})"
                etiqueta, severidad = "aviso", "aviso"
            else:
                etiqueta, severidad = "ok", "dato"
        self.historial.anexar(f"  {resultado['operacion']:<5} {linea}\n", etiqueta)
        self.trazar(f"{resultado['operacion']} {linea}", severidad)
        self.publicar(Evento.FPU_EJECUTADA, **resultado)

    # -- demostracion suelta ------------------------------------------------

    def preparar_demo(self) -> None:
        if self.servicio is not None and self.servicio.disponible:
            self.recalcular()


if __name__ == "__main__":
    PanelFPU.ejecutar_suelto()
