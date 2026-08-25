/* np_hud.c - marcador de la Mega Drive, en el plano ventana.
 *
 * El VDP tiene un plano "window" que no se mueve con el scroll y tapa al plano
 * A en la zona que se le diga: perfecto para el marcador. Aqui ocupa las tres
 * primeras filas de la pantalla.
 */

#include "np_md.h"

#define NP_HUD_FILAS 3

static void np_ventana(uint8_t columna, uint8_t fila, uint16_t celda)
{
    uint16_t direccion = (uint16_t)(MD_WINDOW + (fila * MD_PLANE_W + columna) * 2);
    np_md_vram_addr(MD_ADDR(MD_VRAM_WRITE, direccion));
    *MD_VDP_DATA = celda;
}

void np_hud_clear(void)
{
    uint8_t columna, fila;
    for (fila = 0; fila < NP_HUD_FILAS; fila++)
        for (columna = 0; columna < MD_CELDAS_X; columna++)
            np_ventana(columna, fila, 0);
}

void np_hud_print(uint8_t col, uint8_t fila, const char *texto, uint8_t paleta)
{
    while (*texto && col < MD_CELDAS_X) {
        uint8_t c = (uint8_t)*texto++;
        uint16_t tile = (c < 128) ? (uint16_t)(np_font_first_tile + np_font_index[c]) : 0;
        np_ventana(col, fila, MD_CELDA(tile, paleta, 1));
        col++;
    }
}

void np_hud_number(uint8_t col, uint8_t fila, uint32_t valor, uint8_t digitos, uint8_t paleta)
{
    char buffer[12];
    int8_t i;
    if (digitos > 10) digitos = 10;
    buffer[digitos] = 0;
    for (i = (int8_t)(digitos - 1); i >= 0; i--) {
        buffer[i] = (char)('0' + (valor % 10));
        valor /= 10;
    }
    np_hud_print(col, fila, buffer, paleta);
}

void np_hud_draw(const NpWorld *w)
{
    static uint16_t ultimo_estado = 0xFFFF;

    np_hud_print(2, 1, "SCORE", NP_HUD_PALETTE);
    np_hud_number(8, 1, w->score, 6, NP_HUD_PALETTE);
    np_hud_print(30, 1, "LIVES", NP_HUD_PALETTE);
    np_hud_number(36, 1, w->lives, 1, NP_HUD_PALETTE);
    if (np_time_limit) {
        np_hud_print(18, 1, "TIME", NP_HUD_PALETTE);
        np_hud_number(23, 1, w->time_left / 60, 3, NP_HUD_PALETTE);
    }

    if (w->state != ultimo_estado) {
        uint8_t i;
        for (i = 10; i < 30; i++) np_ventana(i, 2, 0);
        ultimo_estado = w->state;
    }
    switch (w->state) {
    case NP_STATE_TITLE:
        np_hud_print(12, 2, np_game_title, NP_HUD_PALETTE);
        break;
    case NP_STATE_GAME_OVER:
        np_hud_print(15, 2, "GAME OVER", NP_HUD_PALETTE);
        break;
    case NP_STATE_FINISHED:
        np_hud_print(15, 2, "YOU WIN!", NP_HUD_PALETTE);
        break;
    case NP_STATE_LEVEL_END:
        np_hud_print(14, 2, "LEVEL CLEAR", NP_HUD_PALETTE);
        break;
    default:
        break;
    }
}
