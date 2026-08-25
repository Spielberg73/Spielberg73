"""Prueba del preview en un navegador de verdad (opcional).

Abre el preview generado en Chromium, juega unos frames, comprueba que no hay
errores de JavaScript, que el audio arranca y que el editor pinta y exporta.
Guarda capturas para poder mirarlas.

Necesita Playwright y un Chromium; si no estan, se salta:

    pip install playwright && playwright install chromium
    python3 tests/navegador.py ruta/al/preview.html [carpeta_de_capturas]
"""

from __future__ import annotations

import json
import os
import sys

CHROMIUM_POSIBLES = [
    os.environ.get("NEOPLAT_CHROMIUM", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
]


def _lanzar(pw):
    for ruta in CHROMIUM_POSIBLES:
        if ruta and os.path.isfile(ruta):
            return pw.chromium.launch(args=["--no-sandbox"], executable_path=ruta)
    return pw.chromium.launch(args=["--no-sandbox"])


def comprobar(preview: str, capturas: str = ".") -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright no esta instalado: se salta la prueba de navegador")
        return 0

    os.makedirs(capturas, exist_ok=True)
    fallos = []
    with sync_playwright() as pw:
        navegador = _lanzar(pw)
        pagina = navegador.new_page(viewport={"width": 1200, "height": 1000})
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        pagina.on("console",
                  lambda m: errores.append("console: " + m.text) if m.type == "error" else None)
        pagina.goto("file://" + os.path.abspath(preview))
        pagina.wait_for_timeout(700)

        # --- jugar
        pagina.locator("#pantalla").click()
        pagina.keyboard.press("Enter")
        pagina.keyboard.down("ArrowRight")
        pagina.wait_for_timeout(1500)
        pagina.keyboard.up("ArrowRight")
        estado = pagina.evaluate("""() => { const w = window.NeoPlat.world;
            return { estado: w.state, x: w.player.x >> 8, camX: w.camX,
                     musica: w.level.music }; }""")
        print("jugando:", json.dumps(estado))
        if estado["estado"] not in (1, 2, 3):
            fallos.append("el juego no llega a estado de partida")
        if estado["x"] <= 10:
            fallos.append("el jugador no avanza")
        pagina.locator("#pantalla").screenshot(path=os.path.join(capturas, "juego.png"))

        # --- audio
        audio = pagina.evaluate("""() => { const a = window.NeoPlat.audio;
            return { contexto: !!a.ctx, canales: a.canales.length, pistas: a.pistas.length }; }""")
        print("audio:", json.dumps(audio))
        if not audio["contexto"] or audio["canales"] != 3:
            fallos.append("el audio no ha arrancado")

        # --- editor
        pagina.click("#modo")
        pagina.wait_for_timeout(300)
        caja = pagina.locator("#pantalla").bounding_box()
        escala = caja["width"] / 320.0
        pagina.evaluate("() => { window.NeoPlat.editor.herramienta = '#'; }")
        pagina.mouse.move(caja["x"] + 60 * escala, caja["y"] + 60 * escala)
        pagina.mouse.down()
        for i in range(60, 160, 8):
            pagina.mouse.move(caja["x"] + i * escala, caja["y"] + 60 * escala)
        pagina.mouse.up()
        pagina.wait_for_timeout(200)
        pintado = pagina.evaluate("""() => { const e = window.NeoPlat.editor;
            return { cambios: e.historial.length, botones: document.querySelectorAll('#ed-paleta button').length }; }""")
        print("editor:", json.dumps(pintado))
        if pintado["cambios"] < 3:
            fallos.append("pintar arrastrando no cambia el mapa")
        if pintado["botones"] < 5:
            fallos.append("la paleta del editor sale vacia")
        pagina.screenshot(path=os.path.join(capturas, "editor.png"))

        # --- exportar y volver a jugar
        pagina.click("#ed-exportar")
        pagina.wait_for_timeout(200)
        yaml_texto = pagina.evaluate("() => document.getElementById('ed-texto').value")
        if "jugador:" not in yaml_texto or "mapa: |" not in yaml_texto:
            fallos.append("el yaml exportado no parece completo")
        pagina.click("#ed-jugar")
        pagina.wait_for_timeout(400)
        vuelta = pagina.evaluate("""() => { const w = window.NeoPlat.world;
            return { estado: w.state, celdas: w.level.cells.length }; }""")
        print("tras editar:", json.dumps(vuelta))
        if vuelta["estado"] != 1:
            fallos.append("no vuelve al juego despues de editar")

        if errores:
            fallos.append("errores de JavaScript: %s" % errores[:3])
        navegador.close()

    if fallos:
        for fallo in fallos:
            print("FALLO:", fallo)
        return 1
    print("preview, audio y editor funcionan en el navegador")
    return 0


if __name__ == "__main__":
    preview = sys.argv[1] if len(sys.argv) > 1 else "examples/bosque-magico/preview.html"
    destino = sys.argv[2] if len(sys.argv) > 2 else "capturas"
    raise SystemExit(comprobar(preview, destino))
