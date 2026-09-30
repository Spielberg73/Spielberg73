"""Núcleo Z80: decodificador, ensamblador y CPU."""
import random
import shutil
import subprocess

import pytest

from zxcpc.z80 import decode as D
from zxcpc.z80.asm import assemble, AsmError
from zxcpc.z80.cpu import Z80


def _dec(raw, addr=0):
    mem = bytearray(65536)
    mem[addr:addr + len(raw)] = raw
    return D.decode(mem, addr)


def _all_documented():
    """Una instancia de cada instrucción documentada (bytes, texto)."""
    seen = {}
    for pre in ([], [0xCB], [0xED], [0xDD], [0xFD], [0xDD, 0xCB, 5], [0xFD, 0xCB, 0xFB]):
        for op in range(256):
            raw = bytes(pre + [op, 0x34, 0x12, 0x00])
            ins = _dec(raw, 0x8000)
            if ins.undocumented or ins.op in ("DB", "NOP?"):
                continue
            seen.setdefault(ins.text(), bytes(raw[:ins.length]))
    return seen


def test_decode_basico():
    cases = {
        b"\x00": "NOP", b"\x3E\x05": "LD A,$05", b"\x21\x34\x12": "LD HL,$1234",
        b"\xDD\x77\x03": "LD (IX+$03),A", b"\xED\xB0": "LDIR", b"\xCB\x7E": "BIT 7,(HL)",
        b"\xFD\xCB\xFE\xC6": "SET 0,(IY-$02)", b"\xC9": "RET",
    }
    for raw, text in cases.items():
        ins = _dec(raw + b"\x00\x00\x00")
        assert ins.text() == text
        assert ins.length == len(raw)


def test_decode_saltos_relativos():
    ins = _dec(b"\x18\xFE", 0x8000)
    assert ins.target == 0x8000
    ins = _dec(b"\x10\x02", 0x8000)
    assert ins.target == 0x8004


def test_asm_ida_y_vuelta():
    """Ensamblar el texto de cada instrucción documentada da los mismos bytes."""
    table = _all_documented()
    assert len(table) > 600
    for text, raw in table.items():
        out = assemble(f"        org $8000\n        {text}\n").image()
        assert out == raw, text


def test_asm_directivas():
    src = """
        org $9000
N       equ 3
start:  ld b,N
.l:     djnz .l
        rept 2
        nop
        endr
        if N > 2
        db 1,2,"AB"
        else
        db 9
        endif
        dw start
        ds 2, $FF
        align 4
fin:    assert fin % 4 == 0
"""
    r = assemble(src)
    img = r.image()
    assert img[:4] == bytes([0x06, 3, 0x10, 0xFE])
    assert img[4:6] == b"\x00\x00"
    assert img[6:10] == b"\x01\x02AB"
    assert img[10:12] == b"\x00\x90"
    assert img[12:14] == b"\xFF\xFF"
    assert r.symbols["fin"] % 4 == 0
    assert r.symbols["start.l"] == 0x9002


def test_asm_errores():
    with pytest.raises(AsmError):
        assemble("        ld a,(bc,de)\n")
    with pytest.raises(AsmError):
        assemble("        jr lejos\n        ds 300\nlejos:  nop\n")


@pytest.mark.skipif(not shutil.which("pasmo"), reason="pasmo no instalado")
def test_asm_igual_que_pasmo(tmp_path):
    table = _all_documented()
    src = "        org $8000\n" + "".join(f"        {t}\n" for t in table)
    mine = assemble(src).image()
    (tmp_path / "t.asm").write_text(src)
    subprocess.run(["pasmo", str(tmp_path / "t.asm"), str(tmp_path / "t.bin")], check=True,
                   capture_output=True)
    assert (tmp_path / "t.bin").read_bytes() == mine


def _run(code, steps=10000, **regs):
    mem = bytearray(65536)
    img = assemble("        org $8000\n" + code).image()
    mem[0x8000:0x8000 + len(img)] = img
    c = Z80(mem)
    c.pc = 0x8000
    c.set_pair("SP", 0xF000)
    for k, v in regs.items():
        c.set_pair(k, v)
    for _ in range(steps):
        if c.halted:
            break
        c.step()
    return c


def test_cpu_multiplicacion():
    c = _run("""
        ld hl,0
        ld de,123
        ld b,45
.l:     add hl,de
        djnz .l
        halt
""")
    assert c.get_pair("HL") == 123 * 45


def test_cpu_flags_y_pila():
    c = _run("""
        ld a,$99
        add a,$01
        daa
        push af
        pop bc
        ld a,$7F
        inc a
        halt
""")
    assert c.get_pair("BC") >> 8 == 0x00          # 99+1 = 100 en BCD -> 00 con acarreo
    assert c.get_pair("BC") & 1 == 1
    assert c.R[7] == 0x80
    assert c.R[6] & 0x04                          # desbordamiento (P/V)


def test_cpu_ldir_y_llamadas():
    c = _run("""
        ld hl,src
        ld de,$A000
        ld bc,4
        ldir
        call sub
        halt
sub:    ld a,($A003)
        ret
src:    db 1,2,3,4
""")
    assert bytes(c.mem[0xA000:0xA004]) == b"\x01\x02\x03\x04"
    assert c.R[7] == 4


def test_cpu_interrupciones_im2():
    mem = bytearray(65536)
    img = assemble("""
        org $8000
        ld a,$90
        ld i,a
        im 2
        ei
.w:     jr .w
        org $9000
isr:    ld a,$55
        halt
        org $90FF
        dw isr
""").image()
    mem[0x8000:0x8000 + len(img)] = img
    c = Z80(mem)
    c.pc = 0x8000
    c.set_pair("SP", 0xF000)
    for _ in range(10):
        c.step()
    assert c.interrupt(0xFF)
    for _ in range(10):
        if c.halted:
            break
        c.step()
    assert c.R[7] == 0x55


def test_cpu_contra_referencia():
    """Compara con el emulador de referencia (paquete ``z80``) si está instalado."""
    z80 = pytest.importorskip("z80")
    rnd = random.Random(1)
    skip_flags = ("LDIR", "LDDR", "CPIR", "CPDR", "INIR", "INDR", "OTIR", "OTDR")
    base = bytes(rnd.randrange(256) for _ in range(65536))
    for _ in range(1500):
        mem = bytearray(base)
        for _ in range(8):
            mem[rnd.randrange(65536)] = rnd.randrange(256)
        pc = rnd.randrange(0x100, 0xFF00)
        for i in range(6):
            mem[pc + i] = rnd.randrange(256)
        pre = rnd.choice([b"", b"", b"\xCB", b"\xED", b"\xDD", b"\xFD", b"\xDD\xCB"])
        mem[pc:pc + len(pre)] = pre
        regs = {k: rnd.randrange(65536) for k in ("af", "bc", "de", "hl", "ix", "iy", "sp")}
        k = z80.Z80Machine()
        k.set_memory_block(0, bytes(mem))
        for n, v in regs.items():
            setattr(k, n, v)
        k.pc = pc
        k.set_input_callback(lambda p: (p * 7 + 3) & 0xFF)
        k.ticks_to_stop = 1
        k.run()
        while str(k.index_rp_kind) != "hl":
            k.ticks_to_stop = 1
            k.run()
        c = Z80(bytearray(mem))
        for n, v in regs.items():
            c.set_pair(n.upper(), v)
        c.pc = pc
        c.inp = lambda p: (p * 7 + 3) & 0xFF
        c.outp = lambda p, v: None
        c.step()
        ins = D.decode(mem, pc)
        for n in ("af", "bc", "de", "hl", "ix", "iy", "sp", "pc"):
            if n == "af" and (ins.op in skip_flags or ins.op == "BIT"):
                continue
            assert getattr(k, n) == c.get_pair(n.upper()), (ins.text(), n)
        assert bytes(k.memory) == bytes(c.mem), ins.text()
