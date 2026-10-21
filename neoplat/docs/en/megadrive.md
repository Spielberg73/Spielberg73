# The Mega Drive inside (and what NeoPlat does with it)

This is what you need to know about the hardware to make sense of the generated
code, and the first place to look when something looks wrong in the emulator.

## The console in four lines

| | |
|---|---|
| CPU | Motorola 68000 at 7.67 MHz |
| Work RAM | 64 KB, at `$FF0000`–`$FFFFFF` |
| Video | VDP with 64 KB of VRAM of its own |
| Screen | 320 × 224, 60 fps (50 in PAL) |
| Planes | A and B, 64 × 32 cells, with hardware scroll |
| Window plane | covers plane A wherever it is told to and does **not** move with the scroll |
| Sprites | 80 on screen, 20 per line |
| Colour | 512 colours, **64 on screen**: 4 palettes of 16 |
| Sound | YM2612 (FM, driven by a Z80) + PSG SN76489 |

Compared with the Neo Geo it makes the engine's life easier in some ways and
harder in others:

- **in its favour**: there are real background planes, so the stage and the
  parallax cost no sprites, and the 68000 can write the PSG itself without
  needing any Z80 code;
- **against it**: there are only 4 palettes of 16 colours for the whole game,
  and the planes are 64 × 32 cells (512 × 512 pixels), so the stage is
  rewritten column by column as the camera advances.

## How NeoPlat draws

`engine/megadrive/np_video.c` divides the screen like this:

```
window plane    the scoreboard (top 3 rows), fixed
sprites         player, enemies and objects
plane A         the stage, with scroll
plane B         the parallax layer, with its own scroll speed
colour 0        the level's background
```

The stage does not fit whole in plane A: a level can be 200 cells long and the
plane only has 64. What the engine does is draw just the column coming in at
the edge, and since the plane repeats every 64 cells (`& 63`), the new column
overwrites the one that has already left on the other side. Each of the game's
tiles is 16 × 16 and takes up four 8 × 8 cells of the VDP.

Scrolling is hardware: two words in the horizontal scroll table and two in
VSRAM. Plane B gets them multiplied by the layer's speed.

## How the VRAM is laid out

The VDP does not accept any address: planes A and B have to start at a multiple
of 8 KB, the window at a multiple of 4 KB (in 320 px mode), and the sprite and
scroll tables at a multiple of 1 KB. And each table **really does take up what
its size says**, so none of them can overlap another:

```
$0000   graphics            42 KB → 1344 tiles of 8×8
$A800   sprite table        80 entries of 8 bytes
$AC00   horizontal scroll
$B000   scoreboard          64 × 32 cells (4 KB)
$C000   stage               64 × 64 cells (8 KB)
$E000   parallax            64 × 64 cells (8 KB)
```

Slightly fewer than 1344 tiles of 8 × 8 fit. If you go over, `ngplat comprobar`
tells you before compiling.

With 64 × 64-cell planes each table is 8 KB, and three 8 KB tables do not fit
alongside the graphics: that is why the scoreboard uses 64 × 32 (it has room to
spare: it only takes up the first three rows).

The scoreboard shows because register $12 says "the window is the first three
rows". Left at zero, the window takes up nothing and the scoreboard is written
but not seen.

## Colours

A VDP colour is a word `0000 BBB0 GGG0 RRR0`: **three bits per channel**, and
in BGR order, not RGB. It is in `gfx_md.md_color()`.

Since there are only four palettes, `gfx_md.repartir_paletas()` melts the
project's together: it puts the tiles' palette, each actor's, each layer's and
the scoreboard's into four palettes of 15 colours (0 is transparent), reusing
the repeated colours. If they do not fit, it says so, naming the one left over.

Colour 0 of the first palette is the **screen's background**, and the engine
changes it at the start of each level to the `fondo:` you gave it.

## The road: it is not drawn, it slides

In a driving game (`vista: carretera`) the stage is **not painted per frame**.
The roadway in perspective comes ready-made from the compiler —a 512 × 224
image with 74 distinct tiles, which comes in as one more layer— and is painted
once into plane B at the start of the level. From then on, each frame writes
only the horizontal scroll table: **one word per screen line**, the one that
says where the roadway's axis passes at that height.

That is the whole of the drawing. The VDP has per-line scroll as standard
—register `$0B` set to `3`— and the table is 224 pairs that fit exactly in
`$AC00`, the gap already reserved before the window. Not a tile to redo.

It works because the roadway **is always the same width**: if the width does
not change, what is seen on a line is always the same image and the only thing
that changes is where it passes.

### The stripes running towards you are four colours

They are not drawn either. They are **four palette slots** for each thing
—roadway, shoulder, grass— rotated one step per frame: four words to CRAM, and
the bands run. Which slots those are is known by the compiler, and it leaves
them in `np_carretera_huecos`.

They go in pairs, **A, A, B, B**, not alternating. With A, B, A, B, rotating
one step merely swaps the two colours and the bands **flicker**: you cannot
tell whether the road is coming towards you or going the other way. In pairs,
each rotation moves the border between A and B **one segment**, and then they
travel.

### And the two shades have to be properly apart

An afternoon went here. The rotation had been right from the first day and the
roadway came out flat. The VDP stores **three bits per channel** —eight levels,
and the step is 255/7 ≈ 36 points— and the two asphalt greys the kit shipped,
`#4a4a52` and `#42424a`, are eight points apart: they land on the **same grey**.
The palette was rotating four identical colours. From the outside that is
indistinguishable from the CRAM writes not arriving, and that is where the
afternoon went.

If you touch the colours in `carretera:` in your `game.yaml`, separate them by
a whole step. And if you do not, the compiler tells you when you compile: see
`Sistema.avisos_de_carretera`.

### The traffic: drawn at five sizes, not scaled

What sits **on** the roadway —the cars ahead— is drawn per frame, and drawn in
perspective: the engine says where it falls and how much it shrinks
(`np_carretera_donde`), the same for all seven machines.

And it also says **in what order**. `np_carretera_trafico()` projects each thing
once, keeps the twelve nearest ones and returns them from far to near, which is
how they have to be drawn for the near ones to cover the far ones. This sum was
written here and on no other machine, and it showed: the ones without it drew
in entity-list order, so when two cars overlapped, whichever happened to be
first covered the other, and **not the same one on each machine**. Now everyone
asks for it; the Neo Geo walks the same list backwards, because there the one
that covers is the sprite with the lower number.

The VDP cannot shrink a sprite, so the compiler takes **five sizes** of each
thing that can appear on the roadway out of the same PNG, and the engine picks
the right one (`np_carretera_dibujo`). How many and which ones was not chosen by
eye: driving the scaffold's circuit with `tests/pilotar.js`, the traffic is seen
5,142 times and **half of those below scale 32** —an eighth of its size— so the
small sizes are the ones used most, and that is why there are more of them near
the bottom: 256, 128, 64, 32 and 16 out of 256.

Shrinking does not average: each pixel of the result keeps the colour that
**repeats most** in the square it covers. Averaging would invent colours, and
here a palette is sixteen. Counting instead of taking the middle pixel is also
what saves the silhouette: a 64 × 32 car reduced to 8 × 4 by taking the middle
one ends up with four pixels of bodywork or with none, depending on where the
grid falls, and it flickers as it recedes.

A detail that took finding: those shrunken graphics **do not go into the colour
sharing**. They bring not a single new colour —they come out of the same PNG—
but if they are counted, their pixels have weight, and on a machine short of
colour that changes which colours survive. On the Amiga it changed the player's
car palette and the car disappeared, painted in the asphalt greys, with nothing
warning about it. That is why `Build.actor_builds()` has a `con_lejos`: for the
tiles they are asked for with everything, for sharing colour they are asked for
without them.

A detail of the same family: the four entries of a band have to be four
**different** colours in 24 bits, or the palette quantiser merges them into one
and there is nothing left to rotate. They are separated by one point of blue,
and that point is anchored inside one of the machine's steps
(`_azul_para_separar` in `build.py`) so that it does not land right on a border
and show up as a stripe that was not meant to be there.

## How it sounds

The Mega Drive has two chips: the YM2612 (FM), which in practice the Z80
drives, and the PSG SN76489, with three square-wave channels and one noise
channel. The 68000 writes the PSG directly at `$C00011`, so NeoPlat uses it to
play the same notes as on the Neo Geo without needing any Z80:

```
channel 0 -> melody        channel 1 -> accompaniment
channel 2 -> effects       channel 3 -> noise (percussion)
```

Writing to the PSG means sending bytes:

```
latch:  1 cc t dddd    cc = channel, t = 1 volume / 0 tone, dddd = low 4 bits
data:   0 0 dddddd     the high 6 bits of the tone
```

Volume is **attenuation**: 0 is full blast and 15 is silence. The period is
worked out by the compiler with `periodo_psg()`: `3579545 / (32 · hertz)`, in
10 bits.

The tests listen to what comes out of the emulated PSG and check that they are
the notes from the `game.yaml`, one by one: see [sonido.md](sonido.md).

## Digital samples: the Z80 plays them

The 68000 cannot play **digital samples**. The DAC is inside the YM2612
(channel 6 in DAC mode, register `$2A`) and it has to be fed a byte every 125
microseconds: 8,000 interrupts per second would leave the game flat on its
face. The **Z80** does it, which is what it is there for.

The driver is written by the compiler (`tools/ngplat/md_pcm.py`), takes 132
bytes and is copied into the Z80's RAM at startup. Details that have to be got
right:

| | |
|---|---|
| starting the Z80 | ask for the bus **with reset already released** (in reset it does not give it, and the 68000 waits forever: the game does not even get as far as drawing), copy the driver byte by byte, give it a short reset so that it starts at `$0000`, and release the bus |
| asking it for a sample | the 68000 asks for the bus, writes bank, address and length into a block of its RAM and finally changes a `tick` byte. While it holds the bus the Z80 is stopped, so there is nothing else to synchronise |
| the clock | there is no timer: the pace is set by the cycle count of the loop itself. It is 449 out of the Z80's 3,579,545 per second, that is **7,972 samples per second**, and the WAV is resampled to exactly that rate when compiling |
| the 32 KB window | the Z80 does not see the whole cartridge, but 32 KB chosen with the register at `$6000` (nine bits, one per write). If the sample crosses the edge, the loop notices (HL goes from `$FFFF` to `$0000`) and changes bank on the fly |

Since the PSG and the YM2612 are different chips, the music and the sample
sound at the same time without getting in each other's way.

The driver is **run** in the tests (`tests/test_md_pcm.py`): the kit's Z80
emulator with the Mega Drive's memory faked on top, and it is checked that
exactly the sample's bytes arrive at the DAC and in order, even crossing the
32 KB edge. The cycle count is checked too, by adding it up again over the
already-assembled code.

## How a cartridge boots

A cartridge starts with two things at fixed addresses:

```
$000000   vector table: the first long word is the initial stack value and the
          second is the address it starts at
$000100   header: "SEGA MEGA DRIVE ", owner, name, serial, checksum,
          controllers, ROM range, region
$000200   the code
```

`engine/megadrive/arranque.c` lays out the vector table (stack at `$00FFFE00`)
and the header; `_start` copies the variables with an initial value into RAM
and zeroes the rest before calling `main()`.

The **checksum** and the **end of the ROM** cannot be known until the binary is
built, so `arreglar_rom.py` fills them in (it is generated inside the project
and needs nothing installed): it rounds the ROM up to a power of two, writes
the game's name, the range and the sum of all the words from `$200` on.

The first thing the engine does on power-up is the **TMSS** dance: second-batch
Mega Drives demand that `"SEGA"` be written to `$A14000` before touching the
VDP, or they shut down.

## Two 68000 traps the game hangs on

Both were found by the emulator test (`make test-emulador`) and neither could
be seen at compile time:

**1. The compiler's libgcc is 68020.** When the compiler meets a 32-bit `*`,
`/` or `%` it generates a call to `__mulsi3`, `__divsi3`, `__modsi3`… The 68000
does not have those instructions. Those routines usually come in libgcc, but
the one in a 68k compiler for Linux is built for the **68020** and carries
things like `bsr.l` (`61ff`), which the 68000 does not understand: on the first
division the game stops with a "line F" exception. That is why NeoPlat brings
its own in `engine/core/np_aritmetica.c` and links with `-nodefaultlibs`.

**2. gcc merges two byte writes into one word write.** With `-Os`, faced with
`w->keys = 0; w->entity_count = 0;` (two consecutive `uint8_t`s) gcc emits a
`clr.w`. If the pair lands on an odd address, the 68000 stops with an "address
error": **it cannot read or write words at odd addresses**. It is fixed with
`-fno-store-merging`, and the kit's tests go over the finished binary so that
none is left.

## If something looks wrong

- **Scrambled graphics**: the nibble order in `gfx_md.codificar_tile()` (each
  byte is two pixels, the left one in the high four bits).
- **Swapped colours**: look at the BGR order in `md_color()`.
- **A 16 × 16 tile split up**: the VDP draws the four cells in columns
  (top-left, bottom-left, top-right, bottom-right); it is in `partir_16()`.
- **The screen does not come up**: almost always the TMSS or the VDP registers
  in `np_md_init()`.
- **It freezes**: almost certainly one of the two traps above.
  `make test-emulador` catches it; to find out where, put a write to a RAM
  address you do not use (`*(volatile uint16_t *)0xFFFFF0 = n;`) at several
  points and watch that byte with the emulator.
- **Only half the screen shows**: check register $0C (it should be $81 for 320
  px)… or that whoever reads the framebuffer is not assuming 4 bytes per pixel
  when the emulator gives 2.
