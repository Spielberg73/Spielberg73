"""Conversion de graficos al formato del Amiga (OCS/ECS).

El Amiga no trabaja con tiles ni con "un byte por pixel": la pantalla son
**bitplanes**, capas de un bit por pixel que se suman para dar el color. Con 5
bitplanes salen 32 colores, que es lo que usa NeoPlat.

  - **Color**: 12 bits, `0000 RRRR GGGG BBBB` (4 bits por canal).
  - **Una sola paleta de 32 colores** para todo lo que se ve a la vez, asi que
    aqui se fusionan todas las del juego.
  - Los dibujos se guardan **entrelazados**: para cada fila del tile van las
    cinco palabras de los cinco bitplanes seguidas. Asi el blitter puede
    copiar un tile entero de una sola pasada.
  - Cada dibujo lleva ademas su **mascara**: un bit a uno donde el dibujo no es
    transparente, que es lo que usa el blitter para recortarlo sobre el fondo.
    La mascara se guarda repetida cinco veces por fila, una por bitplane, para
    que avance al mismo paso que el dibujo entrelazado y el blitter pueda hacer
    los cinco planos de una sola pasada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .errors import ProjectError
from .gfx import Palette

RGB = Tuple[int, int, int]

PLANOS = 5
COLORES = 1 << PLANOS          # 32
TILE_PX = 16
PALABRAS_POR_FILA = 1          # 16 pixeles = una palabra por plano
BYTES_POR_TILE = TILE_PX * PLANOS * 2          # 160 bytes entrelazados
BYTES_MASCARA = TILE_PX * PLANOS * 2           # 160 bytes: ver codificar_mascara


def amiga_color(rgb: RGB) -> int:
    """24 bits -> palabra de color del Amiga (4 bits por canal)."""
    r = (rgb[0] * 15 + 127) // 255
    g = (rgb[1] * 15 + 127) // 255
    b = (rgb[2] * 15 + 127) // 255
    return (r << 8) | (g << 4) | b


def amiga_color_a_rgb(valor: int) -> RGB:
    r = (valor >> 8) & 0xF
    g = (valor >> 4) & 0xF
    b = valor & 0xF
    return (r * 255 // 15, g * 255 // 15, b * 255 // 15)


def codificar_tile(pixeles: Sequence[int], planos: int = PLANOS) -> bytes:
    """16x16 indices de paleta -> tile entrelazado (una palabra por plano y fila)."""
    if len(pixeles) != TILE_PX * TILE_PX:
        raise ValueError("se esperaba un tile de 16x16")
    datos = bytearray()
    for y in range(TILE_PX):
        for plano in range(planos):
            palabra = 0
            for x in range(TILE_PX):
                bit = (pixeles[y * TILE_PX + x] >> plano) & 1
                palabra |= bit << (15 - x)
            datos.append((palabra >> 8) & 0xFF)
            datos.append(palabra & 0xFF)
    return bytes(datos)


def decodificar_tile(datos: Sequence[int], planos: int = PLANOS) -> List[int]:
    """Inversa de `codificar_tile` (la usan las pruebas)."""
    pixeles = [0] * (TILE_PX * TILE_PX)
    for y in range(TILE_PX):
        for plano in range(planos):
            base = (y * planos + plano) * 2
            palabra = (datos[base] << 8) | datos[base + 1]
            for x in range(TILE_PX):
                if (palabra >> (15 - x)) & 1:
                    pixeles[y * TILE_PX + x] |= 1 << plano
    return pixeles


def codificar_mascara(pixeles: Sequence[int], planos: int = PLANOS) -> bytes:
    """Un bit por pixel (1 = tapa el fondo), repetido para cada bitplane.

    El dibujo va entrelazado, asi que el blitter recorre las filas en el orden
    (fila 0 plano 0, fila 0 plano 1, ... fila 1 plano 0, ...). La mascara tiene
    que seguirle el paso, y por eso cada palabra sale `planos` veces seguidas.
    """
    datos = bytearray()
    for y in range(TILE_PX):
        palabra = 0
        for x in range(TILE_PX):
            if pixeles[y * TILE_PX + x]:
                palabra |= 1 << (15 - x)
        for _ in range(planos):
            datos.append((palabra >> 8) & 0xFF)
            datos.append(palabra & 0xFF)
    return bytes(datos)


def decodificar_mascara(datos: Sequence[int], planos: int = PLANOS) -> List[int]:
    """Inversa de `codificar_mascara` (la usan las pruebas)."""
    pixeles = [0] * (TILE_PX * TILE_PX)
    for y in range(TILE_PX):
        base = y * planos * 2
        palabra = (datos[base] << 8) | datos[base + 1]
        for x in range(TILE_PX):
            if (palabra >> (15 - x)) & 1:
                pixeles[y * TILE_PX + x] = 1
    return pixeles


# ---------------------------------------------------------------- paleta

@dataclass
class PaletaUnica:
    """Los 32 colores del juego y como llegar a ellos desde cada dibujo."""
    colores: List[RGB] = field(default_factory=list)
    asignacion: Dict[str, Dict[int, int]] = field(default_factory=dict)

    def palabras(self) -> List[int]:
        salida = [amiga_color(c) for c in self.colores]
        salida.extend([0] * (COLORES - len(salida)))
        return salida[:COLORES]


def fusionar_paletas(paletas: List[Palette]) -> PaletaUnica:
    """Junta todas las paletas del juego en los 32 colores del Amiga."""
    unica = PaletaUnica(colores=[(0, 0, 0)])       # el 0 es el color de fondo
    for paleta in paletas:
        mapa = {0: 0}
        for i, color in enumerate(paleta.colors):
            if color not in unica.colores:
                if len(unica.colores) >= COLORES:
                    raise ProjectError(
                        "los graficos usan mas de %d colores distintos y el Amiga "
                        "muestra %d a la vez" % (len(unica.colores) + 1, COLORES),
                        hint="repite colores entre dibujos o quita alguna capa de fondo; "
                             "la que no cabe es '%s'" % paleta.name,
                    )
                unica.colores.append(color)
            mapa[i + 1] = unica.colores.index(color)
        unica.asignacion[paleta.name] = mapa
    return unica


# ------------------------------------------------------------ los dibujos

@dataclass
class BancoAmiga:
    """Todos los dibujos del juego, ya entrelazados, y sus mascaras."""
    tiles: bytearray = field(default_factory=bytearray)
    mascaras: bytearray = field(default_factory=bytearray)
    _cache: Dict[Tuple[int, ...], int] = field(default_factory=dict)

    @property
    def cuantos(self) -> int:
        return len(self.tiles) // BYTES_POR_TILE

    def anadir(self, pixeles: Sequence[int], compartir: bool = True) -> int:
        clave = tuple(pixeles)
        if compartir and clave in self._cache:
            return self._cache[clave]
        indice = self.cuantos
        self.tiles.extend(codificar_tile(pixeles))
        self.mascaras.extend(codificar_mascara(pixeles))
        if compartir:
            self._cache[clave] = indice
        return indice
