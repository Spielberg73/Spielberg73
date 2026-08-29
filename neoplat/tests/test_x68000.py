"""Las piezas del X68000 que no necesitan la maquina: color, PCG y ejecutable.

El motor en C se comprueba compilandolo (test_sistemas) y en el emulador
(tests/emulador_x68000.py, que necesita las ROMs de Sharp). Lo de aqui es lo
que se puede mirar en seco.
"""

import os
import shutil
import struct
import subprocess
import tempfile
import unittest

import comun  # noqa: F401  (pone tools/ en el path)
from comun import cargar_demo

from ngplat import sistemas
from ngplat.codegen import generar_para_sistema
from ngplat.scaffold import crear_proyecto
from ngplat.x68k_disk import (ErrorDisco, crear_disquete, leer_archivo,
                              leer_directorio)

from ngplat.art import PALETA as PALETA_BOSQUE
from ngplat.art_hierro import PALETA as PALETA_HIERRO
from ngplat.gfx_x68k import (PATRON_BYTES, codificar_patron, decodificar_patron,
                             x68k_color, x68k_color_a_rgb)
from ngplat.x68k import ErrorX, tabla_de_correcciones


class TestColor(unittest.TestCase):
    """El color del X68000 es GRBi: cinco bits por canal y un bit de intensidad
    que es el LSB **de los tres a la vez**."""

    def test_el_negro_y_el_blanco_salen_exactos(self):
        self.assertEqual(x68k_color((0, 0, 0)), 0x0000)
        self.assertEqual(x68k_color_a_rgb(x68k_color((255, 255, 255))),
                         (255, 255, 255))

    def test_cada_canal_va_en_su_sitio(self):
        """Si se cambiaran de sitio el verde y el rojo, el juego saldria con los
        colores permutados y todo lo demas seguiria funcionando."""
        self.assertEqual(x68k_color((255, 0, 0)) & 0xF800, 0)     # nada en verde
        self.assertEqual(x68k_color((0, 255, 0)) & 0x07C0, 0)     # nada en rojo
        self.assertEqual(x68k_color((0, 0, 255)) & 0xF800, 0)
        rojo = x68k_color_a_rgb(x68k_color((255, 0, 0)))
        self.assertGreater(rojo[0], 240)
        self.assertEqual(rojo[1:], (0, 0))

    def test_las_paletas_del_kit_sobreviven(self):
        """Cinco bits por canal no dan los 256 niveles, asi que algo se pierde:
        lo que se comprueba es **cuanto**. Cuatro de 255 no se ve; si un cambio
        lo empeorara, aqui se nota."""
        peor = 0
        for paleta in (PALETA_BOSQUE, PALETA_HIERRO):
            for nombre, rgb in paleta.items():
                vuelta = x68k_color_a_rgb(x68k_color(rgb[:3]))
                error = max(abs(a - b) for a, b in zip(vuelta, rgb[:3]))
                self.assertLessEqual(error, 4, "%s: %s -> %s" % (nombre, rgb[:3], vuelta))
                peor = max(peor, error)
        self.assertGreater(peor, 0, "no se pierde nada: la prueba no vale")

    def test_el_bit_de_intensidad_se_usa(self):
        """Es lo unico raro de este formato: si se ignorara, los colores claros
        saldrian medio nivel por debajo y el blanco no seria blanco."""
        self.assertEqual(x68k_color((255, 255, 255)) & 1, 1)


class TestPatrones(unittest.TestCase):
    """Un patron de PCG son 16x16 pixeles en 128 bytes: cuatro cuadrantes de
    8x8 en orden de lectura, dos pixeles por byte."""

    def _damero(self):
        return [(x + y * 16) % 16 for y in range(16) for x in range(16)]

    def test_mide_lo_que_tiene_que_medir(self):
        self.assertEqual(len(codificar_patron(self._damero())), PATRON_BYTES)

    def test_ida_y_vuelta(self):
        px = self._damero()
        self.assertEqual(decodificar_patron(codificar_patron(px)), px)

    def test_el_nibble_alto_es_el_pixel_de_la_izquierda(self):
        px = [0] * 256
        px[0] = 0xA           # (0,0)
        px[1] = 0x5           # (1,0)
        self.assertEqual(codificar_patron(px)[0], 0xA5)

    def test_los_cuadrantes_van_en_orden_de_lectura(self):
        """Arriba-izquierda, arriba-derecha, abajo-izquierda, abajo-derecha. Con
        otro orden los sprites saldrian troceados, y eso solo se ve en el
        emulador: aqui se fija el contrato."""
        for indice, (x, y) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
            px = [0] * 256
            px[y * 16 + x] = 0xF
            datos = codificar_patron(px)
            self.assertEqual(datos[indice * 32], 0xF0,
                             "el cuadrante %d no esta donde toca" % indice)

    def test_un_patron_que_no_es_de_16x16_no_cuela(self):
        with self.assertRaises(ValueError):
            codificar_patron([0] * 100)


class TestEjecutable(unittest.TestCase):
    """La tabla de correcciones del .X va por saltos desde la anterior, y un
    salto que no cabe en una palabra se anuncia con un 1."""

    def test_sin_correcciones_no_hay_tabla(self):
        self.assertEqual(tabla_de_correcciones([]), b"")

    def test_los_saltos_son_desde_la_anterior(self):
        tabla = tabla_de_correcciones([4, 10, 20])
        self.assertEqual(tabla, struct.pack(">3H", 4, 6, 10))

    def test_un_salto_largo_se_anuncia_con_un_uno(self):
        tabla = tabla_de_correcciones([4, 0x20000])
        self.assertEqual(tabla, struct.pack(">H", 4) + struct.pack(">HI", 1, 0x20000 - 4))

    def test_van_ordenadas_aunque_lleguen_revueltas(self):
        self.assertEqual(tabla_de_correcciones([20, 4, 10]),
                         tabla_de_correcciones([4, 10, 20]))

    def test_una_correccion_impar_no_cuela(self):
        """El 68000 no puede leer una palabra larga en una direccion impar: si
        se colara, la maquina se para con un error de direccion."""
        with self.assertRaises(ErrorX):
            tabla_de_correcciones([4, 7])


class TestDisquete(unittest.TestCase):
    """El disquete de Human68k: un FAT12 con sectores de 1024 bytes.

    Sin un X68000 delante, la unica forma de saber que esta bien montado es
    releerlo siguiendo la FAT como haria el sistema, que es lo que se hace
    aqui.
    """

    def test_mide_lo_que_mide_un_2hd_japones(self):
        disco = crear_disquete({"JUEGO.X": b"hola"})
        self.assertEqual(len(disco), 77 * 2 * 8 * 1024)

    def test_lleva_la_firma_y_el_bpb(self):
        """La firma en el nombre del fabricante y el BPB son lo que distingue un
        disquete del X68000 de uno de PC: si se pierden, no lo lee nadie."""
        disco = crear_disquete({"JUEGO.X": b"hola"})
        self.assertEqual(disco[0:3], b"\x60\x3c\x90", "falta el salto")
        self.assertEqual(disco[3:11], b"X68IPL30")
        self.assertEqual(struct.unpack("<H", disco[11:13])[0], 1024,
                         "los sectores de esta maquina son de 1024 bytes")
        self.assertEqual(disco[13], 1)          # un sector por agrupacion
        self.assertEqual(disco[16], 2)          # dos FAT
        self.assertEqual(struct.unpack("<H", disco[17:19])[0], 192)
        self.assertEqual(struct.unpack("<H", disco[19:21])[0], 1232)
        self.assertEqual(disco[21], 0xFE)
        self.assertEqual(struct.unpack("<H", disco[24:26])[0], 8)
        self.assertEqual(struct.unpack("<H", disco[26:28])[0], 2)

    def test_un_archivo_vuelve_igual(self):
        datos = bytes(range(256)) * 3
        disco = crear_disquete({"JUEGO.X": datos})
        self.assertEqual(leer_archivo(disco, "JUEGO.X"), datos)

    def test_uno_grande_encadena_agrupaciones(self):
        """Mas de un sector quiere decir mas de una agrupacion, y ahi es donde
        se rompe una FAT mal escrita: si la cadena no se sigue, vuelve cortado
        o con basura de otro archivo."""
        datos = bytes((i * 7) % 251 for i in range(50 * 1024))
        disco = crear_disquete({"GRANDE.X": datos})
        self.assertGreater(len(datos), 1024, "la prueba no encadena nada")
        self.assertEqual(leer_archivo(disco, "GRANDE.X"), datos)

    def test_dos_archivos_no_se_pisan(self):
        uno = b"A" * 5000
        dos = b"B" * 3000
        disco = crear_disquete({"UNO.X": uno, "DOS.TXT": dos})
        self.assertEqual(leer_archivo(disco, "UNO.X"), uno)
        self.assertEqual(leer_archivo(disco, "DOS.TXT"), dos)
        nombres = [n for n, _, _ in leer_directorio(disco)]
        self.assertEqual(sorted(nombres), ["DOS.TXT", "UNO.X"])

    def test_un_nombre_que_no_cabe_no_cuela(self):
        with self.assertRaises(ErrorDisco):
            crear_disquete({"NOMBREDEMASIADOLARGO.X": b"x"})

    def test_lo_que_no_cabe_en_el_disquete_avisa(self):
        with self.assertRaises(ErrorDisco):
            crear_disquete({"ENORME.X": b"\0" * (2 * 1024 * 1024)})


class TestCompilaDeVerdad(unittest.TestCase):
    """Que el proyecto de X68000 se construya entero con el cross-compilador y
    salga un .X que Human68k pueda cargar."""

    @classmethod
    def setUpClass(cls):
        cls.cc = ""
        for nombre in ("m68k-elf-gcc", "m68k-linux-gnu-gcc"):
            if shutil.which(nombre):
                cls.cc = nombre
                break
        if not cls.cc:
            raise unittest.SkipTest("no hay un compilador de 68000")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-x68k-")
        proyecto = os.path.join(cls.tmp, "juego")
        crear_proyecto(proyecto, "X68K", "TEST")
        build = cargar_demo(proyecto, "x68000")
        sistema = sistemas.obtener("x68000")
        sistema.comprobar(build)
        cls.salida = os.path.join(cls.tmp, "build")
        generar_para_sistema(build, cls.salida, sistema, "202")
        hecho = subprocess.run(["make", "-C", cls.salida],
                               capture_output=True, text=True)
        if hecho.returncode:
            raise AssertionError("no compila:\n" + hecho.stdout + hecho.stderr)
        cls.build = build

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "tmp", ""), ignore_errors=True)

    def _ejecutable(self):
        disco = os.path.join(self.salida, "disco")
        nombres = [n for n in os.listdir(disco) if n.endswith(".X")]
        self.assertEqual(len(nombres), 1, nombres)
        with open(os.path.join(disco, nombres[0]), "rb") as fh:
            return fh.read()

    def test_la_cabecera_del_x_cuadra(self):
        datos = self._ejecutable()
        self.assertEqual(datos[:4], b"HU\0\0")
        (base, entrada, texto, seccion_datos, bss, reloc,
         simbolos) = struct.unpack(">7I", datos[4:32])
        self.assertEqual(datos[32:64], b"\0" * 32, "el relleno no esta a cero")
        self.assertEqual(len(datos), 64 + texto + reloc,
                         "los tamanos de la cabecera no suman el archivo")
        self.assertEqual(entrada, 0, "no se entra por el principio")
        self.assertEqual(seccion_datos, 0, "los datos van dentro de TEXT")
        self.assertGreater(texto, 1024)
        self.assertGreater(bss, 0)
        self.assertGreater(reloc, 0, "sin correcciones el juego no se puede "
                                     "montar en cualquier direccion")
        self.assertEqual(simbolos, 0)

    def test_se_entra_por_el_arranque(self):
        """La primera instruccion tiene que ser la que limpia la BSS, y con
        direccionamiento absoluto: relativo al PC se queda corto en cuanto el
        juego pasa de 32 KB, que es enseguida."""
        datos = self._ejecutable()
        self.assertEqual(datos[64:66], b"\x20\x7c",
                         "la primera instruccion no es 'move.l #x, a0'")

    def test_los_graficos_caben_en_la_pcg(self):
        banco = self.build.info["banco"]
        self.assertLessEqual(banco.cuantos, 256)
        self.assertGreater(banco.cuantos, 16, "no se ha empaquetado casi nada")
        self.assertLessEqual(len(banco.paletas), 16)

    def test_el_juego_esta_dentro_del_ejecutable(self):
        """Si los graficos no entraran, el .X saldria enano y el juego no se
        veria. Se mira un trozo del **final** de los patrones, no del
        principio: mirando solo el principio, un empaquetado que se dejara la
        mitad por el camino pasaria igual."""
        datos = self._ejecutable()
        pcg = self.build.info["banco"].datos()
        self.assertIn(pcg[:64], datos,
                      "los patrones de la PCG no estan en el ejecutable")
        self.assertIn(pcg[-64:], datos,
                      "los patrones estan cortados: falta el final")
        self.assertIn(pcg[len(pcg) // 2:len(pcg) // 2 + 64], datos,
                      "los patrones estan cortados por la mitad")


    def test_el_juego_vuelve_entero_del_disquete(self):
        """El .X que monta el make tiene que salir del .xdf byte a byte: es lo
        que va a leer Human68k."""
        disco_dir = os.path.join(self.salida, "disco")
        xdf = [n for n in os.listdir(disco_dir) if n.endswith(".xdf")]
        self.assertEqual(len(xdf), 1, xdf)
        with open(os.path.join(disco_dir, xdf[0]), "rb") as fh:
            imagen = fh.read()
        dentro = leer_directorio(imagen)
        self.assertEqual(len(dentro), 1, dentro)
        nombre = dentro[0][0]
        self.assertEqual(leer_archivo(imagen, nombre), self._ejecutable(),
                         "el ejecutable no sale igual del disquete")


if __name__ == "__main__":
    unittest.main()
