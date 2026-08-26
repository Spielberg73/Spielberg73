/* arranque.S - lo primero que ejecuta el cartucho.
 *
 * La Jaguar no tiene tabla de vectores en el cartucho: la consola lee la pila
 * de cart+$400 y el punto de entrada de cart+$404, y empieza a ejecutar ahi.
 * Eso lo pone el generador de la ROM; esto es lo que hay en esa direccion.
 */
        .section .entrada,"ax"
        .globl  _start
_start:
        move.l  #0x001FFFFC,%sp             /* pila al final de la DRAM     */
        move.l  #0x00070007,0xF0210C        /* G_END: GPU en big-endian     */
        move.l  #0x00070007,0xF1A10C        /* D_END: DSP igual             */
        move.w  #0xFFFF,0xF0004E            /* VI: sin interrupcion de video */
        lea     _data_load,%a0              /* copiar .data de la ROM a RAM  */
        lea     _data_start,%a1
        lea     _data_end,%a2
1:      cmpa.l  %a1,%a2
        bls.s   2f
        move.l  (%a0)+,(%a1)+
        bra.s   1b
2:      lea     _bss_start,%a1              /* y borrar .bss                 */
        lea     _bss_end,%a2
        moveq   #0,%d0
3:      cmpa.l  %a1,%a2
        bls.s   4f
        move.l  %d0,(%a1)+
        bra.s   3b
4:      jsr     main
5:      bra.s   5b
