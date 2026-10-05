; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Modulo Oficial: Conversiones FPU (INT <-> FLOAT) y Mesa de Entrada de Vectores
; Tarea 17: Aritmética de Punto Flotante IEEE 754 Doble Precisión (Binary64)
;
; Autor: Integrante 4 (Deibyd Santiago Barragán Gaitán / Juan Luis Vergara Novoa)
;
; Contenido:
;   1. FPU_VECTORES:      Tabla de vectores canónicos fijos de 5 bytes (JMP)
;                         para desacoplar a los llamadores de las direcciones internas.
;   2. FPU_INT_TO_FLOAT:  Convierte entero con signo de 64 bits (R1) a IEEE 754 (R5).
;   3. FPU_FLOAT_TO_INT:  Convierte IEEE 754 de 64 bits (R1) a entero truncado (R5).
;   4. FPU_FDIV / FCMP:   Puntos de entrada implementados en fdiv.s y fcmp.s.
; ==============================================================================

; ------------------------------------------------------------------------------
; TABLA DE VECTORES DE ENTRADA DE LA BIBLIOTECA FPU
;
; Puntos de entrada fijos de 5 bytes (JMP) a partir de la dirección base:
;   Vector 0 (+0x00): JMP FADD              (Suma - Integrante 1)
;   Vector 1 (+0x05): JMP FSUB              (Resta - Integrante 1)
;   Vector 2 (+0x0A): JMP FMUL              (Multiplicación - Integrante 2)
;   Vector 3 (+0x0F): JMP FDIV              (División)
;   Vector 4 (+0x14): JMP FCMP              (Comparación)
;   Vector 5 (+0x19): JMP FPU_INT_TO_FLOAT  (Conversión INT -> FLOAT - Integrante 4)
;   Vector 6 (+0x1E): JMP FPU_FLOAT_TO_INT  (Conversión FLOAT -> INT - Integrante 4)
;   Vector 7 (+0x23): JMP FSQRT             (Raíz Cuadrada - Integrante 6)
;   Vector 8 (+0x28): JMP FPU_BRUN          (Constante de Brun - Integrante 7)
; ------------------------------------------------------------------------------
FPU_VECTORES:
VEC_FADD:
    JMP FADD
VEC_FSUB:
    JMP FSUB
VEC_FMUL:
    JMP FMUL
VEC_FDIV:
    JMP FDIV
VEC_FCMP:
    JMP FCMP
VEC_INT_TO_FLOAT:
    JMP FPU_INT_TO_FLOAT
VEC_FLOAT_TO_INT:
    JMP FPU_FLOAT_TO_INT
VEC_FSQRT:
    JMP FSQRT
VEC_FBRUN:
    JMP FPU_BRUN

; ------------------------------------------------------------------------------
; SUBRUTINA: FPU_INT_TO_FLOAT (alias INT64_TO_FLOAT64)
;
; Convierte un entero con signo de 64 bits (complemento a 2) a formato IEEE 754
; de doble precisión (binary64).
;
; Procedimiento técnico:
;   1. Comprueba si el entero es 0; si es así, retorna 0.0 (+0.0 en IEEE 754).
;   2. Extrae el signo S = (R1 >> 63) & 1.
;   3. Si es negativo, verifica si es INT64_MIN (-2^63) y calcula |X| = -X.
;   4. Normaliza la mantisa |X| buscando que el bit más significativo (MSB)
;      coincida con la posición 52 (el bit implícito de la mantisa IEEE 754).
;      - Exponente sesgado base para bit 52: E = 1023 + 52 = 1075.
;      - Si |X| >= 2^53 (bits > 52 activos): corre a la derecha, incrementa E
;        y acumula bits expulsados para redondeo al par más cercano.
;      - Si |X| < 2^52: corre a la izquierda y decrementa E.
;   5. Llama a FPU_EMPAQUETAR para ensamblar la palabra IEEE 754 final.
;
; Entrada:
;   R1: Entero con signo de 64 bits.
; Salida:
;   R5: Patrón binario IEEE 754 de 64 bits (en RV).
; Registros modificados:
;   R1, R2, R3, R4, R5.
; ------------------------------------------------------------------------------
FPU_INT_TO_FLOAT:
INT64_TO_FLOAT64:
    ; 1. Caso rápido: si R1 == 0, retornar 0.0
    CMP R1, R0
    JZ I2F_RET_CERO

    ; 2. Determinar signo y calcular valor absoluto |X|
    SHR R2, R1, 63          ; R2 = Signo S (0 o 1)
    CMP R2, R0
    JZ I2F_POSITIVO

    ; Comprobar caso límite INT64_MIN (-0x8000000000000000 = -2^63)
    SHL R3, R1, 1
    CMP R3, R0
    JZ I2F_CASO_INT64_MIN

    ; Negativo ordinario: |X| = 0 - X
    SUB R1, R0, R1          ; R1 = |X| > 0
    JMP I2F_NORMALIZAR

I2F_POSITIVO:
    ; Ya es positivo en R1

I2F_NORMALIZAR:
    ; R1 = |X| > 0
    ; R2 = Signo S (0 o 1)
    ; Exponente base para bit 52: 1023 + 52 = 1075 (0x433)
    ADDI R3, R0, 1075       ; R3 = Exponente E inicial
    ADDI R5, R0, 0          ; R5 = Bit guardado para redondeo (G)

    ; Comprobar si |X| >= 2^53 (bits por encima del bit 52 activos)
I2F_CHECK_DERECHA:
    SHR R4, R1, 53
    CMP R4, R0
    JZ I2F_CHECK_IZQUIERDA

    ; Bucle de corrimiento a la derecha si |X| >= 2^53
I2F_LOOP_DERECHA:
    ; Guardar bit 0 en R5 antes de expulsar (Guard bit)
    ADDI R5, R0, 1
    AND R5, R1, R5          ; R5 = último bit expulsado
    SHR R1, R1, 1           ; R1 >>= 1
    ADDI R3, R3, 1          ; E += 1
    SHR R4, R1, 53
    CMP R4, R0
    JNZ I2F_LOOP_DERECHA

    ; Aplicar redondeo al par más cercano (round-to-nearest, ties to even):
    ; Si el bit expulsado fue 1 y (LSB de mantisa == 1), suma 1 para redondear al par
    CMP R5, R0
    JZ I2F_FINALIZAR_MANTISA
    ADDI R5, R0, 1
    AND R5, R1, R5          ; R5 = LSB actual de mantisa
    CMP R5, R0
    JZ I2F_FINALIZAR_MANTISA
    ADDI R1, R1, 1          ; Redondeo al par
    ; Verificar si el redondeo desbordó la mantisa (bit 53 activo)
    SHR R4, R1, 53
    CMP R4, R0
    JZ I2F_FINALIZAR_MANTISA
    SHR R1, R1, 1
    ADDI R3, R3, 1
    JMP I2F_FINALIZAR_MANTISA

I2F_CHECK_IZQUIERDA:
    ; Comprobar si bit 52 es 1
    SHR R4, R1, 52
    CMP R4, R0
    JNZ I2F_FINALIZAR_MANTISA

    ; Bucle de corrimiento a la izquierda si |X| < 2^52
I2F_LOOP_IZQUIERDA:
    SHL R1, R1, 1           ; R1 <<= 1
    SUBI R3, R3, 1          ; E -= 1
    SHR R4, R1, 52
    CMP R4, R0
    JZ I2F_LOOP_IZQUIERDA

I2F_FINALIZAR_MANTISA:
    ; Preparar argumentos para FPU_EMPAQUETAR:
    ;   R2 = Signo S
    ;   R3 = Exponente E
    ;   R4 = Mantisa M con bit 52 implícito activo
    ADDI R4, R1, 0
    CALL FPU_EMPAQUETAR
    RET

I2F_CASO_INT64_MIN:
    ; -2^63 en IEEE 754: S=1, E=63+1023=1086 (0x43E), Frac=0 -> 0xC3E0000000000000
    ADDI R5, R0, 1
    SHL R5, R5, 63          ; R5 = 0x8000000000000000
    ADDI R3, R0, 1086
    SHL R3, R3, 52          ; R3 = 0x43E0000000000000
    OR R5, R5, R3           ; R5 = 0xC3E0000000000000
    RET

I2F_RET_CERO:
    ADDI R5, R0, 0
    RET

; ------------------------------------------------------------------------------
; SUBRUTINA: FPU_FLOAT_TO_INT (alias FLOAT64_TO_INT64)
;
; Convierte un flotante IEEE 754 de 64 bits a un entero con signo de 64 bits,
; truncando la parte decimal hacia cero.
;
; Procedimiento técnico:
;   1. Desempaqueta mediante FPU_DESEMPAQUETAR: S, E, M (con bit 52 implícito).
;   2. Evalúa si E == 0 (cero o subnormal): la magnitud es < 1.0, retorna 0.
;   3. Evalúa si E == 0x7FF (Infinito o NaN): retorna 0.
;   4. Calcula exponente real e = E - 1023.
;      - Si e < 0: |X| < 1.0, retorna 0.
;      - Si e > 62: desbordamiento de entero de 64 bits con signo (satura a MAX/MIN).
;      - Si e == 52: la mantisa M ya es el entero exacto.
;      - Si e < 52: desplaza a la derecha (52 - e) posiciones: M >>= (52 - e).
;      - Si e > 52: desplaza a la izquierda (e - 52) posiciones: M <<= (e - 52).
;   5. Aplica signo en complemento a 2 si S == 1.
;
; Entrada:
;   R1: Flotante IEEE 754 de 64 bits.
; Salida:
;   R5: Entero con signo de 64 bits truncado hacia cero (en RV).
; Registros modificados:
;   R1, R2, R3, R4, R5.
; ------------------------------------------------------------------------------
FPU_FLOAT_TO_INT:
FLOAT64_TO_INT64:
    ; 1. Desempaquetar
    ENTER 16
    CALL FPU_DESEMPAQUETAR
    STORE R2, [BP - 8]      ; Guardar Signo S en pila

    ; 2. Casos de cero o subnormal (E == 0)
    CMP R3, R0
    JZ F2I_RET_CERO

    ; Caso Infinito / NaN (E == 0x7FF)
    ADDI R5, R0, 0x07FF
    CMP R3, R5
    JZ F2I_RET_CERO

    ; 3. Exponente real e = E - 1023
    ADDI R5, R0, 1023
    CMP R3, R5
    JN F2I_RET_CERO         ; Si E < 1023 -> e < 0 (|X| < 1.0) -> Trunca a 0

    SUB R3, R3, R5          ; R3 = e >= 0

    ; 4. Comprobar desbordamiento de entero con signo (e > 62)
    ADDI R5, R0, 62
    CMP R3, R5
    JP F2I_OVERFLOW

    ; 5. Alinear mantisa M
    ADDI R5, R0, 52
    CMP R3, R5
    JZ F2I_APLICAR_SIGNO
    JP F2I_SHIFT_LEFT

    ; Caso e < 52: desplazar a la derecha (52 - e) veces
    SUB R5, R5, R3          ; R5 = 52 - e > 0
F2I_LOOP_SHR:
    SHR R4, R4, 1
    SUBI R5, R5, 1
    JNZ F2I_LOOP_SHR
    JMP F2I_APLICAR_SIGNO

F2I_SHIFT_LEFT:
    ; Caso e > 52: desplazar a la izquierda (e - 52) veces
    SUB R5, R3, R5          ; R5 = e - 52 > 0
F2I_LOOP_SHL:
    SHL R4, R4, 1
    SUBI R5, R5, 1
    JNZ F2I_LOOP_SHL

F2I_APLICAR_SIGNO:
    ; R4 contiene la magnitud entera truncada
    LOAD R2, [BP - 8]       ; Recuperar Signo S
    CMP R2, R0
    JZ F2I_POSITIVO

    ; Negativo: R5 = -R4
    SUB R5, R0, R4
    LEAVE
    RET

F2I_POSITIVO:
    ADDI R5, R4, 0
    LEAVE
    RET

F2I_RET_CERO:
    ADDI R5, R0, 0
    LEAVE
    RET

F2I_OVERFLOW:
    LOAD R2, [BP - 8]
    CMP R2, R0
    JZ F2I_MAX_INT
    ; Negativo saturado: INT64_MIN = 0x8000000000000000
    ADDI R5, R0, 1
    SHL R5, R5, 63
    LEAVE
    RET

F2I_MAX_INT:
    ; Positivo saturado: INT64_MAX = 0x7FFFFFFFFFFFFFFF
    ADDI R5, R0, 1
    SHL R5, R5, 63
    SUBI R5, R5, 1
    LEAVE
    RET
