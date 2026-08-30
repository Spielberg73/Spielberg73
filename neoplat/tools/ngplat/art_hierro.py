"""Graficos de ejemplo dibujados con seis colores (estilo 'hierro').

Los de `art.py` usan la paleta que les hace falta y quedan bien en las cuatro
maquinas. Estos estan dibujados **a proposito** para el modo de doble plano del
Amiga (`amiga: 8colores`), donde el plano de delante solo tiene siete colores y
uno se lo queda el marcador: seis para todo el juego.

Con tan pocos colores no vale ponerlos por encima de un dibujo cualquiera; hay
que dibujar pensando en ellos. Las reglas que sigue esta paleta son las de toda
la vida en las maquinas de 8 bits:

  - un solo color oscuro (`linea`) hace de contorno **y** de sombra, en todo;
  - un solo color claro (`claro`) hace de luz, de ojos y de brillo, en todo;
  - la roca se lleva dos tonos (`roca` y `roca2`), que es lo que da volumen al
    escenario, y los actores no los usan para que no se camuflen;
  - al heroe le queda `rojo` y a lo que se recoge `oro`, asi que lo que importa
    en la pantalla son los dos unicos colores que no salen en el decorado.

La capa de fondo va aparte: en doble plano tiene su propia paleta de siete
colores (los registros 9 a 15), asi que puede permitirse un degradado.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .art import Lienzo
from .png import Image

RGBA = Tuple[int, int, int, int]

# --- los seis colores del juego ------------------------------------------
LINEA: RGBA = (24, 20, 28, 255)
CLARO: RGBA = (232, 224, 200, 255)
ROJO: RGBA = (200, 72, 64, 255)
ORO: RGBA = (248, 200, 72, 255)
ROCA: RGBA = (112, 104, 128, 255)
ROCA2: RGBA = (64, 60, 84, 255)

PALETA: Dict[str, RGBA] = {
    "linea": LINEA, "claro": CLARO, "rojo": ROJO,
    "oro": ORO, "roca": ROCA, "roca2": ROCA2,
}


# --- el heroe -------------------------------------------------------------

def _heroe_frame(pose: int) -> Image:
    """16x16. 0 quieto, 1-3 correr, 4 saltar, 5 caer, 6 y 7 pegar, 8 subir,
    9 golpeado. Las cuatro ultimas, igual que en el estilo de bosque: sin
    ellas el latigo, la escalera y el golpe recibido se dibujaban con la pose
    de estar quieto."""
    c = Lienzo(16, 16)
    sube = 1 if pose == 2 else 0                   # el cuerpo bota al correr
    top = 2 - sube

    c.rect(5, top, 6, 1, LINEA)                    # capucha
    c.rect(4, top + 1, 8, 3, ROJO)
    c.rect(6, top + 2, 4, 2, CLARO)                # cara
    c.px(6, top + 2, LINEA)                        # ojos
    c.px(9, top + 2, LINEA)

    c.rect(4, top + 4, 8, 5, ROJO)                 # cuerpo
    c.rect(4, top + 4, 1, 5, LINEA)                # sombra a un lado
    c.rect(6, top + 5, 4, 2, CLARO)                # peto claro

    if pose in (1, 3):                             # brazos al correr
        c.rect(2, top + 5, 2, 2, CLARO)
        c.rect(12, top + 5, 2, 2, CLARO)
    elif pose == 6:                                # tomando impulso: atras
        c.rect(1, top + 4, 4, 2, CLARO)
        c.rect(12, top + 6, 1, 2, CLARO)
    elif pose == 7:                                # pegando: brazo estirado
        c.rect(12, top + 5, 2, 2, CLARO)
        c.rect(3, top + 6, 1, 2, CLARO)
    elif pose == 9:                                # golpeado: brazos en cruz
        c.rect(1, top + 3, 3, 2, CLARO)
        c.rect(12, top + 3, 3, 2, CLARO)
    elif pose in (4, 5):                           # brazos arriba al saltar
        c.rect(2, top + 3, 2, 3, CLARO)
        c.rect(12, top + 3, 2, 3, CLARO)
    else:
        c.rect(3, top + 5, 1, 3, CLARO)
        c.rect(12, top + 5, 1, 3, CLARO)

    piernas = top + 9
    if pose == 1:                                  # una adelante, otra atras
        c.rect(3, piernas, 4, 3, LINEA)
        c.rect(9, piernas, 4, 3, LINEA)
    elif pose == 3:
        c.rect(4, piernas, 4, 3, LINEA)
        c.rect(8, piernas, 4, 3, LINEA)
    elif pose == 4:                                # recogidas al saltar
        c.rect(4, piernas - 1, 8, 3, LINEA)
    elif pose == 5:                                # estiradas al caer
        c.rect(4, piernas, 3, 4, LINEA)
        c.rect(9, piernas, 3, 4, LINEA)
    elif pose in (6, 7):                           # plantado para pegar
        c.rect(3, piernas, 4, 4, LINEA)
        c.rect(9, piernas, 4, 4, LINEA)
    elif pose == 9:                                # golpeado: piernas sueltas
        c.rect(3, piernas, 3, 3, LINEA)
        c.rect(10, piernas, 3, 3, LINEA)
    else:
        c.rect(5, piernas, 2, 4, LINEA)
        c.rect(9, piernas, 2, 4, LINEA)
    return c.image


def _heroe_de_espaldas() -> Image:
    """Subiendo la escalera: se le ve la espalda, no la cara."""
    c = Lienzo(16, 16)
    top = 2
    c.rect(5, top, 6, 1, LINEA)                    # capucha
    c.rect(4, top + 1, 8, 3, ROJO)                 # cogote, sin cara
    c.rect(4, top + 4, 8, 5, ROJO)                 # espalda
    c.rect(6, top + 5, 4, 2, LINEA)                # la correa cruzada
    c.rect(2, top + 2, 2, 4, CLARO)                # brazos agarrados arriba
    c.rect(12, top + 2, 2, 4, CLARO)
    c.rect(5, top + 9, 3, 4, LINEA)                # piernas juntas
    c.rect(8, top + 9, 3, 4, LINEA)
    return c.image


def _heroe_agachado() -> Image:
    """Agachado: el cuerpo baja tres pixeles, lo mismo que baja el techo de su
    caja, y el brazo se queda a la altura de la rodilla."""
    c = Lienzo(16, 16)
    top = 5
    c.rect(5, top, 6, 1, LINEA)                    # capucha
    c.rect(4, top + 1, 8, 3, ROJO)
    c.rect(6, top + 2, 4, 1, CLARO)                # cara
    c.px(6, top + 2, LINEA)
    c.px(9, top + 2, LINEA)

    c.rect(4, top + 4, 8, 4, ROJO)                 # tronco encogido
    c.rect(4, top + 4, 1, 4, LINEA)
    c.rect(6, top + 5, 4, 1, CLARO)
    c.rect(12, top + 5, 2, 2, CLARO)               # brazo hacia delante
    c.rect(3, top + 5, 1, 2, CLARO)

    c.rect(3, top + 8, 4, 2, LINEA)                # piernas dobladas
    c.rect(8, top + 8, 4, 2, LINEA)
    return c.image


HEROE_POSES = 11


def heroe() -> Image:
    hoja = Lienzo(16 * HEROE_POSES, 16)
    for i in range(HEROE_POSES):
        if i == 8:
            dibujo = _heroe_de_espaldas()
        elif i == 10:
            dibujo = _heroe_agachado()
        else:
            dibujo = _heroe_frame(i)
        hoja.blit(i * 16, 0, dibujo)
    return hoja.image


# --- el latigo, un fotograma por nivel del arma --------------------------

LATIGO_ANCHO = 48
LATIGO_LARGOS = (24, 36, 48)


def _latigo_frame(largo: int) -> Image:
    """Mide lo que alcanza el golpe: 24, 36 o 48 pixeles. Con seis colores el
    cuero es la roca clara y el chasquido, el oro."""
    c = Lienzo(LATIGO_ANCHO, 16)
    grueso = largo * 2 // 3
    c.rect(0, 7, grueso, 2, ROCA2)
    c.rect(0, 7, grueso, 1, ROCA)
    c.rect(grueso, 8, largo - grueso - 3, 1, ROCA2)
    c.rect(largo - 3, 9, 3, 1, ROCA2)
    c.px(largo - 1, 10, ORO)
    return c.image


def latigo() -> Image:
    hoja = Lienzo(LATIGO_ANCHO * len(LATIGO_LARGOS), 16)
    for i, largo in enumerate(LATIGO_LARGOS):
        hoja.blit(i * LATIGO_ANCHO, 0, _latigo_frame(largo))
    return hoja.image


# --- los bichos -----------------------------------------------------------

def _enemigo_frame(fase: int) -> Image:
    """Un bicho palido: en la cueva lo que se ve es lo que brilla."""
    c = Lienzo(16, 16)
    base = 15 - fase                               # sube y baja un pixel
    c.rect(3, base - 8, 10, 7, CLARO)              # caparazon
    c.rect(3, base - 8, 10, 1, LINEA)
    c.rect(2, base - 6, 1, 4, LINEA)
    c.rect(13, base - 6, 1, 4, LINEA)
    c.px(5, base - 6, LINEA)                       # ojos
    c.px(10, base - 6, LINEA)
    c.rect(5, base - 4, 6, 1, ROJO)                # boca
    patas = 2 if fase else 0
    c.rect(3 + patas, base - 1, 2, 2, LINEA)
    c.rect(11 - patas, base - 1, 2, 2, LINEA)
    return c.image


def enemigo() -> Image:
    hoja = Lienzo(32, 16)
    for i in range(2):
        hoja.blit(i * 16, 0, _enemigo_frame(i))
    return hoja.image


# --- lo que se recoge -----------------------------------------------------

def _gema_frame(ancho: int) -> Image:
    """Una gema girando: cuatro anchos del mismo rombo."""
    c = Lienzo(16, 16)
    for fila in range(10):
        estrecha = abs(4 - fila) if fila <= 4 else abs(fila - 5)
        w = max(1, ancho - estrecha)
        c.rect(8 - w // 2, 3 + fila, w, 1, ORO)
    if ancho >= 6:                                 # el brillo solo cabe de lado
        c.rect(7, 5, 2, 3, CLARO)
    return c.image


def gema() -> Image:
    hoja = Lienzo(64, 16)
    for i, ancho in enumerate((10, 6, 2, 6)):
        hoja.blit(i * 16, 0, _gema_frame(ancho))
    return hoja.image


# --- el escenario ---------------------------------------------------------

def _brasero_frame(llama: int) -> Image:
    """El rompible del estilo hierro: un brasero de metal con su llama."""
    c = Lienzo(16, 16)
    c.rect(6, 9, 4, 5, ROCA)             # el pie
    c.rect(6, 13, 4, 1, LINEA)
    c.rect(5, 14, 6, 2, ROCA2)           # la base
    c.rect(7, 6, 2, 3, ROJO)             # la llama
    c.rect(7, 4 - llama, 2, 3, ORO)
    c.px(8, 3 - llama, ORO)
    return c.image


def brasero() -> Image:
    hoja = Lienzo(16 * 2, 16)
    for i, llama in enumerate([0, 1]):
        hoja.blit(i * 16, 0, _brasero_frame(llama))
    return hoja.image


def _chispa_frame(ancho: int) -> Image:
    """La municion: una chispa que late."""
    c = Lienzo(16, 16)
    x0 = 8 - ancho // 2
    c.rect(x0, 6, ancho, ancho, ORO)
    c.rect(x0 + 1, 7, ancho - 2, ancho - 2, CLARO)
    return c.image


def chispa() -> Image:
    hoja = Lienzo(16 * 2, 16)
    for i, ancho in enumerate([8, 6]):
        hoja.blit(i * 16, 0, _chispa_frame(ancho))
    return hoja.image


def plataforma() -> Image:
    """La plataforma movil: una viga suelta de dos tiles de ancho.

    El fotograma es de 32x16 porque las maquinas dibujan en bloques de 16, pero
    la viga ocupa solo las seis filas de arriba: la caja de colision es esa.
    """
    c = Lienzo(32, 16)
    c.rect(0, 0, 32, 5, ROCA)
    c.rect(0, 0, 32, 1, CLARO)
    c.rect(0, 4, 32, 1, LINEA)
    for x in (3, 11, 20, 28):        # los remaches
        c.px(x, 2, LINEA)
    return c.image


def _tile_vacio() -> Image:
    return Lienzo(16, 16).image


def _tile_roca() -> Image:
    """Piedra con la cara de arriba iluminada."""
    c = Lienzo(16, 16)
    c.rect(0, 0, 16, 16, ROCA2)
    c.rect(0, 0, 16, 3, ROCA)
    c.rect(0, 0, 16, 1, CLARO)                     # la cara por la que se anda
    for x, y in ((2, 6), (9, 5), (5, 11), (12, 10)):
        c.rect(x, y, 3, 2, ROCA)
    c.rect(0, 15, 16, 1, LINEA)
    return c.image


def _tile_fondo() -> Image:
    """La misma piedra, sin la cara iluminada: para el relleno."""
    c = Lienzo(16, 16)
    c.rect(0, 0, 16, 16, ROCA2)
    for x, y in ((3, 3), (10, 7), (6, 12)):
        c.rect(x, y, 2, 2, LINEA)
    return c.image


def _tile_viga() -> Image:
    """Plataforma: una viga de hierro con remaches."""
    c = Lienzo(16, 16)
    c.rect(0, 2, 16, 5, ROCA)
    c.rect(0, 2, 16, 1, CLARO)
    c.rect(0, 6, 16, 1, LINEA)
    for x in (2, 8, 13):
        c.px(x, 4, LINEA)
    return c.image


def _tile_pinchos() -> Image:
    c = Lienzo(16, 16)
    for i in range(4):
        cx = i * 4 + 2
        for fila in range(9):
            w = 1 + fila // 3
            c.rect(cx - w // 2, 7 + fila, max(1, w), 1, CLARO if fila < 5 else LINEA)
    c.rect(0, 14, 16, 2, ROCA2)
    return c.image


def _tile_puerta() -> Image:
    """Meta: un arco de oro."""
    c = Lienzo(16, 16)
    c.rect(1, 2, 14, 14, ORO)
    c.rect(3, 5, 10, 11, LINEA)
    c.rect(5, 8, 6, 8, ORO)
    c.rect(6, 9, 4, 7, CLARO)
    return c.image


def _bala_frame(fase: int) -> Image:
    """El proyectil del estilo hierro: una chispa de energia que late."""
    c = Lienzo(16, 16)
    fuera, dentro = [(4, 2), (3, 2), (3, 1)][fase]
    c.rect(8 - fuera, 8 - fuera, fuera * 2, fuera * 2, ORO)
    c.rect(8 - dentro, 8 - dentro, dentro * 2, dentro * 2, CLARO)
    return c.image


def bala() -> Image:
    hoja = Lienzo(16 * 3, 16)
    for i in range(3):
        hoja.blit(i * 16, 0, _bala_frame(i))
    return hoja.image


def cuchillo() -> Image:
    """Lo que tira el arma secundaria: una pieza de hierro afilada."""
    c = Lienzo(16, 16)
    c.rect(2, 7, 4, 2, ROCA2)
    c.rect(6, 7, 8, 2, ROCA)
    c.rect(6, 8, 8, 1, CLARO)
    return c.image


def _tile_escalera(derecha: bool) -> Image:
    """Escalera de hierro en diagonal: dos largueros y un peldano."""
    c = Lienzo(16, 16)
    for i in range(16):
        x = i if derecha else 15 - i
        y = 15 - i
        c.px(x, y, ROCA2)
        if x + 1 < 16:
            c.px(x + 1, y, ROCA)
        if y - 1 >= 0:
            c.px(x, y - 1, ROCA)
    for d in range(-3, 4):
        x = (8 + d) if derecha else (8 - d)
        y = 7 + d
        if 0 <= x < 16 and 0 <= y < 16:
            c.px(x, y, CLARO)
    return c.image


def _tile_control() -> Image:
    """La antorcha del punto de control, con los seis colores de este estilo.

    El palo va en `roca2` (es parte del escenario) y la llama en `oro`, que es
    el color de lo que se recoge: asi se lee como algo bueno y no como algo que
    hace dano, que aqui va todo en `rojo`.
    """
    c = Lienzo(16, 16)
    c.rect(7, 7, 2, 9, ROCA2)            # el palo
    c.rect(6, 6, 4, 2, ROCA)             # el agarre
    c.rect(5, 5, 6, 2, LINEA)            # el pebetero
    c.rect(6, 2, 4, 3, ORO)              # la llama
    c.rect(7, 0, 2, 3, CLARO)
    c.px(5, 3, ORO)
    c.px(10, 3, ORO)
    return c.image


def tileset() -> Image:
    tiles = [_tile_vacio(), _tile_roca(), _tile_viga(),
             _tile_pinchos(), _tile_puerta(), _tile_fondo(),
             _tile_escalera(True), _tile_escalera(False),
             _tile_control()]
    hoja = Lienzo(16 * len(tiles), 16)
    for i, tile in enumerate(tiles):
        hoja.blit(i * 16, 0, tile)
    return hoja.image


# --- la capa de fondo (siete colores propios) -----------------------------

# Los siete colores de la capa de fondo. Van todos oscuros a proposito: el
# plano de atras tiene que quedarse atras, y como lleva paleta propia se puede
# hundir sin tocar los colores del juego.
FONDO: List[RGBA] = [
    (16, 14, 24, 255),      # el fondo de la cueva
    (26, 24, 38, 255),
    (38, 34, 56, 255),
    (52, 48, 74, 255),
    (22, 42, 58, 255),      # el agua
    (34, 62, 84, 255),
    (72, 110, 136, 255),    # su brillo
]


def cueva() -> Image:
    """Capa lejana: una sala con columnas, estalactitas y agua abajo.

    Mide 256 pixeles de ancho porque asi se repite dentro del hueco que tiene
    el plano de atras para correr (384 px); una capa mas ancha se pararia en el
    borde en vez de volver al principio.
    """
    ancho, alto = 256, 224
    c = Lienzo(ancho, alto)
    hondo, medio, cerca, borde, agua, agua2, brillo = FONDO

    c.rect(0, 0, ancho, alto, hondo)
    c.rect(0, 150, ancho, alto - 150, medio)       # el suelo de la sala

    # columnas: van por parejas para que al repetirse no se note el corte
    for cx in (24, 96, 168, 240):
        c.rect(cx - 10, 0, 20, 160, medio)
        c.rect(cx - 10, 0, 3, 160, cerca)
        c.rect(cx + 7, 0, 3, 160, borde)
        for y in range(24, 156, 26):               # anillos de la columna
            c.rect(cx - 13, y, 26, 3, cerca)

    # estalactitas colgando del techo
    for i, (sx, largo) in enumerate(((56, 40), (128, 26), (200, 34), (8, 20))):
        for fila in range(largo):
            w = max(1, 7 - (fila * 7) // largo)
            c.rect(sx - w // 2, fila, w, 1, cerca if i % 2 else borde)

    # el agua del fondo, con dos olas
    c.rect(0, 186, ancho, alto - 186, agua)
    c.rect(0, 186, ancho, 3, agua2)
    for x in range(0, ancho, 16):
        c.rect(x + (4 if (x // 16) % 2 else 0), 192, 8, 2, agua2)
        c.rect(x + (2 if (x // 16) % 2 else 6), 204, 6, 1, brillo)
    c.rect(0, 216, ancho, 8, agua2)
    return c.image


def _mejora_frame(brillo: bool) -> Image:
    """La mejora del arma en los seis colores de este estilo: `oro` porque es
    algo que se recoge, y `claro` solo para el destello."""
    c = Lienzo(16, 16)
    c.rect(6, 6, 4, 4, ORO)
    c.rect(5, 7, 6, 2, ORO)
    c.rect(7, 5, 2, 6, ORO)
    c.rect(6, 8, 2, 2, LINEA)
    for x, y in ((3, 7), (12, 7), (7, 3), (7, 12)):
        c.px(x, y, ORO)
        c.px(x, y + 1, ORO)
    if brillo:
        c.px(6, 6, CLARO)
        c.px(9, 9, CLARO)
    return c.image


def mejora() -> Image:
    hoja = Lienzo(16 * 2, 16)
    for i, brillo in enumerate((False, True)):
        hoja.blit(i * 16, 0, _mejora_frame(brillo))
    return hoja.image


def todos() -> Dict[str, Image]:
    return {
        "graficos/heroe.png": heroe(),
        "graficos/enemigo.png": enemigo(),
        "graficos/gema.png": gema(),
        "graficos/plataforma.png": plataforma(),
        "graficos/candelabro.png": brasero(),
        "graficos/corazon.png": chispa(),
        "graficos/bala.png": bala(),
        "graficos/cuchillo.png": cuchillo(),
        "graficos/latigo.png": latigo(),
        "graficos/mejora.png": mejora(),
        "graficos/tiles.png": tileset(),
        "graficos/cueva.png": cueva(),
    }
