"""El historial del proyecto: guardar copias y poder volver a ellas.

Es lo que hay debajo del boton "guardar" del editor y de `ngplat historial`.
Un juego grande se hace en muchas sesiones, y lo que no puede pasar es que un
guardado se lleve por delante lo de ayer.
"""

import os
import shutil
import tempfile
import unittest
import zipfile

import comun
from comun import KIT

from ngplat import historial
from ngplat.scaffold import crear_proyecto


class TestHistorial(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-historial-")
        self.raiz = os.path.join(self.tmp, "juego")
        crear_proyecto(self.raiz, "COPIAS", "TEST")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _yaml(self):
        return os.path.join(self.raiz, "game.yaml")

    def _tocar(self, texto):
        with open(self._yaml(), "a", encoding="utf-8") as fh:
            fh.write("\n# %s\n" % texto)

    # --- lo que entra y lo que no ---------------------------------------

    def test_la_copia_lleva_las_fuentes_y_no_lo_generado(self):
        os.makedirs(os.path.join(self.raiz, "build", "neogeo"), exist_ok=True)
        with open(os.path.join(self.raiz, "build", "neogeo", "rom.bin"), "wb") as fh:
            fh.write(b"\0" * 1024)
        with open(os.path.join(self.raiz, "preview.html"), "w") as fh:
            fh.write("<html>")
        rutas = historial.archivos_del_proyecto(self.raiz)
        self.assertIn("game.yaml", rutas)
        self.assertIn("graficos/heroe.png", rutas)
        self.assertTrue(any(r.startswith("sonidos/") for r in rutas), rutas)
        self.assertFalse([r for r in rutas if r.startswith("build/")],
                         "la copia se lleva lo que se puede volver a generar")
        self.assertNotIn("preview.html", rutas)

    def test_una_copia_se_puede_abrir_y_trae_el_proyecto(self):
        ficha = historial.copiar(self.raiz, "prueba")
        ruta = os.path.join(self.raiz, historial.HISTORIAL, str(ficha["archivo"]))
        with zipfile.ZipFile(ruta) as z:
            nombres = z.namelist()
        self.assertIn("neoplat.json", nombres)
        self.assertIn("proyecto/game.yaml", nombres)
        self.assertEqual(ficha["titulo"], "COPIAS")

    def test_el_historial_no_entra_en_sus_propias_copias(self):
        historial.copiar(self.raiz, "una")
        self._tocar("dos")
        ficha = historial.copiar(self.raiz, "dos")
        ruta = os.path.join(self.raiz, historial.HISTORIAL, str(ficha["archivo"]))
        with zipfile.ZipFile(ruta) as z:
            dentro = z.namelist()
        self.assertFalse([n for n in dentro if ".neoplat" in n],
                         "una copia se ha guardado dentro de otra")

    # --- guardar --------------------------------------------------------

    def test_guardar_dos_veces_sin_tocar_nada_no_hace_dos_copias(self):
        self.assertIsNotNone(historial.copiar(self.raiz, "una"))
        self.assertIsNone(historial.copiar(self.raiz, "otra"),
                          "ha copiado un proyecto que no ha cambiado")
        self.assertEqual(len(historial.listar(self.raiz)), 1)

    def test_cada_cambio_es_una_copia_nueva(self):
        historial.copiar(self.raiz, "una")
        self._tocar("dos")
        historial.copiar(self.raiz, "dos")
        self._tocar("tres")
        historial.copiar(self.raiz, "tres")
        copias = historial.listar(self.raiz)
        self.assertEqual([c["numero"] for c in copias], [3, 2, 1],
                         "las copias tienen que salir de la mas nueva a la mas vieja")
        self.assertEqual([c["motivo"] for c in copias], ["tres", "dos", "una"])

    def test_solo_se_guardan_las_ultimas(self):
        for i in range(6):
            self._tocar("cambio %d" % i)
            historial.copiar(self.raiz, "auto", maximo=3)
        copias = historial.listar(self.raiz)
        self.assertEqual(len(copias), 3, "no ha podado las copias viejas")
        self.assertEqual([c["numero"] for c in copias], [6, 5, 4])

    def test_el_motivo_se_limpia(self):
        ficha = historial.copiar(self.raiz, "../../algo raro!")
        self.assertEqual(ficha["motivo"], "algoraro")

    # --- recuperar ------------------------------------------------------

    def test_recuperar_devuelve_el_yaml_a_como_estaba(self):
        with open(self._yaml(), encoding="utf-8") as fh:
            original = fh.read()
        ficha = historial.copiar(self.raiz, "antes")
        self._tocar("esto se va a deshacer")
        historial.recuperar(self.raiz, int(ficha["numero"]))
        with open(self._yaml(), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), original)

    def test_recuperar_devuelve_tambien_los_dibujos(self):
        ruta = os.path.join(self.raiz, "graficos", "heroe.png")
        with open(ruta, "rb") as fh:
            original = fh.read()
        ficha = historial.copiar(self.raiz, "antes")
        with open(ruta, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n" + b"\0" * 32)   # un png destrozado
        historial.recuperar(self.raiz, int(ficha["numero"]))
        with open(ruta, "rb") as fh:
            self.assertEqual(fh.read(), original, "el dibujo no ha vuelto")

    def test_recuperar_quita_lo_que_no_estaba_en_esa_copia(self):
        ficha = historial.copiar(self.raiz, "antes")
        nuevo = os.path.join(self.raiz, "graficos", "invento.png")
        with open(nuevo, "wb") as fh:
            fh.write(b"\x89PNG\r\n\x1a\n")
        _escritos, sobrantes = historial.recuperar(self.raiz, int(ficha["numero"]))
        self.assertIn("graficos/invento.png", sobrantes)
        self.assertFalse(os.path.exists(nuevo),
                         "el proyecto se ha quedado mezclando dos versiones")

    def test_recuperar_guarda_antes_como_estaba(self):
        """Equivocarse de version tampoco puede perder nada."""
        ficha = historial.copiar(self.raiz, "antes")
        self._tocar("trabajo de hoy")
        historial.recuperar(self.raiz, int(ficha["numero"]))
        copias = historial.listar(self.raiz)
        self.assertEqual(copias[0]["motivo"], "antes-de-recuperar", copias)
        # y ese trabajo de hoy se puede volver a sacar
        historial.recuperar(self.raiz, int(copias[0]["numero"]))
        with open(self._yaml(), encoding="utf-8") as fh:
            self.assertIn("trabajo de hoy", fh.read())

    def test_recuperar_una_copia_que_no_existe(self):
        with self.assertRaises(historial.ErrorHistorial):
            historial.recuperar(self.raiz, 77)

    def test_un_proyecto_recuperado_sigue_cargando(self):
        from ngplat.project import load_project
        ficha = historial.copiar(self.raiz, "antes")
        with open(self._yaml(), "w", encoding="utf-8") as fh:
            fh.write("esto: [no cierra\n")
        historial.recuperar(self.raiz, int(ficha["numero"]))
        proyecto = load_project(self.raiz)       # si no carga, esto revienta
        self.assertEqual(proyecto.title, "COPIAS")

    # --- lo que tiene que rebotar ---------------------------------------

    def test_una_copia_no_puede_escribir_fuera_del_proyecto(self):
        """Un zip con '../' dentro no puede sacar archivos de la carpeta."""
        ficha = historial.copiar(self.raiz, "antes")
        ruta = os.path.join(self.raiz, historial.HISTORIAL, str(ficha["archivo"]))
        with zipfile.ZipFile(ruta, "a") as z:
            z.writestr("proyecto/../../fuera.txt", "no deberia salir")
        dentro = historial.contenido(self.raiz, int(ficha["numero"]))
        self.assertFalse([r for r in dentro if ".." in r], dentro)
        historial.recuperar(self.raiz, int(ficha["numero"]))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "fuera.txt")),
                         "una copia ha escrito fuera del proyecto")

    def test_una_carpeta_vacia_no_es_un_proyecto(self):
        vacia = os.path.join(self.tmp, "vacia")
        os.makedirs(vacia)
        with self.assertRaises(historial.ErrorHistorial):
            historial.copiar(vacia)


if __name__ == "__main__":
    unittest.main()
