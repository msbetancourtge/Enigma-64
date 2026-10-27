; Tomado de LP02---CacaoCore_64: src/examples/assembler/bubble_sort.asm
; Ordenamiento burbuja sobre a1..a5 con aritmetica de punteros
.data
    a1: 5
    a2: 3
    a3: 8
    a4: 1
    a5: 4
    temp: 0

.text
    LEA R0, [a1]
    MOVH R1, 5
    MOVH R2, 0

    LOOP_EXTERNO:
        MOVH R8, R1
        DEC R8
        CMP R2, R8
        JG FIN_EXTERNO
        MOVH R3, 0
        NOP
        LOOP_INTERNO:
            CMP R3, R8
            JGE FIN_INTERNO
            MOVH R6, R3
            MUL R6, 8
            ADD R6, R0
            MOVH R7, R6
            ADD R7, 8
            MOVH R4, [R6]
            MOVH R5, [R7]
            CMP R4, R5 
            JLE NO_SWAP
            MOVH [R6], R5
            MOVH [R7], R4
            NO_SWAP:
                INC R3
                JMP LOOP_INTERNO
            FIN_INTERNO:
                INC R2
                JMP LOOP_EXTERNO
        FIN_EXTERNO:
            MOVH R3, 0
            DEC R1
        
        LOOP_IMP:
            CMP R3, R1
            JG FIN_IMP
            MOVH R4, R3
            MUL R4, 8
            ADD R4, R0
            MOVH R2, [R4]
        # PRINT lo que esté en R2
            MOVD [temp], R2
            MOVH R10, 0
            LEA R11, [temp]
            MOVW R12, 1
            INTR 0 
            INC R3
            JMP LOOP_IMP
        FIN_IMP:
            HLT

