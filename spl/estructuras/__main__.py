"""
Interfaz de linea de comandos del subpaquete spl.estructuras.

    python -m spl.estructuras programa.asm [-o salida.e64] [--ejecutar]
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, Optional, Sequence

from .cargador import cargar_y_ejecutar_estructuras, exportar_estructuras_e64


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m spl.estructuras",
        description=(
            "Preprocesa, ensambla, empaqueta (.e64) y ejecuta programas de Enigma-64 "
            "que incluyen la libreria estructuras.inc (Tarea 29 - Integrante 4)."
        ),
    )
    parser.add_argument("entrada", help="Ruta al archivo .asm que usa #include 'estructuras.inc'.")
    parser.add_argument(
        "-o",
        "--salida-e64",
        dest="salida_e64",
        default=None,
        help="Exporta el ejecutable estructurado .e64 en la ruta indicada.",
    )
    parser.add_argument(
        "-I",
        "--include",
        action="append",
        default=[],
        dest="dirs_inclusion",
        help="Directorio adicional de busqueda para #include.",
    )
    parser.add_argument(
        "-D",
        "--define",
        action="append",
        default=[],
        dest="definiciones",
        help="Define una macro NOMBRE=VALOR o NOMBRE.",
    )
    parser.add_argument(
        "--ejecutar",
        action="store_true",
        help="Carga el binario con CargadorEnigma y lo ejecuta en la CPU emulada.",
    )
    parser.add_argument(
        "--max-ciclos",
        type=int,
        default=4_000_000,
        help="Limite maximo de ciclos de reloj al ejecutar en CPU.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    defs: Dict[str, str] = {}
    for raw in args.definiciones:
        if "=" in raw:
            k, v = raw.split("=", 1)
            defs[k.strip()] = v.strip()
        else:
            defs[raw.strip()] = "1"

    if args.salida_e64:
        binario = exportar_estructuras_e64(
            args.entrada,
            args.salida_e64,
            es_archivo=True,
            dirs_inclusion=args.dirs_inclusion,
            definiciones=defs,
        )
        sys.stdout.write(
            f"[OK] Ejecutable .e64 generado: {args.salida_e64} "
            f"(codigo={binario.tamano_codigo} B, simbolos={len(binario.tabla_simbolos)})\n"
        )

    if args.ejecutar or not args.salida_e64:
        res = cargar_y_ejecutar_estructuras(
            args.entrada,
            es_archivo=True,
            dirs_inclusion=args.dirs_inclusion,
            definiciones=defs,
            max_ciclos=args.max_ciclos,
            ejecutar=True,
        )
        sys.stdout.write(
            f"[OK] Cargado en 0x{res.info_carga['direccion_base']:08X} | "
            f"Instrucciones={res.cpu.instrucciones} | Ciclos={res.cpu.ciclos} | "
            f"R5=0x{res.banco.leer_nombre('R5'):016X}\n"
        )
        if res.salida_mmio:
            sys.stdout.write(f"[MMIO] {res.salida_mmio}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
