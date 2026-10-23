# NeoPlat

A kit for making 2D platform games **without programming** and compiling them
for seven real machines: **Neo Geo** (AES/MVS), **Mega Drive** (Genesis),
**Amiga** (OCS/ECS), **Amiga 1200** (AGA), **Atari Jaguar**, **Atari ST** and
**Sharp X68000**.

You describe the game in a `game.yaml` file, you draw the graphics in PNG and
the compiler generates the project in C, the graphics already converted to each
chip's format and a **playable preview in the browser** for trying changes in
seconds.

```
                                ┌──►  preview.html          (playable + editor)
                                │
game.yaml + PNG  ──►  ngplat  ──┼──►  build/neogeo/         C1/C2/S1/M1 ROMs
                                ├──►  build/megadrive/      .bin cartridge
                                ├──►  build/amiga/          .adf floppy
                                ├──►  build/amiga1200/      .adf floppy (AGA)
                                ├──►  build/cd32/           bootable .iso CD
                                ├──►  build/jaguar/         .j64 cartridge
                                ├──►  build/atarist/        .st floppy
                                └──►  build/x68000/         .X executable and .xdf floppy
```

You describe the game once. What changes from one machine to another is how it
is drawn and how it sounds, not what happens: the simulation
(`engine/core/np_world.c`) is the same on all of them, so a jump measures
exactly the same on each. And all of them carry a **68000** (the A1200 and the
CD32 their 68EC020), which is what makes the engine a single one. They are
**eight targets on seven machines**: the CD32 is the same A1200 put inside a
console, so it shares even the binary with it —the only difference is that it
goes on a CD and not on a floppy—.

| | Neo Geo | Mega Drive | Amiga | Amiga 1200 | Jaguar | Atari ST | X68000 |
|---|---|---|---|---|---|---|---|
| CPU | 68000 at 12 MHz | 68000 at 7.6 MHz | 68000 at 7 MHz | 68EC020 at 14 MHz | 68000 at 13.3 MHz | 68000 at 8 MHz | 68000 at 10 MHz |
| Stage | columns of sprites | the VDP's plane A | bitmap + blitter | the same, with 8 bitplanes | linear bitmap | bitplanes, moved by the CPU | the chip's background layer |
| Actors | sprites | the VDP's sprites | blitter with mask | blitter with mask | the chip's objects | drawn by hand, with mask | 16×16 sprites |
| Colours | 4096 on screen | 4 palettes of 16 | one of 32, or two of 8 | one of **256**, or two of 16, **24-bit** | a table of 256 | one of 16 | 16 blocks of 16 |
| Sound | YM2610 (FM) via Z80 | YM2612 (FM) | Paula (4 channels, with the voice as a wavetable) | the same as the Amiga | the DACs, via Jerry's DSP | YM2149 | YM2151 (FM) and ADPCM |
| Parallax | yes | one layer | one layer (`amiga: 8colores`) | one layer, with 16 colours per plane | one layer | one layer (`camara: pantallas`) | one layer (the graphics screen) |
| Output | cartridge ROMs | `.bin` with header and checksum | bootable `.adf` floppy | bootable `.adf` floppy | `.j64` cartridge | bootable `.st` floppy | Human68k `.X` and `.xdf` floppy |

And the Neo Geo has the opposite: it **shrinks sprites in hardware**, which is
what most sets it apart and which none of the other six has. Driving, the
roadway's traffic is drawn with the scaler, so the cars grow smoothly instead
of jumping between the five sizes the others carry; the road, which here cannot
be slid line by line because there is nothing but sprites, goes in bands.
[neogeo.md](neogeo.md) covers it.

The Atari ST is the odd case and that is what makes it worthwhile: the same
68000 as the rest and **nothing** to lend it a hand —no sprites, no blitter and
no hardware scroll— so everything that moves is moved by the CPU. It shows 200
lines instead of 224 (a window onto the same world) and draws at 25 frames per
second while simulating at 50, which is what the machine gives;
[atarist.md](atarist.md) covers how it was measured.

The **Amiga 1200** is the same Amiga with the AGA chipset flexing, and that is
why it is a separate target and not an option on the other one: its floppy
demands an AGA machine and on an A500 nothing would be seen. It shares the
whole engine with OCS —bitplanes, blitter, copper and Paula— and what changes
are numbers: **eight bitplanes** instead of five (256 colours at once),
**eight bits per channel** instead of four (that is, the colours come out
exact, with no rounding), dual playfield at **16+16** colours instead of 7+7,
and the 68EC020 at 14 MHz. Eight bitplanes in low resolution do not fit in the
usual DMA: AGA's 32-bit reads are needed, and with them the screen pointer
jumps 32 pixels at a time and the rest is supplied by the extended fine scroll.
It is measured on an emulated A1200 and it moves pixel by pixel just like OCS;
[amiga.md](amiga.md) covers it.

The **CD32** is that same machine in a console: same 68EC020, same AGA, same
2 MB of chip RAM. That is why `--sistema cd32` produces **the same executable
byte for byte** as the A1200 and the only thing that changes is the wrapper:
instead of a floppy, an **ISO 9660** that the Kickstart mounts as `CD0:` and
boots by running `S/Startup-Sequence`. The controller asks for nothing new
either: a CD32 pad reads as a two-button joystick —red to jump and start, blue
to attack— which is exactly what the Amiga was already reading. For the CD to
**boot by itself** on a real console you have to add `CD32.TM`, 2048 bytes of
Commodore's that cannot be distributed with the kit:
`make MARCA=/path/CD32.TM`. Without it the ISO is valid and readable, but it
does not boot, and the compiler says so.

The X68000 is the other odd case, for the opposite reason: it is the one that
helps most (its patterns are 16×16, exactly the kit's tile) and at the same
time the one with the least reliable documentation. It was ported **by
measuring the hardware in the emulator** with a probe that turns bits on and
watches what comes out on screen; [x68000.md](x68000.md) covers what each test
said: why its sprite chip only shows one layer (and the parallax ended up on
the graphics screen, which is another chip), why 192 patterns are left instead
of 256, and how the YM2151's note table was measured, which is not the one the
documentation gives.

## Installation

None. All you need is **Python 3.7 or later**:

```bash
git clone <this repo>
cd neoplat
./ngplat --version
```

On **Windows** there is also an `ngplat.exe` with the whole kit inside, so that
you do not have to install Python: you unzip it and use it from the command
prompt. It comes out of [`empaquetar.py`](../../empaquetar.py) and it is built
by the [GitHub action](../../.github/workflows/paquetes.yml) on a real Windows.

It uses no external dependencies: it brings its own PNG reader, its own YAML
reader, its own Z80 assembler and its own AmigaDOS executable writer (if you
have PyYAML installed, it makes use of it).

To **build the final binary** you need a 68000 compiler, and which one depends
on the machine:

| Machine | What you need |
|---|---|
| Neo Geo | [ngdevkit](https://github.com/dciabrin/ngdevkit) (`m68k-neogeo-elf-gcc`) |
| Mega Drive | `m68k-elf-gcc`, or Debian/Ubuntu's `gcc-m68k-linux-gnu` package |
| Amiga | the same as the Mega Drive (or `m68k-amigaos-gcc` if you have it) |
| Jaguar | the same as the Mega Drive; the GPU and the DSP are not used, so Atari's SDK is not needed |
| Atari ST | the same as the Mega Drive (or `m68k-atari-mint-gcc` if you have it) |
| Sharp X68000 | the same as the Mega Drive |

For Mega Drive, Amiga, Jaguar, Atari ST and X68000 nothing else is needed: the
rest (cartridge header, checksum, hunks, relocation, the 880 KB floppy with its
bootblock and its file system, the Jaguar cartridge's header and the 720 KB
floppy with its FAT12 and its GEMDOS executable) is done by the kit itself in
Python.

## Getting started

```bash
./ngplat nuevo mijuego      # creates a complete example game
cd mijuego
../ngplat probar            # opens the playable preview in the browser
../ngplat compilar          # generates build/neogeo/ with the C and the graphics ROMs
cd build/neogeo && make     # builds the ROM (needs ngdevkit)
make run                    # boots it in the emulator
```

`ngplat nuevo` **asks you what kind of game you want to make**, because a
jumping game is not the same as a whip game: it changes the physics, the attack
and even the starter level.

| genre | how it plays |
|---|---|
| `plataformas` | you jump, you stomp enemies and you shoot, and the jump can be steered in mid-air. The classic. It also brings a **pond** in the first level: you swim, you dive and your air is counted |
| `castlevania` | you hit with a **whip** (which is visible, and gets longer with each upgrade), you crouch, you climb stairs and you throw knives or the axe, spending ammo. The jump **cannot** be steered, one hit throws you into the void and there are checkpoints. It brings its own creatures: a skeleton, a bat and a hooded boss |
| `comando` | **seen from above**: you walk in eight directions, you shoot where you are looking, you throw grenades with the jump button and you climb the screen rescuing prisoners. The soldiers and the turrets **shoot back**; the tied-up prisoners do not: if you hit them, you lose them |
| `mazmorra` | a **maze** seen from above, Gauntlet style. Health **drains by itself**, so the game is a countdown and you have to keep looking for food; the **spawners** pour out creatures endlessly until you smash them, and the potion on the jump button takes out everything on screen. The goal asks for a key that is on the far side of the maze |
| `barrio` | **me against the neighbourhood**, Double Dragon style: you walk down a street **with depth** and you fight for real. The enemies **do not come and rub against you**: they place themselves at arm's length, they wait their turn (only two hit at a time), they **telegraph** before throwing a punch and are left wide open afterwards —that is your window— and they **surround** you on both sides. You chain (punch, punch and finisher), you **elbow** whoever is behind, you come in with a **jump kick**, you **run** with a double tap and you **grab** whoever is reeling. Each hit **stops the world** for a few frames and each knockdown **shakes the screen** |
| `aventura` | a **screen-by-screen adventure**, Dizzy style. Here you **do not hit**: the button drops what you are carrying, and three things fit in the bag. What stops you is not a creature but a **lock** —a door, a bonfire, a wall— which only opens if you turn up with the right thing; on opening it the object is spent and the way stays open. And the jump **cannot be steered in mid-air**: on take-off you decide where you are going and until you land it cannot be changed |
| `filmation` | a **room seen from a corner**, Knight Lore style. The map is no longer what you see: it is the room's **floor plan**, and each cell carries a **height** —0 is floor, 16 a cube you hop onto, 32 two heights and 48 a wall—. With that number the whole stage is written. The controller goes along the map's axes (on screen they come out diagonal), the jump **cannot be steered in mid-air** and the camera shows the room you are in and **jumps** to the next one as you cross. Jumping is the way to dodge: over a spike or a creature nothing happens |
| `kungfu` | a **temple of fixed screens**, Bruce Lee style. You go around putting out **lanterns** —the door does not open until they are all out— with **two guys after you** who do not belong to the screen but to you: on changing screen they come back in through whichever edge you come in by, so running does not shake them off. And **they hit each other**, so crossing them is a move. You **climb vines** —you grab a vine in mid-air, you climb it straight and from it you jump wherever you like— and the button in mid-air brings out the **flying kick**, which reaches twice as far and hurts twice as much |
| `grafica` | a **graphic adventure**, the point-and-click kind: here you do not walk, you **point**. The player is a **cursor** that has no weight, does not collide, does not collect and cannot die; the jump button cycles through **four verbs** —look, take, use and talk— and the action button applies it to the cell you are pointing at. Each thing in the room answers **something different to each verb**, and what stops you is not a creature: it is what you do not know yet. The example is two rooms —a study and a cellar—, a portrait you can talk to, a lantern, a key, a trapdoor that asks for both and a chest that will not give with bare hands |
| `carretera` | a **driving game**, Out Run style: the road runs off towards the horizon and the only thing to do is go fast without going off. Inside it **is not a new view**: the map is the road's course seen from above and the car climbs it, so the corner is not programmed —the car goes **straight**, and if the road bends and you do not turn, off you go—. How tight a corner can be comes out of one division —`volante / punta`, how much the car moves sideways per row of road— and with the stock values it is **one cell every three rows**: tighter than that cannot be taken, and braking does not help, because that line is the same at any speed. There are two gears (low pushes, high runs), traffic to overtake, and crashing does not cost you health: it puts you into a **spin-out**, and that costs time. The **checkpoints** hand out seconds, which is the only currency there is |
| `vacio` | **none of the ten**: a hero, a flat floor and a goal. There are no enemies, no objects, no music and no parallax, and only the two PNGs the `game.yaml` names land in the folder. It compiles and plays as it is —you walk, you jump and you reach the end— and the file itself has a note at the bottom of which sections are missing, what they are called and where they are documented. The other ten show how a game is written; this one is for when you already know and what you want is your own, because you start from a finished game by **deleting**, and deleting in a three-hundred-line yaml breaks something |

If you would rather say it in one go:

```bash
./ngplat nuevo micastillo --genero castlevania
```

The **genre** decides how it plays and the **style** how it looks: they are two
different axes. If you are going for the Amiga with parallax, start from the
other set of graphics, which already comes with the six counted colours that
fit in dual playfield:

```bash
./ngplat nuevo micueva --estilo hierro --genero castlevania
```

For another machine, just change a word:

```bash
../ngplat sistemas                       # lists the machines and their limits
../ngplat compilar --sistema megadrive   # -> build/megadrive/rom/juego.bin
../ngplat compilar --sistema amiga       # -> build/amiga/disco/MiJuego.adf
```

Or you write it down in the `game.yaml` and forget about it:

```yaml
juego:
  titulo: "MI JUEGO"
  sistema: megadrive     # neogeo (the default), megadrive or amiga
```

Preview controls: arrows to move, <kbd>Z</kbd> or <kbd>space</kbd> to jump,
<kbd>↓</kbd> to drop off a platform, <kbd>Enter</kbd> to start, <kbd>R</kbd> to
restart, <kbd>M</kbd> to mute.

## Editor included

The preview **is** the editor: press <kbd>E</kbd> and the game pauses so that
you can edit it; <kbd>Enter</kbd> and you are playing it again.

- **Drawing**: pencil, rectangle, fill, selection with copy/cut/paste and
  eyedropper. Undo and redo per stroke, zoom, minimap and guides marking each
  of the console's screens.
- **The whole game, not just the map**: each level's properties (name,
  background, music, layers), level management (new, duplicate, delete,
  reorder), the game's settings and the **player's physics with sliders**,
  which apply immediately.
- **New enemies and objects** without touching the file: name, symbol,
  behaviour and box, reusing one of the project's graphics or **drawing it in
  the editor itself** (a 15-colour canvas, several frames, fill, mirror and
  undo). The PNG downloads ready to drop into `graficos/`.
- **A camera to choose from**: `scroll` (the stage slides, as on a console) or
  `pantallas` (the view jumps from one fixed screen to the next, as on the
  8-bit computers). It is the same option for all seven machines.
- **The sound, with a listen button**: the twelve moments the game produces
  (jumping, picking up a coin, taking a hit…) with their type —notes, sweep or
  noise— and their numbers, and the songs with their two note tracks. You hear
  it right there, and **exactly** what will sound on the machine sounds: the
  browser compiles the notes with the same procedure as the kit.
- **Live checking**: it warns you that the start or the goal is missing, about
  enemies hanging in mid-air or about a gap wider than your jump crosses. And a
  button that **sends a bot in to finish the level** to check that it can be
  done.
- **Exports your whole `game.yaml`**, keeping comments and formatting: it only
  changes the lines you have touched.
- **Compiles from the editor itself**: you choose a machine and the button
  saves the `game.yaml` and builds whatever is due —the ROM, the cartridge or
  the floppy— with the log right there. It is done by the `ngplat probar` you
  have open (a web page compiles nothing), so the button is only alive if the
  preview is being served by it.
- **Saves into the project** with a button or <kbd>Ctrl</kbd>+<kbd>S</kbd>, and
  by itself every 20 seconds. Saving is not compiling: it writes the
  `game.yaml` and the graphics **even if the game is half-finished**, which is
  exactly what could not be left written down before.
- **Backup history**: each save leaves a copy of the whole project first, and
  the last 40 are kept. From the "copias" tab or from the terminal
  (`ngplat historial`, `ngplat recuperar N`). Restoring also leaves a copy, so
  picking the wrong version does not lose anything either.

All of it in [editor.md](editor.md).

## What a game looks like

The whole game fits in one file. The maps are drawn with characters:

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
    comportamiento: patrulla      # patrulla, volador, perseguidor, saltarin,
                                  # fijo, cocodrilo, balanceo
    velocidad: 0.4

objetos:
  moneda: {sprite: graficos/moneda.png, puntos: 10}

fondos:                          # parallax layers, far to near
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
  titulo: presentacion           # the title screen's
  jefe: acoso                    # takes over while the boss is alive

variables:                       # the game's memory: it survives levels
  avisos: 0

guiones:                         # and what moves it
  cartel:
    - sumar: {avisos: 1}
    - si: {avisos: 1}
      pasos:
        - decir: "CUIDADO CON EL FOSO."
      si_no:
        - decir: "TE LO DIJE."

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

`P` is the player's start, `G` the goal, `#` a solid block, `=` a platform you
pass through from below, `^` spikes. The other symbols you define yourself.

The player can **attack**, not just stomp: with `ataque:` it fires a projectile
or hits at close range, and the action button on all seven machines starts
doing something. `ngplat nuevo` sets it up for you already.

The goal can be **locked**: an object with `efecto: llave` and a level with
`llaves: N` force a detour before leaving. The scoreboard shows how many you
are carrying, and if the map does not have enough keys `ngplat` does not
compile.

And there are **stairs**: with `tipo: escalera` in the legend and
`velocidad_escalera:` on the player, a diagonal tile is climbed with up and
descended with down. It is a separate movement mode —no gravity, no jumps and
no collisions— which you only leave by either end, and which a hit throws you
out of.

And there is **water**: with `tipo: agua` in the legend and `brazada:` on the
player, some cells stop being air and become a pond. Inside it you fall slowly,
you move less, **up rises** for as long as you hold it and the jump button is
**a stroke** that repeats as often as you like —and which, with your head out,
lifts you onto the bank—. There are two postures and **the head** decides: with
your head out you swim —you breathe, you float, and the next stroke takes you
out of the water—, with your whole body under you dive and the air starts going
down. When it runs out, health goes point by point, and getting your head out
fills it right back up. The game `ngplat nuevo` gives you **already brings a
pond** in the first level, just past the spikes: you fall in without meaning
to, which is the best way of finding out. If you do not want it, deleting
`brazada:` takes the water out of the executable entirely.

The scoreboard shows **health**: `LIFE ###.` with the hits you have left and
the ones you have lost, and in two-player games one bar each. It appears by
itself as soon as the game has `vida:` greater than 1 —with one hit there is
nothing to look at— and switches off outside the game, which is when that row
is used by the title and the *game over*.

And there are **checkpoints**: with `tipo: control` in the legend you place a
marker that does not get in the way —you walk straight through it— but which
notes its cell when you touch it. If you are killed and you have lives left,
you reappear there on your feet instead of at the start of the level, so a long
level stops being a punishment. The last one you pass counts, and each level
starts with none.

And the **weapon upgrades**: with `mejoras:` and `alcance_mejora:` on the
attack, each object with `efecto: mejora` lengthens the whip one step, up to
the limit you set. They are lost on death, which is what makes a life worth
something.

And **the weapon is visible**: with `tipo: golpe`, the attack's `sprite:` is
the whip, and it is drawn in front of the player **only while the hit does
damage**, so what you see on screen is exactly what hits. Each frame is one
upgrade level, drawn to its reach (24, 36 and 48 px), so the upgrade both shows
and is felt.

And you can **crouch**: with `agachado: si`, down on the ground lowers your
box's ceiling —your feet stay where they are— so whatever flies at head height
passes over you, and the whip comes out at knee height. You neither walk nor
jump while crouched.

And there are **candelabra**: with `rompibles:` you define something that does
nothing until you hit it and then drops whatever it carries. With an object
with `efecto: municion` and the weapons in `secundarias:` (up + action) you
have the whole loop of the whip classics: hit everything, collect hearts and
spend them on the knife or the axe. You can carry **more than one**: you start
with the first and you swap by picking up an object with `efecto: subarma`, and
with `a_la_vez:` you decide how many fit in the air at once (one is the
classic, three is the usual triple). With two or more, the scoreboard stops
saying `AMMO 05` and says the name of the one you are carrying (`HACHA 05`),
which is the only thing that tells you what is in your hand. The attack can
also have `preparacion:` (frames in which the arm is already out and does no
damage) and `clavado:` (while hitting, you do not move), and on taking damage
you are thrown back with `retroceso:` and left `aturdido:` for some frames with
no control: a graze at the edge of a platform becomes a fall into the void.

And there are **moving platforms**: with `plataformas:` you define a board that
goes back and forth, and whoever stands on it goes with it. It supports you
like a `plataforma` tile (you pass through from below, pressing down drops you
off) and it does no damage: it is scenery that moves.

With `jugadores: 2` two people play at once on the same screen, each with their
own controller and their own lives: the camera goes to the midpoint and
whoever falls behind stops against the edge. On each machine the second
controller is where it should be (on the Amiga and the Atari ST, in the mouse
port), and all seven are checked in an emulator. The details, in
[formato.md](formato.md).

The complete reference is in [formato.md](formato.md) and there is a
step-by-step tutorial in [tutorial.md](tutorial.md).

## The manual

It is twelve documents, and the index —with the order to read them in and what
each one answers— is in **[docs/en/README.md](README.md)**:

| | |
|---|---|
| [tutorial.md](tutorial.md) | your first game in 10 minutes, and a chapter per genre |
| [formato.md](formato.md) | the `game.yaml` reference: every key |
| [editor.md](editor.md) | the editor, which is the preview itself |
| [sonido.md](sonido.md) | the notes, the voices and how it is checked that it sounds |
| [neogeo.md](neogeo.md) · [megadrive](megadrive.md) · [amiga](amiga.md) · [atarist](atarist.md) · [jaguar](jaguar.md) · [x68000](x68000.md) | one machine per document: the hardware, what the kit does with it and what it cost to find out |

The Spanish original is in [docs/](../README.md), and `make manual` leaves both
**PDFs** in `dist/` (`neoplat-manual-es.pdf` and `neoplat-manual-en.pdf`).

## Distributing it: the ZIPs and the .exe

```bash
make paquetes        # the ZIPs, in dist/
make paquetes-exe    # plus the ngplat.exe (needs PyInstaller)
```

Three things come out, **with the version in the name** (the same one
`ngplat --version` says, which goes up with every change: see
[CAMBIOS.md](../../CAMBIOS.md)):

| | |
|---|---|
| `neoplat-docs-1.56.zip` | the documentation only: this front page and all of `docs/`. It is what you take if you want to read it or pass it on to another project |
| `neoplat-kit-1.56.zip` | the whole kit: engine, tools, example and tests, without the generated files or the history |
| `neoplat-windows-1.56.zip` | the `NeoPlat.exe` (the editor, in its window), the command-line `ngplat.exe` and its README |

The Windows ZIP brings **two programs**, and what changes is the way in.
**`NeoPlat.exe`** is the editor: double click and up it comes, in its own
window, with no console behind it —if there is a game beside it, it opens it;
if there are several, it asks which; and if there are none, it lets you create
one—. **`ngplat.exe`** is the same kit from the command line, for compiling and
the rest; with a double click it asks what you want to do and waits for you to
press Enter before closing the window.

Both carry the interpreter, the engine in C, the preview and the templates
inside: they need neither Python nor anything installed. The editor's window
needs Edge or Chrome, which on Windows 10 and 11 is already there. Building
them from Linux is possible with Wine and a Windows Python:

```bash
make paquetes-exe PYTHON_WINDOWS="wine /path/to/python.exe"
```

but the one that gets distributed is built by the GitHub action on a
`windows-latest`, which is the only thing that guarantees the binary is the one
people will use. The action also runs it: it creates a project and compiles for
all seven machines.

**It is checked that both routes give the same thing**: a project generated
with the `.exe` on Windows is byte for byte identical to one generated with
`./ngplat` on Linux, `preview.html` included. For that, the generated files are
always written with Unix line endings (`newline="\n"`), since otherwise Windows
would put in `\r\n` and the Makefiles would come out different.

And there is a test (`tests/test_empaquetar.py`) that assembles the tree
PyInstaller leaves when the `.exe` starts and checks that everything the kit
opens while running is inside: the engine for all seven machines, the
templates, the preview and the modules the generated project takes with it. It
is easy to add a new file and have the `.exe` end up without it; this way it
comes up before distribution.

## Commands

| Command | What it does |
|---|---|
| `ngplat nuevo <folder>` | Creates a playable project with example graphics, asking the genre |
| `ngplat nuevo <folder> --genero castlevania` | The same, with whip, stairs, ammo and checkpoints instead of jumping and stomping |
| `ngplat nuevo <folder> --genero comando` | The same, but seen from above: eight directions, grenades, enemies that shoot and prisoners to rescue |
| `ngplat nuevo <folder> --genero mazmorra` | A Gauntlet-style maze: health drains by itself, there are creature spawners and a potion that clears the screen |
| `ngplat nuevo <folder> --genero barrio` | A Double Dragon-style brawler: enemies that place themselves, telegraph and wait their turn; elbow, jump kick, running and grabs |
| `ngplat nuevo <folder> --genero aventura` | A Dizzy-style adventure: four screens per level, a bag for three things, doors that ask for their own and the uncontrollable jump |
| `ngplat nuevo <folder> --genero filmation` | A Knight Lore-style isometric castle: six rooms per level, cubes to climb onto, a talisman that opens the final door and an editor that edits rooms |
| `ngplat nuevo <folder> --genero kungfu` | A Bruce Lee-style temple: four screens per level, lanterns to put out, vines to climb, the flying kick and two pursuers who follow you from room to room and hit each other |
| `ngplat nuevo <folder> --genero grafica` | A point-and-click graphic adventure: a cursor, four verbs, two rooms that answer each one and a puzzle of key, lantern and crowbar |
| `ngplat nuevo <folder> --genero carretera` | An Out Run-style driving game: two stretches —the coast and the mountain—, traffic to overtake, checkpoints that extend the clock and a car with two gears |
| `ngplat nuevo <folder> --genero vacio` | **Nothing made**: a hero, a flat floor and a goal, and that is it. Not one enemy, not one object, not one note. It compiles and plays as it is, and it carries a note in the `game.yaml` itself of which section is missing and what it is called. It is where you start if what you want is your game and not ours |
| `ngplat nuevo <folder> --estilo hierro` | The same, but drawn with six colours and ready for the Amiga's dual playfield |
| `ngplat comprobar [project]` | Validates the `game.yaml` and says how much room the game takes |
| `ngplat probar [project]` | Opens the preview and the editor, and keeps serving it |
| `ngplat app [project]` | The same, but **in a window of its own**: no address bar and no tabs, and it stops the server when you close it |
| `ngplat compilar [project]` | Generates `build/<machine>/` with the C, the graphics and the Makefile |
| `ngplat compilar --make` | Also builds the ROM or the floppy |
| `ngplat copia [project]` | Saves a copy of the project into its history |
| `ngplat historial [project]` | Lists the saved copies, newest to oldest |
| `ngplat recuperar N [project]` | Takes the project back to copy N (saving how it is first) |
| `ngplat sistemas` | Lists the machines, what each one takes, how it sounds and what it does with the parallax |

Any command accepts `--sistema neogeo|megadrive|amiga` to work with a machine
without touching the `game.yaml`. The preview too: it draws with the colours
that will really be seen on that machine.

`ngplat probar` opens the browser and **keeps serving** the preview on
localhost until you press Ctrl+C; that is what makes the editor's "generate
ROM" button work. With `--no-servidor` the file is opened bare, as before, and
with `--no-abrir` only the HTML is generated.

Every command has an English alias (`new`, `check`, `preview`, `build`).

## What is inside

```
neoplat/
├── ngplat                  the command (Python, no dependencies)
├── tools/ngplat/           compiler: YAML → C + graphics + preview
│   ├── project.py          reads and validates game.yaml (messages in Spanish)
│   ├── build.py            packs graphics, tiles and levels (no hardware)
│   ├── codegen.py          generates gamedata.c/h and assembles the project
│   ├── sistemas/           one machine per file
│   │   ├── base.py         what a system has to know how to do
│   │   ├── neogeo.py       C1/C2/S1/M1 ROMs and ngdevkit Makefile
│   │   ├── megadrive.py    VDP tiles, 4 palettes, PSG and cartridge header
│   │   ├── amiga.py        bitplanes, masks, Paula and AmigaDOS executable
│   │   ├── jaguar.py       one byte per pixel, object list and .j64 cartridge
│   │   └── atarist.py      4 bitplanes, YM2149 and floppy with an AUTO folder
│   ├── gfx.py              PNG → Neo Geo palettes and tiles (C ROM / S ROM)
│   ├── gfx_md.py           PNG → the VDP's 8x8 tiles and palette sharing
│   ├── gfx_amiga.py        PNG → 5 interleaved bitplanes and their masks
│   ├── gfx_jaguar.py       PNG → one byte per pixel and a 256-colour table
│   ├── gfx_st.py           PNG → the ST's 4 bitplanes and one-word masks
│   ├── hunk.py             ELF → AmigaDOS executable (hunks + relocation)
│   ├── adf.py              bootable 880 KB floppy (bootblock + OFS)
│   ├── prg.py              ELF → GEMDOS executable (.PRG + relocation)
│   ├── st_disk.py          720 KB floppy with FAT12 and an AUTO folder
│   ├── claves.py           names each option accepts (used by the editor)
│   ├── sonido.py           notes -> periods for the SSG, the PSG, Paula or the YM2149
│   ├── m1.py / z80.py      the Z80's sound driver and its assembler
│   ├── jerry.py / dsp.py   the Jaguar DSP's sound driver, and its assembler
│   ├── preview.py          generates the playable preview
│   ├── servidor.py         localhost: the editor sends the yaml and compiles
│   ├── png.py / miniyaml.py  readers of our own (zero dependencies)
│   ├── art.py / scaffold.py  the example project
│   ├── art_sonido.py       the example WAVs, generated from code
│   ├── wav.py / adpcm.py   WAV reader and the YM2610's codec
│   ├── md_pcm.py           the Mega Drive Z80's sample driver
│   └── paths.py            where everything is, inside the .exe too
├── engine/
│   ├── core/np_world.c     the simulation (physics, collisions, enemies)
│   ├── core/np_aritmetica.c 32-bit multiply and divide on a 68000
│   ├── neogeo/             the console's video, HUD, sound and controller
│   ├── megadrive/          VDP, window plane, PSG, startup and header
│   ├── amiga/              copper, blitter, Paula and startup
│   ├── jaguar/             the video object, the DACs and the DSP
│   ├── atarist/            Shifter, YM2149 and IKBD, all with the CPU
│   └── host/np_trace.c     runs the simulation on the computer (tests)
├── preview/
│   ├── np_core.js          the same simulation, in JavaScript
│   ├── np_editor.js        the editor (drawing, properties, validation)
│   ├── np_yaml.js          rewrites the game.yaml without touching the rest
│   ├── np_pixel.js         the graphics editor (sprites, tiles and backgrounds)
│   ├── np_sonido.js        compiles notes, sweeps and noise (twin of sonido.py)
│   └── np_bot.js           the bot that checks whether a level can be finished
├── examples/
│   ├── bosque-magico/      example game ready to compile
│   ├── cueva-de-hierro/    the same engine with six colours and Amiga parallax
│   └── costa-y-montana/    a driving game: the roadway is not a drawing
└── tests/                  590 tests + 263 gameplay ones + the editor's +
                            a bot that finishes the levels + emulators and browser
```

**The engine is C, not C++**, on purpose: ngdevkit's compiler does not bring
libstdc++, and on a 68000 at 7 MHz virtual calls and templates only add cost.
The game's logic is generated by the compiler, so you do not write C anyway.

## Adding another machine

The three there are now carry a 68000, so they share the engine as it is; a new
system only has to implement `tools/ngplat/sistemas/base.py`:

- `preparar(build)`: convert the graphics and palettes to the chip's format.
- `comprobar(build)`: warn about what does not fit (messages in Spanish).
- `generar(build)`: the files that are missing (graphics, sound, Makefile).
- `archivos_motor`: which part of the engine gets copied (video, HUD, sound,
  startup).

And in `engine/<machine>/`, the usual four pieces: drawing a frame, the
scoreboard, the sound and reading the controller. The Atari ST is the example
of how far that separation goes: it has no sprites, no blitter and no hardware
scroll, and even so the `np_world.c` running inside it is exactly the same one.
Everything else (levels, physics, enemies, collisions, editor, preview, tests)
is already done and is not touched.

## The same simulation in all eight places

`engine/core/np_world.c` (the seven machines) and `preview/np_core.js`
(browser) are the same simulation written twice: integers and 24.8 fixed point,
no decimals. `tests/test_paridad.py` runs both with the same button presses and
compares, frame by frame, the position, the speed, the camera, the score and a
hash of every entity. If you touch one and forget the other, the test fails.

That is why what you play in the browser is exactly what will happen on the
console, and it does not matter which one.

## Tests

```bash
make test           # tools, validation, C generation and C/JS parity
make test-emulador  # boots the ROM and the floppy in real emulators
make test-navegador # opens the preview and the editor in Chromium
node tests/comportamiento.js   # 263 gameplay tests
make ejemplo-todos             # compiles the example for all seven machines
```

The emulator and browser tests are optional: if you do not have
`libretro-genesisplusgx`, `amitools` or Playwright installed, they skip
themselves. The Neo Geo cannot be put in an ordinary emulator without SNK's
BIOS, so the kit brings its own test bench: the real 68000 (Musashi, MAME's
core) and the video chip written by hand in `tests/maquina_neogeo.py`.

What they check: the PNG reader against Pillow, the YAML reader against PyYAML,
a round trip of all four graphics formats (Neo Geo tiles, VDP tiles, Amiga
bitplanes and masks, the Jaguar's one byte per pixel), the `game.yaml`'s error
messages, that the generated C compiles without warnings
(`-Wall -Wextra -Werror`) and also with a real 68000 compiler, that the Mega
Drive cartridge and the Amiga executable get built and have the shape each
machine expects, the C/JavaScript parity and the mechanics (variable jump,
coyote time, jump buffer, one-way platforms, stomping enemies, damage, death,
level change, camera).

## State and limits

Verified here:

- The generated C project compiles with `gcc -Wall -Wextra -Werror`, and also
  **really for the 68000** with `m68k-linux-gnu-gcc`.
- **The Mega Drive ROM boots and plays in an emulator**: the tests
  run it in Genesis Plus GX with no screen, check that it draws the title
  screen with its scoreboard, that pressing start begins the game and that the
  stage moves when you run, and leave screenshots. It is the one thing that
  cannot be checked by compiling, and it found two bugs no other test could see
  (see [megadrive.md](megadrive.md)).
- **The Mega Drive cartridge is built whole**: 128 KB with the
  `SEGA MEGA DRIVE` header, the game's name, the ROM range and the checksum,
  which the tests work out again and compare.
- **The Neo Geo ROM draws the game**: the tests run it on the kit's own bench
  —the real 68000 plus the video chip rebuilt in Python—, reconstruct the
  picture from VRAM, the graphics ROMs and the palettes, and check that the
  title comes up, that START begins the game and that the stage moves when you
  run. It found a scoreboard bug no other test could see (the title's text was
  left written over the game).
- **The game runs at 60 of the Neo Geo's 60 fps** (29 on the bad frames before
  optimising): the bench counts each frame's 68000 cycles and the test fails if
  any goes over the 200,000 the console gives. How it was done, in
  [neogeo.md](neogeo.md).
- **The Atari Jaguar cartridge boots and plays in an emulator**: the tests run
  it on Virtual Jaguar, which does not need Atari's BIOS for cartridges, and
  check that the title comes up with its scoreboard, that pressing the button
  begins the game, that the stage moves when you run and that the scoreboard
  **does not come out doubled** (the video chip composes the object list while
  the beam crosses the screen, so rewriting it at the wrong moment paints
  things twice). How the machine works and the four traps that were hard to
  find, in [jaguar.md](jaguar.md).
- **The binary carries nothing the 68000 does not understand**: the tests go
  over the machine code of all **eight targets** (the Neo Geo too, by compiling
  its sources without linking) and fail if a 68020 instruction or an odd-address
  access shows up. That is how it was found that the Neo Geo ROM was carrying
  the same bug that hung the Mega Drive one.
- **The Amiga executable is built whole**: two hunks marked as chip RAM, the
  relocation table checked entry by entry (no address falls outside its hunk)
  and `_start` on the first byte, as AmigaDOS expects.
- **The game runs at 49 of the Amiga's 50 fps** (25 before optimising):
  measured in scanlines inside an emulated A500, part by part. How it was done,
  in [amiga.md](amiga.md).
- **The Amiga floppy boots and plays in an emulator**: the tests put it in an
  emulated A500 (PUAE with AROS's free ROM) **with the memory the game
  declares** in `amiga_ram:`, wait for it to boot on its own, check that the
  game comes up with its scoreboard, press start and play. It found a bootblock
  bug no other test could see.
- **And that each game fits in the Amiga it declares**: the tests build all
  twenty-two starter games (eleven genres by two styles) and measure the
  executable against what that machine leaves free. It found four that did not
  boot on a stock A500 and nobody knew: the floppy mounted all the same and the
  desktop stayed on screen.
- **And the floppy too**: a 901120-byte `.adf` with a `DOS\0` bootblock, an OFS
  file system and `s/startup-sequence`. The tests check that **every** checksum
  adds up (the bootblock's, with carry, and each disk block's), that the bitmap
  marks exactly what is taken and that the executable comes off the disk byte
  for byte as it went in.
- **The Atari ST boots and plays in an emulator**: the tests put the floppy in
  an emulated ST (Hatari with EmuTOS), wait for TOS to run the game from the
  `AUTO` folder and check that the title comes up with its scoreboard, that the
  joystick button begins the game, that the YM2149 plays the `game.yaml`'s
  notes and that the stage moves when you run. It found a keyboard bug that
  failed one time in two: if the ACIA is left with an unread byte before the
  interrupts are opened, the MFP never warns again and the controller is dead
  forever.
- **The game runs at 25 frames per second on the ST** (10 before optimising),
  and at about 17 on the screens that combine scrolling with many actors; the
  simulation runs at 50 steps per second in both cases, the same as the Amiga
  (the other four run at 60, their vertical blank's). Measured in scanlines
  inside an emulated ST, setting the border to a colour while it draws. What
  raised it most was not the drawing but the order of the loop, and along the
  way an ugly bug came out: with a single vertical-blank wait per turn, a
  screen with little to draw made the game run at **twice the speed**. It is
  covered in [atarist.md](atarist.md).
- **And its floppy too**: a 737280-byte `.st` with FAT12, the game in the
  `AUTO` folder and a GEMDOS `.PRG` with its relocation table, which the tests
  walk fix-up by fix-up. The floppy is also read by `mtools` without complaint,
  which is a FAT implementation that is not ours.
- The C engine and the JavaScript preview give identical results frame by
  frame.
- The platform mechanics work (24 gameplay tests).
- The example levels can be finished: a bot plays them all the way through on
  every test run, so an impossible level never slips in.
- The same game compiled for all seven machines describes exactly the same
  levels, enemies and maps: the tests check it.
- A round trip of all five graphics formats (Neo Geo tiles, VDP tiles, Amiga
  bitplanes and masks, the Jaguar's one byte per pixel, the ST's four
  bitplanes): encoding and decoding gives back the original image.
- **All seven machines make sound, and they sound what the `game.yaml` says**:
  the tests capture what comes out of the speaker —from the libretro core on
  Mega Drive, Amiga, Jaguar, Atari ST and X68000, and from the whole
  68000 → Z80 → YM2610 circuit on the Neo Geo— and recognise the notes one by
  one. On all seven **16 of 16** of the melody come out, the example's title
  screen is silent (it declares no `titulo:`) and on a jump the effect is heard
  over the music. Checked that the test knows how to fail: with a deliberately
  mute board, all three checks fail. How it is done, in [sonido.md](sonido.md).
- All six play the same note: 440 Hz comes out at 440 Hz on the SSG, on the
  PSG, on Paula, on the Jaguar's DACs, on the YM2149 and on the YM2151 (with
  each one's rounding).
- The preview is opened in Chromium during the tests and checked to draw what
  it should (screenshots reviewed by hand).
- The editor makes the whole round trip in the tests: it edits maps, physics
  and levels, exports the `game.yaml`, it is compiled again and it is checked
  that not a single comment is lost.
- The graphics editor too: in Chromium the player's PNG is opened, a line is
  painted on it with the mouse, it is undone and the PNG that comes out is
  checked to be exactly the sheet's size.
- The names the editor writes into the `game.yaml` are checked one by one
  against the kit's reader.
- **Both controllers reach both players on all seven machines**: with
  `jugadores: 2`, the tests play the same game three times in each emulator
  —with one controller, with the other and with both— and demand that all three
  end up different. That is where it was seen that on the Jaguar the matrix's
  rows **are not asked for with the same number** on one port as on the other,
  which is what stopped the second controller getting through.
- **The digital samples are audible**: the test project sets as the jump effect
  a pure 3,000 Hz tone with no fallback notes, and the test measures that
  frequency in what comes out of the emulator before and after jumping. It
  sounds 20 times louder on the Amiga, 19 on the Mega Drive, 13 on the Neo Geo
  and 8 on the Jaguar; with the sample path switched off in the Amiga's driver,
  0.4. The Mega Drive's Z80 driver is run byte by byte in the kit's emulator,
  bank crossing included, and on the Neo Geo the bench decodes the ADPCM-A in
  order to hear it.
- **The attack does what it says**: nine JavaScript gameplay tests (that the
  projectile flies the way you are facing, kills and scores, dies against a
  wall and on running out of reach, that the rate of fire is respected, that
  holding the button does not fire endlessly, and that the melee hit reaches
  the next cell and no further), plus the C/JS parity with both attack types:
  the projectiles go in the same entity list, so they go into the trace's hash.
- **The keys really do lock the goal**: five JavaScript gameplay tests (that
  without a key the goal does not open, that with one it does, that a key worth
  several opens on its own, that the one a player picks up works for the other
  and that they are not kept from one level to the next), plus a variant of the
  C/JS parity that checks across the whole trace that the level never ends with
  the counter at zero.
- **The candelabra loop**: fourteen JavaScript gameplay tests (that the
  candelabrum does no damage and is not picked up, that the melee hit and the
  shot break it and what it carries comes out resting where it was, that an
  empty one drops nothing, that with `vida:` several attacks are needed, that
  up + action spends ammo and without ammo it hits instead of throwing, that
  the plain button does not spend, and that the arcing weapon falls and the
  straight one does not), plus a parity variant: the scaffold brings candelabra
  and a knife, so the traces also compare the ammo, and a test checks that in
  that trace some candelabrum gets broken and the ammo gets spent —otherwise
  the parity would be comparing two engines that do nothing.
- **The stairs, the checkpoints and the weapon upgrades**: twenty-four
  JavaScript gameplay tests (that you climb with up and with down, that inside
  there is no gravity and no jump, that you come out standing at both ends,
  that a hit throws you off; that the torch neither gets in the way nor does
  damage but notes its cell, that on dying you reappear at it and not at the
  start, that without touching it you reappear at the start, that the last one
  you pass counts and that passing it again does not sound; that the stock whip
  falls short and with one upgrade it reaches, that the upgrades stop at the
  limit and are lost on death), plus the C/JS parity variants. In the castle's
  trace it is checked that the checkpoint lights up **and** changes where you
  reappear, and that the upgrade is picked up and lost: without that, the
  parity would be comparing two engines that note the cell and then ignore it.
- **The whip, crouching and the secondary weapons**: that the whip is on screen
  for exactly the nine frames in which it does damage —not before, during the
  wind-up, nor after—; that crouched you neither walk nor jump and that a flyer
  that hits you standing passes over you crouched; that the axe object changes
  the weapon, that whatever is already thrown keeps the one it came out with
  and that `a_la_vez` limits how many are in the air. The whip, crouching and
  the weapon you are carrying also go in the trace, so the C/JS parity compares
  them frame by frame.
- **The moving platforms carry the player**: eight JavaScript gameplay tests
  (that it goes back and forth between its two ends and does not overshoot,
  that the player plants himself on top and moves exactly as much as it does,
  that a vertical one takes him up and down without lifting him off on any
  frame, that you can jump from on top, that from below you pass through, that
  pressing down drops you off and that it does no damage), plus a variant of
  the C/JS parity: the platform moves before the players, and if the two
  implementations did not do it in the same order the positions would drift on
  the first turn.
- **The graphics land on an even address**: the Atari ST and the Amiga read the
  tiles long word by long word even though the array is of bytes, and on a
  68000 doing that at an odd address stops the machine dead. One test looks at
  the ELF's symbols and another at the generated declaration.
- The Z80's sound driver is run in an emulator included in the tests: it is
  checked that it receives the 68000's commands and writes into the chip the
  periods and volumes of the notes written in the `game.yaml`.

**Not tried on real hardware**: all seven have been seen working in emulators,
but not on real machines. And on the Neo Geo the emulator is the kit's own,
which takes two things for granted because the engine takes them for granted
too: that sprite 0 goes in front of the rest and that row 0 of the fix plane
lands on line 0 of the screen. If on trying it on an MVS you see the background
covering the player, it is inverted with `NP_SPRITE_FRONT_FIRST` in
`np_video.h`; if you see the scoreboard shifted vertically, it is the second
one.

What it does not do yet:

- **Several parallax layers on the Amiga and the X68000**: with
  `amiga: 8colores` the game uses OCS's *dual playfield* mode and **one** layer
  is drawn, moved in hardware; the rest are ignored. On the X68000 the same
  happens for another reason: the graphics screen is a single page in that
  mode. Drawing them with the blitter and keeping the 32 colours is measured
  and **does not fit**: 1,311 scanlines against the 313 a frame gives
  ([amiga.md](amiga.md)).
- **Digital samples on the Atari ST**: the other six already play them. An
  effect can be a WAV of yours (`muestra: sonidos/x.wav`). Paula plays it from
  chip RAM on the Amiga; on the Mega Drive a Z80 driver the compiler itself
  generates feeds it to the YM2612's DAC; on the Jaguar the DSP reads it from
  the cartridge; on the Neo Geo they go on the YM2610's ADPCM-A channels, with
  the V1 ROM the compiler also assembles (with its codec, in pure Python); and
  on the X68000 the MSM6258 puts them out over DMA, with that same codec, which
  is from the same family. The one that cannot is the **Atari ST**: its YM2149
  only makes square waves and has nothing to read a sample with, so there the
  notes you put alongside are what sounds, and the compiler warns about effects
  that would be left mute for not carrying them.
- **Parallax on the Atari ST with `camara: scroll`**: with `pantallas` it does
  get drawn, and it comes free because the view is standing still; sliding, the
  whole screen would have to be repainted every few pixels and it does not fit
  ([atarist.md](atarist.md)).
- **Sprite zoom outside the road**: the Neo Geo shrinks sprites in hardware and
  the engine **already uses it** —the road's traffic grows with the scaler and
  not in jumps of five sizes, [neogeo.md](neogeo.md) covers it— but only there:
  a boss coming at you in the other genres does not make use of it yet.

## Licence

Do whatever you like with it.
