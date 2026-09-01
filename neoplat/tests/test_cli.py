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

    def test_las_escaleras_estan_en_los_dos_niveles(self):
        """La mecanica que da nombre al genero tiene que salir en todo el juego.

        Estaba solo en un rincon del primer nivel: el segundo no tenia ni una,
        asi que se podia terminar el juego sin subir una escalera.
        """
        from ngplat.project import load_project
        destino = os.path.join(self.tmp, "escaleras")
        self.assertEqual(self._ejecutar("nuevo", destino,
                                        "--genero", "castlevania")[0], 0)
        proyecto = load_project(destino)
        for i, nivel in enumerate(proyecto.levels):
            self.assertTrue(any("/" in fila for fila in nivel.rows),
                            "el nivel %d no tiene ninguna escalera" % (i + 1))
        # y la de arriba lleva a algo: la segunda mejora del latigo
        self.assertTrue(any("M" in fila for fila in proyecto.levels[1].rows),
                        "no hay nada arriba de la escalera del segundo nivel")

    def test_el_genero_de_latigo_trae_su_propia_musica(self):
        """No la misma cancioncilla del de plataformas, y no de dos segundos."""
        from ngplat.project import load_project
        proyectos = {}
        for genero in ("plataformas", "castlevania"):
            destino = os.path.join(self.tmp, "m-" + genero)
            self.assertEqual(self._ejecutar("nuevo", destino,
                                            "--genero", genero)[0], 0)
            proyectos[genero] = load_project(destino)
        plat, cast = proyectos["plataformas"], proyectos["castlevania"]

        self.assertEqual(set(cast.sound.musica), {"castillo", "cripta"})
        self.assertFalse(set(cast.sound.musica) & set(plat.sound.musica),
                         "el de latigo toca la musica del de plataformas")
        # y cada nivel pide la suya
        self.assertEqual([n.music for n in cast.levels], ["castillo", "cripta"])

        def frames(musica):
            return [sum(paso.duracion for paso in pista) for pista in musica.pistas]

        for nombre, musica in cast.sound.musica.items():
            largos = frames(musica)
            self.assertEqual(len(set(largos)), 1,
                             "las dos pistas de '%s' no duran lo mismo: %s"
                             % (nombre, largos))
            self.assertGreaterEqual(
                largos[0], 480,
                "'%s' dura %d frames: se repite antes de ocho segundos"
                % (nombre, largos[0]))
        mas_larga_plat = max(max(frames(m)) for m in plat.sound.musica.values())
        self.assertGreater(max(max(frames(m)) for m in cast.sound.musica.values()),
                           mas_larga_plat * 3,
                           "la del castillo no es mucho mas larga que la de antes")

    def test_el_genero_de_latigo_trae_sus_propios_bichos(self):
        """Con los mismos bichos y el mismo dibujo, un juego de latigo parece el
        de plataformas con otro sprite en la mano. Aqui patrulla un esqueleto
        que aguanta dos golpes -no se puede pisar a nadie, asi que hay que
        acercarse y pegar-, vuela un murcielago y el jefe es otro."""
        from ngplat.project import load_project
        proyectos = {}
        for genero in ("plataformas", "castlevania"):
            destino = os.path.join(self.tmp, "b-" + genero)
            self.assertEqual(self._ejecutar("nuevo", destino,
                                            "--genero", genero)[0], 0)
            proyectos[genero] = (destino, load_project(destino))
        (_, plat), (carpeta, cast) = proyectos["plataformas"], proyectos["castlevania"]

        self.assertEqual(sorted(cast.enemies), ["esqueleto", "muerte", "murcielago"])
        self.assertFalse(set(cast.enemies) & set(plat.enemies),
                         "el de latigo trae los bichos del de plataformas")
        # y cada uno con su dibujo, que es de lo que va esto: en el de
        # plataformas los tres comparten hoja a proposito
        hojas = {e.sprite for e in cast.enemies.values()}
        self.assertEqual(len(hojas), 3, "los tres bichos comparten dibujo")
        for hoja in hojas:
            self.assertTrue(os.path.exists(os.path.join(carpeta, hoja)),
                            "falta el dibujo %s" % hoja)
        # el esqueleto aguanta dos latigazos: uno solo seria como pisarlo
        self.assertEqual(cast.enemies["esqueleto"].health, 2)
        self.assertTrue(cast.enemies["muerte"].boss)
        # y los simbolos del mapa apuntan a los bichos de este genero
        simbolos = cast.levels[0].spawns
        for simbolo, quien in (("s", "esqueleto"), ("m", "murcielago"),
                               ("J", "muerte")):
            self.assertEqual(simbolos.get(simbolo), quien,
                             "el simbolo '%s' no pone un %s" % (simbolo, quien))

    def test_los_dos_estilos_dibujan_los_bichos_del_latigo(self):
        """El genero y el estilo son ejes distintos: el murcielago tiene que
        existir en los dos, y en el de seis colores con esos seis."""
        from ngplat import art, art_hierro
        for modulo, tope in ((art, 15), (art_hierro, 6)):
            dibujos = modulo.todos()
            for nombre in ("graficos/esqueleto.png", "graficos/murcielago.png",
                           "graficos/muerte.png"):
                self.assertIn(nombre, dibujos, modulo.__name__)
                imagen = dibujos[nombre]
                self.assertEqual((imagen.width, imagen.height), (32, 16), nombre)
                colores = {c for c in imagen.colors() if c[3]}
                self.assertTrue(colores, "%s esta en blanco" % nombre)
                self.assertLessEqual(len(colores), tope, nombre)

    def test_la_antorcha_suena(self):
        """El punto de control tenia el evento sin poner y se tocaba en mudo."""
        from ngplat.project import load_project
        destino = os.path.join(self.tmp, "antorcha")
        self.assertEqual(self._ejecutar("nuevo", destino,
                                        "--genero", "castlevania")[0], 0)
        proyecto = load_project(destino)
        self.assertIn("control", proyecto.sound.efectos,
                      "tocar la antorcha no suena")
        # y romper un candelabro tambien, en los dos estilos de dibujo
        for estilo in ("bosque", "hierro"):
            otro = os.path.join(self.tmp, "romper-" + estilo)
            self.assertEqual(self._ejecutar("nuevo", otro, "--estilo", estilo,
                                            "--genero", "castlevania")[0], 0)
            self.assertIn("romper", load_project(otro).sound.efectos,
                          "romper un candelabro no suena en el estilo " + estilo)

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
