; Tomado de LP02---CacaoCore_64: src/examples/assembler/search_max_vars.asm
; Busqueda del maximo de a1..a5
.data
    a1: 1
    a2: 8
    a3: 4
    a4: 2
    a5: 10
    n: 5
    temp: 0
.text
    # Declaramos el arreglo en la zona de datos esaticos
    # [1, 8, 4, 2, 10]

    # Código de busqueda Maximo
    MOVH R0, [n]
    MOVH R1, 0
    MOVH R2, [a1]
    INC R1
    DEC R0
    LOOP:
        CMP R1, R0
        JG END
        MOVD R4, R1
        MUL R4, 8
        LEA R5, [a1]
        ADD R4, R5
        MOVH R6, [R4]
        CMP R6, R2
        JLE NO_REASIGN
        MOVD R2, R6

    NO_REASIGN:
        INC R1
        JMP LOOP

    END:
        MOVW [temp], R2
        MOVH R10, 0
        LEA R11, [temp]
        MOVW R12, 1
        INTR 0
        HLT

