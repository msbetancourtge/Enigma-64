; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Modulo Oficial: FPU Núcleo & FADD / FSUB (IEEE 754 Doble Precisión - 64 bits)
;
; Contenido:
;   1. FPU_DESEMPAQUETAR: Descompone IEEE 754 (64b) en Signo, Exponente y Mantisa.
;   2. FPU_EMPAQUETAR:    Construye IEEE 754 (64b) a partir de Signo, Exponente y Mantisa.
;   3. FSUB:              Resta de flotantes: A - B = A + (-B).
;   4. FADD:              Suma de flotantes con alineación por corrimiento de mantisas,
;                         evaluación de diferencia de exponentes (Delta E) y renormalización.
; ==============================================================================

; ------------------------------------------------------------------------------
; SUBRUTINA: FPU_DESEMPAQUETAR
;
; Extrae los componentes de un flotante IEEE 754 de 64 bits (binary64).
; Formato IEEE 754 de 64 bits:
;   Bit 63:       Signo S (1 bit)
;   Bits [62:52]: Exponente E (11 bits, sesgo 1023)
;   Bits [51:0]:  Fracción F (52 bits)
;
; Entrada:
;   R1: Flotante de 64 bits (IEEE 754).
;
; Salidas:
;   R2: Signo S (0 para positivo, 1 para negativo).
;   R3: Exponente E sesgado (11 bits, 0x000 a 0x7FF).
;   R4: Mantisa M (53 bits, con el bit 52 implícito = 1 si E != 0).
;
; Registros modificados:
;   R2, R3, R4, R5 (R1 se preserva intacto).
; ------------------------------------------------------------------------------
FPU_DESEMPAQUETAR:
    ; 1. Extraer Signo: S = (R1 >> 63) & 1
    SHR R2, R1, 63

    ; 2. Extraer Exponente: E = (R1 >> 52) & 0x07FF
    SHR R3, R1, 52
    ADDI R5, R0, 0x07FF
    AND R3, R3, R5

    ; 3. Extraer Fracción (bits 51:0): Limpiar bits 63:52
    SHL R4, R1, 12
    SHR R4, R4, 12

    ; 4. Añadir bit 52 implícito si E != 0 (número normalizado)
    CMP R3, R0
    JZ DESEMP_FIN

    ; Construir máscara de bit 52: 1 << 52 = 0x0010000000000000
    ADDI R5, R0, 1
    SHL R5, R5, 52
    OR R4, R4, R5

DESEMP_FIN:
    RET

; ------------------------------------------------------------------------------
; SUBRUTINA: FPU_EMPAQUETAR
;
; Reconstruye una palabra de 64 bits en formato canónico IEEE 754 binary64.
;
; Entradas:
;   R2: Signo S (bit 0 = 0 o 1).
;   R3: Exponente E sesgado (11 bits).
;   R4: Mantisa M con bit 52 implícito.
;
; Salida:
;   R5: Palabra de 64 bits IEEE 754 (almacenada en el registro de retorno RV).
;
; Registros modificados:
;   R2, R3, R4, R5.
; ------------------------------------------------------------------------------
FPU_EMPAQUETAR:
    ; 1. Comprobar casos de cero o subdesbordamiento de mantisa/exponente
    CMP R4, R0
    JZ PACK_ZERO
    CMP R3, R0
    JZ PACK_ZERO

    ; 2. Limpiar bit 52 implícito para conservar únicamente la fracción de 52 bits
    SHL R4, R4, 12
    SHR R4, R4, 12

    ; 3. Posicionar Exponente: (E & 0x7FF) << 52
    ADDI R5, R0, 0x07FF
    AND R3, R3, R5
    SHL R3, R3, 52

    ; 4. Posicionar Signo: (S & 1) << 63
    SHL R2, R2, 63

    ; 5. Ensamblar palabra final: R5 = Signo | Exponente | Fracción
    OR R5, R2, R3
    OR R5, R5, R4
    RET

PACK_ZERO:
    ; Retorna 0.0 respetando el signo
    SHL R5, R2, 63
    RET

; ------------------------------------------------------------------------------
; SUBRUTINA: FSUB
;
; Resta de dos flotantes IEEE 754 de 64 bits: R5 = R1 - R2.
; Aplica la identidad fundamental: A - B = A + (-B).
;
; Entradas:
;   R1: Operando A (minuendo).
;   R2: Operando B (sustraendo).
;
; Salida:
;   R5: Resultado A - B en 64 bits IEEE 754 (registro RV).
; ------------------------------------------------------------------------------
FSUB:
    ; Invertir el bit 63 (signo) de B mediante XOR con 0x8000000000000000
    ADDI R3, R0, 1
    SHL R3, R3, 63
    XOR R2, R2, R3
    ; Flujo continuo hacia FADD...

; ------------------------------------------------------------------------------
; SUBRUTINA: FADD
;
; Suma de dos flotantes IEEE 754 de 64 bits: R5 = R1 + R2.
;
; Procedimiento técnico:
;   1. Manejo de identidades con cero.
;   2. Creación de marco de pila (Stack Frame con ENTER 64).
;   3. Desempaquetado de operandos A y B.
;   4. Comparación y ordenamiento: asegurar que |A| >= |B| para que E_A >= E_B.
;   5. Evaluación de diferencia de exponentes: Delta E = E_A - E_B.
;   6. Alineación de mantisas mediante desplazamiento unitario iterativo: M_B >>= 1.
;   7. Operación aritmética: Suma si signos iguales, Resta si signos opuestos.
;   8. Renormalización:
;      - A la derecha con incremento de exponente ante desbordamiento en suma.
;      - A la izquierda con decremento de exponente ante cancelación en resta.
;   9. Empaquetado final llamando a FPU_EMPAQUETAR y liberación del marco con LEAVE.
;
; Entradas:
;   R1: Operando A.
;   R2: Operando B.
;
; Salida:
;   R5: Resultado A + B en 64 bits IEEE 754.
; ------------------------------------------------------------------------------
FADD:
    ; 1. Casos rápidos de cero
    CMP R1, R0
    JZ FADD_CASO_A_CERO
    CMP R2, R0
    JZ FADD_CASO_B_CERO

    ; 2. Crear marco de pila de 64 bytes para variables locales
    ENTER 64

    ; Salvar copia del operando B en la pila [BP - 32]
    STORE R2, [BP - 32]

    ; 3. Desempaquetar operando A (R1)
    CALL FPU_DESEMPAQUETAR
    STORE R2, [BP - 8]       ; [BP - 8]  <- S_A
    STORE R3, [BP - 16]      ; [BP - 16] <- E_A
    STORE R4, [BP - 24]      ; [BP - 24] <- M_A

    ; Desempaquetar operando B (recuperado de la pila)
    LOAD R1, [BP - 32]
    CALL FPU_DESEMPAQUETAR
    STORE R2, [BP - 32]      ; [BP - 32] <- S_B
    STORE R3, [BP - 40]      ; [BP - 40] <- E_B
    STORE R4, [BP - 48]      ; [BP - 48] <- M_B

    ; 4. Comparación de exponentes: garantizar E_A >= E_B
    LOAD R3, [BP - 16]       ; R3 = E_A
    LOAD R4, [BP - 40]       ; R4 = E_B
    CMP R3, R4
    JN FADD_DO_SWAP          ; Si E_A < E_B, intercambiar A y B
    JNZ FADD_CHECK_ALINEAR   ; Si E_A > E_B, proceder a alineación

    ; Si los exponentes son idénticos, asegurar que M_A >= M_B
    LOAD R1, [BP - 24]       ; M_A
    LOAD R2, [BP - 48]       ; M_B
    CMP R1, R2
    JN FADD_DO_SWAP          ; Si M_A < M_B, intercambiar A y B
    JMP FADD_CHECK_ALINEAR

FADD_DO_SWAP:
    ; Intercambiar A y B en las ranuras de la pila
    ; Swap S_A <-> S_B
    LOAD R1, [BP - 8]
    LOAD R2, [BP - 32]
    STORE R2, [BP - 8]
    STORE R1, [BP - 32]
    ; Swap E_A <-> E_B
    LOAD R1, [BP - 16]
    LOAD R2, [BP - 40]
    STORE R2, [BP - 16]
    STORE R1, [BP - 40]
    ; Swap M_A <-> M_B
    LOAD R1, [BP - 24]
    LOAD R2, [BP - 48]
    STORE R2, [BP - 24]
    STORE R1, [BP - 48]

FADD_CHECK_ALINEAR:
    ; 5. Calcular Delta E = E_A - E_B (garantizado >= 0)
    LOAD R3, [BP - 16]       ; E_A
    LOAD R4, [BP - 40]       ; E_B
    SUB R1, R3, R4           ; R1 = Delta E
    LOAD R2, [BP - 48]       ; R2 = M_B

    ; Si Delta E > 54, M_B se anula completamente por pérdida de precisión
    ADDI R3, R0, 54
    CMP R1, R3
    JP FADD_MB_ANULAR

    ; Bucle de corrimiento iterativo para alineación: M_B >>= 1 por cada unidad de Delta E
FADD_LOOP_ALINEAR:
    CMP R1, R0
    JZ FADD_FIN_ALINEAR
    SHR R2, R2, 1
    SUBI R1, R1, 1
    JNZ FADD_LOOP_ALINEAR
    JMP FADD_FIN_ALINEAR

FADD_MB_ANULAR:
    ADDI R2, R0, 0

FADD_FIN_ALINEAR:
    STORE R2, [BP - 48]      ; Guardar M_B alineada en pila

    ; 6. Preparar operandos para la operación aritmética
    LOAD R1, [BP - 8]        ; R1 = S_A (Signo dominante)
    LOAD R2, [BP - 32]       ; R2 = S_B
    LOAD R3, [BP - 24]       ; R3 = M_A
    LOAD R4, [BP - 48]       ; R4 = M_B alineada
    LOAD R5, [BP - 16]       ; R5 = E_A (Exponente preliminar del resultado)

    ; Comparar signos
    CMP R1, R2
    JNZ FADD_OP_RESTA

    ; ---- SUMA DE MANTISAS (Signos iguales) ----
    ADD R3, R3, R4           ; M_R = M_A + M_B

    ; Verificar desbordamiento de mantisa (bit 53 activo): (M_R >> 53) != 0
    SHR R2, R3, 53
    CMP R2, R0
    JZ FADD_INVOCAR_EMPAQUETAR

    ; Desbordamiento detectado: M_R >>= 1 y E_R += 1
    SHR R3, R3, 1
    ADDI R5, R5, 1
    JMP FADD_INVOCAR_EMPAQUETAR

    ; ---- RESTA DE MANTISAS (Signos opuestos) ----
FADD_OP_RESTA:
    SUB R3, R3, R4           ; M_R = M_A - M_B

    ; Si el resultado es cero absoluto
    CMP R3, R0
    JZ FADD_RESULTADO_CERO

    ; Construir máscara de bit 52 para renormalización: 1 << 52
    ADDI R2, R0, 1
    SHL R2, R2, 52           ; R2 = 0x0010000000000000

    ; Bucle de renormalización hacia la izquierda: M_R <<= 1, E_R -= 1
FADD_LOOP_RENORM:
    AND R4, R3, R2           ; Evaluar si bit 52 está activo
    JNZ FADD_INVOCAR_EMPAQUETAR
    SHL R3, R3, 1
    SUBI R5, R5, 1
    CMP R5, R0
    JZ FADD_INVOCAR_EMPAQUETAR
    JMP FADD_LOOP_RENORM

FADD_RESULTADO_CERO:
    ADDI R5, R0, 0
    LEAVE
    RET

FADD_INVOCAR_EMPAQUETAR:
    ; Pasar argumentos a FPU_EMPAQUETAR:
    ;   R2 = Signo (S_A)
    ;   R3 = Exponente (E_R)
    ;   R4 = Mantisa (M_R)
    ADDI R2, R1, 0           ; R2 = S_R
    ADDI R4, R3, 0           ; R4 = M_R
    ADDI R3, R5, 0           ; R3 = E_R
    CALL FPU_EMPAQUETAR
    LEAVE
    RET

FADD_CASO_A_CERO:
    ADDI R5, R2, 0
    RET

FADD_CASO_B_CERO:
    ADDI R5, R1, 0
    RET
