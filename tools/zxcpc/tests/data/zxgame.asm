; Minijuego de prueba para ZX Spectrum 48K (dominio público, escrito para zxcpc)
;
; Usa a propósito todo lo que un portador tiene que resolver:
;   - IM 2 con tabla de vectores (I = $FE, vector en $FDFD)
;   - HALT para sincronizar con el frame
;   - lectura de teclado con IN A,($FE) e IN A,(C), y joystick Kempston
;   - borde y beeper con OUT ($FE),A
;   - llamada a la ROM (CLS en $0D6B)
;   - escrituras en pantalla con LD (HL),A, LD (DE),A, LD (IX+d),A, LDIR y PUSH
;   - atributos de color
;
; Controles: Q/A/O/P o joystick para mover el bloque; ESPACIO para pitar.

        org $8000

start:  di
        ld sp,$FF00
        ld a,1
        out ($FE),a             ; borde azul
        ld a,$38
        ld ($5C8D),a            ; ATTR_P: papel blanco, tinta negra
        call $0D6B              ; CLS de la ROM
        ; tabla IM 2
        ld hl,$FE00
        ld de,$FE01
        ld bc,256
        ld (hl),$FD
        ldir
        ld a,$C3
        ld ($FDFD),a
        ld hl,isr
        ld ($FDFE),hl
        ld a,$FE
        ld i,a
        im 2
        ei
        ; fondo: franja de color con LDIR sobre atributos
        ld hl,$5800+32*20
        ld de,$5800+32*20+1
        ld bc,32*4-1
        ld (hl),$21             ; papel azul, tinta roja
        ldir
        ; franja de píxeles con LD (DE),A
        ld de,$4000+$1000+$20*4   ; tercio 2
        ld b,32
        ld a,$AA
.fr:    ld (de),a
        inc e
        djnz .fr
        ; marco superior con LD (IX+d),A
        ld ix,$4000
        ld b,32
        ld a,$FF
.mk:    ld (ix+0),a
        ld (ix+$20),a           ; siguiente fila de caracteres, línea 0
        inc ix
        djnz .mk
        ; bloque de pixeles con PUSH (volcado por pila)
        ld (savesp),sp
        ld sp,$4000+$0800+$E0+32  ; tercio 1, fila 7, línea 0 (fin de la fila)
        ld hl,$F0F0
        ld b,16
.pu:    push hl
        djnz .pu
        ld sp,(savesp)
        call draw

main:   halt                    ; sincronización a 50 Hz
        call erase
        call input
        call draw
        ld a,(frames)
        and 7
        call z,blink
        jr main

; --- lectura de controles --------------------------------------------------
input:  ld a,$FB                ; semifila Q-T
        in a,($FE)
        bit 0,a                 ; Q
        call z,up
        ld a,$FD                ; semifila A-G
        in a,($FE)
        bit 0,a                 ; A
        call z,down
        ld bc,$DFFE             ; semifila P-Y
        in a,(c)
        bit 1,a                 ; O
        call z,left
        bit 0,a                 ; P
        call z,right
        in a,($1F)              ; Kempston
        bit 0,a
        call nz,right
        bit 1,a
        call nz,left
        bit 2,a
        call nz,down
        bit 3,a
        call nz,up
        ld a,$7F                ; ESPACIO
        in a,($FE)
        bit 0,a
        call z,beep
        ret

up:     push af
        ld a,(ypos)
        or a
        jr z,.x
        dec a
        ld (ypos),a
.x:     pop af
        ret
down:   push af
        ld a,(ypos)
        cp 18
        jr z,.x
        inc a
        ld (ypos),a
.x:     pop af
        ret
left:   push af
        ld a,(xpos)
        or a
        jr z,.x
        dec a
        ld (xpos),a
.x:     pop af
        ret
right:  push af
        ld a,(xpos)
        cp 31
        jr z,.x
        inc a
        ld (xpos),a
.x:     pop af
        ret

; beeper: 100 ciclos de onda cuadrada
beep:   push af
        push bc
        ld c,100
        ld a,(border)
.b1:    xor $10
        out ($FE),a
        ld b,60
.b2:    djnz .b2
        dec c
        jr nz,.b1
        pop bc
        pop af
        ret

; cambia el borde cada 8 frames
blink:  ld a,(border)
        inc a
        and 7
        ld (border),a
        out ($FE),a
        ret

; --- sprite 8x8 --------------------------------------------------------------
; HL = dirección de pantalla de la celda (xpos, ypos)
celladdr:
        ld a,(ypos)
        ld l,a
        and $18
        or $40
        ld h,a
        ld a,l
        and 7
        rrca
        rrca
        rrca
        ld l,a
        ld a,(xpos)
        or l
        ld l,a
        ret

draw:   call celladdr
        ld de,sprite
        ld b,8
.d:     ld a,(de)
        xor (hl)
        ld (hl),a
        inc h
        inc de
        djnz .d
        ; atributo: tinta roja brillante sobre papel amarillo
        call attraddr
        ld (hl),$72
        ret

erase:  call celladdr
        ld de,sprite
        ld b,8
.e:     ld a,(de)
        xor (hl)
        ld (hl),a
        inc h
        inc de
        djnz .e
        call attraddr
        ld (hl),$38
        ret

attraddr:
        ld a,(ypos)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,(xpos)
        ld e,a
        ld d,$58
        add hl,de
        ret

isr:    push af
        push hl
        ld hl,frames
        inc (hl)
        pop hl
        pop af
        ei
        reti

sprite: db %00111100
        db %01111110
        db %11011011
        db %11111111
        db %11111111
        db %10111101
        db %01000010
        db %00111100

xpos:   db 12
ypos:   db 8
frames: db 0
border: db 1
savesp: dw 0
