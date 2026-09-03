/* np_video.c - dibujado del juego en la Neo Geo. */

#include "np_video.h"

void np_vram_seek(uint16_t address, int16_t modulo)
{
    *NP_REG_VRAMADDR = address;
    *NP_REG_VRAMMOD = (uint16_t)modulo;
}

void np_vram_write(uint16_t value)
{
    *NP_REG_VRAMRW = value;
}

/* Espera al retrazo vertical leyendo el contador de linea del LSPC.
 * (Si prefieres la interrupcion de ngdevkit, sustituye esta funcion por
 *  ng_wait_vblank(); el resto del motor no cambia.) */
void np_wait_vblank(void)
{
    while ((*NP_REG_LSPCMODE >> 7) >= 0xF0)  /* si ya estamos en vblank, salimos */
        ;
    while ((*NP_REG_LSPCMODE >> 7) < 0xF0)
        ;
}

/* El mando de Neo Geo es activo a nivel bajo. */
/* Los dos mandos son iguales: cambia el registro de la cruceta y que bits de
   STATUS_B llevan su START (los de P1 son el 0 y el 1, y los de P2 el 2 y el
   3). Todo activo a nivel bajo, de ahi el complemento. */
static uint16_t np_input_de(volatile uint8_t *cnt, uint8_t start)
{
    uint8_t pad = (uint8_t)~(*cnt);
    uint8_t sys = (uint8_t)~(*NP_REG_STATUS_B);
    uint16_t out = 0;
    if (pad & 0x01) out |= NP_IN_UP;
    if (pad & 0x02) out |= NP_IN_DOWN;
    if (pad & 0x04) out |= NP_IN_LEFT;
    if (pad & 0x08) out |= NP_IN_RIGHT;
    if (pad & 0x10) out |= NP_IN_JUMP;      /* boton A */
    if (pad & 0x20) out |= NP_IN_ACTION;    /* boton B */
    if (sys & start) out |= NP_IN_START;    /* START o SELECT, los dos valen */
    return out;
}

uint16_t np_input_read(void)
{
    return np_input_de(NP_REG_P1CNT, 0x03);
}

uint16_t np_input_read2(void)
{
    return np_input_de(NP_REG_P2CNT, 0x0C);
}

/* La posicion de un sprite son dos palabras que estan a 0x200 de distancia
 * (SCB3 = 0x8200, SCB4 = 0x8400). Poniendo ese 0x200 como modulo, el propio
 * chip salta de una a otra y basta con dar la direccion una vez: tres
 * escrituras en vez de seis, y esta es la funcion que mas se llama de todas. */
static void np_sprite_pos(uint16_t sprite, int16_t x, int16_t y, uint8_t height)
{
    np_vram_seek((uint16_t)(NP_SCB3 + sprite), 0x200);
    np_vram_write((uint16_t)((((496 - y) & 0x1FF) << 7) | (height & 0x3F)));
    np_vram_write((uint16_t)((x & 0x1FF) << 7));
}

static void np_sprite_hide(uint16_t sprite)
{
    np_vram_seek((uint16_t)(NP_SCB3 + sprite), 0);
    np_vram_write(0);            /* altura 0 = sprite apagado */
}

static void np_sprite_zoom_full(uint16_t sprite)
{
    np_vram_seek((uint16_t)(NP_SCB2 + sprite), 0);
    np_vram_write(0x0FFF);       /* sin reduccion */
}

void np_video_init(void)
{
    uint16_t i, j;

    /* Paletas: se copian tal cual a la RAM de color. */
    for (i = 0; i < NP_PALETTE_COUNT; i++)
        for (j = 0; j < 16; j++)
            NP_PALETTE_RAM[i * 16 + j] = np_palettes[i][j];
    *NP_BACKDROP = 0x0000;

    /* Plano fix en blanco y todos los sprites apagados. */
    np_hud_clear();
    for (i = 0; i < NP_TOTAL_SPRITES; i++) {
        np_sprite_zoom_full(i);
        np_sprite_hide(i);
    }
}

/* Rellena el tilemap de una columna del fondo. */
static void np_bg_column(const NpWorld *w, uint16_t column, int32_t tile_x, int32_t tile_y)
{
    uint16_t sprite = (uint16_t)(NP_BG_FIRST_SPRITE + column);
    uint16_t tiles[NP_BG_ROWS];
    uint16_t atributos = (uint16_t)(np_tileset_palette << 8);
    uint16_t row;
    np_tile_gfx_column(w, tile_x, tile_y, NP_BG_ROWS, tiles);
    np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
    for (row = 0; row < NP_BG_ROWS; row++) {
        np_vram_write(tiles[row]);              /* numero de tile */
        np_vram_write(atributos);               /* paleta y atributos */
    }
}

/* Dibuja una capa de parallax. La capa se repite horizontalmente y se mueve a
 * una fraccion de la camara: eso es todo el efecto.
 *
 * Igual que el fondo, las columnas van en un anillo: la columna N de la capa
 * cae siempre en el sprite N mod 21, asi que al avanzar la camara solo se
 * rellena el tilemap de la que entra por el borde. */
#define NP_SIN_CARGAR ((int32_t)-0x7FFFFFFF)

/* lo pone np_draw_layers cuando cambia el nivel: hay que rehacerlo todo */
static uint8_t np_capas_todas = 1;

static void np_draw_layer(const NpWorld *w, uint8_t layer_index, uint8_t slot)
{
#if NP_LAYER_COUNT > 0
    static int32_t cargada[NP_LAYER_COUNT][NP_LAYER_COLUMNS];
    static uint8_t last_layer[NP_LAYER_COUNT];
    static int32_t ultimo_x[NP_LAYER_COUNT], ultimo_y[NP_LAYER_COUNT];
    static uint8_t primera_vez = 1;
    const NpLayer *layer = &np_layers[layer_index];
    int32_t scroll_x = ((int32_t)w->cam_x * layer->speed_x) >> 8;
    int32_t scroll_y = ((int32_t)w->cam_y * layer->speed_y) >> 8;
    int32_t col0 = scroll_x >> NP_TILE_SHIFT;
    int16_t off_x = (int16_t)(scroll_x & 15);
    int16_t y = (int16_t)(layer->offset_y - scroll_y);
    uint16_t base = (uint16_t)NP_LAYER_FIRST_SPRITE(slot);
    uint16_t ranura;
    int32_t mapa = col0, col = col0, resto;
    uint8_t todas, i, r;

    if (primera_vez) {
        for (i = 0; i < NP_LAYER_COUNT; i++) {
            last_layer[i] = 0xFF;
            for (r = 0; r < NP_LAYER_COLUMNS; r++) cargada[i][r] = NP_SIN_CARGAR;
        }
        primera_vez = 0;
    }
    todas = np_capas_todas || (layer_index != last_layer[slot]);
    last_layer[slot] = layer_index;

    /* Una capa lenta (velocidad 0.2) se mueve un pixel cada cinco de camara:
       los otros cuatro frames no hay nada que escribir, y son veintiuna
       posiciones de sprite por capa. Medido en el banco: las dos capas del
       ejemplo costaban 40.000 de los 132.000 ciclos del frame. */
    if (!todas && scroll_x == ultimo_x[slot] && scroll_y == ultimo_y[slot])
        return;
    ultimo_x[slot] = scroll_x;
    ultimo_y[slot] = scroll_y;

    /* Una sola division por capa y frame: dentro del bucle basta con sumar. */
    resto = col0 % NP_LAYER_COLUMNS;
    ranura = (uint16_t)(resto < 0 ? resto + NP_LAYER_COLUMNS : resto);
    if (layer->repeat) {
        col %= layer->cols;
        if (col < 0) col += layer->cols;
    }

    for (i = 0; i < NP_LAYER_COLUMNS; i++) {
        uint16_t sprite = (uint16_t)(base + ranura);
        if (!layer->repeat && (mapa < 0 || mapa >= layer->cols)) {
            cargada[slot][ranura] = NP_SIN_CARGAR;
            np_sprite_hide(sprite);
        } else {
            if (todas || cargada[slot][ranura] != col) {
                np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
                for (r = 0; r < layer->rows; r++) {
                    np_vram_write(layer->tiles[r * layer->cols + col]);
                    np_vram_write((uint16_t)(layer->palette << 8));
                }
                cargada[slot][ranura] = col;
            }
            np_sprite_pos(sprite, (int16_t)(i * 16 - off_x), y, layer->rows);
        }
        mapa++;
        if (layer->repeat) {
            if (++col >= layer->cols) col = 0;
        } else {
            col = mapa;
        }
        if (++ranura == NP_LAYER_COLUMNS) ranura = 0;
    }
#else
    (void)w; (void)layer_index; (void)slot;
#endif
}

static void np_draw_layers(const NpWorld *w)
{
#if NP_LAYER_COUNT > 0
    static const NpLevel *ultimo_nivel = 0;
    uint8_t slot;
    /* al cambiar de nivel las capas pueden ser otras, o ninguna: lo que
       hubiera dibujado antes no vale */
    if (w->level != ultimo_nivel) {
        np_capas_todas = 1;
        ultimo_nivel = w->level;
    }
    for (slot = 0; slot < NP_LAYER_COUNT; slot++) {
        if (slot < w->level->layer_count) {
            np_draw_layer(w, w->level->layers[slot], slot);
        } else {
            uint16_t base = (uint16_t)NP_LAYER_FIRST_SPRITE(slot);
            uint8_t i;
            for (i = 0; i < NP_LAYER_COLUMNS; i++)
                np_sprite_hide((uint16_t)(base + i));
        }
    }
    np_capas_todas = 0;
#else
    (void)w;
#endif
}

/* El reparto de columnas es circular: la columna N del mapa cae siempre en el
 * sprite N mod 21. Asi, cuando la camara avanza un tile, veinte de las
 * veintiuna columnas ya estan donde tienen que estar y solo hay que rellenar
 * el tilemap de la que acaba de entrar por el borde: 30 escrituras en la VRAM
 * en vez de 630. Antes de esto la consola bajaba a 29 fps cada 16 pixeles de
 * scroll (medido con tests/maquina_neogeo.py).
 *
 * Con la camara por pantallas la cuenta cambia: la vista salta veinte columnas
 * de golpe y esas veinte no caben en un frame (medido: 214.558 ciclos de los
 * 200.000 que da la consola). Asi que se rellenan NP_BG_POR_FRAME por frame y
 * las que aun no valen se apagan, que es preferible a ensenar los tiles de la
 * pantalla anterior en el sitio equivocado. Se ve como un barrido de un par de
 * frames, que es justo lo que hacian los juegos de pantalla a pantalla. */
#define NP_BG_POR_FRAME 10
static void np_draw_background(const NpWorld *w)
{
    static int32_t cargada[NP_BG_COLUMNS];
    static int32_t last_row = -9999;
    static const NpLevel *last_level = 0;
    /* cuantas puertas habia abiertas al pintar: al abrirse una, la casilla
       pasa a ser aire y hay que rehacer las columnas */
    static uint8_t ultimos_abiertos = 0;
    static uint8_t primera_vez = 1;
    int32_t col = w->cam_x >> NP_TILE_SHIFT;
    int32_t row = w->cam_y >> NP_TILE_SHIFT;
    int16_t off_x = (int16_t)(w->cam_x & 15);
    int16_t off_y = (int16_t)(w->cam_y & 15);
    /* Si cambia la fila (o el nivel) no vale nada de lo que hay: al moverse en
     * vertical cambian los quince tiles de todas las columnas. */
    uint8_t todas = primera_vez || row != last_row || w->level != last_level
                  || w->abiertos_n != ultimos_abiertos;
    /* La camara nunca sale del nivel, pero un resto negativo aqui se saldria
     * del array: mas vale gastar una comparacion al frame. */
    int32_t resto = col % NP_BG_COLUMNS;
    uint16_t ranura = (uint16_t)(resto < 0 ? resto + NP_BG_COLUMNS : resto);
    uint16_t presupuesto = NP_BG_POR_FRAME;
    uint16_t i;

    primera_vez = 0;
    last_row = row;
    last_level = w->level;
    ultimos_abiertos = w->abiertos_n;

    for (i = 0; i < NP_BG_COLUMNS; i++) {
        int32_t mapa = col + i;
        uint8_t lista = 1;
        if (todas || cargada[ranura] != mapa) {
            /* al moverse en vertical hay que rehacerlas todas si o si: ahi no
               hay columna que dejar para luego sin que se vea el hueco */
            if (todas || presupuesto) {
                np_bg_column(w, ranura, mapa, row);
                cargada[ranura] = mapa;
                if (presupuesto) presupuesto--;
            } else {
                lista = 0;
            }
        }
        if (lista) {
            np_sprite_pos((uint16_t)(NP_BG_FIRST_SPRITE + ranura),
                          (int16_t)(i * 16 - off_x), (int16_t)(-off_y), NP_BG_ROWS);
        } else {
            np_sprite_hide((uint16_t)(NP_BG_FIRST_SPRITE + ranura));
        }
        if (++ranura == NP_BG_COLUMNS) ranura = 0;
    }
}

/* Dibuja un actor (jugador, enemigo u objeto) usando `cols` sprites. */
static uint16_t np_draw_actor(const NpActorDef *def, uint16_t sprite,
                              int32_t screen_x, int32_t screen_y,
                              uint8_t frame, uint8_t flip)
{
    uint16_t base = (uint16_t)(def->first_tile + frame * def->cols * def->rows);
    uint8_t c, r;
    for (c = 0; c < def->cols; c++) {
        uint8_t source = flip ? (uint8_t)(def->cols - 1 - c) : c;
        int32_t x = screen_x + c * 16;
        if (sprite >= NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) break;
        if (x <= -16 || x >= NP_SCREEN_W) {      /* fuera de pantalla: se apaga */
            np_sprite_hide(sprite);
            sprite++;
            continue;
        }
        np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
        for (r = 0; r < def->rows; r++) {
            uint16_t tile = (uint16_t)(base + source * def->rows + r);
            np_vram_write(tile);
            np_vram_write((uint16_t)((def->palette << 8) | (flip ? 0x01 : 0x00)));
        }
        np_sprite_pos(sprite, (int16_t)x, (int16_t)screen_y, def->rows);
        sprite++;
    }
    return sprite;
}

void np_video_frame(const NpWorld *w)
{
    const uint8_t *orden;
    uint8_t cuantas;
    uint16_t sprite = NP_ACTOR_FIRST_SPRITE;
    uint8_t i;

    *NP_BACKDROP = w->level->background;
    np_draw_layers(w);
    np_draw_background(w);

    /* De mas lejos a mas cerca: en la vista de cinta los actores se pisan a
       cada rato y hay que pintarlos por la linea del suelo. En las demas
       vistas np_orden_dibujo devuelve el orden de la lista tal cual. */
    orden = np_orden_dibujo(w, &cuantas);
    for (i = 0; i < cuantas; i++) {
        const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
        const NpActorDef *def;
        int32_t sx, sy;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;        /* parpadeo al recibir */
        def = np_entity_def(e);
        sx = NP_F2I(e->x) - def->box_x - w->cam_x;
        sy = NP_F2I(e->y) - def->box_y - w->cam_y;
        if (sx <= -(def->cols * 16) || sx >= NP_SCREEN_W) continue;
        if (sy <= -(def->rows * 16) || sy >= NP_SCREEN_H) continue;
        sprite = np_draw_actor(def, sprite, sx, sy,
                               np_actor_frame(def, e->anim, e->anim_frame),
                               (uint8_t)!e->facing);
        if (sprite >= NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) break;
    }

    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        int32_t sx, sy;
        if (!np_player_visible(w, i)) continue;
        sx = NP_F2I(p->x) - def->box_x - w->cam_x;
        sy = NP_F2I(p->y) - def->box_y - w->cam_y;
        sprite = np_draw_actor(def, sprite, sx, sy,
                               np_actor_frame(def, p->anim, p->anim_frame),
                               (uint8_t)!p->facing);
    }

    while (sprite < NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) {
        np_sprite_hide(sprite);
        sprite++;
    }

#if NP_HUD_ENABLED
    np_hud_draw(w);
#endif
}
