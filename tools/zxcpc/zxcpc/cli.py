"""Interfaz de línea de órdenes de zxcpc."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

from . import __version__


def _num(s):
    s = s.strip()
    if s.startswith(("$", "#")):
        return int(s[1:], 16)
    if s.lower().startswith("0x"):
        return int(s, 16)
    if s.lower().endswith("h"):
        return int(s[:-1], 16)
    return int(s)


def _progress(prefix):
    def f(i, n):
        sys.stderr.write(f"\r{prefix} {i}/{n} frames")
        sys.stderr.flush()
    return f


def _load(args):
    from .program import load_program
    return load_program(args.file, platform=getattr(args, "platform", None),
                        load_addr=_num(args.load) if getattr(args, "load", None) else None,
                        exec_addr=_num(args.exec) if getattr(args, "exec", None) else None,
                        file_in_image=getattr(args, "name", None),
                        sp=_num(args.sp) if getattr(args, "sp", None) else None,
                        zx_rom=_read_rom(getattr(args, "rom", None)),
                        cpc_roms=_cpc_roms(getattr(args, "cpc_roms", None)))


def _read_rom(path):
    if not path:
        return None
    with open(path, "rb") as f:
        return f.read()


def _cpc_roms(path):
    """Directorio con cpc6128.rom (32K: SO + BASIC) o os/basic por separado."""
    if not path:
        return None
    full = os.path.join(path, "cpc6128.rom")
    if os.path.exists(full):
        data = open(full, "rb").read()
        return data[:16384], {0: data[16384:32768]}
    raise SystemExit(f"no encuentro cpc6128.rom en {path}")


def _analyze(args, program, shots=None):
    from .analysis.dynamic import run_dynamic
    from .analysis.static import analyze
    trace = None
    if args.frames > 0:
        t0 = time.time()
        trace = run_dynamic(program, frames=args.frames, rom=_read_rom(getattr(args, "rom", None)),
                            seed=getattr(args, "seed", 1), screenshot_prefix=shots,
                            screenshot_every=max(1, args.frames // 3) if shots else 0,
                            cpc_roms=_cpc_roms(getattr(args, "cpc_roms", None)),
                            progress=_progress("análisis dinámico:") if not args.quiet else None)
        if not args.quiet:
            sys.stderr.write(f"\ranálisis dinámico: {args.frames} frames en {time.time() - t0:.1f}s\n")
    return analyze(program, trace)


# ---------------------------------------------------------------------------

def cmd_info(args):
    from .formats import cpc as fcpc, zx as fzx
    from .program import detect_platform
    data = open(args.file, "rb").read()
    plat, kind = detect_platform(args.file, data)
    print(f"{args.file}: {len(data)} bytes, plataforma={plat or '?'} tipo={kind}")
    if kind == "tap":
        for b in fzx.read_tap(data):
            h = b.header()
            if h:
                t = ["Program", "Number array", "Character array", "Bytes"][h["type"]]
                print(f"  cabecera {t:16} '{h['name']}' long={h['length']} p1={h['param1']} p2={h['param2']}")
            else:
                print(f"  datos flag={b.flag:#04x} {len(b.data)} bytes {'ok' if b.checksum_ok else 'CHECKSUM MAL'}")
    elif kind in ("tzx", "cdt"):
        for b in fzx.read_tzx(data):
            extra = f" {len(b.data)} bytes" if b.data else ""
            extra += f" {b.params.get('text') or b.params.get('name') or ''}"
            print(f"  bloque {b.id:#04x}{extra}")
        if kind == "cdt":
            for f in fcpc.read_cdt_files(data):
                print(f"  fichero '{f['name']}' tipo={f['type']} carga={f['load']:#06x} "
                      f"exec={f['exec']:#06x} {len(f['data'])} bytes")
    elif kind == "dsk":
        d = fcpc.Disk.read(data)
        for name, content in d.files().items():
            h = fcpc.parse_amsdos_header(content)
            if h:
                print(f"  {name:12} tipo={h['type']} carga={h['load']:#06x} exec={h['exec']:#06x} "
                      f"{h['length']} bytes")
            else:
                print(f"  {name:12} {len(content)} bytes (sin cabecera)")
    else:
        p = _load(args)
        print(f"  PC={p.regs['PC']:#06x} SP={p.regs['SP']:#06x} IM={p.im} IFF={p.iff1}")
        for n in p.notes:
            print(f"  · {n}")
    return 0


def cmd_analyze(args):
    from .analysis.report import html_report, text_report
    p = _load(args)
    shots = None
    if args.html:
        base = os.path.splitext(args.html)[0]
        os.makedirs(base + "_capturas", exist_ok=True)
        shots = os.path.join(base + "_capturas", "frame")
    an = _analyze(args, p, shots)
    print(text_report(an))
    if args.html:
        html_report(an, args.html)
        print(f"\ninforme HTML: {args.html}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([{"addr": f"{h.addr:04X}", "kind": h.kind, "instr": h.text, "count": h.count,
                        "detail": {k: (v if not isinstance(v, set) else sorted(v))
                                   for k, v in h.detail.items()}}
                       for h in an.hotspots], f, indent=1, ensure_ascii=False, default=str)
    return 0


def cmd_disasm(args):
    from .analysis.listing import make_listing
    p = _load(args)
    an = _analyze(args, p)
    text = make_listing(an, _num(args.start) if args.start else None,
                        _num(args.end) if args.end else None)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"desensamblado: {args.output}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_asm(args):
    from .z80.asm import assemble_file, AsmError
    try:
        res = assemble_file(args.file)
    except AsmError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    data = res.image()
    out = args.output or os.path.splitext(args.file)[0] + ".bin"
    with open(out, "wb") as f:
        f.write(data)
    print(f"{out}: {len(data)} bytes desde ${res.start:04X}")
    return 0


def cmd_run(args):
    p = _load(args)
    keys = _parse_timed_keys(args.keys) if args.keys else []

    def script(m, frame):
        m.release_all()
        for f0, f1, names in keys:
            if f0 <= frame < f1:
                for k in names:
                    m.press(k)
    if p.platform == "zx":
        from .machines.spectrum import Spectrum48K, SpectrumPlus3
        from .analysis.dynamic import _set_regs
        if p.zx_state is not None and p.zx_state.model == "+3":
            m = SpectrumPlus3(_read_rom(args.rom))
            m.load_state(p.zx_state)
        else:
            m = Spectrum48K(_read_rom(args.rom))
            m.mem[0x4000:] = p.mem[0x4000:]
            _set_regs(m.cpu, p)
    else:
        from .machines.cpc import CPC
        m = CPC(*(_cpc_roms(args.cpc_roms) or (None, None)))
        m.load_state(p.to_cpc_state())
    t0 = time.time()
    m.run_frames(args.frames, script)
    out = args.png or os.path.splitext(os.path.basename(args.file))[0] + ".png"
    m.screenshot(out)
    print(f"{args.frames} frames en {time.time() - t0:.1f}s; captura: {out}")
    return 0


def _parse_timed_keys(spec):
    """'20-60:P,60-90:A+SPACE' -> [(20,60,['P']), (60,90,['A','SPACE'])]"""
    out = []
    for part in spec.split(","):
        rng, names = part.split(":")
        a, b = rng.split("-")
        out.append((int(a), int(b), [n.strip().upper() for n in names.split("+")]))
    return out


def cmd_port(args):
    from .analysis.report import html_report
    p = _load(args)
    target = args.to or ("cpc" if p.platform == "zx" else "zx")
    if (p.platform, target) not in (("zx", "cpc"), ("cpc", "zx")):
        raise SystemExit(f"no sé portar de {p.platform} a {target}")
    name = os.path.splitext(os.path.basename(args.file))[0]
    outdir = args.output or f"{name}_{target}"
    os.makedirs(outdir, exist_ok=True)
    cfg = {}
    if args.config:
        with open(args.config, encoding="utf-8") as f:
            cfg = json.load(f)
    shots_dir = os.path.join(outdir, "capturas")
    os.makedirs(shots_dir, exist_ok=True)
    an = _analyze(args, p, os.path.join(shots_dir, "original"))
    if target == "cpc":
        return _port_zx2cpc(args, p, an, cfg, outdir, name, shots_dir, html_report)
    return _port_cpc2zx(args, p, an, cfg, outdir, name, shots_dir, html_report)


def _port_zx2cpc(args, p, an, cfg, outdir, name, shots_dir, html_report):
    from .port.zx2cpc import PortOptions, port_zx_to_cpc, build_dsk, patches_json
    from .formats.cpc import write_cpc_sna
    from .machines.cpc import CPC
    opt = PortOptions.from_json(cfg)
    opt.zx_rom = _read_rom(args.rom)
    if args.mono:
        opt.mono = True
    if args.refresh is not None:
        opt.refresh_lines = args.refresh
    if args.keys:
        for item in args.keys.split(","):
            zk, ck = item.split("=")
            opt.keys[zk.strip().upper()] = [c.strip().upper() for c in ck.split("+")]
    if args.exclude:
        opt.exclude |= {_num(x) for x in args.exclude.split(",")}
    if args.palette:
        opt.palette = [int(x) for x in args.palette.split(",")]
    res = port_zx_to_cpc(an, opt)
    sna = os.path.join(outdir, f"{name}_cpc.sna")
    with open(sna, "wb") as f:
        f.write(write_cpc_sna(res.state))
    outputs = [sna]
    try:
        dsk = os.path.join(outdir, f"{name}_cpc.dsk")
        with open(dsk, "wb") as f:
            f.write(build_dsk(res))
        outputs.append(dsk)
    except Exception as e:     # noqa: BLE001
        res.warnings.append(f"no se pudo generar el disco: {e}")
    with open(os.path.join(outdir, "hal.asm"), "w", encoding="utf-8") as f:
        f.write(res.hal_source)
    with open(os.path.join(outdir, "parches.json"), "w", encoding="utf-8") as f:
        f.write(patches_json(res))
    used = {"refresh_lines": opt.refresh_lines, "beep_vol": opt.beep_vol, "mono": opt.mono,
            "palette": [f for _, f, _ in res.palette], "keys": opt.keys,
            "exclude": [f"{a:04X}" for a in sorted(opt.exclude)],
            "rom_im2_vector": opt.rom_im2_vector, "patch_static": opt.patch_static}
    with open(os.path.join(outdir, "port.json"), "w", encoding="utf-8") as f:
        json.dump(used, f, indent=1, ensure_ascii=False)
    # prueba en el CPC emulado
    m = CPC()
    m.load_state(res.state)
    m.run_frames(args.test_frames)
    shot = os.path.join(shots_dir, "port_cpc.png")
    m.screenshot(shot)
    if an.trace is not None:
        an.trace.screenshots.append(shot)
    extra = _port_section_html(res, outputs)
    html_report(an, os.path.join(outdir, "informe.html"), f"Port de {p.source} a Amstrad CPC", extra)
    print(f"Port ZX -> CPC de {p.source}")
    print(f"  parches aplicados: {len(res.patches)}   bytes libres en el HAL: {res.free_bytes}")
    print("  paleta: " + ", ".join(f"pluma {i}={n}" for i, _, n in res.palette))
    for w in res.warnings:
        print(f"  ! {w}")
    print("  ficheros:")
    for o in outputs + [os.path.join(outdir, x) for x in ("informe.html", "hal.asm", "parches.json",
                                                           "port.json")]:
        print(f"    {o}")
    return 0


def _port_section_html(res, outputs):
    import html as H
    rows = "".join(
        f"<tr><td><code>{pt.addr:04X}</code></td><td><code>{H.escape(pt.text)}</code></td>"
        f"<td><code>{pt.orig.hex(' ').upper()}</code> → <code>{pt.new.hex(' ').upper()}</code></td>"
        f"<td>{H.escape(pt.kind)}</td><td><code>{H.escape(str(pt.handler))}</code> {H.escape(pt.note)}</td></tr>"
        for pt in res.patches)
    warns = "".join(f"<li>{H.escape(w)}</li>" for w in res.warnings) or "<li>ninguno</li>"
    pal = ", ".join(f"pluma {i}: {H.escape(n)}" for i, _, n in res.palette)
    files = "".join(f"<li><code>{H.escape(os.path.basename(o))}</code></li>" for o in outputs)
    return (f"<h2>Resultado del port</h2><ul class='notes'>{files}"
            f"<li>Paleta: {pal}</li><li>Bytes libres en el HAL: {res.free_bytes}</li></ul>"
            f"<h2>Avisos del portador</h2><ul class='notes'>{warns}</ul>"
            f"<details><summary>Parches aplicados — {len(res.patches)}</summary><div class='wrap'>"
            f"<table><tr><th>Dirección</th><th>Original</th><th>Bytes</th><th>Tipo</th><th>Manejador</th></tr>"
            f"{rows}</table></div></details>")


def _port_cpc2zx(args, p, an, cfg, outdir, name, shots_dir, html_report):
    from .port.cpc2zx import CPCPortOptions, port_cpc_to_zx
    from .formats.zx import write_z80
    from .machines.spectrum import SpectrumPlus3
    opt = CPCPortOptions.from_json(cfg)
    roms = _cpc_roms(args.cpc_roms)
    if roms:
        opt.font = roms[0][0x3900:0x3C00]
    if args.refresh is not None:
        opt.refresh_lines = args.refresh
    if args.keys:
        for item in args.keys.split(","):
            ck, zk = item.split("=")
            opt.keys[ck.strip().upper()] = zk.strip().upper()
    if args.exclude:
        opt.exclude |= {_num(x) for x in args.exclude.split(",")}
    res = port_cpc_to_zx(an, opt)
    z80 = os.path.join(outdir, f"{name}_zx.z80")
    with open(z80, "wb") as f:
        f.write(write_z80(res.state))
    outputs = [z80]
    with open(os.path.join(outdir, "hal.asm"), "w", encoding="utf-8") as f:
        f.write(res.hal_source)
    from .port.zx2cpc import patches_json
    with open(os.path.join(outdir, "parches.json"), "w", encoding="utf-8") as f:
        f.write(patches_json(res))
    m = SpectrumPlus3()
    m.load_state(res.state)
    m.run_frames(args.test_frames)
    shot = os.path.join(shots_dir, "port_zx.png")
    m.screenshot(shot)
    if an.trace is not None:
        an.trace.screenshots.append(shot)
    extra = _port_section_html(res, outputs)
    html_report(an, os.path.join(outdir, "informe.html"), f"Port de {p.source} a ZX Spectrum", extra)
    print(f"Port CPC -> ZX de {p.source} (Spectrum +2A/+3, paginación especial)")
    print(f"  parches aplicados: {len(res.patches)}   bytes libres en el HAL: {res.free_bytes}")
    for w in res.warnings:
        print(f"  ! {w}")
    print("  ficheros:")
    for o in outputs + [os.path.join(outdir, x) for x in ("informe.html", "hal.asm", "parches.json")]:
        print(f"    {o}")
    return 0


def cmd_scr(args):
    """Convierte pantallas: .scr de Spectrum -> PNG / pantalla CPC y viceversa."""
    from .machines.spectrum import Spectrum48K
    data = open(args.file, "rb").read()
    if len(data) == 6912:
        m = Spectrum48K()
        m.mem[0x4000:0x4000 + 6912] = data
        out = args.output or os.path.splitext(args.file)[0] + ".png"
        m.screenshot(out, border=0)
        print(f"PNG: {out}")
        if args.cpc:
            from .port.zx2cpc import build_tables, choose_palette, colour_weights, \
                convert_screen_to_cpc
            from .formats.cpc import make_amsdos_header
            ram = bytearray(49152)
            ram[:6912] = data
            pal = choose_palette(colour_weights([ram]))
            _, _, xm, pm = build_tables(pal)
            scr = convert_screen_to_cpc(ram, xm, pm)
            cpc_out = args.cpc
            with open(cpc_out, "wb") as f:
                f.write(make_amsdos_header("SCREEN", "BIN", 16384, 0xC000, 0) + scr)
            print(f"pantalla CPC (256x192, base $C000, CRTC R1=32 R6=24 inicio $100): {cpc_out}")
        return 0
    raise SystemExit("solo se admiten pantallas .scr de 6912 bytes")


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="zxcpc",
        description="Kit de port asistido ZX Spectrum <-> Amstrad CPC: análisis, "
                    "desensamblado y conversión de juegos.")
    ap.add_argument("--version", action="version", version=f"zxcpc {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp, frames=300):
        sp.add_argument("file", help="fichero de entrada (.z80 .sna .tap .tzx .dsk .cdt .bin)")
        sp.add_argument("--platform", choices=["zx", "cpc"], help="forzar plataforma")
        sp.add_argument("--load", help="dirección de carga (binarios en bruto)")
        sp.add_argument("--exec", help="dirección de arranque (por defecto, la de carga)")
        sp.add_argument("--sp", help="valor inicial de la pila")
        sp.add_argument("--name", help="fichero dentro de un .dsk/.cdt")
        sp.add_argument("--frames", type=int, default=frames,
                        help=f"frames de análisis dinámico (0 = solo estático; por defecto {frames})")
        sp.add_argument("--seed", type=int, default=1, help="semilla del guion de exploración")
        sp.add_argument("--rom", help="ROM de 48K del Spectrum (opcional, mejora el análisis)")
        sp.add_argument("--cpc-roms", help="directorio con cpc6128.rom para ejecutar el firmware")
        sp.add_argument("-q", "--quiet", action="store_true")

    sp = sub.add_parser("info", help="describe un fichero")
    common(sp)
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("analyze", help="analiza un juego y lista sus puntos calientes")
    common(sp)
    sp.add_argument("--html", help="genera un informe HTML")
    sp.add_argument("--json", help="vuelca los puntos calientes en JSON")
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("disasm", help="desensamblado reensamblable")
    common(sp, frames=200)
    sp.add_argument("-o", "--output")
    sp.add_argument("--start")
    sp.add_argument("--end")
    sp.set_defaults(func=cmd_disasm)

    sp = sub.add_parser("port", help="porta un juego a la otra máquina")
    common(sp)
    sp.add_argument("--to", choices=["cpc", "zx"], help="máquina de destino (por defecto la otra)")
    sp.add_argument("-o", "--output", help="directorio de salida")
    sp.add_argument("--config", help="port.json con opciones (se genera en cada port)")
    sp.add_argument("--mono", action="store_true", help="monocromo (más fiel a la forma, sin color)")
    sp.add_argument("--refresh", type=int, help="líneas de refresco de fondo por frame (0-5)")
    sp.add_argument("--keys", help="teclas extra, p.ej. Q=JOYUP,A=JOYDOWN,SPACE=FIRE1")
    sp.add_argument("--exclude", help="direcciones que no se deben parchear (coma)")
    sp.add_argument("--palette", help="4 colores del firmware CPC para las plumas 0-3")
    sp.add_argument("--test-frames", type=int, default=150, help="frames de la prueba final")
    sp.set_defaults(func=cmd_port)

    sp = sub.add_parser("run", help="ejecuta en la máquina emulada y guarda una captura")
    common(sp)
    sp.add_argument("--png")
    sp.add_argument("--keys", help="teclas por intervalo de frames: 20-60:P,60-90:A+SPACE")
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("asm", help="ensambla un fichero .asm")
    sp.add_argument("file")
    sp.add_argument("-o", "--output")
    sp.set_defaults(func=cmd_asm)

    sp = sub.add_parser("scr", help="convierte una pantalla .scr de Spectrum a PNG / CPC")
    sp.add_argument("file")
    sp.add_argument("-o", "--output")
    sp.add_argument("--cpc", help="genera también la pantalla en formato CPC (binario AMSDOS)")
    sp.set_defaults(func=cmd_scr)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except Exception as e:  # noqa: BLE001
        if os.environ.get("ZXCPC_DEBUG"):
            raise
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
