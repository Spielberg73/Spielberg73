"""Portador Amstrad CPC -> ZX Spectrum +2A/+3.

Estrategia:

* El juego corre con la paginación especial del +2A/+3 en la configuración
  "bancos 0,1,2,3": sus 64K de memoria del CPC quedan intactos.
* El HAL corre en la configuración "bancos 4,7,6,3": banco 7 = pantalla del
  Spectrum (sombra), banco 6 = código del HAL, banco 3 = pantalla del CPC
  (común a las dos configuraciones, así se puede convertir directamente).
* Una PUERTA (vectores RST + código de cambio de banco + tablas) vive en un
  hueco libre de la memoria baja del juego y, idéntica, en el banco 4. Los
  registros viajan por un BUZÓN de 48 bytes en el banco 3.
* Las llamadas al firmware funcionan sin tocar el código: el jumpblock de
  $BB00 se sustituye por entradas que cruzan al HAL.
* Las E/S directas (gate array, CRTC, PPI, PSG) se emulan instrucción a
  instrucción; las escrituras en la pantalla del CPC se reflejan al vuelo en la
  del Spectrum (vía rápida sin cruce completo) y un refresco de fondo hace el
  resto, incluidos los atributos de color.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..formats.cpc import FW_RGB, HW_RGB, HW_TO_FW
from ..formats.zx import ZXState
from ..machines.cpc import CPC_KEY_POS, CPC_KEYS, decode_byte
from ..machines.spectrum import ZX_KEYS, ZX_RGB
from ..z80 import decode as D
from ..z80.asm import Assembler
from .zx2cpc import Patch

HAL_SRC = os.path.join(os.path.dirname(__file__), "hal", "cpc2zx.asm")
PROLOGUE = "        ex (sp),hl\n        inc hl\n        ex (sp),hl\n"

# jumpblock: dirección -> (tipo, rutina). 'hal' = cruce (RST $30 + id);
# 'local' = JP a una rutina de la puerta (se ejecuta con la memoria del juego)
FIRMWARE = {
    0xBB06: ("local", "local_wait_char"), 0xBB09: ("local", "local_read_char"),
    0xBB18: ("local", "local_wait_char"), 0xBB1B: ("local", "local_read_char"),
    0xBB1E: ("hal", "fw_km_test_key"), 0xBB24: ("hal", "fw_km_get_joystick"),
    0xBB5A: ("hal", "fw_txt_output"), 0xBB5D: ("hal", "fw_txt_output"),
    0xBB6C: ("hal", "fw_scr_clear"), 0xBB75: ("hal", "fw_txt_set_cursor"),
    0xBB78: ("hal", "fw_txt_get_cursor"), 0xBB90: ("hal", "fw_txt_set_pen"),
    0xBB96: ("hal", "fw_txt_set_paper"), 0xBC0E: ("hal", "fw_scr_set_mode"),
    0xBC11: ("hal", "fw_scr_get_mode"), 0xBC14: ("hal", "fw_scr_clear"),
    0xBC32: ("hal", "fw_scr_set_ink"), 0xBC38: ("hal", "fw_scr_set_border"),
    0xBD19: ("local", "local_wait_flyback"), 0xBD1C: ("hal", "fw_mc_set_mode"),
    0xBCD7: ("hal", "fw_kl_new_frame_fly"), 0xBCE0: ("hal", "fw_kl_new_fast_ticker"),
    0xBCAA: ("local", "local_sound_queue"),
}
FIRMWARE_RET = {0xBB00, 0xBB03, 0xBB4E, 0xBBBA, 0xBBFF, 0xBC02, 0xBCA7, 0xBD37}
INTERNAL = {250: "h_isr", 251: "h_span", 252: "h_outbyte", 253: "h_sound", 254: "h_read_char",
            255: "h_mirror"}

DEFAULT_ZX2CPC = {
    "CAPS": ["SHIFT"], "SYM": ["CTRL"], "ENTER": ["RETURN", "ENTER"], "SPACE": ["SPACE"],
    "5": ["5", "CURLEFT"], "6": ["6", "CURDOWN"], "7": ["7", "CURUP"], "8": ["8", "CURRIGHT"],
    "0": ["0", "COPY"],
}
CPC_ASCII = {
    "SPACE": 32, "RETURN": 13, "ENTER": 13, "DEL": 127, "ESC": 27, ",": 44, ".": 46,
    "/": 47, ";": 59, ":": 58, "-": 45, "^": 94, "@": 64, "[": 91, "]": 93, "\\": 92,
}


@dataclass
class CPCPortOptions:
    refresh_lines: int = 4
    crop_x: int | None = None
    crop_y: int | None = None
    keys: dict = field(default_factory=dict)       # tecla ZX -> tecla(s) CPC extra
    exclude: set = field(default_factory=set)
    font: bytes | None = None                      # 768 bytes (32-127) de la ROM del CPC

    @classmethod
    def from_json(cls, d):
        o = cls()
        for k, v in d.items():
            if k == "exclude":
                v = {int(x, 16) if isinstance(x, str) else x for x in v}
            if k == "font":
                continue
            if hasattr(o, k):
                setattr(o, k, v)
        return o


@dataclass
class CPCPortResult:
    state: ZXState
    patches: list
    warnings: list
    hal_source: str
    hal_symbols: dict
    free_bytes: int
    palette: list = field(default_factory=list)


def _nearest_zx(rgb):
    return min(range(8), key=lambda c: sum((a - b) ** 2 for a, b in zip(ZX_RGB[c + 8], rgb)))


HW2ZX = [_nearest_zx(HW_RGB[h]) for h in range(32)]
FW2ZX = [_nearest_zx(FW_RGB[f]) for f in range(27)]


def _mirror_local(ins: D.Instr):
    """Código (en la puerta) que ejecuta ``ins`` y refleja lo escrito."""
    wk = ins.mem_write_kind()
    if wk is None:
        return None
    mode, det = wk
    body = "        " + ins.text() + "\n"
    if mode == "ind":
        if det == "HL":
            return body + "        jp fast_mirror\n"
        if det == "DE":
            return body + "        ex de,hl\n        call fast_mirror\n        ex de,hl\n        ret\n"
        return body + ("        push hl\n        ld h,b\n        ld l,c\n        call fast_mirror\n"
                       "        pop hl\n        ret\n")
    if mode == "idx":
        reg, d = det
        return body + (f"        push af\n        push hl\n        push de\n        push {reg}\n"
                       f"        pop hl\n        ld de,{d}\n        add hl,de\n"
                       "        call fast_mirror\n        pop de\n        pop hl\n        pop af\n"
                       "        ret\n")
    if mode == "abs":
        nn, width = det
        code = body + f"        push hl\n        ld hl,{nn}\n        call fast_mirror\n"
        if width == 2:
            code += "        inc hl\n        call fast_mirror\n"
        return code + "        pop hl\n        ret\n"
    if mode == "block":
        return {"LDIR": "        jp local_ldir\n", "LDDR": "        jp local_lddr\n",
                "LDI": "        jp local_ldi\n", "LDD": "        jp local_ldd\n"}[det]
    return None


def _in_c_handler(reg):
    set_reg = {
        "B": "        ld b,e\n", "C": "        ld c,e\n",
        "D": "        ld hl,3\n        add hl,sp\n        ld (hl),e\n",
        "E": "        ld hl,2\n        add hl,sp\n        ld (hl),e\n",
        "H": "        ld hl,1\n        add hl,sp\n        ld (hl),e\n",
        "L": "        ld hl,0\n        add hl,sp\n        ld (hl),e\n",
        "A": "        ld hl,5\n        add hl,sp\n        ld (hl),e\n",
        "F": "",
    }[reg]
    return ("        push af\n        push de\n        push hl\n        call cpc_in\n"
            "        ld e,a\n        or a\n        push af\n        pop hl\n        ld a,l\n"
            "        ld hl,4\n        add hl,sp\n        ld d,a\n        ld a,(hl)\n"
            "        and 1\n        or d\n        ld (hl),a\n" + set_reg +
            "        pop hl\n        pop de\n        pop af\n        ret\n")


class CPC2ZX:
    def __init__(self, analysis, options: CPCPortOptions | None = None):
        self.an = analysis
        self.p = analysis.program
        self.opt = options or CPCPortOptions()
        self.warnings = []
        self.patches = []
        self.hal_handlers = {}      # clave -> (etiqueta, código)
        self.hal_ids = {}           # etiqueta -> id (0..249)
        self.local_handlers = {}    # clave -> (etiqueta, código)
        self.local_ids = {}         # etiqueta -> id local
        self.hash_sites = {}        # dirección de retorno -> etiqueta local

    def _hal(self, key, code):
        if key not in self.hal_handlers:
            label = f"hh_{len(self.hal_handlers)}"
            self.hal_handlers[key] = (label, code)
            if len(self.hal_ids) >= 250:
                raise ValueError("demasiados manejadores del HAL")
            self.hal_ids[label] = len(self.hal_ids)
        return self.hal_handlers[key][0]

    def _local(self, key, code, with_id=True):
        if key not in self.local_handlers:
            label = f"hl_{len(self.local_handlers)}"
            self.local_handlers[key] = (label, code)
        label = self.local_handlers[key][0]
        if with_id and label not in self.local_ids:
            if len(self.local_ids) >= 255:
                raise ValueError("demasiados manejadores locales")
            self.local_ids[label] = len(self.local_ids)
        return label

    # -- memoria usada por el juego ------------------------------------------------------
    def _used_map(self):
        p, tr = self.p, self.an.trace
        used = bytearray(65536)
        for lo, hi in p.load_ranges:
            if not (lo == 0 and hi == 0x10000):
                for a in range(lo, min(hi, 0x10000)):
                    used[a] = 1
        if tr is not None:
            for a in range(65536):
                if tr.written[a]:
                    used[a] = 1
            lo = max(0, tr.sp_min - 64)
            for a in range(lo, min(0x10000, tr.sp_max + 2)):
                used[a] = 1
        for a, ins in self.an.instrs.items():
            for k in range(ins.length):
                used[(a + k) & 0xFFFF] = 1
        return used

    def _find_free(self, used, lo, hi, size, align=1, need_zero=False, avoid=()):
        mem = self.p.mem
        a = (lo + align - 1) // align * align
        while a + size <= hi:
            ok = True
            for b in range(a, a + size):
                if used[b] or (need_zero and mem[b]) or any(s <= b < e for s, e in avoid):
                    ok = False
                    break
            if ok:
                return a
            a += align
        return None

    def _screen_gaps(self, st):
        """Bytes de la página de pantalla que el CRTC no muestra."""
        crtc = st.crtc
        r1, r6 = crtc[1] or 40, crtc[6] or 25
        base = ((crtc[12] >> 4) & 3) * 0x4000
        start = ((((crtc[12] & 3) << 8) | crtc[13]) * 2) & 0x7FF
        shown = bytearray(0x800)
        for row in range(r6):
            for x in range(r1 * 2):
                shown[(start + row * r1 * 2 + x) & 0x7FF] = 1
        return base, [base + ln * 0x800 + o for ln in range(8) for o in range(0x800) if not shown[o]]

    # -- plan de parches -------------------------------------------------------------------
    def plan(self):
        an = self.an
        mem = self.p.mem
        kinds_at = {}
        for h in an.hotspots:
            kinds_at.setdefault(h.addr, []).append(h)
        taken = {}
        for addr in sorted(kinds_at):
            if addr in self.opt.exclude or addr < 0x40:
                continue
            if self.p.firmware and 0xB900 <= addr < 0xC000:
                continue
            ins = an.instrs[addr]
            kinds = {h.kind for h in kinds_at[addr]}
            patch = None
            try:
                if "halt" in kinds:
                    patch = Patch(addr, ins.raw, b"\xEF", "halt", ins.text(), "local_halt")
                elif kinds & {"ga_out", "crtc_out", "ppi_io", "io_unknown", "fdc_io"}:
                    patch = self._plan_io(ins, kinds)
                elif "screen_write" in kinds:
                    patch = self._plan_screen(ins)
                elif "im2" in kinds and ins.operands and ins.operands[0].value == 2:
                    self.warnings.append(f"{addr:04X} IM 2: el juego usa IM 2 (no soportado "
                                         "automáticamente)")
                elif "fw_rst" in kinds and ins.target not in (0x20,):
                    self.warnings.append(f"{addr:04X} {ins.text()}: RST del firmware no "
                                         "soportado (SIDE/FAR CALL, LOW/FIRM JUMP)")
            except ValueError as e:
                self.warnings.append(f"{addr:04X} {ins.text()}: {e}")
            if patch is None:
                continue
            rng = range(addr, addr + len(patch.orig))
            if any(b in taken for b in rng) or bytes(mem[addr:addr + len(patch.orig)]) != patch.orig:
                continue
            for b in rng:
                taken[b] = addr
            self.patches.append(patch)
        # instalación de la rutina de interrupción propia en $38
        if an.trace is not None:
            for pc, addrs in an.trace.low_writes.items():
                if not any(0x38 <= a <= 0x3A for a in addrs) or pc not in an.instrs:
                    continue
                ins = an.instrs[pc]
                wk = ins.mem_write_kind()
                if wk and wk[0] == "abs":
                    nn = wk[1][0]
                    self.patches.append(Patch(pc, ins.raw, bytes(ins.raw[:-2]) + b"@@", "isr",
                                              ins.text(), f"MB_GAMEISR+{nn - 0x38}",
                                              note="rutina de interrupción del juego"))
                else:
                    self.warnings.append(f"{pc:04X} {ins.text()}: instala su interrupción en $38 "
                                         "de forma indirecta; revisar a mano")
        for h in an.hotspots:
            if h.addr < 0x40 or (self.p.firmware and 0xB900 <= h.addr < 0xC000):
                continue                # código del propio firmware
            if h.kind == "fw_call":
                t = h.detail.get("target")
                if t not in FIRMWARE and t not in FIRMWARE_RET:
                    self.warnings.append(f"{h.addr:04X} {h.text}: {h.detail.get('name')} no "
                                         "emulado (vuelve sin hacer nada)")
            elif h.kind == "stack_screen":
                self.warnings.append(f"{h.addr:04X} {h.text}: volcado con PUSH a pantalla: "
                                     "solo lo verá el refresco de fondo")

    def _plan_io(self, ins, kinds):
        direction, form, val = ins.io_kind()
        if kinds <= {"fdc_io"}:
            self.warnings.append(f"{ins.addr:04X} {ins.text()}: acceso a la disquetera ignorado")
            label = self._hal(("ret",), "        ret\n")
            return Patch(ins.addr, ins.raw, bytes([0xF7, self.hal_ids[label]]), "io", ins.text(),
                         label)
        if form == "block":
            target = {"OUTI": "local_outi", "OTIR": "local_otir", "OUTD": "local_outd",
                      "OTDR": "local_otdr"}.get(ins.op)
            if target is None:
                self.warnings.append(f"{ins.addr:04X} {ins.text()}: E/S en bloque no soportada")
                return None
            label = self._local(("blk", ins.op), PROLOGUE + f"        jp {target}\n")
            return Patch(ins.addr, ins.raw, bytes([0xC7, self.local_ids[label]]), "io",
                         ins.text(), label)
        if form == "n":
            n = val
            if direction == "out":
                code = (f"        push bc\n        ld b,a\n        ld c,{n}\n        call cpc_out\n"
                        "        pop bc\n        ret\n")
            else:
                code = (f"        push bc\n        push af\n        ld b,a\n        ld c,{n}\n"
                        "        call cpc_in\n        ld b,a\n        pop af\n        ld a,b\n"
                        "        pop bc\n        ret\n")
            label = self._hal((direction + "_n", n), code)
        elif direction == "out":
            src = ins.operands[1]
            reg = "0" if src.kind == D.IMM8 else src.value
            load = "        xor a\n" if reg == "0" else ("" if reg == "A" else
                                                        f"        ld a,{reg.lower()}\n")
            label = self._hal(("out_c", reg), "        push af\n" + load +
                              "        call cpc_out\n        pop af\n        ret\n")
        else:
            reg = ins.operands[0].value
            label = self._hal(("in_c", reg), _in_c_handler(reg))
        return Patch(ins.addr, ins.raw, bytes([0xF7, self.hal_ids[label]]), "io", ins.text(), label)

    def _plan_screen(self, ins):
        wk = ins.mem_write_kind()
        if wk is None or wk[0] == "stack":
            return None
        code = _mirror_local(ins)
        if code is None:
            return None
        raw, n = ins.raw, ins.length
        if n == 1:
            if raw == b"\x77":
                return Patch(ins.addr, raw, b"\xD7", "screen", ins.text(), "fast_ld_hl_a")
            if raw == b"\x12":
                return Patch(ins.addr, raw, b"\xDF", "screen", ins.text(), "fast_ld_de_a")
            label = self._local(("s1", raw), code)
            self.hash_sites[(ins.addr + 1) & 0xFFFF] = label
            return Patch(ins.addr, raw, b"\xCF", "screen", ins.text(), label)
        if n == 2:
            label = self._local(("s2", raw), PROLOGUE + code)
            return Patch(ins.addr, raw, bytes([0xC7, self.local_ids[label]]), "screen", ins.text(),
                         label)
        label = self._local(("s3", raw), code, with_id=False)
        return Patch(ins.addr, raw, b"\xCD@@" + b"\x00" * (n - 3), "screen", ins.text(), label)

    # -- construcción ------------------------------------------------------------------------
    def build(self) -> CPCPortResult:
        p = self.p
        st = p.cpc_state or p.to_cpc_state()
        used = self._used_map()
        self.plan()
        # jumpblock del firmware
        jb = {}
        if p.firmware or any(h.kind == "fw_call" for h in self.an.hotspots):
            for addr in range(0xBB00, 0xBDF4, 3):
                kind, target = FIRMWARE.get(addr, (None, None))
                if kind == "local":
                    jb[addr] = ("jp", target)
                elif kind == "hal":
                    jb[addr] = ("rst", self._hal(("fw", target), f"        jp {target}\n"))
                elif addr in FIRMWARE_RET:
                    jb[addr] = ("rst", self._hal(("ret",), "        ret\n"))
                else:
                    jb[addr] = ("rst", self._hal(("fw_unsup",), "        jp fw_unsupported\n"))
        crtc = st.crtc
        mode = st.ga_rmr & 3
        r1, r6 = crtc[1] or 40, crtc[6] or 25
        crop_x = self.opt.crop_x if self.opt.crop_x is not None else max(0, (r1 * 2 - 64) // 2)
        crop_y = self.opt.crop_y if self.opt.crop_y is not None else max(0, (r6 * 8 - 192) // 2)
        crop_x &= ~1
        # buzón: un hueco de la pantalla del CPC que el juego no use
        base, gaps = self._screen_gaps(st)
        gapset = set(gaps)
        mb = None
        if base == 0xC000:
            for g in gaps:
                if all((g + k) in gapset and not used[g + k] for k in range(48)):
                    mb = g
                    break
        if mb is None:
            mb = self._find_free(used, 0xC000, 0x10000, 48, need_zero=True)
        if mb is None:
            raise ValueError("no encuentro 48 bytes libres en $C000-$FFFF para el buzón")
        font = 0x3C00
        syms = {"CROP_X": crop_x, "CROP_Y": crop_y,
                "REFRESH_LINES": max(1, min(16, self.opt.refresh_lines)), "INIT_MODE": mode,
                "INIT_R1": r1, "MB": mb, "FONT": font, "GATE": 0x0100,
                "NLOCAL": max(1, len(self.local_ids))}
        with open(HAL_SRC, encoding="utf-8") as f:
            base_src = f.read()
        # tamaño de la puerta (con los manejadores locales) para buscarle sitio
        src = self._compose(base_src)
        probe = Assembler(syms).assemble(src, "cpc2zx.asm")
        gate_size = probe.symbols["gate_gen_end"] - probe.symbols["gate_start"]
        gate = self._find_free(used, 0x0040, 0x3C00, gate_size, align=256)
        if gate is None:
            raise ValueError(f"no hay {gate_size} bytes libres (alineados) en $0040-$3BFF para "
                             "la puerta del HAL")
        syms["GATE"] = gate
        res = Assembler(syms).assemble(src, "cpc2zx.asm")
        sy = res.symbols
        return self._image(res, sy, syms, st, mode, crop_x, crop_y, jb, src, gate, gate_size)

    def _compose(self, base_src):
        out = [base_src, "\n; ---- manejadores locales (puerta) ----\n        org gate_gen\n"]
        for key, (label, code) in self.local_handlers.items():
            out.append(f"{label}:\n{code}")
        out.append("gate_gen_end:\n")
        out.append("\n; ---- manejadores del HAL ----\n        org hal_code_end\n")
        for key, (label, code) in self.hal_handlers.items():
            out.append(f"{label}:\n{code}")
        out.append("hal_gen_end:\n        assert hal_gen_end <= $BF00, \"el HAL no cabe\"\n")
        return "".join(out)

    def _image(self, res, sy, syms, st, mode, crop_x, crop_y, jb, src, gate, gate_size):
        p = self.p
        mem = bytearray(p.mem)
        banks = {b: bytearray(16384) for b in range(8)}
        hal = bytearray(65536)
        for s in res.segments:
            hal[s.org:s.org + len(s.data)] = s.data
        gate_lo, gate_hi = gate, gate + gate_size
        # vectores y puerta en los bancos 0 (juego) y 4 (HAL)
        for a in list(range(0, 0x40)) + list(range(gate_lo, gate_hi)):
            mem[a] = hal[a]
        # jumpblock
        for addr, (kind, target) in jb.items():
            if kind == "jp":
                t = sy[target]
                mem[addr:addr + 3] = bytes([0xC3, t & 0xFF, t >> 8])
            else:
                mem[addr:addr + 3] = bytes([0xF7, self.hal_ids[target], 0xC9])
        # parches
        for pt in self.patches:
            new = bytearray(pt.new)
            if b"@@" in new:
                i = new.index(b"@@")
                h = pt.handler
                off = 0
                if "+" in h:
                    h, o = h.split("+")
                    off = int(o)
                tgt = (sy[h] if h in sy else syms[h]) + off
                new[i:i + 2] = bytes([tgt & 0xFF, tgt >> 8])
            pt.new = bytes(new)
            mem[pt.addr:pt.addr + len(new)] = new
        # tablas de la puerta (en las dos copias)
        pal = [st.palette[i] & 31 for i in range(17)]
        pen_zx = [HW2ZX[h] for h in pal[:16]]
        nib, pres_lo, pres_hi = self._mode_tables(mode)
        r1 = st.crtc[1] or 40
        rowstart = [f * r1 * 2 for f in range(32)]
        rowtab = []
        for k in range(128):
            f = 0
            while f < 31 and rowstart[f + 1] <= k * 16:
                f += 1
            rowtab.append(f)
        g = sy["gate_nib"]
        gt = {}
        gt.update({g + i: nib[i] for i in range(256)})
        gt.update({sy["gate_rowtab"] + i: rowtab[i] for i in range(128)})
        for f, v in enumerate(rowstart):
            gt[sy["gate_rowstart"] + 2 * f] = v & 0xFF
            gt[sy["gate_rowstart"] + 2 * f + 1] = (v >> 8) & 0xFF
        for ret, label in self.hash_sites.items():
            idx = ((ret & 0xFF) ^ (ret >> 8)) & 31
            for k in range(32):
                j = (idx + k) & 31
                if gt.get(sy["gate_hash"] + 32 + j, 0) == 0:
                    gt[sy["gate_hash"] + j] = ret & 0xFF
                    gt[sy["gate_hash"] + 32 + j] = ret >> 8
                    gt[sy["gate_hash"] + 64 + j] = self.local_ids[label]
                    break
        for label, i in self.local_ids.items():
            a = sy[label]
            gt[sy["gate_ltab"] + 2 * i] = a & 0xFF
            gt[sy["gate_ltab"] + 2 * i + 1] = a >> 8
        for a, v in gt.items():
            mem[a] = v
            hal[a] = v
        # banco 4: vectores + puerta + fuente
        b4 = bytearray(16384)
        b4[0:0x40] = mem[0:0x40]
        b4[gate_lo:gate_hi] = mem[gate_lo:gate_hi]
        font = syms["FONT"]
        if self.opt.font:
            b4[font:font + 768] = self.opt.font[:768]
        else:
            self.warnings.append("sin la ROM del CPC no hay fuente: TXT OUTPUT no dibujará texto "
                                 "(usa --cpc-roms)")
        # banco 6: HAL + tablas
        b6 = bytearray(hal[0x8000:0xC000])
        b6[0x0000:0x0100] = nib
        b6[0x0100:0x0200] = bytes(((v << 4) & 0xFF) for v in nib)
        b6[0x0200:0x0300] = pres_lo
        b6[0x0300:0x0400] = pres_hi
        for i in range(256):
            m1 = m2 = 0
            for k in range(8):
                if i >> k & 1:
                    m1 |= 1 << pen_zx[k]
                    m2 |= 1 << pen_zx[8 + k]
            b6[0x0400 + i] = m1
            b6[0x0500 + i] = m2
        prio = [6, 5, 4, 7, 2, 3, 1, 0]
        for mask in range(256):
            b6[0x0A00 + mask] = next((k for k in prio if mask >> k & 1), 7)
        ids = dict(self.hal_ids)
        for i, lab in INTERNAL.items():
            ids[lab] = i
        for lab, i in ids.items():
            a = sy[lab]
            b6[0x0600 + i] = a & 0xFF
            b6[0x0700 + i] = a >> 8
        b6[0x0800:0x0880] = bytes(rowtab)
        for f, v in enumerate(rowstart):
            b6[0x0880 + 2 * f] = v & 0xFF
            b6[0x0881 + 2 * f] = (v >> 8) & 0xFF

        def put6(label, data):
            a = sy[label] - 0x8000
            b6[a:a + len(data)] = bytes(data)
        put6("pen_zx", pen_zx)
        put6("hw2zx", HW2ZX)
        put6("fw2zx", FW2ZX)
        put6("crtc_r1", [r1])
        put6("crtc_r12", [st.crtc[12]])
        put6("crtc_r13", [st.crtc[13]])
        put6("row_len", [r1 * 2])
        put6("key_ascii", self._key_ascii())
        put6("zx2cpc", self._zx2cpc())
        # buzón inicial
        mbase = syms["MB"]
        scrhi = (st.crtc[12] >> 4 & 3) * 0x40
        start = ((((st.crtc[12] & 3) << 8) | st.crtc[13]) * 2) & 0x7FF
        mem[mbase:mbase + 48] = bytes(48)
        mem[mbase + 21] = scrhi
        mem[mbase + 22] = start & 0xFF
        mem[mbase + 23] = start >> 8
        mem[mbase + 24] = 1
        mem[mbase + 25] = 0xC9                  # sin rutina de interrupción propia
        # pantalla del Spectrum inicial
        zx_scr = self._convert_screen(mem, st, mode, pen_zx, crop_x, crop_y)
        b7 = bytearray(16384)
        b7[0:6912] = zx_scr
        banks[0][:] = mem[0x0000:0x4000]
        banks[1][:] = mem[0x4000:0x8000]
        banks[2][:] = mem[0x8000:0xC000]
        banks[3][:] = mem[0xC000:0x10000]
        banks[4][:] = b4
        banks[6][:] = b6
        banks[7][:] = b7
        regs = dict(st.regs) if st.regs else dict(p.regs)
        zx = ZXState(bytearray(49152), regs, p.iff1, p.iff2, 1, HW2ZX[pal[16]])
        zx.model = "+3"
        zx.banks = banks
        zx.port_7ffd = 0x08 | 0x10
        zx.port_1ffd = 0x01
        header = "; Símbolos fijados por el portador\n" + "".join(
            f"{k:<16}equ {v}\n" for k, v in syms.items()) + "\n"
        free = 0xBF00 - sy["hal_gen_end"]
        palette = [(i, HW_TO_FW[pal[i]], f"pluma {i} -> color ZX {pen_zx[i]}") for i in range(4)]
        self.warnings.insert(0, f"puerta en {gate:#06x}-{gate + gate_size - 1:#06x}, buzón en "
                             f"{mbase:#06x}")
        return CPCPortResult(zx, self.patches, self.warnings, header + src, sy, free, palette)

    def _mode_tables(self, mode):
        nib, lo, hi = bytearray(256), bytearray(256), bytearray(256)
        for b in range(256):
            pens = decode_byte(b, mode)
            if mode == 0:
                bits = [pn != 0 for pn in pens for _ in (0, 1)]
            elif mode == 2:
                bits = [pens[k] != 0 for k in (0, 2, 4, 6)]
            else:
                bits = [pn != 0 for pn in pens]
            v = 0
            for k, on in enumerate(bits):
                if on:
                    v |= 8 >> k
            nib[b] = v
            for pn in set(pens):
                if pn and pn < 8:
                    lo[b] |= 1 << pn
                elif pn >= 8:
                    hi[b] |= 1 << (pn - 8)
        return nib, lo, hi

    def _key_ascii(self):
        ka = bytearray(80)
        for line, row in enumerate(CPC_KEYS):
            for bit, name in enumerate(row):
                if len(name) == 1:
                    ka[line * 8 + bit] = ord(name.lower()) if name.isalpha() else ord(name)
                elif name in CPC_ASCII:
                    ka[line * 8 + bit] = CPC_ASCII[name]
        return ka

    def _zx2cpc(self):
        out = bytearray()
        extra = {}
        for zk, ck in (self.opt.keys or {}).items():
            extra[zk.upper()] = [c.upper() for c in (ck if isinstance(ck, list) else [ck])]
        for r in range(8):
            for b in range(5):
                zk = ZX_KEYS[r][b]
                keys = list(DEFAULT_ZX2CPC.get(zk, [zk]))
                if zk in extra:
                    keys = (keys[:1] + extra[zk])[:2]
                codes = [CPC_KEY_POS[k][0] * 8 + CPC_KEY_POS[k][1] for k in keys
                         if k in CPC_KEY_POS]
                out += bytes((codes + [0xFF, 0xFF])[:2])
        return out

    def _convert_screen(self, mem, st, mode, pen_zx, crop_x, crop_y):
        crtc = st.crtc
        r1 = crtc[1] or 40
        base = ((crtc[12] >> 4) & 3) * 0x4000
        start = ((((crtc[12] & 3) << 8) | crtc[13]) * 2) & 0x7FF
        out = bytearray(6912)
        paper = pen_zx[0]
        cells = [[set() for _ in range(32)] for _ in range(24)]
        for y in range(192):
            yc = y + crop_y
            line_off = (start + (yc >> 3) * r1 * 2) & 0x7FF
            laddr = base + ((yc & 7) << 11)
            zaddr = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
            for xb in range(32):
                bits = []
                for k in range(2):
                    a = laddr + ((line_off + crop_x + xb * 2 + k) & 0x7FF)
                    pens = decode_byte(mem[a], mode)
                    if mode == 0:
                        px = [pn for pn in pens for _ in (0, 1)]
                    elif mode == 2:
                        px = [pens[i] for i in (0, 2, 4, 6)]
                    else:
                        px = pens
                    bits += px
                    for pn in px:
                        if pn:
                            cells[y >> 3][xb].add(pen_zx[pn])
                v = 0
                for pn in bits:
                    v = (v << 1) | (1 if pn else 0)
                out[zaddr + xb] = v
        prio = [6, 5, 4, 7, 2, 3, 1, 0]
        for r in range(24):
            for c in range(32):
                cols = cells[r][c] - {paper}
                ink = next((k for k in prio if k in cols), 7)
                out[0x1800 + r * 32 + c] = 0x40 | (paper << 3) | ink
        return out


def port_cpc_to_zx(analysis, options=None) -> CPCPortResult:
    return CPC2ZX(analysis, options).build()
