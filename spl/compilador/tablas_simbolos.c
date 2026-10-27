/**
 * @file tablas_simbolos.c
 * @brief Implementación de las Tablas de Símbolos y Literales para Enigma-64 SPL.
 * @author Integrante 6 (Tabla de Símbolos & Tablas de Literales)
 */

#include "tablas_simbolos.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <errno.h>

/* Tablas globales y contadores */
EntradaID tablaID[MAX_SIMBOLOS];
int totalID = 0;

EntradaNum tablaNum[MAX_SIMBOLOS];
int totalNum = 0;

EntradaString tablaString[MAX_SIMBOLOS];
int totalString = 0;

#ifndef TABLAS_EXTERNAL_YYTEXT
char *yytext = NULL;
#endif

/* =========================================================================
 * ALGORITMO DE DES-ESCAPE DETERMINISTA (LITERAL D - TAREA 26)
 * ========================================================================= */

void desescapar_cadena(const char *origen, char *destino, size_t dest_size) {
    if (!origen || !destino || dest_size == 0) {
        if (destino && dest_size > 0) destino[0] = '\0';
        return;
    }

    size_t len = strlen(origen);

    /* Verificación de límites: debe contener al menos dos comillas "" */
    if (len < 2 || origen[0] != '"' || origen[len - 1] != '"') {
        destino[0] = '\0';
        return;
    }

    size_t j = 0;
    /* Omitir comilla inicial (i = 1) y terminar estrictamente antes de comilla final (len - 1) */
    for (size_t i = 1; i < len - 1 && j + 1 < dest_size; i++) {
        if (origen[i] == '\\' && (i + 1 < len - 1)) {
            i++; /* Consumir barra invertida y evaluar carácter de escape */
            switch (origen[i]) {
                case '"':  destino[j++] = '"'; break;
                case '\\': destino[j++] = '\\'; break;
                case 'n':  destino[j++] = '\n'; break;
                case 't':  destino[j++] = '\t'; break;
                case 'r':  destino[j++] = '\r'; break;
                case '0':  destino[j++] = '\0'; break;
                default:   destino[j++] = origen[i]; break;
            }
            continue;
        }
        destino[j++] = origen[i];
    }

    destino[j] = '\0';
}

/* =========================================================================
 * IMPLEMENTACIÓN: TABLA DE IDENTIFICADORES (ID = 150)
 * ========================================================================= */

int InstallID_lex(const char *lexema) {
    if (!lexema || lexema[0] == '\0') {
        return -1;
    }

    /* 1. Búsqueda y deduplicación */
    for (int i = 0; i < totalID; i++) {
        if (strcmp(tablaID[i].lexema, lexema) == 0) {
            return tablaID[i].indice; /* Reutilizar índice previo */
        }
    }

    /* 2. Control de capacidad */
    if (totalID >= MAX_SIMBOLOS) {
        fprintf(stderr, "Error SPL: Desbordamiento en Tabla de Identificadores (Capacidad maxima: %d)\n", MAX_SIMBOLOS);
        return -1;
    }

    /* 3. Inserción de nueva entrada */
    tablaID[totalID].indice = totalID + 1; /* Índices correlativos base 1 */
    snprintf(tablaID[totalID].lexema, sizeof(tablaID[totalID].lexema), "%s", lexema);

    return tablaID[totalID++].indice;
}

int InstallID(void) {
    if (!yytext) {
        fprintf(stderr, "Error SPL: yytext es nulo en llamada a InstallID()\n");
        return -1;
    }
    return InstallID_lex(yytext);
}

/* =========================================================================
 * IMPLEMENTACIÓN: TABLA DE CONSTANTES NUMÉRICAS (NUMBER = 160)
 * Soporta enteros de 64 bits y punto flotante IEEE 754 de 64 bits (binary64)
 * ========================================================================= */

static void clasificar_y_convertir_numero(const char *lexema, EntradaNum *entrada) {
    entrada->tipo = NUM_ENTERO_DECIMAL;
    entrada->valor_int = 0;
    entrada->valor_uint = 0;
    entrada->valor_float = 0.0;

    size_t len = strlen(lexema);
    if (len == 0) return;

    /* Hexadecimal: 0x... / 0X... */
    if (len > 2 && lexema[0] == '0' && (lexema[1] == 'x' || lexema[1] == 'X')) {
        entrada->tipo = NUM_ENTERO_HEX;
        errno = 0;
        uint64_t val = (uint64_t)strtoull(lexema, NULL, 16);
        entrada->valor_uint = val;
        entrada->valor_int = (int64_t)val;
        entrada->valor_float = (double)val;
        return;
    }

    /* Binario: 0b... / 0B... */
    if (len > 2 && lexema[0] == '0' && (lexema[1] == 'b' || lexema[1] == 'B')) {
        entrada->tipo = NUM_ENTERO_BIN;
        uint64_t bin_val = 0;
        for (size_t k = 2; k < len; k++) {
            if (lexema[k] == '0' || lexema[k] == '1') {
                bin_val = (bin_val << 1) | (lexema[k] - '0');
            } else {
                break;
            }
        }
        entrada->valor_uint = bin_val;
        entrada->valor_int = (int64_t)bin_val;
        entrada->valor_float = (double)bin_val;
        return;
    }

    /* Detección de coma flotante o notación científica */
    bool tiene_punto = false;
    bool tiene_exp = false;

    for (size_t k = 0; k < len; k++) {
        if (lexema[k] == '.') tiene_punto = true;
        if (lexema[k] == 'e' || lexema[k] == 'E') tiene_exp = true;
    }

    if (tiene_exp) {
        entrada->tipo = NUM_REAL_CIENTIFICO;
        entrada->valor_float = strtod(lexema, NULL);
        entrada->valor_int = (int64_t)entrada->valor_float;
        entrada->valor_uint = (uint64_t)entrada->valor_int;
    } else if (tiene_punto) {
        entrada->tipo = NUM_REAL_DECIMAL;
        entrada->valor_float = strtod(lexema, NULL);
        entrada->valor_int = (int64_t)entrada->valor_float;
        entrada->valor_uint = (uint64_t)entrada->valor_int;
    } else {
        /* Entero decimal estándar */
        entrada->tipo = NUM_ENTERO_DECIMAL;
        errno = 0;
        int64_t v = strtoll(lexema, NULL, 10);
        entrada->valor_int = v;
        entrada->valor_uint = (uint64_t)v;
        entrada->valor_float = (double)v;
    }
}

int InstallNum_lex(const char *lexema) {
    if (!lexema || lexema[0] == '\0') {
        return -1;
    }

    /* 1. Búsqueda y deduplicación */
    for (int i = 0; i < totalNum; i++) {
        if (strcmp(tablaNum[i].lexema, lexema) == 0) {
            return tablaNum[i].indice; /* Reutilizar índice existente */
        }
    }

    /* 2. Control de capacidad */
    if (totalNum >= MAX_SIMBOLOS) {
        fprintf(stderr, "Error SPL: Desbordamiento en Tabla de Numeros (Capacidad maxima: %d)\n", MAX_SIMBOLOS);
        return -1;
    }

    /* 3. Inserción de nueva entrada */
    tablaNum[totalNum].indice = totalNum + 1;
    snprintf(tablaNum[totalNum].lexema, sizeof(tablaNum[totalNum].lexema), "%s", lexema);

    clasificar_y_convertir_numero(lexema, &tablaNum[totalNum]);

    return tablaNum[totalNum++].indice;
}

int InstallNum(void) {
    if (!yytext) {
        fprintf(stderr, "Error SPL: yytext es nulo en llamada a InstallNum()\n");
        return -1;
    }
    return InstallNum_lex(yytext);
}

/* =========================================================================
 * IMPLEMENTACIÓN: TABLA DE CADENAS LITERALES (STRING = 170)
 * ========================================================================= */

int InstallString_lex(const char *lexema) {
    if (!lexema) return -1;

    char texto_limpio[MAX_TEXTO_STRING];
    desescapar_cadena(lexema, texto_limpio, sizeof(texto_limpio));

    /* 1. Búsqueda y deduplicación sobre el texto limpio normalizado */
    for (int i = 0; i < totalString; i++) {
        if (strcmp(tablaString[i].texto, texto_limpio) == 0) {
            return tablaString[i].indice; /* Reutilizar índice */
        }
    }

    /* 2. Control de capacidad */
    if (totalString >= MAX_SIMBOLOS) {
        fprintf(stderr, "Error SPL: Desbordamiento en Tabla de Cadenas (Capacidad maxima: %d)\n", MAX_SIMBOLOS);
        return -1;
    }

    /* 3. Inserción de nueva cadena limpia */
    tablaString[totalString].indice = totalString + 1;
    snprintf(tablaString[totalString].texto, sizeof(tablaString[totalString].texto), "%s", texto_limpio);
    tablaString[totalString].longitud = strlen(tablaString[totalString].texto);

    return tablaString[totalString++].indice;
}

int InstallString(void) {
    if (!yytext) {
        fprintf(stderr, "Error SPL: yytext es nulo en llamada a InstallString()\n");
        return -1;
    }
    return InstallString_lex(yytext);
}

/* =========================================================================
 * CONSULTAS (LOOKUP) SIN INSERCIÓN FORZADA
 * ========================================================================= */

int BuscarID(const char *lexema) {
    if (!lexema) return 0;
    for (int i = 0; i < totalID; i++) {
        if (strcmp(tablaID[i].lexema, lexema) == 0) {
            return tablaID[i].indice;
        }
    }
    return 0; /* 0 indica no encontrado */
}

int BuscarNum(const char *lexema) {
    if (!lexema) return 0;
    for (int i = 0; i < totalNum; i++) {
        if (strcmp(tablaNum[i].lexema, lexema) == 0) {
            return tablaNum[i].indice;
        }
    }
    return 0;
}

int BuscarString(const char *texto_limpio) {
    if (!texto_limpio) return 0;
    for (int i = 0; i < totalString; i++) {
        if (strcmp(tablaString[i].texto, texto_limpio) == 0) {
            return tablaString[i].indice;
        }
    }
    return 0;
}

const EntradaID* ObtenerEntradaID(int indice) {
    if (indice < 1 || indice > totalID) return NULL;
    return &tablaID[indice - 1];
}

const EntradaNum* ObtenerEntradaNum(int indice) {
    if (indice < 1 || indice > totalNum) return NULL;
    return &tablaNum[indice - 1];
}

const EntradaString* ObtenerEntradaString(int indice) {
    if (indice < 1 || indice > totalString) return NULL;
    return &tablaString[indice - 1];
}

/* =========================================================================
 * GESTIÓN, VOLCADO Y VISUALIZACIÓN ESTRUCTURADA
 * ========================================================================= */

void limpiarTablas(void) {
    totalID = 0;
    totalNum = 0;
    totalString = 0;
}

static const char* nombre_tipo_numero(TipoNumero t) {
    switch (t) {
        case NUM_ENTERO_DECIMAL:  return "ENTERO_DEC";
        case NUM_ENTERO_HEX:      return "ENTERO_HEX";
        case NUM_ENTERO_BIN:      return "ENTERO_BIN";
        case NUM_REAL_DECIMAL:    return "REAL_DEC (IEEE-754)";
        case NUM_REAL_CIENTIFICO: return "REAL_EXP (IEEE-754)";
        default:                  return "DESCONOCIDO";
    }
}

void imprimirTablaID(void) {
    printf("\n* Tabla de Identificadores (tablaID, Categoria 150):\n");
    printf("+--------+------------------------------------------------+\n");
    printf("| Indice | Lexema                                         |\n");
    printf("+--------+------------------------------------------------+\n");
    if (totalID == 0) {
        printf("| (vacia)                                                 |\n");
    } else {
        for (int i = 0; i < totalID; i++) {
            printf("| %-6d | %-46s |\n", tablaID[i].indice, tablaID[i].lexema);
        }
    }
    printf("+--------+------------------------------------------------+\n");
    printf("Total de identificadores registrados: %d\n", totalID);
}

void imprimirTablaNum(void) {
    printf("\n* Tabla de Constantes Numericas (tablaNum, Categoria 160):\n");
    printf("+--------+----------------+---------------------+---------------------+----------------------+\n");
    printf("| Indice | Lexema Literal | Formato Enigma-64   | Valor Entero 64-bit | Real IEEE 754 (64b)  |\n");
    printf("+--------+----------------+---------------------+---------------------+----------------------+\n");
    if (totalNum == 0) {
        printf("| (vacia)                                                                                    |\n");
    } else {
        for (int i = 0; i < totalNum; i++) {
            printf("| %-6d | %-14s | %-19s | %-19lld | %-20.10g |\n",
                   tablaNum[i].indice,
                   tablaNum[i].lexema,
                   nombre_tipo_numero(tablaNum[i].tipo),
                   (long long)tablaNum[i].valor_int,
                   tablaNum[i].valor_float);
        }
    }
    printf("+--------+----------------+---------------------+---------------------+----------------------+\n");
    printf("Total de constantes numericas registradas: %d\n", totalNum);
}

void imprimirTablaString(void) {
    printf("\n* Tabla de Cadenas de Texto (tablaString, Categoria 170):\n");
    printf("+--------+------------------------------------------------+----------+\n");
    printf("| Indice | Texto limpio (des-escapado)                    | Longitud |\n");
    printf("+--------+------------------------------------------------+----------+\n");
    if (totalString == 0) {
        printf("| (vacia)                                                            |\n");
    } else {
        for (int i = 0; i < totalString; i++) {
            printf("| %-6d | %-46s | %-8zu |\n",
                   tablaString[i].indice,
                   tablaString[i].texto,
                   tablaString[i].longitud);
        }
    }
    printf("+--------+------------------------------------------------+----------+\n");
    printf("Total de cadenas de texto registradas: %d\n", totalString);
}

void imprimirVolcadoTablas(void) {
    printf("\n========================================================================================\n");
    printf("                 ESTADO FINAL DE LAS TABLAS DE SIMBOLOS (ENIGMA-64)                     \n");
    printf("========================================================================================\n");
    imprimirTablaID();
    imprimirTablaNum();
    imprimirTablaString();
    printf("========================================================================================\n\n");
}
