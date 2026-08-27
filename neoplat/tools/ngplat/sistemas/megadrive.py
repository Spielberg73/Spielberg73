"""Mega Drive (Sega Genesis): 68000 a 7,6 MHz, dos planos con scroll y PSG.

Comparada con la Neo Geo se lo pone mas facil al motor en unas cosas y mas
dificil en otras:

  + tiene planos de fondo de verdad, con scroll por hardware, asi que el
    escenario y el parallax no gastan sprites
  + el PSG lo escribe el propio 68000: no hace falta codigo de Z80
  - solo hay **4 paletas de 16 colores** para todo el juego, asi que las
    paletas de los dibujos se fusionan aqui
  - los planos son de 64x64 celdas (512x512 px): el escenario se va
    reescribiendo por columnas segun avanza la camara
"""

from __future__ import annotations

from typing import Dict, List

from .. import gfx, gfx_md
from ..build import Build
from ..errors import ProjectError
from .. import md_pcm
from ..sonido import periodo_psg, tabla_de_muestras_c
from .base import Limites, Salida, Sistema, registrar

MAX_TILES = 1344          # lo que cabe en la VRAM antes de la tabla de sprites
PCM_MAXIMO = 64 * 1024    # por efecto; la ROM crece sola hasta la potencia de dos


class MegaDrive(Sistema):
    nombre = "megadrive"
    toca_muestras = True          # el Z80 se las da al DAC del YM2612
    titulo = "Sega Mega Drive / Genesis"
    cpu = "68000 a 7,6 MHz"
    pantalla = (320, 224)
    limites = Limites(colores_por_paleta=16, paletas=4, sprites=80,
                      tiles=MAX_TILES, colores_en_pantalla=64)
    archivos_motor = [
        ("include/np_types.h", "src/np_types.h"),
        ("include/np_game.h", "src/np_game.h"),
        ("include/np_world.h", "src/np_world.h"),
        ("include/np_sonido.h", "src/np_sonido.h"),
        ("core/np_world.c", "src/np_world.c"),
        ("core/np_aritmetica.c", "src/np_aritmetica.c"),
        ("megadrive/np_md.h", "src/np_md.h"),
        ("megadrive/np_video.c", "src/np_video.c"),
        ("megadrive/np_hud.c", "src/np_hud.c"),
        ("megadrive/np_sound.c", "src/np_sound.c"),
        ("megadrive/main.c", "src/main.c"),
        ("megadrive/arranque.c", "src/arranque.c"),
        ("megadrive/megadrive.ld", "megadrive.ld"),
    ]
    extension_ejecutable = "bin"
    nombre_binario = "el cartucho"
    notas = [
        "parallax: una capa, en el plano B del VDP",
        "sonido:   PSG SN76489, tres cuadradas; muestras por el DAC del YM2612",
    ]

    # --- colores -------------------------------------------------------

    def color(self, rgb):
        return gfx_md.md_color(rgb)

    def color_visible(self, rgb):
        return gfx_md.md_color_a_rgb(gfx_md.md_color(rgb))

    # --- empaquetado ---------------------------------------------------

    def preparar(self, build: Build) -> None:
        build.sistema = self
        vram = gfx_md.VramMD()

        # 1) todas las paletas del juego se meten en las 4 del VDP
        paletas = [build.tileset.palette]
        paletas += [a.sheet.palette for a in build.actor_builds()]
        paletas += [c.palette for c in build.layers]
        paletas.append(gfx.hud_palette())
        reparto = gfx_md.repartir_paletas(paletas)

        def remapear(tile, nombre):
            mapa = reparto.asignacion[nombre][1]
            return [mapa.get(v, 0) for v in tile]

        # 2) los dibujos, ya con los colores recolocados
        base_tileset = None
        for tile in build.tileset.tiles:
            indice = vram.anadir_16(remapear(tile, build.tileset.palette.name))
            if base_tileset is None:
                base_tileset = indice
        build.tileset.first_tile = base_tileset or 0
        build.tileset.palette_index = reparto.asignacion[build.tileset.palette.name][0]

        for actor in build.actor_builds():
            primero = None
            for tile in actor.sheet.tiles:
                indice = vram.anadir_16(remapear(tile, actor.sheet.palette.name))
                if primero is None:
                    primero = indice
            actor.sheet.first_tile = primero or 0
            actor.sheet.palette_index = reparto.asignacion[actor.sheet.palette.name][0]

        for capa in build.layers:
            numeros = []
            for dibujo in capa.dibujos:
                numeros.append(vram.anadir_16(remapear(dibujo, capa.palette.name)))
            capa.tiles = [numeros[i] for i in capa.tiles]
            capa.palette_index = reparto.asignacion[capa.palette.name][0]
            capa.dibujos = []

        # 3) la fuente del marcador: tiles de 8x8, uno por caracter
        fuente_paleta = reparto.asignacion["hud"][0]
        mapa_hud = reparto.asignacion["hud"][1]
        primera_fuente = vram.cuantos
        indices_fuente: Dict[str, int] = {}
        vram.anadir([0] * 64, compartir=False)          # el 0 es el hueco en blanco
        for i, char in enumerate(gfx.FONT_CHARS):
            pixeles = [mapa_hud.get(v, 0) for v in gfx.font_glyph_pixels(char)]
            vram.anadir(pixeles, compartir=False)
            indices_fuente[char] = i + 1

        if vram.cuantos > MAX_TILES:
            raise ProjectError(
                "los graficos ocupan %d tiles y en la Mega Drive caben %d"
                % (vram.cuantos, MAX_TILES),
                hint="usa menos dibujos distintos o capas de fondo mas pequenas",
            )

        # el color de fondo de cada nivel, en el formato de esta maquina
        for nivel in build.levels:
            nivel.background = self.color(nivel.background_rgb)

        build.font = indices_fuente
        build.hud_palette = fuente_paleta
        build.paletas = [gfx_md.palabras_de_paleta(p) for p in reparto.paletas]
        build.tile_gfx = [build.tileset.first_tile + t.index * 4 for t in build.tiles]
        build.info = {
            "vram": vram,
            "font_first": primera_fuente,
            "stats": {
                "tiles_8x8": vram.cuantos,
                "bytes_tiles": len(vram.tiles),
            },
            "cabecera": [
                "#define NP_TILE_WORDS %d" % (len(vram.tiles) // 2),
                "#define NP_FONT_FIRST_TILE %d" % primera_fuente,
                "extern const uint16_t np_tile_data[NP_TILE_WORDS];",
                "extern const uint16_t np_font_first_tile;",
            ],
        }

    def comprobar(self, build: Build) -> List[str]:
        avisos: List[str] = []
        for nivel in build.levels:
            if nivel.height > 32:
                self.error(
                    "el nivel '%s' tiene %d casillas de alto y en la Mega Drive el "
                    "plano de fondo llega a 32" % (nivel.name, nivel.height),
                    "haz los niveles mas bajos y mas largos",
                )
        for nivel in build.levels:
            if len(nivel.layers) > 1:
                avisos.append(
                    "en Mega Drive solo se dibuja una capa de fondo: en '%s' se usara '%s'"
                    % (nivel.name, build.layers[nivel.layers[0]].name)
                )
                break
        entidades = max((len(n.spawns) for n in build.levels), default=0)
        if entidades > 40:
            avisos.append(
                "hay niveles con %d enemigos y objetos; en Mega Drive caben 80 sprites "
                "en pantalla y cada actor gasta uno o dos" % entidades
            )
        return avisos

    # --- generacion ----------------------------------------------------

    def generar(self, build: Build, rom_id: str) -> Salida:
        salida = Salida()
        vram: gfx_md.VramMD = build.info["vram"]

        salida.archivos["src/graficos.c"] = _graficos_c(build, vram)
        salida.archivos["src/sonido.c"] = _sonido_c(build)
        salida.archivos["Makefile"] = _makefile(build)
        salida.archivos["arreglar_rom.py"] = _arreglar_rom_py()
        salida.resumen.append("graficos: %d tiles de 8x8 (%d KB en la ROM)"
                              % (vram.cuantos, len(vram.tiles) // 1024))
        salida.resumen.append("paletas:  4 de 16 colores (las del juego se han fusionado)")
        if build.pcm_bytes:
            salida.resumen.append(
                "muestras: %d efectos digitales a %d Hz por el Z80 (%d KB en la ROM)"
                % (sum(1 for e in build.project.sound.efectos.values() if e.digital),
                   md_pcm.RITMO, (build.pcm_bytes + 1023) // 1024))
        return salida


def _c_array(valores, por_linea=12, formato="0x%04x"):
    lineas = []
    for i in range(0, len(valores), por_linea):
        lineas.append("    " + ", ".join(formato % v for v in valores[i:i + por_linea]) + ",")
    return "\n".join(lineas)


def _graficos_c(build: Build, vram: gfx_md.VramMD) -> str:
    palabras = []
    datos = bytes(vram.tiles)
    for i in range(0, len(datos), 2):
        palabras.append((datos[i] << 8) | datos[i + 1])
    partes = [
        "/* Archivo generado por ngplat: los dibujos, ya en formato del VDP. */",
        '#include "gamedata.h"',
        "",
        "/* Cada tile son 8x8 pixeles de 4 bits: 16 palabras. */",
        "const uint16_t np_tile_data[NP_TILE_WORDS] = {",
        _c_array(palabras),
        "};",
        "",
        "const uint16_t np_font_first_tile = %d;" % build.info["font_first"],
        "",
    ]
    return "\n".join(partes)


def _secuencia_c(nombre: str, pasos) -> List[str]:
    lineas = ["static const NpSndPaso %s[] = {" % nombre]
    for paso in pasos:
        duracion = max(1, int(paso.duracion))
        volumen = (paso.volumen & 0x0F) | (0x80 if paso.ruido else 0)
        periodo = periodo_psg(paso.frecuencia)
        while duracion > 0:
            trozo = min(255, duracion)
            lineas.append("    { %d, %d, 0x%02x }," % (periodo, trozo, volumen))
            duracion -= trozo
    lineas.append("    { 0, 0, 0 }")
    lineas.append("};")
    return lineas


def _sonido_c(build: Build) -> str:
    from ..sonido import EVENTOS
    sonido = build.project.sound
    efectos = [n for n in EVENTOS if n in sonido.efectos]
    partes = [
        "/* Archivo generado por ngplat: la musica y los efectos, ya en periodos",
        " * del PSG de la Mega Drive. */",
        '#include "np_sonido.h"',
        "",
    ]
    for i, nombre in enumerate(efectos):
        partes.extend(_secuencia_c("np_sfx%d" % i, sonido.efectos[nombre].pasos))
        partes.append("")
    for i, nombre in enumerate(build.music_order):
        tema = sonido.musica[nombre]
        for p in range(2):
            pista = tema.pistas[p] if p < len(tema.pistas) else []
            partes.extend(_secuencia_c("np_mus%d_%d" % (i, p), pista))
        partes.append("")

    partes.append("const NpSndPaso *const np_snd_efectos[] = {")
    if efectos:
        partes.append("    " + ", ".join("np_sfx%d" % i for i in range(len(efectos))))
    else:
        partes.append("    0")
    partes.append("};")
    partes.append("const NpSndPaso *const np_snd_musica[] = {")
    if build.music_order:
        entradas = []
        for i in range(len(build.music_order)):
            entradas.append("np_mus%d_0" % i)
            entradas.append("np_mus%d_1" % i)
        partes.append("    " + ", ".join(entradas))
    else:
        partes.append("    0, 0")
    partes.append("};")
    partes.append("const uint16_t np_snd_efecto_count = %d;" % len(efectos))
    partes.append("const uint16_t np_snd_musica_count = %d;" % len(build.music_order))
    partes.append("")
    # Las muestras las toca el Z80 (tools/ngplat/md_pcm.py), que no interpola
    # nada: el WAV viene ya a la frecuencia que da su bucle.
    lineas, bytes_pcm = tabla_de_muestras_c(
        [sonido.efectos[n] for n in efectos], md_pcm.RITMO, 60,
        lambda ritmo: 0, maximo=PCM_MAXIMO, sin_signo=True)
    partes.extend(lineas)
    build.pcm_bytes = bytes_pcm

    partes.append("")
    partes.append("/* El driver del Z80 que toca las muestras. El 68000 lo copia")
    partes.append("   a la RAM del Z80 al arrancar. */")
    codigo, _etiquetas = md_pcm.generar()
    partes.append("const uint8_t np_z80_pcm[] = {")
    partes.extend(_c_bytes_z80(codigo))
    partes.append("};")
    partes.append("const uint16_t np_z80_pcm_largo = %d;" % len(codigo))
    partes.append("")
    return "\n".join(partes)


def _c_bytes_z80(datos: bytes, por_linea: int = 16):
    return ["    " + ", ".join("0x%02x" % b for b in datos[i:i + por_linea]) + ","
            for i in range(0, len(datos), por_linea)]


def _makefile(build: Build) -> str:
    return """# Makefile generado por ngplat para "%s" (Mega Drive).
# Se reescribe en cada `ngplat compilar`: pon tus cambios en game.yaml.
#
# Necesita un compilador de 68000. Vale cualquiera de estos:
#   m68k-elf-gcc          (el habitual para consolas)
#   m68k-linux-gnu-gcc    (el paquete gcc-m68k-linux-gnu de Debian/Ubuntu)

# make trae su propio CC por defecto, asi que solo se cambia si nadie lo ha puesto
ifeq ($(origin CC), default)
CC := $(shell which m68k-elf-gcc 2>/dev/null || which m68k-linux-gnu-gcc 2>/dev/null)
endif
ifeq ($(CC),)
$(error no encuentro un compilador de 68000: instala gcc-m68k-linux-gnu o m68k-elf-gcc)
endif
OBJCOPY ?= $(patsubst %%-gcc,%%-objcopy,$(CC))
PYTHON  ?= python3

# -fno-store-merging: sin el, gcc junta dos escrituras de un byte seguidas en
# una sola de dos bytes, y si cae en una direccion impar el 68000 se para con
# un "address error". Las pruebas del kit comprueban que no quede ninguna.
CFLAGS  := -m68000 -Os -fomit-frame-pointer -fno-builtin -ffreestanding \\
           -fno-store-merging -std=c99 -Wall -Wextra -Isrc
# -nodefaultlibs: la libgcc de un compilador de 68k para Linux esta hecha para
# 68020 y lleva instrucciones que el 68000 no tiene; las rutinas de multiplicar
# y dividir las pone src/np_aritmetica.c.
LDFLAGS := -nostdlib -nodefaultlibs -T megadrive.ld -Wl,--build-id=none

SRC := src/arranque.c src/main.c src/np_video.c src/np_hud.c src/np_sound.c \\
       src/np_world.c src/np_aritmetica.c src/gamedata.c src/graficos.c \\
       src/sonido.c
OBJ := $(SRC:.c=.o)
ROM := rom/juego.bin

all: $(ROM)
	@echo "cartucho listo: $(ROM)"

%%.o: %%.c
	$(CC) $(CFLAGS) -c $< -o $@

juego.elf: $(OBJ)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJ)

$(ROM): juego.elf
	@mkdir -p rom
	$(OBJCOPY) -O binary $< $@
	$(PYTHON) arreglar_rom.py $@ "%s"

# Con un emulador instalado (por ejemplo BlastEm o Gens), `make run` lo arranca.
EMU ?= blastem
run: all
	$(EMU) $(ROM)

clean:
	rm -f $(OBJ) juego.elf $(ROM)

.PHONY: all run clean
""" % (build.project.title, build.project.title)


def _arreglar_rom_py() -> str:
    return '''#!/usr/bin/env python3
"""Deja el cartucho listo: tamano, nombre y suma de control.

La cabecera de un cartucho de Mega Drive lleva la direccion final de la ROM y
una suma de control que solo se pueden calcular cuando el binario ya esta
hecho. Esto lo rellena. No necesita nada instalado.

    python3 arreglar_rom.py rom/juego.bin "MI JUEGO"
"""

import sys


def arreglar(ruta, titulo=""):
    with open(ruta, "rb") as fh:
        datos = bytearray(fh.read())

    # el tamano se redondea a una potencia de dos (minimo 128 KB)
    tamano = 0x20000
    while tamano < len(datos):
        tamano *= 2
    datos.extend(b"\\x00" * (tamano - len(datos)))

    if titulo:
        nombre = titulo.upper()[:48].ljust(48).encode("ascii", "replace")
        datos[0x120:0x150] = nombre          # nombre nacional
        datos[0x150:0x180] = nombre          # nombre internacional

    datos[0x1A0:0x1A4] = (0).to_bytes(4, "big")
    datos[0x1A4:0x1A8] = (len(datos) - 1).to_bytes(4, "big")

    # la suma es la de todas las palabras a partir de $200
    suma = 0
    for i in range(0x200, len(datos), 2):
        suma = (suma + (datos[i] << 8) + datos[i + 1]) & 0xFFFF
    datos[0x18E:0x190] = suma.to_bytes(2, "big")

    with open(ruta, "wb") as fh:
        fh.write(datos)
    return len(datos), suma


if __name__ == "__main__":
    ruta = sys.argv[1]
    titulo = sys.argv[2] if len(sys.argv) > 2 else ""
    tamano, suma = arreglar(ruta, titulo)
    print("ROM de %d KB, suma de control 0x%04x" % (tamano // 1024, suma))
'''


registrar(MegaDrive())
