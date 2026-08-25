/* arranque.c - lo primero que ejecuta el Amiga al lanzar el juego.
 *
 * Un ejecutable de AmigaDOS no se carga en una direccion fija: el sistema lo
 * mete donde le cabe y arregla las direcciones (por eso el compilador de
 * NeoPlat genera "hunks" con su tabla de relocalizacion). Lo unico seguro es
 * que la ejecucion empieza en el primer byte del primer hunk, y de eso se
 * encarga el script del enlazador: ahi va `_start`.
 *
 * El juego se queda con la maquina entera (para eso apaga las interrupciones y
 * la DMA en np_amiga_init) y no la devuelve: se sale apagando o reiniciando,
 * como los juegos de la epoca. Las variables sin valor inicial estan en un
 * hunk BSS, que AmigaDOS ya entrega puesto a cero.
 */

#include "np_amiga.h"

int main(void);

__attribute__((section(".text.arranque"), used))
void _start(void)
{
    main();
    for (;;) ;
}
