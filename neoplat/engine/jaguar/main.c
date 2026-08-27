/* main.c - bucle principal del juego en la Atari Jaguar.
 *
 * El mismo bucle que en las otras tres maquinas, porque la parte que decide lo
 * que pasa en el juego (np_world.c) es la misma en todas.
 */

#include "np_jaguar.h"

static NpWorld world;

int main(void)
{
    np_jaguar_init();
    np_hud_clear();
    np_sound_init();
    np_world_init(&world);

    for (;;) {
        uint16_t input = np_input_read();
        uint16_t input2 = np_player_count > 1 ? np_input_read2() : 0;
        np_world_step(&world, input, input2);
        np_sound_update(&world);
        np_wait_vblank();
        np_video_frame(&world);
    }
    return 0;
}
