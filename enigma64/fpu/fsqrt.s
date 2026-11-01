; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Modulo Oficial: FSQRT (Raiz Cuadrada IEEE 754 Doble Precision - binary64)
;
; Metodo Numerico: Newton-Raphson para estimacion de raiz cuadrada
; Referencia: Ricardo Peña, 'De Euclides a JAVA' (pag. 26)
; Autor: Integrante 6 (Algoritmo Raiz Cuadrada & Oraculo)
;
; Contenido:
;   1. FSQRT / FPU_FSQRT: Estimacion de raiz cuadrada en punto flotante
;      utilizando aproximacion inicial y refinamiento iterativo cuadratico:
;          x_{k+1} = 0.5 * (x_k + A / x_k)
;
; Convencion de llamada:
;   * Entrada: R1 = operando A en formato IEEE 754 de 64 bits (binary64).
;   * Salida:  R5 = sqrt(A) en formato IEEE 754 binary64.
;   * Registros modificados: R1..R5 (temporales).
;   * Preservacion: SP (R6) y BP (R7) gestionados formalmente con ENTER / LEAVE.
;
; Reglas del Estandar IEEE 754:
;   * sqrt(+0.0) = +0.0 (preserva signo positivo)
;   * sqrt(-0.0) = -0.0 (preserva signo negativo)
;   * sqrt(x < 0) = NaN canonico (0x7FF8000000000000, operacion invalida)
;   * sqrt(+inf) = +inf
;   * sqrt(-inf) = NaN canonico (operacion invalida)
;   * sqrt(NaN)  = NaN silenciado (activa bit 51 conservando carga util)
; ==============================================================================

FSQRT:
FPU_FSQRT:
    ENTER 64
    STORE R1, [BP - 8]          ; [BP - 8] = Operando A original

    ; 1. Construir constantes necesarias en la pila
    ; Constante +Infinito = 0x7FF0000000000000
    ADDI R4, R0, 0x07FF
    SHL R4, R4, 52
    STORE R4, [BP - 48]         ; [BP - 48] = +Infinito

    ; Constante 0.5 = 0x3FE0000000000000
    ADDI R4, R0, 0x03FE
    SHL R4, R4, 52
    STORE R4, [BP - 32]         ; [BP - 32] = 0.5 (flotante)

    ; 2. Extraer signo S = (A >> 63) & 1
    LOAD R1, [BP - 8]
    SHR R2, R1, 63              ; R2 = S (0 o 1)

    ; 3. Extraer magnitud |A| (limpiar bit 63 de signo)
    SHL R3, R1, 1
    SHR R3, R3, 1               ; R3 = |A|

    ; --- Caso Especial A: Cero (+0.0 y -0.0) ---
    CMP R3, R0
    JZ FSQRT_RET_A              ; sqrt(+-0.0) = +-0.0 (retorna A original)

    ; --- Caso Especial B: Negativo estricto (S == 1 y |A| > 0) ---
    CMP R2, R0
    JNZ FSQRT_RET_NAN_CANONICO  ; Raiz de negativo -> NaN canonico

    ; --- Caso Especial C: Infinito y NaN (|A| >= +Infinito) ---
    LOAD R4, [BP - 48]          ; R4 = +Infinito
    CMP R4, R3                  ; Compara +Inf con |A| (prestamo si |A| > +Inf)
    JC FSQRT_RET_NAN_SILENCIADO ; Si |A| > +Inf -> Es NaN
    CMP R3, R4
    JZ FSQRT_RET_A              ; Si |A| == +Inf -> Retorna +Inf

    ; 4. Calcular Aproximacion Inicial x_0 (Semilla de Newton)
    ; Extraer exponente E_A = (A >> 52) & 0x7FF
    SHR R2, R1, 52
    ADDI R3, R0, 0x07FF
    AND R2, R2, R3              ; R2 = E_A
    CMP R2, R0
    JZ FSQRT_SEMILLA_SUBNORMAL  ; Si E_A == 0, A es subnormal

    ; Caso normal: exponente real e = E_A - 1023
    ADDI R3, R0, 1023
    SUB R2, R2, R3              ; R2 = e (con signo)
    JMP FSQRT_SEMILLA_CALC

FSQRT_SEMILLA_SUBNORMAL:
    ; A es subnormal: normalizar mantisa para obtener exponente efectivo
    LOAD R1, [BP - 8]
    SHL R4, R1, 12
    SHR R4, R4, 12              ; R4 = Fraccion M > 0
    ADDI R2, R0, 1022
    SUB R2, R0, R2              ; R2 = -1022 inicial

FSQRT_NORM_SUB_LOOP:
    SHR R5, R4, 52
    ADDI R3, R0, 1
    AND R5, R5, R3
    JNZ FSQRT_SEMILLA_CALC
    SHL R4, R4, 1
    SUBI R2, R2, 1              ; e -= 1 por cada corrimiento
    JMP FSQRT_NORM_SUB_LOOP

FSQRT_SEMILLA_CALC:
    ; R2 = exponente no sesgado e
    ; e_nuevo = e / 2 (desplazamiento aritmetico con signo)
    ASR R2, R2, 1
    ADDI R3, R0, 1023
    ADD R2, R2, R3              ; E_nuevo = e_nuevo + 1023
    SHL R2, R2, 52              ; R2 = patron IEEE de x_0
    STORE R2, [BP - 16]         ; [BP - 16] = x_k

    ; Inicializar contador de iteraciones maximas (25 iteraciones)
    ADDI R1, R0, 25
    STORE R1, [BP - 40]

; ------------------------------------------------------------------------------
; BUCLE ITERATIVO DE NEWTON-RAPHSON (Ricardo Peña, pag. 26):
;   x_{k+1} = 0.5 * (x_k + A / x_k)
; ------------------------------------------------------------------------------
FSQRT_LOOP:
    ; Paso 1: T = A / x_k (FDIV)
    LOAD R1, [BP - 8]           ; R1 = A
    LOAD R2, [BP - 16]          ; R2 = x_k
    CALL FDIV                   ; R5 = A / x_k
    STORE R5, [BP - 24]         ; [BP - 24] = T

    ; Paso 2: S = x_k + T (FADD)
    LOAD R1, [BP - 16]          ; R1 = x_k
    LOAD R2, [BP - 24]          ; R2 = T
    CALL FADD                   ; R5 = x_k + T
    STORE R5, [BP - 24]         ; [BP - 24] = S

    ; Paso 3: x_sig = S * 0.5 (FMUL)
    LOAD R1, [BP - 24]          ; R1 = S
    LOAD R2, [BP - 32]          ; R2 = 0.5
    CALL FMUL                   ; R5 = x_sig

    ; Paso 4: Evaluar Criterio de Parada
    ; a) Coincidencia bit a bit exacta: x_sig == x_k
    LOAD R2, [BP - 16]          ; R2 = x_k
    CMP R5, R2
    JZ FSQRT_CONVERGIDO

    ; b) Oscilacion de 1 ULP: |x_sig - x_k| <= 1
    SUB R3, R5, R2              ; R3 = x_sig - x_k
    ADDI R4, R0, 1
    CMP R3, R4
    JZ FSQRT_CONVERGIDO         ; Diferencia exactamente +1 ULP
    SUB R4, R0, R4              ; R4 = -1
    CMP R3, R4
    JZ FSQRT_CONVERGIDO         ; Diferencia exactamente -1 ULP

    ; Actualizar x_k = x_sig para la proxima iteracion
    STORE R5, [BP - 16]

    ; Decrementar contador de iteraciones restantes
    LOAD R1, [BP - 40]
    SUBI R1, R1, 1
    STORE R1, [BP - 40]
    JZ FSQRT_CONVERGIDO         ; Si agoto el limite, retorna x_sig

    JMP FSQRT_LOOP

FSQRT_CONVERGIDO:
    ; R5 ya contiene x_sig
    LEAVE
    RET

; ------------------------------------------------------------------------------
; Salidas de Casos Especiales
; ------------------------------------------------------------------------------
FSQRT_RET_A:
    ; Retorna A original (para +-0.0 y +infinito)
    LOAD R5, [BP - 8]
    LEAVE
    RET

FSQRT_RET_NAN_CANONICO:
    ; Retorna NaN canonico: 0x7FF8000000000000
    ADDI R5, R0, 0x0FFF
    SHL R5, R5, 51
    LEAVE
    RET

FSQRT_RET_NAN_SILENCIADO:
    ; Retorna NaN con bit 51 activo (silenciado) conservando la carga util
    LOAD R5, [BP - 8]
    ADDI R4, R0, 1
    SHL R4, R4, 51
    OR R5, R5, R4
    LEAVE
    RET
