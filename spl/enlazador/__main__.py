"""
Linea de comandos del Enlazador de Enigma-64.

    python -m spl.enlazador modulo.obj [otro.tobj ...] [--tokens]
        Analiza cada modulo (.obj binario o .tobj en texto): cabecera,
        encabezados de seccion, tablas de exportacion e importacion, simbolos
        locales y marcas de reubicacion. Con --tokens imprime ademas la
        secuencia de tokens que el lexer de lex.py reconoce en cada .tobj.

    python -m spl.enlazador a.obj b.obj -o programa.e64 [--base 0x00200000]
                                 [--entrada main] [--mapa] [--sin-informe]
        Ademas los enlaza y escribe un ejecutable .e64 absoluto, que el Cargador
        (o la pestana Cargador de la interfaz) deposita en RAM.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import List, Optional

from enigma64.cargador import EXTENSION_OBJETO_TEXTO, USER_MEM_START, ErrorCargador
from .enlace import EnlazadorEnigma
from .lexer import ObjetoLexer
from .objeto import analizar_objeto


def _direccion(texto: str) -> int:
    try:
        return int(texto, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(f"direccion invalida: {texto!r}") from None


def _imprimir_tokens(ruta: str) -> None:
    """Secuencia <linea, categoria, lexema> de un .tobj y resumen por categoria."""
    with open(ruta, encoding="utf-8", errors="replace") as f:
        texto = f.read()
    lexer = ObjetoLexer(al_error=print)
    lexer.input(texto)
    print(f"Tokens de '{ruta}'")
    conteo: Counter = Counter()
    for tok in lexer:
        conteo[tok.type] += 1
        lexema = tok.value.replace("\n", "\\n")
        print(f"<{tok.lineno}, {tok.type}, {lexema}>")
    print(f"\nResumen del analisis lexico de '{ruta}'")
    for categoria in ObjetoLexer.tokens:
        print(f"  {categoria:<24}{conteo[categoria]:>6}")
    print("  " + "-" * 30)
    print(f"  {'Total de tokens':<24}{sum(conteo.values()):>6}")
    print(f"  {'Comentarios ignorados':<24}{lexer.comentarios:>6}")
    print(f"  {'Errores lexicos':<24}{len(lexer.errores):>6}\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m spl.enlazador",
        description=(
            "Analiza modulos objeto reubicables de Enigma-64 (.obj binario o .tobj "
            "en texto) y, con -o o --mapa, los enlaza en un ejecutable absoluto."
        ),
    )
    parser.add_argument("objetos", nargs="+", help="modulos objeto .obj o .tobj")
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
    parser.add_argument(
        "--tokens", action="store_true",
        help="imprime los tokens que reconoce el lexer en cada modulo .tobj",
    )
    args = parser.parse_args(argv)

    try:
        if args.tokens:
            for ruta in args.objetos:
                if ruta.lower().endswith(EXTENSION_OBJETO_TEXTO):
                    _imprimir_tokens(ruta)
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
