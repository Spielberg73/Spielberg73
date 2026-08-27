/* main.c - bucle principal del juego en la Mega Drive.
 *
 * Un frame: leer el mando, simular, sonar, esperar al retrazo y dibujar.
 * Igual que en la Neo Geo, porque la simulacion es la misma.
 */

#include "np_md.h"

static NpWorld world;        /* ~3 KB en la RAM de trabajo, no en la pila */

int main(void)
{
    np_md_init();
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
