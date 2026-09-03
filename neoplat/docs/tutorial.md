# Tu primer juego en 10 minutos

## 1. Crea el proyecto

```bash
./ngplat nuevo mijuego --titulo "MI JUEGO" --autor "TU NOMBRE"
cd mijuego
```

Lo primero que te pregunta es el **género**, con un menú:

```
que tipo de juego quieres hacer?

  1) plataformas   salto controlado en el aire, disparo y pisar enemigos
  2) castlevania   salto sin control, latigo, escaleras y arma secundaria
  3) comando       visto desde arriba: ocho direcciones, granadas y prisioneros
  4) mazmorra      laberinto: la vida se gasta sola y los nidos sacan bichos
  5) barrio        yo contra el barrio: calle con profundidad y tortas
  6) aventura      cargar con las cosas y abrir con ellas lo que no se pasa

elige [1]:
```

El género no es un adorno: cambia la física del salto, el arma, si puedes
pisar enemigos y hasta el mapa del primer nivel. Los dos últimos cambian más
aún: se ven **desde arriba**, así que no hay gravedad ni saltos y se anda en
ocho direcciones (mira [«un juego visto desde
arriba»](#un-juego-visto-desde-arriba) y [«una mazmorra»](#una-mazmorra) al
final). Si ya lo tienes claro, pásalo
directo y se salta el menú:

```bash
./ngplat nuevo mijuego --genero castlevania
```

Puedes cambiar de idea luego: todo lo que elige el menú son campos normales de
`game.yaml` que puedes tocar a mano.

Ya tienes un juego completo: dos niveles, un héroe, dos enemigos y monedas.

## 2. Pruébalo

```bash
../ngplat probar
```

Se abre el navegador con el juego. Flechas para moverte, <kbd>Z</kbd> para
saltar, <kbd>Enter</kbd> para empezar. **Esto es exactamente lo que hará la
consola**: la simulación es la misma.

## 3. Cambia el mapa (con el ratón)

En el preview, pulsa <kbd>E</kbd>. Aparece el editor: eliges qué pintar en la
paleta (suelo, plataformas, pinchos, enemigos, monedas, la salida) y pintas
sobre el nivel. Con <kbd>2</kbd> haces rectángulos, con <kbd>3</kbd> rellenas
zonas y con <kbd>Ctrl</kbd>+<kbd>Z</kbd> deshaces. <kbd>Enter</kbd> lo prueba al
momento y <kbd>E</kbd> te devuelve al editor.

En la pestaña **revisar** tienes un botón que lanza un bot a jugarse el nivel:
si el bot llega a la meta, tú también.

Cuando te guste, pestaña **game.yaml** y copia o descarga el archivo. Todo el
editor está explicado en [editor.md](editor.md).

## 3b. …o cambia el mapa a mano

Abre `game.yaml` y busca `niveles:`. El mapa son caracteres:

```yaml
  - nombre: "BOSQUE"
    mapa: |
      ....................
      ..........ccc.......
      .........=====......
      ....................
      P....s............G.
      ####################
```

- `P` dónde empiezas (solo una)
- `#` suelo, `=` plataforma que se atraviesa desde abajo, `^` pinchos
- `G` la meta
- `s` una seta, `c` una moneda, `k` una llave, `T` un tablón que va y viene
  (mira `spawns:`)
- `/` y `|` escaleras (en el género castlevania): te subes pulsando arriba
  encima de ellas y subes en diagonal, paso a paso
- `!` un punto de control (también en castlevania): no estorba, pero si te
  matan reapareces ahí en vez de al principio del nivel
- `M` la mejora del látigo: cada una lo alarga un poco, y se pierden al morir


Cambia lo que quieras y vuelve a lanzar `../ngplat probar`. Tarda menos de un
segundo.

Consejo: el salto del héroe por defecto sube **2 tiles** y cruza **3 tiles** de
hueco. Si haces un hueco de 4, no se puede pasar (o sube `salto:`).

## 4. Cambia el personaje

Los gráficos están en `graficos/`. `heroe.png` es una tira de 6 fotogramas de
16x16 píxeles:

| 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| quieto | correr | correr | correr | saltar | caer |

Ábrelo con cualquier editor de píxeles (Aseprite, Piskel, GIMP, Paint) y
dibuja encima. Reglas:

- **Máximo 15 colores** más el transparente.
- El tamaño del fotograma tiene que ser múltiplo de 16.
- Si añades fotogramas, cambia también las `animaciones` del `game.yaml`.

¿Quieres un héroe más alto? Haz los fotogramas de 16x32 y pon:

```yaml
jugador:
  frame: [16, 32]
  caja: [10, 30]
```

## 5. Ajusta cómo se siente

Son las opciones que más cambian el juego:

```yaml
jugador:
  velocidad: 1.6      # súbelo a 2.2 para un juego rápido
  salto: 4.3          # 5.2 salta mucho más alto
  gravedad: 0.28      # 0.20 = flotante, 0.40 = pesado
  doble_salto: si     # segundo salto en el aire
```

Cambia un valor, `../ngplat probar` y lo notas al instante.

Y si lo quieres para dos:

```yaml
juego:
  jugadores: 2
```

Juegan los dos a la vez en la misma pantalla, cada uno con su mando y con sus
vidas. En el preview el segundo va con <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd>
y salta con <kbd>G</kbd>.

## 6. Añade un enemigo nuevo (desde el editor)

Lo más rápido: en el preview pulsa <kbd>E</kbd>, pestaña **enemigos y objetos**,
botón **«+ enemigo nuevo»**. Le pones nombre, eliges comportamiento y lo dibujas
ahí mismo (o reaprovechas un dibujo del proyecto). Al crearlo aparece en la
paleta y ya lo puedes pintar en el mapa.

Si lo has dibujado, en la pestaña **game.yaml** te sale un botón para descargar
su PNG: guárdalo en `graficos/` y listo.

## 6b. …o a mano en el archivo

```yaml
enemigos:
  fantasma:
    sprite: graficos/enemigo.png
    comportamiento: perseguidor    # te sigue si te acercas
    velocidad: 0.7
    rango: 120
    puntos: 300

spawns:
  f: fantasma        # ahora puedes poner 'f' en los mapas
```

## 6b. Cambia el fondo

El proyecto viene con dos capas de parallax (`graficos/cielo.png` y
`graficos/arboles.png`). Son PNG normales que se repiten en horizontal:

```yaml
fondos:
  - nombre: cielo
    imagen: graficos/cielo.png
    velocidad: 0.2      # cuanto mas bajo, mas lejos parece
    y: 0
  - nombre: arboles
    imagen: graficos/arboles.png
    velocidad: 0.5
    y: 144
```

Pinta encima de esos PNG (15 colores por capa) o añade otra capa. Si un nivel
concreto quiere otras capas, se lo dices en el propio nivel con
`fondos: [cielo]`.

## 6c. Cambia la música

La música y los efectos también están en el `game.yaml`, escritos con notas:

```yaml
sonido:
  efectos:
    salto: {tipo: barrido, desde: 320, hasta: 900, duracion: 6}
    moneda: {notas: "mi6 sol6", velocidad: 3}
  musica:
    bosque:
      velocidad: 8
      pistas:
        - "do4 mi4 sol4 mi4 | fa4 la4 do5 la4"
        - "do3 -   do3 -    | fa3 -   fa3 -"
```

Cambia las notas y vuelve a lanzar `../ngplat probar`: el preview lo toca al
momento (con <kbd>M</kbd> silencias). La primera pista es la melodía y la
segunda el acompañamiento; el tercer canal del chip se queda para los efectos.

## 7. Añade un nivel

Copia el bloque de un nivel y cambia el mapa. Se juegan en orden:

```yaml
niveles:
  - nombre: "BOSQUE"
    mapa: |
      ...
  - nombre: "CUEVA"
    fondo: "#180c20"
    mapa: |
      ...
```

## 8. Haz la ROM

```bash
../ngplat compilar
cd build/neogeo
make          # necesita ngdevkit instalado
make run      # arranca el emulador de ngdevkit
```

Si no tienes ngdevkit, `ngplat compilar` ya te ha dejado en `build/neogeo/`
todo el proyecto en C y las ROMs gráficas: puedes compilarlo en otro ordenador
que sí lo tenga.

## 9. El mismo juego en otra máquina

El juego que has escrito vale igual para una Mega Drive, para un Amiga o para
un Atari ST: solo cambia cómo se dibuja y cómo suena, no lo que pasa.

```bash
../ngplat sistemas                       # las siete máquinas y sus límites
../ngplat compilar --sistema megadrive   # -> build/megadrive/rom/juego.bin
../ngplat compilar --sistema amiga       # -> build/amiga/disco/MiJuego.adf
../ngplat compilar --sistema amiga1200   # -> lo mismo, con AGA: 256 colores
../ngplat compilar --sistema jaguar      # -> build/jaguar/rom/MiJuego.j64
../ngplat compilar --sistema atarist     # -> build/atarist/disco/mijuego.st
```

Para estas cuatro no hace falta ngdevkit, solo un compilador de 68000
cualquiera (`m68k-elf-gcc`, o el paquete `gcc-m68k-linux-gnu` de Debian y
Ubuntu). Añade `--make` y te lo construye del tirón.

Lo del Amiga es un **disquete de verdad**: un `.adf` de 880 KB que arranca solo,
sin Workbench. Lo metes en FS-UAE, WinUAE o Amiberry (o en un Gotek, si tienes
el Amiga delante) y enciendes:

```bash
cd build/amiga
make run          # con FS-UAE instalado, mete el disquete y arranca
```

Y el del Atari ST es otro disquete de verdad: un `.st` de 720 KB con el juego
en la carpeta `AUTO`, que es de donde TOS lo arranca solo al encender. Va en
Hatari, en Steem o en un ST con un Gotek delante:

```bash
cd build/atarist
make run          # con Hatari instalado, mete el disquete y arranca
```

Cada máquina tiene lo suyo, y `ngplat comprobar --sistema <máquina>` te lo dice
antes de compilar: la Mega Drive solo muestra 64 colores y una capa de fondo,
el Amiga 32 colores y niveles de hasta 16 casillas de alto (o 32, si el nivel no
pasa de 22 de ancho), y el Atari ST 15 colores, sin parallax y con una pantalla
de 200 líneas en vez de 224. Si algo no cabe, el mensaje te dice qué es y qué
quitar.

Y si tu juego se queda corto de colores, prueba `--sistema amiga1200`: es el
mismo Amiga con el chipset AGA, y ahí son **256 a la vez** y sin redondear
ninguno. El disquete que saca pide un A1200, un A4000 o un CD32.

También puedes dejarlo escrito en el `game.yaml` y olvidarte:

```yaml
juego:
  sistema: megadrive
```

## Un juego visto desde arriba

```bash
./ngplat nuevo micomando --genero comando
```

Este género es otra cosa. Se ve **desde arriba**, como el Ikari Warriors o el
Guerrilla War: no hay gravedad ni saltos, y el nivel no se cruza de izquierda a
derecha sino que **se sube**. Empiezas abajo del todo y la base está arriba.

Los mandos cambian con la vista:

- **Flechas**: te mueves en las **ocho** direcciones, diagonales incluidas.
- <kbd>X</kbd>: disparas **hacia donde miras**, sea la dirección que sea.
- <kbd>Z</kbd> / <kbd>espacio</kbd>: en vez de saltar, **tira una granada**. El
  marcador enseña cuántas te quedan (`GRAN 03`) y se recargan con las cajas.

El mapa se dibuja igual que en los otros géneros, solo que alto y estrecho:

```yaml
  - nombre: "EL CAMPAMENTO"
    mapa: |
      AAAAAA..,G,..AAAAAAA
      AAAAA.,,,,,,,.AAAAAA
      ...
      AAAAA...P....AAAAAAA
```

`P` abajo, `G` arriba, y entre medias un camino que **tuerce**: los recodos son
lo que hace que se juegue, porque un pasillo recto se sube andando y ya. Lo que
lo estrecha son los árboles (`A`), los sacos terreros (`#`) y el río (`~`), que
es de los que matan.

Lo nuevo de este género son dos cosas:

- **Los enemigos disparan.** Los soldados y las torretas llevan un bloque
  `dispara:` con su cadencia (`espera:`) y su alcance. Esa cadencia es lo que
  decide si un sitio se puede pasar o no: súbela y el paso se cierra.
- **Los prisioneros.** El símbolo `R` pone un preso atado. Si lo **tocas**, se
  suelta y suma 500 puntos; si le **disparas**, lo pierdes y no suma nada. Es lo
  que te obliga a mirar antes de apretar el gatillo. Están explicados en
  [formato.md](formato.md#prisioneros).

Todo lo demás es igual: los mismos gráficos PNG, el mismo editor con
<kbd>E</kbd> y el mismo `ngplat compilar`.

Sobre las máquinas: estos niveles son de **32 casillas de alto** y entran en las
seis. El Amiga y la Jaguar dibujan el escenario en un mapa de bits que se puede
poner ancho (44 × 16 casillas) o alto (22 × 32), y lo eligen solos según el nivel
más alto del juego; a cambio, con la forma alta el nivel tiene que caber entero
de ancho: 22 casillas. Si te pasas, `ngplat comprobar` te lo dice con esas
palabras antes de compilar.

## Una mazmorra

```bash
./ngplat nuevo micripta --genero mazmorra
```

También se ve desde arriba, pero se juega de otra manera: esto es un Gauntlet.
El nivel no es un camino, es un **laberinto** de 20 × 28 casillas que se ve casi
entero, y lo que decide la partida no es la puntería sino por dónde tiras.

Tres reglas lo cambian todo:

- **La vida se gasta sola.** El jugador trae `vida: 200` y `desgaste: 12`, o
  sea un punto cada doce frames: unos cuarenta segundos de reloj. El marcador
  lo enseña como número (`LIFE 184`) y va bajando siempre, te pegue alguien o
  no. Se recupera con la comida (`efecto: salud`), que es lo único que para la
  cuenta atrás.
- **Los nidos sueltan bichos sin parar.** El símbolo `n` pone un nido y `N` una
  cripta, y cada uno saca su bicho cada tantos frames hasta que lo revientas a
  flechazos. Mientras siga en pie, matar lo que sale no sirve para nada: es lo
  que te empuja a meterte donde no querías.
- **La poción limpia la pantalla.** El botón de saltar no salta (aquí no hay
  nada que saltar): tira una poción. Y hay otra, `r`, que al cogerla hace daño a
  **todo lo que se ve en ese momento**, nidos incluidos. La *smart bomb* de toda
  la vida: vale lo que valga el momento en que la cojas.

Y encima la meta pide una llave que está al otro lado del laberinto, así que
hay que dar la vuelta entera con el reloj corriendo. Ir a por todo —la comida
de un lado y el tesoro del otro— es quedarse sin vida: eso es el género.

```yaml
jugador:
  vida: 200
  desgaste: 12         # un punto cada 12 frames

generadores:
  nido:
    genera: bicho      # qué saca
    cada: 100          # cada cuántos frames
    tope: 3            # cuántos suyos puede haber a la vez
    vida: 3            # flechazos que aguanta
```

Los dos laberintos que trae se pueden terminar andando, y hay una prueba que lo
comprueba con un bot que va **primero a por la llave** y después a la salida
(`tests/test_niveles.py`). Si tocas el mapa y cierras un paso, esa prueba te lo
dice.

Todo lo demás es igual que siempre: los mismos PNG, el mismo editor y el mismo
`ngplat compilar` para las siete máquinas. Están explicados al detalle en
[formato.md](formato.md#generadores) (`generadores`, `desgaste` y
`efecto: bomba`).

## Yo contra el barrio

```bash
./ngplat nuevo micalle --genero barrio
```

Un juego de tortas, de los de Double Dragon. Se ve **de lado**, como el de
plataformas, pero no se anda por una línea: se anda por una **franja de suelo**
con profundidad, arriba y abajo. Y el salto es una tercera coordenada aparte:
la altura sobre el suelo.

Esas tres coordenadas son el género entero:

- **Dos que no están a la misma profundidad no se tocan.** Aunque en la
  pantalla parezca que sí. Por eso lo primero de cada pelea es cuadrarse, y por
  eso moverte arriba y abajo es esquivar.
- **Al saltar, tu caja sube con el dibujo**, así que un puñetazo a ras de suelo
  te pasa por debajo.

Los mandos:

- **Flechas**: te mueves en las ocho direcciones, por el ancho de la calle.
- <kbd>X</kbd>: puñetazo. Y aquí viene lo bueno: si vuelves a apretar antes de
  que se acabe la ventana, **encadenas** —puño, puño y **remate**—. El remate
  hace más daño y **tumba**: el que lo cobra sale despedido y se queda unos
  frames en el suelo, sin decidir nada y sin hacerte daño.
- <kbd>Z</kbd> / <kbd>espacio</kbd>: salta.
- Y al que se **tambalea** de un golpe se le **agarra** tocándolo: con
  <kbd>X</kbd> le das rodillazos y con <kbd>Z</kbd> lo lanzas por encima del
  hombro. Lanzarlo es el golpe más fuerte del juego y además te lo quita de
  encima, que cuando son tres es media pelea.

**La cámara lleva cerrojo**: mientras quede alguien vivo en pantalla, la vista
no avanza. Eso no se configura y no se puede quitar: es lo que convierte un
pasillo en una pelea. Si te vas hacia la derecha sin pegar a nadie, te quedas
en el sitio.

El mapa es una calle de 48 × 14 casillas: arriba los edificios, abajo el
bordillo y en medio las siete filas por las que se anda.

```yaml
  - nombre: "LA CALLE"
    mapa: |
      ################################################
      cccccccccccccccccccccccccccccccccccccccccccccccc
      ------------------------------------------------
      ..........B..............B.....................G
      ....m...........m.............m....m...........G
      P.......................b......................G
      ...
```

`P` a la izquierda, `G` a la derecha, `m` matones, `b` los grandes, `B`
barriles (que se rompen y sueltan un pollo) y `J` el jefe. Lo que hace que se
juegue no es el dibujo del suelo, es **dónde se planta cada grupo**: como la
cámara no pasa, cada grupo es una pantalla.

Y una cosa que se nota al jugar: los actores se pintan **de más lejos a más
cerca**. En un juego donde todo el mundo se pisa, si no, no se entiende quién
está delante de quién. De eso se encarga el motor en las siete máquinas.

## Una aventura

```bash
./ngplat nuevo miaventura --genero aventura
```

Una aventura de las de Dizzy. Se ve **de lado**, como el de plataformas, pero
no va de saltar bien: va de **llevar la cosa correcta al sitio correcto**.

Tres reglas, y las tres cambian cómo se juega:

- **No se pega.** El botón de acción no ataca: **suelta** lo primero de lo que
  llevas encima. Y en la bolsa caben **tres cosas**, así que cargar con una es
  decidir no cargar con otra.
- **Lo que te para no es un bicho: es un cerrojo.** Una puerta, una hoguera o
  una pared que frenan como un muro hasta que apareces con lo suyo. Al abrirlas
  se gasta el objeto y el paso se queda abierto **para siempre**. A los bichos
  no se les mata: se les esquiva.
- **El salto no se manda en el aire.** Al despegar decides hacia dónde vas y
  con cuánto impulso, y hasta caer no se cambia; ni soltar el botón lo acorta.
  Suena incómodo y es justo lo que hace que cada salto sea una decisión. Ojo:
  si chocas de lado contra una pared te quedas sin impulso, así que para subir
  un escalón hay que saltar **antes** de llegar a él.

Los mandos:

- **Flechas**: andar.
- <kbd>Z</kbd> / <kbd>espacio</kbd>: saltar (el salto fijo).
- <kbd>X</kbd>: soltar lo primero de la bolsa, a tus pies.

Arriba, en el marcador, sale **lo que llevas**: sin mirarlo no se sabe si la
puerta de delante se abre o hay que dar media vuelta.

La cámara va **de pantalla en pantalla**, sin scroll: cada nivel son cuatro
pantallas de 20 × 14 pegadas, y cada una es un sitio. Los dos niveles del
proyecto de partida son la misma cadena contada de dos maneras:

- **EL VALLE**, en orden: la llave abre la puerta, detrás está el cubo que apaga
  la hoguera, y detrás el pico que tira la pared.
- **LA CUEVA**, desordenada: el pico y la llave se cogen juntos arriba del todo
  y hacen falta en pantallas distintas, así que hay que **acordarse** de lo que
  llevas.

En el `game.yaml`, un cerrojo es un tile con `tipo: cerrojo` y el objeto que lo
abre:

```yaml
tiles:
  leyenda:
    'D': {tile: 7, tipo: cerrojo, abre_con: llave}
    'F': {tile: 8, tipo: cerrojo, abre_con: cubo}
    'W': {tile: 9, tipo: cerrojo, abre_con: pico}

objetos:
  llave:
    efecto: llevar     # no se gasta al tocarlo: se guarda en la bolsa
    marcador: LLAVE    # como sale escrito arriba
```

Lo que pide un cerrojo tiene que existir y tiene que ser de los que se llevan:
si no, `ngplat comprobar` te lo dice antes de compilar, porque una puerta que
pide algo que no se puede coger no es un puzle difícil, es un juego roto.

Una puerta de **dos casillas** (una encima de otra) es **una** puerta: se abre
entera y cuesta un solo objeto. Y el jugador lleva `salto_fijo: si` y
`pisar_enemigos: no`, que son las dos líneas que convierten el plataformas en
una aventura.

Como en el resto de géneros, el bot comprueba que los dos niveles se pueden
resolver (`tests/test_niveles.py`), y hay un control que quita los tres objetos
del mapa y exige que entonces **no** se pase.

## Cuando algo falla

```bash
../ngplat comprobar
```

Te dice el problema, dónde está y cómo arreglarlo. Ejemplos:

```
error en niveles[1]: el mapa usa el simbolo '@' (fila 4, columna 12) y no esta en la leyenda
  pista: anadelo en 'tiles: leyenda:' o en 'spawns:' del nivel

error en jugador: el fotograma mide 12x12 y la Neo Geo dibuja sprites en bloques de 16x16
  pista: usa medidas multiplos de 16 (16x16, 16x32, 32x32...)
```
