# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2
**Tarea 27:** Traductor de ensamblador CacaoCore-64 → Enigma-64 (LEX / `ply.lex`)  
**Documento Técnico — Registros y ALU**  
**Autor:** Tomás Garzón (Integrante 2)

---

## 1. Alcance

Esta parte traduce los **registros** de CacaoCore-64 al banco de Enigma-64 y las **operaciones de la ALU** de CacaoCore-64 a las 16 operaciones de la ALU de Enigma-64. El acceso a memoria (LOAD/STORE, expansión de direcciones y alineación) es del Integrante 1 (`spl/traductor/memoria.py`) y aquí solo se reutiliza.

| Archivo | Contenido |
| :--- | :--- |
| `spl/traductor/registros.py` | Tabla de asignación, `mapear_registro(n)`, derrames (`emitir_load` / `emitir_store`) |
| `spl/traductor/alu.py` | Definiciones y reglas LEX de las instrucciones ALU; sus acciones emiten el código Enigma-64 |
| `spl/traductor/traductor.py` | Driver mínimo: lee un `.asm` de CacaoCore y escribe el de Enigma-64; `--verificar` y `--ejecutar` |
| `spl/traductor/__main__.py` | `python -m spl.traductor entrada.asm -o salida.asm` |
| `spl/traductor/ejemplos/` | Programas de CacaoCore (Euclides ×2, burbuja, máximo ×2), `prueba_alu.asm` y dos salidas traducidas |
| `tests/test_spl/traductor/test_traductor_registros_alu.py` | 244 pruebas, entre ellas una comparación diferencial contra un modelo de CacaoCore |

```bash
python -m spl.traductor spl/traductor/ejemplos/euclides.asm -o euclides_enigma.asm --ejecutar
python -m pytest tests/test_spl/traductor/
```

## 2. Decisiones sobre la sintaxis de Enigma-64

No hubo que suponer la sintaxis: se tomó de `enigma64/ensamblador.py`, `enigma64/cpu.py` y `enigma64/alu.py`.

| Punto | Lo que hay en Enigma-64 |
| :--- | :--- |
| Registros | `R0` (cableado a 0), `R1`–`R4`, `R5` = RV, `R6` = SP, `R7` = BP. `PC` (código 8) y `SR` (código 9) también caben en el campo de registro de 4 bits. |
| Formato R-R | `ADD Rd, Rs1, Rs2` (tres operandos), igual para SUB MUL DIV AND OR XOR |
| Formato inmediato | `ADDI Rd, Rs1, imm16` y lo mismo SUBI, SHL, SHR, ASR. El inmediato es de 16 bits **con extensión de signo** (−32768…32767). |
| Unarias | `INC Rd`, `DEC Rd`, `NOT Rd` (Rd = op Rd) |
| Comparación | `CMP Rs1, Rs2`: solo banderas |
| Memoria | `LOAD Rd, [Rb]`, `LOAD Rd, [Rb + off]`; las palabras deben estar alineadas a 8 bytes |
| Saltos | `JZ JNZ JC JNC JN JP JV JNV` (relativos, 16 bits) y `JMP`/`CALL` absolutos. `JP` salta si N = 0 **y** Z = 0. |
| Banderas | MUL/DIV/AND/OR/XOR/NOT escriben Z y N; INC/DEC escriben Z N V; ADD/SUB/CMP escriben Z N C V |
| Comentarios y etiquetas | `;` hasta fin de línea; `NOMBRE:` |
| Modo usuario | Al arrancar, S = 0: no se puede acceder por debajo de `0x00200000`. El código va en `0x00200000` y los datos en `0x00201000`. |

Las decisiones que sí tomé yo:

| Punto | Decisión |
| :--- | :--- |
| Temporales | `R4` = TMP1 (dato / primer operando derramado) y `R5` = TMP2 (segundo operando, inmediatos y direcciones del Integrante 1) |
| Área de derrame | `0x00300000`, apuntada por BP (`R7`). Una ranura de 8 bytes por registro: `[R7 + 8·k]`. |
| Sección `.data` | Enigma-64 no tiene directivas de datos, así que el prólogo guarda cada variable con `ADDI/SHL` + `STORE` en la dirección que asigna el Integrante 1 |
| Preservar banderas | `PUSH SR` / `POP SR` (el SR tiene código 9, así que PUSH/POP lo aceptan como cualquier registro; equivale a PUSHF/POPF) |

## 3. Semántica real de CacaoCore-64

Revisé `src/processor/alu.py`, `microinstructions_mixin.py` e `instruction_map.py` de CacaoCore. Hay varias diferencias con el resumen del enunciado, y el traductor sigue la semántica real:

| Hallazgo en CacaoCore | Consecuencia en el traductor |
| :--- | :--- |
| La ALU es de **acumulador**: `add_ra` hace `alu.add(op1, op2)` (el resultado queda en R15) y luego `op1 = R15`. Toda operación ALU de dos operandos, más INC/DEC/NEG/NOT/SHL/SHR/LEA, deja el resultado **también en ACC**. | Se reproduce ese efecto lateral. Si el programa nunca lee R15, se omite y el ACC ni siquiera ocupa un registro (§5). |
| `DIV Rx, Ry` (`div_ra`): Rx = ACC = cociente y **Ry = residuo**. El Euclides de ejemplo depende de esto. `DIV Rx, imm/[m]` y `DIV Ry` (forma de acumulador) descartan el residuo. | Enigma-64 solo calcula el cociente, así que el residuo se obtiene como r = x − (x / y)·y. |
| `CMPZ Rx` es `cmp_ra(0, Rx)`: banderas de **0 − Rx** | `CMP R0, x`. El enunciado proponía `CMP Rx, R0`: Z da igual, pero N cambia. |
| `SHR` desplaza el valor **con signo** (`>>` de Python sobre `signed=True`) | `ASR` |
| `JG/JL/JGE/JLE` (`j_comparacion`) solo miran N y Z | JG = `JP`, JL = `JN`, JGE = `JP`+`JZ`, JLE = `JN`+`JZ` (Z = 1 implica N = 0) |
| `MOV`, `SWAP`, `ROL`/`ROR` y `LEA` no llaman a la ALU: no tocan banderas | Si las banderas están vivas, su traducción no puede alterarlas (§6) |
| Errores de la implementación de referencia: `neg()` está vacía; `not_r` no escribe el registro; `rol_*` apunta a `ror_*`; `ror_ri` rota en 8 bits; `test_ra` copia el ACC viejo en el operando | Se sigue la semántica **documentada** de la ISA (NEG Rx = −Rx; NOT Rx = ~Rx; rotaciones de 64 bits; TEST solo banderas) |

## 4. Tabla de asignación de registros

CacaoCore-64 tiene 16 registros y Enigma-64 solo 7 escribibles. Los papeles fijos son:

| Enigma-64 | Papel en el código traducido | Justificación |
| :--- | :--- | :--- |
| `R0` | Constante 0, **nunca** recibe un registro de CacaoCore | Está cableado a cero: el R0 de propósito general de CacaoCore perdería todas sus escrituras. A cambio, sirve de operando cero: `NEG` → `SUB x, R0, x`, `CMPZ` → `CMP R0, x`, `MOV` → `ADD d, s, R0`, `CMP Rx, 0` → `CMP x, R0`. |
| `R1`, `R2`, `R3` | Los tres registros de CacaoCore **más usados** por el programa | El uso se cuenta en una pasada previa, y cada uso dentro de un bucle (detectado por saltos hacia atrás) pesa ×10 por nivel de anidamiento. |
| `R4` (TMP1) | Temporal de datos | Operando 1 o resultado derramado; valor de los almacenamientos de inmediatos |
| `R5` (TMP2) | Temporal de operando y dirección | Segundo operando, inmediatos que no caben en 16 bits, direcciones `ADDI+SHL+ADDI` del Integrante 1 |
| `R6` (SP) | Recibe `R13` (SP) de CacaoCore | PUSH/POP/CALL/RET de ambas máquinas usan la misma pila, y además la usan `SWAP` y `PUSH SR` |
| `R7` (BP) | Base del área de derrame | Con base en registro, cada acceso es un solo `LOAD`/`STORE [R7 + 8k]`, que **no altera banderas**. Si el programa usa 4 registros o menos, R7 se usa como cuarto residente. |
| memoria | Los demás registros (derrame) | `emitir_load(reg, ranura)` / `emitir_store(reg, ranura)`; el Integrante 1 puede inyectar su propia rutina |

Para Euclides la tabla calculada queda así (es la cabecera que imprime el traductor):

| CacaoCore | Enigma-64 | Peso |
| :--- | :--- | :--- |
| R2 | R1 | 401 (4 usos en el bucle interno ×100) |
| R0 | R2 | 322 |
| R1 | R3 | 223 |
| R3, R9, R10, R11, R12 | `[R7]`, `[R7+8]`, `[R7+16]`, `[R7+24]`, `[R7+32]` | 200, 20, 1, 1, 1 |
| R13 (SP) | R6 | fijo |
| R15 (ACC) | — | el programa nunca lo lee |

`TablaRegistros.por_defecto()` y la función de módulo `mapear_registro(n)` dan una tabla estática (R0→R1, R1→R2, R2→R3, R13→R6, resto derramado) para quien no haya analizado un programa.

## 5. Tabla de traducción de instrucciones

Notación: `x`, `y` = registro de Enigma-64 donde vive Rx, Ry; `A` = el del ACC. Si un registro está derramado, se carga antes en TMP1/TMP2 con `LOAD Tn, [R7+8k]` y se guarda después con `STORE`. Todas las secuencias usan solo las 16 operaciones de la ALU más LOAD/STORE/PUSH/POP.

| Forma CacaoCore | Secuencia Enigma-64 | Observaciones (banderas, temporales) |
| :--- | :--- | :--- |
| `ADD Rx, Ry` | `ADD x, x, y` | Z N C V. Si el ACC es observable y no es fuente, antes se emite `ADD A, x, y`: la operación se calcula dos veces para que las banderas finales sean las de la operación real. |
| `SUB Rx, Ry` | `SUB x, x, y` | igual que ADD |
| `MUL Rx, Ry` | `MUL x, x, y` | Z N |
| `AND`/`OR`/`XOR Rx, Ry` | `AND x, x, y` | Z N. CacaoCore limpia C y V; Enigma-64 no las toca. |
| `ADD Rx, imm` (imm16) | `ADDI x, x, imm` | Si imm no cabe en 16 bits: `cargar_constante(TMP2)` + `ADD x, x, TMP2` |
| `SUB Rx, imm` (imm16) | `SUBI x, x, imm` | igual |
| `MUL`/`DIV`/`AND`/`OR`/`XOR Rx, imm` | `cargar_constante(TMP2, imm)`<br>`OP x, x, TMP2` | Enigma-64 no tiene esas formas inmediatas. imm = 0 se reemplaza por `R0`. |
| `OP Rx, [a]` / `OP Rx, 0x…` | `ADDI TMP2, R0, hi`<br>`SHL TMP2, TMP2, 16`<br>`ADDI TMP2, TMP2, lo`<br>`LOAD TMP2, [TMP2]`<br>`OP x, x, TMP2` | Dirección con las rutinas del Integrante 1 (`obtener_direccion_variable`, `mapear_direccion`, `generar_secuencia_direccion`) |
| `OP Rx, [Ry]` | `LOAD TMP2, [y]`<br>`OP x, x, TMP2` | TMP2 |
| `OP Ry` / `OP imm` / `OP [m]` (ACC implícito) | `OP A, A, y` | Se vuelve explícita sobre el registro del ACC |
| `DIV Rx, Ry` | `DIV TMP1, x, y`<br>`MUL TMP2, TMP1, y`<br>`SUB y, x, TMP2`<br>`ADD x, TMP1, R0` | Rx = cociente, Ry = residuo. El `ADD` final deja Z y N del cociente con C = V = 0, como en CacaoCore. Si Rx está derramado: `LOAD y, [ranura x]` + `SUB y, y, TMP2` (sin temporal extra). Si los dos están derramados, x se recupera de su ranura y q se guarda en la pila. |
| `DIV Rx, imm/[m]`, `DIV Ry` | `DIV x, x, v` | Sin residuo (`div_rm`, `div_a`) |
| `INC Rx` / `DEC Rx` | `INC x` / `DEC x` | Z N V; C no cambia |
| `NEG Rx` | `SUB x, R0, x` | Aprovecha R0 = 0 |
| `NOT Rx` | `NOT x` | Z N |
| `INC`/`DEC`/`NEG`/`NOT [m]` | dirección en TMP2<br>`LOAD TMP1, [TMP2]`<br>`op TMP1`<br>`STORE TMP1, [TMP2]` | `[m]` y ACC reciben el resultado |
| `CMP Rx, Ry` / `CMP Rx, imm` | `CMP x, y` / `CMP x, TMP2` | `CMP Rx, 0` → `CMP x, R0` |
| `CMPZ Rx` / `CMPZ [m]` | `CMP R0, x` | Banderas de 0 − Rx (`cmpz_r`) |
| `TEST Rx, Ry` | `AND TMP1, x, y` | Rx no se destruye; Z N |
| `SHL Rx, n` | `SHL x, x, n` | Z N C |
| `SHR Rx, n` | `ASR x, x, n` | SHR de CacaoCore es aritmético |
| `SHL n` / `SHR n` | `SHL A, A, n` / `ASR A, A, n` | Desplazan el ACC |
| `ROL Rx, n` | `SHR TMP2, x, 64−n`<br>`SHL x, x, n`<br>`OR x, x, TMP2` | Rotación de 64 bits; n se toma módulo 64 (si da 0, no se emite nada). Como no debe tocar banderas, se envuelve en `PUSH SR`/`POP SR` si están vivas. |
| `ROR Rx, n` | `SHL TMP2, x, 64−n`<br>`SHR x, x, n`<br>`OR x, x, TMP2` | igual que ROL |
| `SWAP Rx, Ry` | `PUSH x`<br>`PUSH y`<br>`POP x`<br>`POP y` | No necesita temporal, no toca banderas y funciona con Rx = Ry. Los tres XOR del enunciado ponen el registro en 0 cuando Rx = Ry y cambian las banderas. |
| `SWAP Rx` | igual, con `y = A` | |
| `MOVx Rx, Ry` | `ADD x, y, R0`, o `PUSH y` + `POP x` si las banderas están vivas | Si un registro está derramado basta un `LOAD`/`STORE` directo |
| `MOVx Rx, imm` / `LOADx Rx, imm` / `LOADx imm` | `cargar_constante(x, imm)` | Hasta 64 bits con ADDI/SHL. `MOV Rx, 0` con Rx derramado → `STORE R0, [R7+8k]`. |
| `STOREx Rx` | Rx = ACC (como MOV) | `store_r` |
| `FPADD`… (FPU) | `; [FPU sin traducir] …` | Aviso; no es parte de este trabajo |
| `JG`/`JL`/`JGE`/`JLE`/`JS`/`JNS`/`JO`/`JNO` | `JP` / `JN` / `JP`+`JZ` / `JN`+`JZ` / `JN` / `JP`+`JZ` / `JV` / `JNV` | Soporte mínimo en `traductor.py` |
| `INTR n` | — | Aviso: Enigma-64 no tiene interrupción de E/S y el MMIO no está conectado a la CPU, así que el dato queda en memoria |

`cargar_constante(reg, v)` parte el valor en trozos de 16 bits de arriba hacia abajo: `hi = (v + 0x8000) >> 16`, `lo = v − (hi << 16)`. Para direcciones de 32 bits coincide con la secuencia del Integrante 1, y además funciona con cualquier valor de 64 bits.

## 6. Diseño LEX

`alu.py` está escrito como una especificación LEX. La sección de **definiciones** usa las mismas expresiones de `asm_lexer.py` de CacaoCore:

```python
REGISTRO  = [Rr](?:1[0-5]|[0-9])(?![A-Za-z0-9_])     # (R|r)(1[0-5]|[0-9])
NUMERO    = [+-]?\d+(?![\d.xX])                      # [+-]?\d+
MEMORIA   = 0x[0-9A-Fa-f]+                           # MEMORY: dirección directa
VARIABLE  = [a-z_][a-z0-9_]*                         # VAR
DIRECTO   = MEMORIA | \[VARIABLE\] | \[MEMORIA\]
INDIRECTO = \[REGISTRO\]
FIN       = (?=[ \t]*(?:[;#]|$))                      # nada más en la instrucción
```

Los mnemónicos se aceptan todo en minúscula o todo en MAYÚSCULA, igual que en CacaoCore. Cada **regla** reconoce una forma de direccionamiento (`t_OP_RR`, `t_OP_RI`, `t_OP_RM`, `t_OP_RN`, `t_OP_R`, `t_OP_I`, `t_OP_M`, `t_UNARIA_R`, `t_UNARIA_M`, `t_DESP_I`, `t_DESP_RI`, `t_SWAP_R`, `t_SWAP_RR`, `t_MOV_RR`, `t_MOV_RI`, `t_LOAD_I`, `t_STORE_R`, `t_FLOTANTE`), y su **acción** emite el código Enigma-64. El ancla `FIN` hace que las formas sean excluyentes: `ADD R1` no reconoce el prefijo de `ADD R1, R2`.

`t_error` se encarga de los errores: «registro inválido» (R16…), «modo de direccionamiento no soportado para X» (p. ej. `SHL R1, R2`), «mnemónico mezcla mayúsculas» o «instrucción desconocida». Cada error queda con su número de línea y la traducción sigue con la línea siguiente.

## 7. Banderas y ACC

**Banderas vivas.** Antes de emitir, `traductor.py` calcula para cada instrucción si algún camino posterior lee las banderas (un salto condicional) antes de que otra instrucción las vuelva a escribir. El recorrido sigue los `JMP` y es conservador con CALL/RET/IRET. Con esa información se aplican dos reglas:

1. Si la instrucción de CacaoCore **escribe** banderas, la última instrucción Enigma-64 que las escribe es la operación real, y todo lo que viene después son `STORE` a ranuras de derrame, que no las tocan.
2. Si la instrucción de CacaoCore **no** las escribe (MOV, SWAP, ROL, LEA, accesos a memoria…) pero su traducción sí (ADDI/SHL de direcciones y constantes), la secuencia se envuelve en `PUSH SR` … `POP SR`. Esto solo se hace si las banderas están vivas, así que no cuesta nada en el caso común.

**ACC.** Si ninguna instrucción del programa lee R15 (ni de forma explícita ni con las formas de acumulador implícito), el efecto lateral «ACC = resultado» no se puede observar. En ese caso no se emite y el ACC no ocupa un registro, que es lo que pasa en los cinco programas de ejemplo de CacaoCore. `TraductorCacaoEnigma(sincronizar_acc=True)` lo fuerza siempre.

## 8. Algoritmo de Euclides, lado a lado

Entrada: `spl/traductor/ejemplos/euclides.asm` (`alg_euc_mod.asm` de CacaoCore). Salida completa: `spl/traductor/ejemplos/euclides_enigma.asm`.

| CacaoCore-64 | Enigma-64 |
| :--- | :--- |
| `[prólogo] BP = área de derrame` | `ADDI R7, R0, 0x0030`<br>`SHL R7, R7, 16`<br>`ADDI R7, R7, 0x0000` |
| `a: 987654` | `ADDI R4, R0, 15`<br>`SHL R4, R4, 16`<br>`ADDI R4, R4, 4614`<br>`ADDI R5, R0, 0x0020`<br>`SHL R5, R5, 16`<br>`ADDI R5, R5, 0x1000`<br>`STORE R4, [R5]` |
| `b: 123456` | `ADDI R4, R0, 2`<br>`SHL R4, R4, 16`<br>`ADDI R4, R4, -7616`<br>`ADDI R5, R0, 0x0020`<br>`SHL R5, R5, 16`<br>`ADDI R5, R5, 0x1008`<br>`STORE R4, [R5]` |
| `temp: 0` | `ADDI R5, R0, 0x0020`<br>`SHL R5, R5, 16`<br>`ADDI R5, R5, 0x1010`<br>`STORE R0, [R5]` |
| `MOVD R0, [a]` | `ADDI R5, R0, 0x0020`<br>`SHL R5, R5, 16`<br>`ADDI R5, R5, 0x1000`<br>`LOAD R2, [R5]` |
| `MOVD R1, [b]` | `ADDI R5, R0, 0x0020`<br>`SHL R5, R5, 16`<br>`ADDI R5, R5, 0x1008`<br>`LOAD R3, [R5]` |
| `MOVD R2, 1` | `ADDI R1, R0, 1` |
| `CMP R0, R1` | `CMP R2, R3` |
| `JG GREATER` | `JP GREATER` |
| **`LOOP:`** | **`LOOP:`** |
| `CMP R2, 0` | `CMP R1, R0` |
| `JZ FIN` | `JZ FIN` |
| `MOVD R2, R0` | `ADD R1, R2, R0` |
| `MOVD R3, R1` | `STORE R3, [R7]` |
| `DIV R3, R2` | `LOAD R4, [R7]`<br>`DIV R4, R4, R1`<br>`MUL R5, R4, R1`<br>`LOAD R1, [R7]`<br>`SUB R1, R1, R5`<br>`STORE R4, [R7]` |
| `MOVD R1, R0` | `ADD R3, R2, R0` |
| `MOVD R0, R2` | `ADD R2, R1, R0` |
| `JMP LOOP` | `JMP LOOP` |
| **`GREATER:`** | **`GREATER:`** |
| `MOVD R9, R0` | `STORE R2, [R7 + 8]` |
| `MOVD R0, R1` | `ADD R2, R3, R0` |
| `MOVD R1, R9` | `LOAD R3, [R7 + 8]` |
| `JMP LOOP` | `JMP LOOP` |
| **`FIN:`** | **`FIN:`** |
| `MOVW [temp], R1` | `ADDI R5, R0, 0x0020`<br>`SHL R5, R5, 16`<br>`ADDI R5, R5, 0x1010`<br>`STORE R3, [R5]` |
| `MOVH R10, 0` | `STORE R0, [R7 + 16]` |
| `LEA R11, [temp]` | `ADDI R4, R0, 0x0020`<br>`SHL R4, R4, 16`<br>`ADDI R4, R4, 0x1010`<br>`STORE R4, [R7 + 24]` |
| `MOVW R12, 1` | `ADDI R4, R0, 1`<br>`STORE R4, [R7 + 32]` |
| `INTR 0` | *(sin código; aviso)* |
| `HLT` | `HLT` |

En el archivo real, cada línea emitida lleva como comentario su instrucción de origen, por ejemplo `DIV R4, R4, R1   ; L19: DIV R3, R2`.

Resultado en el emulador de Enigma-64: 232 bytes, 76 instrucciones ejecutadas, `[temp] = 6 = mcd(987654, 123456)`. El estado final de **todos** los registros de CacaoCore coincide con el del modelo de referencia (R3 = 20576, R9 = 987654, …).

## 9. Pruebas

`tests/test_spl/traductor/test_traductor_registros_alu.py` contiene 244 pruebas. Las de extremo a extremo traducen el programa, lo ensamblan con `enigma64/ensamblador.py`, lo ejecutan en la CPU y comparan el estado final con un **modelo de referencia** de CacaoCore escrito en la prueba. La comparación cubre cada registro (los derramados se leen de su ranura) y cada palabra de datos.

| Grupo | Qué verifica |
| :--- | :--- |
| Registros (22) | Normalización R0–R15 y alias, errores, tabla por defecto, R0 de CacaoCore nunca va a R0, asignación por uso, cuándo hay derrames, emisores reemplazables |
| Constantes (15) | `cargar_constante` corrida en la CPU, desde 0 hasta ±2⁶³ |
| Operandos y reglas LEX (40) | Clasificación de operandos, traducción exacta de cada forma, MOV con banderas vivas, DIV con residuo, FPU solo con aviso, cuatro tipos de error con su número de línea |
| Programas de CacaoCore (14) | Euclides (el del enunciado y 7 pares más contra el modelo, incluido 2⁴⁰), Euclides por restas con direcciones hex (84), burbuja ([1,3,4,5,8]), máximo con variables y con hex (10), comentario de origen en cada línea, errores que no detienen la traducción |
| `prueba_alu.asm` (1) | Todas las operaciones ALU en todas sus formas, con derrames y ACC observable. El programa se verifica solo (`[fallos] = 0`) y además se compara contra el modelo. |
| Banderas (32) | 8 saltos × 4 pares de valores, con 10 instrucciones neutras entre el CMP y el salto (MOV con imm de 17 bits, SWAP, ROL, LEA, MOV a/desde memoria, STORED, LOADD) |
| Aleatorias (120) | 60 semillas × 2 modos de ACC: programas con los 15 registros, inmediatos de hasta 17 bits, memoria directa e indirecta, DIV, SWAP, rotaciones y sondas de banderas con saltos |

Aparte de la suite corrí una campaña de 3000 programas aleatorios más: **4958 ejecuciones en dos modos, 0 diferencias**, y 4602 de ellas pasaron por el camino `PUSH SR`/`POP SR`. La suite completa del repositorio sigue pasando (1144 pruebas).

## 10. Limitaciones conocidas

| Limitación | Detalle |
| :--- | :--- |
| División con negativos | Enigma-64 trunca hacia cero; el emulador de CacaoCore usa `//` de Python (piso). Con signos distintos y residuo ≠ 0, cociente y residuo difieren en 1. Con operandos positivos son iguales. |
| Banderas C y V | Z y N son siempre exactas, y son las únicas que leen JZ/JNZ/JG/JL/JGE/JLE/JS/JNS. C y V pueden diferir: CacaoCore las limpia en las operaciones lógicas, y su C de la resta nunca se enciende (`uns_result > 2**64`). |
| Tamaño en MOVB/H/W entre registros | Se copia el valor completo. CacaoCore lanza `OverflowError` si el valor no cabe, así que en programas válidos el resultado es el mismo. |
| `INTR`, `SEXT`, saltos a direcciones absolutas, `JU`/`JNU`, FPU | Aviso o error con número de línea; no se traducen |
| `R13` | Comparte la pila de Enigma-64. Un programa que cargue en R13 una dirección propia de CacaoCore rompería PUSH/POP. |
| Tamaño del código | `.data` empieza en `0x00201000`, así que el código no puede pasar de 4 KiB. `ejecutar_en_enigma` lo comprueba; `prueba_alu` ocupa 2211 bytes. |

## 11. Revisión del módulo del Integrante 1 (`memoria.py`)

Lo reutilizo para todos los accesos a memoria, y sus 27 pruebas siguen pasando. Al integrarlo encontré lo siguiente, comprobado con el código:

| # | Hallazgo | Efecto | Cómo lo evita la integración / arreglo sugerido |
| :--- | :--- | :--- | :--- |
| 1 | `mapear_registro` por defecto: R0→R0, R8→R1, R9→R2…, R12/R14/R15→R5 | R0 pierde sus escrituras; R8 pisa a R1; LR y ACC comparten R5 | Antes de llamarlo, `traductor.py` reescribe cada registro por su registro físico. Arreglo: usar `spl.traductor.registros.TablaRegistros`. |
| 2 | `reg_temporal_valor` por defecto es `R6` (SP) | `MOVD [a], 5` destruye el puntero de pila | Se le pasan TMP1/TMP2 (R4/R5). Arreglo: cambiar el valor por defecto. |
| 3 | `generar_secuencia_direccion(reg)` vuelve a aplicar `mapear_registro` a un nombre que ya es de Enigma | Con `mapeo_registros={"R5": "R2"}` arma la dirección en R2 pero lee `[R5]` | Evitado por el punto 1. Arreglo: no volver a mapear dentro de esa función. |
| 4 | `hi16` se emite con `0x{:04X}`; si es ≥ 0x8000, la CPU le extiende el signo | Direcciones ≥ 0x7FFF8000 salen mal (`0x90000000` → `0xFFFFFFFF90000000`) | Los programas actuales no llegan ahí. Arreglo: usar `alu.cargar_constante`. |
| 5 | `traducir_programa` deja `.data`, `a: 987654` y las instrucciones que no son de memoria sin cambiar | Su salida sola no ensambla (`Mnemónico desconocido: '.DATA'`) | Es lo esperado en una parte; `traductor.py` resuelve el resto |
| 6 | La alineación `& ~7` junta direcciones hex distintas de la misma palabra (`0x100` y `0x104`) | Dos variables de CacaoCore podrían compartir celda | Riesgo de diseño; los ejemplos de CacaoCore no lo provocan |

## 12. Párrafo para el manual técnico

> **Registros y ALU (Integrante 2).** El traductor asigna los 16 registros de CacaoCore-64 a Enigma-64 según su uso en el programa. Cuenta en una pasada previa los usos de cada registro, ponderados ×10 por cada nivel de bucle. Los tres más usados van a R1–R3 (cuatro, con R7, si no hace falta derramar) y el resto se derrama a ranuras de 8 bytes en `0x00300000`, direccionadas con BP (`[R7 + 8k]`), de modo que cada acceso es un único LOAD o STORE que no altera banderas. R0 nunca recibe un registro, porque está cableado a cero, y se usa como operando cero (`NEG` → `SUB x, R0, x`). R4 y R5 son temporales, y R6 es la pila compartida con el R13 de CacaoCore. Las instrucciones ALU se reconocen con reglas `ply.lex` construidas con las mismas expresiones regulares del ensamblador de CacaoCore, una por modo de direccionamiento, y cada acción emite su secuencia de Enigma-64 con la instrucción original como comentario. La traducción respeta la semántica real del emulador de CacaoCore: su ALU de acumulador deja cada resultado también en R15 (efecto que se omite si el programa nunca lee R15), `DIV Rx, Ry` deja el residuo en Ry y se recalcula como x − (x/y)·y, `SHR` es aritmético y `CMPZ` compara 0 − Rx. Un análisis de banderas vivas garantiza que un salto condicional vea las mismas banderas Z y N que en CacaoCore: si una instrucción que no debía tocarlas se expande en código que sí lo hace, se protege con `PUSH SR` / `POP SR`. Los errores se informan con su número de línea y la traducción continúa. La equivalencia se verificó ejecutando los programas traducidos en el emulador de Enigma-64 y comparándolos registro por registro con un modelo de CacaoCore, en cinco programas reales, un programa con todas las operaciones ALU y miles de programas aleatorios.
