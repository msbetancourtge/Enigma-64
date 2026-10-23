"""
Punto de entrada CLI para el Preprocesador del SPL de Enigma-64.
Uso: python -m spl.preprocesador ENTRADA [-o SALIDA] [-I DIR] [-D NOMBRE=VALOR]
"""

import sys
import argparse
from spl.preprocesador.motor import preprocesar_archivo, PreprocesadorError


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m spl.preprocesador",
        description="Preprocesador del SPL de Enigma-64 (Noctua Systems)",
    )
    parser.add_argument("entrada", help="Archivo de entrada a preprocesar")
    parser.add_argument(
        "-o", "--salida",
        help="Archivo donde se guardara el resultado (opcional, por defecto stdout)",
    )
    parser.add_argument(
        "-I", "--include",
        action="append",
        default=[],
        dest="dirs_inclusion",
        help="Directorio adicional de inclusion (puede especificarse multiples veces)",
    )
    parser.add_argument(
        "-D", "--define",
        action="append",
        default=[],
        dest="definiciones_raw",
        help="Definir macro inicial (NOMBRE=VALOR o solo NOMBRE)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    definiciones: dict[str, str] = {}
    for item in args.definiciones_raw:
        if "=" in item:
            nombre, valor = item.split("=", 1)
            definiciones[nombre.strip()] = valor.strip()
        else:
            definiciones[item.strip()] = "1"

    try:
        resultado = preprocesar_archivo(
            args.entrada,
            dirs_inclusion=args.dirs_inclusion,
            definiciones=definiciones,
        )

        salida_texto = resultado.texto
        if salida_texto and not salida_texto.endswith("\n"):
            salida_texto += "\n"

        if args.salida:
            with open(args.salida, "w", encoding="utf-8") as f:
                f.write(salida_texto)
        else:
            sys.stdout.write(salida_texto)

        return 0

    except PreprocesadorError as err:
        sys.stderr.write(f"{err}\n")
        return 1
    except Exception as exc:
        sys.stderr.write(f"error inesperado: {exc}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
