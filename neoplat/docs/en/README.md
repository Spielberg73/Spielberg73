# The NeoPlat manual

This is the index. The manual is **twelve documents**: the kit's
[front page](neoplat.md) and the ten chapters beside it. They are meant to be
read in an order, and this is the order.

> **The Spanish in [`docs/`](../README.md) is the original.** This folder is a
> translation, regenerated when the Spanish changes. Where the two disagree,
> the Spanish is right. The glossary that keeps this translation consistent is
> in [GLOSSARY.md](GLOSSARY.md).

`make manual` leaves both PDFs in `dist/` — `neoplat-manual-es.pdf` and
`neoplat-manual-en.pdf`. Same text, bound.

## Where to start

**If you have never used the kit**, in this order:

| | what it is | what it is for |
|---|---|---|
| 1 | [neoplat.md](neoplat.md) | **the front page**: what NeoPlat is, which machines it builds for, how to install it and what the commands are. If you only read one, read this |
| 2 | [tutorial.md](tutorial.md) | **your first game in 10 minutes**, and then a chapter per genre: a top-down game, a dungeon, a brawler, an adventure, an isometric castle, a kung-fu temple, a graphic adventure and a driving game |
| 3 | [editor.md](editor.md) | **the editor**, which is the preview itself: maps, graphics, enemies and music without leaving the browser |
| 4 | [formato.md](formato.md) | **the `game.yaml` reference**: 51 sections, every key with its default and its limits. It is the one you look things up in, not the one you read end to end |

**If what you want is to understand how it works inside**, there is a document
per machine. All of them are written the same way: the hardware in four lines,
what NeoPlat does with it, what was hard to find out, and what it still does
not do.

| | the machine | what is most its own |
|---|---|---|
| [neogeo.md](neogeo.md) | Neo Geo (AES/MVS) | the stage **has no background layer**: it is columns of sprites. And it is the only one that shrinks sprites in hardware |
| [megadrive.md](megadrive.md) | Mega Drive / Genesis | two tile planes, and the per-line scroll the road is painted with |
| [amiga.md](amiga.md) | Amiga (OCS/ECS), **A1200** (AGA) and **CD32** | no tiles and no sprites: a bitmap, the blitter and the copper. And what fits in an A500's 190 KB |
| [atarist.md](atarist.md) | Atari ST | the most spartan: **nothing** helps it, so the CPU moves everything. Draws at 25 and simulates at 50 |
| [jaguar.md](jaguar.md) | Atari Jaguar | an object list the chip walks, and sound written **for the DSP** |
| [x68000.md](x68000.md) | Sharp X68000 | the one that cost the most: the CRTC, the BG and a YM2151 |

And one that cuts across all of them:

| | what it covers |
|---|---|
| [sonido.md](sonido.md) | the notes are written **once** and seven different chips play them. The eight FM voices, digital samples and, above all, **how it is checked that it sounds**: the tests capture what comes out of the speaker and recognise the notes one by one |

## Two things worth knowing before you read

**The numbers in this manual are measured, not estimated.** When a page says a
frame costs 196,626 cycles of the 200,000 available, or that the executable is
189 KB of the 190 an A500 leaves free, it is because a test measures it and
fails when it stops being true. Where something could not be checked, it says
so.

**A frame is one step of the simulation**, and how long it lasts is set by each
machine's vertical blank: 60 per second on the Neo Geo, the Mega Drive, the
Jaguar and the X68000, and 50 on the Amiga, the A1200, the CD32 and the Atari
ST, which are PAL. A jump covers the same pixels on all seven; on the PAL
machines it takes a sixth longer to make it.

## If you are after one specific thing

| I want… | it is in |
|---|---|
| a `game.yaml` key | [formato.md](formato.md) |
| which genres there are and what each brings | [the front page, "What a game looks like"](neoplat.md#what-a-game-looks-like) |
| the editor's keys | [editor.md](editor.md) |
| how music is written | [formato.md, `musica`](formato.md#musica) and [sonido.md](sonido.md) |
| why my game does not fit in an A500 | [formato.md, `amiga_ram`](formato.md#amiga_ram-which-amiga-the-game-is-aimed-at) and [amiga.md](amiga.md) |
| what the kit does not do yet | [the front page, "State and limits"](neoplat.md#state-and-limits) |
| what changed in each version | [CAMBIOS.md](../../CAMBIOS.md) |
