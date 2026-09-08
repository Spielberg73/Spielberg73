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
  5) barrio        yo contra el barrio: se colocan, avisan y esperan turno
  6) aventura      cargar con las cosas y abrir con ellas lo que no se pasa
  7) filmation     una habitacion vista desde una esquina: cubos y salas
  8) kung-fu       un templo de pantallas fijas: faroles, lianas y dos que
                   te siguen
  9) aventura grafica  se senala, no se anda: un cursor, cuatro verbos y una
                   habitacion que contesta

elige [1]:
```

El género no es un adorno: cambia la física del salto, el arma, si puedes
pisar enemigos y hasta el mapa del primer nivel. Algunos cambian más aún: el
tercero y el cuarto se ven **desde arriba**, así que no hay gravedad ni saltos
y se anda en ocho direcciones (mira [«un juego visto desde
arriba»](#un-juego-visto-desde-arriba) y [«una mazmorra»](#una-mazmorra) al
final), y el noveno no se anda siquiera: se **señala** (mira [«una aventura
gráfica»](#una-aventura-gráfica)). Si ya lo tienes claro, pásalo
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
../ngplat sistemas                       # todas las máquinas y sus límites
../ngplat compilar --sistema megadrive   # -> build/megadrive/rom/juego.bin
../ngplat compilar --sistema amiga       # -> build/amiga/disco/MiJuego.adf
../ngplat compilar --sistema amiga1200   # -> lo mismo, con AGA: 256 colores
../ngplat compilar --sistema cd32        # -> build/cd32/disco/MiJuego.iso
../ngplat compilar --sistema jaguar      # -> build/jaguar/rom/MiJuego.j64
../ngplat compilar --sistema atarist     # -> build/atarist/disco/mijuego.st
```

El CD32 es el mismo juego del A1200 en un CD: el ejecutable es idéntico y lo
que cambia es el envase. Para que el CD arranque solo en una consola de verdad
hay que añadirle la marca de Commodore (`make MARCA=/ruta/CD32.TM`), que no se
puede repartir con el kit; sin ella el ISO vale igual pero no arranca.

Para estas cinco no hace falta ngdevkit, solo un compilador de 68000
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

## Que pase algo: guiones

Hasta aquí el `game.yaml` describe **un mundo**. Lo que no dice es que **pase
algo**: que al pisar una casilla se abra una puerta, que un cartel avise, que
la segunda vez que pasas la cosa haya cambiado. Para eso están los guiones, y
su memoria son las variables.

Es lo más corto que se puede escribir para verlo:

```yaml
variables:
  avisos: 0

guiones:
  cartel:
    - sumar: {avisos: 1}
    - si: {avisos: 1}
      pasos:
        - decir: "CUIDADO CON EL FOSO QUE HAY MAS ADELANTE."
      si_no:
        - decir: "TE LO DIJE."

tiles:
  leyenda:
    'C': {tile: 0, tipo: vacio, guion: cartel}
```

Pones una `C` en el mapa y ya tienes un cartel que se lee, se acuerda de que lo
leíste y la segunda vez dice otra cosa.

**Un guion es una lista de pasos.** No son bloques que se arrastran: aquí el
proyecto es texto a propósito —se lee, se compara, se mete en git y el editor
lo reescribe sin tocar tus comentarios—, y un guion también. Los pasos que hay
son ocho: `decir`, `esperar`, `poner`, `sumar`, `si`, `sonido`, `dar` e
`ir_a_nivel` (los tienes todos en
[docs/formato.md](formato.md#variables-y-guiones)).

Tres cosas que conviene saber desde el principio:

- **Los pasos que no esperan corren todos en el mismo frame.** Poner tres
  variables y dar un objeto cuesta un frame, no cuatro. Sólo paran `decir:`
  —hasta que pulsas— y `esperar:`.
- **Mientras hay un guion, la partida no corre**: ni tú, ni los bichos, ni el
  reloj. Un cuadro de texto mientras te matan por detrás no es un cuadro de
  texto, es un adorno.
- **Las variables son de la partida**, no del nivel: sobreviven a cambiar de
  nivel y a perder una vida. Es lo que permite que el juego se acuerde de lo
  que hiciste dos niveles atrás.

Un guion se lanza de dos maneras: pisando una casilla que lo lleve (`guion:` en
la leyenda, y con `una_vez: si` sólo la primera vez de toda la partida), o al
empezar un nivel (`guion:` en el nivel, que es por donde un juego cuenta algo
antes de dejarte jugar).

**El cuadro de texto son dos líneas de 36 caracteres**, en el marcador. No es
capricho: 36 es lo que cabe en la más estrecha de las siete máquinas, y el
marcador es lo único libre sin tapar el juego. El texto se parte por palabras
**en el compilador**, así que un `decir:` largo sale en varias páginas y se
pasan con el botón.

El género de aventura ya viene con todo esto puesto: prueba
`./ngplat nuevo miaventura --genero aventura` y mira su `game.yaml`.

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

### Los que tienes enfrente

Y lo que hace que esto sea una pelea y no un enjambre: **los enemigos no van a
rozarte, van a pegarte**. Cada uno con `golpe:` hace cuatro cosas, y las cuatro
se notan al mando:

1. **Se coloca y no se te mete dentro.** Se acerca hasta donde le llega el
   brazo y ahí se para. Nunca acabas con tres encima empujándote.
2. **Espera su turno.** `agresivos:` dice cuántos pueden estar pegando **a la
   vez** —dos, como en los recreativos—; el resto rondan. Es el número más
   importante del género y el que menos se ve: sin él no hay hueco entre golpe
   y golpe.
3. **Se le ve venir.** Antes de soltarlo hay `preparacion:` frames de aviso.
   Sin eso no se puede esquivar y el juego es injusto; con eso, cada golpe que
   cobras es culpa tuya.
4. **Deja una ventana.** Después de pegar se queda `recuperar:` frames
   plantado. Ese hueco es tu turno, y de ahí sale el ritmo de la pelea.

Y **te rodean**: la mitad viene por el otro lado, así que girarse importa.

Cuando aciertas, el mundo **se para** cuatro frames (nueve en el remate) y al
tumbar a alguien la pantalla **tiembla**. No es adorno: sin esa parada el puño
atraviesa al otro y no se siente nada.

Los mandos:

- **Flechas**: te mueves en las ocho direcciones, por el ancho de la calle. Y
  **dos toques seguidos** en la misma dirección: **corres**. Correr es la
  respuesta a que te rodeen.
- <kbd>X</kbd>: puñetazo. Y aquí viene lo bueno: si vuelves a apretar antes de
  que se acabe la ventana, **encadenas** —puño, puño y **remate**—. El remate
  hace más daño y **tumba**: el que lo cobra sale despedido y se queda unos
  frames en el suelo, sin decidir nada y sin hacerte daño.
- <kbd>X</kbd> **con alguien detrás**: **codazo**. Si el que te tienes encima
  está a tu espalda y delante no hay nadie, te giras solo. Girarse a mano con
  tres alrededor es imposible, así que lo hace el juego.
- <kbd>X</kbd> **en el aire**: **patada en salto**. Pega como un remate y
  tumba. Es la forma de meterse en un grupo sin comerse los tres golpes de
  camino, y cuesta algo: en el aire no se corrige.
- <kbd>X</kbd> **corriendo**: **hombro**. También vale por un remate, y **gasta
  la carrera**: uno por esprint, no un botón de tumbar.
- <kbd>Z</kbd> / <kbd>espacio</kbd>: salta.
- Y al que se **tambalea** de un golpe se le **agarra** tocándolo: con
  <kbd>X</kbd> le das rodillazos y con <kbd>Z</kbd> lo lanzas por encima del
  hombro. Lanzarlo es el golpe más fuerte del juego y además te lo quita de
  encima, que cuando son tres es media pelea.

Una cosa más, y es la que cambia cómo se juega: **al que ya ha empezado a
soltar el golpe no lo paras con un puñetazo normal**. Hay que apartarse
—moverte en profundidad, que es donde su golpe no llega—, saltarle por encima
o gastarle algo fuerte. Si un puño cualquiera lo cortara, bastaría con pegar
sin parar y volveríamos a machacar el botón.

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
      ..........B.............B......................G
      ..........................m....................G
      P.....m..........b.............................G
      ...
```

`P` a la izquierda, `G` a la derecha, `m` matones, `b` los grandes, `B`
barriles (que se rompen y sueltan un pollo) y `J` el jefe. Lo que hace que se
juegue no es el dibujo del suelo, es **dónde se planta cada grupo**: como la
cámara no pasa, cada grupo es una pantalla.

Y los grupos son de **dos y de tres**, no de siete: como solo pegan dos a la
vez, lo que hace la dificultad no es cuántos hay sino **quiénes** —el grande
avisa más pero pega el doble— y cuánto sitio te dejan.

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

## Un castillo isométrico

```bash
./ngplat nuevo micastillo --genero filmation
```

Esto no se ve de lado ni desde arriba: se ve **una habitación desde una
esquina**, como en el Knight Lore. Y es el género que más cosas cambia, porque
cambia hasta lo que significa el mapa.

**El mapa ya no es lo que se ve: es la planta de la sala.** Cada casilla lleva
una altura, y con ese número se escribe el escenario entero:

```yaml
tiles:
  leyenda:
    '.': {tile: 0, tipo: vacio}                              # suelo
    'e': {tile: 0, tipo: solido, alto: 4,  cubo: escalon}    # se sube andando
    'o': {tile: 0, tipo: solido, alto: 16, cubo: losa}       # un salto
    'O': {tile: 0, tipo: solido, alto: 32, cubo: pilar}      # dos alturas
    '#': {tile: 0, tipo: solido, alto: 48, cubo: pintado}    # pared del fondo
    'M': {tile: 0, tipo: solido, alto: 48, cubo: muro}       # y esto tapia
```

Y una habitación se escribe así, en ocho líneas de ocho:

```
####M###
#.......
#..o....
#.......
M..P....
#....s..
#..o....
#..^....
```

La primera fila y la primera columna son las dos **paredes del fondo** —en
pantalla caen detrás de todo, que es lo que hace que una sala parezca una sala—.
Vienen ya dibujadas, con una puerta en medio de cada una, así que en el mapa se
escriben con `'#'`: para al que anda y no cuesta un solo sprite. Donde esa
puerta no lleve a ninguna parte se tapia con `'M'`, que sí es un cubo de verdad.

Eso no es un capricho: quince cubos de pared por habitación son lo que separa a
una Mega Drive de ir a 60 o a 30. Y no hacen falta, porque una pared del fondo
nunca tapa a nadie.

Las tres reglas del género:

- **Lo que te frena es la altura.** No hay tiles de pared y tiles de suelo: hay
  un número. Seis píxeles se suben andando, dieciséis hay que saltarlos y
  cuarenta y ocho no se pasan. El salto de serie llega a 23, y esa diferencia
  **es** el diseño del juego: para llegar arriba hay que buscar el escalón.
- **El mando va a los ejes del mapa**, no a los de la pantalla: derecha es el
  eje x de la planta, que en pantalla sale hacia abajo y a la derecha. Escrito
  suena raro y jugado se aprende en dos pasos; a cambio, las diagonales del
  mando dan los cuatro lados rectos de la pantalla.
- **El salto no se manda en el aire.** Como en la aventura: al despegar decides
  y hasta caer no se cambia. Lo que sí se guarda es el impulso, así que para
  subirte a un cubo que tienes pegado no hace falta carrerilla.

Los mandos:

- **Flechas**: andar por la planta.
- <kbd>Z</kbd> / <kbd>espacio</kbd>: saltar.
- <kbd>X</kbd>: soltar lo que llevas (el talismán).

Saltar no es solo para subirse: es la forma de **esquivar**. Por encima de un
pincho no pasa nada, y por encima de un bicho tampoco, porque en esta vista dos
que no se cruzan en altura no se tocan.

Una sala son **8x8 casillas** y el mapa se reparte en salas enteras: los dos
niveles del proyecto de partida son seis habitaciones cada uno, tres por dos.
Al cruzar el borde la cámara **salta** a la de al lado, y lo que pasa en las
demás se queda en pausa —de eso vive el que un castillo entero quepa en una
máquina de 1985: solo existen los cubos de la habitación que se está viendo—.

- **EL PATIO** enseña el relieve, y lo enseña por orden. La sala de entrada
  pone un escalón, una losa y un pincho uno al lado de otro —lo que se anda, lo
  que se salta y lo que mata—; la tercera es una tapia de losas con la llave
  detrás, que es la primera vez que el juego pide subirse a algo para llegar a
  alguna parte; y la del paso de los pinchos se cruza en zigzag o por encima.
  Tres llaves y la salida en la última sala.
- **LAS MAZMORRAS** añade dos cosas. La escalera del género: del suelo a una
  losa de 16 y de la losa a un pilar de 32, porque de un salto se suben 23
  píxeles y al pilar no se llega desde abajo. Y el puzle: la salida está detrás
  de una puerta con un talismán grabado, y el talismán está en la otra punta
  del piso de arriba. Hay que cruzar el nivel entero, volver y bajar.

**El editor edita habitaciones.** Al entrar con <kbd>E</kbd> no sale una
cuadrícula de tiles: salen las salas dibujadas en isométrica, con sus cubos y
sus bichos puestos donde van a estar jugando, y el ratón pincha **en el rombo**.
En la paleta cada casilla sale con su cubo y con su altura —"sólido: muro (alto
48)"—, que es lo que hace falta para no confundir una pared con un escalón.

El dibujo de una sala —las dos paredes del fondo y el suelo— es un rectángulo
del propio tileset (`sala: {tile: 16, ancho: 16, alto: 11}`): repintarlo cambia
el castillo entero sin tocar nada más.

Como en el resto de géneros, el bot comprueba que los dos castillos se pueden
terminar, y hay un control que quita el talismán del mapa y exige que entonces
**no** se pase.

## Un templo de kung-fu

```bash
./ngplat nuevo mitemplo --genero kungfu
```

Este se ve de lado, como el de plataformas, pero no va de llegar al final: va
de **recorrer** un templo apagando faroles con dos tipos detrás. Es el Bruce
Lee de 1984, y lo que lo hace ese juego y no otro son tres reglas que van
juntas.

**1. Los que te persiguen no son de la pantalla: son tuyos.**

```yaml
  yamo:
    comportamiento: perseguidor
    tenaz: si          # esta linea es el genero entero
```

Con `tenaz: si`, al cambiar de cuadro el enemigo **vuelve a entrar por el borde
por el que has entrado tú**. No se le deja atrás cambiando de pantalla: se le
esquiva, se le tumba o se le usa. Sin esa línea cada pantalla es un puzle que
se resuelve con calma; con ella entretenerse cuesta, y volver sobre tus pasos
es meterte de cabeza en el que venía detrás.

**2. Se pegan entre ellos.**

```yaml
juego:
  entre_ellos: si    # el golpe de un bicho le hace dano al de al lado
```

El palo del ninja le entra a Yamo igual que a ti. Suena a detalle y es media
mecánica: dos perseguidores que se pegan entre ellos dejan de ser dos problemas
y pasan a ser una herramienta, porque colocarlos para que se crucen es lo único
que tienes cuando no puedes con ninguno de los dos.

**3. Se trepa, y una liana no es una escalera.**

```yaml
tiles:
  leyenda:
    '|': {tile: 5, tipo: liana}
jugador:
  trepa: 1.1         # 0 = las casillas de liana no hacen nada
```

A una escalera se sube desde el suelo y en diagonal. A una liana **te agarras
en el aire**, se sube recta y desde ella se salta a donde sea con impulso: es
el camino a lo que está arriba y la manera de quitarte de en medio. `trepa:` es
lo que la enciende: a cero las mismas casillas siguen dibujándose y dejan de
agarrar.

Y encima de las tres, el golpe tiene dos formas:

```yaml
  ataque:
    tipo: golpe
    alcance: 14
    patada: 26       # en el aire llega casi al doble
    dano_patada: 2   # y duele el doble
```

`patada:` es lo que convierte el salto en un ataque. Sin esa línea, pegar en el
aire saca el mismo puñetazo corto y saltar sólo sirve para moverse. Con ella,
la patada voladora tiene su propio alcance, su propio daño y su propio dibujo
(la animación `patada:`, que por eso los fotogramas son de 32×32: un golpe que
llega más lejos tiene que **verse** más largo).

**Lo que abre la puerta son los faroles.** El objeto lleva `efecto: llave` y el
nivel dice cuántos pide:

```yaml
objetos:
  farol:
    efecto: llave
    cantidad: 1
niveles:
  - nombre: "EL PATIO DEL TEMPLO"
    llaves: 5        # hasta que no estan los cinco, la puerta no se abre
```

Los dos niveles que salen son cuatro pantallas cada uno, sin scroll: cada
cuadro es una sala del templo.

- **EL PATIO DEL TEMPLO** enseña de una en una. La primera pantalla sólo tiene
  vigas —tres escalones de dos casillas, que es justo lo que sube el salto—; la
  segunda añade la liana y a Yamo, que es lento pero no se queda atrás; la
  tercera los fosos de pinchos; y la cuarta al ninja y la puerta. Cinco
  faroles.
- **LAS ENTRAÑAS** ya no enseña nada: usa. Los dos bichos desde la primera
  pantalla, lianas gemelas, pinchos debajo de casi todo y **siete** faroles
  para una puerta que pide seis: el que sobra es para que puedas elegir entre
  trepar por él o quedarte abajo peleando.

**La pared del fondo es una capa, no casillas** (`fondos: [muro]`, con
`velocidad: 0.5`). Así no ocupa mapa, no estorba al saltar y se corre media
pantalla al cambiar de sala, que es lo que hace que las cuatro no parezcan la
misma.

Como en el resto de géneros, el bot comprueba que los dos niveles se pueden
terminar, y hay un control que **quita la liana** de la segunda pantalla y
exige que entonces no se llegue al farol de arriba.

## Una aventura gráfica

```bash
./ngplat nuevo lacasa --genero grafica
```

Éste no se parece a ninguno de los ocho anteriores, y en una cosa: **aquí no se
anda**. El jugador es un cursor. No pesa, no choca, no cobra y no puede morir;
lo único que hace es moverse por la pantalla y señalar.

```yaml
juego:
  vista: puntero
  verbos: [MIRAR, COGER, USAR, HABLAR]
  sin_efecto: nada
```

**El mando lleva un verbo puesto.** El botón de saltar —que aquí no tiene nada
que saltar— pasa al siguiente de los cuatro, en bucle, y el de acción se lo
aplica a la casilla que estés señalando. El verbo sale escrito arriba, delante
de lo que llevas encima, porque sin verlo el juego se convierte en adivinar.

Es la primera vista del kit donde **lo que pasa al pulsar depende de algo que
llevas tú**, y de ahí sale el género entero: la misma puerta contesta una cosa
al mirarla y hace otra al abrirla.

**Las casillas contestan.** En la leyenda, un guion por verbo:

```yaml
tiles:
  leyenda:
    'q': {tile: 13, tipo: vacio, mirar: mirar_cuadro, hablar: hablar_cuadro}
    'K': {tile: 22, tipo: vacio, debajo: 'u', mirar: mirar_llave, coger: coger_llave}
```

Un mueble grande son varias casillas y todas llevan los mismos guiones: el
cuadro son cuatro tiles y el jugador no tiene por qué enterarse. Y cuando la
casilla que señalas no contesta a ese verbo, contesta el juego por ella con el
guion de `sin_efecto:`, escrito una vez y en tu idioma.

**Coger algo son cuatro pasos**, y aquí se ve para qué sirven los guiones:

```yaml
  coger_llave:
    - si: {llave: 0}
      pasos:
        - poner: {llave: 1}       # el juego se acuerda
        - dar: llave              # va a la bolsa, y se ve en el marcador
        - quitar: [12, 9]         # y deja de estar dibujada en la mesa
        - sonido: moneda
        - decir: "TE GUARDAS LA LLAVE."
      si_no:
        - decir: "YA LA LLEVAS ENCIMA."
```

`quitar:` borra la casilla del mapa: deja de dibujarse y deja de contestar. Lo
que se ve en su sitio es lo que diga su `debajo:` —ahí, `'u'`, que es la mitad
derecha de la mesa—, y por eso al coger la llave queda la mesa pelada y no un
agujero con forma de pared.

**El puzle entero cabe en un guion**, porque un puzle de aventura es una
condición:

```yaml
  usar_trampilla:
    - si: {llave: 0}
      pasos:
        - decir: "ESTA CERRADA CON LLAVE."
      si_no:
        - si: {farol: 0}
          pasos:
            - decir: "AHI ABAJO NO SE VE NADA. NECESITAS ALGO DE LUZ."
          si_no:
            - decir: "LA LLAVE ENTRA. ABRES LA TRAMPILLA Y BAJAS."
            - ir_a_nivel: 2
```

**Y se acaba con `acabar:`**, porque aquí no hay casilla de meta que pisar: al
abrir el arcón del sótano con la barra, el último guion dice `acabar: si` y,
por ser el último nivel, se acabó el juego.

El ejemplo son dos habitaciones —el estudio del abuelo y el sótano—, un retrato
con el que se puede hablar (y que se acuerda de cuántas veces le has hablado),
un farol, una llave, una trampilla que pide las dos cosas y un arcón que no
cede con las manos.

El bot del kit también juega a esto, pero de otra manera: como no hay camino
que buscar, va a cada casilla que contesta a algo y le prueba los cuatro
verbos, una y otra vez, barajando el orden. Es lo mismo que hace una persona
cuando se atasca, y si probándolo todo el juego no se acaba, es que no tiene
solución. Hay además un control que **quita la barra** del sótano y exige que
entonces el arcón no se abra.

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
