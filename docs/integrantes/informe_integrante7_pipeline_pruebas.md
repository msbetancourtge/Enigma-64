# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Taller # 01:** Análisis Léxico LEX — Sistema de Procesamiento del Lenguaje (SPL) para Enigma-64  
**Documento Técnico — Módulo: Driver Principal, Pipeline & Batería de Pruebas de Extremo a Extremo**  
**Autor:** Deibyd Santiago Barragán Gaitán (Integrante 7)

---

## 1. Alcance y Responsabilidad Técnica

El presente documento técnico formaliza el diseño, implementación y validación experimental del **Driver Principal y Orquestador del Pipeline SPL** (`spl/pipeline.py` y `spl/__main__.py`), junto con el **`Makefile` general de compilación cruzada** y la **batería automatizada de 3 escenarios integrales de prueba** del Taller # 01:

1. **Construcción del Orquestador Principal (`OrquestadorSPL` en `spl/pipeline.py`):**
   - Integración secuencial y modular de las 4 herramientas del Sistema de Procesamiento del Lenguaje (SPL) de Enigma-64:
     $$\text{Preprocesador} \longrightarrow \text{Compilador (Lexer + Tablas)} \longrightarrow \text{Ensamblador (Lexer)} \longrightarrow \text{Enlazador-Cargador + CPU}$$
   - Estructuras de datos tipadas por etapa (`EtapaPreprocesadorResult`, `EtapaCompiladorResult`, `EtapaEnsambladorResult`, `EtapaEnlazadorCargadorResult` y `ResultadoPipelineSPL`).
2. **Interfaz de Línea de Comandos Unificada (`spl/__main__.py` — `python -m spl`):**
   - Ejecución de los 3 escenarios integrales (`--escenario 1|2|3|todos`).
   - Procesamiento de archivos personalizados (`--spl`, `--asm`, `--obj`) con soporte para directorios de cabeceras (`-I`) y macros por línea de comandos (`-D NOMBRE=VALOR`).
3. **Automatización con `Makefile` y Verificación del Módulo C (`Makefile` raíz y `verificar_modulo_c_tablas()`):**
   - Enlace con `spl/compilador/Makefile` para compilación cruzada en ANSI C11 (`tablas_simbolos.c` y `test_tablas.c`) cuando `gcc` está disponible, y verificación estructural automática de las fuentes C y Python.
4. **Batería de 3 Escenarios Integrales y Suite de Pruebas (`spl/ejemplos/` y `tests/test_spl/test_pipeline_integracion.py`):**
   - 3 escenarios integrales completos (`.spl` + `.asm` + enlace `.obj` y ejecución en `CPU` de Enigma-64).
   - 11 pruebas automatizadas en `pytest` que verifican cada etapa, los 3 escenarios, la CLI y los Makefiles.

### Archivos Entregados

| Archivo | Rol en el Sistema |
| :--- | :--- |
| `spl/pipeline.py` | Clase `OrquestadorSPL`, dataclasses de resultados por etapa y función `verificar_modulo_c_tablas()`. |
| `spl/__main__.py` | Punto de entrada CLI del orquestador (`python -m spl`). |
| `spl/__init__.py` | Exportación pública unificada del paquete `spl`. |
| `Makefile` | Automatización raíz (`all`, `pipeline`, `escenario1..3`, `test`, `test-spl`, `test-c`, `clean`). |
| `spl/ejemplos/escenario1_aritmetica_tda.spl` | Fuente SPL del Escenario 1 (`#include "enigma64.h"`, `#define`, `tda`, `struct`, matrices, `while`, `if-then-else`). |
| `spl/ejemplos/escenario1_modulo.asm` | Módulo ensamblador del Escenario 1 (suma $30 + 12 = 42$ en Enigma-64). |
| `spl/ejemplos/escenario2_punto_flotante_switch.spl` | Fuente SPL del Escenario 2 (macros con argumentos, `#ifdef`, punto flotante IEEE 754, `switch-case`, cadenas con `\"` y `\\`). |
| `spl/ejemplos/escenario2_fpu.asm` | Módulo ensamblador FPU del Escenario 2 (constantes IEEE 754 binary64 y subrutina `paso_newton`). |
| `spl/ejemplos/escenario3_recuperacion_errores.spl` | Fuente SPL del Escenario 3 (5 errores léxicos intencionales y recuperación). |
| `spl/ejemplos/escenario3_errores.asm` | Módulo ensamblador del Escenario 3 (4 errores léxicos intencionales y recuperación hasta `HLT`). |
| `tests/test_spl/test_pipeline_integracion.py` | Suite de 11 pruebas de integración del pipeline completo en `pytest`. |

---

## 2. Arquitectura del Pipeline SPL (Diagrama de Bloques y Flujo)

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                 CÓDIGO FUENTE DE ALTO NIVEL (.spl / .h)                 │
  └────────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  [ETAPA 1] PREPROCESADOR SPL (spl.preprocesador)                        │
  │  • Resolución recursiva de #include ("enigma64.h") y guarda #pragma once│
  │  • Expansión de macros constantes y parametrizadas (#define, #undef)    │
  │  • Compilación condicional (#ifdef, #ifndef, #else, #endif)             │
  │  • Supresión de comentarios de línea (//) y bloque (/* ... */)          │
  └────────────────────────────────────┬────────────────────────────────────┘
                                       │ Código SPL expandido
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  [ETAPA 2] ANALIZADOR LÉXICO DEL COMPILADOR & TABLAS (spl.compilador)   │
  │  • Tokenización de KW (100), TYPE (110), TDA (120), RELOP (200), etc.   │
  │  • InstallID()     -> tablaID (Cat. 150, deduplicación base 1)          │
  │  • InstallNum()    -> tablaNum (Cat. 160, enteros 64-bit / IEEE 754)    │
  │  • InstallString() -> tablaString (Cat. 170, des-escape \" y \\)        │
  └────────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  [ETAPA 3] ANALIZADOR LÉXICO DEL ENSAMBLADOR (spl.ensamblador)          │
  │  • Tokenización de los 41 mnemónicos del ISA de Enigma-64               │
  │  • Registros (R0–R7, PC, SR, RV, SP, BP) y directivas (.data, .text...) │
  │  • Definición y referencia de etiquetas y literales con signo           │
  └────────────────────────────────────┬────────────────────────────────────┘
                                       │ Módulos Objeto Reubicables (.obj)
                                       ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  [ETAPA 4] ENLAZADOR-CARGADOR & CPU ENIGMA-64 (enigma64.enlazador)      │
  │  • Análisis léxico/estructural de cabeceras, secciones y tablas .obj    │
  │  • Construcción de ESTAB y resolución de 5 tipos de marcas (ABS64,      │
  │    ABS32, REL16, HI16, LO16)                                            │
  │  • Carga en RAMMemory (0x00200000) vía CargadorEnigma y ejecución CPU   │
  └─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Documentación de los 3 Escenarios de Prueba Integrales

### 3.1. Escenario Integral 1: Flujo Nominal Completo (TDA, Matrices, Enlace `.obj` y Ejecución en CPU)
- **Archivos:** `spl/ejemplos/escenario1_aritmetica_tda.spl`, `spl/ejemplos/escenario1_modulo.asm`, `principal.obj` + `libmat.obj`.
- **Resultados obtenidos por etapa:**
  - **Etapa 1 (Preprocesador):** Incluye `enigma64.h`, registra **14 macros activas** (`TAM_PALABRA=64`, `VERDADERO=1`, `FALSO=0`, `META_SUMA=42`, `DIM_MATRIZ=3`, etc.) y expande `ENTERO`, `VERDADERO`, `FALSO` y `DIM_MATRIZ` sobre el código fuente.
  - **Etapa 2 (Compilador Lexer & Tablas):** Emite **160 tokens** en 27 categorías distintas con **0 errores léxicos**. Registra **13 identificadores únicos** en `tablaID` (`BloqueAritmetico`, `operando_a`, `_acumulador`, etc.) y **9 constantes numéricas** en `tablaNum` (incluyendo `1.0` $\to$ `0x3FF0000000000000` y `2.5` $\to$ `0x4004000000000000`).
  - **Etapa 3 (Ensamblador Lexer):** Reconoce **66 tokens** (`8 MNEMONICO`, `15 REGISTRO`, `5 DIRECTIVA`, `2 ETIQUETA_DEF`) con **0 errores léxicos**.
  - **Etapa 4 (Enlazador-Cargador & CPU):** Enlaza `principal.obj` y `libmat.obj` aplicando **6 marcas de reubicación** (`HI16`, `LO16`, `ABS32`, `REL16`, `ABS64`) en `0x00200000` (120 bytes), carga en `RAMMemory` y ejecuta **15 instrucciones** hasta `HLT`, obteniendo `R5 = 42`, `resultado = 42` y `copia = 42`.

### 3.2. Escenario Integral 2: Punto Flotante IEEE 754 (64-bit), Switch-Case, Escapes y Macros Parametrizadas
- **Archivos:** `spl/ejemplos/escenario2_punto_flotante_switch.spl` y `spl/ejemplos/escenario2_fpu.asm`.
- **Resultados obtenidos por etapa:**
  - **Etapa 1 (Preprocesador):** Evalúa el bloque condicional `#ifdef USAR_FPU`, define `MODO_EJECUCION = 1` y expande la macro con argumentos `ESCALAR_DOBLE(iter_1_)` $\to$ `((iter_1_) + (iter_1_))` (17 macros activas).
  - **Etapa 2 (Compilador Lexer & Tablas):** Emite **207 tokens** en 37 tipos distintos con **0 errores léxicos**:
    - `tablaID`: **15 identificadores únicos** (incluyendo identificadores con guion bajo como `_max_iter`, `_ruta_bitacora`, `iter_1_`, `_flags`).
    - `tablaNum`: **11 constantes numéricas**, verificando la conversión IEEE 754 Binary64 de `1.0e-9` (`0x3E112E0BE826D695`), `1.5E3` (`1500.0` $\to$ `0x4097700000000000`), `0xFF` (`255`) y `0b1010` (`10`).
    - `tablaString`: **2 entradas únicas** a partir de 3 literales en el código fuente, des-escapando `"C:\\Enigma64\\fpu_trace.log"` $\to$ `C:\Enigma64\fpu_trace.log` (índice 1) y deduplicando las dos apariciones de `"Estado FPU: \"CONVERGENCIA_OK\""` $\to$ `Estado FPU: "CONVERGENCIA_OK"` (índice 2).
  - **Etapa 3 (Ensamblador Lexer):** Reconoce **87 tokens** (`13 MNEMONICO`, `17 REGISTRO`, `6 DIRECTIVA`, `4 ETIQUETA_DEF`) incluyendo `ENTER`, `LEAVE`, `CALL`, `RET` y constantes flotantes con signo (`-2.5e-3`).

### 3.3. Escenario Integral 3: Tolerancia a Fallos y Recuperación ante Errores Léxicos Multietapa
- **Archivos:** `spl/ejemplos/escenario3_recuperacion_errores.spl` y `spl/ejemplos/escenario3_errores.asm`.
- **Resultados obtenidos por etapa:**
  - **Etapa 1 (Preprocesador):** Expande `#include "enigma64.h"` y `#define CODIGO_RECUPERACION 99` sin fallos.
  - **Etapa 2 (Compilador Lexer):** Detecta y reporta **5 errores léxicos** con línea y columna exactas (`'@'` en L14:C13, `'$'` en L15:C12, `'0b10201'` en L16:C19, `'0xFFG1'` en L17:C15 y `'45xyz'` en L18:C25), recuperándose inmediatamente tras cada error para tokenizar `function int verificar_recuperacion()` (54 tokens válidos y 9 identificadores en `tablaID`).
  - **Etapa 3 (Ensamblador Lexer):** Detecta y reporta **4 errores léxicos** (`'@'` en L9:C21, registro inexistente `'R8'` en L10:C17, directiva desconocida `'.float'` en L11:C9 y binario mal formado `'0b102'` en L12:C25), recuperándose para reconocer `STORE R1, [R0 + 64]` y `HLT`.

---

## 4. Manual de Uso del Orquestador y Makefile

```bash
# Ejecutar los 3 escenarios integrales del pipeline SPL
python -m spl

# Ejecutar un escenario puntual (1, 2 o 3) ocultando el volcado extenso de tablas
python -m spl --escenario 1 --sin-tablas

# Ejecutar el pipeline sobre archivos específicos
python -m spl --spl spl/ejemplos/escenario1_aritmetica_tda.spl --asm spl/ejemplos/escenario1_modulo.asm

# Verificar módulo C de Tablas de Símbolos y Makefiles
python -m spl --verificar-c

# Ejecutar la suite de pruebas de integración del pipeline (11 pruebas) y toda la suite SPL (260 pruebas)
python -m pytest tests/test_spl/test_pipeline_integracion.py -v
python -m pytest tests/test_spl tests/core/test_enlazador.py -q
```

