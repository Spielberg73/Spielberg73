/* np_video.c - video del Sharp X68000: capa de fondo y sprites del chip CYNTHIA.
 *
 * Es la maquina mas comoda de las seis para este motor, y por una razon: los
 * tiles del PCG son de **16x16**, exactamente el tamano de tile de NeoPlat.
 * En la Mega Drive hay que partir cada tile en cuatro de 8x8 y en la Neo Geo el
 * escenario se dibuja con columnas de sprites; aqui una casilla del nivel es
 * una casilla de la tabla de nombres y se acabo.
 *
 * El reparto:
 *
 *   capa BG  el escenario, con scroll por hardware
 *   sprites  los actores (jugadores, enemigos, objetos, disparos)
 *   texto    el marcador (np_hud.c), que asi no gasta ni un patron de PCG
 *
 * El parallax no va en el chip de sprites: tiene dos capas, pero encendiendo
 * las dos nunca se ven los dos dibujos a la vez (probado bit a bit en el
 * emulador, ver np_x68k.h), asi que su capa se la queda el escenario. Va en la
 * **pantalla grafica**, que es otro chip: se ve a la vez, por detras, y tiene
 * su propio scroll por hardware.
 *
 * La tabla de nombres es de 64x64 casillas y se repite sola, asi que un nivel
 * mas largo que 64 casillas se dibuja columna a columna segun avanza la camara,
 * igual que en la Mega Drive.
 */

#include "np_x68k.h"
#include "gamedata.h"

/* --- utilidades --------------------------------------------------------- */

/* Una casilla de la tabla de nombres tiene el mismo formato que el atributo de
   un sprite: volteos arriba, bloque de paleta y numero de patron. */
#define NP_CASILLA(patron, paleta) \
    ((uint16_t)(((uint16_t)(paleta) << 8) | ((patron) & 0xFF)))
#define NP_VOLTEO_H 0x4000

/* --- arranque ----------------------------------------------------------- */

static void np_subir_paletas(void)
{
    uint16_t bloque, color;
    for (bloque = 0; bloque < NP_PALETTE_COUNT && bloque < 16; bloque++)
        for (color = 0; color < 16; color++)
            NP_PALETA_PCG[bloque * 16 + color] = np_palettes[bloque][color];
}

static void np_subir_patrones(void)
{
    uint32_t i;
    for (i = 0; i < NP_PCG_BYTES; i++)
        NP_PCG[i] = np_pcg_data[i];
}

static void np_limpiar_sprites(void)
{
    uint16_t i;
    for (i = 0; i < NP_SPRITES; i++)
        NP_SPRITE_REGS[i * 4 + 3] = 0;      /* prioridad 0 = apagado */
}

static void np_limpiar_capa(void)
{
    uint16_t i;
    for (i = 0; i < NP_BG_COLUMNAS * NP_BG_FILAS; i++)
        NP_BG_MAPA[i] = 0;
}

void np_video_init(void)
{
    /* Primero la ROM: _CRTMOD deja la pantalla puesta. Es la unica forma de
       heredar el temporizado bueno de los registros del CRTC, que son de solo
       escritura y no se pueden releer.

       Y **solo** _CRTMOD. Aqui tambien se llamaba a _SP_INIT y _SP_ON para
       preparar el chip de sprites, y eso era una bomba de relojeria: segun con
       que Human68k se lanzara el juego, _SP_INIT **no vuelve**. El juego se
       quedaba colgado ahi para siempre -pantalla negra en el modo de la ROM,
       sin llegar nunca a escribir su temporizado- y desde fuera parecia que no
       arrancaba. Se encontro pintando en la pantalla grafica una marca por
       cada paso del arranque y contando desde el emulador cuantas lineas
       salian: la marca de antes de _SP_INIT, y ninguna de las de despues.

       No hacen falta: el chip de sprites lo enciende el propio motor con el
       bit 9 de BG_CTRL, ahi abajo, y el reparto de patrones y paletas lo hace
       np_subir_patrones/np_subir_paletas. Quitarlas no cambia lo que se ve
       -comprobado en el emulador, con los sprites del jugador y las monedas en
       su sitio- y el juego arranca con cualquier disco de sistema. */
    np_iocs(NP_IOCS_CRTMOD, NP_MODO_ROM, 0);

    /* Y encima, el temporizado nuestro: 320x224, que es la pantalla del kit.
       El chip de sprites lo aguanta -esta comprobado en el emulador- asi que
       no hay que recortar la vista como en el Atari ST. */
    *NP_CRTC_R00 = 0x0037;
    *NP_CRTC_R01 = 0x0005;
    *NP_CRTC_R02 = 0x0007;
    *NP_CRTC_R03 = (uint16_t)(0x0007 + NP_ANCHO / 8);
    /* 266 lineas en total: con 259 el frame salia a 61,5 Hz y el juego corria
       un 2,4% mas rapido que en las otras maquinas. Con esto se queda en 60,0
       (lo dice el propio emulador al pedirle el temporizado). */
    *NP_CRTC_R04 = 0x0109;
    *NP_CRTC_R05 = 0x0002;
    *NP_CRTC_R06 = 0x0010;
    *NP_CRTC_R07 = (uint16_t)(0x0010 + NP_ALTO);
    *NP_CRTC_R20 = NP_R20_COL16 | NP_R20_ANCHO_512;

    *NP_VC_R0 = 0x0000;          /* 16 colores */
    /* Prioridad: los sprites delante, el texto (marcador) encima del todo y la
       pantalla grafica al fondo, que aqui no se usa. */
    *NP_VC_R1 = 0x0100;
    *NP_VC_R2 = NP_VC_SPRITES | NP_VC_TEXTO;

    np_subir_paletas();
    np_subir_patrones();
    np_limpiar_capa();
    np_limpiar_sprites();

    /* El sistema de sprites lleva su propio temporizado, aparte del CRTC. */
    *NP_BG_HTOTAL = 0x0037;
    *NP_BG_HDISP  = 0x000A;
    *NP_BG_VDISP  = 0x0010;
    *NP_BG_RES    = NP_BG_PATRON16;
    *NP_BG_CTRL   = NP_BG_CHIP_ON | NP_BG_CAPA_ON | NP_BG_TABLA_ALTA;
}

/* --- el escenario ------------------------------------------------------- */

/* Escribe una columna del nivel en BG0.
 *
 * Los numeros de patron se piden de golpe (np_tile_gfx_column) para que haya
 * una multiplicacion de 32 bits por columna y no una por casilla: en un 68000
 * cada una es una llamada a la rutina de aritmetica del compilador.
 */
static void np_columna_escenario(const NpWorld *w, int32_t tile_x)
{
    const NpLevel *nivel = w->level;
    uint16_t patrones[NP_BG_FILAS];
    uint16_t columna = (uint16_t)(tile_x & (NP_BG_COLUMNAS - 1));
    int32_t alto = (int32_t)nivel->height;
    int32_t fila;

    if (alto > NP_BG_FILAS) alto = NP_BG_FILAS;
    np_tile_gfx_column(w, tile_x, 0, (uint16_t)alto, patrones);
    for (fila = 0; fila < alto; fila++)
        NP_BG_MAPA[fila * NP_BG_COLUMNAS + columna] =
            NP_CASILLA(patrones[fila], np_tileset_palette);
    for (; fila < NP_BG_FILAS; fila++)
        NP_BG_MAPA[fila * NP_BG_COLUMNAS + columna] = 0;
}

static void np_scroll(const NpWorld *w)
{
    /* El scroll de esta capa es "donde empieza a leerse el mapa", asi que va
       con el mismo signo que la camara, al reves que en la Mega Drive. */
    *NP_BG0_X = (uint16_t)(int16_t)w->cam_x;
    *NP_BG0_Y = (uint16_t)(int16_t)w->cam_y;
}

/* --- el parallax: la pantalla grafica ------------------------------------
 *
 * La unica capa del chip de sprites se la lleva el escenario, asi que el
 * parallax va en la pantalla grafica (GVRAM), que se ve a la vez, por detras,
 * y tiene su propio scroll por hardware. Ver np_x68k.h.
 *
 * La pagina es de 512 pixeles de ancho y se repite sola, asi que la capa se
 * escribe repetida hasta llenarla: luego el scroll da la vuelta solo y no hay
 * que tocar nada por frame mas que dos registros.
 */

/* Mueve la pantalla grafica: la pagina 0, que es la que se ve a 16 colores
   (ver np_x68k.h). Lo que se ve en la columna X de la pantalla es la columna
   X + scroll de la imagen, asi que para poner la columna `c` de la imagen en
   la `p` de la pantalla se escribe c - p. */
static void np_grafica_scroll(uint16_t x)
{
    *NP_SCROLL_X = x;
    *NP_SCROLL_Y = 0;
}

static const NpCapaX68k *np_capa_puesta;

static void np_capa_borrar(void)
{
    uint32_t i, cuantos = (uint32_t)NP_GVRAM_ANCHO * NP_GVRAM_ALTO;
    for (i = 0; i < cuantos; i++) NP_GVRAM[i] = 0;
}

/* Escribe la imagen de una capa en la GVRAM, repetida a lo ancho. */
static void np_capa_cargar(const NpCapaX68k *capa)
{
    const uint8_t *datos = &np_capa_datos[capa->offset];
    uint16_t bytes_fila = (uint16_t)(capa->ancho / 2);
    uint16_t y, x;

    for (y = 0; y < capa->alto; y++) {
        volatile uint16_t *destino;
        const uint8_t *fila = datos + (uint32_t)y * bytes_fila;
        uint16_t pantalla_y = (uint16_t)(capa->y + y);
        if (pantalla_y >= NP_GVRAM_ALTO) break;
        destino = &NP_GVRAM[(uint32_t)pantalla_y * NP_GVRAM_ANCHO];
        for (x = 0; x < NP_GVRAM_ANCHO; x += 2) {
            uint8_t par = fila[(x % capa->ancho) / 2];
            destino[x] = (uint16_t)(par >> 4);
            destino[x + 1] = (uint16_t)(par & 15);
        }
    }
}

/* La capa del nivel, o ninguna. Se llama al empezar cada nivel. */
static void np_capa_nivel(const NpWorld *w)
{
    uint8_t numero = np_capa_de_nivel[w->level_index];
    uint16_t i;

    np_capa_puesta = 0;
    np_capa_borrar();
    if (!numero) {
        *NP_VC_R2 = NP_VC_SPRITES | NP_VC_TEXTO;
        return;
    }
    np_capa_puesta = &np_capas[numero - 1];
    for (i = 0; i < 16; i++) NP_PALETA_GFX[i] = np_capa_puesta->paleta[i];
    np_capa_cargar(np_capa_puesta);
    *NP_VC_R2 = NP_VC_SPRITES | NP_VC_TEXTO | NP_VC_GRAFICA;
}

/* Y el scroll, que es lo unico que cuesta por frame: dos registros. */
static void np_capa_scroll(const NpWorld *w)
{
    int32_t x;
    if (!np_capa_puesta) return;
    x = (w->cam_x * (int32_t)np_capa_puesta->speed) >> 8;
    np_grafica_scroll((uint16_t)(x & (NP_GVRAM_ANCHO - 1)));
}

/* --- los actores -------------------------------------------------------- */

static uint16_t np_sprite_siguiente;

/* Coloca un sprite. Las coordenadas del chip llevan un desplazamiento fijo: el
   pixel (0, 0) de la pantalla es el (16, 16) para los sprites. */
static void np_sprite(int16_t x, int16_t y, uint8_t patron, uint8_t paleta,
                      uint8_t volteo)
{
    volatile uint16_t *reg;
    if (np_sprite_siguiente >= NP_SPRITES) return;
    reg = &NP_SPRITE_REGS[np_sprite_siguiente * 4];
    reg[0] = (uint16_t)((x + NP_SPRITE_ORIGEN_X) & 0x3FF);
    reg[1] = (uint16_t)((y + NP_SPRITE_ORIGEN_Y) & 0x3FF);
    reg[2] = (uint16_t)((volteo ? NP_VOLTEO_H : 0)
                        | ((uint16_t)paleta << 8) | patron);
    reg[3] = 3;                  /* delante de las dos capas */
    np_sprite_siguiente++;
}

/* Un actor puede ocupar varias casillas de ancho y de alto: cada una es un
   sprite. Los patrones de un fotograma van por columnas, igual que en la Neo
   Geo, para que el empaquetador sea el mismo. */
static void np_dibujar_actor(const NpActorDef *def, int32_t x, int32_t y,
                             uint8_t frame, uint8_t volteo)
{
    uint16_t base = (uint16_t)(def->first_tile + frame * def->cols * def->rows);
    uint8_t c, r;
    for (c = 0; c < def->cols; c++) {
        uint8_t origen = volteo ? (uint8_t)(def->cols - 1 - c) : c;
        for (r = 0; r < def->rows; r++) {
            int32_t sx = x + c * 16;
            int32_t sy = y + r * 16;
            if (sx <= -16 || sx >= NP_ANCHO) continue;
            if (sy <= -16 || sy >= NP_ALTO) continue;
            np_sprite((int16_t)sx, (int16_t)sy,
                      (uint8_t)(base + origen * def->rows + r),
                      def->palette, volteo);
        }
    }
}

#if NP_VISTA_CARRETERA
/* --- la carretera --------------------------------------------------------
 *
 * Aqui la calzada no se dibuja: se **desliza**, igual que en la Mega Drive. La
 * imagen en perspectiva la trae hecha el compilador -512 de ancho, con las
 * cuatro franjas dentro- y va en la pantalla grafica, que en el modo del kit
 * es una pagina de 512 que se repite sola. Pintarla por frame no cabria: un
 * pixel es una palabra, y son 36.000 escrituras largas, tres veces el frame.
 *
 * El escenario de tiles no se dibuja en absoluto: en esta vista el mapa es el
 * trazado de la carretera, no lo que se ve. La capa BG se deja en blanco y lo
 * unico que queda por encima de la grafica son los sprites y el marcador.
 *
 * Y las franjas que corren hacia ti tampoco se dibujan: son cuatro huecos de
 * paleta por cosa, rotados un paso por frame. Doce palabras a la paleta
 * grafica, que es donde vive la carretera. */
static void np_carretera_paleta(uint8_t fase)
{
    const uint8_t *huecos = np_carretera_huecos;
    uint8_t grupo, i;
    uint16_t copia[NP_CARRETERA_GRUPOS * NP_CARRETERA_FRANJAS];
    if (!np_capa_puesta) return;
    /* de la ficha de la capa, que es de donde salio la paleta grafica */
    for (grupo = 0; grupo < NP_CARRETERA_GRUPOS; grupo++)
        for (i = 0; i < NP_CARRETERA_FRANJAS; i++)
            copia[grupo * NP_CARRETERA_FRANJAS + i] =
                np_capa_puesta->paleta[huecos[grupo * NP_CARRETERA_FRANJAS + i]];
    for (grupo = 0; grupo < NP_CARRETERA_GRUPOS; grupo++) {
        const uint8_t *cuatro = &huecos[grupo * NP_CARRETERA_FRANJAS];
        for (i = 0; i < NP_CARRETERA_FRANJAS; i++)
            NP_PALETA_GFX[cuatro[i]] =
                copia[grupo * NP_CARRETERA_FRANJAS
                      + ((i + fase) & (NP_CARRETERA_FRANJAS - 1))];
    }
}

/* Un tamano de la calzada, con sprites. Se le da la esquina de arriba a la
   izquierda, igual que a np_dibujar_actor. */
static void np_bloque_carretera(const NpCarreteraTam *tam, int32_t x, int32_t y,
                                uint8_t frame)
{
    uint16_t base = (uint16_t)(tam->first_tile + (uint16_t)frame
                               * tam->cols * tam->rows);
    uint8_t c, r;
    for (c = 0; c < tam->cols; c++)
        for (r = 0; r < tam->rows; r++) {
            int32_t sx = x + c * 16;
            int32_t sy = y + r * 16;
            if (sx <= -16 || sx >= NP_ANCHO) continue;
            if (sy <= -16 || sy >= NP_ALTO) continue;
            np_sprite((int16_t)sx, (int16_t)sy,
                      (uint8_t)(base + c * tam->rows + r), tam->palette, 0);
        }
}

/* La calzada, deslizada **linea a linea**.
 *
 * El scroll de la pantalla grafica es uno para toda la pantalla, y con la
 * curva eso no vale: el eje de la calzada se va de 160 a 340 entre el
 * horizonte y el coche, asi que anclarlo en una sola linea deja el coche fuera
 * del asfalto. Medido en el motor con el circuito del andamiaje.
 *
 * Lo que si tiene esta maquina es lo que dice np_x68k.h: el CRTC avisa cuando
 * el haz llega a la linea que diga R09, y ese aviso entra en el MFP por GPIP6.
 * Asi que la carretera se desliza desde esa interrupcion: cada vez que salta,
 * escribe el scroll de su tramo y deja R09 en la linea del siguiente.
 *
 * No hacen falta 224 saltos. La curva hace que muchas lineas seguidas se
 * corran lo mismo, asi que el frame se reparte en tramos -una entrada por
 * cambio- y salen unas pocas decenas. Es la misma cuenta que en la Jaguar.
 *
 * La tabla va **doble**: el juego llena una mientras la interrupcion lee la
 * otra, y se cambian en el retrazo. Si se escribiera la que se esta leyendo,
 * el haz pillaria medio tramo del frame de antes y medio del nuevo. */
static int16_t np_centro_de_linea[NP_SCREEN_H];

#define NP_CARRETERA_TRAMOS 96

typedef struct {
    uint16_t linea;              /* donde empieza el tramo */
    uint16_t scroll;             /* lo que hay que poner en R12 */
} NpTramoVia;

static NpTramoVia np_tramos[2][NP_CARRETERA_TRAMOS];
static uint8_t np_tramos_n[2];
static volatile uint8_t np_tramo_tabla;   /* la que lee la interrupcion */
static volatile uint8_t np_tramo_i;       /* por que tramo va */
static uint8_t np_tramo_lleno;            /* la que esta llenando el juego */

/* Lo que hay que poner en R12 para que el eje de la calzada caiga donde dice
   la proyeccion en esa linea. */
static uint16_t np_via_scroll(uint16_t y)
{
    return (uint16_t)((NP_CARRETERA_EJE - np_centro_de_linea[y])
                      & (NP_GVRAM_ANCHO - 1));
}

/* La interrupcion de rastreo: escribe el scroll de este tramo y apunta al
   siguiente. Corta y sin llamadas, que salta unas cuantas veces por frame. */
static void __attribute__((interrupt_handler)) np_irq_rastreo(void)
{
    uint8_t tabla = np_tramo_tabla;
    uint8_t i = np_tramo_i;
    if (i < np_tramos_n[tabla]) {
        *NP_SCROLL_X = np_tramos[tabla][i].scroll;
        i++;
        np_tramo_i = i;
        /* la linea del siguiente, o fuera de pantalla si era el ultimo */
        *NP_CRTC_R09 = (uint16_t)(i < np_tramos_n[tabla]
                                  ? np_tramos[tabla][i].linea : 0x3FF);
    }
    *NP_MFP_ISRA = (uint8_t)~NP_MFP_RASTERE;   /* un cero reconoce, ver MC68901 */
}

static void np_carretera_irq_init(void)
{
    volatile uint32_t *vector = (volatile uint32_t *)0;
    /* El MFP del X68000 pone sus vectores a partir del $40; GPIP6 es su canal
       14, asi que el vector es el $4E. */
    vector[0x4E] = (uint32_t)(uintptr_t)&np_irq_rastreo;
    *NP_MFP_AER &= (uint8_t)~NP_MFP_RASTERE;   /* avisa al bajar, como el CRTC */
    *NP_MFP_DDR &= (uint8_t)~NP_MFP_RASTERE;   /* GPIP6 es entrada */
    *NP_MFP_IERA |= NP_MFP_RASTERE;
    *NP_MFP_IMRA |= NP_MFP_RASTERE;
    __asm__ volatile ("andi.w #0xF8FF,%sr");   /* que pasen las del MFP */
}

static void np_carretera_desliza(const NpWorld *w)
{
    uint16_t horizonte = np_carretera(w, np_centro_de_linea);
    uint8_t tabla = np_tramo_lleno;
    uint8_t n = 0;
    uint16_t y, antes;

    if (horizonte >= NP_SCREEN_H) return;
    /* Una entrada por **cambio** de scroll, no por linea. */
    antes = np_via_scroll(horizonte);
    np_tramos[tabla][n].linea = horizonte;
    np_tramos[tabla][n].scroll = antes;
    n++;
    for (y = (uint16_t)(horizonte + 1); y < NP_SCREEN_H; y++) {
        uint16_t ahora = np_via_scroll(y);
        if (ahora == antes) continue;
        if (n >= NP_CARRETERA_TRAMOS) break;
        np_tramos[tabla][n].linea = y;
        np_tramos[tabla][n].scroll = ahora;
        n++;
        antes = ahora;
    }
    np_tramos_n[tabla] = n;

    /* Y el cambio, en el retrazo: aqui no hay haz dibujando. */
    np_tramo_lleno = np_tramo_tabla;
    np_tramo_tabla = tabla;
    np_tramo_i = 0;
    *NP_SCROLL_X = np_tramos[tabla][0].scroll;   /* lo de arriba del horizonte */
    *NP_SCROLL_Y = 0;
    *NP_CRTC_R09 = np_tramos[tabla][0].linea;
}
#endif /* NP_VISTA_CARRETERA */

/* --- un frame ----------------------------------------------------------- */

void np_video_frame(const NpWorld *w)
{
    const uint8_t *orden;
    uint8_t cuantas;
    static int32_t ultima_columna = -9999;
    static const NpLevel *ultimo_nivel = 0;
    /* al abrirse una puerta la casilla pasa a ser aire: hay que repintar */
    static uint8_t ultimos_abiertos = 0;
    int32_t columna = w->cam_x >> 4;
    uint8_t i;

    if (w->level != ultimo_nivel || w->abiertos_n != ultimos_abiertos) {
        int32_t c;
        ultimo_nivel = w->level;
        ultimos_abiertos = w->abiertos_n;
        ultima_columna = columna;
        /* por donde no hay capa ni sprite se ve el color 0 de la paleta
           grafica, asi que ese es el fondo del nivel */
        np_capa_nivel(w);
        NP_PALETA_GFX[0] = (uint16_t)w->level->background;
#if NP_VISTA_CARRETERA
        /* Conduciendo no hay escenario que dibujar: en esta vista el mapa es
           el trazado de la carretera. La capa BG se **apaga** entera (el chip
           se queda encendido, que de el salen los sprites) y lo que se ve es
           la pantalla grafica con la calzada, mas los sprites encima. */
        np_limpiar_capa();
        *NP_BG0_X = 0;
        *NP_BG0_Y = 0;
        *NP_BG_CTRL = NP_BG_CHIP_ON;
        np_carretera_irq_init();
        (void)c;
#else
        for (c = columna - 1; c <= columna + NP_COLUMNAS + 1; c++)
            np_columna_escenario(w, c);
#endif
    } else {
#if !NP_VISTA_CARRETERA
        while (ultima_columna < columna) {          /* avanzando a la derecha */
            ultima_columna++;
            np_columna_escenario(w, ultima_columna + NP_COLUMNAS);
        }
        while (ultima_columna > columna) {          /* hacia atras */
            ultima_columna--;
            np_columna_escenario(w, ultima_columna - 1);
        }
#endif
    }

#if NP_VISTA_CARRETERA
    np_carretera_paleta(np_carretera_fase(w));
    np_carretera_desliza(w);
#else
    np_scroll(w);
    np_capa_scroll(w);
#endif

    np_sprite_siguiente = 0;
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
    /* Lo que hay en la calzada va donde dice la proyeccion y del tamano que le
       toca, y en el orden que dice el motor: de lejos a cerca. */
    {
        NpEnLaVia visto[NP_CARRETERA_A_LA_VEZ];
        uint8_t cuantos = np_carretera_trafico(w, visto, NP_CARRETERA_A_LA_VEZ);
        uint8_t j;
        for (j = 0; j < cuantos; j++) {
            const NpEntity *e = &w->entities[visto[j].entidad];
            const NpActorDef *def = np_entity_def(e);
            const NpCarreteraTam *tam = np_carretera_dibujo(def, visto[j].escala);
            if (!tam) continue;
            /* El dibujo viene centrado y apoyado abajo en su bloque. */
            np_bloque_carretera(tam,
                                visto[j].sx - tam->cols * 16 / 2,
                                visto[j].sy - tam->rows * 16,
                                np_actor_frame(def, e->anim, e->anim_frame));
        }
    }
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        int32_t cx, cy;
        if (!np_player_visible(w, i)) continue;
        /* El coche va en un sitio fijo abajo: la camara le sigue. Sin espejo,
           que se ve de culo. */
        np_carretera_coche(w, i, &cx, &cy);
        np_dibujar_actor(def, cx, cy,
                         np_actor_frame(def, p->anim, p->anim_frame), 0);
    }
    (void)orden; (void)cuantas;
#elif NP_VISTA_ISO
    for (i = 0; i < cuantas; i++) {
        const NpActorDef *def;
        int32_t sx, sy;
        uint8_t frame, flip;
        def = np_dibujo(w, NP_DIBUJO(orden, i), &sx, &sy, &frame, &flip);
        if (!def) continue;
        sx -= w->cam_x;
        sy -= w->cam_y;
        if (sx <= -(def->cols * 16) || sx >= NP_ANCHO) continue;
        if (sy <= -(def->rows * 16) || sy >= NP_ALTO) continue;
        np_dibujar_actor(def, sx, sy, frame, flip);
    }
#else
    for (i = 0; i < cuantas; i++) {
        const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
        const NpActorDef *def;
        int32_t sx, sy;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;    /* parpadeo al recibir */
        def = np_entity_def(e);
        sx = NP_F2I(e->x) - def->box_x - w->cam_x;
        sy = NP_F2I(e->y) - def->box_y - w->cam_y;
        if (sx <= -(def->cols * 16) || sx >= NP_ANCHO) continue;
        if (sy <= -(def->rows * 16) || sy >= NP_ALTO) continue;
        np_dibujar_actor(def, sx, sy, np_actor_frame(def, e->anim, e->anim_frame),
                         (uint8_t)!e->facing);
    }

    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        if (!np_player_visible(w, i)) continue;
        np_dibujar_actor(def, NP_F2I(p->x) - def->box_x - w->cam_x,
                         NP_F2I(p->y) - def->box_y - w->cam_y,
                         np_actor_frame(def, p->anim, p->anim_frame),
                         (uint8_t)!p->facing);
    }
#endif

    /* los que sobran se apagan: si no, se quedarian donde estuvieran */
    while (np_sprite_siguiente < NP_SPRITES) {
        NP_SPRITE_REGS[np_sprite_siguiente * 4 + 3] = 0;
        np_sprite_siguiente++;
    }

#if NP_HUD_ENABLED
    np_hud_draw(w);
#endif
}

/* --- sincronizacion y mandos -------------------------------------------- */

/* El bit V-DISP del MFP esta a cero mientras se dibuja la imagen y a uno
   durante el retrazo. Se espera a que acabe la imagen de este frame y empiece
   el retrazo, que es cuando se puede tocar la VRAM sin que se vea. */
void np_wait_vblank(void)
{
    while ((*NP_MFP_GPIP & NP_MFP_GPIP_VDISP) != 0) { }
    while ((*NP_MFP_GPIP & NP_MFP_GPIP_VDISP) == 0) { }
}

static uint16_t np_leer_mando(volatile uint8_t *puerto)
{
    uint8_t bits = *puerto;
    uint16_t salida = 0;
    if (NP_MANDO_PULSADO(bits, NP_JOY_IZQUIERDA)) salida |= NP_IN_LEFT;
    if (NP_MANDO_PULSADO(bits, NP_JOY_DERECHA))   salida |= NP_IN_RIGHT;
    if (NP_MANDO_PULSADO(bits, NP_JOY_ARRIBA))    salida |= NP_IN_UP;
    if (NP_MANDO_PULSADO(bits, NP_JOY_ABAJO))     salida |= NP_IN_DOWN;
    /* Este mando solo tiene dos botones y hace falta un tercero para empezar
       la partida, asi que el de saltar vale tambien de START: en el titulo y
       en el "game over" saltar no hace nada, asi que no se pisan. Es lo mismo
       que hace el Atari ST con su mando de un boton. */
    if (NP_MANDO_PULSADO(bits, NP_JOY_A))         salida |= NP_IN_JUMP | NP_IN_START;
    if (NP_MANDO_PULSADO(bits, NP_JOY_B))         salida |= NP_IN_ACTION;
    return salida;
}

uint16_t np_input_read(void)
{
    return np_leer_mando(NP_PPI_A);
}

uint16_t np_input_read2(void)
{
    return np_leer_mando(NP_PPI_B);
}
