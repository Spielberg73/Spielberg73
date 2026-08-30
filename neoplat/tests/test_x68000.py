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
from ngplat.x68k_disk import (ErrorDisco, crear_disquete, insertar_archivo,
                              leer_archivo, leer_bpb, leer_directorio,
                              reemplazar_archivo)

from ngplat.art import PALETA as PALETA_BOSQUE
from ngplat.art_hierro import PALETA as PALETA_HIERRO
from ngplat.gfx_x68k import (PATRON_BYTES, codificar_patron, decodificar_patron,
                             x68k_color, x68k_color_a_rgb)
from ngplat.sonido import codigo_ym2151, frecuencia_de_nota, frecuencia_ym2151
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

    def test_los_cuadrantes_van_por_columnas(self):
        """Arriba-izquierda, abajo-izquierda, arriba-derecha, abajo-derecha: por
        columnas, no en orden de lectura.

        Esta medido en el emulador -un patron con los cuatro trozos de 32 bytes
        de cuatro colores, a ver donde caia cada uno- despues de que los
        dibujos salieran partidos con el orden de lectura, que es lo que se
        supuso al principio. Aqui queda fijado el contrato."""
        for indice, (x, y) in enumerate(((0, 0), (0, 8), (8, 0), (8, 8))):
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


class TestNotasDelYM2151(unittest.TestCase):
    """El key code del YM2151, que no es un periodo sino una nota.

    Los valores de anclaje estan **medidos dentro del juego**: el driver
    escribe en el marcador, bit a bit, el codigo que le manda al chip, y se
    empareja cada codigo con la frecuencia que sale por el altavoz. Es la unica
    medida que resulto fiable; midiendo notas sueltas o por tramos salieron
    tres tablas distintas, todas mal.
    """

    ANCLAS = {"do#5": ((1, 5), 0x4D), "mi5": ((4, 5), 0x51),
              "fa#5": ((6, 5), 0x54), "sol#5": ((8, 5), 0x56),
              "do#6": ((1, 6), 0x5D)}

    def test_las_notas_medidas_en_el_emulador(self):
        for nombre, ((semitono, octava), kc) in self.ANCLAS.items():
            hz = frecuencia_de_nota(semitono, octava)
            self.assertEqual(codigo_ym2151(hz) >> 8, kc,
                             "%s tendria que ser el key code $%02X" % (nombre, kc))

    def test_media_octava_se_lleva_al_bloque_siguiente(self):
        """Del re# para arriba, las notas caen ya en el bloque de la octava
        siguiente: el do5 es $4C y el re#5 es $50, no $4F, que no existe."""
        self.assertEqual(codigo_ym2151(frecuencia_de_nota(0, 5)) >> 8, 0x4C)
        self.assertEqual(codigo_ym2151(frecuencia_de_nota(3, 5)) >> 8, 0x50)

    def test_una_octava_es_justo_el_doble(self):
        for semitono in range(12):
            abajo = codigo_ym2151(frecuencia_de_nota(semitono, 3))
            arriba = codigo_ym2151(frecuencia_de_nota(semitono, 4))
            self.assertEqual((arriba >> 8) - (abajo >> 8), 0x10,
                             "la octava son 16 en el key code")

    def test_ida_y_vuelta(self):
        for octava in range(2, 7):
            for semitono in range(12):
                hz = frecuencia_de_nota(semitono, octava)
                vuelta = frecuencia_ym2151(codigo_ym2151(hz))
                self.assertLess(abs(vuelta - hz) / hz, 0.001,
                                "%.2f Hz vuelve como %.2f" % (hz, vuelta))

    def test_los_codigos_que_no_existen_no_se_usan(self):
        """De cada cuatro codigos de nota, uno no vale (el 3, el 7, el 11 y el
        15): el chip lo toma como el anterior."""
        for octava in range(2, 7):
            for semitono in range(12):
                nota = codigo_ym2151(frecuencia_de_nota(semitono, octava)) >> 8
                self.assertNotIn(nota & 0x0F, (3, 7, 11, 15))

    def test_el_silencio_no_tiene_nota(self):
        self.assertEqual(codigo_ym2151(0), 0)


class TestDisquete(unittest.TestCase):
    """El disquete de Human68k: un FAT12 con sectores de 1024 bytes.

    Sin un X68000 delante, la unica forma de saber que esta bien montado es
    releerlo siguiendo la FAT como haria el sistema, que es lo que se hace
    aqui.
    """

    def test_mide_lo_que_mide_un_2hd_japones(self):
        disco = crear_disquete({"JUEGO.X": b"hola"})
        self.assertEqual(len(disco), 77 * 2 * 8 * 1024)

    def test_el_bpb_va_donde_va_y_en_big_endian(self):
        """Lo que distingue el sector de arranque del X68000 del de un PC: el
        nombre del fabricante ocupa 16 bytes y el BPB va en 0x12 y en big
        endian. Comprobado contra un disco de sistema de Sharp de verdad; la
        primera version lo escribia en 0x0B y en little endian, que es como lo
        **finge** una herramienta para poder leerlo con una libreria de PC."""
        disco = crear_disquete({"JUEGO.X": b"hola"})
        self.assertEqual(struct.unpack(">H", disco[0:2])[0], 0x601C,
                         "el salto al codigo de arranque no esta")
        self.assertEqual(len(disco[2:18]), 16)
        bpb = leer_bpb(disco)
        self.assertEqual(bpb["sector"], 1024,
                         "los sectores de esta maquina son de 1024 bytes")
        self.assertEqual(bpb["por_agrupacion"], 1)
        self.assertEqual(bpb["fats"], 2)
        self.assertEqual(bpb["reservados"], 1)
        self.assertEqual(bpb["raiz"], 192)
        self.assertEqual(bpb["sectores"], 1232)
        self.assertEqual(bpb["medio"], 0xFE)
        self.assertEqual(bpb["sectores_fat"], 2)

    def test_el_bpb_no_esta_donde_lo_pondria_un_pc(self):
        """Y que no vuelva el fallo de antes: en 0x0B y little endian no hay un
        BPB, hay parte del nombre del fabricante."""
        disco = crear_disquete({"JUEGO.X": b"hola"})
        self.assertNotEqual(struct.unpack("<H", disco[11:13])[0], 1024)

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

    def test_un_archivo_anadido_despues_se_lee(self):
        """Anadir sin remontar: es lo que hace falta para meter el juego en un
        disco de sistema de Human68k que ya existe."""
        disco = crear_disquete({"UNO.TXT": b"A" * 4000})
        disco = insertar_archivo(disco, "JUEGO.X", b"B" * 9000)
        self.assertEqual(leer_archivo(disco, "JUEGO.X"), b"B" * 9000)
        self.assertEqual(leer_archivo(disco, "UNO.TXT"), b"A" * 4000,
                         "el archivo que ya estaba se ha pisado")
        self.assertEqual(len(disco), 77 * 2 * 8 * 1024)

    def test_anadir_no_reparte_agrupaciones_ya_ocupadas(self):
        """Diez archivos seguidos, cada uno de varias agrupaciones: si la busca
        de sitio libre mirase mal la FAT, alguno saldria con datos de otro."""
        disco = crear_disquete({"BASE.TXT": b"base"})
        esperado = {}
        for i in range(10):
            nombre = "F%d.DAT" % i
            esperado[nombre] = bytes([65 + i]) * (3000 + i * 700)
            disco = insertar_archivo(disco, nombre, esperado[nombre])
        for nombre, datos in esperado.items():
            self.assertEqual(leer_archivo(disco, nombre), datos, nombre)

    def test_anadir_lo_que_no_cabe_avisa(self):
        disco = crear_disquete({"UNO.TXT": b"A"})
        with self.assertRaises(ErrorDisco):
            insertar_archivo(disco, "ENORME.X", b"\0" * (2 * 1024 * 1024))

    def test_cambiar_el_contenido_de_un_archivo(self):
        """Lo que se hace con el AUTOEXEC.BAT del disco de sistema."""
        disco = crear_disquete({"AUTOEXEC.BAT": b"echo lo de antes\r\n",
                                "OTRO.TXT": b"no se toca"})
        disco = reemplazar_archivo(disco, "AUTOEXEC.BAT", b"A:\\X2.X\r\n")
        self.assertEqual(leer_archivo(disco, "AUTOEXEC.BAT"), b"A:\\X2.X\r\n")
        self.assertEqual(leer_archivo(disco, "OTRO.TXT"), b"no se toca")

    def test_cambiarlo_por_algo_mas_largo_de_lo_que_ocupaba_avisa(self):
        disco = crear_disquete({"CORTO.TXT": b"x"})
        with self.assertRaises(ErrorDisco):
            reemplazar_archivo(disco, "CORTO.TXT", b"y" * 5000)

    def test_cambiar_uno_que_no_esta_avisa(self):
        disco = crear_disquete({"UNO.TXT": b"x"})
        with self.assertRaises(ErrorDisco):
            reemplazar_archivo(disco, "NOESTA.TXT", b"y")

    def test_un_nombre_que_no_cabe_no_cuela(self):
        with self.assertRaises(ErrorDisco):
            crear_disquete({"NOMBREDEMASIADOLARGO.X": b"x"})

    def test_lo_que_no_cabe_en_el_disquete_avisa(self):
        with self.assertRaises(ErrorDisco):
            crear_disquete({"ENORME.X": b"\0" * (2 * 1024 * 1024)})


class TestDiscoDeSharp(unittest.TestCase):
    """Leer un disco de sistema de Human68k de verdad.

    Es la unica prueba que dice que el formato esta bien de verdad y no solo
    que somos consistentes con nosotros mismos. El disco no viene en el
    repositorio (es software de Sharp): se busca en NEOPLAT_HUMAN68K y, si no
    esta, la prueba se salta, igual que hace la del Atari ST con el TOS.
    """

    @classmethod
    def setUpClass(cls):
        ruta = os.environ.get("NEOPLAT_HUMAN68K", "")
        if not ruta or not os.path.isfile(ruta):
            raise unittest.SkipTest("no hay un disco de Human68k "
                                    "(pon NEOPLAT_HUMAN68K)")
        with open(ruta, "rb") as fh:
            cls.disco = fh.read()

    def test_el_bpb_del_disco_de_sharp_se_lee(self):
        bpb = leer_bpb(self.disco)
        self.assertEqual(bpb["sector"], 1024)
        self.assertEqual(bpb["sectores"], 1232)
        self.assertEqual(bpb["fats"], 2)

    def test_se_ven_los_archivos_del_sistema(self):
        nombres = {n.upper() for n, _, _ in leer_directorio(self.disco)}
        self.assertIn("HUMAN.SYS", nombres)
        self.assertIn("COMMAND.X", nombres)

    def test_human_sys_es_un_ejecutable_x(self):
        """Y de paso comprueba el otro formato: HUMAN.SYS es un .X, asi que si
        nuestra idea de la cabecera fuera mala, aqui se veria."""
        datos = leer_archivo(self.disco, "HUMAN.SYS")
        self.assertEqual(datos[:4], b"HU\0\0")
        (base, entrada, texto, seccion, bss, reloc,
         simbolos) = struct.unpack(">7I", datos[4:32])
        self.assertEqual(len(datos), 64 + texto + seccion + reloc + simbolos,
                         "los tamanos de la cabecera no suman el archivo")

    def test_el_juego_entra_en_el_disco_de_sistema(self):
        """El disco de arranque que se usa en el emulador: el sistema de Sharp
        tal cual, con nuestro .X dentro y el AUTOEXEC.BAT llamandolo. Si esto
        pasa, el disco que le damos a px68k esta bien montado."""
        humano = leer_archivo(self.disco, "HUMAN.SYS")
        juego = b"HU\0\0" + bytes((i * 13) % 251 for i in range(20000))
        disco = insertar_archivo(self.disco, "X2.X", juego)
        disco = reemplazar_archivo(disco, "AUTOEXEC.BAT", b"A:\\X2.X\r\n")
        self.assertEqual(leer_archivo(disco, "X2.X"), juego)
        self.assertEqual(leer_archivo(disco, "AUTOEXEC.BAT"), b"A:\\X2.X\r\n")
        self.assertEqual(leer_archivo(disco, "HUMAN.SYS"), humano,
                         "el sistema de Sharp no puede quedar tocado")
        self.assertEqual(len(disco), len(self.disco))


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
