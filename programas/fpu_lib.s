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

; ==============================================================================
; Computador Enigma-64 (Noctua Systems)
; Modulo FPU: FCMP (Comparacion IEEE 754 Doble Precision - binary64)
; Autor: Michael Stiven Betancourt Gelves
;
; Contenido:
;   1. FCMP: comparacion quieta de dos patrones IEEE-754 binary64.
;
; Convencion de llamada:
;   * Entrada: R1 = operando A, R2 = operando B.
;   * Salida: R5 = -1 si A < B, 0 si A == B, 1 si A > B,
;             2 si la comparacion es unordered por NaN.
;   * -1 se representa como 0xFFFFFFFFFFFFFFFF en el registro de 64 bits.
;
; Reglas IEEE-754:
;   * +0 y -0 son iguales.
;   * Los NaN no tienen orden y producen 2.
;   * Los infinitos respetan el orden numerico.
;   * No se modifica el estado de excepciones de la CPU.
; ==============================================================================\n
FCMP:
    ENTER 32
    STORE R1, [BP - 8]
    STORE R2, [BP - 16]

    ; abs(x) = x sin el bit de signo; R4 = +infinito.
    SHL R3, R1, 1
    SHR R3, R3, 1
    SHL R4, R2, 1
    SHR R4, R4, 1
    ADDI R5, R0, 0x07FF
    SHL R5, R5, 52

    ; NaN: exponente 0x7FF y fraccion distinta de cero.
    CMP R5, R3
    JC FCMP_UNORDERED
    CMP R5, R4
    JC FCMP_UNORDERED

    ; +0 y -0 son iguales.
    CMP R3, R0
    JNZ FCMP_NO_A_ZERO
    CMP R4, R0
    JZ FCMP_EQUAL
FCMP_NO_A_ZERO:
    CMP R4, R0
    JZ FCMP_SIGNED_RESULT

    ; Signos distintos: el negativo es menor.
    LOAD R1, [BP - 8]
    LOAD R2, [BP - 16]
    SHR R1, R1, 63
    SHR R2, R2, 63
    CMP R1, R2
    JZ FCMP_SAME_SIGN
    CMP R1, R0
    JZ FCMP_GREATER
    JMP FCMP_LESS

FCMP_SAME_SIGN:
    ; Mismos signos: comparar magnitudes y cambiar el sentido para negativos.
    LOAD R1, [BP - 8]
    LOAD R2, [BP - 16]
    SHL R1, R1, 1
    SHR R1, R1, 1
    SHL R2, R2, 1
    SHR R2, R2, 1
    CMP R1, R2
    JZ FCMP_EQUAL
    JC FCMP_MAG_A_LESS
    ; A tiene mayor magnitud.
    LOAD R1, [BP - 8]
    SHR R1, R1, 63
    CMP R1, R0
    JZ FCMP_GREATER
    JMP FCMP_LESS
FCMP_MAG_A_LESS:
    LOAD R1, [BP - 8]
    SHR R1, R1, 63
    CMP R1, R0
    JZ FCMP_LESS
    JMP FCMP_GREATER

FCMP_SIGNED_RESULT:
    ; Solo uno es cero: el signo del cero no altera el orden numerico.
    LOAD R1, [BP - 8]
    SHR R1, R1, 63
    CMP R1, R0
    JZ FCMP_GREATER
    JMP FCMP_LESS
FCMP_UNORDERED:
    ADDI R5, R0, 2
    LEAVE
    RET
FCMP_EQUAL:
    ADDI R5, R0, 0
    LEAVE
    RET
FCMP_LESS:
    ADDI R5, R0, -1
    LEAVE
    RET
FCMP_GREATER:
    ADDI R5, R0, 1
    LEAVE
    RET

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
