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

elige [1]:
```

El género no es un adorno: cambia la física del salto, el arma, si puedes
pisar enemigos y hasta el mapa del primer nivel. El tercero cambia más aún: se
ve **desde arriba**, así que no hay gravedad ni saltos, se anda en ocho
direcciones y se sube la pantalla a tiros (mira
[«un juego visto desde arriba»](#un-juego-visto-desde-arriba) al final). Si ya lo tienes claro, pásalo
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
../ngplat sistemas                       # las seis máquinas y sus límites
../ngplat compilar --sistema megadrive   # -> build/megadrive/rom/juego.bin
../ngplat compilar --sistema amiga       # -> build/amiga/disco/MiJuego.adf
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
el Amiga 32 colores y niveles de hasta 16 casillas de alto, y el Atari ST 15
colores, sin parallax y con una pantalla de 200 líneas en vez de 224. Si algo
no cabe, el mensaje te dice qué es y qué quitar.

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

Un aviso sobre las máquinas: estos niveles son de **32 casillas de alto**, y el
Amiga y la Jaguar dibujan el escenario en un mapa de bits que llega a 16. Ahí
`ngplat comprobar` te lo dice y no compila. Para esas dos, o bajas el nivel a 16
casillas o lo haces de lado como los otros géneros. En Neo Geo, Mega Drive,
Atari ST y X68000 entra tal cual.

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
