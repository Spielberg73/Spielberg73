#!/usr/bin/env python3
"""Monta un disquete de Amiga (.adf) arrancable, sin necesitar nada instalado.

Un ADF es la copia byte a byte de un disquete de 880 KB: 80 cilindros x 2 caras
x 11 sectores x 512 bytes = 901120 bytes. Dentro va un sistema de ficheros de
AmigaDOS. Esto lo escribe entero:

  bloques 0-1    bootblock: 'DOS\\0', su suma de control y el codigo que arranca
                 AmigaDOS (busca dos.library en la ROM y le pasa el control)
  bloque 880     raiz del disco: su nombre, la tabla hash y donde esta el bitmap
  bloque 881     bitmap: un bit por bloque, a 1 si esta libre
  el resto       las cabeceras y los datos de los ficheros

Se usa **OFS** (Old File System, `DOS\\0`) a proposito: es el unico que arranca
en un Amiga con Kickstart 1.3 sin meter el sistema de ficheros en el propio
disco. Gasta 24 bytes de cada bloque en una cabecera, asi que caben 488 bytes
de datos por bloque en vez de 512; a cambio, arranca en cualquier Amiga.

El disco sale siempre igual byte a byte (las fechas son fijas), asi que dos
compilaciones del mismo juego dan el mismo ADF.

    python3 hacer_adf.py disco.adf "BOSQUE" BosqueMagico
"""

from __future__ import annotations

import struct
import sys
from typing import Dict, List, Optional, Tuple

BLOQUE = 512
SECTORES = 11
CARAS = 2
CILINDROS = 80
BLOQUES = CILINDROS * CARAS * SECTORES          # 1760
TAMANO = BLOQUES * BLOQUE                       # 901120 bytes

BLOQUE_RAIZ = BLOQUES // 2                      # 880, el del medio del disco
DATOS_POR_BLOQUE = BLOQUE - 24                  # 488, lo que deja la cabecera OFS
ENTRADAS_HASH = BLOQUE // 4 - 56                # 72

T_HEADER, T_DATA, T_LIST = 2, 8, 16
ST_ROOT, ST_USERDIR, ST_FILE = 1, 2, -3

# Fecha fija (1 de enero de 1994) para que el disco sea reproducible.
FECHA = (5844, 0, 0)                            # dias desde 1978, minutos, ticks


class ErrorAdf(Exception):
    pass


def _suma_bloque(datos: bytearray, donde: int = 20) -> int:
    """Suma de control de un bloque del sistema de ficheros.

    Es la suma de las 128 palabras largas con el campo puesto a cero, cambiada
    de signo: asi la suma del bloque entero da cero.
    """
    copia = bytearray(datos)
    struct.pack_into(">I", copia, donde, 0)
    suma = 0
    for i in range(0, BLOQUE, 4):
        suma = (suma + struct.unpack_from(">I", copia, i)[0]) & 0xFFFFFFFF
    return (-suma) & 0xFFFFFFFF


def _suma_boot(datos: bytearray) -> int:
    """La del bootblock es distinta: suma con acarreo de 1024 bytes, invertida."""
    copia = bytearray(datos)
    struct.pack_into(">I", copia, 4, 0)
    suma = 0
    for i in range(0, len(copia), 4):
        anterior = suma
        suma = (suma + struct.unpack_from(">I", copia, i)[0]) & 0xFFFFFFFF
        if suma < anterior:                      # se ha desbordado: se acarrea
            suma = (suma + 1) & 0xFFFFFFFF
    return (~suma) & 0xFFFFFFFF


def hash_nombre(nombre: str) -> int:
    """Donde cae un nombre en la tabla hash de un directorio (asi lo hace AmigaDOS)."""
    valor = len(nombre)
    for letra in nombre.upper():
        valor = (valor * 13 + ord(letra)) & 0x7FF
    return valor % ENTRADAS_HASH


def _poner_nombre(bloque: bytearray, offset: int, nombre: str, largo: int) -> None:
    crudo = nombre.encode("latin-1", "replace")[:largo]
    bloque[offset] = len(crudo)
    bloque[offset + 1:offset + 1 + len(crudo)] = crudo


def _codigo_de_arranque() -> bytes:
    """El codigo del bootblock: 'arranca AmigaDOS y quitate de en medio'.

    Es el arranque normal de un disquete de AmigaDOS, escrito en codigo maquina
    del 68000 (son nueve instrucciones). Cuando el Amiga lo llama, a6 ya trae la
    base de exec.

        lea     dos(pc),a1
        jsr     -96(a6)         ; FindResident("dos.library")
        tst.l   d0
        beq.s   fallo
        move.l  d0,a0
        move.l  22(a0),a0       ; el punto de entrada de la biblioteca
        moveq   #0,d0
        rts
    fallo:  moveq #-1,d0
        rts
        dc.b    'dos.library',0
    """
    return bytes([
        0x43, 0xFA, 0x00, 0x18,          # lea 24(pc),a1  -> la cadena de abajo
        0x4E, 0xAE, 0xFF, 0xA0,          # jsr -96(a6)    -> FindResident
        0x4A, 0x80,                      # tst.l d0
        0x67, 0x0A,                      # beq.s fallo
        0x20, 0x40,                      # move.l d0,a0
        0x20, 0x68, 0x00, 0x16,          # move.l 22(a0),a0
        0x70, 0x00,                      # moveq #0,d0
        0x4E, 0x75,                      # rts
        0x70, 0xFF,                      # moveq #-1,d0
        0x4E, 0x75,                      # rts
    ]) + b"dos.library\0"


class Disco:
    """Un disquete en blanco al que se le van metiendo ficheros."""

    def __init__(self, nombre: str = "NEOPLAT", arrancable: bool = True):
        self.bloques: List[bytearray] = [bytearray(BLOQUE) for _ in range(BLOQUES)]
        self.usados = set([0, 1, BLOQUE_RAIZ, BLOQUE_RAIZ + 1])
        self.nombre = nombre
        if arrancable:
            self._bootblock()
        self._raiz()

    # --- bloques ------------------------------------------------------

    def _libre(self) -> int:
        for numero in range(2, BLOQUES):
            if numero not in self.usados:
                self.usados.add(numero)
                return numero
        raise ErrorAdf("el disquete se ha llenado: no caben 880 KB")

    def _bootblock(self) -> None:
        boot = bytearray(BLOQUE * 2)
        boot[0:4] = b"DOS\0"                     # OFS, sin proteger
        struct.pack_into(">I", boot, 8, BLOQUE_RAIZ)
        codigo = _codigo_de_arranque()
        boot[12:12 + len(codigo)] = codigo
        struct.pack_into(">I", boot, 4, _suma_boot(boot))
        self.bloques[0] = boot[:BLOQUE]
        self.bloques[1] = boot[BLOQUE:]

    def _raiz(self) -> None:
        raiz = self.bloques[BLOQUE_RAIZ]
        struct.pack_into(">I", raiz, 0x000, T_HEADER)
        struct.pack_into(">I", raiz, 0x00C, ENTRADAS_HASH)
        struct.pack_into(">i", raiz, 0x138, -1)          # el bitmap es valido
        struct.pack_into(">I", raiz, 0x13C, BLOQUE_RAIZ + 1)
        for offset in (0x1A4, 0x1D8, 0x1E4):             # las tres fechas
            struct.pack_into(">III", raiz, offset, *FECHA)
        _poner_nombre(raiz, 0x1B0, self.nombre, 30)
        struct.pack_into(">i", raiz, 0x1FC, ST_ROOT)

    # --- meter cosas dentro -------------------------------------------

    def _enlazar(self, padre: int, entrada: int, nombre: str) -> None:
        """Cuelga una entrada de la tabla hash de su directorio."""
        posicion = 0x018 + hash_nombre(nombre) * 4
        bloque = self.bloques[padre]
        (siguiente, ) = struct.unpack_from(">I", bloque, posicion)
        if not siguiente:
            struct.pack_into(">I", bloque, posicion, entrada)
            return
        while True:                                       # cadena de colisiones
            (encadenado, ) = struct.unpack_from(">I", self.bloques[siguiente], 0x1F0)
            if not encadenado:
                struct.pack_into(">I", self.bloques[siguiente], 0x1F0, entrada)
                return
            siguiente = encadenado

    def carpeta(self, nombre: str, padre: Optional[int] = None) -> int:
        if padre is None:
            padre = BLOQUE_RAIZ
        numero = self._libre()
        bloque = self.bloques[numero]
        struct.pack_into(">I", bloque, 0x000, T_HEADER)
        struct.pack_into(">I", bloque, 0x004, numero)
        struct.pack_into(">III", bloque, 0x1A4, *FECHA)
        _poner_nombre(bloque, 0x1B0, nombre, 30)
        struct.pack_into(">I", bloque, 0x1F4, padre)
        struct.pack_into(">i", bloque, 0x1FC, ST_USERDIR)
        self._enlazar(padre, numero, nombre)
        return numero

    def fichero(self, nombre: str, datos: bytes, padre: Optional[int] = None) -> int:
        """Escribe un fichero: su cabecera, sus bloques de datos y la cadena."""
        if padre is None:
            padre = BLOQUE_RAIZ
        cabecera = self._libre()

        # 1) los datos, troceados en bloques de 488 bytes
        trozos = [datos[i:i + DATOS_POR_BLOQUE]
                  for i in range(0, len(datos), DATOS_POR_BLOQUE)] or [b""]
        numeros = [self._libre() for _ in trozos]
        for i, (numero, trozo) in enumerate(zip(numeros, trozos)):
            bloque = self.bloques[numero]
            struct.pack_into(">I", bloque, 0x000, T_DATA)
            struct.pack_into(">I", bloque, 0x004, cabecera)
            struct.pack_into(">I", bloque, 0x008, i + 1)
            struct.pack_into(">I", bloque, 0x00C, len(trozo))
            struct.pack_into(">I", bloque, 0x010,
                             numeros[i + 1] if i + 1 < len(numeros) else 0)
            bloque[0x018:0x018 + len(trozo)] = trozo

        # 2) la cabecera del fichero, con los 72 primeros bloques de datos
        bloque = self.bloques[cabecera]
        struct.pack_into(">I", bloque, 0x000, T_HEADER)
        struct.pack_into(">I", bloque, 0x004, cabecera)
        struct.pack_into(">I", bloque, 0x010, numeros[0])
        struct.pack_into(">I", bloque, 0x144, len(datos))
        struct.pack_into(">III", bloque, 0x1A4, *FECHA)
        _poner_nombre(bloque, 0x1B0, nombre, 30)
        struct.pack_into(">I", bloque, 0x1F4, padre)
        struct.pack_into(">i", bloque, 0x1FC, ST_FILE)
        self._tabla_de_datos(bloque, numeros[:ENTRADAS_HASH])

        # 3) si hay mas de 72, siguen en bloques de extension encadenados
        resto = numeros[ENTRADAS_HASH:]
        anterior, campo = cabecera, 0x1F8
        while resto:
            extension = self._libre()
            struct.pack_into(">I", self.bloques[anterior], campo, extension)
            ext = self.bloques[extension]
            struct.pack_into(">I", ext, 0x000, T_LIST)
            struct.pack_into(">I", ext, 0x004, extension)
            struct.pack_into(">I", ext, 0x1F4, cabecera)
            struct.pack_into(">i", ext, 0x1FC, ST_FILE)
            self._tabla_de_datos(ext, resto[:ENTRADAS_HASH])
            resto = resto[ENTRADAS_HASH:]
            anterior, campo = extension, 0x1F8

        self._enlazar(padre, cabecera, nombre)
        return cabecera

    @staticmethod
    def _tabla_de_datos(bloque: bytearray, numeros: List[int]) -> None:
        """La tabla se rellena del final hacia el principio; asi la lee AmigaDOS."""
        struct.pack_into(">I", bloque, 0x008, len(numeros))
        for i, numero in enumerate(numeros):
            struct.pack_into(">I", bloque, 0x018 + (ENTRADAS_HASH - 1 - i) * 4, numero)

    # --- cerrar el disco ----------------------------------------------

    def _bitmap(self) -> None:
        bitmap = self.bloques[BLOQUE_RAIZ + 1]
        palabras = [0] * ((BLOQUES - 2 + 31) // 32)
        for numero in range(2, BLOQUES):
            if numero not in self.usados:                  # 1 = libre
                palabras[(numero - 2) // 32] |= 1 << ((numero - 2) % 32)
        for i, palabra in enumerate(palabras):
            struct.pack_into(">I", bitmap, 4 + i * 4, palabra)
        struct.pack_into(">I", bitmap, 0, _suma_bloque(bitmap, 0))

    def bytes(self) -> bytes:
        self._bitmap()
        for numero, bloque in enumerate(self.bloques):
            if numero < 2:
                continue                                   # el boot ya esta hecho
            (tipo, ) = struct.unpack_from(">I", bloque, 0)
            if tipo in (T_HEADER, T_DATA, T_LIST):
                struct.pack_into(">I", bloque, 0x014, _suma_bloque(bloque))
        return b"".join(bytes(b) for b in self.bloques)


# --------------------------------------------------------------- leer

def leer(datos: bytes) -> Dict[str, bytes]:
    """Saca los ficheros de un ADF. Se usa para comprobar lo que se ha escrito."""
    if len(datos) != TAMANO:
        raise ErrorAdf("un ADF mide %d bytes, no %d" % (TAMANO, len(datos)))

    def bloque(numero: int) -> bytes:
        return datos[numero * BLOQUE:(numero + 1) * BLOQUE]

    def nombre_de(b: bytes) -> str:
        largo = b[0x1B0]
        return b[0x1B1:0x1B1 + largo].decode("latin-1")

    salida: Dict[str, bytes] = {}

    def recorrer(numero: int, ruta: str) -> None:
        b = bloque(numero)
        for i in range(ENTRADAS_HASH):
            (entrada, ) = struct.unpack_from(">I", b, 0x018 + i * 4)
            while entrada:
                hijo = bloque(entrada)
                (tipo, ) = struct.unpack_from(">i", hijo, 0x1FC)
                camino = ruta + nombre_de(hijo)
                if tipo == ST_USERDIR:
                    recorrer(entrada, camino + "/")
                elif tipo == ST_FILE:
                    salida[camino] = _leer_fichero(bloque, entrada)
                (entrada, ) = struct.unpack_from(">I", hijo, 0x1F0)

    recorrer(BLOQUE_RAIZ, "")
    return salida


def _leer_fichero(bloque, cabecera: int) -> bytes:
    (tamano, ) = struct.unpack_from(">I", bloque(cabecera), 0x144)
    (siguiente, ) = struct.unpack_from(">I", bloque(cabecera), 0x010)
    trozos = []
    leidos = 0
    while siguiente and leidos < tamano:
        b = bloque(siguiente)
        (cuanto, ) = struct.unpack_from(">I", b, 0x00C)
        trozos.append(b[0x018:0x018 + cuanto])
        leidos += cuanto
        (siguiente, ) = struct.unpack_from(">I", b, 0x010)
    return b"".join(trozos)


# --------------------------------------------------------------- cli

def crear_disco_de_juego(ruta: str, etiqueta: str, ejecutable: str,
                         datos: bytes) -> Tuple[int, int]:
    """Un disquete que arranca solo y ejecuta el juego."""
    disco = Disco(etiqueta)
    disco.fichero(ejecutable, datos)
    carpeta_s = disco.carpeta("s")
    arranque = ("; lo primero que hace el disco al arrancar\n%s\n" % ejecutable)
    disco.fichero("startup-sequence", arranque.encode("latin-1"), carpeta_s)
    imagen = disco.bytes()
    with open(ruta, "wb") as fh:
        fh.write(imagen)
    libres = BLOQUES - len(disco.usados)
    return len(imagen), libres * DATOS_POR_BLOQUE


def main(argv: List[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        return 1
    destino, etiqueta, ejecutable = argv[1], argv[2], argv[3]
    origen = argv[4] if len(argv) > 4 else ejecutable
    try:
        with open(origen, "rb") as fh:
            datos = fh.read()
        tamano, libre = crear_disco_de_juego(destino, etiqueta, ejecutable, datos)
    except (OSError, ErrorAdf) as error:
        sys.stderr.write("error: %s\n" % error)
        return 1
    print("disquete de Amiga: %s (%d KB, arrancable, quedan %d KB libres)"
          % (destino, tamano // 1024, libre // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
