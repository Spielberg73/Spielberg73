/* np_sound.c - musica y efectos en el Amiga, por Paula.
 *
 * Paula tiene cuatro canales de sonido digital: cada uno lee una onda de la
 * RAM chip por DMA y la repite sin parar. Para dar una nota no hace falta una
 * muestra larga: basta una onda cuadrada de dos bytes (+64 y -64) y cambiarle
 * el periodo, que es justo lo que hacen el SSG de la Neo Geo y el PSG de la
 * Mega Drive. Asi las tres maquinas tocan exactamente las mismas notas.
 *
 *   canal 0 -> melodia    canal 1 -> acompanamiento
 *   canal 2 -> efectos    canal 3 -> ruido (percusion)
 *
 * El periodo lo calcula el compilador: periodo = 3546895 / (2 * hercios).
 * El volumen de Paula va de 0 a 64; el del kit, de 0 a 15.
 */

#include "np_amiga.h"
#include "np_sonido.h"

#define NP_CANALES 3
#define NP_CANAL_RUIDO 3

/* La onda: dos bytes bastan para una cuadrada perfecta. Tiene que estar en RAM
   chip, y lo esta porque el ejecutable entero se carga ahi. */
static const int8_t np_onda_cuadrada[2] = { 64, -64 };

/* Ruido para la percusion: una tabla corta que no repite ningun patron que se
   note al oido. */
static const int8_t np_onda_ruido[16] = {
    59, -47, 12, -63, 33, 51, -20, -58, 7, 62, -35, 24, -12, 45, -61, 18
};

typedef struct {
    const NpSndPaso *paso;
    const NpSndPaso *inicio;
    uint8_t contador;
    uint8_t activo;
    uint8_t bucle;
} NpCanal;

static NpCanal np_canales[NP_CANALES];
static uint8_t np_musica_actual;

static void np_paula_onda(uint8_t canal, const int8_t *datos, uint16_t palabras)
{
    DMACON = (uint16_t)(0x0001 << canal);            /* parar el canal */
    AUDLC(canal) = NP_DIR(datos);
    AUDLEN(canal) = palabras;
}

static void np_paula_nota(uint8_t canal, uint16_t periodo, uint8_t volumen)
{
    if (periodo < 124) periodo = 124;                /* la DMA no da para mas */
    AUDPER(canal) = periodo;
    AUDVOL(canal) = (uint16_t)((volumen > 15 ? 15 : volumen) * 64 / 15);
    DMACON = (uint16_t)(0x8000 | (0x0001 << canal)); /* y a sonar */
}

static void np_paula_callar(uint8_t canal)
{
    AUDVOL(canal) = 0;
    DMACON = (uint16_t)(0x0001 << canal);
}

void np_sound_init(void)
{
    uint8_t i;
    for (i = 0; i < 4; i++) {
        np_paula_onda(i, np_onda_cuadrada, 1);
        np_paula_callar(i);
    }
    np_paula_onda(NP_CANAL_RUIDO, np_onda_ruido, sizeof(np_onda_ruido) / 2);
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
    if (!secuencia) np_paula_callar(canal);
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
            np_paula_callar(canal);
            return;
        }
        c->contador = paso->duracion;
        if (paso->volumen & NP_SND_RUIDO) {
            np_paula_nota(NP_CANAL_RUIDO, 320, (uint8_t)(paso->volumen & 0x0F));
            np_paula_callar(canal);
        } else {
            np_paula_nota(canal, paso->periodo, (uint8_t)(paso->volumen & 0x0F));
            if (canal == 2) np_paula_callar(NP_CANAL_RUIDO);
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
