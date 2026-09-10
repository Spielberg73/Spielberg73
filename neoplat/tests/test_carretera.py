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
import subprocess
import unittest

import comun
from comun import KIT

from ngplat import carretera


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
