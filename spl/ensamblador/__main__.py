"""
Punto de entrada CLI del analizador lexico del Ensamblador SPL de Enigma-64.
Uso: python -m spl.ensamblador [ARCHIVO.asm]   (sin archivo lee de stdin)
"""

import sys
import argparse
from collections import Counter

from spl.ensamblador.lexer import EnsambladorLexer


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m spl.ensamblador",
        description="Analizador lexico del ensamblador de Enigma-64 (Noctua Systems)",
    )
    parser.add_argument(
        "entrada",
        nargs="?",
        help="Archivo .asm a tokenizar (opcional, por defecto stdin)",
    )
    return parser.parse_args(argv)


def imprimir_resumen(conteo, total_lineas, comentarios, errores, salida):
    salida.write("\n" + "=" * 15 + " RESUMEN DEL ANALISIS LEXICO " + "=" * 15 + "\n")
    for categoria in EnsambladorLexer.tokens:
        salida.write(f"  {categoria:<24}{conteo[categoria]:>6}\n")
    salida.write("  " + "-" * 30 + "\n")
    salida.write(f"  {'Total de tokens':<24}{sum(conteo.values()):>6}\n")
    salida.write(f"  {'Comentarios ignorados':<24}{comentarios:>6}\n")
    salida.write(f"  {'Lineas analizadas':<24}{total_lineas:>6}\n")
    salida.write(f"  {'Errores lexicos':<24}{errores:>6}\n")


def main(argv=None):
    args = parse_args(argv)

    try:
        if args.entrada:
            with open(args.entrada, encoding="utf-8", errors="replace") as f:
                texto = f.read()
        else:
            texto = sys.stdin.read()
    except OSError as exc:
        sys.stderr.write(f"no se pudo leer '{args.entrada}': {exc.strerror}\n")
        return 2

    salida = sys.stdout
    # Los errores se imprimen en el mismo flujo para que queden en orden con los tokens
    lexer = EnsambladorLexer(al_error=lambda err: salida.write(f"{err}\n"))
    lexer.input(texto)

    conteo = Counter()
    for tok in lexer:
        conteo[tok.type] += 1
        salida.write(f"<{tok.lineno}, {tok.type}, {tok.value}>\n")

    total_lineas = texto.count("\n") + (0 if texto.endswith("\n") or not texto else 1)
    imprimir_resumen(conteo, total_lineas, lexer.comentarios, len(lexer.errores), salida)

    return 1 if lexer.errores else 0


if __name__ == "__main__":
    sys.exit(main())
