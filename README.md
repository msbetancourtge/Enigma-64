# Enigma-64

A Von Neumann-Like Computer with Compiler and a Programming Language

Emulador del computador **Enigma-64** de **Noctua Systems**, diseñado en la Tarea 9
e implementado en la Tarea 10 del curso Lenguajes de Programación G2 2026-2.

## Especificación de la máquina

| Característica | Valor |
|---|---|
| Arquitectura | Von Neumann (memoria unificada de datos e instrucciones) |
| Tamaño de palabra | 64 bits (8 bytes) |
| Unidad direccionable | Byte |
| Bus de datos / direcciones | 64 bits |
| Ordenamiento de bytes | Big-endian |
| Espacio lógico | 2⁶⁴ bytes |
| Memoria física | 4 GiB (`0x00000000` – `0xFFFFFFFF`) |
| Registros arquitectónicos | R0–R7, PC, SR |
| Formatos de instrucción | 6 formatos, longitud variable (1 a 5 bytes) |
| E/S | Mapeada a memoria a partir de `0xFF000000` |

## Autores

- Juan Sebastian Umaña Camacho
- Tomas Felipe Garzón Gómez
- Michael Stiven Betancourt Gelves
- Deibyd Santiago Barragán Gaitán
- Maicol Sebastian Olarte Ramirez
- Juan Luis Vergara Novoa
- Alejandro Argüello Muñoz

## Estructura del repositorio

```
Enigma-64/
├── .gitignore
├── LICENSE
├── README.md
├── requirements.txt
├── environment.yml
├── main.py                        Punto de entrada: lanza la interfaz gráfica del emulador
├── verificacion_manual.py         Script de trazado y verificación del bucle factorial
├── enigma64/                           Paquete principal del emulador
│   ├── __init__.py                Exportación de la API pública del sistema
│   ├── registros.py               Banco de registros de 64 bits, punteros y banderas SR
│   ├── alu.py                     Unidad Aritmético-Lógica (ALU) pura de 64 bits
│   ├── memoria.py                 Controlador de memoria RAM física y subsistema de buses
│   ├── cpu.py                     Unidad de Control FSM (5 fases) y PrefetchBuffer
│   ├── cargador.py                Cargador de ejecutables (.e64, .bin) y manipulador de bits
│   ├── perifericos.py             Subsistema MMIO y controlador de pantalla CRT
│   ├── programas.py               Definición y compilación de programas oficiales de prueba
│   ├── fpu.py                     EmuladorFPUEnigma64, vector jump table y utilidades IEEE 754
│   ├── fpu.s                      Núcleo FPU: FADD, FSUB, empaquetado y desempaquetado
│   ├── fmul.s                     Multiplicación FMUL (IEEE 754 binary64) y MUL128
│   ├── fdiv.s                     División FDIV (IEEE 754 binary64) con guarda y pegajoso
│   ├── fcmp.s                     Comparador FCMP quieto de flotantes IEEE 754
│   ├── fconv.s                    Conversiones INT-FLOAT, FLOAT-INT y tabla canónica FPU_VECTORES
│   ├── fsqrt.s                    Raíz cuadrada FSQRT (Newton-Raphson, Ricardo Peña pág. 26)
│   ├── oraculo_ieee754.py         Módulo utilitario de validación IEEE 754 y oráculo de referencia
│   ├── ui/                        Interfaz gráfica modular (Tkinter / TTK)
│   │   ├── shell/ventana.py       Shell principal y cuaderno de módulos
│   │   ├── paneles/panel_memoria.py Grilla interactiva de RAM (8 bancos) y editor de bits
│   │   ├── paneles/panel_mmio.py  Terminal CRT y visualizador de registros MMIO
│   │   └── paneles/panel_fpu.py   Calculadora reactiva de la FPU y visor IEEE 754
│   └── gui/
│       ├── __init__.py
│       └── panel_registros.py     Panel en vivo de registros y banco de pruebas ALU
├── programas/                     Archivos binarios (.bin, .hex, .e64) y biblioteca fpu_lib.*
├── scripts/                       Scripts utilitarios (generación automatizada de binarios)
└── tests/                         Suite de pruebas automatizadas
    ├── conftest.py                Configuración global de entorno para pytest
    ├── test_registros_alu.py      Pruebas de banco de registros y operaciones ALU
    ├── test_memoria.py            Pruebas de memoria física, paginación y alineación
    ├── test_cpu.py                Pruebas de la CPU, FSM multiciclo y decodificador
    ├── test_cargador.py           Pruebas de carga, formatos y manipulación de bits
    ├── test_perifericos.py        Pruebas de MMIO y controlador de pantalla
    ├── test_algoritmos.py         Pruebas de ejecución de algoritmos oficiales
    ├── test_fpu.py                Pruebas de FADD, FSUB, desempaquetar y empaquetar
    ├── test_fmul.py               Pruebas de FMUL (IEEE 754 binary64) contra el oráculo de Python
    ├── test_fconv.py              Pruebas de conversiones INT-FLOAT y mesa de vectores FPU
    ├── test_oraculo.py            Pruebas del oráculo de validación IEEE 754 y simulación Newton
    ├── test_fsqrt.py              Pruebas de FSQRT (Newton-Raphson) en la CPU contra el oráculo
    ├── test_ui_aislamiento.py     Pruebas estáticas de desacoplamiento de capas (AST)
    ├── test_ui_fpu.py             Pruebas del panel de la FPU, su adaptador y el formato IEEE 754
    ├── test_ui_modulos_nuevos.py  Pruebas de interfaces de servicios y adaptadores
    ├── test_ui_nucleo.py          Pruebas del núcleo de interfaz y bus de eventos
    ├── test_ui_paneles.py         Pruebas funcionales de los paneles gráficos
    └── test_ui_visor_ram_mmio.py  Pruebas de visualización de memoria y edición de bits
```

## Requisitos

- Python 3.10 o superior
- Tkinter (viene incluido con el instalador oficial de Python en Windows)

El emulador central utiliza únicamente la biblioteca estándar. Para instalar las dependencias de prueba (`pytest`):

```bash
pip install -r requirements.txt
```

## Cómo ejecutar

**Todo se ejecuta desde la raíz del repositorio.** Un archivo dentro de `enigma64/`
nunca se lanza con `python ruta/archivo.py`, porque Python no encontraría el paquete.
Se lanza con `python -m enigma64.modulo` o a través de `main.py`.

```bash
cd Enigma-64

# Interfaz gráfica
python main.py

# Equivalente, lanzando el módulo directamente
python -m enigma64.gui.panel_registros
```

---

# Subsistema de Memoria RAM y Buses

## Qué incluye

**`enigma64/memoria.py`** — Controlador de memoria física y subsistema de buses de 64 bits (código 100% en inglés con comentarios explicativos en español).

- **Paginación por software bajo demanda (Sparse Memory):** No instancia un arreglo real de 4 GiB en memoria del host. Implementa un diccionario (`dict`) donde la clave es el índice del bloque de 4 KiB (`PAGE_SIZE = 4096` bytes) y el valor es un `bytearray`.
- **Lectura limpia sin reservas innecesarias:** Si se lee una dirección de un bloque no existente en el diccionario, retorna ceros sin instanciar la página.
- **Escritura bajo demanda:** Al escribir en una dirección no asignada, crea e inicializa el bloque en ceros automáticamente y luego escribe los datos.
- **Validación lógica de 64 bits:** Comprueba que los bits superiores `A[63:32]` sean exactamente `0x00000000`. Si hay algún bit activo (dirección mayor a 4 GiB físicos o negativa), la memoria aborta la operación y retorna la señal `"ADDR_FAULT"`.
- **Enrutamiento a MMIO (Memory-Mapped I/O):** Inspecciona los bits `A[31:24]`. Si este segmento equivale a `0xFF` (direcciones `0xFF000000` a `0xFFFFFFFF`), la memoria no accede a las celdas de RAM y retorna el estado `"MMIO"` para delegar el control al bus de periféricos (pantalla, teclado, temporizadores).
- **Formato Big-Endian:** Toda lectura y escritura en los bloques interpreta y serializa los datos en formato Big-Endian usando `int.from_bytes()` e `int.to_bytes()`.
- **Control estricto de alineación natural:** Para accesos a datos, verifica que la dirección solicitada sea múltiplo exacto del tamaño (`address % size_bytes == 0`). De lo contrario, aborta la operación y retorna el estado `"MISALIGNED"`.
- **Cruce transparente entre bloques:** Permite lecturas y escrituras continuas que atraviesan los límites entre páginas consecutivas (crucial para instrucciones de longitud variable de 1 a 5 bytes).
- **Protocolo de retorno de buses:** Simula el bus de datos y control retornando una tupla `(data, status)`.

## API pública

```python
from enigma64 import (
    RAMMemory,
    PAGE_SIZE,
    STATUS_READY,
    STATUS_ADDR_FAULT,
    STATUS_MMIO,
    STATUS_MISALIGNED,
)

ram = RAMMemory(page_size=4096)
```

### Métodos y Propiedades

| Método / Propiedad | Tipo | Descripción |
|---|---|---|
| `mem_read(address, size_bytes, check_alignment=True)` | `(int \| None, str)` | Lee 1, 2, 4 u 8 bytes en formato Big-Endian. Retorna `(valor, status)`. |
| `mem_write(address, data, size_bytes, check_alignment=True)` | `(None, str)` | Escribe 1, 2, 4 u 8 bytes en Big-Endian. Retorna `(None, status)`. |
| `reset()` | `None` | Vacía el diccionario de páginas liberando la memoria al estado de reset. |
| `.allocated_blocks` | `List[int]` | Lista ordenada de los índices de páginas actualmente residentes en memoria. |
| `.allocated_bytes` | `int` | Memoria real consumida en bytes por las páginas activas. |
| `.page_size` | `int` | Tamaño de bloque configurado (4096 bytes por defecto). |

### Señales del Bus de Control (`status`)

| Señal | Significado arquitectónico | Acción esperada de la CPU / Buses |
|---|---|---|
| `"READY"` | Operación completada con éxito en la RAM física | El ciclo continúa normalmente; en lectura `data` contiene el valor. |
| `"MISALIGNED"` | Dirección no alineada al tamaño del dato | La CPU enciende la bandera `M` (bit 4 del SR) y genera excepción si aplica. |
| `"MMIO"` | Dirección ubicada en `0xFF000000` - `0xFFFFFFFF` | La solicitud se desvía al subsistema de periféricos MMIO. |
| `"ADDR_FAULT"` | Dirección mayor a 4 GiB (`A[63:32] != 0`) o negativa | La CPU aborta la instrucción y dispara un fallo de protección de memoria. |

Excepciones: `InvalidAccessSizeError` (si `size_bytes` no pertenece a `{1, 2, 4, 8}`).

## Decisiones de diseño tomadas

| Punto | Decisión | Razón |
|---|---|---|
| Tamaño de bloque | 4 KiB (`4096` bytes) | Estándar de la arquitectura y compromiso ideal entre granularidad de asignación y velocidad de consulta en Python. |
| Prioridad de decodificación | Rango 64 bits → MMIO → Alineación → Acceso RAM | Sigue fielmente la cascada de decodificación de hardware antes de energizar las líneas de celdas de RAM. |
| Parámetro `check_alignment` | Opcional, por defecto `True` | El ISA tiene instrucciones de longitud variable (1 a 5 bytes) que pueden iniciar en direcciones arbitrarias; la CPU puede pasar `check_alignment=False` en la fase FETCH. |
| Manejo de lecturas vacías | Retorna `0` y no muta `self.pages` | Cumple el principio de Sparse Memory: la memoria no inicializada se lee como ceros sin inflar el uso de RAM del emulador. |
| Máscara en escritura | `data & ((1 << (size_bytes * 8)) - 1)` | Si la CPU pasa un registro de 64 bits para una escritura de 1 o 2 bytes (`STB`, etc.), se aíslan limpiamente los bits menos significativos. |

---

# Banco de Registros y Unidad Aritmético-Lógica (ALU)

## Qué incluye

**`enigma64/registros.py`** — Banco de registros de 64 bits.

- Los 10 registros arquitectónicos con su codificación de 4 bits (`R0`=0x0 … `SR`=0x9).
- R0 cableado a cero: toda escritura se descarta silenciosamente, como en el hardware.
- Enmascarado automático a 64 bits: acepta negativos y enteros grandes de Python.
- Valores de reset: `PC = 0x0`, `SP = 0x00000000EFFFFFFF`.
- Registro SR con las siete banderas Z, N, C, V, M, I, S en los bits 0 a 6.
- Rechazo de los códigos reservados 0xA–0xF.
- Sistema de suscripción para que la GUI se refresque sola.
- `snapshot()`: estado completo en un diccionario, listo para pintar o para un log.

**`enigma64/alu.py`** — ALU de 64 bits, sin estado.

16 operaciones: `ADD SUB MUL DIV ADDI SUBI INC DEC AND OR XOR NOT SHL SHR ASR CMP`.

La ALU es **pura**: recibe dos operandos y devuelve el resultado con sus banderas, sin
tocar el banco de registros. Quien decide si esas banderas se vuelcan al SR y si el
resultado se escribe en Rd es la Unidad de Control. Esto mantiene el Write-Back donde
corresponde (en la FSM) y hace la ALU trivial de probar.

**`enigma64/gui/panel_registros.py`** — Dos componentes de Tkinter.

- `PanelRegistros`: un `ttk.Frame` reutilizable con la tabla de registros (hex y decimal
  con signo) y las siete banderas. Se suscribe al banco y se refresca solo. Resalta en
  amarillo los registros que cambiaron en la última operación.
- `BancoPruebasALU`: controles para disparar operaciones a mano y una bitácora.

## API pública

```python
from enigma64 import ALU, BancoRegistros, hex64

banco = BancoRegistros()
alu = ALU()
```

### BancoRegistros

| Método | Uso |
|---|---|
| `leer(codigo)` / `escribir(codigo, valor)` | Acceso por nibble, lo que usa el decodificador |
| `leer_nombre("R1")` / `escribir_nombre("R1", v)` | Acceso por nombre, cómodo en tests y GUI |
| `.pc` `.sp` `.bp` `.sr` | Propiedades de lectura/escritura directa |
| `avanzar_pc(n)` | Autoincrementa el PC por la longitud de la instrucción |
| `leer_bandera("Z")` / `escribir_bandera("Z", 1)` | Banderas individuales |
| `aplicar_banderas(banderas, afectadas)` | Vuelca al SR solo las banderas que la instrucción afecta |
| `.en_supervisor` / `.interrupciones_habilitadas` | Bits S e I |
| `suscribir(callback)` | Registra un observador para la GUI |
| `snapshot()` | Estado completo como diccionario |
| `reset()` | Estado de encendido |

### ALU

```python
resultado = alu.ejecutar("ADD", a, b)

resultado.valor            # entero de 64 bits
resultado.hex              # "0x0000000000000078"
resultado.con_signo        # interpretación en complemento a 2
resultado.banderas         # {"Z": 0, "N": 0, "C": 0, "V": 0}
resultado.afectadas        # frozenset de las banderas que esta operación modifica
resultado.escribe_destino  # False solo para CMP
```

`resultado.afectadas` es lo que hace que `MUL` actualice Z y N sin pisar C ni V, y que
`CMP` no escriba Rd. Sale directo de la columna "Banderas" de las tablas del ISA.

Excepciones: `DivisionPorCero`, `OperacionInvalida`, `RegistroInvalido`.

## Decisiones de diseño tomadas

El documento de la Tarea 9 no especifica estos puntos. Quedan resueltos así y
documentados en el código:

| Punto | Decisión | Razón |
|---|---|---|
| Bandera C en la resta | `C = 1` cuando hay préstamo (`A < B` sin signo), estilo x86 | Es lo que se lee natural en los trazados manuales del documento. Configurable en `alu.CARRY_EN_RESTA` |
| División entera | Truncada hacia cero | El operador `//` de Python trunca hacia −∞: `-7 // 2` da −4, pero el hardware entrega −3 |
| Desplazamiento de 0 posiciones | La bandera C no se modifica | Convención estándar |
| Desplazamiento con n ≥ 64 | Resultado 0 (o todo bits de signo en `ASR`); C toma el último bit expulsado solo si `n == 64` | El inmediato es de 16 bits, así que el caso es alcanzable |
| `DIV` con divisor 0 | Lanza `DivisionPorCero` | La CPU interrumpe la instrucción y genera una excepción de CPU (`DivisionPorCero`). |

## Especificaciones y Decisiones de Diseño Arquitectónico

1. **Rol de `R0` y Banco de Registros de Propósito General:**
   - La arquitectura define formalmente cinco registros dentro del grupo de propósito general (`R0` a `R4`).
   - Dentro de este bloque, `R0` tiene una función arquitectónica esencial: provee de forma cableada y constante el valor cero (`0x0000000000000000`) del sistema. Se utiliza como fuente para emitir el cero en secuencias de reset, instrucciones de detención (`HALT`), condiciones de bifurcación y operaciones aritmético-lógicas sin necesidad de consumir inmediatos en el bus.
   - En el emulador, toda escritura hacia `R0` se descarta por hardware silenciosamente sin error, asegurando que su lectura siempre entregue cero. Los registros `R1` a `R4` operan como registros de propósito general de lectura/escritura libre.

2. **Valor de Reset del Registro de Estado (SR):**
   - Siguiendo la especificación de la Tarea 9, el valor de reset por defecto es `0x0000000000000001`, lo cual inicializa la CPU con la bandera de cero activa (`Z = 1`).
   - Adicionalmente, para escenarios de ejecución que requieran arrancar explícitamente con privilegios de Supervisor para la inicialización protegida de memoria (`0x00100000`) o firmware (`0x00001000`), el módulo provee y soporta la constante `SR_RESET_SUPERVISOR = 0x0000000000000040` (`S = 1`), permitiendo configurar el modo de inicio según las necesidades de ejecución.

---

# Cargador de Programas y Manipulación de Memoria Bit a Bit

## Qué incluye

**`enigma64/cargador.py`** — Submódulo del Cargador, Manipulador de Memoria Bit a Bit y Firmware (código 100% en Python estándar, sin dependencias externas).

- **Manipulación directa de bits y bytes en RAM:**
  - `leer_bit(ram, direccion, bit_index)`: Lee un bit individual (0 a 7, donde bit 0 es LSB y bit 7 es MSB) en cualquier celda física accesible de la RAM.
  - `escribir_bit(ram, direccion, bit_index, valor)`: Modifica atómicamente un único bit (0 o 1) mediante máscaras (`|` o `& ~`) sin alterar los 7 bits restantes del byte ni celdas contiguas.
  - `conmutar_bit(ram, direccion, bit_index)`: Invierte el bit indicado mediante máscara XOR (`^`).
  - `byte_a_cadena_bits(ram, direccion)`: Genera la cadena de 8 bits (ej. `'10110001'`) formateada de MSB a LSB, lista para la grilla interactiva de edición de memoria en la GUI.
  - `escribir_byte_directo(ram, direccion, valor)` y `leer_byte_directo(ram, direccion)`: Métodos utilitarios de bajo nivel sobre RAM sin verificación de alineación.
- **Modelo de ejecutable con soporte dual (`BinarioEnigma`):**
  - **Modo 1: Binario plano crudo (`.bin`):** Volcado directo de opcodes e inmediatos para las pruebas inmediatas de la Tarea 10 (Factorial, Euclides y Fibonacci).
  - **Modo 2: Binario estructurado Enigma-64 (`.e64`):** Cabecera Big-Endian de 32 bytes (`>4s7I`) que encapsula número mágico (`b'ENIG'`), flags (absoluto vs. reubicable), `entry_point`, `direccion_base`, tamaño de código (`.text`), tamaño de datos (`.data`), tabla de reubicación y tabla de símbolos.
  - **Preparación para el futuro Enlazador:** Si un binario reubicable se monta en una dirección destino diferente a su dirección base original, el cargador procesa la tabla de reubicación y parcha las referencias absolutas automáticamente.
- **Parser de volcados de texto (`parsear_texto_a_bytes`):**
  - Procesa volcados en texto con tokens hexadecimales (`0x78`, `4A`), binarios (`0b11001100`) o decimales, ignorando comentarios (`#`, `//`, `;`) y espacios.
- **Motor del Cargador (`CargadorEnigma`):**
  - Ciclo de vida desacoplado: detención preventiva de la CPU -> validación estricta de fronteras -> reubicación dinámica -> volcado secuencial a RAM -> inicialización de hardware -> reanudación.
  - **Validación estricta de fronteras (Tarea 9):**
    - Bits altos de 64 bits: `A[63:32] == 0` (evita `ADDR_FAULT` y valida espacio físico de 4 GiB).
    - Límite inferior: rechaza cargas por debajo de `0x00200000` (protege vectores en `0x00000000`, firmware en `0x00001000` y área de trabajo en `0x00100000`) lanzando `ViolacionProteccionMemoria`.
    - Límite superior: rechaza cualquier programa cuyo rango invada o sobrepase `0xC0000000` (inicio de la Pila/Stack) lanzando `ViolacionProteccionMemoria`.
- **Inicialización del contexto de hardware:**
  - Tras la carga, inicializa el banco de registros: `PC = entry_point`, `SP = 0x00000000EFFFFFFF` (tope de pila inicial), `SR = SR_RESET`, `R0 = 0` y `R5 = entry_point` (convención de retorno).
- **Emulación de la subrutina de firmware (`emular_subrutina_cargador`):**
  - Modela en software la subrutina residente en `0x00001000`: lee los parámetros pasados en `R1` (origen/buffer), `R2` (destino en RAM), `R3` (longitud), transfiere los bytes y carga `R5 = R2` para que la instrucción siguiente ejecute `JMPR R5`.

## API pública

```python
from enigma64 import (
    CargadorEnigma,
    BinarioEnigma,
    leer_bit,
    escribir_bit,
    conmutar_bit,
    byte_a_cadena_bits,
    emular_subrutina_cargador,
)

cargador = CargadorEnigma(ram=ram, banco=banco)

# Cargar un archivo .bin plano o .e64 estructurado
metadatos = cargador.cargar_archivo("programas/factorial.bin", direccion_destino=0x00200000)

# O cargar bytes crudos directamente
metadatos = cargador.cargar_bytes(b"\x10\x20\x30\x40", direccion_destino=0x00200000)

# Manipulación de bits en memoria para la GUI
bit_val = leer_bit(ram, 0x00200000, bit_index=3)
escribir_bit(ram, 0x00200000, bit_index=3, valor=1)
```

---

# Pruebas

## Nivel 1 — El paquete se importa

```bash
python -c "from enigma64 import ALU, BancoRegistros, RAMMemory, CargadorEnigma; print('OK')"
```

Si falla aquí el problema es de ubicación de archivos, no de código:

- `No module named 'enigma64'` → no estás en la raíz del repositorio.
- `No module named 'enigma64.memoria'` o `enigma64.alu` → falta algún `.py` dentro del paquete.
- `attempted relative import` → falta un `__init__.py`.

## Nivel 2 — Suite de pruebas unitarias

```bash
python -m unittest discover -s tests -v
```

Debe terminar en `Ran 81 tests ... OK`. Cobertura:

| Módulo | Grupo | Qué verifica |
|---|---|---|
| **RAM & Buses** | `TestRAMPaging` | Lectura limpia en ceros sin instanciación, asignación bajo demanda, múltiples accesos por página, liberación completa con `reset()` |
| **RAM & Buses** | `TestBigEndianAndBlockCrossing` | Ordenamiento Big-Endian en 1, 2, 4 y 8 bytes, verificación byte a byte en páginas físicas, cruce continuo entre límites de bloques (4 y 8 bytes) |
| **RAM & Buses** | `TestAlignmentControl` | Control estricto de alineación natural en 2, 4 y 8 bytes (`MISALIGNED`), deshabilitación de chequeo para fetch de instrucciones variables |
| **RAM & Buses** | `TestMMIORouting` | Detección de `A[31:24] == 0xFF` (`MMIO`), ausencia de instanciación en RAM, detección de transferencias que invaden el espacio MMIO |
| **RAM & Buses** | `Test64BitAddressValidation` | Rechazo con `ADDR_FAULT` de direcciones mayores a 4 GiB (`A[63:32] != 0`) y direcciones negativas |
| **RAM & Buses** | `TestExceptionsAndConfiguration` | Lanzamiento de `InvalidAccessSizeError` ante tamaños no soportados y validación de potencias de 2 en el constructor |
| **Registros & ALU** | `PruebasBancoRegistros` | R0 cableado a cero, valores de reset, enmascarado a 64 bits, códigos reservados, avance del PC con longitud variable, posiciones de bits del SR, observadores de la GUI |
| **Registros & ALU** | `PruebasAritmetica` | Acarreo sin signo, desbordamiento con signo, préstamo en la resta, multiplicación de 64 bits bajos, división truncada hacia cero, división por cero |
| **Registros & ALU** | `PruebasLogicaYDesplazamientos` | AND/OR/XOR/NOT, construcción de `0x00200000` y `0xC0000000`, acarreo en desplazamientos, `ASR` frente a `SHR` en negativos, casos límite n = 0 y n ≥ 64 |
| **Registros & ALU** | `PruebasCMP` | Que no escriba el destino; banderas del trazado de Euclides |
| **Registros & ALU** | `PruebasIntegracion` | Reproduce los bucles del factorial y de Euclides del documento |
| **Cargador & Bits** | `TestManipulacionBits` | Lectura de bits 0-7, mutación aislada sin tocar bits vecinos ni bytes contiguos, conmutación XOR, formato string binario y validación de rangos |
| **Cargador & Bits** | `TestValidacionLimitesYMemoria` | Carga en área de usuario (0x00200000), rechazo de vectores/firmware (< 0x00200000), rechazo de invasión a Pila (>= 0xC0000000) y rechazo de direcciones > 4 GiB |
| **Cargador & Bits** | `TestCargaFormatos` | Carga de binarios planos (.bin), serialización/deserialización .e64 Big-Endian, reubicación dinámica de direcciones y parser de volcados en texto |
| **Cargador & Bits** | `TestContextoHardware` | Sincronización de registros tras la carga (PC=entry_point, SP=0xEFFFFFFF, SR=0x1, R0=0, R5=entry_point) y detención/reanudación de CPU |
| **Cargador & Bits** | `TestSubrutinaFirmware` | Transferencia de datos entre buffers emulando la subrutina en 0x00001000 con parámetros R1, R2, R3 y retorno en R5 |
| **FPU — FMUL** | `TestFMULEnigma64` | Tabla de 24 casos en hex, 300 casos aleatorios bit a bit contra el oráculo IEEE 754 de Python, conmutatividad, peor caso de ciclos y producto de 128 bits de `FPU_MUL128` (ver sección FMUL) |


Para correr solo las pruebas de memoria:

```bash
python -m unittest tests.test_memoria -v
```

Para correr solo un grupo:

```bash
python -m unittest tests.test_memoria.TestBigEndianAndBlockCrossing -v
python -m unittest tests.test_registros_alu.PruebasAritmetica -v
```

Para correr una sola prueba:

```bash
python -m unittest tests.test_memoria.TestAlignmentControl.test_misaligned_four_byte_access -v
python -m unittest tests.test_registros_alu.PruebasAritmetica.test_division_trunca_hacia_cero -v
```

## Nivel 3 — Panel gráfico

```bash
python main.py
```

Secuencia de comprobación manual:

| Acción | Resultado esperado |
|---|---|
| Cargar `R1` con `0x20`; `SHL` con inmediato 16 hacia `R1` | `R1 = 0x0000000000200000` |
| Cargar `R2`=3, `R3`=5; `SUB R4 ← R2 - R3` | `R4 = 0xFFFFFFFFFFFFFFFE`, decimal −2, banderas `N=1` y `C=1` |
| `CMP R2, R2` | Bandera `Z=1` y ningún registro cambia (la bitácora dice "sin escritura") |
| Cargar `R0` con cualquier valor | Sigue en cero; la bitácora reporta que ignoró la escritura |
| Pulsar `RESET` | `PC = 0`, `SP = 0x00000000EFFFFFFF` |

## Nivel 4 — Trazado del algoritmo del documento

```bash
python verificacion_manual.py
```

Reproduce el bucle del Algoritmo 1 (factorial de 5) usando únicamente el banco de
registros y la ALU. Debe imprimir cinco iteraciones con los acumuladores 5, 20, 60, 120,
120 y terminar en `0x0000000000000078`, exactamente los mismos valores del trazado
escrito a mano en la Tarea 9.

Lo relevante no es el resultado sino la condición de salida: el bucle **no** pregunta si
el contador llegó a cero, pregunta por la bandera Z que la ALU encendió sola al calcular
la resta. Es el mismo mecanismo de la instrucción `JNZ`.

---

# Unidad de Control (CPU) y Microarquitectura FSM

## Qué incluye

**`enigma64/cpu.py`** — Unidad de Control multiciclo, cola de prebúsqueda y microarquitectura completa de Enigma-64.

### 1. FSM de 5 Fases Síncronas
- **FETCH**: Carga y alineación de instrucciones desde RAM a través del `PrefetchBuffer`.
- **DECODE**: Decodificación de los 6 formatos de instrucción (F1 a F6, 1 a 5 bytes), resolución de registros fuente/destino e inmediatos con extensión de signo.
- **EXECUTE**: Ejecución de operaciones aritmético-lógicas mediante la `ALU`, evaluación de saltos condicionales (`JZ`, `JNZ`, `JN`, `JC`, `JV`, `JA`, etc.) y cálculo de direcciones efectivas.
- **MEMORY**: Accesos de lectura y escritura a `RAMMemory` y desvío al subsistema `MMIO`. Activación de la bandera de desalineación `M` en `SR` cuando se detecta un acceso desalineado.
- **WRITE-BACK**: Escritura en el banco de registros `BancoRegistros`, actualización de `PC`, puntero de pila `SP` y registro de estado `SR`.

### 2. Cola FIFO de Prebúsqueda (`PrefetchBuffer`)
- Búfer de 16 bytes que lee palabras alineadas de 64 bits y proporciona un flujo continuo de bytes decodificables, resolviendo de forma transparente el cruce de fronteras de palabra sin incurrir en fallos de alineación durante la fase de lectura de instrucciones de longitud variable.

### 3. Modos y Control de Pila
- Manejo de instrucciones de pila (`PUSH`, `POP`, `CALL`, `RET`) decrementando/incrementando de 8 en 8 bytes a partir de `SP_RESET` (`0x00000000EFFFFFFF`).
- Modos supervisor y usuario, soporte de instrucciones de control de interrupciones (`EI`, `DI`, `IRET`) y detención formal (`HLT`).

---

# Interconexión y Ciclo de Instrucción

El banco de registros y la ALU se conectan con la CPU y la memoria siguiendo el ciclo de instrucción multiciclo:

## Acceso a Memoria en el Ciclo de Instrucción

El subsistema de memoria expone la interfaz principal de buses mediante `RAMMemory`:

```python
from enigma64 import RAMMemory, STATUS_READY, STATUS_MISALIGNED, STATUS_MMIO, STATUS_ADDR_FAULT

ram = RAMMemory()

# --- FSM Fase FETCH ---
# Lectura de la instrucción apuntada por PC (puede desalinearse al ser longitud variable)
opcode_byte, status = ram.mem_read(banco.pc, size_bytes=1, check_alignment=False)
# Si la instrucción requiere bytes adicionales (inmediatos de 16, 32 o 64 bits):
inmediato, status = ram.mem_read(banco.pc + 1, size_bytes=4, check_alignment=False)

# --- FSM Fase MEMORY (LOAD / STORE) ---
# LOAD R1, [R2] -> MAR = banco.leer(R2)
dato_leido, status = ram.mem_read(mar, size_bytes=8)
if status == STATUS_READY:
    mdr = dato_leido
elif status == STATUS_MISALIGNED:
    banco.escribir_bandera("M", 1)  # La CPU activa la bandera M en el SR
elif status == STATUS_MMIO:
    # Desviar al bus de periféricos (pantalla/teclado MMIO)
    pass
elif status == STATUS_FALLO_DIR:
    # Disparar excepción por dirección > 4 GiB
    pass

# STORE [R2], R1 -> MAR = banco.leer(R2), MDR = banco.leer(R1)
_, status = ram.mem_write(mar, mdr, size_bytes=8)
```

Puntos clave de integración:
- El PC y los punteros apuntan a **bytes**, no a palabras. El MAR se carga con la dirección de 64 bits tal cual.
- El SP arranca en `0x00000000EFFFFFFF` (constante `SP_RESET`), dentro de la región de Pila del mapa de memoria. Las operaciones `PUSH`/`POP` decrementan/incrementan de 8 en 8 bytes.
- La validación de rango `A[63:32] == 0` y el desvío a `MMIO` viven exclusivamente en `RAMMemory`.
- Si `mem_read` o `mem_write` retornan `STATUS_MISALIGNED`, la Unidad de Control (FSM) es quien debe escribir la bandera `M` en el SR llamando a `banco.escribir_bandera("M", 1)`.

## Integración con la Interfaz Gráfica (GUI)

`PanelRegistros` es un `ttk.Frame` normal. Para incrustarlo en la ventana principal:

```python
from enigma64.gui.panel_registros import PanelRegistros

panel = PanelRegistros(ventana_principal, banco)
panel.pack(side="left", fill="y")
```

Se suscribe solo al banco, así que se refresca en cada cambio sin que la ventana tenga que
llamarlo. Si se prefiere pintar la tabla de otra forma, `banco.snapshot()` devuelve todo
en un diccionario con hexadecimal, decimal con signo y las siete banderas.

# Programas Oficiales y Algoritmos de Prueba

## Qué incluye

### 1. `enigma64/programas.py` y `programas/` — Binarios oficiales de la Tarea 9
- **Algoritmo 1: Factorial ($N!$)** en `0x00200000` (41 bytes). Calcula $5! = 120$ en `0x00201008`.
- **Algoritmo 2: Euclides ($MCD$)** en `0x00200100` (50 bytes). Calcula $\text{MCD}(48, 18) = 6$ en `0x00202010`.
- **Algoritmo 3: Sucesión de Fibonacci** en `0x00200200` (63 bytes). Genera $[0, 1, 1, 2, 3, 5, 8]$ secuencialmente en `0x00203000`–`0x00203030`.
- Formatos suministrados: `.bin` (binario crudo), `.hex` (volcado hexadecimal) y `.e64` (ejecutable estructurado con cabecera Magic `ENIG`).
- Script generador: `python scripts/generar_binarios.py`.

### 2. Suite de pruebas de validación formal (`tests/test_algoritmos.py`)
- 16 pruebas automatizadas que verifican la integridad byte a byte contra la Tarea 9, el respeto de fronteras de memoria, la carga en RAM mediante `CargadorEnigma`, la ejecución paso a paso y la ejecución sobre la `CPU` oficial de la máquina.

---

# Subsistema de Entrada/Salida Mapeada en Memoria (MMIO) y Periféricos

## Qué incluye

### 1. `enigma64/perifericos.py` — Controlador básico de pantalla y subsistema MMIO
- **Controlador básico de pantalla (Salida, Base `0xFF001000`):**
  - Mantiene un buffer de texto de pantalla/terminal emulada con cursor bidimensional (`cursor_fila`, `cursor_col`).
  - **`CTRL` (`+0x00`):** Comandos de control (`0x01`: limpiar pantalla y resetear cursor, `0x02`: reset de encendido, `0x03`: salto de línea, `0x04`: scroll).
  - **`STATUS` (`+0x08`):** Estado devuelto (`1 = READY` / Listo).
  - **`DATA` (`+0x10`):** Escribir un byte/código ASCII emite el carácter a la matriz de pantalla, gestionando saltos de línea (`\n`), retorno de carro (`\r`), backspace (`\b`), tabulador (`\t`) y scroll vertical automático.
  - **`ADDR` (`+0x18`):** Posición lineal del cursor en el buffer de texto (o dirección de visualización).
  - **`COUNT` (`+0x20`):** Total acumulado de caracteres emitidos a la pantalla.
  - Callbacks y suscripción de eventos para actualización reactiva en la GUI.
- **Gestor de Periféricos (`Perifericos` / `ControladoresMMIO`):**
  - Mapea los 5 dispositivos físicos de la Tarea 9 (Teclado `0xFF000000`, Pantalla `0xFF001000`, Disco `0xFF002000`, Red `0xFF003000`, Temporizador `0xFF004000`).
  - Conectado automáticamente en `enigma64.ui.servicios.adaptadores.AdaptadorMMIO`, reemplazando el andamio provisional (`es_provisional = False`).

### 2. Grilla visual interactiva de memoria RAM (`enigma64/ui/paneles/panel_memoria.py`)
- **Organización por 8 bancos de memoria (Tarea 9):**
  - Visualiza palabras de 64 bits divididas en sus 8 bancos físicos (`B0` a `B7` seleccionados por `A[2:0]`), reflejando la microarquitectura de la página 4 de la Tarea 9.
  - Cada celda de byte es interactiva: clic la selecciona, la resalta en ámbar Noctua y vincula el Inspector de Bits en vivo.
- **Inspector y Editor de Bits en vivo:**
  - Panel visual con 8 celdas/botones interactivos ($b_7 \dots b_0$).
  - **Conmutación en tiempo real:** hacer clic en cualquier bit conmuta su valor ($0 \leftrightarrow 1$) directamente en la RAM emulada y publica el evento en el bus.
  - Desglose y edición directa en Hexadecimal (`0xXX`), Decimal (con y sin signo), Binario (`0bXXXXXXXX`) y ASCII.
  - Accesos directos a regiones del mapa de memoria (Vectores `0x00000000`, Monitor `0x00001000`, Programas `0x00200000`, Datos `0x00201000`, Pila `0xEFFFFFF0`, MMIO `0xFF001000`).

### 3. Terminal CRT emulada en MMIO (`enigma64/ui/paneles/panel_mmio.py`)
- Visualizador estilo terminal fósforo verde CRT que refleja en tiempo real el buffer del controlador de pantalla.
- Controles interactivos para emitir caracteres/cadenas a `DATA` (`0xFF001010`), enviar comandos a `CTRL` (`0xFF001000`), limpiar pantalla y botón de demostración rápida.

---

# FPU: Multiplicación de Punto Flotante (FMUL)

## Qué incluye

- **`enigma64/fmul.s`** — Subrutina `FMUL` en ensamblador de Enigma-64: `R5 = R1 × R2` en IEEE 754 binary64, con redondeo al par más cercano, subnormales en entrada y salida, y casos especiales (NaN, ±Inf, ±0, 0 × Inf). Incluye las auxiliares `FPU_MUL128` (producto 64 × 64 → 128 bits con cuatro productos parciales de 32 bits, porque `MUL` solo conserva los 64 bits bajos) y `FPU_NORMALIZAR_SUBNORMAL`. Reutiliza `FPU_DESEMPAQUETAR` y `FPU_EMPAQUETAR` de `fpu.s`.
- **`enigma64/fpu.py`** — Ensambla `fpu.s` + `fmul.s` como una sola unidad y expone `EmuladorFPUEnigma64.multiplicar()` (devuelve `float`) y `multiplicar_bits()` (devuelve el patrón de 64 bits).
- **`docs/informe_integrante2_fmul.md`** — Diseño, asignación de registros, oráculo y limitaciones.

## Pruebas (`tests/test_fmul.py`)

Cada prueba ejecuta `FMUL` sobre la CPU oficial y compara el resultado bit a bit contra el oráculo de Python (`struct` + `*`, que es IEEE 754 binary64 con redondeo al par más cercano).

| Prueba | Qué verifica |
|---|---|
| `test_tabla_casos` | 24 casos con entradas y salida esperada en hexadecimal (tabla siguiente) |
| `test_tabla_concuerda_con_oraculo` | Que los valores esperados de la tabla coinciden con el oráculo (NaN se compara con `math.isnan`) |
| `test_multiplicar_flotantes` | La interfaz con `float`: `6.0 × 7.0 = 42.0`, `−0.75 × 8.0 = −6.0`, `0.1 × 3.0` |
| `test_conmutatividad` | `A × B == B × A` en normales, subnormales y extremos |
| `test_aleatorio_contra_oraculo` | 300 casos con semilla fija: bits aleatorios, valores cercanos a 1, zona de subdesbordamiento y subnormal × grande |
| `test_ciclos_peor_caso` | Subnormal × subnormal termina en menos de 10 000 ciclos de la FSM |
| `test_mul128` | `FPU_MUL128` entrega el producto exacto de 128 bits en `R5:R4` |

Casos de `test_tabla_casos`:

| # | Caso | A | B | Esperado |
|:-:|---|---|---|---|
| 1 | normal × normal: 1.5 × 2.5 | `3FF8000000000000` | `4004000000000000` | `400E000000000000` |
| 2 | signo: −3.0 × 4.0 | `C008000000000000` | `4010000000000000` | `C028000000000000` |
| 3 | signo: −2.0 × −0.5 | `C000000000000000` | `BFE0000000000000` | `3FF0000000000000` |
| 4 | identidad: 1.0 × π | `3FF0000000000000` | `400921FB54442D18` | `400921FB54442D18` |
| 5 | potencias de 2: 2^10 × 2^−3 | `4090000000000000` | `3FC0000000000000` | `4060000000000000` |
| 6 | normalización (producto ≥ 2): 1.75 × 1.75 | `3FFC000000000000` | `3FFC000000000000` | `4008800000000000` |
| 7 | redondeo inexacto: 0.1 × 0.2 | `3FB999999999999A` | `3FC999999999999A` | `3F947AE147AE147C` |
| 8 | +0 × 5.0 | `0000000000000000` | `4014000000000000` | `0000000000000000` |
| 9 | −0 × 5.0 | `8000000000000000` | `4014000000000000` | `8000000000000000` |
| 10 | +Inf × −2.0 | `7FF0000000000000` | `C000000000000000` | `FFF0000000000000` |
| 11 | −Inf × −Inf | `FFF0000000000000` | `FFF0000000000000` | `7FF0000000000000` |
| 12 | 0 × Inf (operación inválida) | `0000000000000000` | `7FF0000000000000` | `7FF8000000000000` |
| 13 | NaN × 1.0 (propaga carga útil) | `7FF8000000000123` | `3FF0000000000000` | `7FF8000000000123` |
| 14 | sNaN × 1.0 (se silencia) | `7FF0000000000001` | `3FF0000000000000` | `7FF8000000000001` |
| 15 | overflow: MAX × 2.0 | `7FEFFFFFFFFFFFFF` | `4000000000000000` | `7FF0000000000000` |
| 16 | overflow: 1e200 × −1e200 | `6974E718D7D7625A` | `E974E718D7D7625A` | `FFF0000000000000` |
| 17 | underflow a subnormal: 2^−1022 × 0.5 | `0010000000000000` | `3FE0000000000000` | `0008000000000000` |
| 18 | underflow a cero: 1e−200 × 1e−200 | `16687E92154EF7AC` | `16687E92154EF7AC` | `0000000000000000` |
| 19 | subnormal × normal: 2^−1074 × 2^60 | `0000000000000001` | `43B0000000000000` | `0090000000000000` |
| 20 | empate al par, sube: (1+2^−52) × 1.5 | `3FF0000000000001` | `3FF8000000000000` | `3FF8000000000002` |
| 21 | empate al par, baja: (1+3·2^−52) × 1.5 | `3FF0000000000003` | `3FF8000000000000` | `3FF8000000000004` |
| 22 | empate subnormal: 2^−1074 × 0.5 | `0000000000000001` | `3FE0000000000000` | `0000000000000000` |
| 23 | empate subnormal: 3·2^−1074 × 0.5 | `0000000000000003` | `3FE0000000000000` | `0000000000000002` |
| 24 | subnormal que redondea al menor normal | `000FFFFFFFFFFFFF` | `3FF0000000000001` | `0010000000000000` |

En el caso 12 el oráculo de Python (x86) da `FFF8000000000000`. Los dos son NaN silenciosos: IEEE 754 no fija el signo de un NaN, y FMUL devuelve el NaN canónico positivo.

Para correr solo estas pruebas:

```bash
python -m pytest tests/test_fmul.py -v
# o con unittest estándar
python -m unittest tests.test_fmul -v
```

---

# FPU: Panel Interactivo y Visor IEEE 754 (Integrante 5)

**`enigma64/ui/paneles/panel_fpu.py`** — Pestaña **FPU** de la interfaz. También se abre sola:

```bash
python -m enigma64.ui.paneles.panel_fpu
```

- **Calculadora reactiva.** No hay botón de ejecutar: al escribir un operando o cambiar de operación, la rutina vuelve a correr. Los operandos se escriben en decimal (`10.5`, `1e-308`, `inf`, `nan`) o como patrón IEEE 754 (`0x4025000000000000`).
- **Las cuentas las hace la biblioteca del equipo.** Cada operación entra por la tabla `FPU_VECTORES` (`VEC_FADD`, `VEC_FSUB`, `VEC_FMUL`, `VEC_FDIV`, `VEC_FCMP`, `VEC_INT_TO_FLOAT`, `VEC_FLOAT_TO_INT`) y corre sobre la CPU de Enigma-64. Se muestran los ciclos de reloj consumidos.
- **Contraste con la norma.** Junto al resultado aparece lo que responde el IEEE 754 del anfitrión y una insignia que dice si coinciden.
- **Visor IEEE 754.** Desglosa el operando A, el B o el resultado en el bit 63 de signo, los 11 bits de exponente, los 52 de mantisa y el bit implícito, usando `FPU_DESEMPAQUETAR`. Las celdas de los operandos son pulsables.
- **Entregas pendientes.** `FSQRT` (Integrante 6) figura en el selector como pendiente y se conecta sola cuando su etiqueta aparezca en la biblioteca; el oráculo, la constante de Brun y la batería de pruebas (Integrantes 6 y 7) se marcan en la hoja de ruta del panel.

La capa de servicios (`AdaptadorFPU` en `enigma64/ui/servicios/adaptadores.py`) es la única que importa `enigma64.fpu`; el módulo de la FPU no se modifica.

---

# FPU: Conversiones de Formato y Mesa de Entrada Canónica (Integrante 4)

## Qué incluye

- **`enigma64/fconv.s`** — Subrutinas en ensamblador de Enigma-64:
  - `FPU_VECTORES`: Mesa de entrada / tabla de salto canónica fija de 7 entradas (`JMP` de 5 bytes en saltos fijos de `+0x05`), permitiendo a los programas de usuario invocar cualquier servicio de la FPU de forma canónica desacoplada de la implementación interna.
  - `FPU_INT_TO_FLOAT` (`INT64_TO_FLOAT64`): Conversión de enteros de 64 bits con signo en complemento a dos (R1) a formato IEEE 754 de doble precisión binary64 (R5). Gestiona el caso cero, el caso crítico `INT64_MIN` ($-2^{63}$), normalización y redondeo al par más cercano (*roundTiesToEven*) para enteros que exceden 53 bits de significando.
  - `FPU_FLOAT_TO_INT` (`FLOAT64_TO_INT64`): Conversión de flotantes IEEE 754 binary64 (R1) a enteros de 64 bits con signo (R5), implementando truncamiento hacia cero ($[-1.0, 1.0) \to 0$), soporte para enteros de hasta 63 bits y el límite exacto $-2^{63}$.
- **`enigma64/fpu.py`** — Integración en `EmuladorFPUEnigma64` con métodos `int_to_float()`, `int_to_float_bits()`, `float_to_int()`, `ejecutar_vector()` y constantes de vector `VECTOR_*`.
- **`programas/fpu_lib.s`**, **`fpu_lib.bin`** (1425 bytes), **`fpu_lib.hex`** — Biblioteca binaria unificada completa que compila la tabla `FPU_VECTORES`, `fconv.s`, `fpu.s` y `fmul.s` en un único módulo distribuible.
- **`docs/informe_integrante4_conversiones_enlace.md`** — Informe técnico completo sobre diseño, microarquitectura, convenciones ABI y pruebas.

## Pruebas (`tests/test_fconv.py`)

19 pruebas automatizadas (111 aserciones directas) que validan el comportamiento contra IEEE 754 y el oráculo nativo:

| Prueba | Qué verifica |
|---|---|
| `test_int_to_float_cero` | Conversión de `0` a `+0.0` (`0x0000000000000000`) |
| `test_int_to_float_basicos` | Enteros pequeños positivos y negativos ($\pm 1, \pm 2, \dots, \pm 100$) |
| `test_int_to_float_potencias_de_dos` | Potencias exactas de 2 ($2^0, 2^1, \dots, 2^{62}$, $-2^{63}$) |
| `test_int_to_float_grandes_exactos` | Enteros grandes en el rango exacto $[2^{52}, 2^{53}]$ |
| `test_int_to_float_redondeo_ties_to_even` | Redondeo al par más cercano para enteros $> 2^{53}$ (verificación de bits G, R, S) |
| `test_int_to_float_limites` | Extremos `INT64_MAX` ($2^{63}-1$) y `INT64_MIN` ($-2^{63}$) |
| `test_float_to_int_truncamiento` | Truncamiento hacia cero ($1.99 \to 1$, $-1.99 \to -1$, $0.75 \to 0$) |
| `test_float_to_int_extremos` | Ceros con signo, números subnormales, $\pm\infty$ y NaN saturando a 0 |
| `test_float_to_int_limite_int64_min` | Conversión exacta de $-9223372036854775808.0 \to -2^{63}$ |
| `test_identidad_int_float_int` | Preservación exacta de la identidad $\text{int}(\text{float}(x)) == x$ en $[-2^{53}, 2^{53}]$ |
| `test_mesa_vectores_offsets` | Estructura y distancias exactas de 5 bytes en `FPU_VECTORES` |
| `test_mesa_vectores_ejecucion` | Invocación de rutinas saltando a través de los vectores canónicos |

Para correr solo estas pruebas:

```bash
python -m pytest tests/test_fconv.py -v
```

---

# Flujo de trabajo con Git

Nunca se trabaja directo sobre `main`. `main` debe estar siempre ejecutable.

```bash
# empezar una tarea
git checkout main
git pull
git checkout -b feat/mi-modulo

# al terminar
git add <archivos>
git commit -m "feat(modulo): descripción breve"
git push -u origin feat/mi-modulo
```

Luego se abre un Pull Request para revisión e integración de cambios.

Antes de cada commit, verificar que las pruebas siguen pasando:

```bash
# Suite completa (424 pruebas: unitarias y GUI)
python -m pytest

# O mediante unittest estándar (182 pruebas de hardware sin GUI)
python -m unittest discover -s tests
```
