; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Programa Oficial: Estimacion de la Constante de Brun (B2 - Primos Gemelos)
; Referencia: Tarea 17 - Numeral 3
; Autor: Integrante 7 (Constante de Brun & Bateria de Pruebas - Alejandro Arguello Munoz)
;
; Descripcion:
;   Programa ejecutable de usuario en arquitectura Enigma-64.
;   Lee el numero de pares de primos gemelos K desde la direccion 0x00205000,
;   calcula la estimacion de la Constante de Brun (B2) sumando 1/p + 1/(p+2)
;   utilizando las subrutinas de la FPU emulada (FPU_INT_TO_FLOAT, FDIV, FADD),
;   y escribe:
;     * 0x00205008: B2 estimado en formato IEEE 754 (64 bits)
;     * 0x00205010: Cantidad efectiva de pares calculados (64 bits)
;     * 0x00205018: Ultimo primo gemelo p procesado (64 bits)
;
; Mapa de Memoria de Usuario:
;   - Codigo ejecutable : 0x00200000
;   - Pila de ejecucion : Base SP = 0x00204000 (crece hacia abajo)
;   - Variable Entrada  : 0x00205000 (K pares, entero de 64 bits)
;   - Variable Salida 1 : 0x00205008 (B2 en IEEE 754 de 64 bits)
;   - Variable Salida 2 : 0x00205010 (Pares procesados, entero 64 bits)
;   - Variable Salida 3 : 0x00205018 (Ultimo p, entero 64 bits)
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

    ; 3. Leer numero de pares K de memoria
    LOAD R1, [R4 + 0]

    ; 4. Ejecutar algoritmo de Constante de Brun (FPU_BRUN)
    CALL FPU_BRUN

    ; 5. Guardar resultados en memoria:
    ; R5 = B2 (flotante), R1 = Pares procesados, R2 = Ultimo p
    ADDI R4, R0, 0x0020
    SHL R4, R4, 16
    ADDI R4, R4, 0x5000
    STORE R5, [R4 + 8]
    STORE R1, [R4 + 16]
    STORE R2, [R4 + 24]

    ; 6. Finalizar ejecucion
    HLT
