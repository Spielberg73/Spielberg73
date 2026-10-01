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
    beeper_loops: bool = True             # copiar al HAL los bucles de beeper (tono fiel)
    frameskip: int = 0                    # volcados LDIR a pantalla saltados entre dos reales
    ram512: bool = False                  # 128K que paginan: CPC 6128 con ampliación de 512K

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
        self.fast_sites = {"HL": [], "DE": []}
        self.z128 = False
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

    # -- bucles de beeper ----------------------------------------------------------------
    def _plan_beeper_loops(self):
        """Bucles pequeños con OUT ($FE),A (motores de sonido del beeper): se copian al HAL
        con el OUT cambiado por una espera de la misma duración (JR $+2) y una escritura
        en el PSG solo cuando cambia A. Así la nota conserva su tono y su duración."""
        an = self.an
        executed = an.trace.executed if an.trace is not None else set()
        smc_targets = set()
        for h in an.hotspots:
            if h.kind == "smc":
                smc_targets |= set(h.detail.get("modifies", []))
        kinds_at = {}
        for h in an.hotspots:
            kinds_at.setdefault(h.addr, set()).add(h.kind)
        branches = [i for i in an.instrs.values()
                    if i.flow in ("jr", "djnz", "jp") and i.target is not None]
        done = []
        for x in sorted(a for a, k in kinds_at.items() if "ula_out" in k):
            ins = an.instrs.get(x)
            if ins is None or ins.raw != b"\xD3\xFE" or x not in executed or \
                    any(s <= x < e for s, e in done):
                continue
            back = [b for b in branches if x < b.addr <= x + 96 and b.target <= x
                    and x - b.target <= 96]
            # del bucle más externo al más interno, el primero que se pueda copiar
            found = None
            for last in sorted(back, key=lambda b: (b.addr - b.target), reverse=True):
                t0, end = last.target, last.addr + last.length
                body = self._loop_body(t0, end, kinds_at, smc_targets)
                if body is None or end - t0 < 3:
                    continue
                if all(not (t0 < b.target < end) or t0 <= b.addr < end for b in branches):
                    found = (t0, end, body)
                    break
            if found is None:
                found = self._beeper_routine(x, kinds_at, smc_targets, branches)
            if found is None:
                continue
            t0, end, body = found
            self._handler(("beeploop", t0), self._loop_src(body, t0, end), "call")
            label = self.handlers[("beeploop", t0)][0]
            mem = self.p.mem
            self.patches.append(Patch(t0, bytes(mem[t0:t0 + 3]), b"\xC3@@", "beeper_loop",
                                      f"bucle de beeper {t0:04X}-{end - 1:04X}", label,
                                      note="copiado al HAL con el OUT sustituido"))
            done.append((t0, end))
        return done

    def _beeper_routine(self, x, kinds_at, smc_targets, branches):
        """Subrutina corta sin llamadas (destino de CALL) que contiene el OUT y acaba en RET."""
        an = self.an
        entries = sorted({i.target for i in an.instrs.values() if i.flow == "call"
                          and i.target is not None and x - 64 <= i.target <= x}, reverse=True)
        for t0 in entries:
            a, end = t0, None
            while a < t0 + 96:
                ins = an.instrs.get(a)
                if ins is None:
                    break
                if ins.flow == "ret" and ins.cond is None:
                    end = a + ins.length
                    break
                a += ins.length
            if end is None or end <= x:
                continue
            body = self._loop_body(t0, end, kinds_at, smc_targets, allow_ret=True)
            if body is None:
                continue
            if all(not (t0 < b.target < end) or t0 <= b.addr < end for b in branches):
                return t0, end, body
        return None

    def _loop_body(self, t0, end, kinds_at, smc_targets, allow_ret=False):
        an = self.an
        body = []
        a = t0
        while a < end:
            ins = an.instrs.get(a)
            if ins is None or a in smc_targets:
                return None
            bad = ("call", "rst", "reti", "retn", "jpind", "halt") + (() if allow_ret else ("ret",))
            if ins.flow in bad:
                return None
            k = kinds_at.get(a, set())
            if k and not (k <= {"ula_out"} and ins.raw == b"\xD3\xFE"):
                return None
            if any((a + j) in smc_targets for j in range(ins.length)):
                return None
            body.append(ins)
            a += ins.length
        return body if a == end else None

    def _loop_src(self, body, t0, end):
        targets = {b.target for b in body if b.target is not None and t0 <= b.target < end}
        # borde que el juego deja en los OUT del bucle (si siempre es el mismo)
        tr = self.an.trace
        borders = set()
        for ins in body:
            if ins.raw == b"\xD3\xFE" and tr is not None:
                for (d, port), _n in tr.io.get(ins.addr, {}).items():
                    borders.add((port >> 8) & 7)
        border = borders.pop() if len(borders) == 1 else None
        labels = {t: f".L{t:04X}" for t in targets}
        # si el primer OUT llega antes de que se cambie A, emitir el estado al entrar
        first = next((i for i in body if i.raw == b"\xD3\xFE" or _writes_a(i)), None)
        out = ["        call ula_out            ; estado del altavoz al entrar\n"] \
            if first is not None and first.raw == b"\xD3\xFE" else []
        n = 0
        for ins in body:
            if ins.addr in labels:
                out.append(f"{labels[ins.addr]}:\n")
            if ins.raw == b"\xD3\xFE":
                out.append("        jr $+2                  ; OUT ($FE),A: misma duración\n")
                continue
            if ins.flow in ("jr", "djnz", "jp") and ins.target is not None:
                inside = ins.target in labels
                if ins.flow == "djnz":
                    if inside:
                        out.append(f"        djnz {labels[ins.target]}\n")
                    else:
                        out.append(f"        djnz .x{n}\n        jr .y{n}\n.x{n}:   jp {ins.target}\n.y{n}:\n")
                        n += 1
                    continue
                cond = f"{ins.cond.lower()}," if ins.cond else ""
                if inside:
                    op = "jr" if ins.flow == "jr" else "jp"
                    out.append(f"        {op} {cond}{labels[ins.target]}\n")
                else:
                    out.append(f"        jp {cond}{ins.target}\n")
                continue
            out.append("        " + _asm_ins(ins).strip() + "\n")
            if _writes_a(ins):
                k = _const_a(ins)
                if k is not None and border is not None and (k & 7) == border:
                    # valor conocido y borde sin cambios: solo el volumen del PSG, en línea
                    vol = self.opt.beep_vol if k & 0x10 else 0
                    out.append(f"        ld (last_ula),a\n        push bc\n        ld bc,${0xF400 | vol:04X}\n"
                               "        out (c),c\n        ld bc,$F680\n        out (c),c\n"
                               "        ld c,0\n        out (c),c\n        pop bc\n")
                else:
                    out.append("        call ula_out\n")
        out.append(f"        jp {end}\n")
        return "".join(out)

    def _z128_memory(self, mem, xm, pm):
        """576K: base (pantalla A + HAL, banco 5, banco 2, pantalla B) y el banco n del
        Spectrum en el bloque 3 del banco n de 64K de la ampliación."""
        banks = self.p.zx_state.banks
        out = bytearray(mem) + bytearray(8 * 0x10000)
        b7 = bytes(banks[7])
        out[0xC000:0x10000] = convert_screen_to_cpc(b7 + bytes(0xC000 - len(b7)), xm, pm)
        for n in range(8):
            if n == 5:
                data = mem[0x4000:0x8000]          # ya parcheados
            elif n == 2:
                data = mem[0x8000:0xC000]
            else:
                data = banks[n]
            off = 0x10000 + n * 0x10000 + 0xC000
            out[off:off + 0x4000] = data
        tr = self.an.trace
        if tr is not None and tr.sp_max >= 0xC000:
            self.warnings.append("la pila del juego llega a $C000-$FFFF: al cambiar de banco "
                                 "en el CPC se perdería; revisar")
        return out

    def _frameskip_ok(self):
        if not self.opt.frameskip:
            return False
        if getattr(self, "_fs_checked", None) is None:
            tr = self.an.trace
            # las lecturas de los propios LDIR de pantalla a pantalla (borrados con
            # LD (HL),0 + LDIR) no cuentan: esos sitios nunca se saltan
            blocks = {a for a, i in self.an.instrs.items()
                      if i.op in ("LDIR", "LDDR", "LDI", "LDD")}
            reads = sum(n for pc, n in tr.screen_reads.items() if pc not in blocks) \
                if tr is not None else None
            self._fs_checked = bool(reads == 0)
            if reads is None:
                self.warnings.append("--frameskip necesita el análisis dinámico: no se aplica")
            elif reads:
                pcs = ", ".join(f"{pc:04X}" for pc in tr.screen_reads if pc not in blocks)
                self.warnings.append(f"--frameskip no se aplica: el juego lee la pantalla "
                                     f"({pcs})")
            else:
                self.warnings.append(f"salto de frames: la pantalla se actualiza en 1 de cada "
                                     f"{self.opt.frameskip + 1} volcados")
        return self._fs_checked

    def _hal_features(self):
        """Partes opcionales del HAL que este juego necesita (lo demás no se ensambla y
        deja sitio para los manejadores)."""
        used = {pt.handler for pt in self.patches}
        for _label, code, _t in self.handlers.values():
            used |= set(code.replace(",", " ").split())
        top = 0xC000 if self.z128 else 0x10000      # 128K: lo paginado puede ser datos
        rst10 = any(i.flow == "rst" and i.target == 0x10 and 0x4000 <= a < top
                    for a, i in self.an.instrs.items())
        ay = any(h.kind == "ay_io" for h in self.an.hotspots)
        return {"USE_PRINT": int(rst10 or bool(used & {"h_print", "rom_pr_string",
                                                       "rom_chan_open"})),
                "USE_CLS": int(bool(used & {"rom_cls", "rom_cls_lower"})),
                "USE_BEEPER": int("rom_beeper" in used),
                "USE_KEYSCAN": int("rom_key_scan" in used),
                "USE_AY": int(ay),
                # LAST_K de la ROM: solo si el juego puede estar en IM 1
                "USE_LASTK": int(self.p.im != 2 or any(
                    i.op == "IM" and i.operands and i.operands[0].value != 2
                    for a, i in self.an.instrs.items() if a < top))}

    def _romprot(self):
        """¿Proteger $0000-$3FFF? Si el análisis vio al juego escribir en la ROM, y siempre
        en el modo 128K (los juegos grandes recortan sprites así y puede no verse)."""
        tr = self.an.trace
        return bool(self.z128 or (tr is not None and getattr(tr, "rom_writes", None)))

    def _same_rate(self, pc):
        """Fracción de las escrituras en pantalla de ``pc`` que no cambiaron el byte."""
        tr = self.an.trace
        if tr is None:
            return 0.0
        n = sum(tr.screen_writes.get(pc, {}).values())
        return tr.screen_same.get(pc, 0) / n if n else 0.0

    def _skip_same(self, reg):
        """¿Compensa comprobar el valor en RST $20/$18? Sí si, sumando todos sus sitios,
        al menos un 30 % de las escrituras repiten el byte."""
        tr = self.an.trace
        if tr is None:
            return 0
        tot = same = 0
        for pc in self.fast_sites[reg]:
            tot += sum(tr.screen_writes.get(pc, {}).values())
            same += tr.screen_same.get(pc, 0)
        return 1 if tot and same / tot >= 0.3 else 0

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
        loops = self._plan_beeper_loops() if self.opt.beeper_loops else []
        for t0, end in loops:
            for b in range(t0, end):
                taken[b] = t0
        for addr in sorted(kinds_at):
            if addr in self.opt.exclude or any(t0 <= addr < end for t0, end in loops):
                continue
            if self.z128 and addr >= 0xC000:
                continue        # código paginado: cambia con el banco, no se parchea
            ins = an.instrs[addr]
            hs = kinds_at[addr]
            confident = addr in executed or self.opt.patch_static
            patch = None
            kinds = {h.kind for h in hs}
            try:
                if "halt" in kinds:
                    # HALT va por la tabla hash (RST $08); RST $28 es OUT ($FE),A
                    label = self._handler(("halt8",), "        jp h_halt\n", "rst8")
                    self._id(label)
                    self.hash_sites[(addr + 1) & 0xFFFF] = label
                    patch = Patch(addr, ins.raw, b"\xCF", "halt", ins.text(), label)
                elif kinds & {"ula_out", "ula_in", "kempston_in", "ay_io", "floating_bus",
                              "paging", "io_unknown"}:
                    if confident:
                        patch = self._plan_io(ins, hs)
                elif kinds & {"im2", "ld_i"}:
                    patch = self._plan_int(ins)
                elif "rom_call" in kinds:
                    if executed and addr not in executed:
                        # solo visto en el análisis estático: puede ser un dato que parece
                        # código; parchearlo podría estropear el juego
                        self.warnings.append(f"{addr:04X} {ins.text()}: posible llamada a la "
                                             "ROM no ejecutada en el análisis: no se parchea")
                    else:
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
                src = self._runtime_code_source(addr, len(patch.orig))
                if src is None:
                    self.warnings.append(f"{addr:04X}: los bytes no coinciden, omitido")
                    continue
                # código copiado en ejecución: se parchea su origen (la copia llega parcheada)
                patch.note = (patch.note + "; " if patch.note else "") + \
                    f"código generado en {addr:04X}: parcheado en su origen {src:04X}"
                patch.addr = src
                rng = range(src, src + len(patch.orig))
                if any(b in taken for b in rng):
                    continue
            for b in rng:
                taken[b] = addr
            self.patches.append(patch)
        self._plan_smc_writers(taken)
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
                if val & 1 and self.z128 and val == 0xFD:
                    # 128K: el puerto completo es A*256+$FD (AY o paginación)
                    label = self._handler(("out_fd",), (
                        "        push af\n        push bc\n        push hl\n        ld b,a\n"
                        "        ld c,$FD\n        call out_c_value\n        pop hl\n"
                        "        pop bc\n        pop af\n        ret\n"), "rst30")
                elif val & 1:
                    label = self._handler(("out_ignore",), "        ret\n", "rst30")
                elif val == 0xFE and ins.raw == b"\xD3\xFE":
                    # vía rápida: RST $28 + $FE (el byte del puerto se queda y se salta)
                    return Patch(ins.addr, ins.raw, b"\xEF\xFE", "io", ins.text(), "ula_out")
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
            if "paging" in kinds and not self.z128:
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
        same = self._same_rate(ins.addr)
        chk = _same_check(ins) if same >= 0.5 else None
        skip = chk is not None and wk[0] == "ind"
        if skip:
            # la mayoría de escrituras repiten el valor: comprobar antes y no convertir
            body = chk + _asm_ins(ins) + post + ".same:  pop af\n        ret\n"
        if self._romprot() and wk[0] == "block" and wk[1] in ("LDI", "LDD"):
            # destino por debajo de $4000 (ROM en el Spectrum): LDI/LDD contra un byte de
            # descarte, para que HL, DE, BC y los flags queden igual sin escribir nada
            step = "inc de" if wk[1] == "LDI" else "dec de"
            body = ("        push af\n        ld a,d\n        cp $40\n        jr c,.rom\n"
                    "        pop af\n" + body +
                    f".rom:   pop af\n        push de\n        ld de,rom_scratch\n"
                    f"        {wk[1].lower()}\n        pop de\n        {step}\n        ret\n")
            skip = (skip, "rom")
        if self._romprot() and wk[0] == "ind" and wk[1] in ("HL", "DE", "BC"):
            # el juego escribe a veces en $0000-$3FFF (ROM en el Spectrum): ignorarlo
            hi = {"HL": "h", "DE": "d", "BC": "b"}[wk[1]]
            body = (f"        push af\n        ld a,{hi}\n        cp $40\n        jr c,.rom\n"
                    "        pop af\n" + body + ".rom:   pop af\n        ret\n")
            skip = (skip, "rom")
        if wk == ("block", "LDIR"):
            # copia comparando: solo se convierten los bytes que cambian (los juegos que
            # vuelcan un búfer entero en cada frame cambian muy pocos)
            self._handler(("ldir_scr",), LDIR_SCR_SRC, "call")
            self._handler(("ldir_scr2",), LDIR_SCR2_SRC, "call")
            body = "        jp ldir_scr\n"
            tr = self.an.trace
            if self._frameskip_ok() and not tr.screen_reads.get(ins.addr) and \
                    tr.block_starts.get(ins.addr, 0) >= 20:
                # salto de frames: solo una de cada N+1 copias llega a la pantalla
                n = self.opt.frameskip
                body = ("        push af\n        ld a,(.cnt)\n        inc a\n"
                        f"        cp {n + 1}\n        jr c,.k\n        xor a\n"
                        ".k:     ld (.cnt),a\n        jr z,.go\n        pop af\n"
                        "        jp ldir_skip\n.go:    pop af\n        jp ldir_scr\n"
                        f".cnt:   db {n}\n")              # el primer volcado es real
                key_extra = ("fs", ins.addr)
            else:
                key_extra = None
        n = ins.length
        raw = ins.raw
        if n == 1:
            if raw == b"\x77":
                self.fast_sites["HL"].append(ins.addr)
                return Patch(ins.addr, raw, b"\xE7", "screen", ins.text(), "mirror_hl")
            if raw == b"\x12":
                self.fast_sites["DE"].append(ins.addr)
                return Patch(ins.addr, raw, b"\xDF", "screen", ins.text(), "mirror_de")
            label = self._handler(("scr8", raw, skip), body, "rst8")
            self._id(label)
            self.hash_sites[(ins.addr + 1) & 0xFFFF] = label
            return Patch(ins.addr, raw, b"\xCF", "screen", ins.text(), label)
        if wk != ("block", "LDIR"):
            key_extra = None
        if n == 2:
            label = self._handler(("scr30", raw, skip, key_extra), body, "rst30")
            return Patch(ins.addr, raw, bytes([0xF7, self._id(label)]), "screen", ins.text(), label)
        label = self._handler(("scrcall", raw, skip), body, "call")
        return Patch(ins.addr, raw, b"\xCD@@" + b"\x00" * (n - 3), "screen", ins.text(), label)

    def _runtime_code_source(self, addr, n):
        """Código que no está en la imagen inicial (lo copia el juego al ejecutarse):
        busca sus bytes, tal como se ejecutaron, en la imagen inicial. Devuelve la
        dirección de origen equivalente a ``addr`` si aparece una sola vez."""
        tr = self.an.trace
        if tr is None or not getattr(tr, "first_bytes", None):
            return None
        known = {}
        for pc in range(addr - 16, addr + 20):
            fb = tr.first_bytes.get(pc & 0xFFFF)
            if fb is not None:
                buf = bytearray(65536)
                buf[0:4] = fb
                ln = D.decode(buf, 0).length    # solo los bytes de la instrucción ejecutada
                for k, b in enumerate(fb[:ln]):
                    known.setdefault((pc + k) & 0xFFFF, b)
        if any((addr + k) & 0xFFFF not in known for k in range(n)):
            return None
        lo = addr
        while (lo - 1) & 0xFFFF in known and addr - lo < 16:
            lo -= 1
        hi = addr + n
        while hi & 0xFFFF in known and hi - addr < 20:
            hi += 1
        if hi - lo < 8:
            return None                     # demasiado poco para identificarlo
        pat = bytes(known[a & 0xFFFF] for a in range(lo, hi))
        mem = self.p.mem
        top = 0xC000 if self.z128 else 0x10000
        hits = []
        i = bytes(mem[0x4000:top]).find(pat)
        while i >= 0 and len(hits) < 2:
            hits.append(0x4000 + i)
            i = bytes(mem[0x4000:top]).find(pat, i + 1)
        if len(hits) != 1 or hits[0] == lo:
            return None
        return hits[0] + (addr - lo)

    def _plan_smc_writers(self, taken):
        """Código automodificable que escribe opcodes de escritura en pantalla (p.ej. una
        rutina de sprites de ancho variable que pone LD (HL),A o NOP en cada columna):
        el escritor pasa a escribir el opcode parcheado (RST $20 / RST $18), que hace lo
        mismo y además refleja en la pantalla del CPC."""
        tr = self.an.trace
        if tr is None:
            return
        trans = {0x77: 0xE7, 0x12: 0xDF}
        for pc, targets in tr.smc.items():
            ins = self.an.instrs.get(pc)
            if ins is None or pc in taken:
                continue
            if not any(t in tr.screen_writes or t in taken for t in targets):
                continue                    # no toca código que escriba en pantalla
            if ins.op != "LD" or len(ins.operands) != 2 or ins.operands[1].kind != D.REG \
                    or ins.operands[1].value != "A":
                self.warnings.append(f"{pc:04X} {ins.text()}: modifica código de escritura "
                                     "en pantalla de una forma no soportada; revisar a mano")
                continue
            dst = ins.operands[0]
            useful = sorted(t for t in targets if t in tr.screen_writes or t in taken)
            tab = "".join(f"        dw {t}\n" for t in useful)
            if dst.kind == D.IND_REG and dst.value in ("DE", "HL", "BC"):
                addr = {"DE": "        ld h,d\n        ld l,e\n", "HL": "",
                        "BC": "        ld h,b\n        ld l,c\n"}[dst.value]
            elif dst.kind == D.IND_IMM:
                addr = f"        ld hl,{dst.value}\n"
            else:
                continue
            self._handler(("smc_tr",), SMC_TR_SRC, "call")
            code = ("        push af\n        push hl\n        push de\n        push bc\n"
                    + addr + "        ld de,.tab\n        jp smc_tr\n.tab:\n" + tab +
                    "        dw 0\n")
            n = ins.length
            if n == 1:
                label = self._handler(("smcw", pc), code, "rst8")
                self._id(label)
                self.hash_sites[(pc + 1) & 0xFFFF] = label
                new = b"\xCF"
            elif n == 3:
                label = self._handler(("smcw", pc), code, "call")
                new = b"\xCD@@"
            else:
                continue
            for b in range(pc, pc + n):
                taken[b] = pc
            self.patches.append(Patch(pc, ins.raw, new, "smc", ins.text(), label,
                                      note="traduce LD (HL),A/LD (DE),A a su versión parcheada"))
            self._smc_fixed = getattr(self, "_smc_fixed", set()) | {pc}

    def _report_unhandled(self):
        an = self.an
        for h in an.hotspots:
            if h.kind == "stack_screen":
                self.warnings.append(f"{h.addr:04X} {h.text}: volcado con PUSH a pantalla: "
                                     "solo lo verá el refresco de fondo")
            elif h.kind == "rom_read":
                pages = ", ".join(f"{p:#06x}" for p in h.detail.get("pages", [])[:4])
                self.warnings.append(f"{h.addr:04X} {h.text}: lee datos de la ROM ({pages})")
            elif h.kind == "smc" and h.addr not in getattr(self, "_smc_fixed", set()):
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
        if not refs and chars != 0x3C00:
            # el juego calcula la dirección en la ROM por su cuenta: leerla del banco extra
            if self._rom_reads_via_bank():
                return
        where = self._find_free(mem, 768)
        if where is None:
            if self._rom_reads_via_bank():
                return
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

    def _rom_reads_via_bank(self):
        """Las instrucciones que leen la ROM pasan a leer una copia en el banco extra 5
        del CPC 6128 (configuración $C5, que lo pone en $4000-$7FFF)."""
        patched = {b for pt in self.patches for b in range(pt.addr, pt.addr + len(pt.orig))}
        done = 0
        for h in self.an.hotspots:
            if h.kind != "rom_read" or h.addr in patched:
                continue
            ins = self.an.instrs.get(h.addr)
            body = _rom_read_body(ins) if ins is not None else None
            if body is None:
                self.warnings.append(f"{h.addr:04X} {h.text}: lectura de la ROM en una forma "
                                     "no soportada; revisar a mano")
                continue
            fused = self._fuse_rom_read(ins, body) if ins.length == 1 else None
            if fused is not None:
                done += 1
                continue
            if ins.length == 1:
                label = self._handler(("romrd", ins.raw), body, "rst8")
                self._id(label)
                self.hash_sites[(ins.addr + 1) & 0xFFFF] = label
                new = b"\xCF"
            elif ins.length >= 3:
                label = self._handler(("romrd", ins.raw), body, "call")
                new = b"\xCD@@" + b"\x00" * (ins.length - 3)
            else:
                label = self._handler(("romrd", ins.raw), body, "rst30")
                new = bytes([0xF7, self._id(label)])
            self.patches.append(Patch(ins.addr, ins.raw, new, "rom_read", ins.text(), label,
                                      note="lee la copia de la ROM del banco extra 5"))
            done += 1
        if not done:
            return False
        self._handler(("rom_peek",), ROM_PEEK_SRC, "call")
        self.rom_bank = bytes(self.opt.zx_rom[:16384])
        self.warnings.append(f"{done} lectura(s) de la ROM leen una copia en el banco extra 5: "
                             "el port necesita un CPC 6128 (o 464/664 con 64K de ampliación)")
        return True

    def _fuse_rom_read(self, ins, body):
        """LD r,(rr) de la ROM seguido de LD (HL),A / LD (DE),A a pantalla (el bucle típico
        que imprime con la fuente de la ROM): un solo manejador de 2 bytes en vez de la
        búsqueda en la tabla hash más el RST de la escritura."""
        nxt = (ins.addr + 1) & 0xFFFF
        pt = next((q for q in self.patches if q.addr == nxt), None)
        if pt is None or pt.kind != "screen" or pt.orig not in (b"\x77", b"\x12"):
            return None
        if any(i.target == nxt for i in self.an.instrs.values() if i.target is not None):
            return None
        rd = self._handler(("romrd", ins.raw), body, "call")
        if self._same_rate(nxt) >= 0.5:      # la escritura suele repetir el valor
            vec = "st_hl_a" if pt.orig == b"\x77" else "st_de_a"
        else:
            vec = "$0020" if pt.orig == b"\x77" else "$0018"
        label = self._handler(("romrd_fused", ins.raw, pt.orig),
                              f"        call {rd}\n        jp {vec}\n", "rst30")
        self.patches.remove(pt)
        for lst in self.fast_sites.values():
            if nxt in lst:
                lst.remove(nxt)
        self.patches.append(Patch(ins.addr, ins.raw + pt.orig, bytes([0xF7, self._id(label)]),
                                  "rom_read", f"{ins.text()} / {pt.text}", label,
                                  note="lee la copia de la ROM del banco extra 5 y escribe"))
        return label

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
        top = 0xBFFF if self.z128 else 0xFFFF
        for a in range(top, 0x5CFF, -1):
            ok = mem[a] == 0 and not code[a] and not (lo_sp <= a <= hi_sp) and \
                (tr is None or not (tr.written[a] or tr.written_block[a]))
            run = run + 1 if ok else 0
            if run == size:
                return a
        return None

    # -- construcción ------------------------------------------------------------------
    def build(self) -> PortResult:
        st = self.p.zx_state
        if st is not None and st.model == "128k":
            pag = [h.addr for h in self.an.hotspots if h.kind == "paging"]
            # también LD BC,$7FFD (puerto de paginación) aunque el análisis no lo ejecutara
            pag += [a for a, i in self.an.instrs.items()
                    if i.op == "LD" and len(i.operands) == 2 and i.operands[0].kind == D.REG16
                    and i.operands[0].value == "BC" and i.operands[1].kind == D.IMM16
                    and (i.operands[1].value & 0x8002) == 0 and i.operands[1].value & 0xFF == 0xFD]
            # y en los bytes: LD BC,$7FFD seguido de cerca por OUT (C),r
            mem = self.p.mem
            for a in range(0x4000, 0xFFF8):
                if mem[a] == 0x01 and mem[a + 1] == 0xFD and mem[a + 2] == 0x7F and any(
                        mem[a + k] == 0xED and mem[a + k + 1] in (0x41, 0x49, 0x51, 0x59, 0x61,
                                                                   0x69, 0x79)
                        for k in range(3, 6)):
                    pag.append(a)
            if pag and self.opt.ram512:
                self.z128 = True
                self.warnings.append("modo 128K: paginación con la ampliación de 512K del CPC "
                                     "(el port necesita un CPC 6128 con 512K extra, 576K en "
                                     "total)")
            elif pag:
                sites = ", ".join(f"{a:04X}" for a in sorted(set(pag))[:6])
                raise ValueError(
                    "juego de 128K que pagina memoria ($7FFD en " + sites + "): no se puede "
                    "portar automáticamente al CPC. El Spectrum cambia el banco de $C000 y el "
                    "CPC 6128 solo puede poner sus bancos extra en $4000 (o uno en $C000), y "
                    "los 128K del juego más la pantalla del CPC no caben en 128K. Hace falta "
                    "un port a mano (usa analyze y disasm como punto de partida), o --512k para un "
                    "CPC con ampliación de RAM, que sí puede paginar en $C000")
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
                "GAME_I": p.regs["I"] & 0xFF, "INIT_ULA": border, "kmap": 0,
                "SKIP_SAME_HL": self._skip_same("HL"), "SKIP_SAME_DE": self._skip_same("DE")}
        syms.update(self._hal_features())
        zst = p.zx_state
        syms["ROMPROT"] = int(self._romprot())
        if syms["ROMPROT"]:
            self.warnings.append("escrituras del juego en $0000-$3FFF (ROM en el Spectrum, "
                                 "p.ej. para recortar sprites): el HAL las ignora")
        syms["Z128"] = int(self.z128)
        syms["INIT_7FFD"] = (zst.port_7ffd & 0x3F) if self.z128 else 0
        if self.z128:
            syms["USE_AY"] = 1
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
        # último recurso: una zona libre de la memoria del juego (como la fuente de la ROM)
        game_region = None
        for size in (512, 256, 128):
            g = self._find_free(game_mem, size + 32)
            if g is not None:
                game_region = (g + 16, g + 16 + size)       # con margen a los lados
                free.append(game_region)
                break
        gen_src, placed = self._place_handlers(fixed.symbols, free, syms)
        if game_region is not None and (game_region[0], game_region[1]) not in \
                [tuple(r) for r in placed]:
            used = next(r for r in placed if r[1] == game_region[1])
            self.warnings.append(f"el HAL no tiene sitio para todo: {used[0] - game_region[0]} "
                                 f"bytes de manejadores en {game_region[0]:#06x}, una zona que "
                                 "el juego no tocó durante el análisis")
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

        if self.z128:
            mem = self._z128_memory(mem, xm, pm)
        rom_bank = getattr(self, "rom_bank", None)
        if rom_bank and not self.z128:
            # 128K: copia de la ROM del Spectrum en el banco extra 5
            mem = mem + bytearray(0x10000)
            mem[0x14000:0x18000] = rom_bank
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
        # los manejadores pueden llamarse entre sí: para medirlos basta un valor cualquiera
        dummy = {lab: 0xC000 for lab, _, _ in self.handlers.values()}
        for k in ("rom_peek", "ldir_scr", "ldir_end", "ldir_adj", "ldir_l0", "ldir_sbc",
                  "ldir_skip", "smc_tr", "rom_scratch"):
            dummy[k] = 0xC000
        for key, (label, code, htype) in self.handlers.items():
            src = f"{label}:\n{code}"
            own = {ln.split(":")[0].strip() for ln in src.splitlines()
                   if ln and not ln[0].isspace() and ":" in ln}
            probe = Assembler({**{k: v for k, v in dummy.items() if k not in own}, **symbols,
                               **syms}).assemble(f" org $C000\n{src}")
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
        ram_config = 0
        if self.z128:
            v = p.zx_state.port_7ffd
            ram_config = 0x01 | ((v & 7) << 3)
            if v & 8:
                crtc[12] = 0x31             # pantalla sombra: pantalla B del CPC
        return CPCState(mem=mem, regs=regs, iff1=p.iff1, iff2=p.iff2, im=1, ga_pen=16,
                        palette=palette, ga_rmr=0x01 | 0x04 | 0x08, ram_config=ram_config,
                        crtc_sel=0,
                        crtc=crtc, upper_rom=0, ppi=(8, 0, 0, 0x82), psg_sel=8, psg=psg,
                        model=self.opt.model)


SMC_TR_SRC = """\
smc_tr:
; Escritura automodificable traducida. Pila: [BC][DE][HL][AF][ret]; A = valor,
; HL = dirección escrita, DE = tabla de direcciones (acabada en 0) donde un
; LD (HL),A / LD (DE),A ($77 / $12) debe escribirse parcheado ($E7 / $DF).
        ld b,a
.l:     ld a,(de)
        ld c,a
        inc de
        ld a,(de)
        inc de
        or c
        jr z,.w                 ; no está en la tabla
        dec de
        ld a,(de)               ; byte alto
        inc de
        cp h
        jr nz,.l
        ld a,c
        cp l
        jr nz,.l
        ld a,b
        cp $77
        jr nz,.d
        ld b,$E7
        jr .w
.d:     cp $12
        jr nz,.w
        ld b,$DF
.w:     ld (hl),b
        pop bc
        pop de
        pop hl
        pop af
        ret
"""


LDIR_SCR_SRC = """\
ldir_scr:
; LDIR que solo escribe (y refleja) los bytes de destino que cambian. Mismo
; resultado que LDIR: HL, DE y BC finales y flags (H, N y P/V a cero).
; Con origen y destino alineados a 8 compara por tramos de bloques de 8 bytes
; que no cruzan de página, contando con DJNZ y ajustando BC una vez por tramo.
        push af
        ld a,b
        or c
        jr nz,.top
        dec bc                  ; BC = 0: (casi) 64K, como LDIR
.top:
        if ROMPROT
        ld a,d
        cp $40
        jp c,.rom               ; destino en la "ROM": copiar contra el byte de descarte
        endif
        ld a,l
        or e
        and 7
        jr nz,.one
        ; kc = bloques que permite BC (máx. 32)
        ld a,b
        or a
        ld a,32
        jr nz,.kc
        ld a,c
        rrca
        rrca
        rrca
        and $1F
        jr z,.one               ; menos de 8 bytes
.kc:    ld (.kcv+1),a
        ; kp = bloques hasta el final de la página de origen o destino
        ld a,l
        cp e
        jr nc,.m
        ld a,e
.m:     neg
        rrca
        rrca
        rrca
        and $1F
        jr nz,.kcv
        ld a,32
.kcv:   cp 0
        jr c,.k
        ld a,(.kcv+1)
.k:     ld (ldir_sbc+1),bc          ; guardar BC y el byte bajo inicial
        ld b,a
        ld a,l
        ld (ldir_l0+1),a
.blk:
        rept 8
        ld a,(de)
        cp (hl)
        jr nz,.diff
        inc e
        inc l
        endr
        djnz .blk
        ; tramo entero igual: página siguiente si se ha llegado al final
        ld a,l
        or a
        jr nz,.nh
        inc h
.nh:    ld a,e
        or a
        jr nz,.nd
        inc d
.nd:    call ldir_adj
        ld a,b
        or c
        jr nz,.top
        jp ldir_end
.diff:  call ldir_adj               ; descontar los bytes iguales ya pasados
.one:   ld a,(de)
        cpi                     ; A - (HL); HL+1; BC-1; P/V = (BC != 0)
        jr nz,.chg
        inc de
        jp pe,.top
        jp ldir_end
        if ROMPROT
.rom:   push de
        ld de,rom_scratch
        ldi
        pop de
        inc de
        jp pe,.top
        jp ldir_end
        endif
.chg:   dec hl
        ld a,(hl)
        inc hl
        ld (de),a
        ex de,hl
        call mirror_hl          ; conserva todo
        ex de,hl
        inc de
        jp pe,.top
        jp ldir_end
"""


LDIR_SCR2_SRC = """\
ldir_end:
        pop af
        push hl
        push af
        pop hl
        res 4,l                 ; H = N = P/V = 0
        res 2,l
        res 1,l
        push hl
        pop af
        pop hl
        ret
ldir_skip:  ; copia saltada: HL y DE avanzan BC, BC = 0, flags como LDIR
        push af
        add hl,bc
        ex de,hl
        add hl,bc
        ex de,hl
        ld bc,0
        jp ldir_end
ldir_adj:   ; BC = BC guardado - bytes pasados (L - L0; 0 al acabar una página = 256)
        ld a,l
ldir_l0:
        sub 0
        push hl
        push de
        ld e,a
        ld d,0
        or a
        jr nz,.a1
        ld a,(ldir_l0+1)            ; L0 = L: o nada (diferencia en el 1er byte) o 256
        cp l
        jr nz,.a1
        ld a,b                  ; B = 0 tras el DJNZ completo: 256 bytes
        or a
        jr nz,.a1
        inc d
.a1:
ldir_sbc:
        ld hl,0
        or a
        sbc hl,de
        ld b,h
        ld c,l
        pop de
        pop hl
        ret
"""


ROM_PEEK_SRC = """\
rom_peek:
; A = byte en (HL); por debajo de $4000 se lee la copia de la ROM del banco extra 5.
; Conserva F y el resto de registros. Sin pila mientras el banco está puesto.
        push hl
        push bc
        push af
        ld a,h
        cp $40
        jr nc,.ram
        set 6,h
        ld a,i                  ; P/V = IFF2
        di
        ld bc,$7FC5
        out (c),c
        ld a,(hl)
        ld c,$C0
        out (c),c
        ld b,a
        jp po,.di
        ei
.di:    pop af
        ld a,b
        pop bc
        pop hl
        ret
.ram:   pop af
        ld a,(hl)
        pop bc
        pop hl
        ret
"""


_A_WRITERS = {"XOR", "AND", "OR", "SUB", "CPL", "NEG", "RLA", "RRA", "RLCA", "RRCA", "DAA",
              "RLD", "RRD"}


def _writes_a(ins):
    """¿Puede ``ins`` cambiar el registro A? (en caso de duda, sí)"""
    op, ops = ins.op, ins.operands
    if op in _A_WRITERS:
        return True
    if op in ("LD", "ADD", "ADC", "SBC", "IN", "INC", "DEC", "RL", "RR", "RLC", "RRC", "SLA",
              "SRA", "SRL", "SLL", "SET", "RES") and ops:
        d = ops[0] if op not in ("SET", "RES") else ops[-1]
        return d.kind == D.REG and d.value == "A"
    if op == "EX":
        return any(o.kind == D.REG16 and o.value in ("AF", "AF'") for o in ops)
    if op == "POP":
        return ops and ops[0].value == "AF"
    if op in ("EXX", "NOP", "CP", "BIT", "PUSH", "OUT", "DJNZ", "JR", "JP", "DI", "EI", "SCF",
              "CCF", "LDI", "LDD", "LDIR", "LDDR", "CPI", "CPD", "CPIR", "CPDR"):
        return False
    return True


def _const_a(ins):
    """Valor que deja en A ``LD A,n`` o ``XOR A`` (None si no es constante)."""
    if ins.op == "LD" and len(ins.operands) == 2 and ins.operands[0].kind == D.REG and \
            ins.operands[0].value == "A" and ins.operands[1].kind == D.IMM8:
        return ins.operands[1].value
    if ins.op in ("XOR", "SUB") and ins.operands and ins.operands[-1].kind == D.REG and \
            ins.operands[-1].value == "A":
        return 0
    return None


def _same_check(ins):
    """Código previo que vuelve sin hacer nada si ``ins`` (LD (rr),x) no cambiaría el
    byte. Termina con la pila como estaba; el manejador añade la etiqueta .same."""
    if ins.op != "LD" or len(ins.operands) != 2:
        return None
    dst, src = ins.operands
    if dst.kind != D.IND_REG:
        return None
    if src.kind == D.IMM8:
        load = f"        ld a,{src.value}\n"
    elif src.kind == D.REG and src.value in ("A", "B", "C", "D", "E", "H", "L"):
        load = "" if src.value == "A" else f"        ld a,{src.value.lower()}\n"
    else:
        return None
    if dst.value == "HL":
        cmp = "        cp (hl)\n"
    elif dst.value == "DE":
        cmp = "        ex de,hl\n        cp (hl)\n        ex de,hl\n"
    elif dst.value == "BC":
        cmp = "        push hl\n        ld h,b\n        ld l,c\n        cp (hl)\n        pop hl\n"
    else:
        return None
    return ("        push af\n" + load + cmp + "        jr z,.same\n        pop af\n")


def _rom_read_body(ins):
    """Código que emula ``LD r,(xx)`` leyendo la ROM con rom_peek; None si no es esa forma."""
    if ins.op != "LD" or len(ins.operands) != 2:
        return None
    dst, src = ins.operands
    if dst.kind != D.REG or dst.value in ("I", "R", "IXH", "IXL", "IYH", "IYL"):
        return None
    r = dst.value
    if src.kind == D.IND_REG and src.value in ("HL", "DE", "BC"):
        via = src.value
        calc = "" if via == "HL" else f"        ld h,{via[0].lower()}\n        ld l,{via[1].lower()}\n"
    elif src.kind == D.IDX:
        reg, d = src.value
        via = reg
        calc = (f"        push af\n        push de\n        push {reg.lower()}\n        pop hl\n"
                f"        ld de,{d}\n        add hl,de\n        pop de\n        pop af\n")
    else:
        return None
    code = ""
    if r != "A":
        code += "        push af\n"
    if via != "HL":
        code += "        push hl\n" + calc
    code += "        call rom_peek\n"
    if via != "HL":
        code += "        pop hl\n"
    if r != "A":
        code += f"        ld {r.lower()},a\n        pop af\n"
    return code + "        ret\n"


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
    mem = result.state.mem
    romcopy = len(mem) > 0x14000 and any(mem[0x14000:0x18000])
    loader = Assembler({"STUB2": stub2, "ROMCOPY": int(romcopy)}).assemble(
        src, "loader6128.asm").image()
    files = [("DISC", "BIN", make_amsdos_header("DISC", "BIN", len(loader), 0x8000, 0x8000) + loader)]
    parts = [("A", 0), ("B", 0x4000), ("C", 0x8000), ("D", 0xC000)]
    if romcopy:
        parts.append(("R", 0x14000))        # copia de la ROM del Spectrum -> banco 5
    for part, off in parts:
        data = bytes(mem[off:off + 0x4000])
        files.append(("ZXCPC", part, make_amsdos_header("ZXCPC", part, len(data), 0x4000, 0) + data))
    return make_dsk(files)


def patches_json(result: PortResult):
    return json.dumps([{"addr": f"{p.addr:04X}", "orig": p.orig.hex(" ").upper(),
                        "new": p.new.hex(" ").upper(), "kind": p.kind, "instr": p.text,
                        "handler": p.handler, "note": p.note} for p in result.patches],
                      indent=1, ensure_ascii=False)
