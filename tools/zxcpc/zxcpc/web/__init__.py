"""Reproductor web: una página HTML con un CPC 6128 en JavaScript (cpc.js) y un
snapshot .SNA dentro, para jugar a un port en el navegador sin instalar nada."""

from __future__ import annotations

import base64
import html
import json
import os

_DIR = os.path.dirname(__file__)

# teclas en pantalla (móviles) por defecto: las de los menús y unas de dirección
DEFAULT_PAD = [("ESPACIO", "SPACE"), ("1", "1"), ("0", "0"), ("Y", "Y"), ("N", "N"),
               ("O", "O"), ("P", "P"), ("Q", "Q"), ("A", "A"), ("M", "M"), ("INTRO", "RETURN")]


def build_player(sna: bytes, title: str, note: str = "", pad=None) -> str:
    """Página del reproductor con ``sna`` dentro (un SNA de CPC sin comprimir)."""
    if not sna.startswith(b"MV - SNA"):
        raise ValueError("el reproductor web necesita un .sna de CPC")
    size_kb = sna[0x6B] | (sna[0x6C] << 8)
    if size_kb == 0:
        raise ValueError("SNA comprimido (v3): genera el SNA con zxcpc")
    with open(os.path.join(_DIR, "player.html"), encoding="utf-8") as f:
        page = f.read()
    with open(os.path.join(_DIR, "cpc.js"), encoding="utf-8") as f:
        js = f.read()
    keys = pad if pad is not None else DEFAULT_PAD
    for k, v in {
        "{{TITLE}}": html.escape(title),
        "{{RAMKB}}": str(max(128, size_kb)),
        "{{NOTE}}": html.escape(note),
        "{{PAD}}": json.dumps([list(p) for p in keys]),
        "{{SNA}}": base64.b64encode(sna).decode(),
    }.items():
        page = page.replace(k, v)
    return page.replace("{{CPCJS}}", js.replace("</script", "<\\/script"))
