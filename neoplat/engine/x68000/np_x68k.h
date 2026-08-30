/* np_x68k.h - el hardware del Sharp X68000, en un solo sitio.
 *
 * Los chips que nos importan:
 *
 *   CRTC      ($E80000)  temporizado y modo de pantalla
 *   VIDEO     ($E82000)  paletas, prioridad de capas y que capa se ve
 *   MFP       ($E88000)  interrupciones, y de ahi el retrazo vertical
 *   PPI       ($E9A000)  los dos mandos (un 8255)
 *   CYNTHIA   ($EB0000)  sprites, capa de fondo y la RAM de patrones (PCG)
 *
 * **Todo lo del chip de sprites esta medido en el emulador, no copiado de un
 * manual.** La primera version de este archivo iba de documentacion suelta y
 * no dibujaba nada: los sprites salian a medias y la capa de fondo no salia.
 * Se escribio una sonda que enciende bits, dibuja y mira la pantalla, y de ahi
 * salio lo que hay aqui. Lo que aprendio, por si alguien lo vuelve a tocar:
 *
 *   - Los registros R00-R07 del CRTC son de **solo escritura**: se leen a
 *     cero. Por eso el arranque llama antes a la ROM (_CRTMOD) y luego escribe
 *     su temporizado encima.
 *   - El chip entero se enciende con el bit 9 de $EB0808. Sin el no hay ni
 *     sprites ni capa, pongas lo que pongas en los demas registros.
 *   - Los patrones son de 16x16 **solo si** el bit 0 de $EB0810 esta a uno. A
 *     cero son de 8x8, y una tabla de nombres hecha para 16x16 se ve como
 *     ruido o directamente no se ve.
 *   - La tabla de nombres **es la propia PCG**: $EBC000 y $EBE000 son los
 *     patrones 128-191 y 192-255. Quien usa capa de fondo se queda sin ellos.
 *   - De las dos capas de fondo que tiene el chip, en el emulador solo se
 *     ensena una: con las dos encendidas y cada una leyendo una tabla, nunca
 *     se ven los dos dibujos a la vez. Asi que el escenario va en la capa y el
 *     parallax no se dibuja en esta maquina.
 *   - El plano de texto (el marcador) lee de la **paleta de sprites**, bloque
 *     0. Por eso el color 15 de ese bloque se reserva para el marcador, igual
 *     que en el Atari ST.
 */
#ifndef NP_X68K_H
#define NP_X68K_H

#include "np_world.h"

/* --- la ROM ------------------------------------------------------------
 *
 * Las llamadas IOCS de la ROM dejan la pantalla y el chip de sprites puestos
 * para el modo que se les pida. El arranque las usa y luego cambia el
 * temporizado a lo nuestro: asi no hay que adivinar los valores de los
 * registros que no se pueden releer.
 */
#define NP_IOCS_CRTMOD   0x10     /* poner un modo de pantalla */
#define NP_IOCS_SP_INIT  0xB0     /* preparar el chip de sprites */
#define NP_IOCS_SP_ON    0xB1     /* y encenderlo */
#define NP_MODO_ROM      3        /* 256x240 a 16 colores: el mas parecido */

static __inline long np_iocs(long numero, long d1, long d2)
{
    register long r0 __asm__("d0") = numero;
    register long r1 __asm__("d1") = d1;
    register long r2 __asm__("d2") = d2;
    __asm__ volatile ("trap #15" : "+d"(r0), "+d"(r1), "+d"(r2)
                      : : "a0", "a1", "a2", "cc", "memory");
    return r0;
}

/* --- CRTC: temporizado y modo ------------------------------------------ */
#define NP_CRTC_R00      ((volatile uint16_t *)0xE80000)  /* total horizontal */
#define NP_CRTC_R01      ((volatile uint16_t *)0xE80002)  /* fin del HSYNC */
#define NP_CRTC_R02      ((volatile uint16_t *)0xE80004)  /* inicio de imagen */
#define NP_CRTC_R03      ((volatile uint16_t *)0xE80006)  /* fin de imagen */
#define NP_CRTC_R04      ((volatile uint16_t *)0xE80008)  /* total vertical */
#define NP_CRTC_R05      ((volatile uint16_t *)0xE8000A)  /* fin del VSYNC */
#define NP_CRTC_R06      ((volatile uint16_t *)0xE8000C)  /* primera linea */
#define NP_CRTC_R07      ((volatile uint16_t *)0xE8000E)  /* ultima linea */
#define NP_CRTC_R20      ((volatile uint16_t *)0xE80028)  /* modo de memoria */

/* R20: bits 9-8 color (00 = 16 colores), bits 3-2 alto, bits 1-0 ancho
   (00 = 256, 01 = 512, 10 = 768). */
#define NP_R20_COL16     0x0000
#define NP_R20_ANCHO_512 0x0001
#define NP_R20_ALTO_512  0x0004

/* --- controlador de video: paletas y capas ------------------------------ */
#define NP_PALETA_GFX    ((volatile uint16_t *)0xE82000)  /* 256 colores */
#define NP_PALETA_PCG    ((volatile uint16_t *)0xE82200)  /* 16 bloques de 16 */
#define NP_VC_R0         ((volatile uint16_t *)0xE82400)  /* modo de color */
#define NP_VC_R1         ((volatile uint16_t *)0xE82500)  /* prioridad */
#define NP_VC_R2         ((volatile uint16_t *)0xE82600)  /* que capas se ven */

/* VC_R2: bit 6 sprites, bit 5 texto, bits 3-0 las cuatro paginas graficas */
#define NP_VC_SPRITES    0x0040
#define NP_VC_TEXTO      0x0020

/* --- YM2151 (OPM): la musica y los efectos ------------------------------
 *
 * Dos direcciones, como el YM2149 del Atari ST: el numero de registro en una y
 * el valor en la otra. Por la primera se lee ademas el estado, y el bit 7 dice
 * que el chip todavia esta ocupado con lo anterior.
 */
#define NP_OPM_REGISTRO  ((volatile uint8_t *)0xE90001)
#define NP_OPM_ESTADO    ((volatile uint8_t *)0xE90001)
#define NP_OPM_DATO      ((volatile uint8_t *)0xE90003)
#define NP_OPM_OCUPADO   0x80

/* --- MFP: de aqui sale el retrazo vertical ------------------------------ */
#define NP_MFP_GPIP      ((volatile uint8_t *)0xE88001)
#define NP_MFP_GPIP_VDISP 0x10    /* a 0 mientras se dibuja la imagen */

/* --- PPI: los mandos ----------------------------------------------------
 *
 * Un 8255: el puerto A es el mando 1 y el B el mando 2. Los bits 0-3 son las
 * direcciones y los 4-5 los dos botones.
 *
 * La polaridad es la de un mando de estilo MSX -que es lo que lleva esta
 * maquina-: el puerto tiene resistencias de subida y el mando tira a masa, asi
 * que un bit **a cero** es un boton pulsado. Comprobado en el emulador: con
 * esto el juego empieza al pulsar el boton y el jugador anda hacia donde se le
 * dice; invertido no responderia a nada.
 */
#define NP_PPI_A         ((volatile uint8_t *)0xE9A001)
#define NP_PPI_B         ((volatile uint8_t *)0xE9A003)
#define NP_PPI_C         ((volatile uint8_t *)0xE9A005)
#define NP_PPI_CTRL      ((volatile uint8_t *)0xE9A007)
#define NP_PPI_MODO      0x92     /* A y B de entrada, C de salida */
#define NP_MANDO_PULSADO(bits, bit) (((bits) & (bit)) == 0)

#define NP_JOY_ARRIBA    0x01
#define NP_JOY_ABAJO     0x02
#define NP_JOY_IZQUIERDA 0x04
#define NP_JOY_DERECHA   0x08
#define NP_JOY_A         0x20
#define NP_JOY_B         0x40

/* --- CYNTHIA: sprites, capas BG y patrones ------------------------------
 *
 * Cada sprite son cuatro palabras: x, y, atributo y prioridad. El atributo
 * lleva los volteos (bits 15-14), el bloque de paleta (bits 11-8) y el numero
 * de patron (bits 7-0). La prioridad a cero apaga el sprite.
 *
 * Las coordenadas llevan un desplazamiento fijo: el origen de la pantalla esta
 * en (16, 16) para los sprites, asi que un sprite en (0, 0) queda justo fuera
 * por arriba y por la izquierda.
 */
#define NP_SPRITE_REGS   ((volatile uint16_t *)0xEB0000)
#define NP_SPRITES       128
#define NP_SPRITE_ORIGEN_X 16
#define NP_SPRITE_ORIGEN_Y 16

#define NP_BG0_X         ((volatile uint16_t *)0xEB0800)
#define NP_BG0_Y         ((volatile uint16_t *)0xEB0802)
#define NP_BG1_X         ((volatile uint16_t *)0xEB0804)
#define NP_BG1_Y         ((volatile uint16_t *)0xEB0806)
#define NP_BG_CTRL       ((volatile uint16_t *)0xEB0808)
#define NP_BG_HTOTAL     ((volatile uint16_t *)0xEB080A)
#define NP_BG_HDISP      ((volatile uint16_t *)0xEB080C)
#define NP_BG_VDISP      ((volatile uint16_t *)0xEB080E)
#define NP_BG_RES        ((volatile uint16_t *)0xEB0810)

/* BG_CTRL, medido bit a bit en el emulador:
     bit 9  enciende el chip entero (sprites incluidos)
     bit 0  enciende la capa de fondo
     bit 1  de que tabla come: a cero $EBC000, a uno $EBE000
   Los demas bits no cambiaron nada en ninguna combinacion. */
#define NP_BG_CHIP_ON    0x0200
#define NP_BG_CAPA_ON    0x0001
#define NP_BG_TABLA_ALTA 0x0002

/* BG_RES: el bit 0 pone los patrones en 16x16. */
#define NP_BG_PATRON16   0x0001

/* La tabla de nombres, 64x64 palabras. Cada palabra tiene el mismo formato que
   el atributo de un sprite: volteos, bloque de paleta y numero de patron.

   Se usa la de arriba ($EBE000) a proposito: como la tabla vive dentro de la
   propia PCG, dejarla al final deja seguidos los patrones 0-191 en vez de
   partirlos en dos trozos. */
#define NP_BG_MAPA       ((volatile uint16_t *)0xEBE000)
#define NP_BG_COLUMNAS   64
#define NP_BG_FILAS      64

/* La RAM de patrones: 32 KB en $EB8000, 128 bytes por patron de 16x16. De aqui
   comen los sprites **y** la capa de fondo, y ademas la tabla de nombres esta
   metida dentro (los ultimos 8 KB), asi que quedan 192 patrones y ese es el
   limite de verdad de esta maquina, no los 128 sprites. */
#define NP_PCG           ((volatile uint8_t *)0xEB8000)
#define NP_PATRONES      192
#define NP_PATRON_BYTES  128

/* --- la pantalla que dibujamos ------------------------------------------
 *
 * La simulacion es de 320x224 en las seis maquinas, y aqui se ensena entera:
 * al CRTC se le pide una imagen de ese tamano en vez de quedarse con un modo
 * de catalogo. Comprobado en el emulador: con el temporizado nuestro la capa
 * de fondo llena los 320x224 y los sprites caen donde tienen que caer, asi que
 * no hace falta recortar a 256 como se temia.
 *
 * El color 15 del primer bloque de paleta es el del marcador (ver arriba).
 */
#define NP_HUD_COLOR     15
#define NP_ANCHO         NP_SCREEN_W
#define NP_ALTO          NP_SCREEN_H
#define NP_COLUMNAS      (NP_ANCHO / NP_TILE)     /* 20 columnas de tiles */
#define NP_FILAS         (NP_ALTO / NP_TILE)      /* 14 filas */

void np_video_init(void);
void np_video_frame(const NpWorld *w);
void np_wait_vblank(void);
uint16_t np_input_read(void);
uint16_t np_input_read2(void);

extern const uint8_t np_font_data[];    /* fuente de 8x8, un bit por pixel */

/* marcador (np_hud.c) */
void np_hud_clear(void);
void np_hud_print(uint8_t col, uint8_t fila, const char *texto);
void np_hud_number(uint8_t col, uint8_t fila, uint32_t valor, uint8_t digitos);
void np_hud_draw(const NpWorld *w);

/* sonido (np_sound.c) */
void np_sound_init(void);
void np_sound_frame(const NpWorld *w);

#endif /* NP_X68K_H */
