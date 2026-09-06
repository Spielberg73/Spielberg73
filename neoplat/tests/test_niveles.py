"""Los niveles de ejemplo tienen que poder terminarse.

Un bot juega cada nivel de principio a fin: de lado anda a la derecha y salta
cuando ve un obstaculo, y desde arriba busca el camino hasta la meta y sube
disparando. Si el bot no llega a la meta, el nivel pide precision imposible o
tiene una trampa injusta.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

import comun
from comun import KIT, cargar_demo

from ngplat.build import build_project
from ngplat.preview import build_data
from ngplat.project import load_project
from ngplat.scaffold import crear_proyecto

EJEMPLO = os.path.join(KIT, "examples", "bosque-magico")


def _datos(build, destino):
    datos = build_data(build)
    for hoja in datos["sheets"].values():
        hoja["url"] = ""
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(datos, fh)
    return destino


class TestNivelesJugables(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            self.skipTest("node no esta instalado")
        self.tmp = tempfile.mkdtemp(prefix="neoplat-niveles-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _jugar(self, proyecto):
        build = cargar_demo(proyecto)
        ruta = _datos(build, os.path.join(self.tmp, "datos.json"))
        resultado = subprocess.run(
            ["node", os.path.join(KIT, "tests", "nivel_jugable.js"), ruta],
            capture_output=True, text=True,
        )
        return resultado

    def test_ejemplo_del_kit(self):
        resultado = self._jugar(EJEMPLO)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el ejemplo:\n" + resultado.stdout)

    def test_proyecto_nuevo(self):
        destino = os.path.join(self.tmp, "juego")
        crear_proyecto(destino, "NUEVO", "TEST")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto recien creado:\n"
                         + resultado.stdout)

    def test_el_proyecto_de_castlevania_tambien_se_termina(self):
        """El genero de latigo cambia la fisica entera -sin correccion del
        salto, sin pisar enemigos y con escaleras- asi que su nivel de partida
        hay que comprobarlo aparte: el bot no sabe subir escaleras, y si el
        camino dependiera de una no habria forma de pasar."""
        destino = os.path.join(self.tmp, "castillo")
        crear_proyecto(destino, "CASTILLO", "TEST", genero="castlevania")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto de castlevania:\n"
                         + resultado.stdout)

    def test_el_proyecto_de_comando_tambien_se_termina(self):
        """El genero de comando se ve desde arriba y se juega subiendo, asi que
        el bot que anda hacia la derecha no vale: hay otro que busca el camino
        hasta la meta. Sus dos niveles tienen que poder terminarse."""
        destino = os.path.join(self.tmp, "comando")
        crear_proyecto(destino, "COMANDO", "TEST", genero="comando")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto de comando:\n"
                         + resultado.stdout)

    def test_el_proyecto_de_mazmorra_tambien_se_termina(self):
        """La mazmorra se ve desde arriba como el comando, pero se juega de
        otra manera: la vida se gasta sola, la meta pide una llave que esta al
        otro lado del laberinto y hay generadores sacando bichos. Sus dos
        laberintos tienen que poder terminarse."""
        destino = os.path.join(self.tmp, "mazmorra")
        crear_proyecto(destino, "MAZMORRA", "TEST", genero="mazmorra")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto de mazmorra:\n"
                         + resultado.stdout)

    def test_en_la_mazmorra_la_llave_va_antes_que_la_meta(self):
        """Y que llegue no es casualidad: la meta de los dos laberintos pide
        una llave que esta al otro lado del mapa. Si tapiamos el rincon de la
        llave -dejando la meta donde estaba- el bot tiene que decir que no
        llega **a la llave**. Si dijera que ha terminado, es que se iba
        derecho a la meta y la llave no pintaba nada."""
        destino = os.path.join(self.tmp, "mazmorra-sin-llave")
        crear_proyecto(destino, "SINLLAVE", "TEST", genero="mazmorra")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # el rincon de la llave del primer laberinto, tapiado por la derecha y
        # por abajo: la llave sigue en el mapa, pero no se puede ir a por ella
        pared = [("#..k...#.T.#...c...#", "#..k####.T.#...c...#"),
                 ("#......#...#.......#", "####...#...#.......#")]
        for antes, despues in pared:
            self.assertEqual(texto.count(antes), 1,
                             "el laberinto ya no tiene la fila " + antes)
            texto = texto.replace(antes, despues)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "el bot dice que abre una meta sin coger la llave")
        self.assertIn("la llave", resultado.stdout, resultado.stdout)

    def test_el_proyecto_de_tortas_tambien_se_termina(self):
        """El genero de tortas no se pasa andando: la camara no avanza mientras
        quede alguien vivo en pantalla, asi que el bot tiene que pelear. Sus
        dos calles tienen que poder limpiarse."""
        destino = os.path.join(self.tmp, "barrio")
        crear_proyecto(destino, "BARRIO", "TEST", genero="barrio")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto de tortas:\n"
                         + resultado.stdout)

    def test_en_las_tortas_hay_que_pelear_para_avanzar(self):
        """Y que lo que le hace terminar es pelear: al mismo juego sin ataque
        no le queda forma de limpiar la pantalla, asi que el bot se queda
        parado donde el primer grupo. Si tambien pasara, es que la camara no
        estaba cerrando el paso y la prueba de arriba no probaba nada."""
        destino = os.path.join(self.tmp, "barrio-sin-punos")
        crear_proyecto(destino, "SINPUNOS", "TEST", genero="barrio")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        marca = "  ataque:\n    tipo: golpe\n"
        self.assertIn(marca, texto, "el ataque del barrio ya no se escribe asi")
        # sin alcance el puno no llega a nadie: el resto se queda igual
        texto = texto.replace("    alcance: 14", "    alcance: 4", 1)
        # y los matones aguantan lo que sea
        texto = texto.replace("    vida: 3\n    dano: 1", "    vida: 99\n    dano: 1", 1)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "sin punos tambien se pasa la calle")
        # se queda a medias, se llame como se llame el fallo: o clavado donde
        # el primer grupo o muerto de tanto cobrar sin poder responder
        self.assertNotIn("ok   nivel", resultado.stdout, resultado.stdout)

    def test_el_proyecto_isometrico_tambien_se_termina(self):
        """El genero isometrico no se pasa andando: hay que cruzar seis
        habitaciones, subirse a los cubos para pasar por encima de lo que no se
        rodea y llevar el talisman hasta la puerta. Sus dos castillos tienen
        que poder terminarse."""
        destino = os.path.join(self.tmp, "filmation")
        crear_proyecto(destino, "CASTILLO", "TEST", genero="filmation")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto isometrico:\n"
                         + resultado.stdout)

    def test_en_la_isometrica_sin_talisman_no_se_abre_la_puerta(self):
        """Y que lo que le hace terminar el segundo castillo es el talisman: la
        salida esta detras de una puerta que lo pide, y el talisman esta tres
        habitaciones atras. Quitandolo del mapa -y dejando la puerta donde
        estaba- el bot no puede llegar. Si tambien pasara, es que el cerrojo no
        estaria frenando y la prueba de arriba no probaria nada."""
        destino = os.path.join(self.tmp, "filmation-sin-talisman")
        crear_proyecto(destino, "SINTALISMAN", "TEST", genero="filmation")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # el talisman del segundo castillo, quitado del mapa: la puerta sigue
        # ahi y el camino tambien, lo unico que falta es con que abrirla
        marca = "      #..o....#.......#..t....\n"
        self.assertIn(marca, texto, "el segundo castillo ya no pone el talisman ahi")
        texto = texto.replace(marca, "      #..o....#.......#.......\n", 1)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "sin talisman tambien se abre la puerta")
        self.assertIn("FALLO nivel 2", resultado.stdout, resultado.stdout)

    def test_las_paredes_del_castillo_no_cuestan_un_cubo(self):
        """Las dos paredes del fondo de una habitacion vienen dibujadas en el
        propio dibujo de `sala:`, asi que en el mapa son casillas que levantan
        48 y no traen cubo. No es un detalle de estilo: son quince casillas por
        habitacion, y quince cubos mas los de dentro no le caben a la Mega
        Drive en un frame -medido: el juego se iba a la mitad de velocidad-.
        Aqui se comprueba que siguen sin costar un cubo y que aun asi paran."""
        destino = os.path.join(self.tmp, "filmation-paredes")
        crear_proyecto(destino, "PAREDES", "TEST", genero="filmation")
        proyecto = load_project(os.path.join(destino, "game.yaml"))
        pared = proyecto.tiles["#"]
        self.assertEqual(pared.alto, 48, "la pared del fondo ya no levanta 48")
        self.assertEqual(pared.bloque, "",
                         "la pared del fondo se dibuja con el cubo '%s' y "
                         "deberia venir ya pintada en la sala" % pared.bloque)
        self.assertTrue(pared.pintado, "la pared no esta marcada como pintada")
        self.assertEqual(pared.kind, "solid", "la pared ya no frena")
        # y el muro de verdad, el que tapia el hueco que la sala deja en medio
        # de cada pared, sigue siendo un cubo
        self.assertEqual(proyecto.tiles["M"].bloque, "muro")
        # ninguna habitacion pasa de ocho cubos: es lo que la Mega Drive dibuja
        # en un frame sin perder el retrazo
        build = build_project(proyecto)
        con_cubo = set(i for i, t in enumerate(build.tiles) if t.bloque)
        for nivel in build.levels:
            for ry in range(nivel.cells_h // 8):
                for rx in range(nivel.cells_w // 8):
                    cuantos = 0
                    for cy in range(ry * 8, ry * 8 + 8):
                        for cx in range(rx * 8, rx * 8 + 8):
                            if nivel.cells[cy * nivel.cells_w + cx] in con_cubo:
                                cuantos += 1
                    # Doce es el presupuesto medido: en una Mega Drive cada
                    # cubo cuesta unas 8 de las 262 lineas que dura un frame y
                    # el resto del juego se lleva 127, asi que a partir de
                    # quince se pierde el retrazo. Doce deja margen.
                    self.assertLessEqual(
                        cuantos, 12,
                        "la sala %d,%d de '%s' trae %d cubos"
                        % (rx, ry, nivel.name, cuantos))

    def test_el_proyecto_de_aventura_tambien_se_termina(self):
        """El genero de aventura no se pasa andando: cada pantalla acaba en un
        cerrojo y lo que lo abre esta en la anterior. Sus dos niveles tienen
        que poder resolverse."""
        destino = os.path.join(self.tmp, "aventura")
        crear_proyecto(destino, "AVENTURA", "TEST", genero="aventura")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto de aventura:\n"
                         + resultado.stdout)

    def test_en_la_aventura_sin_los_objetos_no_se_pasa(self):
        """Y que lo que le hace terminar son los objetos: al mismo juego sin la
        llave, el cubo y el pico del primer nivel no le queda forma de abrir
        nada, asi que el bot se queda plantado delante de la primera puerta. Si
        tambien pasara, es que los cerrojos no frenaban y la prueba de arriba no
        probaba nada."""
        destino = os.path.join(self.tmp, "aventura-sin-nada")
        crear_proyecto(destino, "SINNADA", "TEST", genero="aventura")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # se quitan del mapa los tres objetos del primer nivel -la llave, el
        # cubo y el pico-; el mapa, las puertas y el camino se quedan igual
        antes = ("      ..P......k................D....c...a...o......F...x..."
                 "^..m........W...o.tttttttt")
        self.assertEqual(texto.count(antes), 1,
                         "el primer nivel ya no tiene la fila de los objetos")
        despues = antes.replace("k", ".", 1).replace("c", ".", 1).replace("x", ".", 1)
        texto = texto.replace(antes, despues)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "sin los objetos tambien se pasan las puertas")
        self.assertNotIn("ok   nivel 1", resultado.stdout, resultado.stdout)

    def test_el_proyecto_de_kungfu_tambien_se_termina(self):
        """El genero de kung-fu no se pasa andando hacia la derecha: la puerta
        pide todos los faroles y los faroles estan arriba, en las vigas y al
        final de las lianas. Sus dos niveles tienen que poder terminarse."""
        destino = os.path.join(self.tmp, "kungfu")
        crear_proyecto(destino, "TEMPLO", "TEST", genero="kungfu")
        resultado = self._jugar(destino)
        self.assertEqual(resultado.returncode, 0,
                         "el bot no puede terminar el proyecto de kung-fu:\n"
                         + resultado.stdout)

    def test_en_el_kungfu_sin_la_liana_no_se_llega_al_farol(self):
        """Y que lo que le hace llegar arriba es la liana. Quitandola de la
        segunda pantalla del primer nivel -y dejando la viga, el farol y todo
        lo demas donde estaba- el farol de esa sala se queda sin camino y la
        puerta ya no se abre. Si tambien pasara, es que el bot llegaba por otro
        lado y la prueba de arriba no probaba que las lianas sirvan."""
        destino = os.path.join(self.tmp, "kungfu-sin-liana")
        crear_proyecto(destino, "SINLIANA", "TEST", genero="kungfu")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            lineas = fh.read().split("\n")
        # el mapa del primer nivel son las 14 filas de 80 que siguen a su
        # 'mapa: |'; la liana de la segunda pantalla va por la columna 30
        primero = next(i for i, l in enumerate(lineas) if l.strip() == "mapa: |")
        quitadas = 0
        for i in range(primero + 1, primero + 15):
            fila = lineas[i]
            sangria = len(fila) - len(fila.lstrip())
            self.assertEqual(len(fila) - sangria, 80, "la fila %d no mide 80" % i)
            col = sangria + 30
            if fila[col] == "|":
                lineas[i] = fila[:col] + "." + fila[col + 1:]
                quitadas += 1
        self.assertEqual(quitadas, 8,
                         "la liana de la segunda pantalla ya no esta ahi")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lineas))
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "sin la liana tambien se llega al farol de arriba")
        self.assertNotIn("ok   nivel 1", resultado.stdout, resultado.stdout)

    def _mazmorra_con(self, nombre, parches):
        """Un proyecto de mazmorra con el game.yaml retocado."""
        destino = os.path.join(self.tmp, nombre)
        crear_proyecto(destino, nombre.upper(), "TEST", genero="mazmorra")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        for antes, despues in parches:
            self.assertIn(antes, texto, "el andamiaje ya no escribe " + antes)
            texto = texto.replace(antes, despues)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        return destino

    def test_en_la_mazmorra_se_come_para_llegar(self):
        """Con la vida corta no se llega andando: hay que parar a comer. El bot
        va a por la comida cuando le queda poca, asi que termina los dos
        laberintos con 60 puntos de vida y 6 frames por punto -que dan para 360
        frames y el recorrido pasa de 450-."""
        corta = [("  vida: 200", "  vida: 60"), ("  desgaste: 12", "  desgaste: 6")]
        resultado = self._jugar(self._mazmorra_con("hambre", corta))
        self.assertEqual(resultado.returncode, 0,
                         "el bot no come: no llega con la vida corta:\n"
                         + resultado.stdout)

    def test_y_sin_comida_no_llega(self):
        """El control de la de arriba: la misma vida corta pero cambiando la
        comida del mapa por tesoros, que no alimentan. Si tambien pasara, es
        que la vida daba de sobra y la prueba anterior no probaba nada."""
        sin = [("  vida: 200", "  vida: 60"), ("  desgaste: 12", "  desgaste: 6"),
               ("  c: comida", "  c: tesoro")]
        resultado = self._jugar(self._mazmorra_con("sin-comida", sin))
        self.assertNotEqual(resultado.returncode, 0,
                            "sin comida tambien llega: la vida daba de sobra")
        self.assertIn("muere", resultado.stdout, resultado.stdout)

    def test_avisa_cuando_el_camino_de_arriba_esta_cortado(self):
        """Y lo contrario: si un nivel cenital se queda sin paso, el bot tiene
        que decir que no hay camino, no soltar un 'no llega a tiempo' que no
        explica nada. Aqui cerramos una fila entera con sacos terreros."""
        destino = os.path.join(self.tmp, "comando-cortado")
        crear_proyecto(destino, "CORTADO", "TEST", genero="comando")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        fila = "AA.,,,,,g,,,,,,,.AAA"
        assert fila in texto, "el nivel de comando ya no tiene esa fila"
        texto = texto.replace(fila, "#" * len(fila), 1)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "el bot dice que sube por un nivel tapiado")
        self.assertIn("no hay camino", resultado.stdout, resultado.stdout)

    def test_avisa_cuando_la_llave_no_esta_en_el_camino(self):
        """El bot solo anda hacia la derecha. Si la llave que abre la meta esta
        donde el no llega, tiene que decirlo con esas palabras y no soltar un
        'se queda atascado' que no explica nada."""
        destino = os.path.join(self.tmp, "llave-lejos")
        crear_proyecto(destino, "LLAVE", "TEST")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # la llave del andamiaje esta en el camino: se sube a la plataforma
        # mas alta, donde el bot no llega
        assert "^...k" in texto, "el andamiaje ya no pone la llave asi"
        texto = texto.replace("^...k", "^....", 1)
        texto = texto.replace("      ..............................ccc",
                              "      ..............................ckc", 1)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(texto)
        resultado = self._jugar(destino)
        self.assertNotEqual(resultado.returncode, 0,
                            "el bot dice que llega a una meta cerrada")
        self.assertIn("le faltan llaves", resultado.stdout, resultado.stdout)

    def test_avisa_de_enemigos_sin_suelo(self):
        destino = os.path.join(self.tmp, "flotante")
        crear_proyecto(destino, "FLOTANTE", "TEST")
        ruta = os.path.join(destino, "game.yaml")
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        # colocamos una seta en el aire, en una fila vacia del primer nivel
        lineas = texto.split("\n")
        for i, linea in enumerate(lineas):
            if linea.strip() == "." * 48:
                lineas[i] = linea[:12] + "s" + linea[13:]
                break
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lineas))
        proyecto = load_project(ruta)
        self.assertTrue(any("no tiene suelo debajo" in aviso for aviso in proyecto.warnings),
                        proyecto.warnings)


if __name__ == "__main__":
    unittest.main()
