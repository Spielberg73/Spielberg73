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
#define NP_OBJETOS (4 + NP_ACTORES_MAX + 1)
static volatile uint64_t np_lista[NP_OBJETOS * 2] __attribute__((aligned(16)));
static uint64_t np_copia[NP_OBJETOS * 2];       /* el original, para restaurarlo */
static uint16_t np_usados;                      /* frases ocupadas este frame  */

static uint16_t np_vdb, np_vde, np_ancho_reloj, np_alto_lineas;
static int32_t np_base_tile;                    /* primera columna dibujada    */
static const NpLevel *np_nivel_actual;

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
}

/* --- escenario ---------------------------------------------------------- */

/* Copia un tile de 16x16 al mapa de bits. Un byte por pixel: es una copia y ya. */
static void np_pegar_tile(uint16_t tile, int32_t x, int32_t y)
{
    const uint8_t *origen = np_tile_data + (uint32_t)tile * (NP_TILE * NP_TILE);
    uint8_t *destino = np_bitmap + (uint32_t)y * NP_MAPA_ANCHO + x;
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

static void np_columna(const NpWorld *w, int32_t tile_x)
{
    int32_t columna = tile_x - np_base_tile;
    uint16_t tiles[NP_MAPA_ALTO / NP_TILE];
    int32_t fila;
    if (columna < 0 || columna >= NP_MAPA_ANCHO / NP_TILE) return;
    np_tile_gfx_column(w->level, tile_x, 0, NP_MAPA_ALTO / NP_TILE, tiles);
    for (fila = 0; fila < NP_MAPA_ALTO / NP_TILE; fila++)
        np_pegar_tile(tiles[fila], columna * NP_TILE, fila * NP_TILE);
}

static void np_redibujar_todo(const NpWorld *w)
{
    int32_t i;
    np_base_tile = (w->cam_x / NP_TILE) - 1;
    if (np_base_tile < 0) np_base_tile = 0;
    for (i = 0; i < NP_MAPA_ANCHO / NP_TILE; i++) np_columna(w, np_base_tile + i);
    /* el mapa de bits no lo lee el programa, lo lee el chip: sin la barrera el
       compilador se cargaria las copias */
    __asm__ __volatile__ ("" ::: "memory");
}

/* --- actores ------------------------------------------------------------ */

/* Cada trozo de 16x16 de un actor entra en la lista como un objeto. */
static void np_actor(const NpActorDef *def, int32_t x, int32_t y,
                     uint8_t frame, uint8_t espejo)
{
    uint16_t base = (uint16_t)(def->first_tile + frame * def->cols * def->rows);
    uint8_t c, r;
    for (c = 0; c < def->cols; c++) {
        uint8_t origen = espejo ? (uint8_t)(def->cols - 1 - c) : c;
        int32_t px = x + c * NP_TILE;
        if (px <= -NP_TILE || px >= NP_SCREEN_W) continue;
        for (r = 0; r < def->rows; r++) {
            uint16_t tile = (uint16_t)(base + origen * def->rows + r);
            np_objeto(NP_DIR(np_tile_data) + (uint32_t)tile * (NP_TILE * NP_TILE),
                      (int16_t)px, (int16_t)(y + r * NP_TILE),
                      NP_TILE / 8, NP_TILE, NP_TILE / 8, 1);
        }
    }
}

/* --- un frame ----------------------------------------------------------- */

void np_video_frame(const NpWorld *w)
{
    int32_t columna = w->cam_x / NP_TILE;
    static int32_t ultima_columna = -9999;
    uint32_t datos;
    uint8_t i;

    if (w->level != np_nivel_actual) {
        np_nivel_actual = w->level;
        np_redibujar_todo(w);
        ultima_columna = columna;
    } else {
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

    np_ramas();
    BG = w->level->background;

    /* El fondo: el scroll grueso mueve la direccion de ocho en ocho pixeles y
       el fino se hace con la posicion X. */
    {
        int32_t dx = w->cam_x - np_base_tile * NP_TILE;
        int32_t dy = w->cam_y;
        if (dy < 0) dy = 0;
        if (dy > NP_MAPA_ALTO - NP_SCREEN_H) dy = NP_MAPA_ALTO - NP_SCREEN_H;
        datos = NP_DIR(np_bitmap) + (uint32_t)dy * NP_MAPA_ANCHO + ((uint32_t)dx & ~7u);
        np_objeto(datos, (int16_t)(-(dx & 7)), 0,
                  NP_SCREEN_W / 8 + 1, NP_SCREEN_H, NP_MAPA_ANCHO / 8, 0);
    }

    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
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
    if (np_player_visible(w)) {
        const NpActorDef *def = &np_player_def.actor;
        np_actor(def, NP_F2I(w->player.x) - def->box_x - w->cam_x,
                 NP_F2I(w->player.y) - def->box_y - w->cam_y,
                 np_actor_frame(def, w->player.anim, w->player.anim_frame),
                 (uint8_t)!w->player.facing);
    }

#if NP_HUD_ENABLED
    np_hud_draw(w);
    np_objeto(NP_DIR(np_hud_bitmap), 0, 0, NP_SCREEN_W / 8, NP_HUD_ALTO,
              NP_SCREEN_W / 8, 0);
#endif

    np_cerrar_lista();
}

/* --- sincronizacion y mando --------------------------------------------- */

void np_wait_vblank(void)
{
    while ((VC & 0x7FF) >= np_vde) ;      /* salir del retrazo de ahora   */
    while ((VC & 0x7FF) < np_vde) ;       /* y esperar al siguiente       */
    np_volcar_lista();                    /* la lista de este frame       */
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
 */
#define NP_JOY_MASCARA (*(volatile uint16_t *)(uintptr_t)(TOM + 0x14000))

static uint32_t np_fila_mando(uint16_t fila)
{
    NP_JOY_MASCARA = fila;
    return ~JOYSTICK;
}

uint16_t np_input_read(void)
{
    uint32_t f0 = np_fila_mando(0x81FE);
    uint32_t f1 = np_fila_mando(0x81FD);
    uint16_t salida = 0;
    if (f0 & (1UL << 24)) salida |= NP_IN_UP;
    if (f0 & (1UL << 25)) salida |= NP_IN_DOWN;
    if (f0 & (1UL << 26)) salida |= NP_IN_LEFT;
    if (f0 & (1UL << 27)) salida |= NP_IN_RIGHT;
    if (f0 & (1UL << 1))  salida |= NP_IN_JUMP;      /* boton A */
    if (f1 & (1UL << 1))  salida |= NP_IN_ACTION;    /* boton B */
    if (f0 & (1UL << 0))  salida |= NP_IN_START;     /* PAUSE   */
    return salida;
}
