# Your first game in 10 minutes

## 1. Create the project

```bash
./ngplat nuevo mijuego --titulo "MI JUEGO" --autor "TU NOMBRE"
cd mijuego
```

The first thing it asks you is the **genre**, with a menu:

```
que tipo de juego quieres hacer?

   1) plataformas       salto controlado en el aire, disparo y pisar enemigos
   2) castlevania       salto sin control, latigo, escaleras y arma secundaria
   3) comando           visto desde arriba: ocho direcciones y prisioneros
   4) mazmorra          laberinto: la vida se gasta sola y los nidos sacan bichos
   5) barrio            yo contra el barrio: se colocan, avisan y esperan turno
   6) aventura          cargar con las cosas y abrir con ellas lo que no se pasa
   7) filmation         una habitacion vista desde una esquina: cubos y salas
   8) kung-fu           un templo de pantallas fijas: faroles, lianas y dos que
                        te siguen
   9) aventura grafica  se senala, no se anda: un cursor, cuatro verbos y una
                        habitacion que contesta
  10) carretera         un juego de conducir: dos marchas, trafico y el crono
  11) vacio             nada hecho: un heroe, un suelo y una meta, y ya

elige [1]:
```

The genre is not decoration: it changes the jump's physics, the weapon, whether
you can stomp enemies and even the first level's map. Some change more still:
the third and the fourth are seen **from above**, so there is no gravity and no
jumps and you walk in eight directions (see ["a game seen from
above"](#a-game-seen-from-above) and ["a dungeon"](#a-dungeon) at the end), and
the ninth you do not even walk in: you **point** (see ["a graphic
adventure"](#a-graphic-adventure)). The tenth is a **driving** game, and the
eleventh is not a genre: it is the one that **brings no game**, so that you can
make your own (see ["starting from scratch"](#starting-from-scratch) at the
end). If you already know what you want, pass it directly and the menu is
skipped:

```bash
./ngplat nuevo mijuego --genero castlevania
```

You can change your mind later: everything the menu chooses is ordinary
`game.yaml` fields you can edit by hand.

You now have a complete game: two levels, a hero, two enemies and coins.

## 2. Try it

```bash
../ngplat probar
```

The browser opens with the game. Arrows to move, <kbd>Z</kbd> to jump,
<kbd>Enter</kbd> to start. **This is exactly what the console will do**: the
simulation is the same one.

## 3. Change the map (with the mouse)

In the preview, press <kbd>E</kbd>. The editor appears: you choose what to
paint from the palette (floor, platforms, spikes, enemies, coins, the start)
and you paint on the level. With <kbd>2</kbd> you make rectangles, with
<kbd>3</kbd> you fill areas and with <kbd>Ctrl</kbd>+<kbd>Z</kbd> you undo.
<kbd>Enter</kbd> tries it straight away and <kbd>E</kbd> takes you back to the
editor.

In the **revisar** tab there is a button that sends a bot in to play the level:
if the bot reaches the goal, so will you.

When you like it, go to the **game.yaml** tab and copy or download the file.
The whole editor is explained in [editor.md](editor.md).

## 3b. …or change the map by hand

Open `game.yaml` and look for `niveles:`. The map is characters:

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

- `P` where you start (only one)
- `#` floor, `=` a platform you pass through from below, `^` spikes
- `G` the goal
- `~` the water's surface and `w` the bottom: there you swim and dive (the
  first level's pond is made of those; see "5b. The water")
- `s` a mushroom, `c` a coin, `k` a key, `T` a board that goes back and forth
  (see `spawns:`)
- `/` and `|` stairs (in the castlevania genre): you climb by pressing up while
  on them and you go up diagonally, step by step
- `!` a checkpoint (also in castlevania): it does not get in the way, but if
  you are killed you reappear there instead of at the start of the level
- `M` the whip upgrade: each one lengthens it a little, and they are lost on
  death

Change whatever you like and run `../ngplat probar` again. It takes less than a
second.

A tip: the hero's default jump rises **2 tiles** and crosses **3 tiles** of
gap. If you make a gap of 4, it cannot be crossed (or raise `salto:`).

## 4. Change the character

The graphics are in `graficos/`. `heroe.png` is a strip of 6 frames of 16x16
pixels:

| 0 | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| idle | run | run | run | jump | fall |

Open it with any pixel editor (Aseprite, Piskel, GIMP, Paint) and draw over it.
Rules:

- **15 colours maximum** plus the transparent one.
- The frame's size has to be a multiple of 16.
- If you add frames, change the `animaciones` in the `game.yaml` too.

Want a taller hero? Make the frames 16x32 and put:

```yaml
jugador:
  frame: [16, 32]
  caja: [10, 30]
```

## 5. Tune how it feels

These are the options that change the game most:

```yaml
jugador:
  velocidad: 1.6      # raise it to 2.2 for a fast game
  salto: 4.3          # 5.2 jumps much higher
  gravedad: 0.28      # 0.20 = floaty, 0.40 = heavy
  doble_salto: si     # a second jump in mid-air
```

Change a value, `../ngplat probar` and you feel it immediately.

And if you want it for two:

```yaml
juego:
  jugadores: 2
```

Both play at once on the same screen, each with their own controller and their
own lives. In the preview the second goes with
<kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> and jumps with <kbd>G</kbd>.

## 5b. The water: swimming and diving

The game you have just created **already brings a pond**, in the first level,
just past the spikes. Run to the right and fall in: the hero changes posture
and sinks slowly.

There are **two ways up, and it is worth trying both**:

- **up**, held: you rise for as long as you hold it, like someone swimming. It
  is what you do to keep from sinking and to get your head out.
- **the jump button**, which in the water is **a stroke**: a sudden push you
  can repeat. With your head out it pushes far harder and it is what gets you
  onto the bank — and, like any jump in the game, **you have to hold it**: if
  you let go straight away, the push is cut and you are left on the edge.

There are two postures and **the head** decides, not the feet. With your head
out you are swimming: you breathe, you float and the next stroke takes you out
of the water. With your whole body under you are diving, and there the air
starts going down; when it runs out your health goes point by point until you
come up. Get your head out and the air comes right back in one go: the water is
not a resource to manage, it is a place you have to come up from.

In the `game.yaml` the whole of the water is this:

```yaml
tiles:
  leyenda:
    '~': {tile: 9, tipo: agua}      # the surface
    'w': {tile: 10, tipo: agua}     # the bottom
jugador:
  brazada: 2.0        # 0 = the water cells do nothing
  aire: 240           # frames diving before drowning (0 = never)
```

The rest —how fast you sink, how much you move sideways, how much up lifts you,
the push you come out with— is filled in from the land figures, and can be
edited by hand (`gravedad_agua`, `hundimiento`, `velocidad_agua`,
`subida_agua`, `salto_agua`). Raise `aire: 240` to `aire: 0` and the water
stays as a different way of moving, with no drowning.

**To dig your own** two things are needed: the water's row goes **level with
the ground** you walk on (if you put it above, it will look like a block of
water floating) and below the bottom there has to be earth, because the water
does not hold you up and below the map you fall into the void. Two cells deep
is the minimum: with one your head does not fit under and you never get to
dive.

**And if you do not want it**, delete `brazada:` from `jugador:` and the
compiler takes the water out of the executable entirely: 3000 bytes less on the
Amiga and 1934 cycles per frame less on the Neo Geo. The `'~'` and `'w'` cells
you leave on the map stay as scenery.

## 6. Add a new enemy (from the editor)

The quickest way: in the preview press <kbd>E</kbd>, **enemies and objects**
tab, **"+ new enemy"** button. You give it a name, choose a behaviour and draw
it right there (or reuse one of the project's graphics). On creating it, it
appears in the palette and you can paint it on the map straight away.

If you have drawn it, the **game.yaml** tab gives you a button to download its
PNG: save it in `graficos/` and you are done.

## 6b. …or by hand in the file

```yaml
enemigos:
  fantasma:
    sprite: graficos/enemigo.png
    comportamiento: perseguidor    # it follows you if you get close
    velocidad: 0.7
    rango: 120
    puntos: 300

spawns:
  f: fantasma        # now you can put 'f' in the maps
```

## 6b. Change the background

The project comes with two parallax layers (`graficos/cielo.png` and
`graficos/arboles.png`). They are ordinary PNGs that repeat horizontally:

```yaml
fondos:
  - nombre: cielo
    imagen: graficos/cielo.png
    velocidad: 0.2      # the lower, the further away it looks
    y: 0
  - nombre: arboles
    imagen: graficos/arboles.png
    velocidad: 0.5
    y: 144
```

Paint over those PNGs (15 colours per layer) or add another layer. If one
particular level wants different layers, you tell it so in the level itself
with `fondos: [cielo]`.

## 6c. Change the music

The music and the effects are in the `game.yaml` too, written with notes:

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

Change the notes and run `../ngplat probar` again: the preview plays it
straight away (with <kbd>M</kbd> you mute). The first track is the melody and
the second the accompaniment; the chip's third channel is kept for the effects.

## 7. Add a level

Copy a level's block and change the map. They are played in order:

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

## 8. Make the ROM

```bash
../ngplat compilar
cd build/neogeo
make          # needs ngdevkit installed
make run      # boots ngdevkit's emulator
```

If you do not have ngdevkit, `ngplat compilar` has already left in
`build/neogeo/` the whole project in C and the graphics ROMs: you can compile
it on another computer that does have it.

## 9. The same game on another machine

The game you have written works just the same for a Mega Drive, an Amiga or an
Atari ST: only how it is drawn and how it sounds change, not what happens.

```bash
../ngplat sistemas                       # every machine and its limits
../ngplat compilar --sistema megadrive   # -> build/megadrive/rom/juego.bin
../ngplat compilar --sistema amiga       # -> build/amiga/disco/MiJuego.adf
../ngplat compilar --sistema amiga1200   # -> the same, with AGA: 256 colours
../ngplat compilar --sistema cd32        # -> build/cd32/disco/MiJuego.iso
../ngplat compilar --sistema jaguar      # -> build/jaguar/rom/MiJuego.j64
../ngplat compilar --sistema atarist     # -> build/atarist/disco/mijuego.st
```

The CD32 is the A1200's game on a CD: the executable is identical and what
changes is the wrapper. For the CD to boot by itself on a real console you have
to add Commodore's marker (`make MARCA=/path/CD32.TM`), which cannot be
distributed with the kit; without it the ISO is just as valid but does not
boot.

For these five ngdevkit is not needed, only any 68000 compiler
(`m68k-elf-gcc`, or Debian and Ubuntu's `gcc-m68k-linux-gnu` package). Add
`--make` and it builds it in one go.

The Amiga one is a **real floppy**: an 880 KB `.adf` that boots by itself,
without Workbench. You put it in FS-UAE, WinUAE or Amiberry (or in a Gotek, if
you have the Amiga in front of you) and switch on:

```bash
cd build/amiga
make run          # with FS-UAE installed, inserts the floppy and boots
```

**And say which Amiga you are aiming at**, with `amiga_ram:` in `juego:` —
`512K` (the stock A500, which is what the scaffold brings), `1M` or `2M`. It
does not change what gets compiled: what it does is make `make` **stop** if the
game does not fit in that machine, instead of putting out a floppy that boots
and sits at the desktop without saying anything. Inside the `.adf` there is
also a README saying which Amiga is needed, for when you pass it on to
somebody.

And the Atari ST one is another real floppy: a 720 KB `.st` with the game in
the `AUTO` folder, which is where TOS boots it from on power-up. It goes in
Hatari, in Steem or in an ST with a Gotek in front of it:

```bash
cd build/atarist
make run          # with Hatari installed, inserts the floppy and boots
```

Each machine has its own ways, and `ngplat comprobar --sistema <machine>` tells
you before compiling: the Mega Drive only shows 64 colours and one background
layer, the Amiga 32 colours and levels up to 16 cells tall (or 32, if the level
does not go over 22 wide), and the Atari ST 15 colours, no parallax and a
200-line screen instead of 224. If something does not fit, the message tells
you what it is and what to take out.

And if your game is short of colours, try `--sistema amiga1200`: it is the same
Amiga with the AGA chipset, and there it is **256 at once** with none of them
rounded. The floppy it puts out demands an A1200, an A4000 or a CD32.

You can also write it down in the `game.yaml` and forget about it:

```yaml
juego:
  sistema: megadrive
```

## Making something happen: scripts

Up to here the `game.yaml` describes **a world**. What it does not say is that
**something happens**: that stepping on a cell opens a door, that a sign warns
you, that the second time you pass, things have changed. That is what the
scripts are for, and their memory is the variables.

This is the shortest thing you can write to see it:

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

You put a `C` on the map and you have a sign that can be read, that remembers
you read it and that says something else the second time.

**A script is a list of steps.** They are not blocks you drag around: here the
project is text on purpose —it reads, it compares, it goes into git and the
editor rewrites it without touching your comments— and a script is too. There
are eight steps: `decir`, `esperar`, `poner`, `sumar`, `si`, `sonido`, `dar`
and `ir_a_nivel` (you have them all in
[formato.md](formato.md#variables-and-scripts)).

Three things worth knowing from the start:

- **The steps that do not wait all run in the same frame.** Setting three
  variables and giving an object costs one frame, not four. Only `decir:`
  —until you press— and `esperar:` stop.
- **While a script is running, the game does not**: not you, not the creatures,
  not the clock. A text box while you are being killed from behind is not a
  text box, it is decoration.
- **The variables belong to the game**, not the level: they survive changing
  level and losing a life. That is what lets the game remember what you did two
  levels back.

A script is launched in two ways: by stepping on a cell that carries it
(`guion:` in the legend, and with `una_vez: si` only the first time in the
whole game), or on starting a level (`guion:` in the level, which is how a game
tells you something before letting you play).

**The text box is two lines of 36 characters**, in the scoreboard. That is not
a whim: 36 is what fits on the narrowest of the seven machines, and the
scoreboard is the only free space that does not cover the game. The text is
broken into words **in the compiler**, so a long `decir:` comes out as several
pages and they are turned with the button.

The adventure genre already comes with all of this set up: try
`./ngplat nuevo miaventura --genero aventura` and look at its `game.yaml`.

## A game seen from above

```bash
./ngplat nuevo micomando --genero comando
```

This genre is something else. It is seen **from above**, like Ikari Warriors or
Guerrilla War: there is no gravity and no jumping, and the level is not crossed
from left to right but **climbed**. You start at the very bottom and the base
is at the top.

The controls change with the view:

- **Arrows**: you move in **all eight** directions, diagonals included.
- <kbd>X</kbd>: you shoot **where you are looking**, whichever way that is.
- <kbd>Z</kbd> / <kbd>space</kbd>: instead of jumping, you **throw a grenade**.
  The scoreboard shows how many you have left (`GRAN 03`) and they are
  restocked from the crates.

The map is drawn the same as in the other genres, only tall and narrow:

```yaml
  - nombre: "EL CAMPAMENTO"
    mapa: |
      AAAAAA..,G,..AAAAAAA
      AAAAA.,,,,,,,.AAAAAA
      ...
      AAAAA...P....AAAAAAA
```

`P` at the bottom, `G` at the top, and in between a path that **bends**: the
turns are what make it a game, because a straight corridor is climbed by
walking and that is that. What narrows it are the trees (`A`), the sandbags
(`#`) and the river (`~`), which is one of the things that kill.

What is new in this genre is two things:

- **The enemies shoot.** The soldiers and the turrets carry a `dispara:` block
  with their rate of fire (`espera:`) and their range. That rate of fire is
  what decides whether a place can be got past or not: raise it and the way
  closes.
- **The prisoners.** The symbol `R` places a tied-up prisoner. If you **touch**
  him, he is freed and scores 500 points; if you **shoot** him, you lose him
  and score nothing. It is what forces you to look before pulling the trigger.
  They are explained in [formato.md](formato.md#prisoners).

Everything else is the same: the same PNG graphics, the same editor with
<kbd>E</kbd> and the same `ngplat compilar`.

About the machines: these levels are **32 cells tall** and they fit on all six.
The Amiga and the Jaguar draw the stage in a bitmap that can be laid out wide
(44 × 16 cells) or tall (22 × 32), and they choose by themselves according to
the game's tallest level; in exchange, with the tall shape the level has to fit
whole across: 22 cells. If you go over, `ngplat comprobar` tells you in those
words before compiling.

## A dungeon

```bash
./ngplat nuevo micripta --genero mazmorra
```

This is also seen from above, but it plays differently: this is a Gauntlet. The
level is not a path, it is a **maze** of 20 × 28 cells that is seen almost
whole, and what decides the game is not your aim but which way you go.

Three rules change everything:

- **Health drains by itself.** The player comes with `vida: 200` and
  `desgaste: 12`, that is one point every twelve frames: about forty seconds on
  the clock. The scoreboard shows it as a number (`LIFE 184`) and it is always
  going down, whether anyone hits you or not. It is restored with food
  (`efecto: salud`), which is the only thing that stops the countdown.
- **The nests pour out creatures endlessly.** The symbol `n` places a nest and
  `N` a crypt, and each one puts out its creature every so many frames until
  you smash it with arrows. While it is still standing, killing what comes out
  achieves nothing: it is what pushes you into going where you did not want to
  go.
- **The potion clears the screen.** The jump button does not jump (here there
  is nothing to jump over): it throws a potion. And there is another, `r`,
  which on being picked up damages **everything visible at that moment**, nests
  included. The classic smart bomb: it is worth whatever the moment you pick it
  up is worth.

And on top of that the goal asks for a key that is on the far side of the maze,
so you have to go all the way round with the clock running. Going for
everything —the food on one side and the treasure on the other— is running out
of health: that is the genre.

```yaml
jugador:
  vida: 200
  desgaste: 12         # one point every 12 frames

generadores:
  nido:
    genera: bicho      # what it puts out
    cada: 100          # every how many frames
    tope: 3            # how many of its own can be out at once
    vida: 3            # arrows it takes
```

The two mazes it brings can be finished on foot, and there is a test that
checks it with a bot that goes **for the key first** and then to the exit
(`tests/test_niveles.py`). If you touch the map and close a way, that test
tells you.

Everything else is as always: the same PNGs, the same editor and the same
`ngplat compilar` for all seven machines. They are explained in detail in
[formato.md](formato.md#spawners) (`generadores`, `desgaste` and
`efecto: bomba`).

## Me against the neighbourhood

```bash
./ngplat nuevo micalle --genero barrio
```

A brawler, the Double Dragon kind. It is seen **from the side**, like the
platform one, but you do not walk along a line: you walk along a **strip of
ground** with depth, up and down. And the jump is a third separate coordinate:
the height above the ground.

Those three coordinates are the whole genre:

- **Two people at different depths do not touch.** Even if on screen it looks
  as if they do. That is why the first thing in any fight is to line up, and
  that is why moving up and down is dodging.
- **On jumping, your box goes up with the graphic**, so a punch at ground level
  passes underneath you.

### The ones in front of you

And what makes this a fight and not a swarm: **the enemies do not come to rub
against you, they come to hit you**. Each one with `golpe:` does four things,
and all four are felt on the controller:

1. **It places itself and does not get inside you.** It comes as close as its
   arm reaches and stops there. You never end up with three on top of you
   pushing.
2. **It waits its turn.** `agresivos:` says how many can be hitting **at
   once** —two, as in the arcades—; the rest circle. It is the genre's most
   important number and the least visible: without it there is no gap between
   one hit and the next.
3. **You see it coming.** Before throwing it there are `preparacion:` frames of
   warning. Without that there is no dodging and the game is unfair; with it,
   every hit you take is your own fault.
4. **It leaves a window.** After hitting it stands there for `recuperar:`
   frames. That gap is your turn, and the fight's rhythm comes out of it.

And **they surround you**: half of them come from the other side, so turning
round matters.

When you land a hit, the world **stops** for four frames (nine on the finisher)
and on knocking somebody down the screen **shakes**. It is not decoration:
without that pause the fist goes through the other person and nothing is felt.

The controls:

- **Arrows**: you move in all eight directions, across the width of the street.
  And **two taps in a row** in the same direction: you **run**. Running is the
  answer to being surrounded.
- <kbd>X</kbd>: punch. And here comes the good part: if you press again before
  the window closes, you **chain** —punch, punch and **finisher**—. The
  finisher does more damage and **knocks down**: whoever takes it is thrown
  back and spends a few frames on the floor, deciding nothing and doing you no
  harm.
- <kbd>X</kbd> **with somebody behind you**: **elbow**. If whoever is on you is
  at your back and there is nobody in front, you turn round by yourself.
  Turning round by hand with three around you is impossible, so the game does
  it.
- <kbd>X</kbd> **in mid-air**: **jump kick**. It hits like a finisher and
  knocks down. It is the way into a group without taking the three hits on the
  way in, and it costs something: in mid-air you cannot steer.
- <kbd>X</kbd> **while running**: **shoulder charge**. It also counts as a
  finisher, and it **spends the run**: one per sprint, not a knock-down button.
- <kbd>Z</kbd> / <kbd>space</kbd>: jump.
- And whoever is **reeling** from a hit can be **grabbed** by touching them:
  with <kbd>X</kbd> you knee them and with <kbd>Z</kbd> you throw them over
  your shoulder. Throwing is the game's strongest move and it also gets them
  off you, which when there are three of them is half the fight.

One more thing, and it is the one that changes how it plays: **somebody who has
already started throwing a punch is not stopped by an ordinary punch**. You
have to get out of the way —move in depth, which is where their hit does not
reach—, jump over them or spend something strong on them. If any old fist cut
it short, hitting non-stop would be enough and we would be back to mashing the
button.

**The camera has a lock**: while anyone is left alive on screen, the view does
not advance. That is not configurable and cannot be removed: it is what turns a
corridor into a fight. If you head right without hitting anybody, you stay
where you are.

The map is a street of 48 × 14 cells: the buildings at the top, the kerb at the
bottom and in between the seven rows you walk along.

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

`P` on the left, `G` on the right, `m` thugs, `b` the big ones, `B` barrels
(which break and drop a chicken) and `J` the boss. What makes it a game is not
the drawing of the ground, it is **where each group plants itself**: since the
camera does not move on, each group is a screen.

And the groups are of **two and three**, not seven: since only two hit at a
time, what makes the difficulty is not how many there are but **who** —the big
one telegraphs more but hits twice as hard— and how much room they leave you.

And one thing you feel while playing: the actors are painted **from far to
near**. In a game where everyone treads on everyone, otherwise you cannot tell
who is in front of whom. The engine takes care of that on all seven machines.

## An adventure

```bash
./ngplat nuevo miaventura --genero aventura
```

A Dizzy-style adventure. It is seen **from the side**, like the platform one,
but it is not about jumping well: it is about **taking the right thing to the
right place**.

Three rules, and all three change how it plays:

- **You do not hit.** The action button does not attack: it **drops** the first
  thing you are carrying. And three things fit in the bag, so carrying one is
  deciding not to carry another.
- **What stops you is not a creature: it is a lock.** A door, a bonfire or a
  wall that hold you like a wall until you turn up with the right thing. On
  opening them the object is spent and the way stays open **for good**. The
  creatures are not killed: they are dodged.
- **The jump cannot be steered in mid-air.** On take-off you decide where you
  are going and with how much push, and until you land it cannot be changed;
  not even letting go of the button shortens it. It sounds awkward and it is
  exactly what makes each jump a decision. Watch out: if you hit a wall
  sideways you lose your push, so to climb a step you have to jump **before**
  reaching it.

The controls:

- **Arrows**: walk.
- <kbd>Z</kbd> / <kbd>space</kbd>: jump (the fixed jump).
- <kbd>X</kbd>: drop the first thing in the bag, at your feet.

At the top, in the scoreboard, is **what you are carrying**: without looking at
it you cannot tell whether the door ahead opens or you have to turn back.

The camera goes **screen by screen**, with no scroll: each level is four
screens of 20 × 14 side by side, and each one is a place. The starter project's
two levels are the same chain told two ways:

- **EL VALLE**, in order: the key opens the door, behind it is the bucket that
  puts out the bonfire, and behind that the pick that brings down the wall.
- **LA CUEVA**, out of order: the pick and the key are picked up together right
  at the top and are needed on different screens, so you have to **remember**
  what you are carrying.

In the `game.yaml`, a lock is a tile with `tipo: cerrojo` and the object that
opens it:

```yaml
tiles:
  leyenda:
    'D': {tile: 7, tipo: cerrojo, abre_con: llave}
    'F': {tile: 8, tipo: cerrojo, abre_con: cubo}
    'W': {tile: 9, tipo: cerrojo, abre_con: pico}

objetos:
  llave:
    efecto: llevar     # not spent on touching it: it goes into the bag
    marcador: LLAVE    # how it is written at the top
```

What a lock asks for has to exist and has to be one of the carryable kind: if
not, `ngplat comprobar` tells you before compiling, because a door that asks
for something that cannot be picked up is not a hard puzzle, it is a broken
game.

A **two-cell** door (one above the other) is **one** door: it opens whole and
costs a single object. And the player carries `salto_fijo: si` and
`pisar_enemigos: no`, which are the two lines that turn the platformer into an
adventure.

As in the other genres, the bot checks that both levels can be solved
(`tests/test_niveles.py`), and there is a control that removes the three
objects from the map and demands that then it **cannot** be finished.

## An isometric castle

```bash
./ngplat nuevo micastillo --genero filmation
```

This is seen neither from the side nor from above: you see **a room from a
corner**, as in Knight Lore. And it is the genre that changes the most things,
because it even changes what the map means.

**The map is no longer what you see: it is the room's floor plan.** Each cell
carries a height, and with that number the whole stage is written:

```yaml
tiles:
  leyenda:
    '.': {tile: 0, tipo: vacio}                              # floor
    'e': {tile: 0, tipo: solido, alto: 4,  cubo: escalon}    # walked up
    'o': {tile: 0, tipo: solido, alto: 16, cubo: losa}       # one jump
    'O': {tile: 0, tipo: solido, alto: 32, cubo: pilar}      # two heights
    '#': {tile: 0, tipo: solido, alto: 48, cubo: pintado}    # back wall
    'M': {tile: 0, tipo: solido, alto: 48, cubo: muro}       # and this walls it off
```

And a room is written like this, in eight lines of eight:

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

The first row and the first column are the two **back walls** —on screen they
fall behind everything, which is what makes a room look like a room—. They come
already drawn, with a door in the middle of each, so on the map they are
written with `'#'`: it stops whoever walks into it and costs not one sprite.
Where that door leads nowhere it is walled off with `'M'`, which is a real
cube.

That is not a whim: fifteen wall cubes per room are what separates a Mega Drive
running at 60 from one running at 30. And they are not needed, because a back
wall never covers anybody.

The genre's three rules:

- **What stops you is the height.** There are no wall tiles and floor tiles:
  there is a number. Six pixels are walked up, sixteen have to be jumped and
  forty-eight cannot be passed. The stock jump reaches 23, and that difference
  **is** the game's design: to get to the top you have to find the step.
- **The controller goes along the map's axes**, not the screen's: right is the
  floor plan's x axis, which on screen comes out down and to the right. Written
  down it sounds odd and played it is learned in two steps; in exchange, the
  controller's diagonals give the four straight sides of the screen.
- **The jump cannot be steered in mid-air.** As in the adventure: on take-off
  you decide and until you land it cannot be changed. What is kept is the push,
  so to climb onto a cube right next to you no run-up is needed.

The controls:

- **Arrows**: walk about the floor plan.
- <kbd>Z</kbd> / <kbd>space</kbd>: jump.
- <kbd>X</kbd>: drop what you are carrying (the talisman).

Jumping is not only for climbing: it is the way to **dodge**. Over a spike
nothing happens, and over a creature nothing either, because in this view two
things that do not cross in height do not touch.

A room is **8x8 cells** and the map is divided into whole rooms: the starter
project's two levels are six rooms each, three by two. On crossing the edge the
camera **jumps** to the one next door, and what happens in the rest stays
paused —that is how a whole castle fits in a 1985 machine: only the cubes of
the room being looked at exist—.

- **EL PATIO** shows the relief, and shows it in order. The entrance room puts
  a step, a slab and a spike side by side —what you walk up, what you jump and
  what kills—; the third is a wall of slabs with the key behind it, which is
  the first time the game asks you to climb onto something to get anywhere; and
  the spike crossing is taken in zigzag or over the top. Three keys and the
  exit in the last room.
- **LAS MAZMORRAS** adds two things. The genre's staircase: from the floor to a
  16 slab and from the slab to a 32 pillar, because one jump climbs 23 pixels
  and the pillar cannot be reached from the ground. And the puzzle: the exit is
  behind a door with a talisman carved on it, and the talisman is at the far
  end of the upper floor. You have to cross the whole level, come back and go
  down.

**The editor edits rooms.** On entering with <kbd>E</kbd> no tile grid comes
up: the rooms come up drawn isometrically, with their cubes and their creatures
placed where they will be while playing, and the mouse clicks **on the
diamond**. In the palette each cell comes out with its cube and its height
—"solid: wall (height 48)"— which is what is needed in order not to confuse a
wall with a step.

A room's drawing —the two back walls and the floor— is a rectangle of the
tileset itself (`sala: {tile: 16, ancho: 16, alto: 11}`): repainting it changes
the whole castle without touching anything else.

As in the other genres, the bot checks that both castles can be finished, and
there is a control that removes the talisman from the map and demands that then
it **cannot** be finished.

## A kung-fu temple

```bash
./ngplat nuevo mitemplo --genero kungfu
```

This one is seen from the side, like the platform one, but it is not about
reaching the end: it is about **working your way through** a temple putting out
lanterns with two men after you. It is Bruce Lee from 1984, and what makes it
that game and not another is three rules that go together.

**1. The ones chasing you do not belong to the screen: they are yours.**

```yaml
  yamo:
    comportamiento: perseguidor
    tenaz: si          # esta linea es el genero entero
```

With `tenaz: si`, on changing screen the enemy **comes back in through the edge
you came in by**. You do not leave him behind by changing screen: you dodge
him, you knock him down or you use him. Without that line each screen is a
puzzle solved calmly; with it, dawdling costs, and retracing your steps means
walking straight into the one who was behind you.

**2. They hit each other.**

```yaml
juego:
  entre_ellos: si    # el golpe de un bicho le hace dano al de al lado
```

The ninja's stick lands on Yamo just as it lands on you. It sounds like a
detail and it is half the mechanics: two pursuers that hit each other stop
being two problems and become a tool, because placing them so that they cross
is the only thing you have when you cannot handle either of them.

**3. You climb, and a vine is not a staircase.**

```yaml
tiles:
  leyenda:
    '|': {tile: 5, tipo: liana}
jugador:
  trepa: 1.1         # 0 = las casillas de liana no hacen nada
```

A staircase is climbed from the ground and diagonally. A vine **you grab in
mid-air**, it is climbed straight and from it you jump wherever you like with
push: it is the way to what is up there and the way to get yourself out of
trouble. `trepa:` is what switches it on: at zero the same cells are still
drawn and stop grabbing.

And on top of the three, the attack has two forms:

```yaml
  ataque:
    tipo: golpe
    alcance: 14
    patada: 26       # en el aire llega casi al doble
    dano_patada: 2   # y duele el doble
```

`patada:` is what turns the jump into an attack. Without that line, hitting in
mid-air brings out the same short punch and jumping is only good for moving.
With it, the flying kick has its own reach, its own damage and its own graphic
(the `patada:` animation, which is why the frames are 32×32: a hit that reaches
further has to **look** longer).

**What opens the door is the lanterns.** The object carries `efecto: llave` and
the level says how many it asks for:

```yaml
objetos:
  farol:
    efecto: llave
    cantidad: 1
niveles:
  - nombre: "EL PATIO DEL TEMPLO"
    llaves: 5        # hasta que no estan los cinco, la puerta no se abre
```

The two levels you get are four screens each, with no scroll: each screen is a
hall of the temple.

- **EL PATIO DEL TEMPLO** teaches one thing at a time. The first screen has
  only beams —three steps of two cells, which is exactly what the jump
  climbs—; the second adds the vine and Yamo, who is slow but does not get left
  behind; the third the spike pits; and the fourth the ninja and the door. Five
  lanterns.
- **LAS ENTRAÑAS** no longer teaches anything: it uses. Both creatures from the
  first screen, twin vines, spikes under nearly everything and **seven**
  lanterns for a door that asks for six: the spare one is so that you can
  choose between climbing for it or staying below and fighting.

**The back wall is a layer, not cells** (`fondos: [muro]`, with
`velocidad: 0.5`). That way it takes up no map, it does not get in the way of
jumping and it shifts half a screen on changing hall, which is what keeps the
four from looking like the same one.

As in the other genres, the bot checks that both levels can be finished, and
there is a control that **removes the vine** from the second screen and demands
that then the lantern at the top cannot be reached.

## A graphic adventure

```bash
./ngplat nuevo lacasa --genero grafica
```

This one is not like any of the eight before it, and in one way: **here you do
not walk**. The player is a cursor. It has no weight, it does not collide, it
does not collect and it cannot die; all it does is move about the screen and
point.

```yaml
juego:
  vista: puntero
  verbos: [MIRAR, COGER, USAR, HABLAR]
  sin_efecto: nada
```

**The controller carries a verb.** The jump button —which here has nothing to
jump over— moves to the next of the four, in a loop, and the action button
applies it to the cell you are pointing at. The verb is written at the top, in
front of what you are carrying, because without seeing it the game turns into
guesswork.

It is the kit's first view where **what happens on pressing depends on
something you are carrying**, and the whole genre comes out of that: the same
door answers one thing when you look at it and does another when you open it.

**The cells answer.** In the legend, one script per verb:

```yaml
tiles:
  leyenda:
    'q': {tile: 13, tipo: vacio, mirar: mirar_cuadro, hablar: hablar_cuadro}
    'K': {tile: 22, tipo: vacio, debajo: 'u', mirar: mirar_llave, coger: coger_llave}
```

A big piece of furniture is several cells and they all carry the same scripts:
the painting is four tiles and the player need not find out. And when the cell
you are pointing at does not answer that verb, the game answers for it with the
`sin_efecto:` script, written once and in your own words.

**Picking something up is four steps**, and here you see what the scripts are
for:

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

`quitar:` erases the cell from the map: it stops being drawn and stops
answering. What you see in its place is whatever its `debajo:` says —there,
`'u'`, which is the right half of the table— and that is why picking up the key
leaves the table bare and not a wall-shaped hole.

**The whole puzzle fits in one script**, because an adventure puzzle is a
condition:

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

**And it ends with `acabar:`**, because here there is no goal cell to step on:
on opening the cellar's chest with the crowbar, the last script says
`acabar: si` and, being the last level, the game is over.

The example is two rooms —grandfather's study and the cellar—, a portrait you
can talk to (and which remembers how many times you have talked to it), a
lantern, a key, a trapdoor that asks for both and a chest that will not give
with bare hands.

The kit's bot plays this too, but differently: since there is no route to look
for, it goes to each cell that answers to something and tries all four verbs on
it, over and over, shuffling the order. It is the same thing a person does when
stuck, and if trying everything does not finish the game, then it has no
solution. There is also a control that **removes the crowbar** from the cellar
and demands that then the chest does not open.

## A driving game

```bash
./ngplat nuevo micircuito --genero carretera
cd micircuito
../ngplat probar
```

Out comes an Out Run: two stretches —the coast and the mountain—, traffic to
overtake, checkpoints and a car with two gears. **← →** the steering, **B** to
accelerate, **↓** to brake and **A** to change gear.

The first thing to understand about this genre is that **it is not a new
view**:

> The map is the **road's course seen from above**, and the car climbs it.

Open it in the editor (<kbd>E</kbd>) and you will see: there is no road drawn,
there is a vertical map, very long, with a strip of asphalt winding along it.
That is what the car travels; what is on screen is that same map projected.

```
,,,,,.....,,,,,        ',' the grass: you do not go fast there
,,,,,.....,,,,,        '.' the asphalt
,,,,.....,,,,,,        and the road goes off to the left...
,,,.....,,,,,,,
,,.....,,,,,,,,
```

And the whole game comes out of that, with nobody programming it: **the car
goes straight**. Nobody puts you into the corner. If the road bends and you do
not turn, off you go —and off the asphalt you do not go fast—.

### How tight a corner can be

This is worth knowing **before** drawing a course, and it is a division. The
engine does two sums per frame:

```
vy = velocidad                       what goes up the map
vx = volante * velocidad / punta     what moves sideways
```

Both go with the speed, so on dividing them it cancels out: what the car moves
**per row of road** is `volante / punta`, and it **does not depend on how fast
you are going**. With the stock values, `2.2 × 16 / 6.0 = 5.87` pixels per row:

> the tightest corner that can be followed shifts **one cell every three
> rows**.

Tighter than that cannot be taken, and **braking does not help**: the line you
can take is the same at 6.0 as at 1.0. If you want tighter corners to be
takeable, raise `volante:` or lower `punta:`; it is the same sum from both
ends.

```yaml
coche:
  volante: 2.2     # lo que se mueve de lado, a punta
  punta: 6.0       # lo que corre con la marcha larga
  respuesta: 0.55  # lo que gira el volante por frame
```

**`respuesta:` is the feel**: how much the steering turns per frame. By default
it is a quarter of `volante:`, that is four frames from straight to full lock
and another four back, and that is why correcting a corner is something you do
*beforehand* and not in the moment. Raise it and the car is twitchy; lower it
and it has weight. What does not change is the sum above: the steering stores
**how far it is turned**, not pixels, so what it moves per row still does not
depend on how fast you are going, not even halfway through the turn.

What you do gain by braking is something else: **the spin-out only happens if
you were going faster than `lento:`**, so easing up against the crash barrier
slowly does not send you spinning. Braking does not take a finer line; brake so
as not to crash.

### Draw a corner

Change the map in the editor and try it: you do not need the bot, you drive.
With the rule above, a corner of one cell every three rows is followed hugging
the edge, and one of one cell every six is taken without thinking.

### The clock is your life

Here there is no health to lose in one hit. Hitting the crash barrier puts you
into a **spin-out** —90 frames of spinning— and that does not kill you: it
costs you time. What kills you is the clock running out.

```yaml
juego:
  tiempo: 60       # segundos. Los controles de paso lo alargan.
```

And since time is only earned by **arriving**, the checkpoints are the game's
entire economy:

```yaml
tiles:
  leyenda:
    'K': {tile: 3, tipo: control}    # +20 segundos al cruzarlo
```

Put them where the stretch gets hard and the game becomes fair; put them too
close together and there is no tension left. With `tiempo: 0` there is no clock
and you drive at leisure, which is what you need for trying a new course.

### The traffic is not enemies

They are obstacles: they come up their own lane, minding their own business,
and they neither chase you nor shoot at you. What you decide is **which side to
pass them on**.

```yaml
enemigos:
  rival:
    comportamiento: trafico
    velocidad: 2.6
    vida: 99       # no se matan: se adelantan
```

The engine draws them shrunk according to how far away they are, so the sprite
is drawn **at close-up size** and the kit derives the rest.

### The seven colours

The roadway is not a drawing: it is seven colours the engine paints line by
line, in bands that run towards you.

```yaml
carretera:
  asfalto: ["#4a4a52", "#282830"]
  arcen:   ["#d0d0d8", "#c02020"]
  hierba:  ["#3a7a42", "#2c5434"]
  raya:    "#e8e8f0"
```

Change them and you have another place: sand and sky, snow, night. The only
thing to respect is that **the two shades of each pair are properly apart**:
the Mega Drive and the Atari ST store three bits per channel and two similar
shades land on the same colour for them, and then the bands are not seen to run
and it looks as if the car is standing still. `ngplat comprobar` warns you if
it happens.

Everything that can be touched is in [formato.md](formato.md): the
[`carretera`](formato.md#carretera) section for the colours and
[`coche`](formato.md#coche) for the engine, the brake and the steering.

## Starting from scratch

The ten genres bring a finished game —nine have their chapter here; the
`castlevania` one is written just like the platform one, with what the
[front page](neoplat.md#what-a-game-looks-like) covers—. It is fine for seeing
how something is written —that is what this tutorial is for— but it is the
opposite of what you need once you know and what you want is **your** game: you
start from a finished game by **deleting**, and deleting in a three-hundred-line
`game.yaml` breaks something.

That is what the eleventh is for:

```bash
./ngplat nuevo mijuego --genero vacio
cd mijuego
```

And that is everything there is:

```
mijuego/
├── game.yaml
├── .gitignore
└── graficos/
    ├── heroe.png
    └── tiles.png
```

Two PNGs, which are the two the `game.yaml` names: if the style's twenty were
copied, the folder you start with would have nineteen graphics you do not use,
which is exactly what this genre comes to clear out of the way.

The game that comes out **runs**: a hero, a flat floor and a goal at the end.

```
........................................
........................................
..P.................................G...
########################################
```

Flat on purpose. The first thing you are going to do is change the map, and a
row of hashes is understood at a glance: each character is a cell, `#` is the
floor, `P` is where you come in and `G` is the goal. Try it before touching
anything —`../ngplat probar`— and you will have something that walks, jumps and
finishes; from there on, whatever goes wrong is yours and not what came with
it.

There are no enemies, no objects, no music and no parallax. What there is, at
the end of the file, is the **list of what is missing**: what each section is
called and what it is for.

```yaml
# LO QUE FALTA, Y COMO SE ANADE
#
#   enemigos:     bichos, con 'comportamiento:' (patrulla, volador,
#                 perseguidor, saltarin, fijo, cocodrilo, balanceo) y, si
#                 quieres que te tiren cosas, un bloque 'dispara:'
#   objetos:      lo que se coge, con 'efecto:' (puntos, vida, salud,
#                 llave, municion, mejora, subarma, bomba, llevar)
#   ...
```

None of them is needed to compile: they are added as they are needed, and each
goes at the top level. The whole list of what can be written is in
[formato.md](formato.md).

And if at some point you want to see how one of the genres solves something
—how a boss is declared, how a song is written, how a script is put together—
create it in another folder and copy the piece:

```bash
./ngplat nuevo /tmp/mirar --genero castlevania
```

## When something fails

```bash
../ngplat comprobar
```

It tells you the problem, where it is and how to fix it. Examples:

```
error en niveles[1]: el mapa usa el simbolo '@' (fila 4, columna 12) y no esta en la leyenda
  pista: anadelo en 'tiles: leyenda:' o en 'spawns:' del nivel

error en jugador: el fotograma mide 12x12 y la Neo Geo dibuja sprites en bloques de 16x16
  pista: usa medidas multiplos de 16 (16x16, 16x32, 32x32...)
```
