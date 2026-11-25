"""
Suite de Pruebas de la vista binaria pura (0 y 1) del Enlazador - Enigma-64.

Taller 02, Integrante 3 (mejoras 2 y 3 de la retroalimentacion del Taller 01):
  1. Desglose de campos de las 41 instrucciones del ISA (tabla de la CPU).
  2. Texto en ensamblador que el ensamblador del equipo vuelve a codificar igual.
  3. Volcado del modulo objeto: offsets relativos al inicio de cada seccion,
     marcas de reubicacion pendientes y tabla de reubicacion en bits.
  4. Volcado de la imagen enlazada: direccion absoluta + offset relativo a la
     base de su seccion, rellenos de alineacion y campos parchados.
  5. Mapa de enlace con la base de cada direccion y el mapa de direcciones
     reubicadas (P, S, A, formula, bits escritos y base del valor).
  6. Linea de comandos con --binario.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

import contextlib
import io
import os
import re
import tempfile
import unittest

from enigma64.cpu import _INSTRUCTIONS
from enigma64.ensamblador import ensamblar
from spl.enlazador import (
    FORMULA_REUBICACION,
    REUB_ABS64,
    REUB_REL16,
    SECCION_ABSOLUTA,
    EnlazadorEnigma,
    MarcaReubicacion,
    ModuloObjeto,
    ReubicacionAplicada,
    SeccionObjeto,
    SimboloObjeto,
    analizar_objeto,
    bits,
    decodificar,
    formatear_enlace_bits,
    formatear_modulo_bits,
)
from spl.enlazador.__main__ import main as cli_enlazador
from spl.enlazador.ejemplos import (
    CODIGO_LIBMAT,
    CODIGO_PRINCIPAL,
    RUTA_LIBMAT,
    RUTA_PRINCIPAL,
    construir_modulo_libmat,
    construir_modulo_principal,
)

from .objetos_prueba import empaquetar_obj, guardar_obj

BASE = 0x00200000

# Linea del volcado: [<posicion> | <n> B] <grupos de 8 bits> -> <descripcion>
LINEA = re.compile(r"^  \[(?P<pos>[^|]+) \| (?P<n>\d+) B\] (?P<bits>[01]{8}(?: [01]{8})*) -> (?P<texto>.*)$")

# Un ejemplo por formato del ISA, en la sintaxis del ensamblador del equipo
PROGRAMA_TODOS_LOS_FORMATOS = """
    HLT
    RET
    INC R3
    NOT R7
    PUSH R7
    POP R6
    JMPR R4
    ADD R5, R2, R3
    XOR R1, R1, R1
    CMP R5, R0
    ADDI R5, R0, 42
    ADDI R1, R1, -1
    SHL R1, R1, 16
    LOAD R2, [R1 + 8]
    STORE R5, [R7 - 16]
    ENTER 32
    LEAVE
    JMP 0x00200039
    CALL 0x0020003D
"""


def _lineas(volcado: str):
    return [m for m in (LINEA.match(l) for l in volcado.splitlines()) if m]


def _bytes_de(lineas) -> bytes:
    return bytes(int(g, 2) for m in lineas for g in m.group("bits").split())


class TestCamposDeInstruccion(unittest.TestCase):
    """El desglose de campos es el que decodifica la CPU."""

    def test_bits(self) -> None:
        self.assertEqual(bits(b"\x14\x50\x00\x2A"), "00010100 01010000 00000000 00101010")
        self.assertEqual(bits(b""), "")

    def test_los_campos_cubren_todos_los_bits_de_cada_opcode(self) -> None:
        self.assertEqual(len(_INSTRUCTIONS), 41)
        for opcode, (mnemonico, formato, longitud) in _INSTRUCTIONS.items():
            with self.subTest(mnemonico=mnemonico):
                crudo = bytes([opcode]) + bytes((0xA5 + 7 * i) & 0xFF for i in range(longitud - 1))
                instruccion = decodificar(crudo, 0)
                self.assertEqual((instruccion.mnemonico, instruccion.formato, instruccion.longitud),
                                 (mnemonico, formato, longitud))
                concatenado = "".join(v for grupo in instruccion.campos for _n, v in grupo)
                self.assertEqual(concatenado, bits(crudo).replace(" ", ""))
                self.assertEqual(instruccion.campos[0], [("Opcode", f"{opcode:08b}")])

    def test_ejemplo_del_documento_del_taller(self) -> None:
        instruccion = decodificar(ensamblar("ADDI R5, R0, 42", direccion_base=0), 0)
        self.assertEqual(
            f"{bits(instruccion.crudo)} -> {instruccion.ensamblador()} ({instruccion.texto_campos()})",
            "00010100 01010000 00000000 00101010 -> ADDI R5, R0, 42 "
            "(Opcode:00010100 | Rd:0101 Rs1:0000 | Imm16:0000000000101010)",
        )

    def test_campos_por_formato(self) -> None:
        casos = {
            "HLT": "Opcode:00000000",
            "INC R3": "Opcode:00010110 | Rd:0011 Relleno:0000",
            "PUSH R7": "Opcode:01001101 | Rd:0111 Relleno:0000",
            "ADD R5, R2, R3": "Opcode:00010000 | Rd:0101 Rs1:0010 | Rs2:0011 Relleno:0000",
            "CMP R5, R0": "Opcode:00100111 | Relleno:0000 Rs1:0101 | Rs2:0000 Relleno:0000",
            "LOAD R2, [R1 + 8]": "Opcode:00110000 | Rd:0010 Rs1:0001 | Off16:0000000000001000",
            "ENTER 32": "Opcode:01001111 | Relleno:00000000 | Imm16:0000000000100000",
            "CALL 0x0020003D": "Opcode:01001010 | Addr32:00000000001000000000000000111101",
        }
        for fuente, esperado in casos.items():
            with self.subTest(instruccion=fuente):
                instruccion = decodificar(ensamblar(fuente, direccion_base=0), 0)
                self.assertEqual(instruccion.texto_campos(), esperado)

    def test_salto_relativo(self) -> None:
        # JZ hacia 0x20 desde 0x00: desplazamiento 0x20 - 0x03 = +29
        instruccion = decodificar(ensamblar("JZ 0x20", direccion_base=0), 0)
        self.assertEqual(instruccion.texto_campos(), "Opcode:01000001 | Rel16:0000000000011101")
        self.assertEqual((instruccion.ensamblador(), instruccion.desplazamiento_relativo), ("JZ +29", 29))
        atras = decodificar(bytes([0x42, 0xFF, 0xFD]), 0)
        self.assertEqual(atras.ensamblador(), "JNZ -3")

    def test_el_texto_se_vuelve_a_ensamblar_igual(self) -> None:
        codigo = ensamblar(PROGRAMA_TODOS_LOS_FORMATOS, direccion_base=0)
        offset = 0
        while offset < len(codigo):
            instruccion = decodificar(codigo, offset)
            with self.subTest(instruccion=instruccion.ensamblador()):
                self.assertEqual(ensamblar(instruccion.ensamblador(), direccion_base=0), instruccion.crudo)
            offset += instruccion.longitud
        self.assertEqual(offset, len(codigo))

    def test_opcode_desconocido_o_instruccion_cortada(self) -> None:
        self.assertIsNone(decodificar(b"\xFF", 0))
        self.assertIsNone(decodificar(b"\x14\x10", 0))


class TestVolcadoDelModuloObjeto(unittest.TestCase):
    """Offsets relativos al inicio de cada seccion y marcas pendientes."""

    def setUp(self) -> None:
        self.modulo = construir_modulo_principal()
        self.volcado = self.modulo.formatear_binario_bits()

    def test_metodo_del_modulo_y_funcion_dan_lo_mismo(self) -> None:
        self.assertEqual(self.volcado, formatear_modulo_bits(self.modulo))

    def test_los_bits_reconstruyen_cada_seccion(self) -> None:
        lineas = _lineas(self.volcado)
        texto = [m for m in lineas if m.group("pos").startswith(".text+")]
        datos = [m for m in lineas if m.group("pos").startswith(".data+")]
        self.assertEqual(_bytes_de(texto), CODIGO_PRINCIPAL)
        self.assertEqual(_bytes_de(datos), self.modulo.seccion(".data").contenido)
        # Las posiciones son offsets consecutivos desde 0x0000 dentro de .text
        offsets = [int(m.group("pos").split("+")[1], 16) for m in texto]
        tamanos = [int(m.group("n")) for m in texto]
        self.assertEqual(offsets[0], 0)
        self.assertEqual(offsets[1:], [o + n for o, n in zip(offsets, tamanos)][:-1])

    def test_lineas_de_instruccion_y_de_palabra(self) -> None:
        for fragmento in (
            "  [.text+0x0000 | 4 B] 00010100 00010000 00000000 00000000 -> ADDI R1, R0, 0 "
            "(Opcode:00010100 | Rd:0001 Rs1:0000 | Imm16:0000000000000000)",
            "  [.text+0x0014 | 5 B] 01001010 00000000 00000000 00000000 00000000 -> CALL 0x00000000",
            "  [.text+0x0038 | 1 B] 00000000 -> HLT (Opcode:00000000)",
            "  [.data+0x0000 | 8 B] 00000000 00000000 00000000 00000000 00000000 00000000 00000000 "
            "00011110 -> palabra 0x000000000000001E = 30",
        ):
            self.assertIn(fragmento, self.volcado)

    def test_marcas_pendientes_con_su_base(self) -> None:
        self.assertIn("      ^ HI16 valores+0: campo .text+0x0002..0x0003 (relativo al inicio de .text); "
                      "al enlazar recibe (S + A + 0x8000) >> 16", self.volcado)
        self.assertIn("      ^ ABS64 copia+0: campo .data+0x0018..0x001F (relativo al inicio de .data)",
                      self.volcado)
        # El destino del JZ depende de la marca REL16: no se inventa uno
        self.assertIn("-> JZ +0 (Opcode:01000001 | Rel16:0000000000000000) ; destino pendiente: "
                      "lo fija la marca REL16 al enlazar", self.volcado)

    def test_salto_relativo_sin_marca_dice_su_destino(self) -> None:
        modulo = ModuloObjeto("saltos", [SeccionObjeto.texto(ensamblar("JZ 0x20\nHLT", direccion_base=0))])
        self.assertIn("-> JZ +29 (Opcode:01000001 | Rel16:0000000000011101) ; destino .text+0x0020 = PC "
                      "siguiente .text+0x0003 +29 B (relativo al PC de la instruccion siguiente)",
                      modulo.formatear_binario_bits())

    def test_reserva_y_tabla_de_reubicacion(self) -> None:
        self.assertIn("  [.bss+0x0000 | 16 B] " + " ".join(["00000000"] * 16) + " -> reserva sin bytes "
                      "en el archivo: el enlazador la llena con ceros (.bss+0x0000 a .bss+0x000F)",
                      self.volcado)
        self.assertIn("Tabla de reubicacion (6): offsets relativos al inicio de la seccion que se parcha",
                      self.volcado)
        tabla = self.volcado.split("Tabla de reubicacion (6)")[1]
        fila = next(l for l in tabla.splitlines() if l.startswith("  .text") and "REL16" in l)
        self.assertIn("0x001D", fila)
        self.assertIn(FORMULA_REUBICACION[REUB_REL16], fila)
        self.assertTrue(fila.rstrip().endswith("00000000 00000000"))

    def test_binario_y_texto_dan_el_mismo_volcado(self) -> None:
        desde_binario = ModuloObjeto.deserializar(empaquetar_obj(self.modulo))
        self.assertEqual(desde_binario.formatear_binario_bits(), self.volcado)

    def test_casos_limite(self) -> None:
        modulo = ModuloObjeto("raro", [
            SeccionObjeto.texto(b"\xFF\x14\x10", nombre=".text"),
            SeccionObjeto.datos(bytes(range(12)), nombre=".data"),
            SeccionObjeto.reserva(4096, nombre=".pila"),
            SeccionObjeto.texto(b"", nombre=".vacia"),
        ])
        volcado = modulo.formatear_binario_bits()
        self.assertIn("[.text+0x0000 | 1 B] 11111111 -> byte sin instruccion valida (0xFF)", volcado)
        self.assertIn("[.text+0x0002 | 1 B] 00010000 -> byte sin instruccion valida (0x10)", volcado)
        self.assertIn("[.data+0x0008 | 4 B] 00001000 00001001 00001010 00001011 -> 4 bytes 0x08090A0B", volcado)
        self.assertIn("[.pila+0x0000 | 4096 B] 00000000 x 4096 -> reserva", volcado)
        self.assertIn("Seccion .vacia (BITS, R-X, alineacion 1, 0 bytes)\n  (seccion vacia)", volcado)


class TestVolcadoDeLaImagenEnlazada(unittest.TestCase):
    """Direccion absoluta + offset relativo a la base de su seccion."""

    def setUp(self) -> None:
        self.resultado = EnlazadorEnigma([construir_modulo_principal(), construir_modulo_libmat()]).enlazar(BASE)
        self.imagen = bytes(self.resultado.binario.bytes_completos())
        self.volcado = self.resultado.formatear_binario_bits()

    def test_metodo_del_resultado_y_funcion_dan_lo_mismo(self) -> None:
        self.assertEqual(self.volcado, formatear_enlace_bits(self.resultado))

    def test_los_bits_reconstruyen_la_imagen_completa(self) -> None:
        lineas = _lineas(self.volcado)
        self.assertEqual(_bytes_de(lineas), self.imagen)
        direcciones = [int(re.match(r"Dir 0x([0-9A-F]{8})", m.group("pos")).group(1), 16) for m in lineas]
        tamanos = [int(m.group("n")) for m in lineas]
        self.assertEqual(direcciones[0], BASE)
        self.assertEqual(direcciones[1:], [d + n for d, n in zip(direcciones, tamanos)][:-1])

    def test_cada_direccion_lleva_su_offset_de_seccion(self) -> None:
        for fragmento in (
            ".text de 'libmat' (BITS, R-X, 13 bytes): base de la seccion 0x00200039 = base de carga + 0x0039",
            "  [Dir 0x0020003D (.text+0x0004) | 4 B] 00010100 01010000 00000000 11101110 -> ADDI R5, R0, 238",
            "  [Dir 0x00200058 (.data+0x0010) | 8 B]",
            "Relleno de alineacion (2 bytes)\n  [Dir 0x00200046 | 2 B] 00000000 00000000 -> relleno "
            "(no pertenece a ninguna seccion)",
            "  [Dir 0x00200068 (.bss+0x0000) | 16 B]",
        ):
            self.assertIn(fragmento, self.volcado)

    def test_salto_rel16_relativo_al_pc_siguiente(self) -> None:
        self.assertIn(
            "  [Dir 0x0020001C (.text+0x001C) | 3 B] 01000001 00000000 00011110 -> JZ +30 "
            "(Opcode:01000001 | Rel16:0000000000011110) ; destino 0x0020003D = PC siguiente 0x0020001F +30 B",
            self.volcado,
        )
        self.assertEqual(self.resultado.simbolos["error"], 0x0020001F + 30)

    def test_campos_parchados(self) -> None:
        self.assertIn(
            "      ^ ABS32 sumar+0: S = 0x00200039, campo P = 0x00200015 (.text+0x0015 de 'principal', "
            "relativo a la base de la seccion 0x00200000); escrito 00000000 00100000 00000000 00111001",
            self.volcado,
        )
        self.assertIn("escrito 00000000 00011110 = +30 B relativo al PC siguiente 0x0020001F", self.volcado)

    def test_en_otra_base_cambian_las_direcciones_y_no_los_offsets(self) -> None:
        otro = EnlazadorEnigma([construir_modulo_principal(), construir_modulo_libmat()]).enlazar(0x00340003)
        volcado = otro.formatear_binario_bits()
        self.assertEqual(_bytes_de(_lineas(volcado)), bytes(otro.binario.bytes_completos()))
        self.assertIn("[Dir 0x0034003C (.text+0x0000) | 3 B] 00010000 01010010 00110000 -> ADD R5, R2, R3",
                      volcado)
        # libmat termina en 0x00340049; .data se alinea a 8 en 0x00340050
        self.assertIn("Relleno de alineacion (7 bytes)\n  [Dir 0x00340049 | 7 B]", volcado)
        self.assertIn("base de la seccion 0x00340050 = base de carga + 0x004D", volcado)

    def test_reserva_grande_se_resume(self) -> None:
        modulo = ModuloObjeto("pila", [SeccionObjeto.texto(b"\x00"), SeccionObjeto.reserva(4096, ".pila")])
        volcado = EnlazadorEnigma([modulo]).enlazar(BASE).formatear_binario_bits()
        self.assertIn("[Dir 0x00200008 (.pila+0x0000) | 4096 B] 00000000 x 4096 -> reserva en cero", volcado)
        self.assertIn("Relleno de alineacion (7 bytes)\n  [Dir 0x00200001 | 7 B] "
                      + " ".join(["00000000"] * 7), volcado)


class TestMapaDeEnlaceYReubicaciones(unittest.TestCase):
    """Base de cada direccion del mapa y mapa de direcciones reubicadas."""

    def setUp(self) -> None:
        self.resultado = EnlazadorEnigma([construir_modulo_principal(), construir_modulo_libmat()]).enlazar(BASE)
        self.imagen = bytes(self.resultado.binario.bytes_completos())

    def test_detalle_de_cada_reubicacion(self) -> None:
        detalle = self.resultado.detalle_reubicaciones
        self.assertEqual(len(detalle), self.resultado.reubicaciones_aplicadas)
        self.assertEqual(
            [(a.seccion, a.offset, a.nombre_tipo, a.simbolo, a.direccion_campo) for a in detalle],
            [(".text", 0x02, "HI16", "valores", 0x00200002),
             (".text", 0x0A, "LO16", "valores", 0x0020000A),
             (".text", 0x15, "ABS32", "sumar", 0x00200015),
             (".text", 0x1D, "REL16", "error", 0x0020001D),
             (".text", 0x2C, "ABS32", "fin", 0x0020002C),
             (".data", 0x18, "ABS64", "copia", 0x00200060)],
        )
        for aplicada in detalle:
            with self.subTest(campo=hex(aplicada.direccion_campo)):
                self.assertIsInstance(aplicada, ReubicacionAplicada)
                inicio = aplicada.direccion_campo - BASE
                self.assertEqual(self.imagen[inicio:inicio + aplicada.ancho], aplicada.valor)
        rel16 = detalle[3]
        self.assertEqual((rel16.pc_siguiente, rel16.desplazamiento), (0x0020001F, 30))
        self.assertEqual(detalle[5].base_seccion, 0x00200048)

    def test_informe_dice_la_base_de_cada_direccion(self) -> None:
        informe = self.resultado.informe()
        for fragmento in (
            "Relativa a la base de carga",
            "0x00200039  13      R-X   .text    libmat     0x00200000 + 0x0039",
            "0x0020003D  error      libmat     .text de libmat (0x00200039) + 0x0004",
            "0x00200058  resultado  principal  .data de principal (0x00200048) + 0x0010",
            "Mapa de direcciones reubicadas (P = campo parchado, S = simbolo, A = sumando)",
            "+30 B desde el PC siguiente 0x0020001F",
        ):
            self.assertIn(fragmento, informe)
        fila = next(l for l in informe.splitlines() if l.lstrip().startswith("0x00200060"))
        self.assertIn(".data de principal (0x00200048) + 0x0018", fila)
        self.assertIn("ABS64", fila)

    def test_simbolo_absoluto_no_se_reubica(self) -> None:
        constantes = ModuloObjeto("constantes", simbolos=[SimboloObjeto.exportado("TAM", SECCION_ABSOLUTA, 0x40)])
        usuario = ModuloObjeto("usuario", [SeccionObjeto.datos(bytes(8))], [SimboloObjeto.importado("TAM")],
                               [MarcaReubicacion(0, 0, REUB_ABS64, 0)])
        resultado = EnlazadorEnigma([usuario, constantes]).enlazar(BASE)
        self.assertIsNone(resultado.ubicacion_simbolos["TAM"])
        self.assertIn("0x00000040  TAM      constantes  constante absoluta (no se reubica)", resultado.informe())

    def test_sin_marcas_no_hay_mapa_de_reubicadas(self) -> None:
        resultado = EnlazadorEnigma([ModuloObjeto("m", [SeccionObjeto.texto(b"\x00")])]).enlazar(BASE)
        self.assertEqual(resultado.detalle_reubicaciones, [])
        self.assertNotIn("Mapa de direcciones reubicadas", resultado.informe())

    def test_mismo_nombre_de_modulo_y_secciones_vacias(self) -> None:
        # La seccion de cada simbolo se resuelve por indice, no por nombre de modulo
        a = ModuloObjeto("m", [SeccionObjeto.texto(b""), SeccionObjeto.texto(b"\x00", ".t2")],
                         [SimboloObjeto.exportado("x", 1, 0)])
        b = ModuloObjeto("m", [SeccionObjeto.texto(b"")], [SimboloObjeto.exportado("y", 0, 0)])
        resultado = EnlazadorEnigma([a, b]).enlazar(BASE)
        self.assertEqual(resultado.ubicacion_simbolos["x"].seccion, ".t2")
        self.assertEqual(resultado.ubicacion_simbolos["y"].seccion, ".text")


class TestLineaDeComandosBinario(unittest.TestCase):
    """python -m spl.enlazador --binario."""

    def _ejecutar(self, *argumentos):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            codigo = cli_enlazador(list(argumentos))
        return codigo, salida.getvalue()

    def test_volcado_de_modulos_y_de_la_imagen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            libmat_obj = os.path.join(tmp, "libmat.obj")
            guardar_obj(construir_modulo_libmat(), libmat_obj)
            e64 = os.path.join(tmp, "programa.e64")
            codigo, salida = self._ejecutar(RUTA_PRINCIPAL, libmat_obj, "--binario", "--sin-informe", "-o", e64)
            self.assertTrue(os.path.getsize(e64) > 0)
        self.assertEqual(codigo, 0)
        self.assertIn("Volcado binario del modulo objeto 'principal'", salida)
        self.assertIn("Volcado binario del modulo objeto 'libmat'", salida)
        self.assertIn("Volcado binario del ejecutable enlazado: base de carga 0x00200000", salida)
        self.assertNotIn("Encabezados de seccion", salida)

    def test_sin_enlazar_solo_los_modulos(self) -> None:
        codigo, salida = self._ejecutar(RUTA_LIBMAT, "--binario", "--sin-informe")
        self.assertEqual(codigo, 0)
        self.assertIn("[.text+0x0000 | 3 B] 00010000 01010010 00110000 -> ADD R5, R2, R3", salida)
        self.assertNotIn("ejecutable enlazado", salida)
        self.assertEqual(_bytes_de(_lineas(salida)), CODIGO_LIBMAT)

    def test_sin_la_opcion_la_salida_no_cambia_de_forma(self) -> None:
        _, salida = self._ejecutar(RUTA_PRINCIPAL)
        self.assertNotIn("Volcado binario", salida)
        self.assertIn("Tabla de exportaciones (3): Valor = offset relativo al inicio de su seccion", salida)
        self.assertEqual(analizar_objeto(RUTA_PRINCIPAL).nombre, "principal")


if __name__ == "__main__":
    unittest.main()
