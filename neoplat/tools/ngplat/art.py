"""Graficos de ejemplo generados por codigo.

`ngplat nuevo` crea un proyecto que se puede jugar al instante, sin pedir al
usuario ningun PNG. Estos dibujos son deliberadamente simples: estan pensados
para sustituirse por los tuyos (mismo tamano, hasta 15 colores).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .png import Image

RGBA = Tuple[int, int, int, int]

CLEAR: RGBA = (0, 0, 0, 0)

PALETA: Dict[str, RGBA] = {
    "piel":    (248, 200, 152, 255),
    "pelo":    (72, 48, 32, 255),
    "camisa":  (216, 72, 72, 255),
    "panta":   (56, 88, 176, 255),
    "bota":    (56, 40, 32, 255),
    "linea":   (24, 16, 24, 255),
    "hierba":  (88, 184, 88, 255),
    "hierba2": (56, 136, 64, 255),
    "tierra":  (136, 88, 56, 255),
    "tierra2": (104, 64, 40, 255),
    "madera":  (176, 120, 64, 255),
    "madera2": (128, 80, 40, 255),
    "metal":   (192, 200, 216, 255),
    "metal2":  (120, 128, 152, 255),
    "oro":     (248, 208, 72, 255),
    "oro2":    (200, 152, 32, 255),
    "enemigo": (152, 88, 200, 255),
    "enemigo2": (104, 56, 152, 255),
    "ojo":     (255, 255, 255, 255),
    "meta":    (96, 216, 232, 255),
    "meta2":   (48, 152, 184, 255),
}


class Lienzo:
    """Mini utilidad de dibujo sobre una imagen RGBA."""

    def __init__(self, width: int, height: int):
        self.image = Image(width, height, [CLEAR] * (width * height))

    def px(self, x: int, y: int, color: RGBA) -> None:
        if 0 <= x < self.image.width and 0 <= y < self.image.height:
            self.image.set(x, y, color)

    def rect(self, x: int, y: int, w: int, h: int, color: RGBA) -> None:
        for dy in range(h):
            for dx in range(w):
                self.px(x + dx, y + dy, color)

    def blit(self, x: int, y: int, other: Image) -> None:
        for dy in range(other.height):
            for dx in range(other.width):
                pixel = other.get(dx, dy)
                if pixel[3]:
                    self.px(x + dx, y + dy, pixel)


def _heroe_frame(pose: int) -> Image:
    """16x16. pose: 0 quieto, 1-3 correr, 4 saltar, 5 caer."""
    c = Lienzo(16, 16)
    piel, pelo, camisa, panta, bota, linea = (
        PALETA["piel"], PALETA["pelo"], PALETA["camisa"],
        PALETA["panta"], PALETA["bota"], PALETA["linea"],
    )
    bob = 1 if pose in (2,) else 0                 # el cuerpo sube al correr
    top = 1 + bob

    c.rect(5, top, 6, 2, pelo)                     # pelo
    c.rect(5, top + 2, 6, 4, piel)                 # cara
    c.px(6, top + 3, linea)
    c.px(9, top + 3, linea)
    c.rect(6, top + 5, 4, 1, linea)                # boca

    c.rect(5, top + 6, 6, 5, camisa)               # torso
    c.rect(4, top + 6, 1, 4, camisa)
    c.rect(11, top + 6, 1, 4, camisa)

    if pose == 4:                                   # saltando: brazos arriba
        c.rect(3, top + 4, 1, 3, piel)
        c.rect(12, top + 4, 1, 3, piel)
    elif pose == 5:                                 # cayendo: brazos abiertos
        c.rect(3, top + 7, 1, 3, piel)
        c.rect(12, top + 7, 1, 3, piel)
    else:
        c.rect(4, top + 9, 1, 2, piel)
        c.rect(11, top + 9, 1, 2, piel)

    if pose in (1, 3):                              # zancada
        c.rect(4, top + 11, 3, 3, panta)
        c.rect(9, top + 11, 3, 2, panta)
        c.rect(3, top + 14, 4, 1, bota)
        c.rect(9, top + 13, 4, 1, bota)
    elif pose == 2:
        c.rect(5, top + 11, 3, 3, panta)
        c.rect(8, top + 11, 3, 3, panta)
        c.rect(4, top + 14, 4, 1, bota)
        c.rect(8, top + 14, 4, 1, bota)
    elif pose in (4, 5):
        c.rect(5, top + 11, 2, 3, panta)
        c.rect(9, top + 11, 2, 3, panta)
        c.rect(4, top + 13, 3, 1, bota)
        c.rect(9, top + 13, 3, 1, bota)
    else:
        c.rect(5, top + 11, 2, 4, panta)
        c.rect(9, top + 11, 2, 4, panta)
        c.rect(4, top + 15, 3, 1, bota)
        c.rect(9, top + 15, 3, 1, bota)
    return c.image


def heroe() -> Image:
    hoja = Lienzo(16 * 6, 16)
    for pose in range(6):
        hoja.blit(pose * 16, 0, _heroe_frame(pose))
    return hoja.image


def _enemigo_frame(fase: int) -> Image:
    """Bicho morado que se aplasta al andar."""
    c = Lienzo(16, 16)
    cuerpo, sombra, ojo, linea = (
        PALETA["enemigo"], PALETA["enemigo2"], PALETA["ojo"], PALETA["linea"],
    )
    alto = 9 if fase == 0 else 8
    base = 15 - alto
    c.rect(3, base + 1, 10, alto - 1, cuerpo)
    c.rect(2, base + 3, 12, alto - 3, cuerpo)
    c.rect(2, 14, 12, 1, sombra)
    c.rect(4, base, 8, 1, cuerpo)
    c.rect(4, base + 3, 3, 3, ojo)
    c.rect(9, base + 3, 3, 3, ojo)
    c.px(5 + fase, base + 4, linea)
    c.px(10 + fase, base + 4, linea)
    for x in range(2, 14, 3):                       # patitas
        c.rect(x, 15, 2, 1, sombra)
    return c.image


def enemigo() -> Image:
    hoja = Lienzo(32, 16)
    hoja.blit(0, 0, _enemigo_frame(0))
    hoja.blit(16, 0, _enemigo_frame(1))
    return hoja.image


def _moneda_frame(ancho: int) -> Image:
    c = Lienzo(16, 16)
    oro, oro2 = PALETA["oro"], PALETA["oro2"]
    x0 = 8 - ancho // 2
    c.rect(x0, 4, ancho, 8, oro)
    c.rect(x0, 5, ancho, 1, oro2)
    c.rect(x0, 10, ancho, 1, oro2)
    if ancho >= 6:
        c.rect(x0 + 1, 3, ancho - 2, 1, oro)
        c.rect(x0 + 1, 12, ancho - 2, 1, oro)
        c.rect(8 - 1, 6, 2, 4, oro2)
    return c.image


def moneda() -> Image:
    anchos = [8, 6, 2, 6]
    hoja = Lienzo(16 * len(anchos), 16)
    for i, ancho in enumerate(anchos):
        hoja.blit(i * 16, 0, _moneda_frame(ancho))
    return hoja.image


def _llave_frame(alto: int) -> Image:
    """La llave: anilla a la izquierda, paleton a la derecha.

    Los dos fotogramas son la misma llave subida o bajada un pixel, para que
    flote sin gastar un color mas: cuantos menos colores lleve el sprite, mas
    sitio queda en la paleta para el resto del juego.
    """
    c = Lienzo(16, 16)
    oro, oro2 = PALETA["oro"], PALETA["oro2"]
    y = 5 + alto
    c.rect(2, y, 6, 5, oro)                  # la anilla
    c.rect(4, y + 2, 2, 1, (0, 0, 0, 0))     # el agujero
    c.rect(2, y + 4, 6, 1, oro2)
    c.rect(8, y + 2, 6, 2, oro)              # el vastago
    c.rect(8, y + 3, 6, 1, oro2)
    c.rect(10, y + 4, 1, 2, oro)             # los dientes
    c.rect(12, y + 4, 1, 2, oro)
    return c.image


def llave() -> Image:
    hoja = Lienzo(16 * 2, 16)
    for i, alto in enumerate([0, 1]):
        hoja.blit(i * 16, 0, _llave_frame(alto))
    return hoja.image


def _bala_frame(fase: int) -> Image:
    """El proyectil: una bolita de energia que late, centrada en el fotograma.

    El fotograma es de 16x16 porque estas maquinas dibujan los sprites en
    bloques de ese tamano, pero la bola ocupa ocho pixeles a proposito: en el
    Atari ST cada actor lo pinta la CPU pixel a pixel, asi que un disparo
    grande se paga en frames. La caja de colision son seis.
    """
    c = Lienzo(16, 16)
    nucleo, halo = PALETA["meta"], PALETA["meta2"]
    fuera, dentro = [(4, 2), (3, 2), (3, 1)][fase]
    c.rect(8 - fuera, 8 - fuera, fuera * 2, fuera * 2, halo)
    c.rect(8 - dentro, 8 - dentro, dentro * 2, dentro * 2, nucleo)
    return c.image


def bala() -> Image:
    hoja = Lienzo(16 * 3, 16)
    for i in range(3):
        hoja.blit(i * 16, 0, _bala_frame(i))
    return hoja.image


def plataforma() -> Image:
    """La plataforma movil: un tablon de dos tiles de ancho.

    El fotograma es de 32x16 (las maquinas dibujan en bloques de 16) pero el
    tablon ocupa solo las seis filas de arriba: la caja de colision es esa, y
    asi el jugador se planta encima y no flotando.
    """
    c = Lienzo(32, 16)
    madera, madera2 = PALETA["madera"], PALETA["madera2"]
    c.rect(0, 0, 32, 5, madera)
    c.rect(0, 4, 32, 1, madera2)
    for x in range(0, 32, 8):        # las juntas entre tablas
        c.rect(x, 0, 1, 5, madera2)
    return c.image


def _tile_vacio() -> Image:
    return Lienzo(16, 16).image


def _tile_suelo() -> Image:
    c = Lienzo(16, 16)
    c.rect(0, 0, 16, 16, PALETA["tierra"])
    c.rect(0, 0, 16, 4, PALETA["hierba"])
    c.rect(0, 4, 16, 1, PALETA["hierba2"])
    for x in range(0, 16, 4):                        # motitas de tierra
        c.px(x + 1, 8, PALETA["tierra2"])
        c.px(x + 3, 12, PALETA["tierra2"])
    c.rect(0, 15, 16, 1, PALETA["tierra2"])
    return c.image


def _tile_tierra() -> Image:
    c = Lienzo(16, 16)
    c.rect(0, 0, 16, 16, PALETA["tierra"])
    for x in range(0, 16, 4):
        c.px(x + 2, 3, PALETA["tierra2"])
        c.px(x, 9, PALETA["tierra2"])
    c.rect(0, 15, 16, 1, PALETA["tierra2"])
    return c.image


def _tile_plataforma() -> Image:
    c = Lienzo(16, 16)
    c.rect(0, 0, 16, 5, PALETA["madera"])
    c.rect(0, 5, 16, 2, PALETA["madera2"])
    for x in range(2, 16, 5):
        c.px(x, 2, PALETA["madera2"])
    return c.image


def _tile_pinchos() -> Image:
    c = Lienzo(16, 16)
    metal, metal2 = PALETA["metal"], PALETA["metal2"]
    for punta in range(4):
        cx = punta * 4 + 2
        for fila in range(6):
            ancho = fila // 2 + 1
            c.rect(cx - ancho // 2, 15 - fila, max(1, ancho), 1, metal)
    c.rect(0, 14, 16, 2, metal2)
    return c.image


def _tile_meta() -> Image:
    c = Lienzo(16, 16)
    c.rect(6, 0, 2, 16, PALETA["metal2"])
    c.rect(8, 1, 7, 6, PALETA["meta"])
    c.rect(8, 4, 7, 3, PALETA["meta2"])
    c.rect(4, 14, 8, 2, PALETA["metal2"])
    return c.image


def tileset() -> Image:
    tiles = [
        _tile_vacio(), _tile_suelo(), _tile_plataforma(),
        _tile_pinchos(), _tile_meta(), _tile_tierra(),
    ]
    hoja = Lienzo(16 * len(tiles), 16)
    for i, tile in enumerate(tiles):
        hoja.blit(i * 16, 0, tile)
    return hoja.image


def _monte(c: "Lienzo", cx: int, base: int, alto: int, color: RGBA, cima: RGBA) -> None:
    """Dibuja una montana triangular con la cima mas clara."""
    for fila in range(alto):
        ancho = (fila + 1) * 2
        y = base - alto + fila
        c.rect(cx - ancho // 2, y, ancho, 1, color if fila > 2 else cima)


def cielo() -> Image:
    """Capa lejana: degradado, nubes y montanas. Se repite en horizontal."""
    ancho, alto = 256, 96
    c = Lienzo(ancho, alto)
    bandas = [
        (0, 24, (16, 24, 48, 255)),
        (24, 44, (28, 40, 80, 255)),
        (44, 60, (44, 60, 112, 255)),
        (60, 74, (64, 84, 144, 255)),
        (74, alto, (88, 112, 168, 255)),
    ]
    for desde, hasta, color in bandas:
        c.rect(0, desde, ancho, hasta - desde, color)

    nube = (176, 192, 224, 255)
    for cx in (40, 150, 220):
        c.rect(cx, 18, 22, 4, nube)
        c.rect(cx + 4, 14, 14, 4, nube)
        c.rect(cx - 4, 22, 30, 3, nube)

    monte, cima = (48, 64, 96, 255), (120, 136, 176, 255)
    for cx, altura in ((32, 30), (96, 40), (168, 26), (232, 36)):
        _monte(c, cx, alto, altura, monte, cima)
    # el borde derecho enlaza con el izquierdo al repetirse
    _monte(c, 0, alto, 22, monte, cima)
    _monte(c, ancho, alto, 22, monte, cima)
    c.rect(0, alto - 3, ancho, 3, (40, 52, 80, 255))
    return c.image


def arboles() -> Image:
    """Capa intermedia: linea de arboles con la parte de arriba transparente."""
    ancho, alto = 256, 64
    c = Lienzo(ancho, alto)
    copa, sombra, tronco = (40, 96, 56, 255), (28, 72, 44, 255), (72, 48, 32, 255)
    c.rect(0, alto - 6, ancho, 6, sombra)          # suelo de la arboleda
    for i in range(0, ancho, 32):
        altura = 26 if (i // 32) % 2 == 0 else 34
        base = alto - 6
        c.rect(i + 10, base - 2, 4, 8, tronco)     # tronco
        for fila in range(altura):
            ensancha = (fila * 12) // altura
            y = base - altura + fila
            c.rect(i + 10 - ensancha, y, 4 + ensancha * 2, 1, copa if fila % 4 else sombra)
    return c.image


def todos() -> Dict[str, Image]:
    return {
        "graficos/heroe.png": heroe(),
        "graficos/enemigo.png": enemigo(),
        "graficos/moneda.png": moneda(),
        "graficos/bala.png": bala(),
        "graficos/llave.png": llave(),
        "graficos/plataforma.png": plataforma(),
        "graficos/tiles.png": tileset(),
        "graficos/cielo.png": cielo(),
        "graficos/arboles.png": arboles(),
    }


def colores_usados(image: Image) -> List[RGBA]:
    return image.colors()
