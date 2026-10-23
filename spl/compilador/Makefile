# Makefile para Tablas de Símbolos y Literales (SPL Enigma-64)
# Integrante 6 - Lenguajes de Programación (Universidad Nacional de Colombia)

CC ?= gcc
CFLAGS ?= -Wall -Wextra -std=c11 -O2 -I.

TARGET = test_tablas.exe
SRCS = tablas_simbolos.c test_tablas.c
OBJS = $(SRCS:.c=.o)

.PHONY: all test clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $^

%.o: %.c tablas_simbolos.h
	$(CC) $(CFLAGS) -c $< -o $@

test: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(OBJS) $(TARGET)
