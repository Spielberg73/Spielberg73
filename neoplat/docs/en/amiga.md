# The Amiga inside (and what NeoPlat does with it)

This is what you need to know about the hardware to make sense of the generated
code, and the first place to look when something looks wrong in the emulator.

## The computer in four lines

| | |
|---|---|
| CPU | Motorola 68000 at 7.09 MHz |
| Chip RAM | 512 KB on an A500 (the only kind the chips can see) |
| Video | Denise: **bitplanes**, up to 6 (64 colours) |
| Copper | a coprocessor that changes registers on a given line |
| Blitter | copies and combines memory at full speed, with mask and shift |
| Colour | 4096, **32 on screen** with 5 bitplanes |
| Sound | Paula: 4 channels of digital sound over DMA |

It is the most different of the seven machines: **it has neither tiles nor
enough hardware sprites** for a game like this. It has a bitmap that can be
moved whole in hardware and a blitter that draws on top of it.

## How NeoPlat draws

```
bitmap       704 × 256 or 352 × 512 pixels, 5 interleaved bitplanes (chip)
scroll       in hardware: the pointers are moved and BPLCON1 does the rest
stage        only the column of tiles coming in gets drawn
actors       with the blitter, clipped by their mask
scoreboard   its own 320 × 24 band, hooked on by the copper
```

### The bitmap's shape

It always takes the same room —22 KB per plane— but it can be laid out two
ways, and **the game chooses, not you**: the tallest level it has decides.

| shape | cells | what for |
|---|---|---|
| 704 × 256 | 44 × 16 | the usual: a game you cross from left to right |
| 352 × 512 | 22 × 32 | a game you **climb** (`vista: cenital`, or any level more than 16 cells tall) |

In the wide shape the map is **twice as wide as the screen** on purpose. As the
camera advances, the 16-pixel column coming in on the right gets drawn; when
the camera nears the end of the map it starts again on the left, repainting
what is visible (it costs a frame, and happens every 350 pixels of scroll).

In the tall shape there is no window worth having: two cells would be left over
at the sides, so the camera would spend its time repainting the whole screen.
That is why the level has to **fit whole across** (22 cells), and then the
stage is painted once on entry and never touched again: while you climb, the
vertical scroll is nothing but moving the bitplane pointer.
`ngplat comprobar --sistema amiga` says so before compiling if the level does
not fit.

Downwards there is no window in either shape —the vertical scroll is the
pointer and nothing else— so the level's height cannot exceed the bitmap's
height: 16 cells in the wide shape, 32 in the tall one.

**Interleaved** means each row carries the five bitplanes' five words one after
another, instead of having the five planes one behind the other. That way the
blitter draws a whole tile in a single pass. That is why the bitplanes' modulo
is `NP_PASO_FILA - 40` and not `NP_BYTES_FILA - 40`.

Before drawing the actors, the background is **repainted** where they were on
the previous frame (`np_rastros`), which is what stops them leaving trails.

## The scoreboard and the copper

The Amiga has no text plane that can be put on top, so the scoreboard lives in
its own 320 × 24 bitmap and it is the copper that changes the bitplane pointers
on reaching line 24:

```
line $2C   the visible part starts; pointers -> np_hud_bitmap
line $44   copper WAIT; pointers -> np_bitmap + (cam_y + 24) rows
line $10C  the screen ends
```

From there up you see the scoreboard and from there down, the game. Since the
game's pointers start 24 rows further down, the effect is the same as an
overlaid scoreboard: row N of the screen shows row `cam_y + N` of the world.

Colour 0 also lives in the copper list, and the engine changes it at the start
of each level to the `fondo:` you gave it.

## The blitter

Two uses, both in `np_video.c`:

**Copying a stage tile** (`np_blit_tile`): A → D, without shifting.

```
BLTCON0 = $09F0     use A and D, minterm $F0 (D = A)
BLTSIZE = 80 rows × 1 word    (16 pixels × 5 planes)
BLTDMOD = 88 - 2              skip to the bitmap's next plane
```

**Drawing a clipped actor** (`np_blit_bob`): the classic *cookie cut*.

```
BLTCON0 = $0FCA | shift        use A, B, C and D
                               minterm $CA: D = (A and B) or (not A and C)
BLTSIZE = 80 rows × 2 words    two, because shifting spills out of one
BLTALWM = $0000                the extra word is cancelled
BLTAMOD = BLTBMOD = -2         they read two words per row and advance one
```

A is the mask, B the graphic and C the background that was already there: where
the mask is 1 the graphic shows and where it is 0 the background shows. That is
why the graphics are stored **with their mask beside them**.

The mask is stored **repeated five times per row**, one per bitplane. It sounds
wasteful (160 bytes instead of 32) but it is what makes the mask advance in step
with the interleaved graphic and lets the blitter do all five planes in a single
pass instead of five.

## Colours

An Amiga colour is a word `0000 RRRR GGGG BBBB`: **four bits per channel**. It
is in `gfx_amiga.amiga_color()`.

How many colours there are depends on the mode (`amiga:` in the `game.yaml`).
On the A1200 it is the same two modes with twice the bitplanes each, and they
are also called `256colores` and `16colores`:

| | `32colores` | `8colores` |
|---|---|---|
| Bitplanes | 5, one single plane | 6, split 3 and 3 |
| Game colours | 31 (0 is the background, 31 the scoreboard) | 7 (0 transparent, 7 the scoreboard) |
| Parallax colours | — | 7 (registers 9 to 15) |
| Parallax | not drawn | yes, in hardware |

In both cases `fusionar_paletas()` puts all the project's palettes into one,
reusing repeated colours. The difference is what happens when they do not fit:
with 32 it gives an error (it has never happened with ordinary graphics), and
with 8 it **cannot**, because no real graphic fits in seven colours. There the
usual thing for such cases is done: **median cut**. How many pixels use each
colour is counted, the cloud of colours is split into seven boxes (always by
the channel that varies most and at the halfway point of the weight, not of the
number of colours) and each box keeps its average colour; then each original
colour is swapped for the nearest of the seven. It is deterministic, and
`ngplat compilar` warns how many colours it has had to approximate.

## The Amiga 1200 and AGA

The A1200 is the same machine with the **AGA** (or AA) chipset, and in NeoPlat
it is a separate target —`ngplat compilar --sistema amiga1200`— because its
floppy demands an AGA machine: on an A500 the eight bitplanes do not exist and
nothing would be seen. The engine is the same (`engine/amiga/`, with `NP_AGA`
set from `gamedata.h`); what changes are numbers:

| | Amiga (OCS/ECS) | Amiga 1200 (AGA) |
|---|---|---|
| CPU | 68000 at 7 MHz, `-m68000` | 68EC020 at 14 MHz, `-m68020` |
| Bitplanes | 5, or 3+3 in dual playfield | **8**, or 4+4 |
| Colours at once | 32, or 7+7 | **256**, or 16+16 |
| Per channel | 4 bits (4096 in all) | **8 bits** (16.7 million) |
| Chip RAM | 512 KB | 2 MB as standard |
| 16×16 graphic | 160 bytes + 160 of mask | 256 + 256 |

Three things have to be told to the chipset, and all three are in
`np_montar_copper()`:

**1. Eight bitplanes do not fit in the usual DMA.** In low resolution, with
16-bit reads, six fit and only just. AGA can read **32 bits** at a time
(`FMODE` register, bit 0): each read brings twice the pixels, slots are left
over and all eight fit. In exchange the DMA starts eight *color clocks* earlier
(`DDFSTRT` = $30 instead of $38) and makes ten 32-pixel reads instead of twenty
16-pixel ones (`DDFSTOP` = $C0). The 40 bytes per row and plane are the same,
so the modulos do not change.

**2. The number of bitplanes no longer fits in three bits.** `BPLCON0` has
BPU2-0 in bits 14-12 and AGA adds **BPU3 in bit 4**: eight planes is `1000` in
binary, that is bit 4 set and the other three at zero. And **`ECSENA`** is
needed (bit 0 of `BPLCON0`): without it, `BPLCON3` and `BPLCON4` do nothing and
the palette stays at the usual 32 colours.

**3. The 256 colours do not fit in the registers.** There are still 32, and
they are chosen eight at a time in **banks** with bits 15-13 of `BPLCON3`. And
since the colour register is 12 bits but the colour is 24, **each colour is
written twice**: first the top four bits of each channel and then, with the
`LOCT` bit (bit 9 of `BPLCON3`) set, the bottom four. That is 16 passes —eight
banks by two halves— of one `BPLCON3` and 32 colours: 528 copper instructions,
about nine scanlines, and there is plenty to spare before the picture starts.

In dual playfield, the back plane uses colours **16 to 31**, and that is said
with `PF2OF` (bits 12-10 of `BPLCON3`, value `100`).

### The scroll, which is what breaks

Reading 32 bits at a time, the DMA **does not look at the bitplane pointer's
low bits**: moving it two bytes at a time would do nothing half the time and
the scroll would be seen in jerks. So the pointer jumps **32 pixels at a time**
(four bytes) and the remainder —up to 31— is supplied by `BPLCON1`'s fine
scroll.

On OCS that register is four bits per plane (0 to 15 pixels). AGA extends them:
bits 9-8 (front plane) and 11-10 (the back one) are the part that did not fit,
so it reaches 63. It is in `np_scroll_fino()`.

Measured on an emulated A1200: walking at 1.4 pixels per frame, the stage moves
**1, 2, 1, 1, 2…** exactly as on an A500. If the fine scroll did not work you
would see `0, 0, …, 0, 32`.

### How it was checked that AGA really is turned on

Two measurements, because "it looks nice" proves nothing:

- **Eight bitplanes**: the scoreboard is drawn in colour **255**, and in the
  generated palette white is *only* at that index. If the screen had five
  bitplanes, 255 would not exist and the scoreboard would come out another
  colour. It comes out white.
- **Eight bits per channel**: two cells of `#101010` and `#1F1F1F` are
  compiled, which on OCS round to `#111111` and `#222222`. On the emulated
  A1200 the second comes out **`#1F1F1F`**, not `#222222`: the bottom four bits
  (the ones `LOCT` writes) are reaching the screen.

Both are in `tests/test_sistemas.py`, along with the one that boots the floppy
on an emulated A1200 and the one that measures the dual-playfield parallax.

## The CD32: the same A1200 in a console

Inside there is nothing new: 68EC020 at 14 MHz, AGA, 2 MB of chip RAM. It is an
A1200 with no keyboard, no floppy drive and a CD reader. That is why
`--sistema cd32` **does not recompile anything different**: the executable
inside the CD is byte for byte the same as the one on the A1200's floppy
—there is a test that checks it—. What changes is two things on the outside.

### The wrapper: an ISO 9660

The CD32's Kickstart has the CD file system inside it, so booting a CD is the
same as booting a floppy: it mounts `CD0:` and runs `S/Startup-Sequence`. Our
CD carries exactly that —the executable and a one-line `Startup-Sequence` that
calls it— and `iso.py` assembles it without depending on any installed tool.

What tells the machine that this disc is its own is two fields of the primary
descriptor:

| | what it carries |
|---|---|
| System identifier | `CDTV` (both use it, CDTV and CD32) |
| Application use area | the file system's options and, among them, the `TM` entry |

The `TM` entry is twelve big-endian bytes —`"TM"`, `0x0014`, the size and the
sector— pointing at the **marker file**. And the disc ends up like this:

```
 0-15   system area, blank
 16     primary descriptor (with the TM entry)
 17     the same descriptor again
 18     end of the descriptor set
 19     path table in big endian   (the one the Amiga reads)
 ...    the same in little endian  (the one everyone else reads)
 ...    CD32.TM
 ...    the directories and the files
```

It is the same shape ISOCD used, the tool the real CD32s were made with;
NeoPlat writes it from scratch and the tests read it back with the standard in
hand (and, if it is installed, with a third-party ISO library).

### The marker: 2048 bytes that are not ours

`CD32.TM` is a Commodore sector, and without it a real console **does not boot
the disc**. It cannot be distributed with the kit, just as a Kickstart cannot,
so whoever compiles puts it in:

```bash
make MARCA=/wherever/you/have/it/CD32.TM     # or leave it next to the Makefile
```

Without the marker the ISO is generated all the same, it is valid and it reads
on any computer —but it does not boot by itself, and the compiler says so
instead of keeping quiet. Before putting it in, `iso.py` checks that it is 2048
bytes and that its SHA-1 fingerprint is the right one: a wrong file gives a
clear error instead of a mute CD.

### The controller

The CD32 has no keyboard, so everything has to fit on the pad. And it fits
without touching the engine: a CD32 pad plugged into the port behaves like a
two-button joystick, with **red** on the usual fire line (`CIAA_PRA`) and
**blue** on the second button's (`POTGOR`). That is exactly what
`engine/amiga` was already reading: red jumps and starts the game, blue
attacks. The other five buttons (green, yellow, play and the two track ones)
demand a shift-register protocol and are not needed: none of the eleven genres
uses more than two buttons.

## Making it fit in a frame

A PAL Amiga gives **50 frames per second, and each frame is 312 scanlines**: if
what has to be done does not fit in 312, a frame is lost and the game runs at
half speed. With five bitplanes in low resolution the video DMA takes a good
share of the chip memory accesses, so there is less room than it looks.

Measured on an emulated A500, playing (lines per frame):

| | at first | now |
|---|---|---|
| simulating (`np_world_step`) | 76 | 76 |
| repainting the background behind the actors | 70 | 34 |
| drawing the actors | 33 | 33 |
| scoreboard | **184** | 2 |
| stage, scroll, sound and controller | 8 | 8 |
| **total** | **~370** | **~153** |
| **speed** | **25 fps** | **49 fps** |

The two things that fixed it:

- **The scoreboard only repaints what changes.** Writing into the bitmap is
  done by the CPU byte by byte (8 rows × 5 bitplanes per character), and
  repainting `SCORE 000000 … LIVES 3` whole cost more than half a frame, 50
  times a second, to leave it exactly as it was. Now the fixed words are
  written once and each number only when it changes: on a normal frame nothing
  is written.
- **A background tile is repainted once only.** The actors travel together (the
  coins, three at a time) and their rectangles share tiles; one bit per bitmap
  tile is enough to avoid repeating the work. Along the way a `+1` was
  corrected that repainted a column and a row of tiles the actor did not touch.

### What each thing costs

Measured inside the emulated A500, counting scanlines with an accumulating
clock (the hardware counter resets each frame, so subtracting it bare gives
backwards numbers as soon as the measurement crosses a frame):

| | lines |
|---|---|
| an opaque tile (`np_blit_tile`, 16×16, 5 planes) | **2.20** |
| a tile clipped by mask (`np_blit_bob`) | **4.07** |
| repainting the whole screen, 21 × 15 tiles | **950** |
| the same asking for the tiles column by column | **683** |
| a game frame, running | **122** on average, **272** at worst |
| **what the machine gives** | **313** |

Two things can be read there:

- A masked blit costs **twice** what an opaque one does: it reads three places
  (mask, graphic and background) and writes one.
- Of the 950 lines to repaint the screen, **267 were not the blitter**: they
  were the
  32-bit multiplications in `np_tile_gfx_at()`, one per tile, which on a 68000
  are done in software. Asking for the column in one go with
  `np_tile_gfx_column()` brings them down to 683, **28% less**. It is the same
  trap that was found on the Neo Geo, and `np_columna()` already works this
  way: in the assembler the compiler puts out, the inner loop went from one
  call per tile to a `movew %a2@+,%d0` reading from the array, with a single
  call per column.

### Why the parallax is not drawn with the blitter

The natural question is: if the background is already drawn with the blitter,
why not draw the parallax layers too and keep 32 colours throughout? Because it
does not fit, and not by a little:

The example's two layers take up 21 columns × 10 rows of tiles = **210 masked
tiles** per frame, because they move at a different speed from the hardware
scroll and have to be redrawn whole. At 4.07 lines each that is **855 lines**.
And on top of that the stage tiles that fall on that band have to be repainted:
210 more, opaque, **456 lines**.

**1,311 lines of parallax against a budget of 313.** With the 122 the game
already spends, the frame would come out at about 1,430: **4.6 frames**, that
is about 11 fps instead of 50.

And it is not a matter of tuning the code: the floor is the DMA. 210 tiles × 16
rows × 5 planes × 4 accesses is 67,200 blitter accesses, and measured, the
blitter gives about 79 accesses per line with the screen on. That is 850 lines
whatever you do.

With the room that really is there (313 − 272 for the worst frame ≈ 40 lines,
or about 190 if you only look at the average) **between 10 and 46 masked tiles
per frame** fit: a strip two rows tall. Not enough for a background layer.

### The real parallax: dual playfield

Since the blitter cannot do it, the parallax is done by the **video hardware**,
which comes free. OCS knows how to split the six bitplanes into two independent
planes of three (`BPLCON0` bit 10, `DBLPF`): the odd ones (BPL1, BPL3, BPL5)
make the front plane and the even ones (BPL2, BPL4, BPL6) the back one. Each
has:

- **its own fine scroll**, in `BPLCON1`: bits 0-3 move the odd planes and 4-7
  the even ones. That is why in 32-colour mode the same value has to go in both
  nibbles, and here it does not;
- **its own modulo**, `BPL1MOD` for the odd ones and `BPL2MOD` for the even
  ones, which lets the two bitmaps have different widths;
- **its own pointers**, so the coarse scroll is independent too.

In NeoPlat the front plane is the game (colours 0-7) and the back one the
parallax (colours 8-15). The back plane is painted **once on entering the
level**, repeating the layer's graphic across the whole bitmap; from then on
moving it costs writing four words in the copper list: `np_mover_fondo()` puts
the coarse scroll in the pointers and returns the fine one's four bits. Zero
blits per frame, zero lines of budget.

The price is the colours (7 and 7 instead of 31) and **a single layer**: if the
level has several, the first is drawn and `ngplat` says so.

With graphics made for something else the compiler has to approximate colours
and it shows. To see the mode as it should look there is a set of graphics made
for it:

```bash
ngplat nuevo micueva --estilo hierro
```

It comes with `amiga: 8colores` set, six counted colours in the front plane and
a background layer 256 px wide (which is what fits in the 384 of room the back
plane has to run before going back to the start). The ready-made example is in
`examples/cueva-de-hierro/`.

### Changing screen

With `camara: pantallas` the view does not slide: it jumps 320 pixels at once.
That forces the stage's twenty columns to be repainted in one frame, and at
2.20 lines per opaque tile that is about **620 lines** against the 313 a frame
gives: two or three frames lost right at the screen change. It shows, but it is
the moment the whole screen changes anyway, which is what these games did.

It could be avoided: the bitmap has 44 columns and a screen is 20, so while the
camera is standing still there would be room to draw the next screen little by
little. It is not done.

### How to measure it

The Amiga's clock for this is the screen's own beam: `VPOSR` and `VHPOSR` say
which line it is on. Reading the line before and after each part gives what it
costs, and the sums come out in the same unit as the budget (312 lines). Two
warnings:

- the counter goes back to zero each frame, so **anything lasting more than 312
  lines is under-measured**: if the numbers do not add up, that is why;
- to measure a single function, calling it 100 times in a row and dividing
  gives a far cleaner figure than measuring it once.

## The joystick, and the second button

The Amiga's joystick is quadrature: up and down come out of an *xor* of two
bits of `JOY1DAT` (the right-hand port) or `JOY0DAT` (the mouse's, where the
second pad goes). **Fire** is in CIAA_PRA —bit 7 on the right-hand port, bit 6
on the mouse's— and the **second button** in POTGOR, bits 14 and 10; to read it
you must have written `POTGO = 0xFF00` beforehand.

| | |
|---|---|
| fire | jump **and** start the game |
| second button | **action**: attack and, with up, throw the secondary weapon |
| mouse button | start, in one-player games (in two-player that port is the second player's) |

Fire doubling as start is what makes it possible to play with a single-button
pad: you start and jump with it, and the only thing lost is the attack. Start
is only looked at on the title screen and at the end of the game, so having it
stuck to jump does not get in the way while playing.

## How it sounds

Paula has four channels that read a wave from chip RAM over DMA and repeat it
endlessly. To give a note you do not need a long sample: a **two-byte square
wave** (+64 and −64) and changing its period is enough, which is exactly what
the Neo Geo's SSG and the Mega Drive's PSG do. So those three play exactly the
same notes, and the other four the same ones with whatever wave they have.

```
channel 0 -> melody        channel 1 -> accompaniment
channel 2 -> effects       channel 3 -> noise (percussion, with a 16-byte table)
```

The period is worked out by the compiler with `periodo_paula(hz, muestras=2)`:
`3546895 / (2 · hertz)`, with a minimum of 124 (below that the DMA cannot keep
up). With two samples the 30 to 8000 Hz notes the kit accepts fit with room to
spare. Paula's volume goes from 0 to 64; the kit's, from 0 to 15.

The tests listen to what comes out of Paula on the emulated A500 and check that
they are the `game.yaml`'s notes, one by one: see [sonido.md](sonido.md).

## The floppy (.adf)

An `.adf` is a byte-for-byte copy of an Amiga floppy: 80 cylinders × 2 sides ×
11 sectors × 512 bytes = **901120 bytes**. It is what the emulators eat
(FS-UAE, WinUAE, Amiberry), the Goteks and a real Amiga's ADF loaders.
`tools/ngplat/adf.py` assembles the lot, with nothing installed:

```
blocks 0-1     bootblock: "DOS\0", its checksum and the code that starts
               AmigaDOS (it looks for dos.library in the ROM and hands over)
block 880      the disk's root: volume name, hash table and where the bitmap is
block 881      bitmap: one bit per block, 1 if it is free
the rest       the files' headers and data
```

Inside go the executable and a one-line `s/startup-sequence` that launches it.
On power-up the Amiga reads the bootblock, starts AmigaDOS, mounts the disk,
runs the startup-sequence and you are playing: **no Workbench needed**.

### The bootblock has to say the disk boots by itself

The bootblock's code does two things, and the first looks cosmetic but is not:

1. it opens `expansion.library` and sets the **`EBB_SILENTSTART`** bit (bit 6
   of `eb_Flags`), which tells the system that the floppy boots on its own;
2. it looks for `dos.library` in the ROM and hands over control.

Without the first step —AmigaDOS 1.x's short bootblock, which is only the
second— the system boots in normal mode and **its shell never gets as far as
running the game**: it stops at `BosqueMagico: file is not executable`. Checked
on an emulated Amiga, and checked too that it is that exact bit: setting 5 or 7
instead of 6, it does not boot. It is the difference between the floppy working
and not.

**OFS** (*Old File System*, `DOS\0`) is used on purpose, not FFS: it is the
only one that boots on a Kickstart 1.3 without putting the file system on the
disk itself. It spends 24 bytes of header on each block, so 488 bytes of data
fit per block instead of 512; in exchange it boots on any Amiga.

Three details that have to be right or the Amiga rejects the disk:

- **The bootblock's checksum** is different from the rest: a carry-wrapping sum
  of its 1024 bytes, inverted. The other blocks' is the sum of the 128 long
  words with the sign flipped, so that the whole block sums to zero.
- **A file's data block table** is filled in **from the end towards the
  start**. If the file goes over 72 blocks (35 KB), the next ones go in chained
  *extension blocks*.
- **Names are stored in a hash table** of 72 entries
  (`hash = (hash · 13 + letter) & 0x7FF`), with a chain for collisions.

The disk always comes out identical byte for byte (the dates are fixed), so two
compilations of the same game give the same `.adf`.

## How an AmigaDOS executable starts

Here there are no fixed addresses: an executable is a list of pieces (*hunks*)
the system loads wherever they fit, plus a table saying which long words have
to be fixed up with the real address. NeoPlat generates two hunks:

```
HUNK_HEADER    how many hunks there are and how big each is (both, HUNKF_CHIP)
HUNK_CODE      code, constants and variables with an initial value
HUNK_RELOC32   what to fix up, and which hunk each address belongs to
HUNK_END
HUNK_BSS       what has to be reserved (the bitmap) — it arrives zeroed
HUNK_END
```

Both hunks are asked for in **chip RAM**, which is the only kind the copper,
the blitter and Paula can reach.

This is done by `tools/ngplat/hunk.py` (which is copied into the project as
`hacer_ejecutable.py` and needs nothing installed): it reads the sections of
the ELF the linker puts out, takes the relocations `ld --emit-relocs` leaves
and separates the ones pointing at the code from the ones pointing at the BSS.
To be able to tell them apart, `amiga.ld` links the two areas at very distant
addresses (`$00000000` and `$40000000`): looking at each reference's value is
enough.

Execution starts at the **first byte of the first hunk**, and the linker script
takes care of that: `_start` goes there, which calls `main()` and then sits in
a loop. The game keeps the whole machine (it turns off the interrupts and the
DMA in `np_amiga_init`) and does not give it back: you leave by switching off
or resetting, like the games of the day.

## The road: the copper paints it line by line

In a driving game (`vista: carretera`) the Amiga does something the Mega Drive
cannot, and in exchange cannot do what the Mega Drive does.

The roadway in perspective comes ready-made from the compiler —512 × 224— and
is painted **once** into the back plane at the start of the level. After that,
each frame only fills in the copper's section: for each screen line with road,
one wait and six writes.

- `BPL2MOD`: how much the image shifts from one line to the next. The modulo is
  added to the pointer at the end of the line, so writing it here moves **the
  one below**.
- `BPLCON1`: the loose pixels that do not fit in the modulo (0 to 15).
- and **four colours**: grass, shoulder, roadway and centre line.

### On AGA it reads 16 at a time, and that is not an oversight

The A1200 and the CD32 read the bitplanes **32 bits at a time** (`FMODE`): half
the DMA accesses, which is what allows eight bitplanes. Driving, no.

A plane's pointer does not move pixel by pixel: it jumps by what the chip reads
in one go, and what is missing up to there is supplied by `BPLCON1`'s fine
scroll. Reading 32 at a time the jump is 32 pixels, but **the margin for
delaying the plane is still 16**: the DMA starts eight clocks earlier and no
more fits there. Measured in the emulator: adding 16 to the fine scroll does
not move a single pixel. Of the 32 possible positions only half came out, and
the roadway stayed **16 pixels to the left, always** —the scoreboard, which
goes on the other plane, landed in its place; the roadway did not—.

Bringing `DDFSTRT` forward one more block leaves room for 32, but it throws the
whole screen window out. So in the road view AGA reads 16 at a time, like the
A500: the jump and the margin line up again and the roadway lands on the same
pixel on both machines, checked line by line in the emulator. Here the
bandwidth is plentiful —four bitplanes per plane, not eight— so nothing is
lost. Outside the road, AGA still reads 32 at a time.

And the sky: on AGA a colour is **twenty-four bits** and is written twice, the
top four of each channel and then the bottom ones with `LOCT`. The road branch
was writing it in one go, and the circuit's sky came out green. A level's
background colour (`NpLevel.background`) did not fit either: it was sixteen
bits and on AGA it was truncated without warning.

### Why the road is flat here

The Mega Drive gets the image with the four bands drawn inside it —four colours
per thing— and makes the stripes run by rotating the palette. That is twelve
palette slots. One plane of OCS's dual playfield has **seven**: it does not
fit.

But the copper can change a colour in the middle of the screen. So here the
image carries **one single colour per thing** and it is the beam that paints
the bands, writing on each line the shade due. Four colours instead of twelve,
and four writes per line instead of twelve per frame. The system chooses it
with `Sistema.carretera_lisa`; which band is due on each line is told by the
engine in `np_carretera_banda[]`.

### And why the dual playfield is needed

The road slides line by line and the cars do not. If they shared a plane, the
car would come out **in steps**: one slice per line with its own shift. With
two planes the road moves underneath and the car stays still on top, which is
what the Mega Drive achieves using sprites. That is why a driving game is
always compiled to dual playfield, whatever the `game.yaml` says.

### The bitmap, made to measure

A driving game gets a 512 × 256 window —what the road measures— instead of the
wide 704 × 256 one. The two planes then take 96 KB of chip RAM instead of 132.
On an A500 that is not an elegant optimisation: it is the difference between
booting and not booting. With the wide window, AROS answers **`file is not
executable`** and stops at the shell, which is what AmigaDOS says when LoadSeg
cannot find room.

### An edge detail

On a tight corner a little step of up to fifteen pixels can be seen hugging the
left edge. It is the fine scroll: it delays the plane, and those pixels of
delay have not been read —the DMA starts at the pointer— so what shows there is
the tail of the line above.

It is fixed by reading **one extra word per line**: `DDFSTRT` one step earlier
and the modulos and pointers two bytes less. It is the usual recipe, but it
touches both planes and every genre, so it has not been done along the way.

## If something looks wrong

- **Scrambled graphics or mixed-up colours**: the plane order in
  `gfx_amiga.codificar_tile()` (plane 0 = bit 0 of the colour index).
- **The actors leave trails or come out over-clipped**: the mask; check that
  `BLTAMOD` and `BLTBMOD` are still −2 and that `BLTALWM` is 0.
- **The screen shakes when scrolling**: `BPLCON1` carries `cam_x`'s low four
  bits for both playfields (the same four bits, twice).
- **It does not boot**: check with a hunk dumper that the first hunk starts
  with `_start`'s `jsr` and that both hunks are marked CHIP.
- **The emulator says the floppy is not a system disk**: it is the bootblock.
  With `xdftool disco.adf list` (from the `amitools` package) you can see
  whether the disk reads and what it has inside.
- **"file is not executable"**: the file system is fine and the file is found;
  what is missing is the bootblock's `EBB_SILENTSTART` (see above).
- **To see what is happening inside**: `make test-emulador-amiga` boots the
  floppy on an emulated A500 and leaves screenshots. To debug the game, write
  marks to a chip memory address you do not use
  (`*(volatile uint16_t *)0x180 = n;`) and read them from the emulator: after
  the takeover that area is yours.
