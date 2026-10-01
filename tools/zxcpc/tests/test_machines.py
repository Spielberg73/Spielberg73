"""Máquinas emuladas: Spectrum 48K, Spectrum +3 y CPC."""
from zxcpc.z80.asm import assemble
from zxcpc.machines.spectrum import Spectrum48K, SpectrumPlus3
from zxcpc.machines.cpc import CPC


def _load(m, src, org):
    r = assemble(f"        org {org}\n" + src)
    img = r.image()
    m.cpu.mem[org:org + len(img)] = img
    m.cpu.pc = org
    m.cpu.set_pair("SP", 0x7F00 if org < 0x7000 else 0xF000)
    return r.symbols, img


def test_spectrum_teclado_y_pantalla():
    m = Spectrum48K()
    _load(m, """
        di
.l:     ld a,$DF                ; semifila Y-P
        in a,($FE)
        ld ($4000),a
        jr .l
""", 0x8000)
    m.press("P")
    m.run_frame()
    assert m.mem[0x4000] & 1 == 0          # P pulsada (bit 0 a cero)
    m.release_all()
    m.run_frame()
    assert m.mem[0x4000] & 1 == 1


def test_spectrum_interrupcion_por_frame():
    m = Spectrum48K()
    sy, _ = _load(m, """
        ld a,$C3
        ld ($FEFE),a
        ld hl,isr
        ld ($FEFF),hl
        ld a,$FE
        ld i,a
        im 2
        ei
.l:     jr .l
isr:    ld hl,cnt
        inc (hl)
        ei
        reti
cnt:    db 0
""", 0x8000)
    for _ in range(10):
        m.run_frame()
    assert m.mem[sy["cnt"]] in (9, 10)


def test_plus3_paginacion_especial():
    m = SpectrumPlus3()
    sy, img = _load(m, """
        di
        ld bc,$1FFD
        ld a,$01                ; bancos 0,1,2,3
        out (c),a
        ld a,$AA
        ld ($0100),a            ; RAM en $0000
        ld a,$07                ; bancos 4,7,6,3
        out (c),a
        ld a,$55
        ld ($0100),a
        ld a,$01
        out (c),a
        halt
""", 0xC000)
    m.banks[3][:len(img)] = img             # $C000 es el banco 3 en las dos configuraciones
    for _ in range(3):
        m.run_frame()
    assert m.bank_data(0)[0x100] == 0xAA
    assert m.bank_data(4)[0x100] == 0x55
    assert not m.traps                      # sin ROM mapeada no hay trampas HLE


def test_cpc_teclado_por_ppi():
    m = CPC()
    _load(m, """
        di
.l:     ld bc,$F40E
        out (c),c
        ld bc,$F6C0
        out (c),c
        ld bc,$F600
        out (c),c
        ld bc,$F792
        out (c),c
        ld bc,$F648             ; línea 8
        out (c),c
        ld b,$F4
        in a,(c)
        ld ($5000),a
        ld bc,$F782
        out (c),c
        jr .l
""", 0x4000)
    m.press("Q")
    m.run_frame()
    assert m.cpu.mem[0x5000] & 0x08 == 0   # Q: línea 8, bit 3
    m.release_all()
    m.run_frame()
    assert m.cpu.mem[0x5000] & 0x08


def test_cpc_modo_y_paleta():
    m = CPC()
    _load(m, """
        di
        ld bc,$7F8C             ; modo 0
        out (c),c
        ld bc,$7F01
        out (c),c
        ld a,$4A                ; pluma 1 = amarillo brillante
        out (c),a
        halt
""", 0x4000)
    m.run_frame()
    assert m.rmr & 3 == 0
    assert m.palette[1] == 0x0A


def test_spectrum128_paginacion_y_roms():
    from zxcpc.machines.spectrum import Spectrum128
    rom0, rom1 = bytes([0xAA]) * 16384, bytes([0x55]) * 16384
    m = Spectrum128(rom0, rom1)
    sy, img = _load(m, """
        di
        ld bc,$7FFD
        ld a,$13                ; banco 3 en $C000 y ROM 1
        out (c),a
        ld a,($0000)
        ld ($8000),a
        ld a,$77
        ld ($C000),a
        ld a,$04                ; banco 4 y ROM 0
        out (c),a
        ld a,($0000)
        ld ($8001),a
        halt
""", 0x6000)
    m.run_frame()
    assert m.mem[0x8000] == 0x55 and m.mem[0x8001] == 0xAA
    assert m.bank_data(3)[0] == 0x77 and m.bank_data(4)[0] == 0
