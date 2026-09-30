"""Decodificador de instrucciones Z80 dirigido por tablas.

Decodifica cualquier secuencia de bytes (incluidas las instrucciones no
documentadas: IXH/IXL, SLL, DDCB con copia a registro...) y devuelve una
``Instr`` con operandos estructurados, información de flujo y de accesos a
memoria/puertos, que es lo que necesitan el analizador y el portador.
"""

from __future__ import annotations

from dataclasses import dataclass, field

R8 = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
RP = ["BC", "DE", "HL", "SP"]
RP2 = ["BC", "DE", "HL", "AF"]
CC = ["NZ", "Z", "NC", "C", "PO", "PE", "P", "M"]
ALU = ["ADD", "ADC", "SUB", "SBC", "AND", "XOR", "OR", "CP"]
ROT = ["RLC", "RRC", "RL", "RR", "SLA", "SRA", "SLL", "SRL"]
BLOCK = {
    (4, 0): "LDI", (4, 1): "CPI", (4, 2): "INI", (4, 3): "OUTI",
    (5, 0): "LDD", (5, 1): "CPD", (5, 2): "IND", (5, 3): "OUTD",
    (6, 0): "LDIR", (6, 1): "CPIR", (6, 2): "INIR", (6, 3): "OTIR",
    (7, 0): "LDDR", (7, 1): "CPDR", (7, 2): "INDR", (7, 3): "OTDR",
}

# Tipos de operando
REG = "r"          # registro de 8 bits o especial: A,B,...,IXH,I,R,F
REG16 = "rr"       # BC,DE,HL,SP,AF,AF',IX,IY
IMM8 = "n"
IMM16 = "nn"
IND_REG = "(rr)"   # (HL) (BC) (DE) (SP) (IX) (IY) (C)
IND_IMM = "(nn)"   # (nn) de memoria
IDX = "(ix+d)"     # (IX+d)/(IY+d): valor = (reg, d)
PORT_IMM = "(n)"   # puerto inmediato
COND = "cc"
REL = "e"          # destino absoluto de un salto relativo
LIT = "lit"        # literal fijo codificado en el opcode (RST, IM, BIT)


@dataclass(frozen=True)
class Operand:
    kind: str
    value: object

    def text(self, fmt_num=None) -> str:
        f = fmt_num or fmt_hex
        k, v = self.kind, self.value
        if k in (REG, REG16, COND):
            return v
        if k == IMM8:
            return f(v, 2)
        if k in (IMM16, REL):
            return f(v, 4)
        if k == IND_REG:
            return f"({v})"
        if k == IND_IMM:
            return f"({f(v, 4)})"
        if k == PORT_IMM:
            return f"({f(v, 2)})"
        if k == IDX:
            reg, d = v
            return f"({reg}{'+' if d >= 0 else '-'}{f(abs(d), 2)})"
        if k == LIT:
            return f(v, 2) if v > 9 else str(v)
        raise ValueError(k)


def fmt_hex(v: int, digits: int) -> str:
    return "$" + format(v, f"0{digits}X")


@dataclass
class Instr:
    addr: int
    length: int
    raw: bytes
    op: str
    operands: tuple = ()
    flow: str | None = None        # jp, jr, djnz, call, ret, rst, jpind, halt, reti, retn
    cond: str | None = None        # condición (si el salto/ret es condicional)
    target: int | None = None      # destino de salto/call/rst
    prefix_only: bool = False      # prefijo DD/FD sin efecto (actúa como NOP)
    undocumented: bool = False
    notes: list = field(default_factory=list)

    @property
    def next(self) -> int:
        return (self.addr + self.length) & 0xFFFF

    @property
    def ends_block(self) -> bool:
        """True si la ejecución no continúa en la siguiente instrucción."""
        if self.flow in ("jp", "jr", "jpind", "ret", "reti", "retn") and self.cond is None:
            return True
        return False

    def text(self, fmt_num=None, labels=None) -> str:
        if self.prefix_only or self.op == "DB":
            f = fmt_num or fmt_hex
            return "DB " + ",".join(f(b, 2) for b in self.raw)
        parts = []
        for o in self.operands:
            if labels and o.kind in (IMM16, REL) and o.value in labels:
                parts.append(labels[o.value])
            elif labels and o.kind == IND_IMM and o.value in labels:
                parts.append(f"({labels[o.value]})")
            else:
                parts.append(o.text(fmt_num))
        return self.op + (" " + ",".join(parts) if parts else "")

    # --- utilidades para el análisis -----------------------------------
    def regs_in_operands(self):
        return [o.value for o in self.operands if o.kind in (REG, REG16)]

    def mem_write_kind(self):
        """Describe cómo escribe en memoria esta instrucción, o None.

        Devuelve una tupla (modo, detalle): ('ind', 'HL'), ('idx', ('IX', d)),
        ('abs', nn), ('stack', None) o ('block', op).
        """
        op, ops = self.op, self.operands
        if self.prefix_only:
            return None
        if op in ("LDI", "LDD", "LDIR", "LDDR"):
            return ("block", op)
        if op in ("PUSH", "CALL", "RST"):
            return ("stack", None)
        if op == "EX" and ops and ops[0].kind == IND_REG and ops[0].value == "SP":
            return ("stack", None)
        if op in ("RLD", "RRD"):
            return ("ind", "HL")
        if op in ("INI", "IND", "INIR", "INDR"):
            return ("ind", "HL")
        dest = None
        if op in ("LD",) and ops:
            dest = ops[0]
        elif op in ("INC", "DEC", "SET", "RES") + tuple(ROT) and ops:
            # rotaciones/SET/RES: el operando de memoria es el último con (..)
            for o in ops:
                if o.kind in (IND_REG, IDX):
                    dest = o
                    break
            if op in ("INC", "DEC") and ops[0].kind not in (IND_REG, IDX):
                dest = None
        if dest is None:
            return None
        if dest.kind == IND_REG and dest.value in ("HL", "BC", "DE"):
            return ("ind", dest.value)
        if dest.kind == IDX:
            return ("idx", dest.value)
        if dest.kind == IND_IMM:
            width = 2 if (len(ops) > 1 and ops[1].kind == REG16) else 1
            return ("abs", (dest.value, width))
        return None

    def io_kind(self):
        """('in'|'out', 'n'|'c', valor) para instrucciones de E/S, o None."""
        op, ops = self.op, self.operands
        if op == "IN":
            src = ops[-1]
            if src.kind == PORT_IMM:
                return ("in", "n", src.value)
            return ("in", "c", None)
        if op == "OUT":
            dst = ops[0]
            if dst.kind == PORT_IMM:
                return ("out", "n", dst.value)
            return ("out", "c", None)
        if op in ("INI", "IND", "INIR", "INDR"):
            return ("in", "block", op)
        if op in ("OUTI", "OUTD", "OTIR", "OTDR"):
            return ("out", "block", op)
        return None


def _s8(b: int) -> int:
    return b - 256 if b >= 128 else b


class _Reader:
    def __init__(self, fetch, addr):
        self.fetch = fetch
        self.start = addr
        self.pos = addr
        self.raw = bytearray()

    def byte(self) -> int:
        b = self.fetch(self.pos & 0xFFFF) & 0xFF
        self.raw.append(b)
        self.pos += 1
        return b

    def word(self) -> int:
        lo = self.byte()
        return lo | (self.byte() << 8)


def decode(fetch, addr: int) -> Instr:
    """Decodifica la instrucción en ``addr``. ``fetch(addr) -> int``.

    ``fetch`` puede ser también un objeto indexable (bytes, bytearray, lista).
    """
    if not callable(fetch):
        mem = fetch
        fetch = lambda a: mem[a]  # noqa: E731
    rd = _Reader(fetch, addr)
    b = rd.byte()
    if b in (0xDD, 0xFD):
        idx = "IX" if b == 0xDD else "IY"
        nb = fetch((addr + 1) & 0xFFFF) & 0xFF
        if nb in (0xDD, 0xFD, 0xED):
            return Instr(addr, 1, bytes(rd.raw), "DB", (Operand(IMM8, b),), prefix_only=True,
                         notes=["prefijo sin efecto"])
        rd.byte()
        if nb == 0xCB:
            return _decode_idx_cb(rd, addr, idx)
        ins = _decode_main(rd, addr, nb, idx)
        if ins is None:
            return Instr(addr, 1, bytes(rd.raw[:1]), "DB", (Operand(IMM8, b),), prefix_only=True,
                         notes=["prefijo sin efecto"])
        return ins
    if b == 0xCB:
        return _decode_cb(rd, addr)
    if b == 0xED:
        return _decode_ed(rd, addr)
    return _decode_main(rd, addr, b, None)


def _mk(rd, addr, op, *operands, **kw):
    return Instr(addr, len(rd.raw), bytes(rd.raw), op, tuple(operands), **kw)


def _decode_main(rd, addr, b, idx):
    """Decodifica opcode sin prefijo o con prefijo DD/FD (idx='IX'/'IY').

    Devuelve None si el prefijo índice no afecta a la instrucción.
    """
    x, y, z = b >> 6, (b >> 3) & 7, b & 7
    p, q = y >> 1, y & 1
    used = [False]  # si el prefijo índice se ha usado

    def hl16():
        if idx:
            used[0] = True
            return idx
        return "HL"

    disp_cache = []

    def mem_hl():
        if idx:
            used[0] = True
            if not disp_cache:
                disp_cache.append(_s8(rd.byte()))
            return Operand(IDX, (idx, disp_cache[0]))
        return Operand(IND_REG, "HL")

    def r8(i, allow_idx_half=True):
        if i == 6:
            return mem_hl()
        name = R8[i]
        if idx and allow_idx_half and i in (4, 5):
            used[0] = True
            return Operand(REG, idx + ("H" if i == 4 else "L"))
        return Operand(REG, name)

    def rp(i):
        return Operand(REG16, hl16() if i == 2 else RP[i])

    def rp2(i):
        return Operand(REG16, hl16() if i == 2 else RP2[i])

    ins = None
    if x == 0:
        if z == 0:
            if y == 0:
                ins = _mk(rd, addr, "NOP")
            elif y == 1:
                ins = _mk(rd, addr, "EX", Operand(REG16, "AF"), Operand(REG16, "AF'"))
            elif y == 2:
                t = (addr + 2 + _s8(rd.byte())) & 0xFFFF
                ins = _mk(rd, addr, "DJNZ", Operand(REL, t), flow="djnz", cond="B", target=t)
            elif y == 3:
                t = (addr + 2 + _s8(rd.byte())) & 0xFFFF
                ins = _mk(rd, addr, "JR", Operand(REL, t), flow="jr", target=t)
            else:
                c = CC[y - 4]
                t = (addr + 2 + _s8(rd.byte())) & 0xFFFF
                ins = _mk(rd, addr, "JR", Operand(COND, c), Operand(REL, t), flow="jr", cond=c, target=t)
            if idx:
                return None
            return ins
        if z == 1:
            if q == 0:
                r = rp(p)
                ins = _mk(rd, addr, "LD", r, Operand(IMM16, rd.word()))
            else:
                ins = _mk(rd, addr, "ADD", Operand(REG16, hl16()), rp(p))
        elif z == 2:
            if q == 0:
                if p == 0:
                    ins = _mk(rd, addr, "LD", Operand(IND_REG, "BC"), Operand(REG, "A"))
                elif p == 1:
                    ins = _mk(rd, addr, "LD", Operand(IND_REG, "DE"), Operand(REG, "A"))
                elif p == 2:
                    h = hl16()
                    ins = _mk(rd, addr, "LD", Operand(IND_IMM, rd.word()), Operand(REG16, h))
                else:
                    ins = _mk(rd, addr, "LD", Operand(IND_IMM, rd.word()), Operand(REG, "A"))
            else:
                if p == 0:
                    ins = _mk(rd, addr, "LD", Operand(REG, "A"), Operand(IND_REG, "BC"))
                elif p == 1:
                    ins = _mk(rd, addr, "LD", Operand(REG, "A"), Operand(IND_REG, "DE"))
                elif p == 2:
                    h = hl16()
                    ins = _mk(rd, addr, "LD", Operand(REG16, h), Operand(IND_IMM, rd.word()))
                else:
                    ins = _mk(rd, addr, "LD", Operand(REG, "A"), Operand(IND_IMM, rd.word()))
        elif z == 3:
            ins = _mk(rd, addr, "INC" if q == 0 else "DEC", rp(p))
        elif z in (4, 5):
            ins = _mk(rd, addr, "INC" if z == 4 else "DEC", r8(y))
        elif z == 6:
            d = r8(y)
            ins = _mk(rd, addr, "LD", d, Operand(IMM8, rd.byte()))
        else:
            ins = _mk(rd, addr, ["RLCA", "RRCA", "RLA", "RRA", "DAA", "CPL", "SCF", "CCF"][y])
    elif x == 1:
        if z == 6 and y == 6:
            ins = _mk(rd, addr, "HALT", flow="halt")
        elif y == 6 or z == 6:
            # LD r,(IX+d) / LD (IX+d),r: el registro no se sustituye por IXH/IXL
            ins = _mk(rd, addr, "LD", r8(y, False), r8(z, False))
        else:
            ins = _mk(rd, addr, "LD", r8(y), r8(z))
    elif x == 2:
        ins = _alu(rd, addr, y, r8(z))
    else:
        if z == 0:
            c = CC[y]
            ins = _mk(rd, addr, "RET", Operand(COND, c), flow="ret", cond=c)
        elif z == 1:
            if q == 0:
                ins = _mk(rd, addr, "POP", rp2(p))
            elif p == 0:
                ins = _mk(rd, addr, "RET", flow="ret")
            elif p == 1:
                ins = _mk(rd, addr, "EXX")
            elif p == 2:
                ins = _mk(rd, addr, "JP", Operand(IND_REG, hl16()), flow="jpind")
            else:
                ins = _mk(rd, addr, "LD", Operand(REG16, "SP"), Operand(REG16, hl16()))
        elif z == 2:
            c = CC[y]
            t = rd.word()
            ins = _mk(rd, addr, "JP", Operand(COND, c), Operand(IMM16, t), flow="jp", cond=c, target=t)
        elif z == 3:
            if y == 0:
                t = rd.word()
                ins = _mk(rd, addr, "JP", Operand(IMM16, t), flow="jp", target=t)
            elif y == 2:
                ins = _mk(rd, addr, "OUT", Operand(PORT_IMM, rd.byte()), Operand(REG, "A"))
            elif y == 3:
                ins = _mk(rd, addr, "IN", Operand(REG, "A"), Operand(PORT_IMM, rd.byte()))
            elif y == 4:
                ins = _mk(rd, addr, "EX", Operand(IND_REG, "SP"), Operand(REG16, hl16()))
            elif y == 5:
                ins = _mk(rd, addr, "EX", Operand(REG16, "DE"), Operand(REG16, "HL"))
            elif y == 6:
                ins = _mk(rd, addr, "DI")
            elif y == 7:
                ins = _mk(rd, addr, "EI")
            else:  # y == 1 -> CB (no llega aquí)
                raise AssertionError
        elif z == 4:
            c = CC[y]
            t = rd.word()
            ins = _mk(rd, addr, "CALL", Operand(COND, c), Operand(IMM16, t), flow="call", cond=c, target=t)
        elif z == 5:
            if q == 0:
                ins = _mk(rd, addr, "PUSH", rp2(p))
            elif p == 0:
                t = rd.word()
                ins = _mk(rd, addr, "CALL", Operand(IMM16, t), flow="call", target=t)
            else:  # DD/ED/FD (no llega aquí)
                raise AssertionError
        elif z == 6:
            ins = _alu(rd, addr, y, Operand(IMM8, rd.byte()))
        else:
            ins = _mk(rd, addr, "RST", Operand(LIT, y * 8), flow="rst", target=y * 8)
    if idx and not used[0]:
        return None
    if ins is not None and idx and any(
        o.kind == REG and o.value in ("IXH", "IXL", "IYH", "IYL") for o in ins.operands
    ):
        ins.undocumented = True
    return ins


def _alu(rd, addr, y, operand):
    op = ALU[y]
    if op in ("ADD", "ADC", "SBC"):
        return _mk(rd, addr, op, Operand(REG, "A"), operand)
    return _mk(rd, addr, op, operand)


def _decode_cb(rd, addr):
    b = rd.byte()
    x, y, z = b >> 6, (b >> 3) & 7, b & 7
    reg = Operand(IND_REG, "HL") if z == 6 else Operand(REG, R8[z])
    if x == 0:
        return _mk(rd, addr, ROT[y], reg, undocumented=(y == 6))
    op = ["", "BIT", "RES", "SET"][x]
    return _mk(rd, addr, op, Operand(LIT, y), reg)


def _decode_idx_cb(rd, addr, idx):
    d = _s8(rd.byte())
    b = rd.byte()
    x, y, z = b >> 6, (b >> 3) & 7, b & 7
    mem = Operand(IDX, (idx, d))
    extra = () if z == 6 else (Operand(REG, R8[z]),)
    undoc = z != 6
    if x == 0:
        return _mk(rd, addr, ROT[y], mem, *extra, undocumented=undoc or y == 6)
    if x == 1:
        # BIT n,(IX+d): todas las variantes de z son equivalentes
        return _mk(rd, addr, "BIT", Operand(LIT, y), mem, undocumented=undoc)
    op = "RES" if x == 2 else "SET"
    return _mk(rd, addr, op, Operand(LIT, y), mem, *extra, undocumented=undoc)


def _decode_ed(rd, addr):
    b = rd.byte()
    x, y, z = b >> 6, (b >> 3) & 7, b & 7
    p, q = y >> 1, y & 1
    if x == 1:
        if z == 0:
            if y == 6:
                return _mk(rd, addr, "IN", Operand(REG, "F"), Operand(IND_REG, "C"), undocumented=True)
            return _mk(rd, addr, "IN", Operand(REG, R8[y]), Operand(IND_REG, "C"))
        if z == 1:
            if y == 6:
                return _mk(rd, addr, "OUT", Operand(IND_REG, "C"), Operand(IMM8, 0), undocumented=True)
            return _mk(rd, addr, "OUT", Operand(IND_REG, "C"), Operand(REG, R8[y]))
        if z == 2:
            return _mk(rd, addr, "SBC" if q == 0 else "ADC", Operand(REG16, "HL"), Operand(REG16, RP[p]))
        if z == 3:
            if q == 0:
                return _mk(rd, addr, "LD", Operand(IND_IMM, rd.word()), Operand(REG16, RP[p]))
            return _mk(rd, addr, "LD", Operand(REG16, RP[p]), Operand(IND_IMM, rd.word()))
        if z == 4:
            return _mk(rd, addr, "NEG", undocumented=(y != 0))
        if z == 5:
            if y == 1:
                return _mk(rd, addr, "RETI", flow="reti")
            return _mk(rd, addr, "RETN", flow="retn", undocumented=(y != 0))
        if z == 6:
            mode = [0, 0, 1, 2, 0, 0, 1, 2][y]
            return _mk(rd, addr, "IM", Operand(LIT, mode), undocumented=y not in (0, 2, 3))
        return _mk(rd, addr, ["LD", "LD", "LD", "LD", "RRD", "RLD", "NOP", "NOP"][y],
                   *[(Operand(REG, "I"), Operand(REG, "A")), (Operand(REG, "R"), Operand(REG, "A")),
                     (Operand(REG, "A"), Operand(REG, "I")), (Operand(REG, "A"), Operand(REG, "R")),
                     (), (), (), ()][y],
                   undocumented=y >= 6) if y < 6 else _ed_invalid(rd, addr)
    if x == 2 and z <= 3 and y >= 4:
        return _mk(rd, addr, BLOCK[(y, z)])
    return _ed_invalid(rd, addr)


def _ed_invalid(rd, addr):
    ins = _mk(rd, addr, "DB", *[Operand(IMM8, v) for v in rd.raw], undocumented=True)
    ins.notes.append("opcode ED no válido (NOP de 8 ciclos)")
    return ins


def disassemble_range(mem, start: int, end: int):
    """Desensambla linealmente [start, end)."""
    out = []
    a = start
    while a < end:
        ins = decode(mem, a)
        out.append(ins)
        a += ins.length
    return out
