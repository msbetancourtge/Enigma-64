"""
Pruebas del nucleo de la interfaz: formato, bus de eventos y servicios.

Ninguna de estas pruebas necesita pantalla, asi que corren en cualquier
maquina y en integracion continua.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import pytest

from enigma64.ui.core.bus import BusEventos, BusNulo, Evento, Mensaje
from enigma64.ui.core.formato import (
    ValorInvalido, ascii_imprimible, bin8, bin64_agrupado, con_signo,
    hex32, hex64, hex_ancho, parsear_direccion, parsear_entero, tamano_legible,
)
from enigma64.ui.servicios import construir_maquina
from enigma64.ui.servicios.mapa_memoria import REGIONES, nombre_region, region_de


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("texto, esperado", [
    ("0x1F", 31), ("0X1f", 31), ("$1F", 31), ("1Fh", 31),
    ("0b1011", 11), ("1011b", 11), ("0o17", 15),
    ("42", 42), ("-42", -42), ("1_000", 1000), ("  7  ", 7),
])
def test_parsear_entero_acepta_las_bases_de_la_documentacion(texto, esperado):
    assert parsear_entero(texto) == esperado


@pytest.mark.parametrize("texto", ["", "   ", "0xZZ", "ocho", "-", "0b12"])
def test_parsear_entero_rechaza_basura(texto):
    with pytest.raises(ValorInvalido):
        parsear_entero(texto)


def test_las_direcciones_sin_prefijo_se_leen_en_hexadecimal():
    # Asi estan escritas en el mapa de memoria de la Tarea 9.
    assert parsear_direccion("200000") == 0x00200000
    assert parsear_direccion("0x200000") == 0x00200000
    assert parsear_direccion("FF001000") == 0xFF001000


def test_una_direccion_no_puede_ser_negativa():
    with pytest.raises(ValorInvalido):
        parsear_direccion("-8")


def test_formatos_de_salida():
    assert hex64(0x200000) == "0x0000000000200000"
    assert hex32(0x200000) == "0x00200000"
    assert hex_ancho(0xCAFE, 2) == "0xCAFE"
    assert hex_ancho(0xCAFE, 8) == "0x000000000000CAFE"
    assert bin8(5) == "00000101"
    assert bin64_agrupado(1).endswith("00000001")
    assert len(bin64_agrupado(0).split()) == 8


def test_complemento_a_dos():
    assert con_signo(0xFFFFFFFFFFFFFFFF) == -1
    assert con_signo(0x8000000000000000) == -(2 ** 63)
    assert con_signo(120) == 120


def test_ascii_y_tamanos():
    assert ascii_imprimible(0x41) == "A"
    assert ascii_imprimible(0x00) == "."
    assert tamano_legible(4096) == "4 KiB"
    assert tamano_legible(1536) == "1.5 KiB"
    assert tamano_legible(10) == "10 B"


# ---------------------------------------------------------------------------
# Bus de eventos
# ---------------------------------------------------------------------------


def test_el_bus_entrega_a_los_suscriptores():
    bus = BusEventos()
    recibidos = []
    bus.suscribir(Evento.BUS_SENAL, lambda m: recibidos.append(m.get("estado")))
    bus.publicar(Evento.BUS_SENAL, estado="READY")
    assert recibidos == ["READY"]


def test_el_comodin_recibe_todo():
    bus = BusEventos()
    vistos = []
    bus.suscribir_todo(lambda m: vistos.append(m.evento))
    bus.publicar(Evento.MEMORIA_LEIDA)
    bus.publicar(Evento.ALU_EJECUTADA)
    assert vistos == [Evento.MEMORIA_LEIDA, Evento.ALU_EJECUTADA]


def test_un_oyente_roto_no_tumba_a_los_demas():
    """Es la garantia de aislamiento: un panel con un fallo no rompe el resto."""
    bus = BusEventos()
    sanos = []

    def roto(_mensaje):
        raise RuntimeError("panel defectuoso")

    bus.suscribir(Evento.TRAZA, roto)
    bus.suscribir(Evento.TRAZA, lambda m: sanos.append(m.get("texto")))

    bus.traza("sigo vivo")

    assert sanos == ["sigo vivo"]
    assert len(bus.errores) == 1
    assert "panel defectuoso" in bus.errores[0]


def test_desuscribir_detiene_la_entrega():
    bus = BusEventos()
    recibidos = []
    oyente = bus.suscribir(Evento.TRAZA, lambda m: recibidos.append(1))
    bus.traza("uno")
    bus.desuscribir(Evento.TRAZA, oyente)
    bus.traza("dos")
    assert len(recibidos) == 1


def test_el_historial_no_crece_sin_limite():
    bus = BusEventos()
    for i in range(700):
        bus.publicar(Evento.TRAZA, texto=str(i))
    assert len(bus.historial) == 500


def test_el_bus_nulo_no_entrega_nada():
    """Es el bus que recibe un panel cuando se arranca suelto."""
    bus = BusNulo()
    recibidos = []
    bus.suscribir(Evento.TRAZA, lambda m: recibidos.append(m))
    resultado = bus.publicar(Evento.TRAZA, texto="al vacio")
    assert isinstance(resultado, Mensaje)
    assert recibidos == []


# ---------------------------------------------------------------------------
# Mapa de memoria
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("direccion, esperado", [
    (0x00000000, "Vectores"),
    (0x00001000, "Monitor + Enlazador-Cargador"),
    (0x00200000, "Programas y datos"),
    (0xBFFFFFFF, "Programas y datos"),
    (0xC0000000, "Pila"),
    (0xFF001000, "I/O mapeada"),
    (0x100000000, "No mapeado"),
])
def test_cada_direccion_cae_en_su_region(direccion, esperado):
    assert nombre_region(direccion) == esperado


def test_las_regiones_cubren_los_4_gib_sin_huecos():
    ordenadas = sorted(REGIONES, key=lambda r: r["inicio"])
    assert ordenadas[0]["inicio"] == 0x00000000
    assert ordenadas[-1]["fin"] == 0xFFFFFFFF
    for anterior, siguiente in zip(ordenadas, ordenadas[1:]):
        assert siguiente["inicio"] == anterior["fin"] + 1, (
            f"hueco entre {anterior['nombre']} y {siguiente['nombre']}")


def test_fuera_de_los_4_gib_no_hay_region():
    assert region_de(0x1_0000_0000) is None


# ---------------------------------------------------------------------------
# Servicios
# ---------------------------------------------------------------------------


def test_la_maquina_conecta_los_cuatro_modulos():
    maquina = construir_maquina()
    assert maquina.total_modulos == 4
    for informe in maquina.informe():
        assert informe["disponible"], f"{informe['modulo']}: {informe['motivo']}"


def test_dos_maquinas_no_comparten_estado():
    """Cada panel suelto tiene su propio hardware."""
    a, b = construir_maquina(), construir_maquina()
    a.memoria.escribir(0x00200000, 0xFF, 1)
    assert a.memoria.leer(0x00200000, 1)[0] == 0xFF
    assert b.memoria.leer(0x00200000, 1)[0] == 0x00


def test_el_adaptador_de_memoria_respeta_las_reglas_del_bus():
    maquina = construir_maquina()
    assert maquina.memoria.escribir(0x00200000, 0xCAFE, 2)[1] == "READY"
    assert maquina.memoria.leer(0x00200000, 2) == (0xCAFE, "READY")
    assert maquina.memoria.leer(0x00200001, 2)[1] == "MISALIGNED"
    assert maquina.memoria.leer(0xFF001000, 8)[1] == "MMIO"
    assert maquina.memoria.leer(0x1_0000_0000, 8)[1] == "ADDR_FAULT"


def test_la_lectura_de_byte_para_el_volcado_nunca_lanza():
    maquina = construir_maquina()
    assert maquina.memoria.leer_byte(0xFF001000) == 0      # MMIO
    assert maquina.memoria.leer_byte(0x1_0000_0000) == 0   # fuera del mapa


def test_el_adaptador_de_registros_respeta_r0():
    maquina = construir_maquina()
    maquina.registros.escribir_nombre("R0", 0xFFFF)
    assert maquina.registros.leer_nombre("R0") == 0
    assert maquina.registros.es_solo_lectura("R0")
    assert not maquina.registros.es_solo_lectura("R1")


def test_el_adaptador_de_registros_conmuta_banderas():
    maquina = construir_maquina()
    antes = maquina.registros.banco.leer_bandera("C")
    assert maquina.registros.alternar_bandera("C") == (0 if antes else 1)


def test_el_adaptador_de_alu_normaliza_el_resultado():
    maquina = construir_maquina()
    resultado = maquina.alu.ejecutar("ADD", 120, 5)
    assert resultado["valor"] == 125
    assert resultado["hex"] == "0x000000000000007D"
    assert resultado["escribe_destino"] is True
    assert set(resultado["afectadas"]) == {"Z", "N", "C", "V"}


def test_cmp_no_escribe_el_destino():
    maquina = construir_maquina()
    assert maquina.alu.ejecutar("CMP", 5, 5)["escribe_destino"] is False


def test_las_operaciones_unarias_ignoran_el_segundo_operando():
    maquina = construir_maquina()
    assert maquina.alu.es_unaria("INC")
    assert not maquina.alu.es_unaria("ADD")
    assert maquina.alu.ejecutar("INC", 7, 999)["valor"] == 8


def test_volcar_banderas_al_sr_actualiza_el_banco():
    maquina = construir_maquina()
    maquina.alu.ejecutar("SUB", 5, 5, volcar_sr=True)
    assert maquina.registros.banco.leer_bandera("Z") == 1


def test_todas_las_operaciones_del_isa_estan_expuestas():
    maquina = construir_maquina()
    operaciones = set(maquina.alu.operaciones())
    esperadas = {"ADD", "SUB", "MUL", "DIV", "ADDI", "SUBI", "INC", "DEC",
                 "AND", "OR", "XOR", "NOT", "SHL", "SHR", "ASR", "CMP"}
    assert esperadas <= operaciones
    # Y todas quedan clasificadas en alguna familia del selector.
    clasificadas = set()
    for ops in maquina.alu.operaciones_por_familia().values():
        clasificadas.update(ops)
    assert esperadas <= clasificadas


def test_el_cargador_rechaza_invadir_los_vectores():
    from enigma64.cargador import ViolacionProteccionMemoria
    maquina = construir_maquina()
    with pytest.raises(ViolacionProteccionMemoria):
        maquina.cargador.cargar_texto("10 12 30", destino=0x00000100)


def test_el_cargador_rechaza_invadir_la_pila():
    from enigma64.cargador import ViolacionProteccionMemoria
    maquina = construir_maquina()
    with pytest.raises(ViolacionProteccionMemoria):
        maquina.cargador.cargar_texto("10 12 30", destino=0xBFFFFFFF)


def test_una_carga_valida_inicializa_el_contexto_de_cpu():
    maquina = construir_maquina()
    informe = maquina.cargador.cargar_texto("10 12 30 00", destino=0x00200000)
    assert informe["direccion_base"] == 0x00200000
    assert informe["tamano_total"] == 4
    assert maquina.registros.banco.pc == 0x00200000
    assert maquina.registros.banco.leer_nombre("R5") == 0x00200000
    # Y los bytes quedaron realmente en la RAM compartida.
    assert maquina.memoria.leer_byte(0x00200000) == 0x10


def test_el_manipulador_de_bits_opera_sobre_la_misma_ram():
    maquina = construir_maquina()
    maquina.memoria.escribir(0x00200000, 0x10, 1)
    assert maquina.cargador.byte_en_bits(0x00200000) == "00010000"
    assert maquina.cargador.conmutar_bit(0x00200000, 0) == 1
    assert maquina.memoria.leer_byte(0x00200000) == 0x11
    maquina.cargador.escribir_bit(0x00200000, 0, 0)
    assert maquina.memoria.leer_byte(0x00200000) == 0x10
