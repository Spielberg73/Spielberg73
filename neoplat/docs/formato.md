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
  fondo: "#101830"          # color de fondo por defecto
```

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

## Límites de la consola

| Cosa | Límite | Qué pasa si te pasas |
|---|---|---|
| Colores por imagen | 15 + transparente | error al compilar, con el número de colores |
| Entidades por nivel | 64 | error al compilar |
| Tamaño del nivel | 512 × 256 tiles | error al compilar |
| Paletas | 256 en total | error al compilar |
| Sprites en pantalla | 96 para actores | los que sobran no se dibujan |
| Capas de fondo | 21 sprites cada una | con 2 o 3 vas sobrado |
| Símbolos de tile | 255 | error al compilar |
