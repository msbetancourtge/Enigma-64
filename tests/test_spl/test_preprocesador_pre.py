"""
Pruebas para las mejoras de retroalimentación del Preprocesador SPL:
- Emisión explícita de archivos precompilados (.pre)
- Soporte y resolución de cabeceras estándar pre-procesadas (.pre)
- Mapeo de correspondencia de líneas origen vs precompilado
- CLI --emitir-pre
"""

import os
import subprocess
import sys
from pathlib import Path

from spl.preprocesador import (
    ResultadoPreprocesamiento,
    exportar_archivo_pre,
    preprocesar_texto,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_resultado_propiedades_alias():
    res = ResultadoPreprocesamiento(
        texto="int x = 42;",
        macros={"MI_MACRO": "100"},
        mapa_lineas=[("prueba.spl", 1)],
    )
    assert res.texto_expandido == "int x = 42;"
    assert res.macros_activas == {"MI_MACRO": "100"}
    assert res.mapa_lineas == [("prueba.spl", 1)]


def test_exportar_archivo_pre(tmp_path):
    fuente_spl = tmp_path / "modulo_prueba.spl"
    fuente_spl.write_text(
        '#include "enigma64.h"\n'
        'ENTERO principal() {\n'
        '    ENTERO val = 42;\n'
        '    return val;\n'
        '}\n',
        encoding="utf-8",
    )

    ruta_pre, res = exportar_archivo_pre(fuente_spl)
    assert os.path.isfile(ruta_pre)
    assert ruta_pre.endswith("modulo_prueba.pre")

    contenido_pre = Path(ruta_pre).read_text(encoding="utf-8")
    assert "int principal() {" in contenido_pre
    assert "int val = 42;" in contenido_pre
    assert len(res.mapa_lineas) > 0


def test_exportar_archivo_pre_ruta_destino_personalizada(tmp_path):
    fuente_spl = tmp_path / "origen.spl"
    fuente_spl.write_text("int a = 10;\n", encoding="utf-8")
    destino_pre = tmp_path / "salidas" / "compilado.pre"

    ruta_pre, res = exportar_archivo_pre(fuente_spl, ruta_salida_pre=destino_pre)
    assert Path(ruta_pre) == destino_pre.resolve()
    assert destino_pre.exists()
    assert destino_pre.read_text(encoding="utf-8").strip() == "int a = 10;"


def test_cabecera_estandar_pre_procesada_existe():
    ruta_enigma_pre = REPO_ROOT / "spl" / "include" / "enigma64.pre"
    assert ruta_enigma_pre.exists(), "Debe existir spl/include/enigma64.pre"
    texto = ruta_enigma_pre.read_text(encoding="utf-8")
    assert "#define ENTERO int" in texto
    assert "#define TAM_PALABRA 64" in texto


def test_resolucion_cabecera_pre_automatica():
    codigo = (
        '#include "enigma64.h"\n'
        'ENTERO x = 100;\n'
    )
    res = preprocesar_texto(codigo, usar_cabeceras_pre=True)
    assert "int x = 100;" in res.texto
    assert "ENTERO" in res.macros_activas


def test_cli_preprocesador_emitir_pre(tmp_path):
    fuente = tmp_path / "cli_test.spl"
    fuente.write_text(
        '#define BASE 10\n'
        'int y = BASE * 2;\n',
        encoding="utf-8",
    )

    salida_pre = tmp_path / "cli_test.pre"
    cmd = [
        sys.executable,
        "-m",
        "spl.preprocesador",
        str(fuente),
        "--emitir-pre",
        "-o",
        str(salida_pre),
    ]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0
    assert salida_pre.exists()
    assert "int y = 10 * 2;" in salida_pre.read_text(encoding="utf-8")
