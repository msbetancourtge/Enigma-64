# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2

**Tarea 29 — Librería de estructuras de datos (listas y matrices) para Enigma-64**
**Integrante 5 — Maicol Sebastian Olarte Ramirez · GUI Noctua (`enigma64/ui/`)**

---

## 1. Alcance

Panel visual de estructuras de datos en la GUI Noctua: un adaptador en
`enigma64/ui/servicios/` y una vista en Tkinter que muestran en vivo los
vectores (celdas indexadas `V[0 … N-1]`) y las matrices (cuadrícula `F × C`)
mientras corren los algoritmos de la librería, respetando el aislamiento AST
(`test_ui_aislamiento.py`).

| Entregable | Archivo |
|---|---|
| Adaptador de servicio | `enigma64/ui/servicios/estructuras.py` (`AdaptadorEstructuras`) |
| Visores reutilizables | `enigma64/ui/core/visores.py` (`VisorVector`, `VisorMatriz`) |
| Vista Tkinter | `enigma64/ui/paneles/panel_estructuras.py` (`PanelEstructuras`) |
| Registro en la máquina y la ventana | `servicios/fabrica.py`, `servicios/__init__.py`, `shell/ventana.py`, `paneles/__init__.py` |
| Eventos nuevos del bus | `core/bus.py`: `estructuras.definida`, `estructuras.actualizadas` |
| Pruebas | `tests/ui/test_ui_estructuras.py` (+ `test_ui_aislamiento.py`, que ya recorre el panel nuevo) |

Todos los cambios a archivos existentes son **aditivos**: no se modificó
ningún módulo de los compañeros (`spl/estructuras`, `spl/include/*`,
`spl/ejemplos/merge_sort.asm`, `enigma64/cpu.py`, …).

## 2. Diseño

```
PanelEstructuras ──► AdaptadorEstructuras ──► spl.estructuras (Integrante 4)
      │                     │                   DescriptorVector / DescriptorMatriz
      │                     │                   precargar_estructuras_en_ram
      │                     │                   compilar_a_binario_e64  (.e64)
      │                     ├──► AdaptadorCargador ──► CargadorEnigma.cargar_binario
      │                     ├──► AdaptadorMemoria  ──► RAMMemory (0x00210000 – 0x00300000)
      │                     ├──► AdaptadorCPU      ──► CPU (FSM, fase a fase)
      │                     └──► AdaptadorMMIO     ──► Perifericos (pantalla 0xFF001010)
      └──► core/visores.py (VisorVector, VisorMatriz)   ← solo dibujan, no conocen la RAM
```

* **Un panel, un servicio.** El panel no importa ni la librería ni el hardware;
  todo pasa por `AdaptadorEstructuras`, que también expone el parseo y el
  formateo (`parsear_vector`, `parsear_matriz`, `formatear`).
* **Lógica pura y comprobable.** El servicio no usa Tkinter: compila, carga,
  avanza la CPU y devuelve "fotos" de las estructuras (palabras de 64 bits por
  filas). Por eso casi todas las pruebas corren sin pantalla.
* **Visores genéricos.** `VisorVector` y `VisorMatriz` reciben una foto y la
  dibujan sobre un `Canvas`; sirven para cualquier otra pestaña futura.
* **Máquina compartida.** En la ventana completa los datos viven en la misma RAM
  que ven Memoria, Registros y Unidad de Control. Al pulsar una celda se publica
  `ui.ir_a_direccion` y el volcado de memoria salta a esa dirección.
* **Importación defensiva.** Si `spl.estructuras` no carga, el servicio queda
  `disponible = False` y la pestaña explica el motivo sin tumbar la ventana.
* **Catálogo automático.** Cualquier `.asm` de `spl/ejemplos/` que haga
  `#include "estructuras.inc"` aparece solo en el selector, así que los
  problemas del Integrante 7 (producto punto, búsqueda binaria,
  multiplicación de matrices) se integran sin tocar la GUI.

## 3. Funcionalidad de la pestaña

La pestaña guía al usuario en tres pasos numerados:

1. **Datos de entrada.** El usuario escoge *Vector* o *Matriz*, escribe un
   nombre y los valores (`45, -12, 89` o `1 2 3; 4 5 6`, en decimal, `0x..`,
   `0b..` o reales) y pulsa *Escribir en RAM*. Se construye con la librería del
   Integrante 4 el descriptor de 32 bytes (`0x00210000 + ranura·32`), la cabecera
   inline (`[base-16]`, `[base-8]`) y los datos alineados a 8 bytes. La base es
   automática (sin solapes) o la que indique el usuario. Los errores (filas
   irregulares, solapes, nombres inválidos) se muestran en rojo sin perder lo
   que ya estaba.
2. **Programa.** Se elige un programa (merge sort del Integrante 6, prueba de
   cabeceras del Integrante 4 u otro `.asm`) y *Compilar y cargar* lo pasa por
   Preprocesador → Ensamblador → `.e64` → `CargadorEnigma`, con `SP = 0x00400000`.
   Los datos de entrada del usuario se reescriben en cada carga, de modo que
   *Reiniciar* siempre parte de la misma entrada.
3. **Ejecución.** *Paso*, *×10*, *Animar* (cuatro velocidades) o *Ejecutar
   hasta HLT*. En cada instrucción se muestran PC, subrutina actual
   (`MERGE_SORT`, `VEC_SET`, …), instrucción, contador y los registros de la ABI
   (`R1` base, `R2` i/lo, `R3` j/hi/valor, `R4` aux, `R5` retorno, `SP`).

En las estructuras:

| Marca | Significado |
|---|---|
| Fondo ámbar | celda **escrita** por la última instrucción (`STORE`) |
| Borde cian | celda **leída** por la última instrucción (`LOAD`) |
| Texto ámbar | la celda ya no vale lo que valía al cargar |

La dirección accedida se toma del micro-registro `Z` justo antes de la fase
`MEMORY` de la FSM, avanzando la CPU fase a fase. Al terminar se muestran la
**entrada y la salida** lado a lado (`entrada [38, 27, …]` / `salida [-4, 3, …]`)
y lo que el programa escribió en la **pantalla MMIO**. Los valores se ven en
decimal con signo, hexadecimal o IEEE 754, y una celda pulsada muestra su
dirección con la fórmula `B + (i << 3)` o `B + ((i·C + j) << 3)`.

*Detectar en RAM* recorre la tabla de descriptores y dibuja lo que construyó un
programa cualquiera con `DESC_VEC_INIT` / `DESC_MAT_INIT`.

Nota técnica: la CPU compartida nace sin periféricos. Al cargar un programa
de la Tarea 29 el servicio le conecta el subsistema `Perifericos` real
para que la escritura a `0xFF001010` del merge sort no falle.

## 4. Pruebas

`tests/ui/test_ui_estructuras.py` — 43 pruebas:

* **Utilidades puras:** parseo de vectores y matrices (formatos válidos e
  inválidos), formateo en los tres modos, zonas del mapa de memoria.
* **Servicio:** escritura con descriptor y cabecera, matrices *row-major*, bases
  y ranuras sin solape, rechazo de solapes y nombres, detección por
  descriptores, merge sort sobre la entrada del usuario y sobre su vector demo,
  salida MMIO, accesos leídos/escritos, recarga desde la entrada, etiqueta de
  subrutina, cambio de programa, programa con errores y cabecera con basura.
* **Panel (requiere servidor X):** arranque con el merge sort, dibujo de la
  entrada, aviso de entrada inválida, ejecución con entrada/salida, celdas
  iluminadas y eventos del bus, selección de celda, cambio de formato y
  animación con pausa.

Además `test_ui_aislamiento.py` comprueba que `panel_estructuras.py` no importa
otros paneles ni el hardware y que se puede arrancar solo.

```bash
python -m pytest tests/ui/test_ui_estructuras.py -q     # 43 passed
python -m pytest -q                                      # suite completa
```

## 5. Uso

```bash
python main.py                                     # pestaña «Estructuras»
python -m enigma64.ui.paneles.panel_estructuras    # el panel solo
```
