#!/usr/bin/env python3
"""Convierte el ELF del enlazador en un ejecutable de GEMDOS (.PRG, Atari ST).

El ejecutable del ST es mucho mas sencillo que el del Amiga: no son trozos
sueltos sino **un bloque seguido** que TOS carga donde le cabe, con una tabla
que dice que palabras largas hay que sumarle la direccion de carga.

    cabecera de 28 bytes
    TEXT      el codigo, las constantes y los datos con valor
    DATA      (aqui va vacio: el enlazador lo mete todo en TEXT)
    tabla de simbolos (aqui vacia)
    tabla de relocalizacion

La cabecera:

    +0   word   $601A, que es lo que mira TOS para saber que es un programa
    +2   long   cuanto ocupa TEXT
    +6   long   cuanto ocupa DATA
    +10  long   cuanto hay que reservar de BSS (TOS lo entrega a cero)
    +14  long   cuanto ocupa la tabla de simbolos
    +18  long   reservado
    +22  long   banderas
    +26  word   0 = trae tabla de relocalizacion

La tabla de relocalizacion es un invento de Digital Research que gasta un byte
por correccion: primero una palabra larga con el desplazamiento de la primera,
y luego un byte por cada una diciendo cuanto hay que avanzar desde la anterior.
Un byte no llega a 256, asi que el valor 1 significa "avanza 254 y sigue sin
corregir nada", y el 0 cierra la tabla.

    python3 hacer_prg.py juego.elf JUEGO.PRG
"""

from __future__ import annotations

import struct
import sys
from typing import Dict, List, Tuple

MAGIA = 0x601A
R_68K_32 = 1

SALTO = 254                      # lo que avanza el byte 1 de la tabla
LIMITE_PROG = 16 * 1024 * 1024   # ninguna direccion nuestra pasa de aqui


class ErrorPrg(Exception):
    pass


class Elf:
    """Lo justo de un ELF de 68000 (32 bits, big endian) para esto.

    Es el mismo lector que usa hacer_ejecutable.py para el Amiga; va copiado en
    los dos sitios para que cada proyecto generado se valga solo.
    """

    def __init__(self, datos: bytes):
        if datos[:4] != b"\x7fELF":
            raise ErrorPrg("esto no es un ELF")
        if datos[4] != 1 or datos[5] != 2:
            raise ErrorPrg("se esperaba un ELF de 32 bits y big endian (68000)")
        self.datos = datos
        (self.tipo, self.maquina) = struct.unpack_from(">HH", datos, 16)
        if self.maquina != 4:
            raise ErrorPrg("el ELF no es de 68000 (e_machine=%d)" % self.maquina)
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


def tabla_de_relocalizacion(offsets: List[int]) -> bytes:
    """Los desplazamientos a corregir, en el formato de GEMDOS."""
    if not offsets:
        return struct.pack(">I", 0)
    offsets = sorted(offsets)
    for offset in offsets:
        if offset % 2:
            raise ErrorPrg("hay una correccion en una direccion impar (0x%x); el "
                           "68000 no puede leer una palabra larga ahi" % offset)
    salida = bytearray(struct.pack(">I", offsets[0]))
    anterior = offsets[0]
    for offset in offsets[1:]:
        hueco = offset - anterior
        while hueco > 255:
            salida.append(1)                     # avanza 254 y sigue buscando
            hueco -= SALTO
        if hueco < 2:
            raise ErrorPrg("dos correcciones a menos de dos bytes (0x%x)" % offset)
        salida.append(hueco)
        anterior = offset
    salida.append(0)                             # fin de la tabla
    return bytes(salida)


def convertir(ruta_elf: str) -> Tuple[bytes, Dict[str, int]]:
    """ELF -> bytes del .PRG, mas unas cuantas cifras."""
    with open(ruta_elf, "rb") as fh:
        elf = Elf(fh.read())

    texto = elf.seccion(".text")
    if texto is None:
        raise ErrorPrg("el ELF no trae seccion .text")
    codigo = bytearray(elf.contenido(texto))
    while len(codigo) % 4:
        codigo.append(0)

    bss = elf.seccion(".bss")
    tamano_bss = bss["size"] if bss is not None else 0
    tamano_bss = (tamano_bss + 3) & ~3

    # Aqui, al reves que en el Amiga, TEXT y BSS van seguidos en memoria: el
    # enlazador ya coloca .bss detras de .text, asi que toda direccion absoluta
    # es un desplazamiento desde el principio y se corrige igual.
    correcciones: List[int] = []
    for direccion, tipo in elf.relocalizaciones(texto):
        offset = direccion - texto["addr"]
        if offset < 0 or offset + 4 > len(codigo):
            raise ErrorPrg("una relocalizacion cae fuera de .text (0x%x)" % direccion)
        if tipo != R_68K_32:
            continue                     # las relativas al PC no hay que tocarlas
        (valor, ) = struct.unpack_from(">I", codigo, offset)
        if valor >= LIMITE_PROG:
            raise ErrorPrg(
                "una direccion del codigo (0x%08x) no cae dentro del programa; "
                "revisa st.ld" % valor)
        correcciones.append(offset)

    tabla = tabla_de_relocalizacion(correcciones)

    salida = bytearray()
    salida += struct.pack(">H", MAGIA)
    salida += struct.pack(">I", len(codigo))     # TEXT
    salida += struct.pack(">I", 0)               # DATA (todo va en TEXT)
    salida += struct.pack(">I", tamano_bss)      # BSS
    salida += struct.pack(">I", 0)               # sin tabla de simbolos
    salida += struct.pack(">I", 0)               # reservado
    salida += struct.pack(">I", 0)               # banderas: nada especial
    salida += struct.pack(">H", 0)               # 0 = si hay relocalizacion
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
    destino = argv[2] if len(argv) > 2 else "JUEGO.PRG"
    try:
        datos, info = convertir(argv[1])
    except (OSError, ErrorPrg) as error:
        sys.stderr.write("error: %s\n" % error)
        return 1
    with open(destino, "wb") as fh:
        fh.write(datos)
    print("ejecutable de Atari ST: %s (%d KB de codigo y datos, %d KB de BSS, "
          "%d direcciones corregidas)"
          % (destino, info["texto"] // 1024, info["bss"] // 1024, info["reloc"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
