; ============================================================================
; ESCENARIO INTEGRAL 2 - Módulo Ensamblador FPU Enigma-64
; Configura constantes en punto flotante IEEE 754 (binary64) e invoca rutina
; ============================================================================

        .data
        .org    0x00201000
constantes_fpu:
        .word   2.0, 0.5, 1.5e3, -2.5e-3
mascara_cfg:
        .byte   0xFF, 0b00001010

        .text
        .org    0x00200000
inicio_fpu:
        ENTER   16
        ADDI    R1, R0, 0x0020
        SHL     R1, R1, 16
        ADDI    R1, R1, 0x1000
        LOAD    R2, [R1 + 0]
        LOAD    R3, [R1 + 8]
        CALL    paso_newton
        STORE   RV, [BP - 8]
        LEAVE
        HLT

paso_newton:
        ADD     RV, R2, R3
        SHR     RV, RV, 1
        RET

