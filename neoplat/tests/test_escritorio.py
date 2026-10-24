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
import threading
import time
import types
import unittest
import urllib.error
import urllib.parse
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


import contextlib


@contextlib.contextmanager
def _modulo_puesto(nombre, modulo):
    """Mete un modulo de mentira en sys.modules mientras dure el bloque."""
    antes = sys.modules.get(nombre)
    sys.modules[nombre] = modulo
    try:
        yield
    finally:
        if antes is None:
            sys.modules.pop(nombre, None)
        else:
            sys.modules[nombre] = antes


def _lanzador():
    """neoplat_app.py cargado aparte, para poder cambiarle las piezas.

    Se carga por ruta y no con `import`: el lanzador vive en la raiz del kit,
    no es parte del paquete, y lo que se prueba aqui es precisamente lo que
    hace cuando los dialogos no estan.
    """
    import importlib.util as u

    carga = u.spec_from_file_location("neoplat_app",
                                      os.path.join(KIT, "neoplat_app.py"))
    modulo = u.module_from_spec(carga)
    carga.loader.exec_module(modulo)
    return modulo


def _explota(porque: str):
    """Una pieza que no se tenia que llamar. Si se llama, se nota."""
    def saltar(*_a, **_k):
        raise AssertionError(porque)
    return saltar


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

    def test_el_exe_de_windows_se_construye_sin_tkinter(self):
        """Para que el log del empaquetado no avise de una averia que no hay.

        El Python embebido no trae tkinter y PyInstaller lo dice a gritos
        ("tkinter installation is broken") antes de dejarlo fuera. En Windows
        no se usa -los dialogos son del sistema-, asi que se excluye a
        proposito. En Linux y en Mac si es el respaldo, y ahi se queda.
        """
        sys.path.insert(0, KIT)
        import empaquetar

        for ventana in (False, True):
            windows = empaquetar.opciones_pyinstaller(True, ventana=ventana)
            self.assertIn("--exclude-module", windows)
            self.assertEqual("tkinter",
                             windows[windows.index("--exclude-module") + 1])
            self.assertNotIn("--exclude-module",
                             empaquetar.opciones_pyinstaller(False,
                                                             ventana=ventana))


    def test_avisa_aunque_no_haya_tkinter(self):
        """La prueba que explica por que los dialogos son de Windows.

        El Python que cabe dentro de un .exe de ocho megas no trae tkinter, y
        PyInstaller lo deja fuera avisando en una linea del log que es facil no
        leer. Si el lanzador dependiera de el, el programa se cerraria en
        silencio al primer dialogo. Aqui se le quita tkinter a proposito y se
        comprueba que el aviso sale igual: por la salida de errores si no hay
        otra cosa, pero sale.
        """
        guion = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "class Nada:\n"
            "    def find_module(self, nombre, ruta=None):\n"
            "        if nombre.split('.')[0] == 'tkinter':\n"
            "            raise ImportError('aqui no hay tkinter')\n"
            "    def find_spec(self, nombre, ruta=None, destino=None):\n"
            "        return self.find_module(nombre, ruta)\n"
            "sys.meta_path.insert(0, Nada())\n"
            "for m in list(sys.modules):\n"
            "    if m.split('.')[0] == 'tkinter':\n"
            "        del sys.modules[m]\n"
            "import importlib.util as u\n"
            "e = u.spec_from_file_location('app', %r)\n"
            "m = u.module_from_spec(e)\n"
            "e.loader.exec_module(m)\n"
            "m.mensaje('NeoPlat', 'esto se tiene que leer', error=True)\n"
            "print('sigue vivo')\n"
            % (os.path.join(KIT, "tools"), os.path.join(KIT, "neoplat_app.py")))
        hecho = subprocess.run([sys.executable, "-c", guion],
                               capture_output=True, text=True)
        self.assertEqual(0, hecho.returncode, hecho.stderr)
        self.assertIn("esto se tiene que leer", hecho.stderr)
        self.assertIn("sigue vivo", hecho.stdout)

    def test_sin_dialogos_tampoco_se_queda_colgado_preguntando(self):
        """`preguntar` sin dialogos no puede quedarse esperando una respuesta
        que nadie va a dar: devuelve que si, y aqui el si nunca borra nada."""
        app = _lanzador()
        app.ES_WINDOWS = False
        import builtins

        de_verdad = builtins.__import__

        def sin_tkinter(nombre, *resto):
            if nombre.split(".")[0] == "tkinter":
                raise ImportError("aqui no hay tkinter")
            return de_verdad(nombre, *resto)

        builtins.__import__ = sin_tkinter
        try:
            self.assertTrue(app.preguntar("NeoPlat", "?"))
            self.assertEqual("", app.elegir_carpeta("elige", ""))
        finally:
            builtins.__import__ = de_verdad

    def test_con_un_solo_juego_al_lado_no_pregunta_nada(self):
        """El caso de siempre: el .exe junto a la carpeta del juego. Ahi un
        dialogo seria una molestia, asi que no sale ninguno."""
        app = _lanzador()
        app.mensaje = _explota("no tenia que avisar de nada")
        app.preguntar = _explota("no tenia que preguntar nada")
        app.elegir_carpeta = _explota("no tenia que pedir carpeta")
        self.assertEqual("C:\\juegos\\mijuego",
                         app.elegir_proyecto(["C:\\juegos\\mijuego"], "C:\\juegos"))

    def test_una_carpeta_con_cosas_que_no_es_un_juego_no_se_toca(self):
        """Elegir ahi el escritorio por error no puede acabar con un game.yaml
        y unos graficos de ejemplo sembrados entre los papeles de nadie."""
        app = _lanzador()
        ajeno = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, ajeno, True)
        with open(os.path.join(ajeno, "la_tesis.odt"), "w") as f:
            f.write("mia")
        dichos = []
        app.mensaje = lambda t, x, error=False: dichos.append(x)
        app.preguntar = lambda t, x: True
        app.elegir_carpeta = lambda t, desde="": ajeno
        self.assertEqual("", app.elegir_proyecto([], tempfile.gettempdir()))
        self.assertEqual(["la_tesis.odt"], os.listdir(ajeno))
        self.assertTrue(any("vacia" in d for d in dichos), dichos)

    def test_una_carpeta_vacia_se_vuelve_un_juego(self):
        app = _lanzador()
        destino = os.path.join(tempfile.mkdtemp(), "ELCAMPEON")
        self.addCleanup(shutil.rmtree, os.path.dirname(destino), True)
        app.mensaje = _explota("no habia nada que avisar")
        app.preguntar = lambda t, x: True
        app.elegir_carpeta = lambda t, desde="": destino
        self.assertEqual(destino, app.elegir_proyecto([], tempfile.gettempdir()))
        with open(os.path.join(destino, "game.yaml")) as f:
            self.assertIn("ELCAMPEON", f.read())

    def test_una_carpeta_sin_game_yaml_se_dice_y_no_se_abre(self):
        """Pasar una carpeta cualquiera por la linea de ordenes -o arrastrarla
        encima del .exe- no puede acabar en una ventana vacia."""
        app = _lanzador()
        vacia = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, vacia, True)
        dichos = []
        app.mensaje = lambda t, x, error=False: dichos.append(x)
        app.donde_buscar = lambda: vacia    # y el registro, ahi dentro
        self.assertEqual(2, app.main([vacia]))
        self.assertTrue(any("game.yaml" in d for d in dichos), dichos)



class TestSinFlujosEstandar(unittest.TestCase):
    """La prueba que faltaba, y por la que 1.57 no servia.

    En Windows un programa enlazado **sin consola** arranca sin flujos
    estandar: `sys.stdout` y `sys.stderr` valen None. El kit escribe por ahi
    -como todo el mundo-, asi que a la primera linea saltaba un AttributeError
    y el programa se moria **justo despues de abrir la ventana**: lo que veia
    quien hacia doble clic era un enlace muerto.

    Esto lo hace de verdad: le quita los dos flujos al lanzador, lo lanza
    contra un proyecto y exige que **el enlace conteste**. Aqui no vale mirar
    que no reviente: lo que hay que exigir es que sirva.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-sinflujos-")
        cls.proyecto = os.path.join(cls.tmp, "juego")
        crear_proyecto(cls.proyecto, "SINCONSOLA", "TEST")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_el_enlace_contesta_aunque_no_haya_donde_escribir(self):
        falso = os.path.join(self.tmp, "ventana.py")
        with open(falso, "w", encoding="utf-8") as fh:
            fh.write("import sys, time\n"
                     "open(sys.argv[1], 'w').write(' '.join(sys.argv[2:]))\n"
                     "time.sleep(20)\n")
        apunte = os.path.join(self.tmp, "apunte.txt")
        lanzador = os.path.join(self.tmp, "lanzador")
        with open(lanzador, "w", encoding="utf-8") as fh:
            fh.write("#!/bin/sh\nexec %s %s %s \"$@\"\n"
                     % (sys.executable, falso, apunte))
        os.chmod(lanzador, 0o755)

        # El doble clic de Windows, tal cual: sin stdout y sin stderr.
        guion = os.path.join(self.tmp, "doble_clic.py")
        with open(guion, "w", encoding="utf-8") as fh:
            fh.write("import importlib.util as u, sys\n"
                     "carga = u.spec_from_file_location('app', %r)\n"
                     "app = u.module_from_spec(carga)\n"
                     "carga.loader.exec_module(app)\n"
                     "sys.stdout = None\n"
                     "sys.stderr = None\n"
                     "raise SystemExit(app.main([%r]))\n"
                     % (os.path.join(KIT, "neoplat_app.py"), self.proyecto))

        entorno = dict(os.environ, NEOPLAT_NAVEGADOR=lanzador)
        entorno["PYTHONPATH"] = os.path.join(KIT, "tools")
        # Se lanza **desde** la carpeta temporal: el registro que deja el
        # programa va al lado del programa, y aqui eso es la carpeta de
        # trabajo. Asi no se siembra un NeoPlat-registro.txt en tests/.
        proceso = subprocess.Popen([sys.executable, guion],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True,
                                   env=entorno, cwd=self.tmp)
        try:
            direccion = ""
            for _ in range(300):
                if proceso.poll() is not None:
                    self.fail("el lanzador se ha muerto solo:\n%s"
                              % proceso.communicate()[0])
                if os.path.exists(apunte):
                    with open(apunte, encoding="utf-8") as fh:
                        for trozo in fh.read().split():
                            if trozo.startswith("--app="):
                                direccion = trozo[len("--app="):]
                    if direccion:
                        break
                time.sleep(0.1)
            self.assertTrue(direccion, "la ventana no se ha llegado a abrir")

            # Y lo que importa: que al otro lado del enlace haya algo.
            with urllib.request.urlopen(direccion, timeout=15) as r:
                self.assertEqual(200, r.status)
                self.assertIn(b"<html", r.read(4096).lower())

            # Y de paso, lo que sustituye a la consola que aqui no hay: el
            # registro, con la direccion en la que esta sirviendo.
            registro = os.path.join(self.tmp, "NeoPlat-registro.txt")
            self.assertTrue(os.path.isfile(registro),
                            "no ha dejado constancia de nada")
            with open(registro, encoding="utf-8") as fh:
                apuntado = fh.read()
            self.assertIn("servidor en", apuntado)
            self.assertIn(direccion.split("?")[0], apuntado)
        finally:
            if proceso.poll() is None:
                proceso.kill()
                proceso.wait(timeout=10)

    def test_las_lineas_del_kit_se_guardan_para_el_cuadro_de_dialogo(self):
        """Sin consola no hay registro: lo ultimo que se escribio es lo unico
        que puede explicar un fallo, asi que se guarda para el dialogo."""
        app = _lanzador()
        cuaderno = app._Cuaderno()
        for i in range(60):
            cuaderno.write("linea %d\n" % i)
        cuaderno.write("  ok  servidor en http://127.0.0.1:8777\n")
        self.assertEqual(app._Cuaderno.LIMITE, len(cuaderno.lineas))
        self.assertIn("servidor en", cuaderno.ultimas())
        self.assertNotIn("linea 0\n", cuaderno.ultimas())
        self.assertFalse(cuaderno.isatty())

    def test_se_pone_algo_donde_windows_no_pone_nada(self):
        app = _lanzador()
        guardados = (sys.stdout, sys.stderr, sys.stdin)
        try:
            sys.stdout = sys.stderr = sys.stdin = None
            app.apuntalar_salidas()
            self.assertIsNotNone(sys.stdout)
            self.assertIsNotNone(sys.stderr)
            self.assertFalse(sys.stdout.isatty())
            self.assertFalse(sys.stdin.isatty())
            sys.stdout.write("algo\n")      # y esto no puede reventar
        finally:
            sys.stdout, sys.stderr, sys.stdin = guardados

    def test_el_color_no_da_por_hecho_que_haya_salida(self):
        """La linea exacta que mataba al programa: `sys.stdout.isatty()`."""
        from ngplat import cli

        guardado = sys.stdout
        try:
            sys.stdout = None
            self.assertEqual("  ok  ", cli._color("  ok  ", cli.VERDE))
        finally:
            sys.stdout = guardado



class TestDondeSeBuscaElNavegador(unittest.TestCase):
    """Por que esto se reescribio.

    En un Windows de verdad el editor se abria en una pestana normal en vez de
    en su ventana, y lo unico que se sabia era eso: el aviso que lo explicaba
    iba a una consola que en NeoPlat.exe no existe. Mirar solo en
    `%ProgramFiles%` no basta -una instalacion puede estar en otra unidad, y
    la variable puede no haber llegado hasta aqui-, asi que ahora se le
    pregunta a Windows por el registro, y lo que se ha mirado se puede contar.
    """

    def test_se_le_pregunta_a_windows_por_el_registro(self):
        """`App Paths` es como el propio Windows resuelve "msedge"."""
        if not sys.platform.startswith("win"):
            # Aqui no hay registro, asi que lo que se exige es que no invente
            # nada y no reviente por no haberlo.
            self.assertEqual([], escritorio._del_registro())
        falso = types.ModuleType("winreg")
        falso.HKEY_CURRENT_USER = 1
        falso.HKEY_LOCAL_MACHINE = 2
        falso.KEY_READ = 0x20019
        falso.KEY_WOW64_64KEY = 0x0100
        puesto = {}

        class _Clave:
            def __enter__(self): return self
            def __exit__(self, *_): return False

        def abrir(raiz, ruta, reservado, acceso):
            puesto["ruta"] = ruta
            puesto.setdefault("accesos", []).append(acceso)
            if raiz == 2 and ruta.endswith("msedge.exe"):
                return _Clave()
            raise OSError("no esta")

        falso.OpenKey = abrir
        falso.QueryValueEx = lambda clave, nombre: (
            r'"C:\Donde Sea\Edge\msedge.exe"', 1)

        antes_plataforma = escritorio.sys.platform
        with _modulo_puesto("winreg", falso):
            escritorio.sys.platform = "win32"
            try:
                salio = escritorio._del_registro()
            finally:
                escritorio.sys.platform = antes_plataforma
        # las comillas que trae el registro no son parte de la ruta
        self.assertEqual([r"C:\Donde Sea\Edge\msedge.exe"], salio)
        self.assertIn("App Paths", puesto["ruta"])
        # y se pide la vista de 64 bits, para no leer media verdad
        self.assertTrue(any(a & falso.KEY_WOW64_64KEY
                            for a in puesto["accesos"]),
                        puesto["accesos"])

    def test_el_registro_va_antes_que_program_files(self):
        """Lo que diga Windows manda sobre una ruta adivinada."""
        orden = [de_donde for _, de_donde in escritorio.candidatos()]
        sitios = [i for i, d in enumerate(orden) if "registro" in d]
        carpetas = [i for i, d in enumerate(orden) if d == "Program Files"]
        if sitios and carpetas:
            self.assertLess(max(sitios), min(carpetas))

    def test_lo_que_se_ha_mirado_se_puede_contar(self):
        """La lista entera, con un si o un no al lado. Es lo que saca
        `ngplat navegador`, y es lo que faltaba para arreglar esto de lejos."""
        mirados = escritorio.donde_se_busca()
        self.assertTrue(mirados)
        for ruta, de_donde, hay in mirados:
            self.assertTrue(ruta)
            self.assertTrue(de_donde)
            self.assertIsInstance(hay, bool)
            self.assertEqual(os.path.isfile(ruta), hay)

    def test_la_orden_navegador_lo_lista(self):
        hecho = subprocess.run([sys.executable, os.path.join(KIT, "ngplat"),
                                "navegador"],
                               capture_output=True, text=True,
                               env=dict(os.environ, NO_COLOR="1"))
        self.assertEqual(0, hecho.returncode, hecho.stderr)
        self.assertIn("Donde busco el navegador", hecho.stdout)
        self.assertIn("PATH", hecho.stdout)

    def test_no_es_lo_mismo_que_no_este_que_que_no_arranque(self):
        """Los dos casos se veian igual desde fuera -un navegador normal- y
        son cosas distintas: uno se arregla instalando Edge y el otro no."""
        antes = os.environ.get("NEOPLAT_NAVEGADOR")
        try:
            os.environ["NEOPLAT_NAVEGADOR"] = "/no/existe/esto"
            proceso, motivo = escritorio.abrir_con_motivo("http://127.0.0.1:9/")
            self.assertIsNone(proceso)
            self.assertIn("no encuentro", motivo)

            # y ahora algo que existe pero no se puede ejecutar
            ruta = os.path.join(tempfile.mkdtemp(), "no_ejecutable")
            self.addCleanup(shutil.rmtree, os.path.dirname(ruta), True)
            with open(ruta, "w", encoding="utf-8") as fh:
                fh.write("esto no es un programa\n")
            os.chmod(ruta, 0o644)
            os.environ["NEOPLAT_NAVEGADOR"] = ruta
            proceso, motivo = escritorio.abrir_con_motivo("http://127.0.0.1:9/")
            self.assertIsNone(proceso)
            self.assertIn("no he podido arrancar", motivo.lower())
            self.assertIn(ruta, motivo)
        finally:
            if antes is None:
                os.environ.pop("NEOPLAT_NAVEGADOR", None)
            else:
                os.environ["NEOPLAT_NAVEGADOR"] = antes

    def test_sin_ventana_el_lanzador_lo_dice_en_un_dialogo(self):
        """Lo que le faltaba a NeoPlat.exe: sin consola, el aviso de que no hay
        Edge no se veia en ninguna parte y el usuario solo veia una pestana."""
        app = _lanzador()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        crear_proyecto(os.path.join(tmp, "juego"), "AVISO", "TEST")

        dichos = []
        app.mensaje = lambda t, x, error=False: dichos.append(x)
        app.donde_buscar = lambda: tmp       # y el registro, en lo temporal
        guardadas = {}
        from ngplat import cli

        def falso_servir(raiz, preview, puerto, ventana=False, avisar=None,
                         apuntar=None):
            guardadas["avisar"] = avisar
            if avisar is not None:
                avisar("no encuentro Edge ni Chrome")
            return 0

        de_verdad = cli._servir
        cli._servir = falso_servir
        try:
            self.assertEqual(0, app.main([os.path.join(tmp, "juego")]))
        finally:
            cli._servir = de_verdad
        self.assertIsNotNone(guardadas.get("avisar"),
                             "el lanzador no ha dicho por donde avisar")
        self.assertTrue(any("Edge" in d for d in dichos), dichos)

    def test_la_explicacion_dice_que_hacer(self):
        """Un aviso que solo diga "no se puede" no sirve de nada: tiene que
        decir **que hacer**, porque quien lo lee no tiene consola ni manual
        delante."""
        texto = escritorio.explicacion("no encuentro Edge ni Chrome")
        self.assertIn("no encuentro Edge ni Chrome", texto)
        self.assertIn("NEOPLAT_NAVEGADOR", texto)
        self.assertIn("ngplat navegador", texto)



class TestCuandoElNavegadorPasaLaVentanaAOtro(unittest.TestCase):
    """El fallo de "127.0.0.1 rechazo la conexion", y es el bueno.

    Edge y Chrome, cuando ya hay uno corriendo con el mismo perfil, no abren
    la ventana ellos: **le pasan la orden al que ya estaba y el proceso que se
    acaba de lanzar se muere en el acto**. Y como lo que se vigilaba era ese
    proceso, el servidor se paraba dandose por cerrado. La ventana si se
    abria -la abria el otro Edge-, y lo que salia dentro era la conexion
    rechazada. Pasaba siempre, porque tener un Edge abierto es lo normal.

    Aqui el "navegador" es un programa que escribe la direccion y **se muere
    inmediatamente**, que es exactamente lo que hace Edge al traspasar. Lo que
    se exige es que el servidor **siga en pie**.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-traspaso-")
        cls.proyecto = os.path.join(cls.tmp, "juego")
        crear_proyecto(cls.proyecto, "TRASPASO", "TEST")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _lanzar(self, guion_del_navegador):
        falso = os.path.join(self.tmp, "ventana.py")
        with open(falso, "w", encoding="utf-8") as fh:
            fh.write(guion_del_navegador)
        apunte = os.path.join(self.tmp, "apunte.txt")
        if os.path.exists(apunte):
            os.remove(apunte)
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
        self.addCleanup(self._matar, proceso)
        direccion = ""
        for _ in range(300):
            if os.path.exists(apunte):
                with open(apunte, encoding="utf-8") as fh:
                    for trozo in fh.read().split():
                        if trozo.startswith("--app="):
                            direccion = trozo[len("--app="):]
                if direccion:
                    break
            time.sleep(0.1)
        self.assertTrue(direccion, "la ventana no se ha llegado a abrir")
        return proceso, direccion

    @staticmethod
    def _matar(proceso):
        if proceso.poll() is None:
            proceso.kill()
            proceso.wait(timeout=10)

    def test_el_servidor_sigue_en_pie_cuando_el_proceso_se_muere_solo(self):
        """La prueba del fallo. Contra 1.59 el servidor se paraba aqui."""
        proceso, direccion = self._lanzar(
            "import sys\n"
            "open(sys.argv[1], 'w').write(' '.join(sys.argv[2:]))\n")
        # que se muera del todo, y un poco mas: el vigilante mira cada segundo
        time.sleep(6)
        self.assertIsNone(proceso.poll(),
                          "el servidor se ha parado al morirse el navegador")
        with urllib.request.urlopen(direccion, timeout=15) as r:
            self.assertEqual(200, r.status)
            self.assertIn(b"<html", r.read(4096).lower())

    def test_y_al_dejar_de_latir_la_pagina_se_para(self):
        """Pero sin dejar un servidor colgado: si la pagina deja de latir, se
        para. Es lo que sustituye a vigilar el proceso."""
        proceso, direccion = self._lanzar(
            "import sys\n"
            "open(sys.argv[1], 'w').write(' '.join(sys.argv[2:]))\n")
        # se carga el editor y se manda un latido, como hace la pagina
        with urllib.request.urlopen(direccion, timeout=15) as r:
            self.assertEqual(200, r.status)
        partes = urllib.parse.urlsplit(direccion)
        latido = urllib.parse.urlunsplit(
            (partes.scheme, partes.netloc, "/latido", partes.query, ""))
        with urllib.request.urlopen(latido, timeout=15) as r:
            self.assertEqual(204, r.status)
        # y ahora se calla: el servidor tiene que irse detras
        proceso.wait(timeout=90)
        self.assertEqual(0, proceso.returncode)
        with self.assertRaises((urllib.error.URLError, OSError)):
            urllib.request.urlopen(direccion, timeout=5)


class TestElLatido(unittest.TestCase):
    """Lo que le dice al servidor que la ventana sigue abierta."""

    def test_el_servidor_lo_apunta(self):
        from ngplat.servidor import crear

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        preview = os.path.join(tmp, "preview.html")
        with open(preview, "w", encoding="utf-8") as fh:
            fh.write("<html><body>hola</body></html>")
        servidor, direccion = crear(tmp, preview, 0)
        self.addCleanup(servidor.server_close)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.shutdown)

        # recien arrancado no se sabe nada de ninguna pagina
        self.assertFalse(servidor.servida)
        self.assertEqual(0, servidor.latidos)
        self.assertIsNone(servidor.ultimo_latido)

        with urllib.request.urlopen(direccion, timeout=10) as r:
            self.assertEqual(200, r.status)
        self.assertTrue(servidor.servida)
        primero = servidor.ultimo_latido
        self.assertIsNotNone(primero)

        partes = urllib.parse.urlsplit(direccion)
        latido = urllib.parse.urlunsplit(
            (partes.scheme, partes.netloc, "/latido", partes.query, ""))
        time.sleep(0.05)
        with urllib.request.urlopen(latido, timeout=10) as r:
            self.assertEqual(204, r.status)
        self.assertEqual(1, servidor.latidos)
        self.assertGreater(servidor.ultimo_latido, primero)

    def test_sin_la_clave_no_cuenta(self):
        """Un latido de cualquiera mantendria el servidor vivo para siempre."""
        from ngplat.servidor import crear

        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        preview = os.path.join(tmp, "preview.html")
        with open(preview, "w", encoding="utf-8") as fh:
            fh.write("<html></html>")
        servidor, direccion = crear(tmp, preview, 0)
        self.addCleanup(servidor.server_close)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.shutdown)
        partes = urllib.parse.urlsplit(direccion)
        sin_clave = urllib.parse.urlunsplit(
            (partes.scheme, partes.netloc, "/latido", "", ""))
        with self.assertRaises(urllib.error.HTTPError) as caja:
            urllib.request.urlopen(sin_clave, timeout=10)
        self.assertEqual(403, caja.exception.code)
        self.assertEqual(0, servidor.latidos)

    def test_la_pagina_late_y_solo_servida_desde_el_servidor(self):
        """Abierta como file:// no hay a quien latir, y pedirlo seria un error
        en la consola del navegador cada tres segundos."""
        with open(os.path.join(KIT, "tools", "ngplat", "templates",
                               "preview.html"), encoding="utf-8") as fh:
            pagina = fh.read()
        self.assertIn("/latido?t=", pagina)
        self.assertIn("setInterval(latir", pagina)
        # el latido va colgado de `disponible`, que es http + clave
        trozo = pagina.split("this.disponible =", 1)[1][:900]
        self.assertIn("if (this.disponible)", trozo)
        self.assertIn("latir", trozo)


class TestElRegistroDeNeoPlatExe(unittest.TestCase):
    """Sin consola, un fallo que solo le pasa a quien lo usa no deja rastro.

    Esto existe por una tarde entera de arreglar a ciegas: lo unico que llegaba
    de vuelta era "sigue fallando". Ahora llega un fichero.
    """

    def test_apunta_al_lado_del_programa(self):
        app = _lanzador()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        app.donde_buscar = lambda: tmp
        app.apuntar("probando el registro")
        ruta = os.path.join(tmp, app.REGISTRO)
        self.assertTrue(os.path.isfile(ruta))
        with open(ruta, encoding="utf-8") as fh:
            escrito = fh.read()
        self.assertIn("probando el registro", escrito)
        # con su hora, que es la mitad de la utilidad
        self.assertRegex(escrito, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_si_no_se_puede_escribir_ahi_va_a_la_carpeta_temporal(self):
        """Un .exe dentro de Program Files no puede escribir a su lado."""
        app = _lanzador()
        app.donde_buscar = lambda: os.path.join(os.sep, "no", "existe", "esto")
        self.assertEqual(tempfile.gettempdir(),
                         os.path.dirname(app.donde_apuntar()))

    def test_apuntar_no_puede_fallar_nunca(self):
        """Es un registro, no el trabajo: si no se puede, se sigue."""
        app = _lanzador()

        def no_hay_donde():
            raise OSError("nada")

        app.donde_apuntar = no_hay_donde
        app.apuntar("esto no se va a poder apuntar")   # y no revienta

    def test_el_aviso_dice_donde_esta_apuntado(self):
        app = _lanzador()
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        app.donde_buscar = lambda: tmp
        texto = app.con_registro("no encuentro Edge")
        self.assertIn("no encuentro Edge", texto)
        self.assertIn(app.REGISTRO, texto)


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
