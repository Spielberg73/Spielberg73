"""Análisis estático y detección de "puntos calientes" de portabilidad.

Combina el trazado recursivo del código (desde el punto de entrada, la
rutina de interrupción y todo lo que se vio ejecutarse en el análisis
dinámico) con las observaciones dinámicas, y clasifica cada instrucción que
depende del hardware de la máquina de origen.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..z80 import decode as D
from ..z80.decode import decode

ZX_ROM_NAMES = None


def zx_rom_name(addr):
    global ZX_ROM_NAMES
    if ZX_ROM_NAMES is None:
        from ..machines.spectrum import ROM_ROUTINES
        ZX_ROM_NAMES = ROM_ROUTINES
    return ZX_ROM_NAMES.get(addr, f"ROM {addr:#06x}")


CPC_FIRMWARE = {
    0xBB00: "KM INITIALISE", 0xBB03: "KM RESET", 0xBB06: "KM WAIT CHAR", 0xBB09: "KM READ CHAR",
    0xBB18: "KM WAIT KEY", 0xBB1B: "KM READ KEY", 0xBB1E: "KM TEST KEY",
    0xBB24: "KM GET JOYSTICK", 0xBB4E: "TXT INITIALISE", 0xBB5A: "TXT OUTPUT",
    0xBB5D: "TXT WR CHAR", 0xBB6C: "TXT CLEAR WINDOW", 0xBB75: "TXT SET CURSOR",
    0xBB90: "TXT SET PEN", 0xBB96: "TXT SET PAPER", 0xBBBA: "GRA INITIALISE",
    0xBBC0: "GRA MOVE ABSOLUTE", 0xBBDE: "GRA SET PEN", 0xBBEA: "GRA PLOT ABSOLUTE",
    0xBBF6: "GRA LINE ABSOLUTE", 0xBBFF: "SCR INITIALISE", 0xBC0E: "SCR SET MODE",
    0xBC11: "SCR GET MODE", 0xBC14: "SCR CLEAR", 0xBC1A: "SCR CHAR POSITION",
    0xBC1D: "SCR DOT POSITION", 0xBC32: "SCR SET INK", 0xBC38: "SCR SET BORDER",
    0xBC77: "CAS IN OPEN", 0xBC7A: "CAS IN CLOSE", 0xBC83: "CAS IN DIRECT",
    0xBC8C: "CAS OUT OPEN", 0xBCA7: "SOUND RESET", 0xBCAA: "SOUND QUEUE",
    0xBCD7: "KL NEW FRAME FLY", 0xBD19: "MC WAIT FLYBACK", 0xBD1C: "MC SET MODE",
    0xBD37: "JUMP RESTORE",
}


@dataclass
class Hotspot:
    addr: int
    kind: str
    ins: D.Instr
    detail: dict = field(default_factory=dict)
    count: int = 0              # veces observada en ejecución (0 = solo estática)
    severity: str = "info"      # info / aviso / grave

    @property
    def text(self):
        return self.ins.text()


KIND_INFO = {
    # Spectrum
    "ula_out": ("Escritura en la ULA (borde / beeper)", "info"),
    "ula_in": ("Lectura de teclado (puerto $FE)", "info"),
    "kempston_in": ("Lectura de joystick Kempston ($1F)", "info"),
    "ay_io": ("Acceso al chip AY del 128K", "info"),
    "paging": ("Paginación de memoria del 128K ($7FFD)", "grave"),
    "floating_bus": ("Lectura de puerto sin dispositivo (bus flotante)", "aviso"),
    "rom_call": ("Llamada a una rutina de la ROM", "aviso"),
    "rom_read": ("Lectura de datos de la ROM", "aviso"),
    "halt": ("HALT (sincronización con el frame)", "info"),
    "im2": ("Cambio de modo de interrupción", "info"),
    "ld_i": ("LD I,A (vector de interrupciones IM 2)", "info"),
    "screen_write": ("Escritura en memoria de vídeo", "info"),
    "stack_screen": ("Escritura en vídeo usando la pila (PUSH)", "aviso"),
    "smc": ("Código automodificable", "aviso"),
    "block_io": ("E/S en bloque (INIR/OTIR...)", "aviso"),
    "io_unknown": ("E/S a puerto no determinado estáticamente", "aviso"),
    # CPC
    "fw_call": ("Llamada al firmware del CPC", "aviso"),
    "fw_rst": ("RST del firmware del CPC", "aviso"),
    "ga_out": ("Gate array (paleta / modo / ROMs)", "info"),
    "crtc_out": ("CRTC (geometría de pantalla)", "info"),
    "ppi_io": ("PPI 8255 (teclado / PSG / cinta)", "info"),
    "fdc_io": ("Controladora de disco", "grave"),
    "ram_bank": ("Banca de memoria del 6128", "grave"),
}


@dataclass
class Analysis:
    program: object
    trace: object
    instrs: dict
    targets: set
    hotspots: list
    stats: dict
    notes: list

    def by_kind(self, kind):
        return [h for h in self.hotspots if h.kind == kind]

    def kinds(self):
        return Counter(h.kind for h in self.hotspots)


# ---------------------------------------------------------------------------
# Trazado de código
# ---------------------------------------------------------------------------

def trace_code(mem, entries, platform, stop_below=0x4000, extra_known=()):
    """Descubre instrucciones siguiendo el flujo desde ``entries``."""
    instrs = {}
    targets = set()
    work = [e for e in entries if e is not None]
    work += list(extra_known)
    lo = stop_below if platform == "zx" else 0
    seen = set()
    while work:
        a = work.pop() & 0xFFFF
        while True:
            if a in seen:
                break
            if platform == "zx" and a < lo:
                break
            if platform == "cpc" and 0xB900 <= a < 0xC000:
                break          # jumpblock / RAM del firmware
            seen.add(a)
            ins = decode(mem, a)
            instrs[a] = ins
            fl = ins.flow
            if fl in ("jp", "jr", "djnz", "call") and ins.target is not None:
                targets.add(ins.target)
                work.append(ins.target)
            if fl == "rst":
                if platform == "zx" and ins.target in (0x08, 0x28):
                    break       # ERROR / calculadora: datos en línea
                if platform == "cpc":
                    if ins.target in (0x08, 0x28):
                        break   # LOW/FIRM JUMP: no vuelve
                    if ins.target in (0x10, 0x18):
                        a = (ins.next + 2) & 0xFFFF   # SIDE/FAR CALL: 2 bytes en línea
                        continue
            if ins.ends_block or fl == "jpind":
                break
            if fl in ("ret", "reti", "retn") and ins.cond is None:
                break
            a = ins.next
    return instrs, targets


# ---------------------------------------------------------------------------
# Propagación de constantes (muy local) para resolver puertos
# ---------------------------------------------------------------------------

_R8 = ("A", "B", "C", "D", "E", "H", "L")


def known_regs_before(instrs, ordered, idx, targets, max_back=20):
    """Valores conocidos de registros de 8 bits justo antes de ``ordered[idx]``."""
    start = idx
    while start > 0 and idx - start < max_back:
        prev = instrs[ordered[start - 1]]
        if prev.next != ordered[start]:
            break
        if prev.ends_block:
            break
        if ordered[start] in targets and start != idx:
            break
        start -= 1
    known = {}
    for k in range(start, idx):
        _sim(instrs[ordered[k]], known)
    return known


def _sim(ins, known):
    op, ops = ins.op, ins.operands
    if op == "LD" and len(ops) == 2:
        d, s = ops
        if d.kind == D.REG and d.value in _R8:
            if s.kind == D.IMM8:
                known[d.value] = s.value
            elif s.kind == D.REG and s.value in known and s.value in _R8:
                known[d.value] = known[s.value]
            else:
                known.pop(d.value, None)
            return
        if d.kind == D.REG16 and d.value in ("BC", "DE", "HL"):
            hi, lo = d.value[0], d.value[1]
            if s.kind == D.IMM16:
                known[hi], known[lo] = s.value >> 8, s.value & 0xFF
            else:
                known.pop(hi, None)
                known.pop(lo, None)
            return
    if op == "XOR" and ops and ops[0].kind == D.REG and ops[0].value == "A":
        known["A"] = 0
        return
    if op in ("INC", "DEC") and ops and ops[0].kind == D.REG and ops[0].value in known:
        r = ops[0].value
        known[r] = (known[r] + (1 if op == "INC" else -1)) & 0xFF
        return
    if op in ("INC", "DEC") and ops and ops[0].kind == D.REG16 and ops[0].value in ("BC", "DE", "HL"):
        hi, lo = ops[0].value[0], ops[0].value[1]
        if hi in known and lo in known:
            v = ((known[hi] << 8 | known[lo]) + (1 if op == "INC" else -1)) & 0xFFFF
            known[hi], known[lo] = v >> 8, v & 0xFF
        else:
            known.pop(hi, None)
            known.pop(lo, None)
        return
    # cualquier otra cosa: olvidar los registros que pueda modificar
    if op in ("OUT", "CP", "BIT", "PUSH", "NOP", "JR", "JP", "DJNZ", "HALT", "DI", "EI"):
        if op == "DJNZ":
            known.pop("B", None)
        return
    if op in ("EXX", "EX", "CALL", "RST", "LDIR", "LDDR", "LDI", "LDD", "OTIR", "INIR"):
        known.clear()
        return
    for o in ops[:1]:
        if o.kind == D.REG:
            known.pop(o.value, None)
        elif o.kind == D.REG16:
            for ch in o.value[:2]:
                known.pop(ch, None)
    if op in ("ADD", "ADC", "SUB", "SBC", "AND", "OR", "XOR", "NEG", "CPL", "RLA", "RRA",
              "RLCA", "RRCA", "DAA", "IN"):
        known.pop("A", None)


# ---------------------------------------------------------------------------
# Detección de puntos calientes
# ---------------------------------------------------------------------------

def analyze(program, trace=None, extra_entries=()):
    mem = program.mem
    plat = program.platform
    entries = [program.entry] + list(extra_entries)
    if trace is not None:
        entries += list(trace.isr_entries)
    if program.im == 2:
        v = (program.regs["I"] << 8) | 0xFF
        if v >= 0x4000 or plat == "cpc":
            entries.append(mem[v] | mem[(v + 1) & 0xFFFF] << 8)
    known = sorted(trace.executed) if trace is not None else []
    instrs, targets = trace_code(mem, entries, plat, extra_known=known)
    if trace is not None:
        for pc in trace.executed:
            if plat == "zx" and pc < 0x4000:
                continue
            if pc not in instrs:
                instrs[pc] = decode(mem, pc)
        # los destinos de saltos observados también son inicios de bloque
        for src, dsts in trace.rom_calls.items():
            targets.update(dsts)
    if plat == "zx":
        instrs = {a: i for a, i in instrs.items() if a >= 0x4000}
    ordered = sorted(instrs)
    pos = {a: k for k, a in enumerate(ordered)}
    hs = []
    notes = []

    def count_of(a):
        return trace.exec_count.get(a, 0) if trace is not None else 0

    def io_ports(a):
        if trace is None:
            return Counter()
        return trace.io.get(a, Counter())

    for a in ordered:
        ins = instrs[a]
        op = ins.op
        io = ins.io_kind()
        if io is not None:
            kinds = _classify_io(plat, ins, io, instrs, ordered, pos[a], targets, io_ports(a))
            for kind, det in kinds:
                hs.append(Hotspot(a, kind, ins, det, count_of(a)))
        if op == "HALT":
            hs.append(Hotspot(a, "halt", ins, {}, count_of(a)))
        if op == "IM":
            hs.append(Hotspot(a, "im2", ins, {"mode": ins.operands[0].value}, count_of(a)))
        if op == "LD" and ins.operands and ins.operands[0] == D.Operand(D.REG, "I"):
            hs.append(Hotspot(a, "ld_i", ins, {}, count_of(a)))
        if plat == "zx":
            if ins.flow in ("call", "jp", "rst") and ins.target is not None and ins.target < 0x4000:
                if not (ins.flow == "rst" and ins.target == 0x38):
                    hs.append(Hotspot(a, "rom_call", ins,
                                      {"target": ins.target, "name": zx_rom_name(ins.target)},
                                      count_of(a)))
        else:
            if ins.flow in ("call", "jp") and ins.target is not None and 0xB900 <= ins.target < 0xBE00:
                hs.append(Hotspot(a, "fw_call", ins,
                                  {"target": ins.target,
                                   "name": CPC_FIRMWARE.get(ins.target, f"firmware {ins.target:#06x}")},
                                  count_of(a)))
            elif ins.flow == "rst" and ins.target in (0x08, 0x10, 0x18, 0x20, 0x28):
                hs.append(Hotspot(a, "fw_rst", ins, {"target": ins.target}, count_of(a)))

    if trace is not None:
        # llamadas a ROM vistas dinámicamente desde instrucciones que no son CALL directos
        static_rom = {h.addr for h in hs if h.kind in ("rom_call", "fw_call")}
        for src, dsts in trace.rom_calls.items():
            if src in static_rom or src not in instrs:
                continue
            ins = instrs[src]
            if ins.flow in ("ret", "reti", "retn"):
                continue   # retorno al ROM (p.ej. desde una rutina llamada por la ROM)
            for dst, n in dsts.items():
                name = zx_rom_name(dst) if plat == "zx" else CPC_FIRMWARE.get(dst, f"{dst:#06x}")
                hs.append(Hotspot(src, "rom_call" if plat == "zx" else "fw_call", ins,
                                  {"target": dst, "name": name, "indirect": True}, n))
        for pc, pages in trace.read_rom.items():
            if pc in instrs:
                hs.append(Hotspot(pc, "rom_read", instrs[pc],
                                  {"pages": sorted(pages)}, sum(pages.values())))
        for pc, regions in trace.screen_writes.items():
            if pc in instrs:
                ins = instrs[pc]
                kind = "stack_screen" if (trace.stack_in_screen.get(pc) or
                                          (ins.mem_write_kind() or ("",))[0] == "stack") \
                    else "screen_write"
                hs.append(Hotspot(pc, kind, ins,
                                  {"regions": dict(regions), "form": _write_form(ins)},
                                  sum(regions.values())))
        for pc, code_addrs in trace.smc.items():
            if pc in instrs:
                hs.append(Hotspot(pc, "smc", instrs[pc],
                                  {"modifies": sorted(code_addrs)[:32]}, len(code_addrs)))

    for h in hs:
        h.severity = KIND_INFO.get(h.kind, ("", "info"))[1]
    stats = _stats(program, trace, instrs, hs)
    notes += _advice(program, trace, hs, stats)
    return Analysis(program, trace, instrs, targets, hs, stats, notes)


def _write_form(ins):
    """Forma canónica de la instrucción de escritura (para elegir el parche)."""
    wk = ins.mem_write_kind()
    if wk is None:
        return None
    mode, det = wk
    if mode == "ind":
        src = ins.operands[1].text() if ins.op == "LD" and len(ins.operands) > 1 else ins.op
        return f"{ins.op} ({det}),{src}" if ins.op == "LD" else f"{ins.op} ({det})"
    if mode == "idx":
        return f"{ins.op} (IDX)"
    if mode == "abs":
        return f"{ins.op} (nn)"
    if mode == "block":
        return det
    return mode


def _classify_io(plat, ins, io, instrs, ordered, idx, targets, observed):
    direction, form, val = io
    out = []
    ports = set()
    if form == "n":
        # IN A,(n) / OUT (n),A: el byte alto es A
        known = known_regs_before(instrs, ordered, idx, targets)
        hi = known.get("A")
        ports.add((hi << 8 | val) if hi is not None else (None, val))
    elif form == "c":
        known = known_regs_before(instrs, ordered, idx, targets)
        b, c = known.get("B"), known.get("C")
        if b is not None and c is not None:
            ports.add(b << 8 | c)
        elif c is not None:
            ports.add((None, c))
    for (d, p), n in observed.items():
        ports.add(p)
    if form == "block":
        out.append(("block_io", {"op": val}))
    kinds = set()
    for p in ports or {None}:
        lo = p[1] if isinstance(p, tuple) else (p & 0xFF if p is not None else None)
        full = p if isinstance(p, int) else None
        if plat == "zx":
            if lo is None:
                kinds.add("io_unknown")
            elif full is not None and (full & 0x8002) == 0 and (full >> 8) & 0x7F == 0x7F \
                    and full & 0xFF == 0xFD:
                kinds.add("paging")
            elif full is not None and full in (0xFFFD, 0xBFFD):
                kinds.add("ay_io")
            elif full is not None and full == 0x7FFD:
                kinds.add("paging")
            elif not lo & 1:
                kinds.add("ula_out" if direction == "out" else "ula_in")
            elif lo == 0x1F and direction == "in":
                kinds.add("kempston_in")
            elif lo == 0xFD and direction == "out":
                kinds.add("ay_io")
            elif direction == "in":
                kinds.add("floating_bus")
            else:
                kinds.add("io_unknown")
        else:
            hi = full >> 8 if full is not None else None
            if hi is None:
                kinds.add("io_unknown")
            elif hi & 0xC0 == 0x40:
                kinds.add("ga_out")
            elif not hi & 0x40:
                kinds.add("crtc_out")
            elif not hi & 0x08:
                kinds.add("ppi_io")
            elif hi in (0xFA, 0xFB):
                kinds.add("fdc_io")
            else:
                kinds.add("io_unknown")
    for k in sorted(kinds):
        out.append((k, {"ports": sorted(f"{p:#06x}" if isinstance(p, int) else
                                        f"??{p[1]:02x}" if isinstance(p, tuple) else "?"
                                        for p in ports), "direction": direction, "form": form}))
    return out


def _stats(program, trace, instrs, hs):
    code_bytes = sum(i.length for i in instrs.values())
    st = {"instructions": len(instrs), "code_bytes": code_bytes,
          "hotspots": len(hs), "by_kind": dict(Counter(h.kind for h in hs))}
    if trace is not None:
        st.update({
            "frames": trace.frames,
            "executed": len(trace.executed),
            "int_modes": dict(trace.int_modes),
            "i_values": dict(trace.i_values),
            "sp_range": (trace.sp_min, trace.sp_max),
            "written_bytes": sum(trace.written),
            "beeper_toggles": trace.beeper_toggles,
        })
    return st


def _advice(program, trace, hs, stats):
    notes = []
    kinds = Counter(h.kind for h in hs)
    if program.platform == "zx":
        if kinds.get("paging"):
            notes.append("El juego usa paginación de 128K: el port a CPC solo es viable si la "
                         "memoria extra se puede reorganizar a mano.")
        if kinds.get("rom_read"):
            notes.append("El juego lee datos de la ROM (fuente, tablas o números aleatorios). "
                         "En el CPC esa zona contiene la pantalla: revisa las instrucciones "
                         "marcadas (p.ej. fuente en $3D00).")
        if kinds.get("stack_screen"):
            notes.append("Hay volcados a pantalla con PUSH: no se pueden reflejar al vuelo; "
                         "dependerán del refresco de fondo.")
        if kinds.get("smc"):
            notes.append("Hay código automodificable: si modifica instrucciones parcheadas, "
                         "el parche se perdería. Revisa la lista.")
        if trace is not None and trace.executed and not any(
                h.kind in ("ula_in", "kempston_in") and h.count for h in hs):
            notes.append("No se observó lectura de teclado durante el análisis: puede que el "
                         "guion no llegara a la parte jugable. Prueba con más frames.")
    else:
        if kinds.get("fw_call") or kinds.get("fw_rst"):
            notes.append("El juego usa el firmware del CPC: el port necesita reimplementar "
                         "esas llamadas (el portador incluye las más comunes).")
        if kinds.get("ram_bank") or kinds.get("fdc_io"):
            notes.append("El juego accede a la controladora de disco o a la banca del 6128.")
    if trace is not None and trace.executed:
        cov = stats.get("executed", 0)
        notes.append(f"Cobertura dinámica: {cov} instrucciones distintas ejecutadas en "
                     f"{trace.frames} frames.")
    return notes
