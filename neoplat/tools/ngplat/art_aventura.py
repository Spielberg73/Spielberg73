"""Los dibujos del genero de aventura (al estilo Dizzy), vistos de lado.

Lo que hay que dibujar aqui es otra cosa que en los demas generos: el heroe no
pega, asi que no tiene fotograma de ataque; lo que tiene es un salto que se ve
venir. Y el escenario no va de plataformas sino de **sitios**: una puerta
cerrada, una hoguera y una pared de roca, que son las tres cosas que te paran
hasta que apareces con lo que piden.

Como en el resto del kit, los dibujos se escriben con **patrones**: una lista
de filas de texto, una letra por pixel. Asi se ve en el propio codigo lo que
sale, y cambiar un color es cambiar una letra.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .art import Lienzo, patron
from . import art_hierro
from .png import Image

RGBA = Tuple[int, int, int, int]

COLORES: Dict[str, Dict[str, RGBA]] = {
    "bosque": {
        "b": (24, 20, 32, 255),       # contorno
        "e": (250, 240, 212, 255),    # cascara
        "E": (216, 196, 156, 255),    # cascara en sombra
        "w": (248, 248, 248, 255),    # blanco del ojo
        "r": (216, 72, 56, 255),      # guantes y lengua
        "R": (152, 40, 32, 255),      # rojo oscuro
        "z": (72, 112, 216, 255),     # botas
        "Z": (40, 64, 152, 255),      # botas en sombra
        "g": (104, 176, 88, 255),     # hierba
        "G": (64, 120, 56, 255),      # hierba en sombra
        "t": (168, 112, 64, 255),     # tierra
        "T": (112, 72, 40, 255),      # tierra en sombra
        "p": (140, 136, 152, 255),    # piedra
        "P": (92, 88, 104, 255),      # piedra en sombra
        "o": (248, 208, 72, 255),     # oro: llave, moneda, la salida
        "n": (248, 152, 48, 255),     # fuego
        "a": (96, 168, 224, 255),     # agua
        "A": (48, 104, 176, 255),     # agua en sombra
        "m": (152, 96, 48, 255),      # madera
        "M": (100, 60, 28, 255),      # madera en sombra
        "v": (152, 200, 72, 255),     # bicho
        "V": (96, 136, 48, 255),      # bicho en sombra
    },
    "hierro": {
        "b": art_hierro.LINEA, "e": art_hierro.CLARO,
        "E": art_hierro.ROCA, "w": art_hierro.CLARO,
        "r": art_hierro.ROJO, "R": art_hierro.LINEA,
        "z": art_hierro.ROCA, "Z": art_hierro.ROCA2,
        "g": art_hierro.ROCA, "G": art_hierro.ROCA2,
        "t": art_hierro.ROCA2, "T": art_hierro.LINEA,
        "p": art_hierro.ROCA, "P": art_hierro.ROCA2,
        "o": art_hierro.ORO, "n": art_hierro.ROJO,
        "a": art_hierro.ROCA, "A": art_hierro.ROCA2,
        "m": art_hierro.ROCA2, "M": art_hierro.LINEA,
        "v": art_hierro.CLARO, "V": art_hierro.ROCA,
    },
}


def _hoja(frames: List[Tuple[str, ...]], estilo: str) -> Image:
    """Pega los fotogramas de un patron en una hoja de 16 pixeles de alto."""
    colores = COLORES[estilo]
    hoja = Lienzo(16 * len(frames), 16)
    for i, frame in enumerate(frames):
        hoja.blit(i * 16, 0, patron(list(frame), colores))
    return hoja.image


# --- el huevo -------------------------------------------------------------
#
# Cinco fotogramas, en el orden que pide el game.yaml del genero:
#
#   0  quieto        1, 2  andando        3  saltando        4  el golpe
#
# Mira siempre a la derecha: del otro lado se encarga el motor espejandolo. Y
# no hay fotograma de pegar porque en este genero **no se pega**: lo unico que
# hacen las manos es soltar lo que llevas.

_QUIETO = (
    "................",
    ".....bbbbbb.....",
    "....beeeeeeb....",
    "...beeeeeeeeb...",
    "..beeewwewweeb..",
    "..beeewbewbeeb..",
    "..beeeeeeeeeeb..",
    "..beeeeerreeeb..",
    "..beeeeeeeeeeb..",
    "...beeeeeeeeb...",
    "...bEeeeeeeEb...",
    "..brrbEEEEbrrb..",
    "..brrb....brrb..",
    "...bb..bb..bb...",
    "....bzzbbzzb....",
    ".....bbbbbb.....")

_ANDA_A = (
    "................",
    ".....bbbbbb.....",
    "....beeeeeeb....",
    "...beeeeeeeeb...",
    "..beeewwewweeb..",
    "..beeewbewbeeb..",
    "..beeeeeeeeeeb..",
    "..beeeeerreeeb..",
    "..beeeeeeeeeeb..",
    "...beeeeeeeeb...",
    "...bEeeeeeeEb...",
    ".brrbEEEEEEbrrb.",
    ".brrb......brrb.",
    "..bb...bb...bb..",
    "..bzzb.bzzb.....",
    "..bbbb.bbbb.....")

_ANDA_B = (
    "................",
    "................",
    ".....bbbbbb.....",
    "....beeeeeeb....",
    "...beeeeeeeeb...",
    "..beeewwewweeb..",
    "..beeewbewbeeb..",
    "..beeeeeeeeeeb..",
    "..beeeeerreeeb..",
    "..beeeeeeeeeeb..",
    "...beeeeeeeeb...",
    "..brbEeeeeeEbrb.",
    "..brrbEEEEbrrbb.",
    "...bb.bbbb.bb...",
    "....bzzzzzzb....",
    ".....bbbbbb.....")

_SALTA = (
    "................",
    "..b..bbbbbb..b..",
    "..brbeeeeeebrb..",
    "..brbeeeeeebrb..",
    "..brreewwewwerb.",
    "...bbeewbewbeb..",
    "....beeeeeeeeb..",
    "....beeeeeeeeb..",
    "....beeerrreeb..",
    "....beeeeeeeeb..",
    "....bEeeeeeeEb..",
    ".....bEEEEEEb...",
    "......bbbbbb....",
    ".....bzzbbzzb...",
    "....bzzb..bzzb..",
    "....bbb....bbb..")

_DANO = (
    "................",
    "..b.b.bbbb.b.b..",
    "...bbeeeeeebb...",
    "...beeeeeeeeb...",
    "..beebbeebbeeb..",
    "..beebbeebbeeb..",
    "..beeeeeeeeeeb..",
    "..beeebbbbeeeb..",
    "..beeebrrbeeeb..",
    "...beebbbbeeb...",
    "...bEeeeeeeEb...",
    "..brrbEEEEbrrb..",
    "..brrb....brrb..",
    "...bb..bb..bb...",
    "....bzzbbzzb....",
    ".....bbbbbb.....")


def heroe(estilo: str) -> Image:
    return _hoja([_QUIETO, _ANDA_A, _ANDA_B, _SALTA, _DANO], estilo)


# --- los bichos -----------------------------------------------------------
#
# En una aventura no se matan: se esquivan. Por eso son dos y van a lo suyo -la
# arana patrulla su tramo, el murcielago vuela en su sitio-: lo que hacen es
# ocupar el paso justo donde hace falta pasar.

_ARANA_A = (
    "................",
    "................",
    "..b..........b..",
    "...b........b...",
    "....bbbbbbbb....",
    "...bVVVVVVVVb...",
    "..bVvvvvvvvvVb..",
    ".bVvvwbvvbwvvVb.",
    ".bVvvvvvvvvvvVb.",
    ".bVvvvvvvvvvvVb.",
    "..bVvvvvvvvvVb..",
    "...bVVVVVVVVb...",
    "..b.bb.bb.bb.b..",
    ".b...b....b...b.",
    "................",
    "................")

_ARANA_B = (
    "................",
    "................",
    "................",
    "..bb........bb..",
    "....bbbbbbbb....",
    "...bVVVVVVVVb...",
    "..bVvvvvvvvvVb..",
    ".bVvvbwvvwbvvVb.",
    ".bVvvvvvvvvvvVb.",
    ".bVvvvvvvvvvvVb.",
    "..bVvvvvvvvvVb..",
    "...bVVVVVVVVb...",
    ".b..bb.bb.bb..b.",
    "..b..b....b..b..",
    "................",
    "................")

_MURCIELAGO_A = (
    "................",
    "................",
    "..bb........bb..",
    ".bPPb......bPPb.",
    "bPPPPb....bPPPPb",
    "bPPPPPbbbbPPPPPb",
    ".bPPPbppppbPPPb.",
    "..bbbpwppwpbbb..",
    ".....pppppp.....",
    ".....bpbbpb.....",
    "......bppb......",
    ".......bb.......",
    "................",
    "................",
    "................",
    "................")

_MURCIELAGO_B = (
    "................",
    ".......bb.......",
    "......bPPb......",
    ".....bPPPPb.....",
    "..bbbPPPPPPbbb..",
    ".bPPbbbppppbbPPb",
    "bPPPPbpwppwpbPP.",
    ".bbbbbpppppp....",
    "......bpbbpb....",
    ".......bppb.....",
    "........bb......",
    "................",
    "................",
    "................",
    "................",
    "................")


def arana(estilo: str) -> Image:
    return _hoja([_ARANA_A, _ARANA_B], estilo)


def murcielago(estilo: str) -> Image:
    return _hoja([_MURCIELAGO_A, _MURCIELAGO_B], estilo)


# --- lo que se lleva encima -----------------------------------------------
#
# Los tres del puzle: la llave abre la puerta, el cubo apaga la hoguera y el
# pico tira la pared de roca. Cada uno se dibuja distinto **a proposito**: en
# el marcador salen por su nombre, pero en el suelo hay que reconocerlos de un
# vistazo desde el otro lado de la pantalla.

_LLAVE_A = (
    "................",
    "................",
    "................",
    ".....bbbb.......",
    "....boooob......",
    "...boobboob.....",
    "...bob..bob.....",
    "...bob..bob.....",
    "...boobboob.....",
    "....boooob......",
    ".....booob......",
    "......boob......",
    "......boobb.....",
    "......boooob....",
    "......bbbbbb....",
    "................")

_LLAVE_B = (
    "................",
    "................",
    "................",
    "................",
    ".....bbbb.......",
    "....boooob......",
    "...boobboob.....",
    "...bob..bob.....",
    "...boobboob.....",
    "....boooob......",
    ".....booob......",
    "......boob......",
    "......boobb.....",
    "......boooob....",
    "......bbbbbb....",
    "................")

_CUBO_A = (
    "................",
    "................",
    "................",
    "...bb......bb...",
    "..bppb....bppb..",
    "..bpbbbbbbbbpb..",
    "..bpbppppppbpb..",
    "...bbpaaaapbb...",
    "...bpaaaaaapb...",
    "...bpaAaaAaapb..",
    "...bpaaAaaaapb..",
    "....bpaaaaapb...",
    "....bpAAAAApb...",
    ".....bppppppb...",
    "......bbbbbb....",
    "................")

_CUBO_B = (
    "................",
    "................",
    "................",
    "................",
    "...bb......bb...",
    "..bppb....bppb..",
    "..bpbbbbbbbbpb..",
    "..bpbppppppbpb..",
    "...bbpaaaapbb...",
    "...bpaaAaaapb...",
    "...bpaAaaaaapb..",
    "....bpaaaAapb...",
    "....bpAAAAApb...",
    ".....bppppppb...",
    "......bbbbbb....",
    "................")

_PICO_A = (
    "................",
    "................",
    "..bbb.......bbb.",
    ".bpppbbbbbbbpppb",
    ".bpPPpppppppPPpb",
    "..bbppppppppbb..",
    "....bbbpbbbb....",
    ".......bmb......",
    ".......bmb......",
    ".......bmb......",
    ".......bMb......",
    ".......bMb......",
    ".......bMb......",
    ".......bbb......",
    "................",
    "................")

_PICO_B = (
    "................",
    "................",
    "................",
    "..bbb.......bbb.",
    ".bpppbbbbbbbpppb",
    ".bpPPpppppppPPpb",
    "..bbppppppppbb..",
    "....bbbpbbbb....",
    ".......bmb......",
    ".......bmb......",
    ".......bmb......",
    ".......bMb......",
    ".......bMb......",
    ".......bMb......",
    ".......bbb......",
    "................")

_MANZANA_A = (
    "................",
    "................",
    "................",
    ".......bb.......",
    "......bGGb......",
    ".....bGGb.......",
    "....bbrbb.......",
    "...brrrrrbb.....",
    "..brrrrrrrrb....",
    "..brwrrrrrrb....",
    "..brrrrrrrRb....",
    "..bRrrrrrrRb....",
    "...bRrrrrRb.....",
    "....bbRRbb......",
    "......bb........",
    "................")

_MANZANA_B = (
    "................",
    "................",
    "................",
    "................",
    ".......bb.......",
    "......bGGb......",
    ".....bGGb.......",
    "....bbrbb.......",
    "...brrrrrbb.....",
    "..brrrrrrrrb....",
    "..brwrrrrrrb....",
    "..brrrrrrrRb....",
    "...bRrrrrrRb....",
    "....bbRRbb......",
    "......bb........",
    "................")

_MONEDA_A = (
    "................",
    "................",
    "................",
    ".....bbbbbb.....",
    "....boooooob....",
    "...boooooooob...",
    "...booobbooob...",
    "...boobbbboob...",
    "...boobbbboob...",
    "...booobbooob...",
    "...boooooooob...",
    "....boooooob....",
    ".....bbbbbb.....",
    "................",
    "................",
    "................")

_MONEDA_B = (
    "................",
    "................",
    "................",
    "................",
    "......bbb.......",
    ".....booob......",
    ".....boobb......",
    ".....bobob......",
    ".....bboob......",
    ".....booob......",
    "......bbb.......",
    "................",
    "................",
    "................",
    "................",
    "................")


def llave(estilo: str) -> Image:
    return _hoja([_LLAVE_A, _LLAVE_B], estilo)


def cubo(estilo: str) -> Image:
    return _hoja([_CUBO_A, _CUBO_B], estilo)


def pico(estilo: str) -> Image:
    return _hoja([_PICO_A, _PICO_B], estilo)


def manzana(estilo: str) -> Image:
    return _hoja([_MANZANA_A, _MANZANA_B], estilo)


def moneda(estilo: str) -> Image:
    return _hoja([_MONEDA_A, _MONEDA_B], estilo)


# --- el escenario ---------------------------------------------------------
#
# El orden de la hoja es el que espera el game.yaml del genero:
#
#   0 cielo    1 hierba   2 tierra    3 roca      4 pinchos
#   5 rama     6 la meta  7 puerta    8 hoguera   9 pared de roca
#
# Los tres ultimos son los **cerrojos**: se pintan cerrados porque es como se
# ven mientras estan puestos; al abrirlos el motor los deja en aire y lo que se
# ve por debajo es el cielo.

_CIELO = tuple(["................"] * 16)

_HIERBA = (
    "gGgggGggggGgggGg",
    "gggggggggggggggg",
    "gGggGgggGgggggGg",
    "gggggggggggggggg",
    "tGtttGtttGtttGtt",
    "tttttttttttttttt",
    "tTttttTtttttTttt",
    "tttttttttttttttt",
    "ttTtttttTtttttTt",
    "tttttttttttttttt",
    "TtttTttttttTtttt",
    "tttttttttttttttt",
    "ttttttTtttttttTt",
    "tttttttttttttttt",
    "tTtttttttTtttttt",
    "TTTTTTTTTTTTTTTT")

_TIERRA = (
    "tttttttttttttttt",
    "tTtttttTtttttttT",
    "tttttttttttttttt",
    "ttttTttttttTtttt",
    "tttttttttttttttt",
    "TtttttttTttttttt",
    "tttttttttttttttt",
    "ttttttTtttttTttt",
    "tttttttttttttttt",
    "tTtttttttttTtttt",
    "tttttttttttttttt",
    "ttttTtttttttttTt",
    "tttttttttttttttt",
    "tttttttTttttTttt",
    "tttttttttttttttt",
    "TTTTTTTTTTTTTTTT")

_ROCA = (
    "pppppPppppppPppp",
    "pPppppppPpppppPp",
    "PPPPPPPPPPPPPPPP",
    "ppPppppppppPpppp",
    "pppppPppppppppPp",
    "ppppppppPppppppp",
    "PPPPPPPPPPPPPPPP",
    "pPppppppppppPppp",
    "ppppPppppPpppppp",
    "pppppppppppppppp",
    "PPPPPPPPPPPPPPPP",
    "ppppppPppppppppP",
    "ppPpppppppPppppp",
    "pppppppPpppppppp",
    "pppppppppppppppp",
    "PPPPPPPPPPPPPPPP")

_PINCHOS = (
    "................",
    "................",
    "................",
    "................",
    "..b..b..b..b..b.",
    "..b..b..b..b..b.",
    ".bpb.bpb.bpb.bpb",
    ".bpb.bpb.bpb.bpb",
    ".bpb.bpb.bpb.bpb",
    "bpPpbpPpbpPpbpPp",
    "bpPpbpPpbpPpbpPp",
    "bpPpbpPpbpPpbpPp",
    "bPPPbPPPbPPPbPPP",
    "bbbbbbbbbbbbbbbb",
    "TTTTTTTTTTTTTTTT",
    "tttttttttttttttt")

_RAMA = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "bbbbbbbbbbbbbbbb",
    "mmmmmmmmmmmmmmmm",
    "mMmmmMmmmmMmmmMm",
    "MMMMMMMMMMMMMMMM",
    "bbbbbbbbbbbbbbbb",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_META = (
    "................",
    "....bbbbbbbb....",
    "...bmmmmmmmmb...",
    "..bmMMMMMMMMMb..",
    "..bmMoooooooMb..",
    "..bmMobbbbboMb..",
    "..bmMobbbbboMb..",
    "..bmMobbbbboMb..",
    "..bmMobbbbboMb..",
    "..bmMobbbbboMb..",
    "..bmMobbbbboMb..",
    "..bmMobbbbboMb..",
    "..bmMobbbbboMb..",
    "..bmMMMMMMMMMb..",
    "..bbbbbbbbbbbb..",
    "MMMMMMMMMMMMMMMM")

_PUERTA = (
    "bbbbbbbbbbbbbbbb",
    "bmmmmmmmmmmmmmmb",
    "bmMmmmmmmmmmmMmb",
    "bmmmmmmmmmmmmmmb",
    "bMMMMMMMMMMMMMMb",
    "bmmmmmmmmmmmmmmb",
    "bmMmmmmmmmmmmMmb",
    "bmmmmmmmoobmmmmb",
    "bmmmmmmmoobmmmmb",
    "bMMMMMMMMMMMMMMb",
    "bmmmmmmmmmmmmmmb",
    "bmMmmmmmmmmmmMmb",
    "bmmmmmmmmmmmmmmb",
    "bMMMMMMMMMMMMMMb",
    "bmmmmmmmmmmmmmmb",
    "bbbbbbbbbbbbbbbb")

_HOGUERA = (
    "................",
    ".......nn.......",
    "......nrnn......",
    ".....nnrrn......",
    ".....nrrrnn.....",
    "....nnrrrrn.....",
    "....nrrRrrnn....",
    "...nnrrRrrrn....",
    "...nrrRRRrrnn...",
    "..nnrrRRRrrrn...",
    "..nrrrRRRrrrnn..",
    "..nnrrrRRrrrrn..",
    "...nnrrrrrrnn...",
    "..bmMbmMbmMbmMb.",
    "..bMmbMmbMmbMmb.",
    "..bbbbbbbbbbbbb.")

_PARED = (
    "bbbbbbbbbbbbbbbb",
    "bppppppbpppppppb",
    "bpPPPPPbpPPPPPPb",
    "bPPPPPPbPPPPPPPb",
    "bbbbbbbbbbbbbbbb",
    "bppbppppppppbppb",
    "bpPbpPPPPPPPbpPb",
    "bPPbPPPPPPPPbPPb",
    "bbbbbbbbbbbbbbbb",
    "bpppppppbppppppb",
    "bpPPPPPPbpPPPPPb",
    "bPPPPPPPbPPPPPPb",
    "bbbbbbbbbbbbbbbb",
    "bppbppppppppbppb",
    "bpPbpPPPPPPPbpPb",
    "bbbbbbbbbbbbbbbb")

TILES = (_CIELO, _HIERBA, _TIERRA, _ROCA, _PINCHOS, _RAMA, _META, _PUERTA,
         _HOGUERA, _PARED)


def tileset(estilo: str) -> Image:
    return _hoja(list(TILES), estilo)


def todos(estilo: str) -> Dict[str, Image]:
    """Los dibujos que anade este genero, por encima de los del estilo."""
    return {
        "graficos/heroe.png": heroe(estilo),
        "graficos/arana.png": arana(estilo),
        "graficos/murcielago.png": murcielago(estilo),
        "graficos/llave.png": llave(estilo),
        "graficos/cubo.png": cubo(estilo),
        "graficos/pico.png": pico(estilo),
        "graficos/manzana.png": manzana(estilo),
        "graficos/moneda.png": moneda(estilo),
        "graficos/tiles.png": tileset(estilo),
    }
