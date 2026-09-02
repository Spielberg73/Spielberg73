/* np_jaguar.h - hardware de la Atari Jaguar.
 *
 * La Jaguar es la mas moderna de las cuatro y la que trabaja de forma mas
 * distinta. No tiene planos de tiles ni sprites al uso: tiene un **Object
 * Processor** que recorre una lista de objetos en cada linea de barrido y los
 * compone en un buffer de linea. NeoPlat la usa asi:
 *
 *   - un mapa de bits lineal de 704x256, **un byte por pixel** (256 colores de
 *     una tabla de color), que es mucho mas simple que los bitplanes del Amiga
 *   - el scroll es gratis: se mueve la direccion de los datos del objeto (de
 *     ocho en ocho pixeles) y el resto se ajusta con su posicion X
 *   - el jugador, los enemigos y los objetos **no se dibujan**: cada uno es un
 *     objeto mas de la lista, y el chip los compone con transparencia
 *   - el marcador es otro objeto, encima de todo
 *
 * Registros y formato de la lista segun la documentacion de Atari (jaguar.inc
 * del SDK). Ver docs/jaguar.md.
 *
 * TRES TRAMPAS que costaron encontrar, todas comprobadas en el emulador:
 *
 *   1. El cartucho no arranca solo: la consola busca la pila en cart+$400 y el
 *      punto de entrada en cart+$404. Sin eso salta a la direccion 0.
 *   2. El Object Processor **gasta** el objeto mientras dibuja (va restando de
 *      la altura y sumando a la direccion), asi que hay que reescribir su frase
 *      en cada retrazo.
 *   3. Ni la lista ni el mapa de bits los lee el programa: los lee el chip por
 *      DMA. Sin `volatile` (o una barrera) el compilador borra las escrituras
 *      por inservibles y no se ve nada.
 */
#ifndef NP_JAGUAR_H
#define NP_JAGUAR_H

#include "np_world.h"
#include "gamedata.h"

#define TOM 0xF00000

#define REG16(x)  (*(volatile uint16_t *)(uintptr_t)(TOM + (x)))
#define REG32(x)  (*(volatile uint32_t *)(uintptr_t)(TOM + (x)))

/* --- registros de video (TOM) ------------------------------------------ */
#define VC        REG16(0x006)      /* linea de barrido, en medias lineas   */
#define OLP       REG32(0x020)      /* puntero a la lista de objetos        */
#define VMODE     REG16(0x028)
#define BORD1     REG32(0x02A)
#define HDB1      REG16(0x038)
#define HDB2      REG16(0x03A)
#define HDE       REG16(0x03C)
#define VDB       REG16(0x046)
#define VDE       REG16(0x048)
#define VI        REG16(0x04E)
#define BG        REG16(0x058)
#define CLUT      ((volatile uint16_t *)(uintptr_t)(TOM + 0x400))
#define JOYSTICK  REG32(0x14000)    /* mando y botones, activos a nivel bajo */
#define CONFIG    REG16(0x14002)    /* bit 4: 1 = NTSC, 0 = PAL              */

/* --- Jerry: sonido ------------------------------------------------------
 *
 * La Jaguar no tiene chip de sonido: tiene dos DAC de 16 bits y un DSP que los
 * alimenta muestra a muestra. El programa del DSP lo genera el compilador
 * (tools/ngplat/jerry.py) y va en sonido.c; aqui solo estan sus registros.
 */
#define D_FLAGS   REG32(0x1A100)
#define D_PC      REG32(0x1A110)
#define D_CTRL    REG32(0x1A114)
#define SCLK      REG32(0x1A150)    /* muestras = reloj / (64 * (SCLK + 1)) */
#define SMODE     REG32(0x1A154)
#define D_RAM     ((volatile uint32_t *)(uintptr_t)(TOM + 0x1B000))

#define NP_DSPGO      0x00000001u
#define NP_SMODE_INT  0x01u         /* Jerry genera su propio reloj de audio  */
#define NP_SMODE_WSEN 0x04u
#define NP_SMODE_FALL 0x10u
#define NP_SMODE (NP_SMODE_INT | NP_SMODE_WSEN | NP_SMODE_FALL)

/* --- modo de video ------------------------------------------------------ */
#define NP_VIDEN   0x0001
#define NP_RGB16   0x0006
#define NP_CSYNC   0x0040
#define NP_BGEN    0x0080
#define NP_PWIDTH4 0x0600
#define NP_VMODE (NP_VIDEN | NP_RGB16 | NP_CSYNC | NP_BGEN | NP_PWIDTH4)

/* --- tipos de objeto ---------------------------------------------------- */
#define NP_OBJ_BITMAP 0
#define NP_OBJ_BRANCH 3
#define NP_OBJ_STOP   4
#define NP_OBJ_DEPTH8 (3u << 12)    /* 8 bits por pixel        */
#define NP_OBJ_NOGAP  (1u << 15)    /* datos seguidos          */
#define NP_OBJ_TRANS  (1u << 15)    /* en la mitad alta: color 0 transparente */

/* --- pantalla ----------------------------------------------------------- */
/* La forma del mapa de bits la elige gamedata.h: los mismos 176 KB puestos a
   lo ancho (704x256: 44 casillas x 16, para un juego que se cruza) o a lo alto
   (352x512: 22 x 32, para uno que se sube y cabe entero dentro). El alto de un
   nivel no puede pasar de NP_MAPA_ALTO / NP_TILE: hacia abajo el scroll es
   solo mover el puntero del objeto, no hay ventana. */
#ifndef NP_MAPA_ANCHO
#define NP_MAPA_ANCHO 704           /* el doble de ancho que la pantalla     */
#endif
#ifndef NP_MAPA_ALTO
#define NP_MAPA_ALTO 256
#endif
#define NP_TILE 16
#define NP_HUD_ALTO 24
#define NP_FONDO_ALTO 224           /* alto del mapa de bits del parallax     */
#define NP_HUD_COLOR 255            /* el ultimo color de la tabla           */
#define NP_ACTORES_MAX 48           /* objetos de la lista para los actores  */

#define NP_DIR(p) ((uint32_t)(uintptr_t)(p))

void np_jaguar_init(void);
void np_video_frame(const NpWorld *w);
void np_wait_vblank(void);
uint16_t np_input_read(void);
uint16_t np_input_read2(void);

void np_sound_init(void);
void np_sound_update(const NpWorld *w);

void np_hud_draw(const NpWorld *w);
void np_hud_clear(void);
void np_hud_print(uint8_t col, uint8_t fila, const char *texto);
void np_hud_number(uint8_t col, uint8_t fila, uint32_t valor, uint8_t digitos);

/* datos que genera el compilador (graficos.c) */
extern uint8_t np_bitmap[];                 /* el mapa de bits del escenario */
extern uint8_t np_hud_bitmap[];             /* la franja del marcador        */
#if NP_LAYER_COUNT > 0
extern uint8_t np_fondo_bitmap[];           /* el parallax, por detras       */
#endif
extern const uint8_t np_tile_data[];        /* tiles de 16x16, un byte por pixel */
extern const uint16_t np_colores[256];
extern const uint8_t np_font_data[];        /* fuente de 8x8, un bit por pixel */

/* el driver del DSP, tambien generado (sonido.c) */
extern const uint32_t np_dsp_codigo[];
extern const uint16_t np_dsp_palabras;      /* cuantos long ocupa            */
extern const uint32_t np_dsp_inicio;        /* por donde arranca el DSP      */
extern const uint32_t np_dsp_parametros;    /* el bloque que escribe el 68000 */
extern const uint16_t np_dsp_sclk;

#endif /* NP_JAGUAR_H */
