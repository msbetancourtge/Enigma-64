"""
Suite de Pruebas de Integración del Pipeline SPL y Driver Principal — Enigma-64.

Responsabilidad: Integrante 7 (Driver Principal, Pipeline & Pruebas)
Valida:
  1. Integración extremo a extremo de las 4 herramientas del SPL:
     Preprocesador -> Compilador (Lexer + Tablas) -> Ensamblador (Lexer) -> Enlazador-Cargador + CPU.
  2. Ejecución de los 3 escenarios integrales obligatorios del Taller #01.
  3. Interfaz de línea de comandos del orquestador (python -m spl).
  4. Verificación de compilación cruzada / integridad del módulo C y Makefiles.
"""

from __future__ import annotations

import io
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from enigma64.enlazador.ejemplos import exportar_ejemplos
from spl import (
    EtapaCompiladorResult,
    EtapaEnlazadorCargadorResult,
    EtapaEnsambladorResult,
    EtapaPreprocesadorResult,
    OrquestadorSPL,
    ResultadoPipelineSPL,
    verificar_modulo_c_tablas,
)
from spl.__main__ import main as cli_spl
from spl.pipeline import (
    DIR_COMPILADOR_C,
    DIR_EJEMPLOS_PIPELINE,
    DIR_INCLUDE_DEFAULT,
    DIR_SPL,
)


class TestEtapasIndividualesOrquestador:
    """Verifica cada etapa invocada desde OrquestadorSPL."""

    def setup_method(self) -> None:
        self.orquestador = OrquestadorSPL()

    def test_etapa_1_preprocesador_expande_include_y_define(self) -> None:
        codigo = (
            '#include "enigma64.h"\n'
            "#define FACTOR 8\n"
            "// Comentario de linea que debe eliminarse\n"
            "ENTERO x = TAM_PALABRA + FACTOR;\n"
        )
        res = self.orquestador.ejecutar_etapa_preprocesador(codigo, es_archivo=False)
        assert isinstance(res, EtapaPreprocesadorResult)
        assert "enigma64.h" in res.archivos_incluidos
        assert res.macros_definidas["TAM_PALABRA"] == "64"
        assert res.macros_definidas["FACTOR"] == "8"
        assert "int x = 64 + 8;" in res.codigo_expandido
        assert "Comentario de linea" not in res.codigo_expandido

    def test_etapa_2_compilador_tokeniza_y_puebla_tres_tablas(self) -> None:
        codigo = (
            'struct Punto { float _x; float _y; };\n'
            'function void init() {\n'
            '    struct Punto p;\n'
            '    p._x = 1.5E3;\n'
            '    p._y = 1.5E3;\n'
            '    log("Ruta: \\"C:\\\\bin\\"");\n'
            '    log("Ruta: \\"C:\\\\bin\\"");\n'
            '}\n'
        )
        res = self.orquestador.ejecutar_etapa_compilador(codigo)
        assert isinstance(res, EtapaCompiladorResult)
        assert len(res.errores) == 0
        # Deduplicación estricta: 1.5E3 aparece 2 veces pero registra 1 sola entrada en tablaNum
        assert res.tablas.tabla_num.total == 1
        entrada_num = res.tablas.tabla_num.obtener(1)
        assert entrada_num is not None
        assert entrada_num.valor_float == pytest.approx(1500.0)
        assert len(entrada_num.patron_ieee754_hex) == 16

        # Deduplicación estricta y des-escape en tablaString
        assert res.tablas.tabla_string.total == 1
        entrada_str = res.tablas.tabla_string.obtener(1)
        assert entrada_str is not None
        assert entrada_str.texto == 'Ruta: "C:\\bin"'

    def test_etapa_3_ensamblador_reconoce_mnemonicos_registros_y_directivas(self) -> None:
        asm = (
            "        .data\n"
            "        .org 0x00201000\n"
            "dato:   .word 42\n"
            "        .text\n"
            "        .org 0x00200000\n"
            "main:   ADDI R1, R0, 42\n"
            "        HLT\n"
        )
        res = self.orquestador.ejecutar_etapa_ensamblador(asm)
        assert isinstance(res, EtapaEnsambladorResult)
        assert len(res.errores) == 0
        assert res.conteo_por_tipo["DIRECTIVA"] == 5
        assert res.conteo_por_tipo["MNEMONICO"] == 2
        assert res.conteo_por_tipo["REGISTRO"] == 2
        assert res.conteo_por_tipo["ETIQUETA_DEF"] == 2

    def test_etapa_4_enlazador_cargador_y_cpu_ejecuta_programa_reubicado(self) -> None:
        res = self.orquestador.ejecutar_etapa_enlazador_cargador(ejecutar_cpu=True)
        assert isinstance(res, EtapaEnlazadorCargadorResult)
        assert len(res.modulos_analizados) == 2
        assert res.direccion_carga == 0x00200000
        assert res.ejecutado_en_cpu is True
        assert res.ciclos_cpu == 15
        assert res.r5_retorno == 42
        assert res.valor_resultado_ram == 42
        assert res.valor_copia_ram == 42


class TestBateriaTresEscenariosIntegrales:
    """Valida los 3 escenarios integrales obligatorios del Taller #01."""

    def setup_method(self) -> None:
        self.orquestador = OrquestadorSPL()

    def test_escenario_1_flujo_nominal_tda_matrices_y_enlace(self) -> None:
        res = self.orquestador.ejecutar_escenario(1)
        assert isinstance(res, ResultadoPipelineSPL)
        assert res.exito is True
        assert res.total_errores_lexicos == 0
        assert res.preprocesador is not None
        assert "enigma64.h" in res.preprocesador.archivos_incluidos
        assert "META_SUMA" in res.preprocesador.macros_definidas
        assert res.compilador is not None
        assert res.compilador.tablas.tabla_id.buscar("BloqueAritmetico") is not None
        assert res.compilador.tablas.tabla_id.buscar("_acumulador") is not None
        assert res.ensamblador is not None
        assert len(res.ensamblador.errores) == 0
        assert res.enlazador_cargador is not None
        assert res.enlazador_cargador.r5_retorno == 42
        assert res.enlazador_cargador.valor_resultado_ram == 42

    def test_escenario_2_punto_flotante_ieee754_switch_case_y_cadenas(self) -> None:
        res = self.orquestador.ejecutar_escenario(2)
        assert res.exito is True
        assert res.total_errores_lexicos == 0
        assert res.preprocesador is not None
        assert res.preprocesador.macros_definidas.get("MODO_EJECUCION") == "1"
        assert res.compilador is not None

        # Verificar constantes IEEE 754 (1.0e-9, 1.5E3) y bases (0xFF, 0b1010)
        t_num = res.compilador.tablas.tabla_num
        idx_tol = t_num.buscar("1.0e-9")
        idx_cota = t_num.buscar("1.5E3")
        idx_hex = t_num.buscar("0xFF")
        idx_bin = t_num.buscar("0b1010")
        assert idx_tol is not None and t_num.obtener(idx_tol).valor_float == pytest.approx(1e-9)
        assert idx_cota is not None and t_num.obtener(idx_cota).valor_float == pytest.approx(1500.0)
        assert idx_hex is not None and t_num.obtener(idx_hex).valor_int == 255
        assert idx_bin is not None and t_num.obtener(idx_bin).valor_int == 10

        # Verificar des-escape y deduplicación en tablaString (3 literales en fuente -> 2 únicos)
        t_str = res.compilador.tablas.tabla_string
        assert t_str.total == 2
        assert t_str.buscar(r"C:\Enigma64\fpu_trace.log") == 1
        assert t_str.buscar('Estado FPU: "CONVERGENCIA_OK"') == 2

    def test_escenario_3_tolerancia_y_recuperacion_errores_multietapa(self) -> None:
        res = self.orquestador.ejecutar_escenario(3)
        assert res.errores_esperados is True
        assert res.exito is True
        assert res.compilador is not None
        assert len(res.compilador.errores) == 5
        # A pesar de los 5 errores, el compilador se recuperó y registró 'verificar_recuperacion'
        assert res.compilador.tablas.tabla_id.buscar("verificar_recuperacion") is not None

        assert res.ensamblador is not None
        assert len(res.ensamblador.errores) == 4
        # A pesar de los 4 errores ASM, reconoció la instrucción final HLT
        assert any(t.type == "MNEMONICO" and t.value.upper() == "HLT" for t in res.ensamblador.tokens)

    def test_ejecutar_todos_los_escenarios_y_generar_informes(self) -> None:
        resultados = self.orquestador.ejecutar_todos_los_escenarios()
        assert len(resultados) == 3
        for r in resultados:
            assert r.exito is True
            informe = r.generar_informe(incluir_tablas=True)
            assert "[ETAPA 1/4] PREPROCESADOR SPL" in informe
            assert "[ETAPA 2/4] ANALIZADOR LÉXICO DEL COMPILADOR" in informe
            assert "[ETAPA 3/4] ANALIZADOR LÉXICO DEL ENSAMBLADOR" in informe
            assert "[ETAPA 4/4] ENLAZADOR-CARGADOR" in informe


class TestCLIOrquestadorYCompilacionCruzada:
    """Verifica la interfaz de línea de comandos (python -m spl) y los Makefiles."""

    def test_cli_ejecuta_escenario_individual(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_spl(["--escenario", "1", "--sin-tablas"])
        salida = buf.getvalue()
        assert code == 0
        assert "ESCENARIO 1" in salida
        assert "Registro retorno R5 (RV) : 42" in salida

    def test_cli_con_archivos_spl_asm_y_obj_exportados(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rutas_obj = exportar_ejemplos(tmp)
            ruta_spl = str(DIR_EJEMPLOS_PIPELINE / "escenario1_aritmetica_tda.spl")
            ruta_asm = str(DIR_EJEMPLOS_PIPELINE / "escenario1_modulo.asm")
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = cli_spl([
                    "--spl", ruta_spl,
                    "--asm", ruta_asm,
                    "--obj", *rutas_obj,
                    "-D", "EXTRA_FLAG=1",
                    "--sin-tablas",
                ])
            salida = buf.getvalue()
            assert code == 0
            assert "EXTRA_FLAG" in salida
            assert "Módulos .obj enlazados   : 2 (principal, libmat)" in salida

    def test_verificacion_modulo_c_y_makefiles_existen(self) -> None:
        ok, mensaje = verificar_modulo_c_tablas()
        assert ok is True
        assert "tablas_simbolos" in mensaje or "GCC" in mensaje
        assert (DIR_COMPILADOR_C / "Makefile").is_file()
        assert (DIR_INCLUDE_DEFAULT / "enigma64.h").is_file()
        assert (DIR_SPL.parent / "Makefile").is_file()
