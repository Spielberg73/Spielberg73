/* np_sound.c - musica y efectos en la Mega Drive, por el PSG.
 *
 * La Mega Drive tiene dos chips de sonido: el YM2612 (FM, que maneja el Z80) y
 * el PSG SN76489, con tres canales de onda cuadrada y uno de ruido. El PSG lo
 * puede escribir el 68000 directamente, asi que NeoPlat lo usa para tocar las
 * mismas notas que en la Neo Geo sin necesitar codigo de Z80.
 *
 *   canal 0 -> melodia    canal 1 -> acompanamiento    canal 2 -> efectos
 *
 * Escribir en el PSG es mandar bytes al puerto $C00011:
 *   latch:  1 cc t dddd   (cc = canal, t = 1 volumen / 0 tono, dddd = 4 bits)
 *   dato:   0 0 dddddd    (los 6 bits altos del tono)
 * El volumen es atenuacion: 0 suena a tope y 15 calla.
 */

#include "np_md.h"
#include "np_sonido.h"

#define NP_CANALES 3

typedef struct {
    const NpSndPaso *paso;
    const NpSndPaso *inicio;
    uint8_t contador;
    uint8_t activo;
    uint8_t bucle;
} NpCanal;

static NpCanal np_canales[NP_CANALES];
static uint8_t np_musica_actual;

static void np_psg_tono(uint8_t canal, uint16_t periodo)
{
    *MD_PSG = (uint8_t)(0x80 | ((canal & 3) << 5) | (periodo & 0x0F));
    *MD_PSG = (uint8_t)((periodo >> 4) & 0x3F);
}

static void np_psg_volumen(uint8_t canal, uint8_t volumen)
{
    /* nuestro volumen es 0-15 de menos a mas; el PSG es al reves */
    uint8_t atenuacion = (uint8_t)(volumen > 15 ? 0 : 15 - volumen);
    *MD_PSG = (uint8_t)(0x90 | ((canal & 3) << 5) | (atenuacion & 0x0F));
}

static void np_psg_ruido(uint8_t tipo)
{
    *MD_PSG = (uint8_t)(0xE0 | (tipo & 0x07));
}

void np_sound_init(void)
{
    uint8_t i;
    for (i = 0; i < 4; i++) np_psg_volumen(i, 0);     /* todo callado */
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
    if (!secuencia) np_psg_volumen(canal, 0);
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
            np_psg_volumen(canal, 0);
            return;
        }
        c->contador = paso->duracion;
        if (paso->volumen & NP_SND_RUIDO) {
            np_psg_ruido(0x07);                    /* ruido blanco, tono medio */
            np_psg_volumen(3, (uint8_t)(paso->volumen & 0x0F));
            np_psg_volumen(canal, 0);
        } else {
            np_psg_tono(canal, paso->periodo);
            np_psg_volumen(canal, (uint8_t)(paso->volumen & 0x0F));
            if (canal == 2) np_psg_volumen(3, 0);  /* callar el ruido */
        }
        c->paso = paso + 1;
        return;
    }
}

void np_sound_update(const NpWorld *w)
{
#if NP_SOUND_ENABLED
    uint8_t i;
    uint8_t musica = (w->state == NP_STATE_PLAY && w->level->music)
        ? (uint8_t)(w->level->music - 1) : 0xFF;
    np_tocar_musica(musica);

    if (w->sfx) {
        for (i = 0; i < NP_SFX_SLOTS; i++) {
            if ((w->sfx & (1 << i)) && np_sfx_command[i]) {
                uint8_t indice = (uint8_t)(np_sfx_command[i] - 1);
                if (indice < np_snd_efecto_count)
                    np_arrancar(2, np_snd_efectos[indice], 0);
                break;
            }
        }
    }
    for (i = 0; i < NP_CANALES; i++) np_avanzar(i);
#else
    (void)w;
#endif
}
