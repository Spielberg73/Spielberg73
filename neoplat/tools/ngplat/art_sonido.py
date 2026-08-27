"""Muestras digitales de ejemplo, generadas por codigo.

Igual que los graficos del andamiaje (art.py), el proyecto que crea
`ngplat nuevo` trae sus propios sonidos grabados para que se pueda oir de que
va esto sin buscar un WAV por ahi. Son deliberadamente cortos y sencillos:
estan para sustituirlos por los tuyos.

Se guardan en 11025 Hz, mono y 8 bits, que es lo que tocan las maquinas.
"""

from __future__ import annotations

import math
from typing import Dict, List

from .wav import Muestra

RITMO = 11025


def _a_muestra(valores: List[float]) -> Muestra:
    datos = bytes(max(-128, min(127, int(round(v * 127)))) & 0xFF for v in valores)
    return Muestra(datos, RITMO)


def _ruido(semilla: int):
    """Un generador de ruido repetible: el mismo proyecto tiene que salir
    siempre igual, byte a byte, o las pruebas no podrian compararlo."""
    estado = semilla & 0xFFFFFFFF

    def siguiente() -> float:
        nonlocal estado
        estado = (estado * 1103515245 + 12345) & 0x7FFFFFFF
        return (estado >> 15 & 0xFFFF) / 32768.0 - 1.0

    return siguiente


def moneda() -> Muestra:
    """El 'ding' de recoger algo: dos notas cortas que suben."""
    valores: List[float] = []
    for hz, segundos in ((1046.5, 0.05), (1568.0, 0.13)):
        cuantas = int(RITMO * segundos)
        for i in range(cuantas):
            t = i / float(RITMO)
            caida = math.exp(-t * 14.0)
            # la fundamental mas un armonico suave: suena a campanita y no a pito
            onda = math.sin(2 * math.pi * hz * t) * 0.75 + \
                math.sin(4 * math.pi * hz * t) * 0.25
            valores.append(onda * caida * 0.85)
    return _a_muestra(valores)


def golpe() -> Muestra:
    """El 'thud' de pisar a un enemigo: ruido grave que se apaga rapido."""
    ruido = _ruido(20250827)
    cuantas = int(RITMO * 0.16)
    valores: List[float] = []
    filtro = 0.0
    for i in range(cuantas):
        t = i / float(RITMO)
        # el filtro paso bajo es lo que lo hace un golpe y no un siseo
        filtro += (ruido() - filtro) * 0.18
        valores.append(filtro * math.exp(-t * 26.0) * 2.2)
    return _a_muestra(valores)


def todos() -> Dict[str, Muestra]:
    """Ruta relativa dentro del proyecto -> muestra."""
    return {
        "sonidos/moneda.wav": moneda(),
        "sonidos/golpe.wav": golpe(),
    }
