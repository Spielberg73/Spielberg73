#!/usr/bin/env python3
"""Monta un disquete de Atari ST (.st), sin necesitar nada instalado.

Un .st es la copia byte a byte de un disquete: 80 pistas x 2 caras x 9 sectores
x 512 bytes = 737280 bytes (720 KB). Dentro va un **FAT12**, el mismo sistema de
ficheros del MS-DOS de la epoca, que es el que usa TOS:

    sector 0        el sector de arranque, con la tabla de parametros (BPB)
    sectores 1-5    la FAT
    sectores 6-10   su copia
    sectores 11-17  el directorio raiz (112 entradas)
    sector 18 en adelante   los datos, en grupos ("clusters") de dos sectores

El juego se mete en una carpeta llamada **AUTO**: al encender, TOS mira si el
disquete tiene esa carpeta y ejecuta los .PRG que haya dentro antes de sacar el
escritorio. Es la forma normal de que un disco de juego arranque solo, y no hace
falta escribir codigo en el sector de arranque.

Ojo con una cosa que despista: aunque el 68000 es big endian, los numeros de la
tabla de parametros y del directorio van **al reves** (little endian), porque el
formato viene del PC y Atari lo copio tal cual para poder intercambiar discos.

El disco sale siempre igual byte a byte (las fechas son fijas), asi que dos
compilaciones del mismo juego dan el mismo .st.

    python3 hacer_st.py disco.st JUEGO.PRG juego.prg
"""

from __future__ import annotations

import struct
import sys
from typing import Dict, List, Optional, Tuple

SECTOR = 512
SECTORES_PISTA = 9
CARAS = 2
PISTAS = 80
SECTORES = PISTAS * CARAS * SECTORES_PISTA        # 1440
TAMANO = SECTORES * SECTOR                        # 737280 bytes

RESERVADOS = 1                                    # el sector de arranque
FATS = 2
SECTORES_FAT = 5
ENTRADAS_RAIZ = 112
SECTORES_RAIZ = ENTRADAS_RAIZ * 32 // SECTOR      # 7
SECTORES_CLUSTER = 2
CLUSTER = SECTOR * SECTORES_CLUSTER               # 1024 bytes
MEDIO = 0xF9                                      # el codigo de "720 KB, dos caras"

PRIMER_DATO = RESERVADOS + FATS * SECTORES_FAT + SECTORES_RAIZ    # 18
CLUSTERES = (SECTORES - PRIMER_DATO) // SECTORES_CLUSTER          # 711

LIBRE, FIN = 0x000, 0xFFF
ATR_DIRECTORIO, ATR_ARCHIVO = 0x10, 0x20

# Fecha fija (1 de enero de 1994) para que el disco sea reproducible.
HORA = 0                                          # 00:00:00
FECHA = ((1994 - 1980) << 9) | (1 << 5) | 1


class ErrorSt(Exception):
    pass


def _nombre_83(nombre: str) -> bytes:
    """'JUEGO.PRG' -> los once bytes que espera el directorio."""
    nombre = nombre.upper()
    base, _, extension = nombre.partition(".")
    if len(base) > 8 or len(extension) > 3:
        raise ErrorSt("'%s' no cabe en un nombre de TOS (ocho letras y tres de "
                      "extension)" % nombre)
    return (base.ljust(8) + extension.ljust(3)).encode("ascii")


class Disco:
    """Un disquete en blanco al que se le van metiendo ficheros."""

    def __init__(self, etiqueta: str = "NEOPLAT"):
        self.sectores: List[bytearray] = [bytearray(SECTOR) for _ in range(SECTORES)]
        self.fat: List[int] = [LIBRE] * CLUSTERES
        self.fat[0], self.fat[1] = 0xFF9, 0xFFF    # los dos primeros no son de nadie
        self.raiz: List[bytes] = []
        self._arranque(etiqueta)

    # --- el sector de arranque ----------------------------------------

    def _arranque(self, etiqueta: str) -> None:
        """La tabla de parametros. El codigo de arranque no hace falta: el juego
        lo lanza TOS desde la carpeta AUTO."""
        boot = self.sectores[0]
        boot[0:2] = b"\x60\x1C"                    # bra.s +30, por costumbre
        boot[2:8] = etiqueta.upper().ljust(6)[:6].encode("ascii", "replace")
        struct.pack_into("<HBHBHHBHHHH", boot, 11,
                         SECTOR, SECTORES_CLUSTER, RESERVADOS, FATS, ENTRADAS_RAIZ,
                         SECTORES, MEDIO, SECTORES_FAT, SECTORES_PISTA, CARAS, 0)
        # TOS arranca el sector solo si la suma de sus 256 palabras da $1234;
        # aqui **no** queremos eso, asi que se comprueba que no lo dé.
        if self._suma_arranque() == 0x1234:
            boot[510] = 0xFF

    def _suma_arranque(self) -> int:
        boot = self.sectores[0]
        return sum(struct.unpack_from(">H", boot, i)[0]
                   for i in range(0, SECTOR, 2)) & 0xFFFF

    # --- clusters -----------------------------------------------------

    def _reservar(self, cuantos: int) -> List[int]:
        libres = [c for c in range(2, CLUSTERES) if self.fat[c] == LIBRE]
        if len(libres) < cuantos:
            raise ErrorSt("el disquete se ha llenado: no caben 720 KB")
        cadena = libres[:cuantos]
        for i, c in enumerate(cadena):
            self.fat[c] = cadena[i + 1] if i + 1 < len(cadena) else FIN
        return cadena

    def _escribir(self, cadena: List[int], datos: bytes) -> None:
        for i, c in enumerate(cadena):
            trozo = datos[i * CLUSTER:(i + 1) * CLUSTER].ljust(CLUSTER, b"\0")
            primero = PRIMER_DATO + (c - 2) * SECTORES_CLUSTER
            for s in range(SECTORES_CLUSTER):
                self.sectores[primero + s] = bytearray(
                    trozo[s * SECTOR:(s + 1) * SECTOR])

    # --- entradas del directorio --------------------------------------

    @staticmethod
    def _entrada(nombre: bytes, atributos: int, cluster: int, tamano: int) -> bytes:
        entrada = bytearray(32)
        entrada[0:11] = nombre
        entrada[11] = atributos
        struct.pack_into("<HHHI", entrada, 22, HORA, FECHA, cluster, tamano)
        return bytes(entrada)

    def fichero(self, nombre: str, datos: bytes,
                carpeta: Optional[List[bytes]] = None) -> None:
        cuantos = max(1, (len(datos) + CLUSTER - 1) // CLUSTER)
        cadena = self._reservar(cuantos)
        self._escribir(cadena, datos)
        entrada = self._entrada(_nombre_83(nombre), ATR_ARCHIVO, cadena[0], len(datos))
        (self.raiz if carpeta is None else carpeta).append(entrada)

    def carpeta(self, nombre: str) -> Tuple[List[bytes], int]:
        """Una carpeta del raiz. Devuelve su lista de entradas y su cluster; se
        rellena luego, al cerrar el disco."""
        cluster = self._reservar(1)[0]
        self.raiz.append(self._entrada(_nombre_83(nombre), ATR_DIRECTORIO, cluster, 0))
        entradas = [
            self._entrada(b".          ", ATR_DIRECTORIO, cluster, 0),
            self._entrada(b"..         ", ATR_DIRECTORIO, 0, 0),
        ]
        return entradas, cluster

    # --- cerrar el disco ----------------------------------------------

    def cerrar_carpeta(self, entradas: List[bytes], cluster: int) -> None:
        datos = b"".join(entradas)
        if len(datos) > CLUSTER:
            raise ErrorSt("en esa carpeta no caben mas de %d entradas"
                          % (CLUSTER // 32))
        self._escribir([cluster], datos)

    def _fat(self) -> bytes:
        """FAT12: dos entradas en tres bytes, y ademas al reves."""
        crudo = bytearray(SECTORES_FAT * SECTOR)
        # los clusters van de dos en dos y aqui son impares: se anade uno de
        # relleno para que el ultimo de verdad tambien se escriba
        entradas = self.fat + [LIBRE] * (len(self.fat) % 2)
        for i in range(0, len(entradas), 2):
            a, b = entradas[i], entradas[i + 1]
            trio = i // 2 * 3
            crudo[trio] = a & 0xFF
            crudo[trio + 1] = ((a >> 8) & 0x0F) | ((b & 0x0F) << 4)
            crudo[trio + 2] = (b >> 4) & 0xFF
        return bytes(crudo)

    def bytes(self) -> bytes:
        fat = self._fat()
        for copia in range(FATS):
            base = RESERVADOS + copia * SECTORES_FAT
            for s in range(SECTORES_FAT):
                self.sectores[base + s] = bytearray(fat[s * SECTOR:(s + 1) * SECTOR])
        raiz = b"".join(self.raiz).ljust(SECTORES_RAIZ * SECTOR, b"\0")
        base = RESERVADOS + FATS * SECTORES_FAT
        for s in range(SECTORES_RAIZ):
            self.sectores[base + s] = bytearray(raiz[s * SECTOR:(s + 1) * SECTOR])
        return b"".join(bytes(s) for s in self.sectores)


# --------------------------------------------------------------- leer

def leer(datos: bytes) -> Dict[str, bytes]:
    """Saca los ficheros de un .st. Se usa para comprobar lo que se ha escrito."""
    if len(datos) != TAMANO:
        raise ErrorSt("un disquete de ST mide %d bytes, no %d" % (TAMANO, len(datos)))

    fat: List[int] = []
    crudo = datos[RESERVADOS * SECTOR:(RESERVADOS + SECTORES_FAT) * SECTOR]
    for i in range(0, CLUSTERES + CLUSTERES % 2, 2):
        trio = i // 2 * 3
        fat.append(crudo[trio] | ((crudo[trio + 1] & 0x0F) << 8))
        fat.append((crudo[trio + 1] >> 4) | (crudo[trio + 2] << 4))

    def contenido(cluster: int, tamano: Optional[int]) -> bytes:
        trozos = []
        while 2 <= cluster < CLUSTERES:
            primero = PRIMER_DATO + (cluster - 2) * SECTORES_CLUSTER
            trozos.append(datos[primero * SECTOR:(primero + SECTORES_CLUSTER) * SECTOR])
            cluster = fat[cluster]
        entero = b"".join(trozos)
        return entero if tamano is None else entero[:tamano]

    salida: Dict[str, bytes] = {}

    def recorrer(crudo_dir: bytes, ruta: str) -> None:
        for i in range(0, len(crudo_dir), 32):
            entrada = crudo_dir[i:i + 32]
            if not entrada[0] or entrada[0] == 0xE5 or entrada[0] == ord("."):
                continue
            nombre = entrada[0:8].decode("ascii").rstrip()
            extension = entrada[8:11].decode("ascii").rstrip()
            if extension:
                nombre += "." + extension
            cluster, tamano = struct.unpack_from("<HI", entrada, 26)
            if entrada[11] & ATR_DIRECTORIO:
                recorrer(contenido(cluster, None), ruta + nombre + "/")
            else:
                salida[ruta + nombre] = contenido(cluster, tamano)

    base = RESERVADOS + FATS * SECTORES_FAT
    recorrer(datos[base * SECTOR:(base + SECTORES_RAIZ) * SECTOR], "")
    return salida


# --------------------------------------------------------------- cli

def crear_disco_de_juego(ruta: str, etiqueta: str, ejecutable: str,
                         datos: bytes) -> Tuple[int, int]:
    """Un disquete que arranca solo: el juego, dentro de AUTO."""
    disco = Disco(etiqueta)
    auto, cluster = disco.carpeta("AUTO")
    disco.fichero(ejecutable, datos, auto)
    disco.cerrar_carpeta(auto, cluster)
    imagen = disco.bytes()
    with open(ruta, "wb") as fh:
        fh.write(imagen)
    libres = sum(1 for c in disco.fat[2:] if c == LIBRE)
    return len(imagen), libres * CLUSTER


def main(argv: List[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 1
    destino, ejecutable = argv[1], argv[2]
    origen = argv[3] if len(argv) > 3 else ejecutable
    etiqueta = argv[4] if len(argv) > 4 else "NEOPLA"
    try:
        with open(origen, "rb") as fh:
            datos = fh.read()
        tamano, libre = crear_disco_de_juego(destino, etiqueta, ejecutable, datos)
    except (OSError, ErrorSt) as error:
        sys.stderr.write("error: %s\n" % error)
        return 1
    print("disquete de Atari ST: %s (%d KB, arranca solo, quedan %d KB libres)"
          % (destino, tamano // 1024, libre // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
