"""Ensamblador de Z80 (el subconjunto que usa el driver de sonido).

El sonido de la Neo Geo lo lleva un Z80 con su propia ROM (la M1), asi que hay
que generar codigo de Z80. En vez de pedirte que instales un ensamblador, el
kit trae este, pequeno y comprobado: tests/test_z80.py verifica las
codificaciones contra los valores documentados del juego de instrucciones, y
tests/test_sonido.py ejecuta el driver ya ensamblado en un emulador de Z80.

Soporta etiquetas, `org`, `db`, `dw`, `ds`, `equ` y las instrucciones que hacen
falta para el driver. Cualquier cosa que no entienda es un error claro, nunca
un byte al azar.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


class Z80Error(Exception):
    """Error de ensamblado, con numero de linea."""


REGS8 = {"b": 0, "c": 1, "d": 2, "e": 3, "h": 4, "l": 5, "(hl)": 6, "a": 7}
REGS16 = {"bc": 0, "de": 1, "hl": 2, "sp": 3}
PUSH16 = {"bc": 0, "de": 1, "hl": 2, "af": 3}
CONDS = {"nz": 0, "z": 1, "nc": 2, "c": 3, "po": 4, "pe": 5, "p": 6, "m": 7}
ALU = {"add": 0, "adc": 1, "sub": 2, "sbc": 3, "and": 4, "xor": 5, "or": 6, "cp": 7}
ALU_IMM = {"add": 0xC6, "adc": 0xCE, "sub": 0xD6, "sbc": 0xDE,
           "and": 0xE6, "xor": 0xEE, "or": 0xF6, "cp": 0xFE}
SIMPLE = {
    "nop": [0x00], "halt": [0x76], "di": [0xF3], "ei": [0xFB],
    "ret": [0xC9], "reti": [0xED, 0x4D], "retn": [0xED, 0x45],
    "exx": [0xD9], "ex de,hl": [0xEB], "ex af,af'": [0x08],
    "rlca": [0x07], "rrca": [0x0F], "rla": [0x17], "rra": [0x1F],
    "cpl": [0x2F], "scf": [0x37], "ccf": [0x3F], "daa": [0x27],
    "im 0": [0xED, 0x46], "im 1": [0xED, 0x56], "im 2": [0xED, 0x5E],
    "ldir": [0xED, 0xB0], "lddr": [0xED, 0xB8],
    "neg": [0xED, 0x44],
}
# Rotaciones y desplazamientos sobre registro (prefijo CB).
CB_OPS = {"rlc": 0, "rrc": 1, "rl": 2, "rr": 3, "sla": 4, "sra": 5, "sll": 6, "srl": 7}


class Ensamblador:
    def __init__(self):
        self.labels: Dict[str, int] = {}
        self.output = bytearray()
        self.origin = 0
        self.pc = 0                 # posicion actual, para el simbolo '$'

    # ---------------------------------------------------------- expresiones
    def valor(self, texto: str, linea: int, permitir_pendiente: bool = False) -> int:
        texto = texto.strip()
        if not texto:
            raise Z80Error("linea %d: falta un valor" % linea)
        # suma/resta simple de etiquetas y numeros: "tabla+2"
        partes = re.split(r"([+\-])", texto)
        total = 0
        signo = 1
        for parte in partes:
            parte = parte.strip()
            if parte == "+":
                signo = 1
                continue
            if parte == "-":
                signo = -1
                continue
            if not parte:
                continue
            total += signo * self._atomo(parte, linea, permitir_pendiente)
        return total

    def _atomo(self, texto: str, linea: int, permitir_pendiente: bool) -> int:
        texto = texto.strip()
        if texto == "$":
            return self.pc
        if (texto.startswith("$") and len(texto) > 1) or texto.startswith("0x"):
            return int(texto.lstrip("$").replace("0x", ""), 16)
        if texto.lower().endswith("h") and re.match(r"^[0-9a-fA-F]+h$", texto):
            return int(texto[:-1], 16)
        if texto.startswith("%"):
            return int(texto[1:], 2)
        if re.match(r"^-?\d+$", texto):
            return int(texto)
        if texto.startswith("'") and texto.endswith("'") and len(texto) == 3:
            return ord(texto[1])
        if texto in self.labels:
            return self.labels[texto]
        if permitir_pendiente:
            return 0                       # primera pasada: aun no se conoce
        raise Z80Error("linea %d: no se que es '%s'" % (linea, texto))

    # ------------------------------------------------------------ ensamblado
    def ensamblar(self, fuente: str) -> bytes:
        lineas = self._preparar(fuente)
        self._pasada(lineas, primera=True)
        self.output = bytearray()
        self._pasada(lineas, primera=False)
        return bytes(self.output)

    def _preparar(self, fuente: str) -> List[Tuple[int, str]]:
        salida: List[Tuple[int, str]] = []
        for numero, linea in enumerate(fuente.split("\n"), start=1):
            texto = linea.split(";")[0].strip()
            if texto:
                salida.append((numero, texto))
        return salida

    def _pasada(self, lineas: List[Tuple[int, str]], primera: bool) -> None:
        pc = self.origin
        for numero, texto in lineas:
            self.pc = pc
            while ":" in texto.split('"')[0][:40] and re.match(r"^[.\w]+:", texto):
                etiqueta, _, resto = texto.partition(":")
                etiqueta = etiqueta.strip()
                if primera:
                    if etiqueta in self.labels and self.labels[etiqueta] != pc:
                        raise Z80Error("linea %d: etiqueta repetida '%s'" % (numero, etiqueta))
                    self.labels[etiqueta] = pc
                texto = resto.strip()
                if not texto:
                    break
            if not texto:
                continue
            self.pc = pc
            bytes_generados = self._instruccion(texto, pc, numero, primera)
            if not primera:
                self.output.extend(bytes_generados)
            pc += len(bytes_generados)

    # ------------------------------------------------------- una instruccion
    def _instruccion(self, texto: str, pc: int, linea: int, primera: bool) -> List[int]:
        bajo = re.sub(r"\s+", " ", texto.strip())
        clave = bajo.lower()

        if clave in SIMPLE:
            return list(SIMPLE[clave])

        mnem, _, args = bajo.partition(" ")
        mnem = mnem.lower()
        args = args.strip()
        lista = [a.strip() for a in self._separar(args)] if args else []

        if mnem == "org":
            self.origin = self.valor(args, linea, primera)
            return []
        if mnem == "equ":
            raise Z80Error("linea %d: 'equ' va detras de una etiqueta" % linea)
        if mnem == "db" or mnem == "defb":
            datos: List[int] = []
            for elemento in lista:
                if elemento.startswith('"') and elemento.endswith('"'):
                    datos.extend(ord(ch) for ch in elemento[1:-1])
                else:
                    datos.append(self.valor(elemento, linea, primera) & 0xFF)
            return datos
        if mnem == "dw" or mnem == "defw":
            datos = []
            for elemento in lista:
                v = self.valor(elemento, linea, primera) & 0xFFFF
                datos.extend([v & 0xFF, v >> 8])
            return datos
        if mnem == "ds":
            cuantos = self.valor(lista[0], linea, primera)
            relleno = self.valor(lista[1], linea, primera) if len(lista) > 1 else 0
            return [relleno & 0xFF] * cuantos

        metodo = getattr(self, "_op_" + mnem, None)
        if metodo is None:
            raise Z80Error("linea %d: no conozco la instruccion '%s'" % (linea, mnem))
        return metodo(lista, pc, linea, primera)

    @staticmethod
    def _separar(args: str) -> List[str]:
        partes, nivel, actual = [], 0, []
        for ch in args:
            if ch == "(":
                nivel += 1
            elif ch == ")":
                nivel -= 1
            if ch == "," and nivel == 0:
                partes.append("".join(actual))
                actual = []
                continue
            actual.append(ch)
        partes.append("".join(actual))
        return partes

    # ------------------------------------------------------------- opcodes
    def _op_ld(self, a: List[str], pc: int, linea: int, primera: bool) -> List[int]:
        if len(a) != 2:
            raise Z80Error("linea %d: 'ld' necesita dos operandos" % linea)
        destino, origen = a[0].lower(), a[1]
        origen_bajo = origen.lower()

        if destino in REGS8 and origen_bajo in REGS8:
            if destino == "(hl)" and origen_bajo == "(hl)":
                raise Z80Error("linea %d: 'ld (hl),(hl)' no existe" % linea)
            return [0x40 | (REGS8[destino] << 3) | REGS8[origen_bajo]]
        if destino in REGS8 and not origen_bajo.startswith("("):
            return [0x06 | (REGS8[destino] << 3), self.valor(origen, linea, primera) & 0xFF]
        if destino in REGS16 and not origen_bajo.startswith("("):
            v = self.valor(origen, linea, primera) & 0xFFFF
            return [0x01 | (REGS16[destino] << 4), v & 0xFF, v >> 8]
        if destino == "a" and origen_bajo in ("(bc)", "(de)"):
            return [0x0A if origen_bajo == "(bc)" else 0x1A]
        if destino in ("(bc)", "(de)") and origen_bajo == "a":
            return [0x02 if destino == "(bc)" else 0x12]
        if destino == "a" and origen_bajo.startswith("("):
            v = self.valor(origen_bajo[1:-1], linea, primera) & 0xFFFF
            return [0x3A, v & 0xFF, v >> 8]
        if destino.startswith("(") and origen_bajo == "a":
            v = self.valor(destino[1:-1], linea, primera) & 0xFFFF
            return [0x32, v & 0xFF, v >> 8]
        if destino in REGS16 and origen_bajo.startswith("("):
            v = self.valor(origen_bajo[1:-1], linea, primera) & 0xFFFF
            if destino == "hl":
                return [0x2A, v & 0xFF, v >> 8]
            return [0xED, 0x4B | (REGS16[destino] << 4), v & 0xFF, v >> 8]
        if destino.startswith("(") and origen_bajo in REGS16:
            v = self.valor(destino[1:-1], linea, primera) & 0xFFFF
            if origen_bajo == "hl":
                return [0x22, v & 0xFF, v >> 8]
            return [0xED, 0x43 | (REGS16[origen_bajo] << 4), v & 0xFF, v >> 8]
        if destino == "sp" and origen_bajo == "hl":
            return [0xF9]
        raise Z80Error("linea %d: no se ensamblar 'ld %s,%s'" % (linea, a[0], a[1]))

    def _alu(self, mnem: str, a: List[str], linea: int, primera: bool) -> List[int]:
        operando = a[-1]
        bajo = operando.lower()
        if len(a) == 2 and a[0].lower() == "hl":       # add hl,rr
            if mnem != "add":
                raise Z80Error("linea %d: solo existe 'add hl,rr'" % linea)
            if bajo not in REGS16:
                raise Z80Error("linea %d: 'add hl,%s' no existe" % (linea, operando))
            return [0x09 | (REGS16[bajo] << 4)]
        if bajo in REGS8:
            return [0x80 | (ALU[mnem] << 3) | REGS8[bajo]]
        return [ALU_IMM[mnem], self.valor(operando, linea, primera) & 0xFF]

    def _op_add(self, a, pc, linea, primera): return self._alu("add", a, linea, primera)
    def _op_adc(self, a, pc, linea, primera): return self._alu("adc", a, linea, primera)
    def _op_sub(self, a, pc, linea, primera): return self._alu("sub", a, linea, primera)
    def _op_sbc(self, a, pc, linea, primera): return self._alu("sbc", a, linea, primera)
    def _op_and(self, a, pc, linea, primera): return self._alu("and", a, linea, primera)
    def _op_xor(self, a, pc, linea, primera): return self._alu("xor", a, linea, primera)
    def _op_or(self, a, pc, linea, primera): return self._alu("or", a, linea, primera)
    def _op_cp(self, a, pc, linea, primera): return self._alu("cp", a, linea, primera)

    def _op_inc(self, a, pc, linea, primera):
        bajo = a[0].lower()
        if bajo in REGS16:
            return [0x03 | (REGS16[bajo] << 4)]
        if bajo in REGS8:
            return [0x04 | (REGS8[bajo] << 3)]
        raise Z80Error("linea %d: 'inc %s' no existe" % (linea, a[0]))

    def _op_dec(self, a, pc, linea, primera):
        bajo = a[0].lower()
        if bajo in REGS16:
            return [0x0B | (REGS16[bajo] << 4)]
        if bajo in REGS8:
            return [0x05 | (REGS8[bajo] << 3)]
        raise Z80Error("linea %d: 'dec %s' no existe" % (linea, a[0]))

    def _op_jp(self, a, pc, linea, primera):
        if len(a) == 2:
            cond = a[0].lower()
            if cond not in CONDS:
                raise Z80Error("linea %d: condicion desconocida '%s'" % (linea, a[0]))
            v = self.valor(a[1], linea, primera) & 0xFFFF
            return [0xC2 | (CONDS[cond] << 3), v & 0xFF, v >> 8]
        if a[0].lower() in ("(hl)", "hl"):
            return [0xE9]
        v = self.valor(a[0], linea, primera) & 0xFFFF
        return [0xC3, v & 0xFF, v >> 8]

    def _salto_relativo(self, destino: int, pc: int, linea: int, primera: bool) -> int:
        if primera:
            return 0
        delta = destino - (pc + 2)
        if delta < -128 or delta > 127:
            raise Z80Error("linea %d: salto relativo demasiado largo (%d)" % (linea, delta))
        return delta & 0xFF

    def _op_jr(self, a, pc, linea, primera):
        if len(a) == 2:
            cond = a[0].lower()
            if cond not in ("nz", "z", "nc", "c"):
                raise Z80Error("linea %d: 'jr' solo admite nz, z, nc y c" % linea)
            opcode = {"nz": 0x20, "z": 0x28, "nc": 0x30, "c": 0x38}[cond]
            destino = self.valor(a[1], linea, primera)
            return [opcode, self._salto_relativo(destino, pc, linea, primera)]
        destino = self.valor(a[0], linea, primera)
        return [0x18, self._salto_relativo(destino, pc, linea, primera)]

    def _op_djnz(self, a, pc, linea, primera):
        destino = self.valor(a[0], linea, primera)
        return [0x10, self._salto_relativo(destino, pc, linea, primera)]

    def _op_call(self, a, pc, linea, primera):
        if len(a) == 2:
            cond = a[0].lower()
            if cond not in CONDS:
                raise Z80Error("linea %d: condicion desconocida '%s'" % (linea, a[0]))
            v = self.valor(a[1], linea, primera) & 0xFFFF
            return [0xC4 | (CONDS[cond] << 3), v & 0xFF, v >> 8]
        v = self.valor(a[0], linea, primera) & 0xFFFF
        return [0xCD, v & 0xFF, v >> 8]

    def _op_ret(self, a, pc, linea, primera):
        if not a or not a[0]:
            return [0xC9]
        cond = a[0].lower()
        if cond not in CONDS:
            raise Z80Error("linea %d: condicion desconocida '%s'" % (linea, a[0]))
        return [0xC0 | (CONDS[cond] << 3)]

    def _op_push(self, a, pc, linea, primera):
        bajo = a[0].lower()
        if bajo not in PUSH16:
            raise Z80Error("linea %d: 'push %s' no existe" % (linea, a[0]))
        return [0xC5 | (PUSH16[bajo] << 4)]

    def _op_pop(self, a, pc, linea, primera):
        bajo = a[0].lower()
        if bajo not in PUSH16:
            raise Z80Error("linea %d: 'pop %s' no existe" % (linea, a[0]))
        return [0xC1 | (PUSH16[bajo] << 4)]

    def _op_out(self, a, pc, linea, primera):
        destino, origen = a[0].lower(), a[1].lower()
        if origen != "a" or not destino.startswith("("):
            raise Z80Error("linea %d: solo se admite 'out (n),a'" % linea)
        return [0xD3, self.valor(destino[1:-1], linea, primera) & 0xFF]

    def _op_in(self, a, pc, linea, primera):
        destino, origen = a[0].lower(), a[1].lower()
        if destino != "a" or not origen.startswith("("):
            raise Z80Error("linea %d: solo se admite 'in a,(n)'" % linea)
        return [0xDB, self.valor(origen[1:-1], linea, primera) & 0xFF]

    def _cb(self, mnem: str, a: List[str], linea: int) -> List[int]:
        bajo = a[0].lower()
        if bajo not in REGS8:
            raise Z80Error("linea %d: '%s %s' no existe" % (linea, mnem, a[0]))
        return [0xCB, (CB_OPS[mnem] << 3) | REGS8[bajo]]

    def _op_rlc(self, a, pc, linea, primera): return self._cb("rlc", a, linea)
    def _op_rrc(self, a, pc, linea, primera): return self._cb("rrc", a, linea)
    def _op_rl(self, a, pc, linea, primera): return self._cb("rl", a, linea)
    def _op_rr(self, a, pc, linea, primera): return self._cb("rr", a, linea)
    def _op_sla(self, a, pc, linea, primera): return self._cb("sla", a, linea)
    def _op_sra(self, a, pc, linea, primera): return self._cb("sra", a, linea)
    def _op_srl(self, a, pc, linea, primera): return self._cb("srl", a, linea)

    def _op_bit(self, a, pc, linea, primera):
        numero = self.valor(a[0], linea, primera)
        bajo = a[1].lower()
        return [0xCB, 0x40 | (numero << 3) | REGS8[bajo]]

    def _op_set(self, a, pc, linea, primera):
        numero = self.valor(a[0], linea, primera)
        return [0xCB, 0xC0 | (numero << 3) | REGS8[a[1].lower()]]

    def _op_res(self, a, pc, linea, primera):
        numero = self.valor(a[0], linea, primera)
        return [0xCB, 0x80 | (numero << 3) | REGS8[a[1].lower()]]

    def _op_ex(self, a, pc, linea, primera):
        if [x.lower() for x in a] == ["de", "hl"]:
            return [0xEB]
        raise Z80Error("linea %d: solo se admite 'ex de,hl'" % linea)


def ensamblar(fuente: str) -> Tuple[bytes, Dict[str, int]]:
    """Ensambla y devuelve (bytes, etiquetas)."""
    asm = Ensamblador()
    datos = asm.ensamblar(fuente)
    return datos, dict(asm.labels)
