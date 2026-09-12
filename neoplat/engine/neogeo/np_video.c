/* np_video.c - dibujado del juego en la Neo Geo. */

#include "np_video.h"

void np_vram_seek(uint16_t address, int16_t modulo)
{
    *NP_REG_VRAMADDR = address;
    *NP_REG_VRAMMOD = (uint16_t)modulo;
}

void np_vram_write(uint16_t value)
{
    *NP_REG_VRAMRW = value;
}

/* Espera al retrazo vertical leyendo el contador de linea del LSPC.
 * (Si prefieres la interrupcion de ngdevkit, sustituye esta funcion por
 *  ng_wait_vblank(); el resto del motor no cambia.) */
void np_wait_vblank(void)
{
    while ((*NP_REG_LSPCMODE >> 7) >= 0xF0)  /* si ya estamos en vblank, salimos */
        ;
    while ((*NP_REG_LSPCMODE >> 7) < 0xF0)
        ;
}

/* El mando de Neo Geo es activo a nivel bajo. */
/* Los dos mandos son iguales: cambia el registro de la cruceta y que bits de
   STATUS_B llevan su START (los de P1 son el 0 y el 1, y los de P2 el 2 y el
   3). Todo activo a nivel bajo, de ahi el complemento. */
static uint16_t np_input_de(volatile uint8_t *cnt, uint8_t start)
{
    uint8_t pad = (uint8_t)~(*cnt);
    uint8_t sys = (uint8_t)~(*NP_REG_STATUS_B);
    uint16_t out = 0;
    if (pad & 0x01) out |= NP_IN_UP;
    if (pad & 0x02) out |= NP_IN_DOWN;
    if (pad & 0x04) out |= NP_IN_LEFT;
    if (pad & 0x08) out |= NP_IN_RIGHT;
    if (pad & 0x10) out |= NP_IN_JUMP;      /* boton A */
    if (pad & 0x20) out |= NP_IN_ACTION;    /* boton B */
    if (sys & start) out |= NP_IN_START;    /* START o SELECT, los dos valen */
    return out;
}

uint16_t np_input_read(void)
{
    return np_input_de(NP_REG_P1CNT, 0x03);
}

uint16_t np_input_read2(void)
{
    return np_input_de(NP_REG_P2CNT, 0x0C);
}

/* La posicion de un sprite son dos palabras que estan a 0x200 de distancia
 * (SCB3 = 0x8200, SCB4 = 0x8400). Poniendo ese 0x200 como modulo, el propio
 * chip salta de una a otra y basta con dar la direccion una vez: tres
 * escrituras en vez de seis, y esta es la funcion que mas se llama de todas. */
static void np_sprite_pos(uint16_t sprite, int16_t x, int16_t y, uint8_t height)
{
    np_vram_seek((uint16_t)(NP_SCB3 + sprite), 0x200);
    np_vram_write((uint16_t)((((496 - y) & 0x1FF) << 7) | (height & 0x3F)));
    np_vram_write((uint16_t)((x & 0x1FF) << 7));
}

static void np_sprite_hide(uint16_t sprite)
{
    np_vram_seek((uint16_t)(NP_SCB3 + sprite), 0);
    np_vram_write(0);            /* altura 0 = sprite apagado */
}

static void np_sprite_zoom_full(uint16_t sprite)
{
    np_vram_seek((uint16_t)(NP_SCB2 + sprite), 0);
    np_vram_write(0x0FFF);       /* sin reduccion */
}

void np_video_init(void)
{
    uint16_t i, j;

    /* Paletas: se copian tal cual a la RAM de color. */
    for (i = 0; i < NP_PALETTE_COUNT; i++)
        for (j = 0; j < 16; j++)
            NP_PALETTE_RAM[i * 16 + j] = np_palettes[i][j];
    *NP_BACKDROP = 0x0000;

    /* Plano fix en blanco y todos los sprites apagados. */
    np_hud_clear();
    for (i = 0; i < NP_TOTAL_SPRITES; i++) {
        np_sprite_zoom_full(i);
        np_sprite_hide(i);
    }
}

/* Rellena el tilemap de una columna del fondo. */
static void np_bg_column(const NpWorld *w, uint16_t column, int32_t tile_x, int32_t tile_y)
{
    uint16_t sprite = (uint16_t)(NP_BG_FIRST_SPRITE + column);
    uint16_t tiles[NP_BG_ROWS];
    uint16_t atributos = (uint16_t)(np_tileset_palette << 8);
    uint16_t row;
    np_tile_gfx_column(w, tile_x, tile_y, NP_BG_ROWS, tiles);
    np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
    for (row = 0; row < NP_BG_ROWS; row++) {
        np_vram_write(tiles[row]);              /* numero de tile */
        np_vram_write(atributos);               /* paleta y atributos */
    }
}

/* Dibuja una capa de parallax. La capa se repite horizontalmente y se mueve a
 * una fraccion de la camara: eso es todo el efecto.
 *
 * Igual que el fondo, las columnas van en un anillo: la columna N de la capa
 * cae siempre en el sprite N mod 21, asi que al avanzar la camara solo se
 * rellena el tilemap de la que entra por el borde. */
#define NP_SIN_CARGAR ((int32_t)-0x7FFFFFFF)

/* lo pone np_draw_layers cuando cambia el nivel: hay que rehacerlo todo */
static uint8_t np_capas_todas = 1;

static void np_draw_layer(const NpWorld *w, uint8_t layer_index, uint8_t slot)
{
#if NP_LAYER_COUNT > 0
    static int32_t cargada[NP_LAYER_COUNT][NP_LAYER_COLUMNS];
    static uint8_t last_layer[NP_LAYER_COUNT];
    static int32_t ultimo_x[NP_LAYER_COUNT], ultimo_y[NP_LAYER_COUNT];
    static uint8_t primera_vez = 1;
    const NpLayer *layer = &np_layers[layer_index];
    int32_t scroll_x = ((int32_t)w->cam_x * layer->speed_x) >> 8;
    int32_t scroll_y = ((int32_t)w->cam_y * layer->speed_y) >> 8;
    int32_t col0 = scroll_x >> NP_TILE_SHIFT;
    int16_t off_x = (int16_t)(scroll_x & 15);
    int16_t y = (int16_t)(layer->offset_y - scroll_y);
    uint16_t base = (uint16_t)NP_LAYER_FIRST_SPRITE(slot);
    uint16_t ranura;
    int32_t mapa = col0, col = col0, resto;
    uint8_t todas, i, r;

    if (primera_vez) {
        for (i = 0; i < NP_LAYER_COUNT; i++) {
            last_layer[i] = 0xFF;
            for (r = 0; r < NP_LAYER_COLUMNS; r++) cargada[i][r] = NP_SIN_CARGAR;
        }
        primera_vez = 0;
    }
    todas = np_capas_todas || (layer_index != last_layer[slot]);
    last_layer[slot] = layer_index;

    /* Una capa lenta (velocidad 0.2) se mueve un pixel cada cinco de camara:
       los otros cuatro frames no hay nada que escribir, y son veintiuna
       posiciones de sprite por capa. Medido en el banco: las dos capas del
       ejemplo costaban 40.000 de los 132.000 ciclos del frame. */
    if (!todas && scroll_x == ultimo_x[slot] && scroll_y == ultimo_y[slot])
        return;
    ultimo_x[slot] = scroll_x;
    ultimo_y[slot] = scroll_y;

    /* Una sola division por capa y frame: dentro del bucle basta con sumar. */
    resto = col0 % NP_LAYER_COLUMNS;
    ranura = (uint16_t)(resto < 0 ? resto + NP_LAYER_COLUMNS : resto);
    if (layer->repeat) {
        col %= layer->cols;
        if (col < 0) col += layer->cols;
    }

    for (i = 0; i < NP_LAYER_COLUMNS; i++) {
        uint16_t sprite = (uint16_t)(base + ranura);
        if (!layer->repeat && (mapa < 0 || mapa >= layer->cols)) {
            cargada[slot][ranura] = NP_SIN_CARGAR;
            np_sprite_hide(sprite);
        } else {
            if (todas || cargada[slot][ranura] != col) {
                np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
                for (r = 0; r < layer->rows; r++) {
                    np_vram_write(layer->tiles[r * layer->cols + col]);
                    np_vram_write((uint16_t)(layer->palette << 8));
                }
                cargada[slot][ranura] = col;
            }
            np_sprite_pos(sprite, (int16_t)(i * 16 - off_x), y, layer->rows);
        }
        mapa++;
        if (layer->repeat) {
            if (++col >= layer->cols) col = 0;
        } else {
            col = mapa;
        }
        if (++ranura == NP_LAYER_COLUMNS) ranura = 0;
    }
#else
    (void)w; (void)layer_index; (void)slot;
#endif
}

static void np_draw_layers(const NpWorld *w)
{
#if NP_LAYER_COUNT > 0
    static const NpLevel *ultimo_nivel = 0;
    uint8_t slot;
    /* al cambiar de nivel las capas pueden ser otras, o ninguna: lo que
       hubiera dibujado antes no vale */
    if (w->level != ultimo_nivel) {
        np_capas_todas = 1;
        ultimo_nivel = w->level;
    }
    for (slot = 0; slot < NP_LAYER_COUNT; slot++) {
        if (slot < w->level->layer_count) {
            np_draw_layer(w, w->level->layers[slot], slot);
        } else {
            uint16_t base = (uint16_t)NP_LAYER_FIRST_SPRITE(slot);
            uint8_t i;
            for (i = 0; i < NP_LAYER_COLUMNS; i++)
                np_sprite_hide((uint16_t)(base + i));
        }
    }
    np_capas_todas = 0;
#else
    (void)w;
#endif
}

/* El reparto de columnas es circular: la columna N del mapa cae siempre en el
 * sprite N mod 21. Asi, cuando la camara avanza un tile, veinte de las
 * veintiuna columnas ya estan donde tienen que estar y solo hay que rellenar
 * el tilemap de la que acaba de entrar por el borde: 30 escrituras en la VRAM
 * en vez de 630. Antes de esto la consola bajaba a 29 fps cada 16 pixeles de
 * scroll (medido con tests/maquina_neogeo.py).
 *
 * Con la camara por pantallas la cuenta cambia: la vista salta veinte columnas
 * de golpe y esas veinte no caben en un frame (medido: 214.558 ciclos de los
 * 200.000 que da la consola). Asi que se rellenan NP_BG_POR_FRAME por frame y
 * las que aun no valen se apagan, que es preferible a ensenar los tiles de la
 * pantalla anterior en el sitio equivocado. Se ve como un barrido de un par de
 * frames, que es justo lo que hacian los juegos de pantalla a pantalla. */
#define NP_BG_POR_FRAME 10
static void np_draw_background(const NpWorld *w)
{
    static int32_t cargada[NP_BG_COLUMNS];
    static int32_t last_row = -9999;
    static const NpLevel *last_level = 0;
    /* cuantas puertas habia abiertas al pintar: al abrirse una, la casilla
       pasa a ser aire y hay que rehacer las columnas */
    static uint8_t ultimos_abiertos = 0;
    static uint8_t primera_vez = 1;
    int32_t col = w->cam_x >> NP_TILE_SHIFT;
    int32_t row = w->cam_y >> NP_TILE_SHIFT;
    int16_t off_x = (int16_t)(w->cam_x & 15);
    int16_t off_y = (int16_t)(w->cam_y & 15);
    /* Si cambia la fila (o el nivel) no vale nada de lo que hay: al moverse en
     * vertical cambian los quince tiles de todas las columnas. */
    uint8_t todas = primera_vez || row != last_row || w->level != last_level
                  || w->abiertos_n != ultimos_abiertos;
    /* La camara nunca sale del nivel, pero un resto negativo aqui se saldria
     * del array: mas vale gastar una comparacion al frame. */
    int32_t resto = col % NP_BG_COLUMNS;
    uint16_t ranura = (uint16_t)(resto < 0 ? resto + NP_BG_COLUMNS : resto);
    uint16_t presupuesto = NP_BG_POR_FRAME;
    uint16_t i;

    primera_vez = 0;
    last_row = row;
    last_level = w->level;
    ultimos_abiertos = w->abiertos_n;

    for (i = 0; i < NP_BG_COLUMNS; i++) {
        int32_t mapa = col + i;
        uint8_t lista = 1;
        if (todas || cargada[ranura] != mapa) {
            /* al moverse en vertical hay que rehacerlas todas si o si: ahi no
               hay columna que dejar para luego sin que se vea el hueco */
            if (todas || presupuesto) {
                np_bg_column(w, ranura, mapa, row);
                cargada[ranura] = mapa;
                if (presupuesto) presupuesto--;
            } else {
                lista = 0;
            }
        }
        if (lista) {
            np_sprite_pos((uint16_t)(NP_BG_FIRST_SPRITE + ranura),
                          (int16_t)(i * 16 - off_x), (int16_t)(-off_y), NP_BG_ROWS);
        } else {
            np_sprite_hide((uint16_t)(NP_BG_FIRST_SPRITE + ranura));
        }
        if (++ranura == NP_BG_COLUMNS) ranura = 0;
    }
}

#if NP_VISTA_CARRETERA
/* --- la carretera, en bandas -------------------------------------------
 *
 * Esta es la unica de las ocho maquinas que no tiene **nada** con lo que
 * deslizar una imagen linea a linea: no hay plano que correr (la Mega Drive y
 * el X68000), ni copper que lo cambie en mitad de la pantalla (el Amiga), ni
 * lista de objetos por linea (la Jaguar). Aqui todo son sprites, y un sprite
 * de Neo Geo es **una columna**: justo lo contrario de lo que hace falta.
 *
 * Asi que la carretera va en bandas. La imagen es la misma que se lleva la
 * Mega Drive -la calzada en perspectiva, 512 de ancho, con las cuatro franjas
 * dibujadas dentro- y se reparte en filas de veintiuna columnas de sprite, una
 * fila cada 16 lineas. Cada banda se corre lo que diga la proyeccion en su
 * linea de en medio. Es el scroll por linea de la Mega Drive redondeado a
 * dieciseis, y la curva cambia tan poco de una linea a la siguiente que la
 * escalera no se ve.
 *
 * Las columnas van en anillo, igual que en el fondo y en las capas: la columna
 * N de la imagen cae siempre en el sprite N mod 21, asi que cuando una banda
 * se corre un tile solo hay que rehacer el tilemap de la que entra por el
 * borde. Sin eso son 294 tilemaps por frame y la consola no llega.
 *
 * Y las franjas que corren hacia ti no se dibujan: son cuatro huecos de
 * paleta por cosa, rotados un paso por frame. Doce palabras a la RAM de color.
 */

/* La imagen tiene el eje de la calzada en su columna NP_CARRETERA_EJE; si en
   la linea `y` el eje tiene que caer en la columna `centro`, la imagen se
   corre centro - EJE. La misma cuenta que hace la Mega Drive. */
static int16_t np_centro_de_linea[NP_SCREEN_H];
static uint8_t np_bandas_todas = 1;       /* al entrar en el nivel, todas */
static const NpLevel *np_ultimo_nivel;

/* Cuantas cosas de la calzada se dibujan a la vez, las mas cercanas. Con el
   circuito del andamiaje se ven dos coches de media, no sesenta. */
#define NP_CARRETERA_A_LA_VEZ 12

/* Los tres numeros caben de sobra en dieciseis bits, y asi la estructura son
   ocho bytes: con int32_t gcc copia la estructura llamando a memcpy, y aqui no
   hay biblioteca de C que lo tenga. */
typedef struct {
    int16_t sx, sy, escala;
    uint8_t entidad;
} NpEnLaVia;

static void np_paleta_carretera(uint8_t fase)
{
    const uint8_t *huecos = np_carretera_huecos;
    uint8_t pal = np_layers[np_carretera_capa].palette;
    const uint16_t *paleta = np_palettes[pal];
    uint8_t grupo, i;
    for (grupo = 0; grupo < NP_CARRETERA_GRUPOS; grupo++) {
        const uint8_t *cuatro = &huecos[grupo * NP_CARRETERA_FRANJAS];
        for (i = 0; i < NP_CARRETERA_FRANJAS; i++)
            NP_PALETTE_RAM[pal * 16 + cuatro[i]] =
                paleta[cuatro[(i + fase) & (NP_CARRETERA_FRANJAS - 1)]];
    }
}

static void np_banda(uint8_t banda, int16_t desplaza)
{
    /* que columna de la imagen tiene cargada cada ranura de cada banda */
    static int16_t cargada[NP_CARRETERA_BANDAS][NP_LAYER_COLUMNS];
    static int16_t ultimo[NP_CARRETERA_BANDAS];
    const NpLayer *capa = &np_layers[np_carretera_capa];
    uint16_t base = (uint16_t)(NP_CARRETERA_FIRST_SPRITE
                               + (uint16_t)banda * NP_LAYER_COLUMNS);
    int32_t fuera = -(int32_t)desplaza;   /* lo que se sale por la izquierda */
    int32_t primera = fuera >> 4;         /* el >> de un negativo baja: vale */
    int16_t off = (int16_t)(fuera & 15);
    int32_t resto = primera % NP_LAYER_COLUMNS;
    uint16_t ranura0 = (uint16_t)(resto < 0 ? resto + NP_LAYER_COLUMNS : resto);
    int32_t col = primera % capa->cols;
    uint16_t ranura = ranura0;
    uint8_t i;

    if (!np_bandas_todas && ultimo[banda] == desplaza) return;
    ultimo[banda] = desplaza;
    if (col < 0) col += capa->cols;

    /* El tilemap solo se toca cuando la banda se corre un tile entero: las
       columnas van en anillo, asi que de las veintiuna suele cambiar una. */
    for (i = 0; i < NP_LAYER_COLUMNS; i++) {
        if (np_bandas_todas || cargada[banda][ranura] != (int16_t)col) {
            np_vram_seek((uint16_t)(NP_SCB1 + (base + ranura) * 64), 1);
            np_vram_write(capa->tiles[(uint16_t)banda * capa->cols + col]);
            np_vram_write((uint16_t)(capa->palette << 8));
            cargada[banda][ranura] = (int16_t)col;
        }
        if (++col >= capa->cols) col = 0;
        if (++ranura == NP_LAYER_COLUMNS) ranura = 0;
    }

    /* La Y y la altura de una banda **no cambian nunca**, asi que SCB3 se
       escribe una vez al entrar en el nivel y ya no se vuelve a tocar. */
    if (np_bandas_todas) {
        uint16_t alto_y = (uint16_t)(((496 - banda * 16) & 0x1FF) << 7 | 1);
        np_vram_seek((uint16_t)(NP_SCB3 + base), 1);
        for (i = 0; i < NP_LAYER_COLUMNS; i++)
            np_vram_write(alto_y);
    }

    /* Y las X de los veintiun sprites estan **seguidas** en la VRAM (SCB4 +
       numero de sprite), asi que se apunta una vez y se escriben del tiron,
       en orden de sprite y no de pantalla: 23 escrituras por banda en vez de
       las 84 de ir poniendolos uno a uno. Medido en el banco: la carretera
       entera pasa de 215.000 ciclos por frame a caber en los 200.000 que da
       la consola. */
    np_vram_seek((uint16_t)(NP_SCB4 + base), 1);
    for (i = 0; i < NP_LAYER_COLUMNS; i++) {
        int16_t columna = (int16_t)(i + NP_LAYER_COLUMNS - ranura0);
        if (columna >= NP_LAYER_COLUMNS) columna -= NP_LAYER_COLUMNS;
        np_vram_write((uint16_t)(((columna * 16 - off) & 0x1FF) << 7));
    }
}

static void np_dibujar_carretera(const NpWorld *w)
{
    uint16_t horizonte;
    uint8_t banda;
    /* Sin capa de carretera no hay nada que poner: pasa si alguien pide la
       vista de conducir en un juego al que el compilador no le dibujo la
       calzada. Mejor cielo que salirse de np_layers por el -1. */
    if (np_carretera_capa < 0) return;
    horizonte = np_carretera(w, np_centro_de_linea);
    np_paleta_carretera(np_carretera_fase(w));
    for (banda = 0; banda < NP_CARRETERA_BANDAS; banda++) {
        /* la linea de en medio de la banda manda: es la que menos se
           equivoca con las quince de al lado */
        uint16_t linea = (uint16_t)(banda * 16 + 8);
        int16_t desplaza = 0;
        if (linea < NP_SCREEN_H && linea >= horizonte)
            desplaza = (int16_t)(np_centro_de_linea[linea] - NP_CARRETERA_EJE);
        np_banda(banda, desplaza);
    }
    np_bandas_todas = 0;
}

/* --- y el escalador de sprites (SCB2) ----------------------------------
 *
 * Lo que ninguna de las otras siete tiene: la Neo Geo **encoge sprites por
 * hardware**. Cada sprite lleva en SCB2 una palabra con dos numeros, el de
 * arriba de cuatro bits (el ancho: de 1 a 16 pixeles por columna de tile) y el
 * de abajo de ocho (el alto). Es lo que hacen los jefes que se te vienen
 * encima en los juegos de la maquina.
 *
 * El trafico de la carretera se sirve de las dos cosas a la vez: el motor
 * elige el dibujo con np_carretera_dibujo_zoom -que es como el de las otras
 * siete pero al reves: no el mas grande que valga, sino **el mas pequeno que
 * no se quede corto**, para que un coche lejano siga costando un sprite y no
 * cuatro- y el escalador tapa el escalon hasta el tamano exacto. Aqui los
 * coches no crecen a saltos de cinco tamanos: crecen. */
static void np_sprite_zoom(uint16_t sprite, uint8_t ancho, uint16_t alto)
{
    np_vram_seek((uint16_t)(NP_SCB2 + sprite), 0);
    np_vram_write((uint16_t)(((uint16_t)(ancho - 1) << 8) | (alto - 1)));
}

/* Un tamano de la calzada, encogido hasta el que toca de verdad.
 *
 * Se le da el **centro de abajo** del dibujo -que es lo que dice la
 * proyeccion- y lo coloca ya con el encogimiento puesto: si se le pasara la
 * esquina, el que llama tendria que repetir aqui la cuenta del ancho. */
static uint16_t np_bloque_zoom(const NpCarreteraTam *tam, uint16_t sprite,
                               int32_t centro_x, int32_t suelo_y,
                               uint8_t frame, uint16_t zoom)
{
    uint8_t ancho;                        /* pixeles por columna: 1..16 */
    uint16_t alto;                        /* lineas de cada 256: 1..256 */
    uint16_t base;
    int32_t x0, y0;
    uint8_t c, r;
    if (zoom > 256) zoom = 256;           /* el chip encoge, no agranda */
    ancho = (uint8_t)((zoom * 16) >> 8);
    if (!ancho) ancho = 1;
    alto = zoom ? zoom : 1;
    base = (uint16_t)(tam->first_tile + (uint16_t)frame * tam->cols * tam->rows);
    x0 = centro_x - (int32_t)tam->cols * ancho / 2;
    y0 = suelo_y - (int32_t)tam->rows * 16 * alto / 256;
    for (c = 0; c < tam->cols; c++) {
        int32_t x = x0 + (int32_t)c * ancho;
        if (sprite >= NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) break;
        if (x <= -16 || x >= NP_SCREEN_W) {
            np_sprite_hide(sprite);
            sprite++;
            continue;
        }
        np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
        for (r = 0; r < tam->rows; r++) {
            np_vram_write((uint16_t)(base + c * tam->rows + r));
            np_vram_write((uint16_t)(tam->palette << 8));
        }
        np_sprite_zoom(sprite, ancho, alto);
        np_sprite_pos(sprite, (int16_t)x, (int16_t)y0, tam->rows);
        sprite++;
    }
    return sprite;
}

/* El coche del jugador va a tamano natural, asi que lo dibuja np_draw_actor;
   pero el sprite que use puede venir encogido de un frame anterior, y el zoom
   se queda puesto hasta que alguien lo cambie. */
static void np_zoom_entero(uint16_t sprite)
{
    np_vram_seek((uint16_t)(NP_SCB2 + sprite), 0);
    np_vram_write(0x0FFF);
}

#endif /* NP_VISTA_CARRETERA */

/* Dibuja un actor (jugador, enemigo u objeto) usando `cols` sprites. */
static uint16_t np_draw_actor(const NpActorDef *def, uint16_t sprite,
                              int32_t screen_x, int32_t screen_y,
                              uint8_t frame, uint8_t flip)
{
    uint16_t base = (uint16_t)(def->first_tile + frame * def->cols * def->rows);
    uint8_t c, r;
    for (c = 0; c < def->cols; c++) {
        uint8_t source = flip ? (uint8_t)(def->cols - 1 - c) : c;
        int32_t x = screen_x + c * 16;
        if (sprite >= NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) break;
        if (x <= -16 || x >= NP_SCREEN_W) {      /* fuera de pantalla: se apaga */
            np_sprite_hide(sprite);
            sprite++;
            continue;
        }
        np_vram_seek((uint16_t)(NP_SCB1 + sprite * 64), 1);
        for (r = 0; r < def->rows; r++) {
            uint16_t tile = (uint16_t)(base + source * def->rows + r);
            np_vram_write(tile);
            np_vram_write((uint16_t)((def->palette << 8) | (flip ? 0x01 : 0x00)));
        }
        np_sprite_pos(sprite, (int16_t)x, (int16_t)screen_y, def->rows);
        sprite++;
    }
    return sprite;
}

void np_video_frame(const NpWorld *w)
{
    const uint8_t *orden;
    uint8_t cuantas;
    uint16_t sprite = NP_ACTOR_FIRST_SPRITE;
    uint8_t i;

    *NP_BACKDROP = (uint16_t)w->level->background;
#if NP_VISTA_CARRETERA
    /* Conduciendo el escenario **no se dibuja**: el mapa es el trazado de la
       carretera, no lo que se ve. Ni hay capas de parallax: la carretera es
       la unica, y se pone en bandas. */
    if (w->level != np_ultimo_nivel) {
        np_ultimo_nivel = w->level;
        np_bandas_todas = 1;
    }
    np_dibujar_carretera(w);
#else
    np_draw_layers(w);
    np_draw_background(w);
#endif

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
       le toca**, no donde diga el mapa. El motor elige el dibujo -los mismos
       cinco tamanos que en las otras siete- y el escalador de la consola tapa
       el escalon hasta el tamano exacto.

       De mas lejos a mas cerca no vale aqui: en esta maquina el que tapa es
       **el de numero mas bajo**, asi que se dibujan los de cerca primero. Se
       ordena por insercion, que conduciendo el circuito se ven dos coches de
       media y no sesenta. */
    {
        NpEnLaVia visto[NP_CARRETERA_A_LA_VEZ];
        uint8_t vistos = 0, j;
        for (i = 0; i < cuantas; i++) {
            const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
            int32_t sx, sy, escala;
            if (!e->active) continue;
            if (e->hurt && (w->frame & 1)) continue;
            if (!np_carretera_donde(w, e->x, e->y, &sx, &sy, &escala)) continue;
            if (vistos == NP_CARRETERA_A_LA_VEZ) {
                if (escala <= visto[vistos - 1].escala) continue;
                vistos--;
            }
            for (j = vistos; j && visto[j - 1].escala < escala; j--)
                visto[j] = visto[j - 1];
            visto[j].sx = (int16_t)sx;
            visto[j].sy = (int16_t)sy;
            visto[j].escala = (int16_t)escala;
            visto[j].entidad = NP_DIBUJO(orden, i);
            vistos++;
        }
        for (j = 0; j < vistos; j++) {
            const NpEntity *e = &w->entities[visto[j].entidad];
            const NpActorDef *def = np_entity_def(e);
            uint16_t zoom;
            /* El motor elige **el mas pequeno que no se queda corto**, no uno
               de los cinco a ojo: de ahi para abajo lo pone el escalador, y
               asi el coche crece seguido en vez de a saltos. */
            const NpCarreteraTam *tam =
                np_carretera_dibujo_zoom(def, visto[j].escala, &zoom);
            if (!tam) continue;
            sprite = np_bloque_zoom(tam, sprite, visto[j].sx, visto[j].sy,
                                    np_actor_frame(def, e->anim, e->anim_frame),
                                    zoom);
            if (sprite >= NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) break;
        }
    }
    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        int32_t cx, cy;
        if (!np_player_visible(w, i)) continue;
        /* El coche del jugador va en un sitio fijo abajo y a tamano natural:
           la camara le sigue. Sin espejo, que se ve de culo. */
        np_carretera_coche(w, i, &cx, &cy);
        {   /* el sprite puede venir encogido de un frame anterior */
            uint16_t k;
            for (k = 0; k < def->cols; k++) np_zoom_entero(sprite + k);
        }
        sprite = np_draw_actor(def, sprite, cx, cy,
                               np_actor_frame(def, p->anim, p->anim_frame), 0);
        if (sprite >= NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) break;
    }
#elif NP_VISTA_ISO
    for (i = 0; i < cuantas; i++) {
        const NpActorDef *def;
        int32_t sx, sy;
        uint8_t frame, flip;
        def = np_dibujo(w, NP_DIBUJO(orden, i), &sx, &sy, &frame, &flip);
        if (!def) continue;
        sx -= w->cam_x;
        sy -= w->cam_y;
        if (sx <= -(def->cols * 16) || sx >= NP_SCREEN_W) continue;
        if (sy <= -(def->rows * 16) || sy >= NP_SCREEN_H) continue;
        sprite = np_draw_actor(def, sprite, sx, sy, frame, flip);
        if (sprite >= NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) break;
    }
#else
    for (i = 0; i < cuantas; i++) {
        const NpEntity *e = &w->entities[NP_DIBUJO(orden, i)];
        const NpActorDef *def;
        int32_t sx, sy;
        if (!e->active) continue;
        if (e->hurt && (w->frame & 1)) continue;        /* parpadeo al recibir */
        def = np_entity_def(e);
        sx = NP_F2I(e->x) - def->box_x - w->cam_x;
        sy = NP_F2I(e->y) - def->box_y - w->cam_y;
        if (sx <= -(def->cols * 16) || sx >= NP_SCREEN_W) continue;
        if (sy <= -(def->rows * 16) || sy >= NP_SCREEN_H) continue;
        sprite = np_draw_actor(def, sprite, sx, sy,
                               np_actor_frame(def, e->anim, e->anim_frame),
                               (uint8_t)!e->facing);
        if (sprite >= NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) break;
    }

    for (i = 0; i < NP_MAX_PLAYERS; i++) {
        const NpActorDef *def = &np_player_def.actor;
        const NpPlayer *p = &w->players[i];
        int32_t sx, sy;
        if (!np_player_visible(w, i)) continue;
        sx = NP_F2I(p->x) - def->box_x - w->cam_x;
        sy = NP_F2I(p->y) - def->box_y - w->cam_y;
        sprite = np_draw_actor(def, sprite, sx, sy,
                               np_actor_frame(def, p->anim, p->anim_frame),
                               (uint8_t)!p->facing);
    }
#endif

    while (sprite < NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES) {
        np_sprite_hide(sprite);
        sprite++;
    }

#if NP_HUD_ENABLED
    np_hud_draw(w);
#endif
}
