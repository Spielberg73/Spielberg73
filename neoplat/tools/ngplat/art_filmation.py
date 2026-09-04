"""Los dibujos del genero isometrico (al estilo Knight Lore).

Aqui casi nada se dibuja a mano pixel a pixel, y no es por vagueria: en una
vista isometrica las formas son **geometria**. Un suelo son rombos de 32x16
puestos en rejilla y un cubo es ese mismo rombo levantado, con la cara de
arriba clara y las dos de delante en sombra. Escribirlo como formulas hace dos
cosas que un patron de letras no puede: que un cubo de tres alturas salga
exactamente igual de encajado que uno de una, y que el suelo de la sala cuadre
al pixel con la proyeccion del motor, que es la misma cuenta.

Lo que si va a mano son los actores -el heroe y los bichos-, porque ahi lo que
importa es que se lean de un vistazo y eso no sale de una formula.

Las medidas, que son las del motor (np_types.h):

  * un rombo de suelo mide 32x16 y una casilla de planta 16x16 pixeles;
  * un cubo de altura h se dibuja en 32 x (h + 16): el rombo de arriba, las dos
    caras de delante y el pico de abajo;
  * una sala son 8x8 casillas, o sea un rombo grande de 256x128 pixeles, y con
    las dos paredes del fondo por encima el dibujo entero de una habitacion
    mide 256x176: eso es lo que el compilador pega en cada una.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .art import Lienzo, patron
from . import art_hierro
from .png import Image

RGBA = Tuple[int, int, int, int]

# La paleta del genero: **catorce colores y ni uno mas**.
#
# No es una cifra caprichosa: la Mega Drive tiene cuatro paletas de dieciseis y
# el compilador tiene que meter en ellas el tileset, el marcador y todos los
# dibujos del juego. Un juego isometrico trae doce hojas -el heroe, los bichos,
# los cinco cubos, las cosas- y si entre todas suman mas de quince tonos, el
# reparto tiene que aproximar y el resultado es una pared azul y un heroe
# marron. Y el Atari ST aprieta un poco mas: de sus dieciseis, uno se lo lleva
# el color de fondo del nivel. Con catorce entran todas en una sola paleta y el
# color que se dibuja aqui es exactamente el que sale en las siete maquinas.
#
# Por eso hay letras que valen lo mismo: 'l' (el brillo) es el tono de arriba
# de la piedra y 'j' (la junta) es el contorno. Se dejan con nombre propio
# porque asi el dibujo se lee -"aqui va un brillo"- y cambiar el reparto es
# cambiar una linea de esta tabla.
COLORES: Dict[str, Dict[str, RGBA]] = {
    "bosque": {
        "b": (16, 16, 24, 255),       # contorno
        "s": (128, 136, 168, 255),    # piedra: cara de arriba
        "S": (88, 96, 128, 255),      # piedra: cara derecha
        "d": (56, 60, 88, 255),       # piedra: cara izquierda
        "f": (96, 100, 136, 255),     # losa clara del suelo
        "F": (72, 76, 108, 255),      # losa oscura del suelo
        "e": (240, 224, 200, 255),    # piel
        "r": (208, 64, 56, 255),      # capa
        "R": (136, 32, 32, 255),      # capa en sombra, y la capucha de espaldas
        "z": (64, 96, 184, 255),      # ropa
        "w": (248, 248, 248, 255),    # blanco del ojo y del fantasma
        "o": (248, 208, 72, 255),     # oro: llave, talisman, la salida
        "v": (128, 200, 96, 255),     # bicho
        "V": (72, 128, 56, 255),      # bicho en sombra
    },
    "hierro": {
        "b": art_hierro.LINEA,
        "s": art_hierro.ROCA, "S": art_hierro.ROCA2, "d": art_hierro.LINEA,
        "f": art_hierro.ROCA2, "F": art_hierro.LINEA,
        "e": art_hierro.CLARO,
        "r": art_hierro.ROJO, "R": art_hierro.LINEA,
        "z": art_hierro.ROCA,
        "w": art_hierro.CLARO,
        "o": art_hierro.ORO,
        "v": art_hierro.CLARO, "V": art_hierro.ROCA,
    },
}

# Y las letras que comparten tono con otra. Van aparte para que se vea de un
# vistazo cuales son las catorce de verdad.
for _estilo in COLORES.values():
    _estilo["l"] = _estilo["s"]        # el brillo de la arista
    _estilo["j"] = _estilo["b"]        # la junta entre losas
    _estilo["E"] = _estilo["R"]        # la capucha vista de espaldas
    _estilo["W"] = _estilo["S"]        # el fantasma en sombra
    _estilo["O"] = _estilo["d"]        # el oro en sombra
    _estilo["n"] = _estilo["r"]        # el fuego de la antorcha
    _estilo["m"] = _estilo["d"]        # la madera
    _estilo["Z"] = _estilo["b"]        # la ropa en sombra



# ------------------------------------------------------------- la geometria

def semiancho(fila: int, alto: int = 16) -> int:
    """Medio ancho del rombo en esa fila, en pixeles.

    Un rombo de 32x16: en la fila de arriba mide 2 pixeles de ancho, va
    creciendo de cuatro en cuatro y en el centro mide 32. Es la misma cuenta
    para arriba y para abajo, que es lo que hace que un rombo pegue con el de
    al lado sin dejar hueco ni pisarse.
    """
    medio = alto // 2
    d = fila if fila < medio else alto - 1 - fila
    return (d + 1) * 2


def rombo(lienzo: Lienzo, cx: int, cy: int, relleno: RGBA,
          borde: RGBA = None, alto: int = 16) -> None:
    """Un rombo de 32x`alto` con su centro en (cx, cy)."""
    for fila in range(alto):
        hw = semiancho(fila, alto)
        y = cy - alto // 2 + fila
        for x in range(cx - hw, cx + hw):
            lienzo.px(x, y, relleno)
        if borde is not None:
            lienzo.px(cx - hw, y, borde)
            lienzo.px(cx + hw - 1, y, borde)


def cubo(alto: int, colores: Dict[str, RGBA]) -> Image:
    """Un prisma isometrico de `alto` pixeles sobre un rombo de 32x16.

    Sale en un cuadro de 32 x (alto + 16) y se apoya en el centro de abajo del
    cuadro, que es lo que espera el motor: `caja: [16, 16]` con
    `desplazamiento: [8, alto - 8]`.

    Las tres caras llevan tres tonos distintos -arriba claro, derecha media,
    izquierda oscura- porque en una vista isometrica **el tono es la unica
    pista de volumen que hay**: con un solo color, una pila de tres cubos se ve
    como una mancha y no se sabe donde acaba uno y empieza otro.
    """
    alto_total = alto + 16
    c = Lienzo(32, alto_total)
    borde = colores["b"]
    # las dos caras de delante: se extruyen hacia abajo desde el rombo de arriba
    for fila in range(8, 16):
        hw = semiancho(fila)
        y = fila - 8                      # fila dentro de la mitad de abajo
        for dy in range(alto):
            yy = y + 8 + dy
            for x in range(32 - hw - 16, 16):
                c.px(x, yy, colores["d"])         # cara izquierda
            for x in range(16, 16 + hw):
                c.px(x, yy, colores["S"])         # cara derecha
    # el rombo de arriba, encima de todo
    rombo(c, 16, 8, colores["s"], borde)
    # y una linea de brillo en la arista de arriba a la izquierda
    for fila in range(0, 8):
        hw = semiancho(fila)
        c.px(16 - hw, fila, colores["l"])
        c.px(16 - hw + 1, fila, colores["l"])
    # el contorno de las dos caras de delante y el pico de abajo
    for fila in range(8, 16):
        hw = semiancho(fila)
        y = fila - 8 + 8
        c.px(16 - hw, y + alto - 1, borde)
        c.px(16 + hw - 1, y + alto - 1, borde)
    for dy in range(alto):
        c.px(0, 8 + dy, borde)
        c.px(31, 8 + dy, borde)
    # la arista vertical de delante, donde se juntan las dos caras
    for dy in range(alto):
        c.px(15, 16 + dy, borde)
        c.px(16, 16 + dy, borde)
    return c.image


def suelo_de_sala(colores: Dict[str, RGBA]) -> Image:
    """El suelo de una sala entera: 8x8 rombos en 256x128 pixeles.

    Las losas van en damero, con dos tonos, porque en isometrica un suelo de un
    solo color no dice nada: sin el damero no se sabe si has andado dos
    casillas o cuatro, y en un juego que va de medir saltos eso es todo.
    """
    c = Lienzo(256, 128)
    for ly in range(8):
        for lx in range(8):
            cx = (lx - ly) * 16 + 128
            cy = (lx + ly) * 8 + 8
            claro = (lx + ly) % 2 == 0
            rombo(c, cx, cy, colores["f"] if claro else colores["F"],
                  colores["j"])
    return c.image


def sala(colores: Dict[str, RGBA], puerta: int = 4) -> Image:
    """Una habitacion entera dibujada: las dos paredes del fondo y el suelo.

    Mide 256x176 y se pega a partir del tile (2, 2) de la pantalla, o sea en el
    pixel (32, 32). De ahi salen las cuentas: la casilla (lx, ly) cae en
    (128 + 16*(lx-ly), 56 + 8*(lx+ly)) dentro de este dibujo, que sumado al
    origen es justo lo que calcula np_pantalla en el motor.

    **Por que las paredes van aqui y no como cubos.** Un cubo es un sprite que
    hay que ordenar y dibujar en cada frame. Las dos paredes del fondo de una
    sala son quince casillas, y quince cubos mas los de dentro no le caben a la
    Mega Drive en un frame: medido, 479 lineas de trabajo para las 262 que dura
    un frame, o sea el juego a la mitad de velocidad. Y ademas es innecesario:
    las paredes del fondo **nunca** tapan a nadie -estan detras de todo por
    definicion- asi que no necesitan entrar en la fila de profundidad. Pintadas
    aqui salen gratis, que es como lo hacian los juegos del genero.

    Las dos paredes llevan un hueco en la casilla `puerta` (la quinta), que es
    por donde se pasa a la habitacion de al lado. Una sala que ahi no tenga
    salida tapa el hueco poniendo un cubo de muro en el mapa: es el unico sitio
    donde hace falta uno.
    """
    c = Lienzo(256, 176)
    c.blit(0, 48, suelo_de_sala(colores))
    pared = cubo(48, colores)
    # De mas lejos a mas cerca: la esquina primero y luego los dos brazos, que
    # es el orden en el que un cubo tapa al que tiene detras.
    if puerta != 0:
        c.blit(112, 0, pared)
    for d in range(1, 8):
        if d != puerta:
            c.blit(112 + 16 * d, 8 * d, pared)     # pared de la derecha (ly=0)
            c.blit(112 - 16 * d, 8 * d, pared)     # pared de la izquierda (lx=0)
    return c.image


def tileset(estilo: str) -> Image:
    """El tileset del genero: una fila vacia y debajo la habitacion entera.

    La primera fila de 16 tiles se queda transparente a proposito: el tile 0 es
    "aqui no se pinta nada", que es lo que se ve fuera de la sala. El dibujo de
    la habitacion -las dos paredes del fondo y el suelo- empieza en el tile 16,
    que es lo que dice `sala:` en el game.yaml.
    """
    colores = COLORES[estilo]
    c = Lienzo(256, 192)
    c.blit(0, 16, sala(colores))
    return c.image


# ------------------------------------------------------------------ el heroe
#
# Ocho fotogramas de 16x32, con los pies en la fila de abajo del cuadro:
#
#   0 quieto de frente   1, 2 andando de frente
#   3 quieto de espaldas 4, 5 andando de espaldas
#   6 en el aire         7 tocado
#
# De frente y de espaldas son las dos unicas vistas que hacen falta: el motor
# espeja el dibujo y con eso salen los cuatro lados de la planta. Mira siempre
# hacia la derecha de la pantalla, que en la planta es el este (de frente) o el
# norte (de espaldas).

_HEROE_FRENTE = (
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
    ".....bbbb.......",
    "....beeeeb......",
    "....bewewb......",
    "....beeeeb......",
    ".....bebb.......",
    "....brrrrb......",
    "...brrrrrrb.....",
    "..breerrreeb....",
    "..beeerrreeb....",
    "..bbeerrreebb...",
    "....brrrrb......",
    "....bzzzzb......",
    "....bzzzzb......",
    "....bzZZzb......",
    "....bz..zb......",
    "....bz..zb......",
    "...bzz..zzb.....",
    "...bZZ..ZZb.....",
    "...bbb..bbb.....",
    "................",
    "................",
    "................",
)

_HEROE_FRENTE_A = (
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
    ".....bbbb.......",
    "....beeeeb......",
    "....bewewb......",
    "....beeeeb......",
    ".....bebb.......",
    "....brrrrb......",
    "...brrrrrrb.....",
    "..breerrrb......",
    "..beeerrrbeb....",
    "..bbeerrrbeeb...",
    "....brrrrb......",
    "....bzzzzb......",
    "....bzzzzb......",
    "...bzZZzzb......",
    "...bz...zb......",
    "..bzz...zb......",
    "..bzz....zb.....",
    "..bZZ....ZZb....",
    "..bbb....bbb....",
    "................",
    "................",
    "................",
)

_HEROE_FRENTE_B = (
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
    ".....bbbb.......",
    "....beeeeb......",
    "....bewewb......",
    "....beeeeb......",
    ".....bebb.......",
    "....brrrrb......",
    "...brrrrrrb.....",
    "...brrrreeb.....",
    "..beberrreeb....",
    ".beebbrrrbeb....",
    "....brrrrb......",
    "....bzzzzb......",
    "....bzzzzb......",
    "....bzzZZzb.....",
    "....bz...zb.....",
    "....bz...zzb....",
    "...bzz....zb....",
    "...bZZ....ZZb...",
    "...bbb....bbb...",
    "................",
    "................",
    "................",
)

_HEROE_ESPALDA = (
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
    ".....bbbb.......",
    "....bEEEEb......",
    "....bEEEEb......",
    "....bEEEEb......",
    ".....bEbb.......",
    "....brrrrb......",
    "...brrrrrrb.....",
    "..brrrrrrrrb....",
    "..brrrrrrrrb....",
    "..bbrrrrrrbb....",
    "....brrrrb......",
    "....bzzzzb......",
    "....bzzzzb......",
    "....bzZZzb......",
    "....bz..zb......",
    "....bz..zb......",
    "...bzz..zzb.....",
    "...bZZ..ZZb.....",
    "...bbb..bbb.....",
    "................",
    "................",
    "................",
)

_HEROE_ESPALDA_A = (
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
    ".....bbbb.......",
    "....bEEEEb......",
    "....bEEEEb......",
    "....bEEEEb......",
    ".....bEbb.......",
    "....brrrrb......",
    "...brrrrrrb.....",
    "..brrrrrrrb.....",
    "..brrrrrrrbb....",
    "..bbrrrrrrbEb...",
    "....brrrrb......",
    "....bzzzzb......",
    "....bzzzzb......",
    "...bzZZzzb......",
    "...bz...zb......",
    "..bzz...zb......",
    "..bzz....zb.....",
    "..bZZ....ZZb....",
    "..bbb....bbb....",
    "................",
    "................",
    "................",
)

_HEROE_ESPALDA_B = (
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
    ".....bbbb.......",
    "....bEEEEb......",
    "....bEEEEb......",
    "....bEEEEb......",
    ".....bEbb.......",
    "....brrrrb......",
    "...brrrrrrb.....",
    "...brrrrrrrb....",
    "..bEbrrrrrrb....",
    ".bEEbbrrrrrb....",
    "....brrrrb......",
    "....bzzzzb......",
    "....bzzzzb......",
    "....bzzZZzb.....",
    "....bz...zb.....",
    "....bz...zzb....",
    "...bzz....zb....",
    "...bZZ....ZZb...",
    "...bbb....bbb...",
    "................",
    "................",
    "................",
)

_HEROE_SALTO = (
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
    ".....bbbb.......",
    "....beeeeb......",
    "....bewewb......",
    "....beeeeb......",
    ".....bebb.......",
    "..b.brrrrb.b....",
    ".bebbrrrrbbeb...",
    ".beebrrrrbeeb...",
    "..bbbrrrrbbb....",
    "....brrrrb......",
    "....bzzzzb......",
    "....bzzzzb......",
    "...bzZZZZzb.....",
    "..bzz....zzb....",
    "..bz......zb....",
    "..bZ......Zb....",
    "..bb......bb....",
    "................",
    "................",
    "................",
    "................",
    "................",
)

_HEROE_TOCADO = (
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
    "....bbbb........",
    "...beeeeb.......",
    "...bebebb.......",
    "...beeeeb.......",
    "....bebb........",
    "..b.brrrb..b....",
    ".bebbrrrrbbeb...",
    ".beebrrrrbeeb...",
    "..bbbrrrrbbb....",
    "....brrrrb......",
    "....bzzzzb......",
    "....bzzzzb......",
    "...bzZZzzb......",
    "...bz...zb......",
    "..bzz...zb......",
    "..bZZ...Zb......",
    "..bbb...bb......",
    "................",
    "................",
    "................",
    "................",
    "................",
)

_HEROE = (_HEROE_FRENTE, _HEROE_FRENTE_A, _HEROE_FRENTE_B,
          _HEROE_ESPALDA, _HEROE_ESPALDA_A, _HEROE_ESPALDA_B,
          _HEROE_SALTO, _HEROE_TOCADO)


def _hoja(frames, estilo: str, ancho: int, alto: int) -> Image:
    """Pega los fotogramas de un patron en una hoja horizontal."""
    colores = COLORES[estilo]
    hoja = Lienzo(ancho * len(frames), alto)
    for i, frame in enumerate(frames):
        hoja.blit(i * ancho, 0, patron(list(frame), colores))
    return hoja.image


def heroe(estilo: str) -> Image:
    return _hoja(_HEROE, estilo, 16, 32)


# ------------------------------------------------------------------ los bichos
#
# Dos, y los dos hacen algo que el escenario no puede hacer: la arana anda por
# la planta y te obliga a rodearla, y el fantasma **flota** subiendo y bajando,
# asi que a veces se salta por encima y a veces no. En isometrica esa es la
# gracia: el bicho ocupa una altura, no una linea.

_ARANA = (
    ("................",
     "................",
     "..b..........b..",
     "..bb........bb..",
     "...bb.bbbb.bb...",
     "....bbvvvvbb....",
     "...bvvwvvwvvb...",
     "..bvvvvvvvvvvb..",
     "..bvvVVvvVVvvb..",
     "...bvvvvvvvvb...",
     "....bVVVVVVb....",
     "...bb.bbbb.bb...",
     "..bb........bb..",
     "..b..........b..",
     "................",
     "................"),
    ("................",
     "................",
     "...b........b...",
     "..bb........bb..",
     "..b.bb.bbbb.b...",
     "....bbvvvvbb....",
     "...bvvwvvwvvb...",
     "..bvvvvvvvvvvb..",
     "..bvvVVvvVVvvb..",
     "...bvvvvvvvvb...",
     "....bVVVVVVb....",
     "...b.b.bbbb.b...",
     "..bb..........b.",
     "...b.........bb.",
     "................",
     "................"),
)

_FANTASMA = (
    ("................",
     "................",
     ".....bbbb.......",
     "...bbwwwwbb.....",
     "..bwwwwwwwwb....",
     "..bwwbwwbwwb....",
     "..bwwbwwbwwb....",
     "..bwwwwwwwwb....",
     "..bwwwwwwwwb....",
     "..bwWwwwwWwb....",
     "..bwWWwwWWwb....",
     "...bwWbbWwb.....",
     "....bbb.bb......",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "................",
     ".....bbbb.......",
     "...bbwwwwbb.....",
     "..bwwwwwwwwb....",
     "..bwwbwwbwwb....",
     "..bwwbwwbwwb....",
     "..bwwwwwwwwb....",
     "..bwwwwwwwwb....",
     "..bwWwwwwWwb....",
     "..bwWWwwWWwb....",
     "...bwbbbbwb.....",
     "....b....b......",
     "................",
     "................"),
)


def arana(estilo: str) -> Image:
    return _hoja(_ARANA, estilo, 16, 16)


def fantasma(estilo: str) -> Image:
    return _hoja(_FANTASMA, estilo, 16, 16)


# ------------------------------------------------------------------ las cosas

_LLAVE = (
    ("................",
     "................",
     "................",
     "................",
     ".....bbb........",
     "....boOob.......",
     "....bo.ob.......",
     "....boOob.......",
     ".....booob......",
     "......bOoob.....",
     ".......bOoob....",
     "........bOob....",
     ".........bb.....",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "................",
     "................",
     "................",
     ".....bbb........",
     "....boOob.......",
     "....bo.ob.......",
     "....boOob.......",
     ".....booob......",
     "......bOoob.....",
     ".......bOoob....",
     "........bOob....",
     ".........bb.....",
     "................",
     "................"),
)

_TALISMAN = (
    ("................",
     "................",
     "................",
     "......bbb.......",
     ".....bowob......",
     "....bowwwob.....",
     "....bowwwob.....",
     "....booOoob.....",
     ".....bOoOb......",
     "......bOb.......",
     ".......b........",
     "................",
     "................",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "................",
     "......bbb.......",
     ".....boOob......",
     "....booOoob.....",
     "....boOwOob.....",
     "....booOoob.....",
     ".....boOob......",
     "......bOb.......",
     ".......b........",
     "................",
     "................",
     "................",
     "................",
     "................"),
)


def llave(estilo: str) -> Image:
    return _hoja(_LLAVE, estilo, 16, 16)


def talisman(estilo: str) -> Image:
    return _hoja(_TALISMAN, estilo, 16, 16)


# --------------------------------------------------------------- los cubos
#
# Tres alturas, que son las tres cosas que se pueden poner en una sala:
#
#   losa    16 px  el escalon al que se sube de un salto
#   pilar   32 px  dos alturas: hay que subir por la losa
#   muro    48 px  no se salta: es una pared
#
# Los tres salen de la misma formula, y por eso encajan entre si al pixel.

def escalon(estilo: str) -> Image:
    """Un escalon de 4 pixeles: el unico relieve que se sube **andando**.

    Va en un cuadro de 32x32 y no de 32x20, que es lo que mediria el prisma,
    porque los fotogramas tienen que ser multiplos de 16 en las siete maquinas.
    Lo que manda no es lo que mide el cuadro sino donde se apoya: el rombo de
    abajo tiene que quedar pegado al borde de abajo del cuadro, y de ahi sale
    el `desplazamiento: [8, alto_del_cuadro - 24]` que pide el compilador. Con
    32 de alto, eso es [8, 8].
    """
    colores = COLORES[estilo]
    c = Lienzo(32, 32)
    c.blit(0, 12, cubo(4, colores))        # el prisma, pegado abajo
    return c.image


def losa(estilo: str) -> Image:
    return cubo(16, COLORES[estilo])


def pilar(estilo: str) -> Image:
    return cubo(32, COLORES[estilo])


def muro(estilo: str) -> Image:
    return cubo(48, COLORES[estilo])


def puerta(estilo: str) -> Image:
    """Un muro con un talisman grabado: es el cerrojo.

    Se ve que es una puerta y no una pared, que es lo unico que le pedimos: en
    un juego de estos, saber que **eso** se abre con algo es medio puzle.
    """
    colores = COLORES[estilo]
    c = Lienzo(32, 64)
    c.blit(0, 0, cubo(48, colores))
    # el grabado, en la cara de la derecha
    marca = (
        "..oo..",
        ".oooo.",
        "oo..oo",
        ".oooo.",
        "..oo..",
    )
    for y, fila in enumerate(marca):
        for x, letra in enumerate(fila):
            if letra == "o":
                c.px(18 + x, 30 + y, colores["o"])
    return c.image


def pinchos(estilo: str) -> Image:
    """Los pinchos del suelo: un rombo con puas.

    No levantan -son casilla de suelo, con `alto: 0`-, asi que van dibujados
    dentro de un cubo de altura cero: el propio rombo del suelo. Se salta por
    encima, y eso es lo que los hace un obstaculo y no una muerte.
    """
    colores = COLORES[estilo]
    c = Lienzo(32, 16)
    rombo(c, 16, 8, colores["F"], colores["b"])
    for i, (px, py) in enumerate(((10, 4), (16, 6), (22, 4), (13, 9), (19, 9))):
        for h in range(5):
            ancho = 3 - h // 2
            for dx in range(-ancho // 2, ancho // 2 + 1):
                c.px(px + dx, py + 4 - h, colores["l"] if h > 2 else colores["s"])
        c.px(px, py - 1, colores["w"])
    return c.image


def salida(estilo: str) -> Image:
    """La meta: una losa de oro con la marca del castillo.

    Es raso, como los pinchos: se pisa. En un juego donde subirse a las cosas
    es medio verbo, que la salida este **en el suelo** es lo que hace que
    llegar a ella sea una ruta y no un salto.
    """
    colores = COLORES[estilo]
    c = Lienzo(32, 16)
    rombo(c, 16, 8, colores["o"], colores["b"])
    rombo(c, 16, 8, colores["O"], None, 8)
    for x in range(12, 20):
        c.px(x, 7, colores["w"])
        c.px(x, 8, colores["w"])
    return c.image


def antorcha(estilo: str) -> Image:
    """Decorado que se apoya en el suelo: un pebetero encendido.

    Es un cubo bajito con fuego encima. No hace nada -no frena, no quema- y
    esta aqui por una razon de diseno: una sala isometrica vacia no se lee, y
    dos antorchas dicen donde estan las esquinas.
    """
    colores = COLORES[estilo]
    c = Lienzo(32, 32)
    c.blit(0, 0, cubo(16, colores))
    llama = (
        "..n..",
        ".non.",
        "nooon",
        ".non.",
        "..n..",
    )
    for y, fila in enumerate(llama):
        for x, letra in enumerate(fila):
            if letra == "n":
                c.px(14 + x, y, colores["n"])
            elif letra == "o":
                c.px(14 + x, y, colores["o"])
    return c.image


def todos(estilo: str) -> Dict[str, Image]:
    """Todos los dibujos del genero, listos para escribir en el proyecto."""
    return {
        "graficos/heroe.png": heroe(estilo),
        "graficos/tiles.png": tileset(estilo),
        "graficos/arana.png": arana(estilo),
        "graficos/fantasma.png": fantasma(estilo),
        "graficos/llave.png": llave(estilo),
        "graficos/talisman.png": talisman(estilo),
        "graficos/escalon.png": escalon(estilo),
        "graficos/losa.png": losa(estilo),
        "graficos/pilar.png": pilar(estilo),
        "graficos/muro.png": muro(estilo),
        "graficos/puerta.png": puerta(estilo),
        "graficos/pinchos.png": pinchos(estilo),
        "graficos/salida.png": salida(estilo),
        "graficos/antorcha.png": antorcha(estilo),
    }
