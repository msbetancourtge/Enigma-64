"""
Panel de registros y banderas en Tkinter para el Enigma-64.

Contiene dos cosas:

  PanelRegistros : un Frame reutilizable que pinta R0..R7, PC, SR y las siete
                   banderas. Se suscribe al BancoRegistros y se refresca solo.
                   El Integrante 5 puede usarlo en la ventana principal:

                       panel = PanelRegistros(ventana_principal, banco)
                       panel.pack(side="left", fill="y")

  BancoPruebasALU: una ventanita independiente para disparar operaciones de la
                   ALU a mano y ver como cambian registros y banderas. Sirve
                   para demostrar el modulo sin depender de que la CPU y la RAM
                   esten listas.

Ejecutar la demo:  python3 panel_registros.py
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from enigma64 import ALU, BancoRegistros, DivisionPorCero, OperacionInvalida
from enigma64.alu import TABLA_OPERACIONES
from enigma64.registros import (
    ALIAS_ROL,
    CODIGO_POR_NOMBRE,
    NOMBRE_POR_CODIGO,
    ORDEN_BANDERAS,
    a_con_signo,
    hex64,
)

MONO = ("Consolas", 10)
MONO_BOLD = ("Consolas", 10, "bold")

COLOR_ACTIVA = "#2e7d32"
COLOR_INACTIVA = "#9e9e9e"
COLOR_CAMBIO = "#ffe082"


class PanelRegistros(ttk.Frame):
    """Vista en vivo del banco de registros. Se refresca por suscripcion."""

    def __init__(self, maestro, banco: BancoRegistros, **kwargs):
        super().__init__(maestro, padding=8, **kwargs)
        self.banco = banco
        self._etiquetas_valor: dict[str, ttk.Label] = {}
        self._etiquetas_bandera: dict[str, tk.Label] = {}
        self._valores_previos: dict[str, int] = {}

        self._construir_tabla()
        self._construir_banderas()

        banco.suscribir(self.refrescar)
        self.refrescar(banco)

    # -- construccion -------------------------------------------------------

    def _construir_tabla(self) -> None:
        cuadro = ttk.LabelFrame(self, text="Registros (64 bits)", padding=6)
        cuadro.pack(fill="x")

        ttk.Label(cuadro, text="Reg", font=MONO_BOLD, width=9).grid(
            row=0, column=0, sticky="w")
        ttk.Label(cuadro, text="Cod", font=MONO_BOLD, width=5).grid(
            row=0, column=1, sticky="w")
        ttk.Label(cuadro, text="Hexadecimal", font=MONO_BOLD, width=20).grid(
            row=0, column=2, sticky="w")
        ttk.Label(cuadro, text="Decimal (con signo)", font=MONO_BOLD).grid(
            row=0, column=3, sticky="w")

        for fila, (codigo, nombre) in enumerate(NOMBRE_POR_CODIGO.items(), start=1):
            alias = ALIAS_ROL.get(codigo)
            etiqueta = f"{nombre} ({alias})" if alias else nombre
            ttk.Label(cuadro, text=etiqueta, font=MONO).grid(
                row=fila, column=0, sticky="w")
            ttk.Label(cuadro, text=f"0x{codigo:X}", font=MONO).grid(
                row=fila, column=1, sticky="w")

            valor_hex = ttk.Label(cuadro, text="", font=MONO, width=20)
            valor_hex.grid(row=fila, column=2, sticky="w")

            valor_dec = ttk.Label(cuadro, text="", font=MONO)
            valor_dec.grid(row=fila, column=3, sticky="w")

            self._etiquetas_valor[nombre] = valor_hex
            self._etiquetas_valor[nombre + "_dec"] = valor_dec

    def _construir_banderas(self) -> None:
        cuadro = ttk.LabelFrame(self, text="Banderas (SR)", padding=6)
        cuadro.pack(fill="x", pady=(8, 0))

        descripcion = {
            "Z": "Zero", "N": "Negative", "C": "Carry", "V": "oVerflow",
            "M": "Misaligned", "I": "Interrupt", "S": "Supervisor",
        }
        for columna, nombre in enumerate(ORDEN_BANDERAS):
            caja = tk.Frame(cuadro, bd=1, relief="solid", padx=6, pady=3)
            caja.grid(row=0, column=columna, padx=2)
            etiqueta = tk.Label(caja, text=f"{nombre}\n0", font=MONO_BOLD,
                                fg=COLOR_INACTIVA)
            etiqueta.pack()
            self._etiquetas_bandera[nombre] = etiqueta
            caja.bind("<Enter>", lambda _e, d=descripcion[nombre]: self._tip(d))

        self._linea_tip = ttk.Label(cuadro, text="", font=("Segoe UI", 8))
        self._linea_tip.grid(row=1, column=0, columnspan=len(ORDEN_BANDERAS),
                             sticky="w", pady=(4, 0))

    def _tip(self, texto: str) -> None:
        self._linea_tip.config(text=texto)

    # -- refresco -----------------------------------------------------------

    def refrescar(self, banco: BancoRegistros | None = None) -> None:
        banco = banco or self.banco
        snap = banco.snapshot()

        for nombre, datos in snap["registros"].items():
            valor = datos["valor"]
            cambio = self._valores_previos.get(nombre) not in (None, valor)
            self._etiquetas_valor[nombre].config(
                text=datos["hex"],
                background=COLOR_CAMBIO if cambio else "",
            )
            self._etiquetas_valor[nombre + "_dec"].config(
                text=f"{datos['con_signo']:,}".replace(",", " ")
            )
            self._valores_previos[nombre] = valor

        for nombre, valor in snap["banderas"].items():
            self._etiquetas_bandera[nombre].config(
                text=f"{nombre}\n{valor}",
                fg=COLOR_ACTIVA if valor else COLOR_INACTIVA,
            )


class BancoPruebasALU(ttk.Frame):
    """Controles para disparar operaciones de la ALU sobre el banco."""

    def __init__(self, maestro, banco: BancoRegistros, alu: ALU, **kwargs):
        super().__init__(maestro, padding=8, **kwargs)
        self.banco = banco
        self.alu = alu
        self._construir()

    def _construir(self) -> None:
        cargar = ttk.LabelFrame(self, text="Cargar un registro", padding=6)
        cargar.pack(fill="x")

        self.reg_destino_carga = tk.StringVar(value="R1")
        self.valor_carga = tk.StringVar(value="0x0000000000000005")

        ttk.Combobox(cargar, textvariable=self.reg_destino_carga, width=5,
                     state="readonly",
                     values=list(NOMBRE_POR_CODIGO.values())).grid(row=0, column=0)
        ttk.Entry(cargar, textvariable=self.valor_carga, font=MONO,
                  width=22).grid(row=0, column=1, padx=4)
        ttk.Button(cargar, text="Cargar",
                   command=self._cargar).grid(row=0, column=2)

        operar = ttk.LabelFrame(self, text="Ejecutar operacion de la ALU", padding=6)
        operar.pack(fill="x", pady=(8, 0))

        self.operacion = tk.StringVar(value="ADD")
        self.reg_a = tk.StringVar(value="R1")
        self.reg_b = tk.StringVar(value="R2")
        self.reg_d = tk.StringVar(value="R3")
        self.usar_inmediato = tk.BooleanVar(value=False)
        self.inmediato = tk.StringVar(value="1")

        registros = list(NOMBRE_POR_CODIGO.values())

        ttk.Label(operar, text="Op").grid(row=0, column=0)
        ttk.Combobox(operar, textvariable=self.operacion, width=6, state="readonly",
                     values=sorted(TABLA_OPERACIONES)).grid(row=0, column=1, padx=2)

        ttk.Label(operar, text="Rd").grid(row=0, column=2)
        ttk.Combobox(operar, textvariable=self.reg_d, width=5, state="readonly",
                     values=registros).grid(row=0, column=3, padx=2)

        ttk.Label(operar, text="Rs1").grid(row=0, column=4)
        ttk.Combobox(operar, textvariable=self.reg_a, width=5, state="readonly",
                     values=registros).grid(row=0, column=5, padx=2)

        ttk.Label(operar, text="Rs2").grid(row=0, column=6)
        self.combo_b = ttk.Combobox(operar, textvariable=self.reg_b, width=5,
                                    state="readonly", values=registros)
        self.combo_b.grid(row=0, column=7, padx=2)

        ttk.Checkbutton(operar, text="usar inmediato", variable=self.usar_inmediato,
                        command=self._alternar_inmediato).grid(row=1, column=0,
                                                               columnspan=3, sticky="w")
        self.entrada_inmediato = ttk.Entry(operar, textvariable=self.inmediato,
                                           font=MONO, width=10, state="disabled")
        self.entrada_inmediato.grid(row=1, column=3, columnspan=2, sticky="w")

        ttk.Button(operar, text="Ejecutar",
                   command=self._ejecutar).grid(row=1, column=6, columnspan=2)

        acciones = ttk.Frame(self)
        acciones.pack(fill="x", pady=(8, 0))
        ttk.Button(acciones, text="RESET",
                   command=self._reset).pack(side="left")

        self.bitacora = tk.Text(self, height=9, font=MONO, wrap="none")
        self.bitacora.pack(fill="both", expand=True, pady=(8, 0))
        self._log("Enigma-64 listo. R0 esta cableado a cero.")

    def _alternar_inmediato(self) -> None:
        activo = self.usar_inmediato.get()
        self.entrada_inmediato.config(state="normal" if activo else "disabled")
        self.combo_b.config(state="disabled" if activo else "readonly")

    def _log(self, texto: str) -> None:
        self.bitacora.insert("end", texto + "\n")
        self.bitacora.see("end")

    @staticmethod
    def _interpretar(texto: str) -> int:
        texto = texto.strip().replace("_", "")
        return int(texto, 0)

    def _cargar(self) -> None:
        try:
            valor = self._interpretar(self.valor_carga.get())
        except ValueError:
            messagebox.showerror("Valor invalido",
                                 "Escriba un entero decimal o 0x... hexadecimal.")
            return
        nombre = self.reg_destino_carga.get()
        self.banco.escribir_nombre(nombre, valor)
        if nombre == "R0":
            self._log("R0 ignoro la escritura (cableado a cero).")
        else:
            self._log(f"{nombre} <- {hex64(valor)}")

    def _reset(self) -> None:
        self.banco.reset()
        self._log("RESET: PC=0, SP=0x00000000EFFFFFFF")

    def _ejecutar(self) -> None:
        op = self.operacion.get()
        a = self.banco.leer_nombre(self.reg_a.get())

        if self.usar_inmediato.get():
            try:
                b = self._interpretar(self.inmediato.get())
            except ValueError:
                messagebox.showerror("Inmediato invalido", "Use decimal o 0x...")
                return
            origen_b = f"#{b}"
        else:
            b = self.banco.leer_nombre(self.reg_b.get())
            origen_b = self.reg_b.get()

        try:
            resultado = self.alu.ejecutar(op, a, b)
        except DivisionPorCero:
            self._log(f"{op}: EXCEPCION - division por cero, la CU debe atraparla.")
            return
        except OperacionInvalida as exc:
            messagebox.showerror("Operacion invalida", str(exc))
            return

        self.banco.aplicar_banderas(resultado.banderas, resultado.afectadas)

        if resultado.escribe_destino:
            destino = self.reg_d.get()
            self.banco.escribir_nombre(destino, resultado.valor)
            texto_destino = f"{destino} <- "
        else:
            texto_destino = "(sin escritura) "

        banderas = " ".join(
            f"{b}={resultado.banderas[b]}"
            for b in ("Z", "N", "C", "V")
            if b in resultado.afectadas
        )
        self._log(
            f"{op:<5} {self.reg_a.get()}={hex64(a)} {origen_b}  ->  "
            f"{texto_destino}{resultado.hex}  [{banderas}]"
        )


def main() -> None:
    banco = BancoRegistros()
    alu = ALU()

    raiz = tk.Tk()
    raiz.title("Enigma-64 - Registros & ALU (Integrante 2)")
    raiz.resizable(False, False)

    contenedor = ttk.Frame(raiz)
    contenedor.pack(fill="both", expand=True)

    PanelRegistros(contenedor, banco).pack(side="left", fill="y")
    ttk.Separator(contenedor, orient="vertical").pack(side="left", fill="y", padx=4)
    BancoPruebasALU(contenedor, banco, alu).pack(side="left", fill="both", expand=True)

    raiz.mainloop()


if __name__ == "__main__":
    main()
