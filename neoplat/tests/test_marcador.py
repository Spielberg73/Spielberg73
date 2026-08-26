"""La barra de vida del jefe, que es lo unico del motor que fabrica texto.

La usan los marcadores de las cuatro maquinas, y un fallo ahi no lo pilla ni la
traza (no es simulacion) ni el emulador (el jefe del ejemplo esta en el segundo
nivel). Asi que se compila el motor de verdad y se mira lo que escribe.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

import comun  # noqa: F401  (pone tools/ en el path)
from comun import KIT, cargar_demo
from ngplat.codegen import copy_engine, generate_gamedata
from ngplat.scaffold import crear_proyecto


class TestBarraDelJefe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("gcc"):
            raise unittest.SkipTest("no hay gcc para compilar el motor")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-marcador-")
        proyecto = os.path.join(cls.tmp, "juego")
        crear_proyecto(proyecto, "BARRA", "TEST")
        build = cargar_demo(proyecto)
        out = os.path.join(cls.tmp, "build")
        os.makedirs(os.path.join(out, "src"))
        for relativo, contenido in generate_gamedata(build).items():
            with open(os.path.join(out, relativo), "w", encoding="utf-8") as fh:
                fh.write(contenido)
        copy_engine(out)
        binario = os.path.join(cls.tmp, "np_barra")
        hecho = subprocess.run(
            ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-I", os.path.join(out, "src"), "-o", binario,
             os.path.join(KIT, "engine", "host", "np_barra.c"),
             os.path.join(out, "src", "np_world.c"),
             os.path.join(out, "src", "gamedata.c")],
            capture_output=True, text=True)
        if hecho.returncode:
            raise AssertionError("no compila:\n" + hecho.stderr)
        salida = subprocess.run([binario], capture_output=True, text=True, check=True)
        cls.lineas = dict(
            (l.split(" ", 1)[0], l.split("[", 1)[1].rstrip("]"))
            for l in salida.stdout.strip().split("\n"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def test_sin_jefe_sale_en_blanco(self):
        """Asi la misma escritura borra lo que hubiera antes."""
        for caso in ("0/0", "0/5"):
            self.assertEqual(self.lineas[caso].strip(), "",
                             "con %s el marcador ensena algo" % caso)

    def test_a_tope_la_barra_esta_llena(self):
        for caso in ("5/5", "3/3", "1/1", "20/20"):
            self.assertEqual(self.lineas[caso], "BOSS " + "#" * 10, caso)

    def test_va_bajando(self):
        self.assertEqual(self.lineas["4/5"], "BOSS " + "#" * 8 + "  ")
        self.assertEqual(self.lineas["1/5"], "BOSS " + "#" * 2 + " " * 8)
        self.assertEqual(self.lineas["1/3"], "BOSS " + "#" * 4 + " " * 6)

    def test_mientras_le_quede_algo_se_ve_algo(self):
        """Con veinte golpes, uno solo seria medio bloque: se redondea hacia
        arriba para que la barra no desaparezca antes que el jefe."""
        self.assertEqual(self.lineas["1/20"], "BOSS " + "#" + " " * 9)
        self.assertEqual(self.lineas["19/20"], "BOSS " + "#" * 10)

    def test_siempre_ocupa_lo_mismo(self):
        """Ocupa siempre 15 caracteres: por eso al escribirla borra la anterior
        y el marcador no tiene que limpiar la fila."""
        for caso, texto in self.lineas.items():
            self.assertEqual(len(texto), 15, caso)


if __name__ == "__main__":
    unittest.main()
