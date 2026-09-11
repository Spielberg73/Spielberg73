/* np_video.c - dibujado del juego en el Amiga.
 *
 * El mapa de bits es el doble de ancho que la pantalla (704 px). Segun avanza
 * la camara se va dibujando la columna de tiles que entra por la derecha; al
 * llegar al final del mapa se vuelve a empezar por la izquierda repintando lo
 * que se ve (eso cuesta un frame, y pasa cada 350 pixeles de scroll).
 *
 * Los actores se dibujan con el blitter recortados por su mascara. Antes de
 * dibujarlos se repinta el fondo donde estaban en el frame anterior, para no
 * dejar rastro.
 */

#include "np_amiga.h"

#define NP_MAX_RASTROS 48

typedef struct {
    int16_t x, y, ancho, alto;
} NpRastro;

static NpRastro np_rastros[NP_MAX_RASTROS];
static uint8_t np_rastro_count;
static int32_t np_base_tile;          /* primera columna de tiles dibujada */
/* Un nivel que cabe entero en el mapa de bits no necesita ventana: se pinta al
   entrar y ya no se toca. Es lo que hace posible un juego que se sube, donde el
   mapa de bits es estrecho y alto y no queda margen para ir corriendolo. */
static uint8_t np_mapa_fijo;
static const NpLevel *np_nivel_actual;
/* Cuantas puertas habia abiertas la ultima vez que se pinto el escenario. Al
   abrirse una, la casilla pasa a ser aire y hay que repintar: el escenario vive
   en la pantalla y no se entera solo. */
static uint8_t np_abiertos_pintados;

/* Lista del copper. Tiene dos partes: la de arriba pinta el marcador desde
   np_hud_bitmap y, al llegar a la linea NP_HUD_ALTO, engancha los bitplanes al
   mapa de bits del juego. Asi el marcador no se mueve con el scroll. */
#if NP_AGA
/* Nueve pares: BPLCON0, BPLCON2, BPLCON3, BPLCON4, FMODE, DIWSTRT, DIWSTOP,
   DDFSTRT y DDFSTOP. */
#define NP_COP_CABECERA  18
/* Los 256 colores del AGA no caben de golpe: los registros de color siguen
   siendo 32, y se eligen de ocho en ocho bancos con BPLCON3. Ademas cada
   color se escribe **dos veces**, porque el registro es de 12 bits y el color
   de 24: primero los cuatro bits altos de cada canal y luego, con el bit LOCT
   puesto, los cuatro bajos. Son 16 pasadas -ocho bancos por dos mitades- de un
   BPLCON3 y 32 colores cada una. */
#define NP_COP_PASADA    (33 * 2)                 /* palabras de una pasada */
/* y un BPLCON3 mas al final, para dejarlo como lo quiere la pantalla */
#define NP_COP_COLORES   (NP_COP_CABECERA + 16 * NP_COP_PASADA + 2)
#define NP_COP_COLOR0    (NP_COP_CABECERA + 3)    /* el fondo, mitad alta   */
#define NP_COP_COLOR0_BAJO (NP_COP_CABECERA + 8 * NP_COP_PASADA + 3)
#else
#define NP_COP_CABECERA  12                       /* 6 pares de registros   */
#define NP_COP_COLORES   (NP_COP_CABECERA + 64)   /* 32 colores             */
#define NP_COP_COLOR0    (NP_COP_CABECERA + 1)    /* el fondo, que cambia   */
#endif
#define NP_COP_HUD       NP_COP_COLORES           /* BPLCON1 y los modulos  */
#define NP_COP_HUD_PTR   (NP_COP_HUD + 6)
/* En doble plano la seccion de arriba lleva los punteros de los dos planos:
   los del marcador y los del parallax, que a partir de ahi sigue solo. */
#if NP_DOBLE_PLANO
#define NP_COP_FONDO_PTR (NP_COP_HUD_PTR + NP_PLANOS * 4)
#define NP_COP_ESPERA    (NP_COP_FONDO_PTR + NP_PLANOS * 4)
#else
#define NP_COP_ESPERA    (NP_COP_HUD_PTR + NP_PLANOS * 4)
#endif
#define NP_COP_JUEGO     (NP_COP_ESPERA + 2)
/* La seccion del juego escribe BPLCON1 y BPL1MOD, y **solo en un plano** el
   BPL2MOD: en doble plano ese registro es del plano de atras y ya se puso
   arriba, para todo el frame. O sea dos pares de palabras en doble plano y
   tres en uno solo, y los punteros empiezan detras.
   Dar seis por hecho costaba caro: np_punteros escribia dos palabras corridas
   sobre la lista y a partir de la linea del marcador el copper se ponia a
   escribir registros que no tocaban -colores, entre otros-. */
#if NP_DOBLE_PLANO
#define NP_COP_JUEGO_PTR (NP_COP_JUEGO + 4)
#else
#define NP_COP_JUEGO_PTR (NP_COP_JUEGO + 6)
#endif
#define NP_COP_FIN       (NP_COP_JUEGO_PTR + NP_PLANOS * 4)

#define NP_LINEA_ARRIBA 0x2C                      /* primera linea visible  */

#if NP_VISTA_CARRETERA
/* --- la carretera, linea a linea ----------------------------------------
 *
 * Comprobado en un A500 emulado con AROS: la calzada en perspectiva, la curva,
 * las franjas corriendo, la raya discontinua y los coches encima.
 *
 * Queda un detalle de borde: en una curva cerrada, los pixeles de la
 * izquierda que el scroll fino retrasa no se han leido -la DMA empieza en el
 * puntero- y ahi se ve lo ultimo de la linea de arriba, un escaloncito de
 * hasta quince pixeles pegado al borde. Se arregla leyendo una palabra de mas
 * por linea (DDFSTRT un paso antes y los modulos y los punteros dos bytes
 * menos), pero eso lo tocan los dos planos y todos los generos, asi que no se
 * hace de paso.
 *
 *
 * Conduciendo, la lista del copper lleva una seccion mas: una entrada por
 * cada linea de pantalla que tiene carretera. Cada entrada es una espera y
 * seis escrituras, y con eso queda dibujada la carretera entera:
 *
 *   BPL2MOD   cuanto se corre la imagen de una linea a la siguiente. El
 *             modulo se le suma al puntero al acabar la linea, asi que
 *             escribirlo aqui mueve **la linea de abajo**.
 *   BPLCON1   los pixeles sueltos que no caben en el modulo (0 a 15).
 *   y cuatro colores: hierba, arcen, calzada y raya. Aqui las franjas no
 *             vienen dibujadas -la imagen lleva un color por cosa- y lo que
 *             las hace correr es escribir un tono u otro en cada linea.
 *
 * Empieza en NP_HORIZONTE porque por encima no hay carretera: la imagen esta
 * en blanco y se ve el cielo, que es el color 0.
 */
#define NP_CARR_Y0      NP_HORIZONTE
#define NP_CARR_LINEAS  (NP_SCREEN_H - NP_CARR_Y0)
#define NP_CARR_PASO    14                        /* palabras de una entrada */
/* La primera linea de pantalla que cae por debajo de la 255 del monitor. El
   copper compara ocho bits, asi que a partir de ahi hay que esperar primero a
   que acabe la 255 o las esperas de abajo se cumplen solas y de golpe. */
#define NP_CARR_CORTE   (256 - NP_LINEA_ARRIBA)
#define NP_COP_CARRETERA NP_COP_FIN
#define NP_COP_LARGO    (NP_COP_CARRETERA + NP_CARR_LINEAS * NP_CARR_PASO + 4)
#else
#define NP_COP_LARGO     (NP_COP_FIN + 2)
#endif

/* Cuantos pixeles salta de una vez el puntero de bitplane. */
#if NP_AGA
#define NP_SALTO_SCROLL 32
#else
#define NP_SALTO_SCROLL 16
#endif

#if NP_AGA
/* --- lo que hay que decirle al AGA -------------------------------------
 *
 * FMODE: cuantos bits lee de golpe la DMA de bitplanes. Con 16 (lo de
 * siempre) en baja resolucion caben seis bitplanes contados; con 32 cada
 * lectura trae el doble de pixeles, sobran ranuras y entran los ocho. Sin
 * esto no hay 256 colores.
 *
 * Al leer de 32 en 32 la DMA empieza ocho clocks antes y hace la mitad de
 * lecturas: diez de 32 pixeles en vez de veinte de 16. Los 40 bytes por fila
 * y por plano son los mismos, asi que los modulos no cambian.
 *
 * BPLCON0 con ECSENA (bit 0) puesto: sin el, BPLCON3 y BPLCON4 no hacen nada
 * y la paleta se queda en los 32 colores de siempre. BPU3 (bit 4) es el bit
 * de arriba del numero de bitplanes: ocho planos son 1000 en binario.
 */
#define NP_FMODE_32     0x0001
#define NP_DDFSTRT_AGA  0x0030
#define NP_DDFSTOP_AGA  0x00C0
#if NP_DOBLE_PLANO
#define NP_BPLCON3_BASE 0x1000          /* PF2 empieza en el color 16 */
#define NP_BPLCON0_AGA  0x0611          /* 8 planos, doble plano, ECSENA */
#else
#define NP_BPLCON3_BASE 0x0C00          /* el valor compatible de siempre */
#define NP_BPLCON0_AGA  0x0211          /* 8 planos, un plano, ECSENA */
#endif

/* Las dos mitades de un color de 24 bits: el registro es de 12. */
static uint16_t np_color_alto(uint32_t c)
{
    return (uint16_t)((((c >> 20) & 0xF) << 8) | (((c >> 12) & 0xF) << 4)
                      | ((c >> 4) & 0xF));
}

static uint16_t np_color_bajo(uint32_t c)
{
    return (uint16_t)((((c >> 16) & 0xF) << 8) | (((c >> 8) & 0xF) << 4)
                      | (c & 0xF));
}
#endif /* NP_AGA */

/* El scroll fino, en el registro que lo lleva.
 *
 * En OCS son cuatro bits por plano: 0 a 15 pixeles, que es justo lo que sobra
 * de mover el puntero de dos en dos bytes. En AGA se lee de 32 en 32 bits, o
 * sea que el puntero salta de 32 en 32 pixeles y el resto -hasta 31- lo tiene
 * que poner este registro: los bits de arriba de cada plano son la parte que
 * no cabia en OCS.
 */
static uint16_t np_scroll_fino(uint16_t delante, uint16_t detras)
{
#if NP_AGA
    return (uint16_t)((delante & 15) | ((detras & 15) << 4)
                      | (((delante >> 4) & 3) << 8) | (((detras >> 4) & 3) << 10));
#else
    return (uint16_t)((delante & 15) | ((detras & 15) << 4));
#endif
}

static uint16_t np_copper[NP_COP_LARGO];

static void np_esperar_blitter(void)
{
    while (DMACONR & 0x4000) ;
}

/* --- copper y pantalla -------------------------------------------------- */

/* Escribe en la lista los punteros de bitplane a partir de `sitio`.
 *
 * En doble plano los seis bitplanes se reparten alternos: los impares (BPL1,
 * BPL3, BPL5) son el plano de delante y los pares (BPL2, BPL4, BPL6) el de
 * atras, asi que cada plano usa un registro si y otro no. */
#if NP_DOBLE_PLANO
#define NP_SALTO_REG 8
#else
#define NP_SALTO_REG 4
#endif

static void np_copper_punteros(uint16_t *sitio, uint32_t direccion, uint16_t paso,
                               uint16_t primer_reg)
{
    uint8_t i;
    for (i = 0; i < NP_PLANOS; i++) {
        uint32_t plano = direccion + i * paso;
        sitio[0] = (uint16_t)(primer_reg + i * NP_SALTO_REG);
        sitio[1] = (uint16_t)(plano >> 16);
        sitio[2] = (uint16_t)(primer_reg + 2 + i * NP_SALTO_REG);
        sitio[3] = (uint16_t)(plano & 0xFFFF);
        sitio += 4;
    }
}

#if NP_VISTA_CARRETERA
/* Arma la seccion de la carretera: las esperas y los numeros de registro, que
 * no cambian nunca. Lo que cambia cada frame son los seis valores de cada
 * entrada, y los escribe np_copper_carretera.
 *
 * La espera va en la columna 0x0C, o sea al principio de la linea y **antes**
 * de que empiece a leerse el bitplane (DDFSTRT esta en 0x38). Ahi todavia no
 * hay DMA de video comiendose las ranuras, cabe de sobra escribir seis
 * registros, y ademas es el unico sitio donde las tres cosas cuadran a la vez:
 * el color y el scroll fino valen para **esta** linea, y el modulo se suma al
 * acabar la linea, o sea que coloca **la de abajo**.
 */
static void np_montar_carretera(uint16_t *p)
{
    uint16_t y;
    for (y = NP_CARR_Y0; y < NP_SCREEN_H; y++) {
        uint16_t linea = (uint16_t)(NP_LINEA_ARRIBA + y);
        uint8_t i;
        if (y == NP_CARR_CORTE) {
            /* que se acabe la linea 255 del monitor, y a partir de aqui la
               cuenta del copper vuelve a empezar por cero */
            *p++ = 0xFFDF; *p++ = 0xFFFE;
        }
        *p++ = (uint16_t)(((linea & 0xFF) << 8) | 0x0D);
        *p++ = 0xFFFE;
        *p++ = 0x010A; *p++ = (uint16_t)(NP_PASO_FILA - 40);   /* BPL2MOD */
        *p++ = 0x0102; *p++ = 0x0000;                          /* BPLCON1 */
        for (i = 0; i < 4; i++) {
            *p++ = (uint16_t)(0x0180 + np_carretera_regs[i] * 2);
            *p++ = 0x0000;
        }
    }
}

/* Donde empieza la entrada de la linea `y`, contando el corte de la 255. */
static uint16_t *np_carretera_entrada(uint16_t y)
{
    uint16_t n = (uint16_t)(y - NP_CARR_Y0);
    uint16_t sitio = (uint16_t)(NP_COP_CARRETERA + n * NP_CARR_PASO);
    if (y >= NP_CARR_CORTE) sitio += 2;
    return np_copper + sitio;
}
#endif /* NP_VISTA_CARRETERA */

static void np_montar_copper(void)
{
    uint16_t *p = np_copper;
    uint8_t i;

#if NP_AGA
    *p++ = 0x0100; *p++ = NP_BPLCON0_AGA;                /* BPLCON0 */
    *p++ = 0x0104; *p++ = 0x0024;                        /* BPLCON2 */
    *p++ = 0x0106; *p++ = NP_BPLCON3_BASE;               /* BPLCON3 */
    *p++ = 0x010C; *p++ = 0x0011;                        /* BPLCON4 */
    *p++ = 0x01FC; *p++ = NP_FMODE_32;                   /* FMODE */
    *p++ = 0x008E; *p++ = 0x2C81;                        /* DIWSTRT */
    *p++ = 0x0090; *p++ = 0x0CC1;                        /* DIWSTOP: 320x224 */
    *p++ = 0x0092; *p++ = NP_DDFSTRT_AGA;                /* DDFSTRT */
    *p++ = 0x0094; *p++ = NP_DDFSTOP_AGA;                /* DDFSTOP */

    /* Los 256 colores, en dos vueltas de ocho bancos: primero los cuatro bits
       altos de cada canal y luego los cuatro bajos, con LOCT puesto. */
    {
        uint8_t mitad, banco;
        for (mitad = 0; mitad < 2; mitad++) {
            for (banco = 0; banco < 8; banco++) {
                *p++ = 0x0106;
                *p++ = (uint16_t)((banco << 13) | NP_BPLCON3_BASE
                                  | (mitad ? 0x0200 : 0));
                for (i = 0; i < 32; i++) {
                    uint32_t c = np_colores[banco * 32 + i];
                    *p++ = (uint16_t)(0x0180 + i * 2);
                    *p++ = mitad ? np_color_bajo(c) : np_color_alto(c);
                }
            }
        }
    }
    *p++ = 0x0106; *p++ = NP_BPLCON3_BASE;   /* banco 0 otra vez, para pintar */
#else
#if NP_DOBLE_PLANO
    /* seis bitplanes y el bit de doble plano: dos planos de tres cada uno */
    *p++ = 0x0100; *p++ = (6 << 12) | 0x0400 | 0x0200;   /* BPLCON0 */
#else
    *p++ = 0x0100; *p++ = (NP_PLANOS << 12) | 0x0200;   /* BPLCON0: 5 planos */
#endif
    *p++ = 0x0104; *p++ = 0x0024;                        /* BPLCON2 */
    *p++ = 0x008E; *p++ = 0x2C81;                        /* DIWSTRT */
    *p++ = 0x0090; *p++ = 0x0CC1;                        /* DIWSTOP: 320x224 */
    *p++ = 0x0092; *p++ = 0x0038;                        /* DDFSTRT */
    *p++ = 0x0094; *p++ = 0x00D0;                        /* DDFSTOP */

    for (i = 0; i < 32; i++) {
        *p++ = (uint16_t)(0x0180 + i * 2);
        *p++ = np_colores[i];
    }
#endif /* NP_AGA */

    /* franja del marcador */
    *p++ = 0x0102; *p++ = 0x0000;                        /* BPLCON1: sin scroll */
    *p++ = 0x0108; *p++ = (uint16_t)(NP_HUD_PASO - 40);  /* BPL1MOD: plano de delante */
#if NP_DOBLE_PLANO
    /* el plano de atras lleva su propio modulo y sigue solo todo el frame */
    *p++ = 0x010A; *p++ = (uint16_t)(NP_PASO_FILA - 40); /* BPL2MOD */
#else
    *p++ = 0x010A; *p++ = (uint16_t)(NP_HUD_PASO - 40);  /* BPL2MOD */
#endif
    np_copper_punteros(p, NP_DIR(np_hud_bitmap), NP_HUD_BYTES_FILA, 0x00E0);
    p += NP_PLANOS * 4;
#if NP_DOBLE_PLANO
    np_copper_punteros(p, NP_DIR(np_fondo_bitmap), NP_BYTES_FILA, 0x00E4);
    p += NP_PLANOS * 4;
#endif

    /* ...hasta aqui; de la linea NP_HUD_ALTO en adelante manda el juego */
    *p++ = (uint16_t)(((NP_LINEA_ARRIBA + NP_HUD_ALTO) << 8) | 0x01);
    *p++ = 0xFFFE;

    *p++ = 0x0102; *p++ = 0x0000;                        /* BPLCON1: scroll fino */
    /* entrelazado: al acabar una fila hay que saltar los demas bitplanes
       y la parte del mapa que no se ve */
    *p++ = 0x0108; *p++ = (uint16_t)(NP_PASO_FILA - 40);
#if !NP_DOBLE_PLANO
    /* en doble plano BPL2MOD es del plano de atras y ya se puso arriba */
    *p++ = 0x010A; *p++ = (uint16_t)(NP_PASO_FILA - 40);
#endif
    np_copper_punteros(p, NP_DIR(np_bitmap), NP_BYTES_FILA, 0x00E0);
    p += NP_PLANOS * 4;

#if NP_VISTA_CARRETERA
    np_montar_carretera(p);
    p += NP_CARR_LINEAS * NP_CARR_PASO + 2;
#endif
    *p++ = 0xFFFF; *p++ = 0xFFFE;                        /* fin de la lista */
}

/* Mete en la lista del copper donde empieza cada bitplane este frame. */
static void np_punteros(uint32_t direccion)
{
    np_copper_punteros(np_copper + NP_COP_JUEGO_PTR, direccion, NP_BYTES_FILA, 0x00E0);
}

void np_amiga_init(void)
{
    INTENA = 0x7FFF;                   /* nadie nos interrumpe */
    INTREQ = 0x7FFF;
    DMACON = 0x7FFF;                   /* toda la DMA fuera... */
    np_montar_copper();
    COP1LC = NP_DIR(np_copper);
    COPJMP1 = 0;
    DMACON = 0x8000 | 0x0080 | 0x0100 | 0x0200 | 0x0040;  /* copper, blitter y video */
    POTGO = 0xFF00;                    /* para poder leer el segundo boton */
    np_nivel_actual = 0;
    np_rastro_count = 0;
}

/* --- blitter ------------------------------------------------------------ */

/* Copia un tile (16x16, NP_PLANOS planos entrelazados) al mapa de bits `base`. */
static void np_blit_tile_en(uint32_t base, uint16_t tile, int32_t x, int32_t y)
{
    uint32_t destino = base + (uint32_t)y * NP_PASO_FILA + (x / 8);
    const uint8_t *origen = np_tile_data + (uint32_t)tile * (NP_TILE * NP_PLANOS * 2);
    np_esperar_blitter();
    BLTCON0 = 0x09F0;                  /* A -> D, sin desplazar */
    BLTCON1 = 0x0000;
    BLTAFWM = 0xFFFF;
    BLTALWM = 0xFFFF;
    BLTAMOD = 0;
    BLTDMOD = (uint16_t)(NP_BYTES_FILA - 2);
    BLTAPT = NP_DIR(origen);
    BLTDPT = destino;
    BLTSIZE = (uint16_t)(((NP_TILE * NP_PLANOS) << 6) | 1);
}

#if NP_VISTA_CARRETERA
/* Deja en blanco un cuadro de 16x16 del plano de delante. Conduciendo, borrar
   el rastro de un coche no es repintar el escenario -no hay- sino dejar el
   hueco transparente para que se vea la carretera, que va en el otro plano.
   Dos palabras de ancho porque un coche casi nunca cae en un multiplo de 16. */
static void np_borrar_cuadro(int32_t x, int32_t y)
{
    uint32_t destino = NP_DIR(np_bitmap) + (uint32_t)y * NP_PASO_FILA
                     + (uint32_t)((x / 16) * 2);
    np_esperar_blitter();
    BLTCON0 = 0x0100;                  /* solo D, y con minterm 0: D = 0 */
    BLTCON1 = 0x0000;
    BLTAFWM = 0xFFFF;
    BLTALWM = 0xFFFF;
    BLTDMOD = (uint16_t)(NP_BYTES_FILA - 4);
    BLTDPT = destino;
    BLTSIZE = (uint16_t)(((NP_TILE * NP_PLANOS) << 6) | 2);
}
#endif

static void np_blit_tile(uint16_t tile, int32_t x, int32_t y)
{
    np_blit_tile_en(NP_DIR(np_bitmap), tile, x, y);
}

/* Dibuja un actor recortado por su mascara (cookie cut). */
static void np_blit_bob(uint16_t tile, int32_t x, int32_t y)
{
    uint32_t destino = NP_DIR(np_bitmap) + (uint32_t)y * NP_PASO_FILA + ((x / 16) * 2);
    const uint8_t *origen = np_tile_data + (uint32_t)tile * (NP_TILE * NP_PLANOS * 2);
    const uint8_t *mascara = np_tile_mask + (uint32_t)tile * (NP_TILE * NP_PLANOS * 2);
    uint16_t desplazamiento = (uint16_t)((x & 15) << 12);
    np_esperar_blitter();
    /* D = (A y B) o (no A y C): la mascara elige entre el dibujo y el fondo */
    BLTCON0 = (uint16_t)(0x0FCA | desplazamiento);
    BLTCON1 = desplazamiento;
    BLTAFWM = 0xFFFF;
    BLTALWM = 0x0000;                  /* la palabra de mas, por el desplazamiento */
    /* A y B leen dos palabras por fila (el dibujo desplazado ocupa dos) pero
       solo avanzan una: por eso los dos modulos son -2. */
    BLTAMOD = (uint16_t)(-2);
    BLTBMOD = (uint16_t)(-2);
    BLTCMOD = (uint16_t)(NP_BYTES_FILA - 4);
    BLTDMOD = (uint16_t)(NP_BYTES_FILA - 4);
    BLTAPT = NP_DIR(mascara);
    BLTBPT = NP_DIR(origen);
    BLTCPT = destino;
    BLTDPT = destino;
    BLTSIZE = (uint16_t)(((NP_TILE * NP_PLANOS) << 6) | 2);
}

/* --- escenario ---------------------------------------------------------- */

/* Pedir la columna entera de una vez, y no tile a tile, ahorra una
   multiplicacion de 32 bits por tile: el 68000 no la trae y sale de
   np_aritmetica.c. Medido en el Amiga: 950 lineas de barrido para repintar la
   pantalla, 683 asi (un 28% menos). */
static void np_columna(const NpWorld *w, int32_t tile_x)
{
    uint16_t tiles[NP_MAPA_ALTO / NP_TILE];
    int32_t columna = tile_x - np_base_tile;
    int32_t fila;
    if (columna < 0 || columna >= NP_MAPA_ANCHO / NP_TILE) return;
    /* se pinta la columna entera, tambien lo que queda por debajo del nivel:
       si no, ahi se quedaria lo que hubiera dibujado antes */
    np_tile_gfx_column(w, tile_x, 0, NP_MAPA_ALTO / NP_TILE, tiles);
    for (fila = 0; fila < NP_MAPA_ALTO / NP_TILE; fila++)
        np_blit_tile(tiles[fila], columna * NP_TILE, fila * NP_TILE);
}

static void np_redibujar_todo(const NpWorld *w)
{
    int32_t i;
    np_mapa_fijo = (uint8_t)(w->level->width * NP_TILE <= NP_MAPA_ANCHO);
    np_base_tile = np_mapa_fijo ? 0 : (w->cam_x / NP_TILE) - 1;
    if (np_base_tile < 0) np_base_tile = 0;
    for (i = 0; i < NP_MAPA_ANCHO / NP_TILE; i++) np_columna(w, np_base_tile + i);
    np_rastro_count = 0;
}

#if NP_DOBLE_PLANO
/* --- el plano de atras (parallax) --------------------------------------
 *
 * Se pinta una vez al entrar en el nivel, repitiendo el dibujo de la capa a lo
 * ancho de todo el mapa de bits. Despues solo se mueven sus punteros, que es
 * gratis: el scroll de los dos planos es independiente por hardware, y esa es
 * justo la razon de existir de este modo.
 */
/* El plano de delante en blanco. Conduciendo ahi no hay escenario: solo los
   coches, que se pintan y se borran por su rastro. */
static void np_limpiar_juego(void)
{
    uint32_t *p = (uint32_t *)(void *)np_bitmap;
    uint32_t i;
    np_esperar_blitter();
    for (i = 0; i < NP_MAPA_ALTO * NP_PASO_FILA / 4; i++) *p++ = 0;
}

static void np_limpiar_fondo(void)
{
    uint32_t *p = (uint32_t *)(void *)np_fondo_bitmap;
    uint32_t i;
    np_esperar_blitter();
    for (i = 0; i < NP_MAPA_ALTO * NP_PASO_FILA / 4; i++) *p++ = 0;
}

static void np_pintar_fondo(const NpWorld *w)
{
    np_limpiar_fondo();
#if NP_LAYER_COUNT > 0
    if (w->level->layer_count && np_layers[w->level->layers[0]].cols) {
        const NpLayer *capa = &np_layers[w->level->layers[0]];
        int32_t columnas = NP_MAPA_ANCHO / NP_TILE;
        int32_t c, r;
        for (c = 0; c < columnas; c++) {
            int32_t fuente = c % capa->cols;
            for (r = 0; r < capa->rows; r++) {
                int32_t y = capa->offset_y + r * NP_TILE;
                if (y < 0 || y + NP_TILE > NP_MAPA_ALTO) continue;
                np_blit_tile_en(NP_DIR(np_fondo_bitmap),
                                capa->tiles[r * capa->cols + fuente],
                                c * NP_TILE, y);
            }
        }
    }
#else
    (void)w;
#endif
    np_esperar_blitter();
}

/* Mueve el plano de atras: grueso con los punteros, fino con BPLCON1. */
static uint16_t np_mover_fondo(const NpWorld *w)
{
    int32_t sx = 0, sy = 0, periodo = 0;
    int32_t maximo = NP_MAPA_ANCHO - NP_SCREEN_W;   /* lo que se puede desplazar */
    uint32_t direccion;
#if NP_LAYER_COUNT > 0
    if (w->level->layer_count) {
        const NpLayer *capa = &np_layers[w->level->layers[0]];
        sx = ((int32_t)w->cam_x * capa->speed_x) >> 8;
        sy = ((int32_t)w->cam_y * capa->speed_y) >> 8;
        periodo = capa->cols * NP_TILE;
    }
#endif
    /* el dibujo esta repetido a lo ancho del mapa de bits, asi que al llegar a
       su ancho se puede volver al principio sin que se note. Una capa mas ancha
       que el hueco que sobra no tiene donde volver: se para en el borde. */
    if (periodo >= NP_TILE && periodo <= maximo) {
        sx %= periodo;
        if (sx < 0) sx += periodo;
    } else {
        if (sx < 0) sx = 0;
        if (sx > maximo) sx = maximo;
    }
    if (sy < 0) sy = 0;
    if (sy > NP_MAPA_ALTO - NP_SCREEN_H - NP_HUD_ALTO)
        sy = NP_MAPA_ALTO - NP_SCREEN_H - NP_HUD_ALTO;
    direccion = NP_DIR(np_fondo_bitmap) + (uint32_t)sy * NP_PASO_FILA
              + (uint32_t)(sx / 16) * 2;
    np_copper_punteros(np_copper + NP_COP_FONDO_PTR, direccion, NP_BYTES_FILA, 0x00E4);
    return (uint16_t)(sx & 15);
}
#endif /* NP_DOBLE_PLANO */

#if NP_VISTA_CARRETERA
/* --- la carretera, cada frame -------------------------------------------
 *
 * La imagen de la carretera se pinta **una vez** al entrar en el nivel, y no
 * se vuelve a tocar un pixel. Lo unico que se hace por frame es rellenar la
 * seccion del copper: por cada linea de pantalla, cuanto se corre la imagen y
 * de que tono va cada cosa. Seis palabras por linea.
 */
#define NP_CARR_ANCHO   (NP_CARRETERA_EJE * 2)
#define NP_CARR_MARGEN  (NP_CARR_ANCHO - NP_SCREEN_W)   /* lo que se puede correr */

static int16_t np_carretera_centro[NP_SCREEN_H];

/* Pinta la carretera en el plano de atras. Una vez por nivel. */
static void np_pintar_carretera(void)
{
    const NpLayer *capa = &np_layers[np_carretera_capa];
    int32_t c, r;
    np_limpiar_fondo();
    for (c = 0; c < (int32_t)capa->cols; c++) {
        for (r = 0; r < (int32_t)capa->rows; r++) {
            int32_t y = r * NP_TILE;
            if (y + NP_TILE > NP_MAPA_ALTO) continue;
            np_blit_tile_en(NP_DIR(np_fondo_bitmap),
                            capa->tiles[r * capa->cols + c],
                            c * NP_TILE, y);
        }
    }
    np_esperar_blitter();
}

/* La columna de la imagen que tiene que salir en el pixel 0 de la pantalla.
 *
 * La imagen tiene el eje en su columna NP_CARRETERA_EJE, asi que para que el
 * eje salga en la columna `centro` hay que empezar a mirar en EJE - centro.
 * Y hay tope: la imagen mide 512 y la pantalla 320, o sea que se puede correr
 * 192 pixeles y ni uno mas. En una curva muy cerrada el eje se sale por ahi y
 * la carretera se queda pegada al borde en vez de irse: es lo que hay con una
 * imagen de ancho fijo, y a esas alturas la calzada ya casi no se ve. */
static int32_t np_carretera_columna(uint16_t y, uint16_t horizonte)
{
    int32_t off;
    if (y < horizonte) return 0;
    off = NP_CARRETERA_EJE - np_carretera_centro[y];
    /* Y el tope no es 0 ni el margen entero, sino 16 pixeles por dentro. El
       scroll fino **retrasa** el plano: pegado al borde, esos pixeles de
       retraso no tienen de donde salir y en pantalla aparece un escaloncito
       con lo que hubiera antes. Dejando una casilla de margen a cada lado
       siempre hay imagen de donde tirar. */
    if (off < NP_TILE) off = NP_TILE;
    if (off > NP_CARR_MARGEN - NP_TILE) off = NP_CARR_MARGEN - NP_TILE;
    return off;
}

static void np_copper_carretera(const NpWorld *w)
{
    uint16_t horizonte = np_carretera(w, np_carretera_centro);
    uint8_t fase = np_carretera_fase(w);
    uint16_t y;
    int32_t grueso, grueso_sig;

    /* El puntero del plano de atras se coloca ya con el desplazamiento de la
       primera linea con carretera: de ahi para abajo lo llevan los modulos. */
    grueso = (np_carretera_columna(NP_CARR_Y0, horizonte) + 15) & ~15;
    np_copper_punteros(np_copper + NP_COP_FONDO_PTR,
                       NP_DIR(np_fondo_bitmap) + (uint32_t)(grueso / 8),
                       NP_BYTES_FILA, 0x00E4);

    for (y = NP_CARR_Y0; y < NP_SCREEN_H; y++) {
        uint16_t *e = np_carretera_entrada(y);
        int32_t off = np_carretera_columna(y, horizonte);
        uint8_t banda = (uint8_t)((np_carretera_banda[y] + fase)
                                  & (NP_CARRETERA_FRANJAS - 1));
        uint8_t tono = (uint8_t)(banda >> 1);
        if (y + 1 < NP_SCREEN_H)
            grueso_sig = (np_carretera_columna((uint16_t)(y + 1), horizonte) + 15) & ~15;
        else
            grueso_sig = grueso;
        /* el modulo se suma al acabar la linea: lo que dice es cuanto se corre
           **la de abajo** respecto a esta */
        e[3] = (uint16_t)(NP_PASO_FILA - 40 + (grueso_sig - grueso) / 8);
        /* y lo que no cabe en el modulo -de 0 a 15 pixeles- lo pone el scroll
           fino, que retrasa el plano: por eso el grueso se redondea hacia
           arriba y el fino es lo que sobra */
        e[5] = np_scroll_fino(0, (uint16_t)(grueso - off));
        e[7] = np_carretera_tonos[0][tono];          /* hierba */
        e[9] = np_carretera_tonos[1][tono];          /* arcen */
        e[11] = np_carretera_tonos[2][tono];         /* calzada */
        /* La raya del medio es discontinua: se ve en una franja de cada dos.
           Donde no toca se pinta del color de la calzada y desaparece. */
        e[13] = (banda & 1) ? np_carretera_tonos[3][0]
                            : np_carretera_tonos[2][tono];
        grueso = grueso_sig;
    }
}
#endif /* NP_VISTA_CARRETERA */

/* --- un frame ----------------------------------------------------------- */

/* Repintar el fondo es lo mas caro del frame, y los actores suelen ir juntos
   (las monedas van de tres en tres): sin esto, un mismo tile se repinta una vez
   por cada actor que lo toca. Un bit por tile del mapa de bits basta. */
#define NP_TILES_X (NP_MAPA_ANCHO / NP_TILE)
#define NP_TILES_Y (NP_MAPA_ALTO / NP_TILE)
static uint8_t np_ya_repintado[(NP_TILES_X * NP_TILES_Y + 7) / 8];

/* Los cubos de la sala isometrica viven **dentro** del mapa de bits: se pintan
 * una vez al entrar en la habitacion y ahi se quedan, como el suelo. No es un
 * ahorro pequeno: un cubo de 32x64 son ocho trozos que borrar y ocho que
 * volver a pintar en cada frame, y con los cinco o seis de una habitacion el
 * Amiga y el ST pierden el frame y se van a la mitad de velocidad (medido: la
 * melodia pasa de 16 notas de 16 a 8).
 *
 * Lo unico que hay que rehacer es lo que pisa un actor que si se mueve: al
 * borrar su rastro se repinta el suelo y ahi se lleva por delante el trozo de
 * cubo que hubiera. Por eso se apunta que se ha repintado y se vuelven a poner
 * **solo** los cubos que tocan esos trozos, en su sitio de la fila de
 * profundidad, que es lo que sigue dejando pasar al jugador por detras. */
#if NP_VISTA_ISO
static NpRastro np_borrados[NP_MAX_RASTROS];
static uint8_t np_borrados_n;

/* Toca ese cuadro alguno de los trozos de suelo que se acaban de repintar? */
static int np_pisa_lo_borrado(int32_t x, int32_t y, int32_t ancho, int32_t alto)
{
    uint8_t i;
    for (i = 0; i < np_borrados_n; i++) {
        const NpRastro *r = &np_borrados[i];
        if (x >= r->x + r->ancho || x + ancho <= r->x) continue;
        if (y >= r->y + r->alto || y + alto <= r->y) continue;
        return 1;
    }
    return 0;
}
#endif

static void np_repintar_rastros(const NpWorld *w)
{
    uint8_t i;
    uint16_t b;
#if NP_VISTA_ISO
    np_borrados_n = 0;
#endif
    if (!np_rastro_count) return;
#if NP_VISTA_ISO
    for (i = 0; i < np_rastro_count; i++) np_borrados[i] = np_rastros[i];
    np_borrados_n = np_rastro_count;
#endif
    for (b = 0; b < sizeof(np_ya_repintado); b++) np_ya_repintado[b] = 0;

    for (i = 0; i < np_rastro_count; i++) {
        NpRastro *r = &np_rastros[i];
        /* el ultimo pixel del actor es x + ancho - 1: sin el -1 se repinta una
           columna (y una fila) de tiles que el actor no llega a tocar */
        int32_t tx0 = r->x / NP_TILE, tx1 = (r->x + r->ancho - 1) / NP_TILE;
        int32_t ty0 = r->y / NP_TILE, ty1 = (r->y + r->alto - 1) / NP_TILE;
        int32_t tx, ty;
        for (tx = tx0; tx <= tx1; tx++) {
            int32_t columna = tx - np_base_tile;
            if (columna < 0 || columna >= NP_TILES_X) continue;
            for (ty = ty0; ty <= ty1; ty++) {
                uint16_t indice;
                if (ty < 0 || ty >= NP_TILES_Y) continue;
                indice = (uint16_t)(ty * NP_TILES_X + columna);
                if (np_ya_repintado[indice >> 3] & (1 << (indice & 7))) continue;
                np_ya_repintado[indice >> 3] |= (uint8_t)(1 << (indice & 7));
                np_blit_tile(np_tile_gfx_at(w, tx, ty),
                             columna * NP_TILE, ty * NP_TILE);
            }
        }
    }
    np_rastro_count = 0;
}

#if NP_VISTA_CARRETERA
/* Borra por donde pasaron los coches el frame anterior. Conduciendo no hay
   escenario que repintar: se deja el hueco transparente y por ahi se ve la
   carretera, que va en el plano de atras. */
static void np_borrar_rastros(void)
{
    uint8_t n;
    for (n = 0; n < np_rastro_count; n++) {
        const NpRastro *r = &np_rastros[n];
        int32_t x, y;
        for (y = r->y; y < r->y + r->alto; y += NP_TILE)
            for (x = r->x; x < r->x + r->ancho; x += NP_TILE)
                np_borrar_cuadro(x, y);
    }
    np_rastro_count = 0;
}
#endif

static void np_apuntar_rastro(int32_t x, int32_t y, int16_t ancho, int16_t alto)
{
    if (np_rastro_count >= NP_MAX_RASTROS) return;
    np_rastros[np_rastro_count].x = (int16_t)x;
    np_rastros[np_rastro_count].y = (int16_t)y;
    np_rastros[np_rastro_count].ancho = ancho;
    np_rastros[np_rastro_count].alto = alto;
    np_rastro_count++;
}

/* `quieto` dice de que clase es este dibujo:
 *
 *   0  un actor que se mueve: se pinta entero y se apunta su rastro para
 *      borrarlo el frame que viene;
 *   1  un cubo de una sala isometrica recien montada: se pinta entero y ahi se
 *      queda, como el suelo, sin rastro que borrar;
 *   2  un cubo que ya estaba pintado y al que un actor le ha repintado el
 *      suelo por encima: solo hacen falta **los trozos que se han borrado**.
 *      Un muro son ocho trozos y el rastro de un bicho toca uno o dos.
 */
static void np_pintar_bloque(uint16_t first_tile, uint8_t cols, uint8_t rows,
                             int32_t mundo_x, int32_t mundo_y, uint8_t frame,
                             uint8_t quieto)
{
    uint16_t base = (uint16_t)(first_tile + frame * cols * rows);
    uint8_t c, r;
    int32_t x = mundo_x - np_base_tile * NP_TILE;
    if (x < 0 || x + cols * NP_TILE >= NP_MAPA_ANCHO) return;
    for (c = 0; c < cols; c++) {
        for (r = 0; r < rows; r++) {
            int32_t py = mundo_y + r * NP_TILE;
            if (py < 0 || py + NP_TILE > NP_MAPA_ALTO) continue;
#if NP_VISTA_ISO
            if (quieto == 2
                && !np_pisa_lo_borrado(mundo_x + c * NP_TILE,
                                       mundo_y + r * NP_TILE,
                                       NP_TILE, NP_TILE)) continue;
#endif
            np_blit_bob((uint16_t)(base + c * rows + r), x + c * NP_TILE, py);
        }
    }
    if (!quieto)
        np_apuntar_rastro(mundo_x, mundo_y, (int16_t)(cols * NP_TILE),
                          (int16_t)(rows * NP_TILE));
}

static void np_pintar_actor(const NpActorDef *def, int32_t mundo_x, int32_t mundo_y,
                            uint8_t frame, uint8_t flip, uint8_t quieto)
{
    (void)flip;                         /* el espejo se hace con dibujos aparte */
    np_pintar_bloque(def->first_tile, def->cols, def->rows, mundo_x, mundo_y,
                     frame, quieto);
}

void np_video_frame(const NpWorld *w)
{
    const uint8_t *orden;
    uint8_t cuantas;
    static int32_t ultima_columna = -9999;
    int32_t columna = w->cam_x / NP_TILE;
    uint32_t direccion;
    uint8_t i;
    /* La habitacion isometrica que hay pintada ahora mismo en el mapa de bits.
       Al cambiar de sala hay que repintarla entera con sus cubos: todas las
       salas se dibujan en el mismo cuadro y lo unico que cambia son ellos. */
    static uint16_t np_sala_pintada_x = 0xffff, np_sala_pintada_y = 0xffff;
    uint8_t sala_nueva = 0;
    (void)sala_nueva;                 /* solo lo mira la vista isometrica */

#if NP_VISTA_CARRETERA
    /* Conduciendo, el escenario **no se dibuja**: el mapa es el trazado de la
       carretera, no lo que se ve. Lo que hay en el plano de atras es la
       carretera en perspectiva, y en cada frame solo se rellena la seccion del
       copper que la desliza y le pone los colores linea a linea. El plano de
       delante se queda para los coches, que asi no salen a escalones. */
    if (w->level != np_nivel_actual) {
        np_nivel_actual = w->level;
        np_copper[NP_COP_COLOR0] = w->level->background;   /* el cielo */
        np_pintar_carretera();
        np_limpiar_juego();
        np_base_tile = 0;
        np_rastro_count = 0;
    } else {
        np_borrar_rastros();
    }
    np_copper_carretera(w);
    (void)ultima_columna;
    (void)columna;
    (void)np_sala_pintada_x;
    (void)np_sala_pintada_y;
    (void)direccion;
#else
    if (w->level != np_nivel_actual || w->abiertos_n != np_abiertos_pintados
        || (np_vista_iso && (w->sala_x != np_sala_pintada_x
                             || w->sala_y != np_sala_pintada_y))) {
        np_nivel_actual = w->level;
        np_abiertos_pintados = w->abiertos_n;
        /* el color 0 es el fondo de la pantalla, y cada nivel trae el suyo */
#if NP_AGA
        np_copper[NP_COP_COLOR0] = np_color_alto(w->level->background);
        np_copper[NP_COP_COLOR0_BAJO] = np_color_bajo(w->level->background);
#else
        np_copper[NP_COP_COLOR0] = w->level->background;
#endif
#if NP_DOBLE_PLANO
        np_pintar_fondo(w);          /* el parallax se pinta una vez por nivel */
#endif
        np_redibujar_todo(w);
        ultima_columna = columna;
        np_sala_pintada_x = w->sala_x;
        np_sala_pintada_y = w->sala_y;
        sala_nueva = 1;
#if NP_VISTA_ISO
        np_borrados_n = 0;
#endif
    } else {
        np_repintar_rastros(w);
        if (!np_mapa_fijo) {
            while (ultima_columna < columna) {
                ultima_columna++;
                np_columna(w, ultima_columna + NP_SCREEN_W / NP_TILE);
            }
            while (ultima_columna > columna) {
                ultima_columna--;
                np_columna(w, ultima_columna);
            }
            /* si la camara se acerca al final del mapa de bits, se vuelve a
               empezar */
            if (w->cam_x - np_base_tile * NP_TILE >
                NP_MAPA_ANCHO - NP_SCREEN_W - NP_TILE * 2) {
                np_redibujar_todo(w);
                ultima_columna = columna;
                /* se ha repintado el mapa de bits entero: los cubos de la sala
                   se han ido con el y hay que volver a ponerlos */
                sala_nueva = 1;
#if NP_VISTA_ISO
                np_borrados_n = 0;
#endif
            }
        }
    }
#endif /* NP_VISTA_CARRETERA */

    /* De mas lejos a mas cerca: en la vista de cinta los actores se pisan a
       cada rato y hay que pintarlos por la linea del suelo. En las demas
       vistas np_orden_dibujo devuelve el orden de la lista tal cual. */
    /* En la isometrica la fila lleva los cubos de la sala y ademas a los
       jugadores -ahi hay un detras de verdad-, y donde cae cada uno lo decide
       la proyeccion: por eso se pide todo a np_dibujo y el bucle es uno solo.
       En las demas vistas se dibuja como siempre, y no por gusto: preguntarle
       a np_dibujo por cada actor cuesta lo justo para que la Mega Drive pierda
       el vblank y el juego entero se vaya a la mitad de velocidad. Medido: la
       melodia pasa de 16 notas de 16 a 4. */
    orden = np_orden_dibujo(w, &cuantas);
#if NP_VISTA_CARRETERA
    /* Los actores van en **coordenadas de pantalla**: el plano de delante no
       se mueve, asi que el mapa de bits es la pantalla y no hay camara que
       restar despues. La fila 0 del mapa de bits sale en la linea NP_HUD_ALTO,
       que es donde acaba el marcador. */
    /* Lo que hay en la calzada va **donde dice la proyeccion y del tamano que
       le toca**, no donde diga el mapa: en esta vista el mapa es el trazado.
       Se dibuja de mas lejos a mas cerca -np_orden_dibujo ya da ese orden en
       la lista, pero aqui el orden que vale es el de la escala- para que lo de
       delante tape a lo de detras. */
    for (i = 0; i < cuantas; i++) {
        const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
        const NpActorDef *def;
        const NpCarreteraTam *tam;
        int32_t sx, sy, escala;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;
        def = np_entity_def(e);
        if (!np_carretera_donde(w, e->x, e->y, &sx, &sy, &escala)) continue;
        tam = np_carretera_dibujo(def, escala);
        if (!tam) continue;
        /* El dibujo viene centrado y apoyado abajo en su bloque de tiles. */
        sx -= tam->cols * NP_TILE / 2;
        sy -= tam->rows * NP_TILE + NP_HUD_ALTO;
        if (sx < 0 || sx + tam->cols * NP_TILE >= NP_MAPA_ANCHO) continue;
        if (sy < 0 || sy + tam->rows * NP_TILE > NP_MAPA_ALTO) continue;
        np_pintar_bloque(tam->first_tile, tam->cols, tam->rows, sx, sy,
                         np_actor_frame(def, e->anim, e->anim_frame), 0);
    }
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        int32_t cx, cy;
        if (!np_player_visible(w, i)) continue;
        /* El coche va en un sitio fijo abajo: la camara le sigue, asi que en
           la pantalla no se mueve. Lo dice el motor para que caiga en el mismo
           pixel en las ocho maquinas. Y sin espejo: el coche se ve de culo, y
           espejarlo cambiaria de asiento a los dos que van dentro. */
        np_carretera_coche(w, i, &cx, &cy);
        cy -= NP_HUD_ALTO;
        if (cx < 0 || cx + def->cols * NP_TILE >= NP_MAPA_ANCHO) continue;
        if (cy < 0 || cy + def->rows * NP_TILE > NP_MAPA_ALTO) continue;
        np_pintar_actor(def, cx, cy,
                        np_actor_frame(def, p->anim, p->anim_frame), 0, 0);
    }
#elif NP_VISTA_ISO
    for (i = 0; i < cuantas; i++) {
        const NpActorDef *def;
        int32_t sx, sy;
        uint8_t frame, flip, cubo;
        uint8_t puesto = NP_DIBUJO(orden, i);
        def = np_dibujo(w, puesto, &sx, &sy, &frame, &flip);
        if (!def) continue;
        if (sx < w->cam_x - 32 || sx > w->cam_x + NP_SCREEN_W) continue;
        /* Un cubo ya esta pintado en el mapa de bits desde que se monto la
           sala: solo hay que volver a ponerlo si un actor que se mueve le ha
           repintado el suelo por encima. */
        cubo = (uint8_t)(puesto < NP_MAX_ENTITIES
                         && puesto >= (uint8_t)(NP_MAX_ENTITIES - w->bloques_n));
        if (cubo && !sala_nueva
            && !np_pisa_lo_borrado(sx, sy, def->cols * NP_TILE, def->rows * NP_TILE))
            continue;
        np_pintar_actor(def, sx, sy, frame, flip,
                        (uint8_t)(cubo ? (sala_nueva ? 1 : 2) : 0));
    }
#else
    for (i = 0; i < cuantas; i++) {
        const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
        const NpActorDef *def;
        int32_t sx, sy;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;
        def = np_entity_def(e);
        sx = NP_F2I(e->x) - def->box_x;
        sy = NP_F2I(e->y) - def->box_y;
        if (sx < w->cam_x - 32 || sx > w->cam_x + NP_SCREEN_W) continue;
        np_pintar_actor(def, sx, sy, np_actor_frame(def, e->anim, e->anim_frame),
                        (uint8_t)!e->facing, 0);
    }
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        if (!np_player_visible(w, i)) continue;
        np_pintar_actor(def, NP_F2I(p->x) - def->box_x,
                        NP_F2I(p->y) - def->box_y,
                        np_actor_frame(def, p->anim, p->anim_frame),
                        (uint8_t)!p->facing, 0);
    }
#endif

#if NP_VISTA_CARRETERA
    /* El plano de delante no se mueve: los coches ya se han pintado en el
       pixel de pantalla que les tocaba. Los punteros van al principio y el
       scroll fino, a cero. El de atras -la carretera- lo lleva el copper linea
       a linea, asi que aqui no hay nada mas que hacer. */
    np_punteros(NP_DIR(np_bitmap));
    np_copper[NP_COP_HUD + 1] = 0;
    np_copper[NP_COP_JUEGO + 1] = 0;
#else
    /* Scroll: los punteros van al pixel de arriba a la izquierda de lo que se
       ve, y lo que no llega a un salto entero lo pone el scroll fino.
       El salto es de 16 pixeles (dos bytes) en OCS y de 32 (cuatro) en AGA,
       porque leyendo de 32 en 32 bits la DMA no mira los bits de abajo del
       puntero: moverlo de dos en dos bytes no haria nada la mitad de las
       veces, y el scroll se veria a tirones. */
    direccion = NP_DIR(np_bitmap)
        + (uint32_t)(w->cam_y + NP_HUD_ALTO) * NP_PASO_FILA
        + (uint32_t)((w->cam_x - np_base_tile * NP_TILE) / NP_SALTO_SCROLL)
          * (NP_SALTO_SCROLL / 8);
    np_punteros(direccion);
    {
        uint16_t suelto = (uint16_t)(w->cam_x & (NP_SALTO_SCROLL - 1));
#if NP_DOBLE_PLANO
        uint16_t fino = np_mover_fondo(w);
        np_copper[NP_COP_HUD + 1] = np_scroll_fino(0, fino);
        np_copper[NP_COP_JUEGO + 1] = np_scroll_fino(suelto, fino);
#else
        np_copper[NP_COP_JUEGO + 1] = np_scroll_fino(suelto, suelto);
#endif
    }
#endif /* NP_VISTA_CARRETERA */

#if NP_HUD_ENABLED
    np_hud_draw(w);
#endif
}

/* --- sincronizacion y mando --------------------------------------------- */

/* En que linea va el haz. El numero no cabe en un byte: los bits que faltan
   estan en VPOSR. */
static uint16_t np_linea(void)
{
    uint16_t alto = (uint16_t)(VPOSR & 0x0007);
    return (uint16_t)((alto << 8) | (VHPOSR >> 8));
}

#define NP_LINEA_RETRAZO 0x0110        /* justo despues de la ultima visible */

void np_wait_vblank(void)
{
    while (np_linea() >= NP_LINEA_RETRAZO) ;   /* salir del retrazo de ahora */
    while (np_linea() < NP_LINEA_RETRAZO) ;    /* y esperar al siguiente */
}

/* Los dos puertos se leen igual, cambiando de sitio: el de la derecha (donde
 * va el joystick de siempre) tiene los datos en JOY1DAT, el disparo en el bit 7
 * de CIAA_PRA y el segundo boton en el bit 14 de POTGOR; el de la izquierda (el
 * del raton, que es donde se enchufa el segundo mando) los tiene en JOY0DAT, el
 * bit 6 y el bit 10.
 *
 * El **segundo boton es el de accion** (pegar, disparar y, con arriba, el arma
 * secundaria). Antes valia de start y el juego se quedaba sin boton de accion:
 * en el Amiga no habia forma de atacar. El start se lo queda ahora el disparo,
 * que ademas salta, igual que en el X68000 y en el Atari ST: asi un joystick de
 * un solo boton sigue sirviendo para empezar y para jugar, y el de dos gana el
 * ataque. Start solo se mira en el titulo y al acabar la partida, asi que que
 * el disparo lo lleve puesto no molesta mientras se juega. */
static uint16_t np_input_de(uint16_t joy, uint8_t disparo, uint16_t boton2)
{
    uint16_t salida = 0;
    /* el joystick es de cuadratura: arriba y abajo salen de un xor */
    uint8_t abajo = (uint8_t)((joy >> 1) & 1) ^ (uint8_t)(joy & 1);
    uint8_t arriba = (uint8_t)((joy >> 9) & 1) ^ (uint8_t)((joy >> 8) & 1);

    if (joy & 0x0002) salida |= NP_IN_RIGHT;
    if (joy & 0x0200) salida |= NP_IN_LEFT;
    if (abajo) salida |= NP_IN_DOWN;
    if (arriba) salida |= NP_IN_UP;
    if (!(CIAA_PRA & disparo)) salida |= NP_IN_JUMP | NP_IN_START;
    if (!(POTGOR & boton2)) salida |= NP_IN_ACTION;
    return salida;
}

uint16_t np_input_read(void)
{
    uint16_t salida = np_input_de(JOY1DAT, 0x80, 0x4000);
    /* A un jugador, el boton del raton tambien vale de start: es lo mas a mano
     * que hay si el joystick esta en el otro puerto. A dos no, porque ese boton
     * es el salto del segundo jugador. */
    if (np_player_count < 2 && !(CIAA_PRA & 0x40)) salida |= NP_IN_START;
    return salida;
}

uint16_t np_input_read2(void)
{
    return np_input_de(JOY0DAT, 0x40, 0x0400);
}
