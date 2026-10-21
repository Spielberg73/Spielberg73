# `game.yaml` reference

Every key can be written in Spanish or in English (`jugador`/`player`,
`salto`/`jump`…). Speeds go in **pixels per frame** and times in **frames**,
except where it says otherwise.

> The keys themselves are **not translated**: this is a translation of the
> documentation, not of the format. `velocidad:` is `velocidad:` (or `speed:`)
> in every language.

A frame is **one step of the simulation**, and how long it lasts is set by each
machine's vertical blank: 60 per second on the Neo Geo, the Mega Drive, the
Jaguar and the X68000, and **50** on the Amiga, the A1200, the CD32 and the
Atari ST, which are PAL. That is, a jump measures the same pixels on all seven,
but on the PAL ones it takes a sixth longer to make. Where these pages
translate frames into seconds they do it at 60, which is the fast case.

If you write an option wrongly, `ngplat comprobar` tells you which one it is
and where.

---

## `juego`

```yaml
juego:
  titulo: "BOSQUE MAGICO"   # shown on the title screen (max. 24 letters)
  autor: "DAVID"
  jugadores: 1              # 1 or 2 at once
  vidas: 3                  # 1 to 9, for each player
  tiempo: 0                 # seconds per level; 0 = no limit
  hud: si                   # score/lives scoreboard
  camara: scroll            # scroll or pantallas
  amiga: 32colores          # Amiga only: 32colores or 8colores
                            # (on the A1200: 256colores or 16colores)
  amiga_ram: 512K           # which Amiga it is aimed at: 512K, 1M or 2M
  fondo: "#101830"          # default background colour
  sistema: neogeo           # neogeo, megadrive, amiga, jaguar or atarist
```

`camara` decides how the view moves, and it changes quite a lot about what the
game feels like:

| | |
|---|---|
| `scroll` | the camera follows the player and the stage slides. It is what the consoles of the day did. |
| `pantallas` | the level is divided into fixed screens and the view **jumps** to the next one when the player crosses the edge. It is what nearly all the 8-bit computer games did. |

With `pantallas` it is best for the levels to measure an exact number of
screens (multiples of 20 tiles wide and 14 tall); if not, the last one overlaps
the one before and the compiler warns.

**What the jump costs.** Changing screen forces the stage's twenty columns to
be repainted at once, and that squeezes every machine. Each one handles it its
own way:

| | |
|---|---|
| Neo Geo | fills ten columns per frame and turns off the ones not yet valid: the change looks like a two-frame sweep. Without this it went to 214,558 cycles of the 200,000 the console gives (measured with the kit's bench). |
| Mega Drive | writes the plane's twenty columns on the frame of the jump |
| Amiga | repaints the twenty columns with the blitter: about 620 scanlines against a frame's 313, that is two or three frames lost on the change |
| Jaguar | repaints the whole bitmap, as on any other frame |
| Atari ST | repaints the twenty columns with the CPU, which is what it always does; it costs it one of its drawings, that is two hardware frames. And it is the only place where the ST draws parallax: with the view standing still, painting it comes free |
| X68000 | writes the twenty columns of the name table, like the Mega Drive: one word per cell and the chip does the rest |

All six are checked in an emulator (`tests/test_sistemas.py`,
`TestCamaraPorPantallas`): that the view stands still on nearly every frame and
that every so often it changes all at once.

`amiga` is only looked at when compiling for the Amiga, and it decides how its
six bitplanes are shared out:

| | |
|---|---|
| `32colores` | five bitplanes in a single plane: **31 colours** for the graphics, no parallax. |
| `8colores` | three and three, in *dual playfield*: the game in front with **7 colours** and a parallax layer behind with another 7, moved in hardware. |

In `8colores` hardly any graphic fits as it is, so the leftover colours are
swapped for the nearest of the ones that remain and the compiler tells you how
many it has had to approximate. If you want to be in charge of the colours,
draw with seven. The other machines ignore this option.

### `amiga_ram`: which Amiga the game is aimed at

```yaml
juego:
  amiga_ram: 1M      # 512K (the stock A500), 1M or 2M
```

It does not change a single byte of what gets compiled: the `.adf` that comes
out is the same. What changes is that **the compiler knows what to measure
against**.

The Amiga has a failure mode that gives no warning: if the executable does not
fit in the machine's memory, the floppy boots, AmigaDOS cannot load the game
and the desktop stays on screen. Not a message. From outside it is
indistinguishable from a broken floppy, and whoever tries it is not whoever
made the game. With this line, `make` **stops** before assembling the floppy
and says how much it takes and how much fits.

| `amiga_ram` | the machine | fits |
|---|---|---|
| `512K` | a stock A500 | ~190 KB |
| `1M` | A500+, A600, expanded A500 | ~702 KB |
| `2M` | A1200, A4000, CD32 | ~1726 KB |

Of those three numbers **only the first is measured**: on an emulated 512 KB
A500, at 189 KB the game boots and at 209 it does not —and those same 209 boot
as soon as the machine has a megabyte—. The other two are those 190 plus the
extra memory.

And it is **chip** RAM, not memory in general: the game is loaded entirely into
chip —both hunks are asked for that way, because it is the only kind the
copper, the blitter and Paula can reach— so an expansion's *fast* RAM is of no
use to the executable. That is why the list ends at 2 MB: there is no Amiga
with more chip memory than that, and putting eight megabytes in an A1200 does
not make a bigger game fit.

The A1200 and the CD32 do not look at this line: they carry 2 MB as standard
and there is nothing to choose. And the floppy comes out with a **README
inside** saying which Amiga is needed, which is what anybody you hand an `.adf`
to misses when it does not boot for them.

**The starter games that ask for a megabyte.** Not all of them fit in a stock
A500, and until 1.52 nobody knew that: they compiled, assembled their floppy
and did not boot. Now they declare it, and it is measured genre by genre:

| genre | bosque | hierro |
|---|---|---|
| plataformas | 189 KB | **210 KB — 1M** |
| castlevania | **193 KB — 1M** | **213 KB — 1M** |
| filmation | **197 KB — 1M** | **196 KB — 1M** |
| kung-fu | **195 KB — 1M** | **195 KB — 1M** |
| comando, mazmorra, barrio, aventura, grafica, carretera | 180–189 KB | 180–189 KB |

The short-palette ones weigh more and **not because of the colours**: OCS's
dual playfield carries two bitmaps instead of one, and that is about 20 KB more
of chip RAM.

`tests/test_sistemas.py` builds all twenty-two for real and measures them
against the Amiga they declare. When that test fails it will not be the genre's
fault: it will be that the engine no longer fits where it used to.

`sistema` decides which machine it is compiled for and which colours the
preview is drawn with. It can also be chosen without touching the file, with
`--sistema` on any command:

```bash
ngplat compilar --sistema megadrive
```

The usual alternative names work: `genesis` or `md` for the Mega Drive, `a500`
for the Amiga, `aes` or `mvs` for the Neo Geo.

### The controllers

| | moving | jumping | **action** (attack; with ↑, secondary weapon) | start |
|---|---|---|---|---|
| preview | arrows or WASD | <kbd>Z</kbd>, <kbd>K</kbd>, <kbd>space</kbd> | <kbd>X</kbd> (or <kbd>L</kbd>) | <kbd>Enter</kbd> |
| Neo Geo | stick | button A | **button B** | START |
| Mega Drive | d-pad | B (or A) | **button C** | START |
| Atari Jaguar | d-pad | button A | **button B** | PAUSE |
| Sharp X68000 | stick | button A | **button B** | button A |
| Amiga | joystick | fire | **second button** | fire (or the mouse button) |
| Atari ST | joystick or arrows | fire or <kbd>space</kbd> | **<kbd>X</kbd> or <kbd>Control</kbd>** | fire or <kbd>Enter</kbd> |

The **secondary weapon** is thrown with **up + action**; the plain button does
the normal attack. On the Amiga and the Atari ST the usual joystick has **a
single button**, so there that button jumps *and* starts the game, and the
action goes on the second button (Amiga) or on the keyboard (ST). With a
one-button controller it plays just the same, but without attacking.

In two-player games, in the preview the second one goes with **WASD**, jumps
with <kbd>G</kbd> and attacks with <kbd>H</kbd>.

### Two players

With `jugadores: 2` two people play at once, each with their own controller, on
the same screen and at the same time (not in turns). Both are the same
`jugador` from the `game.yaml`: the same graphic, the same jump and the same
lives; they come out together at the level's start, 20 pixels apart.

What changes compared with one player:

| | |
|---|---|
| the camera | goes to the midpoint of the two, and lets neither go off: whoever falls behind stops against the edge of the screen |
| the lives | are each player's own, and the scoreboard says `1P 3  2P 3` instead of `LIVES 3` |
| dying | whoever runs out of lives disappears and the other carries on; the level only restarts (or the game only ends) when both fall |
| starting | start on either controller works |

Where the second controller is plugged in on each machine:

| | |
|---|---|
| Neo Geo | the board's port 2 (`$340000`), with its START and SELECT on bits 2 and 3 of STATUS_B |
| Mega Drive | the second controller connector (`$A10005`) |
| Amiga | the **mouse port**, which is the left one: the mouse has to come out and the other joystick go in there. In two-player games, the mouse button stops working as start |
| Atari Jaguar | the second connector. Both controllers share the same matrix, but **the rows are not asked for with the same number** on one port as on the other (see `engine/jaguar/np_video.c`) |
| Atari ST | **port 0**, which is the mouse's, just as on the Amiga. The keyboard still belongs to the first player only |
| X68000 | **port B** of the 8255; A is the first player's |

In the preview, the second player goes with **WASD**, jumps with **G** and
attacks with **H**. In one-player games, WASD still works as the arrows.

All six are checked in an emulator (`tests/test_sistemas.py`,
`TestDosJugadores`): the same game is played three times, with one controller,
with the other and with both, and all three have to end up different. If the
second controller did not get through, or if both read from the same place,
they would come out the same.

### `agresivos`: how many hit at once

```yaml
juego:
  agresivos: 2
```

Only the brawlers (`vista: cinta`) with enemies that have
[`golpe:`](#golpe-the-enemys-attack) look at it. It is **how many enemies can
be hitting at once**: the rest circle waiting their turn.

It is the genre's most important number and the least visible. With all of them
at once there is no gap between one hit and the next and the fight is a swarm;
with only one the street is empty. Two is what the arcades did.

### The view: from the side, from above or from a corner

```yaml
juego:
  vista: cenital       # lateral (the default), cenital, cinta,
                       # isometrica, puntero or carretera
```

**`lateral`** is the usual one: there is gravity, you jump, you face one way or
the other and the floor is the floor.

**`cenital`** is the top-down view of the commando games (Ikari Warriors,
Guerrilla War, Commando). It changes the whole game:

| | lateral | cenital |
|---|---|---|
| gravity | yes, you fall and you jump | no: whatever does not move, stays |
| movement | left and right | all **eight** directions (the diagonals go at 0.707 so that they are not faster) |
| where you shoot | the way you are facing | **where you are looking**, in the eight directions |
| the jump button | jumps | throws the secondary weapon (the grenade) |
| the map | sky above and an abyss below | it is a **closed box**: all four sides are wall |
| stairs, crouching, stomping enemies | yes | make no sense and are switched off |

The hero is drawn facing three ways and the engine chooses by itself: `arriba`
(from behind) when going up, `abajo` (facing you) when going down and `correr`
for the sides, which is mirrored as always. Without those graphics `correr` is
used for everything.

```yaml
jugador:
  animaciones:
    quieto: {frames: [0]}
    abajo:  {frames: [0, 1], velocidad: 8}   # facing you
    arriba: {frames: [2, 3], velocidad: 8}   # from behind
    correr: {frames: [4, 5], velocidad: 8}   # side on
```

**`cinta`** is the view of the brawlers (Double Dragon, Final Fight, Streets of
Rage): it is seen from the side, but you walk along a **strip of ground** with
depth. It is the top-down view **plus a third coordinate**, the height above
the ground, which is what the jump raises:

| | cenital | cinta |
|---|---|---|
| movement | the eight directions | the same |
| the jump button | throws the secondary weapon | **jumps**, and in mid-air you cannot change your mind |
| the action one | shoots where you are looking | **hits** at close range, the way you are facing |
| two things touching | being on top is enough | they have to match **in depth and in height** |

The genre's rule comes out of that third coordinate: on jumping, your box goes
up with the graphic, so the punch from below passes underneath you; and two
people at different depths do not touch even if on screen it looks as if they
do. That is why before hitting you have to **line up**.

What is drawn is the usual —side on, facing right, and the engine mirrors it—
plus two slots that show here: `saltar` and `remate`.

**And the camera has a lock**: in `cinta`, while an enemy is left alive on
screen, the view does not advance. Backwards it does move, because what is
closed is the way forward and not the view. That is not configurable: it is
what turns a corridor into a fight, and without it the game is walked through.

**`isometrica`** is the view of the *filmation* games (Knight Lore, Alien 8,
Head Over Heels): a **room seen from a corner**. It is the one that changes the
most of all, because it even changes what the map means:

| | cinta | isometrica |
|---|---|---|
| the map | is what you see | is the room's **floor plan**: what you see are its rooms |
| the cells | are of a type | are of a type **and of a height** |
| what stops you | a wall | how high the next cell is compared with your feet |
| the controller | the screen's eight directions | the **map's axes**, which come out diagonal on screen |
| the camera | follows the street | shows **the room you are in** and jumps to the next one as you cross |
| jumping | gets you over a punch | gets you over **a spike, a creature or a cube** |

#### The relief

Each symbol in the legend carries an `alto:` in pixels, and with that number
the whole stage is written:

| `alto:` | what it is |
|---|---|
| 0 | flat ground, which you walk on |
| 4 or less | a step: it is climbed by **walking** |
| 16 | a cube: you have to **jump** to get onto it |
| 32 | two heights: you cannot reach it in one jump, you have to go up via the cube next to it |
| 48 | a wall |

What decides all of that is a single number, `NP_ESCALON` (6 pixels): whatever
is higher than your feet plus six stops you; whatever is not is walked up. And
the stock jump reaches 23 pixels, which is what separates a cube from a wall.

#### The drawing: `cubos:` and `sala:`

In this view the stage **does not come out of the map**: it comes out of the
cubes. Each raised cell says which one it is drawn with, and a cube is an
ordinary actor:

```yaml
tiles:
  imagen: graficos/tiles.png
  # the drawn room: 16x11 tiles of the tileset (256x176 pixels) pasted into
  # each room starting at tile (2, 2). It brings the two back walls and the
  # 8x8-cell floor
  sala: {tile: 16, ancho: 16, alto: 11, x: 2, y: 2}
  leyenda:
    '.': {tile: 0, tipo: vacio}
    'o': {tile: 0, tipo: solido, alto: 16, cubo: losa}
    '#': {tile: 0, tipo: solido, alto: 48, cubo: pintado}   # already in `sala:`
    'M': {tile: 0, tipo: solido, alto: 48, cubo: muro}      # and this one is a cube

cubos:
  losa:
    sprite: graficos/losa.png
    frame: [32, 32]          # 32 x (height + 16)
    caja: [16, 16]           # the plan it takes up: one cell
    desplazamiento: [8, 8]   # [8, height - 8]
```

A cube `alto` pixels tall is drawn in **32 x (height + 16)**: the diamond on
top, the two front faces and the point at the bottom. Its box is always
`[16, 16]` —one cell of floor plan—.

What decides whether it fits is not how tall the picture is but **where it
rests**: the bottom diamond goes flush with the bottom edge, and that fixes the
offset at `[8, picture_height - 24]`. For a cube of exactly the right size that
is `[8, height - 8]`, which is the usual. The picture can be **taller** than
the prism —the frames go sixteen at a time on all seven machines, so a 4-pixel
step has no other way of being drawn than in a 32x32 picture with the prism at
the bottom— but never shorter. The compiler warns about both.

`sala:` is a room's drawing, a rectangle of the tileset itself pasted into all
of them: the **two back walls** and the 8x8-cell floor. **Repainting it changes
the whole castle** without touching a line of anything else. There is one for
the whole game: what tells one room from another is its cubes and its
creatures.

#### `cubo: pintado`, or why the walls are not cubes

A room's two back walls are fifteen cells. Put in as cubes, that is fifteen
sprites that have to be sorted by depth and drawn sixty times a second, and
that —measured on a real Mega Drive— is 479 lines of work against the 262 a
frame lasts: the whole game at half speed.

And they are not needed. A back wall is **behind everything** by definition: it
never covers anybody, so it does not need to go into the depth queue. That is
why it comes painted in `sala:`, and on the map it is written with a symbol
carrying `cubo: pintado`: it rises 48 —that is, it stops whoever walks into it,
exactly like a wall— and nothing is drawn on top.

`sala:` leaves a door in the middle of each wall (cell 4). A room with no exit
there is walled off by putting a real wall cube —the example's `'M'`— which is
the only place on the wall where one is needed. With that, a room costs four or
five cubes instead of twenty, and the Mega Drive runs at 60.

#### The rooms

A room is **8x8 cells**, and the map is divided into whole rooms: a 24x16 level
is six rooms, three by two. Crossing a room's edge puts you into the next one
and the camera jumps; what happens in the other rooms is paused. That is how a
whole castle fits in a 1985 machine: only the cubes of the room being looked at
exist.

Since the cubes take up room in the entity list, between them and the level's
creatures and objects they cannot exceed 64. The compiler says so, with the
number of the busiest room, if you go over.

That is the limit of what **fits**; the one for what runs **smoothly** is
lower. On a Mega Drive each cube costs about 8 of a frame's 262 lines, so
beyond about fifteen per room the game starts missing the vertical blank and
goes to 30. The back walls no longer count —they go painted in `sala:`— and
with that a normal room comes down to five or six cubes with room to spare.

#### The pointer view: the graphic adventure

**`puntero`** is the graphic adventures' one, and it is the most different of
the six: here you do not walk about the stage, you **point**.

| | the other five | puntero |
|---|---|---|
| the player | a hero: has weight, collides, collects and dies | **a cursor**: no weight, no collisions, no collecting and cannot die |
| the controller | moves the hero | moves the cursor, and also **chooses a verb** |
| the jump button | jumps (or throws a grenade) | moves to the **next verb** |
| the action one | hits or shoots | **applies the verb** to the cell you are pointing at |
| what stops you | a wall, a creature, a spike | **what you do not know yet** |
| how the level ends | by stepping on the goal or killing the boss | with a script that says `acabar:` |
| the step-on triggers | fire on entering the cell | **do not fire**: passing the cursor over is not entering |

The cell you point at is the one at the **centre of the cursor's box**, so the
box (`caja:` in `jugador:`) is what decides where the arrow points: draw it
with the tip at the top left and give it a small box.

```yaml
juego:
  vista: puntero
  verbos: [MIRAR, COGER, USAR, HABLAR]   # how they are named in the scoreboard
  sin_efecto: nada                       # the "nothing to do there" script
```

**The four verbs** are always the same and in that order —it is the one the
button cycles through—; the only thing `verbos:` changes is how they are
written, so that an adventure in Spanish says MIRAR and one in English LOOK.
Six letters at most, which is what fits in the scoreboard in front of what you
are carrying.

Four and not twelve: with twelve verbs half are never used and the game turns
into trying them all, which is what killed the genre.

**What each thing answers** is said by the legend, one script per verb:

```yaml
tiles:
  leyenda:
    '.': {tile: 0, tipo: vacio}          # the wall: answers nothing
    'q': {tile: 13, tipo: vacio, mirar: mirar_cuadro, hablar: hablar_cuadro}
    'K': {tile: 20, tipo: vacio, debajo: 'u', mirar: mirar_llave, coger: coger_llave}
```

A big piece of furniture is several cells and they all carry the same scripts:
the player need not know that the door is six tiles. And `tipo:` is nearly
always `vacio`, because here nothing stops you: a cursor passes over
everything.

`debajo:` is the symbol of another cell in the legend, and it is what is seen
when a script **removes** this one from the map (see `quitar:`). Without it the
usual gap is seen —the legend's first empty tile— and picking the key up off
the table would leave a wall-shaped hole.

When the pointed-at cell does not answer that verb, the game answers for it
with the `sin_efecto:` script. Written once, in the game's own words, instead
of sixty times scattered across the map.

**What there is not in this view**: no gravity, no attack, no enemies worth
placing, no spikes that prick, no clock and no goal cell. Losing is not a
possibility; the only thing that can happen is that you do not know how to go
on. That is why a game in this genre is written almost entirely in `guiones:`.

#### The road view: the driving game

**`carretera`** is the driving arcades' one (Out Run, Chase H.Q.): the roadway
runs off towards the horizon and the only thing to do is go fast without going
off.

And inside it **is not a new view**. This is the idea everything else hangs
from:

> The map is the **road's course seen from above**, and the car climbs it. What
> changes is not the world: it is **how it is drawn**.

That is, the engine knows nothing about corners. The car goes **straight** up a
vertical map, like a top-down game's, and what the player sees is that same map
projected in perspective. The whole genre comes out of that: if the road bends
and you do not turn, **off you go** —nobody is putting you into the corner—
and off the asphalt you do not go fast. That is not programmed anywhere: it
falls out of the sum.

**How tight a corner can be** is said by a division, and it is worth knowing
before drawing a course. The engine does this:

```
vy = velocidad                       (what goes up the map)
vx = volante * velocidad / punta     (what moves sideways)
```

Both are proportional to the speed, so on dividing them it cancels out: what
the car can move **per row of road** is `volante / punta`, and it **does not
depend on how fast you are going**. With the stock values that is
`2.2 × 16 / 6.0 = 5.87` pixels per row, that is, the tightest corner that can
be followed shifts **one cell every three rows**. More than that cannot be
taken, and braking does not help: the line you can take is the same at 6.0 as
at 1.0.

What does change when you brake is **what it costs to touch**: the spin-out
only happens if you were going faster than `lento`, so easing up against the
crash barrier slowly does not send you spinning. For tighter corners to be
takeable, raise `volante:` or lower `punta:` in [`coche`](#coche): it is the
same sum from both ends.

| | cenital | carretera |
|---|---|---|
| the map | what you see | the **course**: it is not drawn, it is travelled |
| where you go | the eight directions | always **upwards**; the controller only moves sideways |
| the speed | fixed | you carry it: accelerator, brake and two gears |
| crashing | costs you health | puts you in a **spin-out**: it does not kill, it costs time |
| what you gain | points, objects | **seconds**, at the checkpoints |
| how you lose | out of lives | **out of time** |

**The controller**, which is not the other genres':

| button | what it does |
|---|---|
| ← → | the steering |
| action (B) | **accelerate** |
| down (↓) | brake |
| jump (A) | changes **gear**: low or high |

The two gears are not a gearbox: they are the arcades' arrangement. The low one
pushes hard and runs out; the high one pulls away slowly and is the one that
goes fast. Going into high too early leaves you nailed down, and carrying low
on a straight is throwing time away.

**The map is written like any other**, with the usual legend, and it is its
types that draw the road:

```yaml
tiles:
  leyenda:
    '.': {tile: 0, tipo: vacio}      # the asphalt: you go fast here
    ',': {tile: 1, tipo: lento}      # off: it does not stop you, but you do not go fast
    '#': {tile: 2, tipo: solido}     # the crash barrier: hitting it is a spin-out
    'K': {tile: 3, tipo: control}    # checkpoint: hands out seconds
    'G': {tile: 3, tipo: meta}       # and the finish, right at the end
```

The map runs **bottom to top**: the start (`P`) right at the bottom and the
finish (`G`) at the top, and the longer it is, the more road there is. A
170-row stretch is a circuit of a couple of minutes.

**The traffic** is enemies with `comportamiento: trafico`: they come up their
lane minding their own business, they neither chase you nor shoot at you. They
are not enemies, they are **obstacles**: what you decide is which side to pass
them on.

```yaml
enemigos:
  rival:
    sprite: graficos/rival.png
    comportamiento: trafico
    velocidad: 2.6
    vida: 99          # they are not killed: they are overtaken
    puntos: 0
```

The engine draws them **shrunk according to how far away they are**, at five
sizes —or smoothly, on the Neo Geo, which has a hardware scaler—. The sprite is
drawn at close-up size and the kit derives the rest.

**What there is not in this view**: no jump, no attack, no objects to collect
and no health to lose in one hit. There is only the clock. With `tiempo: 0`
there is not even that and you drive at leisure, which is useful for trying a
course.

The roadway's colours go in [`carretera`](#carretera) and the car's figures in
[`coche`](#coche).

#### The jump

It cannot be steered in mid-air: on take-off you decide where you are going and
with what push, and until you land it cannot be changed —not even by letting go
of the button—. It sounds awkward and it is exactly what makes each jump a
decision. What is kept is the **push**: if you jump right next to a cube, you
rise grazing it and as soon as you clear it it puts you on top, so climbing
onto something needs no run-up.

## `jugador`

```yaml
jugador:
  sprite: graficos/heroe.png
  frame: [16, 16]      # each frame's size; a multiple of 16
  caja: [10, 15]       # collision box (by default, the whole frame)
  velocidad: 1.6       # top running speed
  aceleracion: 0.30    # how much it accelerates per frame on the ground
  friccion: 0.35       # how much it slows on releasing the controller
  control_aire: 0.16   # acceleration while jumping
  salto: 4.3           # the jump's initial push
  corte_salto: 1.6     # on releasing the button, the rise is cut to this value
  gravedad: 0.28
  max_caida: 6.0
  doble_salto: no
  salto_fijo: no       # si (adventures): in mid-air it cannot be steered
  coyote: 6            # frames of grace to jump after leaving an edge
  buffer_salto: 6      # frames of grace to jump before landing
  pisar_enemigos: si
  rebote: 3.6          # push on stomping an enemy
  vida: 1              # hits it takes (1 to 255)
  desgaste: 0          # frames per health point that drains by itself
                       # (0 = health does not drain)
  invulnerable: 90     # frames of flashing after a hit
  retroceso: 3.0       # how hard you are thrown back on taking a hit
  aturdido: 24         # frames with no control after the hit (0 = none)
  animaciones:
    quieto: {frames: [0], velocidad: 30}
    correr: {frames: [1, 2, 3, 2], velocidad: 6}
    saltar: {frames: [4]}
    caer:   {frames: [5]}
    atacar: {frames: [6]}     # only if the player has an attack
```

**The sprite sheet** is a PNG with the frames one after another, left to right.
They are numbered from 0. **15 colours** maximum plus the transparent one per
image.

**Walking right and walking left are the same animation**: the engine draws it
**mirrored** according to which way you are facing, just as these machines do
in hardware. There is no need to draw the character twice (nor to pay twice the
tiles): draw it facing right and that is that.

**Animations**: `frames` is the list of frames and `velocidad` the game frames
each one lasts (higher = slower). Slots the engine understands: `quieto`,
`correr`, `saltar`, `caer`, `dano`, `atacar`, `subir`, `agachado`, `arriba`,
`abajo`, `remate`, `patada`, `nadar` and `bucear`. If any is missing, the
nearest one is used (`caer` falls back to `saltar`, `nadar` and `bucear` fall
back to `saltar` and `caer`, and everything else to `quieto`). `subir` is the
stairs' one and `dano` the one for taking a hit.

With **`bucle: no`** the animation stops on the last frame instead of starting
again. It is what is needed on `atacar` when the attack has `preparacion`: the
first frame is the arm coming out and the second the hit, and without
`bucle: no` it would go back to the first halfway through the whip crack.

```yaml
    atacar: {frames: [6, 7], velocidad: 5, bucle: no}
```

**The collision box** is centred horizontally in the frame and rests on its
bottom edge. Make it a little narrower than the graphic: it plays better.

### `salto_fijo`: the jump that cannot be steered

The normal thing is the usual jump: it is corrected in mid-air with
`control_aire:` and releasing the button shortens it with `corte_salto:`. With
**`salto_fijo: si`** that disappears:

- on take-off you decide **where you are going and with how much push** —
  whatever you were pressing on that frame— and until you land it cannot be
  changed;
- releasing the button does **not** shorten the jump: the arc is always the
  same;
- and if you hit a wall sideways, you lose your push for the rest of the jump.

It is the classic adventures' jump. It sounds awkward and it is exactly what
makes each jump a decision and not a formality: to climb a step you have to
take off **before** reaching it, not pressed against the wall.

### `desgaste`: health that drains by itself

With `desgaste: N` the player **loses one health point every N frames**,
whatever they are doing. It is what turns a game into a countdown, and it is
the dungeon genre's engine: if you do not eat, you die on your own.

```yaml
jugador:
  vida: 200            # here health is not three hits: it is 200 points
  desgaste: 12         # one every 12 frames, that is 200 points = 40 seconds
```

Details that matter:

- the drain **does not respect invulnerability**: the flashing after a hit
  saves you from the enemies, not from hunger;
- it stops with the game (on the title screen, while dying or with the level
  finished it does not go down);
- on reaching zero you die just as from a hit, with its animation and one life
  less.

The natural thing is to put it together with a high `vida:` (100, 200…) and
`efecto: salud` objects spread about the map. And with `desgaste:` set, the
scoreboard stops drawing squares and **writes the number** (`LIFE 184`), which
is what Gauntlet did: a hundred squares do not fit on any of these screens.

### The hit taken: `retroceso` and `aturdido`

On taking damage you are thrown backwards with force `retroceso` and left
`aturdido` frames **with no control**: you do not accelerate, you do not brake,
you do not jump and you do not attack. The shove takes you wherever it takes
you.

It is a whole genre's worth of difference. With `aturdido: 0` (the default) you
get the controls back immediately and a graze is a scratch; with `aturdido: 24`
and a high `retroceso`, a graze at the edge of a platform **throws you into the
void**, and the whip classics' level design lives off that. If you do not set
`retroceso`, your `velocidad` is used, which is how the kit used to behave.

While you are stunned the attack is cut off too: you cannot hit and take a hit
at the same moment.

### `ataque`

Without this section the player **can only stomp enemies** and the action
button does nothing. With it, they attack:

```yaml
jugador:
  ataque:
    tipo: disparo            # disparo or golpe
    sprite: graficos/bala.png
    frame: [16, 16]
    caja: [6, 6]
    desplazamiento: [5, 5]   # the box, centred in the frame
    velocidad: 3.5           # pixels per frame the shot flies
    alcance: 96              # px it covers before dying
    espera: 18               # frames between one attack and the next
    duracion: 8              # frames the pose lasts (and the hit)
    preparacion: 0           # of those, the frames in which it does no damage yet
    clavado: no              # if yes, while hitting you do not move
    dano: 1
    mejoras: 0               # how many times it can be upgraded (0 = never)
    alcance_mejora: 12       # px each upgrade adds
    animaciones:
      quieto: {frames: [0, 1, 2, 1], velocidad: 4}
```

| type | what it does |
|---|---|
| `disparo` | a projectile comes out and flies forwards until it hits a wall, hits an enemy or runs out of `alcance`. It needs a `sprite` |
| `golpe` | for `duracion` frames there is a box `alcance` pixels in front of the player that damages whatever it touches. With a `sprite` it is **visible** (the whip); without one, the hit is invisible |

The button goes **on the edge**: holding it down does not fire endlessly, and
the rate is set by `espera`. While the attack lasts —hitting or shooting— the
player uses the `atacar` animation if you have set one.

#### The weapon you can see

With `tipo: golpe`, **`sprite:` is the weapon**: the whip, the sword or
whatever. It is drawn against the player's side **only while the hit does
damage** —that is, past the `preparacion`— so what you see on screen is exactly
what hits. Facing left it comes out mirrored and still comes out of the handle.

```yaml
jugador:
  ataque:
    tipo: golpe
    sprite: graficos/latigo.png
    frame: [48, 16]          # the whole frame is the weapon
    caja: [48, 16]
    desplazamiento: [0, 0]   # no offset: it starts where the player ends
    alcance: 24
    mejoras: 2
    alcance_mejora: 12       # 24 -> 36 -> 48 px
    animaciones:
      quieto: {frames: [0, 1, 2]}   # one frame per weapon level
```

**Each frame is an upgrade level**: the engine shows 0 with the stock weapon, 1
with one upgrade and 2 with two. Draw each of them at the size of its reach
(here 24, 36 and 48 px) and the upgrade will be seen as well as felt. If the
sheet has fewer frames than levels, it stays on the last one.

The weapon is one more entity in the list while it is visible, so it takes one
of the 64 slots; if there is none left, the hit lands just the same but is not
drawn.

Without a `sprite:` the hit draws nothing, which is how the kit used to work:
the player changes to the `atacar` pose and that is that.

**`preparacion`** is the hit's first few frames in which the arm is still
coming out: it is visible, but it does no damage. It is what separates judging
the distance from mashing the button. It has to be less than `duracion` (if not
the hit would never touch, and `ngplat` does not compile).

**`clavado: si`** plants you on the spot while the hit lasts: on the ground you
neither walk nor turn. **Not in mid-air**: if you jump and hit, you keep your
momentum, which is how the classics play.

The projectiles live in the same list as the enemies and the objects, so 64
things fit on screen at once counting them; if there is no slot left, the shot
is lost. One that leaves the screen dies by itself.

`ngplat nuevo` already leaves you an example attack set up, with its `bala.png`
and its sound (`sonido: efectos: disparo:`).

#### Upgrading the weapon

With **`mejoras:`** the weapon can be lengthened during the game, which is the
classics' whip: each object with `efecto: mejora` (see [`objetos`](#objetos))
raises it a level and each level adds `alcance_mejora` pixels of reach, up to
the limit `mejoras` sets.

```yaml
jugador:
  ataque:
    tipo: golpe
    alcance: 24              # stock
    mejoras: 2               # two upgrades: 24 -> 36 -> 48 px
    alcance_mejora: 12
```

It works the same with `tipo: disparo`, and then what grows is how far the
projectile flies before dying.

The upgrades are **lost on death** and on starting a new level: you always
reappear with the stock weapon. It is what makes a life worth something. With
`mejoras: 0` (the default) the object does nothing and the weapon is always the
same.

### `combo`: the chain of hits

A brawler is not about pressing the button, it is about chaining. With
`combo: N` the melee attack becomes a series of N hits: pressing again before
`ventana:` runs out chains the next one, and the **last is the one that knocks
down**.

```yaml
  ataque:
    tipo: golpe
    alcance: 14
    espera: 12           # frames between one hit and the next
    dano: 1              # what the middle ones do
    combo: 3             # punch, punch and finisher
    ventana: 26          # frames to chain the next one
    dano_remate: 3       # what the last one does
    derribo: 45          # frames whoever takes it stays on the floor
    empujon_remate: 3.0  # how hard they are thrown back
```

Whoever takes the finisher **is knocked down**: they are thrown back the way
you are facing and stay `derribo:` frames on the floor, and while they are
there they **neither decide anything nor do you any harm**. That is what makes
chaining worth something: a few frames without them on top of you.

The rate rules over the window: if `espera:` is greater than `ventana:`, there
is never time to chain and the series does not exist. With `combo: 1` —the
normal thing outside this genre— there is no series and the four numbers below
do nothing.

So that the finisher looks different there is an animation slot of its own,
`remate:`. Whoever does not bring one keeps `atacar`'s.

### The other three hits (only in `vista: cinta`)

They are not configured: they come out of the controller and where you are, and
all three count as a finisher —they do `dano_remate:` and they **knock
down**—. They are what the genre was missing for a fight against three to be
winnable:

| how | what comes out | what it costs |
|---|---|---|
| attack **with somebody behind** and nobody in front | **elbow**: you turn round by yourself | nothing, but only when it is really needed |
| attack **in mid-air** | **jump kick** | in mid-air you cannot steer |
| attack **while running** (two taps in the same direction) | **shoulder charge** | it spends the run: one per sprint |

The jump kick stretches its box **down to the ground**: otherwise the graphic
goes up and the box with it, and the kick would hit nobody.

And on landing one, the world **stops** for four frames (nine on the finisher)
and on knocking somebody down the screen **shakes**. It is not configurable and
cannot be removed: without that pause the fist goes through the other person
and nothing is felt. The controller is **not sampled** during the pause, so
whatever is pressed inside it still counts: chaining is a rhythm, not a
reflexes test.

### `patada`: the flying kick

```yaml
jugador:
  ataque:
    tipo: golpe
    alcance: 14
    dano: 1
    patada: 26        # the mid-air hit's reach; 0 = the usual one
    dano_patada: 2    # and its damage; 0 = the usual one
```

In any side-on view, `patada:` makes **hitting without touching the ground a
different hit**: its own reach, its own damage and its own graphic (the
`patada:` animation, which takes a slot separate from `atacar:`).

It is what turns the jump into an attack rather than a way of moving, and it is
where the kung-fu genre's name comes from. Without the line, in mid-air the
same short standing punch comes out.

If you set it, draw the frame **stretched**: a hit that reaches twice as far
has to look twice as long, or the player does not understand why that one
landed and the other did not. That is why the kung-fu genre uses 32×32 frames
instead of 16×16.

### `agarre`: grabbing, shaking and throwing

What makes a brawler a brawler and not a corridor of punches. Whoever is
**reeling** from a hit (that is, whoever you have just touched) can be grabbed
by touching them, and there it is decided:

```yaml
jugador:
  agarre:
    tiempo: 100          # frames they stay grabbed before breaking free
    rodillazo: 1         # each knee's damage (action button)
    lanzamiento: 3       # how much hitting the ground hurts (jump button)
    fuerza: 4.0          # how fast they are thrown
```

- **Action**: a knee. It does damage and re-hooks the grab, so it can be
  chained.
- **Jump**: you throw them over your shoulder. They fly off —with their height
  and their arc, the jump's same third coordinate—, they crash on landing and
  they land knocked down.
- It releases by itself when `tiempo:` runs out, if you are hit, or if they die
  in your hands.

Without the `agarre:` block the game has no grabbing and touching an enemy
costs you a hit, as in any other genre. And in `vista: cinta` there is one more
rule that is not configurable: **whoever hits you steps aside**, so that three
at once do not kill you in two seconds.

### `secundaria` / `secundarias` (the weapons that spend ammo)

```yaml
jugador:
  secundaria:
    tipo: recta              # recta | arco
    sprite: graficos/cuchillo.png
    frame: [16, 16]
    caja: [10, 4]
    desplazamiento: [3, 6]
    velocidad: 4.0
    gravedad: 0.25           # only counts in arco
    salto: 3.0               # upward push on leaving, only in arco
    alcance: 200
    espera: 24
    coste: 1                 # ammo each throw spends
    dano: 1
```

It is thrown with **up + action**, and it spends ammo. The plain button still
does the usual attack, and if you have no ammo left, up + action hits too: you
are never left with nothing to do.

| type | what it does |
|---|---|
| `recta` | it flies forwards, like the normal attack's shot |
| `arco` | it comes out upwards with `salto` and the `gravedad` brings it down: it falls in a parabola and dies on touching the ground |

The ammo comes from objects with `efecto: municion` (and the breakables drop
it). **Careful with the name**: plain `efecto: corazon` means *health*, which
is something else; ammo is `municion`, `municiones` or `hearts`.

The ammo is emptied at the start of each level, just like the keys, and the
scoreboard shows it as `AMMO 05` as long as the game carries a secondary
weapon. With **several** weapons, in `AMMO`'s place goes the short name of the
one you are carrying (`HACHA 05`): see below.

**`a_la_vez`** limits how many can be flying at once. Without setting it, as
many as fit come out; with `1` you have to wait for the previous one to fall
—which is the classic— and with `3` you have the usual "triple".

#### Several weapons, and the object that changes them

Instead of one, a game can carry **several** with `secundarias:`, each with its
own name. You start with the first and you swap by picking up an object with
`efecto: subarma`, like the classics' axe:

```yaml
jugador:
  secundarias:
    cuchillo:
      tipo: recta
      sprite: graficos/cuchillo.png
      coste: 1
      a_la_vez: 3
      marcador: DAGA         # how it appears in the scoreboard (5 letters)
    hacha:
      tipo: arco
      sprite: graficos/hacha.png
      impulso: 4.0
      coste: 2
      dano: 2
      a_la_vez: 1

objetos:
  hacha:
    sprite: graficos/hacha.png
    efecto: subarma
    arma: hacha              # which of 'secundarias:' it changes to
```

- The weapon you carry belongs to **the game**, not to each player: with two,
  whichever one picks up is carried by both, just like the ammo.
- On **starting a level** it goes back to the first.
- Whatever is already flying **keeps the weapon it came out with**: changing
  weapon does not turn the knife in mid-air into an axe.
- `secundaria:` (one) and `secundarias:` (several) are mutually exclusive:
  setting both is an error.

**The scoreboard says which one you are carrying.** With a single weapon it
says `AMMO 05` and there is nothing to tell apart; as soon as there are two,
`AMMO 05` does not say whether that is five knives or five axes, so in its
place comes the **short name** of the weapon you have on, and it changes when
you change:

```
KEYS 01/03 DAGA 05          <- you are carrying the knife
KEYS 01/03 HACHA 05         <- you pick up the axe and it changes
```

Without `marcador:` the weapon name's first five letters are taken
(`cuchillo` -> `CUCHI`), which is almost never what you want: that is what
`marcador:` is for. **Five letters** fit —it is what the keys and the ammo
count leave free on the line, which is twenty— and only the ones the
scoreboard's font knows how to write (A-Z, numbers and `- . : ! ? /`); any
longer, or with an ñ, and the compiler says so and generates nothing.

### Crouching

```yaml
jugador:
  agachado: si         # with down, on the ground
  caja_agachado: 11    # the box's height when crouched (default, three quarters)
```

With **`agachado: si`**, pressing down on the ground makes the player crouch:
they **neither walk nor jump**, but they **do hit**, and the hit comes out at
knee height. What comes down is their box's **ceiling** —their feet stay where
they are— so whatever passes over stops touching them. That is what makes
crouching good for more than the pose: dodging what flies at head height and
reaching what goes along the ground.

- On a **pass-through platform**, down still means getting off: nobody crouches
  there.
- On a **staircase** neither: the staircase rules.
- On taking a hit, on dying and on reappearing they stand up.
- The pose is the `agachado` animation. Draw it **lower inside the frame**, by
  as much as the box comes down: the engine does not move the graphic, only the
  box.

Without `agachado:` (the default) the down button does the usual and nothing
else: getting off platforms and staircases.

### Stairs

```yaml
tiles:
  leyenda:
    '/': {tile: 6, tipo: escalera}             # goes up to the right
    '|': {tile: 7, tipo: escalera_izquierda}   # goes up to the left

jugador:
  velocidad_escalera: 0.8    # 0 = the game has no stairs
```

A staircase is a **second movement mode**, not one more tile: while you are on
it there is no gravity, no jumps and no collisions with the stage. You move
diagonally with up and down, and you cannot walk sideways.

They are drawn diagonally, one step per cell:

```
      ......####      upper floor
      ...../....
      ..../.....
      .../......
      ##########      lower floor
```

- **Getting on**: standing, by pressing up when you are on the step's cell; or
  by pressing down when the first step is diagonally just below (which is how
  you come down from the upper floor).
- **Getting off**: it happens by itself at both ends. On coming off, the player
  is left **standing on the row where it ends**, so the top step has to reach
  the upper floor and the bottom one the lower floor; if the staircase ends in
  mid-air, you fall.
- From the staircase you **can attack** (in the classics too), but not jump.
- **A hit knocks you off the staircase**: the shove carries you and you lose
  control just as on the ground.
- The stairs **stop nobody**: you walk straight past them, as past scenery.
  They only count when you decide to get on.

Without `velocidad_escalera` you climb at half walking speed. With `0` the game
has no stairs and the tiles stay as decoration.

### Vines

```yaml
tiles:
  leyenda:
    '|': {tile: 5, tipo: liana}     # also: verja, cuerda, cadena, enredadera

jugador:
  trepa: 1.1      # 0 = the vine cells do nothing
```

A vine **is not a staircase**, and the difference is half the mechanics:

|                     | staircase                      | vine                      |
|---------------------|--------------------------------|---------------------------|
| how you get on      | standing, on the cell          | **in mid-air too**        |
| which way it goes   | diagonally, one step per cell  | straight, vertically      |
| how you get off     | by itself at the ends          | by jumping, with push     |
| from it you can     | attack                         | **jump** anywhere         |

You grab it by pressing up or down while touching it: on the ground or falling,
it does not matter. While you are hanging there is no gravity; up and down
climb and descend, and the engine stops you against the ceiling and against the
floor, so a vine against a floor is climbed to the edge and there it stops.

**You let go by jumping**, and the jump comes out with the usual push and
towards whatever you are asking for: that is what is good for moving from one
vine to the next or for landing on a beam. And **a hit knocks you off**, just
as from a staircase: that is why climbing in front of a creature is a decision
and not a formality.

**On reaching the very top you come off standing on the tip**, and the tip can
be stood on: you stay there, at the height of that cell's edge, and from there
you walk sideways. That is what makes the kung-fu genre's bamboo work —it goes
against a beam and at the same height: you climb, you come off at the top and
you walk onto the beam—.

The tip is only the tip: the cell **above** has to be air. A vine that **hangs**
from a beam has the beam there, and then there is no tip to stand on —there is
a ceiling— so that rope does not block the way underneath. And the rest of the
vine is always passed through: both climbing and sliding down it.

Without `trepa:` —or with `trepa: 0`— the game has no vines and those tiles
stay as decoration.

### Water: swimming and diving

```yaml
tiles:
  leyenda:
    '~': {tile: 9, tipo: agua}      # the surface, with its crest of foam
    'w': {tile: 10, tipo: agua}     # the bottom

jugador:
  brazada: 2.0          # 0 = the water cells do nothing
  aire: 240             # frames diving before starting to drown (0 = never)
  ahogo: 45             # frames between one health point and the next with no air
  animaciones:
    nadar:  {frames: [11, 12], velocidad: 8}
    bucear: {frames: [13, 14], velocidad: 6}
```

The water **does not stop you and does not kill you**: it changes how you move
while you are in it. A water cell is passed through on all four sides just like
air, and what it does is this:

- you fall far more slowly (`gravedad_agua`) and with a sinking limit
  (`hundimiento`), so you do not go to the bottom all at once;
- sideways you move less (`velocidad_agua`): the water grips;
- **up rises** (`subida_agua`), for as long as you hold it and at swimming
  speed: in the water you move the same in all four directions;
- the jump button stops being a jump and becomes **a stroke** (`brazada`),
  which pushes upwards all at once and can be repeated as often as you like.

Both ways up are needed and they are not the same. **Up** is going upwards the
way you go sideways: unhurried, without aiming and without letting go, and it
is the first thing anybody who falls in a pond tries. **The stroke** is a push
that is spent, and with your head out it is worth `salto_agua`: it is the one
that lifts you onto the bank in one go. Like a jump, it is cut when you release
the button, so to get out of the water you have to **hold it**.

**There are two states and the head decides**, not the feet. The engine looks
at two points: the centre of the box tells it whether you are in the water, and
the topmost pixel whether you have gone under. The two postures come out of
that:

| where you are | posture | what happens |
|---|---|---|
| the centre in the water and the head out | `nadar` | you breathe, and the stroke **takes you out of the water** (`salto_agua`) |
| the whole body under | `bucear` | the air is spent |

Swimming at the surface the engine **holds you afloat**: touching nothing you
rise no further. Without that, the six-pixel band in which the head shows is
crossed in two frames and the swimming posture would never be seen.

Floating is what happens **when you are not steering**: if you hold up, you
rise; and the stroke that takes you out is not cut by the floating, it lasts
until the push is spent. Until 1.52 it was cut, and that is why you could not
get out of the water: the push was worth one frame and the next it was zero.

**The air** only goes down while diving, and it refills entirely as soon as you
get your head out: there is nothing to manage, you have to come up. When it
reaches zero one health point is lost at that very moment and another every
`ahogo` frames exactly. Drowning **skips invulnerability**: a creature having
grazed you half a second ago does not stop the countdown. With `aire: 0` nobody
drowns: the water is only a way of moving.

The rest is filled in from the land figures, so putting water in a game is
writing **one line**:

| if you do not set it | it is worth |
|---|---|
| `gravedad_agua` | a quarter of `gravedad` |
| `hundimiento` | a third of `max_caida` |
| `velocidad_agua` | two thirds of `velocidad` |
| `subida_agua` | the same as `velocidad_agua` |
| `salto_agua` | the same as `salto` |
| `ahogo` | 60 frames (one health point per second) |

Without `brazada:` —or with `brazada: 0`— the game has no water and those cells
stay as decoration. And they do not stay as decoration only on screen: the
compiler **deletes the whole of the water** from the executable, just as it
does with the crocodiles and the swinging vine.

**A pond is dug, not propped up.** The water's surface has to end up level with
the earth you walk on, or it will look like a block of water put on top of the
ground; and below the bottom there has to be a solid cell, because the water
does not hold you up and below the map you fall into the void. Two cells deep
is enough: with one your head does not fit under and you never get to dive.

### The water **comes ready** in the starter game

The game `ngplat nuevo` creates carries a pond in the first level, just past
the spikes: you fall in without meaning to, which is the best way of finding
out that you swim here. Everything above is already written in its `game.yaml`
and drawn in its PNGs.

It did not come free, and what it cost is measured:

| where | how much |
| --- | --- |
| Neo Geo, the water's code | 1934 cycles per frame out of 200000 |
| Neo Geo, the pond's map | 1930 cycles more |
| Where there is no water | **nothing**: see "what it costs to check whether you are wet" |
| Amiga, the executable | 3196 bytes: from 190628 to 193824 |

The Neo Geo's 3864 cycles did not fit: the level was already spending 198838 of
the 200000. The pond paid for them by taking two things out of their places:
**one mushroom** —the one at the water's edge, almost 4000 cycles— and **one
coin** —the one that was above it, 2000—. With that the most expensive frame
spends **196626** and the game runs at 60 pictures per second, checked on the
bench; and 3374 are left over for whatever you want to put in yourself.

On the Amiga it gets in by **736 bytes**: a 512 KB A500 leaves about 190 KB
free (194560) and the executable takes 193824. It is booted on an emulated
512 KB A500, not calculated.

#### What it costs to check whether you are wet

Each frame, the engine has to know whether the player is in the water, and that
is a lookup in the map: a 32-bit multiplication which on a 68000 is a library
call. It sounds like little and it is not, so the compiler puts two guards in
front of it, both worked out at compile time:

- **`hay_agua`**, one byte per level: if the map has not a single water cell,
  the probe never happens. A game with water usually has most of its levels
  dry, and those pay one comparison.
- **the rectangle that wraps the level's water**, in pixels: outside it there
  is no probing either. In the starter level the pond is eight cells out of
  forty-eight, so it is four integer comparisons for 85% of the journey.

The second is not decoration: without it, the **Atari ST** lost the vblank on
the first level's busiest screen —the one at the start— and the whole game
dropped below 50 pictures per second. It is heard in the music, which is
pinned to the frame: it went from 16 notes of 16 to 10. With the rectangle it
is back to 16 of 16, in and out of the water.

**The vine carries the same guard.** The pendulum's step walks the level's
whole creature list looking for vines, and the whole game paid for that whether
that level had vines or not: 4000 cycles per frame out of the Neo Geo's 200000.
Now each level carries its `hay_balanceo` and one with none does not enter the
loop. The difference is between not fitting and fitting: a vine in the starter
game's second level comes out at **198708** cycles instead of 200650.

What is still left out is **the crocodiles and the swinging vine**, but no
longer for the same reason, and it is worth saying because it was measured
again:

- **the vine now fits on the Neo Geo.** It cost 4000 cycles per frame —not
  6000— and it charged them on every level, vine or no vine; with
  `hay_balanceo` per level, a vine in the cave leaves the most expensive frame
  at **198708** of 200000 and the game at 60. What keeps it out is the
  **Amiga**: its sheet is 48×48 by five frames, 15 KB, and with it the
  executable goes from 190 KB to 205 and stops booting on a 512 KB A500. It is
  preferred that the starter game boots on the bare A500; if that does not
  matter to you, paste it in with the recipe above and raise `amiga_ram: 1M`,
  which is exactly what it is for.
- **the crocodiles** still cost 16000 cycles per frame, and there is no such
  room on any of the tight machines.

The engine carries both, the graphics come with the project and the recipe for
pasting them in is above; on an A1200, a CD32, a Mega Drive, an X68000 or a
Jaguar there is room to spare.

#### Taking the water out

If your game does not use it, take it out and get back the 3000 bytes and the
1934 cycles: all you have to do is **delete `brazada:`** from `jugador:`.
Without that line the compiler deletes the whole of the water from the
executable, and any `tipo: agua` cells left on the map become decoration. The
two postures and the two legend cells can be left or removed: nobody looks at
them any more.

#### The starter game's pond

This is how it is dug. **Two rows of sky** are taken off the top (they were
empty) and **two of earth** are put at the bottom, so the level is still
sixteen rows and the camera does not notice:

```
P.......s...V...k.^.....................c...G...
####################~~~~~~~~######..############
,,,,,,,,,,,,,,,,,,,,wwwwwwww,,,,,,..,,,,,,,,,,,,
,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,..,,,,,,,,,,,,
```

And three things move when it is dug:

- **the key** comes forward from column 22 to 16: in its usual place it would
  be left floating over the pond, and a key you have to fish for is a key
  somebody leaves behind;
- **the mushroom in column 28** disappears: it landed right at the water's edge
  —you came out dripping and ate it— and it is the one that paid almost 4000 of
  the cycles that were needed;
- **the coin in column 22** goes with it. Where it was —two rows above the
  water— it could not be reached: coming out of a stroke the hero rises to row
  11.75 and the coin is on row 11, so it was grazed and not collected, which is
  worse than not putting it there. And lowering it to the water's row, where it
  can be fished while swimming, costs 3982 cycles instead of 2000: there it
  falls inside the most expensive frame —the player swimming, the water and it
  all at once— and the level goes to 200690 out of 200000. Measured all three
  times.

The water's graphics —the hero's four poses (11 and 12 swimming, 13 and 14
diving) and the tileset's two cells— are drawn by the scaffold. If you make
your own, the editor has them (<kbd>E</kbd> → graphics); and if you want the
kit's for a project that already exists:

```python
from ngplat import art
from ngplat.png import write_png
write_png("graficos/heroe.png", art.heroe(agua=True))
write_png("graficos/tiles.png", art.tileset(agua=True))
```

`tests/test_niveles.py` plays that pond with the bot and counts the frames it
spends in the water: finishing the level does not say whether it was crossed by
swimming or by jumping over, and that is exactly what has to be checked.

### `entre_ellos`: letting the creatures hit each other

```yaml
juego:
  entre_ellos: si
```

An enemy's [`golpe:`](#golpe-the-enemys-attack) damages **another enemy** in
front of it. Only the hit counts: brushing against each other does nothing.

It is what turns two pursuers into a tool. Without this, two tough creatures
are two problems; with this, placing them so that they cross and getting
yourself out of the way is a real move, and it is the only one you have when
you cannot handle either of them.

### Checkpoints

```yaml
tiles:
  leyenda:
    '!': {tile: 8, tipo: control}
```

A checkpoint **does not get in the way**: you walk straight past it as past
scenery. What it does is note its cell when you touch it, and if you are killed
and you have lives left you reappear there instead of at the start of the
level. It is what makes long levels possible without dying being a punishment.

- you reappear **standing on the marked cell** and centred in its column, so
  the marker goes on the row where you want to land (usually the one above the
  floor), and it does not matter where you passed when you touched it;
- **the last one you pass counts**, even if it is an earlier one: if you go
  back for something and cross the previous one again, that becomes the good
  one;
- passing again over the one already marked **does nothing** (and makes no
  sound);
- the rest of the level **starts over** as always: the enemies, the objects and
  the candelabra come out again where they came out;
- changing level **clears it**: each level starts with no checkpoint.

In two-player games it belongs to the game, not to each player: whoever dies
goes back to the last one either of them touched.

With `sonido:`'s `evento: control` you put a sound on the moment of touching
it.

## `rompibles`

```yaml
rompibles:
  candelabro:
    sprite: graficos/candelabro.png
    caja: [8, 12]
    suelta: corazon        # the name of an object from 'objetos:'
    puntos: 100
    vida: 1                # hits it takes
    animaciones:
      quieto: {frames: [0, 1], velocidad: 8}
```

A breakable **does nothing** until you hit it: it does not touch you, it does
no damage and it cannot be stomped. On breaking it, it drops the `suelta:`
object right where it was —resting on the same ground— and gives its `puntos`.
Without `suelta:` it simply disappears.

It is the whip classics' loop: hit everything, see what falls. They are placed
on the map with their symbol, like the enemies:

```yaml
spawns:
  V: candelabro
```

Details worth knowing:

- It is broken by the normal attack (`golpe` or `disparo`) as well as by the
  secondary weapon.
- What it drops takes **the same slot** in the entity list that the breakable
  was taking, so it can never run out of room: an extra life inside a
  candelabrum is not lost because the screen is full.
- With `vida:` greater than one several attacks are needed, not several frames:
  what is already flashing is not touched again until it stops.
- If `suelta:` names something that is not in `objetos:`, `ngplat` does not
  compile.

## `tiles`

```yaml
tiles:
  imagen: graficos/tiles.png   # 16x16 tiles in a row, numbered from 0
  leyenda:
    '.': {tile: 0, tipo: vacio}
    '#': {tile: 1, tipo: solido}
    '=': {tile: 2, tipo: plataforma}
    '^': {tile: 3, tipo: peligro}
    'G': {tile: 4, tipo: meta}
    ',': {tile: 5, tipo: solido}
```

Types:

| type | effect |
|---|---|
| `vacio` | does not get in the way |
| `solido` | blocks on all four sides |
| `plataforma` | only stops you if you fall onto it; passed through by jumping from below and dropped off with ↓ |
| `peligro` | kills on contact (spikes, lava) |
| `meta` | finishes the level |
| `escalera` | a staircase going **up to the right** |
| `escalera_izquierda` | a staircase going **up to the left** |
| `control` | checkpoint: does not get in the way, but notes where you reappear (driving, it **hands out seconds**) |
| `cerrojo` | holds like a wall until you turn up with the object it asks for |
| `liana` | climbed vertically, and grabbed in mid-air too |
| `lento` | **does not stop you, it slows you**: a road's grass, a sand pit, a puddle |
| `agua` | you swim and dive: different gravity, different speed and the air counted |
| `decor` | drawn, does not get in the way |

Shortcuts: `'#': 3` is the same as `{tile: 3, tipo: solido}`, and
`'#': [3, plataforma]` works too.

If you do not set a `leyenda`, the default one is used (`.` empty, `#` solid,
`=` platform, `^` hazard, `G` goal).

### `cerrojo`: the door that asks for something

A lock is a cell that **cannot be passed** until you turn up with what it asks
for. On opening it the object is spent, it makes a sound, and the way stays
open **for good** (until the level restarts). It is the other half of an
adventure —the first is [carrying things](#objetos)— and what turns a small map
into a puzzle.

```yaml
tiles:
  leyenda:
    'D': {tile: 7, tipo: cerrojo, abre_con: llave}
    'F': {tile: 8, tipo: cerrojo, abre_con: cubo}
```

- `abre_con:` names an object from `objetos:` that has **`efecto: llevar`**. If
  it does not exist, or if it is not one of the carryable kind, `ngplat` does
  not compile: a door that asks for something that cannot be picked up never
  opens, and that is not a hard puzzle, it is a broken game.
- It is opened by **standing in front of it**, not by getting inside it
  (inside is not possible: it holds like a wall).
- A door of **several consecutive cells** —a column of two, a row of three— is
  **one** door: it opens whole and costs **a single object**. Two cells of the
  same type with a gap in between are two doors and cost two.
- Each level can carry up to twelve open cells at once.

## `enemigos`

```yaml
enemigos:
  seta:
    sprite: graficos/enemigo.png
    caja: [14, 12]
    comportamiento: patrulla
    velocidad: 0.4
    vida: 1              # hits it takes
    dano: 1              # health it takes off the player
    puntos: 100
    pisable: si
    girar_en_borde: si
    jefe: no             # si -> killing it finishes the level
    animaciones:
      quieto: {frames: [0, 1], velocidad: 14}
```

Behaviours:

| behaviour | what it does | its own options |
|---|---|---|
| `patrulla` | walks and turns round at walls and edges | `girar_en_borde` |
| `volador` | floats up and down, ignores gravity | `amplitud`, `periodo` |
| `perseguidor` | goes for the player if they are close, and **stops at the edge** of a hole instead of throwing itself in | `rango`, `girar_en_borde` |
| `saltarin` | jumps every so often | `salto`, `intervalo` |
| `fijo` | does not move | — |
| `trafico` | comes up the road in its own lane, minding its own business (only in `vista: carretera`) | `velocidad` |
| `cocodrilo` | opens and closes its mouth: closed it is ground, open it bites | `periodo`, `intervalo` |
| `balanceo` | a vine that swings and that you hang from | `largo`, `amplitud` |

The two that come next —the crocodile and the vine— **do not come set up in the
game `ngplat nuevo` creates**, and it is worth saying why: that game has to
boot and run at 50 pictures per second on a 512 KB Amiga 500, and there is no
room left there. It is measured:

- with the vine in, the executable goes from 66 KB to 82 and, with the 120 KB
  of BSS, the game asks for 202 KB of chip RAM when about 190 fit in an A500:
  the floppy boots, the system cannot load it and the desktop stays on screen.
  It is the graphic's fault —the vine draws the whole rope, 45 cells of
  graphics— and it was checked the other way round: the same floppy **does**
  boot if the machine is given a megabyte of chip RAM;
- with the crocodile in it boots, but the game drops to 25 pictures per second.

The graphics are created with the project (`graficos/cocodrilo.png` and
`graficos/liana.png`), so on a machine with room —an A1200, a CD32, a Mega
Drive, a Neo Geo— or in a smaller game all you have to do is paste in the block
and put the letter on the map.

### `cocodrilo`: Pitfall's pond

A crocodile is not killed: you catch its moment. It does not move from its spot
and the only thing it does is open and close its mouth, and **with its mouth
closed it is ground**: you step on its back and cross over. With its mouth
open, it bites.

```yaml
enemigos:
  cocodrilo:
    sprite: graficos/cocodrilo.png
    frame: [16, 16]
    caja: [16, 8]        # the back, which is what you step on
    comportamiento: cocodrilo
    periodo: 150         # the whole cycle, in frames
    intervalo: 50        # of those, the ones with its mouth open
    vida: 99             # it is not killed
    animaciones:
      quieto: {frames: [0, 1, 2]}   # closed, warning, open
```

`quieto`'s three frames are not an animation that runs by itself: the engine
sets them according to the mouth. The middle one is the **warning** —it half
opens and its teeth show twelve frames before biting— and without it this is
not a puzzle but a trap.

Placed several in a row they open **in a wave**: each one starts its cycle a
third later than its neighbour, and the offset comes from the map column it is
placed in, so it happens by itself. A pond of three is Pitfall's: it is crossed
at a walk, not at a run.

Put them **on the floor's row**, inside the hole, and not on the one above:
that way the back sits a hand's breadth below the edge and whoever walks along
the edge does not get bitten. On the row above they stick up over the edge and
bite whoever arrives at the hole without so much as a by-your-leave.

### `balanceo`: the vine that crosses to the other side

Pitfall's other half. A vine hangs from wherever you put it and swings by
itself from the first frame. It is caught **in mid-air and by a graze** —there
is no grab button: the vine is caught by jumping well— and the only thing you
decide is when to let go: with jump you come off with whatever the tip was
carrying, and with down you drop straight onto whatever is below.

```yaml
enemigos:
  liana:
    sprite: graficos/liana.png
    frame: [48, 48]           # the whole rope is drawn
    caja: [6, 16]
    desplazamiento: [24, 0]   # the pivot: it hangs from here
    comportamiento: balanceo
    largo: 32                 # the rope's length, in pixels
    amplitud: 45              # the degrees it leans each way
    vida: 99
    animaciones:
      quieto: {frames: [0, 1, 2, 3, 4]}   # the five angles
```

Two things that are not like the other enemies:

- **`amplitud` is degrees**, not pixels. On a flyer it is how far it goes up
  and down; here it is how far the swing leans. The default is 45 each way.
- **the picture is big on purpose**. What is drawn is the whole rope, and a
  32-pixel rope leaning 45 degrees goes 23 to one side: in a 16x16 picture only
  the knot at the top would fit. The `desplazamiento` says which point of the
  picture is the pivot it hangs from. And it costs: five angles of 48x48 is 45
  cells of graphics, more than the hero spends.

`quieto`'s frames are the angles, laid out from the most leaned to the left to
the most leaned to the right, with the middle one being the vine hanging
straight. The engine chooses which one according to where the pendulum is, so
**the order matters**: swapped round, the vine swings backwards. Five do the
trick; with more —seven, nine— the rope follows whoever is hanging better, and
they always go by the exact spot and not by the graphic's. What it costs is
graphics memory: each angle is twenty cells.

With that rope the tip covers about 45 pixels from side to side, so the hole
this vine crosses is three cells: exactly what the longest jump measures. That
is, it can be crossed by a **perfect** jump, and with the vine it is crossed
without gambling. For a wider hole you need a longer rope, and with it a bigger
picture.

And do not let go at the far end, which is what it looks like: there the tip is
standing still and you drop straight down, right over the hole. You let go
**halfway up the far side**, which is when what you have already covered and
what is left of your push add up.

**Careful with the name**: this vine is not the `tipo: liana` from the tile
legend. That one is a cell you **climb** —up and down, you are in charge— and
this one is an enemy you **hang from** and which carries you. You can have both
in the same game and they do not get in each other's way.

**`girar_en_borde`** works for the two that walk on the ground, and it does
different things on each: the patroller turns round and the chaser stops at the
edge and waits for you there (turning round would mean giving up the chase).
With `girar_en_borde: no` both throw themselves into the hole and are lost,
which is sometimes exactly what you want —creatures that come out and fall—
but **never** on a boss: if the boss falls, the level cannot be finished.

### `dispara`: enemies that shoot at you

Without this an enemy only does damage on touching you. With this it shoots at
you from a distance, which is what turns a screen into a commando game:

```yaml
enemigos:
  soldado:
    sprite: graficos/soldado.png
    comportamiento: patrulla
    dispara:
      sprite: graficos/tiro.png
      caja: [4, 4]
      desplazamiento: [6, 6]
      velocidad: 2.0       # pixels per frame
      alcance: 200         # px it covers before dying
      espera: 90           # frames between one shot and the next
      dano: 1
```

- It shoots when the player is **within its range** and it respects the
  `espera`, so the rate of fire is what decides whether a place is passable.
- In the **lateral** view it shoots straight ahead, towards you. In **cenital**
  it aims at you, rounding to the nearest of the eight directions: a soldier
  does not shoot into the air because you have stepped above it.
- The shot stops at walls and does not touch the other enemies: in the commando
  arcades the soldiers' shots cross each other.

**Bosses.** An enemy with `jefe: si` is the level's boss: raise its `vida` so
that it takes several stomps, the scoreboard shows a bar with what it has left
(`BOSS ######`) and **killing it finishes the level**, just like reaching the
goal. A level with a boss needs no `meta` tile.

```yaml
enemigos:
  jefazo:
    sprite: graficos/enemigo.png
    comportamiento: perseguidor
    vida: 5
    puntos: 1000
    jefe: si
```

### `tenaz`: the one that does not get left behind

```yaml
enemigos:
  yamo:
    comportamiento: perseguidor
    tenaz: si
```

Only games with `camara: pantallas` look at it. An enemy with `tenaz: si`
**does not live in a screen: it lives behind you**. On crossing to the next
screen it appears again at the edge you came in by —that is, coming from where
you were coming from— and gets on with it. If there are several, they come in
one after another.

It is not a drawing trick: it changes what a screen means. Without them, each
screen is a puzzle solved calmly and the creature next door stays next door;
with them, dawdling costs and retracing your steps means walking straight into
the one who was behind you.

Starting a level does not count as crossing a door: on reappearing after losing
a life, the tenacious ones come out where the map says, not right next to you.

### `golpe`: the enemy's attack

```yaml
enemigos:
  maton:
    comportamiento: perseguidor
    dano: 1
    golpe:
      alcance: 14         # px its arm reaches
      preparacion: 18     # the warning: how long you have to see it coming
      duracion: 6         # the frames in which the box does damage
      recuperar: 22       # standing there afterwards: **that** is your window
      espera: 46          # how long before it tries again
      dano: 1             # without this, the same `dano:` as above
```

Without this block an enemy does damage **on touching you**, which is the usual
thing in a platformer. With it, it stops being an obstacle and becomes an
opponent: in the
[belt view](#the-view-from-the-side-from-above-or-from-a-corner) **brushing
against it no longer costs you health** —what costs you is its hit— and the
enemy starts behaving like a fighter:

- it comes as close as its arm reaches and **stops there**;
- it waits for a free token (see
  [`agresivos:`](#agresivos-how-many-hit-at-once));
- it **telegraphs** `preparacion:` frames before throwing it;
- it hits for `duracion:` frames and is left wide open for `recuperar:` frames;
- and it **falls back** `espera:` frames before trying again.

The four timings are any fighting game's and all four are felt on the
controller. The warning is what makes the game fair: without it there is no way
to dodge. The recovery is what gives it rhythm: without it there is no gap to
answer in.

**Somebody who has already started throwing a punch is not stopped by an
ordinary punch**: you have to move aside in depth, jump over them or spend a
strong move on them (the chain's finisher, the jump kick or the shoulder
charge). It is what makes winding up a real threat; if any old fist cut it
short, hitting non-stop would be enough.

And on taking a hit, an enemy **reels** for a few frames: it decides nothing
and takes the shove. That gap is where the next hit goes in, that is, what
makes a chain a chain.

## `objetos`

```yaml
objetos:
  moneda:
    sprite: graficos/moneda.png
    caja: [10, 10]
    puntos: 10
    efecto: puntos       # puntos | vida | salud | llave | municion | mejora
                         # | subarma | bomba | llevar
    cantidad: 1
    animaciones:
      quieto: {frames: [0, 1, 2, 3], velocidad: 7}
```

**Keys.** An object with `efecto: llave` adds `cantidad` to the game's key
counter, and a level with `llaves: N` does not open the goal until N are
carried. The keys belong to **the game, not to each player**: with two,
whichever one picks up works for the other. They are emptied at the start of
each level, and the scoreboard shows `KEYS 01/03` while the level asks for any.
If a level asks for more keys than are placed on its map, `ngplat` does not
compile: it could not be finished.

**Weapon upgrades.** An object with `efecto: mejora` raises the player's weapon
by `cantidad` levels and lengthens it (see [`ataque`](#upgrading-the-weapon)).
It stops at the limit `mejoras:` sets, and if the attack takes none the object
does nothing. Unlike the keys, the weapon's level belongs to **each player**,
and it is lost on death.

**The bomb.** An object with `efecto: bomba` does `cantidad` damage to
**everything visible at that moment**: enemies, spawners and breakables that
are on screen. What is off screen does not find out, and that is the point: the
potion does not clear the level, it clears *the screen*, so it is worth
whatever the moment you pick it up is worth. It is the classic smart bomb.

```yaml
  rayo:
    sprite: graficos/pocima.png
    puntos: 300
    efecto: bomba
    cantidad: 4          # the damage it deals, not how many bombs it gives you
```

**Changing secondary weapon.** An object with `efecto: subarma` and
`arma: hacha` swaps the secondary weapon you are carrying for the one it names
(see [`secundarias`](#several-weapons-and-the-object-that-changes-them)). The
weapon has to exist in `secundarias:` or `ngplat` does not compile: otherwise
it would be picked up and nothing would happen.

**What you carry (`efecto: llevar`).** An object with `efecto: llevar` **is not
spent on touching it**: it goes into the **bag**, which has three slots. It is
half of a Dizzy-style adventure —the other half is the
[locks](#cerrojo-the-door-that-asks-for-something)— and with just one of them
in the game two more things change:

- the **action button** stops attacking and starts **dropping** the first thing
  in the bag, at your feet (with a few frames of grace so that you do not pick
  it up again where you have just left it);
- the **scoreboard** shows what you are carrying, by its `marcador:`.

```yaml
objetos:
  llave:
    sprite: graficos/llave.png
    caja: [10, 12]
    efecto: llevar
    marcador: LLAVE      # five letters; without this, the name's
```

If the bag is full, the object **stays where it was**: it is not lost, but you
do not take it either, and that is the decision that makes the game. The bag is
emptied at the start of each level.

## `generadores`

Gauntlet's nests: **they pour out creatures endlessly until you smash them**.
It is the rule that turns the game on its head, because while one is still
standing, killing what comes out achieves nothing.

```yaml
generadores:
  nido:
    sprite: graficos/nido.png
    frame: [16, 16]
    caja: [14, 14]
    genera: bicho        # which enemy it puts out; it has to exist in `enemigos:`
    cada: 100            # frames between one creature and the next (8 to 3600)
    tope: 3              # how many of its own can be out at once (1 to 32)
    vida: 3              # shots it takes
    puntos: 1000         # what destroying it scores
    animaciones:
      quieto: {frames: [0, 1, 2, 1], velocidad: 10}
```

They are placed on the map with their symbol in [`spawns`](#spawns), just like
an enemy:

```yaml
spawns:
  n: nido
```

How it behaves:

- **it counts `cada` frames and puts out a `genera`** on its own cell, with the
  health and behaviour that enemy has in `enemigos:`;
- **`tope` is its own count, not the level's**: when it already has `tope`
  creatures alive it goes quiet, and it puts out another as soon as you kill
  one. Two nests of the same type do not get in each other's way;
- **it does no damage on contact**: you hit it, it does not hit you. It is
  destroyed by shooting (or with a `bomba`), and on falling it scores `puntos`
  and the `romper` sound plays;
- if the entity list is full, that creature does not come out and that is that:
  the nest does not jam.

A spawner is an actor like the rest, so it is drawn, animated and moved by all
seven machines with nothing special.

**What they cost.** Each creature that comes out takes a slot in the entity
list (64 in all, counting shots and objects), so `tope: 3` on four nests is
twelve possible creatures and you are already tight. If you want a tide, lower
`cada`; if you want pressure, raise `tope`.

## `prisioneros`

The commando games' hostages. They are **freed by touching them**, not by
shooting them: they are the kit's only creatures that punish you for pulling
the trigger.

```yaml
prisioneros:
  prisionero:
    sprite: graficos/prisionero.png
    frame: [16, 16]
    caja: [10, 12]
    puntos: 500          # what rescuing him scores
    velocidad: 1.6       # how fast he runs once freed
    escape: 100          # frames running before he is out of sight
    animaciones:
      quieto: {frames: [0, 1], velocidad: 24}   # tied up
      correr: {frames: [2, 3], velocidad: 6}    # freed
```

They are placed on the map like anything else, with their symbol in
[`spawns`](#spawns):

```yaml
spawns:
  R: prisionero
```

How he behaves:

- **Tied up** he stays where you put him, with the `quieto` animation.
- **On touching him** he scores `puntos`, the `moneda` effect plays and he runs
  off with the `correr` animation for `escape` frames; after that he
  disappears.
- **If you shoot him while he is tied up** —with the weapon, with the secondary
  or with anything of the player's— he is lost: he disappears **scoring
  nothing** and the hit sounds. Once freed nothing happens to him any more:
  shots go through him.
- The enemies do nothing to him: it is up to you not to mow him down.

`escape` is only cosmetic, but it counts: at 0 he disappears on the spot, and
with a high number he stays running about the screen for a good while.

The prisoners are not exclusive to `vista: cenital`: side on they are also
freed by touching them, only they run off to one side instead of upwards. But
it is in the top-down view that they make sense: on a screen you climb by
shooting, deciding whether to fire or not is half the game.

## `plataformas`

```yaml
plataformas:
  tablon:
    sprite: graficos/plataforma.png
    frame: [32, 16]
    caja: [32, 6]        # only the top part: it is where you stand
    movimiento: horizontal   # horizontal | vertical
    velocidad: 0.6           # pixels per frame
    distancia: 48            # travel from where it starts, in pixels
```

A moving platform goes back and forth between where the map puts it and
`distancia` pixels further on (to the right if `movimiento: horizontal`,
downwards if `vertical`), and **whoever stands on it goes with it**. It does no
damage, it cannot be killed and it does not count as an enemy: it is scenery
that moves.

It supports you like a `plataforma` tile: you only land on it **falling and
from above**, from below you pass through, and pressing down drops you off.
They are placed on the map with their symbol, just like the enemies and the
objects:

```yaml
spawns:
  T: tablon
```

The collision box is usually only the top band of the graphic (`caja: [32, 6]`
in a 32×16 frame): that way the player plants himself on the board and not
floating above the gap.

## `carretera`

The seven colours the roadway is painted with. Only `vista: carretera` looks at
it, and **the whole thing is optional**: without it you get a grey road with a
red and white shoulder on grass, the usual arcade one.

```yaml
carretera:
  asfalto: ["#4a4a52", "#282830"]   # the roadway's two shades
  arcen:   ["#d0d0d8", "#c02020"]   # the striped edge
  hierba:  ["#3a7a42", "#2c5434"]   # what is outside
  raya:    "#e8e8f0"                # the centre line
  ancho_arcen: 8                    # the shoulder's width each side, in pixels
```

**They go in pairs, and that is the genre's whole technique.** The road is
painted in **bands**: two shades that alternate every two segments and run
towards you as you advance. That is what makes the speed felt —there is no
drawing to move, there are two colours taking turns— and it is how it was done
in the arcades.

**They run every four pixels covered**, not every cell. Until 1.53 the count
went in 16-pixel cells and at everyday speeds the palette only turned one step
**every five or ten frames**: the road jerked instead of running. Counted in
pixels it turns on nearly every frame and the movement looks continuous,
without costing one cycle more: it is the same division, with a different
number.

They are **seven colours and not a drawing** on purpose. That way the roadway
is painted with whatever each machine gives —the Mega Drive's and the X68000's
per-line scroll, the Amiga's copper, shrunken sprites on the Neo Geo— without
spending a single tile, and the same screen comes out on all eight.

With **one single colour** instead of a pair, that band looks flat:
`asfalto: "#303038"` is a roadway with no stripes.

> **Separate the two shades properly, not by a hint.** The kit's
> shortest-on-colour machine —the Mega Drive and the Atari ST— stores **three
> bits per channel**, that is eight levels, and two greys eight points apart
> land on the same one. Then the palette rotates just the same, but it rotates
> four identical colours, and the road looks flat: it looks as if the car is
> standing still. Each pair goes a whole step apart (255/7 = 36 points). If you
> go over, `ngplat comprobar` warns with the band's name and the machine's.

## `coche`

The driving game's figures: the engine, the brake and the steering. **The whole
thing is optional** too: without it you get a car that runs, brakes and turns
like an eighties arcade one.

```yaml
coche:
  punta: 6.0            # how fast it goes in high gear
  punta_corta: 3.2      # and in low
  acelera: 0.030        # what it gains per frame in high
  acelera_corta: 0.075  # and in low, which pushes harder
  frena: 0.140          # what it loses per frame on the brake
  roce: 0.020           # and what it loses on its own, touching nothing
  volante: 2.2          # what it moves sideways, at top speed
  respuesta: 0.55       # how much the steering turns per frame (default, volante/4)
  lento: 1.6            # how fast it goes at most off the asphalt
  arrastre: 0.180       # what the bad ground steals per frame
  trompo: 90            # frames spinning after a crash
  control: 20           # seconds crossing a checkpoint hands out
```

| key | default | from | to |
|---|---|---|---|
| `punta` | 6.0 | 0.5 | 12.0 |
| `punta_corta` | 3.2 | 0.3 | 12.0 |
| `acelera` | 0.030 | 0.002 | 2.0 |
| `acelera_corta` | 0.075 | 0.002 | 2.0 |
| `frena` | 0.140 | 0.005 | 4.0 |
| `roce` | 0.020 | 0.0 | 2.0 |
| `volante` | 2.2 | 0.1 | 8.0 |
| `respuesta` | `volante / 4` | 0.0 | 8.0 |
| `lento` | 1.6 | 0.1 | 8.0 |
| `arrastre` | 0.180 | 0.005 | 4.0 |
| `trompo` | 90 | 0 | 255 |
| `control` | 20 | 0 | 999 |

The speeds go in **pixels per frame**, like any other actor's in the kit, so
they can be compared at a glance: a car at 6.0 runs four times as fast as a
hero at 1.5.

The limits are not for fun. A top speed of 20 pixels per frame skips two whole
cells between frames, and the car **would go through the fences** without
noticing.

**`volante` is the figure that decides the game.** It is what the car moves
sideways at top speed, and out of it comes which corners can be taken flat out
and which cannot. Raise it and the course becomes easy; lower it and there are
corners that force you to lift off, which is where the fun is.

**`respuesta` is the steering's feel**: how much the steering turns per frame,
that is, how long it takes to reach full lock and to come back straight. By
default it is a quarter of `volante`, which is four frames from straight to
full lock and another four back —less than a tenth of a second, but it is what
separates a car from a switch: until 1.53 the steering went from straight to
full lock **in one frame** and the car felt wooden—. Raise it and the car is
twitchy, almost a switch; lower it and it has weight, and you have to start
turning before the corner.

**What `respuesta` does not change is the line you take.** What the steering
stores is *how far it is turned*, not the pixels it moves; the pixels come out
of multiplying how far it is turned by the speed, so the sum above
—`volante / punta` per row, the same at 6.0 as at 1.0— still comes out the same
**on every frame of the turn**, not only at the end. It is defended by
`tests/test_carretera.py`, which is where the warning came from the first time
this was counted in pixels.

**`lento` and `arrastre` are the penalty for going off**: `arrastre` is what
the bad ground steals per frame and `lento` the ceiling it leaves you at. Going
off does not kill —that would be another game— but it costs seconds, and
seconds are the only currency there is.

**`trompo`** is the frames spinning after hitting something `solido`. With
`trompo: 0` crashing only stops you.

**`control`** is the seconds crossing a `tipo: control` cell gives. It is the
genre's currency: here you do not gain by killing or collecting, you gain by
**arriving**, and the prize is carrying on playing. With `tiempo: 0` in
`juego:` there is no clock and this does nothing.

## `fondos` (parallax)

Background layers with scroll of their own. They are written from **furthest to
nearest** and they are only decoration: they collide with nothing.

```yaml
fondos:
  - nombre: cielo
    imagen: graficos/cielo.png   # width and height multiples of 16
    velocidad: 0.2               # fraction of the scroll: 0 = still, 1 = like the ground
    y: 0                         # where it starts on screen, in pixels
    repetir: si                  # repeats horizontally (default yes)
    velocidad_y: 0               # optional, vertical scroll
```

Each layer carries its own 15-colour palette, and repeated tiles (a gradient
sky repeats a great deal) are stored only once in the ROM.

By default every level uses every layer. A level can choose its own:

```yaml
niveles:
  - nombre: "CUEVA"
    fondos: [cielo]      # the far layer only
    mapa: |
      ...
```

Limits: a layer cannot be more than 14 tiles tall (224 px) and each layer
spends 21 of the console's 381 sprites, so with two or three layers you have
plenty to spare.

## `sonido`

The Neo Geo's chip (the YM2610) has three square-wave channels: **two for
the music and one for the effects**. Everything is written with notes, in
Spanish (`do re mi fa sol la si`) or in English (`c d e f g a b`), with `#` or
`b` for accidentals, the octave number after, and `-` for rests. `|` separates
bars and makes no sound.

```yaml
sonido:
  efectos:
    empezar: {notas: "do5 sol5", velocidad: 4}
    salto:   {tipo: barrido, desde: 320, hasta: 900, duracion: 6}
    moneda:  {notas: "mi6 sol6", velocidad: 3}
    golpe:   {tipo: ruido, duracion: 10}
  musica:
    bosque:
      velocidad: 8        # frames each note lasts (higher = slower)
      volumen: 11         # 0 to 15
      bucle: si
      timbres: [flauta, bajo]   # what each track sounds like (FM machines only)
      pistas:
        - "do4 mi4 sol4 mi4 | fa4 la4 do5 la4"    # channel A: melody
        - "do3 -   do3 -    | fa3 -   fa3 -"      # channel B: accompaniment
```

`timbres:` says **what** each track sounds like, not what it plays. The three
machines with an FM chip look at it (Mega Drive, Neo Geo and X68000); the rest
play the same notes with the wave they have. The eight there are —`cuadrada`
(the usual one, and the one you get if you say nothing), `organo`, `flauta`,
`bajo`, `metal`, `campana`, `cuerda` and `pizzicato`— are covered one by one in
[sonido.md](sonido.md#what-it-sounds-like-timbres).

### What the scoreboard shows

It comes up by itself, with nothing to configure, and each piece appears only
if the game uses it:

| piece | when it appears |
|---|---|
| `SCORE`, `LIVES` | always |
| `TIME` | with `tiempo:` other than 0 |
| `KEYS 01/03` | on levels with `llaves:` |
| `AMMO 05` | with a `secundaria:` weapon (with several, the name of the one you carry: `HACHA 05`) |
| `BOSS ####` | with a boss on screen |
| `LIFE ###.` | with `vida:` greater than 1 |
| `LIFE 184` | with `desgaste:` set: there health is a three-figure number |

The health bar carries one square per hit: the full ones (`#`) are the ones you
have left and the dots (`.`) the ones you have lost, so you see at once how
much you can take and how much you could take when whole. In two-player games
there is one each (`1P ###` and `2P ###`), and at most nine squares appear:
with more `vida:` nine are drawn and that is that. With `desgaste:` there are
no squares worth having —two hundred do not fit on any of these screens— and
the number appears. Outside the game it switches off: on the Amiga, the Jaguar
and the Atari ST the scoreboard is a band of three rows and that third row is
the one the title and the *game over* use.

**Moments you can put sound on** (the game produces them by itself):
`empezar`, `salto`, `doble_salto`, `moneda`, `pisar`, `golpe`, `muerte`,
`meta`, `vida`, `disparo`, `romper` (a breakable) and `control` (touching a
checkpoint).

**Effect types**:

| type | what it is for | options |
|---|---|---|
| `notas` | short melodies (coin, goal) | `notas`, `velocidad`, `volumen` |
| `barrido` | jumps and shots: the frequency goes up or down | `desde`, `hasta`, `duracion` |
| `ruido` | hits and explosions | `duracion`, `tono` |

### Digital samples (`muestra:`)

An effect can be **recorded sound** instead of notes: a voice, a drum, a real
hit. It points at a WAV in the project:

```yaml
sonido:
  efectos:
    moneda:  {muestra: sonidos/moneda.wav, notas: "mi6 sol6", velocidad: 3}
    golpe:   {muestra: sonidos/golpe.wav, tipo: ruido, duracion: 10}
```

The WAV has to be **uncompressed PCM**, mono or stereo, 8 or 16 bits, at any
rate, and last at most 4 seconds; the compiler turns it into 8-bit mono and
resamples it to whatever each machine uses. `ngplat nuevo` already leaves you
two examples in `sonidos/`.

`muestra:` **does not replace `tipo:`**: you can set both, and then the notes
are the fallback for the machine that cannot play recorded sound, which is only
one:

| | |
|---|---|
| Amiga | yes: it is what Paula does as standard, reading the sound from chip RAM over DMA |
| Atari Jaguar | yes: the DSP reads them from the cartridge, byte by byte, and mixes them with the square waves |
| Mega Drive | yes: the DAC is in the YM2612 and the Z80 feeds it, with a driver the compiler also generates |
| Neo Geo | yes: the YM2610's ADPCM-A channels, which read from the V1 ROM on their own |
| Atari ST | **never**: the YM2149 only makes square waves |

On the Atari ST the notes sound, and if an effect is sample-only the compiler
warns you that it will be mute there.

The music is always notes: the samples are for the effects.

Each level chooses its music:

```yaml
niveles:
  - nombre: "BOSQUE"
    musica: bosque
```

### The title's and the boss's

Two songs belong to no level, and they are named inside `sonido:`:

```yaml
sonido:
  musica:
    bosque: {...}
    presentacion: {...}
    acoso: {...}
  titulo: presentacion   # plays while it waits for you to press Start
  jefe: acoso            # takes over from the level's while the boss is alive
```

- **`titulo`**: without setting it, the title screen stays silent, which is how
  the kit used to be.
- **`jefe`**: as soon as an enemy with `jefe: si` appears the music changes to
  this one, and on killing it the level's comes back. Without setting it, the
  level's usual one keeps playing.
- Outside the game —the "game over" and the end of a level— neither sounds:
  there, what sounds is the effect.
- The name has to be that of a music that exists; writing it wrongly is a
  compiler error and not a mysterious silence.

Who decides which one sounds is the engine (`np_music_now`), so all seven
machines and the preview do exactly the same thing.

Durations: `do4:2` lasts twice as long. Limits: 46 effects, 14 musics, 2 tracks
per music (the third channel is reserved for the effects) and notes between
roughly `do1` and `do8`.

## `variables` and `guiones`

Up to here the `game.yaml` describes **a world**: how you jump, what is on the
map and what hits. What it does not say is that **something happens**: that
stepping on a cell opens a door, that a sign warns you, that the second time
you pass, things have changed. That is the scripts, and their memory is the
variables.

### `variables`: the game's memory

```yaml
variables:
  puerta_abierta: 0
  monedas: 0
  visitas: 0
```

A number with a name and its starting value. They go from 0 to 65535 and
**32** fit.

They belong to the **game**, not to the level: changing level or losing a life
does not sweep them away. They only go back to their starting value on starting
a new game. It is what lets the game remember what you did two levels back,
which is what having memory is about.

### `guiones`: what happens

```yaml
guiones:
  cartel:
    - decir: "CUIDADO CON EL FOSO QUE HAY MAS ADELANTE."
  la_puerta:
    - si: {llave_de_oro: 1}
      pasos:
        - decir: "LA LLAVE ENCAJA."
        - poner: {puerta_abierta: 1}
        - sonido: control
      si_no:
        - decir: "ESTA CERRADA. FALTA LA LLAVE."
```

A script is a **list of steps**. They are not blocks you drag around:
NeoPlat's project is text on purpose —it reads, it compares, it goes into git
and the editor rewrites it without touching your comments— and a script is too.

The steps there are:

| step | what it does |
|---|---|
| `decir: "TEXT"` | text box; the game stops until you press |
| `esperar: 30` | waits those frames (60 = one second) |
| `poner: {var: 5}` | the variable becomes that |
| `sumar: {var: 1}` | adds that to it (it can be negative) |
| `si: {var: 1}` + `pasos:` + `si_no:` | looks at a variable and picks a branch |
| `sonido: moneda` | fires one of the effects from `sonido: efectos:` |
| `dar: llave` | gives you an object, as if you had picked it up |
| `ir_a_nivel: 2` | changes level |
| `llevar: [12, 5]` | puts the player on that cell (a graphic adventure's door) |
| `quitar: [12, 9]` | erases that cell from the map: it stops being drawn and stops answering |
| `acabar: si` | finishes the level, as if you had stepped on the goal |

**The steps that do not wait all run in the same frame.** Setting three
variables and giving an object does not cost four frames: it costs one. Only
`decir:` —until you press— and `esperar:` stop. If each step lasted a frame,
opening a door and announcing it would take a quarter of a second on things the
player does not even see.

**While a script is running the game does not**: not the player, not the
creatures, not the clock. It is the same thing the hit pause does on landing a
punch, and for the same reason: what stops the game has to stop it properly or
it is no use at all. A text box while you are being killed from behind is not a
text box, it is decoration.

In `si:` you can compare with something other than equality, by putting it in
quotes:

```yaml
    - si: {monedas: ">= 10"}
      pasos:
        - decir: "YA PUEDES PAGAR EL PEAJE."
```

`=`, `!=`, `<`, `<=`, `>` and `>=` all work.

The last three steps belong to the pointer view, although they work in any of
them. `quitar:` is the other half of picking something up —the first is
`dar:`—: the cell stops being drawn (what its `debajo:` says is seen) and stops
answering the verbs, and it is back on starting the level again. Twelve removed
cells fit per level, the same as open locks. `acabar:` is the only way of
finishing a level where there is no goal to step on, and with the last level it
finishes the game.

### How a script is launched

In three ways:

**By stepping on a cell** —a trigger— by giving it to a symbol in the legend:

```yaml
tiles:
  leyenda:
    'C': {tile: 12, tipo: vacio, guion: cartel}
    'E': {tile: 13, tipo: vacio, guion: la_escena, una_vez: si}
```

The script fires **on entering** the cell, not while you stand on it: otherwise
a sign would talk to you sixty times a second. With `una_vez: si` it also only
fires the first time in the whole game, which is the difference between a sign
—which you can re-read— and the scene where somebody gives you a key.

A trigger can **also be anything else**: `tipo: vacio` so that
it can be walked through, but also `solido` or `plataforma` if you want the
cell to be solid and to fire as well.

**On starting a level**, with `guion:` in the level:

```yaml
niveles:
  - nombre: "EL VALLE"
    guion: bienvenida
    mapa: |
      ...
```

**And on pointing at a cell with a verb**, in the pointer view:

```yaml
tiles:
  leyenda:
    'q': {tile: 13, tipo: vacio, mirar: mirar_cuadro, hablar: hablar_cuadro}
```

This is the only one of the three that depends on the controller: the script
that comes out is the one for the verb you have on. See *The pointer view*,
above.

### The text box

Two lines of 36 characters, in the scoreboard. It is not a style decision: 36
is what fits on the narrowest of the seven machines with room to spare, and the
scoreboard is the only free space there is that does not cover the game.

The text is broken **in the compiler**, not on the machine: it is cut at word
boundaries into pages of two lines and the finished strings are what goes into
the ROM. Breaking at word boundaries has to be done by looking ahead, and on a
68000 at 7 MHz that would be paid for sixty times a second forever. Here it is
paid for once.

A long `decir:` comes out as several pages and they are turned one at a time
with the button. The text always comes out in capitals, which is what the font
has.

## `spawns`

Relates map symbols to enemies and objects:

```yaml
spawns:
  s: seta
  m: mosca
  c: moneda
```

It can go at the global level or inside one particular level (the level's
wins).

## `niveles`

```yaml
niveles:
  - nombre: "BOSQUE"
    fondo: "#101830"
    llaves: 1               # keys to be carried to open the goal
    spawns: {b: jefe}       # optional, added to the global ones
    mapa: |
      ....................
      P..................G
      ####################
```

The map's rules:

- Each character is a tile of 16x16 pixels.
- **`P`** marks where the player starts: exactly one per level.
- Minimum 20 columns × 14 rows (what one screen takes), maximum 512 × 256.
- Shorter rows are filled with empty on the right.
- Maximum 64 enemies, objects and platforms per level.
- If a level has no `meta` tile and no boss, `ngplat` warns you (it could not
  be finished).
- With `llaves: N`, there have to be at least N keys on the map (see
  [`objetos`](#objetos)).

The levels are played in order; on finishing the last one `YOU WIN!` comes up.

---

## Each machine's limits

These are the game's, whichever machine it is for:

| Thing | Limit | What happens if you go over |
|---|---|---|
| Colours per image | 15 + transparent | error at compile time, with the number of colours |
| Entities per level | 64 | error at compile time |
| Level size | 512 × 256 tiles | error at compile time |
| Sound effects | 46 | error at compile time |
| Musics | 14, of 2 tracks | error at compile time |
| Tile symbols | 255 | error at compile time |

And these change with the machine. `ngplat comprobar` looks at them before
compiling and tells you which one you have broken.

| | Neo Geo | Mega Drive | Amiga | Amiga 1200 | Jaguar |
|---|---|---|---|---|---|
| Colours at once | 4096 | 64 (4 palettes of 16) | 32, or 8 + 8 | 256, or 16 + 16 | 256 (one table) |
| Per channel | 5 bits | 3 bits | 4 bits | **8 bits** (exact) | 8 bits |
| Palettes | 256 | 4, melting yours together | 1, melting yours together | 1, melting yours together | 1, melting yours together |
| Distinct graphics | 65536 tiles | 1408 tiles of 8 × 8 | 1024 of 16 × 16 | 1024 of 16 × 16 | no fixed limit |
| Actors on screen | 96 sprites | 80 sprites | no fixed limit (the blitter draws them) | no fixed limit | no fixed limit |
| Level height | 256 tiles | 32 tiles | 16, or 32 if the level does not exceed 22 wide | the same | 16, or 32 if the level does not exceed 22 wide |
| Parallax layers | all | one | one, with `amiga: 8colores` | one, with `amiga: 16colores` | one |
| Sound | YM2610 | PSG SN76489 | Paula | Paula | the DACs, via the DSP |
| What comes out | cartridge ROMs | cartridge `.bin` | `.adf` floppy | `.adf` floppy (needs AGA) | `.j64` cartridge |

`ngplat sistemas` shows them without leaving the terminal.
