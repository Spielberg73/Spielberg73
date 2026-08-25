"""El editor del preview: logica y vuelta al game.yaml.

La prueba importante es el viaje de ida y vuelta: se edita un nivel con el
editor (en node, sin navegador), se exporta el game.yaml y se vuelve a cargar
con el compilador. Si el editor escribiera un YAML roto o perdiera opciones,
esto falla.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

import comun
from comun import KIT, cargar_demo

from ngplat.build import build_project
from ngplat.preview import build_data
from ngplat.project import load_project

EJEMPLO = os.path.join(KIT, "examples", "bosque-magico")


class TestEditor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("node no esta instalado")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-editor-")
        cls.original = load_project(EJEMPLO)
        datos = build_data(build_project(cls.original))
        for hoja in datos["sheets"].values():
            hoja["url"] = ""
        cls.datos = os.path.join(cls.tmp, "datos.json")
        with open(cls.datos, "w", encoding="utf-8") as fh:
            json.dump(datos, fh)
        cls.yaml_editado = os.path.join(cls.tmp, "editado.yaml")
        cls.resultado = subprocess.run(
            ["node", os.path.join(KIT, "tests", "editor.js"), cls.datos, cls.yaml_editado],
            capture_output=True, text=True,
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def test_pruebas_del_editor(self):
        self.assertEqual(self.resultado.returncode, 0,
                         "fallan pruebas del editor:\n" + self.resultado.stdout)

    def test_el_preview_lleva_lo_que_necesita_el_editor(self):
        with open(self.datos, encoding="utf-8") as fh:
            datos = json.load(fh)
        self.assertIn("yaml", datos)
        self.assertIn("juego:", datos["yaml"])
        self.assertIn("chars", datos["tiles"])
        self.assertIn("index", datos["tiles"])
        for nivel in datos["levels"]:
            self.assertEqual(len(nivel["rows"]), nivel["height"])
            self.assertEqual(len(nivel["rows"][0]), nivel["width"])
            self.assertIsInstance(nivel["spawn_chars"], dict)

    def test_el_yaml_editado_sigue_siendo_valido(self):
        destino = os.path.join(self.tmp, "proyecto")
        shutil.copytree(EJEMPLO, destino)
        shutil.copyfile(self.yaml_editado, os.path.join(destino, "game.yaml"))
        editado = load_project(destino)
        build_project(editado)          # tiene que compilar sin quejarse
        self.assertEqual(len(editado.levels), len(self.original.levels))

    def test_conserva_todo_lo_que_no_es_el_mapa(self):
        destino = os.path.join(self.tmp, "proyecto2")
        shutil.copytree(EJEMPLO, destino)
        shutil.copyfile(self.yaml_editado, os.path.join(destino, "game.yaml"))
        editado = load_project(destino)
        self.assertEqual(editado.title, self.original.title)
        self.assertEqual(editado.player.jump, self.original.player.jump)
        self.assertEqual(list(editado.enemies), list(self.original.enemies))
        self.assertEqual(list(editado.layers), list(self.original.layers))
        self.assertEqual(list(editado.sound.efectos), list(self.original.sound.efectos))
        self.assertEqual(list(editado.sound.musica), list(self.original.sound.musica))
        # el segundo nivel no se toco
        self.assertEqual(editado.levels[1].rows, self.original.levels[1].rows)

    def test_los_cambios_del_editor_llegan_al_yaml(self):
        destino = os.path.join(self.tmp, "proyecto3")
        shutil.copytree(EJEMPLO, destino)
        shutil.copyfile(self.yaml_editado, os.path.join(destino, "game.yaml"))
        editado = load_project(destino)
        # el editor pinto dos plataformas en la fila 6 y movio la salida
        self.assertEqual(editado.levels[0].rows[6][2:4], "==")
        self.assertEqual(editado.levels[0].start, (5, 9))
        self.assertNotEqual(editado.levels[0].start, self.original.levels[0].start)


if __name__ == "__main__":
    unittest.main()
