; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Modulo FPU: FDIV (Division IEEE 754 Doble Precision - binary64)
; Autor: Michael Stiven Betancourt Gelves
;
; Contenido:
;   1. FDIV: division binaria IEEE-754 con casos especiales y subnormales.
;
; Convencion de llamada:
;   * Entrada: R1 = dividendo A, R2 = divisor B.
;   * Salida: R5 = A / B como patron IEEE-754 binary64.
;   * R1..R5 son registros temporales; SP y BP se restauran con LEAVE.
;
; Casos especiales:
;   * NaN: propagacion silenciada del operando NaN.
;   * 0/0 e infinito/infinito: NaN canonico.
;   * Division por cero: infinito con el signo XOR de los operandos.
;   * Cero e infinito: conservan el signo XOR correspondiente.
;
; El cociente usa division larga de mantisas, bit de guarda, bit pegajoso,
; redondeo al par mas cercano y empaquetado de resultados normales/subnormales.
; Dependencias: FPU_DESEMPAQUETAR y FPU_EMPAQUETAR de fpu.s.
; ==============================================================================\n
FDIV:
    ENTER 160
    STORE R1, [BP - 8]       ; A original
    STORE R2, [BP - 16]      ; B original

    ; Signo del resultado.
    XOR R3, R1, R2
    SHR R3, R3, 63
    STORE R3, [BP - 24]

    ; Clasificacion inicial.
    SHL R3, R1, 1
    SHR R3, R3, 1
    SHL R4, R2, 1
    SHR R4, R4, 1
    STORE R3, [BP - 32]      ; abs(A)
    STORE R4, [BP - 40]      ; abs(B)
    ADDI R5, R0, 0x07FF
    SHL R5, R5, 52
    STORE R5, [BP - 48]      ; infinito positivo

    ; NaN: abs(x) > infinito.
    CMP R5, R3
    JC FDIV_NAN_A
    CMP R5, R4
    JC FDIV_NAN_B

    ; Infinito / infinito es invalido.
    CMP R3, R5
    JNZ FDIV_A_NO_INF
    CMP R4, R5
    JZ FDIV_INVALID
    JMP FDIV_RETURN_INF
FDIV_A_NO_INF:
    ; x / infinito = cero con signo; infinito ya se trato arriba.
    CMP R4, R5
    JNZ FDIV_B_NO_INF
    JMP FDIV_RETURN_ZERO
FDIV_B_NO_INF:
    ; Ceros: 0/0 invalido; x/0 infinito; 0/x cero.
    CMP R4, R0
    JNZ FDIV_B_NOT_ZERO
    CMP R3, R0
    JZ FDIV_INVALID
    JMP FDIV_RETURN_INF
FDIV_B_NOT_ZERO:
    CMP R3, R0
    JZ FDIV_RETURN_ZERO

    ; Desempaquetar y normalizar A.
    LOAD R1, [BP - 8]
    CALL FPU_DESEMPAQUETAR
    STORE R4, [BP - 72]      ; mantisa A
    CMP R3, R0
    JZ FDIV_NORM_A_SUB
    SUBI R3, R3, 1023
    STORE R3, [BP - 56]      ; exponente A sin sesgo
    JMP FDIV_NORM_B
FDIV_NORM_A_SUB:
    ADDI R3, R0, -1022
FDIV_NORM_A_LOOP:
    SHR R5, R4, 52
    ADDI R1, R0, 1
    AND R5, R5, R1
    JNZ FDIV_NORM_A_DONE
    SHL R4, R4, 1
    SUBI R3, R3, 1
    JMP FDIV_NORM_A_LOOP
FDIV_NORM_A_DONE:
    STORE R4, [BP - 72]
    STORE R3, [BP - 56]

    ; Desempaquetar y normalizar B.
FDIV_NORM_B:
    LOAD R1, [BP - 16]
    CALL FPU_DESEMPAQUETAR
    STORE R4, [BP - 80]      ; mantisa B
    CMP R3, R0
    JZ FDIV_NORM_B_SUB
    SUBI R3, R3, 1023
    STORE R3, [BP - 64]
    JMP FDIV_PREP_DIV
FDIV_NORM_B_SUB:
    ADDI R3, R0, -1022
FDIV_NORM_B_LOOP:
    SHR R5, R4, 52
    ADDI R1, R0, 1
    AND R5, R5, R1
    JNZ FDIV_NORM_B_DONE
    SHL R4, R4, 1
    SUBI R3, R3, 1
    JMP FDIV_NORM_B_LOOP
FDIV_NORM_B_DONE:
    STORE R4, [BP - 80]
    STORE R3, [BP - 64]

FDIV_PREP_DIV:
    ; Exponente preliminar y division larga de mantisas.
    LOAD R1, [BP - 56]
    LOAD R2, [BP - 64]
    SUB R1, R1, R2
    STORE R1, [BP - 88]      ; exponente preliminar

    ; Primera fase: consumir los 53 bits de A y obtener el bit entero.
    ADDI R1, R0, 0
    STORE R1, [BP - 96]      ; resto
    LOAD R2, [BP - 72]      ; fuente A
    LOAD R4, [BP - 80]      ; divisor B
    ADDI R5, R0, 53
FDIV_DIVIDENDO:
    SHR R3, R2, 52
    ADDI R1, R0, 1
    AND R3, R3, R1
    SHL R2, R2, 1
    LOAD R1, [BP - 96]
    SHL R1, R1, 1
    OR R1, R1, R3
    CMP R1, R4
    JC FDIV_BIT_CERO
    SUB R1, R1, R4
    ADDI R3, R0, 1
    JMP FDIV_GUARDAR_BIT
FDIV_BIT_CERO:
    ADDI R3, R0, 0
FDIV_GUARDAR_BIT:
    STORE R1, [BP - 96]
    SUBI R5, R5, 1
    JNZ FDIV_DIVIDENDO
    STORE R3, [BP - 104]      ; bit entero q0

    ; Segunda fase: 53 bits fraccionarios para la mantisa.
    LOAD R3, [BP - 104]
    STORE R3, [BP - 112]      ; cociente Q
    LOAD R1, [BP - 96]
    LOAD R4, [BP - 80]
    ADDI R5, R0, 53
FDIV_FRACCION:
    SHL R1, R1, 1
    CMP R1, R4
    JC FDIV_FRAC_CERO
    SUB R1, R1, R4
    ADDI R2, R0, 1
    JMP FDIV_FRAC_GUARDAR
FDIV_FRAC_CERO:
    ADDI R2, R0, 0
FDIV_FRAC_GUARDAR:
    LOAD R3, [BP - 112]
    SHL R3, R3, 1
    OR R3, R3, R2
    STORE R3, [BP - 112]
    SUBI R5, R5, 1
    JNZ FDIV_FRACCION
    STORE R1, [BP - 96]

    ; Bit de guarda y bit pegajoso.
    SHL R1, R1, 1
    CMP R1, R4
    JC FDIV_GUARD_CERO
    SUB R1, R1, R4
    ADDI R2, R0, 1
    JMP FDIV_GUARD_LISTO
FDIV_GUARD_CERO:
    ADDI R2, R0, 0
FDIV_GUARD_LISTO:
    STORE R2, [BP - 120]
    CMP R1, R0
    JZ FDIV_STICKY_CERO
    ADDI R1, R0, 1
    JMP FDIV_STICKY_LISTO
FDIV_STICKY_CERO:
    ADDI R1, R0, 0
FDIV_STICKY_LISTO:
    STORE R1, [BP - 128]

    ; Normalizar antes de redondear. Si Q >= 1, el bit 0 de Q
    ; se convierte en el nuevo bit de guarda al hacer Q >>= 1.
    LOAD R3, [BP - 112]
    SHR R1, R3, 53
    CMP R1, R0
    JZ FDIV_Q_MENOR_UNO
    ADDI R2, R0, 1
    AND R2, R3, R2
    SHR R3, R3, 1
    STORE R3, [BP - 112]
    LOAD R1, [BP - 128]
    LOAD R5, [BP - 120]
    OR R1, R1, R5
    STORE R1, [BP - 128]
    JMP FDIV_REDONDEO_FINAL
FDIV_Q_MENOR_UNO:
    LOAD R1, [BP - 88]
    SUBI R1, R1, 1
    STORE R1, [BP - 88]
    LOAD R2, [BP - 120]
    LOAD R1, [BP - 128]

FDIV_REDONDEO_FINAL:
    ; Redondeo al par: guard && (sticky || mantisa impar).
    LOAD R3, [BP - 112]
    CMP R2, R0
    JZ FDIV_NO_ROUND_GUARD
    CMP R1, R0
    JNZ FDIV_REDONDEAR
    ADDI R5, R0, 1
    AND R5, R3, R5
    CMP R5, R0
    JZ FDIV_NO_ROUND_GUARD
FDIV_REDONDEAR:
    ADDI R3, R3, 1
FDIV_NO_ROUND_GUARD:
    ; El redondeo puede producir 2.0; volver a normalizar en ese caso.
    SHR R5, R3, 53
    CMP R5, R0
    JZ FDIV_STORE_Q_FINAL
    SHR R3, R3, 1
    LOAD R5, [BP - 88]
    ADDI R5, R5, 1
    STORE R5, [BP - 88]
FDIV_STORE_Q_FINAL:
    STORE R3, [BP - 112]

FDIV_PACK_RESULT:
    ; Overflow del exponente: resultado infinito.
    LOAD R1, [BP - 88]
    ADDI R2, R0, 1023
    CMP R1, R2
    JP FDIV_RETURN_INF

    ; Underflow: desplazar la mantisa a fraccion subnormal.
    ADDI R2, R0, -1022
    CMP R1, R2
    JN FDIV_SUBNORMAL

    ; Resultado normal: empaquetar con exponente sesgado.
    ADDI R1, R1, 1023
    LOAD R2, [BP - 24]
    ADDI R4, R3, 0
    ADDI R3, R1, 0
    CALL FPU_EMPAQUETAR
    LEAVE
    RET

FDIV_SUBNORMAL:
    ; shift = -1022 - E. Se limita a 63; mas alla solo queda cero.
    ADDI R2, R0, -1022
    SUB R5, R2, R1
    ADDI R1, R0, 63
    CMP R5, R1
    JN FDIV_SUB_SHIFT_OK
    ADDI R5, R0, 63
FDIV_SUB_SHIFT_OK:
    ADDI R1, R0, 0
FDIV_SUB_SHIFT_LOOP:
    CMP R5, R0
    JZ FDIV_SUB_SHIFT_DONE
    ADDI R2, R0, 1
    AND R2, R3, R2
    SHR R3, R3, 1
    SUBI R5, R5, 1
    JZ FDIV_SUB_SHIFT_LAST
    OR R1, R1, R2
    JMP FDIV_SUB_SHIFT_LOOP
FDIV_SUB_SHIFT_LAST:
    ; R2 es el bit de guarda; R1 acumula los bits anteriores.
    CMP R2, R0
    JZ FDIV_SUB_ROUND_DONE
    CMP R1, R0
    JNZ FDIV_SUB_ROUND_UP
    ADDI R5, R0, 1
    AND R5, R3, R5
    CMP R5, R0
    JZ FDIV_SUB_ROUND_DONE
FDIV_SUB_ROUND_UP:
    ADDI R3, R3, 1
FDIV_SUB_ROUND_DONE:
FDIV_SUB_SHIFT_DONE:
    ; El signo ocupa bit 63; el campo exponente es cero.
    LOAD R2, [BP - 24]
    SHL R2, R2, 63
    SHR R5, R3, 52
    CMP R5, R0
    JZ FDIV_SUB_PACK
    ADDI R5, R0, 1
    SHL R5, R5, 52
    OR R5, R2, R5
    LEAVE
    RET
FDIV_SUB_PACK:
    OR R5, R2, R3
    LEAVE
    RET

; -----------------------------------------------------------------------------
; Casos especiales de FDIV
; -----------------------------------------------------------------------------
FDIV_NAN_A:
    LOAD R5, [BP - 8]
    JMP FDIV_SILENCIAR_NAN
FDIV_NAN_B:
    LOAD R5, [BP - 16]
FDIV_SILENCIAR_NAN:
    ADDI R4, R0, 1
    SHL R4, R4, 51
    OR R5, R5, R4
    LEAVE
    RET
FDIV_INVALID:
    ADDI R5, R0, 0x0FFF
    SHL R5, R5, 51
    LEAVE
    RET
FDIV_RETURN_INF:
    LOAD R3, [BP - 24]
    ADDI R5, R0, 0x07FF
    SHL R5, R5, 52
    SHL R3, R3, 63
    OR R5, R5, R3
    LEAVE
    RET
FDIV_RETURN_ZERO:
    LOAD R5, [BP - 24]
    SHL R5, R5, 63
    LEAVE
    RET
