# Universidad Nacional de Colombia
## Lenguajes de Programación — Semestre 2026-2

**Tarea 27 — Traductor de ensamblador CacaoCore-64 a Enigma-64**
**Integrante 5 — Maicol Sebastian Olarte Ramirez · GUI Principal (`enigma64/ui/`)**

---

## 1. Alcance

Integrar el traductor LEX del grupo (`spl.traductor`) en la interfaz Noctua como
una pestaña más, sin romper la regla de aislamiento de la GUI:

| Entregable | Archivo |
|---|---|
| Adaptador de servicio | `enigma64/ui/servicios/traduccion.py` (`AdaptadorTraduccion`) |
| Vista Tkinter | `enigma64/ui/paneles/panel_traduccion.py` (`PanelTraduccion`) |
| Registro en la máquina y la ventana | `servicios/fabrica.py`, `shell/ventana.py`, `paneles/__init__.py` |
| Eventos nuevos del bus | `core/bus.py`: `traduccion.realizada`, `traduccion.verificada` |
| Pruebas | `tests/ui/test_ui_traduccion.py` (+ `test_ui_aislamiento.py`, que ya recorre el panel nuevo) |

## 2. Diseño

```
PanelTraduccion ──► AdaptadorTraduccion ──► spl.traductor (ply.lex, Integrantes 1, 2 y 4)
                           │                 enigma64.ensamblador
                           ├──► AdaptadorCargador ──► CargadorEnigma   (0x00200000)
                           ├──► AdaptadorMemoria  ──► RAMMemory        (.data en 0x00201000)
                           └──► AdaptadorCPU      ──► CPU (FSM)
```

* **Un panel, un servicio.** Igual que el panel de algoritmos, la composición
  (traductor + cargador + RAM + CPU) se hace en el servicio; el panel no
  importa ni el traductor ni el hardware, y `test_ui_aislamiento.py` lo comprueba
  leyendo su AST.
* **Importación defensiva.** Si `spl.traductor` no carga (por ejemplo, falta
  `ply`), el servicio queda `disponible = False` y la pestaña muestra el motivo
  en vez de tumbar la ventana.
* **Máquina compartida.** En la ventana completa el programa traducido entra en
  la misma RAM que ven las pestañas de Memoria, Registros y Unidad de Control.
  Al cargar se publican `cargador.programa_cargado` y `ui.ir_a_direccion`, así
  que el volcado de memoria y el mapa se actualizan solos.

## 3. Funcionalidad de la pestaña

1. **Fuente:** selector con los `.asm` de `spl/traductor/ejemplos/` (los tres
   algoritmos clásicos primero) o *Abrir .asm...* desde disco. El editor de
   CacaoCore es editable.
2. **Traducir:** ejecuta el traductor LEX y ensambla la salida. Los dos
   programas quedan **lado a lado**; las líneas de CacaoCore con error se pintan
   en rojo y el botón de envío se bloquea.
3. **Correspondencia:** al pulsar una línea de cualquiera de los dos lados se
   resaltan la instrucción de CacaoCore y todas las de Enigma-64 que generó (se
   usa la anotación `; L<n>:` que emite el traductor).
4. **Enviar al Cargador / RAM:** `CargadorEnigma.cargar_bytes` en `0x00200000`
   (PC y SP configurados) y siembra de `.data` con `precargar_datos_en_ram` del
   Integrante 4.
5. **Ejecutar:** corre la CPU hasta `HLT`, lee las variables en RAM y, para los
   tres algoritmos clásicos, contrasta con los resultados oficiales de la
   Tarea 10.
6. **Guardar .asm Enigma...:** exporta el código traducido.

| Programa | Verificación | Resultado en la GUI |
|---|---|---|
| `cacao_euclides.asm` | `a = b = 6` | MCD(48, 18) = 6 · 199 instrucciones |
| `cacao_factorial.asm` | `fact = 120` | 5! = 120 · 164 instrucciones |
| `cacao_fibonacci.asm` | `fib..fib6 = [0, 1, 1, 2, 3, 5, 8]` | 402 instrucciones |

## 4. Pruebas

```bash
python -m pytest tests/ui/test_ui_traduccion.py tests/ui/test_ui_aislamiento.py -q
```

* Servicio (sin pantalla): traducción y ensamblado de los tres algoritmos,
  correspondencia de líneas, errores sin excepción, rechazo de cargas con
  errores, código y `.data` en la RAM compartida, ejecución real con
  verificación contra la Tarea 10, dos cargas seguidas y servicio degradado.
* Panel (con servidor X; se omiten si no hay): arranque con un algoritmo ya
  traducido, resaltado lado a lado, envío al cargador con evento en el bus,
  ejecución + verificación de los tres algoritmos y bloqueo ante errores.

## 5. Uso

```bash
python -m enigma64.ui                            # pestaña "Traductor"
python -m enigma64.ui.paneles.panel_traduccion   # pestaña suelta
```
