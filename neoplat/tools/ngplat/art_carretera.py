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
        "v": (120, 200, 232, 255),    # la luna
        "t": (96, 64, 40, 255),       # el tronco
        "h": (56, 152, 72, 255),      # las hojas
        "p": (232, 232, 240, 255),    # el poste del cartel
        "a": (232, 176, 32, 255),     # la chapa del cartel
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
    },
}

# El coche del trafico: la misma chapa en azul. Se hace cambiando dos colores y
# no dibujandolo otra vez, porque un coche visto de culo es un coche visto de
# culo: lo unico que tiene que cambiar es de que color es.
TRAFICO = {"c": (64, 96, 216, 255), "o": (32, 48, 128, 255)}

# --- el coche, visto de culo ---------------------------------------------
#
# Tres poses. Recto es el de siempre; girando lleva la carroceria inclinada un
# pixel y las ruedas de fuera mas anchas, que es lo que hace que se vea que
# estas tumbando el coche; en el trompo se ve de lado, que es la unica forma de
# que un dibujo de 16x16 diga "estoy dando vueltas".
_RECTO = (
    "................",
    "................",
    "....vvvvvvvv....",
    "...vvvvvvvvvv...",
    "...cccccccccc...",
    "..cccccccccccc..",
    "..cccccccccccc..",
    ".nnccccccccccnn.",
    ".nnccccccccccnn.",
    ".nncoooooooocnn.",
    ".nnclooooooLcnn.",
    ".nncccccccccc nn",
    "..oooooooooooo..",
    "..n..........n..",
    "................",
    "................",
)

_GIRA = (
    "................",
    "................",
    ".....vvvvvvvv...",
    "....vvvvvvvvvv..",
    "....cccccccccc..",
    "...cccccccccccc.",
    "...cccccccccccc.",
    ".nnnccccccccccn.",
    ".nnnccccccccccn.",
    ".nnncoooooooocn.",
    ".nnnclooooooLcn.",
    ".nnncccccccccc..",
    "...oooooooooo...",
    "...n........n...",
    "................",
    "................",
)

_TROMPO = (
    "................",
    "................",
    "................",
    "..vvvv..........",
    ".cccccccc.......",
    "cccccccccccc....",
    "cccccccccccccc..",
    "nnccccccccccccnn",
    "nnccccccccccccnn",
    "nnoooooooooooonn",
    ".loooooooooooL..",
    "..oooooooooo....",
    "....oooooo......",
    "................",
    "................",
    "................",
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
    poses = (_RECTO, _GIRA, _TROMPO)
    return {
        "graficos/coche.png": _hoja(poses, col),
        "graficos/rival.png": _hoja(poses, trafico),
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
