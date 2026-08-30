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

from ngplat import cli
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
        # cada sistema tiene su propia carpeta dentro de build/
        for esperado in ("build/neogeo/src/gamedata.c", "build/neogeo/Makefile",
                         "build/neogeo/rom/202-c1.c1"):
            self.assertTrue(os.path.isfile(os.path.join(self.proyecto, esperado)), esperado)

    def test_compila_para_las_tres_maquinas(self):
        self.assertEqual(self._ejecutar("nuevo", self.proyecto, "--titulo", "CLI")[0], 0)
        esperados = {
            "neogeo": ("src/np_video.c", "rom/202-m1.m1", "Makefile"),
            "megadrive": ("src/graficos.c", "src/sonido.c", "megadrive.ld",
                          "arreglar_rom.py"),
            "amiga": ("src/graficos.c", "src/sonido.c", "amiga.ld",
                      "hacer_ejecutable.py"),
        }
        for sistema, archivos in esperados.items():
            codigo, salida = self._ejecutar("compilar", self.proyecto,
                                            "--sistema", sistema)
            self.assertEqual(codigo, 0, salida)
            for archivo in archivos:
                ruta = os.path.join(self.proyecto, "build", sistema, archivo)
                self.assertTrue(os.path.isfile(ruta), "%s: %s" % (sistema, archivo))

    def test_lista_de_sistemas(self):
        codigo, salida = self._ejecutar("sistemas")
        self.assertEqual(codigo, 0, salida)
        for nombre in ("Neo Geo", "Mega Drive", "Amiga"):
            self.assertIn(nombre, salida)

    def test_alias_en_ingles(self):
        self.assertEqual(self._ejecutar("new", self.proyecto)[0], 0)
        self.assertEqual(self._ejecutar("check", self.proyecto)[0], 0)
        self.assertEqual(self._ejecutar("build", self.proyecto)[0], 0)

    def test_el_genero_cambia_como_se_juega(self):
        """`--genero` no es un adorno: cambia la fisica, el ataque y el nivel."""
        from ngplat.project import load_project
        salidas = {}
        for genero in ("plataformas", "castlevania"):
            destino = os.path.join(self.tmp, "g-" + genero)
            codigo, salida = self._ejecutar("nuevo", destino, "--genero", genero)
            self.assertEqual(codigo, 0, salida)
            salidas[genero] = load_project(destino)

        plat, cast = salidas["plataformas"], salidas["castlevania"]
        self.assertEqual(plat.player.attack.kind, "shot")
        self.assertEqual(cast.player.attack.kind, "melee")
        self.assertTrue(plat.player.stomp, "el de plataformas no pisa enemigos")
        self.assertFalse(cast.player.stomp, "el de latigo pisa enemigos")
        self.assertGreater(plat.player.air_accel, 0,
                           "el de plataformas no corrige el salto")
        self.assertEqual(cast.player.air_accel, 0.0,
                         "el de latigo corrige el salto en el aire")
        self.assertEqual(cast.player.stun, 24, "el de latigo no aturde")
        self.assertIsNone(plat.player.sub, "el de plataformas trae arma secundaria")
        self.assertIsNotNone(cast.player.sub, "el de latigo no trae arma secundaria")
        # y las escaleras: solo el de latigo las lleva, en la leyenda y en el mapa
        tipos = {t.kind for t in cast.tiles.values()}
        self.assertIn("stair_r", tipos, "el de latigo no tiene escaleras")
        self.assertNotIn("stair_r", {t.kind for t in plat.tiles.values()})
        self.assertIn("/", cast.levels[0].rows[14],
                      "el nivel del de latigo no trae escalera")
        # los puntos de control y la mejora del arma van con el mismo genero
        self.assertIn("check", tipos, "el de latigo no tiene puntos de control")
        self.assertNotIn("check", {t.kind for t in plat.tiles.values()})
        self.assertIn("!", cast.levels[0].rows[14],
                      "el nivel del de latigo no trae punto de control")
        self.assertEqual(cast.player.attack.levels, 2,
                         "el latigo no se puede mejorar")
        self.assertEqual(plat.player.attack.levels, 0,
                         "el de plataformas trae mejoras de arma")
        self.assertIn("upgrade", {i.effect for i in cast.items.values()},
                      "el de latigo no trae el objeto que mejora el arma")
        self.assertNotIn("upgrade", {i.effect for i in plat.items.values()})

    def test_un_genero_que_no_existe_no_cuela(self):
        destino = os.path.join(self.tmp, "inventado")
        with self.assertRaises(SystemExit):
            self._ejecutar("nuevo", destino, "--genero", "shmup")
        self.assertFalse(os.path.exists(os.path.join(destino, "game.yaml")))

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


class TestAsistente(unittest.TestCase):
    """Lo que ve quien abre NeoPlat con doble clic, sin escribir ordenes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-asis-")
        self.antes = os.getcwd()
        os.chdir(self.tmp)
        self.abiertos = []
        self.editor_real = cli._abrir_editor
        # abrir el editor levanta un servidor que no acaba nunca: aqui solo
        # anotamos que juego se habria abierto
        cli._abrir_editor = lambda ruta: self.abiertos.append(ruta) or 0

    def tearDown(self):
        cli._abrir_editor = self.editor_real
        os.chdir(self.antes)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _asistente(self, *lineas):
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = cli.asistente(io.StringIO("".join(l + "\n" for l in lineas)),
                                   salida)
        return codigo, salida.getvalue()

    def _crear(self, nombre):
        salida = io.StringIO()
        with redirect_stdout(salida), redirect_stderr(salida):
            main(["nuevo", nombre, "--titulo", nombre.upper(),
                  "--genero", "plataformas"])

    def test_sin_juegos_ofrece_crear_uno_y_abre_su_editor(self):
        codigo, salida = self._asistente("1", "prueba", "", "")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Que quieres hacer", salida)
        self.assertTrue(os.path.isfile(os.path.join("prueba", "game.yaml")), salida)
        self.assertEqual(self.abiertos, ["prueba"])

    def test_con_un_juego_delante_abre_su_editor_sin_preguntar_cual(self):
        self._crear("mijuego")
        codigo, salida = self._asistente("1")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("mijuego", salida)
        self.assertEqual(self.abiertos, [os.path.join(".", "mijuego")])

    def test_con_varios_juegos_pregunta_cual(self):
        self._crear("uno")
        self._crear("dos")
        codigo, salida = self._asistente("1", "2")
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Cual?", salida)
        # los lista en orden alfabetico: dos, uno
        self.assertEqual(self.abiertos, [os.path.join(".", "uno")])

    def test_compila_el_juego_elegido(self):
        self._crear("mijuego")
        # la maquina se puede elegir por numero o escribiendo su nombre
        codigo, salida = self._asistente("3", "megadrive")
        self.assertEqual(codigo, 0, salida)
        self.assertTrue(os.path.isfile(
            os.path.join("mijuego", "build", "megadrive", "src", "gamedata.c")), salida)

    def test_salir_no_toca_nada(self):
        self._crear("mijuego")
        codigo, salida = self._asistente("4")
        self.assertEqual(codigo, 0, salida)
        self.assertEqual(self.abiertos, [])

    def test_una_respuesta_que_no_existe_se_queda_con_la_primera(self):
        self._crear("mijuego")
        codigo, salida = self._asistente("melon")
        self.assertEqual(codigo, 0, salida)
        self.assertEqual(self.abiertos, [os.path.join(".", "mijuego")])


class TestVentanaQueNoSeCierra(unittest.TestCase):
    """Sin ordenes y con alguien delante sale el asistente, no la ayuda.

    El fallo era este: al doble clic, argparse escupia su lista de ordenes,
    devolvia 1 y la ventana se cerraba sin que diera tiempo a leerla.
    """

    class _Consola(io.StringIO):
        def isatty(self):
            return True

    def setUp(self):
        self.stdin = sys.stdin
        self.llamadas = []
        self.asistente_real = cli.asistente
        self.pausa_real = cli._esperar_para_cerrar
        cli.asistente = lambda: self.llamadas.append("asistente") or 0
        cli._esperar_para_cerrar = lambda: self.llamadas.append("pausa")

    def tearDown(self):
        cli.asistente = self.asistente_real
        cli._esperar_para_cerrar = self.pausa_real
        sys.stdin = self.stdin

    def test_con_consola_sale_el_asistente_y_espera_al_enter(self):
        sys.stdin = self._Consola()
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = main([])
        self.assertEqual(codigo, 0)
        self.assertEqual(self.llamadas, ["asistente", "pausa"])

    def test_en_una_tuberia_sigue_saliendo_la_ayuda(self):
        sys.stdin = io.StringIO()
        salida = io.StringIO()
        with redirect_stdout(salida):
            codigo = main([])
        self.assertEqual(codigo, 1)
        self.assertIn("usage", salida.getvalue())
        self.assertEqual(self.llamadas, [])


if __name__ == "__main__":
    unittest.main()
