; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Modulo FPU: FMUL (Multiplicacion IEEE 754 Doble Precision - binary64)
; Autor: Integrante 2 Tomas Garzon
;
; Contenido:
;   1. FMUL:                       Producto A * B con redondeo al par mas cercano.
;   2. FPU_MUL128:                 Producto entero sin signo 64x64 -> 128 bits.
;   3. FPU_NORMALIZAR_SUBNORMAL:   Lleva una mantisa subnormal a la forma 1.f.
;
; Dependencias (definidas en fpu.s, que debe ensamblarse en la misma unidad):
;   FPU_DESEMPAQUETAR: R1 -> R2 = S, R3 = E sesgado, R4 = M (53 bits). Usa R5.
;   FPU_EMPAQUETAR:    R2 = S, R3 = E (1..2046), R4 = M (bit 52 = 1) -> R5.
;
; Restricciones del ISA que determinan el diseno:
;   * Solo R1..R5 son utilizables (R0 = 0, R6 = SP, R7 = BP): las variables
;     viven en un marco de pila creado con ENTER/LEAVE.
;   * MUL entrega solo los 64 bits bajos: el producto de 106 bits se arma con
;     cuatro productos parciales de 32 x 32 bits (FPU_MUL128).
;   * SHL/SHR solo aceptan corrimientos inmediatos: los corrimientos variables
;     (desnormalizacion) se hacen con bucles de un bit.
;   * Los inmediatos son de 16 bits con extension de signo: las constantes
;     grandes se construyen con ADDI + SHL.
; ==============================================================================

; ------------------------------------------------------------------------------
; SUBRUTINA: FMUL
;
; Multiplicacion de dos flotantes IEEE 754 de 64 bits: R5 = R1 * R2.
;
; Procedimiento:
;   1. Signo del resultado: S = S_A XOR S_B.
;   2. Casos especiales sobre el patron de bits (|x| = x sin el bit 63):
;        NaN * x, x * NaN  -> el NaN de entrada, silenciado (A tiene prioridad)
;        0 * Inf, Inf * 0  -> NaN canonico 0x7FF8000000000000 (operacion invalida)
;        Inf * x (x != 0)  -> Inf con signo S
;        0 * x (x finito)  -> 0 con signo S
;   3. Desempaquetado de A y B; los subnormales se normalizan a 1.f con un
;      exponente que puede quedar <= 0.
;   4. Exponente: E_R = E_A + E_B - 1023 (entero con signo de 64 bits, sin
;      riesgo de desbordar el registro).
;   5. Producto de mantisas P = M_A * M_B, P en [2^104, 2^106), en hi:lo.
;   6. Mantisa de trabajo T = P >> 49 con bit pegajoso (sticky):
;        bits [55:3] significando (53 bits), bit 2 guarda, bit 1 redondeo,
;        bit 0 sticky (OR de todos los bits descartados).
;      Si P >= 2^105 (bit 56 de T activo): T >>= 1 conservando sticky, E_R++.
;   7. Subdesbordamiento: si E_R <= 0, T >>= (1 - E_R) con sticky y E_R = 0
;      (resultado subnormal o cero con signo).
;   8. Redondeo al par mas cercano: M = (T + 3 + lsb) >> 3, con lsb = bit 3
;      de T. Si M llega a 2^53: M >>= 1, E_R++.
;   9. Desbordamiento: si E_R >= 2047 -> Inf con signo S.
;  10. Empaquetado: FPU_EMPAQUETAR para normales; para subnormales se arma
;      S << 63 | M directamente (si M = 2^52, el bit 52 cae en el campo de
;      exponente y produce el menor normal, que es lo correcto).
;
; Entradas:
;   R1: Operando A.
;   R2: Operando B.
;
; Salida:
;   R5: Resultado A * B en 64 bits IEEE 754 (registro RV).
;
; Registros modificados:
;   R1, R2, R3, R4, R5. SP y BP se restauran con LEAVE.
;
; Marco de pila (ENTER 64):
;   [BP - 8]  A original          [BP - 40] M_A
;   [BP - 16] B original          [BP - 48] E_B
;   [BP - 24] S_R                 [BP - 56] M_B
;   [BP - 32] E_A, luego E_R
; ------------------------------------------------------------------------------
FMUL:
    ENTER 64
    STORE R1, [BP - 8]
    STORE R2, [BP - 16]

    ; 1. Signo del resultado: S_R = (A XOR B) >> 63
    XOR R3, R1, R2
    SHR R3, R3, 63
    STORE R3, [BP - 24]

    ; 2. Casos especiales. R3 = |A|, R4 = |B|, R5 = 0x7FF0000000000000 (Inf)
    SHL R3, R1, 1
    SHR R3, R3, 1
    SHL R4, R2, 1
    SHR R4, R4, 1
    ADDI R5, R0, 0x07FF
    SHL R5, R5, 52

    ; NaN: |x| > Inf sin signo (CMP pone C = 1 cuando Inf < |x|)
    CMP R5, R3
    JC FMUL_NAN_A
    CMP R5, R4
    JC FMUL_NAN_B

    ; Infinitos
    CMP R3, R5
    JZ FMUL_INF_A
    CMP R4, R5
    JZ FMUL_INF_B

    ; Ceros
    CMP R3, R0
    JZ FMUL_CERO
    CMP R4, R0
    JZ FMUL_CERO

    ; 3. Desempaquetar y normalizar A
    LOAD R1, [BP - 8]
    CALL FPU_DESEMPAQUETAR
    CALL FPU_NORMALIZAR_SUBNORMAL
    STORE R3, [BP - 32]      ; E_A
    STORE R4, [BP - 40]      ; M_A

    ; Desempaquetar y normalizar B
    LOAD R1, [BP - 16]
    CALL FPU_DESEMPAQUETAR
    CALL FPU_NORMALIZAR_SUBNORMAL
    STORE R3, [BP - 48]      ; E_B
    STORE R4, [BP - 56]      ; M_B

    ; 4. Exponente preliminar: E_R = E_A + E_B - 1023
    LOAD R4, [BP - 32]
    ADD R3, R3, R4
    SUBI R3, R3, 1023
    STORE R3, [BP - 32]      ; [BP - 32] <- E_R

    ; 5. Producto de mantisas de 106 bits: R5 = hi, R4 = lo
    LOAD R1, [BP - 40]
    LOAD R2, [BP - 56]
    CALL FPU_MUL128

    ; 6. T = P >> 49 = (hi << 15) | (lo >> 49); sticky = bits [48:0] de lo
    SHL R3, R4, 15           ; R3 != 0 si algun bit descartado esta activo
    SHR R4, R4, 49
    SHL R5, R5, 15
    OR R4, R4, R5            ; R4 = T
    CMP R3, R0
    JZ FMUL_SIN_STICKY
    ADDI R1, R0, 1
    OR R4, R4, R1            ; T |= sticky
FMUL_SIN_STICKY:

    ; Normalizacion: si P >= 2^105 (bit 56 de T), T >>= 1 con sticky y E_R++
    SHR R1, R4, 56
    CMP R1, R0
    JZ FMUL_NORMALIZADO
    ADDI R2, R0, 1
    AND R2, R4, R2           ; bit que sale por la derecha
    SHR R4, R4, 1
    OR R4, R4, R2            ; se conserva en el sticky
    LOAD R3, [BP - 32]
    ADDI R3, R3, 1
    STORE R3, [BP - 32]

FMUL_NORMALIZADO:
    LOAD R3, [BP - 32]       ; R3 = E_R

    ; 7. Subdesbordamiento: si E_R <= 0 se desnormaliza
    CMP R3, R0
    JP FMUL_REDONDEAR

    ; Corrimiento = 1 - E_R, acotado a 60 (a partir de ahi T ya vale 1)
    ADDI R1, R0, 1
    SUB R1, R1, R3
    ADDI R2, R0, 60
    CMP R2, R1               ; C = 1 si 60 < corrimiento
    JNC FMUL_LOOP_DESNORM
    ADDI R1, R0, 60

FMUL_LOOP_DESNORM:
    ADDI R2, R0, 1
    AND R2, R4, R2
    SHR R4, R4, 1
    OR R4, R4, R2            ; T = (T >> 1) | (T & 1)
    SUBI R1, R1, 1
    JNZ FMUL_LOOP_DESNORM
    ADDI R3, R0, 0           ; E_R = 0 marca resultado subnormal

    ; 8. Redondeo al par mas cercano: M = (T + 3 + lsb) >> 3
FMUL_REDONDEAR:
    SHR R1, R4, 3
    ADDI R2, R0, 1
    AND R1, R1, R2           ; lsb del significando
    ADD R4, R4, R1
    ADDI R4, R4, 3
    SHR R4, R4, 3            ; R4 = M redondeada

    CMP R3, R0
    JZ FMUL_EMPAQ_SUBNORMAL

    ; Acarreo del redondeo: M = 2^53 -> M = 2^52, E_R++
    SHR R1, R4, 53
    CMP R1, R0
    JZ FMUL_VERIF_OVERFLOW
    SHR R4, R4, 1
    ADDI R3, R3, 1

    ; 9. Desbordamiento: E_R >= 2047 -> Inf
FMUL_VERIF_OVERFLOW:
    ADDI R1, R0, 0x07FF
    CMP R3, R1
    JN FMUL_EMPAQ_NORMAL
    JMP FMUL_INF

    ; 10. Empaquetado
FMUL_EMPAQ_NORMAL:
    LOAD R2, [BP - 24]       ; R2 = S, R3 = E_R, R4 = M
    CALL FPU_EMPAQUETAR
    LEAVE
    RET

FMUL_EMPAQ_SUBNORMAL:
    LOAD R2, [BP - 24]
    SHL R2, R2, 63
    OR R5, R2, R4            ; campo de exponente 0, fraccion = M
    LEAVE
    RET

    ; ---- Casos especiales ----
FMUL_NAN_A:
    LOAD R5, [BP - 8]
    JMP FMUL_SILENCIAR
FMUL_NAN_B:
    LOAD R5, [BP - 16]
FMUL_SILENCIAR:
    ; Activar el bit 51 (quiet) conservando signo y carga util
    ADDI R4, R0, 1
    SHL R4, R4, 51
    OR R5, R5, R4
    LEAVE
    RET

FMUL_INF_A:
    CMP R4, R0               ; Inf * 0
    JZ FMUL_INVALIDA
    JMP FMUL_INF
FMUL_INF_B:
    CMP R3, R0               ; 0 * Inf
    JZ FMUL_INVALIDA

FMUL_INF:
    ADDI R5, R0, 0x07FF
    SHL R5, R5, 52
    LOAD R3, [BP - 24]
    SHL R3, R3, 63
    OR R5, R5, R3
    LEAVE
    RET

FMUL_INVALIDA:
    ; NaN silencioso canonico: 0x7FF8000000000000
    ADDI R5, R0, 0x0FFF
    SHL R5, R5, 51
    LEAVE
    RET

FMUL_CERO:
    LOAD R5, [BP - 24]
    SHL R5, R5, 63
    LEAVE
    RET

; ------------------------------------------------------------------------------
; SUBRUTINA: FPU_MUL128
;
; Producto entero sin signo de 64 x 64 bits con resultado de 128 bits.
; Como MUL solo conserva los 64 bits bajos, cada operando se parte en dos
; mitades de 32 bits (x = xh*2^32 + xl) y se suman los productos parciales:
;
;   p0 = xl*yl   p1 = xh*yl   p2 = xl*yh   p3 = xh*yh   (todos caben en 64 bits)
;   mid = (p0 >> 32) + lo32(p1) + lo32(p2)             (< 3*2^32, sin acarreo)
;   lo  = (mid << 32) | lo32(p0)
;   hi  = p3 + (p1 >> 32) + (p2 >> 32) + (mid >> 32)
;
; Ninguna suma puede desbordar, asi que no se depende de la bandera C.
;
; Entradas:
;   R1: x.
;   R2: y.
;
; Salidas:
;   R5: 64 bits altos del producto.
;   R4: 64 bits bajos del producto.
;
; Registros modificados:
;   R1, R2, R3, R4, R5.
; ------------------------------------------------------------------------------
FPU_MUL128:
    ENTER 16

    ; Partir operandos en mitades de 32 bits
    SHR R3, R1, 32           ; R3 = xh
    SHL R1, R1, 32
    SHR R1, R1, 32           ; R1 = xl
    SHR R4, R2, 32           ; R4 = yh
    SHL R2, R2, 32
    SHR R2, R2, 32           ; R2 = yl

    ; Productos parciales
    MUL R5, R3, R4           ; p3 = xh*yh
    STORE R5, [BP - 8]
    MUL R5, R1, R2           ; p0 = xl*yl (se conserva en R5)
    STORE R5, [BP - 16]
    MUL R3, R3, R2           ; R3 = p1 = xh*yl
    MUL R4, R1, R4           ; R4 = p2 = xl*yh

    ; hi parcial = p3 + (p1 >> 32) + (p2 >> 32)
    SHR R1, R3, 32
    SHR R2, R4, 32
    ADD R1, R1, R2
    LOAD R2, [BP - 8]
    ADD R1, R1, R2
    STORE R1, [BP - 8]

    ; mid = (p0 >> 32) + lo32(p1) + lo32(p2)
    SHL R3, R3, 32
    SHR R3, R3, 32
    SHL R4, R4, 32
    SHR R4, R4, 32
    ADD R3, R3, R4
    SHR R5, R5, 32
    ADD R3, R3, R5           ; R3 = mid

    ; lo = (mid << 32) | lo32(p0)
    LOAD R4, [BP - 16]
    SHL R4, R4, 32
    SHR R4, R4, 32
    SHL R1, R3, 32
    OR R4, R4, R1

    ; hi = hi parcial + (mid >> 32)
    SHR R3, R3, 32
    LOAD R5, [BP - 8]
    ADD R5, R5, R3

    LEAVE
    RET

; ------------------------------------------------------------------------------
; SUBRUTINA: FPU_NORMALIZAR_SUBNORMAL
;
; Recibe la salida de FPU_DESEMPAQUETAR. Si el operando es subnormal (E = 0,
; sin bit implicito) lo lleva a la forma 1.f: su exponente efectivo es 1, y por
; cada corrimiento a la izquierda de M se decrementa E (puede quedar <= 0).
; Los normales se devuelven sin cambios. Requiere M != 0.
;
; Entradas:
;   R3: Exponente E sesgado.
;   R4: Mantisa M.
;
; Salidas:
;   R3: Exponente ajustado (entero con signo de 64 bits).
;   R4: Mantisa con el bit 52 activo.
;
; Registros modificados:
;   R2, R3, R4, R5.
; ------------------------------------------------------------------------------
FPU_NORMALIZAR_SUBNORMAL:
    CMP R3, R0
    JNZ FPU_NORM_SUB_FIN

    ADDI R3, R0, 1
    ADDI R5, R0, 1
    SHL R5, R5, 52           ; R5 = mascara del bit 52

FPU_NORM_SUB_LOOP:
    AND R2, R4, R5
    JNZ FPU_NORM_SUB_FIN
    SHL R4, R4, 1
    SUBI R3, R3, 1
    JMP FPU_NORM_SUB_LOOP

FPU_NORM_SUB_FIN:
    RET
