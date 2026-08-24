/* np_hud.c - marcador y textos en el plano fix (8x8).
 *
 * El plano fix mide 40x32 tiles y se direcciona por columnas:
 *   direccion = 0x7000 + columna * 32 + fila
 * Cada word es (paleta << 12) | numero de tile.
 */

#include "np_video.h"
#include "gamedata.h"

#define NP_FIX_COLS 40
#define NP_FIX_ROWS 32

void np_hud_clear(void)
{
    uint16_t col, row;
    for (col = 0; col < NP_FIX_COLS; col++) {
        np_vram_seek((uint16_t)(NP_FIXMAP + col * 32), 1);
        for (row = 0; row < NP_FIX_ROWS; row++)
            np_vram_write(0);
    }
}

void np_hud_print(uint8_t col, uint8_t row, const char *text, uint8_t palette)
{
    while (*text && col < NP_FIX_COLS) {
        uint8_t c = (uint8_t)*text++;
        uint16_t tile = (c < 128) ? np_font_index[c] : 0;
        np_vram_seek((uint16_t)(NP_FIXMAP + col * 32 + row), 1);
        np_vram_write((uint16_t)((palette << 12) | tile));
        col++;
    }
}

void np_hud_number(uint8_t col, uint8_t row, uint32_t value, uint8_t digits, uint8_t palette)
{
    char buffer[12];
    int8_t i;
    if (digits > 10) digits = 10;
    buffer[digits] = 0;
    for (i = (int8_t)(digits - 1); i >= 0; i--) {
        buffer[i] = (char)('0' + (value % 10));
        value /= 10;
    }
    np_hud_print(col, row, buffer, palette);
}

static void np_hud_blank(uint8_t col, uint8_t row, uint8_t count)
{
    np_vram_seek((uint16_t)(NP_FIXMAP + col * 32 + row), 32);
    while (count--)
        np_vram_write(0);
}

void np_hud_draw(const NpWorld *w)
{
    static uint16_t last_state = 0xFFFF;

    np_hud_print(2, 1, "SCORE", NP_HUD_PALETTE);
    np_hud_number(8, 1, w->score, 6, NP_HUD_PALETTE);
    np_hud_print(30, 1, "LIVES", NP_HUD_PALETTE);
    np_hud_number(36, 1, w->lives, 1, NP_HUD_PALETTE);
    if (np_time_limit) {
        np_hud_print(18, 1, "TIME", NP_HUD_PALETTE);
        np_hud_number(23, 1, w->time_left / 60, 3, NP_HUD_PALETTE);
    }

    if (w->state != last_state) {
        np_hud_blank(10, 13, 20);
        np_hud_blank(10, 14, 20);
        np_hud_blank(10, 15, 20);
        last_state = w->state;
    }

    switch (w->state) {
    case NP_STATE_TITLE:
        np_hud_print(12, 12, np_game_title, NP_HUD_PALETTE);
        np_hud_print(12, 14, "PRESS START", NP_HUD_PALETTE);
        if (np_game_author[0]) np_hud_print(12, 16, np_game_author, NP_HUD_PALETTE);
        break;
    case NP_STATE_GAME_OVER:
        np_hud_print(15, 13, "GAME OVER", NP_HUD_PALETTE);
        break;
    case NP_STATE_FINISHED:
        np_hud_print(15, 13, "YOU WIN!", NP_HUD_PALETTE);
        break;
    case NP_STATE_LEVEL_END:
        np_hud_print(14, 13, "LEVEL CLEAR", NP_HUD_PALETTE);
        break;
    default:
        break;
    }
}
