"""Coma fija compartida por el motor C, el preview JS y las herramientas.

Todo el motor trabaja con enteros de 32 bits en formato 24.8: una unidad
equivale a 1/256 de pixel. Convertir aqui (y solo aqui) garantiza que la
simulacion del navegador y la de la Neo Geo usen exactamente las mismas
constantes.
"""

from __future__ import annotations

FIXED_SHIFT = 8
FIXED_ONE = 1 << FIXED_SHIFT


def to_fixed(value: float) -> int:
    """Convierte pixeles/frame (o pixeles) a coma fija 24.8, redondeando."""
    return int(round(float(value) * FIXED_ONE))


def from_fixed(value: int) -> float:
    return value / FIXED_ONE
