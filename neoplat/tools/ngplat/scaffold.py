"""`ngplat nuevo`: crea un proyecto jugable desde el primer segundo."""

from __future__ import annotations

import os
from typing import List

from . import art
from .errors import ProjectError
from .png import write_png

ANCHO_1 = 48
ANCHO_2 = 56


def _fila(patron: str, ancho: int) -> str:
    if len(patron) > ancho:
        raise ValueError("fila demasiado larga: %d > %d" % (len(patron), ancho))
    return patron.ljust(ancho, ".")


def _nivel_1() -> List[str]:
    a = ANCHO_1
    return [
        _fila("", a),
        _fila("", a),
        _fila("...........................ccc", a),
        _fila("..........................=====", a),
        _fila("", a),
        _fila("..........ccc.....................ccc", a),
        _fila(".........=====...................=====", a),
        _fila("", a),
        _fila("....c.........................c", a),
        _fila("...====......s.......c.......====", a),
        _fila("", a),
        _fila("......................c...............c.c.c", a),
        _fila("...................========.........", a),
        _fila("..............^^..............s.......", a),
        _fila("P........s....##......................#####G####", a),
        _fila("##########################..#####################"[:a], a),
    ]


def _nivel_2() -> List[str]:
    a = ANCHO_2
    return [
        _fila("", a),
        _fila(".....................c.c.c", a),
        _fila("....................=======", a),
        _fila("", a),
        _fila("..........c...............................ccc", a),
        _fila(".........===.....m...................========", a),
        _fila("", a),
        _fila("...............=====......c.c.c", a),
        _fila("..........................=======.......m", a),
        _fila("....c................................", a),
        _fila("...====.......s...........s..........c......", a),
        _fila("..........................######....====", a),
        _fila("", a),
        _fila("........^^^.......m...........^^^.......", a),
        _fila("P.......###..................###.......s.....G", a),
        _fila("#########################..#######################"[:a], a),
    ]


GAME_YAML = """# Proyecto NeoPlat: un juego de plataformas que compila para Neo Geo.
#
#   ngplat probar     -> abre el preview jugable en el navegador
#   ngplat compilar   -> genera el proyecto en C y las ROMs graficas
#
# Toda la configuracion esta aqui. Los graficos son PNG normales de hasta
# 15 colores (mas el transparente).

juego:
  titulo: "{titulo}"
  autor: "{autor}"
  vidas: 3
  tiempo: 0            # segundos por nivel (0 = sin limite)
  fondo: "#101830"

jugador:
  sprite: graficos/heroe.png
  frame: [16, 16]      # tamano de cada fotograma de la hoja
  caja: [10, 15]       # caja de colision (mas estrecha que el dibujo)
  velocidad: 1.6       # pixeles por frame
  aceleracion: 0.30
  friccion: 0.35
  salto: 4.3
  gravedad: 0.28
  doble_salto: no
  pisar_enemigos: si
  animaciones:
    quieto: {{frames: [0], velocidad: 30}}
    correr: {{frames: [1, 2, 3, 2], velocidad: 6}}
    saltar: {{frames: [4]}}
    caer:   {{frames: [5]}}

tiles:
  imagen: graficos/tiles.png
  leyenda:
    '.': {{tile: 0, tipo: vacio}}
    '#': {{tile: 1, tipo: solido}}
    ',': {{tile: 5, tipo: solido}}
    '=': {{tile: 2, tipo: plataforma}}
    '^': {{tile: 3, tipo: peligro}}
    'G': {{tile: 4, tipo: meta}}

enemigos:
  seta:
    sprite: graficos/enemigo.png
    caja: [14, 12]
    comportamiento: patrulla
    velocidad: 0.4
    puntos: 100
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 14}}
      correr: {{frames: [0, 1], velocidad: 10}}
  mosca:
    sprite: graficos/enemigo.png
    caja: [14, 12]
    comportamiento: volador
    velocidad: 0.6
    amplitud: 28
    periodo: 150
    puntos: 200
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 6}}

objetos:
  moneda:
    sprite: graficos/moneda.png
    caja: [10, 10]
    puntos: 10
    animaciones:
      quieto: {{frames: [0, 1, 2, 3], velocidad: 7}}

# Simbolos del mapa que colocan enemigos y objetos.
spawns:
  s: seta
  m: mosca
  c: moneda

niveles:
{niveles}"""


def _nivel_yaml(nombre: str, filas: List[str], fondo: str) -> str:
    cuerpo = "\n".join("      " + fila for fila in filas)
    return (
        "  - nombre: \"%s\"\n"
        "    fondo: \"%s\"\n"
        "    mapa: |\n%s\n" % (nombre, fondo, cuerpo)
    )


def crear_proyecto(destino: str, titulo: str = "MI JUEGO", autor: str = "") -> List[str]:
    """Crea la carpeta del proyecto con game.yaml y graficos de ejemplo."""
    if os.path.exists(destino) and os.listdir(destino):
        raise ProjectError(
            "la carpeta '%s' ya existe y no esta vacia" % destino,
            hint="elige otro nombre o borra la carpeta",
        )
    os.makedirs(os.path.join(destino, "graficos"), exist_ok=True)
    creados: List[str] = []

    for relativo, imagen in art.todos().items():
        ruta = os.path.join(destino, relativo)
        write_png(ruta, imagen)
        creados.append(relativo)

    niveles = (
        _nivel_yaml("BOSQUE", _nivel_1(), "#101830")
        + _nivel_yaml("CUEVA", _nivel_2(), "#180c20")
    )
    contenido = GAME_YAML.format(titulo=titulo.upper()[:24], autor=autor[:24], niveles=niveles)
    with open(os.path.join(destino, "game.yaml"), "w", encoding="utf-8") as fh:
        fh.write(contenido)
    creados.append("game.yaml")

    with open(os.path.join(destino, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("build/\npreview.html\n")
    creados.append(".gitignore")
    return creados
