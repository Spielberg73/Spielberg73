; =============================================================================
;  Cargador en disco para CPC 6128 (zxcpc)
; =============================================================================
;  RUN"DISC"  carga cuatro bloques de 16K en los bancos extra 4-7 usando el
;  firmware y luego, ya sin firmware, los coloca en los 64K base:
;
;    banco 5 -> $8000 (temporal) -> $4000     (bloque B, $4000-$7FFF)
;    banco 6 -> $8000                          (bloque C, $8000-$BFFF)
;    banco 4 -> $0000                          (bloque A: HAL + pantalla)
;    banco 7 -> $C000   (lo hace STUB2, que vive dentro del bloque A)
;
;  STUB1 se ejecuta en $FE00 (bloque D, que se copia el último) y STUB2 está
;  en un hueco libre del HAL, así ninguno se pisa a sí mismo.
; =============================================================================

CAS_IN_OPEN     equ $BC77
CAS_IN_DIRECT   equ $BC83
CAS_IN_CLOSE    equ $BC7A
TXT_OUTPUT      equ $BB5A

KL_INIT_BACK    equ $BCCE

        org $8000
start:  ; RUN" de un binario restaura los vectores del firmware: reactivar AMSDOS
        ld c,7
        ld de,$0040
        ld hl,$ABFF
        call KL_INIT_BACK
        ld hl,msg
        call print
        ld a,$C4
        ld hl,name_a
        call load
        ld a,$C5
        ld hl,name_b
        call load
        ld a,$C6
        ld hl,name_c
        call load
        ld a,$C7
        ld hl,name_d
        call load
        di
        ld bc,$7FC0
        out (c),c
        ld hl,stub1
        ld de,$FE00
        ld bc,stub1_end-stub1
        ldir
        jp $FE00

; A = configuración de RAM, HL = nombre (8+3 caracteres con punto: 12 bytes)
load:   ld b,$7F
        ld c,a
        out (c),c
        ld b,12
        ld de,$9000             ; búfer de 2K para AMSDOS
        call CAS_IN_OPEN
        jr nc,fail
        ld hl,$4000
        call CAS_IN_DIRECT
        jr nc,fail
        call CAS_IN_CLOSE
        ld bc,$7FC0
        out (c),c
        ld a,'.'
        call TXT_OUTPUT
        ret
fail:   ld bc,$7FC0
        out (c),c
        ld hl,err
        call print
.h:     jr .h

print:  ld a,(hl)
        or a
        ret z
        call TXT_OUTPUT
        inc hl
        jr print

msg:    db "zxcpc: cargando ",0
err:    db 13,10,"Error de disco",0
name_a: db "ZXCPC   .A  "
name_b: db "ZXCPC   .B  "
name_c: db "ZXCPC   .C  "
name_d: db "ZXCPC   .D  "

; ---- STUB1: se copia a $FE00 y se ejecuta sin firmware ----
stub1:
        ; modo 1, ROMs desactivadas
        ld bc,$7F8D
        out (c),c
        ; banco 5 -> $8000
        ld bc,$7FC5
        out (c),c
        ld hl,$4000
        ld de,$8000
        ld bc,$4000
        ldir
        ; $8000 -> $4000 (banco base 1)
        ld bc,$7FC0
        out (c),c
        ld hl,$8000
        ld de,$4000
        ld bc,$4000
        ldir
        ; banco 6 -> $8000
        ld bc,$7FC6
        out (c),c
        ld hl,$4000
        ld de,$8000
        ld bc,$4000
        ldir
        ; banco 4 -> $0000
        ld bc,$7FC4
        out (c),c
        ld hl,$4000
        ld de,$0000
        ld bc,$4000
        ldir
        ; banco 7 visible en $4000 para que STUB2 lo copie a $C000
        ld bc,$7FC7
        out (c),c
        jp STUB2
stub1_end:
