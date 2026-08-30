# Cambios

Cada versión del kit, de la más nueva a la más vieja. La versión sube cada vez
que se cambia algo que se reparte, y va en el nombre de los paquetes
(`neoplat-kit-1.6.zip`) y en `ngplat --version`: así se sabe qué se está
probando sin abrir nada.

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
