"""El driver de muestras de la Mega Drive: se ensambla y se ejecuta.

No es una prueba de "compila y ya". El driver del Z80 (tools/ngplat/md_pcm.py)
se ejecuta en el emulador de Z80 del kit, con la memoria de la Mega Drive
imitada por encima -el YM2612 en $4000, el registro de banco en $6000 y la
ventana de 32 KB del cartucho en $8000-, y se comprueba que le manda al DAC
**exactamente los bytes de la muestra, en orden**, incluso cuando la muestra
cruza el borde de los 32 KB.

Y la frecuencia: el ritmo lo marca la cuenta de ciclos del bucle, asi que la
prueba vuelve a sumar los ciclos leyendo el codigo ya ensamblado. Si alguien
toca el bucle y se olvida de la cuenta, esto lo dice.
"""

import unittest

import comun  # noqa: F401  (mete tools/ en el path)
import z80sim

from ngplat import md_pcm

# Ciclos (estados T) de las instrucciones del bucle. Solo estan las que usa:
# cualquier otra hace fallar la prueba a proposito, para que nadie meta una
# instruccion nueva sin contar lo que cuesta.
CICLOS_Z80 = {
    0x7E: (1, 7),    # ld a,(hl)
    0x32: (3, 13),   # ld (nn),a
    0x23: (1, 6),    # inc hl
    0x7C: (1, 4),    # ld a,h
    0xB7: (1, 4),    # or a
    0xCA: (3, 10),   # jp z,nn
    0x0B: (1, 6),    # dec bc
    0x78: (1, 4),    # ld a,b
    0xB1: (1, 4),    # or c
    0x3E: (2, 7),    # ld a,n
    0x3D: (1, 4),    # dec a
    0xC2: (3, 10),   # jp nz,nn
    0xC3: (3, 10),   # jp nn
}


class Maquina(z80sim.Z80):
    """El Z80 de la Mega Drive: su RAM, el YM2612, el banco y el cartucho.

    El emulador del kit reparte la memoria en "ROM abajo y RAM arriba", que es
    como esta la Neo Geo. Aqui es al reves -codigo y datos en la RAM de abajo,
    cartucho por una ventana arriba-, asi que se sustituyen las dos funciones
    de acceso.
    """

    def __init__(self, codigo, cartucho):
        z80sim.Z80.__init__(self, bytes(0x100))
        self.memoria = bytearray(0x2000)
        self.memoria[:len(codigo)] = codigo
        self.cartucho = cartucho
        self.banco = 0
        self.bits_banco = []
        self.dac = []                 # lo que ha ido al DAC
        self.registro_ym = -1
        self.ym = {}                  # ultimo valor escrito en cada registro

    def leer(self, direccion):
        direccion &= 0xFFFF
        if direccion < 0x2000:
            return self.memoria[direccion]
        if direccion >= 0x8000:
            fisica = (self.banco << 15) | (direccion & 0x7FFF)
            return self.cartucho[fisica] if fisica < len(self.cartucho) else 0
        return 0

    def escribir(self, direccion, valor):
        direccion &= 0xFFFF
        valor &= 0xFF
        if direccion < 0x2000:
            self.memoria[direccion] = valor
            return
        if direccion == 0x4000:
            self.registro_ym = valor
            return
        if direccion == 0x4001:
            if self.registro_ym == 0x2A:
                self.dac.append(valor)
            else:
                self.ym[self.registro_ym] = valor
            return
        if direccion == 0x6000:
            # nueve escrituras, un bit por escritura y del bajo al alto
            self.bits_banco.append(valor & 1)
            if len(self.bits_banco) == 9:
                self.banco = sum(b << i for i, b in enumerate(self.bits_banco))
                self.bits_banco = []
            return

    def correr(self, pasos):
        for _ in range(pasos):
            self.paso()

    def pedir(self, direccion, largo):
        """Lo que hace el 68000: dejar el bloque y cambiar el tick."""
        banco = direccion >> 15
        dentro = 0x8000 | (direccion & 0x7FFF)
        self.memoria[md_pcm.CMD_BANCO] = banco & 0xFF
        self.memoria[md_pcm.CMD_BANCO + 1] = banco >> 8
        self.memoria[md_pcm.CMD_DIR] = dentro & 0xFF
        self.memoria[md_pcm.CMD_DIR + 1] = dentro >> 8
        self.memoria[md_pcm.CMD_LARGO] = largo & 0xFF
        self.memoria[md_pcm.CMD_LARGO + 1] = largo >> 8
        self.memoria[md_pcm.CMD_TICK] = (self.memoria[md_pcm.CMD_TICK] + 1) & 0xFF


def _cartucho(tamano=96 * 1024):
    """Un cartucho de mentira con bytes reconocibles: el byte de la direccion
    N es (N * 7 + 3) mod 256, que no repite ningun patron corto."""
    return bytes((i * 7 + 3) & 0xFF for i in range(tamano))


class TestDriver(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codigo, cls.etiquetas = md_pcm.generar()

    def _tocar(self, direccion, largo, pasos=400000):
        maquina = Maquina(self.codigo, _cartucho())
        maquina.correr(200)                    # que llegue a la espera
        maquina.pedir(direccion, largo)
        maquina.correr(pasos)
        return maquina

    def test_enciende_el_dac_del_ym2612(self):
        maquina = Maquina(self.codigo, _cartucho())
        maquina.correr(50)
        self.assertEqual(maquina.ym.get(0x2B), 0x80,
                         "no ha encendido el DAC (registro $2B)")
        self.assertEqual(maquina.registro_ym, 0x2A,
                         "no ha dejado la direccion en el registro del DAC")

    def test_manda_al_dac_los_bytes_de_la_muestra(self):
        cartucho = _cartucho()
        direccion, largo = 0x1234, 300
        maquina = self._tocar(direccion, largo)
        esperado = list(cartucho[direccion:direccion + largo])
        # el primero es el silencio del arranque y el ultimo el de despues
        self.assertEqual(maquina.dac[1:1 + largo], esperado,
                         "los bytes que llegan al DAC no son los de la muestra")
        self.assertEqual(maquina.dac[-1], 0x80,
                         "al acabar no deja el DAC en silencio")

    def test_una_muestra_que_cruza_el_borde_de_los_32_kb(self):
        """El Z80 solo ve 32 KB del cartucho a la vez. Si la muestra cruza el
        borde hay que cambiar de banco sobre la marcha, y ahi es donde se
        rompen estas cosas."""
        cartucho = _cartucho()
        direccion, largo = 0x8000 - 100, 260   # 100 antes del borde y 160 despues
        maquina = self._tocar(direccion, largo)
        esperado = list(cartucho[direccion:direccion + largo])
        self.assertEqual(maquina.dac[1:1 + largo], esperado,
                         "al cambiar de banco se pierde o se repite algun byte")
        self.assertEqual(maquina.banco, (direccion >> 15) + 1,
                         "no ha subido el banco")

    def test_una_muestra_detras_de_otra(self):
        """El driver vuelve a la espera y atiende la siguiente, que es lo que
        pasa cuando se recogen dos monedas seguidas."""
        cartucho = _cartucho()
        maquina = Maquina(self.codigo, _cartucho())
        maquina.correr(200)
        maquina.pedir(0x0400, 50)
        maquina.correr(60000)
        maquina.dac = []
        maquina.pedir(0x2000, 40)
        maquina.correr(60000)
        self.assertEqual(maquina.dac[:40], list(cartucho[0x2000:0x2000 + 40]),
                         "la segunda muestra no suena")

    def test_la_cuenta_de_ciclos_es_la_que_dice(self):
        """El ritmo lo marca la cuenta de ciclos del bucle, no un temporizador,
        asi que aqui se vuelve a sumar leyendo el codigo ensamblado."""
        bucle = self.etiquetas["bucle"]
        retardo = self.etiquetas["retardo"]

        def sumar(desde, hasta):
            total, pc = 0, desde
            while pc < hasta:
                opcode = self.codigo[pc]
                self.assertIn(opcode, CICLOS_Z80,
                              "el bucle usa una instruccion sin contar ($%02X en "
                              "$%04X): anadela a CICLOS_Z80" % (opcode, pc))
                largo, ciclos = CICLOS_Z80[opcode]
                total += ciclos
                pc += largo
            return total

        # de `bucle` a `retardo` va la parte que se hace una vez por muestra;
        # de `retardo` al final, el bucle de espera mas el salto de vuelta
        fijo = sumar(bucle, retardo)
        dentro = sumar(retardo, retardo + 4)        # dec a (1) + jp nz (3)
        vuelta = sumar(retardo + 4, retardo + 7)    # jp bucle (3)
        total = fijo + dentro * md_pcm.RETARDO + vuelta
        self.assertEqual(total, md_pcm.CICLOS,
                         "el bucle mide %d ciclos y md_pcm.py dice %d"
                         % (total, md_pcm.CICLOS))
        self.assertEqual(md_pcm.RITMO, md_pcm.RELOJ // total)
        self.assertTrue(7000 <= md_pcm.RITMO <= 9000,
                        "%d Hz no es una frecuencia razonable" % md_pcm.RITMO)

    def test_cabe_en_la_ram_del_z80(self):
        self.assertLess(len(self.codigo), md_pcm.RAM,
                        "el driver pisa el bloque compartido")


if __name__ == "__main__":
    unittest.main()
