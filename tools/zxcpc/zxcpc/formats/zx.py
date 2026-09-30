"""Formatos del ZX Spectrum: TAP, TZX, snapshots .Z80 y .SNA, BASIC."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field


class FormatError(Exception):
    pass


# ---------------------------------------------------------------------------
# Estado de máquina (común a snapshots)
# ---------------------------------------------------------------------------

@dataclass
class ZXState:
    """Estado completo de un Spectrum 48K/128K."""
    ram: bytearray                         # 48K (0x4000-0xFFFF) para 48K
    regs: dict                             # AF BC DE HL AF' BC' DE' HL' IX IY SP PC I R
    iff1: int = 0
    iff2: int = 0
    im: int = 1
    border: int = 7
    model: str = "48k"                     # "48k" o "128k"
    banks: dict = field(default_factory=dict)   # 128K: nº banco -> 16K
    port_7ffd: int = 0
    port_1ffd: int = 0
    ay_regs: list = field(default_factory=lambda: [0] * 16)
    ay_select: int = 0

    def memory64k(self, rom: bytes | None = None) -> bytearray:
        """Mapa de 64K tal y como lo ve la CPU (ROM en 0x0000 si se da)."""
        mem = bytearray(65536)
        if rom:
            mem[0:len(rom[:16384])] = rom[:16384]
        if self.model == "48k":
            mem[0x4000:0x10000] = self.ram
        else:
            mem[0x4000:0x8000] = self.banks[5]
            mem[0x8000:0xC000] = self.banks[2]
            mem[0xC000:0x10000] = self.banks[self.port_7ffd & 7]
        return mem


def _default_regs():
    return {k: 0 for k in ("AF", "BC", "DE", "HL", "AF'", "BC'", "DE'", "HL'",
                           "IX", "IY", "SP", "PC", "I", "R")}


# ---------------------------------------------------------------------------
# TAP
# ---------------------------------------------------------------------------

@dataclass
class TapeBlock:
    flag: int
    data: bytes             # sin flag ni checksum
    checksum_ok: bool = True
    source: str = "std"     # std / turbo / pure

    @property
    def is_header(self):
        return self.flag == 0 and len(self.data) == 17

    def header(self):
        if not self.is_header:
            return None
        typ, name, length, p1, p2 = struct.unpack("<B10sHHH", self.data)
        return {"type": typ, "name": name.decode("latin-1").rstrip(), "length": length,
                "param1": p1, "param2": p2}


def _checksum(flag, data):
    c = flag
    for b in data:
        c ^= b
    return c


def read_tap(buf: bytes):
    blocks, i = [], 0
    while i + 2 <= len(buf):
        n = struct.unpack_from("<H", buf, i)[0]
        i += 2
        raw = buf[i:i + n]
        i += n
        if len(raw) < 2:
            continue
        flag, data, chk = raw[0], raw[1:-1], raw[-1]
        blocks.append(TapeBlock(flag, bytes(data), _checksum(flag, data) == chk))
    return blocks


def tap_block(flag, data) -> bytes:
    raw = bytes([flag]) + bytes(data) + bytes([_checksum(flag, data)])
    return struct.pack("<H", len(raw)) + raw


def tap_header(typ, name, length, p1, p2) -> bytes:
    nm = name.encode("latin-1")[:10].ljust(10, b" ")
    return tap_block(0, struct.pack("<B10sHHH", typ, nm, length, p1, p2))


def write_tap_code(name, data, start) -> bytes:
    return tap_header(3, name, len(data), start, 32768) + tap_block(0xFF, data)


def _zx_int(n):
    """Número en BASIC: dígitos + marcador $0E + entero de 5 bytes."""
    return str(n).encode() + bytes([0x0E, 0, 0, n & 0xFF, (n >> 8) & 0xFF, 0])


def basic_loader(clear, usr, line=10) -> bytes:
    """10 CLEAR n: LOAD "" CODE: RANDOMIZE USR m (tokenizado)."""
    body = bytes([0xFD]) + _zx_int(clear) + b":" + bytes([0xEF]) + b'""' + bytes([0xAF]) + \
        b":" + bytes([0xF9, 0xC0]) + _zx_int(usr) + b"\r"
    return bytes([line >> 8, line & 0xFF]) + struct.pack("<H", len(body)) + body


def write_tap_game(name, data, start, entry=None, clear=None) -> bytes:
    """TAP con cargador BASIC + bloque CODE que arranca en ``entry``."""
    prog = basic_loader(clear if clear is not None else max(0x5FFF, start - 1),
                        entry if entry is not None else start)
    return tap_header(0, name, len(prog), 10, len(prog)) + tap_block(0xFF, prog) + \
        write_tap_code(name, data, start)


# ---------------------------------------------------------------------------
# TZX / CDT (mismo contenedor)
# ---------------------------------------------------------------------------

TZX_MAGIC = b"ZXTape!\x1a"


@dataclass
class TzxBlock:
    id: int
    data: bytes = b""              # carga útil (bloques de datos)
    params: dict = field(default_factory=dict)


def read_tzx(buf: bytes):
    if not buf.startswith(TZX_MAGIC):
        raise FormatError("no es un fichero TZX/CDT")
    i = 10
    out = []

    def u8():
        nonlocal i
        v = buf[i]
        i += 1
        return v

    def u16():
        nonlocal i
        v = struct.unpack_from("<H", buf, i)[0]
        i += 2
        return v

    def u24():
        nonlocal i
        v = buf[i] | buf[i + 1] << 8 | buf[i + 2] << 16
        i += 3
        return v

    def u32():
        nonlocal i
        v = struct.unpack_from("<I", buf, i)[0]
        i += 4
        return v

    while i < len(buf):
        bid = u8()
        if bid == 0x10:
            pause, n = u16(), u16()
            out.append(TzxBlock(bid, buf[i:i + n], {"pause": pause}))
            i += n
        elif bid == 0x11:
            p = {}
            for k in ("pilot", "sync1", "sync2", "zero", "one", "pilot_len"):
                p[k] = u16()
            p["used_bits"] = u8()
            p["pause"] = u16()
            n = u24()
            out.append(TzxBlock(bid, buf[i:i + n], p))
            i += n
        elif bid == 0x12:
            i += 4
            out.append(TzxBlock(bid))
        elif bid == 0x13:
            n = u8()
            i += 2 * n
            out.append(TzxBlock(bid))
        elif bid == 0x14:
            p = {"zero": u16(), "one": u16(), "used_bits": u8(), "pause": u16()}
            n = u24()
            out.append(TzxBlock(bid, buf[i:i + n], p))
            i += n
        elif bid == 0x15:
            i += 5
            n = u24()
            i += n
            out.append(TzxBlock(bid))
        elif bid in (0x18, 0x19):
            n = u32()
            i += n
            out.append(TzxBlock(bid))
        elif bid == 0x20:
            out.append(TzxBlock(bid, params={"pause": u16()}))
        elif bid == 0x21:
            n = u8()
            out.append(TzxBlock(bid, params={"name": buf[i:i + n].decode("latin-1")}))
            i += n
        elif bid in (0x22, 0x25, 0x27):
            out.append(TzxBlock(bid))
        elif bid in (0x23, 0x24):
            i += 2
            out.append(TzxBlock(bid))
        elif bid == 0x26:
            n = u16()
            i += 2 * n
            out.append(TzxBlock(bid))
        elif bid == 0x28:
            n = u16()
            i += n
            out.append(TzxBlock(bid))
        elif bid == 0x2A:
            i += 4
            out.append(TzxBlock(bid))
        elif bid == 0x2B:
            i += 5
            out.append(TzxBlock(bid))
        elif bid == 0x30:
            n = u8()
            out.append(TzxBlock(bid, params={"text": buf[i:i + n].decode("latin-1")}))
            i += n
        elif bid == 0x31:
            i += 1
            n = u8()
            out.append(TzxBlock(bid, params={"text": buf[i:i + n].decode("latin-1")}))
            i += n
        elif bid == 0x32:
            n = u16()
            info = {}
            j, cnt = i + 1, buf[i]
            for _ in range(cnt):
                tid, ln = buf[j], buf[j + 1]
                info[tid] = buf[j + 2:j + 2 + ln].decode("latin-1", "replace")
                j += 2 + ln
            out.append(TzxBlock(bid, params={"info": info}))
            i += n
        elif bid == 0x33:
            n = u8()
            i += 3 * n
            out.append(TzxBlock(bid))
        elif bid == 0x35:
            i += 16
            n = u32()
            i += n
            out.append(TzxBlock(bid))
        elif bid == 0x5A:
            i += 9
            out.append(TzxBlock(bid))
        else:
            # Bloques desconocidos de la v1.10+: longitud de 32 bits tras el ID
            n = u32()
            i += n
            out.append(TzxBlock(bid))
    return out


def tzx_data_blocks(blocks):
    """Convierte bloques de datos de un TZX de Spectrum en TapeBlocks."""
    out = []
    for b in blocks:
        if b.id in (0x10, 0x11, 0x14) and len(b.data) >= 2:
            flag, data, chk = b.data[0], b.data[1:-1], b.data[-1]
            src = {0x10: "std", 0x11: "turbo", 0x14: "pure"}[b.id]
            out.append(TapeBlock(flag, bytes(data), _checksum(flag, data) == chk, src))
    return out


# ---------------------------------------------------------------------------
# Snapshots .Z80
# ---------------------------------------------------------------------------

def _z80_decompress(data, end_marker=False):
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        if end_marker and data[i:i + 4] == b"\x00\xed\xed\x00":
            break
        if i + 3 < n + 1 and data[i] == 0xED and i + 1 < n and data[i + 1] == 0xED:
            cnt, val = data[i + 2], data[i + 3]
            out += bytes([val]) * cnt
            i += 4
        else:
            out.append(data[i])
            i += 1
    return out


def _z80_compress(data):
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        b = data[i]
        j = i
        while j < n and data[j] == b and j - i < 255:
            j += 1
        run = j - i
        if (run >= 5) or (b == 0xED and run >= 2):
            out += bytes([0xED, 0xED, run, b])
            i = j
        else:
            out.append(b)
            # un ED aislado seguido de otro byte no debe comprimirse con él
            if b == 0xED and i + 1 < n:
                out.append(data[i + 1])
                i += 2
            else:
                i += 1
    return out


def read_z80(buf: bytes) -> ZXState:
    if len(buf) < 30:
        raise FormatError("snapshot .z80 demasiado corto")
    h = buf[:30]
    a, f = h[0], h[1]
    bc, hl, pc, sp = struct.unpack_from("<HHHH", h, 2)
    i_reg, r = h[10], h[11]
    b12 = h[12] if h[12] != 0xFF else 1
    r = (r & 0x7F) | ((b12 & 1) << 7)
    border = (b12 >> 1) & 7
    compressed = bool(b12 & 0x20)
    de, bc2, de2, hl2 = struct.unpack_from("<HHHH", h, 13)
    a2, f2 = h[21], h[22]
    iy, ix = struct.unpack_from("<HH", h, 23)
    iff1, iff2, b29 = h[27], h[28], h[29]
    regs = {"AF": a << 8 | f, "BC": bc, "DE": de, "HL": hl, "AF'": a2 << 8 | f2, "BC'": bc2,
            "DE'": de2, "HL'": hl2, "IX": ix, "IY": iy, "SP": sp, "PC": pc, "I": i_reg, "R": r}
    st = ZXState(bytearray(49152), regs, 1 if iff1 else 0, 1 if iff2 else 0, b29 & 3, border)
    if pc != 0:
        data = buf[30:]
        mem = _z80_decompress(data, True) if compressed else bytearray(data[:49152])
        if len(mem) < 49152:
            raise FormatError("datos de memoria incompletos en .z80 v1")
        st.ram[:] = mem[:49152]
        return st
    ext_len = struct.unpack_from("<H", buf, 30)[0]
    ext = buf[32:32 + ext_len]
    regs["PC"] = struct.unpack_from("<H", ext, 0)[0]
    hw = ext[2]
    version = 2 if ext_len == 23 else 3
    is128 = (hw in (3, 4) if version == 2 else hw in (4, 5, 6)) or hw in (7, 9, 12, 13)
    if hw in (7, 8, 9, 10, 11, 12, 13, 14):
        # +3, Pentagon, Scorpion... se tratan como 128K
        is128 = hw not in (8, 10, 11, 14) or is128
    st.port_7ffd = ext[3]
    if ext_len >= 55:
        st.port_1ffd = ext[54]
    if hw in (7, 8, 12, 13):
        st.model = "+3"
    st.ay_select = ext[6]
    st.ay_regs = list(ext[7:23])
    i = 32 + ext_len
    pages = {}
    while i + 3 <= len(buf):
        ln, page = struct.unpack_from("<HB", buf, i)
        i += 3
        if ln == 0xFFFF:
            raw = buf[i:i + 16384]
            i += 16384
        else:
            raw = _z80_decompress(buf[i:i + ln])
            i += ln
        pages[page] = bytes(raw[:16384]).ljust(16384, b"\0")
    if is128 or st.model == "+3":
        st.model = st.model if st.model == "+3" else "128k"
        st.banks = {p - 3: bytearray(v) for p, v in pages.items() if 3 <= p <= 10}
        for b in range(8):
            st.banks.setdefault(b, bytearray(16384))
        st.ram[:] = st.banks[5] + st.banks[2] + st.banks[st.port_7ffd & 7]
    else:
        for page, addr in ((8, 0x4000), (4, 0x8000), (5, 0xC000)):
            if page in pages:
                st.ram[addr - 0x4000:addr] = pages[page]
    return st


def write_z80(st: ZXState) -> bytes:
    """Escribe un snapshot .Z80 v3 (48K, o +2A/+3 si ``st.model == '+3'``)."""
    r = st.regs
    h = bytearray(30)
    h[0], h[1] = r["AF"] >> 8, r["AF"] & 0xFF
    struct.pack_into("<HHHH", h, 2, r["BC"], r["HL"], 0, r["SP"])
    h[10] = r["I"]
    h[11] = r["R"] & 0x7F
    h[12] = ((r["R"] >> 7) & 1) | ((st.border & 7) << 1)
    struct.pack_into("<HHHH", h, 13, r["DE"], r["BC'"], r["DE'"], r["HL'"])
    h[21], h[22] = r["AF'"] >> 8, r["AF'"] & 0xFF
    struct.pack_into("<HH", h, 23, r["IY"], r["IX"])
    h[27], h[28] = st.iff1, st.iff2
    h[29] = st.im & 3
    plus3 = st.model == "+3"
    ext = bytearray(55 if plus3 else 54)
    struct.pack_into("<H", ext, 0, r["PC"])
    ext[2] = 7 if plus3 else 0      # 7 = +3 (en .z80 v3)
    if plus3:
        ext[3] = st.port_7ffd
        ext[54] = st.port_1ffd
    ext[6] = st.ay_select
    ext[7:23] = bytes(st.ay_regs[:16])
    out = bytearray(h) + struct.pack("<H", len(ext)) + ext
    if plus3:
        pages = [(b + 3, bytes(st.banks[b])) for b in range(8)]
    else:
        pages = [(page, bytes(st.ram[addr - 0x4000:addr - 0x4000 + 16384]))
                 for page, addr in ((8, 0x4000), (4, 0x8000), (5, 0xC000))]
    for page, raw in pages:
        comp = _z80_compress(raw)
        if len(comp) >= 16384:
            out += struct.pack("<HB", 0xFFFF, page) + raw
        else:
            out += struct.pack("<HB", len(comp), page) + comp
    return bytes(out)



# ---------------------------------------------------------------------------
# Snapshots .SNA
# ---------------------------------------------------------------------------

def read_sna(buf: bytes) -> ZXState:
    if len(buf) < 49179:
        raise FormatError("snapshot .sna demasiado corto")
    h = buf[:27]
    i_reg = h[0]
    hl2, de2, bc2, af2 = struct.unpack_from("<HHHH", h, 1)
    hl, de, bc, iy, ix = struct.unpack_from("<HHHHH", h, 9)
    iff = (h[19] >> 2) & 1
    r = h[20]
    af, sp = struct.unpack_from("<HH", h, 21)
    im, border = h[25], h[26]
    ram = bytearray(buf[27:27 + 49152])
    regs = {"AF": af, "BC": bc, "DE": de, "HL": hl, "AF'": af2, "BC'": bc2, "DE'": de2,
            "HL'": hl2, "IX": ix, "IY": iy, "SP": sp, "PC": 0, "I": i_reg, "R": r}
    st = ZXState(ram, regs, iff, iff, im & 3, border & 7)
    if len(buf) >= 49179 + 4:
        # SNA de 128K
        pc, p7ffd = struct.unpack_from("<HB", buf, 49179)
        regs["PC"] = pc
        st.model = "128k"
        st.port_7ffd = p7ffd
        cur = p7ffd & 7
        st.banks = {5: bytearray(ram[0:16384]), 2: bytearray(ram[16384:32768]),
                    cur: bytearray(ram[32768:49152])}
        i = 49179 + 4
        for b in (0, 1, 3, 4, 6, 7):
            if b == cur or b in (2, 5):
                continue
            st.banks[b] = bytearray(buf[i:i + 16384])
            i += 16384
        for b in range(8):
            st.banks.setdefault(b, bytearray(16384))
    else:
        # 48K: PC en la pila
        spo = sp - 0x4000
        if 0 <= spo < 49151:
            regs["PC"] = ram[spo] | ram[spo + 1] << 8
            regs["SP"] = (sp + 2) & 0xFFFF
    return st


def write_sna(st: ZXState) -> bytes:
    """SNA de 48K. Nota: el PC se empuja en la pila del programa."""
    r = dict(st.regs)
    ram = bytearray(st.ram)
    sp = (r["SP"] - 2) & 0xFFFF
    if sp >= 0x4000:
        ram[sp - 0x4000] = r["PC"] & 0xFF
        ram[sp - 0x4000 + 1] = r["PC"] >> 8
    h = bytearray(27)
    h[0] = r["I"]
    struct.pack_into("<HHHH", h, 1, r["HL'"], r["DE'"], r["BC'"], r["AF'"])
    struct.pack_into("<HHHHH", h, 9, r["HL"], r["DE"], r["BC"], r["IY"], r["IX"])
    h[19] = (st.iff2 & 1) << 2
    h[20] = r["R"] & 0xFF
    struct.pack_into("<HH", h, 21, r["AF"], sp)
    h[25], h[26] = st.im, st.border
    return bytes(h + ram)


# ---------------------------------------------------------------------------
# BASIC de Sinclair
# ---------------------------------------------------------------------------

ZX_TOKENS = {
    0xA3: "SPECTRUM", 0xA4: "PLAY", 0xA5: "RND", 0xA6: "INKEY$", 0xA7: "PI", 0xA8: "FN",
    0xA9: "POINT", 0xAA: "SCREEN$", 0xAB: "ATTR", 0xAC: "AT", 0xAD: "TAB", 0xAE: "VAL$",
    0xAF: "CODE", 0xB0: "VAL", 0xB1: "LEN", 0xB2: "SIN", 0xB3: "COS", 0xB4: "TAN", 0xB5: "ASN",
    0xB6: "ACS", 0xB7: "ATN", 0xB8: "LN", 0xB9: "EXP", 0xBA: "INT", 0xBB: "SQR", 0xBC: "SGN",
    0xBD: "ABS", 0xBE: "PEEK", 0xBF: "IN", 0xC0: "USR", 0xC1: "STR$", 0xC2: "CHR$",
    0xC3: "NOT", 0xC4: "BIN", 0xC5: "OR", 0xC6: "AND", 0xC7: "<=", 0xC8: ">=", 0xC9: "<>",
    0xCA: "LINE", 0xCB: "THEN", 0xCC: "TO", 0xCD: "STEP", 0xCE: "DEF FN", 0xCF: "CAT",
    0xD0: "FORMAT", 0xD1: "MOVE", 0xD2: "ERASE", 0xD3: "OPEN #", 0xD4: "CLOSE #",
    0xD5: "MERGE", 0xD6: "VERIFY", 0xD7: "BEEP", 0xD8: "CIRCLE", 0xD9: "INK", 0xDA: "PAPER",
    0xDB: "FLASH", 0xDC: "BRIGHT", 0xDD: "INVERSE", 0xDE: "OVER", 0xDF: "OUT",
    0xE0: "LPRINT", 0xE1: "LLIST", 0xE2: "STOP", 0xE3: "READ", 0xE4: "DATA",
    0xE5: "RESTORE", 0xE6: "NEW", 0xE7: "BORDER", 0xE8: "CONTINUE", 0xE9: "DIM",
    0xEA: "REM", 0xEB: "FOR", 0xEC: "GO TO", 0xED: "GO SUB", 0xEE: "INPUT", 0xEF: "LOAD",
    0xF0: "LIST", 0xF1: "LET", 0xF2: "PAUSE", 0xF3: "NEXT", 0xF4: "POKE", 0xF5: "PRINT",
    0xF6: "PLOT", 0xF7: "RUN", 0xF8: "SAVE", 0xF9: "RANDOMIZE", 0xFA: "IF", 0xFB: "CLS",
    0xFC: "DRAW", 0xFD: "CLEAR", 0xFE: "RETURN", 0xFF: "COPY",
}


def _zx_float(b5):
    e = b5[0]
    if e == 0:
        v = b5[2] | b5[3] << 8
        return v if b5[1] == 0 else v - 0x10000
    mant = ((b5[1] | 0x80) << 24) | (b5[2] << 16) | (b5[3] << 8) | b5[4]
    val = mant / (1 << 32) * (2.0 ** (e - 128))
    return -val if b5[1] & 0x80 else val


def detokenize_zx_basic(prog: bytes):
    """Devuelve lista de (nº línea, texto, valores numéricos) de un programa."""
    lines = []
    i = 0
    while i + 4 <= len(prog):
        num = prog[i] << 8 | prog[i + 1]
        ln = prog[i + 2] | prog[i + 3] << 8
        body = prog[i + 4:i + 4 + ln]
        i += 4 + ln
        if num > 9999:
            break
        text, nums, j = "", [], 0
        while j < len(body):
            c = body[j]
            if c == 0x0E and j + 5 < len(body) + 1:
                nums.append(_zx_float(body[j + 1:j + 6]))
                j += 6
                continue
            if c == 0x0D:
                break
            if c in ZX_TOKENS:
                text += " " + ZX_TOKENS[c] + " "
            elif 32 <= c < 128:
                text += chr(c)
            j += 1
        lines.append((num, " ".join(text.split()), nums))
    return lines


# ---------------------------------------------------------------------------
# Carga "a lo bruto" de cintas con cargador estándar
# ---------------------------------------------------------------------------

def load_tape_code(blocks):
    """Heurística: cargar en memoria los bloques CODE y localizar el USR de arranque.

    Devuelve (ram48k, entry, log). ``entry`` puede ser None.
    """
    ram = bytearray(49152)
    log = []
    entry = None
    usr_candidates = []
    pending = None
    for b in blocks:
        if b.is_header:
            pending = b.header()
            continue
        if pending is None:
            log.append(f"bloque sin cabecera ({len(b.data)} bytes, flag {b.flag:#x}): ignorado")
            continue
        h = pending
        pending = None
        if h["type"] == 0:
            for num, text, nums in detokenize_zx_basic(b.data):
                if "USR" in text:
                    for v in nums:
                        if isinstance(v, (int, float)) and 0x4000 <= int(v) <= 0xFFFF:
                            usr_candidates.append(int(v))
            log.append(f"BASIC '{h['name']}' ({len(b.data)} bytes)")
        elif h["type"] == 3:
            start = h["param1"]
            n = len(b.data)
            if start >= 0x4000:
                end = min(start + n, 0x10000)
                ram[start - 0x4000:end - 0x4000] = b.data[:end - start]
            log.append(f"CODE '{h['name']}' en {start:#06x}, {n} bytes")
        else:
            log.append(f"array '{h['name']}' ignorado")
    if usr_candidates:
        entry = usr_candidates[-1]
    return ram, entry, log
