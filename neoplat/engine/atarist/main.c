/* main.c - bucle principal del juego en el Atari ST.
 *
 * El mismo bucle que en las otras cuatro maquinas -leer el mando, simular,
 * sonar y dibujar- con una diferencia: el ST **simula dos veces por cada vez
 * que dibuja**. El juego corre a 50 pasos por segundo, igual que en las demas
 * (si no, no seria el mismo juego), pero la pantalla se refresca a 25, que es
 * lo que da de si un 68000 a 8 MHz sin blitter. Esta medido, no supuesto: ver
 * docs/atarist.md.
 *
 * Y ojo con el orden, que no es un detalle y costo dos intentos:
 *
 *   - **una espera por paso**, y no una por vuelta. Con una sola espera, en una
 *     pantalla con poco que dibujar la vuelta entera cabia en un frame y el
 *     juego corria **al doble de velocidad**: el reloj del juego no puede
 *     depender de cuanto haya que pintar;
 *   - y **dibujar dentro del bucle y repartido**: el escenario en el primer
 *     paso y los actores en el segundo. Asi cada mitad cabe de sobra en el
 *     frame que de todas formas hay que esperar. Haciendolo todo de una vez el
 *     trabajo se salia por poco de un frame y costaba otro entero: 16 frames
 *     por segundo en vez de 25.
 */

#include "np_st.h"

/* Medir lo que cuesta simular, con el mismo truco del borde que np_video.c:
 * -DNP_MEDIR=5 pone el color 0 en rojo mientras corren los pasos del motor. */
#ifndef NP_MEDIR
#define NP_MEDIR 0
#endif

static NpWorld world;        /* ~3 KB: en memoria, no en la pila */

int main(void)
{
    uint8_t paso;

    np_st_init();
    np_hud_clear();
    np_sound_init();
    np_world_init(&world);

    for (;;) {
        for (paso = 0; paso < NP_PASOS_POR_DIBUJO; paso++) {
            uint16_t input = np_input_read();
#if NP_MEDIR == 5
            REG16(ST_PALETA) = 0x0700;
#endif
            np_world_step(&world, input);
            np_sound_update(&world);
#if NP_MEDIR == 5
            REG16(ST_PALETA) = world.level->background;
#endif
            /* el dibujado, repartido entre los pasos: ver np_video.c */
            if (paso == 0) np_video_escenario(&world);
            if (paso == NP_PASOS_POR_DIBUJO - 1) np_video_actores(&world);
            np_wait_vblank();
        }
    }
    return 0;
}
