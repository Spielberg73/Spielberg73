"""Convierte el ELF del enlazador en un ejecutable .X de Human68k (X68000).

Human68k es el sistema del X68000 y sus programas son archivos .X. El formato
es de los faciles: una cabecera de 64 bytes, el codigo, los datos y una tabla de
direcciones que hay que corregir.

    +0   'HU\\0\\0'
    +4   long   direccion de montaje (la que supone el codigo)
    +8   long   donde empieza a ejecutarse, contando desde ahi
    +12  long   tamano del codigo (TEXT)
    +16  long   tamano de los datos (DATA)
    +20  long   tamano del hueco sin inicializar (BSS)
    +24  long   tamano de la tabla de correcciones
    +28  long   tamano de la tabla de simbolos
    +32  32 bytes a cero
    +64  el codigo, los datos y detras la tabla

La tabla de correcciones va **por saltos**: cada palabra es lo que se avanza
desde la correccion anterior (la primera, desde el principio del programa). Una
palabra no llega a 65.536, asi que para un salto mas largo se escribe un 1 -que
como salto seria imposible, las direcciones son pares- y detras el salto de
verdad en una palabra larga.

Es el mismo trabajo que hacen prg.py para el Atari ST y hunk.py para el Amiga,
con otro formato: el enlazador nos da un ELF con las direcciones absolutas
marcadas y aqui se traducen.

    python3 hacer_x.py juego.elf JUEGO.X
"""

from __future__ import annotations

import struct
import sys
from typing import Dict, List, Tuple

MAGIA = b"HU\0\0"
R_68K_32 = 1
CABECERA = 64
ESCAPE = 1                       # palabra que anuncia un salto largo
LIMITE_PROG = 16 * 1024 * 1024   # ninguna direccion nuestra pasa de aqui


class ErrorX(Exception):
    pass


class Elf:
    """Lo justo de un ELF de 68000 (32 bits, big endian) para esto.

    Es el mismo lector que usan prg.py y hunk.py; va copiado en los tres para
    que cada proyecto generado se valga solo, sin importar nada del kit.
    """

    def __init__(self, datos: bytes):
        if datos[:4] != b"\x7fELF":
            raise ErrorX("esto no es un ELF")
        if datos[4] != 1 or datos[5] != 2:
            raise ErrorX("se esperaba un ELF de 32 bits y big endian (68000)")
        self.datos = datos
        (self.tipo, self.maquina) = struct.unpack_from(">HH", datos, 16)
        if self.maquina != 4:
            raise ErrorX("el ELF no es de 68000 (e_machine=%d)" % self.maquina)
        (shoff, ) = struct.unpack_from(">I", datos, 32)
        (shentsize, shnum, shstrndx) = struct.unpack_from(">HHH", datos, 46)
        self.secciones: List[Dict] = []
        for i in range(shnum):
            base = shoff + i * shentsize
            campos = struct.unpack_from(">IIIIIIIIII", datos, base)
            self.secciones.append({
                "nombre_off": campos[0], "tipo": campos[1], "flags": campos[2],
                "addr": campos[3], "offset": campos[4], "size": campos[5],
                "link": campos[6], "info": campos[7], "align": campos[8],
                "entsize": campos[9], "indice": i,
            })
        tabla = self.secciones[shstrndx]
        crudo = datos[tabla["offset"]:tabla["offset"] + tabla["size"]]
        for s in self.secciones:
            fin = crudo.index(b"\0", s["nombre_off"])
            s["nombre"] = crudo[s["nombre_off"]:fin].decode("ascii")

    def seccion(self, nombre: str):
        for s in self.secciones:
            if s["nombre"] == nombre:
                return s
        return None

    def contenido(self, s) -> bytes:
        if s["tipo"] == 8:               # SHT_NOBITS (.bss)
            return b"\0" * s["size"]
        return self.datos[s["offset"]:s["offset"] + s["size"]]

    def relocalizaciones(self, seccion) -> List[Tuple[int, int]]:
        """Devuelve (direccion, tipo) de las relocalizaciones de esa seccion."""
        salida = []
        for s in self.secciones:
            if s["tipo"] != 4 or s["info"] != seccion["indice"]:   # SHT_RELA
                continue
            crudo = self.contenido(s)
            for i in range(0, len(crudo), 12):
                offset, info, _addend = struct.unpack_from(">IIi", crudo, i)
                salida.append((offset, info & 0xFF))
        return salida


def tabla_de_correcciones(offsets: List[int]) -> bytes:
    """Los desplazamientos a corregir, en el formato de Human68k."""
    if not offsets:
        return b""
    offsets = sorted(offsets)
    for offset in offsets:
        if offset % 2:
            raise ErrorX("hay una correccion en una direccion impar (0x%x); el "
                         "68000 no puede leer una palabra larga ahi" % offset)
    salida = bytearray()
    anterior = 0
    for offset in offsets:
        salto = offset - anterior
        anterior = offset
        if salto < 0x10000:
            salida += struct.pack(">H", salto)
        else:
            salida += struct.pack(">HI", ESCAPE, salto)
    return bytes(salida)


def convertir(ruta_elf: str, base: int = 0) -> Tuple[bytes, Dict[str, int]]:
    """ELF -> bytes del .X, mas unas cuantas cifras.

    `base` es la direccion de montaje que se escribe en la cabecera. Con 0,
    Human68k coloca el programa donde le cabe y usa la tabla para corregir las
    direcciones, que es lo normal.
    """
    with open(ruta_elf, "rb") as fh:
        elf = Elf(fh.read())

    texto = elf.seccion(".text")
    if texto is None:
        raise ErrorX("el ELF no trae seccion .text")
    codigo = bytearray(elf.contenido(texto))
    while len(codigo) % 4:
        codigo.append(0)

    bss = elf.seccion(".bss")
    tamano_bss = bss["size"] if bss is not None else 0
    tamano_bss = (tamano_bss + 3) & ~3

    # Como en el Atari ST: el enlazador deja .data y .bss detras de .text, asi
    # que todo el programa es un bloque y cada direccion absoluta es un
    # desplazamiento desde el principio. Por eso DATA va a cero y todo cuenta
    # como TEXT: el cargador de Human68k los pone seguidos igual.
    correcciones: List[int] = []
    for direccion, tipo in elf.relocalizaciones(texto):
        if tipo != R_68K_32:
            continue                     # las relativas al PC no hay que tocarlas
        offset = direccion - texto["addr"]
        if offset < 0 or offset + 4 > len(codigo):
            raise ErrorX("una relocalizacion cae fuera de .text (0x%x)" % direccion)
        (valor, ) = struct.unpack_from(">I", codigo, offset)
        if valor >= LIMITE_PROG:
            raise ErrorX(
                "una direccion del codigo (0x%08x) no cae dentro del programa; "
                "revisa x68000.ld" % valor)
        # la direccion se guarda relativa al principio, y el cargador le suma
        # donde haya montado el programa
        struct.pack_into(">I", codigo, offset, valor - texto["addr"] + base)
        correcciones.append(offset)

    tabla = tabla_de_correcciones(correcciones)

    entrada = 0
    salida = bytearray()
    salida += MAGIA
    salida += struct.pack(">7I", base, entrada, len(codigo), 0, tamano_bss,
                          len(tabla), 0)
    salida += b"\0" * 32
    if len(salida) != CABECERA:
        raise ErrorX("la cabecera mide %d bytes y son 64" % len(salida))
    salida += codigo
    salida += tabla

    info = {
        "texto": len(codigo),
        "bss": tamano_bss,
        "reloc": len(correcciones),
        "tabla": len(tabla),
        "archivo": len(salida),
    }
    return bytes(salida), info


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    destino = argv[2] if len(argv) > 2 else "JUEGO.X"
    try:
        datos, info = convertir(argv[1])
    except (OSError, ErrorX) as error:
        sys.stderr.write("error: %s\n" % error)
        return 1
    with open(destino, "wb") as fh:
        fh.write(datos)
    print("ejecutable de X68000: %s (%d KB de codigo y datos, %d KB de BSS, "
          "%d direcciones corregidas)"
          % (destino, info["texto"] // 1024, info["bss"] // 1024, info["reloc"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
