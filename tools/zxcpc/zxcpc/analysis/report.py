"""Informes del análisis: texto para terminal y HTML autocontenido."""

from __future__ import annotations

import base64
import html
import os
from collections import defaultdict

from .static import KIND_INFO

SEV_ORDER = {"grave": 0, "aviso": 1, "info": 2}


def text_report(an, max_rows=12) -> str:
    p = an.program
    out = [f"== {p.source} ({'ZX Spectrum' if p.platform == 'zx' else 'Amstrad CPC'}, {p.kind}) ==",
           f"Entrada: {p.entry:#06x}   IM {p.im}   instrucciones localizadas: "
           f"{an.stats['instructions']}"]
    if an.trace is not None:
        s = an.stats
        out.append(f"Dinámico: {s['frames']} frames, {s['executed']} instrucciones ejecutadas, "
                   f"pila {s['sp_range'][0]:#06x}-{s['sp_range'][1]:#06x}")
    for n in p.notes:
        out.append(f"  · {n}")
    groups = defaultdict(list)
    for h in an.hotspots:
        groups[h.kind].append(h)
    for kind in sorted(groups, key=lambda k: (SEV_ORDER[KIND_INFO.get(k, ('', 'info'))[1]], k)):
        title, sev = KIND_INFO.get(kind, (kind, "info"))
        hs = sorted(groups[kind], key=lambda h: -h.count)
        out.append(f"\n[{sev.upper()}] {title}: {len(hs)}")
        for h in hs[:max_rows]:
            det = _detail_text(h)
            out.append(f"   {h.addr:04X}  {h.text:<24} x{h.count:<7} {det}")
        if len(hs) > max_rows:
            out.append(f"   ... y {len(hs) - max_rows} más")
    if an.notes:
        out.append("\nConclusiones:")
        for n in an.notes:
            out.append(f"  - {n}")
    return "\n".join(out)


def _detail_text(h):
    d = h.detail
    if "name" in d:
        return f"→ {d['name']}" + (" (indirecta)" if d.get("indirect") else "")
    if "ports" in d:
        return "puertos " + ", ".join(d["ports"][:6])
    if "regions" in d:
        return ", ".join(f"{k}:{v}" for k, v in d["regions"].items())
    if "pages" in d:
        return "páginas " + ", ".join(f"{p:#06x}" for p in d["pages"][:6])
    if "modifies" in d:
        return "modifica " + ", ".join(f"{a:#06x}" for a in d["modifies"][:6])
    if "mode" in d:
        return f"IM {d['mode']}"
    return ""


def _context(an, addr, before=3, after=3):
    ordered = sorted(an.instrs)
    import bisect
    i = bisect.bisect_left(ordered, addr)
    rows = []
    for k in range(max(0, i - before), min(len(ordered), i + after + 1)):
        a = ordered[k]
        ins = an.instrs[a]
        rows.append((a, ins.raw.hex(" ").upper(), ins.text(), a == addr))
    return rows


CSS = """
:root{--bg:#f7f7f4;--fg:#1d1d1b;--mut:#6b6b66;--card:#fff;--line:#e2e1dc;--acc:#2f5d8a;
--grave:#b3261e;--aviso:#9a6200;--info:#2f5d8a;--code:#f0efe9}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--fg:#ecebe6;
--mut:#9d9c96;--card:#1f1f1d;--line:#34332f;--acc:#8db4dc;--grave:#f08a82;--aviso:#e0b25a;
--info:#8db4dc;--code:#262624}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.6rem;margin:.2em 0}h2{font-size:1.15rem;margin:2em 0 .6em}
.sub{color:var(--mut)}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
gap:10px;margin:16px 0}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:12px}.card b{display:block;font-size:1.4rem}.card span{color:var(--mut);font-size:.85rem}
.notes li{margin:.3em 0}details{background:var(--card);border:1px solid var(--line);border-radius:10px;
margin:8px 0;padding:0 12px}summary{cursor:pointer;padding:10px 0;font-weight:600}
.sev{display:inline-block;font-size:.72rem;font-weight:700;padding:1px 7px;border-radius:99px;
margin-right:8px;color:var(--card)}.sev.grave{background:var(--grave)}.sev.aviso{background:var(--aviso)}
.sev.info{background:var(--info)}table{border-collapse:collapse;width:100%;font-size:.88rem}
td,th{text-align:left;padding:4px 8px;border-top:1px solid var(--line);vertical-align:top}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:var(--code);padding:6px 8px;border-radius:6px;margin:4px 0;overflow-x:auto;font-size:.8rem}
.hl{font-weight:700;color:var(--acc)}.shots{display:flex;gap:10px;flex-wrap:wrap}
.shots img{max-width:100%;width:320px;image-rendering:pixelated;border-radius:6px;border:1px solid var(--line)}
.map{display:flex;height:22px;border-radius:6px;overflow:hidden;border:1px solid var(--line)}
.map i{flex:1}.legend span{display:inline-flex;align-items:center;margin-right:14px;font-size:.85rem}
.legend b{width:12px;height:12px;display:inline-block;margin-right:5px;border-radius:3px}
.wrap{overflow-x:auto}
"""


def html_report(an, path, title=None, extra_sections=""):
    p = an.program
    plat = "ZX Spectrum" if p.platform == "zx" else "Amstrad CPC"
    title = title or f"Análisis de {p.source}"
    s = an.stats
    cards = [("Plataforma", plat), ("Entrada", f"{p.entry:#06x}"),
             ("Instrucciones", s["instructions"]), ("Puntos calientes", s["hotspots"])]
    if an.trace is not None:
        cards += [("Frames ejecutados", s["frames"]), ("Instr. ejecutadas", s["executed"])]
    card_html = "".join(f'<div class="card"><b>{html.escape(str(v))}</b><span>{html.escape(k)}</span></div>'
                        for k, v in cards)
    notes = "".join(f"<li>{html.escape(n)}</li>" for n in list(p.notes) + list(an.notes))
    groups = defaultdict(list)
    for h in an.hotspots:
        groups[h.kind].append(h)
    sections = []
    for kind in sorted(groups, key=lambda k: (SEV_ORDER[KIND_INFO.get(k, ('', 'info'))[1]], k)):
        t, sev = KIND_INFO.get(kind, (kind, "info"))
        hs = sorted(groups[kind], key=lambda h: (-h.count, h.addr))
        rows = []
        for h in hs[:60]:
            ctx = "\n".join(
                (f'<span class="hl">{a:04X}  {b:<12} {html.escape(txt)}</span>' if me else
                 f"{a:04X}  {b:<12} {html.escape(txt)}") for a, b, txt, me in _context(an, h.addr))
            rows.append(f"<tr><td><code>{h.addr:04X}</code></td><td><code>{html.escape(h.text)}</code>"
                        f"</td><td>{h.count}</td><td>{html.escape(_detail_text(h))}"
                        f"<pre>{ctx}</pre></td></tr>")
        more = f"<p class='sub'>... y {len(hs) - 60} más</p>" if len(hs) > 60 else ""
        sections.append(
            f'<details {"open" if sev != "info" else ""}><summary><span class="sev {sev}">{sev}'
            f'</span>{html.escape(t)} — {len(hs)}</summary><div class="wrap"><table>'
            f"<tr><th>Dirección</th><th>Instrucción</th><th>Ejecuciones</th><th>Detalle y contexto</th></tr>"
            f'{"".join(rows)}</table></div>{more}</details>')
    shots = ""
    if an.trace is not None and an.trace.screenshots:
        imgs = []
        for sp in an.trace.screenshots[-4:]:
            if os.path.exists(sp):
                with open(sp, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                imgs.append(f'<img alt="captura" src="data:image/png;base64,{b64}">')
        shots = f"<h2>Capturas del análisis dinámico</h2><div class='shots'>{''.join(imgs)}</div>"
    mmap = _memory_map(an)
    doc = f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>{CSS}</style></head><body><main>
<h1>{html.escape(title)}</h1><div class="sub">Informe generado por zxcpc — kit de port asistido Spectrum ⇄ CPC</div>
<div class="cards">{card_html}</div>
<h2>Conclusiones</h2><ul class="notes">{notes}</ul>
{extra_sections}
<h2>Mapa de memoria</h2>{mmap}
<h2>Puntos calientes</h2>{''.join(sections)}
{shots}
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
    return path


def _memory_map(an):
    """Barra de 256 celdas (256 bytes cada una): código, escrito, datos, vacío."""
    mem = an.program.mem
    code = bytearray(256)
    for a, ins in an.instrs.items():
        code[a >> 8] = 1
    written = an.trace.written if an.trace is not None else bytearray(65536)
    cells = []
    for pg in range(256):
        chunk = mem[pg * 256:(pg + 1) * 256]
        w = any(written[pg * 256:(pg + 1) * 256])
        if code[pg]:
            col = "var(--acc)"
        elif w:
            col = "var(--aviso)"
        elif any(chunk):
            col = "var(--mut)"
        else:
            col = "var(--line)"
        cells.append(f'<i style="background:{col}" title="{pg * 256:#06x}"></i>')
    legend = ('<div class="legend"><span><b style="background:var(--acc)"></b>código</span>'
              '<span><b style="background:var(--aviso)"></b>escrito en ejecución</span>'
              '<span><b style="background:var(--mut)"></b>datos</span>'
              '<span><b style="background:var(--line)"></b>vacío</span></div>')
    return f'<div class="map">{"".join(cells)}</div><div class="sub">$0000 → $FFFF</div>{legend}'
