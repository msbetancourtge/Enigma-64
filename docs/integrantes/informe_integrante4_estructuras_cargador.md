# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Tarea 29:** Librería básica de estructuras de datos para la máquina construida en la Tarea 10  
**Documento Técnico — Empaquetado de la Librería, Cabeceras/Descriptores y Enlace con `CargadorEnigma`**  
**Autor:** Juan Luis Vergara Novoa (Integrante 4 — Cargador, Directivas, Cabeceras y Enlace)

---

## 1. Resumen de Entregables del Integrante 4

| Archivo | Rol en el Sistema | Contenido Principal |
| :--- | :--- | :--- |
| `spl/include/estructuras.inc` | Cabecera maestra de la librería | Punto único de inclusión (`#include "estructuras.inc"`), constantes de descriptores (`TIPO_VECTOR`, `TIPO_MATRIZ`, `DESC_DIR(slot)`), integración de `layout_datos.inc`, `vec.asm`, `cabeceras.asm` y gancho condicional `#ifdef INCLUIR_MATRICES` para `mat.asm` |
| `spl/include/cabeceras.asm` | Constructores y descriptores en ensamblador | Subrutinas nativas de Enigma-64 para inicializar y consultar cabeceras inline y descriptores de 32 bytes en `BASE_CABECERAS`: `VEC_INIT`, `MAT_INIT`, `MAT_ROWS`, `MAT_COLS`, `DESC_ADDR`, `DESC_VEC_INIT`, `DESC_MAT_INIT` y `DESC_GET_*` |
| `spl/estructuras/descriptores.py` | Constructores y descriptores en Python | Clases `DescriptorVector`, `DescriptorMatriz` y `MapaEstructurasRAM`, normalización de palabras de 64 bits Big-Endian (enteros y `double` IEEE 754) y validación de alineación a 8 bytes |
| `spl/estructuras/memoria.py` | Precarga e inspección sobre `RAMMemory` | Inyección y lectura tipada de vectores, matrices Row-Major y descriptores de 32 bytes validando fronteras con `CargadorEnigma.validar_limites()` |
| `spl/estructuras/cargador.py` | Puente `Preprocesador -> Ensamblador -> CargadorEnigma (.e64)` | Compilación y empaquetado `.e64` (`b"ENIG"`), carga y ejecución en `CPU` con `SP` alineado a 8 bytes (`0x00400000`) y CLI en `spl/estructuras/__main__.py` |
| `spl/ejemplos/prueba_cabeceras_cargador.asm` | Programa de verificación en CPU | Demostración ejecutable sobre la CPU de Enigma-64 que valida todas las rutinas de `cabeceras.asm` y su interoperabilidad con `VEC_LEN` |
| `tests/test_spl/test_estructuras_cargador.py` | Batería de pruebas automatizadas | 18 pruebas unitarias e integrales cubriendo inclusión, lexer del ensamblador, ejecución en CPU, normalización de 64 bits, detección de solapamientos, `.e64` autónomo con `CargadorEnigma` e integración con `prueba_vec.asm` y `merge_sort.asm` |

---

## 2. Descripción y Justificación del Problema (Capítulo 2 del Informe Colectivo)

### 2.1 Planteamiento del Problema: Brecha Semántica entre Estructuras de Datos y Memoria Lineal

El computador **Enigma-64**, diseñado e implementado en la Tarea 10 bajo una arquitectura Von Neumann multiciclo de 64 bits, expone únicamente un espacio físico de direccionamiento lineal de $4\text{ GiB}$ (`0x00000000` a `0xFFFFFFFF`) gobernado por tres restricciones estrictas de hardware en su controlador `RAMMemory`, su unidad de control `CPU` y su subsistema de protección `CargadorEnigma`:

1. **Ausencia de Tipos Compuestos en la ISA:** El repertorio real de 41 instrucciones de Enigma-64 opera exclusivamente sobre escalares de 64 bits alojados en 8 registros de propósito general (`R0`–`R7`, donde `R0 = 0` está cableado a tierra, `R5 = RV`, `R6 = SP` y `R7 = BP`) y transferencias escalares de memoria (`LOAD`, `STORE`, `LDB`, `STB`) con desplazamiento inmediato con signo de 16 bits (`[Rs1 + imm16]`). El hardware carece por completo de nociones nativas de *lista*, *longitud*, *subíndice*, *fila* o *columna*.
2. **Ordenamiento Big-Endian y Alineación Estricta de Palabra (`address % 8 == 0`):** Cada celda elemental numérica (entero en complemento a dos de 64 bits o real `binary64` IEEE 754) ocupa exactamente $W = 8\text{ bytes}$ con el byte más significativo en la dirección menor (*Big-Endian*). Cualquier intento de lectura o escritura de 64 bits sobre una dirección no divisible entre 8 es rechazado por el bus con `STATUS_MISALIGNED`, encendiendo la bandera `M` del registro de estado `SR` y abortando la ejecución con `AlignmentFault`.
3. **Fronteras Rígidas de Protección en Modo Usuario:** El cargador rechaza con `ViolacionProteccionMemoria` todo acceso o volcado inferior a `USER_MEM_START = 0x00200000` (reservado a vectores de interrupción y firmware) o superior a `STACK_START = 0xC0000000` (región de pila). Además, el valor de reinicio arquitectónico `SP_RESET = 0xEFFFFFFF` es impar, por lo que cualquier rutina que emplee marcos de pila (`PUSH`, `CALL`, `ENTER`) requiere un puntero de pila explícitamente alineado a múltiplos de 8 bytes (`0x00400000`).

En consecuencia, programar algoritmos no triviales —como el ordenamiento recursivo por mezclas (*Merge Sort*), operaciones algebraicas sobre vectores o transformaciones matriciales— directamente con direcciones físicas crudas obliga al programador a recalcular manualmente desplazamientos de bytes, gestionar colisiones entre estructuras en RAM y duplicar código de direccionamiento en cada aplicación, incrementando drásticamente el riesgo de fallos de alineación, corrupción silenciosa de memoria y desbalanceo de pila.

### 2.2 Abstracción Matemática de Listas (1D) y Matrices (2D) sobre Memoria Lineal

Para cerrar esta brecha sin alterar un solo módulo de hardware de la Tarea 10, se establece una función biyectiva de linealización desde el dominio de índices lógicos hacia direcciones físicas alineadas de 64 bits ($W = 8$):

- **Lista / Vector Unidimensional $V[0 \dots N-1]$:** Dada una dirección base $B \equiv 0 \pmod 8$, el elemento $i$-ésimo ($0 \le i < N$) se proyecta sobre la dirección física:
  $$\text{Dir}(V[i]) = B + i \cdot 8 = B + (i \ll 3)$$
  En el procesador Enigma-64, sustituir el producto por un corrimiento lógico de 3 bits (`SHL R5, R2, 3`) evita una multiplicación general y resuelve el cálculo efectivo en una sola instrucción ALU antes de `LOAD` o `STORE`.

- **Matriz Bidimensional $M[0 \dots F-1][0 \dots C-1]$ en Orden por Filas (*Row-Major*):** Dada una dirección base $B \equiv 0 \pmod 8$, $F$ filas y $C$ columnas, el elemento $(i, j)$ con $0 \le i < F$ y $0 \le j < C$ se proyecta contiguamente como:
  $$\text{Dir}(M[i][j]) = B + \bigl((i \cdot C) + j\bigr) \cdot 8 = B + \bigl(((i \cdot C) + j) \ll 3\bigr)$$
  La elección del esquema *Row-Major* garantiza una propiedad estructural clave de composicionalidad: cada fila $i$ de una matriz $M$ constituye por sí misma un vector contiguo 1D de longitud $C$ cuya dirección base es $B + ((i \cdot C) \ll 3)$, permitiendo reutilizar directamente las primitivas de vectores (`VEC_COPY`, `VEC_SWAP`, `VEC_GET`, `VEC_SET`) sobre filas completas de matrices.

### 2.3 Justificación del Uso del Preprocesador Léxico (`ply.lex`) frente a Modificaciones de Hardware

Para disponibilizar estas estructuras en las aplicaciones de usuario se evaluaron tres alternativas arquitectónicas:

| Enfoque Evaluado | Impacto en Hardware (Tarea 10) | Sobrecarga en Tiempo de Ejecución | Reutilización y Modularidad |
| :--- | :--- | :--- | :--- |
| **A. Nuevas instrucciones ISA vectoriales/matriciales** | **Alto (Inviable):** Exige rediseñar opcodes, decodificador y FSM de `CPU`. | Baja | Nula compatibilidad hacia atrás con binarios `.e64` previos. |
| **B. Copia manual de rutinas en cada `.asm`** | Ninguno | Baja | **Deficiente:** Duplicación de etiquetas, errores de mantenimiento y colisión de direcciones. |
| **C. Librería modular inyectada por el Preprocesador SPL (`#include` + `#define`) [Adoptado]** | **Cero:** Respeta íntegramente la máquina de la Tarea 10. | **Mínima:** Primitivas hoja en registros y macros en línea sin llamada. | **Óptima:** Inclusión única protegida por `#pragma once` y guardas `#ifndef`. |

La gestión mediante el **Preprocesador del SPL** desarrollado en el Taller #01 resulta estrictamente superior por cuatro razones de ingeniería de lenguajes:

1. **Inmutabilidad de la Máquina Base:** La máquina Enigma-64 permanece intacta; toda la semántica de vectores, matrices y descriptores emerge como una capa de software de sistemas ensamblada a código máquina nativo.
2. **Composición Jerárquica sin Colisiones de Símbolos:** El programador escribe únicamente `#include "estructuras.inc"`. El preprocesador resuelve recursivamente desde `spl/include/` el mapa de memoria (`layout_datos.inc`), las primitivas 1D (`vec.asm`), los constructores de cabeceras (`cabeceras.asm`) y las primitivas 2D (`mat.asm`), suprimiendo inclusiones repetidas mediante `#pragma once` y guardas condicionales `#ifndef` para evitar errores de etiquetas duplicadas en el ensamblador de dos pasadas.
3. **Abstracción Dual (Macros sin Costo + Subrutinas ABI):** Las expresiones constantes y fórmulas de direccionamiento (`BASE_VECTORES`, `VEC_DIR`, `MAT_DIR`, `DESC_DIR`) se expanden léxicamente en tiempo de preprocesamiento con costo cero de llamada, mientras que las operaciones algorítmicas (`VEC_COPY`, `VEC_SWAP`, `DESC_VEC_INIT`, `DESC_MAT_INIT`) se inyectan como subrutinas `CALL`/`RET` protegidas con un salto inicial (`JMP *_FIN_LIBRERIA`) que impide su ejecución accidental por caída.
4. **Integración Transparente con `CargadorEnigma`:** El texto unificado emitido por el preprocesador alimenta directamente al ensamblador y se empaqueta en el formato estructurado `.e64` (`MAGIC_ENIGMA = b"ENIG"`), conservando las validaciones de frontera y la tabla de símbolos para depuración e interfaz gráfica.

---

## 3. Diseño Técnico del Empaquetado, Descriptores y Puente con `CargadorEnigma`

### 3.1 Modelo Dual de Cabeceras y Descriptores en Memoria

En concordancia con la partición de memoria establecida en `spl/include/layout_datos.inc` (`>= 0x00210000`, aislada de los programas de demostración en `0x00201000..0x00205020`), se diseñó un esquema dual de metadatos donde todos los campos son palabras exactas de 64 bits Big-Endian:

1. **Tabla Central de Descriptores en `Zona 1` (`BASE_CABECERAS = 0x00210000`):**
   Cada estructura registrada ocupa una ranura (`slot = 0, 1, 2, ...`) de **32 bytes (4 palabras de 64 bits)** en `DESC_DIR(slot) = 0x00210000 + (slot << 5)`:

   | Offset | Constante | Contenido en Vector 1D (`TIPO_VECTOR = 1`) | Contenido en Matriz 2D (`TIPO_MATRIZ = 2`) |
   | :--- | :--- | :--- | :--- |
   | `+0` | `DESC_OFF_TIPO` | `1` | `2` |
   | `+8` | `DESC_OFF_BASE` | Dirección base `B` de `V[0]` (`B % 8 == 0`) | Dirección base `B` de `M[0][0]` (`B % 8 == 0`) |
   | `+16` | `DESC_OFF_FILAS` | Longitud $N$ del vector | Número de filas $F$ |
   | `+24` | `DESC_OFF_COLS` | `1` (dimensión unitaria) | Número de columnas $C$ |

2. **Cabecera Inline Contigua (`[base - 16]` y `[base - 8]`):**
   Para permitir lecturas $O(1)$ desde cualquier rutina que solo reciba el puntero `R1 = base` (como `VEC_LEN` en `vec.asm` o el detector de precarga externa de `merge_sort.asm`):
   - **En Vectores:** `[base - 16] = 1` (bandera de estructura inicializada) y `[base - 8] = N` (longitud leída por `VEC_LEN`).
   - **En Matrices:** `[base - 16] = F` (leído por `MAT_ROWS`) y `[base - 8] = C` (leído por `MAT_COLS`).

### 3.2 Subrutinas Implementadas en `spl/include/cabeceras.asm`

Todas las subrutinas cumplen estrictamente la convención ABI de la librería (`R1..R4`, `SP` y `BP` *callee-saved*; resultado en `R5`):

| Subrutina | Entradas | Retorno (`R5`) | Efecto en Memoria | Instrucciones |
| :--- | :--- | :--- | :--- | :---: |
| `VEC_INIT` | `R1 = base`, `R2 = N` | `base` | `[base - 16] = 1`, `[base - 8] = N` | 5 |
| `MAT_INIT` | `R1 = base`, `R2 = F`, `R3 = C` | $F \times C$ | `[base - 16] = F`, `[base - 8] = C` | 4 |
| `MAT_ROWS` | `R1 = base` | $F$ | Lee `[base - 16]` | 2 |
| `MAT_COLS` | `R1 = base` | $C$ | Lee `[base - 8]` | 2 |
| `DESC_ADDR` | `R1 = slot` | `0x00210000 + 32*slot` | Ninguno (cálculo puro) | 7 |
| `DESC_VEC_INIT` | `R1 = slot`, `R2 = base`, `R3 = N` | `dir_desc` | Escribe descriptor `(1, base, N, 1)` e inline `[1, N]` | 14 |
| `DESC_MAT_INIT` | `R1 = slot`, `R2 = base`, `R3 = F`, `R4 = C` | `dir_desc` | Escribe descriptor `(2, base, F, C)` e inline `[F, C]` | 14 |
| `DESC_GET_TIPO` / `BASE` / `FILAS` / `COLS` | `R1 = dir_desc` | Campo de 64 bits | Lee `[dir_desc + 0 / 8 / 16 / 24]` | 2 c/u |

### 3.3 Puente Python `Preprocesador -> Ensamblador -> CargadorEnigma (.e64)` (`spl/estructuras/`)

El subpaquete modular `spl/estructuras/` (`descriptores.py`, `memoria.py`, `cargador.py`, `__init__.py` y `__main__.py`) articula las herramientas del SPL con el hardware de la Tarea 10 siguiendo la misma estructura de subpaquetes de `spl/preprocesador/`, `spl/enlazador/` y `spl/traductor/`:

1. **Normalización Segura de 64 Bits (`normalizar_palabra_64` en `descriptores.py`):** Convierte enteros con signo (`[-2^63, 2^63-1]`), enteros sin signo (`[0, 2^64-1]`), flotantes IEEE 754 `binary64` (preservando incluso `-0.0 = 0x8000000000000000`) y literales en texto (apoyándose en `spl.ensamblador.literales` para evitar desbordamientos o el límite de 4300 dígitos de `int()` en Python) a palabras Big-Endian de 8 bytes.
2. **Constructores Validados (`DescriptorVector`, `DescriptorMatriz`, `MapaEstructurasRAM` en `descriptores.py` y `memoria.py`):** Verifican alineación `direccion % 8 == 0`, validan límites de protección con `CargadorEnigma.validar_limites()` y comprueban ausencia total de solapamiento físico entre descriptores, cabeceras inline y bloques de elementos antes de escribir en `RAMMemory`.
3. **Empaquetado `.e64` y Ejecución (`compilar_a_binario_e64`, `exportar_estructuras_e64`, `cargar_y_ejecutar_estructuras` en `cargador.py`):**
   - Ejecuta `preprocesar_archivo`/`preprocesar_texto` $\rightarrow$ `ensamblar()` $\rightarrow$ `BinarioEnigma` con firma mágica `b"ENIG"` y tabla de símbolos completa (etiquetas de código + símbolos de estructuras y descriptores).
   - Al exportar con `incluir_datos_en_imagen=True`, genera un archivo `.e64` **100 % autocontenido** que puede cargarse directamente con `CargadorEnigma.cargar_archivo()` de la Tarea 10 restaurando tanto el código en `0x00200000` como los descriptores en `0x00210000` y los vectores/matrices en `0x00220000`/`0x00260000`.
   - En ejecución directa, invoca `CargadorEnigma.cargar_binario()`, fija `SP = 0x00400000` (alineado a 8 bytes) e inyecta las estructuras en tiempo $O(N)$.

#### Uso desde Línea de Comandos (CLI)
```powershell
python -m spl.estructuras spl/ejemplos/prueba_cabeceras_cargador.asm --ejecutar
python -m spl.estructuras spl/ejemplos/merge_sort.asm -o build/merge_sort.e64 --ejecutar
```

---

## 4. Verificación Automatizada (`tests/test_spl/test_estructuras_cargador.py`)

Se ejecutaron **18 pruebas nuevas** junto con las suites completas de `test_preprocesador_estructuras.py`, `test_vec_lib.py`, `test_merge_sort.py`, `test_cargador.py` y `test_ui_aislamiento.py` (**166 pruebas en total, 0 fallos**):

- **Empaquetado e Inclusión:** Resolución de `#include "estructuras.inc"`, idempotencia ante inclusiones múltiples (`#pragma once` + `#ifndef`), cero errores léxicos en `EnsambladorLexer`, expansión exacta de `DESC_DIR(slot)` y funcionamiento del gancho condicional `#ifdef INCLUIR_MATRICES`.
- **Ejecución Nativa en CPU:** Validación en `CPU` de `prueba_cabeceras_cargador.asm`, `VEC_INIT`, `MAT_INIT`, `DESC_VEC_INIT` y `DESC_MAT_INIT`, confirmando preservación estricta de `R1..R4`, `BP` y `SP = 0x00400000`.
- **Protección y Alineación:** Rechazo de direcciones no múltiplos de 8 (`ErrorEstructuraDatos`), bloqueo de cargas en zona de sistema (`0x00001000`) o pila (`0xC0000000`) con `ViolacionProteccionMemoria`, detección de solapamientos en `MapaEstructurasRAM` y coincidencia exacta entre `DescriptorMatriz.direccion_elemento(i, j)` y la macro `MAT_DIR`.
- **Interoperabilidad Real con `.e64` y Compañeros:** Ejecución exitosa de `prueba_vec.asm` (Integrante 2) y `merge_sort.asm` (Integrante 6) a través de `CargadorEnigma`, incluyendo exportación a disco de `merge_sort_precargado.e64`, recarga pura con `CargadorEnigma.cargar_archivo()` y verificación del vector ordenado en RAM y en la pantalla MMIO (`0xFF001010`).
