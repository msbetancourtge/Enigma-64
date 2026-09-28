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

## Integrantes

| # | Nombre | Módulo |
|---|---|---|
| 1 | Juan Sebastian Umaña Camacho | RAM & Buses |
| 2 | Tomas Felipe Garzón Gómez | Registros & ALU |
| 3 | Michael Stiven Betancourt Gelves | CPU & FSM |
| 4 | Deibyd Santiago Barragán Gaitán | Cargador & Manipulador de Bits |
| 5 | Maicol Sebastian Olarte Ramirez | GUI Principal (Tkinter) |
| 6 | Juan Luis Vergara Novoa | Visor/Editor RAM & MMIO |
| 7 | Alejandro Argüello Muñoz | Algoritmos & Tests |

## Estructura del repositorio

Leyenda de estado: **[OK]** implementado y probado · **[--]** pendiente

```
Enigma-64/
├── .gitignore
├── LICENSE
├── README.md
├── main.py                        [OK] punto de entrada: lanza la GUI
├── verificacion_manual.py         [OK] traza el factorial usando solo registros y ALU
├── enigma64/                           el paquete (todo importable)
│   ├── __init__.py                [OK] exporta el contrato público
│   ├── registros.py               [OK] Integrante 2: banco de registros
│   ├── alu.py                     [OK] Integrante 2: ALU de 64 bits
│   ├── memoria.py                 [OK] Integrante 1: RAM y buses
│   ├── cpu.py                     [OK] Integrante 3: FSM, prebúsqueda y microarquitectura
│   ├── cargador.py                [OK] Integrante 4: cargador y manipulación bit a bit
│   ├── perifericos.py             [OK] Integrante 6: controlador básico de pantalla y MMIO
│   ├── programas.py               [OK] Integrante 7: definición binaria de programas de Tarea 9
│   ├── ui/
│   │   ├── shell/ventana.py       [OK] Integrante 5: shell y cuaderno de módulos
│   │   ├── paneles/panel_memoria.py [OK] Integrante 1 & 6: Grilla interactiva y editor de bits
│   │   └── paneles/panel_mmio.py  [OK] Integrante 6: Terminal CRT y registros MMIO
│   └── gui/
│       ├── __init__.py            [OK]
│       └── panel_registros.py     [OK] Integrante 2: panel en vivo + banco de pruebas
├── programas/                     [OK] Integrante 7: archivos ejecutables (.bin, .hex, .e64)
├── scripts/                       [OK] utilitarios de generación binaria y reportes
└── tests/
    ├── test_registros_alu.py      [OK] Integrante 2: 38 pruebas
    ├── test_memoria.py            [OK] Integrante 1: 22 pruebas
    ├── test_cpu.py                [OK] Integrante 3: 16 pruebas
    ├── test_cargador.py           [OK] Integrante 4: 21 pruebas
    ├── test_perifericos.py        [OK] Integrante 6: 16 pruebas
    ├── test_algoritmos.py         [OK] Integrante 7: 16 pruebas
    ├── test_ui_aislamiento.py     [OK] Integrante 5: 29 pruebas AST
    ├── test_ui_modulos_nuevos.py  [OK] Integrante 5: 42 pruebas
    ├── test_ui_nucleo.py          [OK] Integrante 5: 52 pruebas
    ├── test_ui_paneles.py         [OK] Integrante 5: 59 pruebas GUI
    └── test_ui_visor_ram_mmio.py  [OK] Integrante 6: 8 pruebas
```

## Requisitos

- Python 3.10 o superior
- Tkinter (viene incluido con el instalador oficial de Python en Windows)

No hay dependencias externas: todo el emulador usa solo la biblioteca estándar.

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

# Módulo implementado: RAM & Buses (Integrante 1)

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
| `"MMIO"` | Dirección ubicada en `0xFF000000` - `0xFFFFFFFF` | La solicitud se desvía al bus de controladores de periféricos (Integrante 6). |
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

# Módulo implementado: Registros & ALU (Integrante 2)

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
| `DIV` con divisor 0 | Lanza `DivisionPorCero` | Pendiente: la Unidad de Control debe decidir si detiene con `HLT` o levanta un bit de excepción en el SR |

## Puntos abiertos de la Tarea 9

Dos inconsistencias detectadas al implementar. Pendientes de decisión del grupo:

**Valor de reset del SR.** El documento dice `0x0000000000000001`, que enciende el bit 0,
es decir **Z = 1**. Lo más probable es que se quisiera el bit **S** (supervisor, bit 6),
que sería `0x40`. Con `S = 0` la máquina arranca en modo usuario y no podría acceder al
área de trabajo del cargador en `0x00100000`, marcada como supervisor-only en el mapa de
memoria. El código usa el valor documentado por defecto; la corrección está disponible en
la constante `SR_RESET_SUPERVISOR`.

**Conteo de registros de propósito general.** La sección "Codificación de los Registros"
dice "cinco registros de propósito general identificados desde R0 hasta R4", pero R0 está
cableado a cero y por definición no es de propósito general. Son cuatro: R1 a R4.

---

# Módulo implementado: Cargador & Manipulador de Bits (Integrante 4)

## Qué incluye

**`enigma64/cargador.py`** — Submódulo del Cargador, Manipulador de Memoria Bit a Bit y Firmware (código 100% en Python estándar, sin dependencias externas).

- **Manipulación directa de bits y bytes en RAM (Mandato Tarea 10 - Punto 2):**
  - `leer_bit(ram, direccion, bit_index)`: Lee un bit individual (0 a 7, donde bit 0 es LSB y bit 7 es MSB) en cualquier celda física accesible de la RAM.
  - `escribir_bit(ram, direccion, bit_index, valor)`: Modifica atómicamente un único bit (0 o 1) mediante máscaras (`|` o `& ~`) sin alterar los 7 bits restantes del byte ni celdas contiguas.
  - `conmutar_bit(ram, direccion, bit_index)`: Invierte el bit indicado mediante máscara XOR (`^`).
  - `byte_a_cadena_bits(ram, direccion)`: Genera la cadena de 8 bits (ej. `'10110001'`) formateada de MSB a LSB, lista para la grilla interactiva de edición de memoria en la GUI (Integrante 6).
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

# Módulo implementado: CPU & Unidad de Control FSM (Integrante 3)

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

# Integración y Contratos de Hardware

El banco de registros y la ALU se conectan con la CPU y la memoria siguiendo el ciclo de instrucción multiciclo:

## Contrato con el Integrante 1 (RAM & Buses)

El subsistema de memoria expone el contrato principal de buses mediante `MemoriaRAM`:

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
    # Desviar al bus de periféricos (pantalla/teclado de Integrante 6)
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
- La validación de rango `A[63:32] == 0` y el desvío a `MMIO` viven exclusivamente en `MemoriaRAM`.
- Si `mem_read` o `mem_write` retornan `STATUS_MISALIGNED`, la Unidad de Control (FSM) es quien debe escribir la bandera `M` en el SR llamando a `banco.escribir_bandera("M", 1)`.

## Contrato con el Integrante 5 (GUI Principal)

`PanelRegistros` es un `ttk.Frame` normal. Para incrustarlo en la ventana principal:

```python
from enigma64.gui.panel_registros import PanelRegistros

panel = PanelRegistros(ventana_principal, banco)
panel.pack(side="left", fill="y")
```

Se suscribe solo al banco, así que se refresca en cada cambio sin que la ventana tenga que
llamarlo. Si se prefiere pintar la tabla de otra forma, `banco.snapshot()` devuelve todo
en un diccionario con hexadecimal, decimal con signo y las siete banderas.

# Módulo implementado: Algoritmos & Tests (Integrante 7)

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

# Módulo implementado: Visor/Editor RAM & MMIO (Integrante 6)

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

Luego se abre un Pull Request y otro integrante lo revisa.

**Regla de propiedad de archivos:** cada integrante edita únicamente los archivos marcados
con su número en la estructura de arriba. Así Git no genera conflictos de merge aunque
todos trabajen en la misma carpeta.

Antes de cada commit, verificar que las pruebas siguen pasando:

```bash
# Suite completa (319 pruebas: unitarias y GUI)
python -m pytest

# O mediante unittest estándar (137 pruebas de hardware sin GUI)
python -m unittest discover -s tests
```
