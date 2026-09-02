/* np_musica.c - imprime que cancion toca en cada momento.
 *
 * `np_music_now()` es la regla de la musica, y la usan las seis maquinas: si
 * se equivoca, en el juego no suena lo que tiene que sonar y ni la traza ni el
 * marcador se enteran. Aqui se recorre a mano cada momento de la partida y se
 * imprime el numero de cancion que sale, que es lo que compara
 * tests/test_sonido.py con el proyecto que el mismo ha montado.
 */
#include <stdio.h>

#include "np_world.h"

int main(void)
{
    NpWorld w;

    np_world_init(&w);
    printf("tabla titulo %u\n", (unsigned)np_music_title);
    printf("tabla jefe %u\n", (unsigned)np_music_boss);
    printf("titulo %u\n", np_music_now(&w));
    np_world_step(&w, NP_IN_START, 0);
    printf("nivel %u\n", np_music_now(&w));
    printf("nivel dice %u\n", (unsigned)w.level->music);
    /* con un jefe vivo en pantalla */
    w.boss_health = 5;
    w.boss_max = 5;
    printf("jefe %u\n", np_music_now(&w));
    w.boss_health = 0;
    w.boss_max = 0;
    printf("sin jefe %u\n", np_music_now(&w));
    w.state = NP_STATE_GAME_OVER;
    printf("game over %u\n", np_music_now(&w));
    w.state = NP_STATE_LEVEL_END;
    printf("fin de nivel %u\n", np_music_now(&w));
    return 0;
}
