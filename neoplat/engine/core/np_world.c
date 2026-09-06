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
    /* Ojo con las medidas: `cells_w` y `cells_h` son las del mapa que se pisa,
       que en casi todos los juegos es el que se ve y en la vista isometrica no
       -alli lo que se ve es el dibujo de las salas y esto es su planta-. */
    if (tx < 0 || tx >= (int32_t)level->cells_w) return NP_TILE_SOLID;  /* paredes */
    /* De lado, por arriba hay cielo y por abajo un abismo donde caerse. Desde
       arriba no: ahi el mapa es una caja cerrada y sus cuatro lados son
       pared, que si no se saldria uno del escenario andando. */
    if (ty < 0) return np_vista_cenital ? NP_TILE_SOLID : NP_TILE_EMPTY;
    if (ty >= (int32_t)level->cells_h)
        return np_vista_cenital ? NP_TILE_SOLID : NP_TILE_EMPTY;
    return np_tile_kind[level->cells[ty * level->cells_w + tx]];
}

/* Lo mismo, pero contando los cerrojos que ya se han abierto: una puerta
 * abierta es aire, y hay que verla como aire desde todos los sitios que miran
 * el escenario -andar, chocar, caerse-. Por eso la pregunta de verdad es esta
 * y no la de arriba.
 *
 * Se mira la lista de abiertos **solo** cuando la casilla es un cerrojo, que
 * es una entre mil: en un juego sin cerrojos esto no cuesta nada. */
static uint8_t np_tile_visto(const NpWorld *w, int32_t tx, int32_t ty)
{
    uint8_t kind = np_tile_kind_at(w->level, tx, ty);
    uint16_t casilla;
    uint8_t i;
    if (kind != NP_TILE_LOCK) return kind;
    casilla = (uint16_t)(ty * (int32_t)w->level->cells_w + tx);
    for (i = 0; i < w->abiertos_n; i++)
        if (w->abiertos[i] == casilla) return NP_TILE_EMPTY;
    return kind;
}

uint16_t np_tile_gfx_at(const NpWorld *w, int32_t tx, int32_t ty)
{
    const NpLevel *level = w->level;
    if (tx < 0 || tx >= (int32_t)level->width) return 0;
    if (ty < 0 || ty >= (int32_t)level->height) return 0;
    /* En la isometrica el escenario que se dibuja no es el mapa: es el suelo
       de las salas, que ya viene en numeros de tile. Lo que levanta el relieve
       -los cubos- no se pinta aqui, se dibuja como entidad para que entre en
       su sitio en la fila de profundidad. */
    if (np_vista_iso) return level->fondo[ty * level->width + tx];
    /* Una puerta abierta se ve por lo que hay detras: el aire. Solo se
       pregunta cuando hay alguna abierta, que en casi todos los juegos es
       nunca. */
    if (w->abiertos_n && np_tile_kind_at(level, tx, ty) == NP_TILE_LOCK
        && np_tile_visto(w, tx, ty) == NP_TILE_EMPTY)
        return np_tile_gfx_vacio;
    return np_tile_gfx[level->cells[ty * level->cells_w + tx]];
}

/* Los graficos de una columna entera de tiles, de arriba a abajo.
 *
 * Es lo que necesita el fondo de las tres maquinas. Pedirlos uno a uno con
 * np_tile_gfx_at() sale caro en un 68000: cada llamada multiplica dos enteros
 * de 32 bits y el 68000 no tiene esa instruccion, asi que el compilador se va
 * a una rutina en software. Aqui se multiplica una vez y el resto de la
 * columna se baja sumando el ancho del mapa. Fuera del nivel devuelve 0, igual
 * que np_tile_gfx_at(). */
void np_tile_gfx_column(const NpWorld *w, int32_t tx, int32_t ty,
                        uint16_t count, uint16_t *out)
{
    const NpLevel *level = w->level;
    const uint8_t *cell;
    uint16_t i = 0;
    int32_t primera = ty;

    if (tx < 0 || tx >= (int32_t)level->width) {
        for (; i < count; i++) out[i] = 0;
        return;
    }
    if (np_vista_iso) {
        for (; i < count; i++, ty++)
            out[i] = (ty < 0 || ty >= (int32_t)level->height)
                   ? 0 : level->fondo[ty * level->width + tx];
        return;
    }
    for (; i < count && ty < 0; i++, ty++)
        out[i] = 0;
    if (i < count && ty < (int32_t)level->height) {
        cell = level->cells + (int32_t)ty * level->cells_w + tx;
        for (; i < count && ty < (int32_t)level->height; i++, ty++) {
            out[i] = np_tile_gfx[*cell];
            cell += level->cells_w;
        }
    }
    for (; i < count; i++)
        out[i] = 0;
    /* Y las puertas ya abiertas, por el hueco que dejan. Se mira aparte -y
       solo si hay alguna abierta- para no meter una pregunta mas en el bucle
       de arriba, que es el que pinta el escenario entero en un 68000. */
    if (w->abiertos_n) {
        for (i = 0; i < count; i++) {
            int32_t fila = primera + (int32_t)i;
            if (np_tile_kind_at(level, tx, fila) != NP_TILE_LOCK) continue;
            if (np_tile_visto(w, tx, fila) == NP_TILE_EMPTY)
                out[i] = np_tile_gfx_vacio;
        }
    }
}

/* Un cerrojo frena como una pared hasta que se abre: en cuanto se abre,
   np_tile_visto ya lo devuelve como aire y aqui no llega. */
static int np_blocks(uint8_t kind)
{
    return kind == NP_TILE_SOLID || kind == NP_TILE_LOCK;
}

/* La escalera que hay en ese punto del mundo, o 0 si no hay ninguna.
 *
 * Las escaleras no frenan a nadie: se pasa por delante andando, igual que por
 * un decorado. Solo cuentan cuando el jugador decide subirse, y por eso no
 * aparecen en np_blocks ni en np_move_*. */
static uint8_t np_stair_at(const NpWorld *w, np_fix x, np_fix y)
{
    uint8_t kind = np_tile_visto(w, NP_F2I(x) >> NP_TILE_SHIFT,
                                   NP_F2I(y) >> NP_TILE_SHIFT);
    return (kind == NP_TILE_STAIR_R || kind == NP_TILE_STAIR_L) ? kind : 0;
}

/* Hay una liana en ese punto del mundo?
 *
 * Como las escaleras, no frena a nadie: se pasa por delante andando. Lo que
 * cambia es como se coge -en el aire tambien- y que se sube recta. */
static int np_climb_at(const NpWorld *w, np_fix x, np_fix y)
{
    return np_tile_visto(w, NP_F2I(x) >> NP_TILE_SHIFT,
                            NP_F2I(y) >> NP_TILE_SHIFT) == NP_TILE_CLIMB;
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

/* ------------------------------------------------------ la vista isometrica */
/*
 * En la vista de tipo filmation el mapa no es lo que se ve: es la **planta**
 * de la sala, y cada casilla ademas levanta. Lo que te frena no es el tipo de
 * la casilla de al lado sino lo alto que esta comparada con tus pies: seis
 * pixeles se suben andando y dieciseis hay que saltarlos. Con un solo numero
 * -el `alto:` de la leyenda- se escriben el suelo, el escalon, el cubo al que
 * hay que subirse y la pared, y el nivel se dibuja escribiendo alturas.
 */

/* Lo alto que esta una casilla, en 24.8. Fuera del mapa es pared, como en la
 * vista cenital: una sala es una caja cerrada. Un cerrojo ya abierto no
 * levanta nada, que es lo que hace que una puerta abierta se pueda cruzar. */
static np_fix np_celda_alto(const NpWorld *w, int32_t cx, int32_t cy)
{
    const NpLevel *lv = w->level;
    if (cx < 0 || cx >= (int32_t)lv->cells_w) return NP_I2F(255);
    if (cy < 0 || cy >= (int32_t)lv->cells_h) return NP_I2F(255);
    if (w->abiertos_n && np_tile_visto(w, cx, cy) == NP_TILE_EMPTY
        && np_tile_kind_at(lv, cx, cy) == NP_TILE_LOCK)
        return 0;
    return NP_I2F(np_tile_alto[lv->cells[cy * lv->cells_w + cx]]);
}

static int np_iso_choca(const NpWorld *w, int32_t cx, int32_t cy, np_fix pies)
{
    return np_celda_alto(w, cx, cy) > pies + NP_I2F(NP_ESCALON);
}

/* El suelo que hay debajo de una caja: la casilla mas alta que pisa. */
static np_fix np_iso_suelo(const NpWorld *w, np_fix x, np_fix y, int bw, int bh)
{
    int32_t cx0 = NP_F2I(x) >> NP_TILE_SHIFT;
    int32_t cx1 = NP_F2I(x + NP_I2F(bw) - 1) >> NP_TILE_SHIFT;
    int32_t cy0 = NP_F2I(y) >> NP_TILE_SHIFT;
    int32_t cy1 = NP_F2I(y + NP_I2F(bh) - 1) >> NP_TILE_SHIFT;
    np_fix alto = 0;
    int32_t cx, cy;
    for (cy = cy0; cy <= cy1; cy++)
        for (cx = cx0; cx <= cx1; cx++) {
            np_fix h = np_celda_alto(w, cx, cy);
            if (h > alto) alto = h;
        }
    return alto;
}

/* Andar por la planta, con el relieve delante.
 *
 * Es el np_move_x/np_move_y de siempre -a pasitos de medio tile, para no
 * atravesar nada- pero preguntando por altura en vez de por tipo de casilla, y
 * escrito una sola vez para los dos ejes: en la planta los dos ejes son
 * iguales, no hay uno que sea "el del suelo". `eje` a cero mueve en x y a uno
 * en y; `pies` es la altura a la que vas, que es lo que decide que te frena. */
static np_fix np_iso_move(const NpWorld *w, np_fix x, np_fix y,
                          int bw, int bh, np_fix paso, np_fix pies,
                          int eje, int *hit)
{
    np_fix *movil = eje ? &y : &x;
    int tam = eje ? bh : bw;
    int otro_tam = eje ? bw : bh;
    *hit = 0;
    while (paso != 0) {
        np_fix trozo = NP_CLAMP(paso, -NP_SUBSTEP, NP_SUBSTEP);
        np_fix quieto;
        int32_t a0, a1, c, borde;
        int choca = 0;
        paso -= trozo;
        *movil += trozo;
        quieto = eje ? x : y;
        a0 = NP_F2I(quieto) >> NP_TILE_SHIFT;
        a1 = NP_F2I(quieto + NP_I2F(otro_tam) - 1) >> NP_TILE_SHIFT;
        borde = (trozo > 0) ? (NP_F2I(*movil + NP_I2F(tam) - 1) >> NP_TILE_SHIFT)
                            : (NP_F2I(*movil) >> NP_TILE_SHIFT);
        for (c = a0; c <= a1; c++) {
            int32_t cx = eje ? c : borde;
            int32_t cy = eje ? borde : c;
            if (np_iso_choca(w, cx, cy, pies)) { choca = 1; break; }
        }
        if (choca) {
            *movil = (trozo > 0) ? NP_I2F(borde * NP_TILE - tam)
                                 : NP_I2F((borde + 1) * NP_TILE);
            *hit = 1;
            paso = 0;
        }
    }
    return *movil;
}

/* ------------------------------------------------------- movimiento y tiles */

static np_fix np_move_x(const NpWorld *w, np_fix x, np_fix y,
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
                if (np_blocks(np_tile_visto(w, tx, ty))) {
                    nx = NP_I2F(tx * NP_TILE - bw);
                    *hit = 1;
                    dx = 0;
                    break;
                }
            }
        } else {
            int32_t tx = NP_F2I(nx) >> NP_TILE_SHIFT;
            for (ty = ty0; ty <= ty1; ty++) {
                if (np_blocks(np_tile_visto(w, tx, ty))) {
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

static np_fix np_move_y(const NpWorld *w, np_fix x, np_fix y,
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
                uint8_t kind = np_tile_visto(w, tx, ty);
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
                if (np_blocks(np_tile_visto(w, tx, ty))) {
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
static int np_box_touches(const NpWorld *w, np_fix x, np_fix y, int bw, int bh,
                          uint8_t kind)
{
    int32_t tx0 = NP_F2I(x) >> NP_TILE_SHIFT;
    int32_t tx1 = NP_F2I(x + NP_I2F(bw) - 1) >> NP_TILE_SHIFT;
    int32_t ty0 = NP_F2I(y) >> NP_TILE_SHIFT;
    int32_t ty1 = NP_F2I(y + NP_I2F(bh) - 1) >> NP_TILE_SHIFT;
    int32_t tx, ty;
    for (ty = ty0; ty <= ty1; ty++)
        for (tx = tx0; tx <= tx1; tx++)
            if (np_tile_visto(w, tx, ty) == kind) return 1;
    return 0;
}

/* --------------------------------------------------------- actores y animos */

const NpActorDef *np_entity_def(const NpEntity *e)
{
    if (e->kind == NP_KIND_ENEMY) return &np_enemies[e->def].actor;
    if (e->kind == NP_KIND_SHOT) return &np_player_def.attack.actor;
    if (e->kind == NP_KIND_PLATFORM) return &np_platforms[e->def].actor;
    if (e->kind == NP_KIND_BREAKABLE) return &np_breakables[e->def].actor;
    if (e->kind == NP_KIND_SUBSHOT) return &np_subs[e->def].actor;
    if (e->kind == NP_KIND_MELEE) return &np_player_def.attack.actor;
    if (e->kind == NP_KIND_ENEMY_SHOT) return &np_enemy_shots[e->def].actor;
    if (e->kind == NP_KIND_PRISONER) return &np_prisoners[e->def].actor;
    if (e->kind == NP_KIND_GENERATOR) return &np_generators[e->def].actor;
    if (e->kind == NP_KIND_BLOQUE) return &np_bloques[e->def].actor;
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
static void np_tenaces_siguen(NpWorld *w, int32_t dx, int32_t dy);
static void np_cambio_de_pantalla(NpWorld *w);
static int np_en_la_sala(const NpWorld *w, const NpEntity *e);

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
    /* y con ellas se van los cubos de la sala, que se vuelven a montar en
       cuanto la camara diga en cual estamos */
    w->bloques_n = 0;
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
        e->knock = 0;
        e->golpeado = 0;
        e->altura = 0;
        e->valtura = 0;
        /* El luchador empieza de cero: sin fase, sin tambaleo y sin haber
           tocado a nadie. Sin esto, al volver a empezar el nivel un hueco de
           la lista conservaria la fase del que estaba antes -y saldria
           pegando, o tumbado- que es justo lo que caza la prueba de paridad:
           el preview crea las entidades nuevas y no arrastraria nada. */
        e->fase = NP_LUCHA_IR;
        e->tocado = 0;
        e->aturdido = 0;
        def = np_entity_def(e);
        /* En la isometrica todo se apoya en el relieve: una llave puesta encima
           de un cubo sale encima del cubo y no flotando sobre su sombra. */
        if (np_vista_iso)
            e->altura = np_iso_suelo(w, e->x, e->y, def->box_w, def->box_h);
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
        } else if (e->kind == NP_KIND_PRISONER) {
            e->health = 1;
            e->timer = 0;            /* cero = sigue atado */
        } else if (e->kind == NP_KIND_GENERATOR) {
            const NpGeneratorDef *gd = &np_generators[e->def];
            e->health = gd->health;
            e->timer = 0;             /* el primer bicho tarda lo mismo que los demas */
        } else {
            e->health = 1;
        }
    }
}

/* La caja del jugador ahora mismo. Agachado, el techo baja `crouch_drop`
 * pixeles y los pies se quedan donde estan: lo que pasa por encima deja de
 * tocarte y el latigo sale a la altura de la rodilla.
 *
 * Va por aqui, y no bajando p->y, para que el dibujo se coloque igual que
 * siempre en las seis maquinas: todas pintan al jugador en p->y - box_y, y el
 * fotograma de agachado ya viene dibujado mas abajo dentro del cuadro. */
static np_fix np_player_top(const NpPlayer *p)
{
    return p->crouch ? p->y + NP_I2F(np_player_def.crouch_drop) : p->y;
}

static int16_t np_player_height(const NpPlayer *p)
{
    const NpActorDef *a = &np_player_def.actor;
    return p->crouch ? (int16_t)(a->box_h - np_player_def.crouch_drop) : a->box_h;
}

/* Quita de la lista el dibujo del latigo, si lo habia. Se llama en cuanto el
   golpe deja de hacer dano, y tambien al recibir uno o al morir: si no, el
   latigo se quedaria colgado en el aire mientras el jugador sale despedido. */
static void np_whip_off(NpWorld *w, uint8_t quien)
{
    NpPlayer *p = &w->players[quien];
    if (p->whip && p->whip <= NP_MAX_ENTITIES)
        w->entities[p->whip - 1].active = 0;
    p->whip = 0;
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
    p->wear_timer = 0;          /* la cuenta atras de `desgaste:` empieza de cero */
    p->altura = 0;              /* con los pies en el suelo */
    p->valtura = 0;
    p->combo_link = 0;          /* la serie de golpes, desde el primero */
    p->combo_timer = 0;
    p->grab = 0;                /* y sin nadie agarrado */
    p->grab_timer = 0;
    /* y sin carrera ni golpe fuerte a medias */
    p->fuerte = 0;
    p->carrera = 0;
    p->toque = 0;
    p->toque_dir = 0;
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
    p->crouch = 0;
    np_whip_off(w, quien);
    p->stairs = 0;
    p->trepa = 0;
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
    /* La bolsa y las puertas abiertas son de este nivel: empezar otro es
       empezarlo de cero, con las manos vacias y todo cerrado. */
    for (i = 0; i < NP_BOLSA; i++) w->bolsa[i] = 0;
    w->abiertos_n = 0;
    w->sub = 0;                 /* se empieza con la primera arma secundaria */
    w->boss_health = 0;
    w->boss_max = 0;
    w->time_left = (uint16_t)(np_time_limit * 60);
    w->state = NP_STATE_PLAY;
    w->state_timer = 0;
    np_spawn_entities(w);
    /* Nadie ha estado nunca en la sala 0xFFFF: con eso la camara ve un cambio
       de sala en su primera vuelta y monta los cubos de la de verdad. */
    w->sala_x = 0xFFFF;
    w->sala_y = 0xFFFF;
    np_camera_update(w);
    /* La pantalla de salida es en la que se empieza: nadie "entra" detras de
       ti en el primer frame de un nivel. */
    w->pantalla_x = (uint16_t)(w->cam_x / NP_SCREEN_W);
    w->pantalla_y = (uint16_t)(w->cam_y / NP_SCREEN_H);
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
    p->attack_timer = 0;
    np_whip_off(w, quien);      /* muriendo no se pega, y el latigo no se queda */
    p->anim = NP_ANIM_HURT;
    p->anim_frame = 0;
    if (!np_players_up(w)) {
        w->state = NP_STATE_DYING;
        w->state_timer = NP_DYING_TIME;
    }
}

/* ------------------------------------------------------ la vista cenital */
/*
 * Con `vista: cenital` el juego se mira desde arriba, como los de comando: no
 * hay gravedad ni suelo, se anda en ocho direcciones y se dispara hacia donde
 * se mira. Es un **segundo modo de movimiento**, como las escaleras, pero para
 * todo el juego: por eso el jugador tiene aqui su propia actualizacion en vez
 * de llenar la de siempre de condiciones, y la de vista lateral se queda
 * exactamente como estaba.
 *
 * La mirada son ocho direcciones, empezando por la derecha y girando en el
 * sentido del reloj (la y crece hacia abajo, como en la pantalla).
 */
static const int8_t np_aim_x[8] = { 1, 1, 0, -1, -1, -1,  0,  1 };
static const int8_t np_aim_y[8] = { 0, 1, 1,  1,  0, -1, -1, -1 };

/* En diagonal se anda a 0,707 de la velocidad (181/256): sin esto las
   diagonales serian un 41% mas rapidas y todo el mundo iria en diagonal. */
#define NP_DIAGONAL 181

static uint8_t np_aim_de(int dx, int dy)
{
    if (dx > 0) return (uint8_t)(dy > 0 ? 1 : (dy < 0 ? 7 : 0));
    if (dx < 0) return (uint8_t)(dy > 0 ? 3 : (dy < 0 ? 5 : 4));
    return (uint8_t)(dy > 0 ? 2 : 6);
}

/* La velocidad de un eje, ya corregida si se va en diagonal. */
static np_fix np_paso_cenital(np_fix velocidad, int eje, int diagonal)
{
    np_fix v = diagonal ? (np_fix)((velocidad * NP_DIAGONAL) >> 8) : velocidad;
    return (np_fix)(eje * v);
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
    if (np_vista_cenital) {
        /* mirando desde arriba no hay "hacia arriba": el empujon va al reves
           de donde miras, que es de donde viene el golpe */
        p->vx = (np_fix)(-np_aim_x[p->aim] * np_player_def.knockback);
        p->vy = (np_fix)(-np_aim_y[p->aim] * np_player_def.knockback);
    } else {
        p->vy = -np_player_def.bounce / 2;
        p->vx = p->facing ? -np_player_def.knockback : np_player_def.knockback;
    }
    /* El aturdimiento es lo que hace que el golpe duela de verdad: mientras
       dura no se frena ni se cambia de sentido, asi que el empujon te lleva
       donde te lleve. Con `aturdido: 0` se recupera el control al momento. */
    p->stun = np_player_def.stun;
    p->attack_timer = 0;
    np_whip_off(w, quien);
    p->stairs = 0;              /* un golpe te tira de la escalera */
    p->trepa = 0;               /* y de la liana */
}

/* La vida que se gasta sola.
 *
 * Con `desgaste:` puesto, cada tantos frames se va un punto sin que nadie te
 * toque. Es la mecanica de Gauntlet y cambia el juego entero: ya no se puede
 * esperar a que pase el bicho, hay que ir a por la comida. El ultimo punto
 * mata, igual que un golpe, y va por el mismo sitio (np_player_hurt) para que
 * la muerte se vea y suene igual.
 *
 * No hay invulnerabilidad que valga contra esto: se resta a mano y no por
 * np_player_hurt, que rebota en `invuln` y dejaria la cuenta atras parada
 * cada vez que te rozan. */
static void np_player_wear(NpWorld *w, uint8_t quien)
{
    NpPlayer *p = &w->players[quien];
    if (!np_player_def.wear || !p->playing || p->dying) return;
    if (w->state != NP_STATE_PLAY) return;
    if (++p->wear_timer < np_player_def.wear) return;
    p->wear_timer = 0;
    if (p->health > 1) {
        p->health--;
        return;
    }
    p->health = 0;
    np_player_die(w, quien);
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
    /* Los cubos de la sala ocupan el final de la lista y no son huecos libres
       aunque lo parezcan: buscar aqui pararia justo antes de ellos. */
    uint8_t tope = (uint8_t)(NP_MAX_ENTITIES - w->bloques_n);
    uint8_t i;
    for (i = 0; i < tope; i++) {
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
    /* Le has pegado tu primero: se le corta el golpe y pierde el turno. Es la
       otra mitad de que la pelea tenga ritmo -la primera es que se le vea
       venir-: quien se adelanta manda. */
    e->fase = NP_LUCHA_IR;
    if (e->health > damage) {
        e->health = (uint8_t)(e->health - damage);
        e->hurt = 20;
        /* Y se tambalea: unos frames sin decidir nada. Es el hueco por el que
           entra el golpe siguiente, o sea lo que hace que una serie exista. */
        if (np_vista_cinta) e->aturdido = NP_ATURDE;
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
/* Un generador aguanta unos cuantos tiros y se acabo. No suelta nada: lo que
   suelta es lo que ya haya sacado, y eso sigue vivo. */
static int np_hit_generator(NpWorld *w, NpEntity *e, uint8_t damage)
{
    const NpGeneratorDef *d = &np_generators[e->def];
    if (e->health > damage) {
        e->health = (uint8_t)(e->health - damage);
        e->hurt = 10;
        w->sfx |= NP_SFX_BREAK;
        return 1;
    }
    w->score += d->score;
    w->sfx |= NP_SFX_BREAK;
    e->active = 0;
    return 1;
}

static int np_hit_entity(NpWorld *w, NpEntity *e, uint8_t damage)
{
    if (e->kind == NP_KIND_ENEMY) return np_hit_enemy(w, e, damage);
    if (e->kind == NP_KIND_BREAKABLE) return np_hit_breakable(w, e, damage);
    if (e->kind == NP_KIND_GENERATOR) return np_hit_generator(w, e, damage);
    return 0;
}

/* El alcance del arma ahora mismo: el de siempre mas lo que hayan sumado las
   mejoras. Es una cuenta y no un campo guardado para que no haya dos verdades
   que puedan separarse. */
static uint8_t np_attack_level(const NpPlayer *p)
{
    const NpAttackDef *at = &np_player_def.attack;
    return p->power < at->levels ? p->power : at->levels;
}

/* Esto es una patada voladora y no un puno?
 *
 * Con `patada:` puesto, pegar **sin pisar suelo** es otro golpe: llega mas
 * lejos y hace mas dano. No hay boton nuevo ni hay que aprenderse nada: es el
 * mismo de siempre, y lo que cambia lo que sale es si estabas en el aire. De
 * ahi sale el repertorio de un juego de kung-fu: el puno para el que tienes
 * delante y la patada para el que viene. */
static int np_es_patada(const NpPlayer *p)
{
    return np_player_def.attack.kick_range && !p->on_ground
           && !p->stairs && !p->trepa;
}

static uint16_t np_attack_range(const NpPlayer *p)
{
    const NpAttackDef *at = &np_player_def.attack;
    if (np_es_patada(p)) return at->kick_range;
    return (uint16_t)(at->range + np_attack_level(p) * at->range_step);
}

static void np_player_attack(NpWorld *w, uint8_t quien)
{
    const NpAttackDef *at = &np_player_def.attack;
    NpPlayer *p = &w->players[quien];
    const NpActorDef *pa = &np_player_def.actor;

    if (at->kind == NP_ATTACK_NONE || p->attack_cd) return;
    p->attack_cd = at->cooldown;
    w->sfx |= NP_SFX_SHOOT;

    /* Golpe nuevo, cuenta nueva: lo que ya haya tocado el anterior vuelve a
       poder recibir. Sin esto una serie de tres solo acertaria el primero. */
    if (at->kind == NP_ATTACK_MELEE) {
        uint8_t i;
        for (i = 0; i < w->entity_count; i++)
            w->entities[i].golpeado &= (uint8_t)~(1u << quien);
    }

    /* La serie: si todavia queda ventana, este golpe es el siguiente de la
       tanda; si no, se empieza otra vez por el primero. */
    if (at->kind == NP_ATTACK_MELEE && at->combo > 1) {
        if (p->combo_timer && p->combo_link + 1 < at->combo) p->combo_link++;
        else p->combo_link = 0;
        p->combo_timer = at->combo_window;
    }

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
        if (np_vista_cenital) {
            /* mirando desde arriba el disparo sale por donde miras, en las
               ocho direcciones, y desde el centro del jugador */
            int ax = np_aim_x[p->aim], ay = np_aim_y[p->aim];
            int diagonal = (ax && ay);
            e->x = p->x + NP_I2F((pa->box_w - at->actor.box_w) / 2
                                 + ax * (pa->box_w / 2 + 1));
            e->y = p->y + NP_I2F((pa->box_h - at->actor.box_h) / 2
                                 + ay * (pa->box_h / 2 + 1));
            e->vx = np_paso_cenital(at->speed, ax, diagonal);
            e->vy = np_paso_cenital(at->speed, ay, diagonal);
        } else {
            /* sale a la altura del centro del jugador y por el lado que mira */
            e->x = p->x + NP_I2F(p->facing ? pa->box_w : -at->actor.box_w);
            e->y = np_player_top(p)
                 + NP_I2F((np_player_height(p) - at->actor.box_h) / 2);
            e->vx = p->facing ? at->speed : -at->speed;
            e->vy = 0;
        }
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
/* Cuantas tiradas de esta arma van por el aire ahora mismo. */
static uint8_t np_subs_volando(const NpWorld *w, uint8_t arma)
{
    uint8_t i, cuantas = 0;
    for (i = 0; i < w->entity_count; i++)
        if (w->entities[i].active && w->entities[i].kind == NP_KIND_SUBSHOT
            && w->entities[i].def == arma)
            cuantas++;
    return cuantas;
}

static void np_player_sub(NpWorld *w, uint8_t quien)
{
    const NpSubDef *sb = &np_subs[w->sub];
    NpPlayer *p = &w->players[quien];
    const NpActorDef *pa = &np_player_def.actor;
    int hueco;

    if (!np_sub_count || sb->kind == NP_SUB_NONE || p->attack_cd) return;
    if (w->hearts < sb->cost) return;         /* sin municion no sale nada */
    /* `a_la_vez`: con una sola en el aire hay que esperar a que caiga, que es
       lo clasico; con tres sale el "triple" de toda la vida. */
    if (sb->at_once && np_subs_volando(w, w->sub) >= sb->at_once) return;
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
        e->def = w->sub;          /* se queda con el arma con la que salio */
        e->facing = p->facing;
        if (np_vista_cenital) {
            /* la granada sale por donde miras y vuela recta hasta agotar su
               alcance: desde arriba no hay arco que valga, porque no hay
               "arriba" al que tirar */
            int ax = np_aim_x[p->aim], ay = np_aim_y[p->aim];
            int diagonal = (ax && ay);
            e->x = p->x + NP_I2F((pa->box_w - sb->actor.box_w) / 2
                                 + ax * (pa->box_w / 2 + 1));
            e->y = p->y + NP_I2F((pa->box_h - sb->actor.box_h) / 2
                                 + ay * (pa->box_h / 2 + 1));
            e->vx = np_paso_cenital(sb->speed, ax, diagonal);
            e->vy = np_paso_cenital(sb->speed, ay, diagonal);
        } else {
            e->x = p->x + NP_I2F(p->facing ? pa->box_w : -sb->actor.box_w);
            e->y = np_player_top(p)
                 + NP_I2F((np_player_height(p) - sb->actor.box_h) / 2);
            e->vx = p->facing ? sb->speed : -sb->speed;
            e->vy = (sb->kind == NP_SUB_ARC) ? -sb->jump : 0;
        }
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
    const NpSubDef *sb = &np_subs[e->def];
    const NpActorDef *a = &sb->actor;
    uint8_t i;
    int hit_x = 0, hit_down = 0, hit_up = 0;

    if (!e->vida) { e->active = 0; return; }
    e->vida--;
    /* El arco es cosa de la vista lateral: es tirar por encima de una pared.
       Mirando desde arriba no hay "por encima", asi que vuela recto. */
    if (sb->kind == NP_SUB_ARC && !np_vista_cenital) {
        e->vy += sb->gravity;
        if (e->vy > NP_ENTITY_FALL) e->vy = NP_ENTITY_FALL;
    }
    e->x = np_move_x(w, e->x, e->y, a->box_w, a->box_h, e->vx, &hit_x);
    if (hit_x) { e->active = 0; return; }
    if (e->vy) {
        e->y = np_move_y(w, e->x, e->y, a->box_w, a->box_h, e->vy, 1,
                         &hit_down, &hit_up);
        if (hit_down || hit_up) { e->active = 0; return; }
    }

    for (i = 0; i < w->entity_count; i++) {
        NpEntity *otra = &w->entities[i];
        const NpActorDef *ea;
        if (!otra->active) continue;
        if (otra->kind == NP_KIND_PRISONER) {
            ea = np_entity_def(otra);
            if (!np_boxes_overlap(e->x, e->y, a->box_w, a->box_h,
                                  otra->x, otra->y, ea->box_w, ea->box_h))
                continue;
            if (!otra->timer) {
                otra->active = 0;
                w->sfx |= NP_SFX_HURT;
            }
            e->active = 0;
            return;
        }
        if (otra->kind != NP_KIND_ENEMY && otra->kind != NP_KIND_BREAKABLE
            && otra->kind != NP_KIND_GENERATOR) continue;
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
    e->x = np_move_x(w, e->x, e->y, a->box_w, a->box_h, e->vx, &hit_x);
    if (hit_x) { e->active = 0; return; }
    if (np_vista_cenital && e->vy) {
        /* mirando desde arriba el disparo tambien vuela en vertical, y una
           pared lo para igual que en horizontal */
        int arriba = 0, abajo = 0;
        e->y = np_move_y(w, e->x, e->y, a->box_w, a->box_h, e->vy, 1,
                         &abajo, &arriba);
        if (abajo || arriba) { e->active = 0; return; }
    }

    for (i = 0; i < w->entity_count; i++) {
        NpEntity *otra = &w->entities[i];
        const NpActorDef *ea;
        if (!otra->active) continue;
        if (otra->kind == NP_KIND_PRISONER) {
            /* Al prisionero no hay que dispararle: si le das, se acabo y no
               suma nada. Es el precio de disparar a lo loco. */
            ea = np_entity_def(otra);
            if (!np_boxes_overlap(e->x, e->y, a->box_w, a->box_h,
                                  otra->x, otra->y, ea->box_w, ea->box_h))
                continue;
            if (!otra->timer) {                  /* atado: se pierde */
                otra->active = 0;
                w->sfx |= NP_SFX_HURT;
            }
            e->active = 0;
            return;
        }
        if (otra->kind != NP_KIND_ENEMY && otra->kind != NP_KIND_BREAKABLE
            && otra->kind != NP_KIND_GENERATOR) continue;
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

/* El latigo que se ve.
 *
 * El dano lo sigue haciendo la caja de np_melee_update: esto es solo el
 * dibujo. Y es una entidad mas de la lista, no un caso aparte, porque asi lo
 * pintan las seis maquinas y el preview **sin tocar una linea** (todas
 * recorren las entidades y le piden el dibujo a np_entity_def), y ademas entra
 * en el hash de la traza, o sea que la paridad con el preview lo comprueba
 * frame a frame.
 *
 * Se coloca pegado a la caja del jugador y ocupa el fotograma entero. Mirando
 * a la izquierda el dibujo sale espejado, asi que ahi hay que restar el ancho
 * completo: el latigo empieza entonces por el borde derecho del fotograma, que
 * es justo el costado del jugador. Con eso cuadra sin depender del nivel de
 * mejora.
 *
 * El fotograma es el nivel del arma: 0 el latigo de serie, 1 y 2 los
 * mejorados. Asi la mejora se **ve**, que hasta ahora solo se notaba en que
 * llegabas un poco mas lejos. */
static void np_whip_on(NpWorld *w, uint8_t quien)
{
    const NpAttackDef *at = &np_player_def.attack;
    const NpActorDef *pa = &np_player_def.actor;
    NpPlayer *p = &w->players[quien];
    NpEntity *e;

    if (!at->fx) return;                  /* el ataque no trae dibujo */
    if (!p->whip) {
        int hueco = np_hueco_libre(w);
        if (hueco < 0) return;            /* no cabe: se pega sin verse */
        p->whip = (uint8_t)(hueco + 1);
        e = &w->entities[hueco];
        e->active = 1;
        e->kind = NP_KIND_MELEE;
        e->def = 0;
        e->vx = 0;
        e->vy = 0;
        e->home_x = 0;
        e->home_y = 0;
        e->vida = 0;
        e->timer = 0;
        e->health = 1;
        e->hurt = 0;
        e->anim = NP_ANIM_IDLE;
        e->anim_timer = 0;
    }
    e = &w->entities[p->whip - 1];
    e->facing = p->facing;
    e->x = p->facing ? p->x + NP_I2F(pa->box_w)
                     : p->x - NP_I2F(at->actor.cols * NP_TILE);
    e->y = np_player_top(p);          /* agachado, el latigo va por abajo */
    e->anim_frame = np_attack_level(p);
}

/* El golpe cuerpo a cuerpo: mientras dura, una caja delante del jugador. */
/* ------------------------------------------------ la serie de golpes */
/*
 * Los juegos de tortas no van de apretar el boton, van de encadenar: puno,
 * puno y remate. Lo que lo hace jugable es que el ultimo pega mas fuerte y
 * **tumba**, asi que quien encadena se quita al matón de encima y quien
 * machaca el boton se queda a medias.
 *
 * `combo_link` dice por cual va y `combo_timer` cuanto queda para que la serie
 * se corte. Con `combo: 1` -lo normal fuera de este genero- no hay serie y
 * estas dos funciones devuelven lo de siempre.
 */
/* ¿Hay alguien a tiro por delante? ¿Y por detras? Son las dos preguntas del
 * codazo: en un juego de tortas te rodean, y girarse a mano mientras tres te
 * pegan es imposible. El codo lo resuelve solo, y solo cuando hace falta: si
 * hay alguien delante, el golpe va delante, como siempre.
 *
 * Se mira una franja del ancho del golpe a cada lado y a la altura de la caja,
 * asi que uno que este en otra profundidad no cuenta -no le llegarias-. */
static int np_hay_a_ese_lado(const NpWorld *w, uint8_t quien, int derecha)
{
    const NpPlayer *p = &w->players[quien];
    const NpActorDef *pa = &np_player_def.actor;
    uint16_t alcance = np_attack_range(p);
    np_fix gx = derecha ? p->x + NP_I2F(pa->box_w) : p->x - NP_I2F(alcance);
    uint8_t i;
    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
        const NpActorDef *ea;
        if (!e->active || e->kind != NP_KIND_ENEMY || e->knock) continue;
        ea = np_entity_def(e);
        if (np_boxes_overlap(gx, np_player_top(p), alcance,
                             np_player_height(p), e->x, e->y,
                             ea->box_w, ea->box_h))
            return 1;
    }
    return 0;
}

static int np_hay_delante(const NpWorld *w, uint8_t quien)
{
    return np_hay_a_ese_lado(w, quien, w->players[quien].facing);
}

static int np_hay_detras(const NpWorld *w, uint8_t quien)
{
    return np_hay_a_ese_lado(w, quien, !w->players[quien].facing);
}

/* Los dos golpes que valen por un remate: la patada en salto y el hombro en
 * carrera. Los dos cuestan algo -uno te deja en el aire sin poder corregir, el
 * otro te obliga a cruzar la calle en linea recta-, y por eso pagan como el
 * ultimo de la serie: pegan mas y tumban. Es lo que convierte un grupo de tres
 * en algo que se puede romper por un lado en vez de aguantar de frente. */
static int np_es_remate(const NpPlayer *p)
{
    const NpAttackDef *at = &np_player_def.attack;
    if (np_vista_cinta && p->fuerte) return 1;
    return at->combo > 1 && p->combo_link + 1 >= at->combo;
}

static uint8_t np_golpe_dano(const NpPlayer *p)
{
    const NpAttackDef *at = &np_player_def.attack;
    if (np_es_patada(p) && at->kick_damage) return at->kick_damage;
    if (np_es_remate(p) && at->finish_damage) return at->finish_damage;
    return at->damage;
}

/* Al que cobra el remate lo tumba: sale despedido hacia donde miras y se queda
   unos frames en el suelo, sin gobernarse y sin hacer dano al tocarte. */
static void np_derribar(const NpPlayer *p, NpEntity *e)
{
    const NpAttackDef *at = &np_player_def.attack;
    if (!np_es_remate(p) || !at->finish_stun) return;
    if (e->kind != NP_KIND_ENEMY) return;
    e->knock = at->finish_stun;
    e->vx = p->facing ? at->finish_push : (np_fix)(-at->finish_push);
    e->vy = 0;
}

static void np_melee_update(NpWorld *w, uint8_t quien)
{
    const NpAttackDef *at = &np_player_def.attack;
    const NpActorDef *pa = &np_player_def.actor;
    NpPlayer *p = &w->players[quien];
    np_fix gx, gy;
    uint16_t alcance, alto;
    uint8_t i, fase_antes;

    if (!p->attack_timer) {
        p->fuerte = 0;          /* el golpe fuerte vale para su golpe y ya */
        np_whip_off(w, quien);
        return;
    }
    p->attack_timer--;
    if (at->kind != NP_ATTACK_MELEE) return;   /* un disparo no pega de cerca */
    /* Los primeros `preparacion:` frames el golpe se ve pero no toca: el brazo
       todavia esta saliendo. Es la diferencia entre medir la distancia y
       machacar el boton. El latigo aparece justo cuando empieza a hacer dano,
       asi que lo que se ve en pantalla es exactamente lo que pega. */
    if (p->attack_timer + at->windup >= at->duration) {
        np_whip_off(w, quien);
        return;
    }
    np_whip_on(w, quien);
    alcance = np_attack_range(p);
    gx = p->facing ? p->x + NP_I2F(pa->box_w) : p->x - NP_I2F(alcance);
    gy = np_player_top(p);
    alto = np_player_height(p);
    /* La patada en salto **llega al suelo**: la caja se estira desde donde
       estas hasta la linea del suelo. Sin esto saltar seria la forma de no
       pegarle a nadie -el dibujo sube y la caja con el- y la patada, que es la
       manera de meterse en un grupo, no existiria. */
    if (np_vista_cinta && p->altura > 0)
        alto = (uint16_t)(alto + NP_F2I(p->altura));
    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        const NpActorDef *ea;
        if (!e->active) continue;
        if (e->kind != NP_KIND_ENEMY && e->kind != NP_KIND_BREAKABLE
            && e->kind != NP_KIND_GENERATOR) continue;
        /* A quien ya ha tocado este golpe no se le toca otra vez. La caja se
           queda puesta varios frames y acertaria en todos: sin esto, un solo
           ataque se llevaba por delante a un enemigo de cinco de vida. Lo que
           se mira es **este** golpe y no el parpadeo, para que el segundo de
           una serie pueda acertar al que aun parpadea del primero. */
        if (e->golpeado & (1u << quien)) continue;
        ea = np_entity_def(e);
        if (!np_boxes_overlap(gx, gy, alcance, alto,
                              e->x, e->y, ea->box_w, ea->box_h))
            continue;
        e->golpeado |= (uint8_t)(1u << quien);
        fase_antes = e->fase;
        np_hit_entity(w, e, np_golpe_dano(p));
        /* El que **ya ha empezado a soltar el golpe** no se para con un puno
           normal: hay que apartarse, saltarle por encima o gastarle algo
           fuerte. Sin esto, prepararse seria un adorno -bastaria con pegar sin
           parar para que nadie llegara a soltar nada- y la pelea volveria a
           ser machacar el boton. */
        if (np_vista_cinta && e->active && fase_antes == NP_LUCHA_PREPARAR
            && !np_es_remate(p)) {
            e->fase = NP_LUCHA_PREPARAR;
            e->aturdido = 0;
        }
        /* La parada del impacto. El remate para mas: es el golpe que cuenta y
           tiene que notarse en la mano. Solo en la vista de cinta, que es
           donde el genero vive de esto; en un plataformas parar el mundo cada
           vez que pisas a una seta seria un juego a tirones. */
        if (np_vista_cinta) {
            w->congelado = np_es_remate(p) ? NP_CONGELADO_REMATE : NP_CONGELADO;
            /* Y con el remate, la pantalla tiembla. Va aqui y no en
               np_derribar a proposito: si colgara del derribo, el remate que
               **mata** -que es el que mas se celebra- no sacudiria nada,
               porque a un muerto ya no hay a quien tumbar. */
            if (np_es_remate(p) && e->kind == NP_KIND_ENEMY)
                w->sacudida = NP_SACUDIDA;
        }
        /* y el empujon del tambaleo, hacia donde miras: un golpe mueve al que
           lo cobra, aunque sea un paso */
        if (np_vista_cinta && e->active && e->aturdido) {
            e->vx = p->facing ? NP_I2F(1) : -NP_I2F(1);
            e->vy = 0;
        }
        if (e->active) np_derribar(p, e);
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
/* Frames que un objeto recien soltado no se deja coger. Poco mas de medio
   segundo: lo justo para poder dejarlo y apartarse. */
#define NP_GRACIA_SOLTAR 40

/* ------------------------------------------------------------- la bolsa */
/*
 * Lo que llevas encima, que en una aventura de las de Dizzy es medio juego: se
 * cargan tres cosas a la vez, se cogen tocandolas y se sueltan con el boton, y
 * lo que te para no es un bicho sino una puerta que pide una llave que dejaste
 * tres pantallas atras.
 *
 * Cada hueco guarda el objeto **mas uno**, para que el cero sea "vacio". Se
 * llena por delante y se suelta por delante: la bolsa gira, como en los
 * originales, y por eso el orden en que coges las cosas importa.
 */
static int np_bolsa_meter(NpWorld *w, uint8_t objeto)
{
    uint8_t i;
    for (i = 0; i < NP_BOLSA; i++) {
        if (w->bolsa[i]) continue;
        w->bolsa[i] = (uint16_t)(objeto + 1);
        return 1;
    }
    return 0;                       /* llena: el objeto se queda en el suelo */
}

uint8_t np_bolsa_cuantos(const NpWorld *w)
{
    uint8_t i, n = 0;
    for (i = 0; i < NP_BOLSA; i++) if (w->bolsa[i]) n++;
    return n;
}

/* Saca el primero de la bolsa y corre los demas hacia delante. Devuelve el
   objeto (mas uno) o cero si no llevaba nada. */
static uint16_t np_bolsa_sacar(NpWorld *w)
{
    uint16_t primero = w->bolsa[0];
    uint8_t i;
    if (!primero) return 0;
    for (i = 1; i < NP_BOLSA; i++) w->bolsa[i - 1] = w->bolsa[i];
    w->bolsa[NP_BOLSA - 1] = 0;
    return primero;
}

/* ¿Llevas esto? Devuelve el hueco mas uno, o cero. */
static uint8_t np_bolsa_busca(const NpWorld *w, uint8_t objeto)
{
    uint8_t i;
    for (i = 0; i < NP_BOLSA; i++)
        if (w->bolsa[i] == (uint16_t)(objeto + 1)) return (uint8_t)(i + 1);
    return 0;
}

/* Soltar lo primero de la bolsa: cae a tus pies y ahi se queda.
 *
 * Sale con unos frames de gracia (`timer`) para que no lo vuelvas a coger en el
 * mismo sitio donde lo acabas de dejar: sin eso, soltar y coger serian el mismo
 * boton y no habria forma de dejar nada en el suelo.
 */
static void np_soltar_objeto(NpWorld *w, uint8_t quien)
{
    NpPlayer *p = &w->players[quien];
    const NpActorDef *pa = &np_player_def.actor;
    uint16_t objeto = w->bolsa[0];
    const NpItemDef *d;
    const NpActorDef *ia;
    int hueco;
    NpEntity *e;

    if (!objeto) return;
    hueco = np_hueco_libre(w);
    if (hueco < 0) return;              /* no cabe: mejor seguir llevandolo */
    np_bolsa_sacar(w);
    objeto--;
    d = &np_items[objeto];
    ia = &d->actor;
    e = &w->entities[hueco];
    e->active = 1;
    e->kind = NP_KIND_ITEM;
    e->def = objeto;
    e->x = p->x + NP_I2F((int32_t)(pa->box_w - ia->box_w) / 2);
    e->y = p->y + NP_I2F((int32_t)pa->box_h - (int32_t)ia->box_h);
    e->home_x = e->x;
    e->home_y = e->y;
    e->vx = 0;
    e->vy = 0;
    e->health = 1;
    e->hurt = 0;
    e->knock = 0;
    e->golpeado = 0;
    e->altura = 0;
    e->valtura = 0;
    e->vida = 0;
    e->timer = NP_GRACIA_SOLTAR;
    e->anim = NP_ANIM_IDLE;
    e->anim_frame = 0;
    e->anim_timer = 0;
    w->sfx |= NP_SFX_COIN;
}

static void np_player_action(NpWorld *w, uint8_t quien, uint16_t input)
{
    NpPlayer *p = &w->players[quien];
    if (p->attack_cd) p->attack_cd--;
    /* En una aventura el boton no pega: **suelta lo que llevas**. Es lo unico
       que se hace con las manos en un Dizzy, y por eso se queda con el boton
       entero. Con `np_bolsa_activa` a cero -cualquier otro juego- esto no
       existe y el boton hace lo de siempre. */
    if (np_bolsa_activa) {
        if ((input & NP_IN_ACTION) && !(w->prev_input[quien] & NP_IN_ACTION))
            np_soltar_objeto(w, quien);
        return;
    }
    if ((input & NP_IN_ACTION) && !(w->prev_input[quien] & NP_IN_ACTION)) {
        /* arriba + accion tira el arma secundaria; el boton a secas, el
           ataque de siempre. Si no hay arma o no queda municion, se pega. */
        if ((input & NP_IN_UP) && np_sub_count
            && w->hearts >= np_subs[w->sub].cost)
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
        kind = np_stair_at(w, np_ref_x(p, a), np_ref_y(p, a));
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
    if (!np_stair_at(w, np_ref_x(p, a), np_ref_y(p, a))) {
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

/* --- las lianas -----------------------------------------------------------
 *
 * Una liana no es una escalera, y la diferencia es el genero entero. A una
 * escalera se sube desde el suelo y va en diagonal, de un piso al de arriba. A
 * una liana **te agarras en el aire**: saltas, la coges al vuelo y te quedas
 * colgado donde la hayas cogido. Desde ahi se sube, se baja, se salta a donde
 * sea y se suelta para caer. De eso viven las torres de Bruce Lee: el camino
 * no es un pasillo con escalones, es un salto de liana en liana.
 */

/* Agarrarse. Devuelve 1 si se ha agarrado.
 *
 * Basta con que el punto de referencia -el centro de la caja- este dentro de
 * una liana y se este pidiendo arriba o abajo. No hace falta pisar suelo: esa
 * es justo la gracia. */
static int np_climb_mount(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpActorDef *a = &np_player_def.actor;
    NpPlayer *p = &w->players[quien];
    int32_t tx;

    if (np_player_def.climb_speed <= 0) return 0;
    if (!(input & (NP_IN_UP | NP_IN_DOWN))) return 0;
    if (!np_climb_at(w, np_ref_x(p, a), np_ref_y(p, a))) return 0;
    /* Centrado en la liana, como en las escaleras: agarrarse te coloca. */
    tx = NP_F2I(np_ref_x(p, a)) >> NP_TILE_SHIFT;
    p->x = NP_I2F(tx * NP_TILE + NP_TILE / 2 - a->box_w / 2);
    p->vx = 0;
    p->vy = 0;
    p->trepa = 1;
    p->on_ground = 0;
    return 1;
}

/* Un frame colgado de la liana. Devuelve 1 si sigue en ella. */
static int np_climb_update(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpPlayerDef *d = &np_player_def;
    const NpActorDef *a = &d->actor;
    NpPlayer *p = &w->players[quien];
    int moviendo = 0;

    p->vx = 0;
    p->vy = 0;
    p->on_ground = 0;

    /* Saltar suelta la liana con el impulso de siempre, y hacia donde se este
       pidiendo: es como se pasa de una liana a la de al lado. */
    if ((input & NP_IN_JUMP) && !(w->prev_input[quien] & NP_IN_JUMP)) {
        p->trepa = 0;
        p->vy = -d->jump;
        if (input & NP_IN_RIGHT) { p->vx = d->speed; p->facing = 1; }
        else if (input & NP_IN_LEFT) { p->vx = -d->speed; p->facing = 0; }
        w->sfx |= NP_SFX_JUMP;
        return 0;
    }

    /* Subir y bajar. Va por np_move_y y no a pelo para que la cabeza no
       atraviese el techo ni los pies el suelo: una liana pegada a un piso se
       trepa hasta el borde y ahi se para. Se pasa `drop_through` porque las
       plataformas de atravesar no frenan a quien baja por una cuerda. */
    if (input & (NP_IN_UP | NP_IN_DOWN)) {
        np_fix paso = (input & NP_IN_UP) ? -d->climb_speed : d->climb_speed;
        int abajo, arriba;
        p->y = np_move_y(w, p->x, p->y, a->box_w, a->box_h, paso, 1,
                         &abajo, &arriba);
        moviendo = 1;
    }

    if (!np_climb_at(w, np_ref_x(p, a), np_ref_y(p, a))) {
        /* Se acabo la liana. Por arriba se sale de pie en el borde -que es lo
           que uno espera al llegar al final de una cuerda- y por abajo se
           suelta y se cae. */
        p->trepa = 0;
        if (input & NP_IN_UP) {
            int32_t ty = NP_F2I(np_ref_y(p, a)) >> NP_TILE_SHIFT;
            p->y = NP_I2F(ty * NP_TILE + NP_TILE - a->box_h);
        }
        return 0;
    }
    np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_STAIR);
    if (moviendo) np_anim_tick(a, p->anim, &p->anim_frame, &p->anim_timer);
    return 1;
}

/* ------------------------------------------------------------- el jugador */

/* El jugador mirando desde arriba: ocho direcciones, sin gravedad y sin
 * suelo. Ver el bloque de "la vista cenital" mas arriba. */
static void np_player_update_cenital(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpPlayerDef *d = &np_player_def;
    const NpActorDef *a = &d->actor;
    NpPlayer *p = &w->players[quien];
    int dx = 0, dy = 0;
    int hit_x = 0, hit_down = 0, hit_up = 0;
    uint8_t pose;

    /* Aturdido: ni se anda ni se dispara, y el empujon del golpe se respeta
       hasta que se acaba, igual que en vista lateral. */
    if (p->stun) {
        p->stun--;
        input = 0;
    } else {
        if (input & NP_IN_RIGHT) dx += 1;
        if (input & NP_IN_LEFT) dx -= 1;
        if (input & NP_IN_DOWN) dy += 1;
        if (input & NP_IN_UP) dy -= 1;
    }

    if (dx || dy) {
        p->aim = np_aim_de(dx, dy);
        if (dx) p->facing = (uint8_t)(dx > 0);      /* el espejo del dibujo */
        p->vx = np_paso_cenital(d->speed, dx, dx && dy);
        p->vy = np_paso_cenital(d->speed, dy, dx && dy);
    } else if (p->stun) {
        p->vx = np_approach(p->vx, 0, d->friction); /* el empujon se apaga */
        p->vy = np_approach(p->vy, 0, d->friction);
    } else {
        p->vx = 0;
        p->vy = 0;
    }

    /* Aqui no hay suelo: se choca con las paredes en los dos ejes. */
    p->x = np_move_x(w, p->x, p->y, a->box_w, a->box_h, p->vx, &hit_x);
    if (hit_x) p->vx = 0;
    p->y = np_move_y(w, p->x, p->y, a->box_w, a->box_h, p->vy, 1,
                     &hit_down, &hit_up);
    if (hit_down || hit_up) p->vy = 0;
    /* Pisar no significa nada mirando desde arriba, pero lo miran cosas que
       valen para los dos modos (la pose, el marcador): siempre en el suelo. */
    p->on_ground = 1;
    p->jumps_left = 0;
    p->stairs = 0;
    p->trepa = 0;
    p->crouch = 0;

    /* El boton de saltar no tiene nada que saltar, asi que es el de la
       granada: es el reparto de los recreativos de comando -uno dispara y el
       otro tira-. El de accion sigue siendo el de disparar. */
    if (p->attack_cd) p->attack_cd--;
    if ((input & NP_IN_JUMP) && !(w->prev_input[quien] & NP_IN_JUMP)
        && np_sub_count && w->hearts >= np_subs[w->sub].cost)
        np_player_sub(w, quien);
    else if ((input & NP_IN_ACTION) && !(w->prev_input[quien] & NP_IN_ACTION))
        np_player_attack(w, quien);

    if (p->invuln) p->invuln--;
    if (p->attack_timer) p->attack_timer--;

    /* La pose: de espaldas subiendo, de frente bajando y de lado el resto.
       Quien no traiga esos dibujos se queda en 'correr' (lo dice
       _resolve_anims), asi que un juego cenital sin arte propio se vera raro
       pero se juega igual. */
    if (p->attack_timer) pose = NP_ANIM_ATTACK;
    else if (!dx && !dy) pose = NP_ANIM_IDLE;
    else if (dy < 0 && !dx) pose = NP_ANIM_UP;
    else if (dy > 0 && !dx) pose = NP_ANIM_DOWN;
    else pose = NP_ANIM_RUN;
    np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, pose);
    np_anim_tick(a, p->anim, &p->anim_frame, &p->anim_timer);
}

/* Lo que se aparta un maton despues de pegarte, en frames. No es una opcion
   del game.yaml a proposito: es la regla del genero, no un ajuste. */
#define NP_RECULA 26

/* ------------------------------------------------------------ el agarre */
/*
 * Lo que hace que un juego de tortas sea un juego de tortas y no un pasillo de
 * punetazos: al que se tambalea de un golpe se le coge, se le zarandea a
 * rodillazos y se le lanza por encima del hombro.
 *
 * Se agarra **al que esta parpadeando**, o sea al que acabas de tocar: es la
 * regla de los recreativos y ademas se explica sola -pegar, coger, rematar-.
 * `p->grab` guarda su sitio en la lista mas uno, y mientras dure no se mueve ni
 * decide nada: lo lleva el jugador pegado al costado.
 */
static NpEntity *np_agarrado(NpWorld *w, NpPlayer *p)
{
    NpEntity *e;
    if (!p->grab || p->grab > w->entity_count) return 0;
    e = &w->entities[p->grab - 1];
    if (!e->active || e->kind != NP_KIND_ENEMY) {
        p->grab = 0;
        return 0;
    }
    return e;
}

static void np_soltar(NpPlayer *p)
{
    p->grab = 0;
    p->grab_timer = 0;
}

/* Lanzarlo: sale despedido hacia donde miras, subiendo, y cae derribado al
   otro lado. Es el golpe mas fuerte del genero y el que despeja la pantalla. */
static void np_lanzar(NpWorld *w, uint8_t quien, NpEntity *e)
{
    const NpPlayerDef *d = &np_player_def;
    NpPlayer *p = &w->players[quien];
    e->vx = p->facing ? d->throw_speed : (np_fix)(-d->throw_speed);
    e->vy = 0;
    e->valtura = d->jump;             /* el mismo impulso con el que saltas */
    e->knock = (uint8_t)(d->grab_time ? 60 : 30);
    e->golpeado = 0;
    w->sfx |= NP_SFX_STOMP;
    np_hit_entity(w, e, d->throw_damage);
    np_soltar(p);
}

/* El rodillazo: le hace dano sin soltarlo, y reengancha el agarre. */
static void np_rodillazo(NpWorld *w, uint8_t quien, NpEntity *e)
{
    const NpPlayerDef *d = &np_player_def;
    NpPlayer *p = &w->players[quien];
    p->attack_timer = np_player_def.attack.duration;
    p->grab_timer = d->grab_time;
    w->sfx |= NP_SFX_SHOOT;
    np_hit_entity(w, e, d->grab_damage);
    if (!e->active) np_soltar(p);
}

/* Lo que hace el agarre cada frame: llevarlo pegado al costado, gastar su
   cuenta atras y leer los dos botones. Devuelve 1 si el frame se lo queda el
   agarre, o sea que ni se anda ni se pega de lo normal. */
static int np_grab_update(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpPlayerDef *d = &np_player_def;
    NpPlayer *p = &w->players[quien];
    NpEntity *e = np_agarrado(w, p);
    const NpActorDef *pa = &d->actor;
    const NpActorDef *ea;

    if (!e) return 0;
    if (p->stun || p->dying) { np_soltar(p); return 0; }
    if (!p->grab_timer) { np_soltar(p); return 0; }
    p->grab_timer--;

    /* Se lleva pegado al costado por el que miras y a tu misma profundidad:
       asi lo que le pase le pasa donde se ve que le pasa. */
    ea = np_entity_def(e);
    e->x = p->facing ? p->x + NP_I2F(pa->box_w - 2)
                     : p->x - NP_I2F(ea->box_w - 2);
    e->y = p->y + NP_I2F(pa->box_h - ea->box_h);
    e->vx = 0;
    e->vy = 0;
    e->knock = 0;
    e->facing = (uint8_t)!p->facing;      /* le tienes de frente */
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_HURT);
    np_anim_tick(ea, e->anim, &e->anim_frame, &e->anim_timer);

    if ((input & NP_IN_JUMP) && !(w->prev_input[quien] & NP_IN_JUMP)) {
        np_lanzar(w, quien, e);
        return 1;
    }
    if ((input & NP_IN_ACTION) && !(w->prev_input[quien] & NP_IN_ACTION)
        && !p->attack_cd) {
        p->attack_cd = np_player_def.attack.cooldown;
        np_rodillazo(w, quien, e);
    }
    if (p->attack_timer) p->attack_timer--;
    np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer,
                p->attack_timer ? NP_ANIM_ATTACK : NP_ANIM_IDLE);
    np_anim_tick(pa, p->anim, &p->anim_frame, &p->anim_timer);
    return 1;
}

/* ---------------------------------------------------- la vista de cinta */
/*
 * El "yo contra el barrio": Double Dragon, Final Fight, Streets of Rage.
 *
 * Se anda por una franja de suelo en las ocho direcciones, como en cenital,
 * pero **se salta**: hay una tercera coordenada, la altura sobre el suelo, con
 * su gravedad. Que sean tres y no dos es lo que hace el genero: dos que estan
 * a la misma altura pero a distinta profundidad no se tocan, y por eso hay que
 * cuadrarse antes de pegar.
 *
 * El truco para que esto no cueste ni una linea en las siete maquinas: `y`
 * sigue siendo **donde se dibuja** y la altura se guarda aparte. Asi
 *
 *   - los dibujantes de las siete maquinas no se enteran de nada;
 *   - dos cajas se tocan solo si coinciden en profundidad **y** en altura, que
 *     es justo la regla del genero, y sale gratis de las cajas de siempre: al
 *     saltar, la caja sube y el punetazo de abajo pasa por debajo;
 *   - y quien necesita saber por donde se anda -los choques con el escenario y
 *     la camara- suma la altura y tiene la linea del suelo.
 *
 * En el aire no se cambia de idea: la velocidad con la que saltas es la que te
 * lleva hasta caer, como en los recreativos. Por eso el salto se decide antes
 * de leer el mando y no despues.
 */
static void np_player_update_cinta(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpPlayerDef *d = &np_player_def;
    const NpActorDef *a = &d->actor;
    NpPlayer *p = &w->players[quien];
    int dx = 0, dy = 0;
    int hit_x = 0, hit_down = 0, hit_up = 0;
    np_fix suelo;
    uint8_t pose;

    /* Con alguien agarrado el frame es otro: no se anda, se le zarandea. */
    if (np_player_def.grab_time && np_grab_update(w, quien, input)) return;

    /* Aqui no se cae de ningun sitio: si no estas por el aire, estas de pie.
       Lo primero es cuadrar eso, porque un jugador recien colocado viene con
       `on_ground` a cero -en vista lateral se cae hasta el suelo- y sin esto
       no podria saltar en su primer frame. */
    if (p->altura <= 0 && p->valtura <= 0) {
        p->altura = 0;
        p->valtura = 0;
        p->on_ground = 1;
    }

    if (p->stun) {
        p->stun--;
        input = 0;
    } else {
        if (input & NP_IN_RIGHT) dx += 1;
        if (input & NP_IN_LEFT) dx -= 1;
        if (input & NP_IN_DOWN) dy += 1;
        if (input & NP_IN_UP) dy -= 1;
    }

    /* La carrera: dos toques seguidos en la misma direccion. Es la respuesta a
       que te rodeen -y la unica forma de cruzar la calle sin comerse tres
       golpes-, asi que se enciende con el mando y no con un boton: en un
       recreativo no habia botones de sobra.

       La ventana del segundo toque corre siempre; el esprint se apaga al
       soltar la direccion, al cambiar de sentido o al acabarse su tiempo. */
    if (p->toque) p->toque--;
    if (!p->stun && dx && !(w->prev_input[quien] & (NP_IN_LEFT | NP_IN_RIGHT))) {
        if (p->toque && p->toque_dir == (int8_t)dx) {
            p->carrera = NP_CARRERA;
            p->toque = 0;
        } else {
            p->toque = NP_TOQUE_VENTANA;
            p->toque_dir = (int8_t)dx;
        }
    }
    if (p->carrera) {
        if (p->stun || !dx || (int8_t)dx != p->toque_dir) p->carrera = 0;
        else p->carrera--;
    }

    /* Andar: solo con los pies en el suelo. En el aire manda el impulso. */
    if (p->on_ground) {
        if (dx || dy) {
            np_fix paso = p->carrera
                ? (np_fix)((d->speed * NP_CARRERA_X2) >> 3) : d->speed;
            p->aim = np_aim_de(dx, dy);
            if (dx) p->facing = (uint8_t)(dx > 0);
            p->vx = np_paso_cenital(paso, dx, dx && dy);
            p->vy = np_paso_cenital(paso, dy, dx && dy);
        } else if (p->stun) {
            p->vx = np_approach(p->vx, 0, d->friction);  /* el empujon se apaga */
            p->vy = np_approach(p->vy, 0, d->friction);
        } else {
            p->vx = 0;
            p->vy = 0;
        }
    }

    /* La linea del suelo, **antes** de tocar la altura: es lo que no se mueve
       al saltar. Sacarla despues seria sumar la altura nueva a una `y` que
       todavia lleva la vieja, y el salto se anularia solo. */
    suelo = p->y + p->altura;

    /* El salto, que aqui es la tercera coordenada: `salto:` y `gravedad:` son
       los mismos numeros de siempre, solo que no mueven la y sino la altura. */
    if (!p->stun && (input & NP_IN_JUMP) && !(w->prev_input[quien] & NP_IN_JUMP)
        && p->on_ground) {
        p->valtura = d->jump;
        p->on_ground = 0;
        w->sfx |= NP_SFX_JUMP;
    }
    if (!p->on_ground) {
        p->altura += p->valtura;
        p->valtura -= d->gravity;
        if (p->valtura < -d->max_fall) p->valtura = -d->max_fall;
        if (p->altura <= 0) {
            p->altura = 0;
            p->valtura = 0;
            p->on_ground = 1;
        }
    }

    /* Andar y chocar, en la linea del suelo: saltando se pasa por encima de un
       enemigo, pero no de una pared. */
    p->x = np_move_x(w, p->x, suelo, a->box_w, a->box_h, p->vx, &hit_x);
    if (hit_x) p->vx = 0;
    suelo = np_move_y(w, p->x, suelo, a->box_w, a->box_h, p->vy, 1,
                      &hit_down, &hit_up);
    if (hit_down || hit_up) p->vy = 0;
    p->y = suelo - p->altura;

    p->jumps_left = 0;
    p->stairs = 0;
    p->trepa = 0;
    p->crouch = 0;

    /* El boton de accion es el punetazo; el de saltar, saltar. Aqui no hay
       arma secundaria en el salto como en el comando: en un juego de tortas,
       saltar **es** media pelea. */
    if (p->attack_cd) p->attack_cd--;
    if ((input & NP_IN_ACTION) && !(w->prev_input[quien] & NP_IN_ACTION)) {
        /* El codazo hacia atras: si el que tienes encima esta **detras** y
           delante no hay nadie, te giras al soltar el golpe. Es el codo de
           toda la vida de los juegos de tortas, y es lo que hace que te
           rodeen sin que rodearte sea gratis. */
        if (!np_hay_delante(w, quien) && np_hay_detras(w, quien))
            p->facing = (uint8_t)!p->facing;
        /* Y si sale por el aire es patada en salto, y en carrera es hombro:
           los dos pegan como un remate y tumban. El hombro **gasta** la
           carrera, asi que es uno por esprint y no un boton de tumbar. */
        p->fuerte = (uint8_t)(!p->on_ground || p->carrera != 0);
        p->carrera = 0;
        np_player_attack(w, quien);
    }

    if (p->invuln) p->invuln--;
    /* La caja del punetazo, que ademas lleva el reloj del golpe. En vista
       cenital no se llama: alli el puno tendria que salir en ocho direcciones
       y los juegos de comando disparan. Aqui se mira a un lado o a otro -como
       en cualquier juego de tortas- y la caja de delante vale tal cual. */
    np_melee_update(w, quien);

    if (p->attack_timer)
        pose = np_es_remate(p) ? NP_ANIM_FINISH : NP_ANIM_ATTACK;
    else if (!p->on_ground) pose = (p->valtura > 0) ? NP_ANIM_JUMP : NP_ANIM_FALL;
    else if (!dx && !dy) pose = NP_ANIM_IDLE;
    else if (dy < 0 && !dx) pose = NP_ANIM_UP;
    else if (dy > 0 && !dx) pose = NP_ANIM_DOWN;
    else pose = NP_ANIM_RUN;
    np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, pose);
    np_anim_tick(a, p->anim, &p->anim_frame, &p->anim_timer);
}

/* --------------------------------------------------- el jugador isometrico */
/*
 * Se anda por la **planta** de la sala en las cuatro direcciones del mapa, que
 * en pantalla salen en diagonal -y eso es justo lo que hace que una sala
 * parezca una habitacion y no un tablero-. Y se salta de verdad: la altura es
 * la tercera coordenada, con la gravedad de siempre, y el suelo no es una
 * linea sino el relieve de las casillas.
 *
 * El mando va directo a la planta: derecha es el eje x del mapa y abajo el eje
 * y, asi que en pantalla la derecha del mando sale hacia abajo y a la derecha.
 * Escrito suena raro y jugado no lo es: es lo que hacian todos los del genero,
 * y ademas deja las cuatro diagonales del mando para los cuatro lados rectos
 * de la pantalla, que es como se recorre un pasillo.
 */
static void np_player_update_iso(NpWorld *w, uint8_t quien, uint16_t input)
{
    const NpPlayerDef *d = &np_player_def;
    const NpActorDef *a = &d->actor;
    NpPlayer *p = &w->players[quien];
    int dx = 0, dy = 0;
    int hit_x = 0, hit_y = 0;
    np_fix cota;
    uint8_t pose;

    /* Aqui no se cae de ningun sitio que no sea un cubo: si no estas por el
       aire, estas de pie. Lo primero es cuadrar eso, porque un jugador recien
       colocado viene con `on_ground` a cero -en vista lateral se cae hasta el
       suelo- y sin esto no podria saltar en su primer frame. */
    if (p->altura <= 0 && p->valtura <= 0) {
        p->altura = 0;
        p->valtura = 0;
        p->on_ground = 1;
    }

    if (p->stun) {
        p->stun--;
        input = 0;
    } else {
        if (input & NP_IN_RIGHT) dx += 1;
        if (input & NP_IN_LEFT) dx -= 1;
        if (input & NP_IN_DOWN) dy += 1;
        if (input & NP_IN_UP) dy -= 1;
    }

    /* Por el aire manda el impulso con el que despegaste: en un juego de estos
       el salto es una decision y no un volante, y medio genero es medir. */
    if (p->on_ground) {
        if (dx || dy) {
            p->aim = np_aim_de(dx, dy);
            p->vx = np_paso_cenital(d->speed, dx, dx && dy);
            p->vy = np_paso_cenital(d->speed, dy, dx && dy);
            /* El espejo del dibujo se mira por donde cae en **la pantalla**
               (x - y), no por el eje del mapa: hacia el este y hacia el norte
               se ve el mismo costado. */
            p->facing = (uint8_t)(dx - dy > 0);
        } else if (p->stun) {
            p->vx = np_approach(p->vx, 0, d->friction);
            p->vy = np_approach(p->vy, 0, d->friction);
        } else {
            p->vx = 0;
            p->vy = 0;
        }
    }

    if (!p->stun && (input & NP_IN_JUMP) && !(w->prev_input[quien] & NP_IN_JUMP)
        && p->on_ground) {
        p->valtura = d->jump;
        p->on_ground = 0;
        w->sfx |= NP_SFX_JUMP;
    }
    if (!p->on_ground) {
        p->altura += p->valtura;
        p->valtura -= d->gravity;
        if (p->valtura < -d->max_fall) p->valtura = -d->max_fall;
    }

    /* Andar con los pies donde estan: lo que esta mas alto que tu escalon te
       para, y lo que no, se sube andando. Los dos ejes por separado, para que
       rozar una pared en diagonal no te deje clavado. */
    p->x = np_iso_move(w, p->x, p->y, a->box_w, a->box_h, p->vx, p->altura,
                       0, &hit_x);
    p->y = np_iso_move(w, p->x, p->y, a->box_w, a->box_h, p->vy, p->altura,
                       1, &hit_y);
    /* Chocar solo te para **de pie**. Por el aire el impulso se guarda aunque
       de momento no quepas: es lo que hace que se pueda saltar a un cubo
       estando pegado a el -sales rozandolo, subes por encima y en cuanto lo
       pasas el impulso te mete arriba-. Si se anulara al chocar, el salto
       desde al lado seria un salto en el sitio y para subirse a nada haria
       falta carrerilla, que no es como se juega a esto. */
    if (p->on_ground) {
        if (hit_x) p->vx = 0;
        if (hit_y) p->vy = 0;
    }

    /* Y el suelo que ha quedado debajo. Si estas por debajo de el -acabas de
       subirte a un cubo, o vienes cayendo- te plantas encima; si esta mas
       abajo que tu, te caes. Con eso solo, andar por una sala con relieve ya
       funciona: no hay un caso "subir" y otro "bajar". */
    cota = np_iso_suelo(w, p->x, p->y, a->box_w, a->box_h);
    if (p->valtura <= 0 && p->altura <= cota) {
        p->altura = cota;
        p->valtura = 0;
        p->on_ground = 1;
    } else if (p->altura > cota) {
        p->on_ground = 0;
    }

    p->jumps_left = 0;
    p->stairs = 0;
    p->trepa = 0;
    p->crouch = 0;
    p->riding = 0;

    /* El boton: en un juego con bolsa suelta lo que llevas -que es lo unico
       que se hace con las manos en el genero- y en uno con ataque, pega. */
    np_player_action(w, quien, input);

    if (p->invuln) p->invuln--;

    /* La pose: de espaldas cuando el paso sube por la pantalla y de frente
       cuando baja. Con los cuatro lados de la planta salen cuatro vistas del
       heroe con solo dos dibujos, porque el espejo hace las otras dos. */
    if (p->attack_timer) pose = NP_ANIM_ATTACK;
    else if (!p->on_ground) pose = (p->valtura > 0) ? NP_ANIM_JUMP : NP_ANIM_FALL;
    else if (!dx && !dy) pose = NP_ANIM_IDLE;
    else pose = (dx + dy < 0) ? NP_ANIM_UP : NP_ANIM_DOWN;
    np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, pose);
    np_anim_tick(a, p->anim, &p->anim_frame, &p->anim_timer);
}

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
            if (e->vx) p->x = np_move_x(w, p->x, p->y, a->box_w, a->box_h,
                                        e->vx, &llevado);
            (void)llevado;              /* si topa con una pared, se queda ahi */
            if (e->vy) p->y = np_move_y(w, p->x, p->y, a->box_w, a->box_h,
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
        p->crouch = 0;              /* en la escalera no se agacha nadie */
        np_player_action(w, quien, input);
        if (!np_stair_update(w, quien, input))
            np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_IDLE);
        return;
    }
    if (!p->stun && np_stair_mount(w, quien, input)) {
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_STAIR);
        return;
    }

    /* --- lianas ----------------------------------------------------------
     *
     * Igual que la escalera: colgado manda la liana. Lo que cambia es que a
     * ella se llega tambien por el aire, asi que se prueba a agarrarse aunque
     * no se pise suelo. */
    if (p->trepa) {
        p->crouch = 0;
        np_player_action(w, quien, input);
        if (!np_climb_update(w, quien, input))
            np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_IDLE);
        return;
    }
    if (!p->stun && np_climb_mount(w, quien, input)) {
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_STAIR);
        return;
    }

    /* --- agacharse -------------------------------------------------------
     *
     * Con abajo, en el suelo: no se anda ni se salta, pero se pega, y el golpe
     * sale por abajo. Encima de una plataforma de las de atravesar, abajo
     * sigue siendo para bajarse (de eso se encarga np_move_y): no se puede
     * uno agachar en el aire, asi que al frame siguiente ya no esta agachado.
     *
     * Se mira antes de moverse porque decide si se anda; lo de si sigue en el
     * suelo es lo que quedo del frame anterior, igual que el salto. */
    if (d->crouch_drop && p->on_ground && (input & NP_IN_DOWN)) {
        p->crouch = 1;
        dir = 0;
    } else {
        p->crouch = 0;
    }

    /* Mientras dura un golpe con `clavado: si` te quedas plantado: ni andas ni
       te giras, que es lo que obliga a elegir cuando pegas. En el aire si se
       conserva el impulso, como en los clasicos: saltas y pegas de camino. */
    if (p->attack_timer && d->attack.locks && p->on_ground) {
        p->vx = 0;
    } else if (p->stun) {
        /* ni acelerar ni frenar: el empujon del golpe llega hasta el final */
    } else if (!d->air_control && !p->on_ground) {
        /* El salto de las aventuras: al despegar se decide hacia donde vas y
           ya no se cambia. Es lo que convierte cada salto en una decision. */
    } else if (dir > 0) { p->vx = np_approach(p->vx, d->speed, p->on_ground ? d->accel : d->air_accel); p->facing = 1; }
    else if (dir < 0) { p->vx = np_approach(p->vx, -d->speed, p->on_ground ? d->accel : d->air_accel); p->facing = 0; }
    else if (p->on_ground) p->vx = np_approach(p->vx, 0, d->friction);

    /* El ataque va por flanco: mantener el boton no dispara sin parar, y la
       cadencia la marca `espera:` del game.yaml. */
    np_player_action(w, quien, input);

    /* agachado no se salta: hay que levantarse primero */
    pressed_jump = !p->crouch
        && (input & NP_IN_JUMP) && !(w->prev_input[quien] & NP_IN_JUMP);
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
        /* sin control en el aire, el impulso se fija aqui: lo que se pulsaba
           al despegar es lo que dura todo el salto */
        if (!d->air_control)
            p->vx = dir > 0 ? d->speed : (dir < 0 ? -d->speed : 0);
    }
    /* soltar el boton solo corta el salto si se manda en el aire: el salto de
       las aventuras siempre hace el mismo arco */
    if (d->air_control && !(input & NP_IN_JUMP) && p->vy < -d->jump_cut)
        p->vy = -d->jump_cut;

    p->vy += d->gravity;
    if (p->vy > d->max_fall) p->vy = d->max_fall;

    p->x = np_move_x(w, p->x, p->y, a->box_w, a->box_h, p->vx, &hit_x);
    if (hit_x) p->vx = 0;
    antes_y = p->y;
    p->y = np_move_y(w, p->x, p->y, a->box_w, a->box_h, p->vy,
                     (input & NP_IN_DOWN) ? 1 : 0, &hit_down, &hit_up);
    p->on_ground = (uint8_t)hit_down;
    if (hit_down && p->vy > 0) p->vy = 0;
    if (hit_up && p->vy < 0) p->vy = 0;
    np_ride_update(w, quien, antes_y, (input & NP_IN_DOWN) ? 1 : 0);

    if (p->invuln) p->invuln--;

    /* Agachado manda la pose de agachado, tambien pegando: el golpe sale por
       abajo y con la pose de pie el dibujo no cuadraria con lo que pega. */
    if (p->crouch)
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer, NP_ANIM_CROUCH);
    else if (p->attack_timer)
        /* En el aire con `patada:` puesto, la pose es la de la patada: lo que
           se ve tiene que ser lo que pega, y lo que pega ahi no es el puno. */
        np_anim_set(&p->anim, &p->anim_frame, &p->anim_timer,
                    np_es_patada(p) ? NP_ANIM_KICK : NP_ANIM_ATTACK);
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

/* Si hay donde pisar justo al otro lado del borde por el que va el enemigo.
   Lo usan los dos que andan por el suelo: el que patrulla para darse la vuelta
   y el que persigue para plantarse en vez de tirarse por el agujero. */
static uint8_t np_suelo_delante(const NpWorld *w, const NpEntity *e,
                                const NpActorDef *a, uint8_t hacia_la_derecha)
{
    int32_t borde = hacia_la_derecha ? NP_F2I(e->x + NP_I2F(a->box_w) - 1) + 1
                                     : NP_F2I(e->x) - 1;
    int32_t debajo = NP_F2I(e->y + NP_I2F(a->box_h));
    uint8_t tipo = np_tile_kind_at(w->level, borde >> NP_TILE_SHIFT,
                                   debajo >> NP_TILE_SHIFT);
    return (uint8_t)(tipo == NP_TILE_SOLID || tipo == NP_TILE_PLATFORM);
}

/* ------------------------------------------------------- los prisioneros */
/*
 * El rehen atado de Guerrilla War. Es el unico actor del kit al que **no** hay
 * que dispararle: si lo tocas se suelta, suma sus puntos y echa a correr hasta
 * perderse de vista; si le pega un tiro tuyo -o una granada-, se acabo y no
 * suma nada. Eso es lo que obliga a mirar antes de disparar, que es justo lo
 * que hace distinto un juego de rescatar de uno de arrasar.
 *
 * `timer` a cero quiere decir que sigue atado; en cuanto se suelta lleva la
 * cuenta atras de la huida.
 */
static void np_prisoner_free(NpWorld *w, NpEntity *e, const NpPlayer *p)
{
    const NpPrisonerDef *d = &np_prisoners[e->def];
    if (e->timer) return;                       /* ya iba corriendo */
    e->timer = d->escape ? d->escape : 1;
    w->score += d->score;
    w->sfx |= NP_SFX_COIN;
    /* Echa a correr **al reves de donde estas**: asi no se te cruza por
       delante justo cuando lo acabas de soltar. */
    if (np_vista_cenital) {
        e->vy = (e->y < p->y) ? -d->speed : d->speed;
        e->vx = 0;
    } else {
        e->vx = (e->x < p->x) ? -d->speed : d->speed;
        e->facing = (uint8_t)(e->vx > 0);
    }
}

/* ------------------------------------------------ generadores de bichos */
/*
 * Los nidos de Gauntlet. Se estan quietos y cada `cooldown` frames sacan un
 * enemigo, hasta que los destruyes a tiros. Mientras uno siga en pie, matar
 * bichos no sirve de nada: es lo que convierte la mazmorra en una carrera y no
 * en una sala que se limpia.
 *
 * El tope de bichos suyos a la vez (`cap`) no es un adorno: la lista de
 * entidades tiene 64 sitios y los comparten los disparos. Tres generadores sin
 * tope la llenarian en unos segundos y el juego se quedaria sin poder disparar.
 */
static uint8_t np_cuantos_bichos(const NpWorld *w, uint8_t def)
{
    uint8_t i, cuantos = 0;
    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
        if (e->active && e->kind == NP_KIND_ENEMY && e->def == def) cuantos++;
    }
    return cuantos;
}

static void np_generator_update(NpWorld *w, NpEntity *e)
{
    const NpGeneratorDef *d = &np_generators[e->def];
    const NpActorDef *a = &d->actor;
    int hueco;

    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_IDLE);
    np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
    /* la cuenta va hacia arriba, igual que la del desgaste: asi "cada 30
       frames" son treinta clavados y no treinta y uno */
    if (++e->timer < d->cooldown) return;
    e->timer = 0;
    if (np_cuantos_bichos(w, d->enemy) >= d->cap) return;
    hueco = np_hueco_libre(w);
    if (hueco < 0) return;               /* no cabe: este bicho no sale */
    {
        NpEntity *b = &w->entities[hueco];
        const NpEnemyDef *ed = &np_enemies[d->enemy];
        const NpActorDef *ba = &ed->actor;
        b->active = 1;
        b->kind = NP_KIND_ENEMY;
        b->def = d->enemy;
        /* sale centrado en el nido y apoyado en su misma linea de suelo */
        b->x = e->x + NP_I2F((int32_t)a->box_w / 2 - (int32_t)ba->box_w / 2);
        b->y = e->y + NP_I2F((int32_t)a->box_h - (int32_t)ba->box_h);
        b->home_x = b->x;
        b->home_y = b->y;
        b->vx = ed->speed;
        b->vy = 0;
        b->facing = 1;
        b->health = ed->health;
        b->hurt = 0;
        b->vida = 0;
        b->timer = ed->interval;
        b->anim = NP_ANIM_IDLE;
        b->anim_frame = 0;
        b->anim_timer = 0;
    }
}

static void np_prisoner_update(NpWorld *w, NpEntity *e)
{
    const NpPrisonerDef *d = &np_prisoners[e->def];
    const NpActorDef *a = &d->actor;
    int hit_x = 0, hit_down = 0, hit_up = 0;

    if (!e->timer) {                            /* atado: solo se anima */
        np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_IDLE);
        np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
        return;
    }
    e->timer--;
    if (!e->timer) { e->active = 0; return; }   /* se ha perdido de vista */
    if (e->vx) {
        e->x = np_move_x(w, e->x, e->y, a->box_w, a->box_h, e->vx, &hit_x);
        if (hit_x) e->vx = -e->vx;              /* rebota en las paredes */
    }
    if (e->vy) {
        e->y = np_move_y(w, e->x, e->y, a->box_w, a->box_h, e->vy, 1,
                         &hit_down, &hit_up);
        if (hit_down || hit_up) e->vy = -e->vy;
    }
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_RUN);
    np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
}

/* --------------------------------------------- lo que tiran los enemigos */
/*
 * Con `dispara:` un enemigo deja de ser un obstaculo que hay que esquivar y
 * pasa a ser una amenaza a distancia: es lo que separa un plataformas de un
 * juego de comando. El disparo es una entidad mas de la lista (NP_KIND_ENEMY_
 * SHOT), como los del jugador, asi que las seis maquinas lo dibujan sin
 * enterarse y entra en el hash de la paridad.
 *
 * El enemigo lleva su cuenta atras en `vida`, que en un enemigo no se usa para
 * nada mas (es el contador de vuelo de los proyectiles).
 */
static void np_enemy_shoot(NpWorld *w, NpEntity *e, const NpEnemyDef *d)
{
    const NpEnemyShotDef *sd = &np_enemy_shots[d->shot - 1];
    const NpActorDef *ea = &d->actor;
    const NpPlayer *p = np_nearest_player(w, e->x);
    np_fix dx = (p->x + NP_I2F(np_player_def.actor.box_w / 2))
              - (e->x + NP_I2F(ea->box_w / 2));
    np_fix dy = (p->y + NP_I2F(np_player_def.actor.box_h / 2))
              - (e->y + NP_I2F(ea->box_h / 2));
    int hueco;
    NpEntity *b;
    int ax, ay;

    if (NP_ABS(dx) > NP_I2F(sd->range) || NP_ABS(dy) > NP_I2F(sd->range)) return;
    hueco = np_hueco_libre(w);
    if (hueco < 0) return;               /* no cabe: este tiro se pierde */
    e->vida = sd->cooldown;

    if (np_vista_cenital) {
        /* Desde arriba se apunta en las ocho direcciones, redondeando a la
           mas cercana: un soldado te tira **a ti**, no hacia un lado. */
        np_fix ex = NP_ABS(dx), ey = NP_ABS(dy);
        ax = (ex * 2 > ey) ? NP_SIGN(dx) : 0;
        ay = (ey * 2 > ex) ? NP_SIGN(dy) : 0;
        if (!ax && !ay) ax = e->facing ? 1 : -1;
    } else {
        /* De lado se tira de frente, que es lo unico que tiene sentido con
           gravedad: hacia donde esta el jugador. */
        ax = dx > 0 ? 1 : -1;
        ay = 0;
        e->facing = (uint8_t)(ax > 0);
    }

    b = &w->entities[hueco];
    b->active = 1;
    b->kind = NP_KIND_ENEMY_SHOT;
    b->def = (uint8_t)(d->shot - 1);
    b->facing = (uint8_t)(ax >= 0);
    b->x = e->x + NP_I2F((ea->box_w - sd->actor.box_w) / 2
                         + ax * (ea->box_w / 2 + 1));
    b->y = e->y + NP_I2F((ea->box_h - sd->actor.box_h) / 2
                         + ay * (ea->box_h / 2 + 1));
    b->vx = np_paso_cenital(sd->speed, ax, ax && ay);
    b->vy = np_paso_cenital(sd->speed, ay, ax && ay);
    b->home_x = b->x;
    b->home_y = b->y;
    b->health = 1;
    b->hurt = 0;
    b->timer = 0;
    b->anim = NP_ANIM_IDLE;
    b->anim_frame = 0;
    b->anim_timer = 0;
    b->vida = sd->speed ? (uint16_t)((NP_I2F(sd->range) / sd->speed) + 1) : 1;
    w->sfx |= NP_SFX_SHOOT;
}

/* El disparo de un enemigo: vuela, choca con las paredes y hace dano al
   jugador. No le hace nada a los otros enemigos: en los recreativos de comando
   los tiros de los soldados se cruzan entre ellos sin tocarse. */
static void np_enemy_shot_update(NpWorld *w, NpEntity *e)
{
    const NpEnemyShotDef *sd = &np_enemy_shots[e->def];
    const NpActorDef *a = &sd->actor;
    const NpActorDef *pa = &np_player_def.actor;
    uint8_t quien;
    int hit_x = 0, hit_down = 0, hit_up = 0;

    if (!e->vida) { e->active = 0; return; }
    e->vida--;
    if (e->vx) {
        e->x = np_move_x(w, e->x, e->y, a->box_w, a->box_h, e->vx, &hit_x);
        if (hit_x) { e->active = 0; return; }
    }
    if (e->vy) {
        e->y = np_move_y(w, e->x, e->y, a->box_w, a->box_h, e->vy, 1,
                         &hit_down, &hit_up);
        if (hit_down || hit_up) { e->active = 0; return; }
    }

    for (quien = 0; quien < NP_MAX_PLAYERS; quien++) {
        NpPlayer *p = &w->players[quien];
        if (!p->playing || p->dying) continue;
        if (!np_boxes_overlap(e->x, e->y, a->box_w, a->box_h,
                              p->x, np_player_top(p),
                              pa->box_w, np_player_height(p)))
            continue;
        np_player_hurt(w, quien, sd->damage);
        e->active = 0;
        return;
    }
    np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
}

/* ------------------------------------------------------- el luchador */
/*
 * Un enemigo que anda en linea recta hacia ti y te hace dano al rozarte no da
 * una pelea: da un enjambre. Y con siete a la vez, lo unico que se puede hacer
 * es machacar el boton y perder. Eso es exactamente lo que hacia este genero
 * antes, y es lo que arregla este trozo.
 *
 * Un luchador de verdad hace cuatro cosas, y las cuatro se notan al mando:
 *
 *   1. **Se coloca y no se te mete dentro.** Se acerca hasta la distancia a la
 *      que su golpe llega, y ahi se para. Nunca acaba encima de ti, que es lo
 *      que convertia la pelea en un empujon.
 *   2. **Espera su turno.** Solo `np_agresivos` pegan a la vez; los demas
 *      rondan. Es la regla mas vieja del genero -y la menos conocida-: sin
 *      ella no hay juego, porque no hay hueco entre golpe y golpe.
 *   3. **Se le ve venir.** Antes de soltar el golpe hay `preparacion:` frames
 *      de aviso. Sin eso no se puede esquivar y el juego es injusto; con eso,
 *      cada golpe que cobras es culpa tuya, que es lo que hace que apetezca
 *      volver a intentarlo.
 *   4. **Deja una ventana.** Despues del golpe se queda plantado `recuperar:`
 *      frames. Ese hueco es tu turno, y de ahi sale el ritmo de la pelea.
 *
 * Se reparten ademas por profundidad -cada uno tiene su ranura- para que no se
 * amontonen los siete en la misma linea, que es lo que hace que una calle
 * parezca ancha.
 */

/* La distancia a la que se pelea: lo justo para que su golpe llegue. */
static np_fix np_lucha_cerca(const NpEnemyDef *d, const NpActorDef *a)
{
    return NP_I2F((int32_t)a->box_w + (int32_t)d->reach - 8);
}

/* Su golpe: una caja delante, mientras dura la fase de pegar. */
static void np_lucha_pegar(NpWorld *w, NpEntity *e, const NpEnemyDef *d,
                           const NpActorDef *a)
{
    const NpActorDef *pa = &np_player_def.actor;
    np_fix gx = e->facing ? e->x + NP_I2F(a->box_w)
                          : e->x - NP_I2F(d->reach);
    uint8_t quien;
    for (quien = 0; quien < NP_MAX_PLAYERS; quien++) {
        NpPlayer *p = &w->players[quien];
        if (!p->playing || p->dying) continue;
        /* a quien ya ha tocado **este** golpe no se le toca otra vez */
        if (e->tocado & (1u << quien)) continue;
        if (!np_boxes_overlap(gx, e->y, d->reach, a->box_h,
                              p->x, np_player_top(p), pa->box_w,
                              np_player_height(p)))
            continue;
        e->tocado |= (uint8_t)(1u << quien);
        if (p->invuln) continue;             /* parpadeando no entra */
        np_player_hurt(w, quien, d->punch ? d->punch : d->damage);
        w->congelado = NP_CONGELADO;
    }

    /* --- y si el juego lo lleva, ese mismo golpe le da al de al lado -------
     *
     * Con `entre_ellos: si` el punetazo de un enemigo hace dano a **otro
     * enemigo** que este delante. Suena a detalle y es media mecanica: dos
     * perseguidores que se pegan entre ellos dejan de ser dos problemas y
     * pasan a ser una herramienta, porque colocarlos para que se crucen es lo
     * unico que tienes cuando no puedes con ninguno de los dos.
     *
     * Solo cuenta el golpe: rozarse no hace nada, igual que entre un enemigo y
     * tu cuando el enemigo pega en vez de arrollar. */
    if (np_entre_ellos) {
        uint8_t i;
        for (i = 0; i < w->entity_count; i++) {
            NpEntity *o = &w->entities[i];
            const NpActorDef *oa;
            if (o == e || !o->active || o->kind != NP_KIND_ENEMY) continue;
            if (o->hurt) continue;           /* al que aun se queja, no */
            oa = np_entity_def(o);
            if (!np_boxes_overlap(gx, e->y, d->reach, a->box_h,
                                  o->x, o->y, oa->box_w, oa->box_h))
                continue;
            np_hit_enemy(w, o, d->punch ? d->punch : d->damage);
            w->congelado = NP_CONGELADO;
        }
    }
}

/* Que no se amontonen: si esta encima de otro, se aparta por profundidad, que
   es por donde hay sitio en una calle. Se mueve **solo el de turno**, asi que
   con que lo haga cada uno en su vuelta acaban repartidos solos. */
static void np_lucha_separar(NpWorld *w, NpEntity *e, const NpActorDef *a)
{
    uint8_t i;
    for (i = 0; i < w->entity_count; i++) {
        NpEntity *o = &w->entities[i];
        const NpActorDef *oa;
        if (o == e || !o->active || o->kind != NP_KIND_ENEMY) continue;
        oa = np_entity_def(o);
        if (!np_boxes_overlap(e->x, e->y, a->box_w, a->box_h,
                              o->x, o->y, oa->box_w, oa->box_h))
            continue;
        /* al que esta mas arriba se va arriba, y al de abajo, abajo: asi los
           dos se separan aunque el otro no se mueva */
        e->y += (e->y <= o->y) ? -NP_I2F(1) : NP_I2F(1);
        return;                              /* con uno por frame basta */
    }
}

/* Un frame de luchador. Devuelve 1 si se ha ocupado el del movimiento. */
static void np_lucha_update(NpWorld *w, NpEntity *e, const NpEnemyDef *d,
                            const NpActorDef *a, const NpPlayer *p)
{
    np_fix dx = p->x - e->x;
    np_fix dy = (p->y + p->altura) - e->y;
    np_fix lejos = NP_ABS(dx);
    np_fix cerca = np_lucha_cerca(d, a);
    np_fix anillo = cerca + NP_I2F(22);
    /* De perfil no hay profundidad: la `y` es lo alto, y ahi manda la
       gravedad. Asi que el que pelea de perfil hace lo mismo que el de la
       cinta -se coloca, avisa, suelta y se aparta- pero **solo en x**: ni
       ranuras, ni rodear por detras, ni apartarse hacia dentro. Es el
       luchador de Bruce Lee: se te planta delante y te sacude. */
    int plano = !np_vista_cinta;
    /* Cada uno ronda por su profundidad: tres ranuras repartidas alrededor de
       donde esta el jugador. Sale del sitio que ocupa en la lista, asi que es
       el mismo en las dos implementaciones y no hace falta guardarlo. */
    int32_t ranura = plano ? 0 : ((int32_t)(e - w->entities) % 3 - 1) * 14;
    np_fix hacia_y;
    int32_t ex = 0, ey = 0;
    int puede, en_su_sitio = 0;

    if (!plano) np_lucha_separar(w, e, a);
    if (e->timer) e->timer--;
    /* mirar siempre al que tienes delante: darte la espalda no es dificultad,
       es un bicho tonto */
    if (dx) e->facing = (uint8_t)(dx > 0);

    switch (e->fase) {
    case NP_LUCHA_PREPARAR:
        e->vx = 0;
        if (!plano) e->vy = 0;
        if (!e->timer) {
            e->fase = NP_LUCHA_GOLPEAR;
            e->timer = d->active;
            e->tocado = 0;
        }
        np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_ATTACK);
        return;
    case NP_LUCHA_GOLPEAR:
        e->vx = 0;
        if (!plano) e->vy = 0;
        np_lucha_pegar(w, e, d, a);
        if (!e->timer) {
            e->fase = NP_LUCHA_RECUPERAR;
            e->timer = d->recover;
        }
        np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_ATTACK);
        return;
    case NP_LUCHA_RECUPERAR:
        e->vx = 0;
        if (!plano) e->vy = 0;
        if (!e->timer) {
            e->fase = NP_LUCHA_REPLEGAR;
            e->timer = d->wait;
        }
        np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_IDLE);
        return;
    case NP_LUCHA_REPLEGAR:
        /* pega y se aparta, como en los recreativos: asi te da sitio para
           responder y no se queda pegado a ti esperando el siguiente */
        ex = dx > 0 ? -1 : 1;
        if (NP_ABS(dy) > NP_I2F(2)) ey = dy > 0 ? -1 : 1;
        if (lejos > anillo + NP_I2F(16)) { ex = 0; ey = 0; }
        if (!e->timer) e->fase = NP_LUCHA_IR;
        break;
    default:
        /* IR y RONDAR: ponerse en su sitio.
         *
         * Aqui estan las dos reglas que hacen que la pelea se lea:
         *
         *   **Te rodean.** Cada uno tiene su lado -unos por la derecha y
         *   otros por la izquierda-, asi que no se hace una fila delante de
         *   ti: se reparten. De ahi sale que girarse importe, y de ahi sale
         *   el codazo.
         *
         *   **El que tiene turno se pone en tu linea y los demas se apartan a
         *   la suya.** Si todos rondaran por su ranura no pegaria nadie; si
         *   todos se pusieran en tu linea serian una fila de siete. Y
         *   mientras cruza al otro lado se queda en su ranura, para rodearte
         *   por delante o por detras en vez de atravesarte. */
        puede = (w->atacando < np_agresivos);
        {
            int32_t lado = ((int32_t)(e - w->entities) & 1) ? -1 : 1;
            np_fix quiero = puede ? cerca : anillo;
            np_fix destino = p->x + (np_fix)(lado * (int32_t)quiero);
            np_fix hueco_x = destino - e->x;
            /* "Estar en su sitio" es la **misma** medida que decide si puede
               pegar, y no dos parecidas: con dos, se paraba dentro de la
               tolerancia de andar pero justo fuera de la de pegar, y se
               quedaba mirando para siempre a un palmo del jugador. */
            en_su_sitio = NP_ABS(hueco_x) <= NP_I2F(6);
            if (!en_su_sitio) ex = hueco_x > 0 ? 1 : -1;
            hacia_y = (p->y + p->altura)
                    + NP_I2F((puede && en_su_sitio) ? 0 : ranura);
            (void)hacia_y;
            if (!plano) {
                np_fix hueco = hacia_y - e->y;
                if (NP_ABS(hueco) > NP_I2F(2)) ey = hueco > 0 ? 1 : -1;
            }
        }
        e->fase = (lejos <= anillo + NP_I2F(8)) ? NP_LUCHA_RONDAR : NP_LUCHA_IR;
        /* ¿le toca? Solo si hay ficha libre, ya ha esperado lo suyo, esta en
           su sitio y en tu linea de profundidad. */
        if (puede && !e->timer && en_su_sitio && NP_ABS(dy) <= NP_I2F(7)) {
            e->fase = NP_LUCHA_PREPARAR;
            e->timer = d->windup;
            e->vx = 0;
            if (!plano) e->vy = 0;
            w->atacando++;
            np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_ATTACK);
            return;
        }
        break;
    }
    e->vx = np_paso_cenital(d->speed, ex, ex && ey);
    if (!plano) e->vy = np_paso_cenital(d->speed, ey, ex && ey);
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer,
                (ex || ey) ? NP_ANIM_RUN : NP_ANIM_IDLE);
}

static void np_enemy_update(NpWorld *w, NpEntity *e)
{
    const NpEnemyDef *d = &np_enemies[e->def];
    const NpActorDef *a = &d->actor;
    const NpPlayer *p = np_nearest_player(w, e->x);
    int hit_x = 0, hit_down = 0, hit_up = 0;

    /* Derribado por un remate: no decide nada, solo resbala con el empujon que
       se llevo hasta que se le acaba y se levanta. Es lo que hace que encadenar
       sirva de algo: unos frames sin el encima. */
    if (e->knock) {
        np_fix suelo = e->y + e->altura;
        e->knock--;
        /* tumbado se pierde el turno: la ficha vuelve al monton y quien la
           coja tendra que volver a colocarse */
        e->fase = NP_LUCHA_IR;
        /* Si viene de un lanzamiento, ademas vuela: la altura sube y baja con
           la misma gravedad del jugador, y `y` -que es donde se dibuja- es el
           suelo menos la altura, igual que en np_player_update_cinta. */
        if (e->altura > 0 || e->valtura) {
            e->altura += e->valtura;
            e->valtura -= np_player_def.gravity;
            if (e->altura <= 0) { e->altura = 0; e->valtura = 0; }
        }
        e->x = np_move_x(w, e->x, suelo, a->box_w, a->box_h, e->vx, &hit_x);
        if (hit_x) e->vx = 0;
        e->y = suelo - e->altura;
        /* por el aire no se frena: se frena al tocar el suelo */
        if (!e->altura) e->vx = np_approach(e->vx, 0, np_player_def.friction);
        np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_HURT);
        np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
        return;
    }

    /* Tambaleandose de un golpe: ni decide ni anda, solo aguanta el empujon.
       Va antes que la IA a proposito -mientras dura, no hay IA- y despues del
       derribo, porque uno tumbado ya no se tambalea: esta en el suelo. */
    if (e->aturdido) {
        int golpe_x = 0;
        e->aturdido--;
        e->vx = np_approach(e->vx, 0, np_player_def.friction);
        e->vy = np_approach(e->vy, 0, np_player_def.friction);
        e->x = np_move_x(w, e->x, e->y, a->box_w, a->box_h, e->vx, &golpe_x);
        if (golpe_x) e->vx = 0;
        np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_HURT);
        np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
        return;
    }

    switch (d->behavior) {
    case NP_AI_PATROL:
        e->vx = e->facing ? d->speed : -d->speed;
        break;
    case NP_AI_FLYER: {
        np_fix phase;
        e->vx = e->facing ? d->speed : -d->speed;
        e->timer = (uint16_t)((e->timer + 1) % (d->period ? d->period : 1));
        phase = np_sin_table[(((int32_t)e->timer * 64) / (d->period ? d->period : 1)) & 63];
        /* En la isometrica lo que sube y baja es la **altura**, no la fila del
           mapa: un bicho que flota sobre los cubos y baja a por ti es medio
           genero. `amplitud:` es lo mismo de siempre, solo que ahora se mide
           hacia arriba y nunca baja del suelo. */
        if (np_vista_iso)
            e->altura = d->amplitude + ((d->amplitude * phase) >> NP_FIX_SHIFT);
        else
            e->y = e->home_y + ((d->amplitude * phase) >> NP_FIX_SHIFT);
        break;
    }
    case NP_AI_CHASER: {
        np_fix dx = p->x - e->x;
        /* En la vista de cinta un perseguidor no persigue: **pelea**. Se
           coloca, espera turno y suelta el golpe. Lo de andar en linea recta
           hacia el jugador se queda para los otros generos, donde el enemigo
           es un obstaculo y no un rival. */
        if (d->reach) {
            np_lucha_update(w, e, d, a, p);
            break;
        }
        if (np_vista_cenital) {
            /* Desde arriba se persigue en los dos ejes: es el soldado que se
               te viene encima. `rango` sigue midiendo en horizontal, que es
               como se escribe en el game.yaml. */
            np_fix dy = p->y - e->y;
            if (NP_ABS(dx) <= d->range && NP_ABS(dy) <= d->range) {
                int ex = NP_SIGN(dx), ey = NP_SIGN(dy);
                e->vx = np_paso_cenital(d->speed, ex, ex && ey);
                e->vy = np_paso_cenital(d->speed, ey, ex && ey);
                if (ex) e->facing = (uint8_t)(ex > 0);
            } else {
                e->vx = np_approach(e->vx, 0, d->speed);
                e->vy = np_approach(e->vy, 0, d->speed);
            }
            break;
        }
        if (NP_ABS(dx) <= d->range) {
            e->vx = dx > 0 ? d->speed : -d->speed;
            e->facing = (uint8_t)(dx > 0);
        } else {
            e->vx = np_approach(e->vx, 0, d->speed);
        }
        /* Un perseguidor va detras de ti mires donde mires, y con un agujero
           delante se tira por el y se pierde: si el que se cae es el jefe, el
           nivel ya no se puede terminar y no hay forma de saber por que. Con
           `borde: si` -lo de siempre- se planta en el borde y espera ahi. El
           que patrulla se da la vuelta mas abajo; este no, porque darse la
           vuelta seria dejar de perseguir. */
        if (d->edge_turn && e->vx != 0 && e->vy == 0
            && !np_suelo_delante(w, e, a, (uint8_t)(e->vx > 0)))
            e->vx = 0;
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

    /* La gravedad es de la vista lateral. Desde arriba nadie cae: lo que se
       mueve en vertical lo decide el comportamiento. */
    if (d->behavior != NP_AI_FLYER && !np_vista_cenital) {
        e->vy += d->gravity;
        if (e->vy > NP_ENTITY_FALL) e->vy = NP_ENTITY_FALL;
    }

    if (np_vista_iso) {
        /* Por la planta, con el relieve delante: un cubo frena a un bicho igual
           que a ti, y andando se sube a lo que no llegue al escalon. */
        int hit_y = 0;
        e->x = np_iso_move(w, e->x, e->y, a->box_w, a->box_h, e->vx, e->altura,
                           0, &hit_x);
        if (hit_x) {
            e->facing = (uint8_t)!e->facing;
            e->vx = 0;
        }
        e->y = np_iso_move(w, e->x, e->y, a->box_w, a->box_h, e->vy, e->altura,
                           1, &hit_y);
        if (hit_y) e->vy = 0;
        if (d->behavior != NP_AI_FLYER)
            e->altura = np_iso_suelo(w, e->x, e->y, a->box_w, a->box_h);
        np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer,
                    (e->vx || e->vy) ? NP_ANIM_RUN : NP_ANIM_IDLE);
        np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);
        if (d->shot) {
            if (e->vida) e->vida--;
            else np_enemy_shoot(w, e, d);
        }
        return;
    }

    e->x = np_move_x(w, e->x, e->y, a->box_w, a->box_h, e->vx, &hit_x);
    if (hit_x) {
        e->facing = (uint8_t)!e->facing;
        e->vx = 0;
    }
    if (np_vista_cenital) {
        /* desde arriba las paredes frenan tambien por arriba y por abajo */
        if (e->vy) {
            e->y = np_move_y(w, e->x, e->y, a->box_w, a->box_h, e->vy, 1,
                             &hit_down, &hit_up);
            if (hit_down || hit_up) e->vy = 0;
        }
    } else if (d->behavior != NP_AI_FLYER) {
        e->y = np_move_y(w, e->x, e->y, a->box_w, a->box_h, e->vy, 0,
                         &hit_down, &hit_up);
        if (hit_down && e->vy > 0) e->vy = 0;
        if (hit_up && e->vy < 0) e->vy = 0;

        if (hit_down && d->edge_turn && d->behavior == NP_AI_PATROL
            && !np_suelo_delante(w, e, a, e->facing))
            e->facing = (uint8_t)!e->facing;
    }

    /* Nota: `facing` manda sobre `vx` (es lo que decide la direccion del
     * proximo frame). No se recalcula aqui a partir de vx, porque eso
     * deshacia el giro en los bordes y en las paredes. */
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer,
                (e->vx || (np_vista_cenital && e->vy)) ? NP_ANIM_RUN
                                                       : NP_ANIM_IDLE);
    np_anim_tick(a, e->anim, &e->anim_frame, &e->anim_timer);

    /* Y si lleva `dispara:`, te tirotea. La cuenta atras va en `vida`, que en
       un enemigo no se usa para nada mas. */
    if (d->shot) {
        if (e->vida) e->vida--;
        else np_enemy_shoot(w, e, d);
    }

    /* caerse del mapa mata al enemigo (en cenital no hay de donde caerse) */
    if (!np_vista_cenital
        && NP_F2I(e->y) > (int32_t)(w->level->height + 2) * NP_TILE)
        e->active = 0;
}

static void np_item_update(NpWorld *w, NpEntity *e)
{
    const NpItemDef *d = &np_items[e->def];
    (void)w;
    /* los frames de gracia de lo que se acaba de soltar */
    if (e->timer) e->timer--;
    np_anim_set(&e->anim, &e->anim_frame, &e->anim_timer, NP_ANIM_IDLE);
    np_anim_tick(&d->actor, e->anim, &e->anim_frame, &e->anim_timer);
}

/* La pocima de Gauntlet: al cogerla, todo lo que se **ve** recibe un golpe.
 *
 * Lo que se ve y no todo el nivel: en una mazmorra hay bichos por todas
 * partes, y una pocima que limpiara el mapa entero se cargaria el juego. La
 * pantalla es la que dice la camara, asi que el reparto es el mismo en las
 * siete maquinas y en el preview -todas la calculan igual-, y por eso la
 * paridad sigue en pie.
 */
static void np_bomba(NpWorld *w, uint8_t dano)
{
    uint8_t i;
    if (!dano) dano = 1;
    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        const NpActorDef *ea;
        if (!e->active) continue;
        if (e->kind != NP_KIND_ENEMY && e->kind != NP_KIND_GENERATOR
            && e->kind != NP_KIND_BREAKABLE) continue;
        ea = np_entity_def(e);
        if (NP_F2I(e->x) + (int32_t)ea->box_w <= w->cam_x) continue;
        if (NP_F2I(e->x) >= w->cam_x + NP_SCREEN_W) continue;
        if (NP_F2I(e->y) + (int32_t)ea->box_h <= w->cam_y) continue;
        if (NP_F2I(e->y) >= w->cam_y + NP_SCREEN_H) continue;
        np_hit_entity(w, e, dano);
    }
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
    case NP_ITEM_WEAPON:
        /* Cambia el arma secundaria que se lleva. `amount` es su indice en
           np_subs, que pone el compilador a partir del nombre. */
        if (d->amount < np_sub_count) w->sub = d->amount;
        break;
    case NP_ITEM_BOMB:
        np_bomba(w, d->amount);
        break;
    case NP_ITEM_CARRY:
        /* No hace nada al cogerlo: se guarda. Y si no queda hueco en la bolsa
           **se queda donde estaba**, que es lo que obliga a elegir que llevas
           encima: en un Dizzy, la mitad del juego es esa decision. */
        if (!np_bolsa_meter(w, e->def)) return;
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
/* Abrir lo que se pueda de lo que tienes al lado.
 *
 * Una puerta se abre llegando con el objeto que pide: se gasta el objeto, la
 * casilla pasa a ser aire para siempre y suena. Es la otra mitad de una
 * aventura -la primera es cargar con las cosas- y lo que hace que un mapa
 * pequeno de una tarde de trabajo de mas juego que un nivel largo.
 *
 * Se apunta la casilla abierta en una lista y no se toca el mapa: el mapa vive
 * en ROM. Si se llena la lista no se abre ninguna mas, que es mejor que abrir
 * una y que se cierre sola al frame siguiente.
 */
/* Apunta una casilla como abierta. Devuelve 0 si la lista ya estaba llena. */
static int np_apuntar_abierta(NpWorld *w, uint16_t casilla)
{
    if (w->abiertos_n >= NP_MAX_ABIERTOS) return 0;
    w->abiertos[w->abiertos_n++] = casilla;
    return 1;
}

/* Una puerta de dos casillas es **una puerta**, no dos: se abre entera con un
 * solo objeto. Desde la casilla que se ha abierto se sigue el rastro en las
 * cuatro direcciones mientras haya el mismo tile, que es como se dibuja una
 * puerta alta (una columna) o un paso ancho (una fila).
 */
static void np_abrir_vecinas(NpWorld *w, int32_t tx, int32_t ty, uint16_t tile)
{
    static const int8_t pasos[4][2] = {{0, -1}, {0, 1}, {-1, 0}, {1, 0}};
    uint8_t d;
    for (d = 0; d < 4; d++) {
        int32_t x = tx, y = ty;
        for (;;) {
            uint16_t casilla;
            x += pasos[d][0];
            y += pasos[d][1];
            if (x < 0 || y < 0 || x >= (int32_t)w->level->cells_w
                || y >= (int32_t)w->level->cells_h) break;
            casilla = (uint16_t)(y * (int32_t)w->level->cells_w + x);
            if (w->level->cells[casilla] != tile) break;
            if (np_tile_visto(w, x, y) != NP_TILE_LOCK) break;
            if (!np_apuntar_abierta(w, casilla)) return;
        }
    }
}

static void np_abrir_cerrojos(NpWorld *w, int32_t tx0, int32_t ty0,
                              int32_t tx1, int32_t ty1)
{
    int32_t tx, ty;
    if (!np_bolsa_activa) return;
    for (ty = ty0; ty <= ty1; ty++) {
        for (tx = tx0; tx <= tx1; tx++) {
            uint16_t casilla;
            uint8_t pide, hueco, i;
            if (tx < 0 || ty < 0 || tx >= (int32_t)w->level->cells_w
                || ty >= (int32_t)w->level->cells_h) continue;
            if (np_tile_visto(w, tx, ty) != NP_TILE_LOCK) continue;
            casilla = (uint16_t)(ty * (int32_t)w->level->cells_w + tx);
            pide = np_tile_need[w->level->cells[casilla]];
            if (!pide) continue;                 /* un cerrojo sin llave: nunca */
            hueco = np_bolsa_busca(w, (uint8_t)(pide - 1));
            if (!hueco) continue;                /* no llevas lo que pide */
            if (w->abiertos_n >= NP_MAX_ABIERTOS) return;
            /* el objeto se gasta y la bolsa se cierra por delante, para que no
               queden huecos en medio */
            for (i = (uint8_t)(hueco - 1); i + 1 < NP_BOLSA; i++)
                w->bolsa[i] = w->bolsa[i + 1];
            w->bolsa[NP_BOLSA - 1] = 0;
            np_apuntar_abierta(w, casilla);
            np_abrir_vecinas(w, tx, ty, w->level->cells[casilla]);
            w->sfx |= NP_SFX_CHECK;
        }
    }
}

static void np_check_touch(NpWorld *w, uint8_t quien)
{
    const NpActorDef *a = &np_player_def.actor;
    const NpPlayer *p = &w->players[quien];
    int32_t tx0 = NP_F2I(p->x) >> NP_TILE_SHIFT;
    int32_t tx1 = NP_F2I(p->x + NP_I2F(a->box_w) - 1) >> NP_TILE_SHIFT;
    int32_t ty0 = NP_F2I(p->y) >> NP_TILE_SHIFT;
    int32_t ty1 = NP_F2I(p->y + NP_I2F(a->box_h) - 1) >> NP_TILE_SHIFT;
    int32_t tx, ty;
    /* Los cerrojos se miran un poco mas alla de la caja: una puerta se abre
       **poniendote delante**, no metiendote dentro, y dentro no se puede
       estar porque frena como una pared. */
    np_abrir_cerrojos(w, tx0 - 1, ty0, tx1 + 1, ty1);
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
            if (!np_boxes_overlap(p->x, np_player_top(p), pa->box_w,
                                  np_player_height(p),
                                  e->x, e->y, ea->box_w, ea->box_h))
                continue;
            /* En la isometrica no basta con pisar la misma casilla: hay que
               cruzarse **tambien en altura**. Es lo que convierte el salto en
               una forma de esquivar, que es de lo que va el genero. */
            if (np_vista_iso) {
                np_fix hueco = p->altura - e->altura;
                if (hueco > NP_I2F(12) || hueco < -NP_I2F(12)) continue;
            }
            if (e->kind == NP_KIND_SHOT || e->kind == NP_KIND_SUBSHOT)
                continue;                            /* es tuyo: no te toca */
            if (e->kind == NP_KIND_MELEE) continue;  /* es tu propio latigo */
            if (e->kind == NP_KIND_PLATFORM) continue;   /* es suelo, no un bicho */
            if (e->kind == NP_KIND_BREAKABLE) continue;  /* hay que pegarle */
            if (e->kind == NP_KIND_GENERATOR) continue;  /* tambien: y no hace dano */
            /* uno en el suelo no hace dano: por eso se remata */
            if (e->kind == NP_KIND_ENEMY && e->knock) continue;
            /* Y al que se tambalea de un golpe se le coge: pegar, coger y
               rematar es la escalera entera de un juego de tortas. Se mira el
               parpadeo -o sea, que acabas de tocarle- porque asi el agarre es
               algo que te ganas y no algo que pasa al rozar a nadie. */
            if (np_player_def.grab_time && e->kind == NP_KIND_ENEMY
                && e->hurt && !p->grab && !p->dying) {
                p->grab = (uint8_t)(i + 1);
                p->grab_timer = np_player_def.grab_time;
                e->knock = 0;
                w->sfx |= NP_SFX_STOMP;
                continue;
            }
            if (e->kind == NP_KIND_ENEMY_SHOT) continue; /* se mira en su update */
            if (e->kind == NP_KIND_PRISONER) {
                np_prisoner_free(w, e, p);               /* tocarlo lo suelta */
                continue;
            }
            if (e->kind == NP_KIND_ITEM) {
                /* lo que acabas de soltar no se recoge solo */
                if (!e->timer) np_collect(w, quien, e);
                continue;
            }
            {
                const NpEnemyDef *d = &np_enemies[e->def];
                /* En una pelea, rozar a alguien no hace dano: hace dano su
                   golpe. Es la diferencia entre un obstaculo y un rival, y sin
                   ella no hay forma de acercarse a nadie. Solo vale para los
                   que pegan (`golpe:` con alcance) y en la vista de cinta: en
                   el resto de generos tocar a un bicho sigue costandote vida,
                   como toda la vida. */
                if (d->reach) continue;
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
                    /* si estaba parpadeando, el golpe no entra: entonces
                       tampoco hay por que apartarse */
                    int cobrado = !p->invuln && !p->dying;
                    np_player_hurt(w, quien, d->damage);
                    /* En un juego de tortas, el que te acaba de pegar **se
                       aparta**: pega y recula, como en los recreativos. Sin
                       esto se te queda encima y te vuelve a dar en cuanto se
                       acaba el parpadeo, y tres a la vez no hay quien los
                       aguante. Fuera de la cinta no pasa nada de esto: los
                       demas generos siguen exactamente igual. */
                    if (np_vista_cinta && cobrado) {
                        e->knock = NP_RECULA;
                        e->vx = (e->x < p->x) ? -np_player_def.knockback
                                              : np_player_def.knockback;
                        e->vy = 0;
                    }
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
/* El orden en que se dibujan las entidades: de mas lejos a mas cerca.
 *
 * Solo hace algo en la vista de cinta, que es donde dos actores se pisan a
 * cada rato y hay un "detras" de verdad: la linea del suelo (y + altura). En
 * las demas vistas devuelve el orden de la lista tal cual, asi que no cambia
 * nada de lo que ya funcionaba ni cuesta un ciclo.
 *
 * Es una ordenacion por insercion porque la lista viene casi ordenada de un
 * frame al siguiente -nadie se teletransporta- y ahi la insercion es lineal.
 */
/* La lista de siempre: 0, 1, 2... Va en ROM y no se toca, asi que fuera de la
   vista de cinta pedir el orden no cuesta **nada**: ni una vuelta de bucle.
   Se noto en el Atari ST, que es la maquina mas justa de las siete: montar la
   lista cada frame le comia los ciclos que necesita para ir a su ritmo, y la
   musica -que va por frames- empezo a sonar lenta. */
static const uint8_t np_identidad[NP_MAX_ENTITIES] = {
    0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
   16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
   32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
   48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63
};

/* En la isometrica la fila lleva ademas a los jugadores, asi que hacen falta
   dos puestos mas: los cubos ya salen de la propia lista de entidades. */
static uint8_t np_orden[NP_MAX_ENTITIES + NP_MAX_PLAYERS];

/* La hondura de cada uno, apuntada una sola vez por frame.
 *
 * Ordenar preguntando la hondura en cada comparacion son cuatrocientas
 * llamadas por frame en cuanto la sala tiene veinte cubos. Medido en la Mega
 * Drive: 145 de las 262 lineas que dura un frame, o sea que el juego perdia el
 * retrazo y se iba a la mitad de velocidad. Con los numeros ya sacados, catorce. */
static np_fix np_hondo[NP_MAX_ENTITIES + NP_MAX_PLAYERS];

/* Los cubos de la sala no se mueven ni se animan mientras no cambies de
 * habitacion, asi que donde caen en la pantalla se saca al montarla y el
 * dibujado solo lo lee. Otras 35 lineas de las 262. */
static const NpActorDef *np_cubo_def[NP_MAX_ENTITIES];
static int16_t np_cubo_px[NP_MAX_ENTITIES];
static int16_t np_cubo_py[NP_MAX_ENTITIES];

/* La hondura de un puesto de la lista: cuanto mas grande, mas cerca de quien
 * mira, y por lo tanto mas tarde se dibuja.
 *
 * En la cinta es la linea del suelo. En la isometrica es la profundidad de la
 * planta (x + y), y la altura entra como desempate pequeno: quien esta subido
 * a un cubo va **despues** que el cubo, y como un octavo de la altura nunca
 * llega a lo que mide una casilla, subirse a algo no adelanta a lo que hay una
 * casilla mas cerca. */
static np_fix np_hondura(const NpWorld *w, uint8_t puesto)
{
    if (puesto >= NP_MAX_ENTITIES) {
        const NpPlayer *p = &w->players[puesto - NP_MAX_ENTITIES];
        return np_vista_iso ? (p->x + p->y + (p->altura >> 3))
                            : (p->y + p->altura);
    }
    {
        const NpEntity *e = &w->entities[puesto];
        return np_vista_iso ? (e->x + e->y + (e->altura >> 3))
                            : (e->y + e->altura);
    }
}

const uint8_t *np_orden_dibujo(const NpWorld *w, uint8_t *cuantas)
{
    uint8_t *orden = np_orden;
    np_fix *hondo = np_hondo;
    uint8_t n = 0, i;

    if (!np_vista_cinta && !np_vista_iso) {
        *cuantas = w->entity_count;
        return np_identidad;
    }
    for (i = 0; i < w->entity_count; i++) {
        if (!w->entities[i].active) continue;
        /* Lo que esta en otra habitacion no se dibuja, asi que tampoco entra
           en la fila: ni se ordena ni se pregunta por el. */
        if (np_vista_iso && !np_en_la_sala(w, &w->entities[i])) continue;
        hondo[n] = np_hondura(w, i);
        orden[n++] = i;
    }
    if (np_vista_iso) {
        /* Los cubos de la sala, que viven al final de la lista. Se recorren
           del ultimo hacia atras porque asi salen en orden de profundidad -es
           el orden en que los monto np_bloques_sala- y la ordenacion de abajo,
           que es por insercion, casi no tiene que moverlos.

           Y los jugadores, que en esta vista **entran en la fila**: aqui hay un
           detras de verdad y uno se mete tras un cubo cada dos pasos. En las
           demas vistas se siguen dibujando al final, encima de todo, como
           siempre. */
        for (i = 0; i < w->bloques_n; i++) {
            uint8_t sitio = (uint8_t)(NP_MAX_ENTITIES - 1 - i);
            hondo[n] = np_hondura(w, sitio);
            orden[n++] = sitio;
        }
        for (i = 0; i < NP_MAX_PLAYERS; i++) {
            uint8_t sitio = (uint8_t)(NP_MAX_ENTITIES + i);
            hondo[n] = np_hondura(w, sitio);
            orden[n++] = sitio;
        }
    }
    *cuantas = n;
    for (i = 1; i < n; i++) {
        uint8_t sitio = orden[i];
        np_fix h = hondo[i];
        int j = (int)i - 1;
        while (j >= 0 && hondo[j] > h) {
            orden[j + 1] = orden[j];
            hondo[j + 1] = hondo[j];
            j--;
        }
        orden[j + 1] = sitio;
        hondo[j + 1] = h;
    }
    return orden;
}

/* Queda alguien vivo en la pantalla?
 *
 * Es la pregunta de la que vive el genero de tortas: mientras la respuesta sea
 * que si, la camara no pasa de ahi. Un pasillo por el que se puede seguir
 * andando no es una pelea; una pantalla de la que no se sale hasta limpiarla,
 * si. Se mira la pantalla de ahora -y no el nivel entero- para que la pelea sea
 * la que se ve. */
static int np_alguien_en_pantalla(const NpWorld *w)
{
    uint8_t i;
    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
        const NpActorDef *ea;
        if (!e->active || e->kind != NP_KIND_ENEMY) continue;
        ea = np_entity_def(e);
        if (NP_F2I(e->x) + (int32_t)ea->box_w <= w->cam_x) continue;
        if (NP_F2I(e->x) >= w->cam_x + NP_SCREEN_W) continue;
        return 1;
    }
    return 0;
}

/* ------------------------------------------------- la pantalla y las salas */

void np_pantalla(const NpWorld *w, np_fix x, np_fix y, np_fix altura,
                 const NpActorDef *def, int32_t *sx, int32_t *sy)
{
    if (!np_vista_iso) {
        *sx = NP_F2I(x) - def->box_x;
        *sy = NP_F2I(y) - def->box_y;
        (void)w;
        (void)altura;
        return;
    }
    {
        /* El punto que manda es donde apoya los pies: el centro de su caja en
           la planta. Es lo unico que tiene sentido cuando el suelo son rombos
           -una esquina de la caja caeria en otra casilla-. */
        int32_t px = NP_F2I(x) + def->box_w / 2;
        int32_t py = NP_F2I(y) + def->box_h / 2;
        /* Solo cuenta el sitio **dentro de la sala**: todas las salas se
           dibujan en el mismo cuadro de pantalla y la camara no se mueve
           nunca. De eso vive el que un castillo de veinte habitaciones ocupe
           lo que una pantalla -tanto de dibujo de fondo como de mapa de bits
           en las maquinas que llevan uno-, y ademas es lo que hace que
           cambiar de sala sea un corte y no un viaje. */
        int32_t lx = px & (NP_SALA_PX - 1);
        int32_t ly = py & (NP_SALA_PX - 1);
        /* Y de ahi al dibujo: la esquina de arriba a la izquierda del
           fotograma, sabiendo que los pies van en el centro de abajo de la
           caja. Con las medidas de siempre -caja centrada y apoyada- eso es el
           centro de abajo del cuadro, que es donde uno espera. */
        *sx = NP_ISO_OX + (lx - ly) - (def->box_x + def->box_w / 2);
        *sy = NP_ISO_OY + ((lx + ly) >> 1)
              - NP_F2I(altura) - (def->box_y + def->box_h);
    }
}

/* Montar los cubos de la sala que se esta viendo.
 *
 * Se recorre su planta y por cada casilla que levanta y trae dibujo se pone
 * una entidad con su cubo. Van al **final** de la lista -de NP_MAX_ENTITIES
 * hacia atras- para no pisar los huecos que buscan los disparos, y por
 * diagonales, o sea en orden de profundidad, para que la fila del dibujado
 * salga ya casi ordenada.
 *
 * Se rehace entera al cambiar de sala. Es lo que permite que un castillo de
 * veinte habitaciones quepa en sesenta y cuatro huecos: solo existen los
 * cubos de la habitacion en la que estas. */
static void np_bloques_sala(NpWorld *w)
{
    const NpLevel *lv = w->level;
    int32_t base_x = (int32_t)w->sala_x * NP_SALA;
    int32_t base_y = (int32_t)w->sala_y * NP_SALA;
    int32_t d;
    uint8_t sitio;
    uint8_t n = 0;
    uint8_t tope = (uint8_t)(NP_MAX_ENTITIES - w->entity_count);

    for (sitio = 0; sitio < w->bloques_n; sitio++)
        w->entities[NP_MAX_ENTITIES - 1 - sitio].active = 0;
    w->bloques_n = 0;
    if (!np_vista_iso) return;

    for (d = 0; d <= (NP_SALA - 1) * 2; d++) {
        int32_t cy;
        for (cy = 0; cy < NP_SALA; cy++) {
            int32_t cx = d - cy;
            int32_t mx, my;
            uint8_t tile, cubo;
            NpEntity *e;
            if (cx < 0 || cx >= NP_SALA) continue;
            /* Si la sala trae mas cubos de los que caben, se montan los que
               quepan y se deja la cuenta bien puesta: salir de aqui sin
               apuntar cuantos son dejaba la sala **sin un solo cubo**. */
            if (n >= tope) goto fin;
            mx = base_x + cx;
            my = base_y + cy;
            if (mx < 0 || mx >= (int32_t)lv->cells_w) continue;
            if (my < 0 || my >= (int32_t)lv->cells_h) continue;
            tile = lv->cells[my * lv->cells_w + mx];
            cubo = np_tile_bloque[tile];
            if (!cubo) continue;
            /* una puerta ya abierta no se dibuja: es un hueco por el que pasar */
            if (np_tile_kind[tile] == NP_TILE_LOCK
                && np_tile_visto(w, mx, my) == NP_TILE_EMPTY) continue;
            e = &w->entities[NP_MAX_ENTITIES - 1 - n];
            n++;
            e->active = 1;
            e->kind = NP_KIND_BLOQUE;
            e->def = (uint8_t)(cubo - 1);
            e->x = NP_I2F(mx * NP_TILE);
            e->y = NP_I2F(my * NP_TILE);
            e->home_x = e->x;
            e->home_y = e->y;
            e->vx = 0;
            e->vy = 0;
            e->altura = 0;
            e->valtura = 0;
            e->vida = 0;
            e->timer = 0;
            e->anim = NP_ANIM_IDLE;
            e->anim_frame = 0;
            e->anim_timer = 0;
            e->facing = 1;
            e->health = 1;
            e->hurt = 0;
            e->knock = 0;
            e->golpeado = 0;
            e->fase = NP_LUCHA_IR;
            e->tocado = 0;
            e->aturdido = 0;
            /* Donde cae en la pantalla, ahora y no en cada frame: un cubo no
               se mueve mientras no cambies de habitacion. */
            {
                const NpActorDef *bd = &np_bloques[e->def].actor;
                int32_t bx, by;
                np_pantalla(w, e->x, e->y, e->altura, bd, &bx, &by);
                np_cubo_def[n - 1] = bd;
                np_cubo_px[n - 1] = (int16_t)bx;
                np_cubo_py[n - 1] = (int16_t)by;
            }
        }
    }
fin:
    w->bloques_n = n;
    w->bloques_abiertos = w->abiertos_n;
}

/* La camara de la vista isometrica: no sigue a nadie, ensena **la sala**. Se
 * mira en que habitacion esta el jugador y se salta ahi de golpe, que es como
 * se cambiaba de cuarto en todos los juegos del genero -y ademas es lo que
 * permite que solo existan los cubos de la sala de ahora-. */
static void np_camara_iso(NpWorld *w)
{
    const NpActorDef *a = &np_player_def.actor;
    const NpPlayer *p = &w->players[0];
    int32_t px, py, sx, sy, salas_x, salas_y;
    uint8_t i;
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        if (!w->players[i].playing) continue;
        p = &w->players[i];
        break;
    }
    px = NP_F2I(p->x) + a->box_w / 2;
    py = NP_F2I(p->y) + a->box_h / 2;
    if (px < 0) px = 0;
    if (py < 0) py = 0;
    sx = px >> NP_SALA_SHIFT;
    sy = py >> NP_SALA_SHIFT;
    salas_x = (int32_t)w->level->cells_w / NP_SALA;
    salas_y = (int32_t)w->level->cells_h / NP_SALA;
    if (salas_x < 1) salas_x = 1;
    if (salas_y < 1) salas_y = 1;
    sx = NP_CLAMP(sx, 0, salas_x - 1);
    sy = NP_CLAMP(sy, 0, salas_y - 1);
    /* Al abrir un cerrojo la puerta pasa a ser un hueco: hay que rehacer los
       cubos de la sala o la puerta se quedaria dibujada hasta que salgas de la
       habitacion. */
    if ((uint16_t)sx != w->sala_x || (uint16_t)sy != w->sala_y
        || w->bloques_abiertos != w->abiertos_n) {
        w->sala_x = (uint16_t)sx;
        w->sala_y = (uint16_t)sy;
        np_bloques_sala(w);
    }
    /* La camara se queda quieta: la sala se dibuja siempre en el mismo sitio
       y lo que cambia es lo que hay dentro. */
    w->cam_x = 0;
    w->cam_y = 0;
}

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
    /* La isometrica no sigue a nadie: ensena la sala en la que estas. */
    if (np_vista_iso) { np_camara_iso(w); return; }
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        if (!w->players[i].playing) continue;
        centro_x += NP_F2I(w->players[i].x) + a->box_w / 2;
        /* En la cinta manda la linea del suelo y no donde se dibuja: si no, la
           camara daria un brinco con cada salto. */
        centro_y += NP_F2I(w->players[i].y + w->players[i].altura) + a->box_h / 2;
        cuantos++;
    }
    if (!cuantos) {
        /* game over: no queda nadie en juego, pero la camara tiene que
           quedarse donde estaba y no irse al origen */
        centro_x = NP_F2I(w->players[0].x) + a->box_w / 2;
        centro_y = NP_F2I(w->players[0].y + w->players[0].altura) + a->box_h / 2;
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
    /* El cerrojo del genero de tortas: con alguien vivo en pantalla la camara
       no avanza. Hacia atras si se mueve -si el jugador retrocede, se le
       sigue-, porque lo que se cierra es el paso, no la vista. */
    if (np_vista_cinta && target_x > w->cam_x && np_alguien_en_pantalla(w))
        target_x = w->cam_x;
    w->cam_x = NP_CLAMP(target_x, 0, max_x);
    w->cam_y = NP_CLAMP(target_y, 0, max_y);
    /* La sacudida: al tumbar a alguien la pantalla tiembla unos frames. Es
     * decorado, pero es el decorado que hace que un derribo parezca un
     * derribo, y sale gratis en las siete maquinas porque va en la camara y
     * la camara la miran todas.
     *
     * Se mueve **hacia dentro del nivel** (siempre sumando) y se vuelve a
     * recortar: asi no se ve nunca fuera del mapa, ni siquiera pegado al
     * borde izquierdo, que es justo donde empieza una calle. */
    if (w->sacudida) {
        w->sacudida--;
        if (w->sacudida & 2) {
            w->cam_x += 3;
            if (w->cam_x > max_x) w->cam_x = max_x;
        }
    }
}

/* Se ha cambiado de pantalla? Entonces los perseguidores tenaces entran detras
 * de ti. Se mira por la camara -y no por el jugador- porque lo que decide que
 * es "otra pantalla" es ella, y asi vale igual con uno que con dos.
 *
 * Va aparte de np_camera_update y se llama solo desde el paso del frame. Antes
 * estaba dentro, y entonces empezar un nivel movia la camara de la pantalla
 * donde te acababas de morir a la de la salida: eso era un cambio de pantalla
 * como otro cualquiera y los tenaces aparecian pegados a ti nada mas revivir,
 * en un sitio distinto ademas del que dice el mapa. Empezar un nivel no es
 * cruzar una puerta.
 */
static void np_cambio_de_pantalla(NpWorld *w)
{
    uint16_t px, py;
    if (!np_camara_pantallas) return;
    px = (uint16_t)(w->cam_x / NP_SCREEN_W);
    py = (uint16_t)(w->cam_y / NP_SCREEN_H);
    if (px == w->pantalla_x && py == w->pantalla_y) return;
    {
        int32_t dx = (int32_t)px - (int32_t)w->pantalla_x;
        int32_t dy = (int32_t)py - (int32_t)w->pantalla_y;
        w->pantalla_x = px;
        w->pantalla_y = py;
        np_tenaces_siguen(w, dx, dy);
    }
}

/* --- los perseguidores tenaces --------------------------------------------
 *
 * Un enemigo con `tenaz:` no vive en una pantalla: vive detras de ti. Al
 * cruzar a la pantalla de al lado aparece por el borde por el que has entrado
 * -o sea, viniendo por donde tu venias- y sigue a lo suyo.
 *
 * Lo que hace esto no es un truco de dibujo: cambia lo que significa una
 * pantalla. Sin ellos, cada pantalla es un puzle que se resuelve con calma y
 * el bicho de al lado se queda al lado. Con ellos, entretenerse cuesta, y
 * volver sobre tus pasos es meterte de cabeza en el que venia detras.
 *
 * Se les coloca a ras del borde y a la altura del jugador -que es un sitio por
 * el que se puede andar, porque el jugador esta ahi-, y se les separa un poco
 * entre ellos para que dos no entren pegados. Lo demas ya lo hace su IA de
 * siempre: en cuanto estan dentro, persiguen.
 */
static void np_tenaces_siguen(NpWorld *w, int32_t dx, int32_t dy)
{
    const NpPlayer *p = &w->players[0];
    int32_t izq = w->cam_x, der = w->cam_x + NP_SCREEN_W;
    int32_t arr = w->cam_y, aba = w->cam_y + NP_SCREEN_H;
    uint8_t i, cuantos = 0;

    /* Con dos jugadores, el que mande es el primero que siga en juego. */
    for (i = 0; i < NP_MAX_PLAYERS; i++)
        if (w->players[i].playing && !w->players[i].dying) { p = &w->players[i]; break; }

    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        const NpEnemyDef *ed;
        int32_t x, y;
        if (!e->active || e->kind != NP_KIND_ENEMY) continue;
        ed = &np_enemies[e->def];
        if (!ed->tenaz) continue;

        /* De donde vienes tu: si has ido a la derecha, ellos entran por la
           izquierda. Uno detras de otro, separados media pantalla de nada. */
        x = NP_F2I(p->x);
        y = NP_F2I(p->y);
        if (dx > 0)      x = izq + 2 + cuantos * (ed->actor.box_w + 8);
        else if (dx < 0) x = der - ed->actor.box_w - 2 - cuantos * (ed->actor.box_w + 8);
        if (dy > 0)      y = arr + 2;
        else if (dy < 0) y = aba - ed->actor.box_h - 2;
        if (x < izq) x = izq;
        if (x > der - ed->actor.box_w) x = der - ed->actor.box_w;
        if (y < arr) y = arr;
        if (y > aba - ed->actor.box_h) y = aba - ed->actor.box_h;

        e->x = NP_I2F(x);
        e->y = NP_I2F(y);
        e->vx = 0;
        e->vy = 0;
        e->home_x = e->x;
        e->home_y = e->y;
        e->facing = (dx >= 0) ? 1 : 0;
        e->hurt = 0;
        e->knock = 0;
        e->fase = NP_LUCHA_IR;
        e->timer = ed->interval;
        cuantos++;
    }
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
    if (np_player_count < 2 || np_vista_iso) return;
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        NpPlayer *p = &w->players[i];
        if (!p->playing || p->dying) continue;
        if (NP_F2I(p->x) < izquierda) { p->x = NP_I2F(izquierda); if (p->vx < 0) p->vx = 0; }
        if (NP_F2I(p->x) > derecha) { p->x = NP_I2F(derecha); if (p->vx > 0) p->vx = 0; }
    }
}

/* Que hay que dibujar en un puesto de la fila, y donde cae.
 *
 * Es el unico sitio donde se decide eso, y por eso los seis dibujantes de
 * maquina tienen **un solo bucle**: piden el orden, y por cada puesto piden
 * aqui el actor, su fotograma, si va del reves y en que pixel de la pantalla
 * empieza (sin restar la camara: eso lo hace cada maquina a su manera). Un
 * puesto por debajo de NP_MAX_ENTITIES es una entidad y de ahi para arriba es
 * el jugador que diga la diferencia.
 *
 * Devuelve cero cuando en ese puesto no hay nada que pintar: una entidad
 * apagada, una que esta en mitad del parpadeo de dano o un jugador que no
 * esta en juego. */
/* Esta esa entidad en la sala que se esta viendo? */
static int np_en_la_sala(const NpWorld *w, const NpEntity *e)
{
    int32_t px = NP_F2I(e->x), py = NP_F2I(e->y);
    if (px < 0) px = 0;
    if (py < 0) py = 0;
    return (px >> NP_SALA_SHIFT) == (int32_t)w->sala_x
        && (py >> NP_SALA_SHIFT) == (int32_t)w->sala_y;
}

const NpActorDef *np_dibujo(const NpWorld *w, uint8_t puesto,
                            int32_t *sx, int32_t *sy,
                            uint8_t *frame, uint8_t *flip)
{
    const NpActorDef *def;
    if (puesto >= NP_MAX_ENTITIES) {
        uint8_t quien = (uint8_t)(puesto - NP_MAX_ENTITIES);
        const NpPlayer *p = &w->players[quien];
        if (!np_player_visible(w, quien)) return 0;
        def = &np_player_def.actor;
        np_pantalla(w, p->x, p->y, p->altura, def, sx, sy);
        *frame = np_actor_frame(def, p->anim, p->anim_frame);
        *flip = (uint8_t)!p->facing;
        return def;
    }
    /* Un cubo de la sala: el sitio ya esta sacado y no se anima, asi que aqui
       no hay nada que calcular. */
    if (np_vista_iso && puesto >= (uint8_t)(NP_MAX_ENTITIES - w->bloques_n)) {
        uint8_t cual = (uint8_t)(NP_MAX_ENTITIES - 1 - puesto);
        *sx = np_cubo_px[cual];
        *sy = np_cubo_py[cual];
        *frame = 0;
        *flip = 0;
        return np_cubo_def[cual];
    }
    {
        const NpEntity *e = &w->entities[puesto];
        if (!e->active) return 0;
        if (e->hurt && (w->frame & 1)) return 0;      /* parpadeo al recibir */
        /* Todas las salas se dibujan en el mismo cuadro, asi que lo que esta
           en otra habitacion caeria encima de esta: no se pinta. */
        if (np_vista_iso && !np_en_la_sala(w, e)) return 0;
        def = np_entity_def(e);
        np_pantalla(w, e->x, e->y, e->altura, def, sx, sy);
        *frame = np_actor_frame(def, e->anim, e->anim_frame);
        *flip = (uint8_t)!e->facing;
        return def;
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

    /* Cuantos estan pegando ahora mismo. Se cuenta **una vez** y de ahi salen
       las fichas de ataque: mientras haya `np_agresivos` ocupados, el resto
       ronda. Contarlo aqui y no llevar la cuenta a mano es lo que hace que no
       se pierda una ficha cuando a uno lo tumban o se lo llevan por delante en
       mitad del golpe. */
    w->atacando = 0;
    if (np_vista_cinta) {
        for (i = 0; i < w->entity_count; i++) {
            const NpEntity *e = &w->entities[i];
            if (!e->active || e->kind != NP_KIND_ENEMY) continue;
            if (e->knock || e->fase < NP_LUCHA_PREPARAR
                || e->fase > NP_LUCHA_RECUPERAR) continue;
            w->atacando++;
        }
    }

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
        /* La ventana para encadenar corre aqui, antes de leer el mando, y no
           en cada vista: asi la serie va igual se mire desde donde se mire. */
        if (p->combo_timer) p->combo_timer--;
        if (p->dying) np_player_falling(w, quien);
        else if (np_vista_iso)
            np_player_update_iso(w, quien, mandos[quien]);
        else if (np_vista_cinta)
            np_player_update_cinta(w, quien, mandos[quien]);
        else if (np_vista_cenital)
            np_player_update_cenital(w, quien, mandos[quien]);
        else np_player_update(w, quien, mandos[quien]);
    }

    for (i = 0; i < w->entity_count; i++) {
        NpEntity *e = &w->entities[i];
        int32_t dx;
        int fuera;
        if (!e->active) continue;
        if (e->kind == NP_KIND_BLOQUE) continue;   /* los cubos no hacen nada */
        if (np_vista_iso) {
            /* Aqui "fuera de la vista" es "en otra habitacion": lo que pasa en
               el cuarto de al lado no se ve y no corre. */
            fuera = !np_en_la_sala(w, e);
        } else {
            dx = NP_F2I(e->x) - (int32_t)w->cam_x;
            fuera = (dx < -NP_CULL_MARGIN || dx > NP_SCREEN_W + NP_CULL_MARGIN);
        }
        if (fuera) {
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
        if (e->kind == NP_KIND_MELEE) continue;        /* lo lleva el jugador */
        if (e->hurt) e->hurt--;
        if (e->kind == NP_KIND_SHOT) np_shot_update(w, e);
        else if (e->kind == NP_KIND_SUBSHOT) np_subshot_update(w, e);
        else if (e->kind == NP_KIND_ENEMY_SHOT) np_enemy_shot_update(w, e);
        else if (e->kind == NP_KIND_PRISONER) np_prisoner_update(w, e);
        else if (e->kind == NP_KIND_GENERATOR) np_generator_update(w, e);
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
        /* Saltando por encima de un pincho no pasa nada: en la isometrica la
           altura es de verdad, y esquivar saltando es medio juego. */
        if ((!np_vista_iso || p->altura <= NP_I2F(NP_ISO_PISA))
            && np_box_touches(w,
                           p->x + NP_I2F(NP_HAZARD_INSET_X),
                           np_player_top(p) + NP_I2F(NP_HAZARD_INSET_Y),
                           pa->box_w - NP_HAZARD_INSET_X * 2,
                           np_player_height(p) - NP_HAZARD_INSET_Y,
                           NP_TILE_HAZARD)) {
            np_player_hurt(w, quien, 99);
            continue;
        }
        np_player_wear(w, quien);
        if (p->dying) continue;
        np_check_touch(w, quien);
        /* La meta solo se abre si se llevan las llaves que pide el nivel. Las
         * llaves son de la partida, no de cada jugador: a dos, las que coge
         * uno le valen al otro. */
        if (w->keys >= w->level->keys_needed &&
            (!np_vista_iso || p->altura <= NP_I2F(NP_ISO_PISA)) &&
            np_box_touches(w, p->x, p->y, pa->box_w, pa->box_h,
                           NP_TILE_GOAL)) {
            np_finish_level(w);            /* llega uno, se acaba para los dos */
            return;
        }
        /* Caerse del mapa: en la isometrica no hay de donde caerse -la sala es
           una caja- y ademas `height` mide el dibujo, no la planta. */
        if (!np_vista_iso
            && NP_F2I(p->y) > (int32_t)(w->level->height + 2) * NP_TILE)
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

/* Y "NNN" en tres, para la vida que se gasta sola: ahi no son golpes que se
   cuentan con los dedos sino una cuenta atras de hasta 255. */
static void np_tres_digitos(char *out, uint8_t valor)
{
    out[0] = (char)('0' + valor / 100);
    out[1] = (char)('0' + (valor / 10) % 10);
    out[2] = (char)('0' + valor % 10);
}

/* Lo que lleva la bolsa, en un solo numero. Los marcadores de las siete
 * maquinas solo repintan la linea de "lo que llevas" cuando algo cambia, y sin
 * esto la bolsa no contaba: se cogia una llave y el marcador seguia ensenando
 * lo de tres pantallas atras. Con NP_BOLSA huecos de un byte cabe entera en un
 * entero, asi que la comparacion es exacta y no un resumen que pueda repetirse.
 */
uint32_t np_bolsa_firma(const NpWorld *w)
{
    uint32_t firma = 0;
    uint8_t i;
    for (i = 0; i < NP_BOLSA; i++) firma = (firma << 8) | w->bolsa[i];
    return firma;
}

/* La linea de "lo que llevas": llaves y municion, "KEYS 01/03 AMMO 05" (en
   ingles como el resto del marcador: SCORE, LIVES, BOSS). Cada mitad sale en
   blanco si el juego no la usa, asi que el marcador no tiene que saber nada de
   esto y se limita a escribir lo que salga. */
void np_extras_bar(char *out, const NpWorld *w)
{
    static const char llaves[] = "KEYS ";
    uint8_t i, piden = w->level ? w->level->keys_needed : 0;

    for (i = 0; i < NP_EXTRAS_BAR; i++) out[i] = ' ';
    out[NP_EXTRAS_BAR] = 0;
    if (piden) {
        for (i = 0; i < 5; i++) out[i] = llaves[i];
        np_dos_digitos(out + 5, w->keys);
        out[7] = '/';
        np_dos_digitos(out + 8, piden);
    }
    /* La municion solo tiene sentido si el juego lleva arma secundaria, y con
       mas de una hay que decir **cual llevas**: por eso lo que va delante de la
       cuenta no es "AMMO" a secas sino lo que diga `np_sub_names` del arma que
       llevas (con una sola arma es "AMMO", como siempre). La cuenta va pegada
       al nombre y no en una columna fija: asi "AMMO 05" se queda como estaba y
       "HACHA 05", que es una letra mas largo, tambien cabe en los veinte
       huecos de la linea. */
    if (np_sub_count) {
        const char *etiqueta = np_sub_names[w->sub];
        for (i = 0; i < 5 && etiqueta[i]; i++) out[11 + i] = etiqueta[i];
        np_dos_digitos(out + 12 + i, w->hearts);
    }
    /* Y en una aventura, lo que llevas encima. Ocupa la linea entera porque en
       estos juegos es **la** informacion: sin mirar la bolsa no se sabe si la
       puerta de delante se puede abrir o hay que dar media vuelta. */
    if (np_bolsa_activa) {
        uint8_t hueco, columna = 0;
        for (hueco = 0; hueco < NP_BOLSA; hueco++) {
            const char *nombre;
            if (!w->bolsa[hueco]) continue;
            nombre = np_item_names[w->bolsa[hueco] - 1];
            for (i = 0; i < 5 && nombre[i]; i++)
                if (columna + i < NP_EXTRAS_BAR) out[columna + i] = nombre[i];
            columna = (uint8_t)(columna + i + 1);
        }
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
    for (i = 0; i < 5; i++) out[i] = titulo[i];
    /* Con `desgaste:` la vida no son tres golpes sino una cuenta atras que
       baja sola, y unos cuadrados no dicen nada: lo que hace falta saber es
       cuanto queda. Sale el numero, como en Gauntlet. */
    if (np_player_def.wear) {
        np_tres_digitos(out + 5, p->health);
        out[8] = 0;
        return;
    }
    capacidad = np_life_pips();
    llenos = (p->health > capacidad) ? capacidad : p->health;
    for (i = 0; i < capacidad; i++) out[5 + i] = (i < llenos) ? '#' : '.';
    out[5 + capacidad] = 0;
}

/* Cuantos cuadrados tiene la barra de este juego. Es fijo durante toda la
   partida (sale de `vida:`), asi que el marcador puede pintar la etiqueta una
   vez y repintar solo los cuadrados. */
uint8_t np_life_pips(void)
{
    /* Con `desgaste:` la barra es un numero de tres cifras, no cuadrados. */
    if (np_player_def.wear) return 3;
    if (np_player_def.health <= 1) return 0;
    return (np_player_def.health > NP_LIFE_BAR)
         ? NP_LIFE_BAR : np_player_def.health;
}

/* Que musica toca ahora. La regla es del motor y no de cada maquina: las seis
   tenian la misma linea copiada, y cualquier cosa nueva -la del titulo, la del
   jefe- habia que anadirla seis veces y acordarse de las seis. */
uint8_t np_music_now(const NpWorld *w)
{
    if (w->state == NP_STATE_TITLE) return np_music_title;
    if (w->state != NP_STATE_PLAY) return 0;
    /* Con un jefe en pantalla manda la suya: es el momento en el que la musica
       tiene mas que decir. `boss_max` solo vale mientras el jefe esta vivo. */
    if (np_music_boss && w->boss_max) return np_music_boss;
    return w->level->music;
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
        /* El congelado: al acertar un golpe el mundo se para unos frames. Es el
         * truco mas viejo del genero y el que mas se nota: sin esa parada el
         * puno atraviesa al otro y no se siente nada; con ella, **pega**.
         *
         * Se para todo menos el reloj de frames y el mando: las pulsaciones que
         * caigan dentro se quedan guardadas y salen al frame siguiente, que es
         * lo que hace que encadenar durante el impacto sea comodo en vez de un
         * examen de reflejos. */
        if (w->congelado) {
            w->congelado--;
            /* Y el mando **no se apunta**: lo que se pulse durante la parada
               sigue contando como recien pulsado al frame siguiente. Sin esto,
               el golpe que sale justo al acertar el anterior se perderia y
               encadenar seria un examen de reflejos en vez de un ritmo. */
            return;
        }
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
    np_cambio_de_pantalla(w);
    np_players_in_view(w);
    w->prev_input[0] = input;
    if (NP_MAX_PLAYERS > 1) w->prev_input[1] = input2;
}
