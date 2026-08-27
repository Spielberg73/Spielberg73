/* np_md.h - hardware de la Mega Drive.
 *
 * La Mega Drive lleva el mismo 68000 que la Neo Geo, asi que la simulacion
 * (np_world.c) es la misma; lo que cambia es como se dibuja:
 *
 *   - hay DOS planos de fondo de verdad, con scroll por hardware:
 *       plano A -> el escenario        plano B -> la capa de parallax
 *   - una ventana (window) que no se mueve: ahi va el marcador
 *   - 80 sprites por pantalla para el jugador, enemigos y objetos
 *   - 4 paletas de 16 colores (el 0 es transparente)
 *   - el sonido de NeoPlat sale por el PSG, que el 68000 escribe directamente
 *
 * Registros segun la documentacion del VDP (ver docs/megadrive.md).
 */
#ifndef NP_MD_H
#define NP_MD_H

#include "np_world.h"
#include "gamedata.h"

/* --- puertos ----------------------------------------------------------- */
#define MD_VDP_DATA    ((volatile uint16_t *)0xC00000)
#define MD_VDP_DATA32  ((volatile uint32_t *)0xC00000)
#define MD_VDP_CTRL    ((volatile uint16_t *)0xC00004)
#define MD_VDP_CTRL32  ((volatile uint32_t *)0xC00004)
#define MD_PSG         ((volatile uint8_t *)0xC00011)
#define MD_PAD1_DATA   ((volatile uint8_t *)0xA10003)
#define MD_PAD1_CTRL   ((volatile uint8_t *)0xA10009)
#define MD_PAD2_DATA   ((volatile uint8_t *)0xA10005)
#define MD_PAD2_CTRL   ((volatile uint8_t *)0xA1000B)
#define MD_Z80_BUS     ((volatile uint16_t *)0xA11100)
#define MD_Z80_RESET   ((volatile uint16_t *)0xA11200)
#define MD_Z80_RAM     ((volatile uint8_t *)0xA00000)   /* 8 KB, byte a byte */
#define MD_TMSS        ((volatile uint32_t *)0xA14000)
#define MD_VERSION     ((volatile uint8_t *)0xA10001)

/* --- reparto de la VRAM (64 KB) ----------------------------------------
 *
 * El VDP no admite cualquier direccion: los planos A y B van en multiplos de
 * 8 KB, la ventana en multiplos de 4 KB (en modo de 320 px) y las tablas de
 * sprites y de scroll en multiplos de 1 KB. Y cada tabla ocupa de verdad lo
 * que dice su tamano, asi que ninguna puede pisar a otra:
 *
 *   0x0000  dibujos            42 KB -> 1344 tiles de 8x8
 *   0xA800  tabla de sprites   80 entradas de 8 bytes
 *   0xAC00  scroll horizontal
 *   0xB000  marcador           64x32 celdas (4 KB)
 *   0xC000  escenario          64x64 celdas (8 KB)
 *   0xE000  parallax           64x64 celdas (8 KB)
 */
#define MD_TILES       0x0000    /* los dibujos, 32 bytes cada uno */
#define MD_SPRITES     0xA800    /* tabla de sprites: 80 entradas de 8 bytes */
#define MD_HSCROLL     0xAC00    /* tabla de scroll horizontal */
#define MD_WINDOW      0xB000    /* marcador: 64x32 celdas */
#define MD_PLANE_A     0xC000    /* escenario: 64x64 celdas */
#define MD_PLANE_B     0xE000    /* parallax:  64x64 celdas */

#define MD_PLANE_W 64            /* celdas de ancho de cada plano */
#define MD_PLANE_H 64
#define MD_CELDAS_X 40           /* celdas visibles (320 px) */
#define MD_CELDAS_Y 28           /* celdas visibles (224 px) */

/* --- ordenes al VDP ---------------------------------------------------- */
#define MD_VRAM_WRITE  0x40000000UL
#define MD_CRAM_WRITE  0xC0000000UL
#define MD_VSRAM_WRITE 0x40000010UL

/* Direccion + orden, en el formato retorcido que pide el VDP. */
#define MD_ADDR(orden, direccion) \
    (((uint32_t)(orden)) | (((uint32_t)(direccion) & 0x3FFF) << 16) \
     | (((uint32_t)(direccion) >> 14) & 3))

/* Celda de un plano: prioridad, paleta, espejos y numero de tile. */
#define MD_CELDA(tile, paleta, prioridad) \
    ((uint16_t)(((prioridad) << 15) | ((paleta) << 13) | ((tile) & 0x07FF)))

void np_md_init(void);
void np_md_reg(uint8_t registro, uint8_t valor);
void np_md_vram_addr(uint32_t direccion);
void np_video_frame(const NpWorld *w);
void np_wait_vblank(void);
uint16_t np_input_read(void);
uint16_t np_input_read2(void);

/* marcador, en la ventana (np_hud.c) */
void np_hud_clear(void);
void np_hud_print(uint8_t col, uint8_t fila, const char *texto, uint8_t paleta);
void np_hud_number(uint8_t col, uint8_t fila, uint32_t valor, uint8_t digitos, uint8_t paleta);
void np_hud_draw(const NpWorld *w);

/* sonido: notas por el PSG y muestras por el Z80 (np_sound.c) */
void np_sound_init(void);
void np_sound_update(const NpWorld *w);

/* El driver de muestras del Z80, generado por el compilador en sonido.c */
extern const uint8_t np_z80_pcm[];
extern const uint16_t np_z80_pcm_largo;

#endif /* NP_MD_H */
