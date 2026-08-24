/* np_sound.h - envio de ordenes de sonido del 68000 al Z80.
 *
 * En la Neo Geo el chip de sonido cuelga del Z80, no del 68000: el juego
 * escribe un byte en el puerto de sonido y el driver de la ROM M1 (generado por
 * ngplat, ver tools/ngplat/m1.py) lo interpreta.
 *
 * Formato del byte:  bit 6 = alternancia (para poder repetir el mismo sonido
 * dos veces seguidas), bits 0-5 = que suena:
 *     $01..$2F  efecto de sonido
 *     $30..$3E  musica
 *     $3F       parar la musica
 */
#ifndef NP_SOUND_H
#define NP_SOUND_H

#include "np_world.h"

#define NP_REG_SOUND ((volatile uint8_t *)0x320000)

#define NP_CMD_MUSIC_BASE 0x30
#define NP_CMD_MUSIC_STOP 0x3F

void np_sound_init(void);
void np_sound_command(uint8_t payload);
void np_sound_update(const NpWorld *w);

#endif /* NP_SOUND_H */
