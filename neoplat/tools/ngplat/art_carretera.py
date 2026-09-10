"""Los dibujos del genero de carretera (los juegos de conducir).

Aqui no vale ninguno de los dibujos que ya habia, y por un motivo sencillo: en
este genero **la pantalla no ensena el mapa**. La calzada, el arcen, la hierba
y las rayas no son tiles: son siete colores que pinta el motor linea a linea
(ver `carretera:` en el game.yaml). Lo unico que se dibuja son las cosas que
estan **sobre** la carretera, y todas se ven desde detras:

  - el coche del jugador, visto de culo, con tres poses: recto, girando y
    dando vueltas;
  - los coches del trafico, que se ven igual pero de otro color, porque lo
    unico que importa de ellos es distinguirlos del tuyo de un vistazo;
  - las palmeras y los carteles del borde, que es lo que hace que se note la
    velocidad cuando la carretera es recta.

Como en el resto del kit se escriben con **patrones**: una lista de filas de
texto, una letra por pixel. Un coche visto de culo son cuatro trazos, y
escrito asi se ve en el propio codigo lo que sale.

Los dibujos son pequenos a proposito -16x16 y 32x32-. En la carretera todo se
encoge con la distancia, asi que un dibujo grande solo sirve para el metro que
tienes delante; lo que hace falta es que se lea a diez pixeles de alto.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .art import patron
from .png import Image

RGBA = Tuple[int, int, int, int]

# Los colores del genero. Dos juegos: el coche del jugador (rojo) y el del
# trafico (azul), para que a cien por hora se sepa cual eres tu sin pensarlo.
COLORES: Dict[str, Dict[str, RGBA]] = {
    "bosque": {
        "c": (208, 48, 48, 255),      # la chapa
        "o": (128, 24, 24, 255),      # la sombra de la chapa
        "l": (248, 200, 96, 255),     # los faros y los pilotos
        "n": (32, 32, 40, 255),       # las ruedas y el negro
        "v": (120, 200, 232, 255),    # el parabrisas
        "t": (96, 64, 40, 255),       # el tronco
        "h": (56, 152, 72, 255),      # las hojas
        "p": (232, 232, 240, 255),    # el poste del cartel
        "a": (232, 176, 32, 255),     # la chapa del cartel
        # los dos que van dentro
        "f": (240, 200, 168, 255),    # la piel
        "R": (248, 216, 96, 255),     # la melena, rubia
        "M": (72, 48, 40, 255),       # el pelo de el, moreno
        "s": (248, 248, 248, 255),    # su camisa
        "S": (96, 168, 232, 255),     # el vestido de ella
    },
    "hierro": {
        "c": (200, 64, 48, 255),
        "o": (112, 32, 24, 255),
        "l": (232, 208, 128, 255),
        "n": (24, 24, 32, 255),
        "v": (104, 160, 200, 255),
        "t": (88, 64, 48, 255),
        "h": (64, 128, 80, 255),
        "p": (216, 216, 224, 255),
        "a": (216, 168, 48, 255),
        "f": (224, 184, 152, 255),
        "R": (232, 200, 96, 255),
        "M": (64, 48, 40, 255),
        "s": (232, 232, 232, 255),
        "S": (88, 152, 208, 255),
    },
}

# El coche del trafico: la misma chapa en azul. Se hace cambiando dos colores y
# no dibujandolo otra vez, porque un coche visto de culo es un coche visto de
# culo: lo unico que tiene que cambiar es de que color es.
TRAFICO = {"c": (64, 96, 216, 255), "o": (32, 48, 128, 255)}

# --- el coche, visto de culo ---------------------------------------------
#
# Un descapotable de 32x32 con los dos dentro: el conduce y ella va al lado con
# **la melena al viento**. La melena tiene tres posiciones y se pasan mas
# deprisa cuanto mas corre el coche (lo lleva np_player_update_carretera), asi
# que parada no se mueve y a tope va suelta. Eso es lo que hace que el coche se
# vea rapido aunque el coche, en pantalla, no se mueva del sitio.
#
# El coche va de culo y ocupa lo ancho: a la distancia a la que se ve, lo que
# se lee son la silueta, los dos pilotos rojos y las dos cabezas.

# El cuerpo del coche, que es igual en todas las poses. Se escribe una vez y
# encima se le pegan las cabezas y la melena, que es lo unico que cambia.
#
# Mide 64x32 y no 32x32 a proposito: es el unico dibujo que el jugador tiene
# delante todo el rato y clavado en el sitio, asi que es el que se mira. Con 32
# no se distinguian los dos que van dentro, y sin eso no hay descapotable: hay
# una mancha roja.
_CUERPO = (
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "..........vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv..................",
    ".........vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv.................",
    "........cccccccccccccccccccccccccccccccccccccc................",
    ".......cccccccccccccccccccccccccccccccccccccccc...............",
    "......cccccccccccccccccccccccccccccccccccccccccc..............",
    ".....cccccccccccccccccccccccccccccccccccccccccccc.............",
    "...nncccccccccccccccccccccccccccccccccccccccccccnn............",
    "...nncccccccccccccccccccccccccccccccccccccccccccnn............",
    "...nncccccccccccccccccccccccccccccccccccccccccccnn............",
    "...nnccooooooooooooooooooooooooooooooooooooooooccnn...........",
    "...nnccooooooooooooooooooooooooooooooooooooooooccnn...........",
    "...nnccollllooooooooooooooooooooooooooollllooccnn.............",
    "...nnccollllooooooooooooooooooooooooooollllooccnn.............",
    "...nnccooooooooooooooooooooooooooooooooooooooooccnn...........",
    "...nnoooooooooooooooooooooooooooooooooooooooooonn.............",
    "....nnoooooooooooooooooooooooooooooooooooooooonn..............",
    ".....nn..................................nn...................",
    "................................................................",
    "................................................................",
    "................................................................",
)

# El, al volante: cabeza, pelo corto y hombros. No cambia entre poses.
_EL = (
    (4, "...MMMMMM..."),
    (5, "..MMMMMMMM.."),
    (6, "..MMffffMM.."),
    (7, "..MffffffM.."),
    (8, "...ffffff..."),
    (9, "....ffff...."),
    (10, "..ssssssss.."),
    (11, ".ssssssssss."),
)

# Ella, al lado. La melena es lo unico que cambia.
_ELLA_CABEZA = (
    (4, "...RRRRRR..."),
    (5, "..RRRRRRRR.."),
    (6, "..RRffffRR.."),
    (7, "..RffffffR.."),
    (8, "...ffffff..."),
    (9, "....ffff...."),
    (10, "..SSSSSSSS.."),
    (11, ".SSSSSSSSSS."),
)

# Y la melena que sale por detras, hacia la derecha. Tres posiciones: recogida,
# levantada y suelta del todo.
_MELENA = (
    (
        (6, 10, "RRR"),
        (7, 10, "RRRR"),
        (8, 10, "RRRR"),
        (9, 9, "RRR"),
        (10, 9, "RR"),
    ),
    (
        (4, 10, "RRR"),
        (5, 10, "RRRRRR"),
        (6, 11, "RRRRRR"),
        (7, 11, "RRRRR"),
        (8, 10, "RRR"),
        (9, 10, "RR"),
    ),
    (
        (2, 11, "RRRR"),
        (3, 11, "RRRRRRR"),
        (4, 12, "RRRRRRRR"),
        (5, 12, "RRRRRRR"),
        (6, 12, "RRRR"),
        (7, 11, "RR"),
    ),
)

# Donde va cada uno dentro del coche, en columnas.
_SITIO_EL = 12
_SITIO_ELLA = 32
_ANCHO = 64
_ALTO = 32


def _coche(melena: int, ladeo: int = 0):
    """El coche entero con la melena en la posicion que se pida.

    `ladeo` mueve la carroceria un pixel a un lado: es la pose de estar
    girando, y con el espejo del motor vale para los dos lados."""
    filas = [list(f.ljust(_ANCHO)[:_ANCHO]) for f in _CUERPO]

    def pegar(fila, columna, trozo):
        for i, ch in enumerate(trozo):
            x = columna + i
            if ch != "." and 0 <= x < _ANCHO and 0 <= fila < _ALTO:
                filas[fila][x] = ch

    for fila, trozo in _EL:
        pegar(fila, _SITIO_EL + ladeo, trozo)
    for fila, trozo in _ELLA_CABEZA:
        pegar(fila, _SITIO_ELLA + ladeo, trozo)
    for fila, salto, trozo in _MELENA[melena]:
        pegar(fila, _SITIO_ELLA + salto + ladeo, trozo)
    if ladeo:
        # la carroceria se inclina: se corren las filas de en medio
        for f in range(14, 22):
            fuente = filas[f]
            filas[f] = ([fuente[0]] * ladeo + fuente[:-ladeo] if ladeo > 0
                        else fuente[-ladeo:] + [fuente[-1]] * (-ladeo))
    return tuple("".join(f) for f in filas)


# Y el trompo: el coche visto de lado, dando vueltas. Con un dibujo de 32x32
# es la unica forma de que se lea "estoy girando" y no "estoy parado".
_TROMPO = (
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "..................MMMM..........RRRRRR..........................",
    ".................ffffff........RRffffRR.........................",
    "................ffffffff......RRffffffR.........................",
    "..............vvvvvvvvvvvvvvvvvvvvvv............................",
    ".............cccccccccccccccccccccccccc.........................",
    "............cccccccccccccccccccccccccccc........................",
    "..........nncccccccccccccccccccccccccccccnn.....................",
    "..........nncccccccccccccccccccccccccccccnn.....................",
    "..........nnooooooooooooooooooooooooooooonn.....................",
    "..........nnollllooooooooooooooooolllloonn......................",
    "..........nnooooooooooooooooooooooooooonn.......................",
    "...........nn......................nn...........................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
    "................................................................",
)


# --- el borde de la carretera --------------------------------------------
_PALMERA = (
    "................",
    "....hh..hh......",
    "..hhhhhhhhhh....",
    ".hhhhhhhhhhhh...",
    "hhhh..tt..hhhh..",
    "hh....tt....hh..",
    "......tt........",
    "......tt........",
    "......tt........",
    ".....ttt........",
    ".....ttt........",
    "....tttt........",
    "....tttt........",
    "....tttt........",
    "...ttttt........",
    "...ttttt........",
)

_CARTEL = (
    "................",
    "..aaaaaaaaaaaa..",
    "..annnnnnnnnna..",
    "..anaaaaaaaana..",
    "..anaaaaaaaana..",
    "..anaaaaaaaana..",
    "..annnnnnnnnna..",
    "..aaaaaaaaaaaa..",
    ".......pp.......",
    ".......pp.......",
    ".......pp.......",
    ".......pp.......",
    ".......pp.......",
    ".......pp.......",
    ".......pp.......",
    ".......pp.......",
)


def _hoja(frames, colores: Dict[str, RGBA]) -> Image:
    """Una hoja de fotogramas en fila, que es como los pide el compilador."""
    ancho = len(frames[0][0])
    alto = len(frames[0])
    hoja = Image(ancho * len(frames), alto, [(0, 0, 0, 0)] * (ancho * len(frames) * alto))
    for i, filas in enumerate(frames):
        trozo = patron(list(filas), colores)
        for y in range(alto):
            for x in range(ancho):
                pixel = trozo.get(x, y)
                if pixel[3]:
                    hoja.set(i * ancho + x, y, pixel)
    return hoja


def todos(estilo: str) -> Dict[str, Image]:
    """Todos los dibujos del genero, por nombre de archivo."""
    col = dict(COLORES.get(estilo, COLORES["bosque"]))
    trafico = dict(col)
    trafico.update(TRAFICO)
    # El orden de los fotogramas es el que espera el motor: quieto (recto),
    # correr (girando) y dano (el trompo). No son nombres raros: son las
    # mismas ranuras de animacion de los otros nueve generos, usadas para lo
    # que hace falta aqui.
    # Cuatro fotogramas: tres de ir con la melena en sus tres posiciones, y el
    # trompo.
    #
    # No hay pose de "girando", y no por ahorrar: el coche se ve **de culo**,
    # asi que el motor no puede espejarlo para el otro lado sin cambiar de
    # asiento a los dos que van dentro -y eso se ve al momento-. El volante se
    # lee porque el coche entero se corre a un lado (np_carretera_coche), que
    # es lo que hace de verdad un coche al girar.
    poses = tuple(_coche(m) for m in range(3)) + (_TROMPO,)
    # El trafico es el mismo coche **sin nadie dentro** y de otro color: lo
    # unico que importa de un coche al que vas a adelantar es distinguirlo del
    # tuyo de un vistazo a cien por hora. Un solo fotograma: no hace nada.
    rival = (_CUERPO,)
    return {
        "graficos/coche.png": _hoja(poses, col),
        "graficos/rival.png": _hoja(rival, trafico),
        "graficos/palmera.png": patron(list(_PALMERA), col),
        "graficos/cartel.png": patron(list(_CARTEL), col),
        # Y los cuatro tiles del mapa. En este genero **no se ven**: el mapa es
        # el trazado y lo que se dibuja es la carretera en perspectiva. Estan
        # porque el compilador pide una imagen de tiles, y porque en el editor
        # el trazado se ve con ellos: asfalto gris, hierba verde, quitamiedos
        # rojo y la meta a cuadros.
        "graficos/tiles.png": _tiles(),
    }


def _tiles() -> Image:
    """Los cuatro tiles del trazado, en fila: asfalto, hierba, valla y meta.

    Se ven **solo en el editor**, donde el mapa es el plano del circuito. En el
    juego no se dibuja ni uno: la carretera son colores, no dibujos."""
    colores = ((72, 72, 80, 255), (56, 120, 64, 255),
               (176, 48, 40, 255), (232, 232, 240, 255))
    hoja = Image(16 * 4, 16, [(0, 0, 0, 0)] * (16 * 4 * 16))
    for i, base in enumerate(colores):
        for y in range(16):
            for x in range(16):
                color = base
                if i == 3 and ((x // 4) + (y // 4)) % 2:
                    color = (32, 32, 40, 255)       # la meta, a cuadros
                elif i == 2 and y % 8 < 3:
                    color = (232, 232, 240, 255)    # la valla, a rayas
                hoja.set(i * 16 + x, y, color)
    return hoja
