"""
Verifica por analisis del codigo que los modulos de la interfaz no se mezclan.

Es el requisito explicito del profesor: los componentes deben poder funcionar
por separado. En vez de confiar en la buena voluntad, estas pruebas leen el
arbol sintactico de cada panel y fallan si alguien introduce un acoplamiento.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import ast
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DIR_PANELES = RAIZ / "enigma64" / "ui" / "paneles"

#: Modulos de panel; `base` e `__init__` son infraestructura, no paneles.
ARCHIVOS_PANEL = sorted(
    ruta for ruta in DIR_PANELES.glob("panel_*.py")
)

#: Modulos de hardware del equipo que un panel no debe importar directamente.
MODULOS_HARDWARE = {"memoria", "registros", "alu", "cargador", "fpu"}


def _importaciones(ruta: pathlib.Path):
    """Devuelve los nombres de modulo que importa un archivo."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"), filename=str(ruta))
    nombres = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            nombres.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            # nivel > 0 son relativos: se reconstruyen con puntos.
            nombres.append("." * nodo.level + (nodo.module or ""))
    return nombres


def test_hay_paneles_que_revisar():
    assert ARCHIVOS_PANEL, "no se encontro ningun panel que revisar"


@pytest.mark.parametrize("ruta", ARCHIVOS_PANEL, ids=lambda r: r.stem)
def test_un_panel_no_importa_a_otro_panel(ruta):
    """Ningun panel puede depender de otro panel."""
    otros = {p.stem for p in ARCHIVOS_PANEL} - {ruta.stem}
    for importado in _importaciones(ruta):
        hoja = importado.lstrip(".").split(".")[-1]
        assert hoja not in otros, (
            f"{ruta.name} importa {importado!r}: los paneles deben comunicarse "
            f"por el bus de eventos, no importandose entre si."
        )


@pytest.mark.parametrize("ruta", ARCHIVOS_PANEL, ids=lambda r: r.stem)
def test_un_panel_no_importa_hardware_directamente(ruta):
    """
    Un panel habla con el hardware a traves de su servicio. Importar
    `enigma64.memoria` desde un panel salta la capa de adaptadores y rompe el
    aislamiento frente a cambios en el modulo del companero.
    """
    for importado in _importaciones(ruta):
        if importado.startswith("enigma64.") or importado.startswith("..."):
            hoja = importado.lstrip(".").replace("enigma64.", "").split(".")[0]
            assert hoja not in MODULOS_HARDWARE, (
                f"{ruta.name} importa {importado!r} directamente; debe usar el "
                f"servicio que recibe en el constructor."
            )


@pytest.mark.parametrize("ruta", ARCHIVOS_PANEL, ids=lambda r: r.stem)
def test_cada_panel_se_puede_arrancar_solo(ruta):
    """Cada panel expone su propio punto de entrada `__main__`."""
    fuente = ruta.read_text(encoding="utf-8")
    assert '__name__ == "__main__"' in fuente, (
        f"{ruta.name} no se puede ejecutar por separado"
    )
    assert "ejecutar_suelto()" in fuente, (
        f"{ruta.name} no llama a PanelBase.ejecutar_suelto()"
    )


def test_los_modulos_del_equipo_no_fueron_modificados():
    """
    La interfaz no debe tocar los modulos de los companeros: no puede haber
    ninguna importacion de `enigma64.ui` dentro de ellos.
    """
    for nombre in MODULOS_HARDWARE:
        ruta = RAIZ / "enigma64" / f"{nombre}.py"
        if not ruta.exists():
            continue
        assert "enigma64.ui" not in ruta.read_text(encoding="utf-8"), (
            f"enigma64/{nombre}.py hace referencia a la interfaz; los modulos "
            f"de hardware deben seguir siendo independientes de ella."
        )
