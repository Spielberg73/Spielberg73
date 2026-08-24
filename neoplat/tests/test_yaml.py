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
