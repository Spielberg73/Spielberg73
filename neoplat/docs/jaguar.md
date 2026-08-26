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

## Lo que aún no hace

- **Sonido.** Jerry tiene dos DAC de 16 bits, pero alimentarlos pide un programa
  para el DSP, que es otro juego de instrucciones y otro ensamblador. El juego
  sale mudo y el compilador avisa.
- **Capas de parallax.** Cabrían de sobra —la Jaguar puede componer muchos más
  objetos— pero todavía no están.
- **Color directo.** Se usan los 256 de la tabla. La Jaguar puede hacer 16 bits
  por píxel, y sería la única de las cuatro donde los PNG no habría que
  recortarlos: se verían tal cual.
- **El GPU y el DSP** están sin tocar. Para un juego de plataformas no hacen
  falta, pero ahí están.
