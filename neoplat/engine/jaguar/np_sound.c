/* np_sound.c - sonido de la Jaguar.
 *
 * TODAVIA NO SUENA. El sonido de la Jaguar lo lleva Jerry, con dos DAC de 16
 * bits que alimenta su propio procesador (el DSP). Hacerlo bien pide un
 * programa para ese DSP, que es otro juego de instrucciones y otro ensamblador;
 * queda para la siguiente vuelta. El resto del motor no cambia: cuando este,
 * solo hay que rellenar estas dos funciones.
 */

#include "np_jaguar.h"

void np_sound_init(void)
{
}

void np_sound_update(const NpWorld *w)
{
    (void)w;
}
