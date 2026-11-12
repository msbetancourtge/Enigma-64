#pragma once
#ifndef LAYOUT_DATOS_INC
#define LAYOUT_DATOS_INC

// Especificacion:
//   - Region de datos de usuario: >= 0x00201000
//   - Alineacion natural: multiplos de 8 bytes (palabra de 64 bits, STATUS_READY)
//   - No pisa los programas demo de programas/:
//       * Factorial: 0x00201000 - 0x0020100F
//       * Euclides:  0x00202000 - 0x00202017
//       * Fibonacci: 0x00203000 - 0x00203038
//       * Brun:      SP en 0x00204000 (pila descendente), variables en 0x00205000 - 0x00205020
//     La region de estructuras inicia en 0x00210000, garantizando aislamiento total.

// Constantes generales de alineacion
#define ALINEACION_DATOS 8
#define PALABRA_BYTES 8

// ------------------------------------------------------------------------------
// Zona 1: Cabeceras de Estructuras (Metadatos: tipo, dimension, longitud, capacidad)
// Base: 0x00210000, Tamano: 64 KiB (0x00010000), Limite: 0x00220000
// ------------------------------------------------------------------------------
#define BASE_CABECERAS 0x00210000
#define DIR_CABECERAS 0x00210000
#define CABECERAS_BASE 0x00210000
#define TAM_CABECERAS 0x00010000
#define LIMITE_CABECERAS 0x00220000

// ------------------------------------------------------------------------------
// Zona 2: Vectores (Almacenamiento contiguo de elementos de 64 bits)
// Base: 0x00220000, Tamano: 256 KiB (0x00040000), Limite: 0x00260000
// ------------------------------------------------------------------------------
#define BASE_VECTORES 0x00220000
#define DIR_VECTORES 0x00220000
#define VECTORES_BASE 0x00220000
#define TAM_VECTORES 0x00040000
#define LIMITE_VECTORES 0x00260000

// ------------------------------------------------------------------------------
// Zona 3: Matrices (Arreglos bidimensionales contiguos en orden Row-Major)
// Base: 0x00260000, Tamano: 512 KiB (0x00080000), Limite: 0x002E0000
// ------------------------------------------------------------------------------
#define BASE_MATRICES 0x00260000
#define DIR_MATRICES 0x00260000
#define MATRICES_BASE 0x00260000
#define TAM_MATRICES 0x00080000
#define LIMITE_MATRICES 0x002E0000

// ------------------------------------------------------------------------------
// Zona 4: Buffers Auxiliares (Memoria de intercambio, ordenamiento y multiplicacion)
// Base: 0x002E0000, Tamano: 128 KiB (0x00020000), Limite: 0x00300000
// ------------------------------------------------------------------------------
#define BASE_BUFFERS 0x002E0000
#define DIR_BUFFERS 0x002E0000
#define BUFFERS_BASE 0x002E0000
#define TAM_BUFFERS 0x00020000
#define LIMITE_BUFFERS 0x00300000

// ------------------------------------------------------------------------------
// Desplazamientos estandar para varias estructuras dentro de una misma zona.
// Un programa que usa dos vectores o tres matrices las coloca en
// BASE + 0, BASE + DESP_x_2, BASE + DESP_x_3. Cada hueco deja sitio a los datos
// de la estructura anterior mas la cabecera inline de 16 bytes de la siguiente:
//   vectores: 0x1000 = 512 palabras  -> hasta 510 elementos por vector
//   matrices: 0x3000 = 1536 palabras -> holgado para 32 x 32 (1024 palabras)
// Caben en el inmediato de 16 bits con signo de ADDI (<= 0x7FFF).
// ------------------------------------------------------------------------------
#define DESP_VECTOR_2 0x1000
#define DESP_MATRIZ_2 0x3000
#define DESP_MATRIZ_3 0x6000

// ==============================================================================
// Macros Parametrizadas de Acceso y Direccionamiento
// ==============================================================================

// Direccion efectiva del elemento i en un vector de palabras de 64 bits:
// VEC_DIR(base, i) = base + (i << 3)
#define VEC_DIR(base, i) base + (i << 3)

// Direccion efectiva del elemento (i, j) en una matriz de palabras de 64 bits (cols columnas):
// MAT_DIR(base, cols, i, j) = base + ((i * cols + j) << 3)
#define MAT_DIR(base, cols, i, j) base + ((i * cols + j) << 3)

#endif
