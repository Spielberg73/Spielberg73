/* np_hud.c - marcador del Amiga, en su propia franja de pantalla.
 *
 * El Amiga no tiene un plano de texto que se pueda poner encima, asi que el
 * marcador vive en un mapa de bits aparte (320x24) y es el copper el que
 * cambia los punteros de los bitplanes al llegar a la linea NP_HUD_ALTO: de
 * ahi para arriba se ve el marcador y de ahi para abajo, el juego.
 *
 * Como es texto y cambia poco, se dibuja con la CPU: cada caracter son ocho
 * bytes de la fuente, uno por fila, que se copian a los planos donde el color
 * NP_HUD_COLOR tiene un bit a uno.
 */

#include "np_amiga.h"

#define NP_HUD_COLUMNAS (NP_HUD_BYTES_FILA)      /* 40 caracteres de 8 px */
#define NP_HUD_FILAS (NP_HUD_ALTO / 8)

static void np_hud_char(uint8_t col, uint8_t fila, uint8_t c)
{
    const uint8_t *glifo = np_font_data + (uint32_t)np_font_index[c & 0x7F] * 8;
    uint8_t y;
    if (col >= NP_HUD_COLUMNAS || fila >= NP_HUD_FILAS) return;
    for (y = 0; y < 8; y++) {
        uint8_t *destino = np_hud_bitmap + (fila * 8 + y) * NP_HUD_PASO + col;
        uint8_t bits = glifo[y];
        uint8_t plano;
        for (plano = 0; plano < NP_PLANOS; plano++)
            destino[plano * NP_HUD_BYTES_FILA] =
                ((NP_HUD_COLOR >> plano) & 1) ? bits : 0;
    }
}

/* Lo ultimo que se escribio, para no repintar lo que no ha cambiado. */
static uint32_t np_hud_puntos = 0xFFFFFFFFUL;
static uint16_t np_hud_tiempo = 0xFFFF;
static uint16_t np_hud_estado = 0xFFFF;
static uint8_t np_hud_vidas = 0xFF;
static uint8_t np_hud_vidas2 = 0xFF;
static uint8_t np_hud_etiquetas;

void np_hud_clear(void)
{
    uint16_t i;
    for (i = 0; i < NP_HUD_ALTO * NP_HUD_PASO; i++) np_hud_bitmap[i] = 0;
    np_hud_puntos = 0xFFFFFFFFUL;
    np_hud_tiempo = 0xFFFF;
    np_hud_estado = 0xFFFF;
    np_hud_vidas = 0xFF;
    np_hud_vidas2 = 0xFF;
    np_hud_etiquetas = 0;
}

void np_hud_print(uint8_t col, uint8_t fila, const char *texto)
{
    while (*texto && col < NP_HUD_COLUMNAS) np_hud_char(col++, fila, (uint8_t)*texto++);
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

/* Borra una fila entera del marcador (los mensajes de estado). */
static void np_hud_borrar_fila(uint8_t fila)
{
    uint8_t col;
    for (col = 0; col < NP_HUD_COLUMNAS; col++) np_hud_char(col, fila, ' ');
}

/* Escribir en el mapa de bits lo hace la CPU byte a byte, y con cinco
 * bitplanes por medio la memoria chip va justa: repintar el marcador entero
 * cuesta mas de la mitad de un frame. Por eso solo se toca lo que cambia; en
 * un frame normal no se escribe nada. */
void np_hud_draw(const NpWorld *w)
{
    static uint8_t ultimo_jefe = 0xFF;
    static uint32_t ultimas_llaves = 0xFFFFFFFFu;
    uint16_t segundos;

    if (!np_hud_etiquetas) {            /* las palabras fijas, una sola vez */
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
        np_hud_number(8, 0, w->score, 6);
        np_hud_puntos = w->score;
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
    if (np_time_limit) {
        segundos = (uint16_t)(w->time_left / 60);
        if (segundos != np_hud_tiempo) {
            np_hud_number(23, 0, segundos, 3);
            np_hud_tiempo = segundos;
        }
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

    if (w->state == np_hud_estado) return;    /* el mensaje sigue igual */
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
