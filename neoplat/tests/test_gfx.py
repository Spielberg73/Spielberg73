"""Conversion de graficos al formato de la Neo Geo."""

import random
import unittest

import comun  # noqa: F401

from ngplat import gfx
from ngplat.errors import ProjectError
from ngplat.png import Image


class TestColor(unittest.TestCase):
    def test_extremos(self):
        self.assertEqual(gfx.ng_color((0, 0, 0)), 0x0000)
        self.assertEqual(gfx.ng_color((255, 255, 255)), 0xFFFF)

    def test_ida_y_vuelta_aproximada(self):
        for rgb in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (120, 130, 140), (17, 200, 33)]:
            vuelta = gfx.ng_color_to_rgb(gfx.ng_color(rgb))
            for original, obtenido in zip(rgb, vuelta):
                self.assertLessEqual(abs(original - obtenido), 5, rgb)

    def test_bits_de_canal(self):
        # El bit menos significativo de cada canal va a los bits 14/13/12.
        valor = gfx.ng_color((255, 0, 0))
        self.assertEqual((valor >> 8) & 0xF, 0xF)
        self.assertEqual((valor >> 14) & 1, 1)
        self.assertEqual(valor & 0xF, 0)


class TestTiles(unittest.TestCase):
    def test_sprite_ida_y_vuelta(self):
        random.seed(11)
        for _ in range(20):
            pixeles = [random.randrange(16) for _ in range(256)]
            c1, c2 = gfx.encode_sprite_tile(pixeles)
            self.assertEqual(len(c1), 64)
            self.assertEqual(len(c2), 64)
            self.assertEqual(gfx.decode_sprite_tile(c1, c2), pixeles)

    def test_fix_ida_y_vuelta(self):
        random.seed(12)
        for _ in range(20):
            pixeles = [random.randrange(16) for _ in range(64)]
            data = gfx.encode_fix_tile(pixeles)
            self.assertEqual(len(data), 32)
            self.assertEqual(gfx.decode_fix_tile(data), pixeles)

    def test_planos_separados(self):
        # Un tile con el indice 1 solo enciende el plano 0 (va entero a C1).
        c1, c2 = gfx.encode_sprite_tile([1] * 256)
        self.assertEqual(set(c1[:32]), {0xFF})
        self.assertEqual(set(c2), {0x00})

    def test_paleta_limitada_a_15_colores(self):
        pixeles = [(i * 7 % 256, i * 13 % 256, i * 29 % 256, 255) for i in range(20)]
        imagen = Image(20, 1, pixeles)
        with self.assertRaises(ProjectError) as ctx:
            gfx.build_palette(imagen, "prueba", "prueba.png")
        self.assertIn("15", str(ctx.exception))

    def test_transparente_es_el_indice_0(self):
        imagen = Image(2, 1, [(0, 0, 0, 0), (255, 0, 0, 255)])
        paleta, lookup = gfx.build_palette(imagen, "p", "p")
        indices = gfx.quantize(imagen, lookup)
        self.assertEqual(indices, [0, 1])
        self.assertEqual(paleta.words()[0] & 0x7FFF, 0)


class TestFuente(unittest.TestCase):
    def test_todos_los_glifos_caben_en_un_tile(self):
        for char in gfx.FONT_CHARS:
            pixeles = gfx.font_glyph_pixels(char)
            self.assertEqual(len(pixeles), 64)
            self.assertTrue(all(0 <= p <= 15 for p in pixeles))

    def test_la_fuente_entra_en_la_rom_s(self):
        rom = gfx.RomData()
        mapa = gfx.build_font(rom)
        self.assertEqual(rom.fix_tiles, len(gfx.FONT_CHARS) + 1)
        self.assertEqual(mapa["A"], gfx.FONT_CHARS.index("A") + gfx.FONT_FIRST_TILE)


if __name__ == "__main__":
    unittest.main()
