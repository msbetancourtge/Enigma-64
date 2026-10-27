"""
Pruebas exhaustivas para el módulo traductor de memoria (CacaoCore-64 -> Enigma-64).
"""

import pytest

from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory
from enigma64.registros import BancoRegistros
from spl.traductor.memoria import LexerMemoriaCacao, TraductorMemoria

# 1. Pruebas del Analizador Léxico PLY (LexerMemoriaCacao)

class TestLexerMemoriaCacao:
    """Valida la correcta tokenización de instrucciones de memoria CacaoCore."""

    @pytest.fixture
    def lexer(self):
        return LexerMemoriaCacao()

    @pytest.mark.parametrize("mnem,tipo_esperado", [
        ("movb", "MNEMONICO_BYTE"),
        ("MOVB", "MNEMONICO_BYTE"),
        ("loadb", "MNEMONICO_BYTE"),
        ("LOADB", "MNEMONICO_BYTE"),
        ("storeb", "MNEMONICO_BYTE"),
        ("STOREB", "MNEMONICO_BYTE"),
        ("movd", "MNEMONICO_PALABRA"),
        ("MOVD", "MNEMONICO_PALABRA"),
        ("movw", "MNEMONICO_PALABRA"),
        ("MOVW", "MNEMONICO_PALABRA"),
        ("movh", "MNEMONICO_PALABRA"),
        ("MOVH", "MNEMONICO_PALABRA"),
        ("loadd", "MNEMONICO_PALABRA"),
        ("LOADD", "MNEMONICO_PALABRA"),
        ("loadw", "MNEMONICO_PALABRA"),
        ("stored", "MNEMONICO_PALABRA"),
        ("STORED", "MNEMONICO_PALABRA"),
        ("storew", "MNEMONICO_PALABRA"),
        ("storeh", "MNEMONICO_PALABRA"),
        ("lea", "MNEMONICO_LEA"),
        ("LEA", "MNEMONICO_LEA"),
    ])
    def test_reconocimiento_mnemonicos(self, lexer, mnem, tipo_esperado):
        toks = lexer.tokenizar(mnem)
        assert len(toks) == 1
        assert toks[0].type == tipo_esperado
        assert toks[0].value == mnem.lower()

    @pytest.mark.parametrize("reg_str,nombre_esperado", [
        ("r0", "R0"),
        ("R0", "R0"),
        ("r7", "R7"),
        ("R10", "R10"),
        ("r15", "R15"),
        ("sp", "SP"),
        ("SP", "SP"),
        ("lr", "LR"),
        ("LR", "LR"),
        ("acm", "ACM"),
        ("ACC", "ACC"),
    ])
    def test_reconocimiento_registros(self, lexer, reg_str, nombre_esperado):
        toks = lexer.tokenizar(reg_str)
        assert len(toks) == 1
        assert toks[0].type == "REGISTRO"
        assert toks[0].value == nombre_esperado

    def test_tokenizar_direccion_hexadecimal(self, lexer):
        toks = lexer.tokenizar("0x00000177 0x00040000 0x1D36")
        assert len(toks) == 3
        assert [t.type for t in toks] == ["HEXADECIMAL", "HEXADECIMAL", "HEXADECIMAL"]
        assert [t.value for t in toks] == [0x177, 0x40000, 0x1D36]

    def test_tokenizar_acceso_indirecto_puntero(self, lexer):
        toks = lexer.tokenizar("[R4]")
        assert [t.type for t in toks] == ["CORCHETE_IZQ", "REGISTRO", "CORCHETE_DER"]
        assert toks[1].value == "R4"

    def test_tokenizar_puntero_con_offset(self, lexer):
        toks = lexer.tokenizar("[r4 + 8]")
        assert [t.type for t in toks] == [
            "CORCHETE_IZQ", "REGISTRO", "MAS", "DECIMAL", "CORCHETE_DER"
        ]
        assert toks[1].value == "R4"
        assert toks[3].value == 8

        toks_neg = lexer.tokenizar("[R6 - 16]")
        assert [t.type for t in toks_neg] == [
            "CORCHETE_IZQ", "REGISTRO", "MENOS", "DECIMAL", "CORCHETE_DER"
        ]
        assert toks_neg[3].value == 16

    def test_tokenizar_variable_y_etiqueta(self, lexer):
        toks = lexer.tokenizar("FIN: MOVW [temp], R1 # Comentario")
        assert [t.type for t in toks] == [
            "ID", "DOS_PUNTOS", "MNEMONICO_PALABRA",
            "CORCHETE_IZQ", "ID", "CORCHETE_DER",
            "COMA", "REGISTRO"
        ]
        assert toks[0].value == "FIN"
        assert toks[4].value == "temp"
        assert toks[7].value == "R1"


# 2. Pruebas Unitarias del Traductor de Memoria

class TestTraductorMemoriaUnidad:
    """Valida la generación de código y fórmulas de mapeo."""

    @pytest.fixture
    def traductor(self):
        return TraductorMemoria()

    def test_reubicacion_rango_usuario(self, traductor):
        # 0x00040000 es la base de datos estáticos en CacaoCore -> base_datos (0x00201000)
        assert traductor.mapear_direccion(0x00040000) == 0x00201000
        assert traductor.mapear_direccion(0x00040008) == 0x00201008
        # Direcciones menores a 0x00040000 se suman a base_datos
        assert traductor.mapear_direccion(0x00000177) == 0x00201170  # 0x177 & ~7 = 0x170
        # Direcciones ya en rango de usuario se preservan
        assert traductor.mapear_direccion(0x00205000) == 0x00205000

    def test_secuencia_direccion_con_ajuste_hi16(self, traductor):
        """
        Verifica la secuencia ADDI + SHL + ADDI y el ajuste de signo +0x8000 en HI16.
        """
        # Caso 1: LO16 < 0x8000 (sin carry por signo)
        # 0x00201000: HI16 = ((0x00201000 + 0x8000) >> 16) = 0x0020, LO16 = 0x1000
        secuencia = traductor.generar_secuencia_direccion("R7", 0x00201000)
        assert secuencia == [
            "ADDI R7, R0, 0x0020",
            "SHL R7, R7, 16",
            "ADDI R7, R7, 0x1000",
        ]

        # Caso 2: LO16 >= 0x8000 (carry en HI16 para compensar ADDI con signo negativo)
        # 0x00208100: HI16 = ((0x00208100 + 0x8000) >> 16) = 0x0021, LO16 = 0x8100
        # En la CPU: 0x0021 << 16 = 0x00210000, 0x8100 sign-extended = -0x7F00.
        # 0x00210000 - 0x7F00 = 0x00208100.
        secuencia_carry = traductor.generar_secuencia_direccion("R7", 0x00208100)
        assert secuencia_carry == [
            "ADDI R7, R0, 0x0021",
            "SHL R7, R7, 16",
            "ADDI R7, R7, 0x8100",
        ]

    @pytest.mark.parametrize("offset_in,offset_out", [
        (0, 0),
        (8, 8),
        (16, 16),
        (3, 0),    # desalineado redondeado hacia abajo
        (5, 0),
        (11, 8),
        (15, 8),
        (-8, -8),
        (-3, -8),
    ])
    def test_ajuste_offset_multiplo_8(self, traductor, offset_in, offset_out):
        assert traductor.ajustar_offset(offset_in, alinear=True) == offset_out

    def test_ajuste_offset_byte_sin_modificar(self, traductor):
        # En accesos de byte (LDB/STB), los offsets no se alteran
        assert traductor.ajustar_offset(3, alinear=False) == 3
        assert traductor.ajustar_offset(5, alinear=False) == 5

    def test_traducir_lectura_memoria_hexadecimal(self, traductor):
        lineas = traductor.traducir_linea("MOVD R1, 0x00000177")
        assert lineas == [
            "ADDI R7, R0, 0x0020",
            "SHL R7, R7, 16",
            "ADDI R7, R7, 0x1170",
            "LOAD R1, [R7]",
        ]

    def test_traducir_escritura_inmediato_en_memoria(self, traductor):
        lineas = traductor.traducir_linea("MOVD 0x00000177, 756")
        assert lineas == [
            "ADDI R7, R0, 0x0020",
            "SHL R7, R7, 16",
            "ADDI R7, R7, 0x1170",
            "ADDI R6, R0, 756",
            "STORE R6, [R7]",
        ]

    def test_traducir_variable_data(self, traductor):
        traductor.registrar_variable("temp", 0)
        lineas = traductor.traducir_linea("MOVW [temp], R1")
        assert lineas == [
            "ADDI R7, R0, 0x0020",
            "SHL R7, R7, 16",
            "ADDI R7, R7, 0x1000",
            "STORE R1, [R7]",
        ]

    def test_traducir_puntero_indirecto(self, traductor):
        assert traductor.traducir_linea("MOVH R6, [R4]") == ["LOAD R6, [R4]"]
        assert traductor.traducir_linea("MOVH [R6], R5") == ["STORE R5, [R6]"]
        assert traductor.traducir_linea("movd r5, [r4]") == ["LOAD R5, [R4]"]
        assert traductor.traducir_linea("movd [r4], r3") == ["STORE R3, [R4]"]

    def test_traducir_puntero_offset_alineado(self, traductor):
        assert traductor.traducir_linea("movd r5, [r4 + 8]") == ["LOAD R5, [R4 + 8]"]
        assert traductor.traducir_linea("movd [r4 + 16], r3") == ["STORE R3, [R4 + 16]"]

    def test_traducir_puntero_offset_desalineado(self, traductor):
        # Offset 3 se ajusta a 0
        assert traductor.traducir_linea("movd r5, [r4 + 3]") == ["LOAD R5, [R4]"]
        # Offset 11 se ajusta a 8
        assert traductor.traducir_linea("movd r5, [r4 + 11]") == ["LOAD R5, [R4 + 8]"]

    def test_traducir_byte_con_offset(self, traductor):
        assert traductor.traducir_linea("movb r1, [r2 + 3]") == ["LDB R1, [R2 + 3]"]
        assert traductor.traducir_linea("movb [r2 + 5], r1") == ["STB R1, [R2 + 5]"]

    def test_traducir_lea_variable(self, traductor):
        traductor.registrar_variable("temp", 0)
        lineas = traductor.traducir_linea("LEA R11, [temp]")
        # R11 mapeado por defecto a R4
        assert lineas == [
            "ADDI R4, R0, 0x0020",
            "SHL R4, R4, 16",
            "ADDI R4, R4, 0x1000",
        ]

    def test_traducir_lea_direccion(self, traductor):
        lineas = traductor.traducir_linea("LEA R5, 0x00040000")
        assert lineas == [
            "ADDI R5, R0, 0x0020",
            "SHL R5, R5, 16",
            "ADDI R5, R5, 0x1000",
        ]

    def test_lineas_no_memoria_se_preservan(self, traductor):
        assert traductor.traducir_linea("ADD R1, R2") == ["ADD R1, R2"]
        assert traductor.traducir_linea("CMP R0, R1") == ["CMP R0, R1"]
        assert traductor.traducir_linea("HLT") == ["HLT"]
        assert traductor.traducir_linea("LOOP:") == ["LOOP:"]
        assert traductor.traducir_linea("# Comentario") == ["# Comentario"]

    def test_configuracion_registro_temporal_y_base(self):
        traductor_cust = TraductorMemoria(
            reg_temporal="R3",
            base_datos=0x00250000,
            mapeo_registros={"R0": "R1", "R1": "R2"},
        )
        lineas = traductor_cust.traducir_linea("MOVD R0, 0x00000000")
        assert lineas == [
            "ADDI R3, R0, 0x0025",
            "SHL R3, R3, 16",
            "ADDI R3, R3, 0x0000",
            "LOAD R1, [R3]",
        ]

# 3. Pruebas de Ejecución Real en la CPU de Enigma-64

class TestEjecucionCPU:
    """Verifica la ejecución real en hardware emulado comprobando que M == 0."""

    def _ejecutar(self, lineas_asm: list[str]) -> tuple[CPU, RAMMemory, BancoRegistros]:
        codigo_fuente = "\n".join(lineas_asm)
        binario = ensamblar(codigo_fuente)

        ram = RAMMemory()
        banco = BancoRegistros()
        cpu = CPU(ram=ram, banco=banco)

        for i, b in enumerate(binario):
            ram.mem_write(0x00200000 + i, b, 1, check_alignment=False)

        banco.pc = 0x00200000
        cpu.ejecutar()
        return cpu, ram, banco

    def test_cpu_escribir_y_leer_palabra_sin_flag_m(self):
        """STORE y LOAD de 64 bits en dirección alineada; bandera M debe ser 0."""
        traductor = TraductorMemoria()
        asm = [
            # Cargar dirección base alineada en R1 (0x00201000)
            *traductor.generar_secuencia_direccion("R1", 0x00201000),
            "ADDI R2, R0, 0x4321",
            "STORE R2, [R1 + 8]",
            "LOAD R3, [R1 + 8]",
            "HLT",
        ]
        _, _, banco = self._ejecutar(asm)
        assert banco.leer_nombre("R3") == 0x4321
        assert banco.leer_bandera("M") == 0

    def test_cpu_escribir_y_leer_byte_sin_flag_m(self):
        """STB y LDB en cualquier byte; la bandera M debe ser 0."""
        traductor = TraductorMemoria()
        asm = [
            *traductor.generar_secuencia_direccion("R1", 0x00201000),
            "ADDI R2, R0, 0x7E",
            "STB R2, [R1 + 3]",
            "LDB R4, [R1 + 3]",
            "HLT",
        ]
        _, _, banco = self._ejecutar(asm)
        assert banco.leer_nombre("R4") == 0x7E
        assert banco.leer_bandera("M") == 0

    def test_cpu_puntero_offset_desalineado_ajustado(self):
        """
        Un offset de 3 en un acceso de 64 bits causaría STATUS_MISALIGNED y activaría M=1.
        El traductor ajusta 3 a 0 (múltiplo de 8), ejecutando limpiamente con M=0.
        """
        traductor = TraductorMemoria()
        # Se traduce una instrucción con offset 3
        traducidas_store = traductor.traducir_linea("movd [r4 + 3], r1")
        traducidas_load = traductor.traducir_linea("movd r2, [r4 + 3]")

        asm = [
            *traductor.generar_secuencia_direccion("R4", 0x00201000),
            "ADDI R1, R0, 9999",
            *traducidas_store,
            *traducidas_load,
            "HLT",
        ]
        _, _, banco = self._ejecutar(asm)
        assert banco.leer_nombre("R2") == 9999
        assert banco.leer_bandera("M") == 0

    def test_cpu_secuencia_direccion_con_lo16_negativo(self):
        """
        Verifica ejecución en CPU de una dirección donde LO16 >= 0x8000 (ej. 0x00208100).
        ADDI extiende el signo, por lo que HI16 compensa con +0x8000.
        """
        traductor = TraductorMemoria()
        dir_test = 0x00208100
        asm = [
            *traductor.generar_secuencia_direccion("R7", dir_test),
            "ADDI R1, R0, 0x1234",
            "STORE R1, [R7]",
            "LOAD R2, [R7]",
            "HLT",
        ]
        _, _, banco = self._ejecutar(asm)
        assert banco.leer_nombre("R7") == dir_test
        assert banco.leer_nombre("R2") == 0x1234
        assert banco.leer_bandera("M") == 0

# 4. Pruebas con Accesos Reales del Ensamblado de Euclides (CacaoCore)

class TestAccesosEuclides:
    """Valida los accesos a memoria reales presentes en alg_euc_res.asm y alg_euc_mod.asm."""

    def _ejecutar(self, lineas_asm: list[str]) -> tuple[CPU, RAMMemory, BancoRegistros]:
        codigo_fuente = "\n".join(lineas_asm)
        binario = ensamblar(codigo_fuente)

        ram = RAMMemory()
        banco = BancoRegistros()
        cpu = CPU(ram=ram, banco=banco)

        for i, b in enumerate(binario):
            ram.mem_write(0x00200000 + i, b, 1, check_alignment=False)

        banco.pc = 0x00200000
        cpu.ejecutar()
        return cpu, ram, banco

    def test_euclides_alg_euc_res_accesos_reales(self):
        """
        Accesos de memoria reales de alg_euc_res.asm:
          MOVD 0x00000177, 756
          MOVD 0x000005FF, 924
          MOVD R0, 0x00000177
          MOVD R1, 0x000005FF
          MOVD 0x00001D36, R1
          MOVW [temp], R1
          LEA R11, [temp]
        """
        # Usamos mapeo de registros para adaptar R0 y R11 a Enigma
        traductor = TraductorMemoria(
            mapeo_registros={"R0": "R1", "R1": "R2", "R11": "R4"}
        )

        instrucciones_cacao = [
            "MOVD 0x00000177, 756",
            "MOVD 0x000005FF, 924",
            "MOVD R0, 0x00000177",
            "MOVD R1, 0x000005FF",
            "MOVD 0x00001D36, R1",
            "MOVW [temp], R1",
            "LEA R11, [temp]",
        ]

        asm_enigma = []
        for l in instrucciones_cacao:
            asm_enigma.extend(traductor.traducir_linea(l))
        asm_enigma.append("HLT")

        _, ram, banco = self._ejecutar(asm_enigma)

        # R1 (antes R0) debe tener 756
        assert banco.leer_nombre("R1") == 756
        # R2 (antes R1) debe tener 924
        assert banco.leer_nombre("R2") == 924
        # R4 (antes R11) debe tener la dirección de temp
        dir_temp = traductor.obtener_direccion_variable("temp")
        assert banco.leer_nombre("R4") == dir_temp

        # La variable temp en RAM debe contener 924
        val_temp, status = ram.mem_read(dir_temp, 8, check_alignment=True)
        assert status == "READY"
        assert val_temp == 924

        # Dirección 0x1D36 (alineada a 0x1D30) debe contener 924
        dir_res = traductor.mapear_direccion(0x1D36)
        val_res, status_res = ram.mem_read(dir_res, 8, check_alignment=True)
        assert status_res == "READY"
        assert val_res == 924

        # Bandera M debe ser 0
        assert banco.leer_bandera("M") == 0

    def test_euclides_alg_euc_mod_traducir_programa(self):
        """
        Programa de prueba con la estructura completa de variables de alg_euc_mod.asm:
          .data
              a: 987654
              b: 123456
              temp: 0
          .text
              MOVD R0, [a]
              MOVD R1, [b]
              MOVW [temp], R1
              LEA R11, [temp]
        """
        programa_cacao = """
.data
    a: 987654
    b: 123456
    temp: 0
.text
    MOVD R0, [a]
    MOVD R1, [b]
    MOVW [temp], R1
    LEA R11, [temp]
    HLT
"""
        traductor = TraductorMemoria(
            mapeo_registros={"R0": "R1", "R1": "R2", "R11": "R4"}
        )
        programa_traducido = traductor.traducir_programa(programa_cacao)

        # En la primera pasada de traducción, se asignaron variables
        dir_a = traductor.obtener_direccion_variable("a")
        dir_b = traductor.obtener_direccion_variable("b")
        dir_temp = traductor.obtener_direccion_variable("temp")

        assert dir_a == 0x00201000
        assert dir_b == 0x00201008
        assert dir_temp == 0x00201010

        # Para ejecutarlo en Enigma-64, inicializamos los datos en RAM antes del código
        # y filtramos las líneas .data/.text para ensamblar el bloque ejecutable
        lineas_codigo = [
            l for l in programa_traducido.splitlines()
            if not l.strip().startswith((".data", ".text", "a:", "b:", "temp:"))
        ]

        codigo_fuente = "\n".join(lineas_codigo)
        binario = ensamblar(codigo_fuente)

        ram = RAMMemory()
        banco = BancoRegistros()
        cpu = CPU(ram=ram, banco=banco)

        # Escribir valores iniciales de a y b en RAM
        ram.mem_write(dir_a, 987654, 8, check_alignment=True)
        ram.mem_write(dir_b, 123456, 8, check_alignment=True)

        for i, b in enumerate(binario):
            ram.mem_write(0x00200000 + i, b, 1, check_alignment=False)

        banco.pc = 0x00200000
        cpu.ejecutar()

        assert banco.leer_nombre("R1") == 987654
        assert banco.leer_nombre("R2") == 123456
        assert banco.leer_nombre("R4") == dir_temp

        val_temp, status = ram.mem_read(dir_temp, 8, check_alignment=True)
        assert status == "READY"
        assert val_temp == 123456
        assert banco.leer_bandera("M") == 0
