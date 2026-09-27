"""
Catalogo de los tres algoritmos de verificacion de Enigma-64.

Son los programas de la Tarea 9, transcritos byte a byte de la seccion
"Traduccion Manual a Lenguaje de Maquina (Big-Endian)". No se vuelven a
ensamblar aqui: se guardan tal y como el grupo los tradujo a mano, de modo que
el panel muestra exactamente lo que dice el documento y cualquier discrepancia
sale en las pruebas.

Cada entrada trae:
  * el listado en ensamblador con su direccion y su codigo maquina,
  * los datos de entrada que hay que sembrar en RAM antes de ejecutar,
  * la direccion y el valor del resultado esperado, para poder verificar.

Es dato puro: no importa ningun modulo de hardware.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Una instruccion del listado: (direccion, mnemonico, bytes, comentario)
Instruccion = Tuple[int, str, bytes, str]


# ---------------------------------------------------------------------------
# Algoritmo 1: Factorial de N
# ---------------------------------------------------------------------------

FACTORIAL: List[Instruccion] = [
    (0x00200000, "ADDI  R1, R0, 0x0020", b"\x14\x10\x00\x20", "R1 = 0x0020"),
    (0x00200004, "SHL   R1, R1, 16",     b"\x24\x11\x00\x10", "R1 = 0x00200000"),
    (0x00200008, "ADDI  R1, R1, 0x1000", b"\x14\x11\x10\x00", "R1 = 0x00201000 (base de datos)"),
    (0x0020000C, "LOAD  R2, [R1 + 0]",   b"\x30\x21\x00\x00", "R2 = N"),
    (0x00200010, "ADDI  R3, R0, 1",      b"\x14\x30\x00\x01", "R3 = factorial = 1"),
    (0x00200014, "CMP   R2, R0",         b"\x27\x02\x00",     "compara N con 0 (actualiza Z)"),
    (0x00200017, "JZ    FIN_FACT",       b"\x41\x00\x0A",     "si N == 0, salta al final (+10B)"),
    (0x0020001A, "MUL   R3, R3, R2",     b"\x12\x33\x20",     "LOOP_FACT: factorial *= N"),
    (0x0020001D, "SUBI  R2, R2, 1",      b"\x15\x22\x00\x01", "N = N - 1 (actualiza Z)"),
    (0x00200021, "JNZ   LOOP_FACT",      b"\x42\xFF\xF6",     "si N != 0, repetir (-10B)"),
    (0x00200024, "STORE R3, [R1 + 8]",   b"\x31\x31\x00\x08", "FIN_FACT: Mem[0x00201008] = factorial"),
    (0x00200028, "HLT",                  b"\x00",             "detener ejecucion"),
]

# ---------------------------------------------------------------------------
# Algoritmo 2: Maximo comun divisor por restas sucesivas (Euclides)
# ---------------------------------------------------------------------------

EUCLIDES: List[Instruccion] = [
    (0x00200100, "ADDI  R1, R0, 0x0020", b"\x14\x10\x00\x20", "R1 = 0x0020"),
    (0x00200104, "SHL   R1, R1, 16",     b"\x24\x11\x00\x10", "R1 = 0x00200000"),
    (0x00200108, "ADDI  R1, R1, 0x2000", b"\x14\x11\x20\x00", "R1 = 0x00202000 (base de datos)"),
    (0x0020010C, "LOAD  R2, [R1 + 0]",   b"\x30\x21\x00\x00", "R2 = A"),
    (0x00200110, "LOAD  R3, [R1 + 8]",   b"\x30\x31\x00\x08", "R3 = B"),
    (0x00200114, "CMP   R2, R3",         b"\x27\x02\x30",     "LOOP: evalua A - B (Z, N)"),
    (0x00200117, "JZ    FIN_EUCLIDES",   b"\x41\x00\x13",     "si A == B, terminado (+19B)"),
    (0x0020011A, "JN    B_ES_MAYOR",     b"\x45\x00\x08",     "si A < B (N=1), restar B (+8B)"),
    (0x0020011D, "SUB   R2, R2, R3",     b"\x11\x22\x30",     "caso A > B: A = A - B"),
    (0x00200120, "JMP   0x00200114",     b"\x40\x00\x20\x01\x14", "vuelve al inicio del bucle"),
    (0x00200125, "SUB   R3, R3, R2",     b"\x11\x33\x20",     "B_ES_MAYOR: B = B - A"),
    (0x00200128, "JMP   0x00200114",     b"\x40\x00\x20\x01\x14", "vuelve al inicio del bucle"),
    (0x0020012D, "STORE R2, [R1 + 16]",  b"\x31\x21\x00\x10", "FIN: Mem[0x00202010] = MCD"),
    (0x00200131, "HLT",                  b"\x00",             "detener procesador"),
]

# ---------------------------------------------------------------------------
# Algoritmo 3: Sucesion de Fibonacci en RAM
# ---------------------------------------------------------------------------

FIBONACCI: List[Instruccion] = [
    (0x00200200, "ADDI  R1, R0, 0x0020", b"\x14\x10\x00\x20", "R1 = 0x0020"),
    (0x00200204, "SHL   R1, R1, 16",     b"\x24\x11\x00\x10", "R1 = 0x00200000"),
    (0x00200208, "ADDI  R1, R1, 0x3000", b"\x14\x11\x30\x00", "R1 = 0x00203000 (base del arreglo)"),
    (0x0020020C, "ADDI  R2, R0, 0",      b"\x14\x20\x00\x00", "R2 = F0 = 0"),
    (0x00200210, "ADDI  R3, R0, 1",      b"\x14\x30\x00\x01", "R3 = F1 = 1"),
    (0x00200214, "STORE R2, [R1 + 0]",   b"\x31\x21\x00\x00", "Mem[0x00203000] = 0"),
    (0x00200218, "STORE R3, [R1 + 8]",   b"\x31\x31\x00\x08", "Mem[0x00203008] = 1"),
    (0x0020021C, "ADDI  R1, R1, 16",     b"\x14\x11\x00\x10", "ptr = ptr + 16"),
    (0x00200220, "ADDI  R4, R0, 5",      b"\x14\x40\x00\x05", "R4 = 5 terminos restantes"),
    (0x00200224, "ADD   R5, R3, R2",     b"\x10\x53\x20",     "LOOP: F_sig = F1 + F0"),
    (0x00200227, "STORE R5, [R1 + 0]",   b"\x31\x51\x00\x00", "Mem[ptr] = F_sig"),
    (0x0020022B, "ADDI  R2, R3, 0",      b"\x14\x23\x00\x00", "F0 = F1"),
    (0x0020022F, "ADDI  R3, R5, 0",      b"\x14\x35\x00\x00", "F1 = F_sig"),
    (0x00200233, "ADDI  R1, R1, 8",      b"\x14\x11\x00\x08", "ptr = ptr + 8"),
    (0x00200237, "SUBI  R4, R4, 1",      b"\x15\x44\x00\x01", "contador -= 1 (actualiza Z)"),
    (0x0020023B, "JNZ   LOOP_FIBONACCI", b"\x42\xFF\xE6",     "si contador != 0, repetir (-26B)"),
    (0x0020023E, "HLT",                  b"\x00",             "fin del programa"),
]


# ---------------------------------------------------------------------------
# Catalogo
# ---------------------------------------------------------------------------

CATALOGO: List[Dict[str, Any]] = [
    {
        "clave": "factorial",
        "nombre": "Factorial de N",
        "resumen": "Calcula N! por multiplicaciones sucesivas con un bucle decremental.",
        "listado": FACTORIAL,
        "base": 0x00200000,
        "datos": 0x00201000,
        # Entradas a sembrar en RAM antes de ejecutar: (direccion, valor, bytes)
        "entradas": [(0x00201000, 5, 8)],
        "etiquetas_entrada": ["N"],
        "resultado": {"direccion": 0x00201008, "tamano": 8, "esperado": 120,
                      "etiqueta": "5! = 120"},
        "pseudocodigo": (
            "N = Mem[0x00201000]\n"
            "factorial = 1\n"
            "si N == 0 entonces ir a FIN_FACT\n"
            "mientras N > 0 hacer:\n"
            "    factorial = factorial * N\n"
            "    N = N - 1\n"
            "fin mientras\n"
            "Mem[0x00201008] = factorial"
        ),
    },
    {
        "clave": "euclides",
        "nombre": "Algoritmo de Euclides",
        "resumen": "Maximo comun divisor de A y B por restas sucesivas.",
        "listado": EUCLIDES,
        "base": 0x00200100,
        "datos": 0x00202000,
        "entradas": [(0x00202000, 48, 8), (0x00202008, 18, 8)],
        "etiquetas_entrada": ["A", "B"],
        "resultado": {"direccion": 0x00202010, "tamano": 8, "esperado": 6,
                      "etiqueta": "MCD(48, 18) = 6"},
        "pseudocodigo": (
            "A = Mem[0x00202000]\n"
            "B = Mem[0x00202008]\n"
            "mientras A != B hacer:\n"
            "    si A < B entonces B = B - A\n"
            "    sino A = A - B\n"
            "fin mientras\n"
            "Mem[0x00202010] = A"
        ),
    },
    {
        "clave": "fibonacci",
        "nombre": "Sucesion de Fibonacci",
        "resumen": "Genera los primeros 7 terminos y los guarda en palabras de 64 bits.",
        "listado": FIBONACCI,
        "base": 0x00200200,
        "datos": 0x00203000,
        "entradas": [],
        "etiquetas_entrada": [],
        "resultado": {"direccion": 0x00203000, "tamano": 8, "esperado": 0,
                      "etiqueta": "[0, 1, 1, 2, 3, 5, 8]",
                      "secuencia": [0, 1, 1, 2, 3, 5, 8]},
        "pseudocodigo": (
            "F0 = 0 ; F1 = 1\n"
            "Mem[0x00203000] = F0\n"
            "Mem[0x00203008] = F1\n"
            "ptr = 0x00203010 ; contador = 5\n"
            "mientras contador > 0 hacer:\n"
            "    F_sig = F1 + F0\n"
            "    Mem[ptr] = F_sig\n"
            "    F0 = F1 ; F1 = F_sig\n"
            "    ptr = ptr + 8 ; contador -= 1\n"
            "fin mientras"
        ),
    },
]


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------


def claves() -> Sequence[str]:
    return tuple(a["clave"] for a in CATALOGO)


def obtener(clave: str) -> Optional[Dict[str, Any]]:
    for algoritmo in CATALOGO:
        if algoritmo["clave"] == clave:
            return algoritmo
    return None


def codigo_maquina(algoritmo: Dict[str, Any]) -> bytes:
    """Concatena el codigo maquina de todo el listado, en orden."""
    return b"".join(instruccion[2] for instruccion in algoritmo["listado"])


def tamano(algoritmo: Dict[str, Any]) -> int:
    return len(codigo_maquina(algoritmo))


def direcciones_coherentes(algoritmo: Dict[str, Any]) -> bool:
    """
    Comprueba que las direcciones escritas en el documento encajan con la
    longitud real de cada instruccion. Si el grupo corrige una traduccion a
    mano y se olvida de recalcular una direccion, esto lo detecta.
    """
    direccion = algoritmo["base"]
    for esperada, _mnemonico, octetos, _comentario in algoritmo["listado"]:
        if esperada != direccion:
            return False
        direccion += len(octetos)
    return True
