; Prueba de todas las operaciones ALU de CacaoCore-64 (Integrante 2).
; Cada bloque calcula un valor conocido y lo verifica: XOR con el valor
; esperado (0 si coincide) acumulado con OR en R12, o un salto condicional
; que debe tomarse. Al final [fallos] debe valer 0.
; Usa R0..R12, R14 y R15 (ACC), asi que obliga a derramar registros.
.data
    x: 40
    y: 6
    res: 0
    fallos: 0
.text
    MOVD R12, 0
    MOVD R0, [x]
    MOVD R1, [y]

    ; --- registro-registro: ADD SUB MUL DIV AND OR XOR ---
    MOVD R2, R0
    ADD R2, R1
    XOR R2, 46
    OR R12, R2
    MOVD R3, R0
    SUB R3, R1
    XOR R3, 34
    OR R12, R3
    MOVD R4, R0
    MUL R4, R1
    XOR R4, 240
    OR R12, R4
    MOVD R5, R0
    MOVD R6, R1
    DIV R5, R6
    XOR R5, 6
    OR R12, R5
    XOR R6, 4
    OR R12, R6
    MOVD R7, 12
    MOVD R8, 10
    AND R7, R8
    XOR R7, 8
    OR R12, R7
    MOVD R8, 12
    MOVD R9, 3
    OR R8, R9
    XOR R8, 15
    OR R12, R8
    MOVD R9, 12
    XOR R9, R1
    XOR R9, 10
    OR R12, R9

    ; --- registro-inmediato (incluye inmediatos de mas de 16 bits) ---
    MOVD R2, 46
    ADD R2, 4
    XOR R2, 50
    OR R12, R2
    MOVD R3, 34
    SUB R3, 40000
    XOR R3, -39966
    OR R12, R3
    MOVD R4, 240
    MUL R4, -2
    XOR R4, -480
    OR R12, R4
    MOVD R5, 6
    DIV R5, 4
    XOR R5, 1
    OR R12, R5

    ; --- registro-memoria y registro-indirecto ---
    MOVD R2, 50
    ADD R2, [y]
    XOR R2, 56
    OR R12, R2
    MOVD R7, 8
    MUL R7, [y]
    XOR R7, 48
    OR R12, R7
    MOVD R8, 15
    AND R8, [x]
    XOR R8, 8
    OR R12, R8
    LEA R10, [x]
    MOVD R2, 56
    ADD R2, [R10]
    XOR R2, 96
    OR R12, R2

    ; --- formas de acumulador (operando implicito ACC = R15) ---
    LOADD 100
    ADD R1
    SUB 6
    MUL [y]
    DIV 7
    AND 255
    OR 2
    XOR R1
    STORED R14
    XOR R14, 81
    OR R12, R14

    ; --- INC DEC NEG NOT en registro (tambien dejan el resultado en ACC) ---
    MOVD R2, 10
    INC R2
    NEG R2
    NOT R2
    DEC R2
    STORED R14
    XOR R2, 9
    OR R12, R2
    XOR R14, 9
    OR R12, R14

    ; --- INC DEC NEG NOT en memoria ---
    INC [res]
    NEG [res]
    NOT [res]
    DEC [res]
    MOVD R3, [res]
    XOR R3, -1
    OR R12, R3

    ; --- desplazamientos (SHR es aritmetico) y rotaciones de 64 bits ---
    MOVD R4, -64
    SHR R4, 3
    SHL R4, 4
    XOR R4, -128
    OR R12, R4
    LOADD 3
    SHL 5
    SHR 2
    STORED R14
    XOR R14, 24
    OR R12, R14
    MOVD R5, 1
    ROR R5, 1
    ROL R5, 2
    ROL R5, 64
    XOR R5, 2
    OR R12, R5
    LOADD 1
    ROR 4
    STORED R14
    SHR R14, 60
    XOR R14, 1
    OR R12, R14

    ; --- SWAP ---
    MOVD R6, 111
    MOVD R7, 222
    SWAP R6, R7
    XOR R6, 222
    OR R12, R6
    LOADD 333
    SWAP R7
    STORED R14
    XOR R7, 333
    OR R12, R7
    XOR R14, 111
    OR R12, R14

    ; --- DIV con residuo entre registros derramados ---
    MOVD R10, 100
    MOVD R11, 7
    DIV R10, R11
    XOR R10, 14
    OR R12, R10
    XOR R11, 2
    OR R12, R11

    ; --- CMP TEST CMPZ: las banderas deciden saltos ---
    CMP R0, R1
    JG OK1
    INC R12
OK1:
    CMP R1, R0
    JL OK2
    INC R12
OK2:
    CMP R0, 40
    JZ OK3
    INC R12
OK3:
    TEST R0, 7
    JZ OK4
    INC R12
OK4:
    TEST R0, 8
    JNZ OK5
    INC R12
OK5:
    CMPZ R1
    JS OK6
    INC R12
OK6:
    MOVD R9, 0
    CMPZ R9
    JZ OK7
    INC R12
OK7:
    CMP R1, R0
    JGE MAL8
    JMP OK8
MAL8:
    INC R12
OK8:
    LOADD 5
    CMP 5
    JZ OK9
    INC R12
OK9:
    TEST [x]
    JZ OK10
    INC R12
OK10:
    CMP R0, [x]
    JZ OK11
    INC R12
OK11:
    CMPZ [y]
    JLE OK12
    INC R12
OK12:
    ; las banderas sobreviven a instrucciones que en CacaoCore no las tocan
    CMP R0, R1
    MOVD R2, 12345
    SWAP R3, R4
    ROL R5, 3
    LEA R11, [res]
    JG OK13
    INC R12
OK13:
    MOVD [fallos], R12
    HLT
