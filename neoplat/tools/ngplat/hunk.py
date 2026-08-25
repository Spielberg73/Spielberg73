#!/usr/bin/env python3
"""Convierte el ELF del enlazador en un ejecutable de AmigaDOS (formato hunk).

Un ejecutable de Amiga no lleva direcciones fijas: es una lista de trozos
("hunks") que el sistema carga donde le cabe, mas una tabla que dice que
palabras largas del codigo hay que corregir con la direccion real. Esto es lo
que hace este archivo, sin necesitar nada instalado:

  1. lee las secciones del ELF (.text con el codigo, las constantes y los datos;
     .bss con las variables a cero)
  2. lee las relocalizaciones que deja `ld --emit-relocs` y separa las que
     apuntan al hunk de codigo de las que apuntan al de BSS
  3. escribe el archivo:

        HUNK_HEADER   cuantos hunks hay y cuanto ocupa cada uno
        HUNK_CODE     el codigo y los datos
        HUNK_RELOC32  que corregir y con que hunk
        HUNK_END
        HUNK_BSS      cuanto hay que reservar
        HUNK_END

Los dos hunks se piden en RAM chip (HUNKF_CHIP), que es la unica a la que
llegan el copper, el blitter y Paula.

    python3 hacer_ejecutable.py juego.elf juego
"""

from __future__ import annotations

import struct
import sys
from typing import Dict, List, Tuple

HUNK_CODE = 0x3E9
HUNK_BSS = 0x3EB
HUNK_RELOC32 = 0x3EC
HUNK_END = 0x3F2
HUNK_HEADER = 0x3F3
HUNKF_CHIP = 0x40000000

R_68K_32 = 1

BASE_BSS = 0x40000000            # tiene que coincidir con amiga.ld
LIMITE_PROG = 8 * 1024 * 1024


class ErrorHunk(Exception):
    pass


# ----------------------------------------------------------------- ELF

class Elf:
    """Lo justo de un ELF de 68000 (32 bits, big endian) para esto."""

    def __init__(self, datos: bytes):
        if datos[:4] != b"\x7fELF":
            raise ErrorHunk("esto no es un ELF")
        if datos[4] != 1 or datos[5] != 2:
            raise ErrorHunk("se esperaba un ELF de 32 bits y big endian (68000)")
        self.datos = datos
        (self.tipo, self.maquina) = struct.unpack_from(">HH", datos, 16)
        if self.maquina != 4:
            raise ErrorHunk("el ELF no es de 68000 (e_machine=%d)" % self.maquina)
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


# --------------------------------------------------------------- hunks

def _largo(valor: int) -> bytes:
    return struct.pack(">I", valor & 0xFFFFFFFF)


def convertir(ruta_elf: str, chip: bool = True) -> Tuple[bytes, Dict[str, int]]:
    """ELF -> bytes del ejecutable de AmigaDOS, mas unas cuantas cifras."""
    with open(ruta_elf, "rb") as fh:
        elf = Elf(fh.read())

    texto = elf.seccion(".text")
    if texto is None:
        raise ErrorHunk("el ELF no trae seccion .text")
    codigo = bytearray(elf.contenido(texto))
    while len(codigo) % 4:
        codigo.append(0)

    bss = elf.seccion(".bss")
    tamano_bss = bss["size"] if bss is not None else 0
    tamano_bss = (tamano_bss + 3) & ~3

    # que palabras largas hay que corregir, y a que hunk apuntan
    correcciones: Dict[int, List[int]] = {0: [], 1: []}
    for direccion, tipo in elf.relocalizaciones(texto):
        offset = direccion - texto["addr"]
        if offset < 0 or offset + 4 > len(codigo):
            raise ErrorHunk("una relocalizacion cae fuera de .text (0x%x)" % direccion)
        if tipo != R_68K_32:
            continue                     # las relativas al PC no hay que tocarlas
        (valor, ) = struct.unpack_from(">I", codigo, offset)
        if valor >= BASE_BSS:
            struct.pack_into(">I", codigo, offset, valor - BASE_BSS)
            correcciones[1].append(offset)
        elif valor < LIMITE_PROG:
            correcciones[0].append(offset)
        else:
            raise ErrorHunk(
                "una direccion del codigo (0x%08x) no cae en ninguno de los dos "
                "hunks; revisa amiga.ld" % valor)

    bandera = HUNKF_CHIP if chip else 0
    salida = bytearray()
    salida += _largo(HUNK_HEADER)
    salida += _largo(0)                  # sin nombres de bibliotecas residentes
    salida += _largo(2)                  # cuantos hunks caben en la tabla
    salida += _largo(0)                  # primero
    salida += _largo(1)                  # ultimo
    salida += _largo((len(codigo) // 4) | bandera)
    salida += _largo((tamano_bss // 4) | bandera)

    salida += _largo(HUNK_CODE)
    salida += _largo(len(codigo) // 4)
    salida += codigo

    if any(correcciones.values()):
        salida += _largo(HUNK_RELOC32)
        for hunk in (0, 1):
            offsets = sorted(correcciones[hunk])
            if not offsets:
                continue
            salida += _largo(len(offsets))
            salida += _largo(hunk)
            for offset in offsets:
                salida += _largo(offset)
        salida += _largo(0)              # fin de la tabla
    salida += _largo(HUNK_END)

    salida += _largo(HUNK_BSS)
    salida += _largo(tamano_bss // 4)
    salida += _largo(HUNK_END)

    info = {
        "codigo": len(codigo),
        "bss": tamano_bss,
        "reloc_codigo": len(correcciones[0]),
        "reloc_bss": len(correcciones[1]),
        "archivo": len(salida),
    }
    return bytes(salida), info


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    destino = argv[2] if len(argv) > 2 else "juego"
    try:
        datos, info = convertir(argv[1])
    except ErrorHunk as error:
        sys.stderr.write("error: %s\n" % error)
        return 1
    with open(destino, "wb") as fh:
        fh.write(datos)
    print("ejecutable de Amiga: %s (%d KB de codigo y datos, %d KB de BSS, "
          "%d direcciones corregidas)"
          % (destino, info["codigo"] // 1024, info["bss"] // 1024,
             info["reloc_codigo"] + info["reloc_bss"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
