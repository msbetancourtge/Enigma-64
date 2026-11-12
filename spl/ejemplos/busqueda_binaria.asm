; ==============================================================================
; busqueda_binaria.asm - Problema Computacional 2B: Busqueda Binaria en Vector
; Tarea 29: Integrante 7 (Algoritmos 2 y 3 & Suite de Tests)
;
; Ejecuta busqueda binaria O(log N) sobre un vector ordenado de enteros de
; 64 bits con signo para una lista de consultas.
;
; Distribucion de memoria:
;   - Vector ordenado V : 0x00220000 (slot descriptor 0 en 0x00210000)
;   - Vector consultas Q: 0x00221000 (slot descriptor 1 en 0x00210020)
;   - Vector indices R  : 0x002E0000 (slot descriptor 2 en 0x00210040)
;   - Registro R5       : indice encontrado para Q[0] (o -1 si no existe)
; ==============================================================================
#include "estructuras.inc"

PRINCIPAL:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000 (alineado a 8 bytes)

        ; R1 = base_V (0x00220000)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16

        ; Verificar si el vector V ya fue precargado externamente en RAM
        LOAD R5, [R1 - 16]
        CMP  R5, R0
        JNZ  EJECUTAR_BUSQUEDAS

        CALL VEC_LEN
        CMP  R5, R0
        JNZ  EJECUTAR_BUSQUEDAS

        ; --- Inicializacion Autonoma por Defecto ---
        ; Vector ordenado V (N = 8): [-20, -5, 0, 7, 15, 23, 42, 88]
        ADDI R1, R0, 0              ; slot 0
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16             ; base_V = 0x00220000
        ADDI R3, R0, 8              ; N = 8
        CALL DESC_VEC_INIT

        ADD  R1, R2, R0
        ADDI R2, R0, 0
        ADDI R3, R0, -20
        CALL VEC_SET                ; V[0] = -20

        ADDI R2, R0, 1
        ADDI R3, R0, -5
        CALL VEC_SET                ; V[1] = -5

        ADDI R2, R0, 2
        ADDI R3, R0, 0
        CALL VEC_SET                ; V[2] = 0

        ADDI R2, R0, 3
        ADDI R3, R0, 7
        CALL VEC_SET                ; V[3] = 7

        ADDI R2, R0, 4
        ADDI R3, R0, 15
        CALL VEC_SET                ; V[4] = 15

        ADDI R2, R0, 5
        ADDI R3, R0, 23
        CALL VEC_SET                ; V[5] = 23

        ADDI R2, R0, 6
        ADDI R3, R0, 42
        CALL VEC_SET                ; V[6] = 42

        ADDI R2, R0, 7
        ADDI R3, R0, 88
        CALL VEC_SET                ; V[7] = 88

        ; Vector de consultas Q (M = 4) en 0x00221000: [23, -20, 88, 19]
        ; Indices esperados en R: [5, 0, 7, -1]
        ADDI R1, R0, 1              ; slot 1
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16
        ADDI R2, R2, DESP_VECTOR_2            ; base_Q = 0x00221000
        ADDI R3, R0, 4              ; M = 4
        CALL DESC_VEC_INIT

        ADD  R1, R2, R0
        ADDI R2, R0, 0
        ADDI R3, R0, 23
        CALL VEC_SET                ; Q[0] = 23

        ADDI R2, R0, 1
        ADDI R3, R0, -20
        CALL VEC_SET                ; Q[1] = -20

        ADDI R2, R0, 2
        ADDI R3, R0, 88
        CALL VEC_SET                ; Q[2] = 88

        ADDI R2, R0, 3
        ADDI R3, R0, 19
        CALL VEC_SET                ; Q[3] = 19

EJECUTAR_BUSQUEDAS:
        ; Inicializar vector de resultados R en 0x002E0000 con longitud M = VEC_LEN(Q)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16
        ADDI R1, R1, DESP_VECTOR_2            ; R1 = base_Q (0x00221000)
        CALL VEC_LEN                ; R5 = M
        ADD  R4, R5, R0             ; R4 = M

        ADDI R1, R0, 2              ; slot 2
        ADDI R2, R0, 0x002E
        SHL  R2, R2, 16             ; base_R = 0x002E0000
        ADD  R3, R4, R0             ; longitud M
        CALL DESC_VEC_INIT

        ; Bucle de consultas q = 0 .. M - 1
        ADDI R4, R0, 0              ; R4 = q = 0

BB_LOOP_CONSULTAS:
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16
        ADDI R1, R1, DESP_VECTOR_2            ; R1 = base_Q
        CALL VEC_LEN                ; R5 = M
        CMP  R4, R5                 ; q - M
        JN   BB_PROCESAR_CONSULTA
        JMP  BB_FIN_PROGRAMA

BB_PROCESAR_CONSULTA:
        ; Leer objetivo = Q[q]
        ADD  R2, R4, R0             ; R2 = q
        CALL VEC_GET                ; R5 = Q[q]
        ADD  R3, R5, R0             ; R3 = objetivo

        ; Obtener N = VEC_LEN(base_V)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16             ; R1 = base_V
        CALL VEC_LEN
        ADD  R2, R5, R0             ; R2 = N

        ; Ejecutar busqueda binaria: VEC_BIN_SEARCH(base_V, N, objetivo)
        CALL VEC_BIN_SEARCH         ; R5 = indice o -1

        ; Guardar en R[q]
        ADDI R1, R0, 0x002E
        SHL  R1, R1, 16             ; R1 = base_R
        ADD  R2, R4, R0             ; R2 = q
        ADD  R3, R5, R0             ; R3 = indice encontrado
        CALL VEC_SET

        ADDI R4, R4, 1              ; q = q + 1
        JMP  BB_LOOP_CONSULTAS

BB_FIN_PROGRAMA:
        ; Dejar en R5 el primer resultado R[0]
        ADDI R1, R0, 0x002E
        SHL  R1, R1, 16
        ADDI R2, R0, 0
        CALL VEC_GET                ; R5 = R[0]
        HLT

; ------------------------------------------------------------------------------
; VEC_BIN_SEARCH: Busqueda binaria iterativa en vector ordenado ascendentemente.
;   Entradas : R1 = base_V, R2 = N, R3 = objetivo
;   Salida   : R5 = indice en [0, N-1] si V[indice] == objetivo, o -1 si no esta
;   Preserva : R1..R4, SP, BP
;   Marco tras PUSH R1..R4 y ENTER 24:
;     [BP + 32] R1 (base_V)
;     [BP + 24] R2 (N)
;     [BP + 16] R3 (objetivo)
;     [BP + 8]  R4
;     [BP - 8]  lo
;     [BP - 16] hi
;     [BP - 24] mid
; ------------------------------------------------------------------------------
VEC_BIN_SEARCH:
        PUSH R1
        PUSH R2
        PUSH R3
        PUSH R4
        ENTER 24

        ; Si N <= 0, retornar -1
        CMP  R0, R2                 ; 0 - N
        JZ   VBS_NO_ENCONTRADO
        JN   VBS_INIT_RANGO
        JMP  VBS_NO_ENCONTRADO

VBS_INIT_RANGO:
        STORE R0, [BP - 8]          ; lo = 0
        SUBI R5, R2, 1              ; hi = N - 1
        STORE R5, [BP - 16]

VBS_BUCLE:
        LOAD R1, [BP - 8]           ; R1 = lo
        LOAD R2, [BP - 16]          ; R2 = hi
        CMP  R2, R1                 ; hi - lo
        JN   VBS_NO_ENCONTRADO      ; si hi < lo, no existe

        ; mid = lo + ((hi - lo) >> 1)
        SUB  R5, R2, R1
        SHR  R5, R5, 1
        ADD  R5, R1, R5
        STORE R5, [BP - 24]         ; mid

        ; Leer V[mid]
        LOAD R1, [BP + 32]          ; base_V
        LOAD R2, [BP - 24]          ; mid
        CALL VEC_GET                ; R5 = V[mid]

        LOAD R3, [BP + 16]          ; R3 = objetivo
        CMP  R5, R3                 ; V[mid] - objetivo
        JZ   VBS_ENCONTRADO
        JN   VBS_MITAD_DERECHA      ; si V[mid] < objetivo, buscar en [mid + 1, hi]

        ; V[mid] > objetivo: buscar en [lo, mid - 1]
        LOAD R5, [BP - 24]
        SUBI R5, R5, 1
        STORE R5, [BP - 16]         ; hi = mid - 1
        JMP  VBS_BUCLE

VBS_MITAD_DERECHA:
        LOAD R5, [BP - 24]
        ADDI R5, R5, 1
        STORE R5, [BP - 8]          ; lo = mid + 1
        JMP  VBS_BUCLE

VBS_ENCONTRADO:
        LOAD R5, [BP - 24]          ; R5 = mid
        JMP  VBS_SALIR

VBS_NO_ENCONTRADO:
        ADDI R5, R0, -1             ; R5 = -1

VBS_SALIR:
        LEAVE
        POP  R4
        POP  R3
        POP  R2
        POP  R1
        RET
