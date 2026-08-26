"""Conversion de graficos al formato del Atari ST.

El ST se parece al Amiga en lo que importa aqui: la pantalla son **bitplanes**,
capas de un bit por pixel que se suman para dar el color. Pero solo tiene
cuatro, asi que se ven **16 colores a la vez** en vez de 32.

  - **Color**: 9 bits, `0000 0RRR 0GGG 0BBB` (tres bits por canal, 512 colores
    posibles). El STE amplia cada canal a cuatro bits colocando el nuevo bit
    abajo del todo, y por eso el mismo valor se ve casi igual en las dos
    maquinas; aqui se usa el del ST de siempre.
  - Los dibujos se guardan **entrelazados**, igual que en el Amiga: para cada
    fila del tile van las cuatro palabras de los cuatro bitplanes seguidas. En
    el ST eso no es una eleccion, es como esta la pantalla: cada grupo de 16
    pixeles ocupa cuatro palabras seguidas, una por plano.
  - La **mascara** va aparte y **una sola vez por fila**, no repetida por plano
    como en el Amiga. Alli la lee el blitter, que necesita que avance al mismo
    paso que el dibujo; aqui la lee la CPU, que puede usar la misma palabra para
    los cuatro planos y asi ocupa la cuarta parte.

Que se reutilice el entrelazado del Amiga no es casualidad ni pereza: los dos
chips guardan los bitplanes igual, palabra a palabra, y tener dos copias del
mismo bucle solo daria dos sitios donde equivocarse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .gfx_amiga import codificar_tile, decodificar_tile

RGB = Tuple[int, int, int]

PLANOS = 4
COLORES = 1 << PLANOS          # 16
TILE_PX = 16
BYTES_POR_TILE = TILE_PX * PLANOS * 2          # 128 bytes entrelazados
BYTES_MASCARA = TILE_PX * 2                    # 32 bytes: una palabra por fila


def st_color(rgb: RGB) -> int:
    """24 bits -> palabra de color del ST (tres bits por canal)."""
    r = (rgb[0] * 7 + 127) // 255
    g = (rgb[1] * 7 + 127) // 255
    b = (rgb[2] * 7 + 127) // 255
    return (r << 8) | (g << 4) | b


def st_color_a_rgb(valor: int) -> RGB:
    r = (valor >> 8) & 0x7
    g = (valor >> 4) & 0x7
    b = valor & 0x7
    return (r * 255 // 7, g * 255 // 7, b * 255 // 7)


def codificar_mascara(pixeles: Sequence[int]) -> bytes:
    """Un bit por pixel, a uno donde el dibujo tapa el fondo.

    Una palabra por fila y ya: la CPU la usa para los cuatro planos.
    """
    if len(pixeles) != TILE_PX * TILE_PX:
        raise ValueError("se esperaba un tile de 16x16")
    datos = bytearray()
    for y in range(TILE_PX):
        palabra = 0
        for x in range(TILE_PX):
            if pixeles[y * TILE_PX + x]:
                palabra |= 1 << (15 - x)
        datos.append((palabra >> 8) & 0xFF)
        datos.append(palabra & 0xFF)
    return bytes(datos)


def decodificar_mascara(datos: Sequence[int]) -> List[int]:
    """Inversa de `codificar_mascara` (la usan las pruebas)."""
    pixeles = [0] * (TILE_PX * TILE_PX)
    for y in range(TILE_PX):
        palabra = (datos[y * 2] << 8) | datos[y * 2 + 1]
        for x in range(TILE_PX):
            if (palabra >> (15 - x)) & 1:
                pixeles[y * TILE_PX + x] = 1
    return pixeles


@dataclass
class BancoSt:
    """Todos los dibujos del juego, ya entrelazados, y sus mascaras."""
    tiles: bytearray = field(default_factory=bytearray)
    mascaras: bytearray = field(default_factory=bytearray)
    planos: int = PLANOS
    _cache: Dict[Tuple[int, ...], int] = field(default_factory=dict)

    @property
    def bytes_por_tile(self) -> int:
        return TILE_PX * self.planos * 2

    @property
    def cuantos(self) -> int:
        return len(self.tiles) // self.bytes_por_tile

    def anadir(self, pixeles: Sequence[int], compartir: bool = True) -> int:
        clave = tuple(pixeles)
        if compartir and clave in self._cache:
            return self._cache[clave]
        indice = self.cuantos
        self.tiles.extend(codificar_tile(pixeles, self.planos))
        self.mascaras.extend(codificar_mascara(pixeles))
        if compartir:
            self._cache[clave] = indice
        return indice


__all__ = ["PLANOS", "COLORES", "TILE_PX", "BYTES_POR_TILE", "BYTES_MASCARA",
           "st_color", "st_color_a_rgb", "codificar_tile", "decodificar_tile",
           "codificar_mascara", "decodificar_mascara", "BancoSt"]
