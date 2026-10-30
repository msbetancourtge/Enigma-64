; =============================================================================
; Algoritmo 1: Maximo Comun Divisor (Euclides) - MCD(48, 18) = 6
; Tarea 27 — CacaoCore-64 hacia Enigma-64
; Generado automaticamente a partir de: euclides.cac
; =============================================================================

.data
a : 48
b : 18
.text
LWHILE_START3:
MOVD R0, [a]
CMP R0, [b]
JNE LTRUE0
MOVD R0, 0
JMP LFALSE0
LTRUE0:
MOVD R0, 1
LFALSE0:
CMP R0, 0
JZ LWHILE_END3
MOVD R2, [a]
CMP R2, [b]
JG LTRUE1
MOVD R2, 0
JMP LFALSE1
LTRUE1:
MOVD R2, 1
LFALSE1:
CMP R2, 0
JZ LELSE2
MOVD R3, [a]
SUB R3, [b]
MOVD [a], R3
JMP LEND2
LELSE2:
MOVD R3, [b]
SUB R3, [a]
MOVD [b], R3
LEND2:
JMP LWHILE_START3
LWHILE_END3:
MOVH R10, 0
LEA R11, [a]
MOVW R12, 1
INTR 0
HLT
