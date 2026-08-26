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
        np_world_step(&world, input);
        np_sound_update(&world);
        np_wait_vblank();
        np_video_frame(&world);
    }
    return 0;
}
