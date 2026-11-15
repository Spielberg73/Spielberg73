"""Los dibujos de CIELO ROJO, el ejemplo de la bestia.

Es el estilo de *Shadow of the Beast* (Psygnosis, Amiga, 1989), y lo que se
copia de el no son los dibujos -esos son nuestros- sino **las tres decisiones
que hacian que aquello se viera asi**:

  1. **El cielo rojo.** Un cielo naranja y rojo con el sol enorme y bajo, y
     todo lo demas recortado en negro contra el. Un juego de 1989 no podia
     pintar luz, asi que pintaba siluetas y dejaba que el cielo hiciera el
     trabajo. Sigue funcionando.
  2. **Capas y capas.** Aquello presumia de doce planos de parallax. Aqui son
     cuatro -que es lo que cabe sin que la Neo Geo se quede sin tiles-, pero
     el truco es el mismo: cada capa va mas despacio que la de delante, y la
     sensacion de fondo no la da el dibujo, la da la **diferencia** entre
     velocidades.
  3. **El bicho es grande.** El protagonista ocupa 24x32 en vez de los 16x16
     de los demas ejemplos del kit. Un sprite grande se come mas tiles y mas
     ciclos, y a cambio se le ve la cara: era medio juego.

Los colores son pocos a proposito: cada imagen cabe en quince colores mas el
transparente, que es lo que lleva una paleta de estas maquinas. El cielo son
bandas y no un degradado suave justo por eso -un degradado de verdad se come
la paleta entera-, y resulta que bandeado se parece mas a lo de entonces.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .art import Lienzo, patron
from .png import Image

RGBA = Tuple[int, int, int, int]

# --- la paleta de todo esto ------------------------------------------------
#
# Nombres en vez de numeros porque los va a tocar quien quiera cambiar el tono
# del juego, y "#3a1226" no le dice nada a nadie.
NEGRO = (10, 6, 12, 255)
NOCHE = (26, 14, 30, 255)            # la silueta mas lejana
MORADO = (58, 28, 51, 255)           # la de en medio
MORADO_CLARO = (86, 44, 66, 255)
SANGRE = (122, 30, 24, 255)          # el cielo arriba
ROJO = (170, 48, 24, 255)
NARANJA = (214, 92, 28, 255)         # cerca del horizonte
AMBAR = (238, 142, 46, 255)
SOL = (252, 206, 120, 255)
HUESO = (232, 220, 196, 255)         # la piel de la bestia
HUESO_SOMBRA = (176, 160, 138, 255)
MELENA = (246, 240, 228, 255)        # el pelo, que es lo que se ve de lejos
TELA = (42, 46, 90, 255)             # el taparrabos
SANGRE_OSCURA = (96, 20, 16, 255)
TIERRA = (54, 40, 38, 255)
TIERRA_CLARA = (82, 62, 54, 255)
HIERBA = (40, 56, 40, 255)
CLARO = (0, 0, 0, 0)

ANCHO_CAPA = 256                     # 16 tiles de ancho, como las demas capas


def _franjas(lienzo: Lienzo, bandas: List[Tuple[int, RGBA]]) -> None:
    """Pinta el lienzo en bandas horizontales: (alto, color) de arriba abajo."""
    y = 0
    for alto, color in bandas:
        lienzo.rect(0, y, lienzo.image.width, alto, color)
        y += alto


def cielo() -> Image:
    """El cielo rojo con el sol bajo. La capa que no se mueve casi nada.

    El sol va **entero dentro de la imagen** y no a caballo del borde: la capa
    se repite en bucle mientras el escenario se desliza, y un sol partido por
    la mitad se nota en cuanto da la primera vuelta.
    """
    c = Lienzo(ANCHO_CAPA, 96)
    _franjas(c, [(18, SANGRE), (16, ROJO), (18, NARANJA),
                 (20, AMBAR), (24, SOL)])

    # El sol: un disco grande y bajo, cortado por las bandas de abajo para que
    # parezca que se esta metiendo en el horizonte.
    cx, cy, radio = 176, 62, 30
    for y in range(cy - radio, cy + radio):
        for x in range(cx - radio, cx + radio):
            dx, dy = x - cx, y - cy
            if dx * dx + dy * dy <= radio * radio and y < 84:
                c.px(x, y, SOL)
    # y tres rayas oscuras cruzandolo, que es lo que hacia aquel juego para
    # que el sol no fuera una pelota lisa
    for y in (52, 60, 68):
        c.rect(cx - radio, y, radio * 2, 2, AMBAR)
    return c.image


def _silueta(ancho: int, alto: int, color: RGBA, perfil: List[int],
             relleno: RGBA = None) -> Image:
    """Una silueta a partir de su perfil: para cada x, donde empieza el negro.

    Es como se dibuja una montana o un bosque de un juego de estos: no hay
    volumen, hay un borde. Lo que queda por debajo del borde se rellena y ya.
    """
    c = Lienzo(ancho, alto)
    for x in range(ancho):
        cima = max(0, min(alto, perfil[x % len(perfil)]))
        c.rect(x, cima, 1, alto - cima, relleno or color)
        if relleno:
            c.rect(x, cima, 1, 1, color)      # el borde, un poco mas claro
    return c.image


def _perfil_montes(ancho: int) -> List[int]:
    """El perfil de la cordillera: suma de ondas que caben justas en el ancho.

    La capa se pega consigo misma en bucle mientras el escenario se desliza,
    asi que el ultimo pixel tiene que casar con el primero o se ve la costura
    cada vez que da la vuelta. Con ondas de **numero entero de vueltas** eso
    sale gratis: 1, 2, 3, 5 y 11 vueltas a lo ancho de la imagen casan solas, y
    como no comparten divisores el dibujo tarda en repetirse aunque cada onda
    por separado sea de lo mas regular.
    """
    import math

    perfil = []
    for x in range(ancho):
        a = x / ancho * 2 * math.pi
        altura = (16
                  + 13 * math.sin(a + 0.7)
                  + 8 * math.sin(2 * a + 2.1)
                  + 5 * math.sin(3 * a + 4.0)
                  + 3 * math.sin(5 * a + 1.3)
                  + 2 * math.sin(11 * a))
        perfil.append(int(round(max(2, altura))))
    return perfil


def montes() -> Image:
    """La cordillera del fondo: casi negra, y la que menos se mueve.

    Va **sin borde**: a esa distancia no hay detalle, hay recorte contra el
    cielo. El borde lo lleva la capa de delante, que es la que se mira.
    """
    return _silueta(ANCHO_CAPA, 80, NOCHE, _perfil_montes(ANCHO_CAPA))


def _arbol(c: Lienzo, x: int, suelo: int, alto: int, color: RGBA) -> None:
    """Un arbol muerto: tronco y dos ramas. Sin hojas, que aqui no hay.

    Lo que salga por un lado entra por el otro: la capa se repite en bucle, y
    una rama cortada en el borde se ve como un palo partido cada vez que la
    imagen da la vuelta.
    """
    ancho = c.image.width

    def pintar(px: int, py: int) -> None:
        c.px(px % ancho, py, color)

    tronco = max(2, alto // 10)
    for dx in range(tronco):
        for dy in range(alto):
            pintar(x + dx, suelo - dy)
    for lado, altura in ((-1, alto // 2), (1, alto // 3)):
        brazo = alto // 3
        for i in range(brazo):
            pintar(x + (tronco // 2) + lado * i, suelo - altura - i)
            pintar(x + (tronco // 2) + lado * i, suelo - altura - i - 1)


def bosque() -> Image:
    """Los arboles de en medio. Se mueven el doble que los montes.

    Llevan el canto en morado claro: es lo unico que los separa de la
    cordillera de detras, que es del mismo negro violeta. Sin ese canto las dos
    capas se funden en una mancha y el parallax deja de notarse, que es
    justo lo que no puede pasar en un juego que va de eso.
    """
    c = Lienzo(ANCHO_CAPA, 80)
    sitios = [(4, 46), (26, 32), (44, 52), (70, 38), (96, 58),
              (118, 34), (140, 48), (166, 40), (188, 56), (214, 36),
              (238, 50)]
    for x, alto in sitios:
        _arbol(c, x, 79, alto, MORADO)
        _arbol(c, x + 1, 79, alto - 2, MORADO_CLARO)
    c.rect(0, 72, ANCHO_CAPA, 8, MORADO)        # la linea de tierra
    c.rect(0, 72, ANCHO_CAPA, 1, MORADO_CLARO)
    return c.image


def troncos() -> Image:
    """Los troncos de delante, casi negros y enormes: son los que dan la
    sensacion de velocidad, porque son los que pasan mas deprisa."""
    c = Lienzo(ANCHO_CAPA, 96)
    for x, ancho in ((20, 10), (96, 14), (168, 9), (226, 12)):
        c.rect(x, 0, ancho, 96, NEGRO)
        c.rect(x + ancho - 2, 0, 2, 96, NOCHE)   # un canto, para que no sea plano
    return c.image


def espada() -> Image:
    """El filo que sale delante mientras se pega.

    En este genero `sprite:` del ataque es **el arma**, no el brazo: el motor
    la dibuja justo mientras el golpe hace dano, asi que lo que se ve es
    exactamente lo que llega. Tres fotogramas, que son los tres niveles de
    mejora: el mismo filo, mas largo.
    """
    anchos = (24, 36, 48)
    hoja = Lienzo(48 * len(anchos), 16)
    for i, largo in enumerate(anchos):
        c = Lienzo(48, 16)
        c.rect(0, 7, largo, 2, MELENA)                 # el filo
        c.rect(0, 9, largo - 3, 1, HUESO_SOMBRA)       # la sombra de abajo
        c.rect(largo - 4, 6, 4, 4, MELENA)             # la punta
        c.rect(0, 5, 3, 6, AMBAR)                      # la empunadura
        hoja.blit(i * 48, 0, c.image)
    return hoja.image


# --- los bichos ------------------------------------------------------------

_SABUESO = (
    ("........................",
     "..nn................nn..",
     ".nmmn..............nmmn.",
     ".nmmmnnnnnnnnnnnnnnmmmn.",
     "nmmmmmmmmmmmmmmmmmmmmmmn",
     "nmmrrmmmmmmmmmmmmmmrrmmn",
     "nmmmmmmmmmmmmmmmmmmmmmmn",
     ".nmmnnmmnn....nnmmnnmmn.",
     "..nn...nn......nn...nn..",
     "........................",
     "........................",
     "........................",
     "........................",
     "........................",
     "........................",
     "........................"),
    ("........................",
     "........................",
     "..nn................nn..",
     ".nmmnnnnnnnnnnnnnnnnmmn.",
     "nmmmmmmmmmmmmmmmmmmmmmmn",
     "nmmrrmmmmmmmmmmmmmmrrmmn",
     "nmmmmmmmmmmmmmmmmmmmmmmn",
     ".nmmnn..nnmmnn..nnmmnn..",
     "..nn.....nn......nn.....",
     "........................",
     "........................",
     "........................",
     "........................",
     "........................",
     "........................",
     "........................"),
)


def sabueso() -> Image:
    """El perro del camino: una silueta baja con los ojos rojos.

    Negro sobre el cielo, que es como se veia todo en aquel juego: no hace
    falta que se le distingan las patas, hace falta que se sepa que viene.
    """
    colores = {"n": NEGRO, "m": NOCHE, "r": SANGRE}
    hoja = Lienzo(24 * len(_SABUESO), 16)
    for i, filas in enumerate(_SABUESO):
        hoja.blit(i * 24, 0, patron(list(filas), colores))
    return hoja.image


_CABEZA = (
    ("................",
     "....nnnnnnnn....",
     "..nnmmmmmmmmnn..",
     ".nmmmmmmmmmmmmn.",
     ".nmmrrmmmmrrmmn.",
     ".nmmrrmmmmrrmmn.",
     ".nmmmmmmmmmmmmn.",
     ".nmmmnnnnnnmmmn.",
     "..nmmmmmmmmmmn..",
     "...nnmmmmmmnn...",
     ".....nnnnnn.....",
     "......n..n......",
     "................",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "....nnnnnnnn....",
     "..nnmmmmmmmmnn..",
     ".nmmrrmmmmrrmmn.",
     ".nmmrrmmmmrrmmn.",
     ".nmmmmmmmmmmmmn.",
     ".nmmnnnnnnnnmmn.",
     "..nmmmmmmmmmmn..",
     "...nnmmmmmmnn...",
     "....n.nnnn.n....",
     "................",
     "................",
     "................",
     "................",
     "................"),
)


def cabeza() -> Image:
    """La cabeza que flota: el bicho que va por el aire y no te deja parar."""
    colores = {"n": NEGRO, "m": MORADO, "r": SANGRE}
    hoja = Lienzo(16 * len(_CABEZA), 16)
    for i, filas in enumerate(_CABEZA):
        hoja.blit(i * 16, 0, patron(list(filas), colores))
    return hoja.image


# --- lo que se coge ---------------------------------------------------------

_GEMA = (
    ("................",
     "......rrrr......",
     ".....rssssr.....",
     "....rsssssssr...",
     "...rssrrrrsssr..",
     "...rsrrrrrrrsr..",
     "....rrrrrrrr....",
     ".....rrrrrr.....",
     "......rrrr......",
     ".......rr.......",
     "................",
     "................",
     "................",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "......rrrr......",
     ".....rssssr.....",
     "....rsssssssr...",
     "....rssrrrsssr..",
     ".....rrrrrrrr...",
     "......rrrrrr....",
     ".......rrrr.....",
     "........rr......",
     "................",
     "................",
     "................",
     "................",
     "................",
     "................"),
)

_LLAVE = (
    ("................",
     "....mmmm........",
     "...mm..mm.......",
     "...mm..mm.......",
     "....mmmm........",
     ".....mm.........",
     ".....mm.........",
     ".....mm.........",
     ".....mmmm.......",
     ".....mm.........",
     ".....mmm........",
     "................",
     "................",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "....mmmm........",
     "...mm..mm.......",
     "...mm..mm.......",
     "....mmmm........",
     ".....mm.........",
     ".....mm.........",
     ".....mmmm.......",
     ".....mm.........",
     ".....mmm........",
     "................",
     "................",
     "................",
     "................",
     "................"),
)

_VIDA = (
    ("................",
     "................",
     "...rr....rr.....",
     "..rsrrr.rrrr....",
     ".rsrrrrrrrrrr...",
     ".rsrrrrrrrrrr...",
     ".rrrrrrrrrrrr...",
     "..rrrrrrrrrr....",
     "...rrrrrrrr.....",
     "....rrrrrr......",
     ".....rrrr.......",
     "......rr........",
     "................",
     "................",
     "................",
     "................"),
    ("................",
     "................",
     "................",
     "...rr....rr.....",
     "..rsrrr.rrrr....",
     "..rrrrrrrrrr....",
     "...rrrrrrrr.....",
     "....rrrrrr......",
     ".....rrrr.......",
     "......rr........",
     "................",
     "................",
     "................",
     "................",
     "................",
     "................"),
)


def _dos_frames(frames, colores) -> Image:
    hoja = Lienzo(16 * len(frames), 16)
    for i, filas in enumerate(frames):
        hoja.blit(i * 16, 0, patron(list(filas), colores))
    return hoja.image


def gema() -> Image:
    """Lo que se recoge por puntos: una piedra roja que brilla."""
    return _dos_frames(_GEMA, {"r": SANGRE, "s": AMBAR})


def llave() -> Image:
    """La llave de la puerta del final."""
    return _dos_frames(_LLAVE, {"m": MELENA})


def vida() -> Image:
    """El corazon, que aqui es lo unico que te devuelve aguante."""
    return _dos_frames(_VIDA, {"r": SANGRE, "s": AMBAR})


# --- el suelo --------------------------------------------------------------

def _tile_tierra(con_hierba: bool) -> Image:
    c = Lienzo(16, 16)
    c.rect(0, 0, 16, 16, TIERRA)
    for x, y in ((2, 4), (9, 3), (5, 9), (12, 11), (7, 13)):
        c.rect(x, y, 2, 1, TIERRA_CLARA)
    if con_hierba:
        c.rect(0, 0, 16, 3, HIERBA)
        c.rect(0, 3, 16, 1, TIERRA_CLARA)
    return c.image


def _tile_pinchos() -> Image:
    c = Lienzo(16, 16)
    for i in range(4):
        base = i * 4
        for y in range(8):
            ancho = max(1, (y + 1) // 2)
            c.rect(base + 2 - ancho // 2, 15 - y, max(1, ancho), 1, HUESO)
    c.rect(0, 14, 16, 2, TIERRA)
    return c.image


def _tile_plataforma() -> Image:
    c = Lienzo(16, 16)
    c.rect(0, 0, 16, 4, MORADO_CLARO)
    c.rect(0, 4, 16, 2, MORADO)
    return c.image


def _tile_meta() -> Image:
    """La puerta del final: un arco de piedra con el cielo dentro."""
    c = Lienzo(16, 16)
    c.rect(1, 0, 14, 16, MORADO)
    c.rect(3, 3, 10, 13, SANGRE)
    c.rect(4, 5, 8, 11, NARANJA)
    return c.image


def _tile_escalera(izquierda: bool) -> Image:
    c = Lienzo(16, 16)
    x = 2 if izquierda else 10
    c.rect(x, 0, 4, 16, MORADO_CLARO)
    for y in (2, 7, 12):
        c.rect(0, y, 16, 2, MORADO_CLARO)
    return c.image


def tileset() -> Image:
    """Los nueve tiles que pide la leyenda del genero, en su orden."""
    piezas = [Lienzo(16, 16).image,          # 0 vacio
              _tile_tierra(True),            # 1 solido con hierba
              _tile_plataforma(),            # 2 plataforma
              _tile_pinchos(),               # 3 peligro
              _tile_meta(),                  # 4 meta
              _tile_tierra(False),           # 5 solido de dentro
              _tile_escalera(False),         # 6 escalera
              _tile_escalera(True),          # 7 escalera izquierda
              Lienzo(16, 16).image]          # 8 control (no se ve)
    hoja = Lienzo(16 * len(piezas), 16)
    for i, pieza in enumerate(piezas):
        hoja.blit(i * 16, 0, pieza)
    return hoja.image


def todos() -> Dict[str, Image]:
    """Todos los dibujos del ejemplo, por el nombre con el que van dentro."""
    return {
        "graficos/espada.png": espada(),
        "graficos/gema.png": gema(),
        "graficos/llave.png": llave(),
        "graficos/vida.png": vida(),
        "graficos/sabueso.png": sabueso(),
        "graficos/cabeza.png": cabeza(),
        "graficos/tiles.png": tileset(),
        "graficos/cielo.png": cielo(),
        "graficos/montes.png": montes(),
        "graficos/bosque.png": bosque(),
        "graficos/troncos.png": troncos(),
    }
