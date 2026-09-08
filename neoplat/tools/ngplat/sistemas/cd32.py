"""Amiga CD32: el mismo A1200 de siempre, pero en un CD y sin teclado.

Por dentro no es otra maquina: es un Amiga 1200 con 2 MB de RAM chip, el mismo
68EC020 a 14 MHz y el mismo chipset AGA. Por eso hereda de `amiga1200` y
comparte el motor entero, los ocho bitplanes, la paleta de 24 bits y el
parallax de 16+16 colores. El juego que sale es **el mismo binario**.

Lo que cambia es lo de fuera, y son dos cosas:

  1. **el envase**. No hay disquetera: el juego va en un ISO 9660 que la
     Kickstart del CD32 monta como CD0: y arranca igual que un disquete,
     ejecutando `S/Startup-Sequence`. Lo monta iso.py, que ademas escribe en el
     descriptor la entrada `TM` que hace que el CD32 lo reconozca como suyo;

  2. **el mando**. Tampoco hay teclado, asi que todo tiene que caber en el
     pad. Y cabe sin tocar una linea del motor: un mando de CD32 enchufado al
     puerto se lee como un joystick de dos botones -el **rojo** es el disparo
     de siempre (CIAA_PRA) y el **azul** el segundo boton (POTGOR)-, que es
     exactamente lo que ya lee engine/amiga. Rojo salta y empieza la partida,
     azul ataca. Los otros cinco botones del pad (verde, amarillo, play y los
     dos de pista) piden un protocolo de registro de desplazamiento y no hacen
     falta: ninguno de los nueve generos usa mas de dos botones.

El fichero de marca (CD32.TM)
-----------------------------

Son 2048 bytes de Commodore que van dentro del ISO y sin los cuales un CD32 de
verdad no arranca el disco. No se puede repartir con el kit, igual que no se
puede repartir una BIOS: lo pone quien compila, con

    make MARCA=/donde/lo/tengas/CD32.TM

o dejandolo al lado del Makefile con ese nombre. Sin el, el ISO se genera
igual -es un CD 9660 perfectamente valido y legible- pero no arranca solo, y el
compilador lo dice en vez de callarselo.
"""

from __future__ import annotations

from typing import List

from ..build import Build
from ..paths import fuente_del_kit
from .amiga import _etiqueta_disco, _nombre_ejecutable
from .amiga1200 import Amiga1200
from .base import Salida, registrar


class Cd32(Amiga1200):
    nombre = "cd32"
    titulo = "Amiga CD32"
    cpu = "68EC020 a 14 MHz (AGA, 2 MB de RAM chip)"
    nombre_binario = "el CD"

    notas = [
        "colores:  'amiga: 256colores' da 255 colores y ningun parallax;",
        "          'amiga: 16colores' parte los bitplanes en dos planos de 16",
        "          y 16 colores, y ahi si hay una capa de parallax por hardware",
        "paleta:   8 bits por canal: los colores salen exactos, sin redondear",
        "sonido:   Paula, cuatro canales; toca muestras digitales",
        "mando:    el pad de CD32 se lee como un joystick de dos botones: el",
        "          rojo salta y empieza, el azul ataca",
        "marca:    para que el CD arranque solo hace falta CD32.TM (2048 bytes,",
        "          de Commodore): 'make MARCA=/ruta/CD32.TM' o dejalo al lado",
        "          del Makefile. Sin el, el ISO vale pero no arranca",
    ]

    def generar(self, build: Build, rom_id: str) -> Salida:
        """Lo mismo que el A1200, cambiando el disquete por el CD."""
        salida = super().generar(build, rom_id)
        nombre = _nombre_ejecutable(build)
        etiqueta = _etiqueta_disco(build.project.title)

        # el mismo ejecutable, otro envase
        del salida.archivos["hacer_adf.py"]
        salida.archivos["hacer_iso.py"] = fuente_del_kit("iso.py")
        salida.archivos["Makefile"] = _makefile(build, nombre, etiqueta,
                                                self.cpu_gcc)
        salida.resumen = [linea for linea in salida.resumen
                          if not linea.startswith("disquete:")]
        salida.resumen.append(
            "CD:       disco/%s.iso (ISO 9660, arranca solo con CD32.TM)"
            % nombre)
        salida.avisos.append(
            "el CD solo arranca en un CD32 si le pones la marca de Commodore: "
            "'make MARCA=/ruta/CD32.TM' o deja CD32.TM al lado del Makefile")
        return salida


def _makefile(build: Build, nombre: str, etiqueta: str, cpu: str) -> str:
    """El mismo Makefile del Amiga con el ultimo paso cambiado: donde el A1200
    monta un disquete de 880 KB, aqui se monta un CD."""
    return """# %s para Amiga CD32, generado por NeoPlat.
#
# Necesita un compilador de 68000. Vale cualquiera de estos:
#   m68k-amigaos-gcc      (el del bebbo/amiga-gcc, si lo tienes)
#   m68k-elf-gcc
#   m68k-linux-gnu-gcc    (el paquete gcc-m68k-linux-gnu de Debian/Ubuntu)
#
# El enlazador saca un ELF; hacer_ejecutable.py lo convierte en un ejecutable de
# AmigaDOS (hunks + tabla de relocalizacion, todo en RAM chip) y hacer_iso.py
# monta con el un CD que la Kickstart del CD32 arranca sola.
#
# MARCA es el fichero CD32.TM de Commodore (2048 bytes). Sin el, el CD se
# genera igual pero **no arranca** en un CD32: son los bytes que le dicen a la
# maquina que ese disco es suyo, y no se pueden repartir con el kit. Si lo
# tienes, dejalo al lado de este Makefile o pasalo a mano:
#
#   make MARCA=/donde/lo/tengas/CD32.TM

# make trae su propio CC por defecto, asi que solo se cambia si nadie lo ha puesto
ifeq ($(origin CC), default)
CC := $(shell which m68k-elf-gcc 2>/dev/null || which m68k-linux-gnu-gcc 2>/dev/null)
endif
ifeq ($(CC),)
$(error no encuentro un compilador de 68000: instala gcc-m68k-linux-gnu o m68k-elf-gcc)
endif
PYTHON ?= python3
MARCA  ?= $(wildcard CD32.TM)

# -fno-store-merging: sin el, gcc junta dos escrituras de un byte seguidas en
# una sola de dos bytes, y si cae en una direccion impar el 68000 se para con
# un "address error". Las pruebas del kit comprueban que no quede ninguna.
CFLAGS  := %s -Os -fomit-frame-pointer -fno-builtin -ffreestanding \\
           -fno-store-merging -std=c99 -Wall -Wextra -Isrc
# -nodefaultlibs: la libgcc de un compilador de 68k para Linux esta hecha para
# 68020 y lleva instrucciones que el 68000 no tiene; las rutinas de multiplicar
# y dividir las pone src/np_aritmetica.c.
LDFLAGS := -nostdlib -nodefaultlibs -T amiga.ld -Wl,--emit-relocs -Wl,--build-id=none

SRC := src/arranque.c src/main.c src/np_video.c src/np_hud.c src/np_sound.c \\
       src/np_world.c src/np_aritmetica.c src/gamedata.c src/graficos.c \\
       src/sonido.c
OBJ := $(SRC:.c=.o)
JUEGO := disco/%s
ISO   := disco/%s.iso
DISCO := "%s"

all: $(ISO)
	@echo "CD listo: $(ISO)"

%%.o: %%.c
	$(CC) $(CFLAGS) -c $< -o $@

juego.elf: $(OBJ)
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(OBJ)

$(JUEGO): juego.elf
	@mkdir -p disco
	$(PYTHON) hacer_ejecutable.py $< $@

# El .iso se graba en un CD-R o se mete en el emulador. Dentro va el ejecutable
# y un S/Startup-Sequence que lo llama, que es lo que ejecuta la Kickstart.
$(ISO): $(JUEGO) hacer_iso.py
	$(PYTHON) hacer_iso.py $@ $(DISCO) %s $(JUEGO) $(MARCA)

# Con un emulador instalado, `make run` mete el CD y enciende la consola.
# Hace falta la Kickstart del CD32 (kick40060.CD32 y su .ext).
EMU ?= fs-uae
run: all
	$(EMU) --amiga_model=CD32 --cdrom_drive_0=$(ISO)

clean:
	rm -f $(OBJ) juego.elf $(JUEGO) $(ISO)

.PHONY: all run clean
""" % (build.project.title, cpu, nombre, nombre, etiqueta, nombre)


registrar(Cd32())
