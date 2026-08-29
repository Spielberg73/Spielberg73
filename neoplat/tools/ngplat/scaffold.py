"""`ngplat nuevo`: crea un proyecto jugable desde el primer segundo."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List

from . import art, art_hierro, art_sonido
from .errors import ProjectError
from .png import write_png
from .wav import escribir as escribir_wav

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

def _nivel_1(llave: bool = False, escalera: bool = False) -> List[str]:
    """Nivel de entrada: saltar, coger monedas, pisar un enemigo, esquivar pinchos.

    Con `llave`, en mitad del camino aparece la llave que pide la meta: se coge
    de paso, pero sin ella el final del nivel no se abre.

    Con `escalera` se anade una que sube desde el suelo hasta la plataforma
    alta: es lo que hace falta para ver de que va ese modo nada mas empezar.
    Cada escalon sube una fila y avanza una columna, que es como los lee el
    motor, y el agujero del suelo se tapa porque con el salto sin correccion
    del genero de latigo no se cruza.
    """
    a = ANCHO_1
    suelo_1 = {0: "P", 8: "s", 12: "V", 18: "^", 28: "s", 40: "c", 44: "G"}
    if llave:
        suelo_1[22] = "k"
    escalones = {}
    if escalera:
        for i, fila in enumerate((14, 13, 12)):
            escalones[fila] = {34 + i: "/"}
        suelo_1.pop(40, None)

    def con_escalon(fila, base):
        if fila not in escalones:
            return base
        mezcla = dict(base)
        mezcla.update(escalones[fila])
        return mezcla

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
        _poner(a, con_escalon(12, {})),
        # el candelabro baja a la fila del suelo (para poder pegarle andando) y
        # a cambio se quita la moneda de arriba: cada sprite de mas en pantalla
        # se paga, y este nivel ya iba al limite de la Neo Geo
        _poner(a, con_escalon(13, {22: "c", 33: "c"})),
        _poner(a, con_escalon(14, suelo_1)),
        _suelo(a, [] if escalera else [(34, 2)]),
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
        # el tablon que va y viene: se sube uno encima y se deja llevar
        _poner(a, {32: "T"}),
        _poner(a, {6: "c", 17: "V", 27: "c", 38: "c", 45: "c"}),
        _poner(a, {0: "P", 8: "s", 18: "^", 30: "s", 42: "^", 51: "J"}),
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
  jugadores: 1        # 1 o 2 a la vez, cada uno con su mando
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
  doble_salto: no
{fisica}  animaciones:
    quieto: {{frames: [0], velocidad: 30}}
    correr: {{frames: [1, 2, 3, 2], velocidad: 6}}
    saltar: {{frames: [4]}}
    caer:   {{frames: [5]}}
{armas}
tiles:
  imagen: graficos/tiles.png
  leyenda:
    '.': {{tile: 0, tipo: vacio}}
    '#': {{tile: 1, tipo: solido}}
    ',': {{tile: 5, tipo: solido}}
    '=': {{tile: 2, tipo: plataforma}}
    '^': {{tile: 3, tipo: peligro}}
    'G': {{tile: 4, tipo: meta}}
{escaleras}
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
  # Un jefe es un enemigo con 'jefe: si': aguanta varios pisotones, el marcador
  # ensena lo que le queda y al matarlo se acaba el nivel.
  jefazo:
    sprite: graficos/enemigo.png
    caja: [12, 11]
    comportamiento: perseguidor
    velocidad: 0.5
    rango: 160
    vida: 5
    puntos: 1000
    jefe: si
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 8}}
      correr: {{frames: [0, 1], velocidad: 5}}

objetos:
  moneda:
    sprite: graficos/moneda.png
    caja: [10, 10]
    puntos: 10
    animaciones:
      quieto: {{frames: [0, 1, 2, 3], velocidad: 7}}
  # 'efecto: llave' no da puntos ni vida: suma al contador de llaves de la
  # partida. Un nivel con 'llaves: N' no deja pasar por la meta sin ellas.
  llave:
    sprite: graficos/llave.png
    caja: [12, 10]
    puntos: 50
    efecto: llave
    cantidad: 1
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 10}}
{municion}
# Rompibles: no hacen nada hasta que les pegas, y entonces sueltan lo que
# lleven dentro. Es el bucle de los clasicos de latigo: pegarle a todo.
rompibles:
  candelabro:
    sprite: graficos/candelabro.png
    caja: [8, 12]
    suelta: {suelta}        # el objeto que aparece al romperlo
    puntos: 100
    vida: 1                # golpes que aguanta
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 8}}

# Plataformas moviles: van y vienen entre donde salen y 'distancia' pixeles mas
# alla, y el que se sube encima va con ellas. No hacen dano ni se pueden matar:
# son escenario que se mueve. 'movimiento' es 'horizontal' o 'vertical'.
plataformas:
  tablon:
    sprite: graficos/plataforma.png
    frame: [32, 16]
    caja: [32, 6]          # solo la parte de arriba: es donde se pisa
    movimiento: horizontal
    velocidad: 0.6
    distancia: 48

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
    # muestra: sonido grabado (un WAV tuyo). Lo tocan cuatro de las cinco
    # maquinas; el Atari ST no puede, y toca lo que digan las notas de al lado
    moneda:  {{muestra: sonidos/moneda.wav, notas: "mi6 sol6", velocidad: 3}}
    pisar:   {{tipo: barrido, desde: 800, hasta: 200, duracion: 6}}
    golpe:   {{muestra: sonidos/golpe.wav, tipo: ruido, duracion: 10}}
    muerte:  {{notas: "sol4 mi4 do4 sol3", velocidad: 6}}
    meta:    {{notas: "do5 mi5 sol5 do6", velocidad: 6}}
    disparo: {{tipo: barrido, desde: 1200, hasta: 300, duracion: 4}}
    romper:  {{tipo: ruido, duracion: 6}}
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
  k: llave
  T: tablon
  V: candelabro
  J: jefazo

niveles:
{niveles}"""


# El segundo estilo: seis colores contados, para el modo de doble plano del
# Amiga. Cambian los dibujos, los bichos y la musica; el motor es el mismo.
GAME_YAML_HIERRO = """# Proyecto NeoPlat con la paleta corta: seis colores para todo el juego.
#
#   ngplat probar     -> abre el preview jugable en el navegador
#   ngplat compilar   -> genera el proyecto en C y las ROMs graficas
#
# Los dibujos estan hechos para 'amiga: 8colores', el modo de doble plano del
# OCS: el juego va delante con siete colores (uno se lo queda el marcador) y la
# capa de fondo detras con otros siete, movida por hardware. En las demas
# maquinas se ve igual, solo que les sobra sitio.

juego:
  titulo: "{titulo}"
  autor: "{autor}"
  jugadores: 1        # 1 o 2 a la vez, cada uno con su mando
  vidas: 3
  tiempo: 0            # segundos por nivel (0 = sin limite)
  camara: scroll       # scroll (el escenario se desliza) o pantallas
  amiga: 8colores      # doble plano: menos colores, pero parallax de verdad
  fondo: "#14121e"

jugador:
  sprite: graficos/heroe.png
  frame: [16, 16]
  caja: [10, 15]
  velocidad: 1.6
  aceleracion: 0.30
  friccion: 0.35
  salto: 4.3
  gravedad: 0.28
  doble_salto: no
{fisica}  animaciones:
    quieto: {{frames: [0], velocidad: 30}}
    correr: {{frames: [1, 2, 3, 2], velocidad: 6}}
    saltar: {{frames: [4]}}
    caer:   {{frames: [5]}}
{armas}
tiles:
  imagen: graficos/tiles.png
  leyenda:
    '.': {{tile: 0, tipo: vacio}}
    '#': {{tile: 1, tipo: solido}}
    ',': {{tile: 5, tipo: solido}}
    '=': {{tile: 2, tipo: plataforma}}
    '^': {{tile: 3, tipo: peligro}}
    'G': {{tile: 4, tipo: meta}}
{escaleras}
enemigos:
  raton:
    sprite: graficos/enemigo.png
    caja: [12, 11]
    comportamiento: patrulla
    velocidad: 0.4
    puntos: 100
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 14}}
      correr: {{frames: [0, 1], velocidad: 10}}
  murcielago:
    sprite: graficos/enemigo.png
    caja: [12, 11]
    comportamiento: volador
    velocidad: 0.6
    amplitud: 28
    periodo: 150
    puntos: 200
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 6}}
  # Un jefe es un enemigo con 'jefe: si': aguanta varios pisotones, el marcador
  # ensena lo que le queda y al matarlo se acaba el nivel.
  guardian:
    sprite: graficos/enemigo.png
    caja: [12, 11]
    comportamiento: perseguidor
    velocidad: 0.5
    rango: 160
    vida: 5
    puntos: 1000
    jefe: si
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 8}}
      correr: {{frames: [0, 1], velocidad: 5}}

objetos:
  gema:
    sprite: graficos/gema.png
    caja: [10, 10]
    puntos: 10
    animaciones:
      quieto: {{frames: [0, 1, 2, 3], velocidad: 7}}
{municion}
# Rompibles: no hacen nada hasta que les pegas, y entonces sueltan lo que
# lleven dentro.
rompibles:
  brasero:
    sprite: graficos/candelabro.png
    caja: [8, 12]
    suelta: {suelta}
    puntos: 100
    vida: 1
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 8}}

plataformas:
  viga:
    sprite: graficos/plataforma.png
    frame: [32, 16]
    caja: [32, 6]          # solo la parte de arriba: es donde se pisa
    movimiento: horizontal
    velocidad: 0.6
    distancia: 48

# Una sola capa: en doble plano el Amiga solo puede mover una, y mide 256
# pixeles de ancho para poder repetirse dentro del hueco que tiene para correr.
fondos:
  - nombre: cueva
    imagen: graficos/cueva.png
    velocidad: 0.3
    y: 0

sonido:
  efectos:
    empezar: {{notas: "la4 mi5", velocidad: 4}}
    salto:   {{tipo: barrido, desde: 300, hasta: 820, duracion: 6}}
    moneda:  {{notas: "mi6 la6", velocidad: 3}}
    pisar:   {{tipo: barrido, desde: 760, hasta: 190, duracion: 6}}
    golpe:   {{tipo: ruido, duracion: 10}}
    muerte:  {{notas: "mi4 do4 la3 mi3", velocidad: 6}}
    meta:    {{notas: "la4 do5 mi5 la5", velocidad: 6}}
    disparo: {{tipo: barrido, desde: 1100, hasta: 280, duracion: 4}}
  musica:
    galeria:
      velocidad: 9
      pistas:
        - "la3 do4 mi4 do4 | si3 re4 fa4 re4 | do4 mi4 la4 mi4 | mi4 - re4 -"
        - "la2 -   la2 -   | si2 -   si2 -   | do3 -   do3 -   | mi2 - -   -"
    pozo:
      velocidad: 11
      pistas:
        - "re4 fa4 la4 fa4 | do4 mi4 sol4 mi4 | si3 re4 fa4 re4 | la3 - - -"
        - "re2 -   la2 -   | do3 -   sol2 -   | si2 -   fa2 -   | la2 - - -"

spawns:
  s: raton
  m: murcielago
  c: gema
  T: viga
  V: brasero
  J: guardian

niveles:
{niveles}"""


def _nivel_yaml(nombre: str, filas: List[str], fondo: str, capas: str = "",
                musica: str = "", llaves: int = 0) -> str:
    cuerpo = "\n".join("      " + fila for fila in filas)
    linea_capas = "    fondos: [%s]\n" % capas if capas else ""
    linea_musica = "    musica: %s\n" % musica if musica else ""
    linea_llaves = "    llaves: %d\n" % llaves if llaves else ""
    return (
        "  - nombre: \"%s\"\n"
        "    fondo: \"%s\"\n"
        "%s%s%s"
        "    mapa: |\n%s\n"
        % (nombre, fondo, linea_capas, linea_musica, linea_llaves, cuerpo)
    )


ESTILOS = ("bosque", "hierro")


# --------------------------------------------------------------- generos
#
# El **genero** decide como se juega y el **estilo** como se ve: son dos ejes
# distintos y se eligen por separado. Cada genero es un punado de trozos de
# yaml que se meten en los huecos de la plantilla, no una plantilla aparte:
# duplicar el game.yaml entero por cada combinacion seria imposible de
# mantener y las dos copias se irian separando a la primera.

@dataclass
class Genero:
    """Un tipo de juego: que se puede hacer y como se siente."""
    nombre: str
    titulo: str
    resumen: str
    fisica: str                  # lineas sueltas de la seccion `jugador:`
    armas: str                   # los bloques `ataque:` y `secundaria:`
    escaleras: str               # las filas de escalera de la leyenda
    municion: str                # el objeto de `efecto: municion`, si lo hay
    suelta: str                  # que suelta el rompible
    con_escaleras: bool          # si los niveles llevan una


def _genero_plataformas(nombres: Dict[str, str]) -> Genero:
    return Genero(
        nombre="plataformas",
        titulo="plataformas",
        resumen=("saltar, pisar enemigos y disparar. El salto se corrige en el "
                 "aire. Lo de toda la vida."),
        fisica=("  vida: 2              # golpes que aguanta antes de perder una vida\n"
                "  control_aire: 0.16   # cuanto se corrige el salto en el aire\n"
                "  pisar_enemigos: si\n"
                "  rebote: 3.6          # impulso al pisar un enemigo\n"),
        armas=("  # El boton de accion. Quitalo entero y el jugador solo podra\n"
               "  # pisar enemigos.\n"
               "  ataque:\n"
               "    tipo: disparo            # disparo o golpe (cuerpo a cuerpo)\n"
               "    sprite: graficos/bala.png\n"
               "    frame: [16, 16]\n"
               "    caja: [6, 6]\n"
               "    desplazamiento: [5, 5]\n"
               "    velocidad: 3.5           # pixeles por frame que vuela\n"
               "    alcance: 96              # px que recorre antes de apagarse\n"
               "    espera: 18               # frames entre un disparo y el siguiente\n"
               "    dano: 1\n"
               "    animaciones:\n"
               "      quieto: {frames: [0, 1, 2, 1], velocidad: 4}\n"),
        escaleras="",
        municion="",
        suelta=nombres["moneda"],
        con_escaleras=False,
    )


def _genero_castlevania(nombres: Dict[str, str]) -> Genero:
    return Genero(
        nombre="castlevania",
        titulo="castlevania",
        resumen=("latigo, escaleras y municion. El salto NO se corrige en el "
                 "aire y un golpe te tira al vacio."),
        fisica=("  vida: 4              # aqui no se pisa a nadie: hace falta aguante\n"
                "  control_aire: 0.0    # el salto no se corrige: sale como sale\n"
                "  pisar_enemigos: no   # aqui se pega, no se pisa\n"
                "  retroceso: 3.0       # con cuanta fuerza sales despedido\n"
                "  aturdido: 24         # frames sin control despues del golpe\n"
                "  velocidad_escalera: 0.8\n"),
        armas=("  # El latigo. `preparacion` son los frames en los que el brazo\n"
               "  # todavia sale y no hace dano, y `clavado` te planta en el sitio\n"
               "  # mientras pegas: es lo que obliga a medir la distancia.\n"
               "  ataque:\n"
               "    tipo: golpe\n"
               "    alcance: 26\n"
               "    duracion: 14\n"
               "    preparacion: 5\n"
               "    clavado: si\n"
               "    espera: 18\n"
               "    dano: 1\n"
               "  # El arma secundaria: se tira con **arriba + accion** y gasta\n"
               "  # municion. 'tipo: arco' la haria caer describiendo una parabola.\n"
               "  secundaria:\n"
               "    tipo: recta\n"
               "    sprite: graficos/cuchillo.png\n"
               "    frame: [16, 16]\n"
               "    caja: [10, 4]\n"
               "    desplazamiento: [3, 6]\n"
               "    velocidad: 4.0\n"
               "    alcance: 200\n"
               "    espera: 24\n"
               "    coste: 1               # municion que gasta cada tirada\n"
               "    dano: 1\n"),
        escaleras=("    '/': {tile: 6, tipo: escalera}\n"
                   "    '|': {tile: 7, tipo: escalera_izquierda}\n"),
        municion=("  # 'efecto: municion' recarga el arma secundaria. Ojo:\n"
                  "  # 'efecto: corazon' a secas es salud, que es otra cosa.\n"
                  "  %s:\n"
                  "    sprite: graficos/corazon.png\n"
                  "    caja: [10, 8]\n"
                  "    puntos: 0\n"
                  "    efecto: municion\n"
                  "    cantidad: 5\n"
                  "    animaciones:\n"
                  "      quieto: {frames: [0, 1], velocidad: 12}\n"
                  % nombres["municion"]),
        suelta=nombres["municion"],
        con_escaleras=True,
    )


GENEROS = ("plataformas", "castlevania")

# Como se llama cada cosa en cada estilo de dibujo.
_NOMBRES = {
    "bosque": {"moneda": "moneda", "municion": "corazon"},
    "hierro": {"moneda": "gema", "municion": "chispa"},
}


def genero_de(nombre: str, estilo: str) -> Genero:
    nombres = _NOMBRES[estilo]
    if nombre == "castlevania":
        return _genero_castlevania(nombres)
    return _genero_plataformas(nombres)


def menu_de_generos(entrada=None, salida=None) -> str:
    """Pregunta que tipo de juego se quiere hacer y devuelve su nombre.

    Solo se usa cuando `ngplat nuevo` se lanza sin `--genero` y hay alguien
    delante: en un guion o en las pruebas no se pregunta nada y sale el de por
    defecto, que es el primero de la lista.
    """
    import sys as _sys
    entrada = entrada or _sys.stdin
    salida = salida or _sys.stdout
    opciones = [genero_de(n, "bosque") for n in GENEROS]
    salida.write("\n  Que tipo de juego quieres hacer?\n\n")
    for i, g in enumerate(opciones):
        salida.write("    %d) %-13s %s\n" % (i + 1, g.titulo, g.resumen))
    salida.write("\n  elige [1]: ")
    salida.flush()
    try:
        elegido = (entrada.readline() or "").strip()
    except (OSError, ValueError):
        elegido = ""
    if not elegido:
        return GENEROS[0]
    if elegido.isdigit() and 1 <= int(elegido) <= len(GENEROS):
        return GENEROS[int(elegido) - 1]
    for nombre in GENEROS:
        if nombre.startswith(elegido.lower()):
            return nombre
    salida.write("  no conozco '%s': me quedo con %s\n" % (elegido, GENEROS[0]))
    return GENEROS[0]


def crear_proyecto(destino: str, titulo: str = "MI JUEGO", autor: str = "",
                   estilo: str = "bosque", genero: str = "plataformas") -> List[str]:
    """Crea la carpeta del proyecto con game.yaml y graficos de ejemplo.

    Son dos ejes que se eligen por separado:

      `genero` decide **como se juega**: 'plataformas' salta, pisa enemigos y
      dispara, con el salto corregible en el aire; 'castlevania' pega con
      latigo, sube escaleras, gasta municion y no corrige el salto, asi que un
      golpe al borde de una plataforma te tira al vacio.

      `estilo` decide **como se ve**: 'bosque' es el de siempre y 'hierro'
      viene dibujado con seis colores, listo para el doble plano del Amiga.
    """
    if estilo not in ESTILOS:
        raise ProjectError(
            "no conozco el estilo '%s'" % estilo,
            hint="los que hay son: %s" % ", ".join(ESTILOS),
        )
    if genero not in GENEROS:
        raise ProjectError(
            "no conozco el genero '%s'" % genero,
            hint="los que hay son: %s" % ", ".join(GENEROS),
        )
    g = genero_de(genero, estilo)
    if os.path.exists(destino) and os.listdir(destino):
        raise ProjectError(
            "la carpeta '%s' ya existe y no esta vacia" % destino,
            hint="elige otro nombre o borra la carpeta",
        )
    os.makedirs(os.path.join(destino, "graficos"), exist_ok=True)
    creados: List[str] = []

    dibujos = art.todos() if estilo == "bosque" else art_hierro.todos()
    for relativo, imagen in dibujos.items():
        ruta = os.path.join(destino, relativo)
        write_png(ruta, imagen)
        creados.append(relativo)

    if estilo == "bosque":
        os.makedirs(os.path.join(destino, "sonidos"), exist_ok=True)
        for relativo, muestra in art_sonido.todos().items():
            escribir_wav(os.path.join(destino, relativo), muestra)
            creados.append(relativo)

    if estilo == "bosque":
        niveles = (
            _nivel_yaml("BOSQUE", _nivel_1(llave=True, escalera=g.con_escaleras),
                        "#101830", musica="bosque", llaves=1)
            # el segundo nivel usa solo la capa lejana: se puede elegir por nivel
            + _nivel_yaml("CUEVA", _nivel_2(), "#180c20", capas="cielo", musica="cueva")
        )
        plantilla = GAME_YAML
    else:
        niveles = (
            _nivel_yaml("GALERIA", _nivel_1(escalera=g.con_escaleras), "#14121e",
                        musica="galeria")
            + _nivel_yaml("EL POZO", _nivel_2(), "#0e1018", musica="pozo")
        )
        plantilla = GAME_YAML_HIERRO
    contenido = plantilla.format(
        titulo=titulo.upper()[:24], autor=autor[:24], niveles=niveles,
        fisica=g.fisica, armas=g.armas, escaleras=g.escaleras,
        municion=g.municion, suelta=g.suelta)
    with open(os.path.join(destino, "game.yaml"), "w", encoding="utf-8",
              newline="\n") as fh:
        fh.write(contenido)
    creados.append("game.yaml")

    with open(os.path.join(destino, ".gitignore"), "w", encoding="utf-8",
              newline="\n") as fh:
        # .neoplat/ son las copias locales del historial: utiles en tu disco,
        # ruido en un repositorio (para eso ya esta el propio control de
        # versiones)
        fh.write("build/\npreview.html\n.neoplat/\n")
    creados.append(".gitignore")
    return creados
