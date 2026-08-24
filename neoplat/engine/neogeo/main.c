/* main.c - bucle principal del juego en la Neo Geo.
 *
 * Un frame = leer mando -> simular -> esperar vblank -> dibujar.
 * Dibujar despues del vblank evita que se vea el redibujado a medias.
 */

#include "np_video.h"
#include "gamedata.h"

static NpWorld world;      /* ~3 KB: mejor en RAM estatica que en la pila */

int main(void)
{
    np_video_init();
    np_world_init(&world);

    for (;;) {
        uint16_t input = np_input_read();
        np_world_step(&world, input);
        np_wait_vblank();
        np_video_frame(&world);
        *NP_REG_WATCHDOG = 0;      /* si no se toca, la placa se reinicia */
    }
    return 0;
}
