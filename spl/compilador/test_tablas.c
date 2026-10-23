/**
 * @file test_tablas.c
 * @brief Suite de pruebas unitarias en C para las Tablas de Símbolos y Literales de Enigma-64.
 * @author Integrante 6 (Tabla de Símbolos & Tablas de Literales)
 */

#include "tablas_simbolos.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <math.h>

static int pruebas_ejecutadas = 0;
static int aserciones_exitosas = 0;

#define TEST_ASSERT(cond, msg) do { \
    aserciones_exitosas++; \
    if (!(cond)) { \
        fprintf(stderr, "FALLO en %s:%d: %s\n", __FILE__, __LINE__, msg); \
        exit(1); \
    } \
} while (0)

void test_tabla_identificadores(void) {
    printf("[TEST 1] Probando Tabla de Identificadores (tablaID)...\n");
    limpiarTablas();

    int id1 = InstallID_lex("contador");
    int id2 = InstallID_lex("_temp");
    int id3 = InstallID_lex("val_max");

    TEST_ASSERT(id1 == 1, "id1 debe tener indice 1");
    TEST_ASSERT(id2 == 2, "id2 debe tener indice 2");
    TEST_ASSERT(id3 == 3, "id3 debe tener indice 3");
    TEST_ASSERT(totalID == 3, "totalID debe ser 3");

    /* Deduplicación estricta */
    int id1_dup = InstallID_lex("contador");
    int id2_dup = InstallID_lex("_temp");
    TEST_ASSERT(id1_dup == 1, "Deduplicacion contador fallida (debe reutilizar indice 1)");
    TEST_ASSERT(id2_dup == 2, "Deduplicacion _temp fallida (debe reutilizar indice 2)");
    TEST_ASSERT(totalID == 3, "totalID no debe aumentar en duplicados");

    /* Consultas (lookup) */
    TEST_ASSERT(BuscarID("contador") == 1, "BuscarID contador debe ser 1");
    TEST_ASSERT(BuscarID("no_existe") == 0, "BuscarID inexistente debe ser 0");

    const EntradaID* e = ObtenerEntradaID(2);
    TEST_ASSERT(e != NULL && strcmp(e->lexema, "_temp") == 0, "ObtenerEntradaID(2) debe retornar _temp");

    pruebas_ejecutadas++;
    printf("  -> OK (Deduplicacion e indexacion base 1 verificadas)\n");
}

void test_tabla_constantes_numericas(void) {
    printf("[TEST 2] Probando Tabla de Constantes Numericas (tablaNum - IEEE 754 y 64-bit)...\n");
    limpiarTablas();

    /* Entero decimal */
    int n1 = InstallNum_lex("42");
    TEST_ASSERT(n1 == 1, "n1 debe ser indice 1");
    const EntradaNum *e1 = ObtenerEntradaNum(1);
    TEST_ASSERT(e1->tipo == NUM_ENTERO_DECIMAL, "e1 debe ser NUM_ENTERO_DECIMAL");
    TEST_ASSERT(e1->valor_int == 42, "e1 valor_int debe ser 42");

    /* Hexadecimal de 64 bits (dirección MMIO Enigma-64) */
    int n2 = InstallNum_lex("0xFF000000");
    TEST_ASSERT(n2 == 2, "n2 debe ser indice 2");
    const EntradaNum *e2 = ObtenerEntradaNum(2);
    TEST_ASSERT(e2->tipo == NUM_ENTERO_HEX, "e2 debe ser NUM_ENTERO_HEX");
    TEST_ASSERT(e2->valor_uint == 0xFF000000ULL, "e2 valor_uint debe coincidir");

    /* Binario */
    int n3 = InstallNum_lex("0b1010");
    TEST_ASSERT(n3 == 3, "n3 debe ser indice 3");
    const EntradaNum *e3 = ObtenerEntradaNum(3);
    TEST_ASSERT(e3->tipo == NUM_ENTERO_BIN, "e3 debe ser NUM_ENTERO_BIN");
    TEST_ASSERT(e3->valor_int == 10, "e3 valor_int debe ser 10");

    /* Real estándar */
    int n4 = InstallNum_lex("25.5");
    TEST_ASSERT(n4 == 4, "n4 debe ser indice 4");
    const EntradaNum *e4 = ObtenerEntradaNum(4);
    TEST_ASSERT(e4->tipo == NUM_REAL_DECIMAL, "e4 debe ser NUM_REAL_DECIMAL");
    TEST_ASSERT(fabs(e4->valor_float - 25.5) < 1e-9, "e4 valor_float debe ser 25.5");

    /* Notación científica exponencial IEEE 754 de 64 bits */
    int n5 = InstallNum_lex("1.5E3");
    TEST_ASSERT(n5 == 5, "n5 debe ser indice 5");
    const EntradaNum *e5 = ObtenerEntradaNum(5);
    TEST_ASSERT(e5->tipo == NUM_REAL_CIENTIFICO, "e5 debe ser NUM_REAL_CIENTIFICO");
    TEST_ASSERT(fabs(e5->valor_float - 1500.0) < 1e-9, "e5 valor_float debe ser 1500.0");

    int n6 = InstallNum_lex("0.05e-2");
    TEST_ASSERT(n6 == 6, "n6 debe ser indice 6");
    const EntradaNum *e6 = ObtenerEntradaNum(6);
    TEST_ASSERT(fabs(e6->valor_float - 0.0005) < 1e-9, "e6 valor_float debe ser 0.0005");

    /* Deduplicación */
    int n5_dup = InstallNum_lex("1.5E3");
    int n1_dup = InstallNum_lex("42");
    TEST_ASSERT(n5_dup == 5, "Deduplicacion 1.5E3 fallida");
    TEST_ASSERT(n1_dup == 1, "Deduplicacion 42 fallida");
    TEST_ASSERT(totalNum == 6, "totalNum debe ser 6");

    pruebas_ejecutadas++;
    printf("  -> OK (Enteros 64 bits y flotantes IEEE 754 verificados)\n");
}

void test_tabla_cadenas_literales(void) {
    printf("[TEST 3] Probando Tabla de Cadenas Literales (tablaString y des-escape)...\n");
    limpiarTablas();

    /* Cadena estándar */
    int s1 = InstallString_lex("\"Hola mundo\"");
    TEST_ASSERT(s1 == 1, "s1 debe ser indice 1");
    const EntradaString *es1 = ObtenerEntradaString(1);
    TEST_ASSERT(strcmp(es1->texto, "Hola mundo") == 0, "Texto debe ser 'Hola mundo'");
    TEST_ASSERT(es1->longitud == 10, "Longitud debe ser 10");

    /* Cadena con comillas escapadas */
    int s2 = InstallString_lex("\"Dijo: \\\"Hola\\\"\"");
    TEST_ASSERT(s2 == 2, "s2 debe ser indice 2");
    const EntradaString *es2 = ObtenerEntradaString(2);
    TEST_ASSERT(strcmp(es2->texto, "Dijo: \"Hola\"") == 0, "Escape \\\" fallido");

    /* Ruta con barras dobles */
    int s3 = InstallString_lex("\"C:\\\\Archivos\\\\flex\"");
    TEST_ASSERT(s3 == 3, "s3 debe ser indice 3");
    const EntradaString *es3 = ObtenerEntradaString(3);
    TEST_ASSERT(strcmp(es3->texto, "C:\\Archivos\\flex") == 0, "Escape \\\\ fallido");

    /* Cadena vacía */
    int s4 = InstallString_lex("\"\"");
    TEST_ASSERT(s4 == 4, "s4 debe ser indice 4");
    const EntradaString *es4 = ObtenerEntradaString(4);
    TEST_ASSERT(strcmp(es4->texto, "") == 0 && es4->longitud == 0, "Cadena vacia fallida");

    /* Deduplicación sobre texto limpio */
    int s1_dup = InstallString_lex("\"Hola mundo\"");
    int s2_dup = InstallString_lex("\"Dijo: \\\"Hola\\\"\"");
    TEST_ASSERT(s1_dup == 1, "Deduplicacion s1 fallida");
    TEST_ASSERT(s2_dup == 2, "Deduplicacion s2 fallida");
    TEST_ASSERT(totalString == 4, "totalString debe ser 4");

    pruebas_ejecutadas++;
    printf("  -> OK (Des-escape determinista y deduplicacion limpia verificados)\n");
}

void test_compatibilidad_flex_yytext(void) {
    printf("[TEST 4] Probando llamadas compatibles con FLEX (InstallID/InstallNum/InstallString)...\n");
    limpiarTablas();

    /* Simulación de yytext asignado dinámicamente por FLEX */
    char buffer_flex[128];

    strcpy(buffer_flex, "variable_global");
    yytext = buffer_flex;
    int k1 = InstallID();
    TEST_ASSERT(k1 == 1, "InstallID() con yytext fallido");

    strcpy(buffer_flex, "3.141592653589793");
    yytext = buffer_flex;
    int k2 = InstallNum();
    TEST_ASSERT(k2 == 1, "InstallNum() con yytext fallido");
    const EntradaNum *en = ObtenerEntradaNum(k2);
    TEST_ASSERT(fabs(en->valor_float - 3.141592653589793) < 1e-12, "Precision double fallida");

    strcpy(buffer_flex, "\"Enigma-64\\nSPL\"");
    yytext = buffer_flex;
    int k3 = InstallString();
    TEST_ASSERT(k3 == 1, "InstallString() con yytext fallido");
    const EntradaString *es = ObtenerEntradaString(k3);
    TEST_ASSERT(strcmp(es->texto, "Enigma-64\nSPL") == 0, "Escape \\n fallido");

    pruebas_ejecutadas++;
    printf("  -> OK (Compatibilidad nativa con FLEX y yytext validada)\n");
}

int main(void) {
    printf("========================================================================\n");
    printf(" BATERIA DE PRUEBAS UNITARIAS: TABLAS DE SIMBOLOS Y LITERALES (SPL C)   \n");
    printf("========================================================================\n\n");

    test_tabla_identificadores();
    test_tabla_constantes_numericas();
    test_tabla_cadenas_literales();
    test_compatibilidad_flex_yytext();

    /* Mostrar el volcado formateado */
    imprimirVolcadoTablas();

    printf("========================================================================\n");
    printf(" TODAS LAS PRUEBAS COMPLETADAS CON EXITO!\n");
    printf(" Pruebas modulares: %d | Aserciones formales: %d | Fallos: 0\n", pruebas_ejecutadas, aserciones_exitosas);
    printf("========================================================================\n");

    return 0;
}
