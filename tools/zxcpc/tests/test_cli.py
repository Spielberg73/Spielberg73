"""La línea de órdenes, de principio a fin."""
import json
import os

from zxcpc.cli import main
from zxcpc.z80.asm import assemble_file


def test_asm_e_info(built, tmp_path, capsys):
    from conftest import data
    out = tmp_path / "g.bin"
    assert main(["asm", data("zxgame.asm"), "-o", str(out)]) == 0
    assert out.read_bytes() == open(built["zxgame"][0], "rb").read()
    assert main(["info", str(out), "--platform", "zx", "--load", "0x8000"]) == 0
    assert "8000" in capsys.readouterr().out.upper()


def test_disasm_reensamblable(built, tmp_path):
    path, sy, start = built["zxgame"]
    lst = tmp_path / "g.asm"
    assert main(["disasm", path, "--platform", "zx", "--load", hex(start), "--frames", "60",
                 "-q", "-o", str(lst)]) == 0
    r = assemble_file(str(lst))
    orig = open(path, "rb").read()
    img = r.image()
    off = start - r.start
    assert img[off:off + len(orig)] == orig


def test_analyze_html_json(built, tmp_path):
    path, sy, start = built["cpcgame_hw"]
    html, js = tmp_path / "i.html", tmp_path / "h.json"
    assert main(["analyze", path, "--platform", "cpc", "--load", hex(start), "--frames", "60",
                 "-q", "--html", str(html), "--json", str(js)]) == 0
    assert "<html" in html.read_text(encoding="utf-8").lower()
    kinds = {h["kind"] for h in json.loads(js.read_text(encoding="utf-8"))}
    assert "ga_out" in kinds and "ppi_io" in kinds


def test_port_zx_a_cpc(built, tmp_path):
    path, sy, start = built["zxgame"]
    out = tmp_path / "port"
    assert main(["port", path, "--platform", "zx", "--load", hex(start), "--frames", "100",
                 "--test-frames", "30", "-q", "-o", str(out)]) == 0
    names = set(os.listdir(out))
    for f in ("hal.asm", "parches.json", "port.json", "informe.html"):
        assert f in names, f
    assert any(n.endswith("_cpc.sna") for n in names)
    assert any(n.endswith("_cpc.dsk") for n in names)
    # el port.json generado sirve de configuración para repetir el port
    out2 = tmp_path / "port2"
    assert main(["port", path, "--platform", "zx", "--load", hex(start), "--frames", "100",
                 "--test-frames", "10", "-q", "-o", str(out2),
                 "--config", str(out / "port.json")]) == 0


def test_port_cpc_a_zx(built, tmp_path):
    path, sy, start = built["cpcgame_hw"]
    out = tmp_path / "port"
    assert main(["port", path, "--platform", "cpc", "--load", hex(start), "--frames", "100",
                 "--test-frames", "30", "-q", "-o", str(out)]) == 0
    names = set(os.listdir(out))
    assert any(n.endswith("_zx.z80") for n in names)
    assert "hal.asm" in names


def test_run_png(built, tmp_path):
    path, sy, start = built["zxgame"]
    png = tmp_path / "s.png"
    assert main(["run", path, "--platform", "zx", "--load", hex(start), "--frames", "20",
                 "--png", str(png), "--keys", "5-15:P"]) == 0
    assert png.read_bytes()[:4] == b"\x89PNG"
