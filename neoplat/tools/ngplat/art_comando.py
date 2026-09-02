"""Los dibujos del genero de comando (vista cenital).

El kit tiene dos estilos de dibujo -bosque y hierro- y dos generos que se ven
de lado. Este genero se ve **desde arriba**, asi que no vale ninguno de los
dibujos que ya habia: un heroe de perfil mirando a la derecha no dice nada
cuando el juego se mira en planta. Aqui se dibuja lo que hace falta:

  - el heroe visto en tres direcciones -de frente, de espaldas y de lado-, que
    es lo que pide el motor en vista cenital (las diagonales salen de espejar
    la de lado, y de eso se encarga el motor);
  - los soldados, que patrullan y disparan;
  - el prisionero atado, que es a quien **no** hay que dispararle;
  - la torreta, que no se mueve pero tampoco se calla;
  - las balas, la granada y el escenario de un campamento: hierba, camino,
    agua (que es peligro), sacos terreros, arboles y la salida.

Como en el resto del kit, los dibujos se escriben con **patrones**: una lista
de filas de texto, una letra por pixel. Un soldado visto desde arriba no es un
monton de rectangulos, y escrito asi se ve en el propio codigo lo que sale.

Los colores se piden por nombre y cada estilo los resuelve como quiera: el de
bosque tira de la paleta larga y el de hierro se queda con sus seis, que es lo
que cabe en el doble plano del Amiga.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .art import Lienzo, patron
from . import art
from . import art_hierro
from .png import Image

RGBA = Tuple[int, int, int, int]

# Los colores que usan los dibujos de este genero, por nombre. Cada estilo
# tiene los suyos; los nombres son los mismos para que el patron valga igual.
COLORES: Dict[str, Dict[str, RGBA]] = {
    "bosque": {
        "u": (88, 112, 64, 255),      # uniforme
        "U": (56, 76, 44, 255),       # uniforme en sombra
        "p": (248, 200, 152, 255),    # piel
        "b": (56, 40, 32, 255),       # botas y contorno
        "m": (192, 200, 216, 255),    # metal (armas)
        "r": (216, 72, 72, 255),      # rojo (el prisionero, los avisos)
        "o": (248, 208, 72, 255),     # oro (fogonazos)
        "v": (88, 184, 88, 255),      # hierba
        "V": (56, 136, 64, 255),      # hierba oscura
        "t": (136, 88, 56, 255),      # tierra
        "T": (104, 64, 40, 255),      # tierra oscura
        "a": (72, 120, 200, 255),     # agua
        "A": (48, 88, 160, 255),      # agua oscura
        "s": (176, 152, 96, 255),     # sacos terreros
        "c": (96, 216, 232, 255),     # la salida
    },
    "hierro": {
        "u": art_hierro.ROCA, "U": art_hierro.ROCA2,
        "p": art_hierro.CLARO, "b": art_hierro.LINEA,
        "m": art_hierro.CLARO, "r": art_hierro.ROJO,
        "o": art_hierro.ORO, "v": art_hierro.ROCA,
        "V": art_hierro.ROCA2, "t": art_hierro.ROCA2,
        "T": art_hierro.LINEA, "a": art_hierro.ROCA2,
        "A": art_hierro.LINEA, "s": art_hierro.CLARO,
        "c": art_hierro.ORO,
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
# Nueve fotogramas, en el orden que pide el game.yaml del genero:
#   0        quieto (de frente)
#   1, 2     andando de frente
#   3, 4     andando de espaldas
#   5, 6     andando de lado (se espeja para el otro lado)
#   7        disparando
#   8        el golpe recibido

_FRENTE_QUIETO = (
    "................",
    "................",
    ".....bbbbbb.....",
    "....bmmmmmmb....",
    "....bppppppb....",
    "....bpbppbpb....",
    ".....pppppp.....",
    "...buuuuuuub....",
    "..bumuuuuuumb...",
    "..bupuuuuuupb...",
    "...buuuuuuub....",
    "....buuuuub.....",
    "....bUb..bUb....",
    "....bUb..bUb....",
    "....bbb..bbb....",
    "................")

_FRENTE_A = (
    "................",
    "................",
    ".....bbbbbb.....",
    "....bmmmmmmb....",
    "....bppppppb....",
    "....bpbppbpb....",
    ".....pppppp.....",
    "...buuuuuuub....",
    "..bumuuuuuumb...",
    "..bupuuuuuupb...",
    "...buuuuuuub....",
    "....buuuuub.....",
    "...bUUb..bUb....",
    "...bUb....bUb...",
    "...bbb....bbb...",
    "................")

_FRENTE_B = (
    "................",
    "................",
    ".....bbbbbb.....",
    "....bmmmmmmb....",
    "....bppppppb....",
    "....bpbppbpb....",
    ".....pppppp.....",
    "...buuuuuuub....",
    "..bumuuuuuumb...",
    "..bupuuuuuupb...",
    "...buuuuuuub....",
    "....buuuuub.....",
    "....bUb..bUUb...",
    "...bUb.....bUb..",
    "...bbb.....bbb..",
    "................")

_ESPALDAS_A = (
    "................",
    "................",
    ".....bbbbbb.....",
    "....bmmmmmmb....",
    "....bmmmmmmb....",
    "....bbbbbbbb....",
    ".....UUUUUU.....",
    "...buuuuuuub....",
    "..bumuuuuuumb...",
    "..buuuuuuuuub...",
    "...buuuuuuub....",
    "....buuuuub.....",
    "...bUUb..bUb....",
    "...bUb....bUb...",
    "...bbb....bbb...",
    "................")

_ESPALDAS_B = (
    "................",
    "................",
    ".....bbbbbb.....",
    "....bmmmmmmb....",
    "....bmmmmmmb....",
    "....bbbbbbbb....",
    ".....UUUUUU.....",
    "...buuuuuuub....",
    "..bumuuuuuumb...",
    "..buuuuuuuuub...",
    "...buuuuuuub....",
    "....buuuuub.....",
    "....bUb..bUUb...",
    "...bUb.....bUb..",
    "...bbb.....bbb..",
    "................")

_LADO_A = (
    "................",
    "................",
    "......bbbbb.....",
    ".....bmmmmmb....",
    ".....bpppppb....",
    ".....bppbppb....",
    "......ppppp.....",
    "....buuuuuub....",
    "...bmmmuuuub....",
    "....bpuuuuub....",
    "....buuuuuub....",
    ".....buuuub.....",
    "....bUUb.bUb....",
    "...bUb....bUb...",
    "...bbb....bbb...",
    "................")

_LADO_B = (
    "................",
    "................",
    "......bbbbb.....",
    ".....bmmmmmb....",
    ".....bpppppb....",
    ".....bppbppb....",
    "......ppppp.....",
    "....buuuuuub....",
    "...bmmmuuuub....",
    "....bpuuuuub....",
    "....buuuuuub....",
    ".....buuuub.....",
    ".....bUb.bUb....",
    ".....bUb.bUb....",
    ".....bbb.bbb....",
    "................")

_DISPARANDO = (
    "................",
    "................",
    "......bbbbb.....",
    ".....bmmmmmb....",
    ".....bpppppb....",
    ".....bppbppb....",
    "......ppppp.....",
    "....buuuuuub....",
    "..mmmmmuuuub..o.",
    "....bpuuuuub....",
    "....buuuuuub....",
    ".....buuuub.....",
    "....bUUb.bUb....",
    "...bUb....bUb...",
    "...bbb....bbb...",
    "................")

_GOLPEADO = (
    "................",
    "................",
    "....bbbbbb......",
    "...bmmmmmmb.....",
    "...brrrrrrb.....",
    "...brbrrbrb.....",
    "....rrrrrr......",
    "..buuuuuuub.....",
    ".bumuuuuuumb....",
    ".buuuuuuuuub....",
    "..buuuuuuub.....",
    "...buuuuub......",
    "..bUb....bUb....",
    ".bUb......bUb...",
    ".bbb......bbb...",
    "................")

HEROE = (_FRENTE_QUIETO, _FRENTE_A, _FRENTE_B, _ESPALDAS_A, _ESPALDAS_B,
         _LADO_A, _LADO_B, _DISPARANDO, _GOLPEADO)


def heroe(estilo: str) -> Image:
    return _hoja(list(HEROE), estilo)


# --- los soldados ---------------------------------------------------------
#
# El enemigo lleva gorra en vez de casco y el uniforme oscuro: a 16x16 lo que
# distingue a los dos bandos tiene que ser la silueta y el tono, no el detalle.

_SOLDADO_A = (
    "................",
    "................",
    "......bbbb......",
    ".....brrrrb.....",
    ".....bppppb.....",
    ".....bpbbpb.....",
    "......pppp......",
    "....bUUUUUUb....",
    "...bUmUUUUmUb...",
    "...bUpUUUUpUb...",
    "....bUUUUUUb....",
    ".....bUUUUb.....",
    "....bUb..bUb....",
    "....bUb..bUb....",
    "....bbb..bbb....",
    "................")

_SOLDADO_B = (
    "................",
    "................",
    "......bbbb......",
    ".....brrrrb.....",
    ".....bppppb.....",
    ".....bpbbpb.....",
    "......pppp......",
    "....bUUUUUUb....",
    "...bUmUUUUmUb...",
    "...bUpUUUUpUb...",
    "....bUUUUUUb....",
    ".....bUUUUb.....",
    "...bUUb..bUUb...",
    "...bUb....bUb...",
    "...bbb....bbb...",
    "................")

_SOLDADO_TIRA = (
    "................",
    "................",
    "......bbbb......",
    ".....brrrrb.....",
    ".....bppppb.....",
    ".....bpbbpb.....",
    "......pppp......",
    "....bUUUUUUb....",
    ".ommmmmUUUUb....",
    "....bpUUUUUb....",
    "....bUUUUUUb....",
    ".....bUUUUb.....",
    "....bUb..bUb....",
    "....bUb..bUb....",
    "....bbb..bbb....",
    "................")

_TORRETA_A = (
    "................",
    "................",
    "....bbbbbbbb....",
    "...bssssssssb...",
    "...bsbsssbssb...",
    "...bssssssssb...",
    "....bmmmmmmb....",
    "...bmUUUUUUmb...",
    "...bmUpppUUmb...",
    "...bmUUUUUUmb...",
    "....bmmmmmmb....",
    "...bssssssssb...",
    "...bsbsssbssb...",
    "...bssssssssb...",
    "....bbbbbbbb....",
    "................")

_TORRETA_B = (
    "................",
    "................",
    "....bbbbbbbb....",
    "...bssssssssb...",
    "...bsbsssbssb...",
    "...bssssssssb...",
    "....bmmmmmmb....",
    "..obmUUUUUUmbo..",
    "..obmUpppUUmbo..",
    "...bmUUUUUUmb...",
    "....bmmmmmmb....",
    "...bssssssssb...",
    "...bsbsssbssb...",
    "...bssssssssb...",
    "....bbbbbbbb....",
    "................")


def soldado(estilo: str) -> Image:
    return _hoja([_SOLDADO_A, _SOLDADO_B, _SOLDADO_TIRA], estilo)


def torreta(estilo: str) -> Image:
    return _hoja([_TORRETA_A, _TORRETA_B], estilo)


# --- el prisionero --------------------------------------------------------
#
# Atado (los brazos a la espalda y la cuerda a la vista) y corriendo (los
# brazos en alto). Es el unico al que no hay que dispararle, asi que se dibuja
# **distinto de todo lo demas**: ropa clara y nada de verde.

_REHEN_A = (
    "................",
    "................",
    "......bbbb......",
    ".....bpppppb....",
    ".....bpbbpb.....",
    "......pppp......",
    ".....rrrrrr.....",
    "....bsssssb.....",
    "....bssssssb....",
    "...rbssssssbr...",
    "....bssssssb....",
    ".....bssssb.....",
    ".....bUb.bUb....",
    ".....bUb.bUb....",
    ".....bbb.bbb....",
    "................")

_REHEN_B = (
    "................",
    "................",
    "......bbbb......",
    ".....bpppppb....",
    ".....bpbbpb.....",
    "......pppp......",
    ".....rrrrrr.....",
    "....bsssssb.....",
    "....bssssssb....",
    "..rbssssssbr....",
    "....bssssssb....",
    ".....bssssb.....",
    ".....bUb.bUb....",
    ".....bUb.bUb....",
    ".....bbb.bbb....",
    "................")

_REHEN_CORRE_A = (
    "................",
    "..bp........pb..",
    "..bp..bbbb..pb..",
    "...b.bpppppb.b..",
    ".....bpbbpb.....",
    "......pppp......",
    "....bssssssb....",
    "....bssssssb....",
    "....bssssssb....",
    ".....bssssb.....",
    ".....bssssb.....",
    "....bUUb.bUb....",
    "...bUb....bUb...",
    "...bbb....bbb...",
    "................",
    "................")

_REHEN_CORRE_B = (
    "................",
    "................",
    "..bp..bbbb..pb..",
    "..bp.bpppppbpb..",
    "...b.bpbbpb.b...",
    "......pppp......",
    "....bssssssb....",
    "....bssssssb....",
    "....bssssssb....",
    ".....bssssb.....",
    ".....bssssb.....",
    "....bUb..bUUb...",
    "....bUb....bUb..",
    "....bbb....bbb..",
    "................",
    "................")


def prisionero(estilo: str) -> Image:
    return _hoja([_REHEN_A, _REHEN_B, _REHEN_CORRE_A, _REHEN_CORRE_B], estilo)


# --- lo que vuela ---------------------------------------------------------

_BALA_A = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......oo.......",
    "......ommo......",
    "......ommo......",
    ".......oo.......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_BALA_B = (
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......oo.......",
    "......omoo......",
    "......ommo......",
    "......oomo......",
    ".......oo.......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_TIRO_A = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......rr.......",
    "......rrrr......",
    "......rrrr......",
    ".......rr.......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_TIRO_B = (
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......rr.......",
    "......rrrr......",
    ".....rrrrrr.....",
    "......rrrr......",
    ".......rr.......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................")

_GRANADA = (
    ("................",
     "................",
     "................",
     "................",
     "......bb........",
     ".....bUUb.......",
     "....bUUUUb......",
     "....bUmUUb......",
     "....bUUUUb......",
     ".....bUUb.......",
     "......bb........",
     "................",
     "................",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "................",
     "................",
     ".......bb.......",
     "......bUUb......",
     ".....bUUUUb.....",
     ".....bUUmUb.....",
     ".....bUUUUb.....",
     "......bUUb......",
     ".......bb.......",
     "................",
     "................",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "................",
     "................",
     "........bb......",
     ".......bUUb.....",
     "......bUUUUb....",
     "......bUUmUb....",
     "......bUUUUb....",
     ".......bUUb.....",
     "........bb......",
     "................",
     "................",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "................",
     "................",
     ".......bb.......",
     "......bUUb......",
     ".....bUUUUb.....",
     ".....bUmUUb.....",
     ".....bUUUUb.....",
     "......bUUb......",
     ".......bb.......",
     "................",
     "................",
     "................",
     "................",
     "................"))


def bala(estilo: str) -> Image:
    return _hoja([_BALA_A, _BALA_B], estilo)


def tiro(estilo: str) -> Image:
    return _hoja([_TIRO_A, _TIRO_B], estilo)


def granada(estilo: str) -> Image:
    return _hoja(list(_GRANADA), estilo)


# --- el escenario ---------------------------------------------------------
#
# Visto desde arriba, asi que aqui no hay "suelo" ni "techo": hay lo que se
# pisa (hierba, camino), lo que no se puede pisar (arboles, sacos) y lo que te
# mata (el agua). El orden de la hoja es el que espera el game.yaml del genero:
#
#   0 hierba   1 arbol   2 sacos   3 agua   4 la base (meta)
#   5 camino   6 crater  7 tienda (punto de control)

_HIERBA = (
    "vvvvvvvvvvvvvvvv",
    "vvVvvvvvvvvvVvvv",
    "vvvvvvvVvvvvvvvv",
    "vvvvvvvvvvvvvvVv",
    "vVvvvvvvvvVvvvvv",
    "vvvvvvVvvvvvvvvv",
    "vvvvvvvvvvvvvvvv",
    "vvvVvvvvvvvvvVvv",
    "vvvvvvvvvVvvvvvv",
    "vvvvvVvvvvvvvvvv",
    "vvvvvvvvvvvVvvvv",
    "vVvvvvvvvvvvvvvv",
    "vvvvvvvvVvvvvvvv",
    "vvvvVvvvvvvvvvVv",
    "vvvvvvvvvvvvvvvv",
    "vvvvvvvVvvvvvvvv")

_ARBOL = (
    "vvvvVVVVVVvvvvvv",
    "vvVVVVVVVVVVvvvv",
    "vVVVvVVVVVVVVvvv",
    "VVVVVVVVvVVVVVvv",
    "VVvVVVVVVVVVVVVv",
    "VVVVVVVVVVVvVVVv",
    "VVVVVvVVVVVVVVVv",
    "VVVVVVVVVVVVVVvv",
    "vVVVVVVtVVVVVVvv",
    "vVVVVVtTtVVVVvvv",
    "vvVVVVtTtVVVvvvv",
    "vvvvvvtTtvvvvvvv",
    "vvvvvvtTtvvvvvvv",
    "vvvvvvtTtvvvvvvv",
    "vvvvvvtTtvvvvvvv",
    "vvvvvvttvvvvvvvv")

_SACOS = (
    "bbbbbbbbbbbbbbbb",
    "bssssbssssbsssbb",
    "bsssssbssssbssbb",
    "bbbbbbbbbbbbbbbb",
    "bssbssssbssssbbb",
    "bsssbssssbsssbbb",
    "bbbbbbbbbbbbbbbb",
    "bssssbssssbsssbb",
    "bsssssbssssbssbb",
    "bbbbbbbbbbbbbbbb",
    "bssbssssbssssbbb",
    "bsssbssssbsssbbb",
    "bbbbbbbbbbbbbbbb",
    "bssssbssssbsssbb",
    "bsssssbssssbssbb",
    "bbbbbbbbbbbbbbbb")

_AGUA = (
    "aaaaaaaaaaaaaaaa",
    "aAAaaaaaaAAaaaaa",
    "aaaaaaAAaaaaaaaa",
    "aaaAAaaaaaaaAAaa",
    "aaaaaaaaAAaaaaaa",
    "aAAaaaaaaaaaaaAA",
    "aaaaaAAaaaaaaaaa",
    "aaaaaaaaaaAAaaaa",
    "aaAAaaaaaaaaaaaa",
    "aaaaaaaAAaaaaaAA",
    "aaaaAAaaaaaaaaaa",
    "AAaaaaaaaaAAaaaa",
    "aaaaaaAAaaaaaaaa",
    "aaaAAaaaaaaaAAaa",
    "aaaaaaaaaaaaaaaa",
    "aAAaaaaaAAaaaaaa")

_BASE = (
    "cccccccccccccccc",
    "cbbbbbbbbbbbbbbc",
    "cbccccccccccccbc",
    "cbcbbbbbbbbbbcbc",
    "cbcbccccccccbcbc",
    "cbcbcbbbbbbcbcbc",
    "cbcbcboooobcbcbc",
    "cbcbcboooobcbcbc",
    "cbcbcboooobcbcbc",
    "cbcbcbbbbbbcbcbc",
    "cbcbccccccccbcbc",
    "cbcbbbbbbbbbbcbc",
    "cbccccccccccccbc",
    "cbbbbbbbbbbbbbbc",
    "cccccccccccccccc",
    "cccccccccccccccc")

_CAMINO = (
    "tttttttttttttttt",
    "tTttttttTtttttTt",
    "ttttTtttttttTttt",
    "ttttttttTttttttt",
    "tTttttttttTttttt",
    "ttttttTttttttttT",
    "ttTtttttttttTttt",
    "ttttttttTttttttt",
    "tttTttttttTttttt",
    "ttttttTtttttttTt",
    "tTtttttttttttttt",
    "tttttTttttTttttt",
    "ttttttttTttttttt",
    "ttTtttttttttTttt",
    "ttttttTtttttttTt",
    "tttttttttTtttttt")

_CRATER = (
    "vvvvvvvvvvvvvvvv",
    "vvvvTTTTTTvvvvvv",
    "vvvTttttttTvvvvv",
    "vvTtttTTtttTvvvv",
    "vTttTTTTTTttTvvv",
    "vTtTTTTTTTTtTvvv",
    "vTtTTTTTTTTtTvvv",
    "vTtTTTTTTTTtTvvv",
    "vTttTTTTTTttTvvv",
    "vvTtttTTtttTvvvv",
    "vvvTttttttTvvvvv",
    "vvvvTTTTTTvvvvvv",
    "vvvvvvvvvvvvvvvv",
    "vvvvvvvvvvvvvvvv",
    "vvvvvvvvvvvvvvvv",
    "vvvvvvvvvvvvvvvv")

_TIENDA = (
    "vvvvvvvvvvvvvvvv",
    "vvvvvvvbvvvvvvvv",
    "vvvvvvbUbvvvvvvv",
    "vvvvvbUUUbvvvvvv",
    "vvvvbUUUUUbvvvvv",
    "vvvbUUUbUUUbvvvv",
    "vvbUUUUbUUUUbvvv",
    "vbUUUUUbUUUUUbvv",
    "bUUUUUUbUUUUUUbv",
    "bUUUUUbbbUUUUUbv",
    "bUUUUbbbbbUUUUbv",
    "bbbbbbbbbbbbbbbv",
    "vvvvvvvvvvvvvvvv",
    "vvvvvvvvvvvvvvvv",
    "vvvvvvvvvvvvvvvv",
    "vvvvvvvvvvvvvvvv")

TILES = (_HIERBA, _ARBOL, _SACOS, _AGUA, _BASE, _CAMINO, _CRATER, _TIENDA)


def tileset(estilo: str) -> Image:
    return _hoja(list(TILES), estilo)


def todos(estilo: str) -> Dict[str, Image]:
    """Los dibujos que anade este genero, por encima de los del estilo."""
    return {
        "graficos/heroe.png": heroe(estilo),
        "graficos/soldado.png": soldado(estilo),
        "graficos/torreta.png": torreta(estilo),
        "graficos/prisionero.png": prisionero(estilo),
        "graficos/bala.png": bala(estilo),
        "graficos/tiro.png": tiro(estilo),
        "graficos/granada.png": granada(estilo),
        "graficos/tiles.png": tileset(estilo),
    }
