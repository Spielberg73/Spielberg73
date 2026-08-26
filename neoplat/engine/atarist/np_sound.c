/* np_sound.c - musica y efectos en el Atari ST, por el YM2149.
 *
 * El YM2149 del ST es el mismo chip que el SSG del YM2610 de la Neo Geo: tres
 * canales de onda cuadrada y uno de ruido, con el periodo en doce bits. Lo
 * unico distinto es el reloj (2 MHz en el ST, 4 en la Neo Geo), y de eso ya se
 * encarga el compilador al convertir las notas.
 *
 *   canal 0 -> melodia    canal 1 -> acompanamiento    canal 2 -> efectos
 *
 * Escribirlo son dos pasos: el numero de registro en $FF8800 y su valor en
 * $FF8802. Ojo con el registro 7 (el mezclador): sus bits estan **al reves**,
 * un cero enciende el canal. Y ojo tambien con los bits 6 y 7 de ese registro,
 * que en el ST no son de sonido sino la direccion de los dos puertos de la
 * impresora y el RS-232: si se ponen mal, el ST deja de hablar con ellos. Por
 * eso el mezclador se escribe siempre partiendo de $C0.
 */

#include "np_st.h"
#include "np_sonido.h"

#define NP_CANALES 3
#define NP_MEZCLA_BASE 0xC0          /* los dos puertos, como los deja TOS */

typedef struct {
    const NpSndPaso *paso;
    const NpSndPaso *inicio;
    uint8_t contador;
    uint8_t activo;
    uint8_t bucle;
} NpCanal;

static NpCanal np_canales[NP_CANALES];
static uint8_t np_musica_actual;
static uint8_t np_mezcla;            /* copia de lo ultimo escrito en el 7 */

static void np_ym(uint8_t registro, uint8_t valor)
{
    REG8(ST_YM_REGISTRO) = registro;
    REG8(ST_YM_DATO) = valor;
}

static void np_ym_tono(uint8_t canal, uint16_t periodo)
{
    np_ym((uint8_t)(canal * 2), (uint8_t)(periodo & 0xFF));
    np_ym((uint8_t)(canal * 2 + 1), (uint8_t)((periodo >> 8) & 0x0F));
}

static void np_ym_volumen(uint8_t canal, uint8_t volumen)
{
    np_ym((uint8_t)(8 + canal), (uint8_t)(volumen > 15 ? 15 : volumen));
}

/* En el mezclador un bit a cero **enciende**: los tres de abajo son el tono de
   cada canal y los tres siguientes su ruido. */
static void np_ym_mezcla(uint8_t canal, uint8_t tono, uint8_t ruido)
{
    np_mezcla |= (uint8_t)((1 << canal) | (1 << (canal + 3)));
    if (tono) np_mezcla &= (uint8_t)~(1 << canal);
    if (ruido) np_mezcla &= (uint8_t)~(1 << (canal + 3));
    np_ym(7, np_mezcla);
}

void np_sound_init(void)
{
    uint8_t i;
    np_mezcla = NP_MEZCLA_BASE | 0x3F;           /* todo callado */
    np_ym(7, np_mezcla);
    for (i = 0; i < NP_CANALES; i++) {
        np_ym_volumen(i, 0);
        np_canales[i].paso = 0;
        np_canales[i].activo = 0;
    }
    np_ym(6, 16);                                /* ruido de tono medio */
    np_musica_actual = 0xFF;
}

static void np_arrancar(uint8_t canal, const NpSndPaso *secuencia, uint8_t bucle)
{
    np_canales[canal].paso = secuencia;
    np_canales[canal].inicio = secuencia;
    np_canales[canal].contador = 1;
    np_canales[canal].activo = secuencia ? 1 : 0;
    np_canales[canal].bucle = bucle;
    if (!secuencia) {
        np_ym_volumen(canal, 0);
        np_ym_mezcla(canal, 0, 0);
    }
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
            np_ym_volumen(canal, 0);
            np_ym_mezcla(canal, 0, 0);
            return;
        }
        c->contador = paso->duracion;
        if (paso->volumen & NP_SND_RUIDO) {
            np_ym_mezcla(canal, 0, 1);
            np_ym_volumen(canal, (uint8_t)(paso->volumen & 0x0F));
        } else {
            np_ym_tono(canal, paso->periodo);
            np_ym_mezcla(canal, 1, 0);
            np_ym_volumen(canal, (uint8_t)(paso->volumen & 0x0F));
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
