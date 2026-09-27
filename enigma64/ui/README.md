# Interfaz de Enigma-64 — Noctua Systems

Interfaz grafica del computador **Enigma-64**, construida unicamente sobre la
biblioteca estandar de Python (`tkinter` / `ttk`). No requiere instalar nada
aparte del entorno de conda.

> **Integrante 5 — Maicol Sebastian Olarte Ramirez**
> Modulo de interfaz de usuario.

---

## 1. El requisito que manda sobre el diseno

> *"Es muy importante que cada modulo pueda funcionar por separado; el profesor
> no quiere que todos los componentes se mezclen."*

Toda la arquitectura de este paquete existe para cumplir eso:

| Regla | Como se cumple | Como se comprueba |
|---|---|---|
| Un panel no conoce a otro panel | Se comunican publicando eventos en `core/bus.py` | `tests/test_ui_aislamiento.py` lee el AST y falla si un panel importa a otro |
| Un panel no toca el modulo de hardware | Habla con un **servicio** (`servicios/`) que envuelve el modulo del companero | La misma prueba rechaza `import enigma64.memoria` dentro de un panel |
| Cada panel arranca solo | `PanelBase.ejecutar_suelto()` construye su propia maquina y un bus que no va a ninguna parte | Cada panel tiene su bloque `__main__` |
| Un panel roto no tumba al resto | El bus captura las excepciones de cada oyente y sigue notificando | `test_un_oyente_roto_no_tumba_a_los_demas` |
| Si falta un modulo, la interfaz lo dice | El servicio queda `disponible = False` y el panel pinta un aviso | `test_un_panel_sobrevive_a_que_falte_su_modulo` |

**Los modulos de los companeros no se modifican nunca.** Toda la adaptacion
ocurre en `servicios/adaptadores.py`. Si `enigma64.memoria` cambia de firma,
solo hay que tocar su adaptador.

---

## 2. Como se arranca

```bash
conda env create -f environment.yml      # solo la primera vez
conda activate Enigma-64

python -m enigma64.ui                    # ventana completa
```

Cada modulo por separado, que es como se demuestra ante el profesor:

```bash
python -m enigma64.ui.paneles.panel_memoria     # RAM y buses      (Integrante 1)
python -m enigma64.ui.paneles.panel_registros   # banco de registros (Integrante 2)
python -m enigma64.ui.paneles.panel_alu         # ALU              (Integrante 2)
python -m enigma64.ui.paneles.panel_cargador    # cargador y bits  (Integrante 4)
python -m enigma64.ui.paneles.panel_mapa        # mapa de memoria
python -m enigma64.ui.paneles.panel_consola     # traza del bus
```

Cada una de esas ordenes abre una ventana con **un solo modulo dentro**, con su
propia RAM y su propio banco de registros. No comparten nada.

---

## 3. Organizacion

La estructura sigue la del proyecto guia (`Computer_Emulation-main`), con un
modelo propio:

```
enigma64/ui/
├── core/                  sistema de diseno y fontaneria
│   ├── tema.py            paleta, tipografias y estilos ttk (fuente unica de verdad)
│   ├── widgets.py         tarjetas, diodos, insignias, tira de bits, marca Noctua
│   ├── bus.py             bus de eventos: el unico canal entre paneles
│   └── formato.py         parseo y formateo de valores de 64 bits
├── servicios/             frontera con los modulos del equipo
│   ├── puertos.py         el contrato que espera cada panel
│   ├── adaptadores.py     envoltorios de memoria, registros, alu y cargador
│   ├── fabrica.py         arma una `Maquina` coherente
│   └── mapa_memoria.py    el mapa de la Tarea 9 como dato puro
├── paneles/               un panel por modulo, todos independientes
│   ├── base.py            PanelBase + arranque suelto
│   ├── panel_memoria.py   · panel_registros.py · panel_alu.py
│   ├── panel_cargador.py  · panel_mapa.py      · panel_consola.py
├── shell/ventana.py       compone los paneles; no tiene logica de ningun modulo
└── mockups/               los bocetos previos a la implementacion
```

### Flujo de dependencias

```
   paneles  ──►  servicios  ──►  enigma64.{memoria,registros,alu,cargador}
      │                                   (modulos del equipo, intactos)
      └──────►  core (tema, widgets, bus, formato)

   Entre paneles: NADA. Solo eventos por el bus.
```

---

## 4. Los paneles

| Panel | Modulo que expone | Que muestra |
|---|---|---|
| **Memoria RAM y buses** | `enigma64.memoria` | Acceso de 1/2/4/8 bytes en Big-Endian, control de alineacion, volcado hexadecimal con ASCII, diodos `READY` / `MISALIGNED` / `MMIO` / `ADDR_FAULT`, paginas asignadas |
| **Banco de registros** | `enigma64.registros` | R0..R7, PC y SR con su nibble, hexadecimal y decimal con signo; las siete banderas como diodos pulsables; R0 marcado como cableado a cero |
| **ALU** | `enigma64.alu` | Las 16 operaciones del ISA agrupadas por familia, latches A y B, salida Z en hex/decimal/binario y las banderas que esa instruccion afecta |
| **Cargador y bits** | `enigma64.cargador` | Carga de `.e64` / `.bin` / `.txt` o de un volcado pegado, con validacion del mapa de memoria; manipulador bit a bit con el byte como ocho celdas pulsables |
| **Mapa de memoria** | — (dato puro) | Las ocho regiones de la Tarea 9 con permisos, los controladores MMIO, y la region donde cayo el ultimo acceso |
| **Traza del bus** | — (dato puro) | Todo lo que circula por el bus, con hora, origen y severidad |

Los dos ultimos no dependen de ningun modulo, asi que funcionan siempre.

---

## 5. Eventos del bus

Los paneles se coordinan publicando estos eventos, definidos en `core/bus.py`:

| Evento | Lo publica | Lo escucha |
|---|---|---|
| `memoria.leida` / `memoria.escrita` | panel de memoria | traza |
| `bus.senal` | panel de memoria | mapa, traza |
| `registros.cambiados` | panel de registros | traza |
| `alu.ejecutada` | panel de la ALU | traza |
| `cargador.programa_cargado` | panel del cargador | mapa, traza |
| `cargador.carga_rechazada` | panel del cargador | traza |
| `ui.ir_a_direccion` | panel del cargador | panel de memoria |
| `ui.traza` | cualquiera | traza, barra de estado |

`ui.ir_a_direccion` es el ejemplo que mejor explica la regla: cuando el
cargador termina, **no llama** al panel de memoria para que se mueva. Anuncia
la direccion y sigue con lo suyo. Si el panel de memoria esta abierto, se
entera; si no lo esta, no pasa nada.

---

## 6. Identidad visual

Noctua es la lechuza: vigilancia nocturna. De ahi salen el fondo de noche
profunda, el ambar de los ojos como color de marca y el cian de los datos en
transito por los buses. El isotipo se dibuja con vectores sobre un `Canvas`,
sin archivos de imagen, para que cualquier modulo suelto pueda mostrarlo.

| Color | Uso |
|---|---|
| `#0B0E14` abismo | fondo de la aplicacion |
| `#171E2B` elevado | tarjetas |
| `#F2B138` ambar | marca Noctua, valores recien cambiados |
| `#3FC9D6` cian | datos, direcciones, bits encendidos |
| `#A98BF5` violeta | espacio MMIO |
| `#4FD07A` verde | `READY`, carga aceptada |
| `#FFB454` naranja | `MISALIGNED`, avisos |
| `#FF5C6C` rojo | `ADDR_FAULT`, carga rechazada |

Todo sale de `core/tema.py`; ningun panel define un color por su cuenta.

---

## 7. Pruebas

```bash
python -m pytest tests/ -q
```

| Archivo | Que cubre |
|---|---|
| `tests/test_ui_nucleo.py` | formato, bus, mapa de memoria y adaptadores (sin pantalla) |
| `tests/test_ui_paneles.py` | construccion y comportamiento de los paneles con widgets reales |
| `tests/test_ui_aislamiento.py` | que los modulos no se mezclan (analisis del codigo) |

Las pruebas graficas se omiten solas si no hay servidor X, de modo que la
bateria completa sigue corriendo en una maquina sin escritorio.

---

## 8. Notas para el equipo

- La ventana se dimensiona sola segun la pantalla y **nunca nace mas grande que
  el escritorio**; esta verificado a 1366x768. Los paneles que no caben se
  desplazan con la rueda (`core/widgets.MarcoDesplazable`).
- El `main.py` de la raiz se dejo **sin tocar** para no chocar con la rama de
  los companeros; sigue abriendo la demo de registros. Cuando el equipo quiera
  que `python main.py` abra la interfaz completa, basta cambiar su import por
  `from enigma64.ui.shell.ventana import main`.
- Los bocetos se generan desde la misma paleta que usa la aplicacion:
  `python -m enigma64.ui.mockups.generar_mockups`.
