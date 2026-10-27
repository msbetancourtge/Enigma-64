# ==============================================================================
# Makefile General — Sistema de Procesamiento del Lenguaje (SPL) Enigma-64
# Responsabilidad: Integrante 7 (Driver Principal, Pipeline & Pruebas)
# ==============================================================================

PYTHON ?= python
CC ?= gcc
CFLAGS ?= -Wall -Wextra -std=c11 -O2

C_DIR = spl/compilador
C_TARGET = $(C_DIR)/test_tablas.exe

.PHONY: all pipeline escenario1 escenario2 escenario3 test test-spl test-c clean

all: test-c pipeline

pipeline:
	$(PYTHON) -m spl --escenario todos

escenario1:
	$(PYTHON) -m spl --escenario 1

escenario2:
	$(PYTHON) -m spl --escenario 2

escenario3:
	$(PYTHON) -m spl --escenario 3

test:
	$(PYTHON) -m pytest -q

test-spl:
	$(PYTHON) -m pytest tests/test_spl tests/core/test_enlazador.py -q

test-c:
	$(PYTHON) -m spl --verificar-c --sin-tablas

clean:
	-$(MAKE) -C $(C_DIR) clean
	$(PYTHON) -c "import pathlib, shutil; [shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]"

