"""Commodore Amiga (OCS/ECS, un A500 basta): 68000 a 7 MHz, blitter y Paula.

Es la mas distinta de las tres maquinas. No tiene tiles ni un plano de fondo
con scroll por celdas: tiene un **mapa de bits** que se puede mover entero por
hardware y un **blitter** que copia trozos de memoria a toda velocidad. Asi que
aqui:

  - todos los dibujos del juego se guardan entrelazados en 5 bitplanes, con su
    mascara al lado para poder recortarlos sobre el fondo
  - las paletas del proyecto se funden en **una sola de 32 colores**, que es lo
    que muestra el Amiga de una vez (el ultimo se reserva para el marcador)
  - el sonido sale por Paula con una onda cuadrada de dos bytes a la que se le
    cambia el periodo: las mismas notas que en las otras dos maquinas
  - el resultado no es un cartucho sino un **disquete arrancable** (.adf): el
    ejecutable lo hace hunk.py a partir del ELF del enlazador y adf.py lo mete
    en un disco de 880 KB con su bootblock y su sistema de ficheros
"""

from __future__ import annotations

import os
from typing import Dict, List

from .. import gfx, gfx_amiga
from ..build import Build
from ..errors import ProjectError
from ..sonido import periodo_paula
from .base import Limites, Salida, Sistema, registrar

ALTO_MAX_TILES = gfx_amiga.TILE_PX          # el mapa de bits son 256 lineas
COLOR_HUD = 31                              # el ultimo color, reservado
MAX_COLORES_JUEGO = COLOR_HUD               # los otros 31 son del juego
MAX_TILES = 1024                            # 160 KB de dibujos: de sobra en chip


class Amiga(Sistema):
    nombre = "amiga"
    titulo = "Commodore Amiga (OCS/ECS)"
    cpu = "68000 a 7 MHz"
    pantalla = (320, 224)
    limites = Limites(colores_por_paleta=16, paletas=1, sprites=0,
                      tiles=MAX_TILES, colores_en_pantalla=gfx_amiga.COLORES)
    archivos_motor = [
        ("include/np_types.h", "src/np_types.h"),
        ("include/np_game.h", "src/np_game.h"),
        ("include/np_world.h", "src/np_world.h"),
        ("include/np_sonido.h", "src/np_sonido.h"),
        ("core/np_world.c", "src/np_world.c"),
        ("core/np_aritmetica.c", "src/np_aritmetica.c"),
        ("amiga/np_amiga.h", "src/np_amiga.h"),
        ("amiga/np_video.c", "src/np_video.c"),
        ("amiga/np_hud.c", "src/np_hud.c"),
        ("amiga/np_sound.c", "src/np_sound.c"),
        ("amiga/main.c", "src/main.c"),
        ("amiga/arranque.c", "src/arranque.c"),
        ("amiga/amiga.ld", "amiga.ld"),
    ]
    extension_ejecutable = ""
    carpeta_salida = "disco"       # una carpeta que se copia tal cual al disquete

    # --- colores -------------------------------------------------------

    def color(self, rgb):
        return gfx_amiga.amiga_color(rgb)

    def color_visible(self, rgb):
        return gfx_amiga.amiga_color_a_rgb(gfx_amiga.amiga_color(rgb))

    # --- empaquetado ---------------------------------------------------

    def preparar(self, build: Build) -> None:
        build.sistema = self
        banco = gfx_amiga.BancoAmiga()

        # 1) las paletas del juego caben todas en los 32 colores del Amiga.
        #    Las capas de parallax se quedan fuera: en el Amiga todavia no se
        #    dibujan (ver comprobar), asi que ni gastan colores ni memoria.
        paletas = [build.tileset.palette]
        paletas += [a.sheet.palette for a in build.actor_builds()]
        unica = gfx_amiga.fusionar_paletas(paletas)
        if len(unica.colores) > MAX_COLORES_JUEGO:
            raise ProjectError(
                "los graficos usan %d colores distintos y en el Amiga quedan %d "
                "(el ultimo es del marcador)"
                % (len(unica.colores), MAX_COLORES_JUEGO),
                hint="repite colores entre dibujos o quita alguna capa de fondo",
            )

        def remapear(tile, nombre):
            mapa = unica.asignacion[nombre]
            return [mapa.get(v, 0) for v in tile]

        # 2) los dibujos, ya entrelazados y con su mascara
        #    (sin compartir: el motor cuenta con que van seguidos)
        build.tileset.first_tile = banco.cuantos
        for tile in build.tileset.tiles:
            banco.anadir(remapear(tile, build.tileset.palette.name), compartir=False)
        build.tileset.palette_index = 0

        for actor in build.actor_builds():
            actor.sheet.first_tile = banco.cuantos
            for tile in actor.sheet.tiles:
                banco.anadir(remapear(tile, actor.sheet.palette.name), compartir=False)
            actor.sheet.palette_index = 0

        for capa in build.layers:
            capa.tiles = [0] * len(capa.tiles)
            capa.palette_index = 0
            capa.dibujos = []

        if banco.cuantos > MAX_TILES:
            raise ProjectError(
                "los graficos ocupan %d dibujos de 16x16 y el limite del Amiga "
                "en NeoPlat son %d" % (banco.cuantos, MAX_TILES),
                hint="usa menos dibujos distintos o capas de fondo mas pequenas",
            )

        # 3) la fuente del marcador: 8x8 en un solo bit por pixel
        fuente: Dict[str, int] = {}
        glifos = [[0] * 8]                       # el 0 es el hueco en blanco
        for i, char in enumerate(gfx.FONT_CHARS):
            glifos.append(_glifo_1bpp(gfx.font_glyph_pixels(char)))
            fuente[char] = i + 1

        colores = unica.palabras()
        colores[COLOR_HUD] = gfx_amiga.amiga_color((255, 255, 255))

        # el color de fondo de cada nivel, en el formato de esta maquina
        for nivel in build.levels:
            nivel.background = self.color(nivel.background_rgb)

        build.font = fuente
        build.hud_palette = 0
        build.paletas = [colores[0:16], colores[16:32]]
        build.tile_gfx = [build.tileset.first_tile + t.index for t in build.tiles]
        build.info = {
            "banco": banco,
            "glifos": glifos,
            "colores": colores,
            "stats": {
                "dibujos_16x16": banco.cuantos,
                "bytes_dibujos": len(banco.tiles),
                "bytes_mascaras": len(banco.mascaras),
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
            if nivel.height > ALTO_MAX_TILES:
                self.error(
                    "el nivel '%s' tiene %d casillas de alto y en el Amiga el mapa "
                    "de bits llega a %d" % (nivel.name, nivel.height, ALTO_MAX_TILES),
                    "haz los niveles mas bajos y mas largos",
                )
        for nivel in build.levels:
            if nivel.layers:
                avisos.append(
                    "en Amiga todavia no se dibujan las capas de parallax: el fondo "
                    "de '%s' se vera del color de fondo" % nivel.name)
                break
        return avisos

    # --- generacion ----------------------------------------------------

    def generar(self, build: Build, rom_id: str) -> Salida:
        salida = Salida()
        banco: gfx_amiga.BancoAmiga = build.info["banco"]

        salida.archivos["src/graficos.c"] = _graficos_c(build, banco)
        salida.archivos["src/sonido.c"] = _sonido_c(build)
        nombre = _nombre_ejecutable(build)
        salida.archivos["Makefile"] = _makefile(build, nombre,
                                                _etiqueta_disco(build.project.title))
        salida.archivos["hacer_ejecutable.py"] = _fuente_de("hunk.py")
        salida.archivos["hacer_adf.py"] = _fuente_de("adf.py")
        salida.resumen.append(
            "graficos: %d dibujos de 16x16 (%d KB de dibujos y %d KB de mascaras)"
            % (banco.cuantos, len(banco.tiles) // 1024, len(banco.mascaras) // 1024))
        salida.resumen.append(
            "colores:  %d de los 32 del Amiga (el 31 es el del marcador)"
            % build.info["stats"]["colores"])
        salida.resumen.append(
            "disquete: disco/%s.adf (880 KB, arranca solo en cualquier Amiga)" % nombre)
        return salida


def _nombre_ejecutable(build: Build) -> str:
    """El titulo del juego, hecho un nombre de archivo de AmigaDOS."""
    trozos = [t for t in "".join(
        c if c.isalnum() else " " for c in build.project.title).split() if t]
    nombre = "".join(t[:1].upper() + t[1:].lower() for t in trozos)
    return nombre or "Juego"


def _glifo_1bpp(pixeles) -> List[int]:
    """8x8 indices de paleta -> ocho bytes, un bit por pixel."""
    filas = []
    for y in range(8):
        bits = 0
        for x in range(8):
            if pixeles[y * 8 + x]:
                bits |= 1 << (7 - x)
        filas.append(bits)
    return filas


def _c_bytes(datos, por_linea=16) -> str:
    lineas = []
    for i in range(0, len(datos), por_linea):
        trozo = datos[i:i + por_linea]
        lineas.append("    " + ", ".join("0x%02x" % b for b in trozo) + ",")
    return "\n".join(lineas)


def _graficos_c(build: Build, banco: gfx_amiga.BancoAmiga) -> str:
    colores = build.info["colores"]
    glifos = []
    for filas in build.info["glifos"]:
        glifos.extend(filas)
    partes = [
        "/* Archivo generado por ngplat: los dibujos, ya en bitplanes del Amiga. */",
        '#include "np_amiga.h"',
        "",
        "/* El mapa de bits y la franja del marcador. Estan sin inicializar a",
        " * proposito: asi van al hunk de BSS, que AmigaDOS reserva en RAM chip",
        " * y entrega puesto a cero. */",
        "uint8_t np_bitmap[NP_MAPA_ALTO * NP_PASO_FILA];",
        "uint8_t np_hud_bitmap[NP_HUD_ALTO * NP_HUD_PASO];",
        "",
        "/* Cada dibujo son 16 filas x 5 bitplanes x 2 bytes = 160 bytes.",
        " * Las dos palabras de mas del final son para el blitter: al desplazar un",
        " * dibujo lee una palabra por detras de la ultima fila. */",
        "const uint8_t np_tile_data[NP_TILE_COUNT * %d + 4] = {"
        % gfx_amiga.BYTES_POR_TILE,
        _c_bytes(bytes(banco.tiles)),
        "};",
        "",
        "/* Y su mascara: un bit por pixel, 1 donde el dibujo tapa el fondo,",
        " * repetida para los cinco bitplanes. */",
        "const uint8_t np_tile_mask[NP_TILE_COUNT * %d + 4] = {"
        % gfx_amiga.BYTES_MASCARA,
        _c_bytes(bytes(banco.mascaras)),
        "};",
        "",
        "/* Los 32 colores de la pantalla, en formato del Amiga (4 bits por canal). */",
        "const uint16_t np_colores[32] = {",
        "    " + ", ".join("0x%04x" % c for c in colores[:16]) + ",",
        "    " + ", ".join("0x%04x" % c for c in colores[16:32]) + ",",
        "};",
        "",
        "/* Fuente del marcador: ocho bytes por caracter. */",
        "const uint8_t np_font_data[NP_FONT_COUNT * 8] = {",
        _c_bytes(glifos, por_linea=8),
        "};",
        "",
    ]
    return "\n".join(partes)


def _secuencia_c(nombre: str, pasos) -> List[str]:
    lineas = ["static const NpSndPaso %s[] = {" % nombre]
    for paso in pasos:
        duracion = max(1, int(paso.duracion))
        volumen = (paso.volumen & 0x0F) | (0x80 if paso.ruido else 0)
        # una onda cuadrada de dos bytes: periodo = reloj / (2 * hercios)
        periodo = periodo_paula(paso.frecuencia, muestras=2)
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
        " * de Paula (Amiga). */",
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
    partes.append("    " + (", ".join("np_sfx%d" % i for i in range(len(efectos)))
                            if efectos else "0"))
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
    return "\n".join(partes)


def _makefile(build: Build, nombre: str, etiqueta: str) -> str:
    return """# Makefile generado por ngplat para "%s" (Amiga).
# Se reescribe en cada `ngplat compilar`: pon tus cambios en game.yaml.
#
# Necesita un compilador de 68000. Vale cualquiera de estos:
#   m68k-amigaos-gcc      (el del bebbo/amiga-gcc, si lo tienes)
#   m68k-elf-gcc
#   m68k-linux-gnu-gcc    (el paquete gcc-m68k-linux-gnu de Debian/Ubuntu)
#
# El enlazador saca un ELF; hacer_ejecutable.py lo convierte en un ejecutable de
# AmigaDOS de verdad (hunks + tabla de relocalizacion, todo en RAM chip) y
# hacer_adf.py monta con el un disquete de 880 KB que arranca solo.

# make trae su propio CC por defecto, asi que solo se cambia si nadie lo ha puesto
ifeq ($(origin CC), default)
CC := $(shell which m68k-elf-gcc 2>/dev/null || which m68k-linux-gnu-gcc 2>/dev/null)
endif
ifeq ($(CC),)
$(error no encuentro un compilador de 68000: instala gcc-m68k-linux-gnu o m68k-elf-gcc)
endif
PYTHON ?= python3

# -fno-store-merging: sin el, gcc junta dos escrituras de un byte seguidas en
# una sola de dos bytes, y si cae en una direccion impar el 68000 se para con
# un "address error". Las pruebas del kit comprueban que no quede ninguna.
CFLAGS  := -m68000 -Os -fomit-frame-pointer -fno-builtin -ffreestanding \\
           -fno-store-merging -std=c99 -Wall -Wextra -Isrc
# -nodefaultlibs: la libgcc de un compilador de 68k para Linux esta hecha para
# 68020 y lleva instrucciones que el 68000 no tiene; las rutinas de multiplicar
# y dividir las pone src/np_aritmetica.c.
LDFLAGS := -nostdlib -nodefaultlibs -T amiga.ld -Wl,--emit-relocs -Wl,--build-id=none

SRC := src/arranque.c src/main.c src/np_video.c src/np_hud.c src/np_sound.c \\
       src/np_world.c src/np_aritmetica.c src/gamedata.c src/graficos.c \\
       src/sonido.c
OBJ := $(SRC:.c=.o)
JUEGO := disco/%s
ADF   := disco/%s.adf
DISCO := "%s"

all: $(ADF)
	@echo "disquete listo: $(ADF)"

%%.o: %%.c
	$(CC) $(CFLAGS) -c $< -o $@

juego.elf: $(OBJ)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJ)

$(JUEGO): juego.elf
	@mkdir -p disco
	$(PYTHON) hacer_ejecutable.py $< $@

# El .adf es la copia de un disquete: se mete en el emulador (o en un Gotek, o
# en un Amiga de verdad con ADF Blitz) y arranca solo, sin Workbench.
$(ADF): $(JUEGO) hacer_adf.py
	$(PYTHON) hacer_adf.py $@ $(DISCO) %s $(JUEGO)

# Con un emulador instalado, `make run` mete el disquete y enciende el Amiga.
EMU ?= fs-uae
run: all
	$(EMU) --floppy_drive_0=$(ADF)

clean:
	rm -f $(OBJ) juego.elf $(JUEGO) $(ADF)

.PHONY: all run clean
""" % (build.project.title, nombre, nombre, etiqueta, nombre)


def _fuente_de(modulo: str) -> str:
    """Copia un modulo del kit tal cual, para que el proyecto generado se valga solo."""
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        modulo)
    with open(ruta, "r", encoding="utf-8") as fh:
        return fh.read()


def _etiqueta_disco(titulo: str) -> str:
    """Nombre del volumen: AmigaDOS no admite ':' ni '/' y se queda en 30 letras."""
    limpio = "".join(c if (c.isalnum() or c in " -_") else " " for c in titulo)
    return " ".join(limpio.split())[:30].upper() or "NEOPLAT"


registrar(Amiga())
