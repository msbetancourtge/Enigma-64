"""
Pruebas del panel de la Unidad de Punto Flotante y de su adaptador.

Se dividen en tres bloques: el formato IEEE 754 (sin hardware ni ventanas), el
adaptador sobre la biblioteca en ensamblador del equipo y el panel con widgets
reales. Este ultimo necesita un servidor grafico; donde no lo haya se omite y
los otros dos bloques siguen corriendo.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import math
import tkinter as tk

import pytest

from enigma64.ui.core.bus import BusEventos, Evento
from enigma64.ui.core.formato import (
    ValorInvalido, bits_a_flotante, campos_ieee754, clasificar_ieee754,
    flotante_a_bits, parsear_ieee754, texto_flotante,
)
from enigma64.ui.core.tema import aplicar_tema
from enigma64.ui.servicios import AdaptadorFPU, PuertoFPU, construir_maquina

MENOS_UNO = 0xFFFFFFFFFFFFFFFF


# ---------------------------------------------------------------------------
# Formato IEEE 754
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("texto, patron", [
    ("10.5", 0x4025000000000000),
    ("-0.0", 0x8000000000000000),
    ("1e-324", 0x0000000000000000),
    ("0x4025000000000000", 0x4025000000000000),
    ("0x4025_0000_0000_0000", 0x4025000000000000),
    ("inf", 0x7FF0000000000000),
    ("-INF", 0xFFF0000000000000),
    ("nan", 0x7FF8000000000000),
    (" 1 ", 0x3FF0000000000000),
])
def test_parsear_ieee754(texto, patron):
    assert parsear_ieee754(texto) == patron


@pytest.mark.parametrize("texto", ["", "   ", "diez", "0x1_0000_0000_0000_0000", "1,5"])
def test_parsear_ieee754_rechaza_lo_que_no_es_un_flotante(texto):
    with pytest.raises(ValorInvalido):
        parsear_ieee754(texto)


def test_los_campos_separan_signo_exponente_y_fraccion():
    campos = campos_ieee754(0xC025000000000000)        # -10.5
    assert campos == {"signo": 1, "exponente": 0x402,
                      "fraccion": 0x5000000000000, "implicito": 1}
    assert campos_ieee754(0x0000000000000001)["implicito"] == 0   # subnormal


@pytest.mark.parametrize("patron, clase", [
    (0x0000000000000000, "cero"),
    (0x8000000000000000, "cero"),
    (0x0000000000000001, "subnormal"),
    (0x3FF0000000000000, "normal"),
    (0x7FF0000000000000, "infinito"),
    (0x7FF0000000000001, "NaN"),
])
def test_clasificar_ieee754(patron, clase):
    assert clasificar_ieee754(patron) == clase


def test_el_texto_de_un_flotante_va_y_vuelve():
    for valor in (0.1, -2.5e-310, 1.7976931348623157e308, -0.0):
        patron = flotante_a_bits(valor)
        assert parsear_ieee754(texto_flotante(patron)) == patron
    assert texto_flotante(0x7FF8000000000000) == "NaN"
    assert texto_flotante(0xFFF0000000000000) == "-inf"
    assert bits_a_flotante(0x4025000000000000) == 10.5


# ---------------------------------------------------------------------------
# Adaptador
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def fpu():
    servicio = AdaptadorFPU()
    if not servicio.disponible:
        pytest.skip(f"enigma64.fpu no esta disponible: {servicio.motivo}")
    return servicio


def _f(valor: float) -> int:
    return flotante_a_bits(valor)


def test_el_adaptador_cumple_el_puerto(fpu):
    assert isinstance(fpu, PuertoFPU)


def test_la_maquina_trae_la_fpu_conectada():
    maquina = construir_maquina()
    assert maquina.fpu.disponible, maquina.fpu.motivo
    assert "fpu" in maquina.servicios


def test_la_fpu_no_toca_la_maquina_compartida():
    """Corre sobre su propia CPU: la RAM y los registros comunes no cambian."""
    maquina = construir_maquina()
    maquina.registros.escribir_nombre("R1", 0x1234)
    antes = maquina.registros.instantanea()
    maquina.fpu.ejecutar("FDIV", _f(1.0), _f(3.0))
    assert maquina.registros.instantanea() == antes
    assert maquina.memoria.estadisticas()["paginas"] == 0


@pytest.mark.parametrize("operacion, a, b, esperado", [
    ("FADD", 10.5, 20.5, 31.0),
    ("FSUB", 20.5, 10.5, 10.0),
    ("FMUL", 10.5, 20.2, 10.5 * 20.2),
    ("FDIV", 10.5, 20.2, 10.5 / 20.2),
    ("FDIV", 1.0, 3.0, 1.0 / 3.0),
])
def test_las_operaciones_aritmeticas(fpu, operacion, a, b, esperado):
    resultado = fpu.ejecutar(operacion, _f(a), _f(b))
    assert resultado["conectada"]
    assert resultado["resultado"] == _f(esperado)
    assert resultado["coincide"] is True
    assert resultado["ciclos"] > 0
    assert resultado["punto_entrada"].startswith("VEC_")   # entra por la tabla


def test_la_division_por_cero_da_infinito_y_cero_entre_cero_da_nan(fpu):
    assert fpu.ejecutar("FDIV", _f(1.0), _f(0.0))["resultado"] == 0x7FF0000000000000
    assert fpu.ejecutar("FDIV", _f(-1.0), _f(0.0))["resultado"] == 0xFFF0000000000000
    nan = fpu.ejecutar("FDIV", _f(0.0), _f(0.0))
    assert clasificar_ieee754(nan["resultado"]) == "NaN"
    assert nan["coincide"] is True          # cualquier NaN vale


@pytest.mark.parametrize("a, b, codigo, texto", [
    (1.0, 2.0, MENOS_UNO, "A < B"),
    (2.0, 1.0, 1, "A > B"),
    (2.0, 2.0, 0, "A = B"),
    (-0.0, 0.0, 0, "A = B"),
    (math.nan, 1.0, 2, "sin orden (NaN)"),
])
def test_la_comparacion(fpu, a, b, codigo, texto):
    resultado = fpu.ejecutar("FCMP", _f(a), _f(b))
    assert resultado["resultado"] == codigo
    assert resultado["texto"] == texto
    assert resultado["coincide"] is True
    assert resultado["tipo_salida"] == "orden"


def test_las_conversiones(fpu):
    a_flotante = fpu.ejecutar("I2F", -7 & MENOS_UNO)
    assert a_flotante["resultado"] == _f(-7.0)
    assert a_flotante["inexacto"] is False

    a_entero = fpu.ejecutar("F2I", _f(-7.9))
    assert a_entero["texto"] == "-7"            # trunca hacia cero
    assert a_entero["coincide"] is True
    assert a_entero["inexacto"] is True

    # Una operacion unaria ignora el segundo operando.
    assert fpu.ejecutar("F2I", _f(2.0), _f(99.0))["b"] == 0


def test_el_redondeo_se_detecta_con_aritmetica_exacta(fpu):
    assert fpu.ejecutar("FADD", _f(0.5), _f(0.25))["inexacto"] is False
    assert fpu.ejecutar("FDIV", _f(1.0), _f(3.0))["inexacto"] is True
    assert fpu.ejecutar("FCMP", _f(1.0), _f(3.0))["inexacto"] is None


def test_el_adaptador_no_oculta_una_diferencia_con_la_norma(fpu):
    """
    El contraste con el anfitrion tiene que avisar cuando la rutina y la norma
    discrepan; aqui se fuerza la discrepancia con un emulador que miente.
    """
    class EmuladorQueMiente:
        class cpu:
            ciclos, detenido = 7, True

        def ejecutar_vector(self, etiqueta, a, b=0):
            return _f(99.0)

    mentiroso = AdaptadorFPU(emulador=EmuladorQueMiente())
    resultado = mentiroso.ejecutar("FADD", _f(1.0), _f(1.0))
    assert resultado["coincide"] is False
    assert resultado["texto_referencia"] == "2.0"


def test_una_rutina_que_no_termina_se_informa():
    class EmuladorColgado:
        class cpu:
            ciclos, detenido = 50000, False

        def ejecutar_vector(self, etiqueta, a, b=0):
            return 0

    with pytest.raises(RuntimeError, match="no termino"):
        AdaptadorFPU(emulador=EmuladorColgado()).ejecutar("FADD", 0, 0)


def test_una_operacion_desconocida_se_rechaza(fpu):
    with pytest.raises(ValueError):
        fpu.descripcion("FTAN")


def test_la_descomposicion_usa_la_rutina_del_equipo(fpu):
    d = fpu.descomponer(_f(10.5))
    assert (d["signo"], d["exponente"], d["exponente_real"]) == (0, 0x402, 3)
    assert d["fraccion"] == 0x5000000000000
    assert d["implicito"] == 1
    assert d["mantisa"] == (1 << 52) | 0x5000000000000
    assert d["clase"] == "normal"
    assert d["ciclos"] > 0

    subnormal = fpu.descomponer(0x0000000000000001)
    assert subnormal["implicito"] == 0
    assert subnormal["exponente_real"] == -1022
    assert fpu.descomponer(0xFFF0000000000000)["clase"] == "infinito"


# -- entregas que aun no llegan ---------------------------------------------


def test_la_hoja_de_ruta_distingue_lo_conectado_de_lo_pendiente(fpu):
    estado = {p["clave"]: p["conectada"] for p in fpu.hoja_de_ruta()}
    for entregada in ("FADD", "FSUB", "FMUL", "FDIV", "FCMP", "I2F", "F2I"):
        assert estado[entregada], f"{entregada} deberia estar conectada"
    assert set(estado) >= {"FSQRT", "oraculo", "brun", "bateria"}


def test_una_rutina_pendiente_solo_ensena_la_referencia(tmp_path):
    """Sin la etiqueta en el ensamblador no se ejecuta nada: no se inventa."""
    class EmuladorIntocable:
        def ejecutar_vector(self, *args):
            raise AssertionError("no debe llamarse a una rutina que no existe")

    servicio = AdaptadorFPU(emulador=EmuladorIntocable(), codigo_asm="FADD:\n  RET\n",
                            raiz=tmp_path)
    assert not servicio.esta_conectada("FSQRT")
    resultado = servicio.ejecutar("FSQRT", _f(2.0))
    assert resultado["conectada"] is False
    assert resultado["resultado"] is None
    assert resultado["texto_referencia"] == repr(math.sqrt(2.0))


def test_la_raiz_cuadrada_se_conecta_sola_cuando_llegue(tmp_path):
    """
    En cuanto el Integrante 6 agregue la etiqueta a la biblioteca, la interfaz
    la llama sin que haya que tocar el panel.
    """
    class EmuladorConRaiz:
        class cpu:
            ciclos, detenido = 321, True

        def __init__(self):
            self.llamadas = []

        def ejecutar_vector(self, etiqueta, a, b=0):
            self.llamadas.append(etiqueta)
            return _f(math.sqrt(bits_a_flotante(a)))

    emulador = EmuladorConRaiz()
    servicio = AdaptadorFPU(emulador=emulador, raiz=tmp_path,
                            codigo_asm="VEC_FSQRT:\n    JMP FSQRT\nFSQRT:\n    RET\n")
    resultado = servicio.ejecutar("FSQRT", _f(9.0))
    assert emulador.llamadas == ["VEC_FSQRT"]      # prefiere la tabla de vectores
    assert resultado["texto"] == "3.0"
    assert resultado["coincide"] is True
    assert resultado["inexacto"] is False


def test_las_entregas_se_detectan_por_sus_archivos(tmp_path):
    servicio = AdaptadorFPU(emulador=object(), codigo_asm="", raiz=tmp_path)
    estado = {p["clave"]: p["conectada"] for p in servicio.hoja_de_ruta()}
    assert not (estado["oraculo"] or estado["brun"] or estado["bateria"])

    (tmp_path / "programas").mkdir()
    (tmp_path / "programas" / "constante_brun.s").write_text("; pendiente\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_oraculo_fpu.py").write_text("")
    estado = {p["clave"]: p["conectada"] for p in servicio.hoja_de_ruta()}
    assert estado["brun"] and estado["oraculo"]
    assert not estado["bateria"]


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------

_VENTANA_TEST: tk.Tk | None = None


def _obtener_raiz() -> tk.Tk | None:
    global _VENTANA_TEST
    if _VENTANA_TEST is None:
        try:
            _VENTANA_TEST = tk.Tk()
            _VENTANA_TEST.withdraw()
            aplicar_tema(_VENTANA_TEST)
        except Exception:
            return None
    return _VENTANA_TEST


necesita_pantalla = pytest.mark.skipif(
    _obtener_raiz() is None,
    reason="se necesita un servidor grafico para crear widgets")


@pytest.fixture
def panel():
    from enigma64.ui.paneles.panel_fpu import PanelFPU
    raiz = _obtener_raiz()
    bus = BusEventos()
    panel = PanelFPU(raiz, servicio=construir_maquina().fpu, bus=bus)
    panel.pack(fill="both", expand=True)
    panel.preparar_demo()
    raiz.update_idletasks()
    yield panel
    assert not bus.errores, bus.errores
    panel.destroy()


def _calcular(panel, operacion, a, b=""):
    panel.cargar_caso(operacion, a, b)
    return panel.resultado


@necesita_pantalla
def test_el_panel_arranca_con_un_calculo_hecho(panel):
    assert panel.salida_valor.cget("text") == "30.7"
    assert "0x403EB33333333333" in panel.salida_hex.cget("text")
    assert "VEC_FADD" in panel.salida_hex.cget("text")


@necesita_pantalla
def test_el_panel_recalcula_al_escribir(panel):
    """Escribir en un operando programa un recalculo sin pulsar ningun boton."""
    panel.operando_a.set("1.5")
    assert panel._pendiente is not None        # quedo programado
    panel.recalcular()
    assert panel._pendiente is None
    assert panel.salida_valor.cget("text") == "21.7"


@necesita_pantalla
def test_el_panel_recalcula_al_cambiar_de_operacion(panel):
    panel.operando_a.set("6")
    panel.operando_b.set("1.5")
    panel.elegir_operacion("FMUL")
    assert panel.salida_valor.cget("text") == "9.0"
    panel.elegir_operacion("FDIV")
    assert panel.salida_valor.cget("text") == "4.0"


@necesita_pantalla
def test_el_panel_acepta_el_patron_en_hexadecimal(panel):
    _calcular(panel, "FADD", "0x4025000000000000", "0.5")
    assert panel.salida_valor.cget("text") == "11.0"


@necesita_pantalla
def test_el_panel_no_se_cae_con_una_entrada_invalida(panel):
    panel.operando_a.set("diez y medio")
    panel.recalcular()
    assert panel.resultado is None
    assert panel.salida_valor.cget("text") == "—"
    assert "Operando A" in panel.salida_hex.cget("text")
    assert panel.winfo_exists()
    panel.operando_a.set("2")                  # y se recupera solo
    panel.recalcular()
    assert panel.salida_valor.cget("text") == "22.2"


@necesita_pantalla
def test_el_panel_enciende_las_condiciones_del_resultado(panel):
    def encendidos():
        return {n for n, led in panel._leds.items()
                if led.etiqueta.cget("fg") == led.color}

    _calcular(panel, "FDIV", "1", "0")
    assert encendidos() == {"INFINITO"}
    _calcular(panel, "FDIV", "0", "0")
    assert encendidos() == {"NaN"}
    _calcular(panel, "FDIV", "-1", "3")
    assert encendidos() == {"NEGATIVO", "INEXACTO"}
    _calcular(panel, "FSUB", "2", "2")
    assert encendidos() == {"CERO"}
    _calcular(panel, "FDIV", "0x0010000000000000", "4")
    assert encendidos() == {"SUBNORMAL"}


@necesita_pantalla
def test_el_panel_deshabilita_b_en_las_conversiones(panel):
    panel.elegir_operacion("F2I")
    assert str(panel.entrada_b.cget("state")) == "disabled"
    panel.elegir_operacion("FADD")
    assert str(panel.entrada_b.cget("state")) == "normal"


@necesita_pantalla
def test_el_panel_convierte_enteros_y_flotantes(panel):
    _calcular(panel, "I2F", "-7")
    assert panel.salida_valor.cget("text") == "-7.0"
    assert panel.vista.get() == "R"            # A es un entero: no se desglosa
    _calcular(panel, "F2I", "-7.9")
    assert panel.salida_valor.cget("text") == "-7"
    assert panel.vista.get() == "A"            # el resultado es un entero


@necesita_pantalla
def test_el_panel_muestra_el_orden_de_una_comparacion(panel):
    _calcular(panel, "FCMP", "nan", "1")
    assert panel.salida_valor.cget("text") == "sin orden (NaN)"
    assert panel.vista.get() in ("A", "B")


@necesita_pantalla
def test_el_visor_desglosa_el_valor_elegido(panel):
    _calcular(panel, "FADD", "-10.5", "0")
    panel.elegir_vista("A")
    assert panel.visor.patron == 0xC025000000000000
    assert panel.visor.implicito == 1
    assert panel._campos["signo"].cget("text").startswith("1")
    assert "1026 - 1023 = 3" in panel._campos["exponente"].cget("text")
    assert "0x5000000000000" in panel._campos["mantisa"].cget("text")
    assert "0x15000000000000" in panel._campos["mantisa"].cget("text")
    assert "-1.3125 x 2^3" in panel._campos["valor"].cget("text")

    panel.elegir_vista("R")
    assert panel.visor.patron == 0xC025000000000000
    assert not panel.visor.editable


@necesita_pantalla
def test_el_visor_muestra_el_bit_implicito_en_cero_para_un_subnormal(panel):
    _calcular(panel, "FADD", "0x0000000000000001", "0")
    panel.elegir_vista("A")
    assert panel.visor.implicito == 0
    assert "-1022" in panel._campos["exponente"].cget("text")


@necesita_pantalla
def test_pulsar_un_bit_del_visor_reescribe_el_operando(panel):
    _calcular(panel, "FADD", "1", "0")
    panel.elegir_vista("A")
    panel.visor.pulsar(63)                     # bit de signo
    assert panel.operando_a.get() == "-1.0"
    assert panel.salida_valor.cget("text") == "-1.0"
    panel.visor.pulsar(52)                     # bit menos significativo del exponente
    assert panel.operando_a.get() == "-0.5"


@necesita_pantalla
def test_el_resultado_no_se_edita_desde_el_visor(panel):
    _calcular(panel, "FADD", "1", "2")
    panel.elegir_vista("R")
    panel.visor.pulsar(63)
    assert (panel.operando_a.get(), panel.operando_b.get()) == ("1", "2")
    assert panel.salida_valor.cget("text") == "3.0"


@necesita_pantalla
def test_el_panel_marca_una_rutina_pendiente_sin_inventar_el_resultado(panel):
    if panel.servicio.esta_conectada("FSQRT"):
        pytest.skip("la raiz cuadrada ya fue entregada")
    _calcular(panel, "FSQRT", "2")
    assert panel.salida_valor.cget("text") == "—"
    assert "1.4142135623730951" in panel.salida_referencia.cget("text")
    assert "Integrante 6" in panel.salida_hex.cget("text")


@necesita_pantalla
def test_el_panel_publica_cada_calculo_una_sola_vez(panel):
    recibidos = []
    panel.bus.suscribir(Evento.FPU_EJECUTADA, recibidos.append)
    _calcular(panel, "FMUL", "3", "4")
    panel.recalcular()                         # misma entrada: no se repite
    assert len(recibidos) == 1
    assert recibidos[0].get("origen") == "fpu"
    assert recibidos[0].get("texto") == "12.0"
    assert "FMUL" in panel.historial.obtener()


@necesita_pantalla
def test_intercambiar_los_operandos(panel):
    _calcular(panel, "FSUB", "5", "2")
    panel.intercambiar()
    assert panel.salida_valor.cget("text") == "-3.0"


@necesita_pantalla
def test_todos_los_casos_de_demostracion_se_ejecutan(panel):
    for _rotulo, operacion, a, b in panel.CASOS:
        panel.cargar_caso(operacion, a, b)
        assert panel.resultado is not None, (operacion, a, b)


@necesita_pantalla
def test_la_ventana_completa_trae_la_pestana_de_la_fpu():
    from enigma64.ui.shell.ventana import VentanaEnigma
    ventana = VentanaEnigma()
    try:
        ventana.withdraw()
        ventana.update_idletasks()
        assert "fpu" in ventana.paneles
        etiquetas = [ventana.cuaderno.tab(i, "text")
                     for i in range(ventana.cuaderno.index("end"))]
        assert "FPU" in etiquetas
        assert not ventana.bus.errores, ventana.bus.errores
    finally:
        ventana.destroy()
