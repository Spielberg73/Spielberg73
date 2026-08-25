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

El VDP no acepta cualquier dirección: los planos A y B tienen que empezar en un
múltiplo de 8 KB, la ventana en uno de 4 KB (en modo de 320 px) y las tablas de
sprites y de scroll en uno de 1 KB. Y cada tabla **ocupa de verdad lo que dice
su tamaño**, así que ninguna puede pisar a otra:

```
$0000   dibujos             42 KB → 1344 tiles de 8×8
$A800   tabla de sprites    80 entradas de 8 bytes
$AC00   scroll horizontal
$B000   marcador            64 × 32 celdas (4 KB)
$C000   escenario           64 × 64 celdas (8 KB)
$E000   parallax            64 × 64 celdas (8 KB)
```

Cabe algo menos de 1344 tiles de 8 × 8. Si te pasas, `ngplat comprobar` te lo
dice antes de compilar.

Con planos de 64 × 64 celdas cada tabla son 8 KB, y tres tablas de 8 KB no caben
junto con los dibujos: por eso el marcador usa 64 × 32 (le sobra: sólo ocupa las
tres primeras filas).

El marcador se muestra porque el registro $12 dice "la ventana son las tres
primeras filas". Si se deja a cero, la ventana no ocupa nada y el marcador se
escribe pero no se ve.

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

Las pruebas escuchan lo que sale del PSG emulado y comprueban que son las notas
del `game.yaml`, una a una: ver [docs/sonido.md](sonido.md).

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

## Dos trampas del 68000 con las que se cuelga el juego

Las dos las encontró la prueba del emulador (`make test-emulador`) y ninguna
podía verse compilando:

**1. La libgcc del compilador es de 68020.** Cuando el compilador se encuentra
un `*`, un `/` o un `%` de 32 bits genera una llamada a `__mulsi3`, `__divsi3`,
`__modsi3`… El 68000 no tiene esas instrucciones. Esas rutinas suelen venir en
la libgcc, pero la de un compilador de 68k para Linux está hecha para **68020**
y lleva cosas como `bsr.l` (`61ff`), que el 68000 no entiende: en la primera
división el juego se para con una excepción de "línea F". Por eso NeoPlat trae
las suyas en `engine/core/np_aritmetica.c` y enlaza con `-nodefaultlibs`.

**2. gcc junta dos escrituras de un byte en una de dos.** Con `-Os`, ante
`w->keys = 0; w->entity_count = 0;` (dos `uint8_t` seguidos) gcc emite un
`clr.w`. Si el par cae en una dirección impar, el 68000 se para con un "address
error": **no puede leer ni escribir palabras en direcciones impares**. Se
arregla con `-fno-store-merging`, y las pruebas del kit revisan el binario ya
hecho para que no quede ninguno.

## Si algo se ve raro

- **Gráficos revueltos**: el orden de los nibbles de `gfx_md.codificar_tile()`
  (cada byte son dos píxeles, el de la izquierda en los cuatro bits altos).
- **Colores cambiados**: mira el orden BGR de `md_color()`.
- **Un tile de 16 × 16 partido**: el VDP dibuja las cuatro celdas por columnas
  (arriba-izquierda, abajo-izquierda, arriba-derecha, abajo-derecha); está en
  `partir_16()`.
- **La pantalla no arranca**: casi siempre es el TMSS o los registros del VDP
  de `np_md_init()`.
- **Se queda congelado**: casi seguro que es una de las dos trampas de arriba.
  `make test-emulador` lo pilla; para saber dónde, mete una escritura a una
  dirección de RAM que no uses (`*(volatile uint16_t *)0xFFFFF0 = n;`) en varios
  puntos y mira ese byte con el emulador.
- **Se ve sólo media pantalla**: comprueba el registro $0C (debe valer $81 para
  320 px)... o que quien lee el framebuffer no esté suponiendo 4 bytes por
  píxel cuando el emulador da 2.
