"""Sonido: de la notacion del `game.yaml` a notas con su frecuencia.

Las notas se guardan en **hercios**, que es lo unico que entienden por igual
todas las maquinas; cada sistema las traduce despues a lo que pide su chip:

    Neo Geo   YM2610 (SSG)   periodo = 4.000.000 / (16 * frecuencia)
    Mega Drive SN76489 (PSG) periodo = 3.579.545 / (32 * frecuencia)
    Amiga     Paula          periodo = 3.546.895 / (frecuencia * muestras)

Se usan tres canales de onda cuadrada: dos para la musica (melodia y
acompanamiento) y uno para los efectos. El mismo dato alimenta las tres ROMs y
el preview del navegador, asi que suenan igual (dentro de lo que da cada chip).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import wav
from .errors import ProjectError

SSG_CLOCK = 4000000                  # Hz del SSG del YM2610 (Neo Geo)
SSG_MAX_PERIOD = 4095                # el periodo es de 12 bits
SSG_MIN_PERIOD = 1

PSG_CLOCK = 3579545                  # Hz del SN76489 (Mega Drive)
YM2149_CLOCK = 2000000               # Hz del YM2149 (Atari ST)
PSG_MAX_PERIOD = 1023                # 10 bits
PAULA_CLOCK = 3546895                # reloj de Paula en PAL (Amiga)
PAULA_MIN_PERIOD = 124               # por debajo la DMA no da abasto
PAULA_MAX_PERIOD = 65535

# Margen de notas que se admite al escribir el juego. Cada sistema comprueba
# despues si su chip puede darlas.
FREQ_MIN = 30.0
FREQ_MAX = 8000.0

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


def comprobar_frecuencia(hz: float, where: str = "") -> float:
    """Se queda con la frecuencia si esta dentro de lo que sabe tocar el kit."""
    if hz <= 0:
        return 0.0
    if hz < FREQ_MIN or hz > FREQ_MAX:
        raise ProjectError(
            "la nota de %.1f Hz se sale de lo que tocan estas maquinas" % hz,
            hint="usa notas entre do1 y do8 (unos 30 Hz a 4200 Hz)",
            where=where or None,
        )
    return hz


def periodo_ssg(hz: float) -> int:
    """Neo Geo (YM2610, canales SSG)."""
    if hz <= 0:
        return 0
    return max(SSG_MIN_PERIOD, min(SSG_MAX_PERIOD, int(round(SSG_CLOCK / (16.0 * hz)))))


def periodo_psg(hz: float) -> int:
    """Mega Drive (SN76489). El registro es de 10 bits."""
    if hz <= 0:
        return 0
    return max(1, min(PSG_MAX_PERIOD, int(round(PSG_CLOCK / (32.0 * hz)))))


def periodo_ym2149(hz: float) -> int:
    """Atari ST (YM2149). Es el mismo chip que el SSG de la Neo Geo pero a la
    mitad de reloj, asi que el mismo periodo da una nota una octava mas baja."""
    if hz <= 0:
        return 0
    return max(SSG_MIN_PERIOD, min(SSG_MAX_PERIOD,
                                   int(round(YM2149_CLOCK / (16.0 * hz)))))


def periodo_paula(hz: float, muestras: int = 32) -> int:
    """Amiga (Paula). El periodo depende de cuantas muestras tiene la onda."""
    if hz <= 0:
        return 0
    periodo = int(round(PAULA_CLOCK / (hz * muestras)))
    return max(PAULA_MIN_PERIOD, min(PAULA_MAX_PERIOD, periodo))


def periodo_de_frecuencia(hz: float, where: str = "") -> int:
    """Compatibilidad: el periodo del SSG, que es lo que usaba antes el kit."""
    return periodo_ssg(comprobar_frecuencia(hz, where))


@dataclass
class Paso:
    """Un paso de una secuencia: la nota (en Hz, 0 = silencio) y cuanto dura."""
    frecuencia: float
    duracion: int
    volumen: int = 12
    ruido: int = 0            # 1 = usa el generador de ruido (percusion)

    @property
    def periodo(self) -> int:
        """Periodo del SSG, por comodidad (Neo Geo)."""
        return periodo_ssg(self.frecuencia)


@dataclass
class Efecto:
    """Un efecto: o una secuencia de pasos para el chip, o una muestra digital.

    Las dos cosas a la vez no: `muestra` manda cuando esta puesta, y `pasos`
    queda como recambio para las maquinas que no saben tocar muestras (el Atari
    ST) y para el preview mientras carga."""
    nombre: str
    pasos: List[Paso] = field(default_factory=list)
    muestra: Optional[wav.Muestra] = None
    ruta: str = ""                    # el archivo del que salio, para avisos

    @property
    def digital(self) -> bool:
        return self.muestra is not None


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
            pasos.append(Paso(0.0, velocidad, volumen))
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
        hz = comprobar_frecuencia(frecuencia_de_nota(semitono, octava_num), where)
        pasos.append(Paso(hz, velocidad * int(largo or 1), volumen))
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
        pasos.append(Paso(comprobar_frecuencia(hz, where), 1, volumen))
    return pasos


def ruido(duracion: int, volumen: int, tono: int = 16) -> List[Paso]:
    """Golpes y explosiones: el generador de ruido del chip.

    La frecuencia hace de "color" del ruido; cada sistema la usa como puede.
    """
    duracion = max(1, min(60, duracion))
    return [Paso(SSG_CLOCK / (16.0 * max(1, tono)), duracion, volumen, ruido=1)]


# --- muestras digitales: del WAV a la tabla en C -----------------------
#
# El dato es el mismo en las cuatro maquinas que las tocan (mono, 8 bits con
# signo); lo que cambia es a que frecuencia se guardan y que numero hay que
# meterle al chip para que salgan a esa frecuencia. Por eso esto es una sola
# funcion con dos parametros: el ritmo y como se calcula el periodo.

def _bytes_c(datos: bytes, por_linea: int = 16) -> List[str]:
    """Los bytes tal cual. En la tabla van como `uint8_t` porque lo que
    importa es lo que queda en la ROM, no como se lea: el Amiga guarda la
    muestra con signo (es lo que come Paula) y la Jaguar con el silencio en
    128 (es lo que le conviene a `loadb` del DSP), y las dos son bytes."""
    valores = [str(b) for b in datos]
    return ["    " + ", ".join(valores[i:i + por_linea]) + ","
            for i in range(0, len(valores), por_linea)]


def preparar_muestra(efecto: Efecto, ritmo: int, maximo: int) -> Optional[wav.Muestra]:
    """La muestra de un efecto, ya a la frecuencia de esa maquina y recortada."""
    if efecto.muestra is None:
        return None
    muestra = wav.remuestrear(efecto.muestra, ritmo)
    return wav.recortar(muestra, maximo)


def tabla_de_muestras_c(efectos: List[Efecto], ritmo: int, fps: int,
                        periodo, maximo: int = 32768,
                        par: bool = False,
                        sin_signo: bool = False) -> Tuple[List[str], int]:
    """Las lineas de C con las muestras y su tabla, y cuantos bytes ocupan.

    `periodo(ritmo)` es lo que hay que escribirle al chip; `par` rellena cada
    muestra hasta un numero par de bytes (Paula lee palabras, no bytes), y
    `sin_signo` las guarda con el silencio en 128 (que es lo que le conviene al
    DSP de la Jaguar).
    """
    lineas: List[str] = []
    entradas: List[str] = []
    total = 0
    for i, efecto in enumerate(efectos):
        muestra = preparar_muestra(efecto, ritmo, maximo)
        if muestra is None or not len(muestra):
            entradas.append("    { 0, 0, 0, 0 },")
            continue
        datos = muestra.datos
        if sin_signo:
            datos = bytes((b + 128) & 0xFF for b in datos)
        if par and len(datos) % 2:
            datos += b"\x00"
        total += len(datos)
        lineas.append("static const uint8_t np_pcm%d[] = {" % i)
        lineas.extend(_bytes_c(datos))
        lineas.append("};")
        lineas.append("")
        frames = max(1, int(round(len(datos) * fps / float(ritmo) + 0.5)))
        entradas.append("    { np_pcm%d, %d, %d, %d },"
                        % (i, len(datos), periodo(ritmo), frames))
    lineas.append("const NpSndMuestra np_snd_muestras[] = {")
    lineas.extend(entradas if entradas else ["    { 0, 0, 0, 0 },"])
    lineas.append("    { 0, 0, 0, 0 }")
    lineas.append("};")
    return lineas, total


def tabla_de_muestras_vacia() -> List[str]:
    """La tabla, pero sin nada: para las maquinas que no tocan muestras."""
    return ["const NpSndMuestra np_snd_muestras[] = {",
            "    { 0, 0, 0, 0 }",
            "};"]
