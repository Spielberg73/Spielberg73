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


def _png_de_prueba(ancho, alto):
    """Un PNG de colores planos, para probar la importacion desde el disco."""
    import struct
    import zlib
    filas = b""
    for y in range(alto):
        filas += b"\0"
        for x in range(ancho):
            filas += bytes((255 if (x // 8) % 2 else 40, (y * 8) % 256, 90, 255))

    def trozo(tipo, cuerpo):
        return (struct.pack(">I", len(cuerpo)) + tipo + cuerpo +
                struct.pack(">I", zlib.crc32(tipo + cuerpo) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(filas))
            + trozo(b"IEND", b""))


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
            return { estado: w.state, x: w.players[0].x >> 8, musica: w.level.music }; }""")
        print("jugando:", json.dumps(estado))
        exigir(estado["estado"] in (1, 2, 3), "el juego no llega a estado de partida")
        exigir(estado["x"] > 10, "el jugador no avanza")
        pagina.locator("#pantalla").screenshot(path=os.path.join(capturas, "juego.png"))

        # El ataque: pulsar X saca un proyectil a la lista de entidades. Sin
        # esto, que el boton llegue al motor no lo comprueba nadie desde el
        # navegador.
        antes = pagina.evaluate("""() => {
            const w = window.NeoPlat.world;
            let n = 0;
            for (let i = 0; i < w.entityCount; i++)
              if (w.entities[i].active && w.entities[i].kind === 2) n++;
            return { balas: n, ataque: !!window.NeoPlat.data.player.attack.kind }; }""")
        exigir(antes["ataque"], "el proyecto de ejemplo ya no trae ataque")
        # se reinicia antes: despues de un rato corriendo solo, el jugador
        # puede estar muriendose, y ahi no se dispara
        pagina.keyboard.press("r")
        pagina.wait_for_timeout(150)
        pagina.keyboard.press("Enter")
        pagina.wait_for_timeout(250)
        pagina.keyboard.down("x")
        pagina.wait_for_timeout(150)
        pagina.keyboard.up("x")
        disparos = pagina.evaluate("""() => {
            const w = window.NeoPlat.world;
            let n = 0, def = null;
            for (let i = 0; i < w.entityCount; i++) {
              const e = w.entities[i];
              if (e.active && e.kind === 2) { n++; def = w.entityDef(e).actor; }
            }
            return { balas: n, hoja: def ? def.sheet : "" }; }""")
        print("disparo:", json.dumps(disparos))
        exigir(disparos["balas"] > antes["balas"], "pulsar X no dispara")
        exigir(disparos["hoja"] == "attack",
               "el proyectil no usa su propio dibujo: %r" % disparos["hoja"])

        # Las llaves: el primer nivel del ejemplo pide una, y el motor del
        # navegador tiene que verla igual que el de C.
        llaves = pagina.evaluate("""() => {
            const w = window.NeoPlat.world;
            return { piden: w.level.keys_needed || 0, tengo: w.keys }; }""")
        print("llaves:", json.dumps(llaves))
        exigir(llaves["piden"] > 0, "el ejemplo ya no cierra la meta con llave")

        # Los candelabros y el arma secundaria: se rompe uno con el ataque y
        # sale lo que lleva dentro, que es el bucle entero.
        candelabro = pagina.evaluate("""() => {
            const w = window.NeoPlat.world;
            const cuantos = (k) => {
              let n = 0;
              for (let i = 0; i < w.entityCount; i++)
                if (w.entities[i].active && w.entities[i].kind === k) n++;
              return n;
            };
            const antes = { velas: cuantos(4), objetos: cuantos(1) };
            // se le pega a todo lo que se pueda durante un rato
            for (let i = 0; i < 400; i++) w.step(i % 20 === 0 ? 32 : 2, 0);
            return { antes: antes, velas: cuantos(4),
                     hayArma: !!(w.data.player.sub && w.data.player.sub.kind) };
        }""")
        print("candelabros:", json.dumps(candelabro))
        exigir(candelabro["antes"]["velas"] > 0,
               "el ejemplo ya no trae candelabros")
        exigir(candelabro["velas"] < candelabro["antes"]["velas"],
               "pegando no se rompe ningun candelabro")
        exigir(candelabro["hayArma"], "el ejemplo ya no trae arma secundaria")
        pagina.keyboard.press("r")
        pagina.wait_for_timeout(150)
        pagina.keyboard.press("Enter")
        pagina.wait_for_timeout(250)

        # La plataforma movil vive en el segundo nivel: se carga y se mira que
        # este ahi y que se mueva sola.
        tablon = pagina.evaluate("""async () => {
            const w = window.NeoPlat.world;
            w.loadLevel(1);
            let e = null;
            for (let i = 0; i < w.entityCount; i++)
              if (w.entities[i].active && w.entities[i].kind === 3) e = w.entities[i];
            if (!e) return { hay: false };
            const antes = e.x;
            for (let i = 0; i < 60; i++) w.step(0, 0);
            return { hay: true, movida: e.x !== antes, hoja: w.entityDef(e).actor.sheet };
        }""")
        print("plataforma:", json.dumps(tablon))
        exigir(tablon["hay"], "el ejemplo ya no trae plataforma movil")
        exigir(tablon["movida"], "la plataforma movil no se mueve")
        exigir(tablon["hoja"].startswith("plat"),
               "la plataforma no usa su propio dibujo: %r" % tablon["hoja"])
        pagina.keyboard.press("r")
        pagina.wait_for_timeout(150)
        pagina.keyboard.press("Enter")
        pagina.wait_for_timeout(250)

        # A un jugador, WASD tiene que seguir valiendo como las flechas: a dos
        # pasa a ser el mando del segundo, y es facil llevarselo por delante.
        pagina.keyboard.down("a")
        pagina.wait_for_timeout(600)
        pagina.keyboard.up("a")
        conWasd = pagina.evaluate("() => window.NeoPlat.world.players[0].x >> 8")
        exigir(conWasd < estado["x"],
               "con un jugador, la A ya no mueve: %d -> %d" % (estado["x"], conWasd))

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

        # Las muestras digitales: el navegador las toca tal cual, descodificando
        # el base64 que trae DATA. Si no llegaran, el efecto sonaria con notas y
        # no habria forma de notarlo mirando la pantalla.
        pcm = pagina.evaluate("""() => {
            const a = window.NeoPlat.audio;
            const d = window.NeoPlat.data.sonido.muestras || {};
            const nombres = Object.keys(d);
            const buffers = nombres.filter(n => a.muestras[n]);
            const primera = nombres.length ? a.muestras[nombres[0]] : null;
            return { nombres: nombres, listas: buffers.length,
                     ritmo: primera ? primera.sampleRate : 0,
                     largo: primera ? primera.length : 0 }; }""")
        print("muestras:", json.dumps(pcm))
        exigir(len(pcm["nombres"]) >= 2,
               "el preview no trae las muestras del proyecto: %s" % pcm["nombres"])
        exigir(pcm["listas"] == len(pcm["nombres"]),
               "hay muestras que no se han podido descodificar")
        exigir(pcm["ritmo"] == 11025 and pcm["largo"] > 500,
               "la muestra no tiene la pinta que deberia: %s" % json.dumps(pcm))
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

        # --- el editor de dibujos: abrir lo que ya existe y retocarlo -----
        pagina.click("#pestanas button[data-panel=dibujos]")
        pagina.wait_for_timeout(300)
        lista = pagina.evaluate("""() => Array.from(
            document.querySelectorAll('#dib-lista button')).map(b => b.textContent.trim())""")
        print("dibujos:", json.dumps(lista))
        exigir(any(t.startswith("jugador") for t in lista), "no se puede abrir al jugador")
        exigir(any(t.startswith("tiles") for t in lista), "no se puede abrir el escenario")
        exigir(any(t.startswith("cielo") for t in lista), "no se pueden abrir los fondos")

        pagina.evaluate("() => window.NeoPlat.dibujos.abrir('player')")
        pagina.wait_for_timeout(300)
        abierto = pagina.evaluate("""() => { const d = window.NeoPlat.dibujos.estado();
            return { hoja: d.hoja, frames: d.lienzo.frames,
                     ancho: d.lienzo.ancho, vacio: d.lienzo.vacio(),
                     colores: d.lienzo.indicesUsados().length,
                     cuenta: document.getElementById('dib-cuenta').textContent }; }""")
        print("abierto:", json.dumps(abierto))
        exigir(abierto["hoja"] == "player" and abierto["frames"] == 6,
               "el jugador no se ha abierto entero: %s" % abierto)
        exigir(not abierto["vacio"], "el dibujo del jugador ha salido en blanco")
        exigir(abierto["colores"] > 1, "no ha sacado la paleta del PNG")
        exigir("de 15" in abierto["cuenta"],
               "no dice cuantos colores caben en la maquina: %s" % abierto["cuenta"])

        # dibujar una linea con el raton sobre el fotograma 3
        caja = pagina.locator("#dib-canvas").bounding_box()
        zoom = pagina.evaluate("() => window.NeoPlat.dibujos.estado().zoom")
        pagina.evaluate("() => { window.NeoPlat.dibujos.estado().herramienta = 'linea';"
                        " window.NeoPlat.dibujos.estado().color = 3; }")
        y = caja["y"] + zoom * 2.5
        pagina.mouse.move(caja["x"] + zoom * 33.5, y)
        pagina.mouse.down()
        pagina.mouse.move(caja["x"] + zoom * 44.5, y)
        pagina.mouse.up()
        pagina.wait_for_timeout(200)
        tras = pagina.evaluate("""() => { const d = window.NeoPlat.dibujos.estado();
            let n = 0;
            for (let x = 0; x < 16; x++) if (d.lienzo.coger(2, x, 2) === 3) n++;
            return { pintados: n, frame: d.frame, tocado: d.tocado }; }""")
        print("linea:", json.dumps(tras))
        exigir(tras["pintados"] >= 10, "la linea no ha llegado: %s" % tras)
        exigir(tras["frame"] == 2, "no ha entendido en que fotograma se pinta")

        # deshacer devuelve el dibujo a como estaba
        pagina.click("#dib-deshacer")
        pagina.wait_for_timeout(150)
        deshecho = pagina.evaluate("""() => { const d = window.NeoPlat.dibujos.estado();
            let n = 0;
            for (let x = 0; x < 16; x++) if (d.lienzo.coger(2, x, 2) === 3) n++;
            return n; }""")
        exigir(deshecho < tras["pintados"], "deshacer no ha hecho nada")

        # el PNG que sale mide lo que tiene que medir
        png = pagina.evaluate("() => window.NeoPlat.dibujos.png()")
        exigir(png.startswith("data:image/png;base64,"), "no sale un PNG")
        medidas = pagina.evaluate("""() => new Promise(listo => {
            const i = new Image();
            i.onload = () => listo([i.width, i.height]);
            i.src = window.NeoPlat.dibujos.png(); })""")
        print("png del jugador:", json.dumps(medidas))
        exigir(medidas == [96, 16], "el PNG no mide lo que la hoja: %s" % medidas)

        # --- copiar de un dibujo y pegarlo en otro ------------------------
        #
        # Los pixeles son indices de paleta, asi que pegarlos tal cual en otro
        # dibujo cambiaria los colores sin avisar: lo que se comprueba es que
        # el trozo llega **y** que el editor dice cuantos colores ha tenido que
        # aproximar.
        pagina.click("#dib-copiar")
        pagina.wait_for_timeout(120)
        copiado = pagina.evaluate("""() => { const p = window.NeoPlat.dibujos.estado().portapapeles;
            return p ? { ancho: p.ancho, alto: p.alto, paleta: p.paleta.length } : null; }""")
        print("copiado:", json.dumps(copiado))
        exigir(copiado and copiado["ancho"] == 16 and copiado["alto"] == 16,
               "copiar no ha guardado el fotograma: %s" % copiado)
        exigir(copiado and copiado["paleta"] == 15,
               "el trozo copiado no se lleva su paleta")

        pagina.evaluate("""() => { const d = window.NeoPlat.dibujos.estado();
            d.tocado = false; window.NeoPlat.dibujos.abrir('item0'); }""")
        pagina.wait_for_timeout(250)
        antes_pegar = pagina.evaluate(
            "() => window.NeoPlat.dibujos.estado().lienzo.indicesUsados().length")
        pagina.click("#dib-pegar")
        pagina.wait_for_timeout(200)
        pegado = pagina.evaluate("""() => { const d = window.NeoPlat.dibujos.estado();
            let n = 0;
            for (let y = 0; y < 16; y++)
              for (let x = 0; x < 16; x++) if (d.lienzo.coger(0, x, y)) n++;
            return { hoja: d.hoja, pintados: n, tocado: d.tocado,
                     aviso: document.getElementById('dib-aviso').textContent }; }""")
        print("pegado:", json.dumps(pegado))
        exigir(pegado["hoja"] == "item0", "no se ha cambiado de dibujo")
        exigir(pegado["pintados"] > 20,
               "el trozo pegado no ha llegado: %s" % pegado)
        exigir("pegado" in pegado["aviso"], "no dice que ha pegado: %r" % pegado["aviso"])
        exigir(antes_pegar >= 1, "la moneda estaba vacia y la prueba no vale")

        # --- un dibujo nuevo, que todavia no esta en el game.yaml ---------
        pagina.evaluate("() => { window.NeoPlat.dibujos.estado().tocado = false; }")
        pagina.click("#dib-nuevo")
        pagina.fill("#dib-nuevo-nombre", "chispa")
        pagina.fill("#dib-nuevo-ancho", "16")
        pagina.fill("#dib-nuevo-alto", "32")
        pagina.fill("#dib-nuevo-frames", "3")
        pagina.click("#dib-nuevo-crear")
        pagina.wait_for_timeout(300)
        nuevo = pagina.evaluate("""() => { const d = window.NeoPlat.dibujos.estado();
            return { hoja: d.hoja, ancho: d.lienzo.ancho, alto: d.lienzo.alto,
                     frames: d.lienzo.frames, vacio: d.lienzo.vacio(),
                     ruta: (window.NeoPlat.data.sheets[d.hoja] || {}).ruta,
                     enLista: Array.from(document.querySelectorAll('#dib-lista button'))
                        .some(b => b.textContent.indexOf('chispa') >= 0) }; }""")
        print("dibujo nuevo:", json.dumps(nuevo))
        exigir(nuevo["ancho"] == 16 and nuevo["alto"] == 32 and nuevo["frames"] == 3,
               "el dibujo nuevo no tiene el tamano pedido: %s" % nuevo)
        exigir(nuevo["vacio"], "el dibujo nuevo no empieza en blanco")
        exigir(nuevo["ruta"] == "graficos/chispa.png",
               "el dibujo nuevo no sabe donde se guarda: %s" % nuevo)
        exigir(nuevo["enLista"], "el dibujo nuevo no sale en la lista")

        # --- importar un PNG de fuera -------------------------------------
        #
        # Se importa el propio PNG del jugador (96x16, seis fotogramas de 16x16)
        # sobre un dibujo de 16x32: no cuadra por altura, asi que el editor
        # tiene que decirlo en vez de tragarselo.
        fuera = os.path.join(capturas, "importado.png")
        with open(fuera, "wb") as fh:
            fh.write(_png_de_prueba(64, 16))
        # dos copias con nombres distintos: el navegador no vuelve a avisar si
        # se le da dos veces el mismo archivo
        otra_vez = os.path.join(capturas, "importado2.png")
        with open(otra_vez, "wb") as fh:
            fh.write(_png_de_prueba(64, 16))
        pagina.set_input_files("#dib-archivo", fuera)
        pagina.wait_for_timeout(400)
        malo = pagina.evaluate("() => document.getElementById('dib-aviso').textContent")
        print("importar que no cuadra:", json.dumps(malo))
        exigir("hacen falta" in malo,
               "no avisa de que el PNG no cuadra: %r" % malo)

        # y ahora uno que si: 64x16 sobre el jugador, que son cuatro fotogramas
        pagina.evaluate("""() => { const d = window.NeoPlat.dibujos.estado();
            d.tocado = false; window.NeoPlat.dibujos.abrir('player'); }""")
        pagina.wait_for_timeout(250)
        pagina.set_input_files("#dib-archivo", otra_vez)
        pagina.wait_for_timeout(500)
        traido = pagina.evaluate("""() => { const d = window.NeoPlat.dibujos.estado();
            return { frames: d.lienzo.frames, porFila: d.lienzo.porFila,
                     ancho: d.lienzo.anchoHoja(), tocado: d.tocado,
                     usados: d.lienzo.indicesUsados().length,
                     aviso: document.getElementById('dib-aviso').textContent }; }""")
        print("importado:", json.dumps(traido))
        exigir(traido["frames"] == 4 and traido["ancho"] == 64,
               "la hoja no se ha adaptado a los cuatro fotogramas: %s" % traido)
        exigir(traido["usados"] >= 2, "el PNG importado no ha traido dibujo")
        exigir(traido["tocado"], "importar no marca el dibujo como sin guardar")

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
        exigir(len(panel["maquinas"]) == 5,
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
        exigir(etiquetas.get("atarist") == "generar el disquete",
               "en Atari ST el boton no dice disquete: %r" % etiquetas.get("atarist"))
        exigir(len(set(etiquetas.values())) == 3,
               "el boton deberia decir tres cosas distintas: cartucho (Mega Drive "
               "y Jaguar), disquete (Amiga y Atari ST) y ROM (Neo Geo): %s"
               % etiquetas)
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


def _preview_a_dos(carpeta: str) -> str:
    """Genera el preview de un proyecto con `jugadores: 2` y devuelve la ruta."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from comun import cargar_demo, proyecto_a_dos
    from ngplat.preview import write_preview
    proyecto = proyecto_a_dos(os.path.join(carpeta, "juego"))
    return write_preview(cargar_demo(proyecto),
                         os.path.join(carpeta, "preview.html"))


def comprobar_dos(capturas: str = "capturas") -> int:
    """El preview a dos jugadores: dos teclados, dos jugadores, dos marcadores.

    Es lo que no puede comprobar la paridad con el motor en C (que solo mira la
    simulacion) ni la prueba de emulador (que mira las maquinas): que las
    teclas del segundo llegan al segundo y las del primero al primero.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright no esta instalado: se salta la prueba de navegador")
        return 0
    import tempfile

    os.makedirs(capturas, exist_ok=True)
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    carpeta = tempfile.mkdtemp(prefix="neoplat-dos-web-")
    preview = _preview_a_dos(carpeta)
    with sync_playwright() as pw:
        navegador = _lanzar(pw)
        pagina = navegador.new_page(viewport={"width": 1280, "height": 900})
        errores = []
        pagina.on("pageerror", lambda e: errores.append(str(e)))
        pagina.goto("file://" + os.path.abspath(preview))
        pagina.wait_for_timeout(700)

        exigir(pagina.is_visible("#teclas-2p"),
               "no dice por ningun sitio con que teclas va el segundo jugador")

        pagina.locator("#pantalla").click()
        pagina.keyboard.press("Enter")
        pagina.wait_for_timeout(200)

        def donde():
            return pagina.evaluate("""() => {
                const w = window.NeoPlat.world;
                return [w.players[0].x >> 8, w.players[1].x >> 8,
                        w.players[0].playing, w.players[1].playing]; }""")

        salida = donde()
        exigir(salida[2] == 1 and salida[3] == 1,
               "los dos jugadores no entran en juego: %s" % salida)

        # Al soltar, el jugador no se para en seco: sigue frenando unos
        # frames. Se le deja acabar antes de mirar donde esta, o el arrastre
        # se contaria como si lo hubiera movido la otra tecla.
        def correr(tecla):
            pagina.keyboard.down(tecla)
            pagina.wait_for_timeout(700)
            pagina.keyboard.up(tecla)
            pagina.wait_for_timeout(400)
            return donde()

        # las flechas mueven al primero y no tocan al segundo
        con_flechas = correr("ArrowRight")
        print("con las flechas:", json.dumps(con_flechas))
        exigir(con_flechas[0] > salida[0] + 20, "las flechas no mueven al primero")
        exigir(con_flechas[1] == salida[1],
               "las flechas mueven tambien al segundo: los dos mandos son el mismo")

        # y la D mueve al segundo y no toca al primero
        con_wasd = correr("d")
        print("con WASD:", json.dumps(con_wasd))
        exigir(con_wasd[1] > con_flechas[1] + 20, "la D no mueve al segundo")
        exigir(con_wasd[0] == con_flechas[0],
               "la D mueve tambien al primero: los dos mandos son el mismo")

        pagina.locator("#pantalla").screenshot(
            path=os.path.join(capturas, "juego-dos.png"))
        if errores:
            fallos.append("errores de JavaScript: %s" % errores[:3])
        navegador.close()

    if fallos:
        for fallo in fallos:
            print("FALLO:", fallo)
        return 1
    print("el preview a dos jugadores lleva bien los dos teclados")
    return 0


def comprobar_guardado(capturas: str = "capturas") -> int:
    """El bucle de guardar y recuperar, con el servidor de verdad detras.

    Es lo unico que comprueba el camino entero: se edita en la pagina, se pulsa
    Ctrl+S, y **el archivo del proyecto en disco tiene que cambiar** y quedar
    una copia en el historial de la que se pueda volver. Las pruebas de
    servidor hablan por HTTP sin navegador, y las de navegador abren la pagina
    como archivo, donde no hay a quien guardar: en medio queda justo lo que le
    importa a quien hace un juego grande.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright no esta instalado: se salta la prueba de navegador")
        return 0
    import shutil
    import tempfile
    import threading

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from comun import cargar_demo
    from ngplat import historial, servidor
    from ngplat.preview import write_preview
    from ngplat.scaffold import crear_proyecto

    os.makedirs(capturas, exist_ok=True)
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    carpeta = tempfile.mkdtemp(prefix="neoplat-guardado-")
    raiz = os.path.join(carpeta, "juego")
    crear_proyecto(raiz, "GUARDADO", "TEST")
    preview = write_preview(cargar_demo(raiz), os.path.join(carpeta, "preview.html"))
    yaml = servidor.ruta_del_yaml(raiz)

    def texto_del_yaml():
        with open(yaml, encoding="utf-8") as fh:
            return fh.read()

    original = texto_del_yaml()
    servidor_local, direccion = servidor.crear(raiz, preview)
    hilo = threading.Thread(target=servidor_local.serve_forever, daemon=True)
    hilo.start()
    try:
        with sync_playwright() as pw:
            navegador = _lanzar(pw)
            pagina = navegador.new_page(viewport={"width": 1280, "height": 900})
            errores = []
            pagina.on("pageerror", lambda e: errores.append(str(e)))
            pagina.goto(direccion)
            pagina.wait_for_timeout(700)
            pagina.keyboard.press("Enter")        # salir del titulo
            pagina.wait_for_timeout(200)
            pagina.keyboard.press("e")            # y entrar a editar
            pagina.wait_for_timeout(500)

            estado = pagina.evaluate(
                "() => document.querySelector('#es-guardado').textContent")
            print("al abrir:", json.dumps(estado))
            exigir("servidor" not in estado,
                   "con el servidor en marcha dice que no lo hay: %r" % estado)

            # se cambia algo de verdad: el nombre del nivel
            pagina.click("#pestanas button[data-panel=nivel]")
            pagina.wait_for_timeout(300)
            pagina.evaluate("""() => {
                window.NeoPlat.editor.ponerPropiedad('nivel', 'nombre', 'GUARDADO');
            }""")
            pagina.wait_for_timeout(200)
            sucio = pagina.evaluate("() => window.NeoPlat.editor.sinGuardar")
            exigir(sucio, "tras cambiar algo no se entera de que hay que guardar")

            # Ctrl+S, que es lo que se pulsa sin pensar
            pagina.keyboard.press("Control+s")
            pagina.wait_for_timeout(1500)
            despues = texto_del_yaml()
            print("guardado:", json.dumps({
                "cambia": despues != original,
                "nombre": "GUARDADO" in despues,
                "estado": pagina.evaluate(
                    "() => document.querySelector('#es-guardado').textContent")}))
            exigir(despues != original, "Ctrl+S no ha escrito nada en el proyecto")
            exigir('nombre: "GUARDADO"' in despues,
                   "el nombre del nivel no ha llegado al game.yaml")
            exigir(not pagina.evaluate("() => window.NeoPlat.editor.sinGuardar"),
                   "sigue diciendo que hay cambios sin guardar")

            copias = historial.listar(raiz)
            print("copias:", json.dumps([(c["numero"], c["motivo"]) for c in copias]))
            exigir(len(copias) >= 1, "guardar no ha dejado ninguna copia")
            exigir(any(c["motivo"] == "editor" for c in copias),
                   "la copia no dice que la hizo el editor")

            # la pestana de copias las ensena
            pagina.click("#pestanas button[data-panel=copias]")
            pagina.wait_for_timeout(800)
            filas = pagina.eval_on_selector_all(
                "#copias-lista .fila", "n => n.length")
            exigir(filas >= 1, "la pestana de copias sale vacia")
            pagina.locator("#panel-copias").screenshot(
                path=os.path.join(capturas, "copias.png"))

            # y se puede volver a la de antes
            pagina.on("dialog", lambda d: d.accept())
            pagina.click("#copias-lista .fila button")
            pagina.wait_for_timeout(2000)
            vuelto = texto_del_yaml()
            print("recuperado:", json.dumps({"vuelve": vuelto == original}))
            exigir(vuelto == original,
                   "recuperar no ha devuelto el game.yaml a como estaba")
            exigir(len(historial.listar(raiz)) > len(copias),
                   "recuperar no ha guardado antes como estaba")

            if errores:
                fallos.append("errores de JavaScript: %s" % errores[:3])
            navegador.close()
    finally:
        servidor_local.shutdown()
        servidor_local.server_close()
        shutil.rmtree(carpeta, ignore_errors=True)

    if fallos:
        for fallo in fallos:
            print("FALLO:", fallo)
        return 1
    print("guardar y recuperar funcionan desde el navegador")
    return 0


if __name__ == "__main__":
    destino = [a for a in sys.argv[1:] if not a.startswith("--")]
    capturas = destino[1] if len(destino) > 1 else "capturas"
    if "--dos" in sys.argv[1:]:
        raise SystemExit(comprobar_dos(capturas))
    if "--guardado" in sys.argv[1:]:
        raise SystemExit(comprobar_guardado(capturas))
    preview = destino[0] if destino else "examples/bosque-magico/preview.html"
    raise SystemExit(comprobar(preview, capturas))
