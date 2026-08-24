/* np_world.c - simulacion del juego: fisica, colisiones, enemigos y estados.
 *
 * Este archivo no sabe nada de la Neo Geo: solo enteros. Se compila igual para
 * el 68000 de la consola, para las pruebas de escritorio y (traducido a JS en
 * preview/np_core.js) para el preview del navegador. Cualquier cambio aqui
 * debe hacerse tambien alli: tests/test_paridad.py compara las dos versiones
 * frame a frame.
 */

#include "np_world.h"

#define NP_SUBSTEP     NP_I2F(8)     /* medio tile: evita atravesar paredes */
#define NP_ENTITY_FALL NP_I2F(8)
#define NP_DYING_TIME  60
#define NP_LEVEL_END_TIME 90
#define NP_GAME_OVER_TIME 240
#define NP_CULL_MARGIN 64            /* pixeles fuera de pantalla que siguen vivos */

/* -------------------------------------------------------------- utilidades */

static np_fix np_approach(np_fix value, np_fix target, np_fix delta)
{
    if (value < target) {
        value += delta;
        if (value > target) value = target;
    } else if (value > target) {
        value -= delta;
        if (value < target) value = target;
    }
    return value;
}

uint8_t np_tile_kind_at(const NpLevel *level, int32_t tx, int32_t ty)
{
    if (tx < 0 || tx >= (int32_t)level->width) return NP_TILE_SOLID;  /* paredes */
    if (ty < 0) return NP_TILE_EMPTY;                                 /* cielo */
    if (ty >= (int32_t)level->height) return NP_TILE_EMPTY;           /* abismo */
    return np_tile_kind[level->cells[ty * level->width + tx]];
}

uint16_t np_tile_gfx_at(const NpLevel *level, int32_t tx, int32_t ty)
{
    if (tx < 0 || tx >= (int32_t)level->width) return 0;
    if (ty < 0 || ty >= (int32_t)level->height) return 0;
    return np_tile_gfx[level->cells[ty * level->width + tx]];
}

static int np_blocks(uint8_t kind) { return kind == NP_TILE_SOLID; }

static int np_boxes_overlap(np_fix ax, np_fix ay, int aw, int ah,
                            np_fix bx, np_fix by, int bw, int bh)
{
    if (ax + NP_I2F(aw) <= bx) return 0;
    if (bx + NP_I2F(bw) <= ax) return 0;
    if (ay + NP_I2F(ah) <= by) return 0;
    if (by + NP_I2F(bh) <= ay) return 0;
    return 1;
}

/* ------------------------------------------------------- movimiento y tiles */

static np_fix np_move_x(const NpLevel *lv, np_fix x, np_fix y,
                        int bw, int bh, np_fix dx, int *hit)
{
    *hit = 0;
    while (dx != 0) {
        np_fix step = NP_CLAMP(dx, -NP_SUBSTEP, NP_SUBSTEP);
        np_fix nx = x + step;
        int32_t ty0 = NP_F2I(y) >> NP_TILE_SHIFT;
        int32_t ty1 = NP_F2I(y + NP_I2F(bh) - 1) >> NP_TILE_SHIFT;
        int32_t ty;
        dx -= step;
        if (step > 0) {
            int32_t tx = NP_F2I(nx + NP_I2F(bw) - 1) >> NP_TILE_SHIFT;
            for (ty = ty0; ty <= ty1; ty++) {
                if (np_blocks(np_tile_kind_at(lv, tx, ty))) {
                    nx = NP_I2F(tx * NP_TILE - bw);
                    *hit = 1;
                    dx = 0;
                    break;
                }
            }
        } else {
            int32_t tx = NP_F2I(nx) >> NP_TILE_SHIFT;
            for (ty = ty0; ty <= ty1; ty++) {
                if (np_blocks(np_tile_kind_at(lv, tx, ty))) {
                    nx = NP_I2F((tx + 1) * NP_TILE);
                    *hit = 1;
                    dx = 0;
                    break;
                }
            }
        }
        x = nx;
    }
    return x;
}

static np_fix np_move_y(const NpLevel *lv, np_fix x, np_fix y,
                        int bw, int bh, np_fix dy,
                        int drop_through, int *hit_down, int *hit_up)
{
    *hit_down = 0;
    *hit_up = 0;
    while (dy != 0) {
        np_fix step = NP_CLAMP(dy, -NP_SUBSTEP, NP_SUBSTEP);
        np_fix ny = y + step;
        int32_t tx0 = NP_F2I(x) >> NP_TILE_SHIFT;
        int32_t tx1 = NP_F2I(x + NP_I2F(bw) - 1) >> NP_TILE_SHIFT;
        int32_t tx;
        dy -= step;
        if (step > 0) {
            int32_t bottom = NP_F2I(ny + NP_I2F(bh) - 1);
            int32_t ty = bottom >> NP_TILE_SHIFT;
            int32_t old_bottom = NP_F2I(y + NP_I2F(bh) - 1);
            for (tx = tx0; tx <= tx1; tx++) {
                uint8_t kind = np_tile_kind_at(lv, tx, ty);
                int stops = np_blocks(kind);
                if (!stops && kind == NP_TILE_PLATFORM && !drop_through) {
                    /* las plataformas solo frenan si venias por encima */
                    stops = (old_bottom < ty * NP_TILE);
                }
                if (stops) {
                    ny = NP_I2F(ty * NP_TILE - bh);
                    *hit_down = 1;
                    dy = 0;
                    break;
                }
            }
        } else {
            int32_t ty = NP_F2I(ny) >> NP_TILE_SHIFT;
            for (tx = tx0; tx <= tx1; tx++) {
                if (np_blocks(np_tile_kind_at(lv, tx, ty))) {
                    ny = NP_I2F((ty + 1) * NP_TILE);
                    *hit_up = 1;
                    dy = 0;
                    break;
                }
            }
        }
        y = ny;
    }
    return y;
}

/* Devuelve 1 si la caja toca algun tile del tipo pedido. */
static int np_box_touches(const NpLevel *lv, np_fix x, np_fix y, int bw, int bh,
                          uint8_t kind)
{
    int32_t tx0 = NP_F2I(x) >> NP_TILE_SHIFT;
    int32_t tx1 = NP_F2I(x + NP_I2F(bw) - 1) >> NP_TILE_SHIFT;
    int32_t ty0 = NP_F2I(y) >> NP_TILE_SHIFT;
    int32_t ty1 = NP_F2I(y + NP_I2F(bh) - 1) >> NP_TILE_SHIFT;
    int32_t tx, ty;
    for (ty = ty0; ty <= ty1; ty++)
        for (tx = tx0; tx <= tx1; tx++)
            if (np_tile_kind_at(lv, tx, ty) == kind) return 1;
    return 0;
}

/* --------------------------------------------------------- actores y animos */

const NpActorDef *np_entity_def(const NpEntity *e)
{
    if (e->kind == 0) return &np_enemies[e->def].actor;
    return &np_items[e->def].actor;
}

uint8_t np_actor_frame(const NpActorDef *def, uint8_t anim, uint8_t anim_frame)
{
    const NpAnim *a = &def->anims[anim];
    if (a->count == 0) a = &def->anims[NP_ANIM_IDLE];
    if (a->count == 0) return 0;
    if (anim_frame >= a->count) anim_frame = (uint8_t)(a->count - 1);
    return a->frames[anim_frame];
}

static void np_anim_set(uint8_t *anim, uint8_t *frame, uint16_t *timer, uint8_t next)
{
    if (*anim != next) {
        *anim = next;
        *frame = 0;
        *timer = 0;
    }
}

static void np_anim_tick(const NpActorDef *def, uint8_t anim,
                         uint8_t *frame, uint16_t *timer)
{
    const NpAnim *a = &def->anims[anim];
    if (a->count == 0) a = &def->anims[NP_ANIM_IDLE];
    if (a->count <= 1) { *frame = 0; *timer = 0; return; }
    (*timer)++;
    if (*timer >= a->speed) {
        *timer = 0;
        if (*frame + 1 < a->count) {
            (*frame)++;
        } else if (a->loop) {
            *frame = 0;
        }
    }
}

/* ------------------------------------------------------------- ciclo de vida */

void np_world_init(NpWorld *w)
{
    uint16_t i;
    for (i = 0; i < sizeof(NpWorld); i++) ((uint8_t *)w)[i] = 0;
    w->state = NP_STATE_TITLE;
    w->lives = np_start_lives;
    w->level_index = 0;
    w->level = &np_levels[0];
}

static void np_spawn_entities(NpWorld *w)
{
    const NpLevel *lv = w->level;
    uint16_t i;
    w->entity_count = 0;
    for (i = 0; i < lv->spawn_count && w->entity_count < NP_MAX_ENTITIES; i++) {
        const NpSpawn *s = &lv->spawns[i];
        NpEntity *e = &w->entities[w->entity_count++];
        const NpActorDef *def;
        e->active = 1;
        e->kind = s->kind;
        e->def = s->def;
        e->x = NP_I2F(s->x);
        e->y = NP_I2F(s->y);
        e->home_y = e->y;
        e->vx = 0;
        e->vy = 0;
        e->facing = 0;               /* 0 = izquierda, 1 = derecha */
        e->anim = NP_ANIM_IDLE;
        e->anim_frame = 0;
        e->anim_timer = 0;
        e->hurt = 0;
        e->timer = 0;
        def = np_entity_def(e);
        (void)def;
        if (e->kind == 0) {
            const NpEnemyDef *ed = &np_enemies[e->def];
            e->health = ed->health;
            e->timer = ed->interval;
            e->vx = ed->speed;       /* empieza andando a la derecha */
            e->facing = 1;
        } else {
            e->health = 1;
        }
    }
}

void np_world_load_level(NpWorld *w, uint16_t index)
{
    const NpPlayerDef *d = &np_player_def;
    NpPlayer *p = &w->player;
    if (index >= np_level_count) index = 0;
    w->level_index = index;
    w->level = &np_levels[index];
    p->x = NP_I2F(w->level->start_x);
    p->y = NP_I2F(w->level->start_y);
    p->vx = 0;
    p->vy = 0;
    p->on_ground = 0;
    p->facing = 1;
    p->health = d->health;
    p->invuln = 0;
    p->coyote = 0;
    p->buffer = 0;
    p->jumps_left = d->double_jump ? 1 : 0;
    p->anim = NP_ANIM_IDLE;
    p->anim_frame = 0;
    p->anim_timer = 0;
    w->keys = 0;
    w->time_left = (uint16_t)(np_time_limit * 60);
    w->state = NP_STATE_PLAY;
    w->state_timer = 0;
    np_spawn_entities(w);
}

static void np_player_die(NpWorld *w)
{
    w->state = NP_STATE_DYING;
    w->state_timer = NP_DYING_TIME;
    w->player.vy = -np_player_def.jump;
    w->player.vx = 0;
    w->player.anim = NP_ANIM_HURT;
    w->player.anim_frame = 0;
}

static void np_player_hurt(NpWorld *w, uint8_t damage)
{
    NpPlayer *p = &w->player;
    if (p->invuln || w->state != NP_STATE_PLAY) return;
    if (damage >= p->health) {
        p->health = 0;
        np_player_die(w);
        return;
    }
    p->health = (uint8_t)(p->health - damage);
    p->invuln = np_player_def.invuln;
    p->vy = -np_player_def.bounce / 2;
    p->vx = p->facing ? -np_player_def.speed : np_player_def.speed;
}

/* ------------------------------------------------------------- el jugador */

static void np_player_update(NpWorld *w, uint16_t input)
{
    const NpPlayerDef *d = &np_player_def;
    const NpActorDef *a = &d->actor;
    NpPlayer *p = &w->player;
    int dir = 0;
    int hit_x = 0, hit_down = 0, hit_up = 0;
    int pressed_jump;

    if (input & NP_IN_RIGHT) dir += 1;
    if (input & NP_IN_LEFT) dir -= 1;

    if (dir > 0) { p->vx = np_approach(p->vx, d->speed, p->on_ground ? d->accel : d->air_accel); p->facing = 1; }
    else if (dir < 0) { p->vx = np_approach(p->vx, -d->speed, p->on_ground ? d->accel : d->air_accel); p->facing = 0; }
    else if (p->on_ground) p->vx = np_approach(p->vx, 0, d->friction);

    pressed_jump = (input & NP_IN_JUMP) && !(w->prev_input & NP_IN_JUMP);
    if (pressed_jump) p->buffer = (uint8_t)(d->jump_buffer + 1);
    if (p->buffer) p->buffer--;

    if (p->on_ground) {
        p->coyote = d->coyote;
        p->jumps_left = d->double_jump ? 1 : 0;
    } else if (p->coyote) {
        p->coyote--;
    }

    if (p->buffer && (p->coyote || p->jumps_left)) {
        if (!p->coyote) p->jumps_left--;
        p->vy = -d->jump;
        p->buffer = 0;
        p->coyote = 0;
        p->on_ground = 0;
    }
    if (!(input & NP_IN_JUMP) && p->vy < -d->jump_cut) p->vy = -d->jump_cut;

    p->vy += d->gravity;
    if (p->vy > d->max_fall) p->vy = d->max_fall;

    p->x = np_move_x(w->level, p->x, p->y, a->box_w, a->box_h, p->vx, &hit_x);
    if (hit_x) p->vx = 0;
    p->y = np_move_y(w->level, p->x, p->y, a->box_w, a->box_h, p->vy,
                     (input & NP_IN_DOWN) ? 1 : 0, &hit_down, &hit_up);
    p->on_ground = (uint8_t)hit_down;
    if (hit_down && p->vy > 0) p->vy = 0;
    if (hit_up && p->vy < 0) p->vy = 0;

    if (p->invuln) p->invuln--;

    if (!p->on_ground)
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer,
                    p->vy < 0 ? NP_ANIM_JUMP : NP_ANIM_FALL);
    else if (p->vx > NP_I2F(1) / 8 || p->vx < -(NP_I2F(1) / 8))
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_RUN);
    else
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_IDLE);
    np_anim_tick(a, p->anim, &p->anim_frame, &p->anim_timer);
}

/* --------------------------------------------------------------- enemigos */

static void np_enemy_update(NpWorld *w, NpEntity *e)
{
    const NpEnemyDef *d = &np_enemies[e->def];
    const NpActorDef *a = &d->actor;
    const NpPlayer *p = &w->player;
    int hit_x = 0, hit_down = 0, hit_up = 0;

    switch (d->behavior) {
    case NP_AI_PATROL:
        e->vx = e->facing ? d->speed : -d->speed;
        break;
    case NP_AI_FLYER: {
        np_fix phase;
        e->vx = e->facing ? d->speed : -d->speed;
        e->timer = (uint16_t)((e->timer + 1) % (d->period ? d->period : 1));
        phase = np_sin_table[(((int32_t)e->timer * 64) / (d->period ? d->period : 1)) & 63];
        e->y = e->home_y + ((d->amplitude * phase) >> NP_FIX_SHIFT);
        break;
    }
    case NP_AI_CHASER: {
        np_fix dx = p->x - e->x;
        if (NP_ABS(dx) <= d->range) {
            e->vx = dx > 0 ? d->speed : -d->speed;
            e->facing = (uint8_t)(dx > 0);
        } else {
            e->vx = np_approach(e->vx, 0, d->speed);
        }
        break;
    }
    case NP_AI_JUMPER:
        e->vx = e->facing ? d->speed : -d->speed;
        if (e->timer) {
            e->timer--;
        } else if (e->vy == 0) {
            e->vy = -d->jump;
            e->timer = d->interval;
        }
        break;
    default:                 /* NP_AI_STATIC */
        e->vx = 0;
        break;
    }

    if (d->behavior != NP_AI_FLYER) {
        e->vy += d->gravity;
        if (e->vy > NP_ENTITY_FALL) e->vy = NP_ENTITY_FALL;
    }

    e->x = np_move_x(w->level, e->x, e->y, a->box_w, a->box_h, e->vx, &hit_x);
    if (hit_x) {
        e->facing = (uint8_t)!e->facing;
        e->vx = 0;
    }
    if (d->behavior != NP_AI_FLYER) {
        e->y = np_move_y(w->level, e->x, e->y, a->box_w, a->box_h, e->vy, 0,
                         &hit_down, &hit_up);
        if (hit_down && e->vy > 0) e->vy = 0;
        if (hit_up && e->vy < 0) e->vy = 0;

        if (hit_down && d->edge_turn && d->behavior == NP_AI_PATROL) {
            int32_t edge = e->facing ? NP_F2I(e->x + NP_I2F(a->box_w) - 1) + 1
                                     : NP_F2I(e->x) - 1;
            int32_t below = NP_F2I(e->y + NP_I2F(a->box_h)) ;
            uint8_t kind = np_tile_kind_at(w->level, edge >> NP_TILE_SHIFT,
                                           below >> NP_TILE_SHIFT);
            if (kind != NP_TILE_SOLID && kind != NP_TILE_PLATFORM)
                e->facing = (uint8_t)!e->facing;
        }
    }

    /* Nota: `facing` manda sobre `vx` (es lo que decide la direccion del
     * proximo frame). No se recalcula aqui a partir de vx, porque eso
     * deshacia el giro en los bordes y en las paredes. */
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer,
                e->vx ? NP_ANIM_RUN : NP_ANIM_IDLE);
    np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);

    /* caerse del mapa mata al enemigo */
    if (NP_F2I(e->y) > (int32_t)(w->level->height + 2) * NP_TILE) e->active = 0;
}

static void np_item_update(NpWorld *w, NpEntity *e)
{
    const NpItemDef *d = &np_items[e->def];
    (void)w;
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_IDLE);
    np_anim_tick(&d->actor, e->anim, &e->anim_frame, &e->anim_timer);
}

static void np_collect(NpWorld *w, NpEntity *e)
{
    const NpItemDef *d = &np_items[e->def];
    w->score += d->score;
    switch (d->effect) {
    case NP_ITEM_LIFE:
        if (w->lives < 99) w->lives = (uint8_t)(w->lives + d->amount);
        break;
    case NP_ITEM_HEALTH:
        w->player.health = (uint8_t)NP_MIN(w->player.health + d->amount,
                                           np_player_def.health);
        break;
    case NP_ITEM_KEY:
        if (w->keys < 255) w->keys = (uint8_t)(w->keys + d->amount);
        break;
    default:
        break;
    }
    e->active = 0;
}

static void np_touch_entities(NpWorld *w)
{
    const NpActorDef *pa = &np_player_def.actor;
    NpPlayer *p = &w->player;
    uint8_t i;
    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        const NpActorDef *ea;
        if (!e->active) continue;
        ea = np_entity_def(e);
        if (!np_boxes_overlap(p->x, p->y, pa->box_w, pa->box_h,
                              e->x, e->y, ea->box_w, ea->box_h))
            continue;
        if (e->kind == 1) {
            np_collect(w, e);
            continue;
        }
        {
            const NpEnemyDef *d = &np_enemies[e->def];
            int from_above = p->vy > 0 &&
                (p->y + NP_I2F(pa->box_h) - p->vy) <= e->y + NP_I2F(ea->box_h / 3);
            if (np_player_def.stomp && d->stompable && from_above) {
                if (e->health > 1) {
                    e->health--;
                    e->hurt = 20;
                } else {
                    e->active = 0;
                    w->score += d->score;
                }
                p->vy = -np_player_def.bounce;
                p->on_ground = 0;
            } else {
                np_player_hurt(w, d->damage);
            }
        }
    }
}

/* ---------------------------------------------------------------- camara */

static void np_camera_update(NpWorld *w)
{
    const NpActorDef *a = &np_player_def.actor;
    int32_t max_x = (int32_t)w->level->width * NP_TILE - NP_SCREEN_W;
    int32_t max_y = (int32_t)w->level->height * NP_TILE - NP_SCREEN_H;
    int32_t target_x = NP_F2I(w->player.x) + a->box_w / 2 - NP_SCREEN_W / 2;
    int32_t target_y = NP_F2I(w->player.y) + a->box_h / 2 - NP_SCREEN_H / 2;
    if (max_x < 0) max_x = 0;
    if (max_y < 0) max_y = 0;
    w->cam_x = NP_CLAMP(target_x, 0, max_x);
    w->cam_y = NP_CLAMP(target_y, 0, max_y);
}

int np_player_visible(const NpWorld *w)
{
    if (w->state == NP_STATE_TITLE || w->state == NP_STATE_GAME_OVER) return 0;
    if (w->player.invuln && (w->frame & 2)) return 0;   /* parpadeo */
    return 1;
}

/* ----------------------------------------------------------------- estados */

static void np_play_step(NpWorld *w, uint16_t input)
{
    const NpActorDef *pa = &np_player_def.actor;
    NpPlayer *p = &w->player;
    uint8_t i;

    np_player_update(w, input);

    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        int32_t dx;
        if (!e->active) continue;
        dx = NP_F2I(e->x) - (int32_t)w->cam_x;
        if (dx < -NP_CULL_MARGIN || dx > NP_SCREEN_W + NP_CULL_MARGIN) {
            if (e->kind == 0) continue;      /* enemigos lejanos: en pausa */
        }
        if (e->hurt) e->hurt--;
        if (e->kind == 0) np_enemy_update(w, e);
        else np_item_update(w, e);
    }

    np_touch_entities(w);

    if (w->state != NP_STATE_PLAY) return;

    if (np_box_touches(w->level, p->x, p->y, pa->box_w, pa->box_h, NP_TILE_HAZARD)) {
        np_player_hurt(w, 99);
        return;
    }
    if (np_box_touches(w->level, p->x, p->y, pa->box_w, pa->box_h, NP_TILE_GOAL)) {
        w->state = NP_STATE_LEVEL_END;
        w->state_timer = NP_LEVEL_END_TIME;
        w->score += 100 + (w->time_left / 60) * 10;
        return;
    }
    if (NP_F2I(p->y) > (int32_t)(w->level->height + 2) * NP_TILE) {
        np_player_hurt(w, 99);
        return;
    }
    if (np_time_limit) {
        if (w->time_left) w->time_left--;
        else np_player_hurt(w, 99);
    }
}

void np_world_step(NpWorld *w, uint16_t input)
{
    int start_pressed = (input & NP_IN_START) && !(w->prev_input & NP_IN_START);
    w->frame++;

    switch (w->state) {
    case NP_STATE_TITLE:
        if (start_pressed) {
            w->score = 0;
            w->lives = np_start_lives;
            np_world_load_level(w, 0);
        }
        break;

    case NP_STATE_PLAY:
        np_play_step(w, input);
        break;

    case NP_STATE_DYING:
        w->player.vy += np_player_def.gravity;
        if (w->player.vy > np_player_def.max_fall) w->player.vy = np_player_def.max_fall;
        w->player.y += w->player.vy;
        if (w->state_timer) {
            w->state_timer--;
        } else if (w->lives > 1) {
            w->lives--;
            np_world_load_level(w, w->level_index);
        } else {
            w->lives = 0;
            w->state = NP_STATE_GAME_OVER;
            w->state_timer = NP_GAME_OVER_TIME;
        }
        break;

    case NP_STATE_LEVEL_END:
        if (w->state_timer) {
            w->state_timer--;
        } else if (w->level_index + 1 < np_level_count) {
            np_world_load_level(w, (uint16_t)(w->level_index + 1));
        } else {
            w->state = NP_STATE_FINISHED;
            w->state_timer = NP_GAME_OVER_TIME;
        }
        break;

    case NP_STATE_GAME_OVER:
    case NP_STATE_FINISHED:
    default:
        if (w->state_timer) w->state_timer--;
        if (start_pressed || w->state_timer == 0) {
            w->state = NP_STATE_TITLE;
            w->state_timer = 0;
            w->level_index = 0;
            w->level = &np_levels[0];
        }
        break;
    }

    np_camera_update(w);
    w->prev_input = input;
}
