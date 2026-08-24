"""Los niveles de ejemplo tienen que poder terminarse.

Un bot que solo sabe andar a la derecha y saltar cuando ve un obstaculo juega
cada nivel de principio a fin. Si el bot no llega a la meta, el nivel pide
precision imposible o tiene una trampa injusta.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

import comun
from comun import KIT, cargar_demo

from ngplat.preview import build_data
from ngplat.project import load_project
from ngplat.scaffold import crear_proyecto

EJEMPLO = os.path.join(KIT, "examples", "bosque-magico")


def _datos(build, destino):
    datos = build_data(build)
    for hoja in datos["sheets"].values():
        hoja["url"] = ""
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(datos, fh)
    return destino


class TestNivelesJugables(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            self.skipTest("node no esta instalado")
        self.tmp = tempfile.mkdtemp(prefix="neoplat-niveles-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _jugar(self, proyecto):
        build = cargar_demo(proyecto)
        ruta = _datos(build, os.path.join(self.tmp, "datos.json"))
        resultado = subprocess.run(
            ["node", os.path.join(KIT, "tests", "nivel_jugable.js"), ruta],
            capture_output=True, text=True,
        )
        return resultado

    def test_ejemplo_del_kit(self):
        resultado = self._jugar(EJEMPLO)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el ejemplo:\n" + resultado.stdout)

    def test_proyecto_nuevo(self):
        destino = os.path.join(self.tmp, "juego")
        crear_proyecto(destino, "NUEVO", "TEST")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto recien creado:\n"
                         + resultado.stdout)

    def test_avisa_de_enemigos_sin_suelo(self):
        destino = os.path.join(self.tmp, "flotante")
        crear_proyecto(destino, "FLOTANTE", "TEST")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # colocamos una seta en el aire, en una fila vacia del primer nivel
        lineas = texto.split("\n")
        for i, linea in enumerate(lineas):
            if linea.strip() == "." * 48:
                lineas[i] = linea[:12] + "s" + linea[13:]
                break
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lineas))
        proyecto = load_project(ruta)
        self.assertTrue(any("no tiene suelo debajo" in aviso for aviso in proyecto.warnings),
                        proyecto.warnings)


if __name__ == "__main__":
    unittest.main()
