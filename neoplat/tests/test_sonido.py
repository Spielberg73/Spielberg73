"""El driver de sonido: se ensambla y se ejecuta en un emulador de Z80.

No es una prueba de "compila y ya": el driver se ejecuta de verdad, recibe
comandos como los que manda el 68000 y se comprueba que escribe en el YM2610
los periodos y volumenes que corresponden a las notas del game.yaml.
"""

import os
import unittest

import comun
from comun import KIT

import z80sim
from ngplat import m1 as m1_mod
from ngplat import sonido as sonido_mod
from ngplat.errors import ProjectError
from ngplat.project import load_project
from ngplat.z80 import Z80Error, ensamblar

EJEMPLO = os.path.join(KIT, "examples", "bosque-magico")


class TestNotas(unittest.TestCase):
    def test_la4_son_440_hz(self):
        self.assertAlmostEqual(sonido_mod.frecuencia_de_nota(9, 4), 440.0, places=6)

    def test_periodo_de_la4(self):
        # periodo = 4 MHz / (16 * 440) = 568
        self.assertEqual(sonido_mod.periodo_de_frecuencia(440), 568)

    def test_una_octava_es_el_doble_de_frecuencia(self):
        do4 = sonido_mod.periodo_de_frecuencia(sonido_mod.frecuencia_de_nota(0, 4))
        do5 = sonido_mod.periodo_de_frecuencia(sonido_mod.frecuencia_de_nota(0, 5))
        self.assertAlmostEqual(do4 / float(do5), 2.0, places=2)

    def test_notas_en_espanol_y_en_ingles(self):
        espanol = sonido_mod.parsear_notas("do4 mi4 sol4", 4, 12, "t")
        ingles = sonido_mod.parsear_notas("c4 e4 g4", 4, 12, "t")
        self.assertEqual([p.periodo for p in espanol], [p.periodo for p in ingles])

    def test_silencios_y_duraciones(self):
        pasos = sonido_mod.parsear_notas("do4 - sol4:3", 4, 12, "t")
        self.assertEqual(pasos[1].periodo, 0)
        self.assertEqual(pasos[2].duracion, 12)

    def test_nota_mal_escrita(self):
        with self.assertRaises(ProjectError) as ctx:
            sonido_mod.parsear_notas("do4 xyz", 4, 12, "prueba")
        self.assertIn("xyz", ctx.exception.message)

    def test_nota_fuera_del_alcance_del_chip(self):
        # do0 son unos 16 Hz: el periodo se sale de los 12 bits del chip
        with self.assertRaises(ProjectError):
            sonido_mod.parsear_notas("do0", 4, 12, "t")


class TestEnsamblador(unittest.TestCase):
    """Codificaciones conocidas del juego de instrucciones del Z80."""

    def assertEnsambla(self, fuente, esperado):
        codigo, _ = ensamblar("org 0\n" + fuente)
        self.assertEqual(list(codigo), esperado, fuente)

    def test_instrucciones_basicas(self):
        self.assertEnsambla("nop", [0x00])
        self.assertEnsambla("di", [0xF3])
        self.assertEnsambla("ret", [0xC9])
        self.assertEnsambla("retn", [0xED, 0x45])
        self.assertEnsambla("ld a,$3f", [0x3E, 0x3F])
        self.assertEnsambla("ld b,c", [0x41])
        self.assertEnsambla("ld (hl),a", [0x77])
        self.assertEnsambla("ld a,(hl)", [0x7E])
        self.assertEnsambla("ld hl,$1234", [0x21, 0x34, 0x12])
        self.assertEnsambla("ld sp,$fffe", [0x31, 0xFE, 0xFF])
        self.assertEnsambla("ld ($f800),a", [0x32, 0x00, 0xF8])
        self.assertEnsambla("ld a,($f800)", [0x3A, 0x00, 0xF8])
        self.assertEnsambla("ld ($f810),hl", [0x22, 0x10, 0xF8])
        self.assertEnsambla("ld hl,($f810)", [0x2A, 0x10, 0xF8])

    def test_aritmetica(self):
        self.assertEnsambla("add a,b", [0x80])
        self.assertEnsambla("add a,$10", [0xC6, 0x10])
        self.assertEnsambla("sub $05", [0xD6, 0x05])
        self.assertEnsambla("and $0f", [0xE6, 0x0F])
        self.assertEnsambla("or a", [0xB7])
        self.assertEnsambla("xor a", [0xAF])
        self.assertEnsambla("cp $30", [0xFE, 0x30])
        self.assertEnsambla("inc hl", [0x23])
        self.assertEnsambla("dec (hl)", [0x35])
        self.assertEnsambla("add hl,de", [0x19])

    def test_saltos_y_llamadas(self):
        self.assertEnsambla("jp $1234", [0xC3, 0x34, 0x12])
        self.assertEnsambla("jp nz,$1234", [0xC2, 0x34, 0x12])
        self.assertEnsambla("call $1234", [0xCD, 0x34, 0x12])
        self.assertEnsambla("ret z", [0xC8])
        self.assertEnsambla("push af", [0xF5])
        self.assertEnsambla("pop hl", [0xE1])
        self.assertEnsambla("bit 1,a", [0xCB, 0x4F])

    def test_saltos_relativos(self):
        codigo, _ = ensamblar("org 0\naqui: nop\n jr aqui\n")
        self.assertEqual(list(codigo), [0x00, 0x18, 0xFD])
        codigo, _ = ensamblar("org 0\n jr z,fin\n nop\nfin: nop\n")
        self.assertEqual(list(codigo), [0x28, 0x01, 0x00, 0x00])

    def test_puertos(self):
        self.assertEnsambla("out ($04),a", [0xD3, 0x04])
        self.assertEnsambla("in a,($00)", [0xDB, 0x00])

    def test_etiquetas_y_datos(self):
        codigo, etiquetas = ensamblar(
            "org 0\n jp datos\ndatos: db 1,2,3\n dw $1234\n")
        self.assertEqual(etiquetas["datos"], 3)
        self.assertEqual(list(codigo), [0xC3, 0x03, 0x00, 1, 2, 3, 0x34, 0x12])

    def test_instruccion_desconocida(self):
        with self.assertRaises(Z80Error) as ctx:
            ensamblar("org 0\n hacer_magia a,b\n")
        self.assertIn("hacer_magia", str(ctx.exception))


class TestDriver(unittest.TestCase):
    """Ejecuta el driver de verdad sobre el emulador."""

    @classmethod
    def setUpClass(cls):
        cls.proyecto = load_project(EJEMPLO)
        cls.orden_musica = list(cls.proyecto.sound.musica)
        cls.rom, cls.info = m1_mod.generar_m1(cls.proyecto.sound, cls.orden_musica)

    def _arrancar(self):
        chip = z80sim.YM2610Falso()
        cpu = z80sim.Z80(self.rom, leer_puerto=chip.leer, escribir_puerto=chip.escribir)
        # dejar que termine la inicializacion (hasta que espere el temporizador)
        for _ in range(4000):
            cpu.paso()
            if cpu.pc == self.info["etiquetas"]["esperar_tick"]:
                break
        else:
            self.fail("el driver no llega a esperar el temporizador")
        return cpu, chip

    def _tick(self, cpu, chip, veces=1):
        """Simula `veces` avisos del temporizador (un frame cada uno)."""
        for _ in range(veces):
            chip.timer_listo = True
            for _ in range(20000):
                cpu.paso()
                if not chip.timer_listo and cpu.pc == self.info["etiquetas"]["esperar_tick"]:
                    break
            else:
                self.fail("el driver se ha quedado colgado en un tick")

    def test_la_rom_tiene_el_tamano_correcto(self):
        self.assertEqual(len(self.rom), m1_mod.M1_SIZE)
        self.assertEqual(self.rom[0], 0xF3)             # empieza con 'di'
        self.assertEqual(self.rom[0x66], 0xF5)          # la NMI empieza con 'push af'

    def test_inicializa_el_chip(self):
        cpu, chip = self._arrancar()
        self.assertEqual(chip.registros.get(0x07), 0b00111000, "mezclador mal puesto")
        self.assertEqual(chip.registros.get(0x08), 0, "el canal A deberia empezar callado")
        self.assertEqual(chip.registros.get(0x26), 140, "temporizador B mal programado")
        self.assertEqual(chip.registros.get(0x27) & 0x0A, 0x0A, "el temporizador no arranca")

    def test_un_efecto_suena_con_su_periodo(self):
        cpu, chip = self._arrancar()
        indice = self.info["efectos"].index("moneda")
        pasos = self.proyecto.sound.efectos["moneda"].pasos
        chip.comando = m1_mod.comando_efecto(indice)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 2)
        # el canal C (registros 4, 5 y 10) debe tener la primera nota
        periodo = chip.registros.get(0x04, 0) | (chip.registros.get(0x05, 0) << 8)
        self.assertEqual(periodo, pasos[0].periodo,
                         "el efecto no suena con el periodo de la primera nota")
        self.assertEqual(chip.registros.get(0x0A), pasos[0].volumen)

    def test_el_efecto_avanza_de_nota(self):
        cpu, chip = self._arrancar()
        indice = self.info["efectos"].index("moneda")
        pasos = self.proyecto.sound.efectos["moneda"].pasos
        chip.comando = m1_mod.comando_efecto(indice)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 1 + pasos[0].duracion + 1)
        periodo = chip.registros.get(0x04, 0) | (chip.registros.get(0x05, 0) << 8)
        self.assertEqual(periodo, pasos[1].periodo, "no ha pasado a la segunda nota")

    def test_el_efecto_se_calla_al_acabar(self):
        cpu, chip = self._arrancar()
        indice = self.info["efectos"].index("moneda")
        total = sum(p.duracion for p in self.proyecto.sound.efectos["moneda"].pasos)
        chip.comando = m1_mod.comando_efecto(indice)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, total + 4)
        self.assertEqual(chip.registros.get(0x0A), 0, "el efecto se queda sonando")

    def test_la_musica_suena_en_dos_canales(self):
        cpu, chip = self._arrancar()
        tema = self.proyecto.sound.musica[self.orden_musica[0]]
        chip.comando = m1_mod.comando_musica(0)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 2)
        periodo_a = chip.registros.get(0x00, 0) | (chip.registros.get(0x01, 0) << 8)
        periodo_b = chip.registros.get(0x02, 0) | (chip.registros.get(0x03, 0) << 8)
        self.assertEqual(periodo_a, tema.pistas[0][0].periodo)
        self.assertEqual(periodo_b, tema.pistas[1][0].periodo)
        self.assertGreater(chip.registros.get(0x08, 0), 0)
        self.assertGreater(chip.registros.get(0x09, 0), 0)

    def test_la_musica_da_la_vuelta(self):
        cpu, chip = self._arrancar()
        tema = self.proyecto.sound.musica[self.orden_musica[0]]
        total = sum(p.duracion for p in tema.pistas[0])
        chip.comando = m1_mod.comando_musica(0)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, total + 2)
        periodo_a = chip.registros.get(0x00, 0) | (chip.registros.get(0x01, 0) << 8)
        self.assertEqual(periodo_a, tema.pistas[0][0].periodo,
                         "la musica deberia volver al principio")

    def test_parar_la_musica(self):
        cpu, chip = self._arrancar()
        chip.comando = m1_mod.comando_musica(0)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 3)
        chip.comando = m1_mod.CMD_MUSIC_STOP | 0x40      # con el bit de alternancia
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 2)
        self.assertEqual(chip.registros.get(0x08), 0)
        self.assertEqual(chip.registros.get(0x09), 0)

    def test_el_mismo_efecto_dos_veces_seguidas(self):
        """El bit de alternancia permite repetir sonido (saltar dos veces)."""
        cpu, chip = self._arrancar()
        indice = self.info["efectos"].index("salto")
        pasos = self.proyecto.sound.efectos["salto"].pasos
        chip.comando = m1_mod.comando_efecto(indice)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 3)
        chip.comando = m1_mod.comando_efecto(indice) | 0x40
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 2)
        periodo = chip.registros.get(0x04, 0) | (chip.registros.get(0x05, 0) << 8)
        self.assertEqual(periodo, pasos[0].periodo,
                         "el segundo disparo deberia reiniciar el efecto")

    def test_el_ruido_usa_el_mezclador(self):
        cpu, chip = self._arrancar()
        indice = self.info["efectos"].index("golpe")
        chip.comando = m1_mod.comando_efecto(indice)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 2)
        self.assertEqual(chip.registros.get(0x07), 0b00011100,
                         "el golpe deberia sonar por el generador de ruido")

    def test_un_comando_fuera_de_rango_no_rompe_nada(self):
        cpu, chip = self._arrancar()
        chip.comando = 0x2F                # efecto que no existe
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 3)           # si se colgara, _tick fallaria


if __name__ == "__main__":
    unittest.main()
