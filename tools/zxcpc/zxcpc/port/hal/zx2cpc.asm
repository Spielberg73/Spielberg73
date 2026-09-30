; =============================================================================
;  HAL ZX Spectrum -> Amstrad CPC  (zxcpc)
; =============================================================================
;
;  Mapa de memoria del CPC durante el juego (ROMs desactivadas):
;
;    $0000-$3FFF  pantalla del CPC (modo 1, 256x192, CRTC R1=32 R6=24, inicio
;                 MA=$100). Cada bloque de 2K usa $x200-$x7FF para la imagen y
;                 deja libres $x000-$x1FF: 8 huecos de 512 bytes para este HAL.
;    $4000-$FFFF  memoria del Spectrum tal cual (su pantalla en $4000 queda
;                 como "sombra" que el HAL convierte a formato CPC)
;
;  Vectores RST (los del Spectrum apuntan a su ROM, que aquí no existe):
;    RST $00  reinicio (DI en $0000 para el truco IM2 de vector $FFFF)
;    RST $08  instrucción de 1 byte parcheada (búsqueda en tabla hash)
;    RST $10  PRINT-A de la ROM (emulación básica)
;    RST $18  LD (DE),A con reflejo en la pantalla CPC
;    RST $20  LD (HL),A con reflejo en la pantalla CPC
;    RST $28  HALT (espera al siguiente frame de 50 Hz)
;    RST $30  despacho de parches de 2+ bytes (RST $30 + id)
;    RST $38  interrupción del CPC (300 Hz)
;
;  Símbolos que define el portador (EQU externos):
;    REFRESH_LINES, BEEP_VOL, ROM_IM2_VECTOR, GAME_IM2, GAME_I, INIT_ULA
; =============================================================================

TABHI_PAGE  equ $08         ; tabla nibble alto -> byte CPC expandido
TABLO_PAGE  equ $09         ; tabla nibble bajo -> byte CPC expandido
XM_PAGE     equ $10         ; atributo -> máscara (tinta xor papel)
PM_PAGE     equ $11         ; atributo -> máscara de papel
HITAB       equ $1800       ; TTLLL -> byte alto de la dirección CPC
JPTAB       equ $1900       ; id -> manejador (bajos en +0, altos en +128)
HASH        equ $3800       ; tabla hash de sitios de 1 byte (32 entradas)

; ---------------------------------------------------------------------------
; Bloque 0: $0000-$01FF  vectores, interrupción, despacho
; ---------------------------------------------------------------------------
        org $0000
        di
        jp hal_reset

        org $0008
        jp h_rst8

        org $0010
        jp h_print

        org $0018
        ld (de),a
        jp mirror_de

        org $0020
        ld (hl),a
        jp mirror_hl

        org $0028
        jp h_halt

        org $0030
        jp h_dispatch

        org $0038
isr:    push af
        push bc
        ld b,$F5
        in a,(c)                ; PPI puerto B: bit 0 = VSYNC
        rra
        jr c,isr_frame          ; la interrupción sincronizada con VSYNC = frame
        ld a,(tick)
        inc a
        cp 6
        jr nc,isr_frame         ; VSYNC perdido: cada 6 ticks es un frame
        ld (tick),a
        cp REFRESH_LINES+1
        jr c,isr_refresh        ; ticks 1..REFRESH_LINES: una línea de refresco
        pop bc
        pop af
        ei
        ret

isr_refresh:
        push de
        push hl
        exx
        push bc
        push de
        push hl
        ld a,(refresh_y)
        push af
        call conv_line
        pop af
        inc a
        cp 192
        jr c,.n
        xor a
.n:     ld (refresh_y),a
        pop hl
        pop de
        pop bc
        exx
        pop hl
        pop de
        pop bc
        pop af
        ei
        ret

isr_frame:
        xor a
        ld (tick),a
        push de
        push hl
        push ix
        push iy
        ex af,af'
        push af
        exx
        push bc
        push de
        push hl
        call kb_scan
        ld hl,frame_ctr
        inc (hl)
        pop hl
        pop de
        pop bc
        exx
        pop af
        ex af,af'
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        ; --- interrupción del juego ---
        ld a,(game_im2)
        or a
        jr nz,.im2
        ; IM 1: emulación de la ROM (contador FRAMES)
        push hl
        ld hl,($5C78)
        inc hl
        ld ($5C78),hl
        ld a,h
        or l
        jr nz,.nf
        ld hl,$5C7A
        inc (hl)
.nf:    pop hl
        pop af
        ei
        ret
.im2:   push hl
        ld a,(game_i)
        cp $40
        jr c,.romv
        ld h,a
        ld l,$FF
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        jr .go
.romv:  ld hl,ROM_IM2_VECTOR
.go:    ld (isr_vec),hl
        pop hl                  ; [AF][PC]
        pop af                  ; [PC]
        push hl
        ld hl,(isr_vec)
        ex (sp),hl              ; [rutina del juego][PC]
        ret

; RST $30 + id: localiza el manejador sin tocar registros ni flags
h_dispatch:                     ; [ret]  (ret apunta al byte id)
        push hl
        push af                 ; [AF][HL][ret]
        ld hl,4
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = ret
        ld a,(hl)               ; id
dispatch_id:
        ld h,JPTAB/256
        ld l,a
        ld a,(hl)
        set 7,l
        ld h,(hl)
        ld l,a                  ; HL = manejador
        pop af                  ; [HL][ret]
        ex (sp),hl              ; [manejador][ret]
        ret

; RST $08: sitio de 1 byte -> buscar el id en la tabla hash por la dirección
h_rst8:                         ; [ret] (ret = sitio + 1)
        push hl
        push af
        push de                 ; [DE][AF][HL][ret]
        ld hl,6
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = ret
        xor h
        and 31
        ld e,a                  ; índice inicial
        ld d,32                 ; sondeos máximos
.probe: push de
        ld d,HASH/256
        ld a,e
        add a,32
        ld e,a
        ld a,(de)               ; byte alto
        or a
        jr z,.nf
        cp h
        jr nz,.nx
        ld a,e
        sub 32
        ld e,a
        ld a,(de)               ; byte bajo
        cp l
        jr nz,.nx
        ld a,e
        add a,64
        ld e,a
        ld a,(de)               ; id
        pop de
        pop de
        jr dispatch_id
.nx:    pop de
        ld a,e
        inc a
        and 31
        ld e,a
        dec d
        jr nz,.probe
        push de
.nf:    pop de
        ; no es un sitio parcheado: RST 8 original del juego (error de la
        ; ROM del Spectrum). Se salta el byte de código de error y se sigue.
        pop de
        pop af
        pop hl
        ex (sp),hl
        inc hl
        ex (sp),hl
        ret

; RST $28: HALT -> esperar al siguiente frame de 50 Hz
h_halt: push af
        push hl
        ld hl,frame_ctr
        ld a,(hl)
.w:     halt
        cp (hl)
        jr z,.w
        pop hl
        pop af
        ret

hal_reset:
        di
        halt

; variables
frame_ctr:  db 0
tick:       db 0
game_im2:   db GAME_IM2
game_i:     db GAME_I
isr_vec:    dw 0
c0_end:
        assert c0_end <= $0200, "bloque 0 lleno"

; ---------------------------------------------------------------------------
; Bloque 1: $0800-$09FF  tablas de conversión (las rellena el portador)
; Bloque 2: $1000-$11FF  máscaras de color por atributo (idem)
; ---------------------------------------------------------------------------

; ---------------------------------------------------------------------------
; Bloque 3: $1800-$19FF  conversión de pantalla + tabla de saltos
; ---------------------------------------------------------------------------
        org HITAB
        ; TTLLL -> L*8 + (T+1)*2   (byte alto de la dirección CPC)
        db  2, 10, 18, 26, 34, 42, 50, 58
        db  4, 12, 20, 28, 36, 44, 52, 60
        db  6, 14, 22, 30, 38, 46, 54, 62
        db  0,  0,  0,  0,  0,  0,  0,  0

; Convierte el byte de pantalla del Spectrum en HL ($4000-$57FF).
; Destruye AF, BC, DE, HL.
conv_byte:
        ld a,(hl)
        push af                 ; valor
        ld a,h
        rrca
        rrca
        rrca
        and 3
        or $58
        ld d,a
        ld e,l
        ld a,(de)               ; atributo de la celda
        ld e,a
        ld d,XM_PAGE
        ld a,(de)
        ld c,a                  ; C = máscara tinta^papel
        inc d
        ld a,(de)
        ld b,a                  ; B = máscara de papel
        ld a,h
        and $1F
        ld e,a
        ld d,HITAB/256
        ld a,(de)
        sla l                   ; L*2, acarreo = bit alto de la fila
        adc a,0
        ld d,a
        ld e,l                  ; DE = dirección en la pantalla CPC
        pop af
        ld l,a
        ld h,TABHI_PAGE
        ld a,(hl)
        and c
        xor b
        ld (de),a
        inc e
        inc h
        ld a,(hl)
        and c
        xor b
        ld (de),a
        ret

; Reconvierte las 8 líneas de la celda cuyo atributo está en HL
conv_cell:
        ld a,h
        and 3
        add a,a
        add a,a
        add a,a
        or $40
        ld h,a
        ld b,8
.l:     push bc
        push hl
        call conv_byte
        pop hl
        pop bc
        inc h
        djnz .l
        ret

; Refleja la escritura en la dirección HL (si es pantalla). Conserva todo.
mirror_hl:
        push af
        ld a,h
        sub $40
        cp $1B
        jr nc,.out
        push bc
        push de
        push hl
        cp $18
        jr nc,.attr
        call conv_byte
        jr .done
.attr:  call conv_cell
.done:  pop hl
        pop de
        pop bc
.out:   pop af
        ret

mirror_de:
        ex de,hl
        call mirror_hl
        ex de,hl
        ret

; Refleja el rango [HL, DE) (tras LDIR/LDDR...). Destruye AF, HL.
mirror_span:
        ld a,h
        cp $5B
        ret nc                  ; empieza por encima de la pantalla
.l:     ld a,l
        cp e
        jr nz,.do
        ld a,h
        cp d
        ret z
.do:    call mirror_hl
        inc hl
        ld a,h
        cp $5B
        jr c,.l
        ret
c3_end:
        assert c3_end <= JPTAB, "bloque 3 lleno"

; ---------------------------------------------------------------------------
; Bloque 4: $2000-$21FF  teclado y joystick
; ---------------------------------------------------------------------------
        org $2000
cpc_matrix: ds 10, $FF
            db $FF              ; línea ficticia (nunca pulsada)
zx_rows:    ds 8, $1F
kempston:   db 0

kb_scan:
        ld bc,$F40E
        out (c),c
        ld bc,$F6C0
        out (c),c
        ld bc,$F600
        out (c),c
        ld bc,$F792
        out (c),c               ; puerto A del PPI en entrada
        ld hl,cpc_matrix
        ld a,$40
.l:     ld b,$F6
        out (c),a               ; lectura PSG + línea de teclado
        ld b,$F4
        in d,(c)
        ld (hl),d
        inc hl
        inc a
        cp $4A
        jr nz,.l
        ld bc,$F782
        out (c),c               ; puerto A de nuevo en salida
        call psg_latch8
        ; --- matriz CPC -> semifilas del Spectrum ---
        ld hl,kmap
        ld d,cpc_matrix/256
        exx
        ld hl,zx_rows
        ld b,8
.row:   exx
        ld b,5
.key:   ld e,(hl)               ; línea CPC principal
        inc hl
        ld a,(de)
        and (hl)
        inc hl
        ld e,(hl)               ; línea CPC secundaria
        inc hl
        jr z,.p
        ld a,(de)
        and (hl)                ; (AND deja el acarreo a 0)
        jr z,.p
        inc hl
        rr c
        djnz .key
        jr .end
.p:     inc hl
        scf
        rr c
        djnz .key
.end:   ld a,c
        rrca
        rrca
        rrca
        cpl
        and $1F
        exx
        ld (hl),a
        inc hl
        djnz .row
        ; --- joystick CPC -> Kempston ---
        ld a,(cpc_matrix+9)
        cpl
        ld b,0
        rra
        jr nc,.j1
        set 3,b                 ; arriba
.j1:    rra
        jr nc,.j2
        set 2,b                 ; abajo
.j2:    rra
        jr nc,.j3
        set 1,b                 ; izquierda
.j3:    rra
        jr nc,.j4
        set 0,b                 ; derecha
.j4:    rra
        jr nc,.j5
        set 4,b                 ; fuego 2
.j5:    rra
        jr nc,.j6
        set 4,b                 ; fuego 1
.j6:    ld a,b
        ld (kempston),a
        ret

; Deja el registro 8 del PSG seleccionado (volumen A = beeper)
psg_latch8:
        ld bc,$F408
        out (c),c
        ld bc,$F6C0
        out (c),c
        ld bc,$F600
        out (c),c
        ret

; Escribe E en el registro A del PSG. Destruye AF, BC.
psg_write:
        ld b,$F4
        out (c),a
        ld b,$F6
        ld a,$C0
        out (c),a
        xor a
        out (c),a
        ld b,$F4
        out (c),e
        ld b,$F6
        ld a,$80
        out (c),a
        xor a
        out (c),a
        ret
c4_end:
        assert c4_end <= $2200, "bloque 4 lleno"
        assert (cpc_matrix & $FF) == 0, "cpc_matrix debe empezar en página"

; ---------------------------------------------------------------------------
; Bloque 5: $2800-$29FF  E/S: teclado, joystick, borde, beeper, AY
; ---------------------------------------------------------------------------
        org $2800
border_tab: ds 8, $54           ; color hardware | $40 para cada color ZX
last_ula:   db INIT_ULA
ay_sel:     db 0
ay_shadow:  ds 16, 0

; A = byte alto del puerto -> A = $A0 | semifilas seleccionadas. Usa BC, HL.
ula_read:
        ld c,a
        ld hl,zx_rows
        ld a,$1F
        ld b,8
.l:     rrc c
        jr c,.s
        and (hl)
.s:     inc hl
        djnz .l
        or $A0
        ret

; IN A,(n) con n par: teclado
h_in_ula_a:
        push af
        push bc
        push hl
        call ula_read
set_a_ret:                      ; guarda A en la ranura de AF y vuelve
        ld hl,5
        add hl,sp
        ld (hl),a
        pop hl
        pop bc
        pop af
        ret

; IN A,($1F): Kempston
h_in_kemp_a:
        push af
        push bc
        push hl
        ld a,(kempston)
        jr set_a_ret

; IN A,(n) con puerto sin dispositivo: bus flotante ($FF)
h_in_float_a:
        push af
        push bc
        push hl
        ld a,$FF
        jr set_a_ret

; IN r,(C): valor del puerto BC en A. Conserva BC y DE.
in_c_value:
        ld a,c
        rra
        jr c,.odd
        push bc
        ld a,b
        call ula_read
        pop bc
        ret
.odd:   ld a,c
        cp $1F
        jr z,.kemp
        cp $FD
        jr nz,.ff
        ld a,b
        cp $FF
        jr nz,.ff
        ld hl,ay_shadow
        ld a,(ay_sel)
        add a,l
        ld l,a
        ld a,(hl)
        ret
.kemp:  ld a,(kempston)
        ret
.ff:    ld a,$FF
        ret

; Flags de IN r,(C) para el valor A, conservando el acarreo guardado en la
; ranura de F situada en (SP+OFF). Entrada: A = valor, HL -> ranura de F.
in_flags:
        push de
        ld e,a
        or a
        push af
        pop de                  ; E = flags del valor
        ld a,(hl)
        and 1
        or e
        ld (hl),a
        pop de
        ret

; OUT (n),A con n par: borde y beeper
h_out_ula:
        push af
        push bc
        push hl
        call ula_write
        pop hl
        pop bc
        pop af
        ret

; A = valor escrito en la ULA. Destruye AF, BC, HL.
ula_write:
        ld c,a
        ld a,(last_ula)
        xor c
        ld h,a                  ; bits que cambian
        ld a,c
        ld (last_ula),a
        bit 4,h
        jr z,.nob
        and $10
        jr z,.z
        ld a,BEEP_VOL
.z:     ld b,$F4
        out (c),a               ; dato del PSG (registro 8 ya seleccionado)
        ld b,$F6
        ld a,$80
        out (c),a
        xor a
        out (c),a
.nob:   ld a,h
        and 7
        ret z
        ld a,(last_ula)
        and 7
        ld hl,border_tab
        add a,l
        ld l,a
        ld a,(hl)
        ld bc,$7F10
        out (c),c
        out (c),a
        ret

; OUT (C),r: A = valor, BC = puerto. Destruye AF, HL.
out_c_value:
        ld h,a
        ld a,c
        rra
        jr c,.odd
        push bc
        ld a,h
        call ula_write
        pop bc
        ret
.odd:   ld a,c
        cp $FD
        ret nz
        ld a,b
        cp $FF
        jr z,.sel
        cp $BF
        ret nz                  ; $7FFD (paginación) y otros: se ignoran
        ld a,h
        push bc
        push de
        call ay_write
        pop de
        pop bc
        ret
.sel:   ld a,h
        and 15
        ld (ay_sel),a
        ret

; Escritura en el AY del 128K. Ajusta periodos al reloj del CPC
; (1 MHz frente a 1,7734 MHz: factor 0,5625). A = valor. Destruye todo salvo IX/IY.
ay_write:
        ld e,a
        ld a,(ay_sel)
        cp 14
        ret nc
        ld hl,ay_shadow
        add a,l
        ld l,a
        ld (hl),e
        ld a,(ay_sel)
        cp 6
        jr c,.tone
        jr z,.noise
        cp 7
        jr z,.mix
        cp 11
        jr z,.env
        cp 12
        jr z,.env
        call psg_write          ; volúmenes y forma: directo
        jp psg_latch8
.mix:   ld a,e
        and $3F                 ; el puerto A del PSG siempre en entrada (teclado)
        ld e,a
        ld a,7
        call psg_write
        jp psg_latch8
.noise: ld a,e
        and $1F
        ld l,a
        ld h,0
        call scale
        ld e,l
        ld a,6
        call psg_write
        jp psg_latch8
.env:   ld hl,(ay_shadow+11)
        call scale
        push hl
        ld e,l
        ld a,11
        call psg_write
        pop hl
        ld e,h
        ld a,12
        call psg_write
        jp psg_latch8
.tone:  and 6                   ; registro par del canal
        push af
        ld hl,ay_shadow
        add a,l
        ld l,a
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld a,h
        and 15
        ld h,a
        call scale
        pop af
        push hl
        push af
        ld e,l
        call psg_write
        pop af
        pop hl
        inc a
        ld e,h
        call psg_write
        jp psg_latch8

; HL = HL * 9/16 (redondeando)
scale:  push de
        ld d,h
        ld e,l
        srl h
        rr l                    ; HL = v/2
        srl d
        rr e
        srl d
        rr e
        srl d
        rr e
        srl d
        rr e                    ; DE = v/16
        add hl,de
        pop de
        ret
c5_end:
        assert c5_end <= $2A00, "bloque 5 lleno"
        assert (zx_rows & $FF) <= $F0, "zx_rows cruza página"
        assert (border_tab & $FF) <= $F8, "border_tab cruza página"
        assert (ay_shadow & $FF) <= $F0, "ay_shadow cruza página"

; ---------------------------------------------------------------------------
; Bloque 6: $3000-$31FF  refresco de fondo y rutinas de la ROM
; ---------------------------------------------------------------------------
        org $3000
refresh_y:  db 0

; Convierte la línea A (0-191) completa. Usa todos los registros (incluidos
; los alternativos): solo se llama desde la interrupción, que los guarda.
conv_line:
        ld c,a
        ; destino CPC: ln*$800 + (t+1)*$200 + r*64
        and 7
        add a,a
        add a,a
        add a,a                 ; ln*8
        ld d,a
        ld a,c
        and $C0
        rlca
        rlca                    ; t
        inc a
        add a,a                 ; (t+1)*2
        add a,d
        ld d,a
        ld a,c
        and $38                 ; r*8
        add a,a
        add a,a
        add a,a                 ; r*64 (0-448): bit 8 -> acarreo
        ld e,a
        jr nc,.nc
        inc d
.nc:    push de
        exx
        pop de                  ; DE' = destino
        exx
        ; origen ZX: 010TTLLL RRR00000
        ld a,c
        and 7
        or $40
        ld h,a
        ld a,c
        and $C0
        rrca
        rrca
        rrca
        or h
        ld h,a
        ld a,c
        and $38
        add a,a
        add a,a
        ld l,a
        ; atributos: $5800 + (y/8)*32
        ld a,c
        and $C0
        rlca
        rlca
        or $58
        ld d,a
        ld e,l
        ld b,32
.l:     ld a,(de)               ; atributo
        inc e
        exx
        ld l,a
        ld h,XM_PAGE
        ld c,(hl)
        inc h
        ld b,(hl)
        exx
        ld a,(hl)               ; píxeles
        inc l
        exx
        ld l,a
        ld h,TABHI_PAGE
        ld a,(hl)
        and c
        xor b
        ld (de),a
        inc e
        inc h
        ld a,(hl)
        and c
        xor b
        ld (de),a
        inc e
        exx
        djnz .l
        ret

; --- Sustitutos de rutinas de la ROM del Spectrum ---------------------------

; CLS ($0D6B) / CL-ALL ($0DAF): borrar pantalla con ATTR-P
rom_cls:
        push af
        push bc
        push de
        push hl
        ld hl,$4000
        ld de,$4001
        ld bc,6143
        ld (hl),0
        ldir
        ld a,($5C8D)
        ld hl,$5800
        ld de,$5801
        ld bc,767
        ld (hl),a
        ldir
        ; pantalla CPC: todo papel
        ld l,a
        ld h,PM_PAGE
        ld a,(hl)
        ld hl,$0200
        ld c,8
.blk:   push hl
        ld d,h
        ld e,l
        inc de
        ld (hl),a
        push bc
        ld bc,$05FF
        ldir
        pop bc
        pop hl
        ld de,$0800
        add hl,de
        dec c
        jr nz,.blk
.fin:   pop hl
        pop de
        pop bc
        pop af
        ret

; CLS-LOWER ($0D6E): borra las dos últimas filas de texto
rom_cls_lower:
        push af
        push bc
        push de
        push hl
        ld a,176
.l:     push af
        call clear_line
        pop af
        inc a
        cp 192
        jr nz,.l
        ld a,($5C48)            ; BORDCR
        ld hl,$5AC0
        ld de,$5AC1
        ld bc,63
        ld (hl),a
        ldir
        ld a,176
.m:     push af
        exx
        push bc
        push de
        push hl
        exx
        call conv_line
        exx
        pop hl
        pop de
        pop bc
        exx
        pop af
        inc a
        cp 192
        jr nz,.m
        pop hl
        pop de
        pop bc
        pop af
        ret

; borra la línea A de la pantalla del Spectrum
clear_line:
        ld c,a
        and 7
        or $40
        ld h,a
        ld a,c
        and $C0
        rrca
        rrca
        rrca
        or h
        ld h,a
        ld a,c
        and $38
        add a,a
        add a,a
        ld l,a
        ld b,32
.l:     ld (hl),0
        inc l
        djnz .l
        ret

; BEEPER ($03B5): DE = ciclos, HL = periodo. Mismo bucle, beeper -> AY
rom_beeper:
        push af
        push bc
        push de
        push hl
        push ix
        ld a,d
        or e
        jr z,.fin
        ; iteraciones de espera ~ HL/6.5
        push hl
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l                    ; HL/8
        ld b,h
        ld c,l
        pop hl
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l
        srl h
        rr l                    ; HL/32
        add hl,bc
        inc hl
        push hl
        pop ix                  ; IX = espera por semiperiodo
        ld a,(last_ula)
.cyc:   xor $10
        push af
        push de
        call ula_write
        pop de
        pop af
        push ix
        pop hl
.w:     dec hl
        ld b,a
        ld a,h
        or l
        ld a,b
        jr nz,.w
        dec de
        ld b,a
        ld a,d
        or e
        ld a,b
        jr nz,.cyc
.fin:   pop ix
        pop hl
        pop de
        pop bc
        pop af
        ret

; Rutina de la ROM no soportada: vuelve sin hacer nada
rom_ret:
        ret

; LD-BYTES ($0556): la carga desde cinta no es posible -> error (CF=0)
rom_ld_bytes:
        and a
        ret

; KEY-SCAN ($028E): E = tecla pulsada (o $FF), D = $FF, Z = 1
rom_key_scan:
        push af
        push bc
        push hl
        ld e,$FF
        ld d,$FF
        ld hl,zx_rows
        ld c,0                  ; nº de semifila
.r:     ld a,(hl)
        cpl
        and $1F
        jr z,.nx
        ld b,0
.b:     rra
        jr c,.got
        inc b
        jr .b
.got:   ld a,4
        sub b
        add a,a
        add a,a
        add a,a
        or c
        ld e,a
.nx:    inc hl
        inc c
        ld a,c
        cp 8
        jr nz,.r
        pop hl
        pop bc
        pop af
        cp a                    ; Z = 1
        ret

; BORDER ($2294): A = color
rom_border:
        push af
        push bc
        push hl
        and 7
        ld c,a
        ld a,(last_ula)
        and $F8
        or c
        call ula_write
        pop hl
        pop bc
        pop af
        ret

; MASK-INT llamada directamente ($0038): avanza FRAMES
rom_frames:
        push af
        push hl
        ld hl,($5C78)
        inc hl
        ld ($5C78),hl
        ld a,h
        or l
        jr nz,.n
        ld hl,$5C7A
        inc (hl)
.n:     pop hl
        pop af
        ret
c6_end:
        assert c6_end <= $3200, "bloque 6 lleno"

; ---------------------------------------------------------------------------
; Bloque 7: $3800-$39FF  tabla hash (la genera el portador) + impresión
; ---------------------------------------------------------------------------
        org HASH+96
print_x:    db 0
print_y:    db 0
print_st:   db 0                ; 0 normal, 1-2 esperando AT, 3 esperando color

; RST $10 / PRINT-A: impresión mínima (AT, ENTER, caracteres 32-127 y GDU)
; con la fuente de CHARS si está en RAM ($4000 en adelante).
h_print:
        push af
        push bc
        push de
        push hl
        ld c,a
        ld a,(print_st)
        or a
        jp nz,.state
        ld a,c
        cp 22
        jp z,.at
        cp 13
        jp z,.cr
        cp 16
        jp c,.fin
        cp 22
        jp c,.col               ; INK..OVER: saltar un parámetro
        cp 23
        jp z,.col               ; TAB (simplificado)
        cp 32
        jp c,.fin
        cp 128
        jp c,.chr
        cp 144
        jp c,.fin
        cp 165
        jp nc,.fin
        ; GDU: (UDG) + (código-144)*8
        sub 144
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,($5C7B)
        add hl,de
        jp .draw
.chr:   ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,($5C36)           ; CHARS
        add hl,de
        ld a,d
        cp $3F
        jp c,.adv               ; fuente en ROM: no disponible en el CPC
.draw:  ex de,hl                ; DE = datos del carácter
        ld a,(print_y)
        and $18
        or $40
        ld h,a
        ld a,(print_y)
        and 7
        rrca
        rrca
        rrca
        ld l,a
        ld a,(print_x)
        or l
        ld l,a
        ld b,8
.pl:    ld a,(de)
        ld (hl),a
        inc de
        inc h
        djnz .pl
        ; atributo ATTR-T y reflejo
        dec h
        ld a,h
        rrca
        rrca
        rrca
        and 3
        or $58
        ld h,a
        ld a,($5C8F)
        ld (hl),a
        call mirror_hl
.adv:   ld a,(print_x)
        inc a
        cp 32
        jp c,.sx
        call .newl
        jp .fin
.sx:    ld (print_x),a
        jp .fin
.cr:    call .newl
        jp .fin
.at:    ld a,1
        ld (print_st),a
        jp .fin
.col:   ld a,3
        ld (print_st),a
        jp .fin
.state: cp 1
        jp nz,.st2
        ld a,c
        cp 24
        jp c,.sy
        xor a
.sy:    ld (print_y),a
        ld a,2
        ld (print_st),a
        jp .fin
.st2:   cp 2
        jp nz,.st3
        ld a,c
        and 31
        ld (print_x),a
.st3:   xor a
        ld (print_st),a
.fin:   pop hl
        pop de
        pop bc
        pop af
        ret
.newl:  xor a
        ld (print_x),a
        ld a,(print_y)
        inc a
        cp 24
        jp c,.ny
        xor a
.ny:    ld (print_y),a
        ret

; PR-STRING ($203C): imprime BC bytes desde DE
rom_pr_string:
.l:     ld a,b
        or c
        ret z
        ld a,(de)
        rst $10
        inc de
        dec bc
        jr .l
c7_end:
        assert c7_end <= $3A00, "bloque 7 lleno"
