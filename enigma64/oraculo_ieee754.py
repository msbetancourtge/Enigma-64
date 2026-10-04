"""
Módulo Utilitario de Validación IEEE 754 y Oráculo de Raíz Cuadrada (Enigma-64).

Responsabilidad del Integrante 6 (Tarea 17 - Aritmética de Punto Flotante):
  1. Desglose analítico de números de punto flotante en formato IEEE 754 binary64
     (signo, exponente con sesgo 1023, mantisa de 52 bits con bit implícito 53,
     clasificación de clases normales, subnormales, ceros con signo, infinitos y NaNs).
  2. Conversiones bidireccionales bit a bit de precisión absoluta con struct.
  3. Simulador formal del método numérico de Newton-Raphson para la estimación de
     la raíz cuadrada conforme a la especificación de Ricardo Peña en la página 26
     del libro 'De Euclides a JAVA'.
  4. Oráculo de referencia canónico para validación de la subrutina ensamblador FSQRT.
  5. Cálculo de distancias en ULPs (Units in the Last Place) y generación de la batería
     exhaustiva de casos de prueba.

Arquitectura: Enigma-64 (Noctua Systems) - Big-Endian de 64 bits.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ==============================================================================
# 1. CONSTANTES DEL ESTÁNDAR IEEE 754 (Doble Precisión - binary64)
# ==============================================================================

EXP_BITS: int = 11
FRAC_BITS: int = 52
TOTAL_BITS: int = 64

EXP_BIAS: int = 1023
EXP_MASK: int = 0x7FF
FRAC_MASK: int = 0x000F_FFFF_FFFF_FFFF
IMPLICIT_BIT: int = 0x0010_0000_0000_0000
SIGN_BIT: int = 0x8000_0000_0000_0000
QUIET_NAN_BIT: int = 0x0008_0000_0000_0000
MASK64: int = 0xFFFF_FFFF_FFFF_FFFF

# Patrones canónicos de 64 bits
POS_ZERO: int = 0x0000_0000_0000_0000
NEG_ZERO: int = 0x8000_0000_0000_0000
POS_INFINITY: int = 0x7FF0_0000_0000_0000
NEG_INFINITY: int = 0xFFF0_0000_0000_0000
CANONICAL_NAN: int = 0x7FF8_0000_0000_0000


# ==============================================================================
# 2. CONVERSIONES Y TIPOS DE DATOS
# ==============================================================================

class ClaseIEEE754(str, Enum):
    """Clasificación formal de un patrón de 64 bits según IEEE 754."""
    CERO_POSITIVO = "+0.0"
    CERO_NEGATIVO = "-0.0"
    SUBNORMAL_POSITIVO = "+subnormal"
    SUBNORMAL_NEGATIVO = "-subnormal"
    NORMAL_POSITIVO = "+normal"
    NORMAL_NEGATIVO = "-normal"
    INFINITO_POSITIVO = "+infinito"
    INFINITO_NEGATIVO = "-infinito"
    QNAN = "qNaN (silencioso)"
    SNAN = "sNaN (señalizador)"


def float_a_bits(val: float) -> int:
    """Convierte un flotante de Python a su patrón binario IEEE 754 de 64 bits."""
    return struct.unpack(">Q", struct.pack(">d", val))[0]


def bits_a_float(bits: int) -> float:
    """Convierte un patrón binario de 64 bits a un número flotante de Python."""
    return struct.unpack(">d", struct.pack(">Q", bits & MASK64))[0]


def componer_ieee754(signo: int, exponente: int, fraccion: int) -> int:
    """
    Ensambla signo (1b), exponente (11b) y fracción (52b) en un patrón IEEE 754.
    """
    s = (signo & 1) << 63
    e = (exponente & EXP_MASK) << 52
    f = fraccion & FRAC_MASK
    return s | e | f


@dataclass(frozen=True)
class DesgloseIEEE754:
    """Desglose detallado de los campos de un número IEEE 754 binary64."""
    bits: int
    valor: float
    signo: int
    exponente: int
    exponente_real: int
    fraccion: int
    mantisa_efectiva: int
    bit_implicito: int
    clase: ClaseIEEE754
    es_nan: bool
    es_inf: bool
    es_cero: bool
    es_subnormal: bool
    es_negativo: bool
    carga_util_nan: Optional[int] = None

    def __str__(self) -> str:
        return (
            f"DesgloseIEEE754(valor={self.valor!r}, clase={self.clase.value}, "
            f"hex=0x{self.bits:016X}, S={self.signo}, E={self.exponente} "
            f"(real={self.exponente_real}), frac=0x{self.fraccion:013X})"
        )


def descomponer_ieee754(val: float | int) -> DesgloseIEEE754:
    """
    Analiza un float o un entero de 64 bits y extrae sus campos IEEE 754.
    """
    if isinstance(val, float):
        u64 = float_a_bits(val)
        flt_val = val
    else:
        u64 = val & MASK64
        flt_val = bits_a_float(u64)

    signo = (u64 >> 63) & 1
    exponente = (u64 >> 52) & EXP_MASK
    fraccion = u64 & FRAC_MASK
    es_neg = signo == 1

    carga_util = None
    if exponente == EXP_MASK:
        es_inf = fraccion == 0
        es_nan = fraccion != 0
        es_cero = False
        es_subnormal = False
        bit_implicito = 0
        mantisa_efectiva = fraccion
        exponente_real = exponente - EXP_BIAS
        if es_inf:
            clase = ClaseIEEE754.INFINITO_NEGATIVO if es_neg else ClaseIEEE754.INFINITO_POSITIVO
        else:
            carga_util = fraccion & ~QUIET_NAN_BIT
            es_quiet = bool(fraccion & QUIET_NAN_BIT)
            clase = ClaseIEEE754.QNAN if es_quiet else ClaseIEEE754.SNAN
    elif exponente == 0:
        es_inf = False
        es_nan = False
        es_cero = fraccion == 0
        es_subnormal = fraccion != 0
        bit_implicito = 0
        mantisa_efectiva = fraccion
        exponente_real = -1022  # Subnormales tienen exponente efectivo -1022
        if es_cero:
            clase = ClaseIEEE754.CERO_NEGATIVO if es_neg else ClaseIEEE754.CERO_POSITIVO
        else:
            clase = ClaseIEEE754.SUBNORMAL_NEGATIVO if es_neg else ClaseIEEE754.SUBNORMAL_POSITIVO
    else:
        es_inf = False
        es_nan = False
        es_cero = False
        es_subnormal = False
        bit_implicito = 1
        mantisa_efectiva = IMPLICIT_BIT | fraccion
        exponente_real = exponente - EXP_BIAS
        clase = ClaseIEEE754.NORMAL_NEGATIVO if es_neg else ClaseIEEE754.NORMAL_POSITIVO

    return DesgloseIEEE754(
        bits=u64,
        valor=flt_val,
        signo=signo,
        exponente=exponente,
        exponente_real=exponente_real,
        fraccion=fraccion,
        mantisa_efectiva=mantisa_efectiva,
        bit_implicito=bit_implicito,
        clase=clase,
        es_nan=es_nan,
        es_inf=es_inf,
        es_cero=es_cero,
        es_subnormal=es_subnormal,
        es_negativo=es_neg,
        carga_util_nan=carga_util,
    )


# ==============================================================================
# 3. SIMULADOR DE NEWTON-RAPHSON (Ricardo Peña, 'De Euclides a JAVA', pág. 26)
# ==============================================================================

@dataclass
class PasoNewtonRaphson:
    """Registro de una iteración en el método de Newton-Raphson."""
    iteracion: int
    x_k: float
    x_k_bits: int
    cociente: float           # a / x_k (FDIV)
    suma: float               # x_k + (a / x_k) (FADD)
    x_sig: float              # 0.5 * suma (FMUL)
    x_sig_bits: int
    diff_absoluta: float      # |x_{k+1} - x_k|
    diff_relativa: float      # |x_{k+1} - x_k| / x_{k+1}
    distancia_ulp: int        # Distancia en ULPs al valor exacto math.sqrt(a)


@dataclass
class ResultadoNewtonRaphson:
    """Resultado completo de la simulación del método de Newton-Raphson."""
    entrada: float
    entrada_bits: int
    raiz_estimada: float
    raiz_estimada_bits: int
    raiz_exacta: float
    raiz_exacta_bits: int
    convergido: bool
    iteraciones: List[PasoNewtonRaphson] = field(default_factory=list)
    total_iteraciones: int = 0
    caso_especial: Optional[str] = None
    mensaje: str = ""


def calcular_semilla_inicial(a: float, estrategia: str = "peña") -> float:
    """
    Calcula la aproximación inicial x_0 para el método de Newton-Raphson.

    Estrategias:
      * 'peña': Método textual de Ricardo Peña: x_0 = a / 2.0 si a >= 1.0, o 1.0 si a < 1.0.
      * 'uno': Semilla fija x_0 = 1.0.
      * 'exponente': Semilla rápida IEEE 754 ajustando el campo de exponente a la mitad:
        E(x_0) = ((E(a) - 1023) >> 1) + 1023. Converge en 4-5 iteraciones.
    """
    if a <= 0.0:
        return 0.0

    if estrategia == "uno":
        return 1.0
    elif estrategia == "exponente":
        u64 = float_a_bits(a)
        exp = (u64 >> 52) & EXP_MASK
        frac = u64 & FRAC_MASK
        exp_real = exp - EXP_BIAS
        exp_nuevo = (exp_real >> 1) + EXP_BIAS
        # Semilla con mantisa media para evitar desbordes
        bits_semilla = (exp_nuevo << 52) | (frac >> 1)
        return bits_a_float(bits_semilla)
    else:
        # Por defecto: estrategia Peña
        return (a / 2.0) if a >= 1.0 else 1.0


def simular_newton_raphson(
    a: float | int,
    tolerancia: float = 1e-15,
    max_iter: int = 60,
    estrategia_semilla: str = "peña",
) -> ResultadoNewtonRaphson:
    """
    Ejecuta el método numérico de Newton-Raphson para la estimación de la raíz
    cuadrada tal como se describe en la página 26 del libro 'De Euclides a JAVA'
    del Profesor Ricardo Peña.

    Fórmula iterativa:
        x_{k+1} = 0.5 * (x_k + a / x_k)
    """
    if isinstance(a, int):
        u64_in = a & MASK64
        flt_in = bits_a_float(u64_in)
    else:
        flt_in = a
        u64_in = float_a_bits(flt_in)

    desglose = descomponer_ieee754(u64_in)

    # 1. Tratamiento de casos especiales IEEE 754
    if desglose.es_nan:
        qnan_bits = u64_in | QUIET_NAN_BIT
        return ResultadoNewtonRaphson(
            entrada=flt_in,
            entrada_bits=u64_in,
            raiz_estimada=bits_a_float(qnan_bits),
            raiz_estimada_bits=qnan_bits,
            raiz_exacta=math.nan,
            raiz_exacta_bits=qnan_bits,
            convergido=True,
            total_iteraciones=0,
            caso_especial="NaN",
            mensaje="Operando es NaN: se propaga NaN silenciado.",
        )

    if desglose.es_cero:
        # sqrt(+0.0) = +0.0, sqrt(-0.0) = -0.0
        return ResultadoNewtonRaphson(
            entrada=flt_in,
            entrada_bits=u64_in,
            raiz_estimada=flt_in,
            raiz_estimada_bits=u64_in,
            raiz_exacta=flt_in,
            raiz_exacta_bits=u64_in,
            convergido=True,
            total_iteraciones=0,
            caso_especial="Cero con signo",
            mensaje=f"Cero con signo: sqrt({flt_in}) = {flt_in}.",
        )

    if desglose.es_negativo:
        # Raíz de negativo es inválida -> NaN canónico
        return ResultadoNewtonRaphson(
            entrada=flt_in,
            entrada_bits=u64_in,
            raiz_estimada=math.nan,
            raiz_estimada_bits=CANONICAL_NAN,
            raiz_exacta=math.nan,
            raiz_exacta_bits=CANONICAL_NAN,
            convergido=True,
            total_iteraciones=0,
            caso_especial="Negativo",
            mensaje="Número negativo: operación inválida, produce NaN canónico.",
        )

    if desglose.es_inf:
        return ResultadoNewtonRaphson(
            entrada=flt_in,
            entrada_bits=u64_in,
            raiz_estimada=math.inf,
            raiz_estimada_bits=POS_INFINITY,
            raiz_exacta=math.inf,
            raiz_exacta_bits=POS_INFINITY,
            convergido=True,
            total_iteraciones=0,
            caso_especial="+Infinito",
            mensaje="Infinito positivo: sqrt(+inf) = +inf.",
        )

    # 2. Iteración numérica ordinaria
    exacta = math.sqrt(flt_in)
    exacta_bits = float_a_bits(exacta)

    x_k = calcular_semilla_inicial(flt_in, estrategia_semilla)
    historial: List[PasoNewtonRaphson] = []
    convergido = False

    for k in range(1, max_iter + 1):
        x_k_bits = float_a_bits(x_k)
        cociente = flt_in / x_k            # FDIV
        suma = x_k + cociente              # FADD
        x_sig = 0.5 * suma                 # FMUL
        x_sig_bits = float_a_bits(x_sig)

        diff = abs(x_sig - x_k)
        diff_rel = diff / x_sig if x_sig != 0 else diff
        ulp_dist = abs(x_sig_bits - exacta_bits)

        paso = PasoNewtonRaphson(
            iteracion=k,
            x_k=x_k,
            x_k_bits=x_k_bits,
            cociente=cociente,
            suma=suma,
            x_sig=x_sig,
            x_sig_bits=x_sig_bits,
            diff_absoluta=diff,
            diff_relativa=diff_rel,
            distancia_ulp=ulp_dist,
        )
        historial.append(paso)

        # Criterio de parada: cuando los bits se estabilizan o la diferencia relativa cae bajo epsilon
        if x_sig_bits == x_k_bits or diff_rel <= tolerancia:
            convergido = True
            x_k = x_sig
            break

        # También verificar oscilación en el último bit (LSB)
        if abs(x_sig_bits - x_k_bits) <= 1 and k >= 3:
            convergido = True
            x_k = x_sig
            break

        x_k = x_sig

    return ResultadoNewtonRaphson(
        entrada=flt_in,
        entrada_bits=u64_in,
        raiz_estimada=x_k,
        raiz_estimada_bits=float_a_bits(x_k),
        raiz_exacta=exacta,
        raiz_exacta_bits=exacta_bits,
        convergido=convergido,
        iteraciones=historial,
        total_iteraciones=len(historial),
        mensaje=(
            f"Convergencia alcanzada en {len(historial)} iteraciones."
            if convergido
            else f"Límite de {max_iter} iteraciones alcanzado."
        ),
    )


# ==============================================================================
# 4. ORÁCULO CANÓNICO DE REFERENCIA IEEE 754 (FSQRT)
# ==============================================================================

class OraculoIEEE754:
    """
    Oráculo de referencia para operaciones IEEE 754 binary64 en Enigma-64.
    """

    @staticmethod
    def fsqrt_float(a: float) -> float:
        """Calcula la raíz cuadrada con semántica formal IEEE 754."""
        if math.isnan(a):
            return a
        if a == 0.0:
            return a  # Preserva +0.0 y -0.0
        if a < 0.0:
            return math.nan
        if math.isinf(a):
            return math.inf
        return math.sqrt(a)

    @classmethod
    def fsqrt_bits(cls, a_bits: int) -> int:
        """
        Calcula el patrón de 64 bits esperado de FSQRT para cualquier entrada.
        """
        a_bits &= MASK64
        desglose = descomponer_ieee754(a_bits)

        if desglose.es_nan:
            return a_bits | QUIET_NAN_BIT
        if desglose.es_cero:
            return a_bits  # Conserva +0.0 o -0.0
        if desglose.es_negativo:
            return CANONICAL_NAN
        if desglose.es_inf:
            return POS_INFINITY

        flt_val = bits_a_float(a_bits)
        res_flt = math.sqrt(flt_val)
        return float_a_bits(res_flt)

    @staticmethod
    def distancia_ulps(bits_a: int, bits_b: int) -> int:
        """
        Calcula la distancia en ULPs (Unidades en el Último Lugar) entre dos
        patrones de punto flotante de 64 bits de igual signo.
        """
        bits_a &= MASK64
        bits_b &= MASK64

        # Signos distintos (salvo ceros) están a distancia infinita
        signo_a = (bits_a >> 63) & 1
        signo_b = (bits_b >> 63) & 1
        if signo_a != signo_b:
            if (bits_a & ~SIGN_BIT) == 0 and (bits_b & ~SIGN_BIT) == 0:
                return 0  # +0.0 y -0.0 están a 0 ULPs
            return 0x7FFF_FFFF_FFFF_FFFF

        return abs(bits_a - bits_b)

    @classmethod
    def validar_fsqrt(
        cls,
        entrada_bits: int,
        obtenido_bits: int,
        max_ulps: int = 1,
    ) -> Tuple[bool, str]:
        """
        Verifica si el resultado obtenido por la subrutina FSQRT coincide con
        la especificación formal del oráculo IEEE 754.
        """
        esperado_bits = cls.fsqrt_bits(entrada_bits)
        entrada_bits &= MASK64
        obtenido_bits &= MASK64

        desglose_in = descomponer_ieee754(entrada_bits)

        # Ceros con signo (+0.0 y -0.0)
        if desglose_in.es_cero:
            if obtenido_bits == esperado_bits:
                return True, f"Correcto: cero con signo preservado (0x{obtenido_bits:016X})."
            return False, (
                f"Fallo en cero: esperado 0x{esperado_bits:016X}, "
                f"obtenido 0x{obtenido_bits:016X}."
            )

        # Casos NaN y Negativos estrictos (< 0)
        if desglose_in.es_nan or desglose_in.es_negativo:
            es_nan_obtenido = bool(
                ((obtenido_bits >> 52) & EXP_MASK) == EXP_MASK
                and (obtenido_bits & FRAC_MASK) != 0
            )
            if es_nan_obtenido:
                return True, "Correcto: resultado es NaN como se esperaba."
            return False, f"Fallo: se esperaba NaN pero se obtuvo 0x{obtenido_bits:016X}."

        # Infinito positivo
        if desglose_in.es_inf and not desglose_in.es_negativo:
            if obtenido_bits == POS_INFINITY:
                return True, "Correcto: +infinito preservado."
            return False, f"Fallo en +inf: obtenido 0x{obtenido_bits:016X}."

        # Números finitos positivos
        distancia = cls.distancia_ulps(obtenido_bits, esperado_bits)
        if distancia <= max_ulps:
            return True, (
                f"Correcto: coincidencia con el oráculo dentro de la tolerancia "
                f"(distancia = {distancia} ULP, max={max_ulps})."
            )

        return False, (
            f"Discrepancia numérica: obtenido 0x{obtenido_bits:016X} "
            f"({bits_a_float(obtenido_bits)}), esperado 0x{esperado_bits:016X} "
            f"({bits_a_float(esperado_bits)}), distancia = {distancia} ULPs."
        )


# ==============================================================================
# 5. GENERADOR DE CASOS DE PRUEBA FORMALES
# ==============================================================================

def generar_catalogo_casos_prueba() -> List[Dict[str, Any]]:
    """
    Genera el catálogo canónico de casos de prueba para validar la implementación
    del algoritmo de raíz cuadrada (FSQRT) en Enigma-64.
    """
    casos = [
        # --- Categoría 1: Enteros y Cuadrados Perfectos ---
        {"nombre": "cero_positivo", "valor": 0.0, "categoria": "ceros"},
        {"nombre": "cero_negativo", "valor": -0.0, "categoria": "ceros"},
        {"nombre": "uno", "valor": 1.0, "categoria": "exactos"},
        {"nombre": "cuatro", "valor": 4.0, "categoria": "exactos"},
        {"nombre": "nueve", "valor": 9.0, "categoria": "exactos"},
        {"nombre": "dieciseis", "valor": 16.0, "categoria": "exactos"},
        {"nombre": "veinticinco", "valor": 25.0, "categoria": "exactos"},
        {"nombre": "cien", "valor": 100.0, "categoria": "exactos"},
        {"nombre": "diez_mil", "valor": 10000.0, "categoria": "exactos"},
        {"nombre": "potencia_2_par_4", "valor": 16.0, "categoria": "potencias"},
        {"nombre": "potencia_2_par_20", "valor": float(2**20), "categoria": "potencias"},
        {"nombre": "potencia_2_par_52", "valor": float(2**52), "categoria": "potencias"},

        # --- Categoría 2: Fraccionarios y Decimales Exactos ---
        {"nombre": "cuarto (0.25)", "valor": 0.25, "categoria": "fraccionarios"},
        {"nombre": "dieciseisavo (0.0625)", "valor": 0.0625, "categoria": "fraccionarios"},
        {"nombre": "dos (irracional sqrt(2))", "valor": 2.0, "categoria": "irracionales"},
        {"nombre": "tres (irracional sqrt(3))", "valor": 3.0, "categoria": "irracionales"},
        {"nombre": "medio (0.5)", "valor": 0.5, "categoria": "fraccionarios"},
        {"nombre": "diez (10.0)", "valor": 10.0, "categoria": "decimales"},

        # --- Categoría 3: Constantes Matemáticas ---
        {"nombre": "pi", "valor": math.pi, "categoria": "constantes"},
        {"nombre": "e", "valor": math.e, "categoria": "constantes"},

        # --- Categoría 4: Magnitudes Extremas ---
        {"nombre": "grande_1e50", "valor": 1e50, "categoria": "escalas"},
        {"nombre": "grande_1e150", "valor": 1e150, "categoria": "escalas"},
        {"nombre": "pequeno_1e-50", "valor": 1e-50, "categoria": "escalas"},
        {"nombre": "pequeno_1e-150", "valor": 1e-150, "categoria": "escalas"},

        # --- Categoría 5: Subnormales y Casos Límite ---
        {"nombre": "subnormal_min", "bits": 0x0000_0000_0000_0001, "categoria": "subnormales"},
        {"nombre": "subnormal_medio", "bits": 0x0000_8000_0000_0000, "categoria": "subnormales"},
        {"nombre": "menor_normal", "bits": 0x0010_0000_0000_0000, "categoria": "subnormales"},

        # --- Categoría 6: Casos Especiales IEEE 754 ---
        {"nombre": "negativo_uno (-1.0)", "valor": -1.0, "categoria": "especiales"},
        {"nombre": "negativo_cuatro (-4.0)", "valor": -4.0, "categoria": "especiales"},
        {"nombre": "infinito_positivo (+inf)", "valor": math.inf, "categoria": "especiales"},
        {"nombre": "infinito_negativo (-inf)", "valor": -math.inf, "categoria": "especiales"},
        {"nombre": "nan_canonico", "bits": CANONICAL_NAN, "categoria": "especiales"},
        {"nombre": "snan", "bits": 0x7FF0_0000_0000_0001, "categoria": "especiales"},
    ]

    resultado = []
    for item in casos:
        if "bits" in item:
            u64 = item["bits"]
            flt_val = bits_a_float(u64)
        else:
            flt_val = item["valor"]
            u64 = float_a_bits(flt_val)

        esperado_bits = OraculoIEEE754.fsqrt_bits(u64)
        esperado_flt = bits_a_float(esperado_bits)

        resultado.append({
            "nombre": item["nombre"],
            "categoria": item["categoria"],
            "entrada_float": flt_val,
            "entrada_bits": u64,
            "esperado_bits": esperado_bits,
            "esperado_float": esperado_flt,
            "hex_entrada": f"0x{u64:016X}",
            "hex_esperado": f"0x{esperado_bits:016X}",
        })

    return resultado
