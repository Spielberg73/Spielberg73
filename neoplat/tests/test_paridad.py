"""El motor en C y el preview en JavaScript deben dar el mismo resultado.

Se ejecutan los dos con la misma secuencia de pulsaciones y se comparan las
trazas frame a frame: posicion, velocidad, camara, estado, puntos y un hash de
todas las entidades. Si alguien toca solo una de las dos implementaciones,
esta prueba lo detecta.
"""

import json
import os
import random
import shutil
import subprocess
import tempfile
import unittest

import comun
from comun import KIT, cargar_demo

from ngplat.codegen import copy_engine, generate_gamedata
from ngplat.preview import build_data
from ngplat.scaffold import crear_proyecto

IN_LEFT, IN_RIGHT, IN_DOWN, IN_JUMP, IN_START = 1, 2, 8, 16, 64
IN_ACTION = 32
FRAMES = 3000
ESTADO_FIN_NIVEL = 3        # NP_STATE_LEVEL_END


BOTONES = [IN_RIGHT, IN_RIGHT, IN_RIGHT | IN_JUMP, IN_LEFT,
           IN_LEFT | IN_JUMP, IN_JUMP, IN_DOWN, 0, IN_START,
           IN_ACTION, IN_RIGHT | IN_ACTION, IN_LEFT | IN_ACTION]


def _secuencia(semilla: int):
    """Pulsaciones pseudoaleatorias para los dos mandos, iguales para las dos
    implementaciones. Cada frame son dos numeros: el mando de cada jugador.

    El segundo lleva su propia semilla y cambia de tecla con otro ritmo (cada
    17 frames y no cada 23), para que los dos no hagan lo mismo a la vez: si
    fueran iguales, media prueba no comprobaria nada."""
    rng = random.Random(semilla)
    rng2 = random.Random(semilla * 7919 + 13)
    entradas = [(IN_START, 0), (IN_START, 0), (0, 0)]
    estado = estado2 = 0
    for i in range(FRAMES):
        if i % 23 == 0:
            estado = rng.choice(BOTONES)
        if i % 17 == 0:
            estado2 = rng2.choice(BOTONES)
        entradas.append((estado, estado2))
    return entradas


class TestParidad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("gcc"):
            raise unittest.SkipTest("no hay gcc para compilar el motor")
        if not shutil.which("node"):
            raise unittest.SkipTest("no hay node para ejecutar el preview")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-paridad-")
        # Se comprueban los dos modos de camara: con scroll y pantalla a
        # pantalla la simulacion es la misma, pero la camara no, y la camara va
        # en la traza.
        cls.variantes = {}
        for camara in ("scroll", "pantallas"):
            cls.variantes[camara] = cls._preparar(camara)
        cls.variantes["jefe"] = cls._preparar("scroll", jefe=True)
        cls.variantes["dos"] = cls._preparar("scroll", dos=True)
        cls.variantes["dos-pantallas"] = cls._preparar("pantallas", dos=True)
        cls.variantes["golpe"] = cls._preparar("scroll", golpe=True)
        cls.variantes["llave"] = cls._preparar("scroll", llave=True)
        cls.variantes["tablon"] = cls._preparar("scroll", tablon=True)
        cls.variantes["latigo"] = cls._preparar("scroll", latigo=True)

    @classmethod
    def _preparar(cls, camara, jefe=False, dos=False, golpe=False, llave=False,
                  tablon=False, latigo=False):
        proyecto_dir = os.path.join(
            cls.tmp, "juego-" + camara + ("-jefe" if jefe else "")
            + ("-dos" if dos else "") + ("-golpe" if golpe else "")
            + ("-llave" if llave else "") + ("-tablon" if tablon else "")
            + ("-latigo" if latigo else ""))
        crear_proyecto(proyecto_dir, "PARIDAD", "TEST")
        yaml = os.path.join(proyecto_dir, "game.yaml")
        with open(yaml, encoding="utf-8") as fh:
            texto = fh.read()
        # el andamiaje ya trae 'camara: scroll': hay que cambiar esa linea, no
        # anadir otra, o el lector se queda con la ultima
        assert "  camara: scroll" in texto, "el andamiaje ya no trae la camara"
        texto = texto.replace("  camara: scroll", "  camara: " + camara, 1)
        if dos:
            texto = texto.replace("  vidas:", "  jugadores: 2\n  vidas:", 1)
        if golpe:
            # el mismo proyecto, pero con el ataque cuerpo a cuerpo: no salen
            # proyectiles y el dano lo hace una caja delante del jugador
            marca = "    tipo: disparo"
            assert marca in texto, "el andamiaje ya no trae el ataque asi"
            texto = texto.replace(marca, "    tipo: golpe", 1)
        if llave:
            # el andamiaje pone la llave en la plataforma mas alta y el mando
            # aleatorio no llega hasta alli: se pone otra a dos pasos de la
            # salida para que la traza compare tambien el momento de cogerla
            marca = "\n      P.......s"
            assert marca in texto, "el primer nivel ya no empieza asi"
            texto = texto.replace(marca, "\n      P.k.....s", 1)
        if latigo:
            # el juego "de latigo": golpe con preparacion, clavado en el sitio,
            # y un empujon serio al recibir dano
            texto = texto.replace("    tipo: disparo", "    tipo: golpe", 1)
            texto = texto.replace(
                "    dano: 1\n",
                "    dano: 1\n    preparacion: 5\n    clavado: si\n", 1)
            texto = texto.replace("  vida: 2",
                                  "  vida: 2\n  retroceso: 3.0\n  aturdido: 24", 1)
        if tablon:
            # el andamiaje pone la plataforma movil en el segundo nivel y la
            # traza no llega: se pone una a la salida del primero, encima del
            # jugador, para que se suba a ella y la traza compare tambien eso
            marca = "\n      ..........c...........c..........c.............."
            assert marca in texto, "el primer nivel ya no tiene esa fila"
            texto = texto.replace(
                marca, "\n      ..T.......c...........c..........c..............", 1)
        if jefe:
            # el jefe del andamiaje vive en el segundo nivel y la traza no llega:
            # se pone uno en el primero, cambiando el enemigo que hay a la salida
            marca = "\n      P.......s"
            assert marca in texto, "el primer nivel ya no empieza asi"
            texto = texto.replace(marca, "\n      P.......J", 1)
        with open(yaml, "w", encoding="utf-8") as fh:
            fh.write(texto)
        build = cargar_demo(proyecto_dir)

        out = os.path.join(cls.tmp, "build-" + os.path.basename(proyecto_dir))
        os.makedirs(os.path.join(out, "src"))
        for relativo, contenido in generate_gamedata(build).items():
            with open(os.path.join(out, relativo), "w", encoding="utf-8") as fh:
                fh.write(contenido)
        copy_engine(out)

        datos = build_data(build)
        for hoja in datos["sheets"].values():
            hoja["url"] = ""            # la traza no necesita los graficos
        datos_json = os.path.join(cls.tmp, "datos-%s.json"
                                  % os.path.basename(proyecto_dir))
        with open(datos_json, "w", encoding="utf-8") as fh:
            json.dump(datos, fh)

        binario = os.path.join(cls.tmp,
                               "np_trace-" + os.path.basename(proyecto_dir))
        compilacion = subprocess.run(
            ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-I", os.path.join(out, "src"), "-o", binario,
             os.path.join(KIT, "engine", "host", "np_trace.c"),
             os.path.join(out, "src", "np_world.c"),
             os.path.join(out, "src", "gamedata.c")],
            capture_output=True, text=True,
        )
        if compilacion.returncode != 0:
            raise AssertionError("el motor en C no compila:\n" + compilacion.stderr)
        return (binario, datos_json)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def _trazas(self, semilla, camara="scroll"):
        binario, datos_json = self.variantes[camara]
        entradas = _secuencia(semilla)
        ruta = os.path.join(self.tmp, "inputs-%d.txt" % semilla)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("\n".join("%d %d" % par for par in entradas))
        traza_c = subprocess.run([binario, ruta], capture_output=True, text=True, check=True)
        traza_js = subprocess.run(
            ["node", os.path.join(KIT, "tests", "trace.js"), datos_json, ruta],
            capture_output=True, text=True, check=True,
        )
        return traza_c.stdout.strip().split("\n"), traza_js.stdout.strip().split("\n")

    def test_misma_traza(self):
        for camara in ("scroll", "pantallas"):
            for semilla in (1, 7, 99):
                self._comparar(camara, semilla)

    def test_misma_traza_disparando(self):
        """El andamiaje trae `ataque: disparo`, asi que las pulsaciones incluyen
        el boton de accion y la traza compara tambien los proyectiles: van en la
        misma lista de entidades y entran en el hash."""
        for semilla in (1, 7, 99):
            self._comparar("scroll", semilla)

    def test_misma_traza_pegando(self):
        """Y con `tipo: golpe`, que no saca proyectiles sino una caja delante."""
        for semilla in (1, 7, 99):
            self._comparar("golpe", semilla)

    def test_los_disparos_existen_de_verdad(self):
        """Si el boton de accion no llegara al motor, o los proyectiles no se
        crearan, la paridad pasaria sin comprobar nada de esto."""
        traza, _ = self._trazas(1, "scroll")
        hashes = {linea.split()[14] for linea in traza}
        self.assertGreater(len(hashes), 100,
                           "las entidades casi no cambian: no se esta disparando")
        # y matando enemigos se suben puntos sin pisarlos
        puntos = {int(linea.split()[8]) for linea in traza}
        self.assertGreater(max(puntos), 0, "no se ha matado a nadie")

    def test_misma_traza_con_llaves(self):
        """El andamiaje trae `llaves: 1` en el primer nivel: las dos
        implementaciones tienen que contar igual y abrir la meta a la vez."""
        for semilla in (1, 7, 99):
            self._comparar("llave", semilla)

    def test_la_meta_no_se_abre_sin_la_llave(self):
        """Y que la cerradura muerde de verdad: si el motor en C no mirase las
        llaves, la paridad seguiria pasando (JS haria lo mismo mal)."""
        traza, _ = self._trazas(1, "llave")
        columnas = [linea.split() for linea in traza]
        self.assertIn("1", {c[25] for c in columnas},
                      "en toda la traza no se coge ni una llave")
        for c in columnas:
            if c[5] == str(ESTADO_FIN_NIVEL):
                self.assertNotEqual(c[25], "0",
                                    "el nivel se ha acabado sin coger la llave")

    def test_misma_traza_con_plataformas_moviles(self):
        """Una plataforma movil se mueve antes que los jugadores y se lleva
        consigo al que va encima: si las dos implementaciones no lo hicieran en
        el mismo orden, las posiciones se irian a la primera vuelta."""
        for semilla in (1, 7, 99):
            self._comparar("tablon", semilla)

    def test_el_jugador_se_sube_a_la_plataforma(self):
        """Y que se sube de verdad: si nadie se montara, la paridad pasaria
        comparando una plataforma que va y viene sola."""
        traza, _ = self._trazas(1, "tablon")
        sola, _ = self._trazas(1, "scroll")
        columnas = [linea.split() for linea in traza]
        sin = [linea.split() for linea in sola]
        # el hash de entidades tiene que cambiar (hay una plataforma mas) y el
        # jugador tiene que acabar en otro sitio que sin ella
        self.assertNotEqual([c[14] for c in columnas], [c[14] for c in sin],
                            "la plataforma no esta en la lista de entidades")
        distintos = sum(1 for a, b in zip(columnas, sin) if a[2] != b[2])
        self.assertGreater(distintos, 20,
                           "la plataforma no cambia por donde pasa el jugador")

    def test_misma_traza_con_latigo(self):
        """El ataque con preparacion y clavado, y el empujon con aturdimiento:
        son tres cosas que tocan el control del jugador frame a frame, que es
        donde una diferencia entre C y JS se nota antes."""
        for semilla in (1, 7, 99):
            self._comparar("latigo", semilla)

    def test_el_aturdimiento_cambia_la_partida(self):
        """Si el aturdimiento no llegara al motor, la traza del latigo saldria
        igual que la del golpe normal y la paridad no comprobaria nada."""
        con, _ = self._trazas(1, "latigo")
        sin, _ = self._trazas(1, "golpe")
        distintos = sum(1 for a, b in zip(con, sin)
                        if a.split()[1] != b.split()[1])
        self.assertGreater(distintos, len(con) // 4,
                           "el latigo se juega igual que el golpe de siempre")

    def test_misma_traza_a_dos_jugadores(self):
        """Lo mismo con `jugadores: 2`: dos mandos, dos vidas, la camara en el
        punto medio y el que se queda atras pegado al borde."""
        for variante in ("dos", "dos-pantallas"):
            for semilla in (1, 7, 99):
                self._comparar(variante, semilla)

    def test_el_segundo_jugador_esta_de_verdad(self):
        """Si `jugadores: 2` no llegara al motor, el segundo se quedaria quieto
        en su sitio y la prueba de paridad pasaria sin comprobar nada."""
        traza, _ = self._trazas(1, "dos")
        columnas = [linea.split() for linea in traza]
        self.assertTrue(all(len(c) == 26 for c in columnas),
                        "la traza no trae las columnas del segundo jugador")
        # al empezar los dos estan dentro; luego el mando aleatorio puede
        # dejarlo sin vidas, y eso tambien tiene que salir igual en las dos
        self.assertEqual({c[23] for c in columnas[:200]}, {"1"},
                         "el segundo jugador no entra en juego")
        self.assertGreater(len({c[15] for c in columnas}), 50,
                           "el segundo jugador no se mueve")
        # y no van pegados: si hicieran lo mismo, media prueba sobraria
        distintos = sum(1 for c in columnas if c[1] != c[15])
        self.assertGreater(distintos, len(columnas) // 2,
                           "los dos jugadores hacen lo mismo")

    def test_a_un_jugador_el_segundo_no_existe(self):
        """Y con `jugadores: 1` el segundo se queda fuera: ni se dibuja, ni
        cuenta para la camara, ni le pasa nada."""
        traza, _ = self._trazas(1, "scroll")
        columnas = [linea.split() for linea in traza]
        self.assertEqual({c[23] for c in columnas}, {"0"},
                         "el segundo jugador esta en juego sin pedirlo")

    def _comparar(self, camara, semilla):
        if True:
            lineas_c, lineas_js = self._trazas(semilla, camara)
            self.assertEqual(len(lineas_c), len(lineas_js))
            for i, (a, b) in enumerate(zip(lineas_c, lineas_js)):
                if a != b:
                    self.fail(
                        "camara %s, semilla %d, frame %d:\n  C : %s\n  JS: %s\n"
                        "(columnas: frame x y vx vy estado salud vidas puntos camx camy nivel hash)"
                        % (camara, semilla, i + 1, a, b)
                    )

    def test_las_dos_camaras_no_dan_lo_mismo(self):
        """Si el modo de camara no llegara al motor, las dos trazas saldrian
        identicas y la prueba de paridad pasaria sin comprobar nada."""
        con_scroll, _ = self._trazas(1, "scroll")
        con_pantallas, _ = self._trazas(1, "pantallas")
        camaras_scroll = {l.split()[9] for l in con_scroll}
        camaras_pantallas = {l.split()[9] for l in con_pantallas}
        self.assertNotEqual(camaras_scroll, camaras_pantallas,
                            "las dos camaras dan el mismo recorrido")
        # con pantallas la camara solo se para en multiplos del ancho de pantalla
        # (o pegada al final del nivel)
        for valor in camaras_pantallas:
            x = int(valor)
            self.assertTrue(x % 320 == 0 or x == max(int(v) for v in camaras_pantallas),
                            "la camara por pantallas se ha parado en %d" % x)

    def test_el_jefe_hace_lo_mismo_en_las_dos(self):
        """El jefe cambia el marcador y termina el nivel: si el C y el JS no
        estuvieran de acuerdo en cuantos golpes le quedan, la traza lo dice."""
        traza_c, traza_js = self._trazas(3, "jefe")
        self.assertEqual(traza_c, traza_js)
        vidas = {linea.split()[13] for linea in traza_c}
        self.assertTrue(vidas - {"0"},
                        "la traza no llega a ver al jefe: no comprueba nada")

    def test_la_traza_tiene_contenido(self):
        lineas_c, _ = self._trazas(1)
        self.assertGreater(len(lineas_c), FRAMES)
        estados = {linea.split()[5] for linea in lineas_c}
        self.assertIn("1", estados, "el jugador nunca llega a jugar")
        posiciones = {linea.split()[1] for linea in lineas_c}
        self.assertGreater(len(posiciones), 50, "el jugador no se mueve")


if __name__ == "__main__":
    unittest.main()
