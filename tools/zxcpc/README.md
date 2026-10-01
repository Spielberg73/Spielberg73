# zxcpc — kit de port asistido ZX Spectrum ⇄ Amstrad CPC

`zxcpc` ayuda a llevar juegos en código máquina del **ZX Spectrum al Amstrad CPC** y
del **Amstrad CPC al ZX Spectrum +2A/+3**. Un conversor totalmente automático no es
posible: cada juego toca el hardware a su manera. Por eso el kit hace lo que sí se
puede automatizar y deja a la vista lo que queda para una persona:

1. **Carga** el juego en cualquier formato habitual (TAP, TZX, Z80, SNA, DSK, CDT o
   binario en bruto).
2. **Lo analiza** de dos formas: un desensamblado estático y una ejecución real en
   una máquina emulada, con un guion de pulsaciones que explora el juego. Así
   encuentra el código, cada acceso al hardware, las llamadas a la ROM o al firmware,
   las escrituras en pantalla y el código automodificable.
3. **Parchea** cada punto caliente para que salte a una capa de abstracción de
   hardware (el **HAL**), escrita en ensamblador Z80, que emula en la otra máquina
   la pantalla, el teclado, el sonido y las interrupciones.
4. **Genera el port** listo para cargar (SNA y DSK para el CPC, Z80 para el +3),
   junto con un informe HTML, la lista de parches y el código fuente del HAL.
5. **Prueba el port**: lo ejecuta en paralelo con el original y guarda capturas de
   los dos.

Está escrito en Python 3 puro, sin dependencias. Trae su propio desensamblador,
ensamblador y emulador de Z80.

## Instalación

```sh
cd tools/zxcpc
pip install -e .            # instala la orden «zxcpc»
# o, sin instalar:
python3 -m zxcpc --help
```

Hace falta Python 3.9 o superior. Para los tests hace falta `pytest`
(`pip install -e .[test]`).

### ROMs

`zxcpc` **no incluye ninguna ROM**. Sin ellas funciona para juegos que no dependen
de la ROM o del firmware: en el Spectrum usa una mini-ROM propia con las rutinas más
comunes emuladas. Con las ROMs originales el análisis y el port son más fieles:

* `--rom 48.rom`: ROM de 48K del Spectrum. Permite cargar cintas con el cargador
  real y copiar la fuente de caracteres al port.
* `--cpc-roms DIR`: directorio con `cpc6128.rom` (32K: sistema operativo y BASIC).
  Hace falta para ejecutar juegos del CPC que usan el firmware y para copiar su
  fuente al port.

## Uso rápido

```sh
# ¿Qué hay en el fichero?
zxcpc info juego.tap

# Análisis: lista de puntos calientes e informe HTML
zxcpc analyze juego.z80 --html informe.html

# Spectrum -> CPC (genera juego_cpc.sna y juego_cpc.dsk)
zxcpc port juego.tap --rom 48.rom -o port_cpc

# CPC -> Spectrum +2A/+3 (genera juego_zx.z80)
zxcpc port juego.dsk --cpc-roms roms/ -o port_zx

# Binario en bruto: hay que dar la plataforma y la dirección de carga
zxcpc port juego.bin --platform zx --load 0x8000 -o port_cpc
```

Cada `port` deja en el directorio de salida:

| fichero | contenido |
|---|---|
| `<nombre>_cpc.sna`, `<nombre>_cpc.dsk` | el port para CPC (snapshot y disco; en el disco, `RUN"DISC"`) |
| `<nombre>_zx.z80` | el port para Spectrum +2A/+3 |
| `informe.html` | análisis, parches, avisos y capturas del original y del port |
| `parches.json` | cada parche: dirección, bytes originales, bytes nuevos y manejador |
| `hal.asm` | el código fuente del HAL, con los símbolos fijados para este juego |
| `port.json` | (ZX→CPC) las opciones usadas; se puede editar y pasar con `--config` |
| `capturas/` | capturas PNG del original y del port durante la prueba |

### Órdenes

| orden | para qué |
|---|---|
| `info` | describe un fichero: formato, bloques, cabeceras, registros |
| `analyze` | análisis estático + dinámico; `--html` y `--json` para guardar el resultado |
| `disasm` | desensamblado **reensamblable** (vuelve a dar los mismos bytes con `zxcpc asm`) |
| `port` | porta el juego a la otra máquina (`--to cpc` / `--to zx`, por defecto la otra) |
| `run` | ejecuta en la máquina emulada, con teclas programadas (`--keys 20-60:P,60-90:A+SPACE`), y guarda una captura (`--png`) |
| `asm` | ensambla un fichero `.asm` (sintaxis compatible con pasmo) |
| `scr` | convierte una pantalla `.scr` del Spectrum a PNG y, con `--cpc`, a una pantalla del CPC |

Opciones útiles de `port`:

* `--frames N`: frames de ejecución para el análisis dinámico (0 = solo estático).
* `--keys Q=JOYUP,A=JOYDOWN`: teclas extra. La de la izquierda es la del Spectrum y
  la de la derecha la del CPC.
* `--exclude 8123,8456`: direcciones que no se deben parchear.
* `--refresh N`: líneas de pantalla que el HAL repasa por frame como red de seguridad
  (por defecto 2; 0 con `--512k` si todas las escrituras en pantalla se reflejan).
* `--512k` (ZX→CPC): juegos de 128K que paginan memoria, para un CPC 6128 con la
  ampliación de 512K (576K en total), como la que emulan Caprice32 (`ram_size=576`),
  WinAPE o Retro Virtual Machine.
* `--palette a,b,c,d` (ZX→CPC): los 4 colores del firmware para las plumas 0-3.
* `--mono` (ZX→CPC): monocromo, más fiel a la forma a cambio del color.
* `--frameskip N` (ZX→CPC): en los juegos que vuelcan un búfer entero a la pantalla
  con `LDIR` en cada frame, solo uno de cada N+1 volcados llega a la pantalla del CPC.
  El juego va más rápido y la imagen se mueve a saltos. Solo se aplica si el análisis
  ve que el juego no lee su propia pantalla.

### Flujo de trabajo recomendado

1. `zxcpc port` con las ROMs si las tienes.
2. Abre `informe.html`. En «Avisos» aparece lo que el kit no ha podido resolver solo:
   IM 2 en el CPC, rutinas de la ROM no emuladas, escrituras en pantalla con PUSH,
   accesos indirectos que no se ven…
3. Prueba el port en un emulador real (Caprice32, WinAPE o Retro Virtual Machine para
   el CPC; Fuse o ZEsarUX en modo +3 para el Spectrum).
4. Ajusta (`port.json`, `--exclude`, `--keys`) y repite. Para cambios de más
   calado, `disasm` da un fuente reensamblable del juego y `hal.asm` el de la capa
   de hardware.

## Cómo funciona

### Spectrum → CPC

* **Pantalla.** El CPC usa modo 1 con un CRTC reprogramado a 256×192 (R1=32, R6=24),
  con la pantalla en `$0000-$3FFF`. Así, la RAM del juego (`$4000-$FFFF`) no se toca:
  la pantalla del Spectrum sigue en `$4000` y el juego la escribe como siempre.
  Cada escritura en `$4000-$5AFF` se parchea para que el HAL la convierta al momento.
  Un refresco de fondo repasa unas líneas por frame para lo que no se ve (PUSH, etc.).
* **HAL.** Vive en los ocho huecos de 512 bytes que deja la pantalla del CPC
  (`$x000-$x1FF`), sin gastar memoria del juego.
* **Parches.** Las instrucciones de 1 byte se cambian por un `RST`. `LD (HL),A` y
  `LD (DE),A` tienen un `RST` propio, y las demás se localizan por la dirección de
  retorno. Las de 2 bytes usan `RST $30` más un identificador y las de 3 o 4 bytes,
  un `CALL`. `OUT ($FE),A` tiene su propio `RST $28` (los bucles del beeper hacen
  miles por segundo) y `HALT` va por la tabla de 1 byte y espera el frame.
* **Copias en bloque.** Muchos juegos dibujan en un búfer y lo vuelcan entero a la
  pantalla en cada frame con `LDIR`. El HAL copia comparando, en bloques de 8 bytes
  cuando puede, y solo convierte los bytes que cambian. Del mismo modo, en los sitios
  donde el análisis ve que la mayoría de escrituras repiten el valor (textos,
  atributos), el manejador lo comprueba antes y no convierte nada.
* **Interrupciones.** El CPC interrumpe 300 veces por segundo. El HAL llama a la
  rutina del juego una vez por frame (IM 1 o IM 2, con el vector buscado en la
  ROM) y reparte el trabajo de refresco entre las otras interrupciones.
* **Teclado, joystick y sonido.** La matriz del CPC se traduce a las semifilas del
  Spectrum, y el Kempston sale del joystick del CPC. Si el juego lee el teclado con
  las interrupciones desactivadas, la matriz se vuelve a leer en cada lectura.
* **Sonido del beeper.** Cada `OUT ($FE)` mueve el volumen del canal A del PSG. Los
  bucles y subrutinas cortas de sonido (un `OUT ($FE),A` con retardos) se copian al
  HAL con el `OUT` cambiado por una espera de la misma duración, y el PSG solo se
  toca cuando cambia el altavoz: así las notas conservan su tono y su duración. La
  rutina BEEPER de la ROM usa el generador de tono del PSG (frecuencia y duración
  exactas). El beeper se imita con el
  volumen del canal A del AY, y el AY de los 128K pasa al PSG con las frecuencias
  reescaladas.
* **ROM.** Las rutinas de la ROM más usadas (CLS, BEEPER, KEY-SCAN, PR-STRING,
  CHAN-OPEN, PRINT por `RST $10` con AT/INK/PAPER…) están emuladas. Si se da la ROM
  real, su fuente se copia al port. Si el juego lee datos de la ROM por su cuenta y
  no hay sitio para copiarlos, la ROM se guarda en el banco extra 5 del 6128 y esas
  lecturas la consultan allí.
* **Snapshots detenidos en la ROM.** Si el snapshot se tomó en el BASIC del cargador
  (p. ej. en un `PAUSE`), con `--rom` se ejecuta hasta que entra en el código del
  juego y se porta desde ahí.
* **Disco.** El DSK lleva un cargador para el CPC 6128 que lee el juego por bloques
  de 16K (y la copia de la ROM, si hace falta), los coloca sin firmware y arranca.

### CPC → Spectrum +2A/+3

El +2A/+3 tiene paginación «especial» con RAM en los 64K. El port la usa con dos
configuraciones:

* **Juego** (`$1FFD=$01`, bancos 0-1-2-3): los 64K del CPC tal cual. El juego corre
  sin mover ni un byte.
* **HAL** (`$1FFD=$07`, bancos 4-7-6-3): el HAL en el banco 6, la pantalla del
  Spectrum en el banco 7 (la pantalla «sombra», que es la que se ve) y el banco 3
  (la pantalla del CPC) común a las dos.

Entre las dos configuraciones hay una **puerta**: los vectores, los manejadores
rápidos y las tablas, copiados en el banco 0 y en el banco 4 en la misma dirección.
Los registros viajan por un **buzón** de 48 bytes en un hueco no visible de la
pantalla del CPC. Un segundo buzón guarda el estado del PPI, del PSG y de la matriz
del teclado.

* **E/S emulada en la puerta.** El PPI, el teclado y el PSG se resuelven sin cambiar
  de banco. El PSG pasa al AY del Spectrum con las frecuencias reescaladas. Solo el
  gate array (modo, paleta) y el CRTC cruzan al HAL.
* **Pantalla.** Cada escritura en la pantalla del CPC se refleja al momento en la del
  Spectrum. Cada 2 bytes del CPC dan 1 byte del Spectrum (256 píxeles de ancho, con
  recorte centrado), en los modos 0, 1 y 2. Los atributos salen de las plumas
  presentes en cada celda: se recalculan primero las filas que han cambiado y,
  poco a poco, todas las demás.
* **Firmware.** El jumpblock (`$BB00-$BDF3`) apunta a una emulación de las rutinas
  más usadas: SCR SET MODE/INK/BORDER, TXT OUTPUT/SET CURSOR/SET PEN, KM TEST
  KEY/READ CHAR/WAIT KEY, MC WAIT FLYBACK, SOUND QUEUE y los eventos de frame. Las
  demás vuelven sin hacer nada y aparecen en el informe.
* **Interrupciones.** Si el juego instala su rutina en `$38`, se redirige al buzón.
  El HAL la llama 6 veces por frame, con la señal VSYNC del PPI en la primera, para
  mantener el ritmo de 300 Hz del CPC.
* **Copias en bloque.** `LDIR`/`LDDR` hacia la pantalla se reflejan de golpe (y
  protegen los buzones si un borrado los pisa).

### Spectrum 128K → CPC con 512K (`--512k`)

* **Memoria.** Los 64K base del CPC llevan la pantalla A + HAL, el banco 5, el banco 2
  y la pantalla B (la pantalla sombra del Spectrum, banco 7). Cada banco *n* del
  Spectrum va al bloque 3 del banco *n* de 64K de la ampliación, y el `OUT` a
  `$7FFD` lo pone en `$C000` con la configuración `$C1+n*8`. El bit 3 de `$7FFD`
  cambia la pantalla visible (registro 12 del CRTC). Las copias del banco 5 en `$4000`
  y en la ampliación se mantienen iguales.
* **Pantalla 1.** Su conversión se ejecuta desde un hueco de la pantalla B con la
  configuración 3, que deja a la vez la pantalla B en `$4000` y el banco 7 en `$C000`.
  El escritor del AY vive en otro hueco de la pantalla B (configuración 0).
* **Pila secuestrada.** Las rachas de `LDI` que copian a pantalla con
  `LD SP,tabla / POP DE / LDI…` (la pila usada como puntero de datos) no pueden
  llamar al HAL con `RST`, porque la dirección de retorno pisaría la tabla. Se
  sustituyen por un bucle en el mismo sitio, con una pila propia en los bytes que
  sobran, que compara y convierte solo los bytes que cambian.
* **E/S directa.** Los `OUT (C),r` que en el análisis siempre van al mismo puerto
  (paginación, registro o dato del AY) usan un manejador directo.
* **Disco.** El cargador lleva además los bancos 0, 1, 3, 4, 6 y 7 en ficheros
  aparte (`X0`…`X7`) y los coloca en la ampliación; el 5 y el 2 los copia de la base.

## Limitaciones conocidas

* **CPC → ZX:** necesita un Spectrum **+2A o +3**, por la paginación especial. Los
  modos de 4 y 16 colores pierden color: cada celda de 8×8 tiene solo tinta y papel.
  No se soportan IM 2 en el CPC ni los RST del firmware de salto lejano (SIDE CALL,
  FAR CALL…), y los juegos que cambian el CRTC a mitad de frame (rasters, scroll por
  hardware) no se verán bien.
* **ZX → CPC:** el DSK necesita un CPC 6128 (el SNA se ha probado como 6128). Los
  juegos de 128K que cambian el banco de `$C000` (como Where Time Stood Still)
  necesitan `--512k` y un CPC con 576K: sin ampliación se rechazan con una
  explicación, porque el 6128 no puede poner sus bancos extra en `$C000` y los 128K
  del juego más la pantalla del CPC no caben. En ese modo la pila del juego debe
  estar por debajo de `$C000`. Las escrituras en pantalla con `PUSH` o las que no se
  ven en el análisis solo las recoge el refresco de fondo.
* **Los dos sentidos:** el código cifrado, los cargadores turbo con protección, las
  escrituras en pantalla con direcciones calculadas que el análisis no llega a
  ejecutar y los efectos que dependen del tiempo exacto (colores por raster, beeper
  multicanal) necesitan intervención manual. El informe los señala cuando los
  detecta.
* Los ports son más lentos que el original cuando el juego escribe mucho en
  pantalla, porque cada byte pasa por el HAL. Por ejemplo, Manic Miner se porta y
  se juega en el CPC (probado en Caprice32, desde el disco), pero su bucle principal
  tarda 1,8 veces más que en el Spectrum (1,45 con `--frameskip 1`); Cookie, en
  cambio, va al 90 %. Where Time Stood Still (128K, `--512k`) se carga desde el disco
  y se juega en Caprice32 con 576K, pero a un cuarto de la velocidad del original:
  su zona de juego hace scroll y en cada frame hay que convertir unos 2.500 bytes.
* El sonido del beeper sale algo más grave (en torno a un 10 %) en los motores que
  hacen la espera con `DJNZ`, porque el CPC tarda 4 µs por vuelta y el Spectrum 3,7.
* Las rutinas de la ROM emuladas (PRINT, CLS, BEEPER, KEY-SCAN) y el AY de los 128K
  solo se ensamblan si el juego las usa, para dejar sitio a los manejadores.
* Si el HAL se queda sin sitio para los manejadores, el portador usa una zona de la
  memoria del juego que no se tocó durante el análisis, y lo avisa en el informe.

## Validación

* Decodificador comparado con `z80dasm` y ensamblador comparado con `pasmo` en todas
  las instrucciones documentadas. La CPU se ha comparado con el emulador de
  referencia del paquete `z80`.
* Los juegos de prueba de `tests/data` (dominio público) se portan en los dos
  sentidos. En el emulador interno, las pantallas del original y del port coinciden
  píxel a píxel.
* Los ports se han probado en emuladores reales: Caprice32 (SNA y DSK en el CPC 6128)
  y Fuse (Z80 en el +3).

## Tests

```sh
cd tools/zxcpc
python3 -m pytest -q
```

Los tests que comparan con `pasmo` o con el paquete `z80`, o que necesitan la ROM
del Spectrum (`ZXCPC_ZX_ROM`, por defecto `/usr/share/spectrum-roms/48.rom`), se
saltan si no están disponibles.

## Estructura

```
zxcpc/
  z80/        decode.py (desensamblador), asm.py (ensamblador), cpu.py (emulador)
  formats/    zx.py (TAP, TZX, Z80, SNA, BASIC), cpc.py (SNA, DSK, CDT, AMSDOS), png.py
  machines/   spectrum.py (48K y +2A/+3), cpc.py (464/6128: gate array, CRTC, PPI, PSG)
  analysis/   dynamic.py (trazador), static.py (puntos calientes), report.py, listing.py
  port/       zx2cpc.py, cpc2zx.py y hal/*.asm (las capas de hardware)
  program.py  carga de juegos de cualquier formato
  cli.py      la orden «zxcpc»
tests/        pruebas y juegos de prueba en ensamblador
```

Licencia MIT.
