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
    Actor, Animation, BEHAVIOR_ID, ITEM_EFFECT_ID, Layer, Project, SALA,
    TILE_KIND_ID, TileDef,
)

# Lo que ocupa una sala en la pantalla, en tiles de 16x16. Es una pantalla
# entera: la camara de la vista isometrica salta de habitacion en habitacion.
SALA_TILES_X = 20
SALA_TILES_Y = 14
# Cuantas entidades caben (NP_MAX_ENTITIES del motor). Los cubos de la sala que
# se esta viendo salen de las que sobran despues de los enemigos y los objetos.
MAX_ENTIDADES = 64

# Las dos ultimas solo se usan en vista cenital (el heroe de espaldas y de
# frente); en lateral se quedan en su sustituto y no estorban.
ANIM_SLOTS = ["idle", "run", "jump", "fall", "hurt", "attack", "stair", "crouch",
              "up", "down", "remate", "patada"]
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
    # Lo que se ve, en tiles de pantalla. En casi todos los juegos es el propio
    # mapa; en la vista isometrica es el dibujo de las salas (20x14 por sala).
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
    # Lo que mide el mapa que se pisa, en casillas. Fuera de la isometrica vale
    # lo mismo que width y height.
    cells_w: int = 0
    cells_h: int = 0
    # Solo isometrica: el dibujo del suelo de las salas, ya en numeros de tile
    # de la maquina. Vacio en las demas vistas.
    fondo: List[int] = field(default_factory=list)


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
    blocks: List[ActorBuild] = field(default_factory=list)   # los cubos
    breakables: List[ActorBuild] = field(default_factory=list)
    prisoners: List[ActorBuild] = field(default_factory=list)   # los rehenes
    generators: List[ActorBuild] = field(default_factory=list)  # los nidos
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
    # Cuantos numeros de tile ocupa cada tile del tileset en esta maquina: uno
    # en casi todas y cuatro en la Mega Drive, que trabaja con celdas de 8x8.
    # Hace falta para poder numerar cualquier tile del tileset -y no solo los
    # de la leyenda-, que es lo que pide el dibujo de una sala isometrica.
    tile_gfx_paso: int = 1
    # De cada tile del PNG del tileset, cual es su sitio en la hoja ya
    # compactada. Un tileset puede traer el mismo dibujo repetido -el suelo de
    # una sala isometrica son 128 tiles y casi todos son la misma losa- y
    # guardarlos una sola vez ahorra ROM en todas las maquinas y es lo que hace
    # que quepan en la PCG del X68000, que solo tiene 192 patrones. Fuera es la
    # lista 0, 1, 2... y no cambia nada.
    tileset_remap: List[int] = field(default_factory=list)
    info: Dict[str, object] = field(default_factory=dict)    # datos sueltos del sistema
    pcm_bytes: int = 0                                       # lo que ocupan las muestras

    def actor_builds(self) -> List[ActorBuild]:
        """Todos los dibujos que hay que empaquetar, en un orden que **no
        cambia**: el jugador, los enemigos, los objetos, las plataformas
        moviles y, al final del todo, el proyectil. Lo que se anade va detras
        para no mover los indices de lo que ya estaba, que es lo que guardan
        los niveles."""
        todos = ([self.player] + self.enemies + self.items + self.platforms
                 + self.breakables + self.prisoners + self.generators)
        if self.attack is not None:
            todos.append(self.attack)
        todos.extend(self.subs)
        todos.extend(self.enemy_shots)
        todos.extend(self.blocks)
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
            "generadores": len(self.generators),
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
                "up": "run", "down": "run", "remate": "attack",
                # sin dibujo de patada se pega en el aire con el de siempre
                "patada": "attack"}
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

    # Los tiles repetidos se guardan una sola vez. El suelo de una sala
    # isometrica son 128 tiles del PNG y casi todos son la misma losa; con esto
    # se quedan en una treintena, que es lo que hace que quepan en la PCG del
    # X68000. `tileset_remap` dice donde acabo cada tile del PNG: fuera de ahi
    # nadie lo mira, porque en un tileset normal no se repite nada y la lista
    # sale 0, 1, 2...
    vistos, unicos, tileset_remap = {}, [], []
    for tile in tileset.tiles:
        clave = tuple(tile)
        if clave not in vistos:
            vistos[clave] = len(unicos)
            unicos.append(tile)
        tileset_remap.append(vistos[clave])
    tileset.tiles = unicos
    tileset.frames = len(unicos)

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
    blocks = [
        _load_actor(cubo, "cubos.%s" % name, project.root)
        for name, cubo in project.blocks.items()
    ]
    block_index = {b.name: i for i, b in enumerate(blocks)}
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
    generators = [
        _load_actor(gen, "generadores.%s" % name, project.root)
        for name, gen in project.generators.items()
    ]
    generator_index = {b.name: i for i, b in enumerate(generators)}

    music_order = list(project.sound.musica)
    music_index = {name: i + 1 for i, name in enumerate(music_order)}
    # las dos que no son de ningun nivel, con el mismo numero (indice + 1)
    music_title = music_index.get(project.sound.titulo, 0)
    music_boss = music_index.get(project.sound.jefe, 0)

    empty_index = tile_index.get(".", 0)
    iso = project.view == "iso"
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
                    elif name in generator_index:
                        kind, index = 9, generator_index[name]   # NP_KIND_GENERATOR
                        actor = generators[index].actor
                    else:
                        kind, index = 1, item_index[name]
                        actor = items[index].actor
                    px = x * 16 + (16 - actor.box_w) // 2
                    # En la isometrica la caja es la **planta** de lo que
                    # ocupa, no un cuerpo apoyado en una linea de suelo: va
                    # centrada en la casilla por los dos ejes.
                    if iso:
                        py = y * 16 + (16 - actor.box_h) // 2
                    else:
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
        sy = (level.start[1] * 16 + (16 - project.player.box_h) // 2 if iso
              else level.start[1] * 16 + 16 - project.player.box_h)
        fondo: List[int] = []
        vista_w, vista_h = width, height
        if iso:
            fondo, vista_w, vista_h = _fondo_de_salas(project, tileset,
                                                      len(tileset_remap))
            _cubos_por_sala(project, level, width, height, len(spawns))
        levels.append(LevelBuild(
            name=level.name.upper()[:20],
            width=vista_w, height=vista_h, cells=cells, spawns=spawns,
            cells_w=width, cells_h=height, fondo=fondo,
            start=(max(0, sx), max(0, sy)),
            background=gfx.ng_color(level.background),
            background_rgb=level.background,
            layers=[layer_index[n] for n in level.layers],
            music=music_index.get(level.music, 0),
            keys_needed=level.keys_needed,
        ))

    return Build(
        project=project, rom=rom, tiles=tiles, tile_index=tile_index,
        tileset=tileset, tileset_remap=tileset_remap,
        player=player, enemies=enemies, items=items, layers=layers, levels=levels,
        platforms=platforms, breakables=breakables, blocks=blocks,
        attack=attack, subs=subs,
        enemy_shots=enemy_shots, prisoners=prisoners, generators=generators,
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
        # el golpe cuerpo a cuerpo; alcance 0 = este no pega, hace dano al tocarte
        "reach": e.reach, "windup": e.windup, "active": e.active,
        "recover": e.recover, "wait": e.wait, "punch": e.punch,
        "tenaz": 1 if e.tenaz else 0,
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


def generator_values(build: ActorBuild,
                     enemy_index: Dict[str, int]) -> Dict[str, object]:
    """Los campos de NpGeneratorDef. `enemy` es el indice del enemigo que saca,
    que el lector del proyecto ya ha comprobado que existe."""
    g = build.actor          # type: ignore[assignment]
    return {"score": g.score, "cooldown": g.cooldown, "health": g.health,
            "enemy": enemy_index.get(g.enemy, 0), "cap": g.cap}


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
        "climb_speed": to_fixed(p.climb_speed),
        "coyote": p.coyote, "jump_buffer": p.jump_buffer, "wear": p.wear,
        # el agarre: con `grab_time` a 0 el motor ni lo mira
        "grab_time": p.grab_time, "grab_damage": p.grab_damage,
        "throw_damage": p.throw_damage, "throw_speed": to_fixed(p.throw_speed),
        "double_jump": 1 if p.double_jump else 0, "stomp": 1 if p.stomp else 0,
        "health": p.health,
        # 0 = el salto de las aventuras: al despegar se decide y ya no se cambia
        "air_control": 1 if p.air_control else 0,
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
                "levels": 0, "range_step": 0, "fx": 0,
                "combo": 0, "combo_window": 0, "finish_damage": 0,
                "finish_stun": 0, "finish_push": 0,
                "kick_range": 0, "kick_damage": 0}
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
        # la serie de golpes; con `combo: 1` el motor no la mira siquiera
        "combo": a.combo,
        "combo_window": a.combo_window,
        "finish_damage": a.finish_damage,
        "finish_stun": a.finish_stun,
        "finish_push": to_fixed(a.finish_push),
        # la patada voladora: pegar en el aire es otro golpe
        "kick_range": a.kick_range,
        "kick_damage": a.kick_damage,
        # con `tipo: golpe`, `sprite:` es el arma en si (el latigo) y se dibuja
        # delante del jugador mientras el golpe hace dano; sin sprite el golpe
        # es invisible, que es como estaba el kit
        "fx": 1 if a.sprite else 0,
    }


def _fondo_de_salas(project: Project, tileset: gfx.Sheet, del_png: int
                    ) -> Tuple[List[int], int, int]:
    """El dibujo del suelo de una sala, en tiles de pantalla.

    Es **uno solo** para todo el juego, y de ahi salen dos cosas buenas: un
    castillo de veinte habitaciones ocupa de fondo lo que una pantalla -que es
    lo que hace que quepa en el mapa de bits del Amiga, del ST y de la Jaguar-,
    y cambiar de sala es un corte y no un viaje. Lo que distingue una
    habitacion de otra son los cubos y los bichos, que son sprites.

    El dibujo de una sala isometrica es siempre el mismo -el rombo de 8x8
    casillas y las dos paredes del fondo por encima-, asi que no hay nada que
    calcular: es un trozo del tileset que se pega donde toca. Repintarlo cambia
    el aspecto del juego entero sin tocar una linea de codigo. Y las paredes
    ahi dentro son gratis: no son cubos, no se ordenan y no se dibujan.

    Devuelve indices **del tileset** (y -1 donde no se pinta nada): los numeros
    de verdad los pone el generador de codigo, que es quien sabe como los
    numera cada maquina.
    """
    ts = project.tileset
    ultimo = ts.sala_tile + (ts.sala_h - 1) * tileset.per_row + ts.sala_w - 1
    # Ojo: se mide contra los tiles **del PNG**, no contra los que quedan
    # despues de juntar los repetidos.
    if ultimo >= del_png:
        raise ProjectError(
            "el dibujo de la sala llega hasta el tile %d y el tileset tiene %d"
            % (ultimo, tileset.frames),
            hint="agranda '%s' (tiene %d tiles) o baja 'sala:' en 'tiles:'"
                 % (project.tileset.image, del_png),
            where="tiles.sala")
    ancho, alto = SALA_TILES_X, SALA_TILES_Y
    fondo = [-1] * (ancho * alto)
    for fy in range(ts.sala_h):
        ty = ts.sala_y + fy
        if ty >= alto:
            continue
        for fx in range(ts.sala_w):
            tx = ts.sala_x + fx
            if tx >= ancho:
                continue
            fondo[ty * ancho + tx] = ts.sala_tile + fy * tileset.per_row + fx
    return fondo, ancho, alto


def _cubos_por_sala(project: Project, level, width: int, height: int,
                    spawns: int) -> None:
    """Que los cubos de cada sala quepan en la lista de entidades.

    Solo existen los de la habitacion que se esta viendo -por eso un castillo
    entero cabe en sesenta y cuatro huecos-, pero la habitacion mas cargada
    tiene que caber junto con los enemigos y los objetos del nivel.
    """
    hueco = MAX_ENTIDADES - spawns
    for ry in range(height // SALA):
        for rx in range(width // SALA):
            cuantos = 0
            for cy in range(ry * SALA, ry * SALA + SALA):
                for cx in range(rx * SALA, rx * SALA + SALA):
                    ch = level.rows[cy][cx]
                    tile = project.tiles.get(ch)
                    if tile is not None and tile.bloque:
                        cuantos += 1
            if cuantos > hueco:
                raise ProjectError(
                    "la sala %d,%d de '%s' tiene %d cubos y solo caben %d"
                    % (rx, ry, level.name, cuantos, max(hueco, 0)),
                    hint="quita cubos de esa habitacion o enemigos y objetos "
                         "del nivel: entre todos no pueden pasar de %d"
                         % MAX_ENTIDADES,
                    where="niveles")


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
