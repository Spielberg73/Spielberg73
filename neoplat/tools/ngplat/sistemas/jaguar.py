"""Atari Jaguar: 68000 a 13,3 MHz y un chip de video con lista de objetos.

Particularidades que se resuelven aqui:
  - no hay tiles ni sprites: hay un mapa de bits lineal de un byte por pixel y
    un "Object Processor" que compone objetos en cada linea de barrido
  - 256 colores a la vez, asi que las paletas del juego caben todas juntas
  - el cartucho lleva la pila y el punto de entrada en cart+$400 y cart+$404;
    sin eso la consola salta a la direccion 0
"""

from __future__ import annotations

import os
from typing import Dict, List

from .. import gfx, gfx_jaguar
from ..build import Build
from ..errors import ProjectError
from .base import Limites, Salida, Sistema, registrar

COLOR_HUD = 255                       # el ultimo color, para el marcador
MAX_TILES = 4096
MAPA_ANCHO, MAPA_ALTO = 704, 256      # el mapa de bits del escenario


class Jaguar(Sistema):
    nombre = "jaguar"
    titulo = "Atari Jaguar"
    cpu = "68000 a 13,3 MHz (+ GPU y DSP, sin usar)"
    pantalla = (320, 224)
    limites = Limites(colores_por_paleta=256, paletas=1, sprites=48, tiles=MAX_TILES,
                      colores_en_pantalla=256)
    archivos_motor = [
        ("include/np_types.h", "src/np_types.h"),
        ("include/np_game.h", "src/np_game.h"),
        ("include/np_world.h", "src/np_world.h"),
        ("core/np_world.c", "src/np_world.c"),
        ("core/np_aritmetica.c", "src/np_aritmetica.c"),
        ("jaguar/np_jaguar.h", "src/np_jaguar.h"),
        ("jaguar/np_video.c", "src/np_video.c"),
        ("jaguar/np_hud.c", "src/np_hud.c"),
        ("jaguar/np_sound.c", "src/np_sound.c"),
        ("jaguar/arranque.S", "src/arranque.S"),
        ("jaguar/main.c", "src/main.c"),
    ]
    extension_ejecutable = "j64"
    carpeta_salida = "rom"
    nombre_binario = "el cartucho"

    # --- colores -------------------------------------------------------

    def color(self, rgb):
        return gfx_jaguar.jaguar_color(rgb)

    def color_visible(self, rgb):
        return gfx_jaguar.jaguar_color_a_rgb(gfx_jaguar.jaguar_color(rgb))

    # --- empaquetado ----------------------------------------------------

    def preparar(self, build: Build) -> None:
        build.sistema = self
        banco = gfx_jaguar.BancoJaguar()

        paletas = [build.tileset.palette]
        paletas += [a.sheet.palette for a in build.actor_builds()]
        paletas += [c.palette for c in build.layers]
        unica = gfx_jaguar.fusionar_paletas(paletas, tope=COLOR_HUD)

        def remapear(tile, nombre):
            mapa = unica.asignacion[nombre]
            return [mapa.get(v, 0) for v in tile]

        # los dibujos van seguidos: el motor cuenta con ello para numerarlos
        build.tileset.first_tile = banco.cuantos
        for tile in build.tileset.tiles:
            banco.anadir(remapear(tile, build.tileset.palette.name), compartir=False)
        build.tileset.palette_index = 0

        for actor in build.actor_builds():
            actor.sheet.first_tile = banco.cuantos
            for tile in actor.sheet.tiles:
                banco.anadir(remapear(tile, actor.sheet.palette.name), compartir=False)
            actor.sheet.palette_index = 0

        # las capas de parallax todavia no se dibujan en la Jaguar
        for capa in build.layers:
            capa.tiles = [0] * len(capa.tiles)
            capa.palette_index = 0
            capa.dibujos = []

        if banco.cuantos > MAX_TILES:
            raise ProjectError(
                "los graficos ocupan %d dibujos de 16x16 y el limite en la Jaguar "
                "son %d" % (banco.cuantos, MAX_TILES),
                hint="usa menos dibujos distintos")

        fuente: Dict[str, int] = {}
        glifos = [[0] * 8]                        # el 0 es el hueco en blanco
        for i, char in enumerate(gfx.FONT_CHARS):
            glifos.append(_glifo_1bpp(gfx.font_glyph_pixels(char)))
            fuente[char] = i + 1

        colores = unica.palabras()
        colores[COLOR_HUD] = gfx_jaguar.jaguar_color((255, 255, 255))

        for nivel in build.levels:
            nivel.background = self.color(nivel.background_rgb)

        build.font = fuente
        build.hud_palette = 0
        build.paletas = [colores[i:i + 16] for i in range(0, 256, 16)]
        build.tile_gfx = [build.tileset.first_tile + t.index for t in build.tiles]
        build.info = {
            "banco": banco,
            "glifos": glifos,
            "colores": colores,
            "stats": {
                "dibujos_16x16": banco.cuantos,
                "bytes_dibujos": len(banco.tiles),
                "colores": len(unica.colores),
            },
            "cabecera": [
                "#define NP_TILE_COUNT %d" % banco.cuantos,
                "#define NP_FONT_COUNT %d" % len(glifos),
            ],
        }

    def comprobar(self, build: Build) -> List[str]:
        avisos: List[str] = []
        for nivel in build.levels:
            if nivel.layers:
                avisos.append(
                    "en Jaguar todavia no se dibujan las capas de parallax: el fondo "
                    "de '%s' se vera del color de fondo" % nivel.name)
                break
        if build.project.sound.musica or build.project.sound.efectos:
            avisos.append("en Jaguar todavia no hay sonido: el juego sale mudo")
        return avisos

    # --- generacion -----------------------------------------------------

    def generar(self, build: Build, rom_id: str) -> Salida:
        salida = Salida()
        banco: gfx_jaguar.BancoJaguar = build.info["banco"]
        nombre = _nombre_rom(build)

        salida.archivos["src/graficos.c"] = _graficos_c(build, banco)
        salida.archivos["jaguar.ld"] = _linker()
        salida.archivos["Makefile"] = _makefile(nombre)
        salida.archivos["hacer_rom.py"] = _hacer_rom()
        salida.resumen.append(
            "graficos: %d dibujos de 16x16 (%d KB, un byte por pixel)"
            % (banco.cuantos, len(banco.tiles) // 1024))
        salida.resumen.append(
            "colores:  %d de los 256 de la Jaguar (el 255 es el del marcador)"
            % build.info["stats"]["colores"])
        salida.resumen.append("cartucho: rom/%s.j64 (2 MB)" % nombre)
        return salida


def _nombre_rom(build: Build) -> str:
    trozos = [t for t in "".join(
        c if c.isalnum() else " " for c in build.project.title).split() if t]
    nombre = "".join(t[:1].upper() + t[1:].lower() for t in trozos)
    return nombre or "Juego"


def _glifo_1bpp(pixeles) -> List[int]:
    filas = []
    for y in range(8):
        bits = 0
        for x in range(8):
            if pixeles[y * 8 + x]:
                bits |= 0x80 >> x
        filas.append(bits)
    return filas


def _c_bytes(datos, por_linea=16) -> str:
    lineas = []
    for i in range(0, len(datos), por_linea):
        trozo = datos[i:i + por_linea]
        lineas.append("    " + ", ".join("0x%02x" % b for b in trozo) + ",")
    return "\n".join(lineas)


def _graficos_c(build: Build, banco: gfx_jaguar.BancoJaguar) -> str:
    colores = build.info["colores"]
    glifos = []
    for filas in build.info["glifos"]:
        glifos.extend(filas)
    partes = [
        "/* Archivo generado por ngplat: los dibujos, un byte por pixel. */",
        '#include "np_jaguar.h"',
        "",
        "/* El mapa de bits del escenario y la franja del marcador. Los lee el",
        " * chip de video por DMA, y tienen que empezar en un multiplo de 8. */",
        "uint8_t np_bitmap[NP_MAPA_ANCHO * NP_MAPA_ALTO] __attribute__((aligned(8)));",
        "uint8_t np_hud_bitmap[NP_SCREEN_W * NP_HUD_ALTO] __attribute__((aligned(8)));",
        "",
        "/* Cada dibujo son 16x16 bytes seguidos, uno por pixel. El indice 0 es",
        " * transparente: el chip lo salta al componer, asi que no hacen falta",
        " * mascaras. Alineados a 8 porque el chip los lee de frase en frase. */",
        "const uint8_t np_tile_data[NP_TILE_COUNT * %d] __attribute__((aligned(8))) = {"
        % gfx_jaguar.BYTES_POR_TILE,
        _c_bytes(bytes(banco.tiles)),
        "};",
        "",
        "/* Los 256 colores, en formato de la Jaguar: RRRRRBBBBBGGGGGG. */",
        "const uint16_t np_colores[256] = {",
    ]
    for i in range(0, 256, 8):
        partes.append("    " + ", ".join("0x%04x" % c for c in colores[i:i + 8]) + ",")
    partes += [
        "};",
        "",
        "/* Fuente del marcador: ocho bytes por caracter, un bit por pixel. */",
        "const uint8_t np_font_data[NP_FONT_COUNT * 8] = {",
        _c_bytes(glifos, por_linea=8),
        "};",
        "",
    ]
    return "\n".join(partes)


def _linker() -> str:
    return """/* Mapa de memoria de un cartucho de Jaguar.
 *
 * El cartucho se ve en $800000 y el programa empieza en $802000: los primeros
 * $2000 bytes son la cabecera, donde van la pila y el punto de entrada.
 * La DRAM son 2 MB en $000000; los primeros $4000 los reserva la consola.
 */
OUTPUT_ARCH(m68k)
ENTRY(_start)
MEMORY {
    rom (rx)  : ORIGIN = 0x802000, LENGTH = 2M - 0x2000
    ram (rwx) : ORIGIN = 0x004000, LENGTH = 0x1FC000
}
SECTIONS {
    .text 0x802000 : { KEEP(*(.entrada)) *(.text .text.*) *(.rodata .rodata.*) . = ALIGN(8); } > rom
    .data : { . = ALIGN(8); _data_start = .; *(.data .data.*) . = ALIGN(4); _data_end = .; } > ram AT > rom
    _data_load = LOADADDR(.data);
    .bss (NOLOAD) : { . = ALIGN(8); _bss_start = .; *(.bss .bss.*) *(COMMON) . = ALIGN(4); _bss_end = .; } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
"""


def _makefile(nombre: str) -> str:
    return """# Makefile generado por ngplat para la Atari Jaguar.
# Se reescribe en cada `ngplat compilar`: pon tus cambios en game.yaml.
#
# Solo hace falta un compilador de 68000; el GPU y el DSP de la Jaguar no se
# usan, asi que no hay que instalar el SDK de Atari.
#   apt install gcc-m68k-linux-gnu

# Con '?=' no valdria: make ya trae un CC por defecto y ganaria el suyo.
CC      := m68k-linux-gnu-gcc
OBJCOPY := m68k-linux-gnu-objcopy
PYTHON  ?= python3

# -fno-store-merging: sin el, gcc junta dos escrituras de un byte en una de dos
# y si cae en direccion impar el 68000 se para con un "address error".
CFLAGS := -m68000 -Os -fomit-frame-pointer -fno-builtin -ffreestanding \\
          -fno-store-merging -std=c99 -Wall -Wextra -Isrc
LDFLAGS := -nostdlib -nodefaultlibs -T jaguar.ld -Wl,--build-id=none

SRC := src/arranque.S src/main.c src/np_video.c src/np_hud.c src/np_sound.c \\
       src/np_world.c src/np_aritmetica.c src/gamedata.c src/graficos.c
ROM := rom/%s.j64

all: $(ROM)
\t@echo "cartucho listo: $(ROM)"

juego.elf: $(SRC) jaguar.ld
\t$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SRC)

juego.bin: juego.elf
\t$(OBJCOPY) -O binary $< $@

$(ROM): juego.bin hacer_rom.py
\t@mkdir -p rom
\t$(PYTHON) hacer_rom.py juego.bin $@

clean:
\trm -f juego.elf juego.bin $(ROM)

.PHONY: all clean
""" % nombre


def _hacer_rom() -> str:
    return '''"""Monta el cartucho de Jaguar a partir del binario enlazado.

La consola no arranca sola: lee la pila en cart+$400 y el punto de entrada en
cart+$404, y empieza a ejecutar ahi. Si esos ocho bytes estan a cero, salta a la
direccion 0 y no pasa nada (comprobado en el emulador).
"""

import struct
import sys

CARTUCHO = 0x800000
ENTRADA = 0x802000          # el programa empieza pasada la cabecera
PILA = 0x001FFFFC           # final de la DRAM
TAMANO = 2 * 1024 * 1024


def hacer_rom(binario: str, destino: str) -> int:
    with open(binario, "rb") as fh:
        codigo = fh.read()
    rom = bytearray(b"\\x00" * (ENTRADA - CARTUCHO))
    struct.pack_into(">II", rom, 0x400, PILA, ENTRADA)
    rom.extend(codigo)
    if len(rom) > TAMANO:
        raise SystemExit("el juego ocupa %d bytes y el cartucho son %d"
                         % (len(rom), TAMANO))
    rom.extend(b"\\x00" * (TAMANO - len(rom)))
    with open(destino, "wb") as fh:
        fh.write(bytes(rom))
    print("cartucho de Jaguar: %s (%d KB, %d KB de programa)"
          % (destino, len(rom) // 1024, len(codigo) // 1024))
    return 0


if __name__ == "__main__":
    sys.exit(hacer_rom(sys.argv[1], sys.argv[2]))
'''


registrar(Jaguar())
