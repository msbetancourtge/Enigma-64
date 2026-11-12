; ==============================================================================
; merge_sort.asm - Algoritmo de Ordenamiento por Mezclas (Merge Sort) & MMIO
; Tarea 29: Integrante 6 (Algoritmo 1 & MMIO)
;
; Utiliza la libreria de estructuras de datos (estructuras.inc):
;   - layout_datos.inc (constantes de memoria: BASE_VECTORES, BASE_BUFFERS)
;   - vec.asm (primitivas de listas: VEC_ADDR, VEC_GET, VEC_SET, VEC_COPY, VEC_LEN)
;
; Distribucion de memoria:
;   - BASE_VECTORES (0x00220000): Vector de entrada / ordenado
;   - BASE_BUFFERS  (0x002E0000): Vector auxiliar para MERGE
;   - Pila          (0x00400000): Alineada a 8 bytes, crecimiento descendente
;   - MMIO DATA     (0xFF001010): Registro de emision de datos de pantalla CRT
; ==============================================================================
#include "estructuras.inc"

PRINCIPAL:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000 (alineada a 8 bytes)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16             ; R1 = base del vector (BASE_VECTORES = 0x00220000)
        ADDI R4, R0, 0x002E
        SHL  R4, R4, 16             ; R4 = aux (BASE_BUFFERS = 0x002E0000)

        ; Verificar si la memoria ya fue configurada externamente [base - 16] != 0
        LOAD R5, [R1 - 16]
        CMP  R5, R0
        JNZ  EJECUTAR_ORDENAMIENTO

        ; Si [base - 8] != 0, tambien fue configurado externamente
        CALL VEC_LEN                ; R5 = n
        CMP  R5, R0
        JNZ  EJECUTAR_ORDENAMIENTO

        ; --- Inicializacion Autonoma por Defecto (Vector Demo: 8 elementos) ---
        ; Contenido: [45, -12, 89, 0, 23, -5, 77, 10]
        ADDI R5, R0, 8
        STORE R5, [R1 - 8]          ; cabecera n = 8

        ADDI R2, R0, 0
        ADDI R3, R0, 45
        CALL VEC_SET                ; v[0] = 45

        ADDI R2, R0, 1
        ADDI R3, R0, -12
        CALL VEC_SET                ; v[1] = -12

        ADDI R2, R0, 2
        ADDI R3, R0, 89
        CALL VEC_SET                ; v[2] = 89

        ADDI R2, R0, 3
        ADDI R3, R0, 0
        CALL VEC_SET                ; v[3] = 0

        ADDI R2, R0, 4
        ADDI R3, R0, 23
        CALL VEC_SET                ; v[4] = 23

        ADDI R2, R0, 5
        ADDI R3, R0, -5
        CALL VEC_SET                ; v[5] = -5

        ADDI R2, R0, 6
        ADDI R3, R0, 77
        CALL VEC_SET                ; v[6] = 77

        ADDI R2, R0, 7
        ADDI R3, R0, 10
        CALL VEC_SET                ; v[7] = 10

EJECUTAR_ORDENAMIENTO:
        ADDI R2, R0, 0              ; R2 = lo = 0
        CALL VEC_LEN                ; R5 = n (cabecera en base - 8)
        ADD  R3, R5, R0             ; R3 = hi = n
        CALL MERGE_SORT

        ; Salida del vector ordenado hacia pantalla MMIO (0xFF001010)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16             ; R1 = base del vector
        CALL VEC_LEN                ; R5 = n
        ADD  R2, R5, R0             ; R2 = n
        CALL EMITIR_VECTOR_MMIO

        HLT

; ------------------------------------------------------------------------------
; MERGE_SORT: ordena v[lo, hi) recursivamente
;   R1 = base, R2 = lo, R3 = hi (exclusivo), R4 = aux. Preserva R1..R4.
; ------------------------------------------------------------------------------
MERGE_SORT:
        PUSH R2                     ; preserva lo
        PUSH R3                     ; preserva hi
        ENTER 8                     ; local: mid en [BP - 8]
        SUB  R5, R3, R2             ; R5 = hi - lo
        SUBI R5, R5, 2
        JN   MS_FIN                 ; menos de 2 elementos: ya esta ordenado
        SUB  R5, R3, R2
        SHR  R5, R5, 1
        ADD  R5, R2, R5             ; R5 = mid = lo + (hi - lo) / 2
        STORE R5, [BP - 8]
        ADD  R3, R5, R0             ; hi = mid
        CALL MERGE_SORT             ; ordena [lo, mid); R1, R2, R4 siguen igual
        LOAD R2, [BP - 8]           ; lo = mid
        LOAD R3, [BP + 8]           ; hi original
        CALL MERGE_SORT             ; ordena [mid, hi)
        LOAD R2, [BP + 16]          ; R2 = lo
        LOAD R3, [BP - 8]           ; R3 = mid
        LOAD R5, [BP + 8]
        PUSH R5                     ; 5o argumento: hi
        CALL MERGE                  ; MERGE(base, lo, mid, aux; hi)
        ADDI SP, SP, 8              ; el llamador retira el 5o argumento
MS_FIN:
        LEAVE                       ; SP = BP y recupera el BP anterior
        POP  R3                     ; restaura hi
        POP  R2                     ; restaura lo
        RET

; ------------------------------------------------------------------------------
; MERGE: mezcla v[lo, mid) y v[mid, hi), ya ordenados, en v[lo, hi)
;   R1 = base, R2 = lo, R3 = mid, R4 = aux, pila: hi. Preserva R1..R4.
;   Marco tras PUSH R1..R4 y ENTER 24:
;     [BP + 48] hi (5o argumento)   [BP + 40] retorno
;     [BP + 32] R1  [BP + 24] R2  [BP + 16] R3  [BP + 8] R4  [BP + 0] BP previo
;     [BP - 8] i    [BP - 16] j   [BP - 24] k
; ------------------------------------------------------------------------------
MERGE:
        PUSH R1                     ; preserva base
        PUSH R2                     ; preserva lo
        PUSH R3                     ; preserva mid
        PUSH R4                     ; preserva aux
        ENTER 24                    ; reserva locales: i, j, k

        ; --- Paso 1: Copiar v[lo, hi) a aux[lo, hi) con VEC_COPY ---
        ; destino = aux + lo * 8
        LOAD R2, [BP + 24]          ; R2 = lo
        SHL  R5, R2, 3              ; R5 = lo * 8
        LOAD R1, [BP + 8]           ; R1 = aux
        ADD  R1, R1, R5             ; R1 = destino = aux + lo * 8

        ; origen = base + lo * 8
        LOAD R2, [BP + 32]          ; R2 = base
        ADD  R2, R2, R5             ; R2 = origen = base + lo * 8

        ; n = hi - lo
        LOAD R3, [BP + 48]          ; R3 = hi
        LOAD R5, [BP + 24]          ; R5 = lo
        SUB  R3, R3, R5             ; R3 = n = hi - lo
        CALL VEC_COPY

        ; --- Paso 2: Inicializar indices i = lo, j = mid, k = lo ---
        LOAD R5, [BP + 24]          ; R5 = lo
        STORE R5, [BP - 8]          ; i = lo
        STORE R5, [BP - 24]         ; k = lo
        LOAD R5, [BP + 16]          ; R5 = mid
        STORE R5, [BP - 16]         ; j = mid

MERGE_BUCLE:
        ; Condicion 1: i < mid (si i >= mid, saltar a MERGE_RESTO)
        LOAD R1, [BP - 8]           ; R1 = i
        LOAD R2, [BP + 16]          ; R2 = mid
        CMP  R1, R2                 ; i - mid
        JN   MERGE_I_OK             ; si i < mid (N=1), continuar
        JMP  MERGE_RESTO            ; si i >= mid, salir del bucle

MERGE_I_OK:
        ; Condicion 2: j < hi (si j >= hi, saltar a MERGE_RESTO)
        LOAD R1, [BP - 16]          ; R1 = j
        LOAD R2, [BP + 48]          ; R2 = hi
        CMP  R1, R2                 ; j - hi
        JN   MERGE_J_OK             ; si j < hi (N=1), continuar
        JMP  MERGE_RESTO            ; si j >= hi, salir del bucle

MERGE_J_OK:
        ; Obtener a = aux[i]
        LOAD R1, [BP + 8]           ; R1 = aux
        LOAD R2, [BP - 8]           ; R2 = i
        CALL VEC_GET                ; R5 = a
        PUSH R5                     ; preservar a en pila

        ; Obtener b = aux[j]
        LOAD R1, [BP + 8]           ; R1 = aux
        LOAD R2, [BP - 16]          ; R2 = j
        CALL VEC_GET                ; R5 = b
        ADD  R4, R5, R0             ; R4 = b

        POP  R3                     ; R3 = a

        ; Comparar a y b con signo: si b < a, elegir b; si no (a <= b), elegir a
        CMP  R4, R3                 ; calcular b - a
        JN   MERGE_ELEGIR_B         ; si b < a, salto

        ; Caso a <= b: v[k] = a, i++
        LOAD R1, [BP + 32]          ; R1 = base
        LOAD R2, [BP - 24]          ; R2 = k
        CALL VEC_SET
        LOAD R5, [BP - 8]
        ADDI R5, R5, 1
        STORE R5, [BP - 8]          ; i = i + 1
        JMP  MERGE_AVANZAR_K

MERGE_ELEGIR_B:
        ; Caso b < a: v[k] = b, j++
        LOAD R1, [BP + 32]          ; R1 = base
        LOAD R2, [BP - 24]          ; R2 = k
        ADD  R3, R4, R0             ; R3 = b
        CALL VEC_SET
        LOAD R5, [BP - 16]
        ADDI R5, R5, 1
        STORE R5, [BP - 16]         ; j = j + 1

MERGE_AVANZAR_K:
        LOAD R5, [BP - 24]
        ADDI R5, R5, 1
        STORE R5, [BP - 24]         ; k = k + 1
        JMP  MERGE_BUCLE

MERGE_RESTO:
        ; --- Paso 3: Copiar remanentes de mitad izquierda aux[i..mid) a v[k..] ---
        LOAD R1, [BP - 8]           ; R1 = i
        LOAD R2, [BP + 16]          ; R2 = mid
        CMP  R1, R2                 ; i - mid
        JN   MERGE_COPIAR_RESTO     ; si i < mid (N=1), hay remanente
        JMP  MERGE_FIN              ; si i >= mid, fin (mitad derecha ya en sitio)

MERGE_COPIAR_RESTO:
        ; n_rem = mid - i
        SUB  R3, R2, R1             ; R3 = n_rem = mid - i

        ; origen = aux + i * 8
        SHL  R5, R1, 3              ; R5 = i * 8
        LOAD R2, [BP + 8]           ; R2 = aux
        ADD  R2, R2, R5             ; R2 = origen = aux + i * 8

        ; destino = base + k * 8
        LOAD R1, [BP - 24]          ; R1 = k
        SHL  R5, R1, 3              ; R5 = k * 8
        LOAD R1, [BP + 32]          ; R1 = base
        ADD  R1, R1, R5             ; R1 = destino = base + k * 8

        CALL VEC_COPY

MERGE_FIN:
        LEAVE                       ; desarma marco ENTER 24
        POP  R4                     ; restaura aux
        POP  R3                     ; restaura mid
        POP  R2                     ; restaura lo
        POP  R1                     ; restaura base
        RET

; ------------------------------------------------------------------------------
; EMITIR_VECTOR_MMIO: salida del vector ordenado por pantalla MMIO (0xFF001010)
;   Entradas: R1 = base, R2 = n. Preserva R1..R4, SP, BP.
;   Emite cada entero convertido a caracteres ASCII separados por espacio (' ')
;   y cierra con salto de linea ('\n').
; ------------------------------------------------------------------------------
EMITIR_VECTOR_MMIO:
        PUSH R1
        PUSH R2
        PUSH R3
        PUSH R4
        ENTER 32                    ; locales: [BP-8]=idx, [BP-16]=n, [BP-24]=base, [BP-32]=puerto

        STORE R1, [BP - 24]         ; base
        STORE R2, [BP - 16]         ; n
        ADDI R5, R0, 0
        STORE R5, [BP - 8]          ; idx = 0

        ; Sintetizar direccion MMIO 0xFF001010
        ADDI R5, R0, 1
        SHL  R5, R5, 16
        ADDI R5, R5, -256
        SHL  R5, R5, 16
        ADDI R5, R5, 4112           ; R5 = 0xFF001010
        STORE R5, [BP - 32]         ; puerto_mmio

MMIO_LOOP_ELEM:
        ; Verificar si idx < n
        LOAD R1, [BP - 8]           ; idx
        LOAD R2, [BP - 16]          ; n
        CMP  R1, R2                 ; idx - n
        JN   MMIO_PROCESAR_ELEM     ; si idx < n (N=1), procesar
        JMP  MMIO_FIN_TODO          ; si idx >= n, terminar salida

MMIO_PROCESAR_ELEM:
        ; Si idx > 0, emitir espacio de separacion
        CMP  R1, R0
        JZ   MMIO_LEER_DATO
        ADDI R4, R0, 32             ; ASCII ' ' = 32
        LOAD R5, [BP - 32]
        STORE R4, [R5 + 0]

MMIO_LEER_DATO:
        LOAD R1, [BP - 24]          ; base
        LOAD R2, [BP - 8]           ; idx
        CALL VEC_GET                ; R5 = valor
        ADD  R1, R5, R0             ; R1 = valor a imprimir

        ; Caso valor == 0
        CMP  R1, R0
        JNZ  MMIO_CHECK_SIGNO
        ADDI R4, R0, 48             ; ASCII '0'
        LOAD R5, [BP - 32]
        STORE R4, [R5 + 0]
        JMP  MMIO_SIGUIENTE_ELEM

MMIO_CHECK_SIGNO:
        JN   MMIO_ES_NEGATIVO
        JMP  MMIO_EMITIR_DIGITOS

MMIO_ES_NEGATIVO:
        ADDI R4, R0, 45             ; ASCII '-'
        LOAD R5, [BP - 32]
        STORE R4, [R5 + 0]
        SUB  R1, R0, R1             ; R1 = 0 - R1 (positivo)

MMIO_EMITIR_DIGITOS:
        ADDI R2, R0, 10             ; divisor = 10
        ADDI R4, R0, 0              ; contador de digitos = 0

MMIO_LOOP_DIV:
        CMP  R1, R0
        JZ   MMIO_LOOP_POP_DIGITOS
        DIV  R3, R1, R2             ; cociente
        MUL  R5, R3, R2
        SUB  R5, R1, R5             ; residuo = R1 - cociente * 10
        ADDI R5, R5, 48             ; digito ASCII
        PUSH R5
        ADDI R4, R4, 1
        ADD  R1, R3, R0
        JMP  MMIO_LOOP_DIV

MMIO_LOOP_POP_DIGITOS:
        CMP  R4, R0
        JZ   MMIO_SIGUIENTE_ELEM
        POP  R3                     ; caracter ASCII del digito
        LOAD R5, [BP - 32]
        STORE R3, [R5 + 0]          ; emitir a pantalla MMIO
        SUBI R4, R4, 1
        JMP  MMIO_LOOP_POP_DIGITOS

MMIO_SIGUIENTE_ELEM:
        LOAD R5, [BP - 8]
        ADDI R5, R5, 1
        STORE R5, [BP - 8]          ; idx = idx + 1
        JMP  MMIO_LOOP_ELEM

MMIO_FIN_TODO:
        LOAD R2, [BP - 16]          ; n
        CMP  R2, R0
        JZ   MMIO_SALIR
        ADDI R4, R0, 10             ; ASCII '\n' = 10
        LOAD R5, [BP - 32]
        STORE R4, [R5 + 0]

MMIO_SALIR:
        LEAVE                       ; desarma marco ENTER 32
        POP  R4
        POP  R3
        POP  R2
        POP  R1
        RET
