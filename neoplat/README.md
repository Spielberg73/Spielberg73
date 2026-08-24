# NeoPlat

Kit para hacer juegos de plataformas 2D **sin programar** y compilarlos para
**Neo Geo** (AES/MVS).

Describes el juego en un archivo `game.yaml`, dibujas los gráficos en PNG y el
compilador genera el proyecto en C, las ROMs gráficas y un **preview jugable en
el navegador** para probar los cambios en segundos.

```
game.yaml + PNG  ──►  ngplat  ──┬──►  preview.html   (jugable al momento)
                                └──►  build/         (C + ROMs para ngdevkit)
```

## Instalación

Ninguna. Solo necesitas **Python 3.7 o superior**:

```bash
git clone <este repo>
cd neoplat
./ngplat --version
```

No usa dependencias externas: trae su propio lector de PNG y su propio lector
de YAML (si tienes PyYAML instalado, lo aprovecha).

Para generar la ROM final necesitas además
[ngdevkit](https://github.com/dciabrin/ngdevkit), que aporta el compilador de
68000 (`m68k-neogeo-elf-gcc`) y el emulador `ngdevkit-gngeo`.

## Empezar

```bash
./ngplat nuevo mijuego      # crea un juego completo de ejemplo
cd mijuego
../ngplat probar            # abre el preview jugable en el navegador
../ngplat compilar          # genera build/ con el C y las ROMs gráficas
cd build && make            # construye la ROM (necesita ngdevkit)
make run                    # la arranca en el emulador
```

Controles del preview: flechas para moverte, <kbd>Z</kbd> o <kbd>espacio</kbd>
para saltar, <kbd>↓</kbd> para bajar de una plataforma, <kbd>Enter</kbd> para
empezar, <kbd>R</kbd> para reiniciar.

## Cómo es un juego

Todo el juego cabe en un archivo. Los mapas se dibujan con caracteres:

```yaml
juego:
  titulo: "BOSQUE MAGICO"
  vidas: 3

jugador:
  sprite: graficos/heroe.png
  caja: [10, 15]
  velocidad: 1.6
  salto: 4.3
  gravedad: 0.28
  animaciones:
    quieto: {frames: [0], velocidad: 30}
    correr: {frames: [1, 2, 3, 2], velocidad: 6}

enemigos:
  seta:
    sprite: graficos/enemigo.png
    comportamiento: patrulla      # patrulla, volador, perseguidor, saltarin, fijo
    velocidad: 0.4

objetos:
  moneda: {sprite: graficos/moneda.png, puntos: 10}

fondos:                          # capas de parallax, de lejos a cerca
  - {nombre: cielo, imagen: graficos/cielo.png, velocidad: 0.2, y: 0}
  - {nombre: arboles, imagen: graficos/arboles.png, velocidad: 0.5, y: 144}

sonido:
  efectos:
    salto: {tipo: barrido, desde: 320, hasta: 900, duracion: 6}
    moneda: {notas: "mi6 sol6", velocidad: 3}
  musica:
    bosque:
      pistas:
        - "do4 mi4 sol4 mi4 | fa4 la4 do5 la4"
        - "do3 -   do3 -    | fa3 -   fa3 -"

spawns: {s: seta, c: moneda}

niveles:
  - nombre: "BOSQUE"
    mapa: |
      ..........ccc.......
      .........=====......
      ....c.........c.....
      ...====......====...
      ....................
      ..........c.........
      ....................
      ....................
      ....................
      ....................
      ....................
      .........^^.........
      P....s...##.......G.
      ####################
```

`P` es la salida del jugador, `G` la meta, `#` bloque sólido, `=` plataforma
que se atraviesa desde abajo, `^` pinchos. Los demás símbolos los defines tú.

La referencia completa está en [docs/formato.md](docs/formato.md) y hay un
tutorial paso a paso en [docs/tutorial.md](docs/tutorial.md).

## Órdenes

| Orden | Qué hace |
|---|---|
| `ngplat nuevo <carpeta>` | Crea un proyecto jugable con gráficos de ejemplo |
| `ngplat comprobar [proyecto]` | Valida el `game.yaml` y dice cuánto ocupa el juego |
| `ngplat probar [proyecto]` | Genera y abre el preview del navegador |
| `ngplat compilar [proyecto]` | Genera `build/` con el C, las ROMs gráficas y el Makefile |
| `ngplat compilar --make` | Además construye la ROM (necesita ngdevkit) |

Todas las órdenes tienen alias en inglés (`new`, `check`, `preview`, `build`).

## Qué hay dentro

```
neoplat/
├── ngplat                  la orden (Python, sin dependencias)
├── tools/ngplat/           compilador: YAML → C + ROMs + preview
│   ├── project.py          lee y valida game.yaml (mensajes en castellano)
│   ├── gfx.py              PNG → paletas y tiles de Neo Geo (C ROM / S ROM)
│   ├── build.py            empaqueta gráficos, tiles y niveles
│   ├── codegen.py          genera gamedata.c/h, ROMs y Makefile
│   ├── sonido.py           notas -> periodos del chip de sonido
│   ├── m1.py / z80.py      driver de sonido del Z80 y su ensamblador
│   ├── preview.py          genera el preview jugable
│   ├── png.py / miniyaml.py  lectores propios (cero dependencias)
│   └── art.py / scaffold.py  el proyecto de ejemplo
├── engine/
│   ├── core/np_world.c     la simulación (física, colisiones, enemigos)
│   ├── neogeo/             vídeo, HUD, sonido y mando de la consola
│   └── host/np_trace.c     ejecuta la simulación en el ordenador (pruebas)
├── preview/np_core.js      la misma simulación, en JavaScript
├── examples/bosque-magico/ juego de ejemplo listo para compilar
└── tests/                  92 pruebas + 24 de jugabilidad + bot que se pasa
                            los niveles
```

**El motor es C, no C++**, a propósito: el compilador de ngdevkit no trae
libstdc++, y en un 68000 a 12 MHz las llamadas virtuales y las plantillas solo
añaden coste. La lógica del juego la genera el compilador, así que no escribes
C de todos modos.

## La misma simulación en los dos sitios

`engine/core/np_world.c` (Neo Geo) y `preview/np_core.js` (navegador) son la
misma simulación escrita dos veces: enteros y coma fija 24.8, sin decimales.
`tests/test_paridad.py` ejecuta las dos con las mismas pulsaciones y compara
frame a frame la posición, la velocidad, la cámara, la puntuación y un hash de
todas las entidades. Si tocas una y te olvidas de la otra, la prueba falla.

Por eso lo que juegas en el navegador es exactamente lo que va a pasar en la
consola.

## Pruebas

```bash
make test          # herramientas, validación, generación de C y paridad C/JS
node tests/comportamiento.js   # 24 pruebas de jugabilidad
```

Lo que comprueban: el lector de PNG contra Pillow, el lector de YAML contra
PyYAML, ida y vuelta de los formatos de tile de Neo Geo, los mensajes de error
del `game.yaml`, que el C generado compile sin avisos (`-Wall -Wextra
-Werror`), la paridad C/JavaScript y las mecánicas (salto variable, coyote
time, buffer de salto, plataformas de un sentido, pisar enemigos, daño,
muerte, cambio de nivel, cámara).

## Estado y limitaciones

Verificado aquí:

- El proyecto en C generado compila con `gcc -Wall -Wextra -Werror`.
- Motor en C y preview en JavaScript dan resultados idénticos frame a frame.
- Las mecánicas de plataformas funcionan (24 pruebas de jugabilidad).
- Los niveles de ejemplo se pueden terminar: un bot los juega enteros en cada
  prueba, así que nunca se cuela un nivel imposible.
- El preview se abre en Chromium durante las pruebas y se comprueba que dibuja
  lo que debe (capturas de pantalla revisadas a mano).
- El driver de sonido del Z80 se ejecuta en un emulador incluido en las pruebas:
  se comprueba que recibe las órdenes del 68000 y escribe en el chip los
  periodos y volúmenes de las notas escritas en el `game.yaml`.

**Todavía sin verificar en hardware ni emulador**: el kit convierte los
gráficos al formato de la Neo Geo y programa el chip de vídeo según la
documentación de hardware (ver [docs/neogeo.md](docs/neogeo.md)), pero no he
podido ejecutar la ROM: aquí no hay ngdevkit ni emulador instalados. La
conversión de tiles está probada de ida y vuelta (codificar + decodificar da la
imagen original), lo que garantiza que el formato es coherente, no que sea el
que espera el chip. Si al arrancar la ROM ves los gráficos revueltos, lo más
probable es que haya que ajustar el orden de bytes descrito en `docs/neogeo.md`
(está aislado en dos funciones de `tools/ngplat/gfx.py`).

Lo que aún no hace:

- **Muestras digitales** (ROM V1): la música y los efectos usan los canales de
  onda cuadrada del chip; las voces y percusiones sampleadas aún no.
- **Jefes o eventos guionizados**: hay cinco comportamientos de enemigo fijos.
- **Dos jugadores**.
- **Zoom de sprites** (la Neo Geo lo permite; el motor no lo usa).

## Licencia

Haz lo que quieras con él.
