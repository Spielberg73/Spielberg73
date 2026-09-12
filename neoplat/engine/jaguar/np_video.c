/* np_video.c - dibujado del juego en la Atari Jaguar.
 *
 * La lista de objetos que se monta es esta, de atras hacia delante:
 *
 *   rama      si la linea pasa del final de la pantalla, saltar al STOP
 *   rama      si aun no ha llegado al principio, tambien
 *   fondo     el mapa de bits del escenario, con el scroll aplicado
 *   actores   un objeto por cada trozo de jugador, enemigo u objeto
 *   marcador  la franja de arriba, encima de todo
 *   STOP
 *
 * El escenario se dibuja en el mapa de bits columna a columna segun entra por
 * el borde, igual que en el Amiga. Los actores no se dibujan: cada uno es un
 * objeto que compone el propio chip, con el color 0 como transparente.
 */

#include "np_jaguar.h"

/* Cada objeto son dos frases de 64 bits y la lista tiene que estar alineada a
   16 bytes: el chip lee de dos en dos frases. `volatile` porque quien la lee
   es el chip, no el programa (ver la nota de np_jaguar.h). */
#define NP_OBJETOS (4 + NP_ACTORES_MAX + NP_CARRETERA_OBJETOS + 1)
static volatile uint64_t np_lista[NP_OBJETOS * 2] __attribute__((aligned(16)));
static uint64_t np_copia[NP_OBJETOS * 2];       /* el original, para restaurarlo */
static uint16_t np_usados;                      /* frases ocupadas este frame  */

static uint16_t np_vdb, np_vde, np_ancho_reloj, np_alto_lineas;
static int32_t np_base_tile;                    /* primera columna dibujada    */
/* Un nivel que cabe entero de ancho en el mapa de bits no necesita ventana:
   se pinta al entrar y ya no se toca. Es lo que permite el mapa de bits alto
   y estrecho de los juegos que se suben, donde no queda margen para irlo
   corriendo. */
static uint8_t np_mapa_fijo;
static const NpLevel *np_nivel_actual;
/* Cuantas puertas habia abiertas al pintar el escenario: al abrirse una hay
   que repintar, que la casilla pasa a ser aire. */
static uint8_t np_abiertos_pintados;

/* --- la lista de objetos ------------------------------------------------ */

/* La direccion del siguiente objeto va partida entre las dos mitades de la
   frase; esta es la misma cuenta que hace el SDK de Atari. */
static uint32_t np_enlace_alto(uint32_t dir) { return dir >> 11; }
static uint32_t np_enlace_bajo(uint32_t dir) { return (dir & 0xFFFFu) << 21; }

/* Cada objeto enlaza con el siguiente hueco de la lista; el STOP se pone al
   final de lo que se haya usado y las dos ramas se apuntan a el al cerrar. */
static uint32_t np_hueco(uint16_t i)
{
    return NP_DIR(&np_lista[i]);
}

/* Mete un mapa de bits en la lista: `datos` es la esquina de arriba a la
   izquierda, `paso` el ancho de la imagen completa en frases y `ancho` el que
   se ve. */
static void np_objeto(uint32_t datos, int16_t x, int16_t y,
                      uint16_t ancho, uint16_t alto, uint16_t paso,
                      uint16_t transparente)
{
    uint16_t i = np_usados;
    uint32_t siguiente = np_hueco((uint16_t)(i + 2));
    uint32_t alto_e = np_enlace_alto(siguiente), bajo_e = np_enlace_bajo(siguiente);
    uint16_t ypos;

    if (i + 2 > (NP_OBJETOS - 1) * 2) return;   /* la lista esta llena */
    if (y >= (int16_t)NP_SCREEN_H) return;
    if (y < 0) {                                /* recortar por arriba */
        if (-y >= (int16_t)alto) return;
        datos += (uint32_t)(-y) * paso * 8;
        alto = (uint16_t)(alto + y);
        y = 0;
    }
    if (y + alto > NP_SCREEN_H) alto = (uint16_t)(NP_SCREEN_H - y);

    ypos = (uint16_t)((np_vdb + np_alto_lineas - NP_SCREEN_H + y * 2) & 0xFFFE);
    np_copia[i] = ((uint64_t)(alto_e | (datos << 8)) << 32)
                | (bajo_e | NP_OBJ_BITMAP | ((uint32_t)ypos << 3)
                   | ((uint32_t)alto << 14));
    np_copia[i + 1] = ((uint64_t)((ancho >> 4) | (transparente ? NP_OBJ_TRANS : 0)) << 32)
                    | (((uint32_t)x & 0xFFFu) | NP_OBJ_DEPTH8 | NP_OBJ_NOGAP
                       | ((uint32_t)paso << 18) | ((uint32_t)ancho << 28));
    np_usados = (uint16_t)(i + 2);
}

/* Las dos ramas que recortan el area visible, siempre las primeras. */
/* Las dos ramas que recortan el area visible. Van siempre las primeras y son
   objetos de una frase, asi que ocupan los huecos 0 y 1. */
static void np_ramas(void)
{
    np_usados = 2;
}

static void np_rama(uint16_t hueco, uint32_t destino, uint32_t cc, uint16_t linea)
{
    uint32_t alto_e = np_enlace_alto(destino), bajo_e = np_enlace_bajo(destino);
    np_copia[hueco] = ((uint64_t)alto_e << 32)
                    | (bajo_e | NP_OBJ_BRANCH | (cc << 14)
                       | ((uint32_t)(linea & 0x7FF) << 3));
}

static void np_cerrar_lista(void)
{
    uint32_t parada = np_hueco(np_usados);
    np_copia[np_usados] = (uint64_t)(NP_OBJ_STOP | 8u);
    /* cc = 2: saltar si la linea pasa del final; cc = 1: si aun no ha llegado */
    np_rama(0, parada, 2, np_vde);
    np_rama(1, parada, 1, np_vdb);
    np_usados = (uint16_t)(np_usados + 1);
}

/* La lista viva SOLO se toca aqui, en el retrazo.
 *
 * Por dos razones: el chip gasta las frases mientras dibuja (va restando de la
 * altura y sumando a la direccion), y ademas si se reescriben con el haz en
 * mitad de la pantalla el objeto se vuelve a dibujar desde arriba a partir de
 * ahi. Asi salia el marcador dos veces, la segunda justo donde acababa de
 * llegar la CPU. */
static void np_volcar_lista(void)
{
    uint16_t i;
    for (i = 0; i <= np_usados; i++)
        np_lista[i] = np_copia[i];
}

#if NP_VISTA_CARRETERA
/* --- el retrazo por interrupcion ---------------------------------------
 *
 * Conduciendo, esta maquina no llega a 60: un frame de carretera tarda algo
 * mas de un retrazo. Y como el chip **gasta** la lista segun la dibuja, el
 * retrazo que pasaba mientras el juego pensaba pillaba una lista ya gastada y
 * no dibujaba nada: la pantalla se quedaba en negro uno de cada dos frames, y
 * desde fuera parecia que la carretera no se dibujaba en absoluto.
 *
 * Volcar varias veces seguidas desde el bucle principal tapa unos cuantos de
 * esos retrazos (medido en el emulador: se ve el 33% con uno, el 50% juntando
 * las lineas que se corren lo mismo, el 66% con dos volcados y el 75% con
 * tres), pero nunca el ultimo: **el que pasa mientras el juego piensa**, que
 * por definicion es cuando el bucle no esta mirando. Ese solo lo tapa una
 * interrupcion. Con ella se ve el **100%**, y ademas el juego va mas deprisa,
 * porque ya no gasta dos retrazos enteros esperando a nada.
 *
 * La lista que vuelca la interrupcion no puede ser la que esta escribiendo el
 * juego (la pillaria a medio hacer, sin el STOP del final, y el chip se
 * saldria de la lista). Por eso hay una tercera copia, la maestra: el juego
 * termina su lista tranquilo en np_copia y solo entonces, con la interrupcion
 * cerrada un momento, la pasa a la maestra de una pieza.
 */
static uint64_t np_maestra[NP_OBJETOS * 2];
static uint16_t np_maestra_usados;
static volatile uint8_t np_hubo_retrazo;

static uint16_t np_cerrar_paso(void)
{
    uint16_t sr;
    __asm__ volatile("move.w %%sr,%0\n\tor.w #0x0700,%%sr" : "=d"(sr) : : "memory");
    return sr;
}

static void np_abrir_paso(uint16_t sr)
{
    __asm__ volatile("move.w %0,%%sr" : : "d"(sr) : "memory");
}

static void np_guardar_maestra(void)
{
    uint16_t i, sr = np_cerrar_paso();
    for (i = 0; i <= np_usados; i++)
        np_maestra[i] = np_copia[i];
    np_maestra_usados = np_usados;
    np_abrir_paso(sr);
}

static void __attribute__((interrupt_handler)) np_irq_video(void)
{
    uint16_t i;
    for (i = 0; i <= np_maestra_usados; i++)
        np_lista[i] = np_maestra[i];
    np_hubo_retrazo = 1;
    INT1 = 0x0101;                        /* servida: soltar el pestillo  */
    INT2 = 0;
}

/* TOM no interrumpe por autovector: pone su propio numero de vector, el 64,
 * que en el 68000 es la direccion $100. Comprobado poniendo la rutina solo
 * ahi (se ve el 100% de los frames) y solo en el autovector de nivel 2, en
 * $68 (la maquina se va a paseo: 0%). */
static volatile uintptr_t np_tabla_vectores = 0;

static void np_encender_irq(void)
{
    /* La tabla de vectores esta en el cero de la DRAM. El puntero se calcula
       aparte porque el compilador, si le escribes directamente en la direccion
       cero, avisa de que eso suele ser un error. Aqui no lo es. */
    volatile uint32_t *vector = (volatile uint32_t *)np_tabla_vectores;
    uint32_t rutina = NP_DIR(&np_irq_video);
    vector[0x100 / 4] = rutina;
    VI = np_vde;                          /* justo al empezar el retrazo  */
    INT1 = 0x0001;                        /* dejar pasar la de video      */
    __asm__ volatile("move.w #0x2000,%%sr" : : : "memory");
}
#endif

/* --- arranque ----------------------------------------------------------- */

static void np_init_video(void)
{
    uint16_t medio, mitad;
    if (CONFIG & 0x10) { medio = 823; np_ancho_reloj = 1409; np_vde = 266; np_alto_lineas = 241; }
    else               { medio = 843; np_ancho_reloj = 1381; np_vde = 322; np_alto_lineas = 287; }
    mitad = (uint16_t)(np_ancho_reloj >> 1);
    HDE = (uint16_t)((mitad - 1) | 0x400);
    HDB1 = HDB2 = (uint16_t)(medio - mitad + 4);
    np_vdb = (uint16_t)(np_vde - np_alto_lineas);
    np_vde = (uint16_t)(np_vde + np_alto_lineas);
    VDB = np_vdb;
    VDE = 0xFFFF;
    BORD1 = 0;
    BG = 0;
}

void np_jaguar_init(void)
{
    uint16_t i;
    np_init_video();
    for (i = 0; i < 256; i++) CLUT[i] = np_colores[i];
    np_base_tile = -9999;
    np_nivel_actual = 0;
    np_ramas();
    np_cerrar_lista();
    np_volcar_lista();
    OLP = (NP_DIR(np_lista) >> 16) | (NP_DIR(np_lista) << 16);  /* palabras cambiadas */
    VMODE = NP_VMODE;
#if NP_VISTA_CARRETERA
    np_guardar_maestra();                 /* antes de encenderla, que tenga que volcar */
    np_encender_irq();
#endif
}

/* --- escenario ---------------------------------------------------------- */

/* Copia un tile de 16x16 al mapa de bits. Un byte por pixel: es una copia y ya. */
static void np_pegar_tile_en(uint8_t *mapa, uint16_t tile, int32_t x, int32_t y)
{
    const uint8_t *origen = np_tile_data + (uint32_t)tile * (NP_TILE * NP_TILE);
    uint8_t *destino = mapa + (uint32_t)y * NP_MAPA_ANCHO + x;
    uint8_t fila;
    for (fila = 0; fila < NP_TILE; fila++) {
        uint32_t *d = (uint32_t *)(void *)destino;
        const uint32_t *o = (const uint32_t *)(const void *)origen;
        uint8_t i;
        for (i = 0; i < NP_TILE / 4; i++) *d++ = *o++;   /* de cuatro en cuatro */
        origen += NP_TILE;
        destino += NP_MAPA_ANCHO;
    }
}

static void np_pegar_tile(uint16_t tile, int32_t x, int32_t y)
{
    np_pegar_tile_en(np_bitmap, tile, x, y);
}

static void np_columna(const NpWorld *w, int32_t tile_x)
{
    int32_t columna = tile_x - np_base_tile;
    uint16_t tiles[NP_MAPA_ALTO / NP_TILE];
    int32_t fila;
    if (columna < 0 || columna >= NP_MAPA_ANCHO / NP_TILE) return;
    np_tile_gfx_column(w, tile_x, 0, NP_MAPA_ALTO / NP_TILE, tiles);
    for (fila = 0; fila < NP_MAPA_ALTO / NP_TILE; fila++)
        np_pegar_tile(tiles[fila], columna * NP_TILE, fila * NP_TILE);
}

static void np_redibujar_todo(const NpWorld *w)
{
    int32_t i;
    np_mapa_fijo = (uint8_t)(w->level->width * NP_TILE <= NP_MAPA_ANCHO);
    np_base_tile = np_mapa_fijo ? 0 : (w->cam_x / NP_TILE) - 1;
    if (np_base_tile < 0) np_base_tile = 0;
    for (i = 0; i < NP_MAPA_ANCHO / NP_TILE; i++) np_columna(w, np_base_tile + i);
    /* el mapa de bits no lo lee el programa, lo lee el chip: sin la barrera el
       compilador se cargaria las copias */
    __asm__ __volatile__ ("" ::: "memory");
}

#if NP_LAYER_COUNT > 0
/* --- el parallax --------------------------------------------------------
 *
 * En la Jaguar el parallax es casi gratis: la capa es **otro objeto** de la
 * lista, con su propio mapa de bits y su propia posicion. El chip lo compone
 * antes que el escenario, y como el escenario lleva el color 0 transparente,
 * se ve por los huecos.
 *
 * El dibujo se pinta una vez al entrar en el nivel, repetido a lo ancho; a
 * partir de ahi mover la capa es cambiar dos numeros en la lista.
 */
static void np_pintar_fondo(const NpWorld *w)
{
    uint32_t *p = (uint32_t *)(void *)np_fondo_bitmap;
    uint32_t i;
    for (i = 0; i < (uint32_t)NP_MAPA_ANCHO * NP_FONDO_ALTO / 4; i++) *p++ = 0;
    if (w->level->layer_count && np_layers[w->level->layers[0]].cols) {
        const NpLayer *capa = &np_layers[w->level->layers[0]];
        int32_t columnas = NP_MAPA_ANCHO / NP_TILE;
        int32_t c, r;
        for (c = 0; c < columnas; c++) {
            int32_t fuente = c % capa->cols;
            for (r = 0; r < capa->rows; r++) {
                int32_t y = capa->offset_y + r * NP_TILE;
                if (y < 0 || y + NP_TILE > NP_FONDO_ALTO) continue;
                np_pegar_tile_en(np_fondo_bitmap,
                                 capa->tiles[r * capa->cols + fuente],
                                 c * NP_TILE, y);
            }
        }
    }
    __asm__ __volatile__ ("" ::: "memory");
}

#if NP_VISTA_CARRETERA
/* --- la carretera: una linea, un objeto ---------------------------------
 *
 * Aqui la Jaguar hace de una vez lo que a la Mega Drive le cuesta una tabla y
 * al Amiga una lista de copper. El Object Processor recorre la lista de
 * objetos **en cada linea de barrido**, asi que un mapa de bits de una sola
 * linea de alto, con su propia X, es exactamente una entrada de scroll por
 * linea. Doscientas veinticuatro de esas y la carretera esta puesta.
 *
 * La imagen es la misma que se lleva la Mega Drive -512 de ancho, con las
 * cuatro franjas dibujadas dentro- y se pinta una vez al entrar en el nivel.
 * Las rayas corren rotando la tabla de colores, que aqui son doce palabras a
 * la CLUT.
 */
#define NP_CARR_ANCHO (NP_CARRETERA_EJE * 2)
#define NP_CARR_MARGEN (NP_CARR_ANCHO - NP_SCREEN_W)

static int16_t np_carretera_centro[NP_SCREEN_H];

/* Pinta la carretera en el mapa de bits del fondo. Una vez por nivel. */
static void np_pintar_carretera(void)
{
    const NpLayer *capa = &np_layers[np_carretera_capa];
    uint32_t *p = (uint32_t *)(void *)np_fondo_bitmap;
    uint32_t i;
    int32_t c, r;
    for (i = 0; i < (uint32_t)NP_MAPA_ANCHO * NP_FONDO_ALTO / 4; i++) *p++ = 0;
    for (c = 0; c < (int32_t)capa->cols; c++)
        for (r = 0; r < (int32_t)capa->rows; r++) {
            int32_t y = r * NP_TILE;
            if (y + NP_TILE > NP_FONDO_ALTO) continue;
            np_pegar_tile_en(np_fondo_bitmap,
                             capa->tiles[r * capa->cols + c], c * NP_TILE, y);
        }
    __asm__ __volatile__ ("" ::: "memory");
}

/* Las cuatro entradas de color de cada cosa, rotadas un paso. Es lo mismo que
   hace la Mega Drive con la CRAM: la imagen no se toca, se mueve la paleta. */
static void np_paleta_carretera(uint8_t fase)
{
    const uint8_t *huecos = np_carretera_huecos;
    uint8_t grupo, i;
    for (grupo = 0; grupo < NP_CARRETERA_GRUPOS; grupo++) {
        const uint8_t *cuatro = &huecos[grupo * NP_CARRETERA_FRANJAS];
        for (i = 0; i < NP_CARRETERA_FRANJAS; i++)
            CLUT[cuatro[i]] =
                np_colores[cuatro[(i + fase) & (NP_CARRETERA_FRANJAS - 1)]];
    }
}

/* Cuanto se corre la imagen en esta linea, ya recortado. */
static int32_t np_carretera_off(uint16_t y)
{
    int32_t off = NP_CARRETERA_EJE - np_carretera_centro[y];
    if (off < 0) off = 0;
    if (off > NP_CARR_MARGEN) off = NP_CARR_MARGEN;
    return off;
}

/* Y la lista. Un objeto por **tramo**, no por linea.
 *
 * La idea de partida era una linea un objeto, que es lo que el Object
 * Processor hace de perlas. Pero cada objeto cuesta armarlo y volcarlo, y 224
 * por frame no le caben al 68000 de esta maquina.
 *
 * Y no hacen falta 224. Un objeto de N lineas de alto dibuja N filas seguidas
 * del mapa de bits, que es exactamente lo que pide la carretera: la linea `y`
 * de la pantalla ensena la fila `y` de la imagen. Asi que las lineas seguidas
 * que se corren **lo mismo** van en un solo objeto, y eso es casi todas: en
 * recta la calzada no se mueve de lado, y en curva cambia de tramo en tramo.
 * De 224 objetos se baja a unas pocas decenas, y el juego pasa de 20 imagenes
 * por segundo a 30 (medido en el emulador). */
static void np_objetos_carretera(const NpWorld *w)
{
    uint16_t horizonte = np_carretera(w, np_carretera_centro);
    uint16_t y = horizonte;
    np_paleta_carretera(np_carretera_fase(w));
    while (y < NP_SCREEN_H) {
        int32_t off = np_carretera_off(y);
        uint16_t y0 = y;
        while (++y < NP_SCREEN_H && np_carretera_off(y) == off) ;
        /* La direccion salta de ocho en ocho pixeles -es lo que mide una frase
           de 64 bits a ocho bits por pixel- y lo que sobra lo pone la X del
           objeto, que si es por pixel. */
        np_objeto(NP_DIR(np_fondo_bitmap) + (uint32_t)y0 * NP_MAPA_ANCHO
                  + ((uint32_t)off & ~7u),
                  (int16_t)(-(off & 7)), (int16_t)y0,
                  NP_SCREEN_W + 8, (uint16_t)(y - y0), NP_MAPA_ANCHO / 8, 0);
    }
}
#endif /* NP_VISTA_CARRETERA */

/* Mete el objeto del parallax en la lista, ya desplazado. */
static void np_objeto_fondo(const NpWorld *w)
{
    int32_t sx = 0, sy = 0, periodo = 0;
    int32_t maximo = NP_MAPA_ANCHO - NP_SCREEN_W;
    if (!w->level->layer_count) return;
    {
        const NpLayer *capa = &np_layers[w->level->layers[0]];
        sx = ((int32_t)w->cam_x * capa->speed_x) >> 8;
        sy = ((int32_t)w->cam_y * capa->speed_y) >> 8;
        periodo = capa->cols * NP_TILE;
    }
    /* el dibujo esta repetido, asi que al llegar a su ancho se vuelve al
       principio sin que se note; una capa mas ancha que el hueco se para */
    if (periodo >= NP_TILE && periodo <= maximo) {
        sx %= periodo;
        if (sx < 0) sx += periodo;
    } else {
        if (sx < 0) sx = 0;
        if (sx > maximo) sx = maximo;
    }
    if (sy < 0) sy = 0;
    if (sy > NP_FONDO_ALTO - NP_SCREEN_H) sy = NP_FONDO_ALTO - NP_SCREEN_H;
    np_objeto(NP_DIR(np_fondo_bitmap) + (uint32_t)sy * NP_MAPA_ANCHO
              + ((uint32_t)sx & ~7u),
              (int16_t)(-(sx & 7)), 0,
              NP_SCREEN_W / 8 + 1, NP_SCREEN_H, NP_MAPA_ANCHO / 8, 1);
}
#endif /* NP_LAYER_COUNT */

/* --- actores ------------------------------------------------------------ */

/* Cada trozo de 16x16 de un actor entra en la lista como un objeto. */
/* Un bloque de tiles del tamano que sea. Va aparte del actor porque en la
   carretera lo que se pone en la lista de objetos no es la hoja del actor sino
   una de sus versiones encogidas, con sus propios tiles y su tamano. */
static void np_bloque(uint16_t first_tile, uint8_t cols, uint8_t rows,
                      int32_t x, int32_t y, uint8_t frame, uint8_t espejo)
{
    uint16_t base = (uint16_t)(first_tile + frame * cols * rows);
    uint8_t c, r;
    for (c = 0; c < cols; c++) {
        uint8_t origen = espejo ? (uint8_t)(cols - 1 - c) : c;
        int32_t px = x + c * NP_TILE;
        if (px <= -NP_TILE || px >= NP_SCREEN_W) continue;
        for (r = 0; r < rows; r++) {
            uint16_t tile = (uint16_t)(base + origen * rows + r);
            np_objeto(NP_DIR(np_tile_data) + (uint32_t)tile * (NP_TILE * NP_TILE),
                      (int16_t)px, (int16_t)(y + r * NP_TILE),
                      NP_TILE / 8, NP_TILE, NP_TILE / 8, 1);
        }
    }
}

static void np_actor(const NpActorDef *def, int32_t x, int32_t y,
                     uint8_t frame, uint8_t espejo)
{
    np_bloque(def->first_tile, def->cols, def->rows, x, y, frame, espejo);
}

/* --- un frame ----------------------------------------------------------- */

void np_video_frame(const NpWorld *w)
{
    const uint8_t *orden;
    uint8_t cuantas;
    int32_t columna = w->cam_x / NP_TILE;
    static int32_t ultima_columna = -9999;
    uint32_t datos;
    uint8_t i;

#if NP_VISTA_CARRETERA
    /* Conduciendo, el escenario **no se dibuja**: el mapa es el trazado de la
       carretera, no lo que se ve. */
    if (w->level != np_nivel_actual) {
        np_nivel_actual = w->level;
        np_pintar_carretera();
    }
    (void)ultima_columna;
    (void)columna;
    (void)datos;
#else
    if (w->level != np_nivel_actual || w->abiertos_n != np_abiertos_pintados) {
        np_nivel_actual = w->level;
        np_abiertos_pintados = w->abiertos_n;
#if NP_LAYER_COUNT > 0
        np_pintar_fondo(w);          /* el parallax se pinta una vez por nivel */
#endif
        np_redibujar_todo(w);
        ultima_columna = columna;
    } else if (!np_mapa_fijo) {
        while (ultima_columna < columna) {
            ultima_columna++;
            np_columna(w, ultima_columna + NP_SCREEN_W / NP_TILE);
        }
        while (ultima_columna > columna) {
            ultima_columna--;
            np_columna(w, ultima_columna);
        }
        if (w->cam_x - np_base_tile * NP_TILE > NP_MAPA_ANCHO - NP_SCREEN_W - NP_TILE * 2) {
            np_redibujar_todo(w);
            ultima_columna = columna;
        }
        __asm__ __volatile__ ("" ::: "memory");
    }
#endif /* NP_VISTA_CARRETERA */

    np_ramas();
    BG = w->level->background;

#if NP_VISTA_CARRETERA
    np_objetos_carretera(w);         /* una linea, un objeto */
#else
#if NP_LAYER_COUNT > 0
    np_objeto_fondo(w);              /* primero el parallax: va por detras */
#endif

    /* El escenario: el scroll grueso mueve la direccion de ocho en ocho pixeles
       y el fino se hace con la posicion X. Va con el color 0 transparente, asi
       que por los huecos se ve el parallax (o el color de fondo del nivel). */
    {
        int32_t dx = w->cam_x - np_base_tile * NP_TILE;
        int32_t dy = w->cam_y;
        if (dy < 0) dy = 0;
        if (dy > NP_MAPA_ALTO - NP_SCREEN_H) dy = NP_MAPA_ALTO - NP_SCREEN_H;
        datos = NP_DIR(np_bitmap) + (uint32_t)dy * NP_MAPA_ANCHO + ((uint32_t)dx & ~7u);
        np_objeto(datos, (int16_t)(-(dx & 7)), 0,
                  NP_SCREEN_W / 8 + 1, NP_SCREEN_H, NP_MAPA_ANCHO / 8, 1);
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
    /* Lo que hay en la calzada va **donde dice la proyeccion y del tamano que
       le toca**, no donde diga el mapa: en esta vista el mapa es el trazado. */
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
        np_bloque(tam->first_tile, tam->cols, tam->rows,
                  sx - tam->cols * NP_TILE / 2, sy - tam->rows * NP_TILE,
                  np_actor_frame(def, e->anim, e->anim_frame), 0);
    }
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        int32_t cx, cy;
        if (!np_player_visible(w, i)) continue;
        /* En un sitio fijo abajo: la camara le sigue. Sin espejo, que el coche
           se ve de culo y espejarlo cambiaria de asiento a los de dentro. */
        np_carretera_coche(w, i, &cx, &cy);
        np_actor(def, cx, cy, np_actor_frame(def, p->anim, p->anim_frame), 0);
    }
#elif NP_VISTA_ISO
    for (i = 0; i < cuantas; i++) {
        const NpActorDef *def;
        int32_t sx, sy;
        uint8_t frame, flip;
        def = np_dibujo(w, NP_DIBUJO(orden, i), &sx, &sy, &frame, &flip);
        if (!def) continue;
        np_actor(def, sx - w->cam_x, sy - w->cam_y, frame, flip);
    }
#else
    for (i = 0; i < cuantas; i++) {
        const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
        const NpActorDef *def;
        int32_t sx, sy;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;
        def = np_entity_def(e);
        sx = NP_F2I(e->x) - def->box_x - w->cam_x;
        sy = NP_F2I(e->y) - def->box_y - w->cam_y;
        np_actor(def, sx, sy, np_actor_frame(def, e->anim, e->anim_frame),
                 (uint8_t)!e->facing);
    }
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        if (!np_player_visible(w, i)) continue;
        np_actor(def, NP_F2I(p->x) - def->box_x - w->cam_x,
                 NP_F2I(p->y) - def->box_y - w->cam_y,
                 np_actor_frame(def, p->anim, p->anim_frame),
                 (uint8_t)!p->facing);
    }
#endif

#if NP_HUD_ENABLED
    np_hud_draw(w);
    np_objeto(NP_DIR(np_hud_bitmap), 0, 0, NP_SCREEN_W / 8, NP_HUD_ALTO,
              NP_SCREEN_W / 8, 0);
#endif

    np_cerrar_lista();
#if NP_VISTA_CARRETERA
    np_guardar_maestra();                 /* ya esta entera: que la vea la IRQ */
#endif
}

/* --- sincronizacion y mando --------------------------------------------- */

#if !NP_VISTA_CARRETERA
static void np_esperar_retrazo(void)
{
    while ((VC & 0x7FF) >= np_vde) ;      /* salir del retrazo de ahora   */
    while ((VC & 0x7FF) < np_vde) ;       /* y esperar al siguiente       */
}
#endif

void np_wait_vblank(void)
{
#if NP_VISTA_CARRETERA
    /* Conduciendo se espera **a la interrupcion**, no al contador de linea.
     *
     * Mirando el contador no valia: entre la linea en la que interrumpe y el
     * final de la cuenta solo hay diecisiete medias lineas, y volcar la lista
     * tarda mas que eso. Cuando la rutina soltaba el mando, el contador ya
     * habia dado la vuelta, asi que el bucle nunca llegaba a verlo pasado y
     * se quedaba dando vueltas frame tras frame: la imagen se veia entera y
     * quieta, porque el juego no avanzaba ni un paso.
     *
     * Con la bandera no hay ventana que perder: la pone la rutina y la ve el
     * bucle cuando le toque. */
    np_hubo_retrazo = 0;
    while (!np_hubo_retrazo) ;
#else
    np_esperar_retrazo();
    np_volcar_lista();                    /* la lista de este frame       */
#endif
}

/* El mando de la Jaguar es una matriz: se escribe una **palabra** con la fila
 * que se quiere en $F14000 y se lee un **long** de ahi mismo, que trae las dos
 * mitades del puerto. Los bits son activos a nivel bajo.
 *
 * Los sitios de cada boton salen de la rutina ReadJoypads del SDK de Atari,
 * deshaciendo las rotaciones que hace para dejarlos ordenados:
 *
 *   fila $81FE   bit 24 arriba, 25 abajo, 26 izquierda, 27 derecha,
 *                bit 1 boton A, bit 0 PAUSE
 *   fila $81FD   bit 1 boton B
 *
 * El segundo mando esta en la otra mitad de la misma matriz, y las filas **no
 * se piden con el mismo numero**: el puerto 1 mira el nibble bajo del byte que
 * se escribe y el puerto 2 el alto, y ademas la tabla del puerto 2 es la del 1
 * con los bits del reves. Sale asi:
 *
 *   puerto 1   fila 0 -> nibble $E   fila 1 -> $D   ($81FE y $81FD)
 *   puerto 2   fila 0 -> nibble $7   fila 1 -> $B   ($817F y $81BF)
 *
 * (los nibbles que sobran se dejan a $F, que no apunta a ningun mando). Las
 * direcciones del segundo salen cuatro bits mas arriba (28-31) y los botones
 * dos (2 y 3), asi que la lectura es la misma rutina con los numeros cambiados.
 * Esto esta comprobado en Virtual Jaguar: la tabla de filas sale del manual
 * tecnico (el adaptador de cuatro jugadores) y por eso no es la que se
 * esperaria.
 */
#define NP_JOY_MASCARA (*(volatile uint16_t *)(uintptr_t)(TOM + 0x14000))

static uint32_t np_fila_mando(uint16_t fila)
{
    NP_JOY_MASCARA = fila;
    return ~JOYSTICK;
}

static uint16_t np_input_de(uint16_t fila_a, uint16_t fila_b,
                            uint8_t cruz, uint8_t boton)
{
    uint32_t f0 = np_fila_mando(fila_a);
    uint32_t f1 = np_fila_mando(fila_b);
    uint16_t salida = 0;
    if (f0 & (1UL << (cruz + 0))) salida |= NP_IN_UP;
    if (f0 & (1UL << (cruz + 1))) salida |= NP_IN_DOWN;
    if (f0 & (1UL << (cruz + 2))) salida |= NP_IN_LEFT;
    if (f0 & (1UL << (cruz + 3))) salida |= NP_IN_RIGHT;
    if (f0 & (1UL << (boton + 1))) salida |= NP_IN_JUMP;      /* boton A */
    if (f1 & (1UL << (boton + 1))) salida |= NP_IN_ACTION;    /* boton B */
    if (f0 & (1UL << (boton + 0))) salida |= NP_IN_START;     /* PAUSE   */
    return salida;
}

uint16_t np_input_read(void)
{
    return np_input_de(0x81FE, 0x81FD, 24, 0);
}

uint16_t np_input_read2(void)
{
    return np_input_de(0x817F, 0x81BF, 28, 2);
}
