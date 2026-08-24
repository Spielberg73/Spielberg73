/* np_video.h - capa de hardware Neo Geo: video, mando y sincronizacion.
 *
 * La Neo Geo no tiene un plano de fondo con scroll: el fondo se dibuja con
 * columnas de sprites de 16 pixeles de ancho (el truco clasico de la consola).
 * Aqui se reservan columnas para el escenario, columnas para cada capa de
 * parallax y el resto de sprites para el jugador, los enemigos y los objetos.
 *
 * Direcciones de registros segun la documentacion de hardware de Neo Geo
 * (ver docs/neogeo.md).
 */
#ifndef NP_VIDEO_H
#define NP_VIDEO_H

#include "np_world.h"
#include "gamedata.h"

/* --- registros del hardware ------------------------------------------- */
#define NP_REG_P1CNT     ((volatile uint8_t *)0x300000)
#define NP_REG_WATCHDOG  ((volatile uint8_t *)0x300001)
#define NP_REG_STATUS_B  ((volatile uint8_t *)0x380000)
#define NP_REG_VRAMADDR  ((volatile uint16_t *)0x3C0000)
#define NP_REG_VRAMRW    ((volatile uint16_t *)0x3C0002)
#define NP_REG_VRAMMOD   ((volatile uint16_t *)0x3C0004)
#define NP_REG_LSPCMODE  ((volatile uint16_t *)0x3C0006)
#define NP_PALETTE_RAM   ((volatile uint16_t *)0x400000)
#define NP_BACKDROP      ((volatile uint16_t *)0x401FFE)

/* --- mapa de la VRAM --------------------------------------------------- */
#define NP_SCB1 0x0000   /* tilemaps de sprite: 64 words por sprite */
#define NP_FIXMAP 0x7000 /* plano fix: 40x32, ordenado por columnas */
#define NP_SCB2 0x8000   /* zoom */
#define NP_SCB3 0x8200   /* posicion Y, encadenado y altura */
#define NP_SCB4 0x8400   /* posicion X */

/* --- reparto de sprites ------------------------------------------------
 *
 * El numero de sprite decide quien tapa a quien. NP_SPRITE_FRONT_FIRST a 1
 * significa "el sprite 1 se dibuja delante de los siguientes", que es lo que
 * documenta la escena de Neo Geo.
 *
 * ESTO ES LO PRIMERO QUE HAY QUE MIRAR si al probar la ROM el fondo tapa al
 * jugador o las capas de parallax salen delante: cambia este 1 por un 0 y se
 * invierte todo el reparto, sin tocar nada mas.
 */
#ifndef NP_SPRITE_FRONT_FIRST
#define NP_SPRITE_FRONT_FIRST 1
#endif

#define NP_BG_COLUMNS 21           /* 320/16 + 1 para el scroll */
#define NP_BG_ROWS 15              /* 224/16 + 1 */
#define NP_LAYER_COLUMNS 21
#define NP_ACTOR_SPRITES 96
#define NP_LAYER_SPRITES (NP_LAYER_COUNT * NP_LAYER_COLUMNS)

#if NP_SPRITE_FRONT_FIRST
#define NP_ACTOR_FIRST_SPRITE 1
#define NP_BG_FIRST_SPRITE (NP_ACTOR_FIRST_SPRITE + NP_ACTOR_SPRITES)
/* la capa 0 es la mas lejana: se va al final, detras de todo */
#define NP_LAYER_FIRST_SPRITE(i) \
    (NP_BG_FIRST_SPRITE + NP_BG_COLUMNS + (NP_LAYER_COUNT - 1 - (i)) * NP_LAYER_COLUMNS)
#else
#define NP_LAYER_FIRST_SPRITE(i) (1 + (i) * NP_LAYER_COLUMNS)
#define NP_BG_FIRST_SPRITE (1 + NP_LAYER_SPRITES)
#define NP_ACTOR_FIRST_SPRITE (NP_BG_FIRST_SPRITE + NP_BG_COLUMNS)
#endif

#define NP_TOTAL_SPRITES (1 + NP_ACTOR_SPRITES + NP_BG_COLUMNS + NP_LAYER_SPRITES)

void np_video_init(void);
void np_video_frame(const NpWorld *w);
void np_wait_vblank(void);
uint16_t np_input_read(void);

/* HUD (np_hud.c) */
void np_hud_clear(void);
void np_hud_print(uint8_t col, uint8_t row, const char *text, uint8_t palette);
void np_hud_number(uint8_t col, uint8_t row, uint32_t value, uint8_t digits, uint8_t palette);
void np_hud_draw(const NpWorld *w);

/* utilidades compartidas por np_video.c y np_hud.c */
void np_vram_seek(uint16_t address, int16_t modulo);
void np_vram_write(uint16_t value);

#endif /* NP_VIDEO_H */
