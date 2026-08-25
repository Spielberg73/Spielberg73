"""Conversion de graficos al formato de la Mega Drive (VDP de Sega).

Diferencias con la Neo Geo, que es lo que hay que tener claro:

* **Color**: 9 bits (3 por canal) en una palabra de 16:  `0000 BBB0 GGG0 RRR0`.
  Solo hay **4 paletas de 16 colores** (el 0 es transparente), asi que el juego
  entero tiene que caber en 4 paletas: aqui se fusionan las de los dibujos.
* **Tiles de 8x8**, 4 bits por pixel, 32 bytes cada uno y **lineales**: cada
  fila son 4 bytes y el nibble alto es el pixel de la izquierda. Nada de
  bitplanes.
* Los tiles de 16x16 de NeoPlat se parten en cuatro de 8x8. Se guardan en el
  orden que quiere el VDP para los sprites (por columnas): arriba-izquierda,
  abajo-izquierda, arriba-derecha, abajo-derecha.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .errors import ProjectError
from .gfx import Palette

RGB = Tuple[int, int, int]

TILE_PX = 8
TILE_BYTES = 32
COLORES_POR_PALETA = 16
PALETAS = 4


def md_color(rgb: RGB) -> int:
    """24 bits -> palabra de color del VDP (3 bits por canal)."""
    r = (rgb[0] * 7 + 127) // 255
    g = (rgb[1] * 7 + 127) // 255
    b = (rgb[2] * 7 + 127) // 255
    return (b << 9) | (g << 5) | (r << 1)


def md_color_a_rgb(valor: int) -> RGB:
    r = (valor >> 1) & 7
    g = (valor >> 5) & 7
    b = (valor >> 9) & 7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def codificar_tile(pixeles: Sequence[int]) -> bytes:
    """64 indices de paleta (8x8) -> los 32 bytes del tile."""
    if len(pixeles) != TILE_PX * TILE_PX:
        raise ValueError("un tile de Mega Drive son 64 pixeles, no %d" % len(pixeles))
    datos = bytearray(TILE_BYTES)
    for y in range(TILE_PX):
        for x in range(0, TILE_PX, 2):
            izquierda = pixeles[y * TILE_PX + x] & 0xF
            derecha = pixeles[y * TILE_PX + x + 1] & 0xF
            datos[y * 4 + x // 2] = (izquierda << 4) | derecha
    return bytes(datos)


def decodificar_tile(datos: Sequence[int]) -> List[int]:
    """Inversa de `codificar_tile` (la usan las pruebas)."""
    pixeles = [0] * (TILE_PX * TILE_PX)
    for y in range(TILE_PX):
        for x in range(0, TILE_PX, 2):
            byte = datos[y * 4 + x // 2]
            pixeles[y * TILE_PX + x] = (byte >> 4) & 0xF
            pixeles[y * TILE_PX + x + 1] = byte & 0xF
    return pixeles


def partir_16(tile16: Sequence[int]) -> List[List[int]]:
    """Un tile de 16x16 -> cuatro de 8x8, en el orden del VDP (por columnas).

    Orden: (izquierda, arriba), (izquierda, abajo), (derecha, arriba),
    (derecha, abajo). Es el que espera el hardware al dibujar un sprite de
    2x2 tiles, y el fondo lo aprovecha sabiendo esta misma regla.
    """
    if len(tile16) != 256:
        raise ValueError("se esperaba un tile de 16x16")
    trozos: List[List[int]] = []
    for columna in range(2):
        for fila in range(2):
            trozo: List[int] = []
            for y in range(TILE_PX):
                base = (fila * TILE_PX + y) * 16 + columna * TILE_PX
                trozo.extend(tile16[base:base + TILE_PX])
            trozos.append(trozo)
    return trozos


# --------------------------------------------------------------- paletas

@dataclass
class Reparto:
    """Como han quedado repartidas las paletas del juego en las 4 del VDP."""
    paletas: List[List[RGB]] = field(default_factory=list)
    # nombre de la paleta original -> (indice de paleta, mapa de indices)
    asignacion: Dict[str, Tuple[int, Dict[int, int]]] = field(default_factory=dict)


def repartir_paletas(paletas: List[Palette]) -> Reparto:
    """Mete todas las paletas del juego en las 4 que tiene la Mega Drive.

    Se juntan las que caben juntas (15 colores como mucho por paleta). Si no
    hay manera, se explica que sobra en vez de recortar por lo sano.
    """
    reparto = Reparto()
    grupos: List[List[RGB]] = []
    orden = sorted(range(len(paletas)), key=lambda i: -len(paletas[i].colors))

    for indice in orden:
        paleta = paletas[indice]
        colores = list(dict.fromkeys(paleta.colors))
        destino = None
        for numero, grupo in enumerate(grupos):
            union = list(dict.fromkeys(grupo + colores))
            if len(union) <= COLORES_POR_PALETA - 1:
                grupos[numero] = union
                destino = numero
                break
        if destino is None:
            if len(grupos) >= PALETAS:
                total = sum(len(g) for g in grupos) + len(colores)
                raise ProjectError(
                    "los graficos usan mas colores de los que caben en la Mega Drive "
                    "(%d colores repartidos, y solo hay 4 paletas de 15)" % total,
                    hint="usa menos colores por dibujo o repite colores entre dibujos; "
                         "'%s' es la que no cabe" % paleta.name,
                )
            grupos.append(colores)
            destino = len(grupos) - 1
        mapa = {}
        for i, color in enumerate(paleta.colors):
            mapa[i + 1] = grupos[destino].index(color) + 1
        mapa[0] = 0
        reparto.asignacion[paleta.name] = (destino, mapa)

    while len(grupos) < PALETAS:
        grupos.append([])
    reparto.paletas = grupos
    return reparto


def palabras_de_paleta(colores: List[RGB]) -> List[int]:
    """Los 16 valores que se copian a la CRAM (el 0 es transparente)."""
    salida = [0x0000]
    salida.extend(md_color(c) for c in colores[:COLORES_POR_PALETA - 1])
    salida.extend([0] * (COLORES_POR_PALETA - len(salida)))
    return salida


# ------------------------------------------------------------ la VRAM

@dataclass
class VramMD:
    """Los tiles del juego, ya en el formato del VDP."""
    tiles: bytearray = field(default_factory=bytearray)
    _cache: Dict[Tuple[int, ...], int] = field(default_factory=dict)

    @property
    def cuantos(self) -> int:
        return len(self.tiles) // TILE_BYTES

    def anadir(self, pixeles: Sequence[int], compartir: bool = True) -> int:
        clave = tuple(pixeles)
        if compartir and clave in self._cache:
            return self._cache[clave]
        indice = self.cuantos
        self.tiles.extend(codificar_tile(pixeles))
        if compartir:
            self._cache[clave] = indice
        return indice

    def anadir_16(self, tile16: Sequence[int], compartir: bool = True) -> int:
        """Mete un tile de 16x16 (cuatro de 8x8 seguidos) y devuelve el primero."""
        trozos = partir_16(tile16)
        primero = None
        for trozo in trozos:
            indice = self.anadir(trozo, compartir=False)
            if primero is None:
                primero = indice
        return primero if primero is not None else 0
