"""`ngplat nuevo`: crea un proyecto jugable desde el primer segundo."""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from typing import Dict, List

from . import art, art_comando, art_hierro, art_sonido
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

def _nivel_1(llave: bool = False, escalera: bool = False,
             control: bool = False) -> List[str]:
    """Nivel de entrada: saltar, coger monedas, pisar un enemigo, esquivar pinchos.

    Con `llave`, en mitad del camino aparece la llave que pide la meta: se coge
    de paso, pero sin ella el final del nivel no se abre.

    Con `escalera` se anade una que sube desde el suelo hasta la plataforma
    alta: es lo que hace falta para ver de que va ese modo nada mas empezar.
    Cada escalon sube una fila y avanza una columna, que es como los lee el
    motor, y el agujero del suelo se tapa porque con el salto sin correccion
    del genero de latigo no se cruza.

    Con `control` se pone la antorcha a mitad de camino (justo pasados los
    pinchos, que es donde duele volver a empezar) y una moneda se cambia por la
    mejora del arma. Se cambia, no se anade: cada sprite de mas en pantalla se
    paga y este nivel ya va al limite de la Neo Geo.
    """
    a = ANCHO_1
    suelo_1 = {0: "P", 8: "s", 12: "V", 18: "^", 28: "s", 40: "c", 44: "G"}
    if llave:
        suelo_1[22] = "k"
    fila_13 = {22: "c", 33: "c"}
    if control:
        suelo_1[24] = "!"       # la antorcha, pasados los pinchos de la 18
        fila_13[33] = "M"       # la mejora del latigo, en vez de una moneda
    escalones = {}
    # arriba de la escalera, en vez de una moneda mas, el hacha: es el arma
    # secundaria que se cambia por la de serie, y asi subir tiene premio
    fila_10 = {5: "ccc", 38: "ccc"}
    if escalera:
        for i, fila in enumerate((14, 13, 12)):
            escalones[fila] = {34 + i: "/"}
        suelo_1.pop(40, None)
        fila_10 = {5: "ccc", 38: "cHc"}

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
        _poner(a, fila_10),
        _poner(a, {4: "=====", 37: "====="}),
        _poner(a, con_escalon(12, {})),
        # el candelabro baja a la fila del suelo (para poder pegarle andando) y
        # a cambio se quita la moneda de arriba: cada sprite de mas en pantalla
        # se paga, y este nivel ya iba al limite de la Neo Geo
        _poner(a, con_escalon(13, fila_13)),
        _poner(a, con_escalon(14, suelo_1)),
        _suelo(a, [] if escalera else [(34, 2)]),
    ]


def _nivel_2(control: bool = False, escalera: bool = False) -> List[str]:
    """Segundo nivel: voladores, saltos encadenados y un hueco mas largo.

    Con `escalera` sube una hasta la plataforma alta del final, la del jefe:
    en el genero de latigo las escaleras son la mitad del juego y tenerlas
    solo en el primer nivel las dejaba en anecdota. Se sube pegado al ultimo
    tramo, asi que hay que decidir si se pelea arriba o abajo.

    Cada escalon sube una fila y avanza una columna, y el de arriba tiene que
    dejarte **encima de la plataforma**: por eso el ultimo esta en la columna
    de antes de donde empieza. Si acabara en el aire, te caes.
    """
    a = ANCHO_2
    suelo_2 = {0: "P", 8: "s", 18: "^", 30: "s", 42: "^", 51: "J"}
    fila_13 = {6: "c", 17: "V", 27: "c", 38: "c", 45: "c"}
    escalones = {}
    if control:
        suelo_2[26] = "!"       # la antorcha, pasado el primer hueco
    if escalera:
        for i, fila in enumerate((14, 13, 12)):
            escalones[fila] = {44 + i: "/"}
        # la moneda de la 45 estorbaria a la escalera: en su sitio va la
        # segunda mejora del latigo, que es lo que se busca subiendo
        fila_13.pop(45, None)
        fila_13[49] = "M"

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
        _poner(a, con_escalon(12, {32: "T"})),
        _poner(a, con_escalon(13, fila_13)),
        _poner(a, con_escalon(14, suelo_2)),
        _suelo(a, [(24, 2), (47, 2)]),
    ]


# --------------------------------------------------- los niveles cenitales
#
# Un juego de comando **sube**: se empieza abajo y la meta esta arriba del
# todo. Lo que lo hace jugable no es la longitud sino los recodos: el camino
# tuerce, se estrecha entre sacos y arboles, y en cada recodo hay algo -una
# torreta que guarda el paso, un prisionero metido en un recinto, un rio que
# hay que rodear-. Un pasillo recto de treinta filas seria un pasillo; esto es
# un camino.

CENITAL_ANCHO = 20                   # una pantalla justa de ancho
CENITAL_ALTO = 32                    # algo mas de dos pantallas de alto


def _fila_cenital(mapa: str) -> str:
    """Completa una fila a lo ancho del nivel con arboles a los lados."""
    fila = mapa[:CENITAL_ANCHO]
    return fila + "A" * (CENITAL_ANCHO - len(fila))


def _nivel_comando_1() -> List[str]:
    """El campamento: se sube por un camino que tuerce dos veces, con el rio
    cortando por la mitad y prisioneros metidos en los recintos."""
    filas = [
        "AAAAAA..,G,..AAAAAA",
        "AAAAA.,,,,,,,.AAAAA",
        "AAAA..,,,,,,,..AAAA",
        "AAA..#,,,,,,,#..AAA",
        "AAA..#,,,t,,,#..AAA",
        "AAA.,,,,,,,,,,,.AAA",
        "AA..,,,,,,,,,g,,.AA",
        "AA.,,,#######,,,.AA",
        "AA.,,,#.....#,,,.AA",
        "AA.,s,#..R..#,,,.AA",
        "AA.,,,#.....#,,,.AA",
        "AA.,,,###.###,,,.AA",
        "AA.,,,,,g,,,,,,,.AA",
        "AA.~~~~~~~,,,,,,.AA",
        "AA.~~~~~~~,,,,,,.AA",
        "AAA.~~~~~,,,s,,.AAA",
        "AAA..,,,,,,,,,.AAAA",
        "AAA.,,,,,T,,,,.AAAA",
        "AA.,,,,,,,,,,,,.AAA",
        "AA.,,##,,,,,##,,.AA",
        "AA.,,#R,,s,,R#,,.AA",
        "AA.,,##,,,,,##,,.AA",
        "AA.,,,,,,,,,,,,,.AA",
        "AA.,,,,,,t,,,,,,.AA",
        "AA..,,,,,g,,,,,.AAA",
        "AAA.,,,,,,,,,,.AAAA",
        "AAA..,,,,s,,,,.AAAA",
        "AAAA..,,,,,,,.AAAAA",
        "AAAA...,,,,,..AAAAA",
        "AAAAA..,,c,,.AAAAAA",
        "AAAAA..,,,,,.AAAAAA",
        "AAAAA...P....AAAAAA",
    ]
    return [_fila_cenital(f) for f in filas]


def _nivel_comando_2() -> List[str]:
    """El bunker: mas estrecho, mas torretas y el jefe arriba del todo. Aqui
    los prisioneros estan **detras** de las torretas, para que no valga con
    correr en linea recta."""
    filas = [
        "AAAAAA..,G,..AAAAAA",
        "AAAAA.,,,,,,,.AAAAA",
        "AAAA.,,,,B,,,,.AAAA",
        "AAAA.,,,,,,,,,.AAAA",
        "AAAA.#########.AAAA",
        "AAAA.,,,,,,,,,.AAAA",
        "AAA.,,,t,,,t,,,.AAA",
        "AAA.,,,,,,,,,,,.AAA",
        "AAA.,,#,,,,,#,,.AAA",
        "AAA.,R#,,s,,#R,.AAA",
        "AAA.,,#,,,,,#,,.AAA",
        "AAA.,,,,,,,,,,,.AAA",
        "AA..,,,,,,,,,,,,.AA",
        "AA.~~~~~,,,~~~~~.AA",
        "AA.~~~~,,g,,~~~~.AA",
        "AA.~~~,,,,,,,~~~.AA",
        "AA.,,,,,,,,,,,,,.AA",
        "AA.,,,,,,T,,,,,,.AA",
        "AA.,,,,,,,,,,,,,.AA",
        "AA.,,####,####,,.AA",
        "AA.,,#,,,,,,,#,,.AA",
        "AA.,,#,,,t,,,#,,.AA",
        "AA.,,#,,,,,,,#,,.AA",
        "AA.,,##,,R,,##,,.AA",
        "AA.,,g,,,,,,,,,,.AA",
        "AAA.,,,,s,,,,s,.AAA",
        "AAA.,,,,,,,,,,,.AAA",
        "AAAA.,,,,,,,,,.AAAA",
        "AAAA..,,,c,,,.AAAAA",
        "AAAAA.,,,,,,.AAAAAA",
        "AAAAA..,,,,..AAAAAA",
        "AAAAA...P....AAAAAA",
    ]
    return [_fila_cenital(f) for f in filas]


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
    dano:   {{frames: [9]}}   # la pose de recibir un golpe
{animos}{armas}
tiles:
  imagen: graficos/tiles.png
  leyenda:
    '.': {{tile: 0, tipo: vacio}}
    '#': {{tile: 1, tipo: solido}}
    ',': {{tile: 5, tipo: solido}}
    '=': {{tile: 2, tipo: plataforma}}
    '^': {{tile: 3, tipo: peligro}}
    'G': {{tile: 4, tipo: meta}}
{escaleras}{control}
enemigos:
{bichos}{jefe}
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
{municion}{arma}{mejora}
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
{eventos}{musica}
# Simbolos del mapa que colocan enemigos y objetos.
spawns:
{bichos_spawn}  c: moneda
  k: llave
  T: tablon
  V: candelabro
{spawns}
niveles:
{niveles}"""


# El genero de comando se ve **desde arriba**, asi que no comparte plantilla
# con los otros dos: no hay suelo, ni saltos, ni plataformas, y hasta la
# leyenda de tiles es otra (el agua mata, los sacos frenan). Duplicar el yaml
# por cada estilo si seria un error -por eso los dos de vista lateral comparten
# huecos-, pero duplicarlo por **modo de juego** es lo unico honrado: describe
# otro juego.
GAME_YAML_COMANDO = """# Proyecto NeoPlat de vista cenital: un juego de comando.
#
#   ngplat probar     -> abre el preview jugable en el navegador
#   ngplat compilar   -> genera el proyecto en C y las ROMs graficas
#
# Se ve desde arriba, como los recreativos de comando de los ochenta: andas en
# ocho direcciones, disparas hacia donde miras, tiras granadas con el otro
# boton y subes la pantalla rescatando prisioneros.

juego:
  titulo: "{titulo}"
  autor: "{autor}"
  vista: cenital       # desde arriba: sin gravedad y en ocho direcciones
  jugadores: 1         # 1 o 2 a la vez, cada uno con su mando
  vidas: 3
  tiempo: 0            # segundos por nivel (0 = sin limite)
  camara: scroll
  amiga: 32colores
  fondo: "#183018"

jugador:
  sprite: graficos/heroe.png
  frame: [16, 16]
  caja: [10, 12]       # la caja, mas pequena que el dibujo: se juega mejor
  velocidad: 1.4       # pixeles por frame en las cuatro direcciones
  friccion: 0.35
  vida: 3              # golpes que aguanta antes de perder una vida
  retroceso: 2.0       # el empujon al recibir un tiro
  aturdido: 16
  animaciones:
    # De frente, de espaldas y de lado: el motor elige segun hacia donde andas,
    # y las diagonales salen espejando la de lado.
    quieto: {{frames: [0], velocidad: 30}}
    abajo:  {{frames: [1, 2], velocidad: 8}}
    arriba: {{frames: [3, 4], velocidad: 8}}
    correr: {{frames: [5, 6], velocidad: 8}}
    atacar: {{frames: [7], velocidad: 6}}
    dano:   {{frames: [8]}}
  # El fusil: dispara hacia donde miras, en las ocho direcciones.
  ataque:
    tipo: disparo
    sprite: graficos/bala.png
    frame: [16, 16]
    caja: [4, 4]
    desplazamiento: [6, 6]
    velocidad: 4.5
    alcance: 160
    espera: 10           # se dispara rapido: es un juego de tirar sin parar
    dano: 1
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 4}}
  # La granada va en el **boton de saltar**: aqui no hay nada que saltar.
  secundarias:
    granada:
      tipo: recta
      marcador: GRAN
      sprite: graficos/granada.png
      frame: [16, 16]
      caja: [8, 8]
      desplazamiento: [4, 4]
      velocidad: 3.0
      alcance: 80        # llega hasta donde llega: hay que acercarse
      espera: 40
      coste: 1
      dano: 3            # se lleva por delante lo que pille
      a_la_vez: 1
      animaciones:
        quieto: {{frames: [0, 1, 2, 3], velocidad: 5}}

tiles:
  imagen: graficos/tiles.png
  leyenda:
    '.': {{tile: 0, tipo: vacio}}      # hierba
    ',': {{tile: 5, tipo: vacio}}      # camino
    'o': {{tile: 6, tipo: vacio}}      # crater
    'A': {{tile: 1, tipo: solido}}     # arboles
    '#': {{tile: 2, tipo: solido}}     # sacos terreros
    '~': {{tile: 3, tipo: peligro}}    # el rio: no se cruza a nado
    'G': {{tile: 4, tipo: meta}}       # la base: hasta aqui hay que llegar
    'T': {{tile: 7, tipo: control}}    # la tienda: si te matan, vuelves aqui

enemigos:
  # Los soldados patrullan y **te disparan**: `dispara:` es lo que convierte
  # una pantalla en un juego de comando.
  soldado:
    sprite: graficos/soldado.png
    caja: [10, 12]
    comportamiento: patrulla
    velocidad: 0.5
    puntos: 200
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 16}}
      correr: {{frames: [0, 1], velocidad: 10}}
    dispara:
      sprite: graficos/tiro.png
      frame: [16, 16]
      caja: [4, 4]
      desplazamiento: [6, 6]
      velocidad: 2.2
      alcance: 180
      espera: 100        # la cadencia es lo que decide si un sitio se pasa
      dano: 1
      animaciones:
        quieto: {{frames: [0, 1], velocidad: 5}}
  # La torreta no se mueve, pero tampoco se calla: es la que guarda un paso.
  torreta:
    sprite: graficos/torreta.png
    caja: [14, 14]
    comportamiento: fijo
    vida: 3
    puntos: 500
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 20}}
    dispara:
      sprite: graficos/tiro.png
      frame: [16, 16]
      caja: [4, 4]
      desplazamiento: [6, 6]
      velocidad: 2.6
      alcance: 200
      espera: 70
      dano: 1
      animaciones:
        quieto: {{frames: [0, 1], velocidad: 5}}
  # Un jefe es un enemigo con 'jefe: si': el marcador ensena lo que le queda y
  # al matarlo se acaba el nivel.
  bunker:
    sprite: graficos/torreta.png
    caja: [14, 14]
    comportamiento: fijo
    vida: 10
    puntos: 3000
    jefe: si
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 8}}
    dispara:
      sprite: graficos/tiro.png
      frame: [16, 16]
      caja: [4, 4]
      desplazamiento: [6, 6]
      velocidad: 3.0
      alcance: 260
      espera: 34
      dano: 1
      animaciones:
        quieto: {{frames: [0, 1], velocidad: 4}}

# Los prisioneros: **a estos no hay que dispararles**. Si los tocas, se sueltan
# y suman; si les das un tiro, se pierden. Es lo que obliga a mirar antes de
# apretar el gatillo.
prisioneros:
  prisionero:
    sprite: graficos/prisionero.png
    caja: [10, 12]
    puntos: 500
    velocidad: 1.6       # lo que corre al soltarse
    escape: 100          # frames corriendo antes de perderse de vista
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 24}}
      correr: {{frames: [2, 3], velocidad: 6}}

objetos:
  # Las granadas se recargan: 'efecto: municion' es el contador del arma
  # secundaria, que aqui es la granada.
  caja:
    sprite: graficos/granada.png
    frame: [16, 16]
    caja: [8, 8]
    puntos: 50
    efecto: municion
    cantidad: 3
    animaciones:
      quieto: {{frames: [0, 2], velocidad: 14}}
  medalla:
    sprite: graficos/bala.png
    frame: [16, 16]
    caja: [6, 6]
    puntos: 100
    animaciones:
      quieto: {{frames: [0, 1], velocidad: 6}}

# Sonido. Un juego de comando es sobre todo tiros, asi que el disparo es corto
# y seco: si durase mas, con la cadencia que tiene se pisarian unos a otros.
sonido:
  efectos:
    empezar: {{notas: "do5 mi5 sol5", velocidad: 4}}
    disparo: {{tipo: barrido, desde: 1600, hasta: 500, duracion: 3}}
    golpe:   {{tipo: ruido, duracion: 8}}
    romper:  {{tipo: ruido, duracion: 12}}
    moneda:  {{notas: "mi6 sol6 do7", velocidad: 3}}
    control: {{notas: "sol5 do6", velocidad: 5}}
    muerte:  {{notas: "sol4 mi4 do4 sol3", velocidad: 6}}
    meta:    {{notas: "do5 mi5 sol5 do6", velocidad: 6}}
    salto:   {{tipo: barrido, desde: 400, hasta: 900, duracion: 5}}
{musica}
# Simbolos del mapa que colocan enemigos, prisioneros y objetos.
spawns:
  s: soldado
  t: torreta
  B: bunker
  R: prisionero
  g: caja
  c: medalla

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
    dano:   {{frames: [9]}}   # la pose de recibir un golpe
{animos}{armas}
tiles:
  imagen: graficos/tiles.png
  leyenda:
    '.': {{tile: 0, tipo: vacio}}
    '#': {{tile: 1, tipo: solido}}
    ',': {{tile: 5, tipo: solido}}
    '=': {{tile: 2, tipo: plataforma}}
    '^': {{tile: 3, tipo: peligro}}
    'G': {{tile: 4, tipo: meta}}
{escaleras}{control}
enemigos:
{bichos}{jefe}
objetos:
  gema:
    sprite: graficos/gema.png
    caja: [10, 10]
    puntos: 10
    animaciones:
      quieto: {{frames: [0, 1, 2, 3], velocidad: 7}}
{municion}{arma}{mejora}
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
    romper:  {{tipo: ruido, duracion: 6}}
{eventos}{musica}
spawns:
{bichos_spawn}  c: gema
  T: viga
  V: brasero
{spawns}
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

# ------------------------------------------------------------------ musica
#
# Cada genero trae la suya: la de plataformas cambia con el estilo del dibujo,
# y la de latigo es la misma en los dos porque lo que la define es el genero.
# Las notas van en bloques de yaml ('- |') con **un compas por linea**: en una
# sola linea larga no hay quien cuente los tiempos ni encuentre un error.

_MUSICA_BOSQUE = """  musica:
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
    # La del titulo: suena mientras espera a que pulses Start.
    presentacion:
      velocidad: 9
      pistas:
        - |
          do5 mi5 sol5 do6 si5 sol5 mi5 sol5
          la5 do6 mi6 do6 sol5 mi5 do5 mi5
          fa5 la5 do6 la5 mi5 sol5 si5 sol5
          re5 fa5 la5 fa5 do5 - - -
        - |
          do3 - sol3 - mi3 - sol3 -
          la3 - mi3 - do3 - sol3 -
          fa3 - do4 - mi3 - si3 -
          sol3 - re4 - do3 - - -
    # La del jefe: manda sobre la del nivel mientras el jefe este vivo.
    acoso:
      velocidad: 6
      pistas:
        - |
          la4 - la4 do5 si4 - si4 re5
          la4 - la4 do5 mi5 re5 do5 si4
          la4 - la4 do5 si4 - si4 re5
          fa5 mi5 re5 do5 si4 la4 sol#4 la4
          mi5 - mi5 fa5 mi5 - mi5 do5
          re5 - re5 mi5 re5 - re5 si4
          do5 si4 la4 si4 do5 re5 mi5 fa5
          mi5:2 re5:2 do5:2 si4:2
        - |
          la2 la3 la2 la3 si2 si3 si2 si3
          la2 la3 la2 la3 mi2 mi3 mi2 mi3
          la2 la3 la2 la3 si2 si3 si2 si3
          fa2 fa3 do3 do4 mi2 mi3 mi2 mi3
          do3 do4 do3 do4 la2 la3 la2 la3
          si2 si3 si2 si3 sol2 sol3 sol3 sol3
          la2 la3 do3 do4 mi3 mi2 mi3 mi2
          la2:2 mi3:2 la2:2 mi3:2
  # Las dos canciones que no son de ningun nivel se dicen aqui por su nombre.
  titulo: presentacion
  jefe: acoso
"""

_MUSICA_HIERRO = """  musica:
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
    portada:
      velocidad: 10
      pistas:
        - |
          la4 mi5 do5 mi5 si4 fa#5 re5 fa#5
          do5 sol5 mi5 sol5 si4 - mi5 -
          la4 mi5 do5 mi5 re5 la5 fa5 la5
          mi5 do5 si4 sol4 la4 - - -
        - |
          la2 - mi3 - si2 - fa#3 -
          do3 - sol3 - mi3 - mi2 -
          la2 - mi3 - re3 - la3 -
          do3 - mi3 - la2 - - -
    asedio:
      velocidad: 6
      pistas:
        - |
          re4 - re4 fa4 mi4 - mi4 sol4
          re4 - re4 fa4 la4 sol4 fa4 mi4
          re4 - re4 fa4 mi4 - mi4 sol4
          sib4 la4 sol4 fa4 mi4 re4 do#4 re4
          la4 - la4 sib4 la4 - la4 fa4
          sol4 - sol4 la4 sol4 - sol4 mi4
          fa4 mi4 re4 mi4 fa4 sol4 la4 sib4
          la4:2 sol4:2 fa4:2 mi4:2
        - |
          re2 re3 re2 re3 mi2 mi3 mi2 mi3
          re2 re3 re2 re3 la2 la3 la2 la3
          re2 re3 re2 re3 mi2 mi3 mi2 mi3
          sib2 sib3 fa2 fa3 la2 la3 la2 la3
          fa2 fa3 fa2 fa3 re2 re3 re2 re3
          mi2 mi3 mi2 mi3 do#3 do#3 do#3 do#3
          re2 re3 fa2 fa3 la2 la3 la2 la3
          re2:2 la2:2 re2:2 la2:2
  # Las dos canciones que no son de ningun nivel se dicen aqui por su nombre.
  titulo: portada
  jefe: asedio
"""

# La del genero de latigo. 'castillo' son 16 compases de ocho tiempos (128
# notas, unos 11 segundos antes de repetirse) en re menor, con la sensible
# do# de la escala menor armonica, que es de donde sale el aire de castillo:
# tema, respuesta, un puente que baja por cromatismos y vuelta al tema. El bajo
# va en corcheas saltando de octava, que es lo que empuja. 'cripta' es la
# lenta: la menor, notas largas y mucho silencio entre ellas.
_MUSICA_LATIGO = """  musica:
    castillo:
      velocidad: 5          # frames que dura cada nota (mas alto = mas lento)
      pistas:
        - |
          re5 mi5 fa5 sol5 la5:2 fa5 re5
          mi5 fa5 sol5 la5 sib5:2 la5 sol5
          fa5 sol5 la5 sib5 do#6:2 re6:2
          la5 fa5 re5 do#5 re5:3 -
          fa5 la5 do6 la5 sib5:2 sol5:2
          mi5 sol5 sib5 sol5 la5:2 fa5:2
          re5 fa5 la5 do#6 re6:2 la5:2
          sib5 la5 sol5 fa5 mi5:2 do#5:2
          la5:2 lab5:2 sol5:2 fa#5:2
          fa5:2 mi5:2 mib5:2 re5:2
          sol5 la5 sib5 do6 re6:2 do#6:2
          re6 - la5 - fa5 - re5 -
          re5 mi5 fa5 sol5 la5:2 fa5 re5
          mi5 fa5 sol5 la5 sib5:2 la5 sol5
          fa5 sol5 la5 sib5 do#6:2 re6:2
          la5 fa5 re5 do#5 re5:4
        - |
          re2 re3 re2 re3 la2 la3 la2 la3
          re2 re3 re2 re3 la2 la3 la2 la3
          fa2 fa3 fa2 fa3 la2 la3 do#3 la3
          re2 re3 la2 la3 re2 re3 la2 re3
          fa2 fa3 fa2 fa3 do3 do4 do3 do4
          la2 la3 la2 la3 mi3 mi4 mi3 mi4
          re2 re3 re2 re3 la2 la3 la2 la3
          la2 la3 do#3 do#4 mi3 mi4 la2 la3
          la2 la3 la2 la3 lab2 lab3 lab2 lab3
          sol2 sol3 sol2 sol3 fa2 fa3 fa2 fa3
          mi2 mi3 mi2 mi3 mib2 mib3 mib2 mib3
          re2 re3 la2 la3 re2 re3 la2 la3
          re2 re3 re2 re3 la2 la3 la2 la3
          re2 re3 re2 re3 la2 la3 la2 la3
          fa2 fa3 fa2 fa3 la2 la3 do#3 la3
          re2 re3 la2 la3 re2 re3 re2 re3
    cripta:
      velocidad: 8
      pistas:
        - |
          la4 - do5 - mi5 - do5 -
          si4 - re5 - sol#4 - si4 -
          la4 - do5 - mi5 - la5 -
          sol#5 - mi5 - do5 - si4 -
          fa5:2 mi5:2 re5:2 do5:2
          si4:2 la4:2 sol#4:2 si4:2
          do5 re5 mib5 mi5 fa5:2 mi5:2
          la5:4 sol#5:2 mi5:2
        - |
          la2 - mi3 - la2 - mi3 -
          mi2 - si2 - mi2 - si2 -
          la2 - mi3 - la2 - mi3 -
          do3 - sol#2 - mi2 - si2 -
          re2 - la2 - re2 - la2 -
          mi2 - si2 - mi2 - si2 -
          fa2 - do3 - mi2 - si2 -
          la2 - mi3 - la2:2 mi3:2
    # La del titulo: notas largas, sin prisa, esperando a que pulses Start.
    presagio:
      velocidad: 11
      pistas:
        - |
          re5 - do#5 - re5 - fa5 -
          mi5 - re5 - do#5 - la4 -
          sib4 - do5 - re5 - mi5 -
          fa5 - mi5:2 re5:4
        - |
          re2 - la2 - re2 - la2 -
          la2 - mi3 - la2 - mi3 -
          sib2 - fa3 - sib2 - fa3 -
          la2 - la2:2 re2:4
    # La del jefe: la misma casa, pero con prisa.
    duelo:
      velocidad: 5
      pistas:
        - |
          re5 - re5 mi5 fa5 - fa5 sol5
          la5 - la5 sol5 fa5 mi5 re5 do#5
          re5 - re5 mi5 fa5 - fa5 sol5
          la5 sib5 la5 sol5 fa5 mi5 re5 -
          la5 - la5 sib5 la5 - la5 fa5
          sol5 - sol5 la5 sol5 - sol5 mi5
          fa5 sol5 la5 sib5 la5 sol5 fa5 mi5
          re5:2 do#5:2 re5:4
        - |
          re2 re3 re2 re3 fa2 fa3 fa2 fa3
          la2 la3 la2 la3 re2 re3 re2 re3
          re2 re3 re2 re3 fa2 fa3 fa2 fa3
          la2 la3 sib2 sib3 la2 la3 la2 la3
          fa2 fa3 fa2 fa3 re2 re3 re2 re3
          mi2 mi3 mi2 mi3 do#3 do#3 do#3 do#3
          re2 re3 fa2 fa3 la2 la3 la2 la3
          la2:2 mi3:2 re2:4
  # Las dos canciones que no son de ningun nivel se dicen aqui por su nombre.
  titulo: presagio
  jefe: duelo
"""


ESTILOS = ("bosque", "hierro")


# La del genero de comando: marchas. Bajo que camina en corcheas -es lo que
# empuja- y melodias que suben por la escala menor, que es lo que suena a
# operacion militar de los ochenta. Cuatro: la del titulo, una por nivel y la
# del bunker.
_MUSICA_COMANDO = """  musica:
    himno:
      velocidad: 9
      pistas:
        - |
          la4 - do5 - mi5 - la5 -
          sol5 - mi5 - do5 - mi5 -
          fa5 - do5 - la4 - do5 -
          mi5 - re5 - do5:2 - -
        - |
          la2 - mi3 - la2 - mi3 -
          do3 - sol3 - do3 - sol3 -
          fa2 - do3 - fa2 - do3 -
          mi2 - si2 - la2:2 - -
    avanzada:
      velocidad: 7
      pistas:
        - |
          la4 - la4 do5 mi5 - re5 -
          do5 - si4 la4 si4 - mi4 -
          la4 - la4 do5 mi5 - fa5 -
          mi5 - re5 do5 si4 - - -
          do5 - do5 mi5 sol5 - fa5 -
          mi5 - re5 do5 re5 - la4 -
          la4 do5 mi5 la5 sol5 mi5 do5 la4
          mi4:2 la4:2 mi4:2 la4:2
        - |
          la2 la3 la2 la3 la2 la3 la2 la3
          mi2 mi3 mi2 mi3 mi2 mi3 mi2 mi3
          fa2 fa3 fa2 fa3 fa2 fa3 fa2 fa3
          mi2 mi3 mi2 mi3 mi2 mi3 mi2 mi3
          do3 do4 do3 do4 do3 do4 do3 do4
          sol2 sol3 sol2 sol3 sol2 sol3 sol2 sol3
          la2 la3 do3 do4 mi3 mi2 la2 la3
          la2:2 mi3:2 la2:2 mi3:2
    patrulla:
      velocidad: 8
      pistas:
        - |
          mi4 - sol4 la4 si4 - la4 -
          sol4 - mi4 - re4 - mi4 -
          do5 - si4 la4 sol4 - la4 -
          si4 - sol4 - mi4 - - -
          la4 - do5 re5 mi5 - re5 -
          do5 - la4 - sol4 - la4 -
          mi5 re5 do5 si4 la4 sol4 mi4 sol4
          la4:2 mi4:2 la4:2 - -
        - |
          la2 - mi3 - la2 - mi3 -
          mi2 - si2 - mi2 - si2 -
          do3 - sol3 - do3 - sol3 -
          mi2 - si2 - mi2 - - -
          la2 - mi3 - la2 - mi3 -
          fa2 - do3 - fa2 - do3 -
          la2 la3 do3 do4 mi3 mi2 la2 mi3
          la2:2 mi3:2 la2:2 - -
    asalto:
      velocidad: 6
      pistas:
        - |
          re5 - do#5 re5 mi5 - fa5 -
          mi5 - re5 do#5 re5 - la4 -
          re5 - mi5 fa5 sol5 - la5 -
          fa5 mi5 re5 do#5 re5 - - -
          la5 - la5 sol5 fa5 - mi5 -
          re5 - mi5 fa5 mi5 - re5 -
          do#5 re5 mi5 fa5 sol5 la5 sib5 la5
          re5:2 la4:2 re5:2 - -
        - |
          re2 re3 re2 re3 la2 la3 la2 la3
          si2 si3 si2 si3 fa2 fa3 fa2 fa3
          sol2 sol3 sol2 sol3 re3 re2 re3 re2
          la2 la3 la2 la3 re2 re3 re2 re3
          fa2 fa3 fa2 fa3 do#3 do#3 do#3 do#3
          si2 si3 si2 si3 sol2 sol3 sol2 sol3
          la2 la3 do3 do4 mi3 mi2 la2 la3
          re2:2 la2:2 re2:2 - -
  # Las dos canciones que no son de ningun nivel se dicen aqui por su nombre.
  titulo: himno
  jefe: asalto
"""


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
    control: str                 # la fila del punto de control, si lo lleva
    municion: str                # el objeto de `efecto: municion`, si lo hay
    arma: str                    # el objeto que cambia de arma secundaria
    mejora: str                  # el objeto de `efecto: mejora`, si lo hay
    animos: str                  # animaciones del heroe propias del genero
    musica: str                  # el bloque `musica:` entero
    canciones: tuple             # como se llama la de cada nivel
    eventos: str                 # efectos de sonido que anade este genero
    spawns: str                  # simbolos de mapa que anade este genero
    bichos: str                  # los enemigos del genero (menos el jefe)
    bichos_spawn: str            # los simbolos de esos enemigos y el del jefe
    jefe: str                    # el jefe del genero
    suelta: str                  # que suelta el rompible
    con_escaleras: bool          # si los niveles llevan una
    con_control: bool            # si los niveles llevan puntos de control


# Los bichos de plataformas: el mismo dibujo con dos comportamientos, que es lo
# que ensena que el comportamiento y el dibujo son cosas distintas.
def _bichos_plataformas(nombres: Dict[str, str]) -> str:
    return ("  %s:\n"
            "    sprite: graficos/enemigo.png\n"
            "    caja: [12, 11]\n"
            "    comportamiento: patrulla\n"
            "    velocidad: 0.4\n"
            "    puntos: 100\n"
            "    animaciones:\n"
            "      quieto: {frames: [0, 1], velocidad: 14}\n"
            "      correr: {frames: [0, 1], velocidad: 10}\n"
            "  %s:\n"
            "    sprite: graficos/enemigo.png\n"
            "    caja: [12, 11]\n"
            "    comportamiento: volador\n"
            "    velocidad: 0.6\n"
            "    amplitud: 28\n"
            "    periodo: 150\n"
            "    puntos: 200\n"
            "    animaciones:\n"
            "      quieto: {frames: [0, 1], velocidad: 6}\n"
            % (nombres["andar"], nombres["volar"]))


# Y los del genero de latigo, que son otros y se dibujan aparte: aqui no se
# pisa a nadie, asi que un bicho con 'vida: 2' son dos latigazos, y eso es lo
# que obliga a acercarse, pegar y salir. El murcielago va por el aire a la
# altura de la cabeza: agachandote pasa por encima.
_BICHOS_CASTLEVANIA = (
    "  esqueleto:\n"
    "    sprite: graficos/esqueleto.png\n"
    "    caja: [10, 15]\n"
    "    comportamiento: patrulla\n"
    "    velocidad: 0.35\n"
    "    vida: 2                # dos latigazos: aqui no se pisa a nadie\n"
    "    puntos: 200\n"
    "    animaciones:\n"
    "      quieto: {frames: [0, 1], velocidad: 16}\n"
    "      correr: {frames: [0, 1], velocidad: 10}\n"
    "  murcielago:\n"
    "    sprite: graficos/murcielago.png\n"
    "    caja: [12, 8]\n"
    "    comportamiento: volador\n"
    "    velocidad: 0.7\n"
    "    amplitud: 24           # cuanto sube y baja\n"
    "    periodo: 110           # frames que tarda en subir y bajar\n"
    "    puntos: 200\n"
    "    animaciones:\n"
    "      quieto: {frames: [0, 1], velocidad: 5}\n"
)

# El jefe. Va aparte de los otros bichos porque el comentario que lo explica
# vale para los dos generos: lo que cambia es a que se parece y como pega.
def _jefe_plataformas(nombres: Dict[str, str]) -> str:
    return ("  # Un jefe es un enemigo con 'jefe: si': aguanta varios pisotones,\n"
            "  # el marcador ensena lo que le queda y al matarlo se acaba el nivel.\n"
            "  %s:\n"
            "    sprite: graficos/enemigo.png\n"
            "    caja: [12, 11]\n"
            "    comportamiento: perseguidor\n"
            "    velocidad: 0.5\n"
            "    rango: 160\n"
            "    vida: 5\n"
            "    puntos: 1000\n"
            "    jefe: si\n"
            "    animaciones:\n"
            "      quieto: {frames: [0, 1], velocidad: 8}\n"
            "      correr: {frames: [0, 1], velocidad: 5}\n"
            % nombres["jefe"])


# El del genero de latigo: el encapuchado. Aguanta mas porque aqui no se pisa
# a nadie y cada golpe es un latigazo, y va mas despacio para que se pueda
# torear: acercarse, pegar y salir.
_JEFE_CASTLEVANIA = (
    "  # Un jefe es un enemigo con 'jefe: si': aguanta varios golpes, el\n"
    "  # marcador ensena lo que le queda y al matarlo se acaba el nivel.\n"
    "  muerte:\n"
    "    sprite: graficos/muerte.png\n"
    "    caja: [12, 14]\n"
    "    comportamiento: perseguidor\n"
    "    velocidad: 0.4\n"
    "    rango: 200             # desde donde te huele\n"
    "    vida: 5                # cinco latigazos, y aqui no vale pisarlo\n"
    "    puntos: 2000\n"
    "    jefe: si\n"
    "    animaciones:\n"
    "      quieto: {frames: [0, 1], velocidad: 10}\n"
    "      correr: {frames: [0, 1], velocidad: 6}\n"
)

def _genero_plataformas(nombres: Dict[str, str], estilo: str) -> Genero:
    return Genero(
        nombre="plataformas",
        titulo="plataformas",
        resumen=("saltar, pisar enemigos y disparar. El salto se corrige en el "
                 "aire. Lo de toda la vida."),
        fisica=("  vida: 2              # golpes que aguanta antes de perder una vida\n"
                "  control_aire: 0.16   # cuanto se corrige el salto en el aire\n"
                "  pisar_enemigos: si\n"
                "  rebote: 3.6          # impulso al pisar un enemigo\n"
                "  agachado: si         # con abajo: ni andas ni saltas, pero\n"
                "                       # disparas por abajo y lo que pasa por\n"
                "                       # encima ya no te toca\n"),
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
        control="",
        municion="",
        arma="",
        mejora="",
        animos=("    atacar: {frames: [7], velocidad: 6}\n"
                "    agachado: {frames: [10]}\n"),
        musica=_MUSICA_BOSQUE if estilo == "bosque" else _MUSICA_HIERRO,
        canciones=(("bosque", "cueva") if estilo == "bosque"
                   else ("galeria", "pozo")),
        eventos="",
        spawns="",
        bichos=_bichos_plataformas(nombres),
        bichos_spawn="  s: %s\n  m: %s\n  J: %s\n" % (
            nombres["andar"], nombres["volar"], nombres["jefe"]),
        jefe=_jefe_plataformas(nombres),
        suelta=nombres["moneda"],
        con_escaleras=False,
        con_control=False,
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
                "  velocidad_escalera: 0.8\n"
                "  agachado: si         # con abajo: no andas ni saltas, pero\n"
                "                       # pegas por abajo y lo que pasa por\n"
                "                       # encima ya no te toca\n"),
        armas=("  # El latigo. `preparacion` son los frames en los que el brazo\n"
               "  # todavia sale y no hace dano, y `clavado` te planta en el sitio\n"
               "  # mientras pegas: es lo que obliga a medir la distancia.\n"
               "  #\n"
               "  # Con `tipo: golpe`, `sprite:` es **el arma**: se dibuja delante\n"
               "  # del jugador justo mientras el golpe hace dano, y cada\n"
               "  # fotograma es un nivel de mejora (24, 36 y 48 px), asi que lo\n"
               "  # que se ve es exactamente lo que llega.\n"
               "  ataque:\n"
               "    tipo: golpe\n"
               "    sprite: graficos/latigo.png\n"
               "    frame: [48, 16]\n"
               "    caja: [48, 16]\n"
               "    desplazamiento: [0, 0]\n"
               "    alcance: 24\n"
               "    duracion: 14\n"
               "    preparacion: 5\n"
               "    clavado: si\n"
               "    espera: 18\n"
               "    dano: 1\n"
               "    mejoras: 2             # cuantas veces se puede mejorar\n"
               "    alcance_mejora: 12     # px que alarga cada mejora\n"
               "    animaciones:\n"
               "      # un fotograma por nivel del arma: el motor elige el que\n"
               "      # toca segun las mejoras que lleves\n"
               "      quieto: {frames: [0, 1, 2]}\n"
               "  # Las armas secundarias: se tiran con **arriba + accion** y\n"
               "  # gastan municion. Se empieza con la primera y se cambia\n"
               "  # cogiendo el objeto de la otra (el hacha, aqui abajo).\n"
               "  secundarias:\n"
               "    cuchillo:\n"
               "      tipo: recta          # va recto hasta que choca\n"
               "      marcador: DAGA       # como sale en el marcador; con\n"
               "                           # dos armas o mas, ahi pone cual\n"
               "                           # llevas en vez de 'AMMO'\n"
               "      sprite: graficos/cuchillo.png\n"
               "      frame: [16, 16]\n"
               "      caja: [10, 4]\n"
               "      desplazamiento: [3, 6]\n"
               "      velocidad: 4.0\n"
               "      alcance: 200\n"
               "      espera: 24\n"
               "      coste: 1             # municion que gasta cada tirada\n"
               "      dano: 1\n"
               "      a_la_vez: 3          # cuantas caben en el aire\n"
               "    hacha:\n"
               "      tipo: arco           # sube y cae: hay que medir\n"
               "      marcador: HACHA\n"
               "      sprite: graficos/hacha.png\n"
               "      frame: [16, 16]\n"
               "      caja: [12, 12]\n"
               "      desplazamiento: [2, 2]\n"
               "      velocidad: 2.2\n"
               "      impulso: 4.0         # con cuanta fuerza sale hacia arriba\n"
               "      gravedad: 0.20\n"
               "      alcance: 200\n"
               "      espera: 30\n"
               "      coste: 2\n"
               "      dano: 2\n"
               "      a_la_vez: 1          # una cada vez, como los clasicos\n"
               "      animaciones:\n"
               "        quieto: {frames: [0, 1, 2, 3], velocidad: 4}\n"),
        escaleras=("    '/': {tile: 6, tipo: escalera}\n"
                   "    '|': {tile: 7, tipo: escalera_izquierda}\n"),
        # La antorcha no estorba: se pasa por delante. Al tocarla se apunta
        # donde estas, y si te matan vuelves ahi en vez de al principio.
        control="    '!': {tile: 8, tipo: control}\n",
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
        # 'efecto: mejora' alarga el latigo un paso (`alcance_mejora`) y se
        # pierde al morir: es lo que hace que una vida valga algo.
        # 'efecto: subarma' cambia el arma secundaria que llevas en la mano
        arma=("  hacha:\n"
              "    sprite: graficos/hacha.png\n"
              "    frame: [16, 16]\n"
              "    caja: [12, 12]\n"
              "    puntos: 100\n"
              "    efecto: subarma\n"
              "    arma: hacha            # a cual de 'secundarias:' cambia\n"
              "    animaciones:\n"
              "      quieto: {frames: [0, 1, 2, 3], velocidad: 6}\n"),
        mejora=("  mejora:\n"
                "    sprite: graficos/mejora.png\n"
                "    caja: [10, 10]\n"
                "    puntos: 200\n"
                "    efecto: mejora\n"
                "    cantidad: 1\n"
                "    animaciones:\n"
                "      quieto: {frames: [0, 1], velocidad: 10}\n"),
        # 'atacar' son dos poses: el brazo echado atras mientras dura la
        # `preparacion:` del golpe y estirado cuando ya hace dano. Con
        # 'bucle: no' la segunda se queda hasta el final, en vez de volver a
        # la primera a mitad del latigazo.
        animos=("    atacar: {frames: [6, 7], velocidad: 5, bucle: no}\n"
                "    subir:  {frames: [8]}   # de espaldas, en la escalera\n"
                "    agachado: {frames: [10]}\n"),
        musica=_MUSICA_LATIGO,
        canciones=("castillo", "cripta"),
        # La antorcha del punto de control tenia el sonido sin poner: se
        # tocaba y no sonaba nada, que es justo lo que hay que oir para saber
        # que ya no vuelves al principio del nivel.
        eventos='    control: {notas: "la5 do6 mi6", velocidad: 4}\n',
        spawns="  M: mejora\n  H: hacha\n",
        bichos=_BICHOS_CASTLEVANIA,
        bichos_spawn="  s: esqueleto\n  m: murcielago\n  J: muerte\n",
        jefe=_JEFE_CASTLEVANIA,
        suelta=nombres["municion"],
        con_escaleras=True,
        con_control=True,
    )


GENEROS = ("plataformas", "castlevania", "comando")

# Como se llama cada cosa en cada estilo de dibujo.
_NOMBRES = {
    "bosque": {"moneda": "moneda", "municion": "corazon",
               "andar": "seta", "volar": "mosca", "jefe": "jefazo"},
    "hierro": {"moneda": "gema", "municion": "chispa",
               "andar": "raton", "volar": "murcielago", "jefe": "guardian"},
}


def _genero_comando(nombres: Dict[str, str], estilo: str) -> Genero:
    """El de vista cenital.

    No arma su game.yaml a trozos como los otros dos -se ve desde arriba, asi
    que casi nada de la fisica de saltar le sirve- y tiene su propia plantilla
    entera. De este objeto solo se usa como se llama y que promete, que es lo
    que sale en el menu de `ngplat nuevo`.
    """
    return replace(
        _genero_plataformas(nombres, estilo),
        nombre="comando",
        titulo="comando",
        resumen=("visto desde arriba: ocho direcciones, granadas y subir la "
                 "pantalla rescatando prisioneros."),
    )


def genero_de(nombre: str, estilo: str) -> Genero:
    nombres = _NOMBRES[estilo]
    if nombre == "castlevania":
        return _genero_castlevania(nombres)
    if nombre == "comando":
        return _genero_comando(nombres, estilo)
    return _genero_plataformas(nombres, estilo)


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
      golpe al borde de una plataforma te tira al vacio; 'comando' se ve
      **desde arriba** -otra cosa entera- y va de subir la pantalla a tiros
      rescatando prisioneros.

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
    if genero == "comando":
        # Se ve desde arriba: el heroe de perfil, los tiles de plataformas y
        # los bichos de saltar no sirven de nada aqui, asi que los dibujos de
        # este genero pisan a los del estilo.
        dibujos = dict(dibujos)
        dibujos.update(art_comando.todos(estilo))
    for relativo, imagen in dibujos.items():
        ruta = os.path.join(destino, relativo)
        write_png(ruta, imagen)
        creados.append(relativo)

    if estilo == "bosque":
        os.makedirs(os.path.join(destino, "sonidos"), exist_ok=True)
        for relativo, muestra in art_sonido.todos().items():
            escribir_wav(os.path.join(destino, relativo), muestra)
            creados.append(relativo)

    if genero == "comando":
        # Se sube: se empieza abajo y la meta esta arriba del todo.
        niveles = (
            _nivel_yaml("EL CAMPAMENTO", _nivel_comando_1(),
                        "#183018", musica="avanzada")
            + _nivel_yaml("EL BUNKER", _nivel_comando_2(),
                          "#20281c", musica="patrulla")
        )
        contenido = GAME_YAML_COMANDO.format(
            titulo=titulo.upper()[:24], autor=autor[:24], niveles=niveles,
            musica=_MUSICA_COMANDO)
        with open(os.path.join(destino, "game.yaml"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(contenido)
        creados.append("game.yaml")
        with open(os.path.join(destino, ".gitignore"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write("build/\npreview.html\n.neoplat/\n")
        creados.append(".gitignore")
        return creados

    if estilo == "bosque":
        niveles = (
            _nivel_yaml("BOSQUE",
                        _nivel_1(llave=True, escalera=g.con_escaleras,
                                 control=g.con_control),
                        "#101830", musica=g.canciones[0], llaves=1)
            # el segundo nivel usa solo la capa lejana: se puede elegir por nivel
            + _nivel_yaml("CUEVA",
                          _nivel_2(control=g.con_control,
                                   escalera=g.con_escaleras),
                          "#180c20", capas="cielo", musica=g.canciones[1])
        )
        plantilla = GAME_YAML
    else:
        niveles = (
            _nivel_yaml("GALERIA",
                        _nivel_1(escalera=g.con_escaleras, control=g.con_control),
                        "#14121e", musica=g.canciones[0])
            + _nivel_yaml("EL POZO",
                          _nivel_2(control=g.con_control,
                                   escalera=g.con_escaleras),
                          "#0e1018", musica=g.canciones[1])
        )
        plantilla = GAME_YAML_HIERRO
    contenido = plantilla.format(
        titulo=titulo.upper()[:24], autor=autor[:24], niveles=niveles,
        fisica=g.fisica, armas=g.armas, escaleras=g.escaleras, animos=g.animos,
        control=g.control, municion=g.municion, mejora=g.mejora,
        musica=g.musica, eventos=g.eventos, arma=g.arma,
        spawns=g.spawns, suelta=g.suelta,
        bichos=g.bichos, bichos_spawn=g.bichos_spawn, jefe=g.jefe)
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
