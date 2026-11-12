"""
Servicio del panel de Estructuras de Datos (Tarea 29).

Es el adaptador entre la interfaz y la libreria de estructuras del grupo:

  * `spl.estructuras` (Integrante 4): descriptores, precarga y lectura de
    vectores y matrices en RAM, y el puente Preprocesador -> Ensamblador ->
    BinarioEnigma (.e64) que entra por `CargadorEnigma`.
  * `spl/include/estructuras.inc` (Integrantes 1, 2, 3 y 4): la libreria en
    ensamblador (VEC_*, MAT_*, cabeceras y descriptores).
  * `spl/ejemplos/*.asm` (Integrantes 6 y 7): los algoritmos que la usan, como
    el merge sort. Cualquier programa nuevo que haga
    `#include "estructuras.inc"` aparece solo en el catalogo.

El servicio compone la RAM, el banco de registros, el cargador, la CPU y los
perifericos de la maquina compartida, de modo que lo que ve el panel es la
misma memoria que muestran las demas pestanas. Todo lo que hace es logica
pura (sin Tkinter), por eso se prueba sin pantalla.

Flujo tipico, que es el que sigue el panel:

    1. El usuario escribe sus datos de entrada  -> `definir_vector` / `definir_matriz`
    2. Elige un programa y lo compila           -> `compilar`
    3. Lo carga en RAM con sus datos            -> `cargar`
    4. Lo ejecuta paso a paso o de corrido      -> `avanzar` / `ejecutar_hasta_fin`
    5. Lee como cambiaron las estructuras       -> `instantaneas`

Autor: Integrante 5 Maicol Sebastian Olarte Ramirez - Interfaz de usuario
"""

from __future__ import annotations

import math
import pathlib
import re
import struct
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from .puertos import ServicioBase, ServicioNoDisponible

# ---------------------------------------------------------------------------
# Importacion defensiva de la libreria de estructuras (Integrante 4)
# ---------------------------------------------------------------------------

try:
    from spl.estructuras import (  # type: ignore
        BASE_BUFFERS, BASE_CABECERAS, BASE_MATRICES, BASE_VECTORES,
        DESC_TAM_BYTES, LIMITE_BUFFERS, LIMITE_CABECERAS, LIMITE_MATRICES,
        LIMITE_VECTORES, PILA_ESTRUCTURAS, TIPO_MATRIZ, TIPO_VECTOR,
        DescriptorMatriz, DescriptorVector, compilar_a_binario_e64,
        precargar_estructuras_en_ram,
    )
    _FALLO_ESTRUCTURAS = ""
except Exception as exc:  # pragma: no cover - solo si falta el modulo
    DescriptorMatriz = DescriptorVector = None  # type: ignore
    compilar_a_binario_e64 = precargar_estructuras_en_ram = None  # type: ignore
    BASE_CABECERAS, LIMITE_CABECERAS = 0x00210000, 0x00220000
    BASE_VECTORES, LIMITE_VECTORES = 0x00220000, 0x00260000
    BASE_MATRICES, LIMITE_MATRICES = 0x00260000, 0x002E0000
    BASE_BUFFERS, LIMITE_BUFFERS = 0x002E0000, 0x00300000
    PILA_ESTRUCTURAS, DESC_TAM_BYTES = 0x00400000, 32
    TIPO_VECTOR, TIPO_MATRIZ = 1, 2
    _FALLO_ESTRUCTURAS = f"{type(exc).__name__}: {exc}"

MASCARA_64 = (1 << 64) - 1

#: Carpeta con los programas en ensamblador que usan la libreria.
RAIZ_REPO = pathlib.Path(__file__).resolve().parents[3]
DIR_EJEMPLOS = RAIZ_REPO / "spl" / "ejemplos"
DIR_INCLUDE = RAIZ_REPO / "spl" / "include"

#: Un programa entra al catalogo si incluye la libreria.
_INCLUYE_LIBRERIA = re.compile(r'^\s*#include\s+[<"]estructuras\.inc[>"]', re.MULTILINE)

#: Limites de dibujo: una cabecera con basura no debe congelar la interfaz.
MAX_ELEMENTOS_VECTOR = 256
MAX_FILAS_MATRIZ = 32
MAX_COLUMNAS_MATRIZ = 32

#: Ranuras de la tabla de descriptores que se exploran al detectar.
RANURAS_A_EXPLORAR = 16

#: Formatos con los que el panel puede mostrar cada palabra de 64 bits.
FORMATOS = ("decimal", "hex", "float")

#: Instrucciones que acceden a memoria de datos (su direccion queda en Z).
_LECTURAS = {"LOAD", "LDB"}
_ESCRITURAS = {"STORE", "STB"}

#: Zonas del mapa de la libreria (layout_datos.inc), como dato puro.
ZONAS = (
    {"clave": "cabeceras", "nombre": "Cabeceras / descriptores",
     "inicio": BASE_CABECERAS, "fin": LIMITE_CABECERAS},
    {"clave": "vectores", "nombre": "Vectores", "inicio": BASE_VECTORES,
     "fin": LIMITE_VECTORES},
    {"clave": "matrices", "nombre": "Matrices (row-major)", "inicio": BASE_MATRICES,
     "fin": LIMITE_MATRICES},
    {"clave": "buffers", "nombre": "Buffers auxiliares", "inicio": BASE_BUFFERS,
     "fin": LIMITE_BUFFERS},
)

#: Lo que conviene observar en los programas conocidos del grupo. Una
#: longitud None se lee en vivo de la cabecera inline [base - 8]; una cadena
#: copia la longitud actual de otra estructura observada.
OBSERVABLES_CONOCIDOS: Dict[str, Dict[str, Any]] = {
    "merge_sort": {
        "descripcion": "Merge sort sobre V con vector auxiliar y salida a pantalla MMIO "
                       "(Integrante 6). Si escribes tu propio V en 0x00220000 lo ordena "
                       "a el; si no, usa el vector demo de 8 elementos.",
        "observables": [
            {"nombre": "V", "tipo": "vector", "base": BASE_VECTORES, "longitud": None},
            {"nombre": "AUX", "tipo": "vector", "base": BASE_BUFFERS, "longitud": "V"},
        ],
    },
    "prueba_cabeceras_cargador": {
        "descripcion": "Construye descriptores de un vector de 5 y una matriz 3x4 y "
                       "deja los resultados de los consultores en RES (Integrante 4).",
        "observables": [
            {"nombre": "V", "tipo": "vector", "base": BASE_VECTORES, "longitud": None},
            {"nombre": "M", "tipo": "matriz", "base": BASE_MATRICES,
             "filas": None, "columnas": None},
            {"nombre": "RES", "tipo": "vector", "base": BASE_BUFFERS, "longitud": 10},
        ],
    },
}


# ---------------------------------------------------------------------------
# Utilidades puras (se prueban sin hardware)
# ---------------------------------------------------------------------------


def _numero(texto: str) -> Union[int, float]:
    """Convierte un literal escrito por el usuario: decimal, 0x.., 0b.. o real."""
    limpio = texto.strip().replace("_", "")
    if not limpio:
        raise ValueError("valor vacio")
    try:
        return int(limpio, 0)
    except ValueError:
        pass
    try:
        valor = float(limpio)
    except ValueError:
        raise ValueError(f"'{texto.strip()}' no es un numero valido") from None
    return valor


def parsear_vector(texto: str) -> List[Union[int, float]]:
    """
    '45, -12, 89 0x10' -> [45, -12, 89, 16]. Acepta comas, espacios, punto y
    coma o saltos de linea como separadores, y corchetes opcionales.
    """
    cuerpo = texto.strip().strip("[]")
    piezas = [p for p in re.split(r"[\s,;]+", cuerpo) if p]
    if not piezas:
        raise ValueError("escribe al menos un valor, por ejemplo: 5, 3, 8, 1")
    return [_numero(p) for p in piezas]


def parsear_matriz(texto: str) -> List[List[Union[int, float]]]:
    """
    '1 2 3; 4 5 6' o una fila por linea -> [[1, 2, 3], [4, 5, 6]]. Dentro de
    una fila valen comas o espacios. Todas las filas deben tener el mismo
    numero de columnas.
    """
    cuerpo = texto.strip().strip("[]")
    filas_txt = [f for f in re.split(r"[;\n]+|\]\s*,?\s*\[", cuerpo) if f.strip()]
    if not filas_txt:
        raise ValueError("escribe al menos una fila, por ejemplo: 1 2; 3 4")
    filas = []
    for texto_fila in filas_txt:
        piezas = [p for p in re.split(r"[\s,]+", texto_fila.strip().strip("[]")) if p]
        filas.append([_numero(p) for p in piezas])
    columnas = len(filas[0])
    for indice, fila in enumerate(filas):
        if len(fila) != columnas:
            raise ValueError(
                f"la fila {indice} tiene {len(fila)} columnas y la fila 0 tiene {columnas}; "
                "todas deben tener las mismas")
    return filas


def formatear_palabra(palabra: int, formato: str = "decimal") -> str:
    """Texto de una palabra cruda de 64 bits en el formato pedido."""
    palabra &= MASCARA_64
    if formato == "hex":
        return f"0x{palabra:X}"
    if formato == "float":
        valor = struct.unpack(">d", struct.pack(">Q", palabra))[0]
        if math.isnan(valor) or math.isinf(valor):
            return str(valor)
        return f"{valor:.6g}"
    return str(palabra - (1 << 64) if palabra >> 63 else palabra)


def a_entero_con_signo(palabra: int) -> int:
    palabra &= MASCARA_64
    return palabra - (1 << 64) if palabra >> 63 else palabra


def zona_de(direccion: int) -> Optional[str]:
    """Clave de la zona de la libreria donde cae una direccion, o None."""
    for zona in ZONAS:
        if zona["inicio"] <= direccion < zona["fin"]:
            return zona["clave"]
    return None


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------


class AdaptadorEstructuras(ServicioBase):
    """
    Servicio compuesto: libreria de estructuras + cargador + RAM + CPU + MMIO.

    Mantiene dos listas:
      * `entradas`:    estructuras que el USUARIO escribio. Se vuelven a
                       escribir en RAM cada vez que se carga un programa.
      * `observadas`:  lo que el panel dibuja. Incluye las entradas y las que
                       aporta el programa elegido o la deteccion automatica.
    """

    nombre = "Estructuras de datos (vectores y matrices)"
    modulo = "spl.estructuras"

    def __init__(self, memoria: Optional[Any] = None,
                 registros: Optional[Any] = None,
                 cargador: Optional[Any] = None,
                 cpu: Optional[Any] = None,
                 mmio: Optional[Any] = None) -> None:
        self.memoria = memoria
        self.registros = registros
        self.cargador = cargador
        self.cpu = cpu
        self.mmio = mmio

        motivo = _FALLO_ESTRUCTURAS
        if not motivo:
            faltan = [
                nombre for nombre, servicio in (("memoria", memoria), ("cargador", cargador))
                if servicio is None or not servicio.disponible
            ]
            if faltan:
                motivo = f"faltan los modulos: {', '.join(faltan)}"
        super().__init__(disponible=not motivo, motivo=motivo)

        self.entradas: Dict[str, Dict[str, Any]] = {}
        self.observadas: Dict[str, Dict[str, Any]] = {}
        self.compilado: Optional[Dict[str, Any]] = None
        self._simbolos_por_direccion: List[Tuple[int, str]] = []
        self._valores_al_cargar: Dict[str, List[int]] = {}
        self._ultimo_mnemonico = ""

    # =======================================================================
    # Catalogo de programas
    # =======================================================================

    def programas(self) -> List[Dict[str, Any]]:
        """Los .asm de `spl/ejemplos` que incluyen `estructuras.inc`."""
        if not DIR_EJEMPLOS.is_dir():
            return []
        salida = []
        for ruta in sorted(DIR_EJEMPLOS.glob("*.asm")):
            try:
                fuente = ruta.read_text(encoding="utf-8")
            except OSError:
                continue
            if not _INCLUYE_LIBRERIA.search(fuente):
                continue
            conocido = OBSERVABLES_CONOCIDOS.get(ruta.stem, {})
            salida.append({
                "clave": ruta.stem,
                "nombre": ruta.name,
                "ruta": str(ruta),
                "descripcion": conocido.get("descripcion", _resumen(fuente)),
                "observables": [dict(o) for o in conocido.get("observables", [])],
            })
        # Los programas con observables conocidos van primero.
        salida.sort(key=lambda p: (not p["observables"], p["clave"]))
        return salida

    def leer_archivo(self, ruta: str) -> str:
        return pathlib.Path(ruta).read_text(encoding="utf-8")

    # =======================================================================
    # Datos de entrada del usuario
    # =======================================================================

    def _siguiente_base(self, tipo: str, tamano_bytes: int) -> int:
        """
        Primera direccion libre de la zona (vectores o matrices) dejando 16
        bytes para la cabecera inline y redondeando a 8 bytes.
        """
        inicio = BASE_VECTORES if tipo == "vector" else BASE_MATRICES
        limite = LIMITE_VECTORES if tipo == "vector" else LIMITE_MATRICES
        base = inicio
        ocupadas = sorted(
            (e["base"] - 16, e["base"] + e["bytes"])
            for e in self.entradas.values() if e["tipo"] == tipo
        )
        for ini, fin in ocupadas:
            if base + tamano_bytes <= ini:
                break
            base = max(base, ((fin + 16 + 7) // 8) * 8)
        if base + tamano_bytes > limite:
            raise ValueError(f"no queda espacio en la zona de {tipo}es")
        return base

    def _siguiente_ranura(self) -> int:
        usadas = {e["ranura"] for e in self.entradas.values() if e.get("ranura") is not None}
        ranura = 0
        while ranura in usadas:
            ranura += 1
        return ranura

    def _validar_nombre(self, nombre: str) -> str:
        nombre = (nombre or "").strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", nombre):
            raise ValueError("el nombre debe empezar por letra y usar solo letras, "
                             "digitos o '_' (por ejemplo: V, A, datos_1)")
        return nombre

    def definir_vector(self, nombre: str, valores: Sequence[Union[int, float]],
                       base: Optional[int] = None,
                       ranura: Optional[int] = None) -> Dict[str, Any]:
        """
        Registra un vector de entrada, lo escribe en RAM con la libreria del
        Integrante 4 (descriptor + cabecera inline + datos) y lo observa.
        """
        self.exigir()
        nombre = self._validar_nombre(nombre)
        anterior = self.entradas.pop(nombre, None)
        try:
            if not valores:
                raise ValueError("el vector necesita al menos un valor")
            tam = len(valores) * 8
            base = self._siguiente_base("vector", tam) if base is None else base
            ranura = self._siguiente_ranura() if ranura is None else ranura
            descriptor = DescriptorVector(nombre=nombre, elementos=list(valores),
                                          direccion_base=base, slot_cabecera=ranura)
            self._comprobar_solapes(nombre, descriptor)
        except Exception:
            if anterior is not None:
                self.entradas[nombre] = anterior
            raise
        entrada = {"nombre": nombre, "tipo": "vector", "base": base, "ranura": ranura,
                   "longitud": len(valores), "valores": list(valores),
                   "bytes": tam, "descriptor": descriptor}
        self.entradas[nombre] = entrada
        self._escribir_en_ram([descriptor])
        self.observar(nombre, "vector", base, longitud=None, origen="usuario")
        return self._publico(entrada)

    def definir_matriz(self, nombre: str, filas: Sequence[Sequence[Union[int, float]]],
                       base: Optional[int] = None,
                       ranura: Optional[int] = None) -> Dict[str, Any]:
        """Como `definir_vector`, para una matriz F x C en orden por filas."""
        self.exigir()
        nombre = self._validar_nombre(nombre)
        anterior = self.entradas.pop(nombre, None)
        try:
            if not filas or not filas[0]:
                raise ValueError("la matriz necesita al menos una fila y una columna")
            tam = len(filas) * len(filas[0]) * 8
            base = self._siguiente_base("matriz", tam) if base is None else base
            ranura = self._siguiente_ranura() if ranura is None else ranura
            descriptor = DescriptorMatriz.desde_filas(
                nombre=nombre, filas_2d=[list(f) for f in filas],
                direccion_base=base, slot_cabecera=ranura)
            self._comprobar_solapes(nombre, descriptor)
        except Exception:
            if anterior is not None:
                self.entradas[nombre] = anterior
            raise
        entrada = {"nombre": nombre, "tipo": "matriz", "base": base, "ranura": ranura,
                   "filas": len(filas), "columnas": len(filas[0]),
                   "valores": [list(f) for f in filas], "bytes": tam,
                   "descriptor": descriptor}
        self.entradas[nombre] = entrada
        self._escribir_en_ram([descriptor])
        self.observar(nombre, "matriz", base, filas=None, columnas=None, origen="usuario")
        return self._publico(entrada)

    def _comprobar_solapes(self, nombre: str, descriptor: Any) -> None:
        nuevos = descriptor.segmentos_memoria()
        for otra in self.entradas.values():
            if otra["nombre"] == nombre:
                continue
            for et_n, ini_n, b_n in nuevos:
                for et_o, ini_o, b_o in otra["descriptor"].segmentos_memoria():
                    if max(ini_n, ini_o) < min(ini_n + len(b_n), ini_o + len(b_o)):
                        raise ValueError(
                            f"'{et_n}' en 0x{ini_n:08X} se solapa con '{et_o}' en "
                            f"0x{ini_o:08X}; elige otra direccion base")

    def _escribir_en_ram(self, descriptores: Sequence[Any]) -> int:
        cargador = getattr(self.cargador, "cargador", None)
        return precargar_estructuras_en_ram(self.memoria.ram, list(descriptores),
                                            cargador=cargador)

    def quitar(self, nombre: str) -> None:
        """Deja de observar una estructura y, si era de entrada, la olvida."""
        self.entradas.pop(nombre, None)
        self.observadas.pop(nombre, None)

    def limpiar(self) -> None:
        self.entradas.clear()
        self.observadas.clear()

    def entradas_publicas(self) -> List[Dict[str, Any]]:
        return [self._publico(e) for e in self.entradas.values()]

    @staticmethod
    def _publico(entrada: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in entrada.items() if k != "descriptor"}

    # =======================================================================
    # Observacion de estructuras en RAM
    # =======================================================================

    def observar(self, nombre: str, tipo: str, base: int,
                 longitud: Union[int, str, None] = None,
                 filas: Optional[int] = None, columnas: Optional[int] = None,
                 origen: str = "programa") -> Dict[str, Any]:
        """Anade una estructura a la lista de lo que se dibuja."""
        if tipo not in ("vector", "matriz"):
            raise ValueError(f"tipo desconocido: {tipo!r}")
        if base % 8:
            raise ValueError(f"la base 0x{base:08X} no esta alineada a 8 bytes")
        spec = {"nombre": nombre, "tipo": tipo, "base": base, "origen": origen}
        if tipo == "vector":
            spec["longitud"] = longitud
        else:
            spec["filas"], spec["columnas"] = filas, columnas
        self.observadas[nombre] = spec
        return dict(spec)

    def observar_programa(self, programa: Dict[str, Any]) -> List[str]:
        """Observa lo que el programa elegido declara como interesante."""
        # Lo que aporto el programa anterior (o la deteccion) ya no aplica.
        for nombre in [n for n, s in self.observadas.items() if s.get("origen") != "usuario"]:
            del self.observadas[nombre]
        bases_usuario = {(e["tipo"], e["base"]) for e in self.entradas.values()}
        nombres = []
        for spec in programa.get("observables", []):
            if spec["nombre"] in self.entradas or (spec["tipo"], spec["base"]) in bases_usuario:
                continue  # el usuario ya la definio: manda su version
            self.observar(origen="programa", **spec)
            nombres.append(spec["nombre"])
        return nombres

    def detectar(self) -> List[Dict[str, Any]]:
        """
        Recorre la tabla de descriptores (BASE_CABECERAS) y observa cada
        ranura valida: tipo 1 o 2, base alineada dentro de la zona de usuario y
        dimensiones razonables. Asi se ve lo que un programa cualquiera
        construyo con DESC_VEC_INIT / DESC_MAT_INIT.
        """
        self.exigir()
        encontradas = []
        for ranura in range(RANURAS_A_EXPLORAR):
            dir_desc = BASE_CABECERAS + ranura * DESC_TAM_BYTES
            tipo, base, filas, cols = (self._palabra(dir_desc + 8 * k) for k in range(4))
            if tipo not in (TIPO_VECTOR, TIPO_MATRIZ):
                continue
            if base % 8 or not (BASE_CABECERAS <= base < 0xC0000000):
                continue
            ya = next((n for n, s in self.observadas.items() if s["base"] == base), None)
            if tipo == TIPO_VECTOR and 0 < filas <= MAX_ELEMENTOS_VECTOR:
                nombre = ya or f"V{ranura}"
                if ya is None:
                    self.observar(nombre, "vector", base, longitud=filas, origen="descriptor")
                encontradas.append({"nombre": nombre, "ranura": ranura, "tipo": "vector",
                                    "base": base, "longitud": filas})
            elif (tipo == TIPO_MATRIZ and 0 < filas <= MAX_FILAS_MATRIZ
                  and 0 < cols <= MAX_COLUMNAS_MATRIZ):
                nombre = ya or f"M{ranura}"
                if ya is None:
                    self.observar(nombre, "matriz", base, filas=filas, columnas=cols,
                                  origen="descriptor")
                encontradas.append({"nombre": nombre, "ranura": ranura, "tipo": "matriz",
                                    "base": base, "filas": filas, "columnas": cols})
        return encontradas

    def _palabra(self, direccion: int) -> int:
        valor, _estado = self.memoria.leer(direccion, 8, verificar_alineacion=False)
        return 0 if valor is None else valor & MASCARA_64

    def _dimensiones(self, spec: Dict[str, Any], resueltas: Dict[str, int]) -> Tuple[int, int, str]:
        """(filas, columnas, nota). Un vector es una matriz de 1 x N."""
        base = spec["base"]
        nota = ""
        if spec["tipo"] == "vector":
            n = spec.get("longitud")
            if isinstance(n, str):
                n = resueltas.get(n, 0)
            elif n is None:
                n = self._palabra(base - 8)
            n = a_entero_con_signo(n)
            if n < 0:
                n, nota = 0, "cabecera negativa"
            if n > MAX_ELEMENTOS_VECTOR:
                n, nota = MAX_ELEMENTOS_VECTOR, f"recortado a {MAX_ELEMENTOS_VECTOR}"
            return 1, n, nota
        f = spec.get("filas")
        c = spec.get("columnas")
        f = self._palabra(base - 16) if f is None else f
        c = self._palabra(base - 8) if c is None else c
        if not (0 <= f <= MAX_FILAS_MATRIZ and 0 <= c <= MAX_COLUMNAS_MATRIZ):
            nota = f"cabecera fuera de rango ({f} x {c})"
            f, c = min(max(f, 0), MAX_FILAS_MATRIZ), min(max(c, 0), MAX_COLUMNAS_MATRIZ)
            f = f if f <= MAX_FILAS_MATRIZ else 0
        return f, c, nota

    def instantanea(self, nombre: str, resueltas: Optional[Dict[str, int]] = None
                    ) -> Dict[str, Any]:
        """
        Lee de la RAM el estado actual de una estructura observada:

            {"nombre", "tipo", "base", "filas", "columnas", "origen", "nota",
             "palabras": [[...], ...],     # crudas de 64 bits, por filas
             "iniciales": [[...]] | None,  # las mismas al cargar el programa
             "zona": "vectores"}
        """
        self.exigir()
        spec = self.observadas[nombre]
        filas, columnas, nota = self._dimensiones(spec, resueltas or {})
        base = spec["base"]
        palabras = [[self._palabra(base + ((i * columnas + j) << 3)) for j in range(columnas)]
                    for i in range(filas)]
        iniciales = self._valores_al_cargar.get(nombre)
        if iniciales is not None and len(iniciales) == filas * columnas:
            iniciales_2d = [iniciales[i * columnas:(i + 1) * columnas] for i in range(filas)]
        else:
            iniciales_2d = None
        return {"nombre": nombre, "tipo": spec["tipo"], "base": base, "filas": filas,
                "columnas": columnas, "origen": spec.get("origen", ""), "nota": nota,
                "palabras": palabras, "iniciales": iniciales_2d, "zona": zona_de(base)}

    def instantaneas(self) -> List[Dict[str, Any]]:
        """Todas las observadas, resolviendo las longitudes que dependen de otra."""
        resueltas: Dict[str, int] = {}
        salida = []
        pendientes = list(self.observadas)
        # Primero las que no dependen de nadie, para poder resolver las demas.
        pendientes.sort(key=lambda n: isinstance(self.observadas[n].get("longitud"), str))
        for nombre in pendientes:
            foto = self.instantanea(nombre, resueltas)
            resueltas[nombre] = foto["filas"] * foto["columnas"]
            salida.append(foto)
        orden = list(self.observadas)
        salida.sort(key=lambda f: orden.index(f["nombre"]))
        return salida

    def direccion_de(self, nombre: str, fila: int, columna: int) -> int:
        """Dir(M[i][j]) = B + ((i * C + j) << 3); para un vector, fila = 0."""
        foto = self.instantanea(nombre, {})
        return foto["base"] + ((fila * foto["columnas"] + columna) << 3)

    # =======================================================================
    # Programa: compilar, cargar, ejecutar
    # =======================================================================

    def compilar(self, fuente: str, ruta: Optional[str] = None) -> Dict[str, Any]:
        """
        Preprocesa (resuelve `#include "estructuras.inc"`), ensambla y empaqueta
        el .e64 con el puente del Integrante 4. Los errores vuelven en el
        diccionario: nunca lanza por un programa mal escrito.
        """
        self.exigir()
        dirs = [str(DIR_INCLUDE)]
        if ruta:
            dirs.insert(0, str(pathlib.Path(ruta).resolve().parent))
        try:
            resultado = compilar_a_binario_e64(fuente, es_archivo=False, dirs_inclusion=dirs)
        except Exception as exc:
            self.compilado = None
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "bytes": 0,
                    "simbolos": {}, "lineas": 0}
        binario = resultado.binario_e64
        self.compilado = {"ok": True, "error": "", "binario": binario,
                          "bytes": len(resultado.codigo_maquina),
                          "simbolos": dict(binario.tabla_simbolos),
                          "lineas": len(resultado.preprocesamiento.texto.splitlines()),
                          "entry_point": binario.entry_point}
        self._simbolos_por_direccion = sorted(
            (dir_, nombre) for nombre, dir_ in binario.tabla_simbolos.items()
            if nombre != "_start"
        )
        return {k: v for k, v in self.compilado.items() if k != "binario"}

    @property
    def puede_ejecutar(self) -> bool:
        return self.cpu is not None and self.cpu.disponible

    def _conectar_perifericos(self) -> None:
        """
        La CPU compartida nace sin perifericos. Los programas de la Tarea 29
        escriben en la pantalla MMIO (0xFF001010), asi que se le conecta el
        subsistema real si existe. No cambia nada para los programas que no
        tocan el espacio MMIO.
        """
        cpu = getattr(self.cpu, "cpu", None)
        banco = getattr(self.mmio, "banco", None)
        if (cpu is not None and banco is not None and getattr(cpu, "perifericos", 1) is None
                and not getattr(self.mmio, "es_provisional", True)):
            cpu.perifericos = banco

    def cargar(self, reiniciar_ram: bool = True) -> Dict[str, Any]:
        """
        Deja la maquina lista para ejecutar:
          1. (opcional) RAM limpia, para que no queden restos de otra corrida;
          2. el .e64 entra por `CargadorEnigma.cargar_binario` en 0x00200000;
          3. SP = 0x00400000 (alineado a 8, como pide la libreria);
          4. se reescriben los datos de entrada del usuario;
          5. se fotografian los valores iniciales para compararlos al final.
        """
        self.exigir()
        if not self.compilado or not self.compilado.get("ok"):
            raise ValueError("compila primero un programa sin errores")
        if reiniciar_ram:
            self.memoria.reiniciar()
        if self.puede_ejecutar:
            self.cpu.reiniciar()
            self._conectar_perifericos()
        if self.mmio is not None:
            pantalla = getattr(self.mmio, "controlador_pantalla", None)
            if pantalla is not None and hasattr(pantalla, "reiniciar"):
                pantalla.reiniciar()

        informe = self.cargador.cargador.cargar_binario(
            self.compilado["binario"], direccion_destino=None, configurar_cpu=True)
        if self.registros is not None and self.registros.disponible:
            self.registros.escribir_nombre("SP", PILA_ESTRUCTURAS)

        if self.entradas:
            self._escribir_en_ram([e["descriptor"] for e in self.entradas.values()])
        informe["estructuras_escritas"] = len(self.entradas)

        self._ultimo_mnemonico = ""
        self._valores_al_cargar = {}
        for foto in self.instantaneas():
            self._valores_al_cargar[foto["nombre"]] = [p for fila in foto["palabras"]
                                                       for p in fila]
        return informe

    def etiqueta_de(self, direccion: int) -> str:
        """La subrutina o etiqueta mas cercana por debajo de una direccion."""
        mejor = ""
        for dir_, nombre in self._simbolos_por_direccion:
            if dir_ > direccion:
                break
            if dir_ >= 0x00200000 and dir_ < BASE_CABECERAS:
                mejor = nombre
        return mejor

    def _estado(self, accesos: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        estado = self.cpu.estado() if self.puede_ejecutar else {}
        registros = {}
        if self.registros is not None and self.registros.disponible:
            for nombre in ("R1", "R2", "R3", "R4", "R5", "SP", "BP", "PC"):
                registros[nombre] = self.registros.leer_nombre(nombre)
        pc = registros.get("PC", 0)
        return {
            "pc": pc,
            "etiqueta": self.etiqueta_de(pc),
            "mnemonico": estado.get("mnemonico") or self._ultimo_mnemonico,
            "instrucciones": estado.get("instrucciones", 0),
            "ciclos": estado.get("ciclos", 0),
            "detenido": estado.get("detenido", True),
            "registros": registros,
            "accesos": accesos or [],
            "error": estado.get("error", ""),
        }

    def estado(self) -> Dict[str, Any]:
        return self._estado()

    def avanzar(self, instrucciones: int = 1) -> Dict[str, Any]:
        """
        Ejecuta hasta `instrucciones` instrucciones completas y devuelve el
        estado, con la lista de accesos a memoria de datos que hicieron
        (para que el panel ilumine la celda leida o escrita).
        """
        if not self.puede_ejecutar:
            raise ServicioNoDisponible(
                "Ejecutar necesita la Unidad de Control (enigma64/cpu.py, Integrante 3).")
        accesos: List[Dict[str, Any]] = []
        for _ in range(max(1, instrucciones)):
            acceso = self._una_instruccion()
            if acceso is False:
                break
            if acceso:
                accesos.append(acceso)
        return self._estado(accesos[-12:])

    def _una_instruccion(self) -> Union[Dict[str, Any], None, bool]:
        """
        Avanza la FSM fase a fase hasta completar UNA instruccion. Justo antes
        de la fase MEMORY se anota la direccion efectiva (micro-registro Z) si
        la instruccion es LOAD/STORE: es la celda que el panel ilumina.
        Devuelve False si la CPU ya estaba detenida.
        """
        estado = self.cpu.estado()
        if estado["detenido"]:
            return False
        inicial = estado["instrucciones"]
        acceso = None
        visto = ""
        for _ in range(16):  # holgura sobre las cinco fases de la FSM
            visto = estado.get("mnemonico") or visto
            if estado["fase"] == "MEMORY":
                mnemonico = (estado.get("mnemonico") or "").upper()
                if mnemonico in _LECTURAS or mnemonico in _ESCRITURAS:
                    acceso = {
                        "tipo": "escritura" if mnemonico in _ESCRITURAS else "lectura",
                        "direccion": estado["micro"].get("Z", 0) & MASCARA_64,
                        "mnemonico": mnemonico,
                    }
            estado = self.cpu.paso()
            if estado["instrucciones"] > inicial or estado["detenido"]:
                break
        self._ultimo_mnemonico = visto or estado.get("mnemonico") or ""
        return acceso

    def ejecutar_hasta_fin(self, max_instrucciones: int = 500_000) -> Dict[str, Any]:
        """Corre hasta HLT (o hasta el presupuesto) sin parar a dibujar."""
        if not self.puede_ejecutar:
            raise ServicioNoDisponible(
                "Ejecutar necesita la Unidad de Control (enigma64/cpu.py, Integrante 3).")
        hechas = 0
        while not self.cpu.estado()["detenido"] and hechas < max_instrucciones:
            self.cpu.paso_instruccion()
            hechas += 1
        estado = self._estado()
        estado["agotado"] = not estado["detenido"]
        return estado

    def salida_mmio(self) -> str:
        """Lo que el programa escribio en la pantalla CRT (0xFF001010)."""
        pantalla = getattr(self.mmio, "controlador_pantalla", None)
        if pantalla is None or not hasattr(pantalla, "obtener_texto"):
            return ""
        try:
            return pantalla.obtener_texto().rstrip()
        except Exception:  # pragma: no cover - pantalla de terceros
            return ""

    # -- utilidades puras expuestas al panel --------------------------------

    parsear_vector = staticmethod(parsear_vector)
    parsear_matriz = staticmethod(parsear_matriz)
    formatear = staticmethod(formatear_palabra)

    # -- diagnostico --------------------------------------------------------

    def zonas(self) -> List[Dict[str, Any]]:
        return [dict(z) for z in ZONAS]


def _resumen(fuente: str) -> str:
    """Primera linea descriptiva del comentario de cabecera de un .asm."""
    for linea in fuente.splitlines()[:12]:
        texto = linea.strip().lstrip(";").strip()
        if texto and not set(texto) <= set("=-") and " - " in texto:
            return texto.split(" - ", 1)[1]
    return "Programa que usa la libreria estructuras.inc"
