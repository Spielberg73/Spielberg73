; Juego de prueba para Amstrad CPC SIN firmware (dominio público, para zxcpc)
;
; Todo va directo al hardware, como en muchos juegos comerciales:
;   - instala su propia rutina de interrupción en $38 (JP isr)
;   - modo, paleta y borde con el gate array; CRTC con los valores estándar
;   - teclado leído línea a línea con el PPI y el PSG
;   - sincronización contando interrupciones (6 por frame) y HALT
;   - sprite de modo 0 dibujado con LD (HL),A y LD (IX+d),A
;
; Controles: cursores o Q/A/O/P.

        org $1000

start:  di
        ld sp,$0FFE
        ; rutina de interrupción propia
        ld a,$C3
        ld ($0038),a
        ld hl,isr
        ld ($0039),hl
        im 1
        ; modo 0, ROMs desactivadas
        ld bc,$7F8C
        out (c),c
        ; paleta: 16 plumas + borde
        ld hl,palette
        ld e,0
.pal:   ld bc,$7F00
        out (c),e
        ld a,(hl)
        out (c),a
        inc hl
        inc e
        ld a,e
        cp 17
        jr nz,.pal
        ; CRTC estándar (base $C000)
        ld hl,crtc
        ld e,0
.crtc:  ld b,$BC
        out (c),e
        ld b,$BD
        ld a,(hl)
        out (c),a
        inc hl
        inc e
        ld a,e
        cp 14
        jr nz,.crtc
        ; borrar la pantalla
        ld hl,$C000
        ld de,$C001
        ld bc,$3FFF
        ld (hl),0
        ldir
        ; marco superior de pluma 5 (LD (IX+d),A)
        ld ix,$C000+40*80
        ld a,%11110000 & $F0 | %00001010   ; píxeles de plumas mezcladas
        ld b,80
.fr:    ld (ix+0),a
        inc ix
        djnz .fr
        call draw
        ei

main:   ld a,(ticks)
.w:     ld hl,ticks
        cp (hl)
        jr z,.w                 ; esperar al siguiente tick
        ld a,(ticks)
        and 3
        jr nz,main              ; mover cada 4 ticks
        call erase
        call keys
        call draw
        jr main

isr:    push af
        push hl
        ld hl,subtick
        inc (hl)
        ld a,(hl)
        cp 6
        jr c,.x
        ld (hl),0
        ld hl,ticks
        inc (hl)                ; un tick por frame (6 interrupciones)
.x:     pop hl
        pop af
        ei
        ret

; lee la línea A del teclado -> A (bits a 0 = pulsado)
kline:  ld d,a
        ld bc,$F40E
        out (c),c
        ld bc,$F6C0
        out (c),c
        ld bc,$F600
        out (c),c
        ld bc,$F792
        out (c),c
        ld a,d
        or $40
        ld b,$F6
        out (c),a
        ld b,$F4
        in a,(c)
        ld bc,$F782
        out (c),c
        ld bc,$F600
        out (c),c
        ret

keys:   ld a,0                  ; línea 0: cursores
        call kline
        ld e,a
        bit 0,e                 ; arriba
        call z,up
        bit 2,e                 ; abajo
        call z,down
        bit 1,e                 ; derecha
        call z,right
        ld a,1
        call kline
        bit 0,a                 ; izquierda
        call z,left
        ld a,8                  ; línea 8: Q (bit 3), A (bit 5)
        call kline
        ld e,a
        bit 3,e
        call z,up
        bit 5,e
        call z,down
        ld a,3                  ; línea 3: P (bit 3)
        call kline
        bit 3,a
        call z,right
        ld a,4                  ; línea 4: O (bit 2)
        call kline
        bit 2,a
        call z,left
        ret

left:   ld a,(xpos)
        or a
        ret z
        dec a
        ld (xpos),a
        ret
right:  ld a,(xpos)
        cp 76
        ret z
        inc a
        ld (xpos),a
        ret
up:     ld a,(ypos)
        or a
        ret z
        dec a
        ld (ypos),a
        ret
down:   ld a,(ypos)
        cp 23
        ret z
        inc a
        ld (ypos),a
        ret

scraddr:
        ld a,(ypos)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl
        add hl,de
        ld a,(xpos)
        ld e,a
        ld d,$C0
        add hl,de
        ret

draw:   call scraddr
        ld de,sprite
        ld c,8
.l:     push hl
        ld b,4
.b:     ld a,(de)
        xor (hl)
        ld (hl),a
        inc hl
        inc de
        djnz .b
        pop hl
        ld a,h
        add a,8
        ld h,a
        dec c
        jr nz,.l
        ret

erase:  jr draw

; modo 0: cada byte son 2 píxeles; $C0 = pluma 3 en los dos, $0C = pluma 12...
sprite: db $00,$3C,$3C,$00
        db $3C,$FF,$FF,$3C
        db $FF,$C3,$C3,$FF
        db $FF,$FF,$FF,$FF
        db $FF,$FF,$FF,$FF
        db $3C,$FF,$FF,$3C
        db $0C,$3C,$3C,$0C
        db $00,$3C,$3C,$00

palette: db $54,$4C,$4A,$52,$4B,$55,$5C,$4E,$47,$4F,$4D,$57,$53,$5E,$5A,$59,$44
crtc:   db 63,40,46,$8E,38,0,25,30,0,7,0,0,$30,0

xpos:   db 30
ypos:   db 12
ticks:  db 0
subtick: db 0
