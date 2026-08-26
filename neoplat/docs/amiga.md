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

Cuántos colores hay depende del modo (`amiga:` en el `game.yaml`):

| | `32colores` | `8colores` |
|---|---|---|
| Bitplanes | 5, un solo plano | 6, repartidos 3 y 3 |
| Colores del juego | 31 (el 0 es el fondo, el 31 el marcador) | 7 (el 0 transparente, el 7 el marcador) |
| Colores del parallax | — | 7 (registros 9 a 15) |
| Parallax | no se dibuja | sí, por hardware |

En los dos casos `fusionar_paletas()` mete todas las paletas del proyecto en
una sola reutilizando los colores repetidos. La diferencia es qué pasa cuando
no caben: con 32 da un error (nunca ha pasado con dibujos normales), y con 8
**no puede darlo**, porque no hay dibujo de verdad que quepa en siete colores.
Ahí se hace lo de siempre en estos casos: **corte por la mediana**. Se cuenta
cuántos píxeles usa cada color, se parte la nube de colores en siete cajas
(siempre por el canal que más varía y por la mitad del peso, no del número de
colores) y cada caja se queda con su color medio; después cada color original
se cambia por el más parecido de los siete. Es determinista, y `ngplat
compilar` avisa de cuántos colores ha tenido que aproximar.

## Que quepa en un frame

El Amiga PAL da **50 frames por segundo, y cada frame son 312 líneas de
barrido**: si lo que hay que hacer no cabe en 312, se pierde un frame y el
juego va a la mitad de velocidad. Con cinco bitplanes en baja resolución el
DMA de vídeo se lleva una buena parte de los accesos a memoria chip, así que
hay menos margen del que parece.

Medido en un A500 emulado, jugando (líneas por frame):

| | al principio | ahora |
|---|---|---|
| simular (`np_world_step`) | 76 | 76 |
| repintar el fondo de los actores | 70 | 34 |
| dibujar los actores | 33 | 33 |
| marcador | **184** | 2 |
| escenario, scroll, sonido y mando | 8 | 8 |
| **total** | **~370** | **~153** |
| **velocidad** | **25 fps** | **49 fps** |

Las dos cosas que lo arreglaron:

- **El marcador sólo repinta lo que cambia.** Escribir en el mapa de bits lo
  hace la CPU byte a byte (8 filas × 5 bitplanes por carácter), y repintar
  `SCORE 000000 … LIVES 3` entero costaba más de la mitad de un frame, 50 veces
  por segundo, para dejarlo igual. Ahora las palabras fijas se escriben una vez
  y cada número sólo cuando cambia: en un frame normal no se escribe nada.
- **Un tile del fondo se repinta una sola vez.** Los actores van juntos (las
  monedas, de tres en tres) y sus rectángulos comparten tiles; un bit por tile
  del mapa de bits basta para no repetir el trabajo. De paso se corrigió un
  `+1` que repintaba una columna y una fila de tiles que el actor no tocaba.

### Lo que cuesta cada cosa

Medido dentro del A500 emulado, contando líneas de barrido con un reloj que
acumula (el contador del hardware se pone a cero en cada frame, así que
restarlo a pelo da números al revés en cuanto la medida cruza un frame):

| | líneas |
|---|---|
| un tile opaco (`np_blit_tile`, 16×16, 5 planos) | **2,20** |
| un tile recortado por máscara (`np_blit_bob`) | **4,07** |
| repintar la pantalla entera, 21 × 15 tiles | **950** |
| lo mismo pidiendo los tiles de columna en columna | **683** |
| un frame de juego, corriendo | **122** de media, **272** el peor |
| **lo que da la máquina** | **313** |

Dos cosas se leen ahí:

- Un blit con máscara cuesta **el doble** que uno opaco: lee tres sitios
  (máscara, dibujo y fondo) y escribe uno.
- De las 950 líneas de repintar la pantalla, **267 no son blitter**: son las
  multiplicaciones de 32 bits de `np_tile_gfx_at()`, una por tile, que en un
  68000 se hacen en software. Pidiendo la columna de una vez con
  `np_tile_gfx_column()` bajan a 683, un **28% menos**. Es la misma trampa que
  se encontró en la Neo Geo.

### Por qué el parallax no se dibuja con el blitter

La pregunta natural es: si el fondo ya se dibuja con el blitter, ¿por qué no
dibujar también las capas de parallax y quedarse siempre con 32 colores?
Porque no cabe, y por mucho:

Las dos capas del ejemplo ocupan 21 columnas × 10 filas de tiles = **210 tiles
con máscara** por frame, porque se mueven a otra velocidad que el scroll por
hardware y hay que redibujarlas enteras. A 4,07 líneas cada uno son **855
líneas**. Y encima hay que repintar los tiles del escenario que caen sobre esa
banda: 210 más, opacos, **456 líneas**.

**1.311 líneas de parallax sobre un presupuesto de 313.** Con las 122 que ya
gasta el juego, el frame saldría por unas 1.430: **4,6 frames**, o sea unos
11 fps en vez de 50.

Y no es cuestión de afinar el código: el suelo es el DMA. 210 tiles × 16 filas
× 5 planos × 4 accesos son 67.200 accesos de blitter, y medido el blitter da
unos 79 accesos por línea con la pantalla encendida. Son 850 líneas hagas lo
que hagas.

Con el hueco que hay de verdad (313 − 272 del peor frame ≈ 40 líneas, o unas
190 si sólo miras la media) caben **entre 10 y 46 tiles con máscara por
frame**: una tira de dos filas de alto. No da para una capa de fondo.

### El parallax de verdad: dual playfield

Como el blitter no puede, el parallax lo hace el **hardware de vídeo**, que
sale gratis. El OCS sabe partir los seis bitplanes en dos planos independientes
de tres (`BPLCON0` bit 10, `DBLPF`): los impares (BPL1, BPL3, BPL5) forman el
plano de delante y los pares (BPL2, BPL4, BPL6) el de detrás. Cada uno tiene:

- **su propio scroll fino**, en `BPLCON1`: los bits 0-3 mueven los planos
  impares y los 4-7 los pares. Por eso en el modo de 32 colores hay que poner
  el mismo valor en los dos nibbles, y aquí no;
- **su propio módulo**, `BPL1MOD` para los impares y `BPL2MOD` para los pares,
  lo que permite que los dos mapas de bits tengan anchos distintos;
- **sus propios punteros**, así que el scroll grueso también es independiente.

En NeoPlat el plano de delante es el juego (colores 0-7) y el de detrás el
parallax (colores 8-15). El plano de detrás se pinta **una sola vez al entrar
en el nivel**, repitiendo el dibujo de la capa a lo ancho de todo el mapa de
bits; a partir de ahí moverlo cuesta escribir cuatro palabras en la lista del
copper: `np_mover_fondo()` pone el scroll grueso en los punteros y devuelve los
cuatro bits del fino. Cero blits por frame, cero líneas de presupuesto.

El precio son los colores (7 y 7 en vez de 31) y **una sola capa**: si el nivel
tiene varias, se dibuja la primera y `ngplat` avisa.

### Cómo medirlo

El reloj del Amiga para esto es el propio haz de la pantalla: `VPOSR` y
`VHPOSR` dicen por qué línea va. Leyendo la línea antes y después de cada parte
sale lo que cuesta, y las cuentas salen en la misma unidad que el presupuesto
(312 líneas). Dos avisos:

- el contador vuelve a cero en cada frame, así que **algo que dure más de 312
  líneas se mide de menos**: si los números no cuadran, es eso;
- para medir una función sola, llamarla 100 veces seguidas y dividir da una
  cifra mucho más limpia que medirla una vez.

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

Las pruebas escuchan lo que sale de Paula en el A500 emulado y comprueban que
son las notas del `game.yaml`, una a una: ver [docs/sonido.md](sonido.md).

## El disquete (.adf)

Un `.adf` es la copia byte a byte de un disquete de Amiga: 80 cilindros × 2
caras × 11 sectores × 512 bytes = **901120 bytes**. Es lo que comen los
emuladores (FS-UAE, WinUAE, Amiberry), los Gotek y los cargadores de ADF de un
Amiga de verdad. `tools/ngplat/adf.py` lo monta entero, sin nada instalado:

```
bloques 0-1    bootblock: "DOS\0", su suma de control y el código que arranca
               AmigaDOS (busca dos.library en la ROM y le pasa el control)
bloque 880     raíz del disco: nombre del volumen, tabla hash y dónde está el bitmap
bloque 881     bitmap: un bit por bloque, a 1 si está libre
el resto       las cabeceras y los datos de los ficheros
```

Dentro va el ejecutable y un `s/startup-sequence` de una línea que lo lanza.
Al encender, el Amiga lee el bootblock, arranca AmigaDOS, monta el disco,
ejecuta el startup-sequence y ya estás jugando: **no hace falta Workbench**.

### El bootblock tiene que decir que el disco arranca solo

El código del bootblock hace dos cosas, y la primera parece cosmética pero no
lo es:

1. abre `expansion.library` y le pone el bit **`EBB_SILENTSTART`** (el 6 de
   `eb_Flags`), que le dice al sistema que el disquete arranca por su cuenta;
2. busca `dos.library` en la ROM y le pasa el control.

Sin el primer paso —el bootblock corto de AmigaDOS 1.x, que es sólo el segundo—
el sistema arranca en modo normal y **su shell no llega a ejecutar el juego**:
se queda en `BosqueMagico: file is not executable`. Comprobado en un Amiga
emulado, y comprobado también que es ese bit exacto: poniendo el 5 o el 7 en
vez del 6, no arranca. Es la diferencia entre que el disquete funcione y que
no.

Se usa **OFS** (*Old File System*, `DOS\0`) a propósito, no FFS: es el único
que arranca en un Kickstart 1.3 sin meter el sistema de ficheros en el propio
disco. Gasta 24 bytes de cabecera en cada bloque, así que caben 488 bytes de
datos por bloque en vez de 512; a cambio arranca en cualquier Amiga.

Tres detalles que hay que hacer bien o el Amiga rechaza el disco:

- **La suma del bootblock** es distinta a las demás: suma con acarreo de sus
  1024 bytes, invertida. La de los demás bloques es la suma de las 128 palabras
  largas cambiada de signo, de modo que el bloque entero sume cero.
- **La tabla de bloques de datos** de un fichero se rellena **del final hacia el
  principio**. Si el fichero pasa de 72 bloques (35 KB), los siguientes van en
  *bloques de extensión* encadenados.
- **Los nombres se guardan en una tabla hash** de 72 entradas
  (`hash = (hash · 13 + letra) & 0x7FF`), con una cadena para las colisiones.

El disco sale siempre igual byte a byte (las fechas son fijas), así que dos
compilaciones del mismo juego dan el mismo `.adf`.

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
- **El emulador dice que el disquete no es de sistema**: es el bootblock. Con
  `xdftool disco.adf list` (del paquete `amitools`) se ve si el disco se lee y
  qué lleva dentro.
- **"file is not executable"**: el sistema de ficheros está bien y el fichero se
  encuentra; lo que falta es el `EBB_SILENTSTART` del bootblock (ver arriba).
- **Para ver qué pasa por dentro**: `make test-emulador-amiga` arranca el
  disquete en un A500 emulado y deja capturas. Para depurar el juego, escribe
  marcas en una dirección de memoria chip que no uses
  (`*(volatile uint16_t *)0x180 = n;`) y léelas desde el emulador: tras el
  takeover esa zona es tuya.
