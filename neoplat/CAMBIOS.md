# Cambios

Cada versión del kit, de la más nueva a la más vieja. La versión sube cada vez
que se cambia algo que se reparte, y va en el nombre de los paquetes
(`neoplat-kit-1.12.zip`) y en `ngplat --version`: así se sabe qué se está
probando sin abrir nada.

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
