"""Prueba del preview y del editor en un navegador de verdad (opcional).

Abre el preview generado en Chromium y comprueba, con raton y teclado, que se
juega, que suena y que el editor pinta, edita propiedades, valida, exporta y
guarda. Deja capturas para poder mirarlas.

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


def comprobar(preview: str, capturas: str = "capturas") -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright no esta instalado: se salta la prueba de navegador")
        return 0

    os.makedirs(capturas, exist_ok=True)
    fallos = []

    def exigir(condicion, texto):
        if not condicion:
            fallos.append(texto)

    with sync_playwright() as pw:
        navegador = _lanzar(pw)
        pagina = navegador.new_page(viewport={"width": 1280, "height": 1100})
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        def _console(mensaje):
            # los fallos de red (por ejemplo, las fuentes de Google sin conexion)
            # no son errores del preview
            if mensaje.type == "error" and "Failed to load resource" not in mensaje.text:
                errores.append("console: " + mensaje.text)

        pagina.on("console", _console)
        pagina.goto("file://" + os.path.abspath(preview))
        pagina.wait_for_timeout(700)

        # ---------------------------------------------------------- jugar
        pagina.locator("#pantalla").click()
        pagina.keyboard.press("Enter")
        pagina.keyboard.down("ArrowRight")
        pagina.wait_for_timeout(1500)
        pagina.keyboard.up("ArrowRight")
        estado = pagina.evaluate("""() => { const w = window.NeoPlat.world;
            return { estado: w.state, x: w.player.x >> 8, musica: w.level.music }; }""")
        print("jugando:", json.dumps(estado))
        exigir(estado["estado"] in (1, 2, 3), "el juego no llega a estado de partida")
        exigir(estado["x"] > 10, "el jugador no avanza")
        pagina.locator("#pantalla").screenshot(path=os.path.join(capturas, "juego.png"))

        # La ganancia se mira durante medio segundo y se coge la mayor: en un
        # instante suelto se puede caer justo en un silencio de la melodia, y
        # entonces el cero no significa que no suene.
        audio = pagina.evaluate("""() => new Promise(listo => {
            const a = window.NeoPlat.audio;
            let pico = 0, vueltas = 0;
            const reloj = setInterval(() => {
              pico = Math.max(pico, ...a.canales.map(c => c.gain.gain.value));
              if (++vueltas >= 25) {
                clearInterval(reloj);
                listo({ contexto: !!a.ctx, canales: a.canales.length,
                        pistas: a.pistas.length, ganancia: pico });
              }
            }, 20);
          })""")
        print("audio:", json.dumps(audio))
        exigir(audio["contexto"] and audio["canales"] == 3, "el audio no ha arrancado")
        exigir(audio["ganancia"] > 0, "los osciladores no estan sonando al jugar")

        # --------------------------------------------------------- editor
        pagina.click("#modo")
        pagina.wait_for_timeout(400)
        interfaz = pagina.evaluate("""() => ({
            activo: window.NeoPlat.editor.activo,
            ancho: document.querySelector('#pantalla').width,
            herramientas: document.querySelectorAll('#herramientas button').length,
            paleta: document.querySelectorAll('#ed-paleta button').length,
            pestanas: document.querySelectorAll('#pestanas button').length })""")
        print("editor:", json.dumps(interfaz))
        exigir(interfaz["activo"], "no entra en modo edicion")
        # en el editor el bucle no llama a tick(): si nadie calla los
        # osciladores se quedan sonando la ultima nota para siempre
        pagina.wait_for_timeout(300)
        callado = pagina.evaluate(
            "() => Math.max(...window.NeoPlat.audio.canales.map(c => c.gain.gain.value))")
        exigir(callado < 0.001,
               "el sonido se queda sonando al pasar al editor (ganancia %.4f)" % callado)
        exigir(interfaz["ancho"] == 480, "el lienzo no se agranda al editar")
        exigir(interfaz["herramientas"] >= 6, "faltan herramientas")
        exigir(interfaz["paleta"] >= 5, "la paleta sale vacia")

        def punto(tx, ty):
            """Centro de una casilla en pantalla. Se vuelve a medir el lienzo
            cada vez: abrir paneles puede mover la pagina."""
            pagina.locator("#pantalla").scroll_into_view_if_needed()
            caja = pagina.locator("#pantalla").bounding_box()
            escala = caja["width"] / 480.0
            est = pagina.evaluate("""() => { const e = window.NeoPlat.editor;
                return { cx: e.camX, cy: e.camY, z: e.zoom }; }""")
            return (caja["x"] + (tx * 16 + 8 - est["cx"]) * est["z"] * escala,
                    caja["y"] + (ty * 16 + 8 - est["cy"]) * est["z"] * escala)

        # pintar arrastrando: un trazo = un paso de deshacer
        pagina.evaluate("""() => { const e = window.NeoPlat.editor;
            e.herramienta = 'lapiz'; e.simbolo = '#'; e.camX = 0; e.camY = 64; }""")
        x0, y0 = punto(3, 8)
        pagina.mouse.move(x0, y0)
        pagina.mouse.down()
        for i in range(3, 10):
            xx, yy = punto(i, 8)
            pagina.mouse.move(xx, yy)
        pagina.mouse.up()
        pagina.wait_for_timeout(150)
        trazo = pagina.evaluate("""() => { const e = window.NeoPlat.editor;
            return { fila: e.modelo.filas[e.nivel][8], pasos: e.historial.length }; }""")
        exigir(trazo["fila"][3:10] == "#######", "el trazo no pinta seguido")
        exigir(trazo["pasos"] == 1, "un trazo deberia ser un solo paso de deshacer")

        pagina.click("#ed-deshacer")
        pagina.wait_for_timeout(120)
        exigir("#" not in pagina.evaluate(
            "() => window.NeoPlat.editor.modelo.filas[window.NeoPlat.editor.nivel][8]")[3:10],
            "deshacer no funciona")
        pagina.click("#ed-rehacer")
        pagina.wait_for_timeout(120)
        exigir(pagina.evaluate(
            "() => window.NeoPlat.editor.modelo.filas[window.NeoPlat.editor.nivel][8]")[3:10]
            == "#######", "rehacer no funciona")

        # rectangulo
        pagina.evaluate("() => { window.NeoPlat.editor.herramienta = 'rect'; }")
        ax, ay = punto(12, 6)
        bx, by = punto(16, 9)
        pagina.mouse.move(ax, ay)
        pagina.mouse.down()
        pagina.mouse.move(bx, by)
        pagina.mouse.up()
        pagina.wait_for_timeout(150)
        filas = pagina.evaluate("() => window.NeoPlat.editor.modelo.filas[window.NeoPlat.editor.nivel]")
        exigir(filas[6][12:17] == "#####", "el rectangulo no se pinta")

        # propiedades en vivo
        pagina.click("#pestanas button[data-panel=juego]")
        pagina.wait_for_timeout(200)
        pagina.evaluate("() => window.NeoPlat.editor.ponerPropiedad('jugador','salto',6)")
        pagina.wait_for_timeout(150)
        fisica = pagina.evaluate("""() => ({ modelo: window.NeoPlat.editor.modelo.jugador.salto,
            motor: window.NeoPlat.data.player.jump })""")
        exigir(fisica["motor"] == 1536, "la fisica editada no llega al motor: %s" % fisica)

        # niveles
        pagina.click("#pestanas button[data-panel=nivel]")
        pagina.wait_for_timeout(150)
        pagina.click("#ed-nuevo")
        pagina.wait_for_timeout(250)
        niveles = pagina.evaluate("""() => ({ modelo: window.NeoPlat.editor.modelo.filas.length,
            data: window.NeoPlat.data.levels.length })""")
        exigir(niveles["modelo"] == niveles["data"], "los niveles no cuadran: %s" % niveles)

        # revisar y bot
        pagina.evaluate("() => window.NeoPlat.editor.cambiarNivel(0)")
        pagina.click("#pestanas button[data-panel=revisar]")
        pagina.wait_for_timeout(200)
        pagina.click("#ed-bot")
        pagina.wait_for_timeout(3000)
        mensaje = pagina.evaluate("() => window.NeoPlat.editor.mensaje")
        print("bot:", mensaje)
        exigir("bot" in mensaje, "el bot no responde")

        # crear un enemigo nuevo, dibujandolo
        pagina.click("#pestanas button[data-panel=actores]")
        pagina.wait_for_timeout(200)
        pagina.click("#ed-nuevo-enemigo")
        pagina.wait_for_timeout(300)
        lienzo = pagina.evaluate("""() => ({
            visible: document.getElementById('pixeles').classList.contains('visible'),
            colores: document.querySelectorAll('#pixel-colores button').length,
            frames: document.querySelectorAll('#pixel-frames canvas').length })""")
        exigir(lienzo["visible"] and lienzo["colores"] == 16,
               "el editor de dibujos no aparece: %s" % lienzo)

        pagina.locator("#pixel-canvas").scroll_into_view_if_needed()
        cajaPixel = pagina.locator("#pixel-canvas").bounding_box()
        pasoPixel = cajaPixel["width"] / 16.0
        pagina.evaluate("() => { window.NeoPlat.pixel().color = 8; }")
        pagina.mouse.move(cajaPixel["x"] + pasoPixel * 3.5, cajaPixel["y"] + pasoPixel * 3.5)
        pagina.mouse.down()
        for i in range(3, 12):
            pagina.mouse.move(cajaPixel["x"] + pasoPixel * (i + 0.5),
                              cajaPixel["y"] + pasoPixel * 3.5)
        pagina.mouse.up()
        pagina.wait_for_timeout(200)
        pintado = pagina.evaluate(
            "() => { let n = 0; for (const v of window.NeoPlat.pixel().pixeles) if (v === 8) n++;"
            " return n; }")
        exigir(pintado >= 8, "dibujar con el raton no pinta (%s)" % pintado)

        pagina.fill("#creador-campos input[type=text]", "cangrejo")
        pagina.click("#creador-crear")
        pagina.wait_for_timeout(500)
        creado = pagina.evaluate("""() => { const e = window.NeoPlat.editor;
            const ultimo = e.modelo.enemigos[e.modelo.enemigos.length - 1];
            return { nombre: ultimo.nombre, simbolo: ultimo.simbolo,
                     dibujo: (ultimo.imagen || '').slice(0, 15),
                     enPaleta: Array.from(document.querySelectorAll('#ed-paleta button'))
                        .some(b => b.title.indexOf('cangrejo') >= 0) }; }""")
        print("enemigo nuevo:", json.dumps(creado))
        exigir(creado["nombre"] == "cangrejo", "no se ha creado el enemigo")
        exigir(creado["dibujo"].startswith("data:image"), "no se ha guardado el dibujo")
        exigir(creado["enPaleta"], "el enemigo nuevo no sale en la paleta")

        # se pinta en el mapa y aparece al jugar
        pagina.click("#pestanas button[data-panel=mapa]")
        pagina.evaluate("""() => { const e = window.NeoPlat.editor;
            e.herramienta = 'lapiz'; e.empezarCambio(); e.pintar(20, 12, false);
            e.terminarCambio(); }""")
        pagina.wait_for_timeout(200)
        pagina.click("#ed-jugar")
        pagina.wait_for_timeout(500)
        enJuego = pagina.evaluate("""() => { const w = window.NeoPlat.world;
            const d = window.NeoPlat.data;
            return w.entities.some(e => e.active && e.kind === 0 &&
                                        e.def === d.enemies.length - 1); }""")
        exigir(enJuego, "el enemigo nuevo no aparece en el juego")
        pagina.click("#modo")
        pagina.wait_for_timeout(300)

        # exportar
        pagina.click("#pestanas button[data-panel=yaml]")
        pagina.wait_for_timeout(300)
        yaml_texto = pagina.evaluate("() => document.getElementById('ed-texto').value")
        exigir("jugador:" in yaml_texto and "mapa: |" in yaml_texto,
               "el yaml exportado no parece completo")
        exigir("salto: 6" in yaml_texto, "el yaml no recoge la fisica editada")
        exigir("cangrejo:" in yaml_texto, "el yaml no lleva el enemigo nuevo")
        pendientes = pagina.evaluate("() => window.NeoPlat.editor.imagenesPendientes()")
        exigir(len(pendientes) == 1 and pendientes[0]["ruta"] == "graficos/cangrejo.png",
               "no queda pendiente el PNG del enemigo nuevo: %s" % pendientes)
        exigir("descargar graficos/cangrejo.png" in pagina.inner_text("#pendientes"),
               "no ofrece descargar el dibujo nuevo")
        pagina.screenshot(path=os.path.join(capturas, "editor.png"))

        # guardado automatico
        guardado = pagina.evaluate(
            "() => { try { return Object.keys(localStorage).some(k => k.indexOf('neoplat:') === 0); }"
            " catch (e) { return 'sin acceso'; } }")
        exigir(guardado is True, "no guarda los cambios en el navegador: %s" % guardado)

        # la pestana de generar la ROM
        pagina.click("#pestanas button[data-panel=rom]")
        pagina.wait_for_timeout(200)
        panel = pagina.evaluate("""() => ({
            solo: [...document.querySelectorAll('.panel')]
                    .filter(e => getComputedStyle(e).display !== 'none')
                    .map(e => e.id),
            maquinas: [...document.querySelectorAll('#rom-sistema option')].map(o => o.value),
            servidor: window.NeoPlat.rom.disponible,
            boton: document.querySelector('#rom-generar').disabled })""")
        print("rom:", json.dumps(panel))
        exigir(panel["solo"] == ["panel-rom"],
               "la pestana ROM deja otros paneles a la vista: %s" % panel["solo"])
        exigir(len(panel["maquinas"]) == 4,
               "faltan maquinas donde elegir: %s" % panel["maquinas"])
        # el boton dice lo que va a salir: no todas las maquinas hacen una ROM
        etiquetas = {}
        for maquina in panel["maquinas"]:
            pagina.select_option("#rom-sistema", maquina)
            pagina.wait_for_timeout(60)
            etiquetas[maquina] = pagina.text_content("#rom-generar")
        print("rom, etiquetas:", json.dumps(etiquetas))
        exigir(etiquetas.get("amiga") == "generar el disquete",
               "en Amiga el boton no dice disquete: %r" % etiquetas.get("amiga"))
        exigir(etiquetas.get("neogeo") == "generar la ROM",
               "en Neo Geo el boton no dice ROM: %r" % etiquetas.get("neogeo"))
        exigir(etiquetas.get("jaguar") == "generar el cartucho",
               "en Jaguar el boton no dice cartucho: %r" % etiquetas.get("jaguar"))
        exigir(len(set(etiquetas.values())) == 3,
               "el boton deberia decir tres cosas distintas (Mega Drive y Jaguar "
               "hacen las dos un cartucho): %s" % etiquetas)
        # aqui el preview se abre como file://, asi que no hay ngplat con quien
        # hablar: el boton tiene que estar apagado y decir por que
        exigir(not panel["servidor"], "cree que hay servidor abriendo un archivo")
        exigir(panel["boton"], "ofrece generar la ROM sin servidor detras")
        exigir("ngplat probar" in pagina.inner_text("#rom-ayuda"),
               "no explica como levantar el servidor")

        # volver a jugar con lo editado
        pagina.click("#pestanas button[data-panel=mapa]")
        pagina.click("#ed-jugar")
        pagina.wait_for_timeout(400)
        vuelta = pagina.evaluate("""() => ({ estado: window.NeoPlat.world.state,
            editando: window.NeoPlat.editor.activo,
            ancho: document.querySelector('#pantalla').width })""")
        exigir(vuelta["estado"] == 1 and not vuelta["editando"],
               "no vuelve al juego tras editar")
        exigir(vuelta["ancho"] == 320, "el lienzo no vuelve a 320 al jugar")

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
