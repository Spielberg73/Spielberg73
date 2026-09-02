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
 *
 * Y las **muestras digitales** las toca el Z80. El DAC esta en el YM2612, que
 * el Z80 ve en $4000, y hay que darle un byte cada 125 microsegundos: eso el
 * 68000 no lo puede hacer sin dejar el juego tirado. El driver del Z80 lo
 * escribe el compilador (tools/ngplat/md_pcm.py) y viene en sonido.c como una
 * tabla de bytes; aqui solo se copia a su RAM y se le dice, cuando toca, que
 * muestra tiene que sonar. Como son chips distintos, la musica del PSG y la
 * muestra del YM2612 suenan a la vez sin estorbarse.
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
static uint8_t np_pcm_tick;

/* El bloque compartido con el Z80, en su RAM. Tiene que coincidir con las
   direcciones de tools/ngplat/md_pcm.py. */
#define NP_Z80_TICK   0x1F00
#define NP_Z80_VISTO  0x1F01
#define NP_Z80_BANCO  0x1F02
#define NP_Z80_DIR    0x1F04
#define NP_Z80_LARGO  0x1F06

/* Pedir el bus del Z80 y esperar a que lo den: mientras el 68000 lo tiene, el
   Z80 esta parado y se le puede escribir la RAM sin sincronizar nada.
   La espera lleva tope: si algo va mal, mejor sonar raro que colgarse. */
static void np_z80_parar(void)
{
    uint16_t vueltas = 0;
    *MD_Z80_BUS = 0x0100;
    while ((*MD_Z80_BUS & 0x0100) && ++vueltas) ;
}

static void np_z80_soltar(void)
{
    *MD_Z80_BUS = 0x0000;
}

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
    uint16_t j;
    for (i = 0; i < 4; i++) np_psg_volumen(i, 0);     /* todo callado */
    for (i = 0; i < NP_CANALES; i++) {
        np_canales[i].paso = 0;
        np_canales[i].activo = 0;
    }
    np_musica_actual = 0xFF;

    /* El Z80. El orden importa y es el de siempre en esta maquina:
         1. pedir el bus (con el reset ya quitado: en reset no lo da),
         2. copiar el driver byte a byte -su RAM no admite palabras-,
         3. darle un reset corto, que es lo que hace que arranque en $0000,
         4. soltar el bus.
       A partir de ahi corre solo, esperando ordenes en su bloque. */
    np_pcm_tick = 0;
    np_z80_parar();
    for (j = 0; j < np_z80_pcm_largo; j++) MD_Z80_RAM[j] = np_z80_pcm[j];
    for (j = 0; j < 8; j++) MD_Z80_RAM[NP_Z80_TICK + j] = 0;
    *MD_Z80_RESET = 0x0000;
    for (j = 0; j < 64; j++) (void)*MD_Z80_BUS;    /* el reset necesita durar */
    *MD_Z80_RESET = 0x0100;
    np_z80_soltar();
}

/* Pedirle al Z80 una muestra. El banco son los nueve bits de arriba de la
   direccion en el cartucho y la ventana que ve el Z80 empieza en $8000, asi
   que el resto de la direccion se le suma ahi. `tick` va el ultimo: es lo que
   hace que empiece. */
static void np_muestra(const NpSndMuestra *m)
{
    uint32_t direccion = (uint32_t)(uintptr_t)m->datos;
    uint16_t banco = (uint16_t)(direccion >> 15);
    uint16_t dentro = (uint16_t)(0x8000 | (direccion & 0x7FFF));

    np_pcm_tick++;
    np_z80_parar();
    MD_Z80_RAM[NP_Z80_BANCO] = (uint8_t)(banco & 0xFF);
    MD_Z80_RAM[NP_Z80_BANCO + 1] = (uint8_t)(banco >> 8);
    MD_Z80_RAM[NP_Z80_DIR] = (uint8_t)(dentro & 0xFF);
    MD_Z80_RAM[NP_Z80_DIR + 1] = (uint8_t)(dentro >> 8);
    MD_Z80_RAM[NP_Z80_LARGO] = (uint8_t)(m->largo & 0xFF);
    MD_Z80_RAM[NP_Z80_LARGO + 1] = (uint8_t)(m->largo >> 8);
    MD_Z80_RAM[NP_Z80_TICK] = np_pcm_tick;
    np_z80_soltar();
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
                    if (m->largo) np_muestra(m);
                    else np_arrancar(2, np_snd_efectos[indice], 0);
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
