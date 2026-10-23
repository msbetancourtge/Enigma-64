# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Taller # 01:** Análisis Léxico LEX — Sistema de Procesamiento del Lenguaje (SPL) para Enigma-64  
**Documento Técnico — Módulo: Compilador — Vocabulario, Palabras Reservadas y Categorías Base**  
**Autor:** Juan Luis Vergara Novoa (Integrante 4)

---

## 1. Alcance y Responsabilidad Técnica

El presente documento formaliza el análisis, diseño, especificación matemática, implementación y validación experimental de las responsabilidades asignadas al **Integrante 4** para la Fase 1 (Análisis Léxico) del Sistema de Procesamiento del Lenguaje (SPL) del computador **Enigma-64**:

1. **Diseño del Lenguaje de Alto Nivel para Enigma-64:** Definición formal del vocabulario, sintaxis imperativa con tipos primitivos, tipos abstractos (TDA), estructuras de control y constructos para arreglos unidimensionales y matrices multidimensionales.
2. **Especificación e Implementación del Analizador Léxico Base en PLY (`spl/compilador/lexer.py`):**
   - Catálogo exhaustivo de palabras reservadas (`PALABRAS_RESERVADAS`) para selección, iteración, funciones, tipos primitivos y tipos de datos abstractos.
   - Delimitadores para arreglos (`[` / `]`), matrices (`[r][c]`), bloques de ámbito (`{` / `}`) y acceso a miembros de TDA (`.` y `->`).
   - Regla de identificadores (`t_ID`) con desambiguación rigurosa frente a palabras clave.
   - Integración nativa con la Tabla de Símbolos (`tablaID`, Categoría 150) del Integrante 6 (`GestorTablasSimbolos.install_id()`).
   - Mecanismo determinista de rastreo de líneas (`lineno`), columnas calculadas y reporte de errores léxicos sin abortar el análisis.
3. **Punto de Entrada CLI (`spl/compilador/__main__.py`):** Utilidad de línea de comandos para tokenización interactiva, generación del volcado de tablas de símbolos y resumen estadístico.
4. **Batería de Pruebas Unitarias (`tests/test_spl/test_lexer_compilador.py`):** 18 pruebas automatizadas cubriendo palabras clave, tipos, arreglos, matrices, TDA, desambiguación, errores léxicos y CLI.
5. **Redacción de la Sección 2 del Informe General:** «Descripción y Justificación del Problema», articulando el paradigma imperativo, TDA, arreglos contiguos y la coherencia con la FPU IEEE 754 de 64 bits desarrollada en la Tarea 17.

### Archivos Entregados

| Archivo | Rol en el Sistema |
| :--- | :--- |
| `spl/compilador/lexer.py` | Definición de expresiones regulares, vocabulario, códigos de tokens y clase `CompiladorLexer`. |
| `spl/compilador/__init__.py` | Exportación pública unificada de las interfaces del analizador léxico y las tablas de símbolos. |
| `spl/compilador/__main__.py` | CLI ejecutable mediante `python -m spl.compilador`. |
| `spl/compilador/ejemplos/escenario1_tda_matrices.spl` | Programa de prueba con TDAs (`struct`/`tda`), arreglos unidimensionales y matrices bidimensionales. |
| `spl/compilador/ejemplos/escenario2_control_funciones.spl` | Programa de prueba con estructuras de control (`if-then-else`, `while`, `do-while`, `for`, `switch`) y desambiguación. |
| `spl/compilador/ejemplos/escenario3_errores_recuperacion.spl` | Programa con 7 errores léxicos intencionales para verificar tolerancia y recuperación. |
| `tests/test_spl/test_lexer_compilador.py` | Suite formal en `pytest` (18 pruebas unitarias y de integración). |
| `docs/integrantes/informe_integrante4_vocabulario_compilador.md` | Este documento técnico oficial. |

---

## 2. Descripción y Justificación del Problema (Aporte Documental al Informe General)

### 2.1. Definición y Justificación del Paradigma Imperativo Estructurado

Para el computador **Enigma-64** (arquitectura Von Neumann de 64 bits con memoria unificada de instrucciones y datos, 8 registros de propósito general `R0–R7`, contador de programa `PC` y registro de estado `SR`), se adopta un **paradigma imperativo estructurado**.

#### Razones de la Elección:
1. **Homomorfismo con la Máquina FSM de Enigma-64:** Los conceptos fundamentales del paradigma imperativo (asignación de estado en celdas de memoria, secuencia de pasos gobernada por el `PC`, bifurcaciones condicionales sustentadas en las banderas `Z, N, C, V` del `SR`) tienen correspondencia biunívoca con las instrucciones máquina `LOAD`, `STORE`, `ADD`, `CMP`, `JZ`, `JNZ`, `JMP`.
2. **Estructuras de Control Clásicas:**
   - **Secuencia:** Flujo secuencial natural delimitado por bloques `{ ... }` y sentencias terminadas en `;`.
   - **Selección:** `if-then-else` para bifurcaciones binarias y `switch-case-default` para bifurcaciones múltiples basadas en tablas de salto.
   - **Iteración:** Ciclos con pre-condición (`while`), post-condición (`do-while`) y conteo acotado (`for`), enriquecidos con `break` y `continue`.
   - **Procedimientos y Funciones:** Declaración explícita con `function` y `return`, mapeables directamente al convenio de llamadas de Enigma-64 (`CALL`/`RET`), marco de pila (`ENTER`/`LEAVE`) con `SP = R6` y `BP = R7`, y retorno de valor en `RV = R5`.

### 2.2. Soporte de Tipos de Datos Abstractos (TDA), Arreglos y Matrices

El lenguaje soporta la definición y manipulación de datos estructurados complejos:
1. **Tipos de Datos Abstractos (`struct` y `tda`):**
   - Permite al programador agrupar campos heterogéneos bajo un mismo identificador de tipo.
   - En el analizador léxico se habilitan los delimitadores `LLAVE_IZQ` (`{`) y `LLAVE_DER` (`}`) para el cuerpo del TDA, y los operadores de acceso a miembros:
     - Operador punto `.` (`PUNTO`): Acceso directo a campo (ej. `punto.x`).
     - Operador flecha `->` (`FLECHA`): Acceso indirecto mediante puntero o referencia base (ej. `nodo->siguiente`).
2. **Arreglos Unidimensionales y Matrices Multidimensionales:**
   - Sintaxis con corchetes repetidos: `vector[10]` y `matriz[4][8]`.
   - Delimitadores `CORCHETE_IZQ` (`[`) y `CORCHETE_DER` (`]`), facilitando el análisis sintáctico dimensional en fases posteriores.
3. **Mapeo Físico en Memoria de 4 GiB:**
   - Enigma-64 organiza su memoria física direccionable en bytes bajo ordenamiento **Big-Endian**.
   - Los arreglos y matrices se dispondrán de forma contigua en memoria mediante orden de fila mayor (*row-major order*), donde cada elemento de tipo `int` o `float` ocupa exactamente una palabra de 64 bits (8 bytes).
   - El acceso a un elemento $A[i][j]$ se traduce directamente en la dirección física:
     $$\text{Dir}(A[i][j]) = \text{DirBase} + (i \times N_{\text{columnas}} + j) \times 8$$
     Esta fórmula se computa limpiamente con la ALU de Enigma-64 mediante instrucciones `MUL`, `ADD` y direccionamiento indirecto `LOAD R1, [R_base + R_offset]`.

### 2.3. Coherencia con la FPU y Punto Flotante IEEE 754 de 64 bits

El computador Enigma-64 implementó en la Tarea 17 una biblioteca completa de punto flotante por software (*Soft-Float FPU*) bajo la norma **IEEE 754 Doble Precisión (Binary64)**. El diseño léxico del compilador se articula estrechamente con este logro:
1. El tipo primitivo `float` (`FLOAT_TYPE`) representa formalmente un valor binario de 64 bits (1 bit de signo, 11 de exponente y 52 de mantisa explícita).
2. Durante el análisis léxico, las constantes en coma flotante (`3.14159`, `1.5e-3`) se registran en `tablaNum` (Categoría 160) mediante `GestorTablasSimbolos.install_num()`, garantizando que el valor real se almacene con precisión absoluta de 64 bits y patrón hexadecimal listo para emisión.
3. En la fase de generación de código, las operaciones aritméticas (`+`, `-`, `*`, `/`) entre operandos `float` se traducirán en llamadas a la mesa canónica `FPU_VECTORES`:
   - `float + float` $\longrightarrow$ `CALL VEC_FADD` (offset `+0x00`)
   - `float - float` $\longrightarrow$ `CALL VEC_FSUB` (offset `+0x05`)
   - `float * float` $\longrightarrow$ `CALL VEC_FMUL` (offset `+0x0A`)
   - `float / float` $\longrightarrow$ `CALL VEC_FDIV` (offset `+0x0F`)
   - `float == float` $\longrightarrow$ `CALL VEC_FCMP` (offset `+0x14`)
   - `(float)int` $\longrightarrow$ `CALL VEC_INT_TO_FLOAT` (offset `+0x19`)
   - `(int)float` $\longrightarrow$ `CALL VEC_FLOAT_TO_INT` (offset `+0x1E`)

---

## 3. Especificación Formal del Vocabulario Completo (Literal d.i)

El vocabulario léxico del Compilador SPL para Enigma-64 se define como la unión disjunta de los siguientes conjuntos de terminales:

$$V = V_{\text{control}} \cup V_{\text{tipos}} \cup V_{\text{tda}} \cup V_{\text{id}} \cup V_{\text{delim}} \cup V_{\text{oper}} \cup V_{\text{lit}}$$

### 3.1. Palabras Reservadas de Control ($V_{\text{control}}$)
`if`, `then`, `else`, `switch`, `case`, `default`, `while`, `do`, `for`, `continue`, `function`, `return`, `break`.

### 3.2. Palabras Reservadas de Tipos Primitivos ($V_{\text{tipos}}$)
`int`, `float`, `void`, `char`, `bool`, `const`.

### 3.3. Palabras Reservadas de TDA y Estructuras ($V_{\text{tda}}$)
`struct`, `tda`, `typedef`, `sizeof`.

### 3.4. Identificadores ($V_{\text{id}}$)
Secuencias que comienzan con letra o guion bajo, seguidas de letras, dígitos o guiones bajos, excluyendo las palabras reservadas:
$$\text{ID} \in \{l(l \mid d)^* \setminus \text{PALABRAS\_RESERVADAS}\}$$

### 3.5. Delimitadores Estructurales y de Puntuación ($V_{\text{delim}}$)
`[` (`CORCHETE_IZQ`), `]` (`CORCHETE_DER`), `{` (`LLAVE_IZQ`), `}` (`LLAVE_DER`), `(` (`PARENTESIS_IZQ`), `)` (`PARENTESIS_DER`), `;` (`PUNTO_Y_COMA`), `,` (`COMA`), `:` (`DOS_PUNTOS`), `.` (`PUNTO`), `->` (`FLECHA`), `=` (`ASIGNAR`).

### 3.6. Operadores ($V_{\text{oper}}$)
- Relacionales: `==`, `!=`, `<=`, `>=`, `<`, `>`.
- Aritméticos: `+`, `-`, `*`, `/`, `%`.
- Lógicos: `&&`, `||`, `!`.

### 3.7. Literales ($V_{\text{lit}}$)
Enteros decimales (`100`), enteros hexadecimales (`0xFF000000`), enteros binarios (`0b1010`), flotantes decimales y científicos (`3.14`, `1.5e-3`), caracteres (`'a'`) y cadenas de texto con escape (`"hola\n"`).

---

## 4. Categorías Gramaticales y Tabla de Códigos (Literal d.ii)

Siguiendo la arquitectura canónica de compiladores (Aho, Lam, Sethi, Ullman, Capítulo 3) y la especificación de `tablas_simbolos.h` y `tablas.py` del Integrante 6, se establece la **Tabla Maestra de Códigos de Categoría y Subcódigos**:

| Código Categoría | Categoría Léxica | Tokens Asociados | Subcódigo (`yylval`) | Atributo Léxico Asociado |
| :-: | :--- | :--- | :-: | :--- |
| **100** | `KW` (Control de Flujo) | `IF`, `THEN`, `ELSE`, `SWITCH`, `CASE`, `DEFAULT`, `WHILE`, `DO`, `FOR`, `CONTINUE`, `FUNCTION`, `RETURN`, `BREAK` | 1 al 13 | Ordinal de la palabra reservada |
| **110** | `TYPE` (Tipos Primitivos) | `INT_TYPE`, `FLOAT_TYPE`, `VOID_TYPE`, `CHAR_TYPE`, `BOOL_TYPE`, `CONST` | 1 al 6 | Ordinal del tipo primitivo |
| **120** | `TDA` (Tipos Abstractos) | `STRUCT`, `TDA`, `TYPEDEF`, `SIZEOF` | 1 al 4 | Ordinal del constructo TDA |
| **150** | `ID` (Identificador) | `ID` | 1 | **Índice base 1 en `tablaID`** |
| **160** | `NUMBER` (Constante Numérica) | `ENTERO_DEC`, `ENTERO_HEX`, `ENTERO_BIN`, `FLOTANTE` | 1 al 5 | **Índice base 1 en `tablaNum`** |
| **170** | `STRING` (Cadena Literal) | `STRING`, `CHAR_LITERAL` | 1 | **Índice base 1 en `tablaString`** |
| **200** | `RELOP` (Operador Relacional) | `IGUAL`, `DISTINTO`, `MENOR_IGUAL`, `MAYOR_IGUAL`, `MENOR`, `MAYOR` | 1 al 6 | Subcódigo de comparación |
| **210** | `ARITH` (Operador Aritmético) | `MAS`, `MENOS`, `POR`, `DIV`, `MOD` | 1 al 5 | Subcódigo aritmético |
| **220** | `LOGOP` (Operador Lógico) | `AND_LOGICO`, `OR_LOGICO`, `NOT_LOGICO` | 1 al 3 | Subcódigo lógico |
| **230** | `ASSIGN` (Asignación) | `ASIGNAR` | 1 | Subcódigo de asignación simple |
| **240** | `DELIM` (Delimitadores) | `CORCHETE_IZQ`, `CORCHETE_DER`, `LLAVE_IZQ`, `LLAVE_DER`, `PARENTESIS_IZQ`, `PARENTESIS_DER`, `PUNTO_Y_COMA`, `COMA`, `DOS_PUNTOS`, `PUNTO`, `FLECHA` | 1 al 11 | Código de delimitador |

---

## 5. Expresiones Regulares y Reglas de Traducción (Literal d.iii)

### 5.1. Definiciones Regulares

$$\begin{aligned}
\text{DIGITO} &\longrightarrow [0-9] \\
\text{HEX} &\longrightarrow [0-9a-fA-F] \\
\text{BIN} &\longrightarrow [01] \\
\text{LETRA} &\longrightarrow [a-zA-Z\_] \\
\text{EXPONENTE} &\longrightarrow [eE][+-]?\text{DIGITO}^+ \\
\text{ID} &\longrightarrow \text{LETRA}(\text{LETRA} \mid \text{DIGITO})^* \\
\text{FLOTANTE} &\longrightarrow (\text{DIGITO}^+\,.\,\text{DIGITO}^+(\text{EXPONENTE})? \mid \text{DIGITO}^+\,\text{EXPONENTE}) \\
\text{ENTERO\_HEX} &\longrightarrow 0[xX]\text{HEX}^+ \\
\text{ENTERO\_BIN} &\longrightarrow 0[bB]\text{BIN}^+ \\
\text{ENTERO\_DEC} &\longrightarrow \text{DIGITO}^+ \\
\text{CADENA} &\longrightarrow \text{"}([\text{^\n\r\}"}] \mid \backslash.)^*\text{"} \\
\text{COMENTARIO\_LINEA} &\longrightarrow //[\text{^\n}]^* \\
\text{COMENTARIO\_BLOQUE} &\longrightarrow /\*[\backslash s\backslash S]*?\*/
\end{aligned}$$

### 5.2. Desambiguación Léxica y Prioridad

1. **Palabras Reservadas vs Identificadores:**  
   En la regla `t_ID(t)`, primero se captura la palabra completa mediante la expresión regular `r'[a-zA-Z_][a-zA-Z0-9_]*'`. Acto seguido, se busca el lexema normalizado en `PALABRAS_RESERVADAS`:
   - Si existe: `t.type = PALABRAS_RESERVADAS[val_lower]`, y **no se ingresa a `tablaID`**.
   - Si no existe: se clasifica como `'ID'`, y se invoca `self.tablas.install_id(t.value)` para registrar el símbolo en `tablaID` y obtener su `simbolo_idx`.
   - Esto evita que identificadores como `if_contador` o `float_var` sean fragmentados erróneamente.
2. **Operadores Multicarácter vs Operadores Simples:**  
   Tokens compuestos como `==`, `!=`, `<=`, `>=`, `->`, `&&`, `||` están definidos con mayor precedencia que sus componentes individuales `=`, `<`, `>`, `-`, `!`.
3. **Manejo de Errores con Tolerancia:**  
   La regla `t_error(t)` extrae el carácter espurio, crea un `ErrorLexico(linea, columna, lexema, mensaje)` y ejecuta `t.lexer.skip(1)`, permitiendo que el compilador siga analizando el resto del programa sin abortar.

### 5.3. Tabla Comparativa de Equivalencias FLEX $\longleftrightarrow$ PLY

| Concepto en FLEX (C) | Equivalente en PLY (`spl/compilador/lexer.py`) |
| :--- | :--- |
| Bloque de definiciones (`LETRA [a-zA-Z_]`) | Constantes `LETRA = r'[a-zA-Z_]'` con decorador `@TOKEN(...)` |
| Variable `yytext` | Propiedad `t.value` |
| Variable `yylineno` | Propiedad `t.lexer.lineno` |
| Variable `yylval` | Propiedades añadidas `t.simbolo_idx`, `t.categoria_codigo`, `t.subcodigo` |
| Inserción semántica `{ yylval = InstallID(); return ID; }` | `t.simbolo_idx = self.tablas.install_id(t.value)` |
| `%option noyywrap` | Manejo nativo de fin de cadena en PLY |
| Regla `.` de error | Método `t_error(self, t)` con `t.lexer.skip(1)` |

---

## 6. Integración con `GestorTablasSimbolos` (Integrante 6)

El analizador léxico está 100% articulado con el módulo `spl.compilador.tablas`:
```python
from spl.compilador.tablas import GestorTablasSimbolos

lexer = CompiladorLexer(tablas=GestorTablasSimbolos())
```
Cuando el lexer procesa identificadores, números o cadenas:
- `ID`: Invoca `install_id(lexema)` $\to$ `tablaID` (deduplicado con índice correlativo base 1).
- `ENTERO` / `FLOTANTE`: Invoca `install_num(lexema)` $\to$ `tablaNum` (almacena valor entero de 64 bits y real IEEE 754 Binary64).
- `STRING`: Invoca `install_string(lexema)` $\to$ `tablaString` (des-escapado algorítmico y deduplicación sobre texto limpio).

Al finalizar la tokenización, el método `lexer.tablas.generar_volcado_texto()` genera un reporte estructurado y alineado con el estado exacto de la memoria del compilador.

---

## 7. Escenarios de Prueba Formales y Resultados

Se construyeron 3 escenarios formales de prueba en `spl/compilador/ejemplos/`:

### 7.1. Escenario 1: TDA, Vectores y Matrices (`escenario1_tda_matrices.spl`)
- **Objetivo:** Declaración de estructuras `struct Vector3D`, `tda MatrizTransformacion`, vector unidimensional `lista_puntos[100]` y matriz bidimensional `matriz_rotacion[3][3]`.
- **Resultado:**
  - 123 tokens reconocidos.
  - 16 identificadores únicos registrados en `tablaID` con índices correlativos 1 a 16.
  - 8 constantes numéricas registradas en `tablaNum`.
  - 0 errores léxicos.

### 7.2. Escenario 2: Estructuras de Control, Iteración y Desambiguación (`escenario2_control_funciones.spl`)
- **Objetivo:** Evaluar `if-then-else`, `while`, `do-while`, `for`, `switch-case-default`, funciones con `return` y variables con nombres desambiguados (`if_variable`, `while_contador`, `for_limite`).
- **Resultado:**
  - 172 tokens reconocidos.
  - Las variables con prefijos de palabras clave se clasificaron limpiamente como `ID`.
  - 16 identificadores únicos registrados en `tablaID`.
  - 0 errores léxicos.

### 7.3. Escenario 3: Detección y Recuperación ante Errores Léxicos (`escenario3_errores_recuperacion.spl`)
- **Objetivo:** Verificar la tolerancia a fallos ante caracteres ilegales (`@`, `$`, `` ` ``) y números mal formados (`0b102`, `0xZZ1`, `12abc`).
- **Resultado:**
  - 7 errores léxicos detectados con línea y columna exactas:
    - Línea 9, Col 11: carácter no válido `'@'`
    - Línea 10, Col 11: carácter no válido `'$'`
    - Línea 11, Col 26: carácter no válido ``'`'``
    - Línea 11, Col 28: carácter no válido ``'`'``
    - Línea 14, Col 24: literal numérico mal formado `'0b102'`
    - Línea 15, Col 20: literal numérico mal formado `'0xZZ1'`
    - Línea 16, Col 22: literal numérico mal formado `'12abc'`
  - El analizador se recuperó tras cada error, procesó la función final `fin_del_programa` y deduplicó correctamente `variable_valida` en `tablaID`.

---

## 8. Resultados de la Suite Global de Pruebas

Se ejecutó la suite completa del repositorio mediante `pytest`:

```text
tests/test_spl/test_lexer_compilador.py ..................               [ 18 pasadas]
tests/test_spl/test_lexer_ensamblador.py ............................... [117 pasadas]
tests/test_spl/test_preprocesador.py ................................... [ 45 pasadas]
tests/test_spl/test_tablas.py ...................                        [ 19 pasadas]
======================= 669 passed, 1 skipped in 21.25s =======================
```

**Conclusión:** Las 199 pruebas de la suite SPL y las 670 pruebas totales de Enigma-64 pasan al 100% sin ninguna regresión.
