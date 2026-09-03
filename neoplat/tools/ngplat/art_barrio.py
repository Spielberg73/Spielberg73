"""Los dibujos del genero de tortas (vista de cinta).

Un juego de tortas se ve **de lado**, como el de plataformas, pero se anda por
una franja de suelo con profundidad: los actores se pisan unos a otros y hay un
"detras" de verdad. Eso cambia lo que hay que dibujar:

  - el heroe con su chaqueta, en ocho fotogramas: quieto, andando, el punetazo,
    el remate -que es el que tumba-, el salto y el golpe recibido;
  - los matones, que son a quienes se les pega: uno flaco y otro grande;
  - el jefe, con su chupa y su barba;
  - el bate, que alarga el brazo, y el pollo, que cura;
  - los barriles, que se rompen y sueltan lo que llevan dentro;
  - y una calle: asfalto, acera, bordillo, muro de ladrillo, valla, alcantarilla
    (que es peligro) y la salida.

Como en el resto del kit, los dibujos se escriben con **patrones**: una lista
de filas de texto, una letra por pixel. Asi se ve en el propio codigo lo que
sale, y cambiar un color es cambiar una letra.

Los colores se piden por nombre y cada estilo los resuelve como quiera: el de
bosque tira de la paleta larga y el de hierro se queda con sus seis, que es lo
que cabe en el doble plano del Amiga.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .art import Lienzo, patron
from . import art_hierro
from .png import Image

RGBA = Tuple[int, int, int, int]

COLORES: Dict[str, Dict[str, RGBA]] = {
    "bosque": {
        "a": (72, 112, 208, 255),     # chaqueta del heroe
        "A": (44, 72, 152, 255),      # chaqueta en sombra
        "p": (248, 200, 152, 255),    # piel
        "P": (200, 152, 112, 255),    # piel en sombra
        "b": (32, 28, 36, 255),       # contorno, pelo y botas
        "v": (88, 96, 128, 255),      # vaqueros
        "V": (56, 64, 96, 255),       # vaqueros en sombra
        "r": (200, 72, 64, 255),      # el maton flaco
        "R": (136, 44, 40, 255),      # y su sombra
        "g": (112, 168, 96, 255),     # el maton grande
        "G": (72, 116, 64, 255),
        "m": (192, 200, 216, 255),    # metal (el bate, las farolas)
        "o": (248, 200, 72, 255),     # oro: la salida y los avisos
        "n": (64, 62, 72, 255),       # asfalto
        "N": (52, 50, 60, 255),       # asfalto oscuro
        "c": (168, 152, 136, 255),    # acera
        "C": (128, 116, 104, 255),    # acera en sombra
        "l": (152, 88, 72, 255),      # ladrillo
        "L": (108, 60, 52, 255),      # ladrillo oscuro
        "w": (236, 232, 224, 255),    # blanco (camisetas, brillos)
    },
    "hierro": {
        "a": art_hierro.ROCA, "A": art_hierro.ROCA2,
        "p": art_hierro.CLARO, "P": art_hierro.ROCA,
        "b": art_hierro.LINEA,
        "v": art_hierro.ROCA2, "V": art_hierro.LINEA,
        "r": art_hierro.ROJO, "R": art_hierro.LINEA,
        "g": art_hierro.ROCA, "G": art_hierro.ROCA2,
        "m": art_hierro.CLARO, "o": art_hierro.ORO,
        "n": art_hierro.ROCA2, "N": art_hierro.LINEA,
        "c": art_hierro.ROCA, "C": art_hierro.ROCA2,
        "l": art_hierro.ROCA2, "L": art_hierro.LINEA,
        "w": art_hierro.CLARO,
    },
}


def _hoja(frames: List[Tuple[str, ...]], estilo: str) -> Image:
    """Pega los fotogramas de un patron en una hoja de 16 pixeles de alto."""
    colores = COLORES[estilo]
    hoja = Lienzo(16 * len(frames), 16)
    for i, frame in enumerate(frames):
        hoja.blit(i * 16, 0, patron(list(frame), colores))
    return hoja.image


# --- el heroe -------------------------------------------------------------
#
# Ocho fotogramas, en el orden que pide el game.yaml del genero:
#   0        quieto
#   1, 2     andando
#   3        el punetazo
#   4        el remate (el que tumba)
#   5        saltando
#   6        el golpe recibido
#   7        agarrando
#
# Mira a la derecha: el motor lo espeja para el otro lado, como en las demas
# maquinas hace el hardware.

_H_QUIETO = (
    "................",
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....pppbpp.....",
    ".....ppppp......",
    "....aaaaaaa.....",
    "...paaaaaaap....",
    "...paaaaaaap....",
    "....aaaaaaa.....",
    ".....vvvvv......",
    ".....vv.vv......",
    ".....vv.vv......",
    "....bbb.bbb.....",
    "................",
)

_H_ANDA_1 = (
    "................",
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....pppbpp.....",
    ".....ppppp......",
    "...aaaaaaa......",
    "..paaaaaaaap....",
    "...aaaaaaaap....",
    "....aaaaaa......",
    "....vvvvvv......",
    "...vv...vv......",
    "..vv.....vv.....",
    "..bbb....bbb....",
    "................",
)

_H_ANDA_2 = (
    "................",
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....pppbpp.....",
    ".....ppppp......",
    "....aaaaaaa.....",
    "...paaaaaaap....",
    "....aaaaaaa.....",
    ".....aaaaa......",
    ".....vvvvv......",
    "....vv..vv......",
    "....vv..vv......",
    "...bbb..bbb.....",
    "................",
)

_H_PUNO = (
    "................",
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....pppbpp.....",
    ".....ppppp......",
    "....aaaaaaa.....",
    "...paaaaaaaappp.",
    "...paaaaaaa.....",
    "....aaaaaaa.....",
    ".....vvvvv......",
    ".....vv.vv......",
    ".....vv.vv......",
    "....bbb.bbb.....",
    "................",
)

_H_REMATE = (
    "................",
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    "....ppppbpp.....",
    "....pppppp......",
    "...aaaaaaaa.....",
    "..paaaaaaaaappp.",
    "..paaaaaaaaa....",
    "...aaaaaaaa.....",
    "....vvvvvv......",
    "...vv...vv......",
    "..vv....vv......",
    "..bbb...bbb.....",
    "................",
)

_H_SALTA = (
    "................",
    "................",
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    "..p..pppbpp..p..",
    "..pa.ppppp..ap..",
    "..paaaaaaaaaap..",
    "...aaaaaaaaa....",
    "....aaaaaaa.....",
    ".....vvvvv......",
    "....vv...vv.....",
    "...bb.....bb....",
    "................",
    "................",
)

_H_DANO = (
    "................",
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....ppbbpp.....",
    ".....ppppp......",
    "...aaaaaaa......",
    "..paaaaaaa......",
    "..paaaaaaa......",
    "...aaaaaa.......",
    "....vvvvv.......",
    "....vv.vv.......",
    "...vv..vv.......",
    "..bbb..bbb......",
    "................",
)

_H_AGARRA = (
    "................",
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....pppbpp.....",
    ".....ppppp......",
    "....aaaaaaa.....",
    "...paaaaaaappp..",
    "...paaaaaaappp..",
    "....aaaaaaa.....",
    ".....vvvvv......",
    ".....vv.vv......",
    "....vv..vv......",
    "...bbb..bbb.....",
    "................",
)

HEROE = (_H_QUIETO, _H_ANDA_1, _H_ANDA_2, _H_PUNO, _H_REMATE, _H_SALTA,
         _H_DANO, _H_AGARRA)


def _maton(uno: str, dos: str) -> Tuple[Tuple[str, ...], ...]:
    """Un maton, en cuatro fotogramas: quieto, dos de andar y el golpe.

    Los dos matones del juego son el mismo dibujo con otro color de camiseta,
    que es lo que hacian los recreativos: no es pereza, es que asi el jugador
    los distingue de un vistazo y el cartucho no paga dos veces.
    """
    quieto = (
        "................",
        "................",
        "......bbbb......",
        ".....bbbbbb.....",
        ".....bppppb.....",
        ".....ppbbpp.....",
        ".....ppppp......",
        "....%s%s%s%s%s%s%s....." % ((uno,) * 7),
        "...p%s%s%s%s%s%s%sp...." % ((uno,) * 7),
        "...p%s%s%s%s%s%s%sp...." % ((dos,) * 7),
        "....%s%s%s%s%s%s%s....." % ((dos,) * 7),
        ".....vvvvv......",
        ".....vv.vv......",
        ".....vv.vv......",
        "....bbb.bbb.....",
        "................",
    )
    anda1 = (
        "................",
        "................",
        "......bbbb......",
        ".....bbbbbb.....",
        ".....bppppb.....",
        ".....ppbbpp.....",
        ".....ppppp......",
        "...%s%s%s%s%s%s%s......" % ((uno,) * 7),
        "..p%s%s%s%s%s%s%s%sp...." % ((uno,) * 8),
        "...%s%s%s%s%s%s%s%sp...." % ((dos,) * 8),
        "....%s%s%s%s%s%s......" % ((dos,) * 6),
        "....vvvvvv......",
        "...vv...vv......",
        "..vv.....vv.....",
        "..bbb....bbb....",
        "................",
    )
    anda2 = (
        "................",
        "................",
        "......bbbb......",
        ".....bbbbbb.....",
        ".....bppppb.....",
        ".....ppbbpp.....",
        ".....ppppp......",
        "....%s%s%s%s%s%s%s....." % ((uno,) * 7),
        "...p%s%s%s%s%s%s%sp...." % ((uno,) * 7),
        "....%s%s%s%s%s%s%s....." % ((dos,) * 7),
        ".....%s%s%s%s%s......" % ((dos,) * 5),
        ".....vvvvv......",
        "....vv..vv......",
        "....vv..vv......",
        "...bbb..bbb.....",
        "................",
    )
    dano = (
        "................",
        "................",
        ".......bbbb.....",
        "......bbbbbb....",
        "......bppppb....",
        "......ppbbpp....",
        "......ppppp.....",
        "......%s%s%s%s%s%s%s..." % ((uno,) * 7),
        ".....p%s%s%s%s%s%s%s..." % ((uno,) * 7),
        ".....p%s%s%s%s%s%s%s..." % ((dos,) * 7),
        "......%s%s%s%s%s%s...." % ((dos,) * 6),
        "......vvvvv.....",
        ".....vv..vv.....",
        "....vv....v.....",
        "...bbb...bb.....",
        "................",
    )
    return (quieto, anda1, anda2, dano)


# --- el jefe --------------------------------------------------------------
#
# Mas ancho, con chupa y barba: se ve de lejos que ese no es uno mas.

_J_QUIETO = (
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....ppbbpp.....",
    ".....pppppp.....",
    "......bbbb......",
    "...nnnnnnnnn....",
    "..pnnnnnnnnnp...",
    "..pnnnwwwnnnp...",
    "...nnnnnnnnn....",
    "....nnnnnnn.....",
    "....vvv.vvv.....",
    "....vvv.vvv.....",
    "...bbbb.bbbb....",
    "................",
)

_J_ANDA_1 = (
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....ppbbpp.....",
    ".....pppppp.....",
    "......bbbb......",
    "..nnnnnnnnn.....",
    ".pnnnnnnnnnnp...",
    ".pnnnwwwnnnnp...",
    "..nnnnnnnnn.....",
    "...nnnnnnn......",
    "...vvv..vvv.....",
    "..vvv....vvv....",
    "..bbb.....bbb...",
    "................",
)

_J_ANDA_2 = (
    "................",
    "......bbbb......",
    ".....bbbbbb.....",
    ".....bppppb.....",
    ".....ppbbpp.....",
    ".....pppppp.....",
    "......bbbb......",
    "...nnnnnnnnn....",
    "..pnnnnnnnnnp...",
    "...nnnwwwnnn....",
    "....nnnnnnn.....",
    ".....nnnnn......",
    "....vvv.vvv.....",
    "....vvv.vvv.....",
    "....bbb.bbb.....",
    "................",
)

_J_DANO = (
    "................",
    ".......bbbb.....",
    "......bbbbbb....",
    "......bppppb....",
    "......ppbbpp....",
    "......pppppp....",
    ".......bbbb.....",
    ".....nnnnnnnn...",
    "....pnnnnnnnn...",
    "....pnnnwwwnn...",
    ".....nnnnnnnn...",
    "......nnnnnn....",
    ".....vvv.vvv....",
    "....vvv...vv....",
    "...bbb....bb....",
    "................",
)

JEFE = (_J_QUIETO, _J_ANDA_1, _J_ANDA_2, _J_DANO)

# --- lo que se coge y lo que se rompe -------------------------------------

_BATE = (
    "................",
    "................",
    "................",
    "..............mm",
    ".............mmm",
    "............mmm.",
    "...........mmm..",
    "..........mmm...",
    ".........mmm....",
    "........mmm.....",
    ".......bbb......",
    "......bbb.......",
    ".....bbb........",
    "................",
    "................",
    "................",
)

_BATE_2 = (
    "................",
    "................",
    "................",
    "................",
    ".............mmm",
    "............mmmm",
    "...........mmm..",
    "..........mmm...",
    ".........mmm....",
    "........bbb.....",
    ".......bbb......",
    "......bbb.......",
    "................",
    "................",
    "................",
    "................",
)

_POLLO = (
    "................",
    "................",
    "................",
    ".....bbbb.......",
    "....bwwwwb......",
    "...bwwwwwwb.....",
    "..bwwoowwwwb....",
    "..bwwwwwwwwb....",
    "..bpwwwwwwpb....",
    "...bpwwwwpb.....",
    "....bppppb......",
    ".....bbbb.......",
    "................",
    "................",
    "................",
    "................",
)

_POLLO_2 = (
    "................",
    "................",
    "................",
    "................",
    ".....bbbb.......",
    "....bwwwwb......",
    "...bwwwwwwb.....",
    "..bwwoowwwwb....",
    "..bwwwwwwwwb....",
    "..bpwwwwwwpb....",
    "...bppwwppb.....",
    "....bppppb......",
    ".....bbbb.......",
    "................",
    "................",
    "................",
)

_BARRIL = (
    "................",
    "................",
    "...llllllll.....",
    "..lLLLLLLLLl....",
    "..lLllllllLl....",
    "..lLllllllLl....",
    "..llllllllll....",
    "..lLLLLLLLLl....",
    "..lLllllllLl....",
    "..lLllllllLl....",
    "..llllllllll....",
    "..lLLLLLLLLl....",
    "..lLllllllLl....",
    "..lLLLLLLLLl....",
    "...llllllll.....",
    "................",
)

_BARRIL_ROTO = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "...l......l.....",
    "..lLl....lLl....",
    "..llll..llll....",
    ".lLLLLllLLLLl...",
    "..lLllllllLl....",
    "...llllllll.....",
    "....llllll......",
    "................",
    "................",
    "................",
)

# --- el escenario ---------------------------------------------------------
#
# Ocho casillas: asfalto, acera, bordillo, muro de ladrillo, valla,
# alcantarilla (peligro), la salida y una farola.

_ASFALTO = (
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnNnnnnnnnnnnnn",
    "nnnnnnnnnnnNnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnNnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nNnnnnnnnnnnnNnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnNnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnNnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
)

_ACERA = (
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "CCCCCCCCCCCCCCCC",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "CCCCCCCCCCCCCCCC",
)

_BORDILLO = (
    "CCCCCCCCCCCCCCCC",
    "cccccccccccccccc",
    "cccccccccccccccc",
    "CCCCCCCCCCCCCCCC",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
)

_MURO = (
    "llllllllllllllll",
    "lLLLlLLLLlLLLLLl",
    "lLLLlLLLLlLLLLLl",
    "llllllllllllllll",
    "LLlLLLLlLLLLlLLL",
    "LLlLLLLlLLLLlLLL",
    "llllllllllllllll",
    "lLLLlLLLLlLLLLLl",
    "lLLLlLLLLlLLLLLl",
    "llllllllllllllll",
    "LLlLLLLlLLLLlLLL",
    "LLlLLLLlLLLLlLLL",
    "llllllllllllllll",
    "lLLLlLLLLlLLLLLl",
    "lLLLlLLLLlLLLLLl",
    "llllllllllllllll",
)

_VALLA = (
    "mmmmmmmmmmmmmmmm",
    "m..m.m..m.m..m.m",
    "m..m.m..m.m..m.m",
    "mmmmmmmmmmmmmmmm",
    "m..m.m..m.m..m.m",
    "m..m.m..m.m..m.m",
    "m..m.m..m.m..m.m",
    "mmmmmmmmmmmmmmmm",
    "m..m.m..m.m..m.m",
    "m..m.m..m.m..m.m",
    "m..m.m..m.m..m.m",
    "mmmmmmmmmmmmmmmm",
    "m..m.m..m.m..m.m",
    "m..m.m..m.m..m.m",
    "mmmmmmmmmmmmmmmm",
    "nnnnnnnnnnnnnnnn",
)

_ALCANTARILLA = (
    "nnnnnnnnnnnnnnnn",
    "nCCCCCCCCCCCCCCn",
    "nCbbbbbbbbbbbbCn",
    "nCbCCbCCbCCbCbCn",
    "nCbbbbbbbbbbbbCn",
    "nCbCCbCCbCCbCbCn",
    "nCbbbbbbbbbbbbCn",
    "nCbCCbCCbCCbCbCn",
    "nCbbbbbbbbbbbbCn",
    "nCbCCbCCbCCbCbCn",
    "nCbbbbbbbbbbbbCn",
    "nCbCCbCCbCCbCbCn",
    "nCbbbbbbbbbbbbCn",
    "nCCCCCCCCCCCCCCn",
    "nnnnnnnnnnnnnnnn",
    "nnnnnnnnnnnnnnnn",
)

_SALIDA = (
    "oooooooooooooooo",
    "obbbbbbbbbbbbbbo",
    "ob..o......o..bo",
    "ob.ooo....ooo.bo",
    "ob..o......o..bo",
    "ob............bo",
    "ob...oooooo...bo",
    "ob..o......o..bo",
    "ob..o......o..bo",
    "ob...oooooo...bo",
    "ob............bo",
    "ob..o......o..bo",
    "ob.ooo....ooo.bo",
    "ob..o......o..bo",
    "obbbbbbbbbbbbbbo",
    "oooooooooooooooo",
)

_FAROLA = (
    "nnnnmmmmmmmmnnnn",
    "nnnmoooooooomnnn",
    "nnnmoooooooomnnn",
    "nnnnmmmmmmmmnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnnmmmmnnnnnn",
    "nnnnnmmmmmmnnnnn",
    "nnnnmmmmmmmmnnnn",
    "nnnnnnnnnnnnnnnn",
)

TILES = (_ASFALTO, _ACERA, _BORDILLO, _MURO, _VALLA, _ALCANTARILLA, _SALIDA,
         _FAROLA)


def heroe(estilo: str) -> Image:
    return _hoja(list(HEROE), estilo)


def maton(estilo: str) -> Image:
    return _hoja(list(_maton("r", "R")), estilo)


def bruto(estilo: str) -> Image:
    return _hoja(list(_maton("g", "G")), estilo)


def jefe(estilo: str) -> Image:
    return _hoja(list(JEFE), estilo)


def bate(estilo: str) -> Image:
    return _hoja([_BATE, _BATE_2], estilo)


def pollo(estilo: str) -> Image:
    return _hoja([_POLLO, _POLLO_2], estilo)


def barril(estilo: str) -> Image:
    return _hoja([_BARRIL, _BARRIL_ROTO], estilo)


def tileset(estilo: str) -> Image:
    return _hoja(list(TILES), estilo)


def todos(estilo: str) -> Dict[str, Image]:
    """Los dibujos que anade este genero, por encima de los del estilo."""
    return {
        "graficos/heroe.png": heroe(estilo),
        "graficos/maton.png": maton(estilo),
        "graficos/bruto.png": bruto(estilo),
        "graficos/jefe.png": jefe(estilo),
        "graficos/bate.png": bate(estilo),
        "graficos/pollo.png": pollo(estilo),
        "graficos/barril.png": barril(estilo),
        "graficos/tiles.png": tileset(estilo),
    }
