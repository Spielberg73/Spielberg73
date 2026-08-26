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
    perdidos: int = 0              # colores que no cabian y se han aproximado

    def palabras(self) -> List[int]:
        return self.palabras_de(amiga_color, COLORES)

    def palabras_de(self, convertir, cuantos: int) -> List[int]:
        """La misma paleta en el formato de otra maquina.

        La fusion de paletas no tiene nada de Amiga: es la misma cuenta en el
        Atari ST, que tambien ensena una sola paleta de todo lo que hay en
        pantalla. Lo unico que cambia es cuantos colores caben y como se
        escribe cada uno.
        """
        salida = [convertir(c) for c in self.colores]
        salida.extend([0] * (cuantos - len(salida)))
        return salida[:cuantos]


def fusionar_paletas(paletas: List[Palette], tope: int = COLORES,
                     pesos: Dict[RGB, int] | None = None,
                     aproximar: bool = False) -> PaletaUnica:
    """Junta todas las paletas del juego en los colores que quepan.

    `tope` cuenta el color 0, que es el del fondo. Si los dibujos usan mas
    colores de los que caben hay dos salidas: dar un error (lo normal, con 32
    colores nunca pasa) o, con `aproximar`, quedarse con los colores mas
    usados y cambiar los demas por el mas parecido. Eso ultimo hace falta en el
    modo de doble plano del Amiga, donde solo hay siete colores por plano y no
    hay dibujo que quepa sin retocarlo.
    """
    distintos: List[RGB] = []
    culpable = ""
    for paleta in paletas:
        for color in paleta.colors:
            if color not in distintos:
                distintos.append(color)
                if not culpable and len(distintos) + 1 > tope:
                    culpable = paleta.name

    if len(distintos) + 1 > tope:
        if not aproximar:
            raise ProjectError(
                "los graficos usan %d colores distintos y aqui caben %d"
                % (len(distintos) + 1, tope),
                hint="repite colores entre dibujos: el primero que se sale es "
                     "'%s'" % culpable,
            )
        elegidos = _reducir(distintos, pesos or {}, tope - 1)
    else:
        elegidos = list(distintos)

    unica = PaletaUnica(colores=[(0, 0, 0)] + elegidos)   # el 0 es el fondo
    unica.perdidos = len(distintos) - len(elegidos)
    cercano = {c: 1 + _mas_parecido(c, elegidos) for c in distintos}
    for paleta in paletas:
        mapa = {0: 0}
        for i, color in enumerate(paleta.colors):
            mapa[i + 1] = cercano[color]
        unica.asignacion[paleta.name] = mapa
    return unica


def _distancia(a: RGB, b: RGB) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _mas_parecido(color: RGB, candidatos: List[RGB]) -> int:
    mejor, mejor_d = 0, None
    for i, c in enumerate(candidatos):
        d = _distancia(color, c)
        if mejor_d is None or d < mejor_d:
            mejor, mejor_d = i, d
    return mejor


def _reducir(colores: List[RGB], pesos: Dict[RGB, int], cuantos: int) -> List[RGB]:
    """Corte por la mediana: parte la nube de colores en `cuantos` cajas y se
    queda con el color medio de cada una, pesando cuanto se usa cada uno.

    Es el metodo de toda la vida para bajar de colores, y es determinista: la
    misma imagen da siempre la misma paleta.
    """
    peso = lambda c: max(1, pesos.get(c, 1))
    cajas: List[List[RGB]] = [list(colores)]
    while len(cajas) < cuantos:
        # se parte la caja mas ancha, medida en el canal que mas varia
        mejor, mejor_rango, mejor_canal = -1, -1, 0
        for i, caja in enumerate(cajas):
            if len(caja) < 2:
                continue
            for canal in range(3):
                valores = [c[canal] for c in caja]
                rango = max(valores) - min(valores)
                if rango > mejor_rango:
                    mejor, mejor_rango, mejor_canal = i, rango, canal
        if mejor < 0:
            break
        caja = cajas.pop(mejor)
        caja.sort(key=lambda c: (c[mejor_canal], c))
        # se corta donde la mitad del peso queda a cada lado
        total = sum(peso(c) for c in caja)
        acumulado, corte = 0, 1
        for i, c in enumerate(caja[:-1]):
            acumulado += peso(c)
            corte = i + 1
            if acumulado * 2 >= total:
                break
        cajas.append(caja[:corte])
        cajas.append(caja[corte:])

    salida = []
    for caja in cajas:
        total = sum(peso(c) for c in caja)
        salida.append(tuple(sum(c[canal] * peso(c) for c in caja) // total
                            for canal in range(3)))
    return salida


# ------------------------------------------------------------ los dibujos

@dataclass
class BancoAmiga:
    """Todos los dibujos del juego, ya entrelazados, y sus mascaras.

    `planos` son 5 en el modo normal y 3 en doble plano, donde los seis
    bitplanes se reparten entre los dos planos."""
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
        self.mascaras.extend(codificar_mascara(pixeles, self.planos))
        if compartir:
            self._cache[clave] = indice
        return indice
