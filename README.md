# Enigma-64

Emulador, cadena de herramientas y compilador de la arquitectura **Enigma-64** de **Noctua Systems**.

Enigma-64 es un computador Von Neumann de 64 bits con memoria paginada dispersa, unidad de control FSM multiciclo, unidad de punto flotante (FPU) IEEE 754, subsistema de E/S mapeada en memoria (MMIO), enlazador de módulos objeto reubicables, cargador con protección de memoria, conjunto de herramientas de procesamiento de lenguaje (SPL) e interfaz gráfica interactiva.

---

## Especificaciones de la máquina

| Característica | Especificación |
|---|---|
| **Arquitectura** | Von Neumann (código y datos unificados) |
| **Tamaño de palabra** | 64 bits (8 bytes) |
| **Unidad direccionable** | Byte (8 bits) |
| **Buses de datos y direcciones** | 64 bits |
| **Ordenamiento de bytes** | Big-Endian |
| **Espacio de direcciones** | 4 GiB físicos (`0x00000000` – `0xFFFFFFFF`), espacio lógico de 64 bits |
| **Registros arquitectónicos** | `R0`–`R7`, `PC`, `SR` (registro de estado con banderas Z, N, C, V, M, I, S) |
| **Registro `R0`** | Cableado a cero constante (`0x0`); escrituras descartadas |
| **Punteros especiales** | `SP` (`R6`, inicializado en `0x00000000EFFFFFFF`), `BP` (`R7`), `RV` (`R5`) |
| **Formatos de instrucción** | 6 formatos variables (longitud de 1 a 5 bytes) |
| **Entrada / Salida** | Mapeada en memoria (MMIO) en el rango `0xFF000000` – `0xFFFFFFFF` |
| **Espacio de usuario** | `0x00200000` – `0xBFFFFFFF` (código en `0x00200000`, datos en `0x00201000`) |

### Mapa de memoria

| Rango de direcciones | Tamaño | Propósito / Región |
|---|---|---|
| `0x00000000` – `0x00000FFF` | 4 KiB | Vectores de interrupción y reset (Modo Supervisor) |
| `0x00001000` – `0x000FFFFF` | ~1 MiB | Firmware residente y subrutina de carga inicial |
| `0x00100000` – `0x001FFFFF` | 1 MiB | Área de trabajo del sistema y tablas del monitor |
| `0x00200000` – `0xBFFFFFFF` | ~3 GiB | Espacio de usuario: código (`.text`), datos (`.data`) y montículo (*heap*) |
| `0xC0000000` – `0xEFFFFFFF` | 768 MiB | Pila de usuario (*stack*), decrece desde `0xEFFFFFFF` |
| `0xFF000000` – `0xFFFFFFFF` | 16 MiB | Espacio reservado para E/S mapeada en memoria (MMIO) |

---

## Estructura del repositorio

```text
Enigma-64/
├── main.py                     Punto de entrada: lanza la interfaz gráfica del emulador
├── requirements.txt            Dependencias del proyecto
├── enigma64/                   Núcleo del emulador
│   ├── cpu.py                  Unidad de Control FSM (5 fases) y PrefetchBuffer
│   ├── alu.py                  Unidad Aritmético-Lógica (ALU) pura de 64 bits
│   ├── registros.py            Banco de registros y registro de estado (SR)
│   ├── memoria.py              Controlador de memoria RAM física y buses
│   ├── cargador.py             Cargador de ejecutables (.e64, .obj, .bin) y editor de bits
│   ├── ensamblador.py          Ensamblador oficial de Enigma-64
│   ├── perifericos.py          Subsistema MMIO y controlador de pantalla CRT
│   ├── fpu.py                  Emulador de FPU y tabla canónica FPU_VECTORES
│   ├── asm/                    Firmware y rutinas ensamblador de la FPU (.s)
│   ├── enlazador/              Enlazador de módulos objeto reubicables (.obj)
│   │   ├── objeto.py           Formato .obj, tablas de símbolos y marcas de reubicación
│   │   ├── enlace.py           Motor de enlace en dos pasadas (EnlazadorEnigma)
│   │   └── ejemplos.py         Módulos objeto de ejemplo
│   └── ui/                     Interfaz gráfica interactiva (Tkinter)
│       ├── shell/ventana.py    Ventana principal del emulador
│       └── paneles/            Paneles interactivos: memoria RAM, MMIO y FPU
├── spl/                        Sistema de Procesamiento del Lenguaje (SPL)
│   ├── preprocesador/          Preprocesador de directivas (#include, #define, etc.)
│   ├── compilador/             Compilador de alto nivel (lexer PLY y tablas de símbolos)
│   ├── ensamblador/            Analizador léxico del ensamblador SPL
│   ├── traductor/              Traductor de ensamblador CacaoCore-64 a Enigma-64
│   └── pipeline.py             Orquestador integral del pipeline SPL
├── programas/                  Binarios ejecutables (.bin, .hex, .e64) y bibliotecas
├── scripts/                    Utilidades de compilación y generación de binarios
└── tests/                      Batería completa de pruebas automatizadas
```

---

## Requisitos e instalación

- **Python 3.10** o superior.
- **Tkinter** (incluido por defecto en la distribución estándar de Python para Windows y macOS; en Linux disponible mediante `sudo apt install python3-tk`).
- Dependencias de desarrollo (`pytest` y `ply`):

```bash
pip install -r requirements.txt
```

---

## Cómo ejecutar

### Interfaz gráfica y herramientas CLI

```bash
# Iniciar la interfaz gráfica interactiva
python main.py

# Analizar un módulo objeto reubicable (.obj)
python -m enigma64.enlazador programas/objetos/principal.obj

# Enlazar módulos objeto y generar un ejecutable .e64
python -m enigma64.enlazador programas/objetos/principal.obj programas/objetos/libmat.obj -o programa.e64

# Ejecutar el pipeline completo del compilador SPL
python -m spl --escenario 1

# Ensamblar código SPL a bajo nivel
python -m spl.ensamblador spl/ensamblador/ejemplos/prueba.asm
```

### Uso programático desde Python

```python
from enigma64.cpu import CPU
from enigma64.memoria import RAMMemory
from enigma64.registros import BancoRegistros
from enigma64.ensamblador import ensamblar

# Inicializar hardware
ram = RAMMemory()
banco = BancoRegistros()
cpu = CPU(ram=ram, banco=banco)

# Ensamblar instrucciones y cargar en RAM (espacio de usuario)
codigo = ensamblar("""
    ADDI R1, R0, 40
    ADDI R2, R0, 2
    ADD  R5, R1, R2
    HLT
""")
for i, byte in enumerate(codigo):
    ram.mem_write(0x00200000 + i, byte, 1, check_alignment=False)

banco.pc = 0x00200000
cpu.ejecutar()
print("Resultado en R5:", banco.leer_nombre("R5"))  # 42
```

### Programas de demostración incluidos

El directorio `programas/` contiene ejecutables listos para su carga y validación:

- **Factorial ($N!$):** Ubicado en `0x00200000`, calcula $5! = 120$ en `0x00201008`.
- **Algoritmo de Euclides ($MCD$):** Ubicado en `0x00200100`, calcula $\text{MCD}(48, 18) = 6$ en `0x00202010`.
- **Sucesión de Fibonacci:** Ubicado en `0x00200200`, genera los primeros términos en `0x00203000`–`0x00203030`.
- **Constante de Brun ($B_2$):** En `programas/constante_brun.s`, estima la suma de recíprocos de primos gemelos usando la FPU.

---

## Arquitectura del sistema

### Unidad de Control (CPU) y Microarquitectura FSM
- **FSM síncrona de 5 fases**:
  - `FETCH`: Lectura continua de instrucciones mediante una cola FIFO (`PrefetchBuffer` de 16 bytes) que resuelve cruces de fronteras de palabra.
  - `DECODE`: Decodificación de los 6 formatos de instrucción (1 a 5 bytes) y extensión de signo para inmediatos de 16 bits.
  - `EXECUTE`: Despacho de operaciones aritmético-lógicas a la ALU, evaluación de saltos y bifurcaciones condicionales.
  - `MEMORY`: Accesos a RAM (`LOAD`, `STORE`, `LDB`, `STB`), verificación de alineación natural y desvío a MMIO.
  - `WRITE-BACK`: Actualización del banco de registros, `PC`, `SP` y registro de estado (`SR`).

### Repertorio de instrucciones (ISA)
La CPU implementa 41 instrucciones divididas en 6 grupos funcionales:
- **Aritmética entera:** `ADD`, `SUB`, `MUL`, `DIV`, `ADDI`, `SUBI`, `INC`, `DEC`
- **Lógica, desplazamiento y comparación:** `AND`, `OR`, `XOR`, `NOT`, `SHL`, `SHR`, `ASR`, `CMP`
- **Acceso a memoria:** `LOAD`, `STORE` (palabras de 64 bits), `LDB`, `STB` (bytes individuales)
- **Control de flujo y bifurcación:** `JMP`, `JZ`, `JNZ`, `JC`, `JNC`, `JN`, `JP`, `JV`, `JNV`, `JMPR`, `HLT`
- **Subrutinas y marco de pila:** `CALL`, `CALLR`, `RET`, `PUSH`, `POP`, `ENTER`, `LEAVE`
- **Control de interrupciones:** `EI`, `DI`, `IRET`

### Banco de Registros y ALU
- Registros de 64 bits con enmascaramiento automático.
- `R0` cableado a cero constante (las escrituras se ignoran).
- `SR` con banderas de condición: `Z` (cero), `N` (negativo), `C` (acarreo / préstamo), `V` (desbordamiento), `M` (desalineación de memoria), `I` (interrupciones) y `S` (modo supervisor).
- ALU de 64 bits pura y sin estado para las 16 operaciones aritmético-lógicas.

### Memoria RAM y Buses
- **Paginación bajo demanda (*Sparse Memory*)**: Asignación dinámica en bloques de 4 KiB (`PAGE_SIZE = 4096`), optimizando el uso de memoria en el anfitrión.
- **Validación de fronteras y alineación**:
  - Rechazo de accesos fuera de los 4 GiB físicos (`ADDR_FAULT`).
  - Control de alineación natural en accesos de palabra de 64 bits: las direcciones deben ser múltiplos de 8 bytes; un acceso desalineado retorna `MISALIGNED` y activa la bandera `M`.
  - Las lecturas/escrituras de 1 byte (`LDB`, `STB`) no requieren alineación a 8 bytes.
- **MMIO**: Direcciones en el rango `0xFF000000`–`0xFFFFFFFF` se desvían al controlador de periféricos (terminal de pantalla CRT, teclado, temporizador, disco y red).

### Enlazador y Cargador de Programas
- **Cargador (`CargadorEnigma`)**:
  - Admite binarios planos (`.bin`), binarios estructurados (`.e64`) y módulos objeto (`.obj`).
  - Protege áreas reservadas del sistema (vectores en `0x00000000`, firmware en `0x00001000`) y restringe la carga de programas de usuario a `>= 0x00200000`.
- **Enlazador (`EnlazadorEnigma`)**:
  - Procesa módulos objeto reubicables en formato Big-Endian (`EOBJ`).
  - Resuelve referencias externas contra la tabla global de símbolos (ESTAB) y genera la sección `.bss` inicializada en cero.
  - Aplica las 5 marcas de reubicación: `ABS64`, `ABS32`, `REL16`, `HI16` (con ajuste `+0x8000` por extensión de signo de `ADDI`) y `LO16`.

### Unidad de Punto Flotante (FPU)
- Operaciones en formato IEEE 754 binary64 (doble precisión) con redondeo al par más cercano (*roundTiesToEven*), tratamiento de subnormales y casos especiales (NaN, $\pm\infty$, $\pm 0$):
  - `FADD` / `FSUB`: Suma y resta de flotantes.
  - `FMUL`: Multiplicación con producto exacto de 128 bits (`FPU_MUL128`).
  - `FDIV`: División de flotantes con bits de guarda, redondeo y pegajoso (*sticky*).
  - `FCMP`: Comparador quieto (*quiet comparison*).
  - `FSQRT`: Raíz cuadrada iterativa por Newton-Raphson.
  - `FPU_INT_TO_FLOAT` / `FPU_FLOAT_TO_INT`: Conversiones bidireccionales entero $\leftrightarrow$ flotante.
- Mesa de salto canónica desacoplada: `FPU_VECTORES`.

### Sistema de Procesamiento del Lenguaje (SPL)
- **Preprocesador**: Expansión de macros, inclusión de cabeceras (`#include`) y compilación condicional (`#ifdef`, `#ifndef`).
- **Compilador SPL**: Analizador léxico PLY para lenguaje imperativo estructurado (tipos primitivos, arreglos, matrices, TDA `struct`, estructuras de control) con gestión integrada de tablas de símbolos (`tablaID`, `tablaNum`, `tablaString`).
- **Ensamblador SPL**: Analizador léxico PLY de la sintaxis ensambladora de Enigma-64.
- **Traductor de compatibilidad**: Traducción automática de ensamblador CacaoCore-64 a Enigma-64 (`LOAD`, `STORE`, `LDB`, `STB`, `LEA`), con reubicación a espacio de usuario y alineación de desplazamientos a múltiplos de 8 bytes.

### Interfaz Gráfica (GUI)
- Visualizador y editor interactivo de memoria RAM con selector de banco y conmutación de bits en vivo.
- Monitor en tiempo real del banco de registros, banderas `SR` y panel de pruebas ALU.
- Terminal CRT emulada conectada al puerto de salida MMIO (`0xFF001000`).
- Calculadora reactiva de FPU con desglose de campos IEEE 754 (signo, exponente, mantisa).

---

## Pruebas automatizadas

El proyecto cuenta con una amplia suite de pruebas unitarias, de integración y de hardware emulado ejecutadas con `pytest`:

```bash
# Ejecutar la suite completa de pruebas
python -m pytest

# Ejecutar únicamente las pruebas del núcleo (CPU, ALU, registros, memoria, enlazador)
python -m pytest tests/core/

# Ejecutar las pruebas de la FPU
python -m pytest tests/fpu/

# Ejecutar las pruebas del sistema SPL y traductores
python -m pytest tests/test_spl/

# Ejecutar las pruebas de la interfaz gráfica
python -m pytest tests/ui/
```

---

## Autores

- Juan Sebastian Umaña Camacho
- Tomas Felipe Garzón Gómez
- Michael Stiven Betancourt Gelves
- Deibyd Santiago Barragán Gaitán
- Maicol Sebastian Olarte Ramirez
- Juan Luis Vergara Novoa
- Alejandro Argüello Muñoz
