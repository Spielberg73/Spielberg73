#!/usr/bin/env python3
"""Monta un CD de Amiga CD32 (.iso) arrancable, sin necesitar nada instalado.

Un CD32 es un Amiga 1200 con lector de CD y sin teclado ni disquetera, asi que
el juego es exactamente el mismo -el ejecutable AGA que ya hace `amiga1200`- y
lo unico que cambia es **el envase**: en vez de un disquete de 880 KB, un ISO
9660 que la maquina arranca sola.

Como arranca un CD en un CD32
-----------------------------

La Kickstart del CD32 lleva dentro el sistema de ficheros de CD, asi que
arrancar un CD es igual que arrancar un disquete: monta CD0: y ejecuta
`S/Startup-Sequence`. Lo que decide si ese CD es suyo son dos cosas del
descriptor principal:

  1. el **identificador de sistema** dice "CDTV" (los dos, CDTV y CD32, usan
     el mismo; lo que los distingue es lo de abajo);
  2. en la zona de "uso de la aplicacion" del descriptor van las opciones del
     sistema de ficheros de Amiga, y entre ellas una entrada `TM` que dice
     donde esta y cuanto ocupa el **fichero de marca** (CD32.TM): dos letras,
     un 0x0014 y dos numeros de 32 bits, todo en big endian.

El fichero de marca son 2048 bytes de Commodore -un sector- y **no se puede
repartir**: es suyo, viene en el Developer CD y hace que el CD32 arranque en
modo AGA. Aqui se le pone al lado si lo tienes (`--marca CD32.TM`) y, si no, el
ISO sale igual de valido y de legible pero **no arranca solo**: se avisa por la
salida, que es lo honrado.

La forma del disco, sector a sector (la misma que usa ISOCD, que es la
herramienta con la que se hicieron los CD32 de verdad):

    0-15    zona de sistema, a ceros
    16      descriptor principal (PVD), con las opciones del sistema de
            ficheros y, si la hay, la entrada `TM`
    17      el mismo descriptor otra vez
    18      cierre del juego de descriptores
    19      tabla de caminos en big endian (la que lee el Amiga)
    ...     la misma en little endian (la que leen los demas)
    ...     el fichero de marca, si lo hay
    ...     los directorios y los ficheros
    +32     sectores de relleno al final

El ISO sale siempre igual byte a byte (las fechas son fijas), asi que dos
compilaciones del mismo juego dan el mismo CD.

    python3 iso.py disco.iso "BOSQUE" BosqueMagico juego.exe [CD32.TM]
"""

from __future__ import annotations

import hashlib
import struct
import sys
from typing import Dict, List, Optional, Tuple

SECTOR = 2048
ZONA_SISTEMA = 16              # sectores en blanco antes del primer descriptor
RELLENO_FINAL = 32             # sectores de cortesia al final de la imagen

# El identificador de sistema que hace que un Amiga reconozca el CD como suyo.
# Es "CDTV" tambien en los CD32: lo que separa a uno de otro es el fichero de
# marca al que apunta la entrada TM.
SISTEMA = "CDTV"

# El fichero de marca del CD32: un sector clavado, y con esta huella. Se
# comprueba para que un archivo equivocado -el del CDTV, que mide 22152 bytes,
# o un renombrado cualquiera- de un error claro en vez de un CD que no arranca
# y no dice por que.
MARCA_TAMANO = 2048
MARCA_SHA1 = "c5ffcef2a5e33d2df606185823cd95d1c174d65f"

# La fecha que va en todo el disco. Fija a proposito: asi el ISO es reproducible
# y dos compilaciones iguales dan el mismo archivo.
FECHA = (1993, 9, 17, 0, 0, 0)      # el CD32 se presento en septiembre de 1993


class ErrorIso(Exception):
    """Algo que impide montar el CD, con el motivo escrito para el usuario."""


def _ambos(valor: int) -> bytes:
    """Un entero de 32 bits **en los dos ordenes**, como pide ISO 9660: primero
    little endian y detras big endian. El Amiga lee el segundo."""
    return struct.pack("<I", valor) + struct.pack(">I", valor)


def _ambos16(valor: int) -> bytes:
    return struct.pack("<H", valor) + struct.pack(">H", valor)


def _fecha_larga() -> bytes:
    """Las fechas del descriptor: 16 digitos en texto y un byte de huso."""
    texto = "%04d%02d%02d%02d%02d%02d00" % FECHA
    return texto.encode("ascii") + b"\x00"


def _fecha_corta() -> bytes:
    """Y la de cada entrada de directorio: siete bytes."""
    ano, mes, dia, hora, minuto, segundo = FECHA
    return struct.pack("BBBBBBb", ano - 1900, mes, dia, hora, minuto, segundo, 0)


def _texto(valor: str, ancho: int) -> bytes:
    """Un campo de texto del descriptor, rellenado con espacios."""
    return valor.encode("ascii", "replace")[:ancho].ljust(ancho, b" ")


def _sectores(tamano: int) -> int:
    """Cuantos sectores ocupa algo. Un fichero vacio ocupa uno igual."""
    return max(1, (tamano + SECTOR - 1) // SECTOR)


def _alinear(datos: bytes) -> bytes:
    sobra = len(datos) % SECTOR
    return datos + b"\x00" * (SECTOR - sobra) if sobra else datos


class _Nodo:
    """Un fichero o una carpeta del CD, antes de saber donde va a caer."""

    def __init__(self, nombre: str, datos: Optional[bytes], padre):
        self.nombre = nombre
        self.datos = datos                  # None en las carpetas
        self.padre = padre
        self.hijos: List["_Nodo"] = []
        self.sector = 0
        self.tamano = 0 if datos is None else len(datos)
        self.numero = 0                     # el suyo en la tabla de caminos

    @property
    def carpeta(self) -> bool:
        return self.datos is None

    @property
    def identificador(self) -> bytes:
        """Como se escribe el nombre dentro del CD. Los ficheros llevan `;1`
        detras -el numero de version de ISO 9660, que el Amiga se come sin
        rechistar- y las carpetas van tal cual."""
        nombre = self.nombre if self.carpeta else self.nombre + ";1"
        return nombre.encode("ascii", "replace")


def _registro(nodo: Optional[_Nodo], sector: int, tamano: int,
              identificador: bytes, carpeta: bool) -> bytes:
    """Una entrada de directorio de ISO 9660: 33 bytes fijos, el nombre y un
    byte de relleno si el nombre mide un numero par."""
    del nodo
    largo = 33 + len(identificador)
    if largo % 2:
        largo += 1
    registro = bytearray()
    registro.append(largo)
    registro.append(0)                          # sin atributos extendidos
    registro += _ambos(sector)
    registro += _ambos(tamano)
    registro += _fecha_corta()
    registro.append(0x02 if carpeta else 0x00)  # banderas
    registro.append(0)                          # tamano de unidad
    registro.append(0)                          # hueco de entrelazado
    registro += _ambos16(1)                     # numero de volumen
    registro.append(len(identificador))
    registro += identificador
    if len(registro) < largo:
        registro.append(0)
    assert len(registro) == largo
    return bytes(registro)


class Disco:
    """El CD que se esta montando: carpetas, ficheros y, al final, la imagen."""

    def __init__(self, etiqueta: str):
        self.etiqueta = etiqueta.upper()[:32]
        self.raiz = _Nodo("\x00", None, None)

    # --- lo que se le mete dentro ---------------------------------------

    def carpeta(self, nombre: str, padre: Optional[_Nodo] = None) -> _Nodo:
        nodo = _Nodo(nombre, None, padre or self.raiz)
        nodo.padre.hijos.append(nodo)
        return nodo

    def fichero(self, nombre: str, datos: bytes,
                padre: Optional[_Nodo] = None) -> _Nodo:
        nodo = _Nodo(nombre, datos, padre or self.raiz)
        nodo.padre.hijos.append(nodo)
        return nodo

    # --- y como se convierte en un CD ------------------------------------

    def _carpetas(self) -> List[_Nodo]:
        """Las carpetas en anchura, que es el orden que pide la tabla de
        caminos: primero la raiz, luego las suyas, luego las de esas."""
        fuera = [self.raiz]
        i = 0
        while i < len(fuera):
            for hijo in sorted(fuera[i].hijos, key=lambda n: n.nombre.upper()):
                if hijo.carpeta:
                    fuera.append(hijo)
            i += 1
        for numero, carpeta in enumerate(fuera, start=1):
            carpeta.numero = numero
        return fuera

    def _tabla_de_caminos(self, carpetas: List[_Nodo], grande: bool) -> bytes:
        """La tabla de caminos: una entrada por carpeta, con donde empieza y de
        quien cuelga. Va dos veces en el CD, una en cada orden de bytes."""
        fuera = bytearray()
        for carpeta in carpetas:
            nombre = b"\x00" if carpeta is self.raiz else carpeta.identificador
            fuera.append(len(nombre))
            fuera.append(0)                     # sin atributos extendidos
            fuera += struct.pack(">I" if grande else "<I", carpeta.sector)
            padre = 1 if carpeta is self.raiz else carpeta.padre.numero
            fuera += struct.pack(">H" if grande else "<H", padre)
            fuera += nombre
            if len(nombre) % 2:
                fuera.append(0)
        return bytes(fuera)

    def _extension_de(self, carpeta: _Nodo) -> bytes:
        """El contenido de una carpeta: la entrada de si misma, la de su padre
        y una por cada hijo."""
        padre = carpeta.padre or carpeta
        fuera = bytearray()
        fuera += _registro(carpeta, carpeta.sector, carpeta.tamano,
                           b"\x00", True)
        fuera += _registro(padre, padre.sector, padre.tamano, b"\x01", True)
        for hijo in sorted(carpeta.hijos, key=lambda n: n.identificador.upper()):
            fuera += _registro(hijo, hijo.sector, hijo.tamano,
                               hijo.identificador, hijo.carpeta)
        return bytes(fuera)

    def _descriptor(self, sectores_totales: int, tabla: int,
                    tabla_grande: int, tabla_pequena: int,
                    marca: int, marca_sector: int) -> bytes:
        """El descriptor principal (PVD), que es la portada del CD: como se
        llama, cuanto ocupa, donde esta la raiz y -lo que importa aqui- las
        opciones del sistema de ficheros de Amiga con la entrada `TM`."""
        d = bytearray(SECTOR)
        d[0] = 1                                        # descriptor principal
        d[1:6] = b"CD001"
        d[6] = 1                                        # version
        d[8:40] = _texto(SISTEMA, 32)
        d[40:72] = _texto(self.etiqueta, 32)
        d[80:88] = _ambos(sectores_totales)
        d[120:124] = _ambos16(1)                        # volumenes del juego
        d[124:128] = _ambos16(1)                        # este es el primero
        d[128:132] = _ambos16(SECTOR)                   # bytes por sector
        d[132:140] = _ambos(tabla)                      # lo que ocupa la tabla
        d[140:144] = struct.pack("<I", tabla_pequena)   # tabla en little endian
        d[148:152] = struct.pack(">I", tabla_grande)    # y en big endian
        d[156:190] = _registro(self.raiz, self.raiz.sector, self.raiz.tamano,
                               b"\x00", True)
        d[190:318] = _texto("", 128)                    # juego de volumenes
        d[318:446] = _texto("", 128)                    # editor
        d[446:574] = _texto("NEOPLAT", 128)             # quien lo ha preparado
        d[574:702] = _texto("NEOPLAT", 128)             # la aplicacion
        d[702:739] = _texto("", 37)
        d[739:776] = _texto("", 37)
        d[776:813] = _texto("", 37)
        d[813:830] = _fecha_larga()                     # creacion
        d[830:847] = _fecha_larga()                     # modificacion
        d[847:864] = b"0" * 16 + b"\x00"                # sin caducidad
        d[864:881] = _fecha_larga()                     # desde cuando vale
        d[881] = 1                                      # version de estructura
        # La zona de "uso de la aplicacion": las opciones del sistema de
        # ficheros del Amiga. Empieza por un cero y, si hay marca, lleva la
        # entrada que dice donde esta: dos letras, un 0x0014 y dos numeros de
        # 32 bits, todo en big endian. Es lo que hace que el CD32 arranque.
        opciones = bytearray(b"\x00")
        if marca:
            opciones += b"TM" + struct.pack(">HII", 0x0014, marca, marca_sector)
        d[883:883 + len(opciones)] = opciones
        return bytes(d)

    def bytes(self, marca: bytes = b"") -> bytes:
        carpetas = self._carpetas()
        ficheros = [n for c in carpetas for n in c.hijos if not n.carpeta]

        # 1. lo que ocupa la tabla de caminos, que hace falta antes de saber
        #    donde empieza nada
        for carpeta in carpetas:
            carpeta.sector = 0
        tabla = len(self._tabla_de_caminos(carpetas, True))
        sectores_tabla = _sectores(tabla)

        # 2. y con eso, donde cae cada cosa
        sector = ZONA_SISTEMA + 2 + 1 + 2 * sectores_tabla
        marca_sector = sector
        if marca:
            sector += _sectores(len(marca))
        for carpeta in carpetas:
            carpeta.sector = sector
            carpeta.tamano = len(self._extension_de(carpeta))
            sector += _sectores(carpeta.tamano)
        for fichero in ficheros:
            fichero.sector = sector
            sector += _sectores(fichero.tamano)
        total = sector + RELLENO_FINAL

        # 3. la tabla de caminos se rehace ya con los sitios de verdad
        grande = _alinear(self._tabla_de_caminos(carpetas, True))
        pequena = _alinear(self._tabla_de_caminos(carpetas, False))
        sector_grande = ZONA_SISTEMA + 3
        sector_pequena = sector_grande + len(grande) // SECTOR

        # 4. y se escribe la imagen entera
        imagen = bytearray(b"\x00" * (ZONA_SISTEMA * SECTOR))
        descriptor = self._descriptor(total, tabla, sector_grande,
                                      sector_pequena, len(marca), marca_sector)
        imagen += descriptor
        imagen += descriptor                            # el mismo, dos veces
        cierre = bytearray(SECTOR)
        cierre[0] = 0xFF
        cierre[1:6] = b"CD001"
        cierre[6] = 1
        imagen += cierre
        imagen += grande
        imagen += pequena
        if marca:
            imagen += _alinear(marca)
        for carpeta in carpetas:
            imagen += _alinear(self._extension_de(carpeta))
        for fichero in ficheros:
            imagen += _alinear(fichero.datos or b"\x00")
        imagen += b"\x00" * (RELLENO_FINAL * SECTOR)
        assert len(imagen) == total * SECTOR
        return bytes(imagen)


def leer_marca(ruta: str) -> bytes:
    """Lee el fichero de marca del CD32 y comprueba que es el que es.

    No se reparte con el kit -es de Commodore- asi que lo pone quien compila.
    Un archivo equivocado daria un CD que no arranca y no dice por que, y eso es
    peor que un error: aqui se mira el tamano y la huella."""
    try:
        with open(ruta, "rb") as fh:
            datos = fh.read()
    except OSError as error:
        raise ErrorIso("no puedo leer la marca del CD32 '%s': %s" % (ruta, error))
    if len(datos) != MARCA_TAMANO:
        raise ErrorIso(
            "'%s' mide %d bytes y la marca del CD32 son %d"
            % (ruta, len(datos), MARCA_TAMANO))
    huella = hashlib.sha1(datos).hexdigest()
    if huella != MARCA_SHA1:
        raise ErrorIso(
            "'%s' no es la marca del CD32 (su huella es %s)" % (ruta, huella))
    return datos


def crear_disco_de_juego(ruta: str, etiqueta: str, ejecutable: str,
                         datos: bytes, marca: bytes = b"") -> Tuple[int, bool]:
    """Un CD que arranca solo y ejecuta el juego.

    Dentro va lo mismo que en el disquete: el ejecutable y un
    `S/Startup-Sequence` que lo llama. Lo que cambia es que aqui el sistema de
    ficheros lo pone la Kickstart del CD32 y no un bloque de arranque."""
    disco = Disco(etiqueta)
    disco.fichero(ejecutable, datos)
    carpeta_s = disco.carpeta("S")
    arranque = ("; lo primero que hace el CD al arrancar\n%s\n" % ejecutable)
    disco.fichero("Startup-Sequence", arranque.encode("latin-1"), carpeta_s)
    imagen = disco.bytes(marca)
    with open(ruta, "wb") as fh:
        fh.write(imagen)
    return len(imagen), bool(marca)


def main(argv: List[str]) -> int:
    if len(argv) < 5:
        print(__doc__)
        return 1
    destino, etiqueta, ejecutable, origen = argv[1], argv[2], argv[3], argv[4]
    try:
        with open(origen, "rb") as fh:
            datos = fh.read()
        marca = leer_marca(argv[5]) if len(argv) > 5 else b""
        tamano, arranca = crear_disco_de_juego(destino, etiqueta, ejecutable,
                                               datos, marca)
    except (OSError, ErrorIso) as error:
        sys.stderr.write("error: %s\n" % error)
        return 1
    print("CD de CD32: %s (%d KB, %s)"
          % (destino, tamano // 1024,
             "arrancable" if arranca else "sin marca: no arranca solo"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
