# La Atari Jaguar por dentro (y qué hace NeoPlat con ella)

Esto es lo que hay que saber del hardware para entender el código generado, y
las trampas que costaron encontrar.

## La consola en cuatro líneas

| | |
|---|---|
| CPU | Motorola **68000 a 13,3 MHz** — la misma familia que las otras tres |
| Vídeo | **Object Processor**: recorre una lista de objetos en cada línea |
| Color | 256 a la vez de una tabla, o 16 bits directos |
| RAM | 2 MB de DRAM en `$000000` |
| Cartucho | hasta 6 MB, visible en `$800000` |
| Sonido | Jerry: dos DAC de 16 bits que alimenta un DSP propio |

La Jaguar lleva además dos procesadores RISC de 32 bits (el **GPU** en Tom y el
**DSP** en Jerry). NeoPlat **no los usa**: con el 68000 y el Object Processor
sobra para un juego de plataformas, y así no hace falta instalar el SDK de Atari
ni otro ensamblador. Basta un `gcc` de 68000, el mismo de las otras máquinas.

## Cómo dibuja NeoPlat

La Jaguar no tiene planos de tiles ni sprites. Tiene una **lista de objetos** en
RAM que el chip recorre entera en cada línea de barrido, componiendo lo que
encuentra en un buffer de línea. NeoPlat monta esta, de atrás hacia delante:

```
rama       si la línea pasa del final de la pantalla, saltar al STOP
rama       si aún no ha llegado al principio, también
fondo      el mapa de bits del escenario, con el scroll aplicado
actores    un objeto por cada trozo de 16x16 de jugador, enemigo u objeto
marcador   la franja de arriba, encima de todo
STOP
```

Eso cambia el reparto del trabajo respecto a las otras máquinas:

- **El escenario** es un mapa de bits lineal de 704 × 256 píxeles, **un byte por
  píxel**. Se dibuja columna a columna según entra por el borde, igual que en el
  Amiga, pero copiando bytes: sin bitplanes y sin máscaras.
- **El scroll es gratis.** Se mueve la dirección de los datos del objeto (de
  ocho en ocho píxeles, que es lo que permite el campo) y el resto del
  desplazamiento se hace con su posición X.
- **Los actores no se dibujan.** Cada trozo es un objeto más de la lista y lo
  compone el chip, con el color 0 como transparente. No hace falta repintar el
  fondo por detrás, que es lo más caro en el Amiga.

## Formato de los gráficos

**Color (16 bits)**: el reparto es peculiar, `RRRRRBBBBBGGGGGG`. Cinco bits de
rojo arriba, cinco de azul en medio y **seis de verde abajo**. No es RGB565;
está comprobado leyendo el color de fondo en el emulador.

**Dibujos**: 16 × 16 bytes seguidos, un byte por píxel, alineados a 8 porque el
chip los lee de frase en frase. El índice 0 es transparente.

## La lista de objetos

Cada objeto son una o dos "frases" de 64 bits. Lo que más cuesta es que la
dirección del siguiente (el **enlace**) va partida entre las dos mitades:

```
bits 63-43   dirección de los datos (>> 3)
bits 42-24   enlace al siguiente objeto (>> 3)
bits 27-14   altura en líneas
bits 13-3    posición Y, en medias líneas
bits  2-0    tipo (0 mapa de bits, 3 rama, 4 stop)
```

La aritmética para partir el enlace está copiada de `InitLister`, del SDK de
Atari, y comentada en `np_video.c`.

## Tres trampas que cuestan una tarde

Las tres se encontraron a base de arrancar la consola emulada y mirar, y las
tres dejan la pantalla en negro sin decir por qué:

**1. El cartucho no arranca solo.** No hay tabla de vectores: la consola lee la
pila en `cart+$400` y el punto de entrada en `cart+$404`. Si esos ocho bytes
están a cero, salta a la dirección 0 y no pasa nada. Lo pone `hacer_rom.py`.

**2. El chip gasta la lista mientras dibuja.** Según recorre un mapa de bits va
restando de la altura y sumando a la dirección de los datos, así que al acabar
el frame el objeto está consumido. Hay que reescribirlo entero cada vez.

**3. Y hay que reescribirlo en el retrazo, no antes.** Si se toca la lista con
el haz en mitad de la pantalla, el objeto se vuelve a pintar desde arriba a
partir de ahí. Así salía el marcador dos veces, la segunda justo donde había
llegado la CPU. Por eso el motor construye la lista en una copia y la vuelca de
golpe en `np_wait_vblank()`. Hay una prueba que cuenta las filas de texto del
marcador y falla si salen el doble.

**Y una cuarta, del compilador**: ni la lista ni el mapa de bits los lee el
programa — los lee el chip por DMA. Sin `volatile` (o una barrera de memoria)
gcc borra todas las escrituras por inservibles y no se ve nada. Es la misma
trampa en las dos, y no avisa.

## El parallax: otro objeto y ya está

De las cuatro máquinas, la Jaguar es donde el parallax sale más barato. No hay
que redibujar nada por frame: la capa es **otro objeto** de la lista, con su
propio mapa de bits y su propia posición, y el chip lo compone antes que el
escenario. Moverlo es cambiar dos números:

```c
np_objeto(NP_DIR(np_fondo_bitmap) + sy * NP_MAPA_ANCHO + (sx & ~7),
          -(sx & 7), 0, ...);
```

El dibujo de la capa se pinta una sola vez al entrar en el nivel, repetido a lo
ancho de los 704 píxeles del mapa de bits; como el ancho de la capa (256 px)
cabe en el hueco que sobra (704 − 320 = 384), al llegar a su ancho se vuelve al
principio y no se nota el corte.

Para que se vea por detrás, el objeto del escenario lleva **el color 0
transparente**. Eso arregla de paso otra cosa: hasta ahora los huecos del
escenario se veían negros (el color 0 de la tabla) en vez del color de fondo del
nivel, que es lo que hacen las otras tres máquinas. Ahora por ahí se ve el
`BG`, que es justo el `fondo:` del `game.yaml`.

## El mando

Es una matriz: se escribe una **palabra** con la fila que se quiere en
`$F14000` y se lee un **long** de ahí mismo. Activo a nivel bajo.

```
fila $81FE   bit 24 arriba, 25 abajo, 26 izquierda, 27 derecha
             bit 1 botón A, bit 0 PAUSE
fila $81FD   bit 1 botón B
```

El kit usa **PAUSE para empezar la partida** (es el botón central del mando de
Jaguar). En RetroArch cae en el *Select* del mando.

### El segundo mando, que no es el primero desplazado

Con `jugadores: 2` hay que leer el otro puerto, y ahí está la trampa: los dos
comparten el mismo byte de selección de fila —el puerto 1 mira el nibble bajo y
el puerto 2 el alto—, pero **la tabla de filas del puerto 2 es la del 1 con los
bits del revés**. O sea que la fila 0 no se pide con el mismo número:

| | fila 0 | fila 1 |
|---|---|---|
| puerto 1 | nibble `$E` (`$81FE`) | `$D` (`$81FD`) |
| puerto 2 | nibble `$7` (`$817F`) | `$B` (`$81BF`) |

Los nibbles que sobran se dejan a `$F`, que no apunta a ningún mando. Lo demás
sí es el primero desplazado: las direcciones salen cuatro bits más arriba
(28-31) y los botones dos (bit 3 el A, bit 2 PAUSE).

Esto no se adivinó: escribiendo `$81EF` —que es lo que uno esperaría— el
segundo mando no llegaba, y la prueba de emulador
(`tests/test_sistemas.py`, `TestDosJugadores`) lo cazó. Los números salen del
manual técnico de Atari, del apartado del adaptador de cuatro jugadores, que es
donde está la tabla entera de los dieciséis códigos.

## La ROM que se genera

```
build/jaguar/rom/<Juego>.j64    el cartucho, 2 MB
build/jaguar/src/               el motor y tu juego, en C
build/jaguar/jaguar.ld          mapa de memoria del cartucho
build/jaguar/hacer_rom.py       le pone la cabecera con la pila y la entrada
```

Se construye con `gcc-m68k-linux-gnu` y nada más:

```bash
apt install gcc-m68k-linux-gnu
ngplat compilar mijuego --sistema jaguar --make
```

## Probarlo

```bash
make test-emulador-jaguar
```

Virtual Jaguar **no necesita la BIOS de Atari** para los cartuchos (viene
desactivada por defecto), así que esta máquina se comprueba de verdad, igual que
la Mega Drive y el Amiga: se arranca, se mira el título, se pulsa el botón, se
juega y se comprueba que el escenario se mueve.

## El sonido: un programa para el DSP

La Jaguar **no tiene chip de sonido**. Tiene dos DAC de 16 bits (`LTXD` en
`$F1A148` y `RTXD` en `$F1A14C`) y hace falta alguien que les dé una muestra
cada vez que el reloj de audio hace tic, unas veinte mil veces por segundo. El
68000 no puede: la interrupción del reloj de audio (I2S) no le llega a él, le
llega al **DSP** de Jerry. Así que para que la Jaguar suene hay que escribir un
programa para ese procesador, igual que en la Neo Geo hay que escribir uno para
el Z80.

El kit trae el ensamblador (`tools/ngplat/dsp.py`, 300 líneas) y el driver
(`tools/ngplat/jerry.py`, 292 bytes de código máquina). El reparto es:

| | |
|---|---|
| el **DSP** | genera las ondas: tres cuadradas y un ruido, sumadas, una muestra por interrupción |
| el **68000** | lo mismo que en el Amiga y la Mega Drive: lleva las secuencias del `game.yaml` y, cada frame, deja en la RAM del DSP qué nota toca cada canal |

Se hablan por un bloque de siete palabras en la RAM del DSP: `paso0 paso1 paso2
amplitud0 amplitud1 amplitud2 amplitud_ruido`.

**Cómo suena un canal.** Un acumulador de fase de 32 bits al que se le suma un
`paso` por muestra; el bit de arriba dice si la cuadrada está arriba o abajo. Es
la forma más barata de hacer una cuadrada exacta, y da la misma nota que el SSG
de la Neo Geo o el PSG de la Mega Drive:

    paso = frecuencia * 2^32 / muestras_por_segundo

Con `SCLK = 19` salen 26.590.906 / (64 × 20) = **20.774 muestras por segundo**.
El error de afinación es menor del 0,05% (menos de un cente).

**Lo que hay que saber del juego de instrucciones**, y que cuesta encontrar:

- cada instrucción es **una palabra de 16 bits**: seis de código, cinco del
  primer operando y cinco del segundo, que casi siempre es el destino;
- `movei` lleva detrás la constante de 32 bits **con la palabra baja primero**;
- `shlq` es la **única** instrucción cuyo inmediato se guarda como `32 - n`;
- `jump` y `jr` tienen **ranura de retardo**: la instrucción de detrás se
  ejecuta antes de saltar;
- al entrar en la interrupción el DSP fuerza el banco 0 de registros, mete la
  dirección de vuelta en la pila (`r31`) y pone `IMASK`. Para volver hay que
  sacarla, **sumarle 2** y escribir `D_FLAGS` con `IMASK` a cero y el bit de
  limpiar el aviso de I2S (`$420`), en la ranura de retardo del `jump`.

El vector de la interrupción I2S es el segundo: `$F1B010`. Los vectores ocupan
16 bytes cada uno y sólo se usa ése, así que el manejador empieza ahí y sigue de
largo.

**Cómo se depuró.** A la primera no sonaba nada, y con el emulador no se ve
dentro del DSP. Se fue por partes, cada una una ROM: (1) el 68000 escribiendo el
DAC directamente → sonaba, así que `SCLK` y `SMODE` estaban bien; (2) el DSP
escribiendo el DAC desde su bucle principal → sonaba, así que el DSP arrancaba;
(3) un manejador de I2S que sólo cambiaba el signo → sonaba, así que la
interrupción y la vuelta estaban bien; (4) el manejador entero con constantes →
sonaba. El fallo estaba en la prueba: el botón de empezar en la Jaguar es
`SELECT`, no `A`, y la partida nunca había arrancado.

## Lo que aún no hace

- **Muestras digitales.** Los DAC son de 16 bits y darían para voces y
  percusión de verdad; de momento son ondas cuadradas y ruido, como en las otras
  tres máquinas.
- **Más de una capa de parallax.** Se dibuja una; cabrían más, porque cada capa
  es sólo un objeto más de la lista.
- **Color directo.** Se usan los 256 de la tabla. La Jaguar puede hacer 16 bits
  por píxel, y sería la única de las cuatro donde los PNG no habría que
  recortarlos: se verían tal cual.
- **El GPU y el DSP** están sin tocar. Para un juego de plataformas no hacen
  falta, pero ahí están.
