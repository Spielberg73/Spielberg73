"""El motor en C y el preview en JavaScript deben dar el mismo resultado.

Se ejecutan los dos con la misma secuencia de pulsaciones y se comparan las
trazas frame a frame: posicion, velocidad, camara, estado, puntos y un hash de
todas las entidades. Si alguien toca solo una de las dos implementaciones,
esta prueba lo detecta.
"""

import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest

import comun
from comun import KIT, cargar_demo

from ngplat.codegen import copy_engine, generate_gamedata
from ngplat.preview import build_data
from ngplat.scaffold import crear_proyecto

IN_LEFT, IN_RIGHT, IN_DOWN, IN_JUMP, IN_START = 1, 2, 8, 16, 64
FRAMES = 3000


def _secuencia(semilla: int):
    """Pulsaciones pseudoaleatorias, iguales para las dos implementaciones."""
    rng = random.Random(semilla)
    entradas = [IN_START, IN_START, 0]
    estado = 0
    for i in range(FRAMES):
        if i % 23 == 0:
            estado = rng.choice([IN_RIGHT, IN_RIGHT, IN_RIGHT | IN_JUMP, IN_LEFT,
                                 IN_LEFT | IN_JUMP, IN_JUMP, IN_DOWN, 0, IN_START])
        entradas.append(estado)
    return entradas


class TestParidad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("gcc"):
            raise unittest.SkipTest("no hay gcc para compilar el motor")
        if not shutil.which("node"):
            raise unittest.SkipTest("no hay node para ejecutar el preview")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-paridad-")
        # Se comprueban los dos modos de camara: con scroll y pantalla a
        # pantalla la simulacion es la misma, pero la camara no, y la camara va
        # en la traza.
        cls.variantes = {}
        for camara in ("scroll", "pantallas"):
            cls.variantes[camara] = cls._preparar(camara)

    @classmethod
    def _preparar(cls, camara):
        proyecto_dir = os.path.join(cls.tmp, "juego-" + camara)
        crear_proyecto(proyecto_dir, "PARIDAD", "TEST")
        yaml = os.path.join(proyecto_dir, "game.yaml")
        with open(yaml, encoding="utf-8") as fh:
            texto = fh.read()
        # el andamiaje ya trae 'camara: scroll': hay que cambiar esa linea, no
        # anadir otra, o el lector se queda con la ultima
        assert "  camara: scroll" in texto, "el andamiaje ya no trae la camara"
        with open(yaml, "w", encoding="utf-8") as fh:
            fh.write(texto.replace("  camara: scroll", "  camara: " + camara, 1))
        build = cargar_demo(proyecto_dir)

        out = os.path.join(cls.tmp, "build-" + camara)
        os.makedirs(os.path.join(out, "src"))
        for relativo, contenido in generate_gamedata(build).items():
            with open(os.path.join(out, relativo), "w", encoding="utf-8") as fh:
                fh.write(contenido)
        copy_engine(out)

        datos = build_data(build)
        for hoja in datos["sheets"].values():
            hoja["url"] = ""            # la traza no necesita los graficos
        datos_json = os.path.join(cls.tmp, "datos-%s.json" % camara)
        with open(datos_json, "w", encoding="utf-8") as fh:
            json.dump(datos, fh)

        binario = os.path.join(cls.tmp, "np_trace-" + camara)
        compilacion = subprocess.run(
            ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-I", os.path.join(out, "src"), "-o", binario,
             os.path.join(KIT, "engine", "host", "np_trace.c"),
             os.path.join(out, "src", "np_world.c"),
             os.path.join(out, "src", "gamedata.c")],
            capture_output=True, text=True,
        )
        if compilacion.returncode != 0:
            raise AssertionError("el motor en C no compila:\n" + compilacion.stderr)
        return (binario, datos_json)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def _trazas(self, semilla, camara="scroll"):
        binario, datos_json = self.variantes[camara]
        entradas = _secuencia(semilla)
        ruta = os.path.join(self.tmp, "inputs-%d.txt" % semilla)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("\n".join(str(v) for v in entradas))
        traza_c = subprocess.run([binario, ruta], capture_output=True, text=True, check=True)
        traza_js = subprocess.run(
            ["node", os.path.join(KIT, "tests", "trace.js"), datos_json, ruta],
            capture_output=True, text=True, check=True,
        )
        return traza_c.stdout.strip().split("\n"), traza_js.stdout.strip().split("\n")

    def test_misma_traza(self):
        for camara in ("scroll", "pantallas"):
            for semilla in (1, 7, 99):
                self._comparar(camara, semilla)

    def _comparar(self, camara, semilla):
        if True:
            lineas_c, lineas_js = self._trazas(semilla, camara)
            self.assertEqual(len(lineas_c), len(lineas_js))
            for i, (a, b) in enumerate(zip(lineas_c, lineas_js)):
                if a != b:
                    self.fail(
                        "camara %s, semilla %d, frame %d:\n  C : %s\n  JS: %s\n"
                        "(columnas: frame x y vx vy estado salud vidas puntos camx camy nivel hash)"
                        % (camara, semilla, i + 1, a, b)
                    )

    def test_las_dos_camaras_no_dan_lo_mismo(self):
        """Si el modo de camara no llegara al motor, las dos trazas saldrian
        identicas y la prueba de paridad pasaria sin comprobar nada."""
        con_scroll, _ = self._trazas(1, "scroll")
        con_pantallas, _ = self._trazas(1, "pantallas")
        camaras_scroll = {l.split()[9] for l in con_scroll}
        camaras_pantallas = {l.split()[9] for l in con_pantallas}
        self.assertNotEqual(camaras_scroll, camaras_pantallas,
                            "las dos camaras dan el mismo recorrido")
        # con pantallas la camara solo se para en multiplos del ancho de pantalla
        # (o pegada al final del nivel)
        for valor in camaras_pantallas:
            x = int(valor)
            self.assertTrue(x % 320 == 0 or x == max(int(v) for v in camaras_pantallas),
                            "la camara por pantallas se ha parado en %d" % x)

    def test_la_traza_tiene_contenido(self):
        lineas_c, _ = self._trazas(1)
        self.assertGreater(len(lineas_c), FRAMES)
        estados = {linea.split()[5] for linea in lineas_c}
        self.assertIn("1", estados, "el jugador nunca llega a jugar")
        posiciones = {linea.split()[1] for linea in lineas_c}
        self.assertGreater(len(posiciones), 50, "el jugador no se mueve")


if __name__ == "__main__":
    unittest.main()
