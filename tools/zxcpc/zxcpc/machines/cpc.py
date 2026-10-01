"""Amstrad CPC 464/6128 emulado, orientado a análisis y pruebas.

Emula el gate array (paleta, modos, ROMs, interrupciones cada 52 líneas),
el CRTC (registros de geometría y dirección de pantalla), el PPI 8255, el
PSG AY-3-8912 (registros y teclado a través del puerto A) y la banca de
memoria del 6128. No emula el FDC ni el audio.
"""

from __future__ import annotations

from ..formats.cpc import CPCState, HW_RGB
from ..formats.png import write_png
from ..z80.cpu import Z80

LINE_US = 64
LINES = 312
FRAME_US = LINE_US * LINES

CPC_KEYS = [
    ["CURUP", "CURRIGHT", "CURDOWN", "F9", "F6", "F3", "ENTER", "F."],
    ["CURLEFT", "COPY", "F7", "F8", "F5", "F1", "F2", "F0"],
    ["CLR", "[", "RETURN", "]", "F4", "SHIFT", "\\", "CTRL"],
    ["^", "-", "@", "P", ";", ":", "/", "."],
    ["0", "9", "O", "I", "L", "K", "M", ","],
    ["8", "7", "U", "Y", "H", "J", "N", "SPACE"],
    ["6", "5", "R", "T", "G", "F", "B", "V"],
    ["4", "3", "E", "W", "S", "D", "C", "X"],
    ["1", "2", "ESC", "Q", "TAB", "A", "CAPSLOCK", "Z"],
    ["JOYUP", "JOYDOWN", "JOYLEFT", "JOYRIGHT", "FIRE2", "FIRE1", "SPARE", "DEL"],
]
CPC_KEY_POS = {k: (r, b) for r, row in enumerate(CPC_KEYS) for b, k in enumerate(row)}

# Configuraciones de RAM del 6128: bancos (de 16K) visibles en cada cuarto
RAM_CONFIGS = [(0, 1, 2, 3), (0, 1, 2, 7), (4, 5, 6, 7), (0, 3, 2, 7),
               (0, 4, 2, 3), (0, 5, 2, 3), (0, 6, 2, 3), (0, 7, 2, 3)]


class CPC:
    def __init__(self, lower_rom: bytes | None = None, upper_roms: dict | None = None,
                 ram_kb=128):
        self.cpu = Z80()
        self.view = self.cpu.mem                 # lo que ve la CPU
        self.pages = [bytearray(16384) for _ in range(ram_kb // 16)]
        self.lower_rom = lower_rom
        self.upper_roms = upper_roms or {}
        self.mapped = list(RAM_CONFIGS[0])
        self.rmr = 0x01 | 0x04 | 0x08            # modo 1, ROMs fuera
        self.ram_cfg = 0
        self.upper_sel = 0
        self.pen = 0
        self.palette = [20] * 17
        self.crtc_sel = 0
        self.crtc = [63, 40, 46, 0x8E, 38, 0, 25, 30, 0, 7, 0, 0, 0x30, 0, 0, 0, 0, 0]
        self.ppi_a = 0
        self.ppi_b_out = 0
        self.ppi_c = 0
        self.ppi_ctrl = 0x82
        self.psg_sel = 0
        self.psg = [0] * 16
        self.psg_writes = []                     # (frame, reg, val)
        self.keys = [0xFF] * 10
        self.frame = 0
        self.line = 0
        self.us_in_line = 0
        self.int_pending = False
        self.int_counter = 0
        self.cur_pc = 0
        self.on_write = None
        self.on_io = None
        self.tracer = None
        self.frame_mode = 1
        self.cpu.wb = self._wb
        self.cpu.inp = self._in
        self.cpu.outp = self._out
        self._rom_lo_on = False
        self._rom_hi_on = False
        self._refresh_view(full=True)

    # --- memoria --------------------------------------------------------------
    def _sync_view_to_pages(self):
        v = self.view
        for q in range(4):
            if q == 0 and self._rom_lo_on:
                continue
            if q == 3 and self._rom_hi_on:
                continue
            p = self.mapped[q]
            if p < len(self.pages):
                self.pages[p][:] = v[q * 16384:(q + 1) * 16384]

    def _refresh_view(self, full=False):
        if not full:
            self._sync_view_to_pages()
        cfg = RAM_CONFIGS[self.ram_cfg & 7] if len(self.pages) > 4 else RAM_CONFIGS[0]
        self.mapped = list(cfg)
        self._rom_lo_on = not (self.rmr & 0x04) and self.lower_rom is not None
        up = self.upper_roms.get(self.upper_sel, self.upper_roms.get(0))
        self._rom_hi_on = not (self.rmr & 0x08) and up is not None
        v = self.view
        for q in range(4):
            p = self.mapped[q]
            v[q * 16384:(q + 1) * 16384] = self.pages[p]
        if self._rom_lo_on:
            v[0:16384] = self.lower_rom[:16384]
        if self._rom_hi_on:
            v[0xC000:0x10000] = up[:16384]

    def ram(self) -> bytearray:
        """Los 64K base (bancos 0-3), que es lo que lee el vídeo."""
        self._sync_view_to_pages()
        return self.pages[0] + self.pages[1] + self.pages[2] + self.pages[3]

    def _wb(self, a, v):
        if self.on_write is not None:
            self.on_write(self.cur_pc, a, v)        # antes de escribir: aún se ve el valor viejo
        if a < 0x4000 and self._rom_lo_on:
            self.pages[self.mapped[0]][a] = v
        elif a >= 0xC000 and self._rom_hi_on:
            self.pages[self.mapped[3]][a - 0xC000] = v
        else:
            self.view[a] = v

    # --- E/S ------------------------------------------------------------------
    def _in(self, port):
        v = 0xFF
        if not port & 0x0800:           # PPI
            sub = (port >> 8) & 3
            if sub == 0:
                if self.ppi_ctrl & 0x10:
                    v = self._psg_read()
                else:
                    v = self.ppi_a
            elif sub == 1:
                vsync = 1 if self.line < 8 else 0
                v = 0x5E | vsync          # 50 Hz, Amstrad, sin cinta
            elif sub == 2:
                v = self.ppi_c
        elif not port & 0x4000 and (port >> 8) & 3 == 3:
            v = self.crtc[self.crtc_sel] if 12 <= self.crtc_sel <= 17 else 0
        if self.on_io is not None:
            self.on_io(self.cur_pc, "in", port, v)
        return v

    def _psg_read(self):
        func = (self.ppi_c >> 6) & 3
        if func != 1:
            return 0xFF
        if self.psg_sel == 14:
            line = self.ppi_c & 0x0F
            return self.keys[line] if line < 10 else 0xFF
        return self.psg[self.psg_sel]

    def _psg_update(self):
        func = (self.ppi_c >> 6) & 3
        if func == 3:
            self.psg_sel = self.ppi_a & 0x0F
        elif func == 2:
            if self.psg_sel < 14:
                self.psg[self.psg_sel] = self.ppi_a
                self.psg_writes.append((self.frame, self.psg_sel, self.ppi_a))

    def _out(self, port, v):
        if self.on_io is not None:
            self.on_io(self.cur_pc, "out", port, v)
        if (port & 0xC000) == 0x4000:   # gate array
            f = v >> 6
            if f == 0:
                self.pen = 16 if v & 0x10 else v & 0x0F
            elif f == 1:
                self.palette[self.pen] = v & 0x1F
            elif f == 2:
                old = self.rmr
                self.rmr = v & 0x1F
                if v & 0x10:
                    self.int_counter = 0
                    self.int_pending = False
                if (old ^ self.rmr) & 0x0C:
                    self._refresh_view()
            else:
                if len(self.pages) > 4:
                    self.ram_cfg = v & 7
                    self._refresh_view()
        if not port & 0x4000:           # CRTC
            sub = (port >> 8) & 3
            if sub == 0:
                self.crtc_sel = v & 0x1F
            elif sub == 1 and self.crtc_sel < 18:
                self.crtc[self.crtc_sel] = v
        if not port & 0x2000:           # selección de ROM superior
            self.upper_sel = v
            if not self.rmr & 0x08:
                self._refresh_view()
        if not port & 0x0800:           # PPI
            sub = (port >> 8) & 3
            if sub == 0:
                self.ppi_a = v
                self._psg_update()
            elif sub == 1:
                self.ppi_b_out = v
            elif sub == 2:
                self.ppi_c = v
                self._psg_update()
            else:
                if v & 0x80:
                    self.ppi_ctrl = v
                    self.ppi_c = 0
                else:
                    bit = (v >> 1) & 7
                    if v & 1:
                        self.ppi_c |= 1 << bit
                    else:
                        self.ppi_c &= ~(1 << bit)
                    self._psg_update()

    # --- teclado ------------------------------------------------------------------
    def press(self, *names):
        for n in names:
            r, b = CPC_KEY_POS[n.upper()]
            self.keys[r] &= ~(1 << b)

    def release(self, *names):
        for n in names:
            r, b = CPC_KEY_POS[n.upper()]
            self.keys[r] |= 1 << b

    def release_all(self):
        self.keys = [0xFF] * 10

    # --- estado ---------------------------------------------------------------------
    def load_state(self, st: CPCState):
        mem = st.mem
        for p in range(min(len(self.pages), len(mem) // 16384)):
            self.pages[p][:] = mem[p * 16384:(p + 1) * 16384]
        c = self.cpu
        for k in ("AF", "BC", "DE", "HL", "IX", "IY", "SP", "PC"):
            c.set_pair(k, st.regs[k])
        for k, (hi, lo) in (("AF'", (7, 6)), ("BC'", (0, 1)), ("DE'", (2, 3)), ("HL'", (4, 5))):
            c.alt[hi] = st.regs[k] >> 8
            c.alt[lo] = st.regs[k] & 0xFF
        c.i, c.r = st.regs["I"], st.regs["R"]
        c.iff1, c.iff2, c.im = st.iff1, st.iff2, st.im
        self.palette = list(st.palette)
        self.pen = st.ga_pen
        self.rmr = st.ga_rmr & 0x1F
        self.ram_cfg = st.ram_config & 7
        self.crtc = list(st.crtc)
        self.crtc_sel = st.crtc_sel
        self.upper_sel = st.upper_rom
        self.ppi_a, self.ppi_b_out, self.ppi_c, self.ppi_ctrl = st.ppi
        self.psg = list(st.psg)
        self.psg_sel = st.psg_sel
        self._refresh_view(full=True)

    def save_state(self) -> CPCState:
        self._sync_view_to_pages()
        c = self.cpu
        s = c.state()
        regs = {k: s[k] for k in ("AF", "BC", "DE", "HL", "AF'", "BC'", "DE'", "HL'", "IX", "IY",
                                  "SP", "PC", "I", "R")}
        mem = bytearray().join(self.pages[:8]) if len(self.pages) > 4 else bytearray().join(self.pages)
        return CPCState(mem=mem, regs=regs, iff1=c.iff1, iff2=c.iff2, im=c.im, ga_pen=self.pen,
                        palette=list(self.palette), ga_rmr=self.rmr, ram_config=self.ram_cfg,
                        crtc_sel=self.crtc_sel, crtc=list(self.crtc), upper_rom=self.upper_sel,
                        ppi=(self.ppi_a, self.ppi_b_out, self.ppi_c, self.ppi_ctrl),
                        psg_sel=self.psg_sel, psg=list(self.psg), model=2 if len(self.pages) > 4 else 0)

    # --- ejecución --------------------------------------------------------------------
    def run_frame(self):
        c = self.cpu
        step = c.step
        self.frame_mode = self.rmr & 3
        while self.line < LINES:
            if self.int_pending and c.iff1 and not c.ei_delay:
                t = c.interrupt(0xFF)
                if t:
                    self.int_pending = False
                    # el reconocimiento borra el bit 5 del contador
                    self.int_counter &= 0x1F
                    self._advance((t + 3) >> 2)
                    continue
            self.cur_pc = c.pc
            if c.halted:
                # avanzar hasta la próxima interrupción
                self._advance(LINE_US - self.us_in_line)
                continue
            if self.tracer is not None:
                self.tracer(c.pc)
            t = step()
            self._advance((t + 3) >> 2)
        self.line -= LINES
        self.frame += 1

    def _advance(self, us):
        self.us_in_line += us
        while self.us_in_line >= LINE_US:
            self.us_in_line -= LINE_US
            self.line += 1
            self.int_counter += 1
            if self.line == 2:
                # sincronización con VSYNC (2 HSYNC tras su inicio)
                if self.int_counter >= 32:
                    self.int_pending = True
                self.int_counter = 0
            elif self.int_counter >= 52:
                self.int_counter = 0
                self.int_pending = True

    def run_frames(self, n, keys_script=None):
        for _ in range(n):
            if keys_script:
                keys_script(self, self.frame)
            self.run_frame()

    # --- firmware -------------------------------------------------------------------------
    def boot_firmware(self, frames=100):
        """Arranca el firmware (necesita las ROMs) hasta el "Ready" de BASIC."""
        if self.lower_rom is None:
            raise ValueError("se necesitan las ROMs del CPC para arrancar el firmware")
        self.rmr = 0x01
        self._refresh_view(full=True)
        self.cpu.pc = 0
        self.cpu.iff1 = self.cpu.iff2 = 0
        self.run_frames(frames)

    def inject_and_call(self, data, load, entry, sp=0xBFF0):
        """Carga ``data`` en ``load`` y salta a ``entry`` como un CALL desde BASIC."""
        self._sync_view_to_pages()
        for i, b in enumerate(data):
            a = (load + i) & 0xFFFF
            self.pages[self.mapped[a >> 14]][a & 0x3FFF] = b
        self._refresh_view(full=True)
        c = self.cpu
        c.halted = False
        c.sp = sp
        c.push(0)                       # si el programa vuelve, reinicia
        c.pc = entry
        c.iff1 = c.iff2 = 1
        c.im = 1

    # --- vídeo ------------------------------------------------------------------------
    def screen_pens(self):
        """Matriz de tintas (índices de pluma) de la zona visible.

        Devuelve (ancho_en_pixels_modo, alto, filas, modo). Cada fila es una
        lista de índices de pluma.
        """
        ram = self.ram()
        r1, r6, r9 = self.crtc[1], self.crtc[6], self.crtc[9] & 0x1F
        start = ((self.crtc[12] & 0x3F) << 8) | self.crtc[13]
        mode = self.rmr & 3
        ppb = {0: 2, 1: 4, 2: 8, 3: 2}[mode]
        rows = []
        for cr in range(r6):
            for ln in range(r9 + 1):
                row = []
                for ch in range(r1):
                    ma = (start + cr * r1 + ch) & 0x3FFF
                    base = ((ma & 0x3000) << 2) | ((ln & 7) << 11) | ((ma & 0x3FF) << 1)
                    for k in range(2):
                        b = ram[(base + k) & 0xFFFF]
                        row.extend(decode_byte(b, mode))
                rows.append(row)
        return r1 * 2 * ppb, len(rows), rows, mode

    def screenshot(self, path, border=16, double=True):
        w, h, rows, mode = self.screen_pens()
        scale = {0: 4, 1: 2, 2: 1, 3: 4}[mode]
        pal = [HW_RGB[self.palette[i] & 31] for i in range(17)]
        bc = bytes(pal[16])
        W = w * scale + 2 * border * 2
        out = []
        for _ in range(border):
            out.append(bc * W)
        for r in rows:
            line = bytearray(bc * border * 2)
            for pen in r:
                line += bytes(pal[pen]) * scale
            line += bc * border * 2
            out.append(bytes(line))
            if double:
                out.append(bytes(line))
        for _ in range(border):
            out.append(bc * W)
        return write_png(path, W, len(out), out)


_DECODE = {}


def decode_byte(b, mode):
    key = (b, mode)
    r = _DECODE.get(key)
    if r is not None:
        return r
    if mode == 1:
        r = [((b >> (7 - k)) & 1) | (((b >> (3 - k)) & 1) << 1) for k in range(4)]
    elif mode == 2:
        r = [(b >> (7 - k)) & 1 for k in range(8)]
    else:
        def px(b7, b3, b5, b1):
            return ((b >> b7) & 1) | (((b >> b3) & 1) << 1) | (((b >> b5) & 1) << 2) | \
                (((b >> b1) & 1) << 3)
        r = [px(7, 3, 5, 1), px(6, 2, 4, 0)]
    _DECODE[key] = r
    return r


def encode_mode1(pens):
    """4 plumas (0-3) -> byte de modo 1."""
    b = 0
    for k, p in enumerate(pens):
        b |= (p & 1) << (7 - k)
        b |= ((p >> 1) & 1) << (3 - k)
    return b


def encode_mode0(p0, p1):
    def bits(p, b7, b3, b5, b1):
        return ((p & 1) << b7) | (((p >> 1) & 1) << b3) | (((p >> 2) & 1) << b5) | \
            (((p >> 3) & 1) << b1)
    return bits(p0, 7, 3, 5, 1) | bits(p1, 6, 2, 4, 0)
