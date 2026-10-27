# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Taller #01:** Análisis léxico (SPL de Enigma-64 — Noctua Systems)  
**Documento Técnico — Ensamblador: analizador léxico (PLY / `lex.py`)**  
**Autor:** Tomás Garzón (Integrante 2)

---

## 1. Alcance

Primera fase del ensamblador del SPL: un tokenizador escrito con `ply.lex` (el equivalente en Python de FLEX), igual que el preprocesador del grupo. Archivos:

| Archivo | Contenido |
| :--- | :--- |
| `spl/ensamblador/lexer.py` | Definiciones regulares, vocabulario y la clase `EnsambladorLexer` |
| `spl/ensamblador/__main__.py` | CLI: imprime `<línea, CATEGORÍA, lexema>` y el resumen |
| `spl/ensamblador/ejemplos/prueba.asm` | Programa que usa todas las categorías e incluye 7 errores intencionales |
| `spl/ensamblador/ejemplos/prueba_salida_esperada.txt` | Salida exacta esperada de `prueba.asm` |
| `tests/test_spl/test_lexer_ensamblador.py` | 117 pruebas: vocabulario, literales, errores, CLI y los 11 `.s` oficiales |

## 2. Decisiones sobre la sintaxis de Enigma-64

El enunciado deja varios puntos abiertos. Se resolvieron así, siguiendo la sintaxis que ya usan `enigma64/ensamblador.py` y los `.s` del repositorio:

| Punto | Decisión |
| :--- | :--- |
| Instrucciones | Las **41** del ISA, tomadas de la tabla `_INSTRUCTIONS` de `enigma64/cpu.py`. Una prueba verifica que el lexer y la CPU tengan exactamente el mismo conjunto. |
| Registros | `R0`–`R7`, `PC`, `SR` y los alias por rol `RV` (R5), `SP` (R6) y `BP` (R7), como en `enigma64/registros.py`. |
| Comentario | `;` hasta el fin de línea, que es el que usan todos los `.s` existentes. |
| `#` | Prefijo **opcional** de inmediato (`ADDI R1, R0, #5`). Los programas actuales escriben los inmediatos sin `#`, y ambas formas son válidas. |
| Direccionamiento indirecto | Corchetes, `[BP - 8]` (forma oficial), y paréntesis, `(SP)`. |
| Operadores de desplazamiento | `+` y `-` dentro de la dirección (`[R1 + 8]`). |
| Signo de los literales | El `-` forma parte del literal (`-3`) **salvo** si el token anterior es un operando (registro, número, etiqueta, `]` o `)`). En ese caso es el operador resta: `[BP-8]` da `MENOS` y `8`. Así funcionan tanto `SUBI R4, R4, -1` como `[BP-8]`. |
| Flotantes | Necesitan un dígito antes del punto (`0.5`, no `.5`), para que el punto no se confunda con el inicio de una directiva. Se admite exponente (`-2.5e-3`, `6E2`). |
| Etiquetas | Distinguen mayúsculas, igual que en `ensamblador.py`. Los mnemónicos, registros y directivas no las distinguen. |
| Definición de etiqueta | Se emiten dos tokens, `ETIQUETA_DEF` (el nombre) y `DOS_PUNTOS`. Así el `:` existe como separador propio, como pide el enunciado. |
| `R8`, `R10`, … | Se reportan como error léxico («registro inexistente») y no como etiquetas, porque casi siempre son un registro mal escrito. |
| Rango | Los enteros deben caber en 64 bits: de −2⁶³ a 2⁶⁴−1, con o sin signo. |

## 3. Definiciones regulares

Están al inicio de `lexer.py`. Cumplen el papel de la sección de definiciones de FLEX, y las reglas se construyen con ellas mediante el decorador `@TOKEN`:

```python
DIGITO     = r'[0-9]'
HEX        = r'[0-9a-fA-F]'
BIN        = r'[01]'
LETRA      = r'[a-zA-Z_]'
ID         = LETRA (LETRA | DIGITO)*
REGISTRO   = (?i: BP | PC | R0..R7 | RV | SP | SR )
SIGNO      = -?
EXPONENTE  = [eE][+-]? DIGITO+
FIN_NUM    = (?![\w.])        # el literal no puede ir pegado a letras, dígitos ni '.'
```

## 4. Tabla de categorías léxicas

| Categoría | Patrón / expresión regular | Ejemplos de lexemas |
| :--- | :--- | :--- |
| `MNEMONICO` | `ID` cuyo valor en mayúsculas está en la tabla de 41 instrucciones | `HLT` `ADD` `SUB` `MUL` `DIV` `ADDI` `SUBI` `INC` `DEC` `AND` `OR` `XOR` `NOT` `SHL` `SHR` `ASR` `CMP` `LOAD` `STORE` `LDB` `STB` `JMP` `JZ` `JNZ` `JC` `JNC` `JN` `JP` `JV` `JNV` `JMPR` `CALL` `CALLR` `RET` `PUSH` `POP` `ENTER` `LEAVE` `EI` `DI` `IRET` (también `addi`, `Jmp`) |
| `REGISTRO` | `ID` que cumple `(?i:R[0-7]\|PC\|SR\|RV\|SP\|BP)` | `R0`, `r7`, `PC`, `SR`, `RV`, `SP`, `BP` |
| `DIRECTIVA` | `\.ID` cuyo valor está en {`.data`, `.text`, `.org`, `.word`, `.byte`} | `.data`, `.TEXT`, `.org`, `.word`, `.byte` |
| `ETIQUETA_DEF` | `ID(?=[ \t]*:)` (identificador seguido de `:`, que no se consume) | `main` en `main:`, `ADDR` en `ADDR:` |
| `ETIQUETA_REF` | `ID` que no es mnemónico ni registro | `loop` en `JMP loop`, `ADDR`, `rutina` |
| `ENTERO_DEC` | `-?DIGITO+FIN_NUM` | `0`, `16`, `-3`, `-1` |
| `ENTERO_HEX` | `-?0[xX]HEX+FIN_NUM` | `0x1F`, `0X00201000`, `-0x10` |
| `ENTERO_BIN` | `-?0[bB]BIN+FIN_NUM` | `0b1010`, `0B00001111` |
| `FLOTANTE` | `-?(DIGITO+\.DIGITO+(EXPONENTE)?\|DIGITO+EXPONENTE)FIN_NUM` | `3.14159`, `-2.5e-3`, `6e2`, `1.0E+10` |
| `COMA` | `,` | `,` |
| `DOS_PUNTOS` | `:` | `:` |
| `CORCHETE_IZQ` / `CORCHETE_DER` | `\[` / `\]` | `[` / `]` |
| `PARENTESIS_IZQ` / `PARENTESIS_DER` | `\(` / `\)` | `(` / `)` |
| `INMEDIATO` | `\#` | `#` |
| `MAS` | `\+` | `+` |
| `MENOS` | `-` (y el signo de un literal que sigue a un operando) | `-` en `[BP - 8]` y en `[BP-8]` |
| *(ignorado)* comentario | `;[^\n]*` | `; R1 = base del vector` |
| *(ignorado)* espacios | `[ \t\r]` | espacio, tabulador, `\r` de Windows |
| *(ignorado)* salto de línea | `\n+` (incrementa el contador de líneas) | `\n` |

### Errores léxicos detectados

| Error | Patrón que lo detecta | Ejemplo |
| :--- | :--- | :--- |
| Carácter no válido | cualquier carácter que ninguna regla reconoce (`t_error`) | `@`, `$`, `?`, `"` |
| Literal numérico mal formado | `-?DIGITO[\w.]*` cuando ningún literal válido lo cubre | `0b102`, `0x`, `0xG1`, `12abc`, `3.`, `1.2.3` |
| Literal fuera de 64 bits | literal entero válido con valor fuera de [−2⁶³, 2⁶⁴−1] | `0x1FFFFFFFFFFFFFFFF` |
| Directiva desconocida | `\.ID` que no está en la tabla de directivas | `.float`, `.dato` |
| Registro inexistente | `ID` que cumple `[rR][0-9]+` pero no es R0–R7 | `R8`, `r9`, `R10` |
| Palabra reservada usada como etiqueta | `ETIQUETA_DEF` cuyo nombre es mnemónico o registro | `LOAD:`, `SP:` |

Ante cualquier error, el lexer guarda línea, columna, lexema y mensaje, descarta el lexema y sigue con el análisis.

## 5. Manual técnico

### 5.1 Cómo se resuelven los conflictos

PLY no aplica la regla de la coincidencia más larga de FLEX. Prueba las reglas de función **en el orden en que aparecen en el archivo** y se queda con la primera que coincide. Por eso el orden es:

1. Comentario y salto de línea.
2. Literales, del más específico al más general: `ENTERO_HEX`, `ENTERO_BIN`, `FLOTANTE`, `ENTERO_DEC` y, al final, `NUMERO_MAL` como red de errores. `FIN_NUM` impide que `0b102` se lea como `0b10` seguido de `2`.
3. `DIRECTIVA`.
4. `ETIQUETA_DEF` antes que el identificador genérico.
5. Identificador (`t_ID`).
6. Separadores y operadores.

**Palabras reservadas frente a identificadores.** Hay una sola regla para palabras, `ID`. Primero se lee la palabra completa y después se busca en las tablas de mnemónicos y registros. Así, `ADDR` coincide entero con `ID`, no está en ninguna tabla y queda como etiqueta. Nunca se parte en `ADD` + `R`. Es la técnica que recomienda el manual de PLY y produce el mismo resultado que la coincidencia más larga de FLEX.

**Mayúsculas y minúsculas.** La búsqueda en las tablas se hace con `palabra.upper()` y el patrón `REGISTRO` usa la bandera `(?i:…)`. Es el equivalente de `%option caseless`, pero solo para las palabras reservadas: las etiquetas conservan las mayúsculas.

**El signo menos.** El lexer recuerda la categoría del último token emitido, y la reinicia en cada salto de línea. Si un literal con `-` sigue a un operando, la regla emite `MENOS` y retrocede `lexer.lexpos` una posición después del `-`, de modo que el número se lee en el siguiente token.

### 5.2 Equivalencias con FLEX

| FLEX | Este lexer (PLY) |
| :--- | :--- |
| Sección de definiciones (`DIGITO [0-9]`) | Constantes de módulo `DIGITO`, `HEX`, `ID`, … combinadas con `@TOKEN(...)` |
| `%option caseless` | `upper()` contra las tablas y `(?i:…)` en `REGISTRO` |
| `%option noyywrap` | No aplica: PLY recibe la entrada completa con `lexer.input(texto)` |
| `yylineno` | `lexer.lineno`, que se incrementa en la regla de salto de línea |
| `yytext` | `t.value` |
| `return TOKEN;` / acción vacía | `return t` / `return None` (comentarios, espacios) |
| Regla `.` de error al final | `t_error`, que reporta el error y llama a `lexer.skip(1)` |

### 5.3 API para la siguiente fase (analizador sintáctico)

```python
from spl.ensamblador import EnsambladorLexer

lexer = EnsambladorLexer(al_error=print)   # al_error es opcional
lexer.input(texto)
for tok in lexer:                          # o lexer.token() hasta que devuelva None
    tok.type, tok.value, tok.lineno, tok.columna

tokens, errores = lexer.tokenizar(texto)   # todo de una vez; errores: list[ErrorLexico]
```

`EnsambladorLexer.tokens` es la tupla de categorías que espera `ply.yacc`, de modo que el parser puede importarla directamente. `lexer.comentarios` cuenta los comentarios ignorados.

### 5.4 Pruebas

```bash
python -m pytest tests/test_spl/test_lexer_ensamblador.py -v
```

Las pruebas cubren lo siguiente:
- Cada mnemónico, registro y directiva.
- La insensibilidad a mayúsculas.
- `ADDR` y otros prefijos de palabras reservadas.
- Los literales válidos, los mal formados y los límites de 64 bits.
- El `-` como signo y como resta.
- El conteo de líneas y columnas con finales de línea `\r\n`.
- La recuperación después de errores.
- La CLI con archivo, con stdin y con un archivo inexistente.

También se tokenizan los 11 programas `.s` oficiales del repositorio, con 0 errores.

## 6. Manual de usuario

### 6.1 Requisitos e instalación

- Python 3.10 o superior.
- PLY 3.11, que ya está en `requirements.txt`:

```bash
pip install -r requirements.txt
```

No hay que compilar nada: el lexer se construye al importarse. Funciona igual en Windows y en Linux.

### 6.2 Ejecución

Desde la raíz del repositorio:

```bash
# Analizar un archivo
python -m spl.ensamblador spl/ensamblador/ejemplos/prueba.asm

# Leer desde la entrada estándar
python -m spl.ensamblador < programa.asm
echo "loop: JMP loop" | python -m spl.ensamblador

# Guardar la salida
python -m spl.ensamblador programa.asm > tokens.txt
```

Código de salida: `0` si no hubo errores léxicos, `1` si hubo alguno y `2` si no se pudo leer el archivo.

### 6.3 Formato de la salida

Se imprime un token por línea, `<línea, CATEGORÍA, lexema>`. Los errores aparecen en el mismo flujo y en el punto donde ocurren:

```
<29, MNEMONICO, STORE>
<29, REGISTRO, R3>
<29, COMA, ,>
<29, CORCHETE_IZQ, [>
<29, REGISTRO, BP>
<29, MENOS, ->
<29, ENTERO_DEC, 8>
<29, CORCHETE_DER, ]>
...
<43, ETIQUETA_REF, MOV>
<43, REGISTRO, R1>
<43, COMA, ,>
ERROR LEXICO (linea 43, columna 21): caracter no valido: '@'
<43, REGISTRO, R2>
<44, MNEMONICO, ADDI>
ERROR LEXICO (linea 44, columna 17): registro inexistente (solo R0..R7): 'R8'
<44, COMA, ,>
<44, REGISTRO, R0>
<44, COMA, ,>
<44, ENTERO_DEC, 1>
ERROR LEXICO (linea 45, columna 9): directiva desconocida: '.float'
<45, FLOTANTE, 1.5>
<46, MNEMONICO, ADDI>
<46, REGISTRO, R1>
<46, COMA, ,>
<46, REGISTRO, R0>
<46, COMA, ,>
ERROR LEXICO (linea 46, columna 25): literal numerico mal formado: '0b102'
<47, MNEMONICO, ADDI>
<47, REGISTRO, R1>
<47, COMA, ,>
<47, REGISTRO, R0>
<47, COMA, ,>
ERROR LEXICO (linea 47, columna 25): literal fuera del rango de 64 bits: '0x1FFFFFFFFFFFFFFFF'
ERROR LEXICO (linea 48, columna 1): palabra reservada usada como etiqueta: 'LOAD'
<48, DOS_PUNTOS, :>
<48, MNEMONICO, NOT>
<48, REGISTRO, R1>
<49, MNEMONICO, JMP>
ERROR LEXICO (linea 49, columna 17): caracter no valido: '$'
<49, ETIQUETA_REF, fin>

=============== RESUMEN DEL ANALISIS LEXICO ===============
  MNEMONICO                   26
  REGISTRO                    36
  DIRECTIVA                    8
  ETIQUETA_DEF                 8
  ETIQUETA_REF                 5
  ENTERO_DEC                  11
  ENTERO_HEX                   6
  ENTERO_BIN                   2
  FLOTANTE                     4
  COMA                        33
  DOS_PUNTOS                   9
  CORCHETE_IZQ                 2
  CORCHETE_DER                 2
  PARENTESIS_IZQ               1
  PARENTESIS_DER               1
  INMEDIATO                    1
  MAS                          1
  MENOS                        1
  ------------------------------
  Total de tokens            157
  Comentarios ignorados       23
  Lineas analizadas           49
  Errores lexicos              7
```

La salida completa de `prueba.asm` está en `spl/ensamblador/ejemplos/prueba_salida_esperada.txt`. Una prueba automática verifica que la CLI la reproduzca exactamente.

> `MOV` aparece como `ETIQUETA_REF` y no como error. Léxicamente es un identificador válido, y es el analizador sintáctico el que debe rechazar un identificador en la posición de un mnemónico.

### 6.4 Vocabulario del ensamblador de Enigma-64

Una línea de programa tiene la forma

```
[etiqueta:]  [MNEMONICO operando, operando, ...  |  .directiva valor, ...]  [; comentario]
```

- **Mnemónicos (41):**
  - Control: `HLT`.
  - Aritmética: `ADD SUB MUL DIV ADDI SUBI INC DEC`.
  - Lógica y corrimientos: `AND OR XOR NOT SHL SHR ASR CMP`.
  - Memoria: `LOAD STORE LDB STB`.
  - Saltos: `JMP JZ JNZ JC JNC JN JP JV JNV JMPR`.
  - Subrutinas y pila: `CALL CALLR RET PUSH POP ENTER LEAVE`.
  - Interrupciones: `EI DI IRET`.
- **Registros:** `R0`–`R7`, `PC`, `SR`. `R0` vale siempre 0, y `RV`, `SP` y `BP` son alias de `R5`, `R6` y `R7`.
- **Directivas:**
  - `.data` y `.text` seleccionan la sección.
  - `.org dirección` fija la dirección de ensamblado.
  - `.word` reserva palabras de 64 bits (enteros o flotantes IEEE 754).
  - `.byte` reserva bytes.
- **Operandos:**
  - Registro: `R1`.
  - Inmediato: `5`, `#5`, `0x1F`, `0b101`, `-3`, `2.5e-3`.
  - Etiqueta: `loop`.
  - Memoria: `[Rb + desp]`, `[Rb - desp]`, `[Rb]` o `(Rb)`.
- **Etiquetas:** empiezan por una letra o `_` y siguen con letras, dígitos o `_`. No pueden ser un mnemónico ni un registro.
- **Comentarios:** desde `;` hasta el fin de línea.
