"""Atari ST (un 520 ST basta): 68000 a 8 MHz, Shifter y YM2149.

Es la mas espartana de las cinco maquinas, y por eso la mas interesante: tiene
el mismo procesador que las otras cuatro y **nada** que le eche una mano. No
hay sprites, no hay blitter y no hay scroll por hardware. Todo lo que se ve en
pantalla lo mueve el 68000 a mano.

Lo que eso obliga a hacer:

  - la pantalla son cuatro bitplanes entrelazados (16 colores de 512) y las
    paletas del proyecto se funden en **una sola de 15**, que es lo que queda
    despues de reservar el ultimo color para el marcador;
  - se dibuja en dos pantallas alternas, porque sin blitter borrar y repintar
    un actor lleva medio frame y el haz pasa por encima;
  - el escenario se mueve de **16 en 16 pixeles**: dibujar un tile en una x
    cualquiera cuesta cuatro veces mas, y con la vista pegada a la rejilla se
    copia tal cual. Los actores si van al pixel;
  - el ST ensena **200 lineas** y las demas maquinas 224: se ve una ventana del
    mismo mundo con 24 lineas menos por arriba (por arriba y no repartidas, que
    abajo esta el suelo);
  - hay una capa de parallax, pero solo con `camara: pantallas`: ahi la vista se
    queda quieta entre salto y salto y pintarla sale gratis, porque donde no hay
    escenario ya se pintaba un tile en blanco. Con scroll, fondo y escenario van
    a velocidades distintas y sin un segundo plano por hardware habria que
    repintar la pantalla entera cada pocos pixeles;
  - el sonido sale por el YM2149, que es el mismo chip que el SSG de la Neo
    Geo con la mitad de reloj;
  - el resultado no es un cartucho sino un **disquete** (.st): el ejecutable lo
    hace prg.py a partir del ELF y st_disk.py lo mete en la carpeta AUTO de un
    disco de 720 KB, que es de donde TOS lo arranca solo al encender.
"""

from __future__ import annotations

import os
from typing import Dict, List

from .. import gfx, gfx_amiga, gfx_st
from ..build import Build
from ..errors import ProjectError
from ..sonido import periodo_ym2149, tabla_de_muestras_vacia
from .base import Limites, Salida, Sistema, registrar

COLOR_HUD = 15                              # el ultimo color, reservado
MAX_COLORES_JUEGO = COLOR_HUD               # los otros 15 son del juego
MAX_TILES = 1024                            # 160 KB entre dibujos y mascaras


class AtariSt(Sistema):
    nombre = "atarist"
    titulo = "Atari ST (520/1040)"
    cpu = "68000 a 8 MHz"
    pantalla = (320, 200)
    limites = Limites(colores_por_paleta=16, paletas=1, sprites=0,
                      tiles=MAX_TILES, colores_en_pantalla=gfx_st.COLORES)
    archivos_motor = [
        ("include/np_types.h", "src/np_types.h"),
        ("include/np_game.h", "src/np_game.h"),
        ("include/np_world.h", "src/np_world.h"),
        ("include/np_sonido.h", "src/np_sonido.h"),
        ("core/np_world.c", "src/np_world.c"),
        ("core/np_aritmetica.c", "src/np_aritmetica.c"),
        ("atarist/np_st.h", "src/np_st.h"),
        ("atarist/np_video.c", "src/np_video.c"),
        ("atarist/np_hud.c", "src/np_hud.c"),
        ("atarist/np_sound.c", "src/np_sound.c"),
        ("atarist/main.c", "src/main.c"),
        ("atarist/arranque.c", "src/arranque.c"),
        ("atarist/st.ld", "st.ld"),
    ]
    extension_ejecutable = ""
    carpeta_salida = "disco"
    nombre_binario = "el disquete"
    dibujo_actores = "actores dibujados a mano por la CPU"
    notas = [
        "pantalla: 200 lineas en vez de 224; se ve una ventana del mismo mundo",
        "camara:   el escenario se mueve de 16 en 16 pixeles (no hay scroll",
        "          por hardware), y los actores al pixel",
        "parallax: una capa, y solo con 'camara: pantallas'; con scroll no cabe",
        "sonido:   YM2149, tres cuadradas y un ruido; sin muestras digitales",
    ]

    # --- colores -------------------------------------------------------

    def color(self, rgb):
        return gfx_st.st_color(rgb)

    def color_visible(self, rgb):
        return gfx_st.st_color_a_rgb(gfx_st.st_color(rgb))

    # --- empaquetado ---------------------------------------------------

    def preparar(self, build: Build) -> None:
        build.sistema = self
        banco = gfx_st.BancoSt()
        # El fondo solo se dibuja con la camara por pantallas: ahi la vista se
        # queda quieta entre salto y salto y pintarlo no cuesta nada. Con
        # scroll, escenario y fondo van a velocidades distintas y sin un
        # segundo plano por hardware habria que repintar la pantalla entera
        # cada pocos pixeles. Ver docs/atarist.md.
        fondo = bool(build.layers) and build.project.camera == "pantallas"

        # 1) las paletas: los 16 colores del ST menos el del marcador. No hay
        #    dibujo que quepa tal cual, asi que los que sobran se cambian por el
        #    mas parecido, pesando cuanto se usa cada uno.
        partes = [(build.tileset.palette, build.tileset.tiles)]
        partes += [(a.sheet.palette, a.sheet.tiles) for a in build.actor_builds()]
        if fondo:
            partes += [(c.palette, [c.dibujos[i] for i in c.tiles]) for c in build.layers]
        paletas = [p for p, _ in partes]
        pesos = _pesos(partes)
        unica = gfx_amiga.fusionar_paletas(paletas, tope=COLOR_HUD, pesos=pesos,
                                           aproximar=True)

        def remapear(tile, nombre):
            mapa = unica.asignacion[nombre]
            return [mapa.get(v, 0) for v in tile]

        def sin_transparente(tile):
            """El fondo no tiene nada detras: sus huecos se pintan del color 0
            del nivel igual que antes, asi que se dejan como estan."""
            return tile

        # 2) los dibujos, entrelazados y con su mascara. Sin compartir: el motor
        #    cuenta con que los fotogramas de un actor van seguidos.
        build.tileset.first_tile = banco.cuantos
        for tile in build.tileset.tiles:
            banco.anadir(remapear(tile, build.tileset.palette.name), compartir=False)
        build.tileset.palette_index = 0

        for actor in build.actor_builds():
            actor.sheet.first_tile = banco.cuantos
            for tile in actor.sheet.tiles:
                banco.anadir(remapear(tile, actor.sheet.palette.name), compartir=False)
            actor.sheet.palette_index = 0

        # 3) las capas de parallax, si se van a dibujar
        if fondo:
            for capa in build.layers:
                nuevos = [banco.anadir(remapear(sin_transparente(d), capa.palette.name))
                          for d in capa.dibujos]
                capa.tiles = [nuevos[i] for i in capa.tiles]
                capa.palette_index = 0
                capa.dibujos = []
        else:
            for capa in build.layers:
                capa.tiles = [0] * len(capa.tiles)
                capa.palette_index = 0
                capa.dibujos = []

        if banco.cuantos > MAX_TILES:
            raise ProjectError(
                "los graficos ocupan %d dibujos de 16x16 y el limite del Atari ST "
                "en NeoPlat son %d" % (banco.cuantos, MAX_TILES),
                hint="usa menos dibujos distintos: en el ST cada uno ocupa 160 "
                     "bytes de memoria y no hay cartucho donde dejarlos",
            )

        # 4) la fuente del marcador: 8x8 en un solo bit por pixel
        fuente: Dict[str, int] = {}
        glifos = [[0] * 8]                       # el 0 es el hueco en blanco
        for i, char in enumerate(gfx.FONT_CHARS):
            glifos.append(_glifo_1bpp(gfx.font_glyph_pixels(char)))
            fuente[char] = i + 1

        colores = unica.palabras_de(gfx_st.st_color, gfx_st.COLORES)
        colores[COLOR_HUD] = gfx_st.st_color((255, 255, 255))

        for nivel in build.levels:
            nivel.background = self.color(nivel.background_rgb)

        build.font = fuente
        build.hud_palette = 0
        build.paletas = [colores]
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
                "aproximados": unica.perdidos,
            },
            "fondo": fondo,
            "cabecera": [
                "#define NP_TILE_COUNT %d" % banco.cuantos,
                "#define NP_FONT_COUNT %d" % len(glifos),
                "#define NP_PASOS_POR_DIBUJO %d" % PASOS_POR_DIBUJO,
                "#define NP_FONDO_ST %d" % (1 if fondo else 0),
            ],
        }

    def comprobar(self, build: Build) -> List[str]:
        avisos: List[str] = []
        if build.info.get("stats", {}).get("aproximados"):
            avisos.append(
                "en el Atari ST solo hay 15 colores para los dibujos: %d colores "
                "de los tuyos se han cambiado por el mas parecido de los que "
                "caben. Si quieres mandar tu en los colores, dibuja con quince"
                % build.info["stats"]["aproximados"])
        if not build.info.get("fondo"):
            for nivel in build.levels:
                if nivel.layers:
                    avisos.append(
                        "en el Atari ST el parallax solo se dibuja con "
                        "'camara: pantallas': el fondo de '%s' se vera del color "
                        "de fondo. Con scroll, el fondo y el escenario van a "
                        "velocidades distintas y sin un segundo plano por hardware "
                        "habria que repintar la pantalla entera cada pocos pixeles"
                        % nivel.name)
                    break
        else:
            for nivel in build.levels:
                if len(nivel.layers) > 1:
                    avisos.append(
                        "el Atari ST dibuja una sola capa de fondo: en '%s' se "
                        "usara la primera" % nivel.name)
                    break
        avisos.extend(self.aviso_de_muestras(
            build, "su YM2149 solo hace ondas cuadradas"))
        return avisos

    # --- generacion ----------------------------------------------------

    def generar(self, build: Build, rom_id: str) -> Salida:
        salida = Salida()
        banco: gfx_st.BancoSt = build.info["banco"]

        salida.archivos["src/graficos.c"] = _graficos_c(build, banco)
        salida.archivos["src/sonido.c"] = _sonido_c(build)
        nombre = _nombre_ejecutable(build)
        salida.archivos["Makefile"] = _makefile(build, nombre,
                                                _etiqueta_disco(build.project.title))
        salida.archivos["hacer_prg.py"] = _fuente_de("prg.py")
        salida.archivos["hacer_st.py"] = _fuente_de("st_disk.py")
        salida.resumen.append(
            "graficos: %d dibujos de 16x16 (%d KB de dibujos y %d KB de mascaras)"
            % (banco.cuantos, len(banco.tiles) // 1024, len(banco.mascaras) // 1024))
        salida.resumen.append(
            "colores:  %d de los 16 del ST (el 15 es el del marcador)"
            % build.info["stats"]["colores"])
        if build.info.get("fondo"):
            salida.resumen.append(
                "fondo:    una capa de parallax, dibujada debajo del escenario")
        salida.resumen.append(
            "disquete: disco/%s.st (720 KB, arranca solo desde la carpeta AUTO)"
            % nombre.lower())
        return salida


# Cuantos pasos de juego pasan entre dos dibujados. El juego simula siempre a
# 50 pasos por segundo (eso es lo que hace que sea el mismo juego que en las
# otras maquinas); lo que baja a 25 es la pantalla, porque sin blitter no da
# tiempo a mas. Esta medido en un ST emulado, no supuesto: ver docs/atarist.md.
PASOS_POR_DIBUJO = 2


def _nombre_ejecutable(build: Build) -> str:
    """El titulo del juego, hecho un nombre de fichero de TOS (ocho letras)."""
    letras = [c for c in build.project.title.upper() if c.isalnum()]
    return "".join(letras[:8]) or "JUEGO"


def _pesos(partes) -> Dict[tuple, int]:
    """Cuenta cuantos pixeles usa cada color, para saber cuales merece la pena
    conservar al bajar a quince."""
    pesos: Dict[tuple, int] = {}
    for paleta, dibujos in partes:
        for dibujo in dibujos:
            for v in dibujo:
                if v:
                    color = paleta.colors[v - 1]
                    pesos[color] = pesos.get(color, 0) + 1
    return pesos


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


def _graficos_c(build: Build, banco: gfx_st.BancoSt) -> str:
    colores = build.info["colores"]
    glifos = []
    for filas in build.info["glifos"]:
        glifos.extend(filas)
    partes = [
        "/* Archivo generado por ngplat: los dibujos, ya en bitplanes del ST. */",
        '#include "np_st.h"',
        "",
        "/* Las dos pantallas. Van sin inicializar a proposito: asi caen en la",
        " * BSS, que TOS reserva y entrega puesta a cero. Sobra sitio para poder",
        " * alinearlas a 32 KB, que es lo que hace que el contador de video sirva",
        " * para las dos (ver np_video.c). */",
        "uint8_t np_pantallas[NP_PANTALLAS * NP_HUECO_PANTALLA + NP_HUECO_PANTALLA];",
        "",
        "/* Cada dibujo son 16 filas x 4 bitplanes x 2 bytes = 128 bytes. */",
        "const uint8_t np_tile_data[NP_TILE_COUNT * %d] = {" % banco.bytes_por_tile,
        _c_bytes(bytes(banco.tiles)),
        "};",
        "",
        "/* Y su mascara: un bit por pixel, 1 donde el dibujo tapa el fondo. Aqui",
        " * va una sola palabra por fila, no una por plano como en el Amiga: la",
        " * lee la CPU, que puede usar la misma para los cuatro. */",
        "const uint8_t np_tile_mask[NP_TILE_COUNT * %d] = {" % gfx_st.BYTES_MASCARA,
        _c_bytes(bytes(banco.mascaras)),
        "};",
        "",
        "#if NP_FONDO_ST",
        "/* Un bit por dibujo: 1 si no tiene ni un pixel transparente. Con eso el",
        " * escenario que tapa la casilla entera se copia tal cual y el parallax",
        " * solo cuesta algo en las casillas que dejan huecos. */",
        "const uint8_t np_tile_opaco[(NP_TILE_COUNT + 7) / 8] = {",
        _c_bytes(gfx_st.bits_de(banco.opacos)),
        "};",
        "#endif",
        "",
        "/* Los 16 colores de la pantalla, en formato del ST (3 bits por canal). */",
        "const uint16_t np_colores[16] = {",
        "    " + ", ".join("0x%04x" % c for c in colores[:16]) + ",",
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
        periodo = periodo_ym2149(paso.frecuencia)
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
        " * del YM2149 (Atari ST). */",
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
    partes.extend(tabla_de_muestras_vacia())
    partes.append("")
    return "\n".join(partes)


def _makefile(build: Build, nombre: str, etiqueta: str) -> str:
    return """# Makefile generado por ngplat para "%s" (Atari ST).
# Se reescribe en cada `ngplat compilar`: pon tus cambios en game.yaml.
#
# Necesita un compilador de 68000. Vale cualquiera de estos:
#   m68k-atari-mint-gcc   (el de la comunidad del ST, si lo tienes)
#   m68k-elf-gcc
#   m68k-linux-gnu-gcc    (el paquete gcc-m68k-linux-gnu de Debian/Ubuntu)
#
# El enlazador saca un ELF; hacer_prg.py lo convierte en un ejecutable de
# GEMDOS de verdad (cabecera de 28 bytes y tabla de relocalizacion) y
# hacer_st.py monta con el un disquete de 720 KB que arranca solo: el juego va
# en la carpeta AUTO, que es lo que TOS ejecuta al encender.

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
CFLAGS  := -m68000 -O2 -fomit-frame-pointer -fno-builtin -ffreestanding \\
           -fno-store-merging -std=c99 -Wall -Wextra -Isrc
# -nodefaultlibs: la libgcc de un compilador de 68k para Linux esta hecha para
# 68020 y lleva instrucciones que el 68000 no tiene; las rutinas de multiplicar
# y dividir las pone src/np_aritmetica.c.
LDFLAGS := -nostdlib -nodefaultlibs -T st.ld -Wl,--emit-relocs -Wl,--build-id=none

SRC := src/arranque.c src/main.c src/np_video.c src/np_hud.c src/np_sound.c \\
       src/np_world.c src/np_aritmetica.c src/gamedata.c src/graficos.c \\
       src/sonido.c
OBJ := $(SRC:.c=.o)
JUEGO := disco/%s.PRG
DISCO := disco/%s.st
ETIQUETA := "%s"

all: $(DISCO)
	@echo "disquete listo: $(DISCO)"

%%.o: %%.c
	$(CC) $(CFLAGS) -c $< -o $@

juego.elf: $(OBJ)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJ)

$(JUEGO): juego.elf
	@mkdir -p disco
	$(PYTHON) hacer_prg.py $< $@

# El .st es la copia de un disquete: se mete en el emulador (o en un Gotek, o
# en un ST de verdad) y arranca solo, sin pasar por el escritorio.
$(DISCO): $(JUEGO) hacer_st.py
	$(PYTHON) hacer_st.py $@ %s.PRG $(JUEGO) $(ETIQUETA)

# Con un emulador instalado, `make run` mete el disquete y enciende el ST.
EMU ?= hatari
run: all
	$(EMU) --disk-a $(DISCO)

clean:
	rm -f $(OBJ) juego.elf $(JUEGO) $(DISCO)

.PHONY: all run clean
""" % (build.project.title, nombre, nombre.lower(), etiqueta, nombre)


def _fuente_de(modulo: str) -> str:
    """Copia un modulo del kit tal cual, para que el proyecto generado se valga solo."""
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        modulo)
    with open(ruta, "r", encoding="utf-8") as fh:
        return fh.read()


def _etiqueta_disco(titulo: str) -> str:
    """El nombre del volumen: en TOS son seis letras."""
    letras = [c for c in titulo.upper() if c.isalnum()]
    return "".join(letras[:6]) or "NEOPLA"


registrar(AtariSt())
