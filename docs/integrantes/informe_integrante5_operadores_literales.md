# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Taller # 01:** Análisis Léxico LEX — Sistema de Procesamiento del Lenguaje (SPL) para Enigma-64  
**Documento Técnico — Módulo: Compilador — Operadores & Literales**  
**Autor:** Maicol Sebastian Olarte Ramirez (Integrante 5)

---

## 1. Alcance y Responsabilidad Técnica

Especificación de las expresiones regulares del compilador de alto nivel de Enigma-64 para:

1. **Operadores aritméticos** `+  -  *  /  %`.
2. **Operadores lógicos** `&&  ||  !`.
3. **Operadores relacionales** `==  !=  <  <=  >  >=`.
4. **Literales enteros** en base 10 y base 16 (`0x...`), acotados a la palabra de 64 bits.
5. **Literales flotantes** en punto fijo (`3.14`, `.5`, `5.`) y notación científica (`1e10`, `2.5E-3`), acotados al rango de IEEE 754 binary64.
6. **Cadenas de texto** con secuencias de escape (`\n`, `\t`, `\r`, `\0`, `\\`, `\"`, `\'`).

El trabajo se integra sobre el analizador del Integrante 4 (`spl/compilador/lexer.py`, construido con `ply.lex`, la misma herramienta usada por el resto del equipo) y entrega los lexemas a las tablas del Integrante 6 (`install_num`, `install_string`).

### Archivos entregados

| Archivo | Rol |
| :--- | :--- |
| `spl/compilador/lexer.py` | Definiciones regulares, reglas de operadores y literales, subcódigos y reglas de error. |
| `spl/compilador/__init__.py` | Exporta los diccionarios de operadores, subcódigos y límites de representación. |
| `spl/compilador/ejemplos/escenario4_operadores_literales.spl` | Programa válido que usa todos los operadores y formatos de literal (0 errores). |
| `spl/compilador/ejemplos/escenario5_errores_literales.spl` | Programa con 9 errores léxicos de literales/operadores y recuperación. |
| `tests/test_spl/test_lexer_operadores_literales.py` | 104 pruebas `pytest`. |
| `docs/integrantes/informe_integrante5_operadores_literales.md` | Este documento. |

---

## 2. Especificación en notación FLEX

Las reglas se escriben a continuación en la notación de FLEX; en el código cada definición es una constante `PATRON_*` de `lexer.py` y cada regla un método `t_*` de `CompiladorLexer`.

### 2.1. Definiciones regulares

```lex
DIGITO      [0-9]
HEX         [0-9a-fA-F]
LETRA       [a-zA-Z_]
EXPONENTE   [eE][+-]?{DIGITO}+
MANTISA     {DIGITO}+"."{DIGITO}*|"."{DIGITO}+
ESCAPE      \\[ntr0\\\"']
```

`FIN_NUM` (`(?![\w.])` en el código) exige que un literal numérico no vaya seguido de letra, dígito o punto. FLEX no tiene lookahead negativo: el mismo efecto se logra con la regla de error `{DIGITO}[A-Za-z0-9_.]*`, que por *maximal munch* gana a cualquier literal válido más corto.

### 2.2. Reglas

```lex
%%
"=="                         { return IGUAL;        /* RELOP, sub 1 */ }
"!="                         { return DISTINTO;     /* RELOP, sub 2 */ }
"<="                         { return MENOR_IGUAL;  /* RELOP, sub 4 */ }
">="                         { return MAYOR_IGUAL;  /* RELOP, sub 6 */ }
"<"                          { return MENOR;        /* RELOP, sub 3 */ }
">"                          { return MAYOR;        /* RELOP, sub 5 */ }
"&&"                         { return AND_LOGICO;   /* LOGOP, sub 1 */ }
"||"                         { return OR_LOGICO;    /* LOGOP, sub 2 */ }
"!"                          { return NOT_LOGICO;   /* LOGOP, sub 3 */ }
"+"                          { return MAS;          /* ARITH, sub 1 */ }
"-"                          { return MENOS;        /* ARITH, sub 2 */ }
"*"                          { return POR;          /* ARITH, sub 3 */ }
"/"                          { return DIV;          /* ARITH, sub 4 */ }
"%"                          { return MOD;          /* ARITH, sub 5 */ }
"&"|"|"                      { error("operador logico incompleto"); }

0[xX]{HEX}+                  { if (> 0xFFFFFFFFFFFFFFFF) error(...); else InstallNum(); return ENTERO_HEX; }
{DIGITO}+                    { if (> INT64_MAX) error(...);          else InstallNum(); return ENTERO_DEC; }
{MANTISA}({EXPONENTE})?      { /* desborde a inf o a 0 -> error */      InstallNum(); return FLOTANTE; }
{DIGITO}+{EXPONENTE}         { InstallNum(); return FLOTANTE; }
({MANTISA}|{DIGITO}+)[eE][+-] { error("exponente sin digitos"); }
({DIGITO}|"."{DIGITO})[A-Za-z0-9_.]*  { error("literal numerico mal formado"); }

\"([^"\\\n\r]|{ESCAPE})*\"   { InstallString(); return STRING; }
\"([^"\\\n\r]|\\.)*\"        { error("secuencia de escape no valida"); }
\"([^"\\\n\r]|\\.)*\\?       { error("cadena sin cerrar"); }
'([^'\\\n\r]|{ESCAPE})'      { return CHAR_LITERAL; }
'([^'\\\n\r]|\\.)*'?         { error("literal de caracter mal formado"); }
%%
```

### 2.3. Orden de las reglas en PLY

FLEX resuelve conflictos por coincidencia más larga y después por orden de aparición. PLY prueba primero las reglas definidas como función, en el orden en que aparecen en la clase, y después las cadenas ordenadas de la expresión más larga a la más corta. El orden elegido en `CompiladorLexer` es:

1. Comentarios y saltos de línea, para que `//` y `/*` no se lean como `DIV`.
2. Cadena válida → cadena con escape inválido → cadena sin cerrar. Cada patrón acepta un lenguaje que contiene al anterior, así que una cadena solo llega a las reglas de error si la regla aceptora falló.
3. Carácter válido → carácter mal formado.
4. `ENTERO_HEX`, `ENTERO_BIN`, `FLOTANTE`, `ENTERO_DEC` (todos con `FIN_NUM`), luego `EXPONENTE_INCOMPLETO` y `NUMERO_MAL`.
5. `ID` / palabras reservadas.
6. `&` o `|` aislados (`&(?!&)|\|(?!\|)`); el lookahead deja pasar `&&` y `||` a sus reglas de cadena.
7. Operadores como cadenas (`t_IGUAL = r"=="`, ...). Como PLY los ordena por longitud, `==`, `<=`, `>=`, `!=`, `&&`, `||` y `->` se prueban antes que `=`, `<`, `>`, `!` y `-`: `a<=b` produce `MENOR_IGUAL` y no `MENOR ASIGNAR`.

---

## 3. Códigos de token

La categoría (`categoria_codigo`) es la de la tabla maestra del Integrante 4. Integrante 5 añade el **subcódigo** (`subcodigo`), que distingue el operador concreto dentro de su categoría, como el atributo de `RELOP` en el ejemplo clásico de FLEX.

| Categoría | Código | Token | Lexema | Subcódigo |
| :--- | :---: | :--- | :---: | :---: |
| RELOP | 200 | `IGUAL` | `==` | 1 |
| | | `DISTINTO` | `!=` | 2 |
| | | `MENOR` | `<` | 3 |
| | | `MENOR_IGUAL` | `<=` | 4 |
| | | `MAYOR` | `>` | 5 |
| | | `MAYOR_IGUAL` | `>=` | 6 |
| ARITH | 210 | `MAS` | `+` | 1 |
| | | `MENOS` | `-` | 2 |
| | | `POR` | `*` | 3 |
| | | `DIV` | `/` | 4 |
| | | `MOD` | `%` | 5 |
| LOGOP | 220 | `AND_LOGICO` | `&&` | 1 |
| | | `OR_LOGICO` | `\|\|` | 2 |
| | | `NOT_LOGICO` | `!` | 3 |
| NUMBER | 160 | `ENTERO_DEC` | `42` | 1 |
| | | `ENTERO_HEX` | `0xFF` | 2 |
| | | `ENTERO_BIN` | `0b101` | 3 |
| | | `FLOTANTE` (punto fijo) | `3.14`, `.5`, `5.` | 4 |
| | | `FLOTANTE` (científico) | `6.02e23` | 5 |
| STRING | 170 | `STRING` | `"..."` | 1 |
| | | `CHAR_LITERAL` | `'a'` | 2 |

Los subcódigos numéricos coinciden con `TipoNumero` de `tablas.py` (`ENTERO_DECIMAL`, `ENTERO_HEX`, `ENTERO_BIN`, `REAL_DECIMAL`, `REAL_CIENTIFICO`). El literal binario `0b...` ya existía en el analizador base y se conserva; además se le aplica el límite de 64 bits.

---

## 4. Decisiones de diseño

- **El signo no forma parte del literal.** `-15` produce `MENOS ENTERO_DEC`. Si el lexer pegara el signo, `a-1` se leería como `ID ENTERO_DEC`. Por eso el máximo decimal es `INT64_MAX = 9223372036854775807`; un patrón de 64 bits arbitrario se escribe en hexadecimal (hasta `0xFFFFFFFFFFFFFFFF`, que la tabla reinterpreta en complemento a dos como `-1`).
- **Límites de Enigma-64 aplicados en la fase léxica.** Un entero que no cabe en la palabra o un real que se convierte en `inf` (`1e309`) o que se vuelve cero sin serlo (`1e-400`) se reporta como error y no entra en `tablaNum`. Los subnormales (`4.9e-324`) sí se aceptan porque son representables en binary64.
- **Punto fijo sin dígito a un lado.** `.5` y `5.` son válidos. No chocan con el acceso a campos (`p.x`), porque `.` seguido de letra sigue siendo `PUNTO`, ni con `v[2].y`, porque `]` separa el entero del punto.
- **Escapes validados.** Se admiten exactamente los escapes que resuelve `desescapar_cadena` (Integrante 6). Antes, cualquier `\x` se aceptaba y se convertía en silencio en `x`; ahora `"\q"` es un error que indica la secuencia culpable.
- **Recuperación ante cadenas sin cerrar.** La regla consume hasta el fin de la línea y emite un solo error. Sin ella, el `"` caía en `t_error` y el texto de la cadena se tokenizaba como identificadores, lo que producía una cascada de tokens falsos. La línea siguiente se analiza con normalidad y conserva su número.
- **`&` y `|` aislados.** El lenguaje no tiene operadores de bits a nivel fuente, así que se reportan con un mensaje que sugiere `&&` o `||` en vez del genérico «caracter no valido».
- **Compatibilidad.** Los conteos de error de los escenarios existentes (7 en `escenario3_errores_recuperacion.spl`, 5 en el escenario 3 del pipeline) no cambian.

---

## 5. Verificación

```bash
python -m pytest tests/test_spl/test_lexer_operadores_literales.py -v   # 104 pruebas
python -m pytest tests/test_spl -q                                       # toda la suite SPL
```

La suite cubre:

- cada operador con su categoría y subcódigo, *maximal munch* sin espacios (`a<=b>=c==d!=e&&f||!g`), `=` frente a `==`, `/` frente a comentarios y `-` frente a `->`;
- enteros decimales y hexadecimales hasta los límites exactos de 64 bits, uno por encima de cada límite y literales mal formados (`0xZZ1`, `12abc`, `0x`);
- flotantes en punto fijo y científicos, el patrón IEEE 754 (`10.5` → `4025000000000000`), desborde, subdesborde, exponentes incompletos y mal formados (`1.2.3`, `.5x`);
- cadenas con cada escape admitido y su texto limpio en `tablaString`, deduplicación, escapes inválidos, cadenas sin cerrar con recuperación y literales de carácter;
- los dos escenarios nuevos y la CLI (código de salida 0 y 1).

### Escenario 4 — `escenario4_operadores_literales.spl`

```bash
python -m spl.compilador spl/compilador/ejemplos/escenario4_operadores_literales.spl
```

0 errores léxicos, 182 tokens, los 14 operadores, 11 constantes en `tablaNum` y 2 cadenas en `tablaString`.

### Escenario 5 — `escenario5_errores_literales.spl`

```bash
python -m spl.compilador spl/compilador/ejemplos/escenario5_errores_literales.spl --sin-tablas
```

```
ERROR LEXICO (linea 9, columna 20): literal entero excede el rango de 64 bits con signo: '9223372036854775808'
ERROR LEXICO (linea 10, columna 20): literal hexadecimal excede los 64 bits de Enigma-64: '0x10000000000000000'
ERROR LEXICO (linea 13, columna 18): literal flotante desborda el rango de IEEE 754 binary64: '1e309'
ERROR LEXICO (linea 14, columna 20): literal flotante subdesborda a cero en IEEE 754 binary64: '1e-400'
ERROR LEXICO (linea 17, columna 19): exponente sin digitos en literal flotante: '2.5e+'
ERROR LEXICO (linea 20, columna 12): secuencia de escape no valida '\q' en cadena: '"Escape invalido: \q"'
ERROR LEXICO (linea 23, columna 30): operador logico incompleto (se esperaba '&&' o '||'): '&'
ERROR LEXICO (linea 23, columna 34): operador logico incompleto (se esperaba '&&' o '||'): '|'
ERROR LEXICO (linea 26, columna 12): cadena de texto sin cerrar antes del fin de linea: '"Sin comillas de cierre);'
```

Tras los 9 errores, el analizador sigue reconociendo la función `fin_de_literales` y la CLI termina con código 1.
