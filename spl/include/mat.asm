#pragma once
#ifndef MAT_ASM
#define MAT_ASM
; ==============================================================================
; mat.asm - Libreria de matrices de Enigma-64. Primitivas 2D.
; Tarea 29 - Integrante 3: Control, Pila y Primitivas 2D.
;
; Uso:      #include "mat.asm"     (o #include <mat.asm>; vive en spl/include/)
;           o bien #define INCLUIR_MATRICES antes de #include "estructuras.inc".
;           Doble inclusion protegida con #pragma once y una guarda #ifndef.
;           (El preprocesador expande macros tambien dentro de comentarios ';',
;           por eso aqui no se escriben el nombre de la guarda ni las macros
;           parametrizadas del mapa de memoria.)
;           Incluye cabeceras.asm (MAT_INIT, MAT_ROWS, MAT_COLS), que crea y
;           lee la cabecera de la matriz. Se puede incluir al inicio o al final
;           del programa: los JMP iniciales saltan el cuerpo de las librerias.
;
; Distribucion en memoria de una matriz de F filas y C columnas (Row-Major):
;
;     base - 16 : F (filas)     cabecera escrita por MAT_INIT o DESC_MAT_INIT
;     base -  8 : C (columnas)  la leen MAT_ADDR, MAT_GET, MAT_SET y MAT_CLEAR
;     base + 0  : M[0][0]
;     base + 8  : M[0][1]
;     ...
;     base + ((i * C + j) << 3) : M[i][j]
;
;   base apunta SIEMPRE a M[0][0] y debe ser multiplo de 8 (si no, la maquina
;   lanza STATUS_MISALIGNED). La fila i es un vector contiguo de C elementos
;   que empieza en base + ((i * C) << 3): las primitivas VEC_* de vec.asm
;   sirven sobre una fila sin convertir nada. Las primitivas mueven los 64
;   bits crudos: sirven igual para enteros y para double IEEE-754.
;   La cabecera es OBLIGATORIA: sin C no hay direccion. Las primitivas NO
;   comprueban limites: 0 <= i < F y 0 <= j < C es responsabilidad del
;   llamador (igual que en vec.asm).
;
; Convencion de llamada (la misma de vec.asm y cabeceras.asm):
;   - Argumentos en R1, R2, R3, R4 (en ese orden). Retorno en R5 (alias RV).
;   - R1..R4 se PRESERVAN. R5 y las banderas Z N C V se DESTRUYEN.
;   - R0 vale 0 siempre. R6 = SP y R7 = BP se preservan.
;
; Gestion de pila para llamadas anidadas (R6 = SP, R7 = BP):
;   - La pila crece hacia direcciones menores. PUSH hace SP = SP - 8 y escribe
;     en [SP]; POP lee [SP] y hace SP = SP + 8. CALL apila la direccion de
;     retorno y RET la desapila: cada nivel de anidamiento ocupa su propia
;     palabra y los retornos se recuperan en orden inverso (LIFO).
;   - Rutina hoja (MAT_ADDR): no llama a nadie, no toca la pila ni BP.
;   - Rutina no hoja (MAT_GET, MAT_SET, MAT_CLEAR): guarda con PUSH los
;     registros R1..R4 que use como temporales, abre un marco con ENTER t
;     (apila BP, BP = SP, SP = SP - t) y sale por un unico camino:
;     LEAVE (SP = BP, desapila BP), POP en orden inverso y RET.
;   - Marco de una rutina no hoja tras PUSH de k registros y ENTER t:
;       [BP + 8*(k+1)] retorno al llamador
;       [BP + 8*k .. BP + 8] registros guardados (el ultimo PUSH en BP + 8)
;       [BP + 0]  BP del llamador (enlace dinamico: la cadena de marcos)
;       [BP - 8 .. BP - t] variables locales (t = 0 en esta libreria)
;   - Por eso, durante MAT_GET -> MAT_ADDR la pila contiene, de arriba abajo:
;       [SP] retorno a MAT_GET   [BP] BP del llamador   [BP + 8] retorno al
;       llamador; y siguiendo [BP] se recorre la cadena de marcos completa.
;   - El programa debe poner SP en un multiplo de 8 antes de la primera
;     llamada (SP_RESET = 0xEFFFFFFF esta desalineado).
;   - Un preprocesador de una linea por macro no puede emitir varias
;     instrucciones (la continuacion de linea las une en una sola), asi que la
;     gestion de pila vive en las subrutinas, no en macros #define.
; ==============================================================================
#include "cabeceras.asm"

        JMP MAT_FIN_LIBRERIA        ; salta el cuerpo si el flujo cae aqui

; ------------------------------------------------------------------------------
; MAT_ADDR: R5 = base + ((i * C + j) << 3)
;           Entradas: R1 = base, R2 = i, R3 = j     (C se lee de [base - 8])
; Direccion de M[i][j] en orden Row-Major. Hoja: solo usa R5 (MUL, ADD, SHL).
; ------------------------------------------------------------------------------
MAT_ADDR:
        LOAD R5, [R1 - 8]           ; R5 = C (mismo campo que lee MAT_COLS)
        MUL  R5, R2, R5             ; R5 = i * C
        ADD  R5, R5, R3             ; R5 = i * C + j (indice lineal)
        SHL  R5, R5, 3              ; R5 = (i * C + j) * 8 (bytes)
        ADD  R5, R1, R5             ; R5 = base + ((i * C + j) << 3)
        RET                         ; vuelve con la direccion en R5

; ------------------------------------------------------------------------------
; MAT_GET: R5 = M[i][j]                 Entradas: R1 = base, R2 = i, R3 = j
; No hoja: llamada anidada a MAT_ADDR dentro de un marco ENTER 0 / LEAVE.
; MAT_ADDR solo modifica R5, por eso no hace falta apilar R1..R4.
; ------------------------------------------------------------------------------
MAT_GET:
        ENTER 0                     ; apila BP, BP = SP: enlaza el marco
        CALL MAT_ADDR               ; nivel 2: R5 = &M[i][j]
        LOAD R5, [R5]               ; R5 = M[i][j] (64 bits crudos)
        LEAVE                       ; SP = BP y recupera el BP del llamador
        RET                         ; desapila el retorno del nivel 1

; ------------------------------------------------------------------------------
; MAT_SET: M[i][j] = valor      Entradas: R1 = base, R2 = i, R3 = j, R4 = valor
; No hoja: llamada anidada a MAT_ADDR dentro de un marco ENTER 0 / LEAVE.
; ------------------------------------------------------------------------------
MAT_SET:
        ENTER 0                     ; apila BP, BP = SP: enlaza el marco
        CALL MAT_ADDR               ; nivel 2: R5 = &M[i][j]
        STORE R4, [R5]              ; M[i][j] = R4 (64 bits crudos)
        LEAVE                       ; SP = BP y recupera el BP del llamador
        RET

; ------------------------------------------------------------------------------
; MAT_CLEAR: M[i][j] = 0 para toda la matriz        Entradas: R1 = base
;            Salida: R5 = F * C (palabras puestas a cero; 0 si F * C <= 0)
; No hoja: lee F y C con llamadas anidadas a MAT_ROWS y MAT_COLS. En orden
; Row-Major la matriz es un bloque contiguo de F * C palabras, asi que se
; recorre con un solo puntero. Los bits 0 son tambien el double +0.0.
; Marco tras PUSH R1, PUSH R2 y ENTER 0:
;   [BP + 24] retorno   [BP + 16] R1   [BP + 8] R2   [BP + 0] BP del llamador
; ------------------------------------------------------------------------------
MAT_CLEAR:
        PUSH R1                     ; preserva base (sera el puntero)
        PUSH R2                     ; preserva R2 (sera el contador)
        ENTER 0                     ; apila BP, BP = SP: enlaza el marco
        CALL MAT_ROWS               ; nivel 2: R5 = F
        ADD  R2, R5, R0             ; R2 = F
        CALL MAT_COLS               ; nivel 2: R5 = C
        MUL  R2, R2, R5             ; R2 = n = F * C
        ADD  R5, R0, R0             ; R5 = 0 por si no hay nada que borrar
        CMP  R2, R0                 ; banderas de n - 0
        JZ   MAT_CLEAR_FIN          ; n = 0: matriz vacia
        JN   MAT_CLEAR_FIN          ; n < 0: cabecera invalida, no escribe
        ADD  R5, R2, R0             ; R5 = n (valor de retorno)
MAT_CLEAR_BUCLE:
        STORE R0, [R1]              ; palabra actual = 0 (R0 vale 0 siempre)
        ADDI R1, R1, 8              ; siguiente palabra de la matriz
        DEC  R2                     ; quedan n - 1
        JNZ  MAT_CLEAR_BUCLE        ; repite mientras queden palabras
MAT_CLEAR_FIN:
        LEAVE                       ; SP = BP y recupera el BP del llamador
        POP  R2                     ; restaura en orden inverso al PUSH
        POP  R1
        RET

MAT_FIN_LIBRERIA:
#endif
