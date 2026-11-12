#pragma once
#ifndef ESTRUCTURAS_INC
#define ESTRUCTURAS_INC

; ==============================================================================
; estructuras.inc - Archivo maestro de la libreria de estructuras de datos.
; Tarea 29 - Enigma-64 (Noctua Systems)
; Responsable del empaquetado maestro: Integrante 4 (Cargador, Cabeceras, Enlace)
;
; Punto unico de inclusion gestionado por el Preprocesador del SPL (ply.lex):
;   #include "estructuras.inc"
;
; Empaqueta en orden determinista:
;   1. layout_datos.inc : Mapa de memoria (>= 0x00210000) y macros VEC_DIR/MAT_DIR
;   2. vec.asm          : Primitivas 1D de listas/vectores (VEC_ADDR, VEC_GET,
;                         VEC_SET, VEC_SWAP, VEC_COPY, VEC_LEN)
;   3. cabeceras.asm    : Constructores y descriptores de cabeceras de listas y
;                         matrices (VEC_INIT, MAT_INIT, MAT_ROWS, MAT_COLS,
;                         DESC_ADDR, DESC_VEC_INIT, DESC_MAT_INIT, DESC_GET_*)
;   4. mat.asm          : Primitivas 2D de matrices (activable con INCLUIR_MATRICES
;                         o directamente cuando el modulo 2D este presente)
;
; Contrato de registros (ABI unificada):
;   - Argumentos: R1, R2, R3, R4 (del 5o en adelante por pila).
;   - Retorno:    R5 (RV).
;   - Preservados (callee-saved): R1..R4, SP (R6) y BP (R7).
;   - Destruidos  (caller-saved): R5 y banderas Z, N, C, V.
; ==============================================================================

// Constantes arquitectonicas de ejecucion y descriptores (palabras de 64 bits)
#define BASE_CODIGO_USUARIO 0x00200000
#define PILA_ESTRUCTURAS    0x00400000
#define MMIO_PANTALLA_DATA  0xFF001010

// Codigos de tipo en descriptores de BASE_CABECERAS (0x00210000)
#define TIPO_VECTOR         1
#define TIPO_MATRIZ         2

// Geometria de cada descriptor en BASE_CABECERAS (4 palabras x 8B = 32 bytes)
#define DESC_TAM_BYTES      32
#define DESC_SHIFT_BYTES    5
#define DESC_OFF_TIPO       0
#define DESC_OFF_BASE       8
#define DESC_OFF_FILAS      16
#define DESC_OFF_COLS       24

// Desplazamientos de cabecera inline respecto a la base de datos [base - off]
#define CAB_INLINE_FILAS    16
#define CAB_INLINE_FLAG     16
#define CAB_INLINE_LEN      8
#define CAB_INLINE_COLS     8

// 1. Mapa de memoria (>= 0x00210000) y macros VEC_DIR / MAT_DIR
#include "layout_datos.inc"

// Macro parametrizada para calcular la direccion del descriptor en el slot k:
#define DESC_DIR(slot) BASE_CABECERAS + ((slot) << 5)

// 2. Primitivas 1D y constructores/descriptores de cabeceras
#include "vec.asm"
#include "cabeceras.asm"

#ifdef INCLUIR_MATRICES
#include "mat.asm"
#endif

#endif
