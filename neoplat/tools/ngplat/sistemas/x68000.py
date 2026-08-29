"""Sharp X68000: 68000 a 10 MHz, chip de sprites y dos capas de fondo.

De las seis maquinas del kit es la que menos trabajo pide, y por una razon
concreta: los patrones del PCG son de **16x16**, justo el tamano de tile de
NeoPlat. En la Mega Drive hay que partir cada tile en cuatro de 8x8 y en la Neo
Geo el escenario se dibuja con columnas de sprites; aqui una casilla del nivel
es una casilla de la tabla de nombres.

El reparto de la pantalla:

  BG0      el escenario, con scroll por hardware
  BG1      la capa de parallax
  sprites  los actores (128, de 16x16)
  texto    el marcador, en el plano de texto, que asi no gasta ni un patron

El limite de verdad no son los sprites sino los **256 patrones** de la PCG RAM,
que se reparten entre los sprites y las dos capas.
"""

from __future__ import annotations

from typing import Dict, List

from .. import gfx
from .. import gfx_x68k
from ..build import Build
from ..errors import ProjectError
from ..paths import fuente_del_kit
from .base import Limites, Salida, Sistema, registrar

MAX_PATRONES = gfx_x68k.PATRONES     # los que caben en la PCG RAM
MAX_BLOQUES = gfx_x68k.BLOQUES       # bloques de paleta de 16 colores


class X68000(Sistema):
    nombre = "x68000"
    titulo = "Sharp X68000"
    cpu = "68000 a 10 MHz"
    pantalla = (320, 224)
    limites = Limites(colores_por_paleta=16, paletas=MAX_BLOQUES, sprites=128,
                      tiles=MAX_PATRONES, colores_en_pantalla=65536)
    archivos_motor = [
        ("include/np_types.h", "src/np_types.h"),
        ("include/np_game.h", "src/np_game.h"),
        ("include/np_world.h", "src/np_world.h"),
        ("core/np_world.c", "src/np_world.c"),
        ("core/np_aritmetica.c", "src/np_aritmetica.c"),
        ("x68000/np_x68k.h", "src/np_x68k.h"),
        ("x68000/np_video.c", "src/np_video.c"),
        ("x68000/np_hud.c", "src/np_hud.c"),
        ("x68000/np_sound.c", "src/np_sound.c"),
        ("x68000/main.c", "src/main.c"),
        ("x68000/arranque.S", "src/arranque.S"),
        ("x68000/x68000.ld", "x68000.ld"),
    ]
    extension_ejecutable = "X"
    carpeta_salida = "disco"
    nombre_binario = "el ejecutable"
    notas = [
        "sprites:  128 de 16x16, y el escenario va en capas aparte",
        "patrones: 256 en total, repartidos entre sprites y las dos capas",
        "parallax: una capa, con scroll por hardware",
        "sonido:   YM2151 (ocho canales de FM) y ADPCM; todavia en silencio",
    ]

    # --- colores -------------------------------------------------------

    def color(self, rgb):
        return gfx_x68k.x68k_color(rgb)

    def color_visible(self, rgb):
        return gfx_x68k.x68k_color_a_rgb(gfx_x68k.x68k_color(rgb))

    # --- empaquetado ---------------------------------------------------

    def preparar(self, build: Build) -> None:
        build.sistema = self
        banco = gfx_x68k.BancoX68k()

        # El escenario y los actores van seguidos y sin compartir: el motor
        # cuenta con que los fotogramas de una hoja estan uno detras de otro.
        banco.empaquetar_hoja(build.tileset)
        for actor in build.actor_builds():
            banco.empaquetar_hoja(actor.sheet)

        # Las capas de fondo si comparten: ahi se repite mucho el mismo dibujo.
        for capa in build.layers:
            capa.palette_index = banco.anadir_paleta(capa.palette)
            nuevos = [banco.anadir(d, compartir=True) for d in capa.dibujos]
            capa.tiles = [nuevos[i] for i in capa.tiles]
            capa.dibujos = []

        # El marcador va en el plano de texto, a un bit por pixel: no gasta
        # patrones, asi que la fuente se guarda aparte.
        fuente: Dict[str, int] = {}
        glifos = [[0] * 8]                       # el 0 es el hueco en blanco
        for i, char in enumerate(gfx.FONT_CHARS):
            glifos.append(_glifo_1bpp(gfx.font_glyph_pixels(char)))
            fuente[char] = i + 1

        for nivel in build.levels:
            nivel.background = self.color(nivel.background_rgb)

        build.font = fuente
        build.hud_palette = 0
        build.paletas = banco.palabras()
        build.tile_gfx = [build.tileset.first_tile + t.index for t in build.tiles]
        build.info = {
            "banco": banco,
            "glifos": glifos,
            "stats": {
                "patrones": banco.cuantos,
                "bytes_pcg": banco.cuantos * gfx_x68k.PATRON_BYTES,
                "bloques": len(banco.paletas),
            },
            "cabecera": [
                "#define NP_PCG_PATRONES %d" % banco.cuantos,
                "#define NP_PCG_BYTES %d" % (banco.cuantos * gfx_x68k.PATRON_BYTES),
                "#define NP_FONT_COUNT %d" % len(glifos),
                "extern const uint8_t np_pcg_data[NP_PCG_BYTES];",
            ],
        }

    def comprobar(self, build: Build) -> List[str]:
        avisos: List[str] = []
        banco: gfx_x68k.BancoX68k = build.info["banco"]
        if banco.cuantos > MAX_PATRONES:
            self.error(
                "los graficos ocupan %d patrones de 16x16 y la PCG del X68000 "
                "tiene %d" % (banco.cuantos, MAX_PATRONES),
                "usa menos dibujos distintos: de ahi comen los sprites y las "
                "dos capas de fondo")
        if len(banco.paletas) > MAX_BLOQUES:
            self.error(
                "el juego usa %d paletas y el X68000 tiene %d bloques de 16 "
                "colores" % (len(banco.paletas), MAX_BLOQUES))
        for nivel in build.levels:
            if nivel.height > gfx_x68k.BLOQUES * 4:      # 64 casillas de alto
                avisos.append(
                    "el nivel '%s' tiene %d casillas de alto y la tabla de "
                    "nombres llega a 64: lo que pase de ahi no se dibuja"
                    % (nivel.name, nivel.height))
        sobran = MAX_PATRONES - banco.cuantos
        if sobran < 32:
            avisos.append(
                "quedan %d patrones libres de %d: si anades mas dibujos, no "
                "cabran" % (sobran, MAX_PATRONES))
        return avisos + self.aviso_de_muestras(build, "todavia")

    # --- generacion ----------------------------------------------------

    def generar(self, build: Build, rom_id: str) -> Salida:
        salida = Salida()
        banco: gfx_x68k.BancoX68k = build.info["banco"]
        nombre = _nombre_ejecutable(build)

        salida.archivos["src/graficos.c"] = _graficos_c(build, banco)
        salida.archivos["Makefile"] = _makefile(build, nombre)
        salida.archivos["hacer_x.py"] = fuente_del_kit("x68k.py")
        salida.archivos["hacer_disco.py"] = fuente_del_kit("x68k_disk.py")
        salida.resumen.append(
            "graficos: %d patrones de 16x16 de los %d de la PCG (%d KB)"
            % (banco.cuantos, MAX_PATRONES,
               banco.cuantos * gfx_x68k.PATRON_BYTES // 1024))
        salida.resumen.append(
            "colores:  %d bloques de 16 de los %d que hay"
            % (len(banco.paletas), MAX_BLOQUES))
        salida.resumen.append(
            "ejecutable: disco/%s.X, y disco/%s.xdf con el dentro"
            % (nombre, nombre.lower()))
        return salida


def _nombre_ejecutable(build: Build) -> str:
    """Un nombre de archivo que Human68k acepte: ocho letras como mucho."""
    limpio = "".join(c for c in build.project.title.upper()
                     if c.isalnum())[:8]
    return limpio or "JUEGO"


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


def _graficos_c(build: Build, banco: gfx_x68k.BancoX68k) -> str:
    glifos = build.info["glifos"]
    planos = []
    for fila in glifos:
        planos.extend(fila)
    partes = [
        "/* Archivo generado por ngplat: los dibujos, ya en formato del PCG. */",
        '#include "gamedata.h"',
        "",
        "/* Cada patron son 16x16 pixeles de 4 bits: 128 bytes, en cuatro",
        "   cuadrantes de 8x8 en orden de lectura. */",
        "const uint8_t np_pcg_data[NP_PCG_BYTES] = {",
        _c_bytes(banco.datos()),
        "};",
        "",
        "/* Fuente del marcador: ocho bytes por caracter, un bit por pixel. */",
        "const uint8_t np_font_data[NP_FONT_COUNT * 8] = {",
        _c_bytes(planos, por_linea=8),
        "};",
        "",
    ]
    return "\n".join(partes)


def _makefile(build: Build, nombre: str) -> str:
    return """# Makefile generado por ngplat para "%s" (Sharp X68000).
# Se reescribe en cada `ngplat compilar`: pon tus cambios en game.yaml.
#
# Necesita un compilador de 68000. Vale cualquiera de estos:
#   m68k-elf-gcc
#   m68k-linux-gnu-gcc    (el paquete gcc-m68k-linux-gnu de Debian/Ubuntu)
#
# El enlazador saca un ELF; hacer_x.py lo convierte en un ejecutable .X de
# Human68k de verdad, con su cabecera de 64 bytes y su tabla de correcciones.

ifeq ($(origin CC), default)
CC := $(shell which m68k-elf-gcc 2>/dev/null || which m68k-linux-gnu-gcc 2>/dev/null)
endif
ifeq ($(CC),)
$(error no encuentro un compilador de 68000: instala gcc-m68k-linux-gnu o m68k-elf-gcc)
endif
PYTHON ?= python3

# -fno-store-merging: sin el, gcc junta dos escrituras de un byte seguidas en
# una sola de dos bytes, y si cae en una direccion impar el 68000 se para con
# un "address error".
CFLAGS  := -m68000 -O2 -fomit-frame-pointer -fno-builtin -ffreestanding \\
           -fno-store-merging -std=c99 -Wall -Wextra -Isrc
# -nodefaultlibs: la libgcc de un compilador de 68k para Linux esta hecha para
# 68020 y lleva instrucciones que el 68000 no tiene; las rutinas de multiplicar
# y dividir las pone src/np_aritmetica.c.
LDFLAGS := -nostdlib -nodefaultlibs -T x68000.ld -Wl,--emit-relocs \\
           -Wl,--build-id=none -Wl,-z,max-page-size=2

SRC := src/main.c src/np_video.c src/np_hud.c src/np_sound.c \\
       src/np_world.c src/np_aritmetica.c src/gamedata.c src/graficos.c
OBJ := $(SRC:.c=.o) src/arranque.o
JUEGO := disco/%s.X
DISCO := disco/%s.xdf

all: $(DISCO)
\t@echo "listo: $(JUEGO) y $(DISCO)"

%%.o: %%.c
\t$(CC) $(CFLAGS) -c $< -o $@

src/arranque.o: src/arranque.S
\t$(CC) $(CFLAGS) -c $< -o $@

juego.elf: $(OBJ)
\t$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJ)

$(JUEGO): juego.elf
\t@mkdir -p disco
\t$(PYTHON) hacer_x.py $< $@

# El .xdf es la copia de un disquete de Human68k: se mete en el emulador (o se
# escribe en un disco de verdad) y el juego se arranca desde el con su nombre.
$(DISCO): $(JUEGO)
\t$(PYTHON) hacer_disco.py $< $@

clean:
\trm -f $(OBJ) juego.elf $(JUEGO) $(DISCO)

.PHONY: all clean
""" % (build.project.title, nombre, nombre.lower())


registrar(X68000())
