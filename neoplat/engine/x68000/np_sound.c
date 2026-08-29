/* np_sound.c - sonido del X68000. Todavia en silencio.
 *
 * Esta maquina lleva un YM2151 (OPM) con ocho canales de FM y un MSM6258 para
 * las muestras, y los dos los toca el 68000 directamente: no hay una CPU de
 * sonido de por medio como el Z80 de la Neo Geo o la Mega Drive, asi que va a
 * ser de los mas sencillos del kit.
 *
 * Mientras tanto esto se queda mudo a proposito, con las mismas funciones que
 * las otras cinco maquinas: asi el bucle principal es el mismo y el juego se
 * puede probar antes de que suene nada.
 */

#include "np_x68k.h"
#include "gamedata.h"

void np_sound_init(void)
{
}

void np_sound_frame(const NpWorld *w)
{
    (void)w;
}
