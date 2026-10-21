# El manual de NeoPlat

Esto es el índice. El manual son **once documentos**: el
[README](../README.md) del kit y los diez de esta carpeta. Están pensados para
leerse en un orden, y éste es el orden.

El castellano es el original. En [`en/`](en/README.md) está la traducción al
inglés, que se regenera cuando cambia el castellano. Y en
[`dist/`](../dist) salen los dos PDF —`neoplat-manual-es.pdf` y
`neoplat-manual-en.pdf`— con `make manual`: es el mismo texto, encuadernado.

## Por dónde empezar

**Si nunca has usado el kit**, en este orden:

| | qué es | para qué sirve |
|---|---|---|
| 1 | [README](../README.md) | **la portada**: qué es NeoPlat, qué máquinas saca, cómo se instala y qué órdenes hay. Si sólo vas a leer una cosa, lee ésta |
| 2 | [tutorial.md](tutorial.md) | **tu primer juego en 10 minutos**, y después un capítulo por género: un juego de arriba, una mazmorra, una de pelea, una aventura, un castillo isométrico, un templo de kung-fu, una aventura gráfica y uno de conducir |
| 3 | [editor.md](editor.md) | **el editor**, que es el propio preview: mapas, dibujos, enemigos y música sin salir del navegador |
| 4 | [formato.md](formato.md) | **la referencia de `game.yaml`**: las 51 secciones, con cada clave, su valor de serie y sus topes. Es la que se consulta, no la que se lee de cabo a rabo |

**Si lo que quieres es entender cómo funciona por dentro**, hay un documento
por máquina. Todos están escritos igual: el hardware en cuatro líneas, qué hace
NeoPlat con él, lo que costó averiguar y lo que aún no hace.

| | la máquina | lo más suyo |
|---|---|---|
| [neogeo.md](neogeo.md) | Neo Geo (AES/MVS) | el escenario **no tiene fondo**: son columnas de sprites. Y es la única que encoge sprites por hardware |
| [megadrive.md](megadrive.md) | Mega Drive / Genesis | dos planos de tiles, y el scroll por línea con el que se pinta la carretera |
| [amiga.md](amiga.md) | Amiga (OCS/ECS), **A1200** (AGA) y **CD32** | ni tiles ni sprites: un mapa de bits, el blitter y el copper. Y lo que cabe en los 190 KB de un A500 |
| [atarist.md](atarist.md) | Atari ST | la más espartana: **nada** que le eche una mano, así que todo lo mueve la CPU. Dibuja a 25 y simula a 50 |
| [jaguar.md](jaguar.md) | Atari Jaguar | una lista de objetos que el chip recorre, y el sonido escrito **para el DSP** |
| [x68000.md](x68000.md) | Sharp X68000 | el que más costó: el CRTC, el BG y un YM2151 |

Y uno transversal:

| | qué cuenta |
|---|---|
| [sonido.md](sonido.md) | las notas se escriben **una vez** y las tocan siete chips distintos. Los ocho timbres de FM, las muestras digitales y, sobre todo, **cómo se comprueba que suena**: las pruebas capturan lo que sale por el altavoz y reconocen las notas una a una |

## Dos cosas que conviene saber antes de leer

**Las cifras del manual están medidas, no estimadas.** Cuando una página dice
que un frame cuesta 196.626 ciclos de los 200.000, o que el ejecutable mide
189 KB de los 190 que deja un A500, es porque hay una prueba que lo mide y que
falla si deja de ser verdad. Donde algo no se ha podido comprobar, lo dice.

**Un frame es un paso de la simulación**, y lo que dura lo pone el retrazo de
cada máquina: 60 por segundo en la Neo Geo, la Mega Drive, la Jaguar y el
X68000, y 50 en el Amiga, el A1200, el CD32 y el Atari ST, que son PAL. Un
salto mide los mismos píxeles en las siete; en las PAL se tarda un sexto más en
darlo.

## Si lo que buscas es una cosa concreta

| busco… | está en |
|---|---|
| una clave del `game.yaml` | [formato.md](formato.md) |
| qué géneros hay y qué trae cada uno | [README, «Cómo es un juego»](../README.md#cómo-es-un-juego) |
| las teclas del editor | [editor.md](editor.md) |
| cómo se escribe la música | [formato.md, `musica`](formato.md#musica) y [sonido.md](sonido.md) |
| por qué mi juego no cabe en un A500 | [formato.md, `amiga_ram`](formato.md#amiga_ram-a-qué-amiga-apunta-el-juego) y [amiga.md](amiga.md) |
| qué no hace el kit todavía | [README, «Estado y limitaciones»](../README.md#estado-y-limitaciones) |
| qué cambió en cada versión | [CAMBIOS.md](../CAMBIOS.md) |
