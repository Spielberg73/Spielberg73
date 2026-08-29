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
static uint8_t np_hud_vidas2 = 0xFF;
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
    np_hud_vidas2 = 0xFF;
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
    static uint8_t ultimo_jefe = 0xFF;
    static uint32_t ultimas_llaves = 0xFFFFFFFFu;
    static uint32_t ultima_vida = 0xFFFFFFFFu;
    if (!np_hud_etiquetas) {
        np_hud_print(2, 0, "SCORE");
        if (np_player_count > 1) {
            np_hud_print(30, 0, "1P");
            np_hud_print(35, 0, "2P");
        } else {
            np_hud_print(30, 0, "LIVES");
        }
        if (np_time_limit) np_hud_print(18, 0, "TIME");
        np_hud_etiquetas = 1;
    }
    if (w->score != np_hud_puntos) {
        np_hud_puntos = w->score;
        np_hud_number(8, 0, w->score, 6);
    }
    /* Las vidas son de cada jugador. A uno pone "LIVES 3" como siempre; a dos
       no cabe dos veces, asi que pone "1P 3  2P 3" en el mismo hueco. */
    if (w->players[0].lives != np_hud_vidas) {
        np_hud_vidas = w->players[0].lives;
        np_hud_number(np_player_count > 1 ? 33 : 36, 0, np_hud_vidas, 1);
    }
    if (np_player_count > 1 && w->players[1].lives != np_hud_vidas2) {
        np_hud_vidas2 = w->players[1].lives;
        np_hud_number(38, 0, np_hud_vidas2, 1);
    }
    if (np_time_limit && w->time_left / 60 != np_hud_tiempo) {
        np_hud_tiempo = (uint16_t)(w->time_left / 60);
        np_hud_number(23, 0, np_hud_tiempo, 3);
    }

    /* La barra del jefe. Solo se escribe cuando cambia: son quince letras y
       casi ningun frame le quitas un golpe. */
    if (w->boss_health != ultimo_jefe) {
        char barra[NP_BOSS_BAR + 6];
        np_boss_bar(barra, w);
        np_hud_print(2, 1, barra);
        ultimo_jefe = w->boss_health;
    }

    /* Lo que llevas -llaves y municion- al lado de la barra del jefe. Igual
       que ella: solo se repinta cuando cambia algo. */
    {
        /* los tres numeros en un solo valor, cada uno en su byte: mezclarlos
           con un OR haria que uno tapara al otro y el marcador se quedaria
           colgado */
        uint32_t ahora = ((uint32_t)w->keys << 16) | ((uint32_t)w->hearts << 8)
                       | (uint32_t)(w->level ? w->level->keys_needed : 0);
        if (ahora != ultimas_llaves) {
            char llaves[NP_EXTRAS_BAR + 1];
            np_extras_bar(llaves, w);
            np_hud_print(20, 1, llaves);
            ultimas_llaves = ahora;
        }
    }

    /* La vida del jugador. Va en la fila 2, la ultima de la banda: es
       la de los mensajes, que solo salen fuera de la partida.
       Fuera de la partida np_life_bar la deja en blanco sola, asi que aqui no
       hay que saber nada del estado: se escribe lo que salga. */
    {
        uint32_t ahora = ((uint32_t)w->state << 16)
                       | ((uint32_t)w->players[0].health << 8)
                       | (uint32_t)w->players[1].health;
        if (ahora != ultima_vida) {
            char vida[NP_LIFE_BAR + 6];
            ultima_vida = ahora;
            np_life_bar(vida, w, 0);
            np_hud_print(2, 2, vida);
            if (np_player_count > 1) {
                np_life_bar(vida, w, 1);
                np_hud_print(20, 2, vida);
            }
        }
    }

    if (w->state == np_hud_estado) return;
    np_hud_borrar_fila(2);
    ultima_vida = 0xFFFFFFFFu;   /* la fila que se acaba de borrar */
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
