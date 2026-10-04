; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Programa Oficial: Estimacion de la Raiz Cuadrada (Newton-Raphson)
; Referencia: Ricardo Peña, 'De Euclides a JAVA' (pag. 26)
; Tarea 17 - Integrante 6 (Algoritmo Raiz Cuadrada & Oraculo)
;
; Descripcion:
;   Programa ejecutable de usuario en arquitectura Enigma-64.
;   Lee el operando A de 64 bits en formato IEEE 754 desde la direccion
;   de memoria 0x00205000, calcula sqrt(A) utilizando el metodo iterativo
;   de Newton-Raphson asistido por el emulador FPU, y almacena el resultado
;   en formato IEEE 754 en la direccion 0x00205008.
;
; Mapa de Memoria de Usuario:
;   - Codigo ejecutable : 0x00200000
;   - Pila de ejecucion : Base SP = 0x00204000 (crece hacia abajo)
;   - Variable Entrada  : 0x00205000 (A en IEEE 754 de 64 bits)
;   - Variable Salida   : 0x00205008 (sqrt(A) en IEEE 754 de 64 bits)
; ==============================================================================

MAIN:
    ; 1. Inicializar Pila (SP = 0x00204000, BP = SP)
    ADDI SP, R0, 0x0020
    SHL SP, SP, 16
    ADDI SP, SP, 0x4000
    ADDI BP, SP, 0

    ; 2. Cargar puntero de variables de memoria (0x00205000)
    ADDI R4, R0, 0x0020
    SHL R4, R4, 16
    ADDI R4, R4, 0x5000

    ; 3. Leer operando A de memoria
    LOAD R1, [R4 + 0]

    ; 4. Ejecutar algoritmo de Raiz Cuadrada (FSQRT)
    CALL FSQRT

    ; 5. Guardar resultado sqrt(A) en memoria (0x00205008)
    ADDI R4, R0, 0x0020
    SHL R4, R4, 16
    ADDI R4, R4, 0x5000
    STORE R5, [R4 + 8]

    ; 6. Finalizar ejecucion
    HLT
