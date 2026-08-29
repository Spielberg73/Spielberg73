# NeoPlat

Kit para hacer juegos de plataformas 2D **sin programar** y compilarlos para
cinco máquinas de verdad: **Neo Geo** (AES/MVS), **Mega Drive** (Genesis),
**Amiga** (OCS/ECS), **Atari Jaguar** y **Atari ST**.

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
                                ├──►  build/jaguar/         cartucho .j64
                                └──►  build/atarist/        disquete .st
```

El juego lo describes una vez. Lo que cambia de una máquina a otra es cómo se
dibuja y cómo suena, no lo que pasa: la simulación (`engine/core/np_world.c`)
es la misma en las cinco, así que un salto mide exactamente lo mismo en todas.
Y las cinco llevan un **68000**, que es lo que hace que el motor sea uno solo.

| | Neo Geo | Mega Drive | Amiga | Jaguar | Atari ST |
|---|---|---|---|---|---|
| CPU | 68000 a 12 MHz | 68000 a 7,6 MHz | 68000 a 7 MHz | 68000 a 13,3 MHz | 68000 a 8 MHz |
| Escenario | columnas de sprites | plano A del VDP | mapa de bits + blitter | mapa de bits lineal | bitplanes, movidos por la CPU |
| Actores | sprites | sprites del VDP | blitter con máscara | objetos del chip | dibujados a mano, con máscara |
| Colores | 4096 en pantalla | 4 paletas de 16 | una de 32, o dos de 8 | una tabla de 256 | una de 16 |
| Sonido | YM2610 (SSG) por Z80 | PSG SN76489 | Paula (4 canales) | los DAC, por el DSP de Jerry | YM2149 |
| Parallax | sí | una capa | una capa (`amiga: 8colores`) | una capa | una capa (`camara: pantallas`) |
| Sale | ROMs de cartucho | `.bin` con cabecera y suma | disquete `.adf` arrancable | cartucho `.j64` | disquete `.st` arrancable |

El Atari ST es el caso raro y por eso merece la pena: mismo 68000 que los
demás y **nada** que le eche una mano —sin sprites, sin blitter y sin scroll
por hardware—, así que todo lo que se mueve lo mueve la CPU. Enseña 200 líneas
en vez de 224 (una ventana del mismo mundo) y dibuja a 25 frames por segundo
simulando a 50, que es lo que da de sí la máquina;
[docs/atarist.md](docs/atarist.md) cuenta cómo se midió.

## Instalación

Ninguna. Solo necesitas **Python 3.7 o superior**:

```bash
git clone <este repo>
cd neoplat
./ngplat --version
```

En **Windows** hay además un `ngplat.exe` con el kit entero dentro, para no
tener que instalar Python: se descomprime y se usa desde el símbolo del
sistema. Sale de [`empaquetar.py`](empaquetar.py) y lo construye sola la
[acción de GitHub](.github/workflows/paquetes.yml) en un Windows de verdad.

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
| Atari ST | lo mismo que la Mega Drive (o `m68k-atari-mint-gcc` si lo tienes) |

Para Mega Drive, Amiga, Jaguar y Atari ST no hace falta nada más: el resto
(cabecera del cartucho, suma de control, hunks, relocalización, el disquete de
880 KB con su bootblock y su sistema de ficheros, la cabecera del cartucho de
Jaguar y el disquete de 720 KB con su FAT12 y su ejecutable de GEMDOS) lo hace
el propio kit con Python.

## Empezar

```bash
./ngplat nuevo mijuego      # crea un juego completo de ejemplo
cd mijuego
../ngplat probar            # abre el preview jugable en el navegador
../ngplat compilar          # genera build/neogeo/ con el C y las ROMs gráficas
cd build/neogeo && make     # construye la ROM (necesita ngdevkit)
make run                    # la arranca en el emulador
```

`ngplat nuevo` **te pregunta qué tipo de juego quieres hacer**, porque no es lo
mismo un juego de saltar que uno de látigo: cambia la física, el ataque y hasta
el nivel de partida.

| género | cómo se juega |
|---|---|
| `plataformas` | saltas, pisas enemigos y disparas, y el salto se corrige en el aire. Lo de toda la vida |
| `castlevania` | pegas con látigo, subes escaleras, gastas munición y el látigo se mejora. El salto **no** se corrige, un golpe te tira al vacío y hay puntos de control |

Si prefieres decirlo de una:

```bash
./ngplat nuevo micastillo --genero castlevania
```

El **género** decide cómo se juega y el **estilo** cómo se ve: son dos ejes
distintos. Si vas a por el Amiga con parallax, empieza por el otro juego de
dibujos, que ya viene con los seis colores contados que caben en el doble
plano:

```bash
./ngplat nuevo micueva --estilo hierro --genero castlevania
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
- **Cámara a elegir**: `scroll` (el escenario se desliza, como en consola) o
  `pantallas` (la vista salta de una pantalla fija a la siguiente, como en los
  ordenadores de 8 bits). Es la misma opción para las cinco máquinas.
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
- **Guarda en el proyecto** con un botón o <kbd>Ctrl</kbd>+<kbd>S</kbd>, y solo
  cada 20 segundos. Guardar no es compilar: escribe el `game.yaml` y los dibujos
  **aunque el juego esté a medias**, que es justo lo que antes no se podía
  dejar escrito.
- **Historial de copias**: cada guardado deja antes una copia del proyecto
  entero, y se guardan las 40 últimas. Desde la pestaña «copias» o desde la
  terminal (`ngplat historial`, `ngplat recuperar N`). Recuperar también deja
  copia, así que equivocarse de versión tampoco pierde nada.

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

El jugador puede **atacar**, no sólo pisar: con `ataque:` dispara un proyectil
o pega de cerca, y el botón de acción de las cinco máquinas pasa a hacer algo.
`ngplat nuevo` ya te lo deja montado.

La meta se puede **cerrar con llave**: un objeto con `efecto: llave` y un nivel
con `llaves: N` obligan a dar una vuelta antes de salir. El marcador enseña las
que llevas, y si el mapa no tiene llaves suficientes `ngplat` no compila.

Y hay **escaleras**: con `tipo: escalera` en la leyenda y
`velocidad_escalera:` en el jugador, un tile en diagonal se sube con arriba y
se baja con abajo. Es un modo de movimiento aparte —sin gravedad, sin saltos y
sin choques— del que se sale solo por los dos extremos, y del que un golpe te
tira.

Y hay **puntos de control**: con `tipo: control` en la leyenda pones una marca
que no estorba —se pasa por delante— pero que apunta su casilla al tocarla. Si
te matan y te quedan vidas, reapareces ahí de pie en vez de al principio del
nivel, así que un nivel largo deja de ser un castigo. Manda el último por el
que pasas, y cada nivel empieza sin ninguno.

Y el **arma se mejora**: con `mejoras:` y `alcance_mejora:` en el ataque, cada
objeto de `efecto: mejora` alarga el látigo un paso, hasta el tope que pongas.
Se pierden al morir, que es lo que hace que una vida valga algo.

Y hay **candelabros**: con `rompibles:` defines algo que no hace nada hasta que
le pegas y entonces suelta lo que lleve dentro. Con un objeto de
`efecto: municion` y un arma `secundaria:` (arriba + acción) tienes el bucle
entero de los clásicos de látigo: pegarle a todo, recoger corazones y gastarlos
en el cuchillo. El ataque además puede tener `preparacion:` (frames en los que
el brazo todavía sale y no hace daño) y `clavado:` (mientras pegas, no te
mueves), y al recibir daño sales despedido con `retroceso:` y te quedas
`aturdido:` frames sin control: un roce al borde de una plataforma pasa a
tirarte al vacío.

Y hay **plataformas móviles**: con `plataformas:` defines una tabla que va y
viene, y el que se sube encima va con ella. Se apoya como un tile de
`plataforma` (por debajo se pasa a través, pulsando abajo te dejas caer) y no
hace daño: es escenario que se mueve.

Con `jugadores: 2` juegan dos a la vez en la misma pantalla, cada uno con su
mando y con sus vidas: la cámara va al punto medio y el que se queda atrás se
para pegado al borde. En cada máquina el segundo mando está donde toca (en el
Amiga y en el Atari ST, en el puerto del ratón), y las cinco se comprueban en
emulador. Los detalles, en [docs/formato.md](docs/formato.md).

La referencia completa está en [docs/formato.md](docs/formato.md) y hay un
tutorial paso a paso en [docs/tutorial.md](docs/tutorial.md).

## Repartirlo: los ZIP y el .exe

```bash
make paquetes        # los ZIP, en dist/
make paquetes-exe    # además el ngplat.exe (necesita PyInstaller)
```

Salen tres cosas:

| | |
|---|---|
| `neoplat-docs.zip` | sólo la documentación: este README y todo `docs/`. Es lo que te llevas si quieres leerla o pasársela a otro proyecto |
| `neoplat-kit.zip` | el kit entero: motor, herramientas, ejemplo y pruebas, sin lo generado ni el historial |
| `neoplat-windows.zip` | el `ngplat.exe` y su LEEME |

El `.exe` lleva dentro el intérprete, el motor en C, el preview y las
plantillas; no necesita Python ni nada instalado. Construirlo desde Linux es
posible con Wine y un Python de Windows:

```bash
make paquetes-exe PYTHON_WINDOWS="wine /ruta/a/python.exe"
```

pero el que se reparte lo hace la acción de GitHub en un `windows-latest`, que
es lo único que garantiza que el binario es el que va a usar la gente. La
acción, además, lo ejecuta: crea un proyecto y compila para las cinco máquinas.

**Está comprobado que sale lo mismo por los dos caminos**: un proyecto generado
con el `.exe` en Windows es byte a byte idéntico a uno generado con `./ngplat`
en Linux, `preview.html` incluido. Para eso los archivos generados se escriben
siempre con saltos de línea de Unix (`newline="\n"`), que si no Windows metería
`\r\n` y los Makefile saldrían distintos.

Y hay una prueba (`tests/test_empaquetar.py`) que monta el árbol que deja
PyInstaller al arrancar el `.exe` y comprueba que dentro está todo lo que el
kit abre en marcha: el motor de las cinco máquinas, las plantillas, el preview
y los módulos que el proyecto generado se lleva consigo. Es fácil añadir un
archivo nuevo y que el `.exe` se quede sin él; así salta antes de repartirlo.

## Órdenes

| Orden | Qué hace |
|---|---|
| `ngplat nuevo <carpeta>` | Crea un proyecto jugable con gráficos de ejemplo, preguntando el género |
| `ngplat nuevo <carpeta> --genero castlevania` | Lo mismo, con látigo, escaleras, munición y puntos de control en vez de saltar y pisar |
| `ngplat nuevo <carpeta> --estilo hierro` | Lo mismo, pero dibujado con seis colores y listo para el doble plano del Amiga |
| `ngplat comprobar [proyecto]` | Valida el `game.yaml` y dice cuánto ocupa el juego |
| `ngplat probar [proyecto]` | Abre el preview y el editor, y se queda sirviéndolo |
| `ngplat compilar [proyecto]` | Genera `build/<máquina>/` con el C, los gráficos y el Makefile |
| `ngplat compilar --make` | Además construye la ROM o el disquete |
| `ngplat copia [proyecto]` | Guarda una copia del proyecto en su historial |
| `ngplat historial [proyecto]` | Lista las copias guardadas, de la más nueva a la más vieja |
| `ngplat recuperar N [proyecto]` | Devuelve el proyecto a la copia N (guardando antes cómo está) |
| `ngplat sistemas` | Lista las máquinas, lo que aguanta cada una, cómo suena y qué hace con el parallax |

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
│   │   ├── amiga.py        bitplanes, máscaras, Paula y ejecutable de AmigaDOS
│   │   ├── jaguar.py       un byte por píxel, lista de objetos y cartucho .j64
│   │   └── atarist.py      4 bitplanes, YM2149 y disquete con carpeta AUTO
│   ├── gfx.py              PNG → paletas y tiles de Neo Geo (C ROM / S ROM)
│   ├── gfx_md.py           PNG → tiles de 8x8 del VDP y reparto de paletas
│   ├── gfx_amiga.py        PNG → 5 bitplanes entrelazados y sus máscaras
│   ├── gfx_jaguar.py       PNG → un byte por píxel y tabla de 256 colores
│   ├── gfx_st.py           PNG → 4 bitplanes del ST y máscaras de una palabra
│   ├── hunk.py             ELF → ejecutable de AmigaDOS (hunks + relocalización)
│   ├── adf.py              disquete de 880 KB arrancable (bootblock + OFS)
│   ├── prg.py              ELF → ejecutable de GEMDOS (.PRG + relocalización)
│   ├── st_disk.py          disquete de 720 KB con FAT12 y carpeta AUTO
│   ├── claves.py           nombres que acepta cada opción (los usa el editor)
│   ├── sonido.py           notas -> periodos del SSG, del PSG, de Paula o del YM2149
│   ├── m1.py / z80.py      driver de sonido del Z80 y su ensamblador
│   ├── jerry.py / dsp.py   driver de sonido del DSP de la Jaguar, y el suyo
│   ├── preview.py          genera el preview jugable
│   ├── servidor.py         localhost: el editor manda el yaml y compila
│   ├── png.py / miniyaml.py  lectores propios (cero dependencias)
│   ├── art.py / scaffold.py  el proyecto de ejemplo
│   ├── art_sonido.py       los WAV de ejemplo, generados por codigo
│   ├── wav.py / adpcm.py   lector de WAV y el codec del YM2610
│   ├── md_pcm.py           driver de muestras del Z80 de la Mega Drive
│   └── paths.py            donde esta cada cosa, tambien dentro del .exe
├── engine/
│   ├── core/np_world.c     la simulación (física, colisiones, enemigos)
│   ├── core/np_aritmetica.c multiplicar y dividir 32 bits en un 68000
│   ├── neogeo/             vídeo, HUD, sonido y mando de la consola
│   ├── megadrive/          VDP, plano ventana, PSG, arranque y cabecera
│   ├── amiga/              copper, blitter, Paula y arranque
│   ├── jaguar/             el objeto de video, los DAC y el DSP
│   ├── atarist/            Shifter, YM2149 e IKBD, todo con la CPU
│   └── host/np_trace.c     ejecuta la simulación en el ordenador (pruebas)
├── preview/
│   ├── np_core.js          la misma simulación, en JavaScript
│   ├── np_editor.js        el editor (dibujo, propiedades, validación)
│   ├── np_yaml.js          reescribe el game.yaml sin tocar lo demás
│   ├── np_pixel.js         el editor de dibujos (sprites, tiles y fondos)
│   └── np_bot.js           el bot que comprueba si un nivel se puede terminar
├── examples/
│   ├── bosque-magico/      juego de ejemplo listo para compilar
│   └── cueva-de-hierro/    el mismo motor con seis colores y parallax en Amiga
└── tests/                  274 pruebas + 38 de jugabilidad + 66 del editor +
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
marcador, el sonido y leer el mando. El Atari ST es el ejemplo de hasta dónde
llega esa separación: no tiene sprites, ni blitter, ni scroll por hardware, y
aun así el `np_world.c` que corre dentro es exactamente el mismo. Todo lo demás (niveles, física, enemigos,
colisiones, editor, preview, pruebas) ya está hecho y no se toca.

## La misma simulación en los seis sitios

`engine/core/np_world.c` (las cinco máquinas) y `preview/np_core.js` (navegador)
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
node tests/comportamiento.js   # 38 pruebas de jugabilidad
make ejemplo-todos             # compila el ejemplo para las cinco máquinas
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
  código máquina de las **cinco** máquinas (la Neo Geo también, compilando sus
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
- **El Atari ST arranca y se juega en un emulador**: las pruebas meten el
  disquete en un ST emulado (Hatari con EmuTOS), esperan a que TOS ejecute el
  juego de la carpeta `AUTO` y comprueban que sale el título con su marcador,
  que el botón del joystick empieza la partida, que el YM2149 toca las notas
  del `game.yaml` y que el escenario se mueve al correr. Encontró un fallo del
  teclado que fallaba una vez de cada dos: si el ACIA se queda con un byte sin
  leer antes de abrir las interrupciones, el MFP no vuelve a avisar nunca y el
  mando se muere para siempre.
- **El juego va a 25 frames por segundo en el ST** (10 antes de optimizar), y a
  unos 17 en las pantallas que juntan scroll y muchos actores; la simulación va
  a 50 pasos por segundo en las dos, como en las demás máquinas. Medido en
  líneas de barrido dentro de un ST emulado, poniendo el borde de color mientras
  dibuja. Lo que más subió no fue el dibujado sino el orden del bucle, y de paso
  salió un fallo de los feos: con una sola espera al retrazo por vuelta, una
  pantalla con poco que dibujar hacía que el juego corriese **al doble de
  velocidad**. Está contado en [docs/atarist.md](docs/atarist.md).
- **Y su disquete también**: un `.st` de 737280 bytes con FAT12, el juego en la
  carpeta `AUTO` y un `.PRG` de GEMDOS con su tabla de relocalización, que las
  pruebas recorren corrección a corrección. El disquete lo lee además `mtools`
  sin quejarse, que es una implementación de FAT que no es la nuestra.
- Motor en C y preview en JavaScript dan resultados idénticos frame a frame.
- Las mecánicas de plataformas funcionan (24 pruebas de jugabilidad).
- Los niveles de ejemplo se pueden terminar: un bot los juega enteros en cada
  prueba, así que nunca se cuela un nivel imposible.
- El mismo juego compilado para las cinco máquinas describe exactamente los
  mismos niveles, enemigos y mapas: lo comprueban las pruebas.
- Ida y vuelta de los cinco formatos de gráficos (tiles de Neo Geo, tiles del
  VDP, bitplanes y máscaras del Amiga, un byte por píxel de la Jaguar, cuatro
  bitplanes del ST): codificar y decodificar devuelve la imagen original.
- **Las cinco máquinas suenan, y suenan lo que pone el `game.yaml`**: las
  pruebas capturan lo que sale del altavoz —del core de libretro en Mega Drive,
  Amiga, Jaguar y Atari ST, y del circuito entero 68000 → Z80 → YM2610 en la
  Neo Geo— y reconocen las notas una a una. En las cinco salen **16 de 16** de la
  melodía, la pantalla de título está callada y al saltar se oye el efecto por
  encima de la música. Comprobado que la prueba sabe fallar: con una placa muda
  a propósito, fallan las tres comprobaciones. Cómo se hace, en
  [docs/sonido.md](docs/sonido.md).
- Las cinco tocan la misma nota: 440 Hz salen a 440 Hz en el SSG, en el PSG, en
  Paula, en los DAC de la Jaguar y en el YM2149 (con el redondeo de cada uno).
- El preview se abre en Chromium durante las pruebas y se comprueba que dibuja
  lo que debe (capturas de pantalla revisadas a mano).
- El editor hace el viaje completo en las pruebas: edita mapas, física y
  niveles, exporta el `game.yaml`, se vuelve a compilar y se comprueba que no se
  pierde ni un comentario.
- El editor de dibujos también: en Chromium se abre el PNG del jugador, se le
  pinta una línea con el ratón, se deshace y se comprueba que el PNG que sale
  mide exactamente lo que la hoja.
- Los nombres que el editor escribe en el `game.yaml` se comprueban uno a uno
  contra el lector del kit.
- **Los dos mandos llegan a los dos jugadores en las cinco máquinas**: con
  `jugadores: 2`, las pruebas juegan la misma partida tres veces en cada
  emulador —con un mando, con el otro y con los dos— y exigen que las tres
  acaben distintas. Ahí se vio que en la Jaguar las filas de la matriz **no se
  piden con el mismo número** en un puerto que en el otro, que es lo que hacía
  que el segundo mando no llegase.
- **Las muestras digitales se oyen**: el proyecto de prueba pone como efecto de
  salto un tono puro a 3.000 Hz sin notas de recambio, y la prueba mide esa
  frecuencia en lo que sale del emulador antes y después de saltar. Suena 20
  veces más en el Amiga, 19 en la Mega Drive, 13 en la Neo Geo y 8 en la
  Jaguar; desactivando el camino de las muestras en el driver del Amiga, 0,4.
  El driver de Z80 de la Mega Drive se ejecuta byte a byte en el emulador del
  kit, cruce de banco incluido, y en la Neo Geo el banco descifra el ADPCM-A
  para poder oírlo.
- **El ataque hace lo que dice**: nueve pruebas de jugabilidad en JavaScript
  (que el proyectil vuela hacia donde miras, mata y da puntos, se apaga contra
  una pared y al agotar el alcance, que la cadencia se respeta, que mantener el
  botón no dispara sin parar, y que el golpe llega a lo de al lado y no más
  allá), más la paridad C/JS con los dos tipos de ataque: los proyectiles van
  en la misma lista de entidades, así que entran en el hash de la traza.
- **Las llaves cierran la meta de verdad**: cinco pruebas de jugabilidad en
  JavaScript (que sin llave la meta no se abre, que con ella sí, que una llave
  que vale por varias abre sola, que la que coge un jugador le sirve al otro y
  que no se guardan de un nivel para otro), más una variante de la paridad C/JS
  que comprueba en toda la traza que el nivel no se acaba nunca con el contador
  a cero.
- **El bucle de los candelabros**: catorce pruebas de jugabilidad en JavaScript
  (que el candelabro no hace daño ni se recoge, que el golpe y el disparo lo
  rompen y sale lo que lleva dentro apoyado donde estaba, que uno vacío no
  suelta nada, que con `vida:` hacen falta varios ataques, que arriba + acción
  gasta munición y sin munición pega en vez de tirar, que el botón a secas no
  gasta, y que el arma en arco cae y la recta no), más una variante de paridad
  C/JS: el andamiaje trae candelabros y cuchillo, así que las trazas comparan
  también la munición, y una prueba comprueba que en esa traza se rompe algún
  candelabro y que la munición se gasta —si no, la paridad estaría comparando
  dos motores que no hacen nada.
- **Las escaleras, los puntos de control y las mejoras del arma**: veinticuatro
  pruebas de jugabilidad en JavaScript (que te subes con arriba y con abajo,
  que dentro no hay gravedad ni salto, que se sale de pie por los dos extremos,
  que un golpe te tira; que la antorcha no estorba ni hace daño pero apunta su
  casilla, que al morir se reaparece en ella y no en la salida, que sin tocarla
  se reaparece en la salida, que manda la última por la que pasas y que
  repasarla no vuelve a sonar; que el látigo de serie se queda corto y con una
  mejora llega, que las mejoras se paran en el tope y se pierden al morir), más
  las variantes de paridad C/JS. En la traza del castillo se comprueba que el
  punto de control se enciende **y** cambia dónde reapareces, y que la mejora
  se coge y se pierde: sin eso, la paridad estaría comparando dos motores que
  apuntan la casilla y luego la ignoran.
- **Las plataformas móviles llevan al jugador**: ocho pruebas de jugabilidad en
  JavaScript (que va y viene entre sus dos extremos y no se pasa, que el
  jugador se planta encima y se mueve exactamente lo mismo que ella, que una
  vertical le sube y le baja sin despegarle en ningún frame, que se puede
  saltar desde encima, que por debajo se pasa a través, que pulsando abajo te
  dejas caer y que no hace daño), más una variante de la paridad C/JS: la
  plataforma se mueve antes que los jugadores, y si las dos implementaciones no
  lo hicieran en el mismo orden las posiciones se irían a la primera vuelta.
- **Los dibujos caen en dirección par**: el Atari ST y el Amiga leen los tiles
  de palabra larga en palabra larga aunque el array sea de bytes, y en el 68000
  hacer eso en una dirección impar para la máquina en seco. Una prueba mira los
  símbolos del ELF y otra la declaración generada.
- El driver de sonido del Z80 se ejecuta en un emulador incluido en las pruebas:
  se comprueba que recibe las órdenes del 68000 y escribe en el chip los
  periodos y volúmenes de las notas escritas en el `game.yaml`.

**Sin probar en hardware real**: las cinco se han visto funcionando en
emuladores, pero no en máquinas de verdad. Y en la Neo Geo el emulador es el del
propio kit, que da por buenas dos cosas porque las da por buenas también el
motor: que el sprite 0 va delante de los demás y que la fila 0 del plano fix cae
en la línea 0 de la pantalla. Si al probarla en un MVS ves el fondo tapando al
jugador, se invierte con `NP_SPRITE_FRONT_FIRST` en `np_video.h`; si ves el
marcador desplazado en vertical, es lo segundo.

Lo que aún no hace:

- **Varias capas de parallax en Amiga**: con `amiga: 8colores` el juego usa el
  modo *dual playfield* del OCS y se dibuja **una** capa, movida por hardware;
  las demás se ignoran. Dibujarlas con el blitter y quedarse con los 32 colores
  está medido y **no cabe**: 1.311 líneas de barrido sobre las 313 que da un
  frame ([docs/amiga.md](docs/amiga.md)).
- **Muestras digitales en cuatro de las cinco máquinas**: un efecto ya puede ser
  un WAV tuyo (`muestra: sonidos/x.wav`). Lo toca Paula desde la RAM chip en el
  Amiga; en la Mega Drive se lo da al DAC del YM2612 un driver de Z80 que genera
  el propio compilador; en la Jaguar lo lee el DSP del cartucho; y en la Neo Geo
  van por los canales ADPCM-A del YM2610, con la ROM V1 que también monta el
  compilador (con su códec, en Python puro). El Atari ST no puede: su YM2149
  sólo hace ondas cuadradas, y ahí suenan las notas que le pongas al lado.
- **Parallax en el Atari ST con `camara: scroll`**: con `pantallas` sí se
  dibuja, y sale gratis porque la vista está quieta; deslizándose habría que
  repintar la pantalla entera cada pocos píxeles y no cabe
  ([docs/atarist.md](docs/atarist.md)).
- **Eventos guionizados**: hay cinco comportamientos de enemigo fijos y un jefe
  por nivel (`jefe: si`); no hay forma de guionizar una secuencia.
- **La vida no se ve**: el marcador enseña puntos, vidas, tiempo, llaves,
  munición y la barra del jefe, pero no los golpes que te quedan. Con `vida: 1`
  daba igual; con `vida: 4` (el género de látigo) se juega a ciegas.
- **Aviso de sprites en Neo Geo**: la Mega Drive avisa al pasar de 40 spawns
  por nivel; la Neo Geo no mira nada, y si un nivel se pasa de las 96 columnas
  de sprite el motor deja de dibujar sin decirlo.
- **Zoom de sprites** (la Neo Geo lo permite; el motor no lo usa).

## Licencia

Haz lo que quieras con él.
