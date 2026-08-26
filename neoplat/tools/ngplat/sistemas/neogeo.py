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
from typing import Dict, List

from .. import gfx
from .. import m1 as m1_mod
from ..build import Build
from ..errors import ProjectError
from .base import Limites, Salida, Sistema, registrar

M1_ROM = "m1"


class NeoGeo(Sistema):
    nombre = "neogeo"
    titulo = "Neo Geo (AES / MVS)"
    cpu = "68000 a 12 MHz"
    pantalla = (320, 224)
    limites = Limites(colores_por_paleta=16, paletas=256, sprites=96, tiles=65536,
                      colores_en_pantalla=4096)
    notas = [
        "parallax: todas las capas del proyecto, cada una con su paleta",
        "sonido:   YM2610, tres canales de onda cuadrada por un Z80",
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
