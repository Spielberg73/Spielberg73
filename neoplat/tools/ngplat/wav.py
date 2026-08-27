"""Lector de WAV en Python puro, para las muestras digitales.

Del formato solo hace falta lo que produce cualquier programa de sonido al
guardar "WAV PCM": la cabecera RIFF, el trozo `fmt ` y el trozo `data`. Se
admite 8 bits sin signo o 16 bits con signo, mono o estereo, a cualquier
frecuencia; todo sale de aqui convertido a **mono de 8 bits con signo**, que es
lo que entienden las cuatro maquinas que saben tocar muestras.

    muestra = leer("sonidos/moneda.wav")
    muestra.datos          bytes, uno por muestra, con signo (-128..127)
    muestra.ritmo          muestras por segundo del archivo
    remuestrear(m, 8000)   la misma muestra a otra frecuencia

Por que 8 bits: es lo que dan Paula, el DAC del YM2612 y los DAC de la Jaguar,
y la ADPCM-A de la Neo Geo comprime desde ahi. Guardar mas seria tirar memoria
de cartucho para nada.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import List


class WavError(Exception):
    """El archivo no es un WAV que se pueda usar."""


@dataclass
class Muestra:
    """Sonido digital ya en mono de 8 bits con signo."""
    datos: bytes                  # cada byte es una muestra, complemento a dos
    ritmo: int                    # muestras por segundo

    def __len__(self) -> int:
        return len(self.datos)

    @property
    def segundos(self) -> float:
        return len(self.datos) / float(self.ritmo or 1)

    def con_signo(self) -> List[int]:
        return [b - 256 if b > 127 else b for b in self.datos]


def _trozos(datos: bytes):
    """Recorre los trozos del RIFF: (etiqueta, contenido)."""
    if len(datos) < 12 or datos[:4] != b"RIFF" or datos[8:12] != b"WAVE":
        raise WavError("esto no es un WAV (falta la cabecera RIFF/WAVE)")
    i = 12
    while i + 8 <= len(datos):
        etiqueta = datos[i:i + 4]
        (largo,) = struct.unpack_from("<I", datos, i + 4)
        cuerpo = datos[i + 8:i + 8 + largo]
        yield etiqueta, cuerpo
        i += 8 + largo + (largo & 1)          # los trozos van a par de bytes


def descifrar(datos: bytes) -> Muestra:
    """Bytes de un archivo WAV -> Muestra en mono de 8 bits con signo."""
    formato = canales = bits = 0
    ritmo = 0
    crudo = b""
    for etiqueta, cuerpo in _trozos(datos):
        if etiqueta == b"fmt ":
            if len(cuerpo) < 16:
                raise WavError("el trozo 'fmt ' esta cortado")
            formato, canales, ritmo, _bps, _align, bits = struct.unpack_from(
                "<HHIIHH", cuerpo, 0)
        elif etiqueta == b"data":
            crudo = cuerpo
    if not ritmo:
        raise WavError("el WAV no trae el trozo 'fmt ' con la frecuencia")
    if formato not in (1, 0xFFFE):
        raise WavError(
            "el WAV esta comprimido (formato %d) y aqui solo vale PCM sin "
            "comprimir; vuelvelo a guardar como 'WAV PCM'" % formato)
    if bits not in (8, 16):
        raise WavError("el WAV es de %d bits y solo valen 8 o 16" % bits)
    if canales not in (1, 2):
        raise WavError("el WAV tiene %d canales y solo valen mono o estereo"
                       % canales)
    if not crudo:
        raise WavError("el WAV no tiene sonido (el trozo 'data' esta vacio)")

    salida = bytearray()
    if bits == 8:
        # 8 bits en WAV van **sin signo** (128 es el silencio)
        paso = canales
        for i in range(0, len(crudo) - paso + 1, paso):
            if canales == 1:
                valor = crudo[i] - 128
            else:
                valor = (crudo[i] + crudo[i + 1]) // 2 - 128
            salida.append(valor & 0xFF)
    else:
        paso = 2 * canales
        for i in range(0, len(crudo) - paso + 1, paso):
            if canales == 1:
                (valor,) = struct.unpack_from("<h", crudo, i)
            else:
                izq, der = struct.unpack_from("<hh", crudo, i)
                valor = (izq + der) // 2
            salida.append((valor >> 8) & 0xFF)
    return Muestra(bytes(salida), ritmo)


def leer(ruta: str) -> Muestra:
    with open(ruta, "rb") as fh:
        return descifrar(fh.read())


def remuestrear(muestra: Muestra, ritmo: int) -> Muestra:
    """La misma muestra a otra frecuencia, por interpolacion lineal.

    Lineal y no "coger la mas cercana" porque bajando de 44 kHz a 8 kHz la
    diferencia se oye: el vecino mas cercano mete un siseo que la interpolacion
    no tiene. Sigue sin haber filtro antialias, que para efectos cortos de un
    juego de 8 bits no hace falta.
    """
    if ritmo <= 0:
        raise WavError("la frecuencia de destino tiene que ser positiva")
    if ritmo == muestra.ritmo or len(muestra.datos) < 2:
        return Muestra(muestra.datos, ritmo)
    origen = muestra.con_signo()
    cuantas = max(1, int(round(len(origen) * ritmo / float(muestra.ritmo))))
    salto = (len(origen) - 1) / float(max(1, cuantas - 1)) if cuantas > 1 else 0.0
    salida = bytearray()
    for i in range(cuantas):
        donde = i * salto
        j = int(donde)
        if j >= len(origen) - 1:
            valor = origen[-1]
        else:
            resto = donde - j
            valor = int(round(origen[j] + (origen[j + 1] - origen[j]) * resto))
        salida.append(max(-128, min(127, valor)) & 0xFF)
    return Muestra(bytes(salida), ritmo)


def recortar(muestra: Muestra, maximo: int) -> Muestra:
    """Deja la muestra en `maximo` bytes como mucho, con un desvanecido corto
    al final para que no acabe en un chasquido."""
    if len(muestra.datos) <= maximo:
        return muestra
    valores = muestra.con_signo()[:maximo]
    cola = min(64, len(valores))
    for i in range(cola):
        peso = (cola - i) / float(cola + 1)
        valores[len(valores) - cola + i] = int(
            round(valores[len(valores) - cola + i] * peso))
    return Muestra(bytes(v & 0xFF for v in valores), muestra.ritmo)


def codificar(muestra: Muestra) -> bytes:
    """Muestra -> bytes de un archivo WAV mono de 8 bits (sin signo, que es
    como los guarda el formato)."""
    datos = bytes((v + 128) & 0xFF for v in muestra.con_signo())
    cabecera = (b"RIFF" + struct.pack("<I", 36 + len(datos)) + b"WAVEfmt "
                + struct.pack("<IHHIIHH", 16, 1, 1, muestra.ritmo,
                              muestra.ritmo, 1, 8)
                + b"data" + struct.pack("<I", len(datos)))
    return cabecera + datos


def escribir(ruta: str, muestra: Muestra) -> str:
    with open(ruta, "wb") as fh:
        fh.write(codificar(muestra))
    return ruta
