; ==============================================================================
; producto_punto.asm - Problema Computacional 2A: Producto Punto de Vectores
; Tarea 29: Integrante 7 (Algoritmos 2 y 3 & Suite de Tests)
;
; Calcula el producto escalar (dot product) de dos vectores de 64 bits:
;   dot(A, B) = sum_{k=0}^{N-1} (A[k] * B[k])
;
; Distribucion de memoria:
;   - Vector A      : 0x00220000 (slot descriptor 0 en 0x00210000)
;   - Vector B      : 0x00221000 (slot descriptor 1 en 0x00210020)
;   - Resultado     : 0x002E0000 (vector de longitud 1 con dot(A, B), slot 2)
;   - Registro R5   : conserva el valor final de dot(A, B) al ejecutar HLT
; ==============================================================================
#include "estructuras.inc"

PRINCIPAL:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000 (alineado a 8 bytes)

        ; R1 = base_A (0x00220000)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16

        ; Verificar si el vector A ya fue precargado externamente en RAM
        LOAD R5, [R1 - 16]
        CMP  R5, R0
        JNZ  EJECUTAR_PRODUCTO_PUNTO

        CALL VEC_LEN
        CMP  R5, R0
        JNZ  EJECUTAR_PRODUCTO_PUNTO

        ; --- Inicializacion Autonoma por Defecto (N = 5) ---
        ; A = [3, -4, 7, 2, -5]
        ; B = [6, 5, 2, -3, -4]
        ; dot(A, B) = 18 - 20 + 14 - 6 + 20 = 26
        ADDI R1, R0, 0              ; slot 0
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16             ; base_A = 0x00220000
        ADDI R3, R0, 5              ; N = 5
        CALL DESC_VEC_INIT

        ADD  R1, R2, R0             ; R1 = base_A
        ADDI R2, R0, 0
        ADDI R3, R0, 3
        CALL VEC_SET                ; A[0] = 3

        ADDI R2, R0, 1
        ADDI R3, R0, -4
        CALL VEC_SET                ; A[1] = -4

        ADDI R2, R0, 2
        ADDI R3, R0, 7
        CALL VEC_SET                ; A[2] = 7

        ADDI R2, R0, 3
        ADDI R3, R0, 2
        CALL VEC_SET                ; A[3] = 2

        ADDI R2, R0, 4
        ADDI R3, R0, -5
        CALL VEC_SET                ; A[4] = -5

        ; Inicializar Vector B en 0x00221000 (slot 1)
        ADDI R1, R0, 1              ; slot 1
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16
        ADDI R2, R2, DESP_VECTOR_2            ; base_B = 0x00221000
        ADDI R3, R0, 5              ; N = 5
        CALL DESC_VEC_INIT

        ADD  R1, R2, R0             ; R1 = base_B
        ADDI R2, R0, 0
        ADDI R3, R0, 6
        CALL VEC_SET                ; B[0] = 6

        ADDI R2, R0, 1
        ADDI R3, R0, 5
        CALL VEC_SET                ; B[1] = 5

        ADDI R2, R0, 2
        ADDI R3, R0, 2
        CALL VEC_SET                ; B[2] = 2

        ADDI R2, R0, 3
        ADDI R3, R0, -3
        CALL VEC_SET                ; B[3] = -3

        ADDI R2, R0, 4
        ADDI R3, R0, -4
        CALL VEC_SET                ; B[4] = -4

EJECUTAR_PRODUCTO_PUNTO:
        ; R1 = base_A (0x00220000)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16
        CALL VEC_LEN                ; R5 = N
        ADD  R3, R5, R0             ; R3 = N

        ; R2 = base_B (0x00221000)
        ADD  R2, R1, R0
        ADDI R2, R2, DESP_VECTOR_2

        CALL VEC_DOT                ; R5 = dot(A, B)
        ADD  R4, R5, R0             ; R4 = resultado preservado

        ; Guardar resultado en vector de salida en 0x002E0000 (slot 2, longitud 1)
        ADDI R1, R0, 2              ; slot 2
        ADDI R2, R0, 0x002E
        SHL  R2, R2, 16             ; base_res = 0x002E0000
        ADDI R3, R0, 1              ; longitud = 1
        CALL DESC_VEC_INIT

        ADD  R1, R2, R0             ; R1 = 0x002E0000
        ADDI R2, R0, 0              ; indice 0
        ADD  R3, R4, R0             ; valor = dot(A, B)
        CALL VEC_SET

        ADD  R5, R4, R0             ; R5 = dot(A, B)
        HLT

; ------------------------------------------------------------------------------
; VEC_DOT: Calcula el producto punto de dos vectores de igual longitud N.
;   Entradas : R1 = base_A, R2 = base_B, R3 = N
;   Salida   : R5 = sum_{k=0}^{N-1} A[k] * B[k]
;   Preserva : R1..R4, SP, BP
; ------------------------------------------------------------------------------
VEC_DOT:
        PUSH R1
        PUSH R2
        PUSH R3
        PUSH R4
        ENTER 32                    ; [BP-8]=base_A, [BP-16]=base_B, [BP-24]=N, [BP-32]=acc

        STORE R1, [BP - 8]
        STORE R2, [BP - 16]
        STORE R3, [BP - 24]
        STORE R0, [BP - 32]         ; acc = 0

        ADDI R4, R0, 0              ; k = 0

VD_BUCLE:
        LOAD R3, [BP - 24]          ; R3 = N
        CMP  R4, R3                 ; k - N
        JN   VD_ITERAR              ; si k < N (N=1), continuar
        JMP  VD_FIN

VD_ITERAR:
        ; Leer A[k]
        LOAD R1, [BP - 8]           ; base_A
        ADD  R2, R4, R0             ; k
        CALL VEC_GET                ; R5 = A[k]
        ADD  R3, R5, R0             ; R3 = A[k]

        ; Leer B[k]
        LOAD R1, [BP - 16]          ; base_B
        ADD  R2, R4, R0             ; k
        CALL VEC_GET                ; R5 = B[k]

        ; Multiplicar y acumular: acc += A[k] * B[k]
        MUL  R5, R3, R5
        LOAD R3, [BP - 32]
        ADD  R3, R3, R5
        STORE R3, [BP - 32]

        ADDI R4, R4, 1              ; k = k + 1
        JMP  VD_BUCLE

VD_FIN:
        LOAD R5, [BP - 32]          ; R5 = acc
        LEAVE
        POP  R4
        POP  R3
        POP  R2
        POP  R1
        RET
