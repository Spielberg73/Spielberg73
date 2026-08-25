# La Mega Drive por dentro (y qué hace NeoPlat con ella)

Esto es lo que hay que saber del hardware para entender el código generado, y
lo primero que hay que mirar si algo se ve raro en el emulador.

## La consola en cuatro líneas

| | |
|---|---|
| CPU | Motorola 68000 a 7,67 MHz |
| RAM de trabajo | 64 KB, en `$FF0000`–`$FFFFFF` |
| Vídeo | VDP con 64 KB de VRAM propia |
| Pantalla | 320 × 224, 60 fps (50 en PAL) |
| Planos | A y B, de 64 × 32 celdas, con scroll por hardware |
| Plano ventana | tapa al plano A donde se le diga y **no** se mueve con el scroll |
| Sprites | 80 en pantalla, 20 por línea |
| Color | 512 colores, **64 en pantalla**: 4 paletas de 16 |
| Sonido | YM2612 (FM, lo lleva un Z80) + PSG SN76489 |

Comparada con la Neo Geo se lo pone más fácil al motor en unas cosas y más
difícil en otras:

- **a favor**: hay planos de fondo de verdad, así que el escenario y el
  parallax no gastan sprites, y el PSG lo puede escribir el propio 68000 sin
  necesitar código de Z80;
- **en contra**: solo hay 4 paletas de 16 colores para todo el juego, y los
  planos son de 64 × 32 celdas (512 × 512 píxeles), así que el escenario se va
  reescribiendo por columnas según avanza la cámara.

## Cómo dibuja NeoPlat

`engine/megadrive/np_video.c` reparte la pantalla así:

```
plano ventana   el marcador (3 filas de arriba), fijo
sprites         jugador, enemigos y objetos
plano A         el escenario, con scroll
plano B         la capa de parallax, con su propia velocidad de scroll
color 0         el fondo del nivel
```

El escenario no cabe entero en el plano A: un nivel puede ser de 200 casillas
de largo y el plano solo tiene 64 celdas. Lo que hace el motor es dibujar
únicamente la columna que entra por el borde, y como el plano se repite cada 64
celdas (`& 63`), la columna nueva pisa la que ya salió por el otro lado. Cada
tile del juego es de 16 × 16 y ocupa cuatro celdas de 8 × 8 del VDP.

El scroll es por hardware: dos palabras en la tabla de scroll horizontal y dos
en la VSRAM. El plano B las lleva multiplicadas por la velocidad de la capa.

## Reparto de la VRAM

```
$0000   tiles del juego (los que quepan hasta $B000)
$B000   tabla del plano ventana   (64 × 32 celdas)
$BC00   tabla de sprites          (80 entradas)
$C000   tabla del plano A
$E000   tabla del plano B
$F400   tabla de scroll horizontal
```

Cabe algo menos de 1408 tiles de 8 × 8. Si te pasas, `ngplat comprobar` te lo
dice antes de compilar.

## Colores

El color del VDP es una palabra `0000 BBB0 GGG0 RRR0`: **tres bits por canal**
y en orden BGR, no RGB. Está en `gfx_md.md_color()`.

Como solo hay cuatro paletas, `gfx_md.repartir_paletas()` funde las del
proyecto: mete la de los tiles, la de cada actor, la de cada capa y la del
marcador en cuatro paletas de 15 colores (el 0 es transparente), reutilizando
los colores repetidos. Si no caben, avisa con el nombre de la que sobra.

El color 0 de la primera paleta es el **fondo de la pantalla**, y el motor lo
cambia al empezar cada nivel con el `fondo:` que le hayas puesto.

## Cómo suena

La Mega Drive tiene dos chips: el YM2612 (FM), que en la práctica maneja el
Z80, y el PSG SN76489, con tres canales de onda cuadrada y uno de ruido. El PSG
lo escribe el 68000 directamente en `$C00011`, así que NeoPlat lo usa para
tocar las mismas notas que en la Neo Geo sin necesitar nada de Z80:

```
canal 0 -> melodía     canal 1 -> acompañamiento
canal 2 -> efectos     canal 3 -> ruido (percusión)
```

Escribir en el PSG es mandar bytes:

```
latch:  1 cc t dddd    cc = canal, t = 1 volumen / 0 tono, dddd = 4 bits bajos
dato:   0 0 dddddd     los 6 bits altos del tono
```

El volumen es **atenuación**: 0 suena a tope y 15 calla. El periodo lo calcula
el compilador con `periodo_psg()`: `3579545 / (32 · hercios)`, en 10 bits.

## Cómo arranca un cartucho

Un cartucho empieza con dos cosas en direcciones fijas:

```
$000000   tabla de vectores: la primera palabra larga es el valor inicial de la
          pila y la segunda, la dirección por la que arranca
$000100   cabecera: "SEGA MEGA DRIVE ", propietario, nombre, serie, suma de
          control, mandos, rango de la ROM, región
$000200   el código
```

`engine/megadrive/arranque.c` pone la tabla de vectores (pila en `$00FFFE00`) y
la cabecera; `_start` copia a la RAM las variables con valor inicial y pone a
cero las demás antes de llamar a `main()`.

La **suma de control** y el **fin de la ROM** no se pueden saber hasta que el
binario está hecho, así que los rellena `arreglar_rom.py` (que se genera dentro
del proyecto y no necesita nada instalado): redondea la ROM a una potencia de
dos, escribe el nombre del juego, el rango y la suma de todas las palabras a
partir de `$200`.

Lo primero que hace el motor al encenderse es el baile del **TMSS**: las Mega
Drive de segunda hornada exigen que se escriba `"SEGA"` en `$A14000` antes de
tocar el VDP, o se apagan.

## Si algo se ve raro

- **Gráficos revueltos**: el orden de los nibbles de `gfx_md.codificar_tile()`
  (cada byte son dos píxeles, el de la izquierda en los cuatro bits altos).
- **Colores cambiados**: mira el orden BGR de `md_color()`.
- **Un tile de 16 × 16 partido**: el VDP dibuja las cuatro celdas por columnas
  (arriba-izquierda, abajo-izquierda, arriba-derecha, abajo-derecha); está en
  `partir_16()`.
- **La pantalla no arranca**: casi siempre es el TMSS o los registros del VDP
  de `np_md_init()`.
