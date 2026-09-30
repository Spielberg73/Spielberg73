"""Escritor mínimo de PNG (RGB de 8 bits) sin dependencias."""

import struct
import zlib


def write_png(path, width, height, rgb_rows):
    """``rgb_rows``: lista de ``bytes``/``bytearray`` con width*3 bytes cada una."""
    raw = b"".join(b"\0" + bytes(r) for r in rgb_rows)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    return path


def read_png_rgb(path):
    """Lee un PNG RGB/RGBA de 8 bits sin entrelazar (para pruebas). Devuelve (w, h, filas)."""
    with open(path, "rb") as f:
        data = f.read()
    pos = 8
    idat = b""
    w = h = ctype = 0
    while pos < len(data):
        ln = struct.unpack_from(">I", data, pos)[0]
        tag = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack_from(">IIBB", body)
        elif tag == b"IDAT":
            idat += body
    bpp = 4 if ctype == 6 else 3
    raw = zlib.decompress(idat)
    rows, prev = [], bytearray(w * bpp)
    i = 0
    for _ in range(h):
        ft = raw[i]
        line = bytearray(raw[i + 1:i + 1 + w * bpp])
        i += 1 + w * bpp
        for x in range(len(line)):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if ft == 1:
                line[x] = (line[x] + a) & 0xFF
            elif ft == 2:
                line[x] = (line[x] + b) & 0xFF
            elif ft == 3:
                line[x] = (line[x] + ((a + b) >> 1)) & 0xFF
            elif ft == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        prev = line
        rows.append(bytes(line[j] for k in range(w) for j in (k * bpp, k * bpp + 1, k * bpp + 2)))
    return w, h, rows
