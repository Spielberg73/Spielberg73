"""Neo Geo (AES / MVS): 68000 a 12 MHz, sprites para todo y sonido por Z80.

Particularidades que se resuelven aqui:
  - no hay plano de fondo con scroll: el escenario se dibuja con columnas de
    sprites de 16 px
  - los graficos van en ROMs aparte (C1/C2 para los sprites, S1 para el plano
    fix), con un formato de bitplanes peculiar
  - el sonido lo lleva un Z80 con su propia ROM (M1), que genera tools/ngplat/m1.py
"""

from __future__ import annotations

import os
from typing import Dict, List, Tuple

from .. import gfx
from .. import m1 as m1_mod
from ..build import Build
from ..errors import ProjectError
from .base import Limites, Salida, Sistema, registrar

M1_ROM = "m1"


# Columnas de sprite que la Neo Geo reserva para los actores: NP_ACTOR_SPRITES
# en engine/neogeo/np_video.h. El resto de los 381 del hardware se los llevan el
# escenario (21) y cada capa de parallax (21 mas).
COLUMNAS_ACTOR = 96

# Las tablas de actores por tipo de spawn, en el orden de NP_KIND_* .
_TABLAS = {0: "enemies", 1: "items", 3: "platforms", 4: "breakables"}


def _columnas_de(build: Build, kind: int, indice: int) -> int:
    """Lo que gasta un actor: una columna por cada 16 px de ancho del fotograma.

    Es la cuenta que hace np_draw_actor: recorre `cols` sprites y el alto sale
    gratis, porque un sprite de Neo Geo es una tira vertical.
    """
    tabla = getattr(build, _TABLAS.get(kind, ""), None) if kind in _TABLAS else None
    if not tabla or indice >= len(tabla):
        return 1
    return max(1, tabla[indice].sheet.cols)


def _columnas_a_la_vez(build: Build) -> Tuple[int, str]:
    """La pantalla peor de todo el juego, en columnas de sprite.

    Se prueban las ventanas de 320x224 apoyadas en cada spawn (la que mas coja
    siempre se puede correr hasta tocar alguno por arriba y por la izquierda),
    y a lo que salga se le suman los jugadores, que estan siempre en pantalla.
    """
    peor, donde = 0, ""
    jugadores = max(1, build.project.players) * max(1, build.player.sheet.cols)
    for nivel in build.levels:
        cuesta = [(x, y, _columnas_de(build, kind, indice))
                  for x, y, kind, indice in nivel.spawns]
        mayor = 0
        for x0, _, _ in cuesta:
            for _, y0, _ in cuesta:
                cabe = sum(c for x, y, c in cuesta
                           if x0 <= x < x0 + 320 and y0 <= y < y0 + 224)
                if cabe > mayor:
                    mayor = cabe
        if mayor + jugadores > peor:
            peor, donde = mayor + jugadores, nivel.name
    return peor, donde


class NeoGeo(Sistema):
    nombre = "neogeo"
    toca_muestras = True          # los canales ADPCM-A del YM2610, con la ROM V1
    titulo = "Neo Geo (AES / MVS)"
    cpu = "68000 a 12 MHz"
    pantalla = (320, 224)
    limites = Limites(colores_por_paleta=16, paletas=256, sprites=96, tiles=65536,
                      colores_en_pantalla=4096)
    notas = [
        "parallax: todas las capas del proyecto, cada una con su paleta",
        "sonido:   YM2610 por un Z80: tres cuadradas y muestras en ADPCM-A",
    ]
    archivos_motor = [
        ("include/np_types.h", "src/np_types.h"),
        ("include/np_game.h", "src/np_game.h"),
        ("include/np_world.h", "src/np_world.h"),
        ("core/np_world.c", "src/np_world.c"),
        ("neogeo/np_video.h", "src/np_video.h"),
        ("neogeo/np_video.c", "src/np_video.c"),
        ("neogeo/np_hud.c", "src/np_hud.c"),
        ("neogeo/np_sound.h", "src/np_sound.h"),
        ("neogeo/np_sound.c", "src/np_sound.c"),
        ("neogeo/main.c", "src/main.c"),
    ]
    extension_ejecutable = "rom"

    # --- colores -------------------------------------------------------

    def color(self, rgb):
        return gfx.ng_color(rgb)

    def color_visible(self, rgb):
        """Como se ve ese color en la consola (para el preview)."""
        return gfx.ng_color_to_rgb(gfx.ng_color(rgb))

    # --- empaquetado ----------------------------------------------------

    def preparar(self, build: Build) -> None:
        """Mete los graficos en las ROMs C1/C2 y S1 y reparte las paletas."""
        rom = gfx.RomData()
        build.rom = rom
        build.sistema = self

        rom.pack_sheet(build.tileset)
        for actor in build.actor_builds():
            rom.pack_sheet(actor.sheet)
        for capa in build.layers:
            capa.palette_index = rom.add_palette(capa.palette)
            base = {}
            nuevos = []
            for i, dibujo in enumerate(capa.dibujos):
                base[i] = rom.add_sprite_tile_shared(dibujo)
                nuevos.append(base[i])
            capa.tiles = [nuevos[i] for i in capa.tiles]
            capa.dibujos = []

        build.font = gfx.build_font(rom)
        build.hud_palette = rom.add_palette(gfx.hud_palette())
        build.paletas = [p.words() for p in rom.palettes]
        build.tile_gfx = [build.tileset.first_tile + t.index for t in build.tiles]
        build.info = {
            "stats": {
                "tiles_sprite": rom.sprite_tiles,
                "tiles_fix": rom.fix_tiles,
                "bytes_c1": len(rom.c1),
                "bytes_c2": len(rom.c2),
                "bytes_s1": len(rom.s1),
            },
            "cabecera": [
                "#define NP_FIX_TILES %d" % rom.fix_tiles,
                "#define NP_SPRITE_TILES %d" % rom.sprite_tiles,
            ],
        }

    def comprobar(self, build: Build) -> List[str]:
        avisos: List[str] = []
        if len(build.paletas) > self.limites.paletas:
            self.error("el juego usa %d paletas y la Neo Geo tiene %d"
                       % (len(build.paletas), self.limites.paletas))
        peor, donde = _columnas_a_la_vez(build)
        if peor > COLUMNAS_ACTOR:
            avisos.append(
                "en '%s' pueden caber %d columnas de sprite en una pantalla y la "
                "Neo Geo dibuja %d: lo que pase de ahi no se dibuja, sin avisar. "
                "Cada actor gasta una columna por cada 16 px de ancho (el alto "
                "sale gratis), y los disparos gastan tambien"
                % (donde, peor, COLUMNAS_ACTOR))
        return avisos

    # --- generacion -----------------------------------------------------

    def generar(self, build: Build, rom_id: str) -> Salida:
        salida = Salida()
        rom = build.rom

        # ROMs graficas: se rellenan hasta una potencia de dos
        for sufijo, datos in (("c1", rom.c1), ("c2", rom.c2), ("s1", rom.s1)):
            relleno = bytearray(datos)
            tamano = 1
            while tamano < max(len(relleno), 0x20000):
                tamano <<= 1
            relleno.extend(b"\x00" * (tamano - len(relleno)))
            nombre = "rom/%s-%s.%s" % (rom_id, sufijo, sufijo)
            salida.binarios[nombre] = bytes(relleno)
            salida.resumen.append("grafico:  %s (%d KB)" % (nombre, tamano // 1024))

        # ROM de sonido: el driver del Z80 con la musica y los efectos
        m1_rom, info = m1_mod.generar_m1(build.project.sound, build.music_order)
        nombre_m1 = "rom/%s-m1.m1" % rom_id
        salida.binarios[nombre_m1] = m1_rom
        salida.archivos["src/sonido.z80"] = info["fuente"]
        salida.resumen.append("sonido:   %s (%d KB)" % (nombre_m1, len(m1_rom) // 1024))

        # ROM de muestras: el YM2610 lee de ella por su cuenta, en ADPCM-A
        nombre_v1 = "rom/%s-v1.v1" % rom_id
        salida.binarios[nombre_v1] = info["v1"]
        digitales = sum(1 for primero, _ in info["muestras"] if primero)
        if digitales:
            salida.resumen.append(
                "muestras: %s (%d KB, %d efectos en ADPCM-A a %d Hz)"
                % (nombre_v1, len(info["v1"]) // 1024, digitales, 18500))

        salida.archivos["Makefile"] = _makefile(build, rom_id)
        return salida


def _makefile(build: Build, rom_id: str) -> str:
    from ..codegen import render_template
    from ..fixed import FIXED_ONE
    return render_template("Makefile.in", {
        "TITLE": build.project.title,
        "ROMID": rom_id,
        "FIXED_ONE": FIXED_ONE,
    })


registrar(NeoGeo())
