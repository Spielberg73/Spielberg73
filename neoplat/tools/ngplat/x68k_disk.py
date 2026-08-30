"""Monta un disquete de Human68k (X68000) con el juego dentro.

Un disquete del X68000 es un **FAT12 con sectores de 1024 bytes**, no de 512.
La FAT y el directorio son los de toda la vida, pero el sector de arranque
**no**: el nombre del fabricante ocupa 16 bytes en vez de 8 y el BPB va detras,
en 0x12, y en **big endian**, que es lo suyo en un 68000.

    +0x00  word      salto al codigo de arranque
    +0x02  16 bytes  nombre del fabricante
    +0x12  word      bytes por sector          (big endian)
    +0x14  byte      sectores por agrupacion
    +0x15  byte      cuantas FAT
    +0x16  word      sectores reservados
    +0x18  word      entradas del directorio raiz
    +0x1A  word      sectores del disco
    +0x1C  byte      descriptor de medio
    +0x1D  byte      sectores por FAT
    +0x1E  el codigo de arranque

Esto sale de mirar un disco de sistema de Sharp de verdad, no de la
documentacion. La primera version de este modulo copiaba el BPB de una
herramienta que lee estos disquetes, y estaba mal: esa herramienta **fabrica**
un sector de arranque de mentira, con el BPB en 0x0B y en little endian, para
poder pasarselo a una libreria de FAT de PC. Ninguna maquina lo escribe asi.

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

FABRICANTE = b"NEOPLAT 1.00    "     # 16 bytes, como el de Sharp
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


def sector_de_arranque() -> bytes:
    """El sector 0: el salto, el nombre del fabricante y el BPB.

    El codigo de arranque se deja a cero: este disquete se lee desde Human68k,
    no arranca solo. Para que arrancara solo haria falta el cargador que busca
    y monta HUMAN.SYS, que es lo que trae el disco de sistema de Sharp.
    """
    d = bytearray(SECTOR)
    struct.pack_into(">H", d, 0, 0x601C)        # bra al codigo, en 0x1E
    d[2:18] = FABRICANTE
    struct.pack_into(">H", d, 0x12, SECTOR)
    d[0x14] = 1                                 # un sector por agrupacion
    d[0x15] = FATS
    struct.pack_into(">H", d, 0x16, RESERVADOS)
    struct.pack_into(">H", d, 0x18, ENTRADAS_RAIZ)
    struct.pack_into(">H", d, 0x1A, SECTORES)
    d[0x1C] = MEDIO
    d[0x1D] = SECTORES_FAT
    return bytes(d)


def leer_bpb(disco: bytes) -> Dict[str, int]:
    """Los parametros del disquete, sacados de su propio sector de arranque.

    Leerlos en vez de darlos por supuestos hace que esto valga para **cualquier**
    disquete de Human68k, no solo para los que monta este modulo: es lo que
    permite comprobarlo contra un disco de sistema de Sharp de verdad.
    """
    return {
        "sector": struct.unpack(">H", disco[0x12:0x14])[0],
        "por_agrupacion": disco[0x14],
        "fats": disco[0x15],
        "reservados": struct.unpack(">H", disco[0x16:0x18])[0],
        "raiz": struct.unpack(">H", disco[0x18:0x1A])[0],
        "sectores": struct.unpack(">H", disco[0x1A:0x1C])[0],
        "medio": disco[0x1C],
        "sectores_fat": disco[0x1D],
    }


def crear_disquete(archivos: Dict[str, bytes], etiqueta: str = "NEOPLAT") -> bytes:
    """Un disquete de 1232 sectores con esos archivos en la raiz."""
    if len(archivos) > ENTRADAS_RAIZ:
        raise ErrorDisco("caben %d archivos en la raiz y hay %d"
                         % (ENTRADAS_RAIZ, len(archivos)))
    disco = bytearray(TAMANO)
    disco[0:SECTOR] = sector_de_arranque()
    if etiqueta:
        pass                                    # la etiqueta va en el directorio

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

    La raiz se busca con el BPB del propio disquete, no con los numeros de este
    modulo, asi que esto lee tambien un disco de sistema de Sharp. Las entradas
    si son las de FAT de siempre: la agrupacion y el tamano van en little
    endian aunque el BPB sea big endian.
    """
    bpb = leer_bpb(disco)
    sector = bpb["sector"]
    raiz = bpb["reservados"] + bpb["fats"] * bpb["sectores_fat"]
    salida = []
    base = raiz * sector
    for i in range(bpb["raiz"]):
        e = disco[base + i * 32:base + (i + 1) * 32]
        if len(e) < 32 or e[0] in (0x00, 0xE5):
            continue
        if e[11] & 0x08:                        # etiqueta del volumen
            continue
        nombre = e[0:8].decode("latin-1").rstrip()
        extension = e[8:11].decode("latin-1").rstrip()
        salida.append((nombre + ("." + extension if extension else ""),
                       struct.unpack("<H", e[26:28])[0],
                       struct.unpack("<I", e[28:32])[0]))
    return salida


def leer_archivo(disco: bytes, nombre: str) -> bytes:
    """Saca un archivo siguiendo la FAT, como haria Human68k."""
    bpb = leer_bpb(disco)
    sector = bpb["sector"]
    primera_fat = bpb["reservados"]
    raiz = primera_fat + bpb["fats"] * bpb["sectores_fat"]
    datos_en = raiz + (bpb["raiz"] * 32 + sector - 1) // sector
    for encontrado, primera, largo in leer_directorio(disco):
        if encontrado.upper() != nombre.upper():
            continue
        fat = disco[primera_fat * sector:
                    (primera_fat + bpb["sectores_fat"]) * sector]
        datos = bytearray()
        agrupacion = primera
        while 2 <= agrupacion < 0xFF8 and len(datos) < largo:
            inicio = (datos_en + (agrupacion - 2) * bpb["por_agrupacion"]) * sector
            datos += disco[inicio:inicio + sector * bpb["por_agrupacion"]]
            base = agrupacion * 3 // 2
            par = fat[base] | (fat[base + 1] << 8)
            agrupacion = (par >> 4) if agrupacion & 1 else (par & 0xFFF)
        return bytes(datos[:largo])
    raise ErrorDisco("'%s' no esta en el disquete" % nombre)



def _entradas_raiz(disco, bpb: Dict[str, int]):
    """Recorre las entradas del directorio raiz y da el offset de cada una."""
    raiz = bpb["reservados"] + bpb["fats"] * bpb["sectores_fat"]
    base = raiz * bpb["sector"]
    for i in range(bpb["raiz"]):
        yield base + i * 32


def _primer_dato(bpb: Dict[str, int]) -> int:
    """El sector donde empiezan los datos, o sea la agrupacion numero 2."""
    raiz = bpb["reservados"] + bpb["fats"] * bpb["sectores_fat"]
    return raiz + (bpb["raiz"] * 32 + bpb["sector"] - 1) // bpb["sector"]


def _fat_leer(disco, bpb: Dict[str, int], agrupacion: int) -> int:
    base = bpb["reservados"] * bpb["sector"] + agrupacion * 3 // 2
    par = disco[base] | (disco[base + 1] << 8)
    return (par >> 4) if agrupacion & 1 else (par & 0xFFF)


def _fat_escribir(disco: bytearray, bpb: Dict[str, int], agrupacion: int,
                  valor: int) -> None:
    """Escribe una entrada de la FAT, en las dos copias que tiene el disco."""
    for copia in range(bpb["fats"]):
        base = ((bpb["reservados"] + copia * bpb["sectores_fat"]) * bpb["sector"]
                + agrupacion * 3 // 2)
        par = disco[base] | (disco[base + 1] << 8)
        if agrupacion & 1:
            par = (par & 0x000F) | ((valor & 0xFFF) << 4)
        else:
            par = (par & 0xF000) | (valor & 0xFFF)
        disco[base] = par & 0xFF
        disco[base + 1] = (par >> 8) & 0xFF


def insertar_archivo(imagen: bytes, nombre: str, datos: bytes) -> bytes:
    """Mete un archivo en un disquete que ya existe, sin tocar lo demas.

    Es lo que hace falta para probar el juego de verdad en el emulador: se coge
    un disco de sistema de Human68k, se le anade el .X y arranca solo. Busca
    agrupaciones libres en la FAT y una entrada libre en la raiz, igual que
    haria el sistema al copiar el archivo.
    """
    disco = bytearray(imagen)
    bpb = leer_bpb(disco)
    paso = bpb["sector"] * bpb["por_agrupacion"]
    datos_en = _primer_dato(bpb)
    agrupaciones = (bpb["sectores"] - datos_en) // bpb["por_agrupacion"] + 2

    _nombre_83(nombre)          # que reviente aqui si el nombre no vale
    hueco = None
    for off in _entradas_raiz(disco, bpb):
        if disco[off] in (0x00, 0xE5):
            hueco = off
            break
    if hueco is None:
        raise ErrorDisco("no queda sitio en el directorio raiz")

    libres = [c for c in range(2, agrupaciones) if _fat_leer(disco, bpb, c) == 0]
    hacen_falta = max(1, (len(datos) + paso - 1) // paso)
    if len(libres) < hacen_falta:
        raise ErrorDisco("no caben %d bytes: quedan %d agrupaciones libres"
                         % (len(datos), len(libres)))
    cadena = libres[:hacen_falta]

    for i, agrupacion in enumerate(cadena):
        inicio = (datos_en + (agrupacion - 2) * bpb["por_agrupacion"]) * bpb["sector"]
        trozo = datos[i * paso:(i + 1) * paso]
        disco[inicio:inicio + len(trozo)] = trozo
        _fat_escribir(disco, bpb, agrupacion,
                      cadena[i + 1] if i + 1 < len(cadena) else 0xFFF)

    disco[hueco:hueco + 32] = _entrada(nombre, cadena[0], len(datos))
    return bytes(disco)


def reemplazar_archivo(imagen: bytes, nombre: str, datos: bytes) -> bytes:
    """Cambia el contenido de un archivo que ya esta en el disquete.

    Vale para tocar el AUTOEXEC.BAT de un disco de sistema sin remontar nada.
    Lo nuevo tiene que caber en las agrupaciones que ya ocupaba el archivo, que
    para un AUTOEXEC.BAT de dos lineas sobra de largo.
    """
    disco = bytearray(imagen)
    bpb = leer_bpb(disco)
    paso = bpb["sector"] * bpb["por_agrupacion"]
    datos_en = _primer_dato(bpb)
    quiere = _nombre_83(nombre)

    for off in _entradas_raiz(disco, bpb):
        if disco[off] in (0x00, 0xE5):
            continue
        if (bytes(disco[off:off + 8]), bytes(disco[off + 8:off + 11])) != quiere:
            continue
        agrupacion = struct.unpack("<H", disco[off + 26:off + 28])[0]
        cabe = 0
        cadena = []
        while 2 <= agrupacion < 0xFF0:
            cadena.append(agrupacion)
            cabe += paso
            agrupacion = _fat_leer(disco, bpb, agrupacion)
        if len(datos) > cabe:
            raise ErrorDisco("'%s' ocupaba %d bytes de disco y lo nuevo pide %d"
                             % (nombre, cabe, len(datos)))
        relleno = bytes(datos).ljust(cabe, b"\x00")
        for i, agrupacion in enumerate(cadena):
            inicio = (datos_en + (agrupacion - 2) * bpb["por_agrupacion"]) * bpb["sector"]
            disco[inicio:inicio + paso] = relleno[i * paso:(i + 1) * paso]
        struct.pack_into("<I", disco, off + 28, len(datos))
        return bytes(disco)
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
