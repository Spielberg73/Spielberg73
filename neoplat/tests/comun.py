"""Utilidades compartidas por las pruebas."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KIT, "tools"))

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


def cargar_demo(path: str):
    return build_project(load_project(path))


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
