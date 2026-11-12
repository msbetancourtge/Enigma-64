# Informe técnico: librería de matrices `mat.asm` y gestión de la pila en llamadas anidadas

**Integrante 3: Control, Pila y Primitivas 2D**  
**Tarea 29: Librería básica de estructuras de datos para Enigma-64**

| Archivo | Contenido |
|---|---|
| `spl/include/mat.asm` | Librería: `MAT_ADDR`, `MAT_GET`, `MAT_SET` y `MAT_CLEAR`. Incluye `cabeceras.asm` (`MAT_INIT`, `MAT_ROWS`, `MAT_COLS`) |
| `spl/ejemplos/prueba_mat.asm` | Programa de prueba con el estado esperado de la memoria, de los registros y de la pila (tres niveles de llamadas anidadas) |
| `tests/test_spl/test_mat_lib.py` | 74 pruebas nuevas, ejecutadas en la CPU real a través del puente de la Tarea 29 |
| `tests/test_spl/test_estructuras_cargador.py` | Se ajustó una prueba del Integrante 4: el *mock* de `mat.asm` se reemplazó por el módulo real (ver sección 7) |

## 1. Uso

```asm
#include "mat.asm"            ; o #include <mat.asm>: el archivo está en spl/include/
```

También se puede usar con el archivo maestro del Integrante 4, que ya tenía reservado el gancho:

```asm
#define INCLUIR_MATRICES
#include "estructuras.inc"    ; layout + vec.asm + cabeceras.asm + mat.asm
```

`#pragma once` y una guarda `#ifndef` impiden la doble inclusión. `mat.asm` incluye a su vez
`cabeceras.asm`, porque la matriz necesita su cabecera (`MAT_INIT`), y ese archivo también está
protegido. Las dos librerías empiezan con un `JMP` que salta su cuerpo, así que pueden incluirse al
inicio o al final del programa.

## 2. Decisiones de diseño

**Distribución en memoria (orden por filas).** `base` apunta a `M[0][0]` y
`&M[i][j] = base + ((i·C + j) << 3)`. Es la misma fórmula de la macro `MAT_DIR` de
`layout_datos.inc` y de `DescriptorMatriz.direccion_elemento`. Una prueba compara la expansión de la
macro con el resultado de `MAT_ADDR` en la CPU. Como la fila `i` es un vector contiguo de `C`
elementos que empieza en `base + ((i·C) << 3)`, las primitivas `VEC_*` del Integrante 2 funcionan sobre
una fila sin convertir nada. El programa de prueba lo hace con `VEC_GET` y las pruebas con
`VEC_SWAP`.

**La cabecera es obligatoria.** `C` se lee de `[base − 8]` y `F` de `[base − 16]`. Es el contrato que
fijó el Integrante 4 (`MAT_INIT`, `DESC_MAT_INIT` y `DescriptorMatriz` con cabecera *inline*). Se
descartó pasar `C` como argumento porque la convención solo tiene cuatro registros de argumentos:
`MAT_SET` ya usa los cuatro (base, i, j y valor), así que `C` habría tenido que ir en la pila como quinto
argumento en cada acceso. Al leerla de la cabecera, la matriz se describe a sí misma y todas las rutinas
reciben los argumentos en registros.

**`MAT_ADDR` usa `MUL`, `ADD` y `SHL`.** `C` es arbitrario (no siempre es una potencia de 2), por eso
`i·C` necesita `MUL`. El factor 8 sí es una potencia de 2 y se resuelve con `SHL 3`. `MUL` conserva los
64 bits menos significativos, y la ISA no tiene `MULI`, así que `C` tiene que estar en un registro (R5).
La rutina es una hoja: solo modifica R5 y las banderas.

```asm
MAT_ADDR:
        LOAD R5, [R1 - 8]           ; R5 = C
        MUL  R5, R2, R5             ; R5 = i * C
        ADD  R5, R5, R3             ; R5 = i * C + j
        SHL  R5, R5, 3              ; R5 = (i * C + j) * 8
        ADD  R5, R1, R5             ; R5 = base + ((i * C + j) << 3)
        RET
```

**`MAT_GET` y `MAT_SET` llaman a `MAT_ADDR`.** En `vec.asm` el cálculo se escribió en línea para
ganar velocidad. Aquí la fórmula 2D vive en un solo lugar, como pide la tarea, y las rutinas la
reutilizan con una llamada anidada. Como `MAT_ADDR` solo toca R5, no hace falta apilar R1 a R4
alrededor de la llamada.

**Marco `ENTER 0` / `LEAVE` en las rutinas no hoja.** La convención escrita de la librería (informe
del Integrante 2, sección 3) dice: «las rutinas hoja no crean marco; las rutinas no hoja usan `ENTER t` y
`LEAVE`». `MAT_GET`, `MAT_SET` y `MAT_CLEAR` no son hojas. Ninguna necesita variables locales, así que
`t = 0`, pero cada una enlaza su marco: `[BP]` guarda el BP del llamador. Así la cadena de marcos se
puede recorrer completa durante cualquier llamada anidada (sección 3). Cuesta dos instrucciones por
llamada. La versión en línea y sin marco de `MAT_GET` gastaría 7 instrucciones en vez de 11 (cifra
calculada, no medida: esa variante no se implementó). Se prefirió la uniformidad con la ABI y con
`merge_sort.asm`.

**`MAT_CLEAR` recorre un solo bloque.** En orden por filas, la matriz son `F·C` palabras contiguas.
La rutina obtiene `F` y `C` con llamadas anidadas a `MAT_ROWS` y `MAT_COLS` (`cabeceras.asm`) y escribe
`R0` con un solo puntero: 4 instrucciones por elemento. Devuelve en R5 la cantidad de palabras que
borró. Si `F·C ≤ 0`, no escribe nada (`JZ` y `JN`, como en `VEC_COPY`). Los bits en cero son también el
double `+0.0`, así que sirve igual para matrices de enteros y de reales.

**Sin comprobación de límites.** Se sigue el criterio de `vec.asm`: comprobar que `0 ≤ i < F` y
`0 ≤ j < C` costaría al menos dos lecturas de la cabecera, dos `CMP` y dos saltos en cada acceso (con
comparación sin signo, `JNC`, un índice negativo también queda fuera de rango). El llamador es responsable
de los índices. Si se necesita una versión con validación, se puede envolver la rutina sin cambiar las
primitivas.

**Por qué la gestión de pila no está en macros `#define`.** Se comprobó con el preprocesador del
equipo. Una macro siempre se expande en una sola línea: la continuación con `\` produce
`PUSH R1 PUSH R1` en una sola línea, y un `;` dentro del cuerpo inicia un comentario. El ensamblador
acepta una instrucción por línea, así que una macro no puede generar una secuencia `PUSH`/`POP`. Por
eso la disciplina de pila se implementó en las subrutinas.

## 3. Gestión de la pila en llamadas anidadas (R6 = SP, R7 = BP)

Reglas (las mismas de `vec.asm`, `cabeceras.asm` y `merge_sort.asm`):

| Elemento | Regla |
|---|---|
| Argumentos y retorno | R1 a R4 (del 5.º en adelante, en la pila); retorno en R5 |
| Preservados | R1 a R4, SP y BP. Si una rutina usa uno como temporal, lo guarda con `PUSH` y lo recupera con `POP` en orden inverso |
| Destruidos | R5 y las banderas Z, N, C y V |
| `CALL` / `RET` | `CALL` apila el retorno (`SP −= 8`) y `RET` lo desapila. Cada nivel de anidamiento ocupa su propia palabra (LIFO) |
| Rutina no hoja | `PUSH` de los registros que usa → `ENTER t` (apila BP, `BP = SP`, `SP −= t`) → cuerpo → un único `LEAVE` (`SP = BP`, desapila BP) → `POP` en orden inverso → `RET` |
| Marco tras `k` `PUSH` y `ENTER t` | `[BP + 8(k+1)]` retorno · `[BP + 8k … BP + 8]` registros guardados · `[BP]` BP del llamador · `[BP − 8 … BP − t]` locales |

Contenido de la pila en `prueba_mat.asm` cuando la CPU entra en `MAT_ADDR` por la cadena
`INICIO → SUMAR_MATRIZ → MAT_GET → MAT_ADDR` (`S = 0x00400000`). La prueba
`test_cadena_de_marcos_en_tres_niveles` detiene la CPU en ese punto y comprueba cada palabra:

| Dirección | Contenido | Desde el marco |
|---|---|---|
| `S − 8` | retorno a `INICIO` (`TRAS_SUMAR`) | `BP_s + 32` |
| `S − 16` / `S − 24` / `S − 32` | R2, R3 y R4 guardados por `SUMAR_MATRIZ` | `BP_s + 24` / `+16` / `+8` |
| `S − 40` | BP de `INICIO` (= `S`) | `BP_s` ← marco de `SUMAR_MATRIZ` |
| `S − 48` / `S − 56` | locales `F = 3` y `C = 4` | `BP_s − 8` / `BP_s − 16` |
| `S − 64` | retorno a `SUMAR_MATRIZ` | `BP_g + 8` |
| `S − 72` | `BP_s` (enlace dinámico) | `BP_g` = BP actual ← marco de `MAT_GET` |
| `S − 80` | retorno a `MAT_GET` | `SP` |

Si se sigue `[BP]` desde `BP_g`, se llega a `BP_s` y luego a `S`: dos marcos, en el orden de las
llamadas. Al volver, cada `LEAVE`, `POP` y `RET` deshace exactamente lo que apiló su rutina, y el
programa termina con `SP = BP = 0x00400000`. La prueba `test_recursion_profunda_con_marcos` lleva la
misma disciplina a 300 niveles: una suma recursiva crea un marco por fila y llama a `MAT_GET` en cada
uno.

## 4. Subrutinas

Las instrucciones se cuentan desde la etiqueta hasta `RET`, incluido, sin contar el `CALL` del
llamador. Incluyen las de las rutinas anidadas. Se midieron en el emulador: la FSM gasta 5 ciclos por
instrucción. La pila es la profundidad máxima medida, contando el retorno que apila el `CALL` del
llamador.

| Subrutina | Entradas | Salida | Modifica | Instrucciones | Pila |
|---|---|---|---|---|---|
| `MAT_ADDR` | R1 = base, R2 = i, R3 = j | R5 = `base + ((i·C + j) << 3)` | R5, banderas | 6 | 1 palabra |
| `MAT_GET` | R1 = base, R2 = i, R3 = j | R5 = `M[i][j]` | R5, banderas | 11 | 3 palabras |
| `MAT_SET` | R1 = base, R2 = i, R3 = j, R4 = valor | `M[i][j] = R4` | R5, banderas, memoria | 11 | 3 palabras |
| `MAT_CLEAR` | R1 = base | R5 = `F·C` (0 si `F·C ≤ 0`) | R5, banderas, memoria (R1 y R2 se restauran) | 20 + 4n; 18 si n = 0; 19 si n < 0 | 5 palabras |

## 5. Programa de prueba (`spl/ejemplos/prueba_mat.asm`)

Usa M = `0x00260000` (`BASE_MATRICES`, 3 × 4), N = `0x00260100` (2 × 3, con un centinela justo
después) y deja los resultados en `0x002E0000` (`BASE_BUFFERS`). La pila y el BP empiezan en
`0x00400000`. Estado al llegar a `HLT`, verificado por `TestProgramaDePrueba`:

| Zona | Contenido |
|---|---|
| M (cabecera 3, 4) | `0, 1, 2, 0xC004000000000000 (−2.5)` · `10, 11, 12, 13` · `20, 21, 22, 23` |
| N (cabecera 2, 3) | seis ceros; el centinela en `N + 48` sigue valiendo 12 |
| RES[0..8] | `0x00260048` (MAT_ADDR(M,2,1)), 12, 23, 138 (SUMAR_MATRIZ), `0x00260000` y 3 (R1 y R3 preservados), `0xC004000000000000`, 13 (VEC_GET sobre la fila 1), 6 (MAT_CLEAR) |
| Registros | R1 = `0x00260100`, R2 = 2, R3 = 3, R4 = `0x002E0000`, SP = BP = `0x00400000` |

En total: 768 instrucciones y 3840 ciclos.

## 6. Pruebas (`tests/test_spl/test_mat_lib.py`, 74 casos)

| Grupo | Casos | Qué comprueba |
|---|---|---|
| Inclusión | 8 | `#include` desde `spl/include/`; doble inclusión sin etiquetas duplicadas; gancho `INCLUIR_MATRICES` con `#define` y con `definiciones`; lexer del ensamblador sin errores; no se ejecuta por caída; también sirve incluida al final |
| Programa de prueba | 5 | El estado completo de la sección 5 |
| `MAT_ADDR` | 19 | Usa exactamente `LOAD, MUL, ADD, SHL, ADD`; 8 geometrías (una fila, una columna, desplazamientos de más de 16 bits); coincide con la macro `MAT_DIR`; en una matriz de una fila coincide con `VEC_ADDR` |
| `MAT_GET` / `MAT_SET` | 17 | Los 12 elementos de una 3 × 4; `MAT_SET` solo cambia su celda (cabecera y centinela intactos); los bits de seis doubles (−0.0, subnormal, π…) pasan sin cambios |
| `MAT_CLEAR` | 9 | Borra exactamente F·C palabras en 7 geometrías, incluidas 0 × 4 y 4 × 0; con dimensiones negativas no escribe; tras borrar quedan `+0.0` |
| Convención y pila | 13 | Preserva R1 a R4, SP y BP; profundidad máxima de pila por rutina; contenido exacto del marco durante la llamada anidada (`MAT_GET`, `MAT_SET`, `MAT_CLEAR`); cadena de marcos de tres niveles; recursión de 300 marcos |
| Integración | 3 | Matriz precargada con `DescriptorMatriz` (Python); `DESC_MAT_INIT` + `MAT_CLEAR` con el descriptor en `BASE_CABECERAS`; `VEC_SWAP` sobre una fila |

Para comprobar que las pruebas detectan errores reales, se introdujeron cinco defectos en `mat.asm`,
uno a la vez: quitar el `SHL`, quitar el marco de `MAT_GET`, guardar R3 en vez de R4 en `MAT_SET`,
avanzar 16 bytes en `MAT_CLEAR` y no restaurar R1. Los cinco fueron detectados (entre 7 y 41 pruebas
fallidas cada uno) y el archivo se restauró idéntico byte a byte.

Suite completa del repositorio: **1693 pruebas aprobadas, 1 omitida y 419 subpruebas**, con Python
3.14.

## 7. Ajuste a una prueba del Integrante 4 (autorizado por el PM)

`test_gancho_condicional_incluir_matrices_con_modulo_2d` simulaba el módulo 2D con un `mat.asm` falso
en un directorio temporal. Ahora que `spl/include/mat.asm` existe, la prueba no puede funcionar así:
un `#include "mat.asm"` dentro de `estructuras.inc` busca primero en el directorio del archivo que
incluye, y siempre encuentra el módulo real antes que el falso. El gancho funciona bien, pero la
premisa de la prueba (que el módulo no existe) dejó de cumplirse. Con autorización del PM, se cambió
solo esa prueba: conserva su nombre, comprueba que el gancho trae `MAT_ADDR:` y que el programa sigue
ejecutándose (`R1 = 9`). No se modificó ningún archivo de la librería del Integrante 4.

## 8. Párrafo para el manual técnico

> El módulo de matrices (`spl/include/mat.asm`) es la capa 2D de la librería de estructuras de datos de
> Enigma-64. Se incorpora con `#include "mat.asm"` o definiendo `INCLUIR_MATRICES` antes de
> `#include "estructuras.inc"`. Una matriz de F filas y C columnas es un bloque contiguo de palabras de
> 64 bits en orden por filas, precedido por una cabecera con F en `base − 16` y C en `base − 8`. El
> elemento (i, j) está en `base + ((i·C + j) << 3)`. `MAT_ADDR` calcula esa dirección con `MUL`, `ADD` y
> `SHL`. `MAT_GET` y `MAT_SET` la reutilizan mediante una llamada anidada. `MAT_CLEAR` pone a cero las
> F·C palabras. Cada fila es un vector, de modo que las primitivas `VEC_*` operan sobre ella
> directamente. El módulo sigue la convención de llamada de toda la librería: argumentos en R1–R4,
> resultado en R5, y R1–R4, SP (R6) y BP (R7) preservados. Las rutinas que llaman a otras guardan con
> `PUSH` los registros que usan, abren un marco con `ENTER` y salen por un único `LEAVE`, `POP` y
> `RET`. Así la pila queda balanceada y la cadena de marcos enlazada por BP se puede recorrer en
> cualquier nivel de anidamiento.
