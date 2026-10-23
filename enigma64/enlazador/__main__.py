"""
Linea de comandos del Enlazador de Enigma-64.

    python -m enigma64.enlazador modulo.obj [otro.obj ...]
        Analiza cada modulo: cabecera, encabezados de seccion, tablas de
        exportacion e importacion, simbolos locales y marcas de reubicacion.

    python -m enigma64.enlazador a.obj b.obj -o programa.e64 [--base 0x00200000]
                                 [--entrada main] [--mapa] [--sin-informe]
        Ademas los enlaza y escribe un ejecutable .e64 absoluto, que el Cargador
        (o la pestana Cargador de la interfaz) deposita en RAM.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from ..cargador import USER_MEM_START, ErrorCargador
from .enlace import EnlazadorEnigma
from .objeto import analizar_objeto


def _direccion(texto: str) -> int:
    try:
        return int(texto, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(f"direccion invalida: {texto!r}") from None


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m enigma64.enlazador",
        description=(
            "Analiza modulos objeto reubicables (.obj) de Enigma-64 y, con -o o "
            "--mapa, los enlaza en un ejecutable absoluto."
        ),
    )
    parser.add_argument("objetos", nargs="+", help="modulos objeto .obj")
    parser.add_argument("-o", "--salida", help="escribe el ejecutable .e64 enlazado")
    parser.add_argument(
        "--base", type=_direccion, default=USER_MEM_START,
        help="direccion de carga del enlace (por defecto 0x%(default)08X)",
    )
    parser.add_argument("--entrada", help="simbolo exportado que sera el punto de entrada")
    parser.add_argument("--mapa", action="store_true", help="imprime el mapa de enlace")
    parser.add_argument(
        "--sin-informe", action="store_true", help="no imprime el analisis de cada modulo"
    )
    args = parser.parse_args(argv)

    try:
        modulos = [analizar_objeto(ruta) for ruta in args.objetos]
        if not args.sin_informe:
            print("\n\n".join(modulo.informe() for modulo in modulos))

        if args.salida or args.mapa:
            resultado = EnlazadorEnigma(modulos).enlazar(args.base, args.entrada)
            if args.mapa:
                print("\n" + resultado.informe())
            if args.salida:
                with open(args.salida, "wb") as f:
                    f.write(resultado.binario.serializar_e64())
                print(
                    f"\nEjecutable escrito en {args.salida}: {resultado.tamano_total} bytes "
                    f"en 0x{resultado.direccion_base:08X}, entrada 0x{resultado.entry_point:08X}"
                )
    except (OSError, ErrorCargador) as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
