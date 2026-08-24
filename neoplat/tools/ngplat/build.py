"""Paso intermedio: del `game.yaml` validado a datos listos para la ROM.

Aqui se decide todo lo que luego copian tal cual el generador de C
(`codegen.py`) y el preview del navegador (`preview.py`), de modo que las dos
salidas describan exactamente el mismo juego.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from . import gfx
from .errors import ProjectError
from .png import read_png
from .fixed import to_fixed
from .project import (
    Actor, Animation, BEHAVIOR_ID, ITEM_EFFECT_ID, Layer, Project, TILE_KIND_ID, TileDef,
)

ANIM_SLOTS = ["idle", "run", "jump", "fall", "hurt"]
SIN_STEPS = 64


@dataclass
class ActorBuild:
    name: str
    actor: Actor
    sheet: gfx.Sheet
    anims: List[Animation]          # 5 ranuras, en el orden de ANIM_SLOTS


@dataclass
class LayerBuild:
    """Capa de parallax ya troceada en tiles."""
    name: str
    layer: Layer
    cols: int
    rows: int
    tiles: List[int]          # cols*rows numeros de tile en la ROM C
    palette_index: int
    frames: int               # tiles distintos que ha ocupado en la ROM


@dataclass
class LevelBuild:
    name: str
    width: int
    height: int
    cells: List[int]
    spawns: List[Tuple[int, int, int, int]]   # x, y, kind, def
    start: Tuple[int, int]
    background: int                            # color Neo Geo
    background_rgb: Tuple[int, int, int]
    layers: List[int] = field(default_factory=list)   # indices en Build.layers


@dataclass
class Build:
    project: Project
    rom: gfx.RomData
    tiles: List[TileDef]
    tile_index: Dict[str, int]
    tileset: gfx.Sheet
    player: ActorBuild
    enemies: List[ActorBuild]
    items: List[ActorBuild]
    layers: List[LayerBuild]
    levels: List[LevelBuild]
    font: Dict[str, int] = field(default_factory=dict)
    hud_palette: int = 0
    sin_table: List[int] = field(default_factory=list)

    def actor_builds(self) -> List[ActorBuild]:
        return [self.player] + self.enemies + self.items

    def stats(self) -> Dict[str, int]:
        return {
            "capas": len(self.layers),
            "tiles_sprite": self.rom.sprite_tiles,
            "tiles_fix": self.rom.fix_tiles,
            "paletas": len(self.rom.palettes),
            "niveles": len(self.levels),
            "enemigos": len(self.enemies),
            "objetos": len(self.items),
            "bytes_c1": len(self.rom.c1),
            "bytes_c2": len(self.rom.c2),
            "bytes_s1": len(self.rom.s1),
            "bytes_mapas": sum(len(lv.cells) for lv in self.levels),
        }


def _resolve_anims(actor: Actor, where: str, frames_available: int) -> List[Animation]:
    """Rellena las 5 ranuras estandar aplicando los sustitutos razonables."""
    given = dict(actor.animations)
    if "idle" not in given:
        given["idle"] = Animation("idle", [0], 8, True)
    fallback = {"run": "idle", "jump": "idle", "fall": "jump", "hurt": "idle"}
    out: List[Animation] = []
    for slot in ANIM_SLOTS:
        anim = given.get(slot)
        seen = set()
        while anim is None and slot in fallback and slot not in seen:
            seen.add(slot)
            slot = fallback[slot]
            anim = given.get(slot)
        if anim is None:
            anim = given["idle"]
        for frame in anim.frames:
            if frame >= frames_available:
                raise ProjectError(
                    "la animacion '%s' usa el fotograma %d y la hoja solo tiene %d"
                    % (anim.name, frame, frames_available),
                    hint="los fotogramas se numeran desde 0",
                    where=where,
                )
        out.append(anim)
    return out


def _load_actor(actor: Actor, where: str, rom: gfx.RomData, root: str) -> ActorBuild:
    sheet = gfx.load_sheet(
        os.path.join(root, actor.sprite), where, actor.frame_w, actor.frame_h
    )
    if sheet.frames == 0:
        raise ProjectError("'%s' no tiene ningun fotograma" % actor.sprite, where=where)
    rom.pack_sheet(sheet)
    anims = _resolve_anims(actor, where, sheet.frames)
    return ActorBuild(name=actor.name, actor=actor, sheet=sheet, anims=anims)


def _load_layer(layer: Layer, rom: gfx.RomData, root: str) -> LayerBuild:
    """Trocea la imagen de una capa en tiles de 16x16, reutilizando repetidos."""
    where = "fondos.%s" % layer.name
    image = read_png(os.path.join(root, layer.image))
    if image.width % gfx.TILE_PX or image.height % gfx.TILE_PX:
        raise ProjectError(
            "'%s' mide %dx%d y las capas de fondo se dividen en tiles de 16x16"
            % (layer.image, image.width, image.height),
            hint="usa medidas multiplos de 16",
            where=where,
        )
    palette, lookup = gfx.build_palette(image, layer.name, where)
    palette_index = rom.add_palette(palette)
    indices = gfx.quantize(image, lookup)
    cols = image.width // gfx.TILE_PX
    rows = image.height // gfx.TILE_PX
    if rows > 15:
        raise ProjectError(
            "'%s' tiene %d tiles de alto y la pantalla son 14" % (layer.image, rows),
            hint="recorta la imagen a 224 pixeles de alto como mucho",
            where=where,
        )
    tiles: List[int] = []
    antes = rom.sprite_tiles
    for row in range(rows):
        for col in range(cols):
            tile: List[int] = []
            for y in range(gfx.TILE_PX):
                base = (row * gfx.TILE_PX + y) * image.width + col * gfx.TILE_PX
                tile.extend(indices[base:base + gfx.TILE_PX])
            tiles.append(rom.add_sprite_tile_shared(tile))
    return LayerBuild(name=layer.name, layer=layer, cols=cols, rows=rows, tiles=tiles,
                      palette_index=palette_index, frames=rom.sprite_tiles - antes)


def _sin_table() -> List[int]:
    return [to_fixed(math.sin(2 * math.pi * i / SIN_STEPS)) for i in range(SIN_STEPS)]


def build_project(project: Project) -> Build:
    """Empaqueta graficos, tiles y niveles. Lanza ProjectError si algo no cabe."""
    rom = gfx.RomData()

    tileset = gfx.load_tileset(os.path.join(project.root, project.tileset.image))
    rom.pack_sheet(tileset)

    tiles = sorted(project.tiles.values(), key=lambda t: t.char)
    if len(tiles) > 255:
        raise ProjectError("hay %d simbolos de tile y el maximo es 255" % len(tiles))
    tile_index = {t.char: i for i, t in enumerate(tiles)}
    for tile in tiles:
        if tile.index >= tileset.frames:
            raise ProjectError(
                "el simbolo '%s' usa el tile %d y el tileset solo tiene %d"
                % (tile.char, tile.index, tileset.frames),
                hint="los tiles se numeran desde 0, de izquierda a derecha",
                where="tiles.leyenda",
            )

    layers: List[LayerBuild] = [
        _load_layer(layer, rom, project.root) for layer in project.layers.values()
    ]
    layer_index = {layer.name: i for i, layer in enumerate(layers)}

    player = _load_actor(project.player, "jugador", rom, project.root)
    enemies = [
        _load_actor(enemy, "enemigos.%s" % name, rom, project.root)
        for name, enemy in project.enemies.items()
    ]
    items = [
        _load_actor(item, "objetos.%s" % name, rom, project.root)
        for name, item in project.items.items()
    ]
    enemy_index = {b.name: i for i, b in enumerate(enemies)}
    item_index = {b.name: i for i, b in enumerate(items)}

    empty_index = tile_index.get(".", 0)
    levels: List[LevelBuild] = []
    for level in project.levels:
        width = len(level.rows[0])
        height = len(level.rows)
        cells: List[int] = []
        spawns: List[Tuple[int, int, int, int]] = []
        for y, row in enumerate(level.rows):
            for x, ch in enumerate(row):
                if ch in level.spawns or ch == "P":
                    cells.append(empty_index)
                    if ch == "P":
                        continue
                    name = level.spawns[ch]
                    if name in enemy_index:
                        kind, index = 0, enemy_index[name]
                        actor = enemies[index].actor
                    else:
                        kind, index = 1, item_index[name]
                        actor = items[index].actor
                    px = x * 16 + (16 - actor.box_w) // 2
                    py = y * 16 + 16 - actor.box_h
                    spawns.append((max(0, px), max(0, py), kind, index))
                else:
                    cells.append(tile_index[ch])
        if len(spawns) > 64:
            raise ProjectError(
                "el nivel '%s' tiene %d enemigos y objetos; el maximo por nivel es 64"
                % (level.name, len(spawns)),
                hint="reparte el contenido en varios niveles",
            )
        sx = level.start[0] * 16 + (16 - project.player.box_w) // 2
        sy = level.start[1] * 16 + 16 - project.player.box_h
        levels.append(LevelBuild(
            name=level.name.upper()[:20],
            width=width, height=height, cells=cells, spawns=spawns,
            start=(max(0, sx), max(0, sy)),
            background=gfx.ng_color(level.background),
            background_rgb=level.background,
            layers=[layer_index[n] for n in level.layers],
        ))

    font = gfx.build_font(rom)
    hud_palette = rom.add_palette(gfx.hud_palette())

    return Build(
        project=project, rom=rom, tiles=tiles, tile_index=tile_index, tileset=tileset,
        player=player, enemies=enemies, items=items, layers=layers, levels=levels,
        font=font, hud_palette=hud_palette, sin_table=_sin_table(),
    )


# ------------------------------------------------------ ayudas para la salida

def actor_def_values(build: ActorBuild) -> Dict[str, object]:
    """Los campos de NpActorDef listos para escribir (C o JSON)."""
    actor = build.actor
    sheet = build.sheet
    return {
        "first_tile": sheet.first_tile,
        "palette": sheet.palette_index,
        "cols": sheet.cols,
        "rows": sheet.rows,
        "box_x": actor.box_x,
        "box_y": actor.box_y,
        "box_w": actor.box_w,
        "box_h": actor.box_h,
        "frames": sheet.frames,
        "frame_w": actor.frame_w,
        "frame_h": actor.frame_h,
        "anims": [
            {"frames": list(a.frames), "count": len(a.frames),
             "speed": a.speed, "loop": 1 if a.loop else 0}
            for a in build.anims
        ],
    }


def enemy_values(build: ActorBuild) -> Dict[str, object]:
    e = build.actor          # type: ignore[assignment]
    return {
        "speed": to_fixed(e.speed), "gravity": to_fixed(e.gravity),
        "jump": to_fixed(e.jump), "range": to_fixed(e.range),
        "amplitude": to_fixed(e.amplitude),
        "period": e.period, "interval": e.interval, "score": e.score,
        "behavior": BEHAVIOR_ID[e.behavior], "health": e.health, "damage": e.damage,
        "stompable": 1 if e.stompable else 0, "edge_turn": 1 if e.edge_turn else 0,
    }


def item_values(build: ActorBuild) -> Dict[str, object]:
    it = build.actor         # type: ignore[assignment]
    return {"score": it.score, "effect": ITEM_EFFECT_ID[it.effect], "amount": it.amount}


def player_values(project: Project) -> Dict[str, object]:
    p = project.player
    return {
        "speed": to_fixed(p.speed), "accel": to_fixed(p.accel),
        "friction": to_fixed(p.friction), "air_accel": to_fixed(p.air_accel),
        "jump": to_fixed(p.jump), "jump_cut": to_fixed(p.jump_cut),
        "gravity": to_fixed(p.gravity), "max_fall": to_fixed(p.max_fall),
        "bounce": to_fixed(p.bounce), "invuln": p.invuln,
        "coyote": p.coyote, "jump_buffer": p.jump_buffer,
        "double_jump": 1 if p.double_jump else 0, "stomp": 1 if p.stomp else 0,
        "health": p.health,
    }


def tile_tables(build: Build) -> Tuple[List[int], List[int]]:
    kinds = [TILE_KIND_ID[t.kind] for t in build.tiles]
    graphics = [build.tileset.first_tile + t.index for t in build.tiles]
    return kinds, graphics


def layer_values(build: LayerBuild) -> Dict[str, object]:
    """Los campos de NpLayer listos para escribir (C o JSON)."""
    return {
        "cols": build.cols,
        "rows": build.rows,
        # velocidades en 8.8: 256 = se mueve igual que el escenario
        "speed_x": int(round(build.layer.speed_x * 256)),
        "speed_y": int(round(build.layer.speed_y * 256)),
        "offset_y": build.layer.offset_y,
        "repeat": 1 if build.layer.repeat else 0,
        "palette": build.palette_index,
        "tiles": list(build.tiles),
    }
