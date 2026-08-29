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

/* Cada letra del marcador es una escritura al puerto del VDP, y casi ningun
   frame cambia nada: solo se escribe lo que ha cambiado, como en las otras
   tres maquinas. */
void np_hud_draw(const NpWorld *w)
{
    static uint16_t ultimo_estado = 0xFFFF;
    static uint32_t ultimo_tanteo = 0xFFFFFFFFu;
    static uint16_t ultimas_vidas = 0xFFFF;
    static uint16_t ultimas_vidas2 = 0xFFFF;
    static uint16_t ultimo_tiempo = 0xFFFF;
    static uint8_t rotulos = 0;
    static uint8_t ultimo_jefe = 0xFF;
    static uint32_t ultimas_llaves = 0xFFFFFFFFu;
    static uint32_t ultima_vida = 0xFFFFFFFFu;
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
            np_hud_print(20, 2, llaves, NP_HUD_PALETTE);
            ultimas_llaves = ahora;
        }
    }

    /* La vida del jugador. Va en la fila 0: la ventana del VDP son tres
       filas (0 a 2) y el marcador solo usa la 1 y la 2, asi que la de arriba
       estaba libre y no hay que agrandar la ventana ni tapar mas juego.
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
            np_hud_print(2, 0, vida, NP_HUD_PALETTE);
            if (np_player_count > 1) {
                np_life_bar(vida, w, 1);
                np_hud_print(20, 0, vida, NP_HUD_PALETTE);
            }
        }
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
