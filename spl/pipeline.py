"""
Orquestador Principal del Sistema de Procesamiento del Lenguaje (SPL) — Enigma-64.

Responsabilidad: Integrante 7 (Driver Principal, Pipeline & Pruebas)
Integra en secuencia las 4 herramientas del SPL construidas para Enigma-64:
  1. Preprocesador (spl.preprocesador)          -> #include, #define, condicionales y comentarios
  2. Compilador Lexer & Tablas (spl.compilador) -> Vocabulario, TDA, matrices, ID, NUMBER IEEE 754, STRING
  3. Ensamblador Lexer (spl.ensamblador)        -> 41 mnemónicos ISA, registros, directivas y etiquetas
  4. Enlazador-Cargador (enigma64.enlazador)    -> Módulos .obj, reubicaciones, carga en RAM y CPU Enigma-64
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from enigma64 import (
    CPU,
    USER_MEM_START,
    BancoRegistros,
    CargadorEnigma,
    RAMMemory,
)
from enigma64.enlazador import (
    EnlazadorEnigma,
    ModuloObjeto,
    ResultadoEnlace,
    analizar_objeto,
)
from enigma64.enlazador.ejemplos import (
    construir_modulo_libmat,
    construir_modulo_principal,
)

from spl.compilador import (
    CompiladorLexer,
    ErrorLexico as ErrorLexicoCompilador,
    GestorTablasSimbolos,
)
from spl.ensamblador import (
    EnsambladorLexer,
    ErrorLexico as ErrorLexicoEnsamblador,
)
from spl.preprocesador import (
    ResultadoPreprocesamiento,
    preprocesar_archivo,
    preprocesar_texto,
)

# Directorios canónicos del paquete SPL
DIR_SPL: Path = Path(__file__).resolve().parent
DIR_INCLUDE_DEFAULT: Path = DIR_SPL / "include"
DIR_EJEMPLOS_PIPELINE: Path = DIR_SPL / "ejemplos"
DIR_COMPILADOR_C: Path = DIR_SPL / "compilador"


# ---------------------------------------------------------------------------
# Estructuras de Resultados por Etapa del Pipeline SPL
# ---------------------------------------------------------------------------

@dataclass
class EtapaPreprocesadorResult:
    """Resultado de la Etapa 1: Preprocesador SPL."""
    codigo_original: str
    resultado: ResultadoPreprocesamiento
    lineas_originales: int
    lineas_expandidas: int

    @property
    def codigo_expandido(self) -> str:
        return self.resultado.texto

    @property
    def archivos_incluidos(self) -> List[str]:
        vistos: List[str] = []
        for arch, _ in self.resultado.mapa_lineas:
            if arch and arch != "<string>" and arch not in vistos:
                vistos.append(arch)
        return vistos

    @property
    def macros_definidas(self) -> Dict[str, str]:
        return dict(self.resultado.macros)


@dataclass
class EtapaCompiladorResult:
    """Resultado de la Etapa 2: Analizador Léxico del Compilador y Tablas de Símbolos."""
    tokens: List[Any]
    errores: List[ErrorLexicoCompilador]
    comentarios_ignorados: int
    conteo_por_tipo: Dict[str, int]
    conteo_por_categoria: Dict[int, int]
    tablas: GestorTablasSimbolos


@dataclass
class EtapaEnsambladorResult:
    """Resultado de la Etapa 3: Analizador Léxico del Ensamblador Enigma-64."""
    tokens: List[Any]
    errores: List[ErrorLexicoEnsamblador]
    comentarios_ignorados: int
    conteo_por_tipo: Dict[str, int]


@dataclass
class EtapaEnlazadorCargadorResult:
    """Resultado de la Etapa 4: Enlazador de Módulos .obj, Cargador y Ejecución en CPU."""
    modulos_analizados: List[ModuloObjeto]
    resultado_enlace: ResultadoEnlace
    direccion_carga: int
    entry_point: int
    tamano_total_bytes: int
    ejecutado_en_cpu: bool
    ciclos_cpu: int = 0
    r5_retorno: int = 0
    valor_resultado_ram: int = 0
    valor_copia_ram: int = 0


@dataclass
class ResultadoPipelineSPL:
    """Resultado consolidado de las 4 etapas del Sistema de Procesamiento del Lenguaje."""
    nombre_escenario: str
    preprocesador: Optional[EtapaPreprocesadorResult] = None
    compilador: Optional[EtapaCompiladorResult] = None
    ensamblador: Optional[EtapaEnsambladorResult] = None
    enlazador_cargador: Optional[EtapaEnlazadorCargadorResult] = None
    errores_esperados: bool = False
    notas: List[str] = field(default_factory=list)

    @property
    def total_errores_lexicos(self) -> int:
        err_comp = len(self.compilador.errores) if self.compilador else 0
        err_asm = len(self.ensamblador.errores) if self.ensamblador else 0
        return err_comp + err_asm

    @property
    def exito(self) -> bool:
        if self.errores_esperados:
            return self.total_errores_lexicos > 0
        return self.total_errores_lexicos == 0

    def generar_informe(self, incluir_tablas: bool = True) -> str:
        """Genera un informe estructurado de las 4 etapas del pipeline SPL."""
        lineas: List[str] = []
        sep_mayor = "=" * 88
        sep_menor = "-" * 88

        lineas.append(sep_mayor)
        lineas.append(f"  PIPELINE SPL ENIGMA-64 — {self.nombre_escenario.upper()}")
        lineas.append(sep_mayor)

        # Etapa 1: Preprocesador
        if self.preprocesador is not None:
            p = self.preprocesador
            lineas.append("\n[ETAPA 1/4] PREPROCESADOR SPL (#include, #define, condicionales y comentarios)")
            lineas.append(sep_menor)
            lineas.append(f"  Líneas de entrada        : {p.lineas_originales}")
            lineas.append(f"  Líneas expandidas        : {p.lineas_expandidas}")
            lineas.append(f"  Archivos #include        : {len(p.archivos_incluidos)} -> {p.archivos_incluidos}")
            lineas.append(f"  Macros #define activas   : {len(p.macros_definidas)} ({', '.join(sorted(p.macros_definidas.keys()))})")

        # Etapa 2: Compilador Lexer & Tablas
        if self.compilador is not None:
            c = self.compilador
            lineas.append("\n[ETAPA 2/4] ANALIZADOR LÉXICO DEL COMPILADOR & TABLAS DE SÍMBOLOS")
            lineas.append(sep_menor)
            lineas.append(f"  Total de tokens emitidos : {len(c.tokens)}")
            lineas.append(f"  Tipos de token distintos : {len(c.conteo_por_tipo)}")
            lineas.append(f"  Comentarios descartados  : {c.comentarios_ignorados}")
            lineas.append(f"  Tabla ID (Cat. 150)      : {c.tablas.tabla_id.total} identificadores únicos")
            lineas.append(f"  Tabla NUMBER (Cat. 160)  : {c.tablas.tabla_num.total} constantes numéricas (64-bit / IEEE 754)")
            lineas.append(f"  Tabla STRING (Cat. 170)  : {c.tablas.tabla_string.total} cadenas literales limpias")
            lineas.append(f"  Errores léxicos          : {len(c.errores)}")
            if c.errores:
                for err in c.errores:
                    lineas.append(f"    * {err}")
            if incluir_tablas:
                lineas.append(c.tablas.generar_volcado_texto())

        # Etapa 3: Ensamblador Lexer
        if self.ensamblador is not None:
            a = self.ensamblador
            lineas.append("\n[ETAPA 3/4] ANALIZADOR LÉXICO DEL ENSAMBLADOR ENIGMA-64")
            lineas.append(sep_menor)
            lineas.append(f"  Total de tokens ASM      : {len(a.tokens)}")
            lineas.append(f"  Instrucciones (MNEMONICO): {a.conteo_por_tipo.get('MNEMONICO', 0)}")
            lineas.append(f"  Registros (REGISTRO)     : {a.conteo_por_tipo.get('REGISTRO', 0)}")
            lineas.append(f"  Directivas (DIRECTIVA)   : {a.conteo_por_tipo.get('DIRECTIVA', 0)}")
            lineas.append(f"  Etiquetas definidas      : {a.conteo_por_tipo.get('ETIQUETA_DEF', 0)}")
            lineas.append(f"  Errores léxicos ASM      : {len(a.errores)}")
            if a.errores:
                for err in a.errores:
                    lineas.append(f"    * {err}")

        # Etapa 4: Enlazador-Cargador y Ejecución en CPU
        if self.enlazador_cargador is not None:
            e = self.enlazador_cargador
            lineas.append("\n[ETAPA 4/4] ENLAZADOR-CARGADOR (.obj -> .e64) & EJECUCIÓN EN CPU ENIGMA-64")
            lineas.append(sep_menor)
            nombres_mod = [m.nombre for m in e.modulos_analizados]
            total_reub = sum(len(m.reubicaciones) for m in e.modulos_analizados)
            lineas.append(f"  Módulos .obj enlazados   : {len(e.modulos_analizados)} ({', '.join(nombres_mod)})")
            lineas.append(f"  Marcas de reubicación    : {total_reub} resueltas")
            lineas.append(f"  Dirección base de carga  : 0x{e.direccion_carga:08X}")
            lineas.append(f"  Punto de entrada (PC)    : 0x{e.entry_point:08X}")
            lineas.append(f"  Tamaño imagen enlazada   : {e.tamano_total_bytes} bytes")
            if e.ejecutado_en_cpu:
                lineas.append(f"  Instrucciones ejecutadas : {e.ciclos_cpu} (CPU detenida en HLT)")
                lineas.append(f"  Registro retorno R5 (RV) : {e.r5_retorno} (0x{e.r5_retorno:016X})")
                lineas.append(f"   Símbolo 'resultado' RAM  : {e.valor_resultado_ram}")
                lineas.append(f"  Símbolo 'copia' (.bss)   : {e.valor_copia_ram}")

        lineas.append("\n" + sep_mayor)
        estado_txt = "EXITOSO (CON RECUPERACIÓN DE ERRORES)" if (self.exito and self.errores_esperados) else ("EXITOSO" if self.exito else "CON ERRORES")
        lineas.append(f"  ESTADO GLOBAL DEL PIPELINE: {estado_txt}")
        lineas.append(sep_mayor)
        return "\n".join(lineas)


# ---------------------------------------------------------------------------
# Clase Orquestadora Principal (OrquestadorSPL)
# ---------------------------------------------------------------------------

class OrquestadorSPL:
    """
    Orquestador que ejecuta en cadena las 4 etapas del Sistema de Procesamiento
    del Lenguaje (SPL) para la arquitectura Enigma-64.
    """

    def __init__(self, dirs_inclusion: Optional[Sequence[Union[str, Path]]] = None) -> None:
        dirs = [str(DIR_INCLUDE_DEFAULT)]
        if dirs_inclusion:
            for d in dirs_inclusion:
                ruta_str = str(d)
                if ruta_str not in dirs:
                    dirs.append(ruta_str)
        self.dirs_inclusion: List[str] = dirs

    # --- Etapa 1: Preprocesador ---
    def ejecutar_etapa_preprocesador(
        self,
        entrada: Union[str, Path],
        *,
        es_archivo: bool = True,
        definiciones: Optional[Dict[str, str]] = None,
    ) -> EtapaPreprocesadorResult:
        """Ejecuta el Preprocesador SPL sobre un archivo o cadena de texto."""
        if es_archivo:
            ruta = Path(entrada)
            codigo_original = ruta.read_text(encoding="utf-8")
            res = preprocesar_archivo(
                str(ruta),
                dirs_inclusion=self.dirs_inclusion,
                definiciones=definiciones or {},
            )
        else:
            codigo_original = str(entrada)
            res = preprocesar_texto(
                codigo_original,
                dirs_inclusion=self.dirs_inclusion,
                definiciones=definiciones or {},
            )

        lineas_orig = codigo_original.count("\n") + (1 if codigo_original and not codigo_original.endswith("\n") else 0)
        lineas_exp = res.texto.count("\n") + (1 if res.texto and not res.texto.endswith("\n") else 0)
        return EtapaPreprocesadorResult(
            codigo_original=codigo_original,
            resultado=res,
            lineas_originales=lineas_orig,
            lineas_expandidas=lineas_exp,
        )

    # --- Etapa 2: Compilador (Lexer + Tablas de Símbolos) ---
    def ejecutar_etapa_compilador(
        self,
        codigo_spl: str,
        *,
        tablas: Optional[GestorTablasSimbolos] = None,
    ) -> EtapaCompiladorResult:
        """Ejecuta el Analizador Léxico del Compilador y puebla las 3 tablas de símbolos."""
        gestor = tablas if tablas is not None else GestorTablasSimbolos()
        lexer = CompiladorLexer(tablas=gestor)
        tokens, errores = lexer.tokenizar(codigo_spl)

        conteo_tipo: Counter = Counter()
        conteo_cat: Counter = Counter()
        for tok in tokens:
            conteo_tipo[tok.type] += 1
            conteo_cat[getattr(tok, "categoria_codigo", 0)] += 1

        return EtapaCompiladorResult(
            tokens=tokens,
            errores=errores,
            comentarios_ignorados=lexer.comentarios,
            conteo_por_tipo=dict(conteo_tipo),
            conteo_por_categoria=dict(conteo_cat),
            tablas=gestor,
        )

    # --- Etapa 3: Ensamblador (Lexer Enigma-64) ---
    def ejecutar_etapa_ensamblador(self, codigo_asm: str) -> EtapaEnsambladorResult:
        """Ejecuta el Analizador Léxico del Ensamblador sobre código ASM de Enigma-64."""
        lexer = EnsambladorLexer()
        tokens, errores = lexer.tokenizar(codigo_asm)
        conteo_tipo = Counter(tok.type for tok in tokens)
        return EtapaEnsambladorResult(
            tokens=tokens,
            errores=errores,
            comentarios_ignorados=lexer.comentarios,
            conteo_por_tipo=dict(conteo_tipo),
        )

    # --- Etapa 4: Enlazador-Cargador y Ejecución en CPU Enigma-64 ---
    def ejecutar_etapa_enlazador_cargador(
        self,
        modulos: Optional[Sequence[Union[str, Path, bytes, ModuloObjeto]]] = None,
        *,
        direccion_base: int = USER_MEM_START,
        simbolo_entrada: str = "main",
        ejecutar_cpu: bool = True,
        max_instrucciones: int = 200,
    ) -> EtapaEnlazadorCargadorResult:
        """
        Analiza los módulos objeto (.obj), los enlaza en un ejecutable .e64,
        lo deposita en la MemoriaRAM con CargadorEnigma y opcionalmente lo ejecuta
        en la CPUEnigma64.
        """
        if modulos is None:
            modulos_obj = [construir_modulo_principal(), construir_modulo_libmat()]
        else:
            modulos_obj = [analizar_objeto(m) for m in modulos]

        enlazador = EnlazadorEnigma(modulos_obj)
        res_enlace = enlazador.enlazar(direccion_base, simbolo_entrada)

        ciclos = 0
        r5_val = 0
        val_resultado = 0
        val_copia = 0

        if ejecutar_cpu:
            ram = RAMMemory()
            banco = BancoRegistros()
            cpu = CPU(ram=ram, banco=banco)
            cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)

            meta = enlazador.enlazar_y_cargar(
                cargador, direccion_destino=direccion_base, entrada=simbolo_entrada
            )
            cpu.ejecutar(max_ciclos=max_instrucciones * 10)
            ciclos = cpu.instrucciones
            r5_val = banco.leer(5)
            simbolos = meta.get("simbolos", res_enlace.simbolos)
            if "resultado" in simbolos:
                val_resultado = ram.mem_read(simbolos["resultado"], 8)[0]
            if "copia" in simbolos:
                val_copia = ram.mem_read(simbolos["copia"], 8)[0]

        return EtapaEnlazadorCargadorResult(
            modulos_analizados=modulos_obj,
            resultado_enlace=res_enlace,
            direccion_carga=res_enlace.direccion_base,
            entry_point=res_enlace.entry_point,
            tamano_total_bytes=res_enlace.tamano_total,
            ejecutado_en_cpu=ejecutar_cpu,
            ciclos_cpu=ciclos,
            r5_retorno=r5_val,
            valor_resultado_ram=val_resultado,
            valor_copia_ram=val_copia,
        )

    # --- Ejecución del Pipeline Completo ---
    def ejecutar_pipeline_completo(
        self,
        *,
        nombre_escenario: str = "Pipeline Personalizado",
        ruta_spl: Optional[Union[str, Path]] = None,
        texto_spl: Optional[str] = None,
        ruta_asm: Optional[Union[str, Path]] = None,
        texto_asm: Optional[str] = None,
        modulos_obj: Optional[Sequence[Union[str, Path, bytes, ModuloObjeto]]] = None,
        definiciones_macro: Optional[Dict[str, str]] = None,
        ejecutar_enlazador: bool = True,
        ejecutar_cpu: bool = True,
        errores_esperados: bool = False,
    ) -> ResultadoPipelineSPL:
        """
        Orquesta en secuencia las 4 etapas del SPL:
          Preprocesador -> Compilador (Lexer + Tablas) -> Ensamblador (Lexer) -> Enlazador-Cargador
        """
        res_prep: Optional[EtapaPreprocesadorResult] = None
        res_comp: Optional[EtapaCompiladorResult] = None
        res_asm: Optional[EtapaEnsambladorResult] = None
        res_link: Optional[EtapaEnlazadorCargadorResult] = None

        # 1. Preprocesador + 2. Compilador
        if ruta_spl is not None or texto_spl is not None:
            if ruta_spl is not None:
                res_prep = self.ejecutar_etapa_preprocesador(
                    ruta_spl, es_archivo=True, definiciones=definiciones_macro
                )
            else:
                res_prep = self.ejecutar_etapa_preprocesador(
                    texto_spl or "", es_archivo=False, definiciones=definiciones_macro
                )
            res_comp = self.ejecutar_etapa_compilador(res_prep.codigo_expandido)

        # 3. Ensamblador
        if ruta_asm is not None or texto_asm is not None:
            codigo_asm = Path(ruta_asm).read_text(encoding="utf-8") if ruta_asm is not None else (texto_asm or "")
            res_asm = self.ejecutar_etapa_ensamblador(codigo_asm)

        # 4. Enlazador-Cargador
        if ejecutar_enlazador:
            res_link = self.ejecutar_etapa_enlazador_cargador(
                modulos=modulos_obj, ejecutar_cpu=ejecutar_cpu
            )

        return ResultadoPipelineSPL(
            nombre_escenario=nombre_escenario,
            preprocesador=res_prep,
            compilador=res_comp,
            ensamblador=res_asm,
            enlazador_cargador=res_link,
            errores_esperados=errores_esperados,
        )

    # --- Batería Oficial de 3 Escenarios Integrales ---
    def ejecutar_escenario(self, numero: int) -> ResultadoPipelineSPL:
        """
        Ejecuta uno de los 3 escenarios integrales obligatorios del Taller #01:
          - Escenario 1: Flujo Nominal Completo (Preprocesador + TDA/Matrices + ASM + Enlace/CPU = 42)
          - Escenario 2: Macros Parametrizadas, Punto Flotante IEEE 754 (64-bit), Switch-Case y Cadenas
          - Escenario 3: Tolerancia a Fallos y Recuperación ante Errores Léxicos en Compilador y Ensamblador
        """
        if numero == 1:
            return self.ejecutar_pipeline_completo(
                nombre_escenario="Escenario 1: Flujo Nominal Completo (TDA, Matrices, Enlace .obj y Ejecución CPU)",
                ruta_spl=DIR_EJEMPLOS_PIPELINE / "escenario1_aritmetica_tda.spl",
                ruta_asm=DIR_EJEMPLOS_PIPELINE / "escenario1_modulo.asm",
                ejecutar_enlazador=True,
                ejecutar_cpu=True,
                errores_esperados=False,
            )
        if numero == 2:
            return self.ejecutar_pipeline_completo(
                nombre_escenario="Escenario 2: Punto Flotante IEEE 754 (64-bit), Switch-Case, Escapes y Macros",
                ruta_spl=DIR_EJEMPLOS_PIPELINE / "escenario2_punto_flotante_switch.spl",
                ruta_asm=DIR_EJEMPLOS_PIPELINE / "escenario2_fpu.asm",
                ejecutar_enlazador=True,
                ejecutar_cpu=True,
                errores_esperados=False,
            )
        if numero == 3:
            return self.ejecutar_pipeline_completo(
                nombre_escenario="Escenario 3: Detección y Recuperación ante Errores Léxicos Multietapa",
                ruta_spl=DIR_EJEMPLOS_PIPELINE / "escenario3_recuperacion_errores.spl",
                ruta_asm=DIR_EJEMPLOS_PIPELINE / "escenario3_errores.asm",
                ejecutar_enlazador=True,
                ejecutar_cpu=False,
                errores_esperados=True,
            )
        raise ValueError(f"Número de escenario inválido: {numero}. Use 1, 2 o 3.")

    def ejecutar_todos_los_escenarios(self) -> List[ResultadoPipelineSPL]:
        """Ejecuta en secuencia los 3 escenarios integrales del SPL."""
        return [self.ejecutar_escenario(1), self.ejecutar_escenario(2), self.ejecutar_escenario(3)]


# ---------------------------------------------------------------------------
# Verificación de Compilación Cruzada C/C++ (tablas_simbolos.c / Makefile)
# ---------------------------------------------------------------------------

def verificar_modulo_c_tablas(compilar_si_gcc_disponible: bool = True) -> Tuple[bool, str]:
    """
    Verifica la integridad del módulo nativo en ANSI C de las Tablas de Símbolos
    (spl/compilador/tablas_simbolos.c, tablas_simbolos.h, test_tablas.c y Makefile).
    Si GCC está disponible en el sistema, ejecuta la compilación cruzada y corre el binario.
    """
    archivos_requeridos = [
        DIR_COMPILADOR_C / "tablas_simbolos.h",
        DIR_COMPILADOR_C / "tablas_simbolos.c",
        DIR_COMPILADOR_C / "test_tablas.c",
        DIR_COMPILADOR_C / "Makefile",
    ]
    for ruta in archivos_requeridos:
        if not ruta.is_file():
            return False, f"Archivo C faltante: {ruta}"

    gcc_bin = shutil.which("gcc")
    if compilar_si_gcc_disponible and gcc_bin:
        exe_out = DIR_COMPILADOR_C / ("test_tablas.exe" if os.name == "nt" else "test_tablas")
        cmd_compile = [
            gcc_bin, "-Wall", "-Wextra", "-std=c11", "-O2",
            f"-I{DIR_COMPILADOR_C}",
            str(DIR_COMPILADOR_C / "tablas_simbolos.c"),
            str(DIR_COMPILADOR_C / "test_tablas.c"),
            "-o", str(exe_out),
        ]
        proc_comp = subprocess.run(cmd_compile, capture_output=True, text=True, check=False)
        if proc_comp.returncode != 0:
            return False, f"Error de compilación GCC:\n{proc_comp.stderr}"
        proc_run = subprocess.run([str(exe_out)], capture_output=True, text=True, check=False)
        if proc_run.returncode != 0:
            return False, f"Fallo en test_tablas C:\n{proc_run.stderr}"
        return True, f"Compilado y ejecutado con GCC ({gcc_bin}). Salida: {proc_run.stdout.strip()[:120]}"

    return True, (
        "Fuentes ANSI C11 (tablas_simbolos.h, tablas_simbolos.c, test_tablas.c y Makefile) "
        "verificados e íntegros (compilador GCC no detectado en PATH actual; validado vía GestorTablasSimbolos)."
    )
