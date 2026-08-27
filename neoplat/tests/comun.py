"""Utilidades compartidas por las pruebas."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KIT, "tools"))

from ngplat import sistemas                     # noqa: E402
from ngplat.build import build_project          # noqa: E402
from ngplat.project import load_project         # noqa: E402
from ngplat.scaffold import crear_proyecto      # noqa: E402


class ProyectoTemporal:
    """Crea un proyecto de ejemplo en una carpeta temporal."""

    def __init__(self, titulo: str = "PRUEBA"):
        self.titulo = titulo
        self.path = ""

    def __enter__(self) -> str:
        self.path = os.path.join(tempfile.mkdtemp(prefix="neoplat-"), "juego")
        crear_proyecto(self.path, self.titulo, "TEST")
        return self.path

    def __exit__(self, *args) -> None:
        shutil.rmtree(os.path.dirname(self.path), ignore_errors=True)


# Un nivel de tres pantallas exactas (60x14 tiles) para probar la camara por
# pantallas. Dos cosas a proposito:
#
#   - no tiene pinchos ni agujeros, asi el jugador puede correr a la derecha
#     todo el rato sin morirse y las medidas del emulador salen limpias;
#   - cada pantalla lleva un bloque de piedra a una altura distinta, para que
#     al saltar de una a otra cambie media pantalla y se pueda medir. Los
#     bloques van por el aire, sin tapar el camino del suelo.

def _mapa_por_pantallas() -> list:
    ancho, alto, pantalla = 60, 14, 20
    filas = [["."] * ancho for _ in range(alto)]
    for p in range(ancho // pantalla):
        x = p * pantalla + 4
        techo = 3 + p * 2                      # cada pantalla, mas abajo
        for fila in range(techo, techo + 2):
            for i in range(10):
                filas[fila][x + i] = ","
        for i in range(5):                     # una plataforma con monedas
            filas[techo + 4][x + 2 + i] = "="
            if i < 3:
                filas[techo + 3][x + 3 + i] = "c"
    filas[alto - 2][1] = "P"
    filas[alto - 2][34] = "s"
    filas[alto - 2][ancho - 3] = "G"
    filas[alto - 1] = ["#"] * ancho
    return ["".join(f) for f in filas]


_MAPA_PANTALLAS = _mapa_por_pantallas()


def proyecto_por_pantallas(destino: str, titulo: str = "PANTALLAS") -> str:
    """Proyecto de ejemplo con `camara: pantallas` y niveles de pantallas enteras."""
    crear_proyecto(destino, titulo, "TEST")
    yaml = os.path.join(destino, "game.yaml")
    with open(yaml, encoding="utf-8") as fh:
        texto = fh.read()
    assert "  camara: scroll" in texto, "el andamiaje ya no trae la camara"
    texto = texto.replace("  camara: scroll", "  camara: pantallas", 1)
    # se sustituyen los dos mapas por el de tres pantallas
    cabeza, _, _ = texto.partition("niveles:")
    mapa = "\n".join("      " + fila for fila in _MAPA_PANTALLAS)
    texto = cabeza + ("niveles:\n"
                      '  - nombre: "UNA"\n'
                      '    fondo: "#101830"\n'
                      "    musica: bosque\n"
                      "    mapa: |\n%s\n" % mapa)
    with open(yaml, "w", encoding="utf-8") as fh:
        fh.write(texto)
    return destino


def proyecto_a_dos(destino: str, titulo: str = "DOS") -> str:
    """Proyecto de ejemplo con `jugadores: 2`.

    Se le pone el nivel de tres pantallas (que no tiene ni pinchos ni agujeros)
    porque las pruebas de emulador dejan a los dos corriendo a la derecha un
    buen rato: con el nivel del andamiaje uno de los dos se mataria y la
    comparacion entre partidas dejaria de medir los mandos."""
    crear_proyecto(destino, titulo, "TEST")
    yaml = os.path.join(destino, "game.yaml")
    with open(yaml, encoding="utf-8") as fh:
        texto = fh.read()
    assert "  jugadores: 1" in texto, "el andamiaje ya no trae los jugadores"
    texto = texto.replace("  jugadores: 1", "  jugadores: 2", 1)
    cabeza, _, _ = texto.partition("niveles:")
    mapa = "\n".join("      " + fila for fila in _MAPA_PANTALLAS)
    texto = cabeza + ("niveles:\n"
                      '  - nombre: "UNA"\n'
                      '    fondo: "#101830"\n'
                      "    musica: bosque\n"
                      "    mapa: |\n%s\n" % mapa)
    with open(yaml, "w", encoding="utf-8") as fh:
        fh.write(texto)
    return destino


def cargar_demo(path: str, sistema: str = ""):
    """Carga un proyecto y lo deja listo para el sistema que se pida.

    Sin `sistema` se usa el del propio game.yaml (Neo Geo, si no dice otra cosa).
    """
    proyecto = load_project(path)
    build = build_project(proyecto)
    maquina = sistemas.obtener(sistema or proyecto.system)
    maquina.preparar(build)
    return build


def escribir(path: str, contenido: str) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(contenido)
    return path


MAPA_MINIMO = "\n".join([
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "....................",
    "..........c.........",
    "....................",
    "......=====.........",
    "P.........s.......G.",
    "####################",
])

YAML_MINIMO = """
juego:
  titulo: "MINIMO"
jugador:
  sprite: h.png
  caja: [12, 14]
tiles:
  imagen: t.png
  leyenda:
    '.': {tile: 0, tipo: vacio}
    '#': {tile: 1, tipo: solido}
    '=': {tile: 1, tipo: plataforma}
    'G': {tile: 1, tipo: meta}
enemigos:
  bicho:
    sprite: e.png
objetos:
  moneda:
    sprite: o.png
    puntos: 5
spawns:
  s: bicho
  c: moneda
niveles:
  - nombre: UNO
    mapa: |
%s
"""


def proyecto_minimo(carpeta: str, yaml_texto: str = "") -> str:
    """Escribe un proyecto valido muy pequeno y devuelve la ruta del game.yaml."""
    from ngplat.png import Image, write_png

    os.makedirs(carpeta, exist_ok=True)
    for nombre, color in (("h.png", (200, 40, 40, 255)), ("e.png", (40, 200, 40, 255)),
                          ("o.png", (240, 200, 40, 255)), ("t.png", (90, 90, 120, 255))):
        if nombre == "t.png":     # tileset de dos tiles: vacio y solido
            filas = []
            for _ in range(16):
                filas.extend([(0, 0, 0, 0)] * 16)
                filas.extend([color] * 16)
            write_png(os.path.join(carpeta, nombre), Image(32, 16, filas))
            continue
        write_png(os.path.join(carpeta, nombre), Image(16, 16, [color] * (16 * 16)))
    texto = yaml_texto or (YAML_MINIMO % "\n".join("      " + f for f in MAPA_MINIMO.split("\n")))
    return escribir(os.path.join(carpeta, "game.yaml"), texto)
