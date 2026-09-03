# Cambios

Cada versión del kit, de la más nueva a la más vieja. La versión sube cada vez
que se cambia algo que se reparte, y va en el nombre de los paquetes
(`neoplat-kit-1.23.zip`) y en `ngplat --version`: así se sabe qué se está
probando sin abrir nada.

## 1.23

**Sexto género: una aventura, al estilo Dizzy.**

```bash
ngplat nuevo miaventura --genero aventura
```

Se ve de lado, como el de plataformas, pero no va de saltar bien: va de
**llevar la cosa correcta al sitio correcto**. Tres piezas nuevas del motor, y
las tres se pueden usar sueltas en cualquier juego:

- **La bolsa** (`efecto: llevar`). Un objeto así **no se gasta al tocarlo**: se
  guarda, y caben tres. Con que haya uno en el juego, el botón de acción deja
  de atacar y pasa a **soltar** lo primero de la bolsa a tus pies, y el
  marcador enseña lo que llevas por su `marcador:`. Si la bolsa está llena, el
  objeto se queda donde estaba: esa es la decisión que hace el juego.
- **Los cerrojos** (`tipo: cerrojo` + `abre_con:`). Una casilla que frena como
  una pared hasta que apareces con lo que pide; al abrirla se gasta el objeto y
  el paso se queda abierto para siempre. Una puerta de varias casillas seguidas
  es **una** puerta: se abre entera y cuesta un solo objeto. Y lo que pide
  tiene que existir y tiene que ser de los que se llevan, o `ngplat` no
  compila.
- **El salto fijo** (`salto_fijo: si`). En el aire no se manda: al despegar
  decides hacia dónde vas y con cuánto impulso, y ni soltar el botón acorta el
  salto. Suena incómodo y es justo lo que hace que cada salto sea una decisión;
  para subir un escalón hay que despegar **antes** de llegar a él.

El proyecto de partida son dos niveles de **cuatro pantallas** cada uno, con la
cámara de `pantallas` (sin scroll, un cuadro por sitio) y la misma cadena de
tres contada de dos maneras: EL VALLE en orden —la llave abre la puerta, detrás
el cubo apaga la hoguera, detrás el pico tira la pared— y LA CUEVA desordenada,
donde el pico y la llave se cogen juntos y hacen falta en pantallas distintas.
Y sus dibujos: el huevo, la araña, el murciélago, los tres objetos del puzle y
diez tiles de valle y de cueva, en los dos estilos.

**Lo que encontró la prueba de paridad.** El cerrojo frenaba en el preview y
**no** en el motor en C: `np_blocks` no lo contaba, así que en las siete
máquinas se podía atravesar una puerta cerrada. No lo vio nadie jugando —lo
vio la traza, al primer género que usa cerrojos—. De paso, la traza ahora lleva
la bolsa y las casillas abiertas, para que la próxima vez se vea antes.

**Y lo que encontró la de direcciones impares.** La bolsa son tres huecos
seguidos que se recorren en bucle, y gcc junta dos lecturas de byte pegadas en
una sola de palabra: con la bolsa en una dirección impar, esa palabra es un
*address error* y el 68000 **se para en seco** —la Mega Drive, el Amiga y el
Atari ST se quedaban con la imagen congelada al arrancar—. Los huecos pasan a
ser palabras, que caen siempre en par y no hay nada que juntar mal. La
comprobación estática, además, ahora sigue la paridad del registro base: gcc
coge a veces una base impar a propósito (`lea %a2@(27),%a3`) para llegar a un
grupo de campos con desplazamientos cortos, y eso daba 27 falsos positivos.

También: el marcador de las siete máquinas repinta la línea de "lo que llevas"
cuando cambia **la bolsa** (antes solo miraba llaves y munición, así que cogías
una llave y seguía enseñando lo de tres pantallas atrás), el editor llama a
cada cerrojo por lo que pide en vez de "tile" a secas, y el bot sabe que con el
salto fijo hay que despegar antes de llegar a la pared.

## 1.22

**Quinto género: yo contra el barrio, al estilo Double Dragon.**

```bash
ngplat nuevo micalle --genero barrio
```

Se ve de lado, como el de plataformas, pero no se anda por una línea: se anda
por una **franja de suelo con profundidad**, y el salto es una tercera
coordenada aparte. Eso es una vista nueva del motor, `vista: cinta`, y de ella
sale el género entero: dos que no están a la misma profundidad **no se tocan**,
y al saltar tu caja sube con el dibujo, así que el puñetazo de abajo te pasa
por debajo.

El truco para que la tercera coordenada no costara una línea de código en las
siete máquinas: **`y` sigue siendo dónde se dibuja** y la altura se guarda
aparte. Así los siete dibujantes no se enteran de nada, dos cajas se tocan solo
si coinciden en profundidad **y** en altura —que es justo la regla del
género—, y quien necesita saber por dónde se anda (los choques y la cámara)
suma la altura y tiene la línea del suelo.

Lo que trae el género:

- **La serie de golpes** (`combo:`). Puño, puño y remate: apretar otra vez
  antes de que se acabe `ventana:` encadena el siguiente, y el último hace
  `dano_remate:`, **tumba** al que lo cobra (`derribo:`) y lo manda deslizando.
  Uno tumbado ni decide nada ni te hace daño, que es lo que hace que rematar
  sirva de algo. Con `combo: 1` no hay serie y el motor ni lo mira.
- **El agarre** (`agarre:`). Al que se tambalea de un golpe se le coge
  tocándolo: con acción, rodillazos; con salto, **por encima del hombro**. El
  que sale lanzado vuela con su propia altura y su arco, se estrella al caer y
  aterriza derribado. Es la única vez que una entidad —y no el jugador— usa la
  tercera coordenada.
- **La cámara con cerrojo.** Mientras quede alguien vivo en pantalla, la vista
  no avanza. No se configura: es lo que convierte un pasillo en una pelea, y
  sin ello el juego se pasa andando. Hacia atrás sí se mueve, porque lo que se
  cierra es el paso y no la vista.
- **El que te pega se aparta.** Sin eso, tres matones a la vez te matan en dos
  segundos: en cuanto se acaba el parpadeo vuelven a darte. Ahora pegan y
  reculan, como en los recreativos. Solo en esta vista; los demás géneros
  siguen exactamente igual.
- **Los actores se pintan de más lejos a más cerca**, en las siete máquinas y
  en el preview. En un juego donde todo el mundo se pisa, sin eso no se
  entiende quién está delante de quién. Fuera de esta vista el orden es el de
  siempre y no cuesta un ciclo.

El proyecto que sale trae dos calles (LA CALLE y EL DESCAMPADO) con sus dibujos
propios —el héroe con su chaqueta, dos clases de matón, el jefe, los barriles,
el bate y el pollo—, cuatro canciones y una calle de 48 × 14 donde lo que
importa no es el dibujo del suelo sino dónde se planta cada grupo.

**El bot también aprendió a pelear.** El que comprueba que un nivel se puede
terminar andaba hacia la derecha; en un juego con cerrojo eso no lleva a
ninguna parte. Ahora hace lo que haría cualquiera: se cuadra en la profundidad
del que tiene delante, le pega, y si lo agarra **lo lanza**; y si algo se le
pone por medio —una valla—, lo rodea cambiando de profundidad en vez de
insistir contra ella.

**Arreglado de paso**: el cuerpo a cuerpo solo existía en vista lateral
(`np_melee_update` no se llamaba desde ningún otro sitio), y el guardia de «no
toques dos veces con el mismo golpe» miraba el parpadeo del enemigo en vez del
golpe, así que una serie de tres solo acertaba el primero.

**Y una cosa que enseñó el Atari ST**, que es la máquina más justa de las
siete. Pedir el orden de dibujo estaba bien; **leerlo** dentro del bucle que
pinta a todos los actores le costaba lo bastante como para perder el vblank, y
la música —que va por frames— empezaba a sonar lenta. El índice se resuelve
ahora al compilar (`NP_DIBUJO`, en el `gamedata.h` de cada juego): en uno de
cinta mira la lista y en cualquier otro es `i`, así que el bucle de siempre
queda exactamente como estaba. Lo pilló la prueba que arranca el disquete del
ST en un emulador de verdad, que es justo para lo que está.

Pruebas nuevas: la vista de cinta entera (que se salta y se vuelve al mismo
sitio, que el salto sube el dibujo y no la fila por la que se anda, que
saltando no se atraviesan las paredes y que el daño se cobra con los pies en el
suelo), la serie de golpes, el agarre con su lanzamiento, el cerrojo de la
cámara con su control de que es solo de esta vista, la paridad C/JS de todo
ello —con sus mutantes: cambiando la gravedad del salto en el C la traza se
separa, y el mismo juego sin serie o sin agarre da otra traza—, que las dos
calles se pueden limpiar con el bot y que sin puños no se pasa de la primera, y
que el proyecto se genera para las siete máquinas.

## 1.21

**Cuarto género: la mazmorra, al estilo Gauntlet.**

```bash
ngplat nuevo micripta --genero mazmorra
```

Se ve desde arriba como el de comando, pero se juega de otra manera: el nivel no
es un camino sino un **laberinto** de 20 × 28 casillas que se ve casi entero, y
lo que decide la partida no es la puntería sino por dónde tiras. Tres cosas
nuevas del motor, las tres iguales en las siete máquinas y en el preview:

- **`desgaste:`, la vida que se gasta sola.** Con `vida: 200` y `desgaste: 12`
  el jugador pierde un punto cada doce frames: la partida es una cuenta atrás de
  cuarenta segundos que solo para la comida (`efecto: salud`). No respeta la
  invulnerabilidad —el parpadeo te salva de los golpes, no del hambre— y al
  llegar a cero te mueres como de un golpe. Con la vida por encima de nueve el
  marcador deja de dibujar cuadrados y **escribe el número** (`LIFE 184`), que
  es lo que hacía el Gauntlet.
- **`generadores:`, los nidos que sueltan bichos sin parar.** Cada uno saca su
  enemigo cada `cada:` frames hasta que lo revientas, con un `tope:` de bichos
  suyos vivos a la vez y su propia `vida:`. Mientras siga en pie, matar lo que
  sale no sirve de nada: esa es la regla que le da la vuelta al juego. No hace
  daño al tocarlo —se le pega, no te pega—, y es un actor como los demás, así
  que se dibuja y se anima en las siete máquinas sin una línea de código por
  máquina.
- **`efecto: bomba`, la poción que limpia la pantalla.** Hace daño a todo lo que
  se ve en ese momento —enemigos, nidos y rompibles—, y solo a eso: la *smart
  bomb* de siempre, que vale lo que valga el momento en que la cojas.

El proyecto que sale trae dos laberintos (LA CRIPTA y EL FOSO), cuatro
enemigos con su guardián de jefe, dos clases de nido y la meta cerrada con una
llave que está al otro lado del mapa: hay que dar la vuelta entera con el reloj
corriendo, y eso es el género.

**Y el bot ahora va a por la llave.** El que comprueba que un nivel se puede
terminar (el del botón «¿se puede terminar?» del editor y el de las pruebas)
iba derecho a la meta desde arriba: en una mazmorra con la meta cerrada se
quedaba dando vueltas. Ahora decide igual que una persona —primero comida si le
queda poca vida, después la llave que falte, y la meta al final— y mide el
avance por lo que le queda de camino **hasta lo que busca ahora**, que es lo
que le deja bajar a por la llave sin creerse atascado.

**Arreglado de paso: el editor no conocía a los prisioneros ni a los nidos.**
Su tabla de tipos se paraba en el rompible, así que un `R` de prisionero (desde
la 1.17) o un `n` de nido caían en la lista de objetos: no salían en la paleta,
no se podían pintar y en el mapa se dibujaban como si fueran otra cosa. Ahora
salen los seis tipos con su nombre y su dibujo, y el aviso de «demasiadas
entidades» cuenta también los bichos que pueden tener fuera los nidos.

**Y otro del validador**: un nombre repetido en dos secciones no compilaba
—`ngplat` lo dice— salvo si una de las dos era `prisioneros:` o
`generadores:`, que se quedaban fuera de la comprobación. Ahora se miran las
seis, dos a dos, así que añadir una séptima no vuelve a dejar un hueco.

**En el preview**, el botón de saltar ya no dice «lanzar granada» siempre: dice
el arma secundaria que lleve el juego (en la mazmorra, «lanzar pocima»).

Pruebas nuevas: los dos laberintos se terminan con el bot (y si se tapia el
rincón de la llave, lo dice); la paridad C/JS del desgaste, de los nidos y de la
poción, cada una con su comprobación de que la mecánica está de verdad (la vida
baja de punto en punto; los mismos nidos dormidos dan otra traza; la poción
suma los puntos de los tres bichos que revienta); el proyecto entero se genera
para las siete máquinas y los generadores llegan a su `gamedata.c`; el marcador
de tres cifras, compilando el motor de verdad; el editor con un juego que trae
nidos; que con la vida corta el bot solo termina los laberintos si para a
comer, y cambiando la comida por tesoros ya no llega; y, encendiendo una Mega
Drive emulada, que el marcador **baja solo** sin tocar el mando.

El `ngplat comprobar` también cuenta ahora los prisioneros y los generadores
que trae el proyecto, que antes no salían por ningún lado.

## 1.20

**Séptima máquina: el Amiga 1200, con AGA.**

```bash
ngplat compilar --sistema amiga1200
```

Es el mismo Amiga y comparte el motor entero —bitplanes, blitter, copper y
Paula—, pero con el chipset AGA sacando pecho. Es un destino aparte y no una
opción del otro porque su disquete **pide una máquina AGA**: en un A500 los ocho
bitplanes no existen y no se vería nada.

| | Amiga (OCS/ECS) | Amiga 1200 (AGA) |
|---|---|---|
| Bitplanes | 5, o 3+3 en doble plano | **8**, o 4+4 |
| Colores a la vez | 32, o 7+7 | **256**, o 16+16 |
| Por canal | 4 bits (4096 en total) | **8 bits** (16,7 millones) |
| CPU | 68000 a 7 MHz | 68EC020 a 14 MHz (`-m68020`) |
| RAM chip | 512 KB | 2 MB de serie |

Lo que más se nota no son los 256 colores sino que **no se redondea ninguno**:
el OCS guarda cuatro bits por canal, así que todo lo que dibujas se acerca al
color más parecido de 4096; el AGA guarda los ocho que trae el PNG. Un juego con
más de 31 colores distintos, que en un A500 no compila, en el A1200 entra tal
cual y sin aproximar nada.

Tres cosas hubo que decirle al chipset:

- **Ocho bitplanes no caben en la DMA de siempre.** En baja resolución, leyendo
  de 16 bits, entran seis contados. El AGA lee de **32** (`FMODE`), cada lectura
  trae el doble de píxeles y los ocho entran; a cambio la DMA arranca ocho
  *color clocks* antes y hace diez lecturas en vez de veinte.
- **Los 256 colores no caben en los registros**, que siguen siendo 32: se eligen
  por bancos con `BPLCON3`, y como el registro es de 12 bits y el color de 24,
  cada color se escribe dos veces (los cuatro bits altos de cada canal y luego
  los bajos, con `LOCT`). Son 528 instrucciones de copper que caben de sobra
  antes de que empiece la imagen.
- **El scroll.** Leyendo de 32 en 32 bits el puntero de bitplane no mira sus
  bits de abajo, así que salta de 32 en 32 píxeles y lo que sobra —hasta 31— lo
  pone el scroll fino extendido de `BPLCON1`. Medido: andando a 1,4 píxeles por
  frame se mueve **1, 2, 1, 1, 2…**, exactamente igual que en un A500.

**Y comprobado en un A1200 emulado, no de vista:**

- el marcador se dibuja con el color **255**, y en la paleta el blanco está sólo
  en ese índice: si hubiera cinco bitplanes, saldría de otro color;
- dos casillas de `#101010` y `#1F1F1F` —que el OCS redondea a `#111111` y
  `#222222`— salen en el A1200 como `#1F1F1F`: los bits de abajo llegan;
- el disquete arranca, se juega, suena las 16 notas de su melodía, y en doble
  plano el fondo se mueve a un tercio de lo que se mueve el suelo.

En el `game.yaml`, `amiga: 256colores` y `amiga: 16colores` son los mismos dos
modos de siempre con otro nombre (`32colores` y `8colores` siguen valiendo).

## 1.19

**La pestaña «sonido» del editor.** Hasta ahora el editor cambiaba el mapa, la
física, los enemigos y los dibujos, pero para tocar un efecto o una canción
había que ir al `game.yaml` a mano. Ya no:

- **Los doce momentos** que el juego produce solo (`empezar`, `salto`,
  `doble_salto`, `moneda`, `pisar`, `golpe`, `muerte`, `meta`, `vida`,
  `disparo`, `romper`, `control`) salen listados, con sonido o sin él. En cada
  uno eliges el tipo —**notas**, **barrido** o **ruido**— y ajustas sus números.
  «Sin sonido» se lo quita; elegir un tipo en uno que estaba mudo se lo pone.
- **Botón de escuchar** en cada efecto y en cada canción, sin salir del editor
  ni volver al juego.
- **La música**, con sus frames por nota, su volumen, si va en bucle y las dos
  pistas de notas en su recuadro. Debajo dice cuánto dura una vuelta, y una
  nota que no existe sale en rojo en vez de colarse.
- Todo se escribe en el `game.yaml` como estaba escrito: los efectos en una
  línea (`salto: {tipo: barrido, desde: 320, ...}`) y las pistas en bloque, con
  sus saltos de línea. Lo que no tocas no se reescribe.

**Y lo importante: lo que se oye es lo que va a sonar.** El navegador no puede
usar el compilador del kit (es Python), así que hay un gemelo suyo en
JavaScript, `preview/np_sonido.js`, con las mismas notas, el mismo barrido y el
mismo ruido. Que los dos den exactamente los mismos pasos no se supone: hay una
prueba que los compara nota a nota sobre melodías, barridos y ruidos, y otra
que comprueba que lo que uno rechaza el otro también.

Un efecto con `muestra:` (un WAV tuyo) se puede editar sin perder el WAV: lo
que cambias es el recambio de notas para la máquina que no sabe tocar sonido
grabado.

## 1.18

**Escenarios altos en las seis máquinas.** El género comando salió con niveles
de 32 casillas de alto, y de las seis sólo cuatro los admitían: el Amiga y la
Jaguar no dibujan el escenario con un mapa de nombres sino en un mapa de bits
que hace de ventana, y ese mapa era de 704 × 256 fijos. Dieciséis casillas de
alto. Ahí no cabe un juego que se sube.

Ahora la **forma** del mapa de bits la elige el juego, y ocupa lo mismo en las
dos: los mismos bytes puestos de otra manera.

| forma | casillas | para qué |
|---|---|---|
| 704 × 256 | 44 × 16 | lo de siempre: un juego que se cruza |
| 352 × 512 | 22 × 32 | un juego que **se sube** |

No hay nada que elegir en el `game.yaml`: la decide el nivel más alto que tenga
el juego. El precio de la forma alta es que el nivel tiene que **caber entero de
ancho** (22 casillas): con dos casillas de margen no hay ventana que valga, la
cámara se pasaría el rato repintando la pantalla entera. A cambio, mientras se
sube no se dibuja nada: el escenario se pinta al entrar y el scroll vertical es
sólo mover un puntero. Si un nivel se pasa, `ngplat comprobar` lo dice con esas
palabras y no compila.

Probado subiendo una torre de 20 × 32 hasta la meta **en las seis máquinas de
verdad**: Neo Geo (el banco del kit), Mega Drive, Amiga (PUAE), Jaguar (Virtual
Jaguar), Atari ST (Hatari) y X68000 (px68k). Las seis tardan lo mismo en
subirla, así que ninguna se queda sin frames por el camino.

**Y tres cosas que salieron por el camino:**

- **«VEL CLEAR».** Al terminar un nivel, el Amiga, el Atari ST y la Jaguar se
  comían las dos primeras letras del mensaje: la barra de vida se repintaba en
  blanco sobre la misma fila y borraba lo que había debajo. El X68000 ya lo
  tenía visto y arreglado; ahora lo están las cuatro.
- **La Jaguar no miraba el alto de los niveles.** El límite estaba escrito en la
  documentación pero no se comprobaba: un nivel alto compilaba tan tranquilo y
  luego se veía partido.
- **`--make` para el X68000** se negaba a llamar a un `make` que habría
  funcionado: buscaba sólo `m68k-elf-gcc` cuando su Makefile acepta también el
  `m68k-linux-gnu-gcc` de Debian y Ubuntu.

## 1.17

**El género comando**, entero. La 1.16 dejó el motor mirando desde arriba; esta
lo convierte en un juego que se puede hacer sin escribir nada:

```bash
./ngplat nuevo micomando --genero comando
```

Salen dos niveles jugables, el héroe dibujado de frente, de espaldas y de lado,
soldados y torretas que te disparan, granadas, cajas de munición y prisioneros,
con su música y sus efectos. Es el tercer género del menú de `ngplat nuevo`.

**Los prisioneros.** Un tipo de bicho nuevo, `prisioneros:`, que es el que le da
carácter al género: se sueltan **tocándolos** (suman puntos y echan a correr),
pero si les disparas mientras están atados **los pierdes** y no suman nada. Es
la única cosa del kit que castiga por apretar el gatillo, y es justo lo que hace
que se mire antes de disparar.

```yaml
prisioneros:
  prisionero:
    sprite: graficos/prisionero.png
    puntos: 500
    velocidad: 1.6
    escape: 100        # frames corriendo antes de perderse de vista
```

Como todo lo demás, son una entidad más de la lista: se dibujan solos en las
seis máquinas y en el preview, y entran en la comprobación de paridad.

**Los niveles se suben.** Los dos del género son altos y estrechos (20x32
casillas, algo más de dos pantallas), se empieza abajo y la base está arriba, y
el camino **tuerce**: los recodos, el río que corta por la mitad y los recintos
de sacos terreros son lo que hace que se juegue, porque un pasillo recto se sube
andando y ya.

**Un bot que sabe subir.** El que comprueba que un nivel se puede terminar solo
sabía andar hacia la derecha y saltar, que en una vista cenital no lleva a
ninguna parte. Ahora hay dos: el de siempre y uno que busca el camino hasta la
meta, sube por él y dispara a lo que se le acerca —sin llevarse por delante a
un preso que tenga en la línea de tiro—. Vale para las pruebas y para el botón
«¿se puede terminar?» del editor, que en cenital ya dice a qué **altura** se
quedó en vez de a qué x.

**La fila de teclas del preview** se ajusta a la vista: en cenital dice ocho
direcciones, disparar y lanzar granada, y deja de hablar de saltar y agacharse.

**Y un límite que estaba escrito pero no se miraba**: la Jaguar dibuja el
escenario en un mapa de bits de 704x256, o sea 16 casillas de alto, igual que el
Amiga. El Amiga lo comprobaba y la Jaguar no, así que un nivel alto compilaba
tan tranquilo y luego se veía partido. Ahora `ngplat comprobar --sistema jaguar`
lo dice antes. Los dos niveles del género comando son de 32 casillas: entran en
Neo Geo, Mega Drive, Atari ST y X68000, y en esas dos máquinas hay que bajarlos
a 16 (o subirles el mapa de bits, que es lo siguiente).

## 1.16

**La vista cenital**: el motor ya sabe mirar el juego desde arriba. Es el
primer paso para hacer juegos al estilo Ikari Warriors o Guerrilla War, que
no son un plataformas con otros dibujos sino otra forma de moverse.

```yaml
juego:
  vista: cenital       # lateral (por defecto) o cenital
```

Con `cenital` no hay gravedad ni suelo: se anda en las **ocho direcciones** (y
las diagonales van a 0,707 para que no sean un 41% más rápidas), se dispara
**hacia donde se mira**, el botón de saltar pasa a ser el de la granada —no hay
nada que saltar— y el mapa es una caja cerrada por sus cuatro lados. Las
escaleras, agacharse y pisar enemigos se apagan solos: ahí no significan nada.

El héroe se dibuja mirando a tres sitios y el motor elige: de espaldas cuando
sube (`arriba`), de frente cuando baja (`abajo`) y de lado el resto. Son dos
ranuras de animación nuevas; quien no las traiga se queda con `correr`.

**Y los enemigos disparan.** Con `dispara:` un enemigo deja de ser un obstáculo
que esquivar y pasa a ser una amenaza a distancia:

```yaml
enemigos:
  soldado:
    dispara:
      sprite: graficos/tiro.png
      velocidad: 2.0
      alcance: 200
      espera: 90       # frames entre tiro y tiro
      dano: 1
```

En vista lateral tira de frente; en cenital te **apunta a ti**, redondeando a
la más cercana de las ocho direcciones. Vale para los dos modos: un plataformas
también gana con enemigos que disparan.

Lo que se comprueba: la vista cenital tiene su propia variante en las pruebas
de paridad C/JS —es el sitio donde más fácil sería que el motor del navegador y
el de las máquinas se separaran— y catorce pruebas nuevas de jugabilidad (que
no hay gravedad, que las diagonales no corren más, que las paredes frenan
arriba y abajo, que no se sale uno del mapa, que el disparo sale hacia donde
miras, que el enemigo respeta su cadencia y su alcance, que su tiro se para en
las paredes y que desde arriba te apunta a ti).

Esto es el motor. El género `comando` —con su héroe de tres vistas, sus
soldados, su granada y su nivel— viene detrás.

## 1.15

**El X68000 toca las muestras a 15,6 kHz, no a 10,4.** El kit venía usando el
modo `$0303` del ADPCM porque una medida antigua decía que la quinta velocidad
—los 15,6 kHz del MSM6258— "no sonaba". La medida estaba mal, y la culpa era
del tono con el que se hizo: **3000 Hz no caben a 3,9 kHz de muestreo** (ahí el
máximo son 1950), así que en los modos lentos lo que se oía era un pliegue y el
quinto se juzgó con la vara equivocada.

Repetida con un tono de 1000 Hz, que cabe en las cinco, la escalera sale
entera y el quinto modo suena como los demás:

| modo | velocidad |
|---|---|
| `$0003` | 3,9 kHz |
| `$0103` | 5,2 kHz |
| `$0203` | 7,8 kHz |
| `$0303` | 10,4 kHz |
| `$0403` | **15,6 kHz** |

Ahora el kit usa `$0403`, que es lo mejor que da esta máquina. Se nota en la
prueba de siempre: con el mismo efecto (un tono puro a 3000 Hz), al saltar la
banda de 3000 Hz sube **1556 veces** sobre el fondo, contra las 892 de cuando
iba a 10,4.

Con esto, la lista de "lo que le falta al X68000" se queda sin sus dos
entradas: el parallax entró en 1.14 y la velocidad del ADPCM, aquí.

## 1.14

**El X68000 ya tiene parallax.** Era lo último que le faltaba a esa máquina, y
llevaba apuntado como "si algún día se averigua cómo enseñar la segunda capa".
Resulta que no era por ahí.

- La sonda anterior barrió los bits del chip de sprites con **el mismo mapa en
  las dos tablas**, así que no había forma de distinguir "solo se ve una capa"
  de "se ven las dos, una encima de otra". Repetida con dibujos distintos y en
  sitios distintos —rojo a la izquierda en una tabla, verde a la derecha en la
  otra— el resultado es concluyente: en las 160 combinaciones de `$EB0808` y
  `$EB0810` **nunca** salen los dos. Su capa se la queda el escenario.
- Pero el X68000 tiene **otra pantalla** que el kit no usaba para nada: la
  gráfica (GVRAM), con su propio scroll por hardware. La misma sonda dice que
  se ve **a la vez** que la capa de fondo y por detrás de ella, y que moviendo
  `$E80018` se desplaza sola. Ahí va el parallax.
- Cuesta **dos registros por frame** y no gasta ni un patrón de la PCG (que son
  192 y hacen falta): la capa se escribe una vez al empezar el nivel, repetida
  hasta llenar los 512 píxeles de la página.

Medido en el emulador, corriendo a la derecha: el suelo se desplaza 67 píxeles
y el cielo 14, o sea el 0,21 del scroll, que es exactamente la `velocidad: 0.2`
de esa capa en el `game.yaml`. Quitar el scroll de la capa tira la prueba.

La pantalla gráfica es una sola página en este modo, así que se dibuja **una
capa por nivel** (la más lejana) y el compilador lo dice cuando el juego trae
más, igual que hace el Amiga en doble plano.

## 1.13

**Música de título y música de jefe.** El kit tenía dos canciones por juego,
una por nivel, y la pantalla de título estaba muda. Ahora hay dos canciones más
que no son de ningún nivel y se dicen por su nombre:

```yaml
sonido:
  titulo: presentacion   # suena mientras espera a que pulses Start
  jefe: acoso            # manda sobre la del nivel mientras el jefe esté vivo
```

Los proyectos nuevos las traen puestas —y **compuestas**: dos por estilo de
dibujo y dos para el género de látigo, seis canciones nuevas en total—, así que
un juego recién creado suena en el título, cambia de música en cuanto aparece
el jefe y vuelve a la del nivel al matarlo.

**Quién decide qué suena ahora es el motor.** Las seis máquinas tenían la misma
línea copiada (`si estoy jugando, la del nivel`), así que cualquier regla nueva
había que escribirla seis veces y acordarse de las seis. Ahora existe
`np_music_now()` —y su gemela `musicaAhora()` en el preview— y las seis se
limitan a mandar el número al chip.

Y las pruebas de emulador ya no exigen que el título esté callado: exigen que
**suene lo que diga el proyecto**. Con `titulo:` tiene que oírse (y se oye:
niveles de 1.000 a 6.000 contra un suelo de silencio de 1.0 en las cuatro
máquinas que escuchan el título) y sin él tiene que estar mudo, que es lo que
sigue pasando con los dos ejemplos del kit.

## 1.12

**El género de látigo trae sus propios bichos.** Hasta ahora los dos géneros
compartían la seta y la mosca —y encima los tres enemigos, jefe incluido,
usaban el **mismo dibujo**—, así que un juego de castillo se veía como el de
plataformas con otro sprite en la mano. Ahora el género de látigo trae los
suyos, cada uno con su hoja:

- **Esqueleto**: patrulla despacio y **aguanta dos latigazos**. Aquí no se pisa
  a nadie, así que dos golpes son acercarse, pegar y salir: es lo que obliga a
  medir la distancia, que es de lo que va este género.
- **Murciélago**: va y viene por el aire a la altura de la cabeza. Agachándote
  te pasa por encima.
- **La muerte**: un encapuchado que te persigue y aguanta cinco latigazos, en
  vez del mismo bicho de siempre a lo grande.

Están dibujados en los **dos estilos**: el de bosque con su paleta y el de
hierro con los seis colores contados del doble plano del Amiga. El género y el
estilo siguen siendo ejes distintos. Y el ejemplo `cueva-de-hierro`, cuyo bicho
volador ya se llamaba murciélago, por fin **parece** un murciélago.

**Un perseguidor ya no se tira por los agujeros.** Al ponerle un jefe
perseguidor al segundo nivel salió un fallo del motor que llevaba ahí desde
siempre: `girar_en_borde` solo lo miraba el que patrulla, así que un
perseguidor seguía al jugador hasta el borde de un agujero y se caía del mapa.
Si el que se caía era el jefe —y matar al jefe es lo que termina ese nivel— el
nivel se quedaba **imposible de terminar**, sin nada en pantalla que lo
explicara. Ahora el perseguidor se planta en el borde y espera ahí; darse la
vuelta como el que patrulla sería dejar de perseguir. Con `girar_en_borde: no`
se sigue tirando, que a veces es lo que quieres.

## 1.11

**El marcador dice qué arma secundaria llevas.** Desde 1.7 un juego puede
llevar varias armas y cambiarlas cogiendo un objeto, pero el marcador seguía
poniendo `AMMO 05`, que no dice si eso son cinco cuchillos o cinco hachas: la
única forma de saberlo era tirar una y mirar qué salía. Ahora en el sitio de
`AMMO` va el nombre corto del arma que llevas puesta, y cambia al cambiarla.

```
KEYS 01/03 DAGA 05          <- llevas el cuchillo
KEYS 01/03 HACHA 05         <- coges el hacha y cambia
```

- Se pone con **`marcador:`** en cada arma de `secundarias:` (cinco letras, las
  que sabe escribir la fuente del marcador). Sin ponerlo salen las cinco
  primeras del nombre del arma, que casi nunca es lo que quieres (`cuchillo`
  sale como `CUCHI`), así que el andamiaje y los ejemplos lo traen puesto.
- Con **una sola** arma se queda como estaba, `AMMO 05`: no hay nada que
  distinguir. Si aun así el juego pone `marcador:`, manda el suyo.
- La cuenta va pegada al nombre en vez de en una columna fija, así el nombre
  más largo (`HACHA 99`) sigue cabiendo en los veinte huecos de la línea junto
  con las llaves.
- Sale en las seis máquinas y en el preview a la vez, porque las seis escriben
  esa línea con la misma función del motor.

**Y la línea de "lo que llevas" ya tiene pruebas.** Era la única del marcador
sin ninguna: se compila el motor con cuatro proyectos (sin arma, con una, con
una que trae nombre y con dos) y se comparan las veinte columnas una a una.

## 1.10

Dos deudas, ninguna función nueva.

**Los ejemplos que van en el ZIP estaban cinco versiones por detrás.** Su héroe
tenía seis poses (sin atacar, sin subir, sin agacharse y sin la de recibir un
golpe), su escenario no traía los tiles de escalera ni de antorcha, y el
`game.yaml` no sabía nada de agacharse ni de llevar más de un arma secundaria.
Compilaban y se jugaban —eso lo comprobaba la batería— pero quien abría el
ejemplo del kit veía el NeoPlat de antes.

- **`bosque-magico`**: héroe de once poses, agacharse, y **dos armas
  secundarias** (el cuchillo de siempre y el hacha, que sube y cae en arco),
  con el objeto que las cambia arriba de una plataforma.
- **`cueva-de-hierro`**: lo mismo en seis colores; sigue cabiendo en el doble
  plano del Amiga (7 colores de 32).

**Las pruebas del navegador que faltaban.** En 1.8 entró la principal en la
batería de siempre; las otras dos —dos jugadores en el preview, y guardar y
recuperar con el servidor detrás— seguían sólo en `make test-navegador`, que es
justo el sitio donde las cosas se quedan desfasadas sin que nadie se entere.
Ahora se ejecutan con las demás, y las dos comprobaciones que contaban
fotogramas a mano se los preguntan al proyecto, así que no vuelven a caducar.

## 1.9

**El botón de acción ya existe en el Amiga y en el Atari ST.** En esas dos
máquinas no estaba leído: el juego se compilaba igual, pero ahí **no se podía
ni atacar ni tirar el arma secundaria**. En las otras cuatro sí (Neo Geo botón
B, Mega Drive C, Jaguar B, X68000 B).

- **Amiga**: el **segundo botón** del joystick pasa a ser el de acción, y el
  disparo se queda con saltar *y* empezar la partida. Así un mando de un solo
  botón sigue sirviendo para todo menos para atacar, y el de dos gana el
  ataque.
- **Atari ST**: el joystick sólo tiene un botón (que salta y empieza), así que
  atacar va por teclado: <kbd>X</kbd> o <kbd>Control</kbd>.
- **En el preview**, la barra de teclas ya dice <kbd>X</kbd> atacar y
  <kbd>↑</kbd>+<kbd>X</kbd> arma secundaria —que era la pregunta que nadie
  podía contestar mirando la pantalla— y <kbd>↓</kbd> ahora dice también
  agacharse.
- Y hay **una tabla de mandos por máquina** en
  [docs/formato.md](docs/formato.md#los-mandos), que no existía.

Comprobado en los emuladores de verdad (PUAE y Hatari) midiendo el sonido del
disparo: al pulsar el botón de acción suena, y con otro botón cualquiera no.
Quitar el mapeo tira las dos pruebas.

## 1.8

**Lo que dibujas en el editor ya sale en el juego.** Era el fallo gordo: el
editor promete "pulsas E, dibujas, pulsas Enter y lo estás jugando", pero el
retoque no entraba en la hoja con la que se pinta la partida hasta darle a
*guardar*. Quien probaba un cambio veía el dibujo de antes y no entendía nada.
Ahora el dibujo entra en cuanto sueltas el ratón; guardar sigue siendo para
escribirlo en el PNG del proyecto.

**El personaje trae el juego de movimientos completo, y todo se toca desde el
editor:**

- **Agacharse en los dos géneros** (antes sólo en el de látigo): quieto,
  correr, saltar, caer, agacharse, atacar y la pose de recibir un golpe.
  Derecha e izquierda son la misma animación espejada, como hacen estas
  máquinas por hardware.
- **Las animaciones se editan en la pestaña dibujos**: las ocho ranuras del
  motor (`quieto`, `correr`, `saltar`, `caer`, `dano`, `atacar`, `subir`,
  `agachado`), con sus fotogramas, su velocidad y si se repiten. Se aplica al
  momento y al guardar entra en el `game.yaml` en una línea, respetando el
  resto del archivo. Antes el editor sólo enseñaba cinco ranuras y no dejaba
  cambiar ninguna.
- **Los ajustes de movimiento que faltaban** en el panel de física: retroceso,
  frames aturdido, velocidad al subir escaleras, alto de la caja agachado y el
  interruptor de agacharse.

Y las pruebas del navegador **entran en la batería de siempre**
(`tests/test_navegador.py`): estaban sólo en `make test-navegador`, nadie las
ejecutaba y se habían quedado desfasadas. Por ahí se coló justo este fallo.

## 1.7

**Varias armas secundarias, y el objeto que las cambia.** Había una y era la
misma toda la partida; en los clásicos el hacha, el agua bendita o la cruz
salen de un candelabro y cambian a lo que llevas.

- `secundarias:` admite **varias armas** con su nombre. Se empieza con la
  primera y se cambia cogiendo un objeto con `efecto: subarma`. `secundaria:`
  (una sola) sigue valiendo igual que antes.
- El arma es **de la partida**, como la munición, y al empezar un nivel se
  vuelve a la primera. Lo que ya está volando **se queda con el arma con la que
  salió**: cambiar de arma no convierte en hacha el cuchillo que va por el aire.
- **`a_la_vez`** limita cuántas puede haber volando: `1` es lo clásico (hasta
  que no cae la anterior no sale otra) y `3` es el "triple" de toda la vida.
  Sin ponerlo salen las que quepan, como hasta ahora.
- El género de látigo trae las dos: el cuchillo de serie (recto, tres a la vez)
  y **el hacha** (en arco, una a la vez, cuesta el doble y hace el doble), que
  está arriba de la escalera del primer nivel. Subir tiene premio.

De paso, un arreglo del empaquetador del X68000: dos dibujos con **los mismos
colores** gastaban dos bloques de paleta de los dieciséis que hay. Ahora los
comparten, igual que en la Neo Geo. El proyecto de ejemplo pasó de 15 bloques a
11, así que vuelve a haber sitio para dibujos nuevos.

## 1.6

**Agacharse.** Faltaba entero: en un juego de látigo uno se agacha para pegar
bajo y para esquivar lo que vuela a la altura de la cabeza, y el kit no lo
tenía en ninguna parte.

Con `agachado: si`, pulsar abajo en el suelo agacha al jugador: no anda y no
salta, pero **sí pega**, y el golpe sale a la altura de la rodilla. Lo que baja
es el **techo** de su caja —los pies se quedan donde están— así que lo que pasa
por encima deja de tocarle.

Esa decisión (bajar el techo en vez de mover al jugador) es la que hace que no
haya que tocar el dibujo en ninguna de las seis máquinas: todas pintan al
jugador en el mismo sitio de siempre y el fotograma de agachado ya viene
dibujado más abajo dentro del cuadro.

Sobre una plataforma de las de atravesar abajo sigue siendo para bajarse, en la
escalera manda la escalera, y al recibir un golpe se levanta. El género de
látigo lo trae puesto; el de plataformas, no, y ahí abajo hace lo de siempre.

## 1.5

**El látigo se ve.** Funcionaba —pegaba, alcanzaba más con cada mejora— pero en
pantalla no salía nada: el golpe era una caja invisible de 26 píxeles y el
héroe ni cambiaba de postura, porque el generador rellena con el fotograma 0
las poses que faltan y faltaban cuatro.

- **El arma es un dibujo**: con `tipo: golpe`, `sprite:` es el látigo, y se
  dibuja pegado al costado del jugador **sólo mientras el golpe hace daño**
  (pasada la `preparacion`), así que lo que se ve es exactamente lo que pega.
  Es una entidad más de la lista, no un caso aparte: por eso lo pintan las seis
  máquinas y el preview sin una línea de código por máquina, y por eso entra en
  el hash de la paridad y se compara frame a frame entre C y JavaScript.
- **La mejora se ve**: un fotograma por nivel del arma, dibujado de lo que mide
  su alcance (24, 36 y 48 px).
- **Cuatro poses nuevas del héroe** en los dos estilos de dibujo: el brazo
  echado atrás mientras dura la preparación, el brazo estirado al pegar, de
  espaldas en la escalera y la de recibir un golpe. Con `bucle: no` en la
  animación de atacar, la segunda pose se queda hasta el final en vez de volver
  a la primera a mitad del latigazo.

Comprobado en el emulador de Mega Drive (Genesis Plus GX) y en el preview: el
látigo sale de la mano, se afina y acaba en la punta dorada. Y en la traza, que
está en pantalla exactamente los nueve frames en los que hace daño.

## 1.4

**El género de látigo deja de sonar como el de plataformas.** Tenía la misma
cancioncilla de dos segundos, la antorcha del punto de control era muda y las
escaleras salían en un rincón del primer nivel y en ningún sitio más.

- **Música propia y mucho más larga**: `castillo` son 16 compases en re menor
  con la sensible do# de la escala menor armónica —tema, respuesta, un puente
  que baja por cromatismos y vuelta al tema—, 10,7 s antes de repetirse contra
  los 2,1 s de antes; `cripta` es la lenta, en la menor, 8,5 s. Las dos pistas
  de cada una duran exactamente lo mismo, así que melodía y bajo vuelven a
  empezar juntos. Las notas se escriben con un compás por línea, que es la
  única forma de contar los tiempos sin perderse.
- La música pasa a ser **cosa del género**, no de la plantilla: el de
  plataformas conserva la suya de cada estilo de dibujo.
- **La antorcha suena** al tocarla (`control:`), que es lo que te dice que ya no
  vuelves al principio del nivel. Y **romper un candelabro suena también en el
  estilo `hierro`**, donde faltaba el evento y era mudo.
- **Escaleras en los dos niveles**: la del segundo sube a la plataforma alta
  del final, donde ahora está la segunda mejora del látigo, así que hay que
  decidir si se pelea con el jefe arriba o abajo.

## 1.3

**Abrir NeoPlat con doble clic ya sirve para algo.** En Windows, hacer doble
clic en `ngplat.exe` abria una ventana negra que se cerraba sola: sin ninguna
orden escrita, el programa soltaba su lista de ordenes y salia, y la consola
desaparecia con ella antes de que diera tiempo a leer nada.

- Sin ordenes y con alguien delante sale un **asistente**: dice que juegos hay
  en la carpeta y ofrece crear uno nuevo, abrir el editor de uno que ya exista
  o compilarlo para su maquina.
- La ventana **espera a que se pulse Enter** antes de cerrarse, tambien cuando
  algo falla, asi que el error se puede leer.
- En una tuberia o dentro de un guion no ha cambiado nada: sigue saliendo la
  ayuda de siempre y no se queda nada esperando una respuesta.

## 1.2

**El Sharp X68000 entra en el kit**, y con todo lo que tienen las otras cinco
máquinas: se ve, se juega, suena y lleva dos mandos. Se portó midiendo el
hardware en el emulador, no copiando documentación, porque la que circula
resultó ser falsa en casi todo lo que importaba
([docs/x68000.md](docs/x68000.md) cuenta qué dijo cada medida).

- **Vídeo**: escenario en la capa de fondo del chip CYNTHIA, actores en
  sprites de 16×16 y el marcador en el plano de texto, a 320×224 como las
  demás. Sin parallax: no se consiguió enseñar las dos capas a la vez.
- **Sonido**: música y efectos por el YM2151 (ocho canales de FM), con las
  16 notas de la melodía reconocidas en el emulador, y muestras digitales por
  el ADPCM del MSM6258.
- **Dos jugadores**: puerto A del 8255 para el primero, puerto B para el
  segundo.
- **Salida**: un ejecutable `.X` de Human68k y un disquete `.xdf` (FAT12 con
  sectores de 1024 bytes) para copiarlo a un disco de sistema.

Además, tres arreglos que salieron por el camino:

- El título del juego salía cortado en el marcador ("A DE HIERRO" en vez de
  "CUEVA DE HIERRO"): la barra de vida en blanco lo borraba.
- El frame iba un 2,4% rápido (259 líneas de temporizado en vez de 266).
- El banco de pruebas no contestaba a `SET_FRAME_TIME_CALLBACK`, y sin eso hay
  cores de libretro cuyo tiempo interno no avanza.

## 0.1

La primera: Neo Geo, Mega Drive, Amiga, Atari Jaguar y Atari ST, el preview
jugable en el navegador y el editor de niveles.
