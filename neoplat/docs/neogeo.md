# La Neo Geo por dentro (y qué hace NeoPlat con ella)

Esto es lo que hay que saber del hardware para entender el código generado, y
lo primero que hay que mirar si algo se ve raro en el emulador.

## La consola en cuatro líneas

| | |
|---|---|
| CPU | Motorola 68000 a 12 MHz (sin coma flotante, sin caché) |
| RAM de trabajo | 64 KB |
| Pantalla | 320 × 224, 60 fps |
| Sprites | 381 sprites de 16 píxeles de ancho y hasta 32 tiles de alto |
| Plano fix | 40 × 32 tiles de 8x8, sin scroll (para el marcador) |
| Color | 65536 colores, 4096 en pantalla, 16 por paleta |
| Sonido | Z80 + YM2610 (NeoPlat aún no lo usa) |

**No hay plano de fondo con scroll.** El fondo se dibuja con sprites: es lo que
hacen los juegos comerciales y lo que hace NeoPlat.

## Cómo dibuja NeoPlat

`engine/neogeo/np_video.c` reparte los sprites así (con dos capas de parallax):

```
sprite   1..96    jugador, enemigos y objetos      (delante)
sprite  97..117   escenario: 21 columnas de 15 tiles
sprite 118..138   capa de parallax cercana
sprite 139..159   capa de parallax lejana          (detrás)
```

El número de sprite decide quién tapa a quién. El reparto de arriba supone que
**el sprite 1 se dibuja delante**, que es lo que documenta la escena Neo Geo.
Si al probar la ROM el fondo tapa al jugador, cambia `NP_SPRITE_FRONT_FIRST` a
0 en `np_video.h`: se invierte todo el reparto de una vez y no hay que tocar
nada más.

Cada capa de parallax es otro juego de 21 columnas cuyo tilemap se lee de la
imagen de la capa, desplazado una fracción de la cámara. Los tilemaps solo se
reescriben cuando la capa cruza a otro tile.

Cada columna de fondo es un sprite con su propio tilemap. Cuando la cámara se
mueve dentro del mismo tile solo se actualizan las posiciones (21 escrituras);
cuando cruza a otro tile se reescriben los tilemaps. Así el scroll cuesta poco
tiempo de CPU.

El marcador va en el plano fix, que no se mueve con la cámara.

## Formato de los gráficos

Lo implementa `tools/ngplat/gfx.py`. Cada función tiene su inversa y los tests
comprueban que codificar y decodificar devuelve la imagen original.

### Color (16 bits)

```
bit  15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
      D R0 G0 B0 [ R4..R1 ] [ G4..G1 ] [ B4..B1 ]
```

Cada canal tiene 5 bits: los 4 altos van en su nibble y el bit menos
significativo va a los bits 14/13/12. El bit 15 es el bit "dark".

El color 0 de cada paleta es siempre transparente.

### Tile de sprite (ROM C): 16x16, 4 bits por píxel

Un tile ocupa 128 bytes repartidos entre dos ROMs: **C1** lleva los planos de
bits 0 y 1, **C2** los planos 2 y 3. Dentro de cada ROM, los 64 bytes de un
tile van así:

```
bytes  0..15   plano bajo,  mitad derecha  (x = 8..15), filas 0..15
bytes 16..31   plano bajo,  mitad izquierda (x = 0..7)
bytes 32..47   plano alto,  mitad derecha
bytes 48..63   plano alto,  mitad izquierda
```

En cada byte, el **bit 7 es el píxel de más a la izquierda** del grupo de 8.

### Tile del plano fix (ROM S): 8x8, 4 bits por píxel

32 bytes por tile, 4 bytes por fila, dos píxeles por byte (nibble bajo primero).
Las cuatro parejas de columnas se guardan en el orden **3, 0, 1, 2**.

> **Si los gráficos salen revueltos en el emulador**, es aquí donde hay que
> mirar: `encode_sprite_tile()` y `encode_fix_tile()` en `tools/ngplat/gfx.py`.
> Están escritas según la documentación de hardware de la escena Neo Geo, pero
> **no las he podido comprobar contra un emulador real** en el entorno donde se
> escribió el kit. Alternativa: si tienes las herramientas de ngdevkit
> (`tiletool`), puedes convertir los PNG con ellas y sustituir los `.c1/.c2/.s1`
> generados.

## Registros que usa el motor

```c
0x300000  mando del jugador 1 (activo a nivel bajo)
0x300001  watchdog: hay que escribirlo cada frame o la placa se reinicia
0x380000  START y SELECT
0x3C0000  dirección de VRAM
0x3C0002  lectura/escritura de VRAM (auto-incrementa)
0x3C0004  incremento tras cada acceso
0x3C0006  modo del LSPC / contador de línea (para esperar al vblank)
0x400000  RAM de paletas (256 paletas x 16 colores)
0x401FFE  color de fondo (backdrop)
```

Mapa de la VRAM:

```
0x0000   SCB1  tilemaps de sprite (64 words por sprite: tile, atributos)
0x7000   plano fix, 40x32, direccionado por columnas: 0x7000 + col*32 + fila
0x8000   SCB2  zoom
0x8200   SCB3  posición Y (496 - y), encadenado y altura
0x8400   SCB4  posición X
```

El motor no usa la BIOS ni las interrupciones: espera al retrazo vertical
leyendo el contador de línea. Si prefieres usar la interrupción de ngdevkit,
sustituye `np_wait_vblank()` en `np_video.c` por `ng_wait_vblank()`; el resto
del motor no cambia.

## El sonido: el Z80 y el YM2610

El chip de sonido no cuelga del 68000, sino de un Z80 con su propia ROM (la
M1). El juego manda ordenes de un byte por el puerto `$320000`; eso dispara una
NMI en el Z80, que lee el comando por su puerto 0.

`ngplat` genera ese driver a partir del `game.yaml` (`tools/ngplat/m1.py`), lo
ensambla con su propio ensamblador de Z80 (`tools/ngplat/z80.py`) y deja el
fuente comentado en `build/src/sonido.z80` por si quieres mirarlo.

Formato del byte de orden:

```
bit 6      alternancia (permite repetir el mismo sonido dos veces seguidas)
bits 0-5   $01..$2F efecto, $30..$3E musica, $3F parar la musica
```

El driver usa los tres canales de onda cuadrada (SSG) del YM2610:

```
canal A (registros $00/$01, volumen $08)   primera pista de la musica
canal B (registros $02/$03, volumen $09)   segunda pista
canal C (registros $04/$05, volumen $0A)   efectos, y ruido para los golpes
```

El periodo de una nota es `4.000.000 / (16 * frecuencia)` y el compas lo marca
el temporizador B del YM2610, programado a unos 60 Hz para que la musica avance
al ritmo del juego.

Las pruebas ejecutan este driver en un emulador de Z80 (`tests/z80sim.py`) y
comprueban que escribe los periodos correctos, pero **no se ha probado en
hardware**. Las muestras digitales (ROM V1) todavia no se usan.

## La ROM que se genera

```
build/rom/202-p1.p1   programa (68000), lo genera make
build/rom/202-c1.c1   gráficos, planos 0 y 1
build/rom/202-c2.c2   gráficos, planos 2 y 3
build/rom/202-s1.s1   plano fix (la fuente del marcador)
build/rom/202-m1.m1   driver de sonido del Z80, con tu musica y tus efectos
build/rom/202-v1.v1   muestras digitales (aun sin usar)
```

El identificador `202` es el del romset `puzzledp`, que es el que usa el
emulador de ngdevkit para el homebrew. Se puede cambiar con
`ngplat compilar --rom-id`.

## Una trampa del 68000 con la que se cuelga el juego

Con `-Os`, ante dos escrituras de un byte seguidas (`w->keys = 0;
w->entity_count = 0;`) gcc emite un `clr.w`, una sola escritura de dos bytes.
Si el par cae en una **dirección impar**, el 68000 se para con un *address
error*: no puede leer ni escribir palabras en direcciones impares.

Le pasa a cualquier compilador de 68000, ngdevkit incluido, así que el kit
compila con **`-fno-store-merging`**. Las pruebas revisan el código máquina de
las tres máquinas y fallan si aparece un solo acceso de ese tipo.

Se descubrió arrancando la ROM de Mega Drive en un emulador (se quedaba
congelada nada más cargar el nivel); la de Neo Geo tenía exactamente el mismo
`clr.w %a0@(2109)`.

## Instalar ngdevkit

```bash
# macOS
brew tap dciabrin/ngdevkit && brew install ngdevkit ngdevkit-gngeo

# Linux / otros: ver https://github.com/dciabrin/ngdevkit
```

Después, `ngplat compilar --make` construye la ROM directamente.

## Lo que aún no se ha podido comprobar

Las otras dos máquinas se arrancan en un emulador dentro de las pruebas
(`make test-emulador`). La Neo Geo no: emularla necesita la BIOS de la consola,
que es propietaria y no se puede distribuir. Lo que sí se comprueba es el
código máquina: que no lleve instrucciones que el 68000 no tiene ni accesos a
direcciones impares, que es lo que colgaba a las otras dos.

## Rendimiento

Un frame son unos 200.000 ciclos de 68000. El reparto aproximado del motor:

- simulación (jugador + 64 entidades): unos 20.000 ciclos
- reescritura del fondo al cruzar un tile: unos 15.000 ciclos
- sprites de actores: unos 300 ciclos por sprite

Es decir, sobra tiempo. Los sitios donde tener cuidado si amplías el motor:
multiplicaciones de 32 bits (lentas en 68000), divisiones (aún más) y escrituras
a VRAM fuera del vblank.
