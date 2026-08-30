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
  cuadrantes de 8x8 que van **por columnas**: arriba-izquierda,
  abajo-izquierda, arriba-derecha, abajo-derecha. Dentro de cada fila van dos
  pixeles por byte, el nibble alto es el de la izquierda.

  El orden de los cuadrantes esta medido en el emulador, no leido: se subio un
  patron con los cuatro trozos de 32 bytes de cuatro colores y se miro donde
  caia cada uno. La primera version los ponia en orden de lectura y los
  dibujos salian partidos: el escenario ensenaba cada tile dos veces a media
  altura y los actores salian a cachos.
* Hay 256 patrones de PCG ($EB8000, 128 bytes cada uno = 32 KB), pero los 64
  ultimos son la tabla de nombres de la capa de fondo, asi que quedan **192**.
  De ahi comen los sprites **y** la capa. Ese es el limite real de la maquina,
  no los sprites.
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
# La PCG son 32 KB y un patron de 16x16 ocupa 128 bytes, o sea 256 patrones...
# menos los 64 ultimos, que es donde vive la tabla de nombres de la capa de
# fondo: en esta maquina la tabla esta metida dentro de la propia PCG.
PATRONES = 192


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

    Los cuatro cuadrantes van **por columnas** -arriba-izquierda,
    abajo-izquierda, arriba-derecha, abajo-derecha- y cada uno son 32 bytes:
    ocho filas de cuatro, dos pixeles por byte.
    """
    if len(pixeles) != TILE_PX * TILE_PX:
        raise ValueError("un patron del X68000 son 256 pixeles, no %d"
                         % len(pixeles))
    datos = bytearray(PATRON_BYTES)
    destino = 0
    for cuadrante_x in (0, 8):
        for cuadrante_y in (0, 8):
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
    for cuadrante_x in (0, 8):
        for cuadrante_y in (0, 8):
            for fila in range(8):
                y = cuadrante_y + fila
                for x in range(0, 8, 2):
                    byte = datos[origen]
                    pixeles[y * TILE_PX + cuadrante_x + x] = (byte >> 4) & 0xF
                    pixeles[y * TILE_PX + cuadrante_x + x + 1] = byte & 0xF
                    origen += 1
    return pixeles


class BancoX68k:
    """La RAM de patrones del X68000: 256 patrones de 16x16.

    De aqui comen los sprites **y** las dos capas BG, asi que 256 es el limite
    de verdad de esta maquina. Los patrones de un actor van seguidos y sin
    compartir, porque el motor cuenta con que los fotogramas de una hoja estan
    uno detras de otro; los de las capas de fondo si se comparten, que ahi se
    repite mucho.
    """

    def __init__(self) -> None:
        self.patrones: List[bytes] = []
        self.paletas: List[Palette] = []
        self._por_nombre: Dict[str, int] = {}
        self._compartidos: Dict[bytes, int] = {}

    # --- paletas -------------------------------------------------------

    def anadir_paleta(self, paleta: Palette) -> int:
        if paleta.name in self._por_nombre:
            return self._por_nombre[paleta.name]
        indice = len(self.paletas)
        self.paletas.append(paleta)
        self._por_nombre[paleta.name] = indice
        return indice

    def palabras(self) -> List[List[int]]:
        """Las paletas en formato del hardware, listas para escribir."""
        salida = []
        for paleta in self.paletas:
            colores = [x68k_color(c[:3]) for c in paleta.colors]
            colores += [0] * (COLORES_POR_PALETA - len(colores))
            # el color 0 de cada bloque es el transparente
            colores[0] = 0
            salida.append(colores[:COLORES_POR_PALETA])
        return salida

    # --- patrones ------------------------------------------------------

    def anadir(self, pixeles: Sequence[int], compartir: bool = False) -> int:
        datos = codificar_patron(pixeles)
        if compartir and datos in self._compartidos:
            return self._compartidos[datos]
        indice = len(self.patrones)
        self.patrones.append(datos)
        if compartir:
            self._compartidos[datos] = indice
        return indice

    def empaquetar_hoja(self, hoja) -> None:
        """Mete una hoja entera: sus patrones seguidos y su paleta."""
        hoja.palette_index = self.anadir_paleta(hoja.palette)
        hoja.first_tile = len(self.patrones)
        for tile in hoja.tiles:
            self.anadir(tile)

    @property
    def cuantos(self) -> int:
        return len(self.patrones)

    def datos(self) -> bytes:
        return b"".join(self.patrones)
