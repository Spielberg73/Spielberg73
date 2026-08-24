"""Generacion del proyecto en C: gamedata.c/h, ROMs graficas y Makefile."""

from __future__ import annotations

import os
import shutil
from typing import Dict, List, Sequence

from . import gfx
from .build import (
    Build, actor_def_values, enemy_values, item_values, layer_values, player_values,
    tile_tables,
)
from .fixed import FIXED_ONE
from .paths import ENGINE_DIR, TEMPLATES_DIR

HEADER_NOTE = (
    "/* Archivo generado por ngplat a partir de game.yaml. No lo edites a mano:\n"
    " * se reescribe en cada 'ngplat build'. */\n"
)


def _c_string(text: str) -> str:
    out = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % "".join(ch if 32 <= ord(ch) < 127 else "?" for ch in out)


def _array(values: Sequence[int], per_line: int = 16, fmt: str = "%d") -> str:
    lines: List[str] = []
    for i in range(0, len(values), per_line):
        chunk = ", ".join(fmt % v for v in values[i:i + per_line])
        lines.append("    " + chunk + ",")
    return "\n".join(lines)


def _anim_arrays(prefix: str, build_actor) -> str:
    out: List[str] = []
    for slot, anim in enumerate(build_actor.anims):
        frames = ", ".join(str(f) for f in anim.frames)
        out.append("static const uint8_t %s_anim%d[] = { %s };" % (prefix, slot, frames))
    return "\n".join(out)


def _actor_def(prefix: str, values: Dict[str, object]) -> str:
    anims = []
    for slot, anim in enumerate(values["anims"]):          # type: ignore[index]
        anims.append(
            "        { %s_anim%d, %d, %d, %d }"
            % (prefix, slot, anim["count"], anim["speed"], anim["loop"])
        )
    return (
        "    {\n"
        "        %d, %d, %d, %d,\n"
        "        %d, %d, %d, %d,\n"
        "        {\n%s\n        }\n"
        "    }"
        % (
            values["first_tile"], values["palette"], values["cols"], values["rows"],
            values["box_x"], values["box_y"], values["box_w"], values["box_h"],
            ",\n".join(anims),
        )
    )


def generate_gamedata(build: Build) -> Dict[str, str]:
    """Devuelve {ruta_relativa: contenido} con el codigo C del juego."""
    project = build.project
    kinds, graphics = tile_tables(build)
    palettes = build.rom.palettes

    header = [HEADER_NOTE, "#ifndef GAMEDATA_H", "#define GAMEDATA_H", "",
              '#include "np_game.h"', ""]
    header.append("#define NP_PALETTE_COUNT %d" % len(palettes))
    header.append("#define NP_HUD_PALETTE %d" % build.hud_palette)
    header.append("#define NP_FIX_TILES %d" % build.rom.fix_tiles)
    header.append("#define NP_SPRITE_TILES %d" % build.rom.sprite_tiles)
    header.append("#define NP_MAX_LEVEL_TILES_W %d" % max(l.width for l in build.levels))
    header.append("#define NP_HUD_ENABLED %d" % (1 if project.hud else 0))
    header.append("#define NP_LAYER_COUNT %d" % len(build.layers))
    header.append("#define NP_MAX_LEVEL_LAYERS %d"
                  % max([len(l.layers) for l in build.levels] + [0]))
    header.append("")
    header.append("extern const uint16_t np_palettes[NP_PALETTE_COUNT][16];")
    header.append("extern const uint8_t np_font_index[128];")
    header.append("")
    header.append("#endif /* GAMEDATA_H */")

    src: List[str] = [HEADER_NOTE, '#include "gamedata.h"', ""]
    src.append("const char np_game_title[] = %s;" % _c_string(project.title))
    src.append("const char np_game_author[] = %s;" % _c_string(project.author))
    src.append("const uint8_t np_start_lives = %d;" % project.lives)
    src.append("const uint16_t np_time_limit = %d;" % project.time_limit)
    src.append("const uint16_t np_tileset_first_tile = %d;" % build.tileset.first_tile)
    src.append("const uint8_t np_tileset_palette = %d;" % build.tileset.palette_index)
    src.append("")

    src.append("/* Paletas: 16 colores por paleta, el 0 es transparente. */")
    src.append("const uint16_t np_palettes[NP_PALETTE_COUNT][16] = {")
    for pal in palettes:
        words = ", ".join("0x%04x" % w for w in pal.words())
        src.append("    { %s }, /* %s */" % (words, pal.name))
    src.append("};")
    src.append("")

    src.append("/* Fuente del marcador: caracter ASCII -> tile del plano fix. */")
    font_table = [0] * 128
    for char, tile in build.font.items():
        if ord(char) < 128:
            font_table[ord(char)] = tile
        if char.isalpha():
            font_table[ord(char.lower())] = tile
    src.append("const uint8_t np_font_index[128] = {")
    src.append(_array(font_table))
    src.append("};")
    src.append("")

    src.append("/* Tabla de seno en coma fija 24.8 (un ciclo en 64 pasos). */")
    src.append("const np_fix np_sin_table[64] = {")
    src.append(_array(build.sin_table, per_line=8))
    src.append("};")
    src.append("")

    src.append("/* Tipos y graficos de cada simbolo de la leyenda. */")
    src.append("const uint8_t np_tile_kind[] = {")
    src.append(_array(kinds))
    src.append("};")
    src.append("const uint16_t np_tile_gfx[] = {")
    src.append(_array(graphics))
    src.append("};")
    src.append("const uint16_t np_tile_count = %d;" % len(kinds))
    src.append("")

    # --- jugador
    src.append(_anim_arrays("np_player", build.player))
    pv = player_values(project)
    src.append("const NpPlayerDef np_player_def = {")
    src.append(_actor_def("np_player", actor_def_values(build.player)) + ",")
    src.append("    %d, %d, %d, %d," % (pv["speed"], pv["accel"], pv["friction"], pv["air_accel"]))
    src.append("    %d, %d, %d, %d, %d," % (pv["jump"], pv["jump_cut"], pv["gravity"],
                                            pv["max_fall"], pv["bounce"]))
    src.append("    %d," % pv["invuln"])
    src.append("    %d, %d, %d, %d, %d" % (pv["coyote"], pv["jump_buffer"],
                                           pv["double_jump"], pv["stomp"], pv["health"]))
    src.append("};")
    src.append("")

    # --- enemigos
    for i, enemy in enumerate(build.enemies):
        src.append("/* enemigo %d: %s */" % (i, enemy.name))
        src.append(_anim_arrays("np_enemy%d" % i, enemy))
    src.append("const NpEnemyDef np_enemies[] = {")
    if not build.enemies:
        src.append("    { { 0, 0, 1, 1, 0, 0, 16, 16, { { 0, 0, 0, 0 }, { 0, 0, 0, 0 },"
                   " { 0, 0, 0, 0 }, { 0, 0, 0, 0 }, { 0, 0, 0, 0 } } },"
                   " 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1 }")
    for i, enemy in enumerate(build.enemies):
        ev = enemy_values(enemy)
        src.append("    {")
        src.append(_actor_def("np_enemy%d" % i, actor_def_values(enemy)) + ",")
        src.append("        %d, %d, %d, %d, %d," % (ev["speed"], ev["gravity"], ev["jump"],
                                                    ev["range"], ev["amplitude"]))
        src.append("        %d, %d, %d," % (ev["period"], ev["interval"], ev["score"]))
        src.append("        %d, %d, %d, %d, %d" % (ev["behavior"], ev["health"], ev["damage"],
                                                   ev["stompable"], ev["edge_turn"]))
        src.append("    }," if i + 1 < len(build.enemies) else "    }")
    src.append("};")
    src.append("const uint16_t np_enemy_count = %d;" % len(build.enemies))
    src.append("")

    # --- objetos
    for i, item in enumerate(build.items):
        src.append("/* objeto %d: %s */" % (i, item.name))
        src.append(_anim_arrays("np_item%d" % i, item))
    src.append("const NpItemDef np_items[] = {")
    if not build.items:
        src.append("    { { 0, 0, 1, 1, 0, 0, 16, 16, { { 0, 0, 0, 0 }, { 0, 0, 0, 0 },"
                   " { 0, 0, 0, 0 }, { 0, 0, 0, 0 }, { 0, 0, 0, 0 } } }, 0, 0, 1 }")
    for i, item in enumerate(build.items):
        iv = item_values(item)
        src.append("    {")
        src.append(_actor_def("np_item%d" % i, actor_def_values(item)) + ",")
        src.append("        %d, %d, %d" % (iv["score"], iv["effect"], iv["amount"]))
        src.append("    }," if i + 1 < len(build.items) else "    }")
    src.append("};")
    src.append("const uint16_t np_item_count = %d;" % len(build.items))
    src.append("")

    # --- capas de fondo (parallax)
    for i, layer in enumerate(build.layers):
        values = layer_values(layer)
        src.append("/* capa de fondo %d: %s (%dx%d tiles) */"
                   % (i, layer.name, layer.cols, layer.rows))
        src.append("static const uint16_t np_layer%d_tiles[] = {" % i)
        src.append(_array(values["tiles"], per_line=16))
        src.append("};")
    src.append("const NpLayer np_layers[] = {")
    if not build.layers:
        src.append("    { 0, 256, 0, 0, 1, 1, 0, 1 }")
    for i, layer in enumerate(build.layers):
        values = layer_values(layer)
        src.append(
            "    { np_layer%d_tiles, %d, %d, %d, %d, %d, %d, %d },"
            % (i, values["speed_x"], values["speed_y"], values["offset_y"],
               values["cols"], values["rows"], values["palette"], values["repeat"])
        )
    src.append("};")
    src.append("const uint16_t np_layer_count = %d;" % len(build.layers))
    src.append("")

    # --- niveles
    for i, level in enumerate(build.levels):
        src.append("/* nivel %d: %s (%dx%d tiles) */" % (i, level.name, level.width, level.height))
        src.append("static const uint8_t np_level%d_cells[] = {" % i)
        src.append(_array(level.cells, per_line=32))
        src.append("};")
        if level.spawns:
            src.append("static const NpSpawn np_level%d_spawns[] = {" % i)
            for x, y, kind, index in level.spawns:
                src.append("    { %d, %d, %d, %d }," % (x, y, kind, index))
            src.append("};")
        if level.layers:
            src.append("static const uint8_t np_level%d_layers[] = { %s };"
                       % (i, ", ".join(str(n) for n in level.layers)))
    src.append("const NpLevel np_levels[] = {")
    for i, level in enumerate(build.levels):
        spawns = "np_level%d_spawns" % i if level.spawns else "0"
        capas = "np_level%d_layers" % i if level.layers else "0"
        src.append(
            "    { %s, %d, %d, np_level%d_cells, %s, %d, %d, %d, 0x%04x, %s, %d },"
            % (_c_string(level.name), level.width, level.height, i, spawns,
               len(level.spawns), level.start[0], level.start[1], level.background,
               capas, len(level.layers))
        )
    src.append("};")
    src.append("const uint16_t np_level_count = %d;" % len(build.levels))
    src.append("")

    return {
        "src/gamedata.h": "\n".join(header) + "\n",
        "src/gamedata.c": "\n".join(src) + "\n",
    }


ENGINE_FILES = [
    ("include/np_types.h", "src/np_types.h"),
    ("include/np_game.h", "src/np_game.h"),
    ("include/np_world.h", "src/np_world.h"),
    ("core/np_world.c", "src/np_world.c"),
    ("neogeo/np_video.h", "src/np_video.h"),
    ("neogeo/np_video.c", "src/np_video.c"),
    ("neogeo/np_hud.c", "src/np_hud.c"),
    ("neogeo/main.c", "src/main.c"),
]


def copy_engine(out_dir: str) -> List[str]:
    """Copia el motor dentro del proyecto generado (queda autocontenido)."""
    copied: List[str] = []
    for source, target in ENGINE_FILES:
        src_path = os.path.join(ENGINE_DIR, source)
        dst_path = os.path.join(out_dir, target)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copyfile(src_path, dst_path)
        copied.append(target)
    return copied


def write_rom_data(build: Build, out_dir: str, rom_id: str) -> Dict[str, int]:
    """Escribe las ROMs graficas (C1/C2 para sprites, S1 para el plano fix)."""
    rom_dir = os.path.join(out_dir, "rom")
    os.makedirs(rom_dir, exist_ok=True)
    written: Dict[str, int] = {}
    for suffix, data in (("c1", build.rom.c1), ("c2", build.rom.c2), ("s1", build.rom.s1)):
        # Las ROMs de la Neo Geo se rellenan hasta una potencia de dos.
        padded = bytearray(data)
        size = 1
        while size < max(len(padded), 0x20000):
            size <<= 1
        padded.extend(b"\x00" * (size - len(padded)))
        name = "%s-%s.%s" % (rom_id, suffix, suffix)
        path = os.path.join(rom_dir, name)
        with open(path, "wb") as fh:
            fh.write(bytes(padded))
        written[name] = len(padded)
    return written


def render_template(name: str, values: Dict[str, object]) -> str:
    with open(os.path.join(TEMPLATES_DIR, name), "r", encoding="utf-8") as fh:
        text = fh.read()
    for key, value in values.items():
        text = text.replace("@%s@" % key, str(value))
    return text


def generate_makefile(build: Build, rom_id: str) -> str:
    return render_template("Makefile.in", {
        "TITLE": build.project.title,
        "ROMID": rom_id,
        "FIXED_ONE": FIXED_ONE,
    })
