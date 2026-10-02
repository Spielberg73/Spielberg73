"""Reproductor web: el CPC en JavaScript da exactamente lo mismo que el de Python."""
import hashlib
import json
import shutil
import subprocess

import pytest

from zxcpc.machines.cpc import CPC
from zxcpc.formats.cpc import write_cpc_sna, read_cpc_sna

NODE = shutil.which("node")


@pytest.fixture(scope="module")
def zx_port(built):
    from zxcpc.program import load_program
    from zxcpc.analysis.dynamic import run_dynamic
    from zxcpc.analysis.static import analyze
    from zxcpc.port.zx2cpc import port_zx_to_cpc, PortOptions
    path, sy, start = built["zxgame"]
    p = load_program(path, platform="zx", load_addr=start, exec_addr=start)
    an = analyze(p, run_dynamic(p, frames=150))
    return p, an, port_zx_to_cpc(an, PortOptions(refresh_lines=2)), sy

JS = r"""
const Z = require(process.argv[2]);
const fs = require('fs'), crypto = require('crypto');
const m = new Z.CPC(null, 128);
m.loadSna(fs.readFileSync(process.argv[3]));
const out = [];
for (let f = 0; f < 120; f++) {
  m.keys.fill(0xFF);
  if (f >= 20 && f < 60) m.press('P');
  if (f >= 60 && f < 90) m.press('A');
  m.runFrame();
  if ((f + 1) % 30 === 0) {
    const h = crypto.createHash('md5'); m.pages.forEach(p => h.update(p));
    out.push([h.digest('hex'), ['AF','BC','DE','HL','IX','IY','SP','PC'].map(n => m.cpu.getPair(n)), m.cpu.cycles]);
  }
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="hace falta node")
def test_cpc_js_igual_que_python(zx_port, tmp_path):
    import os
    import zxcpc.web
    _p, _an, res, _sy = zx_port
    sna = tmp_path / "g.sna"
    sna.write_bytes(write_cpc_sna(res.state))
    script = tmp_path / "run.js"
    script.write_text(JS)
    js = os.path.join(os.path.dirname(zxcpc.web.__file__), "cpc.js")
    got = json.loads(subprocess.run([NODE, str(script), js, str(sna)], capture_output=True,
                                    text=True, check=True).stdout)
    c = CPC()
    c.load_state(read_cpc_sna(sna.read_bytes()))
    want = []
    for f in range(120):
        c.release_all()
        if 20 <= f < 60:
            c.press("P")
        elif 60 <= f < 90:
            c.press("A")
        c.run_frame()
        if (f + 1) % 30 == 0:
            c.ram()
            h = hashlib.md5(b"".join(bytes(p) for p in c.pages)).hexdigest()
            want.append([h, [c.cpu.get_pair(k) for k in ("AF", "BC", "DE", "HL", "IX", "IY",
                                                          "SP", "PC")], c.cpu.cycles])
    assert got == want


def test_pagina_del_reproductor(zx_port):
    from zxcpc.web import build_player
    _p, _an, res, _sy = zx_port
    page = build_player(write_cpc_sna(res.state), "Juego <prueba>", "nota")
    assert page.startswith("<title>Juego &lt;prueba&gt;</title>")
    import re
    assert not re.search(r"\{\{[A-Z]+\}\}", page) and "class CPC" in page
    with pytest.raises(ValueError):
        build_player(b"nada", "x")
