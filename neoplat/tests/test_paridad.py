"""El motor en C y el preview en JavaScript deben dar el mismo resultado.

Se ejecutan los dos con la misma secuencia de pulsaciones y se comparan las
trazas frame a frame: posicion, velocidad, camara, estado, puntos y un hash de
todas las entidades. Si alguien toca solo una de las dos implementaciones,
esta prueba lo detecta.
"""

import json
import math
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

# Columnas de la traza que se miran por su numero. Van aqui y no a mano en cada
# prueba porque la traza crece cada vez que el motor aprende algo -los guiones
# le anadieron cuatro- y contar desde el final se rompe sin avisar.
COL_BOLSA = 34            # lo que llevas encima, en un solo numero
COL_ABIERTOS = 35         # cuantos cerrojos se han abierto
COL_GUION = 36            # por que guion va (0 = ninguno)
COL_PASO = 37             # y por que paso
COL_PAGINAS = 38          # paginas de texto que le quedan al cuadro
COL_VARS = 39             # las variables, en un solo numero
COL_VERBO = 40            # el verbo elegido en una aventura grafica
COL_MARCHA = 41           # la marcha que lleva metida el coche
COL_TROMPO = 42           # y los frames que le quedan dando vueltas
COL_CARRETERA = 43        # la carretera que se ve, entera, en una firma
COL_CRONO = 44            # los frames que le quedan al reloj

# El genero de aventura empieza con un cuadro de texto que cuenta de que va, y
# hasta que no se pasa la partida no corre. Las pruebas que le dan un mando
# escrito a mano tienen que pasarlo primero, y pulsando **a golpes**: el cuadro
# avanza con el flanco de la tecla, asi que tenerla apretada no pasa de pagina
# (es a proposito: si no, un texto de tres paginas se lo comeria la pulsacion
# con la que se acaba el anterior).
IN_LEFT, IN_RIGHT, IN_DOWN, IN_JUMP, IN_START = 1, 2, 8, 16, 64
IN_ACTION = 32
IN_UP = 4
PASAR_TEXTO = [(IN_ACTION, 0), (0, 0)] * 8
FRAMES = 3000
ESTADO_JUEGO = 1            # NP_STATE_PLAY
ESTADO_MURIENDO = 2         # NP_STATE_DYING
ESTADO_FIN_NIVEL = 3        # NP_STATE_LEVEL_END


BOTONES = [IN_RIGHT, IN_RIGHT, IN_RIGHT | IN_JUMP, IN_LEFT,
           IN_LEFT | IN_JUMP, IN_JUMP, IN_DOWN, 0, IN_START,
           IN_ACTION, IN_RIGHT | IN_ACTION, IN_LEFT | IN_ACTION,
           IN_UP | IN_ACTION, IN_UP]


def _circuito(trafico: bool = False) -> str:
    """Un circuito para las pruebas: recta, curva a la derecha, ese y meta.

    Se escribe aqui y no a mano en el yaml porque son ciento veinte filas y
    porque asi las curvas son las que son -una pendiente que a punta no se pasa
    y levantando el pie si-, y no las que salgan de contar puntos a ojo en un
    editor de texto."""
    ancho, largo, carril = 40, 120, 7
    filas = []
    for i in range(largo):
        d = largo - 1 - i                    # distancia desde la salida
        if d < 30:
            centro = 20
        elif d < 70:                          # una curva a la derecha
            centro = 20 + int(round(8 * math.sin((d - 30) / 40.0 * math.pi)))
        else:                                 # y una ese
            centro = 20 + int(round(6 * math.sin((d - 70) / 25.0 * math.pi)))
        filas.append("".join(
            "#" if x in (0, ancho - 1)
            else ("." if abs(x - centro) <= carril // 2 else ",")
            for x in range(ancho)))
    filas[0] = filas[0].replace(".", "G")     # la meta, al final del todo
    if trafico:
        # Dos controles de paso -lineas enteras que cruzan la carretera- y
        # coches repartidos por el circuito, cada uno en su carril. Las filas
        # se eligen a mano y no al azar: una prueba que compara dos motores
        # tiene que dar siempre lo mismo.
        # La linea del control cruza **de lado a lado**, arcenes incluidos:
        # una meta volante no se cuela por la hierba. Si solo cubriera el
        # asfalto, un coche que se sale en la curva la pasaria de largo sin
        # cobrar el tiempo, que es justo lo que paso la primera vez.
        for fila in (largo - 25, largo - 40):
            filas[fila] = ("#" + "K" * (ancho - 2) + "#")
        # El primer coche va en mitad del carril y cerca de la salida: asi el
        # que va de frente sin tocar el volante choca con el, que es lo que
        # prueba el trompo. Los otros tres estan repartidos por el circuito.
        for fila, lado in ((largo - 11, 0), (largo - 55, 2),
                           (largo - 75, -3), (largo - 100, 1)):
            texto = list(filas[fila])
            libres = [i for i, ch in enumerate(texto) if ch == "."]
            centro = (libres[0] + libres[-1]) // 2
            texto[centro + lado] = "r"
            filas[fila] = "".join(texto)
    ultima = list(filas[-1])
    ultima[filas[-1].index(".") + carril // 2] = "P"
    filas[-1] = "".join(ultima)
    return ('  - nombre: "CIRCUITO"\n    mapa: |\n'
            + "\n".join("      " + f for f in filas) + "\n")


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
        # La carretera: conducir. Es la unica vista en la que el jugador no
        # anda -acelera-, y las cuentas del motor (las dos marchas, el roce, el
        # volante que manda segun la velocidad, el arrastre de la hierba y el
        # trompo) corren enteras cada frame. Un decimal de diferencia entre las
        # dos implementaciones se acumula y el coche llega a la curva a otra
        # velocidad, asi que es de las que mas falta hace comparar.
        cls.variantes["carretera"] = cls._preparar("scroll", carretera=True)
        # La misma carretera con lo que la convierte en un juego: el crono,
        # los controles de paso que regalan segundos y coches que adelantar.
        # El trafico se coloca solo en su carril mirando la cinta, asi que en
        # una curva las dos implementaciones tienen que ponerlo en el mismo
        # pixel o el jugador chocaria en una y pasaria de largo en la otra.
        cls.variantes["trafico"] = cls._preparar("scroll", carretera=True,
                                                 trafico=True)
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
        # La aventura: la bolsa, los cerrojos y el salto que no se manda. Los
        # tres corren en el jugador **cada frame**, y ademas la camara va de
        # pantalla en pantalla, que es otra manera de moverla.
        cls.variantes["aventura"] = cls._preparar("pantallas", genero="aventura")
        # La misma aventura sin la llave del primer nivel: sirve para probar
        # que la puerta se abre **con la llave** y no sola.
        cls.variantes["sin-llave"] = cls._preparar("pantallas", genero="aventura",
                                                   sin_llave=True)
        # El barrio entero, tal y como sale de `ngplat nuevo --genero barrio`:
        # la IA de pelea (colocarse, esperar turno, avisar, pegar y replegarse),
        # el tambaleo, la parada del impacto, la sacudida y el repertorio del
        # jugador. Es el genero que mas cosas mueve **cada frame** de todos, y
        # ademas la mitad son decisiones de la maquina: si las dos no decidieran
        # igual, se separarian al primer golpe.
        cls.variantes["barrio"] = cls._preparar("scroll", genero="barrio")
        # el mismo barrio con los enemigos sin golpe: vuelven a ser bichos que
        # hacen dano al tocarte, que es lo que eran antes. Sirve de control.
        cls.variantes["barrio-sin-golpe"] = cls._preparar("scroll", genero="barrio",
                                                          sin_golpe=True)
        # La mazmorra: la vida que se gasta sola, los generadores que sacan
        # bichos y la pocima que limpia la pantalla. Son tres cosas que corren
        # **cada frame** en los dos motores, asi que van a la traza.
        cls.variantes["mazmorra"] = cls._preparar("scroll", genero="mazmorra")
        # La misma mazmorra con los nidos dormidos: sirve para probar que los
        # bichos que salen son de verdad de los generadores y no del mapa.
        cls.variantes["nidos-dormidos"] = cls._preparar("scroll",
                                                        genero="mazmorra",
                                                        nidos_dormidos=True)
        # La isometrica: la tercera coordenada es de verdad -el suelo tiene
        # relieve-, el mapa que se pisa no es el que se dibuja, los cubos de la
        # sala se montan y se desmontan al cruzar una puerta y hasta los
        # jugadores entran en la fila de dibujado. Es la vista que mas cosas
        # hace distintas de todas, asi que es la que mas falta hace comparar.
        cls.variantes["iso"] = cls._preparar("pantallas", genero="filmation")
        # La misma sala con todo el relieve a cero: sin cubos, sin escalones y
        # sin nada a lo que subirse. Sirve de control -si las dos trazas de
        # arriba fueran iguales a estas, el relieve no estaria haciendo nada-.
        cls.variantes["iso-llano"] = cls._preparar("pantallas",
                                                   genero="filmation",
                                                   sin_relieve=True)
        # El kung-fu: trepar por lianas, la patada voladora, el fuego amigo
        # entre bichos y los perseguidores que se recolocan al cambiar de
        # pantalla. Las cuatro cosas deciden **cada frame** -donde se agarra
        # uno, si el golpe que sale es el punetazo o la patada, a quien le
        # entra y por que borde vuelven a entrar los que te siguen-, asi que si
        # los dos motores no decidieran igual se separarian en la primera sala.
        cls.variantes["kungfu"] = cls._preparar("pantallas", genero="kungfu")
        # El mismo templo sin lianas: las casillas de liana siguen ahi y no
        # hacen nada. Sirve de control -si las dos trazas fueran iguales, la
        # de arriba no estaria probando que se trepa-.
        cls.variantes["kungfu-sin-liana"] = cls._preparar("pantallas",
                                                          genero="kungfu",
                                                          sin_liana=True)
        # Los guiones: variables, condiciones, cuadros de texto y un disparador
        # en el mapa. Es la primera cosa del kit que **para** la partida, asi
        # que si los dos interpretes no fueran paso a paso iguales, uno seguiria
        # jugando mientras el otro lee y se separarian en el acto.
        cls.variantes["guiones"] = cls._preparar("scroll", guiones=True)
        # La aventura grafica: el cursor, los cuatro verbos y las casillas que
        # contestan. Aqui no hay fisica que comparar -un cursor no cae ni
        # choca- pero si hay algo que no habia en ninguna otra vista: **el
        # mando decide que guion se lanza**. Un boton cambia de verbo y el otro
        # senala, asi que si los dos motores no llevaran el mismo verbo en el
        # mismo frame, uno miraria la puerta mientras el otro la abre.
        cls.variantes["grafica"] = cls._preparar("pantallas", genero="grafica")

    @classmethod
    def _preparar(cls, camara, jefe=False, dos=False, golpe=False, llave=False,
                  tablon=False, genero="plataformas", sin_dibujo=False,
                  cenital=False, nidos_dormidos=False, cinta=False,
                  combo=False, agarre=False, sin_llave=False,
                  sin_golpe=False, sin_relieve=False, sin_liana=False,
                  guiones=False, carretera=False, trafico=False):
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
            + ("-sinllave" if sin_llave else "")
            + ("-singolpe" if sin_golpe else "")
            + ("-llano" if sin_relieve else "")
            + ("-sinliana" if sin_liana else "")
            + ("-guiones" if guiones else "")
            + ("-carretera" if carretera else "")
            + ("-trafico" if trafico else "")
            + ("-" + genero if genero != "plataformas" else ""))
        crear_proyecto(proyecto_dir, "PARIDAD", "TEST", genero=genero)
        yaml = os.path.join(proyecto_dir, "game.yaml")
        with open(yaml, encoding="utf-8") as fh:
            texto = fh.read()
        # el andamiaje ya trae 'camara: scroll': hay que cambiar esa linea, no
        # anadir otra, o el lector se queda con la ultima
        # El genero de aventura sale ya con la camara de pantallas: es media
        # gracia del genero, asi que ahi no se cambia.
        if genero in ("aventura", "filmation", "kungfu", "grafica"):
            assert "  camara: pantallas" in texto, \
                "el genero '%s' ya no trae la camara de pantallas" % genero
        elif True:
            assert "  camara: scroll" in texto, "el andamiaje ya no trae la camara"
            texto = texto.replace("  camara: scroll", "  camara: " + camara, 1)
        if sin_liana:
            # el mismo templo con `trepa: 0`: las casillas de liana se quedan
            # donde estan y dejan de agarrar, que es lo unico que cambia
            marca = "  trepa: 1.1"
            assert marca in texto, "el andamiaje de kung-fu ya no trae trepa"
            texto = texto.replace(marca, "  trepa: 0", 1)
        if guiones:
            # variables, un guion con condicion y cuadros de texto, un
            # disparador en el mapa y un guion de bienvenida en el nivel
            marca = "\nniveles:\n"
            assert marca in texto, "el andamiaje ya no escribe asi los niveles"
            texto = texto.replace(marca, """
variables:
  visitas: 0
  puerta: 0

guiones:
  cartel:
    - sumar: {visitas: 1}
    - si: {visitas: 1}
      pasos:
        - decir: "CUIDADO CON EL FOSO QUE HAY MAS ADELANTE, VIAJERO."
        - poner: {puerta: 1}
      si_no:
        - decir: "TE LO DIJE."
    - esperar: 6
  bienvenida:
    - decir: "EL BOSQUE MAGICO"
    - sumar: {visitas: 0}

niveles:
""", 1)
            marca = "    '.': {tile: 0, tipo: vacio}"
            assert marca in texto, "la leyenda ya no empieza asi"
            texto = texto.replace(
                marca, marca + "\n    'X': {tile: 0, tipo: vacio, guion: cartel}", 1)
            # el guion de bienvenida en el primer nivel
            marca = '  - nombre: "'
            i = texto.index(marca)
            j = texto.index("\n", i)
            texto = texto[:j + 1] + "    guion: bienvenida\n" + texto[j + 1:]
            # y el disparador en el suelo, unas casillas a la derecha
            marca = "      P.......s"
            assert marca in texto, "el primer nivel ya no empieza asi"
            texto = texto.replace(marca, "      P....X..s", 1)
        if dos:
            texto = texto.replace("  vidas:", "  jugadores: 2\n  vidas:", 1)
        if cenital:
            # el mismo juego mirado desde arriba: sin gravedad, en ocho
            # direcciones y disparando hacia donde se mira
            texto = texto.replace("  vidas:", "  vista: cenital\n  vidas:", 1)
        if carretera:
            # el mismo mundo, conduciendo: el mapa es el trazado y el coche lo
            # sube. Lo que hay que comparar es el motor -las dos marchas, el
            # roce, el arrastre de la hierba y el trompo-, y todo eso corre en
            # el jugador cada frame: si las dos implementaciones no hicieran las
            # mismas cuentas con los mismos enteros, el coche llegaria a la
            # curva con velocidades distintas y de ahi no se recupera.
            texto = texto.replace("  vidas:", "  vista: carretera\n  vidas:", 1)
            texto = texto.replace("\njugador:", '''
coche:
  punta: 6.0
  punta_corta: 3.2
  volante: 2.2
  lento: 1.6
  trompo: 40

jugador:''', 1)
            # la hierba: lo que hay fuera del asfalto. No para -se pasa por
            # encima- pero ahi no se corre, que es lo que hace que salirse
            # cueste tiempo en vez de matarte
            marca = "    '#': {tile: 1, tipo: solido}"
            assert marca in texto, "la leyenda ya no trae el solido asi"
            texto = texto.replace(
                marca, marca + "\n    ',': {tile: 1, tipo: hierba}", 1)
            # Y el circuito: sin esto el nivel seria el del juego de
            # plataformas -todo asfalto y sin bordes-, la carretera saldria
            # recta en todos los frames y la proyeccion no se estaria
            # comparando en lo unico donde hace algo, que es una curva.
            marca = "\nniveles:\n"
            assert marca in texto, "el andamiaje ya no escribe asi los niveles"
            texto = texto[:texto.index(marca)] + marca + _circuito(trafico)
        if trafico:
            # El crono, los controles de paso que lo alargan y coches que
            # adelantar. Las tres cosas corren cada frame en los dos motores.
            # El andamiaje ya trae 'tiempo: 0': hay que cambiar esa linea, no
            # anadir otra, o el lector se queda con la ultima y el crono no
            # correria (que es justo lo que paso la primera vez).
            marca = "  tiempo: 0"
            assert marca in texto, "el andamiaje ya no trae el tiempo asi"
            texto = texto.replace(marca, "  tiempo: 60", 1)
            texto = texto.replace("  trompo: 40",
                                  "  trompo: 40\n  control: 15", 1)
            marca = "    '#': {tile: 1, tipo: solido}"
            texto = texto.replace(
                marca, marca + "\n    'K': {tile: 1, tipo: control}", 1)
            # el coche de delante: usa el dibujo del primer enemigo y no pega,
            # solo estorba
            marca = "\nspawns:\n"
            assert marca in texto, "el andamiaje ya no escribe asi los spawns"
            texto = texto.replace(marca, marca + "  r: rival\n", 1)
            marca = "\nenemigos:\n"
            assert marca in texto, "el andamiaje ya no escribe asi los enemigos"
            texto = texto.replace(marca, """
enemigos:
  rival:
    sprite: graficos/enemigo.png
    frame: [16, 16]
    caja: [14, 14]
    comportamiento: trafico
    velocidad: 2.4
    vida: 99
""", 1)
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
        if sin_golpe:
            # se les quita el bloque `golpe:` entero -renombrandolo, para que
            # el mapa y todo lo demas se queden igual- y vuelven a ser bichos
            # que hacen dano al tocarte
            marca = "    golpe:\n"
            assert texto.count(marca) == 3, "el barrio ya no trae tres golpes"
            texto = texto.replace(marca, "    sin_golpe:\n")
        if sin_relieve:
            # el mismo castillo sin relieve: todo lo que levantaba se queda a
            # ras de suelo y sin cubo, asi que no hay nada a lo que subirse ni
            # nada que tape a nadie
            for marca in ("'o': {tile: 0, tipo: solido, alto: 16, cubo: losa}",
                          "'O': {tile: 0, tipo: solido, alto: 32, cubo: pilar}",
                          "'#': {tile: 0, tipo: solido, alto: 48, cubo: pintado}",
                          "'M': {tile: 0, tipo: solido, alto: 48, cubo: muro}",
                          "'A': {tile: 0, tipo: solido, alto: 16, cubo: antorcha}"):
                assert marca in texto, "la leyenda isometrica ya no dice: " + marca
                simbolo = marca.split(":")[0]
                texto = texto.replace(
                    marca, "%s: {tile: 0, tipo: vacio}" % simbolo, 1)
        if sin_llave:
            # se quita la llave del primer nivel dejando el mapa igual: la
            # puerta sigue ahi y el camino tambien, lo unico que falta es con
            # que abrirla
            marca = "      ..P......k.........."
            assert marca in texto, "el primer nivel ya no empieza asi"
            texto = texto.replace(marca, "      ..P.................", 1)
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

    def test_misma_traza_en_el_barrio(self):
        """El genero de tortas entero: la IA de pelea decide cada frame -a que
        distancia se pone cada uno, quien tiene turno, cuando avisa y cuando
        suelta- y ademas estan el tambaleo, la parada del impacto y la sacudida
        de la camara. Media docena de decisiones por bicho y por frame: si las
        dos implementaciones no las tomaran igual, se separarian enseguida."""
        for semilla in (1, 7, 99):
            self._comparar("barrio", semilla)

    def test_en_el_barrio_los_enemigos_pelean_de_verdad(self):
        """Y que lo que hacen es pelear y no rozarte.

        Con golpe, un enemigo se coloca a su distancia y no se te mete dentro:
        lo que te quita vida es su golpe. Sin golpe -el mismo mapa, los mismos
        bichos, la misma traza de mando- vuelven a hacer dano al tocarte, y eso
        se ve en la traza: te alcanzan antes y te cuesta mas vida."""
        con, _ = self._trazas(1, "barrio")
        sin, _ = self._trazas(1, "barrio-sin-golpe")
        self.assertNotEqual(con, sin, "con golpe y sin golpe pasa lo mismo: el "
                                      "bloque `golpe:` no esta haciendo nada")
        # Lo que se mide es **cuantas veces cobra** en la misma partida. Uno
        # que pelea tiene que colocarse, avisar, soltar y recuperarse, y entre
        # golpe y golpe te deja en paz; uno que hace dano al rozarte te va
        # quitando vida cada vez que se le acaba el parpadeo. La vida del
        # jugador va en la columna 6.
        def veces_que_cobra(traza):
            vida = [int(l.split()[6]) for l in traza]
            return sum(1 for i in range(1, len(vida)) if vida[i] < vida[i - 1])
        peleando = veces_que_cobra(con)
        rozando = veces_que_cobra(sin)
        self.assertGreater(rozando, peleando,
                           "rozando se cobra lo mismo que peleando (%d y %d): "
                           "el bloque `golpe:` no cambia como hacen dano"
                           % (rozando, peleando))

    def test_la_parada_del_impacto_pasa_de_verdad(self):
        """El congelado: al acertar, el mundo se para unos frames. Se ve en la
        traza porque el numero de frame sigue subiendo y **nada mas cambia**:
        misma posicion, misma camara, mismo hash de entidades. Si no existiera,
        no habria dos frames seguidos identicos en toda la partida."""
        traza, _ = self._trazas(7, "barrio")
        columnas = [linea.split() for linea in traza]
        parados = 0
        for i in range(1, len(columnas)):
            a, b = columnas[i - 1], columnas[i]
            if a[5] != str(ESTADO_JUEGO) or b[5] != str(ESTADO_JUEGO):
                continue
            # todo igual menos el frame (columna 0) y los eventos de sonido (12)
            if a[1:12] == b[1:12] and a[14] == b[14]:
                parados += 1
        self.assertGreater(parados, 20,
                           "solo %d frames parados: el impacto no congela nada"
                           % parados)

    def test_misma_traza_en_la_isometrica(self):
        """La vista isometrica mete cuatro cosas que no hay en ninguna otra: el
        suelo con relieve -por el que se anda, se sube y se cae-, un mapa que
        no es el que se dibuja, los cubos de la sala montandose y
        desmontandose al cruzar una puerta, y una fila de dibujado en la que
        entran hasta los jugadores. Las cuatro corren cada frame."""
        for semilla in (1, 7, 99):
            self._comparar("iso", semilla)

    def test_misma_traza_con_guiones(self):
        """Los guiones **paran** la partida: mientras hay un cuadro de texto no
        se mueve nadie, ni el reloj. Es la primera cosa del kit que hace eso, y
        si los dos interpretes no fueran paso a paso iguales -el mismo salto en
        el mismo `si`, la misma pagina en el mismo frame- uno seguiria jugando
        mientras el otro lee. La traza mira ademas por que guion va, en que
        paso y cuanto valen las variables."""
        for semilla in (3, 17, 88):
            self._comparar("guiones", semilla)

    def test_misma_traza_en_la_aventura_grafica(self):
        """La vista de puntero mete una cosa que no hay en ninguna otra: lo que
        pasa al pulsar **depende de un estado que lleva el propio mando**, el
        verbo. Cambiar de verbo, senalar una casilla, lanzar el guion que le
        toca a ese verbo y quitar del mapa lo que se coge son cuatro decisiones
        por frame, y la traza mira las cuatro (el verbo va en su columna y en
        la firma de la bolsa, y las casillas quitadas en la de abiertos)."""
        for semilla in (5, 23, 71):
            self._comparar("grafica", semilla)

    def test_el_verbo_cambia_lo_que_pasa(self):
        """Control del anterior: la misma casilla, dos verbos distintos.

        Se va al cuadro del estudio y se pulsa accion con 'mirar' puesto; luego
        lo mismo pero pasando antes al verbo 'hablar'. Los dos motores tienen
        que contestar lo mismo **y** las dos partidas tienen que salir
        distintas: si acabaran iguales, el verbo no estaria decidiendo nada."""
        # El cursor sale en la fila 12, columna 15; el cuadro esta en las
        # casillas 4 y 5 de las filas 2 y 3. A 2.4 pixeles por frame son 75
        # frames a la izquierda y 65 hacia arriba, con margen.
        ir = ([(IN_START, 0)] * 3 + PASAR_TEXTO * 2
              + [(IN_LEFT, 0)] * 80 + [(IN_UP, 0)] * 70)
        mirar = ir + [(IN_ACTION, 0), (0, 0)] * 12
        # tres toques del boton de saltar para pasar de 'mirar' a 'hablar'
        hablar = ir + [(IN_JUMP, 0), (0, 0)] * 3 + [(IN_ACTION, 0), (0, 0)] * 12
        mirar_c, mirar_js = self._trazas_de("grafica", mirar, "verbo-mirar")
        hablar_c, hablar_js = self._trazas_de("grafica", hablar, "verbo-hablar")
        self.assertEqual(mirar_c, mirar_js)
        self.assertEqual(hablar_c, hablar_js)
        self.assertNotEqual(mirar_c, hablar_c,
                            "mirar el cuadro y hablarle acaban igual: el verbo "
                            "no esta eligiendo guion")

    def test_misma_traza_en_el_kungfu(self):
        """El genero de kung-fu mete cuatro cosas en el bucle: agarrarse a una
        liana -que se puede hacer en el aire-, subir y bajar por ella, el golpe
        que cambia de forma segun se este pisando o no, y los perseguidores que
        al cambiar de pantalla se recolocan en el borde por el que has entrado.
        Las cuatro son decisiones por frame, asi que los dos motores tienen que
        tomarlas iguales o se separan en la primera sala."""
        for semilla in (2, 13, 61):
            self._comparar("kungfu", semilla)

    def test_la_liana_hace_algo(self):
        """Control del anterior: el mismo templo con `trepa: 0`.

        Se anda a la derecha hasta la liana y se pulsa arriba. Con `trepa:` uno
        se agarra y sube; con `trepa: 0` las mismas casillas no hacen nada y se
        queda en el suelo. Si las dos partidas acabaran igual, la prueba de
        arriba estaria comparando dos motores que no trepan."""
        # La liana del templo esta en la segunda pantalla, a 480 pixeles de la
        # salida: a 1.5 por frame son 300 andando, y ahi se para y se pulsa
        # arriba. Pasarse de largo no vale -detras esta Yamo, que te devuelve-,
        # asi que el numero es el que es.
        entradas = ([(IN_START, 0)] * 3 + [(IN_RIGHT, 0)] * 300
                    + [(IN_UP, 0)] * 240)
        con_c, con_js = self._trazas_de("kungfu", entradas, "liana-si")
        sin_c, sin_js = self._trazas_de("kungfu-sin-liana", entradas, "liana-no")
        self.assertEqual(con_c, con_js)
        self.assertEqual(sin_c, sin_js)
        # la columna 2 es la y del jugador: trepando se sube, y subir es que y
        # se haga mas pequena
        con_y = min(int(l.split()[2]) for l in con_c)
        sin_y = min(int(l.split()[2]) for l in sin_c)
        self.assertLess(
            con_y, sin_y,
            "con lianas y sin ellas se sube igual (y=%d y y=%d): 'trepa:' no "
            "esta haciendo nada" % (con_y, sin_y))

    def test_el_relieve_frena(self):
        """Control del anterior: el mismo castillo con todo a ras de suelo.

        Se anda hacia el norte y nada mas. Con relieve, el cubo que hay dos
        casillas mas arriba **para** al jugador; sin relieve no hay cubo, no
        hay pared y no hay nada, asi que sigue hasta el borde del mapa. Si el
        `alto:` de la leyenda no hiciera nada, las dos partidas acabarian en el
        mismo sitio y las pruebas de paridad de arriba estarian comparando dos
        motores que no hacen nada."""
        entradas = [(IN_START, 0)] * 3 + [(IN_UP, 0)] * 240
        con_c, con_js = self._trazas_de("iso", entradas, "relieve-si")
        sin_c, sin_js = self._trazas_de("iso-llano", entradas, "relieve-no")
        self.assertEqual(con_c, con_js)
        self.assertEqual(sin_c, sin_js)
        # la columna 2 es la y del jugador, y hacia el norte va bajando
        con_y = min(int(l.split()[2]) for l in con_c)
        sin_y = min(int(l.split()[2]) for l in sin_c)
        self.assertGreater(
            con_y, sin_y,
            "con relieve y sin el se llega igual de lejos (y=%d y y=%d): el "
            "`alto:` de la leyenda no esta frenando nada" % (con_y, sin_y))

    def test_al_cambiar_de_sala_cambian_los_cubos(self):
        """Cruzar una puerta desmonta los cubos de la sala y monta los de la
        siguiente. Va en el hash de entidades de la traza, asi que si las dos
        implementaciones no montaran lo mismo -o no en el mismo orden- se
        separarian en el primer cruce.

        Se comprueba que el cruce **pasa** en la partida que se compara: si el
        jugador no llegara a salir de la primera habitacion, la prueba de
        paridad de arriba no estaria mirando nada de esto."""
        entradas = [(IN_START, 0)] * 3 + [(IN_RIGHT, 0)] * 300
        traza_c, traza_js = self._trazas_de("iso", entradas, "sala")
        self.assertEqual(traza_c, traza_js)
        # la columna 1 es la x del jugador: al cruzar pasa de la primera sala
        # (0..127 pixeles de planta) a la segunda
        xs = [int(l.split()[1]) for l in traza_c]
        self.assertGreater(max(xs), 128,
                           "el jugador no ha salido de la primera sala: "
                           "llego a x=%d" % max(xs))

    def test_misma_traza_en_la_aventura(self):
        """El genero de aventura mete tres cosas en el bucle del jugador: la
        bolsa, los cerrojos y un salto que no se manda en el aire. Las tres
        tienen que dar lo mismo en las dos implementaciones."""
        for semilla in (1, 7, 99):
            self._comparar("aventura", semilla)

    def test_la_puerta_se_abre_con_la_llave(self):
        """Y que la puerta se abre **con la llave**, no sola.

        Andando hacia la derecha se coge la llave del suelo y se llega a la
        puerta, que esta en la pantalla siguiente. Con la llave se pasa; sin
        ella -el mismo mapa, la misma puerta, pero sin llave que coger- el
        jugador se queda plantado delante. Si el cerrojo no frenara, las dos
        partidas acabarian en el mismo sitio y esta prueba no valdria nada."""
        entradas = ([(IN_START, 0)] * 3 + PASAR_TEXTO + [(IN_RIGHT, 0)] * 600)
        traza_c, traza_js = self._trazas_de("aventura", entradas, "puerta")
        self.assertEqual(traza_c, traza_js)
        sin_c, sin_js = self._trazas_de("sin-llave", entradas, "sin-llave")
        self.assertEqual(sin_c, sin_js)
        # la puerta esta en la casilla 26, o sea en x = 416
        con_llave = max(int(linea.split()[1]) for linea in traza_c) // 256
        sin_llave = max(int(linea.split()[1]) for linea in sin_c) // 256
        self.assertGreater(con_llave, 432,
                           "con la llave no ha pasado la puerta: x=%d" % con_llave)
        self.assertLess(sin_llave, 416,
                        "sin llave ha pasado igual: x=%d" % sin_llave)
        # y que la ha gastado: la ultima columna es cuantas casillas ha abierto
        self.assertGreater(int(traza_c[-1].split()[COL_ABIERTOS]), 0,
                           "no ha abierto ninguna casilla")
        self.assertEqual(int(sin_c[-1].split()[COL_ABIERTOS]), 0,
                         "sin llave ha abierto algo igualmente")

    def test_el_salto_de_la_aventura_no_se_manda(self):
        """El salto fijo: en el aire el mando no mueve. Se salta parado y se
        empuja a la derecha; la `x` no puede cambiar hasta aterrizar."""
        entradas = ([(IN_START, 0)] * 3 + PASAR_TEXTO + [(0, 0)] * 20
                    + [(IN_JUMP, 0)] + [(IN_RIGHT, 0)] * 40)
        traza_c, traza_js = self._trazas_de("aventura", entradas, "salto-fijo")
        self.assertEqual(traza_c, traza_js)
        columnas = [linea.split() for linea in traza_c]
        # desde que despega hasta que vuelve a tener vy 0, la x no se mueve
        volando = [c for c in columnas if c[4] != "0"]
        self.assertGreater(len(volando), 20, "no ha llegado a saltar")
        self.assertEqual(len(set(c[1] for c in volando)), 1,
                         "se ha movido en el aire: el salto no es fijo")

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

    def test_misma_traza_conduciendo(self):
        """La carretera: aqui el jugador no anda, acelera. Cada frame se hacen
        las mismas cuentas -la marcha, el empuje, el roce o el freno, el tope
        de la marcha, el arrastre de la hierba y el volante partido por la
        punta- y todas con enteros. Un solo redondeo distinto se acumula frame
        a frame, asi que si las dos implementaciones no fueran la misma, las
        trazas se separarian antes de la primera curva."""
        for semilla in (1, 7, 99):
            self._comparar("carretera", semilla)

    def test_conduciendo_hay_marchas_y_trompos(self):
        """Y que se conduce de verdad: sin esto la paridad compararia dos
        coches parados y no comprobaria nada.

        Con el mando aleatorio no sale -el acelerador hay que **mantenerlo**, y
        una tirada al azar lo suelta cada dos por tres-, asi que aqui se
        conduce a proposito: pie a fondo, se mete la larga y se sigue recto
        hasta lo que haya delante. Se mira que las dos implementaciones cambian
        de marcha en el mismo frame, corren lo mismo y se estrellan a la vez.
        """
        entradas = [(IN_START, 0), (IN_START, 0), (0, 0)]
        entradas += [(IN_ACTION, 0)] * 60          # a fondo con la corta
        entradas += [(IN_ACTION | IN_JUMP, 0)]     # y se mete la larga
        entradas += [(IN_ACTION, 0)] * 500
        traza_c, traza_js = self._trazas_de("carretera", entradas, "conducir")
        self.assertEqual(traza_c, traza_js,
                         "el motor en C y el preview no conducen igual")
        columnas = [linea.split() for linea in traza_c]
        jugando = [c for c in columnas if c[5] == str(ESTADO_JUEGO)]
        self.assertTrue(jugando, "no se llega a jugar")
        self.assertEqual(set(c[COL_MARCHA] for c in jugando), {"0", "1"},
                         "no se cambia de marcha")
        # la marcha corta da 3.2 px/frame (819 en 24.8) y ni uno mas
        corta = [(-int(c[4])) for c in jugando if c[COL_MARCHA] == "0"]
        self.assertEqual(max(corta), 819,
                         "la marcha corta no se queda en su tope")
        # y con la larga metida se pasa de ahi
        larga = [(-int(c[4])) for c in jugando if c[COL_MARCHA] == "1"]
        self.assertGreater(max(larga), 819,
                           "con la larga no se corre mas que con la corta")
        # y de frente contra la pared del final del mapa: un trompo
        self.assertTrue(any(int(c[COL_TROMPO]) for c in jugando),
                        "no se estrella contra nada en todo el recorrido")
        # Y que la carretera que se ve **existe y se mueve**: sin esto la
        # comparacion de arriba estaria dando por buenas dos firmas a cero, que
        # es lo que sale cuando no se dibuja carretera ninguna.
        firmas = [c[COL_CARRETERA] for c in jugando]
        self.assertNotIn("00000000", firmas,
                         "hay frames sin carretera que dibujar")
        self.assertGreater(len(set(firmas)), 20,
                           "la carretera no cambia: no se esta avanzando")

    def test_la_carretera_que_se_ve_es_la_misma_en_los_dos(self):
        """La tabla de lineas -por donde pasa el eje, cuanto mide de ancho y
        que franja toca, en cada una de las 224 lineas- es lo unico que
        necesitan las ocho maquinas para dibujar la carretera. Si el preview y
        el motor en C no la sacaran identica, el juego que se prueba en el
        navegador no seria el que sale de la ROM.

        Aqui se conduce por una curva a proposito, que es donde la proyeccion
        hace algo: en una recta las dos podrian estar equivocadas igual."""
        entradas = [(IN_START, 0), (IN_START, 0), (0, 0)]
        entradas += [(IN_ACTION, 0)] * 60
        entradas += [(IN_ACTION | IN_JUMP, 0)]
        entradas += [(IN_ACTION, 0)] * 120
        entradas += [(IN_ACTION | IN_RIGHT, 0)] * 60      # a la derecha
        entradas += [(IN_ACTION | IN_LEFT, 0)] * 120      # y a la izquierda
        traza_c, traza_js = self._trazas_de("carretera", entradas, "curva")
        self.assertEqual(traza_c, traza_js,
                         "la carretera no se ve igual en el C y en el preview")

        # Y que la proyeccion **hace algo**: el mismo circuito y los mismos
        # frames, pero sin tocar el volante. Si las dos tiradas se vieran
        # igual, la carretera estaria pintada siempre en el mismo sitio y esta
        # prueba estaria comparando dos dibujos fijos.
        recto = [(IN_START, 0), (IN_START, 0), (0, 0)]
        recto += [(IN_ACTION, 0)] * 60
        recto += [(IN_ACTION | IN_JUMP, 0)]
        recto += [(IN_ACTION, 0)] * 300
        traza_recto, _ = self._trazas_de("carretera", recto, "recto")

        def firmas(traza):
            return [c.split()[COL_CARRETERA] for c in traza
                    if c.split()[5] == str(ESTADO_JUEGO)]

        con_volante, sin_volante = firmas(traza_c), firmas(traza_recto)
        self.assertNotIn("00000000", con_volante,
                         "hay frames sin carretera que dibujar")
        self.assertNotEqual(con_volante, sin_volante,
                            "la carretera se ve igual gires o no gires")
        # Y no es un frame suelto: son decenas. Se cuentan solo los frames en
        # los que las dos tiradas siguen jugando, porque a partir de donde una
        # se sale y la otra no, ni siquiera duran lo mismo.
        distintos = sum(1 for a, b in zip(con_volante, sin_volante) if a != b)
        self.assertGreater(distintos, 50,
                           "girar apenas cambia lo que se ve (%d frames de %d)"
                           % (distintos, min(len(con_volante),
                                             len(sin_volante))))

    def test_misma_traza_con_trafico_y_crono(self):
        """El circuito entero: coches que adelantar, controles de paso que
        regalan segundos y el reloj corriendo. El trafico se coloca solo en su
        carril mirando la cinta de la carretera, asi que en una curva las dos
        implementaciones tienen que ponerlo en el mismo pixel: si no, el
        jugador chocaria en una y pasaria de largo en la otra."""
        for semilla in (1, 7, 99):
            self._comparar("trafico", semilla)

    def test_el_control_de_paso_regala_tiempo(self):
        """Lo que hace que un juego de conducir sea un juego: el reloj baja
        solo y cruzar un control lo sube. Sin esto, el crono seria una cuenta
        atras y ya, y llegar no valdria para nada."""
        entradas = [(IN_START, 0), (IN_START, 0), (0, 0)]
        entradas += [(IN_ACTION, 0)] * 60
        entradas += [(IN_ACTION | IN_JUMP, 0)]
        entradas += [(IN_ACTION, 0)] * 500
        traza_c, traza_js = self._trazas_de("trafico", entradas, "control")
        self.assertEqual(traza_c, traza_js,
                         "el reloj no corre igual en el C y en el preview")
        crono = [int(c.split()[COL_CRONO]) for c in traza_c
                 if c.split()[5] == str(ESTADO_JUEGO)]
        self.assertTrue(crono, "no se llega a jugar")
        # el reloj baja solo, un frame por frame
        bajadas = sum(1 for i in range(1, len(crono)) if crono[i] < crono[i - 1])
        self.assertGreater(bajadas, 100, "el reloj no corre")
        # y en algun momento **sube**: eso es un control de paso
        subidas = [i for i in range(1, len(crono)) if crono[i] > crono[i - 1]]
        self.assertTrue(subidas, "cruzar un control no da tiempo")
        # y da lo que dice el game.yaml (15 segundos = 900 frames), ni mas ni
        # menos: uno menos porque el mismo frame que lo da tambien descuenta
        for i in subidas:
            self.assertEqual(crono[i] - crono[i - 1], 15 * 60 - 1,
                             "un control da %d frames y deberia dar 899"
                             % (crono[i] - crono[i - 1]))
        # y no lo da dos veces por cruzar una sola linea
        self.assertLessEqual(len(subidas), 2,
                             "los dos controles del circuito dan tiempo %d "
                             "veces" % len(subidas))

    def test_chocar_con_el_trafico_es_un_trompo(self):
        """Un coche de delante no quita vida: te hace dar vueltas, y eso cuesta
        tiempo, que es la unica moneda del genero. Aqui se va de frente a por
        uno -sin tocar el volante- y se mira que el trompo sale y que la vida
        se queda como estaba."""
        entradas = [(IN_START, 0), (IN_START, 0), (0, 0)]
        entradas += [(IN_ACTION, 0)] * 60
        entradas += [(IN_ACTION | IN_JUMP, 0)]
        entradas += [(IN_ACTION, 0)] * 400
        traza_c, traza_js = self._trazas_de("trafico", entradas, "choque")
        self.assertEqual(traza_c, traza_js,
                         "el choque no sale igual en el C y en el preview")
        columnas = [c.split() for c in traza_c]
        jugando = [c for c in columnas if c[5] == str(ESTADO_JUEGO)]
        trompos = [i for i in range(1, len(jugando))
                   if int(jugando[i][COL_TROMPO])
                   and not int(jugando[i - 1][COL_TROMPO])]
        self.assertTrue(trompos, "no se choca con ningun coche")
        # y la vida no se toca: chocar cuesta tiempo, no vidas
        for i in trompos:
            self.assertEqual(jugando[i][6], jugando[i - 1][6],
                             "chocar con el trafico ha quitado vida")

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
        self.assertTrue(all(len(c) >= COL_ABIERTOS + 1 for c in columnas),
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
