# Cambios

Cada versión del kit, de la más nueva a la más vieja. La versión sube cada vez
que se cambia algo que se reparte, y va en el nombre de los paquetes
(`neoplat-kit-1.3.zip`) y en `ngplat --version`: así se sabe qué se está
probando sin abrir nada.

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
