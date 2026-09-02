/* np_hud.c - marcador del Atari ST.
 *
 * El ST no tiene ni un plano de texto ni nada parecido al copper del Amiga
 * para partir la pantalla en dos: el marcador son simplemente las 24 primeras
 * lineas del mismo mapa de bits que el juego.
 *
 * Y como hay dos pantallas que se alternan, escribir el marcador directamente
 * en la que toca no vale: al frame siguiente se ve la otra, que sigue con lo
 * de antes. Asi que el marcador se escribe en una copia aparte (np_hud_bitmap,
 * 320x24 con la misma forma que la pantalla) y np_video.c la vuelca en las dos
 * pantallas cuando algo cambia. Como cambia poco -el tanteo, el tiempo cada
 * segundo-, en un frame normal no se copia nada.
 */

#include "np_st.h"

#define NP_HUD_COLUMNAS 40                       /* 40 caracteres de 8 px */
#define NP_HUD_FILAS (NP_HUD_ALTO / 8)

/* Alineado a cuatro: np_video.c lo vuelca a la pantalla de palabra larga
   en palabra larga, y en el 68000 una lectura asi en direccion impar es un
   address error. */
uint8_t np_hud_bitmap[NP_HUD_BYTES] __attribute__((aligned(4)));

static uint8_t np_hud_sucio;                     /* 1 = hay algo nuevo que copiar */

uint8_t np_hud_cambiado(void)
{
    uint8_t hubo = np_hud_sucio;
    np_hud_sucio = 0;
    return hubo;
}

/* Un caracter: ocho filas de ocho pixeles, un bit por pixel en la fuente. En
   la pantalla del ST cada grupo de 16 pixeles son cuatro palabras seguidas,
   una por plano, asi que el byte que toca esta en el grupo x/16, en el plano
   que corresponda y en la mitad par o impar de su palabra. */
static void np_hud_char(uint8_t col, uint8_t fila, uint8_t c)
{
    const uint8_t *glifo = np_font_data + (uint32_t)np_font_index[c & 0x7F] * 8;
    uint8_t y;
    if (col >= NP_HUD_COLUMNAS || fila >= NP_HUD_FILAS) return;
    for (y = 0; y < 8; y++) {
        uint8_t *destino = np_hud_bitmap + (uint32_t)(fila * 8 + y) * NP_PASO_FILA
                         + (col >> 1) * (NP_PLANOS * 2) + (col & 1);
        uint8_t bits = glifo[y];
        uint8_t plano;
        for (plano = 0; plano < NP_PLANOS; plano++)
            destino[plano * 2] = ((NP_HUD_COLOR >> plano) & 1) ? bits : 0;
    }
    np_hud_sucio = 1;
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
    for (i = 0; i < NP_HUD_BYTES; i++) np_hud_bitmap[i] = 0;
    np_hud_puntos = 0xFFFFFFFFUL;
    np_hud_tiempo = 0xFFFF;
    np_hud_estado = 0xFFFF;
    np_hud_vidas = 0xFF;
    np_hud_vidas2 = 0xFF;
    np_hud_etiquetas = 0;
    np_hud_sucio = 1;
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

static void np_hud_borrar_fila(uint8_t fila)
{
    uint8_t col;
    for (col = 0; col < NP_HUD_COLUMNAS; col++) np_hud_char(col, fila, ' ');
}

void np_hud_draw(const NpWorld *w)
{
    static uint8_t ultimo_jefe = 0xFF;
    static uint32_t ultimas_llaves = 0xFFFFFFFFu;
    static uint32_t ultima_vida = 0xFFFFFFFFu;
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

    /* La vida del jugador. Va en la fila 2, que es tambien la de los mensajes.
       Fuera de la partida np_life_bar deja la barra en blanco, y **eso no
       vale**: escribir un espacio borra lo que hubiera debajo, asi que la
       barra en blanco se comia el principio del mensaje (salia "VEL CLEAR" en
       vez de "LEVEL CLEAR"). Fuera de la partida la fila es del mensaje y no
       se toca; igual que en el X68000, donde ya estaba visto. */
    if (w->state == NP_STATE_PLAY) {
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

    if (w->state == np_hud_estado) return;    /* el mensaje sigue igual */
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
