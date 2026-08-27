/* np_st.h - hardware del Atari ST (un 520 ST de los de siempre).
 *
 * El ST es un 68000 a 8 MHz con un chip de video (el Shifter) que lee la
 * pantalla de la memoria y poco mas. Comparado con las otras cuatro maquinas
 * del kit, lo que **no** tiene marca todo el diseno:
 *
 *   - no tiene blitter (el del Mega ST llego despues): copiar pixeles lo hace
 *     la CPU, byte a byte;
 *   - no tiene scroll por hardware: la pantalla siempre empieza en la
 *     direccion que se le diga, pero solo con precision de 256 bytes, que son
 *     una linea y media. Para mover el escenario hay que mover la memoria;
 *   - no tiene sprites: los actores se dibujan y se borran a mano.
 *
 * Lo que si tiene, y es lo que se usa aqui:
 *
 *   - 320x200 con **cuatro bitplanes** (16 colores de 512), entrelazados: cada
 *     grupo de 16 pixeles son cuatro palabras seguidas, una por plano;
 *   - un YM2149 igual que el SSG de la Neo Geo: tres cuadradas y un ruido;
 *   - el teclado y el joystick, que los lleva un 6301 aparte (el IKBD) y
 *     hablan por una linea serie.
 *
 * Direcciones segun el "Atari ST Internals" (ver docs/atarist.md).
 */
#ifndef NP_ST_H
#define NP_ST_H

#include "np_world.h"
#include "gamedata.h"

#define REG8(x)   (*(volatile uint8_t *)(uintptr_t)(x))
#define REG16(x)  (*(volatile uint16_t *)(uintptr_t)(x))

/* --- Shifter (video) ---------------------------------------------------- */
#define ST_VIDEO_ALTA   0xFF8201     /* de donde lee la pantalla: A23-A16 */
#define ST_VIDEO_MEDIA  0xFF8203     /*                           A15-A8  */
#define ST_CUENTA_ALTA  0xFF8205     /* por donde va el haz (solo lectura) */
#define ST_CUENTA_MEDIA 0xFF8207
#define ST_CUENTA_BAJA  0xFF8209
#define ST_SINCRONIA    0xFF820A     /* bit 1: 1 = 50 Hz (PAL), 0 = 60 Hz */
#define ST_PALETA       0xFF8240     /* 16 palabras 0000 0RRR 0GGG 0BBB */
#define ST_RESOLUCION   0xFF8260     /* 0 = 320x200 y 16 colores */

/* --- YM2149 (sonido y algunas patillas sueltas) ------------------------- */
#define ST_YM_REGISTRO  0xFF8800     /* que registro (y leerlo) */
#define ST_YM_DATO      0xFF8802     /* y su valor */

/* --- IKBD (teclado y joystick), por el ACIA ----------------------------- */
#define ST_ACIA_ESTADO  0xFFFC00     /* bit 0: hay un byte esperando */
#define ST_ACIA_DATO    0xFFFC02
#define ST_MIDI_ESTADO  0xFFFC04     /* el MIDI comparte la interrupcion */
#define ST_MIDI_DATO    0xFFFC06

/* --- MFP 68901: es quien reparte las interrupciones --------------------- */
#define MFP_IERA        0xFFFA07     /* cuales estan encendidas */
#define MFP_IERB        0xFFFA09
#define MFP_IPRA        0xFFFA0B     /* cuales estan pendientes */
#define MFP_IPRB        0xFFFA0D
#define MFP_ISRB        0xFFFA11     /* cuales se estan atendiendo */
#define MFP_IMRA        0xFFFA13     /* cuales dejan pasar */
#define MFP_IMRB        0xFFFA15
#define MFP_ACIA        0x40         /* la del teclado, en el grupo B */
#define ST_VECTOR_ACIA  0x118        /* vector $46: 0x46 * 4 */

/* --- pantalla ------------------------------------------------------------
 *
 * Aqui esta la unica diferencia de verdad entre el ST y las otras maquinas del
 * kit: el ST muestra **200 lineas** y las demas 224. El motor es el mismo para
 * todas (si no, el juego no seria el mismo juego), asi que lo que se hace es
 * ensenar una ventana del mismo mundo.
 *
 * En las otras maquinas el marcador tapa las 24 primeras lineas de la vista y
 * el juego ocupa las 200 restantes. Aqui el marcador se lleva las mismas 24 y
 * al juego le quedan 176, asi que sobran 24 lineas del mundo. Se quitan
 * **todas por arriba**, no doce arriba y doce abajo: en un juego de
 * plataformas abajo esta el suelo, y recortarlo se nota mucho mas que
 * recortar cielo. Asi el borde de abajo cae exactamente donde en las demas
 * maquinas, y la linea de pantalla L ensena la fila `L + cam_y + 24`.
 */
#define NP_PLANOS 4
#define NP_ANCHO 320
#define NP_ALTO 200
#define NP_PASO_FILA (NP_ANCHO / 8 * NP_PLANOS)      /* 160 bytes por linea */
#define NP_PANTALLA_BYTES (NP_ALTO * NP_PASO_FILA)   /* 32000 */
#define NP_HUD_ALTO 24                               /* tres filas de 8 px */
#define NP_JUEGO_ALTO (NP_ALTO - NP_HUD_ALTO)        /* 176 lineas de juego */
#define NP_RECORTE_Y (NP_SCREEN_H - NP_HUD_ALTO - NP_JUEGO_ALTO)   /* 24 */
#define NP_TILE 16
#define NP_COLUMNAS (NP_ANCHO / NP_TILE)             /* 20 columnas de tiles */
#define NP_FILAS (NP_JUEGO_ALTO / NP_TILE + 1)       /* 12: la ultima, a medias */
#define NP_HUD_COLOR 15                              /* el ultimo color */
#define NP_HUD_BYTES (NP_HUD_ALTO * NP_PASO_FILA)

/* Dos pantallas: mientras se ve una se dibuja la otra. En una maquina sin
   blitter eso no es un lujo, es lo que evita que los actores parpadeen: entre
   borrar y volver a dibujar pasa medio frame, y el haz pasa por encima.
 *
 * Van separadas 32 KB y alineadas a 32 KB a proposito, y no pegadas una detras
 * de otra: asi las dos empiezan en una direccion cuyos bits 8 a 14 son cero, y
 * el contador de video (que es lo unico que dice por donde va el haz cuando no
 * hay interrupciones) marca lo mismo se este viendo la que se este viendo. */
#define NP_PANTALLAS 2
#define NP_HUECO_PANTALLA 32768

/* Cuantas veces se simula por cada vez que se dibuja. En el ST dibujar cuesta
   mas de un frame en cuanto hay que mover el escenario, asi que el juego corre
   a 50 pasos por segundo (como en las demas maquinas, que es lo que hace que
   sea el mismo juego) pero la pantalla se refresca a 25. Lo pone el compilador
   en gamedata.h despues de medirlo; esto es solo el valor por defecto. */
#ifndef NP_PASOS_POR_DIBUJO
#define NP_PASOS_POR_DIBUJO 1
#endif

void np_st_init(void);
void np_video_frame(const NpWorld *w);      /* las dos mitades, seguidas */
void np_video_escenario(const NpWorld *w);  /* y cada una por su cuenta: ver */
void np_video_actores(const NpWorld *w);    /* el reparto en np_video.c      */
void np_wait_vblank(void);
uint16_t np_input_read(void);
uint16_t np_input_read2(void);

void np_sound_init(void);
void np_sound_update(const NpWorld *w);

void np_hud_draw(const NpWorld *w);
void np_hud_clear(void);
void np_hud_print(uint8_t col, uint8_t fila, const char *texto);
void np_hud_number(uint8_t col, uint8_t fila, uint32_t valor, uint8_t digitos);
uint8_t np_hud_cambiado(void);           /* y lo pone a cero */
extern uint8_t np_hud_bitmap[];          /* 320x24: lo que va arriba del todo */

/* El fondo (parallax). Solo se dibuja con `camara: pantallas`: ahi la vista se
 * queda quieta entre salto y salto, asi que el fondo tambien, y pintarlo sale
 * **gratis** (donde no hay escenario ya se pintaba un tile en blanco). Con
 * `camara: scroll` el fondo tendria que ir a otra velocidad que el escenario, y
 * sin un segundo plano por hardware eso obliga a repintar la pantalla entera
 * cada pocos pixeles: no cabe. Lo pone gamedata.h. */
#ifndef NP_FONDO_ST
#define NP_FONDO_ST 0
#endif

/* datos que genera el compilador (graficos.c) */
extern uint8_t np_pantallas[];                   /* las dos, sin alinear */
extern const uint8_t np_tile_data[];             /* 128 bytes por dibujo */
extern const uint8_t np_tile_mask[];             /*  32 bytes por dibujo */
#if NP_FONDO_ST
/* Un bit por dibujo: 1 si no tiene ni un pixel transparente. Un tile asi tapa
   el fondo entero, asi que se copia tal cual y no hay que mirar la mascara ni
   pintar el fondo debajo. En un escenario normal casi todos son de estos o
   estan vacios, y por eso el parallax no cuesta nada. */
extern const uint8_t np_tile_opaco[];
#endif
extern const uint16_t np_colores[16];
extern const uint8_t np_font_data[];             /* fuente de 8x8, un bit por pixel */

#endif /* NP_ST_H */
