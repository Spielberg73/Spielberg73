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
