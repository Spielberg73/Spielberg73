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

    python3 hacer_ejecutable.py juego.elf juego [KB_libres]

El tercer argumento es lo que deja libre el Amiga al que apunta el juego, que
sale de `amiga_ram:` en el game.yaml. Si el ejecutable no cabe, esto para: un
disquete que arranca y no carga el juego es el fallo mas caro del Amiga, porque
desde fuera no se distingue de un disquete roto.
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


A500_LIBRE = 190        # KB de RAM chip que deja libres el sistema


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    destino = argv[2] if len(argv) > 2 else "juego"
    libre = int(argv[3]) if len(argv) > 3 else A500_LIBRE
    try:
        datos, info = convertir(argv[1])
    except ErrorHunk as error:
        sys.stderr.write("error: %s\n" % error)
        return 1
    kb = (info["codigo"] + info["bss"]) // 1024
    print("ejecutable de Amiga: %s (%d KB de codigo y datos, %d KB de BSS, "
          "%d direcciones corregidas)"
          % (destino, info["codigo"] // 1024, info["bss"] // 1024,
             info["reloc_codigo"] + info["reloc_bss"]))
    # Todo esto -codigo, datos y BSS- lo reserva AmigaDOS en RAM chip, que es la
    # unica a la que llegan el copper, el blitter y Paula. En un A500 de 512 KB
    # lo que queda libre despues del sistema son unos 190, y pasado eso el
    # disquete arranca, el sistema no puede cargar el juego y en la pantalla se
    # queda el escritorio con un mensaje que no ayuda: unas veces "not enough
    # memory available" y otras "file is not executable", que es el mismo
    # problema con dos nombres. Esta medido en un A500 emulado: con 189 KB
    # arranca y con 209 no, y los mismos 209 arrancan con un mega.
    #
    # Por eso esto **para** en vez de avisar. Un aviso en mitad de un `make` de
    # cincuenta lineas no lo lee nadie, y lo que hay al otro lado es un disquete
    # que no se distingue de uno roto. Quien quiera el ejecutable igualmente
    # sube `amiga_ram:` en el game.yaml y vuelve a compilar: son diez segundos,
    # y asi queda escrito a que maquina apunta el juego.
    #
    # La comprobacion va **antes** de escribir el archivo, y no por elegancia:
    # si el ejecutable se dejara en disco y luego fallara, `make` lo veria mas
    # nuevo que el .elf en la siguiente pasada, se lo saltaria y montaria el
    # disquete con el juego que no cabe.
    if kb > libre:
        sys.stderr.write(
            "error: el juego ocupa %d KB de RAM chip y en esa maquina caben "
            "unos %d.\n"
            "       Sube 'amiga_ram:' en game.yaml (512K, 1M, 2M) para "
            "apuntar a un Amiga\n"
            "       con mas memoria, o quita dibujos, que es lo que mas "
            "ocupa.\n" % (kb, libre))
        return 1
    with open(destino, "wb") as fh:
        fh.write(datos)
    if libre > A500_LIBRE and kb <= A500_LIBRE:
        print("nota   cabe de sobra: %d KB de los %d de esa maquina, y ademas "
              "entra en un A500 de 512 KB (caben %d)"
              % (kb, libre, A500_LIBRE))
    else:
        print("memoria: %d KB de los %d que deja libres esa maquina" % (kb, libre))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
