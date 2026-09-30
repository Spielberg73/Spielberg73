"""ZX Spectrum 48K emulado, orientado a análisis y pruebas.

No emula la contención de memoria ni el audio: lo importante es ejecutar
el juego con fidelidad suficiente para observar qué hace (E/S, escrituras en
pantalla, llamadas a la ROM, interrupciones).
"""

from __future__ import annotations

from ..formats.png import write_png
from ..formats.zx import ZXState
from ..z80.cpu import Z80

FRAME_T = 69888

ZX_KEYS = [
    ["CAPS", "Z", "X", "C", "V"],
    ["A", "S", "D", "F", "G"],
    ["Q", "W", "E", "R", "T"],
    ["1", "2", "3", "4", "5"],
    ["0", "9", "8", "7", "6"],
    ["P", "O", "I", "U", "Y"],
    ["ENTER", "L", "K", "J", "H"],
    ["SPACE", "SYM", "M", "N", "B"],
]
KEY_POS = {k: (r, b) for r, row in enumerate(ZX_KEYS) for b, k in enumerate(row)}

ZX_RGB = [
    (0, 0, 0), (0, 0, 0xD7), (0xD7, 0, 0), (0xD7, 0, 0xD7),
    (0, 0xD7, 0), (0, 0xD7, 0xD7), (0xD7, 0xD7, 0), (0xD7, 0xD7, 0xD7),
    (0, 0, 0), (0, 0, 0xFF), (0xFF, 0, 0), (0xFF, 0, 0xFF),
    (0, 0xFF, 0), (0, 0xFF, 0xFF), (0xFF, 0xFF, 0), (0xFF, 0xFF, 0xFF),
]

# Direcciones de rutinas de la ROM de 48K habituales en juegos
ROM_ROUTINES = {
    0x0000: "START (reset)", 0x0008: "ERROR-1 (RST 8)", 0x0010: "PRINT-A (RST 16)",
    0x0018: "GET-CHAR (RST 24)", 0x0020: "NEXT-CHAR (RST 32)", 0x0028: "FP-CALC (RST 40)",
    0x0030: "BC-SPACES (RST 48)", 0x0038: "MASK-INT (RST 56)", 0x0066: "RESET NMI",
    0x028E: "KEY-SCAN", 0x02BF: "KEYBOARD", 0x031E: "K-TEST", 0x03B5: "BEEPER",
    0x03F8: "BEEP", 0x04C2: "SA-BYTES", 0x0556: "LD-BYTES", 0x0562: "LD-BYTES+12",
    0x05E3: "LD-EDGE-2", 0x05E7: "LD-EDGE-1", 0x0802: "LD-BLOCK", 0x0D6B: "CLS",
    0x0D6E: "CLS-LOWER", 0x0DAF: "CL-ALL", 0x0DD9: "CL-SET", 0x0E44: "CL-LINE",
    0x0E9B: "CL-ADDR", 0x0EDF: "CLEAR-PRB", 0x1601: "CHAN-OPEN", 0x15D4: "WAIT-KEY",
    0x15DE: "WAIT-KEY1", 0x1DA0: "PRINT...", 0x203C: "PR-STRING", 0x2294: "BORDER",
    0x22AA: "PIXEL-ADD", 0x22CB: "POINT-SUB", 0x22DC: "PLOT", 0x22E5: "PLOT-SUB",
    0x24BA: "DRAW-LINE", 0x2BF1: "STK-FETCH", 0x2D28: "STACK-A", 0x2D2B: "STACK-BC",
    0x2DA2: "FP-TO-BC", 0x2DE3: "PRINT-FP", 0x1A1B: "OUT-NUM-1", 0x1E94: "FIND-INT1",
    0x1E99: "FIND-INT2", 0x3D00: "fuente de caracteres",
}


def build_mini_rom() -> bytes:
    """ROM sustituta mínima (código propio, no la ROM de Sinclair).

    Implementa lo que los juegos usan del sistema en tiempo de ejecución:
    la rutina de interrupción IM 1 (contador FRAMES y lectura de teclado
    en LAST_K) y trampas (HALT en direcciones conocidas) que la máquina
    intercepta para emular BEEPER, CLS, RST 16, etc. a alto nivel.
    """
    from ..z80.asm import assemble
    src = r"""
        org 0
        di
        ld sp,$FF58
        jp $1FFE            ; trampa: arranque (la máquina decide)
        org $0008
        jp $1FF0            ; ERROR-1: trampa
        org $0010
        jp $1FF2            ; PRINT-A: trampa
        org $0038
        push af
        push hl
        ld hl,($5C78)       ; FRAMES
        inc hl
        ld ($5C78),hl
        ld a,h
        or l
        jr nz,.nof
        ld hl,$5C7A
        inc (hl)
.nof:   call $1FF4          ; trampa: KEYBOARD (actualiza LAST_K)
        pop hl
        pop af
        ei
        ret
        org $0066
        retn
        ; puntos de trampa (la máquina los intercepta antes de ejecutarlos)
        org $1FF0
        ret
        ret
        ret
        ret
        ret
        org $1FFE
        halt
        jr $1FFE
    """
    res = assemble(src)
    rom = bytearray(16384)
    for s in res.segments:
        rom[s.org:s.org + len(s.data)] = s.data
    # Rutinas documentadas: cada una es un RET; la máquina las emula al
    # llegar a su dirección (trampa por PC)
    for addr in ROM_ROUTINES:
        if addr >= 0x0040 and addr < 0x3D00 and rom[addr] == 0:
            rom[addr] = 0xC9
    return bytes(rom)


class Spectrum48K:
    def __init__(self, rom: bytes | None = None):
        self.cpu = Z80()
        self.mem = self.cpu.mem
        self.real_rom = rom is not None
        self.rom = rom if rom else build_mini_rom()
        self.mem[0:16384] = self.rom[:16384]
        self.cpu.wb = self._wb
        self.cpu.inp = self._in
        self.cpu.outp = self._out
        self.keys = [0x1F] * 8          # filas del teclado (bits activos a 0)
        self.kempston = 0
        self.border = 7
        self.beeper = 0
        self.frame = 0
        self.t_in_frame = 0
        self.ay_sel = 0
        self.ay = [0] * 16
        # ganchos de análisis
        self.cur_pc = 0
        self.on_write = None            # f(pc, addr, val)
        self.on_io = None               # f(pc, 'in'|'out', port, val)
        self.on_rom_call = None         # f(pc_from, rom_addr)
        self.traps = {}                 # pc -> función (solo con mini-ROM)
        self.tracer = None              # f(pc) antes de cada instrucción
        self.tape_blocks = []
        self.tape_pos = 0
        self.beeper_toggles = 0
        if not self.real_rom:
            self._install_hle_traps()

    # --- memoria y E/S ------------------------------------------------------
    def _wb(self, a, v):
        if a < 0x4000:
            return
        self.mem[a] = v
        if self.on_write is not None:
            self.on_write(self.cur_pc, a, v)

    def _in(self, port):
        v = 0xFF
        if not port & 1:
            hi = port >> 8
            k = 0x1F
            for r in range(8):
                if not hi & (1 << r):
                    k &= self.keys[r]
            v = 0xA0 | k
        elif (port & 0xFF) == 0x1F:
            v = self.kempston
        elif port == 0xFFFD:
            v = self.ay[self.ay_sel & 15]
        if self.on_io is not None:
            self.on_io(self.cur_pc, "in", port, v)
        return v

    def _out(self, port, v):
        if not port & 1:
            self.border = v & 7
            b = (v >> 4) & 1
            if b != self.beeper:
                self.beeper_toggles += 1
            self.beeper = b
        if (port & 0xC002) == 0xC000:
            self.ay_sel = v & 15
        elif (port & 0xC002) == 0x8000:
            self.ay[self.ay_sel] = v
        if self.on_io is not None:
            self.on_io(self.cur_pc, "out", port, v)

    # --- teclado --------------------------------------------------------------
    def press(self, *names):
        for n in names:
            r, b = KEY_POS[n.upper()]
            self.keys[r] &= ~(1 << b)

    def release(self, *names):
        for n in names:
            r, b = KEY_POS[n.upper()]
            self.keys[r] |= 1 << b

    def release_all(self):
        self.keys = [0x1F] * 8
        self.kempston = 0

    # --- estado ---------------------------------------------------------------
    def load_state(self, st: ZXState):
        c = self.cpu
        self.mem[0x4000:0x10000] = st.memory64k()[0x4000:]
        for k in ("AF", "BC", "DE", "HL", "IX", "IY", "SP", "PC"):
            c.set_pair(k, st.regs[k])
        for k, (hi, lo) in (("AF'", (7, 6)), ("BC'", (0, 1)), ("DE'", (2, 3)), ("HL'", (4, 5))):
            c.alt[hi] = st.regs[k] >> 8
            c.alt[lo] = st.regs[k] & 0xFF
        c.i = st.regs["I"]
        c.r = st.regs["R"]
        c.iff1, c.iff2, c.im = st.iff1, st.iff2, st.im
        c.halted = False
        self.border = st.border

    def save_state(self) -> ZXState:
        c = self.cpu
        s = c.state()
        regs = {k: s[k] for k in ("AF", "BC", "DE", "HL", "AF'", "BC'", "DE'", "HL'", "IX", "IY",
                                  "SP", "PC", "I", "R")}
        return ZXState(bytearray(self.mem[0x4000:]), regs, c.iff1, c.iff2, c.im, self.border)

    # --- ejecución -------------------------------------------------------------
    def run_frame(self):
        """Ejecuta un frame completo (interrupción al principio)."""
        c = self.cpu
        step = c.step
        traps = self.traps
        t = self.t_in_frame
        # la línea INT está activa ~32 T-states
        int_done = False
        while t < FRAME_T:
            if not int_done and t < 32:
                took = c.interrupt(0xFF)
                if took:
                    int_done = True
                    t += took
                    continue
            pc = c.pc
            if pc in traps and not c.halted:
                if self.tracer is not None:
                    self.tracer(pc)
                t += traps[pc]()
                continue
            self.cur_pc = pc
            if self.tracer is not None:
                self.tracer(pc)
            t += step()
            if c.halted and t >= 32:
                # saltar hasta el final del frame (el HALT solo se rompe con INT)
                t = max(t, FRAME_T)
        self.t_in_frame = t - FRAME_T
        self.frame += 1

    def run_frames(self, n, keys_script=None):
        for i in range(n):
            if keys_script:
                keys_script(self, self.frame)
            self.run_frame()

    # --- trampas HLE (solo con mini-ROM) ------------------------------------------
    def _ret(self):
        self.cpu.pc = self.cpu.pop()

    def _install_hle_traps(self):
        c = self.cpu
        m = self.mem

        def keyboard():
            # LAST_K / FLAGS: tecla pulsada (muy simplificado)
            for r in range(8):
                row = self.keys[r]
                for b in range(5):
                    if not row & (1 << b):
                        name = ZX_KEYS[r][b]
                        if len(name) == 1:
                            m[0x5C08] = ord(name)
                            m[0x5C3B] |= 0x20
                        elif name == "ENTER":
                            m[0x5C08] = 13
                            m[0x5C3B] |= 0x20
            self._ret()
            return 100

        def beeper():
            # HL = periodo, DE = duración (ciclos): consumimos un tiempo similar
            de = c.get_de()
            hl = c.get_hl()
            self.beeper_toggles += 2 * de
            self._ret()
            return min(FRAME_T, de * (hl * 4 + 60) // 2 + 100)

        def cls():
            attr = m[0x5C8D]
            m[0x4000:0x5800] = bytes(6144)
            m[0x5800:0x5B00] = bytes([attr]) * 768
            self._ret()
            return 20000

        def print_a():
            self._print_char(c.R[7])
            self._ret()
            return 500

        def pr_string():
            de, bc = c.get_de(), c.get_bc()
            for k in range(bc):
                self._print_char(m[(de + k) & 0xFFFF])
            c.set_pair("DE", de + bc)
            c.set_pair("BC", 0)
            self._ret()
            return 500 * max(1, bc)

        def nop_ret():
            self._ret()
            return 20

        def key_scan():
            # devuelve E = código de tecla (0xFF = ninguna) como KEY-SCAN
            code = 0xFF
            for r in range(8):
                for b in range(5):
                    if not self.keys[r] & (1 << b):
                        code = r | ((4 - b) << 3)
            c.R[3] = code & 0xFF
            c.R[2] = 0xFF
            c.R[6] |= 0x40
            self._ret()
            return 1000

        def ld_bytes():
            return self._trap_ld_bytes()

        self.traps = {
            0x1FF4: keyboard, 0x03B5: beeper, 0x0D6B: cls, 0x0DAF: cls, 0x1FF2: print_a,
            0x203C: pr_string, 0x1601: nop_ret, 0x0D6E: nop_ret, 0x028E: key_scan,
            0x0556: ld_bytes, 0x1FF0: nop_ret,
        }

        # cualquier CALL a una rutina ROM no emulada: RET inmediato (se registra)
        def generic(addr):
            def f():
                self._ret()
                return 50
            return f

        for addr in ROM_ROUTINES:
            if 0x40 <= addr < 0x3D00 and addr not in self.traps:
                self.traps[addr] = generic(addr)

    def _print_char(self, ch):
        # impresión mínima: usa la posición en DF_CC (0x5C84) y la fuente CHARS
        m = self.mem
        if ch < 32 or ch > 127:
            return
        pos = m[0x5C84] | m[0x5C85] << 8
        if not 0x4000 <= pos < 0x5800:
            pos = 0x4000
        chars = (m[0x5C36] | m[0x5C37] << 8) + ch * 8
        for k in range(8):
            m[pos + k * 256 & 0xFFFF] = m[(chars + k) & 0xFFFF]
        pos += 1
        m[0x5C84], m[0x5C85] = pos & 0xFF, pos >> 8

    def _trap_ld_bytes(self):
        """LD-BYTES: A=flag, IX=destino, DE=longitud, CF=1 carga. Carga instantánea."""
        c = self.cpu
        R = c.R
        ok = False
        while self.tape_pos < len(self.tape_blocks):
            blk = self.tape_blocks[self.tape_pos]
            self.tape_pos += 1
            if blk.flag != R[7]:
                continue
            ix = c.get_ix()
            de = c.get_de()
            n = min(de, len(blk.data))
            for k in range(n):
                self._wb((ix + k) & 0xFFFF, blk.data[k])
            c.set_pair("IX", ix + n)
            c.set_pair("DE", de - n)
            ok = n == de
            break
        R[6] = (R[6] & ~1) | (1 if ok else 0)
        self._ret()
        return 1000

    # --- vídeo ----------------------------------------------------------------------
    def screen_rgb(self, border=32, flash_phase=0):
        m = self.mem
        w, h = 256 + 2 * border, 192 + 2 * border
        bc = ZX_RGB[self.border]
        rows = []
        brow = bytes(bc) * w
        for _ in range(border):
            rows.append(brow)
        for y in range(192):
            row = bytearray(bytes(bc) * border)
            base = 0x4000 | ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2)
            abase = 0x5800 + (y >> 3) * 32
            for cx in range(32):
                bits = m[base + cx]
                at = m[abase + cx]
                ink = (at & 7) | ((at >> 3) & 8)
                paper = ((at >> 3) & 7) | ((at >> 3) & 8)
                if at & 0x80 and flash_phase:
                    ink, paper = paper, ink
                ci, cp = ZX_RGB[ink], ZX_RGB[paper]
                for b in range(7, -1, -1):
                    row += bytes(ci if bits >> b & 1 else cp)
            row += bytes(bc) * border
            rows.append(bytes(row))
        for _ in range(border):
            rows.append(brow)
        return w, h, rows

    def screenshot(self, path, border=32):
        w, h, rows = self.screen_rgb(border)
        return write_png(path, w, h, rows)
