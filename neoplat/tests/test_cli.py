"""La orden `ngplat` de principio a fin."""

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

import comun
from comun import KIT

from ngplat.cli import main


class TestCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-cli-")
        self.proyecto = os.path.join(self.tmp, "juego")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ejecutar(self, *args):
        salida = io.StringIO()
        with redirect_stdout(salida), redirect_stderr(salida):
            codigo = main(list(args))
        return codigo, salida.getvalue()

    def test_flujo_completo(self):
        codigo, salida = self._ejecutar("nuevo", self.proyecto, "--titulo", "CLI")
        self.assertEqual(codigo, 0, salida)
        self.assertTrue(os.path.isfile(os.path.join(self.proyecto, "game.yaml")))

        codigo, salida = self._ejecutar("comprobar", self.proyecto)
        self.assertEqual(codigo, 0, salida)
        self.assertIn("niveles", salida)

        codigo, salida = self._ejecutar("probar", self.proyecto, "--no-abrir")
        self.assertEqual(codigo, 0, salida)
        self.assertTrue(os.path.isfile(os.path.join(self.proyecto, "preview.html")))

        codigo, salida = self._ejecutar("compilar", self.proyecto)
        self.assertEqual(codigo, 0, salida)
        for esperado in ("build/src/gamedata.c", "build/Makefile", "build/rom/202-c1.c1"):
            self.assertTrue(os.path.isfile(os.path.join(self.proyecto, esperado)), esperado)

    def test_alias_en_ingles(self):
        self.assertEqual(self._ejecutar("new", self.proyecto)[0], 0)
        self.assertEqual(self._ejecutar("check", self.proyecto)[0], 0)
        self.assertEqual(self._ejecutar("build", self.proyecto)[0], 0)

    def test_no_pisa_una_carpeta_con_contenido(self):
        os.makedirs(self.proyecto)
        with open(os.path.join(self.proyecto, "algo.txt"), "w") as fh:
            fh.write("importante")
        codigo, salida = self._ejecutar("nuevo", self.proyecto)
        self.assertEqual(codigo, 2)
        self.assertIn("ya existe", salida)

    def test_error_sin_traza_de_python(self):
        codigo, salida = self._ejecutar("comprobar", os.path.join(self.tmp, "vacio"))
        self.assertEqual(codigo, 2)
        self.assertIn("error", salida)
        self.assertNotIn("Traceback", salida)


if __name__ == "__main__":
    unittest.main()
