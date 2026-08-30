"""Las pruebas del navegador, dentro de la bateria de siempre.

`tests/navegador.py` abre el preview en un Chromium de verdad y comprueba el
juego y el editor. Estaba solo en `make test-navegador`, asi que nadie lo
ejecutaba y se quedo desfasado: por ahi se colo que lo que dibujabas en el
editor no llegaba al juego. Aqui se ejecuta con las demas y, si no hay
Playwright o Chromium, se salta.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest

import comun
from comun import KIT

EJEMPLO = os.path.join(KIT, "examples", "bosque-magico")


def _hay_navegador() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    sys.path.insert(0, os.path.join(KIT, "tests"))
    import navegador
    return any(ruta and os.path.exists(ruta) for ruta in navegador.CHROMIUM_POSIBLES)


class TestNavegador(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _hay_navegador():
            raise unittest.SkipTest("no hay Playwright con Chromium instalado")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-navegador-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def _ejecutar(self, *args):
        resultado = subprocess.run(
            [sys.executable, os.path.join(KIT, "tests", "navegador.py")] + list(args),
            capture_output=True, text=True, cwd=KIT,
        )
        return resultado

    def test_el_juego_y_el_editor_en_un_navegador(self):
        preview = os.path.join(self.tmp, "preview.html")
        generado = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, %r);"
             "from ngplat.preview import write_preview;"
             "from ngplat.build import build_project;"
             "from ngplat.project import load_project;"
             "write_preview(build_project(load_project(%r)), %r)"
             % (os.path.join(KIT, "tools"), EJEMPLO, preview)],
            capture_output=True, text=True)
        self.assertEqual(generado.returncode, 0, generado.stderr)
        resultado = self._ejecutar(preview, os.path.join(self.tmp, "capturas"))
        self.assertEqual(resultado.returncode, 0,
                         resultado.stdout + resultado.stderr)
        # y que ha comprobado lo que dice comprobar
        for senal in ("lo dibujado llega al juego", "ranuras de animacion",
                      "animacion editada"):
            self.assertIn(senal, resultado.stdout,
                          "la prueba del navegador no ha llegado a '%s'" % senal)


if __name__ == "__main__":
    unittest.main()
