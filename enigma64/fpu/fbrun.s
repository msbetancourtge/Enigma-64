; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Modulo Oficial: FPU_BRUN & FPU_ES_PRIMO (Estimacion de la Constante de Brun B2)
; Tarea 17 - Integrante 7 (Constante de Brun & Bateria de Pruebas)
; Autor: Alejandro Arguello Munoz
;
; Contenido:
;   1. FPU_ES_PRIMO: Test de primalidad para enteros de 64 bits en ALU nativa.
;   2. FPU_BRUN / FBRUN: Estimacion de la Constante de Brun (B2) para K pares
;      de primos gemelos (p, p+2) mediante la FPU emulada:
;          B_2 = \sum_{p, p+2 \in \mathbb{P}} \left( \frac{1}{p} + \frac{1}{p+2} \right)
;
; Convencion de llamada FPU_BRUN:
;   * Entrada: R1 = K (numero entero de pares de primos gemelos a sumar, K >= 1).
;   * Salidas:
;       - R5 = Estimacion de B2 en formato IEEE 754 de 64 bits (binary64).
;       - R1 = Cantidad efectiva de pares calculados (entero 64 bits).
;       - R2 = Ultimo primo gemelo p procesado (entero 64 bits).
;   * Registros modificados: R1..R5 (temporales).
;   * Preservacion: SP (R6) y BP (R7) gestionados formalmente con ENTER / LEAVE.
; ==============================================================================

; ------------------------------------------------------------------------------
; SUBRUTINA: FPU_ES_PRIMO
;
; Determina si un entero de 64 bits es un numero primo utilizando divisiones
; de prueba sucesivas en la ALU entera nativa de Enigma-64.
;
; Entrada:
;   R1: Numero entero n a evaluar (64 bits).
;
; Salidas:
;   R2: 1 si n es primo, 0 si n es compuesto o n < 2.
;   Bandera Z: 0 si primo (R2 != 0), 1 si compuesto (R2 == 0).
;
; Registros modificados:
;   R2, R3, R4, R5 (R1 se preserva intacto).
; ------------------------------------------------------------------------------
FPU_ES_PRIMO:
    ; Casos n < 2 -> no primo
    ADDI R2, R0, 2
    CMP R1, R2
    JN ES_PRIMO_RET_0
    JZ ES_PRIMO_RET_1

    ; Si n es par (n & 1 == 0) -> compuesto (excepto 2, ya tratado)
    ADDI R2, R0, 1
    AND R2, R1, R2
    JZ ES_PRIMO_RET_0

    ; Divisor inicial d = 3 en R3
    ADDI R3, R0, 3

ES_PRIMO_LOOP_DIV:
    ; Parada cuando d * d > n
    MUL R4, R3, R3              ; R4 = d * d
    CMP R4, R1                  ; Compara (d*d) con n
    JP ES_PRIMO_RET_1           ; Si d * d > n -> n es primo!

    ; Evaluar si d divide exactamente a n: n % d == 0
    DIV R5, R1, R3              ; R5 = n / d
    MUL R5, R5, R3              ; R5 = (n / d) * d
    SUB R5, R1, R5              ; R5 = n - (n/d)*d = n % d
    CMP R5, R0
    JZ ES_PRIMO_RET_0           ; Si n % d == 0 -> es divisible, compuesto!

    ; Siguiente divisor impar: d = d + 2
    ADDI R3, R3, 2
    JMP ES_PRIMO_LOOP_DIV

ES_PRIMO_RET_1:
    ADDI R2, R0, 1
    CMP R2, R0                  ; Z = 0
    RET

ES_PRIMO_RET_0:
    ADDI R2, R0, 0
    CMP R2, R0                  ; Z = 1
    RET


; ------------------------------------------------------------------------------
; SUBRUTINA: FPU_BRUN / FBRUN
;
; Calcula la estimacion de la Constante de Brun sumando los inversos de los
; primeros K pares de primos gemelos encontrados: (3, 5), (5, 7), (11, 13)...
;
; Entradas:
;   R1: K (cantidad objetivo de pares de primos gemelos, K >= 1).
;
; Salidas:
;   R5: Valor de B_2 en formato IEEE 754 de 64 bits.
;   R1: Cantidad efectiva de pares calculados.
;   R2: Ultimo primo gemelo p procesado.
;
; Mapa del Marco de Pila (ENTER 128):
;   [BP - 8]  : K_target (objetivo)
;   [BP - 16] : K_count (pares acumulados hasta el momento)
;   [BP - 24] : Candidato impar actual p (inicia en 3)
;   [BP - 32] : Suma acumulada B2 en IEEE 754 (inicia en 0.0)
;   [BP - 40] : Constante 1.0 en IEEE 754 (0x3FF0000000000000)
;   [BP - 48] : Variable temporal flotante (1.0 / p)
;   [BP - 56] : Variable temporal flotante (1.0 / (p + 2))
;   [BP - 64] : Temporal auxiliar
; ------------------------------------------------------------------------------
FBRUN:
FPU_BRUN:
    ENTER 128

    ; 1. Inicializar variables locales
    STORE R1, [BP - 8]          ; [BP - 8]  = K_target
    ADDI R2, R0, 0
    STORE R2, [BP - 16]         ; [BP - 16] = K_count = 0
    ADDI R2, R0, 3
    STORE R2, [BP - 24]         ; [BP - 24] = p_candidato = 3
    ADDI R2, R0, 0
    STORE R2, [BP - 32]         ; [BP - 32] = B2_acumulado = +0.0

    ; Construir constante 1.0 en IEEE 754: exponente 1023 (0x3FF) << 52
    ADDI R2, R0, 0x03FF
    SHL R2, R2, 52
    STORE R2, [BP - 40]         ; [BP - 40] = 1.0 flotante (0x3FF0000000000000)

    ; Si K_target <= 0, salir inmediatamente con B2 = 0.0
    LOAD R1, [BP - 8]
    CMP R1, R0
    JZ BRUN_FIN_CERO
    JN BRUN_FIN_CERO

BRUN_LOOP_BUSQUEDA:
    ; Verificar si ya se procesaron los K pares solicitados
    LOAD R1, [BP - 16]          ; R1 = K_count
    LOAD R2, [BP - 8]           ; R2 = K_target
    CMP R1, R2
    JZ BRUN_FINALIZAR           ; Si K_count == K_target, terminar

    ; 2. Evaluar si p es primo:
    LOAD R1, [BP - 24]          ; R1 = p
    CALL FPU_ES_PRIMO
    CMP R2, R0
    JZ BRUN_SIGUIENTE_CANDIDATO ; Si p no es primo, probar siguiente

    ; 3. Evaluar si p + 2 es primo (par de gemelos):
    LOAD R1, [BP - 24]          ; R1 = p
    ADDI R1, R1, 2              ; R1 = p + 2
    CALL FPU_ES_PRIMO
    CMP R2, R0
    JZ BRUN_SIGUIENTE_CANDIDATO ; Si p + 2 no es primo, probar siguiente

    ; ---- ¡PAR DE PRIMOS GEMELOS DETECTADO: (p, p+2)! ----

    ; 4. Calcular 1.0 / p en punto flotante:
    LOAD R1, [BP - 24]          ; R1 = p (entero)
    CALL FPU_INT_TO_FLOAT       ; R5 = float(p)
    ADDI R2, R5, 0              ; R2 = divisor = float(p)
    LOAD R1, [BP - 40]          ; R1 = dividendo = 1.0
    CALL FDIV                   ; R5 = 1.0 / float(p)
    STORE R5, [BP - 48]         ; [BP - 48] = rec_p

    ; 5. Calcular 1.0 / (p + 2) en punto flotante:
    LOAD R1, [BP - 24]          ; R1 = p
    ADDI R1, R1, 2              ; R1 = p + 2 (entero)
    CALL FPU_INT_TO_FLOAT       ; R5 = float(p + 2)
    ADDI R2, R5, 0              ; R2 = divisor = float(p + 2)
    LOAD R1, [BP - 40]          ; R1 = dividendo = 1.0
    CALL FDIV                   ; R5 = 1.0 / float(p + 2)
    STORE R5, [BP - 56]         ; [BP - 56] = rec_q

    ; 6. Acumular ambos recíprocos en B2:
    ; B2 = B2 + rec_p
    LOAD R1, [BP - 32]          ; R1 = B2
    LOAD R2, [BP - 48]          ; R2 = rec_p
    CALL FADD                   ; R5 = B2 + rec_p
    STORE R5, [BP - 32]

    ; B2 = B2 + rec_q
    LOAD R1, [BP - 32]          ; R1 = B2
    LOAD R2, [BP - 56]          ; R2 = rec_q
    CALL FADD                   ; R5 = B2 + rec_q
    STORE R5, [BP - 32]

    ; 7. Incrementar contador de pares procesados: K_count += 1
    LOAD R1, [BP - 16]
    ADDI R1, R1, 1
    STORE R1, [BP - 16]

BRUN_SIGUIENTE_CANDIDATO:
    ; Avanzar al siguiente impar: p = p + 2
    LOAD R1, [BP - 24]
    ADDI R1, R1, 2
    STORE R1, [BP - 24]
    JMP BRUN_LOOP_BUSQUEDA

BRUN_FINALIZAR:
    LOAD R5, [BP - 32]          ; R5 = B2 acumulado final
    LOAD R1, [BP - 16]          ; R1 = pares efectivos procesados
    LOAD R2, [BP - 24]          ; R2 = p candidato
    SUBI R2, R2, 2              ; R2 = ultimo p primo gemelo procesado
    LEAVE
    RET

BRUN_FIN_CERO:
    ADDI R5, R0, 0              ; R5 = +0.0
    ADDI R1, R0, 0              ; R1 = 0 pares
    ADDI R2, R0, 0              ; R2 = 0
    LEAVE
    RET
