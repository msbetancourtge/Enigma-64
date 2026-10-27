; ============================================================================
; ESCENARIO INTEGRAL 1 - Módulo Ensamblador Enigma-64
; Calcula la suma de dos operandos de 64 bits (30 + 12 = 42) y almacena en RAM
; ============================================================================

        .data
        .org    0x00201000
valores:
        .word   30, 12, 0

        .text
        .org    0x00200000
main:
        ADDI    R1, R0, 0x0020
        SHL     R1, R1, 16
        ADDI    R1, R1, #0x1000
        LOAD    R2, [R1 + 0]
        LOAD    R3, [R1 + 8]
        ADD     R5, R2, R3
        STORE   R5, [R1 + 16]
        HLT

