"""Análisis dinámico: ejecuta el programa en la máquina emulada y observa.

Registra qué instrucciones se ejecutan, qué puertos se leen/escriben y desde
dónde, qué instrucciones escriben en la memoria de vídeo, llamadas a la ROM /
firmware, lecturas de datos de ROM, código automodificable, uso de pila y de
memoria. Para explorar más código, "juega" pulsando teclas según un guion.
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..z80 import decode as D
from ..z80.decode import decode


@dataclass
class Trace:
    platform: str
    frames: int = 0
    executed: set = field(default_factory=set)
    exec_count: Counter = field(default_factory=Counter)
    io: dict = field(default_factory=lambda: defaultdict(Counter))       # pc -> (dir,port)->n
    screen_writes: dict = field(default_factory=lambda: defaultdict(Counter))  # pc -> region->n
    screen_same: Counter = field(default_factory=Counter)  # pc -> escrituras que no cambian el byte
    screen_reads: Counter = field(default_factory=Counter)  # pc -> lecturas de la pantalla
    block_starts: Counter = field(default_factory=Counter)  # pc -> veces que empieza un LDIR/LDDR
    first_bytes: dict = field(default_factory=dict)   # pc -> bytes de la 1ª ejecución
    rom_writes: Counter = field(default_factory=Counter)  # pc -> escrituras en la ROM
    written: bytearray = field(default_factory=lambda: bytearray(65536))  # 1 = escrito
    written_block: bytearray = field(default_factory=lambda: bytearray(65536))  # por LDIR/LDDR...
    read_rom: dict = field(default_factory=lambda: defaultdict(Counter))  # pc -> página->n
    rom_calls: dict = field(default_factory=lambda: defaultdict(Counter))  # pc origen -> destino->n
    smc: dict = field(default_factory=lambda: defaultdict(set))          # pc escritor -> dirs de código
    low_writes: dict = field(default_factory=lambda: defaultdict(set))   # pc -> dirs < $40 escritas
    int_modes: Counter = field(default_factory=Counter)
    i_values: Counter = field(default_factory=Counter)
    isr_entries: Counter = field(default_factory=Counter)
    halts: Counter = field(default_factory=Counter)
    sp_min: int = 0xFFFF
    sp_max: int = 0
    sp_pages: set = field(default_factory=set)     # páginas de 256 bytes usadas por la pila
    stack_in_screen: Counter = field(default_factory=Counter)
    beeper_toggles: int = 0
    screenshots: list = field(default_factory=list)
    final_state: object = None
    first_screen_write_frame: int | None = None
    notes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Guion de "juego" para explorar
# ---------------------------------------------------------------------------

def explore_script(platform, seed=1, start_keys=None):
    """Devuelve f(machine, frame) que pulsa teclas para avanzar menús y moverse."""
    rnd = random.Random(seed)
    if platform == "zx":
        menu = start_keys or ["ENTER", "SPACE", "0", "1", "S", "P", "J", "K", "5", "4", "2"]
        moves = ["Q", "A", "O", "P", "M", "SPACE", "6", "7", "8", "9", "0", "Z", "X", "N",
                 "CAPS", "SYM", "ENTER", "1", "2", "3", "4", "5"]
    else:
        menu = start_keys or ["SPACE", "RETURN", "1", "FIRE1", "0", "S", "ENTER", "2", "J"]
        moves = ["JOYUP", "JOYDOWN", "JOYLEFT", "JOYRIGHT", "FIRE1", "FIRE2", "Q", "A", "O",
                 "P", "SPACE", "CURUP", "CURDOWN", "CURLEFT", "CURRIGHT", "Z", "X", "M", "1"]
    state = {"held": []}

    def script(m, frame):
        # fase 1: menús (una tecla cada 40 frames, pulsada 24: algunos juegos solo
        # miran el teclado entre nota y nota de la música del título)
        if frame < len(menu) * 40:
            k, ph = divmod(frame, 40)
            m.release_all()
            if 12 <= ph < 36:
                m.press(menu[k])
            return
        # fase 2: movimientos aleatorios, cambiando cada 8-20 frames
        if frame % 12 == 0:
            m.release_all()
            state["held"] = rnd.sample(moves, rnd.choice([1, 1, 2]))
            if platform == "zx" and rnd.random() < 0.5:
                m.kempston = rnd.choice([1, 2, 4, 8, 16, 17, 18, 20, 24])
        for k in state["held"]:
            m.press(k)
    return script


# ---------------------------------------------------------------------------
# Trazador
# ---------------------------------------------------------------------------

_WRITE_ONLY = {"LD"}


def _read_addr_fn(ins: D.Instr):
    """Devuelve f(cpu)->dirección leída, o None si la instrucción no lee memoria."""
    op = ins.op
    ops = ins.operands
    if ins.prefix_only or op == "DB":
        return None
    if op in ("LDI", "LDD", "LDIR", "LDDR", "CPI", "CPD", "CPIR", "CPDR", "OUTI", "OUTD",
              "OTIR", "OTDR"):
        return lambda c: c.get_hl()
    if op in ("RLD", "RRD"):
        return lambda c: c.get_hl()
    if op in ("POP", "RET", "RETI", "RETN"):
        return None
    srcs = list(ops)
    if op == "LD" and len(ops) == 2:
        srcs = [ops[1]]        # el destino de LD no se lee
    for o in srcs:
        if o.kind == D.IND_REG and o.value in ("HL", "BC", "DE"):
            reg = o.value
            return lambda c, reg=reg: c.get_pair(reg)
        if o.kind == D.IDX:
            reg, d = o.value
            return lambda c, reg=reg, d=d: (c.get_pair(reg) + d) & 0xFFFF
        if o.kind == D.IND_IMM:
            a = o.value
            return lambda c, a=a: a
    return None


class Tracer:
    def __init__(self, machine, platform, trace: Trace, screen_range, rom_range):
        self.m = machine
        self.cpu = machine.cpu
        self.platform = platform
        self.t = trace
        self.cache = {}
        self.owner = {}           # byte -> pc de la instrucción cacheada
        self.last_pc = None
        self.scr_lo, self.scr_hi, self.attr_hi = screen_range
        self.paged_screen = True if hasattr(machine, "p7ffd") else None
        self.rom_lo, self.rom_hi = rom_range
        # ¿se está ejecutando código de ROM? (firmware del CPC / ROM del Spectrum)
        if platform == "cpc":
            self.in_rom = lambda pc: (pc < 0x4000 and machine._rom_lo_on) or \
                (pc >= 0xC000 and machine._rom_hi_on)
        else:
            self.in_rom = lambda pc: pc < 0x4000
        machine.tracer = self.on_step
        machine.on_write = self.on_write
        if hasattr(machine, "on_rom_write"):
            machine.on_rom_write = self.on_rom_write
        machine.on_io = self.on_io

    def _decode(self, pc):
        ins = self.cache.get(pc)
        if ins is None:
            ins = decode(self.cpu.mem, pc)
            rf = _read_addr_fn(ins)
            self.cache[pc] = (ins, rf)
            for k in range(ins.length):
                self.owner[(pc + k) & 0xFFFF] = pc
        return self.cache[pc]

    def on_step(self, pc):
        t = self.t
        if self.in_rom(pc):
            last = self.last_pc
            if last is not None and self.platform == "zx" and last >= 0x4000:
                t.rom_calls[last][pc] += 1
            self.last_pc = pc
            return
        if pc not in t.executed:
            t.first_bytes[pc] = bytes(self.cpu.mem[pc:pc + 4])     # tal como se ejecutó
        t.executed.add(pc)
        t.exec_count[pc] += 1
        entry = self.cache.get(pc)
        if entry is None:
            entry = self._decode(pc)
        ins, rf = entry
        c = self.cpu
        last = self.last_pc
        if last != pc and ins.op in ("LDIR", "LDDR"):
            t.block_starts[pc] += 1         # una copia nueva (no una repetición)
        if last is not None and self.platform == "cpc":
            if 0xB900 <= pc < 0xBE00 and not 0xB900 <= last < 0xBE00 and not self.in_rom(last):
                t.rom_calls[last][pc] += 1
        if rf is not None:
            a = rf(c)
            if self.rom_lo <= a < self.rom_hi and pc >= self.rom_hi:
                t.read_rom[pc][a & 0xFF00] += 1
            elif self.scr_lo <= a < self.attr_hi and not self.in_rom(pc):
                t.screen_reads[pc] += 1
        if ins.op == "HALT":
            t.halts[pc] += 1
        sp = c.sp
        t.sp_pages.add(sp >> 8)
        if sp < t.sp_min:
            t.sp_min = sp
        if sp > t.sp_max:
            t.sp_max = sp
        self.last_pc = pc

    def on_rom_write(self, pc, a):
        if not self.in_rom(pc):
            self.t.rom_writes[pc] += 1      # el juego cuenta con que la ROM no se escribe

    def on_write(self, pc, a, v):
        t = self.t
        if self.in_rom(pc):
            return          # escrituras del firmware/ROM: no son del juego
        ent = self.cache.get(pc)
        if ent is not None and ent[0].op in ("LDIR", "LDDR", "LDI", "LDD"):
            t.written_block[a] = 1
        else:
            t.written[a] = 1
        if a < 0x40:
            t.low_writes[pc].add(a)
        sa = a
        if a >= 0xC000 and self.paged_screen is not None:
            # 128K: las pantallas 0 (banco 5) y 1 (banco 7) también se escriben por $C000
            if (self.m.p7ffd & 7) in (5, 7) and a < 0xDB00:
                sa = a - 0x8000
        if self.scr_lo <= sa < self.attr_hi:
            region = "bitmap" if sa < self.scr_hi else "attr"
            t.screen_writes[pc][region] += 1
            if self.cpu.mem[a] == v:
                t.screen_same[pc] += 1
            if t.first_screen_write_frame is None:
                t.first_screen_write_frame = t.frames
            if self.cpu.sp - 2 <= a <= self.cpu.sp + 1:
                t.stack_in_screen[pc] += 1
        o = self.owner.get(a)
        if o is not None:
            # código modificado: invalidar caché y anotar si ya se había ejecutado
            if o in t.executed:
                t.smc[pc].add(o)
            self.cache.pop(o, None)
            ins_len = 4
            for k in range(ins_len):
                if self.owner.get((o + k) & 0xFFFF) == o:
                    del self.owner[(o + k) & 0xFFFF]

    def on_io(self, pc, direction, port, v):
        if self.in_rom(pc):
            return
        self.t.io[pc][(direction, port)] += 1


def run_dynamic(program, frames=300, rom=None, seed=1, screenshot_prefix=None,
                screenshot_every=0, start_keys=None, cpc_roms=None, progress=None,
                script=None) -> Trace:
    """Ejecuta ``program`` durante ``frames`` frames registrando su comportamiento."""
    trace = Trace(program.platform)
    if program.platform == "zx":
        from ..machines.spectrum import Spectrum48K, Spectrum128
        st = program.zx_state
        if st is not None and st.model == "128k" and st.banks:
            m = Spectrum128(None, rom)          # sin la ROM del editor: se usa la de 48K
            m.load_state(st)
        else:
            m = Spectrum48K(rom)
            m.mem[0x4000:] = program.mem[0x4000:]
            _set_regs(m.cpu, program)
        Tracer(m, "zx", trace, (0x4000, 0x5800, 0x5B00), (0x0000, 0x4000))
        if program.im == 2:
            trace.int_modes[2] += 1
    else:
        from ..machines.cpc import CPC
        lower = upper = None
        if cpc_roms:
            lower, upper = cpc_roms
        m = CPC(lower, upper)
        st = program.to_cpc_state()
        m.load_state(st)
        base = ((m.crtc[12] >> 4) & 3) * 0x4000
        Tracer(m, "cpc", trace, (base, base + 0x4000, base + 0x4000), (0x0000, 0x0000))
    explore = explore_script(program.platform, seed, start_keys)
    if script:
        # guion del usuario [(desde, hasta, [teclas])] y después exploración al azar
        user = script
        end = max(b for _a, b, _k in user)

        def script(m, f, _e=explore):
            if f < end:
                m.release_all()
                for a, b, ks in user:
                    if a <= f < b:
                        for k in ks:
                            m.press(k)
            else:
                _e(m, f - end + 10 ** 6)
    else:
        script = explore
    cpu = m.cpu
    orig_interrupt = cpu.interrupt
    tracer = m.tracer.__self__

    def interrupt(data=0xFF):
        t = orig_interrupt(data)
        if t:
            tracer.last_pc = None       # la entrada a la ROM no es una llamada del juego
            trace.int_modes[cpu.im] += 1
            if cpu.im == 2:
                trace.i_values[cpu.i] += 1
            trace.isr_entries[cpu.pc] += 1
        return t
    cpu.interrupt = interrupt
    for f in range(frames):
        script(m, f)
        m.run_frame()
        trace.frames += 1
        if screenshot_prefix and screenshot_every and (f + 1) % screenshot_every == 0:
            path = f"{screenshot_prefix}_{f + 1:04d}.png"
            m.screenshot(path)
            trace.screenshots.append(path)
        if progress and f % 25 == 0:
            progress(f, frames)
    if screenshot_prefix:
        path = f"{screenshot_prefix}_final.png"
        m.screenshot(path)
        trace.screenshots.append(path)
    trace.beeper_toggles = getattr(m, "beeper_toggles", 0)
    trace.final_state = m.save_state()
    trace.machine = m
    return trace


def _set_regs(cpu, program):
    r = program.regs
    for k in ("AF", "BC", "DE", "HL", "IX", "IY", "SP", "PC"):
        cpu.set_pair(k, r[k])
    for k, (hi, lo) in (("AF'", (7, 6)), ("BC'", (0, 1)), ("DE'", (2, 3)), ("HL'", (4, 5))):
        cpu.alt[hi] = r[k] >> 8
        cpu.alt[lo] = r[k] & 0xFF
    cpu.i = r["I"]
    cpu.r = r["R"]
    cpu.iff1, cpu.iff2, cpu.im = program.iff1, program.iff2, program.im
