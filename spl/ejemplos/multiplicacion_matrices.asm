; ==============================================================================
; multiplicacion_matrices.asm - Problema Computacional 3: Matrices 2D
; Tarea 29: Integrante 7 (Algoritmos 2 y 3 & Suite de Tests)
;
; Implementa sobre el mapa lineal Row-Major de Enigma-64:
;   1. MAT_MUL     : Multiplicacion de matrices C (FA x CB) = A (FA x K) * B (K x CB)
;   2. MAT_VEC_MUL : Multiplicacion matriz por vector y (FA) = A (FA x K) * x (K)
;
; Distribucion de memoria:
;   - Matriz A (FA x K)  : 0x00260000 (slot descriptor 0 en 0x00210000)
;   - Matriz B (K x CB)  : 0x00260200 (slot descriptor 1 en 0x00210020)
;   - Matriz C (FA x CB) : 0x00260400 (slot descriptor 2 en 0x00210040)
;   - Vector x (K)       : 0x00220000 (slot descriptor 3 en 0x00210060)
;   - Vector y (FA)      : 0x00220100 (slot descriptor 4 en 0x00210080)
;   - Registro R5        : conserva C[0][0] al finalizar con HLT
; ==============================================================================
#define INCLUIR_MATRICES
#include "estructuras.inc"

PRINCIPAL:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000 (alineado a 8 bytes)

        ; R1 = base_A (0x00260000)
        ADDI R1, R0, 0x0026
        SHL  R1, R1, 16

        ; Verificar si la matriz A ya fue precargada externamente en RAM
        CALL MAT_ROWS
        CMP  R5, R0
        JNZ  EJECUTAR_MULTIPLICACION

        ; --- Inicializacion Autonoma por Defecto ---
        ; Matriz A (2 x 3) en 0x00260000 (slot 0):
        ;   [ 1,  2,  3 ]
        ;   [ 4, -1,  2 ]
        ADDI R1, R0, 0              ; slot 0
        ADDI R2, R0, 0x0026
        SHL  R2, R2, 16             ; base_A = 0x00260000
        ADDI R3, R0, 2              ; filas = 2
        ADDI R4, R0, 3              ; cols = 3
        CALL DESC_MAT_INIT

        ADD  R1, R2, R0             ; R1 = base_A
        ADDI R2, R0, 0
        ADDI R3, R0, 0
        ADDI R4, R0, 1
        CALL MAT_SET                ; A[0][0] = 1

        ADDI R3, R0, 1
        ADDI R4, R0, 2
        CALL MAT_SET                ; A[0][1] = 2

        ADDI R3, R0, 2
        ADDI R4, R0, 3
        CALL MAT_SET                ; A[0][2] = 3

        ADDI R2, R0, 1
        ADDI R3, R0, 0
        ADDI R4, R0, 4
        CALL MAT_SET                ; A[1][0] = 4

        ADDI R3, R0, 1
        ADDI R4, R0, -1
        CALL MAT_SET                ; A[1][1] = -1

        ADDI R3, R0, 2
        ADDI R4, R0, 2
        CALL MAT_SET                ; A[1][2] = 2

        ; Matriz B (3 x 2) en 0x00260200 (slot 1):
        ;   [ 2,  1 ]
        ;   [ 0, -3 ]
        ;   [ 4,  5 ]
        ; Producto esperado C = A * B (2 x 2):
        ;   [ 14, 10 ]
        ;   [ 16, 17 ]
        ADDI R1, R0, 1              ; slot 1
        ADDI R2, R0, 0x0026
        SHL  R2, R2, 16
        ADDI R2, R2, 512            ; base_B = 0x00260200
        ADDI R3, R0, 3              ; filas = 3
        ADDI R4, R0, 2              ; cols = 2
        CALL DESC_MAT_INIT

        ADD  R1, R2, R0             ; R1 = base_B
        ADDI R2, R0, 0
        ADDI R3, R0, 0
        ADDI R4, R0, 2
        CALL MAT_SET                ; B[0][0] = 2

        ADDI R3, R0, 1
        ADDI R4, R0, 1
        CALL MAT_SET                ; B[0][1] = 1

        ADDI R2, R0, 1
        ADDI R3, R0, 0
        ADDI R4, R0, 0
        CALL MAT_SET                ; B[1][0] = 0

        ADDI R3, R0, 1
        ADDI R4, R0, -3
        CALL MAT_SET                ; B[1][1] = -3

        ADDI R2, R0, 2
        ADDI R3, R0, 0
        ADDI R4, R0, 4
        CALL MAT_SET                ; B[2][0] = 4

        ADDI R3, R0, 1
        ADDI R4, R0, 5
        CALL MAT_SET                ; B[2][1] = 5

        ; Vector x (longitud 3) en 0x00220000 (slot 3): [2, -1, 3]
        ; Producto esperado y = A * x (longitud 2): [9, 15]
        ADDI R1, R0, 3              ; slot 3
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16             ; base_x = 0x00220000
        ADDI R3, R0, 3              ; longitud = 3
        CALL DESC_VEC_INIT

        ADD  R1, R2, R0             ; R1 = base_x
        ADDI R2, R0, 0
        ADDI R3, R0, 2
        CALL VEC_SET                ; x[0] = 2

        ADDI R2, R0, 1
        ADDI R3, R0, -1
        CALL VEC_SET                ; x[1] = -1

        ADDI R2, R0, 2
        ADDI R3, R0, 3
        CALL VEC_SET                ; x[2] = 3

EJECUTAR_MULTIPLICACION:
        ; 1. Si B tiene filas > 0, ejecutar C = A * B
        ADDI R1, R0, 0x0026
        SHL  R1, R1, 16             ; R1 = base_A (0x00260000)
        ADD  R2, R1, R0
        ADDI R2, R2, 512            ; R2 = base_B (0x00260200)
        ADD  R3, R1, R0
        ADDI R3, R3, 1024           ; R3 = base_C (0x00260400)

        PUSH R1
        ADD  R1, R2, R0
        CALL MAT_ROWS               ; R5 = filas de B
        POP  R1
        CMP  R5, R0
        JZ   VERIFICAR_MAT_VEC
        CALL MAT_MUL

VERIFICAR_MAT_VEC:
        ; 2. Si existe un vector x en 0x00220000 con longitud > 0, calcular y = A * x
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16             ; R2 = base_x (0x00220000)
        PUSH R1
        ADD  R1, R2, R0
        CALL VEC_LEN                ; R5 = len(x)
        POP  R1
        CMP  R5, R0
        JZ   FIN_PROGRAMA_MAT

        ADD  R3, R2, R0
        ADDI R3, R3, 256            ; R3 = base_y (0x00220100)
        CALL MAT_VEC_MUL

FIN_PROGRAMA_MAT:
        ; Si C fue calculada, dejar C[0][0] en R5; de lo contrario dejar y[0]
        ADDI R1, R0, 0x0026
        SHL  R1, R1, 16
        ADDI R1, R1, 1024           ; base_C = 0x00260400
        CALL MAT_ROWS
        CMP  R5, R0
        JZ   LEER_Y0_FINAL
        ADDI R2, R0, 0
        ADDI R3, R0, 0
        CALL MAT_GET                ; R5 = C[0][0]
        HLT

LEER_Y0_FINAL:
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16
        ADDI R1, R1, 256            ; base_y = 0x00220100
        ADDI R2, R0, 0
        CALL VEC_GET                ; R5 = y[0]
        HLT

; ------------------------------------------------------------------------------
; MAT_MUL: Multiplicacion de matrices C (FA x CB) = A (FA x K) * B (K x CB).
;   Entradas : R1 = base_A, R2 = base_B, R3 = base_C
;   Salida   : R5 = C[0][0] (y matriz C escrita en base_C con descriptor en slot 2)
;   Preserva : R1..R4, SP, BP
;   Locales en marco ENTER 72:
;     [BP - 8]  base_A
;     [BP - 16] base_B
;     [BP - 24] base_C
;     [BP - 32] filas_A (FA)
;     [BP - 40] cols_A  (K)
;     [BP - 48] cols_B  (CB)
;     [BP - 56] i
;     [BP - 64] j
;     [BP - 72] acc
; ------------------------------------------------------------------------------
MAT_MUL:
        PUSH R1
        PUSH R2
        PUSH R3
        PUSH R4
        ENTER 72

        STORE R1, [BP - 8]          ; base_A
        STORE R2, [BP - 16]         ; base_B
        STORE R3, [BP - 24]         ; base_C

        ; Dimensiones de A: FA y K
        LOAD R1, [BP - 8]
        CALL MAT_ROWS
        STORE R5, [BP - 32]         ; FA
        CALL MAT_COLS
        STORE R5, [BP - 40]         ; K

        ; Columnas de B: CB
        LOAD R1, [BP - 16]
        CALL MAT_COLS
        STORE R5, [BP - 48]         ; CB

        ; Inicializar matriz resultado C (FA x CB) en slot 2 y limpiarla
        ADDI R1, R0, 2              ; slot 2
        LOAD R2, [BP - 24]          ; base_C
        LOAD R3, [BP - 32]          ; FA
        LOAD R4, [BP - 48]          ; CB
        CALL DESC_MAT_INIT

        LOAD R1, [BP - 24]
        CALL MAT_CLEAR

        ; Bucle externo i = 0 .. FA - 1
        STORE R0, [BP - 56]         ; i = 0

MM_LOOP_I:
        LOAD R1, [BP - 56]          ; i
        LOAD R2, [BP - 32]          ; FA
        CMP  R1, R2                 ; i - FA
        JN   MM_INIT_J
        JMP  MM_FIN

MM_INIT_J:
        STORE R0, [BP - 64]         ; j = 0

MM_LOOP_J:
        LOAD R1, [BP - 64]          ; j
        LOAD R2, [BP - 48]          ; CB
        CMP  R1, R2                 ; j - CB
        JN   MM_INIT_K
        JMP  MM_NEXT_I

MM_INIT_K:
        STORE R0, [BP - 72]         ; acc = 0
        ADDI R4, R0, 0              ; k = 0

MM_LOOP_K:
        LOAD R2, [BP - 40]          ; K
        CMP  R4, R2                 ; k - K
        JN   MM_BODY_K
        JMP  MM_STORE_CIJ

MM_BODY_K:
        ; Leer A[i][k]
        LOAD R1, [BP - 8]           ; base_A
        LOAD R2, [BP - 56]          ; i
        ADD  R3, R4, R0             ; k
        CALL MAT_GET                ; R5 = A[i][k]
        PUSH R5

        ; Leer B[k][j]
        LOAD R1, [BP - 16]          ; base_B
        ADD  R2, R4, R0             ; k
        LOAD R3, [BP - 64]          ; j
        CALL MAT_GET                ; R5 = B[k][j]

        ; acc += A[i][k] * B[k][j]
        POP  R3                     ; R3 = A[i][k]
        MUL  R5, R3, R5
        LOAD R3, [BP - 72]
        ADD  R3, R3, R5
        STORE R3, [BP - 72]

        ADDI R4, R4, 1              ; k = k + 1
        JMP  MM_LOOP_K

MM_STORE_CIJ:
        LOAD R1, [BP - 24]          ; base_C
        LOAD R2, [BP - 56]          ; i
        LOAD R3, [BP - 64]          ; j
        LOAD R4, [BP - 72]          ; acc
        CALL MAT_SET

        LOAD R5, [BP - 64]
        ADDI R5, R5, 1
        STORE R5, [BP - 64]         ; j = j + 1
        JMP  MM_LOOP_J

MM_NEXT_I:
        LOAD R5, [BP - 56]
        ADDI R5, R5, 1
        STORE R5, [BP - 56]         ; i = i + 1
        JMP  MM_LOOP_I

MM_FIN:
        LOAD R1, [BP - 24]
        ADDI R2, R0, 0
        ADDI R3, R0, 0
        CALL MAT_GET                ; R5 = C[0][0]
        LEAVE
        POP  R4
        POP  R3
        POP  R2
        POP  R1
        RET

; ------------------------------------------------------------------------------
; MAT_VEC_MUL: Multiplicacion Matriz por Vector y (FA) = A (FA x K) * x (K).
;   Entradas : R1 = base_A, R2 = base_x, R3 = base_y
;   Salida   : R5 = y[0] (y vector resultado en base_y con descriptor en slot 4)
;   Preserva : R1..R4, SP, BP
;   Locales en marco ENTER 56:
;     [BP - 8]  base_A
;     [BP - 16] base_x
;     [BP - 24] base_y
;     [BP - 32] filas_A (FA)
;     [BP - 40] cols_A  (K)
;     [BP - 48] i
;     [BP - 56] acc
; ------------------------------------------------------------------------------
MAT_VEC_MUL:
        PUSH R1
        PUSH R2
        PUSH R3
        PUSH R4
        ENTER 56

        STORE R1, [BP - 8]          ; base_A
        STORE R2, [BP - 16]         ; base_x
        STORE R3, [BP - 24]         ; base_y

        LOAD R1, [BP - 8]
        CALL MAT_ROWS
        STORE R5, [BP - 32]         ; FA
        CALL MAT_COLS
        STORE R5, [BP - 40]         ; K

        ; Inicializar descriptor y cabecera de y en slot 4
        ADDI R1, R0, 4              ; slot 4
        LOAD R2, [BP - 24]          ; base_y
        LOAD R3, [BP - 32]          ; longitud = FA
        CALL DESC_VEC_INIT

        STORE R0, [BP - 48]         ; i = 0

MVM_LOOP_I:
        LOAD R1, [BP - 48]          ; i
        LOAD R2, [BP - 32]          ; FA
        CMP  R1, R2                 ; i - FA
        JN   MVM_INIT_K
        JMP  MVM_FIN

MVM_INIT_K:
        STORE R0, [BP - 56]         ; acc = 0
        ADDI R4, R0, 0              ; k = 0

MVM_LOOP_K:
        LOAD R2, [BP - 40]          ; K
        CMP  R4, R2                 ; k - K
        JN   MVM_BODY_K
        JMP  MVM_STORE_YI

MVM_BODY_K:
        ; Leer A[i][k]
        LOAD R1, [BP - 8]           ; base_A
        LOAD R2, [BP - 48]          ; i
        ADD  R3, R4, R0             ; k
        CALL MAT_GET                ; R5 = A[i][k]
        PUSH R5

        ; Leer x[k]
        LOAD R1, [BP - 16]          ; base_x
        ADD  R2, R4, R0             ; k
        CALL VEC_GET                ; R5 = x[k]

        POP  R3                     ; R3 = A[i][k]
        MUL  R5, R3, R5
        LOAD R3, [BP - 56]
        ADD  R3, R3, R5
        STORE R3, [BP - 56]         ; acc += A[i][k] * x[k]

        ADDI R4, R4, 1              ; k = k + 1
        JMP  MVM_LOOP_K

MVM_STORE_YI:
        LOAD R1, [BP - 24]          ; base_y
        LOAD R2, [BP - 48]          ; i
        LOAD R3, [BP - 56]          ; acc
        CALL VEC_SET                ; y[i] = acc

        LOAD R5, [BP - 48]
        ADDI R5, R5, 1
        STORE R5, [BP - 48]         ; i = i + 1
        JMP  MVM_LOOP_I

MVM_FIN:
        LOAD R1, [BP - 24]
        ADDI R2, R0, 0
        CALL VEC_GET                ; R5 = y[0]
        LEAVE
        POP  R4
        POP  R3
        POP  R2
        POP  R1
        RET
