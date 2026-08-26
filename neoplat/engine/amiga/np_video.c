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
static const NpLevel *np_nivel_actual;

/* Lista del copper. Tiene dos partes: la de arriba pinta el marcador desde
   np_hud_bitmap y, al llegar a la linea NP_HUD_ALTO, engancha los bitplanes al
   mapa de bits del juego. Asi el marcador no se mueve con el scroll. */
#define NP_COP_CABECERA  12                       /* 6 pares de registros   */
#define NP_COP_COLORES   (NP_COP_CABECERA + 64)   /* 32 colores             */
#define NP_COP_COLOR0    (NP_COP_CABECERA + 1)    /* el fondo, que cambia   */
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
#define NP_COP_JUEGO_PTR (NP_COP_JUEGO + 6)
#define NP_COP_FIN       (NP_COP_JUEGO_PTR + NP_PLANOS * 4)
#define NP_COP_LARGO     (NP_COP_FIN + 2)

#define NP_LINEA_ARRIBA 0x2C                      /* primera linea visible  */

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

static void np_montar_copper(void)
{
    uint16_t *p = np_copper;
    uint8_t i;

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

static void np_columna(const NpWorld *w, int32_t tile_x)
{
    int32_t columna = tile_x - np_base_tile;
    int32_t fila;
    if (columna < 0 || columna >= NP_MAPA_ANCHO / NP_TILE) return;
    /* se pinta la columna entera, tambien lo que queda por debajo del nivel:
       si no, ahi se quedaria lo que hubiera dibujado antes */
    for (fila = 0; fila < NP_MAPA_ALTO / NP_TILE; fila++) {
        uint16_t tile = np_tile_gfx_at(w->level, tile_x, fila);
        np_blit_tile(tile, columna * NP_TILE, fila * NP_TILE);
    }
}

static void np_redibujar_todo(const NpWorld *w)
{
    int32_t i;
    np_base_tile = (w->cam_x / NP_TILE) - 1;
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

/* --- un frame ----------------------------------------------------------- */

/* Repintar el fondo es lo mas caro del frame, y los actores suelen ir juntos
   (las monedas van de tres en tres): sin esto, un mismo tile se repinta una vez
   por cada actor que lo toca. Un bit por tile del mapa de bits basta. */
#define NP_TILES_X (NP_MAPA_ANCHO / NP_TILE)
#define NP_TILES_Y (NP_MAPA_ALTO / NP_TILE)
static uint8_t np_ya_repintado[(NP_TILES_X * NP_TILES_Y + 7) / 8];

static void np_repintar_rastros(const NpWorld *w)
{
    uint8_t i;
    uint16_t b;
    if (!np_rastro_count) return;
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
                np_blit_tile(np_tile_gfx_at(w->level, tx, ty),
                             columna * NP_TILE, ty * NP_TILE);
            }
        }
    }
    np_rastro_count = 0;
}

static void np_apuntar_rastro(int32_t x, int32_t y, int16_t ancho, int16_t alto)
{
    if (np_rastro_count >= NP_MAX_RASTROS) return;
    np_rastros[np_rastro_count].x = (int16_t)x;
    np_rastros[np_rastro_count].y = (int16_t)y;
    np_rastros[np_rastro_count].ancho = ancho;
    np_rastros[np_rastro_count].alto = alto;
    np_rastro_count++;
}

static void np_dibujar_actor(const NpActorDef *def, int32_t mundo_x, int32_t mundo_y,
                             uint8_t frame, uint8_t flip)
{
    uint16_t base = (uint16_t)(def->first_tile + frame * def->cols * def->rows);
    uint8_t c, r;
    int32_t x = mundo_x - np_base_tile * NP_TILE;
    (void)flip;                         /* el espejo se hace con dibujos aparte */
    if (x < 0 || x + def->cols * NP_TILE >= NP_MAPA_ANCHO) return;
    for (c = 0; c < def->cols; c++) {
        for (r = 0; r < def->rows; r++) {
            int32_t py = mundo_y + r * NP_TILE;
            if (py < 0 || py + NP_TILE > NP_MAPA_ALTO) continue;
            np_blit_bob((uint16_t)(base + c * def->rows + r), x + c * NP_TILE, py);
        }
    }
    np_apuntar_rastro(mundo_x, mundo_y, (int16_t)(def->cols * NP_TILE),
                      (int16_t)(def->rows * NP_TILE));
}

void np_video_frame(const NpWorld *w)
{
    static int32_t ultima_columna = -9999;
    int32_t columna = w->cam_x / NP_TILE;
    uint32_t direccion;
    uint8_t i;

    if (w->level != np_nivel_actual) {
        np_nivel_actual = w->level;
        /* el color 0 es el fondo de la pantalla, y cada nivel trae el suyo */
        np_copper[NP_COP_COLOR0] = w->level->background;
#if NP_DOBLE_PLANO
        np_pintar_fondo(w);          /* el parallax se pinta una vez por nivel */
#endif
        np_redibujar_todo(w);
        ultima_columna = columna;
    } else {
        np_repintar_rastros(w);
        while (ultima_columna < columna) {
            ultima_columna++;
            np_columna(w, ultima_columna + NP_SCREEN_W / NP_TILE);
        }
        while (ultima_columna > columna) {
            ultima_columna--;
            np_columna(w, ultima_columna);
        }
        /* si la camara se acerca al final del mapa de bits, se vuelve a empezar */
        if (w->cam_x - np_base_tile * NP_TILE > NP_MAPA_ANCHO - NP_SCREEN_W - NP_TILE * 2) {
            np_redibujar_todo(w);
            ultima_columna = columna;
        }
    }

    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
        const NpActorDef *def;
        int32_t sx, sy;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;
        def = np_entity_def(e);
        sx = NP_F2I(e->x) - def->box_x;
        sy = NP_F2I(e->y) - def->box_y;
        if (sx < w->cam_x - 32 || sx > w->cam_x + NP_SCREEN_W) continue;
        np_dibujar_actor(def, sx, sy, np_actor_frame(def, e->anim, e->anim_frame),
                         (uint8_t)!e->facing);
    }
    if (np_player_visible(w)) {
        const NpActorDef *def = &np_player_def.actor;
        np_dibujar_actor(def, NP_F2I(w->player.x) - def->box_x,
                         NP_F2I(w->player.y) - def->box_y,
                         np_actor_frame(def, w->player.anim, w->player.anim_frame),
                         (uint8_t)!w->player.facing);
    }

    /* scroll: los punteros van al pixel de arriba a la izquierda de lo que se ve */
    direccion = NP_DIR(np_bitmap)
        + (uint32_t)(w->cam_y + NP_HUD_ALTO) * NP_PASO_FILA
        + (uint32_t)((w->cam_x - np_base_tile * NP_TILE) / 16) * 2;
    np_punteros(direccion);
#if NP_DOBLE_PLANO
    {
        uint16_t fino = np_mover_fondo(w);
        np_copper[NP_COP_HUD + 1] = (uint16_t)(fino << 4);
        np_copper[NP_COP_JUEGO + 1] = (uint16_t)((fino << 4) | (w->cam_x & 15));
    }
#else
    np_copper[NP_COP_JUEGO + 1] = (uint16_t)(((w->cam_x & 15) << 4) | (w->cam_x & 15));
#endif

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

uint16_t np_input_read(void)
{
    uint16_t joy = JOY1DAT;
    uint16_t salida = 0;
    /* el joystick es de cuadratura: arriba y abajo salen de un xor */
    uint8_t abajo = (uint8_t)((joy >> 1) & 1) ^ (uint8_t)(joy & 1);
    uint8_t arriba = (uint8_t)((joy >> 9) & 1) ^ (uint8_t)((joy >> 8) & 1);

    if (joy & 0x0002) salida |= NP_IN_RIGHT;
    if (joy & 0x0200) salida |= NP_IN_LEFT;
    if (abajo) salida |= NP_IN_DOWN;
    if (arriba) salida |= NP_IN_UP;
    if (!(CIAA_PRA & 0x80)) salida |= NP_IN_JUMP;      /* boton del joystick */
    /* start: el segundo boton del joystick o, si no lo tiene, el del raton */
    if (!(POTGOR & 0x4000) || !(CIAA_PRA & 0x40)) salida |= NP_IN_START;
    return salida;
}
