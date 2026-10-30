; Tomado de LP02---CacaoCore_64: src/examples/assembler/alg_euc_res.asm
; Algoritmo de Euclides por restas, con direcciones hexadecimales
.data
    temp: 0
.text
    #Definicion variable a
    MOVD 0x00000177, 756
    #Definicion varibale b
    MOVD 0x000005FF, 924
    MOVD R0, 0x00000177
    MOVD R1, 0x000005FF

    LOOP:
        CMP R0, R1
        JZ FIN
        JG GREATER
        SUB R1, R0
        JMP LOOP
    
    GREATER:
        SUB R0, R1
        JMP LOOP

    FIN:
        MOVD 0x00001D36, R1
        #Impresion a consola
        MOVW [temp], R1
        MOVH R10, 0
        LEA R11, [temp]
        MOVW R12, 1
        INTR 0
        HLT

