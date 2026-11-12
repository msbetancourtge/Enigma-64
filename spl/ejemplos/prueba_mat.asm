; ==============================================================================
; prueba_mat.asm - Prueba de la libreria mat.asm (Integrante 3).
;
; Se carga y ejecuta en 0x00200000. Zonas usadas (de layout_datos.inc):
;   M   = 0x00260000  matriz 3 x 4 (BASE_MATRICES), cabecera F, C en M - 16, M - 8
;   N   = 0x00260100  matriz 2 x 3 para MAT_CLEAR; la palabra N + 48 es centinela
;   RES = 0x002E0000  resultados para revisar (BASE_BUFFERS)
;   SP  = BP = 0x00400000  pila alineada a 8, fuera de las zonas de datos
;
; Llamadas anidadas que ejercita (cada flecha es un CALL con su RET):
;   INICIO -> MAT_SET / MAT_GET -> MAT_ADDR              (2 niveles)
;   INICIO -> MAT_CLEAR -> MAT_ROWS / MAT_COLS           (2 niveles)
;   INICIO -> SUMAR_MATRIZ -> MAT_GET -> MAT_ADDR        (3 niveles, 3 marcos)
;
; Estado esperado al llegar a HLT:
;   M[0][0..3] = 0, 1, 2, 0xC004000000000000 (-2.5)
;   M[1][0..3] = 10, 11, 12, 13
;   M[2][0..3] = 20, 21, 22, 23            cabecera: F = 3, C = 4
;   N[0..5] = 0, 0, 0, 0, 0, 0             cabecera: F = 2, C = 3
;   N + 48 = 12 (centinela: MAT_CLEAR no escribe fuera de N)
;   RES[0] = 0x00260048   MAT_ADDR(M, 2, 1)
;   RES[1] = 12           MAT_GET(M, 1, 2)
;   RES[2] = 23           MAT_GET(M, 2, 3)
;   RES[3] = 138          SUMAR_MATRIZ(M): suma de los 12 enteros
;   RES[4] = 0x00260000   R1 tras SUMAR_MATRIZ (preservado)
;   RES[5] = 3            R3 tras SUMAR_MATRIZ (preservado)
;   RES[6] = 0xC004000000000000   MAT_GET(M, 0, 3): bits del double -2.5
;   RES[7] = 13           VEC_GET sobre la fila 1: la fila es un vector
;   RES[8] = 6            MAT_CLEAR(N): palabras puestas a cero
;   R1 = 0x00260100  R2 = 2  R3 = 3  R4 = 0x002E0000
;   SP = BP = 0x00400000 (cada CALL, PUSH y ENTER quedaron balanceados)
; ==============================================================================
#define INCLUIR_MATRICES
#include "estructuras.inc"

INICIO:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000
        ADD  BP, SP, R0             ; BP = SP: marco base del programa
        ADDI R1, R0, 0x0026
        SHL  R1, R1, 16             ; R1 = M = 0x00260000
        ADDI R2, R0, 3
        ADDI R3, R0, 4
        CALL MAT_INIT               ; cabecera de M: F = 3, C = 4

; 1) MAT_SET en doble bucle: M[i][j] = 10 * i + j
;    Los limites salen de la cabecera y el bucle depende de que MAT_SET
;    preserve R1..R4 (R5 es caller-saved: se relee con MAT_COLS y MAT_ROWS).
        ADD  R2, R0, R0             ; i = 0
FILAS:
        ADD  R3, R0, R0             ; j = 0
COLUMNAS:
        ADDI R4, R0, 10
        MUL  R4, R2, R4             ; R4 = 10 * i
        ADD  R4, R4, R3             ; R4 = 10 * i + j
        CALL MAT_SET                ; M[i][j] = R4
        INC  R3                     ; j = j + 1
        CALL MAT_COLS               ; R5 = C
        CMP  R3, R5
        JNZ  COLUMNAS               ; hasta j = C
        INC  R2                     ; i = i + 1
        CALL MAT_ROWS               ; R5 = F
        CMP  R2, R5
        JNZ  FILAS                  ; hasta i = F

; 2) MAT_ADDR(M, 2, 1) = M + ((2 * 4 + 1) << 3) = 0x00260048
        ADDI R4, R0, 0x002E
        SHL  R4, R4, 16             ; R4 = RES = 0x002E0000
        ADDI R2, R0, 2
        ADDI R3, R0, 1
        CALL MAT_ADDR
        STORE R5, [R4 + 0]          ; RES[0]

; 3) MAT_GET(M, 1, 2) = 12 y MAT_GET(M, 2, 3) = 23
        ADDI R2, R0, 1
        ADDI R3, R0, 2
        CALL MAT_GET
        STORE R5, [R4 + 8]          ; RES[1]
        ADDI R2, R0, 2
        ADDI R3, R0, 3
        CALL MAT_GET
        STORE R5, [R4 + 16]         ; RES[2]

; 4) Tres niveles de llamadas anidadas: SUMAR_MATRIZ(M) = 138
        CALL SUMAR_MATRIZ           ; INICIO -> SUMAR_MATRIZ -> MAT_GET -> MAT_ADDR
TRAS_SUMAR:
        STORE R5, [R4 + 24]         ; RES[3]
        STORE R1, [R4 + 32]         ; RES[4] = R1 preservado
        STORE R3, [R4 + 40]         ; RES[5] = R3 preservado

; 5) MAT_SET de un double: M[0][3] = -2.5 = 0xC004000000000000
;    R4 lleva RES: se apila mientras sirve de argumento valor.
        PUSH R4                     ; guarda RES
        ADDI R4, R0, -16380         ; R4 = 0xFFFFFFFFFFFFC004
        SHL  R4, R4, 48             ; R4 = 0xC004000000000000
        ADDI R2, R0, 0
        ADDI R3, R0, 3
        CALL MAT_SET
        POP  R4                     ; recupera RES
        CALL MAT_GET
        STORE R5, [R4 + 48]         ; RES[6]

; 6) La fila 1 es un vector de C elementos: VEC_GET(&M[1][0], 3) = M[1][3]
        ADDI R2, R0, 1
        ADDI R3, R0, 0
        CALL MAT_ADDR               ; R5 = &M[1][0]
        PUSH R1                     ; guarda M
        ADD  R1, R5, R0             ; R1 = base de la fila 1
        ADDI R2, R0, 3
        CALL VEC_GET                ; R5 = fila1[3] = M[1][3]
        POP  R1                     ; recupera M
        STORE R5, [R4 + 56]         ; RES[7]

; 7) MAT_CLEAR sobre N = 2 x 3 en 0x00260100. N se llena copiando 7 palabras
;    de M: la septima cae justo despues de N y sirve de centinela.
        ADD  R2, R1, R0             ; origen = M
        ADDI R1, R1, 0x0100         ; destino = N = 0x00260100
        ADDI R3, R0, 7
        CALL VEC_COPY               ; N[0..5] y centinela = 0, 1, 2, -2.5, 10, 11, 12
        ADDI R2, R0, 2
        ADDI R3, R0, 3
        CALL MAT_INIT               ; cabecera de N: F = 2, C = 3
        CALL MAT_CLEAR              ; N = 0 y R5 = 6
        STORE R5, [R4 + 64]         ; RES[8]
        HLT

; ------------------------------------------------------------------------------
; SUMAR_MATRIZ: R5 = suma de todos los elementos (enteros)   Entrada: R1 = base
; Rutina de usuario no hoja: guarda R2..R4, abre un marco con dos locales y
; llama a MAT_GET en un doble bucle (MAT_GET llama a su vez a MAT_ADDR).
;   Marco tras PUSH R2, PUSH R3, PUSH R4 y ENTER 16:
;     [BP + 32] retorno   [BP + 24] R2   [BP + 16] R3   [BP + 8] R4
;     [BP + 0] BP del llamador   [BP - 8] F   [BP - 16] C
; ------------------------------------------------------------------------------
SUMAR_MATRIZ:
        PUSH R2                     ; preserva R2 (sera i)
        PUSH R3                     ; preserva R3 (sera j)
        PUSH R4                     ; preserva R4 (sera el acumulador)
        ENTER 16                    ; locales: F y C
        CALL MAT_ROWS
        STORE R5, [BP - 8]          ; F
        CALL MAT_COLS
        STORE R5, [BP - 16]         ; C
        ADD  R4, R0, R0             ; acumulador = 0
        ADD  R2, R0, R0             ; i = 0
SM_FILAS:
        LOAD R5, [BP - 8]
        CMP  R2, R5
        JZ   SM_FIN                 ; i = F: termino
        ADD  R3, R0, R0             ; j = 0
SM_COLUMNAS:
        LOAD R5, [BP - 16]
        CMP  R3, R5
        JZ   SM_FILA_LISTA          ; j = C: siguiente fila
        CALL MAT_GET                ; R5 = M[i][j] (MAT_GET preserva R1..R4)
        ADD  R4, R4, R5             ; acumulador += M[i][j]
        INC  R3
        JMP  SM_COLUMNAS
SM_FILA_LISTA:
        INC  R2
        JMP  SM_FILAS
SM_FIN:
        ADD  R5, R4, R0             ; R5 = suma
        LEAVE                       ; SP = BP y recupera el BP del llamador
        POP  R4                     ; restaura en orden inverso al PUSH
        POP  R3
        POP  R2
        RET
