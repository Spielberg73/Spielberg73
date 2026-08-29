/* np_video.c - video del Sharp X68000: capas BG y sprites del chip CYNTHIA.
 *
 * Es la maquina mas comoda de las seis para este motor, y por una razon: los
 * tiles del PCG son de **16x16**, exactamente el tamano de tile de NeoPlat.
 * En la Mega Drive hay que partir cada tile en cuatro de 8x8 y en la Neo Geo el
 * escenario se dibuja con columnas de sprites; aqui una casilla del nivel es
 * una casilla de la tabla de nombres y se acabo.
 *
 * El reparto:
 *
 *   BG0      el escenario, con scroll por hardware
 *   BG1      la capa de parallax
 *   sprites  los actores (jugadores, enemigos, objetos, disparos)
 *   texto    el marcador (np_hud.c), que asi no gasta ni un patron de PCG
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

static void np_limpiar_capas(void)
{
    uint16_t i;
    for (i = 0; i < NP_BG_COLUMNAS * NP_BG_FILAS; i++) {
        NP_BG0_MAPA[i] = 0;
        NP_BG1_MAPA[i] = 0;
    }
}

void np_video_init(void)
{
    /* CRTC: los valores son los del modo de 256 lineas a 31 kHz, con la zona
       visible recortada a lo que dibujamos. El X68000 deja programar el
       temporizado entero, asi que se le pide justo NP_ANCHO x NP_ALTO en vez de
       aceptar un modo de catalogo y desperdiciar media pantalla. */
    *NP_CRTC_R00 = 0x0037;
    *NP_CRTC_R01 = 0x0005;
    *NP_CRTC_R02 = 0x0007;
    *NP_CRTC_R03 = (uint16_t)(0x0007 + NP_ANCHO / 8);
    *NP_CRTC_R04 = 0x0103;
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
    np_limpiar_capas();
    np_limpiar_sprites();

    /* El sistema de sprites lleva su propio temporizado, aparte del CRTC. */
    *NP_BG_HTOTAL = 0x0037;
    *NP_BG_HDISP  = 0x000A;
    *NP_BG_VDISP  = 0x0010;
    *NP_BG_RES    = 0x0000;      /* casillas de 16x16, 512 puntos */
    *NP_BG_CTRL   = NP_BG_DISP | NP_BG0_ON | NP_BG1_ON;
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
    np_tile_gfx_column(nivel, tile_x, 0, (uint16_t)alto, patrones);
    for (fila = 0; fila < alto; fila++)
        NP_BG0_MAPA[fila * NP_BG_COLUMNAS + columna] =
            NP_CASILLA(patrones[fila], np_tileset_palette);
    for (; fila < NP_BG_FILAS; fila++)
        NP_BG0_MAPA[fila * NP_BG_COLUMNAS + columna] = 0;
}

/* La capa de parallax se pinta una vez y luego solo se mueve: se repite sola
   porque la tabla de nombres da la vuelta cada 64 casillas. */
static void np_pintar_parallax(const NpWorld *w)
{
#if NP_LAYER_COUNT > 0
    uint16_t columna;
    uint16_t fila;
    if (w->level->layer_count == 0) {
        for (fila = 0; fila < NP_BG_COLUMNAS * NP_BG_FILAS; fila++)
            NP_BG1_MAPA[fila] = 0;
        return;
    }
    {
        const NpLayer *capa = &np_layers[w->level->layers[0]];
        for (columna = 0; columna < NP_BG_COLUMNAS; columna++) {
            uint16_t origen_x = (uint16_t)(columna % capa->cols);
            for (fila = 0; fila < NP_BG_FILAS; fila++) {
                uint16_t casilla = 0;
                if (fila < capa->rows)
                    casilla = NP_CASILLA(capa->tiles[fila * capa->cols + origen_x],
                                         capa->palette);
                NP_BG1_MAPA[fila * NP_BG_COLUMNAS + columna] = casilla;
            }
        }
    }
#else
    (void)w;
#endif
}

static void np_scroll(const NpWorld *w)
{
    /* El scroll de estas capas es "donde empieza a leerse el mapa", asi que va
       con el mismo signo que la camara, al reves que en la Mega Drive. */
    int16_t x = (int16_t)w->cam_x;
    int16_t y = (int16_t)w->cam_y;
    *NP_BG0_X = (uint16_t)x;
    *NP_BG0_Y = (uint16_t)y;
#if NP_LAYER_COUNT > 0
    if (w->level->layer_count) {
        const NpLayer *capa = &np_layers[w->level->layers[0]];
        *NP_BG1_X = (uint16_t)(int16_t)((w->cam_x * capa->speed_x) >> 8);
        *NP_BG1_Y = (uint16_t)(int16_t)((w->cam_y * capa->speed_y) >> 8);
        return;
    }
#endif
    *NP_BG1_X = (uint16_t)x;
    *NP_BG1_Y = (uint16_t)y;
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

/* --- un frame ----------------------------------------------------------- */

void np_video_frame(const NpWorld *w)
{
    static int32_t ultima_columna = -9999;
    static const NpLevel *ultimo_nivel = 0;
    int32_t columna = w->cam_x >> 4;
    uint8_t i;

    if (w->level != ultimo_nivel) {
        int32_t c;
        ultimo_nivel = w->level;
        ultima_columna = columna;
        /* por donde no hay capa ni sprite se ve el color 0 de la paleta
           grafica, asi que ese es el fondo del nivel */
        NP_PALETA_GFX[0] = w->level->background;
        np_pintar_parallax(w);
        for (c = columna - 1; c <= columna + NP_COLUMNAS + 1; c++)
            np_columna_escenario(w, c);
    } else {
        while (ultima_columna < columna) {          /* avanzando a la derecha */
            ultima_columna++;
            np_columna_escenario(w, ultima_columna + NP_COLUMNAS);
        }
        while (ultima_columna > columna) {          /* hacia atras */
            ultima_columna--;
            np_columna_escenario(w, ultima_columna - 1);
        }
    }

    np_scroll(w);

    np_sprite_siguiente = 0;
    for (i = 0; i < w->entity_count; i++) {
        const NpEntity *e = &w->entities[i];
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
