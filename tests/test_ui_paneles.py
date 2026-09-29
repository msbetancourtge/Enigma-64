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


_VENTANA_TEST: tk.Tk | None = None


def _obtener_raiz() -> tk.Tk | None:
    global _VENTANA_TEST
    if _VENTANA_TEST is not None:
        try:
            if _VENTANA_TEST.winfo_exists():
                return _VENTANA_TEST
        except Exception:
            pass
    try:
        _VENTANA_TEST = tk.Tk()
        _VENTANA_TEST.withdraw()
        aplicar_tema(_VENTANA_TEST)
        return _VENTANA_TEST
    except Exception:
        return None


def _hay_pantalla() -> bool:
    return _obtener_raiz() is not None


pytestmark = pytest.mark.skipif(
    not _hay_pantalla(), reason="se necesita un servidor grafico para crear widgets"
)


@pytest.fixture(scope="session")
def raiz():
    ventana = _obtener_raiz()
    if ventana is None:
        pytest.skip("se necesita un servidor grafico para crear widgets")
    yield ventana


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


# ---------------------------------------------------------------------------
# Panel de la Unidad de Control (modulo pendiente)
# ---------------------------------------------------------------------------


def test_el_panel_de_cpu_muestra_el_contrato_mientras_falte_el_modulo(raiz, bus):
    """No basta con no caerse: tiene que decir que debe escribir el Integrante 3."""
    from enigma64.ui.paneles.panel_cpu import PanelCPU
    maquina_sin_cpu = construir_maquina()
    maquina_sin_cpu.cpu.disponible = False
    maquina_sin_cpu.cpu.motivo = "Unidad de Control: modulo pendiente del Integrante 3"
    panel = _montar(PanelCPU, raiz, maquina_sin_cpu, bus)
    assert panel.winfo_exists()
    assert not hasattr(panel, "_cajas_fase")       # no se construyo la vista normal

    textos = []
    def recoger(widget):
        try:
            textos.append(str(widget.cget("text")))
        except tk.TclError:
            pass
        for hijo in widget.winfo_children():
            recoger(hijo)
    recoger(panel)
    unido = " ".join(textos)
    assert "MODULO PENDIENTE" in unido
    assert "Integrante 3" in unido


def test_el_panel_de_cpu_se_enciende_cuando_llega_el_modulo(raiz, bus):
    from enigma64.ui.paneles.panel_cpu import PanelCPU
    from enigma64.ui.servicios.adaptadores import AdaptadorCPU

    class CPUDelIntegrante3:
        def __init__(self): self.ciclos = 0
        def paso(self): self.ciclos += 1
        def paso_instruccion(self): self.ciclos += 5
        def ejecutar(self, max_ciclos=100000): self.ciclos = 40
        def reiniciar(self): self.ciclos = 0
        def estado(self):
            return {"fase": "EXECUTE", "ciclos": self.ciclos,
                    "instrucciones": self.ciclos // 5,
                    "detenido": self.ciclos >= 40,
                    "micro": {"MAR": 0x200000, "IR": 0x14100020},
                    "mnemonico": "ADDI", "prefetch": b"\x14\x10\x00\x20"}

    panel = PanelCPU(raiz, servicio=AdaptadorCPU(cpu=CPUDelIntegrante3()), bus=bus)
    panel.pack()
    raiz.update_idletasks()

    assert hasattr(panel, "_cajas_fase")
    assert set(panel._cajas_fase) == {"FETCH", "DECODE", "EXECUTE", "MEMORY", "WRITE-BACK"}

    panel._avanzar("paso")
    assert panel._contadores["ciclos"].cget("text") == "1"
    assert panel._celdas_micro["MAR"].cget("text") == "0x0000000000200000"

    panel._avanzar("ejecutar")
    assert panel.insignia.itemcget(panel.insignia._texto, "text") == "HLT"


def test_el_panel_de_cpu_publica_su_avance_en_el_bus(raiz, bus):
    from enigma64.ui.paneles.panel_cpu import PanelCPU
    from enigma64.ui.servicios.adaptadores import AdaptadorCPU

    class CPUMinima:
        def paso(self): pass
        def estado(self): return {"fase": "DECODE", "ciclos": 3}

    avances = []
    bus.suscribir(Evento.CPU_AVANZO, lambda m: avances.append(m.get("fase")))
    panel = PanelCPU(raiz, servicio=AdaptadorCPU(cpu=CPUMinima()), bus=bus)
    panel.pack()
    panel._avanzar("paso")
    assert avances == ["DECODE"]


# ---------------------------------------------------------------------------
# Panel de I/O mapeada
# ---------------------------------------------------------------------------


def test_el_panel_mmio_escribe_un_registro(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_mmio import PanelMMIO
    panel = _montar(PanelMMIO, raiz, maquina, bus)
    panel.seleccionar("disco")
    panel._campos[0x18].set("0x2A")        # LBA en DSK_ADDR
    panel.escribir()
    assert maquina.mmio.leer(0xFF002000, 0x18) == 0x2A
    assert "escrito" in panel.mensaje.cget("text")


def test_el_panel_mmio_renombra_los_registros_de_la_red(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_mmio import PanelMMIO
    panel = _montar(PanelMMIO, raiz, maquina, bus)
    panel.seleccionar("red")
    assert "INTERFAZ DE RED" in panel.titulo_registros.cget("text")
    etiquetas = [w.cget("text") for w in panel.rejilla.winfo_children()
                 if isinstance(w, tk.Label)]
    assert "NET_MAC" in etiquetas


def test_el_panel_mmio_rechaza_un_valor_invalido(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_mmio import PanelMMIO
    panel = _montar(PanelMMIO, raiz, maquina, bus)
    panel._campos[0x00].set("no es un numero")
    panel.escribir()
    assert "no es un numero" in panel.mensaje.cget("text").lower()


def test_el_panel_mmio_avisa_de_que_el_banco_es_provisional(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_mmio import PanelMMIO
    from enigma64.ui.servicios import mmio
    from enigma64.ui.servicios.adaptadores import AdaptadorMMIO
    maquina.mmio = AdaptadorMMIO(banco=mmio.BancoMMIOProvisional(), memoria=maquina.memoria)
    panel = _montar(PanelMMIO, raiz, maquina, bus)
    assert maquina.mmio.es_provisional
    textos = []
    def recoger(widget):
        try:
            textos.append(str(widget.cget("text")))
        except tk.TclError:
            pass
        for hijo in widget.winfo_children():
            recoger(hijo)
    recoger(panel)
    assert "BANCO PROVISIONAL" in " ".join(textos)


# ---------------------------------------------------------------------------
# Panel de algoritmos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("clave", ["factorial", "euclides", "fibonacci"])
def test_el_panel_de_algoritmos_carga_cada_programa(clave, raiz, maquina, bus):
    from enigma64.ui.paneles.panel_algoritmos import PanelAlgoritmos
    panel = _montar(PanelAlgoritmos, raiz, maquina, bus)
    panel.elegir(clave)
    panel.cargar()
    assert panel.titulo_resultado.cget("text") == "PROGRAMA CARGADO"

    algoritmo = maquina.algoritmos.obtener(clave)
    esperado = maquina.algoritmos.codigo_maquina(algoritmo)
    real = bytes(maquina.memoria.leer_byte(algoritmo["base"] + i)
                 for i in range(len(esperado)))
    assert real == esperado


def test_el_panel_de_algoritmos_muestra_el_codigo_maquina_del_documento(
        raiz, maquina, bus):
    from enigma64.ui.paneles.panel_algoritmos import PanelAlgoritmos
    panel = _montar(PanelAlgoritmos, raiz, maquina, bus)
    panel.elegir("factorial")
    listado = panel.listado.obtener()
    assert "0x00200000" in listado
    assert "14 10 00 20" in listado          # ADDI R1, R0, 0x0020
    assert "ADDI  R1, R0, 0x0020" in listado


def test_el_panel_de_algoritmos_no_da_por_bueno_un_resultado_inexistente(
        raiz, maquina, bus):
    from enigma64.ui.paneles.panel_algoritmos import PanelAlgoritmos
    panel = _montar(PanelAlgoritmos, raiz, maquina, bus)
    panel.elegir("factorial")
    panel.cargar()
    panel.verificar()
    assert panel.titulo_resultado.cget("text") == "RESULTADO AUN NO ESCRITO"
    if not maquina.algoritmos.puede_ejecutar:
        assert "Integrante 3" in panel.detalle_resultado.cget("text")
    else:
        assert "esperado" in panel.detalle_resultado.cget("text")


def test_el_panel_de_algoritmos_reconoce_el_resultado_correcto(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_algoritmos import PanelAlgoritmos
    panel = _montar(PanelAlgoritmos, raiz, maquina, bus)
    panel.elegir("factorial")
    panel.cargar()
    maquina.memoria.escribir(0x00201008, 120, 8)   # lo que escribiria la CPU
    panel.verificar()
    assert "VERIFICADO" in panel.titulo_resultado.cget("text")


def test_el_boton_ejecutar_esta_deshabilitado_sin_cpu(raiz, bus):
    from enigma64.ui.paneles.panel_algoritmos import PanelAlgoritmos
    maquina_sin_cpu = construir_maquina()
    maquina_sin_cpu.cpu.disponible = False
    panel = _montar(PanelAlgoritmos, raiz, maquina_sin_cpu, bus)
    assert not maquina_sin_cpu.algoritmos.puede_ejecutar
    assert "disabled" in panel.boton_ejecutar.state()


def test_el_panel_de_algoritmos_pide_navegar_tras_cargar(raiz, maquina, bus):
    from enigma64.ui.paneles.panel_algoritmos import PanelAlgoritmos
    destinos = []
    bus.suscribir(Evento.IR_A_DIRECCION, lambda m: destinos.append(m.get("direccion")))
    panel = _montar(PanelAlgoritmos, raiz, maquina, bus)
    panel.elegir("euclides")
    panel.cargar()
    assert destinos == [0x00200100]
