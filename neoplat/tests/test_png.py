"""Lectura y escritura de PNG sin dependencias externas."""

import struct
import unittest
import zlib

import comun  # noqa: F401

from ngplat import png


def _png_manual(color_type, depth, width, height, raw_rows, palette=None, trns=None):
    def chunk(tipo, cuerpo):
        return (struct.pack(">I", len(cuerpo)) + tipo + cuerpo
                + struct.pack(">I", zlib.crc32(tipo + cuerpo) & 0xFFFFFFFF))

    data = png.PNG_MAGIC
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color_type, 0, 0, 0))
    if palette:
        data += chunk(b"PLTE", b"".join(bytes(c) for c in palette))
    if trns:
        data += chunk(b"tRNS", bytes(trns))
    body = b"".join(b"\x00" + fila for fila in raw_rows)
    data += chunk(b"IDAT", zlib.compress(body))
    data += chunk(b"IEND", b"")
    return data


class TestPng(unittest.TestCase):
    def test_ida_y_vuelta_rgba(self):
        original = png.Image(3, 2, [
            (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255),
            (1, 2, 3, 0), (10, 20, 30, 255), (40, 50, 60, 255),
        ])
        vuelta = png.decode_png(png.encode_png(original))
        self.assertEqual(vuelta.width, 3)
        self.assertEqual(vuelta.height, 2)
        self.assertEqual(vuelta.get(0, 0), (255, 0, 0, 255))
        self.assertEqual(vuelta.get(2, 1), (40, 50, 60, 255))

    def test_paleta_con_transparencia(self):
        data = _png_manual(3, 8, 2, 1, [bytes([0, 1])],
                           palette=[(10, 20, 30), (40, 50, 60)], trns=[0, 255])
        imagen = png.decode_png(data)
        self.assertEqual(imagen.get(0, 0), (10, 20, 30, 0))
        self.assertEqual(imagen.get(1, 0), (40, 50, 60, 255))

    def test_rgb_sin_alfa(self):
        fila = bytes([255, 0, 0, 0, 255, 0])
        imagen = png.decode_png(_png_manual(2, 8, 2, 1, [fila]))
        self.assertEqual(imagen.get(1, 0), (0, 255, 0, 255))

    def test_gris_4_bits(self):
        imagen = png.decode_png(_png_manual(0, 4, 2, 1, [bytes([0x0F])]))
        self.assertEqual(imagen.get(0, 0)[0], 0)
        self.assertEqual(imagen.get(1, 0)[0], 255)

    def test_entrelazado_da_mensaje_util(self):
        data = bytearray(_png_manual(6, 8, 1, 1, [bytes([0, 0, 0, 255])]))
        data[28] = 1                           # byte de entrelazado dentro de IHDR
        cuerpo = bytes(data[16:29])
        data[29:33] = struct.pack(">I", zlib.crc32(b"IHDR" + cuerpo) & 0xFFFFFFFF)
        with self.assertRaises(png.PngError) as ctx:
            png.decode_png(bytes(data))
        self.assertIn("entrelazado", str(ctx.exception))

    def test_compatible_con_pillow(self):
        try:
            from PIL import Image as PilImage
        except ImportError:
            self.skipTest("Pillow no instalado")
        import io
        import random
        random.seed(3)
        pixeles = [(random.randrange(256), random.randrange(256), random.randrange(256),
                    random.choice([0, 255])) for _ in range(8 * 5)]
        pil = PilImage.new("RGBA", (8, 5))
        pil.putdata(pixeles)
        for modo in ("RGBA", "RGB", "P", "L"):
            buffer = io.BytesIO()
            pil.convert(modo).save(buffer, format="PNG")
            nuestro = png.decode_png(buffer.getvalue())
            crudo = pil.convert(modo).convert("RGBA").tobytes()
            suyo = [tuple(crudo[i:i + 4]) for i in range(0, len(crudo), 4)]
            self.assertEqual(nuestro.pixels, suyo, "modo %s" % modo)


if __name__ == "__main__":
    unittest.main()
