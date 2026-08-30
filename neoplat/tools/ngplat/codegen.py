"""Generacion del proyecto en C.

Lo que hay aqui es lo que **comparten todas las maquinas**: las tablas del
juego (niveles, actores, fisica, sonido) tal y como las lee el motor. Lo que
cambia de una consola a otra -- el formato de los graficos, las ROMs, el
Makefile -- lo pone cada sistema de tools/ngplat/sistemas/.
"""

from __future__ import annotations

import os
import shutil
from typing import Dict, List, Sequence

from .sonido import EVENTOS
from .build import (
    ANIM_SLOTS, Build, actor_def_values, attack_values, breakable_values,
    enemy_values, item_values, layer_values, platform_values, player_values,
    sub_values, tile_tables,
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


def _actor_vacio() -> str:
    """Un NpActorDef a cero, para las tablas que no tienen ningun elemento.

    Las ranuras de animacion se cuentan a partir de ANIM_SLOTS y no a mano:
    anadir una (como paso con la de atacar) rompia esto en silencio."""
    ranuras = ", ".join(["{ 0, 0, 0, 0 }"] * len(ANIM_SLOTS))
    return "{ 0, 0, 1, 1, 0, 0, 16, 16, { %s } }" % ranuras


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
    palettes = build.paletas

    header = [HEADER_NOTE, "#ifndef GAMEDATA_H", "#define GAMEDATA_H", "",
              '#include "np_game.h"', ""]
    header.append("#define NP_PALETTE_COUNT %d" % len(palettes))
    header.append("#define NP_HUD_PALETTE %d" % build.hud_palette)
    header.append("#define NP_MAX_LEVEL_TILES_W %d" % max(l.width for l in build.levels))
    header.append("#define NP_HUD_ENABLED %d" % (1 if project.hud else 0))
    header.append("#define NP_LAYER_COUNT %d" % len(build.layers))
    header.append("#define NP_MUSIC_COUNT %d" % len(build.music_order))
    header.append("#define NP_SOUND_ENABLED %d"
                  % (1 if (build.project.sound.efectos or build.project.sound.musica) else 0))
    header.append("#define NP_MAX_LEVEL_LAYERS %d"
                  % max([len(l.layers) for l in build.levels] + [0]))
    header.append("")
    header.append("extern const uint16_t np_palettes[NP_PALETTE_COUNT][16];")
    header.append("extern const uint8_t np_font_index[128];")
    # cada sistema anade lo suyo (tablas de graficos, tamanos...)
    for linea in build.info.get("cabecera", []):
        header.append(linea)
    header.append("")
    header.append("#endif /* GAMEDATA_H */")

    src: List[str] = [HEADER_NOTE, '#include "gamedata.h"', ""]
    src.append("const char np_game_title[] = %s;" % _c_string(project.title))
    src.append("const char np_game_author[] = %s;" % _c_string(project.author))
    src.append("const uint8_t np_start_lives = %d;" % project.lives)
    src.append("const uint8_t np_player_count = %d;" % project.players)
    src.append("const uint16_t np_time_limit = %d;" % project.time_limit)
    src.append("const uint8_t np_camara_pantallas = %d;"
               % (1 if project.camera == "pantallas" else 0))
    src.append("const uint16_t np_tileset_first_tile = %d;" % build.tileset.first_tile)
    src.append("const uint8_t np_tileset_palette = %d;" % build.tileset.palette_index)
    src.append("")

    src.append("/* Paletas: 16 colores por paleta, el 0 es transparente. */")
    src.append("const uint16_t np_palettes[NP_PALETTE_COUNT][16] = {")
    for pal in palettes:
        words = ", ".join("0x%04x" % w for w in pal)
        src.append("    { %s }," % words)
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

    orden_efectos = [nombre for nombre in EVENTOS if nombre in project.sound.efectos]
    comandos = [
        (orden_efectos.index(nombre) + 1) if nombre in orden_efectos else 0
        for nombre in EVENTOS
    ]
    src.append("/* Orden de sonido que se manda al Z80 por cada evento. */")
    src.append("const uint8_t np_sfx_command[NP_SFX_SLOTS] = {")
    src.append(_array(comandos))
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
    if build.attack is not None:
        src.append(_anim_arrays("np_attack", build.attack))
    for i, arma in enumerate(build.subs):
        src.append(_anim_arrays("np_sub%d" % i, arma))
    pv = player_values(project)
    src.append("const NpPlayerDef np_player_def = {")
    src.append(_actor_def("np_player", actor_def_values(build.player)) + ",")
    src.append("    %d, %d, %d, %d," % (pv["speed"], pv["accel"], pv["friction"], pv["air_accel"]))
    src.append("    %d, %d, %d, %d, %d," % (pv["jump"], pv["jump_cut"], pv["gravity"],
                                            pv["max_fall"], pv["bounce"]))
    src.append("    %d, %d," % (pv["knockback"], pv["stair_speed"]))
    src.append("    %d, %d," % (pv["invuln"], pv["stun"]))
    src.append("    %d, %d, %d, %d, %d, %d," % (pv["coyote"], pv["jump_buffer"],
                                                pv["double_jump"], pv["stomp"],
                                                pv["health"], pv["crouch_drop"]))
    # el ataque: su dibujo es el ultimo de la lista de actores, si lo hay
    av = attack_values(project)
    src.append("    /* ataque */")
    src.append("    {")
    if build.attack is not None:
        src.append(_actor_def("np_attack", actor_def_values(build.attack)) + ",")
    else:
        src.append("    " + _actor_vacio() + ",")
    src.append("        %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d"
               % (av["speed"], av["range"], av["cooldown"], av["duration"],
                  av["windup"], av["range_step"], av["levels"], av["kind"],
                  av["damage"], av["locks"], av["fx"]))
    src.append("    }")
    src.append("};")
    src.append("")

    # --- las armas secundarias: van en su propia tabla porque un juego puede
    # llevar varias y se cambian cogiendo el objeto que las suelta
    src.append("/* Armas secundarias, en el orden de 'secundarias:'. */")
    src.append("const NpSubDef np_subs[] = {")
    if not build.subs:
        src.append("    { %s, 0, 0, 0, 0, 0, 0, 0, 0, 0 }" % _actor_vacio())
    for i, arma in enumerate(build.subs):
        sv = sub_values(arma.actor)
        src.append("    {")
        src.append(_actor_def("np_sub%d" % i, actor_def_values(arma)) + ",")
        src.append("        %d, %d, %d, %d, %d, %d, %d, %d, %d"
                   % (sv["speed"], sv["gravity"], sv["jump"], sv["range"],
                      sv["cooldown"], sv["kind"], sv["cost"], sv["damage"],
                      sv["at_once"]))
        src.append("    }," if i + 1 < len(build.subs) else "    }")
    src.append("};")
    src.append("const uint8_t np_sub_count = %d;" % len(build.subs))
    src.append("")

    # --- enemigos
    for i, enemy in enumerate(build.enemies):
        src.append("/* enemigo %d: %s */" % (i, enemy.name))
        src.append(_anim_arrays("np_enemy%d" % i, enemy))
    src.append("const NpEnemyDef np_enemies[] = {")
    if not build.enemies:
        src.append("    { %s, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1 }" % _actor_vacio())
    for i, enemy in enumerate(build.enemies):
        ev = enemy_values(enemy)
        src.append("    {")
        src.append(_actor_def("np_enemy%d" % i, actor_def_values(enemy)) + ",")
        src.append("        %d, %d, %d, %d, %d," % (ev["speed"], ev["gravity"], ev["jump"],
                                                    ev["range"], ev["amplitude"]))
        src.append("        %d, %d, %d," % (ev["period"], ev["interval"], ev["score"]))
        src.append("        %d, %d, %d, %d, %d," % (ev["behavior"], ev["health"],
                                                    ev["damage"], ev["stompable"],
                                                    ev["edge_turn"]))
        src.append("        %d" % ev["boss"])
        src.append("    }," if i + 1 < len(build.enemies) else "    }")
    src.append("};")
    src.append("const uint16_t np_enemy_count = %d;" % len(build.enemies))
    src.append("")

    # --- objetos
    # el objeto que cambia de arma guarda el numero del arma, no su nombre: el
    # motor no conoce nombres
    sub_index = {arma.name: i for i, arma in enumerate(build.subs)}
    for i, item in enumerate(build.items):
        src.append("/* objeto %d: %s */" % (i, item.name))
        src.append(_anim_arrays("np_item%d" % i, item))
    src.append("const NpItemDef np_items[] = {")
    if not build.items:
        src.append("    { %s, 0, 0, 1 }" % _actor_vacio())
    for i, item in enumerate(build.items):
        iv = item_values(item, sub_index)
        src.append("    {")
        src.append(_actor_def("np_item%d" % i, actor_def_values(item)) + ",")
        src.append("        %d, %d, %d" % (iv["score"], iv["effect"], iv["amount"]))
        src.append("    }," if i + 1 < len(build.items) else "    }")
    src.append("};")
    src.append("const uint16_t np_item_count = %d;" % len(build.items))
    src.append("")

    # --- plataformas moviles
    for i, plat in enumerate(build.platforms):
        src.append("/* plataforma %d: %s */" % (i, plat.name))
        src.append(_anim_arrays("np_plat%d" % i, plat))
    src.append("const NpPlatformDef np_platforms[] = {")
    if not build.platforms:
        src.append("    { %s, 0, 0, 0 }" % _actor_vacio())
    for i, plat in enumerate(build.platforms):
        pv = platform_values(plat)
        src.append("    {")
        src.append(_actor_def("np_plat%d" % i, actor_def_values(plat)) + ",")
        src.append("        %d, %d, %d" % (pv["speed"], pv["distance"], pv["axis"]))
        src.append("    }," if i + 1 < len(build.platforms) else "    }")
    src.append("};")
    src.append("const uint16_t np_platform_count = %d;" % len(build.platforms))
    src.append("")

    # --- rompibles (los candelabros)
    item_index = {b.name: i for i, b in enumerate(build.items)}
    for i, rom in enumerate(build.breakables):
        src.append("/* rompible %d: %s */" % (i, rom.name))
        src.append(_anim_arrays("np_rompible%d" % i, rom))
    src.append("const NpBreakableDef np_breakables[] = {")
    if not build.breakables:
        src.append("    { %s, 0, 0, 1 }" % _actor_vacio())
    for i, rom in enumerate(build.breakables):
        bv = breakable_values(rom, item_index)
        src.append("    {")
        src.append(_actor_def("np_rompible%d" % i, actor_def_values(rom)) + ",")
        src.append("        %d, %d, %d" % (bv["score"], bv["drop"], bv["health"]))
        src.append("    }," if i + 1 < len(build.breakables) else "    }")
    src.append("};")
    src.append("const uint16_t np_breakable_count = %d;" % len(build.breakables))
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
            "    { %s, %d, %d, np_level%d_cells, %s, %d, %d, %d, 0x%04x, %s, %d, %d, %d },"
            % (_c_string(level.name), level.width, level.height, i, spawns,
               len(level.spawns), level.start[0], level.start[1], level.background,
               capas, len(level.layers), level.music, level.keys_needed)
        )
    src.append("};")
    src.append("const uint16_t np_level_count = %d;" % len(build.levels))
    src.append("")

    return {
        "src/gamedata.h": "\n".join(header) + "\n",
        "src/gamedata.c": "\n".join(src) + "\n",
    }


def copy_engine(out_dir: str, sistema=None) -> List[str]:
    """Copia el motor dentro del proyecto generado (queda autocontenido)."""
    if sistema is None:
        from .sistemas import obtener
        sistema = obtener("neogeo")
    copied: List[str] = []
    for source, target in sistema.archivos_motor:
        src_path = os.path.join(ENGINE_DIR, source)
        dst_path = os.path.join(out_dir, target)
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copyfile(src_path, dst_path)
        copied.append(target)
    return copied


def render_template(name: str, values: Dict[str, object]) -> str:
    with open(os.path.join(TEMPLATES_DIR, name), "r", encoding="utf-8") as fh:
        text = fh.read()
    for key, value in values.items():
        text = text.replace("@%s@" % key, str(value))
    return text


def generar_para_sistema(build: Build, out_dir: str, sistema, rom_id: str) -> Dict[str, int]:
    """Escribe todo el proyecto: tablas comunes, motor y lo propio del sistema."""
    salida = sistema.generar(build, rom_id)

    for relativo, contenido in generate_gamedata(build).items():
        _escribir_texto(os.path.join(out_dir, relativo), contenido)
    copy_engine(out_dir, sistema)
    for relativo, contenido in salida.archivos.items():
        _escribir_texto(os.path.join(out_dir, relativo), contenido)
    binarios: Dict[str, int] = {}
    for relativo, datos in salida.binarios.items():
        ruta = os.path.join(out_dir, relativo)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "wb") as fh:
            fh.write(datos)
        binarios[relativo] = len(datos)
    return binarios, salida


def _escribir_texto(ruta: str, contenido: str) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(contenido)
