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
uint16_t np_input_read(void)
{
    uint8_t pad = (uint8_t)~(*NP_REG_P1CNT);
    uint8_t sys = (uint8_t)~(*NP_REG_STATUS_B);
    uint16_t out = 0;
    if (pad & 0x01) out |= NP_IN_UP;
    if (pad & 0x02) out |= NP_IN_DOWN;
    if (pad & 0x04) out |= NP_IN_LEFT;
    if (pad & 0x08) out |= NP_IN_RIGHT;
    if (pad & 0x10) out |= NP_IN_JUMP;      /* boton A */
    if (pad & 0x20) out |= NP_IN_ACTION;    /* boton B */
    /* START de P1: bit 1 de STATUS_B (bit 0 = SELECT; aceptamos los dos). */
    if (sys & 0x03) out |= NP_IN_START;
    return out;
}

static void np_sprite_pos(uint16_t sprite, int16_t x, int16_t y, uint8_t height)
{
    np_vram_seek((uint16_t)(NP_SCB3 + sprite), 0);
    np_vram_write((uint16_t)((((496 - y) & 0x1FF) << 7) | (height & 0x3F)));
    np_vram_seek((uint16_t)(NP_SCB4 + sprite), 0);
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
    uint16_t row;
    np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
    for (row = 0; row < NP_BG_ROWS; row++) {
        uint16_t tile = np_tile_gfx_at(w->level, tile_x, tile_y + row);
        np_vram_write(tile);                                   /* numero de tile */
        np_vram_write((uint16_t)(np_tileset_palette << 8));     /* paleta y atributos */
    }
}

/* Dibuja una capa de parallax. La capa se repite horizontalmente y se mueve a
 * una fraccion de la camara: eso es todo el efecto. */
static void np_draw_layer(const NpWorld *w, uint8_t layer_index, uint8_t slot)
{
#if NP_LAYER_COUNT > 0
    static int32_t last_col[NP_LAYER_COUNT];
    static uint8_t last_layer[NP_LAYER_COUNT];
    static uint8_t primera_vez = 1;
    const NpLayer *layer = &np_layers[layer_index];
    int32_t scroll_x = ((int32_t)w->cam_x * layer->speed_x) >> 8;
    int32_t scroll_y = ((int32_t)w->cam_y * layer->speed_y) >> 8;
    int32_t col0 = scroll_x >> NP_TILE_SHIFT;
    int16_t off_x = (int16_t)(scroll_x & 15);
    int16_t y = (int16_t)(layer->offset_y - scroll_y);
    uint16_t base = (uint16_t)NP_LAYER_FIRST_SPRITE(slot);
    uint8_t redibujar, i, r;

    if (primera_vez) {
        for (i = 0; i < NP_LAYER_COUNT; i++) { last_col[i] = -9999; last_layer[i] = 0xFF; }
        primera_vez = 0;
    }
    redibujar = (col0 != last_col[slot]) || (layer_index != last_layer[slot]);
    last_col[slot] = col0;
    last_layer[slot] = layer_index;

    for (i = 0; i < NP_LAYER_COLUMNS; i++) {
        int32_t col = col0 + i;
        uint16_t sprite = (uint16_t)(base + i);
        if (layer->repeat) {
            col %= layer->cols;
            if (col < 0) col += layer->cols;
        } else if (col < 0 || col >= layer->cols) {
            np_sprite_hide(sprite);
            continue;
        }
        if (redibujar) {
            np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
            for (r = 0; r < layer->rows; r++) {
                np_vram_write(layer->tiles[r * layer->cols + col]);
                np_vram_write((uint16_t)(layer->palette << 8));
            }
        }
        np_sprite_pos(sprite, (int16_t)(i * 16 - off_x), y, layer->rows);
    }
#else
    (void)w; (void)layer_index; (void)slot;
#endif
}

static void np_draw_layers(const NpWorld *w)
{
#if NP_LAYER_COUNT > 0
    uint8_t slot;
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
#else
    (void)w;
#endif
}

static void np_draw_background(const NpWorld *w)
{
    static int32_t last_col = -9999, last_row = -9999;
    static const NpLevel *last_level = 0;
    int32_t col = w->cam_x >> NP_TILE_SHIFT;
    int32_t row = w->cam_y >> NP_TILE_SHIFT;
    int16_t off_x = (int16_t)(w->cam_x & 15);
    int16_t off_y = (int16_t)(w->cam_y & 15);
    uint16_t i;

    if (col != last_col || row != last_row || w->level != last_level) {
        for (i = 0; i < NP_BG_COLUMNS; i++)
            np_bg_column(w, i, col + i, row);
        last_col = col;
        last_row = row;
        last_level = w->level;
    }
    for (i = 0; i < NP_BG_COLUMNS; i++)
        np_sprite_pos((uint16_t)(NP_BG_FIRST_SPRITE + i),
                      (int16_t)(i * 16 - off_x), (int16_t)(-off_y), NP_BG_ROWS);
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
    uint16_t sprite = NP_ACTOR_FIRST_SPRITE;
    uint8_t i;

    *NP_BACKDROP = w->level->background;
    np_draw_layers(w);
    np_draw_background(w);

    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
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

    if (np_player_visible(w)) {
        const NpActorDef *def = &np_player_def.actor;
        int32_t sx = NP_F2I(w->player.x) - def->box_x - w->cam_x;
        int32_t sy = NP_F2I(w->player.y) - def->box_y - w->cam_y;
        sprite = np_draw_actor(def, sprite, sx, sy,
                               np_actor_frame(def, w->player.anim, w->player.anim_frame),
                               (uint8_t)!w->player.facing);
    }

    while (sprite < NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) {
        np_sprite_hide(sprite);
        sprite++;
    }

#if NP_HUD_ENABLED
    np_hud_draw(w);
#endif
}
