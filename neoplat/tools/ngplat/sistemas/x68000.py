"""Sharp X68000: 68000 a 10 MHz, chip de sprites y una capa de fondo.

De las seis maquinas del kit es la que menos trabajo pide, y por una razon
concreta: los patrones del PCG son de **16x16**, justo el tamano de tile de
NeoPlat. En la Mega Drive hay que partir cada tile en cuatro de 8x8 y en la Neo
Geo el escenario se dibuja con columnas de sprites; aqui una casilla del nivel
es una casilla de la tabla de nombres.

El reparto de la pantalla:

  capa BG  el escenario, con scroll por hardware
  sprites  los actores (128, de 16x16)
  texto    el marcador, en el plano de texto, que asi no gasta ni un patron

Dos cosas que salieron de probarlo en el emulador y no de la documentacion:

  - El chip tiene dos capas de fondo, pero no se consiguio que se vieran las
    dos a la vez con ninguna combinacion de sus registros. Asi que la capa se
    la queda el escenario y **el parallax no se dibuja en esta maquina**.
  - El limite de verdad no son los sprites sino los **192 patrones** de la PCG
    RAM: son 256, pero los 64 ultimos son la tabla de nombres de la capa, que
    vive dentro de la misma memoria.

Y por eso el color 15 del primer bloque de paleta se lo queda el marcador: el
plano de texto lee de la paleta de sprites, no tiene una suya.

El sonido lo lleva el YM2151, ocho canales de FM que toca el propio 68000. La
tabla de notas del chip esta medida en el emulador y no copiada: ver
docs/x68000.md, que cuenta como y por que.
"""

from __future__ import annotations

import struct
from typing import Dict, List

from .. import adpcm
from .. import gfx
from .. import gfx_x68k
from ..build import Build
from ..errors import ProjectError
from ..paths import fuente_del_kit
from ..sonido import _bytes_c, codigo_ym2151, preparar_muestra
from .base import Limites, Salida, Sistema, registrar

# El ADPCM (un MSM6258) y la velocidad a la que se le dan las muestras.
#
# Los dos numeros estan medidos en el emulador: se cifro un tono de 3000 Hz a
# una velocidad conocida y se toco con cada modo de _ADPCMOUT, mirando a que
# frecuencia salia. Sale la escalera de siempre -3,9 / 5,2 / 7,8 / 10,4 kHz-
# repartida en los modos $0003, $0103, $0203 y $0303; el quinto, que en teoria
# son 15,6 kHz, no sono. Se coge el mas rapido que funciona.
ADPCM_MODO = 0x0303                  # 10,4 kHz por los dos altavoces
ADPCM_RITMO = 10417                  # muestras por segundo
ADPCM_MAXIMO = 32 * 1024             # bytes de ADPCM por efecto (el doble en
                                     # muestras: cada byte lleva dos)

MAX_PATRONES = gfx_x68k.PATRONES     # los que quedan libres en la PCG RAM
MAX_BLOQUES = gfx_x68k.BLOQUES       # bloques de paleta de 16 colores
COLOR_HUD = 15                       # el ultimo del bloque 0, del marcador


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
        ("include/np_sonido.h", "src/np_sonido.h"),
        ("x68000/np_sound.c", "src/np_sound.c"),
        ("x68000/main.c", "src/main.c"),
        ("x68000/arranque.S", "src/arranque.S"),
        ("x68000/x68000.ld", "x68000.ld"),
    ]
    toca_muestras = True          # el MSM6258, que lee la RAM por DMA
    extension_ejecutable = "X"
    carpeta_salida = "disco"
    nombre_binario = "el ejecutable"
    notas = [
        "sprites:  128 de 16x16, y el escenario va en una capa aparte",
        "patrones: 192, repartidos entre los sprites y la capa de fondo",
        "parallax: no, esta maquina solo ensena una capa de fondo",
        "sonido:   YM2151 (ocho canales de FM) y muestras por el ADPCM",
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

        # El parallax se queda fuera: esta maquina solo ensena una capa de
        # fondo y se la lleva el escenario. Se quitan antes de empaquetar para
        # que no gasten patrones, que aqui son 192 y hacen falta.
        build.info_parallax = len(build.layers)
        for nivel in build.levels:
            nivel.layers = []
        build.layers = []

        # El marcador va en el plano de texto, a un bit por pixel: no gasta
        # patrones, asi que la fuente se guarda aparte.
        fuente: Dict[str, int] = {}
        glifos = [[0] * 8]                       # el 0 es el hueco en blanco
        for i, char in enumerate(gfx.FONT_CHARS):
            glifos.append(_glifo_1bpp(gfx.font_glyph_pixels(char)))
            fuente[char] = i + 1

        for nivel in build.levels:
            nivel.background = self.color(nivel.background_rgb)

        # El color 15 del primer bloque se lo queda el marcador: el plano de
        # texto lee de esta misma paleta y no tiene una suya. Es lo mismo que
        # hacen el Atari ST y el Amiga con su ultimo color.
        paletas = banco.palabras()
        paletas[0][COLOR_HUD] = self.color((255, 255, 255))

        build.font = fuente
        build.hud_palette = 0
        build.paletas = paletas
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
                "usa menos dibujos distintos: de ahi comen los sprites y la "
                "capa de fondo, y los 64 ultimos son la tabla de nombres")
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
        if getattr(build, "info_parallax", 0):
            avisos.append(
                "el juego tiene %d capa(s) de parallax y el X68000 solo ensena "
                "una capa de fondo, que se lleva el escenario: no se dibujan"
                % build.info_parallax)
        if len(banco.paletas) and _usa_el_ultimo(banco, COLOR_HUD):
            avisos.append(
                "el color %d de la primera paleta se lo queda el marcador: si "
                "el escenario lo usaba, ahi saldra blanco" % COLOR_HUD)
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
        salida.archivos["src/sonido.c"] = _sonido_c(build)
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
        pcm = getattr(build, "pcm_bytes", 0)
        salida.resumen.append(
            "sonido:   %d melodias y %d efectos por el YM2151%s"
            % (len(build.music_order), len(_efectos_de(build)),
               ", y %d KB de muestras en ADPCM" % (pcm // 1024) if pcm else ""))
        salida.resumen.append(
            "ejecutable: disco/%s.X, y disco/%s.xdf con el dentro"
            % (nombre, nombre.lower()))
        return salida


def _efectos_de(build: Build) -> List[str]:
    from ..sonido import EVENTOS
    return [n for n in EVENTOS if n in build.project.sound.efectos]


def _secuencia_c(nombre: str, pasos) -> List[str]:
    """Una secuencia de notas, ya en codigos del YM2151.

    En `periodo` no va un periodo sino el key code del chip y su fraccion, uno
    en cada byte: este chip no toma frecuencias, toma notas. La estructura es la
    misma que en las otras maquinas para que el motor no cambie.
    """
    lineas = ["static const NpSndPaso %s[] = {" % nombre]
    for paso in pasos:
        duracion = max(1, int(paso.duracion))
        volumen = (paso.volumen & 0x0F) | (0x80 if paso.ruido else 0)
        codigo = codigo_ym2151(paso.frecuencia)
        while duracion > 0:
            trozo = min(255, duracion)
            lineas.append("    { 0x%04x, %d, 0x%02x }," % (codigo, trozo, volumen))
            duracion -= trozo
    lineas.append("    { 0, 0, 0 }")
    lineas.append("};")
    return lineas


def _sonido_c(build: Build) -> str:
    sonido = build.project.sound
    efectos = _efectos_de(build)
    partes = [
        "/* Archivo generado por ngplat: la musica y los efectos, ya en codigos",
        " * de nota del YM2151 (X68000). */",
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
    lineas, bytes_pcm = _tabla_de_muestras([sonido.efectos[n] for n in efectos])
    partes.extend(lineas)
    build.pcm_bytes = bytes_pcm
    partes.append("")
    return "\n".join(partes)


def _tabla_de_muestras(efectos):
    """Las muestras digitales, ya cifradas en ADPCM para el MSM6258.

    El chip no lee bytes crudos: lee medio byte por muestra, en el ADPCM de la
    familia OKI, que es el mismo que ya usa la Neo Geo para su YM2610 (de ahi
    sale el cifrador, ngplat/adpcm.py). Asi que una muestra ocupa la mitad que
    en las otras maquinas.

    En `periodo` no va un periodo sino el modo que hay que pasarle a _ADPCMOUT:
    la velocidad y por que altavoces sale.
    """
    lineas: List[str] = []
    entradas: List[str] = []
    total = 0
    for i, efecto in enumerate(efectos):
        muestra = preparar_muestra(efecto, ADPCM_RITMO, ADPCM_MAXIMO * 2)
        if muestra is None or not len(muestra):
            entradas.append("    { 0, 0, 0, 0 },")
            continue
        datos = adpcm.cifrar(struct.unpack("%db" % len(muestra.datos),
                                           muestra.datos))
        total += len(datos)
        lineas.append("static const uint8_t np_pcm%d[] = {" % i)
        lineas.extend(_bytes_c(datos))
        lineas.append("};")
        lineas.append("")
        frames = max(1, int(round(len(muestra.datos) * 60.0 / ADPCM_RITMO + 0.5)))
        entradas.append("    { np_pcm%d, %d, 0x%04X, %d },"
                        % (i, len(datos), ADPCM_MODO, frames))
    lineas.append("const NpSndMuestra np_snd_muestras[] = {")
    lineas.extend(entradas if entradas else ["    { 0, 0, 0, 0 },"])
    lineas.append("    { 0, 0, 0, 0 }")
    lineas.append("};")
    return lineas, total


def _nombre_ejecutable(build: Build) -> str:
    """Un nombre de archivo que Human68k acepte: ocho letras como mucho."""
    limpio = "".join(c for c in build.project.title.upper()
                     if c.isalnum())[:8]
    return limpio or "JUEGO"


def _usa_el_ultimo(banco, indice: int) -> bool:
    """Si el primer bloque de paleta llega hasta el color que se reserva."""
    return bool(banco.paletas) and len(banco.paletas[0].colors) > indice


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

SRC := src/main.c src/np_video.c src/np_hud.c src/np_sound.c src/sonido.c \\
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
