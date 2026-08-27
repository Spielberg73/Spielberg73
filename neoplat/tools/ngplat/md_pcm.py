"""El driver de muestras digitales de la Mega Drive: un programa para el Z80.

La Mega Drive tiene el DAC del YM2612 (canal 6 en modo DAC, registro $2A), pero
alguien tiene que darle un byte cada 125 microsegundos, y eso el 68000 no lo
puede hacer sin dejar el juego tirado. Lo hace el **Z80**, que para eso esta:
tiene su propia RAM de 8 KB, ve el YM2612 en $4000 y puede leer el cartucho por
una ventana de 32 KB en $8000.

El reparto queda asi:

  - las **notas** las sigue tocando el 68000 por el PSG, como siempre
    (engine/megadrive/np_sound.c). El PSG y el YM2612 son chips distintos, asi
    que la musica y la muestra suenan a la vez sin estorbarse;
  - las **muestras** las toca este driver.

**Como se le pide una muestra.** Un bloque de ocho bytes en la RAM del Z80. El
68000 pide el bus (BUSREQ), escribe el bloque -banco, direccion y largo- y por
ultimo cambia `tick`; el Z80 esta parado mientras tanto, asi que no hay que
sincronizar nada mas. Al soltar el bus, el Z80 ve que `tick` ya no es `visto` y
arranca.

**El reloj.** No hay temporizador: el ritmo lo marca el propio bucle, contando
ciclos. El bucle mide %d ciclos de los 3.579.545 por segundo del Z80, o sea
%d muestras por segundo, y a esa frecuencia exacta se remuestrea el WAV al
compilar. Los accesos al cartucho llevan alguna espera por el arbitraje del bus,
asi que la frecuencia real baja un pelo; en un efecto corto no se nota.

**La ventana de 32 KB.** El Z80 no ve el cartucho entero, sino 32 KB a la vez,
elegidos con el registro de banco de $6000 (nueve bits, uno por escritura). Si
una muestra cruza el borde del banco, el bucle lo nota (HL pasa de $FFFF a
$0000) y cambia de banco sobre la marcha.
"""

from __future__ import annotations

from typing import Dict, Tuple

from .z80 import ensamblar

RELOJ = 3579545                  # el Z80 de la Mega Drive
RAM = 0x1F00                     # el bloque compartido, al final de la RAM

# Bloque compartido (direcciones del Z80)
CMD_TICK = RAM + 0               # lo cambia el 68000 para pedir una muestra
CMD_VISTO = RAM + 1              # lo que ya ha atendido el Z80
CMD_BANCO = RAM + 2              # 9 bits, en dos bytes
CMD_DIR = RAM + 4                # $8000..$FFFF, dentro de la ventana
CMD_LARGO = RAM + 6              # cuantos bytes quedan

# Los ciclos del bucle, contados a mano sobre el juego de instrucciones (la
# cuenta esta en el comentario de `_bucle`). Cambiar el bucle obliga a rehacer
# esta cuenta: tests/test_md_pcm.py la comprueba instruccion a instruccion.
RETARDO = 26                     # vueltas del bucle de espera
CICLOS = 85 + 14 * RETARDO       # 449
RITMO = RELOJ // CICLOS          # 7972 muestras por segundo


def fuente() -> str:
    return """
; Driver de muestras de la Mega Drive. Lo genera tools/ngplat/md_pcm.py.
        org     $0000

inicio:
        di
        im      1
        ld      sp,$1F00

; El YM2612: el DAC encendido (registro $2B, bit 7) y la direccion dejada
; apuntando al registro del DAC ($2A), que es donde iran todos los bytes. La
; direccion se escribe en $4000 y el dato en $4001.
        ld      a,$2B
        ld      ($4000),a
        ld      a,$80
        ld      ($4001),a
        ld      a,$2A
        ld      ($4000),a
        ld      a,$80                 ; silencio (el DAC va sin signo)
        ld      ($4001),a

; A esperar a que el 68000 pida algo. Mientras escribe el bloque tiene el bus
; pedido, o sea que el Z80 esta parado: no hay nada que sincronizar.
espera:
        ld      a,($1F00)             ; tick
        ld      b,a
        ld      a,($1F01)             ; visto
        cp      b
        jr      z,espera
        ld      a,b
        ld      ($1F01),a             ; apuntado

        call    poner_banco
        ld      hl,($1F04)            ; donde empieza, dentro de la ventana
        ld      bc,($1F06)            ; cuantos bytes

; --- el bucle que suena ------------------------------------------------
; No hay temporizador: el ritmo lo marca esta cuenta de ciclos.
;
;   ld a,(hl)     7      el byte de la muestra
;   ld ($4001),a 13      al DAC
;   inc hl        6
;   ld a,h        4
;   or a          4      si HL ha dado la vuelta, toca cambiar de banco
;   jp z,otro    10
;   dec bc        6
;   ld a,b        4
;   or c          4
;   jp z,fin     10
;   ld a,RETARDO  7
; retardo:
;   dec a         4      \\ 14 ciclos por vuelta
;   jp nz,retardo 10     /
;   jp bucle     10
;                ---
;                 85 + 14 * RETARDO
bucle:
        ld      a,(hl)
        ld      ($4001),a
        inc     hl
        ld      a,h
        or      a
        jp      z,otro_banco
        dec     bc
        ld      a,b
        or      c
        jp      z,fin
        ld      a,%d
retardo:
        dec     a
        jp      nz,retardo
        jp      bucle

; La muestra ha cruzado el borde de los 32 KB: se sube el banco y HL vuelve al
; principio de la ventana. Pasa como mucho una vez por muestra.
otro_banco:
        push    bc
        ld      hl,$1F02              ; banco = banco + 1, en nueve bits
        inc     (hl)
        jp      nz,ya_subido
        inc     hl
        inc     (hl)
ya_subido:
        call    poner_banco
        pop     bc
        ld      hl,$8000
        dec     bc
        ld      a,b
        or      c
        jp      z,fin
        jp      bucle

fin:
        ld      a,$80                 ; el DAC, al silencio
        ld      ($4001),a
        jp      espera

; El registro de banco de $6000 se escribe **bit a bit**, del bajo al alto y
; uno por escritura: nueve escrituras para los nueve bits que eligen cuales
; 32 KB del cartucho se ven en $8000. `srl b` + `rr c` desplaza BC entero un
; bit a la derecha, asi que el bit que toca queda siempre en A0.
poner_banco:
        ld      a,($1F02)
        ld      c,a
        ld      a,($1F03)
        ld      b,a
        ld      d,9
un_bit:
        ld      a,c
        ld      ($6000),a
        srl     b
        rr      c
        dec     d
        jp      nz,un_bit
        ret
""" % RETARDO


def generar() -> Tuple[bytes, Dict[str, int]]:
    """El driver ya ensamblado y donde ha quedado cada etiqueta."""
    return ensamblar(fuente())
