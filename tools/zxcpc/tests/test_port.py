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
    from zxcpc.port.zx2cpc import LDIR_SCR_SRC
    rnd = random.Random(5)
    r = assemble("        org $9000\nmirror_hl: ret\n" + LDIR_SCR_SRC +
                 "\nentry:  call ldir_scr\n        halt\nref:    ldir\n        halt\n")
    img, sy = r.image(), r.symbols
    for _ in range(120):
        base = bytearray(rnd.randrange(256) for _ in range(65536))
        src = rnd.choice([0x7000, 0x7008, 0x7003, 0x60F8, 0x61FC])
        dst = rnd.choice([0x4000, 0x4008, 0x40F8, 0x4005, 0x5000])
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
                        c.get_pair("BC"), c.get_pair("AF") & 0xFFD7))
        assert out[0] == out[1], (hex(src), hex(dst), n)


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
