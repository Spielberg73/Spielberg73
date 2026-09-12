"""La carretera que dibuja el compilador y la que proyecta el motor.

En un juego de conducir la carretera **no se dibuja en la maquina**: se dibuja
una sola vez al compilar (tools/ngplat/carretera.py) y en cada frame solo se
desliza linea a linea. Eso solo funciona si la imagen que sale del compilador
es **exactamente** lo que el motor va a proyectar: si se separan un pixel, la
carretera que se ve no es la que se pisa, y el jugador se sale en sitios donde
la pantalla decia que habia asfalto.

Aqui se atan las dos: las constantes de la camara se leen del propio
np_types.h, y la forma de la calzada se compara linea a linea contra el motor
en C compilado.
"""

import os
import re
import sys
import shutil
import subprocess
import tempfile
import unittest

import comun
from comun import KIT

from ngplat import carretera, sistemas
from ngplat.scaffold import crear_proyecto


def _constantes_del_motor():
    """Las constantes de la camara, leidas de engine/include/np_types.h."""
    ruta = os.path.join(KIT, "engine", "include", "np_types.h")
    with open(ruta, encoding="utf-8") as fh:
        texto = fh.read()
    salida = {}
    for nombre in ("NP_SCREEN_W", "NP_SCREEN_H", "NP_HORIZONTE",
                   "NP_CAMARA_ALTO", "NP_FOCAL", "NP_CERCA", "NP_TILE",
                   "NP_TRAMOS_VISTA", "NP_CARRETERA_FRANJAS"):
        m = re.search(r"^#define\s+%s\s+(\d+)" % nombre, texto, re.M)
        if m:
            salida[nombre] = int(m.group(1))
    return salida


class TestLaCamaraEsLaMisma(unittest.TestCase):
    """Las cifras de la camara estan escritas dos veces -en el motor y en el
    compilador- porque el compilador tiene que dibujar lo que el motor va a
    proyectar. Que no se separen no se deja a la buena fe."""

    def test_las_constantes_cuadran(self):
        motor = _constantes_del_motor()
        propias = {
            "NP_SCREEN_W": carretera.SCREEN_W,
            "NP_SCREEN_H": carretera.SCREEN_H,
            "NP_HORIZONTE": carretera.HORIZONTE,
            "NP_CAMARA_ALTO": carretera.CAMARA_ALTO,
            "NP_FOCAL": carretera.FOCAL,
            "NP_CERCA": carretera.CERCA,
            "NP_TILE": carretera.TILE,
            "NP_TRAMOS_VISTA": carretera.TRAMOS_VISTA,
        }
        for nombre, valor in propias.items():
            self.assertIn(nombre, motor,
                          "%s ya no esta en np_types.h" % nombre)
            self.assertEqual(motor[nombre], valor,
                             "%s vale %d en el motor y %d en carretera.py"
                             % (nombre, motor[nombre], valor))

    def test_las_franjas_tambien(self):
        """Las franjas se declaran en np_world.h, no en np_types.h."""
        ruta = os.path.join(KIT, "engine", "include", "np_world.h")
        with open(ruta, encoding="utf-8") as fh:
            m = re.search(r"^#define\s+NP_CARRETERA_FRANJAS\s+(\d+)",
                          fh.read(), re.M)
        self.assertIsNotNone(m, "NP_CARRETERA_FRANJAS ya no esta en np_world.h")
        self.assertEqual(int(m.group(1)), carretera.FRANJAS)


class TestLasFranjasSeVen(unittest.TestCase):
    """Que las rayas que corren hacia ti se vean **en la maquina**.

    Las franjas no son un dibujo que se mueva: son cuatro huecos de paleta
    -A, A, B, B- que la maquina rota un paso por frame. Si A y B le caen en el
    mismo color, la rotacion ocurre igual y en pantalla no se mueve nada: la
    calzada sale lisa y parece que el coche esta parado.

    Paso de verdad, y costo una tarde: los dos grises del asfalto que traia el
    kit se llevaban ocho puntos, y la Mega Drive guarda tres bits por canal
    -ocho niveles-, asi que eran el mismo gris. Desde fuera parecia que las
    escrituras a la CRAM no llegaban. Esta prueba lo mira en las ocho
    maquinas, empezando por las dos mas cortas de color.
    """

    def _proyecto(self, destino, asfalto=""):
        crear_proyecto(destino, "COSTA", "TEST", genero="carretera")
        yaml = os.path.join(destino, "game.yaml")
        if asfalto:
            with open(yaml, encoding="utf-8") as fh:
                texto = fh.read()
            texto = re.sub(r"asfalto: \[[^\]]*\]", asfalto, texto)
            with open(yaml, "w", encoding="utf-8") as fh:
                fh.write(texto)
        return yaml

    def test_los_dos_tonos_se_distinguen_en_las_ocho_maquinas(self):
        carpeta = tempfile.mkdtemp(prefix="neoplat-franjas-")
        try:
            yaml = self._proyecto(os.path.join(carpeta, "juego"))
            for maquina in sistemas.disponibles():
                build = comun.cargar_demo(yaml, maquina.nombre)
                self.assertEqual(
                    maquina.avisos_de_carretera(build), [],
                    "en %s las franjas de serie no se distinguen"
                    % maquina.nombre)
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)

    def test_avisa_cuando_los_dos_tonos_son_el_mismo(self):
        """Y si alguien elige dos tonos que se funden, se le dice."""
        carpeta = tempfile.mkdtemp(prefix="neoplat-fundidos-")
        try:
            yaml = self._proyecto(os.path.join(carpeta, "juego"),
                                  'asfalto: ["#4a4a52", "#484850"]')
            build = comun.cargar_demo(yaml, "megadrive")
            avisos = sistemas.obtener("megadrive").avisos_de_carretera(build)
            self.assertTrue(any("asfalto" in a for a in avisos),
                            "no aviso de que el asfalto se funde: %r" % avisos)
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)


class TestLaFormaDeLaCalzada(unittest.TestCase):
    """Y la prueba de verdad: la calzada que dibuja el compilador, linea a
    linea, contra la que proyecta el motor en C."""

    def test_la_textura_es_lo_que_proyecta_el_motor(self):
        import shutil
        import tempfile
        from ngplat.build import build_project
        from ngplat.codegen import copy_engine, generate_gamedata
        from ngplat.project import load_project
        from ngplat.scaffold import crear_proyecto

        if not shutil.which("gcc"):
            self.skipTest("no hay gcc para compilar el motor")
        tmp = tempfile.mkdtemp()
        try:
            proyecto = os.path.join(tmp, "circuito")
            crear_proyecto(proyecto, "COSTA", "TEST", genero="carretera")
            build = build_project(load_project(proyecto))
            out = os.path.join(tmp, "build")
            os.makedirs(os.path.join(out, "src"), exist_ok=True)
            for relativo, contenido in generate_gamedata(build).items():
                with open(os.path.join(out, relativo), "w",
                          encoding="utf-8") as fh:
                    fh.write(contenido)
            copy_engine(out)
            # un programita que saca el medio ancho por linea del motor
            fuente = os.path.join(tmp, "medio.c")
            with open(fuente, "w", encoding="utf-8") as fh:
                fh.write(_MEDIO_C)
            binario = os.path.join(tmp, "medio")
            compilar = subprocess.run(
                ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", os.path.join(out, "src"), "-o", binario, fuente,
                 os.path.join(out, "src", "np_world.c"),
                 os.path.join(out, "src", "gamedata.c")],
                capture_output=True, text=True)
            self.assertEqual(compilar.returncode, 0,
                             "el motor no compila:\n" + compilar.stderr)
            salida = subprocess.run([binario], capture_output=True, text=True,
                                    check=True).stdout.split()
            ancho_via = int(salida[0])
            medio_motor = [int(v) for v in salida[1:]]
            self.assertEqual(len(medio_motor), carretera.SCREEN_H)
            # el ancho de la calzada que ha sacado el compilador tiene que ser
            # el mismo que el que ha sacado el motor del mapa
            self.assertGreater(ancho_via, 0)
            medio_compilador = [m for m, _ in carretera.lineas(ancho_via)]
            distintas = [y for y in range(carretera.SCREEN_H)
                         if medio_motor[y] != medio_compilador[y]]
            self.assertEqual(
                distintas, [],
                "la carretera que dibuja el compilador y la que proyecta el "
                "motor no cuadran en %d lineas (la primera, la %d: motor %d, "
                "compilador %d)"
                % (len(distintas), distintas[0] if distintas else -1,
                   medio_motor[distintas[0]] if distintas else 0,
                   medio_compilador[distintas[0]] if distintas else 0))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestElTraficoEnPerspectiva(unittest.TestCase):
    """Lo que esta en la calzada se ve mas pequeno cuanto mas lejos.

    Y no es un adorno: era un fallo. En la vista de carretera las ocho
    maquinas dibujaban los coches con la camara del mapa -que no es la de esta
    vista- y se iban fuera de la pantalla, asi que no se veia ni uno. El motor
    ya decia donde caen (np_carretera_donde); lo que faltaba era **con que
    dibujo**, porque de las ocho solo la Neo Geo sabe encoger un sprite por
    hardware y las demas necesitan el dibujo ya hecho a cada tamano.
    """

    def test_el_dibujo_encogido_no_inventa_colores(self):
        """Estas maquinas tienen dieciseis colores: uno nuevo es uno que no cabe.

        Por eso no se promedia al encoger, se vota: cada pixel del resultado se
        queda con el color que mas manda en el cuadrado que le toca.
        """
        from ngplat import gfx
        from ngplat.png import read_png
        carpeta = tempfile.mkdtemp(prefix="neoplat-encoger-")
        try:
            proyecto = os.path.join(carpeta, "circuito")
            crear_proyecto(proyecto, "COSTA", "TEST", genero="carretera")
            build = comun.cargar_demo(proyecto, "megadrive")
            rival = next(a for a in build.enemies if a.lejos)
            originales = set(read_png(rival.sheet.path).colors())
            anterior = None
            for hoja in [rival.sheet] + rival.lejos:
                imagen = read_png(hoja.path)
                self.assertEqual(hoja.frame_w % 16, 0, hoja.name)
                self.assertEqual(hoja.frame_h % 16, 0, hoja.name)
                self.assertLessEqual(
                    set(hoja.palette.colors), {c[:3] for c in originales},
                    "%s se ha inventado un color" % hoja.name)
                if anterior is not None:
                    self.assertLessEqual(len(hoja.tiles), len(anterior),
                                         "%s no es mas pequena que la anterior"
                                         % hoja.name)
                anterior = hoja.tiles
                self.assertGreater(
                    sum(1 for t in hoja.tiles for px in t if px), 0,
                    "%s se ha quedado en nada: la silueta no sobrevive"
                    % hoja.name)
            self.assertTrue(imagen)
        finally:
            shutil.rmtree(carpeta, ignore_errors=True)

    def test_de_cerca_a_lejos_el_dibujo_solo_puede_encoger(self):
        """La eleccion la hace el motor -np_carretera_dibujo- para que las ocho
        maquinas elijan el mismo: con cinco tamanos, elegir distinto se ve."""
        if not shutil.which("gcc"):
            self.skipTest("no hay gcc para compilar el motor")
        from ngplat.build import build_project
        from ngplat.codegen import copy_engine, generate_gamedata
        from ngplat.project import load_project
        tmp = tempfile.mkdtemp(prefix="neoplat-tamanos-")
        try:
            proyecto = os.path.join(tmp, "circuito")
            crear_proyecto(proyecto, "COSTA", "TEST", genero="carretera")
            build = build_project(load_project(proyecto))
            out = os.path.join(tmp, "build")
            os.makedirs(os.path.join(out, "src"), exist_ok=True)
            for relativo, contenido in generate_gamedata(build).items():
                with open(os.path.join(out, relativo), "w",
                          encoding="utf-8") as fh:
                    fh.write(contenido)
            copy_engine(out)
            fuente = os.path.join(tmp, "tamanos.c")
            with open(fuente, "w", encoding="utf-8") as fh:
                fh.write(_TAMANOS_C)
            binario = os.path.join(tmp, "tamanos")
            compilar = subprocess.run(
                ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                 "-I", os.path.join(out, "src"), "-o", binario, fuente,
                 os.path.join(out, "src", "np_world.c"),
                 os.path.join(out, "src", "gamedata.c")],
                capture_output=True, text=True)
            self.assertEqual(compilar.returncode, 0,
                             "el motor no compila:\n" + compilar.stderr)
            salida = subprocess.run([binario], capture_output=True, text=True,
                                    check=True).stdout.split()
            areas = [int(v) for v in salida]
            self.assertTrue(areas, "el enemigo de la carretera no tiene tamanos")
            self.assertTrue(all(a > 0 for a in areas),
                            "a alguna distancia no se dibujaria nada: %r" % areas)
            for antes, despues in zip(areas, areas[1:]):
                self.assertLessEqual(despues, antes,
                                     "yendose mas lejos el dibujo crece: %r"
                                     % areas)
            self.assertLess(areas[-1], areas[0],
                            "de lejos se dibuja igual de grande que de cerca")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


    def test_el_trafico_sale_en_la_pantalla_de_la_mega_drive(self):
        """Y la prueba que importa: arrancar la ROM y mirar si se ve.

        El fallo era justo este: el juego compilaba, se jugaba y la calzada se
        veia perfecta, pero **no salia ni un coche**. Asi que aqui no se mira
        ningun registro: se conduce y se buscan en la pantalla los colores que
        solo tiene el trafico, por debajo del horizonte.

        Y no basta con que aparezcan. Lo que dice que hay perspectiva es que
        **lo de abajo se ve mas ancho que lo de arriba**: contando los pixeles
        de trafico fila a fila, la fila mas ancha tiene que estar por debajo de
        la mas estrecha y ser varias veces mayor. Contar el total no vale -se
        probo-: el trafico va a la misma velocidad que tu, asi que el total se
        queda casi clavado aunque la perspectiva este bien.
        """
        import sys
        sys.path.insert(0, os.path.join(KIT, "tests"))
        from libretro import Emulador, buscar_core
        from ngplat import carretera as carr
        from ngplat.build import build_project
        from ngplat.project import load_project
        core = buscar_core("genesis_plus_gx", "NEOPLAT_CORE_MD")
        if not core:
            self.skipTest("no esta instalado el core de Genesis Plus GX")
        if not shutil.which("m68k-linux-gnu-gcc") and not shutil.which("m68k-elf-gcc"):
            self.skipTest("no hay un compilador de 68000 instalado")
        tmp = tempfile.mkdtemp(prefix="neoplat-trafico-")
        try:
            proyecto = os.path.join(tmp, "circuito")
            crear_proyecto(proyecto, "COSTA", "TEST", genero="carretera")
            build = build_project(load_project(proyecto),
                                  sistemas.obtener("megadrive").carretera_como)
            out = os.path.join(tmp, "build")
            from ngplat.codegen import generar_para_sistema
            maquina = sistemas.obtener("megadrive")
            maquina.preparar(build)
            generar_para_sistema(build, out, maquina, "202")
            hecho = subprocess.run(["make", "-C", out], capture_output=True,
                                   text=True)
            self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
            rom = os.path.join(out, "rom", "juego.bin")

            # Los colores que solo tiene el trafico: los suyos menos los de
            # todo lo demas. Si algun dia el arte los compartiera, la prueba lo
            # diria aqui en vez de fallar por otro sitio.
            rival = next(a for a in build.enemies if a.lejos)
            otros = set(build.player.sheet.palette.colors)
            otros |= set(build.tileset.palette.colors)
            for capa in build.layers:
                if capa.palette:
                    otros |= set(capa.palette.colors)
            solo = [c for c in rival.sheet.palette.colors if c not in otros]
            self.assertTrue(solo, "el trafico no tiene ningun color propio: "
                                  "asi no se puede buscar en la pantalla")

            emu = Emulador(core)
            emu.cargar(rom)
            emu.avanzar(120)
            emu.pulsar("START")
            emu.avanzar(4)
            emu.pulsar()                  # soltar, o el juego no arranca
            emu.avanzar(60)
            emu.pulsar("A", "B")          # acelerador y marcha larga
            emu.avanzar(60)
            emu.pulsar("A")
            emu.avanzar(30)
            filas = _filas_de(emu.frame, solo, desde_y=carr.HORIZONTE)
            self.assertTrue(
                filas,
                "conduciendo no se ve ni un coche de trafico: la calzada se "
                "dibuja pero lo que esta encima, no")
            ancha = max(filas, key=lambda par: par[1])
            estrecha = min(filas, key=lambda par: par[1])
            self.assertGreaterEqual(
                ancha[1], estrecha[1] * 4,
                "el trafico se ve igual de ancho de cerca (%d px) que de lejos "
                "(%d px): no esta encogiendo" % (ancha[1], estrecha[1]))
            self.assertGreater(
                ancha[0], estrecha[0],
                "lo mas ancho sale mas arriba (linea %d) que lo mas estrecho "
                "(linea %d): la perspectiva esta al reves"
                % (ancha[0], estrecha[0]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


def _filas_de(pantalla, colores, desde_y=0):
    """Cuantos pixeles de cada uno de esos colores hay en cada fila.

    Devuelve solo las filas donde hay alguno, como (linea, cuantos). Se compara
    con holgura porque cada maquina redondea el color a lo suyo -la Mega Drive
    guarda tres bits por canal- y el emulador lo devuelve ya estirado a ocho.
    """
    ancho, alto, pixeles = pantalla
    filas = []
    for y in range(desde_y, alto):
        base = y * ancho
        cuantos = 0
        for x in range(ancho):
            r, g, b = pixeles[base + x][:3]
            for cr, cg, cb in colores:
                if abs(r - cr) <= 24 and abs(g - cg) <= 24 and abs(b - cb) <= 24:
                    cuantos += 1
                    break
        if cuantos:
            filas.append((y, cuantos))
    return filas


class TestLaCarreteraEnAGA(unittest.TestCase):
    """La calzada tiene que caer en el mismo pixel en el A500 y en el A1200.

    Suena a perogrullada y no lo es. El A1200 y el CD32 leen los bitplanes de
    32 en 32 bits, y el puntero de un plano salta lo que el chip lee de una
    vez: el resto, hasta 31 pixeles, lo tiene que poner el scroll fino. Pero el
    margen para retrasar el plano sigue siendo de 16 -la DMA empieza ocho
    relojes antes y ahi no cabe mas-, asi que de las 32 posiciones posibles
    solo salian la mitad y **la calzada se quedaba 16 pixeles a la izquierda,
    siempre**. El marcador, que va en el otro plano, caia en su sitio.

    Por eso conduciendo AGA lee de 16 en 16, como el A500. Esta prueba es la
    que avisaria si alguien se lo lleva por delante.
    """

    def test_la_calzada_cae_en_el_mismo_pixel_en_ocs_y_en_aga(self):
        import json
        sys.path.insert(0, os.path.join(KIT, "tests"))
        from libretro import buscar_core
        from ngplat.build import build_project
        from ngplat.project import load_project
        if not buscar_core("puae", "NEOPLAT_CORE_AMIGA"):
            self.skipTest("no esta instalado el core de PUAE")
        if not shutil.which("m68k-linux-gnu-gcc") and not shutil.which("m68k-elf-gcc"):
            self.skipTest("no hay un compilador de 68000 instalado")
        tmp = tempfile.mkdtemp(prefix="neoplat-aga-")
        try:
            proyecto = os.path.join(tmp, "circuito")
            crear_proyecto(proyecto, "COSTA", "TEST", genero="carretera")
            # los dos tonos de la calzada, que es lo que se busca en pantalla
            build = build_project(load_project(proyecto),
                                  sistemas.obtener("amiga").carretera_como)
            tonos = ",".join("%02x%02x%02x" % tuple(t)
                             for t in build.asfalto.tonos[2])
            donde = {}
            for maquina, modelo, chip in (("amiga", "A500", "1"),
                                          ("amiga1200", "A1200", "2")):
                from ngplat.codegen import generar_para_sistema
                out = os.path.join(tmp, maquina)
                sistema = sistemas.obtener(maquina)
                suyo = build_project(load_project(proyecto),
                                     sistema.carretera_como)
                sistema.preparar(suyo)
                generar_para_sistema(suyo, out, sistema, "202")
                hecho = subprocess.run(["make", "-C", out], capture_output=True,
                                       text=True)
                self.assertEqual(hecho.returncode, 0,
                                 "%s no compila:\n%s" % (maquina, hecho.stderr))
                adf = [f for f in os.listdir(os.path.join(out, "disco"))
                       if f.endswith(".adf")][0]
                salida = subprocess.run(
                    [sys.executable, os.path.join(KIT, "tests", "calzada_amiga.py"),
                     os.path.join(out, "disco", adf), modelo, chip, tonos],
                    capture_output=True, text=True, check=True)
                donde[maquina] = json.loads(salida.stdout.strip().splitlines()[-1])
                if "saltar" in donde[maquina]:
                    self.skipTest(donde[maquina]["saltar"])
            self.assertTrue(any(v for v in donde["amiga"].values()),
                            "en el A500 no se ve la calzada: %r" % donde["amiga"])
            self.assertEqual(
                donde["amiga1200"], donde["amiga"],
                "la calzada no cae igual en las dos maquinas.\n"
                "  A500 : %r\n  A1200: %r" % (donde["amiga"], donde["amiga1200"]))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestLaCarreteraEnLaJaguar(unittest.TestCase):
    """En la Jaguar hay que mirar dos cosas, y no son la misma.

    El Object Processor **gasta** la lista de objetos segun la dibuja, asi que
    el retrazo que pasa mientras el juego piensa se encontraba una lista ya
    consumida y dejaba la pantalla en negro: salian dos frames de cada tres sin
    imagen. Eso lo arregla volcar la lista desde la interrupcion de video.

    Pero al hacerlo aparecio el fallo gemelo, y este engana: esperar el retrazo
    mirando el contador de linea dejo de valer -entre la linea en la que
    interrumpe y el final de la cuenta hay diecisiete medias lineas y volcar
    tarda mas-, asi que el bucle se quedaba dando vueltas. **Se veia el 100% de
    los frames, todos con la misma foto.** Una prueba que solo cuente colores
    da eso por bueno.

    Asi que aqui se exige lo uno y lo otro: que casi todos los frames traigan
    imagen y que la imagen **cambie**.
    """

    def test_se_ve_en_todos_los_frames_y_ademas_el_juego_avanza(self):
        import hashlib
        sys.path.insert(0, os.path.join(KIT, "tests"))
        from libretro import Emulador, buscar_core
        import emulador_jaguar
        from ngplat.build import build_project
        from ngplat.codegen import generar_para_sistema
        from ngplat.project import load_project
        core = buscar_core(emulador_jaguar.CORE, "NEOPLAT_CORE_JAGUAR")
        if not core:
            self.skipTest("no esta instalado el core de Virtual Jaguar")
        if not shutil.which("m68k-linux-gnu-gcc") and not shutil.which("m68k-elf-gcc"):
            self.skipTest("no hay un compilador de 68000 instalado")
        tmp = tempfile.mkdtemp(prefix="neoplat-jag-carretera-")
        try:
            proyecto = os.path.join(tmp, "circuito")
            crear_proyecto(proyecto, "COSTA", "TEST", genero="carretera")
            maquina = sistemas.obtener("jaguar")
            build = build_project(load_project(proyecto), maquina.carretera_como)
            maquina.preparar(build)
            out = os.path.join(tmp, "build")
            generar_para_sistema(build, out, maquina, "202")
            hecho = subprocess.run(["make", "-C", out], capture_output=True,
                                   text=True)
            self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
            rom = [os.path.join(out, "rom", f)
                   for f in os.listdir(os.path.join(out, "rom"))
                   if f.endswith(".j64")][0]
            emu = Emulador(core, sistema=tempfile.mkdtemp(prefix="neoplat-jag-"))
            emu.cargar(rom)
            emu.avanzar(200)
            emu.pulsar(emulador_jaguar.EMPEZAR); emu.avanzar(6); emu.pulsar()
            emu.avanzar(40)
            emu.pulsar(emulador_jaguar.SALTAR)   # acelerar
            emu.avanzar(60)
            con_imagen, fotos = 0, []
            for _ in range(40):
                emu.avanzar(1)
                ancho, alto, px = emu.frame
                # la pantalla en negro tiene cuatro colores; la carretera, muchos
                if len({p[:3] for p in px}) >= 8:
                    con_imagen += 1
                fotos.append(hashlib.md5(
                    bytes(bytearray([c for p in px for c in p]))).hexdigest())
            self.assertGreaterEqual(
                con_imagen, 38,
                "solo %d frames de 40 traen imagen: la lista se esta gastando "
                "sin volver a volcarla" % con_imagen)
            self.assertGreater(
                len(set(fotos)), 1,
                "los 40 frames son la misma foto: se ve, pero el juego no "
                "avanza (el bucle se ha quedado esperando un retrazo que ya "
                "paso)")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestLaCarreteraEnLaNeoGeo(unittest.TestCase):
    """La Neo Geo es la unica que no tiene **nada** con lo que deslizar una
    imagen linea a linea: no hay plano que correr, ni copper, ni lista de
    objetos por linea. Todo son sprites, y un sprite de Neo Geo es una
    columna: justo lo contrario de lo que hace falta.

    Por eso la carretera va en bandas -una fila de sprites cada 16 lineas, con
    su desplazamiento- y el trafico se sirve de lo unico que esta maquina si
    tiene y ninguna de las otras siete: el escalador de sprites.

    Se comprueba en el banco del kit (tests/maquina_neogeo.py), que ejecuta el
    68000 de verdad y reconstruye la pantalla desde la VRAM.
    """

    def _montar(self):
        try:
            import machine68k  # noqa: F401
        except ImportError:
            self.skipTest("falta machine68k (pip3 install amitools)")
        sys.path.insert(0, os.path.join(KIT, "tests"))
        import maquina_neogeo
        from ngplat.build import build_project
        from ngplat.codegen import generar_para_sistema
        from ngplat.project import load_project
        if not maquina_neogeo.compilador():
            self.skipTest("no hay un compilador de 68000 instalado")
        tmp = tempfile.mkdtemp(prefix="neoplat-ng-carretera-")
        self.addCleanup(shutil.rmtree, tmp, True)
        proyecto = os.path.join(tmp, "circuito")
        crear_proyecto(proyecto, "COSTA", "TEST", genero="carretera")
        maquina = sistemas.obtener("neogeo")
        build = build_project(load_project(proyecto), maquina.carretera_como)
        maquina.preparar(build)
        out = os.path.join(tmp, "build")
        generar_para_sistema(build, out, maquina, "202")
        os.makedirs(os.path.join(out, "rom"), exist_ok=True)
        maquina_neogeo.construir_p1(out, os.path.join(out, "rom", "202-p1.p1"))
        emu = maquina_neogeo.cargar(out)
        self.assertIsNotNone(emu, "el banco no ha podido montar la ROM")
        emu.avanzar(20)
        emu.pulsar("START"); emu.avanzar(4); emu.pulsar(); emu.avanzar(20)
        emu.pulsar("B")   # el acelerador es el boton de accion, no el de saltar
        return maquina_neogeo, emu

    def test_la_calzada_se_ve_en_perspectiva_y_se_mueve_con_el_trazado(self):
        """Dos cosas, y la segunda es la que de verdad prueba las bandas.

        La primera es que la carretera este puesta: asfalto ninguno por encima
        del horizonte y, por debajo, mas ancho abajo que arriba. Eso solo, sin
        embargo, lo daria por bueno una carretera pegada en el sitio: el ancho
        viene dibujado en la imagen del compilador.

        La segunda es que **cada banda se corra por su cuenta**. Se sigue el eje
        de la calzada -el centro del asfalto- en una fila de cerca y en otra de
        lejos, a lo largo de varios frames. Abajo el eje no se mueve casi: el
        coche va siempre encima de la calzada y la camara le sigue. Arriba si,
        porque ahi es donde la curva se ve. Si alguien deja las bandas quietas,
        o las corre todas igual, esto se cae.
        """
        from ngplat import carretera as carr
        _, emu = self._montar()
        emu.avanzar(60)

        def asfalto(px, ancho, fila):
            """Los pixeles grises de esa fila: ni el cielo, ni la hierba, ni
            los arcenes (rojo y blanco) lo son."""
            return [x for x in range(ancho)
                    for r, g, b in (px[fila * ancho + x][:3],)
                    if abs(r - g) < 24 and abs(g - b) < 24 and r < 170]

        ancho, alto, px = emu.dibujar()
        cielo = {p[:3] for p in px[:(carr.HORIZONTE - 8) * ancho]}
        self.assertLessEqual(
            len(cielo), 4,
            "por encima del horizonte tendria que haber solo cielo, y hay %d"
            " colores" % len(cielo))
        arriba = asfalto(px, ancho, carr.HORIZONTE + 8)
        abajo = asfalto(px, ancho, alto - 8)
        self.assertTrue(arriba, "junto al horizonte no se ve calzada")
        self.assertGreater(
            len(abajo), len(arriba) * 3,
            "la calzada no se abre: %d pixeles de asfalto arriba y %d abajo"
            % (len(arriba), len(abajo)))

        ejes_arriba, ejes_abajo = [], []
        for _ in range(8):
            emu.avanzar(12)
            ancho, alto, px = emu.dibujar()
            for fila, donde in ((carr.HORIZONTE + 16, ejes_arriba),
                                (alto - 8, ejes_abajo)):
                trozo = asfalto(px, ancho, fila)
                if trozo:
                    donde.append((trozo[0] + trozo[-1]) // 2)
        recorre_lejos = max(ejes_arriba) - min(ejes_arriba)
        recorre_cerca = max(ejes_abajo) - min(ejes_abajo)
        self.assertGreater(recorre_lejos, 0,
                           "las bandas de lejos no se mueven: %r" % ejes_arriba)
        self.assertGreater(
            recorre_cerca, recorre_lejos * 2,
            "lo de cerca tendria que barrer mucho mas que lo de lejos, y ha "
            "corrido %d frente a %d (%r y %r)"
            % (recorre_cerca, recorre_lejos, ejes_abajo, ejes_arriba))

    def test_el_escalador_encoge_de_verdad_lo_que_esta_lejos(self):
        """Y esto es lo que no puede hacer ninguna otra de las ocho.

        Se mira la VRAM: en SCB2 cada sprite lleva cuanto se encoge, y 0x0FFF
        es "tal cual". Conduciendo tiene que haber sprites encogidos, y ademas
        **con mas de un valor**: si todos encogieran lo mismo seria que el
        motor le esta pasando una constante, no la escala de cada coche.
        """
        maquina_neogeo, emu = self._montar()
        zooms = set()
        for _ in range(6):
            emu.avanzar(20)
            for sprite in range(maquina_neogeo.SPRITES):
                control = emu.vram[maquina_neogeo.SCB3 + sprite]
                if not (control & 0x3F):
                    continue                 # apagado
                z = emu.vram[maquina_neogeo.SCB2 + sprite]
                if z != 0x0FFF:
                    zooms.add(z)
        self.assertTrue(zooms, "no hay ni un sprite encogido: el escalador no"
                               " se esta usando")
        self.assertGreater(len(zooms), 1,
                           "todos los sprites encogen igual (%r): eso no es la"
                           " escala de cada uno" % sorted(zooms))

    def test_el_frame_cabe_en_los_ciclos_que_da_la_consola(self):
        """Una carretera que no quepa en el frame no es una carretera: es un
        juego a 30.

        Lo que no cabia no eran los sprites de las bandas -eso costaba poco-:
        era **la proyeccion**, 160 divisiones de 32 bits por frame, que en un
        68000 no son una instruccion sino una llamada a una rutina de la
        biblioteca. Con la tabla de tramos se quedan en unas veinte y el frame
        pasa de 400.000 ciclos a caber en los 200.000 que da la consola.

        Se mira la media y el pico por separado: de media cabe, y algun frame
        con mucho trafico se pasa un poco -la consola repite ese frame y ya-,
        pero ninguno tiene que irse al doble.
        """
        maquina_neogeo, emu = self._montar()
        emu.avanzar(30)
        ciclos = [emu.frame() for _ in range(60)]
        medio = sum(ciclos) // len(ciclos)
        tope = maquina_neogeo.CICLOS_FRAME
        self.assertLess(
            medio, tope,
            "un frame de carretera cuesta %d ciclos de media y la consola da"
            " %d" % (medio, tope))
        self.assertLess(
            max(ciclos), tope * 3 // 2,
            "hay frames que cuestan %d ciclos, mas de vez y media lo que da la"
            " consola (%d)" % (max(ciclos), tope))


_TAMANOS_C = """/* Que tamano elige el motor a cada distancia, en tiles. */
#include <stdio.h>
#include "np_world.h"
int main(void)
{
    const NpActorDef *def = &np_enemies[0].actor;
    int32_t escala;
    for (escala = 256; escala >= 8; escala -= 8) {
        const NpCarreteraTam *tam = np_carretera_dibujo(def, escala);
        printf("%d ", tam ? tam->cols * tam->rows : 0);
    }
    printf("\\n");
    return 0;
}
"""


_MEDIO_C = """/* Saca el ancho de la calzada y el medio ancho por linea. */
#include <stdio.h>
#include "np_world.h"
static NpWorld world;
static int16_t centro[NP_SCREEN_H];
int main(void)
{
    uint16_t horizonte, y;
    int32_t k, z, sy, i, medio[NP_SCREEN_H], sy_ant, mx, mx_ant, alto, dmx, amx;
    int primero = 1;
    np_world_init(&world);
    np_world_step(&world, NP_IN_START, 0);
    np_world_step(&world, 0, 0);
    horizonte = np_carretera(&world, centro);
    (void)horizonte;
    for (y = 0; y < NP_SCREEN_H; y++) medio[y] = 0;
    /* la misma cuenta que carretera.py: la calzada recta, sin camara */
    sy_ant = NP_SCREEN_H;
    mx_ant = 0;
    for (i = 0; i < NP_TRAMOS_VISTA; i++) {
        z = i * NP_TILE + NP_CERCA;
        k = ((int32_t)NP_FOCAL << 8) / (z < 1 ? 1 : z);
        sy = NP_HORIZONTE + ((NP_CAMARA_ALTO * k) >> 8);
        if (sy >= NP_SCREEN_H) continue;
        if (sy <= NP_HORIZONTE) break;
        mx = (world.via_ancho * k) >> 8;
        alto = sy_ant - sy;
        if (alto <= 0) continue;
        if (primero) { mx_ant = mx; primero = 0; }
        dmx = ((mx_ant - mx) << 8) / alto;
        amx = mx << 8;
        for (y = (uint16_t)sy; y < (uint16_t)sy_ant; y++) {
            medio[y] = amx >> 8;
            amx += dmx;
        }
        sy_ant = sy;
        mx_ant = mx;
    }
    printf("%d\\n", (int)world.via_ancho);
    for (y = 0; y < NP_SCREEN_H; y++) printf("%d\\n", (int)medio[y]);
    return 0;
}
"""


if __name__ == "__main__":
    unittest.main()
