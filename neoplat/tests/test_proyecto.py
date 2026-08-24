"""Validacion de game.yaml: los errores deben ser claros y en su sitio."""

import os
import shutil
import tempfile
import unittest

import comun
from comun import MAPA_MINIMO, YAML_MINIMO, proyecto_minimo

from ngplat.build import build_project
from ngplat.errors import ProjectError
from ngplat.project import load_project


def _yaml_con_mapa(filas):
    return YAML_MINIMO % "\n".join("      " + f for f in filas)


class BaseProyecto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def cargar(self, texto=""):
        ruta = proyecto_minimo(self.tmp, texto)
        return load_project(ruta)

    def error(self, texto):
        with self.assertRaises(ProjectError) as ctx:
            self.cargar(texto)
        return ctx.exception


class TestValido(BaseProyecto):
    def test_carga_completa(self):
        proyecto = self.cargar()
        self.assertEqual(proyecto.title, "MINIMO")
        self.assertEqual(len(proyecto.levels), 1)
        self.assertEqual(proyecto.levels[0].start, (0, 12))
        self.assertIn("bicho", proyecto.enemies)
        self.assertIn("moneda", proyecto.items)

    def test_valores_por_defecto(self):
        proyecto = self.cargar()
        self.assertEqual(proyecto.lives, 3)
        self.assertTrue(proyecto.player.stomp)
        self.assertEqual(proyecto.player.box_w, 12)
        self.assertEqual(proyecto.player.box_h, 14)

    def test_claves_en_ingles(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")).replace(
            "juego:", "game:").replace("titulo:", "title:").replace(
            "jugador:", "player:").replace("niveles:", "levels:").replace(
            "nombre:", "name:").replace("mapa: |", "map: |").replace(
            "enemigos:", "enemies:").replace("objetos:", "items:").replace(
            "puntos:", "score:").replace("imagen:", "image:").replace(
            "leyenda:", "legend:").replace("tipo:", "type:").replace(
            "caja:", "hitbox:").replace("vacio", "empty").replace(
            "solido", "solid").replace("plataforma", "platform").replace("meta", "goal")
        proyecto = self.cargar(texto)
        self.assertEqual(proyecto.title, "MINIMO")
        self.assertEqual(proyecto.items["moneda"].score, 5)

    def test_funciona_sin_pyyaml(self):
        import ngplat.project as project_module

        original = __import__
        ruta = proyecto_minimo(self.tmp)

        def sin_yaml(nombre, *args, **kwargs):
            if nombre == "yaml":
                raise ImportError("simulado")
            return original(nombre, *args, **kwargs)

        import builtins
        builtins.__import__ = sin_yaml
        try:
            proyecto = project_module.load_project(ruta)
        finally:
            builtins.__import__ = original
        self.assertEqual(proyecto.title, "MINIMO")
        self.assertEqual(len(proyecto.levels[0].rows), 14)


class TestErrores(BaseProyecto):
    def test_sin_salida_del_jugador(self):
        filas = [f.replace("P", ".") for f in MAPA_MINIMO.split("\n")]
        error = self.error(_yaml_con_mapa(filas))
        self.assertIn("salida del jugador", error.message)
        self.assertIn("'P'", error.hint)

    def test_dos_salidas(self):
        filas = MAPA_MINIMO.split("\n")
        filas[12] = "P........P........G."
        error = self.error(_yaml_con_mapa(filas))
        self.assertIn("2 salidas", error.message)

    def test_simbolo_desconocido(self):
        filas = MAPA_MINIMO.split("\n")
        filas[10] = "....@..............."
        error = self.error(_yaml_con_mapa(filas))
        self.assertIn("'@'", error.message)
        self.assertIn("fila 11", error.message)
        self.assertIn("columna 5", error.message)

    def test_nivel_demasiado_pequeno(self):
        error = self.error(_yaml_con_mapa(["P..#", "####"]))
        self.assertIn("20 columnas", error.hint)

    def test_opcion_desconocida(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")).replace(
            "  sprite: h.png", "  sprite: h.png\n  velocidadd: 2")
        error = self.error(texto)
        self.assertIn("velocidadd", error.message)

    def test_seccion_desconocida(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")) + "\nmusica:\n  tema: x\n"
        error = self.error(texto)
        self.assertIn("musica", error.message)

    def test_archivo_que_falta(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")).replace("sprite: h.png",
                                                                "sprite: noexiste.png")
        error = self.error(texto)
        self.assertIn("noexiste.png", error.message)

    def test_frame_no_multiplo_de_16(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")).replace(
            "  caja: [12, 14]", "  frame: [12, 12]")
        error = self.error(texto)
        self.assertIn("16x16", error.message)

    def test_caja_mayor_que_el_frame(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")).replace(
            "  caja: [12, 14]", "  caja: [40, 40]")
        error = self.error(texto)
        self.assertIn("no cabe", error.message)

    def test_spawn_sin_definir(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")).replace("s: bicho", "s: dragon")
        error = self.error(texto)
        self.assertIn("dragon", error.message)

    def test_numero_de_tile_fuera_del_tileset(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")).replace(
            "'#': {tile: 1, tipo: solido}", "'#': {tile: 9, tipo: solido}")
        proyecto = load_project(proyecto_minimo(self.tmp, texto))
        with self.assertRaises(ProjectError) as ctx:
            build_project(proyecto)
        self.assertIn("solo tiene 2", ctx.exception.message)

    def test_animacion_con_fotograma_inexistente(self):
        texto = _yaml_con_mapa(MAPA_MINIMO.split("\n")).replace(
            "  caja: [12, 14]", "  animaciones:\n    correr: {frames: [0, 5]}")
        proyecto = load_project(proyecto_minimo(self.tmp, texto))
        with self.assertRaises(ProjectError) as ctx:
            build_project(proyecto)
        self.assertIn("fotograma 5", ctx.exception.message)

    def test_aviso_si_no_hay_meta(self):
        filas = [f.replace("G", ".") for f in MAPA_MINIMO.split("\n")]
        proyecto = self.cargar(_yaml_con_mapa(filas))
        self.assertTrue(any("meta" in aviso for aviso in proyecto.warnings))


if __name__ == "__main__":
    unittest.main()
