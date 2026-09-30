; =============================================================================
;  HAL Amstrad CPC -> ZX Spectrum +2A/+3  (zxcpc)
; =============================================================================
;
;  Se usan dos configuraciones de la paginación especial del +2A/+3:
;
;    JUEGO ($1FFD=$01)  bancos 0,1,2,3  = los 64K del CPC, intactos
;    HAL   ($1FFD=$07)  bancos 4,7,6,3:
;        $0000-$3FFF  banco 4: copia de la PUERTA + fuente y datos del HAL
;        $4000-$5AFF  banco 7: pantalla del Spectrum (sombra: $7FFD bit 3 = 1)
;        $8000-$BFFF  banco 6: código y tablas del HAL
;        $C000-$FFFF  banco 3: pantalla del CPC (común a las dos configuraciones)
;
;  La PUERTA (vectores RST + código de cambio de banco + tablas rápidas) está
;  en un hueco libre de la memoria baja del juego (banco 0) y, byte a byte, en
;  la misma dirección del banco 4: al cambiar de configuración la CPU sigue
;  ejecutando el mismo código. Los registros viajan por un BUZÓN de 48 bytes en
;  el banco 3 (un hueco de la pantalla del CPC que el juego no usa).
;
;  Símbolos del portador: GATE, MB, NSTUBS, CROP_X, CROP_Y, REFRESH_LINES,
;  FONT, INIT_MODE, INIT_R1
; =============================================================================

CFG_GAME    equ $01
CFG_HAL     equ $07

; --- buzón (banco 3) ---
MB_AF       equ MB+0
MB_BC       equ MB+2
MB_DE       equ MB+4
MB_HL       equ MB+6
MB_IX       equ MB+8
MB_IY       equ MB+10
MB_SP       equ MB+12
MB_ID       equ MB+14
MB_IFF      equ MB+15
MB_X1       equ MB+16
MB_X2       equ MB+18
MB_FRAME    equ MB+20
MB_SCRHI    equ MB+21           ; byte alto de la página de pantalla CPC
MB_START    equ MB+22           ; desplazamiento inicial (2 bytes)
MB_FASTOK   equ MB+24           ; 1 = la vía rápida de reflejo es válida
MB_GAMEISR  equ MB+25           ; JP rutina de interrupción del juego (3 bytes)
MB_EVFRAME  equ MB+28           ; rutina "frame flyback" del firmware (2)
MB_EVFAST   equ MB+30           ; rutina "fast ticker" (2)
MB_VSYNC    equ MB+32
MB_INEV     equ MB+33
MB_BUF      equ MB+34           ; 12 bytes de intercambio
MB_NIBHI    equ MB+46           ; página de gate_nib del modo actual
MB_END      equ MB+47

; --- segundo buzón (banco 3): estado del PPI/PSG y matriz del teclado ---
MB2_MATRIX  equ MB2+0           ; 10 líneas (bits a 0 = pulsado)
MB2_PPIA    equ MB2+10
MB2_PPIC    equ MB2+11
MB2_PSGSEL  equ MB2+12
MB2_PSG     equ MB2+13          ; 16 registros del PSG (sombra)
MB2_DIRTY   equ MB2+29          ; 24 bits: filas de atributos por recalcular

; ids de manejadores internos (el portador usa 0..249)
ID_ISR      equ 250
ID_SPAN     equ 251
ID_OUTBYTE  equ 252
ID_SOUND    equ 253
ID_READCH   equ 254
ID_MIRROR   equ 255

; ---------------------------------------------------------------------------
; Vectores (bancos 0 y 4)
; ---------------------------------------------------------------------------
        org $0000
        jp local_rst0
        org $0008
        jp rst8_entry
        org $0010
        jp fast_ld_hl_a
        org $0018
        jp fast_ld_de_a
        org $0020
        ld a,(hl)               ; RAM LAM del firmware
        ret
        org $0028
        jp local_halt
        org $0030
        jp rst30_entry
        org $0038
        jp isr_entry

; ---------------------------------------------------------------------------
; PUERTA (bancos 0 y 4, misma dirección)
; ---------------------------------------------------------------------------
        org GATE
gate_start:

; RST $30 + id: cruce al HAL (ids 0-127 del portador y los internos)
rst30_entry:
        push af
        ld a,i
        di
        push af                 ; [iff][AF][ret]
        push hl
        push de
        ld hl,8
        add hl,sp               ; -> ranura de ret ([DE][HL][iff][AF][ret])
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld a,(de)               ; id
        inc de
        ld (hl),d
        dec hl
        ld (hl),e               ; ret + 1
        ld (MB_ID),a
        pop de
        pop hl
        jp gate_body

; RST $00 + id: manejador local (escrituras en pantalla de 2 bytes).
; Deja [manejador][ret] y el manejador salta el byte id (como en ZX->CPC).
local_rst0:
        push hl
        push af
        push de
        ld hl,6
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld l,(hl)               ; id
        ld h,0
        add hl,hl
        ld de,gate_ltab
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        pop de
        pop af
        ex (sp),hl              ; [manejador][ret]
        ret

; RST $08: sitio de 1 byte -> id local por la dirección de retorno
rst8_entry:
        push hl
        push af
        push de
        ld hl,6
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        xor h
        and 31
        ld e,a
        ld d,32
.probe: push de
        push hl
        ld d,0
        ld hl,gate_hash+32
        add hl,de
        ld a,(hl)               ; byte alto
        pop hl
        or a
        jr z,.nf
        cp h
        jr nz,.nx
        push hl
        ld hl,gate_hash
        add hl,de
        ld a,(hl)               ; byte bajo
        pop hl
        cp l
        jr nz,.nx
        ld hl,gate_hash+64
        add hl,de
        ld l,(hl)               ; id local
        ld h,0
        add hl,hl
        ld de,gate_ltab
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = manejador
        pop de
        pop de
        pop af
        ex (sp),hl              ; [manejador][ret]
        ret
.nx:    pop de
        ld a,e
        inc a
        and 31
        ld e,a
        dec d
        jr nz,.probe
        push de
.nf:    pop de
        pop de                  ; RST 1 original (LOW JUMP): no soportado
        pop af
        pop hl
        ret

; Cruce completo al HAL. Entrada: [iff][AF][ret], interrupciones desactivadas
; y MB_ID ya escrito. Guarda los registros en el buzón, cambia de banco,
; ejecuta el manejador con los registros del juego y vuelve.
gate_body:
        ld (MB_BC),bc
        ld (MB_DE),de
        ld (MB_HL),hl
        ld (MB_IX),ix
        ld (MB_IY),iy
        pop bc
        ld a,c
        ld (MB_IFF),a
        pop bc
        ld (MB_AF),bc
        ld (MB_SP),sp
        ld bc,$1FFD
        ld a,CFG_HAL
        out (c),a
        ld sp,HAL_STACK
        call hal_invoke
        ld bc,$1FFD
        ld a,CFG_GAME
        out (c),a
        ld sp,(MB_SP)
        ld ix,(MB_IX)
        ld iy,(MB_IY)
        ld de,(MB_DE)
        ld hl,(MB_HL)
        ld bc,(MB_AF)
        push bc
        ld bc,(MB_BC)
        ld a,(MB_IFF)
        and 4
        jr z,.di
        pop af
        ei
        ret
.di:    pop af
        ret

; --- reflejo rápido de LD (HL),A / LD (DE),A (RST $10 / RST $18) ---
fast_ld_de_a:
        ld (de),a
        ex de,hl
        call fast_mirror
        ex de,hl
        ret
fast_ld_hl_a:
        ld (hl),a
fast_mirror:                    ; refleja (HL). Conserva todo.
        push af
        ld a,(MB_SCRHI)
        xor h
        and $C0
        jr nz,.out
        ld a,(MB_FASTOK)
        or a
        jr z,.slow
        push bc
        push de
        push hl
        call fast_pair
        pop hl
        pop de
        pop bc
.out:   pop af
        ret
.slow:  pop af
        ld (MB_X1),hl
        push af
        ld a,i
        di
        push af                 ; [iff][AF][ret]
        ld a,ID_MIRROR
        ld (MB_ID),a
        jp gate_body

; HL = dirección en la pantalla CPC -> convierte su par y escribe el byte ZX.
; Todo en la configuración del juego salvo la escritura final.
fast_pair:
        ld a,h
        rrca
        rrca
        rrca
        and 7
        ld c,a                  ; línea dentro del carácter
        ld a,h
        and 7
        ld h,a
        ld de,(MB_START)
        or a
        sbc hl,de
        ld a,h
        and 7
        ld h,a                  ; rel (0-2047)
        ld a,l
        rrca
        rrca
        rrca
        rrca
        and 15
        ld e,a
        ld a,h
        add a,a
        add a,a
        add a,a
        add a,a
        or e                    ; rel >> 4
        ld e,a
        ld d,0
        push hl
        ld hl,gate_rowtab
        add hl,de
        ld a,(hl)               ; fila
        ld b,a
        add a,a
        ld e,a
        ld hl,gate_rowstart
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        pop hl
        or a
        sbc hl,de               ; x dentro de la fila
        ld a,h
        or a
        ret nz
        ld a,b
        add a,a
        add a,a
        add a,a
        add a,c
        sub CROP_Y
        ret c
        cp 192
        ret nc
        ld e,a                  ; línea ZX
        ld a,l
        sub CROP_X
        ret c
        cp 64
        ret nc
        and $3E
        ld d,a                  ; par (relativo al recorte)
        ld a,e
        call mark_dirty
        ; primer byte del par = dirección original con el bit 0 a cero (el inicio
        ; de la pantalla, las filas y el recorte son pares). El llamador guardó HL.
        ld hl,2
        add hl,sp
        ld a,(hl)
        inc hl
        ld h,(hl)
        and $FE
        ld l,a
        push de
        ld a,(hl)
        inc hl
        push hl
        ld l,a
        ld a,(MB_NIBHI)
        ld h,a
        ld a,(hl)
        rlca
        rlca
        rlca
        rlca
        ld c,a
        pop hl
        ld a,(hl)
        ld l,a
        ld a,(MB_NIBHI)
        ld h,a
        ld a,(hl)
        or c
        ld c,a                  ; C = byte ZX
        pop de
        ; dirección ZX: línea E, columna D/2
        ld a,e
        and 7
        or $40
        ld h,a
        ld a,e
        and $C0
        rrca
        rrca
        rrca
        or h
        ld h,a
        ld a,e
        and $38
        add a,a
        add a,a
        ld l,a
        ld a,d
        srl a
        or l
        ld l,a
        ; escribir en el banco 7 (visible en $4000 solo con la configuración HAL).
        ; Sin tocar la pila mientras tanto: puede no estar mapeada.
        ld d,c
        ld a,i
        push af
        di
        ld bc,$1FFD
        ld a,CFG_HAL
        out (c),a
        ld (hl),d
        ld a,CFG_GAME
        out (c),a
        pop af
        ret po
        ei
        ret

; marca como sucia la fila de atributos de la línea ZX A (0-191): el HAL
; recalcula primero esas filas. Destruye AF y HL. Vale en las dos configuraciones.
mark_dirty:
        push bc
        rrca
        rrca
        rrca
        and 31                  ; fila (0-23)
        ld c,a
        and 7
        ld hl,gate_bits
        add a,l
        ld l,a
        jr nc,.n
        inc h
.n:     ld b,(hl)
        ld a,c
        rrca
        rrca
        rrca
        and 3
        add a,MB2_DIRTY&255
        ld l,a
        ld h,MB2_DIRTY/256
        ld a,(hl)
        or b
        ld (hl),a
        pop bc
        ret
gate_bits:
        db 1,2,4,8,16,32,64,128

; --- rutinas locales (se ejecutan con la memoria del juego) ---

; HALT del CPC (300 Hz) -> espera ~1/300 s
local_halt:
        push af
        push bc
        ld b,210
.w:     ex (sp),hl
        ex (sp),hl
        djnz .w
        pop bc
        pop af
        ret

; LDIR/LDDR/LDI/LDD hacia la pantalla: se ejecutan aquí y luego se refleja.
; LDIR/LDDR guardan el buzón si el bloque lo pisa (p.ej. un borrado de 16K).
local_ldir:
        call mb_overlap
        jr nc,.plain
        call mb_backup
        push de
        ldir
        call mb_restore
        ex (sp),hl              ; HL = DE inicial, [HL final]
        ld (MB_X1),hl
        pop hl                  ; HL final (como tras un LDIR normal)
        ld (MB_X2),de
        jp span_go
.plain: ld (MB_X1),de
        ldir
        jp span_after
local_ldi:
        ld (MB_X1),de
        ldi
        jp span_after
local_lddr:
        push de
        call mb_backup
        lddr
        call mb_restore
        jr span_down
local_ldd:
        push de
        ldd
span_down:                      ; rango (DE, inicio] -> [DE+1, inicio+1)
        ex (sp),hl
        inc hl
        ld (MB_X2),hl
        ex de,hl
        inc hl
        ld (MB_X1),hl
        dec hl
        ex de,hl
        pop hl
        jr span_go
; ¿[DE, DE+BC) se solapa con alguno de los dos buzones? -> CF. Conserva todo salvo F.
mb_overlap:
        push hl
        ld hl,MB
        call mb_ov1
        jr c,.x
        ld hl,MB2
        call mb_ov1
.x:     pop hl
        ret
; HL = inicio de un buzón de 48 bytes. Conserva todo salvo F y HL.
mb_ov1: push af
        push hl                 ; [base][AF]
        ld a,l
        add a,47
        ld l,a
        jr nc,.n
        inc h
.n:     or a
        sbc hl,de               ; base+47 - DE
        jr c,.no                ; empieza por encima del buzón
        ld h,d
        ld l,e
        add hl,bc
        dec hl                  ; última dirección escrita
        ex (sp),hl              ; HL = base, [última]
        ex de,hl                ; DE = base, HL = DE original
        ex (sp),hl              ; HL = última, [DE original]
        or a
        sbc hl,de               ; última - base
        pop de
        jr c,.no2               ; termina por debajo del buzón
        pop af
        scf
        ret
.no:    pop hl
.no2:   pop af
        or a
        ret

; copia de seguridad de los buzones en la puerta (banco 0). Conserva todo.
mb_backup:
        push af
        push bc
        push de
        push hl
        ld hl,MB
        ld de,mb_save
        ld bc,48
        ldir
        ld hl,MB2
        ld bc,48
        ldir
        pop hl
        pop de
        pop bc
        pop af
        ret
mb_restore:
        push af
        push bc
        push de
        push hl
        ld hl,mb_save
        ld de,MB
        ld bc,48
        ldir
        ld de,MB2
        ld bc,48
        ldir
        pop hl
        pop de
        pop bc
        pop af
        ret

span_after:
        ld (MB_X2),de
span_go:
        push af
        ld a,i
        di
        push af                 ; [iff][AF][ret]
        ld a,ID_SPAN
        ld (MB_ID),a
        jp gate_body

; OUTI/OTIR/OUTD/OTDR hacia puertos del CPC: los bytes se leen aquí
local_outi:
        push af
        ld a,(hl)
        ld (MB_X1),a
        dec b
        inc hl
        pop af
        call outbyte
        push af
        ld a,b
        or a
        pop af
        ret
local_otir:
        call local_outi
        jr nz,local_otir
        ret
local_outd:
        push af
        ld a,(hl)
        ld (MB_X1),a
        dec b
        dec hl
        pop af
        call outbyte
        push af
        ld a,b
        or a
        pop af
        ret
local_otdr:
        call local_outd
        jr nz,local_otdr
        ret
outbyte:
        push af
        ld a,i
        di
        push af                 ; [iff][AF][ret]
        ld a,ID_OUTBYTE
        ld (MB_ID),a
        jp gate_body

; SOUND QUEUE: copiar el bloque de 9 bytes al buzón antes de cruzar
local_sound_queue:
        push bc
        push de
        push hl
        ld de,MB_BUF
        ld bc,9
        ldir
        pop hl
        pop de
        pop bc
        call .go
        scf
        ret
.go:
        push af
        ld a,i
        di
        push af                 ; [iff][AF][ret]
        ld a,ID_SOUND
        ld (MB_ID),a
        jp gate_body

; MC WAIT FLYBACK: esperar a la siguiente interrupción de frame
local_wait_flyback:
        push af
        push hl
        ld hl,MB_FRAME
        ld a,i
        jp po,.busy             ; interrupciones desactivadas: espera activa
        ld a,(hl)
.w:     halt
        cp (hl)
        jr z,.w
        pop hl
        pop af
        ret
.busy:  push bc
        ld bc,5000
.b:     dec bc
        ld a,b
        or c
        jr nz,.b
        pop bc
        pop hl
        pop af
        ret

; KM WAIT CHAR / KM WAIT KEY
local_wait_char:
.w:     call local_read_char
        ret c
        halt
        jr .w

; KM READ CHAR / KM READ KEY
local_read_char:
        push af
        ld a,i
        di
        push af                 ; [iff][AF][ret]
        ld a,ID_READCH
        ld (MB_ID),a
        jp gate_body

; --- E/S del CPC emulada en la propia puerta (sin cambiar de banco) ---

; OUT: BC = puerto, A = valor. Conserva todo. El PPI y el PSG se resuelven
; aquí; el gate array y el CRTC cruzan al HAL.
local_out:
        push af
        push de
        push hl
        ld e,a
        ld a,b
        bit 3,a
        jr nz,.nppi
        and 3
        jr z,.pa
        cp 2
        jr z,.pc
        cp 3
        jr nz,.done
        bit 7,e                 ; control del PPI
        jr nz,.done
        ld a,e
        rrca
        and 7
        ld d,a
        ld a,1
        inc d
.rot:   dec d
        jr z,.bit
        rlca
        jr .rot
.bit:   ld d,a                  ; D = bit
        ld a,(MB2_PPIC)
        bit 0,e
        jr z,.res
        or d
        jr .pc2
.res:   ld e,a
        ld a,d
        cpl
        and e
        jr .pc2
.pa:    ld a,e
        ld (MB2_PPIA),a
        jr .done
.pc:    ld a,e
.pc2:   ld (MB2_PPIC),a
        and $C0
        cp $C0
        jr z,.sel
        cp $80
        jr nz,.done
        ld a,(MB2_PPIA)         ; escritura en el PSG
        ld e,a
        ld a,(MB2_PSGSEL)
        call local_psg_write
        jr .done
.sel:   ld a,(MB2_PPIA)
        and 15
        ld (MB2_PSGSEL),a
        jr .done
.nppi:  and $C0
        cp $40
        jr z,.cross             ; gate array
        bit 6,b
        jr nz,.done             ; ni gate array ni CRTC: se ignora
.cross: ld a,e
        ld (MB_X1),a
        call cross_out
.done:  pop hl
        pop de
        pop af
        ret
cross_out:
        push af
        ld a,i
        di
        push af
        ld a,ID_OUTBYTE
        ld (MB_ID),a
        jp gate_body

; IN: BC = puerto -> A = valor. Conserva BC, DE, HL (y no toca la pila del HAL).
local_in:
        ld a,b
        bit 3,a
        jr nz,.ff
        and 3
        jr z,.pa
        cp 1
        jr z,.pb
        ld a,(MB2_PPIC)
        ret
.pb:    ld a,(MB_VSYNC)
        or a
        jr z,.nv
        dec a
        ld (MB_VSYNC),a
        ld a,$5F
        ret
.nv:    ld a,$5E
        ret
.pa:    ld a,(MB2_PPIC)
        and $C0
        cp $40
        jr nz,.ff
        ld a,(MB2_PSGSEL)
        cp 14
        jr nz,.reg
        ld a,(MB2_PPIC)
        and 15
        cp 10
        jr nc,.ff
        push hl
        ld hl,MB2_MATRIX
        add a,l
        ld l,a
        jr nc,.m
        inc h
.m:     ld a,(hl)
        pop hl
        ret
.ff:    ld a,$FF
        ret
.reg:   push hl
        ld hl,MB2_PSG
        add a,l
        ld l,a
        jr nc,.r
        inc h
.r:     ld a,(hl)
        pop hl
        ret

; PSG del CPC (1 MHz) -> AY del Spectrum (1,7734 MHz). A = registro, E = valor.
; Destruye AF, HL.
local_psg_write:
        cp 14
        ret nc
        push bc
        push de
        ld c,a
        ld hl,MB2_PSG
        add a,l
        ld l,a
        jr nc,.s
        inc h
.s:     ld (hl),e
        ld a,c
        cp 6
        jr c,.tone
        jr z,.noise
        cp 11
        jr z,.env
        cp 12
        jr z,.env
        cp 7
        jr nz,.direct
        ld a,e
        or $C0                  ; puertos del AY en entrada
        ld e,a
        ld a,7
.direct:
        call ay_out
        pop de
        pop bc
        ret
.noise: ld l,e
        ld h,0
        call up_scale
        ld a,l
        cp 32
        jr c,.n1
        ld a,31
.n1:    ld e,a
        ld a,6
        jr .direct
.env:   ld hl,(MB2_PSG+11)
        call up_scale
        push hl
        ld e,l
        ld a,11
        call ay_out
        pop hl
        ld e,h
        ld a,12
        jr .direct
.tone:  and 6
        ld c,a
        ld hl,MB2_PSG
        add a,l
        ld l,a
        jr nc,.t0
        inc h
.t0:    ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        ld a,h
        and 15
        ld h,a
        call up_scale
        ld a,h
        cp 16
        jr c,.t1
        ld hl,$0FFF
.t1:    push hl
        ld e,l
        ld a,c
        call ay_out
        pop hl
        ld e,h
        ld a,c
        inc a
        jr .direct

; HL = HL * 1,75
up_scale:
        push de
        ld d,h
        ld e,l
        srl d
        rr e
        add hl,de
        srl d
        rr e
        add hl,de
        pop de
        ret

; E -> registro A del AY del Spectrum
ay_out: push bc
        ld bc,$FFFD
        out (c),a
        ld b,$BF
        out (c),e
        pop bc
        ret

; --- interrupción (50 Hz) ---
isr_entry:
        call .work              ; trabajo del HAL (teclado, pantalla, sonido)
        jr .ev
.work:
        push af
        ld a,i
        di
        push af                 ; [iff][AF][ret]
        ld a,ID_ISR
        ld (MB_ID),a
        jp gate_body
.ev:
        push af
        ld a,(MB_INEV)
        or a
        jr nz,.skip
        inc a
        ld (MB_INEV),a
        push bc
        push de
        push hl
        push ix
        push iy
        call run_events
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        xor a
        ld (MB_INEV),a
.skip:  pop af
        ei
        ret

; rutina de interrupción del juego (x6) y eventos del firmware
run_events:
        ld a,(MB_GAMEISR)
        cp $C3
        jr nz,.nogame
        ld b,6
.g:     push bc
        ld a,b
        cp 6
        ld a,0
        jr nz,.nv
        ld a,2
.nv:    ld (MB_VSYNC),a
        ld hl,.back
        push hl
        jp MB_GAMEISR           ; termina con EI / RET
.back:  di
        pop bc
        djnz .g
.nogame:
        ld hl,(MB_EVFRAME)
        ld a,h
        or l
        call nz,.call
        ld b,6
.t:     push bc
        ld hl,(MB_EVFAST)
        ld a,h
        or l
        call nz,.call
        pop bc
        djnz .t
        ret
.call:  call .jp
        di
        ret
.jp:    jp (hl)

        align 256
gate_nib:       ds 768, 0       ; byte CPC -> nibble de píxeles (modos 0, 1 y 2)
gate_rowtab:    ds 128, 0       ; (desplazamiento/16) -> fila
gate_rowstart:  ds 64, 0        ; fila -> desplazamiento
gate_hash:      ds 96, 0        ; sitios de 1 byte (bajos, altos, id)
gate_ltab:      ds NLOCAL*2, 0  ; id local -> manejador
mb_save:        ds 96, 0        ; copia de los buzones durante LDIR/LDDR
gate_gen:                       ; manejadores locales generados (los añade el portador)

; ---------------------------------------------------------------------------
; HAL (configuración HAL): banco 6 en $8000
; ---------------------------------------------------------------------------
HAL_STACK   equ $BFFE

NIB         equ $8000           ; byte CPC -> nibble de píxeles (modo actual)
NIBH        equ $8100           ; lo mismo desplazado 4 bits
PRES_LO     equ $8200           ; byte CPC -> plumas 1-7 presentes
PRES_HI     equ $8300           ; byte CPC -> plumas 8-15 presentes
COMB_LO     equ $8400           ; plumas 0-7 -> colores ZX
COMB_HI     equ $8500           ; plumas 8-15 -> colores ZX
JPTAB       equ $8600           ; id -> manejador (bajos +0, altos +256)
ROWTAB      equ $8800
ROWSTART    equ $8880
ACC         equ $8900           ; acumuladores de plumas por celda (32 + 32)
INK_OF      equ $8A00           ; máscara de colores ZX -> tinta (por prioridad)

        org $8B00
; Ejecuta el manejador MB_ID con los registros del juego y los devuelve
hal_invoke:
        ld a,(MB_ID)
        ld l,a
        ld h,JPTAB/256
        ld e,(hl)
        inc h
        ld d,(hl)
        ld (.jp+1),de
        ld hl,(MB_AF)
        push hl
        pop af
        ld bc,(MB_BC)
        ld de,(MB_DE)
        ld hl,(MB_HL)
        ld ix,(MB_IX)
        ld iy,(MB_IY)
.jp:    call 0
        push af
        ld (MB_BC),bc
        ld (MB_DE),de
        ld (MB_HL),hl
        ld (MB_IX),ix
        ld (MB_IY),iy
        pop hl
        ld (MB_AF),hl
        ret

; ---------------------------------------------------------------------------
; Manejadores internos
; ---------------------------------------------------------------------------
h_isr:  push af                 ; la interrupción no debe alterar ningún registro
        push bc
        push de
        push hl
        push ix
        push iy
        ld hl,MB_FRAME
        inc (hl)
        ld a,2
        ld (MB_VSYNC),a
        call kb_scan
        call refresh
        call snd_tick
        pop iy
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ret

h_span: push af
        push bc
        push de
        push hl
        ld hl,(MB_X1)
        ld de,(MB_X2)
        ; rangos grandes (> 512 bytes): refresco completo en la próxima interrupción
        push hl
        push de
        ex de,hl
        or a
        sbc hl,de               ; tamaño
        ld a,h
        pop de
        pop hl
        cp 2
        jr c,.l
        ld a,1
        ld (full_pending),a
        jr .done
.l:     ld a,l
        cp e
        jr nz,.do
        ld a,h
        cp d
        jr z,.done
.do:    call mirror_hl
        inc hl
        jr .l
.done:  pop hl
        pop de
        pop bc
        pop af
        ret

h_outbyte:
        push af
        ld a,(MB_X1)
        call cpc_out
        pop af
        ret

h_mirror:
        push hl
        ld hl,(MB_X1)
        call mirror_hl
        pop hl
        ret

; ---------------------------------------------------------------------------
; Teclado: Spectrum -> matriz del CPC
; ---------------------------------------------------------------------------
kb_scan:
        ld hl,MB2_MATRIX
        ld b,10
.clr:   ld (hl),$FF
        inc hl
        djnz .clr
        ld ix,zx2cpc
        ld bc,$FEFE
.row:   in a,(c)
        cpl
        and $1F
        ld e,a
        ld d,5
.bit:   rr e
        jr nc,.nk
        ld a,(ix+0)
        call press_cpc
        ld a,(ix+1)
        call press_cpc
.nk:    inc ix
        inc ix
        dec d
        jr nz,.bit
        rlc b
        jr c,.row
        in a,($1F)              ; Kempston -> joystick 0 (línea 9)
        cp $FF
        ret z
        ld e,$FF
        rra
        jr nc,.j1
        res 3,e
.j1:    rra
        jr nc,.j2
        res 2,e
.j2:    rra
        jr nc,.j3
        res 1,e
.j3:    rra
        jr nc,.j4
        res 0,e
.j4:    rra
        jr nc,.j5
        res 5,e
.j5:    ld a,(MB2_MATRIX+9)
        and e
        ld (MB2_MATRIX+9),a
        ret

; A = tecla CPC (línea*8+bit) o $FF. Conserva BC, DE, IX.
press_cpc:
        cp 80
        ret nc
        push bc
        ld c,a
        and 7
        ld hl,bitmask
        add a,l
        ld l,a
        ld b,(hl)
        ld a,c
        rrca
        rrca
        rrca
        and 15
        ld hl,MB2_MATRIX
        add a,l
        ld l,a
        ld a,b
        cpl
        and (hl)
        ld (hl),a
        pop bc
        ret

; ---------------------------------------------------------------------------
; E/S del CPC emulada
; ---------------------------------------------------------------------------
; OUT del gate array / CRTC: BC = puerto, A = valor. Conserva todo.
cpc_out:
        push af
        push bc
        push de
        push hl
        push ix
        ld e,a
        ld a,b
        and $C0
        cp $40
        call z,ga_write
        ld a,b
        bit 6,a
        call z,crtc_write
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ret

ga_write:
        ld a,e
        and $C0
        jr z,.pen
        cp $40
        jr z,.col
        cp $80
        ret nz                  ; banca de RAM del 6128: no soportada
        ld a,e
        and 3
        ld hl,cpc_mode
        cp (hl)
        ret z
        jp set_mode
.pen:   ld a,e
        bit 4,a
        ld a,16
        jr nz,.p
        ld a,e
        and 15
.p:     ld (ga_pen),a
        ret
.col:   ld a,e
        and 31
        ld hl,hw2zx
        add a,l
        ld l,a
        ld e,(hl)
        ld a,(ga_pen)
        cp 16
        jp nz,set_pen_colour
        ld a,e
        out ($FE),a
        ret

crtc_write:
        ld a,b
        and 3
        jr nz,.data
        ld a,e
        ld (crtc_sel),a
        ret
.data:  cp 1
        ret nz
        ld a,(crtc_sel)
        ld hl,crtc_r1
        cp 1
        jr z,.set
        ld hl,crtc_r12
        cp 12
        jr z,.set
        ld hl,crtc_r13
        cp 13
        ret nz
.set:   ld a,e
        cp (hl)
        ret z
        ld (hl),a
        jp geometry

snd_tick:
        ld hl,snd_time
        ld a,(hl)
        or a
        ret z
        dec (hl)
        ret nz
        ld e,0
        ld a,8
        call ay_out
        ld a,9
        call ay_out
        ld a,10
        jp ay_out

; SOUND QUEUE: bloque de 9 bytes en MB_BUF
h_sound:
        push af
        push bc
        push de
        push hl
        push ix
        ld ix,MB_BUF
        ld e,(ix+3)
        ld a,0
        call local_psg_write
        ld e,(ix+4)
        ld a,1
        call local_psg_write
        ld e,$3E
        ld a,7
        call local_psg_write
        ld a,(ix+6)
        and 15
        jr nz,.v
        ld a,12
.v:     ld e,a
        ld a,8
        call local_psg_write
        ld a,(ix+7)
        srl a
        jr nz,.d
        inc a
.d:     ld (snd_time),a
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ret

; ---------------------------------------------------------------------------
; Conversión de pantalla
; ---------------------------------------------------------------------------
geometry:
        push af
        push bc
        push de
        push hl
        ld a,(crtc_r1)
        add a,a
        ld (row_len),a
        ld a,(crtc_r12)
        and $30
        add a,a
        add a,a
        ld (MB_SCRHI),a
        ld a,(crtc_r12)
        and 3
        ld h,a
        ld a,(crtc_r13)
        ld l,a
        add hl,hl
        ld a,h
        and 7
        ld h,a
        ld (MB_START),hl
        ld hl,0
        ld de,ROWSTART
        ld b,32
.rs:    ex de,hl
        ld (hl),e
        inc hl
        ld (hl),d
        inc hl
        ex de,hl
        ld a,(row_len)
        add a,l
        ld l,a
        jr nc,.rs1
        inc h
.rs1:   djnz .rs
        ld hl,ROWTAB
        ld c,0
        ld de,0
        ld b,128
.rt:    push hl
.adv:   ld a,c
        cp 31
        jr nc,.ok
        inc a
        add a,a
        add a,ROWSTART&255
        ld l,a
        ld h,ROWSTART/256
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a
        or a
        sbc hl,de
        jr z,.up
        jr nc,.ok
.up:    inc c
        jr .adv
.ok:    pop hl
        ld (hl),c
        inc hl
        ex de,hl
        push bc
        ld bc,16
        add hl,bc
        pop bc
        ex de,hl
        djnz .rt
        call fast_check
        ld a,1
        ld (full_pending),a
        pop hl
        pop de
        pop bc
        pop af
        ret

; la vía rápida usa tablas de la puerta calculadas al portar: solo vale si la
; geometría no ha cambiado (hay tablas para los modos 0, 1 y 2)
fast_check:
        ld a,(crtc_r1)
        cp INIT_R1
        jr nz,.no
        ld a,(cpc_mode)
        cp 3
        jr z,.no
        add a,gate_nib/256
        ld (MB_NIBHI),a
        ld a,1
        ld (MB_FASTOK),a
        ret
.no:    xor a
        ld (MB_FASTOK),a
        ret

set_mode:
        and 3
        ld (cpc_mode),a
        push af
        push bc
        push de
        push hl
        ld l,0
.b:     ld a,l
        call nib_of
        ld h,NIB/256
        ld (hl),a
        rlca
        rlca
        rlca
        rlca
        inc h
        ld (hl),a
        ld a,l
        call pres_of
        ld h,PRES_LO/256
        ld (hl),d
        inc h
        ld (hl),e
        inc l
        jr nz,.b
        call fast_check
        ld a,1
        ld (full_pending),a
        pop hl
        pop de
        pop bc
        pop af
        ret

nib_of: ld c,a
        ld a,(cpc_mode)
        or a
        jr z,.m0
        cp 1
        jr z,.m1
        ld b,4
        ld e,0
.m2:    rl c
        rl e
        rl c
        djnz .m2
        ld a,e
        ret
.m1:    ld a,c
        rrca
        rrca
        rrca
        rrca
        or c
        and 15
        ret
.m0:    ld b,0
        ld a,c
        and $AA
        jr z,.p0
        ld b,$0C
.p0:    ld a,c
        and $55
        ld a,b
        ret z
        or 3
        ret

pres_of:
        ld c,a
        ld de,0
        ld a,(cpc_mode)
        or a
        jr z,.m0
        cp 1
        jr nz,.m2
        ld b,4
.m1l:   ld a,c
        rlca
        and 1
        ld h,a
        ld a,c
        rrca
        rrca
        rrca
        rrca
        rlca
        and 1
        add a,a
        or h
        call .add
        rlc c
        djnz .m1l
        ret
.m2:    ld a,c
        or a
        ret z
        ld d,2
        ret
.m0:    ld a,c
        call pen_m0
        call .add
        ld a,c
        rlca
        call pen_m0
.add:   or a
        ret z
        push bc
        cp 8
        jr nc,.hi
        ld b,a
        ld a,1
.s:     rlca
        djnz .s
        or d
        ld d,a
        pop bc
        ret
.hi:    sub 8
        ld b,a
        inc b
        ld a,$80
.sh:    rlca
        djnz .sh
        or e
        ld e,a
        pop bc
        ret

pen_m0: push bc
        ld c,a
        xor a
        bit 1,c
        jr z,.a
        or 8
.a:     bit 5,c
        jr z,.b
        or 4
.b:     bit 3,c
        jr z,.c
        or 2
.c:     bit 7,c
        jr z,.d
        or 1
.d:     pop bc
        ret

; A = pluma (0-15), E = color ZX. Actualiza COMB de forma incremental: solo
; cambian las entradas que contienen la pluma, y cada una se obtiene de la
; misma entrada sin ella (que ya es correcta). Destruye AF, BC, DE, HL.
set_pen_colour:
        cp 16
        ret nc
        ld c,a
        ld hl,pen_zx
        add a,l
        ld l,a
        ld a,(hl)
        cp e
        ret z
        ld (hl),e
        ld a,c
        ld h,COMB_LO/256
        cp 8
        jr c,.lo
        sub 8
        inc h
.lo:    push hl
        ld hl,bitmask
        add a,l
        ld l,a
        ld b,(hl)               ; B = bit de la pluma
        ld a,e
        ld hl,bitmask
        add a,l
        ld l,a
        ld d,(hl)               ; D = 1 << color
        pop hl
        ld a,b
        cpl
        ld c,a                  ; C = máscara sin la pluma
        ld l,0
.l:     ld a,l
        and b
        jr z,.n
        ld a,l
        and c
        ld e,l
        ld l,a
        ld a,(hl)
        or d
        ld l,e
        ld (hl),a
.n:     inc l
        jr nz,.l
        ret

; línea CPC A (0-199) -> HL (banco 3). Destruye DE.
cpc_line_addr:
        push bc
        ld c,a
        rrca
        rrca
        rrca
        and 31
        add a,a
        add a,ROWSTART&255
        ld l,a
        ld h,ROWSTART/256
        ld e,(hl)
        inc hl
        ld d,(hl)
        ld hl,(MB_START)
        add hl,de
        ld a,h
        and 7
        ld h,a
        ld a,c
        and 7
        add a,a
        add a,a
        add a,a
        or h
        ld h,a
        ld a,(MB_SCRHI)
        and $C0
        or h
        ld h,a
        pop bc
        ret

zx_line_addr:
        ld c,a
        and 7
        or $40
        ld d,a
        ld a,c
        and $C0
        rrca
        rrca
        rrca
        or d
        ld d,a
        ld a,c
        and $38
        add a,a
        add a,a
        ld e,a
        ret

; Convierte la línea ZX A (0-191). Lee la línea CPC con POP (el HAL corre
; siempre con las interrupciones desactivadas).
conv_line:
        push af
        add a,CROP_Y
        call cpc_line_addr
        ld de,CROP_X
        add hl,de
        pop af
        call zx_line_addr       ; DE = línea ZX
        ld (.sp+1),sp
        ld sp,hl
        ld h,NIBH/256
        rept 32
        pop bc
        ld l,c
        ld a,(hl)
        ld l,b
        dec h
        or (hl)
        inc h
        ld (de),a
        inc e
        endr
.sp:    ld sp,0
        ret

; Atributos de la fila de caracteres A (0-23): OR de las plumas presentes en
; los 16 bytes CPC de cada celda -> tinta; papel = color de la pluma 0.
attr_row:
        ld (.row+1),a
        ld hl,ACC
        ld b,64
.clr:   ld (hl),0
        inc l
        djnz .clr
        ld c,0
.line:  push bc
.row:   ld a,0
        add a,a
        add a,a
        add a,a
        add a,c
        add a,CROP_Y
        call cpc_line_addr
        ld de,CROP_X
        add hl,de
        ld (.sp+1),sp
        ld sp,hl
        ld de,ACC
        ld a,(cpc_mode)
        or a
        jp z,.m0
        ld h,PRES_LO/256
        rept 32
        pop bc
        ld l,c
        ld a,(hl)
        ld l,b
        or (hl)
        ex de,hl
        or (hl)
        ld (hl),a
        inc l
        ex de,hl
        endr
        jp .sp
.m0:
        rept 32
        pop bc
        ld h,PRES_LO/256
        ld l,c
        ld a,(hl)
        ld l,b
        or (hl)
        ex de,hl
        or (hl)
        ld (hl),a
        ex de,hl
        ld h,PRES_HI/256
        ld a,(hl)
        ld l,c
        or (hl)
        ex de,hl
        set 5,l
        or (hl)
        ld (hl),a
        res 5,l
        inc l
        ex de,hl
        endr
.sp:    ld sp,0
        pop bc
        inc c
        ld a,c
        cp 8
        jp nz,.line
        ; escribir los 32 atributos
        ld a,(.row+1)
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,$5800
        add hl,de
        ex de,hl                ; DE = atributos
        ld a,(pen_zx)
        ld c,a                  ; color del papel
        add a,a
        add a,a
        add a,a
        or $40
        ld (.pap+1),a
        ld a,c
        ld hl,bitmask
        add a,l
        ld l,a
        ld a,(hl)
        cpl
        ld (.pm+1),a            ; máscara sin el color del papel
        ld b,0
.cell:  ld hl,ACC
        ld l,b
        ld a,(hl)
        set 5,l
        ld l,(hl)
        ld h,COMB_HI/256
        ld c,(hl)               ; colores de las plumas 8-15
        ld l,a
        dec h
        ld a,(hl)               ; colores de las plumas 1-7
        or c
.pm:    and 0
        ld l,a
        ld h,INK_OF/256
        ld a,(hl)
.pap:   or 0
        ld (de),a
        inc de
        inc b
        ld a,b
        cp 32
        jr nz,.cell
        ret

; Refresco por frame: REFRESH_LINES líneas y, cada 2 frames, una fila de
; atributos. Pantalla completa si cambió el modo o la geometría.
refresh:
        ld a,(full_pending)
        or a
        jr z,.part
        xor a
        ld (full_pending),a
        ld hl,MB2_DIRTY
        ld (hl),a
        inc hl
        ld (hl),a
        inc hl
        ld (hl),a
        ld b,192
.f:     push bc
        ld a,192
        sub b
        call conv_line
        pop bc
        djnz .f
        ld b,24
.fa:    push bc
        ld a,24
        sub b
        call attr_row
        pop bc
        djnz .fa
        ret
.part:  ld a,(refresh_y)
        ld b,REFRESH_LINES
.l:     push bc
        push af
        call conv_line
        pop af
        inc a
        cp 192
        jr c,.n
        xor a
.n:     pop bc
        djnz .l
        ld (refresh_y),a
        ld a,(MB_FRAME)
        rra
        ret c
        ; primero las filas marcadas como sucias
        ld hl,MB2_DIRTY
        ld c,0
        ld b,3
.d:     ld a,(hl)
        or a
        jr nz,.found
        inc hl
        ld a,c
        add a,8
        ld c,a
        djnz .d
        ; ninguna: barrido lento de seguridad (una fila cada 8 frames)
        ld a,(MB_FRAME)
        and 7
        ret nz
        ld a,(attr_cell)
        push af
        call attr_row
        pop af
        inc a
        cp 24
        jr c,.a
        xor a
.a:     ld (attr_cell),a
        ret
.found: ld d,1
.fb:    rrca
        jr c,.got
        inc c
        sla d
        jr .fb
.got:   ld a,d
        cpl
        and (hl)
        ld (hl),a
        ld a,c
        jp attr_row

; refleja (HL) si está en la pantalla CPC. Conserva todo.
mirror_hl:
        push af
        ld a,(MB_SCRHI)
        xor h
        and $C0
        jr nz,.out
        push bc
        push de
        push hl
        call mirror_byte
        pop hl
        pop de
        pop bc
.out:   pop af
        ret

mirror_byte:
        ld a,h
        rrca
        rrca
        rrca
        and 7
        ld c,a
        ld a,h
        and 7
        ld h,a
        ld de,(MB_START)
        or a
        sbc hl,de
        ld a,h
        and 7
        ld h,a
        ld a,l
        rrca
        rrca
        rrca
        rrca
        and 15
        ld e,a
        ld a,h
        add a,a
        add a,a
        add a,a
        add a,a
        or e
        add a,ROWTAB&255
        ld e,a
        ld d,ROWTAB/256
        ld a,(de)
        ld b,a
        add a,a
        add a,ROWSTART&255
        ld e,a
        ld d,ROWSTART/256
        ld a,(de)
        push af
        inc de
        ld a,(de)
        ld d,a
        pop af
        ld e,a
        or a
        sbc hl,de
        ld a,h
        or a
        ret nz
        ld a,b
        add a,a
        add a,a
        add a,a
        add a,c
        sub CROP_Y
        ret c
        cp 192
        ret nc
        ld c,a
        ld a,l
        sub CROP_X
        ret c
        cp 64
        ret nc
        and $3E
        ld b,a
conv_pair:
        ld a,c
        call mark_dirty
        ld a,c
        add a,CROP_Y
        call cpc_line_addr
        ld a,b
        add a,CROP_X
        add a,l
        ld l,a
        jr nc,.nc
        inc h
.nc:    ld a,(hl)
        inc hl
        push hl
        ld l,a
        ld h,NIB/256
        ld a,(hl)
        rlca
        rlca
        rlca
        rlca
        ld e,a
        pop hl
        ld a,(hl)
        ld l,a
        ld h,NIB/256
        ld a,(hl)
        or e
        push af
        ld a,c
        call zx_line_addr
        ld a,b
        srl a
        or e
        ld e,a
        pop af
        ld (de),a
        ret

; ---------------------------------------------------------------------------
; Firmware emulado
; ---------------------------------------------------------------------------
fw_unsupported:
        or a
        ret

fw_ret: ret

fw_km_test_key:
        push de
        ld e,a
        ld a,(MB2_MATRIX+2)
        cpl
        and $A0
        ld c,a
        ld a,e
        and 7
        ld hl,bitmask
        add a,l
        ld l,a
        ld d,(hl)
        ld a,e
        rrca
        rrca
        rrca
        and 15
        ld hl,MB2_MATRIX
        add a,l
        ld l,a
        ld a,(hl)
        cpl
        and d
        pop de
        ret

h_read_char:
        push bc
        push hl
        call read_ascii
        ld hl,key_down
        cp (hl)
        jr z,.none
        ld (hl),a
        or a
        jr z,.none
        pop hl
        pop bc
        scf
        ret
.none:  pop hl
        pop bc
        or a
        ret

read_ascii:
        push de
        ld hl,MB2_MATRIX
        ld de,key_ascii
        ld c,10
.l:     ld a,(hl)
        ld b,8
.b:     rrca
        jr nc,.got
        inc de
        djnz .b
        inc hl
        dec c
        jr nz,.l
        xor a
        pop de
        ret
.got:   ld a,(de)
        pop de
        ret

fw_km_get_joystick:
        ld a,(MB2_MATRIX+9)
        cpl
        and $3F
        ld h,a
        ld a,(MB2_MATRIX+6)
        cpl
        and $3F
        ld l,a
        ld a,h
        ret

fw_txt_set_cursor:
        push af
        ld a,h
        dec a
        ld (cur_x),a
        ld a,l
        dec a
        ld (cur_y),a
        pop af
        ret

fw_txt_get_cursor:
        ld a,(cur_x)
        inc a
        ld h,a
        ld a,(cur_y)
        inc a
        ld l,a
        ret

fw_txt_set_pen:
        push af
        and 15
        ld (txt_pen),a
        pop af
        ret

fw_txt_set_paper:
        push af
        and 15
        ld (txt_paper),a
        pop af
        ret

fw_scr_set_mode:
        push af
        push bc
        push de
        push hl
        call set_mode
        xor a
        ld (cur_x),a
        ld (cur_y),a
        call clear_cpc
        pop hl
        pop de
        pop bc
        pop af
        ret

fw_mc_set_mode:
        push af
        push bc
        push de
        push hl
        call set_mode
        pop hl
        pop de
        pop bc
        pop af
        ret

fw_scr_get_mode:
        ld a,(cpc_mode)
        cp 1
        ret

fw_scr_clear:
        push af
        push bc
        push de
        push hl
        xor a
        ld (cur_x),a
        ld (cur_y),a
        call clear_cpc
        pop hl
        pop de
        pop bc
        pop af
        ret

; borra la pantalla CPC (respetando el buzón si está en ella) y la ZX
clear_cpc:
        ld a,(MB_SCRHI)
        and $C0
        ld h,a
        ld l,0
        ld b,8
.blk:   push bc
        push hl
        ld d,h
        ld e,1
        ld (hl),0
        ld bc,$07CF
        ldir
        pop hl
        ld a,h
        add a,8
        ld h,a
        pop bc
        djnz .blk
        ld hl,$4000
        ld de,$4001
        ld bc,$17FF
        ld (hl),0
        ldir
        ret

fw_scr_set_ink:
        push af
        push bc
        push de
        push hl
        push ix
        ld c,a
        ld a,b
        ld hl,fw2zx
        add a,l
        ld l,a
        ld e,(hl)
        ld a,c
        call set_pen_colour
        pop ix
        pop hl
        pop de
        pop bc
        pop af
        ret

fw_scr_set_border:
        push af
        push hl
        ld a,b
        ld hl,fw2zx
        add a,l
        ld l,a
        ld a,(hl)
        out ($FE),a
        pop hl
        pop af
        ret

fw_kl_new_frame_fly:
        ld (MB_EVFRAME),de
        ret

fw_kl_new_fast_ticker:
        ld (MB_EVFAST),de
        ret

fw_txt_output:
        push af
        push bc
        push de
        push hl
        cp 13
        jr z,.cr
        cp 10
        jr z,.lf
        cp 32
        jr c,.fin
        call draw_char
        ld a,(cur_x)
        inc a
        ld (cur_x),a
        ld b,a
        ld a,(cpc_mode)
        or a
        ld a,20
        jr z,.m
        ld a,40
.m:     cp b
        jr nz,.fin
        xor a
        ld (cur_x),a
.lf:    ld a,(cur_y)
        inc a
        cp 25
        jr c,.sy
        ld a,24
.sy:    ld (cur_y),a
        jr .fin
.cr:    xor a
        ld (cur_x),a
.fin:   pop hl
        pop de
        pop bc
        pop af
        ret

draw_char:
        sub 32
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,FONT
        add hl,de
        ld (.src+1),hl
        ld b,8
        ld c,0
.row:   push bc
        ld a,(cur_y)
        add a,a
        add a,a
        add a,a
        add a,c
        call cpc_line_addr
        ld a,(cpc_mode)
        or a
        ld a,(cur_x)
        jr z,.x0
        add a,a
        jr .x
.x0:    add a,a
        add a,a
.x:     ld e,a
        ld d,0
        add hl,de
.src:   ld de,0
        ld a,(de)
        inc de
        ld (.src+1),de
        ld c,a
        ld a,(cpc_mode)
        or a
        jr z,.m0
        ld a,c
        rrca
        rrca
        rrca
        rrca
        call enc_m1
        ld (hl),a
        call mirror_hl
        inc hl
        ld a,c
        call enc_m1
        ld (hl),a
        call mirror_hl
        jr .next
.m0:    ld b,4
.m0l:   ld a,c
        rlca
        rlca
        ld c,a
        and 3
        call enc_m0
        ld (hl),a
        call mirror_hl
        inc hl
        djnz .m0l
.next:  pop bc
        inc c
        djnz .row
        ret

enc_m1: push bc
        push hl
        and 15
        ld b,a
        rlca
        rlca
        rlca
        rlca
        or b
        ld b,a
        ld a,(txt_pen)
        call m1_mask
        ld c,a
        ld a,(txt_paper)
        call m1_mask
        ld h,a
        xor c
        and b
        xor h
        pop hl
        pop bc
        ret
m1_mask:
        and 3
        ld hl,m1_masks
        add a,l
        ld l,a
        ld a,(hl)
        ret

enc_m0: push bc
        ld b,a
        ld a,(txt_paper)
        bit 1,b
        jr z,.l
        ld a,(txt_pen)
.l:     call m0_left
        ld c,a
        ld a,(txt_paper)
        bit 0,b
        jr z,.r
        ld a,(txt_pen)
.r:     call m0_left
        srl a
        or c
        pop bc
        ret
m0_left:
        push bc
        ld c,a
        xor a
        bit 0,c
        jr z,.a
        or $80
.a:     bit 1,c
        jr z,.b
        or $08
.b:     bit 2,c
        jr z,.c
        or $20
.c:     bit 3,c
        jr z,.d
        or $02
.d:     pop bc
        ret

; ---------------------------------------------------------------------------
; Variables y tablas pequeñas (una página)
; ---------------------------------------------------------------------------
        align 256
bitmask:    db 1,2,4,8,16,32,64,128
m1_masks:   db $00,$F0,$0F,$FF
hw2zx:      ds 32, 7
fw2zx:      ds 27, 7
pen_zx:     ds 16, 0
ink_prio:   db 6,5,4,7,2,3,1,0,$FF
ga_pen:     db 0
crtc_sel:   db 0
snd_time:   db 0
cpc_mode:   db INIT_MODE
crtc_r1:    db INIT_R1
crtc_r12:   db 0
crtc_r13:   db 0
row_len:    db 80
refresh_y:  db 0
attr_cell:  dw 0
full_pending: db 0
cur_x:      db 0
cur_y:      db 0
txt_pen:    db 1
txt_paper:  db 0
key_down:   db 0
key_ascii:  ds 80, 0
zx2cpc:     ds 80, $FF
hal_code_end:
        assert hal_code_end <= $BF00, "el HAL no cabe en el banco 6"
