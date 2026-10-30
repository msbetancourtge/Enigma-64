"""
Servicio de la pestana de traduccion CacaoCore-64 -> Enigma-64 (Tarea 27).

Envuelve el traductor LEX del grupo (`spl.traductor`) y lo compone con la RAM,
el cargador y la Unidad de Control de la maquina compartida. El panel recibe
este unico servicio y nunca importa ni el traductor ni el hardware:

  * traducir   fuente CacaoCore -> codigo Enigma-64 (ply.lex de los integrantes
               1, 2 y 4) y ensamblado con `enigma64.ensamblador`;
  * enviar     el binario entra por `CargadorEnigma` en 0x00200000 y los datos
               de `.data` se siembran en RAM con el enlace del Integrante 4;
  * ejecutar   corre la CPU hasta HLT y lee las variables de vuelta en RAM.

Si el traductor no se puede importar (por ejemplo, falta `ply`), el servicio
queda no disponible y el panel lo explica en pantalla.

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import pathlib
import re
from typing import Any, Dict, List, Optional, Tuple

from .puertos import ServicioBase, ServicioNoDisponible

# ---------------------------------------------------------------------------
# Importacion defensiva del traductor y del ensamblador
# ---------------------------------------------------------------------------

try:
    from spl.traductor import (  # type: ignore
        ProcesadorDirectivasCacao, precargar_datos_en_ram, traducir_texto,
    )
    from spl.traductor.traductor import BASE_CODIGO, BASE_DATOS  # type: ignore
    from ...ensamblador import ensamblar  # type: ignore
    _FALLO_TRADUCTOR = ""
except Exception as exc:  # pragma: no cover - solo si falta el modulo
    traducir_texto = ensamblar = None  # type: ignore
    BASE_CODIGO, BASE_DATOS = 0x00200000, 0x00201000
    _FALLO_TRADUCTOR = f"{type(exc).__name__}: {exc}"

#: Carpeta con los .asm de CacaoCore que trae el traductor.
DIR_EJEMPLOS = pathlib.Path(__file__).resolve().parents[3] / "spl" / "traductor" / "ejemplos"

#: Cada linea emitida por el traductor termina en "; L<n>: <instruccion>".
_ORIGEN = re.compile(r";\s*L(\d+):")

#: Resultados oficiales de la Tarea 10 para los tres algoritmos clasicos,
#: por nombre de archivo: (etiqueta, {variable: valor esperado}).
ESPERADOS: Dict[str, Tuple[str, Dict[str, int]]] = {
    "cacao_euclides": ("MCD(48, 18) = 6", {"a": 6, "b": 6}),
    "cacao_factorial": ("5! = 120", {"fact": 120}),
    "cacao_fibonacci": ("Fibonacci = [0, 1, 1, 2, 3, 5, 8]",
                        {"fib": 0, "fib1": 1, "fib2": 1, "fib3": 2,
                         "fib4": 3, "fib5": 5, "fib6": 8}),
}


def _con_signo(valor: int) -> int:
    return valor - (1 << 64) if valor >> 63 else valor


class AdaptadorTraduccion(ServicioBase):
    """
    Servicio compuesto: traductor LEX + cargador + RAM + CPU.

    Igual que el de algoritmos, junta varios modulos para que el panel siga
    recibiendo un solo servicio.
    """

    nombre = "Traductor CacaoCore-64 -> Enigma-64"
    modulo = "spl.traductor"

    def __init__(self, memoria: Optional[Any] = None,
                 cargador: Optional[Any] = None,
                 cpu: Optional[Any] = None) -> None:
        self.memoria = memoria
        self.cargador = cargador
        self.cpu = cpu

        motivo = _FALLO_TRADUCTOR
        if not motivo:
            faltan = [
                nombre for nombre, servicio in (("memoria", memoria), ("cargador", cargador))
                if servicio is None or not servicio.disponible
            ]
            if faltan:
                motivo = f"faltan los modulos: {', '.join(faltan)}"
        super().__init__(disponible=not motivo, motivo=motivo)

    # -- fuentes ------------------------------------------------------------

    def ejemplos(self) -> List[Dict[str, Any]]:
        """
        Los .asm de CacaoCore que trae el traductor, con los tres algoritmos
        clasicos primero. Se omiten las salidas ya traducidas (`*_enigma.asm`).
        """
        if not DIR_EJEMPLOS.is_dir():
            return []
        rutas = [r for r in DIR_EJEMPLOS.glob("*.asm") if not r.stem.endswith("_enigma")]
        rutas.sort(key=lambda r: (r.stem not in ESPERADOS, r.stem))
        return [
            {"clave": r.stem, "nombre": r.name, "ruta": str(r),
             "esperado": ESPERADOS.get(r.stem, (None, {}))[0]}
            for r in rutas
        ]

    def leer_archivo(self, ruta: str) -> str:
        return pathlib.Path(ruta).read_text(encoding="utf-8")

    # -- traduccion ---------------------------------------------------------

    def traducir(self, fuente: str) -> Dict[str, Any]:
        """
        Traduce y ensambla. Nunca lanza por un programa mal escrito: los
        errores vuelven en el diccionario para que el panel los pinte.
        """
        self.exigir()
        resultado = traducir_texto(fuente)
        lineas = resultado.codigo.splitlines()

        # linea de Enigma-64 (1-based) -> linea de CacaoCore que la origino
        correspondencia: Dict[int, int] = {}
        for numero, linea in enumerate(lineas, start=1):
            coincidencia = _ORIGEN.search(linea)
            if coincidencia:
                correspondencia[numero] = int(coincidencia.group(1))

        binario: Optional[bytes] = None
        error_ensamblado = ""
        if resultado.ok:
            try:
                binario = bytes(ensamblar(resultado.codigo, direccion_base=BASE_CODIGO))
            except Exception as exc:
                error_ensamblado = f"{type(exc).__name__}: {exc}"
            if binario is not None and BASE_CODIGO + len(binario) > BASE_DATOS:
                error_ensamblado = (f"el codigo ({len(binario)} bytes) se solapa con "
                                    f".data en 0x{BASE_DATOS:08X}")
                binario = None

        return {
            "fuente": fuente,
            "codigo": resultado.codigo,
            "errores": list(resultado.errores),
            "avisos": list(resultado.avisos),
            "variables": dict(resultado.variables),
            "registros": list(resultado.tabla.filas()),
            "acc_observable": resultado.acc_observable,
            "correspondencia": correspondencia,
            "binario": binario,
            "error_ensamblado": error_ensamblado,
            "ok": resultado.ok and binario is not None,
            "base_codigo": BASE_CODIGO,
            "base_datos": BASE_DATOS,
        }

    # -- carga --------------------------------------------------------------

    def enviar_a_ram(self, traduccion: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deposita el binario con `CargadorEnigma` en 0x00200000 (PC y SP quedan
        configurados) y siembra los valores iniciales de `.data`.
        """
        self.exigir()
        if not traduccion.get("ok"):
            raise ValueError("la traduccion tiene errores; no se puede cargar")
        informe = self.cargador.cargar_bytes(
            traduccion["binario"], destino=BASE_CODIGO,
            punto_entrada=BASE_CODIGO, configurar_cpu=True,
        )
        mapa = ProcesadorDirectivasCacao(base_datos=BASE_DATOS).procesar(traduccion["fuente"])
        informe["bytes_datos"] = precargar_datos_en_ram(
            self.memoria.ram, mapa, cargador=self.cargador.cargador)
        return informe

    # -- ejecucion ----------------------------------------------------------

    @property
    def puede_ejecutar(self) -> bool:
        return self.cpu is not None and self.cpu.disponible

    def ejecutar(self, max_ciclos: int = 1_000_000) -> Dict[str, Any]:
        if not self.puede_ejecutar:
            raise ServicioNoDisponible(
                "Ejecutar el programa traducido necesita la Unidad de Control "
                "(enigma64/cpu.py, Integrante 3)."
            )
        return self.cpu.ejecutar(max_ciclos)

    def leer_variables(self, traduccion: Dict[str, Any]) -> List[Tuple[str, int, Optional[int]]]:
        """(nombre, direccion, valor con signo) de cada variable de `.data`."""
        self.exigir()
        filas = []
        for nombre, direccion in traduccion["variables"].items():
            valor, _estado = self.memoria.leer(direccion, 8)
            filas.append((nombre, direccion, None if valor is None else _con_signo(valor)))
        return filas

    def verificar(self, clave: str, traduccion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Contrasta las variables en RAM con el resultado oficial de la Tarea 10.
        None si el programa no es uno de los tres algoritmos clasicos.
        """
        if clave not in ESPERADOS:
            return None
        etiqueta, esperados = ESPERADOS[clave]
        leidos = {nombre: valor for nombre, _d, valor in self.leer_variables(traduccion)}
        obtenidos = {nombre: leidos.get(nombre) for nombre in esperados}
        return {"ok": obtenidos == esperados, "etiqueta": etiqueta,
                "esperado": dict(esperados), "obtenido": obtenidos}
