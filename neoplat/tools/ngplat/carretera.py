"""La textura de la carretera: la calzada en perspectiva, dibujada una vez.

Esta es la pieza que hace que un juego de conducir se pueda dibujar en las ocho
maquinas sin escribir ocho dibujantes distintos.

La idea es la de los recreativos de la epoca. Como la calzada mide **lo mismo
en todo el circuito** (ver np_via_ancho), lo que se ve en cada linea de
pantalla no cambia de un frame a otro:

  - lo ancha que es la calzada en esa linea: lo dice la perspectiva y ya esta,
  - de que color es esa linea: una de cuatro franjas que se turnan.

Lo unico que cambia entre frames es **cuanto se desliza cada linea**, que es lo
que hace la curva. Y deslizar una imagen linea a linea lo saben hacer todas:
el scroll por linea de la Mega Drive y el X68000, el copper del Amiga y el
CD32, la lista de objetos de la Jaguar.

Asi que la carretera se dibuja **una sola vez**, al compilar, como una imagen
normal de las que ya sabe tragar el kit, y en la maquina no se dibuja nada:
solo se desliza.

Y las franjas que corren hacia ti -de lo que vive la sensacion de velocidad- no
se dibujan tampoco: la textura lleva cuatro franjas con cuatro colores
distintos y lo que se mueve es **la paleta**, cuatro registros por frame. Eso
tambien es de la epoca, y es lo que hace que el efecto salga gratis en las
ocho maquinas.
"""

from __future__ import annotations

from typing import List, Tuple

from .png import Image

RGBA = Tuple[int, int, int, int]

# --- la camara, la misma que engine/include/np_types.h --------------------
#
# Estan repetidas aqui porque el compilador tiene que dibujar exactamente lo
# que el motor va a proyectar. Que no se separen no se deja a la buena fe:
# tests/test_carretera.py las lee del propio np_types.h y las compara.
SCREEN_W = 320
SCREEN_H = 224
HORIZONTE = 88
CAMARA_ALTO = 48
FOCAL = 135
CERCA = 16
TILE = 16
TRAMOS_VISTA = 160

# Lo ancha que es la textura. La calzada de cerca ocupa casi la pantalla
# entera, y ademas tiene que poder deslizarse a los lados sin que se acabe la
# hierba, asi que se hace del ancho de un plano de la Mega Drive: 512. Es
# tambien lo que cabe en las demas sin pedir nada raro.
ANCHO = 512

# Cuantas franjas se turnan. Con dos, la carretera parpadea entre dos colores y
# no se sabe si va hacia ti o al reves; con cuatro, la paleta las va corriendo
# y se ve **hacia donde** se mueve. Cuatro registros de color por frame.
FRANJAS = 4


def encoge(z: int) -> int:
    """Lo que encoge algo a distancia z, en 8.8. Igual que np_encoge."""
    if z < 1:
        z = 1
    return (FOCAL << 8) // z


def lineas(ancho_via: int) -> List[Tuple[int, int]]:
    """Por cada linea de pantalla: (medio ancho de la calzada, franja).

    `ancho_via` es el medio ancho de la calzada en pixeles del mapa. Devuelve
    una entrada por linea de las 224; las de encima del horizonte salen con
    medio ancho cero, que es como decir que ahi no hay carretera.

    Es la misma cuenta que np_carretera, con una diferencia: aqui no hay
    camara ni curva -la carretera va recta-, porque de la curva se encarga
    despues el deslizamiento linea a linea.
    """
    salida = [(0, 0)] * SCREEN_H
    sy_ant = SCREEN_H
    mx_ant = 0
    primero = True
    for i in range(TRAMOS_VISTA):
        z = i * TILE + CERCA
        k = encoge(z)
        sy = HORIZONTE + ((CAMARA_ALTO * k) >> 8)
        if sy >= SCREEN_H:
            continue
        if sy <= HORIZONTE:
            break
        mx = (ancho_via * k) >> 8
        alto = sy_ant - sy
        if alto <= 0:
            continue
        if primero:
            mx_ant = mx
            primero = False
        # la franja va por el tramo, no por la linea: asi mide lo que mide un
        # trozo de carretera y se encoge con la distancia, como todo lo demas
        franja = i % FRANJAS
        dmx = ((mx_ant - mx) << 8) // alto
        amx = mx << 8
        for y in range(sy, sy_ant):
            salida[y] = (amx >> 8, franja)
            amx += dmx
        sy_ant = sy
        mx_ant = mx
    return salida


def textura(ancho_via: int, colores, ancho_arcen: int = 8) -> Image:
    """La carretera en perspectiva, recta y centrada, lista para deslizar.

    `colores` son los cuatro tonos de cada cosa -calzada, arcen, hierba- y el
    de la raya del medio. Cada franja usa el suyo, y en la maquina lo que se
    mueve es la paleta.
    """
    filas = lineas(ancho_via)
    px: List[RGBA] = [(0, 0, 0, 0)] * (ANCHO * SCREEN_H)
    centro = ANCHO // 2
    for y, (medio, franja) in enumerate(filas):
        base = y * ANCHO
        hierba = colores["hierba"][franja]
        if medio <= 0:
            # Por encima del horizonte no hay carretera **ni hierba**: se deja
            # transparente para que se vea el cielo, que es el color de fondo
            # del nivel. Asi el cielo se cambia desde el game.yaml sin tocar la
            # imagen, y ademas no gasta ni un tile.
            continue
        asfalto = colores["asfalto"][franja]
        arcen = colores["arcen"][franja]
        raya = colores["raya"]
        # el arcen encoge con la distancia, igual que la calzada
        borde = (ancho_arcen * medio) // 64
        mitad = medio - borde
        for x in range(ANCHO):
            d = x - centro
            if d < -medio or d >= medio:
                px[base + x] = hierba
            elif d < -mitad or d >= mitad:
                px[base + x] = arcen
            elif -2 <= d < 2 and (franja & 1) and mitad > 6:
                px[base + x] = raya          # la raya del medio, discontinua
            else:
                px[base + x] = asfalto
    return Image(ANCHO, SCREEN_H, px)


# --- la otra manera: una textura lisa y las bandas con el haz -------------
#
# Hay maquinas que pueden cambiar de color **en mitad de la pantalla**: el
# copper del Amiga, del A1200 y del CD32 escribe registros de color linea a
# linea sin gastar CPU. A esas no les hace falta que las franjas vengan
# dibujadas: les sale mas barato pintar la carretera con **un color por cosa**
# -calzada, arcen, hierba, raya- y decidir en cada linea que tono toca.
#
# Y no es solo mas barato: es lo unico que cabe. Las cuatro franjas por cosa
# son doce huecos de paleta, y un plano del doble plano del Amiga OCS tiene
# siete. Asi la carretera entra en siete colores con sitio de sobra, que es
# justo lo que dice el `carretera:` del game.yaml.
#
# Los indices son fijos porque el motor los necesita para saber que registro
# escribir en cada linea (ver np_carretera_huecos).
LISO_HIERBA = 0
LISO_ARCEN = 1
LISO_ASFALTO = 2
LISO_RAYA = 3
LISO_COSAS = ("hierba", "arcen", "asfalto", "raya")


def textura_lisa(ancho_via: int, colores, ancho_arcen: int = 8) -> Image:
    """La misma carretera, pero con **un solo color por cosa**.

    `colores` es un color por nombre de LISO_COSAS. Los tonos de cada franja no
    estan aqui: los pone la maquina linea a linea. La raya del medio se dibuja
    en todas las lineas donde cabe, y es la maquina la que la borra -pintandola
    del color de la calzada- en las franjas donde no toca.
    """
    filas = lineas(ancho_via)
    px: List[RGBA] = [(0, 0, 0, 0)] * (ANCHO * SCREEN_H)
    centro = ANCHO // 2
    for y, (medio, _franja) in enumerate(filas):
        base = y * ANCHO
        if medio <= 0:
            continue                     # cielo: transparente, como en la otra
        borde = (ancho_arcen * medio) // 64
        mitad = medio - borde
        for x in range(ANCHO):
            d = x - centro
            if d < -medio or d >= medio:
                px[base + x] = colores["hierba"]
            elif d < -mitad or d >= mitad:
                px[base + x] = colores["arcen"]
            elif -2 <= d < 2 and mitad > 6:
                px[base + x] = colores["raya"]
            else:
                px[base + x] = colores["asfalto"]
    return Image(ANCHO, SCREEN_H, px)


# --- y la tercera manera: ni imagen ni bandas, solo los colores ------------
#
# Hay maquinas que no deslizan nada porque **pintan**: el Atari ST y el X68000
# rellenan la carretera franja a franja en su memoria de pantalla y la Jaguar
# la compone con su blitter. A esas la imagen no les sirve de nada: lo unico
# que necesitan de aqui son los siete colores, para que entren en la paleta del
# juego y puedan pedirlos por su numero.
#
# Asi que se les da una muestra: un cuadro de 16x16 con los siete tonos, que
# ocupa un dibujo y no dos mil. Los bordes de la calzada los sacan ellas con la
# misma cuenta que hizo esta textura, y esta escrita una sola vez en el motor
# (np_carretera_bordes).
MUESTRA_COSAS = ("hierba", "arcen", "asfalto", "raya")


def muestra(colores) -> Image:
    """Un cuadro de 16x16 con los dos tonos de cada cosa, y nada mas.

    `colores` es una lista de parejas en el orden de MUESTRA_COSAS. Van en
    columnas de dos pixeles para que ningun cuantizador de paleta los junte por
    ser pocos: cada uno ocupa 32 pixeles del cuadro.
    """
    px: List[RGBA] = [(0, 0, 0, 0)] * (TILE * TILE)
    cuantos = len(colores) * 2
    for i, pareja in enumerate(colores):
        for mitad, color in enumerate(pareja):
            columna = i * 2 + mitad
            for y in range(TILE):
                for x in range(TILE // cuantos):
                    px[y * TILE + columna * (TILE // cuantos) + x] = color + (255,)
    return Image(TILE, TILE, px)


def fase(avance: int) -> int:
    """Que franja toca ahora: cuanto ha avanzado el coche, en tramos.

    Es lo unico que cambia entre frames, y con eso la maquina rota los cuatro
    colores de cada cosa. `avance` es la fila del mapa en la que va el coche.
    """
    return avance % FRANJAS
