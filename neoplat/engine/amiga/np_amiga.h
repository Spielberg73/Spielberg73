/* np_amiga.h - hardware del Amiga (OCS/ECS, un A500 basta).
 *
 * El Amiga es la mas distinta de las tres maquinas: no tiene tiles ni sprites
 * de hardware suficientes para un juego asi, sino **bitplanes** y un **blitter**
 * que copia trozos de memoria a toda velocidad. NeoPlat lo usa asi:
 *
 *   - un mapa de bits de 704x256 pixeles y 5 bitplanes (32 colores),
 *     entrelazado: cada fila lleva las cinco palabras de los cinco planos
 *     seguidas, que es lo que le gusta al blitter
 *   - el scroll es por hardware: se mueven los punteros de los bitplanes y se
 *     usa BPLCON1 para los pixeles sueltos; solo se dibuja la columna que entra
 *   - el jugador, los enemigos y los objetos se dibujan con el blitter
 *     recortados por su mascara, repintando antes el fondo que taparon
 *   - el sonido sale por Paula: una onda cuadrada de 32 muestras a la que se
 *     le cambia el periodo para dar cada nota
 *
 * Registros segun el Amiga Hardware Reference Manual (ver docs/amiga.md).
 */
#ifndef NP_AMIGA_H
#define NP_AMIGA_H

#include "np_world.h"
#include "gamedata.h"

#define CUSTOM 0xDFF000

/* --- registros del chipset --------------------------------------------- */
/* El rodeo por uintptr_t es para que valga tambien cuando el registro se elige
   con una variable (los cuatro canales de Paula) sin que chille el compilador
   del ordenador en las pruebas. */
#define REG16(x)  (*(volatile uint16_t *)(uintptr_t)(CUSTOM + (x)))
#define REG32(x)  (*(volatile uint32_t *)(uintptr_t)(CUSTOM + (x)))

#define DMACONR   REG16(0x002)
#define VPOSR     REG16(0x004)
#define VHPOSR    REG16(0x006)
#define POTGOR    REG16(0x016)
#define JOY0DAT   REG16(0x00A)
#define JOY1DAT   REG16(0x00C)
#define INTENAR   REG16(0x01C)
#define BLTCON0   REG16(0x040)
#define BLTCON1   REG16(0x042)
#define BLTAFWM   REG16(0x044)
#define BLTALWM   REG16(0x046)
#define BLTCPT    REG32(0x048)
#define BLTBPT    REG32(0x04C)
#define BLTAPT    REG32(0x050)
#define BLTDPT    REG32(0x054)
#define BLTSIZE   REG16(0x058)
#define BLTCMOD   REG16(0x060)
#define BLTBMOD   REG16(0x062)
#define BLTAMOD   REG16(0x064)
#define BLTDMOD   REG16(0x066)
#define COP1LC    REG32(0x080)
#define COPJMP1   REG16(0x088)
#define DIWSTRT   REG16(0x08E)
#define DIWSTOP   REG16(0x090)
#define DDFSTRT   REG16(0x092)
#define DDFSTOP   REG16(0x094)
#define POTGO     REG16(0x034)
#define DMACON    REG16(0x096)
#define INTENA    REG16(0x09A)
#define INTREQ    REG16(0x09C)
#define BPLCON0   REG16(0x100)
#define BPLCON1   REG16(0x102)
#define BPL1MOD   REG16(0x108)
#define BPL2MOD   REG16(0x10A)
#define BPLPT(n)  REG32(0x0E0 + (n) * 4)
#define COLOR(n)  REG16(0x180 + (n) * 2)
#define AUDLC(n)  REG32(0x0A0 + (n) * 16)        /* de donde sale la onda */
#define AUDLEN(n) REG16(0x0A4 + (n) * 16)        /* su largo, en palabras  */
#define AUDPER(n) REG16(0x0A6 + (n) * 16)        /* periodo = la nota      */
#define AUDVOL(n) REG16(0x0A8 + (n) * 16)        /* volumen, 0-64          */

#define CIAA_PRA  (*(volatile uint8_t *)0xBFE001)

/* La direccion de algo, en los 32 bits que entienden el copper y el blitter.
   En el Amiga un puntero ya son 32 bits; el rodeo por uintptr_t es para que
   este mismo codigo se pueda comprobar en el ordenador (las pruebas lo hacen). */
#define NP_DIR(p) ((uint32_t)(uintptr_t)(p))

/* --- pantalla -----------------------------------------------------------
 *
 * El Amiga tiene dos modos, y se elige en el game.yaml con `amiga:`:
 *
 *   32colores  cinco bitplanes, un solo plano de juego. Todos los colores para
 *              los dibujos, pero no hay sitio para capas de fondo.
 *   8colores   *dual playfield*: los seis bitplanes se parten en dos planos
 *              independientes de tres, cada uno con su scroll por hardware.
 *              El juego va delante con 7 colores y el parallax detras con
 *              otros 7. Es la unica forma de tener parallax de verdad en un
 *              A500: dibujarlo con el blitter no cabe en un frame, esta medido
 *              (ver docs/amiga.md).
 *
 * gamedata.h define NP_PLANOS a 3 o a 5; aqui solo esta el valor por defecto. */
#ifndef NP_PLANOS
#define NP_PLANOS 5
#endif
#if NP_PLANOS == 3
#define NP_DOBLE_PLANO 1
#else
#define NP_DOBLE_PLANO 0
#endif
#define NP_MAPA_ANCHO 704                       /* pixeles del mapa de bits */
#define NP_MAPA_ALTO 256
#define NP_BYTES_FILA (NP_MAPA_ANCHO / 8)       /* 88 bytes por plano y fila */
#define NP_PASO_FILA (NP_BYTES_FILA * NP_PLANOS) /* entrelazado: 440 bytes */
#define NP_TILE 16

/* El marcador va en su propia franja: el copper cambia los punteros de los
   bitplanes en la linea NP_HUD_ALTO y a partir de ahi se ve el juego. */
#define NP_HUD_ALTO 24                          /* tres filas de 8 pixeles */
#define NP_HUD_BYTES_FILA 40                    /* 320 px de ancho         */
#define NP_HUD_PASO (NP_HUD_BYTES_FILA * NP_PLANOS)
#if NP_DOBLE_PLANO
#define NP_HUD_COLOR 7                          /* el ultimo del plano de delante */
#else
#define NP_HUD_COLOR 31                         /* el ultimo color de la paleta */
#endif

void np_amiga_init(void);
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
extern uint8_t np_bitmap[];                      /* el mapa de bits, en RAM chip */
extern uint8_t np_hud_bitmap[];                  /* la franja del marcador       */
#if NP_DOBLE_PLANO
extern uint8_t np_fondo_bitmap[];                /* el plano de atras (parallax) */
#endif
extern const uint8_t np_tile_data[];             /* dibujos entrelazados */
extern const uint8_t np_tile_mask[];             /* sus mascaras */
extern const uint16_t np_colores[32];
extern const uint8_t np_font_data[];             /* fuente de 8x8, un bit por pixel */

#endif /* NP_AMIGA_H */
