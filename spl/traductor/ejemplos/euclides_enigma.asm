; Traduccion automatica CacaoCore-64 -> Enigma-64
; Temporales: TMP1=R4  TMP2=R5   Pila: R6   Datos: 0x00201000
; ACC sincronizado: no (el programa nunca lee R15)
; Asignacion de registros:
;   R0         -> R2
;   R1         -> R3
;   R2         -> R1
;   R3         -> derrame [R7]
;   R9         -> derrame [R7 + 8]
;   R10        -> derrame [R7 + 16]
;   R11        -> derrame [R7 + 24]
;   R12        -> derrame [R7 + 32]
;   R13 (SP)   -> R6
    ADDI R7, R0, 0x0030       ; [prologo] BP = area de derrame 0x00300000
    SHL R7, R7, 16            ; [prologo] BP = area de derrame 0x00300000
    ADDI R7, R7, 0x0000       ; [prologo] BP = area de derrame 0x00300000
    ADDI R4, R0, 15           ; [datos] a: 987654 -> 0x00201000
    SHL R4, R4, 16            ; [datos] a: 987654 -> 0x00201000
    ADDI R4, R4, 4614         ; [datos] a: 987654 -> 0x00201000
    ADDI R5, R0, 0x0020       ; [datos] a: 987654 -> 0x00201000
    SHL R5, R5, 16            ; [datos] a: 987654 -> 0x00201000
    ADDI R5, R5, 0x1000       ; [datos] a: 987654 -> 0x00201000
    STORE R4, [R5]            ; [datos] a: 987654 -> 0x00201000
    ADDI R4, R0, 2            ; [datos] b: 123456 -> 0x00201008
    SHL R4, R4, 16            ; [datos] b: 123456 -> 0x00201008
    ADDI R4, R4, -7616        ; [datos] b: 123456 -> 0x00201008
    ADDI R5, R0, 0x0020       ; [datos] b: 123456 -> 0x00201008
    SHL R5, R5, 16            ; [datos] b: 123456 -> 0x00201008
    ADDI R5, R5, 0x1008       ; [datos] b: 123456 -> 0x00201008
    STORE R4, [R5]            ; [datos] b: 123456 -> 0x00201008
    ADDI R5, R0, 0x0020       ; [datos] temp: 0 -> 0x00201010
    SHL R5, R5, 16            ; [datos] temp: 0 -> 0x00201010
    ADDI R5, R5, 0x1010       ; [datos] temp: 0 -> 0x00201010
    STORE R0, [R5]            ; [datos] temp: 0 -> 0x00201010
; .data
; .text
    ADDI R5, R0, 0x0020       ; L8: MOVD R0, [a]
    SHL R5, R5, 16            ; L8: MOVD R0, [a]
    ADDI R5, R5, 0x1000       ; L8: MOVD R0, [a]
    LOAD R2, [R5]             ; L8: MOVD R0, [a]
    ADDI R5, R0, 0x0020       ; L9: MOVD R1, [b]
    SHL R5, R5, 16            ; L9: MOVD R1, [b]
    ADDI R5, R5, 0x1008       ; L9: MOVD R1, [b]
    LOAD R3, [R5]             ; L9: MOVD R1, [b]
    ADDI R1, R0, 1            ; L10: MOVD R2, 1
    CMP R2, R3                ; L12: CMP R0, R1
    JP GREATER                ; L13: JG GREATER
LOOP:
    CMP R1, R0                ; L15: CMP R2, 0
    JZ FIN                    ; L16: JZ FIN
    ADD R1, R2, R0            ; L17: MOVD R2, R0
    STORE R3, [R7]            ; L18: MOVD R3, R1
    LOAD R4, [R7]             ; L19: DIV R3, R2
    DIV R4, R4, R1            ; L19: DIV R3, R2
    MUL R5, R4, R1            ; L19: DIV R3, R2
    LOAD R1, [R7]             ; L19: DIV R3, R2
    SUB R1, R1, R5            ; L19: DIV R3, R2
    STORE R4, [R7]            ; L19: DIV R3, R2
    ADD R3, R2, R0            ; L20: MOVD R1, R0
    ADD R2, R1, R0            ; L21: MOVD R0, R2
    JMP LOOP                  ; L22: JMP LOOP
GREATER:
    STORE R2, [R7 + 8]        ; L25: MOVD R9, R0
    ADD R2, R3, R0            ; L26: MOVD R0, R1
    LOAD R3, [R7 + 8]         ; L27: MOVD R1, R9
    JMP LOOP                  ; L28: JMP LOOP
FIN:
    ADDI R5, R0, 0x0020       ; L31: MOVW [temp], R1
    SHL R5, R5, 16            ; L31: MOVW [temp], R1
    ADDI R5, R5, 0x1010       ; L31: MOVW [temp], R1
    STORE R3, [R5]            ; L31: MOVW [temp], R1
    STORE R0, [R7 + 16]       ; L32: MOVH R10, 0
    ADDI R4, R0, 0x0020       ; L33: LEA R11, [temp]
    SHL R4, R4, 16            ; L33: LEA R11, [temp]
    ADDI R4, R4, 0x1010       ; L33: LEA R11, [temp]
    STORE R4, [R7 + 24]       ; L33: LEA R11, [temp]
    ADDI R4, R0, 1            ; L34: MOVW R12, 1
    STORE R4, [R7 + 32]       ; L34: MOVW R12, 1
                              ; L35: INTR 0  (sin codigo en Enigma-64)
    HLT                       ; L36: HLT
