"""Ensamblador Z80 de dos pasadas, sin dependencias.

La tabla de codificación se genera automáticamente a partir del
decodificador (``decode.py``), así que ensamblador y desensamblador son
siempre coherentes entre sí.

Sintaxis admitida (compatible en lo esencial con pasmo/sjasmplus):

* etiquetas ``nombre:`` o en columna 0; locales ``.bucle`` (ámbito: última
  etiqueta global)
* ``ORG``, ``EQU`` (o ``=``), ``DB/DEFB/DEFM``, ``DW/DEFW``, ``DS/DEFS n[,v]``,
  ``ALIGN n``, ``ASSERT expr[,"mensaje"]``, ``IF/ELSE/ENDIF``, ``INCBIN``
* números ``$FF``, ``#FF``, ``0xFF``, ``0FFh``, ``%1010``, ``0b1010``, ``'c'``
* expresiones con ``+ - * / % & | ^ << >> ~ ! == != < > <= >= && ||``,
  ``$`` (dirección actual), ``LOW()``/``HIGH()``
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from . import decode as D


class AsmError(Exception):
    def __init__(self, msg, line_no=None, line=None, filename=None):
        self.msg, self.line_no, self.line, self.filename = msg, line_no, line, filename
        where = ""
        if line_no is not None:
            where = f"{filename or '<asm>'}:{line_no}: "
        super().__init__(f"{where}{msg}" + (f"\n    {line.strip()}" if line else ""))


# ---------------------------------------------------------------------------
# Tabla de codificación generada desde el decodificador
# ---------------------------------------------------------------------------

@dataclass
class _Template:
    prefix: bytes          # bytes de opcode antes de los campos
    fields: tuple          # secuencia de 'd', 'n', 'nn', 'e'
    suffix: bytes          # bytes tras los campos (DDCB)


def _pattern(o: D.Operand):
    k = o.kind
    if k == D.REG:
        return ("r", o.value)
    if k == D.REG16:
        return ("rr", o.value)
    if k in (D.IMM8, D.IMM16, D.REL):
        return ("imm",)
    if k == D.IND_REG:
        return ("ind", o.value)
    if k in (D.IND_IMM, D.PORT_IMM):
        return ("indimm",)
    if k == D.IDX:
        return ("idx", o.value[0])
    if k == D.COND:
        return ("cc", o.value)
    if k == D.LIT:
        return ("lit", o.value)
    raise ValueError(k)


def _fields_of(ins: D.Instr):
    """Lista de campos numéricos en el orden en que aparecen en los bytes."""
    fields = []
    has_idx = any(o.kind == D.IDX for o in ins.operands)
    if has_idx:
        fields.append("d")
    for o in ins.operands:
        if o.kind in (D.IMM8, D.PORT_IMM):
            fields.append("n")
        elif o.kind in (D.IMM16, D.IND_IMM):
            fields.append("nn")
        elif o.kind == D.REL:
            fields.append("e")
    return fields


_TABLE = None


def _build_table():
    table = {}
    filler = bytes([0x05, 0x00, 0x00, 0x00])

    def add(ins, prefix, suffix=b""):
        if ins.op == "DB" or ins.prefix_only:
            return
        key = (ins.op, tuple(_pattern(o) for o in ins.operands))
        # los campos numéricos se recogen en el orden de los operandos, pero
        # en memoria el desplazamiento va siempre antes que el inmediato
        fields = tuple(_fields_of(ins))
        # valores numéricos de operandos (para mapear campo<->operando)
        if key not in table:
            table[key] = _Template(prefix, fields, suffix)

    for op in range(256):
        if op in (0xCB, 0xED, 0xDD, 0xFD):
            continue
        add(D.decode(bytes([op]) + filler, 0), bytes([op]))
    for op in range(256):
        add(D.decode(bytes([0xCB, op]) + filler, 0), bytes([0xCB, op]))
    for op in range(256):
        add(D.decode(bytes([0xED, op]) + filler, 0), bytes([0xED, op]))
    for pre in (0xDD, 0xFD):
        for op in range(256):
            if op in (0xCB, 0xED, 0xDD, 0xFD):
                continue
            ins = D.decode(bytes([pre, op]) + filler, 0)
            if ins.prefix_only:
                continue
            add(ins, bytes([pre, op]))
    for pre in (0xDD, 0xFD):
        # preferir las formas documentadas (z == 6)
        for op in sorted(range(256), key=lambda v: ((v & 7) != 6, v)):
            ins = D.decode(bytes([pre, 0xCB, 0x05, op]), 0)
            add(ins, bytes([pre, 0xCB]), bytes([op]))
    return table


def _table():
    global _TABLE
    if _TABLE is None:
        _TABLE = _build_table()
    return _TABLE


# ---------------------------------------------------------------------------
# Expresiones
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"""
    \s*(?:
      (?P<num>\$[0-9A-Fa-f]+|\#[0-9A-Fa-f]+|0[xX][0-9A-Fa-f]+|%[01]+(?![0-9A-Za-z_])|0[bB][01]+
             |[0-9][0-9A-Fa-f]*[hH](?![0-9A-Za-z_])|[0-9]+(?![0-9A-Za-z_]))
     |(?P<chr>'(?:[^'\\]|\\.)')
     |(?P<id>\.?[A-Za-z_][A-Za-z0-9_.]*'?)
     |(?P<op><<|>>|<=|>=|==|!=|&&|\|\||[-+*/%&|^~!()<>$])
    )""", re.X)


def parse_number(tok: str) -> int:
    t = tok
    if t.startswith(("$", "#")):
        return int(t[1:], 16)
    if t.lower().startswith("0x"):
        return int(t[2:], 16)
    if t.startswith("%"):
        return int(t[1:], 2)
    if t.lower().startswith("0b") and all(c in "01" for c in t[2:]):
        return int(t[2:], 2)
    if t[-1] in "hH":
        return int(t[:-1], 16)
    return int(t, 10)


class _Unresolved(Exception):
    pass


class _Expr:
    """Evaluador recursivo; ``resolve(name)`` devuelve el valor de un símbolo."""

    PREC = [("||",), ("&&",), ("|",), ("^",), ("&",), ("==", "!="), ("<", ">", "<=", ">="),
            ("<<", ">>"), ("+", "-"), ("*", "/", "%")]

    def __init__(self, text, resolve, here):
        self.toks = self._tokenize(text)
        self.i = 0
        self.resolve = resolve
        self.here = here

    @staticmethod
    def _tokenize(text):
        toks = []
        pos = 0
        text = text.rstrip()
        while pos < len(text):
            m = _TOKEN_RE.match(text, pos)
            if not m or m.end() == pos:
                raise AsmError(f"expresión no válida: {text!r}")
            pos = m.end()
            for k in ("num", "chr", "id", "op"):
                v = m.group(k)
                if v is not None:
                    toks.append((k, v))
                    break
        return toks

    def peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def take(self):
        t = self.peek()
        self.i += 1
        return t

    def parse(self):
        v = self._binary(0)
        if self.i != len(self.toks):
            raise AsmError("sobran caracteres en la expresión")
        return v

    def _binary(self, level):
        if level == len(self.PREC):
            return self._unary()
        v = self._binary(level + 1)
        while True:
            k, t = self.peek()
            if k == "op" and t in self.PREC[level]:
                self.take()
                r = self._binary(level + 1)
                v = self._apply(t, v, r)
            else:
                return v

    @staticmethod
    def _apply(op, a, b):
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                raise AsmError("división por cero")
            return int(a / b)
        if op == "%":
            return a % b
        if op == "&":
            return a & b
        if op == "|":
            return a | b
        if op == "^":
            return a ^ b
        if op == "<<":
            return a << b
        if op == ">>":
            return a >> b
        if op == "==":
            return int(a == b)
        if op == "!=":
            return int(a != b)
        if op == "<":
            return int(a < b)
        if op == ">":
            return int(a > b)
        if op == "<=":
            return int(a <= b)
        if op == ">=":
            return int(a >= b)
        if op == "&&":
            return int(bool(a) and bool(b))
        if op == "||":
            return int(bool(a) or bool(b))
        raise AsmError(op)

    def _unary(self):
        k, t = self.take()
        if k == "op" and t == "-":
            return -self._unary()
        if k == "op" and t == "+":
            return self._unary()
        if k == "op" and t == "~":
            return ~self._unary()
        if k == "op" and t == "!":
            return int(not self._unary())
        if k == "op" and t == "(":
            v = self._binary(0)
            k2, t2 = self.take()
            if t2 != ")":
                raise AsmError("falta ')'")
            return v
        if k == "op" and t == "$":
            if self.here is None:
                raise _Unresolved("$")
            return self.here
        if k == "num":
            return parse_number(t)
        if k == "chr":
            s = t[1:-1]
            return ord(s.encode().decode("unicode_escape"))
        if k == "id":
            up = t.upper()
            if up in ("LOW", "HIGH") and self.peek() == ("op", "("):
                self.take()
                v = self._binary(0)
                if self.take()[1] != ")":
                    raise AsmError("falta ')'")
                return (v & 0xFF) if up == "LOW" else ((v >> 8) & 0xFF)
            return self.resolve(t)
        raise AsmError(f"expresión incompleta (token {t!r})")


# ---------------------------------------------------------------------------
# Análisis de operandos
# ---------------------------------------------------------------------------

_R8 = {"A", "B", "C", "D", "E", "H", "L", "I", "R", "F", "IXH", "IXL", "IYH", "IYL"}
_ALIAS8 = {"XH": "IXH", "XL": "IXL", "YH": "IYH", "YL": "IYL", "HX": "IXH", "LX": "IXL",
           "HY": "IYH", "LY": "IYL"}
_R16 = {"BC", "DE", "HL", "SP", "AF", "AF'", "IX", "IY"}
_CC = {"NZ", "Z", "NC", "C", "PO", "PE", "P", "M"}


def _split_operands(s: str):
    out, depth, cur, q = [], 0, "", None
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in "'\"" and not (ch == "'" and cur.strip().upper() == "AF"):
            q = ch
            cur += ch
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def _wholly_parenthesized(s):
    if not (s.startswith("(") and s.endswith(")")):
        return False
    depth = 0
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and i != len(s) - 1:
                return False
    return True


@dataclass
class _Op:
    """Operando analizado: lista de patrones candidatos y valor (expresión)."""
    cands: list
    expr: str | None = None       # expresión numérica asociada
    disp: str | None = None       # expresión de desplazamiento para (IX+d)


def _parse_operand(text: str) -> _Op:
    t = text.strip()
    up = t.upper().replace(" ", "")
    up = _ALIAS8.get(up, up)
    if up in _R8 or up in _R16 or up in _CC:
        cands = []
        if up in _R8:
            cands.append(("r", up))
        if up in _R16:
            cands.append(("rr", up))
        if up in _CC:
            cands.append(("cc", up))
        if up != "AF'":
            cands.append(("imm",))   # por si es una etiqueta con nombre de registro
        return _Op(cands, expr=t)
    if _wholly_parenthesized(t):
        inner = t[1:-1].strip()
        iu = inner.upper().replace(" ", "")
        if iu in ("HL", "BC", "DE", "SP", "IX", "IY", "C"):
            return _Op([("ind", iu)] + ([("idx", iu)] if iu in ("IX", "IY") else []),
                       disp="0" if iu in ("IX", "IY") else None)
        m = re.match(r"(IX|IY)\s*([+-].*)$", inner, re.I)
        if m:
            return _Op([("idx", m.group(1).upper())], disp=m.group(2))
        return _Op([("indimm",)], expr=inner)
    return _Op([("imm",)], expr=t)


# ---------------------------------------------------------------------------
# Ensamblador
# ---------------------------------------------------------------------------

@dataclass
class Segment:
    org: int
    data: bytearray = field(default_factory=bytearray)

    @property
    def end(self):
        return self.org + len(self.data)


@dataclass
class AsmResult:
    segments: list
    symbols: dict
    listing: list          # (addr, bytes, line_no, texto)

    def image(self, start=None, end=None, fill=0):
        segs = [s for s in self.segments if s.data]
        if not segs:
            return bytes()
        lo = min(s.org for s in segs) if start is None else start
        hi = max(s.end for s in segs) if end is None else end
        buf = bytearray([fill]) * (hi - lo)
        for s in segs:
            for i, b in enumerate(s.data):
                a = s.org + i
                if lo <= a < hi:
                    buf[a - lo] = b
        return bytes(buf)

    def poke_into(self, mem):
        """Copia todos los segmentos en un bytearray de 64K."""
        for s in self.segments:
            for i, b in enumerate(s.data):
                mem[(s.org + i) & 0xFFFF] = b

    @property
    def start(self):
        segs = [s for s in self.segments if s.data]
        return min(s.org for s in segs) if segs else 0


_DIRECTIVES = {"ORG", "EQU", "DB", "DEFB", "DEFM", "DM", "DW", "DEFW", "DS", "DEFS", "ALIGN",
               "ASSERT", "IF", "ELSE", "ENDIF", "INCBIN", "END", "BYTE", "WORD", "BLOCK", "=",
               "DEFINE"}


class Assembler:
    def __init__(self, symbols=None, include_dirs=None):
        self.predefined = dict(symbols or {})
        self.include_dirs = include_dirs or []

    # -- API ---------------------------------------------------------------
    def assemble(self, source: str, filename="<asm>") -> AsmResult:
        lines = _expand_rept(source.splitlines(), self.predefined)
        symbols = dict(self.predefined)
        prev = None
        for _ in range(10):
            res = self._pass(lines, symbols, final=False, filename=filename)
            if res.symbols == prev:
                break
            prev = dict(res.symbols)
            symbols = dict(self.predefined)
            symbols.update(res.symbols)
        return self._pass(lines, symbols, final=True, filename=filename)

    # -- una pasada ----------------------------------------------------------
    def _pass(self, lines, known, final, filename):
        self.final = final
        self.known = known
        self.defined = dict(self.predefined)
        self.segments = [Segment(0)]
        self.pc = 0
        self.scope = ""
        self.listing = []
        self.filename = filename
        cond_stack = []
        for no, raw in enumerate(lines, 1):
            self.line_no, self.line = no, raw
            try:
                code = self._strip_comment(raw)
                if not code.strip():
                    continue
                label, mnem, rest = self._split_line(code)
                mu = mnem.upper() if mnem else ""
                if mu in ("IF", "ELSE", "ENDIF"):
                    if mu == "IF":
                        active = all(cond_stack)
                        v = self._eval(rest, required=True) if active else 0
                        cond_stack.append(bool(v))
                    elif mu == "ELSE":
                        if not cond_stack:
                            raise AsmError("ELSE sin IF")
                        cond_stack[-1] = not cond_stack[-1]
                    else:
                        if not cond_stack:
                            raise AsmError("ENDIF sin IF")
                        cond_stack.pop()
                    continue
                if not all(cond_stack):
                    continue
                if mu in ("EQU", "=", "DEFINE"):
                    if not label:
                        raise AsmError("EQU sin etiqueta")
                    self._define(label, self._eval(rest, required=final), equ=True)
                    continue
                if label:
                    self._define(label, self.pc)
                if not mnem:
                    continue
                if mu == "END":
                    break
                start = self.pc
                data = self._directive(mu, rest) if mu in _DIRECTIVES else self._instruction(mnem, rest)
                if data is not None:
                    self._emit(data)
                    self.listing.append((start, bytes(data), no, raw))
            except AsmError as e:
                if e.line_no is None:
                    raise AsmError(e.msg, no, raw, filename) from None
                raise
        if cond_stack:
            raise AsmError("falta ENDIF", len(lines), None, filename)
        segs = [s for s in self.segments if s.data]
        return AsmResult(segs, dict(self.defined), self.listing)

    @staticmethod
    def _strip_comment(line):
        out, q = "", None
        for i, ch in enumerate(line):
            if q:
                out += ch
                if ch == q:
                    q = None
                continue
            if ch == ";":
                break
            if ch in "\"'":
                # AF' no abre comilla
                if ch == "'" and out.upper().rstrip().endswith("AF"):
                    out += ch
                    continue
                if ch == "'" and i + 2 < len(line) + 1 and line[i + 1:i + 3].endswith("'"):
                    pass
                q = ch
            out += ch
        return out.rstrip()

    def _split_line(self, code):
        label = None
        s = code
        m = re.match(r"^\s*(\.?[A-Za-z_][A-Za-z0-9_.]*):", s)
        if m:
            label = m.group(1)
            s = s[m.end():]
        elif s and not s[0].isspace():
            m = re.match(r"^(\.?[A-Za-z_][A-Za-z0-9_.]*)", s)
            if m:
                word = m.group(1)
                if word.upper() not in _DIRECTIVES and word.upper() not in _mnemonics():
                    label = word
                    s = s[m.end():]
        s = s.strip()
        if not s:
            return label, None, ""
        m = re.match(r"^(\S+)\s*(.*)$", s)
        mnem, rest = m.group(1), m.group(2)
        if mnem == "=":
            return label, "=", rest
        return label, mnem, rest.strip()

    def _full_name(self, name):
        if name.startswith("."):
            return self.scope + name
        return name

    def _define(self, name, value, equ=False):
        if not name.startswith("."):
            if not equ:
                self.scope = name
        full = self._full_name(name)
        if full in self.defined and self.defined[full] != value and self.final:
            raise AsmError(f"símbolo redefinido: {full}")
        self.defined[full] = value

    def _resolve(self, name):
        full = self._full_name(name)
        for n in (full, name):
            if n in self.defined:
                return self.defined[n]
            if n in self.known:
                return self.known[n]
        raise _Unresolved(full)

    def _eval(self, text, required=True, default=0):
        try:
            return _Expr(text, self._resolve, self.pc).parse()
        except _Unresolved as e:
            if required and self.final:
                raise AsmError(f"símbolo no definido: {e}")
            return default

    def _eval_known(self, text):
        """Evalúa si es posible; devuelve None si hay símbolos sin resolver."""
        try:
            return _Expr(text, self._resolve, self.pc).parse()
        except _Unresolved:
            return None
        except AsmError:
            return None

    def _emit(self, data):
        seg = self.segments[-1]
        if seg.end != self.pc:
            seg = Segment(self.pc)
            self.segments.append(seg)
        seg.data.extend(data)
        self.pc += len(data)
        if self.pc > 0x10000 and self.final:
            raise AsmError("el código sobrepasa $FFFF")

    # -- directivas ----------------------------------------------------------
    def _directive(self, d, rest):
        if d == "ORG":
            self.pc = self._eval(rest) & 0xFFFF
            self.segments.append(Segment(self.pc))
            return None
        if d in ("DB", "DEFB", "DEFM", "DM", "BYTE"):
            out = bytearray()
            for item in _split_operands(rest):
                if len(item) >= 2 and item[0] == item[-1] and item[0] in "\"'" and (
                        len(item) != 3 or item[0] == '"'):
                    out.extend(item[1:-1].encode("latin-1").decode("unicode_escape").encode("latin-1"))
                else:
                    v = self._eval(item)
                    if self.final and not -128 <= v <= 255:
                        raise AsmError(f"valor de byte fuera de rango: {v}")
                    out.append(v & 0xFF)
            return out
        if d in ("DW", "DEFW", "WORD"):
            out = bytearray()
            for item in _split_operands(rest):
                v = self._eval(item) & 0xFFFF
                out += bytes([v & 0xFF, v >> 8])
            return out
        if d in ("DS", "DEFS", "BLOCK"):
            parts = _split_operands(rest)
            n = self._eval(parts[0])
            fill = self._eval(parts[1]) & 0xFF if len(parts) > 1 else 0
            if n < 0:
                raise AsmError("DS negativo")
            return bytearray([fill]) * n
        if d == "ALIGN":
            n = self._eval(rest)
            pad = (-self.pc) % n
            return bytearray(pad)
        if d == "ASSERT":
            parts = _split_operands(rest)
            if self.final and not self._eval(parts[0]):
                msg = parts[1].strip('"') if len(parts) > 1 else parts[0]
                raise AsmError(f"ASSERT fallido: {msg}")
            return None
        if d == "INCBIN":
            name = rest.strip().strip('"')
            for base in [""] + list(self.include_dirs):
                p = os.path.join(base, name)
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        return bytearray(f.read())
            raise AsmError(f"no se encuentra {name}")
        raise AsmError(f"directiva no soportada: {d}")

    # -- instrucciones -------------------------------------------------------
    def _instruction(self, mnem, rest):
        op = mnem.upper()
        texts = _split_operands(rest) if rest else []
        parsed = [_parse_operand(t) for t in texts]
        tpl, chosen = self._lookup(op, parsed)
        if tpl is None:
            # alias habituales
            if op in ("ADD", "ADC", "SBC", "SUB", "AND", "OR", "XOR", "CP"):
                if op in ("SUB", "AND", "OR", "XOR", "CP") and len(parsed) == 2 and \
                        ("r", "A") in parsed[0].cands:
                    parsed = parsed[1:]
                    tpl, chosen = self._lookup(op, parsed)
                elif op in ("ADD", "ADC", "SBC") and len(parsed) == 1:
                    parsed = [_parse_operand("A")] + parsed
                    tpl, chosen = self._lookup(op, parsed)
            elif op == "JP" and len(parsed) == 1 and parsed[0].cands and \
                    parsed[0].cands[0][0] == "rr" and parsed[0].cands[0][1] in ("HL", "IX", "IY"):
                parsed = [_parse_operand(f"({parsed[0].cands[0][1]})")]
                tpl, chosen = self._lookup(op, parsed)
            elif op == "IN" and len(parsed) == 1 and ("ind", "C") in parsed[0].cands:
                parsed = [_parse_operand("F")] + parsed
                tpl, chosen = self._lookup(op, parsed)
            elif op == "EX" and len(parsed) == 2 and ("rr", "AF") in parsed[0].cands and \
                    ("rr", "AF") in parsed[1].cands:
                parsed[1] = _parse_operand("AF'")
                tpl, chosen = self._lookup(op, parsed)
        if tpl is None:
            raise AsmError(f"instrucción no válida: {mnem} {rest}".strip())
        return self._encode(tpl, chosen, parsed)

    def _lookup(self, op, parsed):
        table = _table()
        combos = [[]]
        for p in parsed:
            new = []
            for c in combos:
                cands = list(p.cands)
                if cands == [("imm",)]:
                    v = self._eval_known(p.expr)
                    if v is not None:
                        cands = [("imm",), ("lit", v)]
                new.extend(c + [x] for x in cands)
            combos = new
        for c in combos:
            key = (op, tuple(c))
            if key in table:
                return table[key], c
        return None, None

    def _encode(self, tpl, chosen, parsed):
        out = bytearray(tpl.prefix)
        nums = []
        disp = None
        for pat, p in zip(chosen, parsed):
            if pat[0] == "idx":
                disp = p.disp or "0"
            elif pat[0] in ("imm", "indimm"):
                nums.append(p.expr)
        ni = 0
        for f in tpl.fields:
            if f == "d":
                v = self._eval(disp)
                if self.final and not -128 <= v <= 127:
                    raise AsmError(f"desplazamiento fuera de rango: {v}")
                out.append(v & 0xFF)
            elif f == "n":
                v = self._eval(nums[ni])
                ni += 1
                if self.final and not -128 <= v <= 255:
                    raise AsmError(f"valor de 8 bits fuera de rango: {v}")
                out.append(v & 0xFF)
            elif f == "nn":
                v = self._eval(nums[ni])
                ni += 1
                if self.final and not -32768 <= v <= 65535:
                    raise AsmError(f"valor de 16 bits fuera de rango: {v}")
                out += bytes([v & 0xFF, (v >> 8) & 0xFF])
            elif f == "e":
                v = self._eval(nums[ni], default=self.pc + 2)
                ni += 1
                rel = v - (self.pc + 2)
                if self.final and not -128 <= rel <= 127:
                    raise AsmError(f"salto relativo fuera de rango ({rel})")
                out.append(rel & 0xFF)
        out += tpl.suffix
        return out


_MNEMONICS = None


def _expand_rept(lines, symbols):
    """Expande bloques REPT n ... ENDR (anidables). ``n`` debe ser constante."""
    out = []
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*REPT\s+(.+?)\s*(;.*)?$", lines[i], re.I)
        if not m:
            out.append(lines[i])
            i += 1
            continue
        depth, j = 1, i + 1
        while j < len(lines):
            if re.match(r"^\s*REPT\b", lines[j], re.I):
                depth += 1
            elif re.match(r"^\s*ENDR\b", lines[j], re.I):
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            n = _Expr(m.group(1), lambda k: symbols[k], 0).parse()
        except Exception:
            raise AsmError(f"REPT necesita un número constante: {m.group(1)}", i + 1, lines[i])
        body = _expand_rept(lines[i + 1:j], symbols)
        out.extend(body * n)
        i = j + 1
    return out


def _mnemonics():
    global _MNEMONICS
    if _MNEMONICS is None:
        _MNEMONICS = {k[0] for k in _table()}
    return _MNEMONICS


def assemble(source: str, symbols=None, filename="<asm>", include_dirs=None) -> AsmResult:
    return Assembler(symbols, include_dirs).assemble(source, filename)


def assemble_file(path, symbols=None) -> AsmResult:
    with open(path, encoding="utf-8") as f:
        src = f.read()
    return Assembler(symbols, [os.path.dirname(os.path.abspath(path))]).assemble(src, path)
