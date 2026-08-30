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
    """16x16. 0 quieto, 1-3 correr, 4 saltar, 5 caer, 6 y 7 pegar, 8 subir,
    9 golpeado, 10 agachado.

    Las cuatro ultimas son las que faltaban: sin ellas, pegar con el latigo,
    subir una escalera y recibir un golpe se dibujaban **con la pose de estar
    quieto**, porque el generador rellena las ranuras que faltan con el
    fotograma 0. El latigo se veia funcionar en los numeros y no en pantalla.

    La 6 es el brazo echado atras (los frames de `preparacion:`, cuando el
    golpe todavia no hace dano) y la 7 el brazo estirado hacia delante: el
    dibujo del latigo arranca justo donde acaba esa mano.
    """
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
    elif pose == 6:                                 # tomando impulso: atras
        c.rect(1, top + 6, 4, 2, piel)
        c.rect(11, top + 9, 1, 2, piel)
    elif pose == 7:                                 # pegando: brazo estirado
        c.rect(11, top + 7, 3, 2, piel)
        c.rect(4, top + 9, 1, 2, piel)
    elif pose == 9:                                 # golpeado: brazos en cruz
        c.rect(2, top + 5, 2, 2, piel)
        c.rect(12, top + 5, 2, 2, piel)
    else:
        c.rect(4, top + 9, 1, 2, piel)
        c.rect(11, top + 9, 1, 2, piel)

    if pose in (6, 7):                              # plantado para pegar
        c.rect(4, top + 11, 3, 4, panta)
        c.rect(9, top + 11, 3, 4, panta)
        c.rect(3, top + 15, 4, 1, bota)
        c.rect(9, top + 15, 4, 1, bota)
    elif pose == 9:                                 # golpeado: piernas sueltas
        c.rect(4, top + 11, 2, 3, panta)
        c.rect(10, top + 11, 2, 3, panta)
        c.rect(3, top + 14, 3, 1, bota)
        c.rect(10, top + 14, 3, 1, bota)
    elif pose in (1, 3):                            # zancada
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


def _heroe_de_espaldas() -> Image:
    """La pose de subir la escalera: se ve la nuca, no la cara."""
    c = Lienzo(16, 16)
    piel, pelo, camisa, panta, bota = (
        PALETA["piel"], PALETA["pelo"], PALETA["camisa"],
        PALETA["panta"], PALETA["bota"],
    )
    top = 1
    c.rect(5, top, 6, 6, pelo)                     # la nuca, todo pelo
    c.rect(5, top + 6, 6, 5, camisa)               # espalda
    c.rect(4, top + 4, 1, 4, piel)                 # brazos agarrados arriba
    c.rect(11, top + 4, 1, 4, piel)
    c.rect(4, top + 6, 1, 4, camisa)               # mangas
    c.rect(11, top + 6, 1, 4, camisa)
    c.rect(6, top + 11, 2, 4, panta)               # piernas juntas
    c.rect(8, top + 11, 2, 4, panta)
    c.rect(5, top + 15, 3, 1, bota)
    c.rect(8, top + 15, 3, 1, bota)
    return c.image


def _heroe_agachado() -> Image:
    """Agachado: el cuerpo baja tres pixeles -lo mismo que baja el techo de su
    caja- y el brazo se queda a la altura de la rodilla, que es por donde sale
    el latigo cuando pegas asi."""
    c = Lienzo(16, 16)
    piel, pelo, camisa, panta, bota, linea = (
        PALETA["piel"], PALETA["pelo"], PALETA["camisa"],
        PALETA["panta"], PALETA["bota"], PALETA["linea"],
    )
    top = 4
    c.rect(5, top, 6, 2, pelo)                     # cabeza, tres filas mas abajo
    c.rect(5, top + 2, 6, 3, piel)
    c.px(6, top + 3, linea)
    c.px(9, top + 3, linea)

    c.rect(4, top + 5, 8, 4, camisa)               # tronco encogido
    # el brazo, en las filas 11 y 12 del cuadro: es justo donde el motor pone
    # el latigo cuando se pega agachado (la caja baja tres pixeles)
    c.rect(11, top + 7, 3, 2, piel)
    c.rect(3, top + 6, 1, 2, piel)                 # y el otro, apoyado

    c.rect(4, top + 9, 3, 2, panta)                # piernas dobladas
    c.rect(8, top + 9, 4, 2, panta)
    c.rect(3, top + 11, 4, 1, bota)
    c.rect(8, top + 11, 4, 1, bota)
    return c.image


HEROE_POSES = 11


def heroe() -> Image:
    hoja = Lienzo(16 * HEROE_POSES, 16)
    for pose in range(HEROE_POSES):
        if pose == 8:
            dibujo = _heroe_de_espaldas()
        elif pose == 10:
            dibujo = _heroe_agachado()
        else:
            dibujo = _heroe_frame(pose)
        hoja.blit(pose * 16, 0, dibujo)
    return hoja.image


# --- el latigo ------------------------------------------------------------
#
# Un fotograma por nivel del arma: el de serie, y los dos que salen al coger
# las mejoras. Cada uno mide exactamente lo que alcanza el golpe (24, 36 y 48
# pixeles), asi que lo que se ve es lo que pega. El motor lo coloca pegado al
# costado del jugador y lo espeja al mirar a la izquierda, asi que el latigo
# sale siempre del mango: por eso se dibuja arrancando en la columna 0.

LATIGO_ANCHO = 48
LATIGO_LARGOS = (24, 36, 48)


def _latigo_frame(largo: int) -> Image:
    c = Lienzo(LATIGO_ANCHO, 16)
    cuero, brillo, punta = PALETA["madera2"], PALETA["madera"], PALETA["oro"]
    # a la altura de la mano: el motor pone la fila 0 del latigo en la fila 1
    # del jugador (su caja empieza ahi), y la mano del fotograma 7 esta en las
    # filas 8 y 9, asi que el mango va en las 7 y 8
    grueso = largo * 2 // 3
    c.rect(0, 7, grueso, 2, cuero)                 # el tramo gordo, con brillo
    c.rect(0, 7, grueso, 1, brillo)
    c.rect(grueso, 8, largo - grueso - 3, 1, cuero)   # se va afinando
    c.rect(largo - 3, 9, 3, 1, cuero)              # y la punta cae
    c.px(largo - 1, 10, punta)                     # el chasquido
    return c.image


def latigo() -> Image:
    hoja = Lienzo(LATIGO_ANCHO * len(LATIGO_LARGOS), 16)
    for i, largo in enumerate(LATIGO_LARGOS):
        hoja.blit(i * LATIGO_ANCHO, 0, _latigo_frame(largo))
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


def _candelabro_frame(llama: int) -> Image:
    """Un candelabro: pie de metal y una llama que titila.

    Es lo que hay que romper para que suelte cosas, asi que se dibuja alto y
    estrecho: se ve de lejos y no se confunde con un enemigo.
    """
    c = Lienzo(16, 16)
    metal, metal2 = PALETA["metal"], PALETA["metal2"]
    fuego, fuego2 = PALETA["oro"], PALETA["camisa"]
    c.rect(6, 9, 4, 5, metal)            # el pie
    c.rect(6, 13, 4, 1, metal2)
    c.rect(5, 14, 6, 2, metal2)          # la base
    c.rect(7, 6, 2, 3, fuego2)           # la llama
    c.rect(7, 4 - llama, 2, 3, fuego)
    c.px(8, 3 - llama, fuego)
    return c.image


def candelabro() -> Image:
    hoja = Lienzo(16 * 2, 16)
    for i, llama in enumerate([0, 1]):
        hoja.blit(i * 16, 0, _candelabro_frame(llama))
    return hoja.image


def _corazon_frame(ancho: int) -> Image:
    """La municion del arma secundaria: un corazon que late."""
    c = Lienzo(16, 16)
    rojo, rojo2 = PALETA["camisa"], PALETA["enemigo2"]
    x0 = 8 - ancho // 2
    c.rect(x0, 5, ancho, 4, rojo)
    c.rect(x0 + 1, 9, ancho - 2, 2, rojo)
    c.rect(x0 + 2, 11, ancho - 4, 1, rojo)
    c.rect(x0, 4, 2, 2, rojo)
    c.rect(x0 + ancho - 2, 4, 2, 2, rojo)
    c.rect(x0 + 1, 6, 1, 2, rojo2)
    return c.image


def corazon() -> Image:
    hoja = Lienzo(16 * 2, 16)
    for i, ancho in enumerate([8, 6]):
        hoja.blit(i * 16, 0, _corazon_frame(ancho))
    return hoja.image


def _mejora_frame(brillo: bool) -> Image:
    """La mejora del arma: una bola de pinchos que destella.

    Se dibuja con los dos tonos del oro (los de la moneda) porque tiene que
    leerse como algo que se recoge y no como un enemigo, que en esta paleta van
    todos en morado.
    """
    c = Lienzo(16, 16)
    oro, oro2 = PALETA["oro"], PALETA["oro2"]
    metal = PALETA["metal"]
    c.rect(6, 6, 4, 4, oro)              # la bola
    c.rect(5, 7, 6, 2, oro)
    c.rect(7, 5, 2, 6, oro)
    c.rect(6, 8, 2, 2, oro2)             # la sombra de abajo
    for x, y in ((3, 7), (12, 7), (7, 3), (7, 12)):
        c.px(x, y, oro2)                 # los pinchos
        c.px(x, y + 1, oro2)
    if brillo:
        c.px(6, 6, metal)
        c.px(9, 9, metal)
    return c.image


def mejora() -> Image:
    hoja = Lienzo(16 * 2, 16)
    for i, brillo in enumerate((False, True)):
        hoja.blit(i * 16, 0, _mejora_frame(brillo))
    return hoja.image


def cuchillo() -> Image:
    """Lo que tira el arma secundaria: una hoja con su mango."""
    c = Lienzo(16, 16)
    metal, metal2 = PALETA["metal"], PALETA["metal2"]
    madera = PALETA["madera2"]
    c.rect(2, 7, 4, 2, madera)           # el mango
    c.rect(6, 7, 8, 2, metal)
    c.rect(6, 8, 8, 1, metal2)
    c.px(14, 7, metal)
    return c.image


def hacha() -> Image:
    """La segunda arma secundaria: gira al volar y cae en arco.

    Se dibuja con los mismos colores que el cuchillo -metal, metal2 y madera-
    a proposito: cada juego de colores distinto se lleva una paleta, y en el
    X68000 solo hay dieciseis para todo.
    """
    metal, metal2 = PALETA["metal"], PALETA["metal2"]
    madera = PALETA["madera2"]
    hoja = Lienzo(16 * 4, 16)
    for giro in range(4):
        c = Lienzo(16, 16)
        if giro % 2 == 0:                      # de canto: el mango horizontal
            arriba = giro == 0
            y = 7
            c.rect(3, y, 8, 2, madera)         # mango
            c.rect(10, y - 3 if arriba else y - 1, 4, 5, metal)   # cabeza
            c.rect(10, y - 3 if arriba else y + 3, 4, 1, metal2)
        else:                                  # de pie: el mango vertical
            izquierda = giro == 1
            x = 7
            c.rect(x, 3, 2, 8, madera)
            c.rect(x - 3 if izquierda else x - 1, 10, 5, 4, metal)
            c.rect(x - 3 if izquierda else x + 3, 10, 1, 4, metal2)
        hoja.blit(giro * 16, 0, c.image)
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


def _tile_escalera(derecha: bool) -> Image:
    """Un tramo de escalera en diagonal, con sus dos largueros y su peldano.

    El dibujo va de esquina a esquina para que dos casillas seguidas encajen y
    la escalera se lea como una linea continua.
    """
    c = Lienzo(16, 16)
    madera, madera2 = PALETA["madera"], PALETA["madera2"]
    for i in range(16):
        x = i if derecha else 15 - i
        y = 15 - i
        c.px(x, y, madera2)
        if x + 1 < 16:
            c.px(x + 1, y, madera)
        if y - 1 >= 0:
            c.px(x, y - 1, madera)
    # el peldano de en medio, cruzado
    medio = 8
    for d in range(-3, 4):
        x = (medio + d) if derecha else (medio - d)
        y = 15 - medio + d
        if 0 <= x < 16 and 0 <= y < 16:
            c.px(x, y, madera)
    return c.image


def _tile_control() -> Image:
    """Una antorcha en la pared: el punto de control.

    Tiene que leerse de lejos y no parecerse a nada que haga dano, asi que va
    encendida y en la mitad de arriba de la casilla: la de abajo se queda vacia
    para que el jugador vea que se pasa por delante.
    """
    c = Lienzo(16, 16)
    madera, madera2 = PALETA["madera"], PALETA["madera2"]
    metal, oro, oro2 = PALETA["metal"], PALETA["oro"], PALETA["oro2"]
    c.rect(7, 7, 2, 9, madera2)          # el palo
    c.rect(6, 6, 4, 2, madera)           # el agarre
    c.rect(5, 5, 6, 2, metal)            # el pebetero
    c.rect(6, 2, 4, 3, oro2)             # la llama, por dentro
    c.rect(7, 0, 2, 3, oro)
    c.px(5, 3, oro2)
    c.px(10, 3, oro2)
    return c.image


def tileset() -> Image:
    tiles = [
        _tile_vacio(), _tile_suelo(), _tile_plataforma(),
        _tile_pinchos(), _tile_meta(), _tile_tierra(),
        _tile_escalera(True), _tile_escalera(False),
        _tile_control(),
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
        "graficos/candelabro.png": candelabro(),
        "graficos/corazon.png": corazon(),
        "graficos/cuchillo.png": cuchillo(),
        "graficos/hacha.png": hacha(),
        "graficos/latigo.png": latigo(),
        "graficos/mejora.png": mejora(),
        "graficos/tiles.png": tileset(),
        "graficos/cielo.png": cielo(),
        "graficos/arboles.png": arboles(),
    }


def colores_usados(image: Image) -> List[RGBA]:
    return image.colors()
