# The editor

The preview that `ngplat probar` opens **is** the editor. There is nothing to
install and no program to switch to: you press <kbd>E</kbd> and the game pauses
so that you can edit it; <kbd>Enter</kbd> and you are playing it again.

Both ways back to the game —<kbd>Enter</kbd> ("test the level") and <kbd>E</kbd>
("back to playing")— carry whatever you have drawn. If you have touched the
stage, the level **starts over**: it has to, because you could be standing right
where you have just painted a wall. If you have not touched it, you carry on
playing where you were.

```bash
ngplat probar          # opens the game; press E to edit
```

## In a window of its own, with no browser around it

`ngplat probar` opens it in the browser, with its address bar, its tabs and
—on Windows— a black console window behind it. It works, but it does not look
like a program for making games: it looks like a web page.

```bash
ngplat app             # the same, but in its own window
```

No address bar, no tabs, its own icon in the taskbar, and **it stops the server
when you close it** — which is what is needed when there is no console to go
back to and press Ctrl+C in. Inside it is the same `ngplat probar` serving on
127.0.0.1, so saving and compiling work just the same.

On **Windows** that is what **`NeoPlat.exe`** does: double click and the editor
comes up. If there is a game beside it, it opens it; if there are several, it
asks which; and if there are none, it lets you create one. The usual
`ngplat.exe` is still there for the command line.

> **What is needed, and what is not.** The window is opened by Edge or Chrome
> in their *application mode* (`--app=`), which is what that mode exists for.
> Edge comes with Windows 10 and 11, so there is normally nothing to install;
> if neither is there, the editor opens in your usual browser and NeoPlat tells
> you so. With `NEOPLAT_NAVEGADOR` you tell it which one to use if you keep it
> somewhere unusual.
>
> **If you get an ordinary tab and you wanted the window**, this command says
> where it looked for the browser and what it found in each place:
>
> ```bash
> ngplat navegador
> ```
>
> It asks Windows first — the registry's `App Paths` list, the same one the
> system uses to resolve `msedge` when you type it into Run — and only then
> looks in `Program Files` and on the PATH. So it does not matter which drive
> it is installed on.
>
> **The editor has not been rewritten, and that is deliberate.** It is fifteen
> thousand lines of JavaScript that draw sprites freehand, play animations at
> 60 pictures per second and run the game itself inside. Packaging a whole
> browser (Electron and company) is 150 MB and a toolchain the kit does not
> have —the whole kit takes less than that— and redoing it in a windowing
> library would be months to end up with less than there already is. What
> changes is the frame; what is inside is the same editor.

Everything you change ends up in your `game.yaml`, keeping comments, order and
formatting: the editor only touches the lines you have changed.

---

## Map

The **mapa** tab is where you draw.

| Tool | Key | What it does |
|---|---|---|
| pencil | <kbd>1</kbd> | paints cell by cell; drag to make strokes |
| rectangle | <kbd>2</kbd> | drag and release; the right button erases |
| fill | <kbd>3</kbd> | fills the whole contiguous area, respecting walls |
| selection | <kbd>4</kbd> | marks a rectangle to copy, cut, paste or delete |
| eyedropper | <kbd>5</kbd> | picks up the symbol under the cursor (or <kbd>Alt</kbd>+click) |
| move | <kbd>6</kbd> | drags the view |

Other shortcuts: <kbd>Ctrl</kbd>+<kbd>Z</kbd> undo,
<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> redo,
<kbd>Ctrl</kbd>+<kbd>C</kbd>/<kbd>X</kbd>/<kbd>V</kbd> copy, cut and paste,
<kbd>Del</kbd> delete the selection, <kbd>G</kbd> grid, <kbd>H</kbd> screen
guides, arrows to move around (with <kbd>Shift</kbd> faster), <kbd>Esc</kbd>
drop the selection.

A **whole stroke counts as one undo step**, not one per cell.

The **palette** is built from your own `game.yaml`: there is a button for each
symbol in the legend (with its real graphic; if the cell is a **trigger** it
also says which script it fires, because it is often air and there is no other
way of telling it from the gap next to it) and another for each thing you have
put in `spawns` —enemies, objects, moving platforms, breakables, prisoners and
spawners— plus the player's start. If the game has **stairs**
(`tipo: escalera` and `escalera_izquierda`), they come out as one more symbol:
they are painted cell by cell, going up a row and along a column per step,
which is how the engine walks them. **Checkpoints** (`tipo: control`) too: they
are painted on the row where you want the player to land on respawning, which
is usually the one above the floor.

Below the canvas there is a **minimap**: it shows the whole level and the box
of what you are looking at; click to go anywhere. The **guides** mark where
each 320×224 screen falls, which is what is seen at once on the console.

You can also **zoom out and in** (0.5× / 1:1 / 2×) and change the level's size
with ± width and ± height, which respect the floor row.

### An isometric game is edited room by room

With `vista: isometrica` the map **is not what you see**: it is the room's
floor plan, and what gets drawn are rooms. So the editor changes two things,
and only two:

- **it draws the same thing the game does**: each room isometric, with its
  floor, its cubes and its enemies placed where they will be while playing, and
  all the level's rooms side by side. The guides mark where each room ends;
- **it translates the mouse backwards**: you click on a cell's diamond and it
  paints that cell. The grid (<kbd>G</kbd>) is the floor plan's diamonds, which
  is what counts the cells when the floor runs diagonally.

Everything else stays the same: the same pencil, the same fill, the same
selection, the same undo and the same `game.yaml`. You are painting on the same
text map as always.

In the **palette**, each cell comes out with **its cube and its height**
—"solid: wall (height 48)", "solid: slab (height 16)"— and not with its `tile:`,
which in this view is always empty and would leave them all blank. That is what
is needed in order not to confuse a wall with a step. The ones that rise and
bring no cube —the back walls, which already come in the room's drawing— come
out blank on purpose and are called "solid (height 48) already painted": the
background drawing already shows them in place.

### A graphic adventure is edited the same way, but what you paint answers back

With `vista: puntero` the map is still a text map and it is painted with the
same pencil. What changes is what the cells mean: here nearly all of them are
`vacio` —a cursor collides with nothing— and what tells them apart is **which
verb they answer**. That is why in the palette they do not come out by their
type, which would be the same twenty times, but by the verbs they answer to
—"look, take", "use"— and the ones that answer nothing come out as "scenery".

The scripts are written in the `game.yaml`, which the editor reads and rewrites
without touching your comments: a big piece of furniture is several cells with
the same scripts, and moving it means painting it somewhere else.

## Level

Name, background colour, music and which parallax layers it uses. And level
management: **new** (born with a start, a goal and a floor, ready to play),
**duplicate**, **delete** and **up/down** to change the order.

## Game and physics

Title, author, lives, time limit, the **machine** it is compiled for (Neo Geo,
Mega Drive, Amiga, Jaguar, Atari ST or X68000), the two options only the Amiga
looks at —how it shares out its bitplanes and **which Amiga the game is aimed
at**, `512K`, `1M` or `2M`— and all the player's settings with sliders: speed,
jump, gravity, acceleration, friction, air control, jump cut, maximum fall,
bounce, coyote time, jump buffer, health, invulnerability, knockback on being
hit, stunned frames, climbing speed, crouched box height, double jump, stomping
enemies and crouching.

Each change applies **immediately**: press <kbd>Enter</kbd> and you try it.
Below it tells you what your jump achieves with those numbers, for example:

> with these settings the jump rises 31 px (1 cell) and crosses 48 px (3 cells)

That is what to look at before drawing a gap.

The machine is saved in the `game.yaml` like any other setting, but it does not
change the preview on the fly: the colours you see are those of the machine it
was generated with. To see it with another, save the yaml and run
`ngplat probar --sistema <machine>` again.

## Enemies and objects

Each enemy defined in the `game.yaml` with its behaviour (patrol, flyer,
chaser, jumper, fixed), speed, health, damage, points, whether it can be
stomped, whether it turns at edges and the settings particular to each
behaviour. The objects, with their effect, points and amount. And the
**delete** button, which also clears their appearances from the map.

### Creating a new one

**"+ new enemy"** or **"+ new object"** opens a form with everything needed:

- **name** and map **symbol** (it suggests a free one; it allows neither
  duplicates nor treading on a tile)
- **graphic**: reuse one of the PNGs the project already has, or **draw it
  right there**
- frame **size** (16×16, 16×32, 32×16, 32×32), **how many frames** and the
  **collision box**
- behaviour, speed, health and points (or effect and points, if it is an
  object)

On creating it, it appears in the map's palette and you can paint it and try it
straight away.

If you choose "draw it here" a small canvas comes up with just enough to invent
a creature. For everything else there is the **dibujos** tab.

## Graphics

Here you draw **anything in the project**: the player, each enemy, each object,
the stage and the background layers. The list on the left has them all; you
click one and it opens with its own palette.

Two things an ordinary pixel editor cannot do, and which are the reason this
one lives inside the kit:

- **the colours are the target machine's.** The graphic is loaded from the PNG
  already put through the machine's rounding, so what you see on the canvas is
  exactly what will be seen on the Neo Geo, the Atari ST or wherever. And the
  counter at the top right says **how many colours you are using of the ones
  that fit**, in red if you go over, before the compiler tells you;
- **the animation runs at the real speed.** The preview on the right plays
  whichever animation you choose (`quieto`, `correr`, `saltar`…) with the
  frames and the speed that actor has in the `game.yaml`, while you draw.

**And it is edited right there.** Below the preview are the fourteen slots the
engine understands —`quieto`, `correr`, `saltar`, `caer`, `dano`, `atacar`,
`subir`, `agachado`, `arriba`, `abajo`, `remate`, `patada`, `nadar` and
`bucear`— and, for the chosen one, **which frames it uses** (`0, 1, 2, 1`),
**how long each one lasts** and **whether it loops**. It applies immediately:
press <kbd>Enter</kbd> and the character already moves that way. On saving, the
animation goes into the `game.yaml` on one line
(`correr: {frames: [1, 2, 3, 2], velocidad: 6}`). A frame that does not exist
in the sheet is dropped and it tells you.

What you draw **is seen in the game without saving**: the touch-up goes into
the sheet the game is painted with as soon as you release the mouse. Saving is
for writing it into the project's PNG.

**Tools**: pencil, eraser, line, rectangle (hollow or filled), ellipse (hollow
or filled), area fill, eyedropper and move a piece. All with undo and redo.

**Per frame**: mirror, flip, rotate (if square), clear, duplicate (it is copied
from the previous one, which is how things are animated), remove, **copy** and
**paste**.

**Copy and paste work from one graphic to another.** The whole frame is copied,
or the piece you have selected with "move piece", and it can be pasted into any
other graphic even if it has a different palette. That last part matters: the
pixels are indices, not colours, and pasting them as they are would change the
colours without warning. The editor translates colour to colour —the exact one
if it is there, the nearest if not— and tells you how many it has had to
approximate. It is the same sum the compiler does when a graphic does not fit
in the machine's palette.

**New** creates a graphic that is not in the `game.yaml` yet: you give it a
name and a size (width, height and how many frames) and it comes out blank, in
the list, under "new". On saving it, it appears at `graficos/<name>.png`; for
it to show up in the game you have to note it in the `game.yaml` —or create the
enemy or object from the **juego** tab, which already does it for you.

**Import** brings an outside PNG into the open graphic: whatever you drew in
Aseprite, in GIMP or wherever. If it is exactly the sheet's size, it goes in as
it is; if it is a strip of the same height with an exact number of frames, the
sheet adapts itself. If it does not add up, it tells you how big it is and how
big it needed to be instead of swallowing it. Either way the graphic keeps the
**15 most-used colours** of the PNG, which is what fits.

**For seeing properly**: zoom, pixel grid, frame markers —the active one in
yellow— and **onion skin**, which shows the previous frame as a ghost under the
one you are drawing.

A sprite opens at a large size, for drawing pixel by pixel; a whole background
layer opens however it fits, to be seen at a glance.

**Saving.** With `ngplat probar` running, "save" leaves the PNG in its place
inside the project and the preview uses it immediately: you draw, you save and
you see it in the game without leaving the browser. If you have opened the
`preview.html` bare (`file://`) there is nobody to talk to and the button
downloads it for you to put in place by hand.

## Sound

The **sonido** tab changes what sounds, and lets you hear it without leaving
the editor.

**Effects.** The twelve moments the game produces by itself (`empezar`,
`salto`, `doble_salto`, `moneda`, `pisar`, `golpe`, `muerte`, `meta`, `vida`,
`disparo`, `romper` and `control`) are listed, with or without sound. On each
one you choose what type it is and adjust its numbers:

| type | what for | what is adjusted |
|---|---|---|
| `notas` | short melodies (coin, goal, start) | the notes and the frames each one lasts |
| `barrido` | jumps and shots: the frequency goes up or down | from which Hz to which Hz and in how many steps |
| `ruido` | hits and explosions | how many frames it lasts and the "colour" of the noise |

**"No sound"** takes it away, and choosing a type on a moment that was mute
gives it one. The **listen** button plays it right there. If an effect carries
a WAV (`muestra:`), the WAV stays where it is: what you edit is the fallback
for the machine that cannot play recorded sound.

**Music.** You choose the song, its frames per note, the volume and whether it
loops, and you write the two tracks —melody and accompaniment— in their box:

```
do4 mi4 sol4 mi4 | fa4 la4 do5 la4
sol4 si4 re5 si4 | do5 -   sol4 -
```

The notes go in Spanish (`do re mi fa sol la si`) or in English
(`c d e f g a b`), with `#` or `b` after them, the octave number (4 if you put
none), `-` for a rest, `|` to separate bars and `:2` to lengthen a note. Two
tracks at most: the chip's third channel is taken by the effects. Below it
tells you how long one turn lasts, and if you write a note that does not exist
it tells you in red instead of swallowing it.

**Listen** plays the whole song and **stop** cuts it off.

What you hear here is **exactly** what will sound on the machine: the browser
compiles the notes with the same procedure as the kit, and there is a test that
compares the two step by step.

## Check

A live list of what is wrong with the level, with a click to go to the spot:

- the `P` start is missing or there is more than one
- there is no goal: the level cannot be finished
- an enemy placed in the air, which will fall at the start
- a gap wider than the jump crosses (with **your** numbers)
- more than 64 enemies and objects —counting the creatures spawners can have
  out— or a level smaller than one screen

And the **"can it be finished?"** button: it launches a bot that plays the
level from start to finish the way somebody would the first time (walk and jump
when it sees something). In top-down games it looks for the way through to the
goal and decides as a person would: if health drains by itself and it has
little left it goes for **food**, if the goal asks for **keys** it does not have
it goes for one, and it leaves the goal for last. If it does not get there, it
tells you why —"there is no walking route to the key", "it gets stuck"— and
takes you to the point where it stopped. It is the same bot the kit's tests use.

In a **graphic adventure** that bot looks for no route —a cursor goes wherever
it likes—: it goes to each cell that answers to something and tries all four
verbs on it, over and over, shuffling the order each time round. It is brute
force on purpose, because it is exactly what a player does when stuck; if
trying everything does not finish the game, then it has no solution.

## game.yaml

The complete file with your changes. **Copy to clipboard** or **download**.

If you are in the preview published on claude.ai, the download goes through the
viewer and arrives as `game.yaml.txt`: it just needs renaming.

## Save

At the top right, next to the status, there is a **save** button that writes
what you are editing into the project's folder: the `game.yaml` and any
graphics you have pending. It also works with <kbd>Ctrl</kbd>+<kbd>S</kbd>, and
the editor saves by itself every 20 seconds if you have touched anything.

Saving and compiling are **two different things**, and that difference is what
makes it possible to build a big game without losing work:

| | save | compile |
|---|---|---|
| what it does | writes the `game.yaml` and the graphics | that, and also generates the code and the ROMs |
| how long it takes | immediate | seconds |
| does it demand the game be complete? | **no** | yes |

A half-finished level, an enemy placed but not defined, a goal that asks for
more keys than there are: none of that compiles, and it used to be exactly what
could not be left written down. Now it saves anyway and the log tells you what
is missing. The only thing that does not get saved is a `game.yaml` that cannot
even be read as YAML: that would be a bug in the editor, not something you
wrote.

The indicator next to the button says where you stand: *no changes*, *unsaved*,
*saving…* or the time of the last save. If you try to close the tab with
unwritten changes, the browser asks you.

## Backups

Every time it saves —by hand, with Ctrl+S or by itself— a **copy of the whole
project** is left first in `.neoplat/historial/`, with everything except what
can be regenerated (`build/`, `preview.html`). The **last 40** are kept, and two
saves in a row without touching anything do not make two copies.

The **copias** tab lists them and any of them can be restored with a button.
Restoring **also leaves a copy** of how things were before, so picking the
wrong version does not lose anything either.

The same from the terminal, which works without a browser:

```bash
ngplat copia              # save a copy right now
ngplat copia --motivo antes-del-jefe
ngplat historial          # list the copies, newest to oldest
ngplat recuperar 12       # take the project back to copy 0012
```

`.neoplat/` is local copies: the scaffold already puts it in the project's
`.gitignore`, because if you use git then git already does that job.

## Compile

The **compilar** tab builds the game without leaving the editor: you choose a
machine and the button saves your `game.yaml` into the project and compiles,
leaving the log of what happened right there.

The button says what will come out, because not every machine does the same
thing:

| Machine | What comes out |
|---|---|
| Neo Geo | **the ROM** — the P1/C1/C2/S1/M1 romset |
| Mega Drive | **the cartridge** — a 128 KB `.bin` |
| Amiga | **the floppy** — an 880 KB `.adf` that boots on its own |
| Atari Jaguar | **the cartridge** — a `.j64` with its header |
| Atari ST | **the floppy** — a 720 KB `.st` that boots on its own |

For it to work, the preview has to be served by `ngplat` itself, because a web
page cannot compile anything. That is what `ngplat probar` does by default:

```bash
ngplat probar          # opens the browser and keeps serving; Ctrl+C to stop
```

If you open the `preview.html` by hand (double click, `--no-servidor`, or the
preview published on claude.ai) the button comes out greyed and tells you this
same thing: there you have to export the `game.yaml` from the next tab along
and compile with `ngplat compilar --make`.

Details worth knowing:

- **It really saves.** The project's `game.yaml` is overwritten with whatever
  you have in the editor, leaving the previous one in `game.yaml.bak` and a
  copy in the history.
- **If what you send does not compile, the file goes back to how it was** and
  the log says what is wrong. For leaving a half-finished game written down
  there is the save button (and, if you lose it anyway, `ngplat historial`).
- **If there is no 68000 compiler**, the project is generated anyway (C code,
  graphics ROMs, sound ROM) and the log tells you what is missing.
- The server listens **only on 127.0.0.1** and demands a key generated at
  startup which goes in the address the browser opens. Without that, any other
  page you had open could write to your `game.yaml` and launch a `make`:
  browsers let any site talk to localhost.

## Nothing gets lost

There are three nets, and each one covers what gets past the one before:

1. **The browser's draft.** The editor saves by itself into `localStorage`
   every time you touch something. If you close the tab abruptly, the next time
   you open the preview it offers to restore what you were doing. The "forget
   saved changes" button deletes it. This lives in your browser, not on your
   disk.
2. **Saving into the project.** The *save* button,
   <kbd>Ctrl</kbd>+<kbd>S</kbd> and the autosave every 20 seconds write into
   the real folder. This is what survives changing computer, browser or month.
3. **The history.** Each save leaves a recoverable copy first, and there are
   40. It is what saves you from having broken something *yourself*, which is
   what neither of the other two can see.

## Why you can trust it

- The editor works on the text map, the same as the file does.
- On pressing "test the level" it rebuilds the data **with the same sums as the
  compiler** (start position, enemy boxes, tile indices), so what you play is
  what gets compiled.
- On exporting, each option is written with the name it already had in your
  file (in Spanish or in English) and only if you have changed it. There is a
  test that checks, option by option, that the reader understands all those
  names.
- The kit's tests make the whole round trip: they edit maps, physics and
  levels, create enemies and objects in the editor, export the `game.yaml`,
  compile it again and check that not a single comment has been lost. The
  browser test goes as far as drawing an enemy with the mouse, placing it,
  playing it and checking that its PNG is ready to save.
- And saving is tested end to end, with the real server behind it: a browser
  test edits, presses <kbd>Ctrl</kbd>+<kbd>S</kbd>, checks that **the file on
  disk has changed**, that the copy has been left, and goes back to it from the
  backups tab, checking that the file ends up as it was.
