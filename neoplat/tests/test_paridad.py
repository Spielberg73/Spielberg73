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
IN_UP = 4
FRAMES = 3000
ESTADO_JUEGO = 1            # NP_STATE_PLAY
ESTADO_MURIENDO = 2         # NP_STATE_DYING
ESTADO_FIN_NIVEL = 3        # NP_STATE_LEVEL_END


BOTONES = [IN_RIGHT, IN_RIGHT, IN_RIGHT | IN_JUMP, IN_LEFT,
           IN_LEFT | IN_JUMP, IN_JUMP, IN_DOWN, 0, IN_START,
           IN_ACTION, IN_RIGHT | IN_ACTION, IN_LEFT | IN_ACTION,
           IN_UP | IN_ACTION, IN_UP]


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
        # el mismo golpe pero sin `sprite:`: el ataque no trae dibujo y no
        # tiene que meter nada en la lista de entidades
        cls.variantes["golpe-pelado"] = cls._preparar("scroll", golpe=True,
                                                      sin_dibujo=True)
        cls.variantes["llave"] = cls._preparar("scroll", llave=True)
        cls.variantes["tablon"] = cls._preparar("scroll", tablon=True)
        # El genero de latigo entero, tal y como sale de `ngplat nuevo`: trae
        # golpe con preparacion, clavado, retroceso, aturdimiento, escaleras,
        # candelabros y arma secundaria. Antes esto eran dos variantes
        # parcheando el yaml a mano; asi se comprueba lo que de verdad recibe
        # quien crea un proyecto.
        cls.variantes["castillo"] = cls._preparar("scroll", genero="castlevania")
        # La vista cenital: otro modo de movimiento entero (sin gravedad, ocho
        # direcciones, disparo hacia donde miras). Es el que mas se parece a
        # tener otro motor, asi que es el que mas falta hace comparar.
        cls.variantes["cenital"] = cls._preparar("scroll", cenital=True)
        # La vista de cinta: el mismo juego de arriba pero con una tercera
        # coordenada, la altura, que ademas es la unica que no se ve en la
        # traza mas que por lo que mueve la `y`. Por eso hay que compararla.
        cls.variantes["cinta"] = cls._preparar("scroll", cinta=True)
        # Y la cinta con la serie de golpes: puno, puno y remate. El remate
        # tumba, y un tumbado se mueve solo con el empujon que se llevo, asi
        # que si las dos no encadenaran igual, las entidades se separarian.
        cls.variantes["combo"] = cls._preparar("scroll", cinta=True, golpe=True,
                                               combo=True)
        # el mismo juego sin serie, para ver que la serie hace algo
        cls.variantes["sin-combo"] = cls._preparar("scroll", cinta=True,
                                                   golpe=True)
        # y con agarre: coger al que se tambalea, zarandearlo y lanzarlo. El
        # que sale lanzado vuela con su propia altura, que es la unica vez que
        # una entidad -y no el jugador- usa la tercera coordenada.
        cls.variantes["agarre"] = cls._preparar("scroll", cinta=True, golpe=True,
                                                combo=True, agarre=True)
        # La mazmorra: la vida que se gasta sola, los generadores que sacan
        # bichos y la pocima que limpia la pantalla. Son tres cosas que corren
        # **cada frame** en los dos motores, asi que van a la traza.
        cls.variantes["mazmorra"] = cls._preparar("scroll", genero="mazmorra")
        # La misma mazmorra con los nidos dormidos: sirve para probar que los
        # bichos que salen son de verdad de los generadores y no del mapa.
        cls.variantes["nidos-dormidos"] = cls._preparar("scroll",
                                                        genero="mazmorra",
                                                        nidos_dormidos=True)

    @classmethod
    def _preparar(cls, camara, jefe=False, dos=False, golpe=False, llave=False,
                  tablon=False, genero="plataformas", sin_dibujo=False,
                  cenital=False, nidos_dormidos=False, cinta=False,
                  combo=False, agarre=False):
        proyecto_dir = os.path.join(
            cls.tmp, "juego-" + camara + ("-jefe" if jefe else "")
            + ("-dos" if dos else "") + ("-golpe" if golpe else "")
            + ("-pelado" if sin_dibujo else "")
            + ("-llave" if llave else "") + ("-tablon" if tablon else "")
            + ("-cenital" if cenital else "")
            + ("-cinta" if cinta else "")
            + ("-combo" if combo else "")
            + ("-agarre" if agarre else "")
            + ("-dormidos" if nidos_dormidos else "")
            + ("-" + genero if genero != "plataformas" else ""))
        crear_proyecto(proyecto_dir, "PARIDAD", "TEST", genero=genero)
        yaml = os.path.join(proyecto_dir, "game.yaml")
        with open(yaml, encoding="utf-8") as fh:
            texto = fh.read()
        # el andamiaje ya trae 'camara: scroll': hay que cambiar esa linea, no
        # anadir otra, o el lector se queda con la ultima
        assert "  camara: scroll" in texto, "el andamiaje ya no trae la camara"
        texto = texto.replace("  camara: scroll", "  camara: " + camara, 1)
        if dos:
            texto = texto.replace("  vidas:", "  jugadores: 2\n  vidas:", 1)
        if cenital:
            # el mismo juego mirado desde arriba: sin gravedad, en ocho
            # direcciones y disparando hacia donde se mira
            texto = texto.replace("  vidas:", "  vista: cenital\n  vidas:", 1)
        if cinta:
            # y el mismo mirado desde arriba **pero saltando**: la vista de los
            # juegos de tortas, con la altura como tercera coordenada
            texto = texto.replace("  vidas:", "  vista: cinta\n  vidas:", 1)
            # y la seta aguanta unos cuantos golpes: con un solo punto de vida
            # el primer punetazo se la lleva y no hay serie que valga
            marca = "    comportamiento: patrulla\n"
            assert marca in texto, "el primer enemigo ya no es de patrulla"
            texto = texto.replace(marca, marca + "    vida: 9\n", 1)
        if golpe:
            # el mismo proyecto, pero con el ataque cuerpo a cuerpo: no salen
            # proyectiles y el dano lo hace una caja delante del jugador
            marca = "    tipo: disparo"
            assert marca in texto, "el andamiaje ya no trae el ataque asi"
            texto = texto.replace(marca, "    tipo: golpe", 1)
        if combo:
            # la serie de golpes, con su remate y su derribo
            marca = "    tipo: golpe"
            assert marca in texto, "el ataque ya no es de golpe"
            texto = texto.replace(
                marca,
                "    tipo: golpe\n    combo: 3\n    ventana: 24\n"
                "    dano_remate: 3\n    derribo: 40\n    empujon_remate: 2.5", 1)
        if agarre:
            # el bloque `agarre:` del jugador, con sus cuatro numeros
            marca = "  pisar_enemigos:"
            assert marca in texto, "el jugador ya no trae 'pisar_enemigos:'"
            texto = texto.replace(
                marca,
                "  agarre:\n    tiempo: 90\n    rodillazo: 2\n"
                "    lanzamiento: 4\n    fuerza: 4.0\n" + marca, 1)
        if sin_dibujo:
            # sin dibujo el golpe es invisible, que es como estaba el kit
            marca = "    sprite: graficos/bala.png\n"
            assert marca in texto, "el ataque del andamiaje ya no trae sprite"
            texto = texto.replace(marca, "", 1)
        if llave:
            # el andamiaje pone la llave en la plataforma mas alta y el mando
            # aleatorio no llega hasta alli: se pone otra a dos pasos de la
            # salida para que la traza compare tambien el momento de cogerla
            marca = "\n      P.......s"
            assert marca in texto, "el primer nivel ya no empieza asi"
            texto = texto.replace(marca, "\n      P.k.....s", 1)
        if genero == "castlevania":
            # El candelabro, la mejora del latigo, el hacha y el punto de
            # control estan repartidos por el nivel (el hacha, arriba de la
            # escalera) y el mando aleatorio no llega a ninguno: se juntan los
            # cuatro a la salida para que la traza compare tambien romperlo,
            # coger la municion, alargar el latigo, cambiar de arma secundaria
            # y, al morir, reaparecer en la antorcha en vez de en la salida.
            marca = "P.......s...V"
            assert marca in texto, "el primer nivel ya no empieza asi"
            texto = texto.replace(marca, "P.VMH!..s....", 1)
        if tablon:
            # el andamiaje pone la plataforma movil en el segundo nivel y la
            # traza no llega: se pone una a la salida del primero, encima del
            # jugador, para que se suba a ella y la traza compare tambien eso
            marca = "\n      ......................c..........c.............."
            assert marca in texto, "el primer nivel ya no tiene esa fila"
            texto = texto.replace(
                marca, "\n      ..T...................c..........c..............", 1)
        if genero == "mazmorra":
            # La pocima que limpia la pantalla esta al otro lado del laberinto
            # y el mando aleatorio no llega: se pone a la salida, con dos
            # bichos delante, para que la traza compare tambien el momento en
            # que revienta lo que se ve.
            marca = "      #####.###,###.######\n      #########P##########"
            assert marca in texto, "el laberinto ya no empieza asi"
            texto = texto.replace(
                marca,
                "      #####.###r###.######\n      #########P##########", 1)
            marca = "      #...#....,....#....#\n      #.f.,....,....,..r.#"
            assert marca in texto, "el laberinto ya no tiene esas filas"
            texto = texto.replace(
                marca,
                "      #...#...bbb...#....#\n      #.f.,....,....,..r.#", 1)
        if nidos_dormidos:
            # Los nidos siguen ahi, en el mismo sitio y contando en el hash,
            # pero con la espera al maximo -un minuto- no les da tiempo a sacar
            # nada en los 3000 frames que dura la traza.
            for antes, despues in (("    cada: 100", "    cada: 3600"),
                                   ("    cada: 150", "    cada: 3600")):
                assert antes in texto, "el generador ya no se escribe asi"
                texto = texto.replace(antes, despues, 1)
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

    def _trazas_de(self, variante, entradas, nombre):
        """Las dos trazas con unas pulsaciones dadas. Sirve para lo que no sale
        por casualidad con el mando aleatorio: ir a por un objeto concreto."""
        binario, datos_json = self.variantes[variante]
        ruta = os.path.join(self.tmp, "inputs-%s.txt" % nombre)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("\n".join("%d %d" % par for par in entradas))
        traza_c = subprocess.run([binario, ruta], capture_output=True, text=True,
                                 check=True)
        traza_js = subprocess.run(
            ["node", os.path.join(KIT, "tests", "trace.js"), datos_json, ruta],
            capture_output=True, text=True, check=True,
        )
        return traza_c.stdout.strip().split("\n"), traza_js.stdout.strip().split("\n")

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

    def test_misma_traza_mirando_desde_arriba(self):
        """La vista cenital es otro modo de movimiento entero -sin gravedad,
        en ocho direcciones y disparando hacia donde miras-, asi que es donde
        mas facil es que el motor en C y el del navegador se separen."""
        for semilla in (1, 7, 99):
            self._comparar("cenital", semilla)

    def test_desde_arriba_se_anda_en_vertical_de_verdad(self):
        """Si la vista cenital no llegara al motor, la traza seria la de un
        plataformas cualquiera y la paridad pasaria sin comprobar nada: aqui se
        mira que el jugador se mueve en vertical **sin estar cayendo**."""
        traza, _ = self._trazas(7, "cenital")
        alturas = {linea.split()[2] for linea in traza}
        self.assertGreater(len(alturas), 20,
                           "el jugador casi no cambia de altura")
        # y no es que se este cayendo: en cenital no hay gravedad, asi que
        # tiene que haber frames subiendo y frames bajando
        ys = [int(linea.split()[2]) for linea in traza]
        subiendo = sum(1 for i in range(1, len(ys)) if ys[i] < ys[i - 1])
        bajando = sum(1 for i in range(1, len(ys)) if ys[i] > ys[i - 1])
        self.assertGreater(subiendo, 20, "nunca sube: parece que hay gravedad")
        self.assertGreater(bajando, 20, "nunca baja")

    def test_misma_traza_en_la_mazmorra(self):
        """El genero de mazmorra mete tres cosas que corren cada frame: la vida
        que se gasta sola, los generadores que sacan bichos y la pocima que
        limpia lo que se ve. Las tres tienen que dar lo mismo en las dos."""
        for semilla in (1, 7, 99):
            self._comparar("mazmorra", semilla)

    def test_la_vida_se_gasta_sola(self):
        """Si el desgaste no llegara al motor en C, la paridad seguiria
        pasando: aqui se mira que la vida **baja sin que nadie pegue**, y que
        baja de uno en uno y no de golpe, que seria un enemigo."""
        traza, _ = self._trazas(1, "mazmorra")
        columnas = [linea.split() for linea in traza]
        jugando = [c for c in columnas if c[5] == str(ESTADO_JUEGO)]
        vidas = [int(c[6]) for c in jugando]
        self.assertGreater(len(set(vidas)), 20,
                           "la vida casi no cambia: no se esta gastando sola")
        bajadas = sum(1 for i in range(1, len(vidas))
                      if vidas[i] == vidas[i - 1] - 1)
        self.assertGreater(bajadas, 20,
                           "la vida no baja de punto en punto")

    def test_los_nidos_sacan_bichos_de_verdad(self):
        """Y que los bichos salen de los nidos, no del mapa: la misma mazmorra
        con los nidos dormidos -mismos nidos, mismo sitio, misma primera
        linea- tiene que dar otra traza en cuanto al primero le toca sacar."""
        despiertos, _ = self._trazas(1, "mazmorra")
        dormidos, _ = self._trazas(1, "nidos-dormidos")
        self.assertEqual(despiertos[0].split()[14], dormidos[0].split()[14],
                         "los dos empiezan con entidades distintas: la prueba "
                         "no compara los nidos sino el mapa")
        distintos = [i for i, (a, b) in enumerate(zip(despiertos, dormidos))
                     if a.split()[14] != b.split()[14]]
        self.assertTrue(distintos, "con los nidos dormidos pasa lo mismo: no "
                                   "estan sacando bichos")
        self.assertLess(distintos[0], 400,
                        "el primer bicho tarda demasiado en salir")

    def test_la_pocima_limpia_lo_que_se_ve(self):
        """La pocima de `efecto: bomba` revienta lo que hay en pantalla. Se
        coge andando hacia arriba desde la salida, con tres bichos delante: si
        no hiciera nada, los puntos serian los del frasco y nada mas."""
        entradas = [(IN_START, 0)] * 3 + [(IN_UP, 0)] * 240
        traza_c, traza_js = self._trazas_de("mazmorra", entradas, "pocima")
        self.assertEqual(traza_c, traza_js)
        with open(self.variantes["mazmorra"][1], encoding="utf-8") as fh:
            datos = json.load(fh)
        pocima = max(o["score"] for o in datos["items"] if o["effect"] == 7)
        bicho = min(e["score"] for e in datos["enemies"])
        puntos = max(int(linea.split()[8]) for linea in traza_c)
        self.assertGreaterEqual(
            puntos, pocima + 3 * bicho,
            "con %d puntos no ha reventado a los tres bichos" % puntos)

    def test_misma_traza_en_la_vista_de_cinta(self):
        """La vista de cinta anade una coordenada que no sale en la traza: la
        altura sobre el suelo. Se ve igual porque `y` es donde se dibuja, o sea
        el suelo menos la altura: si las dos implementaciones no saltaran
        exactamente igual, la `y` se separaria al primer salto."""
        for semilla in (1, 7, 99):
            self._comparar("cinta", semilla)

    def test_en_la_cinta_se_salta_de_verdad(self):
        """Y que se salta: sin esto la paridad compararia dos juegos cenitales
        y no comprobaria nada de la vista nueva. Lo que se mira es que la `y`
        sube y baja **sin que el jugador cambie de fila**, que es justo lo que
        hace un salto en esta vista: el dibujo se levanta y el suelo se queda.
        """
        traza, _ = self._trazas(7, "cinta")
        columnas = [linea.split() for linea in traza]
        jugando = [c for c in columnas if c[5] == str(ESTADO_JUEGO)]
        ys = [int(c[2]) for c in jugando]
        subidas = sum(1 for i in range(1, len(ys)) if ys[i] < ys[i - 1])
        bajadas = sum(1 for i in range(1, len(ys)) if ys[i] > ys[i - 1])
        self.assertGreater(subidas, 20, "nunca sube: no se esta saltando")
        self.assertGreater(bajadas, 20, "nunca baja")
        # y el salto llega alto: mas de lo que se anda en un frame
        self.assertGreater(max(ys) - min(ys), 16 * 256,
                           "el recorrido vertical es de menos de un tile")

    def test_misma_traza_con_la_serie_de_golpes(self):
        """Puno, puno y remate: el ultimo hace mas dano y tumba, y un tumbado
        se mueve solo con el empujon que se llevo. Si las dos implementaciones
        no contaran los golpes igual, las entidades se separarian en cuanto
        empieza el mando aleatorio a machacar el boton."""
        for semilla in (1, 7, 99):
            self._comparar("combo", semilla)

    def test_la_serie_de_golpes_cambia_la_partida(self):
        """Y que la serie hace algo: el mismo juego con `combo: 1` tiene que
        dar otra traza en cuanto caiga un remate. Con el mando aleatorio no
        cae ninguno -tres golpes seguidos en la misma ventana y encima de
        alguien es mucha casualidad-, asi que aqui se pega a proposito: se
        anda hasta el primer bicho y se machaca el boton."""
        entradas = ([(IN_START, 0)] * 3 + [(IN_RIGHT, 0)] * 80
                    + [(IN_ACTION, 0), (0, 0)] * 90)
        con, _ = self._trazas_de("combo", entradas, "combo")
        sin, _ = self._trazas_de("sin-combo", entradas, "sin-combo")
        self.assertEqual(con[0], sin[0],
                         "los dos juegos ya empiezan distintos")
        distintos = [i for i, (a, b) in enumerate(zip(con, sin)) if a != b]
        self.assertTrue(distintos,
                        "con serie y sin serie pasa lo mismo: no se esta "
                        "encadenando nada")
        # y la diferencia esta en las entidades (el remate tumba y empuja) o
        # en los puntos, no en un frame suelto de mas
        self.assertGreater(len(distintos), 10,
                           "solo cambia un frame: no parece un remate")

    def test_misma_traza_con_el_agarre(self):
        """Coger al que se tambalea, zarandearlo y lanzarlo. El que sale
        lanzado vuela con su propia altura -es la unica vez que una entidad y
        no el jugador usa la tercera coordenada-, asi que si las dos no
        calcularan igual el arco, la traza se separaria al primer lanzamiento.
        """
        for semilla in (1, 7, 99):
            self._comparar("agarre", semilla)

    def test_el_agarre_cambia_la_partida(self):
        """Y que el agarre hace algo: el mismo juego sin el bloque `agarre:`
        tiene que dar otra traza. Se pega y se anda hacia el bicho, que es lo
        que hace falta para agarrarlo."""
        entradas = ([(IN_START, 0)] * 3 + [(IN_RIGHT, 0)] * 80
                    + [(IN_ACTION, 0), (IN_RIGHT, 0), (IN_RIGHT, 0),
                       (IN_RIGHT, 0)] * 60)
        con, _ = self._trazas_de("agarre", entradas, "agarre")
        sin, _ = self._trazas_de("combo", entradas, "combo-mismo")
        self.assertEqual(con[0], sin[0],
                         "los dos juegos ya empiezan distintos")
        distintos = [i for i, (a, b) in enumerate(zip(con, sin)) if a != b]
        self.assertTrue(distintos, "con agarre y sin agarre pasa lo mismo")

    def test_misma_traza_con_el_genero_de_latigo(self):
        """El ataque con preparacion y clavado, y el empujon con aturdimiento:
        son tres cosas que tocan el control del jugador frame a frame, que es
        donde una diferencia entre C y JS se nota antes."""
        for semilla in (1, 7, 99):
            self._comparar("castillo", semilla)

    def test_el_aturdimiento_cambia_la_partida(self):
        """Si el aturdimiento no llegara al motor, la traza del latigo saldria
        igual que la del golpe normal y la paridad no comprobaria nada."""
        con, _ = self._trazas(1, "castillo")
        sin, _ = self._trazas(1, "golpe")
        distintos = sum(1 for a, b in zip(con, sin)
                        if a.split()[1] != b.split()[1])
        self.assertGreater(distintos, len(con) // 4,
                           "el latigo se juega igual que el golpe de siempre")

    def test_los_candelabros_y_el_arma_secundaria_pasan_de_verdad(self):
        """El andamiaje trae candelabros que sueltan municion y un arma
        secundaria que la gasta. Si no se rompiera ninguno, la paridad estaria
        comparando dos motores que no hacen nada de esto."""
        traza, _ = self._trazas(1, "castillo")
        municion = [int(linea.split()[26]) for linea in traza]
        self.assertGreater(max(municion), 0,
                           "en toda la traza no se rompe ni un candelabro")
        # y esa municion se gasta: si solo subiera, el arma no estaria saliendo
        gastos = sum(1 for a, b in zip(municion, municion[1:]) if b < a)
        self.assertGreater(gastos, 0, "la municion sube pero no se gasta nunca")

    def test_misma_traza_con_escaleras(self):
        """Las escaleras son un modo de movimiento entero -sin gravedad, sin
        saltos y sin choques- y se entra y se sale de el a mitad de frame. Si
        las dos implementaciones no coincidieran en cuando se entra, la traza
        se iria en el primer escalon."""
        for semilla in (1, 7, 99):
            self._comparar("castillo", semilla)

    def test_el_jugador_se_sube_a_la_escalera(self):
        """Y que se sube de verdad: si nadie se subiera, la paridad estaria
        comparando dos motores que no hacen nada de esto."""
        con, _ = self._trazas(1, "castillo")
        sin, _ = self._trazas(1, "scroll")
        distintos = sum(1 for a, b in zip(con, sin)
                        if a.split()[2] != b.split()[2])
        self.assertGreater(distintos, 20,
                           "la escalera no cambia por donde pasa el jugador")

    def test_el_punto_de_control_manda_al_reaparecer(self):
        """El punto de control tiene que cambiar **donde** reapareces, no solo
        encenderse: sin esto la paridad compararia dos motores que apuntan la
        casilla y luego la ignoran."""
        traza, _ = self._trazas(1, "castillo")
        columnas = [linea.split() for linea in traza]
        salida = int(columnas[0][1]) >> 8
        self.assertEqual({c[27] for c in columnas}, {"0", "1"},
                         "en toda la traza no se toca el punto de control")
        marcados = [c for c in columnas if c[27] == "1"]
        self.assertEqual({(c[28], c[29]) for c in marcados}, {("5", "14")},
                         "el punto de control apuntado no es el del mapa")
        # y el que reaparece despues de morir sale ahi, no en la salida
        vueltas = [b for a, b in zip(columnas, columnas[1:])
                   if a[5] == str(ESTADO_MURIENDO) and b[5] == str(ESTADO_JUEGO)]
        self.assertTrue(vueltas, "en toda la traza no se muere nadie")
        for c in vueltas:
            x = int(c[1]) >> 8
            self.assertGreater(x, salida + 32,
                               "se reaparece en la salida, no en la antorcha")
            self.assertLess(abs(x - 5 * 16), 16,
                            "se reaparece lejos de la casilla marcada")

    def test_la_mejora_del_latigo_se_coge_y_se_pierde(self):
        """La mejora sube el alcance del arma y se pierde al morir. Si no se
        cogiera ninguna, la paridad estaria comparando dos latigos de serie."""
        traza, _ = self._trazas(1, "castillo")
        columnas = [linea.split() for linea in traza]
        niveles = [int(c[30]) for c in columnas]
        self.assertGreater(max(niveles), 0,
                           "en toda la traza no se coge ni una mejora")
        # y despues de morir se vuelve a cero: si solo subiera, morir no dolria
        perdidas = sum(1 for a, b in zip(niveles, niveles[1:]) if b < a)
        self.assertGreater(perdidas, 0, "la mejora no se pierde nunca")

    def test_el_latigo_se_ve_y_dura_lo_que_hace_dano(self):
        """El latigo es una entidad mas de la lista, asi que ya entra en el
        hash de la paridad; esto comprueba que existe y **cuando**.

        Tiene que estar en pantalla exactamente los frames en los que el golpe
        hace dano: `duracion` menos `preparacion`, que en el andamiaje son
        14 - 5 = 9. Ni antes (durante la preparacion el brazo todavia sale) ni
        despues.
        """
        traza, _ = self._trazas(1, "castillo")
        latigo = [int(linea.split()[31]) for linea in traza]
        self.assertIn(1, latigo, "el latigo no aparece en toda la traza")
        self.assertIn(0, latigo, "el latigo no se quita nunca")
        rachas, cuenta = [], 0
        for valor in latigo + [0]:
            if valor:
                cuenta += 1
            elif cuenta:
                rachas.append(cuenta)
                cuenta = 0
        self.assertEqual(max(rachas), 9,
                         "el latigo no dura lo que dura el golpe: %s" % sorted(set(rachas)))
        self.assertGreater(len(rachas), 3, "casi no se pega en toda la traza")

    def test_sin_dibujo_no_hay_latigo(self):
        """Un golpe sin `sprite:` no mete nada en la lista, y un disparo
        tampoco: los proyectos que ya existian se juegan igual que antes."""
        for variante in ("golpe-pelado", "scroll"):
            traza, _ = self._trazas(1, variante)
            self.assertEqual({int(linea.split()[31]) for linea in traza}, {0},
                             "'%s' esta metiendo un latigo en la lista" % variante)

    def test_el_golpe_con_dibujo_lo_ensena(self):
        """Y con `sprite:`, el mismo golpe si lo saca: es lo unico que cambia
        entre las dos variantes."""
        traza, _ = self._trazas(1, "golpe")
        self.assertIn(1, [int(linea.split()[31]) for linea in traza],
                      "el golpe con dibujo no ensena nada")

    def test_agacharse_pasa_de_verdad(self):
        """El mando aleatorio pulsa abajo, asi que la traza ya compara la caja
        mas baja frame a frame; esto comprueba que se llega a usar.

        Los dos generos lo traen puesto: agacharse es del personaje, no del
        tipo de juego. Que sin `agachado:` no se agache nadie lo comprueba
        tests/comportamiento.js, que puede montar ese caso a mano."""
        for variante in ("castillo", "scroll"):
            traza, _ = self._trazas(1, variante)
            agachado = [int(linea.split()[32]) for linea in traza]
            self.assertGreater(sum(agachado), 20,
                               "en la traza de '%s' no se agacha nadie" % variante)

    def test_el_hacha_se_coge_y_cambia_el_arma(self):
        """El andamiaje trae dos armas secundarias -cuchillo y hacha- y el
        hacha esta arriba de la escalera del primer nivel. Sin esto, la
        paridad estaria comparando dos motores que siempre llevan la misma."""
        traza, _ = self._trazas(1, "castillo")
        armas = [int(linea.split()[33]) for linea in traza]
        self.assertEqual(armas[0], 0, "no se empieza con la primera arma")
        self.assertIn(1, armas, "en toda la traza no se coge el hacha")
        # y al cambiar de nivel se vuelve a la de serie
        self.assertEqual(sorted(set(armas)), [0, 1])

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
        self.assertTrue(all(len(c) == 34 for c in columnas),
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
