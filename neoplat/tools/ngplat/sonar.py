"""Convierte una cancion del game.yaml en un WAV que se pueda oir fuera.

El editor ya deja escuchar la musica, pero hace falta un navegador abierto. Esto
es para lo otro: mandarle la cancion a alguien, oirla en el movil, meterla en un
video, o simplemente comprobar sin abrir nada que lo que se acaba de escribir
suena a lo que uno queria.

**No es un sintetizador nuevo.** Las notas las compila `sonido.py` -el mismo
que llena las ROMs- y la forma de onda sale de `fm.onda()`, que es la que el
kit ya usa para el Amiga, el A1200 y el CD32: ahi la musica se toca con una
tabla de onda y lo que suena es literalmente esto. En la Neo Geo o la Mega
Drive el chip es otro y el timbre no sale identico, pero las notas, los
tiempos y el volumen si: son los mismos numeros.

Sale en **16 bits mono** a 44.100, y eso es a proposito aunque Paula sea de 8:
lo que es de 8 bits en aquellas maquinas son **las muestras de la tabla de
onda**, no la salida. Sacar el WAV a 8 bits mete un ruido de cuantizacion que
el Amiga no tenia, asi que sonaria peor que la maquina, no igual. Con `--bits
8` se saca de 8 para ver como queda la tabla en crudo.

Y se lee la onda **interpolando y con sobremuestreo**, que es la otra mitad de
que esto suene bien o a lata: leer una tabla de 512 puntos a saltos, por el
punto mas cercano, es muestrear una curva con armonicos por encima de Nyquist,
y esos armonicos **se pliegan** hacia abajo y salen como un zumbido metalico
que no es de ninguna nota. Interpolar entre puntos y promediar cuatro muestras
por cada una que sale quita casi todo.
"""

from __future__ import annotations

import struct
from typing import List, Optional, Sequence

from . import fm, wav
from .errors import ProjectError

RITMO = 44100            # muestras por segundo del WAV que sale
FPS = 60                 # un paso de musica dura `velocidad` frames
ATAQUE = 0.004           # segundos que tarda la nota en arrancar
CAIDA = 0.008            # y lo que tarda en apagarse al acabar
SOSTENIDO = 0.82         # a cuanto cae una nota larga mientras dura
SOBRE = 4                # muestras que se calculan por cada una que sale


def _tabla(timbre: str) -> List[float]:
    """Un ciclo de la onda del timbre, entre -1 y 1.

    Sin timbre -o con uno que no existe- se usa una cuadrada, que es lo que
    tocan los chips de onda cuadrada (la Neo Geo, el Atari ST) y lo que pone
    el kit por defecto.
    """
    try:
        return fm.onda(fm.por_nombre(timbre), 512)
    except Exception:
        return [1.0] * 256 + [-1.0] * 256


def _una_pista(pasos: Sequence, timbre: str, ritmo: int) -> List[float]:
    """Una pista entera a muestras sueltas, entre -1 y 1.

    Tres cosas que no son adorno:

    * **se interpola** entre los dos puntos de la tabla en vez de coger el mas
      cercano. Sin esto, cada muestra cae donde cae y lo que se oye lleva un
      zumbido metalico encima que no es de ninguna nota;
    * **se calculan cuatro muestras por cada una** y se promedian. Es un filtro
      pasa-bajos de pobre, pero es el que hace falta: lo que suena por encima
      de la mitad del ritmo de muestreo no se puede representar, y si no se
      quita, se pliega hacia abajo y se queda dentro;
    * y cada nota tiene **envolvente**: arranca en cuatro milesimas, cae un
      poco mientras dura y se apaga en ocho. Una nota plana que empieza y acaba
      de golpe suena a sirena, no a instrumento.
    """
    tabla = _tabla(timbre)
    puntos = len(tabla)
    salida: List[float] = []
    ritmo_alto = ritmo * SOBRE
    for paso in pasos:
        hz = float(paso.frecuencia)
        cuantas = max(1, int(round(paso.duracion / float(FPS) * ritmo)))
        if hz <= 0:
            salida.extend([0.0] * cuantas)
            continue
        nivel = (paso.volumen / 15.0) ** 2
        avance = hz * puntos / float(ritmo_alto)
        ataque = max(1, int(ATAQUE * ritmo))
        caida = max(1, int(CAIDA * ritmo))
        fase = 0.0
        for i in range(cuantas):
            suma = 0.0
            for _ in range(SOBRE):
                entero = int(fase)
                resto = fase - entero
                a = tabla[entero % puntos]
                b = tabla[(entero + 1) % puntos]
                suma += a + (b - a) * resto
                fase += avance
            muestra = suma / SOBRE
            # envolvente
            if i < ataque:
                muestra *= i / float(ataque)
            elif i > cuantas - caida:
                muestra *= (cuantas - i) / float(caida)
            else:
                caido = (i - ataque) / float(max(1, cuantas - ataque))
                muestra *= 1.0 - (1.0 - SOSTENIDO) * caido
            salida.append(muestra * nivel)
    return salida


def render(musica, ritmo: int = RITMO, vueltas: int = 1, bits: int = 16):
    """La cancion entera, con sus pistas mezcladas, lista para escribir.

    Cada pista se repite **por su cuenta** hasta llenar lo que dura la mas
    larga, que es como la toca el motor: una melodia de 32 pasos sobre un bajo
    de 16 da dos vueltas de bajo por una de melodia, y es asi como se escriben
    estas cosas.

    Con `bits=8` sale una `wav.Muestra` como las del kit; con 16 -lo normal-
    sale una tupla (datos, ritmo) ya en el formato del archivo.
    """
    if not musica.pistas:
        raise ProjectError("la cancion '%s' no tiene ninguna pista"
                           % musica.nombre)
    timbres = list(musica.timbres or [])
    sueltas = [_una_pista(p, timbres[i] if i < len(timbres) else "", ritmo)
               for i, p in enumerate(musica.pistas) if p]
    if not sueltas or not any(sueltas):
        raise ProjectError("la cancion '%s' esta en silencio entera"
                           % musica.nombre)
    largo = max(len(s) for s in sueltas) * max(1, int(vueltas))

    mezcla = [0.0] * largo
    for pista in sueltas:
        if not pista:
            continue
        for i in range(largo):
            mezcla[i] += pista[i % len(pista)]

    # Se aprovecha el rango entero. Antes se dividia por el numero de pistas y
    # ya: con el volumen 11 que trae el kit por defecto, el pico se quedaba a
    # la mitad de la escala y en 8 bits eso es tirar un bit de los ocho.
    pico = max(abs(v) for v in mezcla) or 1.0
    factor = 0.92 / pico
    if bits == 8:
        datos = bytearray()
        for valor in mezcla:
            v = int(round(valor * factor * 127))
            datos.append(max(-128, min(127, v)) & 0xFF)
        return wav.Muestra(bytes(datos), ritmo)
    datos = bytearray()
    for valor in mezcla:
        v = int(round(valor * factor * 32767))
        v = max(-32768, min(32767, v))
        datos += struct.pack("<h", v)
    return _Wav16(bytes(datos), ritmo)


class _Wav16:
    """Un WAV de 16 bits. `wav.py` escribe de 8 porque es lo que comen estas
    maquinas; esto es solo para oir, asi que va con todo el rango."""

    def __init__(self, datos: bytes, ritmo: int):
        self.datos = datos
        self.ritmo = ritmo

    def __len__(self) -> int:
        return len(self.datos) // 2

    @property
    def segundos(self) -> float:
        return len(self) / float(self.ritmo or 1)

    def escribir(self, ruta: str) -> str:
        cabecera = (b"RIFF" + struct.pack("<I", 36 + len(self.datos))
                    + b"WAVEfmt "
                    + struct.pack("<IHHIIHH", 16, 1, 1, self.ritmo,
                                  self.ritmo * 2, 2, 16)
                    + b"data" + struct.pack("<I", len(self.datos)))
        with open(ruta, "wb") as fh:
            fh.write(cabecera + self.datos)
        return ruta


def escribir(musica, ruta: str, ritmo: int = RITMO, vueltas: int = 1,
             bits: int = 16) -> str:
    """La cancion, a un archivo WAV. Devuelve la ruta."""
    salida = render(musica, ritmo, vueltas, bits)
    if isinstance(salida, _Wav16):
        return salida.escribir(ruta)
    return wav.escribir(ruta, salida)


def buscar(sonido, nombre: str) -> Optional[object]:
    """La cancion que se pida, o la primera si no se pide ninguna."""
    canciones = list(sonido.musica.values()) if hasattr(sonido.musica, "values") \
        else list(sonido.musica)
    if not canciones:
        return None
    if not nombre:
        return canciones[0]
    for cancion in canciones:
        if cancion.nombre == nombre:
            return cancion
    return None


def duracion(musica) -> float:
    """Lo que dura una vuelta, en segundos. Para decirlo sin tocarla."""
    largos = [sum(paso.duracion for paso in pista) for pista in musica.pistas]
    return (max(largos) if largos else 0) / float(FPS)
