# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Tarea 17:** Aritmética de punto flotante para la máquina construida en la Tarea 10 (Enigma-64 — Noctua Systems)  
**Documento Técnico — Módulo FPU: Conversiones de Formato, Mesa de Entrada y Biblioteca Canónica**  
**Autores:** Deibyd Santiago Barragán Gaitán / Juan Luis Vergara Novoa (Integrante 4)

---

## 1. Alcance

El propósito de este módulo es proporcionar la capa de conversión de datos y la interfaz canónica de enlace de la Unidad de Punto Flotante software (*Soft-Float FPU*) de Enigma-64. Se compone de:

1. **Conversión `INT64_TO_FLOAT64` (`FPU_INT_TO_FLOAT`):** Transforma enteros de 64 bits con signo (representación en complemento a dos) al estándar IEEE 754 de doble precisión (*binary64*), aplicando normalización y redondeo al par más cercano (*roundTiesToEven*) cuando el entero excede los 53 bits de significando.
2. **Conversión `FLOAT64_TO_INT64` (`FPU_FLOAT_TO_INT`):** Transforma números en formato IEEE 754 de doble precisión a enteros de 64 bits con signo, truncando cualquier componente fraccionaria hacia cero ($[-1.0, 1.0) \to 0$) y gestionando rangos válidos, casos límite ($-2^{63}$) y valores especiales.
3. **Mesa de Entrada Canónica (`FPU_VECTORES`):** Tabla de salto fija de 7 entradas de 5 bytes cada una, permitiendo a los programas invocar cualquier servicio de la FPU mediante saltos canónicos fijos independientes de la dirección física interna de las subrutinas.
4. **Biblioteca FPU Unificada (`programas/fpu_lib.*`):** Ensamblaje integral de los módulos de la FPU (`fconv.s`, `fpu.s`, `fmul.s`) produciendo la biblioteca binaria en formatos `.bin` y `.hex`.
5. **Capa de Abstracción en Python (`enigma64/fpu.py`):** Métodos de alto nivel (`int_to_float`, `int_to_float_bits`, `float_to_int`, `ejecutar_vector`) en `EmuladorFPUEnigma64`.
6. **Suite de Pruebas Formales (`tests/test_fconv.py`):** 19 pruebas unitarias parametrizadas (111 aserciones/subtests) que validan conformidad bit a bit contra IEEE 754 y contra el oráculo nativo de 64 bits.

### Archivos del módulo

| Archivo | Contenido |
| :--- | :--- |
| `enigma64/fconv.s` | Subrutinas `FPU_INT_TO_FLOAT`, `FPU_FLOAT_TO_INT` y tabla de salto `FPU_VECTORES` |
| `enigma64/fpu.py` | Integración en la clase `EmuladorFPUEnigma64`, constantes `VECTOR_*` y compilación unificada |
| `programas/fpu_lib.s` | Código fuente ensamblador completo y autosuficiente de la biblioteca FPU |
| `programas/fpu_lib.bin` | Binario crudo compilado de la biblioteca FPU (1425 bytes) |
| `programas/fpu_lib.hex` | Volcado hexadecimal oficial de la biblioteca FPU |
| `tests/test_fconv.py` | Suite exhaustiva de pruebas unitarias y verificación con oráculo IEEE 754 |

---

## 2. Restricciones del ISA y Decisiones de Diseño

El diseño de las rutinas de conversión y la tabla de salto se ajusta estrictamente a la microarquitectura y conjunto de instrucciones de Enigma-64:

| Característica de Enigma-64 | Implicación en el Diseño de Conversiones y Mesa |
| :--- | :--- |
| **Instrucciones `JMP` y `CALL` de 5 bytes** | `JMP` genera un opcode de 1 byte (`0x15`) y una dirección absoluta de 4 bytes big-endian. Cada entrada de la tabla canónica mide exactamente **5 bytes**, garantizando un paso de tabla uniforme. |
| **Registros R0–R7 de 64 bits** | R0 está fijado por hardware en 0; R5 es el registro de retorno de valor (RV); R6 es el puntero de pila (SP); R7 es el puntero de marco (BP). Las rutinas usan `ENTER`/`LEAVE` para preservar el estado del marco de pila. |
| **Convención de Llamadas (ABI FPU)** | Operando principal en **R1**, operando secundario en **R2** (para operaciones binarias), resultado retornado en **R5** (RV). Registros temporales de trabajo: **R1–R4**. |
| **Corrimientos solo inmediatos (`SHL`/`SHR`)** | Las instrucciones de corrimiento en Enigma-64 reciben la cantidad de bits codificada de forma inmediata en la instrucción. Corrimientos de magnitud variable (según el exponente $e$) se realizan mediante bucles optimizados de corrimiento de 1 bit. |
| **Aritmética en Complemento a Dos** | El valor mínimo con signo de 64 bits, $\text{INT64\_MIN} = -2^{63} = \text{0x8000000000000000}$, no posee un valor positivo representable en enteros con signo (desborda al negar). Se trata como un caso especial crítico con bifurcación directa. |
| **Reutilización de primitivas FPU** | `FPU_INT_TO_FLOAT` delega el empaquetado final a `FPU_EMPAQUETAR` (`fpu.s`), y `FPU_FLOAT_TO_INT` reutiliza `FPU_DESEMPAQUETAR` (`fpu.s`). |

---

## 3. Mesa de Entrada Canónica (Tabla de Vectores FPU)

La mesa de entrada proporciona una interfaz fija desacoplada de las direcciones físicas del código. Si los módulos internos de la FPU crecen o se reorganizan, los puntos de entrada canónicos permanecen inmutables.

### Estructura de la Tabla (`FPU_VECTORES`)

Ubicada en el offset `+0x00` del binario de la biblioteca:

```text
Offset   Opcode   Instrucción          Destino
+0x00    15 xx xx xx xx   JMP FPU_FADD         (Suma IEEE 754)
+0x05    15 xx xx xx xx   JMP FPU_FSUB         (Resta IEEE 754)
+0x0A    15 xx xx xx xx   JMP FPU_FMUL         (Multiplicación IEEE 754)
+0x0F    15 xx xx xx xx   JMP FPU_FDIV         (División IEEE 754)
+0x14    15 xx xx xx xx   JMP FPU_FCMP         (Comparación IEEE 754)
+0x19    15 xx xx xx xx   JMP FPU_INT_TO_FLOAT (Conversión INT64 → FLOAT64)
+0x1E    15 xx xx xx xx   JMP FPU_FLOAT_TO_INT (Conversión FLOAT64 → INT64)
```

Cada entrada consta de `1 byte (Opcode JMP 0x15)` + `4 bytes (Dirección absoluta de 32 bits)`.

### Constantes exportadas en Python (`enigma64.fpu`)

```python
VECTOR_FADD         = 0x00
VECTOR_FSUB         = 0x05
VECTOR_FMUL         = 0x0A
VECTOR_FDIV         = 0x0F
VECTOR_FCMP         = 0x14
VECTOR_INT_TO_FLOAT = 0x19
VECTOR_FLOAT_TO_INT = 0x1E
```

---

## 4. Algoritmo: `INT64_TO_FLOAT64`

Convierte un entero de 64 bits con signo en R1 al patrón binario IEEE 754 binary64 devuelto en R5.

### Diagrama de Flujo

```
                R1 (entero 64 bits)
                         |
                 ¿R1 == 0? ──SÍ──> Retornar +0.0 (R5 = 0x0000000000000000)
                         | NO
         ¿R1 == -2^63 (INT64_MIN)? ──SÍ──> Retornar 0xC3E0000000000000 (-2^63)
                         | NO
                Aislar Signo:
             Si R1 < 0: S = 1, R1 = -R1
             Si R1 > 0: S = 0
                         |
           Calcular posición del MSB (k):
        k = índice del bit más alto activo (0..62)
                         |
       ┌─────────────────┼──────────────────┐
     k == 52           k < 52             k > 52
        |                 |                  |
   Mantisa OK        Desplazar izq      Desplazar der (k - 52) bits
   E = 52 + 1023     (52 - k) bits      Extraer Guard (G) y Sticky (S)
   M = R1            E = k + 1023       Redondeo roundTiesToEven:
                     M = R1 << shift      M += (G & (S | (M & 1)))
                                        Si M desborda bit 53:
                                          M >>= 1, E += 1
       └─────────────────┬──────────────────┘
                         |
               R2 = S, R3 = E, R4 = M
                         |
               CALL FPU_EMPAQUETAR
                         |
               Retornar R5 (IEEE 754)
```

### Detalle del Redondeo al Par más Cercano (*roundTiesToEven*)

Los enteros con $|R1| \le 2^{53}$ se representan exactamente en IEEE 754 de doble precisión sin pérdida de información (pues la mantisa normalizada cuenta con 53 bits de precisión, 1 implícito + 52 explícitos).

Cuando $|R1| > 2^{53}$ (es decir, $k > 52$, hasta 62), se descartan $d = k - 52$ bits ($1 \le d \le 10$). Para cumplir estrictamente con el estándar IEEE 754:
1. El bit más significativo de los descartados es el **bit de guarda** ($G$).
2. La disyunción lógica (OR) de todos los bits restantes por debajo de $G$ forma el **bit pegajoso** (*sticky bit*, $S$).
3. Si $G = 1$, existe un empate o exceso:
   - Si $S \ne 0$: el valor está estrictamente por encima de la mitad; se suma 1 a la mantisa.
   - Si $S = 0$: el valor está exactamente en la mitad de dos números representables (empate). Se suma 1 si y solo si el bit menos significativo de la mantisa resultante es impar ($\text{LSB} = 1$), forzando a que el resultado redondeado sea par.
4. Si al redondear la mantisa alcanza $2^{53}$, se desplaza 1 bit a la derecha y se incrementa el exponente en 1.

---

## 5. Algoritmo: `FLOAT64_TO_INT64`

Convierte un valor IEEE 754 de 64 bits en R1 a un entero con signo en complemento a dos en R5, implementando la semántica de **truncamiento hacia cero** (equivalente a `int(float)` en Python o `(int64_t)f` en C).

### Pasos de la Rutina

1. **Desempaquetado:** Invoca `FPU_DESEMPAQUETAR` de `fpu.s`.
   - R2 = Signo ($S \in \{0, 1\}$).
   - R3 = Exponente sesgado ($E \in [0, 2047]$).
   - R4 = Mantisa con bit 52 explícito ($M$).
2. **Casos especiales de magnitud:**
   - Si $E = 0$ (subnormal o cero): $|x| < 1.0$. El truncamiento produce **0**.
   - Si $E = 2047$ (Infinito o NaN): valor indefinido o desbordamiento entero. Se satura a **0** (sin lanzar excepción, acorde al modelo sin trampas de hardware del CPU).
3. **Exponente no sesgado:** $e = E - 1023$.
   - Si $e < 0$: el número cumple $|x| < 1.0$. Por truncamiento a cero, retorna **0**.
   - Si $e < 52$: la parte entera requiere desplazar la mantisa a la derecha $52 - e$ posiciones. Los bits fraccionarios se descartan limpiamente con `SHR`.
   - Si $e = 52$: la mantisa de 53 bits ya coincide exactamente con el valor entero; no requiere desplazamiento.
   - Si $52 < e < 63$: la mantisa se desplaza a la izquierda $e - 52$ posiciones mediante un bucle de corrimiento de 1 bit.
   - Si $e = 63$: corresponde a la magnitud $2^{63}$. En complemento a dos de 64 bits, el único valor representable es $\text{INT64\_MIN} = -2^{63}$. Se verifica que el signo sea negativo ($S = 1$) y que la mantisa sea exactamente $2^{52}$ (sin bits fraccionarios); en tal caso devuelve `0x8000000000000000`. Si el signo es positivo, desborda el rango de enteros de 64 bits.
   - Si $e > 63$: desbordamiento del rango entero de 64 bits.
4. **Aplicación del Signo:**
   - Si $S = 1$, se aplica complemento a dos negando el resultado: `R5 = NOT(R5) + 1` (mediante `XOR R1, -1` y `ADDI R1, 1`).

---

## 6. Asignación de Registros y Convenciones de Pila

### Convención en `FPU_INT_TO_FLOAT` (Marco `ENTER 24`)

| Registro / Memoria | Propósito |
| :--- | :--- |
| `R1` | Entrada: entero de 64 bits con signo / Temporal de magnitud |
| `R2` | Signo extraído $S$ ($0$ o $1$) |
| `R3` | Exponente $E$ / Contador de desplazamientos |
| `R4` | Mantisa alineada y redondeada $M$ |
| `R5` | Registro de retorno de valor (patrón IEEE 754) |
| `[BP-8]` | Variable local: Guarda ($G$) |
| `[BP-16]` | Variable local: Pegajoso ($S$) |
| `[BP-24]` | Variable local: Entero original |

### Convención en `FPU_FLOAT_TO_INT` (Marco `ENTER 16`)

| Registro / Memoria | Propósito |
| :--- | :--- |
| `R1` | Entrada: patrón IEEE 754 / Temporal de corrimiento |
| `R2` | Signo $S$ devuelto por desempaquetado |
| `R3` | Exponente sesgado $E$ devuelto por desempaquetado / Exponente real $e$ |
| `R4` | Mantisa desempaquetada $M$ |
| `R5` | Retorno: entero de 64 bits en complemento a dos |
| `[BP-8]` | Variable local: Signo $S$ |
| `[BP-16]` | Variable local: Exponente no sesgado $e$ |

---

## 7. Casos de Prueba y Verificación

La suite formal `tests/test_fconv.py` incluye 19 baterías de pruebas con 111 aserciones directas que cubren exhaustivamente el espacio de estados:

| Batería de Prueba | Método / Enfoque | Casos Evaluados |
| :--- | :--- | :--- |
| **Cero y Signos Básicos** | `test_int_to_float_cero`, `test_int_to_float_basicos` | $0, 1, -1, 2, -2, 10, -10, 100, -100$ |
| **Potencias de Dos** | `test_int_to_float_potencias_de_dos` | $2^0, 2^1, \dots, 2^{62}$, potencias negativas y $-2^{63}$ |
| **Enteros Grandes Exactos** | `test_int_to_float_grandes_exactos` | Valores en la frontera $[2^{52}, 2^{53}]$ con precisión absoluta |
| **Redondeo IEEE TiesToEven** | `test_int_to_float_redondeo_ties_to_even` | Enteros de 54 a 62 bits con empate a par (redondea arriba o abajo exactamente) |
| **Límite Crítico INT64_MIN** | `test_int_to_float_limites` | $\text{INT64\_MIN} = -2^{63}$ y $\text{INT64\_MAX} = 2^{63}-1$ |
| **Truncamiento Hacia Cero** | `test_float_to_int_truncamiento` | $1.99 \to 1$, $-1.99 \to -1$, $0.75 \to 0$, $-0.75 \to 0$ |
| **Casos Extremos y Especiales** | `test_float_to_int_extremos` | $+0.0, -0.0, \text{Subnormales}, +\infty, -\infty, \text{NaN}$ |
| **Límite Crítico Inverso** | `test_float_to_int_limite_int64_min` | $-9223372036854775808.0 \to -2^{63}$ |
| **Identidad Bidireccional** | `test_identidad_int_float_int` | $\text{int}(\text{float}(x)) == x$ para 20 valores aleatorios y canónicos en $[-2^{53}, 2^{53}]$ |
| **Mesa de Vectores Canónica** | `test_mesa_vectores_offsets`, `test_mesa_vectores_ejecucion` | Verificación de saltos a través de `VECTOR_INT_TO_FLOAT` y `VECTOR_FLOAT_TO_INT` |

---

## 8. Resultados de la Suite Completa

Al ejecutar la suite de pruebas del repositorio con el módulo de conversiones integrado:

```bash
$ python -m pytest
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\user\Desktop\UNAL\9 Semestre\Lenguajes de programacion\Enigma-64
collected 355 items

tests\test_algoritmos.py ................                                [  4%]
tests\test_cargador.py .....................                             [ 10%]
tests\test_cpu.py ................                                       [ 14%]
tests\test_fconv.py ...................                                  [ 20%]
tests\test_fmul.py .......                                               [ 22%]
tests\test_fpu.py ...................                                    [ 27%]
tests\test_memoria.py ......................                             [ 33%]
tests\test_perifericos.py ................                               [ 38%]
tests\test_registros_alu.py ......................................       [ 49%]
tests\test_ui_aislamiento.py .............................               [ 57%]
tests\test_ui_modulos_nuevos.py ........................................ [ 68%]
..                                                                       [ 69%]
tests\test_ui_nucleo.py ................................................ [ 82%]
....                                                                     [ 83%]
tests\test_ui_paneles.py ............................................... [ 96%]
...                                                                      [ 97%]
tests\test_ui_visor_ram_mmio.py ........                                 [100%]

============================= 355 passed in 6.44s =============================
```

**Resultado:** 355 pruebas pasando al 100% sin regresiones en ningún subsistema previo de los compañeros de equipo.
