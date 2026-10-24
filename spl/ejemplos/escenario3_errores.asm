; ============================================================================
; ESCENARIO INTEGRAL 3 - Recuperación de Errores Léxicos en Ensamblador
; ============================================================================

        .text
        .org    0x00200000
main:
        ADDI    R1, R0, 99
        MOV     R2, @R1                   ; ERROR 1: caracter ilegal '@'
        ADDI    R8, R0, 1                 ; ERROR 2: registro inexistente R8
        .float  3.14                      ; ERROR 3: directiva desconocida .float
        ADDI    R3, R0, 0b102             ; ERROR 4: literal binario mal formado
        STORE   R1, [R0 + 64]             ; Instrucción válida tras recuperación
        HLT

