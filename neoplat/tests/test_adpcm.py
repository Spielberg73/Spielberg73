"""El codec ADPCM-A del YM2610: cifrar, descifrar y que suene lo mismo."""

import math
import unittest

import comun  # noqa: F401  (mete tools/ en el path)
import sonido as analisis

from ngplat import adpcm


def _seno(hz, segundos, amplitud=100, ritmo=adpcm.RITMO):
    return [int(amplitud * math.sin(2 * math.pi * hz * i / ritmo))
            for i in range(int(ritmo * segundos))]


def _ruido(cuantas, semilla=1):
    estado = semilla
    salida = []
    for _ in range(cuantas):
        estado = (estado * 1103515245 + 12345) & 0x7FFFFFFF
        salida.append((estado >> 16 & 0xFF) - 128)
    return salida


class TestPasos(unittest.TestCase):
    def test_la_tabla_es_la_del_chip(self):
        self.assertEqual(len(adpcm.PASOS), 49)
        self.assertEqual(adpcm.PASOS[0], 16)
        self.assertEqual(adpcm.PASOS[-1], 1552)
        # cada paso crece, y ninguno mas de un 12%
        for antes, ahora in zip(adpcm.PASOS, adpcm.PASOS[1:]):
            self.assertGreater(ahora, antes)
            self.assertLess(ahora, antes * 1.13)

    def test_el_indice_no_se_sale(self):
        """Los cuatro nibbles grandes suben el indice y los pequenos lo bajan;
        pase lo que pase tiene que quedarse entre 0 y 48."""
        valor, indice = 0, 0
        for nibble in [7] * 100 + [0] * 100:
            valor, indice = adpcm._paso(nibble, indice, valor)
            self.assertTrue(0 <= indice <= 48)
            self.assertTrue(adpcm.MINIMO <= valor <= adpcm.MAXIMO)


class TestIdaYVuelta(unittest.TestCase):
    def _snr(self, muestras):
        datos = adpcm.cifrar(muestras)
        vuelta = adpcm.descifrar(datos, len(muestras))
        self.assertEqual(len(vuelta), len(muestras))
        error = sum((m * 16 - v) ** 2 for m, v in zip(muestras, vuelta))
        senal = sum((m * 16) ** 2 for m in muestras)
        return 10 * math.log10(senal / max(1e-9, error))

    def test_comprime_a_la_mitad(self):
        muestras = _seno(440, 0.1)
        self.assertEqual(len(adpcm.cifrar(muestras)), (len(muestras) + 1) // 2)

    def test_una_nota_sobrevive(self):
        """Cuatro bits por muestra pierden calidad, pero la onda tiene que
        seguir siendo reconocible: mas de 25 dB de relacion senal/ruido."""
        self.assertGreater(self._snr(_seno(440, 0.2)), 25.0)
        self.assertGreater(self._snr(_seno(2000, 0.2)), 20.0)

    def test_hasta_el_ruido_sobrevive(self):
        """El caso malo del ADPCM: una senal que salta de un extremo a otro."""
        self.assertGreater(self._snr(_ruido(4000)), 10.0)

    def test_la_frecuencia_no_cambia(self):
        """Si el codec se equivocara de paso o de signo, la onda seguiria
        teniendo energia pero ya no seria la misma nota."""
        muestras = _seno(1000, 0.3)
        vuelta = adpcm.descifrar(adpcm.cifrar(muestras), len(muestras))
        canal = [v / 2048.0 for v in vuelta]
        en_1000 = analisis.energia(canal, adpcm.RITMO, 1000.0)
        for hz in (500.0, 1500.0, 3000.0):
            self.assertGreater(en_1000, analisis.energia(canal, adpcm.RITMO, hz) * 8,
                               "a %g Hz suena casi tanto como a 1000" % hz)

    def test_el_silencio_se_queda_callado(self):
        vuelta = adpcm.descifrar(adpcm.cifrar([0] * 2000), 2000)
        self.assertLess(max(abs(v) for v in vuelta[100:]), 40,
                        "el predictor se va solo: el silencio hace ruido")


class TestBloques(unittest.TestCase):
    def test_cifrar_muestra_redondea_al_bloque(self):
        """El chip direcciona la ROM V1 de 256 en 256 bytes, asi que cada
        muestra tiene que ocupar bloques enteros."""
        for largo in (1, 100, 511, 512, 513, 5000):
            datos = adpcm.cifrar_muestra(bytes(largo))
            self.assertEqual(len(datos) % adpcm.BLOQUE, 0,
                             "%d muestras no dan bloques enteros" % largo)
            self.assertGreaterEqual(len(datos) * 2, largo)

    def test_el_relleno_es_silencio(self):
        """Lo que se anade para llenar el bloque no puede sonar: seria un
        chasquido al final de cada efecto."""
        datos = adpcm.cifrar_muestra(bytes(300))
        vuelta = adpcm.descifrar(datos)
        self.assertLess(max(abs(v) for v in vuelta), 60)


if __name__ == "__main__":
    unittest.main()
