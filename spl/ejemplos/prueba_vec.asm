; ==============================================================================
; prueba_vec.asm - Prueba de la libreria vec.asm (Integrante 2).
;
; Se carga y ejecuta en 0x00200000. Zonas usadas (de layout_datos.inc):
;   V   = 0x00220000  vector de prueba (BASE_VECTORES), cabecera n en V - 8
;   W   = 0x00220100  segundo vector, destino de una copia sin solape
;   RES = 0x002E0000  resultados para revisar (BASE_BUFFERS)
;   SP  = 0x00400000  pila alineada a 8, fuera de las zonas de datos
;
; Estado esperado al llegar a HLT:
;   V[-1..5] = 6 | 50, 20, 30, 40, 40, 0xC004000000000000 (-2.5)
;   W[0..5]  = 50, 20, 30, 40, 10, 0xC004000000000000
;   RES[0] = 0x00220018   VEC_ADDR(V, 3)
;   RES[1] = 30           VEC_GET(V, 2)
;   RES[2] = 0xC004000000000000   VEC_GET(V, 5): bits del double -2.5
;   RES[3] = 6            VEC_LEN(V)
;   RES[4] = 0x00220000   R1 tras VEC_SET, VEC_GET, VEC_SWAP (preservado)
;   RES[5] = 4            R3 tras VEC_SWAP(V, 0, 4) (preservado)
;   R1 = 0x00220000  R2 = 0x00220008  R3 = 4  R4 = 0x002E0000
;   SP = 0x00400000 (cada CALL y cada PUSH quedaron balanceados)
; ==============================================================================
#include "vec.asm"

INICIO:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16             ; R1 = V = 0x00220000
        ADDI R4, R0, 0x002E
        SHL  R4, R4, 16             ; R4 = RES = 0x002E0000
        ADDI R5, R0, 6
        STORE R5, [R1 - 8]          ; cabecera: n = 6

; 1) VEC_SET en bucle: V[0..4] = 10, 20, 30, 40, 50
;    El bucle depende de que VEC_SET preserve R1, R2 y R3.
        ADDI R2, R0, 0              ; i = 0
        ADDI R3, R0, 10             ; valor = 10
LLENAR:
        CALL VEC_SET                ; V[i] = valor
        INC  R2                     ; i = i + 1
        ADDI R3, R3, 10             ; valor = valor + 10
        ADDI R5, R0, 5              ; R5 es caller-saved: se recarga cada vez
        CMP  R2, R5
        JNZ  LLENAR                 ; hasta i = 5

; 2) VEC_SET de un double: V[5] = -2.5 = 0xC004000000000000
        ADDI R3, R0, -16380         ; R3 = 0xFFFFFFFFFFFFC004
        SHL  R3, R3, 48             ; R3 = 0xC004000000000000
        ADDI R2, R0, 5
        CALL VEC_SET

; 3) VEC_ADDR(V, 3) = 0x00220018
        ADDI R2, R0, 3
        CALL VEC_ADDR
        STORE R5, [R4 + 0]          ; RES[0]

; 4) VEC_GET(V, 2) = 30 y VEC_GET(V, 5) = bits de -2.5
        ADDI R2, R0, 2
        CALL VEC_GET
        STORE R5, [R4 + 8]          ; RES[1]
        ADDI R2, R0, 5
        CALL VEC_GET
        STORE R5, [R4 + 16]         ; RES[2]

; 5) VEC_LEN(V) = 6
        CALL VEC_LEN
        STORE R5, [R4 + 24]         ; RES[3]

; 6) VEC_SWAP(V, 0, 4): V = 50, 20, 30, 40, 10, -2.5
;    y VEC_SWAP(V, 2, 2) no cambia nada
        ADDI R2, R0, 0
        ADDI R3, R0, 4
        CALL VEC_SWAP
        STORE R1, [R4 + 32]         ; RES[4] = R1 preservado
        STORE R3, [R4 + 40]         ; RES[5] = R3 preservado
        ADDI R2, R0, 2
        ADDI R3, R0, 2
        CALL VEC_SWAP

; 7) VEC_COPY(W, V, 6) sin solape: W = copia exacta de V
        ADD  R2, R1, R0             ; origen = V
        ADDI R1, R1, 0x0100         ; destino = W
        ADDI R3, R0, 6
        CALL VEC_COPY

; 8) VEC_COPY(V + 8, V, 4) con solape y destino > origen (copia hacia atras)
;    V = 50, 50, 20, 30, 40, -2.5
        ADDI R1, R2, 8              ; destino = &V[1]  (R2 sigue siendo V)
        ADDI R3, R0, 4
        CALL VEC_COPY

; 9) VEC_COPY(V, V + 8, 4) con solape y destino < origen (copia hacia adelante)
;    V = 50, 20, 30, 40, 40, -2.5
        ADD  R1, R2, R0             ; destino = V
        ADDI R2, R2, 8              ; origen = &V[1]
        CALL VEC_COPY               ; R3 sigue en 4

; 10) VEC_COPY con n = 0 no escribe nada (R3 vuelve a 4 al final)
        ADDI R3, R0, 0
        CALL VEC_COPY
        ADDI R3, R0, 4
        HLT
