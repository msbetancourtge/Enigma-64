"""
Punto de entrada CLI del Orquestador Principal del SPL (Sistema de Procesamiento del Lenguaje)
para el computador Enigma-64 (Noctua Systems).

Responsabilidad: Integrante 7 (Driver Principal, Pipeline & Pruebas)

Ejemplos de uso:
  python -m spl                             # Ejecuta los 3 escenarios integrales del Taller #01
  python -m spl --escenario 1               # Ejecuta únicamente el Escenario Integral 1
  python -m spl --spl programa.spl          # Preprocesa y tokeniza un archivo .spl
  python -m spl --asm modulo.asm            # Tokeniza un archivo .asm de Enigma-64
  python -m spl --obj a.obj b.obj           # Analiza, enlaza y ejecuta módulos .obj en Enigma-64
  python -m spl --verificar-c               # Verifica/compila el módulo C de Tablas de Símbolos
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from spl.pipeline import OrquestadorSPL, verificar_modulo_c_tablas


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m spl",
        description=(
            "Orquestador Principal del Sistema de Procesamiento del Lenguaje (SPL) "
            "para Enigma-64: Preprocesador -> Compilador -> Ensamblador -> Enlazador-Cargador."
        ),
    )
    parser.add_argument(
        "--escenario",
        choices=["1", "2", "3", "todos"],
        default=None,
        help="Ejecuta el escenario de prueba integral indicado (1, 2, 3 o todos).",
    )
    parser.add_argument(
        "--spl",
        dest="ruta_spl",
        help="Ruta a un archivo fuente de alto nivel (.spl) para preprocesar y tokenizar.",
    )
    parser.add_argument(
        "--asm",
        dest="ruta_asm",
        help="Ruta a un archivo en lenguaje ensamblador (.asm / .s) para tokenizar.",
    )
    parser.add_argument(
        "--obj",
        nargs="+",
        dest="rutas_obj",
        help="Uno o más módulos objeto reubicables (.obj) para enlazar y cargar en Enigma-64.",
    )
    parser.add_argument(
        "-I", "--include",
        action="append",
        default=[],
        dest="dirs_inclusion",
        help="Directorio adicional de búsqueda para #include.",
    )
    parser.add_argument(
        "-D", "--define",
        action="append",
        default=[],
        dest="definiciones_raw",
        help="Definición de macro inicial NOMBRE=VALOR o NOMBRE.",
    )
    parser.add_argument(
        "--sin-tablas",
        action="store_true",
        help="Oculta el volcado detallado de las tablas de símbolos en la salida.",
    )
    parser.add_argument(
        "--verificar-c",
        action="store_true",
        help="Verifica (y compila si GCC está en PATH) el módulo C de tablas de símbolos.",
    )
    return parser.parse_args(argv)


def _parsear_definiciones(definiciones_raw: List[str]) -> dict[str, str]:
    defs: dict[str, str] = {}
    for item in definiciones_raw:
        if "=" in item:
            nombre, valor = item.split("=", 1)
            defs[nombre.strip()] = valor.strip()
        else:
            defs[item.strip()] = "1"
    return defs


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = parse_args(argv)
    orquestador = OrquestadorSPL(dirs_inclusion=args.dirs_inclusion)
    incluir_tablas = not args.sin_tablas

    if args.verificar_c:
        ok_c, msg_c = verificar_modulo_c_tablas()
        sys.stdout.write(f"[VERIFICACIÓN C/MAKEFILE] {msg_c}\n")
        if not ok_c:
            return 1

    # Si el usuario especificó archivos puntuales (--spl, --asm, --obj)
    if args.ruta_spl or args.ruta_asm or args.rutas_obj:
        definiciones = _parsear_definiciones(args.definiciones_raw)
        ejecutar_link = bool(args.rutas_obj)
        resultado = orquestador.ejecutar_pipeline_completo(
            nombre_escenario="Ejecución Personalizada por CLI",
            ruta_spl=args.ruta_spl,
            ruta_asm=args.ruta_asm,
            modulos_obj=args.rutas_obj,
            definiciones_macro=definiciones,
            ejecutar_enlazador=ejecutar_link,
            ejecutar_cpu=ejecutar_link,
        )
        sys.stdout.write(resultado.generar_informe(incluir_tablas=incluir_tablas) + "\n")
        return 0 if resultado.exito else 1

    # Modo por escenarios (por defecto ejecuta todos los 3 escenarios oficiales)
    seleccion = args.escenario or "todos"
    if seleccion == "todos":
        resultados = orquestador.ejecutar_todos_los_escenarios()
    else:
        resultados = [orquestador.ejecutar_escenario(int(seleccion))]

    for idx, res in enumerate(resultados):
        if idx > 0:
            sys.stdout.write("\n\n")
        sys.stdout.write(res.generar_informe(incluir_tablas=incluir_tablas) + "\n")

    ok_c, msg_c = verificar_modulo_c_tablas()
    sys.stdout.write(f"\n[ESTADO COMPILACIÓN CRUZADA C / MAKEFILE]: {msg_c}\n")

    todos_exitosos = all(r.exito for r in resultados) and ok_c
    return 0 if todos_exitosos else 1


if __name__ == "__main__":
    sys.exit(main())
