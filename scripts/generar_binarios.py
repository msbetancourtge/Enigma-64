"""
Script de generacion automatizada de archivos ejecutables (.bin, .hex, .e64)
para los 3 algoritmos de prueba de la Tarea 9 (Tarea 10 de Lenguajes de Programacion).

Uso:
    python scripts/generar_binarios.py

Genera en la carpeta 'programas/':
    - factorial.bin, factorial.hex, factorial.e64
    - euclides.bin, euclides.hex, euclides.e64
    - fibonacci.bin, fibonacci.hex, fibonacci.e64
    - cargador_firmware.bin
"""

import os
import sys

# Agregar la raiz del proyecto al path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from enigma64.programas import (
    exportar_archivos_programas,
    PROGRAMAS_OFICIALES,
    PROGRAMAS_TAREA17,
    BinarioEnigma,
)


def main():
    dir_programas = os.path.join(ROOT_DIR, "programas")
    print(f"[*] Generando binarios en: {dir_programas}")
    rutas = exportar_archivos_programas(dir_programas)

    # Exportar también binarios estructurados de la Tarea 17
    for clave, prog in PROGRAMAS_TAREA17.items():
        if prog.bytes_codigo:
            ruta_e64 = os.path.join(dir_programas, f"{clave}.e64")
            bin_e64 = BinarioEnigma.desde_crudo(
                prog.bytes_codigo,
                direccion_base=prog.direccion_base,
                entry_point=prog.entry_point,
            )
            with open(ruta_e64, "wb") as f:
                f.write(bin_e64.serializar_e64())
            rutas.append(ruta_e64)

    print(f"[+] Se generaron con exito {len(rutas)} archivos:")
    for ruta in rutas:
        nombre = os.path.basename(ruta)
        tamano = os.path.getsize(ruta)
        print(f"    - {nombre:25s} ({tamano} bytes)")

    print("\n[+] Resumen de programas oficiales de la Tarea 9:")
    for clave, prog in PROGRAMAS_OFICIALES.items():
        print(f"    - {prog.nombre.upper()}:")
        print(f"        Base RAM    : 0x{prog.direccion_base:08X}")
        print(f"        Tamano      : {prog.tamano_bytes} bytes")
        print(f"        Entradas RAM: {prog.entradas_ram}")
        print(f"        Salidas RAM : {prog.salidas_esperadas_ram}")

    print("\n[+] Resumen de programas oficiales de la Tarea 17:")
    for clave, prog in PROGRAMAS_TAREA17.items():
        print(f"    - {prog.nombre.upper()}:")
        print(f"        Base RAM    : 0x{prog.direccion_base:08X}")
        print(f"        Tamano      : {prog.tamano_bytes} bytes")
        print(f"        Entradas RAM: {prog.entradas_ram}")
        print(f"        Salidas RAM : {prog.salidas_esperadas_ram}")


if __name__ == "__main__":
    main()
