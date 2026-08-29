"""Monta un disquete de Human68k (X68000) con el juego dentro.

Un disquete del X68000 es un **FAT12 con sectores de 1024 bytes**, no de 512:
por lo demas es el mismo sistema de archivos de toda la vida. Lo que lo hace
suyo es el sector de arranque, que lleva la firma `X68IPL30` en el nombre del
fabricante y, detras del BPB, el codigo que carga Human68k.

La geometria es la del 2HD japones de 5,25 pulgadas:

    77 pistas x 2 caras x 8 sectores x 1024 bytes = 1.261.568 bytes

y de ahi salen los 1232 sectores que declara el BPB.

    sector 0        arranque (BPB + codigo)
    sectores 1-2    primera FAT
    sectores 3-4    segunda FAT
    sectores 5-10   directorio raiz (192 entradas de 32 bytes)
    sector 11+      los datos, un sector por agrupacion

Es el mismo trabajo que hacen adf.py para el Amiga y st_disk.py para el Atari
ST, con otro sistema de archivos.

    python3 hacer_disco.py JUEGO.X juego.xdf
"""

from __future__ import annotations

import struct
import sys
from typing import Dict, List, Sequence, Tuple

SECTOR = 1024
PISTAS = 77
CARAS = 2
POR_PISTA = 8
SECTORES = PISTAS * CARAS * POR_PISTA          # 1232
TAMANO = SECTORES * SECTOR                     # 1.261.568 bytes

FIRMA = b"X68IPL30"
RESERVADOS = 1
FATS = 2
SECTORES_FAT = 2
ENTRADAS_RAIZ = 192
MEDIO = 0xFE

PRIMERA_FAT = RESERVADOS
RAIZ = RESERVADOS + FATS * SECTORES_FAT        # sector 5
SECTORES_RAIZ = ENTRADAS_RAIZ * 32 // SECTOR   # 6
DATOS = RAIZ + SECTORES_RAIZ                   # sector 11
AGRUPACIONES = SECTORES - DATOS


class ErrorDisco(Exception):
    pass


def _nombre_83(nombre: str) -> Tuple[bytes, bytes]:
    """'JUEGO.X' -> (b'JUEGO   ', b'X  '), que es como lo guarda FAT."""
    nombre = nombre.upper()
    if "." in nombre:
        base, extension = nombre.rsplit(".", 1)
    else:
        base, extension = nombre, ""
    if not base or len(base) > 8 or len(extension) > 3:
        raise ErrorDisco("'%s' no cabe en un nombre 8.3 de Human68k" % nombre)
    for c in base + extension:
        if not (c.isalnum() or c in "_-"):
            raise ErrorDisco("'%s' lleva un caracter que Human68k no acepta: %r"
                             % (nombre, c))
    return base.ljust(8).encode("ascii"), extension.ljust(3).encode("ascii")


def _fat12(cadenas: Sequence[Sequence[int]]) -> bytes:
    """La tabla de agrupaciones, en FAT12: doce bits por entrada."""
    total = SECTORES_FAT * SECTOR * 2 // 3      # entradas que caben
    entradas = [0] * total
    entradas[0] = 0xF00 | MEDIO
    entradas[1] = 0xFFF
    for cadena in cadenas:
        for i, agrupacion in enumerate(cadena):
            entradas[agrupacion] = (cadena[i + 1] if i + 1 < len(cadena)
                                    else 0xFFF)
    datos = bytearray(SECTORES_FAT * SECTOR)
    for i in range(0, len(entradas) - 1, 2):
        a, b = entradas[i] & 0xFFF, entradas[i + 1] & 0xFFF
        base = i * 3 // 2
        if base + 2 >= len(datos):
            break
        datos[base] = a & 0xFF
        datos[base + 1] = ((a >> 8) & 0x0F) | ((b & 0x0F) << 4)
        datos[base + 2] = (b >> 4) & 0xFF
    return bytes(datos)


def _entrada(nombre: str, primera: int, largo: int) -> bytes:
    base, extension = _nombre_83(nombre)
    return (base + extension
            + bytes([0x20])                     # atributo: archivo normal
            + b"\0" * 10
            + struct.pack("<HH", 0x6000, 0x5A21)   # hora y fecha, fijas
            + struct.pack("<H", primera)
            + struct.pack("<I", largo))


def sector_de_arranque(etiqueta: str = "NEOPLAT") -> bytes:
    """El sector 0: el salto, la firma, el BPB y sitio para el codigo.

    El codigo de arranque se deja a cero: este disquete se lee desde Human68k,
    no arranca solo. Para que arrancara solo haria falta el cargador que busca
    y monta HUMAN.SYS, que es lo que trae el disco de sistema de Sharp.
    """
    d = bytearray(SECTOR)
    d[0:3] = b"\x60\x3c\x90"                    # bra +0x3c, y un relleno
    d[3:11] = FIRMA
    struct.pack_into("<H", d, 11, SECTOR)
    d[13] = 1                                   # un sector por agrupacion
    struct.pack_into("<H", d, 14, RESERVADOS)
    d[16] = FATS
    struct.pack_into("<H", d, 17, ENTRADAS_RAIZ)
    struct.pack_into("<H", d, 19, SECTORES)
    d[21] = MEDIO
    struct.pack_into("<H", d, 22, SECTORES_FAT)
    struct.pack_into("<H", d, 24, POR_PISTA)
    struct.pack_into("<H", d, 26, CARAS)
    d[43:54] = etiqueta.upper()[:11].ljust(11).encode("ascii")
    d[54:62] = b"FAT12   "
    return bytes(d)


def crear_disquete(archivos: Dict[str, bytes], etiqueta: str = "NEOPLAT") -> bytes:
    """Un disquete de 1232 sectores con esos archivos en la raiz."""
    if len(archivos) > ENTRADAS_RAIZ:
        raise ErrorDisco("caben %d archivos en la raiz y hay %d"
                         % (ENTRADAS_RAIZ, len(archivos)))
    disco = bytearray(TAMANO)
    disco[0:SECTOR] = sector_de_arranque(etiqueta)

    entradas = bytearray()
    cadenas: List[List[int]] = []
    siguiente = 2                               # las dos primeras estan pilladas
    for nombre, datos in archivos.items():
        cuantas = max(1, (len(datos) + SECTOR - 1) // SECTOR)
        if siguiente + cuantas - 2 > AGRUPACIONES:
            raise ErrorDisco(
                "no cabe: el disquete tiene %d KB y '%s' se pasa"
                % (AGRUPACIONES * SECTOR // 1024, nombre))
        cadena = list(range(siguiente, siguiente + cuantas))
        cadenas.append(cadena)
        for i, agrupacion in enumerate(cadena):
            inicio = (DATOS + agrupacion - 2) * SECTOR
            trozo = datos[i * SECTOR:(i + 1) * SECTOR]
            disco[inicio:inicio + len(trozo)] = trozo
        entradas += _entrada(nombre, cadena[0], len(datos))
        siguiente += cuantas

    fat = _fat12(cadenas)
    for i in range(FATS):
        inicio = (PRIMERA_FAT + i * SECTORES_FAT) * SECTOR
        disco[inicio:inicio + len(fat)] = fat
    inicio = RAIZ * SECTOR
    disco[inicio:inicio + len(entradas)] = entradas
    return bytes(disco)


def leer_directorio(disco: bytes) -> List[Tuple[str, int, int]]:
    """Lo que hay en la raiz: (nombre, primera agrupacion, tamano).

    Existe para que las pruebas puedan releer lo que se ha escrito, que es la
    unica forma de saber que el disquete esta bien montado sin un X68000.
    """
    salida = []
    base = RAIZ * SECTOR
    for i in range(ENTRADAS_RAIZ):
        e = disco[base + i * 32:base + (i + 1) * 32]
        if not e or e[0] in (0x00, 0xE5):
            continue
        nombre = e[0:8].decode("ascii").rstrip()
        extension = e[8:11].decode("ascii").rstrip()
        primera, largo = struct.unpack("<H", e[26:28])[0], struct.unpack("<I", e[28:32])[0]
        salida.append((nombre + ("." + extension if extension else ""),
                       primera, largo))
    return salida


def leer_archivo(disco: bytes, nombre: str) -> bytes:
    """Saca un archivo siguiendo la FAT, como haria Human68k."""
    for encontrado, primera, largo in leer_directorio(disco):
        if encontrado.upper() != nombre.upper():
            continue
        fat = disco[PRIMERA_FAT * SECTOR:(PRIMERA_FAT + SECTORES_FAT) * SECTOR]
        datos = bytearray()
        agrupacion = primera
        while 2 <= agrupacion < 0xFF8 and len(datos) < largo:
            inicio = (DATOS + agrupacion - 2) * SECTOR
            datos += disco[inicio:inicio + SECTOR]
            base = agrupacion * 3 // 2
            par = fat[base] | (fat[base + 1] << 8)
            agrupacion = (par >> 4) if agrupacion & 1 else (par & 0xFFF)
        return bytes(datos[:largo])
    raise ErrorDisco("'%s' no esta en el disquete" % nombre)


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 1
    ejecutable, destino = argv[1], argv[2]
    import os
    with open(ejecutable, "rb") as fh:
        datos = fh.read()
    nombre = os.path.basename(ejecutable).upper()
    try:
        disco = crear_disquete({nombre: datos})
    except ErrorDisco as error:
        sys.stderr.write("error: %s\n" % error)
        return 1
    with open(destino, "wb") as fh:
        fh.write(disco)
    print("disquete de X68000: %s (%d KB, con %s dentro)"
          % (destino, TAMANO // 1024, nombre))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
