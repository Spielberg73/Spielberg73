# Referencia de `game.yaml`

Todas las claves se pueden escribir en castellano o en inglés
(`jugador`/`player`, `salto`/`jump`...). Las velocidades van en **píxeles por
frame** (el juego corre a 60 frames por segundo) y los tiempos en **frames**,
salvo donde se diga otra cosa.

Si escribes mal una opción, `ngplat comprobar` te dice cuál es y dónde está.

---

## `juego`

```yaml
juego:
  titulo: "BOSQUE MAGICO"   # sale en la pantalla de título (máx. 24 letras)
  autor: "DAVID"
  jugadores: 1              # 1 o 2 a la vez
  vidas: 3                  # 1 a 9, para cada jugador
  tiempo: 0                 # segundos por nivel; 0 = sin límite
  hud: si                   # marcador de puntos/vidas
  camara: scroll            # scroll o pantallas
  amiga: 32colores          # solo en Amiga: 32colores o 8colores
  fondo: "#101830"          # color de fondo por defecto
  sistema: neogeo           # neogeo, megadrive, amiga, jaguar o atarist
```

`camara` decide cómo se mueve la vista, y cambia bastante a qué se parece el
juego:

| | |
|---|---|
| `scroll` | la cámara sigue al jugador y el escenario se desliza. Es lo que hacían las consolas de la época. |
| `pantallas` | el nivel se reparte en pantallas fijas y la vista **salta** a la siguiente cuando el jugador cruza el borde. Es lo que hacían casi todos los juegos de ordenador de 8 bits. |

Con `pantallas` conviene que los niveles midan un número exacto de pantallas
(múltiplos de 20 tiles de ancho y 14 de alto); si no, la última se solapa con la
anterior y el compilador avisa.

**Lo que cuesta el salto.** Cambiar de pantalla obliga a repintar las veinte
columnas del escenario de una vez, y eso aprieta en las seis máquinas. Cada
una lo lleva a su manera:

| | |
|---|---|
| Neo Geo | rellena diez columnas por frame y apaga las que aún no valen: el cambio se ve como un barrido de dos frames. Sin esto se iba a 214.558 ciclos de los 200.000 que da la consola (medido con el banco del kit). |
| Mega Drive | escribe las veinte columnas del plano en el frame del salto |
| Amiga | repinta con el blitter las veinte columnas: unas 620 líneas de barrido sobre las 313 de un frame, o sea dos o tres frames perdidos en el cambio |
| Jaguar | repinta el mapa de bits entero, como en cualquier otro frame |
| Atari ST | repinta las veinte columnas con la CPU, que es lo que hace siempre; le cuesta un dibujado de los suyos, o sea dos frames de hardware. Y es el único sitio donde el ST dibuja parallax: con la vista quieta, pintarlo sale gratis |
| X68000 | escribe las veinte columnas de la tabla de nombres, como la Mega Drive: una palabra por casilla y el chip hace el resto |

Las seis se comprueban en emulador (`tests/test_sistemas.py`,
`TestCamaraPorPantallas`): que la vista se quede quieta casi todos los frames y
que de vez en cuando cambie de golpe.

`amiga` solo se mira al compilar para Amiga, y decide cómo se reparten sus seis
bitplanes:

| | |
|---|---|
| `32colores` | cinco bitplanes en un solo plano: **31 colores** para los dibujos, sin parallax. |
| `8colores` | tres y tres, en *dual playfield*: el juego delante con **7 colores** y una capa de parallax detrás con otros 7, movida por hardware. |

En `8colores` casi ningún dibujo cabe tal cual, así que los colores que sobran
se cambian por el más parecido de los que quedan y el compilador te dice
cuántos ha tenido que aproximar. Si quieres mandar tú en los colores, dibuja
con siete. Las demás máquinas ignoran esta opción.

`sistema` decide para qué máquina se compila y con qué colores se dibuja el
preview. También se puede elegir sin tocar el archivo, con `--sistema` en
cualquier orden:

```bash
ngplat compilar --sistema megadrive
```

Valen los nombres alternativos de siempre: `genesis` o `md` para la Mega Drive,
`a500` para el Amiga, `aes` o `mvs` para la Neo Geo.

### Dos jugadores

Con `jugadores: 2` juegan dos a la vez, cada uno con su mando, en la misma
pantalla y a la vez (no por turnos). Los dos son el mismo `jugador` del
`game.yaml`: el mismo dibujo, el mismo salto y las mismas vidas; salen juntos
en la salida del nivel, separados 20 píxeles.

Lo que cambia respecto a un jugador:

| | |
|---|---|
| la cámara | va al punto medio de los dos, y no deja que ninguno se salga: el que se queda atrás se para pegado al borde de la pantalla |
| las vidas | son de cada uno, y el marcador pone `1P 3  2P 3` en vez de `LIVES 3` |
| morirse | el que se queda sin vidas desaparece y el otro sigue; el nivel solo se reinicia (o se acaba la partida) cuando caen los dos |
| empezar | vale el start de cualquiera de los dos mandos |

Dónde se enchufa el segundo mando en cada máquina:

| | |
|---|---|
| Neo Geo | el puerto 2 de la placa (`$340000`), con su START y su SELECT en los bits 2 y 3 de STATUS_B |
| Mega Drive | el segundo conector de mandos (`$A10005`) |
| Amiga | el **puerto del ratón**, que es el de la izquierda: hay que quitar el ratón y enchufar ahí el otro joystick. A dos jugadores, el botón del ratón deja de valer de start |
| Atari Jaguar | el segundo conector. Los dos mandos comparten la misma matriz, pero **las filas no se piden con el mismo número** en un puerto que en el otro (ver `engine/jaguar/np_video.c`) |
| Atari ST | el **puerto 0**, que es el del ratón, igual que en el Amiga. El teclado sigue siendo solo del primero |
| X68000 | el **puerto B** del 8255; el A es el del primer jugador |

En el preview, el segundo jugador va con **WASD** y salta con **G**. A un
jugador, WASD sigue valiendo como las flechas.

Las seis se comprueban en emulador (`tests/test_sistemas.py`,
`TestDosJugadores`): se juega la misma partida tres veces, con un mando, con el
otro y con los dos, y las tres tienen que acabar distintas. Si el segundo mando
no llegara, o si los dos leyeran del mismo sitio, saldrían iguales.

## `jugador`

```yaml
jugador:
  sprite: graficos/heroe.png
  frame: [16, 16]      # tamaño de cada fotograma; múltiplo de 16
  caja: [10, 15]       # caja de colisión (por defecto, todo el fotograma)
  velocidad: 1.6       # velocidad máxima al correr
  aceleracion: 0.30    # cuánto acelera por frame en el suelo
  friccion: 0.35       # cuánto frena al soltar el mando
  control_aire: 0.16   # aceleración mientras salta
  salto: 4.3           # impulso inicial del salto
  corte_salto: 1.6     # al soltar el botón, la subida se corta a este valor
  gravedad: 0.28
  max_caida: 6.0
  doble_salto: no
  coyote: 6            # frames de margen para saltar tras salir de un borde
  buffer_salto: 6      # frames de margen para saltar antes de aterrizar
  pisar_enemigos: si
  rebote: 3.6          # impulso al pisar un enemigo
  vida: 1              # golpes que aguanta
  invulnerable: 90     # frames de parpadeo tras un golpe
  retroceso: 3.0       # con cuánta fuerza sales despedido al recibir un golpe
  aturdido: 24         # frames sin control después del golpe (0 = ninguno)
  animaciones:
    quieto: {frames: [0], velocidad: 30}
    correr: {frames: [1, 2, 3, 2], velocidad: 6}
    saltar: {frames: [4]}
    caer:   {frames: [5]}
    atacar: {frames: [6]}     # sólo si el jugador tiene ataque
```

**La hoja de sprites** es un PNG con los fotogramas uno detrás de otro, de
izquierda a derecha. Se numeran desde 0. Máximo **15 colores** más el
transparente por imagen.

**Animaciones**: `frames` es la lista de fotogramas y `velocidad` los frames de
juego que dura cada uno (más alto = más lento). Ranuras que entiende el motor:
`quieto`, `correr`, `saltar`, `caer`, `dano`, `atacar`, `subir`. Si falta
alguna, se usa la más parecida (`caer` cae en `saltar`, y todo lo demás en
`quieto`). `subir` es la de la escalera y `dano` la de recibir un golpe.

Con **`bucle: no`** la animación se queda en el último fotograma en vez de
volver a empezar. Es lo que hace falta en `atacar` cuando el ataque tiene
`preparacion`: el primer fotograma es el brazo saliendo y el segundo el golpe,
y sin `bucle: no` volvería al primero a mitad del latigazo.

```yaml
    atacar: {frames: [6, 7], velocidad: 5, bucle: no}
```

**La caja de colisión** se centra horizontalmente en el fotograma y se apoya en
su borde inferior. Hazla algo más estrecha que el dibujo: se juega mejor.

### El golpe recibido: `retroceso` y `aturdido`

Al recibir daño sales despedido hacia atrás con fuerza `retroceso` y te quedas
`aturdido` frames **sin control**: no aceleras, no frenas, no saltas y no
atacas. El empujón te lleva donde te lleve.

Es una diferencia de género entera. Con `aturdido: 0` (el valor por defecto)
recuperas el mando al momento y un roce es un rasguño; con `aturdido: 24` y un
`retroceso` alto, un roce al borde de una plataforma **te tira al vacío**, y de
eso vive el diseño de niveles de los clásicos de látigo. Si no pones
`retroceso`, se usa tu `velocidad`, que es como se comportaba el kit antes.

Mientras estás aturdido el ataque también se corta: no puedes pegar y cobrar en
el mismo momento.

### `ataque`

Sin esta sección el jugador **sólo puede pisar enemigos** y el botón de acción
no hace nada. Con ella, ataca:

```yaml
jugador:
  ataque:
    tipo: disparo            # disparo o golpe
    sprite: graficos/bala.png
    frame: [16, 16]
    caja: [6, 6]
    desplazamiento: [5, 5]   # la caja, centrada en el fotograma
    velocidad: 3.5           # píxeles por frame que vuela el disparo
    alcance: 96              # px que recorre antes de apagarse
    espera: 18               # frames entre un ataque y el siguiente
    duracion: 8              # frames que dura la pose (y el golpe)
    preparacion: 0           # frames de esos en los que todavía no hace daño
    clavado: no              # si sí, mientras pegas no te mueves
    dano: 1
    mejoras: 0               # cuántas veces se puede mejorar (0 = ninguna)
    alcance_mejora: 12       # px que alarga cada mejora
    animaciones:
      quieto: {frames: [0, 1, 2, 1], velocidad: 4}
```

| tipo | qué hace |
|---|---|
| `disparo` | sale un proyectil que vuela de frente hasta chocar con una pared, dar a un enemigo o agotar su `alcance`. Necesita `sprite` |
| `golpe` | durante `duracion` frames hay una caja de `alcance` píxeles delante del jugador que hace daño a lo que toque. Con `sprite` se **ve** (el látigo); sin él, el golpe es invisible |

El botón va **por flanco**: mantenerlo pulsado no dispara sin parar, y la
cadencia la marca `espera`. Mientras dura el ataque —pegando o disparando— el
jugador usa la animación `atacar` si la has puesto.

#### El arma que se ve

Con `tipo: golpe`, **`sprite:` es el arma**: el látigo, la espada o lo que sea.
Se dibuja pegado al costado del jugador **sólo mientras el golpe hace daño**
—o sea, pasada la `preparacion`— así que lo que se ve en pantalla es
exactamente lo que pega. Al mirar a la izquierda sale espejado y sigue saliendo
del mango.

```yaml
jugador:
  ataque:
    tipo: golpe
    sprite: graficos/latigo.png
    frame: [48, 16]          # el fotograma entero es el arma
    caja: [48, 16]
    desplazamiento: [0, 0]   # sin desplazar: arranca donde acaba el jugador
    alcance: 24
    mejoras: 2
    alcance_mejora: 12       # 24 -> 36 -> 48 px
    animaciones:
      quieto: {frames: [0, 1, 2]}   # un fotograma por nivel del arma
```

**Cada fotograma es un nivel de mejora**: el motor enseña el 0 con el arma de
serie, el 1 con una mejora y el 2 con dos. Dibuja cada uno de lo que mide su
alcance (aquí 24, 36 y 48 px) y la mejora se verá, además de notarse. Si la
hoja tiene menos fotogramas que niveles, se queda en el último.

El arma es una entidad más de la lista mientras se ve, así que ocupa uno de los
64 huecos; si no queda ninguno, el golpe pega igual pero sin dibujarse.

Sin `sprite:` el golpe no dibuja nada, que es como funcionaba el kit antes: el
jugador cambia a la pose `atacar` y ya.

**`preparacion`** son los primeros frames del golpe en los que el brazo todavía
está saliendo: se ve, pero no hace daño. Es lo que separa medir la distancia de
machacar el botón. Tiene que ser menor que `duracion` (si no, el golpe no
llegaría a tocar nunca, y `ngplat` no compila).

**`clavado: si`** te planta en el sitio mientras dura el golpe: en el suelo no
andas ni te giras. **En el aire no**: si saltas y pegas, conservas el impulso,
que es como se juega en los clásicos.

Los proyectiles viven en la misma lista que enemigos y objetos, así que caben
64 cosas a la vez en pantalla contándolos; si no queda hueco, el disparo se
pierde. Uno que sale de la pantalla se apaga solo.

`ngplat nuevo` ya te deja un ataque de ejemplo montado, con su `bala.png` y su
sonido (`sonido: efectos: disparo:`).

#### Mejorar el arma

Con **`mejoras:`** el arma se puede alargar durante la partida, que es el
látigo de los clásicos: cada objeto con `efecto: mejora` (ver
[`objetos`](#objetos)) sube un nivel y cada nivel suma `alcance_mejora` píxeles
de alcance, hasta el tope que marque `mejoras`.

```yaml
jugador:
  ataque:
    tipo: golpe
    alcance: 24              # de serie
    mejoras: 2               # dos mejoras: 24 -> 36 -> 48 px
    alcance_mejora: 12
```

Vale igual con `tipo: disparo`, y entonces lo que crece es lo que vuela el
proyectil antes de apagarse.

Las mejoras **se pierden al morir** y al empezar un nivel nuevo: reapareces
siempre con el arma de serie. Es lo que hace que una vida valga algo. Con
`mejoras: 0` (lo de por defecto) el objeto no hace nada y el arma es siempre la
misma.

### `secundaria` (el arma que gasta munición)

```yaml
jugador:
  secundaria:
    tipo: recta              # recta | arco
    sprite: graficos/cuchillo.png
    frame: [16, 16]
    caja: [10, 4]
    desplazamiento: [3, 6]
    velocidad: 4.0
    gravedad: 0.25           # sólo cuenta en arco
    salto: 3.0               # impulso hacia arriba al salir, sólo en arco
    alcance: 200
    espera: 24
    coste: 1                 # munición que gasta cada tirada
    dano: 1
```

Se lanza con **arriba + acción**, y gasta munición. El botón a secas sigue
haciendo el ataque de siempre, y si no te queda munición, arriba + acción
también pega: nunca te quedas sin nada que hacer.

| tipo | qué hace |
|---|---|
| `recta` | vuela de frente, como el disparo del ataque normal |
| `arco` | sale hacia arriba con `salto` y la `gravedad` lo va bajando: cae describiendo una parábola y se apaga al tocar el suelo |

La munición la dan los objetos con `efecto: municion` (y la sueltan los
rompibles). **Ojo con el nombre**: `efecto: corazon` a secas significa *salud*,
que es otra cosa; la munición es `municion`, `municiones` o `hearts`.

La munición se vacía al empezar cada nivel, igual que las llaves, y el marcador
la enseña como `AMMO 05` mientras el juego lleve arma secundaria.

### Escaleras

```yaml
tiles:
  leyenda:
    '/': {tile: 6, tipo: escalera}             # sube hacia la derecha
    '|': {tile: 7, tipo: escalera_izquierda}   # sube hacia la izquierda

jugador:
  velocidad_escalera: 0.8    # 0 = el juego no tiene escaleras
```

Una escalera es un **segundo modo de movimiento**, no un tile más: mientras
estás subido no hay gravedad, ni saltos, ni choques con el escenario. Se avanza
en diagonal con arriba y abajo, y no se puede andar de lado.

Se dibujan en diagonal, un escalón por casilla:

```
      ......####      suelo de arriba
      ...../....
      ..../.....
      .../......
      ##########      suelo de abajo
```

- **Subirse**: estando de pie, pulsando arriba cuando estás en la casilla del
  escalón; o pulsando abajo cuando el primer escalón está en diagonal justo
  debajo (que es como se baja desde el suelo de arriba).
- **Bajarse**: se sale sola por los dos extremos. Al salirse, el jugador se
  queda **de pie en la fila donde acaba**, así que el escalón de arriba tiene
  que llegar hasta el suelo de arriba y el de abajo hasta el de abajo; si la
  escalera acaba en el aire, te caes.
- Desde la escalera **se puede atacar** (en los clásicos también), pero no
  saltar.
- **Un golpe te tira de la escalera**: el empujón te lleva y pierdes el control
  igual que en el suelo.
- Las escaleras **no frenan a nadie**: se pasa por delante andando, como por un
  decorado. Sólo cuentan cuando decides subirte.

Sin `velocidad_escalera` se sube a la mitad de lo que se anda. Con `0` el juego
no tiene escaleras y los tiles se quedan de adorno.

### Puntos de control

```yaml
tiles:
  leyenda:
    '!': {tile: 8, tipo: control}
```

Un punto de control **no estorba**: se pasa por delante como por un decorado.
Lo que hace es apuntar su casilla al tocarla, y si te matan y te quedan vidas
reapareces ahí en vez de al principio del nivel. Es lo que permite hacer
niveles largos sin que morir sea un castigo.

- reapareces **de pie encima de la casilla marcada** y centrado en su columna,
  así que la marca se pone en la fila donde quieres caer (normalmente la de
  encima del suelo), y da igual por dónde pasaras al tocarla;
- **manda el último por el que pasas**, aunque sea uno anterior: si retrocedes
  a por algo y vuelves a cruzar el de antes, ese pasa a ser el bueno;
- volver a pasar por el que ya está marcado **no hace nada** (ni suena);
- el resto del nivel **vuelve a empezar** igual que siempre: los enemigos, los
  objetos y los candelabros salen otra vez donde salían;
- cambiar de nivel **lo borra**: cada nivel empieza sin punto de control.

A dos jugadores es de la partida, no de cada uno: el que muere vuelve al último
que haya tocado cualquiera de los dos.

Con el `evento: control` de `sonido:` le pones sonido al momento de tocarlo.

## `rompibles`

```yaml
rompibles:
  candelabro:
    sprite: graficos/candelabro.png
    caja: [8, 12]
    suelta: corazon        # nombre de un objeto de 'objetos:'
    puntos: 100
    vida: 1                # golpes que aguanta
    animaciones:
      quieto: {frames: [0, 1], velocidad: 8}
```

Un rompible **no hace nada** hasta que le pegas: no te toca, no hace daño y no
se puede pisar. Al romperlo suelta el objeto de `suelta:` justo donde estaba
—apoyado en el mismo suelo— y da sus `puntos`. Sin `suelta:` simplemente
desaparece.

Es el bucle de los clásicos de látigo: pegarle a todo, a ver qué cae. Se
colocan en el mapa con su símbolo, como los enemigos:

```yaml
spawns:
  V: candelabro
```

Detalles que conviene saber:

- Lo rompe tanto el ataque normal (`golpe` o `disparo`) como el arma
  secundaria.
- Lo que suelta ocupa **la misma ranura** de la lista de entidades que ocupaba
  el rompible, así que nunca puede quedarse sin sitio: una vida extra dentro de
  un candelabro no se pierde por estar la pantalla llena.
- Con `vida:` mayor que uno hacen falta varios ataques, no varios frames: lo
  que ya está parpadeando no se vuelve a tocar hasta que se le pasa.
- Si `suelta:` nombra algo que no está en `objetos:`, `ngplat` no compila.

## `tiles`

```yaml
tiles:
  imagen: graficos/tiles.png   # tiles de 16x16 en fila, numerados desde 0
  leyenda:
    '.': {tile: 0, tipo: vacio}
    '#': {tile: 1, tipo: solido}
    '=': {tile: 2, tipo: plataforma}
    '^': {tile: 3, tipo: peligro}
    'G': {tile: 4, tipo: meta}
    ',': {tile: 5, tipo: solido}
```

Tipos:

| tipo | efecto |
|---|---|
| `vacio` | no estorba |
| `solido` | bloquea por los cuatro lados |
| `plataforma` | solo frena si caes encima; se atraviesa saltando desde abajo y se baja con ↓ |
| `peligro` | mata al tocarlo (pinchos, lava) |
| `meta` | termina el nivel |
| `escalera` | escalera que **sube hacia la derecha** |
| `escalera_izquierda` | escalera que **sube hacia la izquierda** |
| `control` | punto de control: no estorba, pero apunta dónde reapareces |
| `decor` | se dibuja, no estorba |

Atajos: `'#': 3` equivale a `{tile: 3, tipo: solido}`, y `'#': [3, plataforma]`
también vale.

Si no pones `leyenda`, se usa la de por defecto (`.` vacío, `#` sólido, `=`
plataforma, `^` peligro, `G` meta).

## `enemigos`

```yaml
enemigos:
  seta:
    sprite: graficos/enemigo.png
    caja: [14, 12]
    comportamiento: patrulla
    velocidad: 0.4
    vida: 1              # golpes que aguanta
    dano: 1              # vida que quita al jugador
    puntos: 100
    pisable: si
    girar_en_borde: si
    jefe: no             # si -> matarlo termina el nivel
    animaciones:
      quieto: {frames: [0, 1], velocidad: 14}
```

Comportamientos:

| comportamiento | qué hace | opciones propias |
|---|---|---|
| `patrulla` | anda y da la vuelta en paredes y bordes | `girar_en_borde` |
| `volador` | flota subiendo y bajando, ignora la gravedad | `amplitud`, `periodo` |
| `perseguidor` | va hacia el jugador si está cerca | `rango` |
| `saltarin` | salta cada cierto tiempo | `salto`, `intervalo` |
| `fijo` | no se mueve | — |

**Jefes.** Un enemigo con `jefe: si` es el jefe del nivel: sube su `vida` para
que aguante varios pisotones, el marcador enseña una barra con lo que le queda
(`BOSS ######`) y **matarlo termina el nivel**, igual que llegar a la meta. Un
nivel con jefe no necesita tile de `meta`.

```yaml
enemigos:
  jefazo:
    sprite: graficos/enemigo.png
    comportamiento: perseguidor
    vida: 5
    puntos: 1000
    jefe: si
```

## `objetos`

```yaml
objetos:
  moneda:
    sprite: graficos/moneda.png
    caja: [10, 10]
    puntos: 10
    efecto: puntos       # puntos | vida | salud | llave | municion | mejora
    cantidad: 1
    animaciones:
      quieto: {frames: [0, 1, 2, 3], velocidad: 7}
```

**Llaves.** Un objeto con `efecto: llave` suma `cantidad` al contador de llaves
de la partida, y un nivel con `llaves: N` no abre la meta hasta que se lleven N.
Las llaves son **de la partida, no de cada jugador**: a dos, la que coge uno le
vale al otro. Se vacían al empezar cada nivel, y el marcador enseña `KEYS 01/03`
mientras el nivel pida alguna. Si un nivel pide más llaves de las que hay
puestas en su mapa, `ngplat` no compila: no se podría terminar.

**Mejoras del arma.** Un objeto con `efecto: mejora` sube `cantidad` niveles el
arma del jugador y la alarga (ver [`ataque`](#mejorar-el-arma)). Se para en el
tope que marque `mejoras:`, y si el ataque no admite ninguna el objeto no hace
nada. A diferencia de las llaves, el nivel del arma es **de cada jugador**, y se
pierde al morir.

## `plataformas`

```yaml
plataformas:
  tablon:
    sprite: graficos/plataforma.png
    frame: [32, 16]
    caja: [32, 6]        # solo la parte de arriba: es donde se pisa
    movimiento: horizontal   # horizontal | vertical
    velocidad: 0.6           # pixeles por frame
    distancia: 48            # recorrido desde donde sale, en pixeles
```

Una plataforma movil va y viene entre donde la pone el mapa y `distancia`
pixeles mas alla (a la derecha si `movimiento: horizontal`, hacia abajo si es
`vertical`), y **el que se sube encima va con ella**. No hace dano, no se puede
matar y no cuenta como enemigo: es escenario que se mueve.

Se apoya como un tile de `plataforma`: sólo se aterriza **cayendo y desde
arriba**, por debajo se pasa a través, y pulsando abajo te dejas caer. Se
colocan en el mapa con su símbolo, igual que los enemigos y los objetos:

```yaml
spawns:
  T: tablon
```

La caja de colisión suele ser sólo la franja de arriba del dibujo (`caja: [32,
6]` en un fotograma de 32×16): así el jugador se planta sobre la tabla y no
flotando encima del hueco.

## `fondos` (parallax)

Capas de fondo con scroll propio. Se escriben de la **mas lejana a la mas
cercana** y son solo decorado: no chocan con nada.

```yaml
fondos:
  - nombre: cielo
    imagen: graficos/cielo.png   # ancho y alto multiplos de 16
    velocidad: 0.2               # fraccion del scroll: 0 = quieta, 1 = como el suelo
    y: 0                         # donde empieza en la pantalla, en pixeles
    repetir: si                  # se repite en horizontal (por defecto si)
    velocidad_y: 0               # opcional, scroll vertical
```

Cada capa lleva su propia paleta de 15 colores, y los tiles repetidos (un cielo
en degradado repite muchisimo) se guardan una sola vez en la ROM.

Por defecto todos los niveles usan todas las capas. Un nivel puede elegir las
suyas:

```yaml
niveles:
  - nombre: "CUEVA"
    fondos: [cielo]      # solo la capa lejana
    mapa: |
      ...
```

Limites: la capa no puede pasar de 14 tiles de alto (224 px) y cada capa gasta
21 sprites de los 381 de la consola, asi que con dos o tres capas vas sobrado.

## `sonido`

El chip de la Neo Geo (YM2610) tiene tres canales de onda cuadrada: **dos para
la música y uno para los efectos**. Todo se escribe con notas, en castellano
(`do re mi fa sol la si`) o en inglés (`c d e f g a b`), con `#` o `b` para las
alteraciones, el número de octava detrás y `-` para los silencios. `|` separa
compases y no suena.

```yaml
sonido:
  efectos:
    empezar: {notas: "do5 sol5", velocidad: 4}
    salto:   {tipo: barrido, desde: 320, hasta: 900, duracion: 6}
    moneda:  {notas: "mi6 sol6", velocidad: 3}
    golpe:   {tipo: ruido, duracion: 10}
  musica:
    bosque:
      velocidad: 8        # frames que dura cada nota (más alto = más lento)
      volumen: 11         # 0 a 15
      bucle: si
      pistas:
        - "do4 mi4 sol4 mi4 | fa4 la4 do5 la4"    # canal A: melodía
        - "do3 -   do3 -    | fa3 -   fa3 -"      # canal B: acompañamiento
```

### Lo que enseña el marcador

Sale solo, sin configurar nada, y cada trozo aparece únicamente si el juego lo
usa:

| trozo | cuándo sale |
|---|---|
| `SCORE`, `LIVES` | siempre |
| `TIME` | con `tiempo:` distinto de 0 |
| `KEYS 01/03` | en los niveles con `llaves:` |
| `AMMO 05` | con arma `secundaria:` |
| `BOSS ####` | con un jefe en pantalla |
| `LIFE ###.` | con `vida:` mayor que 1 |

La barra de vida lleva un cuadrado por golpe: los llenos (`#`) son los que te
quedan y los puntos (`.`) los que has perdido, así que se ve a la vez cuánto
aguantas y cuánto aguantabas entero. A dos jugadores sale una por cabeza
(`1P ###` y `2P ###`). Fuera de la partida se apaga: en el Amiga, la Jaguar y
el Atari ST el marcador es una banda de tres filas y esa tercera fila es la que
usan el título y el *game over*.

**Momentos que puedes sonorizar** (los produce el juego solo): `empezar`,
`salto`, `doble_salto`, `moneda`, `pisar`, `golpe`, `muerte`, `meta`, `vida`,
`disparo`, `romper` (un rompible) y `control` (tocar un punto de control).

**Tipos de efecto**:

| tipo | para qué sirve | opciones |
|---|---|---|
| `notas` | melodías cortas (moneda, meta) | `notas`, `velocidad`, `volumen` |
| `barrido` | saltos y disparos: la frecuencia sube o baja | `desde`, `hasta`, `duracion` |
| `ruido` | golpes y explosiones | `duracion`, `tono` |

### Muestras digitales (`muestra:`)

Un efecto puede ser **sonido grabado** en vez de notas: una voz, una batería,
un golpe de verdad. Se apunta a un WAV del proyecto:

```yaml
sonido:
  efectos:
    moneda:  {muestra: sonidos/moneda.wav, notas: "mi6 sol6", velocidad: 3}
    golpe:   {muestra: sonidos/golpe.wav, tipo: ruido, duracion: 10}
```

El WAV tiene que ser **PCM sin comprimir**, mono o estéreo, de 8 o 16 bits, a
cualquier frecuencia, y durar como mucho 4 segundos; el compilador lo pasa a
mono de 8 bits y lo remuestrea a lo que use cada máquina. `ngplat nuevo` ya te
deja dos de ejemplo en `sonidos/`.

`muestra:` **no sustituye a `tipo:`**: puedes poner las dos cosas, y entonces
las notas son el recambio para la máquina que no sabe tocar sonido grabado,
que es una sola:

| | |
|---|---|
| Amiga | sí: es lo que hace Paula de serie, leyendo el sonido de la RAM chip por DMA |
| Atari Jaguar | sí: el DSP las lee del cartucho, byte a byte, y las mezcla con las ondas cuadradas |
| Mega Drive | sí: el DAC está en el YM2612 y se lo da el Z80, con un driver que también genera el compilador |
| Neo Geo | sí: los canales ADPCM-A del YM2610, que leen solos de la ROM V1 |
| Atari ST | **nunca**: el YM2149 sólo hace ondas cuadradas |

En el Atari ST suenan las notas, y si un efecto es sólo muestra el compilador
te avisa de que ahí se quedará mudo.

La música sigue siendo siempre de notas: las muestras son para los efectos.

Cada nivel elige su música:

```yaml
niveles:
  - nombre: "BOSQUE"
    musica: bosque
```

Duraciones: `do4:2` dura el doble. Límites: 46 efectos, 14 músicas, 2 pistas
por música (el tercer canal se reserva para los efectos) y notas entre `do1` y
`do8` aproximadamente.

## `spawns`

Relaciona símbolos del mapa con enemigos y objetos:

```yaml
spawns:
  s: seta
  m: mosca
  c: moneda
```

Se puede poner a nivel global o dentro de un nivel concreto (lo del nivel manda).

## `niveles`

```yaml
niveles:
  - nombre: "BOSQUE"
    fondo: "#101830"
    llaves: 1               # llaves que hay que llevar para abrir la meta
    spawns: {b: jefe}       # opcional, se suma a los globales
    mapa: |
      ....................
      P..................G
      ####################
```

Reglas del mapa:

- Cada carácter es un tile de 16x16 píxeles.
- **`P`** marca dónde empieza el jugador: exactamente una por nivel.
- Mínimo 20 columnas × 14 filas (lo que ocupa una pantalla), máximo 512 × 256.
- Las filas más cortas se rellenan con vacío por la derecha.
- Máximo 64 enemigos, objetos y plataformas por nivel.
- Si un nivel no tiene tile de `meta` ni jefe, `ngplat` te avisa (no se podría
  terminar).
- Con `llaves: N`, en el mapa tiene que haber al menos N llaves (ver
  [`objetos`](#objetos)).

Los niveles se juegan en orden; al terminar el último sale `YOU WIN!`.

---

## Límites de cada máquina

Estos son los del juego, valgan para la que valgan:

| Cosa | Límite | Qué pasa si te pasas |
|---|---|---|
| Colores por imagen | 15 + transparente | error al compilar, con el número de colores |
| Entidades por nivel | 64 | error al compilar |
| Tamaño del nivel | 512 × 256 tiles | error al compilar |
| Efectos de sonido | 46 | error al compilar |
| Músicas | 14, de 2 pistas | error al compilar |
| Símbolos de tile | 255 | error al compilar |

Y estos cambian según la máquina. `ngplat comprobar` los mira antes de
compilar y te dice cuál te has saltado.

| | Neo Geo | Mega Drive | Amiga | Jaguar |
|---|---|---|---|---|
| Colores a la vez | 4096 | 64 (4 paletas de 16) | 32, o 8 + 8 | 256 (una tabla) |
| Paletas | 256 | 4, fundiendo las tuyas | 1, fundiendo las tuyas | 1, fundiendo las tuyas |
| Dibujos distintos | 65536 tiles | 1408 tiles de 8 × 8 | 1024 de 16 × 16 | sin límite fijo |
| Actores en pantalla | 96 sprites | 80 sprites | sin límite fijo (los dibuja el blitter) | sin límite fijo |
| Alto del nivel | 256 tiles | 32 tiles | 16 tiles | 16 tiles |
| Capas de parallax | todas | una | una, con `amiga: 8colores` | una |
| Sonido | YM2610 | PSG SN76489 | Paula | los DAC, por el DSP |
| Qué sale | ROMs de cartucho | `.bin` de cartucho | disquete `.adf` | cartucho `.j64` |

`ngplat sistemas` los enseña sin salir de la terminal.
