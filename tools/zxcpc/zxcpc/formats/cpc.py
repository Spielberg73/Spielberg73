"""Formatos del Amstrad CPC: snapshots .SNA, cabecera AMSDOS, discos .DSK y cintas .CDT."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .zx import FormatError, read_tzx

# Colores del firmware (0..26) -> color hardware
FW_TO_HW = [20, 4, 21, 28, 24, 29, 12, 5, 13, 22, 6, 23, 30, 0, 31, 14, 7, 15, 18, 2, 19,
            26, 25, 27, 10, 3, 11]
# Color hardware -> firmware (los hw 1, 8, 9, 16 y 17 son duplicados)
HW_TO_FW = [13, 13, 19, 25, 1, 7, 10, 16, 7, 25, 24, 26, 6, 8, 15, 17, 1, 19, 18, 20, 0, 2, 9,
            11, 4, 22, 21, 23, 3, 5, 12, 14]
FW_NAMES = ["negro", "azul", "azul brillante", "rojo", "magenta", "malva", "rojo brillante",
            "púrpura", "magenta brillante", "verde", "cian", "azul cielo", "amarillo",
            "blanco", "azul pastel", "naranja", "rosa", "magenta pastel", "verde brillante",
            "verde mar", "cian brillante", "lima", "verde pastel", "cian pastel",
            "amarillo brillante", "amarillo pastel", "blanco brillante"]

# RGB "ideal" de los 27 colores del firmware (niveles 0, 50%, 100%)
FW_RGB = []
for _fw in range(27):
    _g, _r, _b = _fw // 9, (_fw // 3) % 3, _fw % 3
    FW_RGB.append(tuple([0, 0x80, 0xFF][c] for c in (_r, _g, _b)))
HW_RGB = [FW_RGB[HW_TO_FW[_hw]] for _hw in range(32)]


# ---------------------------------------------------------------------------
# Snapshot .SNA
# ---------------------------------------------------------------------------

DEFAULT_CRTC = [63, 40, 46, 0x8E, 38, 0, 25, 30, 0, 7, 0, 0, 0x30, 0, 0, 0, 0, 0]


@dataclass
class CPCState:
    mem: bytearray                                  # 64K o 128K
    regs: dict = field(default_factory=dict)        # AF BC DE HL ... PC I R
    iff1: int = 0
    iff2: int = 0
    im: int = 1
    ga_pen: int = 0
    palette: list = field(default_factory=lambda: [20] * 17)   # 16 tintas + borde (hw)
    ga_rmr: int = 0x01 | 0x04 | 0x08                # modo 1, ROMs desactivadas
    ram_config: int = 0
    crtc_sel: int = 0
    crtc: list = field(default_factory=lambda: list(DEFAULT_CRTC))
    upper_rom: int = 0
    ppi: tuple = (0, 0, 0, 0x82)                    # A, B, C, control
    psg_sel: int = 0
    psg: list = field(default_factory=lambda: [0] * 16)
    model: int = 2                                  # 0=464 1=664 2=6128

    @property
    def mode(self):
        return self.ga_rmr & 3


def _default_regs():
    return {k: 0 for k in ("AF", "BC", "DE", "HL", "AF'", "BC'", "DE'", "HL'",
                           "IX", "IY", "SP", "PC", "I", "R")}


def read_cpc_sna(buf: bytes) -> CPCState:
    if not buf.startswith(b"MV - SNA"):
        raise FormatError("no es un snapshot de CPC")
    h = buf[:256]
    ver = h[0x10]
    r = _default_regs()
    r["AF"] = h[0x12] << 8 | h[0x11]
    r["BC"] = h[0x14] << 8 | h[0x13]
    r["DE"] = h[0x16] << 8 | h[0x15]
    r["HL"] = h[0x18] << 8 | h[0x17]
    r["R"], r["I"] = h[0x19], h[0x1A]
    r["IX"], r["IY"], r["SP"], r["PC"] = struct.unpack_from("<HHHH", h, 0x1D)
    r["AF'"] = h[0x27] << 8 | h[0x26]
    r["BC'"] = h[0x29] << 8 | h[0x28]
    r["DE'"] = h[0x2B] << 8 | h[0x2A]
    r["HL'"] = h[0x2D] << 8 | h[0x2C]
    size_kb = struct.unpack_from("<H", h, 0x6B)[0]
    mem = bytearray(buf[256:256 + size_kb * 1024])
    if ver >= 3 and size_kb == 0:
        mem = _read_sna_v3_chunks(buf[256:])
    if len(mem) < 65536:
        mem = mem.ljust(65536, b"\0")
    return CPCState(
        mem=mem, regs=r, iff1=1 if h[0x1B] else 0, iff2=1 if h[0x1C] else 0, im=h[0x25],
        ga_pen=h[0x2E], palette=[v & 0x1F for v in h[0x2F:0x40]], ga_rmr=h[0x40] & 0x3F,
        ram_config=h[0x41] & 0x3F, crtc_sel=h[0x42], crtc=list(h[0x43:0x55]), upper_rom=h[0x55],
        ppi=tuple(h[0x56:0x5A]), psg_sel=h[0x5A], psg=list(h[0x5B:0x6B]),
        model=h[0x6D] if ver >= 2 else 0)


def _read_sna_v3_chunks(data):
    """Chunks MEM0..MEM8 comprimidos (RLE con marcador E5)."""
    mem = bytearray(65536)
    i = 0
    while i + 8 <= len(data):
        name = data[i:i + 4]
        ln = struct.unpack_from("<I", data, i + 4)[0]
        body = data[i + 8:i + 8 + ln]
        i += 8 + ln
        if name.startswith(b"MEM") and name[3:4].isdigit():
            n = int(name[3:4])
            out = bytearray()
            j = 0
            while j < len(body):
                if body[j] == 0xE5 and j + 1 < len(body):
                    cnt = body[j + 1]
                    if cnt == 0:
                        out.append(0xE5)
                        j += 2
                    else:
                        out += bytes([body[j + 2]]) * cnt
                        j += 3
                else:
                    out.append(body[j])
                    j += 1
            need = (n + 1) * 65536
            if len(mem) < need:
                mem = mem.ljust(need, b"\0")
            mem[n * 65536:n * 65536 + len(out)] = out[:65536]
    return mem


def write_cpc_sna(st: CPCState) -> bytes:
    h = bytearray(256)
    h[0:8] = b"MV - SNA"
    h[0x10] = 2
    r = st.regs
    h[0x11], h[0x12] = r["AF"] & 0xFF, r["AF"] >> 8
    h[0x13], h[0x14] = r["BC"] & 0xFF, r["BC"] >> 8
    h[0x15], h[0x16] = r["DE"] & 0xFF, r["DE"] >> 8
    h[0x17], h[0x18] = r["HL"] & 0xFF, r["HL"] >> 8
    h[0x19], h[0x1A] = r["R"] & 0xFF, r["I"] & 0xFF
    h[0x1B], h[0x1C] = st.iff1, st.iff2
    struct.pack_into("<HHHH", h, 0x1D, r["IX"], r["IY"], r["SP"], r["PC"])
    h[0x25] = st.im
    h[0x26], h[0x27] = r["AF'"] & 0xFF, r["AF'"] >> 8
    h[0x28], h[0x29] = r["BC'"] & 0xFF, r["BC'"] >> 8
    h[0x2A], h[0x2B] = r["DE'"] & 0xFF, r["DE'"] >> 8
    h[0x2C], h[0x2D] = r["HL'"] & 0xFF, r["HL'"] >> 8
    h[0x2E] = st.ga_pen
    h[0x2F:0x40] = bytes(v & 0x1F for v in st.palette[:17])
    h[0x40] = st.ga_rmr & 0x3F
    h[0x41] = st.ram_config & 0x3F
    h[0x42] = st.crtc_sel
    h[0x43:0x55] = bytes(v & 0xFF for v in st.crtc[:18])
    h[0x55] = st.upper_rom
    h[0x56:0x5A] = bytes(st.ppi)
    h[0x5A] = st.psg_sel
    h[0x5B:0x6B] = bytes(v & 0xFF for v in st.psg[:16])
    size = len(st.mem) // 1024
    struct.pack_into("<H", h, 0x6B, size)
    h[0x6D] = st.model
    return bytes(h) + bytes(st.mem)


# ---------------------------------------------------------------------------
# Cabecera AMSDOS
# ---------------------------------------------------------------------------

AMSDOS_BASIC, AMSDOS_PROTECTED, AMSDOS_BINARY = 0, 1, 2


def amsdos_checksum(h):
    return sum(h[0:67]) & 0xFFFF


def make_amsdos_header(name: str, ext: str, length: int, load: int, exec_addr: int,
                       ftype=AMSDOS_BINARY) -> bytes:
    h = bytearray(128)
    h[0] = 0
    h[1:9] = name.upper().encode("ascii")[:8].ljust(8, b" ")
    h[9:12] = ext.upper().encode("ascii")[:3].ljust(3, b" ")
    h[0x12] = ftype
    struct.pack_into("<HH", h, 0x13, 0, load)
    h[0x17] = 0xFF
    struct.pack_into("<HH", h, 0x18, length & 0xFFFF, exec_addr)
    h[0x40] = length & 0xFF
    h[0x41] = (length >> 8) & 0xFF
    h[0x42] = (length >> 16) & 0xFF
    struct.pack_into("<H", h, 0x43, amsdos_checksum(h))
    return bytes(h)


def parse_amsdos_header(data: bytes):
    """Devuelve dict con la cabecera si es válida, o None."""
    if len(data) < 128:
        return None
    h = data[:128]
    if struct.unpack_from("<H", h, 0x43)[0] != amsdos_checksum(h):
        return None
    if sum(h) == 0:
        return None
    length = h[0x40] | h[0x41] << 8 | h[0x42] << 16
    return {"user": h[0], "name": h[1:9].decode("latin-1").rstrip(),
            "ext": h[9:12].decode("latin-1").rstrip(), "type": h[0x12],
            "load": struct.unpack_from("<H", h, 0x15)[0],
            "exec": struct.unpack_from("<H", h, 0x1A)[0], "length": length}


# ---------------------------------------------------------------------------
# DSK (estándar y extendido)
# ---------------------------------------------------------------------------

class Disk:
    """Imagen de disco en memoria: pistas -> lista de sectores (C,H,R,N,datos)."""

    def __init__(self, tracks=40, sides=1):
        self.tracks = tracks
        self.sides = sides
        self.data = {}       # (pista, cara) -> lista de dicts de sector

    # -- lectura --------------------------------------------------------------
    @classmethod
    def read(cls, buf: bytes) -> "Disk":
        ext = buf.startswith(b"EXTENDED")
        if not ext and not buf.startswith(b"MV - CPC"):
            raise FormatError("no es una imagen DSK")
        nt, ns = buf[0x30], buf[0x31]
        d = cls(nt, ns)
        track_size = struct.unpack_from("<H", buf, 0x32)[0]
        pos = 0x100
        for t in range(nt):
            for s in range(ns):
                size = buf[0x34 + t * ns + s] * 256 if ext else track_size
                if size == 0:
                    continue
                tb = buf[pos:pos + size]
                pos += size
                if not tb.startswith(b"Track-Info"):
                    continue
                n_sec = tb[0x15]
                sec_size = 128 << tb[0x14]
                off = 0x100
                secs = []
                for k in range(n_sec):
                    c, hh, r, n, st1, st2, dl = struct.unpack_from("<BBBBBBH", tb, 0x18 + k * 8)
                    ln = dl if ext and dl else (128 << n if n < 7 else sec_size)
                    if not ext:
                        ln = sec_size
                    secs.append({"C": c, "H": hh, "R": r, "N": n, "data": bytes(tb[off:off + ln])})
                    off += ln
                d.data[(tb[0x10], tb[0x11])] = secs
        return d

    def sector(self, track, side, r):
        for s in self.data.get((track, side), []):
            if s["R"] == r:
                return s["data"]
        return None

    # -- sistema de ficheros AMSDOS (DATA / SYSTEM) ---------------------------
    def fs_params(self):
        secs = self.data.get((0, 0), [])
        first = min((s["R"] for s in secs), default=0xC1)
        if first & 0xF0 == 0xC0:
            return {"first": 0xC1, "off": 0}       # DATA
        if first & 0xF0 == 0x40:
            return {"first": 0x41, "off": 2}       # SYSTEM/VENDOR
        return {"first": 0x01, "off": 1}           # IBM

    def _block(self, b, p):
        out = bytearray()
        for k in range(2):
            ls = b * 2 + k
            t = p["off"] + ls // 9
            r = p["first"] + ls % 9
            sec = self.sector(t, 0, r)
            out += sec if sec is not None else bytes(512)
        return out

    def directory(self):
        p = self.fs_params()
        raw = self._block(0, p) + self._block(1, p)
        entries = []
        for i in range(64):
            e = raw[i * 32:(i + 1) * 32]
            if e[0] == 0xE5 or e[0] > 15:
                continue
            name = bytes(c & 0x7F for c in e[1:9]).decode("latin-1").rstrip()
            ext = bytes(c & 0x7F for c in e[9:12]).decode("latin-1").rstrip()
            entries.append({"user": e[0], "name": name, "ext": ext, "extent": e[12],
                            "rc": e[15], "blocks": [b for b in e[16:32] if b]})
        return entries

    def files(self):
        """Dict 'NOMBRE.EXT' -> bytes (incluida la cabecera AMSDOS si la hay)."""
        p = self.fs_params()
        groups = {}
        for e in self.directory():
            groups.setdefault((e["user"], e["name"], e["ext"]), []).append(e)
        out = {}
        for (u, n, x), ents in groups.items():
            data = bytearray()
            for e in sorted(ents, key=lambda e: e["extent"]):
                chunk = bytearray()
                for b in e["blocks"]:
                    chunk += self._block(b, p)
                data += chunk[:e["rc"] * 128]
            out[f"{n}.{x}" if x else n] = bytes(data)
        return out

    # -- escritura -------------------------------------------------------------
    @classmethod
    def new_data_disk(cls) -> "Disk":
        d = cls(40, 1)
        order = [0xC1, 0xC6, 0xC2, 0xC7, 0xC3, 0xC8, 0xC4, 0xC9, 0xC5]
        for t in range(40):
            d.data[(t, 0)] = [{"C": t, "H": 0, "R": r, "N": 2, "data": bytes([0xE5]) * 512}
                              for r in order]
        return d

    def _write_block(self, b, data, p):
        data = bytes(data).ljust(1024, b"\0")
        for k in range(2):
            ls = b * 2 + k
            t = p["off"] + ls // 9
            r = p["first"] + ls % 9
            for s in self.data[(t, 0)]:
                if s["R"] == r:
                    s["data"] = data[k * 512:(k + 1) * 512]

    def add_file(self, name: str, ext: str, content: bytes, user=0):
        """Añade un fichero (content ya debe incluir la cabecera AMSDOS si procede)."""
        p = self.fs_params()
        raw = bytearray(self._block(0, p) + self._block(1, p))
        used = {0, 1}
        free_slots = []
        for i in range(64):
            e = raw[i * 32:(i + 1) * 32]
            if e[0] == 0xE5:
                free_slots.append(i)
            else:
                used.update(b for b in e[16:32] if b)
        total_blocks = (self.tracks - p["off"]) * 9 // 2
        free_blocks = [b for b in range(total_blocks) if b not in used]
        nblocks = (len(content) + 1023) // 1024
        if nblocks > len(free_blocks):
            raise FormatError("no cabe en el disco")
        nextents = max(1, (nblocks + 15) // 16)
        if nextents > len(free_slots):
            raise FormatError("directorio lleno")
        blocks = free_blocks[:nblocks]
        for i, b in enumerate(blocks):
            self._write_block(b, content[i * 1024:(i + 1) * 1024], p)
        records = (len(content) + 127) // 128
        for x in range(nextents):
            e = bytearray(32)
            e[0] = user
            e[1:9] = name.upper().encode("ascii")[:8].ljust(8, b" ")
            e[9:12] = ext.upper().encode("ascii")[:3].ljust(3, b" ")
            e[12] = x
            rc = min(128, records - x * 128)
            e[15] = rc
            bl = blocks[x * 16:(x + 1) * 16]
            e[16:16 + len(bl)] = bytes(bl)
            slot = free_slots[x]
            raw[slot * 32:(slot + 1) * 32] = e
        self._write_block(0, raw[:1024], p)
        self._write_block(1, raw[1024:], p)

    def to_bytes(self) -> bytes:
        """Serializa como DSK estándar (todas las pistas del mismo tamaño)."""
        spt = max(len(v) for v in self.data.values())
        track_size = 0x100 + spt * 512
        h = bytearray(256)
        h[0:34] = b"MV - CPCEMU Disk-File\r\nDisk-Info\r\n"
        h[0x22:0x30] = b"zxcpc".ljust(14, b" ")
        h[0x30] = self.tracks
        h[0x31] = self.sides
        struct.pack_into("<H", h, 0x32, track_size)
        out = bytearray(h)
        for t in range(self.tracks):
            for s in range(self.sides):
                secs = self.data.get((t, s), [])
                tb = bytearray(0x100)
                tb[0:12] = b"Track-Info\r\n"
                tb[0x10], tb[0x11] = t, s
                tb[0x14] = 2
                tb[0x15] = len(secs)
                tb[0x16] = 0x4E
                tb[0x17] = 0xE5
                for k, sec in enumerate(secs):
                    struct.pack_into("<BBBBBBH", tb, 0x18 + k * 8, sec["C"], sec["H"], sec["R"],
                                     sec["N"], 0, 0, 0)
                body = b"".join(bytes(sec["data"]).ljust(512, b"\xe5")[:512] for sec in secs)
                tb += body
                out += tb.ljust(track_size, b"\0")
        return bytes(out)


def make_dsk(files) -> bytes:
    """``files``: lista de (nombre, ext, contenido)."""
    d = Disk.new_data_disk()
    for n, x, c in files:
        d.add_file(n, x, c)
    return d.to_bytes()


# ---------------------------------------------------------------------------
# CDT (cinta de CPC en contenedor TZX)
# ---------------------------------------------------------------------------

def read_cdt_files(buf: bytes):
    """Extrae los ficheros de una cinta de CPC grabada con el firmware estándar.

    Devuelve lista de dicts {name, type, load, exec, length, data}.
    """
    blocks = [b for b in read_tzx(buf) if b.id in (0x10, 0x11, 0x14) and b.data]
    files = []
    cur = None
    pending_header = None
    for b in blocks:
        payload = b.data
        sync = payload[0]
        body = _strip_cpc_crc(payload[1:])
        if sync == 0x2C and len(body) >= 64:
            hdr = body[:64]
            pending_header = {
                "name": hdr[0:16].split(b"\0")[0].decode("latin-1").strip(),
                "block": hdr[16], "last": hdr[17], "type": hdr[18],
                "size": struct.unpack_from("<H", hdr, 19)[0],
                "load": struct.unpack_from("<H", hdr, 21)[0], "first": hdr[23],
                "length": struct.unpack_from("<H", hdr, 24)[0],
                "exec": struct.unpack_from("<H", hdr, 26)[0]}
        elif sync == 0x16 and pending_header:
            h = pending_header
            pending_header = None
            if h["first"] or cur is None or cur["name"] != h["name"]:
                cur = {"name": h["name"], "type": h["type"], "load": h["load"], "exec": h["exec"],
                       "length": h["length"], "data": bytearray()}
                files.append(cur)
            cur["data"] += body[:h["size"]]
    for f in files:
        f["data"] = bytes(f["data"])
    return files


def _strip_cpc_crc(data):
    """Quita los CRC (2 bytes cada 256 de datos) de un registro de cinta CPC."""
    out = bytearray()
    i = 0
    while i + 258 <= len(data):
        out += data[i:i + 256]
        i += 258
    return bytes(out)
