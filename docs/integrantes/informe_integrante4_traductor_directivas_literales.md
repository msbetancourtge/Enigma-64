# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Tarea 27:** Traductor de ensamblador CacaoCore-64 → Enigma-64 (LEX / `ply.lex`)  
**Documento Técnico — Directivas, Secciones, Literales y Enlace con CargadorEnigma**  
**Autor:** Juan Luis Vergara Novoa (Integrante 4 — Cargador, Directivas y Bits)

---

## 1. Alcance y Objetivos Técnicos

El presente documento formaliza el análisis, diseño, implementación y verificación de los componentes de procesamiento de directivas, secciones, literales numéricos/alfanuméricos y el enlace con el subsistema de carga de hardware (`CargadorEnigma`) para la **Tarea 27**:

1. **Reconocimiento Léxico de Directivas y Secciones (`ply.lex`):**
   - Análisis y extracción determinista de secciones de código y datos (`.data`, `.text`, `[DATA]`, `[CODE]`, `[MODULE]`), directivas de asignación y reserva (`.word`, `.quad`, `.byte`, `.ascii`, `.space`, `.align`), así como el filtrado de comentarios (`#` y `;`) y gestión de saltos de línea.
2. **Normalización Universal de Constantes y Literales:**
   - Transformación de cualquier representación sintáctica de CacaoCore-64 (enteros decimales con signo, hexadecimales con padding arbitrario, binarios, números flotantes IEEE 754 de doble precisión, caracteres ASCII y secuencias de escape) a patrones normalizados de **64 bits sin signo** (`0x0000000000000000` a `0xFFFFFFFFFFFFFFFF`), preservando la semántica de complemento a dos y codificación binaria de coma flotante.
3. **Reubicación de Memoria y Alineación Estricta a 8 Bytes:**
   - Mapeo de las variables estáticas desde el espacio plano de 1 MB de CacaoCore hacia el espacio paginado de usuario de Enigma-64 a partir de `0x00201000`.
   - Garantía de **alineación natural a múltiplos de 8 bytes** (`0x00201000 + 8·k`), previniendo excepciones `STATUS_MISALIGNED` y activaciones indeseadas de la bandera `M` en el registro de estado `SR`.
4. **Enlace Directo con `CargadorEnigma` y Ejecutables Estructurados (`.e64`):**
   - Construcción de objetos ejecutables `BinarioEnigma` con firma mágica `b'ENIG'`, tabla de símbolos de variables (`ESTAB`) y punto de entrada `0x00200000`.
   - Soporte dual de ejecución: precarga transparente de datos en memoria `RAMMemory` mediante el cargador o generación de prólogo con instrucciones `STORE`.
   - Invocación formal de `CargadorEnigma` (`cargar_binario`), garantizando la detención preventiva, vaciado del búfer de prebúsqueda (`prefetch.reset()`), sincronización de la FSM multiciclo y reanudación de la CPU.

### Componentes Entregados

| Archivo | Rol en el Sistema | Contenido Principal |
| :--- | :--- | :--- |
| `spl/traductor/directivas.py` | Núcleo del Integrante 4 | `LexerDirectivasCacao`, `ProcesadorDirectivasCacao`, `VariableDato`, `MapaSeccionDatos`, `normalizar_literal_cacao`, `precargar_datos_en_ram`, `construir_binario_enigma`, `exportar_ejecutable_e64`, `cargar_y_ejecutar_con_cargador` |
| `spl/traductor/traductor.py` | Integración no invasiva | Conexión del analizador de literales en `LexerPrograma` y `_valor_dato`; soporte CLI `--exportar-e64` y flag `--cargador` en `ejecutar_en_enigma` |
| `spl/traductor/__init__.py` | Exportaciones del paquete | Exposición pública en `__all__` de las clases y utilidades de directivas y enlace |
| `tests/test_spl/traductor/test_traductor_directivas.py` | Batería de pruebas formales | 19 pruebas unitarias y de integración validando directivas, literales, endianness, cargador y algoritmos clásicos |
| `docs/integrantes/informe_integrante4_traductor_directivas_literales.md` | Documento técnico formal | Informe de ingeniería y Capítulo 2 de la entrega colectiva (el presente informe) |

---

## 2. Descripción y Justificación del Problema (Capítulo 2 del Informe)

### 2.1 Contexto y Necesidad de Interoperabilidad

En el marco de la arquitectura de computadores y la ingeniería de software de sistemas, la interoperabilidad entre máquinas con arquitecturas de conjunto de instrucciones (*Instruction Set Architecture* - ISA) heterogéneas representa uno de los desafíos más significativos. Cuando dos plataformas computacionales han sido diseñadas bajo premisas divergentes de microarquitectura, un programa compilado para una de ellas resulta inejecutable en la otra debido a incompatibilidades fundamentales a nivel binario, organizativo y de representación de datos.

En esta práctica, se confrontan dos computadores académicos de 64 bits:
1. **CacaoCore-64 (`LP02---CacaoCore_64`):** Máquina de referencia, orientada a microinstrucciones basadas en un acumulador implícito (`R15`), con un espacio lineal de 1 MB de memoria y ordenamiento de bytes *Little-Endian*.
2. **Enigma-64 (`Enigma-64`):** Máquina de propósito general, construida en la Tarea 10, con microarquitectura Von Neumann multiciclo, ordenamiento estricto *Big-Endian*, espacio físico direccionable de 4 GiB paginado, banco de 10 registros arquitectónicos y una política estricta de protección de memoria por hardware.

El problema radica en permitir que programas de aplicación clásicos (tales como el algoritmo de Euclides para el Máximo Común Divisor, el Factorial y la Sucesión de Fibonacci), desarrollados en el lenguaje fuente de alto nivel de CacaoCore-64, se ejecuten de manera determinista, correcta y verificable sobre la infraestructura de hardware emulado de Enigma-64.

### 2.2 Diagnóstico de Divergencias Arquitectónicas Críticas

Un análisis comparativo riguroso de ambos repositorios revela cuatro choques arquitectónicos insoslayables:

```
+--------------------------+------------------------------+------------------------------+
| Dimensión                | CacaoCore-64                 | Enigma-64                    |
+--------------------------+------------------------------+------------------------------+
| 1. Endianness            | Little-Endian (LSB primero)  | Big-Endian (MSB primero)     |
| 2. Espacio de Memoria    | 1 MB plano (0x00000-0xFFFFF) | 4 GiB paginado (4096 B/pág)  |
| 3. Protección de Memoria | No segmentada / sin barreras | Frontera en 0x00200000       |
| 4. Banco de Registros    | 16 reg (R0-R15), ACM = R15   | 10 reg (R0-R7, PC, SR)       |
| 5. Comportamiento R0     | Propósito general escribible | Constante cero inmutable     |
| 6. Alineación de Datos   | Byte-addressable libre       | Palabras de 8 bytes alineadas|
| 7. Formato de Instrucción| 2 operandos (Rd, Rs)         | 3 operandos (Rd, Rs1, Rs2)   |
+--------------------------+------------------------------+------------------------------+
```

#### A. Choque de Endianness (Ordenamiento de Bytes)
CacaoCore-64 almacena datos numéricos multidigito en memoria según la convención *Little-Endian* (el byte menos significativo reside en la dirección inferior). Por el contrario, Enigma-64 adopta *Big-Endian* a nivel de arquitectura física, ALU y bus de datos (el byte más significativo reside en la dirección inferior). Por ejemplo, el entero de 64 bits $0x12345678$ se representa en memoria de la siguiente manera:
- En CacaoCore: `[0x78, 0x56, 0x34, 0x12, 0x00, 0x00, 0x00, 0x00]`
- En Enigma-64: `[0x00, 0x00, 0x00, 0x00, 0x12, 0x34, 0x56, 0x78]`

Si un archivo de datos se transfiriera byte a byte sin normalización léxica y reempaquetado, cualquier lectura de 64 bits mediante la instrucción `LOAD` en Enigma-64 interpretaría los valores permutados, corrompiendo inmediatamente las condiciones de parada y cálculos matemáticos.

#### B. Modelo de Memoria y Protección de Fronteras
CacaoCore dispone de apenas 1 MB de RAM (`0x00000` a `0xFFFFF`), ubicando datos estáticos en direcciones absolutas bajas (ej. `0x00000177` o `0x00040000`). En Enigma-64, la clase `CargadorEnigma` y el controlador `RAMMemory` implementan protección por hardware en modo usuario:
- **Zona Protegida de Sistema:** `0x00000000` – `0x001FFFFF` (reservada para vectores de interrupción en `0x00000000`, monitor en `0x00001000` y buffers de periféricos).
- **Lanzamiento de Excepción:** Cualquier intento de acceso o carga por debajo de `0x00200000` dispara instantáneamente `ViolacionProteccionMemoria`.
- **Zona de Pila:** A partir de `0xC0000000` hacia abajo (`SP` inicial = `0xEFFFFFFF`), prohibiendo solapamientos.

Por ende, el traductor no puede mantener las direcciones de CacaoCore; debe reubicar obligatoriamente el código en `0x00200000` y las variables de datos en `0x00201000`.

#### C. Inmutabilidad de R0 y Asignación de Registros
En CacaoCore, `R0` es un registro ordinario que los algoritmos emplean para almacenar variables intermedias (por ejemplo, en el Euclides oficial: `MOVD R0, [a]`). En Enigma-64, **`R0` está cableado físicamente a tierra (`0x0`)**: cualquier lectura produce cero y cualquier escritura se descarta silenciosamente. Asignar un cálculo a `R0` en Enigma-64 destruiría la lógica del programa. Esto obliga a una tabla de remapeo estricta hacia `R1`–`R4` y un mecanismo de derrame (*spill*) hacia memoria cuando se requieren más registros.

### 2.3 Justificación Técnica de la Traducción Léxica (Source-to-Source)

Frente a la incompatibilidad entre ambas máquinas, existen teóricamente tres enfoques de solución:

1. **Emulación Binaria por Software:** Implementar un intérprete que decodifique los opcodes binarios de CacaoCore instrucción por instrucción en tiempo de ejecución.
   - *Desventaja:* Sobrecarga computacional masiva (degradación de 20x a 50x en ciclos de reloj), complejidad innecesaria en la emulación de la microarquitectura ajena y nulo aprovechamiento de la ALU nativa de Enigma-64.
2. **Recompilación Cruzada desde Alto Nivel:** Modificar el backend del compilador de CacaoCore para generar código nativo de Enigma-64.
   - *Desventaja:* Viola el requisito del enunciado, el cual exige explícitamente tomar el código ensamblador emitido por CacaoCore como entrada del traductor.
3. **Traducción Léxica Fuente a Fuente (*Source-to-Source Assembly Transpilation*) con LEX [Seleccionado]:**
   - *Ventajas:*
     - **Elegancia y Desacoplamiento:** El metalenguaje LEX (`ply.lex`) permite modelar mediante autómatas finitos deterministas (DFA) el reconocimiento léxico de directivas, constantes, comentarios y mnemónicos, asociando acciones semánticas directas para emitir código Enigma-64 limpio.
     - **Eficiencia y Verificabilidad:** El ensamblador resultante es nativo, inspeccionable por humanos, ensamblable por el cargador de la Tarea 10 y ejecutable a velocidad de reloj emulado puro en la CPU de Enigma-64.
     - **Modularidad:** Permite separar ortogonalmente la traducción de memoria (Integrante 1), registros/ALU (Integrante 2), saltos/control (Integrante 3), directivas/datos/cargador (Integrante 4) y E/S (Integrante 6).

---

## 3. Diseño e Implementación del Subsistema de Directivas y Literales

### 3.1 Analizador Léxico PLY (`LexerDirectivasCacao`)

El módulo `spl/traductor/directivas.py` define la clase `LexerDirectivasCacao`, construida sobre `ply.lex`:

```python
class LexerDirectivasCacao:
    tokens = (
        "SECCION_DATA", "SECCION_TEXT", "SECCION_OTRA",
        "DIRECTIVA_DATO", "LITERAL_HEX", "LITERAL_BIN",
        "LITERAL_FLOAT", "LITERAL_DEC", "LITERAL_CHAR",
        "LITERAL_STR", "IDENTIFICADOR", "DOS_PUNTOS", "COMA",
    )
```

Las expresiones regulares reconocen:
- **Secciones:** `r"\.(?:data|DATA)\b|\[(?:DATA|data)\]"` para datos y `r"\.(?:text|TEXT)\b|\[(?:CODE|code)\]"` para código.
- **Directivas de Tamaño:** `r"\.(?:word|quad|dword|half|byte|ascii|space|align)\b"`.
- **Literales con Signo:** Hexadecimales (`[+-]?0[xX][0-9a-fA-F]+`), binarios (`[+-]?0[bB][01]+`), flotantes (`[+-]?\d+\.\d+(?:[eE][+-]?\d+)?`), enteros decimales (`[+-]?\d+`), caracteres simples o con escape (`'(?:\\.|[^'\\])+'`) y cadenas (`"(?:\\.|[^"\\])*"`).
- **Comentarios:** `r"[;#][^\n]*"` descartados transparentemente, actualizando el conteo de líneas (`lineno`) en cada salto `\n+`.

### 3.2 Normalización Universal a 64 Bits (`normalizar_literal_cacao`)

La función `normalizar_literal_cacao(texto: str) -> Tuple[int, str]` convierte cualquier constante a una palabra de 64 bits sin signo:
- **Enteros:** `int(t, base) & 0xFFFFFFFFFFFFFFFF`, preservando el complemento a dos en números negativos (por ejemplo, `-1` $\rightarrow$ `0xFFFFFFFFFFFFFFFF`).
- **Flotantes IEEE 754:** `struct.unpack(">Q", struct.pack(">d", float(t)))[0]`, transformando flotantes a su representación canónica Big-Endian de 64 bits.
- **Caracteres y Escapes:** Reconoce secuencias especiales (`\n` $\rightarrow 10$, `\t` $\rightarrow 9$, `\0` $\rightarrow 0$, `\\` $\rightarrow 92$).

### 3.3 Reubicación de Datos y Alineación Natural a 8 Bytes

La clase `ProcesadorDirectivasCacao` recorre el flujo de tokens de la sección `.data`, instancia objetos tipados `VariableDato` y construye un `MapaSeccionDatos`:
1. La primera variable se ubica en `base_datos` (`0x00201000`).
2. Cada variable incrementa la dirección física en $8 \times (1 + \text{longitud de elementos extra})$ bytes.
3. Se verifica formalmente que $\text{dirección} \pmod 8 = 0$, garantizando que las lecturas y escrituras de 64 bits nunca activen la bandera `M` de desalineación en el hardware emulado.

---

## 4. Arquitectura de Enlace con `CargadorEnigma` y Formato `.e64`

Una de las contribuciones centrales del Integrante 4 es conectar la salida del traductor con el subsistema de carga de la Tarea 10 (`enigma64.cargador`), superando la inicialización rudimentaria por instrucciones en el prólogo:

```
                              CADENA DE ENLACE INTEGRADA
                               
 Código Ensamblador CacaoCore (.asm)
                 │
                 ▼ [ProcesadorDirectivasCacao & TraductorCacaoEnigma]
                 │
        ┌────────┴──────────────────────────────┐
        ▼                                       ▼
  MapaSeccionDatos                      Código Enigma-64 (.asm)
  (Variables normalizadas)                      │
        │                                       ▼ [ensamblar()]
        │                               Cuerpo de Código (.text)
        │                                       │
        └───────────────────┬───────────────────┘
                            ▼ [construir_binario_enigma()]
                     BinarioEnigma
       (Cabecera b'ENIG', ESTAB símbolos, Entry=0x00200000)
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
 [exportar_ejecutable_e64()]     [CargadorEnigma.cargar_binario()]
            │                               │
    Archivo en disco (.e64)                 ▼
  (Compatible con GUI Noctua)        RAMMemory (0x00200000 / 0x00201000)
                                            │
                                            ▼ [cpu.ejecutar()]
                                    Ejecución CPU FSM
```

### 4.1 Precarga Directa en Memoria RAM (`precargar_datos_en_ram`)
La función `precargar_datos_en_ram(ram, mapa_datos, cargador)` escribe los bytes de las variables directamente en las celdas de memoria de `RAMMemory` en orden Big-Endian. Valida previamente que `base_datos >= 0x00200000`, lanzando `ViolacionProteccionMemoria` si se intenta invadir la zona reservada.

### 4.2 Construcción y Exportación de Ejecutables Estructurados (`.e64`)
- `construir_binario_enigma(...)`: Ensambla el código fuente traducido, incorpora la sección de datos y genera una tabla de símbolos con todas las variables (`a -> 0x00201000`, `b -> 0x00201008`).
- `exportar_ejecutable_e64(...)`: Serializa el binario con la cabecera estándar de 32 bytes (`b'ENIG'`, versión 1, flags absolutos, entry point `0x00200000`). Este archivo puede ser cargado directamente en la interfaz gráfica de Enigma-64 mediante el panel del Cargador.

### 4.3 Ejecución Asistida por el Cargador (`cargar_y_ejecutar_con_cargador`)
Esta función automatiza el ciclo completo:
1. Traduce las directivas e instrucciones.
2. Construye el hardware emulado (`RAMMemory`, `BancoRegistros`, `CPU`, `CargadorEnigma`).
3. Invoca `cargador.cargar_binario()`, configurando `PC = 0x00200000`, `SP = 0xEFFFFFFF`, reseteando el `PrefetchBuffer` y dejando la FSM en fase `FETCH`.
4. Ejecuta la CPU hasta `HLT`, permitiendo comprobar los resultados numéricos en memoria de forma determinista.

---

## 5. Verificación Experimental y Batería de Pruebas

La implementación cuenta con una suite integral de 19 pruebas automatizadas en `tests/test_spl/traductor/test_traductor_directivas.py`, cubriendo todas las capas del subsistema:

```bash
python -m pytest tests/test_spl/traductor/test_traductor_directivas.py
```
**Resultado:** `19 passed in 0.14s` (100% de éxito).

Adicionalmente, se ejecutó la suite completa de pruebas del traductor (`test_algoritmos_cacao.py`, `test_traductor_directivas.py`, `test_traductor_memoria.py`, `test_traductor_registros_alu.py`):
```bash
python -m pytest tests/test_spl/traductor/
```
**Resultado:** `338 passed, 3 skipped in 2.42s`.

Y la suite total del repositorio Enigma-64 (núcleo, FPU, UI, aislamiento AST y traductores):
```bash
python -m pytest
```
**Resultado consolidado:** `1173 passed, 4 skipped in 27.05s`.

### Validación E2E de los Tres Algoritmos Oficiales con CargadorEnigma

Mediante `cargar_y_ejecutar_con_cargador`, se validó la ejecución real en hardware emulado de los tres programas generados desde CacaoCore:

1. **Euclides (`cacao_euclides.asm`):**
   - Entradas en RAM: $a = 48$ (`0x00201000`), $b = 18$ (`0x00201008`).
   - Salida en RAM tras HLT: $\text{Mem}[a] = 6$ ($MCD(48, 18) = 6$).
   - Estado: `CPU.detenido = True`, `CPU.fase = FETCH`.
2. **Factorial (`cacao_factorial.asm`):**
   - Entradas en RAM: $n = 5$ (`0x00201000`), $\text{fact} = 1$ (`0x00201008`).
   - Salida en RAM tras HLT: $\text{Mem}[\text{fact}] = 120$ ($5! = 120$).
3. **Fibonacci (`cacao_fibonacci.asm`):**
   - Inicialización en RAM: arreglo de 7 elementos en `0x00201000` con `fib0 = 0`, `fib1 = 1`.
   - Salida en RAM tras HLT: $\text{Mem}[\text{res}] = 8$ (séptimo término de la sucesión: $[0, 1, 1, 2, 3, 5, 8]$).

---

## 6. Manual de Uso Rápido

### Línea de Comandos (CLI)

```bash
# 1. Traducir y mostrar en consola
python -m spl.traductor spl/traductor/ejemplos/cacao_euclides.asm

# 2. Traducir y guardar archivo .asm de Enigma-64
python -m spl.traductor spl/traductor/ejemplos/cacao_euclides.asm -o euclides_enigma.asm

# 3. Exportar binario estructurado .e64 para la GUI Noctua
python -m spl.traductor spl/traductor/ejemplos/cacao_euclides.asm --exportar-e64 euclides.e64

# 4. Traducir y ejecutar con CargadorEnigma
python -m spl.traductor spl/traductor/ejemplos/cacao_euclides.asm --ejecutar --cargador
```

### API en Python

```python
from spl.traductor.directivas import cargar_y_ejecutar_con_cargador

fuente_cacao = open("spl/traductor/ejemplos/cacao_euclides.asm").read()
cpu, banco, ram, cargador, info = cargar_y_ejecutar_con_cargador(fuente_cacao)

# Consultar resultado en la memoria física de Enigma-64
mcd, _ = ram.mem_read(0x00201000, 8)
print(f"MCD calculado en hardware: {mcd}")  # Imprime: 6
```
