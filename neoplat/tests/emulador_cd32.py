"""Arranca el CD del CD32 en un emulador de verdad (opcional).

Mete el ISO en PUAE con el modelo CD32 y mira lo que sale por pantalla: si la
consola no arranca el disco, aqui se ve.

Hacen falta dos cosas que **no se reparten con el kit** y que pone quien
prueba, porque son de Commodore:

  - la marca del CD (CD32.TM, 2048 bytes), que va dentro del ISO al compilar:
        make MARCA=/ruta/CD32.TM
  - la Kickstart del CD32 (kick40060.CD32 y kick40060.CD32.ext), en una carpeta
    a la que apunte NEOPLAT_ROMS_CD32.

Sin ellas la prueba se salta sola y dice por que. Con ellas:

    NEOPLAT_ROMS_CD32=/ruta/roms python3 tests/emulador_cd32.py juego.iso [capturas]
"""

from __future__ import annotations

import os
import shutil
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from libretro import Emulador, buscar_core, colores, guardar_png  # noqa: E402

CORE = "puae"
FPS = 50                       # el CD32 es PAL
SEGUNDOS_DE_ARRANQUE = 25      # un CD tarda mucho mas que un disquete

# Las dos ROMs que pide PUAE para emular un CD32, con el nombre que busca.
ROMS = ("kick40060.CD32", "kick40060.CD32.ext")


def marca_del_iso(ruta: str):
    """Lee del propio ISO si lleva la marca de Commodore, sin abrir el CD32.

    Es la entrada `TM` del descriptor principal: doce bytes en big endian que
    dicen donde esta y cuanto ocupa. Sin ella, el CD32 no arranca el disco por
    mucho que el ISO sea perfecto, asi que mirarlo aqui ahorra una prueba que
    solo podia fallar."""
    with open(ruta, "rb") as fh:
        fh.seek(16 * 2048 + 883)
        uso = fh.read(13)
    if len(uso) < 13 or uso[1:3] != b"TM":
        return None
    _, tamano, sector = struct.unpack(">HII", uso[3:13])
    return tamano, sector


def comprobar(iso: str, capturas: str = "capturas") -> int:
    core = buscar_core(CORE, "NEOPLAT_CORE_AMIGA")
    if not core:
        print("el core de PUAE no esta instalado: se salta la prueba")
        return 0
    roms = os.environ.get("NEOPLAT_ROMS_CD32", "")
    if not roms or not all(os.path.isfile(os.path.join(roms, r)) for r in ROMS):
        print("no encuentro la Kickstart del CD32 (%s en NEOPLAT_ROMS_CD32): "
              "se salta la prueba" % " y ".join(ROMS))
        return 0
    if marca_del_iso(iso) is None:
        print("el ISO no lleva la marca de Commodore (CD32.TM): un CD32 de "
              "verdad no lo arrancaria, asi que no hay nada que probar aqui")
        return 0

    os.makedirs(capturas, exist_ok=True)
    fallos = []

    def exigir(condicion, mensaje):
        if not condicion:
            fallos.append(mensaje)

    # PUAE busca las Kickstart en su carpeta de sistema: se le montan ahi
    sistema = tempfile.mkdtemp(prefix="neoplat-cd32-")
    for rom in ROMS:
        shutil.copy(os.path.join(roms, rom), os.path.join(sistema, rom))
    emu = Emulador(core, sistema=sistema, opciones={
        "puae_model": "CD32",
        "puae_video_standard": "PAL",
        "puae_chipmem_size": "2",
    })
    emu.cargar(iso)

    # --- 1) el CD arranca y sale el juego -------------------------------
    while emu.frames < SEGUNDOS_DE_ARRANQUE * FPS:
        emu.avanzar(100)
    titulo = emu.frame
    exigir(titulo is not None, "el emulador no ha dibujado ningun frame")
    if titulo is not None:
        guardar_png(titulo, os.path.join(capturas, "cd32_titulo.png"))
        cuantos = len(colores(titulo))
        # si el CD no arrancara se veria la pantalla de la consola, que es
        # practicamente un color; el titulo del juego trae la paleta entera
        exigir(cuantos >= 8,
               "en la pantalla de arranque solo hay %d colores: el CD no ha "
               "arrancado" % cuantos)

    # --- 2) se juega: el boton rojo empieza la partida -------------------
    emu.pulsar("B")                     # el rojo del pad de CD32
    emu.avanzar(6)
    emu.pulsar()
    emu.avanzar(2 * FPS)
    jugando = emu.frame
    if jugando is not None:
        guardar_png(jugando, os.path.join(capturas, "cd32_jugando.png"))
        exigir(jugando != titulo, "la pantalla no cambia al pulsar el rojo: "
                                  "la partida no empieza")

    # --- 3) y el mando mueve al heroe ------------------------------------
    antes = emu.frame
    emu.pulsar("RIGHT")
    emu.avanzar(FPS)
    emu.pulsar()
    despues = emu.frame
    exigir(antes != despues, "con la cruceta a la derecha no se mueve nada")
    if despues is not None:
        guardar_png(despues, os.path.join(capturas, "cd32_andando.png"))

    for fallo in fallos:
        print("  FALLO", fallo)
    if not fallos:
        print("el CD arranca, dibuja y se juega en el CD32; capturas en %s/"
              % capturas)
    return 1 if fallos else 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(comprobar(sys.argv[1],
                       sys.argv[2] if len(sys.argv) > 2 else "capturas"))
