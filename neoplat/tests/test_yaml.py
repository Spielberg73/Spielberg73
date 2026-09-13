"""El analizador YAML incluido debe dar el mismo resultado que PyYAML."""

import os
import sys
import unittest

import comun  # noqa: F401  (ajusta sys.path)

from ngplat import miniyaml

EJEMPLOS = [
    """
juego:
  titulo: "Mi Juego"   # comentario
  vidas: 3
  gravedad: 0.28
  activo: true
  vacio:
""",
    """
jugador:
  tamano: [12, 22]
  anim: {frames: [1, 2, 3], velocidad: 6}
  nombre: sin comillas
""",
    """
niveles:
  - nombre: Bosque
    spawns:
      m: moneda
      s: seta
    mapa: |
      ..P..
      #####
  - nombre: Cueva
    mapa: |
      ..G..
      ##.##
""",
    """
lista_simple:
  - uno
  - 2
  - 3.5
  - no
""",
    # Una coleccion en linea puesta debajo de su clave. Es YAML del bueno y
    # `ngplat nuevo --genero carretera` lo escribia, pero el analizador de
    # repuesto no lo sabia leer: con PyYAML el proyecto abria y sin el -o sea,
    # en el ngplat.exe- no.
    """
objetos: {}
enemigos:
  {}
capas:
  [1, 2, 3]
""",
]


class TestMiniYaml(unittest.TestCase):
    def test_igual_que_pyyaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML no instalado")
        for texto in EJEMPLOS:
            self.assertEqual(miniyaml.loads(texto), yaml.safe_load(texto),
                             "difiere en:\n%s" % texto)

    def test_bloque_conserva_espacios(self):
        datos = miniyaml.loads("mapa: |\n  ..P..\n  #####\n")
        self.assertEqual(datos["mapa"], "..P..\n#####\n")

    def test_tabuladores_dan_error_claro(self):
        with self.assertRaises(miniyaml.YamlError) as ctx:
            miniyaml.loads("juego:\n\ttitulo: x\n")
        self.assertIn("tabuladores", str(ctx.exception))

    def test_los_proyectos_de_ngplat_nuevo_se_leen_sin_pyyaml(self):
        """Todo lo que escribe `ngplat nuevo` tiene que abrirlo el analizador
        de repuesto.

        Es **la** prueba que faltaba. Las demas cargan el proyecto con
        `load_project`, que usa PyYAML si esta instalado, asi que en una
        maquina con PyYAML -la de desarrollo- un yaml que solo entiende PyYAML
        pasa todas. En el `ngplat.exe`, que no lo lleva, no hay repuesto para
        el repuesto: ahi el proyecto no abre y lo unico que se ve es un error
        del analizador. Le paso al juego de conducir, que salia con un '{}'
        debajo de `objetos:`.

        Por eso aqui se llama a `miniyaml` **a proposito**, sin mirar si
        PyYAML esta o no.
        """
        import shutil
        import tempfile
        from ngplat.scaffold import GENEROS, ESTILOS, crear_proyecto

        tmp = tempfile.mkdtemp(prefix="neoplat-yaml-")
        try:
            for genero in GENEROS:
                for estilo in ESTILOS:
                    destino = os.path.join(tmp, "%s-%s" % (genero, estilo))
                    crear_proyecto(destino, "PRUEBA", "TEST", estilo, genero)
                    ruta = os.path.join(destino, "game.yaml")
                    try:
                        datos = miniyaml.load_file(ruta)
                    except miniyaml.YamlError as exc:
                        self.fail("'ngplat nuevo --genero %s --estilo %s' "
                                  "escribe un game.yaml que el analizador de "
                                  "repuesto no sabe leer: %s" % (genero, estilo, exc))
                    self.assertIn("juego", datos, "%s/%s" % (genero, estilo))
                    self.assertIn("niveles", datos, "%s/%s" % (genero, estilo))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_ejemplos_del_kit(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML no instalado")
        raiz = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples")
        encontrados = 0
        for carpeta, _, archivos in os.walk(raiz):
            for archivo in archivos:
                if not archivo.endswith((".yaml", ".yml")):
                    continue
                ruta = os.path.join(carpeta, archivo)
                with open(ruta, encoding="utf-8") as fh:
                    texto = fh.read()
                self.assertEqual(miniyaml.loads(texto), yaml.safe_load(texto), ruta)
                encontrados += 1
        self.assertGreater(encontrados, 0, "no hay ejemplos que comprobar")


if __name__ == "__main__":
    unittest.main()
