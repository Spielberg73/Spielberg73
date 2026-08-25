"""El editor del preview: logica, exportacion y vuelta al compilador.

La prueba que de verdad importa es el viaje de ida y vuelta: se edita el juego
con el editor (mapas, fisica, niveles nuevos), se exporta el game.yaml y se
vuelve a cargar y compilar. Si el editor escribiera algo que el kit no entiende,
o se dejara opciones por el camino, esto falla.
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
from ngplat.codegen import generate_gamedata
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
        cls.proyecto_editado = os.path.join(cls.tmp, "proyecto")
        shutil.copytree(EJEMPLO, cls.proyecto_editado)
        if os.path.isfile(cls.yaml_editado):
            shutil.copyfile(cls.yaml_editado,
                            os.path.join(cls.proyecto_editado, "game.yaml"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def test_pruebas_del_editor(self):
        self.assertEqual(self.resultado.returncode, 0,
                         "fallan pruebas del editor:\n" + self.resultado.stdout)
        self.assertIn("pruebas del editor", self.resultado.stdout)

    def test_el_preview_lleva_lo_que_necesita_el_editor(self):
        with open(self.datos, encoding="utf-8") as fh:
            datos = json.load(fh)
        self.assertIn("yaml", datos)
        self.assertIn("juego:", datos["yaml"])
        for llave in ("chars", "index", "kind", "gfx"):
            self.assertIn(llave, datos["tiles"])
        self.assertIn("campos", datos["claves"])
        self.assertIn("jugador", datos["claves"]["campos"])
        self.assertIn("rangos", datos["claves"])
        for nivel in datos["levels"]:
            self.assertEqual(len(nivel["rows"]), nivel["height"])
            self.assertEqual(len(nivel["rows"][0]), nivel["width"])
            self.assertIsInstance(nivel["spawn_chars"], dict)

    def test_el_yaml_editado_compila(self):
        editado = load_project(self.proyecto_editado)
        build = build_project(editado)
        generate_gamedata(build)          # tiene que poder generar el C
        self.assertEqual(editado.warnings, [])

    def test_los_cambios_llegan_al_yaml(self):
        editado = load_project(self.proyecto_editado)
        # el guion de tests/editor.js pinta, mueve la salida, cambia la fisica,
        # anade un nivel y crea un enemigo y un objeto
        self.assertEqual(editado.levels[0].rows[6][2:4], "==")
        self.assertEqual(editado.levels[0].start, (5, 9))
        self.assertEqual(editado.player.jump, 5.5)
        self.assertEqual(editado.lives, 4)
        self.assertEqual(len(editado.levels), len(self.original.levels) + 1)
        self.assertEqual(editado.levels[-1].name, "NIVEL DE PRUEBA")

    def test_los_actores_nuevos_llegan_al_yaml(self):
        editado = load_project(self.proyecto_editado)
        self.assertIn("fantasma", editado.enemies)
        fantasma = editado.enemies["fantasma"]
        self.assertEqual(fantasma.behavior, "chaser")
        self.assertEqual(fantasma.score, 300)
        self.assertEqual(fantasma.range, 120)
        self.assertEqual((fantasma.box_w, fantasma.box_h), (12, 11))
        # al reaprovechar un dibujo del proyecto, apunta a ese PNG
        self.assertTrue(os.path.isfile(os.path.join(self.proyecto_editado, fantasma.sprite)))

        self.assertIn("gema", editado.items)
        self.assertEqual(editado.items["gema"].effect, "health" if False else "life")
        self.assertEqual(editado.items["gema"].score, 50)

    def test_los_simbolos_nuevos_se_pueden_usar_en_los_mapas(self):
        editado = load_project(self.proyecto_editado)
        simbolos = {v: k for k, v in editado.levels[0].spawns.items()}
        self.assertIn("fantasma", simbolos)
        self.assertIn("gema", simbolos)
        # y son simbolos libres: no chocan con ningun tile
        self.assertNotIn(simbolos["fantasma"], editado.tiles)
        self.assertNotIn(simbolos["gema"], editado.tiles)

    def test_no_se_pierde_nada_de_lo_que_no_se_toca(self):
        editado = load_project(self.proyecto_editado)
        self.assertEqual(editado.title, self.original.title)
        self.assertEqual(editado.player.speed, self.original.player.speed)
        self.assertEqual(editado.player.gravity, self.original.player.gravity)
        # los que ya estaban siguen igual (ahora ademas hay enemigos nuevos)
        for nombre, enemigo in self.original.enemies.items():
            self.assertIn(nombre, editado.enemies)
            self.assertEqual(editado.enemies[nombre].speed, enemigo.speed)
            self.assertEqual(editado.enemies[nombre].behavior, enemigo.behavior)
        for nombre, objeto in self.original.items.items():
            self.assertIn(nombre, editado.items)
            self.assertEqual(editado.items[nombre].score, objeto.score)
        self.assertEqual(list(editado.layers), list(self.original.layers))
        self.assertEqual(list(editado.sound.efectos), list(self.original.sound.efectos))
        self.assertEqual(list(editado.sound.musica), list(self.original.sound.musica))
        self.assertEqual(editado.levels[1].rows, self.original.levels[1].rows)
        self.assertEqual(editado.levels[0].music, self.original.levels[0].music)

    def test_los_comentarios_sobreviven(self):
        """Ojo: una fila de suelo ('######') tambien empieza por '#'; solo
        cuentan como comentario las que llevan texto detras."""
        def comentarios(ruta):
            with open(ruta, encoding="utf-8") as fh:
                return [l.rstrip("\n") for l in fh
                        if l.strip().startswith("#") and " " in l.strip()]

        antes = comentarios(os.path.join(EJEMPLO, "game.yaml"))
        despues = comentarios(os.path.join(self.proyecto_editado, "game.yaml"))
        self.assertEqual(antes, despues)

    def test_el_nivel_nuevo_se_puede_terminar(self):
        """El nivel que crea el editor tiene que ser jugable de salida."""
        editado = load_project(self.proyecto_editado)
        datos = build_data(build_project(editado))
        for hoja in datos["sheets"].values():
            hoja["url"] = ""
        ruta = os.path.join(self.tmp, "datos-editado.json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(datos, fh)
        guion = (
            "const NP=require(%r);const B=require(%r);"
            "const d=JSON.parse(require('fs').readFileSync(%r,'utf8'));"
            "const r=B.jugar(NP,d,d.levels.length-1,{frames:6000});"
            "console.log(JSON.stringify(r));process.exit(r.ok?0:1);"
            % (os.path.join(KIT, "preview", "np_core.js"),
               os.path.join(KIT, "preview", "np_bot.js"), ruta)
        )
        resultado = subprocess.run(["node", "-e", guion], capture_output=True, text=True)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no termina el nivel nuevo: " + resultado.stdout)


if __name__ == "__main__":
    unittest.main()
