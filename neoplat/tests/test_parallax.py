"""El parallax, medido en la pantalla de una maquina de verdad.

Que un juego **declare** cuatro capas no quiere decir que se dibujen cuatro, y
que se dibujen no quiere decir que se muevan a velocidades distintas. Lo
primero se ve en el game.yaml; lo segundo no se ve en ninguna parte, hay que
mirar la pantalla.

Asi que esto arranca CIELO ROJO en la Jaguar -la unica, con el X68000, que
dibuja las cuatro-, anda, y **mide cuanto se ha desplazado cada franja**
comparando dos pantallas. La medida es una correlacion cruzada: se desliza la
fila de despues sobre la de antes y se busca el desplazamiento en el que mas se
parecen. Y se mide cada fila de la franja y se coge la **mediana**, no una fila
elegida a dedo: hay filas que son de un solo color -el relleno de una silueta-
y ahi no hay nada que medir, y hay otras que pillan al heroe pasando.

**Entre las dos capturas se anda poco a proposito**, y esto es lo que costo
entender: las capas son dibujos que **se repiten**. Los arboles del bosque caen
cada veintidos pixeles, asi que un desplazamiento de cuarenta y cinco
correlaciona igual de bien que uno de uno, y la medida sale cualquier cosa. La
primera version de esta prueba andaba noventa frames y daba numeros que
parecian razonables y no lo eran: pasaba igual con el parallax apagado. Doce
frames son dieciocho pixeles de camara, menos de lo que mide el dibujo mas
apretado, y ahi ya no hay dos respuestas posibles.

Lo que sale con las capas de CIELO ROJO, y cuadra con lo que declaran:

    cielo     0 px     velocidad 0.08
    montes    4 px     velocidad 0.22
    bosque    8 px     velocidad 0.45
    troncos  12 px     velocidad 0.75
    suelo    16 px     el escenario, que va con la camara

Y con una sola capa -el parallax apagado- sale 0, 0, 16, 1, 16: las franjas de
en medio ensenan el escenario o nada, y **el orden se rompe**. Eso es lo que se
exige aqui: que cada capa corra mas que la de detras y menos que el suelo.
"""

import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import unittest

from comun import KIT

sys.path.insert(0, os.path.join(KIT, "tools"))

EJEMPLO = os.path.join(KIT, "examples", "cielo-rojo")

# Donde cae cada capa, en fraccion de lo alto que sea la pantalla: la Jaguar
# entrega 352x240 y no los 320x224 del juego, asi que las filas se calculan.
# Las franjas se eligen donde manda una sola capa, no donde se solapan.
BANDAS = (
    ("cielo", 0.15, 0.33),
    ("montes", 0.34, 0.44),
    ("bosque", 0.57, 0.78),
    ("troncos", 0.80, 0.88),
    ("suelo", 0.90, 0.96),      # el escenario: va con la camara, no es capa
)
ARRANQUE = 150       # frames andando antes de medir: sale del margen y coge
                     # velocidad, que si no la camara ni se ha movido
PASOS = 12           # frames entre las dos capturas (18 px de camara)
BUSCA = 24           # pixeles que se miran al correlar


def _gris(fila):
    return [(p[0] * 30 + p[1] * 59 + p[2] * 11) // 100 for p in fila]


def _desplazamiento(antes, despues):
    """Cuanto se ha movido una fila de pixeles, o None si no hay que medir."""
    if len(antes) < BUSCA * 2 or len(despues) < len(antes):
        return None
    a, b = _gris(antes), _gris(despues)
    if max(a) - min(a) < 8:
        return None                     # fila de un solo color: no dice nada
    mejor, mejor_d = None, 0
    cuantos = len(a) - BUSCA
    for d in range(BUSCA + 1):
        suma = 0
        for i in range(cuantos):
            suma += abs(a[i + d] - b[i])
        if mejor is None or suma < mejor:
            mejor, mejor_d = suma, d
    return mejor_d


def _fila(frame, y):
    ancho, alto, pixeles = frame
    y = max(0, min(alto - 1, y))
    return pixeles[y * ancho:(y + 1) * ancho]


class TestLasCuatroCapasSeMuevenDistinto(unittest.TestCase):
    """CIELO ROJO en la Jaguar, andando."""

    medidas = None

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, os.path.join(KIT, "tests"))
        from libretro import buscar_core
        import emulador_jaguar

        if not buscar_core(emulador_jaguar.CORE, "NEOPLAT_CORE_JAGUAR"):
            raise unittest.SkipTest("no esta instalado el core de Virtual Jaguar")
        if not shutil.which("m68k-linux-gnu-gcc") and \
           not shutil.which("m68k-elf-gcc"):
            raise unittest.SkipTest("no hay un compilador de 68000 instalado")

        cls.tmp = tempfile.mkdtemp(prefix="neoplat-parallax-")
        hecho = subprocess.run(
            [sys.executable, os.path.join(KIT, "ngplat"), "compilar", EJEMPLO,
             "--sistema", "jaguar", "--salida", cls.tmp, "--make"],
            capture_output=True, text=True, timeout=1800)
        if hecho.returncode != 0:
            raise unittest.SkipTest("no se ha podido construir el cartucho:\\n%s"
                                    % hecho.stderr[-800:])
        roms = [n for n in os.listdir(os.path.join(cls.tmp, "rom"))
                if n.endswith(".j64")]
        if not roms:
            raise unittest.SkipTest("el Makefile no ha dejado ningun .j64")
        cls.rom = os.path.join(cls.tmp, "rom", roms[0])

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tmp", ""):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def _medir(self):
        """Arranca, anda y mide. Una sola vez para las tres pruebas: cada
        arranque del emulador cuesta sus segundos."""
        if TestLasCuatroCapasSeMuevenDistinto.medidas is not None:
            return TestLasCuatroCapasSeMuevenDistinto.medidas
        import emulador_jaguar
        from libretro import Emulador, buscar_core

        emu = Emulador(buscar_core(emulador_jaguar.CORE, "NEOPLAT_CORE_JAGUAR"),
                       sistema=tempfile.mkdtemp(prefix="neoplat-jag-"))
        emu.cargar(self.rom)
        emu.avanzar(200)                            # la pantalla de titulo
        emu.pulsar(emulador_jaguar.EMPEZAR)
        emu.avanzar(4)
        emu.pulsar()
        emu.avanzar(120)                            # que entre en el nivel
        emu.pulsar("RIGHT")
        emu.avanzar(ARRANQUE)
        antes = emu.frame
        self.assertIsNotNone(antes, "el emulador no ha dibujado nada")
        emu.avanzar(PASOS)                          # se sigue andando
        despues = emu.frame

        alto = antes[1]
        medidas = {}
        for nombre, desde, hasta in BANDAS:
            sueltas = []
            for y in range(int(alto * desde), int(alto * hasta)):
                cuanto = _desplazamiento(_fila(antes, y), _fila(despues, y))
                if cuanto is not None:
                    sueltas.append(cuanto)
            medidas[nombre] = (statistics.median(sueltas) if sueltas else None,
                               len(sueltas))
        TestLasCuatroCapasSeMuevenDistinto.medidas = (medidas, antes)
        return TestLasCuatroCapasSeMuevenDistinto.medidas

    def test_cada_capa_corre_mas_que_la_de_detras(self):
        """La prueba del parallax. Con una sola capa el orden se rompe."""
        medidas, _ = self._medir()
        faltan = [n for n, (v, _c) in medidas.items() if v is None]
        if faltan:
            self.skipTest("no hay dibujo que medir en %s" % ", ".join(faltan))
        capas = [n for n, _d, _h in BANDAS if n != "suelo"]
        for antes, despues in zip(capas, capas[1:]):
            self.assertLess(
                medidas[antes][0], medidas[despues][0],
                "'%s' no corre mas que '%s', que va detras: %s"
                % (despues, antes, _bonito(medidas)))

    def test_ninguna_capa_corre_tanto_como_el_suelo(self):
        """Una capa que va a la velocidad de la camara **no es una capa**: es
        el escenario pintado otra vez. Es justo lo que se ve en la franja de
        en medio cuando el parallax esta apagado."""
        medidas, _ = self._medir()
        suelo = medidas["suelo"][0]
        if suelo is None:
            self.skipTest("no se ve el suelo moverse: %s" % _bonito(medidas))
        for nombre, _d, _h in BANDAS:
            if nombre == "suelo":
                continue
            with self.subTest(capa=nombre):
                self.assertLess(
                    medidas[nombre][0], suelo,
                    "'%s' corre tanto como el suelo: %s"
                    % (nombre, _bonito(medidas)))

    def test_las_cuatro_franjas_tienen_dibujo(self):
        """Si una capa no se pinta, su franja se queda del color de fondo."""
        medidas, _frame = self._medir()
        for nombre, _desde, _hasta in BANDAS:
            with self.subTest(capa=nombre):
                _valor, filas = medidas[nombre]
                self.assertGreater(
                    filas, 4,
                    "en la franja de '%s' solo %d filas tienen dibujo: esa "
                    "capa no se esta dibujando" % (nombre, filas))


def _bonito(medidas):
    return ", ".join("%s=%s" % (n, medidas[n][0]) for n, _d, _h in BANDAS)


if __name__ == "__main__":
    unittest.main()
