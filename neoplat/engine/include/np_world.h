/* np_world.h - estado y simulacion del juego (independiente del hardware).
 *
 * El mismo np_world_step() corre en la Neo Geo y en las pruebas de escritorio.
 * No usa memoria dinamica ni coma flotante.
 */
#ifndef NP_WORLD_H
#define NP_WORLD_H

#include "np_game.h"

#ifndef NP_MAX_ENTITIES
#define NP_MAX_ENTITIES 64
#endif

typedef struct {
    np_fix x, y, vx, vy;
    uint16_t anim_timer;
    uint16_t invuln;
    uint8_t anim, anim_frame;
    uint8_t on_ground, facing, jumps_left, health;
    uint8_t coyote, buffer;
} NpPlayer;

typedef struct {
    np_fix x, y, vx, vy;
    np_fix home_y;           /* altura de origen (voladores) */
    uint16_t timer;          /* cuenta atras de salto / fase del seno */
    uint16_t anim_timer;
    uint8_t active, kind, def;
    uint8_t anim, anim_frame, facing, health, hurt;
} NpEntity;

typedef struct {
    const NpLevel *level;
    NpPlayer player;
    NpEntity entities[NP_MAX_ENTITIES];
    int32_t cam_x, cam_y;
    uint32_t score;
    uint32_t frame;
    uint16_t level_index;
    uint16_t state, state_timer;
    uint16_t time_left;      /* en frames */
    uint16_t prev_input;
    uint16_t sfx;            /* eventos de sonido de este frame (NP_SFX_*) */
    uint8_t lives, keys, entity_count;
} NpWorld;

void np_world_init(NpWorld *w);
void np_world_load_level(NpWorld *w, uint16_t index);
void np_world_step(NpWorld *w, uint16_t input);

/* Consultas que usa la capa grafica. */
uint8_t np_tile_kind_at(const NpLevel *level, int32_t tx, int32_t ty);
uint16_t np_tile_gfx_at(const NpLevel *level, int32_t tx, int32_t ty);
void np_tile_gfx_column(const NpLevel *level, int32_t tx, int32_t ty,
                        uint16_t count, uint16_t *out);
const NpActorDef *np_entity_def(const NpEntity *e);
uint8_t np_actor_frame(const NpActorDef *def, uint8_t anim, uint8_t anim_frame);
int np_player_visible(const NpWorld *w);

#endif /* NP_WORLD_H */
