# The Atari ST inside (and what NeoPlat does with it)

This is what you need to know about the hardware to make sense of the generated
code, and the first place to look when something looks wrong in the emulator.

## The computer in four lines

| | |
|---|---|
| CPU | Motorola 68000 at 8 MHz |
| RAM | 512 KB on a 520 ST, 1 MB on a 1040 |
| Video | Shifter: **bitplanes**, 4 in low resolution |
| Colour | 512, **16 on screen** |
| Screen | 320 × 200 |
| Sound | YM2149: three square waves and one noise |
| Keyboard | a separate 6301 (the IKBD) that talks over a serial line |

It is the most spartan of the kit's seven machines, and that is what makes it
the most interesting: it carries **the same processor** as the other six and
has nothing to lend it a hand.

- **it has no sprites**;
- **it has no blitter** (the Mega ST's came later, and here things are done as
  if it did not exist: that way the game runs on any ST);
- **it has no hardware scroll**. The screen starts wherever it is told, but
  only to a precision of 256 bytes, which is a line and a half: no use for
  moving the stage.

Everything that moves is moved by the 68000 by hand. The rest of this page
comes out of that.

## The screen: 200 lines and not 224

Here lies the only real difference between the ST and the kit's other machines.
The rest show 224 lines; the ST shows 200.

The engine is the same for all of them —otherwise it would not be the same
game— so what is done is to **show a window onto the same world**: the
scoreboard takes the top 24 lines, just as on the Amiga, and the game is left
with 176 instead of 200. The 24 left over are taken **all off the top**, not
twelve above and twelve below: in a platform game the floor is at the bottom,
and cropping that shows far more than cropping sky. That way the bottom edge
falls exactly where it does on the other machines.

The simulation does not notice: `cam_x` and `cam_y` are the same on all seven
machines, and that is why the C/JS parity test still holds.

## How NeoPlat draws

```
screens      two of 320 × 200 and 4 bitplanes, alternating (32,000 bytes each)
stage        moves 16 pixels at a time, by moving memory
actors       drawn to the pixel, shifted bit by bit and clipped by mask
scoreboard   the top 24 lines of the same screen, from a separate copy
```

Three decisions, and none of them is assumed: they are measured (what with is
explained further down).

**1. Two screens.** Drawing happens on the one not being shown and at the end
of the frame the address the Shifter reads is changed, which really is free.
Without this the actors flicker: between erasing them and drawing them again
half a frame goes by and the beam passes over. Since each screen is shown every
other frame, the one due to be drawn is **two frames behind**, and that is why
each one keeps its own note of which piece of the world it has inside and which
actors have to be erased.

Both are aligned to 32 KB and 32 KB apart. That is not a whim: this way both
start at an address whose bits 8 to 14 are zero and the video counter —which is
the only thing that says where the beam is when there are no interrupts— reads
the same whichever one is being shown.

**2. The stage moves 16 pixels at a time.** Drawing a tile at any old `x`
forces each row's four words to be shifted bit by bit, and that costs four
times as much as copying them as they are. With the view stuck to the tile grid
the stage is copied without shifting. The actors do go to the pixel, because
there are few of them.

**3. Advancing the view moves memory, it does not repaint.** Shifting the play
area's 176 lines eight bytes to the left (about 27 KB) and painting the column
coming in comes cheaper than drawing the 240 cells again.

## How to draw an actor at any old `x`

The usual trick: put the word in the top half of a 32-bit integer and shift it
right by as many bits as needed. At the top is what goes in the group of 16
pixels where the graphic starts and at the bottom what spills into the next
one.

```c
uint32_t v = ((uint32_t)word << 16) >> shift;
left  = v >> 16;
right = v & 0xFFFF;
```

The mask works for all four planes (it is one bit per pixel, set where the
graphic covers the background), so it is shifted **once per row only**. That
allows two shortcuts worth half the work:

- if a row is transparent all the way across, it is skipped and eight writes
  with it;
- if one side of a row has nothing opaque, there is nothing to write there
  either. On a small graphic —a coin, a gem— that is half the writes.

And whatever does not depend on the plane is forced **out of the loop**:
whether it is clipped at the sides, and the mask already inverted. The inner
loop is walked 64 times per graphic (16 rows × 4 planes), and the first version
looked at everything inside it.

## Making it fit in a frame

The game **simulates at 50 steps per second**, the same as the Amiga —on the
Neo Geo, the Mega Drive, the Jaguar and the X68000 it is 60, their vertical
blank's— and **draws at 25**, which is what an 8 MHz 68000 without a blitter
gives. An ST frame is 313 scanlines and a line is 512 cycles: 160,000 cycles
per frame, 320,000 for each drawing.

### How to measure it

With no instruments and no special emulator, the way it was done when the
machine was new: **the border is set to a garish colour while drawing** and put
back to the level's when it finishes. Since the beam waits for nobody, the band
of that colour on screen measures exactly how long it took.

It is in the engine itself, behind a `#define`, and the number says **which**
piece is measured (that way the band fits whole on screen and the sum comes out
exact):

```
make CFLAGS='... -DNP_MEDIR=2'      # 1 whole frame   2 moving the screen
                                    # 3 repainting     4 actors   5 simulating
```

And to count drawn frames without touching anything: the two screens alternate
and the player moves, so two drawn frames are never identical. Counting how
many times the pixel map changes tells you the rate.

### What it took to reach 25

| | frames per second |
|---|---|
| first version | 10 |
| tiles copied long word by long word | 15 |
| whatever does not depend on the plane, out of the loop | 17 |
| **waiting for the vertical blank once per step, not once per drawing** | **25** |
| moving the screen with `movem.l` | 25, and without dropping to 16 when advancing |
| drawing split between the two steps | 25, and 17 at the busiest |

What raised it most was not the drawing: it was the order of the loop. The
first version waited for the vertical blank after each simulation step, and
that threw away a whole frame per turn. The real work —simulating twice and
drawing— fits comfortably in the two frames, but split into pieces that did not
make it to the next vertical blank in time it ate three.

Measured with the border, this is what each thing costs (median, in scanlines;
a hardware frame is 313):

| | lines | |
|---|---|---|
| simulating two steps | 31 | and not 200, as it seemed |
| repainting the background behind the actors | 84 | |
| drawing the actors | 124 | |
| **a normal frame, whole** | **280** | 89% of a hardware frame |
| moving the screen when the view advances | 242 | only when the stage advances |

One drawing frame does not fit in one hardware frame, but **the two fit in the
two**: the game simulates twice for each time it draws, so two vertical blanks
have to be waited for anyway. That is why the drawing is split into two halves,
one per step: the stage in the first and the actors in the second. Doing it all
at once, the work spilled just over one frame and cost another whole one.

**What actually comes out**: 25 frames per second on most screens, and about 17
on the ones that combine scrolling with many actors at once (the example's
level with nine coins and two enemies on screen). The simulation runs at 50
steps per second in both cases, which is what makes it the same game as on the
other six machines.

And watch out for the game's clock: **one wait per step, not one per turn**.
With a single wait, on a screen with little to draw the whole turn fitted in
one frame and the game ran at twice the speed. The clock cannot depend on how
much there is to paint.

### The 27 KB that get moved, and why they are in assembler

Moving the play area is the only thing on the ST written by hand, and it is
measured before deciding it. In C, gcc generates `move.l (a1),(a0)` **with a
displacement** —two extension words per instruction— and comes out at 8.5
cycles per byte: 27 KB is 449 lines, a frame and a half. With `movem.l`, which
moves twelve registers in one go, it is 4.8 cycles per byte and 242 measured
lines.

```
movem.l (a0)+,d0/d2-d7/a2-a6     12 + 8×12 = 108 cycles
movem.l d0/d2-d7/a2-a6,(a1)       8 + 8×12 = 104
lea     48(a1),a1                            8
dbra    d1,loop                             10
                                 ─────────────
                                 230 per 48 bytes
```

That difference is exactly what separates drawing in two frames from needing
three: 280 + 449 + 31 goes over the 626 that two frames give, and 280 + 242 + 31
does not. With the C version the game **dropped to 16 frames per second every
time the stage advanced**; with `movem` it stays at 23-25.

Going backwards you have to work from the end to the start, because source and
destination overlap. Within each block it does not matter: `movem` reads all 48
bytes before writing any of them.

### Without interrupts, how do you know where the beam is?

By looking at the video counter (`$FF8205`-`$FF8209`), which climbs from the
screen's address to the end of the last line and stays there until the next
frame. Of its three bytes the middle one is enough, since that is the one that
counts the lines: that way the read is a single one and cannot catch the
counter half-changed.

## The keyboard goes by interrupt, and it is not optional

The IKBD talks at 7812 baud and the ACIA that receives it **only holds one
byte**: if the next one arrives before the previous one is read, the previous
one is lost. And its messages are two and three consecutive bytes, that is a
quarter of a millisecond between one and the next.

Looking at it once per frame (20 ms) **will not do**: the header is lost
precisely, and the rest is read as if it were keys. Checked on the machine:
with the header lost, the joystick moves the player one time in however many.

So on the MFP only that line is left on and the mask is lowered to level 5,
which lets level 6 (the MFP) through and still blocks the vertical blank and
TOS's clocks. The game leaves the machine as it was, but without losing keys.

**And the ACIA has to be emptied before opening the interrupts.** The MFP warns
when the keyboard's line *goes down*, and that line stays down while there is
an unread byte. If TOS left one there, clearing the pending flags loses the only
warning there was going to be: it never goes down again and the controller is
dead forever. It cost a test that failed one time in two.

The IKBD sends three things mixed together:

| | |
|---|---|
| keys | the key's code, and the same plus `$80` on release |
| joystick | `$FF` (port 1) or `$FE` (port 0) followed by the four directions and the button |
| mouse | `$F8`-`$FB` and two more bytes every time it moves |

At startup the IKBD is asked to silence the mouse (`$12`) and to report the
joystick (`$14`), but the packets already on their way have to be swallowed all
the same: otherwise their two displacement bytes would be read as if they were
keys.

**The action button is a key.** The ST's joystick has a single button, and that
one jumps (and starts the game, since otherwise a one-button controller could
not get the game going). Attacking —and, with up, throwing the secondary
weapon— goes on the <kbd>X</kbd> key or on <kbd>Control</kbd>: without them,
there was no way of hitting anything on the ST. The keys the game reads are the
arrows, <kbd>space</kbd> (jump), <kbd>X</kbd> / <kbd>Control</kbd> (attack) and
<kbd>Enter</kbd> (start).

The packet's header is what says which port it comes from, and that is why with
`jugadores: 2` there is nothing to configure: **port 1** (the usual joystick
connector) is the first player and **port 0** (the mouse's) the second, so the
mouse has to come out and the other joystick go in there. The keyboard still
belongs to the first player only. In Hatari, the second joystick is not
connected by itself either: it has to be asked for with `hatari_twojoy`.

## Colours

The ST shows **16 colours out of 512**: three bits per channel,
`0000 0RRR 0GGG 0BBB`. The STE widens each channel to four bits by putting the
new bit right at the bottom, and that is why the same value looks nearly the
same on both machines.

The project's palettes are melted into a single one of 15 (the last colour is
reserved for the scoreboard). No graphic fits as it is, so the leftover colours
are swapped for the nearest one, weighted by how much each is used: it is the
same median cut the Amiga's dual-playfield mode uses. If you want to be in
charge of the colours, draw with fifteen.

## The parallax, and why it depends on the camera

The ST draws **one background layer, and only with `camara: pantallas`**. It is
not an option to be chosen: it comes out of what each thing costs.

With the screen-by-screen camera the view stands still between jumps, so the
background does too, and painting it **costs nothing**: where there was no
stage a blank tile was already being painted, and now the background's one is
painted instead. There are only three cases, and two are free:

| the cell | what is done | what it costs |
|---|---|---|
| the tile covers the whole cell | it is copied and that is that | the same as before |
| it is empty | the background's tile is copied | the same as before |
| the tile leaves gaps | background underneath and the tile on top with its mask | twice as much, and there are four cells |

To know which is which, the compiler emits one bit per graphic
(`np_tile_opaco`): 1 if it has not one transparent pixel. In a normal stage
almost every tile is one of those or empty.

With `camara: scroll` it is not drawn, and here it really is about what it
costs: the background has to go at a different speed from the stage, and
shifting memory can only move both at once. The whole screen would have to be
repainted every few pixels —322,000 cycles, two frames— and it does not fit.
The compiler warns about it.

## How it sounds

The ST's YM2149 is **the same chip as the SSG in the Neo Geo's YM2610**: three
square-wave channels and one noise, with the period in twelve bits. The only
difference is the clock (2 MHz on the ST, 4 on the Neo Geo), and the compiler
already takes care of that when converting the notes.

Writing to it is two steps: the register number to `$FF8800` and its value to
`$FF8802`. Two warnings:

- register 7 (the mixer) has its bits **the other way round**: a zero turns
  something on;
- its bits 6 and 7 are not about sound but the direction of the two ports, the
  printer's and the RS-232's. Set wrongly, the ST stops talking to them. That
  is why the mixer is always written starting from `$C0`.

## The floppy (.st)

An `.st` is a byte-for-byte copy of a 720 KB floppy: 80 tracks × 2 sides × 9
sectors × 512 bytes. Inside goes a **FAT12**, the same file system as the MS-DOS
of the day, which is the one TOS uses.

```
sector 0        the boot sector, with the parameter table (BPB)
sectors 1-5     the FAT
sectors 6-10    its copy
sectors 11-17   the root directory (112 entries)
sector 18 …     the data, in groups ("clusters") of two sectors
```

The game goes into a folder called **AUTO**: on power-up, TOS looks to see
whether the floppy has that folder and runs whatever `.PRG`s are inside it
before bringing up the desktop. It is the normal way for a game disk to boot by
itself, and there is no need to write code in the boot sector —in fact you have
to **avoid** its 256 words summing to `$1234`, which is what TOS looks at to
decide whether to run it.

Watch out for one confusing thing: although the 68000 is big endian, the
numbers in the parameter table and the directory go **backwards** (little
endian), because the format comes from the PC and Atari copied it as it was so
that disks could be exchanged.

## How a GEMDOS executable starts

The `.PRG` is simpler than the Amiga's executable: it is not loose pieces but
**one continuous block** that TOS loads wherever it fits.

```
+0   word   $601A, which is what TOS looks at to know it is a program
+2   long   how much TEXT takes up
+6   long   how much DATA takes up
+10  long   how much BSS to reserve (TOS hands it over zeroed)
+14  long   how much the symbol table takes up
+18  long   reserved
+22  long   flags
+26  word   0 = it carries a relocation table
```

The relocation table is a Digital Research invention that spends one byte per
fix-up: first a long word with the offset of the first one, and then one byte
per fix-up saying how far to advance from the previous one. A byte does not
reach 256, so the value 1 means "advance 254 and carry on correcting nothing",
and 0 closes the table.

The game starts in **user mode**, which can touch neither the Shifter nor the
sound chip, so the first thing is to ask for supervisor mode with GEMDOS's
`Super(0)`. It has one useful quirk: it leaves the supervisor stack where the
user one was, so the `addq.l #6,sp` afterwards cleans the parameters off the
right place and execution carries on as if nothing had happened.

## The road: here it does not slide, it is painted

The ST has no scroll of any kind. No planes, no copper, no line table: the
screen always starts at the same address and all there is is memory. So in a
driving game the road **does not slide**: it is drawn whole, every frame.

And it comes cheap, which is the surprising part. A line of road is five
stretches of one colour —grass, shoulder, roadway, shoulder, grass— plus the
centre line, and a stretch of one colour on an ST is identical words: 160 bytes
per line, forty long writes. The middle groups are written as they are and only
the two at the ends have to be mixed with what was there. Drawing the whole
road costs **less** than moving the stage of a platform game, which is what
forces the ST to refresh at 25 pictures per second and does not force a driving
game to.

Each line's edges are given by the engine (`np_carretera_bordes`), which is the
same place the Jaguar's come from and the one the compiler drew the Mega
Drive's and the Amiga's textures with. That is why the road lands on the same
pixel on all four.

Of the road's image the ST needs nothing: only the seven colours, to ask for
them by number. The compiler sends them in a 16×16 square
(`Sistema.carretera_como = "muestra"`), which takes up one graphic and not two
thousand.

### The traffic, and why there are two nearly identical painters

What sits on the roadway is drawn in perspective: the engine says where it
falls and how much it shrinks, and the compiler sends the graphic ready-made at
five sizes, because the ST cannot scale anything (it is covered in
[megadrive.md](megadrive.md#the-traffic-drawn-at-five-sizes-not-scaled), which
is where the sizes were decided).

That is why in `np_video.c` there are two nearly identical functions:
`np_pintar_actor`, which works the actor's size out, and `np_pintar_bloque`,
which is given it. It is deliberate, and it is measured. The clean way —a
single painter with the numbers as parameters, and `np_pintar_actor` calling
it— makes **an ordinary game go from playing 16 notes of 16 to playing 8**: of
the eight targets, this is the tightest on cycles, and what is lost in the
frame is heard in the melody. Done this way, in a game that is not about
driving the second painter is not even compiled and the usual path stays
exactly as it was.

## If something looks wrong

| what you see | where to look |
|---|---|
| blank screen and TOS comes up at the desktop | the `.PRG` is not in `AUTO/`, or the header does not start with `$601A` |
| the game hangs shortly after starting | a relocation-table fix-up that lands outside the program |
| the actors leave trails | `np_repintar_rastros`: the noted box does not cover what was drawn |
| the actors flicker | drawing is happening on the screen being shown |
| the controller does not respond | the ACIA was left with an unread byte and the MFP does not warn again |
| the stage jumps oddly as you walk | `np_correr` and the columns coming in: the view and the memory do not line up |
| swapped colours | there are 15: look at `ngplat compilar`'s warning, which says how many have been approximated |
| the background does not show | it is only drawn with `camara: pantallas`; with scroll it does not fit |
| the game runs at twice the speed | a vertical-blank wait is missing per simulation step |

## Checking it in an emulator

`tests/emulador_st.py` puts the floppy into an emulated ST (Hatari, with
EmuTOS) and watches what comes out of the screen and of the YM2149. Neither the
core nor the TOS comes in the repositories:

```
https://buildbot.libretro.com/nightly/linux/x86_64/latest/hatari_libretro.so.zip
https://sourceforge.net/projects/emutos/files/emutos/1.4/
```

The core goes in `/usr/local/lib/libretro/` and the TOS image in
`/usr/local/share/neoplat/tos.img`.

Two things that were hard to find:

- **Hatari does not connect the pad to the ST's joystick unless it is told
  to.** It has to be asked for option by option (`hatari_mapper_*`). Without
  them nothing arrives, neither keys nor joystick, and the game looks hung when
  what is happening is that nobody is talking to it.
- **The core will not start twice in the same process**: the second time it
  hangs. That is why the kit's tests launch it as a separate program.
