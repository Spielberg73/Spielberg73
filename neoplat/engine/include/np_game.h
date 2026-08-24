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

typedef struct {
    NpActorDef actor;
    np_fix speed, accel, friction, air_accel;
    np_fix jump, jump_cut, gravity, max_fall, bounce;
    uint16_t invuln;
    uint8_t coyote, jump_buffer, double_jump, stomp, health;
} NpPlayerDef;

typedef struct {
    NpActorDef actor;
    np_fix speed, gravity, jump, range, amplitude;
    uint16_t period, interval, score;
    uint8_t behavior, health, damage, stompable, edge_turn;
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

typedef struct {
    const char *name;
    uint16_t width, height;          /* en tiles */
    const uint8_t *cells;            /* width * height indices de np_tile_* */
    const NpSpawn *spawns;
    uint16_t spawn_count;
    uint16_t start_x, start_y;       /* salida del jugador, en pixeles */
    uint16_t background;             /* color de fondo ya en formato Neo Geo */
} NpLevel;

/* Tablas que genera el compilador (definidas en gamedata.c). */
extern const NpPlayerDef np_player_def;
extern const NpEnemyDef np_enemies[];
extern const NpItemDef np_items[];
extern const NpLevel np_levels[];
extern const uint8_t np_tile_kind[];     /* tipo de cada tile del proyecto */
extern const uint16_t np_tile_gfx[];     /* tile grafico dentro de la ROM C */
extern const np_fix np_sin_table[64];    /* seno en 24.8, un ciclo completo */

extern const uint16_t np_level_count;
extern const uint16_t np_enemy_count;
extern const uint16_t np_item_count;
extern const uint16_t np_tile_count;
extern const uint16_t np_tileset_first_tile;
extern const uint8_t np_tileset_palette;
extern const uint8_t np_start_lives;
extern const uint16_t np_time_limit;      /* en segundos, 0 = sin limite */
extern const char np_game_title[];
extern const char np_game_author[];

#endif /* NP_GAME_H */
