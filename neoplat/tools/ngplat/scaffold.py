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


def _poner(ancho: int, simbolos: dict, relleno: str = ".") -> str:
    """Construye una fila colocando cada simbolo en su columna.

    Es mas facil de leer (y de no descuadrar) que contar puntos a mano.
    """
    fila = [relleno] * ancho
    for columna, simbolo in simbolos.items():
        for i, ch in enumerate(simbolo):
            if columna + i < ancho:
                fila[columna + i] = ch
    return "".join(fila)


def _suelo(ancho: int, huecos: List[tuple]) -> str:
    """Fila de suelo con huecos [(columna, ancho), ...]."""
    fila = ["#"] * ancho
    for columna, largo in huecos:
        for i in range(largo):
            if columna + i < ancho:
                fila[columna + i] = "."
    return "".join(fila)


# Reglas de diseño que siguen los niveles de ejemplo (y que comprueba el bot de
# tests/nivel_jugable.js):
#   - el salto sube 2 tiles y cruza 3, asi que ningun hueco pasa de 2 tiles
#   - despues de un enemigo hay al menos 8 tiles libres: al pisarlo sales
#     rebotado hacia delante y no puedes caer sobre pinchos
#   - los pinchos van de uno en uno y con suelo llano antes y despues

def _nivel_1() -> List[str]:
    """Nivel de entrada: saltar, coger monedas, pisar un enemigo, esquivar pinchos."""
    a = ANCHO_1
    return [
        _fila("", a),
        _fila("", a),
        _fila("", a),
        _fila("", a),
        _poner(a, {30: "ccc"}),
        _poner(a, {29: "====="}),
        _fila("", a),
        _poner(a, {15: "ccc"}),
        _poner(a, {14: "====="}),
        _fila("", a),
        _poner(a, {5: "ccc", 38: "ccc"}),
        _poner(a, {4: "=====", 37: "====="}),
        _fila("", a),
        _poner(a, {10: "c", 22: "c", 33: "c"}),
        _poner(a, {0: "P", 8: "s", 18: "^", 28: "s", 40: "c", 44: "G"}),
        _suelo(a, [(34, 2)]),
    ]


def _nivel_2() -> List[str]:
    """Segundo nivel: voladores, saltos encadenados y un hueco mas largo."""
    a = ANCHO_2
    return [
        _fila("", a),
        _fila("", a),
        _fila("", a),
        _poner(a, {11: "ccc"}),
        _poner(a, {10: "====="}),
        _fila("", a),
        _poner(a, {24: "ccc", 40: "ccc"}),
        _poner(a, {23: "=====", 39: "====="}),
        _fila("", a),
        _poner(a, {19: "m", 37: "m"}),
        _poner(a, {4: "ccc", 48: "ccc"}),
        _poner(a, {3: "=====", 47: "====="}),
        _fila("", a),
        _poner(a, {6: "c", 17: "c", 27: "c", 38: "c", 45: "c"}),
        _poner(a, {0: "P", 8: "s", 18: "^", 30: "s", 42: "^", 53: "G"}),
        _suelo(a, [(24, 2), (47, 2)]),
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
  camara: scroll       # scroll (el escenario se desliza) o pantallas
  amiga: 32colores     # solo en Amiga: 32colores o 8colores (con parallax)
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
  vida: 2              # golpes que aguanta antes de perder una vida
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
    caja: [12, 11]
    comportamiento: patrulla
    velocidad: 0.4
    puntos: 100
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 14}}
      correr: {{frames: [0, 1], velocidad: 10}}
  mosca:
    sprite: graficos/enemigo.png
    caja: [12, 11]
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

# Capas de fondo con scroll propio (parallax). Van de la mas lejana a la mas
# cercana. 'velocidad' es la fraccion del scroll del escenario: 0 = quieta,
# 1 = se mueve igual que el suelo. 'y' es donde empieza en la pantalla.
fondos:
  - nombre: cielo
    imagen: graficos/cielo.png
    velocidad: 0.2
    y: 0
  - nombre: arboles
    imagen: graficos/arboles.png
    velocidad: 0.5
    y: 144

# Sonido. El chip de la Neo Geo (YM2610) tiene tres canales de onda cuadrada:
# dos los usa la musica y uno los efectos. Las notas se escriben en espanol
# (do re mi fa sol la si) o en ingles (c d e f g a b), con '#' o 'b' para las
# alteraciones, el numero de octava detras y '-' para los silencios.
sonido:
  efectos:
    empezar: {{notas: "do5 sol5", velocidad: 4}}
    salto:   {{tipo: barrido, desde: 320, hasta: 900, duracion: 6}}
    moneda:  {{notas: "mi6 sol6", velocidad: 3}}
    pisar:   {{tipo: barrido, desde: 800, hasta: 200, duracion: 6}}
    golpe:   {{tipo: ruido, duracion: 10}}
    muerte:  {{notas: "sol4 mi4 do4 sol3", velocidad: 6}}
    meta:    {{notas: "do5 mi5 sol5 do6", velocidad: 6}}
  musica:
    bosque:
      velocidad: 8          # frames que dura cada nota (mas alto = mas lento)
      pistas:
        - "do4 mi4 sol4 mi4 | fa4 la4 do5 la4 | sol4 si4 re5 si4 | do5 - sol4 -"
        - "do3 -  do3 -     | fa3 -  fa3 -    | sol3 - sol3 -     | do3 - -    -"
    cueva:
      velocidad: 10
      pistas:
        - "la3 do4 mi4 do4 | sol3 si3 re4 si3 | fa3 la3 do4 la3 | mi3 - - -"
        - "la2 -   mi3 -   | sol2 -   re3 -   | fa2 -   do3 -   | mi2 - - -"

# Simbolos del mapa que colocan enemigos y objetos.
spawns:
  s: seta
  m: mosca
  c: moneda

niveles:
{niveles}"""


def _nivel_yaml(nombre: str, filas: List[str], fondo: str, capas: str = "",
                musica: str = "") -> str:
    cuerpo = "\n".join("      " + fila for fila in filas)
    linea_capas = "    fondos: [%s]\n" % capas if capas else ""
    linea_musica = "    musica: %s\n" % musica if musica else ""
    return (
        "  - nombre: \"%s\"\n"
        "    fondo: \"%s\"\n"
        "%s%s"
        "    mapa: |\n%s\n" % (nombre, fondo, linea_capas, linea_musica, cuerpo)
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
        _nivel_yaml("BOSQUE", _nivel_1(), "#101830", musica="bosque")
        # el segundo nivel usa solo la capa lejana: se puede elegir por nivel
        + _nivel_yaml("CUEVA", _nivel_2(), "#180c20", capas="cielo", musica="cueva")
    )
    contenido = GAME_YAML.format(titulo=titulo.upper()[:24], autor=autor[:24], niveles=niveles)
    with open(os.path.join(destino, "game.yaml"), "w", encoding="utf-8") as fh:
        fh.write(contenido)
    creados.append("game.yaml")

    with open(os.path.join(destino, ".gitignore"), "w", encoding="utf-8") as fh:
        fh.write("build/\npreview.html\n")
    creados.append(".gitignore")
    return creados
