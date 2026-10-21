# The Atari Jaguar inside (and what NeoPlat does with it)

This is what you need to know about the hardware to make sense of the generated
code, and the traps that were hard to find.

## The console in four lines

| | |
|---|---|
| CPU | Motorola **68000 at 13.3 MHz** — the same family as the other six |
| Video | **Object Processor**: walks an object list on every line |
| Colour | 256 at a time from a table, or 16 bits direct |
| RAM | 2 MB of DRAM at `$000000` |
| Cartridge | up to 6 MB, visible at `$800000` |
| Sound | Jerry: two 16-bit DACs fed by a DSP of its own |

The Jaguar also carries two 32-bit RISC processors (the **GPU** in Tom and the
**DSP** in Jerry). NeoPlat **does not use them**: the 68000 and the Object
Processor are plenty for a platform game, and that way there is no need to
install Atari's SDK or another assembler. A 68000 `gcc` is enough, the same one
as on the other machines.

## How NeoPlat draws

The Jaguar has no tile planes and no sprites. It has an **object list** in RAM
that the chip walks through entirely on every scanline, composing what it finds
into a line buffer. NeoPlat builds this one, from back to front:

```
branch     if the line is past the end of the screen, jump to the STOP
branch     if it has not reached the start yet, likewise
background the stage's bitmap, with the scroll applied
actors     one object per 16x16 piece of player, enemy or object
scoreboard the top band, over everything
STOP
```

That changes how the work is shared out compared with the other machines:

- **The stage** is a linear bitmap of **one byte per pixel**. It is drawn
  column by column as it comes in at the edge, the same as on the Amiga, but by
  copying bytes: no bitplanes and no masks. Its shape is chosen by the game —the
  tallest level decides—: 704 × 256 (44 × 16 cells) for one you cross, or
  352 × 512 (22 × 32) for one you **climb**. Both take the same 176 KB. In the
  tall shape there is no window —two cells would be left over at the sides— so
  the level has to fit whole across and the stage is painted once on entry;
  `ngplat comprobar --sistema jaguar` says so before compiling.
- **Scrolling is free.** The address of the object's data is moved (eight
  pixels at a time, which is what the field allows) and the rest of the shift is
  done with its X position.
- **The actors are not drawn.** Each piece is one more object in the list and
  the chip composes it, with colour 0 as transparent. There is no need to
  repaint the background behind, which is the most expensive thing on the
  Amiga.

## Graphics format

**Colour (16 bits)**: the layout is peculiar, `RRRRRBBBBBGGGGGG`. Five bits of
red at the top, five of blue in the middle and **six of green at the bottom**.
It is not RGB565; it is checked by reading the background colour in the
emulator.

**Graphics**: 16 × 16 consecutive bytes, one byte per pixel, aligned to 8
because the chip reads them phrase by phrase. Index 0 is transparent.

## The object list

Each object is one or two 64-bit "phrases". The hardest part is that the
address of the next one (the **link**) is split between the two halves:

```
bits 63-43   address of the data (>> 3)
bits 42-24   link to the next object (>> 3)
bits 27-14   height in lines
bits 13-3    Y position, in half lines
bits  2-0    type (0 bitmap, 3 branch, 4 stop)
```

The arithmetic for splitting the link is copied from `InitLister`, in Atari's
SDK, and commented in `np_video.c`.

## Three traps that cost an afternoon

All three were found by booting the emulated console and looking, and all three
leave the screen black without saying why:

**1. The cartridge does not boot on its own.** There is no vector table: the
console reads the stack at `cart+$400` and the entry point at `cart+$404`. If
those eight bytes are zero, it jumps to address 0 and nothing happens.
`hacer_rom.py` puts them there.

**2. The chip spends the list as it draws.** As it walks a bitmap it subtracts
from the height and adds to the data address, so by the end of the frame the
object is used up. It has to be rewritten whole every time.

**3. And it has to be rewritten in the vertical blank, not before.** If the
list is touched with the beam in the middle of the screen, the object is
painted again from the top starting there. That is how the scoreboard came out
twice, the second time right where the CPU had got to. That is why the engine
builds the list in a copy and dumps it in one go in `np_wait_vblank()`. There
is a test that counts the scoreboard's text rows and fails if twice as many
come out.

**And a fourth, from the compiler**: neither the list nor the bitmap is read by
the program — they are read by the chip over DMA. Without `volatile` (or a
memory barrier) gcc deletes all the writes as useless and nothing is seen. It
is the same trap in both, and it gives no warning.

## The parallax: another object and that is it

Of the seven machines, the Jaguar is where the parallax comes cheapest. There
is nothing to redraw per frame: the layer is **another object** in the list,
with its own bitmap and its own position, and the chip composes it before the
stage. Moving it means changing two numbers:

```c
np_objeto(NP_DIR(np_fondo_bitmap) + sy * NP_MAPA_ANCHO + (sx & ~7),
          -(sx & 7), 0, ...);
```

The layer's graphic is painted once on entering the level, repeated across the
bitmap's 704 pixels; since the layer's width (256 px) fits in the space left
over (704 − 320 = 384), on reaching its width it goes back to the start and the
join does not show.

For it to be seen behind, the stage's object carries **colour 0 transparent**.
That fixes something else along the way: until now the stage's gaps showed
black (colour 0 of the table) instead of the level's background colour, which
is what the other machines do. Now what shows through there is the `BG`, which
is exactly the `fondo:` from the `game.yaml`.

## Digital samples

The same I2S handler that makes the square waves also plays recorded sound: one
byte of the cartridge per audio sample, with nothing interpolated (the WAV
comes in already at the DSP's 20,774 Hz). It is added to the square waves
before going to the DACs.

The pointer is **advanced by the DSP**, not the 68000: it lives in the shared
block, the 68000 only writes where it starts and where it ends, and when the
DSP reaches the end it sets it to zero and the sample switches itself off. The
bytes are stored unsigned (silence at 128) because `loadb` gives 0..255 and
subtracting 128 is cheaper than sign-extending.

Two things about the DSP that were hard to find:

- the block does not fit in a `jr` (the relative jump reaches 15 words), so the
  exit goes by register, with the address set at startup;
- **that register cannot be `r30`**: with the address there the DSP goes
  completely mute, music included. With `r15` it works. It is measured in the
  emulator, not assumed: the sound test goes from 16 of 16 notes to 2 of 16
  just by changing the register number.

## The controller

It is a matrix: a **word** with the row you want is written to `$F14000` and a
**long** is read from the same place. Active low.

```
row $81FE   bit 24 up, 25 down, 26 left, 27 right
            bit 1 button A, bit 0 PAUSE
row $81FD   bit 1 button B
```

The kit uses **PAUSE to start the game** (it is the middle button on the Jaguar
pad). In RetroArch it lands on the pad's *Select*.

### The second controller, which is not the first one shifted

With `jugadores: 2` the other port has to be read, and there lies the trap: the
two share the same row-selection byte —port 1 looks at the low nibble and port
2 at the high one— but **port 2's row table is port 1's with the bits
reversed**. That is, row 0 is not asked for with the same number:

| | row 0 | row 1 |
|---|---|---|
| port 1 | nibble `$E` (`$81FE`) | `$D` (`$81FD`) |
| port 2 | nibble `$7` (`$817F`) | `$B` (`$81BF`) |

The leftover nibbles are left at `$F`, which points at no controller. The rest
really is the first one shifted: the directions come out four bits higher
(28-31) and the buttons two (bit 3 for A, bit 2 for PAUSE).

This was not guessed: writing `$81EF` —which is what you would expect— the
second controller did not arrive, and the emulator test
(`tests/test_sistemas.py`, `TestDosJugadores`) caught it. The numbers come from
Atari's technical manual, from the section on the four-player adapter, which is
where the whole table of the sixteen codes is.

## The ROM that is generated

```
build/jaguar/rom/<Juego>.j64    the cartridge, 2 MB
build/jaguar/src/               the engine and your game, in C
build/jaguar/jaguar.ld          the cartridge's memory map
build/jaguar/hacer_rom.py       puts the header with the stack and the entry on it
```

It is built with `gcc-m68k-linux-gnu` and nothing else:

```bash
apt install gcc-m68k-linux-gnu
ngplat compilar mijuego --sistema jaguar --make
```

## Trying it

```bash
make test-emulador-jaguar
```

Virtual Jaguar **does not need Atari's BIOS** for cartridges (it comes turned
off by default), so this machine is checked for real, just like the Mega Drive
and the Amiga: it is booted, the title is looked at, the button is pressed, it
is played and the stage is checked to be moving.

## The sound: a program for the DSP

The Jaguar **has no sound chip**. It has two 16-bit DACs (`LTXD` at `$F1A148`
and `RTXD` at `$F1A14C`) and somebody has to give them a sample every time the
audio clock ticks, some twenty thousand times a second. The 68000 cannot: the
audio clock's (I2S) interrupt does not reach it, it reaches Jerry's **DSP**. So
for the Jaguar to make a sound you have to write a program for that processor,
just as on the Neo Geo you have to write one for the Z80.

The kit brings the assembler (`tools/ngplat/dsp.py`, 300 lines) and the driver
(`tools/ngplat/jerry.py`, 292 bytes of machine code). The split is:

| | |
|---|---|
| the **DSP** | generates the waves: three square and one noise, summed, one sample per interrupt |
| the **68000** | the same as on the Amiga and the Mega Drive: it carries the `game.yaml`'s sequences and, each frame, leaves in the DSP's RAM which note each channel is playing |

They talk through a block of seven words in the DSP's RAM: `step0 step1 step2
amplitude0 amplitude1 amplitude2 noise_amplitude`.

**How a channel sounds.** A 32-bit phase accumulator with a `step` added per
sample; the top bit says whether the square wave is up or down. It is the
cheapest way to make an exact square wave, and it gives the same note as the
Neo Geo's SSG or the Mega Drive's PSG:

    step = frequency * 2^32 / samples_per_second

With `SCLK = 19` that gives 26,590,906 / (64 × 20) = **20,774 samples per
second**. The tuning error is under 0.05% (less than one cent).

**What you need to know about the instruction set**, and which takes finding:

- each instruction is **one 16-bit word**: six of opcode, five for the first
  operand and five for the second, which is nearly always the destination;
- `movei` carries the 32-bit constant behind it **with the low word first**;
- `shlq` is the **only** instruction whose immediate is stored as `32 - n`;
- `jump` and `jr` have a **delay slot**: the instruction behind them runs
  before the jump;
- on entering the interrupt the DSP forces register bank 0, puts the return
  address on the stack (`r31`) and sets `IMASK`. To return you have to pop it,
  **add 2 to it** and write `D_FLAGS` with `IMASK` at zero and the bit that
  clears the I2S flag (`$420`), in the `jump`'s delay slot.

The I2S interrupt's vector is the second one: `$F1B010`. The vectors take 16
bytes each and only that one is used, so the handler starts there and carries
straight on.

**How it was debugged.** Nothing sounded at first, and with the emulator you
cannot see inside the DSP. It was done in pieces, each one a ROM: (1) the 68000
writing the DAC directly → it sounded, so `SCLK` and `SMODE` were right; (2)
the DSP writing the DAC from its main loop → it sounded, so the DSP was
starting; (3) an I2S handler that only flipped the sign → it sounded, so the
interrupt and the return were right; (4) the whole handler with constants → it
sounded. The fault was in the test: the start button on the Jaguar is `SELECT`,
not `A`, and the game had never started.

## The road: one line, one object

Here the Jaguar does in one go what costs the Mega Drive a table and the Amiga
a copper list. The Object Processor walks the list **on every scanline**, so a
bitmap one line tall, with its own X, **is** a per-line scroll entry.

The image is the same one the Mega Drive gets —512 wide, with the four bands
drawn inside it— and it is painted once on entering the level. The stripes run
by rotating the colour table: twelve words to the CLUT per frame.

The object's address jumps eight pixels at a time —what a 64-bit phrase
measures at eight bits per pixel— and the remainder is supplied by the object's
X, which does go per pixel.

**224 objects are not needed.** The corner means many consecutive lines shift
by exactly the same amount, and an object can be several lines tall: the engine
walks the screen from top to bottom, joins the lines that share a shift and
puts out one object per segment. From 224 it comes down to a few dozen.

### And why the video interrupt was needed

Even so, driving, this machine does not reach 60: a road frame takes a little
more than one vertical blank. Since the chip **spends** the list as it draws it
(trap 2 above), the vertical blank that went by while the game was thinking
found a used-up list and drew nothing. Measured in Virtual Jaguar, counting how
many frames out of sixty carry an image:

| how the list is dumped | you see |
|---|---|
| once per turn of the loop, 224 objects | 33% |
| joining the lines that shift the same | 50% |
| and dumping it twice | 66% |
| and three times | 75% |
| **from the video interrupt** | **100%** |

Dumping more often from the loop covers vertical blanks, but never the last
one: **the one that goes by while the game is thinking**, which by definition
is when the loop is not looking. Only an interrupt covers that one.

Three things that were hard, all three measured:

**TOM does not interrupt by autovector.** It puts out its own vector number,
64, which on the 68000 is address `$100`. Putting the routine only there gives
100%; putting it only on the level 2 autovector (`$68`) sends the machine off
for a walk and nothing is seen. `arranque.S` was still turning the interrupt
off with `VI = $FFFF`; now `np_video.c` turns it on when entering, and only
when driving.

**The list the interrupt dumps cannot be the one the game writes**: it would
catch it half-made, without the `STOP` at the end, and the chip would run off
the end of the list. That is why there is a third copy, the master one. The
game finishes its own in peace and only then, with the interrupt closed for a
moment, passes it over whole.

**And waiting for the vertical blank by watching the line counter stops
working.** Between the line it interrupts on and the end of the count there are
seventeen half lines, and dumping the list takes longer than that: by the time
the routine let go, the counter had already wrapped round, so the loop never
got to see it pass and sat spinning frame after frame. The picture showed whole
and still —100% of frames with the same photo— because the game was not moving
a single step. Now the loop waits for **a flag the routine sets**, and there is
no window to miss.

As a bonus, the game runs faster: it no longer spends two whole vertical blanks
waiting for nothing.

## What it does not do yet

- **Making use of the 16-bit DACs.** The samples already sound —*Digital
  samples*, above, covers it— but they go as they go on the other machines: one
  byte per sample, unsigned and at the handler's 20,774 Hz. The DACs are
  **16-bit and stereo**, so real voices and percussion would fit here, and this
  would be the only one of the seven where that shows.
- **More than one parallax layer.** One is drawn; more would fit, because each
  layer is just one more object in the list.
- **Direct colour.** The table's 256 are used. The Jaguar can do 16 bits per
  pixel, and it would be the only one of the seven where the PNGs would not
  have to be cut down: they would be seen as they are.
- **The GPU** is untouched. For a platform game it is not needed, but there it
  is. The **DSP** is used: it is the one that plays the sound, and the section
  above covers it.
