/* megadrive.ld - reparto de memoria de un cartucho de Mega Drive.
 *
 *   ROM  $000000 en adelante: vectores, cabecera, codigo y datos
 *   RAM  $FF0000 - $FFFFFF (64 KB): variables y pila
 *
 * Las variables con valor inicial viven en la ROM y se copian a la RAM al
 * arrancar (lo hace _start en arranque.c).
 */
OUTPUT_ARCH(m68k)
ENTRY(_start)

MEMORY
{
    rom (rx)  : ORIGIN = 0x000000, LENGTH = 4M
    ram (rwx) : ORIGIN = 0xFF0000, LENGTH = 64K
}

SECTIONS
{
    .vectors 0x000000 : { KEEP(*(.vectors)) } > rom
    .header  0x000100 : { KEEP(*(.header)) } > rom

    .text 0x000200 :
    {
        *(.text .text.*)
        *(.rodata .rodata.*)
        . = ALIGN(2);
    } > rom

    .data :
    {
        _data_start = .;
        *(.data .data.*)
        . = ALIGN(2);
        _data_end = .;
    } > ram AT > rom
    _data_load = LOADADDR(.data);

    .bss (NOLOAD) :
    {
        _bss_start = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(2);
        _bss_end = .;
    } > ram

    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
