"""
Suite de pruebas automatizadas para el modulo del Integrante 4 (Tarea 29):
  - Empaquetado maestro de spl/include/estructuras.inc y spl/include/cabeceras.asm.
  - Constructores y descriptores de cabeceras de listas y matrices en ensamblador (CPU real).
  - Descriptores Python (DescriptorVector, DescriptorMatriz, MapaEstructurasRAM),
    normalizacion Big-Endian de 64 bits (enteros y IEEE 754) y alineacion de 8 bytes.
  - Puente Preprocesador -> Ensamblador -> BinarioEnigma (.e64) -> CargadorEnigma -> CPU,
    incluyendo interoperabilidad con vec.asm (Integrante 2) y merge_sort.asm (Integrante 6).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from enigma64.cargador import (
    MAGIC_ENIGMA,
    BinarioEnigma,
    CargadorEnigma,
    ViolacionProteccionMemoria,
)
from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory
from enigma64.perifericos import Perifericos
from enigma64.registros import BancoRegistros
from spl.estructuras import (
    BASE_BUFFERS,
    BASE_CABECERAS,
    BASE_CODIGO,
    BASE_MATRICES,
    BASE_VECTORES,
    INT64_MAX,
    INT64_MIN,
    PILA_ESTRUCTURAS,
    TIPO_MATRIZ,
    TIPO_VECTOR,
    UINT64_MAX,
    DescriptorMatriz,
    DescriptorVector,
    ErrorEstructuraDatos,
    MapaEstructurasRAM,
    cargar_y_ejecutar_estructuras,
    compilar_a_binario_e64,
    desnormalizar_entero_64,
    desnormalizar_float_64,
    direccion_descriptor,
    exportar_estructuras_e64,
    leer_descriptor_de_ram,
    leer_matriz_de_ram,
    leer_vector_de_ram,
    normalizar_palabra_64,
    precargar_matriz_en_ram,
    precargar_vector_en_ram,
)
from spl.estructuras.__main__ import main as cli_main
from spl.ensamblador import EnsambladorLexer
from spl.preprocesador import preprocesar_texto


RAIZ = Path(__file__).resolve().parents[2]
DIR_EJEMPLOS = RAIZ / "spl" / "ejemplos"
PRUEBA_CABECERAS_ASM = DIR_EJEMPLOS / "prueba_cabeceras_cargador.asm"
PRUEBA_VEC_ASM = DIR_EJEMPLOS / "prueba_vec.asm"
MERGE_SORT_ASM = DIR_EJEMPLOS / "merge_sort.asm"


# ==============================================================================
# 1. Pruebas de Empaquetado Maestro (estructuras.inc y cabeceras.asm)
# ==============================================================================


class TestEmpaquetadoEstructurasInc:
    def test_inclusion_maestra_inyecta_layout_vec_y_cabeceras(self):
        res = preprocesar_texto('#include "estructuras.inc"\nHLT\n')
        for etiqueta in (
            "VEC_ADDR:",
            "VEC_GET:",
            "VEC_SET:",
            "VEC_SWAP:",
            "VEC_COPY:",
            "VEC_LEN:",
            "VEC_INIT:",
            "MAT_INIT:",
            "MAT_ROWS:",
            "MAT_COLS:",
            "DESC_ADDR:",
            "DESC_VEC_INIT:",
            "DESC_MAT_INIT:",
            "DESC_GET_TIPO:",
            "DESC_GET_BASE:",
            "DESC_GET_FILAS:",
            "DESC_GET_COLS:",
        ):
            assert etiqueta in res.texto, f"Falta subrutina {etiqueta} tras incluir estructuras.inc"
        assert "BASE_CABECERAS" in res.macros
        assert "BASE_VECTORES" in res.macros
        assert "BASE_MATRICES" in res.macros
        assert "DESC_DIR" in res.macros

    def test_doble_inclusion_no_duplica_etiquetas(self):
        codigo = (
            '#include "estructuras.inc"\n'
            '#include <estructuras.inc>\n'
            '#include "cabeceras.asm"\n'
            '#include "vec.asm"\n'
            "HLT\n"
        )
        res = preprocesar_texto(codigo)
        assert res.texto.count("JMP VEC_FIN_LIBRERIA") == 1
        assert res.texto.count("JMP CAB_FIN_LIBRERIA") == 1
        binario = ensamblar(res.texto, direccion_base=BASE_CODIGO)
        assert len(binario) > 0

    def test_lexer_ensamblador_sin_errores_sobre_libreria_completa(self):
        texto = preprocesar_texto('#include "estructuras.inc"\nHLT\n').texto
        tokens, errores = EnsambladorLexer().tokenizar(texto)
        assert errores == []
        assert len(tokens) > 0

    def test_macro_desc_dir_coincide_con_aritmetica_de_slots(self):
        res = preprocesar_texto('#include "estructuras.inc"\nint d = DESC_DIR(3);\n')
        assert "0x00210000 + ((3) << 5)" in res.texto
        assert eval("0x00210000 + ((3) << 5)") == direccion_descriptor(3)

    def test_gancho_condicional_incluir_matrices_con_modulo_2d(self):
        # El modulo 2D real (spl/include/mat.asm, Integrante 3) reemplaza al mock:
        # un #include "..." busca primero junto a estructuras.inc.
        codigo = '#include "estructuras.inc"\nADDI R1, R0, 9\nHLT\n'
        res = cargar_y_ejecutar_estructuras(
            codigo,
            es_archivo=False,
            definiciones={"INCLUIR_MATRICES": "1"},
        )
        assert "\nMAT_ADDR:" in res.texto_preprocesado
        assert res.banco.leer_nombre("R1") == 9


# ==============================================================================
# 2. Pruebas de Constructores de Cabeceras en Ensamblador sobre CPU Real
# ==============================================================================


class TestCabecerasEnsambladorCPU:
    def test_programa_ejemplo_cabeceras_completo(self):
        res = cargar_y_ejecutar_estructuras(PRUEBA_CABECERAS_ASM, es_archivo=True)
        resultados = res.leer_vector(direccion_base=BASE_BUFFERS, longitud=10, modo="uint")

        assert resultados == [
            0x00210000,  # RES[0]: dir descriptor slot 0
            5,           # RES[1]: VEC_LEN(0x00220000)
            0x00210020,  # RES[2]: dir descriptor slot 1
            3,           # RES[3]: MAT_ROWS(0x00260000)
            4,           # RES[4]: MAT_COLS(0x00260000)
            TIPO_MATRIZ, # RES[5]: DESC_GET_TIPO(slot 1)
            0x00260000,  # RES[6]: DESC_GET_BASE(slot 1)
            3,           # RES[7]: DESC_GET_FILAS(slot 1)
            4,           # RES[8]: DESC_GET_COLS(slot 1)
            10,          # RES[9]: MAT_INIT(2, 5) -> 10
        ]
        assert res.banco.sp == PILA_ESTRUCTURAS

        desc0 = res.leer_descriptor(0)
        assert desc0["tipo"] == TIPO_VECTOR
        assert desc0["direccion_base"] == BASE_VECTORES
        assert desc0["longitud"] == 5
        assert desc0["columnas"] == 1

        desc1 = res.leer_descriptor(1)
        assert desc1["tipo"] == TIPO_MATRIZ
        assert desc1["direccion_base"] == BASE_MATRICES
        assert desc1["filas"] == 3
        assert desc1["columnas"] == 4

    def test_vec_init_y_preservacion_callee_saved(self):
        asm = """
        #include "estructuras.inc"
        MAIN:
                ADDI R1, R0, 0x0022
                SHL  R1, R1, 16
                ADDI R2, R0, 12
                ADDI R3, R0, 77
                ADDI R4, R0, 88
                ADDI BP, R0, 0x1234
                CALL VEC_INIT
                CALL VEC_LEN
                HLT
        """
        res = cargar_y_ejecutar_estructuras(asm, es_archivo=False)
        assert res.banco.leer_nombre("R1") == BASE_VECTORES
        assert res.banco.leer_nombre("R2") == 12
        assert res.banco.leer_nombre("R3") == 77
        assert res.banco.leer_nombre("R4") == 88
        assert res.banco.leer_nombre("R5") == 12
        assert res.banco.bp == 0x1234
        assert res.banco.sp == PILA_ESTRUCTURAS
        assert res.ram.mem_read(BASE_VECTORES - 16, 8)[0] == 1
        assert res.ram.mem_read(BASE_VECTORES - 8, 8)[0] == 12

    def test_desc_vec_y_mat_init_preservan_registros_r1_a_r4(self):
        asm = """
        #include "estructuras.inc"
        MAIN:
                ADDI R1, R0, 2
                ADDI R2, R0, 0x0026
                SHL  R2, R2, 16
                ADDI R3, R0, 6
                ADDI R4, R0, 7
                CALL DESC_MAT_INIT
                HLT
        """
        res = cargar_y_ejecutar_estructuras(asm, es_archivo=False)
        assert res.banco.leer_nombre("R1") == 2
        assert res.banco.leer_nombre("R2") == BASE_MATRICES
        assert res.banco.leer_nombre("R3") == 6
        assert res.banco.leer_nombre("R4") == 7
        assert res.banco.leer_nombre("R5") == BASE_CABECERAS + 2 * 32
        assert res.banco.sp == PILA_ESTRUCTURAS


# ==============================================================================
# 3. Normalizacion de 64 Bits, Alineacion y Descriptores Python
# ==============================================================================


class TestNormalizacionYDescriptores:
    def test_normalizacion_enteros_extremos_y_complemento_a_dos(self):
        assert normalizar_palabra_64(0) == 0
        assert normalizar_palabra_64(-1) == UINT64_MAX
        assert normalizar_palabra_64(INT64_MIN) == (1 << 63)
        assert normalizar_palabra_64(INT64_MAX) == INT64_MAX
        assert normalizar_palabra_64(UINT64_MAX) == UINT64_MAX

        assert desnormalizar_entero_64(normalizar_palabra_64(-42), con_signo=True) == -42
        assert desnormalizar_entero_64(normalizar_palabra_64(INT64_MIN), con_signo=True) == INT64_MIN
        assert desnormalizar_entero_64(UINT64_MAX, con_signo=False) == UINT64_MAX

    def test_normalizacion_flotantes_ieee754_y_literales_texto(self):
        bits_menos_2_5 = normalizar_palabra_64(-2.5)
        assert bits_menos_2_5 == 0xC004000000000000
        assert desnormalizar_float_64(bits_menos_2_5) == -2.5

        # Preserva el bit de signo de -0.0
        bits_menos_cero = normalizar_palabra_64(-0.0)
        assert bits_menos_cero == 0x8000000000000000
        assert math.copysign(1.0, desnormalizar_float_64(bits_menos_cero)) == -1.0

        assert normalizar_palabra_64("-2.5") == 0xC004000000000000
        assert normalizar_palabra_64("0xFF") == 255
        assert normalizar_palabra_64("0b1010") == 10
        assert desnormalizar_float_64(normalizar_palabra_64("1.5e2")) == 150.0

    def test_rechaza_literales_fuera_de_rango_sin_valueerror_crudo_de_4300_digitos(self):
        gigante = "9" * 5000
        with pytest.raises(ErrorEstructuraDatos):
            normalizar_palabra_64(gigante)
        with pytest.raises(ErrorEstructuraDatos):
            normalizar_palabra_64(UINT64_MAX + 1)
        with pytest.raises(ErrorEstructuraDatos):
            normalizar_palabra_64(INT64_MIN - 1)
        with pytest.raises(ErrorEstructuraDatos):
            normalizar_palabra_64(float("inf"))
        with pytest.raises(ErrorEstructuraDatos):
            normalizar_palabra_64(float("nan"))

    def test_rechaza_direcciones_desalineadas_y_zonas_protegidas(self):
        with pytest.raises(ErrorEstructuraDatos, match="multiplo de 8"):
            DescriptorVector("desalineado", [1, 2, 3], direccion_base=BASE_VECTORES + 4)

        with pytest.raises(ViolacionProteccionMemoria):
            DescriptorVector("sistema", [1, 2], direccion_base=0x00001000, slot_cabecera=None)

        with pytest.raises(ViolacionProteccionMemoria):
            DescriptorMatriz.vacia("pila", 2, 2, direccion_base=0xC0000000, slot_cabecera=None)

    def test_linealizacion_row_major_matriz_coincide_con_macro_mat_dir(self):
        mat = DescriptorMatriz.desde_filas(
            "A",
            [
                [10, 20, 30],
                [40, 50, 60],
            ],
            direccion_base=BASE_MATRICES,
            slot_cabecera=1,
        )
        assert mat.filas == 2
        assert mat.columnas == 3
        assert mat.palabras_datos == [10, 20, 30, 40, 50, 60]

        for i in range(2):
            for j in range(3):
                # Verifica coincidencia exacta con MAT_DIR(base, cols, i, j)
                res_macro = preprocesar_texto(
                    f'#include "layout_datos.inc"\n{mat.direccion_base} == MAT_DIR({mat.direccion_base}, 3, {i}, {j})\n'
                ).texto.splitlines()[-1]
                expr_rhs = res_macro.split("==")[1].strip()
                assert mat.direccion_elemento(i, j) == eval(expr_rhs)

    def test_mapa_estructuras_detecta_solapamiento_de_datos_y_cabeceras(self):
        v1 = DescriptorVector("v1", [1, 2, 3, 4], direccion_base=BASE_VECTORES, slot_cabecera=0)
        # v1 ocupa [0x00220000 .. 0x00220020); si v2 inicia en 0x00220028 su cabecera inline
        # [0x00220018 .. 0x00220028) solapa con el ultimo elemento de v1!
        v2_colision = DescriptorVector(
            "v2", [9, 8], direccion_base=BASE_VECTORES + 0x28, slot_cabecera=1
        )
        with pytest.raises(ErrorEstructuraDatos, match="Solapamiento"):
            MapaEstructurasRAM([v1, v2_colision])

        # Colision de slot de cabecera en BASE_CABECERAS
        v3_mismo_slot = DescriptorVector(
            "v3", [9, 8], direccion_base=BASE_VECTORES + 0x100, slot_cabecera=0
        )
        with pytest.raises(ErrorEstructuraDatos, match="Solapamiento"):
            MapaEstructurasRAM([v1, v3_mismo_slot])


# ==============================================================================
# 4. Puente Completo Preprocesador -> Ensamblador -> .e64 -> CargadorEnigma
# ==============================================================================


class TestPuenteCargadorEnigmaE64:
    def test_precarga_y_lectura_directa_vectores_y_matrices_en_ram(self):
        ram = RAMMemory()
        precargar_vector_en_ram(
            ram,
            elementos=[-10, 0, 25, -999],
            direccion_base=BASE_VECTORES,
            nombre="vec_enteros",
            slot_cabecera=0,
        )
        precargar_matriz_en_ram(
            ram,
            filas_2d=[[1.5, -2.5], [3.25, 0.0]],
            direccion_base=BASE_MATRICES,
            nombre="mat_reales",
            slot_cabecera=1,
        )

        assert leer_vector_de_ram(ram, BASE_VECTORES, modo="int") == [-10, 0, 25, -999]
        assert leer_matriz_de_ram(ram, BASE_MATRICES, modo="float") == [[1.5, -2.5], [3.25, 0.0]]
        assert leer_descriptor_de_ram(ram, 0)["longitud"] == 4
        assert leer_descriptor_de_ram(ram, 1)["filas"] == 2
        assert leer_descriptor_de_ram(ram, 1)["columnas"] == 2

    def test_exportacion_e64_autocontenida_y_carga_con_cargador_enigma_puro(self, tmp_path):
        vec = DescriptorVector(
            nombre="lista_entrada",
            elementos=[80, -30, 15, 0, 42, -7],
            direccion_base=BASE_VECTORES,
            slot_cabecera=0,
        )
        ruta_e64 = tmp_path / "merge_sort_precargado.e64"
        binario = exportar_estructuras_e64(
            MERGE_SORT_ASM,
            ruta_e64,
            es_archivo=True,
            estructuras=[vec],
            incluir_datos_en_imagen=True,
        )

        contenido_disco = ruta_e64.read_bytes()
        assert contenido_disco[:4] == MAGIC_ENIGMA
        deserializado = BinarioEnigma.deserializar_e64(contenido_disco)
        assert "PRINCIPAL" in deserializado.tabla_simbolos
        assert "MERGE_SORT" in deserializado.tabla_simbolos
        assert deserializado.tabla_simbolos["lista_entrada"] == BASE_VECTORES
        assert deserializado.tabla_simbolos["lista_entrada_desc"] == BASE_CABECERAS

        # Cargar el .e64 usando UNICAMENTE CargadorEnigma.cargar_archivo de la Tarea 10
        ram = RAMMemory()
        banco = BancoRegistros()
        perifericos = Perifericos()
        cpu = CPU(ram=ram, banco=banco, perifericos=perifericos)
        cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)

        cargador.cargar_archivo(str(ruta_e64))
        cpu.ejecutar(max_ciclos=3_000_000)

        ordenado = leer_vector_de_ram(ram, BASE_VECTORES, modo="int")
        assert ordenado == [-30, -7, 0, 15, 42, 80]
        assert perifericos.pantalla.obtener_texto().strip() == "-30 -7 0 15 42 80"
        assert binario.tamano_codigo > 0

    def test_integracion_merge_sort_y_prueba_vec_con_puente_cargador(self):
        # 1) Ejecutar prueba_vec.asm del Integrante 2 a traves de nuestro puente
        res_vec = cargar_y_ejecutar_estructuras(PRUEBA_VEC_ASM, es_archivo=True)
        assert res_vec.banco.sp == PILA_ESTRUCTURAS
        assert res_vec.leer_vector(BASE_BUFFERS, longitud=4, modo="uint") == [
            0x00220018,
            30,
            0xC004000000000000,
            6,
        ]

        # 2) Ejecutar merge_sort.asm del Integrante 6 con vector precargado por DescriptorVector
        datos = [99, -15, 7, 7, -100, 42, 0]
        vec = DescriptorVector("entrada", datos, direccion_base=BASE_VECTORES, slot_cabecera=0)
        res_ms = cargar_y_ejecutar_estructuras(
            MERGE_SORT_ASM,
            es_archivo=True,
            estructuras=[vec],
        )
        assert res_ms.leer_vector(BASE_VECTORES, modo="int") == sorted(datos)
        assert res_ms.salida_mmio.strip() == "-100 -15 0 7 7 42 99"
        assert res_ms.banco.sp == PILA_ESTRUCTURAS

    def test_cli_exportar_y_ejecutar(self, tmp_path, capsys):
        salida_e64 = tmp_path / "cabeceras.e64"
        rc = cli_main([str(PRUEBA_CABECERAS_ASM), "-o", str(salida_e64), "--ejecutar"])
        assert rc == 0
        assert salida_e64.is_file()
        out = capsys.readouterr().out
        assert "[OK] Ejecutable .e64 generado" in out
        assert "[OK] Cargado en 0x00200000" in out
