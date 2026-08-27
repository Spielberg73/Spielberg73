"""ADPCM-A: el sonido comprimido del YM2610 (Neo Geo).

Los seis canales de muestras del YM2610 no leen bytes crudos: leen **medio
byte por muestra**, en el ADPCM de la familia OKI, desde una ROM aparte (la V1)
y a 18.500 muestras por segundo fijos. Cuatro bits por muestra son 4:1 de
compresion, que es lo que permitia meter voces en un cartucho de 1990.

El formato es un predictor mas un paso variable:

    delta   = nibble & 7                 los tres bits de magnitud
    salto   = ((2 * delta + 1) * paso) / 8
    valor   = valor -+ salto             el bit 3 es el signo
    indice += [-1,-1,-1,-1, 2, 5, 7, 9][delta]

`indice` recorre una tabla de 49 pasos que va de 16 a 1552: cuando la onda sube
deprisa el paso crece y el codec la sigue; cuando se calma, encoge. El valor se
guarda en 12 bits con signo (-2048..2047).

Aqui estan las dos mitades:

  - `cifrar` convierte una muestra de 8 bits con signo (lo que da el lector de
    WAV) en los nibbles que van a la ROM V1;
  - `descifrar` hace lo contrario, y lo usa el banco de pruebas del kit para
    **oir** lo que saldria del chip (tests/maquina_neogeo.py).

Cifrar es una busqueda: para cada muestra se prueban los dieciseis nibbles y se
elige el que deja el predictor mas cerca del valor que toca. Son dieciseis
restas por muestra, se hace una vez al compilar y sale mejor que cualquier
formula aproximada.
"""

from __future__ import annotations

from typing import Iterable, List

# Los 49 pasos, de 16 a 1552. Cada uno es un 10% mas o menos que el anterior.
PASOS = [
    16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
    50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
    157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449,
    494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411,
    1552,
]
INCREMENTO = [-1, -1, -1, -1, 2, 5, 7, 9]

MINIMO = -2048          # el acumulador son 12 bits con signo
MAXIMO = 2047
RITMO = 18500           # muestras por segundo, fijas en el chip
BLOQUE = 256            # el chip direcciona la ROM V1 de 256 en 256 bytes


def _paso(nibble: int, indice: int, valor: int):
    """Un paso del descifrado: devuelve (valor nuevo, indice nuevo)."""
    delta = nibble & 7
    salto = ((2 * delta + 1) * PASOS[indice]) >> 3
    valor = valor - salto if nibble & 8 else valor + salto
    if valor < MINIMO:
        valor = MINIMO
    elif valor > MAXIMO:
        valor = MAXIMO
    indice += INCREMENTO[delta]
    if indice < 0:
        indice = 0
    elif indice > 48:
        indice = 48
    return valor, indice


def descifrar(datos: bytes, cuantas: int = 0) -> List[int]:
    """Bytes de la ROM V1 -> muestras de 12 bits con signo (-2048..2047).

    El nibble alto va primero, que es como los lee el chip."""
    salida: List[int] = []
    valor, indice = 0, 0
    tope = cuantas or len(datos) * 2
    for byte in datos:
        for nibble in (byte >> 4, byte & 0x0F):
            valor, indice = _paso(nibble, indice, valor)
            salida.append(valor)
            if len(salida) >= tope:
                return salida
    return salida


def cifrar(muestras: Iterable[int]) -> bytes:
    """Muestras de 8 bits con signo -> bytes de ADPCM-A.

    Se escala por 16 porque el acumulador del chip son 12 bits y la muestra
    ocho: asi se aprovecha todo el margen. Si sobra un nibble al final, se
    rellena con silencio."""
    valor, indice = 0, 0
    nibbles: List[int] = []
    for muestra in muestras:
        objetivo = max(MINIMO, min(MAXIMO, int(muestra) * 16))
        mejor = 0
        mejor_error = None
        mejor_estado = (valor, indice)
        for nibble in range(16):
            nuevo, siguiente = _paso(nibble, indice, valor)
            error = abs(objetivo - nuevo)
            if mejor_error is None or error < mejor_error:
                mejor, mejor_error = nibble, error
                mejor_estado = (nuevo, siguiente)
        nibbles.append(mejor)
        valor, indice = mejor_estado
    if len(nibbles) % 2:
        nibbles.append(0)
    return bytes((nibbles[i] << 4) | nibbles[i + 1]
                 for i in range(0, len(nibbles), 2))


def cifrar_muestra(datos: bytes) -> bytes:
    """Lo mismo, partiendo de los bytes con signo del lector de WAV, y
    redondeando a un bloque entero de los que direcciona el chip."""
    valores = [b - 256 if b > 127 else b for b in datos]
    faltan = (-len(valores)) % (BLOQUE * 2)
    valores.extend([0] * faltan)          # el silencio se cifra tambien
    return cifrar(valores)
