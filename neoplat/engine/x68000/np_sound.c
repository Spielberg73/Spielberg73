/* np_sound.c - musica y efectos en el X68000, por el YM2151 (OPM).
 *
 * Ocho canales de FM con cuatro operadores cada uno, y los toca el 68000
 * directamente: no hay una CPU de sonido de por medio como el Z80 de la Neo
 * Geo o la Mega Drive. El reparto es el de las otras maquinas del kit:
 *
 *   canal 0 -> melodia    canal 1 -> acompanamiento    canal 7 -> efectos
 *
 * Los efectos van en el 7 y no en el 2 por una razon: **el generador de ruido
 * del chip solo sale por el ultimo operador del canal 7**. Los efectos son los
 * unicos pasos que pueden pedir ruido (los golpes, las explosiones), asi que
 * ponerlos ahi deja que el mismo canal haga tono y ruido, como en el Atari ST.
 *
 * Escribirlo son dos pasos, igual que el YM2149: el numero de registro en
 * $E90001 y su valor en $E90003. Antes de cada escritura hay que esperar a que
 * el chip no este ocupado (bit 7 del estado, que se lee en $E90001).
 *
 * El "instrumento" es a proposito lo mas simple que suena: algoritmo 7, que
 * pone los cuatro operadores en paralelo como portadoras, con multiplicador 1
 * y sin envolvente de caida. Sale un tono limpio en la nota que se pida, que
 * es lo que hace falta para una melodia de kit; un patch de verdad se puede
 * poner luego sin tocar nada de lo demas.
 */

#include "np_x68k.h"
#include "gamedata.h"
#include "np_sonido.h"

/* Lo que costo afinarlo, por si alguien lo vuelve a tocar.
 *
 * La tabla de notas de este chip no es la que dice la documentacion que
 * circula, y medirla es mas dificil de lo que parece: midiendo notas sueltas o
 * por tramos salieron tres tablas distintas, todas mal, porque la captura se
 * desfasa una nota y no se nota. Lo que si valio fue **mirarlo desde dentro
 * del juego**: el driver escribia en el marcador, bit a bit, el codigo que le
 * mandaba al chip, y se emparejo cada codigo con la frecuencia que salia por
 * el altavoz. Con siete pares quedo claro que todo sonaba 16 semitonos por
 * encima, y de ahi salio la cuenta buena (codigo_ym2151, en sonido.py).
 *
 * Lo demas que hubo que aprender por el camino:
 *
 *   - Al chip hay que callarlo canal por canal antes de tocar nada. Ponerle
 *     todos los registros a cero deja el TL en 0, que es el volumen **maximo**,
 *     y lo que estuviera sonando de antes berrea por encima de la musica.
 *   - Entre el numero de registro y el valor hay que esperar, y el par no
 *     puede partirse: por eso el juego corre en modo supervisor y cierra las
 *     interrupciones mientras escribe (ver arranque.S).
 *   - Un silencio viene con la nota a cero y hay que tratarlo como silencio:
 *     tocarlo daria el do mas grave del chip, que en FM pesa mas que la
 *     melodia y se la come.
 */

#define NP_CANAL_MELODIA 0
#define NP_CANAL_ACOMP   1
#define NP_CANAL_EFECTO  7           /* el unico que sabe hacer ruido */
#define NP_CANALES 3

static const uint8_t np_canal_de[NP_CANALES] = {
    NP_CANAL_MELODIA, NP_CANAL_ACOMP, NP_CANAL_EFECTO
};

/* Cuanto se baja cada voz respecto a lo que pide el game.yaml.
 *
 * El acompanamiento va cuatro puntos por debajo a proposito. En una onda
 * cuadrada -el YM2149 del ST, el PSG de la Mega Drive- una nota grave y una
 * aguda al mismo volumen se oyen parecido; en FM con los cuatro operadores en
 * paralelo la grave pesa mucho mas y se come la melodia. Esta medido: con las
 * dos voces al mismo nivel, el analizador de las pruebas reconocia el bajo en
 * la mitad de los tramos en vez de la melodia. */
static const uint8_t np_baja[NP_CANALES] = { 0, 4, 0 };

typedef struct {
    const NpSndPaso *paso;
    const NpSndPaso *inicio;
    uint8_t contador;
    uint8_t activo;
    uint8_t bucle;
} NpCanal;

static NpCanal np_canales[NP_CANALES];
static uint8_t np_musica_actual;

/* --- el chip ------------------------------------------------------------ */

/* Entre la direccion y el dato el chip pide un respiro: el bit de ocupado no
   basta, porque tarda en levantarse. Los drivers de esta maquina meten una
   espera corta y aqui se hace igual. */
static void np_opm_respirar(void)
{
    volatile uint16_t i;
    for (i = 0; i < 40; i++) { }
}

/* Escribir un registro son dos accesos -el numero y el valor- y entre uno y
   otro **no puede colarse nadie**: si una interrupcion de Human68k escribe en
   el chip por medio, nuestro valor acaba en el registro de otro. Se notaba
   como notas agudas que no estaban en la partitura. Por eso el juego corre en
   modo supervisor (ver arranque.S) y aqui se cierran las interrupciones
   mientras dura el par. */
static void np_opm(uint8_t registro, uint8_t valor)
{
    uint16_t sr;
    __asm__ volatile ("move.w %%sr,%0\n\tori.w #0x0700,%%sr"
                      : "=d"(sr) : : "cc", "memory");
    while (*NP_OPM_ESTADO & NP_OPM_OCUPADO) { }
    *NP_OPM_REGISTRO = registro;
    np_opm_respirar();
    *NP_OPM_DATO = valor;
    np_opm_respirar();
    __asm__ volatile ("move.w %0,%%sr" : : "d"(sr) : "cc", "memory");
}

/* Los cuatro operadores de un canal estan a $40, $48, $50 y $58 del registro
   base, o sea el canal mas ocho por operador. */
static void np_opm_operadores(uint8_t base, uint8_t canal, uint8_t valor)
{
    uint8_t op;
    for (op = 0; op < 4; op++)
        np_opm((uint8_t)(base + op * 8 + canal), valor);
}

/* El volumen es el TL de las portadoras, y va **al reves**: 0 es lo mas alto y
   127 el silencio. Los quince pasos del kit se reparten por ahi. */
/* El volumen es el TL de la portadora, y va **al reves**: 0 es lo mas alto y
   127 el silencio.
   Suena un solo operador de los cuatro. Con los cuatro en paralelo -que es lo
   que parecia mejor, cuatro veces mas fuerte- el tono deja de ser limpio y la
   nota que mas pesa acaba siendo un armonico agudo, no la que se ha pedido:
   medido en el emulador, con los cuatro sale un parcial seis veces mas alto y
   con uno sale la nota. */
static void np_opm_volumen(uint8_t canal, uint8_t volumen)
{
    uint8_t tl = (uint8_t)((15 - (volumen & 0x0F)) * 7 + 6);
    np_opm((uint8_t)(0x60 + canal), tl);
    np_opm((uint8_t)(0x68 + canal), 0x7F);
    np_opm((uint8_t)(0x70 + canal), 0x7F);
    np_opm((uint8_t)(0x78 + canal), 0x7F);
}

static void np_opm_nota(uint8_t canal, uint16_t codigo)
{
    np_opm((uint8_t)(0x28 + canal), (uint8_t)(codigo >> 8));      /* KC */
    np_opm((uint8_t)(0x30 + canal), (uint8_t)((codigo & 0x3F) << 2));  /* KF */
}

static void np_opm_key(uint8_t canal, uint8_t encender)
{
    np_opm(0x08, (uint8_t)(encender ? (0x78 | canal) : canal));
}

static void np_opm_ruido(uint8_t encender, uint8_t tono)
{
    np_opm(0x0F, (uint8_t)(encender ? (0x80 | (tono & 0x1F)) : 0));
}

static void np_opm_instrumento(uint8_t canal)
{
    /* $20: los dos altavoces encendidos (sin esto no se oye nada), sin
       realimentacion y algoritmo 7: los cuatro operadores en paralelo. */
    np_opm((uint8_t)(0x20 + canal), 0xC7);
    np_opm((uint8_t)(0x38 + canal), 0x00);   /* sin vibrato ni tremolo */
    np_opm_operadores(0x40, canal, 0x01);    /* multiplicador 1, sin detune */
    np_opm_operadores(0x80, canal, 0x1F);    /* ataque inmediato */
    np_opm_operadores(0xA0, canal, 0x00);    /* sin primera caida */
    np_opm_operadores(0xC0, canal, 0x00);    /* sin segunda caida */
    np_opm_operadores(0xE0, canal, 0x0F);    /* y que corte rapido al soltar */
    np_opm_volumen(canal, 0);
}

/* --- las muestras digitales --------------------------------------------
 *
 * El ADPCM de esta maquina es un MSM6258 y no lo toca el 68000 a mano: se le
 * dice a la ROM donde estan los datos y ella los va sacando por DMA mientras
 * el juego sigue a lo suyo. Los datos ya vienen cifrados del compilador, en el
 * ADPCM de la familia OKI, y en `periodo` viene el modo (la velocidad y por
 * que altavoces sale).
 *
 * _ADPCMOUT quiere la direccion en a1, el modo en d1 y el largo en d2, asi que
 * hace falta una llamada aparte: np_iocs solo pasa los datos.
 */
static void np_adpcm(const NpSndMuestra *m)
{
    register long r0 __asm__("d0") = NP_IOCS_ADPCMOUT;
    register long r1 __asm__("d1") = (long)m->periodo;
    register long r2 __asm__("d2") = (long)m->largo;
    register const uint8_t *a1 __asm__("a1") = m->datos;
    __asm__ volatile ("trap #15"
                      : "+d"(r0), "+d"(r1), "+d"(r2), "+a"(a1)
                      : : "a0", "a2", "cc", "memory");
}

/* --- las secuencias ----------------------------------------------------- */

void np_sound_init(void)
{
    uint8_t i;
    uint16_t r;
    /* El chip como lo deja Human68k no esta limpio, y limpiarlo mal es peor
       que no limpiarlo: poner todos los registros a cero deja el TL de todos
       los operadores en 0, que en este chip es el **volumen maximo**. Si algun
       canal se quedo sonando de antes, a partir de ahi berrea a toda potencia
       con la nota que tuviera. Eso es lo que pasaba: encima de la musica se
       oia un tono agudo mas fuerte que ella.
       Asi que primero se callan los ocho canales, luego se ponen todos los
       operadores al silencio y ya despues se limpia lo demas. */
    for (r = 0; r < 8; r++)
        np_opm(0x08, (uint8_t)r);            /* nota fuera, canal por canal */
    for (r = 0x60; r < 0x80; r++)
        np_opm((uint8_t)r, 0x7F);            /* TL al maximo: 127 es silencio */
    for (r = 0x01; r < 0x60; r++)
        np_opm((uint8_t)r, 0x00);
    for (r = 0x80; r < 0x100; r++)
        np_opm((uint8_t)r, 0x00);
    np_opm(0x19, 0x00);                      /* sin modulacion de fase */
    np_opm(0x19, 0x80);                      /* ni de amplitud */
    np_opm(0x1B, 0x00);                      /* nada por la salida de reloj */
    np_opm_ruido(0, 0);
    for (i = 0; i < NP_CANALES; i++) {
        uint8_t canal = np_canal_de[i];
        np_opm_instrumento(canal);
        np_opm_key(canal, 0);
        np_canales[i].paso = 0;
        np_canales[i].activo = 0;
    }
    np_musica_actual = 0xFF;
}

static void np_callar(uint8_t i)
{
    uint8_t canal = np_canal_de[i];
    np_opm_key(canal, 0);
    if (canal == NP_CANAL_EFECTO)
        np_opm_ruido(0, 0);
}

static void np_arrancar(uint8_t i, const NpSndPaso *secuencia, uint8_t bucle)
{
    np_canales[i].paso = secuencia;
    np_canales[i].inicio = secuencia;
    np_canales[i].contador = 1;
    np_canales[i].activo = secuencia ? 1 : 0;
    np_canales[i].bucle = bucle;
    if (!secuencia)
        np_callar(i);
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

static void np_avanzar(uint8_t i)
{
    NpCanal *c = &np_canales[i];
    uint8_t canal = np_canal_de[i];
    if (!c->activo) return;
    if (--c->contador) return;
    for (;;) {
        const NpSndPaso *paso = c->paso;
        if (!paso || paso->duracion == 0) {
            if (c->bucle && c->inicio) { c->paso = c->inicio; continue; }
            c->activo = 0;
            np_callar(i);
            return;
        }
        c->contador = paso->duracion;
        np_opm_key(canal, 0);
        if (paso->periodo == 0 && !(paso->volumen & NP_SND_RUIDO)) {
            /* Un silencio: el compilador lo escribe con la nota a cero. Sin
               esto sonaria un do de la octava mas grave del chip, que en FM
               pesa mas que la melodia y se la come. */
            if (canal == NP_CANAL_EFECTO)
                np_opm_ruido(0, 0);
            c->paso = paso + 1;
            return;
        }
        if (paso->volumen & NP_SND_RUIDO) {
            /* El ruido solo sale por el canal 7: si el paso lo pide en otro,
               lo mas parecido es una nota grave, que es lo que suena. */
            np_opm_ruido(canal == NP_CANAL_EFECTO, 16);
            np_opm_nota(canal, paso->periodo);
        } else {
            if (canal == NP_CANAL_EFECTO)
                np_opm_ruido(0, 0);
            np_opm_nota(canal, paso->periodo);
        }
        {
            uint8_t vol = (uint8_t)(paso->volumen & 0x0F);
            vol = (uint8_t)(vol > np_baja[i] ? vol - np_baja[i] : 0);
            np_opm_volumen(canal, vol);
        }
        np_opm_key(canal, 1);
        c->paso = paso + 1;
        return;
    }
}

void np_sound_frame(const NpWorld *w)
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
                    if (m->largo) np_adpcm(m);
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
