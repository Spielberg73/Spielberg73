"""El CD del Amiga CD32: que la imagen sea un ISO 9660 de verdad.

Un disquete se puede mirar a ojo en un emulador; un CD que no arranca no dice
por que. Asi que aqui se abre la imagen y se lee **con la norma en la mano**:
el descriptor, la tabla de caminos, el directorio raiz y los ficheros. Y sobre
todo la entrada `TM`, que es lo unico que separa un CD cualquiera de uno que un
CD32 reconoce como suyo.
"""

import os
import struct
import tempfile
import unittest

import comun  # noqa: F401  (pone tools/ en el path)

from ngplat import iso

SECTOR = iso.SECTOR


def _pvd(imagen: bytes) -> bytes:
    """El descriptor principal, que vive en el sector 16."""
    return imagen[16 * SECTOR:17 * SECTOR]


def _entradas(imagen: bytes, sector: int, tamano: int):
    """Las entradas de un directorio, leidas segun la norma: cada una dice lo
    que ocupa en su primer byte, y un cero quiere decir 'aqui se acabo'."""
    datos = imagen[sector * SECTOR:sector * SECTOR + tamano]
    fuera = []
    i = 0
    while i < len(datos):
        largo = datos[i]
        if largo == 0:
            break
        registro = datos[i:i + largo]
        extension = struct.unpack("<I", registro[2:6])[0]
        mide = struct.unpack("<I", registro[10:14])[0]
        banderas = registro[25]
        nombre = registro[33:33 + registro[32]]
        fuera.append((nombre, extension, mide, bool(banderas & 0x02)))
        i += largo
    return fuera


def _un_cd(marca: bytes = b"") -> bytes:
    disco = iso.Disco("BOSQUE MAGICO")
    disco.fichero("BosqueMagico", b"HUNK" * 1000)
    carpeta = disco.carpeta("S")
    disco.fichero("Startup-Sequence", b"BosqueMagico\n", carpeta)
    return disco.bytes(marca)


class TestFormaDelCd(unittest.TestCase):
    def setUp(self):
        self.imagen = _un_cd()

    def test_mide_sectores_enteros(self):
        self.assertEqual(len(self.imagen) % SECTOR, 0)

    def test_los_dieciseis_primeros_sectores_van_en_blanco(self):
        """La zona de sistema. En un PC es donde va el arranque; en un Amiga no
        se usa, pero tiene que estar."""
        self.assertEqual(self.imagen[:16 * SECTOR], b"\x00" * (16 * SECTOR))

    def test_el_descriptor_es_un_iso9660(self):
        pvd = _pvd(self.imagen)
        self.assertEqual(pvd[0], 1, "el tipo de descriptor tiene que ser 1")
        self.assertEqual(pvd[1:6], b"CD001")
        self.assertEqual(pvd[6], 1, "la version del descriptor")
        self.assertEqual(pvd[881], 1, "la version de la estructura")

    def test_dice_que_es_un_cd_de_amiga(self):
        """El identificador de sistema es lo que mira la Kickstart para saber
        que el CD es suyo. Los dos, CDTV y CD32, usan el mismo."""
        self.assertEqual(_pvd(self.imagen)[8:40].rstrip(), b"CDTV")

    def test_lleva_la_etiqueta_del_juego(self):
        self.assertEqual(_pvd(self.imagen)[40:72].rstrip(), b"BOSQUE MAGICO")

    def test_el_tamano_que_dice_es_el_que_mide(self):
        """Un CD que miente sobre su tamano se lee mal en la mitad de los
        lectores, y en el Amiga no se lee."""
        sectores = struct.unpack("<I", _pvd(self.imagen)[80:84])[0]
        self.assertEqual(sectores * SECTOR, len(self.imagen))
        # y el mismo numero, otra vez, en big endian (asi lo pide la norma)
        self.assertEqual(struct.unpack(">I", _pvd(self.imagen)[84:88])[0],
                         sectores)

    def test_el_sector_mide_2048_bytes(self):
        self.assertEqual(struct.unpack("<H", _pvd(self.imagen)[128:130])[0],
                         SECTOR)

    def test_el_cierre_del_juego_de_descriptores(self):
        """Detras de los descriptores va uno de cierre, o el lector sigue
        buscando."""
        cierre = self.imagen[18 * SECTOR:19 * SECTOR]
        self.assertEqual(cierre[0], 0xFF)
        self.assertEqual(cierre[1:6], b"CD001")

    def test_hay_tabla_de_caminos_en_los_dos_ordenes(self):
        """El Amiga lee la de big endian y todo lo demas la de little endian.
        Las dos tienen que decir lo mismo."""
        pvd = _pvd(self.imagen)
        pequena = struct.unpack("<I", pvd[140:144])[0]
        grande = struct.unpack(">I", pvd[148:152])[0]
        self.assertNotEqual(pequena, grande, "son dos tablas, no una")
        tamano = struct.unpack("<I", pvd[132:136])[0]
        cruda_g = self.imagen[grande * SECTOR:grande * SECTOR + tamano]
        cruda_p = self.imagen[pequena * SECTOR:pequena * SECTOR + tamano]
        # la raiz: nombre de un byte a cero, y de padre ella misma
        self.assertEqual(cruda_g[0], 1)
        self.assertEqual(cruda_p[0], 1)
        raiz_g = struct.unpack(">I", cruda_g[2:6])[0]
        raiz_p = struct.unpack("<I", cruda_p[2:6])[0]
        self.assertEqual(raiz_g, raiz_p, "las dos tablas no dicen lo mismo")

    def test_la_raiz_trae_el_juego_y_la_carpeta_s(self):
        pvd = _pvd(self.imagen)
        raiz = pvd[156:190]
        sector = struct.unpack("<I", raiz[2:6])[0]
        tamano = struct.unpack("<I", raiz[10:14])[0]
        entradas = _entradas(self.imagen, sector, tamano)
        nombres = [n for (n, _, _, _) in entradas]
        self.assertIn(b"\x00", nombres, "falta la entrada de si misma")
        self.assertIn(b"\x01", nombres, "falta la entrada del padre")
        self.assertIn(b"BosqueMagico;1", nombres)
        self.assertIn(b"S", nombres)

    def test_el_ejecutable_esta_donde_dice_y_entero(self):
        pvd = _pvd(self.imagen)
        raiz = pvd[156:190]
        entradas = _entradas(self.imagen,
                             struct.unpack("<I", raiz[2:6])[0],
                             struct.unpack("<I", raiz[10:14])[0])
        for nombre, sector, mide, carpeta in entradas:
            if nombre == b"BosqueMagico;1":
                self.assertFalse(carpeta)
                self.assertEqual(mide, 4000)
                trozo = self.imagen[sector * SECTOR:sector * SECTOR + mide]
                self.assertEqual(trozo, b"HUNK" * 1000)
                break
        else:
            self.fail("el ejecutable no sale en la raiz")

    def test_la_carpeta_s_trae_el_arranque(self):
        """`S/Startup-Sequence` es lo que ejecuta la Kickstart al arrancar: si
        no esta, el CD arranca y se queda mirando."""
        pvd = _pvd(self.imagen)
        raiz = pvd[156:190]
        entradas = _entradas(self.imagen,
                             struct.unpack("<I", raiz[2:6])[0],
                             struct.unpack("<I", raiz[10:14])[0])
        carpeta = [e for e in entradas if e[0] == b"S"][0]
        dentro = _entradas(self.imagen, carpeta[1], carpeta[2])
        nombres = [n for (n, _, _, _) in dentro]
        self.assertIn(b"Startup-Sequence;1", nombres)
        for nombre, sector, mide, _ in dentro:
            if nombre == b"Startup-Sequence;1":
                texto = self.imagen[sector * SECTOR:sector * SECTOR + mide]
                self.assertIn(b"BosqueMagico", texto,
                              "el arranque no llama al juego")

    def test_dos_veces_da_el_mismo_cd(self):
        """Las fechas son fijas a proposito: compilar dos veces tiene que dar
        el mismo archivo byte a byte, o no hay forma de comparar nada."""
        self.assertEqual(_un_cd(), _un_cd())


class TestLaMarcaDelCd32(unittest.TestCase):
    """Los 2048 bytes de Commodore sin los cuales un CD32 no arranca el disco.

    No se reparten con el kit, asi que estas pruebas usan un relleno del mismo
    tamano: lo que se comprueba es **donde va y como se apunta**, que es lo que
    escribe NeoPlat."""

    def setUp(self):
        self.marca = bytes(range(256)) * 8
        self.imagen = _un_cd(self.marca)

    def _entrada_tm(self, imagen):
        uso = _pvd(imagen)[883:883 + 13]
        if uso[1:3] != b"TM":
            return None
        etiqueta, tamano, sector = struct.unpack(">HII", uso[3:13])
        return etiqueta, tamano, sector

    def test_sin_marca_no_hay_entrada(self):
        """Y el CD sigue siendo valido: se lee en cualquier ordenador, solo que
        el CD32 no lo arranca solo."""
        self.assertIsNone(self._entrada_tm(_un_cd()))

    def test_la_entrada_dice_donde_esta_y_cuanto_ocupa(self):
        etiqueta, tamano, sector = self._entrada_tm(self.imagen)
        self.assertEqual(etiqueta, 0x0014)
        self.assertEqual(tamano, len(self.marca))
        self.assertEqual(
            self.imagen[sector * SECTOR:sector * SECTOR + tamano], self.marca,
            "la entrada TM apunta a un sitio donde no esta la marca")

    def test_la_entrada_va_en_big_endian(self):
        """El que la lee es un 68000: si los numeros fueran al reves, el CD32
        buscaria la marca en el sector 134217728."""
        uso = _pvd(self.imagen)[883:896]
        self.assertEqual(uso[0], 0, "la zona empieza por un cero")
        self.assertEqual(uso[3:5], b"\x00\x14")
        sector = struct.unpack(">I", uso[9:13])[0]
        self.assertLess(sector, len(self.imagen) // SECTOR)

    def test_la_marca_no_pisa_los_ficheros(self):
        """Va entre las tablas de caminos y los directorios: si se solapara con
        algo, el CD arrancaria y el juego no estaria."""
        _, tamano, sector = self._entrada_tm(self.imagen)
        pvd = _pvd(self.imagen)
        raiz_sector = struct.unpack("<I", pvd[156:190][2:6])[0]
        self.assertLess(sector, raiz_sector)
        self.assertLessEqual(sector + (tamano + SECTOR - 1) // SECTOR,
                             raiz_sector)


class TestComprobarLaMarca(unittest.TestCase):
    """Un archivo equivocado tiene que dar un error claro y no un CD mudo."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="neoplat-tm-")

    def _archivo(self, datos):
        ruta = os.path.join(self.tmp, "CD32.TM")
        with open(ruta, "wb") as fh:
            fh.write(datos)
        return ruta

    def test_el_tamano_tiene_que_ser_el_de_un_sector(self):
        with self.assertRaises(iso.ErrorIso) as error:
            iso.leer_marca(self._archivo(b"\x00" * 1024))
        self.assertIn("2048", str(error.exception))

    def test_la_huella_tiene_que_cuadrar(self):
        """Del tamano justo pero no es: el CDTV.TM renombrado, por ejemplo."""
        with self.assertRaises(iso.ErrorIso) as error:
            iso.leer_marca(self._archivo(b"\x00" * iso.MARCA_TAMANO))
        self.assertIn("marca del CD32", str(error.exception))

    def test_si_no_esta_lo_dice(self):
        with self.assertRaises(iso.ErrorIso):
            iso.leer_marca(os.path.join(self.tmp, "no-existe.TM"))


class TestConUnaLibreriaDeVerdad(unittest.TestCase):
    """Y por si nos hemos leido mal la norma, la misma imagen abierta con una
    libreria de ISO 9660 que no es nuestra. Si no esta instalada, se salta."""

    def setUp(self):
        try:
            import pycdlib  # noqa: F401
        except ImportError:
            self.skipTest("pycdlib no esta instalado")

    def test_una_libreria_ajena_lee_el_cd(self):
        import io as _io
        import pycdlib
        tmp = tempfile.mkdtemp(prefix="neoplat-iso-")
        ruta = os.path.join(tmp, "juego.iso")
        with open(ruta, "wb") as fh:
            fh.write(_un_cd())
        cd = pycdlib.PyCdlib()
        cd.open(ruta)
        try:
            self.assertEqual(cd.pvd.system_identifier.decode().strip(), "CDTV")
            buf = _io.BytesIO()
            cd.get_file_from_iso_fp(buf, iso_path="/S/Startup-Sequence;1")
            self.assertIn(b"BosqueMagico", buf.getvalue())
        finally:
            cd.close()


if __name__ == "__main__":
    unittest.main()
