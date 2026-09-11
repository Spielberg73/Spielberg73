/* np_sound.c - musica y efectos en la Mega Drive: el YM2612 y el PSG.
 *
 * La Mega Drive tiene dos chips de sonido y aqui se usan los dos, cada uno para
 * lo que se le da bien:
 *
 *   YM2612   seis voces de **FM** de cuatro operadores. La musica: la melodia
 *            en el canal 1 y el acompanamiento en el 2, cada una con su timbre
 *            (ver tools/ngplat/fm.py). El canal 6 se queda para el DAC.
 *   PSG      tres ondas cuadradas y un ruido. Los efectos, en su canal 3, que
 *            asi ni tapan a la musica ni se los come ella.
 *
 * El YM2612 **vive en el bus del Z80**: para escribirle hay que parar al Z80,
 * que es el mismo trato que ya habia para mandarle una muestra. Se para una vez
 * por frame, se escribe todo lo que haya que escribir y se le suelta; mientras
 * esta parado no alimenta el DAC, asi que cuanto menos se le tenga, mejor.
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

/* Los canales 0 y 1 son los dos del YM2612 y el 2 es el del PSG. El numero de
   canal es el mismo para el motor: lo unico que cambia es a que chip va. */
#define NP_ES_FM(canal) ((canal) < 2)

/* Con que timbre suena cada uno de los dos canales de FM ahora mismo, para no
   volver a escribir los veintiseis registros en cada nota. */
static uint8_t np_fm_puesto[2];

/* La mezcla, y es una decision, no un numero al azar: el FM suena **mucho** mas
   que el PSG -es un chip de 1988 contra uno de 1980- y si se le deja a tope se
   come los efectos, que van por el PSG, y el bajo se come a la melodia. Asi que
   la musica entra un poco por debajo y el acompanamiento, mas: la melodia
   manda, el acompanamiento acompana y el efecto se oye por encima de los dos.
   Son unidades de `tl`, tres cuartos de decibelio cada una. */
static const uint8_t NP_FM_MEZCLA[2] = { 10, 18 };

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

/* --- el YM2612 ----------------------------------------------------------
 *
 * Escribir un registro son dos pasos -primero cual y luego que- y entre uno y
 * otro hay que dejar que el chip respire: el bit 7 del puerto de estado dice si
 * sigue ocupado. La espera lleva tope por lo mismo que la del bus: mejor sonar
 * raro que colgarse.
 *
 * Todo esto solo vale con el Z80 parado. Lo hace np_fm_abrir/np_fm_cerrar, que
 * envuelven la vuelta entera de la musica: asi se para una vez y no cuarenta.
 */
static void np_ym_esperar(void)
{
    uint16_t vueltas = 0;
    while ((*MD_YM_DIR0 & 0x80) && ++vueltas) ;
}

static void np_ym(uint8_t reg, uint8_t valor)
{
    np_ym_esperar();
    *MD_YM_DIR0 = reg;
    np_ym_esperar();
    *MD_YM_DAT0 = valor;
}

/* El timbre entero en un canal: los seis registros de cada uno de los cuatro
   operadores, mas el algoritmo y los dos altavoces. Son 26 escrituras, y por
   eso solo se hace cuando **cambia** el timbre, no en cada nota. */
static void np_fm_timbre(uint8_t canal, const NpFmTimbre *t)
{
    uint8_t i;
    for (i = 0; i < 4; i++) {
        uint8_t d = (uint8_t)(canal + i * 4);
        np_ym((uint8_t)(0x30 + d), t->dt_mul[i]);
        np_ym((uint8_t)(0x40 + d), t->tl[i]);
        np_ym((uint8_t)(0x50 + d), t->ks_ar[i]);
        np_ym((uint8_t)(0x60 + d), t->am_dr[i]);
        np_ym((uint8_t)(0x70 + d), t->sr[i]);
        np_ym((uint8_t)(0x80 + d), t->sl_rr[i]);
    }
    np_ym((uint8_t)(0xB0 + canal), t->alg_fb);
    /* Los dos altavoces. Sin esto el chip toca y no se oye **nada**: es el
       fallo clasico de la primera vez que uno enciende un YM2612. */
    np_ym((uint8_t)(0xB4 + canal), 0xC0);
}

/* El volumen de una nota, que en FM no es un registro de volumen sino el `tl`
   de las portadoras -las que suenan-. Va al reves: 0 es a tope. A los
   moduladores no se les toca, que ahi el `tl` es el brillo y bajarselo cambia
   el timbre en vez del volumen. */
static void np_fm_volumen(uint8_t canal, const NpFmTimbre *t, uint8_t volumen)
{
    uint8_t i;
    uint8_t suma = (uint8_t)((volumen > 15 ? 0 : 15 - volumen) * 3
                             + NP_FM_MEZCLA[canal & 1]);
    for (i = 0; i < 4; i++) {
        uint16_t tl;
        if (!(t->portadoras & (1 << i))) continue;
        tl = (uint16_t)(t->tl[i] + suma);
        np_ym((uint8_t)(0x40 + canal + i * 4), (uint8_t)(tl > 127 ? 127 : tl));
    }
}

static void np_fm_nota(uint8_t canal, uint16_t nota)
{
    /* El orden importa: primero la parte de arriba -octava y los tres bits
       altos-, que el chip se la guarda, y al escribir la de abajo entra todo de
       una vez. Al reves, la nota suena un instante desafinada. */
    np_ym((uint8_t)(0xA4 + canal),
          (uint8_t)((NP_FM_BLOQUE(nota) << 3) | (NP_FM_FNUM(nota) >> 8)));
    np_ym((uint8_t)(0xA0 + canal), (uint8_t)(NP_FM_FNUM(nota) & 0xFF));
}

static void np_fm_pulsar(uint8_t canal, uint8_t operadores)
{
    np_ym(0x28, (uint8_t)((operadores << 4) | (canal & 3)));
}

/* Y al terminar de escribir, **devolverle la direccion al Z80**.
 *
 * Esto no es cortesia: es la unica forma de que las muestras sigan sonando. El
 * driver del Z80 (tools/ngplat/md_pcm.py) deja la direccion del YM apuntando al
 * registro del DAC de una vez por todas y a partir de ahi solo escribe bytes de
 * datos, que es lo que le permite alimentarlo cada 125 microsegundos. Si el
 * 68000 escribe un registro de FM y se va dejando ahi **su** direccion, los
 * bytes del Z80 entran en ese registro en vez de en el DAC: la muestra
 * desaparece y ademas se le escribe basura al chip. Medido: sin esta linea, 0
 * de energia en la frecuencia de la muestra; con ella, se oye como siempre. */
#define NP_YM_DAC 0x2A

static void np_fm_devolver(void)
{
    np_ym_esperar();
    *MD_YM_DIR0 = NP_YM_DAC;
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
    np_fm_puesto[0] = np_fm_puesto[1] = 0xFF;

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

    /* Y el YM2612, que vive en este mismo bus: sin vibrato, sin temporizadores
       y con las seis voces calladas. El bus ya esta pedido de arriba. */
    np_ym(0x22, 0x00);                     /* el LFO, apagado */
    np_ym(0x27, 0x00);                     /* temporizadores y modo normal */
    for (i = 0; i < 3; i++) {
        np_ym(0x28, i);                    /* canales 1-3, sueltos */
        np_ym(0x28, (uint8_t)(4 + i));     /* y 4-6 */
    }
    np_fm_devolver();
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

static void np_callar(uint8_t canal)
{
    if (NP_ES_FM(canal)) np_fm_pulsar(canal, 0x00);   /* soltar la nota */
    else np_psg_volumen(canal, 0);
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
    /* El timbre de cada pista, antes de la primera nota. Si es el mismo que ya
       estaba puesto no se vuelve a escribir: son veintiseis registros. */
    {
        uint8_t p;
        for (p = 0; p < 2; p++) {
            uint8_t cual = np_fm_musica[indice * 2 + p];
            if (cual >= np_fm_timbre_count) cual = 0;
            if (np_fm_puesto[p] != cual) {
                np_fm_timbre(p, &np_fm_timbres[cual]);
                np_fm_puesto[p] = cual;
            }
        }
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
            return;
        }
        c->contador = paso->duracion;
        if (NP_ES_FM(canal)) {
            const NpFmTimbre *t = &np_fm_timbres[np_fm_puesto[canal] < np_fm_timbre_count
                                                 ? np_fm_puesto[canal] : 0];
            /* Soltar y volver a pulsar aunque sea la misma nota: si no, dos
               negras seguidas del mismo tono suenan como una blanca. */
            np_fm_pulsar(canal, 0x00);
            if (paso->periodo) {
                np_fm_volumen(canal, t, (uint8_t)(paso->volumen & 0x0F));
                np_fm_nota(canal, paso->periodo);
                np_fm_pulsar(canal, 0x0F);         /* los cuatro operadores */
            }
        } else if (paso->volumen & NP_SND_RUIDO) {
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

    /* Todo lo que toca el YM2612 va con el Z80 parado: el chip esta en **su**
       bus, y escribirle con el Z80 corriendo es escribir en el suelo. Asi
       empezo esto: el juego sonaba a silencio y el chip ni se enteraba.
     *
     * Pero solo se le para si hay algo que escribir. Un canal de musica cambia
     * de nota una vez cada `velocidad` frames -una de cada ocho, de serie- y
     * los otros siete no hay nada que decirle al chip. Parando el Z80 **todos**
     * los frames las muestras digitales dejaban de sonar del todo: mientras
     * esta parado no alimenta el DAC, y un byte cada 125 microsegundos no
     * espera a nadie. Medido: sin esto, 0 de energia en la frecuencia de la
     * muestra; con esto, se oye como antes. */
    if (musica != np_musica_actual
        || (np_canales[0].activo && np_canales[0].contador <= 1)
        || (np_canales[1].activo && np_canales[1].contador <= 1)) {
        np_z80_parar();
        np_tocar_musica(musica);
        np_avanzar(0);
        np_avanzar(1);
        np_fm_devolver();
        np_z80_soltar();
    } else {
        /* Nada que escribir: se baja el contador a mano y se le deja en paz. */
        if (np_canales[0].activo) np_canales[0].contador--;
        if (np_canales[1].activo) np_canales[1].contador--;
    }

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
    /* Y el del PSG, fuera: ese chip lo escribe el 68000 sin pedirle permiso a
       nadie. */
    np_avanzar(2);
    (void)i;
#else
    (void)w;
#endif
}
