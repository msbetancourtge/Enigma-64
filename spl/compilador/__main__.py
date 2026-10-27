"""
Punto de entrada CLI del analizador léxico del Compilador SPL de Enigma-64.
Uso: python -m spl.compilador [ARCHIVO.spl]   (sin archivo lee de stdin)
"""

import sys
import argparse
from collections import Counter

from spl.compilador.lexer import CompiladorLexer


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m spl.compilador",
        description="Analizador léxico del Compilador SPL de Enigma-64 (Noctua Systems)",
    )
    parser.add_argument(
        "entrada",
        nargs="?",
        help="Archivo .spl/.prog a tokenizar (opcional, por defecto stdin)",
    )
    parser.add_argument(
        "--sin-tablas",
        action="store_true",
        help="Oculta el volcado estructurado de las tablas de símbolos",
    )
    return parser.parse_args(argv)


def imprimir_resumen(conteo, total_lineas, comentarios, errores, salida):
    salida.write("\n" + "=" * 18 + " RESUMEN DEL ANALISIS LEXICO DEL COMPILADOR " + "=" * 18 + "\n")
    for categoria in sorted(conteo.keys()):
        salida.write(f"  {categoria:<28}{conteo[categoria]:>6}\n")
    salida.write("  " + "-" * 34 + "\n")
    salida.write(f"  {'Total de tokens':<28}{sum(conteo.values()):>6}\n")
    salida.write(f"  {'Comentarios ignorados':<28}{comentarios:>6}\n")
    salida.write(f"  {'Lineas analizadas':<28}{total_lineas:>6}\n")
    salida.write(f"  {'Errores lexicos':<28}{errores:>6}\n")
    salida.write("=" * 76 + "\n")


def main(argv=None):
    args = parse_args(argv)

    try:
        if args.entrada:
            with open(args.entrada, encoding="utf-8", errors="replace") as f:
                texto = f.read()
        else:
            texto = sys.stdin.read()
    except OSError as exc:
        sys.stderr.write(f"Error al leer '{args.entrada}': {exc.strerror}\n")
        return 2

    salida = sys.stdout
    lexer = CompiladorLexer(al_error=lambda err: salida.write(f"{err}\n"))
    lexer.input(texto)

    conteo = Counter()
    salida.write("\n" + "=" * 25 + " SECUENCIA DE TOKENS SPL " + "=" * 25 + "\n")
    salida.write(f"{'Línea':<8}{'Col':<6}{'Categoría Token':<20}{'Código':<8}{'Atributo / Lexema':<28}\n")
    salida.write("-" * 76 + "\n")

    for tok in lexer:
        conteo[tok.type] += 1
        idx_info = f"[sym={tok.simbolo_idx}] " if getattr(tok, "simbolo_idx", None) else ""
        lexema_repr = repr(tok.value) if "\n" in str(tok.value) else str(tok.value)
        salida.write(
            f"{tok.lineno:<8}{tok.columna:<6}{tok.type:<20}{tok.categoria_codigo:<8}{idx_info + lexema_repr:<28}\n"
        )

    # Volcado estructurado de las tablas de símbolos y literales
    if not args.sin_tablas and lexer.tablas is not None:
        salida.write("\n" + lexer.tablas.generar_volcado_texto() + "\n")

    total_lineas = texto.count("\n") + (0 if texto.endswith("\n") or not texto else 1)
    imprimir_resumen(conteo, total_lineas, lexer.comentarios, len(lexer.errores), salida)

    return 1 if lexer.errores else 0


if __name__ == "__main__":
    sys.exit(main())
