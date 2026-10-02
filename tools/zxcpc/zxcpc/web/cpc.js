// Amstrad CPC 6128 (hasta 576K) en JavaScript para el reproductor web de zxcpc.
// Es una traducción directa de zxcpc/z80/cpu.py y zxcpc/machines/cpc.py: mismos
// tiempos, flags e interrupciones, para que los dos den exactamente el mismo
// resultado (lo comprueba tests/test_web.py). Añade el sonido del PSG.
"use strict";

const B = 0, C = 1, D = 2, E = 3, H = 4, L = 5, F = 6, A = 7;
const IXH = 8, IXL = 9, IYH = 10, IYL = 11;
const FS = 0x80, FZ = 0x40, FY = 0x20, FH = 0x10, FX = 0x08, FP = 0x04, FN = 0x02, FC = 0x01;

const SZ53 = new Uint8Array(256), SZ53P = new Uint8Array(256), PARITY = new Uint8Array(256);
for (let i = 0; i < 256; i++) {
  const v = (i & (FS | FY | FX)) | (i === 0 ? FZ : 0);
  let n = 0;
  for (let k = 0; k < 8; k++) n += (i >> k) & 1;
  const p = n % 2 === 0 ? FP : 0;
  SZ53[i] = v; SZ53P[i] = v | p; PARITY[i] = p;
}
const R8 = [B, C, D, E, H, L, -1, A];
const CC = [[FZ, 0], [FZ, FZ], [FC, 0], [FC, FC], [FP, 0], [FP, FP], [FS, 0], [FS, FS]];

function indexAffects(op) {
  const x = op >> 6, y = (op >> 3) & 7, z = op & 7, p = y >> 1, q = y & 1;
  if (op === 0xDD || op === 0xFD || op === 0xED || op === 0xCB) return true;
  if (x === 0) {
    if (z === 1) return p === 2 || q === 1;
    if (z === 2 || z === 3) return p === 2;
    if (z === 4 || z === 5 || z === 6) return y >= 4 && y <= 6;
    return false;
  }
  if (x === 1) {
    if (op === 0x76) return false;
    return (y >= 4 && y <= 6) || (z >= 4 && z <= 6);
  }
  if (x === 2) return z >= 4 && z <= 6;
  return op === 0xE1 || op === 0xE5 || op === 0xE3 || op === 0xE9 || op === 0xF9;
}
const AFFECTS = new Uint8Array(256);
for (let i = 0; i < 256; i++) AFFECTS[i] = indexAffects(i) ? 1 : 0;

class Z80 {
  constructor(bus) {
    this.bus = bus;
    this.R = new Uint8Array(12);
    this.R[A] = 0xFF; this.R[F] = 0xFF;
    this.alt = new Uint8Array(8);
    this.sp = 0xFFFF; this.pc = 0; this.i = 0; this.r = 0;
    this.iff1 = 0; this.iff2 = 0; this.im = 0;
    this.halted = false; this.wz = 0; this.eiDelay = false; this.cycles = 0;
  }
  rd(a) { return this.bus.rd(a); }
  wb(a, v) { this.bus.wr(a, v); }
  incR() { this.r = (this.r & 0x80) | ((this.r + 1) & 0x7F); }
  f8() { const v = this.rd(this.pc); this.pc = (this.pc + 1) & 0xFFFF; return v; }
  f16() {
    const pc = this.pc;
    const v = this.rd(pc) | (this.rd((pc + 1) & 0xFFFF) << 8);
    this.pc = (pc + 2) & 0xFFFF;
    return v;
  }
  fd() { const v = this.f8(); return v & 0x80 ? v - 256 : v; }
  push(v) {
    let sp = (this.sp - 1) & 0xFFFF;
    this.wb(sp, (v >> 8) & 0xFF);
    sp = (sp - 1) & 0xFFFF;
    this.wb(sp, v & 0xFF);
    this.sp = sp;
  }
  pop() {
    const sp = this.sp;
    const v = this.rd(sp) | (this.rd((sp + 1) & 0xFFFF) << 8);
    this.sp = (sp + 2) & 0xFFFF;
    return v;
  }
  getPair(n) {
    const R = this.R;
    switch (n) {
      case "AF": return R[A] << 8 | R[F];
      case "BC": return R[B] << 8 | R[C];
      case "DE": return R[D] << 8 | R[E];
      case "HL": return R[H] << 8 | R[L];
      case "IX": return R[IXH] << 8 | R[IXL];
      case "IY": return R[IYH] << 8 | R[IYL];
      case "SP": return this.sp;
      case "PC": return this.pc;
    }
  }
  setPair(n, v) {
    const R = this.R, hi = (v >> 8) & 0xFF, lo = v & 0xFF;
    switch (n) {
      case "AF": R[A] = hi; R[F] = lo; break;
      case "BC": R[B] = hi; R[C] = lo; break;
      case "DE": R[D] = hi; R[E] = lo; break;
      case "HL": R[H] = hi; R[L] = lo; break;
      case "IX": R[IXH] = hi; R[IXL] = lo; break;
      case "IY": R[IYH] = hi; R[IYL] = lo; break;
      case "SP": this.sp = v & 0xFFFF; break;
      case "PC": this.pc = v & 0xFFFF; break;
    }
  }

  step() {
    this.eiDelay = false;
    if (this.halted) { this.incR(); this.cycles += 4; return 4; }
    const op = this.rd(this.pc);
    this.pc = (this.pc + 1) & 0xFFFF;
    this.incR();
    const t = this.main(op, 0);
    this.cycles += t;
    return t;
  }
  interrupt(data) {
    if (!this.iff1 || this.eiDelay) return 0;
    if (this.halted) this.halted = false;
    this.iff1 = this.iff2 = 0;
    this.incR();
    this.push(this.pc);
    let t;
    if (this.im === 2) {
      const v = (this.i << 8) | (data & 0xFF);
      this.pc = this.rd(v) | (this.rd((v + 1) & 0xFFFF) << 8);
      t = 19;
    } else { this.pc = 0x38; t = 13; }
    this.wz = this.pc;
    this.cycles += t;
    return t;
  }

  // --- ALU ---------------------------------------------------------------------
  add(v, cy) {
    const R = this.R, a = R[A], res = a + v + cy, r8 = res & 0xFF;
    R[F] = SZ53[r8] | ((res >> 8) & 1) | ((a ^ v ^ res) & FH) |
      (((a ^ res) & (v ^ res) & 0x80) ? FP : 0);
    R[A] = r8;
  }
  sub(v, cy, store) {
    const R = this.R, a = R[A], res = a - v - cy, r8 = res & 0xFF;
    R[F] = (store ? SZ53[r8] : (SZ53[r8] & ~(FY | FX)) | (v & (FY | FX))) | FN |
      (res < 0 ? 1 : 0) | ((a ^ v ^ res) & FH) | (((a ^ v) & (a ^ res) & 0x80) ? FP : 0);
    if (store) R[A] = r8;
  }
  alu(y, v) {
    const R = this.R;
    switch (y) {
      case 0: this.add(v, 0); break;
      case 1: this.add(v, R[F] & 1); break;
      case 2: this.sub(v, 0, true); break;
      case 3: this.sub(v, R[F] & 1, true); break;
      case 4: { const r = R[A] & v; R[A] = r; R[F] = SZ53P[r] | FH; break; }
      case 5: { const r = R[A] ^ v; R[A] = r; R[F] = SZ53P[r]; break; }
      case 6: { const r = R[A] | v; R[A] = r; R[F] = SZ53P[r]; break; }
      default: this.sub(v, 0, false);
    }
  }
  inc8(v) {
    const r = (v + 1) & 0xFF;
    this.R[F] = (this.R[F] & FC) | SZ53[r] | ((v & 0xF) === 0xF ? FH : 0) | (v === 0x7F ? FP : 0);
    return r;
  }
  dec8(v) {
    const r = (v - 1) & 0xFF;
    this.R[F] = (this.R[F] & FC) | SZ53[r] | FN | ((v & 0xF) === 0 ? FH : 0) | (v === 0x80 ? FP : 0);
    return r;
  }
  rot(y, v) {
    const cy = this.R[F] & 1;
    let c, r;
    switch (y) {
      case 0: c = v >> 7; r = ((v << 1) | c) & 0xFF; break;
      case 1: c = v & 1; r = (v >> 1) | (c << 7); break;
      case 2: c = v >> 7; r = ((v << 1) | cy) & 0xFF; break;
      case 3: c = v & 1; r = (v >> 1) | (cy << 7); break;
      case 4: c = v >> 7; r = (v << 1) & 0xFF; break;
      case 5: c = v & 1; r = (v >> 1) | (v & 0x80); break;
      case 6: c = v >> 7; r = ((v << 1) | 1) & 0xFF; break;
      default: c = v & 1; r = v >> 1;
    }
    this.R[F] = SZ53P[r] | c;
    return r;
  }
  cond(c) { return (this.R[F] & CC[c][0]) === CC[c][1]; }

  // --- tabla principal (idx: 0 sin prefijo, 1 IX, 2 IY) -------------------------------
  main(op, idx) {
    if (idx && !AFFECTS[op]) return 4 + this.main(op, 0);
    const R = this.R;
    const HI = idx === 0 ? H : idx === 1 ? IXH : IYH;
    const LO = idx === 0 ? L : idx === 1 ? IXL : IYL;
    const extra = idx ? 4 : 0;
    const x = op >> 6, y = (op >> 3) & 7, z = op & 7, p = y >> 1, q = y & 1;
    const maddr = () => {
      if (!idx) return R[H] << 8 | R[L];
      const d = this.fd();
      const a = (((R[HI] << 8) | R[LO]) + d) & 0xFFFF;
      this.wz = a;
      return a;
    };
    const ri = (zz) => zz === 4 ? HI : zz === 5 ? LO : R8[zz];
    const getrp = (pp) => pp === 0 ? R[B] << 8 | R[C] : pp === 1 ? R[D] << 8 | R[E] :
      pp === 2 ? R[HI] << 8 | R[LO] : this.sp;
    const setrp = (pp, v) => {
      if (pp === 0) { R[B] = v >> 8; R[C] = v & 0xFF; }
      else if (pp === 1) { R[D] = v >> 8; R[E] = v & 0xFF; }
      else if (pp === 2) { R[HI] = v >> 8; R[LO] = v & 0xFF; }
      else this.sp = v;
    };
    if (x === 0) {
      if (z === 0) {
        if (y === 0) return 4;
        if (y === 1) {
          const al = this.alt;
          let t = R[A]; R[A] = al[A]; al[A] = t;
          t = R[F]; R[F] = al[F]; al[F] = t;
          return 4;
        }
        if (y === 2) {
          const d = this.fd();
          const b = (R[B] - 1) & 0xFF;
          R[B] = b;
          if (b) { this.pc = (this.pc + d) & 0xFFFF; this.wz = this.pc; return 13; }
          return 8;
        }
        if (y === 3) { const d = this.fd(); this.pc = (this.pc + d) & 0xFFFF; this.wz = this.pc; return 12; }
        const d = this.fd();
        if (this.cond(y - 4)) { this.pc = (this.pc + d) & 0xFFFF; this.wz = this.pc; return 12; }
        return 7;
      }
      if (z === 1) {
        if (q === 0) { setrp(p, this.f16()); return 10 + extra; }
        const hl = getrp(2), v = getrp(p), res = hl + v;
        this.wz = (hl + 1) & 0xFFFF;
        R[F] = (R[F] & (FS | FZ | FP)) | ((res >> 8) & (FY | FX)) | (((hl ^ v ^ res) >> 8) & FH) | (res >> 16);
        setrp(2, res & 0xFFFF);
        return 11 + extra;
      }
      if (z === 2) {
        if (q === 0) {
          if (p === 0 || p === 1) {
            const a = p === 0 ? R[B] << 8 | R[C] : R[D] << 8 | R[E];
            this.wb(a, R[A]);
            this.wz = (R[A] << 8) | ((a + 1) & 0xFF);
            return 7;
          }
          const a = this.f16();
          if (p === 2) {
            this.wb(a, R[LO]); this.wb((a + 1) & 0xFFFF, R[HI]);
            this.wz = (a + 1) & 0xFFFF;
            return 16 + extra;
          }
          this.wb(a, R[A]);
          this.wz = (R[A] << 8) | ((a + 1) & 0xFF);
          return 13;
        }
        if (p === 0 || p === 1) {
          const a = p === 0 ? R[B] << 8 | R[C] : R[D] << 8 | R[E];
          R[A] = this.rd(a);
          this.wz = (a + 1) & 0xFFFF;
          return 7;
        }
        const a = this.f16();
        if (p === 2) {
          R[LO] = this.rd(a); R[HI] = this.rd((a + 1) & 0xFFFF);
          this.wz = (a + 1) & 0xFFFF;
          return 16 + extra;
        }
        R[A] = this.rd(a);
        this.wz = (a + 1) & 0xFFFF;
        return 13;
      }
      if (z === 3) { setrp(p, (getrp(p) + (q === 0 ? 1 : -1)) & 0xFFFF); return 6 + extra; }
      if (z === 4 || z === 5) {
        if (y === 6) {
          const a = maddr();
          const v = this.rd(a);
          this.wb(a, z === 4 ? this.inc8(v) : this.dec8(v));
          return idx ? 23 : 11;
        }
        const k = ri(y);
        R[k] = z === 4 ? this.inc8(R[k]) : this.dec8(R[k]);
        return 4 + extra;
      }
      if (z === 6) {
        if (y === 6) { const a = maddr(); this.wb(a, this.f8()); return idx ? 19 : 10; }
        R[ri(y)] = this.f8();
        return 7 + extra;
      }
      // z === 7: operaciones con el acumulador
      const a0 = R[A], f0 = R[F];
      switch (y) {
        case 0: { const c = a0 >> 7, a = ((a0 << 1) | c) & 0xFF; R[A] = a; R[F] = (f0 & (FS | FZ | FP)) | (a & (FY | FX)) | c; break; }
        case 1: { const c = a0 & 1, a = (a0 >> 1) | (c << 7); R[A] = a; R[F] = (f0 & (FS | FZ | FP)) | (a & (FY | FX)) | c; break; }
        case 2: { const c = a0 >> 7, a = ((a0 << 1) | (f0 & 1)) & 0xFF; R[A] = a; R[F] = (f0 & (FS | FZ | FP)) | (a & (FY | FX)) | c; break; }
        case 3: { const c = a0 & 1, a = (a0 >> 1) | ((f0 & 1) << 7); R[A] = a; R[F] = (f0 & (FS | FZ | FP)) | (a & (FY | FX)) | c; break; }
        case 4: {
          let corr = 0, carry = f0 & FC;
          if ((f0 & FH) || (a0 & 0x0F) > 9) corr = 6;
          if (carry || a0 > 0x99) { corr |= 0x60; carry = FC; }
          let h, r;
          if (f0 & FN) { h = ((f0 & FH) && (a0 & 0x0F) < 6) ? FH : 0; r = (a0 - corr) & 0xFF; }
          else { h = (a0 & 0x0F) > 9 ? FH : 0; r = (a0 + corr) & 0xFF; }
          R[A] = r; R[F] = SZ53P[r] | h | (f0 & FN) | carry;
          break;
        }
        case 5: { const a = a0 ^ 0xFF; R[A] = a; R[F] = (f0 & (FS | FZ | FP | FC)) | FH | FN | (a & (FY | FX)); break; }
        case 6: R[F] = (f0 & (FS | FZ | FP)) | FC | (a0 & (FY | FX)); break;
        default: R[F] = ((f0 & (FS | FZ | FP)) | ((f0 & FC) << 4) | (a0 & (FY | FX))) | ((f0 & FC) ^ FC);
      }
      return 4;
    }
    if (x === 1) {
      if (op === 0x76) { this.halted = true; return 4; }
      if (y === 6) { const a = maddr(); this.wb(a, R[R8[z]]); return idx ? 19 : 7; }
      if (z === 6) { R[R8[y]] = this.rd(maddr()); return idx ? 19 : 7; }
      R[ri(y)] = R[ri(z)];
      return 4 + extra;
    }
    if (x === 2) {
      if (z === 6) { this.alu(y, this.rd(maddr())); return idx ? 19 : 7; }
      this.alu(y, R[ri(z)]);
      return 4 + extra;
    }
    // x === 3
    switch (z) {
      case 0:
        if (this.cond(y)) { this.pc = this.pop(); this.wz = this.pc; return 11; }
        return 5;
      case 1:
        if (q === 0) {
          if (p === 3) { const v = this.pop(); R[A] = v >> 8; R[F] = v & 0xFF; return 10; }
          setrp(p, this.pop());
          return 10 + extra;
        }
        if (p === 0) { this.pc = this.pop(); this.wz = this.pc; return 10; }
        if (p === 1) {
          const al = this.alt;
          for (const k of [B, C, D, E, H, L]) { const t = R[k]; R[k] = al[k]; al[k] = t; }
          return 4;
        }
        if (p === 2) { this.pc = R[HI] << 8 | R[LO]; return 4 + extra; }
        this.sp = R[HI] << 8 | R[LO];
        return 6 + extra;
      case 2: {
        const t = this.f16();
        this.wz = t;
        if (this.cond(y)) this.pc = t;
        return 10;
      }
      case 3:
        switch (y) {
          case 0: this.pc = this.f16(); this.wz = this.pc; return 10;
          case 1: {
            if (!idx) {
              const o = this.f8();
              this.incR();
              return this.cb(o);
            }
            const pc = this.pc;
            let d = this.rd(pc);
            const o = this.rd((pc + 1) & 0xFFFF);
            this.pc = (pc + 2) & 0xFFFF;
            if (d & 0x80) d -= 256;
            const a = (((R[HI] << 8) | R[LO]) + d) & 0xFFFF;
            this.wz = a;
            return this.xcb(o, a);
          }
          case 2: {
            const n = this.f8(), a = R[A];
            this.bus.out((a << 8) | n, a);
            this.wz = (a << 8) | ((n + 1) & 0xFF);
            return 11;
          }
          case 3: {
            const n = this.f8(), port = (R[A] << 8) | n;
            this.wz = (port + 1) & 0xFFFF;
            R[A] = this.bus.inp(port) & 0xFF;
            return 11;
          }
          case 4: {
            const sp = this.sp;
            const v = this.rd(sp) | (this.rd((sp + 1) & 0xFFFF) << 8);
            this.wb(sp, R[LO]); this.wb((sp + 1) & 0xFFFF, R[HI]);
            R[HI] = v >> 8; R[LO] = v & 0xFF;
            this.wz = v;
            return 19 + extra;
          }
          case 5: {
            let t = R[D]; R[D] = R[H]; R[H] = t;
            t = R[E]; R[E] = R[L]; R[L] = t;
            return 4;
          }
          case 6: this.iff1 = this.iff2 = 0; return 4;
          default: this.iff1 = this.iff2 = 1; this.eiDelay = true; return 4;
        }
      case 4: {
        const t = this.f16();
        this.wz = t;
        if (this.cond(y)) { this.push(this.pc); this.pc = t; return 17; }
        return 10;
      }
      case 5:
        if (q === 0) {
          if (p === 3) { this.push(R[A] << 8 | R[F]); return 11; }
          this.push(getrp(p));
          return 11 + extra;
        }
        if (p === 0) { const t = this.f16(); this.push(this.pc); this.pc = t; this.wz = t; return 17; }
        {
          const o = this.f8();
          this.incR();
          if (p === 1) return this.main(o, 1);
          if (p === 2) return this.ed(o);
          return this.main(o, 2);
        }
      case 6: this.alu(y, this.f8()); return 7;
      default: this.push(this.pc); this.pc = y * 8; this.wz = this.pc; return 11;
    }
  }

  cb(op) {
    const R = this.R, x = op >> 6, y = (op >> 3) & 7, z = op & 7, k = R8[z];
    if (x === 0) {
      if (z === 6) { const a = R[H] << 8 | R[L]; this.wb(a, this.rot(y, this.rd(a))); return 15; }
      R[k] = this.rot(y, R[k]);
      return 8;
    }
    if (x === 1) {
      const bit = 1 << y;
      let v, f;
      if (z === 6) { v = this.rd(R[H] << 8 | R[L]); f = (R[F] & FC) | FH | ((this.wz >> 8) & (FY | FX)); }
      else { v = R[k]; f = (R[F] & FC) | FH | (v & (FY | FX)); }
      const res = v & bit;
      if (!res) f |= FZ | FP;
      if (y === 7 && res) f |= FS;
      R[F] = f;
      return z === 6 ? 12 : 8;
    }
    const mask = x === 2 ? (~(1 << y)) & 0xFF : 0xFF, orv = x === 2 ? 0 : 1 << y;
    if (z === 6) { const a = R[H] << 8 | R[L]; this.wb(a, (this.rd(a) & mask) | orv); return 15; }
    R[k] = (R[k] & mask) | orv;
    return 8;
  }

  xcb(op, a) {
    const R = this.R, x = op >> 6, y = (op >> 3) & 7, z = op & 7, k = R8[z];
    if (x === 0) {
      const v = this.rot(y, this.rd(a));
      this.wb(a, v);
      if (k >= 0) R[k] = v;
      return 23;
    }
    if (x === 1) {
      const v = this.rd(a), res = v & (1 << y);
      let f = (R[F] & FC) | FH | ((a >> 8) & (FY | FX));
      if (!res) f |= FZ | FP;
      if (y === 7 && res) f |= FS;
      R[F] = f;
      return 20;
    }
    const mask = x === 2 ? (~(1 << y)) & 0xFF : 0xFF, orv = x === 2 ? 0 : 1 << y;
    const v = (this.rd(a) & mask) | orv;
    this.wb(a, v);
    if (k >= 0) R[k] = v;
    return 23;
  }

  ed(op) {
    const R = this.R, x = op >> 6, y = (op >> 3) & 7, z = op & 7, p = y >> 1, q = y & 1;
    const getrp = (pp) => pp === 0 ? R[B] << 8 | R[C] : pp === 1 ? R[D] << 8 | R[E] :
      pp === 2 ? R[H] << 8 | R[L] : this.sp;
    const setrp = (pp, v) => {
      if (pp === 0) { R[B] = v >> 8; R[C] = v & 0xFF; }
      else if (pp === 1) { R[D] = v >> 8; R[E] = v & 0xFF; }
      else if (pp === 2) { R[H] = v >> 8; R[L] = v & 0xFF; }
      else this.sp = v;
    };
    if (x === 1) {
      switch (z) {
        case 0: {
          const bc = R[B] << 8 | R[C], v = this.bus.inp(bc) & 0xFF;
          this.wz = (bc + 1) & 0xFFFF;
          R[F] = (R[F] & FC) | SZ53P[v];
          if (R8[y] >= 0) R[R8[y]] = v;
          return 12;
        }
        case 1: {
          const bc = R[B] << 8 | R[C];
          this.bus.out(bc, R8[y] >= 0 ? R[R8[y]] : 0);
          this.wz = (bc + 1) & 0xFFFF;
          return 12;
        }
        case 2: {
          const hl = R[H] << 8 | R[L], v = getrp(p);
          let res, r16;
          if (q === 0) {
            res = hl - v - (R[F] & 1);
            r16 = res & 0xFFFF;
            R[F] = ((r16 >> 8) & (FS | FY | FX)) | (r16 === 0 ? FZ : 0) | FN | (res < 0 ? 1 : 0) |
              (((hl ^ v ^ res) >> 8) & FH) | (((hl ^ v) & (hl ^ res) & 0x8000) ? FP : 0);
          } else {
            res = hl + v + (R[F] & 1);
            r16 = res & 0xFFFF;
            R[F] = ((r16 >> 8) & (FS | FY | FX)) | (r16 === 0 ? FZ : 0) | (res >> 16) |
              (((hl ^ v ^ res) >> 8) & FH) | (((hl ^ res) & (v ^ res) & 0x8000) ? FP : 0);
          }
          this.wz = (hl + 1) & 0xFFFF;
          R[H] = r16 >> 8; R[L] = r16 & 0xFF;
          return 15;
        }
        case 3: {
          const a = this.f16();
          if (q === 0) {
            const v = getrp(p);
            this.wb(a, v & 0xFF); this.wb((a + 1) & 0xFFFF, v >> 8);
          } else setrp(p, this.rd(a) | (this.rd((a + 1) & 0xFFFF) << 8));
          this.wz = (a + 1) & 0xFFFF;
          return 20;
        }
        case 4: {
          const a = R[A], res = -a, r8 = res & 0xFF;
          R[F] = SZ53[r8] | FN | (a ? 1 : 0) | ((a ^ res) & FH) | (a === 0x80 ? FP : 0);
          R[A] = r8;
          return 8;
        }
        case 5: this.pc = this.pop(); this.wz = this.pc; this.iff1 = this.iff2; return 14;
        case 6: this.im = [0, 0, 1, 2, 0, 0, 1, 2][y]; return 8;
        default:
          switch (y) {
            case 0: this.i = R[A]; return 9;
            case 1: this.r = R[A]; return 9;
            case 2: { const v = this.i; R[A] = v; R[F] = (R[F] & FC) | SZ53[v] | (this.iff2 ? FP : 0); return 9; }
            case 3: { const v = this.r & 0xFF; R[A] = v; R[F] = (R[F] & FC) | SZ53[v] | (this.iff2 ? FP : 0); return 9; }
            case 4: {
              const hl = R[H] << 8 | R[L], m = this.rd(hl);
              let a = R[A];
              this.wb(hl, ((a << 4) | (m >> 4)) & 0xFF);
              a = (a & 0xF0) | (m & 0x0F);
              R[A] = a; R[F] = (R[F] & FC) | SZ53P[a];
              this.wz = (hl + 1) & 0xFFFF;
              return 18;
            }
            case 5: {
              const hl = R[H] << 8 | R[L], m = this.rd(hl);
              let a = R[A];
              this.wb(hl, ((m << 4) | (a & 0x0F)) & 0xFF);
              a = (a & 0xF0) | (m >> 4);
              R[A] = a; R[F] = (R[F] & FC) | SZ53P[a];
              this.wz = (hl + 1) & 0xFFFF;
              return 18;
            }
            default: return 8;
          }
      }
    }
    if (x === 2 && z <= 3 && y >= 4) return this.block(y, z);
    return 8;
  }

  block(y, z) {
    const R = this.R, inc = (y === 4 || y === 6) ? 1 : -1, repeat = y >= 6;
    const hlAdd = () => { const v = ((R[H] << 8 | R[L]) + inc) & 0xFFFF; R[H] = v >> 8; R[L] = v & 0xFF; };
    if (z === 0) {
      let hl = R[H] << 8 | R[L], de = R[D] << 8 | R[E];
      const v = this.rd(hl);
      this.wb(de, v);
      hl = (hl + inc) & 0xFFFF; de = (de + inc) & 0xFFFF;
      const bc = ((R[B] << 8 | R[C]) - 1) & 0xFFFF;
      R[H] = hl >> 8; R[L] = hl & 0xFF; R[D] = de >> 8; R[E] = de & 0xFF; R[B] = bc >> 8; R[C] = bc & 0xFF;
      const n = (v + R[A]) & 0xFF;
      const f = (R[F] & (FS | FZ | FC)) | (bc ? FP : 0) | (n & FX) | ((n << 4) & FY);
      if (repeat && bc) {
        const pc = (this.pc - 2) & 0xFFFF;
        this.pc = pc; this.wz = (pc + 1) & 0xFFFF;
        R[F] = (f & ~(FY | FX)) | ((pc >> 8) & (FY | FX));
        return 21;
      }
      R[F] = f;
      return 16;
    }
    if (z === 1) {
      const hl = R[H] << 8 | R[L], v = this.rd(hl), a = R[A];
      const res = (a - v) & 0xFF, hflag = (a ^ v ^ res) & FH;
      hlAdd();
      const bc = ((R[B] << 8 | R[C]) - 1) & 0xFFFF;
      R[B] = bc >> 8; R[C] = bc & 0xFF;
      const n = (res - (hflag ? 1 : 0)) & 0xFF;
      const f = (R[F] & FC) | FN | (SZ53[res] & (FS | FZ)) | hflag | (bc ? FP : 0) | (n & FX) | ((n << 4) & FY);
      this.wz = (this.wz + inc) & 0xFFFF;
      if (repeat && bc && res !== 0) {
        const pc = (this.pc - 2) & 0xFFFF;
        this.pc = pc; this.wz = (pc + 1) & 0xFFFF;
        R[F] = (f & ~(FY | FX)) | ((pc >> 8) & (FY | FX));
        return 21;
      }
      R[F] = f;
      return 16;
    }
    let v, b, k;
    if (z === 2) {
      const bc = R[B] << 8 | R[C];
      v = this.bus.inp(bc) & 0xFF;
      this.wz = (bc + inc) & 0xFFFF;
      this.wb(R[H] << 8 | R[L], v);
      hlAdd();
      b = (R[B] - 1) & 0xFF;
      R[B] = b;
      k = v + ((R[C] + inc) & 0xFF);
    } else {
      v = this.rd(R[H] << 8 | R[L]);
      b = (R[B] - 1) & 0xFF;
      R[B] = b;
      const bc = b << 8 | R[C];
      this.bus.out(bc, v);
      this.wz = (bc + inc) & 0xFFFF;
      hlAdd();
      k = v + R[L];
    }
    let f = SZ53[b] | (v & 0x80 ? FN : 0) | (k > 255 ? (FH | FC) : 0) | PARITY[(k & 7) ^ b];
    if (repeat && b) {
      const pc = (this.pc - 2) & 0xFFFF;
      this.pc = pc;
      f = (f & ~(FY | FX)) | ((pc >> 8) & (FY | FX));
      let hf, pp;
      if (f & FC) {
        if (v & 0x80) { hf = (b & 0x0F) === 0 ? FH : 0; pp = PARITY[((b - 1) & 7) ^ (k & 7) ^ b]; }
        else { hf = (b & 0x0F) === 0x0F ? FH : 0; pp = PARITY[((b + 1) & 7) ^ (k & 7) ^ b]; }
      } else { hf = 0; pp = PARITY[(b & 7) ^ (k & 7) ^ b]; }
      R[F] = (f & ~(FH | FP)) | hf | pp;
      return 21;
    }
    R[F] = f;
    return 16;
  }
}

// ---------------------------------------------------------------------------
// CPC
// ---------------------------------------------------------------------------

const LINE_US = 64, LINES = 312;
const RAM_CONFIGS = [[0, 1, 2, 3], [0, 1, 2, 7], [4, 5, 6, 7], [0, 3, 2, 7],
  [0, 4, 2, 3], [0, 5, 2, 3], [0, 6, 2, 3], [0, 7, 2, 3]];
const HW_RGB = [0x808080, 0x808080, 0x00FF80, 0xFFFF80, 0x000080, 0xFF0080, 0x008080, 0xFF8080,
  0xFF0080, 0xFFFF80, 0xFFFF00, 0xFFFFFF, 0xFF0000, 0xFF00FF, 0xFF8000, 0xFF80FF, 0x000080,
  0x00FF80, 0x00FF00, 0x00FFFF, 0x000000, 0x0000FF, 0x008000, 0x0080FF, 0x800080, 0x80FF80,
  0x80FF00, 0x80FFFF, 0x800000, 0x8000FF, 0x808000, 0x8080FF];
const CPC_KEYS = [
  ["CURUP", "CURRIGHT", "CURDOWN", "F9", "F6", "F3", "ENTER", "F."],
  ["CURLEFT", "COPY", "F7", "F8", "F5", "F1", "F2", "F0"],
  ["CLR", "[", "RETURN", "]", "F4", "SHIFT", "\\", "CTRL"],
  ["^", "-", "@", "P", ";", ":", "/", "."],
  ["0", "9", "O", "I", "L", "K", "M", ","],
  ["8", "7", "U", "Y", "H", "J", "N", "SPACE"],
  ["6", "5", "R", "T", "G", "F", "B", "V"],
  ["4", "3", "E", "W", "S", "D", "C", "X"],
  ["1", "2", "ESC", "Q", "TAB", "A", "CAPSLOCK", "Z"],
  ["JOYUP", "JOYDOWN", "JOYLEFT", "JOYRIGHT", "FIRE2", "FIRE1", "SPARE", "DEL"],
];
const KEY_POS = {};
CPC_KEYS.forEach((row, r) => row.forEach((k, b) => { KEY_POS[k] = [r, b]; }));

class CPC {
  constructor(lowerRom, ramKb) {
    this.pages = [];
    for (let i = 0; i < (ramKb || 128) / 16; i++) this.pages.push(new Uint8Array(16384));
    this.lowerRom = lowerRom || null;
    this.map = [this.pages[0], this.pages[1], this.pages[2], this.pages[3]];
    this.rdmap = this.map.slice();
    this.rmr = 0x01 | 0x04 | 0x08;
    this.ramCfg = 0;
    this.pen = 0;
    this.palette = new Array(17).fill(20);
    this.crtcSel = 0;
    this.crtc = [63, 40, 46, 0x8E, 38, 0, 25, 30, 0, 7, 0, 0, 0x30, 0, 0, 0, 0, 0];
    this.ppiA = 0; this.ppiB = 0; this.ppiC = 0; this.ppiCtrl = 0x82;
    this.psgSel = 0;
    this.psg = new Array(16).fill(0);
    this.psgLog = [];                    // [us dentro del frame, registro, valor]
    this.keys = new Array(10).fill(0xFF);
    this.frame = 0; this.line = 0; this.usInLine = 0;
    this.intPending = false; this.intCounter = 0;
    const self = this;
    this.cpu = new Z80({
      rd: (a) => self.rdmap[a >> 14][a & 0x3FFF],
      wr: (a, v) => { self.map[a >> 14][a & 0x3FFF] = v; },
      inp: (p) => self.inp(p),
      out: (p, v) => self.out(p, v),
    });
    this.refresh();
  }

  refresh() {
    const cfg = this.pages.length > 4 ? RAM_CONFIGS[this.ramCfg & 7] : RAM_CONFIGS[0];
    let bank = (this.ramCfg >> 3) & 7;
    if (4 + bank * 4 + 3 >= this.pages.length) bank = 0;
    for (let q = 0; q < 4; q++) {
      const b = cfg[q];
      this.map[q] = this.pages[b < 4 ? b : 4 + bank * 4 + (b - 4)];
      this.rdmap[q] = this.map[q];
    }
    if (!(this.rmr & 0x04) && this.lowerRom) this.rdmap[0] = this.lowerRom;
  }

  inp(port) {
    let v = 0xFF;
    if (!(port & 0x0800)) {
      const sub = (port >> 8) & 3;
      if (sub === 0) v = (this.ppiCtrl & 0x10) ? this.psgRead() : this.ppiA;
      else if (sub === 1) v = 0x5E | (this.line < 8 ? 1 : 0);
      else if (sub === 2) v = this.ppiC;
    } else if (!(port & 0x4000) && ((port >> 8) & 3) === 3) {
      v = (this.crtcSel >= 12 && this.crtcSel <= 17) ? this.crtc[this.crtcSel] : 0;
    }
    return v;
  }
  psgRead() {
    if (((this.ppiC >> 6) & 3) !== 1) return 0xFF;
    if (this.psgSel === 14) { const l = this.ppiC & 0x0F; return l < 10 ? this.keys[l] : 0xFF; }
    return this.psg[this.psgSel];
  }
  psgUpdate() {
    const func = (this.ppiC >> 6) & 3;
    if (func === 3) this.psgSel = this.ppiA & 0x0F;
    else if (func === 2 && this.psgSel < 14) {
      this.psg[this.psgSel] = this.ppiA;
      this.psgLog.push([this.line * LINE_US + this.usInLine, this.psgSel, this.ppiA]);
    }
  }
  out(port, v) {
    if ((port & 0xC000) === 0x4000) {
      const f = v >> 6;
      if (f === 0) this.pen = (v & 0x10) ? 16 : v & 0x0F;
      else if (f === 1) this.palette[this.pen] = v & 0x1F;
      else if (f === 2) {
        const old = this.rmr;
        this.rmr = v & 0x1F;
        if (v & 0x10) { this.intCounter = 0; this.intPending = false; }
        if ((old ^ this.rmr) & 0x0C) this.refresh();
      } else if (this.pages.length > 4) { this.ramCfg = v & 0x3F; this.refresh(); }
    }
    if (!(port & 0x4000)) {
      const sub = (port >> 8) & 3;
      if (sub === 0) this.crtcSel = v & 0x1F;
      else if (sub === 1 && this.crtcSel < 18) this.crtc[this.crtcSel] = v;
    }
    if (!(port & 0x0800)) {
      const sub = (port >> 8) & 3;
      if (sub === 0) { this.ppiA = v; this.psgUpdate(); }
      else if (sub === 1) this.ppiB = v;
      else if (sub === 2) { this.ppiC = v; this.psgUpdate(); }
      else if (v & 0x80) { this.ppiCtrl = v; this.ppiC = 0; }
      else {
        const bit = (v >> 1) & 7;
        if (v & 1) this.ppiC |= 1 << bit; else this.ppiC &= ~(1 << bit);
        this.psgUpdate();
      }
    }
  }

  press(name) { const p = KEY_POS[name]; if (p) this.keys[p[0]] &= ~(1 << p[1]); }
  release(name) { const p = KEY_POS[name]; if (p) this.keys[p[0]] |= 1 << p[1]; }

  // SNA v2/v3 sin comprimir (como los que escribe zxcpc)
  loadSna(buf) {
    const h = buf;
    if (String.fromCharCode(...h.slice(0, 8)) !== "MV - SNA") throw new Error("no es un SNA de CPC");
    const sizeKb = h[0x6B] | (h[0x6C] << 8);
    const n = sizeKb / 16;
    while (this.pages.length < n) this.pages.push(new Uint8Array(16384));
    for (let i = 0; i < n; i++) this.pages[i].set(h.subarray(256 + i * 16384, 256 + (i + 1) * 16384));
    const c = this.cpu, w = (o) => h[o] | (h[o + 1] << 8);
    c.setPair("AF", h[0x12] << 8 | h[0x11]); c.setPair("BC", w(0x13)); c.setPair("DE", w(0x15));
    c.setPair("HL", w(0x17)); c.r = h[0x19]; c.i = h[0x1A];
    c.iff1 = h[0x1B] ? 1 : 0; c.iff2 = h[0x1C] ? 1 : 0;
    c.setPair("IX", w(0x1D)); c.setPair("IY", w(0x1F)); c.setPair("SP", w(0x21)); c.setPair("PC", w(0x23));
    c.im = h[0x25];
    const alt = [[0x26, F, A], [0x28, C, B], [0x2A, E, D], [0x2C, L, H]];
    for (const [o, lo, hi] of alt) { c.alt[lo] = h[o]; c.alt[hi] = h[o + 1]; }
    this.pen = h[0x2E];
    for (let i = 0; i < 17; i++) this.palette[i] = h[0x2F + i] & 0x1F;
    this.rmr = h[0x40] & 0x1F;
    this.ramCfg = h[0x41] & 0x3F;
    this.crtcSel = h[0x42];
    for (let i = 0; i < 18; i++) this.crtc[i] = h[0x43 + i];
    this.ppiA = h[0x56]; this.ppiB = h[0x57]; this.ppiC = h[0x58]; this.ppiCtrl = h[0x59];
    this.psgSel = h[0x5A];
    for (let i = 0; i < 16; i++) this.psg[i] = h[0x5B + i];
    this.refresh();
  }

  runFrame() {
    const c = this.cpu;
    this.psgLog = [];
    while (this.line < LINES) {
      if (this.intPending && c.iff1 && !c.eiDelay) {
        const t = c.interrupt(0xFF);
        if (t) { this.intPending = false; this.intCounter &= 0x1F; this.advance((t + 3) >> 2); continue; }
      }
      if (c.halted) { this.advance(LINE_US - this.usInLine); continue; }
      const t = c.step();
      this.advance((t + 3) >> 2);
    }
    this.line -= LINES;
    this.frame++;
  }
  advance(us) {
    this.usInLine += us;
    while (this.usInLine >= LINE_US) {
      this.usInLine -= LINE_US;
      this.line++;
      this.intCounter++;
      if (this.line === 2) {
        if (this.intCounter >= 32) this.intPending = true;
        this.intCounter = 0;
      } else if (this.intCounter >= 52) { this.intCounter = 0; this.intPending = true; }
    }
  }

  // Imagen RGBA de la zona definida por el CRTC (modo 0, 1 o 2), sin borde
  render(rgba, stride, ox, oy) {
    const r1 = this.crtc[1], r6 = this.crtc[6], r9 = this.crtc[9] & 0x1F;
    const start = ((this.crtc[12] & 0x3F) << 8) | this.crtc[13];
    const mode = this.rmr & 3;
    const pal = this.palette.map((p) => HW_RGB[p & 31]);
    const pg = this.pages;
    let y = oy;
    for (let cr = 0; cr < r6; cr++) {
      for (let ln = 0; ln <= r9; ln++, y++) {
        let o = (y * stride + ox) * 4;
        for (let ch = 0; ch < r1; ch++) {
          const ma = (start + cr * r1 + ch) & 0x3FFF;
          const base = ((ma & 0x3000) << 2) | ((ln & 7) << 11) | ((ma & 0x3FF) << 1);
          for (let k = 0; k < 2; k++) {
            const ad = (base + k) & 0xFFFF, b = pg[ad >> 14][ad & 0x3FFF];
            let pens;
            if (mode === 1) {
              pens = [((b >> 7) & 1) | (((b >> 3) & 1) << 1), ((b >> 6) & 1) | (((b >> 2) & 1) << 1),
                ((b >> 5) & 1) | (((b >> 1) & 1) << 1), ((b >> 4) & 1) | ((b & 1) << 1)];
            } else if (mode === 2) {
              pens = [];
              for (let j = 7; j >= 0; j -= 2) pens.push(((b >> j) & 1) | ((b >> (j - 1)) & 1));
            } else {
              const px = (b7, b3, b5, b1) => ((b >> b7) & 1) | (((b >> b3) & 1) << 1) |
                (((b >> b5) & 1) << 2) | (((b >> b1) & 1) << 3);
              const p0 = px(7, 3, 5, 1), p1 = px(6, 2, 4, 0);
              pens = [p0, p0, p1, p1];
            }
            for (const pn of pens) {
              const rgb = pal[pn];
              rgba[o] = rgb >> 16; rgba[o + 1] = (rgb >> 8) & 0xFF; rgba[o + 2] = rgb & 0xFF; rgba[o + 3] = 255;
              o += 4;
            }
          }
        }
      }
    }
    return [r1 * 8, y - oy];
  }
  border() { return HW_RGB[this.palette[16] & 31]; }
}

// ---------------------------------------------------------------------------
// PSG AY-3-8912 a 1 MHz: tonos, ruido y envolvente
// ---------------------------------------------------------------------------

const AY_VOL = [0, 0.0106, 0.0150, 0.0222, 0.0320, 0.0466, 0.0665, 0.1039, 0.1237, 0.2050,
  0.2930, 0.3725, 0.4924, 0.6351, 0.8053, 1.0];

class AY {
  constructor(rate) {
    this.rate = rate;
    this.reg = new Array(16).fill(0);
    this.cnt = [0, 0, 0]; this.out = [0, 0, 0];
    this.ncnt = 0; this.rng = 1; this.nout = 0;
    this.ecnt = 0; this.estep = 0; this.ehold = false; this.ealt = false; this.eatt = false;
    this.acc = 0;
  }
  write(r, v) {
    this.reg[r] = v;
    if (r === 13) {
      this.estep = 0; this.ehold = false; this.ecnt = 0;
      this.eatt = !!(v & 4);
    }
  }
  envLevel() {
    const v = this.estep & 15;
    return this.eatt ? v : 15 - v;
  }
  tick8() {          // 8 ciclos de 1 MHz = un paso de los contadores
    const rg = this.reg;
    for (let ch = 0; ch < 3; ch++) {
      const per = (rg[ch * 2] | ((rg[ch * 2 + 1] & 15) << 8)) || 1;
      if (++this.cnt[ch] >= per) { this.cnt[ch] = 0; this.out[ch] ^= 1; }
    }
    const np = (rg[6] & 31) || 1;
    if (++this.ncnt >= np * 2) {
      this.ncnt = 0;
      const bit = (this.rng ^ (this.rng >> 3)) & 1;
      this.rng = (this.rng >> 1) | (bit << 16);
      this.nout = this.rng & 1;
    }
    const ep = (rg[11] | (rg[12] << 8)) || 1;
    if (++this.ecnt >= ep * 2) {
      this.ecnt = 0;
      if (!this.ehold) {
        this.estep++;
        if (this.estep > 15) {
          const shape = rg[13];
          if (!(shape & 8) || (shape & 1)) {
            this.ehold = true;
            if (!(shape & 8)) this.eatt = false, this.estep = 15;      // queda a 0
            else { if (shape & 2) this.eatt = !this.eatt; this.estep = 15; }
          } else { this.estep = 0; if (shape & 2) this.eatt = !this.eatt; }
        }
      }
    }
  }
  sample() {
    const rg = this.reg, mix = rg[7];
    let s = 0;
    for (let ch = 0; ch < 3; ch++) {
      const t = (this.out[ch] | ((mix >> ch) & 1)) & (this.nout | ((mix >> (ch + 3)) & 1));
      const vr = rg[8 + ch];
      const vol = (vr & 16) ? this.envLevel() : vr & 15;
      s += t ? AY_VOL[vol] : 0;
    }
    return s / 3;
  }
  // n muestras con las escrituras del frame [us, reg, val] repartidas en el tiempo
  render(n, log, frameUs) {
    const outb = new Float32Array(n);
    const ticksPerSample = 1000000 / 8 / this.rate;
    let li = 0;
    for (let i = 0; i < n; i++) {
      const us = (i / n) * frameUs;
      while (li < log.length && log[li][0] <= us) { this.write(log[li][1], log[li][2]); li++; }
      this.acc += ticksPerSample;
      let s = 0, k = 0;
      while (this.acc >= 1) { this.tick8(); s += this.sample(); k++; this.acc -= 1; }
      outb[i] = k ? s / k : this.sample();
    }
    while (li < log.length) { this.write(log[li][1], log[li][2]); li++; }
    return outb;
  }
}

const ZXCPC = { Z80, CPC, AY, KEY_POS, HW_RGB, LINE_US, LINES };
if (typeof module !== "undefined" && module.exports) module.exports = ZXCPC;
if (typeof window !== "undefined") window.ZXCPC = ZXCPC;
