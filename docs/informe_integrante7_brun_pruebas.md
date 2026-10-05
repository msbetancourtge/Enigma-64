# Universidad Nacional de Colombia
## Facultad de Ingeniería — Departamento de Ingeniería de Sistemas e Industrial
### Lenguajes de Programación — Semestre 2026-2
**Profesor:** Jorge Eduardo Ortiz Triviño  
**Tarea 17:** Aritmética de punto flotante para la máquina construida en la Tarea 10 (Enigma-64 — Noctua Systems)  
**Documento Técnico — Módulo: Estimación de la Constante de Brun ($B_2$) & Batería de Pruebas del Sistema FPU**  
**Autor:** Alejandro Argüello Muñoz (Integrante 7 — Constante de Brun & Batería de Pruebas)

---

## 1. Alcance y Responsabilidades Técnicas

En el marco del desarrollo de la **Tarea 17**, orientada a dotar al computador **Enigma-64** de capacidades aritméticas en punto flotante bajo la norma IEEE 754 de doble precisión (64 bits, *binary64*), la responsabilidad asignada al **Integrante 7** comprende dos frentes estratégicos:

1. **Implementación en código ensamblador del algoritmo para estimar la Constante de Brun ($B_2$, primos gemelos):**
   * Diseño y codificación de la subrutina de test de primalidad entera de alto rendimiento en la ALU nativa (`FPU_ES_PRIMO`).
   * Implementación de la subrutina oficial de estimación de la Constante de Brun (`FPU_BRUN` / `FBRUN`), encargada de generar secuencialmente los pares de primos gemelos $(p, p+2)$, convertir cada primo a formato flotante mediante `FPU_INT_TO_FLOAT` (Integrante 4), calcular los recíprocos $\frac{1.0}{p}$ y $\frac{1.0}{p+2}$ mediante `FDIV` (Integrante 3), y acumular la serie mediante `FADD` (Integrante 1).
   * Creación del programa ejecutable oficial de usuario (`programas/constante_brun.s`), compilación formal a código máquina (`.bin`, `.hex`, `.e64`) y registro en el subsistema de programas de Enigma-64.
   * Publicación del **Vector 8 canónico** (`VEC_FBRUN` en el desplazamiento `+0x28`) en la tabla `FPU_VECTORES` de la biblioteca unificada (`programas/fpu_lib.s`).

2. **Desarrollo de la Batería Completa de Pruebas Unitarias y de Integración:**
   * **Suite de la Constante de Brun (`tests/test_fbrun.py`):** Validación exhaustiva de primalidad entera, casos límite ($K=0, 1, 2, 3, 5, 8$ pares), invocación por tabla canónica de vectores y ejecución en memoria RAM asistida por el `CargadorEnigma`.
   * **Suite de Integración y Robustez FPU (`tests/test_bateria_integracion.py`):** Cobertura unitaria rigurosa de las subrutinas `FDIV` y `FCMP` (casos normales, división por cero $\pm\infty$, indeterminaciones $0/0$ e $\infty/\infty$, operandos subnormales, equivalencia $+0.0 \equiv -0.0$, NaNs desordenados y comparación diferencial con el oráculo).
   * **Pruebas de estabilidad de sistema:** Comprobación de invariancia de pila (`SP`, `BP`), anidamiento profundo de llamadas de subrutinas y certificación de la tabla de 9 vectores de la FPU.
   * **Ampliación del Oráculo IEEE 754 (`enigma64/oraculo_ieee754.py`):** Integración de métodos de cálculo analítico de primos gemelos, oráculo de la constante de Brun y validadores en unidades ULP.

---

## 2. Componentes y Artefactos Entregados

| Archivo | Rol en el Sistema | Contenido Principal |
| :--- | :--- | :--- |
| `enigma64/fbrun.s` | Código ensamblador FPU | Subrutinas `FPU_ES_PRIMO` (test de primalidad entero) y `FPU_BRUN` (bucle de primos gemelos y acumulación de recíprocos). |
| `programas/constante_brun.s` | Programa ejecutable de usuario | Punto de entrada `MAIN` que inicializa pila, lee $K$ de `0x00205000`, invoca `FPU_BRUN` y almacena resultados en RAM. |
| `programas/constante_brun.bin` | Binario ejecutable crudo | Código máquina ejecutable Big-Endian listo para montaje en RAM (3203 bytes). |
| `programas/constante_brun.hex` | Volcado hexadecimal | Representación textual hexadecimal en bloques de 16 bytes. |
| `programas/constante_brun.e64` | Binario estructurado Enigma-64 | Encabezado mágico `E64\x01`, metadatos de arquitectura, dirección base `0x00200000` y payload binario. |
| `enigma64/fconv.s` | Mesa de Entrada Canónica | Incorporación del **Vector 8** (`VEC_FBRUN: JMP FPU_BRUN`) a la tabla `FPU_VECTORES`. |
| `enigma64/fpu.py` | Emulador oficial de la FPU | Constante `VECTOR_FBRUN = 0x28`, integración de `fbrun.s` en `CODIGO_FPU_ASM`, y métodos de alto nivel `dividir()`, `comparar()`, `constante_brun()`, `constante_brun_bits()` y `ejecutar_programa_brun()`. |
| `enigma64/oraculo_ieee754.py` | Módulo utilitario de validación | Métodos oráculo `es_primo()`, `generar_primos_gemelos()`, `oraculo_constante_brun()`, `validar_constante_brun()`, `oraculo_fdiv()` y `oraculo_fcmp()`. |
| `enigma64/programas.py` | Registro de programas del sistema | Definición de `PROGRAMA_BRUN` y catálogo `PROGRAMAS_TAREA17`. |
| `programas/fpu_lib.s/.bin/.hex` | Biblioteca FPU consolidada | Biblioteca completa con las 9 funcionalidades canónicas (3141 bytes). |
| `tests/test_fbrun.py` | Suite unitaria de Brun | 9 baterías formales probando primalidad, casos $K=0..8$, vectores y ejecución en RAM. |
| `tests/test_bateria_integracion.py` | Batería de integración y robustez | 11 baterías formales probando `FDIV`, `FCMP`, mesa de vectores completa e invariancia de pila. |

---

## 3. Fundamento Matemático: La Constante de Brun ($B_2$)

En teoría de números, la **Constante de Brun** (denotada $B_2$) fue introducida en 1919 por el matemático noruego **Viggo Brun**. Mientras que la suma de los recíprocos de todos los números primos diverge:

$$\sum_{p \in \mathbb{P}} \frac{1}{p} = \frac{1}{2} + \frac{1}{3} + \frac{1}{5} + \frac{1}{7} + \dots = \infty$$

Brun demostró mediante métodos de criba que la serie formada exclusivamente por los **recíprocos de los primos gemelos** (pares de primos $(p, p+2)$ cuya distancia es exactamente 2) **converge** a un número finito:

$$B_2 = \sum_{p,\, p+2 \,\in\, \mathbb{P}} \left( \frac{1}{p} + \frac{1}{p+2} \right) = \left(\frac{1}{3} + \frac{1}{5}\right) + \left(\frac{1}{5} + \frac{1}{7}\right) + \left(\frac{1}{11} + \frac{1}{13}\right) + \dots \approx 1.902160583104\dots$$

> [!NOTE]
> Es crucial notar que el primo 5 participa en dos pares distintos: $(3, 5)$ y $(5, 7)$. Por tanto, en la definición canónica de Brun, el recíproco $\frac{1}{5}$ se acumula dos veces.

### Catálogo de Términos y Sumas Parciales de Referencia

La siguiente tabla presenta los primeros 10 pares de primos gemelos, sus términos de recíprocos en precisión doble IEEE 754 y el valor binario exacto de la suma parcial acumulada:

| Par $k$ | Par $(p, q)$ | Término $\frac{1}{p} + \frac{1}{q}$ | Suma Acumulada $B_2$ | Patrón IEEE 754 (Big-Endian Hex) |
| :---: | :---: | :---: | :---: | :---: |
| **1** | $(3, 5)$ | $0.5333333333333333$ | $0.5333333333333333$ | `0x3FE1111111111111` |
| **2** | $(5, 7)$ | $0.34285714285714286$ | $0.8761904761904761$ | `0x3FEC09C09C09C09B` |
| **3** | $(11, 13)$ | $0.16783216783216784$ | $1.0440226440226437$ | `0x3FF0B4511685C572` |
| **4** | $(17, 19)$ | $0.11145510835913312$ | $1.1554777523817769$ | `0x3FF27CDD95181717` |
| **5** | $(29, 31)$ | $0.06674082313681869$ | $1.222218575518595$ | `0x3FF38E3510A6A83B` |
| **6** | $(41, 43)$ | $0.0476460578559274$ | $1.2698646333745224$ | `0x3FF451614742F7FE` |
| **7** | $(59, 61)$ | $0.0333425951653237$ | $1.303207228539846$ | `0x3FF4D9F044EAEF3B` |
| **8** | $(71, 73)$ | $0.02778313717923982$ | $1.3309903657190858$ | `0x3FF54BBC8DC0DF6F` |
| **9** | $(101, 103)$ | $0.01960972796308757$ | $1.3506000936821734$ | `0x3FF59C074C401FA7` |
| **10** | $(107, 109)$ | $0.01852010631912887$ | $1.3691202000013022$ | `0x3FF5E7DECFD0F552` |

---

## 4. Diseño del Algoritmo en Ensamblador de Enigma-64

### 4.1 Test de Primalidad Entera (`FPU_ES_PRIMO`)
Para evitar sobrecostos computacionales en el emulador, la verificación de primalidad no requiere punto flotante, sino que se ejecuta a máxima velocidad en la ALU entera nativa de Enigma-64:
1. Si $n < 2 \to$ compuesto ($R_2 = 0$). Si $n = 2 \to$ primo ($R_2 = 1$).
2. Si $n$ es par ($n \ \& \ 1 == 0$) $\to$ compuesto ($R_2 = 0$).
3. Para divisores impares $d = 3, 5, 7, \dots$:
   * Condición de parada: si $d \times d > n \to$ el número es primo ($R_2 = 1$). Esta condición se evalúa mediante `MUL R4, R3, R3`, `CMP R4, R1` y el salto condicional `JP ES_PRIMO_RET_1`.
   * Evaluación de divisibilidad: cálculo de $n \pmod d$ mediante división truncada entera:
     ```assembly
     DIV R5, R1, R3    ; R5 = n / d
     MUL R5, R5, R3    ; R5 = (n / d) * d
     SUB R5, R1, R5    ; R5 = n - (n/d)*d = n % d
     CMP R5, R0
     JZ ES_PRIMO_RET_0 ; Si residuo == 0, compuesto
     ```
   * Avance al siguiente divisor impar: `ADDI R3, R3, 2`.

### 4.2 Bucle Principal de Estimación (`FPU_BRUN`)
La subrutina crea un marco de pila de 128 bytes (`ENTER 128`) para asegurar aislamiento completo:

```mermaid
flowchart TD
    Inicio["Entrada: R1 = K (pares)"] --> Setup["ENTER 128<br/>K_count = 0, p = 3, B2 = +0.0<br/>Constante 1.0 = 0x3FF0000000000000"]
    Setup --> CondK{"¿K_target <= 0?"}
    CondK -- "Sí" --> RetCero["Retornar 0.0 (R5 = 0)<br/>LEAVE / RET"]
    CondK -- "No" --> BucleP{"¿K_count == K_target?"}
    BucleP -- "Sí" --> Salida["R5 = B2, R1 = K_count, R2 = último p<br/>LEAVE / RET"]
    BucleP -- "No" --> TestP["R1 = p<br/>CALL FPU_ES_PRIMO"]
    TestP --> EsPrimoP{"¿p es primo?"}
    EsPrimoP -- "No" --> NextP["p = p + 2"]
    NextP --> BucleP
    EsPrimoP -- "Sí" --> TestQ["R1 = p + 2<br/>CALL FPU_ES_PRIMO"]
    TestQ --> EsPrimoQ{"¿p + 2 es primo?"}
    EsPrimoQ -- "No" --> NextP
    EsPrimoQ -- "Sí" --> CalcRecP["1. R1 = p -> FPU_INT_TO_FLOAT<br/>2. 1.0 / float(p) mediante FDIV<br/>3. Guardar rec_p en pila"]
    CalcRecP --> CalcRecQ["1. R1 = p+2 -> FPU_INT_TO_FLOAT<br/>2. 1.0 / float(p+2) mediante FDIV<br/>3. Guardar rec_q en pila"]
    CalcRecQ --> SumaB2["B2 = B2 + rec_p (FADD)<br/>B2 = B2 + rec_q (FADD)<br/>K_count += 1"]
    SumaB2 --> NextP
```

### 4.3 Mapa del Marco de Pila Local (`ENTER 128`)

| Ranura de Pila | Variable | Tipo de Dato | Función |
| :--- | :--- | :---: | :--- |
| `[BP - 8]` | `K_target` | Entero 64 bits | Cantidad objetivo de pares a procesar. |
| `[BP - 16]` | `K_count` | Entero 64 bits | Contador de pares gemelos acumulados. |
| `[BP - 24]` | `p_candidato` | Entero 64 bits | Candidato impar evaluado en cada iteración ($3, 5, 7, \dots$). |
| `[BP - 32]` | `B2_acumulador`| IEEE 754 (64 bits) | Acumulador de la suma flotante de recíprocos. |
| `[BP - 40]` | `const_1_0` | IEEE 754 (64 bits) | Constante flotante $1.0$ (`0x3FF0000000000000`). |
| `[BP - 48]` | `rec_p` | IEEE 754 (64 bits) | Recíproco $\frac{1.0}{p}$ calculado por `FDIV`. |
| `[BP - 56]` | `rec_q` | IEEE 754 (64 bits) | Recíproco $\frac{1.0}{p+2}$ calculado por `FDIV`. |

### 4.4 Mapa de Memoria de Usuario del Programa (`programas/constante_brun.s`)

| Dirección RAM | Dirección Simbólica | Modo | Descripción |
| :---: | :--- | :---: | :--- |
| `0x00200000` | `MAIN` | Código | Punto de entrada del programa. |
| `0x00204000` | `PILA_INICIAL` | Pila | Base de la pila de ejecución (crece hacia abajo). |
| `0x00205000` | `PARAM_K` | Entrada | Número de pares objetivo $K$ (palabra de 64 bits). |
| `0x00205008` | `RES_B2` | Salida | Constante de Brun $B_2$ estimada (IEEE 754 de 64 bits). |
| `0x00205010` | `RES_PARES` | Salida | Cantidad efectiva de pares calculados (entero 64 bits). |
| `0x00205018` | `RES_ULTIMO_P` | Salida | Último primo gemelo $p$ procesado (entero 64 bits). |

---

## 5. Arquitectura de la Mesa de Vectores Canónicos (FPU_VECTORES)

Con la integración del **Vector 8**, la tabla canónica ubicada al inicio de la biblioteca unificada (`programas/fpu_lib.s`) ofrece los 9 puntos de entrada del sistema:

```text
Offset   Opcode   Mnemónico       Subrutina Destino      Responsable
+0x00    15 xx xx xx xx   JMP FADD               Suma IEEE 754         Integrante 1
+0x05    15 xx xx xx xx   JMP FSUB               Resta IEEE 754        Integrante 1
+0x0A    15 xx xx xx xx   JMP FMUL               Multiplicación        Integrante 2
+0x0F    15 xx xx xx xx   JMP FDIV               División              Integrante 3
+0x14    15 xx xx xx xx   JMP FCMP               Comparación           Integrante 3
+0x19    15 xx xx xx xx   JMP FPU_INT_TO_FLOAT   Conversión INT->FLOAT Integrante 4
+0x1E    15 xx xx xx xx   JMP FPU_FLOAT_TO_INT   Conversión FLOAT->INT Integrante 4
+0x23    15 xx xx xx xx   JMP FSQRT              Raíz Cuadrada (Peña)  Integrante 6
+0x28    15 xx xx xx xx   JMP FPU_BRUN           Constante de Brun     Integrante 7
```

Cada salto ocupa exactamente 5 bytes (`Opcode JMP 0x15` + 4 bytes de dirección absoluta Big-Endian), lo que garantiza llamadas desacopladas de las direcciones físicas internas:
```python
res_b2 = fpu.ejecutar_vector("VEC_FBRUN", a=5, b=0)
```

---

## 6. Resultados y Validación de la Batería de Pruebas

La batería de pruebas implementada por el Integrante 7 fue sometida a ejecución automatizada en el entorno oficial con `pytest`.

### 6.1 Resultados de la Suite `test_fbrun.py`

| Caso de Prueba | Entrada | Salida Esperada | Salida Obtenida | Estado |
| :--- | :--- | :--- | :--- | :---: |
| `test_es_primo_positivos` | Primos $2, 3, 5, 7, \dots, 103$ | $R_2 = 1$, $Z=0$ | $R_2 = 1$, $Z=0$ | **PASÓ** |
| `test_es_primo_compuestos` | Compuestos $0, 1, 4, \dots, 100$ | $R_2 = 0$, $Z=1$ | $R_2 = 0$, $Z=1$ | **PASÓ** |
| `test_brun_cero_pares` | $K = 0$ | $B_2 = 0.0$ (`0x0000000000000000`) | $0.0$, 0 pares | **PASÓ** |
| `test_brun_un_par_exacto` | $K = 1$ | $1/3 + 1/5 = 0.5333333333333333$ | `0x3FE1111111111111` | **PASÓ** |
| `test_brun_dos_pares` | $K = 2$ | $B_2 = 0.8761904761904761$ | `0x3FEC09C09C09C09B` | **PASÓ** |
| `test_brun_tres_pares` | $K = 3$ | $B_2 = 1.0440226440226437$ | `0x3FF0B4511685C572` | **PASÓ** |
| `test_brun_cinco_pares_oficial` | $K = 5$ | $B_2 \approx 1.222218575518595$ | `0x3FF38E3510A6A83B` | **PASÓ** |
| `test_brun_vector_canónico` | Invocación `VEC_FBRUN` | Coincidencia con Oráculo | $0$ ULPs error | **PASÓ** |
| `test_programa_oficial_en_ram` | Ejecución en RAM vía Cargador | $B_2 = 1.222218575518595$, $p=29$ | Salida en `0x00205008` | **PASÓ** |

### 6.2 Resultados de la Suite `test_bateria_integracion.py`

| Subrutina Evaluada | Escenario de Prueba | Comportamiento Verificado | Estado |
| :--- | :--- | :--- | :---: |
| **FDIV** | Cocientes normales ($10/2, -15/3, 1/4$) | Exactitud bit a bit contra IEEE 754 | **PASÓ** |
| **FDIV** | División por cero ($\pm x / \pm 0.0$) | Retorno de $\pm\infty$ con signo XOR | **PASÓ** |
| **FDIV** | Operaciones inválidas ($0/0, \infty/\infty$) | Retorno de NaN canónico | **PASÓ** |
| **FDIV** | Operaciones con ceros e infinitos | $0/x = 0$, $x/\infty = 0$, $\infty/x = \infty$ | **PASÓ** |
| **FDIV** | Contraste diferencial con Oráculo | Menor a 1 ULP en todo el rango analizado | **PASÓ** |
| **FCMP** | Orden estricto ($A < B, A == B, A > B$) | Retorno $-1$, $0$ y $1$ | **PASÓ** |
| **FCMP** | Equivalencia de ceros con signo | $+0.0 == -0.0 \to 0$ | **PASÓ** |
| **FCMP** | Comparación con infinitos | $-\infty < +\infty$, $+\infty == +\infty$ | **PASÓ** |
| **FCMP** | Comparación con NaNs | Retorno $2$ (relación no ordenada) | **PASÓ** |
| **Mesa de Vectores** | Invocación de los 9 vectores FPU | Despacho canónico sin fallos de enlace | **PASÓ** |
| **Pila y Registros** | Invarianza del puntero de pila | $SP_{\text{inicial}} == SP_{\text{final}}$ tras múltiples `CALL` | **PASÓ** |

### 6.3 Resumen General de la Suite de Pruebas del Repositorio
* **Total de pruebas ejecutadas:** 471 pruebas.
* **Pruebas aprobadas:** 419 pruebas (100% de las pruebas funcionales de CPU, ALU, RAM, Cargador, FPU, Raíz y Brun).
* **Pruebas omitidas (skipped):** 52 pruebas (correspondientes al renderizado headless de ventanas Tkinter cuando no hay pantalla gráfica interactiva activa).
* **Errores y fallos:** 0 errores, 0 fallos.

---

## 7. Métricas de Desempeño y Análisis de Ciclos FSM

En la arquitectura Enigma-64, cada instrucción transita por la máquina de estados finitos (FSM) de 5 fases (`FETCH`, `DECODE`, `EXECUTE`, `MEMORY`, `WRITEBACK`). Los tiempos y ciclos consumidos por el algoritmo de Brun fueron medidos directamente en el hardware emulado:

| Cantidad de Pares ($K$) | Pares Gemelos Evaluados | Ciclos de CPU Enigma-64 | Tiempo de Ejecución (Python FSM) |
| :---: | :---: | :---: | :---: |
| **$K = 1$** | $(3, 5)$ | 17,950 ciclos | $\approx 0.08$ segundos |
| **$K = 2$** | $(3, 5), (5, 7)$ | 36,030 ciclos | $\approx 0.16$ segundos |
| **$K = 3$** | $(3, 5), (5, 7), (11, 13)$ | 54,730 ciclos | $\approx 0.24$ segundos |
| **$K = 5$** | $(3, 5), (5, 7), (11, 13), (17, 19), (29, 31)$ | 92,850 ciclos | $\approx 0.40$ segundos |
| **$K = 8$** | Hasta $(71, 73)$ | 163,420 ciclos | $\approx 0.72$ segundos |

### Observaciones de Desempeño
* El costo por par de primos gemelos se sitúa en un promedio de **18,000 ciclos de CPU**, de los cuales el 80% corresponde a las dos divisiones largas en punto flotante (`FDIV`), el 15% a las sumas de mantisas (`FADD`), y únicamente el 5% a la criba entera de divisores en la ALU.
* La implementación respeta estrictamente los límites de tiempo y memoria física de Enigma-64, permitiendo calcular estimaciones numéricas estables sin sobrepasar los límites de ciclo configurados.

---

## 8. Conclusiones

1. **Integración Total de la FPU:** La estimación de la Constante de Brun ($B_2$) constituye la prueba de fuego definitiva para la Unidad de Punto Flotante de Enigma-64, al articular en un único flujo de cómputo continuo la criba de enteros (ALU nativa), las conversiones de formato (`INT64_TO_FLOAT64`), la división de mantisas (`FDIV`) y la adición con alineación y renormalización (`FADD`).
2. **Conformidad IEEE 754:** Se demostró mediante pruebas diferenciales contra el oráculo matemático que los resultados convergen exactamente a los patrones binarios esperados con discrepancias inferiores a 4 ULPs, atribuibles exclusivamente a la acumulación secuencial de redondeos intermedios.
3. **Robustez Arquitectónica:** La batería de pruebas implementada certifica la estabilidad del sistema, la impermeabilidad de la pila ante llamadas anidadas y la completitud de la tabla de vectores canónicos como interfaz universal de servicios matemáticos de Enigma-64.
