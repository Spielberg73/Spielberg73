"""El manual encuadernado: el renderizador de Markdown y los dos PDF.

Lo que se vigila aqui son dos cosas distintas.

La primera es el **renderizador**: convierte el Markdown del manual a HTML y
para en seco con lo que no sabe hacer, asi que lo que hay que comprobar es que
sabe hacer todo lo que de verdad aparece en el manual -y se comprueba contra
los documentos de verdad, no contra ejemplos inventados-.

La segunda es que los enlaces de un capitulo a otro **llegan a algun sitio**.
En GitHub se ve enseguida que un enlace esta roto porque sale un 404; dentro de
un PDF no se ve, se queda el texto en negro y nadie se entera.

El PDF en si solo se saca si esta WeasyPrint instalado. Si no esta, esa parte
se salta: es una dependencia de quien reparte el kit, no de quien lo usa.
"""

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

from comun import KIT

sys.path.insert(0, os.path.join(KIT, "tools"))

from ngplat import __version__ as VERSION    # noqa: E402
from ngplat import manual                    # noqa: E402


def _documentos():
    return [ruta for ruta, _, _ in manual.DOCUMENTOS]


class TestElRenderizadorSabeLoQueHayEnElManual(unittest.TestCase):
    """Todos los documentos pasan enteros, y sin perder nada por el camino."""

    def test_los_doce_documentos_se_convierten(self):
        for ruta in _documentos():
            entero = os.path.join(KIT, ruta)
            texto = io.open(entero, encoding="utf-8").read()
            try:
                html, cabeceras = manual.md_a_html(texto)
            except manual.ManualError as error:
                self.fail("%s: %s" % (ruta, error))
            self.assertTrue(cabeceras, "%s: no ha salido ni una cabecera" % ruta)
            self.assertTrue(html.strip(), "%s: ha salido vacio" % ruta)

    def test_salen_tantas_cabeceras_como_tiene_el_markdown(self):
        """Si una cabecera se pierde, el indice del PDF se queda sin ella y
        nadie lo ve hasta que busca algo y no esta."""
        for ruta in _documentos():
            texto = io.open(os.path.join(KIT, ruta), encoding="utf-8").read()
            dentro, escritas = False, 0
            for linea in texto.split("\n"):
                if linea.startswith("```"):
                    dentro = not dentro
                elif not dentro and re.match(r"^#{1,6} ", linea):
                    escritas += 1
            _, cabeceras = manual.md_a_html(texto)
            self.assertEqual(escritas, len(cabeceras),
                             "%s: %d cabeceras en el Markdown y %d en el HTML"
                             % (ruta, escritas, len(cabeceras)))

    def test_los_bloques_de_codigo_salen_enteros(self):
        """Lo que hay dentro de ``` se copia tal cual: ni se interpreta ni se
        recorta. En el manual hay diagramas de cajas y trozos de yaml donde un
        asterisco o un guion de menos cambia lo que se lee."""
        texto = ("Antes\n\n```\n| a | b |\n**no** es negrita\n  sangrado\n"
                 "```\n\nDespues\n")
        html, _ = manual.md_a_html(texto)
        self.assertIn("| a | b |", html)
        self.assertIn("**no** es negrita", html)
        self.assertIn("  sangrado", html)
        self.assertNotIn("<strong>", html)
        self.assertNotIn("<table>", html)

    def test_un_bloque_sin_cerrar_para_en_seco(self):
        with self.assertRaises(manual.ManualError):
            manual.md_a_html("texto\n\n```\nsin cerrar\n")

    def test_las_tablas_salen_con_su_cabecera(self):
        html, _ = manual.md_a_html("| a | b |\n|---|--:|\n| 1 | 2 |\n")
        self.assertIn("<thead>", html)
        self.assertIn("<th", html)
        self.assertIn("text-align:right", html)
        self.assertEqual(2, html.count("<td"))

    def test_el_codigo_en_linea_no_se_toca(self):
        """Dentro de los acentos graves, `<carpeta>` es texto y no una
        etiqueta, y un asterisco es un asterisco."""
        html, _ = manual.md_a_html("Pon `ngplat nuevo <carpeta>` y `a*b`.")
        self.assertIn("&lt;carpeta&gt;", html)
        self.assertIn("a*b", html)
        self.assertNotIn("<em>", html)

    def test_kbd_es_la_unica_etiqueta_que_pasa(self):
        html, _ = manual.md_a_html("Pulsa <kbd>E</kbd> y ya.")
        self.assertIn("<kbd>E</kbd>", html)

    def test_las_anclas_son_las_de_github(self):
        """Los enlaces del manual estan escritos para GitHub, asi que las
        anclas tienen que salir como las suyas: minusculas, con guiones y **con
        las tildes puestas**."""
        self.assertEqual("como-es-un-juego", manual._ancla("Como es un juego"))
        self.assertEqual("cómo-es-un-juego", manual._ancla("Cómo es un juego"))
        self.assertEqual("amiga_ram-a-qué-amiga-apunta-el-juego",
                         manual._ancla("`amiga_ram`: a qué Amiga apunta el juego"))


class TestLosEnlacesDelManualLlegan(unittest.TestCase):
    """Dentro del PDF un enlace roto no se ve. Aqui si."""

    @classmethod
    def setUpClass(cls):
        cls.html = manual.construir_html(KIT, "es", VERSION)

    def test_ningun_enlace_apunta_a_un_ancla_que_no_existe(self):
        anclas = set(re.findall(r"id=\"([^\"]+)\"", self.html))
        rotos = sorted({d for d in re.findall(r"href=\"#([^\"]+)\"", self.html)
                        if d not in anclas})
        self.assertEqual([], rotos,
                         "enlaces a anclas que no existen: %s" % rotos[:10])

    def test_los_doce_capitulos_estan(self):
        self.assertEqual(len(manual.DOCUMENTOS),
                         self.html.count("<h1 class=\"capitulo\""))

    def test_lleva_portada_e_indice(self):
        self.assertIn("class=\"portada\"", self.html)
        self.assertIn("class=\"indice\"", self.html)
        self.assertIn("target-counter", self.html)
        self.assertIn(VERSION, self.html)


class TestElManualEnIngles(unittest.TestCase):
    """La traduccion tiene que estar entera: un capitulo que falte deja un
    agujero en medio del PDF y el indice ya no cuadra con el castellano."""

    def test_estan_los_mismos_documentos(self):
        faltan = [ruta for ruta, _, ingles in manual.DOCUMENTOS
                  if not os.path.exists(os.path.join(
                      KIT, manual.ruta_del_documento(ruta, ingles, "en")))]
        self.assertEqual([], faltan, "faltan en ingles: %s" % faltan)

    def test_se_convierte_entero_y_sin_enlaces_rotos(self):
        html = manual.construir_html(KIT, "en", VERSION)
        anclas = set(re.findall(r"id=\"([^\"]+)\"", html))
        rotos = sorted({d for d in re.findall(r"href=\"#([^\"]+)\"", html)
                        if d not in anclas})
        self.assertEqual([], rotos, "enlaces rotos en ingles: %s" % rotos[:10])
        self.assertEqual(len(manual.DOCUMENTOS),
                         html.count("<h1 class=\"capitulo\""))

    def test_la_traduccion_tiene_las_mismas_cabeceras_que_el_original(self):
        """No se compara el texto -es otra lengua- pero si **cuantas**
        secciones tiene cada capitulo: si una traduccion se deja una seccion,
        aqui se ve."""
        malos = []
        for ruta, _, nombre in manual.DOCUMENTOS:
            ingles = os.path.join(
                KIT, manual.ruta_del_documento(ruta, nombre, "en"))
            if not os.path.exists(ingles):
                continue
            _, a = manual.md_a_html(
                io.open(os.path.join(KIT, ruta), encoding="utf-8").read())
            _, b = manual.md_a_html(io.open(ingles, encoding="utf-8").read())
            if len(a) != len(b):
                malos.append("%s: %d secciones en castellano y %d en ingles"
                             % (ruta, len(a), len(b)))
        self.assertEqual([], malos, "\n".join(malos))


class TestElPdfSale(unittest.TestCase):
    """Lo ultimo: que WeasyPrint lo pagine y salga un PDF que se pueda abrir."""

    @classmethod
    def setUpClass(cls):
        if not manual.motor():
            raise unittest.SkipTest("no esta WeasyPrint (pip3 install weasyprint)")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-manual-")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tmp", ""):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_el_castellano_sale_y_tiene_sus_tildes(self):
        salida = manual.generar(KIT, "es", VERSION,
                                os.path.join(self.tmp, "es.pdf"))
        self.assertTrue(os.path.getsize(salida) > 100 * 1024,
                        "el PDF ha salido demasiado pequeno")
        with open(salida, "rb") as fh:
            self.assertEqual(b"%PDF", fh.read(4))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "es.html")),
                         "se ha quedado el HTML intermedio sin borrar")
        if not shutil.which("pdftotext"):
            return
        texto = subprocess.run(["pdftotext", salida, "-"], capture_output=True,
                               text=True).stdout
        self.assertIn("máquinas", texto, "las tildes no han llegado al PDF")
        self.assertIn("game.yaml", texto)
        self.assertGreater(len(texto), 200000,
                           "el manual ha salido con muy poco texto")
