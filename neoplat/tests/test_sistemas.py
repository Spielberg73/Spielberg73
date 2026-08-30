"""Las cinco maquinas: conversion de graficos, generacion y compilacion real.

Lo que se comprueba aqui es que el mismo juego sale bien para Neo Geo, Mega
Drive, Amiga, Jaguar y Atari ST: los graficos se convierten sin perder
informacion, el proyecto generado trae lo que tiene que traer y, si hay un
compilador de 68000 a mano, el cartucho y el ejecutable se construyen de verdad
y tienen la pinta que espera cada maquina.
"""

import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

import comun
from comun import KIT, cargar_demo

from ngplat import adf, gfx, gfx_amiga, gfx_md, hunk, prg, sistemas, st_disk
from ngplat.codegen import generar_para_sistema
from ngplat.errors import ProjectError
from ngplat.gfx import Palette
from ngplat.sonido import periodo_paula, periodo_psg


def _banderas_del_makefile(ruta):
    """Las opciones del compilador que importan para esta comprobacion."""
    with open(ruta, encoding="utf-8") as fh:
        texto = fh.read()
    return [b for b in ("-fno-store-merging",) if b in texto]


def _comprobar_amiga(prueba, disco, capturas, proyecto="", pantallas=False):
    """Arranca el disquete del Amiga en PUAE, en un proceso aparte.

    Aparte por lo mismo que el ST: **el core no se deja arrancar dos veces en
    el mismo proceso**. No se cuelga como Hatari, que seria facil de ver; lo
    que hace es sonar peor. La primera vez el analizador reconoce las 16 notas
    de la melodia y a partir de la segunda solo 12, con las ultimas mudas.
    Esta medido: `dosveces.py` arranca tres veces seguidas y da 16, 12, 12.

    Como el game.yaml no cuelga del disquete, se le pasa donde esta para que
    el proceso hijo sepa que musica y que efecto tiene que oir."""
    import emulador_amiga
    from libretro import buscar_core
    if not buscar_core(emulador_amiga.CORE, "NEOPLAT_CORE_AMIGA"):
        prueba.skipTest("no esta instalado el core de PUAE")
    orden = [sys.executable, os.path.join(KIT, "tests", "emulador_amiga.py"),
             disco, capturas]
    if proyecto:
        orden.append("--proyecto=" + proyecto)
    if pantallas:
        orden.append("--pantallas")
    hecho = subprocess.run(orden, capture_output=True, text=True)
    print(hecho.stdout.strip())
    prueba.assertEqual(hecho.returncode, 0,
                       "el disquete no arranca, no se juega o no suena en el "
                       "emulador:\n" + hecho.stdout + hecho.stderr)


def _comprobar_st(prueba, disco, capturas, proyecto="", pantallas=False):
    """Arranca el disquete del ST en Hatari, en un proceso aparte.

    Aparte porque el core no se deja arrancar dos veces en el mismo proceso: la
    segunda se queda colgada, y aqui hay dos pruebas que lo usan.
    """
    import emulador_st
    from libretro import buscar_core
    if not buscar_core(emulador_st.CORE, "NEOPLAT_CORE_ST"):
        prueba.skipTest("no esta instalado el core de Hatari")
    if not emulador_st._buscar_tos():
        prueba.skipTest("no hay una imagen de TOS (tos.img)")
    orden = [sys.executable, os.path.join(KIT, "tests", "emulador_st.py"),
             disco, capturas]
    if proyecto:
        orden.append("--proyecto=" + proyecto)
    if pantallas:
        orden.append("--pantallas")
    hecho = subprocess.run(orden, capture_output=True, text=True)
    print(hecho.stdout.strip())
    prueba.assertEqual(hecho.returncode, 0,
                       "el disquete no arranca, no se juega o no suena en el "
                       "emulador:\n" + hecho.stdout + hecho.stderr)


def _compilador_68k():
    for nombre in ("m68k-elf-gcc", "m68k-linux-gnu-gcc"):
        if shutil.which(nombre):
            return nombre
    return ""


def _tile16(semilla: int, colores: int = 15):
    return [((x * 7 + y * 3 + semilla) % colores) + 1
            for y in range(16) for x in range(16)]


class TestColores(unittest.TestCase):
    def test_ida_y_vuelta_mega_drive(self):
        """El color del VDP son 3 bits por canal: el redondeo tiene que ser estable."""
        for rgb in ((0, 0, 0), (255, 255, 255), (34, 170, 238), (200, 12, 90)):
            valor = gfx_md.md_color(rgb)
            self.assertEqual(gfx_md.md_color(gfx_md.md_color_a_rgb(valor)), valor)
            self.assertEqual(valor & 0x1111, 0, "los bits bajos van a cero")

    def test_ida_y_vuelta_amiga(self):
        """El color del Amiga son 4 bits por canal."""
        for rgb in ((0, 0, 0), (255, 255, 255), (34, 170, 238), (200, 12, 90)):
            valor = gfx_amiga.amiga_color(rgb)
            self.assertEqual(gfx_amiga.amiga_color(gfx_amiga.amiga_color_a_rgb(valor)),
                             valor)
            self.assertLessEqual(valor, 0x0FFF)

    def test_cada_maquina_ve_su_propio_color(self):
        for nombre in ("neogeo", "megadrive", "amiga", "jaguar", "atarist", "x68000"):
            visible = sistemas.obtener(nombre).color_visible((200, 12, 90))
            self.assertEqual(len(visible), 3)
            for canal in visible:
                self.assertTrue(0 <= canal <= 255)


class TestGraficosMegaDrive(unittest.TestCase):
    def test_tile_ida_y_vuelta(self):
        pixeles = [(x + y) % 16 for y in range(8) for x in range(8)]
        datos = gfx_md.codificar_tile(pixeles)
        self.assertEqual(len(datos), gfx_md.TILE_BYTES)
        self.assertEqual(gfx_md.decodificar_tile(datos), pixeles)

    def test_un_tile_de_16_son_cuatro_de_8(self):
        grande = _tile16(1)
        trozos = gfx_md.partir_16(grande)
        self.assertEqual(len(trozos), 4)
        # el VDP dibuja los cuatro trozos por columnas: arriba-izq, abajo-izq...
        self.assertEqual(trozos[0][0], grande[0])
        self.assertEqual(trozos[1][0], grande[8 * 16])
        self.assertEqual(trozos[2][0], grande[8])

    def test_las_paletas_se_funden_en_cuatro(self):
        paletas = [Palette("p%d" % i, [(i * 8, 0, 0), (0, i * 8, 0)])
                   for i in range(6)]
        reparto = gfx_md.repartir_paletas(paletas)
        self.assertLessEqual(len(reparto.paletas), gfx_md.PALETAS)
        for paleta in paletas:
            indice, mapa = reparto.asignacion[paleta.name]
            self.assertLess(indice, gfx_md.PALETAS)
            self.assertEqual(mapa[0], 0, "el 0 sigue siendo transparente")

    def test_avisa_si_no_caben(self):
        paletas = [Palette("p%d" % i, [(i * 4 + c, 1, 2) for c in range(15)])
                   for i in range(5)]
        with self.assertRaises(ProjectError):
            gfx_md.repartir_paletas(paletas)


class TestGraficosAmiga(unittest.TestCase):
    def test_tile_ida_y_vuelta(self):
        pixeles = [(x + y) % 32 for y in range(16) for x in range(16)]
        datos = gfx_amiga.codificar_tile(pixeles)
        self.assertEqual(len(datos), gfx_amiga.BYTES_POR_TILE)
        self.assertEqual(gfx_amiga.decodificar_tile(datos), pixeles)

    def test_la_mascara_marca_lo_que_no_es_transparente(self):
        pixeles = [0] * 256
        pixeles[0] = 5
        pixeles[255] = 7
        mascara = gfx_amiga.codificar_mascara(pixeles)
        self.assertEqual(len(mascara), gfx_amiga.BYTES_MASCARA)
        vuelta = gfx_amiga.decodificar_mascara(mascara)
        self.assertEqual(vuelta[0], 1)
        self.assertEqual(vuelta[255], 1)
        self.assertEqual(sum(vuelta), 2)

    def test_la_mascara_se_repite_una_vez_por_bitplane(self):
        """El blitter recorre el dibujo entrelazado: la mascara le sigue el paso."""
        pixeles = [1] * 16 + [0] * (256 - 16)      # solo la primera fila
        mascara = gfx_amiga.codificar_mascara(pixeles)
        primeras = [mascara[i * 2] << 8 | mascara[i * 2 + 1]
                    for i in range(gfx_amiga.PLANOS)]
        self.assertEqual(primeras, [0xFFFF] * gfx_amiga.PLANOS)
        siguiente = mascara[gfx_amiga.PLANOS * 2] << 8 | mascara[gfx_amiga.PLANOS * 2 + 1]
        self.assertEqual(siguiente, 0, "la segunda fila esta vacia")

    def test_las_paletas_se_funden_en_una_de_32(self):
        paletas = [Palette("p%d" % i, [(i * 8, 0, 0), (0, i * 8, 0)])
                   for i in range(4)]
        unica = gfx_amiga.fusionar_paletas(paletas)
        self.assertLessEqual(len(unica.colores), gfx_amiga.COLORES)
        self.assertEqual(unica.colores[0], (0, 0, 0))
        self.assertEqual(len(unica.palabras()), 32)
        for paleta in paletas:
            for indice_local, color in enumerate(paleta.colors):
                destino = unica.asignacion[paleta.name][indice_local + 1]
                self.assertEqual(unica.colores[destino], color)

    def test_avisa_si_hay_mas_de_32_colores(self):
        paletas = [Palette("p%d" % i, [(i * 16 + c, 1, 2) for c in range(15)])
                   for i in range(4)]
        with self.assertRaises(ProjectError):
            gfx_amiga.fusionar_paletas(paletas)

    def test_en_doble_plano_los_colores_que_sobran_se_aproximan(self):
        """Con siete colores por plano no hay dibujo que quepa: en vez de dar un
        error, cada color se cambia por el mas parecido de los que se quedan."""
        paletas = [Palette("p%d" % i, [(i * 16 + c * 3, 40, 80) for c in range(15)])
                   for i in range(3)]
        with self.assertRaises(ProjectError):
            gfx_amiga.fusionar_paletas(paletas, tope=8)
        unica = gfx_amiga.fusionar_paletas(paletas, tope=8, aproximar=True)
        self.assertLessEqual(len(unica.colores), 8)
        self.assertGreater(unica.perdidos, 0)
        for paleta in paletas:
            for indice_local, color in enumerate(paleta.colors):
                destino = unica.asignacion[paleta.name][indice_local + 1]
                self.assertLess(destino, 8)
                elegido = unica.colores[destino]
                # el que le toca es el mas parecido de los que hay
                distancias = [gfx_amiga._distancia(color, c) for c in unica.colores[1:]]
                self.assertEqual(gfx_amiga._distancia(color, elegido), min(distancias))

    def test_el_doble_plano_gasta_tres_bitplanes_por_dibujo(self):
        banco = gfx_amiga.BancoAmiga(planos=3)
        banco.anadir(_tile16(3))
        self.assertEqual(banco.bytes_por_tile, 16 * 3 * 2)
        self.assertEqual(len(banco.tiles), 96)
        self.assertEqual(len(banco.mascaras), 96)

    def test_los_dibujos_del_estilo_hierro_caben_en_doble_plano(self):
        """El estilo 'hierro' esta dibujado para el modo de 8 colores: tiene que
        entrar sin que el compilador cambie ni un color."""
        from ngplat import art_hierro
        dibujos = art_hierro.todos()
        juego, fondo = set(), set()
        for nombre, imagen in dibujos.items():
            colores = {c for c in imagen.colors() if c[3]}
            (fondo if "cueva" in nombre else juego).update(colores)
        self.assertLessEqual(len(juego), 6,
                             "al plano de delante le quedan seis colores")
        self.assertLessEqual(len(fondo), 7,
                             "al plano de atras le quedan siete colores")

    def test_el_banco_comparte_los_dibujos_repetidos(self):
        banco = gfx_amiga.BancoAmiga()
        primero = banco.anadir(_tile16(3))
        self.assertEqual(banco.anadir(_tile16(3)), primero)
        self.assertEqual(banco.cuantos, 1)
        self.assertEqual(banco.anadir(_tile16(3), compartir=False), 1)


class TestListado(unittest.TestCase):
    """Lo que cuenta `ngplat sistemas` tiene que seguir siendo verdad."""

    def test_cada_maquina_dice_como_suena_y_que_hace_con_el_parallax(self):
        for nombre in ("neogeo", "megadrive", "amiga", "jaguar", "atarist", "x68000"):
            sistema = sistemas.obtener(nombre)
            texto = " ".join(sistema.notas).lower()
            self.assertTrue(sistema.notas, "%s no cuenta nada de si" % nombre)
            self.assertIn("sonido:", texto, nombre)
            self.assertTrue("parallax" in texto or "colores:" in texto, nombre)

    def test_el_amiga_dice_que_tiene_dos_modos(self):
        notas = " ".join(sistemas.obtener("amiga").notas)
        for modo in ("32colores", "8colores"):
            self.assertIn(modo, notas,
                          "el listado no menciona 'amiga: %s'" % modo)


class TestSonidoDeCadaChip(unittest.TestCase):
    def test_la_misma_nota_en_los_tres_chips(self):
        """440 Hz tienen que sonar a 440 Hz en las tres maquinas (con su redondeo)."""
        from ngplat.sonido import periodo_ssg, SSG_CLOCK, PSG_CLOCK, PAULA_CLOCK
        self.assertAlmostEqual(SSG_CLOCK / (16.0 * periodo_ssg(440)), 440, delta=2)
        self.assertAlmostEqual(PSG_CLOCK / (32.0 * periodo_psg(440)), 440, delta=2)
        self.assertAlmostEqual(PAULA_CLOCK / (2.0 * periodo_paula(440, muestras=2)),
                               440, delta=2)

    def test_paula_llega_a_todo_el_rango_del_kit(self):
        """Con una onda de dos bytes entran las notas de 30 a 8000 Hz."""
        for hz in (30, 110, 440, 1760, 4000, 8000):
            periodo = periodo_paula(hz, muestras=2)
            self.assertGreaterEqual(periodo, 124, "%d Hz se sale por abajo" % hz)
            self.assertLessEqual(periodo, 65535)


class TestDisquete(unittest.TestCase):
    """El .adf: un disquete de Amiga de 880 KB que arranca solo."""

    def test_tamano_y_arranque(self):
        disco = adf.Disco("PRUEBA")
        imagen = disco.bytes()
        self.assertEqual(len(imagen), 901120, "un disquete son 80x2x11x512 bytes")
        self.assertEqual(imagen[0:4], b"DOS\0", "falta la marca del sistema OFS")
        self.assertIn(b"dos.library", imagen[:1024], "el bootblock no arranca nada")

    def test_las_sumas_de_control_cuadran(self):
        """El Amiga rechaza el disco si una suma no da cero."""
        disco = adf.Disco("PRUEBA")
        disco.fichero("JUEGO", b"x" * 5000)
        imagen = disco.bytes()

        # el bootblock: suma con acarreo de sus 1024 bytes
        suma = 0
        for i in range(0, 1024, 4):
            anterior = suma
            suma = (suma + struct.unpack_from(">I", imagen, i)[0]) & 0xFFFFFFFF
            if suma < anterior:
                suma = (suma + 1) & 0xFFFFFFFF
        self.assertEqual(suma, 0xFFFFFFFF, "la suma del bootblock no cuadra")

        # los demas bloques: la suma de las 128 palabras largas tiene que dar 0
        for numero in range(2, adf.BLOQUES):
            base = numero * adf.BLOQUE
            (tipo, ) = struct.unpack_from(">I", imagen, base)
            if tipo not in (adf.T_HEADER, adf.T_DATA, adf.T_LIST):
                continue
            suma = 0
            for i in range(0, adf.BLOQUE, 4):
                suma = (suma + struct.unpack_from(">I", imagen, base + i)[0]) & 0xFFFFFFFF
            self.assertEqual(suma, 0, "el bloque %d tiene mal la suma" % numero)

    def test_ida_y_vuelta_de_un_fichero_grande(self):
        """Mas de 72 bloques de datos: hacen falta bloques de extension."""
        datos = bytes((i * 7 + 3) & 0xFF for i in range(200 * 1024))
        disco = adf.Disco("PRUEBA")
        disco.fichero("GRANDE", datos)
        vuelta = adf.leer(disco.bytes())
        self.assertEqual(vuelta["GRANDE"], datos)

    def test_el_disco_del_juego_arranca_el_ejecutable(self):
        tmp = tempfile.mkdtemp(prefix="neoplat-adf-")
        try:
            ruta = os.path.join(tmp, "juego.adf")
            adf.crear_disco_de_juego(ruta, "MI JUEGO", "MiJuego", b"ejecutable")
            with open(ruta, "rb") as fh:
                contenido = adf.leer(fh.read())
            self.assertEqual(contenido["MiJuego"], b"ejecutable")
            arranque = contenido["s/startup-sequence"].decode("latin-1")
            self.assertIn("MiJuego", arranque,
                          "el startup-sequence no lanza el juego")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_el_bitmap_marca_lo_ocupado(self):
        disco = adf.Disco("PRUEBA")
        disco.fichero("JUEGO", b"x" * 5000)
        imagen = disco.bytes()
        base = (adf.BLOQUE_RAIZ + 1) * adf.BLOQUE
        libres = 0
        for numero in range(2, adf.BLOQUES):
            palabra = struct.unpack_from(">I", imagen, base + 4 + ((numero - 2) // 32) * 4)[0]
            libre = (palabra >> ((numero - 2) % 32)) & 1
            if libre:
                libres += 1
            else:
                self.assertIn(numero, disco.usados, "el bloque %d no esta en uso" % numero)
        self.assertEqual(libres, adf.BLOQUES - len(disco.usados))

    def test_no_deja_meter_mas_de_880_kb(self):
        disco = adf.Disco("PRUEBA")
        with self.assertRaises(adf.ErrorAdf):
            disco.fichero("ENORME", b"x" * (900 * 1024))


class TestDisqueteSt(unittest.TestCase):
    """El .st: un disquete de Atari ST de 720 KB con un FAT12 dentro.

    Lo que se comprueba es lo que mira TOS al encender: el tamano, la tabla de
    parametros del sector de arranque (que va al reves, en little endian) y que
    el juego esta en la carpeta AUTO, que es de donde lo saca solo.
    """

    def test_tamano_y_tabla_de_parametros(self):
        imagen = st_disk.Disco("PRUEBA").bytes()
        self.assertEqual(len(imagen), 737280, "un disquete son 80x2x9x512 bytes")
        campos = struct.unpack_from("<HBHBHHBHHH", imagen, 11)
        self.assertEqual(campos, (512, 2, 1, 2, 112, 1440, 0xF9, 5, 9, 2),
                         "la tabla de parametros no describe un disco de 720 KB")

    def test_el_sector_de_arranque_no_se_ejecuta(self):
        """TOS ejecuta el sector 0 solo si sus palabras suman $1234. Aqui el
        juego lo lanza la carpeta AUTO, asi que no debe sumar eso."""
        imagen = st_disk.Disco("PRUEBA").bytes()
        suma = sum(struct.unpack_from(">H", imagen, i)[0]
                   for i in range(0, 512, 2)) & 0xFFFF
        self.assertNotEqual(suma, 0x1234)

    def test_ida_y_vuelta_de_un_fichero_grande(self):
        """Mas de un cluster: hace falta que la cadena de la FAT este bien."""
        datos = bytes((i * 7 + 3) & 0xFF for i in range(200 * 1024))
        disco = st_disk.Disco("PRUEBA")
        disco.fichero("GRANDE.BIN", datos)
        self.assertEqual(st_disk.leer(disco.bytes())["GRANDE.BIN"], datos)

    def test_el_ultimo_cluster_del_disco_tambien_se_apunta(self):
        """En FAT12 las entradas van de dos en dos y aqui hay un numero impar:
        si se cuentan mal, el ultimo cluster se pierde."""
        disco = st_disk.Disco("PRUEBA")
        datos = b"z" * ((st_disk.CLUSTERES - 2) * st_disk.CLUSTER)
        disco.fichero("TODO.BIN", datos)
        self.assertEqual(st_disk.leer(disco.bytes())["TODO.BIN"], datos)

    def test_el_juego_va_dentro_de_auto(self):
        tmp = tempfile.mkdtemp(prefix="neoplat-st-")
        try:
            ruta = os.path.join(tmp, "juego.st")
            st_disk.crear_disco_de_juego(ruta, "MIJUEG", "JUEGO.PRG", b"ejecutable")
            with open(ruta, "rb") as fh:
                contenido = st_disk.leer(fh.read())
            self.assertEqual(contenido["AUTO/JUEGO.PRG"], b"ejecutable",
                             "TOS solo arranca solo lo que hay en AUTO")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_no_deja_meter_mas_de_720_kb(self):
        disco = st_disk.Disco("PRUEBA")
        with self.assertRaises(st_disk.ErrorSt):
            disco.fichero("ENORME.BIN", b"x" * (800 * 1024))

    def test_el_nombre_tiene_que_caber_en_ocho_y_tres(self):
        disco = st_disk.Disco("PRUEBA")
        with self.assertRaises(st_disk.ErrorSt):
            disco.fichero("UNNOMBREMUYLARGO.PRG", b"x")


class TestEjecutablePrg(unittest.TestCase):
    """La tabla de relocalizacion del .PRG, que es la parte que se puede
    equivocar sin que salte nada hasta que el ST se cuelga."""

    def test_sin_correcciones(self):
        self.assertEqual(prg.tabla_de_relocalizacion([]), b"\0\0\0\0")

    def test_la_primera_va_entera_y_las_demas_de_a_byte(self):
        tabla = prg.tabla_de_relocalizacion([4, 10, 20])
        self.assertEqual(tabla, struct.pack(">I", 4) + bytes([6, 10, 0]))

    def test_un_hueco_grande_se_parte_en_saltos_de_254(self):
        tabla = prg.tabla_de_relocalizacion([0, 600])
        self.assertEqual(tabla[:4], struct.pack(">I", 0))
        pasos = tabla[4:-1]
        avance = sum(prg.SALTO if p == 1 else p for p in pasos)
        self.assertEqual(avance, 600, "los saltos no llegan a la correccion")
        self.assertEqual(tabla[-1], 0, "la tabla no se cierra")

    def test_las_correcciones_van_en_direcciones_pares(self):
        with self.assertRaises(prg.ErrorPrg):
            prg.tabla_de_relocalizacion([3])


class TestProyectoGenerado(unittest.TestCase):
    """Genera el proyecto para cada maquina y mira que salga completo."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-sistemas-")
        cls.proyecto = os.path.join(cls.tmp, "juego")
        from ngplat.scaffold import crear_proyecto
        crear_proyecto(cls.proyecto, "PRUEBA", "TEST")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _generar(self, nombre):
        build = cargar_demo(self.proyecto, nombre)
        sistema = sistemas.obtener(nombre)
        sistema.comprobar(build)
        salida_dir = os.path.join(self.tmp, "build-" + nombre)
        generar_para_sistema(build, salida_dir, sistema, "202")
        return build, salida_dir

    def test_megadrive_genera_todo(self):
        build, out = self._generar("megadrive")
        for archivo in ("src/gamedata.c", "src/graficos.c", "src/sonido.c",
                        "src/np_video.c", "src/arranque.c", "megadrive.ld",
                        "Makefile", "arreglar_rom.py"):
            self.assertTrue(os.path.isfile(os.path.join(out, archivo)), archivo)
        self.assertEqual(len(build.paletas), 4, "el VDP tiene cuatro paletas")

    def test_amiga_genera_todo(self):
        build, out = self._generar("amiga")
        for archivo in ("src/gamedata.c", "src/graficos.c", "src/sonido.c",
                        "src/np_video.c", "src/np_hud.c", "src/arranque.c",
                        "amiga.ld", "Makefile", "hacer_ejecutable.py",
                        "hacer_adf.py"):
            self.assertTrue(os.path.isfile(os.path.join(out, archivo)), archivo)
        with open(os.path.join(out, "src/graficos.c"), encoding="utf-8") as fh:
            texto = fh.read()
        self.assertIn("np_tile_data", texto)
        self.assertIn("np_tile_mask", texto)
        self.assertIn("np_colores[32]", texto)

    def test_los_arrays_de_bytes_se_declaran_alineados(self):
        """El Atari ST y el Amiga leen los dibujos de palabra en palabra aunque
        el array sea de bytes, y el 68000 no sabe hacer eso en una direccion
        impar: se para en seco. Como el enlazador coloca los arrays de bytes
        donde le cabe, sin el `aligned` el juego arrancaba o no segun cuantos
        dibujos llevara."""
        for maquina, nombres in (
            ("atarist", ("np_tile_data", "np_tile_mask", "np_pantallas",
                         "np_hud_bitmap")),
            ("amiga", ("np_tile_data", "np_tile_mask", "np_bitmap",
                       "np_hud_bitmap")),
        ):
            _, out = self._generar(maquina)
            fuente = os.path.join(out, "src/graficos.c")
            if maquina == "atarist" and not os.path.isfile(fuente):
                self.fail("el Atari ST ya no genera src/graficos.c")
            with open(fuente, encoding="utf-8") as fh:
                texto = fh.read()
            if maquina == "atarist":
                # el marcador del ST vive en el motor, no en lo generado
                with open(os.path.join(out, "src/np_hud.c"), encoding="utf-8") as fh:
                    texto += fh.read()
            for nombre in nombres:
                trozo = texto.split(nombre, 1)
                self.assertEqual(len(trozo), 2, "%s: falta %s" % (maquina, nombre))
                # la declaracion acaba en el ';' o en el '=' de los datos
                declaracion = trozo[1].split("{")[0].split(";")[0]
                self.assertIn("aligned", declaracion,
                              "%s: %s se declara sin alinear" % (maquina, nombre))

    def test_amiga_en_doble_plano_pide_seis_bitplanes(self):
        """Con 'amiga: 8colores' salen tres bitplanes por plano y el mapa de
        bits del parallax, que en el modo normal no existe."""
        otro = os.path.join(self.tmp, "juego8")
        if not os.path.isdir(otro):
            shutil.copytree(self.proyecto, otro)
            yaml = os.path.join(otro, "game.yaml")
            with open(yaml, encoding="utf-8") as fh:
                texto = fh.read()
            assert "  amiga: 32colores" in texto, "el andamiaje ya no trae el modo"
            with open(yaml, "w", encoding="utf-8") as fh:
                fh.write(texto.replace("  amiga: 32colores", "  amiga: 8colores", 1))
        build = cargar_demo(otro, "amiga")
        sistema = sistemas.obtener("amiga")
        sistema.comprobar(build)
        salida_dir = os.path.join(self.tmp, "build-amiga8")
        generar_para_sistema(build, salida_dir, sistema, "202")
        self.assertIn("#define NP_PLANOS 3", build.info["cabecera"])
        with open(os.path.join(salida_dir, "src/graficos.c"), encoding="utf-8") as fh:
            texto = fh.read()
        self.assertIn("np_fondo_bitmap", texto)
        self.assertIn("np_colores[32]", texto)
        # los dibujos ocupan tres bitplanes, no cinco
        banco = build.info["banco"]
        self.assertEqual(len(banco.tiles), banco.cuantos * 96)
        # y el parallax se empaqueta de verdad: alguna casilla apunta a un dibujo
        self.assertTrue(any(any(c.tiles) for c in build.layers),
                        "el parallax no se ha metido en el banco")

    def test_el_estilo_hierro_no_pierde_ningun_color(self):
        """Compilar el estilo 'hierro' para Amiga no aproxima nada: para eso
        esta dibujado con la paleta corta."""
        otro = os.path.join(self.tmp, "hierro")
        if not os.path.isdir(otro):
            from ngplat.scaffold import crear_proyecto
            crear_proyecto(otro, "HIERRO", "TEST", estilo="hierro")
        build = cargar_demo(otro, "amiga")
        self.assertTrue(build.project.amiga_modo == "8colores",
                        "el estilo hierro viene con el doble plano puesto")
        self.assertEqual(build.info["stats"]["aproximados"], 0)
        self.assertIn("#define NP_PLANOS 3", build.info["cabecera"])
        self.assertEqual(sistemas.obtener("amiga").comprobar(build), [])

    def test_jaguar_genera_todo(self):
        build, out = self._generar("jaguar")
        for archivo in ("src/gamedata.c", "src/graficos.c", "src/np_video.c",
                        "src/np_hud.c", "src/arranque.S", "jaguar.ld",
                        "Makefile", "hacer_rom.py"):
            self.assertTrue(os.path.isfile(os.path.join(out, archivo)), archivo)
        with open(os.path.join(out, "src/graficos.c"), encoding="utf-8") as fh:
            texto = fh.read()
        self.assertIn("np_colores[256]", texto, "la Jaguar tiene 256 colores")
        self.assertNotIn("np_tile_mask", texto,
                         "en la Jaguar no hacen falta mascaras: el color 0 es "
                         "transparente para el chip")

    def test_atarist_genera_todo(self):
        build, out = self._generar("atarist")
        for archivo in ("src/gamedata.c", "src/graficos.c", "src/sonido.c",
                        "src/np_video.c", "src/np_hud.c", "src/arranque.c",
                        "st.ld", "Makefile", "hacer_prg.py", "hacer_st.py"):
            self.assertTrue(os.path.isfile(os.path.join(out, archivo)), archivo)
        with open(os.path.join(out, "src/graficos.c"), encoding="utf-8") as fh:
            texto = fh.read()
        self.assertIn("np_colores[16]", texto, "el ST ensena 16 colores")
        self.assertIn("np_tile_mask", texto)
        self.assertEqual(len(build.paletas), 1, "el ST tiene una sola paleta")

    def test_el_st_dibuja_el_parallax_solo_por_pantallas(self):
        """En el ST el fondo sale gratis si la vista esta quieta, y no cabe si
        se desliza: por eso depende de la camara y no de un modo aparte."""
        con_scroll = cargar_demo(self.proyecto, "atarist")
        self.assertEqual(con_scroll.project.camera, "scroll",
                         "el andamiaje ya no viene con scroll")
        self.assertFalse(con_scroll.info["fondo"])
        self.assertIn("#define NP_FONDO_ST 0", con_scroll.info["cabecera"])
        self.assertTrue(all(not any(c.tiles) for c in con_scroll.layers),
                        "con scroll el parallax deberia quedarse a cero")

        otro = os.path.join(self.tmp, "st-pantallas")
        if not os.path.isdir(otro):
            from comun import proyecto_por_pantallas
            proyecto_por_pantallas(otro)
        por_pantallas = cargar_demo(otro, "atarist")
        self.assertTrue(por_pantallas.info["fondo"])
        self.assertIn("#define NP_FONDO_ST 1", por_pantallas.info["cabecera"])
        self.assertTrue(any(any(c.tiles) for c in por_pantallas.layers),
                        "el parallax no se ha metido en el banco")
        # y la tabla de opacos: el escenario tiene tiles que tapan la casilla
        banco = por_pantallas.info["banco"]
        self.assertEqual(len(banco.opacos), banco.cuantos)
        self.assertTrue(any(banco.opacos),
                        "ningun dibujo tapa la casilla entera: el fondo se "
                        "pintaria debajo de todos y costaria el doble")

    def test_el_st_recorta_la_pantalla_pero_no_el_mundo(self):
        """El ST ensena 200 lineas y las demas 224. Lo que **no** puede cambiar
        es el mundo: si el motor viera otra pantalla, el juego seria otro."""
        self.assertEqual(sistemas.obtener("atarist").pantalla, (320, 200))
        for nombre in ("neogeo", "megadrive", "amiga", "jaguar", "x68000"):
            self.assertEqual(sistemas.obtener(nombre).pantalla, (320, 224), nombre)
        cabecera = os.path.join(KIT, "engine", "include", "np_types.h")
        with open(cabecera, encoding="utf-8") as fh:
            texto = fh.read()
        self.assertIn("#define NP_SCREEN_H  224", texto,
                      "la altura del mundo la comparten todas las maquinas")

    def test_los_sistemas_describen_el_mismo_juego(self):
        """Cambiar de maquina no cambia el juego: niveles, enemigos y mapas."""
        referencia = None
        for nombre in ("neogeo", "megadrive", "amiga", "jaguar", "atarist", "x68000"):
            build = cargar_demo(self.proyecto, nombre)
            resumen = [(n.name, n.width, n.height, n.cells, n.spawns)
                       for n in build.levels]
            if referencia is None:
                referencia = resumen
            else:
                self.assertEqual(resumen, referencia, nombre)

    def test_el_codigo_de_cada_maquina_compila_en_el_ordenador(self):
        """Sintaxis y tipos, sin necesidad de un compilador de 68000."""
        if not shutil.which("gcc"):
            self.skipTest("no hay gcc")
        fuentes = {
            "megadrive": ["src/np_video.c", "src/np_hud.c", "src/np_sound.c",
                          "src/main.c", "src/graficos.c", "src/sonido.c"],
            "amiga": ["src/np_video.c", "src/np_hud.c", "src/np_sound.c",
                      "src/main.c", "src/graficos.c", "src/sonido.c"],
            "atarist": ["src/np_video.c", "src/np_hud.c", "src/np_sound.c",
                        "src/main.c", "src/graficos.c", "src/sonido.c"],
        }
        for sistema, archivos in fuentes.items():
            _, out = self._generar(sistema)
            for archivo in archivos:
                resultado = subprocess.run(
                    ["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                     "-Wno-array-bounds", "-fsyntax-only",
                     "-I", os.path.join(out, "src"), os.path.join(out, archivo)],
                    capture_output=True, text=True)
                self.assertEqual(resultado.returncode, 0,
                                 "%s/%s:\n%s" % (sistema, archivo, resultado.stderr))


def _simbolos_del_elf(ruta):
    """{nombre: direccion} de los simbolos globales del ELF que suelta el
    enlazador de 68000. Se lee con el mismo lector de ELF del kit para no
    depender de que este instalado `nm`."""
    import struct
    from ngplat.prg import Elf
    with open(ruta, "rb") as fh:
        elf = Elf(fh.read())
    tabla = elf.seccion(".symtab")
    textos = elf.seccion(".strtab")
    if tabla is None or textos is None:
        return {}
    crudo = elf.contenido(tabla)
    nombres = elf.contenido(textos)
    salida = {}
    for i in range(0, len(crudo), 16):
        off, valor = struct.unpack_from(">II", crudo, i)
        if not off or off >= len(nombres):
            continue
        fin = nombres.index(b"\0", off)
        salida[nombres[off:fin].decode("ascii", "replace")] = valor
    return salida


class TestSpritesNeoGeo(unittest.TestCase):
    """El aviso de sprites de la Neo Geo.

    El motor no se queja si un nivel se pasa: np_draw_actor deja de dibujar y ya
    esta. La Mega Drive avisaba desde el principio y la Neo Geo no miraba nada,
    asi que un nivel cargado salia a medias sin que nadie lo dijera.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-sprites-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _proyecto(self, nombre, filas=None):
        from ngplat.scaffold import crear_proyecto
        raiz = os.path.join(self.tmp, nombre)
        crear_proyecto(raiz, "SPRITES", "TEST")
        if filas is not None:
            yaml = os.path.join(raiz, "game.yaml")
            with open(yaml, encoding="utf-8") as fh:
                texto = fh.read()
            mapa = "\n".join("      " + f for f in filas)
            corte = texto.index("niveles:")
            texto = (texto[:corte] + 'niveles:\n  - nombre: "LLENO"\n'
                     '    fondo: "#101830"\n    mapa: |\n' + mapa + "\n")
            with open(yaml, "w", encoding="utf-8") as fh:
                fh.write(texto)
        return cargar_demo(raiz, "neogeo")

    def test_el_andamiaje_no_da_falsa_alarma(self):
        """Lo primero que tiene que hacer un aviso es no saltar cuando no toca:
        si saltara con el proyecto de partida, se aprenderia a ignorarlo."""
        build = self._proyecto("normal")
        self.assertEqual(sistemas.obtener("neogeo").comprobar(build), [])

    def test_avisa_cuando_un_nivel_no_cabe_en_pantalla(self):
        ancho = 24
        filas = ["." * ancho for _ in range(10)]
        # cuatro filas de dieciseis tablones: cada uno mide 32 px, o sea dos
        # columnas de sprite, y los sesenta y cuatro caben en una pantalla
        for _ in range(4):
            filas.append(("T" * 16).ljust(ancho, "."))
        filas.append("P" + "." * (ancho - 3) + "G.")
        filas.append("#" * ancho)
        build = self._proyecto("lleno", filas)
        self.assertEqual(len(build.levels[0].spawns), 64,
                         "el nivel de prueba no tiene los spawns que se creia")
        avisos = sistemas.obtener("neogeo").comprobar(build)
        self.assertEqual(len(avisos), 1, avisos)
        self.assertIn("129", avisos[0], "la cuenta no sale: %s" % avisos[0])
        self.assertIn("96", avisos[0])
        self.assertIn("LLENO", avisos[0])

    def test_cada_actor_cuesta_por_su_ancho(self):
        """Un actor de 32 px gasta dos columnas y uno de 16 gasta una: es lo que
        hace np_draw_actor, y contar actores a secas se equivocaria al doble."""
        from ngplat.sistemas.neogeo import _columnas_a_la_vez
        ancho = 24
        setas = ["." * ancho for _ in range(12)]
        setas.append(("s" * 10).ljust(ancho, "."))
        setas.append("P" + "." * (ancho - 3) + "G.")
        setas.append("#" * ancho)
        tablones = list(setas)
        tablones[12] = ("T" * 10).ljust(ancho, ".")
        # diez setas de 16 px = 10 columnas; diez tablones de 32 = 20
        self.assertEqual(_columnas_a_la_vez(self._proyecto("setas", setas))[0], 11)
        self.assertEqual(_columnas_a_la_vez(self._proyecto("tablones", tablones))[0], 21)

    def test_lo_que_esta_lejos_no_cuenta(self):
        """Solo se miran los que caben en una pantalla a la vez: si contara el
        nivel entero, cualquier nivel largo avisaria siempre."""
        from ngplat.sistemas.neogeo import _columnas_a_la_vez
        juntos = ["." * 60 for _ in range(12)]
        juntos.append(("T" * 20).ljust(60, "."))
        juntos.append("P" + "." * 57 + "G.")
        juntos.append("#" * 60)
        # los mismos veinte tablones, pero repartidos por todo el nivel
        lejos = list(juntos)
        lejos[12] = "".join("T" if i % 3 == 0 else "." for i in range(60))
        self.assertGreater(_columnas_a_la_vez(self._proyecto("juntos", juntos))[0],
                           _columnas_a_la_vez(self._proyecto("lejos", lejos))[0])


class TestCompilacionReal(unittest.TestCase):
    """Con un compilador de 68000 instalado, se construye de verdad."""

    @classmethod
    def setUpClass(cls):
        cls.cc = _compilador_68k()
        if not cls.cc:
            raise unittest.SkipTest("no hay un compilador de 68000 instalado")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-68k-")
        cls.proyecto = os.path.join(cls.tmp, "juego")
        from ngplat.scaffold import crear_proyecto
        crear_proyecto(cls.proyecto, "PRUEBA", "TEST")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tmp", ""):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def _generar(self, nombre):
        build = cargar_demo(self.proyecto, nombre)
        out = os.path.join(self.tmp, nombre)
        generar_para_sistema(build, out, sistemas.obtener(nombre), "202")
        self.proyecto_cargado = build.project
        return out

    def _banda_sonora(self):
        """La musica y el efecto de salto del proyecto de prueba, para que las
        pruebas de emulador puedan comprobar que suena lo que toca."""
        from sonido import musica_al_empezar
        proyecto = getattr(self, "proyecto_cargado", None)
        if not proyecto:
            return (None, None, None)
        return (musica_al_empezar(proyecto), proyecto.sound.efectos.get("salto"),
                proyecto.sound)

    def _construir(self, nombre):
        out = self._generar(nombre)
        hecho = subprocess.run(["make", "-C", out], capture_output=True, text=True)
        self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
        return out

    def test_los_graficos_caen_en_direccion_par(self):
        """El Atari ST y el Amiga leen los dibujos de palabra larga en palabra
        larga aunque el array sea de bytes. En el 68000 eso, en una direccion
        impar, es un address error: la maquina se para en seco y la pantalla se
        queda congelada. El enlazador coloca los arrays de bytes donde le cabe,
        asi que arrancar o no dependia de cuantos dibujos llevara el juego."""
        for maquina, simbolos in (
            ("atarist", ("np_tile_data", "np_tile_mask",
                         "np_pantallas", "np_hud_bitmap")),
            ("amiga", ("np_tile_data", "np_tile_mask",
                       "np_bitmap", "np_hud_bitmap")),
        ):
            out = self._construir(maquina)
            tabla = _simbolos_del_elf(os.path.join(out, "juego.elf"))
            self.assertTrue(tabla, "no se han podido leer los simbolos del ELF")
            for nombre in simbolos:
                self.assertIn(nombre, tabla, "%s: falta %s" % (maquina, nombre))
                self.assertEqual(
                    tabla[nombre] % 4, 0,
                    "%s: %s cae en 0x%08x, que no es multiplo de cuatro"
                    % (maquina, nombre, tabla[nombre]))

    def test_cartucho_de_megadrive(self):
        out = self._construir("megadrive")
        with open(os.path.join(out, "rom/juego.bin"), "rb") as fh:
            rom = fh.read()
        self.assertEqual(rom[0x100:0x110], b"SEGA MEGA DRIVE ")
        self.assertEqual(len(rom) & (len(rom) - 1), 0, "la ROM no es potencia de dos")
        self.assertGreaterEqual(len(rom), 0x20000)
        # la pila y el punto de entrada, en la tabla de vectores
        (pila, entrada) = struct.unpack_from(">II", rom, 0)
        self.assertEqual(pila, 0x00FFFE00)
        self.assertGreaterEqual(entrada, 0x200)
        self.assertLess(entrada, len(rom))
        # el fin de la ROM y la suma de control, que rellena arreglar_rom.py
        (fin, ) = struct.unpack_from(">I", rom, 0x1A4)
        self.assertEqual(fin, len(rom) - 1)
        suma = 0
        for i in range(0x200, len(rom), 2):
            suma = (suma + (rom[i] << 8) + rom[i + 1]) & 0xFFFF
        self.assertEqual(struct.unpack_from(">H", rom, 0x18E)[0], suma)

    def test_disquete_de_amiga(self):
        """El .adf construido de verdad: arranca y lleva dentro el ejecutable."""
        out = self._construir("amiga")
        ruta = os.path.join(out, "disco/Prueba.adf")
        self.assertTrue(os.path.isfile(ruta), "no se ha creado el disquete")
        with open(ruta, "rb") as fh:
            imagen = fh.read()
        self.assertEqual(len(imagen), 901120)
        self.assertEqual(imagen[0:4], b"DOS\0")
        contenido = adf.leer(imagen)
        self.assertIn("Prueba", contenido)
        self.assertIn("s/startup-sequence", contenido)
        with open(os.path.join(out, "disco/Prueba"), "rb") as fh:
            self.assertEqual(contenido["Prueba"], fh.read(),
                             "el ejecutable del disco no es el que se compilo")

    def test_disquete_de_atari_st(self):
        """El .st construido de verdad: FAT12 con el juego en la carpeta AUTO,
        que es de donde lo arranca TOS al encender."""
        out = self._construir("atarist")
        ruta = os.path.join(out, "disco/prueba.st")
        self.assertTrue(os.path.isfile(ruta), "no se ha creado el disquete")
        with open(ruta, "rb") as fh:
            imagen = fh.read()
        self.assertEqual(len(imagen), 737280)
        contenido = st_disk.leer(imagen)
        self.assertIn("AUTO/PRUEBA.PRG", contenido,
                      "el juego no esta donde TOS lo busca")
        with open(os.path.join(out, "disco/PRUEBA.PRG"), "rb") as fh:
            self.assertEqual(contenido["AUTO/PRUEBA.PRG"], fh.read(),
                             "el ejecutable del disco no es el que se compilo")

    def test_ejecutable_de_atari_st(self):
        """La cabecera de GEMDOS y la tabla de relocalizacion, que es la parte
        que se puede equivocar sin que salte nada hasta que el ST se cuelga."""
        out = self._construir("atarist")
        ruta = os.path.join(out, "disco/PRUEBA.PRG")
        with open(ruta, "rb") as fh:
            datos = fh.read()
        (magia, ) = struct.unpack_from(">H", datos, 0)
        self.assertEqual(magia, prg.MAGIA, "TOS no reconoceria esto como programa")
        texto, dato, bss, simbolos = struct.unpack_from(">IIII", datos, 2)
        self.assertEqual(dato, 0, "el enlazador lo mete todo en TEXT")
        self.assertEqual(simbolos, 0)
        self.assertEqual(texto % 4, 0, "el TEXT no acaba en palabra larga")
        self.assertGreater(bss, 64 * 1024, "faltan las dos pantallas en la BSS")
        self.assertEqual(struct.unpack_from(">H", datos, 26)[0], 0,
                         "el ejecutable dice que no trae relocalizacion")
        # la tabla: la primera correccion entera y luego un byte por cada una
        tabla = datos[28 + texto:]
        (primera, ) = struct.unpack_from(">I", tabla, 0)
        self.assertLess(primera, texto)
        sitio, correcciones = primera, 1
        for paso in tabla[4:]:
            if paso == 0:
                break
            sitio += prg.SALTO if paso == 1 else paso
            if paso != 1:
                correcciones += 1
            self.assertLessEqual(sitio + 4, texto,
                                 "una correccion cae fuera del programa")
        self.assertGreater(correcciones, 10, "casi ninguna direccion se corrige")

    def test_ejecutable_de_amiga(self):
        out = self._construir("amiga")
        ruta = os.path.join(out, "disco/Prueba")
        self.assertTrue(os.path.isfile(ruta), "no se ha creado el ejecutable")
        with open(ruta, "rb") as fh:
            datos = fh.read()
        cabecera, tabla, hunks, primero, ultimo = struct.unpack_from(">IIIII", datos, 0)
        self.assertEqual(cabecera, hunk.HUNK_HEADER)
        self.assertEqual(tabla, 0)
        self.assertEqual((hunks, primero, ultimo), (2, 0, 1))
        tamanos = struct.unpack_from(">II", datos, 20)
        for tamano in tamanos:
            self.assertTrue(tamano & hunk.HUNKF_CHIP, "los hunks van en RAM chip")
        codigo_largo = tamanos[0] & 0x3FFFFFFF
        self.assertEqual(struct.unpack_from(">I", datos, 28)[0], hunk.HUNK_CODE)
        self.assertEqual(struct.unpack_from(">I", datos, 32)[0], codigo_largo)
        codigo = datos[36:36 + codigo_largo * 4]
        # lo primero del hunk 0 es _start: llamar a main y quedarse ahi
        self.assertEqual(codigo[0:2], b"\x4e\xb9", "deberia empezar con un jsr")
        self.assertEqual(codigo[6:8], b"\x60\xfe", "y seguir con un bucle sin fin")
        # y el BSS (el mapa de bits) tiene que caber en la RAM chip de un A500
        bss = (tamanos[1] & 0x3FFFFFFF) * 4
        self.assertGreater(bss, 704 * 256 * 5 // 8)
        self.assertLess(bss + codigo_largo * 4, 512 * 1024)

    def test_ninguna_maquina_genera_accesos_impares(self):
        """Lo mismo, pero sobre los fuentes de las cinco maquinas y sin enlazar:
        asi tambien entra la Neo Geo, que se construye con ngdevkit y aqui no
        esta. El fallo lo comete el compilador, no el enlazador."""
        objdump = self.cc.replace("-gcc", "-objdump")
        if not shutil.which(objdump):
            self.skipTest("no hay %s" % objdump)
        patron = re.compile(
            r"\b(?!lea|pea)[a-z]+[wl]\s+\S*%(?:a\d|sp|fp)@\((\d+)\)")
        for sistema in ("neogeo", "megadrive", "amiga", "jaguar", "atarist", "x68000"):
            build = cargar_demo(self.proyecto, sistema)
            out = os.path.join(self.tmp, "estatico-" + sistema)
            generar_para_sistema(build, out, sistemas.obtener(sistema), "202")
            banderas = _banderas_del_makefile(os.path.join(out, "Makefile"))
            self.assertIn("-fno-store-merging", banderas,
                          "%s: falta -fno-store-merging en el Makefile" % sistema)
            impares = []
            for fuente in sorted(os.listdir(os.path.join(out, "src"))):
                if not fuente.endswith(".c"):
                    continue
                objeto = os.path.join(self.tmp, "prueba.o")
                compilar = subprocess.run(
                    [self.cc, "-m68000", "-Os", "-fomit-frame-pointer",
                     "-ffreestanding", "-fno-builtin", "-std=c99"] + banderas +
                    ["-I", os.path.join(out, "src"), "-c",
                     os.path.join(out, "src", fuente), "-o", objeto],
                    capture_output=True, text=True)
                if compilar.returncode != 0:
                    continue          # algun fuente necesita cabeceras del kit
                hecho = subprocess.run([objdump, "-d", objeto],
                                       capture_output=True, text=True)
                for linea in hecho.stdout.split("\n"):
                    for desplazamiento in patron.findall(linea):
                        if int(desplazamiento) % 2:
                            impares.append("%s/%s: %s" % (sistema, fuente, linea.strip()))
            self.assertEqual(impares, [], "\n".join(impares[:5]))

    def test_no_hay_accesos_a_direcciones_impares(self):
        """El 68000 se para con un "address error" si lee o escribe una palabra
        en una direccion impar, y gcc genera esos accesos cuando junta dos
        escrituras de un byte seguidas (por eso el kit compila con
        -fno-store-merging). Esta prueba lo comprueba en el binario ya hecho."""
        objdump = self.cc.replace("-gcc", "-objdump")
        if not shutil.which(objdump):
            self.skipTest("no hay %s" % objdump)
        # una instruccion de palabra (.w) o palabra larga (.l) sobre un registro
        # de direccion con desplazamiento: movew %d0,%a0@(2109)
        patron = re.compile(
            r"\b(?!lea|pea)[a-z]+[wl]\s+\S*%(?:a\d|sp|fp)@\((\d+)\)")
        for sistema in ("megadrive", "amiga", "atarist"):
            out = self._construir(sistema)
            hecho = subprocess.run([objdump, "-d", os.path.join(out, "juego.elf")],
                                   capture_output=True, text=True)
            self.assertEqual(hecho.returncode, 0, hecho.stderr)
            impares = []
            for linea in hecho.stdout.split("\n"):
                for desplazamiento in patron.findall(linea):
                    if int(desplazamiento) % 2:
                        impares.append(linea.strip())
            self.assertEqual(impares, [],
                             "%s: accesos a direcciones impares:\n%s"
                             % (sistema, "\n".join(impares[:5])))

    def test_no_quedan_instrucciones_de_68020(self):
        """La libgcc de un compilador de 68k para Linux esta hecha para 68020 y
        cuela instrucciones que el 68000 no tiene; el kit trae las suyas."""
        objdump = self.cc.replace("-gcc", "-objdump")
        if not shutil.which(objdump):
            self.skipTest("no hay %s" % objdump)
        for sistema in ("megadrive", "amiga", "atarist"):
            out = self._construir(sistema)
            hecho = subprocess.run([objdump, "-d", os.path.join(out, "juego.elf")],
                                   capture_output=True, text=True)
            # bsr.l (61ff) y bra.l (60ff) son del 68020; en un 68000 se ejecutan
            # como un salto a una direccion impar
            malas = [l.strip() for l in hecho.stdout.split("\n")
                     if re.search(r":\s+6[01]ff\b", l)]
            self.assertEqual(malas, [], "%s:\n%s" % (sistema, "\n".join(malas[:5])))
            for rutina in ("__mulsi3", "__divsi3", "__udivsi3", "__modsi3",
                           "__umodsi3"):
                self.assertIn(rutina, hecho.stdout,
                              "%s: falta %s (deberia venir de np_aritmetica.c)"
                              % (sistema, rutina))

    def test_la_rom_arranca_en_un_emulador(self):
        """La comprobacion que ninguna otra puede hacer: encender la consola."""
        import emulador_md
        from libretro import buscar_core
        if not buscar_core(emulador_md.CORE, "NEOPLAT_CORE_MD"):
            self.skipTest("no esta instalado el core de Genesis Plus GX")
        out = self._construir("megadrive")
        capturas = os.path.join(self.tmp, "capturas-md")
        musica, salto, _ = self._banda_sonora()
        self.assertEqual(
            emulador_md.comprobar(os.path.join(out, "rom/juego.bin"), capturas,
                                  musica, salto), 0,
            "la ROM no arranca, no se juega o no suena en el emulador")

    def test_el_disquete_arranca_en_un_emulador(self):
        """Y encender el Amiga: el disquete entero, del bootblock al ultimo
        bitplane."""
        out = self._construir("amiga")
        _comprobar_amiga(self, os.path.join(out, "disco/Prueba.adf"),
                         os.path.join(self.tmp, "capturas-amiga"), self.proyecto)

    def test_el_disquete_de_st_arranca_en_un_emulador(self):
        """Y encender el ST: el disquete entero, del FAT12 al ultimo bitplane,
        pasando por la carpeta AUTO y el teclado por interrupcion."""
        out = self._construir("atarist")
        _comprobar_st(self, os.path.join(out, "disco/prueba.st"),
                      os.path.join(self.tmp, "capturas-st"), self.proyecto)

    def test_el_juego_de_x68000_arranca_en_un_emulador(self):
        """Y encender el X68000: el .X con su tabla de correcciones, el
        disquete de Human68k, el CRTC, el chip de sprites con su capa y el
        marcador en el plano de texto.

        Hacen falta tres cosas que no son nuestras y no vienen en el
        repositorio: el core de px68k, las ROMs del X68000 y un disquete de
        arranque de Human68k. Sin ellas la prueba se salta."""
        import emulador_x68000
        from libretro import buscar_core
        if not buscar_core(emulador_x68000.CORE, "NEOPLAT_CORE_X68000"):
            self.skipTest("no esta instalado el core de px68k")
        if not emulador_x68000._buscar_roms():
            self.skipTest("no estan las ROMs del X68000 (iplrom.dat)")
        if not emulador_x68000._buscar_human68k():
            self.skipTest("no hay un disquete de Human68k (NEOPLAT_HUMAN68K)")
        out = self._construir("x68000")
        juego = [n for n in os.listdir(os.path.join(out, "disco"))
                 if n.endswith(".X")]
        self.assertTrue(juego, "el Makefile no ha dejado ningun .X en disco/")
        self.assertEqual(
            emulador_x68000.comprobar(os.path.join(out, "disco", juego[0]),
                                      os.path.join(self.tmp, "capturas-x68000")),
            0, "el juego no arranca o no se juega en el emulador de X68000")

    def test_la_neogeo_dibuja_el_juego(self):
        """La Neo Geo no se puede arrancar en un emulador normal sin la BIOS de
        SNK, asi que el kit trae su propio banco: el 68000 de verdad y el chip
        de video escrito a mano (tests/maquina_neogeo.py)."""
        import emulador_neogeo
        try:
            import machine68k  # noqa: F401
        except ImportError:
            self.skipTest("falta machine68k (pip3 install amitools)")
        # el Makefile de Neo Geo pide ngdevkit; el banco enlaza su propia ROM
        out = self._generar("neogeo")
        capturas = os.path.join(self.tmp, "capturas-neogeo")
        musica, salto, sonido = self._banda_sonora()
        self.assertEqual(
            emulador_neogeo.comprobar(out, capturas, musica, salto, sonido), 0,
                         "la ROM de Neo Geo no dibuja, no se juega o no suena")

    def test_el_cartucho_de_jaguar_arranca_en_un_emulador(self):
        """La Jaguar se puede comprobar de verdad: su emulador no necesita la
        BIOS de Atari para los cartuchos."""
        import emulador_jaguar
        from libretro import buscar_core
        if not buscar_core(emulador_jaguar.CORE, "NEOPLAT_CORE_JAGUAR"):
            self.skipTest("no esta instalado el core de Virtual Jaguar")
        out = self._construir("jaguar")
        rom = [f for f in os.listdir(os.path.join(out, "rom")) if f.endswith(".j64")]
        self.assertTrue(rom, "no se ha creado el cartucho")
        capturas = os.path.join(self.tmp, "capturas-jaguar")
        musica, salto, _ = self._banda_sonora()
        self.assertEqual(
            emulador_jaguar.comprobar(os.path.join(out, "rom", rom[0]), capturas,
                                      musica=musica, salto=salto), 0,
            "el cartucho no arranca, no se juega o no suena en el emulador")

    def test_cartucho_de_jaguar(self):
        """La consola lee la pila en cart+$400 y el punto de entrada en
        cart+$404: sin eso salta a la direccion 0 y no arranca."""
        out = self._construir("jaguar")
        rom = [f for f in os.listdir(os.path.join(out, "rom")) if f.endswith(".j64")][0]
        with open(os.path.join(out, "rom", rom), "rb") as fh:
            datos = fh.read()
        self.assertEqual(len(datos), 2 * 1024 * 1024)
        pila, entrada = struct.unpack_from(">II", datos, 0x400)
        self.assertEqual(pila, 0x001FFFFC)
        self.assertEqual(entrada, 0x00802000)
        self.assertNotEqual(datos[0x2000:0x2004], b"\x00\x00\x00\x00",
                            "no hay codigo en el punto de entrada")

    def test_las_direcciones_relocalizadas_caen_en_su_hunk(self):
        """La tabla de relocalizacion es lo que hace que el juego se pueda cargar
        en cualquier sitio: si apuntara fuera, el Amiga se colgaria."""
        out = self._construir("amiga")
        datos, info = hunk.convertir(os.path.join(out, "juego.elf"))
        self.assertGreater(info["reloc_codigo"], 0)
        self.assertGreater(info["reloc_bss"], 0)
        tamanos = [struct.unpack_from(">I", datos, 20 + i * 4)[0] & 0x3FFFFFFF
                   for i in range(2)]
        codigo = datos[36:36 + tamanos[0] * 4]
        p = 36 + tamanos[0] * 4
        self.assertEqual(struct.unpack_from(">I", datos, p)[0], hunk.HUNK_RELOC32)
        p += 4
        vistos = 0
        while True:
            (cuantos, ) = struct.unpack_from(">I", datos, p)
            p += 4
            if cuantos == 0:
                break
            (destino, ) = struct.unpack_from(">I", datos, p)
            p += 4
            for _ in range(cuantos):
                (offset, ) = struct.unpack_from(">I", datos, p)
                p += 4
                (valor, ) = struct.unpack_from(">I", codigo, offset)
                self.assertLess(valor, tamanos[destino] * 4,
                                "una direccion se sale del hunk %d" % destino)
                vistos += 1
        self.assertEqual(vistos, info["reloc_codigo"] + info["reloc_bss"])


class TestCamaraPorPantallas(unittest.TestCase):
    """La camara por pantallas, en las seis maquinas de verdad.

    La paridad C/JS ya comprueba que el motor la calcula bien, pero eso es la
    simulacion. Lo que se mira aqui es el chip de video: cuando la vista salta
    320 pixeles de golpe, cada maquina tiene que repintar la pantalla entera en
    un frame, y ahi es donde se rompen las cosas.
    """

    @classmethod
    def setUpClass(cls):
        cls.cc = _compilador_68k()
        if not cls.cc:
            raise unittest.SkipTest("no hay un compilador de 68000 instalado")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-pantallas-")
        from comun import proyecto_por_pantallas
        cls.proyecto = proyecto_por_pantallas(os.path.join(cls.tmp, "juego"))

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tmp", ""):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def _generar(self, nombre):
        build = cargar_demo(self.proyecto, nombre)
        out = os.path.join(self.tmp, nombre)
        generar_para_sistema(build, out, sistemas.obtener(nombre), "202")
        return out

    def _construir(self, nombre):
        out = self._generar(nombre)
        hecho = subprocess.run(["make", "-C", out], capture_output=True, text=True)
        self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
        return out

    def _capturas(self, nombre):
        return os.path.join(self.tmp, "capturas-" + nombre)

    def test_la_megadrive_salta_de_pantalla(self):
        import emulador_md
        from libretro import buscar_core
        if not buscar_core(emulador_md.CORE, "NEOPLAT_CORE_MD"):
            self.skipTest("no esta instalado el core de Genesis Plus GX")
        out = self._construir("megadrive")
        self.assertEqual(
            emulador_md.comprobar(os.path.join(out, "rom/juego.bin"),
                                  self._capturas("md"), pantallas=True), 0,
            "la Mega Drive no salta de pantalla como debe")

    def test_el_amiga_salta_de_pantalla(self):
        out = self._construir("amiga")
        _comprobar_amiga(self, os.path.join(out, "disco/Pantallas.adf"),
                         self._capturas("amiga"), self.proyecto, pantallas=True)

    def test_el_atari_st_salta_de_pantalla(self):
        out = self._construir("atarist")
        _comprobar_st(self, os.path.join(out, "disco/pantalla.st"),
                      self._capturas("st"), pantallas=True)

    def test_la_jaguar_salta_de_pantalla(self):
        import emulador_jaguar
        from libretro import buscar_core
        if not buscar_core(emulador_jaguar.CORE, "NEOPLAT_CORE_JAGUAR"):
            self.skipTest("no esta instalado el core de Virtual Jaguar")
        out = self._construir("jaguar")
        self.assertEqual(
            emulador_jaguar.comprobar(os.path.join(out, "rom/Pantallas.j64"),
                                      self._capturas("jaguar"), pantallas=True), 0,
            "la Jaguar no salta de pantalla como debe")

    def test_el_x68000_salta_de_pantalla(self):
        import emulador_x68000
        from libretro import buscar_core
        if not buscar_core(emulador_x68000.CORE, "NEOPLAT_CORE_X68000"):
            self.skipTest("no esta instalado el core de px68k")
        if not emulador_x68000._buscar_roms():
            self.skipTest("no estan las ROMs del X68000 (iplrom.dat)")
        if not emulador_x68000._buscar_human68k():
            self.skipTest("no hay un disquete de Human68k (NEOPLAT_HUMAN68K)")
        out = self._construir("x68000")
        juego = [n for n in os.listdir(os.path.join(out, "disco"))
                 if n.endswith(".X")]
        self.assertTrue(juego, "el Makefile no ha dejado ningun .X en disco/")
        self.assertEqual(
            emulador_x68000.comprobar(os.path.join(out, "disco", juego[0]),
                                      self._capturas("x68000"), pantallas=True),
            0, "el X68000 no salta de pantalla como debe")

    def test_la_neogeo_salta_de_pantalla_sin_pasarse_de_ciclos(self):
        """La mas exigente: el banco de Neo Geo cuenta los ciclos, y saltar de
        pantalla obliga a rehacer veinte columnas de fondo de golpe."""
        import emulador_neogeo
        try:
            import machine68k  # noqa: F401
        except ImportError:
            self.skipTest("falta machine68k (pip3 install amitools)")
        out = self._generar("neogeo")
        self.assertEqual(
            emulador_neogeo.comprobar(out, self._capturas("neogeo"),
                                      pantallas=True), 0,
            "la Neo Geo no salta de pantalla, o no le cabe en un frame")


class TestDosJugadores(unittest.TestCase):
    """Con `jugadores: 2`, el segundo mando en las cinco maquinas de verdad.

    La paridad C/JS ya comprueba que el motor lleva bien a los dos jugadores,
    pero eso es la simulacion. Lo que se mira aqui es el otro extremo: que el
    segundo mando de cada maquina (el puerto 2 de la Neo Geo, el otro conector
    de la Mega Drive, el puerto del raton en el Amiga y en el ST, la otra
    mitad de la matriz en la Jaguar) llega de verdad al segundo jugador y no
    es el primero leido dos veces. Como se comprueba, en dos_jugadores.py.
    """

    @classmethod
    def setUpClass(cls):
        cls.cc = _compilador_68k()
        if not cls.cc:
            raise unittest.SkipTest("no hay un compilador de 68000 instalado")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-dos-")
        from comun import proyecto_a_dos
        cls.proyecto = proyecto_a_dos(os.path.join(cls.tmp, "juego"))

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tmp", ""):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def _generar(self, nombre):
        build = cargar_demo(self.proyecto, nombre)
        out = os.path.join(self.tmp, nombre)
        generar_para_sistema(build, out, sistemas.obtener(nombre), "202")
        return out

    def _construir(self, nombre):
        out = self._generar(nombre)
        hecho = subprocess.run(["make", "-C", out], capture_output=True, text=True)
        self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
        return out

    def _capturas(self):
        return os.path.join(self.tmp, "capturas")

    def _mirar(self, sistema, ruta):
        import dos_jugadores
        self.assertEqual(dos_jugadores.comprobar_maquina(sistema, ruta,
                                                         self._capturas()), 0,
                         "el segundo mando no llega al segundo jugador")

    def test_los_dos_mandos_de_la_neogeo(self):
        try:
            import machine68k  # noqa: F401
        except ImportError:
            self.skipTest("falta machine68k (pip3 install amitools)")
        self._mirar("neogeo", self._generar("neogeo"))

    def test_los_dos_mandos_de_la_megadrive(self):
        self._mirar("megadrive",
                    os.path.join(self._construir("megadrive"), "rom/juego.bin"))

    def test_los_dos_mandos_del_amiga(self):
        self._mirar("amiga",
                    os.path.join(self._construir("amiga"), "disco/Dos.adf"))

    def test_los_dos_mandos_de_la_jaguar(self):
        self._mirar("jaguar",
                    os.path.join(self._construir("jaguar"), "rom/Dos.j64"))

    def test_los_dos_mandos_del_atari_st(self):
        """En un proceso aparte: Hatari no se deja arrancar dos veces en el
        mismo, y aqui hay mas de una prueba que lo usa."""
        import emulador_st
        from libretro import buscar_core
        if not buscar_core(emulador_st.CORE, "NEOPLAT_CORE_ST"):
            self.skipTest("no esta instalado el core de Hatari")
        if not emulador_st._buscar_tos():
            self.skipTest("no hay una imagen de TOS (tos.img)")
        disco = os.path.join(self._construir("atarist"), "disco/dos.st")
        hecho = subprocess.run(
            [sys.executable, os.path.join(KIT, "tests", "dos_jugadores.py"),
             "atarist", disco, self._capturas()],
            capture_output=True, text=True)
        print(hecho.stdout.strip())
        self.assertEqual(hecho.returncode, 0,
                         "el segundo mando no llega al segundo jugador:\n"
                         + hecho.stdout + hecho.stderr)


class TestMuestras(unittest.TestCase):
    """Las muestras digitales, oidas en un emulador de verdad.

    El proyecto de prueba pone como efecto de salto un tono puro a 3000 Hz y
    **sin notas de recambio**: si la maquina no tocara la muestra, al saltar no
    sonaria nada ahi. Como se mide, en muestras.py.
    """

    @classmethod
    def setUpClass(cls):
        cls.cc = _compilador_68k()
        if not cls.cc:
            raise unittest.SkipTest("no hay un compilador de 68000 instalado")
        cls.tmp = tempfile.mkdtemp(prefix="neoplat-pcm-")
        from comun import proyecto_con_muestra
        cls.proyecto = proyecto_con_muestra(os.path.join(cls.tmp, "juego"))

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tmp", ""):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def _generar(self, nombre):
        build = cargar_demo(self.proyecto, nombre)
        out = os.path.join(self.tmp, nombre)
        generar_para_sistema(build, out, sistemas.obtener(nombre), "202")
        return out

    def _construir(self, nombre):
        out = self._generar(nombre)
        hecho = subprocess.run(["make", "-C", out], capture_output=True, text=True)
        self.assertEqual(hecho.returncode, 0, hecho.stdout + hecho.stderr)
        return out

    def _escuchar(self, sistema, ruta, sonido=False):
        import muestras
        self.assertEqual(muestras.comprobar_maquina(sistema, ruta, sonido), 0,
                         "la muestra digital no suena")

    def test_la_neogeo_toca_la_muestra(self):
        """El YM2610 lee las muestras el solo de la ROM V1, en ADPCM-A. El
        banco del kit las descifra para poder oirlas."""
        try:
            import machine68k  # noqa: F401
        except ImportError:
            self.skipTest("falta machine68k (pip3 install amitools)")
        from ngplat.project import load_project
        sonido = load_project(os.path.join(self.proyecto, "game.yaml")).sound
        self._escuchar("neogeo", self._generar("neogeo"), sonido)

    def _rom(self, sistema, carpeta, extension):
        ruta = os.path.join(self._construir(sistema), carpeta)
        salida = [f for f in os.listdir(ruta) if f.endswith(extension)]
        self.assertTrue(salida, "no se ha construido nada en " + carpeta)
        return os.path.join(ruta, salida[0])

    def test_la_megadrive_toca_la_muestra(self):
        """El DAC esta en el YM2612 y hay que darle un byte cada 125
        microsegundos: eso lo hace el Z80, con su propio driver."""
        self._escuchar("megadrive",
                       os.path.join(self._construir("megadrive"), "rom/juego.bin"))

    def test_la_jaguar_toca_la_muestra(self):
        """El DSP lee el sonido del cartucho, un byte por muestra de audio, y
        lo suma a las ondas cuadradas antes de mandarlo a los DAC."""
        self._escuchar("jaguar", self._rom("jaguar", "rom", ".j64"))

    def test_el_amiga_toca_la_muestra(self):
        """Paula lee el sonido de la RAM chip por DMA, igual que lee la onda
        cuadrada de las notas: para ella una muestra no es un caso aparte."""
        self._escuchar("amiga", self._rom("amiga", "disco", ".adf"))


if __name__ == "__main__":
    unittest.main()
