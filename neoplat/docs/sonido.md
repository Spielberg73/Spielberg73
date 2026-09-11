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
| Neo Geo | YM2610 (FM) | `fnum = Hz × 144 × 2^(21−bloque) / 8.000.000` |
| Mega Drive | YM2612 (FM) | `fnum = Hz × 144 × 2^(21−bloque) / 7.670.453` |
| X68000 | YM2151 (FM) | nota y fracción (el chip cuenta en 1/64 de semitono) |
| Amiga | Paula | `3.546.895 / (Hz × muestras)` |
| Atari ST | YM2149 | `2.000.000 / (16 × Hz)` |
| Neo Geo (efectos) | YM2610 (canal SSG) | `4.000.000 / (16 × Hz)` |

El YM2149 del ST es el mismo chip que el SSG de la Neo Geo con la mitad de
reloj: el mismo período da una nota una octava más baja, y de eso se encarga la
tabla de arriba.

Las tres máquinas con chip de FM tocan la **música** por FM; los efectos siguen
por donde estaban (el SSG en la Neo Geo, el PSG en la Mega Drive), así que
suenan a la vez sin quitarse sitio. Lo que va al chip son dos bytes por nota,
que son **exactamente** los dos registros que espera —el kit no le hace pensar
nada al driver.

### Con qué suena: `timbres:`

Un chip de FM no tiene «un» sonido: tiene cuatro osciladores de seno por voz
—los **operadores**—, cada uno con su envolvente, y ocho maneras de
conectarlos entre sí (el **algoritmo**). Los que están al final de la cadena se
oyen; los de antes no suenan, **deforman** a los siguientes, y de ahí salen los
metales, las campanas y los bajos que suenan a los ochenta.

Todo eso, en el `game.yaml`, es una palabra por pista:

```yaml
  musica:
    bosque:
      velocidad: 8
      timbres: [flauta, bajo]   # melodía y acompañamiento
      pistas:
        - "do4 mi4 sol4 mi4 | fa4 la4 do5 la4"
        - "do3 -  do3 -     | fa3 -  fa3 -   "
```

Los ocho que trae el kit (`tools/ngplat/fm.py`):

| timbre | qué es |
|---|---|
| `cuadrada` | el de siempre, con el chip nuevo: realimentación a tope y el seno se rompe hasta parecer un diente de sierra. Es el que sale si no dices nada |
| `organo` | cuatro senos en paralelo (1, 2, 4 y 8 veces la nota). El más seguro: siempre se oye |
| `flauta` | un seno limpio y nada más. Deja sitio a lo demás |
| `bajo` | ataque de golpe y caída corta: empuja y se quita de en medio |
| `metal` | el «paaa» que abre según entra la nota |
| `campana` | multiplicadores que no casan (1, 3, 7, 14): parciales sueltos en vez de armónicos |
| `cuerda` | ataque lento: la nota entra empujando. Para fondos |
| `pizzicato` | ataque seco y sin sostenido: marca el compás sin tapar a nadie |

**Un timbre, tres chips.** El YM2612, el YM2610 y el YM2151 guardan por
operador los mismos seis números con la misma forma, y hasta en el mismo orden
raro (1, 3, 2, 4). Así que el kit emite **los mismos bytes** para los tres y
cada driver los mete donde van: en la familia OPN los operadores están de
cuatro en cuatro y en la OPM, de ocho en ocho. Que sigan coincidiendo lo
comprueba `tests/test_sistemas.py`,
`test_el_timbre_de_fm_vale_igual_para_los_dos_chips`.

Las máquinas sin FM leen `timbres:` y lo ignoran: tocan las mismas notas con lo
que tengan.

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
                                       YM2610: FM (canales 1 y 2)
                                          |  + SSG para los efectos
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
make test-emulador          # las siete
```

En las siete: que la pantalla de título suena **como diga el proyecto** —con
`sonido: titulo:` tiene que sonar y sin ella tiene que estar callada—, que al
empezar el nivel suenan **las 16 notas** de la melodía del `game.yaml`, y que
al saltar se oye el efecto por encima de la música.

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

**Mega Drive.** Aquí el 68000 no puede: el DAC está en el YM2612 y hay que
darle un byte cada 125 microsegundos. Lo toca el **Z80**, con un driver de 132
bytes que también escribe el compilador (`tools/ngplat/md_pcm.py`) y que el
68000 le copia a su RAM al arrancar. El ritmo no lo marca ningún temporizador
sino la cuenta de ciclos del propio bucle: 449 de los 3.579.545 por segundo del
Z80, o sea **7.972 Hz**, y a esa frecuencia se remuestrea el WAV. Como el PSG y
el YM2612 son chips distintos, la música y la muestra suenan a la vez. Los
detalles (arrancar el Z80, pedirle una muestra, la ventana de 32 KB) en
[megadrive.md](megadrive.md).

Ese driver se **ejecuta** en las pruebas (`tests/test_md_pcm.py`): el emulador
de Z80 del kit con la memoria de la Mega Drive imitada por encima, comprobando
que al DAC llegan exactamente los bytes de la muestra y en orden, incluso
cuando cruza el borde de los 32 KB. La cuenta de ciclos se vuelve a sumar sobre
el código ya ensamblado, así que tocar el bucle y olvidarse de la cuenta falla.

**Neo Geo.** La que tiene el hardware más pensado para esto: el YM2610
lleva seis canales de **ADPCM-A** que leen solos de una ROM aparte (la V1) a
18.500 Hz y con 4 bits por muestra. El driver del Z80 sólo tiene que decirle
dónde empieza y dónde acaba, en bloques de 256 bytes. El códec es del kit
(`tools/ngplat/adpcm.py`) y cifra buscando: para cada muestra prueba los
dieciséis nibbles y se queda con el que deja el predictor más cerca. Detalles
en [neogeo.md](neogeo.md).

**X68000.** Un **MSM6258**, que lee el mismo ADPCM de la familia OKI que el
YM2610 —así que el códec del kit vale tal cual— y lo saca por DMA: al 68000 le
basta con decirle a la ROM dónde están los datos. La velocidad está medida en
el emulador, tocando un tono conocido con cada modo: **15,6 kHz**, la más
rápida de las cinco, y es la que usa el kit. (Durante un tiempo se creyó que
esa quinta velocidad no funcionaba: el tono con el que se midió era demasiado
agudo para las lentas y se plegaba, ver [x68000.md](x68000.md).)

**Cómo se comprueba.** Igual que la música: escuchando. El proyecto de prueba
(`tests/comun.py`, `proyecto_con_muestra`) pone como efecto de salto un tono
puro a **3.000 Hz y sin notas de recambio**; 3.000 Hz no es ninguna nota de la
canción ni armónico impar de ninguna, así que ahí no llega nada más. Se mide la
energía en esa frecuencia estando quieto y saltando: con la muestra suena 20
veces más en el Amiga, 19 en la Mega Drive, 13 en la Neo Geo, 8 en la Jaguar y
más de mil en el X68000, y desactivando el camino de las muestras en el driver
del Amiga baja a 0,4 (y en el del X68000, a nada). En
la Neo Geo el banco del kit **descifra el ADPCM-A** para poder oírlo, así que
ahí también se cierra el círculo entero, del WAV al altavoz. La prueba es
`tests/test_sistemas.py`, `TestMuestras`.

## Qué suena en cada momento

Lo decide el motor, no cada máquina: `np_music_now()` (y su gemela
`musicaAhora()` en el preview) miran el estado de la partida y devuelven qué
canción toca.

| momento | qué suena |
|---|---|
| pantalla de título | `sonido: titulo:`, si el juego la trae; si no, silencio |
| jugando | la del nivel (`musica:` del nivel) |
| con un jefe vivo en pantalla | `sonido: jefe:`, si la trae; si no, sigue la del nivel |
| "game over" y fin de nivel | nada: ahí lo que suena es el efecto |

Las siete máquinas y el preview llaman a esa función y se limitan a mandar el
número al chip, así que una regla nueva se escribe una sola vez.

## Cambiarlo sin salir del navegador

`ngplat probar` + <kbd>E</kbd> abre el editor, y su pestaña **sonido** cambia
los efectos y la música con botón de escuchar. Lo que se oye ahí es lo mismo
que va a sonar en la máquina: el navegador compila las notas con
`preview/np_sonido.js`, que es el gemelo de `tools/ngplat/sonido.py`, y una
prueba los compara paso a paso sobre una tanda de melodías, barridos y ruidos
(`tests/test_sonido.py::TestGemeloEnJavaScript`). Está contado en
[editor.md](editor.md#sonido).

## Lo que aún no hace

- **Muestras digitales en el Atari ST.** Las otras cinco ya las tocan; el
  YM2149 del ST no puede, salvo moviendo el volumen a mano desde la CPU, así
  que ahí no las habrá. El compilador avisa de los efectos que se quedarían
  mudos por no llevar notas al lado.
- **El timbre en las máquinas sin FM.** El Amiga, el CD32, la Jaguar y el Atari
  ST leen `timbres:` y lo ignoran: tocan las mismas notas con la onda que
  tienen. Lo que se podría hacer es lo contrario de lo que parece: en vez de
  imitar la FM, generar de una vez la onda del timbre y que Paula o el DSP la
  toquen como cualquier otra muestra.
- **Envolventes.** El SSG y Paula pueden hacer que una nota decaiga sola; ahora
  el volumen es constante mientras dura.
