"""El lector de WAV y las muestras digitales, sin emulador de por medio."""

import math
import os
import struct
import tempfile
import unittest

import comun
from comun import escribir

from ngplat import art_sonido, wav
from ngplat.errors import ProjectError
from ngplat.project import load_project


def _wav(datos, ritmo=22050, canales=1, bits=16):
    """Monta un archivo WAV a mano, para dar de comer al lector."""
    bloque = canales * bits // 8
    return (b"RIFF" + struct.pack("<I", 36 + len(datos)) + b"WAVEfmt "
            + struct.pack("<IHHIIHH", 16, 1, canales, ritmo,
                          ritmo * bloque, bloque, bits)
            + b"data" + struct.pack("<I", len(datos)) + datos)


def _seno(hz, segundos, ritmo=22050, amplitud=20000):
    return b"".join(
        struct.pack("<h", int(amplitud * math.sin(2 * math.pi * hz * i / ritmo)))
        for i in range(int(ritmo * segundos)))


class TestLeerWav(unittest.TestCase):
    def test_16_bits_mono(self):
        m = wav.descifrar(_wav(_seno(440, 0.1)))
        self.assertEqual(m.ritmo, 22050)
        self.assertEqual(len(m), 2205)
        self.assertAlmostEqual(m.segundos, 0.1, places=3)
        # 20000 de 32767 son unos 78 de 127
        self.assertGreater(max(m.con_signo()), 70)
        self.assertLess(min(m.con_signo()), -70)

    def test_8_bits_van_sin_signo(self):
        """En WAV, 8 bits es 0..255 con el silencio en 128; el kit los usa con
        signo. Si no se restara ese 128, el silencio saldria a tope."""
        m = wav.descifrar(_wav(bytes([128, 128, 128, 255, 0]), bits=8))
        self.assertEqual(m.con_signo(), [0, 0, 0, 127, -128])

    def test_estereo_se_mezcla_a_mono(self):
        izquierda = struct.pack("<h", 20000)
        derecha = struct.pack("<h", -20000)
        m = wav.descifrar(_wav((izquierda + derecha) * 4, canales=2))
        self.assertEqual(len(m), 4)
        self.assertEqual(set(m.con_signo()), {0})

    def test_un_wav_comprimido_se_rechaza_con_una_pista(self):
        crudo = bytearray(_wav(b"\0" * 16))
        crudo[20] = 17                      # formato ADPCM
        with self.assertRaises(wav.WavError) as caso:
            wav.descifrar(bytes(crudo))
        self.assertIn("PCM", str(caso.exception))

    def test_lo_que_no_es_un_wav(self):
        with self.assertRaises(wav.WavError):
            wav.descifrar(b"esto no es un wav para nada")

    def test_ida_y_vuelta(self):
        m = wav.descifrar(_wav(_seno(440, 0.05)))
        vuelta = wav.descifrar(wav.codificar(m))
        self.assertEqual(vuelta.datos, m.datos)
        self.assertEqual(vuelta.ritmo, m.ritmo)


class TestRemuestrear(unittest.TestCase):
    def test_dura_lo_mismo(self):
        m = wav.descifrar(_wav(_seno(440, 0.2)))
        for ritmo in (8000, 11025, 44100):
            otra = wav.remuestrear(m, ritmo)
            self.assertEqual(otra.ritmo, ritmo)
            self.assertAlmostEqual(otra.segundos, m.segundos, places=2)

    def test_la_nota_sigue_siendo_la_misma(self):
        """Remuestrear mal (perdiendo o repitiendo muestras) cambia el tono, y
        eso no lo ve una prueba que solo mire cuantos bytes salen."""
        import sonido as analisis
        m = wav.descifrar(_wav(_seno(1000, 0.3, ritmo=44100), ritmo=44100))
        otra = wav.remuestrear(m, 11025)
        canal = [v / 128.0 for v in otra.con_signo()]
        en_1000 = analisis.energia(canal, 11025, 1000.0)
        for hz in (700.0, 1400.0, 2000.0):
            self.assertGreater(en_1000, analisis.energia(canal, 11025, hz) * 8,
                               "a %g Hz suena casi tanto como a 1000" % hz)

    def test_recortar_deja_el_final_bajando(self):
        m = wav.Muestra(bytes([100] * 1000), 11025)
        corta = wav.recortar(m, 200)
        self.assertEqual(len(corta), 200)
        self.assertEqual(corta.con_signo()[0], 100)
        self.assertLess(corta.con_signo()[-1], 20, "acaba de golpe: chasquea")


class TestMuestrasDelAndamiaje(unittest.TestCase):
    def test_el_proyecto_nuevo_trae_sus_wav(self):
        with comun.ProyectoTemporal() as ruta:
            for relativo in art_sonido.todos():
                self.assertTrue(os.path.isfile(os.path.join(ruta, relativo)),
                                "falta " + relativo)
            proyecto = load_project(os.path.join(ruta, "game.yaml"))
            digitales = [n for n, e in proyecto.sound.efectos.items() if e.digital]
            self.assertEqual(sorted(digitales), ["golpe", "moneda"])
            # y siguen teniendo notas de recambio para el Atari ST
            for nombre in digitales:
                self.assertTrue(proyecto.sound.efectos[nombre].pasos,
                                "'%s' se quedaria mudo en el Atari ST" % nombre)

    def test_salen_siempre_iguales(self):
        """Los WAV de ejemplo se generan por codigo: si no fueran repetibles,
        dos proyectos nuevos no serian el mismo proyecto."""
        self.assertEqual(art_sonido.todos()["sonidos/golpe.wav"].datos,
                         art_sonido.todos()["sonidos/golpe.wav"].datos)


class TestMuestraEnElYaml(unittest.TestCase):
    def _proyecto(self, efecto):
        carpeta = tempfile.mkdtemp(prefix="neoplat-wav-")
        comun.crear_proyecto(carpeta + "/juego", "PRUEBA", "TEST")
        raiz = carpeta + "/juego"
        yaml = os.path.join(raiz, "game.yaml")
        with open(yaml, encoding="utf-8") as fh:
            texto = fh.read()
        marca = "    salto:   {tipo: barrido, desde: 320, hasta: 900, duracion: 6}"
        assert marca in texto
        escribir(yaml, texto.replace(marca, "    salto:   " + efecto, 1))
        return raiz

    def test_una_muestra_sin_notas_no_tiene_pasos(self):
        raiz = self._proyecto("{muestra: sonidos/moneda.wav}")
        proyecto = load_project(os.path.join(raiz, "game.yaml"))
        salto = proyecto.sound.efectos["salto"]
        self.assertTrue(salto.digital)
        self.assertEqual(salto.pasos, [])

    def test_muestra_y_notas_conviven(self):
        """El recambio para las maquinas que no tocan muestras. Antes esto no
        funcionaba: poner 'tipo: ruido' al lado de 'muestra:' se comia la
        muestra."""
        raiz = self._proyecto(
            "{muestra: sonidos/moneda.wav, tipo: ruido, duracion: 10}")
        salto = load_project(os.path.join(raiz, "game.yaml")).sound.efectos["salto"]
        self.assertTrue(salto.digital)
        self.assertTrue(salto.pasos, "se ha perdido el recambio de notas")

    def test_si_falta_el_archivo_lo_dice(self):
        raiz = self._proyecto("{muestra: sonidos/no-existe.wav}")
        with self.assertRaises(ProjectError) as caso:
            load_project(os.path.join(raiz, "game.yaml"))
        self.assertIn("no-existe.wav", str(caso.exception))

    def test_tipo_muestra_sin_archivo_se_queja(self):
        raiz = self._proyecto("{tipo: muestra, volumen: 10}")
        with self.assertRaises(ProjectError) as caso:
            load_project(os.path.join(raiz, "game.yaml"))
        self.assertIn("sonar", str(caso.exception))


if __name__ == "__main__":
    unittest.main()
