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

/* Los pinchos matan con una caja algo mas pequena que la del jugador: rozar el
 * borde del tile no deberia matar, igual que en los juegos clasicos. */
#define NP_HAZARD_INSET_X 2
#define NP_HAZARD_INSET_Y 4

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

/* Los graficos de una columna entera de tiles, de arriba a abajo.
 *
 * Es lo que necesita el fondo de las tres maquinas. Pedirlos uno a uno con
 * np_tile_gfx_at() sale caro en un 68000: cada llamada multiplica dos enteros
 * de 32 bits y el 68000 no tiene esa instruccion, asi que el compilador se va
 * a una rutina en software. Aqui se multiplica una vez y el resto de la
 * columna se baja sumando el ancho del mapa. Fuera del nivel devuelve 0, igual
 * que np_tile_gfx_at(). */
void np_tile_gfx_column(const NpLevel *level, int32_t tx, int32_t ty,
                        uint16_t count, uint16_t *out)
{
    const uint8_t *cell;
    uint16_t i = 0;

    if (tx < 0 || tx >= (int32_t)level->width) {
        for (; i < count; i++) out[i] = 0;
        return;
    }
    for (; i < count && ty < 0; i++, ty++)
        out[i] = 0;
    if (i < count && ty < (int32_t)level->height) {
        cell = level->cells + (int32_t)ty * level->width + tx;
        for (; i < count && ty < (int32_t)level->height; i++, ty++) {
            out[i] = np_tile_gfx[*cell];
            cell += level->width;
        }
    }
    for (; i < count; i++)
        out[i] = 0;
}

static int np_blocks(uint8_t kind) { return kind == NP_TILE_SOLID; }

/* La escalera que hay en ese punto del mundo, o 0 si no hay ninguna.
 *
 * Las escaleras no frenan a nadie: se pasa por delante andando, igual que por
 * un decorado. Solo cuentan cuando el jugador decide subirse, y por eso no
 * aparecen en np_blocks ni en np_move_*. */
static uint8_t np_stair_at(const NpLevel *lv, np_fix x, np_fix y)
{
    uint8_t kind = np_tile_kind_at(lv, NP_F2I(x) >> NP_TILE_SHIFT,
                                   NP_F2I(y) >> NP_TILE_SHIFT);
    return (kind == NP_TILE_STAIR_R || kind == NP_TILE_STAIR_L) ? kind : 0;
}

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
    if (e->kind == NP_KIND_ENEMY) return &np_enemies[e->def].actor;
    if (e->kind == NP_KIND_SHOT) return &np_player_def.attack.actor;
    if (e->kind == NP_KIND_PLATFORM) return &np_platforms[e->def].actor;
    if (e->kind == NP_KIND_BREAKABLE) return &np_breakables[e->def].actor;
    if (e->kind == NP_KIND_SUBSHOT) return &np_player_def.sub.actor;
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

static void np_camera_update(NpWorld *w);

/* Donde sale cada jugador. A dos, el segundo aparece un poco a la derecha para
   que no empiecen uno dentro del otro. */
#define NP_HUECO_2P 20

/* Donde aparece un jugador: en la salida del nivel, o en el ultimo punto de
   control que se haya tocado. Se cae de pie **encima** de la casilla marcada y
   centrado en su columna, para que la marca se pueda poner donde se quiera sin
   depender de por donde se paso al tocarla. */
static void np_player_place(NpWorld *w, uint8_t quien)
{
    const NpActorDef *a = &np_player_def.actor;
    NpPlayer *p = &w->players[quien];
    int32_t x, y;
    if (w->check_on) {
        x = (int32_t)w->check_x * NP_TILE + (NP_TILE - (int32_t)a->box_w) / 2;
        y = (int32_t)w->check_y * NP_TILE + NP_TILE - (int32_t)a->box_h;
    } else {
        x = w->level->start_x;
        y = w->level->start_y;
    }
    p->x = NP_I2F(x + (quien ? NP_HUECO_2P : 0));
    p->y = NP_I2F(y);
}

void np_world_init(NpWorld *w)
{
    uint16_t i;
    for (i = 0; i < sizeof(NpWorld); i++) ((uint8_t *)w)[i] = 0;
    w->state = NP_STATE_TITLE;
    w->level_index = 0;
    w->level = &np_levels[0];
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        w->players[i].playing = (uint8_t)(i < np_player_count);
        w->players[i].lives = np_start_lives;
        np_player_place(w, (uint8_t)i);
    }
    /* Colocamos al jugador en su salida ya en la pantalla de titulo: asi el
     * fondo del titulo es el principio del nivel y no una esquina vacia. */
    np_camera_update(w);
}

static void np_spawn_entities(NpWorld *w)
{
    const NpLevel *lv = w->level;
    uint16_t i;
    /* La lista se limpia entera, no solo hasta entity_count: los proyectiles
       buscan hueco recorriendola desde el principio, y una entidad viva de un
       nivel anterior mas alla del ultimo spawn les daria un sitio ocupado. El
       preview hace lo mismo, y de eso vive la paridad. */
    for (i = 0; i < NP_MAX_ENTITIES; i++) w->entities[i].active = 0;
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
        e->home_x = e->x;
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
        e->vida = 0;
        if (e->kind == NP_KIND_ENEMY) {
            const NpEnemyDef *ed = &np_enemies[e->def];
            e->health = ed->health;
            e->timer = ed->interval;
            e->vx = ed->speed;       /* empieza andando a la derecha */
            e->facing = 1;
        } else if (e->kind == NP_KIND_PLATFORM) {
            e->health = 1;
            e->facing = 1;           /* sale hacia la derecha o hacia abajo */
        } else if (e->kind == NP_KIND_BREAKABLE) {
            e->health = np_breakables[e->def].health;
        } else {
            e->health = 1;
        }
    }
}

/* Deja a un jugador como recien salido: en la salida del nivel y entero. Se usa
   al empezar el nivel y cuando reaparece despues de morir. */
static void np_player_reset(NpWorld *w, uint8_t quien)
{
    const NpPlayerDef *d = &np_player_def;
    NpPlayer *p = &w->players[quien];
    np_player_place(w, quien);
    p->vx = 0;
    p->vy = 0;
    p->on_ground = 0;
    p->facing = 1;
    p->health = d->health;
    p->invuln = 0;
    p->coyote = 0;
    p->buffer = 0;
    p->dying = 0;
    p->jumps_left = d->double_jump ? 1 : 0;
    p->attack_timer = 0;
    p->attack_cd = 0;
    p->stun = 0;
    p->power = 0;               /* el arma vuelve a la de serie */
    p->riding = 0;
    p->stairs = 0;
    p->stair_dir = 1;
    p->anim = NP_ANIM_IDLE;
    p->anim_frame = 0;
    p->anim_timer = 0;
}

void np_world_load_level(NpWorld *w, uint16_t index)
{
    uint8_t i;
    if (index >= np_level_count) index = 0;
    w->level_index = index;
    w->level = &np_levels[index];
    /* antes de colocar a nadie: cargar un nivel es empezarlo de cero */
    w->check_on = 0;
    w->check_x = 0;
    w->check_y = 0;
    for (i = 0; i < NP_MAX_PLAYERS; i++) np_player_reset(w, i);
    w->keys = 0;
    w->hearts = 0;
    w->boss_health = 0;
    w->boss_max = 0;
    w->time_left = (uint16_t)(np_time_limit * 60);
    w->state = NP_STATE_PLAY;
    w->state_timer = 0;
    np_spawn_entities(w);
}

/* Cuantos jugadores siguen en juego y no se estan muriendo. */
static uint8_t np_players_up(const NpWorld *w)
{
    uint8_t i, n = 0;
    for (i = 0; i < NP_MAX_PLAYERS; i++)
        if (w->players[i].playing && !w->players[i].dying) n++;
    return n;
}

/* Cuando muere un jugador y queda otro en pie, reaparece el solo y el nivel
 * sigue: es lo que hace un juego a dos. Cuando **no** queda ninguno, el nivel
 * se reinicia entero, que es lo de siempre en un juego a uno (ahi el unico
 * jugador es tambien el ultimo). Una sola regla para los dos casos. */
static void np_player_die(NpWorld *w, uint8_t quien)
{
    NpPlayer *p = &w->players[quien];
    w->sfx |= NP_SFX_DIE;
    p->dying = NP_DYING_TIME;
    p->vy = -np_player_def.jump;
    p->vx = 0;
    p->anim = NP_ANIM_HURT;
    p->anim_frame = 0;
    if (!np_players_up(w)) {
        w->state = NP_STATE_DYING;
        w->state_timer = NP_DYING_TIME;
    }
}

static void np_player_hurt(NpWorld *w, uint8_t quien, uint8_t damage)
{
    NpPlayer *p = &w->players[quien];
    if (p->invuln || p->dying || !p->playing) return;
    if (w->state != NP_STATE_PLAY) return;
    if (damage >= p->health) {
        p->health = 0;
        np_player_die(w, quien);
        return;
    }
    p->health = (uint8_t)(p->health - damage);
    w->sfx |= NP_SFX_HURT;
    p->invuln = np_player_def.invuln;
    p->vy = -np_player_def.bounce / 2;
    p->vx = p->facing ? -np_player_def.knockback : np_player_def.knockback;
    /* El aturdimiento es lo que hace que el golpe duela de verdad: mientras
       dura no se frena ni se cambia de sentido, asi que el empujon te lleva
       donde te lleve. Con `aturdido: 0` se recupera el control al momento. */
    p->stun = np_player_def.stun;
    p->attack_timer = 0;
    p->stairs = 0;              /* un golpe te tira de la escalera */
}

static void np_finish_level(NpWorld *w);

/* ---------------------------------------------------------------- ataque */
/*
 * El boton de accion. Hasta ahora el motor lo leia y no hacia nada con el; con
 * `ataque:` en el game.yaml el jugador puede disparar o pegar.
 *
 * Disparar mete un proyectil en la lista de entidades, con `kind` a
 * NP_KIND_SHOT. Va ahi y no en una lista aparte a proposito: asi las cinco
 * maquinas lo dibujan sin tocar una linea (todas recorren las entidades y
 * piden su dibujo a np_entity_def) y la traza de las pruebas lo cuenta en su
 * hash, o sea que la paridad con el preview tambien lo comprueba.
 */

/* Un hueco libre en la lista. Se busca desde el principio, que es lo mismo que
   hace el preview: el orden tiene que ser identico o la paridad falla. */
static int np_hueco_libre(NpWorld *w)
{
    uint8_t i;
    for (i = 0; i < NP_MAX_ENTITIES; i++) {
        if (!w->entities[i].active) {
            if (i >= w->entity_count) w->entity_count = (uint8_t)(i + 1);
            return i;
        }
    }
    return -1;
}

/* El dano que hace un ataque a un enemigo. Devuelve 1 si le ha dado. */
static int np_hit_enemy(NpWorld *w, NpEntity *e, uint8_t damage)
{
    const NpEnemyDef *d = &np_enemies[e->def];
    if (e->health > damage) {
        e->health = (uint8_t)(e->health - damage);
        e->hurt = 20;
        w->sfx |= NP_SFX_STOMP;
        return 1;
    }
    e->active = 0;
    w->score += d->score;
    w->sfx |= NP_SFX_STOMP;
    if (d->boss) np_finish_level(w);
    return 1;
}

/* Le pega a un candelabro. Devuelve 1 si se lo ha llevado por delante.
 *
 * Al romperse suelta lo que lleve dentro ocupando **su propia ranura** de la
 * lista: asi un candelabro nunca puede quedarse sin sitio para su objeto, que
 * seria la peor forma de perder una vida extra. */
static int np_hit_breakable(NpWorld *w, NpEntity *e, uint8_t damage)
{
    const NpBreakableDef *d = &np_breakables[e->def];
    uint8_t suelta = d->drop;
    if (e->health > damage) {
        e->health = (uint8_t)(e->health - damage);
        e->hurt = 10;
        w->sfx |= NP_SFX_BREAK;
        return 1;
    }
    w->score += d->score;
    w->sfx |= NP_SFX_BREAK;
    if (!suelta || suelta > np_item_count) {
        e->active = 0;
        return 1;
    }
    {
        /* el objeto sale centrado donde estaba el candelabro */
        const NpActorDef *ea = &d->actor;
        const NpActorDef *ia = &np_items[suelta - 1].actor;
        np_fix cx = e->x + NP_I2F(ea->box_w / 2);
        np_fix suelo = e->y + NP_I2F(ea->box_h);
        e->kind = NP_KIND_ITEM;
        e->def = (uint8_t)(suelta - 1);
        e->x = cx - NP_I2F(ia->box_w / 2);
        e->y = suelo - NP_I2F(ia->box_h);
        e->home_x = e->x;
        e->home_y = e->y;
        e->vx = 0;
        e->vy = 0;
        e->health = 1;
        e->hurt = 0;
        e->timer = 0;
        e->vida = 0;
        e->anim = NP_ANIM_IDLE;
        e->anim_frame = 0;
        e->anim_timer = 0;
    }
    return 1;
}

/* Lo que hace un ataque al tocar una entidad: hacer dano a un enemigo o
 * reventar un candelabro. Devuelve 1 si ha pasado algo. */
static int np_hit_entity(NpWorld *w, NpEntity *e, uint8_t damage)
{
    if (e->kind == NP_KIND_ENEMY) return np_hit_enemy(w, e, damage);
    if (e->kind == NP_KIND_BREAKABLE) return np_hit_breakable(w, e, damage);
    return 0;
}

/* El alcance del arma ahora mismo: el de siempre mas lo que hayan sumado las
   mejoras. Es una cuenta y no un campo guardado para que no haya dos verdades
   que puedan separarse. */
static uint16_t np_attack_range(const NpPlayer *p)
{
    const NpAttackDef *at = &np_player_def.attack;
    uint8_t niveles = p->power < at->levels ? p->power : at->levels;
    return (uint16_t)(at->range + niveles * at->range_step);
}

static void np_player_attack(NpWorld *w, uint8_t quien)
{
    const NpAttackDef *at = &np_player_def.attack;
    NpPlayer *p = &w->players[quien];
    const NpActorDef *pa = &np_player_def.actor;

    if (at->kind == NP_ATTACK_NONE || p->attack_cd) return;
    p->attack_cd = at->cooldown;
    w->sfx |= NP_SFX_SHOOT;

    /* La pose de atacar dura lo mismo se pegue o se dispare: es lo que ve el
       jugador y lo que cuenta para `clavado:`. El golpe en si solo lo mira
       np_melee_update, que se desentiende si el ataque es de disparo. */
    p->attack_timer = at->duration;
    if (at->kind == NP_ATTACK_MELEE) return;
    {
        int hueco = np_hueco_libre(w);
        NpEntity *e;
        if (hueco < 0) return;               /* no cabe: el disparo se pierde */
        e = &w->entities[hueco];
        e->active = 1;
        e->kind = NP_KIND_SHOT;
        e->def = 0;
        e->facing = p->facing;
        /* sale a la altura del centro del jugador y por el lado que mira */
        e->x = p->x + NP_I2F(p->facing ? pa->box_w : -at->actor.box_w);
        e->y = p->y + NP_I2F((pa->box_h - at->actor.box_h) / 2);
        e->vx = p->facing ? at->speed : -at->speed;
        e->vy = 0;
        e->home_y = e->y;
        e->health = 1;
        e->hurt = 0;
        e->timer = 0;
        e->anim = NP_ANIM_IDLE;
        e->anim_frame = 0;
        e->anim_timer = 0;
        /* cuanto vuela: el alcance en pixeles, pasado a frames */
        e->vida = at->speed
            ? (uint16_t)((NP_I2F(np_attack_range(p)) / at->speed) + 1) : 1;
    }
}

/* El arma secundaria: arriba + accion, y gasta municion.
 *
 * Es lo que en los clasicos separa el latigo del cuchillo o el hacha: uno
 * siempre esta ahi y la otra se acaba. Con `tipo: arco` sale hacia arriba y la
 * gravedad la va bajando, que es la diferencia entre tirar de frente y tirar
 * por encima de una pared. */
static void np_player_sub(NpWorld *w, uint8_t quien)
{
    const NpSubDef *sb = &np_player_def.sub;
    NpPlayer *p = &w->players[quien];
    const NpActorDef *pa = &np_player_def.actor;
    int hueco;

    if (sb->kind == NP_SUB_NONE || p->attack_cd) return;
    if (w->hearts < sb->cost) return;         /* sin municion no sale nada */
    hueco = np_hueco_libre(w);
    if (hueco < 0) return;
    w->hearts = (uint8_t)(w->hearts - sb->cost);
    p->attack_cd = sb->cooldown;
    p->attack_timer = np_player_def.attack.duration;
    w->sfx |= NP_SFX_SHOOT;
    {
        NpEntity *e = &w->entities[hueco];
        e->active = 1;
        e->kind = NP_KIND_SUBSHOT;
        e->def = 0;
        e->facing = p->facing;
        e->x = p->x + NP_I2F(p->facing ? pa->box_w : -sb->actor.box_w);
        e->y = p->y + NP_I2F((pa->box_h - sb->actor.box_h) / 2);
        e->vx = p->facing ? sb->speed : -sb->speed;
        e->vy = (sb->kind == NP_SUB_ARC) ? -sb->jump : 0;
        e->home_x = e->x;
        e->home_y = e->y;
        e->health = 1;
        e->hurt = 0;
        e->timer = 0;
        e->anim = NP_ANIM_IDLE;
        e->anim_frame = 0;
        e->anim_timer = 0;
        e->vida = sb->speed ? (uint16_t)((NP_I2F(sb->range) / sb->speed) + 1) : 1;
    }
}

/* Lo tirado por el arma secundaria en vuelo. A diferencia del disparo normal,
   este puede caer: con `tipo: arco` la gravedad lo baja, y se apaga tambien al
   dar en el suelo. */
static void np_subshot_update(NpWorld *w, NpEntity *e)
{
    const NpSubDef *sb = &np_player_def.sub;
    const NpActorDef *a = &sb->actor;
    uint8_t i;
    int hit_x = 0, hit_down = 0, hit_up = 0;

    if (!e->vida) { e->active = 0; return; }
    e->vida--;
    if (sb->kind == NP_SUB_ARC) {
        e->vy += sb->gravity;
        if (e->vy > NP_ENTITY_FALL) e->vy = NP_ENTITY_FALL;
    }
    e->x = np_move_x(w->level, e->x, e->y, a->box_w, a->box_h, e->vx, &hit_x);
    if (hit_x) { e->active = 0; return; }
    if (e->vy) {
        e->y = np_move_y(w->level, e->x, e->y, a->box_w, a->box_h, e->vy, 1,
                         &hit_down, &hit_up);
        if (hit_down || hit_up) { e->active = 0; return; }
    }

    for (i = 0; i < w->entity_count; i++) {
        NpEntity *otra = &w->entities[i];
        const NpActorDef *ea;
        if (!otra->active) continue;
        if (otra->kind != NP_KIND_ENEMY && otra->kind != NP_KIND_BREAKABLE) continue;
        ea = np_entity_def(otra);
        if (!np_boxes_overlap(e->x, e->y, a->box_w, a->box_h,
                              otra->x, otra->y, ea->box_w, ea->box_h))
            continue;
        np_hit_entity(w, otra, sb->damage);
        e->active = 0;
        return;
    }
    np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
}

/* Un candelabro: no hace nada. Solo se anima y espera a que le pegues. */
static void np_breakable_update(NpWorld *w, NpEntity *e)
{
    const NpBreakableDef *d = &np_breakables[e->def];
    (void)w;
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_IDLE);
    np_anim_tick(&d->actor, e->anim, &e->anim_frame, &e->anim_timer);
}

/* Un proyectil en vuelo: avanza, y se apaga al chocar con una pared, al darle
   a un enemigo o al agotar su alcance. */
static void np_shot_update(NpWorld *w, NpEntity *e)
{
    const NpActorDef *a = &np_player_def.attack.actor;
    uint8_t i;
    int hit_x = 0;

    if (!e->vida) { e->active = 0; return; }
    e->vida--;
    e->x = np_move_x(w->level, e->x, e->y, a->box_w, a->box_h, e->vx, &hit_x);
    if (hit_x) { e->active = 0; return; }

    for (i = 0; i < w->entity_count; i++) {
        NpEntity *otra = &w->entities[i];
        const NpActorDef *ea;
        if (!otra->active) continue;
        if (otra->kind != NP_KIND_ENEMY && otra->kind != NP_KIND_BREAKABLE) continue;
        ea = np_entity_def(otra);
        if (!np_boxes_overlap(e->x, e->y, a->box_w, a->box_h,
                              otra->x, otra->y, ea->box_w, ea->box_h))
            continue;
        np_hit_entity(w, otra, np_player_def.attack.damage);
        e->active = 0;
        return;
    }
    np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
}

/* El golpe cuerpo a cuerpo: mientras dura, una caja delante del jugador. */
static void np_melee_update(NpWorld *w, uint8_t quien)
{
    const NpAttackDef *at = &np_player_def.attack;
    const NpActorDef *pa = &np_player_def.actor;
    NpPlayer *p = &w->players[quien];
    np_fix gx, gy;
    uint16_t alcance;
    uint8_t i;

    if (!p->attack_timer) return;
    p->attack_timer--;
    if (at->kind != NP_ATTACK_MELEE) return;   /* un disparo no pega de cerca */
    /* Los primeros `preparacion:` frames el golpe se ve pero no toca: el brazo
       todavia esta saliendo. Es la diferencia entre medir la distancia y
       machacar el boton. */
    if (p->attack_timer + at->windup >= at->duration) return;
    alcance = np_attack_range(p);
    gx = p->facing ? p->x + NP_I2F(pa->box_w) : p->x - NP_I2F(alcance);
    gy = p->y;
    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        const NpActorDef *ea;
        if (!e->active) continue;
        if (e->kind != NP_KIND_ENEMY && e->kind != NP_KIND_BREAKABLE) continue;
        /* Lo que esta parpadeando no se vuelve a tocar. La caja del golpe se
           queda puesta varios frames y acierta en todos: sin esto, un solo
           ataque se llevaba por delante a un enemigo de cinco de vida y el
           `vida:` de los enemigos no servia de nada contra un cuerpo a
           cuerpo. */
        if (e->hurt) continue;
        ea = np_entity_def(e);
        if (!np_boxes_overlap(gx, gy, alcance, pa->box_h,
                              e->x, e->y, ea->box_w, ea->box_h))
            continue;
        np_hit_entity(w, e, at->damage);
    }
}

/* --------------------------------------------------- plataformas moviles */

/* Va y viene entre donde salio y `distance` pixeles mas alla. Se mueve **antes
 * que los jugadores** (ver np_play_step): el que va encima tiene que ir con
 * ella, y para eso hay que saber cuanto se ha movido este frame. Eso es lo que
 * queda en vx/vy, que aqui no es una velocidad sino el desplazamiento de este
 * frame ya recortado en los extremos del recorrido. */
static void np_platform_update(NpWorld *w, NpEntity *e)
{
    const NpPlatformDef *d = &np_platforms[e->def];
    np_fix limite = NP_I2F(d->distance);
    np_fix paso = e->facing ? d->speed : -d->speed;
    (void)w;
    e->vx = 0;
    e->vy = 0;
    if (d->speed && d->distance) {
        if (d->axis == NP_PLAT_Y) {
            np_fix nueva = e->y + paso;
            if (nueva >= e->home_y + limite) { nueva = e->home_y + limite; e->facing = 0; }
            else if (nueva <= e->home_y) { nueva = e->home_y; e->facing = 1; }
            e->vy = nueva - e->y;
            e->y = nueva;
        } else {
            np_fix nueva = e->x + paso;
            if (nueva >= e->home_x + limite) { nueva = e->home_x + limite; e->facing = 0; }
            else if (nueva <= e->home_x) { nueva = e->home_x; e->facing = 1; }
            e->vx = nueva - e->x;
            e->x = nueva;
        }
    }
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_IDLE);
    np_anim_tick(&d->actor, e->anim, &e->anim_frame, &e->anim_timer);
}

/* Encima de que plataforma se queda el jugador, si es que se queda en alguna.
 *
 * Se mira despues de moverse con los tiles y funciona igual que un tile de
 * `plataforma`: solo se aterriza **cayendo y desde arriba**, y pulsando abajo
 * se deja caer. `antes_y` es donde estaba antes de moverse este frame (ya
 * llevado por la plataforma, si iba montado), que es lo que distingue
 * aterrizar encima de subir por dentro. */
static void np_ride_update(NpWorld *w, uint8_t quien, np_fix antes_y, int soltar)
{
    const NpActorDef *a = &np_player_def.actor;
    NpPlayer *p = &w->players[quien];
    np_fix pies_antes = antes_y + NP_I2F(a->box_h);
    uint8_t i;

    p->riding = 0;
    if (soltar || p->vy < 0) return;
    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        const NpActorDef *ea;
        if (!e->active || e->kind != NP_KIND_PLATFORM) continue;
        ea = &np_platforms[e->def].actor;
        if (p->x + NP_I2F(a->box_w) <= e->x) continue;
        if (e->x + NP_I2F(ea->box_w) <= p->x) continue;
        if (pies_antes > e->y) continue;                   /* venia por debajo */
        if (p->y + NP_I2F(a->box_h) < e->y) continue;      /* no llega a tocarla */
        p->y = e->y - NP_I2F(a->box_h);
        p->vy = 0;
        p->on_ground = 1;
        p->riding = (uint8_t)(i + 1);
        return;
    }
}

/* El boton de accion. Va aparte porque se usa igual andando que subido a una
   escalera: en los clasicos se pega desde la escalera, y no poder hacerlo
   convertiria cada escalera en una trampa. */
static void np_player_action(NpWorld *w, uint8_t quien, uint16_t input)
{
    NpPlayer *p = &w->players[quien];
    if (p->attack_cd) p->attack_cd--;
    if ((input & NP_IN_ACTION) && !(w->prev_input[quien] & NP_IN_ACTION)) {
        /* arriba + accion tira el arma secundaria; el boton a secas, el
           ataque de siempre. Si no hay arma o no queda municion, se pega. */
        if ((input & NP_IN_UP) && np_player_def.sub.kind != NP_SUB_NONE
            && w->hearts >= np_player_def.sub.cost)
            np_player_sub(w, quien);
        else
            np_player_attack(w, quien);
    }
    np_melee_update(w, quien);
}

/* ------------------------------------------------------------- escaleras */
/*
 * Una escalera es un **segundo modo de movimiento**, no un tile mas: mientras
 * estas subido no hay gravedad, ni saltos, ni choques con el escenario. Se
 * avanza en diagonal, un paso por frame, y se sale por arriba o por abajo.
 *
 * Todo se apoya en un solo punto de referencia: el **pixel de abajo del centro
 * de la caja del jugador** (los pies, un pixel por dentro). Mientras ese punto
 * caiga en una casilla de escalera, se sigue subido; en cuanto sale, el
 * jugador se planta de pie en la fila donde haya acabado. La misma regla vale
 * para llegar arriba y para llegar abajo, y por eso no hay dos casos que
 * mantener.
 */

static np_fix np_ref_x(const NpPlayer *p, const NpActorDef *a)
{
    return p->x + NP_I2F(a->box_w / 2);
}

static np_fix np_ref_y(const NpPlayer *p, const NpActorDef *a)
{
    return p->y + NP_I2F(a->box_h - 1);
}

/* Coloca al jugador con el punto de referencia en el centro de esa casilla:
   subirse a una escalera te centra en ella, como en los clasicos. */
static void np_stair_place(NpPlayer *p, const NpActorDef *a,
                           int32_t tx, int32_t ty)
{
    p->x = NP_I2F(tx * NP_TILE + NP_TILE / 2 - a->box_w / 2);
    p->y = NP_I2F(ty * NP_TILE + NP_TILE / 2 - (a->box_h - 1));
    p->vx = 0;
    p->vy = 0;
}

/* Intenta subirse a una escalera. Devuelve 1 si se ha subido.
 *
 * Hacia arriba basta con que los pies esten dentro de una escalera: es la
 * casilla en la que estas cuando andas por delante de ella. Hacia abajo hay
 * que mirar **en diagonal**, porque el primer escalon de bajada no esta debajo
 * de los pies sino un paso hacia el lado: la escalera arranca donde acaba el
 * suelo. */
static int np_stair_mount(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpActorDef *a = &np_player_def.actor;
    NpPlayer *p = &w->players[quien];
    int32_t tx = NP_F2I(np_ref_x(p, a)) >> NP_TILE_SHIFT;
    uint8_t kind;

    if (!p->on_ground || np_player_def.stair_speed <= 0) return 0;

    if (input & NP_IN_UP) {
        int32_t ty = NP_F2I(np_ref_y(p, a)) >> NP_TILE_SHIFT;
        kind = np_stair_at(w->level, np_ref_x(p, a), np_ref_y(p, a));
        if (kind) {
            p->stairs = 1;
            p->stair_dir = (kind == NP_TILE_STAIR_R) ? 1 : -1;
            np_stair_place(p, a, tx, ty);
            return 1;
        }
    }
    if (input & NP_IN_DOWN) {
        /* la fila del suelo que estas pisando; el escalon esta una mas abajo */
        int32_t ty = (NP_F2I(p->y + NP_I2F(a->box_h)) >> NP_TILE_SHIFT) + 1;
        int32_t bx;
        for (bx = -1; bx <= 1; bx += 2) {
            uint8_t esperado = (bx < 0) ? NP_TILE_STAIR_R : NP_TILE_STAIR_L;
            kind = np_tile_kind_at(w->level, tx + bx, ty);
            if (kind != esperado) continue;
            p->stairs = 1;
            p->stair_dir = (kind == NP_TILE_STAIR_R) ? 1 : -1;
            np_stair_place(p, a, tx + bx, ty);
            return 1;
        }
    }
    return 0;
}

/* Un frame subido a la escalera. Devuelve 1 si sigue en ella. */
static int np_stair_update(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpPlayerDef *d = &np_player_def;
    const NpActorDef *a = &d->actor;
    NpPlayer *p = &w->players[quien];
    int moviendo = 0;

    p->vx = 0;
    p->vy = 0;
    p->on_ground = 0;
    if (input & NP_IN_UP) {
        p->x += (np_fix)p->stair_dir * d->stair_speed;
        p->y -= d->stair_speed;
        moviendo = 1;
    } else if (input & NP_IN_DOWN) {
        p->x -= (np_fix)p->stair_dir * d->stair_speed;
        p->y += d->stair_speed;
        moviendo = 1;
    }
    if (!np_stair_at(w->level, np_ref_x(p, a), np_ref_y(p, a))) {
        /* se ha acabado la escalera: de pie en la fila donde han quedado los
           pies, que es el suelo de arriba subiendo y el de abajo bajando */
        int32_t ty = NP_F2I(np_ref_y(p, a)) >> NP_TILE_SHIFT;
        p->y = NP_I2F(ty * NP_TILE - a->box_h);
        p->stairs = 0;
        p->on_ground = 1;
        return 0;
    }
    np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_STAIR);
    /* quieto en la escalera se queda quieto el dibujo: solo anima al avanzar */
    if (moviendo) np_anim_tick(a, p->anim, &p->anim_frame, &p->anim_timer);
    return 1;
}

/* ------------------------------------------------------------- el jugador */

static void np_player_update(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpPlayerDef *d = &np_player_def;
    const NpActorDef *a = &d->actor;
    NpPlayer *p = &w->players[quien];
    int dir = 0;
    int hit_x = 0, hit_down = 0, hit_up = 0;
    int pressed_jump;
    np_fix antes_y;

    /* Si venia montado en una plataforma, se va con ella antes de nada. En
       horizontal a traves de np_move_x, para que la plataforma no le meta
       dentro de una pared. */
    if (p->riding && p->riding <= w->entity_count) {
        const NpEntity *e = &w->entities[p->riding - 1];
        if (e->active && e->kind == NP_KIND_PLATFORM) {
            int llevado = 0;
            if (e->vx) p->x = np_move_x(w->level, p->x, p->y, a->box_w, a->box_h,
                                        e->vx, &llevado);
            (void)llevado;              /* si topa con una pared, se queda ahi */
            if (e->vy) p->y = np_move_y(w->level, p->x, p->y, a->box_w, a->box_h,
                                        e->vy, 0, &hit_down, &hit_up);
        }
    }
    hit_down = 0;
    hit_up = 0;

    /* Aturdido: el mando no se lee. Ni andar, ni saltar, ni pegar; la
       velocidad que traiga se respeta tal cual para que el empujon del golpe
       llegue hasta el final. La gravedad y los choques siguen su curso. */
    if (p->stun) {
        p->stun--;
        input = 0;
    } else {
        if (input & NP_IN_RIGHT) dir += 1;
        if (input & NP_IN_LEFT) dir -= 1;
    }

    /* --- escaleras -------------------------------------------------------
     *
     * Subido a una escalera manda la escalera: ni gravedad, ni saltos, ni
     * choques con el escenario. Lo unico que sigue funcionando es el boton de
     * accion. Al salirse (por arriba o por abajo) se acaba el frame ahi y el
     * siguiente ya es uno normal, de pie. */
    if (p->stairs) {
        np_player_action(w, quien, input);
        if (!np_stair_update(w, quien, input))
            np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_IDLE);
        return;
    }
    if (!p->stun && np_stair_mount(w, quien, input)) {
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_STAIR);
        return;
    }

    /* Mientras dura un golpe con `clavado: si` te quedas plantado: ni andas ni
       te giras, que es lo que obliga a elegir cuando pegas. En el aire si se
       conserva el impulso, como en los clasicos: saltas y pegas de camino. */
    if (p->attack_timer && d->attack.locks && p->on_ground) {
        p->vx = 0;
    } else if (p->stun) {
        /* ni acelerar ni frenar: el empujon del golpe llega hasta el final */
    } else if (dir > 0) { p->vx = np_approach(p->vx, d->speed, p->on_ground ? d->accel : d->air_accel); p->facing = 1; }
    else if (dir < 0) { p->vx = np_approach(p->vx, -d->speed, p->on_ground ? d->accel : d->air_accel); p->facing = 0; }
    else if (p->on_ground) p->vx = np_approach(p->vx, 0, d->friction);

    /* El ataque va por flanco: mantener el boton no dispara sin parar, y la
       cadencia la marca `espera:` del game.yaml. */
    np_player_action(w, quien, input);

    pressed_jump = (input & NP_IN_JUMP) && !(w->prev_input[quien] & NP_IN_JUMP);
    if (pressed_jump) p->buffer = (uint8_t)(d->jump_buffer + 1);
    if (p->buffer) p->buffer--;

    if (p->on_ground) {
        p->coyote = d->coyote;
        p->jumps_left = d->double_jump ? 1 : 0;
    } else if (p->coyote) {
        p->coyote--;
    }

    if (p->buffer && (p->coyote || p->jumps_left)) {
        w->sfx |= p->coyote ? NP_SFX_JUMP : NP_SFX_DJUMP;
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
    antes_y = p->y;
    p->y = np_move_y(w->level, p->x, p->y, a->box_w, a->box_h, p->vy,
                     (input & NP_IN_DOWN) ? 1 : 0, &hit_down, &hit_up);
    p->on_ground = (uint8_t)hit_down;
    if (hit_down && p->vy > 0) p->vy = 0;
    if (hit_up && p->vy < 0) p->vy = 0;
    np_ride_update(w, quien, antes_y, (input & NP_IN_DOWN) ? 1 : 0);

    if (p->invuln) p->invuln--;

    if (p->attack_timer)
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_ATTACK);
    else if (!p->on_ground)
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer,
                    p->vy < 0 ? NP_ANIM_JUMP : NP_ANIM_FALL);
    else if (p->vx > NP_I2F(1) / 8 || p->vx < -(NP_I2F(1) / 8))
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_RUN);
    else
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_IDLE);
    np_anim_tick(a, p->anim, &p->anim_frame, &p->anim_timer);
}

/* --------------------------------------------------------------- enemigos */

/* A quien persigue un enemigo: al jugador en juego que tenga mas cerca. Con un
   solo jugador siempre es el mismo, asi que el juego a uno no cambia. */
static const NpPlayer *np_nearest_player(const NpWorld *w, np_fix x)
{
    const NpPlayer *mejor = &w->players[0];
    np_fix distancia = 0;
    uint8_t i, primero = 1;
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpPlayer *p = &w->players[i];
        np_fix d = NP_ABS(p->x - x);
        if (!p->playing || p->dying) continue;
        if (primero || d < distancia) { mejor = p; distancia = d; primero = 0; }
    }
    return mejor;
}

static void np_enemy_update(NpWorld *w, NpEntity *e)
{
    const NpEnemyDef *d = &np_enemies[e->def];
    const NpActorDef *a = &d->actor;
    const NpPlayer *p = np_nearest_player(w, e->x);
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

/* Lo recoge quien lo toca: la vida y la salud van a ese jugador, y los puntos
   y las llaves al marcador, que es comun. */
static void np_collect(NpWorld *w, uint8_t quien, NpEntity *e)
{
    const NpItemDef *d = &np_items[e->def];
    NpPlayer *p = &w->players[quien];
    w->score += d->score;
    w->sfx |= (d->effect == NP_ITEM_LIFE) ? NP_SFX_LIFE : NP_SFX_COIN;
    switch (d->effect) {
    case NP_ITEM_LIFE:
        if (p->lives < 99) p->lives = (uint8_t)(p->lives + d->amount);
        break;
    case NP_ITEM_HEALTH:
        p->health = (uint8_t)NP_MIN(p->health + d->amount,
                                    np_player_def.health);
        break;
    case NP_ITEM_KEY:
        if (w->keys < 255) w->keys = (uint8_t)(w->keys + d->amount);
        break;
    case NP_ITEM_AMMO:
        w->hearts = (uint8_t)NP_MIN(w->hearts + d->amount, 99);
        break;
    case NP_ITEM_UPGRADE:
        p->power = (uint8_t)NP_MIN(p->power + d->amount,
                                   np_player_def.attack.levels);
        break;
    default:
        break;
    }
    e->active = 0;
}

/* Se acaba el nivel: por la meta o por matar al jefe, da igual. */
static void np_finish_level(NpWorld *w)
{
    w->sfx |= NP_SFX_GOAL;
    w->state = NP_STATE_LEVEL_END;
    w->state_timer = NP_LEVEL_END_TIME;
    w->score += 100 + (w->time_left / 60) * 10;
}

/* Los puntos de control. Se busca **la casilla**, no solo si toca alguna,
   porque lo que hay que guardar es donde estaba: el jugador reaparecera ahi.
   Volver a pasar por el que ya esta marcado no hace nada (ni suena), pero
   pasar por uno anterior si lo mueve hacia atras: manda el ultimo que se toca,
   que es lo que uno espera despues de retroceder a por algo. */
static void np_check_touch(NpWorld *w, uint8_t quien)
{
    const NpActorDef *a = &np_player_def.actor;
    const NpPlayer *p = &w->players[quien];
    int32_t tx0 = NP_F2I(p->x) >> NP_TILE_SHIFT;
    int32_t tx1 = NP_F2I(p->x + NP_I2F(a->box_w) - 1) >> NP_TILE_SHIFT;
    int32_t ty0 = NP_F2I(p->y) >> NP_TILE_SHIFT;
    int32_t ty1 = NP_F2I(p->y + NP_I2F(a->box_h) - 1) >> NP_TILE_SHIFT;
    int32_t tx, ty;
    for (ty = ty0; ty <= ty1; ty++) {
        for (tx = tx0; tx <= tx1; tx++) {
            if (np_tile_kind_at(w->level, tx, ty) != NP_TILE_CHECK) continue;
            if (w->check_on && w->check_x == (int16_t)tx &&
                w->check_y == (int16_t)ty)
                return;
            w->check_on = 1;
            w->check_x = (int16_t)tx;
            w->check_y = (int16_t)ty;
            w->sfx |= NP_SFX_CHECK;
            return;
        }
    }
}

/* Quien toca que. Se recorre jugador por jugador y, dentro, entidad por
   entidad: asi el orden es el mismo con uno y con dos, y el juego a uno sale
   exactamente igual que antes. */
static void np_touch_entities(NpWorld *w)
{
    const NpActorDef *pa = &np_player_def.actor;
    uint8_t quien, i;
    for (quien = 0; quien < NP_MAX_PLAYERS; quien++) {
        NpPlayer *p = &w->players[quien];
        if (!p->playing || p->dying) continue;
        for (i = 0; i < w->entity_count; i++) {
            NpEntity *e = &w->entities[i];
            const NpActorDef *ea;
            if (!e->active) continue;
            ea = np_entity_def(e);
            if (!np_boxes_overlap(p->x, p->y, pa->box_w, pa->box_h,
                                  e->x, e->y, ea->box_w, ea->box_h))
                continue;
            if (e->kind == NP_KIND_SHOT || e->kind == NP_KIND_SUBSHOT)
                continue;                            /* es tuyo: no te toca */
            if (e->kind == NP_KIND_PLATFORM) continue;   /* es suelo, no un bicho */
            if (e->kind == NP_KIND_BREAKABLE) continue;  /* hay que pegarle */
            if (e->kind == NP_KIND_ITEM) {
                np_collect(w, quien, e);
                continue;
            }
            {
                const NpEnemyDef *d = &np_enemies[e->def];
                /* Se pisa al enemigo si vienes cayendo y, antes de moverte en
                 * este frame, tenias los pies por encima de su mitad. Con un
                 * tercio la ventana era tan estrecha que era casi imposible
                 * acertar. */
                int from_above = p->vy > 0 &&
                    (p->y + NP_I2F(pa->box_h) - p->vy) <= e->y + NP_I2F(ea->box_h / 2);
                if (np_player_def.stomp && d->stompable && from_above) {
                    w->sfx |= NP_SFX_STOMP;
                    if (e->health > 1) {
                        e->health--;
                        e->hurt = 20;
                    } else {
                        e->active = 0;
                        w->score += d->score;
                        /* matar al jefe termina el nivel, como llegar a la meta */
                        if (d->boss) np_finish_level(w);
                    }
                    p->vy = -np_player_def.bounce;
                    p->on_ground = 0;
                } else {
                    np_player_hurt(w, quien, d->damage);
                }
            }
        }
    }
}

/* ---------------------------------------------------------------- camara */

/* Hay dos formas de mover la camara, y se elige en el game.yaml:
 *
 *   scroll     la camara sigue al jugador y el escenario se desliza. Es lo
 *              que hacen los juegos de consola de la epoca.
 *   pantallas  el nivel se reparte en pantallas fijas y la camara salta de una
 *              a la siguiente cuando el jugador cruza el borde, sin deslizarse.
 *              Es lo que hacian casi todos los de ordenador de 8 bits.
 *
 * La ultima pantalla puede quedarse corta si el nivel no mide un numero exacto
 * de pantallas: entonces se recorta contra el final del nivel y se solapa un
 * poco con la anterior. El compilador avisa cuando pasa. */
static void np_camera_update(NpWorld *w)
{
    const NpActorDef *a = &np_player_def.actor;
    int32_t max_x = (int32_t)w->level->width * NP_TILE - NP_SCREEN_W;
    int32_t max_y = (int32_t)w->level->height * NP_TILE - NP_SCREEN_H;
    int32_t centro_x = 0, centro_y = 0;
    int32_t target_x, target_y;
    /* A dos jugadores la camara va al punto medio de los dos. Con uno sale la
       misma cuenta de siempre: la suma de uno dividida por uno. */
    uint8_t i, cuantos = 0;
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        if (!w->players[i].playing) continue;
        centro_x += NP_F2I(w->players[i].x) + a->box_w / 2;
        centro_y += NP_F2I(w->players[i].y) + a->box_h / 2;
        cuantos++;
    }
    if (!cuantos) {
        /* game over: no queda nadie en juego, pero la camara tiene que
           quedarse donde estaba y no irse al origen */
        centro_x = NP_F2I(w->players[0].x) + a->box_w / 2;
        centro_y = NP_F2I(w->players[0].y) + a->box_h / 2;
    } else if (cuantos > 1) {
        centro_x /= cuantos;
        centro_y /= cuantos;
    }
    if (max_x < 0) max_x = 0;
    if (max_y < 0) max_y = 0;
    if (np_camara_pantallas) {
        if (centro_x < 0) centro_x = 0;
        if (centro_y < 0) centro_y = 0;
        target_x = (centro_x / NP_SCREEN_W) * NP_SCREEN_W;
        target_y = (centro_y / NP_SCREEN_H) * NP_SCREEN_H;
    } else {
        target_x = centro_x - NP_SCREEN_W / 2;
        target_y = centro_y - NP_SCREEN_H / 2;
    }
    w->cam_x = NP_CLAMP(target_x, 0, max_x);
    w->cam_y = NP_CLAMP(target_y, 0, max_y);
}

/* A dos jugadores, el que se queda atras no puede salirse de la pantalla: la
 * camara va al punto medio y a el se le para en el borde. Con un solo jugador
 * no se toca nada -la camara lo lleva centrado y nunca se sale-, asi que el
 * juego a uno sigue siendo exactamente el mismo. */
static void np_players_in_view(NpWorld *w)
{
    const NpActorDef *a = &np_player_def.actor;
    int32_t izquierda = w->cam_x;
    int32_t derecha = w->cam_x + NP_SCREEN_W - a->box_w;
    uint8_t i;
    if (np_player_count < 2) return;
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        NpPlayer *p = &w->players[i];
        if (!p->playing || p->dying) continue;
        if (NP_F2I(p->x) < izquierda) { p->x = NP_I2F(izquierda); if (p->vx < 0) p->vx = 0; }
        if (NP_F2I(p->x) > derecha) { p->x = NP_I2F(derecha); if (p->vx > 0) p->vx = 0; }
    }
}

int np_player_visible(const NpWorld *w, uint8_t quien)
{
    const NpPlayer *p = &w->players[quien];
    if (!p->playing) return 0;
    if (w->state == NP_STATE_TITLE || w->state == NP_STATE_GAME_OVER) return 0;
    if (p->invuln && (w->frame & 2)) return 0;   /* parpadeo */
    return 1;
}

/* ----------------------------------------------------------------- estados */

/* Un jugador que se esta muriendo mientras el otro sigue: cae, y al acabar la
   caida reaparece si le quedan vidas. Si se queda sin ellas, se va del juego. */
static void np_player_falling(NpWorld *w, uint8_t quien)
{
    NpPlayer *p = &w->players[quien];
    p->vy += np_player_def.gravity;
    if (p->vy > np_player_def.max_fall) p->vy = np_player_def.max_fall;
    p->y += p->vy;
    if (p->dying) p->dying--;
    if (p->dying) return;
    if (p->lives > 1) {
        p->lives--;
        np_player_reset(w, quien);
    } else {
        p->lives = 0;
        p->playing = 0;
    }
}

/* Volver a empezar el nivel despues de perder una vida. Es cargar el nivel,
   pero conservando el punto de control: cargarlo lo borra (empezar un nivel es
   empezarlo de cero) y aqui no se esta empezando, se esta reintentando. */
static void np_level_restart(NpWorld *w)
{
    uint8_t on = w->check_on, i;
    int16_t cx = w->check_x, cy = w->check_y;
    np_world_load_level(w, w->level_index);
    if (!on) return;
    w->check_on = on;
    w->check_x = cx;
    w->check_y = cy;
    for (i = 0; i < NP_MAX_PLAYERS; i++) np_player_place(w, i);
}

static void np_play_step(NpWorld *w, uint16_t input, uint16_t input2)
{
    const NpActorDef *pa = &np_player_def.actor;
    uint16_t mandos[NP_MAX_PLAYERS];
    uint8_t quien, i;

    mandos[0] = input;
    if (NP_MAX_PLAYERS > 1) mandos[1] = input2;

    /* Las plataformas moviles se mueven antes que nadie: el jugador que va
       encima se apunta al sitio donde han quedado. Tampoco se pausan fuera de
       pantalla como los enemigos: el que las lleva siempre esta a la vista. */
    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        if (e->active && e->kind == NP_KIND_PLATFORM) np_platform_update(w, e);
    }

    for (quien = 0; quien < NP_MAX_PLAYERS; quien++) {
        NpPlayer *p = &w->players[quien];
        if (!p->playing) continue;
        if (p->dying) np_player_falling(w, quien);
        else np_player_update(w, quien, mandos[quien]);
    }

    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        int32_t dx;
        if (!e->active) continue;
        dx = NP_F2I(e->x) - (int32_t)w->cam_x;
        if (dx < -NP_CULL_MARGIN || dx > NP_SCREEN_W + NP_CULL_MARGIN) {
            /* Lejos de la vista, los enemigos se quedan en pausa y los
               proyectiles se apagan: uno que sale de la pantalla ya no vuelve,
               y si no se ocuparia un hueco de la lista hasta agotar su
               alcance. */
            if (e->kind == NP_KIND_SHOT || e->kind == NP_KIND_SUBSHOT) {
                e->active = 0;
                continue;
            }
            if (e->kind == NP_KIND_ENEMY) continue;
        }
        if (e->kind == NP_KIND_PLATFORM) continue;      /* ya se ha movido */
        if (e->hurt) e->hurt--;
        if (e->kind == NP_KIND_SHOT) np_shot_update(w, e);
        else if (e->kind == NP_KIND_SUBSHOT) np_subshot_update(w, e);
        else if (e->kind == NP_KIND_ENEMY) np_enemy_update(w, e);
        else if (e->kind == NP_KIND_BREAKABLE) np_breakable_update(w, e);
        else np_item_update(w, e);
    }

    np_touch_entities(w);

    /* Que jefe hay en pantalla, para el marcador. Se mira despues de las
       colisiones para que el golpe de este frame ya se vea, y para que al
       matarlo quede en cero. */
    w->boss_health = 0;
    w->boss_max = 0;
    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
        if (e->active && e->kind == NP_KIND_ENEMY && np_enemies[e->def].boss) {
            w->boss_health = e->health;
            w->boss_max = np_enemies[e->def].health;
            break;
        }
    }


    if (w->state != NP_STATE_PLAY) return;

    for (quien = 0; quien < NP_MAX_PLAYERS; quien++) {
        NpPlayer *p = &w->players[quien];
        if (!p->playing || p->dying) continue;
        if (np_box_touches(w->level,
                           p->x + NP_I2F(NP_HAZARD_INSET_X),
                           p->y + NP_I2F(NP_HAZARD_INSET_Y),
                           pa->box_w - NP_HAZARD_INSET_X * 2,
                           pa->box_h - NP_HAZARD_INSET_Y,
                           NP_TILE_HAZARD)) {
            np_player_hurt(w, quien, 99);
            continue;
        }
        np_check_touch(w, quien);
        /* La meta solo se abre si se llevan las llaves que pide el nivel. Las
         * llaves son de la partida, no de cada jugador: a dos, las que coge
         * uno le valen al otro. */
        if (w->keys >= w->level->keys_needed &&
            np_box_touches(w->level, p->x, p->y, pa->box_w, pa->box_h,
                           NP_TILE_GOAL)) {
            np_finish_level(w);            /* llega uno, se acaba para los dos */
            return;
        }
        if (NP_F2I(p->y) > (int32_t)(w->level->height + 2) * NP_TILE)
            np_player_hurt(w, quien, 99);
    }
    if (w->state != NP_STATE_PLAY) return;

    /* el tiempo es de la partida, no de cada uno: al acabarse caen los dos */
    if (np_time_limit) {
        if (w->time_left) {
            w->time_left--;
        } else {
            for (quien = 0; quien < NP_MAX_PLAYERS; quien++)
                np_player_hurt(w, quien, 99);
        }
    }
}

/* La barra de vida del jefe, para el marcador: "BOSS ######    ".
 *
 * Siempre ocupa lo mismo y se rellena con espacios, asi que al escribirla borra
 * lo que hubiera antes y no hace falta limpiar la fila aparte. Sin jefe en
 * pantalla sale entera en blanco. Necesita NP_BOSS_BAR + 6 caracteres. */
void np_boss_bar(char *out, const NpWorld *w)
{
    uint8_t i, llenos = 0;
    const char *titulo = "     ";
    if (w->boss_health && w->boss_max) {
        int32_t partes = ((int32_t)w->boss_health * NP_BOSS_BAR
                          + w->boss_max - 1) / w->boss_max;
        llenos = (uint8_t)(partes > NP_BOSS_BAR ? NP_BOSS_BAR : partes);
        titulo = "BOSS ";
    }
    for (i = 0; i < 5; i++) out[i] = titulo[i];
    for (i = 0; i < NP_BOSS_BAR; i++) out[5 + i] = (i < llenos) ? '#' : ' ';
    out[5 + NP_BOSS_BAR] = 0;
}

/* Escribe "NN" en dos digitos, con tope en 99. */
static void np_dos_digitos(char *out, uint8_t valor)
{
    if (valor > 99) valor = 99;
    out[0] = (char)('0' + valor / 10);
    out[1] = (char)('0' + valor % 10);
}

/* La linea de "lo que llevas": llaves y municion, "KEYS 01/03 AMMO 05" (en
   ingles como el resto del marcador: SCORE, LIVES, BOSS). Cada mitad sale en
   blanco si el juego no la usa, asi que el marcador no tiene que saber nada de
   esto y se limita a escribir lo que salga. */
void np_extras_bar(char *out, const NpWorld *w)
{
    static const char llaves[] = "KEYS ";
    static const char municion[] = "AMMO ";
    uint8_t i, piden = w->level ? w->level->keys_needed : 0;

    for (i = 0; i < NP_EXTRAS_BAR; i++) out[i] = ' ';
    out[NP_EXTRAS_BAR] = 0;
    if (piden) {
        for (i = 0; i < 5; i++) out[i] = llaves[i];
        np_dos_digitos(out + 5, w->keys);
        out[7] = '/';
        np_dos_digitos(out + 8, piden);
    }
    /* la municion solo tiene sentido si el juego lleva arma secundaria */
    if (np_player_def.sub.kind != NP_SUB_NONE) {
        for (i = 0; i < 5; i++) out[11 + i] = municion[i];
        np_dos_digitos(out + 16, w->hearts);
    }
}

/* La vida del jugador, para el marcador: "LIFE ##..".
 *
 * Los llenos son los golpes que le quedan y los puntos los que ha perdido, asi
 * que de un vistazo se ve cuanto aguanta **y** cuanto aguantaba entero. Sale
 * entera en blanco cuando el juego se juega a un golpe (`vida: 1`), igual que
 * la municion sale en blanco sin arma secundaria: ahi no hay nada que mirar.
 *
 * Los cuadrados arrancan siempre en la posicion 5, se llame como se llame la
 * etiqueta, para que a dos jugadores las dos barras queden alineadas.
 *
 * Fuera de la partida sale en blanco a proposito: en el Amiga, el Jaguar y el
 * Atari ST el marcador es una banda de tres filas y la tercera -la de la barra-
 * es la que usan el titulo y el "game over". Decidirlo aqui y no en cada
 * maquina deja los cinco marcadores iguales.
 *
 * Ocupa **lo que necesita**, no siempre lo maximo: escribir el marcador cuesta
 * una escritura de VRAM por letra y esta barra se repinta justo en el frame del
 * golpe, que es el mas caro de la partida. Cuando no hay nada que ensenar si
 * sale entera de espacios, porque entonces lo que hace falta es borrar. */
void np_life_bar(char *out, const NpWorld *w, uint8_t quien)
{
    const NpPlayer *p = &w->players[quien];
    const char *titulo;
    uint8_t i, capacidad, llenos;

    if (w->state != NP_STATE_PLAY || np_player_def.health <= 1 || !p->playing) {
        for (i = 0; i < 5 + NP_LIFE_BAR; i++) out[i] = ' ';
        out[5 + NP_LIFE_BAR] = 0;
        return;
    }
    titulo = (np_player_count > 1) ? (quien ? "2P   " : "1P   ") : "LIFE ";
    capacidad = np_life_pips();
    llenos = (p->health > capacidad) ? capacidad : p->health;
    for (i = 0; i < 5; i++) out[i] = titulo[i];
    for (i = 0; i < capacidad; i++) out[5 + i] = (i < llenos) ? '#' : '.';
    out[5 + capacidad] = 0;
}

/* Cuantos cuadrados tiene la barra de este juego. Es fijo durante toda la
   partida (sale de `vida:`), asi que el marcador puede pintar la etiqueta una
   vez y repintar solo los cuadrados. */
uint8_t np_life_pips(void)
{
    if (np_player_def.health <= 1) return 0;
    return (np_player_def.health > NP_LIFE_BAR)
         ? NP_LIFE_BAR : np_player_def.health;
}

void np_world_step(NpWorld *w, uint16_t input, uint16_t input2)
{
    /* Start vale desde cualquiera de los dos mandos: en la maquina recreativa
       la partida la empieza el que llega primero. */
    uint16_t ambos = (uint16_t)(input | (np_player_count > 1 ? input2 : 0));
    uint16_t antes = (uint16_t)(w->prev_input[0]
                     | (np_player_count > 1 ? w->prev_input[1] : 0));
    int start_pressed = (ambos & NP_IN_START) && !(antes & NP_IN_START);
    uint8_t quien;
    w->frame++;
    w->sfx = 0;                 /* los eventos duran un solo frame */

    switch (w->state) {
    case NP_STATE_TITLE:
        if (start_pressed) {
            w->sfx |= NP_SFX_START;
            w->score = 0;
            for (quien = 0; quien < NP_MAX_PLAYERS; quien++) {
                w->players[quien].playing = (uint8_t)(quien < np_player_count);
                w->players[quien].lives = np_start_lives;
            }
            np_world_load_level(w, 0);
        }
        break;

    case NP_STATE_PLAY:
        np_play_step(w, input, input2);
        break;

    case NP_STATE_DYING:
        /* Aqui se llega cuando **no queda nadie en pie**: caen todos y, al
           acabar la cuenta, el nivel vuelve a empezar si a alguno le quedan
           vidas. Con un solo jugador es lo de siempre. */
        for (quien = 0; quien < NP_MAX_PLAYERS; quien++) {
            NpPlayer *p = &w->players[quien];
            if (!p->playing || !p->dying) continue;
            p->vy += np_player_def.gravity;
            if (p->vy > np_player_def.max_fall) p->vy = np_player_def.max_fall;
            p->y += p->vy;
        }
        if (w->state_timer) {
            w->state_timer--;
        } else {
            uint8_t quedan = 0;
            for (quien = 0; quien < NP_MAX_PLAYERS; quien++) {
                NpPlayer *p = &w->players[quien];
                if (!p->playing) continue;
                if (p->lives > 1) { p->lives--; quedan++; }
                else { p->lives = 0; p->playing = 0; }
            }
            if (quedan) {
                np_level_restart(w);
            } else {
                w->state = NP_STATE_GAME_OVER;
                w->state_timer = NP_GAME_OVER_TIME;
            }
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
    np_players_in_view(w);
    w->prev_input[0] = input;
    if (NP_MAX_PLAYERS > 1) w->prev_input[1] = input2;
}
