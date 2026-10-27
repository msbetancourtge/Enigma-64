"""
Suite de Pruebas del Enlazador (modulos objeto reubicables .obj) - Enigma-64.

Verifica:
  1. Reconocimiento de la cabecera y de los encabezados de seccion.
  2. Extraccion de las tablas de exportacion e importacion.
  3. Interpretacion de las marcas de reubicacion.
  4. Rechazo de archivos .obj mal formados o incoherentes (ObjetoInvalido).
  5. Formulas de reubicacion y deteccion de desbordamientos.
  6. Enlace: ubicacion de secciones, ESTAB, resolucion e imagen parchada.
  7. Enlace + carga + ejecucion en la CPU oficial en varias direcciones base.
  8. Integracion con CargadorEnigma.cargar_archivo y la linea de comandos.

Autor: Integrante 3 Michael Stiven Betancourt Gelves - Enlazador-Cargador
"""

import contextlib
import io
import os
import struct
import tempfile
import unittest

from enigma64 import (
    ALU,
    CPU,
    MASK64,
    USER_MEM_START,
    BancoRegistros,
    BinarioEnigma,
    CargadorEnigma,
    DireccionInvalida,
    ErrorCargador,
    FormatoInvalido,
    RAMMemory,
    ViolacionProteccionMemoria,
)
from enigma64.enlazador import (
    LIMITE_HI16,
    PERM_EJECUCION,
    PERM_ESCRITURA,
    PERM_LECTURA,
    REUB_ABS32,
    REUB_ABS64,
    REUB_HI16,
    REUB_LO16,
    REUB_REL16,
    SECCION_ABSOLUTA,
    SECCION_BITS,
    SECCION_INDEFINIDA,
    SECCION_VACIA,
    SIMBOLO_DATO,
    SIMBOLO_FUNCION,
    TAM_CABECERA_OBJ,
    TAM_REUBICACION,
    TAM_SECCION,
    TAM_SIMBOLO,
    VERSION_OBJETO,
    CLASE_CODIGO,
    CLASE_DATOS,
    CLASE_RESERVA,
    DesbordamientoReubicacion,
    EnlazadorEnigma,
    ErrorEnlazador,
    MarcaReubicacion,
    ModuloObjeto,
    ObjetoInvalido,
    SeccionObjeto,
    SimboloDuplicado,
    SimboloNoDefinido,
    SimboloObjeto,
    analizar_objeto,
    calcular_parche,
    texto_permisos,
)
from enigma64.cpu import _INSTRUCTIONS
from enigma64.enlazador.__main__ import main as cli_enlazador
from enigma64.enlazador.ejemplos import (
    CODIGO_ERROR,
    CODIGO_LIBMAT,
    CODIGO_PRINCIPAL,
    VALOR_A,
    VALOR_B,
    construir_modulo_libmat,
    construir_modulo_principal,
)
from enigma64.ensamblador import ensamblar
from enigma64.fpu import (
    CODIGO_FPU_ASM,
    VECTOR_FDIV,
    VECTOR_FMUL,
    EmuladorFPUEnigma64,
    float_a_ieee64,
    ieee64_a_float,
)
from enigma64.programas import BYTES_EUCLIDES

# Mismo programa que CODIGO_PRINCIPAL escrito para el ensamblador oficial; los
# operandos reubicables van en un valor que deja el campo en cero.
FUENTE_PRINCIPAL = """
main:   ADDI R1, R0, 0
        SHL  R1, R1, 16
        ADDI R1, R1, 0
        LOAD R2, [R1 + 0]
        LOAD R3, [R1 + 8]
        CALL 0
        CMP  R5, R0
        JZ   0x1F
        STORE R5, [R1 + 16]
        LOAD R4, [R1 + 24]
        STORE R5, [R4 + 0]
        JMP  0
trampa: ADDI R5, R0, 0x0BAD
        STORE R5, [R1 + 16]
fin:    HLT
"""

FUENTE_LIBMAT = """
sumar:  ADD  R5, R2, R3
        RET
error:  ADDI R5, R0, 0x00EE
        STORE R5, [R1 + 16]
        HLT
"""

# Programa autocontenido: duplica el dato de .data y lo guarda a continuacion
FUENTE_DUPLICADOR = """
inicio: ADDI R1, R0, 0
        SHL  R1, R1, 16
        ADDI R1, R1, 0
        LOAD R2, [R1 + 0]
        ADD  R2, R2, R2
        STORE R2, [R1 + 8]
        HLT
"""

# Cliente de la FPU compilado por separado: pila propia en .bss, operandos en
# .data y la rutina de la FPU como importacion (CALL en +0x24, campo en +0x25).
FUENTE_CLIENTE_FPU = """
main:   ADDI SP, R0, 0
        SHL  SP, SP, 16
        ADDI SP, SP, 0
        ADDI BP, SP, 0
        ADDI R4, R0, 0
        SHL  R4, R4, 16
        ADDI R4, R4, 0
        LOAD R1, [R4 + 0]
        LOAD R2, [R4 + 8]
        CALL 0
        ADDI R4, R0, 0
        SHL  R4, R4, 16
        ADDI R4, R4, 0
        STORE R5, [R4 + 0]
        HLT
"""

BASE = USER_MEM_START  # 0x00200000


def _offsets_de_etiquetas(fuente: str, etiquetas) -> dict:
    """
    Pregunta al ensamblador oficial donde quedo cada etiqueta sin modificarlo:
    agrega al final un JMP por etiqueta y lee su campo absoluto (base 0).
    """
    sin_sondas = ensamblar(fuente, direccion_base=0)
    con_sondas = ensamblar(
        fuente + "\n" + "\n".join(f"JMP {e}" for e in etiquetas), direccion_base=0
    )
    inicio = len(sin_sondas)
    return {
        e: int.from_bytes(con_sondas[inicio + 5 * i + 1 : inicio + 5 * i + 5], "big")
        for i, e in enumerate(etiquetas)
    }


def _modulo_desde_codigo_absoluto(nombre, codigo, base_original, exportaciones) -> ModuloObjeto:
    """
    Convierte codigo absoluto del equipo en un modulo reubicable: barre las
    instrucciones con la tabla del ISA y marca como ABS32 el destino de cada
    JMP / CALL (los saltos relativos no dependen de la posicion).
    """
    marcas = []
    pc = 0
    while pc < len(codigo):
        _mnemonico, formato, longitud = _INSTRUCTIONS[codigo[pc]]
        if formato == "absolute":
            destino = int.from_bytes(codigo[pc + 1 : pc + 5], "big")
            marcas.append(MarcaReubicacion(0, pc + 1, REUB_ABS32, 0, destino - base_original))
        pc += longitud
    simbolos = [SimboloObjeto.local("inicio_text", 0, 0)] + [
        SimboloObjeto.exportado(n, 0, offset, SIMBOLO_FUNCION) for n, offset in exportaciones.items()
    ]
    return ModuloObjeto(nombre, [SeccionObjeto.texto(codigo)], simbolos, marcas)


def _modulo_cliente_fpu(rutina: str, sumando: int = 0) -> ModuloObjeto:
    operandos, resultado, pila_tope, importada = 1, 2, 3, 4
    return ModuloObjeto(
        nombre="cliente",
        secciones=[
            SeccionObjeto.texto(ensamblar(FUENTE_CLIENTE_FPU, direccion_base=0)),
            SeccionObjeto.datos(bytes(24)),
            SeccionObjeto.reserva(4096, ".pila"),
        ],
        simbolos=[
            SimboloObjeto.exportado("main", 0, 0, SIMBOLO_FUNCION),
            SimboloObjeto.local("operandos", 1, 0, SIMBOLO_DATO),
            SimboloObjeto.exportado("resultado", 1, 16, SIMBOLO_DATO),
            SimboloObjeto.local("pila_tope", 2, 4096),
            SimboloObjeto.importado(rutina, SIMBOLO_FUNCION),
        ],
        reubicaciones=[
            MarcaReubicacion(0, 0x02, REUB_HI16, pila_tope),
            MarcaReubicacion(0, 0x0A, REUB_LO16, pila_tope),
            MarcaReubicacion(0, 0x12, REUB_HI16, operandos),
            MarcaReubicacion(0, 0x1A, REUB_LO16, operandos),
            MarcaReubicacion(0, 0x25, REUB_ABS32, importada, sumando),
            MarcaReubicacion(0, 0x2B, REUB_HI16, resultado),
            MarcaReubicacion(0, 0x33, REUB_LO16, resultado),
        ],
        entrada=(0, 0),
    )


def _modulo_duplicador() -> ModuloObjeto:
    return ModuloObjeto(
        nombre="duplicador",
        secciones=[
            SeccionObjeto.texto(ensamblar(FUENTE_DUPLICADOR, direccion_base=0)),
            SeccionObjeto.datos(struct.pack(">QQ", 21, 0)),
        ],
        simbolos=[
            SimboloObjeto.exportado("inicio", 0, 0, SIMBOLO_FUNCION),
            SimboloObjeto.local("dato", 1, 0, SIMBOLO_DATO),
            SimboloObjeto.exportado("doble", 1, 8, SIMBOLO_DATO),
        ],
        reubicaciones=[
            MarcaReubicacion(0, 0x02, REUB_HI16, 1),
            MarcaReubicacion(0, 0x0A, REUB_LO16, 1),
        ],
        entrada=(0, 0),
    )


def _parchear(datos: bytes, offset: int, formato: str, valor) -> bytes:
    copia = bytearray(datos)
    struct.pack_into(formato, copia, offset, valor)
    return bytes(copia)


def _extender_signo_16(valor: int) -> int:
    return valor - 0x10000 if valor & 0x8000 else valor


def _leer64(ram: RAMMemory, direccion: int) -> int:
    valor, _ = ram.mem_read(direccion, size_bytes=8)
    return valor


class TestCabeceraYSecciones(unittest.TestCase):
    """Reconocimiento de la cabecera del archivo y de los encabezados de seccion."""

    def setUp(self) -> None:
        self.original = construir_modulo_principal()
        self.datos = self.original.serializar()
        self.modulo = ModuloObjeto.deserializar(self.datos)

    def test_cabecera_reconocida(self) -> None:
        cab = self.modulo.cabecera
        self.assertTrue(self.datos.startswith(b"EOBJ"))
        self.assertEqual(cab.version, VERSION_OBJETO)
        self.assertEqual(cab.maquina, 0xE064)
        self.assertEqual(cab.tamano_archivo, len(self.datos))
        self.assertEqual((cab.num_secciones, cab.num_simbolos, cab.num_reubicaciones), (3, 9, 6))
        # Disposicion: cabecera, encabezados, contenidos BITS, simbolos, marcas, cadenas
        self.assertEqual(cab.off_secciones, TAM_CABECERA_OBJ)
        self.assertEqual(cab.off_simbolos, TAM_CABECERA_OBJ + 3 * TAM_SECCION + 57 + 32)
        self.assertEqual(cab.off_reubicaciones, cab.off_simbolos + 9 * TAM_SIMBOLO)
        self.assertEqual(cab.off_cadenas, cab.off_reubicaciones + 6 * TAM_REUBICACION)
        self.assertEqual(cab.off_cadenas + cab.tam_cadenas, len(self.datos))
        self.assertEqual(self.modulo.nombre, "principal")
        self.assertEqual(self.modulo.entrada, (0, 0))

    def test_encabezados_de_seccion(self) -> None:
        resumen = [
            (s.nombre, s.tipo, texto_permisos(s.permisos), s.alineacion, s.tamano, s.clase)
            for s in self.modulo.secciones
        ]
        self.assertEqual(resumen, [
            (".text", SECCION_BITS, "R-X", 1, 57, CLASE_CODIGO),
            (".data", SECCION_BITS, "RW-", 8, 32, CLASE_DATOS),
            (".bss", SECCION_VACIA, "RW-", 8, 16, CLASE_RESERVA),
        ])

    def test_contenido_de_seccion_ubicado_en_el_archivo(self) -> None:
        texto, datos, bss = self.modulo.secciones
        self.assertEqual(texto.offset_archivo, TAM_CABECERA_OBJ + 3 * TAM_SECCION)
        self.assertEqual(self.datos[texto.offset_archivo:][:57], CODIGO_PRINCIPAL)
        self.assertEqual(datos.offset_archivo, texto.offset_archivo + 57)
        self.assertEqual(texto.contenido, CODIGO_PRINCIPAL)
        # .bss solo declara su tamano: no tiene bytes en el archivo
        self.assertIsNone(bss.offset_archivo)
        self.assertEqual(bss.contenido, b"")

    def test_fabricas_de_seccion(self) -> None:
        self.assertEqual(SeccionObjeto.texto(b"\x00").permisos, PERM_LECTURA | PERM_EJECUCION)
        self.assertEqual(SeccionObjeto.datos(b"").permisos, PERM_LECTURA | PERM_ESCRITURA)
        reserva = SeccionObjeto.reserva(64)
        self.assertEqual((reserva.tipo, reserva.tamano, reserva.alineacion), (SECCION_VACIA, 64, 8))
        self.assertEqual(texto_permisos(PERM_LECTURA | PERM_ESCRITURA | PERM_EJECUCION), "RWX")


class TestTablasDeSimbolos(unittest.TestCase):
    """Extraccion de las tablas de exportacion e importacion."""

    def setUp(self) -> None:
        self.modulo = ModuloObjeto.deserializar(construir_modulo_principal().serializar())

    def test_tabla_de_exportaciones(self) -> None:
        exportaciones = [
            (s.nombre, self.modulo.nombre_seccion_de(s), s.valor, s.tipo)
            for s in self.modulo.exportaciones
        ]
        self.assertEqual(exportaciones, [
            ("main", ".text", 0x00, SIMBOLO_FUNCION),
            ("resultado", ".data", 0x10, SIMBOLO_DATO),
            ("copia", ".bss", 0x00, SIMBOLO_DATO),
        ])

    def test_tabla_de_importaciones(self) -> None:
        importaciones = self.modulo.importaciones
        self.assertEqual([s.nombre for s in importaciones], ["sumar", "error"])
        for simbolo in importaciones:
            self.assertEqual(simbolo.seccion, SECCION_INDEFINIDA)
            self.assertEqual(self.modulo.nombre_seccion_de(simbolo), "*IND*")

    def test_locales_no_se_exportan(self) -> None:
        self.assertEqual(
            [s.nombre for s in self.modulo.locales], ["trampa", "fin", "valores", "puntero"]
        )
        for simbolo in self.modulo.locales:
            self.assertFalse(simbolo.es_exportacion)
            self.assertFalse(simbolo.es_importacion)

    def test_referencias_de_cada_importacion(self) -> None:
        self.assertEqual(
            self.modulo.referencias("sumar"),
            [MarcaReubicacion(0, 0x15, REUB_ABS32, self.modulo.indice_simbolo("sumar"))],
        )
        self.assertEqual(
            [m.nombre_tipo for m in self.modulo.referencias("error")], ["REL16"]
        )


class TestMarcasDeReubicacion(unittest.TestCase):
    """Interpretacion de las marcas de reubicacion para la memoria."""

    def setUp(self) -> None:
        self.original = construir_modulo_principal()
        self.modulo = ModuloObjeto.deserializar(self.original.serializar())

    def test_marcas_interpretadas(self) -> None:
        self.assertEqual(self.modulo.reubicaciones, self.original.reubicaciones)
        resumen = [
            (self.modulo.secciones[m.seccion].nombre, m.offset, m.nombre_tipo, m.ancho,
             self.modulo.simbolos[m.simbolo].nombre, m.sumando)
            for m in self.modulo.reubicaciones
        ]
        self.assertEqual(resumen, [
            (".text", 0x02, "HI16", 2, "valores", 0),
            (".text", 0x0A, "LO16", 2, "valores", 0),
            (".text", 0x15, "ABS32", 4, "sumar", 0),
            (".text", 0x1D, "REL16", 2, "error", 0),
            (".text", 0x2C, "ABS32", 4, "fin", 0),
            (".data", 0x18, "ABS64", 8, "copia", 0),
        ])

    def test_marcas_por_seccion_ordenadas(self) -> None:
        self.assertEqual(
            [m.offset for m in self.modulo.marcas_de_seccion(".text")], [0x02, 0x0A, 0x15, 0x1D, 0x2C]
        )
        self.assertEqual(len(self.modulo.marcas_de_seccion(".bss")), 0)

    def test_campos_apuntan_a_la_instruccion_correcta(self) -> None:
        """Cada marca cae en el operando de la instruccion que debe parcharse."""
        codigo = self.modulo.seccion(".text").contenido
        for marca in self.modulo.marcas_de_seccion(".text"):
            with self.subTest(marca=marca):
                if marca.tipo in (REUB_HI16, REUB_LO16):
                    self.assertEqual(codigo[marca.offset - 2], 0x14)  # ADDI: imm16 en bytes 2-3
                elif marca.tipo == REUB_REL16:
                    self.assertIn(codigo[marca.offset - 1], range(0x41, 0x49))  # JZ..JNV
                else:
                    self.assertIn(codigo[marca.offset - 1], (0x40, 0x4A))  # JMP / CALL

    def test_nombre_de_tipo_desconocido(self) -> None:
        self.assertEqual(MarcaReubicacion(0, 0, 0x77, 0).nombre_tipo, "0x77")
        self.assertEqual(MarcaReubicacion(0, 0, 0x77, 0).ancho, 0)


class TestSerializacion(unittest.TestCase):
    """Ida y vuelta del formato, archivos en disco e informe legible."""

    def test_ida_y_vuelta(self) -> None:
        for construir in (construir_modulo_principal, construir_modulo_libmat, _modulo_duplicador):
            with self.subTest(modulo=construir.__name__):
                original = construir()
                datos = original.serializar()
                leido = ModuloObjeto.deserializar(datos)
                self.assertEqual(leido, original)
                self.assertEqual(leido.serializar(), datos)

    def test_nombres_utf8(self) -> None:
        modulo = ModuloObjeto(
            "módulo_ñ",
            [SeccionObjeto.texto(b"\x00")],
            [SimboloObjeto.exportado("cálculo", 0, 0)],
        )
        leido = ModuloObjeto.deserializar(modulo.serializar())
        self.assertEqual(leido.nombre, "módulo_ñ")
        self.assertEqual(leido.exportaciones[0].nombre, "cálculo")

    def test_desde_archivo_usa_el_nombre_del_archivo_si_falta(self) -> None:
        modulo = ModuloObjeto("", [SeccionObjeto.texto(b"\x00")])
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "anonimo.obj")
            modulo.guardar(ruta)
            self.assertEqual(analizar_objeto(ruta).nombre, "anonimo")

    def test_analizar_objeto_acepta_modulo_bytes_y_ruta(self) -> None:
        modulo = construir_modulo_libmat()
        self.assertIs(analizar_objeto(modulo), modulo)
        self.assertEqual(analizar_objeto(modulo.serializar()), modulo)
        self.assertEqual(analizar_objeto(bytearray(modulo.serializar())), modulo)

    def test_informe_textual(self) -> None:
        informe = ModuloObjeto.deserializar(construir_modulo_principal().serializar()).informe()
        for fragmento in (
            "Modulo objeto 'principal'", "Formato EOBJ v1", "Punto de entrada: .text+0x0000",
            "Encabezados de seccion", ".bss    VACIA  RESERVA", "Tabla de exportaciones (3)",
            "Tabla de importaciones (2)", ".text+0x0015 ABS32", "Simbolos locales (4)",
            "Marcas de reubicacion (6)", "IMPORTADO",
        ):
            self.assertIn(fragmento, informe)
        # Un modulo construido en memoria no tiene offsets de archivo que mostrar
        self.assertIn("(vacia)", construir_modulo_libmat().informe())

    def test_ejemplos_coinciden_con_el_ensamblador_oficial(self) -> None:
        self.assertEqual(ensamblar(FUENTE_PRINCIPAL, direccion_base=0), CODIGO_PRINCIPAL)
        self.assertEqual(ensamblar(FUENTE_LIBMAT, direccion_base=0), CODIGO_LIBMAT)


class TestObjetoInvalido(unittest.TestCase):
    """El analizador rechaza archivos corruptos con un mensaje que dice que fallo."""

    def setUp(self) -> None:
        self.datos = construir_modulo_principal().serializar()
        self.cab = ModuloObjeto.deserializar(self.datos).cabecera

    def _seccion(self, indice: int, campo: int) -> int:
        return self.cab.off_secciones + indice * TAM_SECCION + campo

    def _simbolo(self, indice: int, campo: int) -> int:
        return self.cab.off_simbolos + indice * TAM_SIMBOLO + campo

    def _marca(self, indice: int, campo: int) -> int:
        return self.cab.off_reubicaciones + indice * TAM_REUBICACION + campo

    def test_jerarquia_de_excepciones(self) -> None:
        self.assertTrue(issubclass(ObjetoInvalido, ErrorEnlazador))
        self.assertTrue(issubclass(ObjetoInvalido, FormatoInvalido))
        self.assertTrue(issubclass(ErrorEnlazador, ErrorCargador))
        for error in (SimboloNoDefinido, SimboloDuplicado, DesbordamientoReubicacion):
            self.assertTrue(issubclass(error, ErrorEnlazador))

    def test_archivos_corruptos(self) -> None:
        d = self.datos
        nombre_text = struct.unpack_from(">I", d, self._seccion(0, 0))[0]
        nombre_main = struct.unpack_from(">I", d, self._simbolo(0, 0))[0]
        casos = {
            "firma magica": b"ENIG" + d[4:],
            "version": _parchear(d, 4, ">H", 2),
            "maquina": _parchear(d, 6, ">H", 0x8086),
            "banderas desconocidas": _parchear(d, 8, ">H", 0x8001),
            "cabecera truncada": d[:TAM_CABECERA_OBJ - 1],
            "tabla de secciones fuera": _parchear(d, 20, ">I", 1000),
            "tabla de simbolos fuera": _parchear(d, 32, ">I", len(d)),
            "tabla de marcas fuera": _parchear(d, 36, ">I", 10 ** 6),
            "tabla de cadenas fuera": _parchear(d, 44, ">I", 10_000),
            "contenido de seccion fuera": _parchear(d, self._seccion(0, 12), ">I", 10_000),
            "nombre fuera de cadenas": _parchear(d, self._seccion(0, 0), ">I", 10_000),
            "nombre sin NUL": d[:-1] + b"X",
            "nombre no UTF-8": _parchear(d, self.cab.off_cadenas + 1, ">B", 0xFF),
            "tipo de seccion": _parchear(d, self._seccion(0, 4), ">H", 7),
            "VACIA con offset": _parchear(d, self._seccion(2, 16), ">I", 4),
            "alineacion no potencia de 2": _parchear(d, self._seccion(1, 8), ">I", 6),
            "alineacion cero": _parchear(d, self._seccion(1, 8), ">I", 0),
            "alineacion mayor que pagina": _parchear(d, self._seccion(1, 8), ">I", 8192),
            "permisos desconocidos": _parchear(d, self._seccion(0, 6), ">H", 0x10),
            "seccion duplicada": _parchear(d, self._seccion(1, 0), ">I", nombre_text),
            "simbolo en seccion inexistente": _parchear(d, self._simbolo(0, 4), ">H", 9),
            "simbolo fuera de su seccion": _parchear(d, self._simbolo(0, 8), ">I", 58),
            "importado LOCAL": _parchear(d, self._simbolo(7, 6), ">B", 0),
            "simbolo duplicado": _parchear(d, self._simbolo(1, 0), ">I", nombre_main),
            "ligadura desconocida": _parchear(d, self._simbolo(0, 6), ">B", 5),
            "tipo de simbolo desconocido": _parchear(d, self._simbolo(0, 7), ">B", 9),
            "marca en seccion inexistente": _parchear(d, self._marca(0, 0), ">H", 5),
            "marca en seccion VACIA": _parchear(d, self._marca(0, 0), ">H", 2),
            "campo fuera de la seccion": _parchear(d, self._marca(4, 4), ">I", 55),
            "tipo de marca desconocido": _parchear(d, self._marca(0, 2), ">B", 99),
            "byte reservado": _parchear(d, self._marca(0, 3), ">B", 1),
            "simbolo de marca inexistente": _parchear(d, self._marca(0, 8), ">I", 100),
            "marcas solapadas": _parchear(d, self._marca(1, 4), ">I", 0x03),
            "entrada fuera de la seccion": _parchear(d, 12, ">I", 57),
            "entrada en seccion inexistente": _parchear(d, 10, ">H", 9),
            "entrada en seccion no ejecutable": _parchear(d, 10, ">H", 1),
        }
        for descripcion, corrupto in casos.items():
            with self.subTest(caso=descripcion):
                with self.assertRaises(ObjetoInvalido):
                    ModuloObjeto.deserializar(corrupto)

    def test_modelo_incoherente_no_se_serializa(self) -> None:
        texto = SeccionObjeto.texto(b"\x00\x00\x00\x00")
        casos = {
            "seccion sin nombre": ModuloObjeto("m", [SeccionObjeto("", b"\x00")]),
            "nombre con NUL": ModuloObjeto("m", [texto], [SimboloObjeto.local("a\x00b", 0, 0)]),
            "BITS con reserva": ModuloObjeto("m", [SeccionObjeto(".x", b"\x00", tamano_reservado=4)]),
            "VACIA con contenido": ModuloObjeto(
                "m", [SeccionObjeto(".bss", b"\x00", tipo=SECCION_VACIA)]),
            "valor negativo": ModuloObjeto("m", [texto], [SimboloObjeto.local("a", 0, -1)]),
            "sumando de 33 bits": ModuloObjeto(
                "m", [texto], [SimboloObjeto.local("a", 0, 0)],
                [MarcaReubicacion(0, 0, REUB_ABS32, 0, 1 << 31)]),
            "seccion duplicada": ModuloObjeto("m", [texto, SeccionObjeto.texto(b"\x00")]),
        }
        for descripcion, modulo in casos.items():
            with self.subTest(caso=descripcion):
                with self.assertRaises(ObjetoInvalido):
                    modulo.serializar()


class TestCalculoDeParches(unittest.TestCase):
    """Formulas de cada tipo de marca y deteccion de desbordamientos."""

    def test_abs64_y_abs32(self) -> None:
        self.assertEqual(calcular_parche(REUB_ABS64, 0x00200048, 8, 0), (0x00200050).to_bytes(8, "big"))
        self.assertEqual(calcular_parche(REUB_ABS32, 0x00200039, 0, 0), bytes([0x00, 0x20, 0x00, 0x39]))
        self.assertEqual(calcular_parche(REUB_ABS32, 0xFFFFFFF0, 0xF, 0), b"\xFF\xFF\xFF\xFF")

    def test_rel16_se_mide_desde_la_instruccion_siguiente(self) -> None:
        campo = 0x0020001D  # JZ en 0x0020001C: la siguiente instruccion empieza en 0x0020001F
        self.assertEqual(calcular_parche(REUB_REL16, 0x0020003D, 0, campo), b"\x00\x1E")
        self.assertEqual(calcular_parche(REUB_REL16, campo + 2, 0, campo), b"\x00\x00")
        self.assertEqual(calcular_parche(REUB_REL16, campo + 2 + 0x7FFF, 0, campo), b"\x7F\xFF")
        self.assertEqual(calcular_parche(REUB_REL16, campo + 2 - 0x8000, 0, campo), b"\x80\x00")
        self.assertEqual(calcular_parche(REUB_REL16, campo - 8, 0, campo), b"\xFF\xF6")

    def test_hi16_lo16_reconstruyen_la_direccion_en_la_alu(self) -> None:
        """ADDI Rx,R0,hi / SHL Rx,Rx,16 / ADDI Rx,Rx,lo con la ALU oficial da la direccion."""
        alu = ALU()
        direcciones = [
            0x00000000, 0x00200000, 0x00201008, 0x00207FFF, 0x00208000, 0x0020FFFF,
            0x00348048, 0x12345678, 0x7FFF0000, LIMITE_HI16 - 1,
        ]
        for direccion in direcciones:
            with self.subTest(direccion=hex(direccion)):
                hi = int.from_bytes(calcular_parche(REUB_HI16, direccion, 0, 0), "big")
                lo = int.from_bytes(calcular_parche(REUB_LO16, direccion, 0, 0), "big")
                r = alu.ejecutar("ADDI", 0, _extender_signo_16(hi) & MASK64).valor
                r = alu.ejecutar("SHL", r, 16).valor
                r = alu.ejecutar("ADDI", r, _extender_signo_16(lo) & MASK64).valor
                self.assertEqual(r, direccion)

    def test_hi16_compensa_la_extension_de_signo(self) -> None:
        self.assertEqual(calcular_parche(REUB_HI16, 0x00201000, 0, 0), b"\x00\x20")
        self.assertEqual(calcular_parche(REUB_HI16, 0x00209000, 0, 0), b"\x00\x21")
        self.assertEqual(calcular_parche(REUB_LO16, 0x00209000, 0, 0), b"\x90\x00")

    def test_desbordamientos(self) -> None:
        casos = {
            "ABS64 de 65 bits": (REUB_ABS64, 1 << 64, 0, 0),
            "ABS64 negativo": (REUB_ABS64, 0, -1, 0),
            "ABS32 fuera de 4 GiB": (REUB_ABS32, 0xFFFFFFFF, 1, 0),
            "ABS32 negativo": (REUB_ABS32, 4, -8, 0),
            "REL16 adelante": (REUB_REL16, 0x1000 + 2 + 0x8000, 0, 0x1000),
            "REL16 atras": (REUB_REL16, 0x9000 + 2 - 0x8001, 0, 0x9000),
            "HI16 en el limite": (REUB_HI16, LIMITE_HI16, 0, 0),
            "HI16 negativo": (REUB_HI16, 0, -4, 0),
            "LO16 fuera de 4 GiB": (REUB_LO16, 1 << 32, 0, 0),
        }
        for descripcion, argumentos in casos.items():
            with self.subTest(caso=descripcion):
                with self.assertRaises(DesbordamientoReubicacion):
                    calcular_parche(*argumentos)

    def test_tipo_desconocido(self) -> None:
        with self.assertRaises(ErrorEnlazador):
            calcular_parche(0x77, 0, 0, 0)


class TestEnlazador(unittest.TestCase):
    """Asignacion de direcciones, ESTAB, resolucion de importaciones y reubicacion."""

    def setUp(self) -> None:
        self.principal = construir_modulo_principal()
        self.libmat = construir_modulo_libmat()
        self.resultado = EnlazadorEnigma([self.principal, self.libmat]).enlazar(BASE)
        self.imagen = bytes(self.resultado.binario.bytes_completos())

    def test_ubicacion_de_secciones(self) -> None:
        mapa = [(u.modulo, u.seccion, u.direccion, u.tamano) for u in self.resultado.mapa]
        self.assertEqual(mapa, [
            ("principal", ".text", 0x00200000, 57),
            ("libmat", ".text", 0x00200039, 13),   # codigo de todos los modulos primero
            ("principal", ".data", 0x00200048, 32),  # 0x00200046 alineado a 8
            ("principal", ".bss", 0x00200068, 16),   # reservas al final
        ])
        self.assertEqual(self.resultado.tamano_total, 120)

    def test_tabla_global_de_simbolos(self) -> None:
        self.assertEqual(self.resultado.simbolos, {
            "main": 0x00200000,
            "resultado": 0x00200058,
            "copia": 0x00200068,
            "sumar": 0x00200039,
            "error": 0x0020003D,
        })
        self.assertEqual(self.resultado.origen_simbolos["sumar"], "libmat")
        self.assertEqual(self.resultado.binario.tabla_simbolos, self.resultado.simbolos)

    def test_parches_aplicados_en_la_imagen(self) -> None:
        img = self.imagen
        self.assertEqual(img[0x02:0x04], b"\x00\x20")              # HI16(valores = 0x00200048)
        self.assertEqual(img[0x0A:0x0C], b"\x00\x48")              # LO16(valores)
        self.assertEqual(img[0x15:0x19], b"\x00\x20\x00\x39")      # CALL sumar
        self.assertEqual(img[0x1D:0x1F], b"\x00\x1E")              # JZ error: 0x3D - 0x1F
        self.assertEqual(img[0x2C:0x30], b"\x00\x20\x00\x38")      # JMP fin
        self.assertEqual(img[0x60:0x68], (0x00200068).to_bytes(8, "big"))  # puntero -> copia
        self.assertEqual(self.resultado.reubicaciones_aplicadas, 6)
        # Los opcodes y el resto de la imagen quedan intactos
        self.assertEqual((img[0x14], img[0x1C], img[0x2B]), (0x4A, 0x41, 0x40))
        self.assertEqual(img[0x39:0x46], CODIGO_LIBMAT)

    def test_reserva_bss_en_ceros_y_division_codigo_datos(self) -> None:
        binario = self.resultado.binario
        self.assertEqual(self.imagen[0x68:0x78], bytes(16))
        self.assertEqual(binario.tamano_codigo, 0x48)
        self.assertEqual(binario.tamano_datos, 48)
        self.assertFalse(binario.reubicable)
        self.assertEqual(binario.entry_point, 0x00200000)

    def test_enlazar_no_modifica_los_modulos(self) -> None:
        antes = (self.principal.serializar(), self.libmat.serializar())
        enlazador = EnlazadorEnigma([self.principal, self.libmat])
        otro = enlazador.enlazar(0x00400000)
        self.assertEqual((self.principal.serializar(), self.libmat.serializar()), antes)
        self.assertEqual(otro.simbolos["sumar"], 0x00400039)
        self.assertEqual(enlazador.enlazar(BASE).binario.bytes_completos(), self.imagen)

    def test_simbolo_duplicado(self) -> None:
        with self.assertRaises(SimboloDuplicado) as ctx:
            EnlazadorEnigma([self.principal, self.libmat, construir_modulo_libmat()]).enlazar()
        self.assertIn("'sumar'", str(ctx.exception))

    def test_importaciones_sin_resolver(self) -> None:
        with self.assertRaises(SimboloNoDefinido) as ctx:
            EnlazadorEnigma([self.principal]).enlazar()
        self.assertEqual(ctx.exception.faltantes, {"sumar": ["principal"], "error": ["principal"]})
        self.assertIn("'error' (importado por principal)", str(ctx.exception))

    def test_simbolo_absoluto_exportado(self) -> None:
        constantes = ModuloObjeto(
            "constantes", simbolos=[SimboloObjeto.exportado("TAM", SECCION_ABSOLUTA, 0x40)]
        )
        usuario = ModuloObjeto(
            "usuario",
            [SeccionObjeto.datos(bytes(8))],
            [SimboloObjeto.importado("TAM")],
            [MarcaReubicacion(0, 0, REUB_ABS64, 0)],
        )
        for base in (BASE, 0x00500000):
            resultado = EnlazadorEnigma([usuario, constantes]).enlazar(base)
            self.assertEqual(resultado.simbolos["TAM"], 0x40)
            self.assertEqual(resultado.binario.bytes_completos(), (0x40).to_bytes(8, "big"))

    def test_punto_de_entrada(self) -> None:
        modulos = [self.principal, self.libmat]
        self.assertEqual(EnlazadorEnigma(modulos).enlazar(BASE).entry_point, 0x00200000)
        self.assertEqual(EnlazadorEnigma(modulos).enlazar(BASE, "sumar").entry_point, 0x00200039)
        with self.assertRaises(SimboloNoDefinido):
            EnlazadorEnigma(modulos).enlazar(BASE, "no_existe")

        otra_entrada = construir_modulo_libmat()
        otra_entrada.entrada = (0, 0)
        with self.assertRaises(ErrorEnlazador):
            EnlazadorEnigma([self.principal, otra_entrada]).enlazar(BASE)

        # Sin declaracion arranca en el codigo, aunque el modulo liste antes sus datos
        datos_primero = ModuloObjeto(
            "datos_primero", [SeccionObjeto.datos(bytes(8)), SeccionObjeto.texto(b"\x00")]
        )
        resultado = EnlazadorEnigma([datos_primero]).enlazar(BASE)
        self.assertEqual(resultado.mapa[0].seccion, ".text")
        self.assertEqual(resultado.entry_point, BASE)

    def test_errores_de_configuracion(self) -> None:
        with self.assertRaises(ErrorEnlazador):
            EnlazadorEnigma().enlazar()
        with self.assertRaises(DireccionInvalida):
            EnlazadorEnigma([self.libmat]).enlazar(0x100000000)
        with self.assertRaises(DireccionInvalida):
            EnlazadorEnigma([self.libmat]).enlazar(-1)
        with self.assertRaises(DireccionInvalida):
            EnlazadorEnigma([self.principal, self.libmat]).enlazar(0xFFFFFFF0)

    def test_desbordamiento_informa_modulo_y_campo(self) -> None:
        # REL16 contra la constante 0: el salto quedaria a mas de 32 KiB
        lejano = ModuloObjeto(
            "lejano",
            [SeccionObjeto.texto(bytes([0x41, 0x00, 0x00]))],
            [SimboloObjeto.local("cero", SECCION_ABSOLUTA, 0)],
            [MarcaReubicacion(0, 1, REUB_REL16, 0)],
        )
        with self.assertRaises(DesbordamientoReubicacion) as ctx:
            EnlazadorEnigma([lejano]).enlazar(BASE)
        self.assertIn("Modulo 'lejano', REL16 en .text+0x1 contra 'cero'", str(ctx.exception))

        # Por encima de LIMITE_HI16 la secuencia ADDI/SHL/ADDI ya no construye la direccion
        with self.assertRaises(DesbordamientoReubicacion):
            EnlazadorEnigma([self.principal, self.libmat]).enlazar(LIMITE_HI16)

    def test_informe_de_enlace(self) -> None:
        informe = self.resultado.informe()
        self.assertIn("Mapa de enlace: base 0x00200000, 120 bytes, entrada 0x00200000", informe)
        self.assertIn("0x00200039  13      R-X   .text    libmat", informe)
        self.assertIn("0x0020003D  error      libmat", informe)
        self.assertIn("Marcas de reubicacion aplicadas: 6", informe)


class TestEnlaceCargaEjecucion(unittest.TestCase):
    """El programa enlazado corre en la CPU oficial donde sea que se cargue."""

    def _enlazar_cargar_ejecutar(self, fuentes, base):
        ram, banco = RAMMemory(), BancoRegistros()
        cargador = CargadorEnigma(ram=ram, banco=banco)
        metadatos = EnlazadorEnigma(fuentes).enlazar_y_cargar(cargador, base)
        cpu = CPU(ram=ram, banco=banco)
        return ram, metadatos, cpu

    def test_programa_enlazado_se_ejecuta_en_varias_bases(self) -> None:
        # 0x00348000 deja 'valores' en 0x00348048 (LO16 >= 0x8000 ejercita el ajuste
        # de HI16); 0x00340003 obliga a rellenar para alinear .data.
        for base in (0x00200000, 0x00348000, 0x00340003):
            with self.subTest(base=hex(base)):
                ram, meta, cpu = self._enlazar_cargar_ejecutar(
                    [construir_modulo_principal(), construir_modulo_libmat()], base
                )
                self.assertEqual(meta["entry_point"], base)
                self.assertEqual(meta["modulos"], ["principal", "libmat"])
                cpu.ejecutar(max_ciclos=10_000)
                simbolos = meta["simbolos"]
                self.assertTrue(cpu.detenido)
                self.assertEqual(_leer64(ram, simbolos["resultado"]), VALOR_A + VALOR_B)
                self.assertEqual(_leer64(ram, simbolos["copia"]), VALOR_A + VALOR_B)
                self.assertEqual(_leer64(ram, simbolos["resultado"] + 8), simbolos["copia"])
                # main + sumar sin pasar por la trampa: 15 instrucciones
                self.assertEqual(cpu.instrucciones, 15)

    def test_salto_rel16_entre_modulos(self) -> None:
        ram, meta, cpu = self._enlazar_cargar_ejecutar(
            [construir_modulo_principal(), construir_modulo_libmat()], 0x00300000
        )
        valores = meta["simbolos"]["resultado"] - 16
        ram.mem_write(valores, 0, 8)
        ram.mem_write(valores + 8, 0, 8)
        cpu.ejecutar(max_ciclos=10_000)
        self.assertEqual(_leer64(ram, meta["simbolos"]["resultado"]), CODIGO_ERROR)
        self.assertEqual(_leer64(ram, meta["simbolos"]["copia"]), 0)

    def test_cargar_archivo_obj_se_enlaza_automaticamente(self) -> None:
        ram, banco = RAMMemory(), BancoRegistros()
        cargador = CargadorEnigma(ram=ram, banco=banco)
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "duplicador.obj")
            _modulo_duplicador().guardar(ruta)
            meta = cargador.cargar_archivo(ruta, direccion_destino=0x00250000)
        self.assertEqual(meta["direccion_base"], 0x00250000)
        self.assertEqual(banco.pc, 0x00250000)
        self.assertEqual(meta["modulos"], ["duplicador"])
        CPU(ram=ram, banco=banco).ejecutar(max_ciclos=10_000)
        self.assertEqual(_leer64(ram, meta["simbolos"]["doble"]), 42)

    def test_cargar_archivo_obj_con_importaciones_se_rechaza(self) -> None:
        cargador = CargadorEnigma(ram=RAMMemory(), banco=BancoRegistros())
        with tempfile.TemporaryDirectory() as tmp:
            ruta = os.path.join(tmp, "principal.obj")
            construir_modulo_principal().guardar(ruta)
            with self.assertRaises(SimboloNoDefinido):
                cargador.cargar_archivo(ruta)

    def test_el_cargador_sigue_aplicando_el_mapa_de_memoria(self) -> None:
        cargador = CargadorEnigma(ram=RAMMemory(), banco=BancoRegistros())
        with self.assertRaises(ViolacionProteccionMemoria):
            EnlazadorEnigma([_modulo_duplicador()]).enlazar_y_cargar(cargador, 0x00100000)


class TestEnlaceConCodigoDelEquipo(unittest.TestCase):
    """
    Verificacion con codigo real del proyecto: el programa oficial de Euclides
    (Tarea 9) y la biblioteca FPU completa (Tarea 17) como modulos reubicables.
    """

    EXPORTACIONES_FPU = ("FADD", "FSUB", "FMUL", "FDIV", "FCMP", "FSQRT", "FPU_VECTORES")

    @classmethod
    def setUpClass(cls) -> None:
        codigo = ensamblar(CODIGO_FPU_ASM, direccion_base=0)
        offsets = _offsets_de_etiquetas(CODIGO_FPU_ASM, cls.EXPORTACIONES_FPU)
        cls.fpu = _modulo_desde_codigo_absoluto("fpu", codigo, 0, offsets)

    def test_euclides_oficial_reubicado(self) -> None:
        """Sin enlazador el binario solo funciona en 0x00200100; reubicado corre en cualquier base."""
        euclides = _modulo_desde_codigo_absoluto(
            "euclides", BYTES_EUCLIDES, 0x00200100, {"euclides": 0}
        )
        self.assertEqual([m.offset for m in euclides.reubicaciones], [0x21, 0x29])  # los dos JMP

        for reubicar in (True, False):
            with self.subTest(reubicado=reubicar):
                ram, banco = RAMMemory(), BancoRegistros()
                cargador = CargadorEnigma(ram=ram, banco=banco)
                if reubicar:
                    EnlazadorEnigma([euclides]).enlazar_y_cargar(cargador, 0x00400000)
                else:
                    cargador.cargar_bytes(BYTES_EUCLIDES, direccion_destino=0x00400000)
                ram.mem_write(0x00202000, 48, 8)
                ram.mem_write(0x00202008, 18, 8)
                CPU(ram=ram, banco=banco).ejecutar(max_ciclos=10_000)
                mcd = _leer64(ram, 0x00202010)
                # Sin reubicar, el JMP vuelve a 0x00200114 (RAM vacia = HLT) y no hay MCD
                self.assertEqual(mcd, 6 if reubicar else 0)

    def test_biblioteca_fpu_como_modulo_objeto(self) -> None:
        leido = ModuloObjeto.deserializar(self.fpu.serializar())
        self.assertEqual(leido, self.fpu)
        self.assertEqual(
            [s.nombre for s in leido.exportaciones], list(self.EXPORTACIONES_FPU)
        )
        self.assertEqual(len(leido.reubicaciones), 68)  # un ABS32 por cada JMP / CALL
        self.assertEqual({m.nombre_tipo for m in leido.reubicaciones}, {"ABS32"})

    def test_cliente_separado_llama_a_la_fpu_reubicada(self) -> None:
        """
        La FPU (68 marcas ABS32) enlazada en una base impar con un cliente que la
        importa da los mismos bits que el ensamblado monolitico de siempre.
        """
        a, b = 10.0, 3.0
        referencia = EmuladorFPUEnigma64()
        casos = [
            ("FADD", 0, "FADD", a + b),
            ("FSUB", 0, "FSUB", a - b),
            ("FMUL", 0, "FMUL", a * b),
            ("FDIV", 0, "FDIV", a / b),
            ("FSQRT", 0, "FSQRT", None),
            ("FPU_VECTORES", VECTOR_FMUL, "VEC_FMUL", a * b),  # importacion + sumando
            ("FPU_VECTORES", VECTOR_FDIV, "VEC_FDIV", a / b),
        ]
        for importado, sumando, etiqueta, esperado in casos:
            with self.subTest(rutina=etiqueta):
                ram, banco = RAMMemory(), BancoRegistros()
                meta = EnlazadorEnigma([_modulo_cliente_fpu(importado, sumando), self.fpu]) \
                    .enlazar_y_cargar(CargadorEnigma(ram=ram, banco=banco), 0x00A13457)
                resultado = meta["simbolos"]["resultado"]
                ram.mem_write(resultado - 16, float_a_ieee64(a), 8)
                ram.mem_write(resultado - 8, float_a_ieee64(b), 8)
                CPU(ram=ram, banco=banco).ejecutar(max_ciclos=500_000)

                bits = _leer64(ram, resultado)
                self.assertEqual(bits, referencia.ejecutar_vector(etiqueta, a, b))
                if esperado is not None:
                    self.assertEqual(ieee64_a_float(bits), esperado)


class TestLineaDeComandos(unittest.TestCase):
    """python -m enigma64.enlazador: analisis, enlace a .e64 y errores."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name
        self.principal = os.path.join(self.dir, "principal.obj")
        self.libmat = os.path.join(self.dir, "libmat.obj")
        construir_modulo_principal().guardar(self.principal)
        construir_modulo_libmat().guardar(self.libmat)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _ejecutar(self, *argumentos):
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = cli_enlazador(list(argumentos))
        return codigo, salida.getvalue(), errores.getvalue()

    def test_analisis(self) -> None:
        codigo, salida, _ = self._ejecutar(self.principal)
        self.assertEqual(codigo, 0)
        for fragmento in ("Encabezados de seccion", "Tabla de exportaciones",
                          "Tabla de importaciones", "Marcas de reubicacion", "IMPORTADO"):
            self.assertIn(fragmento, salida)

    def test_enlace_genera_un_e64_que_carga_y_ejecuta(self) -> None:
        salida_e64 = os.path.join(self.dir, "programa.e64")
        codigo, salida, _ = self._ejecutar(
            self.principal, self.libmat, "-o", salida_e64, "--base", "0x00300000",
            "--mapa", "--sin-informe",
        )
        self.assertEqual(codigo, 0)
        self.assertIn("Mapa de enlace: base 0x00300000", salida)
        self.assertNotIn("Encabezados de seccion", salida)

        with open(salida_e64, "rb") as f:
            binario = BinarioEnigma.deserializar_e64(f.read())
        self.assertEqual(binario.direccion_base, 0x00300000)
        self.assertEqual(binario.tabla_simbolos["sumar"], 0x00300039)

        ram, banco = RAMMemory(), BancoRegistros()
        CargadorEnigma(ram=ram, banco=banco).cargar_archivo(salida_e64)
        CPU(ram=ram, banco=banco).ejecutar(max_ciclos=10_000)
        self.assertEqual(_leer64(ram, binario.tabla_simbolos["resultado"]), 42)

    def test_errores_devuelven_codigo_1(self) -> None:
        codigo, _, errores = self._ejecutar(self.principal, "--mapa")
        self.assertEqual(codigo, 1)
        self.assertIn("SimboloNoDefinido", errores)
        self.assertIn("'sumar'", errores)

        codigo, _, errores = self._ejecutar(os.path.join(self.dir, "no_existe.obj"))
        self.assertEqual(codigo, 1)

        basura = os.path.join(self.dir, "basura.obj")
        with open(basura, "wb") as f:
            f.write(b"EOBJ" + bytes(10))
        codigo, _, errores = self._ejecutar(basura)
        self.assertEqual(codigo, 1)
        self.assertIn("ObjetoInvalido", errores)


if __name__ == "__main__":
    unittest.main()
