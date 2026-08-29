"""Las barras del marcador, que son lo unico del motor que fabrica texto.

Las usan los marcadores de las cinco maquinas, y un fallo ahi no lo pilla ni la
traza (no es simulacion) ni el emulador (el jefe del ejemplo esta en el segundo
nivel). Asi que se compila el motor de verdad y se mira lo que escribe.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

import comun  # noqa: F401  (pone tools/ en el path)
from comun import KIT, cargar_demo
from ngplat.codegen import copy_engine, generate_gamedata
from ngplat.scaffold import crear_proyecto


def _compilar(tmp, nombre, vida=None, jugadores=None):
    """Monta un proyecto y compila el programa que imprime las barras.

    `vida` y `jugadores` cambian el `game.yaml` antes de generar: la barra de
    vida depende de los dos, y la unica forma de comprobarla de verdad es
    compilar el motor con esos valores dentro.
    """
    proyecto = os.path.join(tmp, nombre)
    crear_proyecto(proyecto, "BARRA", "TEST")
    yaml = os.path.join(proyecto, "game.yaml")
    with open(yaml, encoding="utf-8") as fh:
        texto = fh.read()
    if vida is not None:
        marca = "\n  vida: "
        assert marca in texto, "el andamiaje ya no trae 'vida:' en el jugador"
        corte = texto.index(marca) + len(marca)
        fin = texto.index("\n", corte)
        texto = texto[:corte] + str(vida) + texto[fin:]
    if jugadores is not None:
        marca = "  jugadores: 1"
        assert marca in texto, "el andamiaje ya no trae 'jugadores:'"
        texto = texto.replace(marca, "  jugadores: %d" % jugadores, 1)
    with open(yaml, "w", encoding="utf-8") as fh:
        fh.write(texto)

    build = cargar_demo(proyecto)
    out = os.path.join(tmp, "build-" + nombre)
    os.makedirs(os.path.join(out, "src"))
    for relativo, contenido in generate_gamedata(build).items():
        with open(os.path.join(out, relativo), "w", encoding="utf-8") as fh:
            fh.write(contenido)
    copy_engine(out)
    binario = os.path.join(tmp, "np_barra-" + nombre)
    hecho = subprocess.run(
        ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
         "-I", os.path.join(out, "src"), "-o", binario,
         os.path.join(KIT, "engine", "host", "np_barra.c"),
         os.path.join(out, "src", "np_world.c"),
         os.path.join(out, "src", "gamedata.c")],
        capture_output=True, text=True)
    if hecho.returncode:
        raise AssertionError("no compila:\n" + hecho.stderr)
    return binario


def _lineas(binario, *args):
    """Cada linea es "clave [contenido]"; devuelve {clave: contenido}."""
    salida = subprocess.run([binario] + list(args), capture_output=True,
                            text=True, check=True)
    return dict((l.split(" [", 1)[0], l.split(" [", 1)[1].rstrip("]"))
                for l in salida.stdout.strip().split("\n"))


class TestBarraDelJefe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("gcc"):
            raise unittest.SkipTest("no hay gcc para compilar el motor")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-marcador-")
        cls.lineas = _lineas(_compilar(cls.tmp, "jefe"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def test_sin_jefe_sale_en_blanco(self):
        """Asi la misma escritura borra lo que hubiera antes."""
        for caso in ("0/0", "0/5"):
            self.assertEqual(self.lineas[caso].strip(), "",
                             "con %s el marcador ensena algo" % caso)

    def test_a_tope_la_barra_esta_llena(self):
        for caso in ("5/5", "3/3", "1/1", "20/20"):
            self.assertEqual(self.lineas[caso], "BOSS " + "#" * 10, caso)

    def test_va_bajando(self):
        self.assertEqual(self.lineas["4/5"], "BOSS " + "#" * 8 + "  ")
        self.assertEqual(self.lineas["1/5"], "BOSS " + "#" * 2 + " " * 8)
        self.assertEqual(self.lineas["1/3"], "BOSS " + "#" * 4 + " " * 6)

    def test_mientras_le_quede_algo_se_ve_algo(self):
        """Con veinte golpes, uno solo seria medio bloque: se redondea hacia
        arriba para que la barra no desaparezca antes que el jefe."""
        self.assertEqual(self.lineas["1/20"], "BOSS " + "#" + " " * 9)
        self.assertEqual(self.lineas["19/20"], "BOSS " + "#" * 10)

    def test_siempre_ocupa_lo_mismo(self):
        """Ocupa siempre 15 caracteres: por eso al escribirla borra la anterior
        y el marcador no tiene que limpiar la fila."""
        for caso, texto in self.lineas.items():
            self.assertEqual(len(texto), 15, caso)


class TestBarraDeVida(unittest.TestCase):
    """La vida del jugador en el marcador.

    Se compila el motor con tres proyectos distintos porque la barra depende de
    `vida:` y de `jugadores:`, que son del juego y no del estado: con un solo
    proyecto no se veria ni el caso de un golpe ni el de dos jugadores.
    """

    @classmethod
    def setUpClass(cls):
        if not shutil.which("gcc"):
            raise unittest.SkipTest("no hay gcc para compilar el motor")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-vida-")
        cls.cuatro = _lineas(_compilar(cls.tmp, "v4", vida=4), "vida")
        cls.uno = _lineas(_compilar(cls.tmp, "v1", vida=1), "vida")
        cls.dos = _lineas(
            _compilar(cls.tmp, "v2p", vida=3, jugadores=2), "vida")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def test_ensena_lo_que_queda_y_lo_que_cabe(self):
        """Los llenos son los golpes que quedan y los puntos los perdidos: sin
        los puntos no se sabria si vas a tope o te falta media vida."""
        self.assertEqual(self.cuatro["p0 4"], "LIFE ####")
        self.assertEqual(self.cuatro["p0 3"], "LIFE ###.")
        self.assertEqual(self.cuatro["p0 1"], "LIFE #...")
        self.assertEqual(self.cuatro["p0 0"], "LIFE ....")

    def test_con_un_solo_golpe_no_sale(self):
        """Con `vida: 1` no hay nada que mirar: una barra de un cuadrado solo
        gastaria sitio, igual que la municion sin arma secundaria."""
        # que el proyecto tiene de verdad `vida: 1`: si el parche del yaml no
        # hubiera entrado, esto pasaria en vacio con la vida de por defecto
        self.assertEqual(sorted(k for k in self.uno if k.startswith("p0")),
                         ["p0 0", "p0 1", "p0 fuera"])
        for clave, texto in self.uno.items():
            self.assertEqual(texto.strip(), "",
                             "con vida: 1 el marcador ensena algo (%s)" % clave)

    def test_a_dos_cada_uno_la_suya(self):
        """Y alineadas: los cuadrados empiezan en el mismo sitio en las dos,
        aunque la etiqueta sea mas corta que 'LIFE'."""
        self.assertEqual(self.dos["p0 3"], "1P   ###")
        self.assertEqual(self.dos["p1 2"], "2P   ##.")
        self.assertEqual(self.dos["p0 3"].index("#"), 5)
        self.assertEqual(self.dos["p1 2"].index("#"), 5)

    def test_el_que_no_juega_no_sale(self):
        """El segundo de una partida a uno existe en el motor con `playing` a
        cero: su barra tiene que salir en blanco y no un cero de vida."""
        self.assertEqual(self.cuatro["p1 fuera"].strip(), "")
        self.assertEqual(self.dos["p0 fuera"].strip(), "")

    def test_fuera_de_la_partida_no_sale(self):
        """En el Amiga, el Jaguar y el Atari ST esa fila la usan el titulo y el
        "game over": si la barra siguiera escrita, se pisarian."""
        self.assertEqual(self.cuatro["titulo"].strip(), "")
        self.assertEqual(self.dos["titulo"].strip(), "")

    def test_ocupa_lo_que_necesita_y_al_borrar_ocupa_todo(self):
        """Escribir el marcador cuesta una escritura de VRAM por letra y esta
        barra se repinta en el frame del golpe, que es el mas caro de la
        partida: por eso no arrastra espacios de relleno. Cuando no ensena nada
        si sale entera, porque entonces lo que hace falta es borrar."""
        for clave, texto in self.cuatro.items():
            esperado = 14 if not texto.strip() else 9
            self.assertEqual(len(texto), esperado, "%s: %r" % (clave, texto))
        for clave, texto in self.uno.items():        # con `vida: 1` siempre borra
            self.assertEqual(len(texto), 14, clave)
        for clave, texto in self.dos.items():
            esperado = 14 if not texto.strip() else 8
            self.assertEqual(len(texto), esperado, "%s: %r" % (clave, texto))


if __name__ == "__main__":
    unittest.main()
