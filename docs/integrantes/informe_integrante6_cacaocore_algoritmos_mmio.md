# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Tarea 27:** Traductor de ensamblador CacaoCore-64 → Enigma-64 (LEX / `ply.lex`)  
**Documento Técnico — Programación en Alto Nivel en CacaoCore_64, Compilación Base y Soporte MMIO**  

---

## 1. Alcance y Objetivos Técnicos

El presente documento formaliza el análisis, diseño, implementación y verificación de los componentes de programación en alto nivel, compilación base y soporte de periféricos para la **Tarea 27**:

1. **Programación en Alto Nivel en CacaoCore_64 (`CacaoScript`):**
   - Escritura de tres (3) algoritmos clásicos bajo la sintaxis y el sistema de tipos del compilador oficial de CacaoCore-64:
     - **Algoritmo 1 (Obligatorio):** Máximo Común Divisor (Euclides) por restas sucesivas ($MCD(48, 18) = 6$).
     - **Algoritmo 2:** Cálculo del Factorial de $N$ ($5! = 120$).
     - **Algoritmo 3:** Generación secuencial de la Sucesión de Fibonacci en memoria RAM ($[0, 1, 1, 2, 3, 5, 8]$).
2. **Compilación Base y Extracción `.asm`:**
   - Automatización y ejecución del compilador oficial de CacaoCore-64 (`Compiler.compile_full`), obteniendo los 3 archivos `.asm` puros que sirven como entrada estándar e insumo reproducible para el traductor LEX y la suite de verificación automatizada.
3. **Soporte de Salida por MMIO (`0xFF001000` / `0xFF001010`):**
   - Resolución de la divergencia arquitectónica entre la interrupción de software `INTR 0` de CacaoCore-64 y el subsistema de Entrada/Salida Mapeada en Memoria (MMIO) de Enigma-64 (`BASE_PANTALLA = 0xFF001000`, `OFFSET_DATA = 0x10`).
   - Implementación de la rutina de conversión determinista de enteros de 64 bits a caracteres ASCII para su volcado en la terminal CRT emulada, garantizando simultáneamente la persistencia del resultado en la memoria RAM de usuario.
4. **Verificación Automatizada:**
   - Suite formal de pruebas en `pytest` cubriendo compilación, traducción LEX, ejecución en el emulador de Enigma-64 y emisión a periféricos.

### Componentes Entregados

| Archivo | Rol en el Sistema | Contenido Principal |
| :--- | :--- | :--- |
| `spl/traductor/cacaocore_src/euclides.cac` | Código fuente de alto nivel | Algoritmo de Euclides en CacaoScript con $A = 48, B = 18$ |
| `spl/traductor/cacaocore_src/factorial.cac` | Código fuente de alto nivel | Factorial en CacaoScript con $N = 5$ |
| `spl/traductor/cacaocore_src/fibonacci.cac` | Código fuente de alto nivel | Fibonacci en CacaoScript con arreglo de 7 términos |
| `tools/compilar_algoritmos_cacao.py` | Driver de compilación reproducible | Compila `.cac` a `.asm` invocando el compilador oficial de CacaoCore-64 |
| `spl/traductor/ejemplos/cacao_euclides.asm` | Ensamblador CacaoCore generado | 41 líneas de código ensamblador (secciones `.data` y `.text`) |
| `spl/traductor/ejemplos/cacao_factorial.asm` | Ensamblador CacaoCore generado | 28 líneas de código ensamblador (secciones `.data` y `.text`) |
| `spl/traductor/ejemplos/cacao_fibonacci.asm` | Ensamblador CacaoCore generado | 56 líneas de código ensamblador con direccionamiento indexado |
| `spl/traductor/mmio_soporte.py` | Módulo de soporte MMIO | Rutina de conversión entero $\rightarrow$ ASCII para puerto `0xFF001010` y runner con periféricos |
| `tests/test_spl/traductor/test_algoritmos_cacao.py` | Batería de pruebas automatizadas | 13 pruebas unitarias y E2E validando compilación, traducción, RAM y MMIO |
| `docs/integrantes/informe_integrante6_cacaocore_algoritmos_mmio.md` | Documento técnico formal | Informe técnico de ingeniería (el presente documento) |

---

## 2. Lenguaje de Alto Nivel de CacaoCore-64: CacaoScript

A partir del análisis directo del repositorio oficial de CacaoCore-64 (`src/compiler/` y `src/examples/high_level/`), se identificaron las características sintácticas y semánticas del lenguaje de alto nivel:

* **Declaración e Inmutabilidad:** Variables inmutables con `let id: tipo = valor` y reasignación explícita con `set id = expresion`.
* **Arreglos Estáticos:** Sintaxis `let arr: tipo[tam] = v0, v1, ..., vn` (separados por comas, sin corchetes en el inicializador). Indexación mediante `arr[expr]`.
* **Estructuras de Control:** 
  - Bucle condicional: `asLongAs condicion { cuerpo }`.
  - Bifurcación: `if condicion { cuerpo } otherwise { cuerpo }`.
* **Emisión de Resultados:** La sentencia `show expr` imprime el valor de una variable o expresión. En el generador de código de CacaoCore-64 (`generador_codigo.py`), esto emite la secuencia de interrupción por software:
  ```assembly
  MOVH R10, 0
  LEA R11, [variable]
  MOVW R12, 1
  INTR 0
  ```

---

## 3. Especificación de los 3 Algoritmos Clásicos

Los tres algoritmos fueron diseñados para satisfacer de forma estricta los valores de prueba oficiales establecidos en la **Tarea 10**:

### 3.1 Algoritmo 1: Máximo Común Divisor (Euclides)
* **Archivo:** `spl/traductor/cacaocore_src/euclides.cac`
* **Entradas:** $a = 48$, $b = 18$.
* **Salida esperada:** $MCD(48, 18) = 6$.
* **Código Fuente CacaoScript:**
  ```cacaoscript
  let a: int = 48
  let b: int = 18

  asLongAs a != b {
      if a > b {
          set a = a - b
      }
      otherwise {
          set b = b - a
      }
  }

  show a
  ```
* **Ensamblador CacaoCore-64 generado (`cacao_euclides.asm`):**
  Consta de directivas `.data` para reservar `a: 48` y `b: 18`, y sección `.text` con bucle `LWHILE_START3`, comparaciones `CMP R0, [b]`, salto condicional `JNE LTRUE0`, y restas `SUB R3, [b]`.

### 3.2 Algoritmo 2: Cálculo del Factorial ($N!$)
* **Archivo:** `spl/traductor/cacaocore_src/factorial.cac`
* **Entradas:** $n = 5$, acumulador `fact = 1`.
* **Salida esperada:** $5! = 120$.
* **Código Fuente CacaoScript:**
  ```cacaoscript
  let n: int = 5
  let fact: int = 1

  asLongAs n > 1 {
      set fact = fact * n
      set n = n - 1
  }

  show fact
  ```
* **Ensamblador CacaoCore-64 generado (`cacao_factorial.asm`):**
  Estructura limpia de 28 líneas que realiza multiplicaciones sucesivas con `MUL R2, [n]` y decrementa con `SUB R2, 1`.

### 3.3 Algoritmo 3: Sucesión de Fibonacci en Memoria
* **Archivo:** `spl/traductor/cacaocore_src/fibonacci.cac`
* **Entradas:** Arreglo estático de 7 posiciones inicializado en `[0, 1, 0, 0, 0, 0, 0]`.
* **Salida esperada:** Arreglo en memoria con $[0, 1, 1, 2, 3, 5, 8]$ y variable `res = 8`.
* **Código Fuente CacaoScript:**
  ```cacaoscript
  let fib: int[7] = 0, 1, 0, 0, 0, 0, 0
  let i: int = 2

  asLongAs i < 7 {
      set fib[i] = fib[i - 1] + fib[i - 2]
      set i = i + 1
  }

  let res: int = fib[6]
  show res
  ```
* **Ensamblador CacaoCore-64 generado (`cacao_fibonacci.asm`):**
  El compilador descompone el acceso indexado en escalamiento de palabra (`MUL R3, 8`), cálculo de dirección efectiva (`LEA R4, [fib]`, `ADD R3, R4`) y acceso indirecto por registro (`MOVD R4, [R3]`).

---

## 4. Divergencia Arquitectónica y Soporte MMIO (`0xFF001000`)

### 4.1 Problema de Compatibilidad
En CacaoCore-64, la salida estándar por consola se modela como un servicio del sistema operativo invocado por la instrucción de software `INTR 0`.

Por el contrario, en **Enigma-64** (conforme al diseño de las Tareas 9 y 10 implementado en `enigma64/perifericos.py`):
* No existen interrupciones de software dedicadas a consola de texto.
* La comunicación con periféricos se realiza mediante **Entrada/Salida Mapeada en Memoria (MMIO)** en el rango `0xFF000000 - 0xFFFFFFFF` ($A[31:24] == \text{0xFF}$).
* El **Controlador de Pantalla** se ubica en la base `0xFF001000`, y su registro de emisión de datos `DATA` está en el desplazamiento `+0x10` (`0xFF001010`).

### 4.2 Solución Implementada (`spl/traductor/mmio_soporte.py`)
Para garantizar que los programas compilados que imprimen resultados puedan observarse en la terminal emulada de Enigma-64 sin alterar los algoritmos originales:

1. **Carga Segura de Dirección MMIO de 32/64 bits:**
   Dado que Enigma-64 utiliza inmediatos de 16 bits con extensión de signo en `ADDI`, la dirección `0xFF001010` no puede cargarse con un único `ADDI`. Se sintetiza mediante la secuencia determinista provista por `cargar_constante`:
   ```assembly
   ADDI R5, R0, 1        ; R5 = 0x0001
   SHL R5, R5, 16        ; R5 = 0x00010000
   ADDI R5, R5, -256     ; R5 = 0x0000FF00
   SHL R5, R5, 16        ; R5 = 0xFF000000
   ADDI R5, R5, 4112     ; R5 = 0xFF001010 (BASE_PANTALLA + OFFSET_DATA)
   ```

2. **Algoritmo de Conversión Entero $\rightarrow$ ASCII en Ensamblador:**
   Para visualizar valores multidígito como `120` en la terminal CRT:
   - Se toma el valor numérico en un registro (ej. `R1`).
   - Se divide sucesivamente por 10 (`DIV R4, R1, R2`), extrayendo el residuo ($R_3 = R_1 - (R_4 \times 10)$).
   - Se convierte cada residuo a su código ASCII (`ADDI R3, R3, 48`) y se empuja a la pila (`PUSH R3`).
   - Se extraen los dígitos en orden correcto (`POP R4`) y se escriben uno a uno en `[R5 + 0]` (`0xFF001010`).
   - Se emite un carácter de salto de línea (`\n`, ASCII 10) al finalizar.

3. **Conexión en la CPU de Enigma-64:**
   Se conectó el bus MMIO en `enigma64/cpu.py`: cuando la CPU accede a una dirección con $A[31:24] == \text{0xFF}$, si el módulo `perifericos` está conectado, redirige la lectura/escritura al controlador físico correspondiente (`Perifericos.escribir` / `leer`) en lugar de arrojar `MemoryFault`. Si no hay periféricos conectados, mantiene el comportamiento previo arrojando `MemoryFault("MMIO no conectado")`.

4. **Persistencia Dual:**
   El resultado permanece almacenado tanto en su celda natural de memoria RAM (área de datos `0x00201000+` requerida para contraste automatizado) como en el buffer de texto de la pantalla MMIO.

---

## 5. Resultados de Verificación y Contraste

Se ejecutó la suite completa de pruebas unitarias y de integración (`tests/test_spl/traductor/test_algoritmos_cacao.py`), obteniendo un **100% de éxito en 13 pruebas**:

| Prueba | Entrada | Salida Esperada (Tarea 10) | Salida en RAM | Salida Terminal CRT (MMIO) | Estado |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Euclides** | $a=48, b=18$ | $MCD = 6$ | `RAM[0x00201000] = 6` | `"6\n"` en `0xFF001010` | **PASS** |
| **Factorial** | $n=5$ | $5! = 120$ | `RAM[0x00201008] = 120` | `"120\n"` en `0xFF001010` | **PASS** |
| **Fibonacci** | 7 términos | $[0, 1, 1, 2, 3, 5, 8]$ | `RAM[0x00201000..0x00201030]` | `"8\n"` en `0xFF001010` | **PASS** |

La suite del paquete traductor pasó en su totalidad (**322 pruebas exitosas**), y la suite global del repositorio se mantiene intacta (**1144 pruebas exitosas, 1 skipped**).

---

## 6. Instrucciones de Reproducción

### Compilación de Fuentes CacaoScript
```bash
python tools/compilar_algoritmos_cacao.py
```

### Ejecución de Pruebas Unitarias y E2E
```bash
python -m pytest tests/test_spl/traductor/test_algoritmos_cacao.py -v
```

### Ejecución de la Suite Completa del Traductor
```bash
python -m pytest tests/test_spl/traductor/
```
