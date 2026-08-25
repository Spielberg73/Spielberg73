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


def guardar_png(frame, ruta):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "tools"))
    from ngplat.png import Image, encode_png
    ancho, alto, pixeles = frame
    imagen = Image(ancho, alto, [(r, g, b, 255) for (r, g, b) in pixeles])
    with open(ruta, "wb") as fh:
        fh.write(encode_png(imagen))
