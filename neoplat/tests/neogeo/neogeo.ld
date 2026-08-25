OUTPUT_ARCH(m68k)
ENTRY(_start)
MEMORY {
    rom (rx)  : ORIGIN = 0x000000, LENGTH = 1M
    ram (rwx) : ORIGIN = 0x100000, LENGTH = 64K
}
SECTIONS {
    .vectors 0x000000 : { KEEP(*(.vectors)) } > rom
    .text : { *(.text .text.*) *(.rodata .rodata.*) . = ALIGN(2); } > rom
    .data : { _data_start = .; *(.data .data.*) . = ALIGN(2); _data_end = .; } > ram AT > rom
    _data_load = LOADADDR(.data);
    .bss (NOLOAD) : { _bss_start = .; *(.bss .bss.*) *(COMMON) . = ALIGN(2); _bss_end = .; } > ram
    /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
