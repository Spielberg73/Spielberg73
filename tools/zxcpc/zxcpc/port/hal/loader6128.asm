; =============================================================================
;  Cargador en disco para CPC 6128 (zxcpc)
; =============================================================================
;  RUN"DISC"  carga cuatro bloques de 16K usando el firmware y luego, ya sin
;  firmware, los coloca en los 64K base:
;
;    bloque B ($4000-$7FFF) se carga directamente en su sitio
;    banco 6 -> $8000                          (bloque C, $8000-$BFFF)
;    banco 4 -> $0000                          (bloque A: HAL + pantalla)
;    banco 7 -> $C000   (lo hace STUB2, que vive dentro del bloque A)
;
;  Si ROMCOPY = 1, el bloque R (copia de la ROM del Spectrum) se queda en el
;  banco 5, de donde lo lee el HAL.
;
;  Si Z128 = 1 (576K), los bancos 0, 1, 3, 4, 6 y 7 del Spectrum (ficheros X0-X7)
;  van al bloque 3 del banco de 64K de su número en la ampliación, y el bloque D
;  espera en el banco 5 (el bloque 3 del banco 0 de la ampliación es el banco 0
;  del Spectrum).
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
        ld a,$C0
        ld hl,name_b
        call load
        if ROMCOPY
        ld a,$C5
        ld hl,name_r
        call load
        endif
        ld a,$C6
        ld hl,name_c
        call load
        if Z128
        ld a,$C5
        else
        ld a,$C7
        endif
        ld hl,name_d
        call load
        if Z128
        ld hl,banks
.bk:    ld a,(hl)
        or a
        jr z,.bd
        inc hl
        push hl
        call load
        pop hl
        ld de,12
        add hl,de
        jr .bk
.bd:
        endif
        di
        ld bc,$7FC0
        out (c),c
        ld hl,stub1
        ld de,$FE00
        ld bc,stub1_all_end-stub1
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
name_r: db "ZXCPC   .R  "
        if Z128
banks:  db $C7+0*8,"ZXCPC   .X0 "
        db $C7+1*8,"ZXCPC   .X1 "
        db $C7+3*8,"ZXCPC   .X3 "
        db $C7+4*8,"ZXCPC   .X4 "
        db $C7+6*8,"ZXCPC   .X6 "
        db $C7+7*8,"ZXCPC   .X7 "
        db 0
        endif

; ---- STUB1: se copia a $FE00 y se ejecuta sin firmware ----
stub1:
        ; modo 1, ROMs desactivadas
        ld bc,$7F8D
        out (c),c
        ; CRTC (tabla copiada a $FF00 junto con el stub)
        ld hl,$FE00+stub1_crtc-stub1
        ld bc,$BC00
.c:     out (c),c
        ld a,(hl)
        inc b
        out (c),a
        dec b
        inc hl
        inc c
        ld a,c
        cp 14
        jr nz,.c
        ; paleta (16 tintas + borde)
        ld hl,$FE00+stub1_pal-stub1
        ld bc,$7F00
.p:     out (c),c
        ld a,(hl)
        out (c),a
        inc hl
        inc c
        ld a,c
        cp 17
        jr nz,.p
        ; PPI y PSG: registro 7 = $3F (tonos apagados), registro 8 seleccionado
        ld bc,$F782
        out (c),c
        ld bc,$F407
        out (c),c
        ld bc,$F6C0
        out (c),c
        ld bc,$F600
        out (c),c
        ld bc,$F43F
        out (c),c
        ld bc,$F680
        out (c),c
        ld bc,$F600
        out (c),c
        ld bc,$F408
        out (c),c
        ld bc,$F6C0
        out (c),c
        ld bc,$F600
        out (c),c
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
        ; bloque D visible en $4000 para que STUB2 lo copie a $C000
        if Z128
        ld bc,$7FC5
        else
        ld bc,$7FC7
        endif
        out (c),c
        jp STUB2
stub1_end:
