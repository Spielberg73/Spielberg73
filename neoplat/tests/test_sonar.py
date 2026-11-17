"""`ngplat sonar`: la musica a un WAV que se pueda oir fuera del navegador.

Lo que se comprueba aqui no es que suene bien -eso no lo dice una prueba- sino
que **suene lo que pone**: que la cancion dure lo que suman sus pasos, que un
silencio salga en silencio y que una nota salga con su frecuencia. Lo ultimo se
mide contando por donde cruza el cero la onda, que a estas alturas es la manera
mas simple de preguntarle a un sonido a que nota corresponde.
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

from comun import KIT

sys.path.insert(0, os.path.join(KIT, "tools"))

from ngplat import sonar                              # noqa: E402
from ngplat.errors import ProjectError                # noqa: E402
from ngplat.project import load_project               # noqa: E402

EJEMPLO = os.path.join(KIT, "examples", "cielo-rojo")


def cancion(nombre, pistas, velocidad=8, timbres=None, volumen=15):
    """Una cancion montada a mano, sin pasar por un game.yaml.

    Para las pruebas que miden **una** cosa -una nota, un silencio- y no
    quieren arrastrar un proyecto entero detras.
    """
    from ngplat.sonido import Musica, parsear_notas

    return Musica(
        nombre=nombre, velocidad=velocidad,
        pistas=[parsear_notas(p, velocidad, volumen, nombre) for p in pistas],
        bucle=True, timbres=list(timbres or ["cuadrada"]), fuente={})


def _muestras(ruta):
    """Las muestras del WAV, con signo, sea de 8 o de 16 bits.

    De 8 el formato las guarda **sin signo** (0 a 255, con el silencio en 128)
    y de 16 **con signo**. Leer unas como las otras no da un error: da medidas
    sin sentido, que es peor.
    """
    with wave.open(ruta) as fh:
        datos = fh.readframes(fh.getnframes())
        ancho, ritmo = fh.getsampwidth(), fh.getframerate()
    if ancho == 1:
        return [b - 128 for b in datos], ritmo
    return list(struct.unpack("<%dh" % (len(datos) // 2), datos)), ritmo


def _hercios(valores, ritmo, desde, hasta):
    """A que frecuencia va un trozo de onda.

    Por autocorrelacion y no contando cruces por cero: las ondas de estos
    timbres **no son cuadradas limpias** -son FM, con sus armonicos- y cruzan
    el cero varias veces por ciclo, asi que contar cruces da el triple o el
    cuadruple de lo que es. Buscar el retardo en el que la onda se parece mas
    a si misma da el ciclo de verdad.
    """
    trozo = [float(v) for v in valores[desde:hasta]]
    if len(trozo) < 64:
        return 0.0
    ventana = min(len(trozo), 2048)
    trozo = trozo[:ventana]
    medio = sum(trozo) / len(trozo)
    trozo = [v - medio for v in trozo]
    mejor, mejor_lag = 0.0, 0
    lag_min = max(2, int(ritmo / 1200.0))      # hasta 1200 Hz
    lag_max = min(len(trozo) // 2, int(ritmo / 60.0))   # desde 60 Hz
    for lag in range(lag_min, lag_max):
        suma = 0.0
        for i in range(len(trozo) - lag):
            suma += trozo[i] * trozo[i + lag]
        if suma > mejor:
            mejor, mejor_lag = suma, lag
    return ritmo / float(mejor_lag) if mejor_lag else 0.0


class TestLoQueSale(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.project = load_project(EJEMPLO)
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-sonar-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_dura_lo_que_suman_sus_pasos(self):
        """Un paso dura `velocidad` frames y un frame es 1/60 de segundo. Si
        esto se descuadra, la musica va mas rapida o mas lenta que el juego."""
        cancion = sonar.buscar(self.project.sound, "cielorojo")
        ruta = sonar.escribir(cancion, os.path.join(self.tmp, "uno.wav"))
        valores, ritmo = _muestras(ruta)
        esperado = sonar.duracion(cancion)
        self.assertAlmostEqual(esperado, len(valores) / float(ritmo), places=1)

    def test_las_vueltas_se_repiten(self):
        cancion = sonar.buscar(self.project.sound, "elguardian")
        una = sonar.render(cancion, vueltas=1)
        dos = sonar.render(cancion, vueltas=2)
        self.assertAlmostEqual(len(una) * 2, len(dos), delta=4)

    def test_una_nota_sale_con_su_frecuencia(self):
        """La prueba que de verdad dice que esto toca lo que pone: la4 son
        440 Hz, y se mide contando por donde cruza el cero la onda."""
        una = cancion("prueba", ["la4:4"], velocidad=30)
        ruta = sonar.escribir(una, os.path.join(self.tmp, "la4.wav"))
        valores, ritmo = _muestras(ruta)
        # por el medio, lejos de la subida y de la bajada de la nota
        medido = _hercios(valores, ritmo, ritmo // 4, ritmo // 2)
        self.assertAlmostEqual(440.0, medido, delta=12.0,
                               msg="la4 tendria que dar 440 Hz y da %.0f"
                                   % medido)

    def test_cada_octava_dobla(self):
        """Y la de arriba, el doble: si esto no sale, la tabla de frecuencias
        esta mal en alguna parte."""
        for nota, hz in (("la3:4", 220.0), ("la5:4", 880.0)):
            with self.subTest(nota=nota):
                una = cancion("x", [nota], velocidad=30)
                ruta = sonar.escribir(una, os.path.join(self.tmp, "o.wav"))
                valores, ritmo = _muestras(ruta)
                medido = _hercios(valores, ritmo, ritmo // 4, ritmo // 2)
                self.assertAlmostEqual(hz, medido, delta=hz * 0.04)

    def test_el_silencio_es_silencio(self):
        """Un `-` no puede sonar a nada: ni a ruido, ni a la nota de antes
        arrastrada."""
        una = cancion("x", ["la4:2 - - la4:2"], velocidad=30)
        ruta = sonar.escribir(una, os.path.join(self.tmp, "hueco.wav"))
        valores, ritmo = _muestras(ruta)
        # los dos pasos de en medio son el silencio: medio segundo cada uno
        desde = int(ritmo * 30 * 2 / 60.0) + ritmo // 10
        hasta = int(ritmo * 30 * 4 / 60.0) - ritmo // 10
        callado = valores[desde:hasta]
        self.assertTrue(callado, "no hay trozo que mirar")
        tope = 2 if max(abs(v) for v in valores) < 200 else 64
        self.assertTrue(all(abs(v) <= tope for v in callado),
                        "el hueco suena: pico %d" % max(abs(v) for v in callado))

    def test_no_se_pasa_del_rango(self):
        """Pasarse del rango es que la onda se corte por arriba y chasque."""
        for nombre in ("cielorojo", "lahuida", "elguardian"):
            with self.subTest(cancion=nombre):
                cancion = sonar.buscar(self.project.sound, nombre)
                ruta = sonar.escribir(cancion,
                                      os.path.join(self.tmp, "r.wav"))
                valores, _ = _muestras(ruta)
                self.assertLessEqual(max(valores), 32767)
                self.assertGreaterEqual(min(valores), -32768)
                # y que no este muerta: una cancion muda seria un fallo mudo
                vivos = sum(1 for v in valores if abs(v) > 1000)
                self.assertGreater(vivos, len(valores) // 4,
                                   "'%s' sale practicamente en silencio" % nombre)

    def test_se_aprovecha_el_rango(self):
        """Antes el pico se quedaba a la mitad de la escala y en 8 bits eso es
        tirar un bit de los ocho: ruido de cuantizacion de balde."""
        cancion = sonar.buscar(self.project.sound, "cielorojo")
        ruta = sonar.escribir(cancion, os.path.join(self.tmp, "p.wav"))
        valores, _ = _muestras(ruta)
        pico = max(abs(v) for v in valores)
        self.assertGreater(pico, 32767 * 0.8,
                           "el pico se queda en %d de 32767" % pico)
        self.assertLessEqual(pico, 32767)

    def test_tambien_sale_de_ocho_bits_si_se_pide(self):
        """`--bits 8` para ver como queda la tabla en crudo."""
        cancion = sonar.buscar(self.project.sound, "elguardian")
        ruta = sonar.escribir(cancion, os.path.join(self.tmp, "ocho.wav"),
                              bits=8)
        with wave.open(ruta) as fh:
            self.assertEqual(1, fh.getsampwidth())


class TestLaOrden(unittest.TestCase):

    def test_saca_todas_las_canciones(self):
        tmp = tempfile.mkdtemp(prefix="neoplat-sonar-cli-")
        self.addCleanup(shutil.rmtree, tmp, True)
        hecho = subprocess.run(
            [sys.executable, os.path.join(KIT, "ngplat"), "sonar", EJEMPLO,
             "--todas", "--salida", tmp],
            capture_output=True, text=True, env=dict(os.environ, NO_COLOR="1"))
        self.assertEqual(0, hecho.returncode, hecho.stderr)
        salieron = sorted(f for f in os.listdir(tmp) if f.endswith(".wav"))
        esperadas = sorted("%s.wav" % c for c in
                           load_project(EJEMPLO).sound.musica)
        self.assertEqual(esperadas, salieron)

    def test_una_cancion_que_no_existe_se_dice(self):
        hecho = subprocess.run(
            [sys.executable, os.path.join(KIT, "ngplat"), "sonar", EJEMPLO,
             "--cancion", "nohaytal"],
            capture_output=True, text=True, env=dict(os.environ, NO_COLOR="1"))
        self.assertNotEqual(0, hecho.returncode)
        todo = hecho.stdout + hecho.stderr
        self.assertIn("nohaytal", todo)
        # y dice cuales hay, que es lo que hace falta saber en ese momento
        self.assertIn("cielorojo", todo)

    def test_el_wav_es_un_wav(self):
        """Suena tonto, pero una cabecera mal escrita no la detecta nadie
        hasta que alguien intenta abrir el archivo."""
        tmp = tempfile.mkdtemp(prefix="neoplat-sonar-wav-")
        self.addCleanup(shutil.rmtree, tmp, True)
        destino = os.path.join(tmp, "x.wav")
        subprocess.run(
            [sys.executable, os.path.join(KIT, "ngplat"), "sonar", EJEMPLO,
             "--cancion", "lahuida", "--salida", destino],
            capture_output=True, text=True, check=True)
        with open(destino, "rb") as fh:
            cabecera = fh.read(44)
        self.assertEqual(b"RIFF", cabecera[:4])
        self.assertEqual(b"WAVE", cabecera[8:12])
        canales, ritmo = struct.unpack("<HI", cabecera[22:28])
        self.assertEqual(1, canales)
        self.assertEqual(44100, ritmo)
        self.assertEqual(16, struct.unpack("<H", cabecera[34:36])[0])


if __name__ == "__main__":
    unittest.main()
