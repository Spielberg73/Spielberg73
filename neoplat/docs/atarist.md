# El Atari ST por dentro (y qué hace NeoPlat con él)

Esto es lo que hay que saber del hardware para entender el código generado, y
lo primero que hay que mirar si algo se ve raro en el emulador.

## El ordenador en cuatro líneas

| | |
|---|---|
| CPU | Motorola 68000 a 8 MHz |
| RAM | 512 KB en un 520 ST, 1 MB en un 1040 |
| Vídeo | Shifter: **bitplanes**, 4 en baja resolución |
| Color | 512, **16 en pantalla** |
| Pantalla | 320 × 200 |
| Sonido | YM2149: tres ondas cuadradas y un ruido |
| Teclado | un 6301 aparte (el IKBD) que habla por una línea serie |

Es la más espartana de las cinco máquinas del kit, y por eso la más
interesante: lleva **el mismo procesador** que las otras cuatro y no tiene nada
que le eche una mano.

- **no tiene sprites**;
- **no tiene blitter** (el del Mega ST llegó después, y aquí se hace como si no
  existiera: así el juego corre en cualquier ST);
- **no tiene scroll por hardware**. La pantalla empieza donde se le diga, pero
  solo con precisión de 256 bytes, que son línea y media: no sirve para mover
  el escenario.

Todo lo que se mueve, lo mueve el 68000 a mano. De ahí sale el resto de la
página.

## La pantalla: 200 líneas y no 224

Aquí está la única diferencia de verdad entre el ST y las otras máquinas del
kit. Las demás enseñan 224 líneas; el ST enseña 200.

El motor es el mismo para todas —si no, no sería el mismo juego—, así que lo
que se hace es **enseñar una ventana del mismo mundo**: el marcador se lleva
las 24 líneas de arriba, igual que en el Amiga, y al juego le quedan 176 en
vez de 200. Las 24 que sobran se quitan **todas por arriba**, no doce arriba y
doce abajo: en un juego de plataformas abajo está el suelo, y recortarlo se
nota mucho más que recortar cielo. Así el borde de abajo cae exactamente donde
en las demás máquinas.

La simulación no se entera: `cam_x` y `cam_y` valen lo mismo en las cinco
máquinas, y por eso la prueba de paridad C/JS sigue valiendo.

## Cómo dibuja NeoPlat

```
pantallas      dos de 320 × 200 y 4 bitplanes, alternas (32.000 bytes cada una)
escenario      se mueve de 16 en 16 píxeles, moviendo la memoria
actores        se dibujan al píxel, desplazando bit a bit y recortando por máscara
marcador       las 24 líneas de arriba de la misma pantalla, desde una copia aparte
```

Tres decisiones, y ninguna está supuesta: están medidas (más abajo se explica
con qué).

**1. Dos pantallas.** Se dibuja en la que no se ve y al final del frame se
cambia la dirección que lee el Shifter, que eso sí es gratis. Sin esto los
actores parpadean: entre borrarlos y volverlos a dibujar pasa medio frame y el
haz pasa por encima. Como cada pantalla se ve un frame sí y otro no, la que
toca dibujar va **dos frames atrasada**, y por eso cada una lleva apuntado por
su cuenta qué trozo del mundo tiene dentro y qué actores hay que borrar.

Las dos van alineadas a 32 KB y separadas 32 KB. No es capricho: así las dos
empiezan en una dirección cuyos bits 8 a 14 son cero y el contador de vídeo
—que es lo único que dice por dónde va el haz cuando no hay interrupciones—
marca lo mismo se esté viendo la que se esté viendo.

**2. El escenario se mueve de 16 en 16 píxeles.** Dibujar un tile en una `x`
cualquiera obliga a desplazar bit a bit las cuatro palabras de cada fila, y eso
cuesta cuatro veces más que copiarlas tal cual. Con la vista pegada a la
rejilla de tiles el escenario se copia sin desplazar. Los actores sí van al
píxel, porque son pocos.

**3. Al avanzar la vista se mueve la memoria, no se repinta.** Correr las 176
líneas del área de juego ocho bytes a la izquierda (unos 27 KB) y pintar la
columna que entra sale más barato que volver a dibujar las 240 casillas.

## Cómo dibujar un actor en una `x` cualquiera

El truco de siempre: meter la palabra en la mitad de arriba de un entero de 32
bits y correrlo a la derecha tantos bits como haga falta. Arriba queda lo que
va en el grupo de 16 píxeles donde empieza el dibujo y abajo lo que se sale al
siguiente.

```c
uint32_t v = ((uint32_t)palabra << 16) >> desplazamiento;
izquierda = v >> 16;
derecha   = v & 0xFFFF;
```

La máscara vale para los cuatro planos (es un bit por píxel, a uno donde el
dibujo tapa el fondo), así que se desplaza **una sola vez por fila**. Eso
permite dos atajos que valen la mitad del trabajo:

- si la fila es transparente entera, se salta y con ella ocho escrituras;
- si a un lado de la fila no hay nada opaco, tampoco hay nada que escribir
  ahí. En un dibujo pequeño —una moneda, una gema— eso es la mitad de las
  escrituras.

Y lo que no depende del plano sale **fuera del bucle a la fuerza**: si se
recorta o no por los lados, y la máscara ya invertida. El bucle de dentro se
recorre 64 veces por dibujo (16 filas × 4 planos), y la primera versión lo
miraba todo dentro.

## Que quepa en un frame

El juego **simula a 50 pasos por segundo**, igual que en las otras cuatro
máquinas —eso es lo que hace que sea el mismo juego— y **dibuja a 25**, que es
lo que da de sí un 68000 a 8 MHz sin blitter. Un frame del ST son 313 líneas
de barrido y una línea son 512 ciclos: 160.000 ciclos por frame, 320.000 por
cada dibujado.

### Cómo medirlo

Sin instrumentos y sin emulador especial, como se hacía cuando la máquina era
nueva: **se pone el borde de un color chillón mientras se dibuja** y se
devuelve al del nivel al acabar. Como el haz no espera a nadie, la franja de
ese color que sale en pantalla mide exactamente lo que ha tardado.

Está en el propio motor, detrás de un `#define`, y el número dice **qué** trozo
se mide (así la franja cabe entera en la pantalla y la cuenta sale exacta):

```
make CFLAGS='... -DNP_MEDIR=2'      # 1 frame entero   2 mover la pantalla
                                    # 3 repintar        4 actores    5 simular
```

Y para contar frames dibujados sin tocar nada: las dos pantallas se alternan y
el jugador se mueve, así que dos frames dibujados nunca salen iguales. Contando
cuántas veces cambia el mapa de píxeles se sabe a qué ritmo va.

### Lo que costó llegar a 25

| | frames por segundo |
|---|---|
| primera versión | 10 |
| tiles copiados de palabra larga en palabra larga | 15 |
| lo que no depende del plano, fuera del bucle | 17 |
| **esperar al retrazo una vez por paso, no una por dibujado** | **25** |
| mover la pantalla con `movem.l` | 25, y sin caerse a 16 al avanzar |
| dibujar repartido entre los dos pasos | 25, y 17 en lo más cargado |

Lo que más subió no fue el dibujado: fue el orden del bucle. La primera versión
esperaba al retrazo después de cada paso de simulación, y eso tiraba un frame
entero por vuelta. El trabajo de verdad —simular dos veces y dibujar— cabe de
sobra en los dos frames, pero repartido en trozos que no llegaban a tiempo al
siguiente retrazo se comía tres.

Medido con el borde, esto es lo que cuesta cada cosa (mediana, en líneas de
barrido; un frame de hardware son 313):

| | líneas | |
|---|---|---|
| simular dos pasos | 31 | y no 200, como parecía |
| repintar el fondo de los actores | 84 | |
| dibujar los actores | 124 | |
| **un frame normal, entero** | **280** | el 89% de un frame de hardware |
| mover la pantalla al avanzar la vista | 242 | solo cuando el escenario avanza |

Un frame de dibujado no cabe en un frame de hardware, pero **caben los dos en
los dos**: el juego simula dos veces por cada vez que dibuja, así que de todas
formas hay que esperar dos retrazos. Por eso el dibujado va partido en dos
mitades, una por paso: el escenario en la primera y los actores en la segunda.
Haciéndolo todo de una vez el trabajo se salía por poco de un frame y costaba
otro entero.

**Lo que sale de verdad**: 25 frames por segundo en la mayoría de las pantallas,
y unos 17 en las que juntan scroll y muchos actores a la vez (el nivel del
ejemplo con nueve monedas y dos enemigos en pantalla). La simulación va a 50
pasos por segundo en las dos, que es lo que hace que sea el mismo juego que en
las otras cuatro máquinas.

Y ojo con el reloj del juego: **una espera por paso, no una por vuelta**. Con
una sola espera, en una pantalla con poco que dibujar la vuelta entera cabía en
un frame y el juego corría al doble de velocidad. El reloj no puede depender de
cuánto haya que pintar.

### Los 27 KB que se mueven, y por qué van en ensamblador

Mover el área de juego es lo único del ST escrito a mano, y está medido antes
de decidirlo. En C, gcc genera `move.l (a1),(a0)` **con desplazamiento** —dos
palabras de extensión por instrucción— y sale a 8,5 ciclos por byte: 27 KB son
449 líneas, frame y medio. Con `movem.l`, que mueve doce registros de una
tacada, son 4,8 ciclos por byte y 242 líneas medidas.

```
movem.l (a0)+,d0/d2-d7/a2-a6     12 + 8×12 = 108 ciclos
movem.l d0/d2-d7/a2-a6,(a1)       8 + 8×12 = 104
lea     48(a1),a1                            8
dbra    d1,bucle                            10
                                 ─────────────
                                 230 por 48 bytes
```

Esa diferencia es justo la que separa dibujar en dos frames de necesitar tres:
280 + 449 + 31 se pasa de los 626 que dan dos frames, y 280 + 242 + 31 no. Con
la versión en C el juego **caía a 16 frames por segundo cada vez que el
escenario avanzaba**; con `movem` se queda en 23-25.

Hacia atrás hay que ir del final al principio, porque origen y destino se
solapan. Dentro de cada bloque da igual: `movem` lee los 48 bytes enteros antes
de escribir ninguno.

### Sin interrupciones, ¿cómo se sabe dónde está el haz?

Mirando el contador de vídeo (`$FF8205`-`$FF8209`), que sube desde la dirección
de la pantalla hasta el final de la última línea y ahí se queda hasta el frame
siguiente. De sus tres bytes basta el de en medio, que es el que cuenta las
líneas: así la lectura es de una sola vez y no puede pillar el contador a medio
cambiar.

## El teclado va por interrupción, y no es opcional

El IKBD habla a 7812 baudios y el ACIA que lo recibe **solo guarda un byte**:
si llega el siguiente antes de leer el anterior, el anterior se pierde. Y sus
mensajes son de dos y tres bytes seguidos, o sea un cuarto de milisegundo entre
uno y otro.

Mirarlo una vez por frame (20 ms) **no vale**: se pierde justo la cabecera y el
resto se lee como si fueran teclas. Comprobado en la máquina: con la cabecera
perdida, el joystick mueve al jugador una vez de cada tantas.

Así que del MFP se deja encendida solo esa línea y se baja la máscara a nivel
5, que deja pasar el nivel 6 (el MFP) y sigue tapando el retrazo y los relojes
de TOS. El juego se queda con la máquina igual que antes, pero sin perder
teclas.

**Y hay que vaciar el ACIA antes de abrir las interrupciones.** El MFP avisa
cuando la línea del teclado *baja*, y esa línea se queda abajo mientras haya un
byte sin leer. Si TOS dejó uno ahí, al borrar lo pendiente se pierde el único
aviso que iba a haber: no vuelve a bajar nunca y el mando se queda muerto para
siempre. Costó una prueba que fallaba una vez de cada dos.

El IKBD manda tres cosas mezcladas:

| | |
|---|---|
| teclas | el código de la tecla, y el mismo más `$80` al soltarla |
| joystick | `$FF` (puerto 1) o `$FE` (puerto 0) y detrás las cuatro direcciones y el botón |
| ratón | `$F8`-`$FB` y dos bytes más cada vez que se mueve |

Al arrancar se le pide al IKBD que calle el ratón (`$12`) y que avise del
joystick (`$14`), pero los paquetes que ya venían de camino hay que tragárselos
igual: si no, sus dos bytes de desplazamiento se leerían como si fueran teclas.

**El botón de acción es una tecla.** El joystick del ST tiene un solo botón, y
ese salta (y empieza la partida, que si no un mando de un botón no podría
arrancar el juego). Atacar —y con arriba, tirar el arma secundaria— va con la
tecla <kbd>X</kbd> o con <kbd>Control</kbd>: sin ellas, en el ST no había forma
de pegar. Las teclas que lee el juego son las flechas, <kbd>espacio</kbd>
(saltar), <kbd>X</kbd> / <kbd>Control</kbd> (atacar) y <kbd>Enter</kbd>
(empezar).

La cabecera del paquete es lo que dice de qué puerto viene, y por eso con
`jugadores: 2` no hay nada que configurar: el **puerto 1** (el conector del
joystick de siempre) es el primer jugador y el **puerto 0** (el del ratón) el
segundo, así que hay que quitar el ratón y enchufar ahí el otro joystick. El
teclado sigue siendo solo del primero. En Hatari, el segundo joystick tampoco
se conecta solo: hay que pedirlo con `hatari_twojoy`.

## Colores

El ST enseña **16 colores de 512**: tres bits por canal, `0000 0RRR 0GGG 0BBB`.
El STE amplía cada canal a cuatro bits colocando el nuevo bit abajo del todo, y
por eso el mismo valor se ve casi igual en las dos máquinas.

Las paletas del proyecto se funden en una sola de 15 (el último color se
reserva para el marcador). No hay dibujo que quepa tal cual, así que los
colores que sobran se cambian por el más parecido, pesando cuánto se usa cada
uno: es el mismo corte por la mediana que usa el modo de doble plano del Amiga.
Si quieres mandar tú en los colores, dibuja con quince.

## El parallax, y por qué depende de la cámara

El ST dibuja **una capa de fondo, y solo con `camara: pantallas`**. No es una
opción que haya que elegir: sale de lo que cuesta cada cosa.

Con la cámara por pantallas la vista se queda quieta entre salto y salto, así
que el fondo también, y pintarlo **no cuesta nada**: donde no hay escenario ya
se pintaba un tile en blanco, y ahora se pinta el del fondo. Solo hay tres
casos, y dos son gratis:

| la casilla | qué se hace | qué cuesta |
|---|---|---|
| el tile tapa la casilla entera | se copia y ya está | lo mismo que antes |
| está vacía | se copia el tile del fondo | lo mismo que antes |
| el tile deja huecos | fondo debajo y el tile encima con su máscara | el doble, y son cuatro casillas |

Para saber cuál es cada una, el compilador emite un bit por dibujo
(`np_tile_opaco`): 1 si no tiene ni un píxel transparente. En un escenario
normal casi todos los tiles son de esos o están vacíos.

Con `camara: scroll` no se dibuja, y aquí sí es por lo que cuesta: el fondo
tiene que ir a otra velocidad que el escenario, y correr la memoria solo puede
mover los dos a la vez. Habría que repintar la pantalla entera cada pocos
píxeles —322.000 ciclos, dos frames— y no cabe. El compilador lo avisa.

## Cómo suena

El YM2149 del ST es **el mismo chip que el SSG del YM2610 de la Neo Geo**: tres
canales de onda cuadrada y uno de ruido, con el periodo en doce bits. Lo único
distinto es el reloj (2 MHz en el ST, 4 en la Neo Geo), y de eso ya se encarga
el compilador al convertir las notas.

Escribirlo son dos pasos: el número de registro en `$FF8800` y su valor en
`$FF8802`. Dos avisos:

- el registro 7 (el mezclador) tiene los bits **al revés**: un cero enciende;
- sus bits 6 y 7 no son de sonido, sino la dirección de los dos puertos de la
  impresora y el RS-232. Si se ponen mal, el ST deja de hablar con ellos. Por
  eso el mezclador se escribe siempre partiendo de `$C0`.

## El disquete (.st)

Un `.st` es la copia byte a byte de un disquete de 720 KB: 80 pistas × 2 caras
× 9 sectores × 512 bytes. Dentro va un **FAT12**, el mismo sistema de ficheros
del MS-DOS de la época, que es el que usa TOS.

```
sector 0        el sector de arranque, con la tabla de parámetros (BPB)
sectores 1-5    la FAT
sectores 6-10   su copia
sectores 11-17  el directorio raíz (112 entradas)
sector 18 …     los datos, en grupos ("clusters") de dos sectores
```

El juego se mete en una carpeta llamada **AUTO**: al encender, TOS mira si el
disquete tiene esa carpeta y ejecuta los `.PRG` que haya dentro antes de sacar
el escritorio. Es la forma normal de que un disco de juego arranque solo, y no
hace falta escribir código en el sector de arranque —de hecho hay que
**evitar** que la suma de sus 256 palabras dé `$1234`, que es lo que TOS mira
para decidir si lo ejecuta.

Ojo con una cosa que despista: aunque el 68000 es big endian, los números de la
tabla de parámetros y del directorio van **al revés** (little endian), porque
el formato viene del PC y Atari lo copió tal cual para poder intercambiar
discos.

## Cómo arranca un ejecutable de GEMDOS

El `.PRG` es más sencillo que el ejecutable del Amiga: no son trozos sueltos
sino **un bloque seguido** que TOS carga donde le cabe.

```
+0   word   $601A, que es lo que mira TOS para saber que es un programa
+2   long   cuánto ocupa TEXT
+6   long   cuánto ocupa DATA
+10  long   cuánto hay que reservar de BSS (TOS lo entrega a cero)
+14  long   cuánto ocupa la tabla de símbolos
+18  long   reservado
+22  long   banderas
+26  word   0 = trae tabla de relocalización
```

La tabla de relocalización es un invento de Digital Research que gasta un byte
por corrección: primero una palabra larga con el desplazamiento de la primera,
y luego un byte por cada una diciendo cuánto hay que avanzar desde la anterior.
Un byte no llega a 256, así que el valor 1 significa "avanza 254 y sigue sin
corregir nada", y el 0 cierra la tabla.

El juego arranca en **modo usuario**, que no puede tocar ni el Shifter ni el
chip de sonido, así que lo primero es pedir modo supervisor con `Super(0)` de
GEMDOS. Tiene una particularidad útil: deja la pila de supervisor donde estaba
la de usuario, así que el `addq.l #6,sp` de después limpia los parámetros del
sitio correcto y la ejecución sigue como si nada.

## Si algo se ve raro

| lo que se ve | dónde mirar |
|---|---|
| pantalla en blanco y TOS sale al escritorio | el `.PRG` no está en `AUTO/`, o la cabecera no empieza por `$601A` |
| el juego se cuelga al poco de arrancar | una corrección de la tabla de relocalización que cae fuera del programa |
| los actores dejan rastro | `np_repintar_rastros`: la caja apuntada no cubre lo que se dibujó |
| los actores parpadean | se está dibujando en la pantalla que se ve |
| el mando no responde | el ACIA se quedó con un byte sin leer y el MFP no vuelve a avisar |
| el escenario da saltos raros al andar | `np_correr` y las columnas que entran: la vista y la memoria no cuadran |
| colores cambiados | son 15: mira el aviso de `ngplat compilar`, que dice cuántos se han aproximado |
| el fondo no sale | solo se dibuja con `camara: pantallas`; con scroll no cabe |
| el juego va al doble de velocidad | falta una espera al retrazo por cada paso de simulación |

## Comprobarlo en un emulador

`tests/emulador_st.py` mete el disquete en un ST emulado (Hatari, con EmuTOS) y
mira lo que sale por pantalla y por el YM2149. Ni el core ni el TOS vienen en
los repositorios:

```
https://buildbot.libretro.com/nightly/linux/x86_64/latest/hatari_libretro.so.zip
https://sourceforge.net/projects/emutos/files/emutos/1.4/
```

El core va en `/usr/local/lib/libretro/` y la imagen de TOS en
`/usr/local/share/neoplat/tos.img`.

Dos cosas que costaron encontrar:

- **Hatari no conecta el mando al joystick del ST si no se le dice.** Hay que
  pedirlo opción a opción (`hatari_mapper_*`). Sin ellas no llega nada, ni
  teclas ni joystick, y el juego parece colgado cuando lo que pasa es que nadie
  le está hablando.
- **El core no se deja arrancar dos veces en el mismo proceso**: la segunda se
  queda colgada. Por eso las pruebas del kit lo lanzan como un programa aparte.
