/* np_sonido.h - tablas de musica y efectos para los sistemas que suenan
 * desde el propio 68000 (Mega Drive y Amiga).
 *
 * En la Neo Geo el sonido lo lleva un Z80 con su ROM aparte; en las otras dos
 * maquinas el chip esta al alcance del 68000, asi que las secuencias van aqui,
 * en la misma ROM que el juego.
 *
 * Cada paso: el valor que hay que meter en el chip (el periodo, ya convertido
 * por el compilador), cuantos frames dura y el volumen. `duracion == 0` marca
 * el final de la secuencia.
 */
#ifndef NP_SONIDO_H
#define NP_SONIDO_H

#include "np_types.h"

#define NP_SND_RUIDO 0x80        /* bit del volumen: usar el generador de ruido */

typedef struct {
    uint16_t periodo;
    uint8_t duracion;
    uint8_t volumen;             /* 0-15, mas NP_SND_RUIDO si toca */
} NpSndPaso;

/* Las genera el compilador en sonido.c */
extern const NpSndPaso *const np_snd_efectos[];
extern const NpSndPaso *const np_snd_musica[];   /* dos pistas por cancion */
extern const uint16_t np_snd_efecto_count;
extern const uint16_t np_snd_musica_count;

#endif /* NP_SONIDO_H */
