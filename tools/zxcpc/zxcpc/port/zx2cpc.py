"""Portador ZX Spectrum 48K -> Amstrad CPC.

Estrategia ("port asistido"):

1. El juego conserva su memoria del Spectrum en $4000-$FFFF sin moverse.
2. La pantalla del CPC se coloca en $0000-$3FFF (donde el Spectrum tenía la
   ROM) con un CRTC de 256x192 en modo 1, y el HAL ocupa los huecos que deja.
3. Cada instrucción que depende del hardware del Spectrum se sustituye *en su
   sitio* por otra del mismo tamaño que llama al HAL (RST o CALL), así no se
   desplaza nada del código.
4. Las escrituras en la pantalla del Spectrum observadas en el análisis
   dinámico se reflejan al vuelo en la pantalla del CPC; un refresco de fondo
   convierte además unas líneas por frame como red de seguridad.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from ..formats.cpc import CPCState, FW_RGB, FW_TO_HW, FW_NAMES
from ..machines.spectrum import ZX_RGB, ZX_KEYS
from ..machines.cpc import CPC_KEY_POS
from ..z80 import decode as D
from ..z80.asm import Assembler

HAL_SRC = os.path.join(os.path.dirname(__file__), "hal", "zx2cpc.asm")
LOADER_SRC = os.path.join(os.path.dirname(__file__), "hal", "loader6128.asm")

STUB2_SRC = """stub2:
        ld hl,$4000
        ld de,$C000
        ld bc,$4000
        ldir
        ld bc,$7FC0
        out (c),c
        ld a,{I}
        ld i,a
        im 1
        ld sp,stub2_regs
        pop hl
        pop de
        pop bc
        pop af
        exx
        ex af,af'
        pop hl
        pop de
        pop bc
        pop ix
        pop iy
        pop af
        ld sp,{SP}
{EI}        jp {PC}
stub2_regs: dw {REGS}
"""

# Sustitutos de rutinas de la ROM
ROM_STUBS = {
    0x0D6B: "rom_cls", 0x0DAF: "rom_cls", 0x0D6E: "rom_cls_lower", 0x03B5: "rom_beeper",
    0x0556: "rom_ld_bytes", 0x0562: "rom_ld_bytes", 0x028E: "rom_key_scan",
    0x2294: "rom_border", 0x0038: "rom_frames", 0x203C: "rom_pr_string", 0x0010: "h_print",
    0x1601: "rom_chan_open", 0x0D4D: "rom_chan_open", 0x0000: "hal_reset",
}
ROM_STUB_SUPPORTED = {0x0D6B, 0x0DAF, 0x0D6E, 0x03B5, 0x028E, 0x2294, 0x0038, 0x203C, 0x0010,
                      0x1601, 0x0D4D}

# Mapa de teclas por defecto: tecla ZX -> (principal CPC, secundaria CPC)
DEFAULT_KEYS = {
    "CAPS": ("SHIFT", None), "SYM": ("CTRL", None), "ENTER": ("RETURN", "ENTER"),
    "SPACE": ("SPACE", None),
    # joystick Sinclair 1 (teclas 6-0) también desde el joystick del CPC
    "6": ("6", "JOYLEFT"), "7": ("7", "JOYRIGHT"), "8": ("8", "JOYDOWN"),
    "9": ("9", "JOYUP"), "0": ("0", "FIRE1"),
}

FREE_REGIONS_END = {"c0_end": 0x0200, "c3_end": 0x1900, "c4_end": 0x2200, "c5_end": 0x2A00,
                    "c6_end": 0x3200, "c7_end": 0x3A00}


@dataclass
class PortOptions:
    refresh_lines: int = 2
    beep_vol: int = 15
    mono: bool = False
    palette: list | None = None          # 4 colores del firmware (0-26)
    keys: dict = field(default_factory=dict)   # "Q": "JOYUP" o ["Q","JOYUP"]
    exclude: set = field(default_factory=set)  # direcciones que no se parchean
    rom_im2_vector: int = 0xFFFF
    patch_static: bool = True             # parchear E/S vistas solo estáticamente
    model: int = 2                        # modelo en el snapshot (0=464, 2=6128)
    zx_rom: bytes | None = None           # ROM de 48K del Spectrum aportada por el usuario

    @classmethod
    def from_json(cls, d):
        o = cls()
        for k, v in d.items():
            if k == "zx_rom":
                continue
            if k == "exclude":
                v = {int(x, 16) if isinstance(x, str) else x for x in v}
            if hasattr(o, k):
                setattr(o, k, v)
        return o


@dataclass
class Patch:
    addr: int
    orig: bytes
    new: bytes
    kind: str
    text: str
    handler: str | None = None
    note: str = ""


@dataclass
class PortResult:
    state: CPCState
    patches: list
    warnings: list
    palette: list                 # [(pen, fw, nombre)]
    hal_source: str
    hal_symbols: dict
    free_bytes: int
    options: PortOptions
    hw_tables: tuple = ((), ())


# ---------------------------------------------------------------------------
# Paleta y tablas de conversión
# ---------------------------------------------------------------------------

def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


def _nearest_fw(rgb):
    return min(range(27), key=lambda f: _dist(FW_RGB[f], rgb))


def colour_weights(screens):
    """Peso de cada color ZX (0-15, brillo*8+color) por píxeles en pantalla."""
    w = [0] * 16
    for ram in screens:          # ram = 48K desde $4000
        for cell in range(768):
            at = ram[0x1800 + cell]
            br = 8 if at & 0x40 else 0
            ink, paper = (at & 7) | br, ((at >> 3) & 7) | br
            row, col = divmod(cell, 32)
            ones = 0
            for ln in range(8):
                y = row * 8 + ln
                addr = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | col
                ones += bin(ram[addr]).count("1")
            w[ink] += ones + 1
            w[paper] += 64 - ones + 1
    # el negro normal y el brillante son el mismo color
    w[0] += w[8]
    w[8] = 0
    return w


def choose_palette(weights, n=4):
    """Elige n colores ZX representativos (k-medoides voraz ponderado)."""
    used = [c for c in range(16) if weights[c] > 0] or [0, 7]
    chosen = []
    while len(chosen) < n and len(chosen) < len(used):
        best, best_cost = None, None
        for cand in used:
            if cand in chosen:
                continue
            reps = chosen + [cand]
            cost = sum(weights[c] * min(_dist(ZX_RGB[c], ZX_RGB[r]) for r in reps) for c in used)
            if best_cost is None or cost < best_cost:
                best, best_cost = cand, cost
        chosen.append(best)
    while len(chosen) < n:
        for c in (0, 7, 2, 4, 1, 6, 3, 5):
            if c not in chosen:
                chosen.append(c)
                break
    return chosen[:n]


def build_tables(pal_zx, mono=False):
    """Devuelve (TABHI, TABLO, XM, PM, pen_of_colour) para 4 plumas."""
    masks = [0x00, 0xF0, 0x0F, 0xFF]
    tabhi = bytes(((v >> 4) << 4) | (v >> 4) for v in range(256))
    tablo = bytes(((v & 15) << 4) | (v & 15) for v in range(256))

    def pens_by_distance(c):
        return sorted(range(4), key=lambda p: _dist(ZX_RGB[c], ZX_RGB[pal_zx[p]]))

    xm = bytearray(256)
    pm = bytearray(256)
    for at in range(256):
        br = 8 if at & 0x40 else 0
        ink, paper = (at & 7) | br, ((at >> 3) & 7) | br
        if mono:
            ip, pp = (1, 0) if ink != paper else (0, 0)
        else:
            order_i = pens_by_distance(ink)
            pp = pens_by_distance(paper)[0]
            ip = order_i[0]
            if ip == pp and (ink & 7) != (paper & 7):
                ip = order_i[1]
        xm[at] = masks[ip] ^ masks[pp]
        pm[at] = masks[pp]
    return tabhi, tablo, bytes(xm), bytes(pm)


def convert_screen_to_cpc(ram, xm, pm):
    """Convierte la pantalla ZX (ram = 48K desde $4000) a la pantalla CPC ($0000-$3FFF)."""
    out = bytearray(16384)
    for y in range(192):
        t, r, ln = y >> 6, (y >> 3) & 7, y & 7
        for col in range(32):
            zaddr = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | col
            v = ram[zaddr]
            at = ram[0x1800 + (y >> 3) * 32 + col]
            caddr = ln * 0x800 + (t + 1) * 0x200 + r * 64 + col * 2
            hi = ((v >> 4) << 4) | (v >> 4)
            lo = ((v & 15) << 4) | (v & 15)
            out[caddr] = (hi & xm[at]) ^ pm[at]
            out[caddr + 1] = (lo & xm[at]) ^ pm[at]
    return out


# ---------------------------------------------------------------------------
# Generación de manejadores
# ---------------------------------------------------------------------------

PROLOGUE = "        ex (sp),hl\n        inc hl\n        ex (sp),hl\n"


def _asm_ins(ins: D.Instr) -> str:
    return "        " + ins.text() + "\n"


def _mirror_code(ins: D.Instr):
    """Código que refleja en pantalla lo que acaba de escribir ``ins``.

    Devuelve (código que va ANTES de la instrucción, código DESPUÉS) o None.
    """
    wk = ins.mem_write_kind()
    if wk is None:
        return None
    mode, det = wk
    if mode == "ind":
        if det == "HL":
            return "", "        jp mirror_hl\n"
        if det == "DE":
            return "", "        jp mirror_de\n"
        return "", ("        push hl\n        ld h,b\n        ld l,c\n        call mirror_hl\n"
                    "        pop hl\n        ret\n")
    if mode == "idx":
        reg, d = det
        return "", (f"        push af\n        push hl\n        push de\n        push {reg}\n"
                    f"        pop hl\n        ld de,{d}\n        add hl,de\n        call mirror_hl\n"
                    "        pop de\n        pop hl\n        pop af\n        ret\n")
    if mode == "abs":
        nn, width = det
        body = f"        push hl\n        ld hl,{nn}\n        call mirror_hl\n"
        if width == 2:
            body += "        inc hl\n        call mirror_hl\n"
        return "", body + "        pop hl\n        ret\n"
    if mode == "block":
        if det == "LDIR":
            return "        push de\n", ("        ex (sp),hl\n        push af\n        push bc\n"
                                         "        push de\n        call mirror_span\n        pop de\n"
                                         "        pop bc\n        pop af\n        pop hl\n        ret\n")
        if det == "LDDR":
            return "        push de\n", ("        ex (sp),hl\n        push af\n        push bc\n"
                                         "        push de\n        ex de,hl\n        inc hl\n"
                                         "        inc de\n        call mirror_span\n        pop de\n"
                                         "        pop bc\n        pop af\n        pop hl\n        ret\n")
        # LDI / LDD
        return "        push de\n", "        ex (sp),hl\n        call mirror_hl\n        pop hl\n        ret\n"
    return None


def _in_c_handler(reg):
    """IN r,(C) completo (valor + flags, conservando el acarreo)."""
    set_reg = {
        "B": "        ld b,e\n", "C": "        ld c,e\n",
        "D": "        ld hl,3\n        add hl,sp\n        ld (hl),e\n",
        "E": "        ld hl,2\n        add hl,sp\n        ld (hl),e\n",
        "H": "        ld hl,1\n        add hl,sp\n        ld (hl),e\n",
        "L": "        ld hl,0\n        add hl,sp\n        ld (hl),e\n",
        "A": "        ld hl,5\n        add hl,sp\n        ld (hl),e\n",
        "F": "",
    }[reg]
    # la pila: [HL][DE][AF]  -> F en SP+4, A en SP+5
    return ("        push af\n        push de\n        push hl\n        call in_c_value\n"
            "        ld e,a\n        ld hl,4\n        add hl,sp\n        call in_flags\n"
            + set_reg +
            "        pop hl\n        pop de\n        pop af\n        ret\n")


def _out_c_handler(reg):
    load = "        xor a\n" if reg == "0" else ("" if reg == "A" else f"        ld a,{reg.lower()}\n")
    return ("        push af\n        push bc\n        push hl\n" + load +
            "        call out_c_value\n        pop hl\n        pop bc\n        pop af\n        ret\n")


# ---------------------------------------------------------------------------
# Portador
# ---------------------------------------------------------------------------

class ZX2CPC:
    def __init__(self, analysis, options: PortOptions | None = None):
        self.an = analysis
        self.p = analysis.program
        self.opt = options or PortOptions()
        self.warnings = []
        self.patches = []
        self.handlers = {}        # clave -> (etiqueta, código, tipo 'rst30'|'rst8'|'call')
        self.ids = {}             # etiqueta -> id (rst30/rst8)
        self.hash_sites = {}      # dirección de retorno -> etiqueta

    # -- utilidades --------------------------------------------------------------
    def _handler(self, key, code, htype):
        if key not in self.handlers:
            label = f"hg_{len(self.handlers)}"
            if htype == "rst30":
                code = PROLOGUE + code
            self.handlers[key] = (label, code, htype)
        return self.handlers[key][0]

    def _id(self, label):
        if label not in self.ids:
            if len(self.ids) >= 128:
                raise ValueError("demasiados manejadores con id (máx. 128)")
            self.ids[label] = len(self.ids)
        return self.ids[label]

    # -- selección de parches -------------------------------------------------------
    def plan(self):
        an = self.an
        mem = self.p.mem
        executed = an.trace.executed if an.trace is not None else set()
        kinds_at = {}
        for h in an.hotspots:
            kinds_at.setdefault(h.addr, []).append(h)
        taken = {}                  # byte -> addr del parche
        for addr in sorted(kinds_at):
            if addr in self.opt.exclude:
                continue
            ins = an.instrs[addr]
            hs = kinds_at[addr]
            confident = addr in executed or self.opt.patch_static
            patch = None
            kinds = {h.kind for h in hs}
            try:
                if "halt" in kinds:
                    patch = Patch(addr, ins.raw, b"\xEF", "halt", ins.text(), "h_halt")
                elif kinds & {"ula_out", "ula_in", "kempston_in", "ay_io", "floating_bus",
                              "paging", "io_unknown"}:
                    if confident:
                        patch = self._plan_io(ins, hs)
                elif kinds & {"im2", "ld_i"}:
                    patch = self._plan_int(ins)
                elif "rom_call" in kinds:
                    patch = self._plan_rom(ins, hs)
                elif kinds & {"screen_write"}:
                    patch = self._plan_screen(ins, hs)
            except ValueError as e:
                self.warnings.append(f"{addr:04X} {ins.text()}: {e}")
                patch = None
            if patch is None:
                continue
            rng = range(addr, addr + len(patch.orig))
            if any(b in taken for b in rng):
                self.warnings.append(f"{addr:04X}: parche solapado con {taken[rng[0]]:04X}, omitido")
                continue
            if bytes(mem[addr:addr + len(patch.orig)]) != patch.orig:
                self.warnings.append(f"{addr:04X}: los bytes no coinciden, omitido")
                continue
            for b in rng:
                taken[b] = addr
            self.patches.append(patch)
        self._report_unhandled()

    def _plan_io(self, ins, hs):
        io = ins.io_kind()
        direction, form, val = io
        kinds = {h.kind for h in hs}
        if form == "block":
            self.warnings.append(f"{ins.addr:04X} {ins.text()}: E/S en bloque no soportada")
            return None
        if form == "n":
            if direction == "in":
                if "ula_in" in kinds:
                    target = "h_in_ula_a"
                elif "kempston_in" in kinds:
                    target = "h_in_kemp_a"
                else:
                    target = "h_in_float_a"
                    if "floating_bus" in kinds:
                        self.warnings.append(f"{ins.addr:04X} {ins.text()}: lectura del bus "
                                             "flotante: devolverá siempre $FF")
                label = self._handler(("in_n", target), f"        jp {target}\n", "rst30")
            else:
                if val & 1:
                    label = self._handler(("out_ignore",), "        ret\n", "rst30")
                else:
                    label = self._handler(("out_n", "ula"), "        jp h_out_ula\n", "rst30")
        else:
            reg = None
            if direction == "in":
                reg = ins.operands[0].value
                label = self._handler(("in_c", reg), _in_c_handler(reg), "rst30")
            else:
                src = ins.operands[1]
                reg = "0" if src.kind == D.IMM8 else src.value
                label = self._handler(("out_c", reg), _out_c_handler(reg), "rst30")
            if "paging" in kinds:
                self.warnings.append(f"{ins.addr:04X} {ins.text()}: paginación de 128K ignorada")
        return Patch(ins.addr, ins.raw, bytes([0xF7, self._id(label)]), "io", ins.text(), label)

    def _plan_int(self, ins):
        if ins.op == "IM":
            mode = ins.operands[0].value
            code = f"        push af\n        ld a,{1 if mode == 2 else 0}\n        ld (game_im2),a\n" \
                   "        pop af\n        ret\n"
            label = self._handler(("im", mode == 2), code, "rst30")
        else:
            label = self._handler(("ld_i",), "        ld i,a\n        ld (game_i),a\n        ret\n",
                                  "rst30")
        return Patch(ins.addr, ins.raw, bytes([0xF7, self._id(label)]), "int", ins.text(), label)

    def _plan_rom(self, ins, hs):
        h = hs[0]
        target = h.detail.get("target")
        if h.detail.get("indirect"):
            self.warnings.append(f"{ins.addr:04X} {ins.text()}: salto indirecto a la ROM "
                                 f"({h.detail.get('name')}) — hay que resolverlo a mano")
            return None
        if ins.flow == "rst":
            if target == 0x10:
                return None          # RST $10 ya es PRINT en el HAL
            if target in (0x18, 0x20, 0x28, 0x30):
                self.warnings.append(f"{ins.addr:04X} {ins.text()}: el juego usa el RST de la "
                                     "ROM que el HAL reutiliza; necesita revisión manual")
            return None
        stub = ROM_STUBS.get(target, "rom_ret")
        if target not in ROM_STUB_SUPPORTED:
            sev = "no hay sustituto" if target not in ROM_STUBS else "solo se simula"
            self.warnings.append(f"{ins.addr:04X} {ins.text()}: rutina ROM {h.detail.get('name')}: "
                                 f"{sev}")
        raw = bytearray(ins.raw)
        return Patch(ins.addr, ins.raw, bytes(raw[:-2]) + b"@@", "rom", ins.text(), stub,
                     note=h.detail.get("name", ""))

    def _plan_screen(self, ins, hs):
        wk = ins.mem_write_kind()
        if wk is None:
            return None
        if wk[0] == "stack":
            return None
        mc = _mirror_code(ins)
        if mc is None:
            return None
        pre, post = mc
        body = pre + _asm_ins(ins) + post
        n = ins.length
        raw = ins.raw
        if n == 1:
            if raw == b"\x77":
                return Patch(ins.addr, raw, b"\xE7", "screen", ins.text(), "mirror_hl")
            if raw == b"\x12":
                return Patch(ins.addr, raw, b"\xDF", "screen", ins.text(), "mirror_de")
            label = self._handler(("scr8", raw), body, "rst8")
            self._id(label)
            self.hash_sites[(ins.addr + 1) & 0xFFFF] = label
            return Patch(ins.addr, raw, b"\xCF", "screen", ins.text(), label)
        if n == 2:
            label = self._handler(("scr30", raw), body, "rst30")
            return Patch(ins.addr, raw, bytes([0xF7, self._id(label)]), "screen", ins.text(), label)
        label = self._handler(("scrcall", raw), body, "call")
        return Patch(ins.addr, raw, b"\xCD@@" + b"\x00" * (n - 3), "screen", ins.text(), label)

    def _report_unhandled(self):
        an = self.an
        for h in an.hotspots:
            if h.kind == "stack_screen":
                self.warnings.append(f"{h.addr:04X} {h.text}: volcado con PUSH a pantalla: "
                                     "solo lo verá el refresco de fondo")
            elif h.kind == "rom_read":
                pages = ", ".join(f"{p:#06x}" for p in h.detail.get("pages", [])[:4])
                self.warnings.append(f"{h.addr:04X} {h.text}: lee datos de la ROM ({pages})")
            elif h.kind == "smc":
                patched = {p.addr for p in self.patches}
                hit = [a for a in h.detail.get("modifies", []) if a in patched]
                if hit:
                    self.warnings.append(f"{h.addr:04X} {h.text}: modifica código parcheado "
                                         f"({', '.join(f'{a:04X}' for a in hit)})")
        if an.trace is not None:
            if 2 in an.trace.int_modes and self.p.im != 2 and not any(
                    h.kind == "im2" for h in an.hotspots):
                self.warnings.append("se observó IM 2 sin instrucción IM 2 localizada")
            low = [pc for pc in an.trace.executed if pc < 0x4000]
            if low and self.p.platform == "zx":
                pass

    # -- datos de la ROM (con la ROM del usuario) ---------------------------------------
    def _rom_data(self, mem):
        rom = self.opt.zx_rom
        p = self.p
        if not rom or len(rom) < 16384:
            if any(h.kind == "rom_read" for h in self.an.hotspots):
                self.warnings.append("el juego lee datos de la ROM: pasa --rom 48.rom para que el "
                                     "portador pueda recolocarlos (fuente, vectores IM 2)")
            return
        # vector IM 2 dentro de la ROM
        i_vals = set(self.an.trace.i_values) if self.an.trace is not None else set()
        if p.im == 2:
            i_vals.add(p.regs["I"])
        for i in i_vals:
            if i < 0x40:
                v = (i << 8) | 0xFF
                self.opt.rom_im2_vector = rom[v] | (rom[(v + 1) & 0x3FFF] << 8)
        # fuente de caracteres de la ROM ($3D00-$3FFF)
        uses_font = False
        refs = []
        executed = self.an.trace.executed if self.an.trace is not None else set()
        for a, ins in self.an.instrs.items():
            if ins.op == "LD" and len(ins.operands) == 2 and ins.operands[1].kind == D.IMM16 \
                    and ins.operands[0].kind == D.REG16 and 0x3C00 <= ins.operands[1].value < 0x4000:
                if a in executed or not executed:
                    refs.append(ins)
        for h in self.an.hotspots:
            if h.kind == "rom_read" and any(0x3D00 <= pg < 0x4000 for pg in h.detail.get("pages", [])):
                uses_font = True
        chars = mem[0x5C36] | mem[0x5C37] << 8
        if any(h.kind == "rom_call" and h.detail.get("target") in (0x10, 0x203C)
               for h in self.an.hotspots) or \
                any(i.flow == "rst" and i.target == 0x10 for i in self.an.instrs.values()):
            uses_font = uses_font or chars == 0x3C00
        if not (uses_font or refs):
            return
        where = self._find_free(mem, 768)
        if where is None:
            self.warnings.append("el juego usa la fuente de la ROM pero no encuentro 768 bytes "
                                 "libres en su memoria para copiarla")
            return
        mem[where:where + 768] = rom[0x3D00:0x4000]
        self.warnings.append(f"fuente de la ROM copiada a {where:#06x}")
        if chars == 0x3C00:
            base = where - 256
            mem[0x5C36], mem[0x5C37] = base & 0xFF, base >> 8
        patched = {pt.addr for pt in self.patches}
        for ins in refs:
            if ins.addr in patched:
                continue
            v = ins.operands[1].value
            nv = (where + (v - 0x3D00)) & 0xFFFF
            new = bytes(ins.raw[:-2]) + bytes([nv & 0xFF, nv >> 8])
            self.patches.append(Patch(ins.addr, ins.raw, new, "rom_font", ins.text(), None,
                                      note=f"{v:#06x} -> {nv:#06x}"))

    def _find_free(self, mem, size):
        """Zona de ``size`` bytes a cero, nunca escrita, sin código y lejos de la pila."""
        tr = self.an.trace
        code = bytearray(65536)
        for a, ins in self.an.instrs.items():
            for k in range(ins.length):
                code[(a + k) & 0xFFFF] = 1
        lo_sp = (tr.sp_min - 128) if tr is not None else 0
        hi_sp = (tr.sp_max + 2) if tr is not None else 0
        run = 0
        for a in range(0xFFFF, 0x5CFF, -1):
            ok = mem[a] == 0 and not code[a] and not (lo_sp <= a <= hi_sp) and \
                (tr is None or not tr.written[a])
            run = run + 1 if ok else 0
            if run == size:
                return a
        return None

    # -- construcción ------------------------------------------------------------------
    def build(self) -> PortResult:
        self.plan()
        opt = self.opt
        p = self.p
        game_mem = bytearray(p.mem)
        self._rom_data(game_mem)
        ram = game_mem[0x4000:]
        screens = [ram]
        if self.an.trace is not None and self.an.trace.final_state is not None:
            screens.append(self.an.trace.final_state.ram)
        if opt.palette:
            pal_fw = list(opt.palette)[:4]
            pal_zx = [min(range(16), key=lambda c: _dist(ZX_RGB[c], FW_RGB[f])) for f in pal_fw]
        elif opt.mono:
            pal_zx = [0, 7, 7, 7]
            pal_fw = [0, 26, 26, 26]
        else:
            pal_zx = choose_palette(colour_weights(screens))
            pal_fw = [_nearest_fw(ZX_RGB[c]) for c in pal_zx]
        tabhi, tablo, xm, pm = build_tables(pal_zx, opt.mono)

        zx_state = p.zx_state
        border = zx_state.border if zx_state is not None else 7
        game_im2 = 1 if p.im == 2 else 0
        syms = {"REFRESH_LINES": max(1, opt.refresh_lines), "BEEP_VOL": opt.beep_vol,
                "ROM_IM2_VECTOR": opt.rom_im2_vector, "GAME_IM2": game_im2,
                "GAME_I": p.regs["I"] & 0xFF, "INIT_ULA": border, "kmap": 0}
        with open(HAL_SRC, encoding="utf-8") as f:
            base_src = f.read()
        # 1ª pasada: medir el HAL fijo
        fixed = Assembler(syms).assemble(base_src, "zx2cpc.asm")
        syms["kmap"] = fixed.symbols["c4_end"]
        fixed = Assembler(syms).assemble(base_src, "zx2cpc.asm")
        free = [(fixed.symbols[k] + (160 if k == "c4_end" else 0), end)
                for k, end in FREE_REGIONS_END.items()]
        # 2ª: colocar manejadores generados (y el STUB2 del cargador de disco)
        self._stub2 = self._stub2_src(p, pal_fw, border)
        gen_src, placed = self._place_handlers(fixed.symbols, free, syms)
        full_src = base_src + "\n; ---- código generado por el portador ----\n" + gen_src
        res = Assembler(syms).assemble(full_src, "zx2cpc.asm")
        symbols = res.symbols

        # memoria del CPC
        mem = bytearray(65536)
        mem[0x4000:] = ram
        mem[0:0x4000] = convert_screen_to_cpc(ram, xm, pm)
        for s in res.segments:
            mem[s.org:s.org + len(s.data)] = s.data
        mem[0x0800:0x0900] = tabhi
        mem[0x0900:0x0A00] = tablo
        mem[0x1000:0x1100] = xm
        mem[0x1100:0x1200] = pm
        # tabla de saltos
        for label, i in self.ids.items():
            a = symbols[label]
            mem[0x1900 + i] = a & 0xFF
            mem[0x1980 + i] = a >> 8
        # tabla hash
        for ret, label in self.hash_sites.items():
            idx = ((ret & 0xFF) ^ (ret >> 8)) & 31
            for k in range(32):
                j = (idx + k) & 31
                if mem[0x3820 + j] == 0:
                    mem[0x3800 + j] = ret & 0xFF
                    mem[0x3820 + j] = ret >> 8
                    mem[0x3840 + j] = self.ids[label]
                    break
            else:
                raise ValueError("tabla hash llena")
        # mapa de teclado
        kmap_addr = symbols["kmap"]
        mem[kmap_addr:kmap_addr + 160] = self._kmap()
        # tabla de borde
        bt = symbols["border_tab"]
        for c in range(8):
            mem[bt + c] = FW_TO_HW[_nearest_fw(ZX_RGB[c])] | 0x40
        # aplicar parches
        for pt in self.patches:
            new = bytearray(pt.new)
            if b"@@" in new:
                i = new.index(b"@@")
                tgt = symbols[pt.handler] if pt.handler in symbols else None
                if tgt is None:
                    raise ValueError(f"manejador desconocido {pt.handler}")
                new[i:i + 2] = bytes([tgt & 0xFF, tgt >> 8])
            pt.new = bytes(new)
            mem[pt.addr:pt.addr + len(new)] = new

        st = self._cpc_state(mem, pal_fw, border)
        palette = [(i, f, FW_NAMES[f]) for i, f in enumerate(pal_fw)]
        free_bytes = sum(end - start for start, end in placed)
        header = "; Símbolos fijados por el portador\n" + "".join(
            f"{k:<16}equ {v}\n" for k, v in syms.items()) + "\n"
        return PortResult(st, self.patches, self.warnings, palette, header + full_src, symbols,
                          free_bytes, opt, getattr(self, "_hw_tables", ((), ())))

    def _place_handlers(self, symbols, free, syms):
        """Coloca los manejadores generados en los huecos libres del HAL."""
        items = []
        for key, (label, code, htype) in self.handlers.items():
            src = f"{label}:\n{code}"
            probe = Assembler(dict(symbols, **syms)).assemble(f" org $C000\n{src}")
            size = sum(len(s.data) for s in probe.segments)
            items.append((size, label, src))
        if getattr(self, "_stub2", None):
            probe = Assembler(dict(symbols, **syms)).assemble(f" org $C000\n{self._stub2}")
            items.append((sum(len(s.data) for s in probe.segments), "stub2", self._stub2))
        items.sort(reverse=True)
        regions = [[s, e] for s, e in free]
        out = []
        for size, label, src in items:
            for r in regions:
                if r[1] - r[0] >= size:
                    out.append(f"        org ${r[0]:04X}\n{src}")
                    r[0] += size
                    break
            else:
                raise ValueError(f"no queda sitio en el HAL para {label} ({size} bytes); "
                                 "excluye parches con --exclude o reduce la lista")
        return "\n".join(out) + "\n", [tuple(r) for r in regions]

    def _stub2_src(self, p, pal_fw, border):
        r = p.regs
        pc, sp = r["PC"], r["SP"]
        if pc < 0x4000:
            sp_ret = p.mem[sp] | p.mem[(sp + 1) & 0xFFFF] << 8
            pc, sp = sp_ret, (sp + 2) & 0xFFFF
        st_pal = [FW_TO_HW[f] for f in pal_fw] + [FW_TO_HW[0]] * 12
        st_pal.append(FW_TO_HW[_nearest_fw(ZX_RGB[border & 7])])
        crtc = [63, 32, 42, 0x8E, 38, 0, 24, 30, 0, 7, 0, 0, 0x01, 0x00]
        regs = [r["HL'"], r["DE'"], r["BC'"], r["AF'"], r["HL"], r["DE"], r["BC"], r["IX"],
                r["IY"], r["AF"]]
        self._hw_tables = (crtc, [v | 0x40 for v in st_pal])
        return STUB2_SRC.format(I=r["I"] & 0xFF, SP=sp, PC=pc,
                                EI="        ei\n" if p.iff1 else "",
                                REGS=",".join(str(v) for v in regs))

    def _kmap(self):
        """40 entradas x 4 bytes: (línea, máscara) principal y secundaria."""
        out = bytearray()
        user = {}
        for k, v in (self.opt.keys or {}).items():
            if isinstance(v, str):
                v = [v]
            user[k.upper()] = [x.upper() for x in v]
        for r in range(8):
            for b in range(5):
                zk = ZX_KEYS[r][b]
                prim, sec = DEFAULT_KEYS.get(zk, (zk, None))
                if zk in user:
                    lst = user[zk]
                    if len(lst) == 1:
                        sec = lst[0]
                    else:
                        prim, sec = lst[0], lst[1]
                for ck in (prim, sec):
                    if ck and ck in CPC_KEY_POS:
                        line, bit = CPC_KEY_POS[ck]
                        out += bytes([line, 1 << bit])
                    else:
                        out += bytes([10, 1])
        return bytes(out)

    def _cpc_state(self, mem, pal_fw, border):
        p = self.p
        regs = dict(p.regs)
        if regs["PC"] < 0x4000:
            # snapshot tomado dentro de la ROM: volver a la dirección de la pila
            sp = regs["SP"]
            ret = mem[sp] | mem[(sp + 1) & 0xFFFF] << 8
            self.warnings.append(f"el snapshot estaba en la ROM ({regs['PC']:#06x}); se continúa "
                                 f"en la dirección de retorno {ret:#06x}")
            regs["PC"] = ret
            regs["SP"] = (sp + 2) & 0xFFFF
        palette = [FW_TO_HW[f] for f in pal_fw] + [FW_TO_HW[0]] * 12
        palette.append(FW_TO_HW[_nearest_fw(ZX_RGB[border & 7])])
        crtc = [63, 32, 42, 0x8E, 38, 0, 24, 30, 0, 7, 0, 0, 0x01, 0x00, 0, 0, 0, 0]
        psg = [0] * 16
        psg[7] = 0x3F
        return CPCState(mem=mem, regs=regs, iff1=p.iff1, iff2=p.iff2, im=1, ga_pen=16,
                        palette=palette, ga_rmr=0x01 | 0x04 | 0x08, ram_config=0, crtc_sel=0,
                        crtc=crtc, upper_rom=0, ppi=(8, 0, 0, 0x82), psg_sel=8, psg=psg,
                        model=self.opt.model)


def port_zx_to_cpc(analysis, options=None) -> PortResult:
    return ZX2CPC(analysis, options).build()


def build_dsk(result: PortResult) -> bytes:
    """Disco de datos para CPC 6128: RUN"DISC" carga y arranca el juego portado."""
    from ..formats.cpc import make_amsdos_header, make_dsk
    stub2 = result.hal_symbols.get("stub2")
    if stub2 is None:
        raise ValueError("el HAL no contiene STUB2")
    crtc, pal = result.hw_tables
    with open(LOADER_SRC, encoding="utf-8") as f:
        src = f.read()
    src += "\nstub1_crtc: db " + ",".join(str(v) for v in crtc) + \
           "\nstub1_pal:  db " + ",".join(str(v) for v in pal) + "\nstub1_all_end:\n"
    loader = Assembler({"STUB2": stub2}).assemble(src, "loader6128.asm").image()
    mem = result.state.mem
    files = [("DISC", "BIN", make_amsdos_header("DISC", "BIN", len(loader), 0x8000, 0x8000) + loader)]
    for i, part in enumerate("ABCD"):
        data = bytes(mem[i * 0x4000:(i + 1) * 0x4000])
        files.append(("ZXCPC", part, make_amsdos_header("ZXCPC", part, len(data), 0x4000, 0) + data))
    return make_dsk(files)


def patches_json(result: PortResult):
    return json.dumps([{"addr": f"{p.addr:04X}", "orig": p.orig.hex(" ").upper(),
                        "new": p.new.hex(" ").upper(), "kind": p.kind, "instr": p.text,
                        "handler": p.handler, "note": p.note} for p in result.patches],
                      indent=1, ensure_ascii=False)
