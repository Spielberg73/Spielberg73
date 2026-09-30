; Segundo juego de prueba para ZX Spectrum 48K (dominio público, para zxcpc)
;
; Imita los hábitos de muchos juegos comerciales sencillos:
;   - IM 1 (rutina de interrupción de la ROM) y teclado leído vía LAST_K/FLAGS
;   - textos con RST $10 (AT, INK...) usando la fuente de la ROM
;   - una rutina propia que dibuja letras leyendo la fuente en $3D00
;   - sonido con la rutina BEEPER de la ROM ($03B5)
;   - código automodificable (la velocidad de una animación)
;   - OUT (C),A e IN r,(C) con BC cargado desde otro sitio
;
; Controles: O/P mueven la barra; ESPACIO hace sonar un pitido.

        org $8000

start:  ld a,$07
        ld ($5C8D),a            ; ATTR-P: tinta blanca, papel negro
        call $0D6B              ; CLS (deja abierto el canal K)
        ld a,2
        call $1601              ; CHAN-OPEN canal 2 (pantalla superior)
        ld de,title
        ld bc,title_end-title
        call $203C              ; PR-STRING
        ; letras grandes propias leyendo la fuente de la ROM
        ld hl,$4000+$0800+$40   ; tercio 1, fila 2
        ld a,'Z'
        call bigchar
        ld hl,$4000+$0800+$42
        ld a,'X'
        call bigchar
        ld hl,$4000+$0800+$44
        ld a,'C'
        call bigchar
        ld hl,$4000+$0800+$46
        ld a,'P'
        call bigchar
        ld hl,$4000+$0800+$48
        ld a,'C'
        call bigchar
        ei

main:   halt
        call keys
        call move
        call bar
        call anim
        call score
        jr main

; --- teclado vía LAST_K (lo actualiza la interrupción de la ROM) -------------
keys:   ld hl,$5C3B             ; FLAGS
        bit 5,(hl)
        ret z
        res 5,(hl)
        ld a,($5C08)            ; LAST_K
        cp 'p'
        jr z,.r
        cp 'o'
        jr z,.l
        cp ' '
        ret nz
        ld hl,300               ; tono
        ld de,40                ; duración
        call $03B5              ; BEEPER de la ROM
        ret
.r:     ld a,1
        ld (dir),a
        ret
.l:     ld a,$FF
        ld (dir),a
        ret

move:   ld a,(dir)
        ld b,a
        ld a,(barx)
        add a,b
        cp 28
        jr c,.ok
        xor a
        ld (dir),a
        ret
.ok:    ld (barx),a
        ret

; barra de 4 celdas en la fila 20 (atributos)
bar:    ld hl,$5800+20*32
        ld b,32
.c:     ld (hl),$07
        inc hl
        djnz .c
        ld a,(barx)
        ld l,a
        ld h,0
        ld de,$5800+20*32
        add hl,de
        ld b,4
.d:     ld (hl),$2D             ; papel cian, tinta azul claro
        inc hl
        djnz .d
        ret

; animación del borde: el retardo está en el operando de "ld a,n" (SMC)
anim:   ld a,(tick)
        inc a
        ld (tick),a
speed:  cp 10
        ret c
        xor a
        ld (tick),a
        ld a,(bord)
        inc a
        and 7
        ld (bord),a
        ld bc,$00FE
        out (c),a
        ; acelerar cada vez (modifica el operando de 'cp' en speed+1)
        ld a,(speed+1)
        dec a
        jr nz,.s
        ld a,10
.s:     ld (speed+1),a
        ; lee el teclado entero con IN r,(C) (no hace nada con ello)
        ld bc,$00FE
        in e,(c)
        ret

; marcador con RST $10
score:  ld a,22                 ; AT
        rst $10
        ld a,12
        rst $10
        ld a,0
        rst $10
        ld a,(barx)
        add a,'A'
        rst $10
        ret

; letra 8x8 a doble ancho leyendo la fuente de la ROM: A = carácter, HL = pantalla
bigchar:
        push hl
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,$3D00-256
        add hl,de
        ex de,hl                ; DE = datos del carácter en la ROM
        pop hl
        ld b,8
.l:     push bc
        ld a,(de)
        ld c,0
        ld b,4
.hi:    rla                     ; bits 7-4 -> doble ancho en C
        push af
        rl c
        pop af
        rl c
        djnz .hi
        ld (hl),c
        inc l
        ld b,4
        ld c,0
.lo:    rla
        push af
        rl c
        pop af
        rl c
        djnz .lo
        ld (hl),c
        dec l
        inc h
        inc de
        pop bc
        djnz .l
        ret

title:  db 22,0,6,16,6,"ZXCPC PRUEBA 2",22,1,2,16,5,"O/P mover, ESPACIO pitar"
title_end:

barx:   db 14
dir:    db 0
tick:   db 0
bord:   db 0
