"""
Archivos .obj de prueba para las suites del Enlazador-Cargador - Enigma-64.

El Enlazador-Cargador solo lee modulos objeto (.obj y .tobj) y escribe el
ejecutable .e64. Para probar el lector binario, las pruebas arman los bytes de
entrada con este codificador propio, escrito a partir de la especificacion del
formato EOBJ v1 (Big-Endian). Los formatos struct van fijos aqui y no se toman
de spl/enlazador/objeto.py, asi un cambio en el lector no pasa inadvertido.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

import struct

# Especificacion del formato (la misma que documenta spl/enlazador/objeto.py)
FORMATO_CABECERA = ">4sHHHHIIIIIIIIII"   # 52 B
FORMATO_SECCION = ">IHHIII"              # 20 B: nombre, tipo, permisos, alineacion, tamano, offset
FORMATO_SIMBOLO = ">IHBBI"               # 12 B: nombre, seccion, ligadura, tipo, valor
FORMATO_REUBICACION = ">HBBIIi"          # 16 B: seccion, tipo, reservado, offset, simbolo, sumando
SECCION_BITS, SECCION_INDEFINIDA, BANDERA_ENTRADA = 1, 0xFFFF, 0x0001


def empaquetar_obj(modulo) -> bytes:
    """Bytes del archivo .obj que describe el modulo (no lo valida: sirve para armar casos)."""
    cadenas, offsets = bytearray(b"\x00"), {"": 0}

    def cadena(texto: str) -> int:
        if texto not in offsets:
            offsets[texto] = len(cadenas)
            cadenas.extend(texto.encode("utf-8") + b"\x00")
        return offsets[texto]

    nombre_modulo = cadena(modulo.nombre)
    off_secciones = struct.calcsize(FORMATO_CABECERA)
    off_contenido = off_secciones + struct.calcsize(FORMATO_SECCION) * len(modulo.secciones)
    encabezados, contenidos = bytearray(), bytearray()
    for sec in modulo.secciones:
        offset = 0
        if sec.tipo == SECCION_BITS:
            offset = off_contenido + len(contenidos)
            contenidos.extend(sec.contenido)
        encabezados += struct.pack(FORMATO_SECCION, cadena(sec.nombre), sec.tipo, sec.permisos,
                                   sec.alineacion, sec.tamano, offset)
    off_simbolos = off_contenido + len(contenidos)
    simbolos = b"".join(
        struct.pack(FORMATO_SIMBOLO, cadena(s.nombre), s.seccion, s.ligadura, s.tipo, s.valor)
        for s in modulo.simbolos
    )
    off_marcas = off_simbolos + len(simbolos)
    marcas = b"".join(
        struct.pack(FORMATO_REUBICACION, m.seccion, m.tipo, 0, m.offset, m.simbolo, m.sumando)
        for m in modulo.reubicaciones
    )
    off_cadenas = off_marcas + len(marcas)
    if modulo.entrada is not None:
        banderas, (seccion_entrada, offset_entrada) = BANDERA_ENTRADA, modulo.entrada
    else:
        banderas, seccion_entrada, offset_entrada = 0, SECCION_INDEFINIDA, 0
    cabecera = struct.pack(
        FORMATO_CABECERA, b"EOBJ", 1, 0xE064, banderas, seccion_entrada, offset_entrada,
        nombre_modulo, len(modulo.secciones), off_secciones, len(modulo.simbolos), off_simbolos,
        len(modulo.reubicaciones), off_marcas, len(cadenas), off_cadenas,
    )
    return cabecera + bytes(encabezados) + bytes(contenidos) + simbolos + marcas + bytes(cadenas)


def guardar_obj(modulo, ruta: str) -> None:
    """Escribe en disco el .obj de prueba del modulo."""
    with open(ruta, "wb") as f:
        f.write(empaquetar_obj(modulo))
