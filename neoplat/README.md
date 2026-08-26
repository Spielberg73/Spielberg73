# NeoPlat

Kit para hacer juegos de plataformas 2D **sin programar** y compilarlos para
cuatro máquinas de verdad: **Neo Geo** (AES/MVS), **Mega Drive** (Genesis),
**Amiga** (OCS/ECS) y **Atari Jaguar**.

Describes el juego en un archivo `game.yaml`, dibujas los gráficos en PNG y el
compilador genera el proyecto en C, los gráficos ya convertidos al formato de
cada chip y un **preview jugable en el navegador** para probar los cambios en
segundos.

```
                                ┌──►  preview.html          (jugable + editor)
                                │
game.yaml + PNG  ──►  ngplat  ──┼──►  build/neogeo/         ROMs C1/C2/S1/M1
                                ├──►  build/megadrive/      cartucho .bin
                                ├──►  build/amiga/          disquete .adf
                                └──►  build/jaguar/         cartucho .j64
```

El juego lo describes una vez. Lo que cambia de una máquina a otra es cómo se
dibuja y cómo suena, no lo que pasa: la simulación (`engine/core/np_world.c`)
es la misma en las cuatro, así que un salto mide exactamente lo mismo en todas.
Y las cuatro llevan un **68000**, que es lo que hace que el motor sea uno solo.

| | Neo Geo | Mega Drive | Amiga | Jaguar |
|---|---|---|---|---|
| CPU | 68000 a 12 MHz | 68000 a 7,6 MHz | 68000 a 7 MHz | 68000 a 13,3 MHz |
| Escenario | columnas de sprites | plano A del VDP | mapa de bits + blitter | mapa de bits lineal |
| Actores | sprites | sprites del VDP | blitter con máscara | objetos del chip |
| Colores | 4096 en pantalla | 4 paletas de 16 | una paleta de 32 | una tabla de 256 |
| Sonido | YM2610 (SSG) por Z80 | PSG SN76489 | Paula (4 canales) | todavía no |
| Parallax | sí | una capa | todavía no | todavía no |
| Sale | ROMs de cartucho | `.bin` con cabecera y suma | disquete `.adf` arrancable | cartucho `.j64` |

## Instalación

Ninguna. Solo necesitas **Python 3.7 o superior**:

```bash
git clone <este repo>
cd neoplat
./ngplat --version
```

No usa dependencias externas: trae su propio lector de PNG, su propio lector de
YAML, su propio ensamblador de Z80 y su propio conversor a ejecutable de
AmigaDOS (si tienes PyYAML instalado, lo aprovecha).

Para **construir el binario final** hace falta un compilador de 68000, y cuál
depende de la máquina:

| Máquina | Qué necesitas |
|---|---|
| Neo Geo | [ngdevkit](https://github.com/dciabrin/ngdevkit) (`m68k-neogeo-elf-gcc`) |
| Mega Drive | `m68k-elf-gcc`, o el paquete `gcc-m68k-linux-gnu` de Debian/Ubuntu |
| Amiga | lo mismo que la Mega Drive (o `m68k-amigaos-gcc` si lo tienes) |
| Jaguar | lo mismo que la Mega Drive; el GPU y el DSP no se usan, así que no hace falta el SDK de Atari |

Para Mega Drive, Amiga y Jaguar no hace falta nada más: el resto (cabecera del
cartucho, suma de control, hunks, relocalización, el disquete de 880 KB con su
bootblock y su sistema de ficheros, y la cabecera del cartucho de Jaguar) lo
hace el propio kit con Python.

## Empezar

```bash
./ngplat nuevo mijuego      # crea un juego completo de ejemplo
cd mijuego
../ngplat probar            # abre el preview jugable en el navegador
../ngplat compilar          # genera build/neogeo/ con el C y las ROMs gráficas
cd build/neogeo && make     # construye la ROM (necesita ngdevkit)
make run                    # la arranca en el emulador
```

Para otra máquina, solo cambia una palabra:

```bash
../ngplat sistemas                       # lista las máquinas y sus límites
../ngplat compilar --sistema megadrive   # -> build/megadrive/rom/juego.bin
../ngplat compilar --sistema amiga       # -> build/amiga/disco/MiJuego.adf
```

O lo dejas escrito en el `game.yaml` y te olvidas:

```yaml
juego:
  titulo: "MI JUEGO"
  sistema: megadrive     # neogeo (por defecto), megadrive o amiga
```

Controles del preview: flechas para moverte, <kbd>Z</kbd> o <kbd>espacio</kbd>
para saltar, <kbd>↓</kbd> para bajar de una plataforma, <kbd>Enter</kbd> para
empezar, <kbd>R</kbd> para reiniciar, <kbd>M</kbd> para silenciar.

## Editor incluido

El preview **es** el editor: pulsa <kbd>E</kbd> y el juego se pausa para que lo
edites; <kbd>Enter</kbd> y lo estás jugando otra vez.

- **Dibujo**: lápiz, rectángulo, relleno, selección con copiar/cortar/pegar y
  cuentagotas. Deshacer y rehacer por trazos, zoom, minimapa y guías que marcan
  cada pantalla de la consola.
- **Todo el juego, no solo el mapa**: propiedades de cada nivel (nombre, fondo,
  música, capas), gestión de niveles (nuevo, duplicar, borrar, reordenar),
  ajustes del juego y **física del jugador con deslizadores**, que se aplican al
  momento.
- **Enemigos y objetos nuevos** sin tocar el archivo: nombre, símbolo,
  comportamiento y caja, reaprovechando un dibujo del proyecto o **dibujándolo
  en el propio editor** (lienzo de 15 colores, varios fotogramas, relleno,
  espejo y deshacer). El PNG se descarga listo para dejarlo en `graficos/`.
- **Revisión en vivo**: te avisa de que falta la salida o la meta, de enemigos
  colgados en el aire o de un hueco más ancho de lo que cruza tu salto. Y un
  botón que **lanza un bot a terminarse el nivel** para comprobar que es posible.
- **Exporta tu `game.yaml` entero**, conservando comentarios y formato: solo
  cambia las líneas que has tocado.
- **Compila desde el propio editor**: eliges máquina y el botón guarda el
  `game.yaml` y construye lo que toque —la ROM, el cartucho o el disquete—, con
  el registro ahí mismo. Lo hace el `ngplat probar` que tienes abierto (una
  página web no compila nada), así que el botón solo está vivo si el preview lo
  está sirviendo él.
- **Guarda solo** en el navegador: si cierras sin exportar, te ofrece recuperar
  lo que estabas haciendo.

Todo en [docs/editor.md](docs/editor.md).

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
| `ngplat probar [proyecto]` | Abre el preview y el editor, y se queda sirviéndolo |
| `ngplat compilar [proyecto]` | Genera `build/<máquina>/` con el C, los gráficos y el Makefile |
| `ngplat compilar --make` | Además construye la ROM o el disquete |
| `ngplat sistemas` | Lista las máquinas de destino y lo que aguanta cada una |

Cualquier orden acepta `--sistema neogeo|megadrive|amiga` para trabajar con una
máquina sin tocar el `game.yaml`. El preview también: dibuja con los colores
que se van a ver de verdad en esa máquina.

`ngplat probar` abre el navegador y **se queda sirviendo** el preview en
localhost hasta que pulses Ctrl+C; eso es lo que hace que el botón «generar ROM»
del editor funcione. Con `--no-servidor` se abre el archivo a pelo, como antes,
y con `--no-abrir` solo se genera el HTML.

Todas las órdenes tienen alias en inglés (`new`, `check`, `preview`, `build`).

## Qué hay dentro

```
neoplat/
├── ngplat                  la orden (Python, sin dependencias)
├── tools/ngplat/           compilador: YAML → C + gráficos + preview
│   ├── project.py          lee y valida game.yaml (mensajes en castellano)
│   ├── build.py            empaqueta gráficos, tiles y niveles (sin hardware)
│   ├── codegen.py          genera gamedata.c/h y arma el proyecto
│   ├── sistemas/           una máquina por archivo
│   │   ├── base.py         qué tiene que saber hacer un sistema
│   │   ├── neogeo.py       ROMs C1/C2/S1/M1 y Makefile de ngdevkit
│   │   ├── megadrive.py    tiles del VDP, 4 paletas, PSG y cabecera del cartucho
│   │   └── amiga.py        bitplanes, máscaras, Paula y ejecutable de AmigaDOS
│   ├── gfx.py              PNG → paletas y tiles de Neo Geo (C ROM / S ROM)
│   ├── gfx_md.py           PNG → tiles de 8x8 del VDP y reparto de paletas
│   ├── gfx_amiga.py        PNG → 5 bitplanes entrelazados y sus máscaras
│   ├── gfx_jaguar.py       PNG → un byte por píxel y tabla de 256 colores
│   ├── hunk.py             ELF → ejecutable de AmigaDOS (hunks + relocalización)
│   ├── adf.py              disquete de 880 KB arrancable (bootblock + OFS)
│   ├── claves.py           nombres que acepta cada opción (los usa el editor)
│   ├── sonido.py           notas -> periodos del SSG, del PSG o de Paula
│   ├── m1.py / z80.py      driver de sonido del Z80 y su ensamblador
│   ├── preview.py          genera el preview jugable
│   ├── servidor.py         localhost: el editor manda el yaml y compila
│   ├── png.py / miniyaml.py  lectores propios (cero dependencias)
│   └── art.py / scaffold.py  el proyecto de ejemplo
├── engine/
│   ├── core/np_world.c     la simulación (física, colisiones, enemigos)
│   ├── core/np_aritmetica.c multiplicar y dividir 32 bits en un 68000
│   ├── neogeo/             vídeo, HUD, sonido y mando de la consola
│   ├── megadrive/          VDP, plano ventana, PSG, arranque y cabecera
│   ├── amiga/              copper, blitter, Paula y arranque
│   └── host/np_trace.c     ejecuta la simulación en el ordenador (pruebas)
├── preview/
│   ├── np_core.js          la misma simulación, en JavaScript
│   ├── np_editor.js        el editor (dibujo, propiedades, validación)
│   ├── np_yaml.js          reescribe el game.yaml sin tocar lo demás
│   ├── np_pixel.js         el lienzo para dibujar enemigos y objetos
│   └── np_bot.js           el bot que comprueba si un nivel se puede terminar
├── examples/bosque-magico/ juego de ejemplo listo para compilar
└── tests/                  159 pruebas + 24 de jugabilidad + 49 del editor +
                            bot que se pasa los niveles + emuladores y navegador
```

**El motor es C, no C++**, a propósito: el compilador de ngdevkit no trae
libstdc++, y en un 68000 a 7 MHz las llamadas virtuales y las plantillas solo
añaden coste. La lógica del juego la genera el compilador, así que no escribes
C de todos modos.

## Añadir otra máquina

Las tres que hay ahora llevan un 68000, así que comparten el motor tal cual;
un sistema nuevo solo tiene que implementar `tools/ngplat/sistemas/base.py`:

- `preparar(build)`: convertir los dibujos y las paletas al formato del chip.
- `comprobar(build)`: avisar de lo que no cabe (mensajes en castellano).
- `generar(build)`: los archivos que faltan (gráficos, sonido, Makefile).
- `archivos_motor`: qué parte del motor se copia (vídeo, HUD, sonido, arranque).

Y en `engine/<máquina>/`, las cuatro piezas de siempre: dibujar un frame, el
marcador, el sonido y leer el mando. Todo lo demás (niveles, física, enemigos,
colisiones, editor, preview, pruebas) ya está hecho y no se toca.

## La misma simulación en los cuatro sitios

`engine/core/np_world.c` (las cuatro máquinas) y `preview/np_core.js` (navegador)
son la misma simulación escrita dos veces: enteros y coma fija 24.8, sin
decimales.
`tests/test_paridad.py` ejecuta las dos con las mismas pulsaciones y compara
frame a frame la posición, la velocidad, la cámara, la puntuación y un hash de
todas las entidades. Si tocas una y te olvidas de la otra, la prueba falla.

Por eso lo que juegas en el navegador es exactamente lo que va a pasar en la
consola, y da igual en cuál.

## Pruebas

```bash
make test           # herramientas, validación, generación de C y paridad C/JS
make test-emulador  # arranca la ROM y el disquete en emuladores de verdad
make test-navegador # abre el preview y el editor en Chromium
node tests/comportamiento.js   # 24 pruebas de jugabilidad
make ejemplo-todos             # compila el ejemplo para las cuatro máquinas
```

Las pruebas con emulador y navegador son opcionales: si no tienes
`libretro-genesisplusgx`, `amitools` o Playwright instalados, se saltan solas.
La Neo Geo no se puede meter en un emulador normal sin la BIOS de SNK, así que
el kit trae su propio banco de pruebas: el 68000 de verdad (Musashi, el núcleo
de MAME) y el chip de vídeo escrito a mano en `tests/maquina_neogeo.py`.

Lo que comprueban: el lector de PNG contra Pillow, el lector de YAML contra
PyYAML, ida y vuelta de los cuatro formatos de gráficos (tiles de Neo Geo, tiles
del VDP, bitplanes y máscaras del Amiga, un byte por píxel de la Jaguar), los mensajes de error del
`game.yaml`, que el C generado compile sin avisos (`-Wall -Wextra -Werror`) y
también con un compilador de 68000 de verdad, que el cartucho de Mega Drive y
el ejecutable de Amiga se construyan y tengan la forma que espera cada máquina,
la paridad C/JavaScript y las mecánicas (salto variable, coyote time, buffer de
salto, plataformas de un sentido, pisar enemigos, daño, muerte, cambio de
nivel, cámara).

## Estado y limitaciones

Verificado aquí:

- El proyecto en C generado compila con `gcc -Wall -Wextra -Werror`, y también
  **de verdad para 68000** con `m68k-linux-gnu-gcc`.
- **La ROM de Mega Drive arranca y se juega en un emulador**: las pruebas la
  ejecutan en Genesis Plus GX sin pantalla, comprueban que dibuja la pantalla de
  título con su marcador, que al pulsar start empieza la partida y que el
  escenario se mueve al correr, y dejan capturas. Es lo único que no se puede
  comprobar compilando, y encontró dos fallos que ninguna otra prueba veía (ver
  [docs/megadrive.md](docs/megadrive.md)).
- **El cartucho de Mega Drive se construye entero**: 128 KB con la cabecera
  `SEGA MEGA DRIVE`, el nombre del juego, el rango de la ROM y la suma de
  control, que las pruebas vuelven a calcular y comparan.
- **La ROM de Neo Geo dibuja el juego**: las pruebas la ejecutan en el banco del
  propio kit —el 68000 de verdad más el chip de vídeo reconstruido en Python—,
  reconstruyen la imagen desde la VRAM, las ROMs de gráficos y las paletas, y
  comprueban que sale el título, que START empieza la partida y que el escenario
  se mueve al correr. Encontró un fallo del marcador que ninguna otra prueba veía
  (el texto del título se quedaba escrito encima del juego).
- **El juego va a 60 de los 60 fps de la Neo Geo** (29 en los frames malos antes
  de optimizar): el banco cuenta los ciclos de 68000 de cada frame y la prueba
  falla si alguno se pasa de los 200.000 que da la consola. Cómo se hizo, en
  [docs/neogeo.md](docs/neogeo.md).
- **El cartucho de Atari Jaguar arranca y se juega en un emulador**: las
  pruebas lo ejecutan en Virtual Jaguar, que no necesita la BIOS de Atari para
  los cartuchos, y comprueban que sale el título con su marcador, que al pulsar
  el botón empieza la partida, que el escenario se mueve al correr y que el
  marcador **no sale duplicado** (el chip de vídeo compone la lista de objetos
  mientras el haz recorre la pantalla, así que reescribirla a destiempo pinta
  las cosas dos veces). Cómo funciona la máquina y las cuatro trampas que
  costaron encontrarla, en [docs/jaguar.md](docs/jaguar.md).
- **El binario no lleva nada que el 68000 no entienda**: las pruebas revisan el
  código máquina de las **cuatro** máquinas (la Neo Geo también, compilando sus
  fuentes sin enlazar) y fallan si aparece una instrucción de 68020 o un acceso
  a una dirección impar. Así se encontró que la ROM de Neo Geo arrastraba el
  mismo fallo que colgaba la de Mega Drive.
- **El ejecutable de Amiga se construye entero**: dos hunks marcados como RAM
  chip, la tabla de relocalización comprobada entrada por entrada (ninguna
  dirección se sale de su hunk) y `_start` en el primer byte, como espera
  AmigaDOS.
- **El juego va a 49 de los 50 fps del Amiga** (25 antes de optimizar): medido
  en líneas de barrido dentro de un A500 emulado, parte por parte. Cómo se hizo,
  en [docs/amiga.md](docs/amiga.md).
- **El disquete de Amiga arranca y se juega en un emulador**: las pruebas lo
  meten en un A500 emulado (PUAE con la ROM libre de AROS), esperan a que
  arranque solo, comprueban que sale el juego con su marcador, pulsan start y
  juegan. Encontró un fallo en el bootblock que ninguna otra prueba veía.
- **Y el disquete también**: un `.adf` de 901120 bytes con bootblock `DOS\0`,
  sistema de ficheros OFS y `s/startup-sequence`. Las pruebas comprueban que
  **todas** las sumas de control cuadran (la del bootblock, con acarreo, y la de
  cada bloque del disco), que el bitmap marca exactamente lo ocupado y que el
  ejecutable sale del disco byte a byte igual que entró.
- Motor en C y preview en JavaScript dan resultados idénticos frame a frame.
- Las mecánicas de plataformas funcionan (24 pruebas de jugabilidad).
- Los niveles de ejemplo se pueden terminar: un bot los juega enteros en cada
  prueba, así que nunca se cuela un nivel imposible.
- El mismo juego compilado para las cuatro máquinas describe exactamente los
  mismos niveles, enemigos y mapas: lo comprueban las pruebas.
- Ida y vuelta de los cuatro formatos de gráficos (tiles de Neo Geo, tiles del
  VDP, bitplanes y máscaras del Amiga, un byte por píxel de la Jaguar): codificar y decodificar devuelve la
  imagen original.
- **Tres de las cuatro máquinas suenan, y suenan lo que pone el `game.yaml`**: las
  pruebas capturan lo que sale del altavoz —del core de libretro en Mega Drive
  y Amiga, y del circuito entero 68000 → Z80 → YM2610 en la Neo Geo— y
  reconocen las notas una a una. En las tres salen **16 de 16** notas de la
  melodía, la pantalla de título está callada y al saltar se oye el efecto por
  encima de la música. Comprobado que la prueba sabe fallar: con una placa muda
  a propósito, fallan las tres comprobaciones. Cómo se hace, en
  [docs/sonido.md](docs/sonido.md).
- Esas tres máquinas tocan la misma nota: 440 Hz salen a 440 Hz en el SSG, en el
  PSG y en Paula (con el redondeo de cada chip).
- El preview se abre en Chromium durante las pruebas y se comprueba que dibuja
  lo que debe (capturas de pantalla revisadas a mano).
- El editor hace el viaje completo en las pruebas: edita mapas, física y
  niveles, exporta el `game.yaml`, se vuelve a compilar y se comprueba que no se
  pierde ni un comentario.
- Los nombres que el editor escribe en el `game.yaml` se comprueban uno a uno
  contra el lector del kit.
- El driver de sonido del Z80 se ejecuta en un emulador incluido en las pruebas:
  se comprueba que recibe las órdenes del 68000 y escribe en el chip los
  periodos y volúmenes de las notas escritas en el `game.yaml`.

**Sin probar en hardware real**: las cuatro se han visto funcionando en
emuladores, pero no en máquinas de verdad. Y en la Neo Geo el emulador es el del
propio kit, que da por buenas dos cosas porque las da por buenas también el
motor: que el sprite 0 va delante de los demás y que la fila 0 del plano fix cae
en la línea 0 de la pantalla. Si al probarla en un MVS ves el fondo tapando al
jugador, se invierte con `NP_SPRITE_FRONT_FIRST` en `np_video.h`; si ves el
marcador desplazado en vertical, es lo segundo. Las muestras digitales siguen
sin usarse en ninguna de las cuatro.

Lo que aún no hace:

- **Sonido en Jaguar**: Jerry tiene dos DAC de 16 bits, pero alimentarlos pide
  un programa para el DSP, que es otro juego de instrucciones y otro
  ensamblador. Por ahora el juego sale mudo en esa máquina y el compilador
  avisa.
- **Parallax en Amiga**: en la Neo Geo van todas las capas y en la Mega Drive
  una; en el Amiga el fondo se ve del color de fondo del nivel. Haría falta
  modo *dual playfield*, que deja el juego en 7 colores por plano en vez de 32.
  Dibujarlas con el blitter y quedarse con los 32 colores está medido y **no
  cabe**: 1.311 líneas de barrido sobre las 313 que da un frame
  ([docs/amiga.md](docs/amiga.md)).
- **Muestras digitales**: la música y los efectos usan ondas cuadradas en las
  tres máquinas que suenan; las voces y percusiones sampleadas aún no (ni la ROM V1 de la
  Neo Geo ni los samples de Paula ni el YM2612).
- **Jefes o eventos guionizados**: hay cinco comportamientos de enemigo fijos.
- **Dos jugadores**.
- **Zoom de sprites** (la Neo Geo lo permite; el motor no lo usa).

## Licencia

Haz lo que quieras con él.
