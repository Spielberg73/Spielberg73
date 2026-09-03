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

/* Una linea de texto en el plano fix.
 *
 * El fix se direcciona por columnas, asi que dos letras seguidas estan a 32
 * words una de otra: con el modulo de la VRAM puesto a 32 se busca la direccion
 * **una vez** y luego solo se escribe. Buscarla por letra costaba tres
 * escrituras de registro en vez de una, y el marcador es lo unico que se
 * escribe en el peor frame de todos (el del golpe, que repinta la vida). */
void np_hud_print(uint8_t col, uint8_t row, const char *text, uint8_t palette)
{
    if (!*text || col >= NP_FIX_COLS) return;
    np_vram_seek((uint16_t)(NP_FIXMAP + col * 32 + row), 32);
    while (*text && col < NP_FIX_COLS) {
        uint8_t c = (uint8_t)*text++;
        uint16_t tile = (c < 128) ? np_font_index[c] : 0;
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
    /* Estado por pintar. El frame en el que cambia el estado es tambien el de
       la carga del nivel -se crean todas las entidades y se redibujan todos
       los sprites- y es, con diferencia, el mas caro de la partida: 206.000
       ciclos frente a los 160.000 del siguiente peor, medido con
       tests/maquina_neogeo.py. Repintar ademas el marcador entero ahi es lo
       que lo saca de los 200.000 que da la consola, y no hace falta: se
       aparta para el frame siguiente, que va sobrado. Los caches de cada
       campo se quedan viejos, asi que se repintan solos. */
    static uint16_t estado_pendiente = 0xFFFF;
    static uint32_t ultimo_tanteo = 0xFFFFFFFFu;
    static uint16_t ultimas_vidas = 0xFFFF;
    static uint16_t ultimas_vidas2 = 0xFFFF;
    static uint16_t ultimo_tiempo = 0xFFFF;
    static uint8_t rotulos = 0;
    static uint8_t ultimo_jefe = 0xFF;
    static uint32_t ultimas_llaves = 0xFFFFFFFFu;
    static uint32_t ultima_bolsa = 0xFFFFFFFFu;
    static uint32_t ultima_vida = 0xFFFFFFFFu;
    uint16_t segundos = (uint16_t)(w->time_left / 60);

    if (w->state != last_state) {
        last_state = w->state;
        estado_pendiente = w->state;
        return;                   /* el frame de la carga se deja en paz */
    }

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

    /* Lo que llevas -llaves y municion- al lado de la barra del jefe. Igual
       que ella: solo se repinta cuando cambia algo. */
    {
        /* los tres numeros en un solo valor, cada uno en su byte: mezclarlos
           con un OR haria que uno tapara al otro y el marcador se quedaria
           colgado */
        uint32_t ahora = ((uint32_t)w->keys << 16) | ((uint32_t)w->hearts << 8)
                       | (uint32_t)(w->level ? w->level->keys_needed : 0);
        /* y lo que llevas encima: sin esto la bolsa cambiaba y el
           marcador seguia ensenando lo de antes */
        uint32_t bolsa = np_bolsa_firma(w);
        if (ahora != ultimas_llaves || bolsa != ultima_bolsa) {
            char llaves[NP_EXTRAS_BAR + 1];
            np_extras_bar(llaves, w);
            np_hud_print(20, 2, llaves, NP_HUD_PALETTE);
            ultimas_llaves = ahora;
            ultima_bolsa = bolsa;
        }
    }

    /* La vida del jugador. Va en la fila 3, que en el plano fix esta libre:
       aqui el marcador no es una banda, se dibuja encima del juego. Fuera de la
       partida np_life_bar la deja en blanco sola, asi que aqui no hay que saber
       nada del estado: se escribe lo que salga.
   
       Esta es la unica parte del marcador que se repinta en el frame del golpe,
       que es el mas caro de la partida (y la Neo Geo va justa de ciclos), asi
       que cuando lo unico que ha cambiado es la salud se saltan las letras de
       la etiqueta y se escriben solo los cuadrados. */
    {
        uint32_t ahora = ((uint32_t)w->state << 16)
                       | ((uint32_t)w->players[0].health << 8)
                       | (uint32_t)w->players[1].health;
        if (ahora != ultima_vida) {
            /* la etiqueta solo hace falta cuando cambia el estado: dentro de la
               partida no se mueve */
            uint8_t solo_salud = ((ahora >> 16) == (ultima_vida >> 16));
            uint8_t desde = solo_salud ? NP_LIFE_LABEL : 0;
            char vida[NP_LIFE_BAR + 6];
            uint8_t quien;
            ultima_vida = ahora;
            for (quien = 0; quien < np_player_count; quien++) {
                np_life_bar(vida, w, quien);
                np_hud_print((uint8_t)(2 + quien * 18 + desde), 3, vida + desde,
                             NP_HUD_PALETTE);
            }
        }
    }

    if (estado_pendiente != 0xFFFF) {
        /* Se borran todas las filas donde puede caer un mensaje (12 a 16), no
           solo las de en medio: si no, el titulo de la fila 12 y el autor de
           la 16 se quedaban pegados encima del juego al pulsar start. */
        uint8_t row;
        for (row = 12; row <= 16; row++)
            np_hud_blank(10, row, 20);
        estado_pendiente = 0xFFFF;
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
