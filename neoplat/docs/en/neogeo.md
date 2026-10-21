# The Neo Geo inside (and what NeoPlat does with it)

This is what you need to know about the hardware to make sense of the generated
code, and the first place to look when something looks wrong in the emulator.

## The console in four lines

| | |
|---|---|
| CPU | Motorola 68000 at 12 MHz (no floating point, no cache) |
| Work RAM | 64 KB |
| Screen | 320 × 224, 60 fps |
| Sprites | 381 sprites 16 pixels wide and up to 32 tiles tall |
| Fix plane | 40 × 32 tiles of 8x8, no scroll (for the scoreboard) |
| Colour | 65536 colours, 4096 on screen, 16 per palette |
| Sound | Z80 + YM2610: FM for the music, SSG for the effects and ADPCM-A for the samples |

**There is no scrolling background plane.** The background is drawn with
sprites: that is what the commercial games do and what NeoPlat does.

## How NeoPlat draws

`engine/neogeo/np_video.c` shares out the sprites like this (with two parallax
layers):

```
sprite   1..96    player, enemies and objects       (front)
sprite  97..117   stage: 21 columns of 15 tiles
sprite 118..138   near parallax layer
sprite 139..159   far parallax layer                (back)
```

The sprite number decides who covers whom. The split above assumes that
**sprite 1 is drawn in front**, which is what the Neo Geo scene documents. If,
on trying the ROM, the background covers the player, change
`NP_SPRITE_FRONT_FIRST` to 0 in `np_video.h`: the whole split is inverted at
once and nothing else has to be touched.

Each parallax layer is another set of 21 columns whose tilemap is read from the
layer's image, shifted by a fraction of the camera. The tilemaps are only
rewritten when the layer crosses into another tile.

Each background column is a sprite with its own tilemap. When the camera moves
within the same tile only the positions are updated (21 writes); when it
crosses into another tile the tilemaps are rewritten. That way scrolling costs
little CPU time.

The scoreboard goes on the fix plane, which does not move with the camera.

### Driving, the split is different: the road in bands

This is the only one of the seven machines with **nothing** to slide an image
line by line: there is no plane to shift (the Mega Drive and the X68000), no
copper to change it in the middle of the screen (the Amiga), no per-line object
list (the Jaguar). Here everything is sprites, and a Neo Geo sprite is **a
column**: exactly the opposite of what is needed.

So the road goes in bands. The image is the same one the Mega Drive gets —the
roadway in perspective, 512 wide, with the four bands drawn inside it— and it
is split into rows of twenty-one sprite columns, one row every 16 lines. Each
band is shifted by whatever the projection says at its middle line:

```
sprite   1..48    the car, the traffic and anything on the roadway  (front)
sprite  49..342   the road: 14 bands of 21 columns                  (back)
```

That is 294 of the console's 381 sprites, so the actors are left with fewer. It
does not matter: on the roadway you see two cars on average, not twenty.

It is the Mega Drive's per-line scroll rounded to sixteen, and the corner
changes so little from one line to the next that the staircase does not show.
Three details that make it fit in the frame:

- the columns of each band go **in a ring**, just as in the background: column
  N of the image always lands on sprite N mod 21, so when a band shifts by one
  tile only one tilemap has to be redone;
- a band's Y and height never change, so `SCB3` is written once on entering the
  level;
- and the Xs of the twenty-one sprites are **consecutive** in VRAM, so the
  address is set once and they are written in one go, in sprite order and not
  screen order: 23 writes per band instead of 84.

The stripes running towards you are not drawn: they are four palette slots per
thing, rotated one step per frame. Twelve words to colour RAM.

### The sprite scaler (SCB2)

What none of the other six has. Each sprite carries in `SCB2` a word with two
numbers: the top one, four bits, is the width (from 1 to 16 pixels per tile
column) and the bottom one, eight bits, the height (from 1 to 256 lines out of
every 256). It is what the bosses that come at you in this machine's games do.

The road's traffic uses both things at once:

1. the engine picks the graphic with `np_carretera_dibujo_zoom()`, which is
   like the other six's `np_carretera_dibujo()` but **the other way round**: it
   does not look for the largest graphic that will do, but the smallest one
   that is not too small. That way a distant car still costs one sprite and not
   four;
2. and the scaler covers the step up to the exact size.

Here the cars do not grow in jumps of five sizes: they grow.

## Graphics format

It is implemented in `tools/ngplat/gfx.py`. Each function has its inverse and
the tests check that encoding and decoding gives back the original image.

### Colour (16 bits)

```
bit  15 14 13 12 11 10  9  8  7  6  5  4  3  2  1  0
      D R0 G0 B0 [ R4..R1 ] [ G4..G1 ] [ B4..B1 ]
```

Each channel has 5 bits: the top 4 go in its nibble and the least significant
bit goes to bits 14/13/12. Bit 15 is the "dark" bit.

Colour 0 of each palette is always transparent.

### Sprite tile (ROM C): 16x16, 4 bits per pixel

A tile takes 128 bytes split between two ROMs: **C1** carries bitplanes 0 and
1, **C2** planes 2 and 3. Inside each ROM, a tile's 64 bytes go like this:

```
bytes  0..15   low plane,  right half  (x = 8..15), rows 0..15
bytes 16..31   low plane,  left half   (x = 0..7)
bytes 32..47   high plane, right half
bytes 48..63   high plane, left half
```

In each byte, **bit 7 is the leftmost pixel** of the group of 8.

### Fix-plane tile (ROM S): 8x8, 4 bits per pixel

32 bytes per tile, 4 bytes per row, two pixels per byte (low nibble first). The
four column pairs are stored in the order **3, 0, 1, 2**.

> **If the graphics come out scrambled in the emulator**, this is where to
> look: `encode_sprite_tile()` and `encode_fix_tile()` in
> `tools/ngplat/gfx.py`. They are written to the Neo Geo scene's hardware
> documentation, but **I have not been able to check them against a real
> emulator** in the environment the kit was written in. Alternative: if you
> have ngdevkit's tools (`tiletool`), you can convert the PNGs with them and
> replace the generated `.c1/.c2/.s1`.

## Registers the engine uses

```c
0x300000  player 1's controller (active low)
0x300001  watchdog: it has to be written every frame or the board resets
0x340000  player 2's controller (with `jugadores: 2`)
0x380000  START and SELECT: bits 0 and 1 player 1's, 2 and 3 player 2's
0x3C0000  VRAM address
0x3C0002  VRAM read/write (auto-increments)
0x3C0004  increment after each access
0x3C0006  LSPC mode / line counter (for waiting on the vblank)
0x400000  palette RAM (256 palettes x 16 colours)
0x401FFE  background colour (backdrop)
```

VRAM map:

```
0x0000   SCB1  sprite tilemaps (64 words per sprite: tile, attributes)
0x7000   fix plane, 40x32, addressed by columns: 0x7000 + col*32 + row
0x8000   SCB2  zoom
0x8200   SCB3  Y position (496 - y), chaining and height
0x8400   SCB4  X position
```

The engine uses neither the BIOS nor the interrupts: it waits for the vertical
blank by reading the line counter. If you would rather use ngdevkit's
interrupt, replace `np_wait_vblank()` in `np_video.c` with `ng_wait_vblank()`;
the rest of the engine does not change.

## The sound: the Z80 and the YM2610

The sound chip does not hang off the 68000 but off a Z80 with its own ROM (the
M1). The game sends one-byte commands through port `$320000`; that fires an NMI
on the Z80, which reads the command on its port 0.

`ngplat` generates that driver from the `game.yaml` (`tools/ngplat/m1.py`),
assembles it with its own Z80 assembler (`tools/ngplat/z80.py`) and leaves the
commented source in `build/src/sonido.z80` in case you want to look at it.

Format of the command byte:

```
bit 6      toggle (lets the same sound be repeated twice in a row)
bits 0-5   $01..$2F effect, $30..$3E music, $3F stop the music
```

The YM2610 is three chips in one, and the driver uses all three at once:

```
FM channel 1 ($A1/$A5, voice at $31..$B5)   the music's first track
FM channel 2 ($A2/$A6, voice at $32..$B6)   the second track
SSG channel C ($04/$05, volume $0A)         effects, and noise for the hits
ADPCM-A channel 0 (part B of the chip)      the digital samples
```

**This chip's FM channels start at 1, not at 0**: the YM2610 is a YM2608 with
the first of every three taken out, so of the six, four are left and in each
half of the chip 1 and 2 are the valid ones. Writing channel 0 gives no error:
it just does not sound.

An FM note is two bytes, `fnum` and block, which the compiler leaves in the ROM
already shaped as registers `$A0` and `$A4`; the driver just releases the note,
copies the two bytes and presses again. The **voice** (what it sounds like: see
[sonido.md](sonido.md#what-it-sounds-like-timbres)) is a couple of dozen
registers loaded once at the start of the song, with the volume already in, so
playing a note costs no more than four writes.

The period of an effect on the SSG is `4,000,000 / (16 * frequency)`, and the
beat is set by the YM2610's timer B, programmed to about 60 Hz so that the
music advances at the game's pace.

One thing that gives no warning when done wrong: the chip stays **busy** for a
while after each write and does not say so. After the data of an FM register it
is about 83 cycles of its own clock, which at 8 MHz is 10 microseconds; the
driver waits them out counting `nop`s, which at 4 MHz come one per microsecond.

### Digital samples: the ADPCM-A channels and the V1 ROM

The YM2610 also has **six sample channels**, which read on their own from a
separate ROM (the V1) at a fixed 18,500 samples per second in 4-bit ADPCM: half
the size, which is what made it possible to fit voices on a 1990 cartridge.
`tools/ngplat/adpcm.py` is that codec, and the V1 ROM is assembled by the same
file that generates the M1, because the two have to agree on the addresses.

The chip addresses the V1 **in 256-byte blocks**, so each sample starts on one.
The first block is left free on purpose: that way the driver can use "start = 0"
to mean that this effect has no sample, without confusing it with one that
started at byte zero.

The driver uses channel 0 and gives it five things through **part B** of the
chip (ports `$06` and `$07`, not `$04` and `$05` like the SSG):

```
$00 = $81          stop whatever was sounding
$10/$18            where it starts, in 256-byte blocks
$20/$28            where it ends
$01 = $3F          overall ADPCM-A volume, at maximum
$08 = $DF          channel 0: both speakers and volume at maximum
$00 = $01          and off it goes
```

Encoding is a search: for each sample all sixteen nibbles are tried and the one
that leaves the predictor closest is chosen. That is sixteen subtractions per
sample, done once at compile time, and it comes out better than any approximate
formula: about 27 dB of signal-to-noise ratio on an ordinary wave.

The test bench **decodes the ADPCM-A** in order to hear it, so the circuit is
checked end to end, from the WAV to the speaker.

The tests run this driver in a Z80 emulator (`tests/z80sim.py`) and, from the
test bench, the whole circuit: the 68000 writes to `$320000`, that fires the
Z80's NMI, the Z80 runs the real M1 ROM, and from the registers it leaves in
the YM2610 the wave is generated and compared against the `game.yaml`'s notes.
How, in [sonido.md](sonido.md). The **digital samples** go by another route:
the YM2610's six ADPCM-A channels read on their own from the V1 ROM the
compiler assembles, so there the Z80 does nothing but tell the chip which one
to play.

## The ROM that is generated

```
build/rom/202-p1.p1   program (68000), generated by make
build/rom/202-c1.c1   graphics, planes 0 and 1
build/rom/202-c2.c2   graphics, planes 2 and 3
build/rom/202-s1.s1   fix plane (the scoreboard's font)
build/rom/202-m1.m1   the Z80's sound driver, with your music and your effects
build/rom/202-v1.v1   digital samples, already in ADPCM-A
```

The identifier `202` is that of the `puzzledp` romset, which is the one
ngdevkit's emulator uses for homebrew. It can be changed with
`ngplat compilar --rom-id`.

## A 68000 trap the game hangs on

With `-Os`, faced with two consecutive byte writes (`w->keys = 0;
w->entity_count = 0;`) gcc emits a `clr.w`, a single two-byte write. If the
pair lands on an **odd address**, the 68000 stops with an *address error*: it
cannot read or write words at odd addresses.

It happens to any 68000 compiler, ngdevkit included, so the kit compiles with
**`-fno-store-merging`**. The tests go over the machine code of all eight
targets and fail if a single access of that kind shows up.

It was discovered by booting the Mega Drive ROM in an emulator (it froze as
soon as the level loaded); the Neo Geo one had exactly the same
`clr.w %a0@(2109)`.

## Installing ngdevkit

```bash
# macOS
brew tap dciabrin/ngdevkit && brew install ngdevkit ngdevkit-gngeo

# Linux / others: see https://github.com/dciabrin/ngdevkit
```

After that, `ngplat compilar --make` builds the ROM directly.

## Trying the ROM without the BIOS: the test bench

The other six machines are booted in a real emulator inside the tests. The Neo
Geo cannot be: any emulator needs SNK's BIOS, which is proprietary and not
distributed.

So the kit brings half an emulator of its own, in `tests/maquina_neogeo.py`:

- the **real 68000** is run by Musashi (the same core as MAME) through
  `machine68k`, which comes with `amitools`;
- the **LSPC** (the video chip) is written by hand in Python: it keeps what the
  game writes through `$3C0000`-`$3C0004` and then rebuilds the picture with
  the tiles from the C1/C2 and S1 ROMs and the palettes from `$400000`.

The game that runs is exactly the one `ngplat compilar` generates. The only
thing added is `tests/neogeo/arranque.c`, which does what the BIOS would do
(set the stack, copy `.data`, clear `.bss`) and enters `main()`.

```bash
pip3 install amitools           # brings machine68k
apt-get install gcc-m68k-linux-gnu
make test-emulador-neogeo       # leaves the screenshots in capturas/
```

The test turns the console on, looks at the title screen, presses START, plays
for a while to the right and checks that the picture changes, that the
scoreboard is drawn and that no frame goes over the machine's budget.

**It is not a Neo Geo emulator.** There is no BIOS. The Z80 with the YM2610 are
there (the M1 ROM really runs) and so is the sprite zoom, modelled with
proportional sharing: the real chip chooses which pixels survive with a table
of its own, so one may land differently; what does come out the same is the
**size**, which is what gets checked. And there are two things it takes for
granted, the same two the engine takes for granted, so it cannot contradict
them (only an MVS or MAME with a BIOS can):

- that sprite 0 goes in front and the following ones stay behind;
- that row 0 of the fix plane lands on line 0 of the screen.

## Performance

A frame is 200,000 68000 cycles (12 MHz divided by 60 frames). Measured with
the test bench on the `bosque-magico` example, running and jumping:

| | cycles per frame |
|---|---|
| normal frame | 96,000 |
| frame where the camera crosses a tile vertically | 162,000 |
| the console's budget | 200,000 |

Getting there meant fixing five things, and all of them were seen with the
bench:

**The background was redrawn whole.** The Neo Geo has no scrolling plane: the
stage is 21 columns of sprites. On crossing a tile all 21 were refilled (630
VRAM writes) and the console dropped to **29 fps**. Now the sharing is circular
—column N of the map always lands on sprite N mod 21— so twenty columns are
already where they should be and only the one coming in at the edge is
refilled: 30 writes. The parallax layers work the same way. In total, 79% fewer
VRAM writes.

**Each background tile cost a 32-bit multiplication.** `np_tile_gfx_at()`
works out `row * width + column`, and the 68000 cannot multiply two long
integers: the compiler goes off to a software routine.
`np_tile_gfx_column()` (in `np_world.c`) multiplies once per column and comes
down adding the map's width.

**Placing a sprite cost six writes.** SCB3 and SCB4 are `0x200` apart, so by
setting that `0x200` as the increment the chip itself jumps from the vertical
position to the horizontal one and the address only has to be given once: three
writes. It is the most-called function in the whole engine.

**The parallax layers were repositioned even when they had not moved.** A layer
at speed 0.2 advances one pixel for every five of camera: on the other four
frames there is nothing to write, and that is 21 sprite positions per layer.
The example's two layers cost **40,000 of the frame's 132,000 cycles**; now, if
the layer's scroll comes out the same as the previous frame's, nothing is
touched.

**The scoreboard was repainted whole every frame.** Each letter is a VRAM write
and almost no frame changes anything: the score goes up when a coin is picked
up and the lives almost never. It was **14,000 cycles** per frame. Now only
what has changed is written (and the fixed words, once only).

What is left to do is the peak: when the camera crosses a tile **vertically**
all 21 columns have to be redone, because a sprite's tile strip cannot be
rotated. Each column could be given a strip taller than the screen and a start
row of its own, and the work spread over several frames; it is not done.

The places to be careful if you extend the engine are the same ones: 32-bit
multiplications (slow on a 68000), divisions (slower still) and unnecessary
VRAM writes.

## What has not been possible to check

The test bench covers the video, the controller and the sound, and the FM
music, the V1 ROM's samples and the sprite zoom are already in there. What has
not been seen is any of this **on a real board**: the bench is the kit's own,
and of the scaler it models the size but not which exact pixel survives.
