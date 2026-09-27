"""
Pruebas de los tres modulos que la interfaz preparo para el resto del equipo:
la Unidad de Control (pendiente), la I/O mapeada y los algoritmos de la Tarea 9.

Ninguna necesita pantalla.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import pytest

from enigma64.ui.servicios import algoritmos as cat
from enigma64.ui.servicios import mmio
from enigma64.ui.servicios.adaptadores import AdaptadorCPU, AdaptadorMMIO
from enigma64.ui.servicios import construir_maquina
from enigma64.ui.servicios.puertos import (
    FASES_FSM, MICRO_REGISTROS, ServicioNoDisponible,
)


# ===========================================================================
# Algoritmos de verificacion
# ===========================================================================


def test_estan_los_tres_algoritmos_del_documento():
    assert cat.claves() == ("factorial", "euclides", "fibonacci")


@pytest.mark.parametrize("clave", cat.claves())
def test_las_direcciones_del_listado_encajan_con_el_codigo(clave):
    """
    Cada direccion del documento debe coincidir con la suma de las longitudes
    de las instrucciones anteriores. Detecta una traduccion manual mal cuadrada.
    """
    assert cat.direcciones_coherentes(cat.obtener(clave))


@pytest.mark.parametrize("clave, bytes_esperados", [
    ("factorial", 41), ("euclides", 50), ("fibonacci", 63),
])
def test_el_tamano_del_programa_es_el_del_documento(clave, bytes_esperados):
    assert cat.tamano(cat.obtener(clave)) == bytes_esperados


def test_el_factorial_empieza_con_la_traduccion_manual_del_documento():
    # 0x00200000: ADDI R1, R0, 0x0020 -> 14 10 00 20
    assert cat.codigo_maquina(cat.obtener("factorial"))[:4] == b"\x14\x10\x00\x20"


def test_euclides_usa_saltos_absolutos_de_cinco_bytes():
    """JMP es formato 5 (5 bytes): opcode 0x40 + direccion de 32 bits."""
    listado = cat.obtener("euclides")["listado"]
    saltos = [octetos for _d, mnemonico, octetos, _c in listado
              if mnemonico.startswith("JMP")]
    assert saltos, "Euclides debe contener saltos incondicionales"
    for octetos in saltos:
        assert len(octetos) == 5
        assert octetos[0] == 0x40
        assert int.from_bytes(octetos[1:], "big") == 0x00200114


def test_todos_los_programas_terminan_en_hlt():
    for clave in cat.claves():
        assert cat.codigo_maquina(cat.obtener(clave))[-1] == 0x00


def test_los_programas_caben_en_la_region_de_usuario():
    for clave in cat.claves():
        algoritmo = cat.obtener(clave)
        assert algoritmo["base"] >= 0x00200000
        assert algoritmo["base"] + cat.tamano(algoritmo) <= 0xC0000000
        assert algoritmo["datos"] >= 0x00200000


def test_los_programas_no_se_pisan_entre_si():
    rangos = []
    for clave in cat.claves():
        algoritmo = cat.obtener(clave)
        rangos.append((algoritmo["base"], algoritmo["base"] + cat.tamano(algoritmo)))
    for i, (inicio_a, fin_a) in enumerate(rangos):
        for inicio_b, fin_b in rangos[i + 1:]:
            assert fin_a <= inicio_b or fin_b <= inicio_a, "dos algoritmos se solapan"


def test_cargar_un_algoritmo_deja_los_bytes_exactos_en_la_ram():
    maquina = construir_maquina()
    algoritmo = maquina.algoritmos.obtener("factorial")
    informe = maquina.algoritmos.cargar(algoritmo)

    esperado = maquina.algoritmos.codigo_maquina(algoritmo)
    real = bytes(maquina.memoria.leer_byte(algoritmo["base"] + i)
                 for i in range(len(esperado)))
    assert real == esperado
    assert informe["entry_point"] == algoritmo["base"]
    assert maquina.registros.banco.pc == algoritmo["base"]


def test_cargar_siembra_los_datos_de_entrada():
    maquina = construir_maquina()
    maquina.algoritmos.cargar(maquina.algoritmos.obtener("euclides"))
    assert maquina.memoria.leer(0x00202000, 8)[0] == 48   # A
    assert maquina.memoria.leer(0x00202008, 8)[0] == 18   # B


def test_verificar_antes_de_ejecutar_no_da_falso_positivo():
    """Sin CPU nadie ha escrito el resultado, asi que no puede dar por bueno."""
    maquina = construir_maquina()
    algoritmo = maquina.algoritmos.obtener("factorial")
    maquina.algoritmos.cargar(algoritmo)
    veredicto = maquina.algoritmos.verificar(algoritmo)
    assert veredicto["ok"] is False
    assert veredicto["esperado"] == 120


def test_verificar_reconoce_el_resultado_correcto():
    """Se simula lo que escribiria la CPU y la verificacion debe aceptarlo."""
    maquina = construir_maquina()
    algoritmo = maquina.algoritmos.obtener("factorial")
    maquina.algoritmos.cargar(algoritmo)
    maquina.memoria.escribir(0x00201008, 120, 8)
    assert maquina.algoritmos.verificar(algoritmo)["ok"] is True


def test_fibonacci_se_verifica_como_secuencia_completa():
    maquina = construir_maquina()
    algoritmo = maquina.algoritmos.obtener("fibonacci")
    maquina.algoritmos.cargar(algoritmo)
    for indice, valor in enumerate([0, 1, 1, 2, 3, 5, 8]):
        maquina.memoria.escribir(0x00203000 + indice * 8, valor, 8)
    veredicto = maquina.algoritmos.verificar(algoritmo)
    assert veredicto["es_secuencia"] and veredicto["ok"]
    assert veredicto["obtenido"] == [0, 1, 1, 2, 3, 5, 8]


def test_ejecutar_sin_cpu_explica_que_falta():
    maquina = construir_maquina()
    with pytest.raises(ServicioNoDisponible, match="Unidad de Control"):
        maquina.algoritmos.ejecutar()


# ===========================================================================
# I/O mapeada en memoria
# ===========================================================================


def test_los_cinco_controladores_del_documento():
    assert [c["base"] for c in mmio.CONTROLADORES] == [
        0xFF000000, 0xFF001000, 0xFF002000, 0xFF003000, 0xFF004000]


def test_cada_controlador_ocupa_una_pagina_de_4_kib():
    for anterior, siguiente in zip(mmio.CONTROLADORES, mmio.CONTROLADORES[1:]):
        assert siguiente["base"] - anterior["base"] == mmio.TAMANO_PAGINA


def test_los_registros_van_en_desplazamientos_de_ocho_bytes():
    assert [d for d, _n, _x in mmio.REGISTROS] == [0x00, 0x08, 0x10, 0x18, 0x20]


@pytest.mark.parametrize("direccion, controlador, registro", [
    (0xFF002018, "Memoria secundaria (disco)", "ADDR"),
    (0xFF001010, "Salida (pantalla)", "DATA"),
    (0xFF004000, "Temporizador / reloj", "CTRL"),
    (0xFF003010, "Interfaz de red", "NET_MAC"),
])
def test_descomponer_una_direccion_mmio(direccion, controlador, registro):
    ctrl, _despl, nombre = mmio.descomponer(direccion)
    assert ctrl["nombre"] == controlador
    assert nombre == registro


def test_una_direccion_fuera_de_mmio_no_tiene_controlador():
    assert mmio.descomponer(0x00200000) == (None, 0, None)


def test_la_red_especializa_los_mismos_desplazamientos():
    nombres = [n for _d, n, _x in mmio.registros_de("red")]
    assert nombres == ["NET_CTRL", "NET_STATUS", "NET_MAC", "NET_TX_ADDR", "NET_TX_LEN"]
    # Los demas controladores conservan los nombres genericos.
    assert [n for _d, n, _x in mmio.registros_de("disco")][:3] == ["CTRL", "STATUS", "DATA"]


def test_el_banco_provisional_arranca_con_los_controladores_listos():
    banco = mmio.BancoMMIOProvisional()
    for controlador in mmio.CONTROLADORES:
        assert banco.leer(controlador["base"], 0x08) == 1   # STATUS = listo


def test_el_adaptador_mmio_lee_y_escribe():
    adaptador = AdaptadorMMIO()
    adaptador.escribir(0xFF002000, 0x18, 0x2A)      # LBA en DSK_ADDR
    assert adaptador.leer(0xFF002000, 0x18) == 0x2A
    adaptador.reiniciar()
    assert adaptador.leer(0xFF002000, 0x18) == 0


def test_el_adaptador_mmio_avisa_de_que_es_provisional():
    adaptador = AdaptadorMMIO()
    assert adaptador.es_provisional is True
    assert "provisional" in adaptador.advertencia.lower()


def test_el_adaptador_mmio_prefiere_el_modulo_real_si_existe():
    class PerifericosDelEquipo:
        es_provisional = False
        def __init__(self): self.datos = {}
        def leer(self, base, despl): return self.datos.get((base, despl), 0xFF)
        def escribir(self, base, despl, valor): self.datos[(base, despl)] = valor
        def reiniciar(self): self.datos.clear()

    adaptador = AdaptadorMMIO(banco=PerifericosDelEquipo())
    assert adaptador.es_provisional is False
    assert adaptador.advertencia == ""
    assert adaptador.leer(0xFF000000, 0x00) == 0xFF


# ===========================================================================
# Unidad de Control (modulo pendiente)
# ===========================================================================


def test_la_cpu_esta_pendiente_y_lo_dice_con_claridad():
    maquina = construir_maquina()
    assert maquina.cpu.disponible is False
    assert "cpu" in maquina.cpu.motivo.lower()
    assert "Integrante 3" in maquina.cpu.motivo


def test_la_cpu_ausente_no_rompe_el_resto_de_la_maquina():
    maquina = construir_maquina()
    assert maquina.memoria.disponible and maquina.registros.disponible
    assert maquina.alu.disponible and maquina.cargador.disponible


def test_el_estado_de_una_cpu_ausente_es_neutro_y_completo():
    """El panel no debe tener que comprobar si cada clave existe."""
    estado = construir_maquina().cpu.estado()
    assert estado["fase"] == FASES_FSM[0]
    assert estado["ciclos"] == 0 and estado["instrucciones"] == 0
    assert set(estado["micro"]) == set(MICRO_REGISTROS)
    assert estado["detenido"] is False


def test_las_fases_y_micro_registros_son_los_de_la_tarea_9():
    adaptador = construir_maquina().cpu
    assert tuple(adaptador.fases()) == (
        "FETCH", "DECODE", "EXECUTE", "MEMORY", "WRITE-BACK")
    assert tuple(adaptador.micro_registros()) == ("MAR", "MDR", "IR", "A", "B", "Z")


class _CPUEnEspanol:
    def __init__(self, ram=None, banco=None): self.ciclos = 0
    def paso(self): self.ciclos += 1
    def paso_instruccion(self): self.ciclos += 5
    def ejecutar(self, max_ciclos=100000): self.ciclos += 50
    def reiniciar(self): self.ciclos = 0
    def estado(self):
        return {"fase": "EXECUTE", "ciclos": self.ciclos,
                "instrucciones": self.ciclos // 5, "detenido": self.ciclos >= 50,
                "micro": {"MAR": 0x200000, "IR": 0x14100020}}


class _CPUEnIngles:
    def __init__(self, ram=None, banco=None): self.n = 0
    def step(self): self.n += 1
    def run(self, max_ciclos=100000): self.n += 50
    def reset(self): self.n = 0
    def state(self):
        return {"fase": "DECODE", "ciclos": self.n, "micro": {"MDR": 7}}


@pytest.mark.parametrize("clase", [_CPUEnEspanol, _CPUEnIngles],
                         ids=["nombres_en_espanol", "nombres_en_ingles"])
def test_el_adaptador_engancha_una_cpu_por_pato(clase):
    """
    El Integrante 3 no tiene que acertar la nomenclatura exacta: el adaptador
    acepta tanto paso/ejecutar/estado como step/run/state.
    """
    adaptador = AdaptadorCPU(cpu=clase())
    assert adaptador.disponible
    assert adaptador.paso()["ciclos"] == 1
    assert adaptador.ejecutar()["ciclos"] == 51
    adaptador.reiniciar()
    assert adaptador.estado()["ciclos"] == 0


def test_el_adaptador_normaliza_los_micro_registros_que_falten():
    """Si la CPU solo informa de algunos, el resto sale en cero, no ausente."""
    estado = AdaptadorCPU(cpu=_CPUEnIngles()).estado()
    assert estado["micro"]["MDR"] == 7
    assert estado["micro"]["MAR"] == 0
    assert set(estado["micro"]) == set(MICRO_REGISTROS)


def test_una_cpu_incompleta_avisa_de_la_operacion_que_falta():
    class CPUAMedias:
        def estado(self): return {"fase": "FETCH"}

    adaptador = AdaptadorCPU(cpu=CPUAMedias())
    with pytest.raises(ServicioNoDisponible, match="paso_instruccion"):
        adaptador.paso_instruccion()


def test_una_cpu_que_lanza_en_estado_no_tumba_el_panel():
    class CPUDefectuosa:
        def estado(self): raise RuntimeError("FSM sin inicializar")

    estado = AdaptadorCPU(cpu=CPUDefectuosa()).estado()
    assert "FSM sin inicializar" in estado["error"]
    assert estado["fase"] == "FETCH"      # sigue siendo utilizable


def test_la_maquina_expone_los_seis_modulos():
    maquina = construir_maquina()
    assert set(maquina.servicios) == {
        "memoria", "registros", "alu", "cargador", "cpu", "mmio"}
    assert maquina.total_modulos == 6
    assert maquina.modulos_disponibles == 5   # falta la CPU del Integrante 3
