"""Pruebas de jugabilidad: se ejecutan con node sobre el motor del preview.

El motor en JavaScript y el motor en C son equivalentes (lo comprueba
test_paridad.py), asi que estas pruebas valen para los dos.
"""

import os
import shutil
import subprocess
import unittest

import comun
from comun import KIT


class TestJugabilidad(unittest.TestCase):
    def test_comportamiento(self):
        if not shutil.which("node"):
            self.skipTest("node no esta instalado")
        resultado = subprocess.run(
            ["node", os.path.join(KIT, "tests", "comportamiento.js")],
            capture_output=True, text=True,
        )
        self.assertEqual(resultado.returncode, 0,
                         "fallan pruebas de jugabilidad:\n" + resultado.stdout)
        self.assertIn("pruebas de jugabilidad", resultado.stdout)


if __name__ == "__main__":
    unittest.main()
