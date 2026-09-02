"""Paso intermedio: del `game.yaml` validado a datos listos para la ROM.

Aqui se decide todo lo que luego copian tal cual el generador de C
(`codegen.py`) y el preview del navegador (`preview.py`), de modo que las dos
salidas describan exactamente el mismo juego.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from . import gfx
from .errors import ProjectError
from .png import read_png
from .fixed import to_fixed
from .project import (
    Actor, Animation, BEHAVIOR_ID, ITEM_EFFECT_ID, Layer, Project, TILE_KIND_ID, TileDef,
)

# Las dos ultimas solo se usan en vista cenital (el heroe de espaldas y de
# frente); en lateral se quedan en su sustituto y no estorban.
ANIM_SLOTS = ["idle", "run", "jump", "fall", "hurt", "attack", "stair", "crouch",
              "up", "down"]
SIN_STEPS = 64


@dataclass
class ActorBuild:
    name: str
    actor: Actor
    sheet: gfx.Sheet
    anims: List[Animation]          # una por ranura, en el orden de ANIM_SLOTS
    shot_index: int = 0             # enemigos: su disparo + 1 (0 = no dispara)


@dataclass
class LayerBuild:
    """Capa de parallax ya troceada en tiles."""
    name: str
    layer: Layer
    cols: int
    rows: int
    tiles: List[int]                 # que dibujo va en cada casilla
    palette_index: int = 0
    frames: int = 0                  # dibujos distintos
    palette: object = None           # gfx.Palette de la capa
    dibujos: List[List[int]] = field(default_factory=list)   # indices de paleta


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
    music: int = 0                             # 0 = sin musica, si no indice + 1
    keys_needed: int = 0                       # llaves que pide la meta


@dataclass
class Build:
    project: Project
    rom: Optional[gfx.RomData]        # empaquetado de Neo Geo (lo pone su sistema)
    tiles: List[TileDef]
    tile_index: Dict[str, int]
    tileset: gfx.Sheet
    player: ActorBuild
    enemies: List[ActorBuild]
    items: List[ActorBuild]
    layers: List[LayerBuild]
    levels: List[LevelBuild]
    platforms: List[ActorBuild] = field(default_factory=list)
    breakables: List[ActorBuild] = field(default_factory=list)
    prisoners: List[ActorBuild] = field(default_factory=list)   # los rehenes
    attack: Optional[ActorBuild] = None       # el proyectil, si el juego lo lleva
    subs: List[ActorBuild] = field(default_factory=list)   # las armas secundarias
    # Los disparos de los enemigos que llevan `dispara:`. Van en su propia
    # lista porque cada uno tiene su dibujo, y el enemigo guarda su numero.
    enemy_shots: List[ActorBuild] = field(default_factory=list)
    music_order: List[str] = field(default_factory=list)   # nombres, en orden
    music_title: int = 0        # la del titulo, indice + 1 (0 = ninguna)
    music_boss: int = 0         # la del jefe, indice + 1 (0 = la del nivel)
    font: Dict[str, int] = field(default_factory=dict)
    hud_palette: int = 0
    sin_table: List[int] = field(default_factory=list)

    # --- lo rellena el sistema de destino (Neo Geo, Mega Drive, Amiga) ---
    sistema: object = None
    paletas: List[List[int]] = field(default_factory=list)   # colores ya en su formato
    tile_gfx: List[int] = field(default_factory=list)        # numero grafico por tile
    info: Dict[str, object] = field(default_factory=dict)    # datos sueltos del sistema
    pcm_bytes: int = 0                                       # lo que ocupan las muestras

    def actor_builds(self) -> List[ActorBuild]:
        """Todos los dibujos que hay que empaquetar, en un orden que **no
        cambia**: el jugador, los enemigos, los objetos, las plataformas
        moviles y, al final del todo, el proyectil. Lo que se anade va detras
        para no mover los indices de lo que ya estaba, que es lo que guardan
        los niveles."""
        todos = ([self.player] + self.enemies + self.items + self.platforms
                 + self.breakables + self.prisoners)
        if self.attack is not None:
            todos.append(self.attack)
        todos.extend(self.subs)
        todos.extend(self.enemy_shots)
        return todos

    def stats(self) -> Dict[str, int]:
        datos = {
            "capas": len(self.layers),
            "efectos": len(self.project.sound.efectos),
            "musicas": len(self.project.sound.musica),
            "paletas": len(self.paletas),
            "niveles": len(self.levels),
            "enemigos": len(self.enemies),
            "objetos": len(self.items),
            "plataformas": len(self.platforms),
            "rompibles": len(self.breakables),
            "prisioneros": len(self.prisoners),
            "bytes_mapas": sum(len(lv.cells) for lv in self.levels),
        }
        datos.update(self.info.get("stats", {}))     # lo que anada cada sistema
        return datos


def _resolve_anims(actor: Actor, where: str, frames_available: int) -> List[Animation]:
    """Rellena las 5 ranuras estandar aplicando los sustitutos razonables."""
    given = dict(actor.animations)
    if "idle" not in given:
        given["idle"] = Animation("idle", [0], 8, True)
    fallback = {"run": "idle", "jump": "idle", "fall": "jump", "hurt": "idle",
                "up": "run", "down": "run"}
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


def _load_actor(actor: Actor, where: str, root: str) -> ActorBuild:
    sheet = gfx.load_sheet(
        os.path.join(root, actor.sprite), where, actor.frame_w, actor.frame_h
    )
    if sheet.frames == 0:
        raise ProjectError("'%s' no tiene ningun fotograma" % actor.sprite, where=where)
    anims = _resolve_anims(actor, where, sheet.frames)
    return ActorBuild(name=actor.name, actor=actor, sheet=sheet, anims=anims)


def _load_layer(layer: Layer, root: str) -> LayerBuild:
    """Trocea la imagen de una capa en tiles de 16x16 (sin repetir los iguales)."""
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
    indices = gfx.quantize(image, lookup)
    cols = image.width // gfx.TILE_PX
    rows = image.height // gfx.TILE_PX
    if rows > 15:
        raise ProjectError(
            "'%s' tiene %d tiles de alto y la pantalla son 14" % (layer.image, rows),
            hint="recorta la imagen a 224 pixeles de alto como mucho",
            where=where,
        )
    # se guardan los dibujos de los tiles (indices de paleta) y, aparte, que
    # tile va en cada casilla, reutilizando los repetidos
    dibujos: List[List[int]] = []
    vistos: Dict[tuple, int] = {}
    tiles: List[int] = []
    for row in range(rows):
        for col in range(cols):
            tile: List[int] = []
            for y in range(gfx.TILE_PX):
                base = (row * gfx.TILE_PX + y) * image.width + col * gfx.TILE_PX
                tile.extend(indices[base:base + gfx.TILE_PX])
            clave = tuple(tile)
            if clave not in vistos:
                vistos[clave] = len(dibujos)
                dibujos.append(tile)
            tiles.append(vistos[clave])
    return LayerBuild(name=layer.name, layer=layer, cols=cols, rows=rows, tiles=tiles,
                      palette=palette, dibujos=dibujos, palette_index=0,
                      frames=len(dibujos))


def _sin_table() -> List[int]:
    return [to_fixed(math.sin(2 * math.pi * i / SIN_STEPS)) for i in range(SIN_STEPS)]


def build_project(project: Project) -> Build:
    """Lee graficos, tiles, niveles y sonido, sin atarse a ninguna maquina.

    El empaquetado para el hardware (formato de los tiles, paletas, ROMs) lo
    hace despues el sistema de destino: ver tools/ngplat/sistemas/.
    """
    rom = gfx.RomData()          # lo usa Neo Geo; los demas sistemas lo ignoran

    tileset = gfx.load_tileset(os.path.join(project.root, project.tileset.image))

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
        _load_layer(layer, project.root) for layer in project.layers.values()
    ]
    layer_index = {layer.name: i for i, layer in enumerate(layers)}

    player = _load_actor(project.player, "jugador", project.root)
    enemies = [
        _load_actor(enemy, "enemigos.%s" % name, project.root)
        for name, enemy in project.enemies.items()
    ]
    # Los disparos de los enemigos que llevan `dispara:`. Cada uno es un actor
    # mas -tiene su dibujo y su caja- y el enemigo se queda con su numero.
    enemy_shots: List[ActorBuild] = []
    for construido in enemies:
        disparo = getattr(construido.actor, "shot", None)
        if disparo is None:
            continue
        enemy_shots.append(_load_actor(disparo, disparo.name, project.root))
        construido.shot_index = len(enemy_shots)
    items = [
        _load_actor(item, "objetos.%s" % name, project.root)
        for name, item in project.items.items()
    ]
    platforms = [
        _load_actor(plat, "plataformas.%s" % name, project.root)
        for name, plat in project.platforms.items()
    ]
    breakables = [
        _load_actor(rom, "rompibles.%s" % name, project.root)
        for name, rom in project.breakables.items()
    ]
    attack = (_load_actor(project.player.attack, "jugador.ataque", project.root)
              if project.player.attack is not None
              and project.player.attack.sprite else None)
    subs = [_load_actor(arma, "jugador.secundarias.%s" % arma.name, project.root)
            for arma in project.player.subs]
    enemy_index = {b.name: i for i, b in enumerate(enemies)}
    item_index = {b.name: i for i, b in enumerate(items)}
    platform_index = {b.name: i for i, b in enumerate(platforms)}
    breakable_index = {b.name: i for i, b in enumerate(breakables)}
    prisoners = [
        _load_actor(pri, "prisioneros.%s" % name, project.root)
        for name, pri in project.prisoners.items()
    ]
    prisoner_index = {b.name: i for i, b in enumerate(prisoners)}

    music_order = list(project.sound.musica)
    music_index = {name: i + 1 for i, name in enumerate(music_order)}
    # las dos que no son de ningun nivel, con el mismo numero (indice + 1)
    music_title = music_index.get(project.sound.titulo, 0)
    music_boss = music_index.get(project.sound.jefe, 0)

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
                    elif name in platform_index:
                        kind, index = 3, platform_index[name]
                        actor = platforms[index].actor
                    elif name in breakable_index:
                        kind, index = 4, breakable_index[name]
                        actor = breakables[index].actor
                    elif name in prisoner_index:
                        # 8 = NP_KIND_PRISONER: el `kind` del spawn es el mismo
                        # numero que el de la entidad, no otro
                        kind, index = 8, prisoner_index[name]
                        actor = prisoners[index].actor
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
            music=music_index.get(level.music, 0),
            keys_needed=level.keys_needed,
        ))

    return Build(
        project=project, rom=rom, tiles=tiles, tile_index=tile_index, tileset=tileset,
        player=player, enemies=enemies, items=items, layers=layers, levels=levels,
        platforms=platforms, breakables=breakables, attack=attack, subs=subs,
        enemy_shots=enemy_shots, prisoners=prisoners,
        music_order=music_order, music_title=music_title, music_boss=music_boss,
        sin_table=_sin_table(),
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
        "boss": 1 if e.boss else 0,
        # el numero de su disparo **mas uno**; cero = este no dispara
        "shot": getattr(build, "shot_index", 0),
    }


def enemy_shot_values(build: ActorBuild) -> Dict[str, object]:
    """Los campos de NpEnemyShotDef: lo que tira un enemigo con `dispara:`."""
    s = build.actor          # type: ignore[assignment]
    return {
        "speed": to_fixed(s.speed), "range": int(s.range),
        "cooldown": s.cooldown, "damage": s.damage,
    }


def item_values(build: ActorBuild, sub_index: Optional[Dict[str, int]] = None
                ) -> Dict[str, object]:
    it = build.actor         # type: ignore[assignment]
    # con 'efecto: subarma', `amount` es el numero del arma a la que cambia:
    # el motor no conoce nombres, solo indices de np_subs
    cantidad = it.amount
    if it.effect == "weapon":
        cantidad = (sub_index or {}).get(it.weapon, 0)
    return {"score": it.score, "effect": ITEM_EFFECT_ID[it.effect],
            "amount": cantidad}


PLATFORM_AXIS_ID = {"x": 0, "y": 1}


def platform_values(build: ActorBuild) -> Dict[str, object]:
    pl = build.actor         # type: ignore[assignment]
    return {"speed": to_fixed(pl.speed), "distance": pl.distance,
            "axis": PLATFORM_AXIS_ID[pl.axis]}


SUB_KIND_ID = {"": 0, "line": 1, "arc": 2}


def sub_values(sb) -> Dict[str, object]:
    """Los campos de NpSubDef de un arma secundaria."""
    return {
        "kind": SUB_KIND_ID[sb.kind],
        "speed": to_fixed(sb.speed),
        "gravity": to_fixed(sb.gravity),
        "jump": to_fixed(sb.jump),
        "range": sb.range,
        "cooldown": sb.cooldown,
        "cost": sb.cost,
        "damage": sb.damage,
        "at_once": sb.at_once,
    }


def prisoner_values(build: ActorBuild) -> Dict[str, object]:
    """Los campos de NpPrisonerDef: lo que vale soltarlo y lo que corre."""
    pr = build.actor         # type: ignore[assignment]
    return {"score": pr.score, "speed": to_fixed(pr.speed), "escape": pr.escape}


def breakable_values(build: ActorBuild, item_index: Dict[str, int]) -> Dict[str, object]:
    """Los campos de NpBreakableDef. `drop` es el indice del objeto **mas uno**:
    el cero significa 'no suelta nada'."""
    b = build.actor          # type: ignore[assignment]
    return {"score": b.score, "health": b.health,
            "drop": item_index.get(b.drop, -1) + 1}


def player_values(project: Project) -> Dict[str, object]:
    p = project.player
    return {
        "speed": to_fixed(p.speed), "accel": to_fixed(p.accel),
        "friction": to_fixed(p.friction), "air_accel": to_fixed(p.air_accel),
        "jump": to_fixed(p.jump), "jump_cut": to_fixed(p.jump_cut),
        "gravity": to_fixed(p.gravity), "max_fall": to_fixed(p.max_fall),
        "bounce": to_fixed(p.bounce), "invuln": p.invuln,
        "knockback": to_fixed(p.knockback), "stun": p.stun,
        "stair_speed": to_fixed(p.stair_speed),
        "coyote": p.coyote, "jump_buffer": p.jump_buffer,
        "double_jump": 1 if p.double_jump else 0, "stomp": 1 if p.stomp else 0,
        "health": p.health,
        # cuanto baja el techo de la caja al agacharse; 0 = no se puede
        "crouch_drop": (p.box_h - p.crouch_h) if p.crouch else 0,
    }


ATTACK_KIND_ID = {"": 0, "shot": 1, "melee": 2}


def attack_values(project: Project) -> Dict[str, object]:
    """Los campos de NpAttackDef. Sin ataque salen todos a cero, que es lo que
    el motor entiende como 'este juego no lleva ataque'."""
    a = project.player.attack
    if a is None:
        return {"kind": 0, "speed": 0, "range": 0, "cooldown": 0,
                "duration": 0, "windup": 0, "damage": 0, "locks": 0,
                "levels": 0, "range_step": 0, "fx": 0}
    return {
        "kind": ATTACK_KIND_ID[a.kind],
        "speed": to_fixed(a.speed),
        "range": a.range,
        "cooldown": a.cooldown,
        "duration": a.duration,
        "windup": a.windup,
        "damage": a.damage,
        "locks": 1 if a.locks else 0,
        "levels": a.levels,
        "range_step": a.range_step,
        # con `tipo: golpe`, `sprite:` es el arma en si (el latigo) y se dibuja
        # delante del jugador mientras el golpe hace dano; sin sprite el golpe
        # es invisible, que es como estaba el kit
        "fx": 1 if a.sprite else 0,
    }


def tile_tables(build: Build) -> Tuple[List[int], List[int]]:
    """Tipo de cada tile y su numero grafico (lo pone el sistema de destino)."""
    kinds = [TILE_KIND_ID[t.kind] for t in build.tiles]
    graphics = build.tile_gfx or [t.index for t in build.tiles]
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
