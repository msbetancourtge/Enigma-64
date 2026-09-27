"""
Pruebas de los paneles con widgets reales.

Necesitan un servidor grafico. Donde no lo haya (por ejemplo en integracion
continua) la sesion entera se omite en vez de fallar, y el resto de la bateria
sigue corriendo.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk

import pytest

from enigma64.ui.core.bus import BusEventos, Evento
from enigma64.ui.core.tema import aplicar_tema
from enigma64.ui.paneles import PANELES
from enigma64.ui.servicios import construir_maquina


def _hay_pantalla() -> bool:
    try:
        raiz = tk.Tk()
    except tk.TclError:
        return False
    raiz.destroy()
    return True


pytestmark = pytest.mark.skipif(
    not _hay_pantalla(), reason="se necesita un servidor grafico para crear widgets"
)


@pytest.fixture
def raiz():
    ventana = tk.Tk()
    ventana.withdraw()          # nunca aparece en pantalla durante las pruebas
    aplicar_tema(ventana)
    yield ventana
    ventana.destroy()


@pytest.fixture
def maquina():
    return construir_maquina()


@pytest.fixture
def bus():
    return BusEventos()


def _montar(clase, raiz, maquina, bus):
    servicio = getattr(maquina, clase.CLAVE_SERVICIO) if clase.CLAVE_SERVICIO else None
    panel = clase(raiz, servicio=servicio, bus=bus)
    panel.pack(fill="both", expand=True)
    panel.preparar_demo()
    raiz.update_idletasks()
    return panel


# ---------------------------------------------------------------------------
# Construccion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("clase", PANELES, ids=lambda c: c.NOMBRE)
def test_cada_panel_se_construye_sin_errores(clase, raiz, maquina, bus):
    panel = _montar(clase, raiz, maquina, bus)
    assert panel.winfo_exists()
    assert not bus.errores, bus.errores


@pytest.mark.parametrize("clase", PANELES, ids=lambda c: c.NOMBRE)
def test_cada_panel_cabe_en_su_ventana_suelta(clase, raiz, maquina, bus):
    """El tamano sugerido para el arranque suelto debe bastar para el contenido."""
    panel = _montar(clase, raiz, maquina, bus)
    ancho_max, alto_max = clase.TAMANO_SUELTO
    assert panel.winfo_reqwidth() <= ancho_max, (
        f"{clase.NOMBRE} pide {panel.winfo_reqwidth()}px de ancho")
    assert panel.winfo_reqheight() <= alto_max, (
        f"{clase.NOMBRE} pide {panel.winfo_reqheight()}px de alto")


def test_un_panel_sobrevive_a_que_falte_su_modulo(raiz, bus):
    """Si el modulo del companero no carga, el panel lo informa y sigue en pie."""
    from enigma64.ui.paneles.panel_memoria import PanelMemoria
    from enigma64.ui.servicios.adaptadores import AdaptadorMemoria

    roto = AdaptadorMemoria.__new__(AdaptadorMemoria)
    roto.disponible = False
    roto.motivo = "ModuleNotFoundError: simulado para la prueba"
    roto.ram = None

    panel = PanelMemoria(raiz, servicio=roto, bus=bus)
    panel.pack()
    raiz.update_idletasks()
    assert panel.winfo_exists()
    assert not hasattr(panel, "leds")   # no se construyo la vista normal


# ---------------------------------------------------------------------------
# Panel de memoria
# ---------------------------------------------------------------------------


def test_el_panel_de_memoria_escribe_y_lee(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_memoria import PanelMemoria
    panel = _montar(PanelMemoria, raiz, maquina, bus)

    panel.campo_direccion.texto = "0x00200000"
    panel.tamano.set("8")
    panel.campo_valor.texto = "0x454E494700000001"
    panel.escribir()
    assert "READY" in panel.mensaje.cget("text")

    panel.campo_valor.texto = "0x0"
    panel.leer()
    assert panel.campo_valor.texto == "0x454E494700000001"


@pytest.mark.parametrize("direccion, tamano, esperado", [
    ("0x00200001", "4", "MISALIGNED"),
    ("0xFF001000", "8", "MMIO"),
    ("0x100000000", "8", "ADDR_FAULT"),
])
def test_el_panel_de_memoria_muestra_la_senal_del_bus(direccion, tamano, esperado,
                                                      raiz, maquina, bus):
    from enigma64.ui.paneles.panel_memoria import PanelMemoria
    panel = _montar(PanelMemoria, raiz, maquina, bus)
    panel.campo_direccion.texto = direccion
    panel.tamano.set(tamano)
    panel.leer()
    assert esperado in panel.mensaje.cget("text")


def test_el_panel_de_memoria_avisa_de_una_direccion_invalida(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_memoria import PanelMemoria
    panel = _montar(PanelMemoria, raiz, maquina, bus)
    panel.campo_direccion.texto = "no es un numero"
    panel.leer()
    assert "no es un numero" in panel.mensaje.cget("text").lower()


def test_el_panel_de_memoria_obedece_al_evento_de_navegacion(raiz, maquina, bus):
    """Otro panel pide ver una direccion publicando en el bus, no llamando."""
    from enigma64.ui.paneles.panel_memoria import PanelMemoria
    panel = _montar(PanelMemoria, raiz, maquina, bus)
    bus.publicar(Evento.IR_A_DIRECCION, direccion=0x00201230)
    assert panel.base_volcado == 0x00201230
    assert panel.campo_direccion.texto == "0x00201230"


# ---------------------------------------------------------------------------
# Panel de registros
# ---------------------------------------------------------------------------


def test_el_panel_de_registros_escribe_un_registro(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_registros import PanelRegistros
    panel = _montar(PanelRegistros, raiz, maquina, bus)
    panel.registro.set("R3")
    panel.valor.set("0xABC")
    panel.escribir()
    assert maquina.registros.leer_nombre("R3") == 0xABC


def test_el_panel_de_registros_explica_que_r0_esta_cableado(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_registros import PanelRegistros
    panel = _montar(PanelRegistros, raiz, maquina, bus)
    panel.registro.set("R0")
    panel.valor.set("0xFFFF")
    panel.escribir()
    assert "cableado a cero" in panel.mensaje.cget("text")
    assert maquina.registros.leer_nombre("R0") == 0


def test_el_panel_de_registros_conmuta_una_bandera(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_registros import PanelRegistros
    panel = _montar(PanelRegistros, raiz, maquina, bus)
    antes = maquina.registros.banco.leer_bandera("C")
    panel.conmutar_bandera("C")
    assert maquina.registros.banco.leer_bandera("C") != antes


def test_el_panel_de_registros_se_refresca_solo(raiz, maquina, bus):
    """Se suscribe al banco: si la ALU cambia el SR, la tabla se entera sola."""
    from enigma64.ui.paneles.panel_registros import PanelRegistros
    panel = _montar(PanelRegistros, raiz, maquina, bus)
    maquina.registros.escribir_nombre("R2", 0x1234)
    raiz.update_idletasks()
    _, _, celda_hex, _ = panel._filas["R2"]
    assert celda_hex.cget("text") == "0x0000000000001234"


# ---------------------------------------------------------------------------
# Panel de la ALU
# ---------------------------------------------------------------------------


def test_el_panel_de_alu_ejecuta_una_suma(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_alu import PanelALU
    panel = _montar(PanelALU, raiz, maquina, bus)
    panel.elegir_operacion("ADD")
    panel.latch_a.set("120")
    panel.latch_b.set("5")
    panel.ejecutar()
    assert panel.salida_hex.cget("text") == "0x000000000000007D"


def test_el_panel_de_alu_deshabilita_el_latch_b_en_operaciones_unarias(
        raiz, maquina, bus):
    from enigma64.ui.paneles.panel_alu import PanelALU
    panel = _montar(PanelALU, raiz, maquina, bus)
    panel.elegir_operacion("NOT")
    assert str(panel.entrada_b.cget("state")) == "disabled"
    panel.elegir_operacion("ADD")
    assert str(panel.entrada_b.cget("state")) == "normal"


def test_el_panel_de_alu_no_se_cae_al_dividir_por_cero(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_alu import PanelALU
    panel = _montar(PanelALU, raiz, maquina, bus)
    panel.elegir_operacion("DIV")
    panel.latch_a.set("8")
    panel.latch_b.set("0")
    panel.ejecutar()
    assert "DivisionPorCero" in panel.historial.obtener()
    assert panel.winfo_exists()


def test_el_panel_de_alu_vuelca_las_banderas_al_sr(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_alu import PanelALU
    panel = _montar(PanelALU, raiz, maquina, bus)
    panel.elegir_operacion("SUB")
    panel.latch_a.set("5")
    panel.latch_b.set("5")
    panel.volcar_sr.set(True)
    panel.ejecutar()
    assert maquina.registros.banco.leer_bandera("Z") == 1


# ---------------------------------------------------------------------------
# Panel del cargador
# ---------------------------------------------------------------------------


def test_el_panel_del_cargador_carga_un_volcado(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_cargador import PanelCargador
    panel = _montar(PanelCargador, raiz, maquina, bus)
    panel.volcado.fijar("10 12 30 00")
    panel.destino.set("0x00200000")
    panel.cargar_texto()
    assert panel.titulo_resultado.cget("text") == "CARGA ACEPTADA"
    assert maquina.memoria.leer_byte(0x00200000) == 0x10


def test_el_panel_del_cargador_explica_una_carga_rechazada(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_cargador import PanelCargador
    panel = _montar(PanelCargador, raiz, maquina, bus)
    panel.volcado.fijar("10 12 30 00")
    panel.destino.set("0x00000100")       # invade los vectores
    panel.cargar_texto()
    assert "RECHAZADA" in panel.titulo_resultado.cget("text")
    assert "protegida" in panel.detalle_resultado.cget("text")


def test_el_panel_del_cargador_pide_navegar_por_el_bus(raiz, maquina, bus):
    """Tras cargar publica IR_A_DIRECCION; no llama al panel de memoria."""
    from enigma64.ui.paneles.panel_cargador import PanelCargador
    panel = _montar(PanelCargador, raiz, maquina, bus)
    destinos = []
    bus.suscribir(Evento.IR_A_DIRECCION, lambda m: destinos.append(m.get("direccion")))
    panel.volcado.fijar("10 12 30 00")
    panel.destino.set("0x00200000")
    panel.cargar_texto()
    assert destinos == [0x00200000]


def test_el_panel_del_cargador_conmuta_un_bit(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_cargador import PanelCargador
    panel = _montar(PanelCargador, raiz, maquina, bus)
    maquina.memoria.escribir(0x00200000, 0x10, 1)
    panel.direccion_bit.set("0x00200000")
    panel.refrescar_bits()
    panel.conmutar_bit(0)
    assert maquina.memoria.leer_byte(0x00200000) == 0x11


# ---------------------------------------------------------------------------
# Panel del mapa y traza
# ---------------------------------------------------------------------------


def test_el_panel_del_mapa_resalta_la_region_del_acceso(raiz, bus):
    from enigma64.ui.paneles.panel_mapa import PanelMapa
    panel = PanelMapa(raiz, servicio=None, bus=bus)
    panel.pack()
    bus.publicar(Evento.BUS_SENAL, direccion=0xFF001000, estado="MMIO")
    assert panel.detalle_direccion.cget("text") == "0xFF001000"
    assert "I/O mapeada" in panel.detalle_region.cget("text")


def test_el_panel_del_mapa_avisa_de_una_direccion_no_mapeada(raiz, bus):
    from enigma64.ui.paneles.panel_mapa import PanelMapa
    panel = PanelMapa(raiz, servicio=None, bus=bus)
    panel.pack()
    panel.resaltar(0x1_0000_0000)
    assert "FALLO_DIR" in panel.detalle_region.cget("text")


def test_la_traza_registra_lo_que_pasa_por_el_bus(raiz, bus):
    from enigma64.ui.paneles.panel_consola import PanelConsola
    panel = PanelConsola(raiz, servicio=None, bus=bus)
    panel.pack()
    antes = panel._lineas
    bus.traza("mensaje de prueba", "exito", "pruebas")
    assert panel._lineas == antes + 1
    assert "mensaje de prueba" in panel.registro.obtener()


def test_la_traza_no_crece_sin_limite(raiz, bus):
    from enigma64.ui.paneles.panel_consola import PanelConsola
    panel = PanelConsola(raiz, servicio=None, bus=bus)
    panel.pack()
    for i in range(500):
        bus.traza(f"linea {i}")
    assert panel._lineas <= 400


# ---------------------------------------------------------------------------
# Ventana completa
# ---------------------------------------------------------------------------


def test_la_ventana_completa_monta_los_seis_paneles():
    from enigma64.ui.shell.ventana import VentanaEnigma
    ventana = VentanaEnigma()
    try:
        ventana.withdraw()
        ventana.update_idletasks()
        assert set(ventana.paneles) == {c.NOMBRE for c in PANELES}
        assert not ventana.bus.errores, ventana.bus.errores
    finally:
        ventana.destroy()


def test_la_ventana_no_nace_mas_grande_que_la_pantalla():
    from enigma64.ui.shell.ventana import VentanaEnigma
    ventana = VentanaEnigma()
    try:
        ventana.update_idletasks()
        geometria = ventana.geometry()
        ancho = int(geometria.split("x")[0])
        alto = int(geometria.split("x")[1].split("+")[0])
        assert ancho <= ventana.winfo_screenwidth()
        assert alto <= ventana.winfo_screenheight()
    finally:
        ventana.destroy()


def test_el_reset_de_la_ventana_limpia_memoria_y_registros():
    from enigma64.ui.shell.ventana import VentanaEnigma
    ventana = VentanaEnigma()
    try:
        ventana.withdraw()
        ventana.maquina.memoria.escribir(0x00200000, 0xFF, 1)
        ventana.maquina.registros.escribir_nombre("R1", 0x99)
        ventana.reiniciar_maquina()
        assert ventana.maquina.memoria.estadisticas()["paginas"] == 0
        assert ventana.maquina.registros.leer_nombre("R1") == 0
    finally:
        ventana.destroy()
