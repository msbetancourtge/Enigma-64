# Programas Oficiales de Prueba - Enigma-64 (Noctua Systems)

Este directorio contiene los archivos ejecutables compilados manualmente a código máquina Big-Endian de 64 bits para el computador **Enigma-64**, conforme a la especificación formal de la **Tarea 9** y para ser consumidos en la emulación de la **Tarea 10**.

## Formatos Disponibles

Para cada algoritmo se suministran tres formatos compatibles con el [CargadorEnigma](file:///d:/estocasticos/enigma64/cargador.py):
1. `.bin`: Binario crudo plano (flujo de bytes exactos listos para volcar en RAM).
2. `.hex`: Volcado en texto hexadecimal legible con cabecera comentada.
3. `.e64`: Formato ejecutable estructurado propio de Enigma-64 (Magic `ENIG`, cabecera de 32 bytes Big-Endian con dirección base, tamaño y punto de entrada).

---

## 1. Algoritmo 1: Cálculo del Factorial ($N!$)
* **Archivos**: `factorial.bin` (41 bytes), `factorial.hex`, `factorial.e64`.
* **Dirección base de carga**: `0x00200000` (Área de usuario).
* **Punto de entrada (PC inicial)**: `0x00200000`.
* **Variables en memoria RAM**:
  * Entrada $N$: `0x00201000` (Palabra de 64 bits = `0x0000000000000005`, $N=5$).
  * Salida factorial: `0x00201008` (Palabra de 64 bits = `0x0000000000000078`, $5! = 120$).
* **Registros utilizados**:
  * `R1`: Puntero base de variables (`0x00201000`).
  * `R2`: Valor de entrada $N$ / contador decremental.
  * `R3`: Acumulador del producto factorial.
* **Secuencia de instrucciones y bytes**:
  ```text
  0x00200000: ADDI R1, R0, 0x0020 -> 14 10 00 20
  0x00200004: SHL  R1, R1, 16     -> 24 11 00 10
  0x00200008: ADDI R1, R1, 0x1000 -> 14 11 10 00
  0x0020000C: LOAD R2, [R1 + 0]   -> 30 21 00 00
  0x00200010: ADDI R3, R0, 1      -> 14 30 00 01
  0x00200014: CMP  R2, R0         -> 27 02 00
  0x00200017: JZ   FIN_FACT       -> 41 00 0A
  0x0020001A: MUL  R3, R3, R2     -> 12 33 20
  0x0020001D: SUBI R2, R2, 1      -> 15 22 00 01
  0x00200021: JNZ  LOOP_FACT      -> 42 FF F6
  0x00200024: STORE R3, [R1 + 8]  -> 31 31 00 08
  0x00200028: HLT                 -> 00
  ```

---

## 2. Algoritmo 2: Algoritmo de Euclides ($MCD(A, B)$)
* **Archivos**: `euclides.bin` (50 bytes), `euclides.hex`, `euclides.e64`.
* **Dirección base de carga**: `0x00200100` (Área de usuario).
* **Punto de entrada (PC inicial)**: `0x00200100`.
* **Variables en memoria RAM**:
  * Entrada $A$: `0x00202000` (Palabra de 64 bits = `0x0000000000000030`, $A=48$).
  * Entrada $B$: `0x00202008` (Palabra de 64 bits = `0x0000000000000012`, $B=18$).
  * Salida $MCD$: `0x00202010` (Palabra de 64 bits = `0x0000000000000006`, $MCD=6$).
* **Registros utilizados**:
  * `R1`: Puntero base de variables (`0x00202000`).
  * `R2`: Variable $A$.
  * `R3`: Variable $B$.
* **Secuencia de instrucciones y bytes**:
  ```text
  0x00200100: ADDI R1, R0, 0x0020 -> 14 10 00 20
  0x00200104: SHL  R1, R1, 16     -> 24 11 00 10
  0x00200108: ADDI R1, R1, 0x2000 -> 14 11 20 00
  0x0020010C: LOAD R2, [R1 + 0]   -> 30 21 00 00
  0x00200110: LOAD R3, [R1 + 8]   -> 30 31 00 08
  0x00200114: CMP  R2, R3         -> 27 02 30
  0x00200117: JZ   FIN_EUCLIDES   -> 41 00 13
  0x0020011A: JN   B_ES_MAYOR     -> 45 00 08
  0x0020011D: SUB  R2, R2, R3     -> 11 22 30
  0x00200120: JMP  0x00200114     -> 40 00 20 01 14
  0x00200125: SUB  R3, R3, R2     -> 11 33 20
  0x00200128: JMP  0x00200114     -> 40 00 20 01 14
  0x0020012D: STORE R2, [R1 + 16] -> 31 21 00 10
  0x00200131: HLT                 -> 00
  ```

---

## 3. Algoritmo 3: Sucesión de Fibonacci en RAM
* **Archivos**: `fibonacci.bin` (63 bytes), `fibonacci.hex`, `fibonacci.e64`.
* **Dirección base de carga**: `0x00200200` (Área de usuario).
* **Punto de entrada (PC inicial)**: `0x00200200`.
* **Variables en memoria RAM**:
  * Arreglo secuencial a partir de `0x00203000` (7 palabras de 64 bits = 56 bytes):
    * `0x00203000`: $F_0 = 0$
    * `0x00203008`: $F_1 = 1$
    * `0x00203010`: $F_2 = 1$
    * `0x00203018`: $F_3 = 2$
    * `0x00203020`: $F_4 = 3$
    * `0x00203028`: $F_5 = 5$
    * `0x00203030`: $F_6 = 8$
* **Registros utilizados**:
  * `R1`: Puntero dinámico a la celda de memoria RAM (`ptr`).
  * `R2`: Término $F_{k-1}$.
  * `R3`: Término $F_k$.
  * `R4`: Contador de iteraciones restantes ($5$).
  * `R5`: Siguiente término generado ($F_{k+1}$).
* **Secuencia de instrucciones y bytes**:
  ```text
  0x00200200: ADDI R1, R0, 0x0020 -> 14 10 00 20
  0x00200204: SHL  R1, R1, 16     -> 24 11 00 10
  0x00200208: ADDI R1, R1, 0x3000 -> 14 11 30 00
  0x0020020C: ADDI R2, R0, 0      -> 14 20 00 00
  0x00200210: ADDI R3, R0, 1      -> 14 30 00 01
  0x00200214: STORE R2, [R1 + 0]  -> 31 21 00 00
  0x00200218: STORE R3, [R1 + 8]  -> 31 31 00 08
  0x0020021C: ADDI R1, R1, 16     -> 14 11 00 10
  0x00200220: ADDI R4, R0, 5      -> 14 40 00 05
  0x00200224: ADD  R5, R3, R2     -> 10 53 20
  0x00200227: STORE R5, [R1 + 0]  -> 31 51 00 00
  0x0020022B: ADDI R2, R3, 0      -> 14 23 00 00
  0x0020022F: ADDI R3, R5, 0      -> 14 35 00 00
  0x00200233: ADDI R1, R1, 8      -> 14 11 00 08
  0x00200237: SUBI R4, R4, 1      -> 15 44 00 01
  0x0020023B: JNZ  LOOP_FIBONACCI -> 42 FF E6
  0x0020023E: HLT                 -> 00
  ```

---

## 4. Firmware del Cargador (Residente en 0x00001000)
* **Archivo**: `cargador_firmware.bin` (69 bytes).
* **Dirección base**: `0x00001000` (Región de monitor y cargador).
* Emula la rutina descrita en la Tarea 9 (Págs. 25-28) que recibe en `R1` (origen), `R2` (destino) y `R3` (tamaño), validando que no invada vectores ni pila antes de copiar byte a byte y saltar a `R5`.
