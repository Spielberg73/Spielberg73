"""Las piezas del X68000 que no necesitan la maquina: color, PCG y ejecutable.

El motor en C se comprueba compilandolo (test_sistemas) y en el emulador
(tests/emulador_x68000.py, que necesita las ROMs de Sharp). Lo de aqui es lo
que se puede mirar en seco.
"""

import struct
import unittest

import comun  # noqa: F401  (pone tools/ en el path)

from ngplat.art import PALETA as PALETA_BOSQUE
from ngplat.art_hierro import PALETA as PALETA_HIERRO
from ngplat.gfx_x68k import (PATRON_BYTES, codificar_patron, decodificar_patron,
                             x68k_color, x68k_color_a_rgb)
from ngplat.x68k import ErrorX, tabla_de_correcciones


class TestColor(unittest.TestCase):
    """El color del X68000 es GRBi: cinco bits por canal y un bit de intensidad
    que es el LSB **de los tres a la vez**."""

    def test_el_negro_y_el_blanco_salen_exactos(self):
        self.assertEqual(x68k_color((0, 0, 0)), 0x0000)
        self.assertEqual(x68k_color_a_rgb(x68k_color((255, 255, 255))),
                         (255, 255, 255))

    def test_cada_canal_va_en_su_sitio(self):
        """Si se cambiaran de sitio el verde y el rojo, el juego saldria con los
        colores permutados y todo lo demas seguiria funcionando."""
        self.assertEqual(x68k_color((255, 0, 0)) & 0xF800, 0)     # nada en verde
        self.assertEqual(x68k_color((0, 255, 0)) & 0x07C0, 0)     # nada en rojo
        self.assertEqual(x68k_color((0, 0, 255)) & 0xF800, 0)
        rojo = x68k_color_a_rgb(x68k_color((255, 0, 0)))
        self.assertGreater(rojo[0], 240)
        self.assertEqual(rojo[1:], (0, 0))

    def test_las_paletas_del_kit_sobreviven(self):
        """Cinco bits por canal no dan los 256 niveles, asi que algo se pierde:
        lo que se comprueba es **cuanto**. Cuatro de 255 no se ve; si un cambio
        lo empeorara, aqui se nota."""
        peor = 0
        for paleta in (PALETA_BOSQUE, PALETA_HIERRO):
            for nombre, rgb in paleta.items():
                vuelta = x68k_color_a_rgb(x68k_color(rgb[:3]))
                error = max(abs(a - b) for a, b in zip(vuelta, rgb[:3]))
                self.assertLessEqual(error, 4, "%s: %s -> %s" % (nombre, rgb[:3], vuelta))
                peor = max(peor, error)
        self.assertGreater(peor, 0, "no se pierde nada: la prueba no vale")

    def test_el_bit_de_intensidad_se_usa(self):
        """Es lo unico raro de este formato: si se ignorara, los colores claros
        saldrian medio nivel por debajo y el blanco no seria blanco."""
        self.assertEqual(x68k_color((255, 255, 255)) & 1, 1)


class TestPatrones(unittest.TestCase):
    """Un patron de PCG son 16x16 pixeles en 128 bytes: cuatro cuadrantes de
    8x8 en orden de lectura, dos pixeles por byte."""

    def _damero(self):
        return [(x + y * 16) % 16 for y in range(16) for x in range(16)]

    def test_mide_lo_que_tiene_que_medir(self):
        self.assertEqual(len(codificar_patron(self._damero())), PATRON_BYTES)

    def test_ida_y_vuelta(self):
        px = self._damero()
        self.assertEqual(decodificar_patron(codificar_patron(px)), px)

    def test_el_nibble_alto_es_el_pixel_de_la_izquierda(self):
        px = [0] * 256
        px[0] = 0xA           # (0,0)
        px[1] = 0x5           # (1,0)
        self.assertEqual(codificar_patron(px)[0], 0xA5)

    def test_los_cuadrantes_van_en_orden_de_lectura(self):
        """Arriba-izquierda, arriba-derecha, abajo-izquierda, abajo-derecha. Con
        otro orden los sprites saldrian troceados, y eso solo se ve en el
        emulador: aqui se fija el contrato."""
        for indice, (x, y) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
            px = [0] * 256
            px[y * 16 + x] = 0xF
            datos = codificar_patron(px)
            self.assertEqual(datos[indice * 32], 0xF0,
                             "el cuadrante %d no esta donde toca" % indice)

    def test_un_patron_que_no_es_de_16x16_no_cuela(self):
        with self.assertRaises(ValueError):
            codificar_patron([0] * 100)


class TestEjecutable(unittest.TestCase):
    """La tabla de correcciones del .X va por saltos desde la anterior, y un
    salto que no cabe en una palabra se anuncia con un 1."""

    def test_sin_correcciones_no_hay_tabla(self):
        self.assertEqual(tabla_de_correcciones([]), b"")

    def test_los_saltos_son_desde_la_anterior(self):
        tabla = tabla_de_correcciones([4, 10, 20])
        self.assertEqual(tabla, struct.pack(">3H", 4, 6, 10))

    def test_un_salto_largo_se_anuncia_con_un_uno(self):
        tabla = tabla_de_correcciones([4, 0x20000])
        self.assertEqual(tabla, struct.pack(">H", 4) + struct.pack(">HI", 1, 0x20000 - 4))

    def test_van_ordenadas_aunque_lleguen_revueltas(self):
        self.assertEqual(tabla_de_correcciones([20, 4, 10]),
                         tabla_de_correcciones([4, 10, 20]))

    def test_una_correccion_impar_no_cuela(self):
        """El 68000 no puede leer una palabra larga en una direccion impar: si
        se colara, la maquina se para con un error de direccion."""
        with self.assertRaises(ErrorX):
            tabla_de_correcciones([4, 7])


if __name__ == "__main__":
    unittest.main()
