/* Mapa de memoria de un juego de X68000.
 *
 * Human68k coloca el programa donde le cabe y corrige las direcciones con la
 * tabla del .X, asi que aqui se enlaza en 0 y hacer_x.py se encarga del resto:
 * cada direccion absoluta se guarda relativa al principio del programa.
 *
 * Todo va en una sola seccion seguida -codigo, datos y BSS- porque el cargador
 * de Human68k los pone asi en memoria y el arranque limpia la BSS a mano.
 */
OUTPUT_FORMAT("elf32-m68k")
OUTPUT_ARCH(m68k)
ENTRY(_start)

SECTIONS
{
    . = 0;
    .text : {
        src/arranque.o(.text)
        *(.text .text.*)
        . = ALIGN(4);
        *(.rodata .rodata.*)
        . = ALIGN(4);
        *(.data .data.*)
        . = ALIGN(4);
    }
    __bss_start = .;
    .bss (NOLOAD) : {
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
    }
    __bss_end = .;

    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame) }
}
