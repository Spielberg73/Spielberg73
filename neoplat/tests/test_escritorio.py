"""El editor como programa: su ventana, y lo que pasa al cerrarla.

Dos cosas distintas se vigilan aqui.

La primera es **como se abre la ventana**: con que navegador, con que
argumentos y en que perfil. Es codigo que en Linux no se puede ejecutar de
verdad contra Edge, asi que lo que se comprueba es la orden que se arma, que
es donde estan los fallos de este tipo de cosas (una comilla de mas, el perfil
en la carpeta del usuario, el `--app` mal escrito y entonces lo que sale es un
navegador con su barra de direcciones).

La segunda importa mas: **al cerrar la ventana se para el servidor**. Quien
abre esto con doble clic no tiene una consola a la que volver para pulsar
Ctrl+C, asi que un servidor que se quedara escuchando seria un proceso
colgado para siempre y un puerto ocupado la proxima vez.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from comun import KIT, crear_proyecto

sys.path.insert(0, os.path.join(KIT, "tools"))

from ngplat import escritorio    # noqa: E402


class TestConQueSeAbreLaVentana(unittest.TestCase):

    def test_la_orden_lleva_el_modo_aplicacion(self):
        """`--app=` es lo unico que separa una ventana de una pestana."""
        orden = escritorio.argumentos("/usr/bin/eso", "http://127.0.0.1:9/?t=x")
        self.assertEqual("/usr/bin/eso", orden[0])
        self.assertIn("--app=http://127.0.0.1:9/?t=x", orden)
        self.assertTrue(any(a.startswith("--window-size=") for a in orden))

    def test_el_perfil_es_suyo_y_no_el_del_usuario(self):
        """Con el perfil del usuario, la ventana heredaria sus extensiones y
        sus pestanas, y cerrarla podria cerrarle el navegador."""
        orden = escritorio.argumentos("/usr/bin/eso", "http://127.0.0.1:9/")
        perfiles = [a for a in orden if a.startswith("--user-data-dir=")]
        self.assertEqual(1, len(perfiles))
        carpeta = perfiles[0].split("=", 1)[1]
        self.assertIn("NeoPlat", carpeta)
        self.assertTrue(os.path.isdir(carpeta))

    def test_no_sale_el_cuento_de_la_primera_vez(self):
        orden = escritorio.argumentos("/usr/bin/eso", "http://127.0.0.1:9/")
        self.assertIn("--no-first-run", orden)
        self.assertIn("--no-default-browser-check", orden)

    def test_se_le_puede_decir_cual(self):
        """En una maquina donde el navegador esta en un sitio raro, o donde hay
        varios, `NEOPLAT_NAVEGADOR` manda."""
        antes = os.environ.get("NEOPLAT_NAVEGADOR")
        os.environ["NEOPLAT_NAVEGADOR"] = sys.executable
        try:
            self.assertEqual(sys.executable, escritorio.buscar_navegador())
        finally:
            if antes is None:
                del os.environ["NEOPLAT_NAVEGADOR"]
            else:
                os.environ["NEOPLAT_NAVEGADOR"] = antes

    def test_sin_navegador_no_revienta(self):
        """Devolver None es la respuesta a "aqui no hay con que", y quien llama
        abre el navegador de siempre. Lo que no puede es fallar."""
        antes = os.environ.get("NEOPLAT_NAVEGADOR")
        os.environ["NEOPLAT_NAVEGADOR"] = "/no/existe/esto"
        try:
            self.assertIsNone(escritorio.buscar_navegador())
            self.assertIsNone(escritorio.abrir("http://127.0.0.1:9/"))
        finally:
            if antes is None:
                del os.environ["NEOPLAT_NAVEGADOR"]
            else:
                os.environ["NEOPLAT_NAVEGADOR"] = antes


class TestAlCerrarLaVentanaSeParaElServidor(unittest.TestCase):
    """Lo que se prueba de verdad, y de punta a punta.

    El "navegador" es un Python que duerme un rato y se muere: hace de ventana
    que se cierra. Si el servidor siguiera vivo despues, esta prueba se
    quedaria esperando y fallaria por tiempo.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-escritorio-")
        cls.proyecto = os.path.join(cls.tmp, "juego")
        crear_proyecto(cls.proyecto, "VENTANA", "TEST")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_se_abre_sirve_y_al_cerrar_la_ventana_se_para(self):
        falso = os.path.join(self.tmp, "ventana.py")
        with open(falso, "w", encoding="utf-8") as fh:
            # Escribe la direccion que le pasan y se queda vivo un rato, que es
            # lo que hace una ventana abierta.
            fh.write("import sys, time\n"
                     "open(sys.argv[1], 'w').write(' '.join(sys.argv[2:]))\n"
                     "time.sleep(6)\n")
        apunte = os.path.join(self.tmp, "apunte.txt")
        lanzador = os.path.join(self.tmp, "lanzador")
        with open(lanzador, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexec %s %s %s \"$@\"\n"
                     % (sys.executable, falso, apunte))
        os.chmod(lanzador, 0o755)

        entorno = dict(os.environ, NEOPLAT_NAVEGADOR=lanzador)
        entorno["PYTHONPATH"] = os.path.join(KIT, "tools")
        proceso = subprocess.Popen(
            [sys.executable, os.path.join(KIT, "ngplat"), "app", self.proyecto],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env=entorno)
        try:
            direccion = ""
            for _ in range(200):
                if os.path.exists(apunte):
                    with open(apunte, encoding="utf-8") as fh:
                        escrito = fh.read()
                    for trozo in escrito.split():
                        if trozo.startswith("--app="):
                            direccion = trozo[len("--app="):]
                    if direccion:
                        break
                time.sleep(0.1)
            self.assertTrue(direccion, "la ventana no se ha llegado a abrir")

            # mientras la ventana vive, el editor se sirve
            with urllib.request.urlopen(direccion, timeout=10) as r:
                self.assertEqual(200, r.status)
                self.assertIn(b"<html", r.read(4096).lower())

            # y al morirse la ventana, el servidor se va detras
            proceso.wait(timeout=40)
            self.assertEqual(0, proceso.returncode)
            with self.assertRaises((urllib.error.URLError, OSError)):
                urllib.request.urlopen(direccion, timeout=5)
        finally:
            if proceso.poll() is None:
                proceso.kill()
                proceso.wait(timeout=10)


class TestElLanzadorSinConsola(unittest.TestCase):
    """neoplat_app.py es lo que se empaqueta como NeoPlat.exe."""

    def test_se_puede_importar_sin_tener_pantalla(self):
        """Lo importa PyInstaller al empaquetar, y ahi no hay ni X ni Windows:
        si tkinter se tocara al importar, el .exe no se construiria."""
        hecho = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, %r); "
             "import importlib.util as u; "
             "e = u.spec_from_file_location('app', %r); "
             "m = u.module_from_spec(e); e.loader.exec_module(m); "
             "print(bool(m.main))"
             % (os.path.join(KIT, "tools"),
                os.path.join(KIT, "neoplat_app.py"))],
            capture_output=True, text=True)
        self.assertEqual(0, hecho.returncode, hecho.stderr)
        self.assertIn("True", hecho.stdout)

    def test_el_empaquetado_construye_los_dos_binarios(self):
        """Uno con consola y otro sin ella: Windows lo decide al enlazar, asi
        que no puede ser el mismo .exe."""
        sys.path.insert(0, KIT)
        import empaquetar

        consola = empaquetar.opciones_pyinstaller(True)
        ventana = empaquetar.opciones_pyinstaller(True, ventana=True)
        self.assertIn("--console", consola)
        self.assertIn("ngplat", consola)
        self.assertIn("--windowed", ventana)
        self.assertIn("NeoPlat", ventana)
        self.assertIn("neoplat_app.py", ventana)
        # y los dos se llevan los mismos datos dentro
        self.assertEqual([a for a in consola if a == "--add-data"],
                         [a for a in ventana if a == "--add-data"])


def _yaml_kungfu() -> str:
    """El game.yaml del genero, con los huecos rellenos de cualquier cosa."""
    from ngplat.scaffold import GAME_YAML_KUNGFU

    huecos = set(re.findall(r"\{(\w+)\}", GAME_YAML_KUNGFU))
    return GAME_YAML_KUNGFU.format(**{h: "" for h in huecos})


class TestLaHojaDelHeroeDeKungFu(unittest.TestCase):
    """Los fotogramas del heroe y lo que el game.yaml dice que hay.

    Son dos sitios distintos -el dibujo lo hace art_kungfu y los numeros los
    pone la plantilla del genero- y si se separan no falla nada: sale el
    fotograma equivocado, o ninguno, y eso solo se ve jugando.
    """

    def test_son_trece_y_todos_miden_lo_mismo(self):
        from ngplat import art_kungfu

        for estilo in ("bosque", "hierro"):
            hoja = art_kungfu.heroe(estilo)
            self.assertEqual(32, hoja.height, estilo)
            self.assertEqual(13, hoja.width // 32, estilo)
            self.assertEqual(0, hoja.width % 32, estilo)

    def test_ningun_fotograma_sale_en_blanco(self):
        """Un fotograma vacio es un hueco en la animacion que no avisa."""
        from ngplat import art_kungfu

        hoja = art_kungfu.heroe("bosque")
        for i in range(hoja.width // 32):
            pintados = sum(1 for y in range(32) for x in range(32)
                           if hoja.get(i * 32 + x, y)[3])
            self.assertGreater(pintados, 120,
                               "el fotograma %d esta casi vacio" % i)

    def test_cada_fotograma_es_distinto_del_de_al_lado(self):
        """Dos fotogramas iguales en una animacion es un fotograma de menos."""
        from ngplat import art_kungfu

        hoja = art_kungfu.heroe("bosque")
        def trozo(i):
            return [hoja.get(i * 32 + x, y)
                    for y in range(32) for x in range(32)]
        for i in range(hoja.width // 32 - 1):
            self.assertNotEqual(trozo(i), trozo(i + 1),
                                "los fotogramas %d y %d son el mismo"
                                % (i, i + 1))

    def test_el_game_yaml_del_genero_no_pide_un_fotograma_que_no_existe(self):
        from ngplat import art_kungfu
        from ngplat.scaffold import GAME_YAML_KUNGFU

        cuantos = art_kungfu.heroe("bosque").width // 32
        yaml = _yaml_kungfu()
        dentro, pedidos = False, []
        for linea in yaml.split("\n"):
            if linea.startswith("jugador:"):
                dentro = True
            elif dentro and linea and not linea[0].isspace():
                break
            if dentro and "frames: [" in linea:
                numeros = linea.split("frames: [", 1)[1].split("]", 1)[0]
                pedidos += [int(n) for n in numeros.split(",") if n.strip()]
        self.assertTrue(pedidos, "no se ha leido ninguna animacion")
        self.assertLess(max(pedidos), cuantos,
                        "el yaml pide el fotograma %d y la hoja tiene %d"
                        % (max(pedidos), cuantos))
        # y los usa todos: un fotograma dibujado que nadie pide es trabajo
        # tirado y, en el Amiga, KB de RAM chip tirados
        self.assertEqual(set(range(cuantos)), set(pedidos),
                         "hay fotogramas dibujados que el yaml no usa")

    def test_el_andar_tiene_cuatro(self):
        """La razon de rehacer la hoja: con dos, lo que se veia no era andar."""
        from ngplat.scaffold import GAME_YAML_KUNGFU

        yaml = _yaml_kungfu()
        for linea in yaml.split("\n"):
            if linea.strip().startswith("correr:"):
                numeros = linea.split("frames: [", 1)[1].split("]", 1)[0]
                self.assertEqual(4, len([n for n in numeros.split(",")
                                         if n.strip()]))
                return
        self.fail("el genero de kung-fu no declara 'correr:'")
