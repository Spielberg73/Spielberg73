/* np_hud.c - marcador del X68000, en el plano de texto.
 *
 * Esta maquina tiene un plano de texto aparte ($E00000), de 1024x1024 y cuatro
 * bitplanes de un bit. Poner ahi el marcador sale gratis en dos sentidos: no
 * gasta ni un patron de PCG -que son 256 para todo el juego y es el limite de
 * verdad- ni un sprite, y se dibuja por encima de las capas sin estorbar.
 *
 * Se escribe en los cuatro planos a la vez, asi que el marcador sale del color
 * 15 del primer bloque de paleta. No es un capricho: el plano de texto lee de
 * la paleta de sprites (comprobado en el emulador), y el color 15 es el que el
 * empaquetador deja reservado para el marcador, igual que en el Atari ST y en
 * el Amiga. La fuente viene ya a un bit por pixel (ocho bytes por caracter), la
 * misma que usan la Jaguar y el Atari ST, asi que una fila de un caracter es un
 * byte y se copia tal cual.
 */

#include "np_x68k.h"
#include "gamedata.h"

/* El plano de texto: cada linea son 128 bytes (1024 pixeles a un bit) y cada
   plano ocupa 128 KB. */
#define NP_TEXTO         ((volatile uint8_t *)0xE00000)
#define NP_TEXTO_PASO    128
#define NP_TEXTO_PLANO   0x20000
#define NP_TEXTO_COLS    (NP_ANCHO / 8)
#define NP_TEXTO_FILAS   (NP_ALTO / 8)

/* El plano de texto entero, los cuatro planos. Se limpia todo y no solo lo que
   se ve porque lo que deja escrito Human68k al arrancar ocupa 768x512, mas de
   lo que ensena el juego, y en cuanto el marcador se mueve asomaria por debajo. */
void np_hud_clear(void)
{
    volatile uint32_t *p = (volatile uint32_t *)NP_TEXTO;
    uint32_t i;
    for (i = 0; i < 4UL * NP_TEXTO_PLANO / 4; i++)
        p[i] = 0;
}

void np_hud_print(uint8_t col, uint8_t fila, const char *texto)
{
    while (*texto && col < NP_TEXTO_COLS) {
        uint8_t c = (uint8_t)*texto++;
        uint8_t indice = (c < 128) ? np_font_index[c] : 0;
        const uint8_t *glifo = &np_font_data[(uint32_t)indice * 8];
        volatile uint8_t *destino = NP_TEXTO + (uint32_t)fila * 8 * NP_TEXTO_PASO + col;
        uint8_t y, p;
        for (y = 0; y < 8; y++)
            for (p = 0; p < 4; p++)
                destino[(uint32_t)p * NP_TEXTO_PLANO + (uint32_t)y * NP_TEXTO_PASO]
                    = glifo[y];
        col++;
    }
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
    uint32_t base = (uint32_t)fila * 8 * NP_TEXTO_PASO;
    uint16_t y, x;
    uint8_t p;
    for (p = 0; p < 4; p++)
        for (y = 0; y < 8; y++)
            for (x = 0; x < NP_TEXTO_COLS; x++)
                NP_TEXTO[(uint32_t)p * NP_TEXTO_PLANO + base
                         + (uint32_t)y * NP_TEXTO_PASO + x] = 0;
}

/* Igual que en las otras cinco: solo se escribe lo que ha cambiado, porque
   escribir el marcador entero cada frame se nota. */
void np_hud_draw(const NpWorld *w)
{
    static uint16_t ultimo_estado = 0xFFFF;
    static uint32_t ultimo_tanteo = 0xFFFFFFFFu;
    static uint16_t ultimas_vidas = 0xFFFF;
    static uint16_t ultimas_vidas2 = 0xFFFF;
    static uint16_t ultimo_tiempo = 0xFFFF;
    static uint8_t ultimo_jefe = 0xFF;
    static uint32_t ultimas_llaves = 0xFFFFFFFFu;
    static uint32_t ultima_vida = 0xFFFFFFFFu;
    static uint8_t rotulos = 0;
    uint16_t segundos = (uint16_t)(w->time_left / 60);

    if (!rotulos) {
        np_hud_print(2, 0, "SCORE");
        if (np_player_count > 1) {
            np_hud_print(30, 0, "1P");
            np_hud_print(35, 0, "2P");
        } else {
            np_hud_print(30, 0, "LIVES");
        }
        if (np_time_limit) np_hud_print(18, 0, "TIME");
        rotulos = 1;
    }
    if (w->score != ultimo_tanteo) {
        np_hud_number(8, 0, w->score, 6);
        ultimo_tanteo = w->score;
    }
    if (w->players[0].lives != ultimas_vidas) {
        np_hud_number(np_player_count > 1 ? 33 : 36, 0, w->players[0].lives, 1);
        ultimas_vidas = (uint16_t)w->players[0].lives;
    }
    if (np_player_count > 1 && w->players[1].lives != ultimas_vidas2) {
        np_hud_number(38, 0, w->players[1].lives, 1);
        ultimas_vidas2 = (uint16_t)w->players[1].lives;
    }
    if (np_time_limit && segundos != ultimo_tiempo) {
        np_hud_number(23, 0, segundos, 3);
        ultimo_tiempo = segundos;
    }

    if (w->boss_health != ultimo_jefe) {
        char barra[NP_BOSS_BAR + 6];
        np_boss_bar(barra, w);
        np_hud_print(2, 1, barra);
        ultimo_jefe = w->boss_health;
    }

    {
        uint32_t ahora = ((uint32_t)w->keys << 16) | ((uint32_t)w->hearts << 8)
                       | (uint32_t)(w->level ? w->level->keys_needed : 0);
        if (ahora != ultimas_llaves) {
            char llaves[NP_EXTRAS_BAR + 1];
            np_extras_bar(llaves, w);
            np_hud_print(20, 1, llaves);
            ultimas_llaves = ahora;
        }
    }

    /* La vida del jugador. Va en la fila 2, la de los mensajes: solo salen
       fuera de la partida, y np_life_bar deja la barra en blanco entonces. */
    {
        uint32_t ahora = ((uint32_t)w->state << 16)
                       | ((uint32_t)w->players[0].health << 8)
                       | (uint32_t)w->players[1].health;
        if (ahora != ultima_vida) {
            char vida[NP_LIFE_BAR + 6];
            uint8_t quien;
            ultima_vida = ahora;
            for (quien = 0; quien < np_player_count; quien++) {
                np_life_bar(vida, w, quien);
                np_hud_print((uint8_t)(2 + quien * 18), 2, vida);
            }
        }
    }

    if (w->state == ultimo_estado) return;
    np_hud_borrar_fila(2);
    ultima_vida = 0xFFFFFFFFu;   /* la fila que se acaba de borrar */
    ultimo_estado = w->state;
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
