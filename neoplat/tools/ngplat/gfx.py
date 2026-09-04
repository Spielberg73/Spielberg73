"""Conversion de PNG al formato grafico de la Neo Geo.

Formatos implementados (ver docs/neogeo.md para la referencia completa):

* Color: 16 bits por color, `D RGB RRRR GGGG BBBB`, donde el bit 15 es el bit
  "dark" y los bits 14/13/12 son los bits menos significativos de rojo, verde y
  azul. Cada canal acaba teniendo 5 bits (0-31).
* Paleta: 16 colores; el color 0 siempre es transparente.
* Tile de sprite (ROM C): 16x16 pixeles, 4 bits por pixel, 128 bytes repartidos
  entre C1 (planos 0 y 1) y C2 (planos 2 y 3), 64 bytes en cada ROM:
      C1[ 0..15] plano 0, mitad derecha (x = 8..15), filas 0..15
      C1[16..31] plano 0, mitad izquierda (x = 0..7)
      C1[32..47] plano 1, mitad derecha
      C1[48..63] plano 1, mitad izquierda
  En cada byte, el bit 7 es el pixel de mas a la izquierda del grupo de 8.
* Tile de fix (ROM S): 8x8 pixeles, 4 bits por pixel, 32 bytes. Cada fila ocupa
  4 bytes y las columnas van en el orden 3, 0, 1, 2 (nibble bajo = pixel par).

`encode_sprite_tile`/`decode_sprite_tile` y `encode_fix_tile`/`decode_fix_tile`
son inversas exactas, cosa que comprueban los tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .errors import ProjectError
from .png import Image, read_png

RGB = Tuple[int, int, int]

TILE_PX = 16
FIX_PX = 8
SPRITE_TILE_BYTES = 64        # por cada ROM (C1 y C2)
FIX_TILE_BYTES = 32
PALETTE_COLORS = 16


# ------------------------------------------------------------------- colores

def ng_color(rgb: RGB) -> int:
    """Convierte un color de 24 bits al valor de 16 bits de la Neo Geo."""
    r5 = (rgb[0] * 31 + 127) // 255
    g5 = (rgb[1] * 31 + 127) // 255
    b5 = (rgb[2] * 31 + 127) // 255
    dark = 1 if (r5 & 1) and (g5 & 1) and (b5 & 1) else 0
    return (
        (dark << 15)
        | ((r5 & 1) << 14)
        | ((g5 & 1) << 13)
        | ((b5 & 1) << 12)
        | ((r5 >> 1) << 8)
        | ((g5 >> 1) << 4)
        | (b5 >> 1)
    )


def ng_color_to_rgb(value: int) -> RGB:
    """Inversa aproximada de `ng_color`, util para el preview y los tests."""
    r5 = ((value >> 8) & 0xF) * 2 + ((value >> 14) & 1)
    g5 = ((value >> 4) & 0xF) * 2 + ((value >> 13) & 1)
    b5 = (value & 0xF) * 2 + ((value >> 12) & 1)
    return (r5 * 255 // 31, g5 * 255 // 31, b5 * 255 // 31)


@dataclass
class Palette:
    name: str
    colors: List[RGB] = field(default_factory=list)   # sin contar el indice 0

    def key(self) -> Tuple[RGB, ...]:
        return tuple(self.colors)

    def words(self) -> List[int]:
        out = [0x8000]  # indice 0: transparente (bit dark encendido, como el estandar)
        out.extend(ng_color(c) for c in self.colors)
        out.extend([0] * (PALETTE_COLORS - len(out)))
        return out

    def index_of(self, rgb: RGB) -> int:
        return self.colors.index(rgb) + 1


def build_palette(image: Image, name: str, where: str) -> Tuple[Palette, Dict[RGB, int]]:
    """Extrae la paleta de una imagen (maximo 15 colores + transparente)."""
    opaque: List[RGB] = []
    for px in image.pixels:
        if px[3] < 128:
            continue
        rgb = (px[0], px[1], px[2])
        if rgb not in opaque:
            opaque.append(rgb)
    if len(opaque) > PALETTE_COLORS - 1:
        raise ProjectError(
            "'%s' usa %d colores y la Neo Geo permite 15 por paleta (+ transparente)"
            % (where, len(opaque)),
            hint="reduce los colores de la imagen (indexada a 16 colores)",
        )
    palette = Palette(name=name, colors=opaque)
    lookup = {rgb: i + 1 for i, rgb in enumerate(opaque)}
    return palette, lookup


def quantize(image: Image, lookup: Dict[RGB, int]) -> List[int]:
    """Devuelve un indice de paleta (0 = transparente) por pixel."""
    out: List[int] = []
    for px in image.pixels:
        if px[3] < 128:
            out.append(0)
        else:
            out.append(lookup[(px[0], px[1], px[2])])
    return out


# --------------------------------------------------------------------- tiles

def encode_sprite_tile(pixels: Sequence[int]) -> Tuple[bytes, bytes]:
    """16x16 indices de paleta -> (64 bytes de C1, 64 bytes de C2)."""
    if len(pixels) != TILE_PX * TILE_PX:
        raise ValueError("un tile de sprite son 256 pixeles, no %d" % len(pixels))
    c1 = bytearray(SPRITE_TILE_BYTES)
    c2 = bytearray(SPRITE_TILE_BYTES)
    for y in range(TILE_PX):
        for half in range(2):            # 0 = mitad derecha, 1 = mitad izquierda
            base_x = 8 if half == 0 else 0
            bits = [0, 0, 0, 0]
            for i in range(8):
                value = pixels[y * TILE_PX + base_x + i] & 0xF
                bit = 7 - i              # bit 7 = pixel mas a la izquierda
                for plane in range(4):
                    bits[plane] |= ((value >> plane) & 1) << bit
            offset = half * 16 + y
            c1[offset] = bits[0]
            c1[offset + 32] = bits[1]
            c2[offset] = bits[2]
            c2[offset + 32] = bits[3]
    return bytes(c1), bytes(c2)


def decode_sprite_tile(c1: Sequence[int], c2: Sequence[int]) -> List[int]:
    """Inversa de `encode_sprite_tile` (para verificar la conversion)."""
    pixels = [0] * (TILE_PX * TILE_PX)
    for y in range(TILE_PX):
        for half in range(2):
            base_x = 8 if half == 0 else 0
            offset = half * 16 + y
            planes = (c1[offset], c1[offset + 32], c2[offset], c2[offset + 32])
            for i in range(8):
                bit = 7 - i
                value = 0
                for plane in range(4):
                    value |= ((planes[plane] >> bit) & 1) << plane
                pixels[y * TILE_PX + base_x + i] = value
    return pixels


# Orden de columnas de los tiles del plano fix: 3, 0, 1, 2 (dos pixeles por byte).
FIX_COLUMN_ORDER = (3, 0, 1, 2)


def encode_fix_tile(pixels: Sequence[int]) -> bytes:
    """8x8 indices de paleta -> 32 bytes del ROM S."""
    if len(pixels) != FIX_PX * FIX_PX:
        raise ValueError("un tile de fix son 64 pixeles, no %d" % len(pixels))
    data = bytearray(FIX_TILE_BYTES)
    for y in range(FIX_PX):
        for group in range(4):           # cada grupo son 2 pixeles contiguos
            x = group * 2
            low = pixels[y * FIX_PX + x] & 0xF
            high = pixels[y * FIX_PX + x + 1] & 0xF
            data[y * 4 + FIX_COLUMN_ORDER[group]] = low | (high << 4)
    return bytes(data)


def decode_fix_tile(data: Sequence[int]) -> List[int]:
    pixels = [0] * (FIX_PX * FIX_PX)
    for y in range(FIX_PX):
        for group in range(4):
            byte = data[y * 4 + FIX_COLUMN_ORDER[group]]
            x = group * 2
            pixels[y * FIX_PX + x] = byte & 0xF
            pixels[y * FIX_PX + x + 1] = (byte >> 4) & 0xF
    return pixels


# ------------------------------------------------------------ hojas de sprite

@dataclass
class Sheet:
    """Una imagen ya troceada en fotogramas y tiles de 16x16."""
    name: str
    path: str
    frame_w: int
    frame_h: int
    frames: int
    palette: Palette
    tiles: List[List[int]] = field(default_factory=list)  # indices de paleta
    first_tile: int = 0                                   # asignado al empaquetar
    palette_index: int = 0
    per_row: int = 1        # fotogramas por fila de la imagen

    @property
    def cols(self) -> int:
        return self.frame_w // TILE_PX

    @property
    def rows(self) -> int:
        return self.frame_h // TILE_PX

    @property
    def tiles_per_frame(self) -> int:
        return self.cols * self.rows


def load_sheet(path: str, name: str, frame_w: int, frame_h: int) -> Sheet:
    """Trocea un PNG en fotogramas horizontales y estos en tiles de 16x16.

    Los tiles de cada fotograma se guardan en el orden que espera el hardware:
    de arriba a abajo dentro de cada columna, y luego a la columna siguiente.
    """
    image = read_png(path)
    if image.width % frame_w or image.height % frame_h:
        raise ProjectError(
            "'%s' mide %dx%d y no es multiplo del fotograma %dx%d"
            % (name, image.width, image.height, frame_w, frame_h),
            hint="recorta la imagen o ajusta 'frame' en game.yaml",
        )
    per_row = image.width // frame_w
    rows_of_frames = image.height // frame_h
    frames = per_row * rows_of_frames
    palette, lookup = build_palette(image, name, name)
    sheet = Sheet(name=name, path=path, frame_w=frame_w, frame_h=frame_h,
                  frames=frames, palette=palette, per_row=per_row)
    for fy in range(rows_of_frames):
        for fx in range(per_row):
            frame = image.crop(fx * frame_w, fy * frame_h, frame_w, frame_h)
            indices = quantize(frame, lookup)
            for col in range(frame_w // TILE_PX):
                for row in range(frame_h // TILE_PX):
                    tile: List[int] = []
                    for y in range(TILE_PX):
                        base = (row * TILE_PX + y) * frame_w + col * TILE_PX
                        tile.extend(indices[base:base + TILE_PX])
                    sheet.tiles.append(tile)
    return sheet


def load_tileset(path: str, name: str = "tileset") -> Sheet:
    """Carga un tileset como hoja de fotogramas de 16x16 (uno por tile)."""
    return load_sheet(path, name, TILE_PX, TILE_PX)


# ------------------------------------------------------------------- ROM data

@dataclass
class RomData:
    c1: bytearray = field(default_factory=bytearray)
    c2: bytearray = field(default_factory=bytearray)
    s1: bytearray = field(default_factory=bytearray)
    palettes: List[Palette] = field(default_factory=list)
    _cache: Dict[Tuple[int, ...], int] = field(default_factory=dict)

    def add_sprite_tile_shared(self, pixels: Sequence[int]) -> int:
        """Como add_sprite_tile, pero reutiliza los tiles repetidos.

        En los fondos de parallax (cielos, degradados) la mayoria de los tiles
        son iguales, asi que esto ahorra bastante ROM."""
        key = tuple(pixels)
        if key in self._cache:
            return self._cache[key]
        index = self.add_sprite_tile(pixels)
        self._cache[key] = index
        return index

    def add_sprite_tile(self, pixels: Sequence[int]) -> int:
        index = len(self.c1) // SPRITE_TILE_BYTES
        c1, c2 = encode_sprite_tile(pixels)
        self.c1.extend(c1)
        self.c2.extend(c2)
        return index

    def add_fix_tile(self, pixels: Sequence[int]) -> int:
        index = len(self.s1) // FIX_TILE_BYTES
        self.s1.extend(encode_fix_tile(pixels))
        return index

    def add_palette(self, palette: Palette) -> int:
        key = palette.key()
        for i, existing in enumerate(self.palettes):
            if existing.key() == key:
                return i
        self.palettes.append(palette)
        return len(self.palettes) - 1

    def pack_sheet(self, sheet: Sheet) -> Sheet:
        sheet.palette_index = self.add_palette(sheet.palette)
        sheet.first_tile = len(self.c1) // SPRITE_TILE_BYTES
        for tile in sheet.tiles:
            self.add_sprite_tile(tile)
        return sheet

    @property
    def sprite_tiles(self) -> int:
        return len(self.c1) // SPRITE_TILE_BYTES

    @property
    def fix_tiles(self) -> int:
        return len(self.s1) // FIX_TILE_BYTES


# ------------------------------------------------------------ fuente del HUD

# Fuente de 3x5 pixeles: cada glifo son 5 filas de 3 bits (bit 2 = izquierda).
FONT_3X5: Dict[str, Tuple[int, int, int, int, int]] = {
    " ": (0b000, 0b000, 0b000, 0b000, 0b000),
    "0": (0b111, 0b101, 0b101, 0b101, 0b111),
    "1": (0b010, 0b110, 0b010, 0b010, 0b111),
    "2": (0b111, 0b001, 0b111, 0b100, 0b111),
    "3": (0b111, 0b001, 0b111, 0b001, 0b111),
    "4": (0b101, 0b101, 0b111, 0b001, 0b001),
    "5": (0b111, 0b100, 0b111, 0b001, 0b111),
    "6": (0b111, 0b100, 0b111, 0b101, 0b111),
    "7": (0b111, 0b001, 0b010, 0b010, 0b010),
    "8": (0b111, 0b101, 0b111, 0b101, 0b111),
    "9": (0b111, 0b101, 0b111, 0b001, 0b111),
    "A": (0b111, 0b101, 0b111, 0b101, 0b101),
    "B": (0b110, 0b101, 0b110, 0b101, 0b110),
    "C": (0b111, 0b100, 0b100, 0b100, 0b111),
    "D": (0b110, 0b101, 0b101, 0b101, 0b110),
    "E": (0b111, 0b100, 0b111, 0b100, 0b111),
    "F": (0b111, 0b100, 0b111, 0b100, 0b100),
    "G": (0b111, 0b100, 0b101, 0b101, 0b111),
    "H": (0b101, 0b101, 0b111, 0b101, 0b101),
    "I": (0b111, 0b010, 0b010, 0b010, 0b111),
    "J": (0b001, 0b001, 0b001, 0b101, 0b111),
    "K": (0b101, 0b101, 0b110, 0b101, 0b101),
    "L": (0b100, 0b100, 0b100, 0b100, 0b111),
    "M": (0b101, 0b111, 0b111, 0b101, 0b101),
    "N": (0b110, 0b101, 0b101, 0b101, 0b101),
    "O": (0b111, 0b101, 0b101, 0b101, 0b111),
    "P": (0b111, 0b101, 0b111, 0b100, 0b100),
    "Q": (0b111, 0b101, 0b101, 0b111, 0b011),
    "R": (0b111, 0b101, 0b110, 0b101, 0b101),
    "S": (0b111, 0b100, 0b111, 0b001, 0b111),
    "T": (0b111, 0b010, 0b010, 0b010, 0b010),
    "U": (0b101, 0b101, 0b101, 0b101, 0b111),
    "V": (0b101, 0b101, 0b101, 0b101, 0b010),
    "W": (0b101, 0b101, 0b111, 0b111, 0b101),
    "X": (0b101, 0b101, 0b010, 0b101, 0b101),
    "Y": (0b101, 0b101, 0b010, 0b010, 0b010),
    "Z": (0b111, 0b001, 0b010, 0b100, 0b111),
    "-": (0b000, 0b000, 0b111, 0b000, 0b000),
    ".": (0b000, 0b000, 0b000, 0b000, 0b010),
    ":": (0b000, 0b010, 0b000, 0b010, 0b000),
    "!": (0b010, 0b010, 0b010, 0b000, 0b010),
    "?": (0b111, 0b001, 0b011, 0b000, 0b010),
    "/": (0b001, 0b001, 0b010, 0b100, 0b100),
    "x": (0b000, 0b101, 0b010, 0b101, 0b000),
    "<": (0b001, 0b010, 0b100, 0b010, 0b001),
    ">": (0b100, 0b010, 0b001, 0b010, 0b100),
    # bloque lleno: la barra de vida del jefe se dibuja repitiendolo
    "#": (0b111, 0b111, 0b111, 0b111, 0b111),
}

# Orden de los caracteres dentro del ROM S; el indice del tile es la posicion
# en esta cadena mas `FONT_FIRST_TILE`.
FONT_CHARS = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-.:!?/x<>#"
FONT_FIRST_TILE = 1     # el tile 0 del fix se deja en blanco


def font_glyph_pixels(char: str, color: int = 1) -> List[int]:
    """Dibuja un glifo 3x5 centrado en un tile de 8x8."""
    rows = FONT_3X5.get(char.upper() if char.upper() in FONT_3X5 else char)
    if rows is None:
        rows = FONT_3X5[" "]
    pixels = [0] * (FIX_PX * FIX_PX)
    for y, bits in enumerate(rows):
        for x in range(3):
            if (bits >> (2 - x)) & 1:
                pixels[(y + 1) * FIX_PX + (x + 2)] = color
    return pixels


def build_font(rom: RomData) -> Dict[str, int]:
    """Mete la fuente del HUD en el ROM S y devuelve caracter -> tile."""
    if rom.fix_tiles == 0:
        rom.add_fix_tile([0] * (FIX_PX * FIX_PX))   # tile 0 en blanco
    mapping: Dict[str, int] = {}
    for char in FONT_CHARS:
        mapping[char] = rom.add_fix_tile(font_glyph_pixels(char))
    return mapping


def hud_palette() -> Palette:
    """Paleta del plano fix: blanco, gris y amarillo para el marcador."""
    return Palette(name="hud", colors=[
        (255, 255, 255), (168, 168, 168), (248, 216, 72), (248, 96, 72),
    ])
