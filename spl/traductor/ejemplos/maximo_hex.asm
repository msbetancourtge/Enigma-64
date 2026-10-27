; Tomado de LP02---CacaoCore_64: src/examples/assembler/search_max.asm
; Busqueda del maximo con direcciones hexadecimales
.text
    # Declaramos el arreglo en la zona de datos esaticos
    # [1, 8, 4, 2, 10]

    MOVH 0x00040000, 1
    MOVH 0x00040008, 8
    MOVH 0x00040010, 4
    MOVH 0x00040018, 2
    MOVH 0x00040020, 10

    # Declaramos el tamaño luego del arreglo
    MOVH 0x00040028, 5
    # Código de busqueda Maximo
    MOVH R0, 0x00040028
    MOVH R1, 0
    MOVH R2, 0x00040000
    INC R1
    DEC R0
    LOOP:
        CMP R1, R0
        JG END
        MOVD R4, R1
        MUL R4, 8
        LEA R5, 0x00040000
        ADD R4, R5
        MOVH R6, [R4]
        CMP R6, R2
        JLE NO_REASIGN
        MOVD R2, R6

    NO_REASIGN:
        INC R1
        JMP LOOP

    END:
        MOVW 0x00040030, R2
        MOVH R10, 0
        LEA R11, 0x00040030
        MOVW R12, 1
        INTR 0
        HLT

