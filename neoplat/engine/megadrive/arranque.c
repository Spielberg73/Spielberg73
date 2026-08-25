/* arranque.c - lo primero que ejecuta la Mega Drive al encenderse.
 *
 * Un cartucho empieza con dos cosas en direcciones fijas:
 *   $000000  tabla de vectores: la primera palabra larga es el valor inicial
 *            de la pila y la segunda, la direccion por la que arranca
 *   $000100  cabecera del cartucho (nombre, region, tamano, suma de control)
 *
 * La suma de control y el tamano los rellena `arreglar_rom.py` al terminar de
 * compilar, porque dependen del binario final.
 */

#include <stdint.h>

int main(void);

extern uint32_t _data_load, _data_start, _data_end, _bss_start, _bss_end;

void _start(void);
static void np_parada(void);

/* --- tabla de vectores ------------------------------------------------- */
__attribute__((section(".vectors"), used))
void *const np_vectores[64] = {
    (void *)0x00FFFE00,          /* pila: al final de los 64 KB de RAM */
    (void *)_start,
    /* el resto de excepciones e interrupciones se quedan quietas */
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada, (void *)np_parada, (void *)np_parada,
    (void *)np_parada, (void *)np_parada
};

/* --- cabecera del cartucho --------------------------------------------- */
__attribute__((section(".header"), used))
const char np_cabecera[256] =
    "SEGA MEGA DRIVE "                                  /* 0x100 consola     */
    "(C)NEOPLAT 2025 "                                  /* 0x110 propietario */
    "                                                "  /* 0x120 nombre      */
    "                                                "  /* 0x150 nombre int. */
    "GM 00000000-00"                                    /* 0x180 serie       */
    "\0\0"                                              /* 0x18E suma        */
    "J               "                                  /* 0x190 mandos      */
    "\0\0\0\0"                                          /* 0x1A0 inicio ROM  */
    "\0\0\0\0"                                          /* 0x1A4 fin ROM     */
    "\0\xff\0\0" "\0\xff\xff\xff"                       /* 0x1A8 RAM         */
    "            "                                      /* 0x1B0 SRAM        */
    "            "                                      /* 0x1BC modem       */
    "                                        "          /* 0x1C8 notas       */
    "JUE             ";                                 /* 0x1F0 region      */

static void np_parada(void)
{
    for (;;) ;
}

void _start(void)
{
    uint32_t *origen, *destino, *fin;

    /* copiar las variables con valor inicial de la ROM a la RAM */
    origen = &_data_load;
    destino = &_data_start;
    fin = &_data_end;
    while (destino < fin) *destino++ = *origen++;

    /* y poner a cero las que no lo tienen */
    destino = &_bss_start;
    fin = &_bss_end;
    while (destino < fin) *destino++ = 0;

    main();
    np_parada();
}
