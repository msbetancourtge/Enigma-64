# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Proyecto:** Módulo Enlazador-Cargador (Enigma-64 — Noctua Systems)  
**Documento Técnico — Enlazador: análisis de módulos objeto reubicables (`.obj`), enlace y reubicación**  
**Autor:** Michael Stiven Betancourt Gelves (Integrante 3)

---

## 1. Alcance

La especificación de la Tarea 9 asigna la región `0x00001000`–`0x000FFFFF` al bloque **Monitor + Enlazador-Cargador** y describe así al Cargador: *"No traduce ensamblador ni resuelve símbolos entre módulos (tarea del Enlazador); su función es la ubicación física en memoria y la transferencia de control al programa cargado"*. El repositorio ya tenía el Cargador (`CargadorEnigma`, Tarea 10), pero no el Enlazador. Para combinar código de varios archivos había que concatenar las fuentes y ensamblarlas juntas, que es como se arma hoy `CODIGO_FPU_ASM`.

Este trabajo completa el Enlazador. La pieza central es el análisis de los módulos objeto reubicables: reconocer los encabezados de sección, extraer las tablas de exportación e importación e interpretar las marcas de reubicación, que indican qué bytes de la memoria hay que parchar. Sobre ese análisis se construyó el enlace y su conexión con el Cargador.

### Trabajo realizado

1. **Entorno local.** Se tomó la rama remota más reciente, `feat/compilador-vocabulario-base`, que ya incluye `feat/preprocesador`, `feat/lexer-ensamblador` y `feat/tablas-simbolos-literales`. Se instaló `ply`, que figuraba en `requirements.txt` pero faltaba en el entorno virtual; sin él no corrían las 199 pruebas del SPL. Punto de partida: 669 pruebas aprobadas y 1 omitida a propósito.
2. **Formato `.obj`** (sección 3) y **marcas de reubicación** (sección 4).
3. **Analizador y escritor** de módulos objeto: `enigma64/enlazador/objeto.py` (sección 5).
4. **Enlazador de dos pasadas** e integración con el Cargador y la interfaz: `enigma64/enlazador/enlace.py` (sección 6).
5. **Verificación** con pruebas propias y con código real del equipo: el programa de Euclides y la biblioteca FPU completa (sección 8).
6. **Revisión de la interfaz**, donde apareció un fallo previo de integración entre la CPU y el cargador (sección 9).
7. **Publicación** en la rama `feat/enlazador-objetos`.

### Archivos

| Archivo | Contenido |
| :--- | :--- |
| `enigma64/enlazador/objeto.py` | Formato `.obj`: modelo de datos, analizador con validación y escritor |
| `enigma64/enlazador/enlace.py` | `EnlazadorEnigma`: ubicación de secciones, tabla global de símbolos, resolución de importaciones y aplicación de marcas |
| `enigma64/enlazador/__main__.py` | Línea de comandos `python -m enigma64.enlazador` |
| `enigma64/enlazador/ejemplos.py` | Módulos objeto de ejemplo (`principal.obj` y `libmat.obj`) |
| `enigma64/enlazador/__init__.py` | API pública del paquete |
| `enigma64/cargador.py` | Firma `MAGIC_OBJETO` y reconocimiento de `.obj` en `cargar_archivo` |
| `enigma64/ui/paneles/panel_cargador.py` | Opción `*.obj` en el selector de archivos de la pestaña Cargador |
| `tests/core/test_enlazador.py` | 50 pruebas (82 subpruebas) |
| `README.md` | Sección del enlazador y conteos de pruebas corregidos |

## 2. Restricciones del ISA que guían el diseño

Las marcas de reubicación salen de los campos de instrucción que pueden contener una dirección (tabla `_INSTRUCTIONS` de `enigma64/cpu.py`):

| Formato | Instrucciones | Campo | Consecuencia para el enlazador |
| :--- | :--- | :--- | :--- |
| Absoluto (5 B) | `JMP`, `CALL` | Bytes 1–4: dirección de 32 bits | Depende de dónde quede el destino, aunque la etiqueta esté en el mismo módulo: necesita `ABS32` |
| Relativo (3 B) | `JZ`, `JNZ`, `JC`, `JNC`, `JN`, `JP`, `JV`, `JNV` | Bytes 1–2: desplazamiento con signo desde la instrucción siguiente | Dentro de un módulo no cambia al mover el código; hacia otro módulo necesita `REL16` |
| Inmediato y memoria (4 B) | `ADDI`, `SUBI`, `LOAD`, `STORE`, `LDB`, `STB` | Bytes 2–3: 16 bits con extensión de signo | Una dirección de 32 bits se arma con `ADDI`, `SHL 16`, `ADDI`: necesita el par `HI16` / `LO16` |
| Datos | Palabras de 64 bits | 8 bytes | Un puntero guardado en `.data` necesita `ABS64` |

Otras restricciones:

- La máquina es Big-Endian y direccionable por byte; el formato también es Big-Endian, igual que el `.e64`.
- Las instrucciones miden de 1 a 5 bytes y no tienen alineación, así que el código se ubica con alineación 1. Los datos se alinean a 8 porque `LOAD` y `STORE` exigen alineación natural.
- Los programas solo se cargan en la región de usuario, `0x00200000`–`0xBFFFFFFF`. El enlazador no duplica esa regla: la sigue aplicando `CargadorEnigma`.

## 3. Formato del módulo objeto (`.obj`)

```
+-------------------------------+ 0
| Cabecera                52 B  |
+-------------------------------+ off_secciones
| Encabezados de sección  20 B c/u
+-------------------------------+
| Contenido de secciones BITS   |  (.bss no ocupa bytes en el archivo)
+-------------------------------+ off_simbolos
| Tabla de símbolos       12 B c/u
+-------------------------------+ off_reubicaciones
| Marcas de reubicación   16 B c/u
+-------------------------------+ off_cadenas
| Tabla de cadenas (UTF-8, NUL) |
+-------------------------------+
```

### 3.1 Cabecera (52 bytes, `>4sHHHHIIIIIIIIII`)

| Campo | Tipo | Descripción |
| :--- | :--- | :--- |
| `magia` | 4 bytes | `"EOBJ"`, distinta de la del ejecutable `.e64` (`"ENIG"`) |
| `version` | `H` | `1` |
| `maquina` | `H` | `0xE064` (Enigma-64) |
| `banderas` | `H` | Bit 0: el módulo declara el punto de entrada |
| `seccion_entrada`, `offset_entrada` | `H`, `I` | Punto de entrada, relativo a una sección |
| `nombre_modulo` | `I` | Offset del nombre en la tabla de cadenas |
| `num_*`, `off_*` | `I`, `I` | Cantidad y posición de los encabezados de sección, los símbolos y las marcas |
| `tam_cadenas`, `off_cadenas` | `I`, `I` | Tamaño y posición de la tabla de cadenas |

### 3.2 Encabezado de sección (20 bytes, `>IHHIII`)

| Campo | Descripción |
| :--- | :--- |
| `nombre` | Offset en la tabla de cadenas (`.text`, `.data`, `.bss` o un nombre propio) |
| `tipo` | `1` = BITS (el contenido está en el archivo), `2` = VACIA (solo reserva memoria en cero) |
| `permisos` | R = 1, W = 2, X = 4, como la columna "Permisos" del mapa de memoria |
| `alineacion` | Potencia de 2 entre 1 y 4096 |
| `tamano` | Bytes que ocupa en memoria |
| `offset` | Posición del contenido en el archivo (0 en las secciones VACIA) |

### 3.3 Símbolo (12 bytes, `>IHBBI`)

| Campo | Descripción |
| :--- | :--- |
| `nombre` | Offset en la tabla de cadenas |
| `seccion` | Índice de la sección que lo define; `0xFFFF` = importado, `0xFFFE` = constante absoluta |
| `ligadura` | `0` = LOCAL, `1` = GLOBAL |
| `tipo` | `0` = SIN_TIPO, `1` = FUNCION, `2` = DATO |
| `valor` | Offset dentro de su sección, o el valor de la constante |

De estos campos salen las tablas que pide el análisis:

- **Tabla de exportaciones:** símbolos GLOBAL definidos en el módulo (en una sección o como constante absoluta).
- **Tabla de importaciones:** símbolos con sección `0xFFFF`, que siempre son GLOBAL.
- **Símbolos locales:** etiquetas internas. El enlazador las usa para reubicar, pero no las publica.

### 3.4 Marca de reubicación (16 bytes, `>HBBIIi`)

| Campo | Descripción |
| :--- | :--- |
| `seccion` | Sección que contiene el campo a parchar |
| `tipo` | Tipo de marca (sección 4) |
| `reservado` | Siempre `0` |
| `offset` | Posición del primer byte del campo dentro de la sección |
| `simbolo` | Índice del símbolo cuya dirección se escribe |
| `sumando` | Entero con signo que se suma a la dirección del símbolo |

### 3.5 Tabla de cadenas

Nombres UTF-8 terminados en NUL y referenciados por offset. El offset 0 es la cadena vacía y el escritor no repite nombres.

## 4. Marcas de reubicación

S = dirección final del símbolo, A = sumando, P = dirección final del primer byte del campo.

| Tipo | Ancho | Valor escrito | Rango válido | Uso |
| :--- | :--- | :--- | :--- | :--- |
| `ABS64` | 8 B | `S + A` | 0 a 2⁶⁴−1 | Puntero en `.data` |
| `ABS32` | 4 B | `S + A` | 0 a `0xFFFFFFFF` | Destino de `JMP` / `CALL` |
| `REL16` | 2 B | `S + A − (P + 2)` | −32768 a 32767 | Desplazamiento de `JZ`, `JNZ`, … |
| `HI16` | 2 B | `(S + A + 0x8000) >> 16` | `S + A` menor que `0x7FFF8000` | Inmediato del `ADDI` que precede a `SHL 16` |
| `LO16` | 2 B | `(S + A) & 0xFFFF` | 0 a `0xFFFFFFFF` | Inmediato del segundo `ADDI` o desplazamiento de `LOAD` / `STORE` |

**REL16.** El campo son los dos últimos bytes de una instrucción de 3 bytes, así que la instrucción siguiente empieza en `P + 2`. Es la convención de los trazados de la Tarea 9: *"los desplazamientos de los saltos relativos se calculan respecto a la dirección de la instrucción siguiente al salto"*.

**HI16 ajustado.** La CPU extiende el signo de los inmediatos de 16 bits. Si la parte baja es `0x8000` o mayor, el segundo `ADDI` resta `0x10000` en lugar de sumar, y la parte alta lo compensa sumando `0x8000` antes del desplazamiento. Ejemplo con `X = 0x00209000`:

```
LO16 = 0x9000           -> la CPU lo interpreta como -0x7000
HI16 = (0x00209000 + 0x8000) >> 16 = 0x0021
ADDI R1, R0, 0x0021     -> R1 = 0x00000021
SHL  R1, R1, 16         -> R1 = 0x00210000
ADDI R1, R1, 0x9000     -> R1 = 0x00210000 - 0x7000 = 0x00209000
```

Cuando la parte baja es menor que `0x8000`, `HI16` coincide con la parte alta de siempre (`0x00201000` da `0x0020`), así que los programas actuales del equipo no cambian. Como el primer `ADDI` también extiende el signo, la parte alta no puede pasar de `0x7FFF`: la secuencia solo construye direcciones menores que `0x7FFF8000` (`LIMITE_HI16`). Por encima, el enlazador lo reporta como desbordamiento en lugar de generar código erróneo.

**Sumando explícito.** El enlazador escribe `S + A` sin leer lo que había en el campo. Por convención el ensamblador deja esos campos en cero.

## 5. Análisis del módulo objeto (`objeto.py`)

`ModuloObjeto.deserializar` recorre el archivo en este orden. `analizar_objeto` hace lo mismo y además acepta una ruta o un módulo ya construido.

1. Lee la cabecera y comprueba firma, versión, máquina y banderas.
2. Verifica que cada tabla quepa en el archivo antes de leerla.
3. Lee los encabezados de sección y el contenido de las secciones BITS.
4. Lee los símbolos y las marcas, resolviendo los nombres en la tabla de cadenas.
5. Ejecuta `ModuloObjeto.validar()`, la misma validación que corre el escritor antes de serializar. Así ningún módulo incoherente entra ni sale del enlazador.

Cualquier fallo lanza `ObjetoInvalido`, que también es `FormatoInvalido` y `ErrorCargador`:

| Elemento | Se rechaza si… |
| :--- | :--- |
| Cabecera | La firma, la versión o la máquina no coinciden, hay banderas desconocidas o el archivo mide menos de 52 bytes |
| Tablas | Una tabla o el contenido de una sección se sale del archivo |
| Nombres | Apuntan fuera de la tabla de cadenas, no terminan en NUL o no son UTF-8; los de sección y de símbolo tampoco pueden estar vacíos |
| Secciones | Tipo o permisos desconocidos, alineación que no es potencia de 2 o pasa de 4096, nombre repetido o sección VACIA con contenido |
| Símbolos | Sección inexistente, offset fuera de su sección, importado LOCAL, nombre repetido, ligadura o tipo desconocidos |
| Marcas | Sección inexistente o VACIA, campo que se sale de la sección, tipo desconocido, símbolo inexistente, byte reservado distinto de 0, sumando fuera de 32 bits o dos marcas que parchan los mismos bytes |
| Punto de entrada | Sección inexistente o no ejecutable, u offset fuera de la sección |

API principal:

```python
from enigma64.enlazador import analizar_objeto

modulo = analizar_objeto("programas/objetos/principal.obj")
modulo.cabecera                   # campos de la cabecera, con el offset de cada tabla
modulo.secciones                  # SeccionObjeto: nombre, tipo, permisos, alineacion, tamano, offset_archivo
modulo.exportaciones              # tabla de exportaciones
modulo.importaciones              # tabla de importaciones
modulo.locales                    # etiquetas internas
modulo.reubicaciones              # MarcaReubicacion: seccion, offset, tipo, simbolo, sumando
modulo.referencias("sumar")       # marcas que usan un símbolo
modulo.marcas_de_seccion(".text") # marcas de una sección, ordenadas por offset
print(modulo.informe())           # volcado legible, al estilo de objdump
```

Para construir módulos en memoria, que es lo que hará el backend del ensamblador, están `SeccionObjeto.texto/datos/reserva`, `SimboloObjeto.local/exportado/importado`, `MarcaReubicacion` y `ModuloObjeto.serializar()` / `guardar()`.

## 6. Enlace y carga (`enlace.py`)

`EnlazadorEnigma` sigue el esquema clásico del cargador-enlazador de dos pasadas.

**Pasada 1, asignación.**

- Las secciones se ubican por clase: primero el código de todos los módulos, luego los datos y al final las reservas `.bss`. Dentro de cada clase, las secciones del mismo nombre van juntas y en el orden de los módulos.
- Cada sección empieza en la siguiente dirección múltiplo de su alineación.
- Con las exportaciones se arma la tabla global de símbolos (ESTAB). Si dos módulos exportan el mismo nombre se lanza `SimboloDuplicado`.

**Pasada 2, enlace y reubicación.**

- Cada importación se busca en la ESTAB. Las que faltan se reportan juntas en un solo `SimboloNoDefinido`, cuyo atributo `faltantes` indica qué módulo importa cada una.
- Cada marca se aplica sobre la imagen de memoria con su fórmula. Si el valor no cabe en el campo se lanza `DesbordamientoReubicacion`, con el módulo, la sección, el offset y el símbolo.
- Las reservas `.bss` quedan escritas en ceros dentro de la imagen.

**Punto de entrada:** el símbolo indicado en `entrada`; si no se indica, el que declare un módulo; si ninguno lo declara, el inicio del código. Que dos módulos declaren entrada es un error.

**Resultado:** un `BinarioEnigma` absoluto (`reubicable=False`), el mapa de secciones y la ESTAB. Es absoluto porque la tabla de reubicación del `.e64` solo parcha palabras de 8 bytes y no sabría corregir campos `ABS32`, `REL16` ni `HI16`/`LO16`. Por eso `enlazar_y_cargar` enlaza directamente en la dirección de carga y deposita la imagen con `CargadorEnigma`, que sigue aplicando las fronteras del mapa de memoria e inicializa PC, SP, SR, R0 y R5.

**Integración.**

- `CargadorEnigma.cargar_archivo` reconoce la firma `EOBJ`, enlaza el módulo en la dirección destino y lo carga. Si el módulo importa símbolos lo rechaza con `SimboloNoDefinido`; para varios módulos se usa `EnlazadorEnigma`.
- La pestaña Cargador ofrece `*.obj` en su selector de archivos. No hizo falta nada más en la interfaz, porque el botón Cargar archivo ya llega a `cargar_archivo`.

**Programa de ejemplo** (`ejemplos.py`). El módulo `principal` lee `a` y `b` de su `.data`, llama a `sumar` (importada de `libmat`), guarda el resultado y lo copia en `.bss` a través de un puntero. Si la suma da cero, salta a `error`, también de `libmat`. Entre los dos módulos usan los cinco tipos de marca. Mapa de enlace en `0x00200000`:

| Dirección | Tamaño | Permisos | Sección | Módulo |
| :--- | :--- | :--- | :--- | :--- |
| `0x00200000` | 57 | R-X | `.text` | principal |
| `0x00200039` | 13 | R-X | `.text` | libmat |
| `0x00200048` | 32 | RW- | `.data` | principal (`0x00200046` alineado a 8) |
| `0x00200068` | 16 | RW- | `.bss` | principal |

ESTAB: `main` = `0x00200000`, `sumar` = `0x00200039`, `error` = `0x0020003D`, `resultado` = `0x00200058`, `copia` = `0x00200068`. Se aplican 6 marcas y la imagen ocupa 120 bytes.

## 7. Decisiones de diseño

| Punto | Decisión | Razón |
| :--- | :--- | :--- |
| Orden de bytes | Big-Endian en todo el archivo | Es el de la máquina y el del `.e64` |
| Ubicación de las tablas | La cabecera guarda el offset de cada tabla | El analizador verifica cada región antes de leerla |
| Nombres | Tabla de cadenas UTF-8 terminadas en NUL | Sin límite de longitud y sin repetir nombres |
| Validación | Estricta, al leer y al escribir | Un `.obj` corrupto se detiene antes de llegar a la RAM, con un mensaje que dice qué campo falló |
| Sumando | Explícito en la marca | La fórmula no depende del contenido previo del campo |
| Salida | Ejecutable absoluto, enlazado en la dirección de carga | La reubicación del `.e64` solo maneja palabras de 8 bytes |
| `.bss` | Se escribe en ceros | La RAM puede conservar datos de una carga anterior |
| Importaciones sin resolver | Se reportan todas a la vez | Se ve en un solo intento todo lo que falta enlazar |
| Organización | Subpaquete `enigma64/enlazador/` con `__main__.py` | Mismo patrón que `spl/ensamblador`; `python -m enigma64.enlazador` funciona sin advertencias y `cargador.py` casi no cambia |
| Ejemplos | Código máquina escrito byte a byte con comentarios | Mismo estilo que `enigma64/programas.py`; una prueba lo compara con la salida del ensamblador oficial |

## 8. Verificación

### 8.1 Suite `tests/core/test_enlazador.py`

| Grupo | Qué verifica |
| :--- | :--- |
| `TestCabeceraYSecciones` | Firma, versión, máquina, cantidades y offsets; tipo, permisos, alineación, tamaño, clase y posición de cada sección |
| `TestTablasDeSimbolos` | Tablas de exportación e importación, símbolos locales y referencias de cada importación |
| `TestMarcasDeReubicacion` | Sección, offset, tipo, ancho, símbolo y sumando de cada marca; que cada campo caiga en el operando de la instrucción correcta |
| `TestSerializacion` | Ida y vuelta byte a byte, nombres UTF-8, lectura desde disco, informe y coincidencia de los ejemplos con el ensamblador oficial |
| `TestObjetoInvalido` | 36 archivos corruptos, cada uno rechazado por el motivo esperado, y 7 modelos incoherentes que el escritor no serializa |
| `TestCalculoDeParches` | Fórmulas de los cinco tipos, desbordamientos y reconstrucción de 10 direcciones con `HI16`/`LO16` ejecutando `ADDI`, `SHL` y `ADDI` en la ALU oficial |
| `TestEnlazador` | Mapa y alineación, ESTAB, bytes parchados, `.bss` en ceros, duplicados, importaciones faltantes, constantes absolutas y punto de entrada |
| `TestEnlaceCargaEjecucion` | Ejecución del programa de dos módulos en la CPU oficial en tres bases, salto `REL16` entre módulos y carga de `.obj` desde `cargar_archivo` |
| `TestEnlaceConCodigoDelEquipo` | Euclides y la biblioteca FPU como módulos reubicables (sección 8.2) |
| `TestLineaDeComandos` | Análisis, enlace a un `.e64` que se carga y ejecuta, y códigos de error |

El programa de ejemplo se ejecutó en tres bases:

- `0x00200000`, la base usual.
- `0x00348000`, que deja `valores` en `0x00348048`: la parte baja es mayor o igual que `0x8000`, así que el ajuste de `HI16` se prueba en la CPU real.
- `0x00340003`, una base impar que obliga a rellenar para alinear `.data`.

En las tres el resultado es 42 y se ejecutan 15 instrucciones: el `JMP` reubicado salta la instrucción trampa.

### 8.2 Verificación con código del equipo

**Euclides (Tarea 9).** El binario oficial solo funciona en `0x00200100`, porque sus dos `JMP` llevan direcciones absolutas. Convertido en módulo reubicable, con dos marcas `ABS32`, y enlazado en `0x00400000`, calcula MCD(48, 18) = 6. Como control, el mismo binario cargado en `0x00400000` sin enlazar salta a `0x00200114`, encuentra memoria vacía (que se decodifica como `HLT`) y termina sin resultado.

**Biblioteca FPU (Tarea 17).** Es el caso real de compilación separada que hoy se resuelve concatenando fuentes. El procedimiento fue:

1. Se ensambló `CODIGO_FPU_ASM` en la base 0: 3141 bytes y 897 instrucciones.
2. Las direcciones de las etiquetas exportadas (`FADD`, `FSUB`, `FMUL`, `FDIV`, `FCMP`, `FSQRT`, `FPU_VECTORES`) se obtuvieron sin modificar el ensamblador: se agregó al final un `JMP` por etiqueta y se leyó su campo absoluto.
3. Un barrido lineal con la tabla del ISA marcó cada `JMP` y `CALL` como `ABS32` relativa al inicio de la sección: 68 marcas. El barrido es exacto porque el código FPU no tiene datos incrustados ni etiquetas usadas como inmediato, así que solo `JMP` y `CALL` dependen de la posición.
4. Un cliente compilado aparte, con pila propia en una reserva `.bss` y operandos en `.data`, importa la rutina.
5. Los dos módulos se enlazaron en la base impar `0x00A13457`.

Para `FADD`, `FSUB`, `FMUL`, `FDIV` y `FSQRT`, y para las entradas `VEC_FMUL` y `VEC_FDIV` (importación de `FPU_VECTORES` más un sumando), el resultado es idéntico bit a bit al del ensamblado monolítico de siempre (`EmuladorFPUEnigma64.ejecutar_vector`). En las cuatro operaciones básicas coincide además con el IEEE 754 de Python. Con una sola de las 68 marcas mal aplicada, la FPU dejaría de funcionar en la nueva base.

### 8.3 Regresión

| Comprobación | Resultado |
| :--- | :--- |
| `python -m pytest` | 719 aprobadas, 1 omitida a propósito, 308 subpruebas |
| `python -m unittest discover -s tests` | 280 pruebas, OK |
| Python 3.14 (entorno virtual) y 3.15 | Pasan (en 3.15 se corrió la suite del enlazador); sintaxis compatible desde 3.9. No se probó en 3.11 (`environment.yml`) |
| Pruebas del enlazador y del cargador con `-W error` | Sin advertencias |
| Enlaces internos del `README.md` | 68 revisados, 0 rotos |
| Comandos del `README.md` y pestaña Cargador | Funcionan como se documentan |

## 9. Hallazgo: integración CPU–cargador en la interfaz (pendiente)

Al revisar la interfaz apareció un fallo que ya estaba en `main` y no depende del enlazador: después de que un programa termina con `HLT`, el siguiente programa cargado desde la pestaña Cargador no se ejecuta.

- **Causa.** `enigma64/ui/servicios/fabrica.py` (clase `Maquina`, líneas 38 y 39) crea los adaptadores del cargador y de la CPU por separado y nunca llama a `conectar_hardware(cpu=...)`. `CargadorEnigma.cargar_binario` detiene la CPU antes de cargar y la reanuda al terminar, pero solo cuando la tiene conectada.
- **Parche temporal.** Pulsar Reiniciar en la pestaña CPU *antes* de cargar el programa. Después no sirve, porque el reinicio deja PC = 0.
- **Propuesta.**
  - Parte 1: conectar la CPU al cargador en `Maquina.__init__`.
  - Parte 2: un método de la CPU que limpie el estado transitorio sin tocar los registros (búfer de prebúsqueda, fase, instrucción en curso y halt pendiente), y que el cargador lo llame al reanudar.

  La parte 2 cubre dos casos. Si un programa se carga justo después del anterior, la CPU ejecutaría bytes viejos del búfer de prebúsqueda. Si se carga mientras se avanza fase por fase, se terminaría primero la instrucción del programa anterior.
- **Verificación.** Se reprodujo a través de los servicios de la interfaz. Hoy fallan los dos escenarios; con la parte 1 pasa el caso común y con las dos partes (la segunda simulada) pasan todos.
- **Estado.** Se comunicó al equipo. No se corrigió en esta rama porque toca `cpu.py` y la capa de servicios de la interfaz.

## 10. Limitaciones y trabajo pendiente

- **Ningún ensamblador emite `.obj` todavía.** `enigma64/ensamblador.py` produce bytes planos y el ensamblador SPL va en la fase léxica. Este formato es el contrato que debe seguir su backend:

  | Construcción en ensamblador | Marca que debe emitir |
  | :--- | :--- |
  | `JMP etiqueta` / `CALL etiqueta` (local o externa) | `ABS32` en el byte 1 de la instrucción |
  | Salto condicional hacia otro módulo | `REL16` en el byte 1; dentro del módulo se resuelve al ensamblar |
  | Dirección de una etiqueta con `ADDI` / `SHL 16` / `ADDI` | `HI16` en el byte 2 del primer `ADDI` y `LO16` en el byte 2 del segundo |
  | `.word etiqueta` | `ABS64` en la palabra |
  | `.global` / `.extern` | Símbolo GLOBAL definido / símbolo importado |

- Las direcciones construidas con `HI16`/`LO16` deben quedar por debajo de `0x7FFF8000`.
- No hay bibliotecas de archivos (`.a`), símbolos débiles ni símbolos comunes; el alcance actual no los necesita.
- La pestaña Cargador muestra el resultado de la carga, pero no el mapa de enlace ni la ESTAB que devuelve `enlazar_y_cargar`.

## 11. Manual de usuario

### 11.1 Requisitos

- Python 3.10 o superior.
- El enlazador solo usa la biblioteca estándar. `ply` hace falta únicamente para las pruebas del SPL (`pip install -r requirements.txt`).

### 11.2 Ejecución

Desde la raíz del repositorio:

```bash
# Generar los módulos de ejemplo en programas/objetos/ (carpeta ignorada por git)
python -m enigma64.enlazador.ejemplos

# Analizar un módulo: cabecera, secciones, exportaciones, importaciones y marcas
python -m enigma64.enlazador programas/objetos/principal.obj

# Enlazar dos módulos, imprimir el mapa y escribir un ejecutable .e64
python -m enigma64.enlazador programas/objetos/principal.obj programas/objetos/libmat.obj -o programas/objetos/demo.e64 --mapa

# Pruebas del enlazador
python -m pytest tests/core/test_enlazador.py -v
```

Opciones de la línea de comandos:

- `-o archivo.e64`: escribe el ejecutable enlazado.
- `--base`: dirección de carga del enlace (por defecto `0x00200000`).
- `--entrada`: símbolo exportado que será el punto de entrada.
- `--mapa`: imprime el mapa de enlace y la ESTAB.
- `--sin-informe`: omite el análisis de cada módulo.

El código de salida es `0` si todo sale bien y `1` ante un error (archivo inexistente, objeto inválido, símbolo sin definir…).

En la interfaz (`python main.py`): pestaña Cargador → Examinar → `programas/objetos/demo.e64` → Cargar archivo; luego, en la pestaña CPU, Ejecutar hasta HLT. El resultado, 42, queda en `0x00200058`. Un `.e64` enlazado es absoluto, así que debe cargarse en la misma dirección con la que se enlazó; el campo Dirección destino trae `0x00200000` por defecto. Con un `.obj` autocontenido, en cambio, esa dirección es la base del enlace.

### 11.3 Formato de la salida

Extracto del análisis de `principal.obj`:

```
Modulo objeto 'principal'
  Formato EOBJ v1, maquina 0xE064 (Enigma-64), 493 bytes
  Secciones: 3  Simbolos: 9  Marcas de reubicacion: 6
  Punto de entrada: .text+0x0000

Encabezados de seccion
  Idx  Nombre  Tipo   Clase    Perm  Alin  Tamano  Offset
  0    .text   BITS   CODIGO   R-X   1     57      0x0070
  1    .data   BITS   DATOS    RW-   8     32      0x00A9
  2    .bss    VACIA  RESERVA  RW-   8     16      -

Tabla de exportaciones (3)
  Simbolo    Seccion  Valor       Tipo
  main       .text    0x00000000  FUNCION
  resultado  .data    0x00000010  DATO
  copia      .bss     0x00000000  DATO

Tabla de importaciones (2)
  Simbolo  Tipo     Referencias
  sumar    FUNCION  .text+0x0015 ABS32
  error    FUNCION  .text+0x001D REL16
...
Marcas de reubicacion (6)
  Seccion  Offset  Tipo   Ancho  Simbolo  Origen     Sumando
  .text    0x0002  HI16   2      valores  LOCAL      +0
  .text    0x000A  LO16   2      valores  LOCAL      +0
  .text    0x0015  ABS32  4      sumar    IMPORTADO  +0
  .text    0x001D  REL16  2      error    IMPORTADO  +0
  .text    0x002C  ABS32  4      fin      LOCAL      +0
  .data    0x0018  ABS64  8      copia    GLOBAL     +0
```
