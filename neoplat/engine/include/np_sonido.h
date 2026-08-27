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

/* Una muestra digital: sonido grabado, no notas. Cuatro de las cinco maquinas
 * saben tocarlo (todas menos el Atari ST, cuyo YM2149 solo hace ondas
 * cuadradas), cada una a su manera, pero el dato es el mismo: mono, 8 bits con
 * signo. Hay una entrada por efecto, en el mismo orden que np_snd_efectos;
 * `largo == 0` quiere decir que ese efecto no es digital y se toca con notas.
 */
typedef struct {
    /* Bytes, sin interpretar: cada maquina los guarda como le convienen (el
       Amiga con signo, que es lo que come Paula; la Jaguar con el silencio en
       128, que es lo que le conviene al `loadb` del DSP). */
    const uint8_t *datos;
    uint16_t largo;              /* en bytes */
    uint16_t periodo;            /* lo que necesita el chip para su frecuencia */
    uint16_t frames;             /* cuanto dura, en frames de video */
} NpSndMuestra;

/* Las genera el compilador en sonido.c */
extern const NpSndPaso *const np_snd_efectos[];
extern const NpSndMuestra np_snd_muestras[];
extern const NpSndPaso *const np_snd_musica[];   /* dos pistas por cancion */
extern const uint16_t np_snd_efecto_count;
extern const uint16_t np_snd_musica_count;

#endif /* NP_SONIDO_H */
