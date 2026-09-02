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
        # Un efecto de notas y uno de muestra, elegidos por lo que son y no por
        # su nombre: el ejemplo puede cambiar de banda sonora y estas pruebas
        # tienen que seguir mirando lo que miran.
        efectos = cls.proyecto.sound.efectos
        cls.de_notas = next(n for n in cls.info["efectos"]
                            if efectos[n].pasos and not efectos[n].digital)
        cls.de_muestra = next((n for n in cls.info["efectos"] if efectos[n].digital),
                              "")

    def _pasos(self, nombre):
        return self.proyecto.sound.efectos[nombre].pasos

    def _arrancar(self, rom=None, info=None):
        rom = self.rom if rom is None else rom
        info = self.info if info is None else info
        chip = z80sim.YM2610Falso()
        cpu = z80sim.Z80(rom, leer_puerto=chip.leer, escribir_puerto=chip.escribir)
        # dejar que termine la inicializacion (hasta que espere el temporizador)
        for _ in range(4000):
            cpu.paso()
            if cpu.pc == info["etiquetas"]["esperar_tick"]:
                break
        else:
            self.fail("el driver no llega a esperar el temporizador")
        return cpu, chip

    def _tick(self, cpu, chip, veces=1, info=None):
        """Simula `veces` avisos del temporizador (un frame cada uno)."""
        info = self.info if info is None else info
        for _ in range(veces):
            chip.timer_listo = True
            for _ in range(20000):
                cpu.paso()
                if not chip.timer_listo and cpu.pc == info["etiquetas"]["esperar_tick"]:
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
        indice = self.info["efectos"].index(self.de_notas)
        pasos = self._pasos(self.de_notas)
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
        indice = self.info["efectos"].index(self.de_notas)
        pasos = self._pasos(self.de_notas)
        chip.comando = m1_mod.comando_efecto(indice)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 1 + pasos[0].duracion + 1)
        periodo = chip.registros.get(0x04, 0) | (chip.registros.get(0x05, 0) << 8)
        self.assertEqual(periodo, pasos[1].periodo, "no ha pasado a la segunda nota")

    def test_el_efecto_se_calla_al_acabar(self):
        cpu, chip = self._arrancar()
        indice = self.info["efectos"].index(self.de_notas)
        total = sum(p.duracion for p in self._pasos(self.de_notas))
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
        indice = self.info["efectos"].index(self.de_notas)
        pasos = self._pasos(self.de_notas)
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
        """Con su propio proyecto, para no depender de como suene el ejemplo:
        un unico efecto y de ruido."""
        sonido = sonido_mod.Sonido()
        sonido.efectos["golpe"] = sonido_mod.Efecto(
            nombre="golpe", pasos=sonido_mod.ruido(8, 12))
        rom, info = m1_mod.generar_m1(sonido, [])
        cpu, chip = self._arrancar(rom, info)
        chip.comando = m1_mod.comando_efecto(0)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 2, info)
        self.assertEqual(chip.registros.get(0x07), 0b00011100,
                         "el golpe deberia sonar por el generador de ruido")

    # --- muestras digitales (ADPCM-A) --------------------------------------

    def test_una_muestra_arranca_el_adpcm(self):
        """Un efecto con WAV no suena por el SSG: el driver le da al YM2610 los
        limites en la ROM V1 y le dice que arranque el canal 0."""
        if not self.de_muestra:
            self.skipTest("el ejemplo no trae ningun efecto con muestra")
        cpu, chip = self._arrancar()
        indice = self.info["efectos"].index(self.de_muestra)
        chip.comando = m1_mod.comando_efecto(indice)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 2)
        reg = chip.registros_b
        self.assertEqual(reg.get(0x00), 0x01, "no ha arrancado el canal 0")
        self.assertEqual(reg.get(0x01), 0x3F, "el volumen general no esta a tope")
        self.assertEqual(reg.get(0x08), 0xDF,
                         "el canal 0 no suena por los dos altavoces y a tope")
        primero = (reg.get(0x18, 0) << 8) | reg.get(0x10, 0)
        ultimo = (reg.get(0x28, 0) << 8) | reg.get(0x20, 0)
        esperado = self.info["muestras"][indice]
        self.assertEqual((primero, ultimo), esperado,
                         "los limites no son los de la tabla de muestras")
        self.assertGreater(primero, 0,
                           "una muestra no puede empezar en el bloque 0: es el "
                           "que marca 'este efecto no tiene muestra'")
        # y el canal C del SSG se queda como estaba: no suena dos veces
        self.assertFalse(chip.registros.get(0x0A),
                         "el efecto tambien esta sonando por el SSG")

    def test_la_muestra_de_la_v1_no_es_silencio(self):
        """Las direcciones tienen que apuntar al sonido de verdad, no a la
        parte vacia de la ROM."""
        if not self.de_muestra:
            self.skipTest("el ejemplo no trae ningun efecto con muestra")
        from ngplat import adpcm
        indice = self.info["efectos"].index(self.de_muestra)
        primero, ultimo = self.info["muestras"][indice]
        trozo = self.info["v1"][primero * adpcm.BLOQUE:
                                (ultimo + 1) * adpcm.BLOQUE]
        self.assertTrue(trozo, "la muestra cae fuera de la ROM V1")
        onda = adpcm.descifrar(trozo)
        self.assertGreater(max(abs(v) for v in onda), 200,
                           "lo que hay en la V1 no suena")

    def test_un_efecto_sin_muestra_no_toca_el_adpcm(self):
        cpu, chip = self._arrancar()
        indice = self.info["efectos"].index(self.de_notas)
        chip.comando = m1_mod.comando_efecto(indice)
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 2)
        self.assertEqual(chip.escrituras_b, [],
                         "un efecto de notas no deberia tocar los ADPCM-A")

    def test_un_comando_fuera_de_rango_no_rompe_nada(self):
        cpu, chip = self._arrancar()
        chip.comando = 0x2F                # efecto que no existe
        cpu.nmi_pendiente = True
        self._tick(cpu, chip, 3)           # si se colgara, _tick fallaria


class TestQueCancionToca(unittest.TestCase):
    """`np_music_now` decide que suena en cada momento, y las seis maquinas le
    hacen caso. Se compila el motor de verdad con un proyecto que trae musica
    de titulo y de jefe, y se mira lo que dice en cada estado."""

    @classmethod
    def setUpClass(cls):
        import shutil, subprocess, tempfile
        from ngplat.codegen import copy_engine, generate_gamedata
        from ngplat.scaffold import crear_proyecto
        if not shutil.which("gcc"):
            raise unittest.SkipTest("no hay gcc para compilar el motor")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-musica-")
        proyecto = os.path.join(cls.tmp, "juego")
        crear_proyecto(proyecto, "MUSICA", "TEST", genero="castlevania")
        cls.proyecto = load_project(proyecto)
        from comun import cargar_demo
        build = cargar_demo(proyecto)
        salida = os.path.join(cls.tmp, "build")
        os.makedirs(os.path.join(salida, "src"))
        for relativo, contenido in generate_gamedata(build).items():
            with open(os.path.join(salida, relativo), "w", encoding="utf-8") as fh:
                fh.write(contenido)
        copy_engine(salida)
        binario = os.path.join(cls.tmp, "np_musica")
        hecho = subprocess.run(
            ["gcc", "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
             "-I", os.path.join(salida, "src"), "-o", binario,
             os.path.join(KIT, "engine", "host", "np_musica.c"),
             os.path.join(salida, "src", "np_world.c"),
             os.path.join(salida, "src", "gamedata.c")],
            capture_output=True, text=True)
        if hecho.returncode:
            raise AssertionError("no compila:\n" + hecho.stderr)
        salida_texto = subprocess.run([binario], capture_output=True, text=True,
                                      check=True).stdout
        # cada linea es "<momento> <numero de cancion>"
        cls.crudo = dict((l[:l.rindex(" ")], int(l[l.rindex(" ") + 1:]))
                         for l in salida_texto.strip().split("\n"))
        cls.orden = list(cls.proyecto.sound.musica)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def _cancion(self, clave):
        """El nombre de la cancion que dice el motor (o None si silencio)."""
        numero = self.crudo[clave]
        return self.orden[numero - 1] if numero else None

    def test_la_tabla_lleva_las_dos_canciones(self):
        """Si el compilador no las emitiera, todo lo demas pasaria en vacio."""
        self.assertEqual(self.orden[self.crudo["tabla titulo"] - 1],
                         self.proyecto.sound.titulo)
        self.assertEqual(self.orden[self.crudo["tabla jefe"] - 1],
                         self.proyecto.sound.jefe)

    def test_el_titulo_tiene_la_suya(self):
        """Antes no sonaba nada hasta que empezabas a jugar."""
        self.assertEqual(self._cancion("titulo"), self.proyecto.sound.titulo)

    def test_jugando_suena_la_del_nivel(self):
        self.assertEqual(self._cancion("nivel"), self.proyecto.levels[0].music)

    def test_con_el_jefe_delante_manda_la_suya(self):
        """Es el momento en el que la musica tiene mas que decir."""
        self.assertEqual(self._cancion("jefe"), self.proyecto.sound.jefe)
        self.assertNotEqual(self.proyecto.sound.jefe, self.proyecto.levels[0].music)

    def test_muerto_el_jefe_vuelve_la_del_nivel(self):
        self.assertEqual(self._cancion("sin jefe"), self.proyecto.levels[0].music)

    def test_fuera_de_la_partida_no_suena_nada(self):
        """El 'game over' y el fin de nivel se quedan en silencio, como estaban:
        ahi lo que suena es el efecto."""
        self.assertIsNone(self._cancion("game over"))
        self.assertIsNone(self._cancion("fin de nivel"))


if __name__ == "__main__":
    unittest.main()
