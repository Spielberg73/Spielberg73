"""Carga de cualquier fichero soportado como un ``Program`` ejecutable.

Un ``Program`` es la imagen de memoria de 64K más el estado de la CPU y del
hardware, para una plataforma ('zx' o 'cpc'). Es la entrada común del
analizador y de los portadores.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .formats import cpc as fcpc
from .formats import zx as fzx
from .formats.zx import FormatError


@dataclass
class Program:
    platform: str                 # 'zx' | 'cpc'
    mem: bytearray                # 64K tal como la ve la CPU (sin ROM)
    regs: dict
    iff1: int = 1
    iff2: int = 1
    im: int = 1
    source: str = ""
    kind: str = ""                # z80 / sna / tap / dsk / bin ...
    notes: list = field(default_factory=list)
    zx_state: object = None       # ZXState original (si lo hay)
    cpc_state: object = None      # CPCState original (si lo hay)
    load_ranges: list = field(default_factory=list)   # (inicio, fin) de datos cargados
    firmware: bool = False        # CPC: estado con el firmware activo

    @property
    def entry(self):
        return self.regs["PC"]

    def to_zx_state(self) -> fzx.ZXState:
        st = fzx.ZXState(bytearray(self.mem[0x4000:]), dict(self.regs), self.iff1, self.iff2,
                         self.im, self.zx_state.border if self.zx_state else 7)
        return st

    def to_cpc_state(self) -> fcpc.CPCState:
        if self.cpc_state is not None:
            st = self.cpc_state
            mem = bytearray(st.mem)
            mem[0:65536] = self.mem
            return fcpc.CPCState(mem=mem, regs=dict(self.regs), iff1=self.iff1, iff2=self.iff2,
                                 im=self.im, ga_pen=st.ga_pen, palette=list(st.palette),
                                 ga_rmr=st.ga_rmr, ram_config=st.ram_config, crtc_sel=st.crtc_sel,
                                 crtc=list(st.crtc), upper_rom=st.upper_rom, ppi=st.ppi,
                                 psg_sel=st.psg_sel, psg=list(st.psg), model=st.model)
        return fcpc.CPCState(mem=bytearray(self.mem), regs=dict(self.regs), iff1=self.iff1,
                             iff2=self.iff2, im=self.im)


def _regs(**kw):
    r = {k: 0 for k in ("AF", "BC", "DE", "HL", "AF'", "BC'", "DE'", "HL'",
                        "IX", "IY", "SP", "PC", "I", "R")}
    r.update(kw)
    return r


# Variables de sistema del Spectrum tras el arranque (las que usan los juegos)
ZX_SYSVARS = {
    0x5C36: (0x3C00, 2),   # CHARS
    0x5C8D: (0x38, 1),     # ATTR_P
    0x5C8F: (0x38, 1),     # ATTR_T
    0x5C48: (0x38, 1),     # BORDCR
    0x5C84: (0x4000, 2),   # DF_CC
    0x5C3B: (0x0C, 1),     # FLAGS
    0x5CB2: (0xFF57, 2),   # RAMTOP
    0x5CB4: (0xFFFF, 2),   # P_RAMT
    0x5C7B: (0xFF58, 2),   # UDG
}


def _zx_default_sysvars(mem):
    for addr, (v, n) in ZX_SYSVARS.items():
        mem[addr] = v & 0xFF
        if n == 2:
            mem[addr + 1] = v >> 8


def detect_platform(path, data):
    ext = os.path.splitext(path)[1].lower()
    if data.startswith(b"MV - SNA"):
        return "cpc", "sna"
    if data.startswith((b"MV - CPC", b"EXTENDED")):
        return "cpc", "dsk"
    if data.startswith(fzx.TZX_MAGIC):
        return ("cpc", "cdt") if ext == ".cdt" else ("zx", "tzx")
    if ext == ".z80":
        return "zx", "z80"
    if ext == ".sna":
        return "zx", "sna"
    if ext == ".tap":
        return "zx", "tap"
    if fcpc.parse_amsdos_header(data):
        return "cpc", "amsdos"
    if ext == ".scr" and len(data) == 6912:
        return "zx", "scr"
    return None, "bin"


def load_program(path, platform=None, load_addr=None, exec_addr=None, file_in_image=None,
                 sp=None, zx_rom=None, cpc_roms=None) -> Program:
    with open(path, "rb") as f:
        data = f.read()
    plat, kind = detect_platform(path, data)
    platform = platform or plat
    if platform is None:
        raise FormatError(f"no sé qué es {path}: indica --platform zx|cpc y --load/--exec")
    name = os.path.basename(path)

    if kind in ("z80", "sna") and platform == "zx":
        st = fzx.read_z80(data) if kind == "z80" else fzx.read_sna(data)
        p = Program("zx", st.memory64k(), dict(st.regs), st.iff1, st.iff2, st.im, name, kind,
                    zx_state=st, load_ranges=[(0x4000, 0x10000)])
        if st.model == "128k":
            p.notes.append("snapshot de 128K: se usa la configuración de memoria actual "
                           f"(banco {st.port_7ffd & 7} en $C000); la paginación no se porta")
        return p

    if kind in ("tap", "tzx") and platform == "zx":
        blocks = fzx.read_tap(data) if kind == "tap" else fzx.tzx_data_blocks(fzx.read_tzx(data))
        if zx_rom and exec_addr is None:
            from .machines.spectrum import Spectrum48K
            m = Spectrum48K(zx_rom)
            ok, msg = m.load_tape_and_run(blocks)
            if ok:
                st = m.save_state()
                p = Program("zx", st.memory64k(), dict(st.regs), st.iff1, st.iff2, st.im, name,
                            kind, zx_state=st, load_ranges=[(0x4000, 0x10000)])
                p.notes.append(msg + " (con la ROM real)")
                return p
        ram, entry, log = fzx.load_tape_code(blocks)
        mem = bytearray(65536)
        mem[0x4000:] = ram
        _zx_default_sysvars(mem)
        if exec_addr is not None:
            entry = exec_addr
        if entry is None:
            raise FormatError("no encuentro el RANDOMIZE USR del cargador; indica --exec DIRECCIÓN")
        stack = sp if sp is not None else 0xFF58
        p = Program("zx", mem, _regs(PC=entry, SP=stack, IY=0x5C3A, I=0x3F), 1, 1, 1, name, kind)
        p.notes += log
        p.notes.append(f"cinta cargada con heurística de cargador estándar: arranque en {entry:#06x}"
                       " (los cargadores turbo o protegidos necesitan un snapshot .z80/.sna)")
        return p

    if kind == "scr":
        mem = bytearray(65536)
        mem[0x4000:0x4000 + 6912] = data
        return Program("zx", mem, _regs(PC=0, SP=0xFF58), 0, 0, 1, name, kind)

    if platform == "cpc" and kind == "sna":
        st = fcpc.read_cpc_sna(data)
        mem = bytearray(st.mem[:65536])
        p = Program("cpc", mem, dict(st.regs), st.iff1, st.iff2, st.im, name, kind, cpc_state=st,
                    load_ranges=[(0, 0x10000)])
        if len(st.mem) > 65536:
            p.notes.append("snapshot con 128K: solo se analizan los 64K base")
        return p

    if platform == "cpc" and kind in ("dsk", "cdt", "amsdos"):
        if kind == "dsk":
            files = fcpc.Disk.read(data).files()
            cands = []
            for fname, content in files.items():
                h = fcpc.parse_amsdos_header(content)
                if h and h["type"] == fcpc.AMSDOS_BINARY:
                    cands.append((fname, h, content[128:128 + h["length"]]))
        elif kind == "cdt":
            cands = [(f["name"], {"load": f["load"], "exec": f["exec"], "length": len(f["data"])},
                      f["data"]) for f in fcpc.read_cdt_files(data) if f["type"] & 0x0E == 2]
        else:
            h = fcpc.parse_amsdos_header(data)
            cands = [(name, h, data[128:128 + h["length"]])]
        if file_in_image:
            cands = [c for c in cands if c[0].upper().startswith(file_in_image.upper())]
        if not cands:
            raise FormatError("no hay ficheros binarios en la imagen" +
                              (f" que coincidan con {file_in_image}" if file_in_image else ""))
        # el mayor binario suele ser el juego
        fname, h, body = max(cands, key=lambda c: len(c[2]))
        load = load_addr if load_addr is not None else h["load"]
        if cpc_roms:
            entry = exec_addr if exec_addr is not None else h["exec"]
            return _cpc_with_firmware(name, kind, body, load, entry, cpc_roms, fname)
        mem = bytearray(65536)
        mem[load:load + len(body)] = body[:65536 - load]
        entry = exec_addr if exec_addr is not None else h["exec"]
        p = Program("cpc", mem, _regs(PC=entry, SP=sp if sp is not None else 0xBFF8), 0, 0, 1,
                    name, kind, load_ranges=[(load, load + len(body))])
        p.notes.append(f"fichero {fname}: {len(body)} bytes en {load:#06x}, ejecución en {entry:#06x}")
        others = [c[0] for c in cands if c[0] != fname]
        if others:
            p.notes.append("otros binarios en la imagen (no cargados): " + ", ".join(others))
        return p

    # binario en bruto
    if load_addr is None or exec_addr is None:
        raise FormatError("para un binario en bruto indica --load y --exec")
    if platform == "cpc" and cpc_roms:
        return _cpc_with_firmware(name, "bin", data, load_addr, exec_addr, cpc_roms, name)
    mem = bytearray(65536)
    mem[load_addr:load_addr + len(data)] = data[:65536 - load_addr]
    if platform == "zx":
        _zx_default_sysvars(mem)
    default_sp = 0xFF58 if platform == "zx" else 0xBFF8
    p = Program(platform, mem, _regs(PC=exec_addr, SP=sp if sp is not None else default_sp,
                                     IY=0x5C3A if platform == "zx" else 0),
                1 if platform == "zx" else 0, 1 if platform == "zx" else 0, 1, name, "bin", load_ranges=[(load_addr, load_addr + len(data))])
    return p


def _cpc_with_firmware(name, kind, body, load, entry, cpc_roms, fname):
    """Arranca el firmware del CPC, carga el binario y devuelve el estado listo."""
    from .machines.cpc import CPC
    lower, upper = cpc_roms
    m = CPC(lower, upper)
    m.boot_firmware()
    m.inject_and_call(body, load, entry)
    st = m.save_state()
    p = Program("cpc", bytearray(st.mem[:65536]), dict(st.regs), st.iff1, st.iff2, st.im, name,
                kind, cpc_state=st, load_ranges=[(load, load + len(body))])
    p.notes.append(f"{fname}: {len(body)} bytes en {load:#06x}, arranque en {entry:#06x} "
                   "con el firmware real inicializado")
    p.firmware = True
    return p
