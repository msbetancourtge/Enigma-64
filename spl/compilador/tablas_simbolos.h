/**
 * @file tablas_simbolos.h
 * @brief Estructuras de datos y tablas de literales para el Compilador SPL (Enigma-64).
 * @author Integrante 6 (Tabla de Símbolos & Tablas de Literales)
 * 
 * Implementa las tablas de símbolos para Identificadores (ID), Constantes
 * Numéricas (NUMBER - enteros y punto flotante IEEE 754 binary64 de 64 bits)
 * y Cadenas Literales (STRING) con des-escape y deduplicación estricta.
 */

#ifndef TABLAS_SIMBOLOS_H
#define TABLAS_SIMBOLOS_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Capacidad máxima de registros por tabla */
#define MAX_SIMBOLOS 1024
#define MAX_LEXEMA_ID 128
#define MAX_LEXEMA_NUM 64
#define MAX_TEXTO_STRING 512

/**
 * @brief Tipos numéricos soportados por el computador Enigma-64.
 */
typedef enum {
    NUM_ENTERO_DECIMAL = 1,
    NUM_ENTERO_HEX     = 2,
    NUM_ENTERO_BIN     = 3,
    NUM_REAL_DECIMAL   = 4,
    NUM_REAL_CIENTIFICO= 5
} TipoNumero;

/**
 * @brief Entrada en la Tabla de Identificadores (tablaID).
 */
typedef struct {
    int indice;                     /**< Posición correlativa 1-based (valor para yylval) */
    char lexema[MAX_LEXEMA_ID];     /**< Nombre del identificador */
} EntradaID;

/**
 * @brief Entrada en la Tabla de Constantes Numéricas (tablaNum).
 * Almacena enteros de 64 bits y flotantes IEEE 754 de 64 bits.
 */
typedef struct {
    int indice;                     /**< Posición correlativa 1-based (valor para yylval) */
    char lexema[MAX_LEXEMA_NUM];    /**< Representación textual original (ej. "1.5E3", "0xFF000000") */
    TipoNumero tipo;                /**< Clasificación formal del literal numérico */
    int64_t valor_int;              /**< Valor entero con signo (64 bits complemento a dos) */
    uint64_t valor_uint;            /**< Valor entero sin signo (64 bits para máscaras/MMIO) */
    double valor_float;             /**< Valor en punto flotante IEEE 754 binary64 de 64 bits */
} EntradaNum;

/**
 * @brief Entrada en la Tabla de Cadenas Literales (tablaString).
 */
typedef struct {
    int indice;                     /**< Posición correlativa 1-based (valor para yylval) */
    char texto[MAX_TEXTO_STRING];   /**< Texto limpio (des-comillado y con secuencias de escape resueltas) */
    size_t longitud;                /**< Longitud en bytes de la cadena limpia */
} EntradaString;

/* Tablas globales y contadores de elementos registrados */
extern EntradaID tablaID[MAX_SIMBOLOS];
extern int totalID;

extern EntradaNum tablaNum[MAX_SIMBOLOS];
extern int totalNum;

extern EntradaString tablaString[MAX_SIMBOLOS];
extern int totalString;

/* Variable externa provista por FLEX */
#ifndef YYTEXT_DEFINED
extern char *yytext;
#endif

/* =========================================================================
 * FUNCIONES CANÓNICAS DE INSERCIÓN Y DEDUPLICACIÓN (REQUISITO INTEGRANTE 6)
 * ========================================================================= */

/**
 * @brief Búsqueda e inserción de identificadores sin duplicados a partir de yytext.
 * @return Índice 1-based asignado a yylval.
 */
int InstallID(void);

/**
 * @brief Búsqueda e inserción de constantes numéricas (enteros y flotantes IEEE 754 de 64 bits) desde yytext.
 * @return Índice 1-based asignado a yylval.
 */
int InstallNum(void);

/**
 * @brief Procesamiento, des-escape y deduplicación de cadenas literales a partir de yytext.
 * @return Índice 1-based asignado a yylval.
 */
int InstallString(void);

/* Versiones explícitas para llamadas con buffer específico o desde código C/C++ */
int InstallID_lex(const char *lexema);
int InstallNum_lex(const char *lexema);
int InstallString_lex(const char *lexema);

/* =========================================================================
 * ALGORITMO DE DES-ESCAPE DETERMINISTA (LITERAL D - TAREA 26)
 * ========================================================================= */

/**
 * @brief Elimina comillas externas y resuelve secuencias de escape en cadenas (\", \\, \n, \t, etc.).
 * @param origen Cadena bruta con comillas y barras invertidas (yytext).
 * @param destino Búfer donde se almacenará la cadena limpia.
 * @param dest_size Tamaño máximo del búfer destino.
 */
void desescapar_cadena(const char *origen, char *destino, size_t dest_size);

/* =========================================================================
 * FUNCIONES DE CONSULTA (LOOKUP) SIN INSERCIÓN FORZADA
 * ========================================================================= */

int BuscarID(const char *lexema);
int BuscarNum(const char *lexema);
int BuscarString(const char *texto_limpio);

const EntradaID* ObtenerEntradaID(int indice);
const EntradaNum* ObtenerEntradaNum(int indice);
const EntradaString* ObtenerEntradaString(int indice);

/* =========================================================================
 * GESTIÓN, VOLCADO Y VISUALIZACIÓN ESTRUCTURADA
 * ========================================================================= */

void limpiarTablas(void);
void imprimirTablaID(void);
void imprimirTablaNum(void);
void imprimirTablaString(void);
void imprimirVolcadoTablas(void);

#ifdef __cplusplus
}
#endif

#endif /* TABLAS_SIMBOLOS_H */
