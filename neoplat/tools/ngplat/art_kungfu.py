"""Los dibujos del genero de kung-fu (al estilo del Bruce Lee de 1984).

Un juego de estos se ve de lado, en pantallas fijas, y todo lo que hay en la
pantalla tiene que leerse **de un vistazo**: quien eres, quien te persigue, por
donde se trepa y que farol falta. En un juego con scroll uno tiene tiempo de
mirar; aqui la pantalla cambia de golpe y con dos perseguidores encima, asi que
lo que no se distingue en medio segundo no sirve.

De ahi salen las tres decisiones de este arte:

  * **los tres personajes no se parecen en nada.** El heroe va de amarillo y es
    delgado; el luchador grande es verde y ocupa el doble; el ninja es una
    silueta azul oscuro. No comparten silueta ni color, asi que se sabe quien
    viene sin mirarlos;
  * **la patada voladora se dibuja horizontal.** Por eso los fotogramas son de
    32x32 y no de 16: un golpe que llega mas lejos tiene que **verse** mas
    largo, o el jugador no entiende por que ese ha entrado y el otro no;
  * **las lianas se leen aunque haya un bicho encima.** Van en verde claro con
    la junta oscura y ocupan la casilla entera, para que la columna por la que
    se trepa se vea entera de arriba abajo.

Como en el resto del kit los dibujos se escriben con **patrones**: una lista de
filas de texto, una letra por pixel, asi que en el propio codigo se ve lo que
sale y cambiar un color es cambiar una letra.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .art import Lienzo, patron
from . import art_hierro
from .png import Image

RGBA = Tuple[int, int, int, int]

# Trece colores. El limite es el mismo de siempre -la Mega Drive reparte cuatro
# paletas de dieciseis entre el tileset, el marcador y todos los dibujos, y el
# Atari ST gasta uno de los suyos en el fondo del nivel-, asi que con trece
# entran todos en una paleta y el color que se escribe aqui es el que sale en
# las siete maquinas.
COLORES: Dict[str, Dict[str, RGBA]] = {
    "bosque": {
        "k": (16, 16, 24, 255),       # contorno y sombra dura
        "p": (248, 208, 160, 255),    # piel
        "P": (192, 144, 104, 255),    # piel en sombra
        "y": (248, 216, 72, 255),     # el traje del heroe
        "Y": (192, 152, 32, 255),     # el traje en sombra
        "g": (96, 184, 96, 255),      # el luchador grande, y las lianas
        "G": (48, 112, 64, 255),      # su sombra
        "b": (72, 88, 152, 255),      # el ninja
        "B": (36, 44, 88, 255),       # su sombra
        "s": (168, 152, 136, 255),    # la piedra del templo
        "S": (104, 92, 88, 255),      # la piedra en sombra
        "l": (216, 208, 192, 255),    # el brillo de la piedra
        "o": (248, 152, 48, 255),     # el farol encendido
        # Y dos tonos que solo usa la pared del fondo. Van aparte porque el
        # fondo es una capa con paleta propia: puede gastar colores sin
        # quitarselos a los dibujos, y tiene que quedar **por detras**.
        "m": (72, 68, 76, 255),       # el sillar
        "n": (44, 42, 52, 255),       # el sillar en sombra
    },
    # Con seis colores no hay para trece, asi que se reparten por lo que hace
    # falta distinguir: el heroe se queda el rojo -que no sale en el decorado-,
    # el luchador grande la roca clara, el ninja la linea, y el oro es para el
    # farol, que es lo que hay que buscar.
    "hierro": {
        "k": art_hierro.LINEA,
        "p": art_hierro.CLARO, "P": art_hierro.ROCA,
        "y": art_hierro.ROJO, "Y": art_hierro.LINEA,
        "g": art_hierro.ROCA, "G": art_hierro.ROCA2,
        "b": art_hierro.ROCA2, "B": art_hierro.LINEA,
        "s": art_hierro.ROCA, "S": art_hierro.ROCA2,
        "l": art_hierro.CLARO, "o": art_hierro.ORO,
        "m": art_hierro.ROCA2, "n": art_hierro.LINEA,
    },
}


def _hoja(frames: List[Tuple[str, ...]], estilo: str, ancho: int = 32,
          alto: int = 32) -> Image:
    """Pega los fotogramas de un patron en una hoja de una fila."""
    colores = COLORES[estilo]
    hoja = Lienzo(ancho * len(frames), alto)
    for i, frame in enumerate(frames):
        hoja.blit(i * ancho, 0, patron(list(frame), colores))
    return hoja.image


# --- el heroe --------------------------------------------------------------
#
# Ocho fotogramas de 32x32, en el orden que pide el game.yaml del genero:
#
#   0 quieto      1, 2 andando      3 en el aire
#   4 el puno     5 la patada       6 tocado      7 trepando
#
# Va centrado en el cuadro y con los pies en la fila de abajo, menos la patada,
# que se estira hacia la derecha: ahi esta la gracia del fotograma.

_H_QUIETO = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "..............kkkk..............",
    ".............kppppk.............",
    ".............pkppkp.............",
    ".............pppppp.............",
    "..............pPPp..............",
    ".............kyyyyk.............",
    "............kyyyyyyk............",
    "...........kyyyyyyyyk...........",
    "...........pyyyyyyyyp...........",
    "...........pkyyyyyykp...........",
    "............kYYYYYYk............",
    ".............YYYYYY.............",
    ".............kY..Yk.............",
    ".............kY..Yk.............",
    ".............kY..Yk.............",
    ".............kY..Yk.............",
    ".............pp..pp.............",
    ".............pp..pp.............",
    "............kkkkkkkk............",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_H_ANDA_1 = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "..............kkkk..............",
    ".............kppppk.............",
    ".............pkppkp.............",
    ".............pppppp.............",
    "..............pPPp..............",
    "...........kkyyyyk..............",
    "..........kpyyyyyyk.............",
    ".........kpkyyyyyyyk............",
    "..........p.yyyyyyyp............",
    "............kyyyyykp............",
    "............kYYYYYYk............",
    ".............YYYYYY.............",
    "............kY...Yk.............",
    "...........kY.....Yk............",
    "..........kY.......Yk...........",
    ".........kY.........Yk..........",
    ".........pp.........pp..........",
    ".........pp.........pp..........",
    "........kkkk.......kkkk.........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_H_ANDA_2 = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "..............kkkk..............",
    ".............kppppk.............",
    ".............pkppkp.............",
    ".............pppppp.............",
    "..............pPPp..............",
    ".............kyyyyk.............",
    "............kyyyyyyk...kp.......",
    "...........kyyyyyyyyk.kp........",
    "...........pyyyyyyyypp..........",
    "...........pkyyyyyykp...........",
    "............kYYYYYYk............",
    ".............YYYYYY.............",
    ".............kYYYYk.............",
    ".............kY..Yk.............",
    "............kY....Yk............",
    "............kY....Yk............",
    "............pp....pp............",
    "............pp....pp............",
    "...........kkk....kkk...........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_H_SALTA = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "..............kkkk..............",
    ".............kppppk.............",
    ".............pkppkp.............",
    ".............pppppp.............",
    "..............pPPp..............",
    ".............kyyyyk.............",
    ".......kkkk.kyyyyyyk.kkkk.......",
    "......kpppkkyyyyyyyykkpppk......",
    ".....kppppppyyyyyyyyppppppk.....",
    "......kkkkkpkyyyyyykpkkkkk......",
    "............kYYYYYYk............",
    ".............YYYYYY.............",
    "............kYY..YYk............",
    "...........kY......Yk...........",
    "..........kY........Yk..........",
    "..........pp........pp..........",
    ".........kkk........kkk.........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_H_PUNO = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "...........kkkk.................",
    "..........kppppk................",
    "..........pkppkp................",
    "..........pppppp................",
    "...........pPPp.................",
    "..........kyyyyk................",
    ".........kyyyyyyk...............",
    "........kyyyyyyyykpppppppkk.....",
    "........pyyyyyyyykppppppPkk.....",
    "........pkyyyyyykp..............",
    ".........kYYYYYYk...............",
    "..........YYYYYY................",
    "..........kY..Yk................",
    "..........kY..Yk................",
    "..........kY..Yk................",
    "..........kY..Yk................",
    "..........pp..pp................",
    "..........pp..pp................",
    ".........kkkkkkkk...............",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_H_PATADA = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "....kkkk........................",
    "...kppppk.......................",
    "...pkppkp.......................",
    "...pppppp.......................",
    "....pPPp........................",
    "...kyyyyk.......................",
    "..kyyyyyyk....kkkkkkkkkkkk......",
    ".kkkyyyyykkkkkYYYYYYYYYYYYkk....",
    "kppyyyyyy.YYYYYYYYYYYYYYYYkpppk.",
    "kppyyyyyy.YYYYYYYYYYYYYYYYkpppk.",
    ".kkkyyyyk.kkkkkkkkkkkkkkkkkkkk..",
    "...kYYYYYk......................",
    "....YYYYY.......................",
    "....kYYYk.......................",
    ".....kYk........................",
    ".....ppp........................",
    "....kkkkk.......................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_H_DANO = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "...............kkkk.............",
    "..............kppppk............",
    "..............pkkkkp............",
    "..............pppppp............",
    "...............pPPp.............",
    "..............kyyyyk............",
    ".........kkk.kyyyyyyk...........",
    "........kppkkyyyyyyyyk..........",
    ".......kpppppyyyyyyyyp..........",
    "........kkkkpkyyyyyykp..........",
    ".............kYYYYYYk...........",
    "..............YYYYYY............",
    ".............kYY.Yk.............",
    "............kY...Yk.............",
    "...........kY.....Yk............",
    "..........kY.......Yk...........",
    "..........pp.......pp...........",
    ".........kkk.......kkk..........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_H_TREPA = (
    "................................",
    "................................",
    "................................",
    "................................",
    "..............kkkk..............",
    ".............kppppk.............",
    ".............pkppkp.............",
    ".............pppppp.............",
    "..............pPPp..............",
    "...........kppkkk.kppk..........",
    "...........kppkyyyykppk.........",
    "...........kkkyyyyyykkk.........",
    "............kyyyyyyk............",
    "............kyyyyyyk............",
    "............kYYYYYYk............",
    ".............YYYYYY.............",
    ".............kYYYYk.............",
    "............kY....Yk............",
    "...........kY......Yk...........",
    "...........pp......pp...........",
    "..........kkk......kkk..........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

HEROE = (_H_QUIETO, _H_ANDA_1, _H_ANDA_2, _H_SALTA, _H_PUNO, _H_PATADA,
         _H_DANO, _H_TREPA)


# --- Yamo, el luchador grande ----------------------------------------------
#
# El doble de ancho que el heroe y de otro color: se ve venir de lejos, que es
# justo lo que hace falta cuando entra por el borde de la pantalla detras de
# ti. Cinco fotogramas: quieto, dos de andar, el golpe y el tocado.
_Y_QUIETO = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kkkkkk.............",
    "............kppppppk............",
    "............pkkppkkp............",
    "............pppppppp............",
    ".............pkkkkp.............",
    ".........kkgggggggggkk..........",
    "........kgggggggggggggk.........",
    "......kpkggggggggggggggk........",
    "......kpkggggggggggggggk........",
    ".........kgggggggggggk..........",
    ".........kGGGGGGGGGGGk..........",
    "..........GGGGGGGGGG............",
    ".........kGGGGGGGGGGGk..........",
    "..........kGGGk..kGGGk..........",
    "..........kGGGk..kGGGk..........",
    "..........kGGGk..kGGGk..........",
    ".........kGGGGk..kGGGGk.........",
    ".........pppp.....pppp..........",
    "........kkkkkk...kkkkkk.........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_Y_ANDA_1 = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kkkkkk.............",
    "............kppppppk............",
    "............pkkppkkp............",
    "............pppppppp............",
    ".............pkkkkp.............",
    ".........kkgggggggggkk..........",
    "........kgggggggggggggk.........",
    ".....kppkggggggggggggggkppk.....",
    ".....kkkkggggggggggggggkkkk.....",
    ".........kgggggggggggk..........",
    ".........kGGGGGGGGGGGk..........",
    "..........GGGGGGGGGG............",
    ".........kGGGGGGGGGGGk..........",
    ".........kGGGk....kGGGk.........",
    "........kGGGk......kGGGk........",
    ".......kGGGk........kGGGk.......",
    "......kGGGGk........kGGGGk......",
    "......pppp...........pppp.......",
    ".....kkkkkk.........kkkkkk......",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_Y_ANDA_2 = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kkkkkk.............",
    "............kppppppk............",
    "............pkkppkkp............",
    "............pppppppp............",
    ".............pkkkkp.............",
    ".........kkgggggggggkk..........",
    "........kgggggggggggggk.........",
    ".......kpkgggggggggggggppk......",
    ".......kkkgggggggggggggkkk......",
    ".........kgggggggggggk..........",
    ".........kGGGGGGGGGGGk..........",
    "..........GGGGGGGGGG............",
    ".........kGGGGGGGGGGGk..........",
    "..........kGGGk..kGGGk..........",
    "..........kGGGk..kGGGk..........",
    "..........kGGGk..kGGGk..........",
    ".........kGGGGk..kGGGGk.........",
    ".........pppp.....pppp..........",
    "........kkkkkk...kkkkkk.........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

# El golpe saca el brazo entero por delante: no es un adorno, es el aviso
# que da tiempo a quitarse. Un enemigo duro sin aviso es una trampa.
_Y_PEGA = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kkkkkk.............",
    "............kppppppk............",
    "............pkkppkkp............",
    "............pppppppp............",
    ".............pkkkkp.............",
    ".........kkgggggggggkk..........",
    "........kgggggggggggggk.........",
    "........kggggggggggggggkkppppppk",
    "........kggggggggggggggkkppppppk",
    ".........kgggggggggggk..........",
    ".........kGGGGGGGGGGGk..........",
    "..........GGGGGGGGGG............",
    ".........kGGGGGGGGGGGk..........",
    "..........kGGGk..kGGGk..........",
    "..........kGGGk..kGGGk..........",
    ".........kGGGGk..kGGGGk.........",
    "........kGGGGk....kGGGGk........",
    "........pppp.......pppp.........",
    ".......kkkkkk.....kkkkkk........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_Y_DANO = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "..............kkkkkk............",
    ".............kppppppk...........",
    ".............pkkkkkkp...........",
    ".............pppppppp...........",
    "..............pkkkkp............",
    ".........kkgggggggggkk..........",
    "........kgggggggggggggk.........",
    "....kpppkggggggggggggggk........",
    "....kkkkkggggggggggggggk........",
    ".........kgggggggggggk..........",
    ".........kGGGGGGGGGGGk..........",
    "..........GGGGGGGGGG............",
    ".........kGGGGGGGGGGGk..........",
    "..........kGGGk..kGGGk..........",
    "..........kGGGk..kGGGk..........",
    "..........kGGGk..kGGGk..........",
    ".........kGGGGk..kGGGGk.........",
    ".........pppp.....pppp..........",
    "........kkkkkk...kkkkkk.........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

YAMO = (_Y_QUIETO, _Y_ANDA_1, _Y_ANDA_2, _Y_PEGA, _Y_DANO)


# --- el ninja ---------------------------------------------------------------
#
# Va entero de azul oscuro menos los ojos, que son la unica mancha clara: no
# tiene piel a la vista, asi que aunque pasen los tres juntos por delante de la
# misma pared no hay manera de confundirlo con el heroe ni con Yamo.
_N_QUIETO = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "............bblllbbb............",
    "............kbbbbbbk............",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "...........kbbbbbbbbk...........",
    "...........kbbbbbbbbk...........",
    "...........kbbbbbbbbk...........",
    "............kBBBBBBk............",
    ".............BBBBBB.............",
    ".............kB..Bk.............",
    ".............kB..Bk.............",
    ".............kB..Bk.............",
    ".............kB..Bk.............",
    ".............BB..BB.............",
    "............kkkkkkkk............",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_N_ANDA_1 = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "............bblllbbb............",
    "............kbbbbbbk............",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "...........kbbbbbbbbk...........",
    ".........kbbkbbbbbbbbk..........",
    ".........kbbkbbbbbbbbk..........",
    "............kBBBBBBk............",
    ".............BBBBBB.............",
    "............kB...Bk.............",
    "...........kB.....Bk............",
    "..........kB.......Bk...........",
    ".........kB.........Bk..........",
    ".........BB.........BB..........",
    "........kkkk.......kkkk.........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_N_ANDA_2 = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "............bblllbbb............",
    "............kbbbbbbk............",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "...........kbbbbbbbbk...........",
    "...........kbbbbbbbbkbbk........",
    "...........kbbbbbbbbkbbk........",
    "............kBBBBBBk............",
    ".............BBBBBB.............",
    ".............kB..Bk.............",
    "............kB....Bk............",
    "............kB....Bk............",
    "...........kB......Bk...........",
    "...........BB......BB...........",
    "..........kkkk....kkkk..........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

# Pega estirando el brazo hasta el borde del cuadro: llega mas lejos que
# Yamo y por eso hay que saltarselo en vez de quitarse andando.
_N_PEGA = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "............bblllbbb............",
    "............kbbbbbbk............",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "...........kbbbbbbbbk...........",
    "...........kbbbbbbbbkkkkkkkkkkl.",
    "...........kbbbbbbbbkbbbbbbbbkl.",
    "............kBBBBBBk............",
    ".............BBBBBB.............",
    "............kB...Bk.............",
    "...........kB.....Bk............",
    "..........kB.......Bk...........",
    "..........kB.......Bk...........",
    "..........BB.......BB...........",
    ".........kkkk.....kkkk..........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

_N_DANO = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "............bbkkkbbb............",
    "............kbbbbbbk............",
    ".............kbbbbk.............",
    "............kbbbbbbk............",
    "...........kbbbbbbbbk...........",
    "......kbbbbbbkbbbbbbk...........",
    "......kkkkkkkkbbbbbbk...........",
    "............kBBBBBBk............",
    ".............BBBBBB.............",
    "..............kBBk..............",
    ".............kB..Bk.............",
    "............kB....Bk............",
    "...........kB......Bk...........",
    "...........BB......BB...........",
    "..........kkkk....kkkk..........",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

NINJA = (_N_QUIETO, _N_ANDA_1, _N_ANDA_2, _N_PEGA, _N_DANO)


# --- el farol ---------------------------------------------------------------
#
# 16x16 y dos fotogramas, que es la llama subiendo y bajando. Es lo unico
# naranja de la pantalla: en un juego donde lo que se hace es **buscar** los
# faroles, el color es la mitad del diseno.
_F_ALTA = (
    "................",
    ".......kk.......",
    ".......kk.......",
    ".....kkkkkk.....",
    "....kSSSSSSk....",
    "...koooooooook..",
    "...kolllllllok..",
    "...kolllllllok..",
    "...kolllllllok..",
    "...kolllllllok..",
    "...koooooooook..",
    "....kSSSSSSk....",
    ".....kkkkkk.....",
    "................",
    "................",
    "................",
)

_F_BAJA = (
    "................",
    ".......kk.......",
    ".......kk.......",
    ".....kkkkkk.....",
    "....kSSSSSSk....",
    "...koooooooook..",
    "...koooooooook..",
    "...kooollloook..",
    "...kooollloook..",
    "...koooooooook..",
    "...koooooooook..",
    "....kSSSSSSk....",
    ".....kkkkkk.....",
    "................",
    "................",
    "................",
)

FAROL = (_F_ALTA, _F_BAJA)


# --- el templo --------------------------------------------------------------
#
# Nueve casillas de 16x16, en el orden que pide la leyenda del game.yaml:
#
#   0 vacio    1 suelo    2 pared    3 viga    4 pinchos
#   5 liana    6 puerta   7 losa     8 farolillo de adorno
#
# La liana ocupa la casilla entera a proposito. En este juego la columna por la
# que se trepa hay que verla de arriba abajo aunque tenga a alguien encima, y
# una cuerda fina de dos pixeles desaparece en cuanto se le pone un bicho
# delante.
_T_0 = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
)

_T_1 = (
    "llllllllllllllll",
    "ssssssssssssssss",
    "ssssssssssssssss",
    "sssssssSssssssss",
    "SSSSSSSSSSSSSSSS",
    "sssssssssssssssS",
    "sssssssssssssssS",
    "sssssssssssssssS",
    "SSSSSSSSSSSSSSSS",
    "sssssssSssssssss",
    "sssssssSssssssss",
    "sssssssSssssssss",
    "SSSSSSSSSSSSSSSS",
    "sssssssssssssssS",
    "sssssssssssssssS",
    "SSSSSSSSSSSSSSSS",
)

_T_2 = (
    "SSSSSSSSkSSSSSSS",
    "SSSSSSSSkSSSSSSS",
    "SSSSSSSSkSSSSSSS",
    "kkkkkkkkkkkkkkkk",
    "kSSSSSSSSSSSSSSS",
    "kSSSSSSSSSSSSSSS",
    "kSSSSSSSSSSSSSSS",
    "kkkkkkkkkkkkkkkk",
    "SSSSSSSSkSSSSSSS",
    "SSSSSSSSkSSSSSSS",
    "SSSSSSSSkSSSSSSS",
    "kkkkkkkkkkkkkkkk",
    "kSSSSSSSSSSSSSSS",
    "kSSSSSSSSSSSSSSS",
    "kSSSSSSSSSSSSSSS",
    "kkkkkkkkkkkkkkkk",
)

_T_3 = (
    "llllllllllllllll",
    "ssssssssssssssss",
    "SsSSsSSsSSsSSsSs",
    "SSSSSSSSSSSSSSSS",
    "kkkkkkkkkkkkkkkk",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
)

_T_4 = (
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".k...k...k...k..",
    "lkl.lkl.lkl.lkl.",
    "lsl.lsl.lsl.lsl.",
    "lssllssllssllssl",
    "SSSSSSSSSSSSSSSS",
    "SSSSSSSSSSSSSSSS",
)

_T_5 = (
    "....kgGGgk......",
    ".....kgGgk......",
    ".....kgGgk..g...",
    ".....kgGgk......",
    "..g..kgGgk......",
    ".....kgGgk......",
    ".....kgGgk..g...",
    ".....kgGgk......",
    "....kgGGgk......",
    ".....kgGgk......",
    ".....kgGgk..g...",
    ".....kgGgk......",
    "..g..kgGgk......",
    ".....kgGgk......",
    ".....kgGgk..g...",
    ".....kgGgk......",
)

_T_6 = (
    "..kkkkkkkkkkkk..",
    "..kooooooooook..",
    "..kolllllllllk..",
    "..kolssssssllk..",
    "..kolssssssslk..",
    "..kolssssssslk..",
    "..kolssssssslk..",
    "..kolsssoosslk..",
    "..kolsssoosslk..",
    "..kolssssssslk..",
    "..kolssssssslk..",
    "..kolssssssslk..",
    "..kolssssssslk..",
    "..kolssssssslk..",
    "..kolllllllllk..",
    "..kkkkkkkkkkkk..",
)

_T_7 = (
    "kkkkkkkkkkkkkkkk",
    "kllllllllllllllk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "klssssssssssssSk",
    "kSSSSSSSSSSSSSSk",
    "kkkkkkkkkkkkkkkk",
)

_T_8 = (
    "................",
    ".......kk.......",
    "......kkkk......",
    ".....koooook....",
    ".....kollook....",
    ".....koolook....",
    ".....koooook....",
    "......kkkk......",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
)

TILES = (_T_0, _T_1, _T_2, _T_3, _T_4, _T_5, _T_6, _T_7, _T_8)


# --- el muro del fondo ------------------------------------------------------
#
# Una sala de templo sin pared del fondo es un color plano, y con las lianas y
# las vigas por delante no se entiende que se esta dentro de un sitio. Va como
# **capa de fondo** y no como casillas: asi no ocupa mapa, no estorba al saltar
# y con `velocidad: 0.5` cambia de una sala a otra, que es lo que hace que las
# cuatro pantallas no parezcan la misma.
#
# Se dibuja oscuro a proposito. Lo que tiene que verse en esta pantalla son el
# heroe, los faroles y los dos que vienen a por ti; el muro esta para que haya
# un detras, no para mirarlo.

def muro(estilo: str) -> Image:
    c = COLORES[estilo]
    lienzo = Lienzo(256, 192)
    lienzo.rect(0, 0, 256, 192, c["m"])
    # Los sillares, con la junta partida de una hilada a la siguiente y el
    # canto de arriba un poco mas claro: es lo que hace que se vean bloques y
    # no una reja.
    for y in range(0, 192, 16):
        lienzo.rect(0, y, 256, 1, c["n"])
        lienzo.rect(0, y + 1, 256, 1, c["S"])
        salto = 16 if (y // 16) % 2 else 0
        for x in range(salto, 256, 32):
            lienzo.rect(x, y, 1, 16, c["n"])
    # Y las columnas, cada cuatro casillas: son las que dan el ritmo y las que
    # hacen que al cambiar de sala se note que te has movido.
    for px in range(8, 256, 64):
        lienzo.rect(px, 0, 20, 192, c["S"])
        lienzo.rect(px + 2, 0, 3, 192, c["s"])
        lienzo.rect(px + 1, 0, 1, 192, c["n"])
        lienzo.rect(px + 17, 0, 3, 192, c["n"])
        # el capitel y la basa, que son las que dicen que es una columna
        for cy in (14, 168):
            lienzo.rect(px - 3, cy, 26, 8, c["S"])
            lienzo.rect(px - 3, cy + 1, 26, 2, c["s"])
            lienzo.rect(px - 3, cy, 26, 1, c["n"])
            lienzo.rect(px - 3, cy + 7, 26, 1, c["n"])
    # Y una franja de musgo abajo del todo: es lo unico vivo del fondo y lo que
    # dice que el templo lleva mucho tiempo ahi.
    for x in range(0, 256, 8):
        alto = 3 + ((x // 8) % 3) * 2
        lienzo.rect(x, 192 - alto, 8, alto, c["G"])
    return lienzo.image


# --- las hojas --------------------------------------------------------------

def heroe(estilo: str) -> Image:
    return _hoja(list(HEROE), estilo)


def yamo(estilo: str) -> Image:
    return _hoja(list(YAMO), estilo)


def ninja(estilo: str) -> Image:
    return _hoja(list(NINJA), estilo)


def farol(estilo: str) -> Image:
    return _hoja(list(FAROL), estilo, 16, 16)


def tileset(estilo: str) -> Image:
    return _hoja(list(TILES), estilo, 16, 16)


def todos(estilo: str) -> Dict[str, Image]:
    """Los dibujos que anade este genero, por encima de los del estilo."""
    return {
        "graficos/heroe.png": heroe(estilo),
        "graficos/yamo.png": yamo(estilo),
        "graficos/ninja.png": ninja(estilo),
        "graficos/farol.png": farol(estilo),
        "graficos/tiles.png": tileset(estilo),
        "graficos/muro.png": muro(estilo),
    }
