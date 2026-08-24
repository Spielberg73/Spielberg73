"""Preview jugable en el navegador, generado a partir del mismo build.

El HTML resultante es un unico archivo autocontenido: lleva dentro los datos
del juego, los graficos ya convertidos a los colores reales de la Neo Geo y
`preview/np_core.js`, que es la traduccion literal del motor en C. Sirve para
iterar en segundos sin abrir el emulador.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Dict, List

from . import gfx
from .build import Build, actor_def_values, enemy_values, item_values, player_values, tile_tables
from .paths import PREVIEW_DIR, TEMPLATES_DIR
from .png import Image, encode_png, read_png


def _quantized_data_uri(path: str) -> str:
    """Devuelve el PNG con los colores que se veran en la consola."""
    image = read_png(path)
    pixels = []
    for px in image.pixels:
        if px[3] < 128:
            pixels.append((0, 0, 0, 0))
        else:
            r, g, b = gfx.ng_color_to_rgb(gfx.ng_color((px[0], px[1], px[2])))
            pixels.append((r, g, b, 255))
    data = encode_png(Image(image.width, image.height, pixels))
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _sheet_entry(path: str, frame_w: int, frame_h: int) -> Dict[str, object]:
    image = read_png(path)
    return {
        "url": _quantized_data_uri(path),
        "frame_w": frame_w,
        "frame_h": frame_h,
        "per_row": max(1, image.width // frame_w),
    }


def build_data(build: Build) -> Dict[str, object]:
    """Los mismos numeros que gamedata.c, en JSON."""
    project = build.project
    kinds, _ = tile_tables(build)
    sheets: Dict[str, object] = {}

    def actor_json(actor_build, sheet_name: str) -> Dict[str, object]:
        values = actor_def_values(actor_build)
        sheets[sheet_name] = _sheet_entry(
            os.path.join(project.root, actor_build.actor.sprite),
            actor_build.actor.frame_w, actor_build.actor.frame_h,
        )
        values["sheet"] = sheet_name
        return values

    sheets["__tiles__"] = _sheet_entry(
        os.path.join(project.root, project.tileset.image), 16, 16
    )

    player = dict(player_values(project))
    player["actor"] = actor_json(build.player, "player")

    enemies: List[Dict[str, object]] = []
    for i, enemy in enumerate(build.enemies):
        entry = dict(enemy_values(enemy))
        entry["actor"] = actor_json(enemy, "enemy%d" % i)
        entry["name"] = enemy.name
        enemies.append(entry)

    items: List[Dict[str, object]] = []
    for i, item in enumerate(build.items):
        entry = dict(item_values(item))
        entry["actor"] = actor_json(item, "item%d" % i)
        entry["name"] = item.name
        items.append(entry)

    layers = []
    for i, layer in enumerate(build.layers):
        nombre = "layer%d" % i
        sheets[nombre] = _sheet_entry(
            os.path.join(project.root, layer.layer.image), 16, 16
        )
        sheets[nombre]["per_row"] = layer.cols
        layers.append({
            "name": layer.name,
            "sheet": nombre,
            "cols": layer.cols,
            "rows": layer.rows,
            "speed_x": int(round(layer.layer.speed_x * 256)),
            "speed_y": int(round(layer.layer.speed_y * 256)),
            "offset_y": layer.layer.offset_y,
            "repeat": 1 if layer.layer.repeat else 0,
        })

    levels = []
    for level in build.levels:
        levels.append({
            "name": level.name,
            "width": level.width,
            "height": level.height,
            "cells": level.cells,
            "spawns": [list(s) for s in level.spawns],
            "start": list(level.start),
            "background": "#%02x%02x%02x" % gfx.ng_color_to_rgb(level.background),
            "layers": list(level.layers),
        })

    font = {char: list(rows) for char, rows in gfx.FONT_3X5.items()}

    return {
        "title": project.title,
        "author": project.author,
        "lives": project.lives,
        "time_limit": project.time_limit,
        "hud": project.hud,
        "player": player,
        "enemies": enemies,
        "items": items,
        # `gfx` aqui es el numero de tile dentro del tileset (en la ROM se
        # convierte al numero absoluto de la ROM C).
        "tiles": {"kind": kinds, "gfx": [t.index for t in build.tiles]},
        "levels": levels,
        "layers": layers,
        "sin": build.sin_table,
        "sheets": sheets,
        "font": font,
    }


def render_html(build: Build) -> str:
    with open(os.path.join(PREVIEW_DIR, "np_core.js"), "r", encoding="utf-8") as fh:
        core = fh.read()
    with open(os.path.join(TEMPLATES_DIR, "preview.html"), "r", encoding="utf-8") as fh:
        template = fh.read()
    data = json.dumps(build_data(build), separators=(",", ":"))
    html = template.replace("@CORE@", core)
    html = html.replace("@DATA@", data)
    html = html.replace("@TITLE@", build.project.title)
    html = html.replace("@AUTHOR@", build.project.author or "")
    return html


def write_preview(build: Build, path: str) -> str:
    html = render_html(build)
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    return path
