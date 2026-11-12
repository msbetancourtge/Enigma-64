"""
Pruebas del panel visual de Estructuras de Datos (Tarea 29).

La primera parte prueba el servicio sin pantalla: parseo de lo que escribe el
usuario, escritura en RAM con la libreria del Integrante 4, observacion en
vivo, deteccion por descriptores y ejecucion del merge sort del Integrante 6
sobre la maquina compartida. La segunda monta el panel con widgets reales y
se omite si no hay servidor X.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import tkinter as tk

import pytest

from enigma64.ui.core.bus import BusEventos, Evento
from enigma64.ui.core.tema import aplicar_tema
from enigma64.ui.servicios import AdaptadorEstructuras, construir_maquina
from enigma64.ui.servicios.estructuras import (
    BASE_BUFFERS, BASE_CABECERAS, BASE_MATRICES, BASE_VECTORES,
    formatear_palabra, parsear_matriz, parsear_vector, zona_de,
)

MASCARA = (1 << 64) - 1


def _con_signo(palabra: int) -> int:
    return palabra - (1 << 64) if palabra >> 63 else palabra


@pytest.fixture
def maquina():
    return construir_maquina()


@pytest.fixture
def servicio(maquina):
    assert maquina.estructuras.disponible, maquina.estructuras.motivo
    return maquina.estructuras


def _programa(servicio, clave):
    return next(p for p in servicio.programas() if p["clave"] == clave)


def _cargar(servicio, clave):
    programa = _programa(servicio, clave)
    servicio.observar_programa(programa)
    resultado = servicio.compilar(servicio.leer_archivo(programa["ruta"]), programa["ruta"])
    assert resultado["ok"], resultado["error"]
    return servicio.cargar()


# ===========================================================================
# Utilidades puras
# ===========================================================================


@pytest.mark.parametrize("texto, esperado", [
    ("45, -12, 89", [45, -12, 89]),
    ("[1 2 3]", [1, 2, 3]),
    ("0x10; 0b11\n7", [16, 3, 7]),
    ("1.5, -2", [1.5, -2]),
])
def test_parsear_vector_acepta_formatos_comunes(texto, esperado):
    assert parsear_vector(texto) == esperado


@pytest.mark.parametrize("texto", ["", "   ", "1, dos, 3"])
def test_parsear_vector_rechaza_entradas_invalidas(texto):
    with pytest.raises(ValueError):
        parsear_vector(texto)


@pytest.mark.parametrize("texto", ["1 2 3; 4 5 6", "1,2,3\n4,5,6", "[[1, 2, 3], [4, 5, 6]]"])
def test_parsear_matriz_acepta_filas_por_linea_o_punto_y_coma(texto):
    assert parsear_matriz(texto) == [[1, 2, 3], [4, 5, 6]]


def test_parsear_matriz_rechaza_filas_irregulares():
    with pytest.raises(ValueError, match="columnas"):
        parsear_matriz("1 2 3; 4 5")


def test_formatear_palabra_en_los_tres_formatos():
    menos_cuatro = (-4) & MASCARA
    assert formatear_palabra(menos_cuatro, "decimal") == "-4"
    assert formatear_palabra(menos_cuatro, "hex") == "0xFFFFFFFFFFFFFFFC"
    assert formatear_palabra(0x3FF8000000000000, "float") == "1.5"


def test_zonas_del_mapa_de_la_libreria():
    assert zona_de(BASE_CABECERAS) == "cabeceras"
    assert zona_de(BASE_VECTORES + 8) == "vectores"
    assert zona_de(BASE_MATRICES) == "matrices"
    assert zona_de(BASE_BUFFERS) == "buffers"
    assert zona_de(0x00200000) is None


# ===========================================================================
# Servicio sobre la maquina compartida
# ===========================================================================


def test_la_fabrica_entrega_el_servicio_compartiendo_el_hardware(maquina):
    servicio = maquina.estructuras
    assert isinstance(servicio, AdaptadorEstructuras)
    assert servicio.memoria is maquina.memoria
    assert servicio.cargador is maquina.cargador
    assert servicio.cpu is maquina.cpu


def test_el_catalogo_encuentra_los_programas_que_incluyen_la_libreria(servicio):
    claves = [p["clave"] for p in servicio.programas()]
    assert "merge_sort" in claves
    assert "prueba_cabeceras_cargador" in claves
    # Los que no incluyen estructuras.inc no aparecen.
    assert "esqueleto_merge_sort" not in claves or all(
        "estructuras.inc" in servicio.leer_archivo(p["ruta"]) for p in servicio.programas())


def test_definir_vector_lo_escribe_en_ram_con_descriptor_y_cabecera(servicio, maquina):
    entrada = servicio.definir_vector("V", [5, -3, 8])
    base = entrada["base"]
    assert base == BASE_VECTORES and entrada["ranura"] == 0

    leer = lambda d: maquina.memoria.leer(d, 8)[0]
    assert [_con_signo(leer(base + 8 * i)) for i in range(3)] == [5, -3, 8]
    assert leer(base - 8) == 3                      # cabecera inline N
    assert leer(BASE_CABECERAS) == 1                # descriptor: tipo vector
    assert leer(BASE_CABECERAS + 8) == base         # descriptor: base

    foto = servicio.instantanea("V")
    assert foto["filas"] == 1 and foto["columnas"] == 3
    assert [_con_signo(p) for p in foto["palabras"][0]] == [5, -3, 8]
    assert foto["zona"] == "vectores" and foto["origen"] == "usuario"


def test_definir_matriz_en_cuadricula_row_major(servicio):
    entrada = servicio.definir_matriz("A", [[1, 2, 3], [4, 5, 6]])
    assert entrada["base"] == BASE_MATRICES
    foto = servicio.instantanea("A")
    assert (foto["filas"], foto["columnas"]) == (2, 3)
    assert foto["palabras"] == [[1, 2, 3], [4, 5, 6]]
    assert servicio.direccion_de("A", 1, 2) == BASE_MATRICES + ((1 * 3 + 2) << 3)


def test_dos_vectores_reciben_bases_y_ranuras_distintas_sin_solaparse(servicio):
    a = servicio.definir_vector("A", [1, 2, 3])
    b = servicio.definir_vector("B", [9, 9])
    assert b["base"] >= a["base"] + 3 * 8 + 16
    assert b["base"] % 8 == 0
    assert a["ranura"] != b["ranura"]


def test_una_base_que_se_solapa_se_rechaza_y_conserva_lo_anterior(servicio):
    servicio.definir_vector("A", [1, 2, 3, 4])
    with pytest.raises(ValueError, match="solapa"):
        servicio.definir_vector("B", [7], base=BASE_VECTORES + 8)
    assert "B" not in servicio.entradas and "A" in servicio.entradas


@pytest.mark.parametrize("nombre", ["", "1V", "con espacio"])
def test_nombres_invalidos_se_rechazan(servicio, nombre):
    with pytest.raises(ValueError):
        servicio.definir_vector(nombre, [1])


def test_detectar_encuentra_las_estructuras_por_su_descriptor(servicio):
    servicio.definir_vector("V", [1, 2])
    servicio.definir_matriz("M", [[1, 2], [3, 4]])
    servicio.observadas.clear()
    encontradas = servicio.detectar()
    tipos = sorted((e["tipo"], e["base"]) for e in encontradas)
    assert tipos == [("matriz", BASE_MATRICES), ("vector", BASE_VECTORES)]
    assert len(servicio.instantaneas()) == 2


def test_merge_sort_ordena_la_entrada_del_usuario_y_la_emite_por_mmio(servicio):
    servicio.definir_vector("V", [38, 27, 43, 3, 9, 82, 10, -4])
    informe = _cargar(servicio, "merge_sort")
    assert informe["estructuras_escritas"] == 1

    estado = servicio.ejecutar_hasta_fin()
    assert estado["detenido"] and not estado["agotado"]

    foto = next(f for f in servicio.instantaneas() if f["nombre"] == "V")
    assert [_con_signo(p) for p in foto["palabras"][0]] == [-4, 3, 9, 10, 27, 38, 43, 82]
    # La foto inicial conserva la entrada para compararla con la salida.
    assert [_con_signo(p) for p in foto["iniciales"][0]] == [38, 27, 43, 3, 9, 82, 10, -4]
    assert servicio.salida_mmio() == "-4 3 9 10 27 38 43 82"


def test_merge_sort_sin_entrada_usa_su_vector_demo(servicio):
    _cargar(servicio, "merge_sort")
    servicio.ejecutar_hasta_fin()
    fotos = {f["nombre"]: f for f in servicio.instantaneas()}
    assert [_con_signo(p) for p in fotos["V"]["palabras"][0]] == [-12, -5, 0, 10, 23, 45, 77, 89]
    # El auxiliar copia la longitud actual de V.
    assert fotos["AUX"]["columnas"] == 8


def test_avanzar_reporta_las_celdas_leidas_y_escritas(servicio):
    servicio.definir_vector("V", [3, 1, 2])
    _cargar(servicio, "merge_sort")
    escrituras_en_v = []
    for _ in range(5000):
        estado = servicio.avanzar(1)
        escrituras_en_v += [a for a in estado["accesos"] if a["tipo"] == "escritura"
                            and BASE_VECTORES <= a["direccion"] < BASE_VECTORES + 24]
        if estado["detenido"]:
            break
    assert estado["detenido"]
    assert escrituras_en_v, "MERGE deberia escribir de vuelta en V"
    assert estado["instrucciones"] > 0 and estado["registros"]["PC"] > 0


def test_cada_carga_parte_de_los_datos_de_entrada(servicio):
    servicio.definir_vector("V", [2, 1])
    _cargar(servicio, "merge_sort")
    servicio.ejecutar_hasta_fin()
    servicio.cargar()  # recargar: la entrada vuelve a estar desordenada
    assert [_con_signo(p) for p in servicio.instantanea("V")["palabras"][0]] == [2, 1]


def test_la_etiqueta_sigue_al_pc_por_las_subrutinas(servicio):
    _cargar(servicio, "merge_sort")
    vistas = set()
    for _ in range(400):
        vistas.add(servicio.avanzar(1)["etiqueta"])
    assert {"PRINCIPAL", "VEC_SET"} & vistas


def test_cambiar_de_programa_descarta_lo_que_observaba_el_anterior(servicio):
    servicio.definir_vector("V", [1, 2])
    servicio.observar_programa(_programa(servicio, "merge_sort"))
    assert "AUX" in servicio.observadas
    servicio.observar_programa(_programa(servicio, "prueba_cabeceras_cargador"))
    assert "AUX" not in servicio.observadas
    assert {"V", "M", "RES"} <= set(servicio.observadas)


def test_programa_con_errores_no_lanza(servicio):
    resultado = servicio.compilar('#include "estructuras.inc"\n  NOEXISTE R1, R2\n')
    assert resultado["ok"] is False and resultado["error"]
    with pytest.raises(ValueError):
        servicio.cargar()


def test_una_cabecera_con_basura_no_congela_el_dibujo(servicio, maquina):
    maquina.memoria.escribir(BASE_VECTORES - 8, 10 ** 9, 8)
    servicio.observar("X", "vector", BASE_VECTORES, longitud=None)
    foto = servicio.instantanea("X")
    assert foto["columnas"] <= 256 and foto["nota"]


# ===========================================================================
# Panel con widgets reales
# ===========================================================================

_RAIZ = None


def _raiz():
    global _RAIZ
    if _RAIZ is None:
        try:
            _RAIZ = tk.Tk()
            _RAIZ.withdraw()
            aplicar_tema(_RAIZ)
        except Exception:
            _RAIZ = False
    return _RAIZ or None


grafico = pytest.mark.skipif(_raiz() is None, reason="se necesita un servidor grafico")


@pytest.fixture
def panel(maquina):
    from enigma64.ui.paneles.panel_estructuras import PanelEstructuras

    bus = BusEventos()
    raiz = _raiz()
    marco = tk.Frame(raiz)
    marco.pack()
    vista = PanelEstructuras(marco, servicio=maquina.estructuras, bus=bus)
    vista.pack(fill="both", expand=True)
    vista.preparar_demo()
    raiz.update_idletasks()
    yield vista
    vista.pausar()
    marco.destroy()


def _escribir(panel, tipo, texto, nombre=None):
    panel.tipo_entrada.set(tipo)
    panel._al_cambiar_tipo()
    if nombre:
        panel._fijar_campo(panel.campo_nombre, nombre)
    panel.campo_valores.delete("1.0", "end")
    panel.campo_valores.insert("1.0", texto)
    return panel.escribir_entrada()


@grafico
def test_el_panel_arranca_con_el_merge_sort_elegido(panel):
    assert panel.programa["clave"] == "merge_sort"
    assert {"V", "AUX"} <= set(panel._visores)


@grafico
def test_el_panel_dibuja_la_entrada_del_usuario(panel):
    entrada = _escribir(panel, "vector", "5, 3, 9")
    assert entrada is not None
    visor = panel._visores["V"]["visor"]
    assert [_con_signo(p) for p in visor.palabras[0]] == [5, 3, 9]
    assert "tu entrada" in panel._visores["V"]["titulo"].cget("text")
    assert panel.lista_entradas.size() == 1

    _escribir(panel, "matriz", "1 2\n3 4", nombre="A")
    assert panel._visores["A"]["visor"].palabras == [[1, 2], [3, 4]]


@grafico
def test_el_panel_avisa_de_una_entrada_invalida_sin_romperse(panel):
    assert _escribir(panel, "matriz", "1 2; 3") is None
    assert "columnas" in panel.mensaje_entrada.cget("text")


@grafico
def test_el_panel_ejecuta_y_muestra_entrada_y_salida(panel):
    _escribir(panel, "vector", "4, 1, 3, 2")
    assert panel.compilar_y_cargar()
    estado = panel.ejecutar_todo()
    assert estado["detenido"]
    assert panel._datos["estado"].cget("text") == "HLT"
    assert panel.pantalla.cget("text") == "1 2 3 4"
    comparacion = panel._visores["V"]["comparacion"].cget("text")
    assert "entrada  [4, 1, 3, 2]" in comparacion and "salida   [1, 2, 3, 4]" in comparacion


@grafico
def test_pasos_iluminan_celdas_y_publican_en_el_bus(panel):
    eventos = []
    panel.bus.suscribir_todo(lambda m: eventos.append(m.evento))
    _escribir(panel, "vector", "2, 1")
    panel.compilar_y_cargar()
    iluminadas = False
    for _ in range(600):
        estado = panel.avanzar(1)
        visor = panel._visores["V"]["visor"]
        iluminadas = iluminadas or bool(visor.escritas or visor.leidas)
        if estado["detenido"]:
            break
    assert iluminadas
    assert Evento.ESTRUCTURA_DEFINIDA in eventos
    assert Evento.PROGRAMA_CARGADO in eventos
    assert Evento.ESTRUCTURAS_ACTUALIZADAS in eventos


@grafico
def test_pulsar_una_celda_muestra_su_direccion_y_salta_en_memoria(panel):
    destinos = []
    panel.bus.suscribir(Evento.IR_A_DIRECCION, lambda m: destinos.append(m.get("direccion")))
    _escribir(panel, "vector", "7, 8, 9")
    panel.seleccionar_celda("V", 0, 2)
    assert "0x00220010" in panel.detalle_celda.cget("text")
    assert destinos[-1] == BASE_VECTORES + 16


@grafico
def test_cambiar_de_formato_redibuja_en_hexadecimal(panel):
    _escribir(panel, "vector", "-1")
    panel.formato.set("hex")
    panel.refrescar()
    assert panel._visores["V"]["visor"].formato == "hex"


@grafico
def test_la_animacion_avanza_y_se_puede_pausar(panel):
    _escribir(panel, "vector", "3, 2, 1")
    panel.compilar_y_cargar()
    panel.alternar_animacion()
    assert panel._animando
    panel.pausar()
    assert not panel._animando and panel._tarea is None
