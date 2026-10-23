; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Modulo FPU: FCMP (Comparacion IEEE 754 Doble Precision - binary64)
; Autor: Michael Stiven Betancourt Gelves
;
; Contenido:
;   1. FCMP: comparacion quieta de dos patrones IEEE-754 binary64.
;
; Convencion de llamada:
;   * Entrada: R1 = operando A, R2 = operando B.
;   * Salida: R5 = -1 si A < B, 0 si A == B, 1 si A > B,
;             2 si la comparacion es unordered por NaN.
;   * -1 se representa como 0xFFFFFFFFFFFFFFFF en el registro de 64 bits.
;
; Reglas IEEE-754:
;   * +0 y -0 son iguales.
;   * Los NaN no tienen orden y producen 2.
;   * Los infinitos respetan el orden numerico.
;   * No se modifica el estado de excepciones de la CPU.
; ==============================================================================\n
FCMP:
    ENTER 32
    STORE R1, [BP - 8]
    STORE R2, [BP - 16]

    ; abs(x) = x sin el bit de signo; R4 = +infinito.
    SHL R3, R1, 1
    SHR R3, R3, 1
    SHL R4, R2, 1
    SHR R4, R4, 1
    ADDI R5, R0, 0x07FF
    SHL R5, R5, 52

    ; NaN: exponente 0x7FF y fraccion distinta de cero.
    CMP R5, R3
    JC FCMP_UNORDERED
    CMP R5, R4
    JC FCMP_UNORDERED

    ; +0 y -0 son iguales.
    CMP R3, R0
    JNZ FCMP_NO_A_ZERO
    CMP R4, R0
    JZ FCMP_EQUAL
FCMP_NO_A_ZERO:
    CMP R4, R0
    JZ FCMP_SIGNED_RESULT

    ; Signos distintos: el negativo es menor.
    LOAD R1, [BP - 8]
    LOAD R2, [BP - 16]
    SHR R1, R1, 63
    SHR R2, R2, 63
    CMP R1, R2
    JZ FCMP_SAME_SIGN
    CMP R1, R0
    JZ FCMP_GREATER
    JMP FCMP_LESS

FCMP_SAME_SIGN:
    ; Mismos signos: comparar magnitudes y cambiar el sentido para negativos.
    LOAD R1, [BP - 8]
    LOAD R2, [BP - 16]
    SHL R1, R1, 1
    SHR R1, R1, 1
    SHL R2, R2, 1
    SHR R2, R2, 1
    CMP R1, R2
    JZ FCMP_EQUAL
    JC FCMP_MAG_A_LESS
    ; A tiene mayor magnitud.
    LOAD R1, [BP - 8]
    SHR R1, R1, 63
    CMP R1, R0
    JZ FCMP_GREATER
    JMP FCMP_LESS
FCMP_MAG_A_LESS:
    LOAD R1, [BP - 8]
    SHR R1, R1, 63
    CMP R1, R0
    JZ FCMP_LESS
    JMP FCMP_GREATER

FCMP_SIGNED_RESULT:
    ; Solo uno es cero: el signo del cero no altera el orden numerico.
    LOAD R1, [BP - 8]
    SHR R1, R1, 63
    CMP R1, R0
    JZ FCMP_GREATER
    JMP FCMP_LESS
FCMP_UNORDERED:
    ADDI R5, R0, 2
    LEAVE
    RET
FCMP_EQUAL:
    ADDI R5, R0, 0
    LEAVE
    RET
FCMP_LESS:
    ADDI R5, R0, -1
    LEAVE
    RET
FCMP_GREATER:
    ADDI R5, R0, 1
    LEAVE
    RET
