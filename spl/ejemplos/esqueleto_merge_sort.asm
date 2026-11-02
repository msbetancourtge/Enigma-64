; ==============================================================================
; esqueleto_merge_sort.asm - ESQUELETO de merge sort sobre vec.asm (Integrante 2).
; Solo muestra que la API de vectores alcanza. El grupo completa los TODO.
;
; Convencion usada (la misma de vec.asm), mas dos reglas para rutinas no hoja:
;   - Mas de 4 argumentos: del 5o en adelante van en la pila. El llamador los
;     apila (PUSH) antes de CALL y los saca despues (ADDI SP, SP, 8 * k).
;     Dentro del llamado, con el marco de abajo, el 5o argumento esta en
;     [BP + 8 * (registros preservados + 2)].
;   - Variables locales en un marco: ENTER t reserva t bytes y las locales
;     quedan en [BP - 8], [BP - 16], ... LEAVE deshace el marco.
;     El programa debe poner SP en un multiplo de 8 antes de la primera
;     llamada: LOAD/STORE sobre [BP - k] exigen alineacion (STATUS_MISALIGNED).
;
; Marco de MERGE_SORT tras PUSH R2, PUSH R3, ENTER 8 (S = SP al entrar):
;   [BP + 24] direccion de retorno   (S)
;   [BP + 16] lo  (R2 preservado)    (S - 8)
;   [BP + 8]  hi  (R3 preservado)    (S - 16)
;   [BP + 0]  BP anterior            (S - 24)
;   [BP - 8]  mid (local)            (S - 32 = SP)
; ==============================================================================
#include "vec.asm"

PRINCIPAL:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000, alineada a 8
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16             ; R1 = base del vector (BASE_VECTORES)
        ADDI R2, R0, 0              ; R2 = lo = 0
        CALL VEC_LEN                ; R5 = n (cabecera en base - 8)
        ADD  R3, R5, R0             ; R3 = hi = n
        ADDI R4, R0, 0x002E
        SHL  R4, R4, 16             ; R4 = aux (BASE_BUFFERS), n elementos libres
        CALL MERGE_SORT
        HLT

; ------------------------------------------------------------------------------
; MERGE_SORT: ordena v[lo, hi)
;   R1 = base, R2 = lo, R3 = hi (exclusivo), R4 = aux. Preserva R1..R4.
; ------------------------------------------------------------------------------
MERGE_SORT:
        PUSH R2                     ; preserva lo
        PUSH R3                     ; preserva hi
        ENTER 8                     ; local: mid en [BP - 8]
        SUB  R5, R3, R2             ; R5 = hi - lo
        SUBI R5, R5, 2
        JN   MS_FIN                 ; menos de 2 elementos: ya esta ordenado
        SUB  R5, R3, R2
        SHR  R5, R5, 1
        ADD  R5, R2, R5             ; R5 = mid = lo + (hi - lo) / 2
        STORE R5, [BP - 8]
        ADD  R3, R5, R0             ; hi = mid
        CALL MERGE_SORT             ; ordena [lo, mid); R1, R2, R4 siguen igual
        LOAD R2, [BP - 8]           ; lo = mid
        LOAD R3, [BP + 8]           ; hi original
        CALL MERGE_SORT             ; ordena [mid, hi)
        LOAD R2, [BP + 16]          ; R2 = lo
        LOAD R3, [BP - 8]           ; R3 = mid
        LOAD R5, [BP + 8]
        PUSH R5                     ; 5o argumento: hi
        CALL MERGE                  ; MERGE(base, lo, mid, aux; hi)
        ADDI SP, SP, 8              ; el llamador retira el 5o argumento
MS_FIN:
        LEAVE                       ; SP = BP y recupera el BP anterior
        POP  R3                     ; restaura hi
        POP  R2                     ; restaura lo
        RET

; ------------------------------------------------------------------------------
; MERGE: mezcla v[lo, mid) y v[mid, hi), ya ordenados, en v[lo, hi)
;   R1 = base, R2 = lo, R3 = mid, R4 = aux, pila: hi. Preserva R1..R4.
;   Marco tras PUSH R1..R4 y ENTER 24:
;     [BP + 48] hi (5o argumento)   [BP + 40] retorno
;     [BP + 32] R1  [BP + 24] R2  [BP + 16] R3  [BP + 8] R4  [BP + 0] BP previo
;     [BP - 8] i    [BP - 16] j   [BP - 24] k
; ------------------------------------------------------------------------------
MERGE:
        PUSH R1
        PUSH R2
        PUSH R3
        PUSH R4
        ENTER 24
        ; Paso 1: aux[lo, hi) = v[lo, hi) con una sola llamada a VEC_COPY
        ;   destino = aux + lo * 8   (VEC_ADDR con R1 = aux)
        ;   origen  = base + lo * 8  (VEC_ADDR con R1 = base)
        ;   n       = hi - lo
        ; TODO(grupo): armar R1, R2, R3 con VEC_ADDR y [BP + 48]
        CALL VEC_COPY
        ; Paso 2: i = lo, j = mid, k = lo  -> STORE en [BP - 8], [BP - 16], [BP - 24]
MERGE_BUCLE:
        ; TODO(grupo): salir a MERGE_RESTO si i >= mid o j >= hi
        ;   a = VEC_GET(aux, i)   ; R1 = [BP + 8], R2 = i      -> R5
        ;   b = VEC_GET(aux, j)   ; R1 = [BP + 8], R2 = j      -> R5
        ;   si a <= b: VEC_SET(base, k, a), i = i + 1
        ;   si no:     VEC_SET(base, k, b), j = j + 1
        ;   k = k + 1
        ; Como R5 se destruye en cada llamada, a se guarda en la pila (PUSH R5)
        ; antes de pedir b. CMP + JN/JZ deciden con signo (enteros con signo).
        CALL VEC_GET
        CALL VEC_SET
MERGE_RESTO:
        ; Paso 3: si quedaron elementos de la mitad izquierda se copian juntos:
        ;   VEC_COPY(base + k * 8, aux + i * 8, mid - i)
        ; Los restos de la mitad derecha ya estan en su lugar en v.
        ; TODO(grupo): armar R1, R2, R3
        CALL VEC_COPY
        LEAVE
        POP  R4
        POP  R3
        POP  R2
        POP  R1
        RET
