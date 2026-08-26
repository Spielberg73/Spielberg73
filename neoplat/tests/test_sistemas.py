"""Las tres maquinas: conversion de graficos, generacion y compilacion real.

Lo que se comprueba aqui es que el mismo juego sale bien para Neo Geo, Mega
Drive y Amiga: los graficos se convierten sin perder informacion, el proyecto
generado trae lo que tiene que traer y, si hay un compilador de 68000 a mano,
el cartucho y el ejecutable se construyen de verdad y tienen la pinta que
espera cada maquina.
"""

import os
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

import comun
from comun import cargar_demo

from ngplat import adf, gfx, gfx_amiga, gfx_md, hunk, sistemas
from ngplat.codegen import generar_para_sistema
from ngplat.errors import ProjectError
from ngplat.gfx import Palette
from ngplat.sonido import periodo_paula, periodo_psg


def _banderas_del_makefile(ruta):
    """Las opciones del compilador que importan para esta comprobacion."""
    with open(ruta, encoding="utf-8") as fh:
        texto = fh.read()
    return [b for b in ("-fno-store-merging",) if b in texto]


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
        for nombre in ("neogeo", "megadrive", "amiga", "jaguar"):
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

    def test_los_sistemas_describen_el_mismo_juego(self):
        """Cambiar de maquina no cambia el juego: niveles, enemigos y mapas."""
        referencia = None
        for nombre in ("neogeo", "megadrive", "amiga", "jaguar"):
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
        """Lo mismo, pero sobre los fuentes de las cuatro maquinas y sin enlazar:
        asi tambien entra la Neo Geo, que se construye con ngdevkit y aqui no
        esta. El fallo lo comete el compilador, no el enlazador."""
        objdump = self.cc.replace("-gcc", "-objdump")
        if not shutil.which(objdump):
            self.skipTest("no hay %s" % objdump)
        patron = re.compile(
            r"\b(?!lea|pea)[a-z]+[wl]\s+\S*%(?:a\d|sp|fp)@\((\d+)\)")
        for sistema in ("neogeo", "megadrive", "amiga", "jaguar"):
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
        for sistema in ("megadrive", "amiga"):
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
        for sistema in ("megadrive", "amiga"):
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
        import emulador_amiga
        from libretro import buscar_core
        if not buscar_core(emulador_amiga.CORE, "NEOPLAT_CORE_AMIGA"):
            self.skipTest("no esta instalado el core de PUAE")
        out = self._construir("amiga")
        capturas = os.path.join(self.tmp, "capturas-amiga")
        musica, salto, _ = self._banda_sonora()
        self.assertEqual(
            emulador_amiga.comprobar(os.path.join(out, "disco/Prueba.adf"),
                                     capturas, musica, salto), 0,
            "el disquete no arranca, no se juega o no suena en el emulador")

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
        self.assertEqual(
            emulador_jaguar.comprobar(os.path.join(out, "rom", rom[0]), capturas), 0,
            "el cartucho no arranca o no se juega en el emulador")

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
    """La camara por pantallas, en las cuatro maquinas de verdad.

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
        import emulador_amiga
        from libretro import buscar_core
        if not buscar_core(emulador_amiga.CORE, "NEOPLAT_CORE_AMIGA"):
            self.skipTest("no esta instalado el core de PUAE")
        out = self._construir("amiga")
        self.assertEqual(
            emulador_amiga.comprobar(os.path.join(out, "disco/Pantallas.adf"),
                                     self._capturas("amiga"), pantallas=True), 0,
            "el Amiga no salta de pantalla como debe")

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


if __name__ == "__main__":
    unittest.main()
