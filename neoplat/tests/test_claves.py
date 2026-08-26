"""La tabla de nombres del editor tiene que coincidir con lo que lee el kit.

Si alguien anade una opcion nueva al game.yaml y se olvida de la tabla (o al
reves), el editor escribiria una clave que el lector no entiende. Aqui se
comprueba una por una: se escribe un game.yaml con cada alias y se lee.
"""

import os
import shutil
import tempfile
import unittest

import comun
from comun import MAPA_MINIMO, YAML_MINIMO, proyecto_minimo

from ngplat.claves import CAMPOS, OPCIONES, RANGOS
from ngplat.project import BEHAVIORS, ITEM_EFFECTS, load_project

VALORES = {
    "titulo": '"OTRO"', "autor": '"YO"', "vidas": "4", "tiempo": "30",
    "hud": "no", "fondo": '"#204060"', "camara": '"pantallas"',
    "velocidad": "2.0", "aceleracion": "0.4", "friccion": "0.3",
    "control_aire": "0.2", "salto": "5.0", "corte_salto": "1.2",
    "gravedad": "0.3", "max_caida": "7", "doble_salto": "si",
    "coyote": "8", "buffer_salto": "7", "pisar_enemigos": "no",
    "rebote": "3.0", "vida": "3", "invulnerable": "120",
    "comportamiento": "volador", "dano": "2", "puntos": "250",
    "pisable": "no", "girar_en_borde": "no", "rango": "120",
    "amplitud": "40", "periodo": "90", "intervalo": "60",
    "efecto": "vida", "cantidad": "2", "nombre": '"OTRO NIVEL"',
    "musica": "tema", "fondos": "[]",
}


def _yaml(reemplazos):
    texto = YAML_MINIMO % "\n".join("      " + f for f in MAPA_MINIMO.split("\n"))
    for viejo, nuevo in reemplazos:
        texto = texto.replace(viejo, nuevo, 1)
    return texto


class TestClaves(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-claves-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cargar(self, texto):
        return load_project(proyecto_minimo(self.tmp, texto))

    def _probar_seccion(self, seccion, ancla, sangria):
        for campo, alias in CAMPOS[seccion].items():
            if campo not in VALORES:
                continue
            for nombre in alias:
                linea = "%s%s: %s" % (sangria, nombre, VALORES[campo])
                texto = _yaml([(ancla, ancla + "\n" + linea)])
                try:
                    self._cargar(texto)
                except Exception as exc:       # noqa: BLE001
                    self.fail("'%s: %s' no lo acepta el lector (%s)"
                              % (nombre, VALORES[campo], exc))

    def test_alias_del_juego(self):
        self._probar_seccion("juego", 'juego:', "  ")

    def test_alias_del_jugador(self):
        self._probar_seccion("jugador", "jugador:", "  ")

    def test_alias_de_los_enemigos(self):
        self._probar_seccion("enemigo", "  bicho:", "    ")

    def test_alias_de_los_objetos(self):
        self._probar_seccion("objeto", "  moneda:", "    ")

    def test_alias_de_los_niveles(self):
        for campo, alias in CAMPOS["nivel"].items():
            if campo in ("musica", "fondos"):
                continue          # necesitan que exista la musica o la capa
            for nombre in alias:
                texto = _yaml([("  - nombre: UNO",
                                "  - nombre: UNO\n    %s: %s" % (nombre, VALORES[campo]))])
                try:
                    self._cargar(texto)
                except Exception as exc:       # noqa: BLE001
                    self.fail("'%s' en un nivel no lo acepta el lector (%s)" % (nombre, exc))

    def test_los_valores_de_lista_existen(self):
        for valor in OPCIONES["comportamiento"]:
            self.assertIn(valor, BEHAVIORS, "comportamiento '%s' desconocido" % valor)
        for valor in OPCIONES["efecto"]:
            self.assertIn(valor, ITEM_EFFECTS, "efecto '%s' desconocido" % valor)

    def test_todos_los_campos_con_rango_son_numeros(self):
        for campo, rango in RANGOS.items():
            self.assertLess(rango["min"], rango["max"], campo)
            self.assertGreater(rango["paso"], 0, campo)


if __name__ == "__main__":
    unittest.main()
