; =============================================================================
; Algoritmo 3: Sucesion de Fibonacci - [0, 1, 1, 2, 3, 5, 8]
; Tarea 27 — CacaoCore-64 hacia Enigma-64
; Generado automaticamente a partir de: fibonacci.cac
; =============================================================================

.data
fib : 0
fib1 : 1
fib2 : 0
fib3 : 0
fib4 : 0
fib5 : 0
fib6 : 0
i : 2
res : 0
.text
LWHILE_START1:
MOVD R0, [i]
CMP R0, 7
JL LTRUE0
MOVD R0, 0
JMP LFALSE0
LTRUE0:
MOVD R0, 1
LFALSE0:
CMP R0, 0
JZ LWHILE_END1
MOVD R3, [i]
SUB R3, 1
MUL R3, 8
LEA R4, [fib]
ADD R3, R4
MOVD R4, [R3]
MOVD R3, [i]
SUB R3, 2
MUL R3, 8
LEA R5, [fib]
ADD R3, R5
MOVD R5, [R3]
ADD R4, R5
MOVD R2, [i]
MUL R2, 8
LEA R3, [fib]
ADD R2, R3
MOVD [R2], R4
MOVD R2, [i]
ADD R2, 1
MOVD [i], R2
JMP LWHILE_START1
LWHILE_END1:
MOVD R0, 6
MUL R0, 8
LEA R2, [fib]
ADD R0, R2
MOVD R2, [R0]
MOVD [res], R2
MOVH R10, 0
LEA R11, [res]
MOVW R12, 1
INTR 0
HLT
