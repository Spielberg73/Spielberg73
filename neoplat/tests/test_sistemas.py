"""Las tres maquinas: conversion de graficos, generacion y compilacion real.

Lo que se comprueba aqui es que el mismo juego sale bien para Neo Geo, Mega
Drive y Amiga: los graficos se convierten sin perder informacion, el proyecto
generado trae lo que tiene que traer y, si hay un compilador de 68000 a mano,
el cartucho y el ejecutable se construyen de verdad y tienen la pinta que
espera cada maquina.
"""

import os
import shutil
import struct
import subprocess
import tempfile
import unittest

import comun
from comun import cargar_demo

from ngplat import gfx, gfx_amiga, gfx_md, hunk, sistemas
from ngplat.codegen import generar_para_sistema
from ngplat.errors import ProjectError
from ngplat.gfx import Palette
from ngplat.sonido import periodo_paula, periodo_psg


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
        for nombre in ("neogeo", "megadrive", "amiga"):
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
                        "amiga.ld", "Makefile", "hacer_ejecutable.py"):
            self.assertTrue(os.path.isfile(os.path.join(out, archivo)), archivo)
        with open(os.path.join(out, "src/graficos.c"), encoding="utf-8") as fh:
            texto = fh.read()
        self.assertIn("np_tile_data", texto)
        self.assertIn("np_tile_mask", texto)
        self.assertIn("np_colores[32]", texto)

    def test_los_tres_sistemas_describen_el_mismo_juego(self):
        """Cambiar de maquina no cambia el juego: niveles, enemigos y mapas."""
        referencia = None
        for nombre in ("neogeo", "megadrive", "amiga"):
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

    def _construir(self, nombre):
        build = cargar_demo(self.proyecto, nombre)
        out = os.path.join(self.tmp, nombre)
        generar_para_sistema(build, out, sistemas.obtener(nombre), "202")
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


if __name__ == "__main__":
    unittest.main()
