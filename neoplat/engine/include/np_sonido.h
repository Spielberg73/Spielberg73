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

/* --- los timbres de FM ---------------------------------------------------
 *
 * Tres maquinas del kit llevan un chip de FM de cuatro operadores: el YM2612
 * de la Mega Drive, el YM2610 de la Neo Geo y el YM2151 del X68000. Un timbre
 * son esos cuatro operadores -cuatro senos con su envolvente- y como se
 * conectan entre si.
 *
 * Los bytes vienen **ya empaquetados** por el compilador en el orden en el que
 * los quiere el chip, incluida la rareza de que los cuatro operadores no van
 * seguidos en los registros sino en el orden 1, 3, 2, 4. Aqui solo hay que
 * escribirlos: el juego no sabe nada de FM, solo copia.
 */
typedef struct {
    uint8_t alg_fb;              /* realimentacion y algoritmo, ya juntos */
    uint8_t dt_mul[4];           /* en orden de registro, no de operador */
    uint8_t tl[4];
    uint8_t ks_ar[4];
    uint8_t am_dr[4];
    uint8_t sr[4];
    uint8_t sl_rr[4];
    uint8_t portadoras;          /* un bit por operador que se oye */
} NpFmTimbre;

/* En las secuencias de FM, `periodo` no es un periodo sino la nota tal y como
 * la quiere el chip: el bloque (la octava) en los bits altos y el `fnum` en los
 * once de abajo. Se parte con estas dos. */
#define NP_FM_BLOQUE(p) ((uint8_t)((p) >> 11))
#define NP_FM_FNUM(p)   ((uint16_t)((p) & 0x07FF))

/* Las genera el compilador en sonido.c */
extern const NpSndPaso *const np_snd_efectos[];
extern const NpSndMuestra np_snd_muestras[];
extern const NpSndPaso *const np_snd_musica[];   /* dos pistas por cancion */
extern const uint16_t np_snd_efecto_count;
extern const uint16_t np_snd_musica_count;
/* Los timbres que usa el juego y con cual suena cada pista de cada cancion
   (dos por cancion, en el mismo orden que np_snd_musica). Los generan solo las
   maquinas con chip de FM; en las demas no existen. */
extern const NpFmTimbre np_fm_timbres[];
extern const uint8_t np_fm_musica[];
extern const uint16_t np_fm_timbre_count;

#endif /* NP_SONIDO_H */
