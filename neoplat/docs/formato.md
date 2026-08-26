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
  vidas: 3                  # 1 a 9
  tiempo: 0                 # segundos por nivel; 0 = sin límite
  hud: si                   # marcador de puntos/vidas
  camara: scroll            # scroll o pantallas
  amiga: 32colores          # solo en Amiga: 32colores o 8colores
  fondo: "#101830"          # color de fondo por defecto
  sistema: neogeo           # neogeo, megadrive, amiga o jaguar
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
columnas del escenario de una vez, y eso aprieta en las cuatro máquinas. Cada
una lo lleva a su manera:

| | |
|---|---|
| Neo Geo | rellena diez columnas por frame y apaga las que aún no valen: el cambio se ve como un barrido de dos frames. Sin esto se iba a 214.558 ciclos de los 200.000 que da la consola (medido con el banco del kit). |
| Mega Drive | escribe las veinte columnas del plano en el frame del salto |
| Amiga | repinta con el blitter las veinte columnas: unas 620 líneas de barrido sobre las 313 de un frame, o sea dos o tres frames perdidos en el cambio |
| Jaguar | repinta el mapa de bits entero, como en cualquier otro frame |

Las cuatro se comprueban en emulador (`tests/test_sistemas.py`,
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
  animaciones:
    quieto: {frames: [0], velocidad: 30}
    correr: {frames: [1, 2, 3, 2], velocidad: 6}
    saltar: {frames: [4]}
    caer:   {frames: [5]}
```

**La hoja de sprites** es un PNG con los fotogramas uno detrás de otro, de
izquierda a derecha. Se numeran desde 0. Máximo **15 colores** más el
transparente por imagen.

**Animaciones**: `frames` es la lista de fotogramas y `velocidad` los frames de
juego que dura cada uno (más alto = más lento). Ranuras que entiende el motor:
`quieto`, `correr`, `saltar`, `caer`, `hurt`. Si falta alguna, se usa la más
parecida (`caer` cae en `saltar`, y todo lo demás en `quieto`).

**La caja de colisión** se centra horizontalmente en el fotograma y se apoya en
su borde inferior. Hazla algo más estrecha que el dibujo: se juega mejor.

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

## `objetos`

```yaml
objetos:
  moneda:
    sprite: graficos/moneda.png
    caja: [10, 10]
    puntos: 10
    efecto: puntos       # puntos | vida | salud | llave
    cantidad: 1
    animaciones:
      quieto: {frames: [0, 1, 2, 3], velocidad: 7}
```

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

**Momentos que puedes sonorizar** (los produce el juego solo): `empezar`,
`salto`, `doble_salto`, `moneda`, `pisar`, `golpe`, `muerte`, `meta`, `vida`.

**Tipos de efecto**:

| tipo | para qué sirve | opciones |
|---|---|---|
| `notas` | melodías cortas (moneda, meta) | `notas`, `velocidad`, `volumen` |
| `barrido` | saltos y disparos: la frecuencia sube o baja | `desde`, `hasta`, `duracion` |
| `ruido` | golpes y explosiones | `duracion`, `tono` |

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
- Máximo 64 enemigos y objetos por nivel.
- Si un nivel no tiene tile de `meta`, `ngplat` te avisa (no se podría terminar).

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
| Capas de parallax | todas | una | una, con `amiga: 8colores` | ninguna (todavía) |
| Sonido | YM2610 | PSG SN76489 | Paula | los DAC, por el DSP |
| Qué sale | ROMs de cartucho | `.bin` de cartucho | disquete `.adf` | cartucho `.j64` |

`ngplat sistemas` los enseña sin salir de la terminal.
