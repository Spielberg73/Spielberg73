/* np_sound.c - musica y efectos en la Jaguar.
 *
 * La Jaguar no tiene chip de sonido: tiene dos DAC de 16 bits y hay que darles
 * una muestra cada vez que el reloj de audio hace tic, unas veinte mil veces
 * por segundo. Eso no lo puede hacer el 68000, asi que lo hace el **DSP** de
 * Jerry, que es quien recibe la interrupcion I2S.
 *
 * El reparto queda asi:
 *
 *   - el DSP genera las ondas: tres cuadradas, un ruido y una muestra digital,
 *     sumados. Su programa lo escribe y lo ensambla el compilador
 *     (tools/ngplat/jerry.py) y viene en sonido.c como una tabla de longs;
 *   - el 68000 hace lo de siempre, lo mismo que en el Amiga y la Mega Drive:
 *     lleva la cuenta de las secuencias del game.yaml y, cada frame, deja en la
 *     RAM del DSP que paso y que amplitud toca cada canal.
 *
 * El bloque compartido son diez palabras seguidas:
 *
 *     paso0 paso1 paso2 amplitud0 amplitud1 amplitud2 amplitud_ruido
 *     pcm_puntero pcm_fin pcm_ganancia
 *
 * El paso es el incremento de fase de 32 bits; en la tabla de notas cabe en 16
 * (paso >> 14), asi que aqui se devuelve a su sitio.
 *
 * De la muestra digital el 68000 solo escribe donde empieza y donde acaba: el
 * puntero **lo adelanta el DSP**, un byte por cada muestra de audio, y cuando
 * llega al final lo pone a cero y se apaga sola. Por eso el WAV viene ya a la
 * frecuencia del DSP y aqui no hay que llevar ninguna cuenta.
 */

#include "np_jaguar.h"
#include "np_sonido.h"

#define NP_CANALES 3
#define NP_PARAMETROS 10
#define NP_PCM_PUNTERO 7
#define NP_PCM_FIN 8
#define NP_PCM_GANANCIA 9
/* La muestra llega a +-128 y aqui todo se suma en el mismo DAC, asi que la
   ganancia es cuanto pesa frente a la musica. Mientras suena una muestra el
   canal de efectos esta callado, asi que lo mas que puede sumarse es la musica
   a tope (2 * 15 * 400 = 12.000) mas 128 * 110 = 14.080: 26.080 de los 32.767
   que caben. */
#define NP_PCM_GAIN 110
#define NP_DESPLAZAMIENTO 14        /* el que usa jerry.py al guardar el paso */
/* Aqui los cuatro canales se suman en el mismo DAC, asi que el reparto de
   volumen lo decide el motor: los efectos y la percusion pesan casi el doble
   que la musica para que se oigan por encima de ella, como en las maquinas que
   tienen un canal aparte. Con los volumenes mas altos posibles la suma se
   queda en 22.500 de los 32.767 que caben. */
#define NP_AMPLITUD 400             /* por cada punto de volumen (0-15)       */
#define NP_AMPLITUD_SFX 700

typedef struct {
    const NpSndPaso *paso;
    const NpSndPaso *inicio;
    uint8_t contador;
    uint8_t activo;
    uint8_t bucle;
} NpCanal;

static NpCanal np_canales[NP_CANALES];
static uint8_t np_musica_actual;
static volatile uint32_t *np_bloque;

static uint32_t np_amplitud(uint8_t canal, uint8_t volumen)
{
    uint16_t escala = (canal >= 2) ? NP_AMPLITUD_SFX : NP_AMPLITUD;
    return (uint32_t)((volumen > 15 ? 15 : volumen) * escala);
}

static void np_nota(uint8_t canal, uint16_t campo, uint8_t volumen)
{
    if (!np_bloque) return;
    np_bloque[canal] = (uint32_t)campo << NP_DESPLAZAMIENTO;
    np_bloque[NP_CANALES + canal] = np_amplitud(canal, volumen);
}

static void np_callar(uint8_t canal)
{
    if (np_bloque) np_bloque[NP_CANALES + canal] = 0;
}

static void np_ruido(uint8_t volumen)
{
    if (np_bloque) np_bloque[NP_CANALES * 2] = np_amplitud(2, volumen);
}

/* Arrancar una muestra: se le da al DSP donde empieza y donde acaba, y el
   resto lo lleva el. El orden importa: primero el final y la ganancia y
   despues el puntero, porque es el puntero lo que hace que empiece a sonar. */
static void np_muestra(const NpSndMuestra *m)
{
    if (!np_bloque) return;
    np_bloque[NP_PCM_FIN] = (uint32_t)(uintptr_t)m->datos + m->largo;
    np_bloque[NP_PCM_GANANCIA] = NP_PCM_GAIN;
    np_bloque[NP_PCM_PUNTERO] = (uint32_t)(uintptr_t)m->datos;
}

void np_sound_init(void)
{
    uint16_t i;
    volatile uint32_t *destino = D_RAM;

    D_CTRL = 0;                              /* el DSP, parado */
    for (i = 0; i < np_dsp_palabras; i++)
        destino[i] = np_dsp_codigo[i];

    np_bloque = (volatile uint32_t *)(uintptr_t)np_dsp_parametros;
    for (i = 0; i < NP_PARAMETROS; i++) np_bloque[i] = 0;

    SCLK = np_dsp_sclk;                      /* la frecuencia de muestreo */
    SMODE = NP_SMODE;
    D_PC = np_dsp_inicio;
    D_CTRL = NP_DSPGO;                       /* y a correr */

    for (i = 0; i < NP_CANALES; i++) {
        np_canales[i].paso = 0;
        np_canales[i].activo = 0;
    }
    np_musica_actual = 0xFF;
}

static void np_arrancar(uint8_t canal, const NpSndPaso *secuencia, uint8_t bucle)
{
    np_canales[canal].paso = secuencia;
    np_canales[canal].inicio = secuencia;
    np_canales[canal].contador = 1;
    np_canales[canal].activo = secuencia ? 1 : 0;
    np_canales[canal].bucle = bucle;
    if (!secuencia) np_callar(canal);
}

static void np_tocar_musica(uint8_t indice)
{
#if NP_SOUND_ENABLED
    if (indice == np_musica_actual) return;
    np_musica_actual = indice;
    if (indice == 0xFF || indice >= np_snd_musica_count) {
        np_arrancar(0, 0, 0);
        np_arrancar(1, 0, 0);
        return;
    }
    np_arrancar(0, np_snd_musica[indice * 2], 1);
    np_arrancar(1, np_snd_musica[indice * 2 + 1], 1);
#else
    (void)indice;
#endif
}

static void np_avanzar(uint8_t canal)
{
    NpCanal *c = &np_canales[canal];
    if (!c->activo) return;
    if (--c->contador) return;
    for (;;) {
        const NpSndPaso *paso = c->paso;
        if (!paso || paso->duracion == 0) {
            if (c->bucle && c->inicio) { c->paso = c->inicio; continue; }
            c->activo = 0;
            np_callar(canal);
            if (canal == 2) np_ruido(0);
            return;
        }
        c->contador = paso->duracion;
        if (paso->volumen & NP_SND_RUIDO) {
            np_ruido((uint8_t)(paso->volumen & 0x0F));
            np_callar(canal);
        } else {
            np_nota(canal, paso->periodo, (uint8_t)(paso->volumen & 0x0F));
            if (canal == 2) np_ruido(0);
        }
        c->paso = paso + 1;
        return;
    }
}

void np_sound_update(const NpWorld *w)
{
#if NP_SOUND_ENABLED
    uint8_t i;
    /* Cual toca lo decide el motor (np_music_now): aqui solo se pasa del
       numero de musica al indice de la tabla. */
    uint8_t suena = np_music_now(w);
    uint8_t musica = suena ? (uint8_t)(suena - 1) : 0xFF;
    np_tocar_musica(musica);

    if (w->sfx) {
        for (i = 0; i < NP_SFX_SLOTS; i++) {
            if ((w->sfx & (1 << i)) && np_sfx_command[i]) {
                uint8_t indice = (uint8_t)(np_sfx_command[i] - 1);
                if (indice < np_snd_efecto_count) {
                    const NpSndMuestra *m = &np_snd_muestras[indice];
                    if (m->largo) {
                        np_arrancar(2, 0, 0);      /* callar las notas */
                        np_ruido(0);
                        np_muestra(m);
                    } else {
                        np_arrancar(2, np_snd_efectos[indice], 0);
                    }
                }
                break;
            }
        }
    }
    for (i = 0; i < NP_CANALES; i++) np_avanzar(i);
#else
    (void)w;
#endif
}
