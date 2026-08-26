"""El ensamblador del DSP de la Jaguar, instruccion a instruccion.

Cada palabra son 16 bits: codigo (15-10), primer operando (9-5) y segundo
(4-0). Aqui se comprueban las codificaciones una a una contra los numeros de
operacion documentados, y sobre todo las tres trampas del juego de
instrucciones: `movei` guarda la constante con la palabra baja primero, `shlq`
es el unico inmediato que se guarda como 32-n, y los saltos son relativos a la
instruccion de detras (la de la ranura de retardo).
"""

import unittest

import comun  # noqa: F401  (pone tools/ en el path)
from ngplat.dsp import RAM_DSP, DspError, ensamblar


def palabras(codigo):
    return [(codigo[i] << 8) | codigo[i + 1] for i in range(0, len(codigo), 2)]


class TestCodificacion(unittest.TestCase):
    def _una(self, texto):
        codigo, _ = ensamblar("        " + texto)
        return palabras(codigo)

    def test_registro_a_registro(self):
        # add r5,r7 -> codigo 0, origen 5, destino 7
        self.assertEqual(self._una("add r5,r7"), [(0 << 10) | (5 << 5) | 7])
        self.assertEqual(self._una("move r1,r2"), [(34 << 10) | (1 << 5) | 2])
        self.assertEqual(self._una("xor r31,r0"), [(11 << 10) | (31 << 5) | 0])

    def test_el_32_se_guarda_como_cero(self):
        self.assertEqual(self._una("addq #32,r3"), [(2 << 10) | (0 << 5) | 3])
        self.assertEqual(self._una("addq #1,r3"), [(2 << 10) | (1 << 5) | 3])
        self.assertEqual(self._una("shrq #31,r4"), [(25 << 10) | (31 << 5) | 4])

    def test_shlq_es_la_excepcion(self):
        """La unica instruccion que guarda 32 - n en vez de n."""
        self.assertEqual(self._una("shlq #1,r2"), [(24 << 10) | (31 << 5) | 2])
        self.assertEqual(self._una("shlq #32,r2"), [(24 << 10) | (0 << 5) | 2])

    def test_movei_lleva_la_palabra_baja_delante(self):
        self.assertEqual(self._una("movei #$12345678,r9"),
                         [(38 << 10) | 9, 0x5678, 0x1234])

    def test_load_y_store_se_leen_al_reves(self):
        # load (r3),r4 : el puntero es el primer operando
        self.assertEqual(self._una("load (r3),r4"), [(41 << 10) | (3 << 5) | 4])
        # store r4,(r3) : el puntero sigue siendo el primer operando
        self.assertEqual(self._una("store r4,(r3)"), [(47 << 10) | (3 << 5) | 4])

    def test_la_condicion_va_en_el_segundo_operando(self):
        self.assertEqual(self._una("jump t,(r7)"), [(52 << 10) | (7 << 5) | 0])
        self.assertEqual(self._una("jump ne,(r7)"), [(52 << 10) | (7 << 5) | 1])

    def test_moveq_y_bset(self):
        self.assertEqual(self._una("moveq #17,r2"), [(35 << 10) | (17 << 5) | 2])
        self.assertEqual(self._una("bset #10,r5"), [(14 << 10) | (10 << 5) | 5])

    def test_solo_destino(self):
        self.assertEqual(self._una("neg r6"), [(8 << 10) | 6])
        self.assertEqual(self._una("nop"), [57 << 10])


class TestSaltosYEtiquetas(unittest.TestCase):
    def test_un_bucle_de_una_instruccion(self):
        """`jr` es relativo a la instruccion de detras: volver sobre si mismo
        son -1 palabras."""
        codigo, _ = ensamblar("bucle\n        jr t,bucle\n        nop\n")
        self.assertEqual(palabras(codigo)[0], (53 << 10) | (31 << 5) | 0)

    def test_hacia_delante(self):
        codigo, etq = ensamblar(
            "        jr t,fin\n        nop\n        nop\nfin\n        nop\n")
        # de la instruccion de detras (pc+2) a 'fin' hay dos palabras
        self.assertEqual(palabras(codigo)[0], (53 << 10) | (2 << 5) | 0)
        self.assertEqual(etq["fin"], RAM_DSP + 6)

    def test_las_etiquetas_saben_donde_estan(self):
        codigo, etq = ensamblar("uno\n        nop\ndos\n        nop\n")
        self.assertEqual(etq["uno"], RAM_DSP)
        self.assertEqual(etq["dos"], RAM_DSP + 2)
        self.assertEqual(len(codigo), 4)

    def test_un_salto_demasiado_lejos_da_error(self):
        fuente = "        jr t,lejos\n" + "        nop\n" * 40 + "lejos\n        nop\n"
        with self.assertRaises(DspError):
            ensamblar(fuente)


class TestDirectivas(unittest.TestCase):
    def test_datos_y_reserva(self):
        codigo, _ = ensamblar("        dc.l $11223344\n        ds 4\n")
        self.assertEqual(list(codigo), [0x11, 0x22, 0x33, 0x44, 0, 0, 0, 0])

    def test_alinea(self):
        codigo, etq = ensamblar("        nop\n        alinea 4\naqui\n        nop\n")
        self.assertEqual(etq["aqui"], RAM_DSP + 4)

    def test_lo_que_no_entiende_es_un_error(self):
        for malo in ("mueve r1,r2", "add r1", "moveq #99,r1", "load r3,r4",
                     "jump zzz,(r1)", "shlq #0,r1", "addq #40,r1"):
            with self.assertRaises(DspError, msg=malo):
                ensamblar("        " + malo)


class TestDriver(unittest.TestCase):
    """El driver de verdad, el que acaba en el cartucho."""

    def setUp(self):
        from ngplat import jerry
        self.jerry = jerry
        self.codigo, self.etiquetas = jerry.generar()

    def test_el_manejador_esta_en_el_vector_de_i2s(self):
        """El DSP salta a RAM + 0x10 cuando Jerry pide una muestra."""
        self.assertEqual(self.etiquetas["manejador"], RAM_DSP + 0x10)

    def test_cabe_en_la_ram_del_dsp(self):
        self.assertLess(len(self.codigo), 8 * 1024)
        self.assertEqual(len(self.codigo) % 4, 0, "tiene que caber en longs")

    def test_el_bloque_de_parametros_esta_alineado(self):
        self.assertEqual(self.etiquetas["parametros"] % 4, 0)
        self.assertGreater(self.etiquetas["pila"], self.etiquetas["parametros"])

    def test_las_notas_salen_donde_tienen_que_salir(self):
        """El paso de fase se guarda en 16 bits; lo que se pierde al redondear
        tiene que quedar muy por debajo de un semitono (un 6%)."""
        for hz in (65.41, 130.81, 261.63, 440.0, 1046.5, 2093.0, 3520.0):
            vuelta = self.jerry.frecuencia_de_paso(self.jerry.paso_de_frecuencia(hz))
            self.assertLess(abs(vuelta - hz) / hz, 0.002,
                            "%.2f Hz se convierte en %.2f" % (hz, vuelta))


if __name__ == "__main__":
    unittest.main()
