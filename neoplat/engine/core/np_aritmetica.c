/* np_aritmetica.c - multiplicar y dividir enteros de 32 bits en un 68000.
 *
 * El 68000 sabe multiplicar 16x16 y dividir 32/16, pero no tiene instrucciones
 * para 32x32 ni para 32/32: cuando el compilador se encuentra un `*`, un `/` o
 * un `%` de 32 bits, genera una llamada a una rutina auxiliar (__mulsi3,
 * __divsi3, __modsi3 y sus versiones sin signo).
 *
 * Esas rutinas suelen venir en la libgcc del compilador, pero **la libgcc de un
 * compilador de 68k para Linux esta hecha para 68020**, y lleva instrucciones
 * que el 68000 no entiende (por ejemplo `bsr.l`): el juego se cuelga con una
 * excepcion de "linea F" en cuanto hace la primera division. Por eso NeoPlat
 * trae las suyas y no enlaza libgcc: asi da igual que compilador de 68000 use
 * cada uno.
 *
 * Estan escritas sin usar `*`, `/` ni `%` de 32 bits a proposito: si los
 * usaran, el compilador las convertiria en llamadas a si mismas.
 */

#include "np_types.h"

/* El compilador las llama por estos nombres; no las llama nadie mas. */
int32_t __mulsi3(int32_t a, int32_t b);
uint32_t __udivsi3(uint32_t a, uint32_t b);
uint32_t __umodsi3(uint32_t a, uint32_t b);
int32_t __divsi3(int32_t a, int32_t b);
int32_t __modsi3(int32_t a, int32_t b);

/* 16x16 -> 32. En el 68000 es una sola instruccion (mulu.w); en el ordenador,
   donde se ejecutan las pruebas, es una multiplicacion normal. */
static uint32_t np_mul16(uint16_t a, uint16_t b)
{
#if defined(__mc68000__) || (defined(__m68k__) && !defined(__mc68020__))
    uint32_t r = a;
    __asm__ ("mulu%.w %1,%0" : "+d" (r) : "dmi" (b));
    return r;
#else
    return (uint32_t)a * (uint32_t)b;
#endif
}

int32_t __mulsi3(int32_t a, int32_t b)
{
    uint32_t x = (uint32_t)a, y = (uint32_t)b;
    uint32_t bajo = np_mul16((uint16_t)x, (uint16_t)y);
    uint32_t cruce = np_mul16((uint16_t)(x >> 16), (uint16_t)y)
                   + np_mul16((uint16_t)x, (uint16_t)(y >> 16));
    return (int32_t)(bajo + (cruce << 16));
}

/* Division larga en binario: 32 restas y 32 desplazamientos como mucho. */
static uint32_t np_dividir(uint32_t dividendo, uint32_t divisor, uint32_t *resto)
{
    uint32_t cociente = 0;
    uint32_t bit = 1;
    if (divisor == 0) {              /* dividir por cero: como hace libgcc */
        *resto = dividendo;
        return 0xFFFFFFFFu;
    }
    while (divisor <= dividendo && !(divisor & 0x80000000u)) {
        divisor <<= 1;
        bit <<= 1;
    }
    while (bit) {
        if (dividendo >= divisor) {
            dividendo -= divisor;
            cociente |= bit;
        }
        divisor >>= 1;
        bit >>= 1;
    }
    *resto = dividendo;
    return cociente;
}

uint32_t __udivsi3(uint32_t a, uint32_t b)
{
    uint32_t resto;
    return np_dividir(a, b, &resto);
}

uint32_t __umodsi3(uint32_t a, uint32_t b)
{
    uint32_t resto;
    np_dividir(a, b, &resto);
    return resto;
}

/* Con signo: se divide en positivo y se le pone el signo que toca. En C el
   cociente se trunca hacia cero y el resto se queda con el signo del
   dividendo. */
int32_t __divsi3(int32_t a, int32_t b)
{
    int negativo = 0;
    uint32_t resto, cociente;
    if (a < 0) { a = -a; negativo = !negativo; }
    if (b < 0) { b = -b; negativo = !negativo; }
    cociente = np_dividir((uint32_t)a, (uint32_t)b, &resto);
    return negativo ? -(int32_t)cociente : (int32_t)cociente;
}

int32_t __modsi3(int32_t a, int32_t b)
{
    int negativo = a < 0;
    uint32_t resto;
    if (a < 0) a = -a;
    if (b < 0) b = -b;
    np_dividir((uint32_t)a, (uint32_t)b, &resto);
    return negativo ? -(int32_t)resto : (int32_t)resto;
}
