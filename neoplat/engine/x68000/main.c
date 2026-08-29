/* main.c - bucle principal del juego en el Sharp X68000.
 *
 * El mismo bucle que en las otras cinco maquinas, porque la parte que decide lo
 * que pasa (np_world.c) es la misma en todas.
 */

#include "np_x68k.h"

static NpWorld world;

int main(void)
{
    np_video_init();
    np_hud_clear();
    np_sound_init();
    np_world_init(&world);

    for (;;) {
        uint16_t input = np_input_read();
        uint16_t input2 = np_player_count > 1 ? np_input_read2() : 0;
        np_world_step(&world, input, input2);
        np_sound_frame(&world);
        np_wait_vblank();
        np_video_frame(&world);
    }
    return 0;
}
