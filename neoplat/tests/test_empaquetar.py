"""El empaquetado: los ZIP y, sobre todo, que el .exe lleve todo lo que abre.

El ejecutable de Windows es el kit entero metido en un archivo, y ahi es facil
que se quede algo fuera: el motor en C, una plantilla, el preview o uno de los
modulos que el proyecto generado se lleva dentro. Si falta, no se entera nadie
hasta que alguien compila para esa maquina y le salta un FileNotFoundError.

Asi que aqui se monta un **arbol de mentira** como el que deja PyInstaller al
arrancar el .exe, se pone a `paths.py` en modo congelado y se comprueba que
todo lo que el kit abre en marcha esta ahi.
"""

import importlib
import os
import shutil
import sys
import tempfile
import unittest
import zipfile

import comun
from comun import KIT

sys.path.insert(0, KIT)
import empaquetar  # noqa: E402

from ngplat import paths, sistemas  # noqa: E402


class TestZips(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-zip-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _hacer(self, entradas, prefijo):
        destino = os.path.join(self.tmp, "prueba.zip")
        empaquetar.hacer_zip(destino, entradas, prefijo)
        with zipfile.ZipFile(destino) as zf:
            return zf.namelist()

    def test_los_paquetes_llevan_la_version_en_el_nombre(self):
        """Para saber que se esta probando sin abrir nada."""
        from ngplat import __version__
        empaquetar.main([])
        salidas = sorted(os.listdir(empaquetar.DIST))
        self.assertIn("neoplat-kit-%s.zip" % __version__, salidas)
        self.assertIn("neoplat-docs-%s.zip" % __version__, salidas)
        with zipfile.ZipFile(os.path.join(empaquetar.DIST,
                                          "neoplat-kit-%s.zip" % __version__)) as zf:
            nombres = zf.namelist()
        self.assertTrue(all(n.startswith("neoplat-%s/" % __version__)
                            for n in nombres),
                        "todo tiene que colgar de una carpeta con la version")
        self.assertIn("neoplat-%s/CAMBIOS.md" % __version__, nombres,
                      "el historial de versiones viaja con el kit")

    def test_el_zip_de_docs_lleva_la_documentacion(self):
        nombres = self._hacer(empaquetar.DOCS, "docs")
        self.assertIn("docs/README.md", nombres)
        for pagina in ("formato", "tutorial", "sonido", "neogeo", "megadrive",
                       "amiga", "jaguar", "atarist", "x68000", "editor"):
            self.assertIn("docs/docs/%s.md" % pagina, nombres,
                          "falta docs/%s.md en el ZIP" % pagina)

    def test_el_zip_del_kit_lleva_lo_que_hace_falta_para_usarlo(self):
        nombres = set(self._hacer(empaquetar.KIT, "k"))
        for imprescindible in ("k/ngplat", "k/Makefile", "k/tools/ngplat/cli.py",
                               "k/engine/core/np_world.c", "k/preview/np_core.js",
                               "k/tools/ngplat/templates/preview.html",
                               "k/examples/bosque-magico/game.yaml"):
            self.assertIn(imprescindible, nombres, "falta " + imprescindible)

    def test_no_se_cuela_lo_generado(self):
        nombres = self._hacer(empaquetar.KIT, "k")
        for nombre in nombres:
            self.assertNotIn("/build/", nombre, "se ha colado " + nombre)
            self.assertNotIn("__pycache__", nombre, "se ha colado " + nombre)
            self.assertFalse(nombre.endswith(".pyc"), "se ha colado " + nombre)

    def test_el_mismo_codigo_da_el_mismo_zip(self):
        """Las fechas van fijas a proposito: dos paquetes del mismo codigo
        tienen que salir byte a byte iguales para poder compararlos."""
        uno = os.path.join(self.tmp, "1.zip")
        otro = os.path.join(self.tmp, "2.zip")
        empaquetar.hacer_zip(uno, empaquetar.DOCS, "d")
        empaquetar.hacer_zip(otro, empaquetar.DOCS, "d")
        with open(uno, "rb") as a, open(otro, "rb") as b:
            self.assertEqual(a.read(), b.read())


class TestElExeLlevaTodo(unittest.TestCase):
    """Monta el arbol que deja PyInstaller y comprueba que no falta nada."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-exe-")
        cls.raiz = os.path.join(cls.tmp, "_MEI")
        for origen, dentro in empaquetar.DATOS:
            desde = os.path.join(KIT, origen.replace("/", os.sep))
            hasta = os.path.join(cls.raiz, dentro.replace("/", os.sep))
            if os.path.isdir(desde):
                shutil.copytree(desde, hasta, dirs_exist_ok=True)
            else:
                os.makedirs(hasta, exist_ok=True)
                shutil.copy2(desde, hasta)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)
        # dejar paths.py como estaba, que lo usan las demas pruebas
        sys.frozen = False
        del sys.frozen
        if hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS
        importlib.reload(paths)

    def _congelado(self):
        sys.frozen = True
        sys._MEIPASS = self.raiz
        return importlib.reload(paths)

    def test_el_motor_de_las_seis_maquinas_esta_dentro(self):
        congelado = self._congelado()
        try:
            faltan = []
            for nombre in ("neogeo", "megadrive", "amiga", "jaguar", "atarist",
                           "x68000"):
                for origen, _destino in sistemas.obtener(nombre).archivos_motor:
                    ruta = os.path.join(congelado.ENGINE_DIR,
                                        origen.replace("/", os.sep))
                    if not os.path.isfile(ruta):
                        faltan.append("%s: %s" % (nombre, origen))
            self.assertEqual(faltan, [],
                             "el .exe no llevaria estos archivos del motor: %s"
                             % ", ".join(faltan))
        finally:
            self._descongelar()

    def test_las_plantillas_y_el_preview_estan_dentro(self):
        congelado = self._congelado()
        try:
            for nombre in os.listdir(os.path.join(KIT, "tools", "ngplat", "templates")):
                self.assertTrue(
                    os.path.isfile(os.path.join(congelado.TEMPLATES_DIR, nombre)),
                    "falta la plantilla " + nombre)
            for nombre in os.listdir(os.path.join(KIT, "preview")):
                if nombre.endswith(".js"):
                    self.assertTrue(
                        os.path.isfile(os.path.join(congelado.PREVIEW_DIR, nombre)),
                        "falta el preview " + nombre)
        finally:
            self._descongelar()

    def test_los_modulos_que_se_copian_al_proyecto_estan_dentro(self):
        """El Amiga y el Atari ST meten estos modulos en el proyecto generado.
        De un modulo ya congelado no se puede leer el fuente, asi que tienen
        que ir como datos."""
        congelado = self._congelado()
        try:
            for modulo in congelado.FUENTES_COPIADAS:
                texto = congelado.fuente_del_kit(modulo)
                self.assertIn("def ", texto, "%s ha salido vacio" % modulo)
        finally:
            self._descongelar()

    def _descongelar(self):
        if hasattr(sys, "frozen"):
            del sys.frozen
        if hasattr(sys, "_MEIPASS"):
            del sys._MEIPASS
        importlib.reload(paths)


class TestFuentesCopiadas(unittest.TestCase):
    def test_la_lista_es_la_que_usan_los_sistemas(self):
        """Si alguien anade un modulo a un sistema y se olvida de la lista, el
        .exe se rompe solo para esa maquina. Aqui se compara con lo que dicen
        los propios archivos."""
        import re
        usados = set()
        carpeta = os.path.join(KIT, "tools", "ngplat", "sistemas")
        for nombre in os.listdir(carpeta):
            if not nombre.endswith(".py"):
                continue
            with open(os.path.join(carpeta, nombre), encoding="utf-8") as fh:
                usados.update(re.findall(r'fuente_del_kit\("([^"]+)"\)', fh.read()))
        self.assertEqual(usados, set(paths.FUENTES_COPIADAS),
                         "FUENTES_COPIADAS no coincide con lo que piden los sistemas")


if __name__ == "__main__":
    unittest.main()
