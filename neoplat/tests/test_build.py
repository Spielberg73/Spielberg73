"""Del game.yaml al proyecto en C: empaquetado, generacion y compilacion."""

import os
import shutil
import subprocess
import tempfile
import unittest

import comun
from comun import ProyectoTemporal, cargar_demo

from ngplat import gfx
from ngplat import sistemas
from ngplat.codegen import generar_para_sistema, generate_gamedata
from ngplat.preview import build_data, render_html
from ngplat.project import TILE_KIND_ID, load_project


class TestEmpaquetado(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-build-")
        cls.proyecto_dir = os.path.join(cls.tmp, "juego")
        from ngplat.scaffold import crear_proyecto
        crear_proyecto(cls.proyecto_dir, "PRUEBA", "TEST")
        cls.build = cargar_demo(cls.proyecto_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_cuenta_de_tiles(self):
        total = len(self.build.tileset.tiles)
        for actor in self.build.actor_builds():
            total += len(actor.sheet.tiles)
        for capa in self.build.layers:      # las capas comparten tiles repetidos
            total += capa.frames
        self.assertEqual(self.build.rom.sprite_tiles, total)
        self.assertEqual(len(self.build.rom.c1), total * gfx.SPRITE_TILE_BYTES)
        self.assertEqual(len(self.build.rom.c2), total * gfx.SPRITE_TILE_BYTES)

    def test_tiles_no_se_solapan(self):
        rangos = []
        for actor in self.build.actor_builds():
            inicio = actor.sheet.first_tile
            rangos.append((inicio, inicio + len(actor.sheet.tiles)))
        rangos.sort()
        for (_, fin), (inicio, _) in zip(rangos, rangos[1:]):
            self.assertLessEqual(fin, inicio, "dos actores comparten tiles")

    def test_tabla_de_tiles(self):
        tipos = {t.char: t.kind for t in self.build.tiles}
        self.assertEqual(tipos["#"], "solid")
        self.assertEqual(tipos["="], "platform")
        self.assertEqual(tipos["^"], "hazard")
        self.assertEqual(tipos["G"], "goal")

    def test_spawns_apoyados_en_el_suelo(self):
        nivel = self.build.levels[0]
        self.assertTrue(nivel.spawns)
        for x, y, kind, index in nivel.spawns:
            actor = (self.build.enemies if kind == 0 else self.build.items)[index].actor
            self.assertEqual((y + actor.box_h) % 16, 0,
                             "la entidad no queda apoyada en la rejilla de tiles")
            self.assertGreaterEqual(x, 0)

    def test_salida_del_jugador(self):
        nivel = self.build.levels[0]
        jugador = self.build.project.player
        self.assertEqual((nivel.start[1] + jugador.box_h) % 16, 0)

    def test_celdas_coinciden_con_el_mapa(self):
        nivel = self.build.levels[0]
        filas = self.build.project.levels[0].rows
        self.assertEqual(len(nivel.cells), nivel.width * nivel.height)
        indice = self.build.tile_index
        for y, fila in enumerate(filas):
            for x, char in enumerate(fila):
                celda = nivel.cells[y * nivel.width + x]
                if char in ("P",) or char in self.build.project.levels[0].spawns:
                    self.assertEqual(celda, indice["."])
                else:
                    self.assertEqual(celda, indice[char])

    def test_paletas_unicas(self):
        claves = [p.key() for p in self.build.rom.palettes]
        self.assertEqual(len(claves), len(set(claves)))
        self.assertLessEqual(len(claves), 256)


class TestGeneracion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-gen-")
        self.proyecto_dir = os.path.join(self.tmp, "juego")
        from ngplat.scaffold import crear_proyecto
        crear_proyecto(self.proyecto_dir, "PRUEBA", "TEST")
        self.build = cargar_demo(self.proyecto_dir)
        self.out = os.path.join(self.tmp, "build")
        os.makedirs(self.out)
        self.roms, _ = generar_para_sistema(
            self.build, self.out, sistemas.obtener("neogeo"), "202")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_archivos_generados(self):
        for esperado in ("src/gamedata.c", "src/gamedata.h", "src/np_world.c",
                         "src/np_video.c", "src/np_hud.c", "src/np_sound.c",
                         "src/main.c", "src/sonido.z80", "Makefile"):
            self.assertTrue(os.path.isfile(os.path.join(self.out, esperado)), esperado)

    def test_la_rom_de_sonido_lleva_el_driver(self):
        nombre = [n for n in self.roms if n.endswith(".m1")]
        self.assertEqual(len(nombre), 1, "falta la ROM M1")
        with open(os.path.join(self.out, nombre[0]), "rb") as fh:
            datos = fh.read()
        self.assertEqual(datos[0], 0xF3, "el driver deberia empezar con 'di'")
        self.assertEqual(datos[0x66], 0xF5, "falta el manejador de la NMI")
        self.assertGreater(len(set(datos[:0x400])), 10, "la ROM M1 parece vacia")

    def test_roms_con_tamano_potencia_de_dos(self):
        for nombre, tamano in self.roms.items():
            self.assertEqual(tamano & (tamano - 1), 0, "%s no es potencia de dos" % nombre)
            self.assertGreaterEqual(tamano, 0x20000)

    def test_datos_del_juego_en_el_c(self):
        with open(os.path.join(self.out, "src/gamedata.c"), encoding="utf-8") as fh:
            texto = fh.read()
        self.assertIn('const char np_game_title[] = "PRUEBA";', texto)
        self.assertIn("const NpLevel np_levels[]", texto)
        self.assertIn("const NpPlayerDef np_player_def", texto)
        self.assertIn("np_level_count = %d;" % len(self.build.levels), texto)

    def test_compila_con_gcc_del_ordenador(self):
        """El codigo generado se compila sin avisos (sintaxis y tipos)."""
        if not shutil.which("gcc"):
            self.skipTest("no hay gcc")
        fuentes = ["src/gamedata.c", "src/np_world.c", "src/np_video.c",
                   "src/np_hud.c", "src/np_sound.c", "src/main.c"]
        for fuente in fuentes:
            resultado = subprocess.run(
                ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-fsyntax-only",
                 "-I", os.path.join(self.out, "src"), os.path.join(self.out, fuente)],
                capture_output=True, text=True,
            )
            self.assertEqual(resultado.returncode, 0,
                             "%s no compila:\n%s" % (fuente, resultado.stderr))

    def test_preview_autocontenido(self):
        html = render_html(self.build)
        self.assertIn("<canvas", html)
        self.assertIn("NPCore", html)
        self.assertIn("data:image/png;base64,", html)
        self.assertNotIn("@DATA@", html)
        self.assertNotIn("src=\"http", html)

    def test_preview_y_c_describen_lo_mismo(self):
        datos = build_data(self.build)
        self.assertEqual(len(datos["levels"]), len(self.build.levels))
        for json_level, level in zip(datos["levels"], self.build.levels):
            self.assertEqual(json_level["cells"], level.cells)
            self.assertEqual(json_level["start"], list(level.start))
            self.assertEqual(json_level["spawns"], [list(s) for s in level.spawns])
        self.assertEqual(datos["tiles"]["kind"],
                         [TILE_KIND_ID[t.kind] for t in self.build.tiles])
        self.assertEqual(datos["player"]["jump"],
                         int(round(self.build.project.player.jump * 256)))


if __name__ == "__main__":
    unittest.main()


class TestCapasDeFondo(unittest.TestCase):
    """Parallax: empaquetado de las capas y su uso por nivel."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-capas-")
        self.proyecto = os.path.join(self.tmp, "juego")
        from ngplat.scaffold import crear_proyecto
        crear_proyecto(self.proyecto, "CAPAS", "TEST")
        self.build = cargar_demo(self.proyecto)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_el_ejemplo_trae_capas(self):
        self.assertEqual(len(self.build.layers), 2)
        nombres = [c.name for c in self.build.layers]
        self.assertEqual(nombres, ["cielo", "arboles"])

    def test_tiles_de_capa_dentro_de_la_rom(self):
        for capa in self.build.layers:
            self.assertEqual(len(capa.tiles), capa.cols * capa.rows)
            for tile in capa.tiles:
                self.assertLess(tile, self.build.rom.sprite_tiles)

    def test_se_reutilizan_los_tiles_repetidos(self):
        """Un cielo con degradado repite muchisimo tile: no debe duplicarlos."""
        cielo = self.build.layers[0]
        self.assertLess(cielo.frames, len(cielo.tiles),
                        "los tiles repetidos deberian compartirse")

    def test_cada_nivel_elige_sus_capas(self):
        self.assertEqual(self.build.levels[0].layers, [0, 1])
        self.assertEqual(self.build.levels[1].layers, [0])

    def test_el_c_generado_incluye_las_capas(self):
        texto = generate_gamedata(self.build)["src/gamedata.c"]
        self.assertIn("const NpLayer np_layers[]", texto)
        self.assertIn("np_layer_count = 2;", texto)
        self.assertIn("np_level0_layers", texto)

    def test_capa_desconocida_da_error(self):
        ruta = os.path.join(self.proyecto, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        texto = texto.replace("fondos: [cielo]", "fondos: [niebla]")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        from ngplat.errors import ProjectError
        with self.assertRaises(ProjectError) as ctx:
            load_project(ruta)
        self.assertIn("niebla", ctx.exception.message)
