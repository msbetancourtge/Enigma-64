#pragma once
#ifndef CABECERAS_ASM
#define CABECERAS_ASM
; ==============================================================================
; cabeceras.asm - Constructores y descriptores de cabeceras en memoria.
; Tarea 29 - Integrante 4: Cargador, Directivas, Cabeceras y Enlace.
;
; Implementa el modelo dual de metadatos sobre palabras de 64 bits (Big-Endian,
; alineadas estrictamente a multiplos de 8 bytes en RAM):
;
;   1) Tabla de Descriptores en Zona 1 (BASE_CABECERAS = 0x00210000):
;      Cada ranura (slot = 0, 1, 2, ...) ocupa 32 bytes (4 palabras de 64 bits):
;        [dir_desc +  0] = tipo  (1 = vector 1D, 2 = matriz 2D)
;        [dir_desc +  8] = base  (direccion del primer elemento, multiplo de 8)
;        [dir_desc + 16] = filas (longitud N en vector, filas F en matriz)
;        [dir_desc + 24] = cols  (1 en vector, columnas C en matriz)
;
;   2) Cabecera Inline Contigua ([base - 16] y [base - 8]):
;      - En vectores: [base - 16] = 1 (marca inicializado), [base - 8] = N
;        (compatible directamente con VEC_LEN de vec.asm y merge_sort.asm).
;      - En matrices: [base - 16] = F (filas), [base - 8] = C (columnas).
;
; Convencion ABI (identica al resto de la libreria):
;   - Argumentos en R1..R4; valor de retorno en R5 (RV).
;   - R1..R4, SP (R6) y BP (R7) son callee-saved (se preservan intactos).
;   - Solo R5 y las banderas de estado (SR) se modifican.
;   - El JMP inicial evita ejecutar las subrutinas por caida.
; ==============================================================================

        JMP CAB_FIN_LIBRERIA        ; salta las subrutinas si el flujo cae aqui

; ------------------------------------------------------------------------------
; VEC_INIT: inicializa la cabecera inline de un vector en memoria
;   Entradas: R1 = base (&v[0], multiplo de 8), R2 = N (longitud)
;   Salida:   R5 = base
;   Efecto:   [base - 16] = 1 (marca configurado), [base - 8] = N (para VEC_LEN)
; ------------------------------------------------------------------------------
VEC_INIT:
        ADDI R5, R0, 1
        STORE R5, [R1 - 16]         ; marca de estructura configurada
        STORE R2, [R1 - 8]          ; longitud N leida por VEC_LEN
        ADD  R5, R1, R0             ; retorna base en R5
        RET

; ------------------------------------------------------------------------------
; MAT_INIT: inicializa la cabecera inline de una matriz 2D en memoria
;   Entradas: R1 = base (&M[0][0], multiplo de 8), R2 = F (filas), R3 = C (cols)
;   Salida:   R5 = F * C (total de palabras de 64 bits de la matriz)
;   Efecto:   [base - 16] = F, [base - 8] = C
; ------------------------------------------------------------------------------
MAT_INIT:
        STORE R2, [R1 - 16]         ; guarda filas F en [base - 16]
        STORE R3, [R1 - 8]          ; guarda columnas C en [base - 8]
        MUL  R5, R2, R3             ; R5 = F * C
        RET

; ------------------------------------------------------------------------------
; MAT_ROWS: lee el numero de filas F de la cabecera inline de una matriz
;   Entradas: R1 = base
;   Salida:   R5 = F ([base - 16])
; ------------------------------------------------------------------------------
MAT_ROWS:
        LOAD R5, [R1 - 16]
        RET

; ------------------------------------------------------------------------------
; MAT_COLS: lee el numero de columnas C de la cabecera inline de una matriz
;   Entradas: R1 = base
;   Salida:   R5 = C ([base - 8])
; ------------------------------------------------------------------------------
MAT_COLS:
        LOAD R5, [R1 - 8]
        RET

; ------------------------------------------------------------------------------
; DESC_ADDR: calcula la direccion en BASE_CABECERAS del descriptor en 'slot'
;   Entradas: R1 = slot (0, 1, 2, ...)
;   Salida:   R5 = 0x00210000 + (slot << 5)
; ------------------------------------------------------------------------------
DESC_ADDR:
        PUSH R2                     ; preserva R2
        ADDI R2, R0, 0x0021
        SHL  R2, R2, 16             ; R2 = 0x00210000 (BASE_CABECERAS)
        SHL  R5, R1, 5              ; R5 = slot * 32 bytes
        ADD  R5, R2, R5             ; R5 = BASE_CABECERAS + slot * 32
        POP  R2                     ; restaura R2
        RET

; ------------------------------------------------------------------------------
; DESC_VEC_INIT: construye un descriptor de vector en BASE_CABECERAS y su
;                cabecera inline [base - 16] / [base - 8]
;   Entradas: R1 = slot, R2 = base, R3 = N (longitud)
;   Salida:   R5 = direccion del descriptor (0x00210000 + slot * 32)
; ------------------------------------------------------------------------------
DESC_VEC_INIT:
        PUSH R4                     ; preserva R4
        ADDI R4, R0, 0x0021
        SHL  R4, R4, 16             ; R4 = 0x00210000 (BASE_CABECERAS)
        SHL  R5, R1, 5              ; R5 = slot * 32
        ADD  R5, R4, R5             ; R5 = dir_desc
        ADDI R4, R0, 1              ; R4 = TIPO_VECTOR (1)
        STORE R4, [R5 + 0]          ; [dir_desc + 0]  = 1 (vector 1D)
        STORE R2, [R5 + 8]          ; [dir_desc + 8]  = base
        STORE R3, [R5 + 16]         ; [dir_desc + 16] = longitud N
        STORE R4, [R5 + 24]         ; [dir_desc + 24] = 1 (dimension secundaria)
        STORE R4, [R2 - 16]         ; [base - 16]     = 1 (marca inicializado)
        STORE R3, [R2 - 8]          ; [base - 8]      = N (compatible VEC_LEN)
        POP  R4                     ; restaura R4
        RET

; ------------------------------------------------------------------------------
; DESC_MAT_INIT: construye un descriptor de matriz en BASE_CABECERAS y su
;                cabecera inline [base - 16] = F, [base - 8] = C
;   Entradas: R1 = slot, R2 = base, R3 = F (filas), R4 = C (columnas)
;   Salida:   R5 = direccion del descriptor (0x00210000 + slot * 32)
; ------------------------------------------------------------------------------
DESC_MAT_INIT:
        PUSH R1                     ; preserva slot
        ADDI R5, R0, 0x0021
        SHL  R5, R5, 16             ; R5 = 0x00210000 (BASE_CABECERAS)
        SHL  R1, R1, 5              ; R1 = slot * 32
        ADD  R5, R5, R1             ; R5 = dir_desc
        ADDI R1, R0, 2              ; R1 = TIPO_MATRIZ (2)
        STORE R1, [R5 + 0]          ; [dir_desc + 0]  = 2 (matriz 2D)
        STORE R2, [R5 + 8]          ; [dir_desc + 8]  = base
        STORE R3, [R5 + 16]         ; [dir_desc + 16] = filas F
        STORE R4, [R5 + 24]         ; [dir_desc + 24] = columnas C
        STORE R3, [R2 - 16]         ; [base - 16]     = filas F (MAT_ROWS)
        STORE R4, [R2 - 8]          ; [base - 8]      = columnas C (MAT_COLS)
        POP  R1                     ; restaura R1
        RET

; ------------------------------------------------------------------------------
; Consultores O(1) de campos de un descriptor en BASE_CABECERAS
;   Entradas: R1 = dir_desc (direccion devuelta por DESC_ADDR / DESC_*_INIT)
;   Salida:   R5 = valor de 64 bits del campo solicitado
; ------------------------------------------------------------------------------
DESC_GET_TIPO:
        LOAD R5, [R1 + 0]
        RET

DESC_GET_BASE:
        LOAD R5, [R1 + 8]
        RET

DESC_GET_FILAS:
        LOAD R5, [R1 + 16]
        RET

DESC_GET_COLS:
        LOAD R5, [R1 + 24]
        RET

CAB_FIN_LIBRERIA:
#endif
