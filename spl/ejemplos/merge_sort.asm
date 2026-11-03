; ==============================================================================
; merge_sort.asm - Algoritmo de Ordenamiento por Mezclas (Merge Sort) & MMIO
; Tarea 29: Integrante 6 (Algoritmo 1 & MMIO)
;
; Utiliza la libreria de estructuras de datos (estructuras.inc):
;   - layout_datos.inc (constantes de memoria: BASE_VECTORES, BASE_BUFFERS)
;   - vec.asm (primitivas de listas: VEC_ADDR, VEC_GET, VEC_SET, VEC_COPY, VEC_LEN)
;
; Distribucion de memoria:
;   - BASE_VECTORES (0x00220000): Vector de entrada / ordenado
;   - BASE_BUFFERS  (0x002E0000): Vector auxiliar para MERGE
;   - Pila          (0x00400000): Alineada a 8 bytes, crecimiento descendente
;   - MMIO DATA     (0xFF001010): Registro de emision de datos de pantalla CRT
; ==============================================================================
#include "estructuras.inc"

PRINCIPAL:
        ADDI SP, R0, 0x0040
        SHL  SP, SP, 16             ; SP = 0x00400000 (alineada a 8 bytes)
        ADDI R1, R0, 0x0022
        SHL  R1, R1, 16             ; R1 = base del vector (BASE_VECTORES)
        ADDI R2, R0, 0              ; R2 = lo = 0
        CALL VEC_LEN                ; R5 = n (cabecera en base - 8)
        ADD  R3, R5, R0             ; R3 = hi = n
        ADDI R4, R0, 0x002E
        SHL  R4, R4, 16             ; R4 = aux (BASE_BUFFERS)
        CALL MERGE_SORT
        CALL EMITIR_VECTOR_MMIO
        HLT

; ------------------------------------------------------------------------------
; MERGE_SORT: ordena v[lo, hi) recursivamente
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
;   (Implementacion completa en Fase 2)
; ------------------------------------------------------------------------------
MERGE:
        RET

; ------------------------------------------------------------------------------
; EMITIR_VECTOR_MMIO: salida del vector ordenado por pantalla MMIO (0xFF001010)
;   R1 = base, R2 = lo, R3 = hi
;   (Implementacion completa en Fase 3)
; ------------------------------------------------------------------------------
EMITIR_VECTOR_MMIO:
        RET
