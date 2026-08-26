"""Conversion de graficos al formato de la Atari Jaguar.

La Jaguar es la mas comoda de las cuatro maquinas para esto: no hay bitplanes,
ni mascaras, ni tiles que empaquetar en ROMs raras. La pantalla es un mapa de
bits lineal de **un byte por pixel** y una tabla de 256 colores, asi que un
dibujo se guarda tal cual, fila a fila.

  - **Color**: 16 bits con un reparto peculiar, `RRRRRBBBBBGGGGGG`: cinco bits
    de rojo arriba, cinco de azul en medio y **seis de verde abajo**. No es
    RGB565: comprobado leyendo el color de fondo en el emulador.
  - **Transparencia**: el indice 0. El chip lo salta al componer, asi que los
    actores no necesitan mascara.
  - **256 colores a la vez**, asi que las paletas del juego caben todas juntas
    sin tener que fusionar nada a la fuerza (a diferencia del Amiga, que solo
    tiene 32).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .errors import ProjectError
from .gfx import Palette

RGB = Tuple[int, int, int]

COLORES = 256
TILE_PX = 16
BYTES_POR_TILE = TILE_PX * TILE_PX      # un byte por pixel


def jaguar_color(rgb: RGB) -> int:
    """24 bits -> palabra de color de la Jaguar (R5 B5 G6)."""
    r = (rgb[0] * 31 + 127) // 255
    g = (rgb[1] * 63 + 127) // 255
    b = (rgb[2] * 31 + 127) // 255
    return (r << 11) | (b << 6) | g


def jaguar_color_a_rgb(valor: int) -> RGB:
    r = (valor >> 11) & 0x1F
    b = (valor >> 6) & 0x1F
    g = valor & 0x3F
    return (r * 255 // 31, g * 255 // 63, b * 255 // 31)


@dataclass
class PaletaUnica:
    colores: List[RGB] = field(default_factory=list)
    asignacion: Dict[str, Dict[int, int]] = field(default_factory=dict)

    def palabras(self, hueco: int = COLORES) -> List[int]:
        salida = [jaguar_color(c) for c in self.colores]
        salida.extend([0] * (hueco - len(salida)))
        return salida


def fusionar_paletas(paletas: List[Palette], tope: int = COLORES - 1) -> PaletaUnica:
    """Junta todas las paletas del juego en la tabla de 256 colores.

    El indice 0 se reserva para el transparente y el ultimo para el marcador.
    """
    unica = PaletaUnica(colores=[(0, 0, 0)])       # el 0 es transparente
    for paleta in paletas:
        mapa = {0: 0}
        for i, color in enumerate(paleta.colors):
            if color not in unica.colores:
                if len(unica.colores) >= tope:
                    raise ProjectError(
                        "los graficos usan mas de %d colores distintos y en la "
                        "Jaguar caben %d" % (len(unica.colores), tope),
                        hint="repite colores entre dibujos; el que no cabe esta "
                             "en '%s'" % paleta.name,
                    )
                unica.colores.append(color)
            mapa[i + 1] = unica.colores.index(color)
        unica.asignacion[paleta.name] = mapa
    return unica


def codificar_tile(pixeles: Sequence[int]) -> bytes:
    """16x16 indices de paleta -> 256 bytes, fila a fila."""
    if len(pixeles) != TILE_PX * TILE_PX:
        raise ValueError("se esperaba un tile de 16x16")
    return bytes(bytearray(v & 0xFF for v in pixeles))


def decodificar_tile(datos: Sequence[int]) -> List[int]:
    """Inversa de `codificar_tile` (para comprobar la conversion)."""
    if len(datos) != BYTES_POR_TILE:
        raise ValueError("se esperaban %d bytes" % BYTES_POR_TILE)
    return list(datos)


@dataclass
class BancoJaguar:
    """Todos los dibujos del juego, uno detras de otro."""
    tiles: bytearray = field(default_factory=bytearray)
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
        if compartir:
            self._cache[clave] = indice
        return indice
