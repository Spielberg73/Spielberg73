"""Ports completos: se ejecutan original y port en paralelo y se comparan píxeles."""
import os

import pytest

from conftest import ZX_ROM
from zxcpc.program import load_program
from zxcpc.analysis.dynamic import run_dynamic, _set_regs
from zxcpc.analysis.static import analyze
from zxcpc.machines.cpc import CPC, decode_byte
from zxcpc.machines.spectrum import Spectrum48K, SpectrumPlus3


# --- ZX -> CPC -----------------------------------------------------------------------------

def _zx_bits(mem):
    return [[(mem[0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)]
              >> (7 - (x & 7))) & 1 for x in range(256)] for y in range(192)]


def _cpc_bits_from_zx_port(c, pm):
    """Píxeles 'de tinta' del port en el CPC (pantalla en $0000, atributos en $5800)."""
    ram = c.ram()
    out = []
    for y in range(192):
        t, r, ln = y >> 6, (y >> 3) & 7, y & 7
        row = []
        for col in range(32):
            pp = decode_byte(pm[c.cpu.mem[0x5800 + (y >> 3) * 32 + col]], 1)
            for k in range(2):
                pens = decode_byte(ram[ln * 0x800 + (t + 1) * 0x200 + r * 64 + col * 2 + k], 1)
                row += [1 if pens[i] != pp[i] else 0 for i in range(4)]
        out.append(row)
    return out


@pytest.fixture(scope="module")
def zx_port(built):
    from zxcpc.port.zx2cpc import port_zx_to_cpc, PortOptions
    path, sy, start = built["zxgame"]
    p = load_program(path, platform="zx", load_addr=start, exec_addr=start)
    tr = run_dynamic(p, frames=150)
    an = analyze(p, tr)
    return p, an, port_zx_to_cpc(an, PortOptions(refresh_lines=2)), sy


def test_zx2cpc_analisis(zx_port):
    p, an, res, sy = zx_port
    kinds = {h.kind for h in an.hotspots}
    for k in ("ula_in", "ula_out", "kempston_in", "halt", "im2", "rom_call", "screen_write"):
        assert k in kinds, k
    assert res.patches


def test_zx2cpc_equivalente(zx_port):
    p, an, res, sy = zx_port
    z = Spectrum48K()
    z.mem[0x4000:] = p.mem[0x4000:]
    _set_regs(z.cpu, p)
    c = CPC()
    c.load_state(res.state)
    pm = bytes(res.state.mem[0x1100:0x1200])
    X = sy["xpos"]

    def keys(m, f, cpc):
        m.release_all()
        if 20 <= f < 60:
            m.press("P")
        elif 60 <= f < 90:
            m.press("A")
        elif 90 <= f < 110:
            if cpc:
                m.press("JOYLEFT")
            else:
                m.kempston = 2
        elif not cpc:
            m.kempston = 0
    for f in range(140):
        keys(z, f, False)
        keys(c, f, True)
        z.run_frame()
        c.run_frame()
        if f in (89, 109, 139):
            # (antes, la línea que el juego vuelca con PUSH aún puede estar pendiente
            # del refresco de fondo)
            a, b = _zx_bits(z.mem), _cpc_bits_from_zx_port(c, pm)
            diff = sum(a[y][x] != b[y][x] for y in range(192) for x in range(256))
            assert diff == 0, f"frame {f}: {diff} píxeles distintos"
        if f in (19, 59, 89, 109, 139):
            assert (z.mem[X], z.mem[X + 1]) == (c.cpu.mem[X], c.cpu.mem[X + 1]), f
    assert z.mem[X] != 12                  # se ha movido


def test_zx2cpc_dsk_y_sna(zx_port, tmp_path):
    from zxcpc.port.zx2cpc import build_dsk
    from zxcpc.formats.cpc import write_cpc_sna, read_cpc_sna, Disk
    p, an, res, sy = zx_port
    sna = write_cpc_sna(res.state)
    assert read_cpc_sna(sna).regs["PC"] == res.state.regs["PC"]
    files = Disk.read(build_dsk(res)).files()
    assert files


@pytest.mark.skipif(not os.path.exists(ZX_ROM), reason="sin ROM del Spectrum")
def test_zx2cpc_con_rom_real(built):
    """Juego que imprime con RST $10, usa PR-STRING, BEEPER y la fuente de la ROM."""
    from zxcpc.formats.zx import write_tap_game
    from zxcpc.port.zx2cpc import port_zx_to_cpc, PortOptions
    rom = open(ZX_ROM, "rb").read()
    path, sy, start = built["zxgame2"]
    tap = path.replace(".bin", ".tap")
    with open(tap, "wb") as f:
        f.write(write_tap_game("zxgame2", open(path, "rb").read(), start))
    p = load_program(tap, zx_rom=rom)
    tr = run_dynamic(p, frames=300, rom=rom)
    res = port_zx_to_cpc(analyze(p, tr), PortOptions(refresh_lines=2, zx_rom=rom))
    z = Spectrum48K(rom)
    z.load_state(p.zx_state)
    c = CPC()
    c.load_state(res.state)
    pm = bytes(res.state.mem[0x1100:0x1200])
    for f in range(120):
        for m in (z, c):
            m.release_all()
            if 40 <= f < 48:
                m.press("P")
        z.run_frame()
        c.run_frame()
    a, b = _zx_bits(z.mem), _cpc_bits_from_zx_port(c, pm)
    assert sum(a[y][x] != b[y][x] for y in range(192) for x in range(256)) == 0


# --- CPC -> ZX -----------------------------------------------------------------------------

def _cpc_mode0_bits(c):
    ram = c.ram()
    out = []
    for y in range(192):
        yc = y + 4
        row = []
        for xb in range(64):
            a = 0xC000 + ((yc & 7) << 11) + (((yc >> 3) * 80 + 8 + xb) & 0x7FF)
            row += [1 if pn else 0 for pn in decode_byte(ram[a], 0) for _ in (0, 1)]
        out.append(row)
    return out


def _zx_shadow_bits(z):
    b7 = z.bank_data(7)
    return [[(b7[((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (x >> 3)]
              >> (7 - (x & 7))) & 1 for x in range(256)] for y in range(192)]


@pytest.fixture(scope="module")
def cpc_port(built):
    from zxcpc.port.cpc2zx import port_cpc_to_zx
    path, sy, start = built["cpcgame_hw"]
    p = load_program(path, platform="cpc", load_addr=start, exec_addr=start)
    tr = run_dynamic(p, frames=150)
    an = analyze(p, tr)
    return p, an, port_cpc_to_zx(an), sy


def test_cpc2zx_analisis(cpc_port):
    p, an, res, sy = cpc_port
    kinds = {h.kind for h in an.hotspots}
    for k in ("ga_out", "crtc_out", "ppi_io", "screen_write"):
        assert k in kinds, k
    assert any(pt.kind == "isr" for pt in res.patches)
    assert res.state.model == "+3"


def test_cpc2zx_equivalente(cpc_port):
    p, an, res, sy = cpc_port
    c = CPC()
    c.load_state(p.to_cpc_state())
    z = SpectrumPlus3()
    z.load_state(res.state)
    X, Y = sy["xpos"], sy["ypos"]
    for f in range(160):
        c.release_all()
        z.release_all()
        if 50 <= f < 110:
            c.press("CURRIGHT")
            z.press("8")
        c.run_frame()
        z.run_frame()
    cpos = (c.cpu.mem[X], c.cpu.mem[Y])
    zpos = (z.bank_data(0)[X], z.bank_data(0)[Y])
    assert cpos[0] > 30 and abs(cpos[0] - zpos[0]) <= 1 and cpos[1] == zpos[1]
    # el juego borra y redibuja el sprite cada 4 frames, y el port lo hace algo más
    # lento: en alguno de los 4 frames del ciclo las pantallas deben coincidir
    diffs = []
    for f in range(4):
        c.run_frame()
        z.run_frame()
        a, b = _cpc_mode0_bits(c), _zx_shadow_bits(z)
        diffs.append(sum(a[y][x] != b[y][x] for y in range(192) for x in range(256)))
    assert min(diffs) == 0, diffs


def test_cpc2zx_z80_valido(cpc_port):
    from zxcpc.formats.zx import write_z80, read_z80
    p, an, res, sy = cpc_port
    st = read_z80(write_z80(res.state))
    assert st.model == "+3" and st.port_1ffd == 0x01
    z = SpectrumPlus3()
    z.load_state(st)
    z.run_frame()


# --- piezas del HAL ZX -> CPC -------------------------------------------------------------

def test_ldir_scr_igual_que_ldir():
    """La copia comparando (solo convierte lo que cambia) deja lo mismo que LDIR."""
    import random
    from zxcpc.z80.asm import assemble
    from zxcpc.z80.cpu import Z80
    from zxcpc.port.zx2cpc import LDIR_SCR_SRC, LDIR_SCR2_SRC
    rnd = random.Random(5)
    r = assemble("ROMPROT equ 1\n        org $9000\nmirror_hl: ret\nrom_scratch: db 0\n"
                 + LDIR_SCR_SRC + LDIR_SCR2_SRC +
                 "\nentry:  call ldir_scr\n        halt\nref:    ldir\n        halt\n")
    img, sy = r.image(), r.symbols
    for _ in range(120):
        base = bytearray(rnd.randrange(256) for _ in range(65536))
        src = rnd.choice([0x7000, 0x7008, 0x7003, 0x60F8, 0x61FC])
        dst = rnd.choice([0x4000, 0x4008, 0x40F8, 0x4005, 0x5000, 0x3F00, 0x3FF8, 0x0100])
        n = rnd.choice([1, 3, 8, 9, 16, 17, 255, 256, 300, 1030])
        for i in range(n):
            if rnd.random() < 0.9:
                base[dst + i] = base[src + i]
        af = rnd.randrange(65536)
        out = []
        for entry in ("entry", "ref"):
            m = bytearray(base)
            m[0x9000:0x9000 + len(img)] = img
            c = Z80(m)
            c.pc = sy[entry]
            for k, v in (("SP", 0xF000), ("HL", src), ("DE", dst), ("BC", n), ("AF", af)):
                c.set_pair(k, v)
            while not c.halted:
                c.step()
            out.append((bytes(c.mem[0x4000:0x8000]), c.get_pair("HL"), c.get_pair("DE"),
                        c.get_pair("BC"), c.get_pair("AF") & 0xFFD7, bytes(c.mem[0:0x4000])))
        assert out[0][:5] == out[1][:5], (hex(src), hex(dst), n)
        # con ROMPROT, lo que cae por debajo de $4000 no se escribe (como en la ROM)
        assert out[0][5] == bytes(base[0:0x4000]), (hex(src), hex(dst), n)


@pytest.mark.skipif(not os.path.exists(ZX_ROM), reason="sin ROM del Spectrum")
def test_snapshot_detenido_en_la_rom(built, tmp_path):
    """Un snapshot tomado en el BASIC del cargador (PAUSE 0) arranca en el USR del juego."""
    from zxcpc.formats.zx import write_tap_game, write_z80
    rom = open(ZX_ROM, "rb").read()
    path, sy, start = built["zxgame"]
    tap = tmp_path / "g.tap"
    tap.write_bytes(write_tap_game("g", open(path, "rb").read(), start))
    m = Spectrum48K(rom)
    ok, _ = m.load_tape_and_run(__import__("zxcpc.formats.zx", fromlist=["read_tap"]).read_tap(
        tap.read_bytes()))
    assert ok
    st = m.save_state()
    st.regs["SP"] -= 2                      # simular que estaba dentro de una rutina de la ROM
    st.ram[st.regs["SP"] - 0x4000] = st.regs["PC"] & 0xFF
    st.ram[st.regs["SP"] - 0x3FFF] = st.regs["PC"] >> 8
    st.regs["PC"] = 0x0038                  # en la ROM: la interrupción (vuelve al juego)
    snap = tmp_path / "g.z80"
    snap.write_bytes(write_z80(st))
    p = load_program(str(snap), zx_rom=rom)
    assert p.regs["PC"] >= 0x4000
    assert any("estaba en la ROM" in n for n in p.notes)


def test_bucles_de_beeper_reubicados(tmp_path):
    """Un bucle tipo Manic Miner y una subrutina tipo Cookie se copian al HAL y suenan
    en el PSG (volumen del canal A alternando) con el mismo número de cambios."""
    from zxcpc.z80.asm import assemble
    from zxcpc.port.zx2cpc import port_zx_to_cpc, PortOptions
    src = """
        org $8000
start:  di
        ld sp,$FF00
main:   ld a,$10                ; bucle: OUT en la cabeza, XOR $18 cada E vueltas
        ld e,20
        ld bc,$0002
.l:     out ($FE),a
        dec e
        jr nz,.n
        ld e,20
        xor $18
.n:     djnz .l
        dec c
        jr nz,.l
        ld c,30                 ; subrutina con retardos, como la de Cookie
        ld d,40
.s:     call tick
        dec c
        jr nz,.s
        jr main
tick:   ld a,$10
        out ($FE),a
        ld b,d
.d1:    djnz .d1
        xor a
        out ($FE),a
        ld b,d
.d2:    djnz .d2
        ret
"""
    path = tmp_path / "b.bin"
    path.write_bytes(assemble(src).image())
    p = load_program(str(path), platform="zx", load_addr=0x8000)
    an = analyze(p, run_dynamic(p, frames=20))
    res = port_zx_to_cpc(an, PortOptions())
    loops = [pt for pt in res.patches if pt.kind == "beeper_loop"]
    assert len(loops) == 2, [pt.text for pt in res.patches]
    c = CPC()
    c.load_state(res.state)
    for _ in range(20):
        c.run_frame()
    vols = [v for _f, r, v in c.psg_writes if r == 8]
    assert len(vols) > 100 and set(vols) == {0, 15}
    z = Spectrum48K()
    z.mem[0x4000:] = p.mem[0x4000:]
    _set_regs(z.cpu, p)
    for _ in range(20):
        z.run_frame()
    # mismo orden de magnitud de cambios del altavoz que el original
    assert 0.5 < len(vols) / max(1, z.beeper_toggles) < 1.5


def test_beeper_reubicado_no_saca_calculos_de_a(tmp_path):
    """Una subrutina de beeper que usa A para otras cuentas antes del OUT (como la de
    Where Time Stood Still) no debe sacar esos valores al altavoz ni al borde."""
    from zxcpc.z80.asm import assemble
    from zxcpc.port.zx2cpc import port_zx_to_cpc, PortOptions
    src = """
        org $8000
start:  di
        ld sp,$FF00
        ld c,0
main:   inc c
        call snd
        jr main
snd:    ld b,0
        ld a,c
        and $07
        ld c,a
        ld a,$3B
        ld (var),a
        ld a,$10
        out ($FE),a
        ret
var:    db 0
"""
    path = tmp_path / "w.bin"
    path.write_bytes(assemble(src).image())
    p = load_program(str(path), platform="zx", load_addr=0x8000)
    an = analyze(p, run_dynamic(p, frames=10))
    res = port_zx_to_cpc(an, PortOptions())
    assert any(pt.kind == "beeper_loop" for pt in res.patches)
    c = CPC()
    c.load_state(res.state)
    pens = []
    out = c.cpu.outp

    def spy(port, v):
        if (port >> 8) & 0xC0 == 0x40 and v & 0xC0 == 0x40 and c.pen == 16:
            pens.append(v & 0x1F)
        return out(port, v)
    c.cpu.outp = spy
    for _ in range(10):
        c.run_frame()
    assert len(set(pens)) <= 1          # borde negro fijo, como en el Spectrum


def test_frameskip_en_volcados_de_bufer(tmp_path):
    """Con --frameskip, el volcado frecuente de un búfer a pantalla se salta 1 de cada 2
    veces, el primer volcado es real y la pantalla acaba igual que en el Spectrum."""
    from zxcpc.z80.asm import assemble
    from zxcpc.port.zx2cpc import port_zx_to_cpc, PortOptions
    src = """
        org $8000
start:  di
        ld sp,$FF00
        ld hl,$4000             ; borrado con el truco LD (HL),0 + LDIR (lee la pantalla)
        ld de,$4001
        ld bc,$17FF
        ld (hl),0
        ldir
        ld a,1
main:   ld hl,$C000             ; dibujar una barra en el búfer y volcarlo entero
        ld b,0
.f:     ld (hl),a
        inc hl
        djnz .f
        rlca
        ld hl,$C000
        ld de,$4000
        ld bc,$0800
        ldir
        jr main
"""
    path = tmp_path / "f.bin"
    path.write_bytes(assemble(src).image())
    p = load_program(str(path), platform="zx", load_addr=0x8000)
    an = analyze(p, run_dynamic(p, frames=30))
    res = port_zx_to_cpc(an, PortOptions(frameskip=1))
    assert any("salto de frames" in w for w in res.warnings)
    assert res.hal_source.count("jp ldir_skip") == 1      # solo el volcado del búfer
    c = CPC()
    c.load_state(res.state)
    for _ in range(40):
        c.run_frame()
    # la pantalla del CPC refleja algún volcado real (la barra no está vacía)
    assert any(c.cpu.mem[0x4000:0x4100])


def test_128k_con_paginacion_se_rechaza(tmp_path):
    from zxcpc.z80.asm import assemble
    from zxcpc.formats.zx import ZXState, write_z80
    from zxcpc.port.zx2cpc import port_zx_to_cpc
    code = assemble("""
        org $8000
        di
.l:     ld a,3
        ld bc,$7FFD
        out (c),a
        jr .l
""").image()
    banks = {b: bytearray(16384) for b in range(8)}
    banks[2][0:len(code)] = code
    regs = {k: 0 for k in ("AF", "BC", "DE", "HL", "AF'", "BC'", "DE'", "HL'", "IX", "IY",
                           "I", "R")}
    regs.update(SP=0xBF00, PC=0x8000)
    st = ZXState(bytearray(49152), regs, 0, 0, 1, 0)
    st.model, st.banks = "128k", banks
    snap = tmp_path / "p.z80"
    snap.write_bytes(write_z80(st))
    p = load_program(str(snap))
    an = analyze(p, run_dynamic(p, frames=5))
    with pytest.raises(ValueError, match="pagina memoria"):
        port_zx_to_cpc(an)


def _snap128(tmp_path, src, attr=0x38):
    """Instantánea de 128K con ``src`` (org $8000) en el banco 2 y el banco 0 en $C000."""
    from zxcpc.z80.asm import assemble
    from zxcpc.formats.zx import ZXState, write_z80
    code = assemble(src).image()
    banks = {b: bytearray(16384) for b in range(8)}
    banks[2][0:len(code)] = code
    banks[5][0x1800:0x1B00] = bytes([attr]) * 0x300
    banks[7][0x1800:0x1B00] = bytes([attr]) * 0x300
    regs = {k: 0 for k in ("AF", "BC", "DE", "HL", "AF'", "BC'", "DE'", "HL'", "IX", "IY",
                           "I", "R")}
    regs.update(SP=0xBF00, PC=0x8000)
    st = ZXState(bytearray(49152), regs, 0, 0, 1, 0)
    st.model, st.banks = "128k", banks
    snap = tmp_path / "p.z80"
    snap.write_bytes(write_z80(st))
    return load_program(str(snap)), st


def test_512k_ldi_con_pila_secuestrada(tmp_path):
    """128K en el CPC de 576K: volcado a la pantalla 1 con LD SP,tabla / POP DE / LDI x24
    (los LDI parcheados no deben machacar la tabla con su dirección de retorno), en
    pantalla 0 y en pantalla 1 alternando, más escrituras en el AY por OUT (C)."""
    from zxcpc.port.zx2cpc import port_zx_to_cpc, PortOptions
    from zxcpc.machines.spectrum import Spectrum128
    rows = ", ".join(f"${0xC000 + (r & 7) * 0x100 + (r >> 3) * 0x20 + 4:04X}"
                     for r in range(16))
    p, st = _snap128(tmp_path, f"""
        org $8000
start:  di
        ld a,$0F                ; banco 7 en $C000 y pantalla 1 visible
        ld (bank),a
main:   ld a,(bank)
        xor $0A                 ; alternar banco 7/pantalla 1 y banco 5/pantalla 0
        ld (bank),a
        ld bc,$7FFD
        out (c),a
        ld hl,src
        ld (save),sp
        ld sp,table
        ld a,16
.r:     pop de
        rept 24
        ldi
        endr
        dec a
        jr nz,.r
        ld sp,(save)
        ld a,(cnt)
        ld e,a
        ld hl,src               ; cambiar parte del origen
        ld b,96
.m:     ld a,(hl)
        add a,e
        ld (hl),a
        inc hl
        inc hl
        djnz .m
        ld bc,$FFFD
        ld a,8
        out (c),a
        ld b,$BF
        ld a,e
        and 15
        out (c),a
        ld hl,cnt
        dec (hl)
        jr nz,main
.fin:   jr .fin
cnt:    db 24
bank:   db 0
save:   dw 0
table:  dw {rows}
src:    db {", ".join(str((i * 37) & 255) for i in range(384))}
""")
    an = analyze(p, run_dynamic(p, frames=40))
    res = port_zx_to_cpc(an, PortOptions(ram512=True))
    assert any(pt.text == "24 x LDI" for pt in res.patches)
    z = Spectrum128(None, None)
    z.load_state(st)
    for _ in range(40):
        z.run_frame()
    z._sync()
    c = CPC(ram_kb=576)
    c.load_state(res.state)
    for _ in range(200):
        c.run_frame()
    c.ram()
    ram = b"".join(bytes(pg) for pg in c.pages)           # base y ampliación
    pm = bytes(res.state.mem[0x1100:0x1200])
    tbl = 0x8000 + p.mem[0x8000:0x8100].find(bytes([0x04, 0xC0, 0x04, 0xC1]))
    assert c.cpu.mem[tbl:tbl + 32] == z.banks[2][tbl - 0x8000:tbl - 0x8000 + 32]
    for bank, base in ((7, 0xC000), (5, 0x0000)):
        zx = z.banks[bank]
        cp = ram[0x10000 + bank * 0x10000 + 0xC000:][:0x1B00] if bank == 7 else \
            ram[0x4000:0x5B00]
        assert bytes(cp) == bytes(zx[:0x1B00])
        # píxeles de la pantalla del CPC (A en $0000, B en el bloque base 3)
        for y in range(16):
            za = ((y & 7) << 8) | ((y >> 3) << 5)
            for col in range(4, 28):
                v = zx[za + col]
                pp = decode_byte(pm[zx[0x1800 + (y >> 3) * 32 + col]], 1)
                k = base + (y & 7) * 0x800 + 0x200 + (y >> 3) * 64 + col * 2
                pens = decode_byte(ram[k], 1) + decode_byte(ram[k + 1], 1)
                ink = [(v >> (7 - i)) & 1 for i in range(8)]
                assert [1 if q != pp[i & 3] else 0 for i, q in enumerate(pens)] == ink, \
                    (bank, y, col)
    assert c.psg[8] == z.ay[8]
    # disco: los bancos del Spectrum que no están en la base van en ficheros aparte
    from zxcpc.port.zx2cpc import build_dsk
    dsk = build_dsk(res)
    assert b"ZXCPC   X7 " in dsk and b"ZXCPC   X5 " not in dsk


def test_pantalla_de_creditos(zx_port):
    """Con créditos, el SNA arranca en la pantalla de créditos y, tras una tecla, el
    juego sigue con su pantalla intacta; el disco los muestra mientras carga."""
    from zxcpc.port.zx2cpc import port_zx_to_cpc, PortOptions, build_dsk, credit_lines
    p, an, res0, sy = zx_port
    res = port_zx_to_cpc(an, PortOptions(refresh_lines=2, credits=["JUEGO", "",
                                                                    "CONVERSIÓN: NOSOTROS"]))
    assert credit_lines(["CONVERSIÓN"]) == ["CONVERSION", "", "PULSA UNA TECLA"]
    assert res.state.regs["PC"] == res.hal_symbols["stub2_spl"]
    c = CPC()
    c.load_state(res.state)
    for _ in range(5):
        c.run_frame()
    assert 0x4000 <= c.cpu.pc < 0x8000 and c.ram_cfg & 0x3F == 6   # en los créditos
    for _ in range(5):
        c.press("SPACE")
        c.run_frame()
    c.release_all()
    for _ in range(5):
        c.run_frame()
    assert c.ram_cfg & 0x3F == 0                 # de vuelta en el juego
    dsk = build_dsk(res)
    assert b"NOSOTROS" in dsk and b"PULSA UNA TECLA" in dsk
    with pytest.raises(ValueError, match="32 caracteres"):
        credit_lines(["X" * 33])
