"""Lectura y validacion de `game.yaml`.

Acepta las claves en espanol o en ingles (`jugador`/`player`, `salto`/`jump`...)
y devuelve una estructura ya normalizada y comprobada. Cualquier fallo del
usuario sale como `ProjectError` con un mensaje util, nunca como traza.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import sonido as sonido_mod
from . import wav
from .errors import ProjectError

# ---------------------------------------------------------------- utilidades

def load_yaml(path: str) -> Any:
    """Usa PyYAML si esta instalado; si no, el analizador incluido."""
    try:
        import yaml  # type: ignore
    except ImportError:
        from . import miniyaml

        try:
            return miniyaml.load_file(path)
        except miniyaml.YamlError as exc:
            raise ProjectError(str(exc), where=os.path.basename(path))
    with open(path, "r", encoding="utf-8") as fh:
        try:
            return yaml.safe_load(fh)
        except Exception as exc:  # pragma: no cover - depende de PyYAML
            raise ProjectError(str(exc), where=os.path.basename(path))


class Node:
    """Mapa del YAML con acceso tolerante a alias y errores explicativos."""

    def __init__(self, data: Any, where: str):
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ProjectError(
                "se esperaba una lista de opciones (clave: valor)", where=where
            )
        self.data = data
        self.where = where
        self.used: set = set()

    def raw(self, *names: str) -> Any:
        for name in names:
            if name in self.data:
                self.used.add(name)
                return self.data[name]
        return None

    def has(self, *names: str) -> bool:
        return any(name in self.data for name in names)

    def child(self, *names: str) -> "Node":
        value = self.raw(*names)
        return Node(value, "%s.%s" % (self.where, names[0]))

    def str_(self, names: Sequence[str], default: Optional[str] = None,
             required: bool = False) -> Optional[str]:
        value = self.raw(*names)
        if value is None:
            if required:
                raise ProjectError(
                    "falta la opcion obligatoria '%s'" % names[0], where=self.where
                )
            return default
        return str(value)

    def num(self, names: Sequence[str], default: float = 0.0,
            minimum: Optional[float] = None, maximum: Optional[float] = None) -> float:
        value = self.raw(*names)
        if value is None:
            return float(default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ProjectError(
                "'%s' debe ser un numero, no %r" % (names[0], value), where=self.where
            )
        value = float(value)
        if minimum is not None and value < minimum:
            raise ProjectError(
                "'%s' = %g es demasiado bajo (minimo %g)" % (names[0], value, minimum),
                where=self.where,
            )
        if maximum is not None and value > maximum:
            raise ProjectError(
                "'%s' = %g es demasiado alto (maximo %g)" % (names[0], value, maximum),
                where=self.where,
            )
        return value

    def int_(self, names: Sequence[str], default: int = 0,
             minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
        return int(round(self.num(names, default, minimum, maximum)))

    def bool_(self, names: Sequence[str], default: bool = False) -> bool:
        value = self.raw(*names)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in ("si", "sí", "true", "yes", "1"):
            return True
        if text in ("no", "false", "0"):
            return False
        raise ProjectError(
            "'%s' debe ser si/no, no %r" % (names[0], value), where=self.where
        )

    def pair(self, names: Sequence[str], default: Optional[Tuple[int, int]] = None
             ) -> Optional[Tuple[int, int]]:
        value = self.raw(*names)
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return (int(value), int(value))
        if isinstance(value, (list, tuple)) and len(value) == 2:
            return (int(value[0]), int(value[1]))
        raise ProjectError(
            "'%s' debe ser [ancho, alto] o un numero, no %r" % (names[0], value),
            where=self.where,
        )

    def choice(self, names: Sequence[str], options: Dict[str, str], default: str) -> str:
        value = self.raw(*names)
        if value is None:
            return default
        text = str(value).strip().lower()
        if text not in options:
            raise ProjectError(
                "'%s' no reconoce el valor '%s'" % (names[0], value),
                hint="valores validos: %s" % ", ".join(sorted(set(options))),
                where=self.where,
            )
        return options[text]

    def check_unknown(self, allowed: Sequence[str]) -> List[str]:
        allowed_set = set(allowed)
        return [key for key in self.data if key not in allowed_set]


def parse_color(text: Any, where: str) -> Tuple[int, int, int]:
    """Acepta '#rrggbb', '#rgb' o [r, g, b]."""
    if isinstance(text, (list, tuple)) and len(text) == 3:
        return tuple(max(0, min(255, int(c))) for c in text)  # type: ignore
    value = str(text).strip().lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    if len(value) != 6:
        raise ProjectError(
            "color invalido '%s'" % text,
            hint="usa '#1a2b3c', '#abc' o [r, g, b]",
            where=where,
        )
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        raise ProjectError("color invalido '%s'" % text, where=where)


# ------------------------------------------------------------------ modelos

# `cubo: pintado` en un tile de la vista isometrica: la casilla levanta -y por
# lo tanto para al que anda- pero **no se dibuja nada encima**, porque el
# dibujo ya viene en la imagen de la sala. Es como se hacen las dos paredes del
# fondo de una habitacion: pintadas una vez en `sala:` en vez de quince cubos
# que hay que ordenar y dibujar en cada frame.
PINTADO = ("pintado", "pintada", "sala", "ninguno", "nada", "painted", "none")

TILE_KINDS = {
    "vacio": "empty", "vacío": "empty", "empty": "empty", "aire": "empty",
    "solido": "solid", "sólido": "solid", "solid": "solid", "bloque": "solid",
    "plataforma": "platform", "platform": "platform", "oneway": "platform",
    "peligro": "hazard", "hazard": "hazard", "pinchos": "hazard", "spikes": "hazard",
    "meta": "goal", "goal": "goal", "salida": "goal", "exit": "goal",
    "decorado": "decor", "decor": "decor", "fondo": "decor",
    # escaleras: hay dos porque una escalera tiene sentido de subida
    "escalera": "stair_r", "escalera_derecha": "stair_r", "stair_r": "stair_r",
    "escalera_sube_derecha": "stair_r", "stairs": "stair_r",
    "escalera_izquierda": "stair_l", "stair_l": "stair_l",
    "escalera_sube_izquierda": "stair_l",
    # punto de control: se atraviesa, y al tocarlo apunta donde reapareces
    "control": "check", "punto_control": "check", "punto_de_control": "check",
    "checkpoint": "check", "check": "check", "bandera": "check",
    # cerrojo: frena como una pared hasta que llegas con el objeto que pide
    "cerrojo": "lock", "lock": "lock", "puerta": "lock", "candado": "lock",
    "cerradura": "lock",
}

TILE_KIND_ID = {"empty": 0, "solid": 1, "platform": 2, "hazard": 3, "goal": 4,
                "decor": 5, "stair_r": 6, "stair_l": 7, "check": 8,
                # el cerrojo de las aventuras: frena como una pared hasta que
                # llegas con el objeto que pide, y entonces se abre para siempre
                "lock": 9}

BEHAVIORS = {
    "patrulla": "patrol", "patrol": "patrol", "andar": "patrol", "walker": "patrol",
    "volador": "flyer", "flyer": "flyer", "volar": "flyer", "mosca": "flyer",
    "perseguidor": "chaser", "chaser": "chaser", "perseguir": "chaser",
    "saltarin": "jumper", "saltarín": "jumper", "jumper": "jumper", "saltar": "jumper",
    "fijo": "static", "static": "static", "quieto": "static", "torreta": "static",
}

BEHAVIOR_ID = {"patrol": 0, "flyer": 1, "chaser": 2, "jumper": 3, "static": 4}

ITEM_EFFECTS = {
    "puntos": "points", "points": "points", "score": "points", "moneda": "points",
    "vida": "life", "life": "life", "1up": "life",
    "salud": "health", "health": "health", "corazon": "health", "corazón": "health",
    "llave": "key", "key": "key",
    # municion del arma secundaria. Ojo: "corazon" a secas es salud, que es
    # como estaba antes y no se cambia; la municion es "municion"/"corazones".
    "municion": "ammo", "munición": "ammo", "ammo": "ammo",
    "corazones": "ammo", "hearts": "ammo",
    # mejora del arma: alarga el ataque un paso y se pierde al morir
    "mejora": "upgrade", "upgrade": "upgrade", "mejorar": "upgrade",
    "arma": "upgrade", "latigo": "upgrade", "látigo": "upgrade",
    # cambia el arma secundaria que se lleva: `secundaria: hacha`
    "subarma": "weapon", "arma_secundaria": "weapon", "weapon": "weapon",
    "cambiar_arma": "weapon",
    # la pocima de Gauntlet: al cogerla hace dano a todo lo que se ve
    "bomba": "bomb", "bomb": "bomb", "pocima": "bomb", "pocion": "bomb",
    "poción": "bomb", "smart_bomb": "bomb",
    # el objeto que se lleva encima, de las aventuras tipo Dizzy: no hace nada
    # al cogerlo, se guarda en la bolsa y abre el sitio que lo pide
    "llevar": "carry", "carry": "carry", "objeto": "carry", "coger": "carry",
    "inventario": "carry", "herramienta": "carry",
}

ITEM_EFFECT_ID = {"points": 0, "life": 1, "health": 2, "key": 3, "ammo": 4,
                  "upgrade": 5, "weapon": 6, "bomb": 7, "carry": 8}


@dataclass
class Animation:
    name: str
    frames: List[int]
    speed: int          # frames de juego por fotograma
    loop: bool = True


@dataclass
class Actor:
    """Base comun de jugador, enemigos y objetos: como se dibuja y su caja."""
    name: str
    sprite: str                      # ruta relativa al proyecto
    frame_w: int
    frame_h: int
    box_w: int
    box_h: int
    box_x: int                       # desplazamiento de la caja dentro del frame
    box_y: int
    animations: Dict[str, Animation] = field(default_factory=dict)


@dataclass
class Player(Actor):
    speed: float = 1.5
    accel: float = 0.28
    friction: float = 0.35
    air_accel: float = 0.16
    jump: float = 4.3
    jump_cut: float = 1.6
    gravity: float = 0.28
    max_fall: float = 6.0
    double_jump: bool = False
    # Si se manda en el aire. False es el salto de las aventuras clasicas: al
    # despegar se decide hacia donde vas y hasta caer no se cambia.
    air_control: bool = True
    coyote: int = 6
    jump_buffer: int = 6
    stomp: bool = True
    bounce: float = 3.6
    health: int = 1
    # Frames que tarda en irse un punto de vida sola. 0 = no se va nunca.
    wear: int = 0
    # El agarre de los juegos de tortas. 0 = el juego no lleva agarre.
    grab_time: int = 0             # frames que aguanta agarrado
    grab_damage: int = 1           # lo que hace cada rodillazo
    throw_damage: int = 2          # lo que duele estrellarse
    throw_speed: float = 3.5       # a que velocidad sale despedido
    invuln: int = 90
    knockback: float = 0.0        # 0 = tanto como la velocidad de andar
    stun: int = 0                 # frames sin control tras un golpe
    stair_speed: float = 0.0      # 0 = la mitad de la velocidad de andar
    crouch: bool = False          # si se puede agachar con abajo
    crouch_h: int = 0             # alto de la caja agachado (0 = tres cuartos)
    attack: Optional["Attack"] = None
    subs: List["Sub"] = field(default_factory=list)   # las armas secundarias

    @property
    def sub(self) -> Optional["Sub"]:
        """La primera arma secundaria, que es con la que se empieza."""
        return self.subs[0] if self.subs else None


@dataclass
class Attack(Actor):
    """El ataque del jugador. `kind` vacio = el juego no lleva ataque."""
    kind: str = ""                 # "shot" o "melee"
    speed: float = 3.0             # velocidad del proyectil
    range: int = 64                # px que recorre, o alcance del golpe
    cooldown: int = 20             # frames entre ataques
    duration: int = 8              # frames que dura el golpe
    windup: int = 0                # frames de preparacion antes de hacer dano
    locks: bool = False            # mientras pegas, no te mueves
    damage: int = 1
    levels: int = 0                # cuantas mejoras admite (0 = ninguna)
    range_step: int = 12           # px que alarga cada mejora
    # La serie de golpes: puno, puno y remate. 1 = no hay serie.
    combo: int = 1                 # golpes que tiene la serie
    combo_window: int = 30         # frames para encadenar el siguiente
    finish_damage: int = 0         # lo que hace el ultimo (0 = como los demas)
    finish_stun: int = 0           # frames que se queda en el suelo el que cobra
    finish_push: float = 3.0       # con cuanta fuerza sale despedido


@dataclass
class EnemyShot(Actor):
    """Lo que tira un enemigo con `dispara:`.

    Es un actor mas -tiene su dibujo y su caja- con lo justo para volar: a que
    velocidad, cuanto llega, cada cuanto sale y cuanto duele."""
    speed: float = 2.0
    range: float = 200.0
    cooldown: int = 90
    damage: int = 1


@dataclass
class Enemy(Actor):
    behavior: str = "patrol"
    speed: float = 0.5
    gravity: float = 0.28
    health: int = 1
    damage: int = 1
    score: int = 100
    stompable: bool = True
    edge_turn: bool = True
    boss: bool = False
    range: float = 96.0
    amplitude: float = 24.0
    period: int = 120
    jump: float = 3.5
    interval: int = 90
    shot: Optional["EnemyShot"] = None   # con `dispara:`, lo que te tira
    # El golpe cuerpo a cuerpo, para los juegos de tortas. Con `reach` a cero
    # el enemigo no pega: hace dano al tocarte, como en el resto de generos.
    reach: int = 0                       # alcance del golpe, en px
    windup: int = 16                     # preparacion: el aviso
    active: int = 6                      # frames que hace dano
    recover: int = 20                    # plantado despues: tu ventana
    wait: int = 40                       # espera antes de volver a intentarlo
    punch: int = 0                       # dano del golpe; 0 = el de `dano:`


@dataclass
class Item(Actor):
    effect: str = "points"
    score: int = 10
    amount: int = 1
    weapon: str = ""               # con 'efecto: subarma', a cual cambia
    # Como sale en la bolsa del marcador (cinco letras). Solo lo miran los
    # objetos de `efecto: llevar`; sin `marcador:` se recorta el nombre.
    label: str = ""


@dataclass
class Sub(Actor):
    """El arma secundaria: arriba + accion, y gasta municion."""
    kind: str = ""                 # "" ninguna, "line" recta, "arc" en arco
    speed: float = 3.0
    gravity: float = 0.25          # solo cuenta en arco
    jump: float = 3.0              # impulso hacia arriba al salir, en arco
    range: int = 160
    cooldown: int = 24
    cost: int = 1
    damage: int = 1
    at_once: int = 0               # cuantas a la vez en el aire (0 = sin tope)
    label: str = ""                # como sale en el marcador (5 letras)


@dataclass
class Breakable(Actor):
    """Un candelabro: se rompe a golpes y suelta lo que lleve dentro."""
    drop: str = ""                 # nombre del objeto que suelta
    score: int = 0
    health: int = 1


@dataclass
class Prisoner(Actor):
    """Un prisionero atado, de los de Guerrilla War.

    No hace dano ni se le puede matar de un pisoton: esta ahi esperando. Si le
    tocas, se suelta y echa a correr (y suma puntos); si le pegas un tiro, se
    acabo, y ese es el castigo por disparar a lo loco. Es el unico actor del
    kit al que **no** hay que dispararle."""
    score: int = 500
    speed: float = 1.2            # lo que corre al soltarse
    escape: int = 90              # frames corriendo antes de perderse de vista


@dataclass
class Generator(Actor):
    """Un generador de bichos, de los de Gauntlet.

    No se mueve y no hace dano: lo que hace es **sacar enemigos** cada tantos
    frames, uno detras de otro, hasta que lo destruyes a tiros. Es lo que
    convierte una mazmorra en una carrera: mientras siga en pie, matar bichos
    no sirve de nada, y el juego deja de ser "limpiar la sala" para ser "llegar
    al generador".
    """
    enemy: str = ""          # que enemigo saca; tiene que estar en `enemigos:`
    health: int = 3          # tiros que aguanta
    score: int = 1000        # lo que vale destruirlo
    cooldown: int = 90       # frames entre bicho y bicho
    cap: int = 3             # cuantos suyos puede haber a la vez


@dataclass
class Platform(Actor):
    """Plataforma movil: va y viene, y el que se sube encima va con ella."""
    axis: str = "x"          # "x" (de lado) o "y" (arriba y abajo)
    speed: float = 0.5
    distance: int = 64       # pixeles de recorrido desde donde sale


@dataclass
class Block(Actor):
    """Un cubo de la vista isometrica: el dibujo de una casilla levantada.

    No tiene nada mas -ni velocidad, ni vida, ni comportamiento- porque un cubo
    no hace nada: esta ahi, te subes encima y te tapa al que pasa por detras.
    Lo unico que se le pide es que el fotograma mida 32 de ancho por `alto` + 16
    de alto, que es lo que ocupa un prisma de esa altura sobre un rombo."""


@dataclass
class TileDef:
    char: str
    index: int          # numero de tile dentro del tileset
    kind: str
    # con `tipo: cerrojo`, que objeto lo abre. Vacio = ninguno (y entonces no
    # se abre nunca, que es un error del juego y se avisa).
    needs: str = ""
    # Solo en la vista isometrica: lo que levanta la casilla, en pixeles, y con
    # que cubo se dibuja. Cero es suelo raso; 16 es un cubo al que hay que
    # subirse de un salto; 48 es una pared. Es lo unico que hace falta para
    # escribir una habitacion entera.
    alto: int = 0
    bloque: str = ""
    # `cubo: pintado` -la casilla levanta pero no se dibuja nada, porque ya
    # viene en el dibujo de la sala-. Es lo que hace que las paredes del fondo
    # de una habitacion no cuesten un sprite cada una.
    pintado: bool = False


@dataclass
class Layer:
    """Capa de fondo con scroll propio (parallax). Solo es decorado."""
    name: str
    image: str
    speed_x: float = 0.5      # 0 = quieta, 1 = va con el escenario
    speed_y: float = 0.0
    offset_y: int = 0         # donde empieza la capa en la pantalla
    repeat: bool = True


@dataclass
class Level:
    name: str
    rows: List[str]
    spawns: Dict[str, str]
    background: Tuple[int, int, int]
    layers: List[str] = field(default_factory=list)   # nombres de capas de fondo
    music: str = ""                                   # nombre de la musica del nivel
    keys_needed: int = 0                              # llaves que pide la meta
    start: Tuple[int, int] = (0, 0)


@dataclass
class Tileset:
    image: str
    size: int = 16
    # El dibujo de una sala isometrica: un rectangulo de tiles dentro del
    # propio tileset que el compilador pega en cada sala. Trae el suelo -8x8
    # casillas, siempre el mismo rombo de 256x128 pixeles- y las dos paredes
    # del fondo por encima. Es un dibujo normal y corriente: se puede repintar
    # entero.
    # `sala_tile` a -1 quiere decir que el juego no lleva salas isometricas.
    sala_tile: int = -1
    sala_w: int = 16          # en tiles de 16x16
    sala_h: int = 8
    sala_x: int = 2           # donde se pega dentro de la pantalla, en tiles
    sala_y: int = 5


@dataclass
class Project:
    root: str
    title: str
    author: str
    system: str            # para que maquina se compila por defecto
    lives: int
    players: int           # 1 o 2 jugadores a la vez
    time_limit: int
    hud: bool
    camera: str            # "scroll" o "pantallas"
    # Cuantos enemigos pegan a la vez en un juego de tortas. Es el numero que
    # decide si una pelea se juega o se sufre: con todos a la vez no hay hueco
    # entre golpe y golpe. Dos es lo de los recreativos.
    aggressive: int
    view: str              # "lateral" (con gravedad) o "cenital" (desde arriba)
    amiga_modo: str        # "32colores" o "8colores"
    player: Player
    tileset: Tileset
    tiles: Dict[str, TileDef]
    enemies: Dict[str, Enemy]
    items: Dict[str, Item]
    platforms: Dict[str, "Platform"]
    breakables: Dict[str, "Breakable"]
    blocks: Dict[str, "Block"]        # los cubos de la vista isometrica
    prisoners: Dict[str, "Prisoner"]
    generators: Dict[str, "Generator"]
    layers: Dict[str, Layer]
    sound: "sonido_mod.Sonido"
    levels: List[Level]
    warnings: List[str] = field(default_factory=list)

    def spawn_names(self) -> List[str]:
        return (list(self.enemies) + list(self.items) + list(self.platforms)
                + list(self.breakables) + list(self.prisoners)
                + list(self.generators))


# ------------------------------------------------------------------- lectura

ANIM_ALIASES = {
    "quieto": "idle", "parado": "idle", "idle": "idle",
    "correr": "run", "andar": "run", "caminar": "run", "run": "run", "walk": "run",
    "saltar": "jump", "salto": "jump", "jump": "jump",
    "caer": "fall", "caida": "fall", "caída": "fall", "fall": "fall",
    "morir": "hurt", "dano": "hurt", "daño": "hurt", "hurt": "hurt",
    "atacar": "attack", "ataque": "attack", "attack": "attack", "pegar": "attack",
    "subir": "stair", "escalera": "stair", "trepar": "stair", "stair": "stair",
    "agachado": "crouch", "agacharse": "crouch", "crouch": "crouch",
    "agachar": "crouch",
    "girar": "turn", "turn": "turn",
    # solo en vista cenital: el heroe visto de espaldas y de frente
    "arriba": "up", "espaldas": "up", "up": "up", "subiendo": "up",
    "abajo": "down", "frente": "down", "down": "down", "bajando": "down",
    # el ultimo golpe de una serie, el que tumba (juegos de tortas)
    "remate": "remate", "finish": "remate", "ultimo": "remate",
    "final": "remate", "tumbar": "remate",
}

STANDARD_ANIMS = ["idle", "run", "jump", "fall", "hurt"]


def _read_animations(node: Node, where: str) -> Dict[str, Animation]:
    anims: Dict[str, Animation] = {}
    for key, value in (node.data or {}).items():
        canon = ANIM_ALIASES.get(str(key).strip().lower(), str(key).strip().lower())
        sub_where = "%s.%s" % (where, key)
        if isinstance(value, (list, tuple)):
            frames = [int(f) for f in value]
            speed, loop = 6, True
        else:
            sub = Node(value, sub_where)
            raw_frames = sub.raw("frames", "fotogramas", "cuadros")
            if raw_frames is None:
                raise ProjectError(
                    "la animacion '%s' no indica 'frames'" % key, where=sub_where
                )
            if isinstance(raw_frames, (int, float)):
                raw_frames = [raw_frames]
            frames = [int(f) for f in raw_frames]
            speed = sub.int_(["speed", "velocidad", "duracion", "duración"], 6, minimum=1)
            loop = sub.bool_(["loop", "bucle", "repetir"], True)
        if not frames:
            raise ProjectError(
                "la animacion '%s' no tiene ningun fotograma" % key, where=sub_where
            )
        if any(f < 0 for f in frames):
            raise ProjectError(
                "la animacion '%s' usa fotogramas negativos" % key, where=sub_where
            )
        anims[canon] = Animation(canon, frames, speed, loop)
    return anims


def _actor_geometry(node: Node, where: str, default_frame: Tuple[int, int]
                    ) -> Tuple[int, int, int, int, int, int]:
    frame = node.pair(["frame", "fotograma", "tamano_frame"], default_frame)
    fw, fh = frame  # type: ignore
    if fw <= 0 or fh <= 0:
        raise ProjectError("'frame' debe ser positivo", where=where)
    if fw % 16 or fh % 16:
        raise ProjectError(
            "el fotograma mide %dx%d y la Neo Geo dibuja sprites en bloques de 16x16"
            % (fw, fh),
            hint="usa medidas multiplos de 16 (16x16, 16x32, 32x32...)",
            where=where,
        )
    box = node.pair(["hitbox", "caja", "colision", "colisión", "tamano", "tamaño", "size"],
                    None)
    if box is None:
        bw, bh = fw, fh
    else:
        bw, bh = box
    if bw <= 0 or bh <= 0:
        raise ProjectError("la caja de colision debe ser positiva", where=where)
    if bw > fw or bh > fh:
        raise ProjectError(
            "la caja de colision (%dx%d) no cabe en el fotograma (%dx%d)"
            % (bw, bh, fw, fh),
            where=where,
        )
    offset = node.pair(["hitbox_offset", "offset_caja", "desplazamiento"], None)
    if offset is None:
        bx, by = (fw - bw) // 2, fh - bh   # centrada y apoyada en el suelo
    else:
        bx, by = offset
    return fw, fh, bw, bh, bx, by


CAMARAS = {
    "scroll": "scroll", "desplazamiento": "scroll", "suave": "scroll",
    "pantallas": "pantallas", "pantalla": "pantallas", "screens": "pantallas",
    "flip": "pantallas", "pantalla_a_pantalla": "pantallas",
}


VISTAS = {
    "lateral": "lateral", "side": "lateral", "plataformas": "lateral",
    "perfil": "lateral", "de_lado": "lateral",
    "cenital": "cenital", "aerea": "cenital", "aérea": "cenital",
    "top": "cenital", "top_down": "cenital", "desde_arriba": "cenital",
    "pajaro": "cenital", "vista_de_pajaro": "cenital",
    # La cinta: se ve desde arriba como la cenital, pero con salto de verdad.
    "cinta": "cinta", "belt": "cinta", "cinta_transportadora": "cinta",
    "yo_contra_el_barrio": "cinta", "beat_em_up": "cinta", "brawler": "cinta",
    "tortas": "cinta",
    # La isometrica: la sala se ve desde una esquina, se anda por su planta y
    # se salta de cubo en cubo. Es la del Knight Lore y las suyas, que llamaban
    # a esto "filmation".
    "isometrica": "iso", "isométrica": "iso", "iso": "iso",
    "filmation": "iso", "isometrico": "iso", "isométrico": "iso",
    "tresd": "iso", "3d": "iso", "habitaciones": "iso",
}


def _leer_vista(game: Node) -> str:
    """Desde donde se ve el juego, que es lo que decide como se mueve todo.

    'lateral' es lo de siempre: hay gravedad, se salta y se mira a un lado o a
    otro. 'cenital' es la vista desde arriba de los juegos de comando: no hay
    gravedad ni suelo, andas en ocho direcciones y disparas hacia donde miras.
    'cinta' es la de los juegos de tortas: se anda en ocho direcciones por una
    franja de suelo, como en cenital, pero **se salta**, porque hay una tercera
    coordenada -lo alto que estas sobre el suelo- con su gravedad.

    No son generos -eso es lo que se puede hacer-, son **desde donde se mira**,
    y por eso van en `juego:` al lado de la camara.
    """
    texto = (game.str_(["vista", "view", "perspectiva"], "lateral") or "lateral")
    clave = str(texto).strip().lower().replace(" ", "_").replace("-", "_")
    if clave not in VISTAS:
        raise ProjectError(
            "no entiendo la vista '%s'" % texto,
            hint="pon 'lateral' (de lado, con gravedad), 'cenital' "
                 "(desde arriba, en ocho direcciones), 'cinta' (desde arriba "
                 "pero saltando) o 'isometrica' (una sala vista desde una "
                 "esquina)",
            where="juego",
        )
    return VISTAS[clave]


def _leer_camara(game: Node) -> str:
    """Como se mueve la camara: siguiendo al jugador o de pantalla en pantalla."""
    texto = (game.str_(["camara", "cámara", "camera"], "scroll") or "scroll")
    clave = str(texto).strip().lower().replace(" ", "_").replace("-", "_")
    if clave not in CAMARAS:
        raise ProjectError(
            "no entiendo la camara '%s'" % texto,
            hint="pon 'scroll' (el escenario se desliza) o 'pantallas' "
                 "(salta de pantalla en pantalla)",
            where="juego",
        )
    return CAMARAS[clave]


# Lo que se elige de verdad es **un plano o dos**, no un numero de colores: los
# nombres vienen del OCS, donde salen 32 y 8. En el A1200, con AGA, los mismos
# dos modos dan 256 y 16, y por eso '256colores' y '16colores' valen igual.
MODOS_AMIGA = {
    "32colores": "32colores", "32": "32colores", "32_colores": "32colores",
    "256colores": "32colores", "256": "32colores", "256_colores": "32colores",
    "normal": "32colores", "un_plano": "32colores",
    "8colores": "8colores", "8": "8colores", "8_colores": "8colores",
    "16colores": "8colores", "16": "8colores", "16_colores": "8colores",
    "parallax": "8colores", "doble_plano": "8colores", "dual": "8colores",
}


def _leer_modo_amiga(game: Node) -> str:
    """En el Amiga hay que elegir: 32 colores o parallax de verdad.

    Los seis bitplanes del OCS se pueden usar de dos maneras: cinco para un
    solo plano de 32 colores, o tres y tres para dos planos independientes de
    8. El segundo modo es la unica forma de tener parallax en un A500 (esta
    medido: dibujarlo con el blitter no cabe en un frame), y cuesta pasar de 32
    colores a 7 mas otros 7.
    """
    texto = (game.str_(["amiga", "modo_amiga"], "32colores") or "32colores")
    clave = str(texto).strip().lower().replace(" ", "_").replace("-", "_")
    if clave not in MODOS_AMIGA:
        raise ProjectError(
            "no entiendo el modo de Amiga '%s'" % texto,
            hint="pon '32colores' (mas colores, sin parallax) o '8colores' "
                 "(parallax de verdad, 7 colores por plano). En el A1200 los "
                 "mismos dos modos se llaman tambien '256colores' y '16colores'",
            where="juego",
        )
    return MODOS_AMIGA[clave]


ATTACK_KINDS = {
    "disparo": "shot", "shot": "shot", "bala": "shot", "proyectil": "shot",
    "tiro": "shot", "shoot": "shot",
    "golpe": "melee", "melee": "melee", "espada": "melee", "cuerpo": "melee",
    "puno": "melee", "puño": "melee",
}


def _read_attack(node: Node, root: str) -> Optional["Attack"]:
    """El ataque del jugador. Sin seccion `ataque:` no hay ataque y el boton de
    accion no hace nada, que es como estaba el kit antes."""
    if not node.data:
        return None
    where = "jugador.ataque"
    kind = node.choice(["type", "tipo"], ATTACK_KINDS, "shot")
    sprite = node.str_(["sprite", "imagen", "image"], "") or ""
    if kind == "shot" and not sprite:
        raise ProjectError(
            "un ataque de tipo 'disparo' necesita el dibujo del proyectil",
            hint="anade 'sprite: graficos/bala.png', o usa 'tipo: golpe' si no "
                 "quieres que salga nada",
            where=where)
    if sprite:
        _require_file(root, sprite, where)
        fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (8, 8))
        anims = _read_animations(node.child("animations", "animaciones", "anims"),
                                 where)
    else:
        fw = fh = bw = bh = 8
        bx = by = 0
        anims = {}
    ataque = Attack(
        name="attack", sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        kind=kind,
        speed=node.num(["speed", "velocidad"], 3.0, 0.25, 12.0),
        range=node.int_(["range", "alcance"], 64 if kind == "shot" else 12, 4, 512),
        cooldown=node.int_(["cooldown", "espera", "cadencia"], 20, 1, 300),
        duration=node.int_(["duration", "duracion", "duración"], 8, 1, 120),
        windup=node.int_(["windup", "preparacion", "preparación", "aviso"], 0, 0, 120),
        locks=node.bool_(["locks", "clavado", "sin_moverse"], False),
        damage=node.int_(["damage", "dano", "daño"], 1, 1, 99),
        levels=node.int_(["levels", "mejoras", "niveles"], 0, 0, 8),
        range_step=node.int_(["range_step", "alcance_mejora", "paso_mejora"],
                             12, 1, 128),
        # La serie de golpes de los juegos de tortas. Con `combo: 1` -lo
        # normal- no hay serie y los tres numeros de abajo no pintan nada.
        combo=node.int_(["combo", "serie", "encadenado"], 1, 1, 8),
        combo_window=node.int_(["combo_window", "ventana", "ventana_combo"],
                               30, 2, 300),
        finish_damage=node.int_(["finish_damage", "dano_remate", "daño_remate",
                                 "remate"], 0, 0, 99),
        finish_stun=node.int_(["finish_stun", "derribo", "tumbado"], 0, 0, 240),
        finish_push=node.num(["finish_push", "empujon_remate", "empujón_remate"],
                             3.0, 0.0, 12.0),
    )
    if ataque.windup >= ataque.duration:
        raise ProjectError(
            "la preparacion del ataque (%d) se come su duracion entera (%d): "
            "no llegaria a hacer dano nunca" % (ataque.windup, ataque.duration),
            hint="baja 'preparacion:' o sube 'duracion:'",
            where=where)
    _warn_unknown(node, where, [
        "type", "tipo", "sprite", "imagen", "image",
        "frame", "fotograma", "tamano_frame", "hitbox", "caja", "colision",
        "colisión", "tamano", "tamaño", "size", "hitbox_offset", "offset_caja",
        "desplazamiento", "animations", "animaciones", "anims",
        "speed", "velocidad", "range", "alcance", "cooldown", "espera",
        "cadencia", "duration", "duracion", "duración",
        "windup", "preparacion", "preparación", "aviso",
        "locks", "clavado", "sin_moverse",
        "damage", "dano", "daño",
        "levels", "mejoras", "niveles", "range_step", "alcance_mejora",
        "paso_mejora",
        "combo", "serie", "encadenado", "combo_window", "ventana",
        "ventana_combo", "finish_damage", "dano_remate", "daño_remate",
        "remate", "finish_stun", "derribo", "tumbado",
        "finish_push", "empujon_remate", "empujón_remate",
    ])
    return ataque


SUB_KINDS = {
    "recta": "line", "recto": "line", "line": "line", "straight": "line",
    "arco": "arc", "arc": "arc", "parabola": "arc", "parábola": "arc",
}


# Lo que sabe escribir la fuente del marcador (ver FONT_CHARS en gfx.py): es
# lo unico que puede llevar el nombre corto de un arma.
LETRAS_MARCADOR = " 0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ-.:!?/"


def _read_subs(uno: Node, varias: Node, root: str) -> List["Sub"]:
    """Las armas secundarias del juego, en orden. Se empieza con la primera y
    se cambian cogiendo un objeto con `efecto: subarma`.

    Se admiten las dos formas: `secundaria:` con una sola (como estaba el kit)
    y `secundarias:` con varias, cada una con su nombre."""
    if varias.data:
        if uno.data:
            raise ProjectError(
                "el juego trae 'secundaria:' y 'secundarias:' a la vez",
                hint="deja solo 'secundarias:' y pon ahi todas las armas",
                where="jugador")
        armas = []
        for nombre, datos in (varias.data or {}).items():
            arma = _read_sub(Node(datos, "jugador.secundarias.%s" % nombre), root,
                             "jugador.secundarias.%s" % nombre)
            if arma is None:
                continue
            arma.name = str(nombre)
            armas.append(arma)
        if not armas:
            raise ProjectError("'secundarias:' esta vacio", where="jugador")
        _etiquetas(armas)
        return armas
    arma = _read_sub(uno, root, "jugador.secundaria")
    if arma is None:
        return []
    _etiquetas([arma])
    return [arma]


def _etiquetas(armas: List["Sub"]) -> None:
    """Como sale cada arma en el marcador cuando no lo dice `marcador:`.

    Con una sola arma no hay nada que distinguir y el hueco pone "AMMO", que es
    lo que ponia el kit de siempre; en cuanto hay dos, el nombre del arma es la
    unica forma de saber cual llevas, asi que salen las cinco primeras letras
    de su nombre."""
    for arma in armas:
        if arma.label:
            continue
        if len(armas) == 1:
            arma.label = "AMMO"
            continue
        # del nombre solo valen las letras que tiene la fuente: un arma que se
        # llame "latigo con nen" se queda sin nada que ensenar y vuelve a "AMMO"
        corto = "".join(c for c in arma.name.upper() if c in LETRAS_MARCADOR)
        arma.label = corto[:5].strip() or "AMMO"


def _read_sub(node: Node, root: str, where: str = "jugador.secundaria"
              ) -> Optional["Sub"]:
    """Un arma secundaria. Sin seccion `secundaria:` no hay ninguna y arriba +
    accion se comporta como el boton a secas."""
    if not node.data:
        return None
    kind = node.choice(["type", "tipo"], SUB_KINDS, "line")
    sprite = node.str_(["sprite", "imagen", "image"], "") or ""
    if not sprite:
        raise ProjectError(
            "el arma secundaria necesita el dibujo de lo que lanza",
            hint="anade 'sprite: graficos/cuchillo.png'",
            where=where)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    arma = Sub(
        name="sub", sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        kind=kind,
        speed=node.num(["speed", "velocidad"], 3.0, 0.25, 12.0),
        gravity=node.num(["gravity", "gravedad"], 0.25, 0.0, 4.0),
        jump=node.num(["jump", "salto", "impulso"], 3.0, 0.0, 12.0),
        range=node.int_(["range", "alcance"], 160, 8, 512),
        cooldown=node.int_(["cooldown", "espera", "cadencia"], 24, 1, 300),
        cost=node.int_(["cost", "coste", "municion", "munición"], 1, 0, 99),
        damage=node.int_(["damage", "dano", "daño"], 1, 1, 99),
        at_once=node.int_(["at_once", "a_la_vez", "en_el_aire", "simultaneas"],
                          0, 0, 16),
        label=(node.str_(["label", "marcador", "etiqueta"], "") or "").upper(),
    )
    _warn_unknown(node, where, [
        "type", "tipo", "sprite", "imagen", "image",
        "frame", "fotograma", "tamano_frame", "hitbox", "caja", "colision",
        "colisión", "tamano", "tamaño", "size", "hitbox_offset", "offset_caja",
        "desplazamiento", "animations", "animaciones", "anims",
        "speed", "velocidad", "gravity", "gravedad", "jump", "salto", "impulso",
        "range", "alcance", "cooldown", "espera", "cadencia",
        "cost", "coste", "municion", "munición", "damage", "dano", "daño",
        "at_once", "a_la_vez", "en_el_aire", "simultaneas",
        "label", "marcador", "etiqueta",
    ])
    # En el marcador caben cinco letras: es lo que dejan libre las llaves y la
    # cuenta de municion, y el marcador de estas maquinas no da para mas. Sin
    # `marcador:` se cogen las cinco primeras del nombre.
    if len(arma.label) > 5:
        raise ProjectError(
            "'marcador: %s' tiene %d letras y en el marcador caben cinco"
            % (arma.label, len(arma.label)),
            hint="ponle un nombre corto, como 'HACHA' o 'CRUZ'",
            where=where)
    # Y con las letras que tiene la fuente del marcador: la de estas maquinas
    # no lleva ni acentos ni enes, que se verian como huecos.
    for letra in arma.label:
        if letra not in LETRAS_MARCADOR:
            raise ProjectError(
                "'marcador: %s' lleva un caracter ('%s') que no esta en la "
                "fuente del marcador" % (arma.label, letra),
                hint="solo letras de la A a la Z, numeros y espacios",
                where=where)
    return arma


def _read_breakable(name: str, data: Any, root: str) -> "Breakable":
    where = "rompibles.%s" % name
    node = Node(data, where)
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    return Breakable(
        name=name, sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        drop=node.str_(["drop", "suelta", "contiene"], "") or "",
        score=node.int_(["score", "puntos"], 0, 0, 99999),
        health=node.int_(["health", "salud", "vida"], 1, 1, 99),
    )


def _read_prisoner(name: str, data: Any, root: str) -> "Prisoner":
    where = "prisioneros.%s" % name
    node = Node(data, where)
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    prisionero = Prisoner(
        name=name, sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        score=node.int_(["score", "puntos"], 500, 0, 99999),
        speed=node.num(["speed", "velocidad"], 1.2, 0.0, 8.0),
        escape=node.int_(["escape", "huida", "corre"], 90, 0, 600),
    )
    _warn_unknown(node, where, [
        "sprite", "imagen", "image", "frame", "fotograma", "tamano_frame",
        "hitbox", "caja", "colision", "colisión", "tamano", "tamaño", "size",
        "hitbox_offset", "offset_caja", "desplazamiento",
        "animations", "animaciones", "anims",
        "score", "puntos", "speed", "velocidad", "escape", "huida", "corre",
    ])
    return prisionero


def _read_generator(name: str, data: Any, root: str) -> "Generator":
    where = "generadores.%s" % name
    node = Node(data, where)
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    generador = Generator(
        name=name, sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        enemy=node.str_(["enemy", "genera", "saca", "bicho"], required=True) or "",
        health=node.int_(["health", "salud", "vida"], 3, 1, 99),
        score=node.int_(["score", "puntos"], 1000, 0, 99999),
        cooldown=node.int_(["cooldown", "cada", "intervalo", "espera"], 90, 8, 3600),
        cap=node.int_(["cap", "tope", "a_la_vez", "maximo"], 3, 1, 32),
    )
    _warn_unknown(node, where, [
        "sprite", "imagen", "image", "frame", "fotograma", "tamano_frame",
        "hitbox", "caja", "colision", "colisión", "tamano", "tamaño", "size",
        "hitbox_offset", "offset_caja", "desplazamiento",
        "animations", "animaciones", "anims",
        "enemy", "genera", "saca", "bicho",
        "health", "salud", "vida", "score", "puntos",
        "cooldown", "cada", "intervalo", "espera",
        "cap", "tope", "a_la_vez", "maximo",
    ])
    return generador


def _read_grab(node: Node) -> Dict[str, object]:
    """El bloque `agarre:` del jugador. Sin el, el juego no lleva agarre y los
    demas numeros no pintan nada."""
    if not node.data:
        return {"grab_time": 0}
    return {
        "grab_time": node.int_(["time", "tiempo", "duracion", "duración"],
                               90, 8, 600),
        "grab_damage": node.int_(["knee", "rodillazo", "dano", "daño"], 1, 0, 99),
        "throw_damage": node.int_(["throw", "lanzamiento", "dano_caida"],
                                  2, 0, 99),
        "throw_speed": node.num(["speed", "fuerza", "velocidad"], 3.5, 0.5, 12.0),
    }


def _read_player(node: Node, root: str) -> Player:
    where = "jugador"
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    player = Player(
        name="player", sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        speed=node.num(["speed", "velocidad"], 1.5, 0.05, 8.0),
        accel=node.num(["accel", "aceleracion", "aceleración"], 0.28, 0.01, 8.0),
        friction=node.num(["friction", "friccion", "fricción"], 0.35, 0.0, 8.0),
        air_accel=node.num(["air_accel", "control_aire", "aceleracion_aire"], 0.16, 0.0, 8.0),
        jump=node.num(["jump", "salto"], 4.3, 0.5, 12.0),
        jump_cut=node.num(["jump_cut", "corte_salto"], 1.6, 0.0, 12.0),
        gravity=node.num(["gravity", "gravedad"], 0.28, 0.01, 4.0),
        max_fall=node.num(["max_fall", "max_caida", "caida_maxima"], 6.0, 0.5, 16.0),
        double_jump=node.bool_(["double_jump", "doble_salto"], False),
        # `salto_fijo: si` quita el mando en el aire: el salto sale con el
        # impulso que llevabas al despegar y hace siempre el mismo arco. Es el
        # salto de las aventuras tipo Dizzy, y es media dificultad del genero.
        air_control=not node.bool_(["fixed_jump", "salto_fijo"], False),
        coyote=node.int_(["coyote", "coyote_time", "margen_salto"], 6, 0, 30),
        jump_buffer=node.int_(["jump_buffer", "buffer_salto"], 6, 0, 30),
        stomp=node.bool_(["stomp", "pisar", "pisar_enemigos"], True),
        bounce=node.num(["bounce", "rebote"], 3.6, 0.0, 12.0),
        health=node.int_(["health", "salud", "vida"], 1, 1, 255),
        # `desgaste:` es lo que convierte la partida en una cuenta atras: cada
        # tantos frames se va un punto de vida sin que nadie te toque, y hay
        # que ir buscando comida. Es la mecanica de Gauntlet.
        wear=node.int_(["wear", "desgaste", "hambre"], 0, 0, 3600),
        # `agarre:` es lo que hace de un juego de tortas un juego de tortas:
        # al que se tambalea de un golpe se le coge, se le zarandea a
        # rodillazos y se le lanza por encima del hombro.
        **_read_grab(node.child("grab", "agarre")),
        invuln=node.int_(["invuln", "invulnerable", "invulnerabilidad"], 90, 0, 600),
        knockback=node.num(["knockback", "retroceso", "empujon", "empujón"], 0.0,
                           0.0, 12.0),
        stun=node.int_(["stun", "aturdido", "aturdimiento"], 0, 0, 120),
        stair_speed=node.num(["stair_speed", "velocidad_escalera", "escalera"],
                             0.0, 0.0, 8.0),
        crouch=node.bool_(["crouch", "agachado", "agacharse", "agachar"], False),
        crouch_h=node.int_(["crouch_h", "caja_agachado", "alto_agachado"], 0, 0, 64),
        attack=_read_attack(node.child("attack", "ataque"), root),
        subs=_read_subs(node.child("sub", "secundaria", "arma_secundaria"),
                        node.child("subs", "secundarias", "armas_secundarias"),
                        root),
    )
    # Sin `retroceso:` el empujon es el de siempre: lo que anda el jugador. Asi
    # un proyecto que no lo pone se comporta exactamente igual que antes.
    if not player.knockback:
        player.knockback = player.speed
    # Y sin `velocidad_escalera:` se sube a la mitad de lo que se anda, que es
    # lo que hace que una escalera sea un sitio incomodo donde te pueden cazar.
    if not player.stair_speed:
        player.stair_speed = player.speed / 2.0
    # Agachado, la caja baja una cuarta parte por arriba: los pies se quedan
    # donde estan y lo que pasa por encima ya no te toca. Es lo que hace que
    # agacharse sirva para algo mas que para la pose.
    if player.crouch and not player.crouch_h:
        player.crouch_h = player.box_h - player.box_h // 4
    if player.crouch and player.crouch_h >= player.box_h:
        raise ProjectError(
            "'caja_agachado' es %d y la caja de pie mide %d: agachado hay que "
            "ocupar menos" % (player.crouch_h, player.box_h),
            hint="quitalo y sale solo (tres cuartas partes de la caja)",
            where=where,
        )
    _warn_unknown(node, where, [
        "sprite", "imagen", "image", "frame", "fotograma", "tamano_frame",
        "hitbox", "caja", "colision", "colisión", "tamano", "tamaño", "size",
        "hitbox_offset", "offset_caja", "desplazamiento",
        "animations", "animaciones", "anims",
        "speed", "velocidad", "accel", "aceleracion", "aceleración",
        "friction", "friccion", "fricción", "air_accel", "control_aire",
        "aceleracion_aire", "jump", "salto", "jump_cut", "corte_salto",
        "gravity", "gravedad", "max_fall", "max_caida", "caida_maxima",
        "double_jump", "doble_salto", "fixed_jump", "salto_fijo",
        "coyote", "coyote_time", "margen_salto",
        "jump_buffer", "buffer_salto", "stomp", "pisar", "pisar_enemigos",
        "bounce", "rebote", "health", "salud", "vida", "invuln", "invulnerable",
        "wear", "desgaste", "hambre", "grab", "agarre",
        "invulnerabilidad", "attack", "ataque",
        "knockback", "retroceso", "empujon", "empujón",
        "stun", "aturdido", "aturdimiento",
        "stair_speed", "velocidad_escalera", "escalera",
        "crouch", "agachado", "agacharse", "agachar",
        "crouch_h", "caja_agachado", "alto_agachado",
        "sub", "secundaria", "arma_secundaria",
        "subs", "secundarias", "armas_secundarias",
    ])
    return player


def _read_enemy(name: str, data: Any, root: str) -> Enemy:
    where = "enemigos.%s" % name
    node = Node(data, where)
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    behavior = node.choice(["behavior", "comportamiento", "ia"], BEHAVIORS, "patrol")
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    default_gravity = 0.0 if behavior in ("flyer", "static") else 0.28
    return Enemy(
        name=name, sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        behavior=behavior,
        speed=node.num(["speed", "velocidad"], 0.5, 0.0, 8.0),
        gravity=node.num(["gravity", "gravedad"], default_gravity, 0.0, 4.0),
        health=node.int_(["health", "salud", "vida"], 1, 1, 99),
        # Hasta 99 y no 9: con `desgaste:` la vida son cientos de puntos
        # y un golpe de uno no se notaria.
        damage=node.int_(["damage", "dano", "daño"], 1, 0, 99),
        score=node.int_(["score", "puntos"], 100, 0, 99999),
        stompable=node.bool_(["stompable", "pisable"], True),
        edge_turn=node.bool_(["edge_turn", "girar_en_borde", "girar"], True),
        boss=node.bool_(["jefe", "boss"], False),
        range=node.num(["range", "rango", "vista"], 96.0, 0.0, 512.0),
        amplitude=node.num(["amplitude", "amplitud"], 24.0, 0.0, 200.0),
        period=node.int_(["period", "periodo", "período"], 120, 8, 1200),
        jump=node.num(["jump", "salto"], 3.5, 0.0, 12.0),
        interval=node.int_(["interval", "intervalo"], 90, 8, 1200),
        shot=_read_enemy_shot(node.child("shot", "dispara", "disparo"), root, where),
        # `golpe:` convierte a un enemigo en un rival: se coloca, se prepara
        # -y se le ve venir- y suelta un golpe que deja hueco para responder.
        **_read_enemy_hit(node.child("hit", "golpe", "ataque")),
    )


def _read_enemy_hit(node: Node) -> Dict[str, int]:
    """`golpe:` en un enemigo: su ataque cuerpo a cuerpo.

    Sin este bloque el enemigo hace dano al tocarte, que es lo de siempre en un
    plataformas. Con el deja de ser un obstaculo y pasa a ser alguien con quien
    se pelea: se pone a distancia, avisa, pega y se queda vendido un momento.

    Los cuatro tiempos son los de cualquier juego de pelea y los cuatro se
    notan al mando: `preparacion:` es el aviso -sin el no hay forma de
    esquivar-, `duracion:` lo que la caja hace dano, `recuperar:` lo que se
    queda plantado despues -esa es tu ventana- y `espera:` lo que tarda en
    volver a intentarlo."""
    if not node.data:
        return {}
    return dict(
        reach=node.int_(["reach", "alcance"], 14, 4, 96),
        windup=node.int_(["windup", "preparacion", "preparación", "aviso"],
                         16, 0, 120),
        active=node.int_(["active", "duracion", "duración"], 6, 1, 60),
        recover=node.int_(["recover", "recuperar", "recuperacion",
                           "recuperación"], 20, 0, 120),
        wait=node.int_(["wait", "espera", "cadencia"], 40, 0, 600),
        punch=node.int_(["damage", "dano", "daño"], 0, 0, 99),
    )


def _read_enemy_shot(node: Node, root: str, donde: str) -> Optional[EnemyShot]:
    """`dispara:` en un enemigo: lo que te tira y cada cuanto.

    Sin este bloque un enemigo solo hace dano al tocarte, que es lo de toda la
    vida en un plataformas. Con el, te tirotea desde lejos, que es lo que
    convierte una pantalla en un juego de comando."""
    if not node.data:
        return None
    where = donde + ".dispara"
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    disparo = EnemyShot(
        name=where, sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        speed=node.num(["speed", "velocidad"], 2.0, 0.1, 8.0),
        range=node.num(["range", "alcance"], 200.0, 8.0, 1024.0),
        cooldown=node.int_(["cooldown", "espera", "cadencia"], 90, 4, 1200),
        # Hasta 99 y no 9: con `desgaste:` la vida son cientos de puntos
        # y un golpe de uno no se notaria.
        damage=node.int_(["damage", "dano", "daño"], 1, 0, 99),
    )
    _warn_unknown(node, where, [
        "sprite", "imagen", "image", "frame", "fotograma", "tamano_frame",
        "hitbox", "caja", "colision", "colisión", "tamano", "tamaño", "size",
        "hitbox_offset", "offset_caja", "desplazamiento",
        "animations", "animaciones", "anims",
        "speed", "velocidad", "range", "alcance",
        "cooldown", "espera", "cadencia", "damage", "dano", "daño",
    ])
    return disparo


def _read_item(name: str, data: Any, root: str) -> Item:
    where = "objetos.%s" % name
    node = Node(data, where)
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    objeto = Item(
        name=name, sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        effect=node.choice(["effect", "efecto", "tipo"], ITEM_EFFECTS, "points"),
        score=node.int_(["score", "puntos"], 10, 0, 99999),
        # Hasta 99: con `desgaste:` la vida son cientos de puntos y la
        # comida tiene que devolver un pellizco de verdad.
        amount=node.int_(["amount", "cantidad"], 1, 1, 99),
        # con 'efecto: subarma', a que arma secundaria cambia
        weapon=node.str_(["weapon", "arma", "secundaria"], "") or "",
        # como sale en la bolsa, para los objetos que se llevan
        label=(node.str_(["label", "marcador", "etiqueta"], "") or "").upper(),
    )
    if not objeto.label:
        # sin `marcador:`, el propio nombre en mayusculas y recortado a cinco
        objeto.label = str(name).upper().replace(" ", "")[:5]
    return objeto


PLATFORM_AXES = {
    "x": "x", "horizontal": "x", "lado": "x", "de_lado": "x",
    "y": "y", "vertical": "y", "arriba": "y", "arriba_abajo": "y",
}


def _read_platform(name: str, data: Any, root: str) -> Platform:
    where = "plataformas.%s" % name
    node = Node(data, where)
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (16, 16))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    return Platform(
        name=name, sprite=sprite, frame_w=fw, frame_h=fh,
        box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims,
        axis=node.choice(["axis", "eje", "movimiento"], PLATFORM_AXES, "x"),
        speed=node.num(["speed", "velocidad"], 0.5, 0.0, 8.0),
        distance=node.int_(["distance", "distancia", "recorrido"], 64, 0, 512),
    )


def _read_block(name: str, data: Any, root: str) -> Block:
    """Un cubo de la vista isometrica: solo dibujo y caja."""
    where = "bloques.%s" % name
    node = Node(data, where)
    sprite = node.str_(["sprite", "imagen", "image"], required=True)
    _require_file(root, sprite, where)
    fw, fh, bw, bh, bx, by = _actor_geometry(node, where, (32, 32))
    anims = _read_animations(node.child("animations", "animaciones", "anims"), where)
    return Block(name=name, sprite=sprite, frame_w=fw, frame_h=fh,
                 box_w=bw, box_h=bh, box_x=bx, box_y=by, animations=anims)


DEFAULT_LEGEND = {
    ".": TileDef(".", 0, "empty"),
    " ": TileDef(" ", 0, "empty"),
    "#": TileDef("#", 1, "solid"),
    "=": TileDef("=", 2, "platform"),
    "^": TileDef("^", 3, "hazard"),
    "G": TileDef("G", 4, "goal"),
}


def _read_tiles(node: Node, root: str) -> Tuple[Tileset, Dict[str, TileDef]]:
    where = "tiles"
    image = node.str_(["image", "imagen", "sprite"], required=True)
    _require_file(root, image, where)
    size = node.int_(["size", "tamano", "tamaño"], 16)
    if size != 16:
        raise ProjectError(
            "los tiles miden %d px y el motor usa bloques de 16x16" % size,
            hint="deja 'tamano: 16' o quita la opcion",
            where=where,
        )
    sala = node.child("sala", "room", "habitacion")
    sala_tile, sala_w, sala_h, sala_x, sala_y = -1, 16, 8, 2, 5
    if sala.data:
        sala_tile = sala.int_(["tile", "indice", "índice", "id"], 0, minimum=0)
        sala_w = sala.int_(["ancho", "width", "cols"], 16, 1, 40)
        sala_h = sala.int_(["alto", "height", "filas"], 8, 1, 28)
        sala_x = sala.int_(["x", "columna"], 2, 0, 39)
        sala_y = sala.int_(["y", "fila"], 5, 0, 27)
    legend_node = node.child("legend", "leyenda", "mapa_tiles")
    tiles: Dict[str, TileDef] = {}
    if not legend_node.data:
        tiles = dict(DEFAULT_LEGEND)
    else:
        for key, value in legend_node.data.items():
            char = str(key)
            if len(char) != 1:
                raise ProjectError(
                    "la leyenda usa '%s' y cada simbolo del mapa es un solo caracter" % char,
                    where=where,
                )
            sub_where = "tiles.leyenda['%s']" % char
            if isinstance(value, (int, float)):
                index = int(value)
                kind = "solid" if index > 0 else "empty"
            elif isinstance(value, (list, tuple)) and len(value) == 2:
                index = int(value[0])
                kind = TILE_KINDS.get(str(value[1]).strip().lower())
                if kind is None:
                    raise ProjectError(
                        "tipo de tile desconocido '%s'" % value[1],
                        hint="tipos: %s" % ", ".join(sorted(TILE_KIND_ID)),
                        where=sub_where,
                    )
            needs = ""
            alto, bloque, pintado = 0, "", False
            if isinstance(value, dict):
                sub = Node(value, sub_where)
                index = sub.int_(["tile", "indice", "índice", "id"], 0, minimum=0)
                kind = sub.choice(["type", "tipo", "clase"], TILE_KINDS, "solid")
                # con `tipo: cerrojo`, que objeto lo abre
                needs = sub.str_(["needs", "abre_con", "pide", "llave",
                                  "objeto"], "") or ""
                # y en la vista isometrica, lo que levanta la casilla
                alto = sub.int_(["alto", "altura", "height", "relieve"], 0, 0, 255)
                bloque = sub.str_(["bloque", "cubo", "block"], "") or ""
                if bloque.strip().lower() in PINTADO:
                    bloque, pintado = "", True
            elif not isinstance(value, (int, float, list, tuple)):
                sub = Node(value, sub_where)
                index = sub.int_(["tile", "indice", "índice", "id"], 0, minimum=0)
                kind = sub.choice(["type", "tipo", "clase"], TILE_KINDS, "solid")
            if index < 0:
                raise ProjectError("el numero de tile no puede ser negativo", where=sub_where)
            tiles[char] = TileDef(char, index, kind, needs, alto, bloque, pintado)
        tiles.setdefault(".", TileDef(".", 0, "empty"))
        tiles.setdefault(" ", TileDef(" ", 0, "empty"))
    return Tileset(image=image, size=size, sala_tile=sala_tile,
                   sala_w=sala_w, sala_h=sala_h,
                   sala_x=sala_x, sala_y=sala_y), tiles


MUESTRA_MAX_SEGUNDOS = 4.0


def _leer_muestra(root: str, relative: str, where: str) -> "wav.Muestra":
    """Lee un WAV del proyecto y lo deja en mono de 8 bits."""
    ruta = _require_file(root, relative, where)
    try:
        muestra = wav.leer(ruta)
    except wav.WavError as error:
        raise ProjectError(str(error), where=where,
                           hint="guardalo como WAV PCM, mono, de 8 o 16 bits")
    if muestra.segundos > MUESTRA_MAX_SEGUNDOS:
        raise ProjectError(
            "la muestra '%s' dura %.1f segundos" % (relative, muestra.segundos),
            hint="los efectos son cortos: recortala a %g segundos o menos"
                 % MUESTRA_MAX_SEGUNDOS,
            where=where)
    return muestra


def _read_sound(raw: Any, root: str = ".", where: str = "sonido") -> "sonido_mod.Sonido":
    """Lee los efectos y la musica. Todo es opcional: sin seccion, hay silencio."""
    resultado = sonido_mod.Sonido()
    if raw is None:
        return resultado
    node = Node(raw, where)

    efectos = node.child("effects", "efectos", "sfx")
    for clave, valor in (efectos.data or {}).items():
        nombre = str(clave).strip().lower()
        nombre = sonido_mod.EVENTO_ALIAS.get(nombre, nombre)
        sub_where = "%s.efectos.%s" % (where, clave)
        if nombre not in sonido_mod.EVENTOS:
            raise ProjectError(
                "'%s' no es un momento del juego con sonido" % clave,
                hint="momentos validos: %s" % ", ".join(sonido_mod.EVENTOS),
                where=sub_where,
            )
        sub = Node(valor, sub_where)
        volumen = sub.int_(["volume", "volumen"], 12, 0, 15)
        # `muestra:` es un eje aparte de `tipo:`, no otro valor suyo: un efecto
        # puede ser una muestra digital **y ademas** llevar notas o ruido, que
        # es lo que suena en las maquinas que no tocan muestras (el Atari ST).
        muestra = None
        ruta_muestra = (sub.str_(["muestra", "sample", "wav"], "")
                        if sub.has("muestra", "sample", "wav") else "")
        tiene_notas = sub.has("notas", "notes", "melodia")
        tiene_ruido = sub.has("ruido", "noise")
        tiene_barrido = sub.has("desde", "from")
        tipo = sub.choice(["type", "tipo"], {
            "notas": "notas", "notes": "notas", "melodia": "notas", "melodía": "notas",
            "barrido": "barrido", "sweep": "barrido",
            "ruido": "ruido", "noise": "ruido",
            "muestra": "", "sample": "", "wav": "",
        }, "notas" if tiene_notas else
           ("ruido" if tiene_ruido else
            ("barrido" if tiene_barrido else ("" if ruta_muestra else "notas"))))
        if not tipo and (tiene_notas or tiene_ruido or tiene_barrido):
            # 'tipo: muestra' escrito a mano, pero con recambio al lado
            tipo = ("notas" if tiene_notas else
                    ("ruido" if tiene_ruido else "barrido"))
        if not tipo and not ruta_muestra:
            raise ProjectError(
                "el efecto '%s' no dice que tiene que sonar" % clave,
                hint="pon 'notas:', 'tipo: barrido', 'tipo: ruido' o 'muestra:'",
                where=sub_where)
        # `fuente` guarda lo que ponia en el yaml, que es lo unico con lo que
        # el editor puede ensenar y cambiar el efecto: de los pasos ya
        # compilados no se vuelve a "do4 mi4".
        fuente = {"tipo": tipo or "muestra", "volumen": volumen}
        if tipo == "notas":
            texto = sub.str_(["notas", "notes", "melodia"], required=True)
            velocidad = sub.int_(["speed", "velocidad", "duracion", "duración"], 4, 1, 60)
            pasos = sonido_mod.parsear_notas(texto or "", velocidad, volumen, sub_where)
            fuente.update(notas=texto or "", velocidad=velocidad)
        elif tipo == "barrido":
            desde = sub.num(["from", "desde"], 300.0, 30.0, 4000.0)
            hasta = sub.num(["to", "hasta"], 900.0, 30.0, 4000.0)
            duracion = sub.int_(["duration", "duracion", "duración", "pasos"], 8, 2, 60)
            pasos = sonido_mod.barrido(desde, hasta, duracion, volumen, sub_where)
            fuente.update(desde=desde, hasta=hasta, duracion=duracion)
        elif tipo == "ruido":
            duracion = sub.int_(["duration", "duracion", "duración"], 8, 1, 60)
            tono = sub.int_(["tono", "tone"], 16, 1, 31)
            pasos = sonido_mod.ruido(duracion, volumen, tono)
            fuente.update(duracion=duracion, tono=tono)
        else:
            pasos = []                       # solo muestra, sin recambio
        if ruta_muestra:
            muestra = _leer_muestra(root, ruta_muestra, sub_where)
            fuente["muestra"] = ruta_muestra
        resultado.efectos[nombre] = sonido_mod.Efecto(
            nombre=nombre, pasos=pasos, muestra=muestra, ruta=ruta_muestra or "",
            fuente=fuente)

    musicas = node.child("music", "musica", "música", "canciones")
    for clave, valor in (musicas.data or {}).items():
        nombre = str(clave)
        sub_where = "%s.musica.%s" % (where, nombre)
        sub = Node(valor, sub_where)
        velocidad = sub.int_(["speed", "velocidad", "tempo"], 8, 1, 60)
        volumen = sub.int_(["volume", "volumen"], 11, 0, 15)
        bucle = sub.bool_(["loop", "bucle", "repetir"], True)
        pistas_raw = sub.raw("tracks", "pistas", "canales")
        if pistas_raw is None:
            raise ProjectError(
                "la musica '%s' no tiene pistas" % nombre,
                hint="anade 'pistas:' con una o dos lineas de notas",
                where=sub_where,
            )
        if isinstance(pistas_raw, str):
            pistas_raw = [pistas_raw]
        if len(pistas_raw) > 2:
            raise ProjectError(
                "la musica '%s' tiene %d pistas y solo hay 2 canales libres"
                % (nombre, len(pistas_raw)),
                hint="el tercer canal del chip se reserva para los efectos",
                where=sub_where,
            )
        pistas = [
            sonido_mod.parsear_notas(str(pista), velocidad, volumen,
                                     "%s.pistas[%d]" % (sub_where, i + 1))
            for i, pista in enumerate(pistas_raw)
        ]
        resultado.musica[nombre] = sonido_mod.Musica(
            nombre=nombre, velocidad=velocidad, pistas=pistas, bucle=bucle,
            fuente={"velocidad": velocidad, "volumen": volumen, "bucle": bucle,
                    "pistas": [str(p) for p in pistas_raw]})

    # Las dos canciones que no son de ningun nivel. Se dicen por su nombre, y
    # el nombre tiene que existir: escribirlo mal y quedarte sin musica en el
    # titulo sin que nadie te diga nada seria lo peor de los dos mundos.
    for campo, claves in (("titulo", ["titulo", "título", "title", "musica_titulo"]),
                          ("jefe", ["jefe", "boss", "musica_jefe"])):
        nombre = node.str_(claves, "")
        if not nombre:
            continue
        if nombre not in resultado.musica:
            raise ProjectError(
                "la musica '%s' no existe" % nombre,
                hint="las que hay son: %s" % (", ".join(resultado.musica) or "ninguna"),
                where="%s.%s" % (where, campo),
            )
        setattr(resultado, campo, nombre)

    _warn_unknown(node, where, ["effects", "efectos", "sfx", "music", "musica",
                                "música", "canciones",
                                "titulo", "título", "title", "musica_titulo",
                                "jefe", "boss", "musica_jefe"])
    return resultado


def _read_layers(raw: Any, root: str, where: str = "fondos") -> Dict[str, Layer]:
    """Lee las capas de parallax, de la mas lejana a la mas cercana."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        raw = [dict(value or {}, nombre=key) for key, value in raw.items()]
    if not isinstance(raw, list):
        raise ProjectError("'fondos' debe ser una lista de capas", where=where)
    layers: Dict[str, Layer] = {}
    for i, item in enumerate(raw):
        sub_where = "%s[%d]" % (where, i + 1)
        node = Node(item, sub_where)
        image = node.str_(["image", "imagen", "sprite"], required=True)
        _require_file(root, image, sub_where)
        name = node.str_(["name", "nombre"], "capa%d" % (i + 1)) or "capa%d" % (i + 1)
        if name in layers:
            raise ProjectError("hay dos capas de fondo llamadas '%s'" % name, where=sub_where)
        layers[name] = Layer(
            name=name, image=image,
            speed_x=node.num(["speed", "velocidad", "velocidad_x"], 0.5, 0.0, 4.0),
            speed_y=node.num(["speed_y", "velocidad_y"], 0.0, 0.0, 4.0),
            offset_y=node.int_(["y", "offset_y", "altura"], 0, -256, 256),
            repeat=node.bool_(["repeat", "repetir"], True),
        )
        _warn_unknown(node, sub_where, [
            "image", "imagen", "sprite", "name", "nombre",
            "speed", "velocidad", "velocidad_x", "speed_y", "velocidad_y",
            "y", "offset_y", "altura", "repeat", "repetir",
        ])
    return layers


def _read_levels(raw_levels: Any, tiles: Dict[str, TileDef], spawn_names: List[str],
                 global_spawns: Dict[str, str], default_bg: Tuple[int, int, int],
                 warnings: List[str], necesitan_suelo: Optional[Dict[str, bool]] = None,
                 layer_names: Optional[List[str]] = None,
                 music_names: Optional[List[str]] = None,
                 jefes: Optional[set] = None,
                 llaves: Optional[Dict[str, int]] = None) -> List[Level]:
    if not raw_levels:
        raise ProjectError(
            "el juego no tiene niveles",
            hint="anade una seccion 'niveles:' con al menos un mapa",
            where="niveles",
        )
    if isinstance(raw_levels, dict):
        raw_levels = [dict(value or {}, nombre=key) for key, value in raw_levels.items()]
    if not isinstance(raw_levels, list):
        raise ProjectError("'niveles' debe ser una lista", where="niveles")

    levels: List[Level] = []
    for i, raw in enumerate(raw_levels):
        where = "niveles[%d]" % (i + 1)
        node = Node(raw, where)
        name = node.str_(["name", "nombre"], "NIVEL %d" % (i + 1))
        text = node.raw("map", "mapa", "tilemap")
        if text is None:
            raise ProjectError(
                "el nivel no tiene mapa",
                hint="anade 'mapa: |' seguido de las filas del nivel",
                where=where,
            )
        rows = [line.rstrip("\n") for line in str(text).split("\n")]
        while rows and not rows[-1].strip():
            rows.pop()
        while rows and not rows[0].strip():
            rows.pop(0)
        if not rows:
            raise ProjectError("el mapa esta vacio", where=where)
        width = max(len(r) for r in rows)
        rows = [r.ljust(width) for r in rows]
        spawns = dict(global_spawns)
        spawns.update({str(k): str(v) for k, v in
                       (node.child("spawns", "entidades", "objetos").data or {}).items()})
        bg = node.raw("background", "fondo", "color_fondo")
        background = parse_color(bg, where) if bg is not None else default_bg
        capas = node.raw("layers", "fondos", "capas")
        if capas is None:
            usadas = list(layer_names or [])
        else:
            if isinstance(capas, str):
                capas = [capas]
            usadas = [str(c) for c in capas]
            for nombre_capa in usadas:
                if nombre_capa not in (layer_names or []):
                    raise ProjectError(
                        "el nivel usa la capa de fondo '%s', que no esta definida"
                        % nombre_capa,
                        hint="definela en la seccion 'fondos:'",
                        where=where,
                    )
        musica = node.str_(["music", "musica", "música", "cancion"], "") or ""
        if musica and musica not in (music_names or []):
            raise ProjectError(
                "el nivel usa la musica '%s', que no esta definida" % musica,
                hint="definela en 'sonido: musica:'",
                where=where,
            )
        piden = node.int_(["keys", "llaves", "llaves_meta"], 0)
        if piden < 0 or piden > 99:
            raise ProjectError(
                "el nivel pide %d llaves; van de 0 a 99" % piden,
                hint="pon 'llaves: 3' o quita la linea si la meta esta abierta",
                where=where,
            )
        level = Level(name=name, rows=rows, spawns=spawns, background=background,
                      layers=usadas, music=musica, keys_needed=piden)
        _validate_level(level, tiles, spawn_names, where, warnings,
                        necesitan_suelo or {}, jefes or set(), llaves or {})
        levels.append(level)
    return levels


PLAYER_CHAR = "P"


def _validate_level(level: Level, tiles: Dict[str, TileDef], spawn_names: List[str],
                    where: str, warnings: List[str],
                    necesitan_suelo: Optional[Dict[str, bool]] = None,
                    jefes: Optional[set] = None,
                    llaves: Optional[Dict[str, int]] = None) -> None:
    height = len(level.rows)
    width = len(level.rows[0])
    if width < 20 or height < 14:
        raise ProjectError(
            "el nivel mide %dx%d tiles y la pantalla ya ocupa 20x14" % (width, height),
            hint="haz el mapa mas grande (20 columnas x 14 filas como minimo)",
            where=where,
        )
    if width > 512 or height > 256:
        raise ProjectError(
            "el nivel mide %dx%d tiles, demasiado para la ROM" % (width, height),
            hint="maximo 512x256 tiles",
            where=where,
        )
    necesitan_suelo = necesitan_suelo or {}
    jefes = jefes or set()
    llaves = llaves or {}
    hay_llaves = 0            # llaves que se pueden coger en este mapa
    hay_jefe = False
    starts: List[Tuple[int, int]] = []
    unknown: Dict[str, Tuple[int, int]] = {}
    sin_suelo: List[Tuple[str, int, int]] = []

    def hay_suelo(x: int, y: int) -> bool:
        if y + 1 >= height:
            return False
        debajo = level.rows[y + 1][x]
        return debajo in tiles and tiles[debajo].kind in ("solid", "platform")

    for y, row in enumerate(level.rows):
        for x, ch in enumerate(row):
            if ch == PLAYER_CHAR:
                starts.append((x, y))
                continue
            if ch in level.spawns:
                nombre = level.spawns[ch]
                if nombre not in spawn_names:
                    raise ProjectError(
                        "el simbolo '%s' apunta a '%s', que no esta definido"
                        % (ch, nombre),
                        hint="definelo en 'enemigos:' u 'objetos:'",
                        where=where,
                    )
                if necesitan_suelo.get(nombre) and not hay_suelo(x, y):
                    sin_suelo.append((nombre, x + 1, y + 1))
                if nombre in jefes:
                    hay_jefe = True
                hay_llaves += llaves.get(nombre, 0)
                continue
            if ch not in tiles and ch not in unknown:
                unknown[ch] = (x + 1, y + 1)
    if level.keys_needed > hay_llaves:
        raise ProjectError(
            "la meta pide %d llaves y en el mapa solo hay %d"
            % (level.keys_needed, hay_llaves),
            hint="pon mas llaves en el mapa o baja el numero de 'llaves:'",
            where=where,
        )
    if unknown:
        ch, (col, line) = sorted(unknown.items())[0]
        raise ProjectError(
            "el mapa usa el simbolo '%s' (fila %d, columna %d) y no esta en la leyenda"
            % (ch, line, col),
            hint="anadelo en 'tiles: leyenda:' o en 'spawns:' del nivel",
            where=where,
        )
    if not starts:
        raise ProjectError(
            "el nivel no tiene punto de salida del jugador",
            hint="pon una 'P' en el mapa donde empieza el jugador",
            where=where,
        )
    if len(starts) > 1:
        raise ProjectError(
            "el nivel tiene %d salidas 'P' y solo puede haber una" % len(starts),
            where=where,
        )
    level.start = starts[0]
    has_goal = any(
        tiles[ch].kind == "goal" for row in level.rows for ch in row if ch in tiles
    )
    # un jefe tambien termina el nivel, asi que ahi no hace falta meta
    if not has_goal and not hay_jefe:
        warnings.append(
            "%s ('%s') no tiene tile de meta ni jefe: el nivel no se puede terminar"
            % (where, level.name)
        )
    for nombre, col, fila in sin_suelo[:3]:
        warnings.append(
            "%s ('%s'): el enemigo '%s' de la fila %d, columna %d no tiene suelo "
            "debajo y se caera nada mas empezar"
            % (where, level.name, nombre, fila, col)
        )


SALA = 8            # lo que mide una sala, en casillas (NP_SALA del motor)


def _revisar_isometrica(levels, tiles, tileset, blocks, warnings) -> None:
    """Lo que tiene que cuadrar en un juego de salas isometricas.

    Son cuatro cosas, y las cuatro dan un error claro en vez de un juego raro:
    el mapa se reparte en salas enteras de 8x8, cada casilla que levanta trae
    su cubo, ese cubo mide lo que levanta y el tileset trae el dibujo del suelo
    de la sala.
    """
    if tileset.sala_tile < 0:
        raise ProjectError(
            "un juego de vista isometrica necesita el dibujo del suelo de la sala",
            hint="anade a 'tiles:' un bloque 'sala: {tile: N, ancho: 16, alto: 11}' "
                 "que diga que trozo del tileset es el dibujo de una habitacion",
            where="tiles")
    for tile in tiles.values():
        donde = "tiles.leyenda['%s']" % tile.char
        if tile.alto and not tile.bloque and not tile.pintado:
            raise ProjectError(
                "el tile '%s' levanta %d pixeles pero no dice con que cubo se "
                "dibuja" % (tile.char, tile.alto),
                hint="anade 'cubo: <nombre>' con uno de los de 'cubos:', o "
                     "'cubo: pintado' si ese trozo ya viene dibujado en 'sala:'",
                where=donde)
        if tile.bloque and tile.bloque not in blocks:
            raise ProjectError(
                "el tile '%s' se dibuja con el cubo '%s', que no existe"
                % (tile.char, tile.bloque),
                hint="los cubos que hay son: %s" % (", ".join(blocks) or "ninguno"),
                where=donde)
        if not tile.bloque:
            continue
        cubo = blocks[tile.bloque]
        # Un prisma de `alto` pixeles sobre un rombo de 32x16 ocupa 32 de ancho
        # y alto+16 de alto. Si el dibujo no mide eso, el cubo se vera flotando
        # o hundido en el suelo, que es de esas cosas que uno mira diez minutos
        # sin saber por que no encajan.
        if cubo.frame_w != 32 or cubo.frame_h != tile.alto + 16:
            warnings.append(
                "el cubo '%s' mide %dx%d y para un alto de %d deberia medir 32x%d"
                % (tile.bloque, cubo.frame_w, cubo.frame_h, tile.alto,
                   tile.alto + 16))
    for nivel in levels:
        ancho, alto = len(nivel.rows[0]), len(nivel.rows)
        if ancho % SALA or alto % SALA:
            raise ProjectError(
                "el nivel '%s' mide %dx%d casillas y las salas son de %dx%d"
                % (nivel.name, ancho, alto, SALA, SALA),
                hint="en la vista isometrica el mapa es la planta y se reparte "
                     "en habitaciones enteras: pon medidas multiplos de %d" % SALA,
                where="niveles")


def _require_file(root: str, relative: str, where: str) -> str:
    path = os.path.join(root, relative)
    if not os.path.isfile(path):
        raise ProjectError(
            "no encuentro el archivo '%s'" % relative,
            hint="ruta buscada: %s" % path,
            where=where,
        )
    return path


def _warn_unknown(node: Node, where: str, allowed: Sequence[str]) -> None:
    extra = node.check_unknown(allowed)
    if extra:
        raise ProjectError(
            "opcion desconocida '%s'" % extra[0],
            hint="revisa la ortografia; opciones validas en docs/formato.md",
            where=where,
        )


def load_project(path: str) -> Project:
    """Carga `game.yaml` (o la carpeta que lo contiene) ya validado."""
    if os.path.isdir(path):
        for candidate in ("game.yaml", "juego.yaml", "game.yml", "juego.yml"):
            full = os.path.join(path, candidate)
            if os.path.isfile(full):
                path = full
                break
        else:
            raise ProjectError(
                "no hay ningun game.yaml en '%s'" % path,
                hint="crea un proyecto nuevo con: ngplat nuevo mijuego",
            )
    if not os.path.isfile(path):
        raise ProjectError("no encuentro '%s'" % path)

    root = os.path.dirname(os.path.abspath(path)) or "."
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise ProjectError(
            "el archivo no describe un juego",
            hint="debe empezar por 'juego:' con el titulo",
            where=os.path.basename(path),
        )
    top = Node(data, os.path.basename(path))
    warnings: List[str] = []

    game = top.child("game", "juego")
    title = (game.str_(["title", "titulo", "título"], "NEOPLAT") or "NEOPLAT")
    author = (game.str_(["author", "autor"], "") or "")
    lives = game.int_(["lives", "vidas"], 3, 1, 9)
    players = game.int_(["players", "jugadores"], 1, 1, 2)
    time_limit = game.int_(["time", "tiempo", "tiempo_limite"], 0, 0, 999)
    hud = game.bool_(["hud", "marcador"], True)
    camera = _leer_camara(game)
    # `agresivos:` es el numero de enemigos que pueden estar pegando a la vez.
    # Solo lo miran los juegos de tortas; en el resto no hay a quien repartir.
    aggressive = game.int_(["aggressive", "agresivos", "a_la_vez"], 2, 1, 8)
    view = _leer_vista(game)
    amiga_modo = _leer_modo_amiga(game)
    sistema = (game.str_(["system", "sistema", "maquina", "máquina"], "neogeo") or "neogeo")
    bg = game.raw("background", "fondo", "color_fondo")
    default_bg = parse_color(bg, "juego") if bg is not None else (16, 24, 48)

    player = _read_player(top.child("player", "jugador"), root)
    tileset, tiles = _read_tiles(top.child("tiles", "tileset", "bloques"), root)

    enemies: Dict[str, Enemy] = {}
    for name, data_enemy in (top.child("enemies", "enemigos").data or {}).items():
        enemies[str(name)] = _read_enemy(str(name), data_enemy, root)
    items: Dict[str, Item] = {}
    for name, data_item in (top.child("items", "objetos").data or {}).items():
        items[str(name)] = _read_item(str(name), data_item, root)
    platforms: Dict[str, Platform] = {}
    for name, data_plat in (top.child("platforms", "plataformas").data or {}).items():
        platforms[str(name)] = _read_platform(str(name), data_plat, root)
    breakables: Dict[str, Breakable] = {}
    for name, data_rom in (top.child("breakables", "rompibles").data or {}).items():
        breakables[str(name)] = _read_breakable(str(name), data_rom, root)

    # Los cubos de la vista isometrica. La seccion se llama 'cubos:' y no
    # 'bloques:' porque 'bloques' ya es un alias de la seccion de tiles desde la
    # primera version del kit, y cambiarlo romperia los juegos de la gente.
    blocks: Dict[str, Block] = {}
    for name, data_blk in (top.child("blocks", "cubos").data or {}).items():
        blocks[str(name)] = _read_block(str(name), data_blk, root)

    prisoners: Dict[str, Prisoner] = {}
    for name, data_pri in (top.child("prisoners", "prisioneros",
                                     "rehenes").data or {}).items():
        prisoners[str(name)] = _read_prisoner(str(name), data_pri, root)

    generators: Dict[str, Generator] = {}
    for name, data_gen in (top.child("generators", "generadores",
                                     "nidos").data or {}).items():
        generators[str(name)] = _read_generator(str(name), data_gen, root)
    # el enemigo que saca tiene que existir: si no, el generador estaria ahi
    # soltando nada y nadie lo diria
    for nombre, gen in generators.items():
        if gen.enemy not in enemies:
            raise ProjectError(
                "el generador '%s' saca '%s', que no esta en 'enemigos:'"
                % (nombre, gen.enemy),
                hint="los enemigos que hay son: %s" % (", ".join(enemies) or "ninguno"),
                where="generadores.%s" % nombre,
            )
    # el objeto que cambia de arma tiene que decir a cual, y esa tiene que
    # existir: si no, se cogeria y no pasaria nada
    nombres_armas = [arma.name for arma in player.subs]
    for nombre, objeto in items.items():
        if objeto.effect != "weapon":
            continue
        if not objeto.weapon:
            raise ProjectError(
                "el objeto '%s' cambia de arma secundaria pero no dice a cual"
                % nombre,
                hint="anade 'arma: %s'" % (nombres_armas[0] if nombres_armas
                                           else "hacha"),
                where="objetos.%s" % nombre)
        if objeto.weapon not in nombres_armas:
            raise ProjectError(
                "el objeto '%s' cambia al arma '%s', que no existe"
                % (nombre, objeto.weapon),
                hint=("definela en 'jugador: secundarias:'; ahora mismo hay: %s"
                      % (", ".join(nombres_armas) or "ninguna")),
                where="objetos.%s" % nombre)

    for nombre, rompible in breakables.items():
        if rompible.drop and rompible.drop not in items:
            raise ProjectError(
                "el rompible '%s' suelta '%s', que no es ningun objeto"
                % (nombre, rompible.drop),
                hint="definelo en 'objetos:', o quita la linea 'suelta:'",
                where="rompibles.%s" % nombre)

    # Un nombre repetido en dos secciones no se puede resolver: el simbolo del
    # mapa saldria como una cosa o como otra segun el orden en que se miren las
    # listas, que no es algo que nadie tenga que saber. Se miran las seis, dos
    # a dos, para que no se quede fuera ninguna al anadir una nueva.
    secciones = (("enemigo", enemies), ("objeto", items),
                 ("plataforma", platforms), ("rompible", breakables),
                 ("prisionero", prisoners), ("generador", generators))
    for i, (nombre_a, a) in enumerate(secciones):
        for nombre_b, b in secciones[i + 1:]:
            repetidos = set(a) & set(b)
            if repetidos:
                raise ProjectError(
                    "'%s' esta definido como %s y como %s"
                    % (sorted(repetidos)[0], nombre_a, nombre_b),
                    hint="usa nombres distintos",
                )

    # Lo que pide un cerrojo tiene que existir y tiene que ser de los que se
    # llevan: una puerta que pide algo que no se puede coger no se abre nunca,
    # y eso no es un puzle dificil, es un juego roto.
    for char, tile in tiles.items():
        if tile.kind != "lock":
            continue
        donde = "tiles.leyenda['%s']" % char
        if not tile.needs:
            raise ProjectError(
                "el cerrojo '%s' no dice con que se abre" % char,
                hint="anade 'abre_con: <objeto>' con un objeto de "
                     "'efecto: llevar'",
                where=donde)
        objeto = items.get(tile.needs)
        if objeto is None:
            raise ProjectError(
                "el cerrojo '%s' se abre con '%s', que no es ningun objeto"
                % (char, tile.needs),
                hint="los objetos que hay son: %s" % (", ".join(items) or "ninguno"),
                where=donde)
        if objeto.effect != "carry":
            raise ProjectError(
                "el cerrojo '%s' se abre con '%s', que no se puede llevar"
                % (char, tile.needs),
                hint="ponle 'efecto: llevar' a ese objeto: los cerrojos se "
                     "abren con lo que llevas en la bolsa",
                where=donde)

    global_spawns = {str(k): str(v) for k, v in
                     (top.child("spawns", "simbolos", "símbolos").data or {}).items()}
    # Los enemigos con gravedad necesitan suelo debajo; los voladores no. Y
    # mirando desde arriba no lo necesita ninguno: ahi no hay de donde caerse.
    # Mirando desde arriba -y en la cinta, que es la misma manera de andar- no
    # hay de donde caerse: el suelo es toda la franja.
    necesitan_suelo = {
        name: (view not in ("cenital", "cinta", "iso") and enemy.gravity > 0
               and enemy.behavior != "flyer")
        for name, enemy in enemies.items()
    }
    jefes = {name for name, enemy in enemies.items() if enemy.boss}
    # Cuantas llaves da cada objeto, para poder avisar de una meta imposible.
    llaves = {name: item.amount for name, item in items.items()
              if item.effect == "key"}
    layers = _read_layers(top.raw("backgrounds", "fondos", "capas"), root)
    sound = _read_sound(top.raw("sound", "sonido", "audio"), root)
    levels = _read_levels(
        top.raw("levels", "niveles"), tiles,
        list(enemies) + list(items) + list(platforms) + list(breakables)
        + list(prisoners) + list(generators),
        global_spawns, default_bg, warnings, necesitan_suelo, list(layers),
        list(sound.musica), jefes=jefes, llaves=llaves,
    )

    known_top = {
        "game", "juego", "player", "jugador", "tiles", "tileset", "bloques",
        "enemies", "enemigos", "items", "objetos", "levels", "niveles",
        "platforms", "plataformas", "breakables", "rompibles",
        "prisoners", "prisioneros", "rehenes",
        "generators", "generadores", "nidos",
        "spawns", "simbolos", "símbolos", "backgrounds", "fondos", "capas",
        "sound", "sonido", "audio", "blocks", "cubos",
    }
    extra_top = [key for key in data if key not in known_top]
    if extra_top:
        raise ProjectError(
            "seccion desconocida '%s'" % extra_top[0],
            hint="secciones validas: juego, jugador, tiles, enemigos, objetos, "
                 "prisioneros, "
                 "fondos, sonido, spawns, niveles",
            where=os.path.basename(path),
        )

    if view == "iso":
        _revisar_isometrica(levels, tiles, tileset, blocks, warnings)

    # La isometrica no entra aqui: sus salas son pantallas por definicion -8x8
    # casillas- y el mapa mide casillas, no pixeles de pantalla.
    if camera == "pantallas" and view != "iso":
        for nivel in levels:
            ancho, alto = len(nivel.rows[0]) * 16, len(nivel.rows) * 16
            if ancho % 320 or (alto > 224 and alto % 224):
                warnings.append(
                    "con la camara por pantallas, '%s' mide %dx%d pixeles y no son "
                    "pantallas enteras (320x224): la ultima se solapara con la "
                    "anterior" % (nivel.name, ancho, alto))
                break

    return Project(
        root=root, title=title.upper()[:24], author=author[:24], system=sistema,
        lives=lives, players=players, camera=camera, view=view,
        aggressive=aggressive,
        amiga_modo=amiga_modo,
        time_limit=time_limit, hud=hud, player=player, tileset=tileset, tiles=tiles,
        enemies=enemies, items=items, platforms=platforms,
        breakables=breakables, blocks=blocks,
        prisoners=prisoners, generators=generators,
        layers=layers, sound=sound, levels=levels,
        warnings=warnings,
    )
