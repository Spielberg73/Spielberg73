/* np_game.h - estructuras de datos que genera `ngplat build`.
 *
 * Todo lo que hay aqui vive en ROM (const): el compilador de NeoPlat escribe
 * un gamedata.c con estas tablas a partir de game.yaml.
 */
#ifndef NP_GAME_H
#define NP_GAME_H

#include "np_types.h"

typedef struct {
    const uint8_t *frames;   /* indices de fotograma dentro de la hoja */
    uint8_t count;
    uint8_t speed;           /* frames de juego por fotograma */
    uint8_t loop;
} NpAnim;

typedef struct {
    uint16_t first_tile;     /* primer tile de la hoja en la ROM C */
    uint8_t palette;         /* paleta asignada */
    uint8_t cols, rows;      /* tamano del fotograma en tiles de 16x16 */
    int16_t box_x, box_y;    /* caja de colision dentro del fotograma */
    int16_t box_w, box_h;
    NpAnim anims[NP_ANIM_SLOTS];
} NpActorDef;

/* El ataque del jugador. `kind` a cero quiere decir que el juego no lleva
 * ataque y el boton no hace nada, que es como estaba el kit hasta ahora.
 *
 *   NP_ATTACK_SHOT   sale un proyectil que vuela de frente hasta chocar con
 *                    una pared, dar a un enemigo o agotar su alcance;
 *   NP_ATTACK_MELEE  no sale nada: durante `duration` frames hay una caja
 *                    delante del jugador que hace dano a lo que toque.
 *
 * `actor` es el dibujo del proyectil, y solo se usa con NP_ATTACK_SHOT. */
typedef struct {
    NpActorDef actor;
    np_fix speed;            /* velocidad del proyectil */
    uint16_t range;          /* pixeles que recorre, o alcance del golpe */
    uint16_t cooldown;       /* frames entre un ataque y el siguiente */
    uint16_t duration;       /* frames que dura el golpe */
    uint8_t kind;            /* NP_ATTACK_* */
    uint8_t damage;
} NpAttackDef;

typedef struct {
    NpActorDef actor;
    np_fix speed, accel, friction, air_accel;
    np_fix jump, jump_cut, gravity, max_fall, bounce;
    uint16_t invuln;
    uint8_t coyote, jump_buffer, double_jump, stomp, health;
    NpAttackDef attack;
} NpPlayerDef;

typedef struct {
    NpActorDef actor;
    np_fix speed, gravity, jump, range, amplitude;
    uint16_t period, interval, score;
    uint8_t behavior, health, damage, stompable, edge_turn;
    uint8_t boss;            /* 1 = matarlo termina el nivel */
} NpEnemyDef;

typedef struct {
    NpActorDef actor;
    uint16_t score;
    uint8_t effect, amount;
} NpItemDef;

typedef struct {
    uint16_t x, y;           /* posicion en pixeles (esquina superior izquierda) */
    uint8_t kind;            /* 0 = enemigo, 1 = objeto */
    uint8_t def;             /* indice en np_enemies / np_items */
} NpSpawn;

/* Capa de fondo con scroll propio (parallax). Es solo decorado: no participa
 * en la simulacion, asi que no afecta a la paridad con el preview. */
typedef struct {
    const uint16_t *tiles;   /* cols * rows numeros de tile de la ROM C */
    uint16_t speed_x;        /* 8.8: 256 = se mueve igual que el escenario */
    uint16_t speed_y;
    int16_t offset_y;        /* donde empieza la capa en la pantalla */
    uint8_t cols, rows;
    uint8_t palette;
    uint8_t repeat;          /* 1 = se repite horizontalmente */
} NpLayer;

/* Una plataforma movil: va y viene entre donde sale y `distance` pixeles mas
 * alla, y el que se sube encima va con ella. No hace dano ni se puede matar:
 * es escenario que se mueve. */
typedef struct {
    NpActorDef actor;
    np_fix speed;                    /* pixeles por frame */
    uint16_t distance;               /* recorrido, en pixeles */
    uint8_t axis;                    /* NP_PLAT_X o NP_PLAT_Y */
} NpPlatformDef;

typedef struct {
    const char *name;
    uint16_t width, height;          /* en tiles */
    const uint8_t *cells;            /* width * height indices de np_tile_* */
    const NpSpawn *spawns;
    uint16_t spawn_count;
    uint16_t start_x, start_y;       /* salida del jugador, en pixeles */
    uint16_t background;             /* color de fondo ya en formato Neo Geo */
    const uint8_t *layers;           /* indices en np_layers, de lejos a cerca */
    uint8_t layer_count;
    uint8_t music;                   /* 0 = sin musica, si no indice + 1 */
    uint8_t keys_needed;             /* llaves que pide la meta, 0 = ninguna */
} NpLevel;

/* Tablas que genera el compilador (definidas en gamedata.c). */
extern const NpPlayerDef np_player_def;
extern const NpEnemyDef np_enemies[];
extern const NpItemDef np_items[];
extern const NpPlatformDef np_platforms[];
extern const NpLevel np_levels[];
extern const NpLayer np_layers[];
extern const uint8_t np_tile_kind[];     /* tipo de cada tile del proyecto */
extern const uint16_t np_tile_gfx[];     /* tile grafico dentro de la ROM C */
extern const np_fix np_sin_table[64];    /* seno en 24.8, un ciclo completo */
/* Orden que hay que mandar al Z80 por cada evento de sonido (0 = sin sonido).
 * El indice es el numero de bit de NP_SFX_*. */
extern const uint8_t np_sfx_command[NP_SFX_SLOTS];

extern const uint16_t np_level_count;
extern const uint16_t np_layer_count;
extern const uint16_t np_enemy_count;
extern const uint16_t np_item_count;
extern const uint16_t np_platform_count;
extern const uint16_t np_tile_count;
extern const uint16_t np_tileset_first_tile;
extern const uint8_t np_tileset_palette;
extern const uint8_t np_start_lives;
extern const uint8_t np_player_count;     /* 1 o 2 jugadores a la vez */
extern const uint16_t np_time_limit;      /* en segundos, 0 = sin limite */
extern const uint8_t np_camara_pantallas; /* 1 = pantalla a pantalla, 0 = scroll */
extern const char np_game_title[];
extern const char np_game_author[];

#endif /* NP_GAME_H */
