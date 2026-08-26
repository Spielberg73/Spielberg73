/* main.c - bucle principal del juego en el Atari ST.
 *
 * El mismo bucle que en las otras cuatro maquinas -leer el mando, simular,
 * sonar y dibujar- con una diferencia: el ST **simula dos veces por cada vez
 * que dibuja**. El juego corre a 50 pasos por segundo, igual que en las demas
 * (si no, no seria el mismo juego), pero la pantalla se refresca a 25, que es
 * lo que da de si un 68000 a 8 MHz sin blitter. Esta medido, no supuesto: ver
 * docs/atarist.md.
 *
 * Y ojo con el orden, que no es un detalle: **una sola espera por vuelta, y al
 * principio**. La primera version esperaba al retrazo despues de cada paso, y
 * eso tiraba un frame entero por vuelta: el trabajo de verdad (simular dos
 * veces y dibujar) cabe de sobra en los dos frames, pero repartido en trozos
 * que no llegaban a tiempo al siguiente retrazo se comia tres. De 16 frames por
 * segundo a 25 sin tocar una sola linea del dibujado.
 */

#include "np_st.h"

static NpWorld world;        /* ~3 KB: en memoria, no en la pila */

int main(void)
{
    uint8_t paso;

    np_st_init();
    np_hud_clear();
    np_sound_init();
    np_world_init(&world);

    for (;;) {
        np_wait_vblank();
        for (paso = 0; paso < NP_PASOS_POR_DIBUJO; paso++) {
            uint16_t input = np_input_read();
            np_world_step(&world, input);
            np_sound_update(&world);
        }
        np_video_frame(&world);
    }
    return 0;
}
