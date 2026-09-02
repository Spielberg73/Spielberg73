"""Los niveles de ejemplo tienen que poder terminarse.

Un bot juega cada nivel de principio a fin: de lado anda a la derecha y salta
cuando ve un obstaculo, y desde arriba busca el camino hasta la meta y sube
disparando. Si el bot no llega a la meta, el nivel pide precision imposible o
tiene una trampa injusta.
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

    def test_el_proyecto_de_castlevania_tambien_se_termina(self):
        """El genero de latigo cambia la fisica entera -sin correccion del
        salto, sin pisar enemigos y con escaleras- asi que su nivel de partida
        hay que comprobarlo aparte: el bot no sabe subir escaleras, y si el
        camino dependiera de una no habria forma de pasar."""
        destino = os.path.join(self.tmp, "castillo")
        crear_proyecto(destino, "CASTILLO", "TEST", genero="castlevania")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto de castlevania:\n"
                         + resultado.stdout)

    def test_el_proyecto_de_comando_tambien_se_termina(self):
        """El genero de comando se ve desde arriba y se juega subiendo, asi que
        el bot que anda hacia la derecha no vale: hay otro que busca el camino
        hasta la meta. Sus dos niveles tienen que poder terminarse."""
        destino = os.path.join(self.tmp, "comando")
        crear_proyecto(destino, "COMANDO", "TEST", genero="comando")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto de comando:\n"
                         + resultado.stdout)

    def test_avisa_cuando_el_camino_de_arriba_esta_cortado(self):
        """Y lo contrario: si un nivel cenital se queda sin paso, el bot tiene
        que decir que no hay camino, no soltar un 'no llega a tiempo' que no
        explica nada. Aqui cerramos una fila entera con sacos terreros."""
        destino = os.path.join(self.tmp, "comando-cortado")
        crear_proyecto(destino, "CORTADO", "TEST", genero="comando")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        fila = "AA.,,,,,g,,,,,,,.AAA"
        assert fila in texto, "el nivel de comando ya no tiene esa fila"
        texto = texto.replace(fila, "#" * len(fila), 1)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "el bot dice que sube por un nivel tapiado")
        self.assertIn("no hay camino", resultado.stdout, resultado.stdout)

    def test_avisa_cuando_la_llave_no_esta_en_el_camino(self):
        """El bot solo anda hacia la derecha. Si la llave que abre la meta esta
        donde el no llega, tiene que decirlo con esas palabras y no soltar un
        'se queda atascado' que no explica nada."""
        destino = os.path.join(self.tmp, "llave-lejos")
        crear_proyecto(destino, "LLAVE", "TEST")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # la llave del andamiaje esta en el camino: se sube a la plataforma
        # mas alta, donde el bot no llega
        assert "^...k" in texto, "el andamiaje ya no pone la llave asi"
        texto = texto.replace("^...k", "^....", 1)
        texto = texto.replace("      ..............................ccc",
                              "      ..............................ckc", 1)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "el bot dice que llega a una meta cerrada")
        self.assertIn("le faltan llaves", resultado.stdout, resultado.stdout)

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
