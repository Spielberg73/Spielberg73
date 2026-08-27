/* np_video.c - dibujado del juego en el Atari ST.
 *
 * En el Amiga hay un mapa de bits mas ancho que la pantalla y el scroll lo
 * hace el hardware moviendo unos punteros. Aqui no hay nada de eso: la
 * pantalla del ST empieza siempre donde diga el Shifter, pero solo con
 * precision de 256 bytes (linea y media), asi que **no sirve para mover el
 * escenario**. Todo lo que se mueve, lo mueve la CPU.
 *
 * De ahi salen las tres decisiones que explican el resto del archivo:
 *
 *   1. **Dos pantallas.** Se dibuja en la que no se ve y al final del frame se
 *      cambia la direccion que lee el Shifter (eso si es gratis). Sin esto los
 *      actores parpadean: entre borrarlos y volverlos a dibujar pasa medio
 *      frame y el haz pasa por encima.
 *
 *   2. **El escenario se mueve de 16 en 16 pixeles.** Dibujar un tile en una
 *      x cualquiera obliga a desplazar bit a bit las cuatro palabras de cada
 *      fila, y eso cuesta cuatro veces mas que copiarlas tal cual. Con la
 *      vista pegada a la rejilla de tiles, el escenario se copia sin
 *      desplazar; los actores si van al pixel, porque son pocos.
 *
 *   3. **Al avanzar la vista se mueve la memoria, no se repinta.** Correr las
 *      176 lineas del juego ocho bytes a la izquierda y pintar la columna que
 *      entra sale mas barato que volver a dibujar las 240 casillas.
 *
 * Como cada pantalla se ve un frame si y otro no, la que toca dibujar va **dos
 * frames atrasada**: por eso cada una lleva apuntado por su cuenta que trozo
 * del mundo tiene dentro y que actores hay que borrar.
 */

#include "np_st.h"

#define NP_MAX_RASTROS 48

typedef struct {
    int16_t x, y, ancho, alto;
} NpRastro;

/* Lo que hay dentro de cada una de las dos pantallas. */
typedef struct {
    uint8_t *pixeles;
    int32_t vista_x, vista_y;        /* esquina de arriba a la izquierda */
    const NpLevel *nivel;
    NpRastro rastros[NP_MAX_RASTROS];
    uint8_t rastro_count;
    uint8_t hud;                     /* 1 = hay que copiar el marcador */
} NpBuffer;

static NpBuffer np_buffers[NP_PANTALLAS];
static uint8_t np_cual;              /* la que se esta dibujando */

void np_acia_isr(void);              /* el manejador del teclado (mas abajo) */
void np_ikbd_atender(void);          /* y lo que hace por dentro */

/* --- arranque ----------------------------------------------------------- */

static void np_ver(const uint8_t *pantalla)
{
    uint32_t direccion = (uint32_t)(uintptr_t)pantalla;
    REG8(ST_VIDEO_ALTA) = (uint8_t)(direccion >> 16);
    REG8(ST_VIDEO_MEDIA) = (uint8_t)(direccion >> 8);
}

/* Por donde va el haz.
 *
 * Sin interrupciones no hay quien avise del retrazo, asi que se mira el
 * contador de video: sube desde la direccion de la pantalla hasta el final de
 * la ultima linea y ahi se queda hasta el frame siguiente. De sus tres bytes
 * basta el de en medio, que es el que cuenta las lineas (256 bytes son linea y
 * media), y ademas asi la lectura es de una sola vez y no puede pillar el
 * contador a medio cambiar.
 *
 * Las dos pantallas estan alineadas a 32 KB, asi que ese byte va de 0 a $7D en
 * las dos (32000 = $7D00) salvo por el bit de arriba, que dice cual es: de ahi
 * el `& 0x7F`. La cuenta sale igual se este viendo la que se este viendo. */
#define NP_FIN_PINTADO 0x7C          /* de aqui en adelante ya no pinta nada */

static uint8_t np_cuenta(void)
{
    return (uint8_t)(REG8(ST_CUENTA_MEDIA) & 0x7F);
}

void np_wait_vblank(void)
{
    while (np_cuenta() >= NP_FIN_PINTADO) ;   /* salir del retrazo de ahora */
    while (np_cuenta() < NP_FIN_PINTADO) ;    /* y esperar al siguiente */
}

/* El IKBD arranca mandando la posicion del raton, que aqui no sirve de nada y
   solo ensucia la linea. Se le apaga y se le pide que avise del joystick. */
static void np_ikbd(uint8_t orden)
{
    while (!(REG8(ST_ACIA_ESTADO) & 0x02)) ;      /* esperar a que pueda enviar */
    REG8(ST_ACIA_DATO) = orden;
}

void np_st_init(void)
{
    uint32_t base = ((uint32_t)(uintptr_t)np_pantallas + (NP_HUECO_PANTALLA - 1))
                    & ~(uint32_t)(NP_HUECO_PANTALLA - 1);
    uint8_t i;

    for (i = 0; i < NP_PANTALLAS; i++) {
        np_buffers[i].pixeles =
            (uint8_t *)(uintptr_t)(base + i * NP_HUECO_PANTALLA);
        np_buffers[i].vista_x = -30000;           /* nada dibujado todavia */
        np_buffers[i].vista_y = -30000;
        np_buffers[i].nivel = 0;
        np_buffers[i].rastro_count = 0;
        np_buffers[i].hud = 1;
    }
    np_cual = 0;

    REG8(ST_RESOLUCION) = 0;                      /* 320x200, 16 colores */
    REG8(ST_SINCRONIA) = 0x02;                    /* 50 Hz */
    for (i = 0; i < 16; i++)
        REG16(ST_PALETA + i * 2) = np_colores[i];
    np_ver(np_buffers[0].pixeles);

    np_ikbd(0x12);                                /* raton, fuera */
    np_ikbd(0x14);                                /* y avisa del joystick */

    /* del MFP se deja viva solo la linea del teclado, y se le pone nuestro
       manejador; el vector es el $46, o sea la direccion $118 */
    REG8(MFP_IERA) = 0x00;
    REG8(MFP_IERB) = MFP_ACIA;
    REG8(MFP_IMRA) = 0x00;
    REG8(MFP_IMRB) = MFP_ACIA;
    *(volatile uint32_t *)(uintptr_t)ST_VECTOR_ACIA = (uint32_t)(uintptr_t)np_acia_isr;
    REG8(MFP_IPRA) = 0x00;                        /* un cero borra lo pendiente */
    REG8(MFP_IPRB) = 0x00;
    /* Y **vaciar el ACIA antes de abrir las interrupciones**, que no es un
       detalle: el MFP avisa cuando la linea del teclado *baja*, y esa linea se
       queda abajo mientras haya un byte sin leer. Si TOS dejo uno ahi (o llego
       uno mientras se le hablaba al IKBD), al borrar lo pendiente se pierde el
       unico aviso que iba a haber: no vuelve a bajar nunca y el mando se queda
       muerto para siempre. Costo una prueba que fallaba una vez de cada dos. */
    np_ikbd_atender();
    __asm__ volatile ("move.w #0x2500,%sr");      /* pasa el nivel 6 y nada mas */
}

/* --- el mando -----------------------------------------------------------
 *
 * El IKBD habla por una linea serie a 7812 baudios y el ACIA que la recibe
 * **solo guarda un byte**: si llega el siguiente antes de leer el anterior, el
 * anterior se pierde. Y sus mensajes son de dos y tres bytes seguidos, o sea
 * un cuarto de milisegundo entre uno y otro. Mirarlo una vez por frame (20 ms)
 * no vale: se pierde justo la cabecera y el resto se lee como si fueran
 * teclas. Esta medido en la maquina: con la cabecera perdida, el joystick
 * mueve al jugador una vez de cada tantas.
 *
 * Asi que el ACIA se atiende por interrupcion, que es para lo que esta. De las
 * del MFP se deja encendida **solo esa** y se baja la mascara a nivel 5, que
 * deja pasar el nivel 6 (el MFP) y sigue tapando el retrazo y los relojes de
 * TOS: el juego se queda con la maquina igual que antes, pero sin perder
 * teclas.
 *
 * El IKBD manda tres cosas mezcladas:
 *
 *   - teclas sueltas: el codigo de la tecla, y el mismo mas $80 al soltarla;
 *   - joystick: $FE o $FF (segun el puerto) y detras el estado de las cuatro
 *     direcciones y el boton;
 *   - y el raton, que manda $F8-$FB y dos bytes mas cada vez que se mueve.
 *
 * Al arrancar se le pide al IKBD que calle el raton, pero los paquetes que ya
 * venian de camino hay que tragarselos igual: si no, sus dos bytes de
 * desplazamiento se leerian como si fueran teclas. De ahi el contador de bytes
 * que faltan por descartar.
 *
 * Valen el teclado y el joystick a la vez, y los dos puertos: en un emulador el
 * mando puede salir por cualquiera de ellos y no hay forma de saberlo desde aqui.
 */
#define ST_TECLA_IZQUIERDA 0x4B
#define ST_TECLA_DERECHA   0x4D
#define ST_TECLA_ARRIBA    0x48
#define ST_TECLA_ABAJO     0x50
#define ST_TECLA_ESPACIO   0x39
#define ST_TECLA_ENTRAR    0x1C

static volatile uint16_t np_teclas;   /* lo que sigue pulsado */
static volatile uint16_t np_joystick;
static uint8_t np_faltan;            /* bytes que quedan del paquete de ahora */
static uint8_t np_es_joystick;       /* 1 = el paquete de ahora es del joystick */

static void np_tecla(uint8_t codigo, uint16_t pulsada)
{
    uint16_t bit = 0;
    switch (codigo) {
    case ST_TECLA_IZQUIERDA: bit = NP_IN_LEFT; break;
    case ST_TECLA_DERECHA:   bit = NP_IN_RIGHT; break;
    case ST_TECLA_ARRIBA:    bit = NP_IN_UP; break;
    case ST_TECLA_ABAJO:     bit = NP_IN_DOWN; break;
    case ST_TECLA_ESPACIO:   bit = NP_IN_JUMP; break;
    case ST_TECLA_ENTRAR:    bit = NP_IN_START; break;
    default: return;
    }
    if (pulsada) np_teclas |= bit;
    else np_teclas &= (uint16_t)~bit;
}

/* La parte en C de la interrupcion. Se llama desde np_acia_isr, que es quien
   guarda los registros y avisa al MFP de que ya esta atendida. */
void np_ikbd_atender(void)
{
    while (REG8(ST_ACIA_ESTADO) & 0x01) {
        uint8_t byte = REG8(ST_ACIA_DATO);
        if (np_faltan) {
            np_faltan--;
            if (!np_es_joystick) continue;        /* raton: no interesa */
            np_es_joystick = 0;
            np_joystick = 0;
            if (byte & 0x01) np_joystick |= NP_IN_UP;
            if (byte & 0x02) np_joystick |= NP_IN_DOWN;
            if (byte & 0x04) np_joystick |= NP_IN_LEFT;
            if (byte & 0x08) np_joystick |= NP_IN_RIGHT;
            /* el joystick solo tiene un boton: vale de salto y de start */
            if (byte & 0x80) np_joystick |= NP_IN_JUMP | NP_IN_START;
        } else if (byte >= 0xF8 && byte <= 0xFB) {
            np_faltan = 2;                        /* raton: cabecera y dos deltas */
        } else if (byte == 0xFE || byte == 0xFF) {
            np_faltan = 1;                        /* joystick 0 o 1: da igual cual */
            np_es_joystick = 1;
        } else if (byte < 0xF6) {
            np_tecla((uint8_t)(byte & 0x7F), (uint16_t)!(byte & 0x80));
        }
    }
    /* el MIDI comparte la misma interrupcion: si tiene algo hay que sacarlo,
       porque si no la linea se queda pidiendo atencion para siempre */
    if (REG8(ST_MIDI_ESTADO) & 0x01) (void)REG8(ST_MIDI_DATO);
}

/* El manejador de verdad. En ensamblador porque tiene que acabar en `rte` y
   avisar al MFP de que la interrupcion ya esta servida (el bit 6 de ISRB): TOS
   deja el chip en modo "fin por software" y, sin eso, no vuelve a avisar. */
__asm__(
"    .text\n"
"    .globl np_acia_isr\n"
"np_acia_isr:\n"
"    movem.l %d0-%d1/%a0-%a1,-(%sp)\n"
"    jsr     np_ikbd_atender\n"
"    movem.l (%sp)+,%d0-%d1/%a0-%a1\n"
"    bclr    #6,0xFFFA11\n"
"    rte\n");

uint16_t np_input_read(void)
{
    /* Red de seguridad: si por lo que sea quedo un byte sin leer, la linea del
       teclado se queda abajo y el MFP no vuelve a avisar. Mirarlo una vez por
       frame cuesta una lectura y devuelve el mando a la vida. */
    if (REG8(ST_ACIA_ESTADO) & 0x01) np_ikbd_atender();
    return (uint16_t)(np_teclas | np_joystick);
}

/* --- dibujar un tile -----------------------------------------------------
 *
 * `x` va siempre en multiplos de 16, asi que un tile son ocho bytes seguidos
 * por fila y se copian tal cual. `y` puede caer donde sea: las filas que se
 * salen del area de juego se recortan.
 *
 * Se copia de cuatro en cuatro bytes y no de dos en dos: el 68000 tarda lo
 * mismo en mover una palabra que una palabra larga cuando ya tiene la
 * direccion, asi que ir de long en long cuesta la mitad. Los dos extremos
 * estan alineados a cuatro (la pantalla porque empieza en multiplo de 32 KB y
 * cada fila mide 160 bytes; el tile porque mide 128).
 */
static void np_tile_en(uint8_t *pantalla, uint16_t tile, int32_t x, int32_t y)
{
    const uint32_t *origen;
    uint32_t *destino;
    int32_t f, desde = 0, hasta = NP_TILE;

    if (x < 0 || x >= NP_ANCHO) return;
    if (y < NP_HUD_ALTO) desde = NP_HUD_ALTO - y;
    if (y + NP_TILE > NP_ALTO) hasta = NP_ALTO - y;
    if (desde >= hasta) return;

    origen = (const uint32_t *)(const void *)(np_tile_data
             + (uint32_t)tile * (NP_TILE * NP_PLANOS * 2) + desde * NP_PLANOS * 2);
    destino = (uint32_t *)(void *)(pantalla + (uint32_t)(y + desde) * NP_PASO_FILA
                                   + (uint32_t)(x >> 1));
    for (f = desde; f < hasta; f++) {
        destino[0] = origen[0];
        destino[1] = origen[1];
        origen += 2;
        destino += NP_PASO_FILA / 4;
    }
}

/* --- dibujar un actor ----------------------------------------------------
 *
 * Aqui `x` si va al pixel, asi que hay que desplazar. El truco de siempre:
 * meter la palabra en la mitad de arriba de un entero de 32 bits y correrlo a
 * la derecha tantos bits como haga falta; arriba queda lo que va en el grupo
 * de 16 pixeles donde empieza el dibujo y abajo lo que se sale al siguiente.
 *
 * El bucle de dentro se recorre 64 veces por dibujo (16 filas x 4 planos), asi
 * que lo que no dependa del plano sale fuera **a la fuerza**: si se recorta o
 * no por los lados y la mascara ya invertida. La primera version lo miraba
 * todo dentro y el ST dibujaba a 10 frames por segundo; con esto y los tiles a
 * palabras largas sube a 25 (medido, ver docs/atarist.md).
 *
 * Las filas transparentes enteras se saltan, y con ellas ocho escrituras en
 * memoria: en un dibujo normal eso es la cuarta parte del trabajo.
 */

/* Los cuatro planos de una fila, con el dibujo desplazado y recortado por la
   mascara. `izq`/`der` dicen si cada uno de los dos grupos de 16 pixeles cae
   dentro de la pantalla; van como argumentos y no como condiciones dentro
   porque el compilador hace tres copias del bucle, una por caso. */
#define NP_FILA_SPRITE(izq, der)                                              \
    do {                                                                      \
        uint8_t p;                                                            \
        for (p = 0; p < NP_PLANOS; p++) {                                     \
            uint32_t v = ((uint32_t)fuente[p] << 16) >> desplazamiento;       \
            if (izq) destino[p] = (uint16_t)((destino[p] & hueco_i)           \
                                             | (uint16_t)(v >> 16));          \
            if (der) destino[p + NP_PLANOS] =                                 \
                (uint16_t)((destino[p + NP_PLANOS] & hueco_d) | (uint16_t)v); \
        }                                                                     \
    } while (0)

static void np_sprite_en(uint8_t *pantalla, uint16_t tile, int32_t x, int32_t y)
{
    const uint16_t *dib;
    const uint16_t *msk;
    uint16_t desplazamiento = (uint16_t)(x & 15);
    int32_t grupo = x >> 4;                       /* en grupos de 16 pixeles */
    int32_t f, desde = 0, hasta = NP_TILE;
    uint8_t izquierda = (uint8_t)(grupo >= 0 && grupo < NP_COLUMNAS);
    uint8_t derecha = (uint8_t)(grupo + 1 >= 0 && grupo + 1 < NP_COLUMNAS);
    uint16_t *fila;

    if (!izquierda && !derecha) return;
    if (y < NP_HUD_ALTO) desde = NP_HUD_ALTO - y;
    if (y + NP_TILE > NP_ALTO) hasta = NP_ALTO - y;
    if (desde >= hasta) return;

    dib = (const uint16_t *)(const void *)(np_tile_data
          + (uint32_t)tile * (NP_TILE * NP_PLANOS * 2));
    msk = (const uint16_t *)(const void *)(np_tile_mask
          + (uint32_t)tile * (NP_TILE * 2));
    fila = (uint16_t *)(void *)(pantalla + (uint32_t)(y + desde) * NP_PASO_FILA
                                + (uint32_t)(grupo * 8));

    for (f = desde; f < hasta; f++, fila += NP_PASO_FILA / 2) {
        uint32_t mascara = ((uint32_t)msk[f] << 16) >> desplazamiento;
        const uint16_t *fuente = dib + f * NP_PLANOS;
        uint16_t *destino = fila;
        uint16_t hueco_i, hueco_d;
        uint8_t pinta_i, pinta_d;
        if (!mascara) continue;                   /* fila transparente entera */
        hueco_i = (uint16_t)~(uint16_t)(mascara >> 16);
        hueco_d = (uint16_t)~(uint16_t)mascara;
        /* y si a un lado de la fila no hay nada opaco, tampoco hay nada que
           escribir ahi: en un dibujo pequeno (una moneda, una gema) eso es la
           mitad de las escrituras */
        pinta_i = (uint8_t)(izquierda && hueco_i != 0xFFFF);
        pinta_d = (uint8_t)(derecha && hueco_d != 0xFFFF);
        if (pinta_i && pinta_d) NP_FILA_SPRITE(1, 1);
        else if (pinta_i) NP_FILA_SPRITE(1, 0);
        else if (pinta_d) NP_FILA_SPRITE(0, 1);
    }
}

/* --- el escenario -------------------------------------------------------- */

/* Una columna de tiles del mundo, en la pantalla `b`. */
static void np_columna(NpBuffer *b, const NpWorld *w, int32_t tile_x)
{
    uint16_t tiles[NP_FILAS];
    int32_t x = tile_x * NP_TILE - b->vista_x;
    int32_t primera = (b->vista_y + NP_HUD_ALTO) >> 4;
    int32_t f;
    if (x < 0 || x >= NP_ANCHO) return;
    np_tile_gfx_column(w->level, tile_x, primera, NP_FILAS, tiles);
    for (f = 0; f < NP_FILAS; f++)
        np_tile_en(b->pixeles, tiles[f], x, (primera + f) * NP_TILE - b->vista_y);
}

static void np_redibujar_todo(NpBuffer *b, const NpWorld *w)
{
    int32_t primera = b->vista_x >> 4;
    int32_t c;
    for (c = 0; c < NP_COLUMNAS; c++) np_columna(b, w, primera + c);
    b->rastro_count = 0;
}

/* Corre el area de juego `grupos` grupos de 16 pixeles hacia un lado.
 *
 * Es lo mas caro que hace el ST en todo el frame y no hay forma de evitarlo en
 * un 520: son 176 lineas de 152 bytes, casi 27 KB. Aqui si merece la pena el
 * ensamblador, y esta medido: escrito en C, gcc genera `move.l (a1),(a0)` con
 * desplazamiento y sale a 8,5 ciclos por byte, o sea **449 lineas de barrido**,
 * frame y medio. Con `movem.l`, que mueve doce registros de una tacada, son 4,8
 * y bajan a 253. Esa diferencia es justo la que separa dibujar en dos frames de
 * necesitar tres: con la version en C el juego caia a 16 frames por segundo
 * cada vez que el escenario avanzaba.
 *
 * Doce registros son 48 bytes por vuelta:
 *
 *     movem.l (a0)+,d0/d2-d7/a2-a6     12 + 8x12 = 108 ciclos
 *     movem.l d0/d2-d7/a2-a6,(a1)       8 + 8x12 = 104
 *     lea     48(a1),a1                            8
 *     dbra    d1,bucle                            10
 *
 * Y hacia atras hay que ir del final al principio, porque origen y destino se
 * solapan; `movem` lee los 48 bytes enteros antes de escribir ninguno, asi que
 * dentro de cada bloque el solape da igual.
 */
#define NP_LARGOS_BLOQUE 12              /* palabras largas por vuelta */

void np_mover_bloques(uint32_t *destino, const uint32_t *origen, int32_t bloques);
void np_mover_bloques_atras(uint32_t *destino, const uint32_t *origen,
                            int32_t bloques);

#ifdef __mc68000__
__asm__(
"    .text\n"
"    .globl np_mover_bloques\n"
"np_mover_bloques:\n"
"    movem.l %d2-%d7/%a2-%a6,-(%sp)\n"     /* once registros: 44 bytes de pila */
"    move.l  48(%sp),%a1\n"                /* destino */
"    move.l  52(%sp),%a0\n"                /* origen  */
"    move.w  58(%sp),%d1\n"                /* bloques (la palabra baja) */
"    subq.w  #1,%d1\n"
"    bmi.s   9f\n"
"1:  movem.l (%a0)+,%d0/%d2-%d7/%a2-%a6\n"
"    movem.l %d0/%d2-%d7/%a2-%a6,(%a1)\n"
"    lea     48(%a1),%a1\n"
"    dbra    %d1,1b\n"
"9:  movem.l (%sp)+,%d2-%d7/%a2-%a6\n"
"    rts\n"
"\n"
"    .globl np_mover_bloques_atras\n"
"np_mover_bloques_atras:\n"                /* destino y origen apuntan al final */
"    movem.l %d2-%d7/%a2-%a6,-(%sp)\n"
"    move.l  48(%sp),%a1\n"
"    move.l  52(%sp),%a0\n"
"    move.w  58(%sp),%d1\n"
"    subq.w  #1,%d1\n"
"    bmi.s   9f\n"
"1:  lea     -48(%a0),%a0\n"
"    movem.l (%a0),%d0/%d2-%d7/%a2-%a6\n"
"    lea     -48(%a1),%a1\n"
"    movem.l %d0/%d2-%d7/%a2-%a6,(%a1)\n"
"    dbra    %d1,1b\n"
"9:  movem.l (%sp)+,%d2-%d7/%a2-%a6\n"
"    rts\n");
#else
/* En el ordenador no hay movem: las pruebas compilan este archivo para
   comprobar la sintaxis y los tipos, y ahi basta con que copie lo mismo. */
void np_mover_bloques(uint32_t *destino, const uint32_t *origen, int32_t bloques)
{
    int32_t i, n = bloques * NP_LARGOS_BLOQUE;
    for (i = 0; i < n; i++) destino[i] = origen[i];
}

void np_mover_bloques_atras(uint32_t *destino, const uint32_t *origen,
                            int32_t bloques)
{
    int32_t i, n = bloques * NP_LARGOS_BLOQUE;
    for (i = 1; i <= n; i++) destino[-i] = origen[-i];
}
#endif

static void np_correr(uint8_t *pantalla, int32_t grupos)
{
    int32_t bytes = grupos * 8;
    int32_t largos = (bytes > 0 ? NP_PASO_FILA - bytes : NP_PASO_FILA + bytes) / 4;
    /* la division va una sola vez y no una por linea: el 68000 no divide */
    int32_t bloques = largos / NP_LARGOS_BLOQUE;
    int32_t resto = largos - bloques * NP_LARGOS_BLOQUE;
    int32_t linea, i;

    for (linea = NP_HUD_ALTO; linea < NP_ALTO; linea++) {
        uint8_t *fila = pantalla + (uint32_t)linea * NP_PASO_FILA;
        if (bytes > 0) {                          /* la vista va a la derecha */
            uint32_t *destino = (uint32_t *)(void *)fila;
            const uint32_t *origen = (const uint32_t *)(const void *)(fila + bytes);
            np_mover_bloques(destino, origen, bloques);
            destino += bloques * NP_LARGOS_BLOQUE;
            origen += bloques * NP_LARGOS_BLOQUE;
            for (i = 0; i < resto; i++) destino[i] = origen[i];
        } else {
            uint32_t *destino = (uint32_t *)(void *)(fila + NP_PASO_FILA);
            const uint32_t *origen =
                (const uint32_t *)(const void *)(fila + NP_PASO_FILA + bytes);
            np_mover_bloques_atras(destino, origen, bloques);
            destino -= bloques * NP_LARGOS_BLOQUE;
            origen -= bloques * NP_LARGOS_BLOQUE;
            for (i = 1; i <= resto; i++) destino[-i] = origen[-i];
        }
    }
}

/* --- borrar lo que dejaron los actores ----------------------------------- */

#define NP_TILES_TOTAL (NP_COLUMNAS * NP_FILAS)
static uint8_t np_ya_repintado[(NP_TILES_TOTAL + 7) / 8];

static void np_repintar_rastros(NpBuffer *b, const NpWorld *w)
{
    uint8_t i;
    uint16_t byte;
    if (!b->rastro_count) return;
    for (byte = 0; byte < sizeof(np_ya_repintado); byte++) np_ya_repintado[byte] = 0;

    for (i = 0; i < b->rastro_count; i++) {
        NpRastro *r = &b->rastros[i];
        /* el ultimo pixel del actor es x + ancho - 1: sin el -1 se repinta
           una columna (y una fila) de tiles que el actor no llega a tocar, y
           eso es media pantalla de trabajo de mas por frame */
        int32_t tx0 = r->x >> 4, tx1 = (r->x + r->ancho - 1) >> 4;
        int32_t ty0 = r->y >> 4, ty1 = (r->y + r->alto - 1) >> 4;
        int32_t tx, ty;
        for (tx = tx0; tx <= tx1; tx++) {
            /* los tiles de la columna, de una vez: pedirlos uno a uno cuesta
               una multiplicacion de 32 bits por tile, y el 68000 no la trae */
            uint16_t tiles[4];
            int32_t cuantos = ty1 - ty0 + 1;
            int32_t columna = tx - (b->vista_x >> 4);
            if (columna < 0 || columna >= NP_COLUMNAS) continue;
            if (cuantos > (int32_t)(sizeof(tiles) / sizeof(tiles[0])))
                cuantos = (int32_t)(sizeof(tiles) / sizeof(tiles[0]));
            np_tile_gfx_column(w->level, tx, ty0, (uint16_t)cuantos, tiles);
            for (ty = ty0; ty < ty0 + cuantos; ty++) {
                int32_t fila = ty - ((b->vista_y + NP_HUD_ALTO) >> 4);
                uint16_t indice;
                if (fila < 0 || fila >= NP_FILAS) continue;
                indice = (uint16_t)(fila * NP_COLUMNAS + columna);
                if (np_ya_repintado[indice >> 3] & (1 << (indice & 7))) continue;
                np_ya_repintado[indice >> 3] |= (uint8_t)(1 << (indice & 7));
                np_tile_en(b->pixeles, tiles[ty - ty0],
                           tx * NP_TILE - b->vista_x, ty * NP_TILE - b->vista_y);
            }
        }
    }
    b->rastro_count = 0;
}

static void np_apuntar_rastro(NpBuffer *b, int32_t x, int32_t y,
                              int16_t ancho, int16_t alto)
{
    if (b->rastro_count >= NP_MAX_RASTROS) return;
    b->rastros[b->rastro_count].x = (int16_t)x;
    b->rastros[b->rastro_count].y = (int16_t)y;
    b->rastros[b->rastro_count].ancho = ancho;
    b->rastros[b->rastro_count].alto = alto;
    b->rastro_count++;
}

static void np_dibujar_actor(NpBuffer *b, const NpActorDef *def,
                             int32_t mundo_x, int32_t mundo_y, uint8_t frame)
{
    uint16_t base = (uint16_t)(def->first_tile + frame * def->cols * def->rows);
    uint8_t c, r;
    int32_t x = mundo_x - b->vista_x;
    int32_t y = mundo_y - b->vista_y;
    if (x + def->cols * NP_TILE <= 0 || x >= NP_ANCHO) return;
    for (c = 0; c < def->cols; c++)
        for (r = 0; r < def->rows; r++)
            np_sprite_en(b->pixeles, (uint16_t)(base + c * def->rows + r),
                         x + c * NP_TILE, y + r * NP_TILE);
    np_apuntar_rastro(b, mundo_x, mundo_y, (int16_t)(def->cols * NP_TILE),
                      (int16_t)(def->rows * NP_TILE));
}

/* --- un frame ------------------------------------------------------------ */

/* Medir lo que cuesta un frame, sin instrumentos y sin emulador especial: se
 * pone el color 0 (que es tambien el del borde) de un color chillon mientras se
 * dibuja y se devuelve al del nivel al acabar. Como el haz no espera a nadie,
 * la franja de ese color que sale en pantalla mide **exactamente** lo que ha
 * tardado: una linea de barrido son 512 ciclos del 68000. Es como se median
 * estas cosas cuando la maquina era nueva.
 *
 * Se compila con -DNP_MEDIR=n, y `n` dice **que** trozo se mide:
 *
 *     1  el frame entero
 *     2  solo mover la pantalla al avanzar la vista (np_correr)
 *     3  solo repintar el fondo por donde pasaron los actores
 *     4  solo dibujar los actores
 *     5  solo simular (esta en main.c)
 *
 * Midiendo un trozo cada vez la franja cabe entera en la pantalla y la cuenta
 * sale exacta. En el juego de verdad nada de esto esta. */
#ifndef NP_MEDIR
#define NP_MEDIR 0
#endif
#define NP_COLOR_MEDIDA 0x0700                   /* rojo del ST */

#if NP_MEDIR
#define NP_MARCA(trozo, fondo) \
    do { if ((trozo) == NP_MEDIR) REG16(ST_PALETA) = (fondo); } while (0)
#else
#define NP_MARCA(trozo, fondo) do { } while (0)
#endif

void np_video_frame(const NpWorld *w)
{
    NpBuffer *b = &np_buffers[np_cual];
    NP_MARCA(1, NP_COLOR_MEDIDA);
    int32_t vista_x = w->cam_x & ~(int32_t)15;
    int32_t vista_y = w->cam_y + NP_RECORTE_Y;
    int32_t grupos = (vista_x - b->vista_x) >> 4;
    uint8_t i;

    if (w->level != b->nivel || vista_y != b->vista_y
        || grupos <= -NP_COLUMNAS || grupos >= NP_COLUMNAS) {
        b->nivel = w->level;
        b->vista_x = vista_x;
        b->vista_y = vista_y;
        np_redibujar_todo(b, w);
    } else if (grupos) {
        int32_t primera = b->vista_x >> 4;
        int32_t c;
        NP_MARCA(3, NP_COLOR_MEDIDA);
        np_repintar_rastros(b, w);
        NP_MARCA(3, w->level->background);
        NP_MARCA(2, NP_COLOR_MEDIDA);
        np_correr(b->pixeles, grupos);
        NP_MARCA(2, w->level->background);
        b->vista_x = vista_x;
        /* las columnas que entran por el lado hacia el que se mueve la vista */
        for (c = 0; c < (grupos > 0 ? grupos : -grupos); c++)
            np_columna(b, w, grupos > 0 ? primera + NP_COLUMNAS + c
                                        : primera - 1 - c);
    } else {
        NP_MARCA(3, NP_COLOR_MEDIDA);
        np_repintar_rastros(b, w);
        NP_MARCA(3, w->level->background);
    }

    NP_MARCA(4, NP_COLOR_MEDIDA);
    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
        const NpActorDef *def;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;
        def = np_entity_def(e);
        np_dibujar_actor(b, def, NP_F2I(e->x) - def->box_x, NP_F2I(e->y) - def->box_y,
                         np_actor_frame(def, e->anim, e->anim_frame));
    }
    if (np_player_visible(w)) {
        const NpActorDef *def = &np_player_def.actor;
        np_dibujar_actor(b, def, NP_F2I(w->player.x) - def->box_x,
                         NP_F2I(w->player.y) - def->box_y,
                         np_actor_frame(def, w->player.anim, w->player.anim_frame));
    }

    NP_MARCA(4, w->level->background);

#if NP_HUD_ENABLED
    np_hud_draw(w);
    if (np_hud_cambiado())
        for (i = 0; i < NP_PANTALLAS; i++) np_buffers[i].hud = 1;
    if (b->hud) {
        uint32_t *destino = (uint32_t *)(void *)b->pixeles;
        const uint32_t *origen = (const uint32_t *)(const void *)np_hud_bitmap;
        uint16_t j;
        for (j = 0; j < NP_HUD_BYTES / 4; j++) *destino++ = *origen++;
        b->hud = 0;
    }
#endif

    /* el color 0 es el fondo del nivel, y ademas el del borde de la pantalla */
    REG16(ST_PALETA) = w->level->background;
    np_ver(b->pixeles);
    np_cual = (uint8_t)((np_cual + 1) % NP_PANTALLAS);
}
