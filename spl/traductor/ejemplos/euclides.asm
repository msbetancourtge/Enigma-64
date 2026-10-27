; Tomado de LP02---CacaoCore_64: src/examples/assembler/alg_euc_mod.asm
; Algoritmo de Euclides por residuo (DIV deja el residuo en el 2o registro)
.data
    a: 987654
    b: 123456
    temp: 0
.text
    MOVD R0, [a]
    MOVD R1, [b]
    MOVD R2, 1

    CMP R0, R1
    JG GREATER
    LOOP:
        CMP R2, 0
        JZ FIN
        MOVD R2, R0
        MOVD R3, R1
        DIV R3, R2
        MOVD R1, R0
        MOVD R0, R2
        JMP LOOP
    
    GREATER:
        MOVD R9, R0
        MOVD R0, R1
        MOVD R1, R9
        JMP LOOP

    FIN:
        MOVW [temp], R1
        MOVH R10, 0
        LEA R11, [temp]
        MOVW R12, 1
        INTR 0
        HLT

