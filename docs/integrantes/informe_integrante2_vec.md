# Informe técnico: librería de vectores `vec.asm` y corrección del ValueError

**Integrante 2: Registros, ALU y Primitivas 1D**

| Archivo | Contenido |
|---|---|
| `spl/include/vec.asm` | Librería: `VEC_ADDR`, `VEC_GET`, `VEC_SET`, `VEC_SWAP`, `VEC_COPY` y `VEC_LEN` |
| `spl/ejemplos/prueba_vec.asm` | Programa de prueba con el estado esperado de la memoria y de los registros |
| `spl/ejemplos/esqueleto_merge_sort.asm` | Esqueleto de merge sort sobre la API (el grupo completa los TODO) |
| `spl/ensamblador/literales.py` | Conversión robusta de literales a double IEEE-754 y a enteros de 64 bits |
| `spl/ensamblador/lexer.py`, `spl/traductor/alu.py`, `spl/traductor/traductor.py` | Usan el conversor en lugar de `int()` y `float()` directos |
| `tests/test_spl/test_vec_lib.py`, `tests/test_spl/test_literales.py` | 104 pruebas nuevas |

## 1. Uso

```asm
#include "vec.asm"        ; o #include <vec.asm>: el archivo está en spl/include/
```

`#pragma once` y una guarda `#ifndef` impiden la doble inclusión. La librería empieza con
`JMP VEC_FIN_LIBRERIA`, así que puede incluirse al inicio o al final del programa sin que el flujo
entre en ella por caída.

## 2. Decisiones de diseño

**Distribución en memoria.** `base` apunta al primer elemento: `&v[i] = base + (i << 3)`. Es la misma
fórmula de la macro `VEC_DIR` de `layout_datos.inc` y es compatible con `MAT_DIR` (orden por filas).
Así, una fila de una matriz es un vector y el módulo de matrices puede usar `VEC_*` sobre ella sin
convertir nada. La longitud se guarda en una **cabecera opcional en `base - 8`**, que solo lee `VEC_LEN`.
Si la cabecera estuviera en `base + 0`, todo índice tendría que sumar 1 y se perdería esa
compatibilidad. `base` debe ser múltiplo de 8: si no, `LOAD` y `STORE` producen `STATUS_MISALIGNED`.

**Sin comprobación de límites.** Comprobar `0 <= i < n` cuesta un `LOAD` de la cabecera, un `CMP` y dos
saltos (unas 4 instrucciones más) en cada acceso. Esa sobrecarga caería en el bucle interno de merge
sort. El llamador es responsable de los índices. Si el grupo necesita validar índices, puede escribir
una envoltura con `VEC_LEN` sin modificar las primitivas.

**Bytes crudos.** Las primitivas mueven 64 bits con `LOAD` y `STORE` y nunca operan sobre el dato. Por eso
sirven igual para enteros con signo, enteros sin signo y double IEEE-754. Las pruebas lo comprueban con
-0.0, el menor subnormal y el mayor double.

**VEC_GET y VEC_SET calculan la dirección en línea.** Las cifras se midieron en el emulador. La FSM
gasta 5 ciclos por instrucción.

| Variante de VEC_GET | Instrucciones (con CALL) | Ciclos | Accesos extra a la pila | Registros |
|---|---|---|---|---|
| En línea: `SHL`, `ADD`, `LOAD`, `RET` | 5 | 25 | 0 | solo R5 |
| Llamando a `VEC_ADDR` | 7 | 35 | 2 (apila y desapila el retorno) | solo R5 |

La versión en línea es un 40 % más rápida y no usa más registros. Solo duplica dos instrucciones.
`VEC_ADDR` se mantiene como contrato público y estable para el módulo de matrices.

**VEC_COPY tiene semántica de `memmove`.** Si `destino < origen`, copia hacia adelante. Si
`destino > origen`, copia hacia atrás. Si `destino = origen` o `n <= 0`, no hace nada. La comparación de
direcciones es sin signo: usa la bandera C, que en Enigma-64 indica *préstamo* (`CARRY_EN_RESTA`). Por
eso funciona aunque las zonas se solapen.

## 3. Convención de llamada (toda la librería, incluidas las matrices)

| Elemento | Regla |
|---|---|
| Argumentos | R1, R2, R3 y R4, en ese orden. Del 5.º en adelante van en la pila: el llamador hace `PUSH` antes de `CALL` y los retira después con `ADDI SP, SP, 8*k` |
| Retorno | R5 (alias `RV`) |
| Preservados (callee-saved) | R1, R2, R3 y R4, además de R6 = SP y R7 = BP. La subrutina que use alguno como temporal lo guarda con `PUSH` y lo recupera con `POP` en orden inverso |
| Destruidos (caller-saved) | R5 y las banderas Z, N, C y V |
| R0 | Siempre vale 0. Sirve como fuente de cero, por ejemplo en `ADD Rd, Rs, R0` (copia) o `CMP Rx, R0` |
| Pila | Crece hacia abajo. `PUSH` hace `SP -= 8` y luego escribe en `[SP]`. `CALL` apila el retorno y `RET` lo desapila, así que toda subrutina deja SP como lo encontró |
| Marco y locales | Las rutinas hoja (todas las `VEC_*`) no crean marco. Las rutinas no hoja usan `ENTER t` y `LEAVE`, con locales en `[BP-8]`, `[BP-16]`, etc. El programa debe poner SP en un múltiplo de 8 antes de llamar, porque `SP_RESET = 0xEFFFFFFF` está desalineado y `LOAD [BP-k]` fallaría |
| Llamadas anidadas | Como R1 a R4 sobreviven, el llamador no tiene que guardarlos y puede llamar en bucle a `VEC_GET` con la misma base. Solo debe salvar R5 si lo necesita después de la llamada |

Se eligió preservar R1 a R4 porque con solo cinco registros libres, si fueran caller-saved, cada bucle
tendría que apilar y desapilar sus índices en cada llamada. Con esta regla el costo lo paga una sola
vez la subrutina que necesita temporales (`VEC_SWAP` y `VEC_COPY`). Las de una línea (`VEC_GET` y
`VEC_SET`) usan solo R5 y no tocan la pila.

## 4. Subrutinas

Las instrucciones se cuentan desde la etiqueta hasta `RET` inclusive, sin el `CALL` del llamador. Se
midieron en el emulador.

| Subrutina | Entradas | Salida | Registros que modifica | Instrucciones |
|---|---|---|---|---|
| `VEC_ADDR` | R1 = base, R2 = i | R5 = base + (i << 3) | R5, banderas | 3 |
| `VEC_GET` | R1 = base, R2 = i | R5 = v[i] | R5, banderas | 4 |
| `VEC_SET` | R1 = base, R2 = i, R3 = valor | v[i] = R3 | R5, banderas, memoria | 4 |
| `VEC_SWAP` | R1 = base, R2 = i, R3 = j | intercambia v[i] y v[j] | R5, banderas, memoria (R2, R3 y R4 se restauran) | 15 (6 accesos a pila) |
| `VEC_COPY` | R1 = destino, R2 = origen, R3 = n | copia n elementos | R5, banderas, memoria (R1, R2 y R3 se restauran) | 9 si n ≤ 0 o destino = origen; 13 + 6n hacia adelante; 17 + 6n hacia atrás |
| `VEC_LEN` | R1 = base | R5 = [base − 8] | R5 | 2 |

## 5. Programa de prueba (`spl/ejemplos/prueba_vec.asm`)

Usa V = `0x00220000` (`BASE_VECTORES`, con la cabecera n = 6), W = `0x00220100` y los resultados en
`0x002E0000` (`BASE_BUFFERS`). La pila está en `0x00400000`. Estado al llegar a `HLT`, verificado por
`TestProgramaDePrueba`:

| Zona | Contenido |
|---|---|
| V[−1..5] | 6 · 50, 20, 30, 40, 40, `0xC004000000000000` (−2.5) |
| W[0..5] | 50, 20, 30, 40, 10, `0xC004000000000000` |
| RES[0..5] | `0x00220018` (VEC_ADDR(V,3)), 30 (VEC_GET(V,2)), `0xC004000000000000`, 6 (VEC_LEN), `0x00220000` y 4 (R1 y R3 preservados tras VEC_SWAP) |
| Registros | R1 = `0x00220000`, R2 = `0x00220008`, R3 = 4, R4 = `0x002E0000`, SP = `0x00400000` |

En total: 285 instrucciones y 1425 ciclos.

## 6. Corrección del ValueError con decimales largos

**Reproducción (Python 3.14).**

| Entrada | Componente | Error |
|---|---|---|
| `mov R1, 999…9` (5000 cifras) | traductor, `parsear_operando` → `int(t)` | `ValueError: Exceeds the limit (4300 digits) for integer string conversion` |
| `ADDI R1, R0, 999…9` | lexer del ensamblador, `_literal_entero` → `int()` | el mismo; el lexer se caía en lugar de reportar un error léxico |
| `1e-07`, `2.5E+10` | traductor, regex `FLOTANTE = [+-]?\d+\.\d+` | sin excepción, pero el literal no se reconocía como flotante |

**Causa.** Desde Python 3.11, `int()` rechaza las cadenas decimales de más de 4300 dígitos. `float()` no
tiene ese límite: CPython redondea correctamente al double más cercano (empate al par) cualquier
cantidad de cifras. Es decir, el problema nunca estuvo en convertir el flotante, sino en pasar por `int()`
y en una regex sin exponente. No se usa `Decimal`, porque convertir texto → Decimal → float
no aporta precisión y añade una conversión intermedia.

**Corrección.** El módulo `spl/ensamblador/literales.py`:

- `literal_a_double(texto)`: valida con `[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?` y convierte con `float()`.
  Si el valor desborda a infinito, lanza `LiteralInvalido` en vez de guardar `inf` en silencio. Si es
  demasiado pequeño, da un subnormal o ±0.0, como dicta IEEE-754.
- `literal_a_bytes(texto, orden="big")`: devuelve `struct.pack('>d', v)`. Se usa big-endian porque la RAM
  de Enigma-64 lee las palabras así (`enigma64/memoria.py`). El enunciado pedía `'<d'`, pero con
  `'<d'` un `LOAD` leería los bytes invertidos. `orden="little"` está disponible si alguna herramienta lo
  necesita.
- `entero_decimal_64(texto)`: mide la cantidad de dígitos antes de llamar a `int()`. Más de 20 dígitos no
  caben en 64 bits.
- `LiteralInvalido` hereda de `ValueError`, así que el código que ya capturaba `ValueError` sigue
  funcionando.

El lexer del ensamblador reporta `literal fuera del rango de 64 bits` o `literal fuera del rango de double`
como error léxico y sigue analizando. Además, cada token `FLOTANTE` lleva en `t.bits` su patrón IEEE-754.
El traductor acepta notación científica y convierte `LiteralInvalido` en un error de traducción.

**Pruebas** (`test_literales.py`, 63 casos): π con 50 cifras, 1/3 con 5000 cifras, `1e-07`, `6.02E+23`, el menor
subnormal, el menor normal, el mayor double, negativos, `+0.0` y `-0.0` (bits distintos),
subdesbordamiento a cero, empate al par en 2^53 + 1, desbordamiento (`1e400`), formas mal escritas (`nan`,
`1_000.5`, `1e`), enteros en los límites de 64 bits y enteros de 5000 cifras.

**Fuera de mi módulo (aviso para el dueño).** `enigma64/ensamblador.py::_parse_int` también lanza un
`ValueError` crudo con cualquier literal no entero (`ADDI R1, R0, 3.14`) y trunca en silencio los
inmediatos a 16 bits (`ADDI R1, R0, 0x00220000` carga 0). No lo modifiqué porque no es parte del trabajo
del integrante 2. Se recomienda envolver el `int()` en un `try` y lanzar `ErrorEnsamblador`, y rechazar
los inmediatos que no quepan en el rango [−32768, 65535].

## 7. Párrafo para el manual técnico

> El módulo de vectores (`spl/include/vec.asm`) es la capa 1D de la librería de estructuras de datos de
> Enigma-64 y se incorpora a cualquier programa con `#include "vec.asm"`. El preprocesador lo resuelve
> desde `spl/include/` y evita la doble inclusión con `#pragma once`. Un vector es una secuencia contigua
> de palabras de 64 bits alineadas a 8 bytes. Su base apunta al primer elemento, de modo que el elemento
> *i* está en `base + (i << 3)`, y su longitud puede guardarse en una cabecera opcional en `base − 8`.
> Ofrece seis primitivas: `VEC_ADDR` (dirección de *v[i]*), `VEC_GET`, `VEC_SET`, `VEC_SWAP`, `VEC_COPY`
> (copia segura aunque las zonas se solapen) y `VEC_LEN`. Todas mueven los 64 bits sin interpretarlos,
> por lo que sirven igual para enteros y para double IEEE-754. La librería entera sigue una única
> convención de llamada: los argumentos van en R1–R4 (del quinto en adelante, en la pila), el resultado
> en R5, y la subrutina preserva R1–R4, SP y BP. Solo R5 y las banderas pueden cambiar. La pila crece
> hacia abajo, cada subrutina la deja balanceada y las rutinas con variables locales usan `ENTER` y
> `LEAVE` con un SP alineado a 8. El módulo de matrices y los algoritmos de prueba (merge sort, entre
> otros) se construyen sobre este contrato.
