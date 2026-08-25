/* main.c - bucle principal del juego en el Amiga.
 *
 * Un frame: leer el joystick, simular, sonar, esperar al retrazo y dibujar.
 * Es el mismo bucle que en la Neo Geo y en la Mega Drive, porque la parte que
 * decide lo que pasa en el juego (np_world.c) es la misma en las tres.
 */

#include "np_amiga.h"

static NpWorld world;        /* ~3 KB: en memoria, no en la pila */

int main(void)
{
    np_amiga_init();
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
