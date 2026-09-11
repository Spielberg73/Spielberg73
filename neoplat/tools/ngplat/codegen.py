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

from .project import VERBOS
from .sonido import EVENTOS
from .build import (
    ANIM_SLOTS, Build, actor_def_values, attack_values, breakable_values,
    enemy_values, item_values, layer_values, platform_values, player_values,
    enemy_shot_values, generator_values, prisoner_values, sub_values,
    tile_tables,
)
from . import carretera as carretera_mod
from .build import coche_values
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
    return "{ 0, 0, 1, 1, 0, 0, 0, 16, 16, { %s } }" % ranuras


def _actor_def(prefix: str, values: Dict[str, object]) -> str:
    anims = []
    for slot, anim in enumerate(values["anims"]):          # type: ignore[index]
        anims.append(
            "        { %s_anim%d, %d, %d, %d }"
            % (prefix, slot, anim["count"], anim["speed"], anim["loop"])
        )
    return (
        "    {\n"
        "        %d, %d, %d, %d, %d,\n"
        "        %d, %d, %d, %d,\n"
        "        {\n%s\n        }\n"
        "    }"
        % (
            values["first_tile"], values["palette"], values["cols"], values["rows"],
            values.get("lejos", 0),
            values["box_x"], values["box_y"], values["box_w"], values["box_h"],
            ",\n".join(anims),
        )
    )


def _carretera_tamanos_c(build: Build) -> List[str]:
    """Los tamanos de cada cosa que sale en la calzada, ya en C.

    De mas cerca a mas lejos, terminados en uno con `cols` a cero. El primero
    es el dibujo natural -la misma hoja de siempre- y los demas las versiones
    encogidas que saco el compilador. Fuera del genero de conducir la tabla
    sigue existiendo, con una entrada muerta, porque un array vacio no es C
    valido y la alternativa seria un #if mas en las ocho maquinas.
    """
    from .build import CARRETERA_ESCALAS
    con_tamanos = sorted(
        (a for a in build.actor_builds() if a.lejos_index),
        key=lambda a: a.lejos_index,
    )
    src = ["/* --- los tamanos de la carretera ------------------------------",
           " *",
           " * Lo que esta en la calzada se ve mas pequeno cuanto mas lejos, y de",
           " * estas ocho maquinas solo la Neo Geo sabe encoger un sprite. Las demas",
           " * lo llevan ya dibujado a varios tamanos, sacados del mismo PNG al",
           " * compilar. Cada dibujo va centrado y apoyado abajo en su bloque de",
           " * tiles, asi que el motor solo pone la esquina y no mira margenes. */"]
    for construido in con_tamanos:
        hojas = [construido.sheet] + construido.lejos
        src.append("static const NpCarreteraTam np_lejos%d[] = {"
                   % (construido.lejos_index - 1))
        for hoja, (escala, desde) in zip(hojas, CARRETERA_ESCALAS):
            src.append("    { %d, %d, %d, %d, %d },   /* a %d/256 */"
                       % (hoja.first_tile, hoja.palette_index, hoja.cols,
                          hoja.rows, desde, escala))
        src.append("    { 0, 0, 0, 0, 0 }")
        src.append("};")
    src.append("const NpCarreteraTam *const np_carretera_tam[] = {")
    if con_tamanos:
        src.append("    " + ", ".join("np_lejos%d" % i
                                      for i in range(len(con_tamanos))))
    else:
        src.append("    0")
    src.append("};")
    src.append("")
    return src


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
    # La vista de cinta, tambien como macro: los dibujantes deciden **al
    # compilar** si tienen que pintar por profundidad. En el Atari ST la
    # indireccion del orden dentro del bucle que dibuja a todos los actores se
    # nota -tanto que la musica empieza a sonar lenta-, y un juego que no es de
    # cinta no tiene por que pagarla.
    header.append("#define NP_VISTA_CINTA %d"
                  % (1 if project.view == "cinta" else 0))
    header.append("/* Como recorren los dibujantes la fila: por profundidad "
                  "en un juego de")
    header.append(" * cinta o isometrico -donde hay un detras de verdad- y en "
                  "el orden de la")
    header.append(" * lista en los demas. Ver np_orden_dibujo. */")
    header.append("#define NP_VISTA_ISO %d"
                  % (1 if project.view == "iso" else 0))
    header.append("#if NP_VISTA_CINTA || NP_VISTA_ISO")
    header.append("#define NP_DIBUJO(orden, i) ((orden)[(i)])")
    header.append("#else")
    # el (void) es para que `orden` cuente como usada: sin el, un juego que no
    # es de cinta no compila con -Werror por una variable "asignada y no usada"
    header.append("#define NP_DIBUJO(orden, i) ((void)(orden), (i))")
    header.append("#endif")
    # Y la carretera, tambien como macro y por lo mismo, solo que aqui no es
    # el dibujo sino la simulacion: la vuelta que mueve el trafico se **borra
    # al compilar** en los nueve generos que no la usan.
    #
    # No es purismo. Llamar a esa vuelta desde donde tocaba -el bucle de
    # enemigos- cuesta 1900 ciclos por frame en la Neo Geo aunque el juego no
    # tenga un solo coche: gcc se la mete dentro, la funcion crece, necesita
    # mas registros y se encarecen todos los bichos de todos los generos. El
    # juego de ejemplo ya gastaba 198744 de los 200000 que da un frame, asi que
    # con eso se pasaba, y un juego que se pasa del frame va a la mitad.
    # Dos mecanicas de plataformas que se borran al compilar si el juego no las
    # usa, por lo mismo que el trafico: su vuelta la recorre cada bicho, y
    # dejarla puesta encarece a todos los generos aunque no haya ninguna.
    _ias = {e.actor.behavior for e in build.enemies}
    header.append("#define NP_HAY_COCODRILOS %d"
                  % (1 if "cocodrilo" in _ias else 0))
    header.append("#define NP_HAY_BALANCEO %d" % (1 if "balanceo" in _ias else 0))
    header.append("#define NP_VISTA_CARRETERA %d"
                  % (1 if project.view == "carretera" else 0))
    # La columna de la imagen de la carretera por la que pasa el eje de la
    # calzada, y cuantos grupos de cuatro franjas hay (calzada, arcen, hierba).
    header.append("#define NP_CARRETERA_EJE %d" % (carretera_mod.ANCHO // 2))
    # Lo que mide el arcen a cada lado, en pixeles de calzada de cerca. Lo
    # necesitan las maquinas que **pintan** la carretera en vez de deslizarla:
    # el Atari ST y el X68000 la rellenan por franjas y la Jaguar la compone
    # con su lista de objetos, y todas tienen que sacar los mismos bordes que
    # saco el compilador al dibujar la textura.
    header.append("#define NP_CARRETERA_ARCEN %d"
                  % (project.asfalto.ancho_arcen if project.view == "carretera"
                     else 8))
    # Con la textura lisa los huecos son cuatro -uno por cosa- en vez de doce,
    # y hay ademas dos tonos por cosa que la maquina escribe linea a linea.
    grupos = len(build.asfalto.franjas) if build.asfalto else 3
    por_grupo = (len(build.asfalto.franjas[0])
                 if build.asfalto and build.asfalto.franjas else 4)
    header.append("#define NP_CARRETERA_LISA %d"
                  % (1 if por_grupo == 1 else 0))
    header.append("#define NP_CARRETERA_GRUPOS %d" % grupos)
    header.append("#define NP_CARRETERA_HUECOS_POR_GRUPO %d" % por_grupo)
    header.append("extern const uint8_t np_carretera_huecos[];")
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
    src.append("/* Desde donde se mira: 0 = de lado (con gravedad), 1 = desde arriba. */")
    # La cinta es una vista cenital que ademas salta: pone las dos banderas
    # para que el movimiento, la punteria y el empujon de los golpes sean los
    # de cenital sin repetir una linea.
    src.append("const uint8_t np_vista_cenital = %d;"
               % (1 if project.view in ("cenital", "cinta", "iso", "puntero",
                                        "carretera")
                  else 0))
    src.append("/* Y si ademas se salta (el 'yo contra el barrio'). */")
    src.append("const uint8_t np_vista_cinta = %d;"
               % (1 if project.view == "cinta" else 0))
    src.append("/* Y la isometrica: la sala vista desde una esquina. Anda como")
    src.append("   la cenital y salta como la cinta, pero con relieve. */")
    src.append("const uint8_t np_vista_iso = %d;"
               % (1 if project.view == "iso" else 0))
    src.append("/* Y la de puntero: la aventura grafica. Se senala con un")
    src.append("   cursor y se elige verbo; no hay fisica que correr. */")
    src.append("const uint8_t np_vista_puntero = %d;"
               % (1 if project.view == "puntero" else 0))
    src.append("/* Y la de carretera: el juego de conducir. Por dentro es el")
    src.append("   plano de la cenital -el mapa es el trazado y el coche lo")
    src.append("   sube-, y lo que cambia es que no se anda: se acelera. */")
    src.append("const uint8_t np_vista_carretera = %d;"
               % (1 if project.view == "carretera" else 0))
    cv = coche_values(project.coche)
    src.append("/* El coche: motor, freno y volante. Solo lo mira la vista de")
    src.append("   carretera; en los demas juegos esta y no cuesta nada. */")
    src.append("const NpCocheDef np_coche = {")
    src.append("    %d, %d,      /* lo que corre con cada marcha */"
               % (cv["punta"], cv["punta_corta"]))
    src.append("    %d, %d,      /* y lo que empuja cada una */"
               % (cv["acelera"], cv["acelera_corta"]))
    src.append("    %d, %d,      /* el freno y el roce */"
               % (cv["frena"], cv["roce"]))
    src.append("    %d,          /* el volante, a punta */" % cv["volante"])
    src.append("    %d, %d,      /* fuera del asfalto: tope y tiron */"
               % (cv["lento"], cv["arrastre"]))
    src.append("    %d, %d       /* trompo, y lo que regala un control */"
               % (cv["trompo"], cv["control"]))
    src.append("};")
    src.append("/* Cuantos enemigos pegan a la vez: el numero que hace que una")
    src.append("   pelea se juegue en vez de sufrirse. */")
    src.append("const uint8_t np_agresivos = %d;" % project.aggressive)
    src.append("/* 1 = el golpe de un enemigo hace dano a otro enemigo */")
    src.append("const uint8_t np_entre_ellos = %d;" % (1 if project.entre_ellos else 0))
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
    # Que objeto abre cada cerrojo (el objeto mas uno; 0 = no es cerrojo).
    indice_objetos = {o.name: i for i, o in enumerate(build.items)}
    necesita = [indice_objetos.get(t.needs, -1) + 1 if t.kind == "lock" else 0
                for t in build.tiles]
    src.append("const uint8_t np_tile_need[] = {")
    src.append(_array(necesita))
    src.append("};")
    # El relieve de la vista isometrica: lo que levanta cada casilla y con que
    # cubo se dibuja (indice + 1, cero = no se dibuja).
    indice_cubos = {c.name: i for i, c in enumerate(build.blocks)}
    src.append("/* Relieve de la vista isometrica: lo que levanta cada casilla")
    src.append("   y con que cubo se pinta. Todo ceros en las demas vistas. */")
    src.append("const uint8_t np_tile_alto[] = {")
    src.append(_array([t.alto for t in build.tiles]))
    src.append("};")
    src.append("const uint8_t np_tile_bloque[] = {")
    src.append(_array([indice_cubos.get(t.bloque, -1) + 1 for t in build.tiles]))
    src.append("};")
    # El dibujo que se ve por el hueco de una puerta abierta: el del primer
    # tile vacio de la leyenda (que es el cielo o el suelo de fondo).
    vacio = next((graphics[i] for i, k in enumerate(kinds) if k == 0), 0)
    # Los disparadores: que guion lanza cada casilla (indice + 1) y si es de
    # los que solo saltan una vez en toda la partida.
    indice_guiones = {n: i for i, n in enumerate(build.guion_orden)}
    src.append("/* Disparadores: el guion que lanza cada casilla al pisarla. */")
    src.append("const uint8_t np_tile_guion[] = {")
    src.append(_array([indice_guiones.get(t.guion, -1) + 1 for t in build.tiles]))
    src.append("};")
    src.append("const uint8_t np_tile_una_vez[] = {")
    src.append(_array([1 if t.una_vez else 0 for t in build.tiles]))
    src.append("};")
    # Y la aventura grafica: que guion contesta cada casilla a cada verbo. Una
    # fila por verbo y un puntero a cada una, porque cuantos tiles hay lo sabe
    # este archivo y no la cabecera.
    src.append("/* Aventura grafica: el guion que contesta cada casilla a cada")
    src.append("   verbo (mirar, coger, usar, hablar). Cero = no contesta. */")
    for numero, verbo in enumerate(VERBOS):
        src.append("static const uint8_t np_tile_verbo%d[] = {" % numero)
        src.append(_array([indice_guiones.get(t.verbos.get(verbo, ""), -1) + 1
                           for t in build.tiles]))
        src.append("};")
    src.append("const uint8_t *const np_tile_verbo[NP_VERBOS] = {")
    src.append("    " + ", ".join("np_tile_verbo%d" % i
                                  for i in range(len(VERBOS))))
    src.append("};")
    src.append("/* El guion de \"aqui no hay nada que hacer\", el que contesta")
    src.append("   cuando la casilla no dice nada. Cero = no contesta nadie. */")
    src.append("const uint8_t np_guion_nada = %d;"
               % (indice_guiones.get(project.guion_nada, -1) + 1))
    src.append("/* Como se llama cada verbo en el marcador. */")
    src.append("const char np_verbo_names[NP_VERBOS][7] = {")
    src.append("    " + ", ".join(_c_string(n[:6]) for n in project.verbos))
    src.append("};")
    # Lo que se ve debajo de una casilla que se quita. Son numeros de tile del
    # propio tileset -no de la leyenda- para que el que dibuja no tenga que
    # mirar dos tablas: le sale el dibujo de una vez.
    orden_tiles = {t.char: i for i, t in enumerate(build.tiles)}
    src.append("/* Lo que se ve debajo de una casilla que se quita (aventura")
    src.append("   grafica). Por defecto, lo mismo que una puerta abierta. */")
    src.append("const uint16_t np_tile_debajo[] = {")
    src.append(_array([graphics[orden_tiles[t.debajo]] if t.debajo in orden_tiles
                       else vacio for t in build.tiles]))
    src.append("};")
    src.append("const uint16_t np_tile_count = %d;" % len(kinds))
    # El dibujo que se ve por el hueco de una puerta abierta: el del primer
    # tile vacio de la leyenda (que es el cielo o el suelo de fondo). Sin esto
    # una puerta abierta se seguiria viendo cerrada.
    src.append("const uint16_t np_tile_gfx_vacio = %d;" % vacio)
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
    src.append("    %d,   /* lo que se sube por una liana */" % pv["climb_speed"])
    src.append("    %d, %d," % (pv["invuln"], pv["stun"]))
    src.append("    %d,   /* desgaste */" % pv["wear"])
    src.append("    %d, %d,   /* el agarre: cuanto dura y con cuanta fuerza lanza */"
               % (pv["grab_time"], pv["throw_speed"]))
    src.append("    %d, %d,   /* rodillazo y estrellon */"
               % (pv["grab_damage"], pv["throw_damage"]))
    src.append("    %d, %d, %d, %d, %d," % (pv["coyote"], pv["jump_buffer"],
                                            pv["double_jump"], pv["stomp"],
                                            pv["health"]))
    src.append("    %d,   /* si se manda en el aire */" % pv["air_control"])
    src.append("    %d,   /* cuanto baja el techo al agacharse */"
               % pv["crouch_drop"])
    # el ataque: su dibujo es el ultimo de la lista de actores, si lo hay
    av = attack_values(project)
    src.append("    /* ataque */")
    src.append("    {")
    if build.attack is not None:
        src.append(_actor_def("np_attack", actor_def_values(build.attack)) + ",")
    else:
        src.append("    " + _actor_vacio() + ",")
    src.append("        %d, %d, %d, %d, %d, %d,"
               % (av["speed"], av["range"], av["cooldown"], av["duration"],
                  av["windup"], av["range_step"]))
    src.append("        %d, %d,   /* la serie: ventana y empujon del remate */"
               % (av["combo_window"], av["finish_push"]))
    src.append("        %d, %d, %d,   /* golpes, dano del remate y derribo */"
               % (av["combo"], av["finish_damage"], av["finish_stun"]))
    src.append("        %d, %d, %d, %d, %d,"
               % (av["levels"], av["kind"], av["damage"], av["locks"],
                  av["fx"]))
    src.append("        %d, %d   /* la patada voladora: alcance y dano */"
               % (av["kick_range"], av["kick_damage"]))
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
    # Como sale cada una en el marcador. Cinco letras: es lo que dejan libres
    # las llaves y la cuenta de municion.
    src.append("const char np_sub_names[][6] = {")
    if not build.subs:
        src.append('    "AMMO"')
    for i, arma in enumerate(build.subs):
        etiqueta = arma.actor.label
        src.append('    "%s"%s' % (etiqueta, "," if i + 1 < len(build.subs) else ""))
    src.append("};")
    src.append("")

    # --- enemigos
    for i, enemy in enumerate(build.enemies):
        src.append("/* enemigo %d: %s */" % (i, enemy.name))
        src.append(_anim_arrays("np_enemy%d" % i, enemy))
    src.append("const NpEnemyDef np_enemies[] = {")
    if not build.enemies:
        # Los veintidos ceros de un enemigo que no existe. Van uno a uno y no
        # a medias: gcc con -Werror no deja un inicializador incompleto, y un
        # juego sin enemigos -una aventura grafica, por ejemplo- es lo que hace
        # que esta linea se compile de verdad alguna vez.
        src.append("    { %s, 0, 0, 0, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0,"
                   "      0, 0, 0, 0, 0, 0, 0, 0 }" % _actor_vacio())
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
        src.append("        %d, %d," % (ev["boss"], ev["shot"]))
        src.append("        /* el golpe: alcance, aviso, dano, recuperar, espera */")
        src.append("        %d, %d, %d, %d, %d, %d,"
                   % (ev["reach"], ev["windup"], ev["active"], ev["recover"],
                      ev["wait"], ev["punch"]))
        src.append("        %d   /* tenaz: te sigue de pantalla en pantalla */"
                   % ev["tenaz"])
        src.append("    }," if i + 1 < len(build.enemies) else "    }")
    src.append("};")
    src.append("const uint16_t np_enemy_count = %d;" % len(build.enemies))
    src.append("")

    # --- los prisioneros: se sueltan tocandolos y se pierden a tiros
    src.append("/* Los prisioneros, en el orden de 'prisioneros:'. */")
    for i, pri in enumerate(build.prisoners):
        src.append(_anim_arrays("np_prisoner%d" % i, pri))
    src.append("const NpPrisonerDef np_prisoners[] = {")
    if not build.prisoners:
        src.append("    { %s, 0, 0, 0 }" % _actor_vacio())
    for i, pri in enumerate(build.prisoners):
        pv = prisoner_values(pri)
        src.append("    {")
        src.append(_actor_def("np_prisoner%d" % i, actor_def_values(pri)) + ",")
        src.append("        %d, %d, %d" % (pv["score"], pv["speed"], pv["escape"]))
        src.append("    }," if i + 1 < len(build.prisoners) else "    }")
    src.append("};")
    src.append("const uint8_t np_prisoner_count = %d;" % len(build.prisoners))
    src.append("")

    src.append("/* Los generadores de bichos, en el orden de 'generadores:'. */")
    for i, gen in enumerate(build.generators):
        src.append(_anim_arrays("np_generator%d" % i, gen))
    indice_enemigos = {b.name: i for i, b in enumerate(build.enemies)}
    src.append("const NpGeneratorDef np_generators[] = {")
    if not build.generators:
        src.append("    { %s, 0, 0, 0, 0, 0 }" % _actor_vacio())
    for i, gen in enumerate(build.generators):
        gv = generator_values(gen, indice_enemigos)
        src.append("    {")
        src.append(_actor_def("np_generator%d" % i, actor_def_values(gen)) + ",")
        src.append("        %d, %d, %d, %d, %d"
                   % (gv["score"], gv["cooldown"], gv["health"], gv["enemy"],
                      gv["cap"]))
        src.append("    }," if i + 1 < len(build.generators) else "    }")
    src.append("};")
    src.append("const uint8_t np_generator_count = %d;" % len(build.generators))
    src.append("")

    # --- lo que tiran los enemigos que llevan `dispara:`
    src.append("/* Los disparos de los enemigos, en el orden de 'dispara:'. */")
    for i, disparo in enumerate(build.enemy_shots):
        src.append(_anim_arrays("np_eshot%d" % i, disparo))
    src.append("const NpEnemyShotDef np_enemy_shots[] = {")
    if not build.enemy_shots:
        src.append("    { %s, 0, 0, 0, 0 }" % _actor_vacio())
    for i, disparo in enumerate(build.enemy_shots):
        sv = enemy_shot_values(disparo)
        src.append("    {")
        src.append(_actor_def("np_eshot%d" % i, actor_def_values(disparo)) + ",")
        src.append("        %d, %d, %d, %d"
                   % (sv["speed"], sv["range"], sv["cooldown"], sv["damage"]))
        src.append("    }," if i + 1 < len(build.enemy_shots) else "    }")
    src.append("};")
    src.append("const uint8_t np_enemy_shot_count = %d;" % len(build.enemy_shots))
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
    # Como sale cada objeto en la bolsa del marcador. Cinco letras, como las
    # armas secundarias: es lo que cabe en la linea de "lo que llevas".
    src.append("const char np_item_names[][6] = {")
    if not build.items:
        src.append('    ""')
    for i, item in enumerate(build.items):
        src.append('    "%s"%s' % (item.actor.label,
                                   "," if i + 1 < len(build.items) else ""))
    src.append("};")
    # 1 = el juego lleva bolsa. Con esto a cero el boton de accion hace lo de
    # siempre y el marcador no ensena nada de esto.
    lleva_bolsa = any(item.actor.effect == "carry" for item in build.items)
    src.append("const uint8_t np_bolsa_activa = %d;" % (1 if lleva_bolsa else 0))
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

    # --- los cubos de la vista isometrica
    for i, cubo in enumerate(build.blocks):
        src.append("/* cubo %d: %s */" % (i, cubo.name))
        src.append(_anim_arrays("np_cubo%d" % i, cubo))
    src.append("const NpBlockDef np_bloques[] = {")
    if not build.blocks:
        src.append("    { %s }" % _actor_vacio())
    for i, cubo in enumerate(build.blocks):
        src.append("    {")
        src.append(_actor_def("np_cubo%d" % i, actor_def_values(cubo)))
        src.append("    }," if i + 1 < len(build.blocks) else "    }")
    src.append("};")
    src.append("const uint8_t np_bloque_count = %d;" % len(build.blocks))
    src.append("")

    src.extend(_carretera_tamanos_c(build))

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
    # Cual de las capas es la carretera. Va aqui y no en un sitio propio
    # porque la carretera **es** una capa: la dibuja el compilador y cada
    # maquina la convierte con lo que ya sabia hacer. -1 = este juego no
    # conduce.
    src.append("/* La capa que lleva la carretera en perspectiva, o -1. */")
    # Hay maquinas que se llevan las capas a otro sitio y vacian build.layers
    # -el X68000 las pone en su pantalla grafica-, y entonces la carretera no
    # esta en la lista. No es un error: es que esa maquina no la dibuja desde
    # ahi. Se dice -1 y el que la dibuje sabra de donde sacarla.
    _capa = (build.layers.index(build.asfalto)
             if build.asfalto is not None and build.asfalto in build.layers
             else -1)
    src.append("const int16_t np_carretera_capa = %d;" % _capa)
    # Y los huecos de paleta de las cuatro franjas de cada cosa, seguidos:
    # calzada, arcen y hierba. Rotarlos un paso por frame es lo que hace correr
    # las rayas hacia el jugador, y son cuatro escrituras de color por grupo.
    huecos = []
    for grupo in (build.asfalto.franjas if build.asfalto else []):
        huecos.extend(grupo)
    src.append("/* Los huecos de paleta de las franjas: calzada, arcen y")
    src.append("   hierba, cuatro de cada. Rotarlos hace correr las rayas. */")
    src.append("const uint8_t np_carretera_huecos[] = { %s };"
               % (", ".join(str(h) for h in huecos) or "0"))
    src.append("")

    # --- niveles
    for i, level in enumerate(build.levels):
        src.append("/* nivel %d: %s (%dx%d tiles) */" % (i, level.name, level.width, level.height))
        src.append("static const uint8_t np_level%d_cells[] = {" % i)
        src.append(_array(level.cells, per_line=32))
        src.append("};")
        if level.fondo:
            # El dibujo del suelo de las salas ya en numeros de tile: no pasa
            # por la leyenda porque son 280 tiles por sala y no caben en un
            # abecedario. -1 quiere decir "aqui no se pinta nada".
            paso = build.tile_gfx_paso
            base = build.tileset.first_tile
            remap = build.tileset_remap
            src.append("static const uint16_t np_level%d_fondo[] = {" % i)
            src.append(_array([vacio if n < 0 else base + remap[n] * paso
                               for n in level.fondo], per_line=20))
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
        fondo = "np_level%d_fondo" % i if level.fondo else "0"
        src.append(
            "    { %s, %d, %d, np_level%d_cells, %d, %d, %s, %s, %d, %d, %d,"
            " 0x%04x, %s, %d, %d, %d, %d },"
            % (_c_string(level.name), level.width, level.height, i,
               level.cells_w or level.width, level.cells_h or level.height,
               fondo, spawns,
               len(level.spawns), level.start[0], level.start[1], level.background,
               capas, len(level.layers), level.music, level.keys_needed,
               level.guion)
        )
    src.append("};")
    src.append("const uint16_t np_level_count = %d;" % len(build.levels))
    # Las dos canciones que no son de ningun nivel: la del titulo y la del
    # jefe. El numero es el indice + 1, como en los niveles.
    src.append("const uint8_t np_music_title = %d;" % build.music_title)
    src.append("const uint8_t np_music_boss = %d;" % build.music_boss)
    src.append("")

    # --- los guiones y la memoria del juego
    src.append("/* Los guiones: todos los pasos seguidos, y donde empieza cada")
    src.append("   uno. El ultimo hueco de np_guion_ini cierra la lista. */")
    src.append("const NpPaso np_pasos[] = {")
    if build.guion_pasos:
        for op, a_, cmp_, b_, c_ in build.guion_pasos:
            src.append("    { %d, %d, %d, %d, %d }," % (op, a_, cmp_, b_, c_))
    else:
        src.append("    { 0, 0, 0, 0, 0 },")
    src.append("};")
    src.append("const uint16_t np_guion_ini[] = {")
    src.append(_array(build.guion_ini or [0]))
    src.append("};")
    src.append("const uint16_t np_guion_count = %d;" % len(build.guion_orden))
    src.append("const char *const np_dialogo[] = {")
    if build.dialogo:
        for linea in build.dialogo:
            src.append("    %s," % _c_string(linea))
    else:
        src.append("    0,")
    src.append("};")
    src.append("const uint16_t np_dialogo_count = %d;" % len(build.dialogo))
    src.append("const uint16_t np_var_inicial[] = {")
    src.append(_array(list(project.variables.values()) or [0]))
    src.append("};")
    src.append("const uint16_t np_var_count = %d;" % len(project.variables))
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
