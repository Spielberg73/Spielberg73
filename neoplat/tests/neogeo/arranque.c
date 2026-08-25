/* Arranque minimo para el banco de pruebas: la Neo Geo de verdad arranca por
   la BIOS, que llama al juego; aqui se entra directo en main(). */
#include <stdint.h>
int main(void);
void _start(void);
static void parada(void) { for (;;) ; }

__attribute__((section(".vectors"), used))
void *const vectores[8] = {
    (void *)0x0010FF00,      /* pila, al final de la RAM de trabajo */
    (void *)_start,
    (void *)parada, (void *)parada, (void *)parada, (void *)parada,
    (void *)parada, (void *)parada
};

extern uint32_t _data_load, _data_start, _data_end, _bss_start, _bss_end;

void _start(void)
{
    uint32_t *o = &_data_load, *d = &_data_start, *f = &_data_end;
    while (d < f) *d++ = *o++;
    d = &_bss_start; f = &_bss_end;
    while (d < f) *d++ = 0;
    main();
    parada();
}
