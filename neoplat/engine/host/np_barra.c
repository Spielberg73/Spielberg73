/* np_barra.c - imprime la barra de vida del jefe para unos cuantos valores.
 *
 * `np_boss_bar()` es lo unico del motor que fabrica texto, y lo usan los
 * marcadores de las cuatro maquinas. Un fallo ahi no se ve en la traza (no es
 * simulacion) ni en las pruebas de emulador (el jefe del ejemplo esta en el
 * segundo nivel), asi que se comprueba aqui: tests/test_marcador.py ejecuta
 * este programa y compara las lineas una a una.
 */
#include <stdio.h>

#include "np_world.h"

int main(void)
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
    return 0;
}
