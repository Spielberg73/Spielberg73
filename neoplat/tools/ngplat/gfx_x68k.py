"""Conversion de graficos al formato del Sharp X68000 (chip CYNTHIA).

Es la maquina mas parecida a la Neo Geo de las que lleva el kit, pero con una
diferencia que lo cambia todo: **tiene capas de fondo de verdad**. En la Neo
Geo el escenario se dibuja con columnas de sprites (21 de las 381 que hay); aqui
lo lleva el hardware con dos planos BG, y los sprites se quedan enteros para los
actores.

Lo que hay que tener claro:

* **Color**: palabra de 16 bits en formato GRBi -`GGGGG RRRRR BBBBB I`-, con
  cinco bits por canal y un bit de intensidad al final que es el LSB comun a
  los tres. O sea, 65.536 colores posibles y 32 niveles por canal (33 contando
  el bit de intensidad).
* **Paletas**: 16 bloques de 16 colores en $E82200, y los comparten los sprites
  y las dos capas BG. El color 0 de cada bloque es el transparente.
* **PCG**: los dibujos son de 16x16 y ocupan **128 bytes**, partidos en cuatro
  cuadrantes de 8x8 y en este orden: arriba-izquierda, arriba-derecha,
  abajo-izquierda, abajo-derecha. Dentro de cada fila van dos pixeles por byte,
  el nibble alto es el de la izquierda.
* Hay **256 patrones** de PCG ($EB8000, 128 bytes cada uno = 32 KB), y de ahi
  comen los sprites **y** las capas BG. Ese es el limite real de la maquina, no
  los sprites.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

from .errors import ProjectError
from .gfx import Palette

RGB = Tuple[int, int, int]

TILE_PX = 16                 # el PCG del X68000 es de 16x16
PATRON_BYTES = 128
COLORES_POR_PALETA = 16
BLOQUES = 16                 # bloques de paleta que comparten sprites y BG
PATRONES = 256               # los que caben en la PCG RAM


def _nivel(cinco: int, intensidad: int) -> int:
    """Lo que se ve de verdad en pantalla: los cinco bits del canal mas el bit
    de intensidad hacen un valor de seis bits (0..63)."""
    return ((cinco << 1) | intensidad) * 255 // 63


def x68k_color(rgb: RGB) -> int:
    """24 bits -> palabra GRBi del X68000.

    El bit de intensidad **es de los tres canales a la vez**: es el LSB comun.
    Asi que no se puede redondear cada canal por su cuenta y luego votar, que
    era lo primero que se probo y dejaba el (24, 20, 28) del estilo hierro en
    (28, 20, 28). Se prueban los dos valores del bit y se elige el que menos se
    aleja en total, que son doce cuentas y sale exacto.
    """
    mejor = None
    for intensidad in (0, 1):
        canales, error = [], 0
        for objetivo in rgb:
            cinco = min(range(32),
                        key=lambda c: abs(_nivel(c, intensidad) - objetivo))
            canales.append(cinco)
            error += abs(_nivel(cinco, intensidad) - objetivo)
        if mejor is None or error < mejor[0]:
            mejor = (error, canales, intensidad)
    _, (r, g, b), intensidad = mejor
    return (g << 11) | (r << 6) | (b << 1) | intensidad


def x68k_color_a_rgb(valor: int) -> RGB:
    """Inversa de `x68k_color` (la usan las pruebas)."""
    i = valor & 1
    return (_nivel((valor >> 6) & 31, i),
            _nivel((valor >> 11) & 31, i),
            _nivel((valor >> 1) & 31, i))


def codificar_patron(pixeles: Sequence[int]) -> bytes:
    """256 indices de paleta (16x16) -> los 128 bytes del patron de PCG.

    Los cuatro cuadrantes van en orden de lectura -arriba-izquierda,
    arriba-derecha, abajo-izquierda, abajo-derecha- y cada uno son 32 bytes:
    ocho filas de cuatro, dos pixeles por byte.
    """
    if len(pixeles) != TILE_PX * TILE_PX:
        raise ValueError("un patron del X68000 son 256 pixeles, no %d"
                         % len(pixeles))
    datos = bytearray(PATRON_BYTES)
    destino = 0
    for cuadrante_y in (0, 8):
        for cuadrante_x in (0, 8):
            for fila in range(8):
                y = cuadrante_y + fila
                for x in range(0, 8, 2):
                    izquierda = pixeles[y * TILE_PX + cuadrante_x + x] & 0xF
                    derecha = pixeles[y * TILE_PX + cuadrante_x + x + 1] & 0xF
                    datos[destino] = (izquierda << 4) | derecha
                    destino += 1
    return bytes(datos)


def decodificar_patron(datos: Sequence[int]) -> List[int]:
    """Inversa de `codificar_patron` (la usan las pruebas)."""
    pixeles = [0] * (TILE_PX * TILE_PX)
    origen = 0
    for cuadrante_y in (0, 8):
        for cuadrante_x in (0, 8):
            for fila in range(8):
                y = cuadrante_y + fila
                for x in range(0, 8, 2):
                    byte = datos[origen]
                    pixeles[y * TILE_PX + cuadrante_x + x] = (byte >> 4) & 0xF
                    pixeles[y * TILE_PX + cuadrante_x + x + 1] = byte & 0xF
                    origen += 1
    return pixeles
