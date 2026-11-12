#pragma once
#ifndef VEC_ASM
#define VEC_ASM
; ==============================================================================
; vec.asm - Libreria de vectores (listas) de Enigma-64. Primitivas 1D.
; Integrante 2: Registros, ALU y Primitivas 1D.
;
; Uso:      #include "vec.asm"     (o #include <vec.asm>; vive en spl/include/)
;           Doble inclusion protegida con #pragma once y una guarda #ifndef.
;           (El preprocesador expande macros tambien dentro de comentarios ';',
;           por eso aqui no se escribe el nombre de la guarda.)
;           Se puede incluir al inicio o al final del programa: el primer
;           JMP salta el cuerpo de la libreria, asi nunca se ejecuta por caida.
;
; Distribucion en memoria de un vector de n elementos:
;
;     base - 8 : n (cabecera OPCIONAL, la lee VEC_LEN; las demas la ignoran)
;     base + 0 : v[0]
;     base + 8 : v[1]
;     ...
;     base + 8*(n-1) : v[n-1]
;
;   base apunta SIEMPRE al primer elemento y debe ser multiplo de 8 (si no, la
;   maquina lanza STATUS_MISALIGNED). Cada elemento ocupa 8 bytes, por eso
;   la direccion de v[i] es base + (i << 3). Las primitivas mueven los 64 bits
;   crudos: sirven igual para enteros y para double IEEE-754.
;   Las primitivas NO comprueban limites: 0 <= i < n es responsabilidad del
;   llamador (el bucle interno de merge sort no paga ese costo).
;
; Convencion de llamada (la usa toda la libreria, incluida la de matrices):
;   - Argumentos en R1, R2, R3, R4 (en ese orden). Retorno en R5 (alias RV).
;   - R1..R4 se PRESERVAN: al volver tienen el mismo valor que al entrar.
;     La subrutina que necesite temporales los guarda con PUSH y los recupera
;     con POP en orden inverso antes de RET.
;   - R5 y las banderas Z N C V se DESTRUYEN (caller-saved). Si el llamador
;     necesita R5 despues de la llamada, debe guardarlo el.
;   - R0 vale 0 siempre. R6 = SP y R7 = BP se preservan. La pila crece hacia
;     direcciones menores: PUSH hace SP = SP - 8 y escribe en [SP].
;   - CALL apila la direccion de retorno y RET la desapila; por eso toda
;     subrutina debe dejar SP igual que al entrar antes de RET.
;   - Las primitivas son hojas (no llaman a otras) y no usan BP: no crean
;     marco con ENTER/LEAVE porque no tienen variables locales.
; ==============================================================================

        JMP VEC_FIN_LIBRERIA        ; salta el cuerpo si el flujo cae aqui

; ------------------------------------------------------------------------------
; VEC_ADDR: R5 = base + (i << 3)       Entradas: R1 = base, R2 = i
; Direccion de v[i]. Contrato estable: la libreria de matrices la usa.
; ------------------------------------------------------------------------------
VEC_ADDR:
        SHL  R5, R2, 3              ; R5 = i * 8 (desplazamiento en bytes)
        ADD  R5, R1, R5             ; R5 = base + i * 8
        RET                         ; vuelve con la direccion en R5

; ------------------------------------------------------------------------------
; VEC_GET: R5 = v[i]                    Entradas: R1 = base, R2 = i
; Calculo de direccion en linea (no llama a VEC_ADDR): ahorra CALL y RET.
; ------------------------------------------------------------------------------
VEC_GET:
        SHL  R5, R2, 3              ; R5 = i * 8
        ADD  R5, R1, R5             ; R5 = &v[i]
        LOAD R5, [R5]               ; R5 = v[i] (64 bits crudos)
        RET

; ------------------------------------------------------------------------------
; VEC_SET: v[i] = valor                 Entradas: R1 = base, R2 = i, R3 = valor
; R5 sirve de temporal porque es caller-saved: no hace falta pila.
; ------------------------------------------------------------------------------
VEC_SET:
        SHL  R5, R2, 3              ; R5 = i * 8
        ADD  R5, R1, R5             ; R5 = &v[i]
        STORE R3, [R5]              ; v[i] = R3 (64 bits crudos)
        RET

; ------------------------------------------------------------------------------
; VEC_SWAP: intercambia v[i] y v[j]     Entradas: R1 = base, R2 = i, R3 = j
; Necesita cuatro valores vivos (dos direcciones y dos datos) y solo R5 es
; libre: guarda R2, R3 y R4 en la pila y los usa como temporales.
; Correcto tambien con i = j (lee los dos antes de escribir).
; ------------------------------------------------------------------------------
VEC_SWAP:
        PUSH R2                     ; preserva i
        PUSH R3                     ; preserva j
        PUSH R4                     ; preserva R4 (sera temporal)
        SHL  R2, R2, 3              ; R2 = i * 8
        ADD  R2, R1, R2             ; R2 = &v[i]
        SHL  R3, R3, 3              ; R3 = j * 8
        ADD  R3, R1, R3             ; R3 = &v[j]
        LOAD R4, [R2]               ; R4 = v[i]
        LOAD R5, [R3]               ; R5 = v[j]
        STORE R5, [R2]              ; v[i] = antiguo v[j]
        STORE R4, [R3]              ; v[j] = antiguo v[i]
        POP  R4                     ; restaura en orden inverso al PUSH
        POP  R3
        POP  R2
        RET

; ------------------------------------------------------------------------------
; VEC_COPY: copia n elementos de origen a destino (semantica memmove)
;           Entradas: R1 = destino, R2 = origen, R3 = n
; Soporta zonas solapadas eligiendo el sentido de la copia:
;   destino < origen -> hacia adelante (v[0] primero)
;   destino > origen -> hacia atras    (v[n-1] primero)
;   destino = origen o n <= 0 -> no hace nada
; La comparacion de direcciones es sin signo: usa C (prestamo de la resta).
; ------------------------------------------------------------------------------
VEC_COPY:
        PUSH R1                     ; preserva destino (se usa como puntero)
        PUSH R2                     ; preserva origen (se usa como puntero)
        PUSH R3                     ; preserva n (se usa como contador)
        CMP  R3, R0                 ; banderas de n - 0
        JZ   VEC_COPY_FIN           ; n = 0: nada que copiar
        JN   VEC_COPY_FIN           ; n < 0: nada que copiar
        CMP  R1, R2                 ; banderas de destino - origen
        JZ   VEC_COPY_FIN           ; misma zona: la copia no cambia nada
        JC   VEC_COPY_ADELANTE      ; C = 1 (prestamo): destino < origen
        SHL  R5, R3, 3              ; R5 = n * 8 (destino > origen: hacia atras)
        ADD  R1, R1, R5             ; R1 = destino + 8n (uno despues del final)
        ADD  R2, R2, R5             ; R2 = origen + 8n
VEC_COPY_ATRAS:
        SUBI R1, R1, 8              ; R1 = &destino[k]
        SUBI R2, R2, 8              ; R2 = &origen[k]
        LOAD R5, [R2]               ; R5 = origen[k]
        STORE R5, [R1]              ; destino[k] = origen[k]
        DEC  R3                     ; quedan n - 1
        JNZ  VEC_COPY_ATRAS         ; repite mientras queden elementos
        JMP  VEC_COPY_FIN
VEC_COPY_ADELANTE:
        LOAD R5, [R2]               ; R5 = origen[k]
        STORE R5, [R1]              ; destino[k] = origen[k]
        ADDI R1, R1, 8              ; avanza destino
        ADDI R2, R2, 8              ; avanza origen
        DEC  R3                     ; quedan n - 1
        JNZ  VEC_COPY_ADELANTE      ; repite mientras queden elementos
VEC_COPY_FIN:
        POP  R3                     ; restaura n
        POP  R2                     ; restaura origen
        POP  R1                     ; restaura destino
        RET

; ------------------------------------------------------------------------------
; VEC_LEN: R5 = n                       Entradas: R1 = base
; Solo para vectores creados con cabecera (n guardado en base - 8).
; ------------------------------------------------------------------------------
VEC_LEN:
        LOAD R5, [R1 - 8]           ; R5 = cabecera (longitud)
        RET

VEC_FIN_LIBRERIA:
#endif
