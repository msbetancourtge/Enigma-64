; ==============================================================================
; prueba_cabeceras_cargador.asm - Prueba integral de estructuras.inc y cabeceras.
; Tarea 29 - Integrante 4 (Cargador, Directivas, Cabeceras y Enlace).
;
; Verifica en la CPU real de Enigma-64:
;   1. Inclusion maestra con #include "estructuras.inc" sin ejecucion por caida.
;   2. Construccion de descriptores en BASE_CABECERAS (0x00210000) mediante
;      DESC_VEC_INIT y DESC_MAT_INIT.
;   3. Sincronizacion de cabeceras inline con VEC_LEN, MAT_ROWS y MAT_COLS.
;   4. Consultores O(1): DESC_ADDR, DESC_GET_TIPO, DESC_GET_BASE,
;      DESC_GET_FILAS y DESC_GET_COLS.
;   5. Preservacion estricta de R1..R4 y balanceo de SP = 0x00400000.
;
; Estado esperado en RES = 0x002E0000 (BASE_BUFFERS) al llegar a HLT:
;   RES[0] = 0x00210000   direccion descriptor slot 0 (vector V)
;   RES[1] = 5            VEC_LEN(0x00220000) leido tras DESC_VEC_INIT
;   RES[2] = 0x00210020   direccion descriptor slot 1 (matriz M 3x4)
;   RES[3] = 3            MAT_ROWS(0x00260000)
;   RES[4] = 4            MAT_COLS(0x00260000)
;   RES[5] = 2            DESC_GET_TIPO(0x00210020) -> TIPO_MATRIZ
;   RES[6] = 0x00260000   DESC_GET_BASE(0x00210020)
;   RES[7] = 3            DESC_GET_FILAS(0x00210020)
;   RES[8] = 4            DESC_GET_COLS(0x00210020)
;   RES[9] = 10           MAT_INIT(0x00260200, 2, 5) -> 2 * 5 = 10
; ==============================================================================
#include "estructuras.inc"

INICIO:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000 (alineada a 8 bytes)
        ADDI R4, R0, 0x002E
        SHL  R4, R4, 16             ; R4 = RES = 0x002E0000 (BASE_BUFFERS)

; 1) Construir descriptor de vector en slot 0: V en 0x00220000 con N = 5
        ADDI R1, R0, 0              ; slot = 0
        ADDI R2, R0, 0x0022
        SHL  R2, R2, 16             ; base = 0x00220000 (BASE_VECTORES)
        ADDI R3, R0, 5              ; N = 5
        CALL DESC_VEC_INIT          ; R5 = 0x00210000
        STORE R5, [R4 + 0]          ; RES[0] = 0x00210000

        ADD  R1, R2, R0             ; R1 = 0x00220000 (R2 fue preservado)
        CALL VEC_LEN                ; R5 = [0x00220000 - 8] = 5
        STORE R5, [R4 + 8]          ; RES[1] = 5

; 2) Construir descriptor de matriz en slot 1: M en 0x00260000 de 3 x 4
        PUSH R4                     ; guarda puntero RES
        ADDI R1, R0, 1              ; slot = 1
        ADDI R2, R0, 0x0026
        SHL  R2, R2, 16             ; base = 0x00260000 (BASE_MATRICES)
        ADDI R3, R0, 3              ; F = 3
        ADDI R4, R0, 4              ; C = 4
        CALL DESC_MAT_INIT          ; R5 = 0x00210020
        POP  R4                     ; recupera puntero RES
        STORE R5, [R4 + 16]         ; RES[2] = 0x00210020

; 3) Verificar cabeceras inline de la matriz con MAT_ROWS y MAT_COLS
        ADD  R1, R2, R0             ; R1 = 0x00260000
        CALL MAT_ROWS
        STORE R5, [R4 + 24]         ; RES[3] = 3
        CALL MAT_COLS
        STORE R5, [R4 + 32]         ; RES[4] = 4

; 4) Consultar campos del descriptor en slot 1 usando DESC_ADDR y DESC_GET_*
        ADDI R1, R0, 1
        CALL DESC_ADDR              ; R5 = 0x00210020
        ADD  R1, R5, R0
        CALL DESC_GET_TIPO
        STORE R5, [R4 + 40]         ; RES[5] = 2
        CALL DESC_GET_BASE
        STORE R5, [R4 + 48]         ; RES[6] = 0x00260000
        CALL DESC_GET_FILAS
        STORE R5, [R4 + 56]         ; RES[7] = 3
        CALL DESC_GET_COLS
        STORE R5, [R4 + 64]         ; RES[8] = 4

; 5) MAT_INIT directo sobre matriz secundaria en 0x00260200 (2 x 5 = 10)
        ADDI R1, R0, 0x0026
        SHL  R1, R1, 16
        ADDI R1, R1, 0x0200         ; R1 = 0x00260200
        ADDI R2, R0, 2              ; F = 2
        ADDI R3, R0, 5              ; C = 5
        CALL MAT_INIT               ; R5 = 10
        STORE R5, [R4 + 72]         ; RES[9] = 10

        HLT
