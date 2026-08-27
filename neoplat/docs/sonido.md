# El sonido, y cómo se comprueba que suena

Las tres máquinas tocan las mismas notas, escritas una sola vez en el
`game.yaml`. Cada una lo hace con un chip distinto y por un camino distinto, y
las tres están comprobadas oyéndolas: las pruebas capturan lo que sale por el
altavoz y miran si las notas son las del `game.yaml`.

## Del game.yaml al altavoz

Las notas se guardan en **hercios**, que es lo único que entienden por igual
todos los chips. Cada sistema las traduce a lo que pide el suyo:

| | chip | período |
|---|---|---|
| Neo Geo | YM2610 (canales SSG) | `4.000.000 / (16 × Hz)` |
| Mega Drive | SN76489 (PSG) | `3.579.545 / (32 × Hz)` |
| Amiga | Paula | `3.546.895 / (Hz × muestras)` |
| Atari ST | YM2149 | `2.000.000 / (16 × Hz)` |

El YM2149 del ST es el mismo chip que el SSG de la Neo Geo con la mitad de
reloj: el mismo período da una nota una octava más baja, y de eso se encarga la
tabla de arriba.

Se usan tres voces: melodía, acompañamiento y efectos. En la Mega Drive, el
Amiga y el Atari ST el reproductor va en C dentro del propio juego
(`np_sound.c`); en la
Neo Geo no puede, porque el chip de sonido no cuelga del 68000: hay un Z80 con
su propia ROM (la M1) que genera `tools/ngplat/m1.py`, y el 68000 solo le manda
órdenes de un byte por el puerto `$320000`.

## Oír lo que sale

Comprobar que el driver escribe el período correcto en un registro no dice si
suena la nota: puede estar bien el período y mal el canal, el volumen, el
mezclador o el orden de las notas. Así que las pruebas escuchan.

**Mega Drive y Amiga.** El core de libretro entrega las muestras que produce el
chip emulado. `tests/libretro.py` las guarda tal cual (16 bits con signo,
estéreo entrelazado) y `tests/sonido.py` las analiza.

**Neo Geo.** No hay emulador que se pueda usar sin la BIOS de SNK, así que el
banco de pruebas del kit (`tests/maquina_neogeo.py`) monta el circuito entero:

```
68000 (Musashi)  --escribe $320000-->  Z80 (tests/z80sim.py)
                                          |  ejecuta la ROM M1 de verdad
                                          v
                                       YM2610: registros $00..$0A
                                          |  tres ondas cuadradas
                                          v
                                       la onda que se analiza
```

La ROM M1 que ejecuta el Z80 se vuelve a generar desde el `game.yaml` y se
compara byte a byte con la que hay en `build/rom`: si no fueran la misma, la
prueba estaría escuchando otra cosa.

## Reconocer una nota

`tests/sonido.py` usa el **algoritmo de Goertzel**, que es una DFT de una sola
frecuencia: mide cuánta energía hay exactamente en un hercio concreto sin
calcular el espectro entero. Se prueba solo con las notas que usa la canción
(una docena, no la escala cromática entera) y gana la que más energía tiene.

Tres detalles que hicieron falta para que la medida fuese fiable:

- **El acompañamiento suena a la vez que la melodía**, así que no se exige que
  la nota de la melodía sea la más fuerte: basta con que esté entre las dos que
  más suenan de toda la canción.
- **La captura no empieza en una nota.** La música lleva sonando desde que
  empezó el nivel, así que se prueban todos los desfases —de compás y de
  frame— y se toma el mejor. Una melodía equivocada no acierta con ninguno: las
  mismas notas barajadas sacan 5 de 16 donde la buena saca 16 de 16.
- **Los silencios se miden en relativo.** Un silencio de verdad no llega a
  cero: el chip sigue soltando algo. Se compara con lo que suena el resto de la
  canción.

Los efectos no son notas sino barridos y ruidos, así que se miran de otra
forma: se busca energía en la franja por encima de la nota más aguda de la
música, frame a frame (un efecto dura unos pocos frames y medido de golpe se
diluye). Al saltar tiene que aparecer ahí algo que antes no estaba.

## Lo que se comprueba en cada máquina

```bash
make test-emulador          # las cinco
```

En las cinco: que la pantalla de título está **callada** (la música es solo de
la partida), que al empezar el nivel suenan **las 16 notas** de la melodía del
`game.yaml`, y que al saltar se oye el efecto por encima de la música.

Comprobado que las pruebas saben fallar: con una placa muda a propósito (el
68000 no manda la orden al Z80) las tres comprobaciones fallan.

La Jaguar es el caso raro: no tiene chip de sonido, así que las ondas las hace
un programa que corre en el DSP de Jerry y que también genera el kit
([docs/jaguar.md](jaguar.md)).

## Muestras digitales

Un efecto puede ser sonido grabado en vez de notas (`muestra: sonidos/x.wav`,
ver [formato.md](formato.md)). El compilador lee el WAV sin ninguna biblioteca
(`tools/ngplat/wav.py`), lo pasa a **mono de 8 bits con signo** —que es lo que
dan estos chips— y lo remuestrea a lo que use cada máquina.

**Amiga.** Es la que menos trabajo cuesta, porque Paula ya toca sonido de la
RAM: una nota no es más que una onda cuadrada de dos bytes repitiéndose, así
que una muestra es lo mismo cambiando el bloque y el período. Va a 11.025 Hz
por el canal de efectos.

Lo único que Paula no sabe hacer es "tocar esto una vez": al acabar el bloque
vuelve a empezar por donde diga `AUDLC`. El truco de siempre es arrancar el DMA
y, en cuanto el chip ha leído el puntero, dejar en `AUDLC` dos bytes de
silencio. El "en cuanto lo ha leído" son dos accesos de DMA de audio, que
llegan una vez por línea de barrido: por eso el driver espera **dos cambios de
línea** antes de cambiar el puntero. Sin esa espera las muestras cortas se
cortan por la mitad.

**Jaguar.** Como no hay chip, la muestra es una voz más del programa del DSP:
un byte del cartucho por cada muestra de audio, sumado a las tres cuadradas y
al ruido antes de ir a los DAC. Por eso el WAV se remuestrea a los **20.774 Hz**
exactos del DSP y no hay que interpolar. El puntero lo adelanta el propio DSP;
el 68000 sólo dice dónde empieza y dónde acaba. Los detalles (y el registro que
no se podía usar) en [jaguar.md](jaguar.md).

**Cómo se comprueba.** Igual que la música: escuchando. El proyecto de prueba
(`tests/comun.py`, `proyecto_con_muestra`) pone como efecto de salto un tono
puro a **3.000 Hz y sin notas de recambio**; 3.000 Hz no es ninguna nota de la
canción ni armónico impar de ninguna, así que ahí no llega nada más. Se mide la
energía en esa frecuencia estando quieto y saltando: con la muestra suena 20
veces más en el Amiga y 8 en la Jaguar, y desactivando el camino de las
muestras en el driver del Amiga baja a 0,4. La prueba es
`tests/test_sistemas.py`, `TestMuestras`.

## Lo que aún no hace

- **Muestras digitales en dos de las cinco máquinas.** El Amiga y la Jaguar ya
  las tocan; la ROM V1 de la Neo Geo y el YM2612 de la Mega Drive pueden y
  todavía no se usan. El YM2149 del Atari ST no puede, salvo moviendo
  el volumen a mano desde la CPU, así que ahí no las habrá; el compilador avisa
  de los efectos que se quedarían mudos.
- **FM.** La Mega Drive tiene el YM2612 y la Neo Geo cuatro canales FM del
  YM2610 sin tocar; el kit usa los de onda cuadrada de las dos, que es lo que
  permite que suene igual en todas.
- **Envolventes.** El SSG y Paula pueden hacer que una nota decaiga sola; ahora
  el volumen es constante mientras dura.
