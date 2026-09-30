"""Emulador de CPU Z80 en Python puro.

Incluye flags no documentados (bits 3 y 5), MEMPTR/WZ, instrucciones
no documentadas (IXH/IXL, SLL, DDCB con copia a registro) y tiempos en
T-states. Está pensado para análisis dinámico y pruebas, no para velocidad
real: ~0,5-1 M instrucciones/segundo en CPython.

Las máquinas que lo usan conectan:

* ``cpu.mem``    bytearray de 64K (lecturas directas)
* ``cpu.wb(a,v)`` escritura de memoria (permite ROM, espejos, trazas...)
* ``cpu.inp(port) -> int`` y ``cpu.outp(port, v)`` para E/S
"""

from __future__ import annotations

# Índices en cpu.R
B, C, D, E, H, L, F, A = range(8)
IXH, IXL, IYH, IYL = 8, 9, 10, 11

FS, FZ, FY, FH, FX, FP, FN, FC = 0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01

SZ53 = [0] * 256
SZ53P = [0] * 256
PARITY = [0] * 256
for _i in range(256):
    _v = (_i & (FS | FY | FX)) | (FZ if _i == 0 else 0)
    _p = FP if bin(_i).count("1") % 2 == 0 else 0
    SZ53[_i] = _v
    SZ53P[_i] = _v | _p
    PARITY[_i] = _p


class Z80:
    def __init__(self, mem: bytearray | None = None):
        self.mem = mem if mem is not None else bytearray(65536)
        self.R = [0] * 12
        self.R[A] = 0xFF
        self.R[F] = 0xFF
        self.alt = [0] * 8          # B' C' D' E' H' L' F' A'
        self.sp = 0xFFFF
        self.pc = 0
        self.i = 0
        self.r = 0
        self.iff1 = self.iff2 = 0
        self.im = 0
        self.halted = False
        self.wz = 0
        self.ei_delay = False
        self.cycles = 0
        self.wb = self._default_wb
        self.inp = lambda port: 0xFF
        self.outp = lambda port, v: None
        self._build()

    # --- utilidades ---------------------------------------------------------
    def _default_wb(self, a, v):
        self.mem[a] = v

    def get_bc(self):
        return self.R[B] << 8 | self.R[C]

    def get_de(self):
        return self.R[D] << 8 | self.R[E]

    def get_hl(self):
        return self.R[H] << 8 | self.R[L]

    def get_af(self):
        return self.R[A] << 8 | self.R[F]

    def get_ix(self):
        return self.R[IXH] << 8 | self.R[IXL]

    def get_iy(self):
        return self.R[IYH] << 8 | self.R[IYL]

    def set_pair(self, name, v):
        v &= 0xFFFF
        hi, lo = v >> 8, v & 0xFF
        R = self.R
        if name == "BC":
            R[B], R[C] = hi, lo
        elif name == "DE":
            R[D], R[E] = hi, lo
        elif name == "HL":
            R[H], R[L] = hi, lo
        elif name == "AF":
            R[A], R[F] = hi, lo
        elif name == "IX":
            R[IXH], R[IXL] = hi, lo
        elif name == "IY":
            R[IYH], R[IYL] = hi, lo
        elif name == "SP":
            self.sp = v
        elif name == "PC":
            self.pc = v
        else:
            raise KeyError(name)

    def get_pair(self, name):
        return {
            "BC": self.get_bc, "DE": self.get_de, "HL": self.get_hl, "AF": self.get_af,
            "IX": self.get_ix, "IY": self.get_iy, "SP": lambda: self.sp, "PC": lambda: self.pc,
        }[name]()

    def state(self):
        R = self.R
        return {
            "AF": self.get_af(), "BC": self.get_bc(), "DE": self.get_de(), "HL": self.get_hl(),
            "IX": self.get_ix(), "IY": self.get_iy(), "SP": self.sp, "PC": self.pc,
            "AF'": self.alt[A] << 8 | self.alt[F], "BC'": self.alt[B] << 8 | self.alt[C],
            "DE'": self.alt[D] << 8 | self.alt[E], "HL'": self.alt[H] << 8 | self.alt[L],
            "I": self.i, "R": self.r & 0xFF, "IFF1": self.iff1, "IFF2": self.iff2, "IM": self.im,
            "halted": self.halted,
        }

    def push(self, v):
        sp = (self.sp - 1) & 0xFFFF
        self.wb(sp, (v >> 8) & 0xFF)
        sp = (sp - 1) & 0xFFFF
        self.wb(sp, v & 0xFF)
        self.sp = sp

    def pop(self):
        m = self.mem
        sp = self.sp
        v = m[sp] | (m[(sp + 1) & 0xFFFF] << 8)
        self.sp = (sp + 2) & 0xFFFF
        return v

    # --- ejecución ----------------------------------------------------------
    def step(self) -> int:
        """Ejecuta una instrucción y devuelve los T-states consumidos."""
        self.ei_delay = False
        if self.halted:
            self.r = (self.r & 0x80) | ((self.r + 1) & 0x7F)
            self.cycles += 4
            return 4
        pc = self.pc
        op = self.mem[pc]
        self.pc = (pc + 1) & 0xFFFF
        self.r = (self.r & 0x80) | ((self.r + 1) & 0x7F)
        t = self.main[op]()
        self.cycles += t
        return t

    def interrupt(self, data=0xFF) -> int:
        """Solicita una interrupción enmascarable. Devuelve T-states (0 si se ignora)."""
        if not self.iff1 or self.ei_delay:
            return 0
        if self.halted:
            self.halted = False
        self.iff1 = self.iff2 = 0
        self.r = (self.r & 0x80) | ((self.r + 1) & 0x7F)
        self.push(self.pc)
        if self.im == 2:
            v = (self.i << 8) | (data & 0xFF)
            m = self.mem
            self.pc = m[v] | (m[(v + 1) & 0xFFFF] << 8)
            t = 19
        else:
            self.pc = 0x38
            t = 13
        self.wz = self.pc
        self.cycles += t
        return t

    def nmi(self) -> int:
        self.halted = False
        self.iff1 = 0
        self.r = (self.r & 0x80) | ((self.r + 1) & 0x7F)
        self.push(self.pc)
        self.pc = 0x66
        self.wz = 0x66
        self.cycles += 11
        return 11

    def run(self, cycles: int) -> int:
        """Ejecuta al menos ``cycles`` T-states."""
        done = 0
        step = self.step
        while done < cycles:
            done += step()
        return done

    # --- construcción de tablas de despacho ----------------------------------
    def _build(self):
        self.main = _build_main(self, None)
        self.tab_ix = _build_main(self, "IX")
        self.tab_iy = _build_main(self, "IY")
        self.tab_cb = _build_cb(self)
        self.tab_ed = _build_ed(self)
        self.tab_xcb = {"IX": _build_idx_cb(self, "IX"), "IY": _build_idx_cb(self, "IY")}


# ---------------------------------------------------------------------------
# ALU compartida
# ---------------------------------------------------------------------------

def _alu_funcs(cpu):
    R = cpu.R

    def add(v, cy=0):
        a = R[A]
        res = a + v + cy
        r8 = res & 0xFF
        R[F] = SZ53[r8] | (res >> 8 & 1) | ((a ^ v ^ res) & FH) | \
            (FP if ((a ^ res) & (v ^ res) & 0x80) else 0)
        R[A] = r8

    def sub(v, cy=0, store=True):
        a = R[A]
        res = a - v - cy
        r8 = res & 0xFF
        f = (SZ53[r8] if store else (SZ53[r8] & ~(FY | FX)) | (v & (FY | FX))) | FN | \
            (1 if res < 0 else 0) | ((a ^ v ^ res) & FH) | \
            (FP if ((a ^ v) & (a ^ res) & 0x80) else 0)
        R[F] = f
        if store:
            R[A] = r8

    def op_alu(y, v):
        if y == 0:
            add(v)
        elif y == 1:
            add(v, R[F] & 1)
        elif y == 2:
            sub(v)
        elif y == 3:
            sub(v, R[F] & 1)
        elif y == 4:
            r = R[A] & v
            R[A] = r
            R[F] = SZ53P[r] | FH
        elif y == 5:
            r = R[A] ^ v
            R[A] = r
            R[F] = SZ53P[r]
        elif y == 6:
            r = R[A] | v
            R[A] = r
            R[F] = SZ53P[r]
        else:
            sub(v, 0, False)

    alus = [lambda v: add(v), lambda v: add(v, R[F] & 1), lambda v: sub(v),
            lambda v: sub(v, R[F] & 1), None, None, None, lambda v: sub(v, 0, False)]

    def _and(v):
        r = R[A] & v
        R[A] = r
        R[F] = SZ53P[r] | FH

    def _xor(v):
        r = R[A] ^ v
        R[A] = r
        R[F] = SZ53P[r]

    def _or(v):
        r = R[A] | v
        R[A] = r
        R[F] = SZ53P[r]

    alus[4], alus[5], alus[6] = _and, _xor, _or

    def inc8(v):
        r = (v + 1) & 0xFF
        R[F] = (R[F] & FC) | SZ53[r] | (FH if (v & 0xF) == 0xF else 0) | (FP if v == 0x7F else 0)
        return r

    def dec8(v):
        r = (v - 1) & 0xFF
        R[F] = (R[F] & FC) | SZ53[r] | FN | (FH if (v & 0xF) == 0 else 0) | (FP if v == 0x80 else 0)
        return r

    def rot(y, v):
        cy = R[F] & 1
        if y == 0:      # RLC
            c = v >> 7
            r = ((v << 1) | c) & 0xFF
        elif y == 1:    # RRC
            c = v & 1
            r = (v >> 1) | (c << 7)
        elif y == 2:    # RL
            c = v >> 7
            r = ((v << 1) | cy) & 0xFF
        elif y == 3:    # RR
            c = v & 1
            r = (v >> 1) | (cy << 7)
        elif y == 4:    # SLA
            c = v >> 7
            r = (v << 1) & 0xFF
        elif y == 5:    # SRA
            c = v & 1
            r = (v >> 1) | (v & 0x80)
        elif y == 6:    # SLL
            c = v >> 7
            r = ((v << 1) | 1) & 0xFF
        else:           # SRL
            c = v & 1
            r = v >> 1
        R[F] = SZ53P[r] | c
        return r

    return op_alu, alus, inc8, dec8, rot


# ---------------------------------------------------------------------------
# Tabla principal (sin prefijo o con DD/FD)
# ---------------------------------------------------------------------------

def _build_main(cpu, idx):
    R = cpu.R
    mem = cpu.mem
    _, alus, inc8, dec8, rot = _alu_funcs(cpu)
    HI = {None: H, "IX": IXH, "IY": IYH}[idx]
    LO = {None: L, "IX": IXL, "IY": IYL}[idx]
    extra = 0 if idx is None else 4    # ciclos del prefijo

    def f8():
        pc = cpu.pc
        v = mem[pc]
        cpu.pc = (pc + 1) & 0xFFFF
        return v

    def f16():
        pc = cpu.pc
        v = mem[pc] | (mem[(pc + 1) & 0xFFFF] << 8)
        cpu.pc = (pc + 2) & 0xFFFF
        return v

    def fd():
        v = f8()
        return v - 256 if v & 0x80 else v

    # dirección del operando de memoria: (HL) o (IX+d)
    if idx is None:
        def maddr():
            return R[H] << 8 | R[L]
    else:
        def maddr():
            d = fd()
            a = ((R[HI] << 8 | R[LO]) + d) & 0xFFFF
            cpu.wz = a
            return a

    def getrp(p):
        if p == 0:
            return lambda: R[B] << 8 | R[C]
        if p == 1:
            return lambda: R[D] << 8 | R[E]
        if p == 2:
            return lambda: R[HI] << 8 | R[LO]
        return lambda: cpu.sp

    def setrp(p):
        if p == 0:
            def s(v):
                R[B] = v >> 8
                R[C] = v & 0xFF
        elif p == 1:
            def s(v):
                R[D] = v >> 8
                R[E] = v & 0xFF
        elif p == 2:
            def s(v):
                R[HI] = v >> 8
                R[LO] = v & 0xFF
        else:
            def s(v):
                cpu.sp = v
        return s

    # índice del registro de 8 bits (con sustitución IXH/IXL) para r8[z]
    def ridx(z, subst=True):
        if z == 4 and subst:
            return HI
        if z == 5 and subst:
            return LO
        return [B, C, D, E, H, L, None, A][z]

    table = [None] * 256

    def prefix_dispatch(tab_name):
        def f():
            pc = cpu.pc
            op = mem[pc]
            cpu.pc = (pc + 1) & 0xFFFF
            cpu.r = (cpu.r & 0x80) | ((cpu.r + 1) & 0x7F)
            return getattr(cpu, tab_name)[op]()
        return f

    def cb_dispatch():
        if idx is None:
            def f():
                pc = cpu.pc
                op = mem[pc]
                cpu.pc = (pc + 1) & 0xFFFF
                cpu.r = (cpu.r & 0x80) | ((cpu.r + 1) & 0x7F)
                return cpu.tab_cb[op]()
        else:
            def f():
                pc = cpu.pc
                d = mem[pc]
                op = mem[(pc + 1) & 0xFFFF]
                cpu.pc = (pc + 2) & 0xFFFF
                if d & 0x80:
                    d -= 256
                a = ((R[HI] << 8 | R[LO]) + d) & 0xFFFF
                cpu.wz = a
                return cpu.tab_xcb[idx][op](a)
        return f

    for op in range(256):
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        p, q = y >> 1, y & 1
        fn = None
        if x == 0:
            if z == 0:
                if y == 0:
                    def fn():
                        return 4
                elif y == 1:
                    def fn():
                        alt = cpu.alt
                        R[A], alt[A] = alt[A], R[A]
                        R[F], alt[F] = alt[F], R[F]
                        return 4
                elif y == 2:
                    def fn():
                        d = fd()
                        b = (R[B] - 1) & 0xFF
                        R[B] = b
                        if b:
                            cpu.pc = (cpu.pc + d) & 0xFFFF
                            cpu.wz = cpu.pc
                            return 13
                        return 8
                elif y == 3:
                    def fn():
                        d = fd()
                        cpu.pc = (cpu.pc + d) & 0xFFFF
                        cpu.wz = cpu.pc
                        return 12
                else:
                    fn = _mk_jr_cc(cpu, fd, y - 4)
            elif z == 1:
                if q == 0:
                    s = setrp(p)

                    def fn(s=s):
                        s(f16())
                        return 10 + extra
                else:
                    g, gh, sh = getrp(p), getrp(2), setrp(2)

                    def fn(g=g, gh=gh, sh=sh):
                        hl = gh()
                        v = g()
                        res = hl + v
                        cpu.wz = (hl + 1) & 0xFFFF
                        R[F] = (R[F] & (FS | FZ | FP)) | ((res >> 8) & (FY | FX)) | \
                            (((hl ^ v ^ res) >> 8) & FH) | (res >> 16)
                        sh(res & 0xFFFF)
                        return 11 + extra
            elif z == 2:
                if q == 0:
                    if p == 0:
                        def fn():
                            a = R[B] << 8 | R[C]
                            cpu.wb(a, R[A])
                            cpu.wz = (R[A] << 8) | ((a + 1) & 0xFF)
                            return 7
                    elif p == 1:
                        def fn():
                            a = R[D] << 8 | R[E]
                            cpu.wb(a, R[A])
                            cpu.wz = (R[A] << 8) | ((a + 1) & 0xFF)
                            return 7
                    elif p == 2:
                        def fn():
                            a = f16()
                            cpu.wb(a, R[LO])
                            cpu.wb((a + 1) & 0xFFFF, R[HI])
                            cpu.wz = (a + 1) & 0xFFFF
                            return 16 + extra
                    else:
                        def fn():
                            a = f16()
                            cpu.wb(a, R[A])
                            cpu.wz = (R[A] << 8) | ((a + 1) & 0xFF)
                            return 13
                else:
                    if p == 0:
                        def fn():
                            a = R[B] << 8 | R[C]
                            R[A] = mem[a]
                            cpu.wz = (a + 1) & 0xFFFF
                            return 7
                    elif p == 1:
                        def fn():
                            a = R[D] << 8 | R[E]
                            R[A] = mem[a]
                            cpu.wz = (a + 1) & 0xFFFF
                            return 7
                    elif p == 2:
                        def fn():
                            a = f16()
                            R[LO] = mem[a]
                            R[HI] = mem[(a + 1) & 0xFFFF]
                            cpu.wz = (a + 1) & 0xFFFF
                            return 16 + extra
                    else:
                        def fn():
                            a = f16()
                            R[A] = mem[a]
                            cpu.wz = (a + 1) & 0xFFFF
                            return 13
            elif z == 3:
                g, s = getrp(p), setrp(p)
                dlt = 1 if q == 0 else -1

                def fn(g=g, s=s, dlt=dlt):
                    s((g() + dlt) & 0xFFFF)
                    return 6 + extra
            elif z in (4, 5):
                func = inc8 if z == 4 else dec8
                if y == 6:
                    def fn(func=func):
                        a = maddr()
                        cpu.wb(a, func(mem[a]))
                        return 11 if idx is None else 23
                else:
                    ri = ridx(y)

                    def fn(func=func, ri=ri):
                        R[ri] = func(R[ri])
                        return 4 + extra
            elif z == 6:
                if y == 6:
                    def fn():
                        a = maddr()
                        cpu.wb(a, f8())
                        return 10 if idx is None else 19
                else:
                    ri = ridx(y)

                    def fn(ri=ri):
                        R[ri] = f8()
                        return 7 + extra
            else:
                fn = _mk_acc_op(cpu, y)
        elif x == 1:
            if op == 0x76:
                def fn():
                    cpu.halted = True
                    return 4
            elif y == 6:
                ri = ridx(z, False)

                def fn(ri=ri):
                    a = maddr()
                    cpu.wb(a, R[ri])
                    return 7 if idx is None else 19
            elif z == 6:
                ri = ridx(y, False)

                def fn(ri=ri):
                    R[ri] = mem[maddr()]
                    return 7 if idx is None else 19
            else:
                di, si = ridx(y), ridx(z)

                def fn(di=di, si=si):
                    R[di] = R[si]
                    return 4 + extra
        elif x == 2:
            alu = alus[y]
            if z == 6:
                def fn(alu=alu):
                    alu(mem[maddr()])
                    return 7 if idx is None else 19
            else:
                si = ridx(z)

                def fn(alu=alu, si=si):
                    alu(R[si])
                    return 4 + extra
        else:
            if z == 0:
                fn = _mk_ret_cc(cpu, y)
            elif z == 1:
                if q == 0:
                    if p == 3:
                        def fn():
                            v = cpu.pop()
                            R[A] = v >> 8
                            R[F] = v & 0xFF
                            return 10
                    else:
                        s = setrp(p)

                        def fn(s=s):
                            s(cpu.pop())
                            return 10 + extra
                elif p == 0:
                    def fn():
                        cpu.pc = cpu.pop()
                        cpu.wz = cpu.pc
                        return 10
                elif p == 1:
                    def fn():
                        alt = cpu.alt
                        for k in (B, C, D, E, H, L):
                            R[k], alt[k] = alt[k], R[k]
                        return 4
                elif p == 2:
                    def fn():
                        cpu.pc = R[HI] << 8 | R[LO]
                        return 4 + extra
                else:
                    def fn():
                        cpu.sp = R[HI] << 8 | R[LO]
                        return 6 + extra
            elif z == 2:
                fn = _mk_jp_cc(cpu, f16, y)
            elif z == 3:
                if y == 0:
                    def fn():
                        cpu.pc = f16()
                        cpu.wz = cpu.pc
                        return 10
                elif y == 1:
                    fn = cb_dispatch()
                elif y == 2:
                    def fn():
                        n = f8()
                        a = R[A]
                        cpu.outp((a << 8) | n, a)
                        cpu.wz = (a << 8) | ((n + 1) & 0xFF)
                        return 11
                elif y == 3:
                    def fn():
                        n = f8()
                        port = (R[A] << 8) | n
                        cpu.wz = (port + 1) & 0xFFFF
                        R[A] = cpu.inp(port) & 0xFF
                        return 11
                elif y == 4:
                    def fn():
                        sp = cpu.sp
                        v = mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8)
                        cpu.wb(sp, R[LO])
                        cpu.wb((sp + 1) & 0xFFFF, R[HI])
                        R[HI] = v >> 8
                        R[LO] = v & 0xFF
                        cpu.wz = v
                        return 19 + extra
                elif y == 5:
                    def fn():
                        R[D], R[H] = R[H], R[D]
                        R[E], R[L] = R[L], R[E]
                        return 4
                elif y == 6:
                    def fn():
                        cpu.iff1 = cpu.iff2 = 0
                        return 4
                else:
                    def fn():
                        cpu.iff1 = cpu.iff2 = 1
                        cpu.ei_delay = True
                        return 4
            elif z == 4:
                fn = _mk_call_cc(cpu, f16, y)
            elif z == 5:
                if q == 0:
                    if p == 3:
                        def fn():
                            cpu.push(R[A] << 8 | R[F])
                            return 11
                    else:
                        g = getrp(p)

                        def fn(g=g):
                            cpu.push(g())
                            return 11 + extra
                elif p == 0:
                    def fn():
                        t = f16()
                        cpu.push(cpu.pc)
                        cpu.pc = t
                        cpu.wz = t
                        return 17
                elif p == 1:
                    fn = prefix_dispatch("tab_ix")
                elif p == 2:
                    fn = prefix_dispatch("tab_ed")
                else:
                    fn = prefix_dispatch("tab_iy")
            elif z == 6:
                alu = alus[y]

                def fn(alu=alu):
                    alu(f8())
                    return 7
            else:
                def fn(t=y * 8):
                    cpu.push(cpu.pc)
                    cpu.pc = t
                    cpu.wz = t
                    return 11
        if idx is not None:
            # opcodes a los que no afecta el prefijo: se ejecuta la versión normal
            if not _index_affects(op):
                def fn(op=op):
                    return 4 + cpu.main[op]()
        table[op] = fn
    return table


def _index_affects(op):
    x, y, z = op >> 6, (op >> 3) & 7, op & 7
    p, q = y >> 1, y & 1
    if op in (0xDD, 0xFD, 0xED):
        return True  # se tratan como encadenado (ver abajo)
    if op == 0xCB:
        return True
    if x == 0:
        if z == 1:
            return p == 2 or q == 1     # LD IX,nn / ADD IX,rr
        if z == 2:
            return p == 2
        if z == 3:
            return p == 2
        if z in (4, 5, 6):
            return y in (4, 5, 6)
        return False
    if x == 1:
        if op == 0x76:
            return False
        return y in (4, 5, 6) or z in (4, 5, 6)
    if x == 2:
        return z in (4, 5, 6)
    if op in (0xE1, 0xE5, 0xE3, 0xE9, 0xF9):
        return True
    return False


def _mk_jr_cc(cpu, fd, c):
    R = cpu.R
    mask, want = [(FZ, 0), (FZ, FZ), (FC, 0), (FC, FC)][c]

    def fn():
        d = fd()
        if (R[F] & mask) == want:
            cpu.pc = (cpu.pc + d) & 0xFFFF
            cpu.wz = cpu.pc
            return 12
        return 7
    return fn


_CC_TEST = [(FZ, 0), (FZ, FZ), (FC, 0), (FC, FC), (FP, 0), (FP, FP), (FS, 0), (FS, FS)]


def _mk_jp_cc(cpu, f16, c):
    R = cpu.R
    mask, want = _CC_TEST[c]

    def fn():
        t = f16()
        cpu.wz = t
        if (R[F] & mask) == want:
            cpu.pc = t
        return 10
    return fn


def _mk_call_cc(cpu, f16, c):
    R = cpu.R
    mask, want = _CC_TEST[c]

    def fn():
        t = f16()
        cpu.wz = t
        if (R[F] & mask) == want:
            cpu.push(cpu.pc)
            cpu.pc = t
            return 17
        return 10
    return fn


def _mk_ret_cc(cpu, c):
    R = cpu.R
    mask, want = _CC_TEST[c]

    def fn():
        if (R[F] & mask) == want:
            cpu.pc = cpu.pop()
            cpu.wz = cpu.pc
            return 11
        return 5
    return fn


def _mk_acc_op(cpu, y):
    R = cpu.R
    if y == 0:      # RLCA
        def fn():
            a = R[A]
            c = a >> 7
            a = ((a << 1) | c) & 0xFF
            R[A] = a
            R[F] = (R[F] & (FS | FZ | FP)) | (a & (FY | FX)) | c
            return 4
    elif y == 1:    # RRCA
        def fn():
            a = R[A]
            c = a & 1
            a = (a >> 1) | (c << 7)
            R[A] = a
            R[F] = (R[F] & (FS | FZ | FP)) | (a & (FY | FX)) | c
            return 4
    elif y == 2:    # RLA
        def fn():
            a = R[A]
            c = a >> 7
            a = ((a << 1) | (R[F] & 1)) & 0xFF
            R[A] = a
            R[F] = (R[F] & (FS | FZ | FP)) | (a & (FY | FX)) | c
            return 4
    elif y == 3:    # RRA
        def fn():
            a = R[A]
            c = a & 1
            a = (a >> 1) | ((R[F] & 1) << 7)
            R[A] = a
            R[F] = (R[F] & (FS | FZ | FP)) | (a & (FY | FX)) | c
            return 4
    elif y == 4:    # DAA
        def fn():
            a = R[A]
            f = R[F]
            corr = 0
            carry = f & FC
            if (f & FH) or (a & 0x0F) > 9:
                corr = 6
            if carry or a > 0x99:
                corr |= 0x60
                carry = FC
            if f & FN:
                h = FH if (f & FH) and (a & 0x0F) < 6 else 0
                r = (a - corr) & 0xFF
            else:
                h = FH if (a & 0x0F) > 9 else 0
                r = (a + corr) & 0xFF
            R[A] = r
            R[F] = SZ53P[r] | h | (f & FN) | carry
            return 4
    elif y == 5:    # CPL
        def fn():
            a = R[A] ^ 0xFF
            R[A] = a
            R[F] = (R[F] & (FS | FZ | FP | FC)) | FH | FN | (a & (FY | FX))
            return 4
    elif y == 6:    # SCF
        def fn():
            R[F] = (R[F] & (FS | FZ | FP)) | FC | (R[A] & (FY | FX))
            return 4
    else:           # CCF
        def fn():
            f = R[F]
            R[F] = ((f & (FS | FZ | FP)) | ((f & FC) << 4) | (R[A] & (FY | FX))) | ((f & FC) ^ FC)
            return 4
    return fn


# ---------------------------------------------------------------------------
# CB
# ---------------------------------------------------------------------------

def _build_cb(cpu):
    R = cpu.R
    mem = cpu.mem
    _, _, _, _, rot = _alu_funcs(cpu)
    table = [None] * 256
    for op in range(256):
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        ri = [B, C, D, E, H, L, None, A][z]
        if x == 0:
            if z == 6:
                def fn(y=y):
                    a = R[H] << 8 | R[L]
                    cpu.wb(a, rot(y, mem[a]))
                    return 15
            else:
                def fn(y=y, ri=ri):
                    R[ri] = rot(y, R[ri])
                    return 8
        elif x == 1:
            bit = 1 << y
            if z == 6:
                def fn(bit=bit, y=y):
                    v = mem[R[H] << 8 | R[L]]
                    res = v & bit
                    f = (R[F] & FC) | FH | ((cpu.wz >> 8) & (FY | FX))
                    if not res:
                        f |= FZ | FP
                    if y == 7 and res:
                        f |= FS
                    R[F] = f
                    return 12
            else:
                def fn(bit=bit, y=y, ri=ri):
                    v = R[ri]
                    res = v & bit
                    f = (R[F] & FC) | FH | (v & (FY | FX))
                    if not res:
                        f |= FZ | FP
                    if y == 7 and res:
                        f |= FS
                    R[F] = f
                    return 8
        else:
            if x == 2:
                mask, orv = (~(1 << y)) & 0xFF, 0
            else:
                mask, orv = 0xFF, 1 << y
            if z == 6:
                def fn(mask=mask, orv=orv):
                    a = R[H] << 8 | R[L]
                    cpu.wb(a, (mem[a] & mask) | orv)
                    return 15
            else:
                def fn(mask=mask, orv=orv, ri=ri):
                    R[ri] = (R[ri] & mask) | orv
                    return 8
        table[op] = fn
    return table


def _build_idx_cb(cpu, idx):
    R = cpu.R
    mem = cpu.mem
    _, _, _, _, rot = _alu_funcs(cpu)
    table = [None] * 256
    for op in range(256):
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        ri = [B, C, D, E, H, L, None, A][z]
        if x == 0:
            def fn(a, y=y, ri=ri):
                v = rot(y, mem[a])
                cpu.wb(a, v)
                if ri is not None:
                    R[ri] = v
                return 23
        elif x == 1:
            bit = 1 << y

            def fn(a, bit=bit, y=y):
                v = mem[a]
                res = v & bit
                f = (R[F] & FC) | FH | ((a >> 8) & (FY | FX))
                if not res:
                    f |= FZ | FP
                if y == 7 and res:
                    f |= FS
                R[F] = f
                return 20
        else:
            if x == 2:
                mask, orv = (~(1 << y)) & 0xFF, 0
            else:
                mask, orv = 0xFF, 1 << y

            def fn(a, mask=mask, orv=orv, ri=ri):
                v = (mem[a] & mask) | orv
                cpu.wb(a, v)
                if ri is not None:
                    R[ri] = v
                return 23
        table[op] = fn
    return table


# ---------------------------------------------------------------------------
# ED
# ---------------------------------------------------------------------------

def _build_ed(cpu):
    R = cpu.R
    mem = cpu.mem
    table = [None] * 256

    def f16():
        pc = cpu.pc
        v = mem[pc] | (mem[(pc + 1) & 0xFFFF] << 8)
        cpu.pc = (pc + 2) & 0xFFFF
        return v

    def get_rp(p):
        return [lambda: R[B] << 8 | R[C], lambda: R[D] << 8 | R[E],
                lambda: R[H] << 8 | R[L], lambda: cpu.sp][p]

    def set_rp(p):
        def s(v, p=p):
            if p == 0:
                R[B], R[C] = v >> 8, v & 0xFF
            elif p == 1:
                R[D], R[E] = v >> 8, v & 0xFF
            elif p == 2:
                R[H], R[L] = v >> 8, v & 0xFF
            else:
                cpu.sp = v
        return s

    def invalid():
        return 8

    for op in range(256):
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        p, q = y >> 1, y & 1
        fn = invalid
        if x == 1:
            if z == 0:
                ri = [B, C, D, E, H, L, None, A][y]

                def fn(ri=ri):
                    bc = R[B] << 8 | R[C]
                    v = cpu.inp(bc) & 0xFF
                    cpu.wz = (bc + 1) & 0xFFFF
                    R[F] = (R[F] & FC) | SZ53P[v]
                    if ri is not None:
                        R[ri] = v
                    return 12
            elif z == 1:
                ri = [B, C, D, E, H, L, None, A][y]

                def fn(ri=ri):
                    bc = R[B] << 8 | R[C]
                    cpu.outp(bc, R[ri] if ri is not None else 0)
                    cpu.wz = (bc + 1) & 0xFFFF
                    return 12
            elif z == 2:
                g = get_rp(p)
                if q == 0:
                    def fn(g=g):
                        hl = R[H] << 8 | R[L]
                        v = g()
                        res = hl - v - (R[F] & 1)
                        cpu.wz = (hl + 1) & 0xFFFF
                        r16 = res & 0xFFFF
                        R[F] = ((r16 >> 8) & (FS | FY | FX)) | (FZ if r16 == 0 else 0) | FN | \
                            (1 if res < 0 else 0) | (((hl ^ v ^ res) >> 8) & FH) | \
                            (FP if ((hl ^ v) & (hl ^ res) & 0x8000) else 0)
                        R[H], R[L] = r16 >> 8, r16 & 0xFF
                        return 15
                else:
                    def fn(g=g):
                        hl = R[H] << 8 | R[L]
                        v = g()
                        res = hl + v + (R[F] & 1)
                        cpu.wz = (hl + 1) & 0xFFFF
                        r16 = res & 0xFFFF
                        R[F] = ((r16 >> 8) & (FS | FY | FX)) | (FZ if r16 == 0 else 0) | \
                            (res >> 16) | (((hl ^ v ^ res) >> 8) & FH) | \
                            (FP if ((hl ^ res) & (v ^ res) & 0x8000) else 0)
                        R[H], R[L] = r16 >> 8, r16 & 0xFF
                        return 15
            elif z == 3:
                if q == 0:
                    g = get_rp(p)

                    def fn(g=g):
                        a = f16()
                        v = g()
                        cpu.wb(a, v & 0xFF)
                        cpu.wb((a + 1) & 0xFFFF, v >> 8)
                        cpu.wz = (a + 1) & 0xFFFF
                        return 20
                else:
                    s = set_rp(p)

                    def fn(s=s):
                        a = f16()
                        s(mem[a] | (mem[(a + 1) & 0xFFFF] << 8))
                        cpu.wz = (a + 1) & 0xFFFF
                        return 20
            elif z == 4:
                def fn():
                    a = R[A]
                    res = -a
                    r8 = res & 0xFF
                    R[F] = SZ53[r8] | FN | (1 if a else 0) | ((a ^ res) & FH) | (FP if a == 0x80 else 0)
                    R[A] = r8
                    return 8
            elif z == 5:
                def fn():
                    cpu.pc = cpu.pop()
                    cpu.wz = cpu.pc
                    cpu.iff1 = cpu.iff2
                    return 14
            elif z == 6:
                mode = [0, 0, 1, 2, 0, 0, 1, 2][y]

                def fn(mode=mode):
                    cpu.im = mode
                    return 8
            else:
                if y == 0:
                    def fn():
                        cpu.i = R[A]
                        return 9
                elif y == 1:
                    def fn():
                        cpu.r = R[A]
                        return 9
                elif y == 2:
                    def fn():
                        v = cpu.i
                        R[A] = v
                        R[F] = (R[F] & FC) | SZ53[v] | (FP if cpu.iff2 else 0)
                        return 9
                elif y == 3:
                    def fn():
                        v = cpu.r & 0xFF
                        R[A] = v
                        R[F] = (R[F] & FC) | SZ53[v] | (FP if cpu.iff2 else 0)
                        return 9
                elif y == 4:    # RRD
                    def fn():
                        hl = R[H] << 8 | R[L]
                        m = mem[hl]
                        a = R[A]
                        cpu.wb(hl, ((a << 4) | (m >> 4)) & 0xFF)
                        a = (a & 0xF0) | (m & 0x0F)
                        R[A] = a
                        R[F] = (R[F] & FC) | SZ53P[a]
                        cpu.wz = (hl + 1) & 0xFFFF
                        return 18
                elif y == 5:    # RLD
                    def fn():
                        hl = R[H] << 8 | R[L]
                        m = mem[hl]
                        a = R[A]
                        cpu.wb(hl, ((m << 4) | (a & 0x0F)) & 0xFF)
                        a = (a & 0xF0) | (m >> 4)
                        R[A] = a
                        R[F] = (R[F] & FC) | SZ53P[a]
                        cpu.wz = (hl + 1) & 0xFFFF
                        return 18
        elif x == 2 and z <= 3 and y >= 4:
            fn = _mk_block(cpu, y, z)
        table[op] = fn
    return table


def _mk_block(cpu, y, z):
    R = cpu.R
    mem = cpu.mem
    inc = 1 if y in (4, 6) else -1
    repeat = y >= 6

    def hl_add():
        v = ((R[H] << 8 | R[L]) + inc) & 0xFFFF
        R[H], R[L] = v >> 8, v & 0xFF

    if z == 0:      # LDI/LDD/LDIR/LDDR
        def fn():
            hl = R[H] << 8 | R[L]
            de = R[D] << 8 | R[E]
            v = mem[hl]
            cpu.wb(de, v)
            hl = (hl + inc) & 0xFFFF
            de = (de + inc) & 0xFFFF
            bc = ((R[B] << 8 | R[C]) - 1) & 0xFFFF
            R[H], R[L] = hl >> 8, hl & 0xFF
            R[D], R[E] = de >> 8, de & 0xFF
            R[B], R[C] = bc >> 8, bc & 0xFF
            n = (v + R[A]) & 0xFF
            f = (R[F] & (FS | FZ | FC)) | (FP if bc else 0) | (n & FX) | ((n << 4) & FY)
            if repeat and bc:
                pc = (cpu.pc - 2) & 0xFFFF
                cpu.pc = pc
                cpu.wz = (pc + 1) & 0xFFFF
                R[F] = (f & ~(FY | FX)) | ((pc >> 8) & (FY | FX))
                return 21
            R[F] = f
            return 16
    elif z == 1:    # CPI/CPD/CPIR/CPDR
        def fn():
            hl = R[H] << 8 | R[L]
            v = mem[hl]
            a = R[A]
            res = (a - v) & 0xFF
            hflag = (a ^ v ^ res) & FH
            hl_add()
            bc = ((R[B] << 8 | R[C]) - 1) & 0xFFFF
            R[B], R[C] = bc >> 8, bc & 0xFF
            n = (res - (1 if hflag else 0)) & 0xFF
            f = (R[F] & FC) | FN | (SZ53[res] & (FS | FZ)) | hflag | (FP if bc else 0) | \
                (n & FX) | ((n << 4) & FY)
            cpu.wz = (cpu.wz + inc) & 0xFFFF
            if repeat and bc and res != 0:
                pc = (cpu.pc - 2) & 0xFFFF
                cpu.pc = pc
                cpu.wz = (pc + 1) & 0xFFFF
                R[F] = (f & ~(FY | FX)) | ((pc >> 8) & (FY | FX))
                return 21
            R[F] = f
            return 16
    elif z == 2:    # INI/IND/INIR/INDR
        def fn():
            bc = R[B] << 8 | R[C]
            v = cpu.inp(bc) & 0xFF
            cpu.wz = (bc + inc) & 0xFFFF
            hl = R[H] << 8 | R[L]
            cpu.wb(hl, v)
            hl_add()
            b = (R[B] - 1) & 0xFF
            R[B] = b
            k = v + ((R[C] + inc) & 0xFF)
            f = SZ53[b] | (FN if v & 0x80 else 0) | ((FH | FC) if k > 255 else 0) | \
                PARITY[(k & 7) ^ b]
            if repeat and b:
                pc = (cpu.pc - 2) & 0xFFFF
                cpu.pc = pc
                f = _block_io_repeat_flags(f, pc, b, v, k)
                R[F] = f
                return 21
            R[F] = f
            return 16
    else:           # OUTI/OUTD/OTIR/OTDR
        def fn():
            hl = R[H] << 8 | R[L]
            v = mem[hl]
            b = (R[B] - 1) & 0xFF
            R[B] = b
            bc = b << 8 | R[C]
            cpu.outp(bc, v)
            cpu.wz = (bc + inc) & 0xFFFF
            hl_add()
            k = v + R[L]
            f = SZ53[b] | (FN if v & 0x80 else 0) | ((FH | FC) if k > 255 else 0) | \
                PARITY[(k & 7) ^ b]
            if repeat and b:
                pc = (cpu.pc - 2) & 0xFFFF
                cpu.pc = pc
                f = _block_io_repeat_flags(f, pc, b, v, k)
                R[F] = f
                return 21
            R[F] = f
            return 16
    return fn


def _block_io_repeat_flags(f, pc, b, v, k):
    """Ajuste de flags de INIR/OTIR... cuando se repiten (comportamiento real)."""
    f = (f & ~(FY | FX)) | ((pc >> 8) & (FY | FX))
    if f & FC:
        if v & 0x80:
            hf = FH if (b & 0x0F) == 0 else 0
            p = PARITY[((b - 1) & 7) ^ (k & 7) ^ b]
        else:
            hf = FH if (b & 0x0F) == 0x0F else 0
            p = PARITY[((b + 1) & 7) ^ (k & 7) ^ b]
    else:
        hf = 0
        p = PARITY[(b & 7) ^ (k & 7) ^ b]
    return (f & ~(FH | FP)) | hf | p
