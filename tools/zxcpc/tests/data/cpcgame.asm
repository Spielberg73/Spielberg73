; Juego de prueba para Amstrad CPC (dominio público, escrito para zxcpc)
;
; Usa lo que un portador CPC -> Spectrum tiene que resolver:
;   - firmware: SCR SET MODE, SCR SET INK, SCR SET BORDER, TXT SET CURSOR,
;     TXT SET PEN, TXT OUTPUT, KM TEST KEY, MC WAIT FLYBACK
;   - escritura directa en la pantalla (modo 1, base $C000)
;   - paleta cambiada directamente con el gate array (OUT)
;   - sonido directo en el PSG a través del PPI
;   - lectura directa del teclado (línea 9: joystick) con el PPI
;
; Controles: cursores o joystick mueven el bloque; ESPACIO pita.

SCR_SET_MODE    equ $BC0E
SCR_SET_INK     equ $BC32
SCR_SET_BORDER  equ $BC38
TXT_SET_CURSOR  equ $BB75
TXT_SET_PEN     equ $BB90
TXT_OUTPUT      equ $BB5A
KM_TEST_KEY     equ $BB1E
MC_WAIT_FLYBACK equ $BD19

        org $4000

start:  ld a,1
        call SCR_SET_MODE
        ld a,0                  ; pluma 0: negro
        ld bc,$0000
        call SCR_SET_INK
        ld a,1                  ; pluma 1: amarillo brillante
        ld bc,$1818
        call SCR_SET_INK
        ld a,2                  ; pluma 2: cian brillante
        ld bc,$1414
        call SCR_SET_INK
        ld a,3                  ; pluma 3: rojo brillante
        ld bc,$0606
        call SCR_SET_INK
        ld bc,$0101             ; borde azul
        call SCR_SET_BORDER
        ; título
        ld hl,$0508             ; columna 8, fila 5 (base 1)
        call TXT_SET_CURSOR
        ld a,1
        call TXT_SET_PEN
        ld hl,title
.t:     ld a,(hl)
        or a
        jr z,.tdone
        call TXT_OUTPUT
        inc hl
        jr .t
.tdone:
        ; franja de pluma 2 con LDIR directo en pantalla (línea 0 de la fila 20)
        ld hl,$C000+20*80
        ld de,$C000+20*80+1
        ld bc,79
        ld (hl),$0F             ; 4 píxeles de pluma 2
        ldir
        call draw

main:   call MC_WAIT_FLYBACK
        call erase
        call keys
        call joy
        call draw
        ld a,(frames)
        inc a
        ld (frames),a
        and 15
        call z,flash
        jr main

; --- teclado por firmware ----------------------------------------------------
keys:   ld a,8                  ; cursor izquierda
        call KM_TEST_KEY
        call nz,left
        ld a,1                  ; cursor derecha
        call KM_TEST_KEY
        call nz,right
        ld a,0                  ; cursor arriba
        call KM_TEST_KEY
        call nz,up
        ld a,2                  ; cursor abajo
        call KM_TEST_KEY
        call nz,down
        ld a,47                 ; espacio
        call KM_TEST_KEY
        call nz,beep
        ret

; --- joystick leído directamente del PPI/PSG (línea 9) -----------------------
joy:    ld bc,$F40E
        out (c),c
        ld bc,$F6C0
        out (c),c
        ld bc,$F600
        out (c),c
        ld bc,$F792
        out (c),c
        ld bc,$F649             ; lectura PSG + línea 9
        out (c),c
        ld b,$F4
        in a,(c)
        ld bc,$F782
        out (c),c
        ld bc,$F600
        out (c),c
        bit 2,a                 ; izquierda (activo a 0)
        call z,left
        bit 3,a
        call z,right
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
        cp 76
        jr z,.x
        inc a
        ld (xpos),a
.x:     pop af
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
        cp 23
        jr z,.x
        inc a
        ld (ypos),a
.x:     pop af
        ret

; tono en el canal A del PSG durante unos frames
beep:   ld a,0
        ld e,$80
        call psg
        ld a,1
        ld e,0
        call psg
        ld a,7
        ld e,$3E                ; solo tono A
        call psg
        ld a,8
        ld e,12
        call psg
        ld b,6
.w:     push bc
        call MC_WAIT_FLYBACK
        pop bc
        halt
        djnz .w
        ld a,8
        ld e,0
        call psg
        ret

; escribe E en el registro A del PSG
psg:    ld b,$F4
        out (c),a
        ld bc,$F6C0
        out (c),c
        ld bc,$F600
        out (c),c
        ld b,$F4
        out (c),e
        ld bc,$F680
        out (c),c
        ld bc,$F600
        out (c),c
        ret

; alterna el color de la pluma 3 con el gate array directamente
flash:  ld a,(fcol)
        xor $0C ^ $0E           ; rojo brillante <-> amarillo pastel (hw)
        ld (fcol),a
        ld bc,$7F03
        out (c),c
        or $40
        out (c),a
        ret

; --- sprite de 4 bytes x 8 líneas (16 píxeles de modo 1) ---------------------
; HL = dirección de pantalla de (xpos bytes, ypos filas de 8)
scraddr:
        ld a,(ypos)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl               ; *16
        ld d,h
        ld e,l
        add hl,hl
        add hl,hl               ; *64
        add hl,de               ; *80
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

sprite: db $00,$FF,$FF,$00
        db $0F,$FF,$FF,$0F
        db $FF,$F0,$F0,$FF
        db $FF,$FF,$FF,$FF
        db $FF,$FF,$FF,$FF
        db $F0,$FF,$FF,$F0
        db $0F,$0F,$0F,$0F
        db $00,$FF,$FF,$00

title:  db "ZXCPC PRUEBA CPC",0
xpos:   db 36
ypos:   db 12
frames: db 0
fcol:   db $0C
