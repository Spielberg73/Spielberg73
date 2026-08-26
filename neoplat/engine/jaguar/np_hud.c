/* np_hud.c - el marcador de la Jaguar.
 *
 * Va en su propia franja de 320x24 pixeles, que entra en la lista de objetos
 * por encima de todo lo demas. Se dibuja con la CPU: un byte por pixel, asi
 * que escribir una letra es copiar bytes, sin las mascaras y los bitplanes que
 * hacen falta en el Amiga.
 */

#include "np_jaguar.h"

#define NP_COLS (NP_SCREEN_W / 8)
#define NP_FILAS (NP_HUD_ALTO / 8)

static uint32_t np_hud_puntos = 0xFFFFFFFFUL;
static uint16_t np_hud_tiempo = 0xFFFF;
static uint16_t np_hud_estado = 0xFFFF;
static uint8_t np_hud_vidas = 0xFF;
static uint8_t np_hud_etiquetas;

void np_hud_clear(void)
{
    uint32_t *p = (uint32_t *)(void *)np_hud_bitmap;
    uint16_t i;
    for (i = 0; i < NP_SCREEN_W * NP_HUD_ALTO / 4; i++) *p++ = 0;
    np_hud_puntos = 0xFFFFFFFFUL;
    np_hud_tiempo = 0xFFFF;
    np_hud_estado = 0xFFFF;
    np_hud_vidas = 0xFF;
    np_hud_etiquetas = 0;
    __asm__ __volatile__ ("" ::: "memory");
}

static void np_hud_char(uint8_t col, uint8_t fila, uint8_t c)
{
    const uint8_t *glifo = np_font_data + (uint32_t)np_font_index[c & 0x7F] * 8;
    uint8_t *destino = np_hud_bitmap + (uint32_t)fila * 8 * NP_SCREEN_W + col * 8;
    uint8_t y, x;
    if (col >= NP_COLS || fila >= NP_FILAS) return;
    for (y = 0; y < 8; y++) {
        uint8_t bits = glifo[y];
        for (x = 0; x < 8; x++)
            destino[x] = (uint8_t)((bits & (0x80 >> x)) ? NP_HUD_COLOR : 0);
        destino += NP_SCREEN_W;
    }
}

void np_hud_print(uint8_t col, uint8_t fila, const char *texto)
{
    while (*texto && col < NP_COLS)
        np_hud_char(col++, fila, (uint8_t)*texto++);
    __asm__ __volatile__ ("" ::: "memory");
}

void np_hud_number(uint8_t col, uint8_t fila, uint32_t valor, uint8_t digitos)
{
    char buffer[12];
    int8_t i;
    if (digitos > 10) digitos = 10;
    buffer[digitos] = 0;
    for (i = (int8_t)(digitos - 1); i >= 0; i--) {
        buffer[i] = (char)('0' + (valor % 10));
        valor /= 10;
    }
    np_hud_print(col, fila, buffer);
}

static void np_hud_borrar_fila(uint8_t fila)
{
    uint32_t *p = (uint32_t *)(void *)(np_hud_bitmap + (uint32_t)fila * 8 * NP_SCREEN_W);
    uint16_t i;
    for (i = 0; i < NP_SCREEN_W * 8 / 4; i++) *p++ = 0;
    __asm__ __volatile__ ("" ::: "memory");
}

void np_hud_draw(const NpWorld *w)
{
    if (!np_hud_etiquetas) {
        np_hud_print(2, 0, "SCORE");
        np_hud_print(30, 0, "LIVES");
        if (np_time_limit) np_hud_print(18, 0, "TIME");
        np_hud_etiquetas = 1;
    }
    if (w->score != np_hud_puntos) {
        np_hud_puntos = w->score;
        np_hud_number(8, 0, w->score, 6);
    }
    if (w->lives != np_hud_vidas) {
        np_hud_vidas = w->lives;
        np_hud_number(36, 0, w->lives, 1);
    }
    if (np_time_limit && w->time_left / 60 != np_hud_tiempo) {
        np_hud_tiempo = (uint16_t)(w->time_left / 60);
        np_hud_number(23, 0, np_hud_tiempo, 3);
    }
    if (w->state == np_hud_estado) return;
    np_hud_borrar_fila(2);
    np_hud_estado = w->state;
    switch (w->state) {
    case NP_STATE_TITLE:
        np_hud_print(12, 2, np_game_title);
        break;
    case NP_STATE_GAME_OVER:
        np_hud_print(15, 2, "GAME OVER");
        break;
    case NP_STATE_FINISHED:
        np_hud_print(15, 2, "YOU WIN!");
        break;
    case NP_STATE_LEVEL_END:
        np_hud_print(14, 2, "LEVEL CLEAR");
        break;
    default:
        break;
    }
}
