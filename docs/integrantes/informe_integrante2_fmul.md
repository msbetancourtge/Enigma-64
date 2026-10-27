# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Tarea 10:** Emulación de Computador Von Neumann (Enigma-64 — Noctua Systems)  
**Documento Técnico — Módulo FPU: FMUL (multiplicación IEEE 754 binary64)**  
**Autor:** Tomás Garzón (Integrante 2)

---

## 1. Alcance

`FMUL` multiplica dos flotantes IEEE 754 de doble precisión sobre la CPU emulada, usando solo el ISA entero de Enigma-64. Archivos:

| Archivo | Contenido |
| :--- | :--- |
| `enigma64/fmul.s` | `FMUL`, `FPU_MUL128` (64×64→128) y `FPU_NORMALIZAR_SUBNORMAL` |
| `enigma64/fpu.py` | Carga `fpu.s` + `fmul.s` como una sola unidad; métodos `multiplicar()` y `multiplicar_bits()` |
| `tests/test_fmul.py` | Tabla de 24 casos en hex, prueba diferencial aleatoria (300 casos), prueba de `FPU_MUL128` |

## 2. Restricciones del ISA que guían el diseño

| Hecho del ISA (verificado en `cpu.py`, `alu.py`, `ensamblador.py`) | Consecuencia en FMUL |
| :--- | :--- |
| Palabra de 64 bits; registros R0–R7, con R0 = 0, R5 = RV, R6 = SP, R7 = BP | Solo **R1–R5** son de trabajo: las variables viven en un marco `ENTER 64` |
| `MUL` conserva solo los **64 bits bajos** | Producto de 106 bits armado con 4 productos parciales de 32×32 (`FPU_MUL128`) |
| `SHL`/`SHR` solo con **corrimiento inmediato** | Corrimientos variables (subnormales) con bucles de 1 bit |
| Inmediatos de 16 bits con extensión de signo | Constantes grandes con `ADDI` + `SHL` (p. ej. `0x7FF << 52`) |
| `CMP a, b`: C = 1 si `a < b` sin signo (préstamo); N = bit 63 de `a − b` | `JC` = menor sin signo (detección de NaN); `JN`/`JP` = comparación con signo de exponentes |
| Convención de FADD: R1 = A, R2 = B, resultado en R5 | FMUL usa la misma |

## 3. Interfaz

| | Registro | Contenido |
| :--- | :--- | :--- |
| Entrada | R1 | A (patrón binary64) |
| Entrada | R2 | B (patrón binary64) |
| Salida | R5 (RV) | A × B (patrón binary64) |
| Modificados | R1–R4 | El llamador debe guardarlos si los necesita |
| Preservados | R6 (SP), R7 (BP) | Restaurados con `LEAVE` |

Subrutinas del compañero que se reutilizan tal cual (`fpu.s`):

* `FPU_DESEMPAQUETAR`: R1 → R2 = S, R3 = E sesgado, R4 = M de 53 bits (bit 52 implícito si E ≠ 0). Usa R5.
* `FPU_EMPAQUETAR`: R2 = S, R3 = E ∈ [1, 2046], R4 = M con bit 52 → R5. No redondea ni empaqueta subnormales (devuelve 0 si E = 0), por eso FMUL arma los subnormales por su cuenta.

## 4. Algoritmo

1. **Signo:** `S = (A XOR B) >> 63`.
2. **Casos especiales** sobre `|x| = x` sin bit 63 e `INF = 0x7FF0000000000000`:

   | Condición | Resultado |
   | :--- | :--- |
   | `|A| > INF` (A es NaN) | A con el bit 51 activo (NaN silenciado, conserva carga útil) |
   | `|B| > INF` | B silenciado |
   | Inf × 0 o 0 × Inf | `0x7FF8000000000000` (NaN canónico, operación inválida) |
   | Inf × finito ≠ 0, Inf × Inf | Inf con signo S |
   | 0 × finito | 0 con signo S |

3. **Desempaquetado:** `FPU_DESEMPAQUETAR` + `FPU_NORMALIZAR_SUBNORMAL`. Un subnormal (E = 0) toma exponente efectivo 1 y se corre a la izquierda hasta tener el bit 52, decrementando E (puede quedar ≤ 0).
4. **Exponente:** `E_R = E_A + E_B − 1023`, como entero con signo de 64 bits. Su rango real (≈ −1125 … 3071) no desborda el registro, así que la verificación de overflow/underflow se hace después de normalizar.
5. **Producto:** `P = M_A × M_B ∈ [2^104, 2^106)` con `FPU_MUL128`:

   ```
   x = xh·2^32 + xl,  y = yh·2^32 + yl
   p0 = xl·yl   p1 = xh·yl   p2 = xl·yh   p3 = xh·yh      (cada uno < 2^64)
   mid = (p0 >> 32) + lo32(p1) + lo32(p2)                 (< 3·2^32: sin acarreo)
   lo  = (mid << 32) | lo32(p0)
   hi  = p3 + (p1 >> 32) + (p2 >> 32) + (mid >> 32)
   ```
   Ninguna suma desborda, así que no depende de la bandera C.
6. **Mantisa de trabajo:** `T = P >> 49 = (hi << 15) | (lo >> 49)`, y el bit 0 de T se hace OR con "algún bit de `lo[48:0]` ≠ 0" (sticky):

   ```
   bit:  56 | 55 ........ 3 | 2 | 1 | 0
         ov | significando  | G | R | S
   ```
7. **Normalización:** si el bit 56 está activo (P ≥ 2^105, el producto quedó en [2, 4)): `T = (T >> 1) | (T & 1)` y `E_R += 1`.
8. **Subdesbordamiento:** si `E_R ≤ 0`, `T` se corre `1 − E_R` posiciones (máximo 60) conservando el sticky, y `E_R = 0` (resultado subnormal o ±0). **Los subnormales están soportados** en entrada y salida (subdesbordamiento gradual).
9. **Redondeo al par más cercano:** `M = (T + 3 + lsb) >> 3`, con `lsb` = bit 3 de T. Equivale a "subir si G·(R + S + lsb)": los 3 bits bajos más 3 + lsb llegan a 8 solo si GRS > 100, o GRS = 100 y lsb = 1.
10. **Acarreo del redondeo:** si `M = 2^53`, `M >>= 1`, `E_R += 1`.
11. **Desbordamiento:** si `E_R ≥ 2047` → Inf con signo S.
12. **Empaquetado:** normales con `FPU_EMPAQUETAR`; subnormales con `S << 63 | M`. Si un subnormal redondea a `M = 2^52`, ese bit cae en el campo de exponente y produce exactamente el menor normal.

## 5. Asignación de registros y memoria

**FMUL (marco `ENTER 64`):**

| Ubicación | Contenido |
| :--- | :--- |
| `[BP−8]`, `[BP−16]` | A y B originales (para devolver NaN y desempaquetar) |
| `[BP−24]` | S_R |
| `[BP−32]` | E_A, luego E_R |
| `[BP−40]`, `[BP−56]` | M_A, M_B |
| `[BP−48]` | E_B |
| R3 / R4 / R5 en casos especiales | \|A\| / \|B\| / constante INF |
| R4 tras el producto | T (mantisa de trabajo), luego M redondeada |
| R3 tras el producto | E_R |
| R1, R2 | Temporales: máscaras, contador de corrimientos, lsb |

**FPU_MUL128 (marco `ENTER 16`):** R1 = xl, R2 = yl, R3 = xh → p1 → mid, R4 = yh → p2 → lo, R5 = p0 → hi; `[BP−8]` = p3 / hi parcial, `[BP−16]` = p0.

## 6. Oráculo de referencia en Python

Los `float` de Python son binary64 con redondeo al par más cercano, así que basta con `struct`:

```python
import struct

def ieee(x: float) -> int:
    return struct.unpack(">Q", struct.pack(">d", x))[0]

def flt(u: int) -> float:
    return struct.unpack(">d", struct.pack(">Q", u))[0]

def oraculo_fmul(a: int, b: int) -> int:
    """Patrón binary64 esperado de A * B (A y B como enteros de 64 bits)."""
    return ieee(flt(a) * flt(b))

# Comparación con el emulador:
from enigma64.fpu import EmuladorFPUEnigma64
fpu = EmuladorFPUEnigma64()
a, b = 0x3FB999999999999A, 0x3FC999999999999A          # 0.1, 0.2
assert fpu.multiplicar_bits(a, b) == oraculo_fmul(a, b)  # 0x3F947AE147AE147C
```

Para NaN se compara con `math.isnan`, porque IEEE 754 no fija el signo ni la carga útil.

## 7. Tabla de casos de prueba

Todos verificados en el emulador (`tests/test_fmul.py::test_tabla_casos`) y contra el oráculo.

| # | Caso | A | B | Esperado |
| :-: | :--- | :--- | :--- | :--- |
| 1 | normal × normal: 1.5 × 2.5 | `3FF8000000000000` | `4004000000000000` | `400E000000000000` (3.75) |
| 2 | signo: −3.0 × 4.0 | `C008000000000000` | `4010000000000000` | `C028000000000000` (−12) |
| 3 | signo: −2.0 × −0.5 | `C000000000000000` | `BFE0000000000000` | `3FF0000000000000` (1.0) |
| 4 | identidad: 1.0 × π | `3FF0000000000000` | `400921FB54442D18` | `400921FB54442D18` |
| 5 | potencias de 2: 2^10 × 2^−3 | `4090000000000000` | `3FC0000000000000` | `4060000000000000` (128) |
| 6 | normalización (producto ≥ 2): 1.75 × 1.75 | `3FFC000000000000` | `3FFC000000000000` | `4008800000000000` (3.0625) |
| 7 | redondeo inexacto: 0.1 × 0.2 | `3FB999999999999A` | `3FC999999999999A` | `3F947AE147AE147C` |
| 8 | +0 × 5.0 | `0000000000000000` | `4014000000000000` | `0000000000000000` |
| 9 | −0 × 5.0 | `8000000000000000` | `4014000000000000` | `8000000000000000` |
| 10 | +Inf × −2.0 | `7FF0000000000000` | `C000000000000000` | `FFF0000000000000` |
| 11 | −Inf × −Inf | `FFF0000000000000` | `FFF0000000000000` | `7FF0000000000000` |
| 12 | 0 × Inf (inválida) | `0000000000000000` | `7FF0000000000000` | `7FF8000000000000` (NaN) |
| 13 | NaN × 1.0 (propaga carga útil) | `7FF8000000000123` | `3FF0000000000000` | `7FF8000000000123` |
| 14 | sNaN × 1.0 (se silencia) | `7FF0000000000001` | `3FF0000000000000` | `7FF8000000000001` |
| 15 | overflow: MAX × 2.0 | `7FEFFFFFFFFFFFFF` | `4000000000000000` | `7FF0000000000000` |
| 16 | overflow: 1e200 × −1e200 | `6974E718D7D7625A` | `E974E718D7D7625A` | `FFF0000000000000` |
| 17 | underflow a subnormal: 2^−1022 × 0.5 | `0010000000000000` | `3FE0000000000000` | `0008000000000000` |
| 18 | underflow a cero: 1e−200 × 1e−200 | `16687E92154EF7AC` | `16687E92154EF7AC` | `0000000000000000` |
| 19 | subnormal × normal: 2^−1074 × 2^60 | `0000000000000001` | `43B0000000000000` | `0090000000000000` (2^−1014) |
| 20 | empate al par, sube: (1+2^−52) × 1.5 | `3FF0000000000001` | `3FF8000000000000` | `3FF8000000000002` |
| 21 | empate al par, baja: (1+3·2^−52) × 1.5 | `3FF0000000000003` | `3FF8000000000000` | `3FF8000000000004` |
| 22 | empate subnormal: 2^−1074 × 0.5 | `0000000000000001` | `3FE0000000000000` | `0000000000000000` |
| 23 | empate subnormal: 3·2^−1074 × 0.5 | `0000000000000003` | `3FE0000000000000` | `0000000000000002` |
| 24 | subnormal que redondea al menor normal | `000FFFFFFFFFFFFF` | `3FF0000000000001` | `0010000000000000` |

En los casos 20 y 21 el producto exacto cae justo a la mitad entre dos flotantes: en el 20 la parte truncada es impar (…01) y sube a …02; en el 21 es par (…04) y se queda.

## 8. Limitaciones y decisiones

* **Solo redondeo al par más cercano.** No hay modos hacia 0, +∞ o −∞ (el SR de Enigma-64 no tiene campo de modo de redondeo).
* **Sin banderas de excepción IEEE** (inexact, underflow, overflow, invalid, divide-by-zero): el SR solo tiene Z, N, C, V, M, I, S. Las condiciones se reflejan únicamente en el valor devuelto.
* **Signo del NaN de 0 × Inf:** se devuelve `0x7FF8000000000000` (como RISC-V/ARM). En x86, y por eso en Python, sale `0xFFF8000000000000`. IEEE 754 no especifica el signo de un NaN, y ambos son NaN silenciosos.
* **Prioridad de NaN:** si los dos operandos son NaN se devuelve A silenciado.
* **Tiempo variable:** el camino normal toma ≈ 166 instrucciones (≈ 830 ciclos de la FSM); subnormal × subnormal ≈ 1040 instrucciones (≈ 5200 ciclos) por los bucles de 1 bit. Dentro del límite de 50 000 ciclos del harness.
* **R1–R4 no se preservan** (igual que FADD/FSUB).
* `programas/fpu_nucleo.s/.bin/.hex` no se regeneraron: siguen conteniendo solo el núcleo (FADD/FSUB).
