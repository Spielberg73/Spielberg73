"""El tracker: que la rejilla no cambie la cancion.

Un tracker es una **vista** sobre las dos lineas de notas que ya tiene el
game.yaml. Y eso da una cosa que probar que vale mas que cualquier captura de
pantalla: **lo que entra tiene que salir**. Si abrir una cancion en la rejilla
y guardarla sin tocar nada mueve una sola nota, el tracker no es una vista: es
una trituradora.

Asi que casi todo lo de aqui es la misma pregunta hecha de cinco maneras:

  1. abrir y guardar sin tocar nada deja el texto **byte a byte** igual;
  2. tocar una pista no toca la otra;
  3. la rejilla reescrita suena **exactamente igual** -los mismos pasos del
     chip, comparados con sonido.py, que es quien manda-;
  4. una nota larga a caballo entre dos compases sigue siendo una nota larga
     y no dos notas repetidas;
  5. y las notas que el tracker acepta son las mismas que acepta sonido.py,
     ni una mas: una rejilla que te deja escribir algo que luego no compila es
     una trampa.

Todo contra el JavaScript de verdad, con node, que es lo que corre en el
editor. Sin node no se prueban: se saltan y se dice.
"""

import json
import os
import random
import shutil
import subprocess
import unittest

from comun import KIT, json_de

import sys
sys.path.insert(0, os.path.join(KIT, "tools"))

from ngplat import sonido as sonido_mod          # noqa: E402
from ngplat.errors import ProjectError           # noqa: E402

TRACKER = os.path.join(KIT, "preview", "np_tracker.js")

# Las canciones de los ejemplos del kit, que son las que tiene delante
# cualquiera que abra el editor.
CANCIONES = [
    ["do4 mi4 sol4 mi4 | fa4 la4 do5 la4 | sol4 si4 re5 si4 | do5 - sol4 -",
     "do3 -  do3 -     | fa3 -  fa3 -    | sol3 - sol3 -     | do3 - -    -"],
    ["la3 do4 mi4 do4 | sol3 si3 re4 si3 | fa3 la3 do4 la3 | mi3 - - -",
     "la2 -   mi3 -   | sol2 -   re3 -   | fa2 -   do3 -   | mi2 - - -"],
    # una sola pista, sin barras y con notas largas
    ["do4:4 mi4:2 sol4 la4 si4:3"],
    # dos pistas que miden distinto: la corta no se puede rellenar
    ["do4 re4 mi4 fa4 sol4 la4 si4 do5", "do3:4 sol3:4"],
    # notas en ingles y con alteraciones, que tambien son notas
    ["c4 d#4 gb4 a4 | b4 c5 d5 e5"],
]


def _node(guion: str, entrada) -> object:
    """Ejecuta un trozo de JavaScript con el tracker cargado."""
    completo = ("var T = require(%s);\n"
                "var dato = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
                % json.dumps(TRACKER)) + guion
    hecho = subprocess.run(["node", "-e", completo], input=json.dumps(entrada),
                           capture_output=True, text=True)
    if hecho.returncode != 0:
        raise AssertionError("node ha fallado:\n%s" % hecho.stderr)
    return json.loads(hecho.stdout)


def _pasos(texto: str):
    """Como suena una linea de notas, segun quien manda: sonido.py."""
    return [(round(p.frecuencia, 2), p.duracion)
            for p in sonido_mod.parsear_notas(texto, 8, 15, "prueba")]


class TrackerConNode(unittest.TestCase):
    """Base: sin node no hay nada que probar aqui."""

    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("node no esta instalado")


class TestLoQueEntraSale(TrackerConNode):

    def test_abrir_y_guardar_sin_tocar_nada_no_cambia_una_coma(self):
        """La primera regla, y la que mas se agradece: el tracker no te
        reescribe el game.yaml por haberlo mirado."""
        salio = _node(
            "console.log(JSON.stringify(dato.map(function (pistas) {\n"
            "  return T.aPistas(T.aRejilla({pistas: pistas}));\n"
            "})));\n", CANCIONES)
        self.assertEqual(CANCIONES, salio)

    def test_tocar_una_pista_no_toca_la_otra(self):
        """Cambiar la melodia no puede reformatear el acompanamiento: lo que
        sale en el diff tiene que ser lo que has hecho, y nada mas."""
        salio = _node(
            "var r = T.aRejilla({pistas: dato});\n"
            "T.ponerNota(r, 0, 2, 'la#5');\n"
            "console.log(JSON.stringify(T.aPistas(r)));\n", CANCIONES[0])
        self.assertNotEqual(CANCIONES[0][0], salio[0])
        self.assertEqual(CANCIONES[0][1], salio[1])

    def test_la_rejilla_reescrita_suena_exactamente_igual(self):
        """La prueba que de verdad importa.

        Se fuerza a reescribir cada pista -como si se hubiera tocado- y se
        compara **lo que suena**, paso a paso, contra sonido.py. El texto puede
        salir con otros espacios o con los largos escritos de otra forma; los
        hercios y las duraciones, no.
        """
        salio = _node(
            "console.log(JSON.stringify(dato.map(function (pistas) {\n"
            "  var r = T.aRejilla({pistas: pistas});\n"
            "  r.pistas.forEach(function (p) { p.tocada = true; });\n"
            "  return T.aPistas(r);\n"
            "})));\n", CANCIONES)
        for antes, despues in zip(CANCIONES, salio):
            for original, reescrita in zip(antes, despues):
                with self.subTest(pista=original):
                    self.assertEqual(_pasos(original), _pasos(reescrita))

    def test_la_rejilla_aguanta_cualquier_cancion(self):
        """Lo mismo pero con mil canciones al azar, que es donde salen los
        casos que a uno no se le ocurren: notas largas pegadas, silencios al
        final, compases a medias."""
        al_azar = random.Random(1960)
        notas = ["do4", "re4", "mi4", "fa#4", "sol4", "la3", "si5", "c3", "eb5"]
        canciones = []
        for _ in range(120):
            pistas = []
            for _ in range(al_azar.randint(1, 2)):
                trozos = []
                for paso in range(al_azar.randint(1, 24)):
                    if paso and al_azar.random() < 0.2:
                        trozos.append("|")
                    tirada = al_azar.random()
                    if tirada < 0.25:
                        trozos.append("-")
                    elif tirada < 0.45:
                        trozos.append("%s:%d" % (al_azar.choice(notas),
                                                 al_azar.randint(2, 4)))
                    else:
                        trozos.append(al_azar.choice(notas))
                pistas.append(" ".join(trozos))
            canciones.append(pistas)

        salio = _node(
            "console.log(JSON.stringify(dato.map(function (pistas) {\n"
            "  var r = T.aRejilla({pistas: pistas});\n"
            "  r.pistas.forEach(function (p) { p.tocada = true; });\n"
            "  return T.aPistas(r);\n"
            "})));\n", canciones)
        for antes, despues in zip(canciones, salio):
            for original, reescrita in zip(antes, despues):
                with self.subTest(pista=original):
                    self.assertEqual(_pasos(original), _pasos(reescrita))

    def test_la_ida_y_vuelta_de_la_rejilla_es_la_misma_rejilla(self):
        """Y las celdas tambien: leer el texto que uno mismo ha escrito tiene
        que dar la rejilla de la que salio, o editar dos veces seguidas
        acabaria en otro sitio."""
        salio = _node(
            "console.log(JSON.stringify(dato.map(function (pistas) {\n"
            "  var r = T.aRejilla({pistas: pistas});\n"
            "  r.pistas.forEach(function (p) { p.tocada = true; });\n"
            "  var texto = T.aPistas(r);\n"
            "  var otra = T.aRejilla({pistas: texto});\n"
            "  return [r.pistas.map(function (p) { return p.celdas; }),\n"
            "          otra.pistas.map(function (p) { return p.celdas; })];\n"
            "})));\n", CANCIONES)
        for antes, despues in salio:
            self.assertEqual(antes, despues)


class TestLasNotasLargas(TrackerConNode):
    """`do4:3` son tres filas en la rejilla, y tienen que volver a ser `:3`."""

    def test_una_nota_de_tres_pasos_ocupa_tres_filas(self):
        salio = _node(
            "var r = T.aRejilla({pistas: ['do4:3 mi4']});\n"
            "console.log(JSON.stringify(r.pistas[0].celdas.map(function (c) {\n"
            "  return c.tipo;\n"
            "})));\n", None)
        self.assertEqual(["nota", "sigue", "sigue", "nota"], salio)

    def test_una_nota_larga_a_caballo_de_un_compas_sigue_siendo_una(self):
        """El fallo que tenia esto al escribirlo: la barra cortaba la nota y lo
        que salia eran dos notas repetidas. Una barra es una raya para leer, no
        un silencio."""
        salio = _node(
            "var r = T.aRejilla({pistas: ['do4 mi4 sol4 la4 | si4 do5 re5 mi5']});\n"
            "T.ponerNota(r, 0, 3, 'la4');\n"
            "for (var f = 4; f < 8; f++) T.ponerSigue(r, 0, f);\n"
            "console.log(JSON.stringify(T.aPistas(r)[0]));\n", None)
        self.assertIn("la4:5", salio)
        # y suena como una nota de cinco pasos, no como cinco notas
        pasos = _pasos(salio)
        self.assertEqual(4, len(pasos))
        self.assertEqual(8 * 5, pasos[-1][1])

    def test_un_sigue_suelto_es_un_silencio(self):
        """Borrar una nota y dejarse sus colas no puede dar un `:2` sin nota
        delante, que no compila en ninguna parte."""
        salio = _node(
            "var r = T.aRejilla({pistas: ['do4:3 mi4']});\n"
            "T.ponerSilencio(r, 0, 0);\n"
            "console.log(JSON.stringify(T.aPistas(r)[0]));\n", None)
        self.assertEqual(["-", "-", "-", "mi4"], salio.split())


class TestLasPistasDeDistintoLargo(TrackerConNode):
    """Rellenar la pista corta con silencios cambiaria la cancion."""

    def test_la_pista_corta_no_se_alarga_sola(self):
        salio = _node(
            "var r = T.aRejilla({pistas: dato});\n"
            "r.pistas.forEach(function (p) { p.tocada = true; });\n"
            "console.log(JSON.stringify([r.filas, r.pistas.map(function (p) {\n"
            "  return p.largo;\n"
            "}), T.aPistas(r)]));\n", ["do4 re4 mi4 fa4 sol4 la4 si4 do5", "do3:4"])
        filas, largos, textos = salio
        self.assertEqual(8, filas)
        self.assertEqual([8, 4], largos)
        self.assertEqual("do3:4", textos[1].strip())

    def test_escribir_mas_abajo_alarga_solo_esa_pista(self):
        """Pinchar en la fila 10 de la pista corta la alarga con silencios,
        que es lo que uno espera al pinchar ahi; la otra se queda como esta."""
        salio = _node(
            "var r = T.aRejilla({pistas: dato});\n"
            "T.ponerNota(r, 1, 9, 'sol2');\n"
            "console.log(JSON.stringify([r.pistas.map(function (p) {\n"
            "  return p.largo;\n"
            "}), T.aPistas(r)]));\n", ["do4 re4 mi4 fa4", "do3 sol3"])
        largos, textos = salio
        self.assertEqual([4, 10], largos)
        self.assertEqual("do4 re4 mi4 fa4", textos[0])
        self.assertEqual(10, len(textos[1].replace("|", " ").split()))


class TestLoQueSePuedeEscribir(TrackerConNode):

    def test_acepta_exactamente_lo_que_acepta_sonido_py(self):
        """La rejilla y el compilador tienen que estar de acuerdo. Si aqui se
        puede escribir algo que luego no compila, el editor te deja guardar un
        juego que no se construye, y eso se descubre media hora despues."""
        candidatos = ["do4", "DO4", "sol#3", "lab5", "c0", "b9", "mi", "re-1",
                      "do10", "xx4", "do#", "sol##4", "", "4", "do4b", "fa#"]
        salio = _node(
            "console.log(JSON.stringify(dato.map(T.valeComoNota)));\n",
            candidatos)
        for texto, vale in zip(candidatos, salio):
            with self.subTest(nota=texto):
                try:
                    sonido_mod.parsear_notas(texto, 8, 15, "prueba")
                    compila = True
                except ProjectError:
                    compila = False
                self.assertEqual(compila, vale,
                                 "'%s': el tracker dice %s y sonido.py %s"
                                 % (texto, vale, compila))

    def test_el_teclado_escribe_las_doce_notas(self):
        """Dos filas de teclas, dos octavas, como en cualquier tracker."""
        salio = _node(
            "var fuera = {};\n"
            "Object.keys(T.TECLAS).forEach(function (k) {\n"
            "  fuera[k] = T.nombreDeNota(T.TECLAS[k], 4);\n"
            "});\n"
            "console.log(JSON.stringify(fuera));\n", None)
        self.assertEqual("do4", salio["z"])
        self.assertEqual("do#4", salio["s"])
        self.assertEqual("si4", salio["m"])
        self.assertEqual("do5", salio["q"])       # la fila de arriba, una octava mas
        self.assertEqual("si5", salio["u"])
        self.assertEqual(24, len(salio))
        for nota in salio.values():
            self.assertTrue(sonido_mod.parsear_notas(nota, 8, 15, "t"))


class TestTransportar(TrackerConNode):
    """Subir o bajar de tono lo que hay escrito, que a mano es un suplicio."""

    def test_subir_una_octava_son_doce_semitonos(self):
        salio = _node(
            "var r = T.aRejilla({pistas: ['do4 mi4 sol4']});\n"
            "T.transportar(r, 0, 0, 2, 12);\n"
            "console.log(JSON.stringify(T.aPistas(r)[0].split(/\\s+/)));\n", None)
        self.assertEqual(["do5", "mi5", "sol5"], salio)

    def test_no_se_sale_de_las_octavas_que_existen(self):
        """Bajar nueve octavas no puede dejar escrito 'do-5', que no compila."""
        salio = _node(
            "var r = T.aRejilla({pistas: ['do4 mi4']});\n"
            "T.transportar(r, 0, 0, 1, -72);\n"
            "console.log(JSON.stringify(T.aPistas(r)[0].split(/\\s+/)));\n", None)
        self.assertEqual(["do4", "mi4"], salio)

    def test_lo_que_no_cabe_en_el_chip_se_queda_donde_esta(self):
        """Bajar cuatro octavas deja notas de 16 Hz: se entienden, pero no las
        toca ninguna de las ocho maquinas. Mejor que esa nota no se mueva que
        dejar la cancion sin poder construir."""
        salio = _node(
            "var r = T.aRejilla({pistas: ['do4 mi4']});\n"
            "T.transportar(r, 0, 0, 1, -48);\n"
            "console.log(JSON.stringify(T.aPistas(r)[0].split(/\\s+/)));\n", None)
        self.assertEqual(["do4", "mi4"], salio)
        # pero tres octavas si entran, que son 32 Hz
        baja = _node(
            "var r = T.aRejilla({pistas: ['do4 mi4']});\n"
            "T.transportar(r, 0, 0, 1, -36);\n"
            "console.log(JSON.stringify(T.aPistas(r)[0].split(/\\s+/)));\n", None)
        self.assertEqual(["do1", "mi1"], baja)
        for nota in baja:
            self.assertTrue(sonido_mod.parsear_notas(nota, 8, 15, "t"))

    def test_los_silencios_se_quedan_quietos(self):
        salio = _node(
            "var r = T.aRejilla({pistas: ['do4 - mi4']});\n"
            "T.transportar(r, 0, 0, 2, 2);\n"
            "console.log(JSON.stringify(T.aPistas(r)[0].split(/\\s+/)));\n", None)
        self.assertEqual(["re4", "-", "fa#4"], salio)


GUION_NAVEGADOR = r"""
const { chromium } = require('playwright');
const ruta = process.argv[2];
(async () => {
  const navegador = await chromium.launch({ args: ['--no-sandbox'] });
  const pagina = await navegador.newPage();
  const fallos = [];
  pagina.on('pageerror', e => fallos.push('pageerror: ' + e.message));
  pagina.on('console', m => { if (m.type() === 'error') fallos.push('console: ' + m.text()); });
  await pagina.goto('file://' + ruta);
  await pagina.waitForTimeout(600);
  await pagina.click('#modo');
  await pagina.click('#pestanas button[data-panel="tracker"]');
  await pagina.waitForTimeout(200);

  const salida = {};
  salida.filas = await pagina.locator('#tr-rejilla tbody tr').count();
  salida.columnas = await pagina.locator('#tr-rejilla tbody tr').first()
                                .locator('td').count();
  await pagina.click('#pestanas button[data-panel="yaml"]');
  salida.yamlAntes = await pagina.locator('#ed-texto').inputValue();
  await pagina.click('#pestanas button[data-panel="tracker"]');
  await pagina.waitForTimeout(150);

  /* la tecla 'n' es el la de la octava que marque el editor */
  await pagina.click('#tr-rejilla td[data-pista="0"][data-fila="2"]');
  await pagina.keyboard.press('n');
  await pagina.waitForTimeout(150);
  salida.celda = await pagina.locator('#tr-rejilla td[data-pista="0"][data-fila="2"]')
                             .textContent();
  salida.cursor = await pagina.locator('#tr-rejilla td.cursor')
                              .getAttribute('data-fila');
  await pagina.keyboard.press('-');
  await pagina.waitForTimeout(100);
  salida.silencio = await pagina.locator('#tr-rejilla td[data-pista="0"][data-fila="3"]')
                                .textContent();
  await pagina.click('#pestanas button[data-panel="yaml"]');
  await pagina.waitForTimeout(150);
  salida.yamlDespues = await pagina.locator('#ed-texto').inputValue();

  /* y que suene: la fila verde tiene que ir bajando sola */
  await pagina.click('#pestanas button[data-panel="tracker"]');
  await pagina.click('#tr-tocar');
  await pagina.waitForTimeout(600);
  salida.sonandoA = await pagina.locator('#tr-rejilla tr.sonando td.numero')
                                .textContent().catch(() => null);
  await pagina.waitForTimeout(900);
  salida.sonandoB = await pagina.locator('#tr-rejilla tr.sonando td.numero')
                                .textContent().catch(() => null);
  await pagina.click('#tr-parar');
  await pagina.waitForTimeout(150);
  salida.verdesTrasParar = await pagina.locator('#tr-rejilla tr.sonando').count();
  /* tocar desde la fila donde estes, que es como se compone */
  await pagina.click('#tr-rejilla td[data-pista="0"][data-fila="8"]');
  await pagina.click('#tr-aqui');
  await pagina.waitForTimeout(250);
  salida.desdeAqui = await pagina.locator('#tr-rejilla tr.sonando td.numero')
                                 .textContent().catch(() => null);
  await pagina.click('#tr-parar');

  /* los nombres de las canciones, que salian en blanco */
  salida.canciones = await pagina.locator('#tr-cancion option')
                                 .allTextContents();

  /* y una cancion nueva, escrita desde cero */
  pagina.on('dialog', async d => { await d.accept('batalla'); });
  await pagina.click('#tr-nueva');
  await pagina.waitForTimeout(400);
  salida.trasCrear = await pagina.locator('#tr-cancion option').allTextContents();
  salida.elegida = await pagina.locator('#tr-cancion').inputValue();
  await pagina.click('#tr-rejilla td[data-pista="0"][data-fila="0"]');
  for (const k of ['z', 'x', 'c', 'v']) await pagina.keyboard.press(k);
  await pagina.waitForTimeout(200);
  await pagina.click('#pestanas button[data-panel="yaml"]');
  await pagina.waitForTimeout(250);
  salida.yamlConCancion = await pagina.locator('#ed-texto').inputValue();
  /* crear una con el mismo nombre no puede colar: en el yaml seria un bloque
     repitiendo la clave y el segundo pisaria al primero */
  await pagina.click('#pestanas button[data-panel="tracker"]');
  await pagina.click('#tr-nueva');
  await pagina.waitForTimeout(300);
  salida.trasRepetir = await pagina.locator('#tr-cancion option').allTextContents();
  salida.avisoRepetir = await pagina.locator('#tr-aviso').textContent();
  salida.fallos = fallos;
  console.log(JSON.stringify(salida));
  await navegador.close();
})().catch(e => { console.error(e.message); process.exit(3); });
"""


class TestLaRejillaEnUnNavegadorDeVerdad(unittest.TestCase):
    """La otra mitad: que la pantalla haga lo que dice el parser.

    Las pruebas de arriba son de las cuentas, y las cuentas pueden estar
    perfectas con la rejilla sin pintar o con el teclado muerto. Asi que esta
    abre el preview **en un Chromium de verdad**, se va al editor, pincha una
    celda, escribe una nota con el teclado y exige que la nota aparezca en el
    game.yaml. Y que no haya saltado ni un error de JavaScript por el camino,
    que en una pagina se tragan solos.
    """

    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("node no esta instalado")
        hay = subprocess.run(["node", "-e", "require('playwright')"],
                             capture_output=True, text=True)
        if hay.returncode != 0:
            raise unittest.SkipTest("playwright no esta instalado")

    _visto = None

    def _abrir(self):
        """Abre el preview una sola vez: arrancar Chromium cuesta segundos."""
        if TestLaRejillaEnUnNavegadorDeVerdad._visto is not None:
            return TestLaRejillaEnUnNavegadorDeVerdad._visto
        import tempfile
        from ngplat.build import build_project
        from ngplat.preview import write_preview
        from ngplat.project import load_project

        tmp = tempfile.mkdtemp(prefix="neoplat-tracker-")
        self.addCleanup(shutil.rmtree, tmp, True)
        proyecto = os.path.join(KIT, "examples", "bosque-magico")
        destino = os.path.join(tmp, "preview.html")
        write_preview(build_project(load_project(proyecto)), destino)

        guion = os.path.join(tmp, "navegador.js")
        with open(guion, "w", encoding="utf-8") as fh:
            fh.write(GUION_NAVEGADOR)
        hecho = subprocess.run(["node", guion, destino],
                               capture_output=True, text=True, timeout=180)
        if hecho.returncode == 3:
            self.skipTest("no se ha podido abrir el navegador: %s" % hecho.stderr)
        self.assertEqual(0, hecho.returncode, hecho.stderr)
        salida = json_de(hecho.stdout)
        TestLaRejillaEnUnNavegadorDeVerdad._visto = salida
        return salida

    def test_se_escribe_una_nota_y_llega_al_game_yaml(self):
        salida = self._abrir()
        self.assertEqual([], salida["fallos"], "la pagina ha dado errores")
        # la rejilla se pinta: 16 pasos y tres columnas (numero + dos pistas)
        self.assertEqual(16, salida["filas"])
        self.assertEqual(3, salida["columnas"])
        # la tecla escribe la nota y el cursor baja, como en cualquier tracker
        self.assertEqual("la4", salida["celda"])
        self.assertEqual("3", salida["cursor"])
        self.assertEqual("-", salida["silencio"])
        # y lo escrito esta en el game.yaml, que es lo unico que se reparte
        self.assertNotEqual(salida["yamlAntes"], salida["yamlDespues"])
        # la linea de la melodia es la que lleva compases: los efectos de
        # sonido tambien son notas, y uno de ellos es "sol4 mi4 do4 sol3"
        melodia = [l for l in salida["yamlDespues"].splitlines()
                   if "|" in l and "do4" in l]
        self.assertTrue(melodia, "no encuentro la melodia en el yaml")
        self.assertIn("la4", melodia[0])
        # la otra pista, intacta: solo se reescribe lo que se toca
        self.assertIn("do3 -  do3 -", salida["yamlDespues"])

    def test_suena_y_la_fila_verde_va_bajando(self):
        """Un tracker en el que no se ve por donde va la cancion es una tabla."""
        salida = self._abrir()
        self.assertEqual([], salida["fallos"])
        self.assertIsNotNone(salida["sonandoA"], "no se ha puesto a sonar")
        self.assertNotEqual(salida["sonandoA"], salida["sonandoB"],
                            "la fila verde no se mueve")
        self.assertEqual(0, salida["verdesTrasParar"],
                         "al parar se queda una fila verde colgada")
        # tocar desde la fila 8 empieza por la 8, no por el principio
        self.assertIn(salida["desdeAqui"], ("008", "009", "010"))

    def test_se_crea_una_cancion_y_llega_al_game_yaml(self):
        """Lo que le faltaba al tracker: empezar una cancion de cero.

        Y lo que importa no es que salga en la lista, es que **se escriba en
        el game.yaml**: una cancion que solo existe en la pantalla se pierde
        al cerrar.
        """
        salida = self._abrir()
        self.assertEqual([], salida["fallos"])
        self.assertEqual(["bosque", "cueva", "batalla"], salida["trasCrear"])
        self.assertEqual("2", salida["elegida"],
                         "la nueva tendria que quedarse elegida")
        yaml = salida["yamlConCancion"]
        self.assertIn("batalla:", yaml)
        # con las cuatro notas que se han escrito, y en su bloque
        trozo = yaml[yaml.index("batalla:"):]
        self.assertIn("do4", trozo)
        self.assertIn("fa4", trozo)
        self.assertIn("pistas:", trozo)

    def test_dos_canciones_no_pueden_llamarse_igual(self):
        """En el yaml el nombre es la clave del bloque: dos iguales serian
        una, y la segunda se comeria a la primera al guardar."""
        salida = self._abrir()
        self.assertEqual(["bosque", "cueva", "batalla"], salida["trasRepetir"])
        self.assertIn("cogido", salida["avisoRepetir"])

    def test_las_canciones_tienen_nombre(self):
        """Salian en blanco: los nombres estan en lo ya compilado, no en el
        modelo, que son las notas tal cual se escribieron."""
        self.assertEqual(["bosque", "cueva"], self._abrir()["canciones"])


if __name__ == "__main__":
    unittest.main()
