/* np_barra.c - imprime las barras del marcador para unos cuantos valores.
 *
 * `np_boss_bar()` y `np_life_bar()` son lo unico del motor que fabrica texto, y
 * las usan los marcadores de las cinco maquinas. Un fallo ahi no se ve en la
 * traza (no es simulacion) ni en las pruebas de emulador (el jefe del ejemplo
 * esta en el segundo nivel), asi que se comprueba aqui: tests/test_marcador.py
 * ejecuta este programa y compara las lineas una a una.
 *
 * Con un argumento cualquiera imprime la de vida en vez de la del jefe, y con
 * uno que empiece por 'e' la de "lo que llevas" (llaves y municion): las dos
 * dependen del proyecto -de `np_player_def.health` una y de las armas
 * secundarias la otra-, asi que la prueba monta el proyecto que quiere y llama
 * a este mismo programa.
 */
#include <stdio.h>

#include "np_world.h"

static void jefe(void)
{
    static const unsigned char casos[][2] = {
        {0, 0}, {0, 5}, {5, 5}, {4, 5}, {1, 5}, {3, 3}, {1, 3},
        {1, 1}, {7, 20}, {20, 20}, {1, 20}, {19, 20},
    };
    NpWorld w;
    unsigned i;
    char barra[NP_BOSS_BAR + 6];

    for (i = 0; i < sizeof(casos) / sizeof(casos[0]); i++) {
        w.boss_health = casos[i][0];
        w.boss_max = casos[i][1];
        np_boss_bar(barra, &w);
        printf("%u/%u [%s]\n", (unsigned)w.boss_health, (unsigned)w.boss_max, barra);
    }
}

/* La de vida, para el jugador 0 y para el 1: se recorre la salud de cero hasta
   la del proyecto, y ademas un jugador que no esta jugando. */
static void vida(void)
{
    NpWorld w;
    unsigned quien, salud;
    char barra[NP_LIFE_BAR + 6];

    w.state = NP_STATE_PLAY;
    for (quien = 0; quien < 2; quien++) {
        for (salud = 0; salud <= (unsigned)np_player_def.health; salud++) {
            w.players[quien].health = (unsigned char)salud;
            w.players[quien].playing = 1;
            np_life_bar(barra, &w, (unsigned char)quien);
            printf("p%u %u [%s]\n", quien, salud, barra);
        }
        w.players[quien].health = np_player_def.health;
        w.players[quien].playing = 0;
        np_life_bar(barra, &w, (unsigned char)quien);
        printf("p%u fuera [%s]\n", quien, barra);
    }
    /* y fuera de la partida: la fila es de los mensajes */
    w.players[0].health = np_player_def.health;
    w.players[0].playing = 1;
    w.state = NP_STATE_TITLE;
    np_life_bar(barra, &w, 0);
    printf("titulo [%s]\n", barra);
}

/* La linea de "lo que llevas": llaves y municion. Con mas de un arma
   secundaria en el hueco de la municion va el nombre corto del arma, asi que
   se recorren todas las que tenga el proyecto. La prueba monta el proyecto que
   quiere y llama a este mismo programa. */
static void extras(void)
{
    static const unsigned char llaves[][2] = {{0, 0}, {1, 3}, {3, 3}, {12, 99}};
    NpWorld w;
    NpLevel nivel;
    unsigned i, arma;
    char barra[NP_EXTRAS_BAR + 6];

    nivel = np_levels[0];
    w.level = &nivel;
    w.hearts = 5;
    w.sub = 0;
    for (i = 0; i < sizeof(llaves) / sizeof(llaves[0]); i++) {
        w.keys = llaves[i][0];
        nivel.keys_needed = llaves[i][1];
        np_extras_bar(barra, &w);
        printf("llaves %u/%u [%s]\n", (unsigned)w.keys,
               (unsigned)nivel.keys_needed, barra);
    }
    w.keys = 0;
    nivel.keys_needed = 0;
    for (arma = 0; arma < (np_sub_count ? np_sub_count : 1u); arma++) {
        w.sub = (uint8_t)arma;
        for (i = 0; i < 3; i++) {
            w.hearts = (unsigned char)(i == 0 ? 0 : (i == 1 ? 5 : 123));
            np_extras_bar(barra, &w);
            printf("arma %u %u [%s]\n", arma, (unsigned)w.hearts, barra);
        }
    }
}

int main(int argc, char **argv)
{
    if (argc > 1 && argv[1][0] == 'e') extras();
    else if (argc > 1) vida();
    else jefe();
    return 0;
}
