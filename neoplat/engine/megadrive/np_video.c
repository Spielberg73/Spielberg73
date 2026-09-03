/* np_video.c - dibujado del juego en la Mega Drive.
 *
 * El escenario va en el plano A y la capa de parallax en el plano B, los dos
 * con scroll por hardware. Como un plano son 64x64 celdas (512x512 pixeles) y
 * los niveles son mas largos, el escenario se va reescribiendo por columnas
 * segun avanza la camara: solo la columna que entra por el borde.
 */

#include "np_md.h"

void np_md_reg(uint8_t registro, uint8_t valor)
{
    *MD_VDP_CTRL = (uint16_t)(0x8000 | (registro << 8) | valor);
}

void np_md_vram_addr(uint32_t direccion)
{
    *MD_VDP_CTRL32 = direccion;
}

static void np_celda(uint16_t plano, uint16_t columna, uint16_t fila, uint16_t celda)
{
    uint16_t direccion = (uint16_t)(plano + ((fila & (MD_PLANE_H - 1)) * MD_PLANE_W
                                             + (columna & (MD_PLANE_W - 1))) * 2);
    np_md_vram_addr(MD_ADDR(MD_VRAM_WRITE, direccion));
    *MD_VDP_DATA = celda;
}

/* --- arranque ---------------------------------------------------------- */

static void np_subir_paletas(void)
{
    uint16_t i, j;
    np_md_vram_addr(MD_ADDR(MD_CRAM_WRITE, 0));
    for (i = 0; i < 4; i++)
        for (j = 0; j < 16; j++)
            *MD_VDP_DATA = np_palettes[i][j];
}

/* El color 0 de la primera paleta es el fondo de la pantalla; cada nivel puede
   traer el suyo. */
static void np_color_de_fondo(uint16_t color)
{
    np_md_vram_addr(MD_ADDR(MD_CRAM_WRITE, 0));
    *MD_VDP_DATA = color;
}

static void np_subir_tiles(void)
{
    uint32_t i;
    np_md_vram_addr(MD_ADDR(MD_VRAM_WRITE, MD_TILES));
    for (i = 0; i < NP_TILE_WORDS; i++) *MD_VDP_DATA = np_tile_data[i];
}

void np_md_init(void)
{
    uint16_t i;

    /* La Mega Drive de segunda generacion pide esta contrasena antes de dejar
     * tocar el VDP. En las de primera no hace dano. */
    if (*MD_VERSION & 0x0F) *MD_TMSS = 0x53454741UL;   /* "SEGA" */

    /* El Z80 lo arranca np_sound_init: las notas las toca el 68000 por el PSG,
     * pero las muestras digitales las lleva el Z80 (ver np_sound.c). Aqui se
     * deja quieto, con el bus pedido y sin reset. */
    *MD_Z80_BUS = 0x0100;
    *MD_Z80_RESET = 0x0100;

    np_md_reg(0x00, 0x04);      /* modo 1: sin interrupcion de linea */
    np_md_reg(0x01, 0x74);      /* modo 2: pantalla y vblank encendidos, 224 lineas */
    np_md_reg(0x02, MD_PLANE_A >> 10);
    np_md_reg(0x03, MD_WINDOW >> 10);
    np_md_reg(0x04, MD_PLANE_B >> 13);
    np_md_reg(0x05, MD_SPRITES >> 9);
    np_md_reg(0x07, 0x00);      /* color del borde */
    np_md_reg(0x0A, 0xFF);
    np_md_reg(0x0B, 0x00);      /* scroll de pantalla completa */
    np_md_reg(0x0C, 0x81);      /* 40 celdas de ancho (320 px) */
    np_md_reg(0x0D, MD_HSCROLL >> 10);
    np_md_reg(0x0F, 0x02);      /* avanzar de dos en dos bytes */
    np_md_reg(0x10, 0x11);      /* planos de 64x64 celdas */
    np_md_reg(0x11, 0x00);      /* la ventana no ocupa nada a lo ancho... */
    np_md_reg(0x12, 0x03);      /* ...pero si las tres primeras filas */

    /* VRAM a cero */
    np_md_vram_addr(MD_ADDR(MD_VRAM_WRITE, 0));
    for (i = 0; i < 0x8000; i++) *MD_VDP_DATA = 0;

    np_subir_paletas();
    np_subir_tiles();
    np_hud_clear();
}

/* --- fondo ------------------------------------------------------------- */

/* Escribe una columna del escenario (dos celdas por tile del nivel).
 *
 * Los tiles se piden de una vez: asi hay una multiplicacion de 32 bits por
 * columna y no una por tile, que en un 68000 son llamadas a np_aritmetica.c. */
static void np_columna_escenario(const NpWorld *w, int32_t tile_x)
{
    const NpLevel *nivel = w->level;
    uint16_t tiles[MD_PLANE_H / 2];
    uint16_t columna = (uint16_t)((tile_x * 2) & (MD_PLANE_W - 1));
    int32_t alto = (int32_t)nivel->height;
    int32_t fila;
    if (alto > MD_PLANE_H / 2) alto = MD_PLANE_H / 2;
    np_tile_gfx_column(w, tile_x, 0, (uint16_t)alto, tiles);
    for (fila = 0; fila < alto; fila++) {
        uint16_t base = tiles[fila];
        uint16_t paleta = np_tileset_palette;
        /* un tile de 16x16 son cuatro de 8x8, guardados por columnas */
        np_celda(MD_PLANE_A, columna, (uint16_t)(fila * 2), MD_CELDA(base + 0, paleta, 0));
        np_celda(MD_PLANE_A, columna, (uint16_t)(fila * 2 + 1), MD_CELDA(base + 1, paleta, 0));
        np_celda(MD_PLANE_A, columna + 1, (uint16_t)(fila * 2), MD_CELDA(base + 2, paleta, 0));
        np_celda(MD_PLANE_A, columna + 1, (uint16_t)(fila * 2 + 1), MD_CELDA(base + 3, paleta, 0));
    }
}

/* La capa de parallax se pinta una vez y se repite: luego solo se mueve. */
static void np_pintar_parallax(const NpWorld *w)
{
    uint16_t columna, fila;
#if NP_LAYER_COUNT > 0
    if (w->level->layer_count == 0) return;
    {
        const NpLayer *capa = &np_layers[w->level->layers[0]];
        for (columna = 0; columna < MD_PLANE_W; columna++) {
            uint16_t origenX = (uint16_t)((columna / 2) % capa->cols);
            for (fila = 0; fila < MD_PLANE_H; fila++) {
                uint16_t celda = 0;
                uint16_t origenY = (uint16_t)(fila / 2);
                if (origenY < capa->rows) {
                    uint16_t base = capa->tiles[origenY * capa->cols + origenX];
                    uint16_t trozo = (uint16_t)((columna & 1) * 2 + (fila & 1));
                    celda = MD_CELDA(base + trozo, capa->palette, 0);
                }
                np_celda(MD_PLANE_B, columna, fila, celda);
            }
        }
    }
#else
    (void)w; (void)columna; (void)fila;
#endif
}

static void np_scroll(const NpWorld *w)
{
    int16_t scroll_a = (int16_t)(-w->cam_x);
    int16_t scroll_b = scroll_a;
#if NP_LAYER_COUNT > 0
    if (w->level->layer_count)
        scroll_b = (int16_t)(-((w->cam_x * np_layers[w->level->layers[0]].speed_x) >> 8));
#endif
    np_md_vram_addr(MD_ADDR(MD_VRAM_WRITE, MD_HSCROLL));
    *MD_VDP_DATA = (uint16_t)scroll_a;
    *MD_VDP_DATA = (uint16_t)scroll_b;
    np_md_vram_addr(MD_ADDR(MD_VSRAM_WRITE, 0));
    *MD_VDP_DATA = (uint16_t)w->cam_y;
    *MD_VDP_DATA = 0;                     /* la capa de fondo no sube ni baja */
}

/* --- sprites ----------------------------------------------------------- */

#define MD_MAX_SPRITES 80

static uint16_t np_sprites[MD_MAX_SPRITES * 4];
static uint8_t np_sprite_count;

static void np_sprite(int16_t x, int16_t y, uint8_t ancho, uint8_t alto,
                      uint16_t tile, uint8_t paleta, uint8_t flip)
{
    uint16_t *entrada;
    if (np_sprite_count >= MD_MAX_SPRITES) return;
    entrada = &np_sprites[np_sprite_count * 4];
    entrada[0] = (uint16_t)(y + 128);
    entrada[1] = (uint16_t)((((ancho - 1) & 3) << 10) | (((alto - 1) & 3) << 8)
                            | ((np_sprite_count + 1) & 0x7F));
    entrada[2] = (uint16_t)((1 << 15) | (paleta << 13) | (flip ? (1 << 11) : 0)
                            | (tile & 0x07FF));
    entrada[3] = (uint16_t)(x + 128);
    np_sprite_count++;
}

static void np_volcar_sprites(void)
{
    uint16_t i;
    if (np_sprite_count == 0) {          /* uno vacio para cortar la lista */
        np_sprites[0] = 0;
        np_sprites[1] = 0;
        np_sprites[2] = 0;
        np_sprites[3] = 0;
        np_sprite_count = 1;
    } else {
        np_sprites[(np_sprite_count - 1) * 4 + 1] &= 0xFF00;   /* enlace = 0: fin */
    }
    np_md_vram_addr(MD_ADDR(MD_VRAM_WRITE, MD_SPRITES));
    for (i = 0; i < np_sprite_count * 4; i++) *MD_VDP_DATA = np_sprites[i];
    np_sprite_count = 0;
}

static void np_dibujar_actor(const NpActorDef *def, int32_t x, int32_t y,
                             uint8_t frame, uint8_t flip)
{
    uint16_t base = (uint16_t)(def->first_tile + frame * def->cols * def->rows * 4);
    uint8_t c;
    for (c = 0; c < def->cols; c++) {
        uint8_t origen = flip ? (uint8_t)(def->cols - 1 - c) : c;
        int32_t px = x + c * 16;
        if (px <= -16 || px >= NP_SCREEN_W) continue;
        np_sprite((int16_t)px, (int16_t)y, 2, (uint8_t)(def->rows * 2),
                  (uint16_t)(base + origen * def->rows * 4), def->palette, flip);
    }
}

/* --- un frame ---------------------------------------------------------- */

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
        np_color_de_fondo(w->level->background);
        np_pintar_parallax(w);
        for (c = columna - 1; c <= columna + MD_CELDAS_X / 2 + 1; c++)
            np_columna_escenario(w, c);
    } else {
        while (ultima_columna < columna) {          /* avanzando a la derecha */
            ultima_columna++;
            np_columna_escenario(w, ultima_columna + MD_CELDAS_X / 2);
        }
        while (ultima_columna > columna) {          /* hacia atras */
            ultima_columna--;
            np_columna_escenario(w, ultima_columna - 1);
        }
    }

    np_scroll(w);

    /* De mas lejos a mas cerca: en la vista de cinta los actores se pisan a
       cada rato y hay que pintarlos por la linea del suelo. En las demas
       vistas np_orden_dibujo devuelve el orden de la lista tal cual. */
    orden = np_orden_dibujo(w, &cuantas);
    for (i = 0; i < cuantas; i++) {
        const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
        const NpActorDef *def;
        int32_t sx, sy;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;
        def = np_entity_def(e);
        sx = NP_F2I(e->x) - def->box_x - w->cam_x;
        sy = NP_F2I(e->y) - def->box_y - w->cam_y;
        if (sx <= -(def->cols * 16) || sx >= NP_SCREEN_W) continue;
        if (sy <= -(def->rows * 16) || sy >= NP_SCREEN_H) continue;
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

    np_volcar_sprites();

#if NP_HUD_ENABLED
    np_hud_draw(w);
#endif
}

/* --- sincronizacion y mando -------------------------------------------- */

void np_wait_vblank(void)
{
    while (*MD_VDP_CTRL & 0x0008) ;      /* si ya estamos en vblank, esperar a salir */
    while (!(*MD_VDP_CTRL & 0x0008)) ;   /* y entrar en el siguiente */
}

/* Los dos mandos se leen igual: se sube TH para la cruceta, B y C, se baja
   para start y A, y se vuelve a subir. Solo cambian los puertos. */
static uint16_t np_input_de(volatile uint8_t *datos, volatile uint8_t *control)
{
    uint8_t primera, segunda;
    uint16_t salida = 0;

    *control = 0x40;
    *datos = 0x40;                       /* TH alto: C, B y la cruceta */
    __asm__ volatile ("nop\n\tnop");
    primera = (uint8_t)~(*datos);
    *datos = 0x00;                       /* TH bajo: start y A */
    __asm__ volatile ("nop\n\tnop");
    segunda = (uint8_t)~(*datos);
    *datos = 0x40;

    if (primera & 0x01) salida |= NP_IN_UP;
    if (primera & 0x02) salida |= NP_IN_DOWN;
    if (primera & 0x04) salida |= NP_IN_LEFT;
    if (primera & 0x08) salida |= NP_IN_RIGHT;
    if (primera & 0x10) salida |= NP_IN_JUMP;      /* boton B */
    if (primera & 0x20) salida |= NP_IN_ACTION;    /* boton C */
    if (segunda & 0x10) salida |= NP_IN_JUMP;      /* boton A tambien salta */
    if (segunda & 0x20) salida |= NP_IN_START;
    return salida;
}

uint16_t np_input_read(void)
{
    return np_input_de(MD_PAD1_DATA, MD_PAD1_CTRL);
}

uint16_t np_input_read2(void)
{
    return np_input_de(MD_PAD2_DATA, MD_PAD2_CTRL);
}
