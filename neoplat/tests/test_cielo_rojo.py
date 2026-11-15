"""CIELO ROJO: el ejemplo de la bestia.

Un ejemplo del kit no es un adorno: es lo primero que abre quien lo prueba. Si
no carga, no compila o se queda sin tiles en una de las ocho maquinas, lo que
se lleva no es un juego, es un error. Asi que aqui se comprueba lo mismo que
se le pide a los otros dos ejemplos, y dos cosas mas que son propias de este:

  * que **las cuatro capas de parallax** esten en orden, de la mas lejana a la
    mas cercana y cada una mas rapida que la anterior. Es lo unico que hace
    que cuatro dibujos parezcan un paisaje, y se rompe sin que nadie se entere
    con solo cambiar un numero;
  * y que los dibujos que salen del kit -el cielo, las capas, el suelo, la
    espada y lo que se coge- sigan siendo **los que genera
    `tools/ngplat/art_bestia.py`**. El heroe y el guerrero de sombra no: esos
    vinieron de fuera, bajados de resolucion a mano, y eso se comprueba de
    otra manera (que quepan en la paleta, que es lo que los puede romper).
"""

import os
import unittest

from comun import KIT, cargar_demo

import sys
sys.path.insert(0, os.path.join(KIT, "tools"))

from ngplat import art_bestia, sistemas                      # noqa: E402
from ngplat.build import build_project                       # noqa: E402
from ngplat.png import read_png                              # noqa: E402
from ngplat.project import load_project                      # noqa: E402

EJEMPLO = os.path.join(KIT, "examples", "cielo-rojo")

# Los dibujos que vienen de fuera: no los genera el kit, asi que de estos se
# comprueba que quepan donde tienen que caber, no de donde salen.
DE_FUERA = ("graficos/heroe.png", "graficos/sombra.png")


class TestElProyectoCarga(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.project = load_project(EJEMPLO)
        cls.build = build_project(cls.project)

    def test_carga_sin_avisos(self):
        """Un ejemplo con avisos es un ejemplo que ensena a hacerlo mal."""
        self.assertEqual([], list(self.project.warnings))

    def test_el_heroe_es_del_doble_de_alto(self):
        """32x32 y no 16x16: es la tercera decision del estilo, y si alguien
        la toca sin querer el juego deja de parecerse a lo que imita."""
        self.assertEqual((32, 32), (self.project.player.frame_w,
                                    self.project.player.frame_h))

    def test_se_pega_y_no_se_pisa(self):
        """La fisica del genero, que es media gracia: aqui saltar encima de
        alguien no lo mata, te mata."""
        self.assertFalse(self.project.player.stomp)
        # `control_aire: 0.0` es la aceleracion en el aire: a cero, el salto
        # sale como sale y no se corrige a medio camino.
        self.assertEqual(0.0, self.project.player.air_accel)
        self.assertGreater(self.project.player.knockback, 0)


class TestLasCuatroCapas(unittest.TestCase):
    """El parallax, que es por lo que existe este ejemplo."""

    @classmethod
    def setUpClass(cls):
        cls.project = load_project(EJEMPLO)

    def test_son_cuatro_y_van_de_lejos_a_cerca(self):
        nombres = [c for c in self.project.levels[0].layers]
        self.assertEqual(["cielo", "montes", "bosque", "troncos"], nombres)

    def test_cada_capa_corre_mas_que_la_de_detras(self):
        """La diferencia entre velocidades **es** el efecto. Dos capas a la
        misma velocidad son una sola capa pintada dos veces."""
        capas = [self.project.layers[n] for n in self.project.levels[0].layers]
        velocidades = [c.speed_x for c in capas]
        for antes, despues in zip(velocidades, velocidades[1:]):
            self.assertLess(antes, despues,
                            "las capas van %s: alguna adelanta a la de delante"
                            % velocidades)
        self.assertLess(velocidades[0], 0.2, "el cielo casi no se mueve")
        self.assertLess(velocidades[-1], 1.0, "nada corre mas que el suelo")

    def test_las_capas_casan_consigo_mismas_al_repetirse(self):
        """Se pegan en bucle mientras el escenario se desliza: si la ultima
        columna no casa con la primera, se ve la costura cada vuelta."""
        for nombre in ("montes", "bosque", "troncos", "cielo"):
            with self.subTest(capa=nombre):
                im = read_png(os.path.join(EJEMPLO, "graficos",
                                           "%s.png" % nombre))
                distintas = sum(
                    1 for y in range(im.height)
                    if (im.get(0, y)[3] > 0) != (im.get(im.width - 1, y)[3] > 0))
                self.assertLessEqual(
                    distintas, 2,
                    "la capa '%s' no casa consigo misma: %d filas de costura"
                    % (nombre, distintas))


class TestLosDibujos(unittest.TestCase):

    def test_los_del_kit_siguen_siendo_los_del_kit(self):
        """Si alguien cambia `art_bestia.py`, el ejemplo se queda atras sin
        que nadie lo note. Esta prueba es la que avisa."""
        for nombre, imagen in art_bestia.todos().items():
            with self.subTest(dibujo=nombre):
                guardado = read_png(os.path.join(EJEMPLO, nombre))
                self.assertEqual((imagen.width, imagen.height),
                                 (guardado.width, guardado.height))
                distintos = sum(
                    1 for y in range(imagen.height) for x in range(imagen.width)
                    if imagen.get(x, y) != guardado.get(x, y))
                self.assertEqual(
                    0, distintos,
                    "'%s' ya no es el que genera art_bestia.py (%d pixeles "
                    "distintos): vuelve a generarlo" % (nombre, distintos))

    def test_todos_caben_en_una_paleta(self):
        """Quince colores mas el transparente. Es lo que hay en estas
        maquinas, y es lo que se rompe al traer un dibujo de fuera: los de
        fuera vienen con miles."""
        graficos = os.path.join(EJEMPLO, "graficos")
        for nombre in sorted(os.listdir(graficos)):
            with self.subTest(dibujo=nombre):
                im = read_png(os.path.join(graficos, nombre))
                colores = set()
                for y in range(im.height):
                    for x in range(im.width):
                        pixel = im.get(x, y)
                        if pixel[3]:
                            colores.add(pixel)
                self.assertLessEqual(len(colores), 15,
                                     "'%s' usa %d colores" % (nombre,
                                                              len(colores)))

    def test_los_de_fuera_estan_donde_se_dice(self):
        """La cabecera del game.yaml cuenta de donde salen los dos dibujos que
        no genera el kit. Si alguien los quita, la cabecera miente."""
        for nombre in DE_FUERA:
            self.assertTrue(os.path.isfile(os.path.join(EJEMPLO, nombre)),
                            "falta %s" % nombre)
        with open(os.path.join(EJEMPLO, "game.yaml"), encoding="utf-8") as fh:
            cabecera = fh.read()
        self.assertIn("sprites que trajo quien usa el kit", cabecera,
                      "el game.yaml ya no dice de donde salen los dibujos")


class TestCompilaParaLasOchoMaquinas(unittest.TestCase):
    """Que genere el proyecto en C para las ocho, que es lo que promete el kit.

    No se construye el binario aqui -eso lo hace la prueba de los generos, que
    necesita el compilador de 68000-: lo que se exige es que el ejemplo pase
    por el generador de cada maquina sin reventar y sin quedarse sin sitio.
    """

    def test_las_ocho(self):
        import shutil
        import tempfile
        from ngplat.codegen import generar_para_sistema

        tmp = tempfile.mkdtemp(prefix="neoplat-cielo-")
        self.addCleanup(shutil.rmtree, tmp, True)
        for sistema in sistemas.disponibles():
            with self.subTest(maquina=sistema.nombre):
                build = cargar_demo(EJEMPLO, sistema.nombre)
                salida = os.path.join(tmp, sistema.nombre)
                os.makedirs(salida, exist_ok=True)
                generar_para_sistema(build, salida, sistema, "202")
                self.assertTrue(os.path.isdir(os.path.join(salida, "src")))


if __name__ == "__main__":
    unittest.main()
