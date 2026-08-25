# El Amiga por dentro (y qué hace NeoPlat con él)

Esto es lo que hay que saber del hardware para entender el código generado, y
lo primero que hay que mirar si algo se ve raro en el emulador.

## El ordenador en cuatro líneas

| | |
|---|---|
| CPU | Motorola 68000 a 7,09 MHz |
| RAM chip | 512 KB en un A500 (es la única que ven los chips) |
| Vídeo | Denise: **bitplanes**, hasta 6 (64 colores) |
| Copper | un coprocesador que cambia registros en una línea concreta |
| Blitter | copia y combina memoria a toda velocidad, con máscara y desplazamiento |
| Color | 4096, **32 en pantalla** con 5 bitplanes |
| Sonido | Paula: 4 canales de sonido digital por DMA |

Es la más distinta de las tres máquinas: **no tiene tiles ni sprites de
hardware suficientes** para un juego así. Tiene un mapa de bits que se puede
mover entero por hardware y un blitter que dibuja encima.

## Cómo dibuja NeoPlat

```
mapa de bits   704 × 256 píxeles, 5 bitplanes entrelazados (RAM chip)
scroll         por hardware: se mueven los punteros y BPLCON1 hace el resto
escenario      solo se dibuja la columna de tiles que entra
actores        con el blitter, recortados por su máscara
marcador       su propia franja de 320 × 24, enganchada por el copper
```

El mapa de bits es **el doble de ancho que la pantalla** a propósito. Según
avanza la cámara se va dibujando la columna de 16 píxeles que entra por la
derecha; cuando la cámara se acerca al final del mapa se vuelve a empezar por
la izquierda repintando lo que se ve (cuesta un frame, y pasa cada 350 píxeles
de scroll).

**Entrelazado** quiere decir que cada fila lleva las cinco palabras de los
cinco bitplanes seguidas, en vez de tener los cinco planos uno detrás de otro.
Así el blitter dibuja un tile entero de una sola pasada. Por eso el módulo de
los bitplanes es `NP_PASO_FILA - 40` y no `NP_BYTES_FILA - 40`.

Antes de dibujar a los actores se **repinta el fondo** donde estaban en el
frame anterior (`np_rastros`), que es lo que evita que dejen rastro.

## El marcador y el copper

El Amiga no tiene un plano de texto que se pueda poner encima, así que el
marcador vive en su propio mapa de bits de 320 × 24 y es el copper el que
cambia los punteros de los bitplanes al llegar a la línea 24:

```
línea $2C   empieza lo visible; punteros -> np_hud_bitmap
línea $44   WAIT del copper; punteros -> np_bitmap + (cam_y + 24) filas
línea $10C  se acaba la pantalla
```

De ahí para arriba se ve el marcador y de ahí para abajo, el juego. Como los
punteros del juego arrancan 24 filas más abajo, el efecto es el mismo que un
marcador superpuesto: la fila N de la pantalla enseña la fila `cam_y + N` del
mundo.

El color 0 también vive en la lista del copper, y el motor lo cambia al empezar
cada nivel con el `fondo:` que le hayas puesto.

## El blitter

Dos usos, los dos en `np_video.c`:

**Copiar un tile del escenario** (`np_blit_tile`): A → D, sin desplazar.

```
BLTCON0 = $09F0     usar A y D, minterm $F0 (D = A)
BLTSIZE = 80 filas × 1 palabra    (16 píxeles × 5 planos)
BLTDMOD = 88 - 2                  saltar al siguiente plano del mapa de bits
```

**Dibujar un actor recortado** (`np_blit_bob`): el clásico *cookie cut*.

```
BLTCON0 = $0FCA | desplazamiento   usar A, B, C y D
                                   minterm $CA: D = (A y B) o (no A y C)
BLTSIZE = 80 filas × 2 palabras    dos, porque al desplazar se sale de una
BLTALWM = $0000                    la palabra de más se anula
BLTAMOD = BLTBMOD = -2             leen dos palabras por fila y avanzan una
```

A es la máscara, B el dibujo y C el fondo que ya había: donde la máscara vale 1
se ve el dibujo y donde vale 0 se ve el fondo. Por eso los dibujos se guardan
**con su máscara al lado**.

La máscara se guarda **repetida cinco veces por fila**, una por bitplane. Suena
a desperdicio (160 bytes en vez de 32) pero es lo que hace que la máscara avance
al mismo paso que el dibujo entrelazado y que el blitter pueda hacer los cinco
planos de una sola pasada, en vez de cinco.

## Colores

El color del Amiga es una palabra `0000 RRRR GGGG BBBB`: **cuatro bits por
canal**. Está en `gfx_amiga.amiga_color()`.

Solo hay **una paleta de 32 colores** para todo lo que se ve a la vez, así que
`fusionar_paletas()` mete todas las del proyecto en ella reutilizando los
colores repetidos. El 0 es el fondo y el 31 se reserva para el marcador, así
que a los dibujos les quedan 31.

Las capas de parallax **todavía no se dibujan** en Amiga (haría falta modo
*dual playfield*, que dejaría el juego en 8 colores), así que sus colores ni se
cuentan ni gastan memoria.

## Cómo suena

Paula tiene cuatro canales que leen una onda de la RAM chip por DMA y la
repiten sin parar. Para dar una nota no hace falta una muestra larga: basta una
**onda cuadrada de dos bytes** (+64 y −64) y cambiarle el periodo, que es justo
lo que hacen el SSG de la Neo Geo y el PSG de la Mega Drive. Así las tres
máquinas tocan exactamente las mismas notas.

```
canal 0 -> melodía     canal 1 -> acompañamiento
canal 2 -> efectos     canal 3 -> ruido (percusión, con una tabla de 16 bytes)
```

El periodo lo calcula el compilador con `periodo_paula(hz, muestras=2)`:
`3546895 / (2 · hercios)`, con un mínimo de 124 (por debajo la DMA no da
abasto). Con dos muestras entran de sobra las notas de 30 a 8000 Hz que acepta
el kit. El volumen de Paula va de 0 a 64; el del kit, de 0 a 15.

## Cómo arranca un ejecutable de AmigaDOS

Aquí no hay direcciones fijas: un ejecutable es una lista de trozos (*hunks*)
que el sistema carga donde le cabe, más una tabla que dice qué palabras largas
hay que corregir con la dirección real. NeoPlat genera dos hunks:

```
HUNK_HEADER    cuántos hunks hay y cuánto ocupa cada uno (los dos, HUNKF_CHIP)
HUNK_CODE      código, constantes y variables con valor inicial
HUNK_RELOC32   qué corregir, y de qué hunk es cada dirección
HUNK_END
HUNK_BSS       lo que hay que reservar (el mapa de bits) — llega puesto a cero
HUNK_END
```

Los dos hunks se piden en **RAM chip**, que es la única a la que llegan el
copper, el blitter y Paula.

Esto lo hace `tools/ngplat/hunk.py` (que se copia dentro del proyecto como
`hacer_ejecutable.py` y no necesita nada instalado): lee las secciones del ELF
que saca el enlazador, coge las relocalizaciones que deja `ld --emit-relocs` y
separa las que apuntan al código de las que apuntan al BSS. Para poder
distinguirlas, `amiga.ld` enlaza las dos zonas en direcciones muy separadas
(`$00000000` y `$40000000`): basta mirar el valor de cada referencia.

La ejecución empieza en el **primer byte del primer hunk**, y de eso se encarga
el script del enlazador: ahí va `_start`, que llama a `main()` y se queda en un
bucle. El juego se queda con la máquina entera (apaga las interrupciones y la
DMA en `np_amiga_init`) y no la devuelve: se sale apagando o reiniciando, como
los juegos de la época.

## Si algo se ve raro

- **Gráficos revueltos o con los colores mezclados**: el orden de los planos en
  `gfx_amiga.codificar_tile()` (plano 0 = bit 0 del índice de color).
- **Los actores dejan rastro o salen recortados de más**: la máscara; mira que
  `BLTAMOD` y `BLTBMOD` sigan valiendo −2 y que `BLTALWM` sea 0.
- **La pantalla tiembla al hacer scroll**: `BPLCON1` lleva los cuatro bits
  bajos de `cam_x` para los dos playfields (los mismos cuatro bits, dos veces).
- **No arranca**: comprueba con un volcador de hunks que el primer hunk empieza
  con el `jsr` de `_start` y que los dos hunks van marcados como CHIP.
