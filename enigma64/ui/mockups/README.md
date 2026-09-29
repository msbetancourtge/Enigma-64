# Bocetos de la interfaz de Enigma-64

Bocetos de diseno previos a la implementacion, en SVG (se abren en cualquier
navegador).

No estan dibujados a mano en una herramienta externa: se **generan desde la
misma paleta que usa la aplicacion** (`enigma64/ui/core/tema.py`), asi que el
boceto y el producto final no se pueden separar. Si cambia un color de marca,
se regeneran y ya estan al dia:

```bash
python -m enigma64.ui.mockups.generar_mockups
```

| Archivo | Que muestra |
|---|---|
| `00_shell_completo.svg` | La ventana completa a 1366x768: cuaderno de modulos a la izquierda, mapa y traza a la derecha |
| `01_panel_memoria.svg` | El modulo de RAM y buses abierto por separado |
| `02_panel_registros.svg` | El banco de registros con las siete banderas |
| `03_panel_alu.svg` | La ALU con el repertorio del ISA agrupado por familia |
| `04_panel_cargador.svg` | El cargador y el manipulador bit a bit |
| `05_panel_mapa.svg` | El mapa de memoria de la Tarea 9 con permisos y controladores MMIO |
| `06_sistema_diseno.svg` | Paleta, tipografias, componentes y el principio de aislamiento |
| `07_panel_cpu.svg` | La Unidad de Control con sus cinco fases y los micro-registros (estado encendido, el que se vera al fusionar la rama del Integrante 3) |
| `08_panel_mmio.svg` | Visor/editor de los cinco controladores mapeados en memoria |
| `09_panel_algoritmos.svg` | Los algoritmos de la Tarea 9 con su traduccion manual a lenguaje de maquina |

Los bocetos 01 a 05 y 07 a 09 estan enmarcados como **ventanas de un solo modulo**,
porque asi es como se demuestra cada componente por separado. La insignia
"MODULO INDEPENDIENTE" y la orden `python -m enigma64.ui.paneles.…` aparecen en
la cabecera de cada uno.
