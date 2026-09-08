"""Los dibujos del genero de aventura grafica: una habitacion y un cursor.

Aqui no hay heroe, ni bichos, ni plataformas. Lo que hay que dibujar es **un
sitio**: una pared con su papel pintado, un suelo de tarima, una puerta, una
ventana, un cuadro y las cosas que se pueden mirar, coger y usar. El jugador es
una flecha.

Eso cambia como se dibuja. En los demas generos cada tile es una pieza suelta
que se repite por todo el mapa; aqui casi todo son **muebles**, o sea dibujos
grandes partidos en casillas de 16x16 que solo tienen sentido puestos en su
sitio. Por eso este archivo dibuja el mueble entero en un lienzo de 32x32 y
luego lo corta: una puerta se disena como una puerta y no como cuatro cuartos
de puerta.

El tileset entero cabe en una paleta de quince colores mas el transparente, que
es lo que lleva una paleta de la Neo Geo -y de las otras seis maquinas-. No es
una casualidad: es el limite con el que hay que dibujar.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from . import art_hierro
from .art import Lienzo, patron
from .png import Image

RGBA = Tuple[int, int, int, int]

# Los quince colores de la habitacion. Con nombres cortos porque se usan en
# cada linea de cada dibujo, y por parejas -claro y oscuro- porque lo que hace
# que un mueble parezca un mueble es la sombra, no el detalle.
COLORES: Dict[str, Dict[str, RGBA]] = {
    "bosque": {
        "b": (24, 20, 32, 255),       # contorno
        "w": (208, 192, 168, 255),    # papel de la pared
        "W": (160, 140, 116, 255),    # la raya del papel
        "m": (160, 104, 56, 255),     # madera
        "M": (104, 64, 32, 255),      # madera en sombra
        "n": (56, 36, 20, 255),       # madera casi negra (marcos y juntas)
        "o": (248, 208, 72, 255),     # laton, luz, oro
        "y": (248, 152, 48, 255),     # llama
        "r": (176, 56, 48, 255),      # tela roja
        "R": (112, 32, 28, 255),      # tela roja en sombra
        "a": (72, 104, 168, 255),     # el cielo por la ventana
        "A": (32, 48, 96, 255),       # el cielo de noche
        "p": (144, 140, 150, 255),    # piedra del sotano
        "k": (12, 10, 16, 255),       # negro: huecos y sombras
        "c": (240, 232, 208, 255),    # papel, cal, brillos
    },
    # En el estilo de hierro solo hay seis colores para todo el juego: la
    # habitacion se dibuja igual y lo que cambia es que las parejas claro y
    # oscuro caen en las dos unicas rocas que hay.
    "hierro": {
        "b": art_hierro.LINEA, "w": art_hierro.ROCA, "W": art_hierro.ROCA2,
        "m": art_hierro.ROCA, "M": art_hierro.ROCA2, "n": art_hierro.LINEA,
        "o": art_hierro.ORO, "y": art_hierro.ORO,
        "r": art_hierro.ROJO, "R": art_hierro.LINEA,
        "a": art_hierro.ROCA, "A": art_hierro.ROCA2,
        "p": art_hierro.ROCA, "k": art_hierro.LINEA, "c": art_hierro.CLARO,
    },
}


def _cortar(lienzo: Lienzo, cols: int, filas: int) -> List[Image]:
    """Parte un mueble en casillas de 16x16, de izquierda a derecha y de arriba
    abajo. Es el orden en el que hay que escribirlas luego en el mapa."""
    trozos: List[Image] = []
    for fy in range(filas):
        for fx in range(cols):
            trozo = Lienzo(16, 16)
            for y in range(16):
                for x in range(16):
                    trozo.px(x, y, lienzo.image.get(fx * 16 + x, fy * 16 + y))
            trozos.append(trozo.image)
    return trozos


def _lleno(w: int, h: int, color: RGBA) -> Lienzo:
    c = Lienzo(w, h)
    c.rect(0, 0, w, h, color)
    return c


# --- las tres casillas que se repiten -------------------------------------
#
# Pared, zocalo y suelo son el 90% de la habitacion: van repetidas por todas
# partes y por eso son las unicas que se dibujan como una casilla suelta.

def _pared(col: Dict[str, RGBA]) -> Image:
    """Papel pintado: dos rayas verticales, que es lo que da la escala."""
    c = _lleno(16, 16, col["w"])
    for x in (3, 11):
        c.rect(x, 0, 1, 16, col["W"])
    return c.image


def _zocalo(col: Dict[str, RGBA]) -> Image:
    """La fila donde la pared se convierte en madera. Va justo encima del suelo
    y es lo que hace que la habitacion tenga suelo y no se caiga."""
    c = _lleno(16, 16, col["w"])
    for x in (3, 11):
        c.rect(x, 0, 1, 4, col["W"])
    c.rect(0, 4, 16, 1, col["b"])       # la moldura
    c.rect(0, 5, 16, 2, col["m"])
    c.rect(0, 7, 16, 1, col["M"])
    c.rect(0, 8, 16, 7, col["m"])       # el panel
    for x in (3, 12):
        c.rect(x, 8, 1, 7, col["n"])
    c.rect(0, 14, 16, 1, col["M"])
    c.rect(0, 15, 16, 1, col["b"])
    return c.image


def _suelo(col: Dict[str, RGBA]) -> Image:
    """Tarima: tablas horizontales de cinco pixeles.

    Sin juntas verticales a proposito. Una junta vertical en un tile de 16 se
    repite cada 16 pixeles por todo el suelo, y entonces la tarima deja de
    parecer tarima y parece un muro de ladrillo tumbado -que es exactamente lo
    que salia en la primera version de este dibujo-."""
    c = _lleno(16, 16, col["m"])
    for y in (4, 9, 15):
        c.rect(0, y, 16, 1, col["M"])
    for y in (0, 5, 10):
        c.rect(0, y, 16, 1, col["m"])
    c.rect(2, 2, 6, 1, col["M"])          # dos vetas, y ninguna llega al borde
    c.rect(9, 12, 5, 1, col["M"])
    return c.image


# --- los muebles ----------------------------------------------------------

def _puerta(col: Dict[str, RGBA]) -> List[Image]:
    """La puerta de la calle: 32x48, marco oscuro, dos cuarterones y pomo.

    Tres casillas de alto y no dos: una puerta de 32x32 en una habitacion de
    224 pixeles no parece una puerta, parece un armario. La altura es lo unico
    que hace que se lea como una salida."""
    c = _lleno(32, 48, col["m"])
    c.rect(0, 0, 32, 2, col["b"])            # dintel
    c.rect(0, 0, 2, 48, col["n"])            # jambas
    c.rect(30, 0, 2, 48, col["n"])
    c.rect(2, 2, 28, 2, col["M"])
    for arriba, alto in ((6, 16), (26, 18)):
        c.rect(5, arriba, 22, alto, col["M"])
        c.rect(6, arriba + 1, 20, alto - 2, col["m"])
        c.rect(7, arriba + 2, 18, 1, col["M"])
    c.rect(0, 46, 32, 2, col["n"])           # el umbral
    c.rect(24, 23, 3, 4, col["o"])           # el pomo
    c.px(25, 24, col["c"])
    return _cortar(c, 2, 3)


def _ventana(col: Dict[str, RGBA]) -> List[Image]:
    """La ventana: 32x32, cuatro cristales y la lluvia fuera."""
    c = _lleno(32, 32, col["n"])
    c.rect(2, 2, 28, 28, col["A"])
    for x in (2, 17):
        for y in (2, 17):
            c.rect(x, y, 13, 13, col["a"])
            c.rect(x, y, 13, 1, col["A"])
            c.rect(x, y, 1, 13, col["A"])
    c.rect(15, 0, 2, 32, col["n"])           # los travesanos
    c.rect(0, 15, 32, 2, col["n"])
    c.rect(0, 0, 32, 2, col["m"])            # el marco
    c.rect(0, 30, 32, 2, col["m"])
    c.rect(0, 0, 2, 32, col["m"])
    c.rect(30, 0, 2, 32, col["m"])
    for x, y in ((6, 6), (10, 20), (22, 9), (26, 23), (19, 4)):
        c.rect(x, y, 1, 3, col["c"])         # la lluvia
    return _cortar(c, 2, 2)


def _cuadro(col: Dict[str, RGBA]) -> List[Image]:
    """El retrato del abuelo: 32x32, marco dorado y una cara seria.

    Es el unico personaje del juego, y por eso es el unico sitio donde el verbo
    'hablar' tiene con quien hablar. Que sea un cuadro y no una persona no es
    pereza: una aventura de 1987 se hacia asi, con lo que cabia."""
    c = _lleno(32, 32, col["o"])
    c.rect(1, 1, 30, 30, col["M"])
    c.rect(3, 3, 26, 26, col["n"])
    c.rect(4, 4, 24, 24, col["A"])           # el fondo del cuadro
    c.rect(11, 6, 10, 12, col["c"])          # la cara
    c.rect(10, 8, 1, 8, col["c"])
    c.rect(21, 8, 1, 8, col["c"])
    c.rect(10, 4, 12, 3, col["p"])           # el pelo, con entradas
    c.rect(9, 5, 1, 5, col["p"])
    c.rect(22, 5, 1, 5, col["p"])
    c.rect(12, 6, 3, 1, col["c"])
    c.rect(17, 6, 3, 1, col["c"])
    c.rect(12, 9, 3, 1, col["p"])            # las cejas
    c.rect(17, 9, 3, 1, col["p"])
    c.rect(13, 10, 1, 2, col["k"])           # los ojos, de un pixel de ancho
    c.rect(18, 10, 1, 2, col["k"])
    c.rect(15, 11, 2, 3, col["W"])           # la nariz
    c.rect(11, 12, 1, 3, col["W"])           # las mejillas
    c.rect(20, 12, 1, 3, col["W"])
    c.rect(13, 16, 6, 2, col["p"])           # el bigote
    c.rect(14, 15, 4, 1, col["M"])           # la boca, sin una sonrisa
    c.rect(9, 18, 14, 8, col["R"])           # la levita
    c.rect(14, 18, 4, 5, col["c"])           # la camisa
    c.rect(15, 19, 2, 3, col["r"])           # la corbata
    return _cortar(c, 2, 2)


def _mesa(col: Dict[str, RGBA]) -> List[Image]:
    """La mesa de roble: 32x32, tablero arriba y dos patas.

    Lleva la pared y el zocalo pintados detras porque la mesa esta **contra la
    pared**: un mueble con el fondo transparente ensena el color de fondo del
    juego por los huecos, y ahi lo que tiene que verse es la habitacion."""
    c = Lienzo(32, 32)
    for x in (0, 16):
        c.blit(x, 0, _pared(col))
        c.blit(x, 16, _zocalo(col))
    c.rect(0, 6, 32, 2, col["M"])            # el canto del tablero
    c.rect(0, 4, 32, 2, col["m"])
    c.rect(1, 8, 30, 1, col["n"])            # la sombra de debajo
    for x in (3, 25):
        c.rect(x, 9, 4, 21, col["M"])        # las patas
        c.rect(x, 9, 2, 21, col["m"])
        c.rect(x - 1, 29, 6, 2, col["n"])    # las bases
    c.rect(5, 12, 22, 2, col["M"])           # el travesano
    return _cortar(c, 2, 2)


def _llave_en_la_mesa(col: Dict[str, RGBA], mesa: Image) -> Image:
    """La casilla de arriba a la derecha de la mesa, con la llave encima.

    Es la mesa **y** la llave en el mismo dibujo, no un objeto suelto: aqui no
    hay sprites sueltos por el escenario, hay casillas. Cuando el jugador la
    coge, el motor ensena en su sitio lo que diga `debajo:` -o sea la mesa
    pelada- y la llave desaparece de la mesa sin que nadie mueva un tile."""
    c = Lienzo(16, 16)
    c.blit(0, 0, mesa)
    c.rect(3, 1, 4, 4, col["o"])             # el anillo
    c.rect(4, 2, 2, 2, col["M"])
    c.rect(7, 2, 6, 2, col["o"])             # la cana
    c.rect(11, 4, 2, 1, col["o"])            # los dientes
    c.rect(8, 4, 1, 1, col["o"])
    return c.image


def _estante(col: Dict[str, RGBA]) -> Image:
    """Una casilla de estanteria, con sus libros. Se repite tal cual: tres a lo
    ancho y dos a lo alto ya parecen una biblioteca."""
    c = _lleno(16, 16, col["n"])
    c.rect(0, 0, 16, 1, col["M"])
    anchos = (3, 2, 4, 3, 2)
    x = 1
    for i, ancho in enumerate(anchos):
        if x + ancho > 15:
            break
        color = (col["r"], col["o"], col["a"], col["R"], col["m"])[i % 5]
        alto = 11 - (i % 3)
        c.rect(x, 15 - alto, ancho, alto, color)
        c.rect(x, 15 - alto, ancho, 1, col["c"])
        x += ancho + 1
    c.rect(0, 14, 16, 2, col["m"])           # la balda
    c.rect(0, 15, 16, 1, col["M"])
    return c.image


def _farol(col: Dict[str, RGBA]) -> Image:
    """El farol de aceite colgado de la pared. Sobre el papel pintado, para que
    al cogerlo quede la pared y no un agujero."""
    c = Lienzo(16, 16)
    c.blit(0, 0, _pared(col))
    c.rect(7, 0, 2, 3, col["n"])             # la alcayata
    c.rect(4, 3, 8, 1, col["n"])             # el asa
    c.rect(3, 4, 10, 2, col["M"])            # el sombrerete
    c.rect(4, 6, 8, 7, col["o"])             # el cristal
    c.rect(6, 8, 4, 4, col["y"])             # la llama
    c.rect(7, 9, 2, 2, col["c"])
    c.rect(3, 13, 10, 2, col["M"])           # la base
    c.rect(4, 4, 1, 9, col["n"])
    c.rect(11, 4, 1, 9, col["n"])
    return c.image


def _trampilla(col: Dict[str, RGBA]) -> List[Image]:
    """La trampilla del sotano: 32x16, en el suelo, con su anilla."""
    c = Lienzo(32, 16)
    c.blit(0, 0, _suelo(col))
    c.blit(16, 0, _suelo(col))
    c.rect(1, 2, 30, 12, col["n"])
    c.rect(2, 3, 28, 10, col["M"])
    c.rect(3, 4, 26, 4, col["m"])
    c.rect(3, 9, 26, 3, col["m"])
    c.rect(14, 3, 1, 10, col["n"])
    c.rect(3, 5, 3, 2, col["k"])             # las bisagras
    c.rect(3, 10, 3, 2, col["k"])
    c.rect(20, 5, 6, 6, col["o"])            # la anilla
    c.rect(21, 6, 4, 4, col["M"])
    c.rect(22, 7, 2, 2, col["o"])
    return _cortar(c, 2, 1)


# --- el sotano ------------------------------------------------------------

def _pared_piedra(col: Dict[str, RGBA]) -> Image:
    """Sillares. Las juntas van cambiadas de fila para que no salga una cuadricula."""
    c = _lleno(16, 16, col["p"])
    for y in (0, 8):
        c.rect(0, y, 16, 1, col["k"])
    c.rect(5, 1, 1, 7, col["k"])
    c.rect(13, 9, 1, 7, col["k"])
    c.rect(1, 2, 3, 1, col["W"])             # las manchas de humedad
    c.rect(9, 11, 4, 1, col["W"])
    return c.image


def _suelo_piedra(col: Dict[str, RGBA]) -> Image:
    c = _lleno(16, 16, col["W"])
    c.rect(0, 0, 16, 1, col["k"])
    c.rect(7, 0, 1, 16, col["k"])
    c.rect(1, 1, 5, 2, col["p"])
    c.rect(9, 5, 5, 2, col["p"])
    return c.image


def _escalera(col: Dict[str, RGBA]) -> Image:
    """Un peldano de la escalera que sube a la casa. Se repite en vertical."""
    c = _lleno(16, 16, col["k"])
    c.rect(0, 0, 16, 5, col["m"])
    c.rect(0, 5, 16, 2, col["M"])
    c.rect(0, 8, 16, 5, col["m"])
    c.rect(0, 13, 16, 2, col["M"])
    c.rect(0, 0, 1, 16, col["n"])
    return c.image


def _cofre(col: Dict[str, RGBA]) -> List[Image]:
    """El arcon del abuelo: 32x32, con dos flejes y un candado. Contra la pared
    del sotano, que es la que lleva pintada detras."""
    c = Lienzo(32, 32)
    for x in (0, 16):
        for y in (0, 16):
            c.blit(x, y, _pared_piedra(col))
    c.rect(2, 4, 28, 12, col["M"])           # la tapa, curva a lo bruto
    c.rect(4, 2, 24, 4, col["M"])
    c.rect(5, 3, 22, 2, col["m"])
    c.rect(3, 7, 26, 3, col["m"])
    c.rect(2, 16, 28, 14, col["M"])          # el cuerpo
    c.rect(3, 18, 26, 4, col["m"])
    c.rect(3, 24, 26, 4, col["m"])
    for x in (7, 22):                        # los flejes
        c.rect(x, 2, 3, 28, col["o"])
        c.rect(x + 1, 3, 1, 26, col["y"])
    c.rect(14, 14, 5, 7, col["o"])           # el candado
    c.rect(15, 16, 3, 3, col["k"])
    c.rect(2, 30, 28, 2, col["n"])
    return _cortar(c, 2, 2)


def _palanca(col: Dict[str, RGBA]) -> Image:
    """La palanca, colgada de dos clavos en la pared de piedra."""
    c = Lienzo(16, 16)
    c.blit(0, 0, _pared_piedra(col))
    c.rect(1, 5, 14, 5, col["k"])            # la sombra, que es lo que la separa
    c.rect(2, 5, 11, 3, col["p"])            # de la pared: sin ella no se ve
    c.rect(2, 5, 11, 1, col["c"])
    c.rect(11, 2, 3, 6, col["p"])            # el cuello, doblado
    c.rect(12, 2, 2, 5, col["c"])
    c.rect(13, 1, 2, 2, col["p"])            # la una, partida en dos
    c.rect(13, 1, 1, 1, col["c"])
    c.rect(2, 8, 4, 3, col["p"])             # y el otro extremo, aplanado
    c.rect(2, 8, 4, 1, col["c"])
    c.rect(4, 3, 1, 2, col["k"])             # los clavos
    c.rect(9, 3, 1, 2, col["k"])
    return c.image


def _barril(col: Dict[str, RGBA]) -> Image:
    c = Lienzo(16, 16)
    c.blit(0, 0, _suelo_piedra(col))
    c.rect(3, 2, 10, 13, col["M"])
    c.rect(4, 3, 8, 11, col["m"])
    c.rect(3, 5, 10, 2, col["n"])
    c.rect(3, 10, 10, 2, col["n"])
    c.rect(4, 2, 8, 1, col["m"])
    c.rect(3, 14, 10, 1, col["k"])
    return c.image


def _telarana(col: Dict[str, RGBA]) -> Image:
    """La telarana de la esquina. No sirve para nada y por eso hace falta: una
    habitacion en la que todo sirve para algo no es una habitacion."""
    c = Lienzo(16, 16)
    c.blit(0, 0, _pared_piedra(col))
    # Solo la esquina: una telarana que ocupa la casilla entera tapa la pared y
    # se lee como una reja. Tres radios y dos hilos bastan para que se entienda.
    for i in range(9):
        c.px(i, i, col["c"])
    for i in range(11):
        c.px(0, i, col["c"])
        c.px(i, 0, col["c"])
    for r in (4, 8):
        for i in range(r + 1):
            if (i + r) % 2 == 0:
                c.px(i, r - i, col["c"])
    return c.image


# --- el cursor ------------------------------------------------------------
#
# Tres fotogramas: quieto y dos de moverse. La punta esta arriba a la
# izquierda, en el pixel (2, 1), y la caja del jugador mide 12x12: asi la
# casilla que el motor da por senalada -la del centro de la caja- cae dentro de
# la flecha y no dos tiles mas alla, que es lo que convierte un cursor en algo
# que se puede apuntar.

_CURSOR = (
    "..b.............",
    "..bb............",
    "..bcb...........",
    "..bccb..........",
    "..bcccb.........",
    "..bccccb........",
    "..bcccccb.......",
    "..bccccccb......",
    "..bcccccccb.....",
    "..bccccbbbbb....",
    "..bccbcb........",
    "..bcb.bccb......",
    "..bb...bccb.....",
    "..b.....bccb....",
    ".........bcb....",
    "..........b.....")

_CURSOR_B = (
    "..b.............",
    "..bb............",
    "..bob...........",
    "..boob..........",
    "..booob.........",
    "..boooob........",
    "..booooob.......",
    "..bcccoccb......",
    "..bcccccccb.....",
    "..bccccbbbbb....",
    "..bccbcb........",
    "..bcb.bccb......",
    "..bb...bccb.....",
    "..b.....bccb....",
    ".........bcb....",
    "..........b.....")

_CURSOR_C = (
    "..b.............",
    "..bb............",
    "..bcb...........",
    "..bccb..........",
    "..bcccb.........",
    "..bccccb........",
    "..bcooocb.......",
    "..bcoooocb......",
    "..bcccccccb.....",
    "..bccccbbbbb....",
    "..bccbcb........",
    "..bcb.bccb......",
    "..bb...bccb.....",
    "..b.....bccb....",
    ".........bcb....",
    "..........b.....")


def cursor(estilo: str) -> Image:
    col = COLORES[estilo]
    hoja = Lienzo(48, 16)
    for i, frame in enumerate((_CURSOR, _CURSOR_B, _CURSOR_C)):
        hoja.blit(i * 16, 0, patron(list(frame), col))
    return hoja.image


# --- los dos objetos que se llevan ---------------------------------------
#
# No se ponen nunca en el mapa: los da un guion cuando coges la casilla que los
# tiene dibujados. Existen para que el marcador pueda escribir lo que llevas
# encima, que en una aventura es la mitad de la informacion.

def _objeto(dibujar, col: Dict[str, RGBA]) -> Image:
    """Dos fotogramas iguales menos un brillo, para que el objeto no parezca
    pegado a la pantalla."""
    hoja = Lienzo(32, 16)
    for i in range(2):
        c = Lienzo(16, 16)
        dibujar(c, col, i)
        hoja.blit(i * 16, 0, c.image)
    return hoja.image


def _dibujo_llave(c: Lienzo, col: Dict[str, RGBA], brillo: int) -> None:
    c.rect(2, 5, 5, 5, col["o"])
    c.rect(3, 6, 3, 3, col["M"])
    c.rect(7, 6, 7, 3, col["o"])
    c.rect(12, 9, 2, 2, col["o"])
    c.rect(9, 9, 1, 2, col["o"])
    if brillo:
        c.rect(3, 4, 2, 1, col["c"])


def _dibujo_farol(c: Lienzo, col: Dict[str, RGBA], brillo: int) -> None:
    c.rect(5, 1, 6, 1, col["n"])
    c.rect(4, 2, 8, 2, col["M"])
    c.rect(5, 4, 6, 8, col["o"])
    c.rect(6, 6, 4, 5, col["y"])
    c.rect(7, 7 + brillo, 2, 2, col["c"])
    c.rect(4, 12, 8, 2, col["M"])
    c.rect(5, 4, 1, 8, col["n"])
    c.rect(10, 4, 1, 8, col["n"])


def _dibujo_barra(c: Lienzo, col: Dict[str, RGBA], brillo: int) -> None:
    c.rect(2, 8, 12, 2, col["p"])
    c.rect(2, 8, 12, 1, col["c"] if brillo else col["p"])
    c.rect(12, 5, 2, 4, col["p"])
    c.rect(13, 4, 1, 2, col["c"])
    c.rect(2, 10, 2, 2, col["p"])


def barra(estilo: str) -> Image:
    return _objeto(_dibujo_barra, COLORES[estilo])


def llave(estilo: str) -> Image:
    return _objeto(_dibujo_llave, COLORES[estilo])


def farol(estilo: str) -> Image:
    return _objeto(_dibujo_farol, COLORES[estilo])


# --- el tileset entero ----------------------------------------------------
#
# El orden es el que usa la leyenda del game.yaml del genero y **no se puede
# cambiar sin cambiarla**: ahi cada simbolo dice su numero de tile.
#
#    0 pared        1 zocalo       2 suelo
#    3..6 puerta    7..10 ventana  11..14 cuadro
#   15 estante     16..19 mesa    20 llave sobre la mesa
#   21 farol       22,23 trampilla
#   24 pared de piedra   25 suelo de piedra   26 escalera
#   27..30 cofre   31 palanca     32 barril    33 telarana

def _tiles(estilo: str) -> List[Image]:
    col = COLORES[estilo]
    mesa = _mesa(col)
    orden: List[Image] = [_pared(col), _zocalo(col), _suelo(col)]
    orden += _puerta(col)
    orden += _ventana(col)
    orden += _cuadro(col)
    orden.append(_estante(col))
    orden += mesa
    orden.append(_llave_en_la_mesa(col, mesa[1]))
    orden.append(_farol(col))
    orden += _trampilla(col)
    orden += [_pared_piedra(col), _suelo_piedra(col), _escalera(col)]
    orden += _cofre(col)
    orden += [_palanca(col), _barril(col), _telarana(col)]
    return orden


def tileset(estilo: str) -> Image:
    trozos = _tiles(estilo)
    hoja = Lienzo(16 * len(trozos), 16)
    for i, trozo in enumerate(trozos):
        hoja.blit(i * 16, 0, trozo)
    return hoja.image


def todos(estilo: str) -> Dict[str, Image]:
    """Los dibujos que anade este genero, por encima de los del estilo."""
    return {
        "graficos/heroe.png": cursor(estilo),
        "graficos/llave.png": llave(estilo),
        "graficos/farol.png": farol(estilo),
        "graficos/barra.png": barra(estilo),
        "graficos/tiles.png": tileset(estilo),
    }
