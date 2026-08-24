"""Lector/escritor PNG en Python puro (solo usa zlib de la stdlib).

Soporta lo que necesita un proyecto de pixel art:
  - lectura: 8 bits por canal, tipos 0 (gris), 2 (RGB), 3 (paleta), 4 (gris+alfa)
    y 6 (RGBA), sin entrelazado, con trozo tRNS opcional.
  - escritura: RGBA de 8 bits.

La imagen se representa como `Image`, con los pixeles en una lista plana de
tuplas (r, g, b, a).
"""

from __future__ import annotations

import struct
import zlib
from typing import List, Tuple

RGBA = Tuple[int, int, int, int]

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class PngError(Exception):
    """Error de formato al leer o escribir un PNG."""


class Image:
    __slots__ = ("width", "height", "pixels")

    def __init__(self, width: int, height: int, pixels: List[RGBA]):
        if len(pixels) != width * height:
            raise PngError(
                "numero de pixeles incoherente: %d para %dx%d"
                % (len(pixels), width, height)
            )
        self.width = width
        self.height = height
        self.pixels = pixels

    def get(self, x: int, y: int) -> RGBA:
        return self.pixels[y * self.width + x]

    def set(self, x: int, y: int, value: RGBA) -> None:
        self.pixels[y * self.width + x] = value

    def crop(self, x: int, y: int, w: int, h: int) -> "Image":
        if x < 0 or y < 0 or x + w > self.width or y + h > self.height:
            raise PngError(
                "recorte fuera de la imagen: (%d,%d %dx%d) en %dx%d"
                % (x, y, w, h, self.width, self.height)
            )
        out: List[RGBA] = []
        for row in range(y, y + h):
            start = row * self.width + x
            out.extend(self.pixels[start:start + w])
        return Image(w, h, out)

    def colors(self) -> List[RGBA]:
        """Colores unicos en orden de primera aparicion (alfa 0 normalizado)."""
        seen = {}
        for px in self.pixels:
            key = (0, 0, 0, 0) if px[3] == 0 else px
            if key not in seen:
                seen[key] = None
        return list(seen.keys())


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> bytes:
    stride = width * bpp
    out = bytearray(stride * height)
    pos = 0
    for y in range(height):
        ftype = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if len(line) != stride:
            raise PngError("datos de imagen truncados en la fila %d" % y)
        base = y * stride
        prev = base - stride
        if ftype == 0:
            pass
        elif ftype == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ftype == 2:
            if y > 0:
                for i in range(stride):
                    line[i] = (line[i] + out[prev + i]) & 0xFF
        elif ftype == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up = out[prev + i] if y > 0 else 0
                line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
        elif ftype == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up = out[prev + i] if y > 0 else 0
                ul = out[prev + i - bpp] if (y > 0 and i >= bpp) else 0
                line[i] = (line[i] + _paeth(left, up, ul)) & 0xFF
        else:
            raise PngError("filtro PNG desconocido: %d" % ftype)
        out[base:base + stride] = line
    return bytes(out)


def _expand_bits(data: bytes, width: int, height: int, depth: int) -> List[int]:
    """Expande filas de 1/2/4 bits a un valor por pixel."""
    per_byte = 8 // depth
    mask = (1 << depth) - 1
    stride = (width + per_byte - 1) // per_byte
    values: List[int] = []
    for y in range(height):
        row = data[y * stride:(y + 1) * stride]
        count = 0
        for byte in row:
            for k in range(per_byte):
                if count >= width:
                    break
                shift = 8 - depth * (k + 1)
                values.append((byte >> shift) & mask)
                count += 1
    return values


def read_png(path: str) -> Image:
    with open(path, "rb") as fh:
        data = fh.read()
    return decode_png(data, path)


def decode_png(data: bytes, path: str = "<memoria>") -> Image:
    if not data.startswith(PNG_MAGIC):
        raise PngError("%s no es un PNG valido" % path)
    pos = len(PNG_MAGIC)
    idat = bytearray()
    palette: List[Tuple[int, int, int]] = []
    trns = b""
    width = height = depth = color_type = 0
    interlace = 0
    seen_ihdr = False
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length  # cabecera + cuerpo + CRC
        if ctype == b"IHDR":
            width, height, depth, color_type, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", body
            )
            seen_ihdr = True
        elif ctype == b"PLTE":
            palette = [tuple(body[i:i + 3]) for i in range(0, len(body), 3)]
        elif ctype == b"tRNS":
            trns = bytes(body)
        elif ctype == b"IDAT":
            idat.extend(body)
        elif ctype == b"IEND":
            break
    if not seen_ihdr:
        raise PngError("%s: falta la cabecera IHDR" % path)
    if interlace:
        raise PngError(
            "%s: PNG entrelazado no soportado; vuelve a guardarlo sin entrelazado"
            % path
        )
    if depth == 16:
        raise PngError("%s: PNG de 16 bits por canal no soportado" % path)
    if color_type not in (0, 2, 3, 4, 6):
        raise PngError("%s: tipo de color PNG no soportado: %d" % (path, color_type))

    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    raw = zlib.decompress(bytes(idat))
    if depth == 8:
        bpp = channels
        flat = _unfilter(raw, width, height, bpp)
        samples = list(flat)
    else:
        # Solo los tipos con un canal pueden tener menos de 8 bits.
        stride_bytes = (width * depth + 7) // 8
        flat = _unfilter(raw, stride_bytes, height, 1)
        samples = _expand_bits(flat, width, height, depth)
        bpp = 1

    pixels: List[RGBA] = []
    if color_type == 3:
        if not palette:
            raise PngError("%s: imagen con paleta pero sin trozo PLTE" % path)
        for idx in samples:
            if idx >= len(palette):
                raise PngError("%s: indice de paleta fuera de rango: %d" % (path, idx))
            r, g, b = palette[idx]
            a = trns[idx] if idx < len(trns) else 255
            pixels.append((r, g, b, a))
    elif color_type == 0:
        maxv = (1 << depth) - 1
        key = struct.unpack(">H", trns)[0] if len(trns) == 2 else None
        for v in samples:
            g = v * 255 // maxv
            pixels.append((g, g, g, 0 if key is not None and v == key else 255))
    elif color_type == 4:
        for i in range(0, len(samples), 2):
            g = samples[i]
            pixels.append((g, g, g, samples[i + 1]))
    elif color_type == 2:
        key = None
        if len(trns) == 6:
            key = tuple(struct.unpack(">HHH", trns))
        for i in range(0, len(samples), 3):
            r, g, b = samples[i], samples[i + 1], samples[i + 2]
            a = 0 if key is not None and (r, g, b) == key else 255
            pixels.append((r, g, b, a))
    else:  # RGBA
        for i in range(0, len(samples), 4):
            pixels.append(
                (samples[i], samples[i + 1], samples[i + 2], samples[i + 3])
            )
    return Image(width, height, pixels)


def _chunk(ctype: bytes, body: bytes) -> bytes:
    return (
        struct.pack(">I", len(body))
        + ctype
        + body
        + struct.pack(">I", zlib.crc32(ctype + body) & 0xFFFFFFFF)
    )


def encode_png(image: Image) -> bytes:
    raw = bytearray()
    for y in range(image.height):
        raw.append(0)  # filtro "none": el pixel art comprime bien igualmente
        for px in image.pixels[y * image.width:(y + 1) * image.width]:
            raw.extend(px)
    body = (
        PNG_MAGIC
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    return body


def write_png(path: str, image: Image) -> None:
    with open(path, "wb") as fh:
        fh.write(encode_png(image))
