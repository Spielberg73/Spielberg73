"""Sonido: de la notacion del `game.yaml` a tablas de notas.

El chip de sonido de la Neo Geo (YM2610) tiene, entre otras cosas, tres canales
de onda cuadrada (SSG) heredados del AY-3-8910. NeoPlat usa esos tres:

    canal A -> melodia        canal B -> acompanamiento      canal C -> efectos

Aqui se convierten las notas escritas por el usuario ("do4 mi4 sol4") en los
periodos que entiende el chip. El mismo dato alimenta la ROM y el preview del
navegador, asi que suenan igual (dentro de lo que da un navegador).

Periodo del canal SSG:  periodo = reloj / (16 * frecuencia)
con el reloj del SSG de la Neo Geo a 4 MHz  ->  periodo = 250000 / frecuencia.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .errors import ProjectError

SSG_CLOCK = 4000000                  # Hz del SSG del YM2610 en Neo Geo
SSG_MAX_PERIOD = 4095                # el periodo es de 12 bits
SSG_MIN_PERIOD = 1

# Semitonos desde do, en espanol y en ingles.
NOTAS = {
    "do": 0, "c": 0,
    "re": 2, "d": 2,
    "mi": 4, "e": 4,
    "fa": 5, "f": 5,
    "sol": 7, "g": 7,
    "la": 9, "a": 9,
    "si": 11, "b": 11,
}

NOTA_RE = re.compile(r"^(do|re|mi|fa|sol|la|si|[a-g])([#b]?)(-?\d)?(?::(\d+))?$", re.I)

# Eventos que puede disparar el motor. Son fijos: el juego los produce y el
# usuario decide que suena en cada uno.
EVENTOS = ["empezar", "salto", "doble_salto", "moneda", "pisar", "golpe",
           "muerte", "meta", "vida"]

EVENTO_ALIAS = {
    "start": "empezar", "inicio": "empezar",
    "jump": "salto", "saltar": "salto",
    "double_jump": "doble_salto", "doble": "doble_salto",
    "coin": "moneda", "objeto": "moneda", "item": "moneda",
    "stomp": "pisar", "pisar_enemigo": "pisar",
    "hurt": "golpe", "dano": "golpe", "daño": "golpe",
    "die": "muerte", "morir": "muerte",
    "goal": "meta", "nivel": "meta",
    "life": "vida", "1up": "vida",
}

# Bits que usa el motor (coinciden con NP_SFX_* de np_types.h).
EVENTO_BIT = {nombre: 1 << i for i, nombre in enumerate(EVENTOS)}


def frecuencia_de_nota(semitono: int, octava: int) -> float:
    """La4 (a4) = 440 Hz."""
    # distancia en semitonos hasta la4: la4 esta en la octava 4, semitono 9
    distancia = (octava - 4) * 12 + (semitono - 9)
    return 440.0 * (2.0 ** (distancia / 12.0))


def periodo_de_frecuencia(hz: float, where: str = "") -> int:
    if hz <= 0:
        return 0
    periodo = int(round(SSG_CLOCK / (16.0 * hz)))
    if periodo < SSG_MIN_PERIOD or periodo > SSG_MAX_PERIOD:
        raise ProjectError(
            "la frecuencia %.1f Hz no la puede dar el chip de la Neo Geo" % hz,
            hint="usa notas entre do1 y do8 (unos 30 Hz a 4000 Hz)",
            where=where or None,
        )
    return periodo


@dataclass
class Paso:
    """Un paso de una secuencia: periodo (0 = silencio) y cuanto dura."""
    periodo: int
    duracion: int
    volumen: int = 12
    ruido: int = 0            # 1 = usa el generador de ruido (percusion)


@dataclass
class Efecto:
    nombre: str
    pasos: List[Paso] = field(default_factory=list)


@dataclass
class Musica:
    nombre: str
    velocidad: int                    # frames por nota
    pistas: List[List[Paso]] = field(default_factory=list)
    bucle: bool = True


@dataclass
class Sonido:
    efectos: Dict[str, Efecto] = field(default_factory=dict)
    musica: Dict[str, Musica] = field(default_factory=dict)

    def evento_bits(self) -> Dict[str, int]:
        return {nombre: EVENTO_BIT[nombre] for nombre in self.efectos}


def parsear_notas(texto: str, velocidad: int, volumen: int, where: str) -> List[Paso]:
    """Convierte "do4 mi4 - sol4:2" en pasos con periodo y duracion.

    - las notas van en espanol (do re mi fa sol la si) o en ingles (c d e f g a b)
    - '#' sube un semitono, 'b' lo baja; el numero es la octava (4 por defecto)
    - '-' es un silencio y '|' se ignora (sirve para separar compases)
    - ':n' multiplica la duracion de esa nota
    """
    pasos: List[Paso] = []
    for token in str(texto).replace("|", " ").split():
        if token in ("-", "_", "."):
            pasos.append(Paso(0, velocidad, volumen))
            continue
        match = NOTA_RE.match(token)
        if not match:
            raise ProjectError(
                "no entiendo la nota '%s'" % token,
                hint="ejemplos: do4, sol#3, la5:2, '-' para silencio",
                where=where,
            )
        nombre, alteracion, octava, largo = match.groups()
        semitono = NOTAS[nombre.lower()]
        if alteracion == "#":
            semitono += 1
        elif alteracion == "b":
            semitono -= 1
        octava_num = int(octava) if octava is not None else 4
        hz = frecuencia_de_nota(semitono, octava_num)
        pasos.append(Paso(periodo_de_frecuencia(hz, where), velocidad * int(largo or 1),
                          volumen))
    if not pasos:
        raise ProjectError("la secuencia de notas esta vacia", where=where)
    return pasos


def barrido(desde: float, hasta: float, duracion: int, volumen: int, where: str
            ) -> List[Paso]:
    """Efecto de frecuencia que sube o baja (saltos, disparos, monedas)."""
    duracion = max(2, min(60, duracion))
    pasos: List[Paso] = []
    for i in range(duracion):
        hz = desde + (hasta - desde) * i / float(duracion - 1)
        pasos.append(Paso(periodo_de_frecuencia(hz, where), 1, volumen))
    return pasos


def ruido(duracion: int, volumen: int, tono: int = 16) -> List[Paso]:
    """Golpes y explosiones: el generador de ruido del SSG."""
    duracion = max(1, min(60, duracion))
    pasos = [Paso(tono, duracion, volumen, ruido=1)]
    return pasos
