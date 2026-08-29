| arranque.S - lo primero que se ejecuta del juego en el X68000.
|
| Human68k carga el programa donde le cabe y salta al principio con la pila ya
| puesta, asi que aqui hay menos que hacer que en un cartucho: basta con dejar
| la BSS a cero (el .X no la trae, solo dice cuanto ocupa) y llamar a main.
|
| No se vuelve: el juego es un bucle sin fin. Si alguna vez volviera, se sale
| al sistema con DOS _EXIT en vez de seguir ejecutando basura.

        | sin esto el enlazador avisa de que la pila seria ejecutable
        .section .note.GNU-stack,"",@progbits

        .text
        .globl  _start
_start:
        | La BSS va detras del programa y Human68k no la limpia. Las dos
        | direcciones se cargan absolutas y **no** relativas al PC: un juego
        | pasa de 32 KB enseguida y ahi el desplazamiento de 16 bits del 68000
        | se queda corto. Human68k las corrige con la tabla del .X.
        move.l  #__bss_start, %a0
        move.l  #__bss_end, %a1
        cmpa.l  %a0, %a1
        bls     1f
0:      clr.b   (%a0)+
        cmpa.l  %a0, %a1
        bhi     0b
1:
        jsr     main

        | por si acaso: devolver el control al sistema
        clr.w   -(%sp)
        move.w  #0x4c00, -(%sp)         | DOS _EXIT2
        trap    #15
        addq.l  #4, %sp
2:      bra     2b
