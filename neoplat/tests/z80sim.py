"""Emulador de Z80 con lo justo para ejecutar el driver de sonido de NeoPlat.

No pretende ser un Z80 completo: implementa las instrucciones que genera
tools/ngplat/m1.py y **falla ruidosamente** ante cualquier otra, para que
nunca se cuele una instruccion sin probar.

Sirve para comprobar que el driver hace lo que debe: recibe un comando del
68000 y escribe en el YM2610 los periodos y volumenes de la secuencia.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

FLAG_S = 0x80
FLAG_Z = 0x40
FLAG_H = 0x10
FLAG_PV = 0x04
FLAG_N = 0x02
FLAG_C = 0x01


class Z80Error(Exception):
    pass


class Z80:
    def __init__(self, memoria: bytes, ram_desde: int = 0xF800,
                 leer_puerto: Optional[Callable[[int], int]] = None,
                 escribir_puerto: Optional[Callable[[int, int], None]] = None):
        self.rom = bytearray(memoria)
        self.ram_desde = ram_desde
        self.ram = bytearray(0x10000 - ram_desde)
        self.a = self.f = 0
        self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.sp = 0xFFFE
        self.pc = 0
        self.iff = True
        self.nmi_pendiente = False
        self.ciclos = 0
        self.leer_puerto = leer_puerto or (lambda p: 0)
        self.escribir_puerto = escribir_puerto or (lambda p, v: None)

    # ----------------------------------------------------------- memoria
    def leer(self, direccion: int) -> int:
        direccion &= 0xFFFF
        if direccion >= self.ram_desde:
            return self.ram[direccion - self.ram_desde]
        if direccion < len(self.rom):
            return self.rom[direccion]
        return 0

    def escribir(self, direccion: int, valor: int) -> None:
        direccion &= 0xFFFF
        if direccion >= self.ram_desde:
            self.ram[direccion - self.ram_desde] = valor & 0xFF
        # escribir en la ROM no hace nada, como en la consola

    def leer16(self, direccion: int) -> int:
        return self.leer(direccion) | (self.leer(direccion + 1) << 8)

    def escribir16(self, direccion: int, valor: int) -> None:
        self.escribir(direccion, valor & 0xFF)
        self.escribir(direccion + 1, (valor >> 8) & 0xFF)

    # --------------------------------------------------------- registros
    @property
    def hl(self) -> int:
        return (self.h << 8) | self.l

    @hl.setter
    def hl(self, valor: int) -> None:
        self.h, self.l = (valor >> 8) & 0xFF, valor & 0xFF

    @property
    def de(self) -> int:
        return (self.d << 8) | self.e

    @de.setter
    def de(self, valor: int) -> None:
        self.d, self.e = (valor >> 8) & 0xFF, valor & 0xFF

    @property
    def bc(self) -> int:
        return (self.b << 8) | self.c

    @bc.setter
    def bc(self, valor: int) -> None:
        self.b, self.c = (valor >> 8) & 0xFF, valor & 0xFF

    def _reg(self, codigo: int) -> int:
        return [self.b, self.c, self.d, self.e, self.h, self.l,
                self.leer(self.hl), self.a][codigo]

    def _set_reg(self, codigo: int, valor: int) -> None:
        valor &= 0xFF
        if codigo == 0: self.b = valor
        elif codigo == 1: self.c = valor
        elif codigo == 2: self.d = valor
        elif codigo == 3: self.e = valor
        elif codigo == 4: self.h = valor
        elif codigo == 5: self.l = valor
        elif codigo == 6: self.escribir(self.hl, valor)
        else: self.a = valor

    # ------------------------------------------------------------ flags
    def _flags_logicos(self, valor: int, carry: int = 0) -> None:
        self.f = 0
        if valor & 0x80: self.f |= FLAG_S
        if (valor & 0xFF) == 0: self.f |= FLAG_Z
        if carry: self.f |= FLAG_C

    def _flags_suma(self, resultado: int) -> None:
        self.f = 0
        if resultado & 0x80: self.f |= FLAG_S
        if (resultado & 0xFF) == 0: self.f |= FLAG_Z
        if resultado > 0xFF: self.f |= FLAG_C

    def _flags_resta(self, izquierda: int, derecha: int) -> int:
        resultado = (izquierda - derecha) & 0xFF
        self.f = FLAG_N
        if resultado & 0x80: self.f |= FLAG_S
        if resultado == 0: self.f |= FLAG_Z
        if derecha > izquierda: self.f |= FLAG_C
        return resultado

    def _cond(self, codigo: int) -> bool:
        return [not (self.f & FLAG_Z), bool(self.f & FLAG_Z),
                not (self.f & FLAG_C), bool(self.f & FLAG_C),
                not (self.f & FLAG_PV), bool(self.f & FLAG_PV),
                not (self.f & FLAG_S), bool(self.f & FLAG_S)][codigo]

    # ------------------------------------------------------------ pila
    def push(self, valor: int) -> None:
        self.sp = (self.sp - 2) & 0xFFFF
        self.escribir16(self.sp, valor)

    def pop(self) -> int:
        valor = self.leer16(self.sp)
        self.sp = (self.sp + 2) & 0xFFFF
        return valor

    def nmi(self) -> None:
        """El 68000 ha escrito en el puerto de sonido."""
        self.push(self.pc)
        self.pc = 0x0066

    # ------------------------------------------------------- ejecucion
    def siguiente_byte(self) -> int:
        valor = self.leer(self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return valor

    def siguiente_word(self) -> int:
        bajo = self.siguiente_byte()
        return bajo | (self.siguiente_byte() << 8)

    def paso(self) -> None:
        if self.nmi_pendiente:
            self.nmi_pendiente = False
            self.nmi()
        opcode = self.siguiente_byte()
        self.ciclos += 1
        pc_instruccion = (self.pc - 1) & 0xFFFF

        # ld r,r' / halt
        if 0x40 <= opcode <= 0x7F:
            if opcode == 0x76:
                raise Z80Error("halt en $%04x" % pc_instruccion)
            destino = (opcode >> 3) & 7
            origen = opcode & 7
            self._set_reg(destino, self._reg(origen))
            return
        # aritmetica con registro
        if 0x80 <= opcode <= 0xBF:
            self._alu((opcode >> 3) & 7, self._reg(opcode & 7))
            return

        manejador = getattr(self, "_op_%02x" % opcode, None)
        if manejador is None:
            raise Z80Error("opcode $%02x sin implementar en $%04x (el driver no "
                           "deberia usarlo)" % (opcode, pc_instruccion))
        manejador()

    def _alu(self, operacion: int, valor: int) -> None:
        if operacion == 0:      # add
            resultado = self.a + valor
            self._flags_suma(resultado)
            self.a = resultado & 0xFF
        elif operacion == 1:    # adc
            resultado = self.a + valor + (1 if self.f & FLAG_C else 0)
            self._flags_suma(resultado)
            self.a = resultado & 0xFF
        elif operacion == 2:    # sub
            self.a = self._flags_resta(self.a, valor)
        elif operacion == 3:    # sbc
            self.a = self._flags_resta(self.a, valor + (1 if self.f & FLAG_C else 0))
        elif operacion == 4:    # and
            self.a &= valor
            self._flags_logicos(self.a)
            self.f |= FLAG_H
        elif operacion == 5:    # xor
            self.a ^= valor
            self._flags_logicos(self.a)
        elif operacion == 6:    # or
            self.a |= valor
            self._flags_logicos(self.a)
        else:                   # cp
            self._flags_resta(self.a, valor)

    # --- instrucciones sueltas ------------------------------------------
    def _op_00(self): pass                                   # nop
    def _op_f3(self): self.iff = False                       # di
    def _op_fb(self): self.iff = True                        # ei
    def _op_c3(self): self.pc = self.siguiente_word()        # jp nn
    def _op_c9(self): self.pc = self.pop()                   # ret
    def _op_cd(self):                                        # call nn
        destino = self.siguiente_word()
        self.push(self.pc)
        self.pc = destino
    def _op_18(self):                                        # jr d
        salto = self.siguiente_byte()
        self.pc = (self.pc + (salto - 256 if salto > 127 else salto)) & 0xFFFF
    def _op_10(self):                                        # djnz
        salto = self.siguiente_byte()
        self.b = (self.b - 1) & 0xFF
        if self.b:
            self.pc = (self.pc + (salto - 256 if salto > 127 else salto)) & 0xFFFF
    def _op_eb(self):                                        # ex de,hl
        self.de, self.hl = self.hl, self.de
    def _op_f9(self): self.sp = self.hl                      # ld sp,hl
    def _op_31(self): self.sp = self.siguiente_word()        # ld sp,nn
    def _op_2f(self):                                        # cpl
        self.a ^= 0xFF
    def _op_e9(self): self.pc = self.hl                      # jp (hl)

    def _salto_cond(self, codigo: int, relativo: bool) -> None:
        if relativo:
            salto = self.siguiente_byte()
            if self._cond(codigo):
                self.pc = (self.pc + (salto - 256 if salto > 127 else salto)) & 0xFFFF
        else:
            destino = self.siguiente_word()
            if self._cond(codigo):
                self.pc = destino


def _añadir_opcodes() -> None:
    """Genera los manejadores repetitivos (saltos, ld r,n, inc/dec, etc.)."""
    def hacer_ld_rn(codigo):
        def manejador(self):
            self._set_reg(codigo, self.siguiente_byte())
        return manejador

    def hacer_inc(codigo):
        def manejador(self):
            valor = (self._reg(codigo) + 1) & 0xFF
            self._set_reg(codigo, valor)
            carry = self.f & FLAG_C
            self._flags_logicos(valor, carry)
        return manejador

    def hacer_dec(codigo):
        def manejador(self):
            valor = (self._reg(codigo) - 1) & 0xFF
            self._set_reg(codigo, valor)
            carry = self.f & FLAG_C
            self._flags_logicos(valor, carry)
            self.f |= FLAG_N
        return manejador

    def hacer_jr(codigo):
        def manejador(self):
            self._salto_cond(codigo, True)
        return manejador

    def hacer_jp(codigo):
        def manejador(self):
            self._salto_cond(codigo, False)
        return manejador

    def hacer_call(codigo):
        def manejador(self):
            destino = self.siguiente_word()
            if self._cond(codigo):
                self.push(self.pc)
                self.pc = destino
        return manejador

    def hacer_ret(codigo):
        def manejador(self):
            if self._cond(codigo):
                self.pc = self.pop()
        return manejador

    def hacer_alu_inmediato(operacion):
        def manejador(self):
            self._alu(operacion, self.siguiente_byte())
        return manejador

    def hacer_ld_rr(par):
        def manejador(self):
            valor = self.siguiente_word()
            if par == 0: self.bc = valor
            elif par == 1: self.de = valor
            elif par == 2: self.hl = valor
            else: self.sp = valor
        return manejador

    def hacer_inc_rr(par, delta):
        def manejador(self):
            if par == 0: self.bc = (self.bc + delta) & 0xFFFF
            elif par == 1: self.de = (self.de + delta) & 0xFFFF
            elif par == 2: self.hl = (self.hl + delta) & 0xFFFF
            else: self.sp = (self.sp + delta) & 0xFFFF
        return manejador

    def hacer_add_hl(par):
        def manejador(self):
            otro = [self.bc, self.de, self.hl, self.sp][par]
            total = self.hl + otro
            self.hl = total & 0xFFFF
            self.f = (self.f & ~(FLAG_C | FLAG_N)) | (FLAG_C if total > 0xFFFF else 0)
        return manejador

    def hacer_push(par):
        def manejador(self):
            valor = [self.bc, self.de, self.hl, (self.a << 8) | self.f][par]
            self.push(valor)
        return manejador

    def hacer_pop(par):
        def manejador(self):
            valor = self.pop()
            if par == 0: self.bc = valor
            elif par == 1: self.de = valor
            elif par == 2: self.hl = valor
            else:
                self.a, self.f = (valor >> 8) & 0xFF, valor & 0xFF
        return manejador

    for codigo in range(8):
        setattr(Z80, "_op_%02x" % (0x06 | (codigo << 3)), hacer_ld_rn(codigo))
        setattr(Z80, "_op_%02x" % (0x04 | (codigo << 3)), hacer_inc(codigo))
        setattr(Z80, "_op_%02x" % (0x05 | (codigo << 3)), hacer_dec(codigo))
        setattr(Z80, "_op_%02x" % (0xC2 | (codigo << 3)), hacer_jp(codigo))
        setattr(Z80, "_op_%02x" % (0xC4 | (codigo << 3)), hacer_call(codigo))
        setattr(Z80, "_op_%02x" % (0xC0 | (codigo << 3)), hacer_ret(codigo))
        setattr(Z80, "_op_%02x" % (0xC6 | (codigo << 3)), hacer_alu_inmediato(codigo))
    for codigo, opcode in ((0, 0x20), (1, 0x28), (2, 0x30), (3, 0x38)):
        setattr(Z80, "_op_%02x" % opcode, hacer_jr(codigo))
    for par in range(4):
        setattr(Z80, "_op_%02x" % (0x01 | (par << 4)), hacer_ld_rr(par))
        setattr(Z80, "_op_%02x" % (0x03 | (par << 4)), hacer_inc_rr(par, 1))
        setattr(Z80, "_op_%02x" % (0x0B | (par << 4)), hacer_inc_rr(par, -1))
        setattr(Z80, "_op_%02x" % (0x09 | (par << 4)), hacer_add_hl(par))
        setattr(Z80, "_op_%02x" % (0xC5 | (par << 4)), hacer_push(par))
        setattr(Z80, "_op_%02x" % (0xC1 | (par << 4)), hacer_pop(par))


_añadir_opcodes()


def _op_32(self):                                   # ld (nn),a
    self.escribir(self.siguiente_word(), self.a)


def _op_3a(self):                                   # ld a,(nn)
    self.a = self.leer(self.siguiente_word())


def _op_22(self):                                   # ld (nn),hl
    self.escribir16(self.siguiente_word(), self.hl)


def _op_2a(self):                                   # ld hl,(nn)
    self.hl = self.leer16(self.siguiente_word())


def _op_02(self): self.escribir(self.bc, self.a)    # ld (bc),a
def _op_12(self): self.escribir(self.de, self.a)    # ld (de),a
def _op_0a(self): self.a = self.leer(self.bc)       # ld a,(bc)
def _op_1a(self): self.a = self.leer(self.de)       # ld a,(de)


def _op_d3(self):                                   # out (n),a
    self.escribir_puerto(self.siguiente_byte(), self.a)


def _op_db(self):                                   # in a,(n)
    self.a = self.leer_puerto(self.siguiente_byte()) & 0xFF


def _op_ed(self):                                   # prefijo ED
    segundo = self.siguiente_byte()
    if segundo in (0x45, 0x4D):                     # retn / reti
        self.pc = self.pop()
        return
    if segundo == 0x56 or segundo == 0x46 or segundo == 0x5E:   # im 0/1/2
        return
    if segundo == 0x44:                             # neg
        self.a = self._flags_resta(0, self.a)
        return
    if (segundo & 0xCF) == 0x43:                    # ld (nn),rr
        par = (segundo >> 4) & 3
        valor = [self.bc, self.de, self.hl, self.sp][par]
        self.escribir16(self.siguiente_word(), valor)
        return
    if (segundo & 0xCF) == 0x4B:                    # ld rr,(nn)
        par = (segundo >> 4) & 3
        valor = self.leer16(self.siguiente_word())
        if par == 0: self.bc = valor
        elif par == 1: self.de = valor
        elif par == 2: self.hl = valor
        else: self.sp = valor
        return
    raise Z80Error("prefijo ED $%02x sin implementar" % segundo)


def _op_cb(self):                                   # prefijo CB
    segundo = self.siguiente_byte()
    operacion = (segundo >> 3) & 7
    registro = segundo & 7
    valor = self._reg(registro)
    if segundo < 0x40:                              # rotaciones y desplazamientos
        if operacion == 7:                          # srl
            carry = valor & 1
            valor >>= 1
        elif operacion == 4:                        # sla
            carry = (valor >> 7) & 1
            valor = (valor << 1) & 0xFF
        elif operacion == 5:                        # sra
            carry = valor & 1
            valor = (valor & 0x80) | (valor >> 1)
        elif operacion == 2:                        # rl
            carry_previo = 1 if self.f & FLAG_C else 0
            carry = (valor >> 7) & 1
            valor = ((valor << 1) | carry_previo) & 0xFF
        elif operacion == 3:                        # rr
            carry_previo = 1 if self.f & FLAG_C else 0
            carry = valor & 1
            valor = (valor >> 1) | (carry_previo << 7)
        else:
            raise Z80Error("rotacion CB $%02x sin implementar" % segundo)
        self._set_reg(registro, valor)
        self._flags_logicos(valor, carry)
        return
    if segundo < 0x80:                              # bit n,r
        bit = operacion
        self.f = (self.f & FLAG_C) | FLAG_H
        if not (valor >> bit) & 1:
            self.f |= FLAG_Z
        return
    if segundo < 0xC0:                              # res n,r
        self._set_reg(registro, valor & ~(1 << operacion))
        return
    self._set_reg(registro, valor | (1 << operacion))   # set n,r


for _nombre, _funcion in list(globals().items()):
    if _nombre.startswith("_op_"):
        setattr(Z80, _nombre, _funcion)


class YM2610Falso:
    """YM2610 de mentira: apunta lo que le escriben y simula el temporizador."""

    def __init__(self):
        self.registros: Dict[int, int] = {}
        self.escrituras: List[tuple] = []
        self.direccion = 0
        self.timer_listo = False
        self.comando = 0

    def leer(self, puerto: int) -> int:
        if puerto == 0x00:                 # comando del 68000
            return self.comando
        if puerto == 0x04:                 # estado: bit 1 = aviso del timer B
            return 0x02 if self.timer_listo else 0x00
        return 0

    def escribir(self, puerto: int, valor: int) -> None:
        if puerto == 0x04:
            self.direccion = valor
        elif puerto == 0x05:
            self.registros[self.direccion] = valor
            self.escrituras.append((self.direccion, valor))
            if self.direccion == 0x27 and (valor & 0x20):
                self.timer_listo = False     # se ha limpiado el aviso
