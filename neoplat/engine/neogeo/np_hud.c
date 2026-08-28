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

/* Escribir el marcador cuesta una escritura de VRAM por letra, y casi ningun
   frame cambia nada: el tanteo sube al coger una moneda y las vidas casi
   nunca. Repintarlo entero cada frame costaba 14.000 de los 132.000 ciclos que
   da un frame (medido con tests/maquina_neogeo.py), asi que aqui solo se
   escribe lo que ha cambiado. */
void np_hud_draw(const NpWorld *w)
{
    static uint16_t last_state = 0xFFFF;
    static uint32_t ultimo_tanteo = 0xFFFFFFFFu;
    static uint16_t ultimas_vidas = 0xFFFF;
    static uint16_t ultimas_vidas2 = 0xFFFF;
    static uint16_t ultimo_tiempo = 0xFFFF;
    static uint8_t rotulos = 0;
    static uint8_t ultimo_jefe = 0xFF;
    static uint16_t ultimas_llaves = 0xFFFF;
    uint16_t segundos = (uint16_t)(w->time_left / 60);

    if (!rotulos) {
        np_hud_print(2, 1, "SCORE", NP_HUD_PALETTE);
        if (np_player_count > 1) {
            np_hud_print(30, 1, "1P", NP_HUD_PALETTE);
            np_hud_print(35, 1, "2P", NP_HUD_PALETTE);
        } else {
            np_hud_print(30, 1, "LIVES", NP_HUD_PALETTE);
        }
        if (np_time_limit) np_hud_print(18, 1, "TIME", NP_HUD_PALETTE);
        rotulos = 1;
    }
    if (w->score != ultimo_tanteo) {
        np_hud_number(8, 1, w->score, 6, NP_HUD_PALETTE);
        ultimo_tanteo = w->score;
    }
    /* Las vidas son de cada jugador. A uno pone "LIVES 3" como siempre; a dos
       no cabe dos veces, asi que pone "1P 3  2P 3" en el mismo hueco. */
    if (w->players[0].lives != ultimas_vidas) {
        np_hud_number(np_player_count > 1 ? 33 : 36, 1, w->players[0].lives, 1,
                      NP_HUD_PALETTE);
        ultimas_vidas = (uint16_t)w->players[0].lives;
    }
    if (np_player_count > 1 && w->players[1].lives != ultimas_vidas2) {
        np_hud_number(38, 1, w->players[1].lives, 1, NP_HUD_PALETTE);
        ultimas_vidas2 = (uint16_t)w->players[1].lives;
    }
    if (np_time_limit && segundos != ultimo_tiempo) {
        np_hud_number(23, 1, segundos, 3, NP_HUD_PALETTE);
        ultimo_tiempo = segundos;
    }


    /* La barra del jefe. Solo se escribe cuando cambia: son quince letras y
       casi ningun frame le quitas un golpe. */
    if (w->boss_health != ultimo_jefe) {
        char barra[NP_BOSS_BAR + 6];
        np_boss_bar(barra, w);
        np_hud_print(2, 2, barra, NP_HUD_PALETTE);
        ultimo_jefe = w->boss_health;
    }

    /* Las llaves que llevas y las que pide la meta, al lado de la barra del
       jefe. Igual que ella: solo se repinta cuando cambia alguna de las dos. */
    {
        uint16_t ahora = (uint16_t)((w->keys << 8)
                                    | (w->level ? w->level->keys_needed : 0));
        if (ahora != ultimas_llaves) {
            char llaves[NP_KEYS_BAR + 1];
            np_keys_bar(llaves, w);
            np_hud_print(20, 2, llaves, NP_HUD_PALETTE);
            ultimas_llaves = ahora;
        }
    }

    if (w->state != last_state) {
        /* Se borran todas las filas donde puede caer un mensaje (12 a 16), no
           solo las de en medio: si no, el titulo de la fila 12 y el autor de
           la 16 se quedaban pegados encima del juego al pulsar start. */
        uint8_t row;
        for (row = 12; row <= 16; row++)
            np_hud_blank(10, row, 20);
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
