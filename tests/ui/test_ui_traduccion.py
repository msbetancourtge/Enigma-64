"""
Pruebas de la pestana de traduccion CacaoCore-64 -> Enigma-64 (Tarea 27).

La primera mitad prueba el servicio sin pantalla: traducir, enviar al
Cargador/RAM de la maquina compartida, ejecutar y contrastar los tres
algoritmos clasicos con los resultados oficiales de la Tarea 10. La segunda
mitad monta el panel con widgets reales y se omite si no hay servidor X.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk

import pytest

from enigma64.ui.core.bus import BusEventos, Evento
from enigma64.ui.core.tema import aplicar_tema
from enigma64.ui.servicios import AdaptadorTraduccion, construir_maquina
from enigma64.ui.servicios.puertos import ServicioNoDisponible
from enigma64.ui.servicios.traduccion import ESPERADOS

CLASICOS = tuple(ESPERADOS)


@pytest.fixture
def maquina():
    return construir_maquina()


@pytest.fixture
def servicio(maquina):
    assert maquina.traduccion.disponible, maquina.traduccion.motivo
    return maquina.traduccion


def _fuente(servicio, clave):
    ejemplo = next(e for e in servicio.ejemplos() if e["clave"] == clave)
    return servicio.leer_archivo(ejemplo["ruta"])


# ===========================================================================
# Servicio
# ===========================================================================


def test_la_fabrica_entrega_el_servicio_de_traduccion(maquina):
    assert isinstance(maquina.traduccion, AdaptadorTraduccion)
    # Compone la misma RAM y el mismo cargador que el resto de pestanas.
    assert maquina.traduccion.memoria is maquina.memoria
    assert maquina.traduccion.cargador is maquina.cargador


def test_los_ejemplos_listan_primero_los_tres_algoritmos_clasicos(servicio):
    claves = [e["clave"] for e in servicio.ejemplos()]
    assert tuple(claves[:3]) == tuple(sorted(CLASICOS))
    assert not any(clave.endswith("_enigma") for clave in claves)


@pytest.mark.parametrize("clave", CLASICOS)
def test_traduce_y_ensambla_los_algoritmos_clasicos(servicio, clave):
    t = servicio.traducir(_fuente(servicio, clave))
    assert t["ok"], t["errores"] or t["error_ensamblado"]
    assert t["binario"] and t["base_codigo"] + len(t["binario"]) <= t["base_datos"]
    assert set(ESPERADOS[clave][1]) <= set(t["variables"])


def test_la_correspondencia_apunta_a_lineas_reales_de_cacaocore(servicio):
    fuente = _fuente(servicio, "cacao_euclides")
    t = servicio.traducir(fuente)
    cacao = fuente.splitlines()
    enigma = t["codigo"].splitlines()
    assert t["correspondencia"]
    for linea_enigma, linea_cacao in t["correspondencia"].items():
        original = cacao[linea_cacao - 1].strip()
        assert original and original in enigma[linea_enigma - 1]


def test_un_programa_invalido_devuelve_errores_sin_lanzar(servicio):
    t = servicio.traducir(".text\nFOO R1, R2\nHLT\n")
    assert not t["ok"]
    assert t["errores"] and t["errores"][0][0] == 2
    assert t["binario"] is None


def test_no_se_envia_una_traduccion_con_errores(servicio):
    with pytest.raises(ValueError):
        servicio.enviar_a_ram(servicio.traducir(".text\nFOO R1\nHLT\n"))


def test_enviar_deja_codigo_y_datos_en_la_ram_compartida(maquina, servicio):
    t = servicio.traducir(_fuente(servicio, "cacao_euclides"))
    informe = servicio.enviar_a_ram(t)

    assert informe["direccion_base"] == 0x00200000
    assert informe["bytes_datos"] > 0
    assert maquina.registros.banco.pc == 0x00200000
    primeros = bytes(maquina.memoria.leer_byte(0x00200000 + i) for i in range(4))
    assert primeros == t["binario"][:4]
    # Los valores iniciales de .data ya estan en RAM antes de ejecutar.
    valores = {nombre: valor for nombre, _d, valor in servicio.leer_variables(t)}
    assert valores == {"a": 48, "b": 18}


@pytest.mark.parametrize("clave", CLASICOS)
def test_el_programa_traducido_corre_y_da_el_resultado_de_la_tarea_10(servicio, clave):
    if not servicio.puede_ejecutar:
        pytest.skip("falta la Unidad de Control")
    t = servicio.traducir(_fuente(servicio, clave))
    servicio.enviar_a_ram(t)
    estado = servicio.ejecutar()
    assert estado["detenido"]
    veredicto = servicio.verificar(clave, t)
    assert veredicto["ok"], veredicto


def test_se_puede_cargar_y_ejecutar_dos_programas_seguidos(servicio):
    if not servicio.puede_ejecutar:
        pytest.skip("falta la Unidad de Control")
    for clave in ("cacao_factorial", "cacao_euclides"):
        t = servicio.traducir(_fuente(servicio, clave))
        servicio.enviar_a_ram(t)
        servicio.ejecutar()
        assert servicio.verificar(clave, t)["ok"]


def test_verificar_un_programa_sin_resultado_oficial_devuelve_none(servicio):
    t = servicio.traducir(_fuente(servicio, "maximo"))
    assert servicio.verificar("maximo", t) is None


def test_sin_cargador_el_servicio_queda_no_disponible():
    servicio = AdaptadorTraduccion(memoria=None, cargador=None)
    assert not servicio.disponible
    assert "cargador" in servicio.motivo
    with pytest.raises(ServicioNoDisponible):
        servicio.traducir("HLT\n")


# ===========================================================================
# Panel (necesita servidor grafico)
# ===========================================================================


def _raiz():
    try:
        ventana = tk.Tk()
    except Exception:
        return None
    ventana.withdraw()
    aplicar_tema(ventana)
    return ventana


@pytest.fixture(scope="module")
def raiz():
    ventana = _raiz()
    if ventana is None:
        pytest.skip("se necesita un servidor grafico para crear widgets")
    yield ventana
    ventana.destroy()


@pytest.fixture
def panel(raiz, maquina):
    from enigma64.ui.paneles.panel_traduccion import PanelTraduccion

    bus = BusEventos()
    panel = PanelTraduccion(raiz, servicio=maquina.traduccion, bus=bus)
    panel.pack(fill="both", expand=True)
    panel.preparar_demo()
    raiz.update_idletasks()
    yield panel
    panel.destroy()


def _ejemplo(panel, clave):
    return next(n for n, e in panel._ejemplos.items() if e["clave"] == clave)


def test_el_panel_arranca_con_un_algoritmo_ya_traducido(panel):
    assert panel.cacao.obtener().strip()
    assert "Traduccion automatica CacaoCore-64 -> Enigma-64" in panel.enigma.obtener()
    assert panel.traduccion["ok"]
    assert "disabled" not in panel.boton_enviar.state()
    assert not panel.bus.errores, panel.bus.errores


def test_el_panel_resalta_las_lineas_correspondientes(panel):
    panel.abrir_ejemplo(_ejemplo(panel, "cacao_euclides"))
    linea_cacao = next(iter(panel.traduccion["correspondencia"].values()))
    destino = panel.resaltar_desde_cacao(linea_cacao)
    assert destino
    resaltadas = panel.enigma.texto.tag_ranges("foco")
    assert resaltadas and int(str(resaltadas[0]).split(".")[0]) == destino[0]


def test_el_panel_envia_al_cargador_y_publica_en_el_bus(panel, maquina):
    recibidos = []
    panel.bus.suscribir(Evento.PROGRAMA_CARGADO, recibidos.append)
    panel.abrir_ejemplo(_ejemplo(panel, "cacao_factorial"))
    panel.enviar()
    assert recibidos and recibidos[0].get("direccion_base") == 0x00200000
    assert panel.titulo_resultado.cget("text") == "PROGRAMA TRADUCIDO EN RAM"
    assert maquina.registros.banco.pc == 0x00200000


@pytest.mark.parametrize("clave", CLASICOS)
def test_el_panel_ejecuta_y_verifica_contra_la_tarea_10(panel, clave):
    if not panel.servicio.puede_ejecutar:
        pytest.skip("falta la Unidad de Control")
    verificados = []
    panel.bus.suscribir(Evento.TRADUCCION_VERIFICADA, verificados.append)
    panel.abrir_ejemplo(_ejemplo(panel, clave))
    panel.enviar()
    panel.ejecutar()
    assert panel.titulo_resultado.cget("text").startswith("VERIFICADO")
    assert verificados and verificados[0].get("ok")


def test_el_panel_marca_los_errores_y_bloquea_el_envio(panel):
    panel.cacao.fijar(".text\nFOO R1, R2\nHLT\n")
    panel.traducir()
    assert not panel.traduccion["ok"]
    assert "disabled" in panel.boton_enviar.state()
    assert panel.cacao.texto.tag_ranges("error")
    assert panel.titulo_resultado.cget("text") == "LA TRADUCCION TIENE ERRORES"
