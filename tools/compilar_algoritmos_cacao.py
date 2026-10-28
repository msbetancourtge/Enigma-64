#!/usr/bin/env python3
"""
Compilador Base de CacaoCore-64 para Enigma-64 (Tarea 27).

Compila los tres algoritmos clásicos escritos en CacaoScript (.cac)
hacia lenguaje ensamblador de CacaoCore-64 (.asm) empleando el
compilador oficial de CacaoCore-64:
  1. Euclides (MCD por restas sucesivas: 48, 18 -> 6)
  2. Factorial (5! -> 120)
  3. Fibonacci (7 terminos -> [0, 1, 1, 2, 3, 5, 8])
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Tuple

# Rutas predeterminadas
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "spl" / "traductor" / "cacaocore_src"
OUT_DIR = BASE_DIR / "spl" / "traductor" / "ejemplos"


def buscar_cacaocore_src(candidato: str | None = None) -> Path:
    """Localiza el directorio 'src' del repositorio CacaoCore-64."""
    rutas_a_probar = []
    if candidato:
        rutas_a_probar.append(Path(candidato))
        rutas_a_probar.append(Path(candidato) / "src")

    env_path = os.environ.get("CACAOCORE_PATH")
    if env_path:
        rutas_a_probar.append(Path(env_path))
        rutas_a_probar.append(Path(env_path) / "src")

    # Rutas relativas comunes (scratch, proyectos hermanos, etc.)
    rutas_a_probar.extend([
        Path(r"C:\Users\Usuario\.gemini\antigravity\brain\5fee7d90-c309-4c41-87b9-6b28bed33c24\scratch\CacaoCore_64\src"),
        Path(r"C:\Users\Usuario\.gemini\antigravity\brain\5fee7d90-c309-4c41-87b9-6b28bed33c24\scratch\CacaoCore_64"),
        BASE_DIR.parent / "LP02---CacaoCore_64" / "src",
        BASE_DIR.parent / "LP02---CacaoCore_64",
        BASE_DIR.parent / "cacaocore-64" / "src",
        BASE_DIR.parent / "cacaocore-64",
    ])

    for ruta in rutas_a_probar:
        if (ruta / "compiler" / "compiler.py").is_file():
            return ruta.resolve()
        if (ruta / "src" / "compiler" / "compiler.py").is_file():
            return (ruta / "src").resolve()

    raise FileNotFoundError(
        "No se encontro el compilador de CacaoCore-64 (compiler/compiler.py). "
        "Especifique la ruta con --cacaocore-path o la variable CACAOCORE_PATH."
    )


def compilar_archivo_cacao(ruta_fuente: Path, ruta_cacaocore_src: Path) -> List[str]:
    """Compila un archivo .cac usando el Compiler oficial de CacaoCore-64."""
    cacao_src_str = str(ruta_cacaocore_src.resolve())
    if cacao_src_str not in sys.path:
        sys.path.insert(0, cacao_src_str)

    from compiler.compiler import Compiler

    compilador = Compiler()
    codigo_fuente = ruta_fuente.read_text(encoding="utf-8")
    resultado = compilador.compile_full(codigo_fuente)

    if isinstance(resultado, tuple):
        errores, asmc = resultado
        if errores:
            raise RuntimeError(f"Errores de compilacion en {ruta_fuente.name}: {errores}")
        return asmc
    elif isinstance(resultado, list) and resultado and isinstance(resultado[0], str):
        raise RuntimeError(f"Errores de compilacion en {ruta_fuente.name}: {resultado}")
    else:
        raise RuntimeError(f"Resultado inesperado del compilador: {resultado}")


def formatear_asm_cacao(lineas: List[str], titulo: str, origen: str) -> str:
    """Agrega cabecera estructurada y formato limpio al codigo ensamblador."""
    cabecera = [
        "; " + "=" * 77,
        f"; {titulo}",
        "; Tarea 27 — CacaoCore-64 hacia Enigma-64",
        f"; Generado automaticamente a partir de: {origen}",
        "; " + "=" * 77,
        "",
    ]
    return "\n".join(cabecera + lineas) + "\n"


def compilar_todos(cacaocore_path: str | None = None) -> List[Tuple[str, Path]]:
    """Compila los 3 algoritmos clasicos y escribe los .asm resultantes."""
    ruta_cacao = buscar_cacaocore_src(cacaocore_path)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    algoritmos = [
        ("euclides.cac", "cacao_euclides.asm", "Algoritmo 1: Maximo Comun Divisor (Euclides) - MCD(48, 18) = 6"),
        ("factorial.cac", "cacao_factorial.asm", "Algoritmo 2: Calculo del Factorial - 5! = 120"),
        ("fibonacci.cac", "cacao_fibonacci.asm", "Algoritmo 3: Sucesion de Fibonacci - [0, 1, 1, 2, 3, 5, 8]"),
    ]

    generados: List[Tuple[str, Path]] = []
    for src_nombre, out_nombre, titulo in algoritmos:
        src_path = SRC_DIR / src_nombre
        out_path = OUT_DIR / out_nombre
        if not src_path.is_file():
            raise FileNotFoundError(f"No existe el archivo fuente {src_path}")

        print(f"Compilando {src_nombre} -> {out_nombre}...")
        lineas_asm = compilar_archivo_cacao(src_path, ruta_cacao)
        contenido_asm = formatear_asm_cacao(lineas_asm, titulo, src_nombre)
        out_path.write_text(contenido_asm, encoding="utf-8")
        print(f"  OK: {len(lineas_asm)} lineas de ensamblador emitidas en {out_path.name}")
        generados.append((titulo, out_path))

    return generados


def main():
    parser = argparse.ArgumentParser(description="Compilador Base de CacaoCore-64 para Tarea 27")
    parser.add_argument("--cacaocore-path", "-c", type=str, default=None,
                        help="Ruta al repositorio o carpeta src/ de CacaoCore-64")
    args = parser.parse_args()

    try:
        generados = compilar_todos(args.cacaocore_path)
        print("\nCompilacion completada con exito:")
        for titulo, ruta in generados:
            print(f"  * {ruta.name} ({ruta.stat().st_size} bytes) - {titulo}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
