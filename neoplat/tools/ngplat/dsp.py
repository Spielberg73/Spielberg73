"""Ensamblador del DSP de la Jaguar (el subconjunto que usa el driver de sonido).

El sonido de la Jaguar no sale de un chip de sonido: sale de dos DAC de 16 bits
que hay que alimentar muestra a muestra, y quien puede hacerlo a tiempo es el
**DSP** de Jerry, un RISC de 32 bits con su propia RAM. O sea que para que suene
hay que escribir un programa para ese procesador, igual que en la Neo Geo hay
que escribir uno para el Z80.

Como con el Z80, en vez de pedirte que instales un ensamblador el kit trae este.
Es pequeno porque el driver es pequeno: `tools/ngplat/jerry.py`.

Del juego de instrucciones del RISC:

  - cada instruccion es **una palabra de 16 bits**: seis bits de codigo (15-10),
    cinco de primer operando (9-5) y cinco de segundo (4-0);
  - el segundo operando es casi siempre el registro **destino**;
  - `movei` es la excepcion: lleva detras la constante de 32 bits **con la
    palabra baja primero**;
  - `jump` y `jr` tienen **ranura de retardo**: la instruccion que va detras se
    ejecuta antes de saltar. Aqui no se rellena sola, se escribe a mano;
  - los desplazamientos inmediatos codifican el 32 como 0... menos `shlq`, que
    es el unico que guarda `32 - n`.

Las codificaciones se comprueban una a una en tests/test_dsp.py.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple


class DspError(Exception):
    """Error de ensamblado, con numero de linea."""


# codigo de operacion de cada instruccion (los seis bits de arriba)
RS_RD = {                       # `op rM,rN`  ->  rN = rN op rM
    "add": 0, "addc": 1, "sub": 4, "subc": 5, "and": 9, "or": 10, "xor": 11,
    "mult": 16, "imult": 17, "div": 21, "sh": 23, "sha": 26, "ror": 28,
    "cmp": 30, "move": 34, "moveta": 36, "movefa": 37, "mtoi": 55, "normi": 56,
}
Q_RD = {                        # `op #q,rN`, con el 32 guardado como 0
    "addq": 2, "addqt": 3, "subq": 6, "subqt": 7,
    "shrq": 25, "sharq": 27, "rorq": 29,
}
BIT_RD = {"btst": 13, "bset": 14, "bclr": 15}     # numero de bit, 0..31
SOLO_RD = {"neg": 8, "not": 12, "resmac": 19, "abs": 22, "sat16s": 33}
CONDICIONES = {                 # las que entiende el salto
    "t": 0, "siempre": 0,       # incondicional
    "ne": 1, "nz": 1,           # el resultado no era cero
    "eq": 2, "z": 2,            # era cero
    "cc": 4, "nc": 4,           # sin acarreo
    "cs": 8, "c": 8,            # con acarreo
    "nunca": 0x1F,
}

RAM_DSP = 0xF1B000              # donde vive la RAM local del DSP
RAM_DSP_FIN = RAM_DSP + 8 * 1024


def _palabra(codigo: int, p1: int, p2: int) -> int:
    return ((codigo & 0x3F) << 10) | ((p1 & 0x1F) << 5) | (p2 & 0x1F)


class Ensamblador:
    def __init__(self, origen: int = RAM_DSP):
        self.etiquetas: Dict[str, int] = {}
        self.salida = bytearray()
        self.origen = origen
        self.pc = origen

    # ---------------------------------------------------------- expresiones
    def valor(self, texto: str, linea: int, pendiente: bool = False) -> int:
        texto = texto.strip()
        if not texto:
            raise DspError("linea %d: falta un valor" % linea)
        total, signo = 0, 1
        for parte in re.split(r"([+\-])", texto):
            parte = parte.strip()
            if parte == "+":
                signo = 1
            elif parte == "-":
                signo = -1
            elif parte:
                total += signo * self._atomo(parte, linea, pendiente)
        return total

    def _atomo(self, texto: str, linea: int, pendiente: bool) -> int:
        if texto == "$":
            return self.pc
        if texto.startswith("$") and len(texto) > 1:
            return int(texto[1:], 16)
        if texto.startswith("0x"):
            return int(texto[2:], 16)
        if texto.startswith("%"):
            return int(texto[1:], 2)
        if re.match(r"^-?\d+$", texto):
            return int(texto)
        if texto in self.etiquetas:
            return self.etiquetas[texto]
        if pendiente:
            return self.origen          # primera pasada: aun no se conoce
        raise DspError("linea %d: no se que es '%s'" % (linea, texto))

    def registro(self, texto: str, linea: int) -> int:
        texto = texto.strip().lower()
        m = re.match(r"^r(\d+)$", texto)
        if not m or int(m.group(1)) > 31:
            raise DspError("linea %d: '%s' no es un registro (r0 a r31)"
                           % (linea, texto))
        return int(m.group(1))

    def _indirecto(self, texto: str, linea: int) -> int:
        texto = texto.strip()
        if not (texto.startswith("(") and texto.endswith(")")):
            raise DspError("linea %d: se esperaba (rN) y hay '%s'" % (linea, texto))
        return self.registro(texto[1:-1], linea)

    @staticmethod
    def _cero_es_32(q: int, linea: int) -> int:
        if q == 32:
            return 0
        if not 1 <= q <= 31:
            raise DspError("linea %d: el inmediato es de 1 a 32 y es %d" % (linea, q))
        return q

    # ------------------------------------------------------------ ensamblado
    def ensamblar(self, fuente: str) -> bytes:
        lineas = self._preparar(fuente)
        self._pasada(lineas, primera=True)
        self.salida = bytearray()
        self.pc = self.origen
        self._pasada(lineas, primera=False)
        return bytes(self.salida)

    def _preparar(self, fuente: str) -> List[Tuple[int, str]]:
        lineas = []
        for numero, cruda in enumerate(fuente.split("\n"), 1):
            texto = cruda.split(";")[0].rstrip()
            if texto.strip():
                lineas.append((numero, texto))
        return lineas

    def _pasada(self, lineas, primera: bool) -> None:
        self.pc = self.origen
        for numero, texto in lineas:
            resto = texto
            # etiqueta al principio de la linea (sin sangrar, o con dos puntos)
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):?\s*", texto)
            if m and (texto[0] not in " \t"):
                nombre = m.group(1)
                if primera:
                    self.etiquetas[nombre] = self.pc
                resto = texto[m.end():]
            resto = resto.strip()
            if resto:
                self._instruccion(resto, numero, primera)

    def _emitir(self, palabra: int) -> None:
        self.salida.append((palabra >> 8) & 0xFF)
        self.salida.append(palabra & 0xFF)
        self.pc += 2

    def _instruccion(self, texto: str, linea: int, primera: bool) -> None:
        partes = texto.split(None, 1)
        nombre = partes[0].lower()
        args = [a.strip() for a in partes[1].split(",")] if len(partes) > 1 else []

        def pide(cuantos: int) -> None:
            if len(args) != cuantos:
                raise DspError("linea %d: '%s' lleva %d operando%s y le has dado %d"
                               % (linea, nombre, cuantos,
                                  "" if cuantos == 1 else "s", len(args)))

        # --- directivas ---
        if nombre == "org":
            pide(1)
            destino = self.valor(args[0], linea, primera)
            if destino < self.pc:
                raise DspError("linea %d: 'org' hacia atras" % linea)
            self._rellenar(destino - self.pc)
            return
        if nombre in ("ds", "reserva"):
            pide(1)
            self._rellenar(self.valor(args[0], linea, primera))
            return
        if nombre in ("dc.l", "dato"):
            for arg in args:
                v = self.valor(arg, linea, primera) & 0xFFFFFFFF
                self._emitir((v >> 16) & 0xFFFF)
                self._emitir(v & 0xFFFF)
            return
        if nombre == "dc.w":
            for arg in args:
                self._emitir(self.valor(arg, linea, primera) & 0xFFFF)
            return
        if nombre == "alinea":
            pide(1)
            cuantos = self.valor(args[0], linea, primera)
            while (self.pc - self.origen) % cuantos:
                self._emitir(0)
            return

        # --- instrucciones ---
        if nombre == "nop":
            self._emitir(_palabra(57, 0, 0))
            return
        if nombre in SOLO_RD:
            pide(1)
            self._emitir(_palabra(SOLO_RD[nombre], 0, self.registro(args[0], linea)))
            return
        if nombre in RS_RD:
            pide(2)
            self._emitir(_palabra(RS_RD[nombre], self.registro(args[0], linea),
                                  self.registro(args[1], linea)))
            return
        if nombre in Q_RD:
            pide(2)
            q = self._cero_es_32(self._inmediato(args[0], linea, primera), linea)
            self._emitir(_palabra(Q_RD[nombre], q, self.registro(args[1], linea)))
            return
        if nombre == "shlq":
            pide(2)
            q = self._inmediato(args[0], linea, primera)
            if not 1 <= q <= 32:
                raise DspError("linea %d: shlq desplaza de 1 a 32" % linea)
            # la unica instruccion que guarda 32 - n
            self._emitir(_palabra(24, (32 - q) & 0x1F, self.registro(args[1], linea)))
            return
        if nombre in BIT_RD:
            pide(2)
            b = self._inmediato(args[0], linea, primera)
            if not 0 <= b <= 31:
                raise DspError("linea %d: el bit es de 0 a 31 y es %d" % (linea, b))
            self._emitir(_palabra(BIT_RD[nombre], b, self.registro(args[1], linea)))
            return
        if nombre == "moveq":
            pide(2)
            q = self._inmediato(args[0], linea, primera)
            if not 0 <= q <= 31:
                raise DspError("linea %d: moveq va de 0 a 31 (usa movei)" % linea)
            self._emitir(_palabra(35, q, self.registro(args[1], linea)))
            return
        if nombre == "cmpq":
            pide(2)
            q = self._inmediato(args[0], linea, primera)
            if not -16 <= q <= 15:
                raise DspError("linea %d: cmpq va de -16 a 15" % linea)
            self._emitir(_palabra(31, q & 0x1F, self.registro(args[1], linea)))
            return
        if nombre == "movei":
            pide(2)
            v = self._inmediato(args[0], linea, primera) & 0xFFFFFFFF
            self._emitir(_palabra(38, 0, self.registro(args[1], linea)))
            self._emitir(v & 0xFFFF)            # la palabra baja va primero
            self._emitir((v >> 16) & 0xFFFF)
            return
        if nombre == "load":
            pide(2)
            self._emitir(_palabra(41, self._indirecto(args[0], linea),
                                  self.registro(args[1], linea)))
            return
        if nombre in ("loadb", "loadw"):
            pide(2)
            self._emitir(_palabra(39 if nombre == "loadb" else 40,
                                  self._indirecto(args[0], linea),
                                  self.registro(args[1], linea)))
            return
        if nombre in ("store", "storeb", "storew"):
            pide(2)
            codigo = {"storeb": 45, "storew": 46, "store": 47}[nombre]
            self._emitir(_palabra(codigo, self._indirecto(args[1], linea),
                                  self.registro(args[0], linea)))
            return
        if nombre == "jump":
            pide(2)
            cc = self._condicion(args[0], linea)
            self._emitir(_palabra(52, self._indirecto(args[1], linea), cc))
            return
        if nombre == "jr":
            pide(2)
            cc = self._condicion(args[0], linea)
            destino = self.valor(args[1], linea, primera)
            # el salto es relativo a la instruccion de detras, en palabras
            salto = (destino - (self.pc + 2)) // 2
            if not primera and not -16 <= salto <= 15:
                raise DspError("linea %d: el salto es de %d palabras y solo "
                               "caben de -16 a 15; usa movei y jump" % (linea, salto))
            self._emitir(_palabra(53, salto & 0x1F, cc))
            return
        raise DspError("linea %d: no conozco la instruccion '%s'" % (linea, nombre))

    def _inmediato(self, texto: str, linea: int, primera: bool) -> int:
        texto = texto.strip()
        if not texto.startswith("#"):
            raise DspError("linea %d: se esperaba un inmediato (#n) y hay '%s'"
                           % (linea, texto))
        return self.valor(texto[1:], linea, primera)

    def _condicion(self, texto: str, linea: int) -> int:
        clave = texto.strip().lower()
        if clave not in CONDICIONES:
            raise DspError("linea %d: no conozco la condicion '%s' (%s)"
                           % (linea, texto, ", ".join(sorted(CONDICIONES))))
        return CONDICIONES[clave]

    def _rellenar(self, cuantos: int) -> None:
        if cuantos < 0:
            raise DspError("no se puede rellenar %d bytes" % cuantos)
        for _ in range(cuantos):
            self.salida.append(0)
        self.pc += cuantos


def ensamblar(fuente: str, origen: int = RAM_DSP) -> Tuple[bytes, Dict[str, int]]:
    asm = Ensamblador(origen)
    codigo = asm.ensamblar(fuente)
    if origen + len(codigo) > RAM_DSP_FIN:
        raise DspError("el programa del DSP ocupa %d bytes y su RAM son 8 KB"
                       % len(codigo))
    return codigo, asm.etiquetas
