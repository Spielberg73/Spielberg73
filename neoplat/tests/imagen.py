"""Lo que se mira en una captura de pantalla.

Cuatro funciones que usan por igual las pruebas de emulador (Mega Drive,
Amiga) y el banco de pruebas de Neo Geo. Un "frame" es siempre la terna
(ancho, alto, pixeles) con los pixeles como (r, g, b).
"""

from __future__ import annotations

import os
import sys


def colores(frame):
    """Cuantas veces sale cada color en el frame."""
    cuenta = {}
    for pixel in frame[2]:
        cuenta[pixel] = cuenta.get(pixel, 0) + 1
    return cuenta


def distintos(a, b):
    """Que parte de la pantalla ha cambiado entre dos frames (0 a 1)."""
    return sum(1 for x, y in zip(a[2], b[2]) if x != y) / float(len(a[2]))


def franja(frame, alto):
    """Los primeros `alto` pixeles de arriba (donde suele ir el marcador)."""
    return frame[2][:frame[0] * alto]


def filas_escritas(frame, alto):
    """Cuantas de las primeras `alto` filas llevan algo dibujado.

    Una fila con un solo color esta vacia; una con dos o mas tiene letras. Es
    lo que dice si el marcador se esta pintando, y no depende de donde caiga
    exactamente la imagen dentro del frame: los emuladores no alinean igual
    todas las maquinas -PUAE baja unas veinte lineas la imagen de un A1200
    respecto a la de un A500- y mirar una franja fija se equivocaba de sitio.
    """
    ancho = frame[0]
    return sum(1 for y in range(min(alto, frame[1]))
               if len(set(frame[2][y * ancho:(y + 1) * ancho])) > 1)


def guardar_png(frame, ruta):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.png import Image, encode_png
    ancho, alto, pixeles = frame
    imagen = Image(ancho, alto, [(r, g, b, 255) for (r, g, b) in pixeles])
    with open(ruta, "wb") as fh:
        fh.write(encode_png(imagen))


# --- lo que la vista isometrica cambia de todo esto ------------------------
#
# Una habitacion vista desde una esquina es un suelo de losas, dos paredes y el
# fondo: cuatro o cinco tonos, y encima el marcador en blanco sobre el fondo.
# Los numeros de arriba estan puestos para un bosque o una calle, donde detras
# del marcador hay escenario; aqui no lo hay, y exigirlos no comprobaria que el
# juego dibuja sino que el juego es de otro genero. Estos son los mismos dos
# limites medidos en un castillo: en las seis maquinas salen 7 u 8 colores de
# titulo y 2 tonos en la franja del marcador.

def minimo_de_colores(iso: bool) -> int:
    """Cuantos colores prueban que la pantalla de titulo esta dibujando."""
    return 4 if iso else 8


def minimo_del_marcador(iso: bool) -> int:
    """Cuantos tonos prueban que la franja de arriba lleva marcador."""
    return 1 if iso else 2
