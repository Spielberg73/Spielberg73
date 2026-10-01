"""Formatos de fichero del Spectrum y del CPC."""
import random

from zxcpc.formats import zx as fzx
from zxcpc.formats import cpc as fcpc
from zxcpc.formats.png import write_png, read_png_rgb

REGS = {"AF": 0x1234, "BC": 0x2345, "DE": 0x3456, "HL": 0x4567, "AF'": 0x5678, "BC'": 0x6789,
        "DE'": 0x789A, "HL'": 0x89AB, "IX": 0x9ABC, "IY": 0xABCD, "SP": 0xFF00, "PC": 0x8000,
        "I": 0x3F, "R": 0x12}


def _ram(seed=1, size=49152):
    rnd = random.Random(seed)
    ram = bytearray(size)
    for a in range(0, size, 7):
        ram[a] = rnd.randrange(256)
    ram[1000:3000] = bytes(2000)            # tramo comprimible
    return ram


def test_z80_ida_y_vuelta():
    st = fzx.ZXState(_ram(), dict(REGS), 1, 1, 2, 3)
    back = fzx.read_z80(fzx.write_z80(st))
    assert back.ram == st.ram
    for k in ("AF", "BC", "HL", "IX", "SP", "PC", "HL'"):
        assert back.regs[k] == REGS[k], k
    assert (back.iff1, back.im, back.border) == (1, 2, 3)


def test_z80_plus3_ida_y_vuelta():
    st = fzx.ZXState(bytearray(49152), dict(REGS), 0, 0, 1, 0)
    st.model = "+3"
    st.banks = {b: bytes([b]) * 16384 for b in range(8)}
    st.port_7ffd, st.port_1ffd = 0x18, 0x01
    back = fzx.read_z80(fzx.write_z80(st))
    assert back.model == "+3"
    assert back.port_1ffd == 0x01 and back.port_7ffd == 0x18
    assert all(back.banks[b] == st.banks[b] for b in range(8))


def test_sna_ida_y_vuelta():
    st = fzx.ZXState(_ram(2), dict(REGS), 1, 1, 1, 5)
    back = fzx.read_sna(fzx.write_sna(st))
    sp = REGS["SP"] - 0x4000                # el SNA guarda el PC en la pila
    assert back.ram[:sp - 2] == st.ram[:sp - 2] and back.ram[sp:] == st.ram[sp:]
    assert back.regs["PC"] == 0x8000 and back.regs["SP"] == REGS["SP"]
    assert back.border == 5


def test_tap_y_cargador_basic():
    code = bytes(range(200))
    tap = fzx.write_tap_game("prueba", code, 0x8000)
    blocks = fzx.read_tap(tap)
    assert len(blocks) == 4 and all(b.checksum_ok for b in blocks)
    h = blocks[2].header()
    assert h["type"] == 3 and h["length"] == 200 and h["param1"] == 0x8000
    assert blocks[3].data == code
    lines = fzx.detokenize_zx_basic(blocks[1].data)
    text = lines[0][1]
    assert "CLEAR" in text and "USR" in text and "32768" in text
    ram, entry, log = fzx.load_tape_code(blocks)
    assert entry == 0x8000
    assert ram[0x4000:0x4000 + 200] == code


def test_cpc_sna_ida_y_vuelta():
    st = fcpc.CPCState(_ram(3, 65536), dict(REGS), 1, 1, 1)
    st.palette = [i for i in range(17)]
    st.ga_rmr = 0x8C & 0x1F
    st.crtc[1] = 32
    st.psg[7] = 0x3F
    back = fcpc.read_cpc_sna(fcpc.write_cpc_sna(st))
    assert bytes(back.mem[:65536]) == bytes(st.mem)
    assert back.regs["PC"] == 0x8000
    assert back.palette[:17] == st.palette
    assert back.crtc[1] == 32 and back.psg[7] == 0x3F
    assert back.mode == st.mode


def test_amsdos_y_dsk():
    content = bytes(range(256)) * 20
    hdr = fcpc.make_amsdos_header("JUEGO", "BIN", len(content), 0x4000, 0x4010)
    info = fcpc.parse_amsdos_header(hdr + content)
    assert info["load"] == 0x4000 and info["exec"] == 0x4010 and info["length"] == len(content)
    dsk = fcpc.make_dsk([("JUEGO", "BIN", hdr + content), ("OTRO", "", b"hola" * 100)])
    files = fcpc.Disk.read(dsk).files()
    assert files["JUEGO.BIN"][128:128 + len(content)] == content
    assert files["OTRO"][:400] == b"hola" * 100


def test_png(tmp_path):
    rows = [b"".join(bytes([x * 10, y * 20, 7]) for x in range(5)) for y in range(4)]
    p = write_png(str(tmp_path / "t.png"), 5, 4, rows)
    w, h, back = read_png_rgb(p)
    assert (w, h) == (5, 4)
    assert [bytes(r) for r in back] == rows


def test_z80_128k_ida_y_vuelta():
    st = fzx.ZXState(bytearray(49152), dict(REGS), 0, 0, 1, 0)
    st.model = "128k"
    st.banks = {b: bytes([b + 1]) * 16384 for b in range(8)}
    st.port_7ffd = 0x13
    back = fzx.read_z80(fzx.write_z80(st))
    assert back.model == "128k" and back.port_7ffd == 0x13
    assert all(back.banks[b] == st.banks[b] for b in range(8))
