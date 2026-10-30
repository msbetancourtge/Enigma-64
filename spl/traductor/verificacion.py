"""
Pipeline de Verificacion y Contraste Oficial — Tarea 27 (Integrante 7).

Responsabilidades del Integrante 7 (Algoritmos & Tests):
  1. Paso de los 3 archivos .asm de CacaoCore-64 (Euclides, Factorial y
     Fibonacci) por el traductor LEX completo (memoria, registros, ALU,
     control de flujo y directivas).
  2. Ensamblado a codigo de maquina Big-Endian y ejecucion real sobre la
     CPU, BancoRegistros, RAMMemory y CargadorEnigma de Enigma-64.
  3. Contraste automatizado contra la ejecucion y los resultados oficiales
     de la Tarea 10 definidos en enigma64/programas.py:
       - Factorial: 5! = 120
       - Euclides : MCD(48, 18) = 6
       - Fibonacci: [0, 1, 1, 2, 3, 5, 8]

Autor: Integrante 7 - Algoritmos & Tests (Alejandro Arguello Munoz)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from enigma64.cargador import BinarioEnigma, CargadorEnigma
from enigma64.cpu import CPU
from enigma64.ensamblador import ensamblar
from enigma64.memoria import RAMMemory, STATUS_READY
from enigma64.programas import (
    PROGRAMA_EUCLIDES,
    PROGRAMA_FACTORIAL,
    PROGRAMA_FIBONACCI,
    PROGRAMAS_OFICIALES,
    DefinicionPrograma,
    inicializar_escenario_prueba,
)
from enigma64.registros import BancoRegistros, MASK64

from .directivas import (
    BASE_CODIGO,
    BASE_DATOS,
    ProcesadorDirectivasCacao,
    cargar_y_ejecutar_con_cargador,
    construir_binario_enigma,
)
from .mmio_soporte import ejecutar_en_enigma_mmio, inyectar_salida_mmio
from .traductor import ResultadoTraduccion, TraductorCacaoEnigma, ejecutar_en_enigma, traducir_texto

DIR_EJEMPLOS_CACAO = Path(__file__).resolve().parent / "ejemplos"

ARCHIVOS_ALGORITMOS_CACAO: Dict[str, Path] = {
    "euclides": DIR_EJEMPLOS_CACAO / "cacao_euclides.asm",
    "factorial": DIR_EJEMPLOS_CACAO / "cacao_factorial.asm",
    "fibonacci": DIR_EJEMPLOS_CACAO / "cacao_fibonacci.asm",
}

RESULTADOS_OFICIALES_TAREA10: Dict[str, Any] = {
    "factorial": 120,
    "euclides": 6,
    "fibonacci": [0, 1, 1, 2, 3, 5, 8],
}


@dataclass
class ResultadoVerificacionAlgoritmo:
    """Resultado detallado de traducir, ejecutar y contrastar un algoritmo contra la Tarea 10."""

    nombre: str
    ruta_asm_cacao: Path
    codigo_cacao: str
    traduccion: ResultadoTraduccion
    bytes_enigma: bytes
    binario_enigma: BinarioEnigma
    ciclos_traducido: int
    instrucciones_traducido: int
    detenido_hlt_traducido: bool
    pc_final_traducido: int
    resultado_traducido: Any
    resultado_nativo_tarea10: Any
    resultado_esperado_tarea10: Any
    ciclos_nativo_tarea10: int
    instrucciones_nativo_tarea10: int
    detenido_hlt_nativo: bool
    coincide_con_tarea10: bool
    salida_mmio_lineas: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            self.traduccion.ok
            and self.detenido_hlt_traducido
            and self.detenido_hlt_nativo
            and self.coincide_con_tarea10
            and self.resultado_traducido == self.resultado_esperado_tarea10
        )


@dataclass
class ReporteVerificacionTraductor:
    """Reporte consolidado del pipeline de verificacion de los 3 algoritmos clasicos."""

    algoritmos: Dict[str, ResultadoVerificacionAlgoritmo] = field(default_factory=dict)

    @property
    def exito_total(self) -> bool:
        return bool(self.algoritmos) and all(r.ok for r in self.algoritmos.values())

    @property
    def total_instrucciones_traducidas(self) -> int:
        return sum(r.instrucciones_traducido for r in self.algoritmos.values())

    @property
    def total_ciclos_traducidos(self) -> int:
        return sum(r.ciclos_traducido for r in self.algoritmos.values())


def _reemplazar_datos_cacao(fuente_cacao: str, overrides: Dict[str, int]) -> str:
    """Reemplaza valores iniciales en la seccion .data de un fuente .asm de CacaoCore."""
    texto = fuente_cacao
    for nombre, valor in overrides.items():
        patron = rf"(^\s*{re.escape(nombre)}\s*:\s*)([^\n;#]+)"
        texto = re.sub(patron, rf"\g<1>{valor}", texto, count=1, flags=re.MULTILINE)
    return texto


def ejecutar_algoritmo_nativo_tarea10(
    nombre: str,
    overrides_ram: Optional[Dict[int, int]] = None,
    max_ciclos: int = 100_000,
) -> Tuple[Any, int, int, bool]:
    """
    Ejecuta el binario nativo oficial de la Tarea 10 (enigma64/programas.py)
    en una instancia limpia de CPU + RAMMemory + CargadorEnigma y retorna:
      (resultado_en_ram, ciclos, instrucciones, detenido_hlt)
    """
    prog: DefinicionPrograma = PROGRAMAS_OFICIALES[nombre]
    ram = RAMMemory()
    banco = BancoRegistros()
    cpu = CPU(ram=ram, banco=banco)
    cargador = CargadorEnigma(ram=ram, banco=banco, cpu=cpu)

    inicializar_escenario_prueba(ram, banco, cargador, prog)
    if overrides_ram:
        for direccion, valor in overrides_ram.items():
            _, status = ram.mem_write(direccion, valor & MASK64, size_bytes=8, check_alignment=True)
            if status != STATUS_READY:
                raise RuntimeError(f"Error al escribir override en 0x{direccion:08X}")

    cpu.ejecutar(max_ciclos=max_ciclos)

    if nombre == "factorial":
        val, st = ram.mem_read(0x00201008, size_bytes=8, check_alignment=True)
        assert st == STATUS_READY
        resultado: Any = val
    elif nombre == "euclides":
        val, st = ram.mem_read(0x00202010, size_bytes=8, check_alignment=True)
        assert st == STATUS_READY
        resultado = val
    elif nombre == "fibonacci":
        terminos: List[int] = []
        for i in range(7):
            val, st = ram.mem_read(0x00203000 + i * 8, size_bytes=8, check_alignment=True)
            assert st == STATUS_READY
            terminos.append(int(val or 0))
        resultado = terminos
    else:
        raise ValueError(f"Algoritmo oficial desconocido: {nombre}")

    return resultado, cpu.ciclos, cpu.instrucciones, bool(cpu.detenido)


def _extraer_resultado_traducido(
    nombre: str,
    ram: RAMMemory,
    variables: Dict[str, int],
) -> Any:
    """Extrae de RAMMemory el resultado producido por el algoritmo traducido desde CacaoCore."""
    if nombre == "factorial":
        dir_fact = variables["fact"]
        val, st = ram.mem_read(dir_fact, size_bytes=8, check_alignment=True)
        if st != STATUS_READY:
            raise RuntimeError(f"Lectura desalineada o invalida en fact (0x{dir_fact:08X})")
        return int(val or 0)

    if nombre == "euclides":
        dir_a = variables["a"]
        val, st = ram.mem_read(dir_a, size_bytes=8, check_alignment=True)
        if st != STATUS_READY:
            raise RuntimeError(f"Lectura desalineada o invalida en a (0x{dir_a:08X})")
        return int(val or 0)

    if nombre == "fibonacci":
        claves = ["fib", "fib1", "fib2", "fib3", "fib4", "fib5", "fib6"]
        valores: List[int] = []
        for clave in claves:
            dir_elem = variables[clave]
            val, st = ram.mem_read(dir_elem, size_bytes=8, check_alignment=True)
            if st != STATUS_READY:
                raise RuntimeError(f"Lectura desalineada o invalida en {clave} (0x{dir_elem:08X})")
            valores.append(int(val or 0))
        return valores

    raise ValueError(f"Algoritmo desconocido: {nombre}")


def verificar_algoritmo_cacao(
    nombre: str,
    usar_cargador: bool = True,
    overrides_cacao: Optional[Dict[str, int]] = None,
    overrides_nativo_ram: Optional[Dict[int, int]] = None,
    verificar_mmio: bool = True,
    max_ciclos: int = 1_000_000,
) -> ResultadoVerificacionAlgoritmo:
    """
    Ejecuta el flujo completo de verificacion para uno de los 3 algoritmos clasicos:
      1. Lee el archivo .asm de CacaoCore-64.
      2. Lo traduce a ensamblador de Enigma-64 mediante TraductorCacaoEnigma (LEX).
      3. Ensambla el codigo Enigma-64 y construye el BinarioEnigma.
      4. Lo carga y ejecuta en la CPU y RAMMemory de Enigma-64.
      5. Ejecuta en paralelo el binario nativo de la Tarea 10 y contrasta los resultados.
    """
    clave = nombre.lower()
    if clave not in ARCHIVOS_ALGORITMOS_CACAO:
        raise ValueError(
            f"Algoritmo '{nombre}' no reconocido. Opciones: {tuple(ARCHIVOS_ALGORITMOS_CACAO)}"
        )

    ruta_asm = ARCHIVOS_ALGORITMOS_CACAO[clave]
    codigo_cacao = ruta_asm.read_text(encoding="utf-8")
    if overrides_cacao:
        codigo_cacao = _reemplazar_datos_cacao(codigo_cacao, overrides_cacao)

    traductor = TraductorCacaoEnigma(base_datos=BASE_DATOS)
    traduccion = traductor.traducir(codigo_cacao)
    if not traduccion.ok:
        raise ValueError(f"Errores al traducir {ruta_asm.name}: {traduccion.errores}")

    proc_datos = ProcesadorDirectivasCacao(base_datos=BASE_DATOS)
    mapa_datos = proc_datos.procesar(codigo_cacao)
    bytes_enigma = bytes(ensamblar(traduccion.codigo, direccion_base=BASE_CODIGO))
    binario_enigma = construir_binario_enigma(
        codigo_o_binario=bytes_enigma,
        mapa_datos=mapa_datos,
        direccion_codigo=BASE_CODIGO,
        entry_point=BASE_CODIGO,
    )

    if usar_cargador:
        cpu_trad, _banco_trad, ram_trad, _cargador, _info = cargar_y_ejecutar_con_cargador(
            codigo_cacao,
            max_ciclos=max_ciclos,
            base_datos=BASE_DATOS,
        )
    else:
        cpu_trad, _banco_trad, ram_trad = ejecutar_en_enigma(
            traduccion.codigo,
            max_ciclos=max_ciclos,
            base_datos=BASE_DATOS,
            usar_cargador=False,
        )

    resultado_traducido = _extraer_resultado_traducido(clave, ram_trad, traduccion.variables)
    resultado_nativo, ciclos_nat, inst_nat, hlt_nat = ejecutar_algoritmo_nativo_tarea10(
        clave,
        overrides_ram=overrides_nativo_ram,
        max_ciclos=max_ciclos,
    )

    esperado = (
        resultado_nativo
        if (overrides_cacao or overrides_nativo_ram)
        else RESULTADOS_OFICIALES_TAREA10[clave]
    )

    lineas_mmio: List[str] = []
    if verificar_mmio:
        var_mmio = {"euclides": ["a"], "factorial": ["fact"], "fibonacci": ["res"]}[clave]
        codigo_mmio = inyectar_salida_mmio(traduccion.codigo, traduccion.variables, var_mmio)
        _cpu_m, _banco_m, _ram_m, perifs_m = ejecutar_en_enigma_mmio(
            codigo_mmio, max_ciclos=max_ciclos
        )
        lineas_mmio = [l for l in perifs_m.controlador_pantalla.obtener_lineas() if l]

    return ResultadoVerificacionAlgoritmo(
        nombre=clave,
        ruta_asm_cacao=ruta_asm,
        codigo_cacao=codigo_cacao,
        traduccion=traduccion,
        bytes_enigma=bytes_enigma,
        binario_enigma=binario_enigma,
        ciclos_traducido=cpu_trad.ciclos,
        instrucciones_traducido=cpu_trad.instrucciones,
        detenido_hlt_traducido=bool(cpu_trad.detenido),
        pc_final_traducido=cpu_trad.banco.pc,
        resultado_traducido=resultado_traducido,
        resultado_nativo_tarea10=resultado_nativo,
        resultado_esperado_tarea10=esperado,
        ciclos_nativo_tarea10=ciclos_nat,
        instrucciones_nativo_tarea10=inst_nat,
        detenido_hlt_nativo=hlt_nat,
        coincide_con_tarea10=(resultado_traducido == resultado_nativo),
        salida_mmio_lineas=lineas_mmio,
    )


def ejecutar_pipeline_verificacion_cacao(
    usar_cargador: bool = True,
    verificar_mmio: bool = True,
) -> ReporteVerificacionTraductor:
    """
    Ejecuta el pipeline de verificacion completo sobre los 3 algoritmos clasicos
    (Euclides, Factorial y Fibonacci) y retorna el reporte consolidado.
    """
    reporte = ReporteVerificacionTraductor()
    for nombre in ("euclides", "factorial", "fibonacci"):
        reporte.algoritmos[nombre] = verificar_algoritmo_cacao(
            nombre,
            usar_cargador=usar_cargador,
            verificar_mmio=verificar_mmio,
        )
    return reporte


def construir_definiciones_programas_tarea27() -> Dict[str, DefinicionPrograma]:
    """
    Genera objetos DefinicionPrograma (compatibles con enigma64/programas.py)
    para los 3 algoritmos clasicos traducidos desde CacaoCore-64.
    """
    definiciones: Dict[str, DefinicionPrograma] = {}
    descripciones = {
        "euclides": "Euclides traducido desde CacaoCore-64 (MCD(48, 18) = 6)",
        "factorial": "Factorial traducido desde CacaoCore-64 (5! = 120)",
        "fibonacci": "Fibonacci traducido desde CacaoCore-64 ([0, 1, 1, 2, 3, 5, 8])",
    }

    for clave, ruta in ARCHIVOS_ALGORITMOS_CACAO.items():
        fuente = ruta.read_text(encoding="utf-8")
        res = traducir_texto(fuente, base_datos=BASE_DATOS)
        codigo_bytes = bytes(ensamblar(res.codigo, direccion_base=BASE_CODIGO))
        lineas_limpias = [
            ln.strip()
            for ln in res.codigo.splitlines()
            if ln.strip() and not ln.strip().startswith(";")
        ]

        if clave == "euclides":
            salidas = {res.variables["a"]: 6}
        elif clave == "factorial":
            salidas = {res.variables["fact"]: 120}
        else:
            salidas = {
                res.variables[k]: v
                for k, v in zip(
                    ["fib", "fib1", "fib2", "fib3", "fib4", "fib5", "fib6"],
                    [0, 1, 1, 2, 3, 5, 8],
                )
            }
            salidas[res.variables["res"]] = 8

        definiciones[f"cacao_{clave}"] = DefinicionPrograma(
            nombre=f"cacao_{clave}",
            descripcion=descripciones[clave],
            bytes_codigo=codigo_bytes,
            direccion_base=BASE_CODIGO,
            entry_point=BASE_CODIGO,
            entradas_ram={},
            salidas_esperadas_ram=salidas,
            lineas_ensamblador=lineas_limpias,
        )

    return definiciones
