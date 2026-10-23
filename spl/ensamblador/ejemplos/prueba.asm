; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Programa de prueba del analizador lexico del ensamblador SPL
; Suma los elementos de un vector y guarda el resultado; incluye errores
; lexicos intencionales (marcados con "ERROR") para verificar la recuperacion.
; ==============================================================================

        .data
        .org    0x00201000
vector: .word   10, -3, 0x1F, 0b1010      ; enteros dec, hex y bin con negativo
pi:     .word   3.14159, -2.5e-3, 6e2     ; flotantes IEEE 754 binary64
mascara: .byte  0xFF, 0b00001111
total:  .word   0

        .text
        .org    0x00200000
main:
        ADDI    R1, R0, 0x0020            ; R1 = base del vector
        SHL     R1, R1, 16
        ADDI    R1, R1, #0x1000           ; '#' opcional antes de un inmediato
        addi    r2, r0, 4                 ; minusculas: mnemonicos y registros caseless
        XOR     R3, R3, R3
ADDR:   LOAD    R4, [R1 + 0]              ; ADDR es etiqueta, no ADD + R
        ADD     R3, R3, R4
        ADDI    R1, R1, 8
        DEC     R2
        CMP     R2, R0
        JNZ     ADDR
        STORE   R3, [BP-8]                ; '-' tras registro: operador resta
        LDB     R5, (SP)                  ; indirecto con parentesis
        PUSH    RV
        CALL    rutina
        JMP     fin

rutina: ENTER   16
        SUBI    R4, R4, -1                ; '-' tras coma: signo del literal
        LEAVE
        RET

fin:    HLT

; ----------------------------- errores intencionales -------------------------
        MOV     R1, @R2                   ; ERROR: '@' no es un caracter valido
        ADDI    R8, R0, 1                 ; ERROR: R8 no existe
        .float  1.5                       ; ERROR: directiva desconocida
        ADDI    R1, R0, 0b102             ; ERROR: literal binario mal formado
        ADDI    R1, R0, 0x1FFFFFFFFFFFFFFFF ; ERROR: excede 64 bits
LOAD:   NOT     R1                        ; ERROR: mnemonico usado como etiqueta
        JMP     $fin                      ; ERROR: '$' no es un caracter valido
