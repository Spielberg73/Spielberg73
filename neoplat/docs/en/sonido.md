# The sound, and how it is checked that it sounds

All seven machines play the same notes, written once in the `game.yaml`. Each
does it with a different chip and by a different route, and all seven are
checked by listening to them: the tests capture what comes out of the speaker
and see whether the notes are the ones in the `game.yaml`.

## From the game.yaml to the speaker

Notes are stored in **hertz**, which is the only thing every chip understands
alike. Each system translates them into what its own demands:

| | chip | period |
|---|---|---|
| Neo Geo | YM2610 (FM) | `fnum = Hz × 144 × 2^(21−block) / 8,000,000` |
| Mega Drive | YM2612 (FM) | `fnum = Hz × 144 × 2^(21−block) / 7,670,453` |
| X68000 | YM2151 (FM) | note and fraction (the chip counts in 1/64 of a semitone) |
| Amiga | Paula | `3,546,895 / (Hz × samples)` |
| Atari ST | YM2149 | `2,000,000 / (16 × Hz)` |
| Neo Geo (effects) | YM2610 (SSG channel) | `4,000,000 / (16 × Hz)` |

The ST's YM2149 is the same chip as the Neo Geo's SSG at half the clock: the
same period gives a note an octave lower, and the table above takes care of
that.

The three machines with an FM chip play the **music** on FM; the effects stay
where they were (the SSG on the Neo Geo, the PSG on the Mega Drive), so they
sound at the same time without taking each other's room. What goes to the chip
is two bytes per note, which are **exactly** the two registers it expects — the
kit does not make the driver think about anything.

### What it sounds like: `timbres:`

An FM chip does not have "a" sound: it has four sine oscillators per voice
—the **operators**— each with its own envelope, and eight ways of wiring them
together (the **algorithm**). The ones at the end of the chain are heard; the
ones before them do not sound, they **bend** the ones after, and that is where
the brass, the bells and the basses that sound like the eighties come from.

All of that, in the `game.yaml`, is one word per track:

```yaml
  musica:
    bosque:
      velocidad: 8
      timbres: [flauta, bajo]   # melody and accompaniment
      pistas:
        - "do4 mi4 sol4 mi4 | fa4 la4 do5 la4"
        - "do3 -  do3 -     | fa3 -  fa3 -   "
```

The eight the kit brings (`tools/ngplat/fm.py`):

| voice | what it is |
|---|---|
| `cuadrada` | the usual square, on the new chip: feedback at maximum and the sine broken up until it looks like a sawtooth. It is the one you get if you say nothing |
| `organo` | four sines in parallel (1, 2, 4 and 8 times the note). The safest: it is always audible |
| `flauta` | one clean sine and nothing else. It leaves room for everything else |
| `bajo` | sudden attack and short decay: it pushes and gets out of the way |
| `metal` | the "paaa" that opens up as the note comes in |
| `campana` | multipliers that do not match (1, 3, 7, 14): loose partials instead of harmonics |
| `cuerda` | slow attack: the note comes in pushing. For backgrounds |
| `pizzicato` | dry attack and no sustain: it marks the beat without covering anyone |

**One voice, three chips.** The YM2612, the YM2610 and the YM2151 store the
same six numbers per operator in the same shape, and even in the same odd order
(1, 3, 2, 4). So the kit emits **the same bytes** for all three and each driver
puts them where they go: in the OPN family the operators go four at a time and
in the OPM family, eight at a time. That they still match is checked by
`tests/test_sistemas.py`,
`test_el_timbre_de_fm_vale_igual_para_los_dos_chips`.

**A voice with no chip to synthesise it.** The Amiga, the A1200 and the CD32
have no FM, but they do know how to loop a sample, which is what a Paula
channel is about. So the compiler **draws one cycle** of the voice's waveform
—sixteen signed bytes— and the game plays that instead of the usual two-byte
square wave. The same `timbres:` that tells the YM2612 how to wire its
operators tells Paula what shape the wave has.

Sixteen samples is not a whim: it comes out of Paula. A channel repeats a cycle
of N samples at `period = clock / (Hz × N)`, and the period cannot go below
124, so the more samples the cycle has, **the sooner it runs out of high
notes**:

| samples per cycle | up to |
|---|---|
| 8 | 3575 Hz |
| **16** | **1788 Hz** |
| 32 | 894 Hz |

The highest note in the songs the kit brings is an E6 (1318 Hz), so 32 does not
reach and 16 reaches with room to spare; and sixteen holds eight harmonics,
more than enough to tell a flute from an organ. Above the limit, that note is
played with the square wave: at that height Paula's filter has already eaten
the harmonics that make the voice.

The wave reaches **64 and not 127** on purpose, which is what the usual square
wave is worth: the voice changes the shape of the wave, not how loud the music
is. At 127 the title music sounded twice as loud (2609 against 1230, measured
in PUAE) and covered the effects, which go on another channel.

What you actually hear, measured on an emulated Amiga note by note —the median
of twenty-four half-note windows, with the same song and only the voices
changed in the `game.yaml`—:

| voice | 2nd harmonic | 3rd |
|---|---|---|
| `flauta` | 0.003 | 0.004 |
| `cuadrada` | 0.217 | 0.247 |

The flute is a bare sine and the square wave brings everything, which is
exactly what they claim to be.

**The Jaguar and the Atari ST not yet.** The Jaguar could —its waves are
generated by Jerry's DSP, and a sixteen-entry table would fit— but that means
touching the DSP's program and its cycle budget, and it is not done. The ST
cannot: its YM2149 only makes square waves and has nothing to read a sample
with. Both read `timbres:` and play the same notes with what they have.

Three voices are used: melody, accompaniment and effects. On the Mega Drive,
the Amiga and the Atari ST the player runs in C inside the game itself
(`np_sound.c`); on the Neo Geo it cannot, because the sound chip does not hang
off the 68000: there is a Z80 with its own ROM (the M1) generated by
`tools/ngplat/m1.py`, and the 68000 only sends it one-byte commands through
port `$320000`.

## Hearing what comes out

Checking that the driver writes the right period into a register does not tell
you whether the note sounds: the period can be right and the channel, the
volume, the mixer or the order of the notes wrong. So the tests listen.

**Mega Drive and Amiga.** The libretro core hands over the samples the emulated
chip produces. `tests/libretro.py` keeps them as they come (16-bit signed,
interleaved stereo) and `tests/sonido.py` analyses them.

**Neo Geo.** There is no emulator that can be used without SNK's BIOS, so the
kit's test bench (`tests/maquina_neogeo.py`) assembles the whole circuit:

```
68000 (Musashi)  --writes $320000-->  Z80 (tests/z80sim.py)
                                         |  runs the real M1 ROM
                                         v
                                      YM2610: FM (channels 1 and 2)
                                         |  + SSG for the effects
                                         v
                                      the wave that gets analysed
```

The M1 ROM the Z80 runs is regenerated from the `game.yaml` and compared byte
for byte against the one in `build/rom`: if they were not the same, the test
would be listening to something else.

## Recognising a note

`tests/sonido.py` uses the **Goertzel algorithm**, which is a DFT of a single
frequency: it measures how much energy there is at exactly one given hertz
without working out the whole spectrum. Only the notes the song uses are tried
(a dozen, not the whole chromatic scale) and the one with the most energy wins.

Three details were needed to make the measurement trustworthy:

- **The accompaniment sounds at the same time as the melody**, so the melody's
  note is not required to be the loudest: it is enough for it to be among the
  two loudest in the whole song.
- **The capture does not start on a note.** The music has been playing since
  the level began, so every offset is tried —of bar and of frame— and the best
  one is taken. A wrong melody does not hit with any of them: the same notes
  shuffled score 5 out of 16 where the right one scores 16 out of 16.
- **Silences are measured relatively.** A real silence does not reach zero: the
  chip keeps letting something out. It is compared against what the rest of the
  song sounds like.

The effects are not notes but sweeps and noise, so they are looked at
differently: energy is sought in the band above the music's highest note, frame
by frame (an effect lasts a few frames and measured all at once it is diluted).
On a jump, something that was not there before has to appear.

## What is checked on each machine

```bash
make test-emulador          # all seven
```

On all seven: that the title screen sounds **as the project says** —with
`sonido: titulo:` it has to sound and without it it has to be silent—, that at
the start of the level **all 16 notes** of the `game.yaml`'s melody sound, and
that on a jump the effect is heard over the music.

Checked that the tests know how to fail: with a deliberately mute board (the
68000 does not send the command to the Z80) all three checks fail.

The Jaguar is the odd case: it has no sound chip, so the waves are made by a
program running on Jerry's DSP which the kit also generates
([jaguar.md](jaguar.md)).

## Digital samples

An effect can be recorded sound instead of notes (`muestra: sonidos/x.wav`, see
[formato.md](formato.md)). The compiler reads the WAV with no library at all
(`tools/ngplat/wav.py`), turns it into **8-bit signed mono** —which is what
these chips take— and resamples it to whatever each machine uses.

**Amiga.** The least work, because Paula already plays sound from RAM: a note
is nothing but a two-byte square wave repeating, so a sample is the same thing
with a different block and period. It goes at 11,025 Hz on the effects channel.

The one thing Paula does not know how to do is "play this once": at the end of
the block it starts again wherever `AUDLC` says. The usual trick is to start
the DMA and, as soon as the chip has read the pointer, leave two bytes of
silence in `AUDLC`. "As soon as it has read it" is two audio DMA accesses,
which arrive once per scanline: that is why the driver waits for **two line
changes** before changing the pointer. Without that wait, short samples get cut
in half.

**Jaguar.** Since there is no chip, the sample is one more voice in the DSP's
program: one byte of the cartridge per audio sample, added to the three square
waves and the noise before going to the DACs. That is why the WAV is resampled
to the DSP's exact **20,774 Hz** and there is nothing to interpolate. The
pointer is advanced by the DSP itself; the 68000 only says where it starts and
where it ends. The details (and the register that could not be used) in
[jaguar.md](jaguar.md).

**Mega Drive.** Here the 68000 cannot: the DAC is inside the YM2612 and it has
to be fed a byte every 125 microseconds. The **Z80** plays it, with a 132-byte
driver the compiler also writes (`tools/ngplat/md_pcm.py`) and which the 68000
copies into its RAM at startup. The pace is set by no timer but by the cycle
count of the loop itself: 449 out of the Z80's 3,579,545 per second, that is
**7,972 Hz**, and the WAV is resampled to that rate. Since the PSG and the
YM2612 are different chips, the music and the sample sound at the same time.
The details (starting the Z80, asking it for a sample, the 32 KB window) in
[megadrive.md](megadrive.md).

That driver is **run** in the tests (`tests/test_md_pcm.py`): the kit's Z80
emulator with the Mega Drive's memory faked on top, checking that exactly the
sample's bytes arrive at the DAC and in order, even when it crosses the 32 KB
edge. The cycle count is added up again over the already-assembled code, so
touching the loop and forgetting the count fails.

**Neo Geo.** The one whose hardware is best thought out for this: the YM2610
carries six **ADPCM-A** channels that read from a separate ROM (the V1) on
their own at 18,500 Hz with 4 bits per sample. The Z80's driver only has to
tell it where it starts and where it ends, in 256-byte blocks. The codec is the
kit's own (`tools/ngplat/adpcm.py`) and it encodes by searching: for each
sample it tries all sixteen nibbles and keeps the one that leaves the predictor
closest. Details in [neogeo.md](neogeo.md).

**X68000.** An **MSM6258**, which reads the same OKI-family ADPCM as the YM2610
—so the kit's codec works as it is— and puts it out over DMA: the 68000 only
has to tell the ROM where the data is. The rate is measured in the emulator, by
playing a known tone with each mode: **15.6 kHz**, the fastest of the five, and
the one the kit uses. (For a while that fifth rate was thought not to work: the
tone it was measured with was too high for the slow ones and folded over, see
[x68000.md](x68000.md).)

**How it is checked.** Same as the music: by listening. The test project
(`tests/comun.py`, `proyecto_con_muestra`) sets as the jump effect a pure tone
at **3,000 Hz with no fallback notes**; 3,000 Hz is not a note of the song nor
an odd harmonic of any of them, so nothing else reaches there. The energy at
that frequency is measured standing still and jumping: with the sample it
sounds 20 times louder on the Amiga, 19 on the Mega Drive, 13 on the Neo Geo, 8
on the Jaguar and more than a thousand on the X68000, and switching off the
sample path in the Amiga's driver drops it to 0.4 (and in the X68000's, to
nothing). On the Neo Geo the kit's bench **decodes the ADPCM-A** in order to
hear it, so there the whole circle closes too, from the WAV to the speaker. The
test is `tests/test_sistemas.py`, `TestMuestras`.

## What sounds at each moment

The engine decides, not each machine: `np_music_now()` (and its twin
`musicaAhora()` in the preview) look at the state of the game and return which
song it is.

| moment | what sounds |
|---|---|
| title screen | `sonido: titulo:`, if the game brings it; if not, silence |
| playing | the level's (the level's `musica:`) |
| with a boss alive on screen | `sonido: jefe:`, if it brings it; if not, the level's keeps going |
| "game over" and end of level | nothing: there, what sounds is the effect |

All seven machines and the preview call that function and limit themselves to
sending the number to the chip, so a new rule is written only once.

## Changing it without leaving the browser

`ngplat probar` + <kbd>E</kbd> opens the editor, and its **sonido** tab changes
the effects and the music with a listen button. What you hear there is the same
thing that will sound on the machine: the browser compiles the notes with
`preview/np_sonido.js`, which is the twin of `tools/ngplat/sonido.py`, and a
test compares them step by step over a batch of melodies, sweeps and noises
(`tests/test_sonido.py::TestGemeloEnJavaScript`). It is covered in
[editor.md](editor.md#sonido).

## What it does not do yet

- **Digital samples on the Atari ST.** The other six already play them; the
  ST's YM2149 cannot, except by moving the volume by hand from the CPU, so
  there will be none there. The compiler warns about effects that would be left
  mute for not carrying notes alongside.
- **Voices on the Jaguar.** The Amiga, the A1200 and the CD32 already play them
  with the wavetable (above). The Jaguar could do the same, but its waves are
  generated by Jerry's DSP in its I2S handler —a square wave of seven
  instructions per channel, twenty thousand times per second— so swapping it
  for a table means touching the DSP's program and measuring its cycle budget
  again. On the **Atari ST** there will be none: its YM2149 only makes square
  waves and has nothing to read a sample with.
- **Envelopes.** The SSG and Paula can make a note decay by itself; right now
  the volume is constant for as long as it lasts.
