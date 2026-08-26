/* arranque.c - lo primero que ejecuta el ST al lanzar el juego.
 *
 * El juego va en la carpeta AUTO del disquete, asi que TOS lo ejecuta al
 * encender, antes de sacar el escritorio, y en **modo usuario**. Desde ahi no
 * se puede tocar ni el Shifter ni el chip de sonido, asi que lo primero es
 * pedir modo supervisor con la llamada Super de GEMDOS.
 *
 * Super(0) tiene una particularidad util: deja la pila de supervisor donde
 * estaba la de usuario, asi que el `addq.l #6,sp` de despues limpia los
 * parametros del sitio correcto y la ejecucion sigue como si nada.
 *
 * Despues se suben todas las mascaras de interrupcion (SR = $2700). A partir
 * de ahi el juego se queda con la maquina entera: nada de TOS vuelve a correr,
 * ni el reloj, ni el manejador del teclado. El teclado se lee a mano (ver
 * np_video.c) y el frame se cuenta mirando por donde va el haz, que es lo que
 * hay cuando no se quiere que nadie mas toque el hardware.
 */

#include "np_st.h"

int main(void);

__attribute__((section(".text.arranque"), used))
void _start(void)
{
    __asm__ volatile (
        "clr.l   -(%%sp)\n\t"            /* Super(0L): a modo supervisor */
        "move.w  #0x20,-(%%sp)\n\t"
        "trap    #1\n\t"
        "addq.l  #6,%%sp\n\t"
        "move.w  #0x2700,%%sr"           /* y que no interrumpa nadie */
        ::: "d0", "d1", "d2", "a0", "a1", "a2", "cc", "memory");
    main();
    for (;;) ;
}
