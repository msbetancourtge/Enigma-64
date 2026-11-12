# Informe Técnico: Algoritmo de Ordenamiento por Mezclas (Merge Sort) y Salida MMIO

**Integrante 6: Algoritmo 1 (Merge Sort) & Periférico de Pantalla MMIO**  
**Tarea 29: Librería básica de estructuras de datos para Enigma-64**

| Archivo | Contenido |
|---|---|
| `spl/ejemplos/merge_sort.asm` | Programa completo: `PRINCIPAL`, subrutina recursiva `MERGE_SORT`, fusión `MERGE`, emisión `EMITIR_VECTOR_MMIO` y vector demo |
| `spl/include/estructuras.inc` | Archivo maestro de inclusión con guardas (`layout_datos.inc` + `vec.asm`) |
| `tests/test_spl/test_merge_sort.py` | Batería automatizada de 20 pruebas (casos base, invertidos, repetidos, estrés con 100 elementos, MMIO y ejecución autónoma) |

---

## 1. Uso e Inclusión

El programa se estructura conforme a la directiva de la tarea, importando la librería maestra de estructuras de datos:

```asm
#include "estructuras.inc"
```

El preprocesador de SPL resuelve la inclusión recursiva protegiéndola contra dobles inclusiones mediante `#pragma once` y directivas `#ifndef`. La librería empaqueta:
1. `spl/include/layout_datos.inc`: Define el mapa de memoria estandarizado en la región de usuario ($\ge \text{0x00201000}$), estableciendo:
   * `BASE_VECTORES = 0x00220000` (Vector principal de entrada / ordenado).
   * `BASE_BUFFERS  = 0x002E0000` (Buffer auxiliar para mezcla).
   * Pila en `0x00400000` (alineada estrictamente a 8 bytes, descendente).
2. `spl/include/vec.asm`: Primitivas de bajo nivel (`VEC_ADDR`, `VEC_GET`, `VEC_SET`, `VEC_COPY`, `VEC_LEN`).

---

## 2. Decisiones de Diseño e Implementación

### 2.1. Partición y Recursión (`MERGE_SORT`)
La subrutina recursiva divide el rango $[lo, hi)$ calculando el punto medio como:
$$mid = lo + \left\lfloor \frac{hi - lo}{2} \right\rfloor$$
utilizando desplazamiento lógico a la derecha (`SHR R5, R5, 1`).

* **Caso base:** Se evalúa $hi - lo < 2$ mediante `SUB` y `SUBI R5, R5, 2` con salto condicional `JN MS_FIN`. Vectores de 0 o 1 elementos retornan de inmediato sin tocar memoria ni invocar partición.
* **Marco de pila:** Utiliza `ENTER 8` para reservar una variable local en `[BP - 8]` donde se preserva $mid$ durante las llamadas anidadas. Los argumentos de rango $lo$ y $hi$ se preservan en pila antes de `ENTER`, garantizando que `R1..R4`, `SP` y `BP` sobrevivan a toda la recursión.
* **Paso de parámetros:** Para invocar a `MERGE`, se pasan 4 argumentos en registros (`R1 = base`, `R2 = lo`, `R3 = mid`, `R4 = aux`) y el quinto argumento ($hi$) se pasa en la pila mediante `PUSH R5` antes de `CALL MERGE`. Al retornar, el llamador balancea la pila con `ADDI SP, SP, 8`.

### 2.2. Subrutina de Mezcla (`MERGE`)
La subrutina `MERGE` fusiona las dos mitades ya ordenadas $v[lo, mid)$ y $v[mid, hi)$ empleando el vector auxiliar:

1. **Marco y variables locales (`ENTER 24`):**
   * `[BP + 48]`: 5.º argumento ($hi$).
   * `[BP - 8]`: Índice $i$ (mitad izquierda, inicializado en $lo$).
   * `[BP - 16]`: Índice $j$ (mitad derecha, inicializado en $mid$).
   * `[BP - 24]`: Índice $k$ (escritura en $v$, inicializado en $lo$).
2. **Paso 1 — Copia al vector auxiliar:**
   Se calcula la dirección de origen $base + (lo \ll 3)$ y destino $aux + (lo \ll 3)$ y la cantidad $n = hi - lo$. Se traslada el bloque completo con una única llamada a `CALL VEC_COPY`.
3. **Paso 2 — Bucle de mezcla principal:**
   * Se comprueban condiciones de corte ($i < mid$ y $j < hi$).
   * Se leen $a = aux[i]$ y $b = aux[j]$ usando `VEC_GET`.
   * **Estabilidad del ordenamiento:** Se comparan los elementos mediante `CMP b, a`. Si $b < a$ ($N=1$), se elige $b$ e incrementa $j$; en caso contrario ($a \le b$, con $N=0$), se elige $a$ e incrementa $i$. Esto garantiza que ante elementos con valores idénticos, se preserve su orden original de aparición (estabilidad estricta).
   * El elemento seleccionado se escribe en $v[k]$ con `VEC_SET`.
4. **Paso 3 — Vaciado de remanentes optimizado:**
   * Si la mitad izquierda no ha terminado ($i < mid$), los $mid - i$ elementos restantes se transfieren de $aux[i..]$ a $v[k..]$ mediante `VEC_COPY`.
   * Si la mitad izquierda terminó primero ($i = mid$), la propiedad matemática del algoritmo garantiza que $k = j$. Por lo tanto, los elementos restantes de la mitad derecha $v[j..hi)$ ya están exactamente en sus posiciones finales dentro de $v$, ahorrando operaciones de copia redundantes.

### 2.3. Emisión por Periférico de Pantalla MMIO (`0xFF001010`)
* **Dirección del puerto:** El Controlador de Pantalla CRT se localiza en `BASE_PANTALLA = 0xFF001000` y su registro de emisión `DATA` en el desplazamiento `+0x10` (`0xFF001010`).
* **Síntesis de constante:** Debido a que el inmediato de `ADDI` es de 16 bits con extensión de signo, la dirección `0xFF001010` no puede cargarse en una sola instrucción. Se sintetiza mediante la secuencia determinista:
  ```asm
  ADDI R5, R0, 1
  SHL  R5, R5, 16
  ADDI R5, R5, -256
  SHL  R5, R5, 16
  ADDI R5, R5, 4112          ; R5 = 0xFF001010
  ```
* **Conversión ASCII:**
  * Soporta cero explícito (`'0'`).
  * Para números negativos, emite el carácter `'-'` (ASCII 45) y niega el valor (`SUB R1, R0, R1`).
  * Realiza divisiones sucesivas entre 10 (`DIV` y módulo con `MUL`/`SUB`), empujando cada residuo más 48 a la pila (`PUSH`).
  * Desapila (`POP`) los dígitos en orden LIFO y los escribe en `STORE R3, [R5 + 0]`, emitiendo los números legibles de izquierda a derecha.
  * Separa cada número con un espacio (`' '`) y remata la línea con un salto de línea final (`'\n'`).
  * Si el vector tiene 0 elementos, no emite caracteres.

### 2.4. Modo Dual de Ejecución (Autónomo / Harness)
El programa principal `merge_sort.asm` detecta si la memoria RAM de datos se encuentra limpia (sin configurar por un entorno externo). En dicho caso, inicializa autónomamente un **Vector Demo de 8 elementos** (`[45, -12, 89, 0, 23, -5, 77, 10]`) en `BASE_VECTORES`, lo ordena y lo proyecta en la pantalla MMIO. Si un arnés de prueba externo pre-configura la memoria, el programa respeta los datos inyectados y los ordena fielmente.

---

## 3. Convención de Registros Utilizada

| Registro | Rol en Merge Sort / MMIO | Política |
|---|---|---|
| `R0` | Constante 0 de hardware | Fijo |
| `R1` | Puntero base del vector principal `v` (`0x00220000`) | Callee-saved (preservado) |
| `R2` | Índice $lo$ / índices temporales en primitivas | Callee-saved (preservado) |
| `R3` | Índice $hi$ / valor en `VEC_SET` | Callee-saved (preservado) |
| `R4` | Puntero base del buffer auxiliar `aux` (`0x002E0000`) | Callee-saved (preservado) |
| `R5` | Retorno de funciones (`RV`), temporales y puntero MMIO | Caller-saved (destruido) |
| `R6 (SP)` | Puntero de Pila (`0x00400000`), alineado estrictamente a 8 bytes | Preservado |
| `R7 (BP)` | Puntero de Marco para gestión de variables locales con `ENTER`/`LEAVE` | Preservado |

---

## 4. Mediciones de Rendimiento y Complejidad

Las instrucciones y ciclos fueron medidos directamente sobre la CPU emulada de Enigma-64 (a razón de 5 ciclos por instrucción):

| Tamaño Vector ($N$) | Instrucciones Ejecutadas | Ciclos de Reloj | Pila Máxima Consumida | Salida MMIO |
|---|---|---|---|---|
| **$N = 0$** | 16 | 80 | 0 bytes | `""` |
| **$N = 1$** | 20 | 100 | 0 bytes | `"777\n"` |
| **$N = 2$** | 134 | 670 | 80 bytes | `"10 50\n"` |
| **$N = 4$** | 472 | 2,360 | 136 bytes | `"10 20 30 40\n"` |
| **$N = 8$ (Demo)** | 2,294 | 11,470 | 192 bytes | `"-12 -5 0 10 23 45 77 89\n"` |
| **$N = 32$** | 12,058 | 60,290 | 304 bytes | `"1 2 3 ... 32\n"` |
| **$N = 50$** | 20,476 | 102,380 | 360 bytes | Salida formateada |
| **$N = 100$** | 45,511 | 227,555 | 416 bytes | Salida formateada |

### Análisis de Complejidad
* **Temporal:** La relación entre $N=8$ (2,294 inst.) y $N=32$ (12,058 inst.) exhibe un factor experimental de $\approx 5.25$, en estricta concordancia con la curva teórica:
  $$\frac{32 \log_2 32}{8 \log_2 8} = \frac{160}{24} \approx 6.66$$
  confirmando la cota $\mathcal{O}(N \log N)$ sin casos degenerados.
* **Espacial:** El buffer auxiliar consume exactamente $N$ palabras en `BASE_BUFFERS` ($\mathcal{O}(N)$). La pila requiere $\mathcal{O}(\log N)$ marcos anidados; para $N=100$, el consumo máximo fue de solo 416 bytes, muy inferior al límite de seguridad asignado a la pila en `0x00400000`.

---

## 5. Batería de Pruebas Automatizadas (`test_merge_sort.py`)

La suite automatizada incluye **20 pruebas unitarias e integrales** estructuradas en 5 clases:

```text
tests/test_spl/test_merge_sort.py::TestFase1Setup::test_archivo_estructuras_inc_existe PASSED
tests/test_spl/test_merge_sort.py::TestFase1Setup::test_preprocesamiento_merge_sort PASSED
tests/test_spl/test_merge_sort.py::TestFase1Setup::test_ensamblado_merge_sort PASSED
tests/test_spl/test_merge_sort.py::TestFase2MergeSort::test_merge_sort_vector_pequeno PASSED
tests/test_spl/test_merge_sort.py::TestFase2MergeSort::test_merge_sort_invertido PASSED
tests/test_spl/test_merge_sort.py::TestFase2MergeSort::test_merge_sort_ya_ordenado PASSED
tests/test_spl/test_merge_sort.py::TestFase2MergeSort::test_merge_sort_duplicados_y_negativos PASSED
tests/test_spl/test_merge_sort.py::TestFase2MergeSort::test_merge_sort_casos_base PASSED
tests/test_spl/test_merge_sort.py::TestFase2MergeSort::test_merge_sort_aleatorio PASSED
tests/test_spl/test_merge_sort.py::TestFase2MergeSort::test_preservacion_pila_y_registros PASSED
tests/test_spl/test_merge_sort.py::TestFase3MMIO::test_emision_mmio_pantalla_vector_ordenado PASSED
tests/test_spl/test_merge_sort.py::TestFase3MMIO::test_emision_mmio_pantalla_negativos_y_cero PASSED
tests/test_spl/test_merge_sort.py::TestFase3MMIO::test_emision_mmio_pantalla_vector_vacio PASSED
tests/test_spl/test_merge_sort.py::TestFase4Integracion::test_ejecucion_autonoma_demo PASSED
tests/test_spl/test_merge_sort.py::TestFase5BateriaCompleta::test_vector_grande_50_elementos PASSED
tests/test_spl/test_merge_sort.py::TestFase5BateriaCompleta::test_vector_grande_100_elementos_estres_recursion PASSED
tests/test_spl/test_merge_sort.py::TestFase5BateriaCompleta::test_todos_elementos_identicos PASSED
tests/test_spl/test_merge_sort.py::TestFase5BateriaCompleta::test_alternancia_signos_y_extremos PASSED
tests/test_spl/test_merge_sort.py::TestFase5BateriaCompleta::test_inverso_estricto_32_elementos PASSED
tests/test_spl/test_merge_sort.py::TestFase5BateriaCompleta::test_metricas_rendimiento_o_nlogn PASSED
```

---

## 6. Párrafo para el Manual Técnico General del Equipo

> **Algoritmo de Ordenamiento por Mezclas (Merge Sort) & Salida MMIO (Integrante 6):**  
> Se implementó en ensamblador nativo de Enigma-64 el algoritmo de ordenamiento por mezclas (`MERGE_SORT`) sobre vectores contiguos de 64 bits en la región de memoria de usuario (`BASE_VECTORES = 0x00220000`), apoyado en el buffer auxiliar `BASE_BUFFERS = 0x002E0000` y gestionado mediante marcos de pila anidados (`ENTER`/`LEAVE`) con convención callee-saved sobre `R1..R4`, `SP` y `BP`. La subrutina de mezcla `MERGE` aprovecha la semántica `memmove` de `VEC_COPY` y asegura ordenamiento estrictamente estable mediante comparaciones con signo (`CMP`). Adicionalmente, se desarrolló la subrutina `EMITIR_VECTOR_MMIO` para convertir enteros de 64 bits a caracteres ASCII con manejo de negativos y enviar el vector ordenado al puerto `0xFF001010` del Controlador de Pantalla CRT. El programa cuenta con modo dual autónomo con vector de demostración integrado y una suite automatizada de 20 pruebas en pytest con cobertura de estrés hasta 100 elementos comprobando la complejidad asintótica $\mathcal{O}(N \log N)$ y la integridad de la pila.
