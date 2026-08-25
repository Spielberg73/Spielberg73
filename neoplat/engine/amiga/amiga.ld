/* amiga.ld - reparto de memoria de un ejecutable de Amiga.
 *
 * Aqui no hay direcciones fijas: el ejecutable se compone de dos trozos
 * ("hunks") que AmigaDOS carga donde quiere. El script solo tiene que dejar
 * cada trozo seguido y en su sitio:
 *
 *   prog   codigo, constantes y variables con valor inicial -> hunk 0
 *   datos  variables sin valor inicial (el mapa de bits)    -> hunk 1 (BSS)
 *
 * Los dos hunks se piden en RAM chip, porque el copper, el blitter y Paula
 * solo llegan a esa mitad de la memoria.
 *
 * Las dos zonas se enlazan en direcciones muy separadas a proposito: asi
 * hacer_ejecutable.py sabe, mirando el valor de cada referencia, a que hunk
 * apunta.
 */
OUTPUT_ARCH(m68k)
ENTRY(_start)

MEMORY
{
    prog  (rwx) : ORIGIN = 0x00000000, LENGTH = 8M
    datos (rw)  : ORIGIN = 0x40000000, LENGTH = 8M
}

SECTIONS
{
    .text 0x00000000 :
    {
        KEEP(*(.text.arranque))
        *(.text .text.*)
        *(.rodata .rodata.*)
        *(.data .data.*)
        . = ALIGN(4);
    } > prog

    .bss (NOLOAD) :
    {
        _bss_start = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
        _bss_end = .;
    } > datos

    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
