; =============================================================================
; Algoritmo 2: Calculo del Factorial - 5! = 120
; Tarea 27 — CacaoCore-64 hacia Enigma-64
; Generado automaticamente a partir de: factorial.cac
; =============================================================================

.data
n : 5
fact : 1
.text
LWHILE_START1:
MOVD R0, [n]
CMP R0, 1
JG LTRUE0
MOVD R0, 0
JMP LFALSE0
LTRUE0:
MOVD R0, 1
LFALSE0:
CMP R0, 0
JZ LWHILE_END1
MOVD R2, [fact]
MUL R2, [n]
MOVD [fact], R2
MOVD R2, [n]
SUB R2, 1
MOVD [n], R2
JMP LWHILE_START1
LWHILE_END1:
MOVH R10, 0
LEA R11, [fact]
MOVW R12, 1
INTR 0
HLT
