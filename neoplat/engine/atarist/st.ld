/* st.ld - reparto de memoria de un ejecutable de GEMDOS.
 *
 * En el ST, al contrario que en el Amiga, el programa es **un bloque seguido**:
 * TOS lo carga donde le cabe y le suma la direccion de carga a las palabras
 * largas que dice la tabla de relocalizacion. Asi que aqui no hay dos zonas
 * separadas: el codigo, las constantes y los datos van del cero para arriba y
 * la BSS detras, que es justo como los coloca TOS en memoria.
 *
 * TOS entrega la BSS puesta a cero, asi que las dos pantallas y el marcador no
 * hace falta limpiarlos.
 */
OUTPUT_ARCH(m68k)
ENTRY(_start)

SECTIONS
{
    .text 0x00000000 :
    {
        KEEP(*(.text.arranque))
        *(.text .text.*)
        *(.rodata .rodata.*)
        *(.data .data.*)
        . = ALIGN(4);
    }

    .bss (NOLOAD) :
    {
        _bss_start = .;
        *(.bss .bss.*)
        *(COMMON)
        . = ALIGN(4);
        _bss_end = .;
    }

    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
