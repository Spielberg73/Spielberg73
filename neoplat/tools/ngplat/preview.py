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

from . import gfx, sistemas
from .claves import tabla_para_el_editor
from .build import (Build, actor_def_values, attack_values, enemy_values,
                    item_values, player_values, tile_tables)
from .paths import PREVIEW_DIR, TEMPLATES_DIR
from .png import Image, encode_png, read_png


def _leer_yaml(root: str) -> str:
    """Texto original del game.yaml (el editor devuelve una copia modificada)."""
    for nombre in ("game.yaml", "juego.yaml", "game.yml", "juego.yml"):
        ruta = os.path.join(root, nombre)
        if os.path.isfile(ruta):
            with open(ruta, "r", encoding="utf-8") as fh:
                return fh.read()
    return ""


def _quantized_data_uri(path: str, sistema) -> str:
    """Devuelve el PNG con los colores que se veran en la maquina de destino.

    Cada una redondea distinto: la Neo Geo usa 5 bits por canal, el Amiga 4 y
    la Mega Drive solo 3. El preview ensena el resultado de ese redondeo para
    que no haya sorpresas al compilar.
    """
    image = read_png(path)
    pixels = []
    cache = {}
    for px in image.pixels:
        if px[3] < 128:
            pixels.append((0, 0, 0, 0))
        else:
            clave = (px[0], px[1], px[2])
            if clave not in cache:
                cache[clave] = sistema.color_visible(clave)
            r, g, b = cache[clave]
            pixels.append((r, g, b, 255))
    data = encode_png(Image(image.width, image.height, pixels))
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _sheet_entry(path: str, frame_w: int, frame_h: int, sistema,
                 ruta: str = "") -> Dict[str, object]:
    image = read_png(path)
    return {
        "url": _quantized_data_uri(path, sistema),
        "frame_w": frame_w,
        "frame_h": frame_h,
        "per_row": max(1, image.width // frame_w),
        # el archivo dentro del proyecto, para que el editor de dibujos sepa
        # a donde tiene que devolverlo cuando lo guardes
        "ruta": ruta,
        "frames": max(1, (image.width // frame_w) * (image.height // frame_h)),
    }


def build_data(build: Build) -> Dict[str, object]:
    """Los mismos numeros que gamedata.c, en JSON."""
    project = build.project
    kinds, _ = tile_tables(build)
    sheets: Dict[str, object] = {}
    sistema = build.sistema or sistemas.obtener(project.system)

    def actor_json(actor_build, sheet_name: str) -> Dict[str, object]:
        values = actor_def_values(actor_build)
        sheets[sheet_name] = _sheet_entry(
            os.path.join(project.root, actor_build.actor.sprite),
            actor_build.actor.frame_w, actor_build.actor.frame_h, sistema,
            actor_build.actor.sprite,
        )
        values["sheet"] = sheet_name
        values["sprite"] = actor_build.actor.sprite      # ruta del PNG original
        return values

    sheets["__tiles__"] = _sheet_entry(
        os.path.join(project.root, project.tileset.image), 16, 16, sistema,
        project.tileset.image,
    )

    player = dict(player_values(project))
    player["actor"] = actor_json(build.player, "player")
    # el ataque: `kind` a cero quiere decir que el juego no lleva ninguno
    ataque = dict(attack_values(project))
    ataque["actor"] = (actor_json(build.attack, "attack") if build.attack is not None
                       else actor_def_values(build.player))
    player["attack"] = ataque

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
            os.path.join(project.root, layer.layer.image), 16, 16, sistema,
            layer.layer.image,
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

    # El editor necesita el mapa en texto y a que corresponde cada simbolo.
    tile_chars = [t.char for t in build.tiles]
    tile_index = {t.char: i for i, t in enumerate(build.tiles)}
    enemy_index = {b.name: i for i, b in enumerate(build.enemies)}
    item_index = {b.name: i for i, b in enumerate(build.items)}

    levels = []
    for level in build.levels:
        levels.append({
            "name": level.name,
            "width": level.width,
            "height": level.height,
            "cells": level.cells,
            "spawns": [list(s) for s in level.spawns],
            "start": list(level.start),
            "background": "#%02x%02x%02x" % sistema.color_visible(level.background_rgb),
            "layers": list(level.layers),
            "music": level.music,
        })
    for salida, original in zip(levels, project.levels):
        salida["rows"] = list(original.rows)
        salida["spawn_chars"] = {
            char: ({"kind": 0, "def": enemy_index[nombre]} if nombre in enemy_index
                   else {"kind": 1, "def": item_index[nombre]})
            for char, nombre in original.spawns.items()
            if nombre in enemy_index or nombre in item_index
        }

    font = {char: list(rows) for char, rows in gfx.FONT_3X5.items()}

    sonido = {
        "efectos": {
            nombre: [[round(paso.frecuencia, 2), paso.duracion, paso.volumen, paso.ruido]
                     for paso in efecto.pasos]
            for nombre, efecto in project.sound.efectos.items()
        },
        "musica": [
            {
                "nombre": nombre,
                "velocidad": tema.velocidad,
                "bucle": 1 if tema.bucle else 0,
                "pistas": [[[round(paso.frecuencia, 2), paso.duracion, paso.volumen]
                            for paso in pista] for pista in tema.pistas],
            }
            for nombre, tema in project.sound.musica.items()
        ],
        # bit del evento -> nombre del efecto que suena
        "eventos": {str(bit): nombre
                    for nombre, bit in project.sound.evento_bits().items()},
        # Las muestras digitales, en base64 y a su frecuencia. Van aparte de
        # los pasos porque no son notas: el navegador las toca tal cual.
        "muestras": {
            nombre: {"ritmo": efecto.muestra.ritmo,
                     "datos": base64.b64encode(efecto.muestra.datos).decode()}
            for nombre, efecto in project.sound.efectos.items()
            if efecto.muestra is not None
        },
    }

    return {
        "title": project.title,
        "author": project.author,
        "lives": project.lives,
        "players": project.players,
        "time_limit": project.time_limit,
        "hud": project.hud,
        "player": player,
        "enemies": enemies,
        "items": items,
        # `gfx` aqui es el numero de tile dentro del tileset (en la ROM se
        # convierte al numero absoluto de la ROM C).
        "tiles": {
            "kind": kinds,
            "gfx": [t.index for t in build.tiles],
            "chars": tile_chars,
            "index": tile_index,
        },
        "levels": levels,
        "layers": layers,
        "sonido": sonido,
        # el YAML original, para que el editor pueda devolverlo ya modificado
        "yaml": _leer_yaml(project.root),
        "claves": tabla_para_el_editor(),
        "nombres": {
            "enemigos": [b.name for b in build.enemies],
            "objetos": [b.name for b in build.items],
        },
        "camara_pantallas": 1 if project.camera == "pantallas" else 0,
        "amiga_modo": project.amiga_modo,
        "sistema": sistema.nombre,
        # lo que aguanta la maquina, para que el editor de dibujos pueda avisar
        # antes de que el compilador te lo diga
        "limites": {
            "colores": sistema.limites.colores_por_paleta - 1,
            "colores_en_pantalla": sistema.limites.colores_en_pantalla,
        },
        "sistemas": [{"id": m.nombre, "nombre": m.titulo, "binario": m.nombre_binario}
                     for m in sistemas.disponibles()],
        "sin": build.sin_table,
        "sheets": sheets,
        "font": font,
    }


def render_html(build: Build) -> str:
    with open(os.path.join(PREVIEW_DIR, "np_core.js"), "r", encoding="utf-8") as fh:
        core = fh.read()
    piezas = {}
    for nombre in ("np_editor.js", "np_yaml.js", "np_bot.js", "np_pixel.js"):
        with open(os.path.join(PREVIEW_DIR, nombre), "r", encoding="utf-8") as fh:
            piezas[nombre] = fh.read()
    with open(os.path.join(TEMPLATES_DIR, "preview.html"), "r", encoding="utf-8") as fh:
        template = fh.read()
    data = json.dumps(build_data(build), separators=(",", ":"))
    html = template.replace("@CORE@", core)
    html = html.replace("@EDITOR@", piezas["np_editor.js"])
    html = html.replace("@YAML@", piezas["np_yaml.js"])
    html = html.replace("@BOT@", piezas["np_bot.js"])
    html = html.replace("@PIXEL@", piezas["np_pixel.js"])
    html = html.replace("@DATA@", data)
    sistema = build.sistema or sistemas.obtener(build.project.system)
    html = html.replace("@TITLE@", build.project.title)
    html = html.replace("@SISTEMA@", sistema.titulo)
    html = html.replace("@AUTHOR@", build.project.author or "")
    return html


def write_preview(build: Build, path: str) -> str:
    html = render_html(build)
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)
    return path
