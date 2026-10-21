# Translator's glossary

The Spanish documents in `docs/` are the original. This folder is the English
translation, and this file is what keeps it from drifting: the kit's own words,
each with **one** English word, so the same thing is not called three things in
three chapters.

Add to it when a new term appears. Do not change an existing row without
changing every chapter that uses it.

## The kit's words

| Spanish | English | note |
|---|---|---|
| `game.yaml`, `ngplat` | unchanged | names, not words |
| motor | engine | `engine/core/np_world.c` is "the engine" |
| gemelo | twin | the JavaScript engine that must match the C one |
| preview | preview | it is already English in the original |
| juego de partida | starter game | the game `ngplat nuevo` writes for you |
| género | genre | |
| plantilla | template | |
| casilla | cell | a square of the **map** |
| tile | tile | a square of **graphics** |
| mapa | map | |
| actor | actor | anything that moves: hero, enemy, coin |
| bicho | enemy | |
| jefe | boss | |
| mando | controller | |
| marcador | scoreboard | the line with score, lives and time |
| cuadro de texto | text box | |
| nivel | level | |
| pantalla | screen | |
| vista | view | side, top-down, belt, isometric, road, pointer |
| vista cenital | top-down view | |
| vista de cinta | belt view | the beat-'em-up one |
| vista de carretera | road view | |
| vista de puntero | pointer view | the graphic adventure |
| escalón | step | both the stair kind and the staircase-of-values kind |
| liana | vine | |
| charca | pond | |
| cerrojo | lock | the door that asks for an object |
| guion | script | the `guiones:` kind, not a shell script |
| desgaste | drain | life that runs down by itself |
| aturdido | stunned | |
| retroceso | knockback | |
| munición | ammo | |
| pócima | potion | |
| agacharse | crouch | |
| trepar | climb | |

## Driving

| Spanish | English |
|---|---|
| coche | car |
| carretera | road |
| calzada | roadway |
| arcén | shoulder |
| hierba | grass |
| quitamiedos | crash barrier |
| volante | steering |
| respuesta (del volante) | response |
| punta | top speed |
| marcha corta / larga | low / high gear |
| trompo | spin-out |
| control de paso | checkpoint |
| franja | band |
| trazar | take a line (through a corner) |

## The machines

| Spanish | English | note |
|---|---|---|
| retrazo | vertical blank | "vblank" in code |
| haz | beam | the electron beam |
| paleta | palette | |
| plano | plane | the Mega Drive's A and B |
| mapa de bits | bitmap | |
| bitplane | bitplane | already English |
| disquete | floppy | |
| cartucho | cartridge | |
| placa | board | the arcade one |
| ciclos | cycles | |
| muestra | sample | digital audio |
| onda cuadrada | square wave | |
| onda de tabla | wavetable | |
| timbre | voice | an FM `timbres:` entry — never "timbre" |
| pista | track | a channel of music |
| banco de pruebas | test bench | the kit's own Neo Geo simulator |

## The voice

The original is short-sentenced, concrete and a little blunt: it says what was
measured and what it cost, and it uses dashes —like this— for asides. Keep
that. Two habits worth copying:

- **It never says "simply" or "just".** If something is easy, it says why.
- **Every number comes with where it came from.** "196,626 cycles of the
  200,000 the console gives" keeps the "of the 200,000": the second number is
  what makes the first one mean anything.

Numbers change shape across languages. The original writes `196.626` and
`3,2`; in English that is `196,626` and `3.2`. Sizes (`189 KB`), cycles and
pixel counts stay as they are.
