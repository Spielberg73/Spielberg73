"""Los timbres de FM: un mismo sonido para los tres chips que lo tienen.

Tres de las maquinas del kit llevan un chip de FM de **cuatro operadores** de
Yamaha, y los tres son primos:

    YM2612   Mega Drive     6 canales   familia OPN
    YM2610   Neo Geo        4 canales   familia OPN (mas SSG y ADPCM)
    YM2151   Sharp X68000   8 canales   familia OPM

«Cuatro operadores» quiere decir cuatro osciladores de seno por voz, cada uno
con su propia envolvente, conectados entre si de ocho maneras distintas (el
**algoritmo**). Los que suenan son los que estan al final de la cadena -las
*portadoras*-; los de antes no se oyen: **deforman** a los siguientes, y de ahi
salen los metales, las campanas y los bajos que suenan a los ochenta.

Un timbre son, pues, cuatro operadores y dos numeros: con que algoritmo se
conectan y cuanta realimentacion se le da al primero. Los tres chips entienden
**los mismos parametros** —cambia donde se escriben, no lo que significan— asi
que aqui se guardan una sola vez y cada maquina los mete en sus registros.

Lo que no se guarda aqui es la nota: el timbre dice como suena un instrumento,
y la nota, cual toca. Por eso un mismo timbre vale para toda una pista.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class Operador:
    """Un oscilador con su envolvente.

    - `mul`   multiplica la frecuencia de la nota (1 = la nota, 2 = la octava
              de arriba...). Con `mul` distintos entre operadores salen los
              armonicos, y con numeros que no casan, las campanas.
    - `dt`    desafina un pelin ese operador. Dos operadores casi iguales pero
              no del todo es lo que hace que un sonido «respire».
    - `tl`    lo fuerte que suena, **al reves**: 0 es a tope y 127 callado. En
              una portadora es el volumen; en un modulador, cuanto deforma al
              siguiente, o sea el brillo.
    - `ar`    lo rapido que arranca (31 = de golpe, 1 = subiendo despacio).
    - `dr`    lo rapido que cae hasta el sostenido, y `sl` donde se queda.
    - `sr`    si sigue cayendo mientras aguantas la nota (0 = se queda).
    - `rr`    lo rapido que se apaga al soltarla.
    - `ks`    cuanto se acortan las envolventes segun se sube de octava, que es
              lo que hace que los agudos de un piano duren menos.
    """
    mul: int = 1
    dt: int = 0
    tl: int = 0
    ar: int = 31
    dr: int = 0
    sr: int = 0
    rr: int = 7
    sl: int = 0
    ks: int = 0
    am: int = 0


@dataclass
class Timbre:
    nombre: str
    algoritmo: int = 4               # como se conectan los cuatro (0-7)
    realimentacion: int = 0          # cuanto se muerde la cola el primero (0-7)
    operadores: List[Operador] = field(default_factory=list)

    def op(self, i: int) -> Operador:
        return self.operadores[i] if i < len(self.operadores) else Operador(tl=127)


# --- los timbres que trae el kit ------------------------------------------
#
# Ocho, elegidos para que se distingan entre si a la primera y para que
# cualquiera de ellos sirva de melodia o de acompanamiento. No pretenden imitar
# a un instrumento de verdad: pretenden sonar a **esa** maquina.
#
# El que quiera los suyos los escribe en el game.yaml con estos mismos nombres
# de parametro; esto no es una lista cerrada, es lo que hay si no dices nada.

TIMBRES: Dict[str, Timbre] = {
    # Cuatro portadoras en paralelo y nada que las deforme: una suma de senos.
    # Es lo mas parecido a un organo de iglesia que da un chip de FM, y el
    # sonido mas seguro de todos -siempre tiene fundamental, siempre se oye-.
    "organo": Timbre("organo", algoritmo=7, realimentacion=0, operadores=[
        Operador(mul=1, tl=0,  ar=31, dr=0, sl=0,  rr=9),
        Operador(mul=2, tl=14, ar=31, dr=0, sl=0,  rr=9),
        Operador(mul=4, tl=24, ar=31, dr=0, sl=0,  rr=9),
        Operador(mul=8, tl=34, ar=31, dr=0, sl=0,  rr=9),
    ]),
    # Dos parejas: cada modulador deforma a su portadora. Ataque de golpe y
    # caida corta: empuja y se quita de en medio, que es lo que se le pide a un
    # bajo.
    "bajo": Timbre("bajo", algoritmo=4, realimentacion=5, operadores=[
        Operador(mul=1, tl=32, ar=31, dr=14, sl=4, rr=8, ks=1),
        Operador(mul=1, tl=2,  ar=31, dr=12, sl=3, rr=8),
        Operador(mul=2, tl=40, ar=31, dr=16, sl=6, rr=8, ks=1),
        Operador(mul=1, tl=10, ar=31, dr=10, sl=2, rr=8),
    ]),
    # Realimentacion alta en el primer operador: el seno se va rompiendo hasta
    # parecer un diente de sierra. Es el timbre que mas se acerca a la onda
    # cuadrada de siempre, para quien quiera el sonido de antes con el chip
    # nuevo.
    "cuadrada": Timbre("cuadrada", algoritmo=7, realimentacion=7, operadores=[
        Operador(mul=1, tl=0,  ar=31, dr=0, sl=0, rr=10),
        Operador(mul=1, tl=127),
        Operador(mul=1, tl=127),
        Operador(mul=1, tl=127),
    ]),
    # Un solo seno limpio, sin nada que lo deforme. Suena a flauta y deja sitio
    # a lo demas: va bien de acompanamiento debajo de algo con brillo.
    "flauta": Timbre("flauta", algoritmo=7, realimentacion=0, operadores=[
        Operador(mul=1, tl=2, ar=26, dr=4, sl=2, rr=10),
        Operador(mul=1, tl=127),
        Operador(mul=1, tl=127),
        Operador(mul=1, tl=127),
    ]),
    # Cadena de dos con realimentacion: el modulador abre el sonido segun
    # arranca y de ahi sale el «paaa» de los metales.
    "metal": Timbre("metal", algoritmo=2, realimentacion=6, operadores=[
        Operador(mul=1, tl=28, ar=24, dr=10, sl=6, rr=9),
        Operador(mul=1, tl=26, ar=26, dr=8,  sl=5, rr=9),
        Operador(mul=1, tl=22, ar=22, dr=9,  sl=6, rr=9),
        Operador(mul=1, tl=4,  ar=28, dr=6,  sl=3, rr=9),
    ]),
    # Multiplicadores que no casan entre si (1, 3, 7, 14): en vez de armonicos
    # salen parciales sueltos, y eso es exactamente lo que distingue una
    # campana de una nota.
    "campana": Timbre("campana", algoritmo=7, realimentacion=0, operadores=[
        Operador(mul=1,  tl=4,  ar=31, dr=7,  sl=2, rr=4),
        Operador(mul=3,  tl=18, ar=31, dr=9,  sl=3, rr=4),
        Operador(mul=7,  tl=26, ar=31, dr=12, sl=4, rr=5),
        Operador(mul=14, tl=34, ar=31, dr=15, sl=5, rr=6),
    ]),
    # Ataque lento: la nota entra empujando en vez de aparecer. Para fondos.
    "cuerda": Timbre("cuerda", algoritmo=4, realimentacion=2, operadores=[
        Operador(mul=1, tl=34, ar=17, dr=6, sl=2, rr=7),
        Operador(mul=1, tl=6,  ar=18, dr=5, sl=1, rr=7),
        Operador(mul=2, tl=38, ar=16, dr=7, sl=2, rr=7),
        Operador(mul=1, tl=12, ar=19, dr=6, sl=2, rr=7),
    ]),
    # Ataque de golpe y caida rapida, sin sostenido: suena a cuerda pellizcada
    # y marca el compas sin tapar a nadie.
    "pizzicato": Timbre("pizzicato", algoritmo=4, realimentacion=4, operadores=[
        Operador(mul=3, tl=30, ar=31, dr=22, sl=8, rr=12),
        Operador(mul=1, tl=4,  ar=31, dr=18, sl=6, rr=12),
        Operador(mul=1, tl=36, ar=31, dr=24, sl=9, rr=12),
        Operador(mul=1, tl=12, ar=31, dr=20, sl=7, rr=12),
    ]),
}

POR_DEFECTO = "cuadrada"      # el que sale si pides FM y no dices cual


# --- de la nota al chip ----------------------------------------------------

# Los dos de la familia OPN cuentan la nota igual: un numero de 11 bits (el
# `fnum`) y un `bloque` que es la octava. La formula es la de la hoja de datos:
#
#     Hz = fnum * reloj / (144 * 2^(21 - bloque))
#
# El reloj no es el mismo en las dos maquinas, asi que va como parametro.
RELOJ_YM2612 = 7670453        # Mega Drive NTSC: reloj maestro / 7
RELOJ_YM2610 = 8000000        # Neo Geo
RELOJ_YM2151 = 4000000        # X68000 (OPM)


def fnum_bloque(hz: float, reloj: int = RELOJ_YM2612) -> Tuple[int, int]:
    """La nota, en (bloque, fnum) para un chip de la familia OPN.

    El bloque se elige para que el `fnum` caiga en la mitad alta de su rango,
    que es donde tiene mas resolucion: con el fnum pequeno, dos notas seguidas
    se convierten en el mismo numero y la melodia sale desafinada.
    """
    if hz <= 0:
        return (0, 0)
    for bloque in range(8):
        fnum = int(round(hz * 144.0 * (1 << (21 - bloque)) / reloj))
        if fnum < 2048:
            # Si cabe de sobra, se sube de bloque para ganar precision.
            if fnum >= 1024 or bloque == 7:
                return (bloque, fnum)
            continue
        # No cabe: hay que subir de bloque si o si.
    return (7, 2047)


# En OPN, los cuatro operadores **no** estan seguidos en los registros: van en
# el orden 1, 3, 2, 4, separados de cuatro en cuatro. Es una de esas cosas que
# si no sabes te cuesta media tarde.
ORDEN_OPN = (0, 2, 1, 3)


def registros_opn(t: Timbre, canal: int) -> List[Tuple[int, int]]:
    """El timbre entero, en pares (registro, valor) listos para un OPN.

    `canal` es 0-2: en el YM2612 los canales 3-5 son los mismos registros con
    0x100 sumado, y de eso se encarga quien escribe.
    """
    pares: List[Tuple[int, int]] = []
    for i, ranura in enumerate(ORDEN_OPN):
        op = t.op(i)
        d = canal + ranura * 4
        pares.append((0x30 + d, ((op.dt & 7) << 4) | (op.mul & 15)))
        pares.append((0x40 + d, op.tl & 127))
        pares.append((0x50 + d, ((op.ks & 3) << 6) | (op.ar & 31)))
        pares.append((0x60 + d, ((op.am & 1) << 7) | (op.dr & 31)))
        pares.append((0x70 + d, op.sr & 31))
        pares.append((0x80 + d, ((op.sl & 15) << 4) | (op.rr & 15)))
    pares.append((0xB0 + canal,
                  ((t.realimentacion & 7) << 3) | (t.algoritmo & 7)))
    # Los dos altavoces encendidos. Sin esto el chip toca y **no se oye nada**:
    # es el fallo clasico de la primera vez que uno enciende un YM2612.
    pares.append((0xB4 + canal, 0xC0))
    return pares


# --- OPM: el mismo timbre, otros registros ---------------------------------
#
# El YM2151 del X68000 guarda lo mismo en otro sitio y cuenta las notas de otra
# manera: en vez de un numero de 11 bits, un codigo de nota (octava + cual de
# las doce) y una fraccion. Y tiene una rareza: de los 16 valores del campo de
# nota solo valen 12, porque se salta uno de cada cuatro.
NOTA_OPM = (0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14)

# En OPM las ranuras van de ocho en ocho y en el orden 1, 3, 2, 4, igual que en
# OPN pero con otro paso.
ORDEN_OPM = (0, 2, 1, 3)


def codigo_opm(hz: float) -> Tuple[int, int]:
    """La nota, en (KC, KF) para el YM2151.

    KC lleva la octava y la nota; KF, la fraccion entre una nota y la
    siguiente, en 64 pasos. Asi una melodia sale afinada aunque las notas no
    caigan justo en el temperamento igual.
    """
    if hz <= 0:
        return (0, 0)
    import math
    # Semitonos desde do-1 (16,3516 Hz es el do de la octava 0 de OPM), contados
    # **en sesentaicuatroavos**: si se redondea el semitono por un lado y la
    # fraccion por otro, un la de 440 sale como un sol sostenido y 63/64, que es
    # la misma nota pero contada de la peor manera posible.
    pasos = int(round(12.0 * 64.0 * math.log(hz / 16.3516, 2.0)))
    if pasos < 0:
        pasos = 0
    octava, resto = divmod(pasos // 64, 12)
    frac = pasos % 64
    if octava > 7:
        octava, resto, frac = 7, 11, 63
    kc = ((octava & 7) << 4) | NOTA_OPM[resto]
    kf = (frac & 63) << 2
    return (kc, kf)


def registros_opm(t: Timbre, canal: int) -> List[Tuple[int, int]]:
    """El timbre entero, en pares (registro, valor) listos para un YM2151."""
    pares: List[Tuple[int, int]] = []
    # RL (los dos altavoces), realimentacion y algoritmo, todo en un registro.
    pares.append((0x20 + canal,
                  0xC0 | ((t.realimentacion & 7) << 3) | (t.algoritmo & 7)))
    for i, ranura in enumerate(ORDEN_OPM):
        op = t.op(i)
        d = canal + ranura * 8
        # OPM llama DT1 a lo mismo que OPN llama DT, y ademas tiene un DT2 que
        # desafina mucho mas; aqui no se usa (queda a cero).
        pares.append((0x40 + d, ((op.dt & 7) << 4) | (op.mul & 15)))
        pares.append((0x60 + d, op.tl & 127))
        pares.append((0x80 + d, ((op.ks & 3) << 6) | (op.ar & 31)))
        pares.append((0xA0 + d, ((op.am & 1) << 7) | (op.dr & 31)))
        pares.append((0xC0 + d, op.sr & 31))
        pares.append((0xE0 + d, ((op.sl & 15) << 4) | (op.rr & 15)))
    return pares


# --- los operadores que suenan --------------------------------------------

# Cuales de los cuatro son portadoras en cada algoritmo. Hace falta para dos
# cosas: para el volumen (subir o bajar una nota es tocar el `tl` de las
# portadoras y **solo** de las portadoras, porque en un modulador el `tl` es el
# brillo) y para saber si un timbre va a sonar a algo.
PORTADORAS = (
    (0b1000,),   # 0: 1 -> 2 -> 3 -> 4
    (0b1000,),   # 1: (1 + 2) -> 3 -> 4
    (0b1000,),   # 2: (1 + (2 -> 3)) -> 4
    (0b1000,),   # 3: ((1 -> 2) + 3) -> 4
    (0b1010,),   # 4: (1 -> 2) + (3 -> 4)
    (0b1110,),   # 5: 1 -> (2 + 3 + 4)
    (0b1110,),   # 6: (1 -> 2) + 3 + 4
    (0b1111,),   # 7: 1 + 2 + 3 + 4
)


def portadoras(algoritmo: int) -> List[int]:
    """Los operadores (0-3) que se oyen con ese algoritmo."""
    mascara = PORTADORAS[algoritmo & 7][0]
    return [i for i in range(4) if mascara & (1 << i)]


def por_nombre(nombre: str) -> Timbre:
    return TIMBRES[nombre]


def nombres() -> List[str]:
    return list(TIMBRES)
