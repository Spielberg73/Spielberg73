"""Los dibujos del genero de mazmorra (Gauntlet), en vista cenital.

Se ve desde arriba, como el de comando, pero lo que hay que dibujar es otra
cosa: un caballero con casco y escudo, bichos de mazmorra, los **nidos** que
los sacan sin parar, la comida que te mantiene vivo y la pocima que limpia la
pantalla. Y un escenario de piedra: muros, losas, lava y la salida.

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
        "a": (176, 184, 200, 255),    # armadura
        "A": (112, 120, 140, 255),    # armadura en sombra
        "p": (248, 200, 152, 255),    # piel
        "b": (24, 20, 32, 255),       # contorno y huecos
        "o": (248, 208, 72, 255),     # oro: llaves, tesoro, la salida
        "r": (216, 72, 56, 255),      # rojo: demonio y lava
        "R": (152, 40, 32, 255),      # rojo oscuro
        "g": (120, 116, 128, 255),    # piedra del muro
        "G": (80, 78, 92, 255),       # piedra en sombra
        "s": (72, 64, 72, 255),       # losa del suelo
        "S": (56, 50, 58, 255),       # losa oscura
        "v": (104, 176, 88, 255),     # bicho
        "V": (64, 120, 56, 255),      # bicho en sombra
        "w": (232, 236, 248, 255),    # fantasma
        "m": (168, 96, 216, 255),     # pocima
        "c": (200, 120, 72, 255),     # carne
    },
    "hierro": {
        "a": art_hierro.CLARO, "A": art_hierro.ROCA,
        "p": art_hierro.CLARO, "b": art_hierro.LINEA,
        "o": art_hierro.ORO, "r": art_hierro.ROJO,
        "R": art_hierro.LINEA, "g": art_hierro.ROCA,
        "G": art_hierro.ROCA2, "s": art_hierro.ROCA2,
        "S": art_hierro.LINEA, "v": art_hierro.ROCA,
        "V": art_hierro.ROCA2, "w": art_hierro.CLARO,
        "m": art_hierro.ROJO, "c": art_hierro.ORO,
    },
}


def _hoja(frames: List[Tuple[str, ...]], estilo: str) -> Image:
    """Pega los fotogramas de un patron en una hoja de 16 pixeles de alto."""
    colores = COLORES[estilo]
    hoja = Lienzo(16 * len(frames), 16)
    for i, frame in enumerate(frames):
        hoja.blit(i * 16, 0, patron(list(frame), colores))
    return hoja.image


# --- el caballero ---------------------------------------------------------
#
# Nueve fotogramas, en el orden que pide el game.yaml del genero:
#   0        quieto (de frente)
#   1, 2     andando de frente
#   3, 4     andando de espaldas
#   5, 6     andando de lado (se espeja para el otro lado)
#   7        atacando
#   8        el golpe recibido
#
# Visto en planta se le ve sobre todo el casco y los hombros, y por eso el
# escudo (a la izquierda) y la espada (a la derecha) son lo que dice hacia
# donde mira.

_FRENTE_QUIETO = (
    "................",
    ".....bbbbbb.....",
    "....baaaaaab....",
    "....baApppb.....",
    "....bapbbpab....",
    "....baapppab....",
    ".....bAAAAb.....",
    "...bbaaaaaabb...",
    "..bAAbaaaab oAb.",
    "..bAAbaaaab oAb.",
    "..bAAbaaaabbbAb.",
    "...bbbaaaabbbbb.",
    "....bAAbbAAb....",
    "....bAb..bAb....",
    "....bbb..bbb....",
    "................")

_FRENTE_A = (
    "................",
    ".....bbbbbb.....",
    "....baaaaaab....",
    "....baApppb.....",
    "....bapbbpab....",
    "....baapppab....",
    ".....bAAAAb.....",
    "...bbaaaaaabb...",
    "..bAAbaaaab oAb.",
    "..bAAbaaaab oAb.",
    "..bAAbaaaabbbAb.",
    "...bbbaaaabbbbb.",
    "...bAAbb.bAAb...",
    "...bAb....bAb...",
    "...bbb....bbb...",
    "................")

_FRENTE_B = (
    "................",
    ".....bbbbbb.....",
    "....baaaaaab....",
    "....baApppb.....",
    "....bapbbpab....",
    "....baapppab....",
    ".....bAAAAb.....",
    "...bbaaaaaabb...",
    "..bAAbaaaab oAb.",
    "..bAAbaaaab oAb.",
    "..bAAbaaaabbbAb.",
    "...bbbaaaabbbbb.",
    "....bAAb.bbAAb..",
    "....bAb....bAb..",
    "....bbb....bbb..",
    "................")

_ESPALDAS_A = (
    "................",
    ".....bbbbbb.....",
    "....baaaaaab....",
    "....baaaaaab....",
    "....baAAAAab....",
    "....bAAAAAAb....",
    ".....bAAAAb.....",
    "...bbaaaaaabb...",
    "..bAAbaaaab oAb.",
    "..bAAbaaaab oAb.",
    "..bAAbaaaabbbAb.",
    "...bbbaaaabbbbb.",
    "...bAAbb.bAAb...",
    "...bAb....bAb...",
    "...bbb....bbb...",
    "................")

_ESPALDAS_B = (
    "................",
    ".....bbbbbb.....",
    "....baaaaaab....",
    "....baaaaaab....",
    "....baAAAAab....",
    "....bAAAAAAb....",
    ".....bAAAAb.....",
    "...bbaaaaaabb...",
    "..bAAbaaaab oAb.",
    "..bAAbaaaab oAb.",
    "..bAAbaaaabbbAb.",
    "...bbbaaaabbbbb.",
    "....bAAb.bbAAb..",
    "....bAb....bAb..",
    "....bbb....bbb..",
    "................")

_LADO_A = (
    "................",
    "......bbbbb.....",
    ".....baaaaab....",
    ".....bapppab....",
    ".....bappbab....",
    ".....baapppb....",
    "......bAAAb.....",
    "..bbbbaaaabb....",
    ".bAAAbaaaab.o...",
    ".bAAAbaaaab.o...",
    ".bAAAbaaaabbb...",
    "..bbbbaaaabb....",
    "....bAAbbAAb....",
    "....bAb..bAb....",
    "....bbb..bbb....",
    "................")

_LADO_B = (
    "................",
    "......bbbbb.....",
    ".....baaaaab....",
    ".....bapppab....",
    ".....bappbab....",
    ".....baapppb....",
    "......bAAAb.....",
    "..bbbbaaaabb....",
    ".bAAAbaaaab.o...",
    ".bAAAbaaaab.o...",
    ".bAAAbaaaabbb...",
    "..bbbbaaaabb....",
    "...bAAb..bAAb...",
    "...bAb....bAb...",
    "...bbb....bbb...",
    "................")

_ATACANDO = (
    "................",
    ".....bbbbbb.....",
    "....baaaaaab....",
    "....baApppb.....",
    "....bapbbpab....",
    "....baapppab....",
    ".....bAAAAb.....",
    "...bbaaaaaabb...",
    "..bAAbaaaab.....",
    "..bAAbaaaab.....",
    "..bAAbaaaabooooo",
    "...bbbaaaabbbbbb",
    "....bAAbbAAb....",
    "....bAb..bAb....",
    "....bbb..bbb....",
    "................")

_GOLPEADO = (
    "................",
    "................",
    "....bbbbbbb.....",
    "...brrrrrrrb....",
    "...brApppAbb....",
    "...brpbbpArb....",
    "...brrpppprb....",
    "....brrrrrb.....",
    "..bbrrrrrrrbb...",
    ".bAAbrrrrrbbAb..",
    ".bAAbrrrrrb.Ab..",
    "..bbbrrrrrbbbb..",
    "....brAbbArb....",
    "....bAb..bAb....",
    "....bbb..bbb....",
    "................")


def heroe(estilo: str) -> Image:
    return _hoja([_FRENTE_QUIETO, _FRENTE_A, _FRENTE_B,
                  _ESPALDAS_A, _ESPALDAS_B, _LADO_A, _LADO_B,
                  _ATACANDO, _GOLPEADO], estilo)


# --- los bichos -----------------------------------------------------------

_BICHO_A = (
    "................",
    "................",
    "....bbbbbbb.....",
    "...bvvvvvvvb....",
    "..bvvVvvvVvvb...",
    "..bvvbvvvbvvb...",
    "..bvvvvvvvvvb...",
    "..bvvbbbbbvvb...",
    "..bvvvvvvvvvb...",
    "...bvvvvvvvb....",
    "..bVbvvvvvbVb...",
    "..bVbbVVVbbVb...",
    "...bb bVb bb....",
    "......bbb.......",
    "................",
    "................")

_BICHO_B = (
    "................",
    "................",
    "....bbbbbbb.....",
    "...bvvvvvvvb....",
    "..bvvVvvvVvvb...",
    "..bvvbvvvbvvb...",
    "..bvvvvvvvvvb...",
    "..bvvbbbbbvvb...",
    "..bvvvvvvvvvb...",
    "...bvvvvvvvb....",
    "...bvvvvvvvb....",
    "..bVbbVVVbbVb...",
    ".bVb..bVb..bVb..",
    ".bb...bbb...bb..",
    "................",
    "................")

_FANTASMA_A = (
    "................",
    "................",
    "....bbbbbb......",
    "...bwwwwwwb.....",
    "..bwwwwwwwwb....",
    "..bwbwwwwbwb....",
    "..bwbwwwwbwb....",
    "..bwwwwwwwwb....",
    "..bwwwbbwwwb....",
    "..bwwwwwwwwb....",
    "..bwwwwwwwwb....",
    "..bwwwwwwwwb....",
    "..bwbwwbwwbwb...",
    "..bbb.bb.bbb....",
    "................",
    "................")

_FANTASMA_B = (
    "................",
    "................",
    "....bbbbbb......",
    "...bwwwwwwb.....",
    "..bwwwwwwwwb....",
    "..bwbwwwwbwb....",
    "..bwbwwwwbwb....",
    "..bwwwwwwwwb....",
    "..bwwwbbwwwb....",
    "..bwwwwwwwwb....",
    "..bwwwwwwwwb....",
    "..bwwwwwwwwb....",
    "..bbwwbwwbwwb...",
    "...bb.bb.bb.b...",
    "................",
    "................")

_DEMONIO_A = (
    "................",
    "..b..........b..",
    "..bb.bbbbbb.bb..",
    "..brbrrrrrrbrb..",
    "..brrrrrrrrrrb..",
    "..brrobrrborrb..",
    "..brrrrrrrrrrb..",
    "..bRrrrbbrrrRb..",
    "..bRRrrrrrrRRb..",
    "...bRRRRRRRRb...",
    "..bRbRRRRRRbRb..",
    "..bRb.bRRb.bRb..",
    "...b..bRRb..b...",
    "......bbbb......",
    "................",
    "................")

_DEMONIO_B = (
    "................",
    "..b..........b..",
    "..bb.bbbbbb.bb..",
    "..brbrrrrrrbrb..",
    "..brrrrrrrrrrb..",
    "..brrobrrborrb..",
    "..brrrrrrrrrrb..",
    "..bRrrbbbbrrRb..",
    "..bRRrrrrrrRRb..",
    "...bRRRRRRRRb...",
    "...bRRRRRRRRb...",
    "..bRbbRRRRbbRb..",
    "..bRb.bRRb.bRb..",
    "...b..bbbb..b...",
    "................",
    "................")


def bicho(estilo: str) -> Image:
    return _hoja([_BICHO_A, _BICHO_B], estilo)


def fantasma(estilo: str) -> Image:
    return _hoja([_FANTASMA_A, _FANTASMA_B], estilo)


def demonio(estilo: str) -> Image:
    return _hoja([_DEMONIO_A, _DEMONIO_B], estilo)


# --- el nido, que es lo que hay que reventar ------------------------------
#
# Tres fotogramas: late despacio cuando esta entero y se ve el bicho asomando.

_NIDO_A = (
    "................",
    "..bbbbbbbbbbbb..",
    ".bGGGGGGGGGGGGb.",
    ".bGgggggggggGGb.",
    ".bGgbbbbbbbbgGb.",
    ".bGgbRRRRRRbgGb.",
    ".bGgbRbRRbRbgGb.",
    ".bGgbRRRRRRbgGb.",
    ".bGgbRRbbRRbgGb.",
    ".bGgbRRRRRRbgGb.",
    ".bGgbbbbbbbbgGb.",
    ".bGggggggggggGb.",
    ".bGGGGGGGGGGGGb.",
    "..bbbbbbbbbbbb..",
    "................",
    "................")

_NIDO_B = (
    "................",
    "..bbbbbbbbbbbb..",
    ".bGGGGGGGGGGGGb.",
    ".bGgggggggggGGb.",
    ".bGgbbbbbbbbgGb.",
    ".bGgbrrrrrrbgGb.",
    ".bGgbrbrrbrbgGb.",
    ".bGgbrrrrrrbgGb.",
    ".bGgbrrbbrrbgGb.",
    ".bGgbrrrrrrbgGb.",
    ".bGgbbbbbbbbgGb.",
    ".bGggggggggggGb.",
    ".bGGGGGGGGGGGGb.",
    "..bbbbbbbbbbbb..",
    "................",
    "................")

_NIDO_C = (
    "................",
    "..bbbbbbbbbbbb..",
    ".bGGGGGGGGGGGGb.",
    ".bGgggggggggGGb.",
    ".bGgbbbbbbbbgGb.",
    ".bGgbrrvvrrbgGb.",
    ".bGgbrbvvbrbgGb.",
    ".bGgbrvvvvrbgGb.",
    ".bGgbrvbbvrbgGb.",
    ".bGgbrrvvrrbgGb.",
    ".bGgbbbbbbbbgGb.",
    ".bGggggggggggGb.",
    ".bGGGGGGGGGGGGb.",
    "..bbbbbbbbbbbb..",
    "................",
    "................")


def nido(estilo: str) -> Image:
    return _hoja([_NIDO_A, _NIDO_B, _NIDO_C], estilo)


# --- lo que vuela ---------------------------------------------------------

_FLECHA_A = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "......o.........",
    ".....booooooo...",
    "......obbbbbb...",
    "......o.........",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_FLECHA_B = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "......o.........",
    ".....bo.........",
    "....booooooooo..",
    ".....bobbbbbbb..",
    "......o.........",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_FUEGO_A = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "......bbb.......",
    ".....brrrb......",
    ".....broRb......",
    ".....brrrb......",
    "......bbb.......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_FUEGO_B = (
    "................",
    "................",
    "................",
    "................",
    "......bbb.......",
    ".....brrRb......",
    "....brroorb.....",
    "....bRoooRb.....",
    "....brroorb.....",
    ".....brrRb......",
    "......bbb.......",
    "................",
    "................",
    "................",
    "................",
    "................")


def flecha(estilo: str) -> Image:
    return _hoja([_FLECHA_A, _FLECHA_B], estilo)


def bola(estilo: str) -> Image:
    return _hoja([_FUEGO_A, _FUEGO_B], estilo)


# --- lo que se recoge -----------------------------------------------------

_COMIDA_A = (
    "................",
    "................",
    "................",
    "......bbb.......",
    "....bbcccbb.....",
    "...bccccccccb...",
    "..bcccccccccb...",
    "..bccbcccbccb...",
    "..bcccccccccb...",
    "...bcccccccb....",
    "....bbcccbb.....",
    "......bbb.......",
    ".......b........",
    ".......b........",
    "................",
    "................")

_COMIDA_B = (
    "................",
    "................",
    "................",
    "......bbb.......",
    "....bbcccbb.....",
    "...bcccccccb....",
    "..bcccccccccb...",
    "..bccbcccbccb...",
    "..bcccccccccb...",
    "...bcccccccb....",
    "....bbcccbb.....",
    "......bbb.......",
    "......b.b.......",
    "......b.b.......",
    "................",
    "................")

_POCIMA_A = (
    "................",
    "................",
    "......bbb.......",
    "......bob.......",
    "......bob.......",
    ".....bbobb......",
    ".....bmmmb......",
    "....bmmmmmb.....",
    "....bmwmmmb.....",
    "....bmmmmmb.....",
    "....bmmmmmb.....",
    "....bbmmmbb.....",
    ".....bbbbb......",
    "................",
    "................",
    "................")

_POCIMA_B = (
    "................",
    "................",
    "......bbb.......",
    "......bob.......",
    "......bob.......",
    ".....bbobb......",
    ".....bmwmb......",
    "....bmmmmmb.....",
    "....bmmmwmb.....",
    "....bmwmmmb.....",
    "....bmmmmmb.....",
    "....bbmmmbb.....",
    ".....bbbbb......",
    "................",
    "................",
    "................")

_LLAVE_A = (
    "................",
    "................",
    "................",
    ".....bbbb.......",
    "....bo..ob......",
    "....bo..ob......",
    "....bo..ob......",
    ".....bobb.......",
    "......bo........",
    "......bo........",
    "......boob......",
    "......bo........",
    "......boob......",
    "......bbb.......",
    "................",
    "................")

_LLAVE_B = (
    "................",
    "................",
    "................",
    "................",
    ".....bbbb.......",
    "....bo..ob......",
    "....bo..ob......",
    "....bo..ob......",
    ".....bobb.......",
    "......bo........",
    "......boob......",
    "......bo........",
    "......boob......",
    "......bbb.......",
    "................",
    "................")

_TESORO_A = (
    "................",
    "................",
    "................",
    "................",
    "...bbbbbbbbbb...",
    "..booooooooob...",
    "..bobbobbobob...",
    "..booooooooob...",
    "..boooooooo ob..",
    "..bbbbbbbbbbb...",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_TESORO_B = (
    "................",
    "................",
    "................",
    "................",
    "...bbbbbbbbbb...",
    "..booooooooob...",
    "..bobbobbobob...",
    "..boowooooooB...",
    "..booooooooob...",
    "..bbbbbbbbbbb...",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")


def comida(estilo: str) -> Image:
    return _hoja([_COMIDA_A, _COMIDA_B], estilo)


def pocima(estilo: str) -> Image:
    return _hoja([_POCIMA_A, _POCIMA_B], estilo)


def llave(estilo: str) -> Image:
    return _hoja([_LLAVE_A, _LLAVE_B], estilo)


def tesoro(estilo: str) -> Image:
    return _hoja([_TESORO_A, _TESORO_B], estilo)


# --- el escenario ---------------------------------------------------------
#
# El orden de la hoja es el que espera el game.yaml del genero:
#
#   0 losa    1 muro    2 roca    3 lava   4 la salida
#   5 suelo   6 grieta  7 altar (punto de control)

_LOSA = (
    "ssssssssssssssss",
    "sSSSSSSSsSSSSSSs",
    "sSssssSSsSssssSs",
    "sSssssSSsSssssSs",
    "sSssssSSsSssssSs",
    "sSSSSSSSsSSSSSSs",
    "ssssssssssssssss",
    "SSSSSSSSSSSSSSSS",
    "ssssssssssssssss",
    "sSSSSSSSsSSSSSSs",
    "sSssssSSsSssssSs",
    "sSssssSSsSssssSs",
    "sSssssSSsSssssSs",
    "sSSSSSSSsSSSSSSs",
    "ssssssssssssssss",
    "SSSSSSSSSSSSSSSS")

_MURO = (
    "bbbbbbbbbbbbbbbb",
    "bggggggbggggggbb",
    "bgggggGbgggggGbb",
    "bgGGGGGbgGGGGGbb",
    "bbbbbbbbbbbbbbbb",
    "bggbggggggbggggb",
    "bgGbgggggGbggggG",
    "bGGbgGGGGGbgGGGG",
    "bbbbbbbbbbbbbbbb",
    "bggggggbggggggbb",
    "bgggggGbgggggGbb",
    "bgGGGGGbgGGGGGbb",
    "bbbbbbbbbbbbbbbb",
    "bggbggggggbggggb",
    "bgGbgggggGbggggG",
    "bbbbbbbbbbbbbbbb")

_ROCA = (
    "ssssbbbbbbbsssss",
    "sssbgggggggbssss",
    "ssbgggGGgggggbss",
    "sbggGGGGGGgggbss",
    "sbgggGGGGGGggbss",
    "bggGGGgggGGGggbs",
    "bgGGGgggggGGGgbs",
    "bgGGgggggggGGgbs",
    "bGGgggggggggGGbs",
    "sbGgggggggggGbss",
    "sbGGgggggggGGbss",
    "ssbGGGgggGGGbsss",
    "sssbGGGGGGGbssss",
    "ssssbbbbbbbsssss",
    "ssssssssssssssss",
    "ssssssssssssssss")

_LAVA = (
    "RRRRRRRRRRRRRRRR",
    "RrrRRRRrrRRRRRRR",
    "RRRrrRRRRRrrRRRR",
    "RRRRRRrrRRRRRrrR",
    "RrrRRRRRRrrRRRRR",
    "RRRRrrRRRRRRrrRR",
    "RrrRRRRrrRRRRRRR",
    "RRRRRRRRRRrrRRRR",
    "RRrrRRRrrRRRRRrr",
    "RRRRRrrRRRRrrRRR",
    "RrrRRRRRrrRRRRRR",
    "RRRRrrRRRRRRrrRR",
    "RRrrRRRRrrRRRRRR",
    "RRRRRrrRRRRrrRRR",
    "RrrRRRRRRRRRRRrr",
    "RRRRRrrRRRrrRRRR")

_SALIDA = (
    "bbbbbbbbbbbbbbbb",
    "boooooooooooooob",
    "boSSSSSSSSSSSSob",
    "boSbbbbbbbbbbSob",
    "boSbSSSSSSSSbSob",
    "boSbSbbbbbbSbSob",
    "boSbSbSSSSbSbSob",
    "boSbSbSooSbSbSob",
    "boSbSbSooSbSbSob",
    "boSbSbSSSSbSbSob",
    "boSbSbbbbbbSbSob",
    "boSbSSSSSSSSbSob",
    "boSbbbbbbbbbbSob",
    "boSSSSSSSSSSSSob",
    "boooooooooooooob",
    "bbbbbbbbbbbbbbbb")

_SUELO = (
    "ssssssssssssssss",
    "ssSssssssssSssss",
    "sssssssSssssssss",
    "ssssssssssssssSs",
    "sSsssssssSssssss",
    "ssssssSsssssssss",
    "ssssssssssssssss",
    "sssSsssssssssSss",
    "sssssssssSssssss",
    "sssssSssssssssss",
    "sssssssssssSssss",
    "sSssssssssssssss",
    "ssssssssSsssssss",
    "ssssSsssssssssSs",
    "ssssssssssssssss",
    "sssssssSssssssss")

_GRIETA = (
    "ssssssssssssssss",
    "sssssssbssssssss",
    "ssssssbSbsssssss",
    "sssssbSSsbssssss",
    "sssssbSsSbssssss",
    "ssssbSSsSSbsssss",
    "sssbSSssSSbssssss"[:16],
    "sssbSsssSSSbssss",
    "ssbSSssssSSbssss",
    "ssbSssssssSbssss",
    "sssbSsssssSbssss",
    "ssssbSssssbsssss",
    "sssssbSsSbssssss",
    "ssssssbSbsssssss",
    "sssssssbssssssss",
    "ssssssssssssssss")

_ALTAR = (
    "ssssssssssssssss",
    "sssbbbbbbbbbbsss",
    "ssbGGGGGGGGGGbss",
    "ssbGgggggggggbss",
    "ssbGgbbbbbbggbss",
    "ssbGgboooooggbss",
    "ssbGgbobbogggbss",
    "ssbGgbobbogggbss",
    "ssbGgboooooggbss",
    "ssbGgbbbbbbggbss",
    "ssbGgggggggggbss",
    "ssbGGGGGGGGGGbss",
    "sssbbbbbbbbbbsss",
    "ssssssssssssssss",
    "ssssssssssssssss",
    "ssssssssssssssss")

TILES = (_LOSA, _MURO, _ROCA, _LAVA, _SALIDA, _SUELO, _GRIETA, _ALTAR)


def tileset(estilo: str) -> Image:
    return _hoja(list(TILES), estilo)


def todos(estilo: str) -> Dict[str, Image]:
    """Los dibujos que anade este genero, por encima de los del estilo."""
    return {
        "graficos/heroe.png": heroe(estilo),
        "graficos/bicho.png": bicho(estilo),
        "graficos/fantasma.png": fantasma(estilo),
        "graficos/demonio.png": demonio(estilo),
        "graficos/nido.png": nido(estilo),
        "graficos/flecha.png": flecha(estilo),
        "graficos/bola.png": bola(estilo),
        "graficos/comida.png": comida(estilo),
        "graficos/pocima.png": pocima(estilo),
        "graficos/llave.png": llave(estilo),
        "graficos/tesoro.png": tesoro(estilo),
        "graficos/tiles.png": tileset(estilo),
    }
