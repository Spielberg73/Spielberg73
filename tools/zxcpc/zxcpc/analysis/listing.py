"""Desensamblado reensamblable (código + datos) a partir de un análisis.

El fichero generado se vuelve a ensamblar byte a byte idéntico con
``zxcpc asm`` (y en lo esencial con pasmo/sjasmplus), así que sirve de base
para modificar el juego a mano: etiquetas en los destinos de saltos,
comentarios con los puntos calientes y DB para lo que no es código.
"""

from __future__ import annotations

from ..z80.asm import Assembler, AsmError
from .static import KIND_INFO


def _label(a):
    return f"L{a:04X}"


def make_listing(an, start=None, end=None, hotspot_comments=True) -> str:
    p = an.program
    mem = p.mem
    lo = start if start is not None else (0x4000 if p.platform == "zx" else 0x0000)
    hi = end if end is not None else 0x10000
    if start is None and p.load_ranges:
        lo = max(lo, min(r[0] for r in p.load_ranges))
        hi = min(hi, max(r[1] for r in p.load_ranges))
    instrs = {a: i for a, i in an.instrs.items() if lo <= a < hi}
    # descartar instrucciones solapadas (quedarse con las ejecutadas/antes)
    executed = an.trace.executed if an.trace is not None else set()
    chosen = {}
    occupied = {}
    for a in sorted(instrs, key=lambda x: (x not in executed, x)):
        ins = instrs[a]
        rng = range(a, a + ins.length)
        if any(b in occupied for b in rng) or a + ins.length > hi:
            continue
        for b in rng:
            occupied[b] = a
        chosen[a] = ins
    labels = {}
    for a, ins in chosen.items():
        if ins.target is not None and ins.flow in ("jp", "jr", "djnz", "call") and ins.target in chosen:
            labels[ins.target] = _label(ins.target)
    # comprobar que cada instrucción se reensambla igual (formas no canónicas -> DB)
    texts = {a: ins.text() for a, ins in chosen.items()}
    ok = _verify(chosen, texts)
    hs_at = {}
    for h in an.hotspots:
        hs_at.setdefault(h.addr, []).append(h)

    out = [f"; Desensamblado de {p.source} generado por zxcpc",
           f"; Plataforma: {'ZX Spectrum' if p.platform == 'zx' else 'Amstrad CPC'}",
           f"; Entrada: ${p.entry:04X}", "", f"        org ${lo:04X}", ""]
    a = lo
    data_run = []

    def flush():
        if not data_run:
            return
        start_a = data_run[0][0]
        vals = [v for _, v in data_run]
        for k in range(0, len(vals), 16):
            chunk = vals[k:k + 16]
            if all(v == 0 for v in chunk) and len(chunk) == 16:
                out.append(f"        ds 16                      ; ${start_a + k:04X}")
            else:
                out.append("        db " + ",".join(f"${v:02X}" for v in chunk) +
                           f"   ; ${start_a + k:04X}")
        data_run.clear()

    while a < hi:
        if a in chosen:
            flush()
            ins = chosen[a]
            if a in labels:
                out.append(f"{labels[a]}:")
            text = texts[a] if ok.get(a) else "db " + ",".join(f"${b:02X}" for b in ins.raw)
            if ok.get(a):
                text = _with_labels(ins, labels) or text
            comment = f"${a:04X}"
            if not ok.get(a):
                comment += f"  {ins.text()} (forma no canónica)"
            if hotspot_comments and a in hs_at:
                comment += "  <<< " + "; ".join(KIND_INFO.get(h.kind, (h.kind,))[0] for h in hs_at[a])
            out.append(f"        {text:<28} ; {comment}")
            a += ins.length
        else:
            data_run.append((a, mem[a]))
            if a in labels:
                flush()
            a += 1
    flush()
    return "\n".join(out) + "\n"


def _with_labels(ins, labels):
    if ins.target is None or ins.target not in labels:
        return None
    if ins.flow not in ("jp", "jr", "djnz", "call"):
        return None
    return ins.text(labels=labels)


def _verify(chosen, texts):
    """Ensambla todas las instrucciones y marca las que dan los mismos bytes."""
    ordered = sorted(chosen)
    src = []
    for a in ordered:
        src.append(f" org ${a:04X}")
        src.append(" " + texts[a])
    ok = {}
    try:
        res = Assembler().assemble("\n".join(src))
    except AsmError:
        # comprobación una a una si algo falla en bloque
        for a in ordered:
            try:
                r = Assembler().assemble(f" org ${a:04X}\n {texts[a]}")
                ok[a] = r.image() == chosen[a].raw
            except AsmError:
                ok[a] = False
        return ok
    got = {}
    for addr, data, _, _ in res.listing:
        got[addr] = data
    for a in ordered:
        ok[a] = got.get(a) == chosen[a].raw
    return ok
